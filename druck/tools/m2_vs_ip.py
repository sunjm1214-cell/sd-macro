"""SD 유동성 규칙 — 통화량(M2) 증가율 vs 산업생산 증가율.

2009년 말 은행 FX 트레이더 대상 강연(1:12:23)에서 그가 한 말:
  "경제가 엉망이니 주식이 싫다? 그건 안 통한다. 통화 공급이 산업생산보다 훨씬 빨리 늘면
   주식시장은 대체로 오른다. 그게 돈이 가는 곳이다."
같은 강연에서 그는 QE1이 끝나는 2010년 1분기 말 무렵 위험자산이 되돌림을 시작할 것으로 봤다.
뿌리가 되는 생각(1990년대 초 인터뷰로 널리 인용): 주식에 최고의 환경은 연준이 살리려 애쓰는 굼뜬 경제이고,
경제가 강해지면 기업이 재고·설비에 돈을 써서 주식으로 갈 돈이 줄어든다.

60년 검증 (2026-11-23, M2SL·INDPRO 월간 vs Shiller S&P 500 월평균, 1961~2026년 783개월, 다음 12개월 가격 수익률):
- 차이가 1년 새 +5.1%p 이상 벌어진 달(상위 20%): 평균 +16.5%, 91% 상승. 나머지 구간은 +6~8%.
- 국면별: 플러스·유지/확대 +9.9% / 플러스·축소 +4.8%(가장 약함) / 마이너스·개선 +13.0% / 마이너스·악화 +12.8%.
  마이너스는 대개 침체 직후 산업생산이 급반등하는 회복 초기라 주식에 나쁘지 않았다.
- 플러스→마이너스 역전 8번 중 큰 폭락은 1961-11(이후 1962 폭락)과 1987-08(블랙먼데이) 두 번 — 모두 연준 긴축 중.
→ 판정: 차이의 '확대 속도'를 가장 강한 신호로, 축소·역전은 연준 긴축과 겹칠 때만 경고로 쓴다.
"""
from __future__ import annotations

import pandas as pd

from ..core import Chart, Context, Signal, ToolResult
from ..registry import tool
from ..stats import fdate, fmt, percentile_rank, to_freq, yoy_pct

YT = "https://www.youtube.com/watch?v="


