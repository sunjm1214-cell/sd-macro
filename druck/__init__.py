"""druck — SD의 매크로 판단 규칙을 데이터로 돌리는 툴킷.

파이썬에서 직접 쓰기:
    from druck import make_context, run_tool, run_all
    ctx = make_context()                       # FRED 실데이터 (demo=True면 합성)
    r = run_tool("profit_headwind", ctx, scenario_oil_pct=30, scenario_dollar_pct=10, scenario_rate_pp=1)
    print(r.signal.label, r.headline)
"""
from __future__ import annotations

import pandas as pd

from .core import Chart, Context, DataUnavailable, Signal, ToolResult
from .registry import all_tools, get_tool, run_all, run_tool, tool

__all__ = ["make_context", "run_tool", "run_all", "all_tools", "get_tool", "tool",
           "Context", "Signal", "ToolResult", "Chart", "DataUnavailable"]
__version__ = "0.1.0"


def make_context(demo: bool = False, as_of: str | None = None, refresh: bool = False,
                 cache_dir: str | None = None, csv: str | None = None, check_updates: bool = False) -> Context:
    """check_updates=True면 실행할 때 FRED/Yahoo에 새 데이터가 있는지 확인하고 바뀐 것만 갱신한다."""
    if demo:
        from .demo import DemoPrices, DemoSource
        fred, prices = DemoSource(), DemoPrices()
    else:
        from .data import FredSource, YahooSource
        fred = FredSource(cache_dir=cache_dir, refresh=refresh, check_updates=check_updates)
        prices = YahooSource(cache_dir=cache_dir, refresh=refresh, check_updates=check_updates)
    if csv:
        from .data import load_csv_overrides
        load_csv_overrides(fred, csv)
    return Context(fred=fred, prices=prices, as_of=pd.Timestamp(as_of) if as_of else None)
