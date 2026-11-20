"""구리/금 비율 — 경기 기대(구리) 대 불안(금)을 한 숫자로.

#56 TomorrowX 2026-11: 1월엔 원자재·구리 신고가 돌파(구리 롱) → 11월엔 원자재 천장 후 하락(구리 숏),
  "원자재 흐름 + 방어주 주도 → 2027년 하반기 경기 실망 가능, 금리 쪽에서 생각 중".
구리는 실물 수요, 금은 불안·통화가치 하락에 오른다. 비율이 오르면 시장이 성장을, 내리면 둔화·불안을 말한다.
이 비율은 10년물 금리와 오래 같이 움직였다 — 둘이 엇갈리면 어느 한쪽이 틀린 것.
"""
from __future__ import annotations

import pandas as pd

from ..core import Chart, Context, DataUnavailable, Signal, ToolResult
from ..registry import tool
from ..stats import fmt, to_freq

YT = "https://www.youtube.com/watch?v="


def _pair(ctx: Context) -> tuple[pd.Series, str]:
    for cu, au, label in (("HG=F", "GC=F", "구리 선물 ÷ 금 선물"), ("CPER", "GLD", "구리 ETF ÷ 금 ETF")):
        try:
            r = (ctx.price(cu) / ctx.price(au)).dropna()
            if len(r) > 260:
                return r, label
        except DataUnavailable:
            continue
    raise DataUnavailable("구리·금 가격 없음")


@tool(
    name="copper_gold",
    title="구리/금 비율 (성장 기대 vs 불안)",
    concept="원자재가 먼저 말한다",
    rule="구리가 금보다 강하면 시장은 성장을, 약하면 둔화를 예상한다. 금리와 엇갈리면 한쪽이 틀렸다.",
    sources=[("Robin Hood 2016 (구리/금 = 통화 급진주의 vs 실물경제)", YT + "S_x0n5BS1Pw"),
             ("TomorrowX 2026-11 (구리 롱 → 구리 숏)", YT + "6r3D-CMJkuI")],
    order=20,
    series=["DGS10"],
    tickers=["HG=F", "GC=F", "CPER", "GLD"],
    layer="채권",
    use="타이밍",
    lead="3~9개월",
)
def run(ctx: Context, move: float = 10.0) -> ToolResult:
    r, label = _pair(ctx)
    t = r.index[-1]
    r6 = float((r.iloc[-1] / r[r.index <= t - pd.Timedelta(days=182)].iloc[-1] - 1) * 100)
    w = r[r.index >= t - pd.Timedelta(days=365)]
    pos = float((r.iloc[-1] - w.min()) / (w.max() - w.min()) * 100) if w.max() > w.min() else 50.0
    y3 = None
    try:
        y = ctx.series("DGS10")
        y3 = float(y.iloc[-1] - y[y.index <= y.index[-1] - pd.Timedelta(days=91)].iloc[-1])
    except DataUnavailable:
        pass
    r3 = float((r.iloc[-1] / r[r.index <= t - pd.Timedelta(days=91)].iloc[-1] - 1) * 100)
    if r6 <= -move and pos <= 25:
        sig, msg = Signal.ALERT, "구리가 금보다 크게 약함 — 시장이 성장 둔화를 말하는 중"
    elif r6 >= move and pos >= 75:
        sig, msg = Signal.OK, "구리가 금보다 강함 — 시장이 성장을 예상"
    else:
        sig, msg = Signal.WATCH if r6 < 0 else Signal.OK, "뚜렷한 방향 없음"
    div = ""
    if y3 is not None and ((r3 <= -5 and y3 >= 0.25) or (r3 >= 5 and y3 <= -0.25)):
        div = " · 10년물과 엇갈림(" + ("비율↓ 금리↑ — 금리 상승이 성장 때문이 아님: 인플레·재정 쪽 의심" if y3 > 0 else "비율↑ 금리↓") + ")"
        sig = Signal.WATCH if sig == Signal.OK else sig
    metrics = {"기준일": t.strftime("%Y-%m-%d"), "비율 6개월": fmt(r6, "%", 1, sign=True), "비율 3개월": fmt(r3, "%", 1, sign=True),
               "52주 범위 내 위치": fmt(pos, "%", 0)}
    if y3 is not None:
        metrics["10년물 3개월"] = fmt(y3 * 100, "bp", 0, sign=True)
    headline = f"구리/금 6개월 {r6:+.1f}%, 52주 범위 {pos:.0f}% 위치 → {msg}{div}"
    notes = [f"계산: {label}. 선물이 없으면 ETF로 대신합니다(수준은 다르지만 방향은 같음).",
             "SD는 2026년 11월 '원자재 천장 + 방어주 주도'를 근거로 경기 실망과 금리 쪽을 생각한다고 했습니다. 이 비율이 내리는데 10년물이 오르면, 금리 상승이 성장이 아니라 인플레·재정 공급 때문일 가능성을 의심하세요."]
    series = {"구리/금 비율": r}
    charts = [Chart("구리/금 비율", series, y_title="비율", years=10)]
    try:
        charts.append(Chart("구리/금 비율 vs 10년물 (월평균)", {"구리/금 (왼쪽)": to_freq(r, "M"), "10년물 % (오른쪽)": to_freq(ctx.series("DGS10"), "M")},
                            secondary=["10년물 % (오른쪽)"], years=15))
    except DataUnavailable:
        pass
    return ToolResult(sig, headline, metrics, notes, [], charts, as_of=t.strftime("%Y-%m-%d"))
