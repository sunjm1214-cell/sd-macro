"""'매크로 차트' — 주요 지수 · 채권·금리 · 원자재 · 통화. 판단 없이 시장 흐름만 본다.

각 종목은 (원천, ID) 후보를 순서대로 시도한다: Yahoo가 막히면 FRED로.
  y = Yahoo (yfinance, 지수·선물·환율), f = FRED (금리·유가·환율 일별)
변화 표기: 가격은 %, 금리·스프레드는 bp(0.01%p). 색은 한국식 — 상승 빨강 ▲, 하락 파랑 ▼.
"""
from __future__ import annotations

import html
import math

import pandas as pd

from .core import Context, DataUnavailable

UP, DN = "#d64545", "#2f6fdb"

# key, 이름, [(원천, ID)], 종류(price/rate), 소수점, 설명
GROUPS = [
    ("idx", "주요 지수", [
        ("spx", "S&P 500", [("y", "^GSPC")], "price", 0, "미국 대형주 500"),
        ("ndx", "나스닥 종합", [("y", "^IXIC")], "price", 0, "미국 기술주 중심"),
        ("dji", "다우존스", [("y", "^DJI")], "price", 0, "미국 우량주 30"),
        ("rut", "러셀 2000", [("y", "^RUT")], "price", 0, "미국 소형주 — 경기 민감"),
        ("vix", "VIX", [("y", "^VIX")], "price", 1, "S&P 500 옵션 변동성 — 공포지수"),
        ("kospi", "코스피", [("y", "^KS11")], "price", 0, "한국 대표 지수"),
        ("kosdaq", "코스닥", [("y", "^KQ11")], "price", 0, "한국 성장주"),
        ("n225", "니케이 225", [("y", "^N225")], "price", 0, "일본"),
        ("sx5e", "유로스톡스 50", [("y", "^STOXX50E")], "price", 0, "유로존 대형주"),
        ("shcomp", "상해종합", [("y", "000001.SS")], "price", 0, "중국 본토"),
    ]),
    ("rates", "채권·금리", [
        ("us3m", "미 3개월물", [("f", "DGS3MO")], "rate", 2, "정책금리 기대에 가장 가까움"),
        ("us2y", "미 2년물", [("f", "DGS2")], "rate", 2, "향후 1~2년 연준 경로"),
        ("us5y", "미 5년물", [("f", "DGS5")], "rate", 2, ""),
        ("us10y", "미 10년물", [("f", "DGS10")], "rate", 2, "SD 황금률: 명목GDP 근처여야"),
        ("us30y", "미 30년물", [("f", "DGS30")], "rate", 2, "재정 공급 압박이 먼저 보이는 곳"),
        ("real10", "미 10년 실질금리", [("f", "DFII10")], "rate", 2, "TIPS — 금·성장주 할인율"),
        ("t10y2y", "10년−2년 스프레드", [("f", "T10Y2Y")], "rate", 2, "음수 = 역전"),
        ("hy", "하이일드 스프레드", [("f", "BAMLH0A0HYM2")], "rate", 2, "신용 위험 프리미엄"),
        ("kr10y", "한국 10년물 (월)", [("f", "IRLTLT01KRM156N")], "rate", 2, "OECD 월간"),
    ]),
    ("cmd", "원자재", [
        ("wti", "WTI 원유", [("f", "DCOILWTICO"), ("y", "CL=F")], "price", 2, "달러/배럴"),
        ("brent", "브렌트유", [("f", "DCOILBRENTEU"), ("y", "BZ=F")], "price", 2, "달러/배럴"),
        ("gold", "금", [("y", "GC=F"), ("y", "GLD")], "price", 0, "달러/온스 (선물)"),
        ("silver", "은", [("y", "SI=F")], "price", 2, "달러/온스 (선물)"),
        ("copper", "구리", [("y", "HG=F"), ("y", "CPER")], "price", 3, "달러/파운드 (선물) — '닥터 코퍼'"),
        ("natgas", "천연가스", [("y", "NG=F"), ("f", "DHHNGSP")], "price", 2, "달러/MMBtu"),
    ]),
    ("fx", "통화", [
        ("dxy", "달러인덱스", [("y", "DX-Y.NYB"), ("f", "DTWEXBGS")], "price", 2, "주요 6개 통화 대비 달러"),
        ("usdkrw", "원/달러", [("y", "KRW=X"), ("f", "DEXKOUS")], "price", 1, "오르면 원화 약세"),
        ("usdjpy", "엔/달러", [("y", "JPY=X"), ("f", "DEXJPUS")], "price", 2, "오르면 엔화 약세"),
        ("eurusd", "달러/유로", [("y", "EURUSD=X"), ("f", "DEXUSEU")], "price", 4, "오르면 유로 강세"),
        ("usdcny", "위안/달러", [("y", "CNY=X"), ("f", "DEXCHUS")], "price", 4, "오르면 위안화 약세"),
        ("btc", "비트코인", [("y", "BTC-USD")], "price", 0, "달러"),
    ]),
]
HOME_STRIP = ["spx", "ndx", "kospi", "us10y", "wti", "gold", "copper", "dxy", "usdkrw"]
HORIZONS = [("1주", 7), ("1개월", 30), ("3개월", 91), ("올해", "ytd"), ("1년", 365)]


