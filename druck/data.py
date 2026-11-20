"""데이터 소스.

- FredSource: FRED(세인트루이스 연준). API 키 없이 fredgraph CSV로 받고, 로컬에 캐시한다.
  check_updates=True(기본 실행)면 매번 원천을 확인해 새 관측치·개정이 있을 때만 캐시를 고치고 결과를 기록한다.
  환경변수 FRED_API_KEY가 있으면 공식 API를 쓴다.
- YahooSource: 업종 ETF 가격 (yfinance 설치 시).
- CsvSource: 직접 가진 CSV로 어떤 시리즈든 덮어쓰기/추가 (예: 컨센서스 EPS, 사내 데이터).
"""
from __future__ import annotations

import io
import json
import os
import sys
import threading
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd

from .core import DataUnavailable

FRED_CSV = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}"
FRED_API = "https://api.stlouisfed.org/fred/series/observations?{q}"


def _default_cache() -> Path:
    return Path(os.environ.get("DRUCK_CACHE", Path.home() / ".druck_cache"))


def parse_fred_csv(text: str, sid: str) -> pd.Series:
    df = pd.read_csv(io.StringIO(text), na_values=["."])
    if df.shape[1] < 2:
        raise ValueError("CSV 형식이 아닙니다")
    date_col = df.columns[0]
    val_col = sid if sid in df.columns else df.columns[1]
    s = pd.Series(
        pd.to_numeric(df[val_col], errors="coerce").to_numpy(),
        index=pd.to_datetime(df[date_col]),
        name=sid,
    )
    s = s.dropna().sort_index()
    if s.empty:
        raise ValueError("빈 시리즈")
    return s


class _Cache:
    def __init__(self, cache_dir, max_age_hours, refresh):
        self.dir = Path(cache_dir) if cache_dir else _default_cache()
        self.max_age = max_age_hours * 3600
        self.refresh = refresh

    def path(self, kind: str, key: str) -> Path:
        safe = "".join(c if c.isalnum() or c in "-_." else "_" for c in key)
        return self.dir / kind / f"{safe}.csv"

    def read(self, p: Path, allow_stale=False) -> pd.Series | None:
        if not p.exists():
            return None
        fresh = (time.time() - p.stat().st_mtime) < self.max_age
        if (fresh and not self.refresh) or allow_stale:
            s = pd.read_csv(p, index_col=0, parse_dates=True).iloc[:, 0]
            return s.dropna()
        return None

    def write(self, p: Path, s: pd.Series):
        p.parent.mkdir(parents=True, exist_ok=True)
        s.to_csv(p)


def compare(old: pd.Series | None, new: pd.Series) -> dict:
    """받아 둔 데이터(old)와 방금 받은 데이터(new)를 비교한다.

    status: first(처음 받음) | new(새 관측치 추가) | revised(과거 값 개정) | same(변화 없음)
    """
    new_last = new.index[-1]
    if old is None or old.empty:
        return {"status": "first", "old_last": None, "new_last": new_last, "added": len(new), "revised": 0}
    old_last = old.index[-1]
    added = int((new.index > old_last).sum())
    both = old.index.intersection(new.index)
    diff = (new.reindex(both).astype(float) - old.reindex(both).astype(float)).abs()
    revised = int((diff > 1e-9 * (1 + old.reindex(both).abs())).sum())
    status = "new" if added else ("revised" if revised else "same")
    return {"status": status, "old_last": old_last, "new_last": new_last, "added": added, "revised": revised}


class _Checked:
    """'실행할 때마다 원천에 새 데이터가 있는지 확인' 모드의 공통 동작.

    check_updates=True면 캐시 나이와 상관없이 원천에서 다시 받아 캐시와 비교하고, 바뀐 경우에만 캐시를 고친다.
    네트워크가 안 되면 받아 둔 캐시를 쓰고 status='offline'으로 기록한다. 결과는 self.updates에 쌓인다.
    """

    kind = ""

    def _init_check(self, check_updates: bool):
        self.check_updates = check_updates
        self.updates: dict[str, dict] = {}
        self._lock = threading.Lock()

    def _load(self, key: str, download) -> pd.Series:
        p = self.cache.path(self.kind, key)
        if not self.check_updates:
            s = self.cache.read(p)
            if s is not None:
                return s
        old = self.cache.read(p, allow_stale=True)
        try:
            s = download(key)
        except Exception as e:  # 네트워크 실패 시 받아 둔 캐시라도 쓴다
            if old is None:
                raise DataUnavailable(f"{self.kind} {key} 다운로드 실패: {e}") from e
            with self._lock:
                self.updates[key] = {"status": "offline", "old_last": old.index[-1], "new_last": old.index[-1],
                                     "added": 0, "revised": 0, "error": str(e)[:120]}
            print(f"[경고] {key}: 다운로드 실패, 받아 둔 데이터 사용", file=sys.stderr)
            return old
        info = compare(old, s)
        if self.kind == "yahoo" and info["status"] == "revised":
            info["status"] = "same"  # 수정주가(배당 반영)·장중 마지막 봉은 매번 바뀌므로 '개정'으로 치지 않는다
            info["revised"] = 0
            self.cache.write(p, s)
        elif info["status"] != "same" or old is None:
            self.cache.write(p, s)
        else:
            p.touch()  # 확인했다는 표시 (캐시 나이 갱신)
        with self._lock:
            self.updates[key] = info
        return s

    def prefetch(self, keys, workers: int = 8):
        """여러 시리즈를 병렬로 확인/다운로드한다. 실패는 무시(실제 사용 시 다시 처리)."""
        keys = [k for k in dict.fromkeys(keys) if k not in self._mem and k not in getattr(self, "overrides", {})]

        def one(k):
            try:
                self.get(k)
            except Exception:
                pass

        with ThreadPoolExecutor(max_workers=workers) as ex:
            list(ex.map(one, keys))


