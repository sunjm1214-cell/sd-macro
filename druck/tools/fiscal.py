"""재정 지배(Fiscal dominance) — The Endgame의 계기판.

그의 주장들:
- 완전고용 상태에서 GDP 대비 5~7% 적자는 지속 불가능 (Norges 2023, Sohn 2023)
- 세수 대비 이자비용이 커지면 연준이 적자를 화폐화하라는 정치 압력을 받는다 (WSJ 2021)
- 2020년 위기 속 외국인의 미 국채 매도는 '전례 없는 경고' (WSJ 2021)
- 위기의 방아쇠는 '실패한 국채 입찰'일 가능성이 가장 높다 (Norges 2023)
"""
from __future__ import annotations

import pandas as pd

from ..core import Chart, Context, DataUnavailable, Signal, ToolResult
from ..registry import tool
from ..stats import fdate, fmt, to_billions, to_freq
from . import src


@tool(
    name="fiscal",
    title="재정 지배 (적자 · 이자비용 · 외국인 수요)",
    concept="The Endgame · 세대 간 도둑질",
    rule="호황·완전고용에서도 큰 적자를 내고 이자비용이 세수를 잠식하면, 결국 연준이 화폐화 압력을 받는다.",
    sources=[src("WSJ 2021 The Fed Is Playing With Fire", "sources/wsj-fed-playing-with-fire-2021"),
             src("USC 2023 (재정 격차)", "sources/usc-us-exceptionalism-2023"),
             src("Norges Bank 2023 (완전고용 7% 적자, 신뢰 붕괴 방아쇠)", "sources/norges-bank-in-good-company-2023"),
             src("Economic Club of NY 2019 (완전고용 속 대규모 적자는 처음)", "sources/economic-club-ny-2019"),
             src("Ira Sohn 2023 (호황기에 총알을 다 썼다)", "sources/ira-sohn-2023-sokoloff"),
             src("Bloomberg Invest 2023 (이자 27%, 2040년 세수 초과)", "sources/bloomberg-invest-ny-2023")],
    order=30,
    series=["FYFSGDA188S", "UNRATE", "A091RC1Q027SBEA", "FGRECPT", "FGEXPND", "GFDEGDQ188S", "FDHBFIN", "GFDEBTN",
            "FEDFUNDS"],
    layer="누적 위험",
    use="배경",
    lead="수년 (그는 '3~6개월 단위로 다룰 문제가 아니다'라고 했다)",
)
def run(ctx: Context, deficit_alert: float = 5.0, full_employment_u: float = 4.5,
        interest_alert: float = 15.0) -> ToolResult:
    stress, metrics, notes, charts, tables = 0, {}, [], [], []
    lit = {"완전고용 대규모 적자": False, "이자 부담": False, "외국인 수요 이탈": False}
    as_of = None
    got = 0

    bal = ctx.try_series("FYFSGDA188S")
    u = ctx.try_series("UNRATE")
    if bal is not None:
        got += 1
        deficit = -bal  # 양수 = 적자
        deficit.index = deficit.index.year
        d_now, yr = float(deficit.iloc[-1]), int(deficit.index[-1])
        metrics["재정적자/GDP (회계연도 %d)" % yr] = fmt(d_now, "%")
        if u is not None:
            ua = u.groupby(u.index.year).mean()
            u_yr = float(ua.get(yr, ua.iloc[-1]))
            metrics["같은 해 평균 실업률"] = fmt(u_yr, "%")
            fe = pd.DataFrame({"적자/GDP": deficit, "실업률": ua}).dropna()
            fe_years = fe[(fe["실업률"] < full_employment_u) & (fe["적자/GDP"] > deficit_alert)]
            if d_now > deficit_alert and u_yr < full_employment_u:
                stress += 1
                lit["완전고용 대규모 적자"] = True
                notes.append(f"완전고용(실업률<{full_employment_u}%)인데 적자가 GDP의 {deficit_alert}%를 넘음 — 그가 '지속 불가능'이라 부른 조합.")
            hist = ", ".join(str(y) for y in fe_years.index) or "없음"
            metrics["'완전고용+대규모 적자' 해"] = hist
        charts.append(Chart("연방 재정적자 (GDP 대비, 양수=적자)", {"적자/GDP": pd.Series(
            deficit.to_numpy(), index=pd.to_datetime([f"{y}-09-30" for y in deficit.index]))},
            kind="bar", y_title="%", hlines=[(deficit_alert, "")]))
        as_of = str(yr)

    ip, rc = ctx.try_series("A091RC1Q027SBEA"), ctx.try_series("FGRECPT")
    if ip is not None and rc is not None:
        got += 1
        ratio = (to_freq(ip, "Q") / to_freq(rc, "Q") * 100).dropna()
        r_now = float(ratio.iloc[-1])
        r_3y = float(ratio.iloc[-13]) if len(ratio) > 12 else float("nan")
        metrics["이자비용/연방세수"] = fmt(r_now, "%")
        metrics["3년 전 대비"] = fmt(r_now - r_3y, "%p", sign=True)
        ex = ctx.try_series("FGEXPND")
        if ex is not None:
            ro = (to_freq(ip, "Q") / to_freq(ex, "Q") * 100).dropna()
            metrics["이자비용/연방지출"] = fmt(float(ro.iloc[-1]), "%")
            notes.append(f"이자비용은 지출의 {float(ro.iloc[-1]):.0f}%. 그가 인용한 CBO 전망: 2050년 27%, 엔타이틀먼트+이자가 2040년엔 세수 전체를 넘는다(Bloomberg Invest 2023).")
        if r_now > interest_alert or (r_now - r_3y) > 3:
            stress += 1
            lit["이자 부담"] = True
        charts.append(Chart("연방 이자비용 / 연방 경상수입", {"이자/세수": ratio}, y_title="%",
                            hlines=[(interest_alert, "")]))
        as_of = fdate(ratio.index[-1])

    debt = ctx.try_series("GFDEGDQ188S")
    if debt is not None:
        got += 1
        metrics["연방부채/GDP"] = fmt(float(debt.iloc[-1]), "%", 0)

    fh, tot = ctx.try_series("FDHBFIN"), ctx.try_series("GFDEBTN")
    if fh is not None and tot is not None:
        got += 1
        fhb = to_billions(to_freq(fh, "Q"), 500, 15000)
        totb = to_billions(to_freq(tot, "Q"), 5000, 60000)
        share = (fhb / totb * 100).dropna()
        s_now = float(share.iloc[-1])
        s_3y = float(share.iloc[-13]) if len(share) > 12 else float("nan")
        metrics["외국인 보유 비중"] = fmt(s_now, "%")
        metrics["외국인 비중 3년 변화"] = fmt(s_now - s_3y, "%p", sign=True)
        if s_now - s_3y < -2:
            stress += 1
            lit["외국인 수요 이탈"] = True
        charts.append(Chart("외국인·국제기관의 미 국채 보유 비중", {"외국인 비중": share}, y_title="%"))

    if got == 0:
        raise DataUnavailable("재정 데이터 전부 없음")

    # 정책 여력 — "통화·재정 총알을 호황기에 다 써버렸다" (Sohn 2023)
    ffs = ctx.try_series("FEDFUNDS")
    if ffs is not None:
        ff_now = float(to_freq(ffs, "M").iloc[-1])
        metrics["기준금리 (인하 여력)"] = fmt(ff_now, "%", 2)
        dnow = metrics.get(next((k for k in metrics if k.startswith("재정적자/GDP")), ""), None)
        notes.append(f"정책 여력: 과거 침체마다 연준은 보통 5%p 안팎을 내렸습니다. 지금 기준금리 {ff_now:.2f}%"
                     + (f", 적자는 이미 GDP의 {dnow}" if dnow else "") + " — 그가 말한 '총알을 호황기에 다 써버린' 상태인지 보세요.")

    sig = Signal.ALERT if stress >= 2 else (Signal.WATCH if stress == 1 else Signal.OK)
    msg = {0: "재정 스트레스 신호 없음", 1: "재정 스트레스 1개 점등", 2: "재정 스트레스 다수 점등 — 엔드게임 압력"}[min(stress, 2)]
    headline = f"{msg} ({stress}/3) — " + " · ".join(("●" if v else "○") + " " + k for k, v in lit.items())
    notes.append("이 툴은 시점(timing) 신호가 아닙니다. 신뢰가 깨지는 방아쇠로 그가 꼽은 것: ① 실패한 국채 입찰 ② 연준이 틀려 인플레이션이 다시 오르는 것 ③ 코로나 때 낮춰둔 기업부채·모기지의 2025~26년 차환(Norges 2023) ④ 위기 중 외국인의 국채 매도(WSJ 2021). 이 툴은 ④만 데이터로 봅니다.")
    return ToolResult(sig, headline, metrics, notes, tables, charts, as_of=as_of)