def all_ids() -> tuple[list[str], list[str]]:
    """prefetch용 (FRED, Yahoo) ID 목록."""
    f, y = [], []
    for _, _, items in GROUPS:
        for it in items:
            for src, sid in it[2]:
                (f if src == "f" else y).append(sid)
    return sorted(set(f)), sorted(set(y))


def _series(ctx: Context, cands) -> tuple[pd.Series, str]:
    err = None
    for src, sid in cands:
        try:
            s = ctx.series(sid) if src == "f" else ctx.price(sid)
            s = s.dropna()
            if len(s) > 5:
                return s, ("FRED " if src == "f" else "Yahoo ") + sid
        except Exception as e:  # noqa: BLE001 — 하나가 막혀도 다음 후보로
            err = e
    raise DataUnavailable(str(err) if err else "데이터 없음")


def _at(s: pd.Series, when: pd.Timestamp):
    v = s[s.index <= when]
    return float(v.iloc[-1]) if len(v) else None


def _changes(s: pd.Series, kind: str) -> dict:
    last_t, last = s.index[-1], float(s.iloc[-1])
    out = {}
    for lab, d in HORIZONS:
        when = pd.Timestamp(year=last_t.year - 1, month=12, day=31) if d == "ytd" else last_t - pd.Timedelta(days=d)
        base = _at(s, when)
        if base is None or (kind == "price" and base == 0):
            out[lab] = None
        else:
            out[lab] = (last - base) * 100 if kind == "rate" else (last / base - 1) * 100
    return out


def _thin(s: pd.Series) -> pd.Series:
    s = s[s.index >= "2000-01-01"]
    cut = s.index[-1] - pd.DateOffset(years=3)
    old = s[s.index < cut].resample("W").last().dropna()
    return pd.concat([old, s[s.index >= cut]])


def build(ctx: Context) -> dict:
    groups = []
    for gkey, gname, items in GROUPS:
        rows = []
        for key, name, cands, kind, dec, desc in items:
            try:
                s, src = _series(ctx, cands)
            except DataUnavailable as e:
                rows.append({"key": key, "name": name, "desc": desc, "kind": kind, "err": str(e)[:80]})
                continue
            w = s[s.index >= s.index[-1] - pd.Timedelta(days=365)]
            lo, hi, last = float(w.min()), float(w.max()), float(s.iloc[-1])
            rows.append({"key": key, "name": name, "desc": desc, "kind": kind, "dec": dec, "src": src,
                         "last": last, "date": s.index[-1].strftime("%Y-%m-%d"), "chg": _changes(s, kind),
                         "lo": lo, "hi": hi, "pos": (last - lo) / (hi - lo) * 100 if hi > lo else 50.0,
                         "s": _thin(s)})
        curve = None
        if gkey == "rates":
            pts = [("3개월", "us3m"), ("2년", "us2y"), ("5년", "us5y"), ("10년", "us10y"), ("30년", "us30y")]
            by = {r["key"]: r for r in rows if "s" in r}
            if all(k in by for _, k in pts):
                curve = []
                for lab, days in (("지금", 0), ("1개월 전", 30), ("1년 전", 365)):
                    vals = []
                    for _, k in pts:
                        s = by[k]["s"]
                        vals.append(_at(s, s.index[-1] - pd.Timedelta(days=days)))
                    curve.append((lab, vals))
                curve = {"x": [p for p, _ in pts], "lines": curve}
        groups.append({"key": gkey, "name": gname, "rows": rows, "curve": curve})
    return {"groups": groups}


# ---------------------------------------------------------------- 화면
def _e(v) -> str:
    return html.escape(str(v))


def _fmt(v, dec) -> str:
    return "-" if v is None or (isinstance(v, float) and math.isnan(v)) else f"{v:,.{dec}f}"


