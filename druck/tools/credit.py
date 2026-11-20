"""신용·기업 행태 — 공짜 돈은 나쁜 행동을 만든다.

- Lost Tree 2015: 2013~14 발행 1.1조 달러(2006~07의 1.5배), B등급 비중 28%→71%, 커버넌트 라이트 20%→60%+
- Endgame 2016: "영업현금흐름 증가율은 5년 전 정점을 지나 전년비 마이너스인데 순부채는 고속 증가 — 전후 처음, 5년 괴리는 전례 없다"
- ECNY 2019: 2010~18 기업부채 6조→10조(+65%) vs 이익 1.7조→2.2조
- Norges 페이지 녹취: 스프레드 타이트·금 신고가·주식 급등인데 50bp 인하 — 불안
- Talks at GS 2021: "신용은 8년마다 시장이 완전히 무너질 때만 들어가서 산다" → 스프레드 폭발은 그에게 '기회'

그래서 부채를 회계이익(CP)이 아니라 기업 순현금흐름(CNCF)과 비교한다. 발행의 질(B등급·커버넌트)은 FRED에 없다.
"""
from __future__ import annotations

import pandas as pd

from ..core import Chart, Context, DataUnavailable, Signal, ToolResult
from ..registry import tool
from ..stats import diff, fdate, fmt, percentile_rank, to_billions, to_freq, yoy_pct
from . import src


