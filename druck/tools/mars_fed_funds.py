"""화성인 금리 게임 — 데이터만 보면 기준금리는 어디여야 하나?

2003년 말 기준금리 1%, 명목성장률 9%. SD는 직원들에게 "화성에서 왔다고 치고
데이터만 보면 금리가 얼마여야 하나"를 물었고 답은 3~6%였다. 그 괴리가 주택 버블의 씨앗이었다.
2016년 Endgame 연설에서는 볼커·그린스펀식 테일러 룰이면 금리가 3% 근처여야 한다며
'경력상 가장 크고 긴 비둘기파 이탈'이라고 했다.

2018년 Real Vision에서도 같은 게임: 성장 견조·대규모 재정·실업률 4% 미만이면 "화성인은 4~5%라고 할 것".

그가 실제로 쓴 '데이터'는 두 가지다: (1) 명목성장률 대비 기준금리(2003년 9% vs 1%), (2) 표준 테일러 룰(2016년).
둘 다 본다. 괴리가 크게 마이너스(너무 완화) → 버블·자본 오배분 축적. 크게 플러스(너무 긴축) → 경기 급랭 위험.
"큰돈의 80%는 중앙은행 실수에 대응한 약세장에서 벌었다" (Lost Tree 2015).
"""
from __future__ import annotations

import pandas as pd

from ..core import Chart, Context, Signal, ToolResult
from ..registry import tool
from ..stats import episodes, fdate, fmt, to_freq, yoy_pct
from . import src


def rule_rates(ctx: Context, r_star: float, target: float, okun: float) -> pd.DataFrame:
    ff = to_freq(ctx.series("FEDFUNDS"), "M")
    core = to_freq(ctx.series("PCEPILFE"), "M")
    u = to_freq(ctx.series("UNRATE"), "M")
    nrou_q = ctx.series("NROU")
    nrou = nrou_q.resample("MS").ffill()
    nrou.index = nrou.index + pd.offsets.MonthEnd(0)
    infl = yoy_pct(core, 12)
    df = pd.DataFrame({"기준금리": ff, "근원PCE(%)": infl, "실업률": u})
    df["자연실업률"] = nrou.reindex(df.index).ffill()
    df = df.dropna()
    gap = -okun * (df["실업률"] - df["자연실업률"])
    pi = df["근원PCE(%)"]
    df["산출갭(추정)"] = gap
    df["테일러(1993)"] = r_star + pi + 0.5 * (pi - target) + 0.5 * gap
    df["균형접근(Yellen)"] = r_star + pi + 0.5 * (pi - target) + 1.0 * gap
    df["화성인 하단"] = df[["테일러(1993)", "균형접근(Yellen)"]].min(axis=1)
    df["화성인 상단"] = df[["테일러(1993)", "균형접근(Yellen)"]].max(axis=1)
    df["괴리(실제-테일러)"] = df["기준금리"] - df["테일러(1993)"]
    return df


