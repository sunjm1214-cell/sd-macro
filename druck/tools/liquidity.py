"""유동성 대시보드 — "실적이 아니라 연준이 시장을 움직인다".

- 순유동성 = 연준 총자산 − 재무부 일반계정(TGA) − 역레포(RRP)  [십억 달러]
  (2022년 그는 TGA 축소가 QT를 상쇄해 왔다고 지적)
- 변화율이 핵심: 2018년 그는 중앙은행 매입이 연 1조 달러에서 12개월 안에 0으로 가는 '변화율'을 문제 삼았다
  ("수준이 여전히 낮아도 그 변화가 주식에 문제가 되지 않겠나"). 그래서 연간 증감액과, 그 증감액이 1년 사이 얼마나
  바뀌었는지(유동성 충격)를 같이 본다.
- TGA: 재무부 계좌 인출은 유동성 공급, 재충전은 흡수 (Delivering Alpha 2022, Bloomberg Invest 2023).
- "나에게는 이익도 정치도 아니고 언제나 유동성이었다" (Real Vision 2018).
- M2 vs 명목GDP: 2021년 "2018년 이후 M2가 명목GDP보다 25% 더 늘었다"를 인플레이션 근거로 썼다.
  M2가 GDP보다 빨리 늘면 실물에 필요 없는 돈이 자산시장으로 간다.
"""
from __future__ import annotations

import pandas as pd

from ..core import Chart, Context, DataUnavailable, Signal, ToolResult
from ..registry import tool
from ..stats import fdate, fmt, percentile_rank, to_billions, to_freq, yoy_pct
from . import src


def net_liquidity(ctx: Context) -> pd.DataFrame:
    walcl = to_billions(to_freq(ctx.series("WALCL"), "W", "last"), 500, 10000)
    tga = ctx.try_series("WTREGEN")
    rrp = ctx.try_series("RRPONTSYD")
    df = pd.DataFrame({"연준 총자산": walcl})
    df["TGA"] = to_billions(to_freq(tga, "W", "last"), 10, 2000).reindex(df.index).ffill() if tga is not None else 0.0
    df["역레포"] = to_billions(to_freq(rrp, "W", "last"), 1, 3000).reindex(df.index).fillna(0.0) if rrp is not None else 0.0
    df["순유동성"] = df["연준 총자산"] - df["TGA"].fillna(0.0) - df["역레포"]
    return df.dropna(subset=["순유동성"])


