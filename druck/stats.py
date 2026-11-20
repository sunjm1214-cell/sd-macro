"""공통 통계 도구: 주기 변환, 변화율, OLS(Newey-West), 분위수, 구간 탐지, 단위 정규화, 포맷."""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

_PD_NEW = tuple(int(x) for x in pd.__version__.split(".")[:2]) >= (2, 2)
_ALIAS = {"M": "ME", "Q": "QE", "A": "YE"} if _PD_NEW else {"M": "M", "Q": "Q", "A": "A"}


_SLACK_DAYS = {"M": 7, "Q": 45, "A": 100}  # 마지막 관측이 기간 끝에서 이만큼 이내면 '다 찬' 기간으로 본다


def to_freq(s: pd.Series, freq: str, how: str = "mean", complete: bool = True) -> pd.Series:
    """freq: 'M' | 'Q' | 'A' | 'W' (수요일 기준 주간). how: mean | last.

    complete=True면 더 촘촘한 데이터(일별→월 등)를 묶을 때 아직 덜 찬 마지막 기간을 버린다.
    예: 10월 2일까지만 있는 일별 달러지수의 '10월 평균'은 이틀치라 한 달 값처럼 쓰면 안 된다.
    """
    rule = "W-WED" if freq == "W" else _ALIAS[freq]
    r = s.resample(rule)
    out = (r.mean() if how == "mean" else r.last()).dropna()
    if complete and freq in _SLACK_DAYS and len(out) and len(s) > 2:
        step = pd.Series(s.index).diff().dt.days.median()
        period_days = {"M": 30, "Q": 91, "A": 365}[freq]
        if step < period_days * 0.8 and (out.index[-1] - s.index[-1]).days > _SLACK_DAYS[freq]:
            out = out.iloc[:-1]
    return out


def yoy_pct(s: pd.Series, periods: int) -> pd.Series:
    """고정 주기 시리즈의 periods 전 대비 % 변화."""
    return (s / s.shift(periods) - 1.0) * 100.0


def diff(s: pd.Series, periods: int) -> pd.Series:
    return s - s.shift(periods)


def zscore(s: pd.Series) -> pd.Series:
    sd = s.std()
    return (s - s.mean()) / sd if sd and not math.isnan(sd) else s * 0.0


def percentile_rank(history: pd.Series, value: float) -> float:
    """value가 history 안에서 몇 번째 백분위(0~100)인지."""
    h = history.dropna().to_numpy()
    if len(h) == 0 or value is None or (isinstance(value, float) and math.isnan(value)):
        return float("nan")
    return float((h < value).mean() * 100.0 + (h == value).mean() * 50.0)


def episodes(mask: pd.Series, min_len: int = 1, merge_gap: int = 0) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    """True가 연속된 구간의 (시작, 끝) 목록. merge_gap 관측치 이하 공백은 합친다."""
    v = mask.astype("boolean").fillna(False).to_numpy(dtype=bool)
    idx = mask.index
    runs: list[list[int]] = []
    i = 0
    while i < len(v):
        if v[i]:
            j = i
            while j + 1 < len(v) and v[j + 1]:
                j += 1
            runs.append([i, j])
            i = j + 1
        else:
            i += 1
    merged: list[list[int]] = []
    for r in runs:
        if merged and r[0] - merged[-1][1] - 1 <= merge_gap:
            merged[-1][1] = r[1]
        else:
            merged.append(r)
    return [(idx[a], idx[b]) for a, b in merged if b - a + 1 >= min_len]


def to_billions(s: pd.Series, lo: float, hi: float) -> pd.Series:
    """단위가 백만/십억 중 무엇이든, 예상 범위(십억 달러 기준 lo~hi)에 맞도록 스케일을 맞춘다.

    FRED 시리즈는 단위가 제각각이고 가끔 바뀐다. 상위 90% 분위 값이
    [lo/10, hi*10] 안에 들어오는 첫 배율(1, 1e-3, 1e-6)을 고른다.
    """
    q = s.abs().quantile(0.9)
    for f in (1.0, 1e-3, 1e-6):
        if lo / 10 <= q * f <= hi * 10:
            return s * f
    return s


# ---------------------------------------------------------------- 회귀

def ols(y: pd.Series, X: pd.DataFrame, nw_lags: int = 0) -> dict:
    """상수항 포함 OLS. nw_lags>0이면 Newey-West(HAC) 표준오차.

    겹치는 관측치(예: 4분기 선행 수익률)를 쓰면 잔차가 자기상관되므로 HAC가 필요하다.
    """
    df = pd.concat([y.rename("__y"), X], axis=1).dropna()
    if len(df) < X.shape[1] + 5:
        raise ValueError("회귀에 필요한 관측치가 부족합니다")
    yv = df["__y"].to_numpy(float)
    names = ["상수"] + list(X.columns)
    Xv = np.column_stack([np.ones(len(df)), df[list(X.columns)].to_numpy(float)])
    n, k = Xv.shape
    XtX_inv = np.linalg.pinv(Xv.T @ Xv)
    beta = XtX_inv @ Xv.T @ yv
    resid = yv - Xv @ beta
    if nw_lags > 0:
        u = Xv * resid[:, None]
        S = u.T @ u
        for lag in range(1, nw_lags + 1):
            w = 1.0 - lag / (nw_lags + 1.0)
            G = u[lag:].T @ u[:-lag]
            S += w * (G + G.T)
        cov = XtX_inv @ S @ XtX_inv * n / (n - k)
    else:
        sigma2 = resid @ resid / (n - k)
        cov = XtX_inv * sigma2
    se = np.sqrt(np.clip(np.diag(cov), 0, None))
    ss_tot = ((yv - yv.mean()) ** 2).sum()
    r2 = 1 - (resid @ resid) / ss_tot if ss_tot > 0 else float("nan")
    return {
        "coef": pd.Series(beta, index=names),
        "se": pd.Series(se, index=names),
        "t": pd.Series(beta / np.where(se == 0, np.nan, se), index=names),
        "r2": float(r2),
        "nobs": int(n),
        "fitted": pd.Series(Xv @ beta, index=df.index),
        "resid": pd.Series(resid, index=df.index),
    }


def predict(fit: dict, x: dict | pd.Series) -> float:
    coef = fit["coef"]
    total = coef["상수"]
    for name, b in coef.items():
        if name == "상수":
            continue
        total += b * float(x[name])
    return float(total)


# ---------------------------------------------------------------- 포맷

def fmt(v, unit: str = "", digits: int = 1, sign: bool = False) -> str:
    if v is None or (isinstance(v, float) and (math.isnan(v) or math.isinf(v))):
        return "-"
    s = f"{v:+,.{digits}f}" if sign else f"{v:,.{digits}f}"
    return f"{s}{unit}"


def fdate(ts) -> str:
    if ts is None or (isinstance(ts, float) and math.isnan(ts)):
        return "-"
    return pd.Timestamp(ts).strftime("%Y-%m")


def last(s: pd.Series) -> tuple[pd.Timestamp, float]:
    s = s.dropna()
    if s.empty:
        return None, float("nan")
    return s.index[-1], float(s.iloc[-1])
