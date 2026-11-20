"""시장 내부 — 경기민감주 vs 방어주. 그가 꼽은 '최고의 경제 예측기'.

ECNY 2019: "거시 통계는 어디 있는지·어디 있었는지는 잘 알려주지만 예측력은 별로다. 내가 본 최고의 경제 예측기는
주식시장 '내부', 즉 경기민감 기업들이다. 특히 트럭·소매·러셀2000. 이들이 빠지기 시작하고 방어주와 장기성장주가
상대적으로 오르면 신호다." 당시 XRT −24%, 러셀 −15%, 금속 −20%가 모두 52주 상대 저점, 1% 성장에서도 3%에서도
실적이 비슷한 기업들은 상대 고점이었다.
Sohn 2022: 주택건설 고점 대비 −50%, 트럭 −40% — 실적은 사상 최고인데. "트럭만이면 괜찮다. 그런데 주택·소매·전부다."
그리고 "선행 기간은 6개월~1년". Sohn 2023: 트럭은 6~8개월 선행.
주의: 코로나로 소매는 '오염된 신호'(2022). 2026년엔 "기술적 분석·가격 vs 뉴스는 경쟁 때문에 효과가 줄었다".

yfinance가 필요하다 (pip install yfinance).
"""
from __future__ import annotations

import pandas as pd

from ..core import Chart, Context, DataUnavailable, Signal, ToolResult
from ..registry import tool
from ..stats import fmt
from . import src

CYCLICALS = {"XRT": "소매", "IYT": "운송(트럭)", "ITB": "주택건설", "IWM": "소형주(러셀2000)", "XME": "금속·광업"}
DEFENSIVES = {"XLP": "필수소비재", "XLU": "유틸리티"}


def _range_pos(s: pd.Series, days: int = 252) -> float:
    """최근 52주 범위 안에서의 위치 (0 = 저점, 100 = 고점)."""
    w = s.iloc[-days:]
    lo, hi = float(w.min()), float(w.max())
    return float((s.iloc[-1] - lo) / (hi - lo) * 100) if hi > lo else 50.0


@tool(
    name="sector_leadership",
    title="시장 내부 (경기민감주 vs 방어주 상대강도)",
    concept="기술적 확인 · 18개월 룰",
    rule="경기민감 업종(트럭·소매·주택·소형주·금속)이 방어주 대비 52주 상대 저점으로 밀리면, 실적이 좋아도 경제는 6~12개월 뒤 꺾인다. 한 업종이 아니라 '전부'일 때 신호다.",
    sources=[src("Economic Club of NY 2019 (시장 내부가 최고의 예측기)", "sources/economic-club-ny-2019"),
             src("Ira Sohn 2022 (주택 −50%, 트럭 −40%, 선행 6~12개월)", "sources/ira-sohn-2022-collison"),
             src("Ira Sohn 2023 (트럭 6~8개월 선행)", "sources/ira-sohn-2023-sokoloff"),
             src("Real Vision 2018 (내부 업종 신호의 약화)", "sources/real-vision-monetary-policy-2018")],
    order=10,
    series=[],
    layer="주식·이익",
    use="타이밍",
    lead="6~12개월 (트럭 6~8개월)",
    tickers=[*CYCLICALS, *DEFENSIVES],
)
def run(ctx: Context, rel_months: int = 6, low_zone: float = 20.0, weak_rel_pct: float = -5.0,
        cyclicals: dict | None = None, defensives: dict | None = None) -> ToolResult:
    cyclicals = cyclicals or CYCLICALS
    defensives = defensives or DEFENSIVES
    defs = []
    for tk in defensives:
        try:
            p = ctx.price(tk)
            defs.append(p / p.iloc[0])
        except DataUnavailable:
            pass
    if not defs:
        raise DataUnavailable("방어주 가격(XLP/XLU) 없음")
    d = pd.concat(defs, axis=1).dropna().mean(axis=1)  # 동일가중 방어주 바스켓
    days = int(rel_months * 21)
    rows, rel_series, weak, got = [], {}, 0, 0
    t = d.index[-1]
    for tk, name in cyclicals.items():
        try:
            p = ctx.price(tk)
        except DataUnavailable:
            rows.append({"티커": tk, "업종": name, "상태": "데이터 없음"})
            continue
        df = pd.concat([p.rename("p"), d.rename("d")], axis=1).dropna()
        if len(df) < max(days, 252) + 2:
            continue
        got += 1
        rel = df["p"] / df["d"]
        rel_ret = float((rel.iloc[-1] / rel.iloc[-1 - days] - 1) * 100)
        pos = _range_pos(rel)
        dd = float((df["p"].iloc[-1] / df["p"].iloc[-252:].max() - 1) * 100)
        is_weak = pos <= low_zone and rel_ret <= weak_rel_pct
        weak += is_weak
        rows.append({"티커": tk, "업종": name, f"방어주 대비 {rel_months}개월": fmt(rel_ret, "%p", sign=True),
                     "52주 상대 범위 위치": fmt(pos, "", 0), "52주 고점 대비(절대)": fmt(dd, "%", sign=True),
                     "상태": "약세 ⚠" if is_weak else ("주의" if pos <= 40 else "양호")})
        rel_series[f"{tk} {name}"] = rel.iloc[-756:] / rel.iloc[-756:].iloc[0] * 100
    if not got:
        raise DataUnavailable("경기민감 업종 가격 없음")

    if weak >= 3:
        sig, msg = Signal.ALERT, "경기민감 업종 다수가 방어주 대비 52주 상대 저점권 — '트럭만이 아니라 전부' 국면"
    elif weak >= 2:
        sig, msg = Signal.WATCH, "경기민감 업종 일부가 상대 저점권 — 확산되는지 지켜볼 단계"
    elif weak == 1:
        sig, msg = Signal.WATCH, "한 업종만 약세 — 그의 말로 '그것만이면 괜찮다'"
    else:
        sig, msg = Signal.OK, "경기민감 업종이 방어주 대비 버팀 — 시장 내부는 경기 둔화를 말하지 않음"
    headline = f"경기민감 {got}개 중 {weak}개가 방어주 대비 52주 상대 저점권 + {rel_months}개월 {weak_rel_pct:g}%p 이하 → {msg}"
    metrics = {"기준일": t.strftime("%Y-%m-%d"), "약세 업종(폭)": f"{weak}/{got}",
               "비교 기준": " + ".join(defensives.values()) + " 동일가중"}
    notes = ["'52주 상대 범위 위치'는 (경기민감 ÷ 방어주) 비율이 최근 1년 범위의 어디에 있는지입니다. 0이면 1년 중 가장 약한 상태.",
             "그는 가격과 뉴스를 함께 봤습니다: 주택건설·트럭이 '실적 사상 최고'인데 −40~50%였던 2022년처럼, 실적이 좋은데 주가가 무너지면 시장이 아직 공개되지 않은 무언가를 말하는 것입니다. 실적 발표와 같이 보세요.",
             "2022년 단서: 코로나로 소매는 지갑 점유율이 85%→100%로 왜곡된 '오염된 신호'였습니다. 2026년엔 이런 기법이 경쟁 때문에 효과가 줄었다고 스스로 평가했습니다 — 보조 신호로 쓰세요."]
    charts = [Chart("방어주 대비 상대강도 (3년, 시작=100)", rel_series, y_title="지수", shade_recessions=False)]
    return ToolResult(sig, headline, metrics, notes, [("업종별 상태", pd.DataFrame(rows))], charts,
                      as_of=t.strftime("%Y-%m-%d"))