class FredSource(_Checked):
    kind = "fred"

    def __init__(self, cache_dir=None, max_age_hours: float = 12, refresh: bool = False,
                 api_key: str | None = None, timeout: float = 20, check_updates: bool = False):
        self.cache = _Cache(cache_dir, max_age_hours, refresh)
        self.api_key = api_key or os.environ.get("FRED_API_KEY") or None
        self.timeout = timeout
        self._mem: dict[str, pd.Series] = {}
        self._failed: dict[str, str] = {}
        self.overrides: dict[str, pd.Series] = {}
        self._init_check(check_updates or refresh)

    def get(self, sid: str) -> pd.Series:
        if sid in self.overrides:
            return self.overrides[sid].copy()
        if sid in self._mem:
            return self._mem[sid].copy()
        if sid in self._failed:  # 이번 실행에서 이미 실패 — 다시 기다리지 않는다
            raise DataUnavailable(self._failed[sid])
        try:
            s = self._load(sid, self._download).astype(float).rename(sid)
        except DataUnavailable as e:
            self._failed[sid] = str(e)
            raise
        self._mem[sid] = s
        return s.copy()

    def _fetch(self, url: str) -> str:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36 sd-macro",
            "Accept": "text/csv,application/json,*/*"})
        with urllib.request.urlopen(req, timeout=self.timeout) as r:
            return r.read().decode("utf-8")

    def _download(self, sid: str) -> pd.Series:
        if self.api_key:
            q = urllib.parse.urlencode({"series_id": sid, "api_key": self.api_key, "file_type": "json"})
            obs = json.loads(self._fetch(FRED_API.format(q=q)))["observations"]
            s = pd.Series(
                pd.to_numeric([o["value"] for o in obs], errors="coerce"),
                index=pd.to_datetime([o["date"] for o in obs]),
                name=sid,
            ).dropna()
            if s.empty:
                raise ValueError("빈 시리즈")
            return s
        return parse_fred_csv(self._fetch(FRED_CSV.format(sid=sid)), sid)


class YahooSource(_Checked):
    """ETF 종가. yfinance가 없으면 DataUnavailable."""

    kind = "yahoo"

    def __init__(self, cache_dir=None, max_age_hours: float = 12, refresh: bool = False, start="1999-01-01",
                 check_updates: bool = False):
        self.cache = _Cache(cache_dir, max_age_hours, refresh)
        self.start = start
        self._mem: dict[str, pd.Series] = {}
        self._failed: dict[str, str] = {}
        self._init_check(check_updates or refresh)

    def get(self, ticker: str) -> pd.Series:
        if ticker in self._mem:
            return self._mem[ticker].copy()
        if ticker in self._failed:
            raise DataUnavailable(self._failed[ticker])
        try:
            s = self._load(ticker, self._download).astype(float).rename(ticker)
        except DataUnavailable as e:
            self._failed[ticker] = str(e)
            raise
        self._mem[ticker] = s
        return s.copy()

    def _download(self, ticker: str) -> pd.Series:
        try:
            import yfinance as yf
        except ImportError as e:
            raise DataUnavailable("yfinance 미설치 → pip install yfinance") from e
        df = None
        for attempt in range(3):  # 병렬 다운로드 때 yfinance 내부 캐시가 잠기는 경우('database is locked') 다시 시도
            df = yf.download(ticker, start=self.start, auto_adjust=True, progress=False, threads=False, timeout=20)
            if df is not None and not df.empty:
                break
            time.sleep(1 + attempt)
        if df is None or df.empty:
            raise ValueError("빈 데이터")
        close = df["Close"]
        if isinstance(close, pd.DataFrame):
            close = close.iloc[:, 0]
        s = close.dropna().rename(ticker)
        if s.empty:
            raise ValueError("빈 데이터")
        s.index = pd.to_datetime(s.index).tz_localize(None)
        return s


def update_rows(*sources) -> list[dict]:
    """이번 실행의 데이터 확인 결과를 표로 (새 데이터 → 개정 → 처음 → 실패 → 변화 없음 순)."""
    label = {"new": "새 데이터", "revised": "과거 값 개정", "first": "처음 받음", "offline": "확인 실패(기존 데이터 사용)",
             "same": "변화 없음"}
    order = list(label)
    rows = []
    for src in sources:
        for key, u in getattr(src, "updates", {}).items():
            d = lambda ts: pd.Timestamp(ts).strftime("%Y-%m-%d") if ts is not None else "-"
            rows.append({"원천": "FRED" if getattr(src, "kind", "") == "fred" else "Yahoo", "시리즈": key,
                         "결과": label[u["status"]], "_s": u["status"],
                         "이전 마지막": d(u["old_last"]), "최신 마지막": d(u["new_last"]),
                         "추가": u["added"], "개정": u["revised"]})
    rows.sort(key=lambda r: (order.index(r["_s"]), r["원천"], r["시리즈"]))
    return rows


def load_csv_overrides(source, path: str):
    """CSV(date, 시리즈ID1, 시리즈ID2, ...)를 읽어 소스의 해당 시리즈를 덮어쓴다."""
    df = pd.read_csv(path, index_col=0, parse_dates=True)
    for col in df.columns:
        source.overrides[col] = pd.to_numeric(df[col], errors="coerce").dropna().rename(col)
    return list(df.columns)
