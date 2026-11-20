"""시장 폭 — 상승·하락 종목 수 누적선(ADL, Advance-Decline Line).

SD(2026-11 TomorrowX): "A/D 선 고점은 8/14인데 지수 고점은 10월" — 지수는 신고가인데 오르는 종목 수가 줄어드는
다이버전스가 그가 물러선 이유 중 하나였다. 무료 A/D 데이터가 없어서 구성 종목 종가로 직접 계산한다.

  - S&P 500: 위키피디아 구성 종목 목록 → 야후 종가 → 매일 (상승 종목 수 − 하락 종목 수) 누적
  - 나스닥: 나스닥 종합(3,000여 종목)은 너무 많아 나스닥 100 구성 종목으로 계산
  - 덤: 200일선 위 종목 비율 (폭의 '수준')

주의: 지금 구성 종목으로 과거까지 계산하므로(생존 편향) 오래된 구간일수록 실제 ADL과 다릅니다. 그래서 2년만 본다.
"""
from __future__ import annotations

import html
import io
import math
import urllib.request

import numpy as np
import pandas as pd

UP, DN, ADL_C = "#d64545", "#2f6fdb", "#e0a020"
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36 sd-macro"
INDEXES = [
    # key, 이름, 지수 티커, 구성 종목 위키 주소
    ("sp", "S&P 500", "^GSPC", "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"),
    ("ndx", "나스닥 100", "^NDX", ["https://api.nasdaq.com/api/quote/list-type/nasdaq100",
                                   "https://en.wikipedia.org/wiki/List_of_Nasdaq-100_companies",
                                   "https://en.wikipedia.org/wiki/Nasdaq-100"]),
]


def constituents(urls) -> list[str]:
    """구성 종목 티커. 주소를 여러 개 주면 되는 것을 쓴다 (나스닥 API JSON 또는 위키피디아 표)."""
    errs = []
    for url in ([urls] if isinstance(urls, str) else urls):
        try:
            return _constituents(url)
        except Exception as e:  # noqa: BLE001
            errs.append(f"{url.split('/')[2]}: {str(e)[:150]}")
    raise ValueError(" / ".join(errs))


def _constituents(url: str) -> list[str]:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json, text/html"})
    with urllib.request.urlopen(req, timeout=20) as r:
        text = r.read().decode("utf-8", "replace")
    if "api.nasdaq.com" in url:
        import json
        rows = json.loads(text)["data"]["data"]["rows"]
        vals = sorted({str(x["symbol"]).strip().replace(".", "-") for x in rows if x.get("symbol")})
        if len(vals) < 80:
            raise ValueError(f"{len(vals)}종목뿐")
        return vals
    seen = []
    for t in pd.read_html(io.StringIO(text)):
        cols = [" ".join(map(str, c)) if isinstance(c, tuple) else str(c) for c in t.columns]
        seen.append(f"{len(t)}행 {cols[:4]}")
        for i, c in enumerate(cols):
            if any(k in c.lower() for k in ("symbol", "ticker")) and 80 <= len(t) <= 600:
                vals = [str(x).strip().replace(".", "-") for x in t.iloc[:, i]]
                vals = [v for v in vals if v and v.lower() != "nan" and len(v) <= 6 and v.replace("-", "").isalnum()]
                if len(vals) >= 80:
                    return sorted(set(vals))
    raise ValueError("구성 종목 표를 찾지 못함: " + " | ".join(seen[:8]))


def _closes(tickers: list[str], period: str = "2y") -> pd.DataFrame:
    import yfinance as yf

    df = yf.download(tickers, period=period, auto_adjust=True, progress=False, threads=True, timeout=30)
    c = df["Close"] if isinstance(df.columns, pd.MultiIndex) else df[["Close"]]
    c.index = pd.to_datetime(c.index).tz_localize(None)
    return c.dropna(axis=1, how="all")


