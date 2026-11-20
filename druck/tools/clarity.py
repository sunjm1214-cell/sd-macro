"""명확성 점검 — '크게 걸 때'와 '안 할 때'를 가르는 체크리스트.

TomorrowX Summit 2026 (iConnections, Morgan Stanley 일리아나 부잘리 진행):
그는 2026년 1월엔 경기·주식에 크게 걸었고, 11월엔 "50년 동안 12개월 뒤가 이렇게 안 보인 적이 없다"며
"I'm not playing(안 한다)" — 자본 보존 모드라고 했다. 두 시점을 가른 것은 같은 체크리스트의 방향이었다.

  1월(명확, 확장)                         →  11월(전부 뒤집힘)
  - 기준금리 3.5% < 명목성장 → '터무니없이 완화'  →  연준이 인하가 아니라 인상 (연준 체제 교체)
  - 점도표상 인하 예정                        →  긴축 진행
  - 원자재·구리 신고가 돌파                    →  천장 찍고 하락, 구리는 숏
  - 상승·하락 종목 수(A/D) 선 신고가            →  A/D 선은 8/14 고점, 지수는 10월 고점 (다이버전스)
  - 신용 스프레드 매우 타이트                   →  스프레드 확대
  - 경기민감주가 방어주를 앞섬                  →  방어주가 주도
  → "6~12개월 안에 침체는 거의 불가능"           →  "27년 하반기 경기가 실망스러울 수 있다"

원칙: 명확할 때 크게, 명확하지 않으면 거의 안 한다. 그래도 그는 AI 혁신과 이미 씻겨 나간 포지션 때문에
"감히 숏은 못 한다"고 했다 — 신호가 반대로 정렬돼도 이 툴은 '공매도'가 아니라 '비중 축소·관망'의 근거로 쓴다.

화면은 '1월과 비교'가 아니라 지금 상태를 보여준다: 각 항목의 현재 판정·근거 수치와 '확장 쪽이 되려면' 기준.
원자재는 구리 하나가 아니라 원자재 종합·구리·원유 바스켓으로 본다 (그는 구리만이 아니라 원자재 전반을 봤다).
데이터: 기준금리는 일별 목표금리(DFEDTARU), 시장 기대는 2년물(DGS2), Baa 스프레드도 일별. 명목 GDP만 분기.
"""
from __future__ import annotations

import pandas as pd

from ..core import Context, DataUnavailable, Signal, ToolResult
from ..registry import tool
from ..stats import fmt, percentile_rank, to_freq, yoy_pct
from .sector_leadership import CYCLICALS, DEFENSIVES

VIDEO = "https://www.youtube.com/watch?v=6r3D-CMJkuI"
UP, DOWN, MID = "확장 쪽", "수축 쪽", "중립"


def _basket(ctx: Context, tickers) -> pd.Series:
    parts = []
    for tk in tickers:
        try:
            p = ctx.price(tk)
            parts.append(p / p.iloc[0])
        except DataUnavailable:
            pass
    if not parts:
        raise DataUnavailable("바스켓 가격 없음")
    return pd.concat(parts, axis=1).dropna().mean(axis=1)