@tool(
    name="mars_fed_funds",
    title="화성인 금리 게임 (적정 기준금리 vs 실제)",
    concept="유동성 > 실적 · 중앙은행 실수 찾기",
    rule="데이터만 보고 금리를 정해보라. 실제 금리가 그보다 한참 낮으면 연준이 실수하는 중이고, 큰돈은 그 실수의 대가에서 나온다.",
    sources=[src("Lost Tree Club 2015 (2003년 화성인 게임)", "sources/lost-tree-club-2015"),
             src("The Endgame 2016 (테일러 룰 이탈)", "sources/ira-sohn-endgame-2016"),
             src("Real Vision 2018 (적정 4~5%)", "sources/real-vision-monetary-policy-2018")],
    order=10,
    series=["FEDFUNDS", "PCEPILFE", "UNRATE", "NROU", "GDP"],
    layer="유동성·연준",
    use="타이밍",
    lead="1~3년 (2003년 실수 → 2005년 주택 정점 → 2007년 붕괴)",
)
def run(ctx: Context, r_star: float = 2.0, inflation_target: float = 2.0, okun: float = 2.0,
        alert_gap: float = 2.0) -> ToolResult:
    df = rule_rates(ctx, r_star, inflation_target, okun)
    t = df.index[-1]
    row = df.iloc[-1]
    dev = float(row["괴리(실제-테일러)"])

    ngdp = yoy_pct(to_freq(ctx.series("GDP"), "Q"), 4).dropna()
    ngdp_now = float(ngdp.iloc[-1]) if len(ngdp) else float("nan")
    ff_all = to_freq(ctx.series("FEDFUNDS"), "M")
    ff_latest, ff_latest_t = float(ff_all.iloc[-1]), ff_all.index[-1]  # 물가 발표보다 앞선 최신 기준금리
    ng_gap = ngdp_now - ff_latest  # 2003년: 9 − 1 = +8

    # 두 '화성인 데이터'를 같이 본다: 테일러 괴리, 명목성장 − 기준금리
    if dev <= -alert_gap or ng_gap >= 2 * alert_gap + 1:
        sig = Signal.ALERT
    elif dev >= alert_gap:
        sig = Signal.ALERT
    elif abs(dev) >= alert_gap / 2 or ng_gap >= alert_gap + 1:
        sig = Signal.WATCH
    else:
        sig = Signal.OK
    direction = "너무 완화적(버블 축적 위험)" if dev < 0 or ng_gap >= alert_gap + 1 else "너무 긴축적(경기 급랭 위험)"
    headline = (f"화성인 적정금리 {fmt(row['화성인 하단'])}~{fmt(row['화성인 상단'])}% vs 실제 {fmt(ff_latest, '%', 2)}, "
                f"명목성장 {fmt(ngdp_now, '%')} → 테일러 괴리 {fmt(dev, '%p', sign=True)}, 명목성장−금리 {fmt(ng_gap, '%p', sign=True)}"
                + (f" · {direction}" if sig != Signal.OK else " · 규범 범위 내"))

    metrics = {
        "기준월": fdate(t),
        f"최신 기준금리 ({fdate(ff_latest_t)})": fmt(ff_latest, "%", 2),
        "테일러(1993)": fmt(row["테일러(1993)"], "%"),
        "균형접근 룰": fmt(row["균형접근(Yellen)"], "%"),
        "괴리(실제−테일러)": fmt(dev, "%p", sign=True),
        "근원 PCE 물가": fmt(row["근원PCE(%)"], "%"),
        "실업률 / 자연실업률": f"{fmt(row['실업률'])}% / {fmt(row['자연실업률'])}%",
        "명목GDP 성장률(전년비)": fmt(ngdp_now, "%"),
        "명목성장 − 기준금리": fmt(ng_gap, "%p", sign=True),
    }
    notes = [
        f"룰: 금리 = r*({r_star}) + 물가 + 0.5×(물가−{inflation_target}) + b×산출갭. 산출갭은 오쿤 법칙(−{okun}×(실업률−자연실업률))으로 추정. b=0.5(테일러), 1.0(균형접근).",
        "2003년 사례: 명목성장 9% vs 기준금리 1% → '명목성장 − 기준금리'가 크게 플러스면 돈이 너무 싸다는 그의 직관적 지표. 직원 7명의 답은 3~6%였습니다(Lost Tree 2015).",
        "테일러 괴리는 물가·실업 발표 시점(기준월) 기준, 최신 기준금리는 그 뒤 달까지 반영합니다.",
        "r*(중립 실질금리)를 0.5로 낮추면 적정금리가 1.5%p 내려갑니다. 파라미터 r_star로 조정하세요.",
    ]

    loose = episodes(df["괴리(실제-테일러)"] <= -alert_gap, min_len=6, merge_gap=2)
    tight = episodes(df["괴리(실제-테일러)"] >= alert_gap, min_len=6, merge_gap=2)
    rows = []
    for kind, eps in (("과잉 완화", loose), ("과잉 긴축", tight)):
        for s, e in eps:
            seg = df.loc[s:e, "괴리(실제-테일러)"]
            rows.append({"유형": kind, "시작": fdate(s), "끝": fdate(e), "개월": len(seg),
                         "최대 괴리(%p)": round(float(seg.min() if kind == "과잉 완화" else seg.max()), 1)})
    tables = [("괴리 ±%.0f%%p 이상이 6개월 넘게 지속된 구간" % alert_gap,
               pd.DataFrame(rows).sort_values("시작").reset_index(drop=True) if rows else pd.DataFrame({"결과": ["해당 구간 없음"]}))]

    charts = [
        Chart("실제 기준금리 vs 화성인 적정금리", {
            "실제 기준금리": df["기준금리"], "테일러(1993)": df["테일러(1993)"],
            "균형접근 룰": df["균형접근(Yellen)"], "명목GDP 성장률": ngdp}, y_title="%", hlines=[(0, "")]),
        Chart("괴리 (실제 − 테일러)", {"괴리": df["괴리(실제-테일러)"]}, kind="bar", y_title="%p",
              hlines=[(alert_gap, ""), (-alert_gap, "")]),
    ]
    return ToolResult(sig, headline, metrics, notes, tables, charts, as_of=fdate(t), data={"frame": df})
