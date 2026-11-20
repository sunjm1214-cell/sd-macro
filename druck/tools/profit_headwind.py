"""이익 역풍 모델 — 금리·유가·달러가 향후 기업이익에 주는 영향.

2000년 노동절, SD는 유가·금리·달러가 동시에 오르는데 주가가 버티는 걸 보고
Ed Hyman에게 물었다. 하이먼의 회귀(통화 50%·유가 25%·금리 25% 가중)는 향후 1년 이익
-35%를 가리켰고 월가 컨센서스는 +18%였다. 그는 국채를 펀드의 350% 규모로 사서
4분기에만 40%를 벌었다.

원문을 다시 보면 그는 회귀만 본 게 아니다: 거래처 소상공인들의 '장사가 안 된다'는 일화와 그린스펀의 긴축 기조를
함께 봤고, 거래는 '연준이 결국 돌아선다'에 건 국채 매수였다(Sohn 2022, Norges 2023, USC 2023).

이 툴은 그 분석을 두 가지 방식으로 재현한다.
 1) 하이먼 가중 역풍지수: 세 변수의 전년비 변화를 표준화해 50/25/25로 가중 합산
 2) 회귀 모델: 향후 h분기 기업이익 증가율 ~ 달러·유가 전년비 % + 금리 전년비 변화(%p)
    (겹치는 관측치이므로 Newey-West 표준오차, 확장창 표본외 검증 포함)
그리고 시나리오(유가 +30%, 달러 +10%, 금리 +1%p 등)를 넣으면 이익 변화를 추정한다.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from ..core import Chart, Context, DataUnavailable, Signal, ToolResult
from ..registry import tool
from ..stats import diff, fdate, fmt, ols, predict, to_freq, yoy_pct, zscore
from . import src

FACTORS = ["달러(%)", "유가(%)", "금리(%p)"]
HYMAN_W = {"달러(%)": 0.50, "유가(%)": 0.25, "금리(%p)": 0.25}


def dollar_index(ctx: Context) -> pd.Series:
    """광의 달러지수 월간. 2006년 이전은 단종된 TWEXBMTH를 비율로 이어 붙인다."""
    new = ctx.try_series("DTWEXBGS")
    old = ctx.try_series("TWEXBMTH")
    if new is None and old is None:
        raise DataUnavailable("달러지수(DTWEXBGS/TWEXBMTH) 없음")
    if new is None:
        return to_freq(old, "M")
    new_m = to_freq(new, "M")
    if old is None:
        return new_m
    old_m = to_freq(old, "M")
    overlap = new_m.index.intersection(old_m.index)
    if len(overlap) < 6:
        return new_m
    ratio = (new_m[overlap] / old_m[overlap]).mean()
    early = old_m[old_m.index < new_m.index[0]] * ratio
    return pd.concat([early, new_m]).sort_index()


def build_frame(ctx: Context, rate_series: str, horizon_q: int, start: str) -> pd.DataFrame:
    profits = to_freq(ctx.series("CP"), "Q")
    oil = to_freq(ctx.series("WTISPLC"), "Q")
    usd = to_freq(dollar_index(ctx), "Q")
    rate = to_freq(ctx.series(rate_series), "Q")
    df = pd.DataFrame({
        "이익": profits,
        "달러(%)": yoy_pct(usd, 4),
        "유가(%)": yoy_pct(oil, 4),
        "금리(%p)": diff(rate, 4),
    })
    df["향후이익(%)"] = (df["이익"].shift(-horizon_q) / df["이익"] - 1) * 100
    df["과거이익(%)"] = yoy_pct(df["이익"], 4)
    return df[df.index >= pd.Timestamp(start)]


def fit_model(df: pd.DataFrame, horizon_q: int) -> dict:
    return ols(df["향후이익(%)"], df[FACTORS], nw_lags=horizon_q)


def out_of_sample(df: pd.DataFrame, horizon_q: int, min_obs: int = 60) -> pd.Series:
    """확장창: t 시점에는 t-h까지 실현된 타깃만으로 적합 → t의 예측. 미래 정보 누출 없음."""
    data = df.dropna(subset=FACTORS)
    preds = {}
    for i, t in enumerate(data.index):
        train = data.iloc[: max(0, i - horizon_q + 1)].dropna(subset=["향후이익(%)"])
        if len(train) < min_obs:
            continue
        try:
            fit = ols(train["향후이익(%)"], train[FACTORS])
        except (ValueError, np.linalg.LinAlgError):
            continue
        preds[t] = predict(fit, data.loc[t, FACTORS])
    return pd.Series(preds, dtype=float)


def scenario(fit: dict, dollar_pct=0.0, oil_pct=0.0, rate_pp=0.0) -> dict:
    x = {"달러(%)": dollar_pct, "유가(%)": oil_pct, "금리(%p)": rate_pp}
    contrib = {k: float(fit["coef"][k] * v) for k, v in x.items()}
    return {"예측": predict(fit, x), "기여": contrib, "상수": float(fit["coef"]["상수"])}


@tool(
    name="profit_headwind",
    title="이익 역풍 모델 (금리·유가·달러 → 기업이익)",
    concept="18개월 룰 · 유동성 > 실적",
    rule="유가·금리·달러가 함께 오르면 '앞으로의 기업이익에 언제나 끔찍했다'. 모델과 월가 컨센서스의 괴리가 크고 연준이 긴축 중이면, 연준이 결국 돌아선다에 건다.",
    sources=[src("Ira Sohn 2022 (2000년 하이먼 회귀 일화)", "sources/ira-sohn-2022-collison"),
             src("Norges Bank 2023 (가중 50/25/25, −36% vs +18%)", "sources/norges-bank-in-good-company-2023"),
             src("USC 2023 (같은 일화, 국채 350%)", "sources/usc-us-exceptionalism-2023")],
    order=20,
    series=["CP", "WTISPLC", "DTWEXBGS", "TWEXBMTH", "GS10", "FEDFUNDS"],
    layer="주식·이익",
    use="타이밍",
    lead="4분기 (모델 지평)",
)
def run(ctx: Context, horizon_q: int = 4, rate_series: str = "GS10", start: str = "1975-01-01",
        scenario_dollar_pct: float | None = None, scenario_oil_pct: float | None = None,
        scenario_rate_pp: float | None = None, consensus_pct: float | None = None) -> ToolResult:
    df = build_frame(ctx, rate_series, horizon_q, start)
    fit = fit_model(df, horizon_q)

    feats = df[FACTORS].dropna()
    t_now = feats.index[-1]
    x_now = feats.iloc[-1]
    pred_now = predict(fit, x_now)

    # 하이먼 가중 역풍지수 (+ = 이익에 역풍)
    z = pd.DataFrame({k: zscore(feats[k]) for k in FACTORS})
    headwind = sum(z[k] * w for k, w in HYMAN_W.items())
    triple = (feats > 0).all(axis=1)
    hw_now = float(headwind.iloc[-1])

    oos = out_of_sample(df, horizon_q)
    actual = df["향후이익(%)"]
    both = pd.concat([oos.rename("p"), actual.rename("a")], axis=1).dropna()
    oos_r2 = float("nan")
    if len(both) > 20:
        bench = df["향후이익(%)"].expanding().mean().shift(horizon_q).reindex(both.index)
        sse_m = ((both["a"] - both["p"]) ** 2).sum()
        sse_b = ((both["a"] - bench) ** 2).sum()
        oos_r2 = float(1 - sse_m / sse_b) if sse_b > 0 else float("nan")

    # 연준 방향 — 2000년엔 '긴축 기조'가 역풍과 겹쳐 있었다
    ff6 = float("nan")
    ffs = ctx.try_series("FEDFUNDS")
    if ffs is not None:
        ffm = to_freq(ffs, "M")
        ff6 = float(diff(ffm, 6).dropna().iloc[-1]) if len(ffm) > 7 else float("nan")
    fed_tight = ff6 > 0.2

    # 신호
    if (triple.iloc[-1] and hw_now > 0.75) or pred_now < -10:
        sig = Signal.ALERT
    elif hw_now > 0.5 or pred_now < 0 or (triple.iloc[-1] and fed_tight):
        sig = Signal.WATCH
    else:
        sig = Signal.OK
    weak_model = not (oos_r2 > 0)
    if weak_model and sig == Signal.ALERT and consensus_pct is None:
        sig = Signal.WATCH  # 표본외 예측력이 없으면 모델 단독으로 경고하지 않는다

    headline = (f"현재 조합(달러 {fmt(x_now['달러(%)'], '%', sign=True)}, 유가 {fmt(x_now['유가(%)'], '%', sign=True)}, "
                f"금리 {fmt(x_now['금리(%p)'], '%p', 2, sign=True)})이면 향후 {horizon_q}분기 기업이익 "
                f"{fmt(pred_now, '%', sign=True)} 추정. 역풍지수 {fmt(hw_now, '', 2, sign=True)}"
                + (" — 세 변수 동시 상승(트리플 역풍)" if triple.iloc[-1] else ""))

    metrics = {
        "기준 분기": fdate(t_now),
        f"모델 예측: 향후 {horizon_q}분기 이익": fmt(pred_now, "%", sign=True),
        "하이먼 역풍지수(z)": fmt(hw_now, "", 2, sign=True),
        "트리플 역풍": "예" if triple.iloc[-1] else "아니오",
        "직전 4분기 실제 이익": fmt(df["과거이익(%)"].dropna().iloc[-1], "%", sign=True),
        "표본내 R²": fmt(fit["r2"], "", 2),
        "표본외 R² (확장창)": fmt(oos_r2, "", 2),
        "기준금리 6개월 변화": fmt(ff6, "%p", 2, sign=True),
    }
    notes = [
        "역풍지수는 세 변수의 전년비 변화를 전 기간 기준으로 표준화한 뒤 달러 50%·유가 25%·금리 25%로 가중 합산한 값입니다. +1 이상이면 역사적으로 강한 역풍.",
        "회귀 계수는 '변수가 1단위 변할 때 향후 이익 증가율이 몇 %p 변하는가'입니다. 기간이 겹치는 관측치라 t값은 Newey-West로 보정했습니다.",
        "표본외 R²가 0 이하면 이 단순 모델은 '역사 평균'보다 나을 게 없다는 뜻입니다. 이때는 모델만으로 경고를 내지 않습니다. SD도 이 회귀를 단독 신호가 아니라 컨센서스와의 괴리를 찾는 도구로, 거래처 일화·연준 기조와 함께 썼습니다.",
        "2000년의 조합: 세 변수 동시 상승 + 연준 긴축 기조 + 체감 경기 악화 → 그는 주식 숏이 아니라 '연준이 돌아선다'에 건 국채 매수로 표현했습니다(4분기 +40%).",
    ]
    if triple.iloc[-1] and fed_tight:
        notes.insert(0, "지금은 세 변수 동시 상승에 연준까지 긴축 중 — 2000년 노동절과 같은 구조입니다.")

    if consensus_pct is not None:
        gap = pred_now - consensus_pct
        metrics["컨센서스 대비 괴리"] = fmt(gap, "%p", sign=True)
        notes.insert(0, f"컨센서스 {fmt(consensus_pct, '%', sign=True)} vs 모델 {fmt(pred_now, '%', sign=True)} → "
                        f"괴리 {fmt(gap, '%p', sign=True)}. (2000년: 모델 −35% vs 월가 +18%, 괴리 −53%p)")
        if gap < -20:
            sig = Signal.ALERT

    tables = []
    coef_tbl = pd.DataFrame({
        "계수": fit["coef"].round(3),
        "t값(NW)": fit["t"].round(2),
        "현재 입력": pd.Series({"상수": 1.0, **x_now.to_dict()}).round(2),
    })
    coef_tbl["현재 기여(%p)"] = (coef_tbl["계수"] * coef_tbl["현재 입력"]).round(1)
    tables.append((f"회귀: 향후 {horizon_q}분기 이익 증가율 (n={fit['nobs']}, {fdate(df.index[0])}~)", coef_tbl))

    scen = {}
    if any(v is not None for v in (scenario_dollar_pct, scenario_oil_pct, scenario_rate_pp)):
        sc = scenario(fit, scenario_dollar_pct or 0.0, scenario_oil_pct or 0.0, scenario_rate_pp or 0.0)
        scen = sc
        rows = {
            "달러 변화": [fmt(scenario_dollar_pct or 0, "%", sign=True), fmt(sc["기여"]["달러(%)"], "%p", sign=True)],
            "유가 변화": [fmt(scenario_oil_pct or 0, "%", sign=True), fmt(sc["기여"]["유가(%)"], "%p", sign=True)],
            "금리 변화": [fmt(scenario_rate_pp or 0, "%p", 2, sign=True), fmt(sc["기여"]["금리(%p)"], "%p", sign=True)],
            "상수(평균 성장)": ["", fmt(sc["상수"], "%p", sign=True)],
            "예상 이익 변화": ["", fmt(sc["예측"], "%", sign=True)],
        }
        tables.insert(0, ("시나리오 결과", pd.DataFrame(rows, index=["입력", "이익 기여"]).T))
        metrics["시나리오 예측"] = fmt(sc["예측"], "%", sign=True)

    # 트리플 역풍 과거 구간
    from ..stats import episodes
    eps = episodes(triple, min_len=2, merge_gap=1)
    if eps:
        rows = []
        for s, e in eps:
            fwd = actual.get(s, np.nan)
            rows.append({"시작": fdate(s), "끝": fdate(e), "시작 시점 이후 실제 이익": fmt(fwd, "%", sign=True)})
        tables.append(("트리플 역풍(달러·유가·금리 동시 상승, 2분기 이상) 과거 구간", pd.DataFrame(rows)))

    charts = [
        Chart("향후 이익 증가율: 실제 vs 모델", {
            "실제(향후 %d분기)" % horizon_q: actual.dropna(),
            "표본내 적합": fit["fitted"],
            "표본외 예측": oos,
        }, y_title="%", hlines=[(0, "")]),
        Chart("하이먼 역풍지수 (+ = 이익 역풍)", {"역풍지수": headwind}, kind="bar", y_title="z",
              hlines=[(1, "강한 역풍"), (-1, "")]),
    ]
    return ToolResult(sig, headline, metrics, notes, tables, charts, as_of=fdate(t_now),
                      data={"fit": fit, "frame": df, "scenario": scen, "pred_now": pred_now})