@tool(
    name="clarity",
    title="명확성 점검 (크게 걸 때 vs 안 할 때)",
    concept="명확할 때 크게 · 자본 보존",
    rule="연준 완화·원자재 돌파·시장 폭 신고가·타이트한 신용·경기민감주 주도가 한 방향으로 정렬되면 크게 건다. "
         "이것들이 엇갈리거나 뒤집히면 '안 한다' — 돈을 버는 것보다 잃지 않는 것이 목표가 된다.",
    sources=[("TomorrowX Summit 2026 — 'I'm not playing' (1월 vs 지금 체크리스트)", VIDEO)],
    order=0,
    series=["GDP", "DFEDTARU", "FEDFUNDS", "DGS2", "BAA10Y", "BAMLH0A0HYM2"],
    layer="유동성·연준",
    use="사이즈",
    lead="6~12개월",
    tickers=["HG=F", "CPER", "CL=F", "USO", "DBC", "RSP", "SPY", *CYCLICALS, *DEFENSIVES],
)
def run(ctx: Context, loose_gap: float = 1.5, fed_move: float = 0.25, fed_months: int = 6, fed_turn: float = 0.1,
        cu_near_high: float = -5.0, cu_topped: float = -12.0, breadth_off_high: float = -4.0, breadth_lag_days: int = 30,
        spread_tight_pct: float = 30.0, spread_widen: float = 0.3, hy_widen: float = 0.4, rel_months: int = 6,
        rel_band: float = 3.0, clear_share: float = 0.8, mkt_gap: float = 0.25, y2_move: float = 0.3) -> ToolResult:
    rows: list[dict] = []

    def add(item, now, need, state, value):
        rows.append({"항목": item, "지금 상태": state, "근거 수치": value, "확장 쪽이 되려면": need, "_s": now})

    # 기준금리: 일별 목표금리 상단(DFEDTARU) — 결정 다음 날 반영. 없으면 월평균 FEDFUNDS
    rate = ctx.try_series("DFEDTARU")
    rate_name = "목표금리 상단"
    if rate is None or len(rate) < 300:
        rate, rate_name = ctx.try_series("FEDFUNDS"), "실효 기준금리(월평균)"

    def ago(sr, days):
        old = sr[sr.index <= sr.index[-1] - pd.Timedelta(days=days)]
        return float(old.iloc[-1]) if len(old) else float(sr.iloc[0])

    # 1) 통화정책 수준: 기준금리 vs 명목성장 ("기준금리 3.5%, 명목성장은 그보다 높다 → 터무니없이 완화")
    try:
        if rate is None:
            raise DataUnavailable("기준금리 없음")
        g = yoy_pct(ctx.series("GDP"), 4).dropna()
        ngdp, ff = float(g.iloc[-1]), float(rate.iloc[-1])
        q = pd.Timestamp(g.index[-1])
        gap = ngdp - ff
        s = UP if gap >= loose_gap else (DOWN if gap <= 0 else MID)
        add("통화정책 수준 (명목성장 − 기준금리)", s, f"명목성장이 기준금리보다 {loose_gap:.1f}%p 이상 높음",
            {UP: "완화적", DOWN: "긴축적", MID: "중립 근처"}[s],
            f"명목성장 {ngdp:.1f}%({q.year}년 {q.quarter}분기) − {rate_name} {ff:.2f}% = {gap:+.1f}%p")
        # 2) 연준 방향 — 실제 결정 ("연준이 인하가 아니라 인상 중")
        chg, chg3 = ff - ago(rate, fed_months * 30), ff - ago(rate, 91)
        s = UP if chg <= -fed_move else (DOWN if chg >= fed_move else MID)
        label = {UP: "인하 중", DOWN: "인상 중", MID: "동결"}[s]
        # 전환은 6개월 합계보다 먼저 보인다: 인하 뒤 최근 3개월에 인상이 나오면 '인상 전환'(2026-11 그가 물러선 첫 이유)
        if s != DOWN and chg3 >= fed_turn:
            s, label = DOWN, "인상 전환"
        elif s != UP and chg3 <= -fed_turn:
            s, label = UP, "인하 전환"
        add("연준 방향 (실제 결정)", s, "인하 중이거나 인하로 전환", label,
            f"{rate_name} 지금 {ff:.2f}% · 6개월 {chg:+.2f}%p · 3개월 {chg3:+.2f}%p")
    except DataUnavailable as e:
        add("통화정책", None, "-", "데이터 없음", str(e))

    # 2-b) 시장의 연준 기대 — 2년물 ("점도표상 인하 예정" → 지금은 시장이 무엇을 가격에 넣었나)
    try:
        y2 = ctx.series("DGS2").dropna()
        if rate is None:
            raise DataUnavailable("기준금리 없음")
        now2, ff = float(y2.iloc[-1]), float(rate.iloc[-1])
        spread, d2 = now2 - ff, now2 - ago(y2, 91)
        if spread <= -mkt_gap and d2 <= 0:
            s, label = UP, "인하를 가격에 반영"
        elif spread >= mkt_gap or d2 >= y2_move:
            s, label = DOWN, "인상(또는 인하 축소)을 가격에 반영"
        else:
            s, label = MID, "동결 근처"
        add("시장의 연준 기대 (2년물)", s, "2년물이 기준금리보다 낮고 내려가는 중", label,
            f"2년물 {now2:.2f}% − 기준금리 {ff:.2f}% = {spread:+.2f}%p · 2년물 3개월 {d2 * 100:+.0f}bp")
    except DataUnavailable as e:
        add("시장의 연준 기대", None, "-", "데이터 없음", str(e))

    # 3) 원자재 — 구리 하나가 아니라 바스켓 ("원자재·구리 신고가 돌파 → 천장 찍고 하락")
    comms = []
    for name, tks in (("원자재 종합", ["DBC"]), ("구리", ["HG=F", "CPER"]), ("원유", ["CL=F", "USO"])):
        for tk in tks:
            try:
                px = ctx.price(tk).dropna()
                if len(px) < 252:
                    continue
                off = float((px.iloc[-1] / px.iloc[-252:].max() - 1) * 100)
                above = bool(px.iloc[-1] > px.iloc[-200:].mean())
                st = UP if (off >= cu_near_high and above) else (DOWN if (off <= cu_topped or not above) else MID)
                comms.append((name, st, off, above))
                break
            except DataUnavailable:
                continue
    if comms:
        ups = sum(c[1] == UP for c in comms)
        downs = sum(c[1] == DOWN for c in comms)
        s = UP if ups > len(comms) / 2 else (DOWN if downs > len(comms) / 2 else MID)
        detail = " · ".join(f"{n} 고점 대비 {o:+.1f}%({'200일선 위' if a_ else '200일선 아래'})" for n, _, o, a_ in comms)
        add("원자재 (종합·구리·원유)", s, f"과반이 52주 고점 {cu_near_high:.0f}% 이내 + 200일선 위",
            {UP: f"상승 추세 ({ups}/{len(comms)})", DOWN: f"고점 대비 하락 · 추세 이탈 ({downs}/{len(comms)})", MID: "엇갈림"}[s],
            detail)
    else:
        add("원자재", None, "-", "데이터 없음", "원자재 가격을 받지 못함")

    # 4) 시장 폭 — A/D 선 대용: 동일가중 S&P(RSP)가 지수와 함께 고점을 만드는가, 먼저 꺾였나
    #    (RSP÷SPY 비율 '수준'은 대형주 집중으로 수년째 구조적으로 내려 다이버전스를 과다 판정 → 고점 '시점'으로 본다)
    try:
        rsp, spy = ctx.price("RSP"), ctx.price("SPY")
        rw, sw = rsp.iloc[-252:], spy.iloc[-252:]
        r_off = float((rsp.iloc[-1] / rw.max() - 1) * 100)
        spy_off = float((spy.iloc[-1] / sw.max() - 1) * 100)
        lag = int(sw.index.get_loc(sw.idxmax()) - rw.index.get_loc(rw.idxmax()))  # 폭 고점이 지수 고점보다 며칠 먼저
        if spy_off >= -3 and lag >= breadth_lag_days and r_off <= -1.5:
            s, txt = DOWN, f"폭이 먼저 꺾임 — 동일가중 고점 {rw.idxmax():%m/%d} vs 지수 고점 {sw.idxmax():%m/%d}(다이버전스)"
        elif r_off <= breadth_off_high * 2:
            s, txt = DOWN, "폭넓은 하락"
        elif r_off >= -2:
            s, txt = UP, "폭이 지수를 확인(동일가중도 고점권)"
        else:
            s, txt = MID, "애매"
        add("시장 폭 (A/D 선 대용: 동일가중 S&P 고점 시점)", s, "동일가중 S&P도 지수와 함께 고점권", txt,
            f"동일가중 52주 고점 대비 {r_off:+.1f}%({rw.idxmax():%Y-%m-%d}), S&P 500 {spy_off:+.1f}%({sw.idxmax():%Y-%m-%d})")
    except DataUnavailable as e:
        add("시장 폭", None, "-", "데이터 없음", str(e))

    # 5) 신용 스프레드 ("매우 타이트 → 확대 중")
    #    수준(얼마나 좁은가)은 긴 역사가 있는 Baa−10년물로, 방향(넓어지는가)은 더 민감한 하이일드로 본다.
    #    국채 금리가 크게 오르면 Baa−10년물은 좁아 보이는데 정크본드 쪽은 이미 벌어질 수 있다(2026년 8~11월).
    try:
        sp = ctx.series("BAA10Y").dropna()
        now = float(sp.iloc[-1])
        pct = percentile_rank(to_freq(sp, "M").iloc[-240:], now)
        d3 = now - ago(sp, 91)
        hy_txt, hy_wide = "", False
        hy = ctx.try_series("BAMLH0A0HYM2")
        if hy is not None and len(hy) > 70:
            h3 = float(hy.iloc[-1] - hy[hy.index <= hy.index[-1] - pd.Timedelta(days=91)].iloc[-1])
            hy_wide = h3 >= hy_widen
            hy_txt = f", 하이일드 {float(hy.iloc[-1]):.2f}%p(3개월 {h3 * 100:+.0f}bp)"
        widening = d3 >= spread_widen or hy_wide
        s = DOWN if widening else (UP if pct <= spread_tight_pct else MID)
        label = {UP: "타이트", DOWN: "확대 중" + (" — 하이일드부터" if hy_wide and d3 < spread_widen else ""), MID: "보통"}[s]
        add("신용 스프레드 (Baa − 10년물 · 하이일드)", s, f"20년 중 하위 {spread_tight_pct:.0f}% 분위 + 넓어지지 않음", label,
            f"Baa {now:.2f}%p, 20년 중 {pct:.0f}% 분위, 3개월 {d3:+.2f}%p{hy_txt}")
    except DataUnavailable as e:
        add("신용 스프레드", None, "-", "데이터 없음", str(e))

    # 6) 경기민감 vs 방어 ("1년 전엔 경기민감주가 앞섰는데 지금은 방어주가 전부 주도")
    try:
        cyc, dfn = _basket(ctx, CYCLICALS), _basket(ctx, DEFENSIVES)
        rel = (cyc / dfn).dropna()
        days = rel_months * 21
        rr = float((rel.iloc[-1] / rel.iloc[-1 - days] - 1) * 100)
        s = UP if rr >= rel_band else (DOWN if rr <= -rel_band else MID)
        add("주도주 (경기민감 vs 방어)", s, f"경기민감주가 {rel_months}개월간 방어주보다 {rel_band:.0f}%p 이상 앞섬", {UP: "경기민감주 우위", DOWN: "방어주 주도", MID: "비슷"}[s],
            f"경기민감 바스켓의 방어주 대비 {rel_months}개월 {rr:+.1f}%p")
    except DataUnavailable as e:
        add("주도주", None, "-", "데이터 없음", str(e))

    have = [x for x in rows if x["_s"] is not None]
    if len(have) < 3:
        raise DataUnavailable("판정 가능한 항목이 3개 미만")
    up = sum(x["_s"] == UP for x in have)
    down = sum(x["_s"] == DOWN for x in have)
    n = len(have)
    if up >= clear_share * n and down == 0:
        sig = Signal.OK
        msg = "명확함 — 확장 쪽으로 정렬. 그가 '크게 걸던' 국면(2026년 1월이 이랬다)"
    elif down >= clear_share * n and up == 0:
        sig = Signal.ALERT
        msg = "체크리스트가 전부 반대로 뒤집힘 — 그는 이때도 숏 대신 '쉬기(자본 보존)'를 택했다"
    else:
        sig = Signal.WATCH
        msg = "명확성 낮음 — 신호가 엇갈림. 그의 말로 'I'm not playing': 작게 치고(번트) 기다릴 때"
    headline = f"{n}개 항목 중 확장 쪽 {up}개 · 수축 쪽 {down}개 · 중립 {n - up - down}개 → {msg}"
    metrics = {"확장 쪽": f"{up}/{n}", "수축 쪽": f"{down}/{n}", "명확성": f"{abs(up - down) / n * 100:.0f}%",
               "그의 대응": {Signal.OK: "크게 건다", Signal.ALERT: "비중 축소 · 관망", Signal.WATCH: "작게 · 관망"}[sig]}
    table = pd.DataFrame([{k: v for k, v in x.items() if k != "_s"} for x in rows])
    notes = [
        "명확성 = |확장 쪽 − 수축 쪽| ÷ 항목 수. 그는 명확할 때만 크게 걸었고, 명확하지 않으면 '거의 안 한다'고 했습니다. 이 툴은 방향보다 '얼마나 걸 것인가(사이즈)'를 위한 것입니다.",
        "A/D 선(상승·하락 종목 수 누적)은 무료 데이터가 없어 동일가중 S&P(RSP)로 대신합니다. 비율(RSP÷SPY)의 수준은 대형주 집중 때문에 수년째 구조적으로 내려가 다이버전스를 과다 판정하므로, 동일가중의 52주 고점이 지수 고점보다 30거래일 이상 먼저 나왔는지(그가 말한 'A/D 고점 8/14 vs 지수 고점 10월')로 봅니다.",
        "체크리스트가 전부 반대로 뒤집혀도 그는 공매도하지 않았습니다 — AI 혁신과 이미 씻겨 나간 포지션 때문. 경고는 '숏 신호'가 아니라 '자본 보존' 신호로 읽으세요.",
        "그의 리스크 관리는 VaR가 아니라 자기 손익(P&L): 포지션이 기대대로 움직이지 않거나 상관관계가 깨지면 줄인다. 이 체크리스트와 함께 내 계좌의 움직임을 보세요.",
        "데이터 시점: 원자재·시장 폭·주도주·신용·금리는 전날 미국 종가(매일 아침 갱신). 명목 GDP만 분기 데이터라 최대 3~4개월 늦습니다.",
        "판정 기준값(명목성장−기준금리 1.5%p, 원자재 고점 대비 −12%, 2년물−기준금리 ±0.25%p 등)은 이 툴의 해석이며 그가 말한 숫자가 아닙니다. --param clarity.○○=값 으로 바꿀 수 있습니다.",
    ]
    try:
        as_of = pd.Timestamp(ctx.price("SPY").index[-1]).strftime("%Y-%m-%d")
    except DataUnavailable:
        as_of = None
    return ToolResult(sig, headline, metrics, notes, [("체크리스트: 지금 상태", table)], [], as_of=as_of,
                      data={"rows": rows, "up": up, "down": down, "n": n})
