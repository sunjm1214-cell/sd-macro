"""글로벌 중앙은행 유동성 — 연준 + ECB + 일본은행 대차대조표 합산의 '변화율'.

#10 CNBC 2017-12: "중앙은행들이 연 1조 달러를 사고 있다. ECB가 9월에 멈추면 이 속도가 −6천억으로 간다.
                   하루 30억 달러 매수가 20억 달러 매도로 — 이 변화가 자산가격을 버티게 하기 어렵다."
#13 Real Vision 2018-11: "1년 안에 1조에서 0으로. 내게 중요한 건 이익도 정치도 아니라 언제나 유동성."
그래서 수준이 아니라 1년 증감(속도)과 그 증감이 1년 전보다 늘었는지 줄었는지(가속도)를 본다.
환율 변동이 섞이지 않도록 과거 값도 '최근 환율'로 달러 환산한다(고정환율 기준).
"""
from __future__ import annotations

import pandas as pd

from ..core import Chart, Context, DataUnavailable, Signal, ToolResult
from ..registry import tool
from ..stats import fdate, fmt, to_freq

YT = "https://www.youtube.com/watch?v="


@tool(
    name="global_liquidity",
    title="글로벌 중앙은행 유동성 (연준 + ECB + 일본은행)",
    concept="유동성 > 실적 · 변화율",
    rule="미국만이 아니라 세계 중앙은행 순매입의 '속도 변화'가 자산가격을 움직인다. 1조 달러 매입이 0으로 가는 것 자체가 위험이다.",
    sources=[("CNBC 2017-12 (연 1조 → −6천억)", YT + "DWDgJ_hNFSE"),
             ("Real Vision 2018-11 (1년 안에 1조에서 0으로)", YT + "G-MlrpoMig0")],
    order=6,
    series=["WALCL", "ECBASSETSW", "JPNASSETS", "DEXUSEU", "DEXJPUS"],
    layer="유동성·연준",
    use="타이밍",
    lead="6~12개월",
)
def run(ctx: Context, accel_bn: float = 300.0) -> ToolResult:
    parts, missing = {}, []
    try:
        parts["연준"] = to_freq(ctx.series("WALCL"), "M", how="last") / 1000  # 백만 달러 → 십억 달러
    except DataUnavailable:
        missing.append("연준")
    try:
        eur = float(ctx.series("DEXUSEU").iloc[-1])  # 1유로당 달러
        parts["ECB"] = to_freq(ctx.series("ECBASSETSW"), "M", how="last") / 1000 * eur  # 백만 유로 → 십억 달러
    except DataUnavailable:
        missing.append("ECB")
    try:
        jpy = float(ctx.series("DEXJPUS").iloc[-1])  # 1달러당 엔
        parts["일본은행"] = to_freq(ctx.series("JPNASSETS"), "M", how="last") * 1e8 / jpy / 1e9  # 억 엔 → 십억 달러
    except DataUnavailable:
        missing.append("일본은행")
    if "연준" not in parts or len(parts) < 2:
        raise DataUnavailable("중앙은행 대차대조표가 2개 미만: " + ", ".join(missing))
    df = pd.DataFrame(parts).dropna()
    total = df.sum(axis=1)
    chg = total.diff(12)              # 1년 증감 = 속도 (십억 달러/년)
    acc = chg.diff(12)                # 1년 전 속도 대비 = 가속도
    t = total.index[-1]
    v, a = float(chg.iloc[-1]), float(acc.iloc[-1])
    if v > 0 and a > accel_bn:
        sig, msg = Signal.OK, "세계 중앙은행이 돈을 더 빠르게 풀고 있음 — 자산가격에 순풍"
    elif v < 0 and a < -accel_bn:
        sig, msg = Signal.ALERT, "세계 중앙은행 유동성이 줄고, 줄어드는 속도도 빨라짐 — 2018년 그가 숏을 든 조합"
    elif a < -accel_bn:
        sig, msg = Signal.WATCH, "아직 늘고 있지만 속도가 꺾이는 중 — 변화율이 먼저 말한다"
    elif a > accel_bn:
        sig, msg = Signal.WATCH, "아직 줄고 있지만 속도가 회복되는 중"
    else:
        sig, msg = Signal.WATCH if v < 0 else Signal.OK, "속도 변화 작음 — " + ("완만한 축소" if v < 0 else "완만한 확대")
    metrics = {"기준월": fdate(t), "3개 중앙은행 합산": fmt(float(total.iloc[-1]) / 1000, "조$", 1),
               "1년 증감 (속도)": fmt(v, "십억$", 0, sign=True), "1년 전 속도 대비 (가속도)": fmt(a, "십억$", 0, sign=True)}
    for k in parts:
        metrics[f"{k} 1년 증감"] = fmt(float(df[k].diff(12).iloc[-1]), "십억$", 0, sign=True)
    if missing:
        metrics["빠진 중앙은행"] = ", ".join(missing)
    headline = f"합산 1년 {v:+,.0f}십억$, 가속도 {a:+,.0f}십억$ → {msg}"
    notes = [
        "ECB·일본은행 자산은 최근 환율로 달러 환산했습니다(고정환율). 환율이 움직인 효과가 '유동성 변화'로 잘못 잡히지 않게 하기 위해서입니다.",
        "그는 2018년 7월 이 논리로 숏을 들었다가 2~3개월 틀렸다고 했습니다(#13). 변화율은 방향을 말하지만 정확한 시점은 시장 내부·가격으로 확인해야 합니다.",
        "중국 인민은행·영란은행은 빠져 있습니다. 합산 규모의 대부분은 이 세 곳입니다.",
    ]
    charts = [Chart("3개 중앙은행 자산 1년 증감 (십억 달러, 고정환율)",
                    {k: df[k].diff(12) for k in parts} | {"합산": chg}, y_title="십억$", hlines=[(0, "")], years=20),
              Chart("중앙은행 자산 (십억 달러, 고정환율)", {k: df[k] for k in parts}, y_title="십억$", years=20)]
    return ToolResult(sig, headline, metrics, notes, [], charts, as_of=fdate(t))
