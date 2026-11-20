"""달러 — 2026년 그가 달러 약세에 베팅한 세 가지 이유.

Morgan Stanley 2026: "달러에 약세다. 주로 ① 구매력 기준으로 역사적 범위의 상단이고 ② 외국인이 달러를 과도하게,
아주 과도하게 들고 있기 때문이다. 'Sell America'라기보다, ③ 무역수지와 포지셔닝 때문에 외국인이 미국 자산을
순매수하지 않기만 해도 달러는 혼자 내려간다."
CNBC 2021: "연준이 화폐화하면 달러에 끔찍한 결과" — 재정 툴과 연결.

① 실질실효환율 분위(구매력), ② 순국제투자포지션(NIIP)/GDP — 외국인이 쌓아둔 미국 자산의 크기,
③ 경상수지/GDP — 외국인이 매년 새로 사줘야 하는 양.
"""
from __future__ import annotations

import pandas as pd

from ..core import Chart, Context, DataUnavailable, Signal, ToolResult
from ..registry import tool
from ..stats import fdate, fmt, percentile_rank, to_freq, yoy_pct, zscore
from . import src


@tool(
    name="dollar",
    title="달러 (구매력 고평가 · 외국인 과다보유 · 경상수지)",
    concept="채권 → 통화 → 주식 · 비대칭 위험보상",
    rule="달러가 구매력 기준 역사적 상단이고 외국인이 달러 자산을 과도하게 들고 있으면, 그들이 순매수만 멈춰도 달러는 혼자 내려간다.",
    sources=[src("Morgan Stanley 2026 (달러 약세 세 가지 근거)", "sources/morgan-stanley-hard-lessons-2026"),
             src("CNBC 2021 (화폐화와 기축통화)", "sources/cnbc-squawk-2021"),
             src("Talks at GS 2021 (달러 숏)", "sources/talks-at-gs-2021")],
    order=10,
    series=["RBUSBIS", "RTWEXBGS", "IIPUSNETIQ", "IEABC", "GDP"],
    layer="통화",
    use="사이즈",
    lead="수년 (고평가 해소는 긴 추세)",
)
def run(ctx: Context, high_pct: float = 85.0, trend_months: int = 6, niip_low_pct: float = 10.0) -> ToolResult:
    s, sid = None, None
    for cand in ("RBUSBIS", "RTWEXBGS"):
        s = ctx.try_series(cand)
        if s is not None:
            sid = cand
            break
    if s is None:
        raise DataUnavailable("실질실효환율(RBUSBIS/RTWEXBGS) 없음")
    m = to_freq(s, "M")
    t = m.index[-1]
    now = float(m.iloc[-1])
    pct = percentile_rank(m, now)
    z = float(zscore(m).iloc[-1])
    mom = float((m.iloc[-1] / m.iloc[-1 - trend_months] - 1) * 100) if len(m) > trend_months else float("nan")
    ma = m.rolling(12).mean()
    below_ma = now < float(ma.iloc[-1])
    rich = pct >= high_pct

    metrics = {"기준월": fdate(t), "실질실효환율 분위": fmt(pct, "%", 0), "z-점수": fmt(z, "", 2, sign=True),
               f"{trend_months}개월 변화": fmt(mom, "%", sign=True), "12개월 평균 아래?": "예" if below_ma else "아니오"}
    charts = [Chart(f"달러 실질실효환율 ({sid})", {"달러": m, "12개월 평균": ma.dropna()}, y_title="지수")]

    gdp = to_freq(ctx.series("GDP"), "Q")
    overloaded, ca_def = None, None
    niip = ctx.try_series("IIPUSNETIQ")
    if niip is not None:
        n = to_freq(niip, "Q", "last") / 1000  # 백만 → 십억 달러
        r = (n / gdp * 100).dropna()
        rn = float(r.iloc[-1])
        overloaded = percentile_rank(r, rn) <= niip_low_pct
        metrics["순국제투자포지션/GDP"] = fmt(rn, "%", 0)
        metrics["NIIP 역사적 분위 (낮을수록 외국인 과다보유)"] = fmt(percentile_rank(r, rn), "%", 0)
        charts.append(Chart("순국제투자포지션 / GDP (음수 = 외국인이 가진 미국 자산이 더 많음)", {"NIIP/GDP": r},
                            y_title="%", hlines=[(0, "")]))
    ca = ctx.try_series("IEABC")
    if ca is not None:
        c = (to_freq(ca, "Q", "last") * 4 / 1000 / gdp * 100).dropna()  # 분기 → 연율, 백만 → 십억
        cn = float(c.iloc[-1])
        ca_def = cn < -2.0
        metrics["경상수지/GDP"] = fmt(cn, "%", 1, sign=True)
        charts.append(Chart("경상수지 / GDP (외국인이 매년 새로 사줘야 하는 양)", {"경상수지/GDP": c},
                            y_title="%", hlines=[(0, "")], kind="bar"))

    turned = mom < 0 and below_ma
    structural = rich and bool(overloaded) and bool(ca_def)
    if structural and turned:
        sig, msg = Signal.ALERT, "고평가 + 외국인 과다보유 + 경상적자에 추세까지 꺾임 — 그의 2026년 달러 약세 논리 그대로"
    elif structural:
        sig, msg = Signal.WATCH, "고평가 + 외국인 과다보유 + 경상적자 — 구조는 갖춰졌고 추세 전환 확인 대기"
    elif rich:
        sig, msg = Signal.WATCH, "구매력 기준 고평가 — 포지셔닝·경상수지 조건은 일부만 충족"
    elif pct <= 100 - high_pct:
        sig, msg = Signal.WATCH, "저평가 구간 — 반대 방향 위험"
    else:
        sig, msg = Signal.OK, "중립 구간"
    lit = " · ".join(("●" if v else "○") + " " + k for k, v in
                     (("구매력 고평가", rich), ("외국인 과다보유", bool(overloaded)), ("경상적자 2% 초과", bool(ca_def)),
                      ("추세 꺾임", turned)))
    headline = f"실질실효환율 {pct:.0f}% 분위 → {msg}"
    notes = [f"점검 항목: {lit}",
             "'신호'는 달러 자산 보유자 관점의 경고등입니다. 빨강 = 달러 하락 위험이 크다(비달러 자산·원자재에는 우호적일 수 있음). 그는 2021년에도 달러 숏을 인플레이션 매트릭스의 한 축으로 썼습니다.",
             "외국인의 세부 포지셔닝(TIC)은 FRED에 없어 NIIP로 대신했습니다. NIIP는 분기 데이터이며 환율·주가 변동에 따른 평가 변화가 섞여 있습니다."]
    return ToolResult(sig, headline, metrics, notes, [], charts, as_of=fdate(t))
