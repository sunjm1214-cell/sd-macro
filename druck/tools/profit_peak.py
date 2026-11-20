"""이익 정점 규칙 — "기업이익이 정점을 찍기 전에 침체가 온 적은 없다" (ECNY 2019).

원문(ECNY 2019): "기업이익이 정점을 찍기 전에 침체가 온 걸 본 적이 없다." 그해 1분기 이익이 줄자 "마진·임금·관세를
보면 그게 정점이 아니었다고 상상하기 어렵다"고 했다 — 첫 감소 + 마진 압박을 같이 봤다.

과거 각 침체 직전의 이익 정점과 선행 기간을 표로 보여주고, 지금 이익이 정점에서 얼마나 내려왔는지,
이익률(이익/GDP)이 역사적으로 얼마나 높은지(되돌림 여지)를 확인한다.
"""
from __future__ import annotations

import pandas as pd

from ..core import Chart, Context, Signal, ToolResult
from ..registry import tool
from ..stats import fdate, fmt, to_freq, yoy_pct
from . import src


@tool(
    name="profit_peak",
    title="이익 정점 규칙 (침체 전에 이익이 먼저 꺾인다)",
    concept="18개월 룰",
    rule="기업이익이 정점을 찍기 전에 침체가 온 적은 없다. 이익이 꺾이기 시작하면 경계.",
    sources=[src("Economic Club of NY 2019 (정점 전 침체 없음)", "sources/economic-club-ny-2019"),
             src("The Endgame 2016 (이익 정점 통과)", "sources/ira-sohn-endgame-2016")],
    order=30,
    series=["CP", "USREC", "GDP"],
    layer="주식·이익",
    use="타이밍",
    lead="평균 4분기 (정점 → 침체)",
)
def run(ctx: Context, drawdown_alert: float = 5.0, lookback_q: int = 12) -> ToolResult:
    cp = to_freq(ctx.series("CP"), "Q")
    yoy = yoy_pct(cp, 4)
    peak = cp.cummax()
    dd = (cp / peak - 1) * 100
    t = cp.index[-1]
    rows = []
    for s, _ in ctx.recessions():
        before = cp[(cp.index < s) & (cp.index >= s - pd.DateOffset(months=3 * lookback_q))]
        if len(before) < 2:
            continue
        pk = before.idxmax()
        lead = (s.to_period("Q") - pk.to_period("Q")).n
        rows.append({"침체 시작": fdate(s), "직전 이익 정점": fdate(pk), "선행(분기)": lead,
                     "침체 시작 시 정점 대비": fmt((float(cp[cp.index <= s].iloc[-1]) / float(before.max()) - 1) * 100, "%", sign=True)})
    tbl = pd.DataFrame(rows)

    y_now, dd_now = float(yoy.iloc[-1]), float(dd.iloc[-1])
    recent_peak = cp.iloc[-lookback_q:].idxmax()
    if y_now < 0 and dd_now <= -drawdown_alert:
        sig, msg = Signal.ALERT, "이익이 정점에서 의미 있게 꺾임 — 규칙상 침체 전제조건 충족"
    elif y_now < 5 or dd_now < 0:
        sig, msg = Signal.WATCH, "이익 모멘텀 둔화"
    else:
        sig, msg = Signal.OK, "이익 신고점 경신 중"
    metrics = {"기준 분기": fdate(t), "기업이익(세후, 연율)": fmt(float(cp.iloc[-1]), "B$", 0),
               "전년비": fmt(y_now, "%", sign=True), "역대 고점 대비": fmt(dd_now, "%", sign=True),
               f"최근 {lookback_q}분기 고점": fdate(recent_peak)}
    if len(tbl):
        metrics["과거 평균 선행"] = fmt(tbl["선행(분기)"].mean(), "분기", 1)
    gdp = ctx.try_series("GDP")
    if gdp is not None:
        share = (cp / to_freq(gdp, "Q") * 100).dropna()
        from ..stats import percentile_rank
        sp = percentile_rank(share, float(share.iloc[-1]))
        metrics["이익/GDP (이익률)"] = fmt(float(share.iloc[-1]), "%")
        metrics["이익/GDP 역사적 분위"] = fmt(sp, "%", 0)
        if sig == Signal.OK and sp >= 95:
            msg += " — 다만 이익률이 역사적 최상단이라 되돌림 여지가 큼(그가 2019년 '정점'을 의심한 근거: 마진 압박)"
    headline = f"기업이익 전년비 {fmt(y_now, '%', sign=True)}, 고점 대비 {fmt(dd_now, '%', sign=True)} → {msg}"
    notes = ["이익 데이터(CP)는 분기 말 후 약 2개월 뒤 발표되고 이후 수정됩니다. 실시간 판단은 이보다 늦습니다.",
             "역 방향은 성립하지 않습니다: 이익이 꺾여도 침체가 오지 않은 경우(예: 1998, 2015~16)가 있습니다."]
    charts = [Chart("기업이익 전년비", {"전년비": yoy.dropna()}, kind="bar", y_title="%", hlines=[(0, "")]),
              Chart("기업이익 수준 (십억 달러, 연율)", {"기업이익": cp, "누적 고점": peak}, y_title="B$")]
    return ToolResult(sig, headline, metrics, notes,
                      [("침체 직전 이익 정점과 선행 기간", tbl if len(tbl) else pd.DataFrame({"결과": ["침체 데이터 없음"]}))],
                      charts, as_of=fdate(t))
