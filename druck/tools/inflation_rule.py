"""인플레이션 5% 규칙 — 두 개의 '무패 기록'.

Sohn 2022: "인플레이션이 5%를 넘으면 기준금리가 CPI를 넘기 전에는 내려온 적이 없다.
그리고 5%를 넘은 인플레이션이 경기침체 없이 잡힌 적도 없다."
이 툴은 CPI 5% 돌파 구간을 모두 찾아 두 규칙이 각각 지켜졌는지 데이터로 확인하고,
지금 실질 정책금리(기준금리 − CPI)가 어디에 있는지 보여준다.
"""
from __future__ import annotations

import pandas as pd

from ..core import Chart, Context, Signal, ToolResult
from ..registry import tool
from ..stats import fdate, fmt, to_freq, yoy_pct
from . import src


def find_episodes(cpi_yoy: pd.Series, ff: pd.Series, recessions, start_th: float, end_th: float,
                  rec_window_m: int) -> pd.DataFrame:
    rows = []
    in_ep = False
    s = None
    idx = cpi_yoy.index
    for i, (t, v) in enumerate(cpi_yoy.items()):
        if not in_ep and v > start_th:
            in_ep, s = True, t
        elif in_ep and v < end_th:
            rows.append((s, t))
            in_ep = False
    if in_ep:
        rows.append((s, None))
    out = []
    for s, e in rows:
        seg = cpi_yoy[s:e] if e is not None else cpi_yoy[s:]
        peak_t = seg.idxmax()
        ff_seg = ff.reindex(seg.index)
        above = ff_seg[ff_seg > seg]
        first_above = above.index[0] if len(above) else None
        end_for_rec = (e if e is not None else idx[-1]) + pd.DateOffset(months=rec_window_m)
        rec = [r for r in recessions if s <= r[0] <= end_for_rec]
        out.append({
            "5% 돌파": fdate(s),
            "5% 초과 개월": int((seg > start_th).sum()),
            "CPI 정점": f"{seg.max():.1f}% ({fdate(peak_t)})",
            f"{end_th:g}% 아래 복귀": fdate(e) if e is not None else "진행 중",
            "기준금리>CPI 최초": fdate(first_above) if first_above is not None else "없음",
            "규칙1 (금리>CPI 후 하락)": ("지켜짐" if first_above is not None else "깨짐") if e is not None else "진행 중",
            "경기침체": fdate(rec[0][0]) if rec else "없음",
            "규칙2 (침체 동반)": ("지켜짐" if rec else "깨짐") if e is not None else "진행 중",
        })
    return pd.DataFrame(out)


@tool(
    name="inflation_rule",
    title="인플레이션 5% 규칙 (기준금리 vs CPI)",
    concept="The Endgame · 역사적 규칙",
    rule="CPI가 5%를 넘으면 ① 기준금리가 CPI를 넘어야 내려오고 ② 경기침체 없이 잡힌 적이 없다.",
    sources=[src("Ira Sohn 2022 (두 개의 무패 기록)", "sources/ira-sohn-2022-collison"),
             src("Delivering Alpha 2022 (경착륙 전망)", "sources/delivering-alpha-2022")],
    order=20,
    series=["CPIAUCSL", "FEDFUNDS", "USREC"],
    layer="유동성·연준",
    use="타이밍",
    lead="수개월~2년 (5% 돌파 후 침체까지)",
)
def run(ctx: Context, start_threshold: float = 5.0, end_threshold: float = 3.0,
        recession_window_months: int = 24) -> ToolResult:
    cpi = yoy_pct(to_freq(ctx.series("CPIAUCSL"), "M"), 12).dropna()
    ff = to_freq(ctx.series("FEDFUNDS"), "M")
    df = pd.DataFrame({"CPI(전년비)": cpi, "기준금리": ff}).dropna()
    df["실질 정책금리"] = df["기준금리"] - df["CPI(전년비)"]
    t = df.index[-1]
    now = df.iloc[-1]
    eps = find_episodes(df["CPI(전년비)"], df["기준금리"], ctx.recessions(), start_threshold,
                        end_threshold, recession_window_months)

    c, real = float(now["CPI(전년비)"]), float(now["실질 정책금리"])
    if c > start_threshold and real < 0:
        sig, msg = Signal.ALERT, "고인플레인데 실질금리가 마이너스 — 역사상 이 상태로 물가가 잡힌 적 없음"
    elif c > start_threshold:
        sig, msg = Signal.WATCH, "고인플레, 실질금리 플러스 — 물가는 잡히는 경로지만 침체 동반이 역사적 기본값"
    elif c > end_threshold and real < 0:
        sig, msg = Signal.WATCH, "물가가 목표 위인데 실질금리 마이너스 — 재가속 위험(1970년대 2차 파동 패턴)"
    else:
        sig, msg = Signal.OK, "5% 규칙 구간 아님"
    headline = f"CPI {fmt(c, '%')}, 기준금리 {fmt(now['기준금리'], '%', 2)}, 실질 정책금리 {fmt(real, '%p', sign=True)} → {msg}"

    done = eps[eps[f"{end_threshold:g}% 아래 복귀"] != "진행 중"] if len(eps) else eps
    r1 = (done["규칙1 (금리>CPI 후 하락)"] == "지켜짐").sum() if len(done) else 0
    r2 = (done["규칙2 (침체 동반)"] == "지켜짐").sum() if len(done) else 0
    metrics = {
        "기준월": fdate(t),
        "CPI 전년비": fmt(c, "%"),
        "기준금리": fmt(now["기준금리"], "%", 2),
        "실질 정책금리": fmt(real, "%p", sign=True),
        "규칙1 기록": f"{r1}/{len(done)} 구간 지켜짐",
        "규칙2 기록": f"{r2}/{len(done)} 구간 지켜짐",
    }
    notes = [
        f"구간 정의: CPI 전년비가 {start_threshold:g}%를 넘은 달부터 {end_threshold:g}% 아래로 내려온 달까지. 침체는 구간 시작~종료 후 {recession_window_months}개월 안에 시작된 NBER 침체.",
        "SD 본인은 2022년에 '규칙1은 깨지고 규칙2는 지켜질 것'이라 했지만, 실제로는 디스인플레이션은 맞고 침체는 오지 않았습니다(사이트가 '지적 겸손' 사례로 기록).",
        "'5% 초과 개월'이 몇 달뿐인 구간(예: 2008년 원자재 급등)은 지속적 인플레이션이 아니라 일시적 스파이크라 규칙의 취지와 다를 수 있습니다.",
        "그가 강조한 함정: 연준이 근원 물가만 보더라도 노조는 체감 물가로 임금을 협상한다 — 헤드라인 CPI를 쓰는 이유.",
    ]
    tables = [(f"CPI {start_threshold:g}% 돌파 구간과 두 규칙 검증", eps if len(eps) else pd.DataFrame({"결과": ["구간 없음"]}))]
    charts = [Chart("CPI 전년비 vs 기준금리", {"CPI 전년비": df["CPI(전년비)"], "기준금리": df["기준금리"]},
                    y_title="%", hlines=[(start_threshold, "5%"), (0, "")], years=None),
              Chart("실질 정책금리 (기준금리 − CPI)", {"실질 정책금리": df["실질 정책금리"]}, kind="bar",
                    y_title="%p", hlines=[(0, "")], years=None)]
    return ToolResult(sig, headline, metrics, notes, tables, charts, as_of=fdate(t), data={"episodes": eps})