def _flat(v, kind) -> bool:
    return abs(v) < (0.5 if kind == "rate" else 0.05)


def _chg(v, kind) -> str:
    if v is None:
        return "<td class='c'>-</td>"
    if _flat(v, kind):
        return f"<td class='c'>0{'bp' if kind == 'rate' else '%'}</td>"
    cls = "up" if v > 0 else "dn" if v < 0 else ""
    arrow = "▲" if v > 0 else "▼" if v < 0 else ""
    txt = f"{abs(v):,.0f}bp" if kind == "rate" else f"{abs(v):,.1f}%"
    return f"<td class='c {cls}'>{arrow}{txt}</td>"


def _line_spec(r: dict) -> dict:
    s = r["s"]
    x = [d.strftime("%Y-%m-%d") for d in s.index]
    y = [None if math.isnan(v) else round(float(v), 4) for v in s.to_numpy()]
    one = (s.index[-1] - pd.DateOffset(years=1)).strftime("%Y-%m-%d")
    color = UP if (r["chg"].get("1년") or 0) >= 0 else DN
    return {"data": [{"x": x, "y": y, "type": "scatter", "mode": "lines", "name": r["name"],
                      "line": {"width": 1.6, "color": color}, "fill": "none",
                      "hovertemplate": "%{x|%Y-%m-%d}<br>%{y:,." + str(r["dec"]) + "f}<extra></extra>"}],
            "layout": {"title": {"text": "", "font": {"size": 1}}, "height": 210, "showlegend": False,
                       "margin": {"l": 6, "r": 6, "t": 34, "b": 6}, "hovermode": "x",
                       "xaxis": {"type": "date", "range": [one, x[-1]], "automargin": True,
                                 "rangeselector": {"x": 0, "y": 1.04, "yanchor": "bottom", "font": {"size": 10},
                                                   "buttons": [{"count": 1, "label": "1M", "step": "month", "stepmode": "backward"},
                                                               {"count": 6, "label": "6M", "step": "month", "stepmode": "backward"},
                                                               {"count": 1, "label": "1Y", "step": "year", "stepmode": "backward"},
                                                               {"count": 5, "label": "5Y", "step": "year", "stepmode": "backward"},
                                                               {"step": "all", "label": "전체"}]}},
                       "yaxis": {"automargin": True, "zeroline": False, "side": "right"},
                       "shapes": [], "paper_bgcolor": "rgba(0,0,0,0)", "plot_bgcolor": "rgba(0,0,0,0)"}}


def _bar_spec(rows: list[dict], kind: str) -> dict | None:
    ok = [r for r in rows if "chg" in r]
    if not ok:
        return None
    names = [r["name"] for r in ok]

    def arr(lab):
        v = [r["chg"].get(lab) for r in ok]
        v = [None if x is None else (0.0 if _flat(x, kind) else round(x, 2)) for x in v]
        unit = "bp" if kind == "rate" else "%"
        return {"x": v, "marker.color": [UP if (x or 0) >= 0 else DN for x in v],
                "text": ["" if x is None else (f"{x:+,.0f}{unit}" if kind == "rate" else f"{x:+.1f}{unit}") for x in v]}

    default = "1개월"
    d0 = arr(default)
    buttons = [{"label": lab, "method": "restyle",
                "args": [{"x": [a["x"]], "marker.color": [a["marker.color"]], "text": [a["text"]]}]}
               for lab, a in ((lab, arr(lab)) for lab, _ in HORIZONS)]
    active = [lab for lab, _ in HORIZONS].index(default)
    return {"data": [{"type": "bar", "orientation": "h", "y": names, "x": d0["x"], "text": d0["text"],
                      "textposition": "outside", "cliponaxis": False, "marker": {"color": d0["marker.color"]},
                      "hovertemplate": "%{y}: %{text}<extra></extra>"}],
            "layout": {"height": 46 + 30 * len(ok), "margin": {"l": 10, "r": 40, "t": 44, "b": 10},
                       "showlegend": False, "bargap": 0.35,
                       "xaxis": {"zeroline": True, "zerolinewidth": 1, "automargin": True,
                                 "ticksuffix": "bp" if kind == "rate" else "%"},
                       "yaxis": {"autorange": "reversed", "automargin": True},
                       "updatemenus": [{"type": "buttons", "direction": "right", "x": 0, "y": 1.02, "xanchor": "left",
                                        "yanchor": "bottom", "showactive": True, "active": active,
                                        "pad": {"r": 4, "t": 0}, "font": {"size": 11}, "buttons": buttons}],
                       "paper_bgcolor": "rgba(0,0,0,0)", "plot_bgcolor": "rgba(0,0,0,0)"}}


