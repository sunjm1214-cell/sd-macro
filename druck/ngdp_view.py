"""명목GDP vs 금리 화면 — 판단 없이 데이터를 보는 화면(툴 신호 아님).

팩트체크 (chian.io 원문 대조, 2026-10-13):
- 명목GDP를 '따라간다'고 한 금리는 **10년물 국채금리**다.
  Robin Hood 2016 "조작되지 않을 때 10년물은 명목GDP 위에서 거래되는 경향",
  Norges 2023 "10년물은 명목GDP까지 갈 수 있다", Bloomberg 2024 "황금률: 10년물은 명목GDP 근처(5.5%)".
- 기준금리는 '따라가야 한다'가 아니라, 명목성장보다 한참 낮으면 연준이 너무 완화적이라는 증거로 썼다
  (2003년 명목성장 7~9% vs 기준금리 1% — Lost Tree 2015, Real Vision 2018, ECNY 2019).
"""
from __future__ import annotations

import pandas as pd

from .core import Chart, Context
from .stats import fdate, fmt, to_freq, yoy_pct

FACTCHECK = [
    ("10년물 국채", "조작되지 않을 때 10년물은 명목GDP 위에서 거래되는 경향이 있다", "Robin Hood 2016",
     "sources/robin-hood-ptj-2016"),
    ("10년물 국채", "10년물은 명목GDP까지 갈 수 있다 (인플레 4~4.5% + 실질성장 2.5~3% → 6~7%)", "Norges Bank 2023",
     "sources/norges-bank-in-good-company-2023"),
    ("10년물 국채", "내 황금률: 10년물은 명목GDP 근처에서 거래돼야 한다 — 지금 5.5%", "Bloomberg 2024",
     "sources/bloomberg-sonali-2024"),
    ("기준금리", "2003년 명목성장 9%인데 기준금리 1% — 연준 실수의 대표 사례 ('따라가야 한다'는 규칙이 아니라 과잉 완화의 증거)",
     "Lost Tree 2015 · Real Vision 2018 · ECNY 2019", "sources/lost-tree-club-2015"),
]


def build(ctx: Context) -> dict:
    gdp = to_freq(ctx.series("GDP"), "Q")
    y10m = to_freq(ctx.series("GS10"), "M")
    ffm = to_freq(ctx.series("FEDFUNDS"), "M")
    df = pd.DataFrame({"명목GDP 전년비": yoy_pct(gdp, 4), "10년물": to_freq(y10m, "Q"),
                       "기준금리": to_freq(ffm, "Q")}).dropna()
    df["10년물 − 명목성장"] = df["10년물"] - df["명목GDP 전년비"]
    df["기준금리 − 명목성장"] = df["기준금리"] - df["명목GDP 전년비"]
    t, row = df.index[-1], df.iloc[-1]
    y10, ff = float(y10m.iloc[-1]), float(ffm.iloc[-1])
    ng = float(row["명목GDP 전년비"])
    hist = df[df.index < "2008-01-01"]  # QE 이전(채권이 '조작되지 않던' 시기) 평균
    kpis = {
        f"명목GDP 전년비 ({fdate(t)})": fmt(ng, "%"),
        f"10년물 ({fdate(y10m.index[-1])})": fmt(y10, "%", 2),
        f"기준금리 ({fdate(ffm.index[-1])})": fmt(ff, "%", 2),
        "10년물 − 명목성장": fmt(y10 - ng, "%p", sign=True),
        "기준금리 − 명목성장": fmt(ff - ng, "%p", sign=True),
        "QE 이전 평균: 10년물 − 명목성장": fmt(float(hist["10년물 − 명목성장"].mean()), "%p", sign=True),
        "2003년 4분기 기준금리 − 명목성장": fmt(float(df.loc["2003-10":"2003-12", "기준금리 − 명목성장"].mean()), "%p", sign=True)
        if len(df.loc["2003-10":"2003-12"]) else "-",
    }
    charts = [
        Chart("명목GDP 성장률 vs 10년물 vs 기준금리", {
            "명목GDP 전년비": df["명목GDP 전년비"], "10년물": df["10년물"], "기준금리": df["기준금리"]},
            y_title="%", hlines=[(0, "")], years=None),
        Chart("10년물 − 명목성장 (그의 황금률: 0 근처)", {"10년물 − 명목성장": df["10년물 − 명목성장"]},
              kind="bar", y_title="%p", hlines=[(0, "")], years=None),
        Chart("기준금리 − 명목성장 (크게 마이너스 = 2003년형 과잉 완화)", {"기준금리 − 명목성장": df["기준금리 − 명목성장"]},
              kind="bar", y_title="%p", hlines=[(0, "")], years=None),
    ]
    return {"as_of": fdate(t), "kpis": kpis, "charts": charts, "factcheck": FACTCHECK}