def compute(closes: pd.DataFrame, index: pd.Series) -> dict:
    """구성 종목 종가(열 = 종목) → ADL·지수·요약."""
    closes = closes.sort_index()
    chg = closes.diff()
    valid = chg.notna()
    adv = ((chg > 0) & valid).sum(axis=1)
    dec = ((chg < 0) & valid).sum(axis=1)
    keep = valid.sum(axis=1) >= max(1, int(closes.shape[1] * 0.5))  # 휴장·데이터 빈 날 제외
    adv, dec = adv[keep], dec[keep]
    net = adv - dec
    adl = net.cumsum()
    ma200 = closes.rolling(200, min_periods=150).mean()
    above = ((closes > ma200) & ma200.notna()).sum(axis=1) / ma200.notna().sum(axis=1).replace(0, np.nan) * 100
    above = above[keep].dropna()
    index = index.sort_index()
    index = index[index.index >= adl.index[0]]
    w = 252
    a1, i1 = adl.iloc[-w:], index.iloc[-w:]
    a_hi, i_hi = a1.idxmax(), i1.idxmax()
    a_off = float(adl.iloc[-1] - a1.max())  # 순상승 종목 수 기준, 고점보다 몇 종목분 아래인가
    i_off = float((index.iloc[-1] / i1.max() - 1) * 100)
    lag = int((i_hi - a_hi).days)
    if lag >= 30 and i_off >= -3:
        state, cls = f"다이버전스 진행 중 — ADL 고점 {a_hi:%m/%d}가 지수 고점 {i_hi:%m/%d}보다 {lag}일 먼저", "dn"
    elif lag >= 30:
        state, cls = f"ADL이 먼저 꺾인 뒤({a_hi:%m/%d}) 지수도 하락({i_hi:%m/%d} 고점 대비 {i_off:.0f}%) — 다이버전스 경고가 맞은 구간", "dn"
    elif a_hi >= adl.index[-1] - pd.Timedelta(days=10):
        state, cls = "ADL도 신고가 — 폭이 지수를 확인", "up"
    else:
        state, cls = "ADL이 고점 아래 — 지켜볼 구간", ""
    return {"adl": adl, "net": net, "index": index, "above": above, "n": int(closes.shape[1]),
            "adv": int(adv.iloc[-1]), "dec": int(dec.iloc[-1]), "date": adl.index[-1].strftime("%Y-%m-%d"),
            "adl_hi": a_hi.strftime("%Y-%m-%d"), "idx_hi": i_hi.strftime("%Y-%m-%d"), "adl_off": a_off, "idx_off": i_off,
            "net20": int(net.iloc[-20:].sum()), "above_now": float(above.iloc[-1]) if len(above) else math.nan,
            "state": state, "cls": cls}


