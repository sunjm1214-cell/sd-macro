"""신흥국 스트레스 — "유동성 축소는 늘 신흥국에서 먼저 터진다".

#13 Real Vision 2018-11: 유동성 축소가 이미 신흥국에서 시작됐다 — "늘 거기서 시작한다". 아직 안 터진 곳은 신용시장.
#7/#8 DealBook 2015: 6년 제로금리·QE가 신흥국 정부(브라질·터키)를 시장 규율 없이 행동하게 만들었다.
그래서 (1) 신흥국 주식이 미국 대비 얼마나 약한지, (2) 신흥국 달러채가 미 국채 대비 얼마나 밀리는지(스프레드 대용)를 본다.
"""
from __future__ import annotations

import pandas as pd

from ..core import Chart, Context, DataUnavailable, Signal, ToolResult
from ..registry import tool
from ..stats import fmt

YT = "https://www.youtube.com/watch?v="


@tool(
    name="em_stress",
    title="신흥국 스트레스 (신흥국 주식·달러채 vs 미국)",
    concept="균열은 바깥부터",
    rule="유동성이 줄면 가장 약한 고리인 신흥국이 먼저 깨진다. 그다음이 신용시장이다.",
    sources=[("Real Vision 2018-11 (늘 신흥국에서 시작)", YT + "G-MlrpoMig0"),
             ("DealBook 2015 (시장 규율 없는 신흥국 정부)", YT + "aviToCACiNA")],
    order=20,
    series=[],
    tickers=["EEM", "SPY", "EMB", "IEF"],
    layer="통화",
    use="타이밍",
    lead="수 주~수 개월 (전염 경로)",
)
def run(ctx: Context, eq_weak: float = -5.0, bond_weak: float = -2.0) -> ToolResult:
    eem, spy = ctx.price("EEM"), ctx.price("SPY")
    rel = (eem / spy).dropna()
    r6 = float((rel.iloc[-1] / rel[rel.index <= rel.index[-1] - pd.Timedelta(days=182)].iloc[-1] - 1) * 100)
    w = rel[rel.index >= rel.index[-1] - pd.Timedelta(days=365)]
    near_low = float((rel.iloc[-1] / w.min() - 1) * 100) <= 2.0
    eq_bad = r6 <= eq_weak and near_low
    bond_bad, b3, brel = False, None, None
    try:
        brel = (ctx.price("EMB") / ctx.price("IEF")).dropna()
        b3 = float((brel.iloc[-1] / brel[brel.index <= brel.index[-1] - pd.Timedelta(days=91)].iloc[-1] - 1) * 100)
        bond_bad = b3 <= bond_weak
    except DataUnavailable:
        pass
    if eq_bad and bond_bad:
        sig, msg = Signal.ALERT, "신흥국 주식과 달러채가 함께 밀림 — 유동성 축소가 바깥 고리부터 깨뜨리는 모습"
    elif eq_bad or bond_bad:
        sig, msg = Signal.WATCH, ("신흥국 주식이 미국 대비 52주 상대 저점권" if eq_bad else "신흥국 달러채가 미 국채 대비 밀림(스프레드 확대)") + " — 한쪽만, 확산 여부 주시"
    else:
        sig, msg = Signal.OK, "신흥국에서 스트레스 신호 없음"
    t = rel.index[-1]
    metrics = {"기준일": t.strftime("%Y-%m-%d"), "신흥국 주식/S&P 6개월": fmt(r6, "%", 1, sign=True),
               "52주 상대 저점 근처": "예" if near_low else "아니오"}
    if b3 is not None:
        metrics["신흥국 달러채/미 국채 3개월"] = fmt(b3, "%", 1, sign=True)
    headline = f"신흥국 주식 상대 6개월 {r6:+.1f}%" + (f", 달러채 상대 3개월 {b3:+.1f}%" if b3 is not None else "") + f" → {msg}"
    notes = [
        "EEM(신흥국 주식) ÷ SPY, EMB(신흥국 달러 국채) ÷ IEF(미 7~10년 국채)입니다. 두 번째 비율이 내리면 신흥국 채권이 미 국채보다 약하다는 뜻이라 스프레드 확대의 대용으로 씁니다.",
        "강달러·고금리는 달러 빚이 많은 신흥국을 먼저 압박합니다. 달러 도구와 같이 보세요.",
    ]
    series = {"신흥국 주식 / S&P 500": rel / rel.iloc[0] * 100}
    if brel is not None:
        series["신흥국 달러채 / 미 국채"] = brel / brel.iloc[0] * 100
    charts = [Chart("신흥국 상대 강도 (시작=100)", series, y_title="시작=100", shade_recessions=True, years=10)]
    return ToolResult(sig, headline, metrics, notes, [], charts, as_of=t.strftime("%Y-%m-%d"))
