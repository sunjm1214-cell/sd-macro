"""수익률곡선 — 채권시장을 가장 먼저 읽는다.

채권→통화→주식 순서에서 채권이 첫 번째다. USC 2023에서 그는 "역사상 가장 깊은 역전, 그보다 덜 역전된 과거
11번 모두 침체"를 말하면서, 연준이 대차대조표를 조절하지 않는 지금은 국채시장에 다시 주목한다고 했다.
Sohn 2022: "지난 10~11년 채권시장은 아무 신호도 주지 않았다. 중앙은행이 수조 달러를 사서 가격을 조작했으니까."
→ 연준 국채 보유가 빠르게 늘고 있으면 이 툴의 신뢰도를 낮춘다(QE 오염 표시).
기록: 2022~23년 역전 뒤 그가 예상한 2023년 침체는 오지 않았고, 그는 이를 인정했다.
"""
from __future__ import annotations

import pandas as pd

from ..core import Chart, Context, Signal, ToolResult
from ..registry import tool
from ..stats import episodes, fdate, fmt, to_freq
from . import src


@tool(
    name="yield_curve",
    title="수익률곡선 역전 (10년−3개월, 10년−2년)",
    concept="채권 → 통화 → 주식",
    rule="방향은 채권시장에서 먼저 읽는다. 깊은 역전 뒤에는 침체가 왔다 — 다만 QE가 채권 신호를 오염시킬 수 있다.",
    sources=[src("USC 2023 (가장 깊은 역전, 과거 11번)", "sources/usc-us-exceptionalism-2023"),
             src("Ira Sohn 2022 (QE가 채권 신호를 지웠다)", "sources/ira-sohn-2022-collison"),
             src("Ira Sohn 2023 (역전으로 본 침체 시점)", "sources/ira-sohn-2023-sokoloff"),
             src("채권→통화→주식 개념", "concepts/bonds-currencies-equities")],
    order=20,
    series=["T10Y3M", "T10Y2Y", "USREC", "TREAST"],
    layer="채권",
    use="타이밍",
    lead="역전 후 평균 1년 남짓 (편차 큼)",
)
def run(ctx: Context, primary: str = "T10Y3M", min_months: int = 3, lookback_disinvert_m: int = 12) -> ToolResult:
    curves = {}
    for sid in ("T10Y3M", "T10Y2Y"):
        s = ctx.try_series(sid)
        if s is not None:
            curves[sid] = to_freq(s, "M")
    if primary not in curves:
        primary = next(iter(curves)) if curves else None
    if primary is None:
        from ..core import DataUnavailable
        raise DataUnavailable("T10Y3M/T10Y2Y 모두 없음")
    c = curves[primary]
    t = c.index[-1]
    now = float(c.iloc[-1])
    recs = ctx.recessions()

    eps = episodes(c < 0, min_len=min_months, merge_gap=3)
    rows = []
    for s, e in eps:
        nxt = [r for r in recs if r[0] >= s]
        lead = (nxt[0][0].to_period("M") - s.to_period("M")).n if nxt else None
        elapsed = (t.to_period("M") - s.to_period("M")).n
        if nxt and lead is not None and lead <= 36:
            nxt_label = fdate(nxt[0][0])
        else:
            nxt_label = "아직 없음 (관찰 중)" if elapsed < 36 else "36개월 내 없음"
        rows.append({"역전 시작": fdate(s), "역전 종료": fdate(e), "최저(%p)": round(float(c[s:e].min()), 2),
                     "다음 침체": nxt_label,
                     "선행(개월)": lead if lead is not None and lead <= 36 else None})
    tbl = pd.DataFrame(rows)

    inverted = now < 0
    recent_end = [e for s, e in eps if (t.to_period("M") - e.to_period("M")).n <= lookback_disinvert_m]
    disinverting = (not inverted) and bool(recent_end)
    if inverted:
        sig, msg = Signal.ALERT, "현재 역전 중"
    elif disinverting:
        sig, msg = Signal.ALERT, f"최근 {lookback_disinvert_m}개월 내 역전 해소 — 과거엔 해소(재가팔라짐) 국면에 침체가 시작되는 경우가 많았음"
    elif now < 0.5:
        sig, msg = Signal.WATCH, "곡선 평탄"
    else:
        sig, msg = Signal.OK, "정상 기울기"
    taint = None
    tr = ctx.try_series("TREAST")
    if tr is not None:
        trm = to_freq(tr, "M", "last")
        taint = float((trm.iloc[-1] / trm.iloc[-13] - 1) * 100) if len(trm) > 13 else None
    if taint is not None and taint > 10 and sig == Signal.ALERT:
        sig, msg = Signal.WATCH, msg + " (단, 연준이 국채를 대량 매입 중이라 신호가 오염됐을 수 있음)"
    hits = tbl["선행(개월)"].notna().sum() if len(tbl) else 0
    judged = (tbl["다음 침체"] != "아직 없음 (관찰 중)").sum() if len(tbl) else 0
    headline = f"{primary} = {fmt(now, '%p', 2, sign=True)} → {msg}"
    metrics = {"기준월": fdate(t), f"{primary}": fmt(now, "%p", 2, sign=True)}
    for sid, s in curves.items():
        if sid != primary:
            metrics[sid] = fmt(float(s.iloc[-1]), "%p", 2, sign=True)
    metrics["과거 역전 → 36개월 내 침체"] = f"{hits}/{judged}"
    if taint is not None:
        metrics["연준 국채 보유 1년 변화 (QE 오염)"] = fmt(taint, "%", sign=True)
    if hits:
        metrics["평균 선행"] = fmt(tbl["선행(개월)"].mean(), "개월", 0)
    notes = ["월평균 기준. 침체 판정은 NBER(USREC)이며 NBER는 사후에 발표하므로 최근 침체는 아직 0으로 나올 수 있습니다.",
             "SD는 2022년 '지난 10년간 10년물은 아무 신호도 주지 않았다(중앙은행 조작)'고 했습니다. 연준 국채 보유가 1년간 10% 넘게 늘고 있으면 경고를 주시로 낮춥니다.",
             "2023년 그는 가장 깊은 역전을 근거로 침체를 예상했지만 오지 않았습니다. 그는 이를 '지적 겸손'의 사례로 인정했습니다 — 역전은 확률을 높일 뿐입니다."]
    charts = [Chart("장단기 금리차", {k: v for k, v in curves.items()}, y_title="%p", hlines=[(0, "")])]
    return ToolResult(sig, headline, metrics, notes,
                      [("역전 구간 (월평균 < 0, %d개월 이상)" % min_months, tbl if len(tbl) else pd.DataFrame({"결과": ["없음"]}))],
                      charts, as_of=fdate(t))
