"""주식 위험 프리미엄 — 주식 이익수익률 − 10년 실질금리.

#31 Delivering Alpha 2022: "1982년엔 5년물이 15%라 실질금리가 높았고 '침체된' 이익의 8배였다.
  지금은 '부풀려진' 이익의 18~19배." → 밸류에이션은 금리와 같이 봐야 한다.
#35 Robin Hood 2023: QE 없는 세계면 15배가 맞고 지금은 20배 — 20~30% 할증을 낼 이유가 없다.
이익수익률(이익 ÷ 시가총액)이 실질금리보다 얼마나 높은지가 주식을 들고 있는 보상이다. 좁을수록 채권 대비 주식의 보상이 작다.
"""
from __future__ import annotations

from ..core import Chart, Context, Signal, ToolResult
from ..registry import tool
from ..stats import fdate, fmt, percentile_rank, to_billions, to_freq

YT = "https://www.youtube.com/watch?v="


@tool(
    name="equity_risk_premium",
    title="주식 위험 프리미엄 (이익수익률 − 실질금리)",
    concept="비대칭 위험보상",
    rule="비싼 주식도 금리가 낮으면 버틸 수 있다. 이익수익률이 실질금리보다 별로 높지 않으면 주식을 들고 있을 보상이 작다.",
    sources=[("Delivering Alpha 2022 (8배 vs 18~19배)", YT + "IMeuzvzToPQ"),
             ("Robin Hood 2023 (15배 vs 20배)", "https://livewiremarkets.com/wires/druckenmiller-things-are-going-to-break-and-equities-are-not-the-place-to-be")],
    order=15,
    series=["CP", "NCBEILQ027S", "DFII10", "GS10"],
    layer="누적 위험",
    use="사이즈",
    lead="없음 (크기 판단용)",
)
def run(ctx: Context, thin_pct: float = 10.0, rich_pct: float = 60.0) -> ToolResult:
    mv = to_billions(to_freq(ctx.series("NCBEILQ027S"), "Q"), 1000, 100000)
    cp = to_freq(ctx.series("CP"), "Q")
    ey = (cp / mv * 100).dropna()
    real = to_freq(ctx.series("DFII10"), "Q")
    erp = (ey - real).dropna()
    t = erp.index[-1]
    now = float(erp.iloc[-1])
    pct = percentile_rank(erp, now)
    if pct <= thin_pct:
        sig, msg = Signal.ALERT, "주식 보상이 실질금리 대비 역사적으로 얇음 — 걸더라도 작게"
    elif pct >= rich_pct:
        sig, msg = Signal.OK, "주식 보상이 실질금리 대비 넉넉함"
    else:
        sig, msg = Signal.WATCH, "보통 구간"
    nom = to_freq(ctx.series("GS10"), "Q")
    metrics = {"기준 분기": fdate(t), "이익수익률": fmt(float(ey.iloc[-1]), "%", 1), "10년 실질금리": fmt(float(real.iloc[-1]), "%", 2),
               "위험 프리미엄": fmt(now, "%p", 1), f"분위 ({fdate(erp.index[0])}~, 낮을수록 얇음)": fmt(pct, "%", 0),
               "이익수익률 − 10년 명목금리": fmt(float(ey.iloc[-1] - nom.reindex(ey.index).iloc[-1]), "%p", 1),
               "주가이익배수 환산": fmt(100 / float(ey.iloc[-1]), "배", 1)}
    headline = f"이익수익률 {float(ey.iloc[-1]):.1f}% − 실질금리 {float(real.iloc[-1]):.2f}% = {now:.1f}%p (분위 {pct:.0f}%) → {msg}"
    notes = ["이익은 FRED 기업이익(세후, 연율), 시가총액은 비금융기업 주식 시장가치입니다. 정확한 S&P 500 이익수익률과 수준은 다르지만 시간에 따른 변화를 보기엔 충분합니다.",
             "실질금리(TIPS)는 2003년부터라 분위도 그 이후 기준입니다.",
             "밸류에이션 도구처럼 '언제'가 아니라 '얼마나'를 정하는 재료입니다. 유동성이 넘치면 얇은 보상에서도 더 오를 수 있습니다."]
    charts = [Chart("주식 위험 프리미엄 (이익수익률 − 10년 실질금리)", {"위험 프리미엄": erp}, y_title="%p", hlines=[(0, "")], years=None),
              Chart("이익수익률 vs 실질금리", {"이익수익률": ey[ey.index >= erp.index[0]], "10년 실질금리": real}, y_title="%", years=None)]
    return ToolResult(sig, headline, metrics, notes, [], charts, as_of=fdate(t))
