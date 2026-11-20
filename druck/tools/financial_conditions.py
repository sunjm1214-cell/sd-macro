"""금융여건 — 이론이 아니라 시장이 말하는 긴축 여부.

Bloomberg 2024: "실질금리 때문에 통화정책이 긴축적이라는 이론이 있지만, 나는 이론으로 가지 않는다. 시장 동물이다.
주식 사상 최고, 금 사상 최고, GDP 추세 이상, 신용 타이트, 크립토 광풍 — 긴축의 흔적이 전혀 없다."
Norges 2023 페이지 녹취: "스프레드 타이트, 금 신고가, 주식 급등, 경기 약세 신호 없는데 50bp 인하 — 인플레이션이 다시 오를까 불안하다."

느슨한 여건 속에서 연준이 인하하면 = '완화 속 완화' → 인플레이션 재점화 위험(그가 보는 연준 실수의 전형).
"""
from __future__ import annotations

import pandas as pd

from ..core import Chart, Context, DataUnavailable, Signal, ToolResult
from ..registry import tool
from ..stats import diff, fdate, fmt, percentile_rank, to_freq, yoy_pct
from . import src


def _near_high(p: pd.Series, days: int = 252) -> float:
    """52주 고점 대비 % (0이면 신고가)."""
    return float((p.iloc[-1] / p.iloc[-days:].max() - 1) * 100)


@tool(
    name="financial_conditions",
    title="금융여건 (시장이 말하는 긴축 여부)",
    concept="유동성 > 실적 · 중앙은행 실수 찾기",
    rule="이론상 금리가 아니라 시장을 본다. 주식·금이 신고가이고 신용이 타이트하며 성장이 추세 이상인데 연준이 내리면, 인플레이션이 다시 온다.",
    sources=[src("Bloomberg 2024 (시장이 교수보다 낫다)", "sources/bloomberg-sonali-2024"),
             src("Norges Bank 페이지 (타이트 스프레드 속 50bp 인하)", "sources/norges-bank-in-good-company-2023"),
             src("WSJ 2021 (비상 조치를 비상 이후에도)", "sources/wsj-fed-playing-with-fire-2021")],
    order=30,
    series=["BAA10Y", "GDPC1", "GDPPOT", "NFCI", "FEDFUNDS"],
    layer="유동성·연준",
    use="타이밍",
    lead="6~18개월 (완화가 물가에 번지는 시간)",
    tickers=["SPY", "GLD"],
)
def run(ctx: Context, near_high_pct: float = -5.0, tight_spread_pct: float = 25.0, cut_pp: float = -0.25,
        loose_min: int = 3) -> ToolResult:
    flags: dict[str, bool] = {}
    metrics: dict[str, str] = {}
    charts = []
    as_of = None

    for tk, label in (("SPY", "주식(S&P 500)"), ("GLD", "금")):
        try:
            p = ctx.price(tk)
            nh = _near_high(p)
            flags[f"{label} 52주 고점 근처"] = nh >= near_high_pct
            metrics[f"{label} 52주 고점 대비"] = fmt(nh, "%", sign=True)
            as_of = as_of or p.index[-1].strftime("%Y-%m-%d")
        except DataUnavailable:
            metrics[f"{label}"] = "데이터 없음"

    baa = ctx.try_series("BAA10Y")
    if baa is not None:
        m = to_freq(baa, "M")
        pct = percentile_rank(m, float(m.iloc[-1]))
        flags["신용 스프레드 타이트"] = pct <= tight_spread_pct
        metrics["Baa−10년 스프레드 분위"] = fmt(pct, "%", 0)

    real, pot = ctx.try_series("GDPC1"), ctx.try_series("GDPPOT")
    if real is not None and pot is not None:
        g = yoy_pct(to_freq(real, "Q"), 4).dropna()
        gp = yoy_pct(to_freq(pot, "Q"), 4).reindex(g.index)
        gap = float(g.iloc[-1] - gp.iloc[-1])
        flags["실질성장 > 잠재성장"] = gap > 0
        metrics["실질성장 − 잠재성장"] = fmt(gap, "%p", sign=True)
        charts.append(Chart("실질GDP 성장률 vs 잠재성장률", {"실질GDP 전년비": g, "잠재성장(CBO)": gp.dropna()},
                            y_title="%", hlines=[(0, "")]))

    nfci = ctx.try_series("NFCI")
    if nfci is not None:
        n = to_freq(nfci, "W", "last")
        flags["NFCI 평균보다 느슨(<0)"] = float(n.iloc[-1]) < 0
        metrics["시카고연준 NFCI"] = fmt(float(n.iloc[-1]), "", 2, sign=True)
        charts.append(Chart("시카고연준 금융여건지수 (0 아래 = 평균보다 느슨)", {"NFCI": n}, y_title="z",
                            hlines=[(0, "")]))

    if not flags:
        raise DataUnavailable("금융여건 데이터 전부 없음")

    ff = to_freq(ctx.series("FEDFUNDS"), "M")
    ff6 = float(diff(ff, 6).dropna().iloc[-1])
    cutting, hiking = ff6 <= cut_pp, ff6 >= -cut_pp
    loose_n, total = sum(flags.values()), len(flags)
    loose = loose_n >= min(loose_min, total)
    tight = loose_n <= max(0, total - loose_min - 1)
    metrics = {"기준 시점": as_of or fdate(ff.index[-1]), "느슨함 점수": f"{loose_n}/{total}",
               "기준금리 6개월 변화": fmt(ff6, "%p", 2, sign=True), **metrics}

    if loose and cutting:
        sig, msg = Signal.ALERT, "느슨한 여건 속 인하 — 인플레이션 재점화 위험(그가 2024년에 불안해한 조합)"
    elif loose:
        sig, msg = Signal.WATCH, "시장이 말하는 긴축의 흔적 없음 — 연준이 '긴축적'이라고 해도 여건은 느슨"
    elif tight and hiking:
        sig, msg = Signal.WATCH, "여건이 실제로 조여지는데 연준은 계속 인상 — 과잉 긴축 위험"
    else:
        sig, msg = Signal.OK, "여건과 정책 방향이 크게 어긋나지 않음"
    lit = " · ".join(("●" if v else "○") + " " + k for k, v in flags.items())
    headline = f"느슨함 {loose_n}/{total}, 기준금리 6개월 {fmt(ff6, '%p', 2, sign=True)} → {msg}"
    notes = [f"점검 항목: {lit}",
             "그는 '실질금리가 플러스라 긴축적'이라는 설명을 받아들이지 않았습니다. 긴축이 실제로 작동하면 주식·금·신용·성장 중 어딘가에서 먼저 드러난다는 것이 그의 관점입니다.",
             "주식·금 가격은 Yahoo(yfinance)에서 받습니다. 없으면 나머지 항목만으로 판정합니다."]
    charts.insert(0, Chart("기준금리", {"기준금리": ff}, y_title="%"))
    return ToolResult(sig, headline, metrics, notes, [], charts, as_of=metrics["기준 시점"],
                      data={"flags": flags})
