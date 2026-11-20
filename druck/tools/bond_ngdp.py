"""10년물 vs 명목GDP — 그의 '황금률'.

Bloomberg 2024: "내가 늘 써온 황금률은 10년물이 명목GDP 근처에서 거래돼야 한다는 것이다(지금 5.5%).
인플레이션이 다시 오르면 채권은 수백bp 움직일 수 있고, 틀려도 25~30bp 잃는다. 그래서 국채 숏이 위험보상이 좋다."
Norges 2023: "10년물은 명목GDP까지 갈 수 있다. 1970년대 채권시장은 인플레이션이 3%에서 12%로 다시 오를 때까지
반응하지 않다가 한꺼번에 반응했다."

10년물이 명목성장보다 한참 낮다 = 채권이 '억눌려' 있다(연준 매입·금융억압). 그 괴리는 채권 보유자에게 비대칭 위험이다.
"""
from __future__ import annotations

import pandas as pd

from ..core import Chart, Context, Signal, ToolResult
from ..registry import tool
from ..stats import episodes, fdate, fmt, to_freq, yoy_pct
from . import src


@tool(
    name="bond_ngdp",
    title="채권 황금률 (10년물 vs 명목GDP 성장률)",
    concept="채권 → 통화 → 주식 · 비대칭 위험보상",
    rule="10년물은 명목GDP 성장률 근처에서 거래돼야 한다. 한참 아래면 채권이 억눌린 것이고, 되돌림은 수백bp일 수 있다.",
    sources=[src("Bloomberg 2024 (황금률: 10년물 ≈ 명목GDP)", "sources/bloomberg-sonali-2024"),
             src("Norges Bank 2023 (1970년대 채권의 뒤늦은 반응)", "sources/norges-bank-in-good-company-2023"),
             src("Ira Sohn 2022 (QE가 채권 신호를 지웠다)", "sources/ira-sohn-2022-collison")],
    order=10,
    series=["GS10", "GDP", "TREAST"],
    layer="채권",
    use="사이즈",
    lead="수개월~수년 (되돌림 시점은 인플레이션 재점화가 결정)",
)
def run(ctx: Context, alert_gap: float = -2.0, watch_gap: float = -1.0, smooth_q: int = 8) -> ToolResult:
    y10 = to_freq(ctx.series("GS10"), "Q")
    gdp = to_freq(ctx.series("GDP"), "Q")
    ng = yoy_pct(gdp, 4)
    ng_s = ((gdp / gdp.shift(smooth_q)) ** (4 / smooth_q) - 1) * 100  # 2년 연율 — 코로나 같은 급변 완화
    df = pd.DataFrame({"10년물": y10, "명목GDP 전년비": ng, f"명목GDP {smooth_q // 4}년 연율": ng_s}).dropna()
    df["괴리(10년물−명목성장)"] = df["10년물"] - df["명목GDP 전년비"]
    df["괴리(평활)"] = df["10년물"] - df[f"명목GDP {smooth_q // 4}년 연율"]
    t = df.index[-1]
    row = df.iloc[-1]
    gap, gap_s = float(row["괴리(10년물−명목성장)"]), float(row["괴리(평활)"])
    y_now = float(to_freq(ctx.series("GS10"), "M").iloc[-1])  # 화면에는 최신 월 금리

    # QE 오염: 연준이 국채를 늘리는 중이면 '시장이 정한 가격'이 아니다
    taint = None
    tr = ctx.try_series("TREAST")
    if tr is not None:
        trm = to_freq(tr, "M", "last")
        taint = float((trm.iloc[-1] / trm.iloc[-13] - 1) * 100) if len(trm) > 13 else None

    # 둘 다(전년비·평활) 아래일 때만 '억눌림'으로 본다 — 한 분기 급등락에 흔들리지 않게
    worst = max(gap, gap_s)
    if worst <= alert_gap:
        sig, msg = Signal.ALERT, "10년물이 명목성장보다 한참 낮음 — 채권이 억눌려 있고 되돌림 위험이 큼(그가 국채 숏을 든 조합)"
    elif worst <= watch_gap:
        sig, msg = Signal.WATCH, "10년물이 명목성장보다 낮음 — 채권 보유자에 불리한 비대칭"
    elif min(gap, gap_s) >= 1.5:
        sig, msg = Signal.WATCH, "10년물이 명목성장보다 높음 — 성장 둔화를 선반영(채권이 경기 약세를 말하는 중)"
    else:
        sig, msg = Signal.OK, "10년물이 명목성장 근처 — 황금률 범위"
    headline = (f"10년물 {fmt(y_now, '%', 2)} vs 명목성장 {fmt(row['명목GDP 전년비'], '%')}(2년 연율 "
                f"{fmt(row[f'명목GDP {smooth_q // 4}년 연율'], '%')}) → 괴리 {fmt(gap, '%p', sign=True)} · {msg}")
    metrics = {
        "기준 분기": fdate(t),
        "10년물 (최신 월)": fmt(y_now, "%", 2),
        "명목GDP 전년비": fmt(row["명목GDP 전년비"], "%"),
        "괴리 (10년물 − 명목성장)": fmt(gap, "%p", sign=True),
        f"명목GDP {smooth_q // 4}년 연율": fmt(row[f"명목GDP {smooth_q // 4}년 연율"], "%"),
        "괴리 (평활)": fmt(gap_s, "%p", sign=True),
    }
    if taint is not None:
        metrics["연준 국채 보유 1년 변화"] = fmt(taint, "%", sign=True)

    notes = []
    if taint is not None and taint > 5:
        notes.append(f"연준이 국채 보유를 1년간 {taint:+.0f}% 늘리는 중 — 그의 말대로 '중앙은행이 가격을 조작하는 동안 채권은 신호가 없다'. 괴리는 시장 판단이 아니라 매입의 결과일 수 있습니다.")
    elif taint is not None and taint < -5:
        notes.append(f"연준이 국채를 1년간 {taint:+.0f}% 줄이는 중(QT) — 채권 가격이 다시 시장에서 정해지는 국면. 그는 이때 채권 신호에 다시 주목한다고 했습니다(USC 2023).")
    notes += [
        "그의 2024년 계산: 틀리면 25~30bp 손실, 맞으면(인플레 재가속) 수백bp — 같은 괴리라도 인플레이션 방향이 보상을 결정합니다. 인플레이션 5% 규칙·금융여건 툴과 같이 보세요.",
        "명목GDP는 분기 데이터라 1~2개월 늦습니다. 전년비와 2년 연율이 모두 아래일 때만 '억눌림'으로 판정합니다.",
    ]
    deep = episodes(df["괴리(평활)"] <= alert_gap, min_len=4, merge_gap=1)
    rows = []
    for s, e in deep:
        seg = df.loc[s:e]
        after = y10[(y10.index > e)].iloc[:8]
        rows.append({"시작": fdate(s), "끝": fdate(e), "분기": len(seg), "최저 괴리(%p)": round(float(seg["괴리(평활)"].min()), 1),
                     "구간 끝 10년물": fmt(float(seg["10년물"].iloc[-1]), "%", 2),
                     "이후 2년 10년물 최고": fmt(float(after.max()), "%", 2) if len(after) else "-"})
    tables = [(f"평활 괴리 {alert_gap:g}%p 이하가 1년 넘게 지속된 구간",
               pd.DataFrame(rows) if rows else pd.DataFrame({"결과": ["없음"]}))]
    charts = [
        Chart("10년물 vs 명목GDP 성장률", {"10년물": df["10년물"], "명목GDP 전년비": df["명목GDP 전년비"],
                                          f"명목GDP {smooth_q // 4}년 연율": df[f"명목GDP {smooth_q // 4}년 연율"]},
              y_title="%", hlines=[(0, "")], years=None),
        Chart("괴리 (10년물 − 명목성장, 평활)", {"괴리": df["괴리(평활)"]}, kind="bar", y_title="%p",
              hlines=[(alert_gap, ""), (0, "")], years=None),
    ]
    return ToolResult(sig, headline, metrics, notes, tables, charts, as_of=fdate(t), data={"frame": df})
