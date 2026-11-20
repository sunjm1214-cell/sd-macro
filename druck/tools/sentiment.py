"""소비자심리 — 뻔한 것은 이미 가격에 있다.

How Leaders Lead(2022 녹화): "뻔한 것은 뻔하게 틀렸고 이미 증권 가격에 반영돼 있다. 모든 게 장밋빛이면 더 살 사람이 없다.
거꾸로 무엇이 잘될 수 있는지도 봐야 한다. 거의 모든 주식시장 바닥이 침체와 나쁜 실적 속에서, 모든 천장이 소비자 신뢰가
높을 때 오는 건 우연이 아니다."
Morgan Stanley 2026: "역발상은 과대평가돼 있다." — 그래서 이 툴은 단독 매매 신호가 아니라 '분위기 점검'이다.
"""
from __future__ import annotations

import pandas as pd

from ..core import Chart, Context, Signal, ToolResult
from ..registry import tool
from ..stats import fdate, fmt, percentile_rank, to_freq, yoy_pct
from . import src


@tool(
    name="sentiment",
    title="소비자심리 (천장은 낙관 속에, 바닥은 비관 속에)",
    concept="18개월 룰 · 지적 겸손",
    rule="천장은 소비자 신뢰가 높을 때, 바닥은 침체와 나쁜 실적 속에서 온다. 모두가 아는 장밋빛은 이미 가격에 있다.",
    sources=[src("How Leaders Lead (바닥·천장과 소비자 신뢰)", "sources/how-leaders-lead-novak-2024"),
             src("Morgan Stanley 2026 (역발상은 과대평가)", "sources/morgan-stanley-hard-lessons-2026")],
    order=40,
    series=["UMCSENT", "CP", "USREC"],
    layer="주식·이익",
    use="타이밍",
    lead="수개월 (극단에서만 의미)",
)
def run(ctx: Context, high_pct: float = 80.0, low_pct: float = 15.0) -> ToolResult:
    s = to_freq(ctx.series("UMCSENT"), "M")
    t, now = s.index[-1], float(s.iloc[-1])
    pct = percentile_rank(s, now)
    chg12 = float(s.iloc[-1] - s.iloc[-13]) if len(s) > 13 else float("nan")
    cp = ctx.try_series("CP")
    cp_yoy = float(yoy_pct(to_freq(cp, "Q"), 4).dropna().iloc[-1]) if cp is not None else float("nan")
    rec = ctx.try_series("USREC")
    in_rec = bool(rec is not None and float(rec.iloc[-1]) > 0.5)

    if pct >= high_pct:
        sig, msg = Signal.WATCH, "소비자 낙관이 역사적 상단 — 그의 말로 '천장은 신뢰가 높을 때'"
    elif pct <= low_pct and (in_rec or cp_yoy < 0):
        sig, msg = Signal.OK, "비관 극단 + 침체/이익 감소 — 역사적으로 바닥이 만들어지던 조합(역발상 기회 점검)"
    elif pct <= low_pct:
        sig, msg = Signal.OK, "비관 극단이지만 이익·경기는 아직 버팀 — 심리와 실물의 괴리"
    else:
        sig, msg = Signal.OK, "심리 중립 구간"
    headline = f"미시간대 소비자심리 {now:.1f} (역사적 {pct:.0f}% 분위) → {msg}"
    metrics = {"기준월": fdate(t), "소비자심리": fmt(now, "", 1), "역사적 분위": fmt(pct, "%", 0),
               "1년 변화": fmt(chg12, "", 1, sign=True), "기업이익 전년비": fmt(cp_yoy, "%", sign=True),
               "침체 중(NBER)": "예" if in_rec else "아니오"}
    notes = ["이 툴의 초록은 '위험 없음'이 아니라 '심리가 과열되지 않았다'는 뜻입니다. 비관 극단은 그에게 매수 후보를 찾는 출발점이었지, 그 자체로 매수 신호는 아니었습니다.",
             "2026년 그는 '역발상은 과대평가돼 있다, 다만 확신이 극단적인데 아무도 안 믿을 때는 확신이 더 커진다'고 했습니다."]
    charts = [Chart("미시간대 소비자심리지수", {"소비자심리": s}, y_title="지수",
                    hlines=[(float(s.quantile(high_pct / 100)), "상단"), (float(s.quantile(low_pct / 100)), "하단")])]
    return ToolResult(sig, headline, metrics, notes, [], charts, as_of=fdate(t))
