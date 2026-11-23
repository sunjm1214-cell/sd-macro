"""SD 유동성 규칙 — 통화량(M2) 증가율 vs 산업생산 증가율.

2009년 말 은행 FX 트레이더 대상 강연(1:12:23)에서 그가 한 말:
  "경제가 엉망이니 주식이 싫다? 그건 안 통한다. 통화 공급이 산업생산보다 훨씬 빨리 늘면
   주식시장은 대체로 오른다. 그게 돈이 가는 곳이다."
같은 강연에서 그는 QE1이 끝나는 2010년 1분기 말 무렵 위험자산이 되돌림을 시작할 것으로 봤다.
실제로 2010년 3월 M2 증가율이 산업생산 증가율 밑으로 내려갔고, S&P 500은 4~7월 약 16% 조정을 받았다.

- 산업생산(INDPRO): 공장·광산·발전소의 실질 생산량. 매달 나오고 경기 전환점에 민감하다.
- 차이(M2 − 산업생산)가 플러스면 실물이 쓰고 남는 돈이 자산시장으로 간다.
- `liquidity` 툴의 'M2 vs 명목GDP'(분기)와 같은 생각을 월간·실물 생산 기준으로 본 것이다.
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
    series=["M2SL", "INDPRO"],
    layer="유동성·연준",
    use="타이밍",
    lead="수개월 (2009년 3월 차이 최대 → 2010년 3월 역전 → 4~7월 조정)",
)
def run(ctx: Context, turn_months: int = 6, flat_band: float = 0.3) -> ToolResult:
    m2 = to_freq(ctx.series("M2SL"), "M")
    ip = to_freq(ctx.series("INDPRO"), "M")
    df = pd.DataFrame({"M2 전년비": yoy_pct(m2, 12), "산업생산 전년비": yoy_pct(ip, 12)}).dropna()
    df["차이(%p)"] = df["M2 전년비"] - df["산업생산 전년비"]
    gap = df["차이(%p)"]

    t = df.index[-1]
    g_now = float(gap.iloc[-1])
    chg = float(gap.iloc[-1] - gap.iloc[-1 - turn_months]) if len(gap) > turn_months else float("nan")
    rising = not (chg < -flat_band)  # ±flat_band 안의 변화는 '유지'로 본다

    # 플러스(또는 마이너스)가 몇 달째 이어지는지
    sign = gap > 0
    run_len = 0
    for v in reversed(sign.to_list()):
        if v == sign.iloc[-1]:
            run_len += 1
        else:
            break

    if g_now > 0 and rising:
        sig, msg = Signal.OK, "돈이 실물보다 빨리 늘고 그 폭도 유지·확대 중 — 그의 규칙상 주식에 우호적인 바람"
    elif g_now > 0:
        sig, msg = Signal.WATCH, "아직 돈이 실물보다 빨리 늘지만 폭이 줄어드는 중 — 연료가 줄어드는 방향"
    elif rising:
        sig, msg = Signal.WATCH, "실물이 돈을 더 빨아들이지만 차이는 더 벌어지지 않는 중 — 방향(2차 미분)은 개선·정체"
    else:
        sig, msg = Signal.ALERT, "실물이 돈을 빨아들이고 차이도 더 벌어지는 중 — 2010년 3월(QE1 종료)형 역전"

    headline = (f"M2 {fmt(df['M2 전년비'].iloc[-1], '%', sign=True)} vs 산업생산 "
                f"{fmt(df['산업생산 전년비'].iloc[-1], '%', sign=True)} → 차이 {fmt(g_now, '%p', sign=True)}"
                f" ({turn_months}개월 전 대비 {fmt(chg, '%p', sign=True)}) → {msg}")

    metrics = {
        "기준월": fdate(t),
        "M2 전년비": fmt(df["M2 전년비"].iloc[-1], "%", sign=True),
        "산업생산 전년비": fmt(df["산업생산 전년비"].iloc[-1], "%", sign=True),
        "차이 (M2 − 산업생산)": fmt(g_now, "%p", sign=True),
        f"차이 {turn_months}개월 변화": fmt(chg, "%p", sign=True),
        "차이 역사적 분위": fmt(percentile_rank(gap, g_now), "%", 0),
        ("플러스" if g_now > 0 else "마이너스") + " 지속": f"{run_len}개월",
    }

    recent = df.iloc[-12:].iloc[::-1].copy()
    recent.index = [d.strftime("%Y-%m") for d in recent.index]
    recent = recent.round(1)

    notes = [
        "산업생산은 미국 연준이 매달 내는 공장·광산·발전소의 실질 생산량 지수입니다. GDP보다 빨리(다음 달 중순) 나오고 "
        "경기 전환점에 민감해서, 실물경제가 돈을 얼마나 쓰는지의 대리 지표로 씁니다.",
        "읽는 법: 차이가 플러스면 실물이 쓰고 남는 돈이 주식·자산으로 갑니다. 마이너스로 역전되면 자산시장 연료가 줄어듭니다. "
        "수준보다 방향(최근 몇 달 사이 차이가 커지는지 줄어드는지)을 같이 봅니다.",
        "역사적 사례: 2009년 3월 M2 +9.3% vs 산업생산 −14.7%(차이 +24%p) → 그달 S&P 바닥 후 급등. "
        "2010년 3월 M2 +1.7% vs 산업생산 +4.2%로 첫 역전, QE1 매입 종료와 겹침 → S&P 4~7월 약 −16%.",
        "한계: 명목 M2와 실질 산업생산을 비교해 물가를 따로 보지 않습니다. 돈이 물가로 가면(2021~22년) 자산에는 오히려 부담이 될 수 있습니다. "
        "산업생산은 서비스업을 빼므로 서비스 중심 경기에서는 체감과 다를 수 있습니다. 그도 '신호가 3개월 뒤일 수도 3년 뒤일 수도 있다'고 했습니다 — 방향을 보는 도구이지 타이밍 신호 단독으로 쓰지 않습니다.",
        "판정 규칙(이 툴의 해석): 차이 플러스·유지/확대=양호, 플러스·축소 또는 마이너스·유지/개선=주시, 마이너스·악화=경고. "
        "최근 6개월 변화가 ±0.3%p 안이면 '유지'로 봅니다. "
        "그의 말은 플러스 쪽(돈이 더 빨리 늘면 주식 상승)이고, 역전 쪽은 같은 강연의 'QE 종료 후 되돌림' 전망에서 가져왔습니다.",
    ]

    charts = [
        Chart("M2 vs 산업생산 증가율 (전년비)", {"M2 전년비": df["M2 전년비"], "산업생산 전년비": df["산업생산 전년비"]},
              y_title="%", hlines=[(0, "")]),
        Chart("차이: M2 − 산업생산 (플러스면 남는 돈이 자산으로)", {"차이": gap}, kind="bar", y_title="%p",
              hlines=[(0, "")]),
    ]
    return ToolResult(sig, headline, metrics, notes, [("최근 12개월", recent)], charts, as_of=fdate(t),
                      data={"gap": gap})