def _curve_spec(c: dict) -> dict:
    cols = ["#1d1f23", "#8a8f98", "#c9c7c2"]
    data = [{"x": c["x"], "y": [None if v is None else round(v, 3) for v in vals], "name": lab, "type": "scatter",
             "mode": "lines+markers", "line": {"width": 2.6 if i == 0 else 1.6, "color": cols[i],
                                                 "dash": "solid" if i == 0 else "dot"},
             "hovertemplate": "%{x}: %{y:.2f}%<extra>" + lab + "</extra>"} for i, (lab, vals) in enumerate(c["lines"])]
    return {"data": data, "layout": {"height": 300, "margin": {"l": 10, "r": 10, "t": 40, "b": 10},
                                     "title": {"text": "미국 국채 수익률 곡선", "font": {"size": 14}, "x": 0},
                                     "xaxis": {"type": "category", "automargin": True},
                                     "yaxis": {"ticksuffix": "%", "automargin": True},
                                     "legend": {"orientation": "h", "x": 1, "xanchor": "right", "y": 1.08},
                                     "paper_bgcolor": "rgba(0,0,0,0)", "plot_bgcolor": "rgba(0,0,0,0)"}}


def strip(m: dict | None) -> str:
    """홈 상단 주요 시세 띠."""
    if not m:
        return ""
    by = {r["key"]: (g["key"], r) for g in m["groups"] for r in g["rows"] if "last" in r}
    cells = []
    for k in HOME_STRIP:
        if k not in by:
            continue
        g, r = by[k]
        c = r["chg"].get("1개월")
        if c is not None and _flat(c, r["kind"]):
            c = 0.0
        cls = "up" if (c or 0) > 0 else "dn" if (c or 0) < 0 else ""
        unit = "%" if r["kind"] == "rate" else ""
        ctxt = "-" if c is None else ("0" + ("bp" if r["kind"] == "rate" else "%")) if c == 0 else (f"{'▲' if c > 0 else '▼'}{abs(c):,.0f}bp" if r["kind"] == "rate"
                                      else f"{'▲' if c > 0 else '▼'}{abs(c):.1f}%")
        cells.append(f"<a class='tk' href='#chart-{g}'><span class='tn'>{_e(r['name'])}</span>"
                     f"<span class='tv'>{_fmt(r['last'], r['dec'])}{unit}</span><span class='tc {cls}'>{ctxt}<small>1개월</small></span></a>")
    return f"<div class='tstrip'>{''.join(cells)}</div>" if cells else ""


