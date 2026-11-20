"""툴 레지스트리. druck/tools/ 안의 파일은 자동으로 불러와 등록된다.

새 툴 추가 방법은 druck/tools/_template.py 참고.
"""
from __future__ import annotations

import importlib
import inspect
import pkgutil
import traceback
from dataclasses import dataclass, field
from typing import Callable

from .core import Context, DataUnavailable, Signal, ToolResult


# SD의 읽는 순서: 유동성·연준(원인) → 채권(먼저 읽는 방향) → 통화 → 주식·이익(확인) → 누적 위험(크기·배경)
LAYERS = ["유동성·연준", "채권", "통화", "주식·이익", "누적 위험"]
USES = {"타이밍": "언제 — 방향 전환 신호", "사이즈": "얼마나 — 위험보상의 크기, 타이밍 도구 아님",
        "배경": "수년 단위 구조 — 시점 신호 아님"}


@dataclass
class ToolSpec:
    name: str
    title: str
    concept: str          # SD 개념 (예: 유동성 > 실적)
    rule: str             # 그가 말한 규칙을 한 문장으로
    sources: list[tuple[str, str]]  # (라벨, URL)
    func: Callable[..., ToolResult]
    order: int = 100
    series: list[str] = field(default_factory=list)
    layer: str = "주식·이익"
    use: str = "타이밍"
    lead: str = ""        # 선행 기간 (예: "6~12개월")
    tickers: list[str] = field(default_factory=list)  # Yahoo 가격 티커 (리포트의 데이터 원본 링크용)

    @property
    def params(self) -> dict:
        sig = inspect.signature(self.func)
        return {k: v.default for k, v in list(sig.parameters.items())[1:]
                if v.default is not inspect.Parameter.empty}


_REGISTRY: dict[str, ToolSpec] = {}
_LOADED = False


def tool(name: str, title: str, concept: str, rule: str, sources=(), order: int = 100, series=(),
         layer: str = "주식·이익", use: str = "타이밍", lead: str = "", tickers=()):
    """툴 등록 데코레이터. 함수 시그니처: fn(ctx: Context, **params) -> ToolResult

    layer: LAYERS 중 하나 (리포트에서 이 순서로 묶인다), use: USES 중 하나.
    """

    def deco(fn):
        if name in _REGISTRY:
            raise ValueError(f"툴 이름 중복: {name}")
        if layer not in LAYERS or use not in USES:
            raise ValueError(f"{name}: layer는 {LAYERS}, use는 {list(USES)} 중 하나")
        _REGISTRY[name] = ToolSpec(name, title, concept, rule, list(sources), fn, order, list(series),
                                   layer, use, lead, list(tickers))
        return fn

    return deco


def load_tools():
    global _LOADED
    if _LOADED:
        return
    from . import tools as pkg

    for m in pkgutil.iter_modules(pkg.__path__):
        if not m.name.startswith("_"):
            importlib.import_module(f"{pkg.__name__}.{m.name}")
    _LOADED = True


def all_tools() -> list[ToolSpec]:
    load_tools()
    return sorted(_REGISTRY.values(), key=lambda t: (LAYERS.index(t.layer), t.order, t.name))


def get_tool(name: str) -> ToolSpec:
    load_tools()
    if name not in _REGISTRY:
        raise KeyError(f"없는 툴: {name}. 목록: {', '.join(_REGISTRY)}")
    return _REGISTRY[name]


def run_tool(name: str, ctx: Context, **params) -> ToolResult:
    spec = get_tool(name)
    known = spec.params
    unknown = set(params) - set(known)
    if unknown:
        raise TypeError(f"{name}: 알 수 없는 파라미터 {sorted(unknown)}. 가능: {sorted(known)}")
    try:
        res = spec.func(ctx, **params)
    except DataUnavailable as e:
        res = ToolResult(Signal.NA, f"데이터 부족으로 판단 불가: {e}", error=str(e))
    except Exception as e:  # 한 툴이 실패해도 대시보드 전체는 돈다
        res = ToolResult(Signal.NA, f"실행 오류: {type(e).__name__}: {e}",
                         error=traceback.format_exc())
    res.tool, res.title = spec.name, spec.title
    return res


def run_all(ctx: Context, names: list[str] | None = None, params: dict[str, dict] | None = None):
    params = params or {}
    specs = all_tools() if not names else [get_tool(n) for n in names]
    return [run_tool(s.name, ctx, **params.get(s.name, {})) for s in specs]
