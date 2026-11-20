"""시가총액/GDP — "1982년은 50%, 지금은 150%" (Delivering Alpha 2022).

SD는 밸류에이션을 '얼마나(사이즈)'를 정하는 재료로, 유동성·기술적 흐름을 '언제'를 정하는
재료로 쓴다 — "밸류에이션으로 타이밍을 잡지 않는다"(New Market Wizards 1992).
Delivering Alpha 2022 원문: "1982년엔 GDP의 50%, 지금은 150%(225%에서 내려옴). 그때는 5년물이 15%라 실질금리가 높았고,
그래서 '침체된' 이익의 8배였다. 지금은 '부풀려진' 이익의 18~19배." → 시총/GDP와 함께 이익률(이익/GDP)과 실질금리를 본다.
"""
from __future__ import annotations

import pandas as pd

from ..core import Chart, Context, Signal, ToolResult
from ..registry import tool
from ..stats import fdate, fmt, percentile_rank, to_billions, to_freq, yoy_pct
from . import src


@tool(
    name="valuation",
    title="밸류에이션 (비금융기업 시가총액 / GDP)",
    concept="비대칭 위험보상",
    rule="빌린 미래가 많을수록 할인이 아니라 할증으로 거래되면 위험보상이 나쁘다. 단, 밸류는 타이밍 도구가 아니다.",
    sources=[src("Delivering Alpha 2022 (50%→150%, 8배 vs 18~19배)", "sources/delivering-alpha-2022"),
             src("The Endgame 2016 (1981년의 거울상)", "sources/ira-sohn-endgame-2016"),
             src("New Market Wizards 1992 (밸류는 타이밍 도구가 아니다)", "sources/new-market-wizards-1992")],
    order=10,
    series=["NCBEILQ027S", "GDP", "CP", "GS5", "PCEPILFE"],
    layer="누적 위험",
    use="사이즈",
    lead="없음 (크기 판단용)",
)
def run(ctx: Context, alert_pct: float = 90.0, cheap_pct: float = 30.0) -> ToolResult:
    mv = to_billions(to_freq(ctx.series("NCBEILQ027S"), "Q"), 1000, 100000)
    gdp = to_freq(ctx.series("GDP"), "Q")
    ratio = (mv / gdp * 100).dropna()
    t = ratio.index[-1]
    now = float(ratio.iloc[-1])
    pct = percentile_rank(ratio, now)
    refs = {}
    for label, a, b in (("1982 저점", "1980", "1983"), ("2000 정점", "1999", "2001"),
                        ("2009 저점", "2008", "2010"), ("2021 정점", "2020", "2022")):
        seg = ratio[a:b]
        if len(seg):
            refs[label] = (seg.max() if "정점" in label else seg.min())
    sig = Signal.ALERT if pct >= alert_pct else (Signal.OK if pct <= cheap_pct else Signal.WATCH)
    metrics = {"기준 분기": fdate(t), "시가총액/GDP": fmt(now, "%", 0), "역사적 분위": fmt(pct, "%", 0)}
    extra = []
    cp = ctx.try_series("CP")
    if cp is not None:
        share = (to_freq(cp, "Q") / gdp * 100).dropna()
        sp = percentile_rank(share, float(share.iloc[-1]))
        metrics["이익/GDP (이익률)"] = fmt(float(share.iloc[-1]), "%")
        metrics["이익률 분위"] = fmt(sp, "%", 0)
        if sp >= 80:
            extra.append("이익도 부풀려진 상태")
    g5, pce = ctx.try_series("GS5"), ctx.try_series("PCEPILFE")
    if g5 is not None and pce is not None:
        real = (to_freq(g5, "M") - yoy_pct(to_freq(pce, "M"), 12)).dropna()
        metrics["5년물 실질금리 (근원PCE 차감)"] = fmt(float(real.iloc[-1]), "%", 1, sign=True)
        metrics["1981년 실질금리 (참고)"] = "약 +5%"
    headline = (f"시가총액/GDP {now:.0f}% — 역사적 {pct:.0f}% 분위"
                + (" (최상단: 위험보상 불리" + (", " + ", ".join(extra) if extra else "") + ")" if sig == Signal.ALERT else ""))
    for k, v in refs.items():
        metrics[k] = fmt(float(v), "%", 0)
    notes = ["이 툴은 '언제'가 아니라 '얼마나'를 말합니다. 빨강이어도 유동성이 넘치면 더 오를 수 있고(2015년 그는 순매도하지 않았다), 유동성이 꺾일 때 하락 폭을 키우는 재료입니다.",
             "FRED의 비금융기업 주식 시장가치(Z.1)를 명목GDP로 나눈 값입니다. 금융주가 빠져 있어 흔히 보는 '버핏 지표'보다 수준이 다를 수 있습니다.",
             "2015년 그는 시총/GDP가 1999~2000년을 빼면 100년 최고라면서도 '이 통화정책이면 그럴 만하다'며 순매도하지 않았습니다. 밸류는 유동성 툴과 같이 보세요."]
    charts = [Chart("비금융기업 시가총액 / 명목GDP", {"시총/GDP": ratio}, y_title="%")]
    return ToolResult(sig, headline, metrics, notes, [], charts, as_of=fdate(t))
