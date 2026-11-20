"""핵심 자료구조: 신호(경고등), 차트, 툴 결과, 실행 컨텍스트."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import pandas as pd


class DataUnavailable(Exception):
    """데이터를 받을 수 없을 때. 툴은 이 예외를 그대로 올리면 '판단불가'로 처리된다."""


class Signal(str, Enum):
    """모든 툴은 '경고등' 하나를 낸다. 초록=경고 없음, 노랑=주시, 빨강=SD식 경고."""

    OK = "ok"
    WATCH = "watch"
    ALERT = "alert"
    NA = "n/a"

    @property
    def label(self) -> str:
        return {"ok": "🟢 양호", "watch": "🟡 주시", "alert": "🔴 경고", "n/a": "⚪ 판단불가"}[self.value]

    @property
    def rank(self) -> int:
        return {"ok": 0, "watch": 1, "alert": 2, "n/a": -1}[self.value]


@dataclass
class Chart:
    title: str
    series: dict[str, pd.Series]
    kind: str = "line"  # line | bar
    y_title: str = ""
    hlines: list[tuple[float, str]] = field(default_factory=list)
    shade_recessions: bool = True
    secondary: list[str] = field(default_factory=list)  # 오른쪽 축에 그릴 시리즈 이름
    years: int | None = 30  # 처음 보여줄 최근 기간(년). None이면 전체


@dataclass
class ToolResult:
    signal: Signal
    headline: str
    metrics: dict[str, str] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)
    tables: list[tuple[str, pd.DataFrame]] = field(default_factory=list)
    charts: list[Chart] = field(default_factory=list)
    as_of: str | None = None
    data: dict[str, Any] = field(default_factory=dict)  # 다른 툴/코드에서 재사용할 원자료
    # 아래는 실행기가 채운다
    tool: str = ""
    title: str = ""
    error: str | None = None


@dataclass
class Context:
    """툴이 데이터에 접근하는 유일한 통로. as_of를 주면 그 날짜까지의 데이터만 보인다."""

    fred: Any
    prices: Any = None
    as_of: pd.Timestamp | None = None
    _recessions: list[tuple[pd.Timestamp, pd.Timestamp]] | None = None

    def series(self, sid: str) -> pd.Series:
        s = self.fred.get(sid)
        if self.as_of is not None:
            s = s[s.index <= self.as_of]
        if s.empty:
            raise DataUnavailable(f"{sid}: 해당 기간 데이터 없음")
        return s

    def try_series(self, sid: str) -> pd.Series | None:
        try:
            return self.series(sid)
        except DataUnavailable:
            return None

    def price(self, ticker: str) -> pd.Series:
        if self.prices is None:
            raise DataUnavailable("가격 데이터 소스가 없습니다")
        s = self.prices.get(ticker)
        if self.as_of is not None:
            s = s[s.index <= self.as_of]
        if s.empty:
            raise DataUnavailable(f"{ticker}: 해당 기간 가격 없음")
        return s

    def recessions(self) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
        """NBER 경기침체 구간 (USREC). 못 받으면 빈 리스트."""
        if self._recessions is None:
            from .stats import episodes

            try:
                rec = self.series("USREC")
                self._recessions = episodes(rec > 0.5)
            except DataUnavailable:
                self._recessions = []
        return self._recessions