@tool(
    name="liquidity",
    title="유동성 (연준 순유동성 · M2 vs 명목GDP)",
    concept="유동성 > 실적",
    rule="시장 전체를 움직이는 건 실적이 아니라 연준과 유동성의 흐름이다. 수준보다 변화율을 본다.",
    sources=[src("Lost Tree Club 2015", "sources/lost-tree-club-2015"),
             src("Real Vision 2018 (변화율)", "sources/real-vision-monetary-policy-2018"),
             src("Talks at GS 2021 (M2 vs 명목GDP)", "sources/talks-at-gs-2021"),
             src("Delivering Alpha 2022 (TGA)", "sources/delivering-alpha-2022"),
             src("Bloomberg Invest 2023 (TGA 재충전 = 흡수)", "sources/bloomberg-invest-ny-2023")],
    order=5,
    series=["WALCL", "WTREGEN", "RRPONTSYD", "M2SL", "GDP"],
    layer="유동성·연준",
    use="타이밍",
    lead="수개월 (변화율이 먼저 움직인다)",
)
def run(ctx: Context, roc_weeks: int = 26) -> ToolResult:
    score = 0
    parts = []  # 헤드라인에 넣을 근거 (숫자 포함)
    metrics, notes, charts, tables = {}, [], [], []
    as_of = None
    have_any = False

    try:
        nl = net_liquidity(ctx)
        have_any = True
        t = nl.index[-1]
        as_of = fdate(t)
        roc = (nl["순유동성"] / nl["순유동성"].shift(roc_weeks) - 1) * 100
        roc13 = (nl["순유동성"] / nl["순유동성"].shift(13) - 1) * 100
        bs_roc = (nl["연준 총자산"] / nl["연준 총자산"].shift(52) - 1) * 100
        r = float(roc.iloc[-1])
        score += 1 if r > 2 else (-1 if r < -2 else 0)
        # 2018년식 '변화율의 변화': 연준 자산 연간 증감액($)과 그 1년 전 대비 변화
        flow = nl["연준 총자산"] - nl["연준 총자산"].shift(52)
        impulse = flow - flow.shift(52)
        f_now, i_now = float(flow.iloc[-1]), float(impulse.iloc[-1])
        if i_now < -500:
            score -= 1
            parts.append(f"연준 자산 연간 증감이 1년 새 {fmt(i_now, 'B$', 0, sign=True)} 감속(2018년형 충격)")
        elif i_now > 500:
            score += 1
            parts.append(f"연준 자산 연간 증감이 1년 새 {fmt(i_now, 'B$', 0, sign=True)} 가속")
        parts.append(f"순유동성 {roc_weeks}주 {fmt(r, '%', sign=True)}" + (" 증가" if r > 2 else (" 감소" if r < -2 else " 보합")))
        metrics.update({
            "기준주": t.strftime("%Y-%m-%d"),
            "순유동성": fmt(nl["순유동성"].iloc[-1], "B$", 0),
            f"순유동성 {roc_weeks}주 변화": fmt(r, "%", sign=True),
            "순유동성 13주 변화": fmt(float(roc13.iloc[-1]), "%", sign=True),
            "연준 총자산 52주 변화": fmt(float(bs_roc.iloc[-1]), "%", sign=True),
            "연준 자산 연간 증감": fmt(f_now, "B$", 0, sign=True),
            "증감의 1년 변화 (충격)": fmt(i_now, "B$", 0, sign=True),
            "TGA / 역레포": f"{fmt(nl['TGA'].iloc[-1], 'B$', 0)} / {fmt(nl['역레포'].iloc[-1], 'B$', 0)}",
        })
        charts.append(Chart("연준 순유동성 (총자산 − TGA − 역레포)", {
            "순유동성": nl["순유동성"], "연준 총자산": nl["연준 총자산"]}, y_title="십억 달러"))
        charts.append(Chart(f"순유동성 {roc_weeks}주 변화율", {"변화율": roc.dropna()}, kind="bar", y_title="%",
                            hlines=[(0, "")]))
        charts.append(Chart("연준 자산 연간 증감액과 그 1년 변화 (2018년식 변화율)", {
            "연간 증감": flow.dropna(), "증감의 1년 변화": impulse.dropna()}, y_title="십억 달러", hlines=[(0, "")]))
    except DataUnavailable as e:
        notes.append(f"연준 대차대조표 데이터 없음: {e}")

    try:
        m2 = to_freq(ctx.series("M2SL"), "Q")
        gdp = to_freq(ctx.series("GDP"), "Q")
        have_any = True
        m2b = to_billions(m2, 1000, 30000)
        df = pd.DataFrame({"M2 전년비": yoy_pct(m2b, 4), "명목GDP 전년비": yoy_pct(gdp, 4),
                           "M2/명목GDP": m2b / gdp}).dropna()
        df["초과 유동성(%p)"] = df["M2 전년비"] - df["명목GDP 전년비"]
        ex = float(df["초과 유동성(%p)"].iloc[-1])
        score += 1 if ex > 0 else -1
        parts.append(f"M2 증가율이 명목GDP보다 {abs(ex):.1f}%p " + ("빠름" if ex > 0 else "느림"))
        k = df["M2/명목GDP"]
        cum3 = (k.iloc[-1] / k.shift(12).iloc[-1] - 1) * 100 if len(k) > 12 else float("nan")
        metrics.update({
            "M2 전년비": fmt(df["M2 전년비"].iloc[-1], "%"),
            "명목GDP 전년비": fmt(df["명목GDP 전년비"].iloc[-1], "%"),
            "초과 유동성 (M2−GDP)": fmt(ex, "%p", sign=True),
            "M2/GDP 3년 누적 변화": fmt(cum3, "%", sign=True),
            "M2/GDP 역사적 분위": fmt(percentile_rank(k, float(k.iloc[-1])), "%", 0),
        })
        as_of = as_of or fdate(df.index[-1])
        charts.append(Chart("M2 vs 명목GDP 증가율", {"M2 전년비": df["M2 전년비"],
                                                    "명목GDP 전년비": df["명목GDP 전년비"]}, y_title="%",
                            hlines=[(0, "")]))
    except DataUnavailable as e:
        notes.append(f"M2/GDP 데이터 없음: {e}")

    if not have_any:
        raise DataUnavailable("유동성 데이터 전부 없음")

    if score >= 2:
        sig, msg = Signal.OK, "유동성 확장 국면 — 그의 표현으로 '연준과 싸우지 마라' 쪽 바람"
    elif score <= -2:
        sig, msg = Signal.ALERT, "유동성 수축 국면 — 순유동성 감소 + 돈이 실물 성장보다 느리게 늘어남"
    elif score == 0:
        sig, msg = Signal.WATCH, "혼조 — 유동성 방향이 엇갈림"
    else:
        sig, msg = Signal.WATCH, "약한 " + ("확장" if score > 0 else "수축") + " — 한쪽만 뚜렷하고 다른 쪽은 보합"
    notes.insert(0, "순유동성은 시장 참여자들이 쓰는 통상적 근사치이며 SD가 이 공식을 직접 쓴 것은 아닙니다. 그가 실제로 언급한 재료(QE·QT 규모, TGA, M2 vs 명목GDP)를 합친 것입니다.")
    headline = f"{', '.join(parts)} → {msg}" if parts else msg
    return ToolResult(sig, headline, metrics, notes, tables, charts, as_of=as_of)