def _demo(key: str) -> dict:
    r = np.random.default_rng(7 if key == "sp" else 13)
    idx = pd.bdate_range(end=pd.Timestamp.today().normalize(), periods=520)
    n = 500 if key == "sp" else 100
    mkt = np.cumsum(r.normal(.0004, .009, len(idx)))
    tilt = np.where(np.arange(len(idx)) > len(idx) - 70, -.0012, .0002)  # 최근 폭 약화
    rets = r.normal(0, .015, (len(idx), n)) + (np.diff(np.r_[0, mkt]) + tilt)[:, None]
    closes = pd.DataFrame(100 * np.exp(np.cumsum(rets, axis=0)), index=idx)
    big = closes.iloc[:, : n // 10].mean(axis=1) * np.exp(np.linspace(0, .08, len(idx)))
    return compute(closes, big * (6600 / big.iloc[-1] if key == "sp" else 25000 / big.iloc[-1]))


def build(ctx=None, demo: bool = False) -> dict:
    out = {}
    for key, name, tk, url in INDEXES:
        try:
            if demo:
                res = _demo(key)
            else:
                tickers = constituents(url)
                closes = _closes(tickers)
                try:
                    index = ctx.price(tk)
                except Exception:  # noqa: BLE001
                    index = _closes([tk]).iloc[:, 0]
                res = compute(closes, index)
                res["missing"] = len(tickers) - res["n"]
            out[key] = {"name": name, **res}
        except Exception as e:  # noqa: BLE001 — 화면엔 '데이터 없음'으로
            out[key] = {"name": name, "err": f"{type(e).__name__}: {str(e)[:120]}"}
    return out


# ---------------------------------------------------------------- 화면
def _xy(s: pd.Series, dec: int = 2):
    return ([d.strftime("%Y-%m-%d") for d in s.index],
            [None if (isinstance(v, float) and math.isnan(v)) else round(float(v), dec) for v in s.to_numpy()])


def _spec(b: dict) -> dict:
    xi, yi = _xy(b["index"])
    xa, ya = _xy(b["adl"], 0)
    one = (b["adl"].index[-1] - pd.DateOffset(years=1)).strftime("%Y-%m-%d")
    return {"data": [
        {"x": xi, "y": yi, "type": "scatter", "mode": "lines", "name": f"{b['name']} 지수 (왼쪽)",
         "line": {"width": 1.7, "color": "#8a8f98"}, "hovertemplate": "%{x|%Y-%m-%d}<br>지수 %{y:,.0f}<extra></extra>"},
        {"x": xa, "y": ya, "type": "scatter", "mode": "lines", "name": "ADL (오른쪽)", "yaxis": "y2",
         "line": {"width": 2, "color": ADL_C}, "hovertemplate": "%{x|%Y-%m-%d}<br>ADL %{y:,.0f}<extra></extra>"},
        {"x": [b["idx_hi"]], "y": [float(b["index"].loc[b["idx_hi"]])], "type": "scatter", "mode": "markers+text",
         "name": "지수 52주 고점", "marker": {"size": 9, "color": "#8a8f98", "symbol": "triangle-down"},
         "text": ["지수 고점"], "textposition": "top center", "textfont": {"size": 11}, "hoverinfo": "skip"},
        {"x": [b["adl_hi"]], "y": [float(b["adl"].loc[b["adl_hi"]])], "type": "scatter", "mode": "markers+text",
         "yaxis": "y2", "name": "ADL 52주 고점", "marker": {"size": 9, "color": ADL_C, "symbol": "triangle-down"},
         "text": ["ADL 고점"], "textposition": "top center", "textfont": {"size": 11}, "hoverinfo": "skip"},
    ], "layout": {
        "height": 360, "hovermode": "x unified", "showlegend": True,
        "legend": {"orientation": "h", "y": -0.12, "font": {"size": 11}},
        "margin": {"l": 8, "r": 8, "t": 40, "b": 8},
        "xaxis": {"type": "date", "range": [one, xa[-1]], "automargin": True,
                  "rangeselector": {"x": 0, "y": 1.04, "yanchor": "bottom", "font": {"size": 10},
                                    "buttons": [{"count": 3, "label": "3M", "step": "month", "stepmode": "backward"},
                                                {"count": 6, "label": "6M", "step": "month", "stepmode": "backward"},
                                                {"count": 1, "label": "1Y", "step": "year", "stepmode": "backward"},
                                                {"step": "all", "label": "2Y"}]}},
        "yaxis": {"automargin": True, "zeroline": False, "title": {"text": "지수", "font": {"size": 11}}},
        "yaxis2": {"overlaying": "y", "side": "right", "automargin": True, "zeroline": False, "showgrid": False,
                   "title": {"text": "ADL (누적 순상승 종목 수)", "font": {"size": 11}}},
        "shapes": [], "paper_bgcolor": "rgba(0,0,0,0)", "plot_bgcolor": "rgba(0,0,0,0)"}}


def _sub_spec(b: dict) -> dict:
    net = b["net"].iloc[-260:]
    xn, yn = _xy(net, 0)
    ma = net.rolling(10).mean()
    xm, ym = _xy(ma, 1)
    xa, ya = _xy(b["above"].iloc[-260:], 1)
    return {"data": [
        {"x": xn, "y": yn, "type": "bar", "name": "하루 순상승 종목 수",
         "marker": {"color": [UP if (v or 0) >= 0 else DN for v in yn]}, "opacity": .55,
         "hovertemplate": "%{x|%Y-%m-%d}<br>상승−하락 %{y:+,}<extra></extra>"},
        {"x": xm, "y": ym, "type": "scatter", "mode": "lines", "name": "10일 평균", "line": {"width": 1.6, "color": "#555"}},
        {"x": xa, "y": ya, "type": "scatter", "mode": "lines", "name": "200일선 위 종목 비율 % (오른쪽)", "yaxis": "y2",
         "line": {"width": 1.8, "color": ADL_C, "dash": "dot"}, "hovertemplate": "%{y:.0f}%<extra></extra>"},
    ], "layout": {
        "height": 260, "hovermode": "x unified", "showlegend": True, "bargap": 0,
        "legend": {"orientation": "h", "y": -0.18, "font": {"size": 11}},
        "margin": {"l": 8, "r": 8, "t": 10, "b": 8},
        "xaxis": {"type": "date", "automargin": True},
        "yaxis": {"automargin": True, "zeroline": True},
        "yaxis2": {"overlaying": "y", "side": "right", "range": [0, 100], "showgrid": False, "automargin": True},
        "shapes": [], "paper_bgcolor": "rgba(0,0,0,0)", "plot_bgcolor": "rgba(0,0,0,0)"}}


def view(b: dict | None, sub: str, nav, add_chart) -> str:
    if not b:
        return ""
    e = html.escape
    secs = []
    for key, _n, _t, _u in INDEXES:
        x = b.get(key)
        if not x:
            continue
        if "err" in x:
            secs.append(f"<section class='tool overview'><h3 class='h3s'>{e(x['name'])}</h3>"
                        f"<p class='rule'>데이터 없음 — {e(x['err'])}</p></section>")
            continue
        miss = f" (받지 못한 종목 {x['missing']}개 제외)" if x.get("missing") else ""
        kpis = "".join(f"<div class='kpi'><div class='k'>{k}</div><div class='v'>{v}</div></div>" for k, v in [
            (f"오늘 상승 / 하락 ({x['date']})", f"<span class='up'>{x['adv']}</span> / <span class='dn'>{x['dec']}</span>"),
            ("최근 20일 순상승 합계", f"<span class='{'up' if x['net20'] >= 0 else 'dn'}'>{x['net20']:+,}</span>"),
            ("200일선 위 종목 비율", f"{x['above_now']:.0f}%" if not math.isnan(x["above_now"]) else "-"),
            ("지수 52주 고점", f"{x['idx_hi']} <small>({x['idx_off']:+.1f}%)</small>"),
            ("ADL 52주 고점", f"{x['adl_hi']} <small>({x['adl_off']:+,.0f})</small>"),
        ])
        secs.append(f"""<section class='tool overview'>
  <h3 class='h3s'>{e(x['name'])} <span class='bstate {x['cls']}'>{e(x['state'])}</span></h3>
  <div class='kpis'>{kpis}</div>
  <div class='chart' id='{add_chart(_spec(x))}'></div>
  <div class='chart' id='{add_chart(_sub_spec(x))}'></div>
  <p class='rule'>구성 종목 {x['n']}개{e(miss)} 종가로 계산. ADL = 매일 (상승 종목 수 − 하락 종목 수)를 누적한 선 — 절대 수준보다 <b>지수와 같이 고점을 만드는지</b>를 봅니다.</p>
</section>""")
    return f"""<div class='view' id='v-chart-breadth' data-title='매크로 차트 · 시장 폭 (ADL)'>
<h2 class='vt'>시장 폭 — ADL (상승·하락 종목 수 누적선)</h2><div class='sub'>{sub}</div>
{nav('chart-breadth')}
<section class='tool overview'><p class='headline'>지수는 소수 대형주만으로도 오를 수 있다. ADL은 '몇 개 종목이 같이 오르는가'를 본다 —
지수가 신고가인데 ADL이 먼저 꺾이면(다이버전스) 상승의 폭이 좁아지고 있다는 경고.</p>
<p class='rule'>SD(2026년 11월): "A/D 선 고점은 8/14, 지수 고점은 10월" — 체크리스트가 뒤집힌 근거 중 하나. 노란 선(ADL)의 고점(▼)이 회색 선(지수)의 고점보다 한참 앞에 있으면 같은 패턴입니다.
지금 구성 종목으로 과거를 계산하므로(생존 편향) 2년만 보여 줍니다. 나스닥은 종합지수 대신 나스닥 100 구성 종목입니다.</p></section>
{''.join(secs)}
</div>"""


CSS = """
.bstate{font-size:12.5px;font-weight:600;margin-left:8px;padding:2px 8px;border-radius:99px;background:var(--line);color:var(--ink)}
.bstate.dn{background:#2f6fdb22;color:#2f6fdb} .bstate.up{background:#d6454522;color:#d64545}
"""