@tool(
    name="m2_vs_ip",
    title="SD 유동성 규칙 (M2 vs 산업생산)",
    concept="유동성 > 실적",
    rule="통화 공급이 산업생산보다 훨씬 빨리 늘면 주식시장은 대체로 오른다 — 경기가 나빠도 돈은 자산으로 간다.",
    sources=[("Druckenmiller Interview 2009 (은행 FX 트레이더 강연, 1:12:23)", YT + "AJqLuMo9GPY&t=4343")],
    order=7,
    series=["M2SL", "INDPRO", "FEDFUNDS"],
    layer="유동성·연준",
    use="타이밍",
    lead="12개월 (차이가 1년 새 크게 벌어진 뒤 12개월이 가장 강했다)",
)
def run(ctx: Context, turn_months: int = 6, flat_band: float = 0.3, surge: float = 5.0,
        hike: float = 0.25) -> ToolResult:
    m2 = to_freq(ctx.series("M2SL"), "M")
    ip = to_freq(ctx.series("INDPRO"), "M")
    df = pd.DataFrame({"M2 전년비": yoy_pct(m2, 12), "산업생산 전년비": yoy_pct(ip, 12)}).dropna()
    df["차이(%p)"] = df["M2 전년비"] - df["산업생산 전년비"]
    gap = df["차이(%p)"]
    d12 = gap - gap.shift(12)

    t = df.index[-1]
    g_now = float(gap.iloc[-1])
    chg = float(gap.iloc[-1] - gap.iloc[-1 - turn_months]) if len(gap) > turn_months else float("nan")
    y_chg = float(d12.iloc[-1]) if pd.notna(d12.iloc[-1]) else float("nan")
    shrinking = chg < -flat_band  # ±flat_band 안의 변화는 '유지'로 본다

    # 연준 긴축 여부: 기준금리 6개월 변화
    ff_chg = float("nan")
    try:
        ff = to_freq(ctx.series("FEDFUNDS"), "M").dropna()
        if len(ff) > 6:
            ff_chg = float(ff.iloc[-1] - ff.iloc[-7])
    except Exception:  # 기준금리가 없어도 나머지 판정은 한다
        pass
    hiking = ff_chg > hike

    # 플러스(또는 마이너스)가 몇 달째 이어지는지
    sign = gap > 0
    run_len = 0
    for v in reversed(sign.to_list()):
        if v == sign.iloc[-1]:
            run_len += 1
        else:
            break

    if y_chg >= surge:
        sig, msg = Signal.OK, (f"차이가 1년 새 {fmt(y_chg, '%p', sign=True)} 벌어지는 중 — 60년 데이터에서 가장 강했던 국면"
                               "(다음 12개월 평균 +16.5%, 91% 상승)")
    elif g_now > 0 and not shrinking:
        sig, msg = Signal.OK, "돈이 실물보다 빨리 늘고 그 폭도 유지·확대 중 — 그의 규칙상 주식에 우호적인 바람"
    elif (shrinking or g_now <= 0) and hiking:
        sig, msg = Signal.ALERT, (f"남는 돈이 줄어드는데 연준까지 긴축 중(기준금리 6개월 {fmt(ff_chg, '%p', sign=True)}) — "
                                  "1962·1987·2022년형 조합")
    elif g_now > 0:
        sig, msg = Signal.WATCH, "아직 돈이 실물보다 빨리 늘지만 폭이 줄어드는 중 — 60년 데이터에서 가장 약했던 국면(평균 +4.8%)"
    else:
        sig, msg = Signal.WATCH, ("실물이 돈을 더 빨아들이는 중(대개 회복 초기 생산 반등) — 연준이 긴축하지 않으면 "
                                  "역사적으로 주식엔 나쁘지 않았다(평균 +13%)")

    headline = (f"M2 {fmt(df['M2 전년비'].iloc[-1], '%', sign=True)} vs 산업생산 "
                f"{fmt(df['산업생산 전년비'].iloc[-1], '%', sign=True)} → 차이 {fmt(g_now, '%p', sign=True)}"
                f" (6개월 {fmt(chg, '%p', sign=True)}, 1년 {fmt(y_chg, '%p', sign=True)}) → {msg}")

    metrics = {
        "기준월": fdate(t),
        "M2 전년비": fmt(df["M2 전년비"].iloc[-1], "%", sign=True),
        "산업생산 전년비": fmt(df["산업생산 전년비"].iloc[-1], "%", sign=True),
        "차이 (M2 − 산업생산)": fmt(g_now, "%p", sign=True),
        f"차이 {turn_months}개월 변화": fmt(chg, "%p", sign=True),
        "차이 1년 변화 (핵심 신호)": fmt(y_chg, "%p", sign=True) + (" ★" if y_chg >= surge else ""),
        "기준금리 6개월 변화": fmt(ff_chg, "%p", 2, sign=True) + (" (긴축)" if hiking else ""),
        "차이 역사적 분위": fmt(percentile_rank(gap, g_now), "%", 0),
        ("플러스" if g_now > 0 else "마이너스") + " 지속": f"{run_len}개월",
    }

    recent = df.iloc[-12:].iloc[::-1].copy()
    recent.index = [d.strftime("%Y-%m") for d in recent.index]
    recent = recent.round(1)

    backtest = pd.DataFrame(
        {"다음 12개월 평균": ["+9.9%", "+4.8%", "+13.0%", "+12.8%", "+16.5%"],
         "상승 비율": ["75%", "68%", "87%", "84%", "91%"],
         "개월 수": [367, 259, 53, 104, 157]},
        index=["플러스 · 유지/확대", "플러스 · 축소 (가장 약함)", "마이너스 · 개선", "마이너스 · 악화",
               "차이 1년 새 +5.1%p 이상 확대 (가장 강함)"])

    notes = [
        "산업생산은 미국 연준이 매달 내는 공장·광산·발전소의 실질 생산량 지수입니다. GDP보다 빨리(다음 달 중순) 나오고 "
        "경기 전환점에 민감해서, 실물경제가 돈을 얼마나 쓰는지의 대리 지표로 씁니다.",
        "읽는 법: 차이가 플러스면 실물이 쓰고 남는 돈이 주식·자산으로 갑니다. 가장 강한 신호는 수준이 아니라 "
        "차이가 1년 새 얼마나 벌어졌는지입니다(위기 직후 돈 풀기: 1975, 1983, 2001~02, 2009, 2020).",
        "60년 검증(1961~2026, 783개월, Shiller S&P 500 월평균 가격): 아래 표. 겹치는 12개월 구간이라 표본이 독립적이지 않고, "
        "월평균 가격이라 장중 낙폭은 작게 잡힙니다. 통계 검정이 아니라 경향을 보는 기술 통계입니다.",
        "마이너스(산업생산이 M2를 앞지름)는 대개 침체 직후 생산이 급반등하는 회복 초기라 주식에 나쁘지 않았습니다. "
        "플러스→마이너스 역전 8번 중 큰 폭락은 1961-11(1962 폭락)과 1987-08(블랙먼데이)뿐이고, 둘 다 연준 긴축 중이었습니다. "
        "그래서 경고는 '축소·역전 + 연준 긴축'이 겹칠 때만 냅니다. 그도 2009년에 'QE 종료'라는 연준 행동을 방아쇠로 붙였습니다.",
        "그의 말: 첫 멘토에게서 '이익이 아니라 연준이 시장 전체를 움직인다'를 배웠고(2015 회고), 주식에 최고의 환경은 "
        "'연준이 살리려 애쓰는 굼뜬 경제'이며 경제가 강해지면 기업이 재고·설비에 돈을 써서 주식으로 갈 돈이 줄어든다고 했습니다"
        "(1990년대 초 인터뷰로 널리 인용). 2021년엔 'M2가 2018년 이후 명목GDP보다 25% 더 늘었다'를 인플레이션 근거로 썼습니다.",
        "한계: 명목 M2와 실질 산업생산을 비교해 물가를 따로 보지 않습니다. 남는 돈은 자산과 물가 양쪽으로 갑니다(2021년). "
        "산업생산은 서비스업을 빼므로 서비스 중심 경기에서는 체감과 다를 수 있습니다.",
        f"판정 규칙: 차이 1년 변화 ≥ +{surge:.0f}%p=양호(강) / 플러스·유지 또는 확대=양호 / 축소·역전 + 기준금리 6개월 "
        f"+{hike:.2f}%p 초과=경고 / 플러스·축소=주시 / 마이너스·연준 긴축 아님=주시. 6개월 변화가 ±{flat_band}%p 안이면 '유지'.",
    ]

    charts = [
        Chart("M2 vs 산업생산 증가율 (전년비)", {"M2 전년비": df["M2 전년비"], "산업생산 전년비": df["산업생산 전년비"]},
              y_title="%", hlines=[(0, "")]),
        Chart("차이: M2 − 산업생산 (플러스면 남는 돈이 자산으로)", {"차이": gap}, kind="bar", y_title="%p",
              hlines=[(0, "")]),
        Chart(f"차이의 1년 변화 (+{surge:.0f}%p 위 = 60년 데이터상 가장 강한 매수 환경)", {"1년 변화": d12.dropna()},
              kind="bar", y_title="%p", hlines=[(0, ""), (surge, f"+{surge:.0f}%p")]),
    ]
    return ToolResult(sig, headline, metrics, notes, [("최근 12개월", recent), ("60년 검증 (1961~2026)", backtest)],
                      charts, as_of=fdate(t), data={"gap": gap, "gap_12m_change": d12})