@tool(
    name="credit",
    title="신용 · 기업 행태 (스프레드 · 부채 vs 현금흐름)",
    concept="The Endgame · 유동성 > 실적",
    rule="현금흐름은 꺾였는데 부채만 늘면 성장을 미래에서 빌린 것. 스프레드가 타이트한데 연준이 내리면 과열이고, 스프레드가 폭발하면 그때가 신용을 살 때다.",
    sources=[src("The Endgame 2016 (현금흐름 vs 순부채 괴리)", "sources/ira-sohn-endgame-2016"),
             src("Lost Tree Club 2015 (B등급·커버넌트 라이트)", "sources/lost-tree-club-2015"),
             src("Economic Club of NY 2019 (부채 +65% vs 이익)", "sources/economic-club-ny-2019"),
             src("Talks at GS 2021 (8년마다 오는 신용 붕괴)", "sources/talks-at-gs-2021"),
             src("Norges Bank 페이지 (타이트 스프레드 속 인하)", "sources/norges-bank-in-good-company-2023")],
    order=20,
    series=["BAMLH0A0HYM2", "BAA10Y", "FEDFUNDS", "BCNSDODNS", "CNCF", "CP"],
    layer="누적 위험",
    use="사이즈",
    lead="수년 (누적) · 스프레드 급확대는 즉시",
)
def run(ctx: Context, tight_pct: float = 10.0, widening_bp: float = 150.0, hy_widen_bp: float = 40.0, min_history_years: int = 10,
        diverge_q: int = 4) -> ToolResult:
    """하이일드 OAS의 역사가 min_history_years보다 짧으면 분위와 신호는 Moody's Baa−10년물(1986~)로 계산한다.
    급확대 폭 기준도 Baa에 맞춰 1/2로 줄인다."""
    hy_raw, baa_raw = ctx.try_series("BAMLH0A0HYM2"), ctx.try_series("BAA10Y")
    hy = to_freq(hy_raw, "M") if hy_raw is not None else None
    baa = to_freq(baa_raw, "M") if baa_raw is not None else None
    hy_years = (hy.index[-1] - hy.index[0]).days / 365.25 if hy is not None else 0
    if hy is not None and hy_years >= min_history_years:
        main, main_name, wide_bp = hy, "하이일드 OAS", widening_bp
    elif baa is not None:
        main, main_name, wide_bp = baa, "Baa−10년물 스프레드", widening_bp / 2
    elif hy is not None:
        main, main_name, wide_bp = hy, "하이일드 OAS(짧은 역사)", widening_bp
    else:
        raise DataUnavailable("신용 스프레드(BAMLH0A0HYM2/BAA10Y) 없음")
    t = main.index[-1]
    now = float(main.iloc[-1])
    pct = percentile_rank(main, now)
    chg3 = float(diff(main, 3).iloc[-1]) * 100  # bp
    ff6 = float(diff(to_freq(ctx.series("FEDFUNDS"), "M"), 6).dropna().iloc[-1])

    flags, level = [], 0
    hy_chg3 = None
    if hy_raw is not None and main is not hy and len(hy_raw) > 70:  # 짧은 하이일드로 '방향'만 본다
        base = hy_raw[hy_raw.index <= hy_raw.index[-1] - pd.Timedelta(days=91)]
        if len(base):
            hy_chg3 = (float(hy_raw.iloc[-1]) - float(base.iloc[-1])) * 100
            if hy_chg3 >= hy_widen_bp:
                level = max(level, 1)
                flags.append(f"하이일드 스프레드가 3개월 {hy_chg3:+.0f}bp 확대 — 투자등급(Baa)은 아직 타이트해도 정크본드부터 벌어지는 중")
    if chg3 >= wide_bp:
        level = 2
        flags.append(f"스프레드 3개월 {chg3:.0f}bp 급확대 — 신용 스트레스. 그에게는 '8년마다 오는' 신용 매수 기회의 초입일 수 있음")
    if pct <= tight_pct * 2.5 and ff6 < -0.2:
        level = max(level, 1)
        flags.append(f"스프레드가 역사적 하위 {pct:.0f}%로 타이트한데 연준이 6개월간 {ff6:+.2f}%p 인하 — 그가 불안해한 '완화 속 완화'")
    elif pct <= tight_pct:
        level = max(level, 1)
        flags.append(f"스프레드가 역사적 하위 {pct:.0f}% — 위험에 대한 보상이 거의 없음(2015년 그가 지적한 느슨한 신용 기준의 환경)")

    metrics = {"기준월": fdate(t), main_name: fmt(now, "%p", 2),
               f"역사적 분위 ({fdate(main.index[0])}~, 낮을수록 타이트)": fmt(pct, "%", 0),
               "3개월 변화": fmt(chg3, "bp", 0, sign=True), "기준금리 6개월 변화": fmt(ff6, "%p", 2, sign=True)}
    if hy is not None and main is not hy:
        metrics["하이일드 OAS (참고)"] = fmt(float(hy_raw.iloc[-1]), "%p", 2)
    if hy_chg3 is not None:
        metrics["하이일드 3개월 변화"] = fmt(hy_chg3, "bp", 0, sign=True)
    spreads = {k: v for k, v in (("HY OAS", hy), ("Baa−10년", baa)) if v is not None}
    charts = [Chart("신용 스프레드", spreads, y_title="%p")]
    tables = []

    debt = ctx.try_series("BCNSDODNS")
    cf = ctx.try_series("CNCF")
    cf_name = "기업 순현금흐름"
    if cf is None:
        cf, cf_name = ctx.try_series("CP"), "기업이익(현금흐름 대용)"
    if debt is not None and cf is not None:
        d = to_billions(to_freq(debt, "Q"), 1000, 40000)
        c = to_freq(cf, "Q")
        df = pd.DataFrame({"부채 전년비": yoy_pct(d, 4), f"{cf_name} 전년비": yoy_pct(c, 4)}).dropna()
        diverge = (df["부채 전년비"] > 0) & (df[f"{cf_name} 전년비"] < 0)
        streak = 0
        for v in reversed(diverge.to_list()):
            if not v:
                break
            streak += 1
        lev = (d / c).dropna()
        d8 = float((d.iloc[-1] / d.iloc[-33] - 1) * 100) if len(d) > 33 else float("nan")
        c8 = float((c.iloc[-1] / c.iloc[-33] - 1) * 100) if len(c) > 33 else float("nan")
        metrics.update({"기업부채 전년비": fmt(df["부채 전년비"].iloc[-1], "%"),
                        f"{cf_name} 전년비": fmt(df[f"{cf_name} 전년비"].iloc[-1], "%"),
                        "부채 '증가 + 현금흐름 감소' 연속": f"{streak}분기",
                        "부채/현금흐름 배수": fmt(float(lev.iloc[-1]), "배"),
                        "배수 분위": fmt(percentile_rank(lev, float(lev.iloc[-1])), "%", 0),
                        "8년 누적: 부채 vs 현금흐름": f"{fmt(d8, '%', 0, sign=True)} vs {fmt(c8, '%', 0, sign=True)}"})
        if streak >= diverge_q:
            level = max(level, 2)
            flags.insert(0, f"부채는 늘고 현금흐름은 줄어드는 상태가 {streak}분기 연속 — Endgame 연설의 '전례 없는 괴리'")
        elif streak >= 2:
            level = max(level, 1)
            flags.append(f"부채 증가 + 현금흐름 감소 {streak}분기째")
        eps = []
        run_s = None
        for ts, v in diverge.items():
            if v and run_s is None:
                run_s = ts
            if not v and run_s is not None:
                eps.append((run_s, prev))
                run_s = None
            prev = ts
        if run_s is not None:
            eps.append((run_s, prev))
        rows = [{"시작": fdate(a), "끝": fdate(b), "분기": len(diverge[a:b])} for a, b in eps if len(diverge[a:b]) >= 2]
        tables.append((f"부채 증가 + {cf_name} 감소가 2분기 이상 이어진 구간",
                       pd.DataFrame(rows) if rows else pd.DataFrame({"결과": ["없음"]})))
        charts.append(Chart(f"비금융기업 부채 vs {cf_name} 증가율", {
            "부채 전년비": df["부채 전년비"], f"{cf_name} 전년비": df[f"{cf_name} 전년비"]}, y_title="%",
            hlines=[(0, "")]))

    sig = [Signal.OK, Signal.WATCH, Signal.ALERT][level]
    headline = flags[0] if flags else f"{main_name} {now:.2f}%p(분위 {pct:.0f}%), 부채·현금흐름 괴리 없음 — 과열·스트레스 신호 없음"
    notes = flags[1:] + [
        "신용의 '질'(B등급 비중, 커버넌트 라이트 비중, 발행량)은 FRED에 없어 다루지 못합니다. 2015년 그가 본 핵심 재료이므로 발행 통계가 있으면 --csv로 추가하세요.",
        "스프레드 급확대는 경고(빨강)로 표시하지만, 그의 실제 행동은 그때 신용을 '사는' 것이었습니다 — 리스크 관리 관점과 기회 관점을 같이 보세요.",
    ]
    return ToolResult(sig, headline, metrics, notes, tables, charts, as_of=fdate(t))
