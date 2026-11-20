"""주요국 정책 격차 — 미국 vs 유로존·일본 기준금리가 '동시에 반대로' 움직이는가.

#6 Bloomberg 2015-05 · #7/#8 DealBook 2015: 2014년 5월 미·유럽 통화정책이 동시에 뒤집혔다
  (연준 테이퍼 vs ECB QE·마이너스 금리) → 교과서적 통화 기회, 유로 숏.
  "주요 통화 추세가 2년 미만에 끝난 걸 본 적 없다. 중간에 쉬어 갈 수는 있다."
#32 Norges 2023: 달러 숏 — 앞으로 미국의 긴축이 외국보다 덜할 것.
그래서 금리 '수준 차이'보다 격차가 벌어지거나 좁혀지는 속도(6개월 변화)를 본다.
"""
from __future__ import annotations

import pandas as pd

from ..core import Chart, Context, DataUnavailable, Signal, ToolResult
from ..registry import tool
from ..stats import fdate, fmt, to_freq

YT = "https://www.youtube.com/watch?v="
OTHERS = {"유로존": "ECBDFR", "일본": "IRSTCI01JPM156N"}


@tool(
    name="policy_divergence",
    title="주요국 정책 격차 (미국 vs 유로존·일본 기준금리)",
    concept="통화 = 견해의 표현",
    rule="두 중앙은행 정책이 동시에 반대로 꺾이면 통화 추세가 생긴다. 주요 통화 추세는 보통 2~3년 간다.",
    sources=[("Bloomberg 2015-05 (정책 동시 반전 = 교과서적 기회)", YT + "7TYzjM-ATyU"),
             ("DealBook 2015 (통화 추세 2~3년, 중간 휴지기)", YT + "aviToCACiNA"),
             ("Norges 2023 (달러 숏)", YT + "dXxWajc-tgI")],
    order=10,
    series=["FEDFUNDS", "ECBDFR", "IRSTCI01JPM156N"],
    layer="통화",
    use="타이밍",
    lead="통화 추세 2~3년",
)
def run(ctx: Context, months: int = 6, move: float = 0.25) -> ToolResult:
    us = to_freq(ctx.series("FEDFUNDS"), "M")
    rows, gaps, flags = [], {"미국": us}, []
    us_chg = float(us.iloc[-1] - us.iloc[-1 - months])
    for name, sid in OTHERS.items():
        try:
            o = to_freq(ctx.series(sid), "M")
        except DataUnavailable:
            continue
        gaps[name] = o
        g = (us - o).dropna()
        o_chg = float(o.iloc[-1] - o.iloc[-1 - months])
        g_chg = float(g.iloc[-1] - g.iloc[-1 - months])
        opposite = (us_chg >= move and o_chg <= -move) or (us_chg <= -move and o_chg >= move)
        if opposite:
            side = "달러 강세" if us_chg > 0 else "달러 약세"
            flags.append(f"미국과 {name}이 동시에 반대로 — 미국 {us_chg:+.2f}%p vs {name} {o_chg:+.2f}%p → {side} 쪽 추세 조건")
        elif abs(g_chg) >= 2 * move:
            flags.append(f"미국−{name} 금리차가 {months}개월 {g_chg:+.2f}%p 변화 — " + ("달러 쪽으로 벌어짐" if g_chg > 0 else "달러에 불리하게 좁혀짐"))
        rows.append({"상대": name, "상대 기준금리": fmt(float(o.iloc[-1]), "%", 2), f"상대 {months}개월 변화": fmt(o_chg, "%p", 2, sign=True),
                     "미국−상대 금리차": fmt(float(g.iloc[-1]), "%p", 2), f"금리차 {months}개월 변화": fmt(g_chg, "%p", 2, sign=True),
                     "동시 반대": "예" if opposite else "아니오"})
    if len(gaps) < 2:
        raise DataUnavailable("유로존·일본 기준금리 없음")
    t = us.index[-1]
    sig = Signal.WATCH if flags else Signal.OK
    headline = flags[0] if flags else f"미국 {months}개월 {us_chg:+.2f}%p — 다른 중앙은행과 정책이 크게 엇갈리지 않음(통화 추세 조건 아님)"
    metrics = {"기준월": fdate(t), "미국 기준금리": fmt(float(us.iloc[-1]), "%", 2), f"미국 {months}개월 변화": fmt(us_chg, "%p", 2, sign=True)}
    notes = flags[1:] + [
        "노랑은 '위험'이 아니라 '통화 추세가 생길 조건'이라는 뜻입니다. 그는 이 조건에서 1/3로 들어가고 가격이 확인되면 늘렸습니다(#13 유로 1.39 → 1.35 돌파 때 증액).",
        "일본은 월간 콜금리(OECD), 유로존은 ECB 예금금리입니다. 기준이 조금 달라도 '방향'을 보는 데는 충분합니다.",
    ]
    charts = [Chart("주요국 기준금리", gaps, y_title="%", years=15),
              Chart("미국 − 상대국 금리차", {f"미국−{k}": (us - v).dropna() for k, v in gaps.items() if k != "미국"},
                    y_title="%p", hlines=[(0, "")], years=15)]
    return ToolResult(sig, headline, metrics, notes, [("미국 vs 상대국", pd.DataFrame(rows))], charts, as_of=fdate(t))