def views(m: dict | None, sub: str, nav, add_chart) -> str:
    """그룹별 화면. nav(key) → 하위 메뉴 HTML, add_chart(spec) → 차트 div id."""
    if not m:
        return ""
    out = []
    for g in m["groups"]:
        kind = "rate" if g["key"] == "rates" else "price"
        rows = []
        for r in g["rows"]:
            if "err" in r:
                rows.append(f"<tr><td><b>{_e(r['name'])}</b><div class='why'>{_e(r['desc'])}</div></td>"
                            f"<td colspan='8' class='why'>데이터 없음 — {_e(r['err'])}</td></tr>")
                continue
            unit = "%" if r["kind"] == "rate" else ""
            bar = (f"<div class='rng'><span style='left:{max(0, min(100, r['pos'])):.0f}%'></span></div>"
                   f"<div class='rngl'><span>{_fmt(r['lo'], r['dec'])}</span><span>{_fmt(r['hi'], r['dec'])}</span></div>")
            rows.append(f"<tr><td><a href='#mk-{r['key']}'><b>{_e(r['name'])}</b></a><div class='why'>{_e(r['desc'])}</div></td>"
                        f"<td class='c last'>{_fmt(r['last'], r['dec'])}{unit}<div class='why'>{_e(r['date'])}</div></td>"
                        + "".join(_chg(r["chg"].get(lab), r["kind"]) for lab, _ in HORIZONS)
                        + f"<td class='rngc'>{bar}</td></tr>")
        head = "".join(f"<th class='c'>{_e(lab)}</th>" for lab, _ in HORIZONS)
        table = (f"<div class='tblwrap'><table class='tbl mkt'><thead><tr><th>종목</th><th class='c'>현재</th>{head}"
                 f"<th class='c'>52주 범위</th></tr></thead><tbody>{''.join(rows)}</tbody></table></div>")
        bar = _bar_spec(g["rows"], kind)
        bar_html = f"<div class='chart bar' id='{add_chart(bar)}'></div>" if bar else ""
        curve = f"<div class='chart' id='{add_chart(_curve_spec(g['curve']))}'></div>" if g.get("curve") else ""
        minis = "".join(
            f"<div class='mini' id='mk-{r['key']}'><div class='mh2'><b>{_e(r['name'])}</b>"
            f"<span>{_fmt(r['last'], r['dec'])}{'%' if r['kind'] == 'rate' else ''}</span>"
            f"{_chg(r['chg'].get('1년'), r['kind']).replace('<td', '<em').replace('</td>', ' <small>1년</small></em>')}</div>"
            f"<div class='chart sm' id='{add_chart(_line_spec(r))}'></div><div class='src2'>{_e(r['src'])}</div></div>"
            for r in g["rows"] if "s" in r)
        note = ("금리·스프레드의 변화는 bp(0.01%p)입니다. 금리가 오르면(▲) 채권 가격은 내립니다." if kind == "rate"
                else "색은 한국식입니다: 상승 빨강 ▲, 하락 파랑 ▼.")
        out.append(f"""<div class='view' id='v-chart-{g['key']}' data-title='매크로 차트 · {_e(g['name'])}'>
<h2 class='vt'>{_e(g['name'])}</h2><div class='sub'>{sub}</div>
{nav('chart-' + g['key'])}
<section class='tool overview'>
  <h3 class='h3s'>시세판</h3>{table}
  <p class='rule'>{note} 52주 범위의 점은 지금 위치(왼쪽 = 52주 최저, 오른쪽 = 최고).</p>
</section>
<section class='tool overview'><h3 class='h3s'>기간별 변화</h3>{bar_html}{curve}</section>
<section class='tool overview'><h3 class='h3s'>종목별 차트</h3><div class='minis'>{minis}</div>
  <p class='rule'>기본 1년 · 위 버튼으로 기간 변경 · 선 색은 1년 변화 방향. 3년보다 오래된 구간은 주간 값입니다.</p></section>
</div>""")
    return "".join(out)


CSS = """
.tstrip{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:8px;margin:16px 0 4px}
.tk{display:flex;flex-direction:column;gap:1px;background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:10px 12px;text-decoration:none;color:inherit}
.tk:hover{border-color:var(--mute)}
.tn{font-size:12.5px;color:var(--mute)} .tv{font-size:19px;font-weight:700;font-variant-numeric:tabular-nums;letter-spacing:-.2px}
.tc{font-size:12.5px;font-weight:600;font-variant-numeric:tabular-nums} .tc small{color:var(--mute);font-weight:400;margin-left:4px;font-size:11.5px}
.up{color:#d64545} .dn{color:#2f6fdb}
.h3s{font-size:15px;margin:0 0 10px}
.tbl.mkt{width:100%} .tbl.mkt td{vertical-align:middle} .tbl.mkt td.c,.tbl.mkt th.c{text-align:right} .tbl.mkt td.last{font-weight:700;font-size:15px}
.tbl.mkt .why{font-size:12px;color:var(--mute);font-weight:400;white-space:normal} .tbl.mkt a{color:var(--ink);text-decoration:none}
.tbl.mkt td.up,.tbl.mkt td.dn{font-weight:600}
.rngc{min-width:130px} .rng{position:relative;height:6px;border-radius:3px;background:linear-gradient(90deg,#2f6fdb33,#8a8f9833,#d6454533);margin-top:4px}
.rng span{position:absolute;top:-4px;width:12px;height:12px;margin-left:-6px;border-radius:50%;background:var(--ink);border:2px solid var(--panel)}
.rngl{display:flex;justify-content:space-between;font-size:11px;color:var(--mute);margin-top:3px;font-variant-numeric:tabular-nums}
.chart.bar{min-height:0}
.minis{display:grid;grid-template-columns:repeat(auto-fill,minmax(min(100%,330px),1fr));gap:10px}
.mini{border:1px solid var(--line);border-radius:10px;padding:8px 10px 4px}
.mh2{display:flex;gap:8px;align-items:baseline;flex-wrap:wrap} .mh2 b{font-size:14.5px} .mh2 span{font-weight:700;font-variant-numeric:tabular-nums}
.mh2 em{font-style:normal;font-size:12.5px;font-weight:600} .mh2 em small{color:var(--mute);font-weight:400}
.chart.sm{min-height:210px;border:0;padding:0}
.src2{font-size:11px;color:var(--mute);text-align:right}
"""
