"""HTML 리포트. 단일 파일(차트는 Plotly CDN)로 브라우저에서 바로 연다.

읽는 순서대로 배치한다: 한눈 요약(경고 → 주시 → 양호) → 툴별 결론 → 핵심 숫자 → 차트,
규칙의 근거·해석 메모·과거 구간 표는 접어 두고 필요할 때 펼친다.
"""
from __future__ import annotations

import html
import json
import math
from datetime import datetime, timedelta, timezone


import pandas as pd

from .core import Chart, Signal, ToolResult
from .earnings import CSS as E_CSS, JS as E_JS, view as e_view
from .reference import CSS as R_CSS, view as r_view
from .markets import CSS as M_CSS, strip as m_strip, views as m_views
from .links import data_links
from .registry import LAYERS, USES, get_tool
from .stats import _ALIAS

PLOTLY = "https://cdn.jsdelivr.net/npm/plotly.js-dist-min@2.35.2/plotly.min.js"
PALETTE = ["#2f6fdb", "#e0782b", "#2a9d6a", "#b8448a", "#7a5cd6", "#8a8f98"]
SIG_CLASS = {Signal.OK: "ok", Signal.WATCH: "watch", Signal.ALERT: "alert", Signal.NA: "na"}
SIG_TEXT = {Signal.ALERT: "경고", Signal.WATCH: "주시", Signal.OK: "양호", Signal.NA: "판단불가"}
SUMMARY_ORDER = [Signal.ALERT, Signal.WATCH, Signal.OK, Signal.NA]
LAYER_NOTE = {
    "유동성·연준": "원인 — '시장을 움직이는 건 이익이 아니라 연준과 유동성'",
    "채권": "방향을 가장 먼저 읽는 곳 — 단, 연준이 국채를 사는 동안엔 신호가 흐려진다",
    "통화": "견해를 가장 효율적으로 표현하는 곳",
    "주식·이익": "확인 — 시장 내부와 이익이 경제를 6~12개월 앞서 말한다",
    "누적 위험": "타이밍이 아니라 '얼마나' — 위험보상의 크기와 수년짜리 배경",
}
N_KPI = 4  # 크게 보여줄 핵심 숫자 개수. 나머지는 '세부 지표'로 작게


def _clean(v):
    if v is None:
        return None
    v = float(v)
    return None if math.isnan(v) or math.isinf(v) else round(v, 4)


def _thin(s: pd.Series, max_pts: int = 2500) -> pd.Series:
    s = s.dropna()
    if len(s) > max_pts:
        s = s.resample("W").last().dropna()
    if len(s) > max_pts:
        s = s.resample(_ALIAS["M"]).last().dropna()
    return s


def chart_spec(ch: Chart, recessions) -> dict:
    traces = []
    for i, (name, s) in enumerate(ch.series.items()):
        s = _thin(s)
        tr = {"x": [d.strftime("%Y-%m-%d") for d in s.index], "y": [_clean(v) for v in s.to_numpy()],
              "name": name, "type": "bar" if ch.kind == "bar" else "scatter",
              "marker": {"color": PALETTE[i % len(PALETTE)]},
              "hovertemplate": "%{y:,.2f}<extra>" + html.escape(name) + "</extra>"}
        if ch.kind != "bar":
            tr.update(mode="lines", line={"width": 1.8, "color": PALETTE[i % len(PALETTE)]})
        if name in ch.secondary:
            tr["yaxis"] = "y2"
        traces.append(tr)
    shapes = []
    xs = [x for t in traces for x in t["x"]]
    x0, x1 = (min(xs), max(xs)) if xs else (None, None)
    if ch.shade_recessions and x0:
        for a, b in recessions:
            if b.strftime("%Y-%m-%d") < x0:
                continue
            shapes.append({"type": "rect", "xref": "x", "yref": "paper", "x0": a.strftime("%Y-%m-%d"),
                           "x1": (b + pd.offsets.MonthEnd(0)).strftime("%Y-%m-%d"), "y0": 0, "y1": 1,
                           "fillcolor": "rgba(128,128,128,0.16)", "line": {"width": 0}, "layer": "below"})
    for y, _label in ch.hlines:
        shapes.append({"type": "line", "xref": "paper", "x0": 0, "x1": 1, "y0": y, "y1": y,
                       "line": {"color": "rgba(128,128,128,0.7)", "width": 1, "dash": "dot"}})
    xaxis = {"type": "date", "automargin": True}
    if x0 and ch.years:
        start = (pd.Timestamp(x1) - pd.DateOffset(years=ch.years)).strftime("%Y-%m-%d")
        if start > x0:
            xaxis["range"] = [start, x1]
    xaxis["rangeselector"] = {"x": 0, "y": 1.02, "yanchor": "bottom", "font": {"size": 11},
                              "buttons": [{"count": 10, "label": "10년", "step": "year", "stepmode": "backward"},
                                          {"count": 30, "label": "30년", "step": "year", "stepmode": "backward"},
                                          {"step": "all", "label": "전체"}]}
    layout = {"title": {"text": ch.title, "font": {"size": 14}, "x": 0, "xanchor": "left", "y": 0.98},
              "shapes": shapes, "height": 340, "margin": {"l": 10, "r": 10, "t": 70, "b": 10},
              "hovermode": "x unified", "showlegend": len(traces) > 1,
              "legend": {"orientation": "h", "x": 1, "xanchor": "right", "y": 1.02, "yanchor": "bottom", "font": {"size": 12}},
              "xaxis": xaxis, "yaxis": {"title": {"text": ch.y_title, "font": {"size": 12}}, "zeroline": False, "automargin": True},
              "paper_bgcolor": "rgba(0,0,0,0)", "plot_bgcolor": "rgba(0,0,0,0)", "bargap": 0.05}
    if ch.secondary:
        layout["yaxis2"] = {"overlaying": "y", "side": "right", "automargin": True}
    return {"data": traces, "layout": layout}


def _table(title: str, df: pd.DataFrame) -> str:
    body = df.to_html(index=not isinstance(df.index, pd.RangeIndex), border=0, classes="tbl", na_rep="-",
                      escape=True, float_format=lambda v: f"{v:,.2f}")
    return (f"<details class='fold'><summary>{html.escape(title)} <span class='cnt'>{len(df)}행</span></summary>"
            f"<div class='tblwrap'>{body}</div></details>")


def _split_metrics(metrics: dict[str, str]) -> tuple[str | None, list, list]:
    """'기준…' 항목은 머리말의 기준 시점으로 빼고, 나머지는 앞 N_KPI개(핵심)와 그 뒤(세부)로 나눈다."""
    as_of, items = None, []
    for k, v in metrics.items():
        if k.startswith("기준") and as_of is None:
            as_of = str(v)
        else:
            items.append((k, str(v)))
    return as_of, items[:N_KPI], items[N_KPI:]


def _section(r: ToolResult, chart_divs: list[str]) -> str:
    cls = SIG_CLASS[r.signal]
    spec = get_tool(r.tool)
    as_of, kpis, rest = _split_metrics(r.metrics)
    as_of = as_of or r.as_of or "-"
    kpi_html = "".join(f"<div class='kpi'><div class='k'>{html.escape(k)}</div><div class='v'>{html.escape(v)}</div></div>"
                       for k, v in kpis)
    rest_html = ("<dl class='more'>" + "".join(f"<div><dt>{html.escape(k)}</dt><dd>{html.escape(v)}</dd></div>"
                                              for k, v in rest) + "</dl>") if rest else ""
    src = " · ".join(f"<a href='{html.escape(u)}' target='_blank' rel='noopener'>{html.escape(l)}</a>"
                     for l, u in spec.sources)
    notes = "".join(f"<li>{html.escape(n)}</li>" for n in r.notes)
    chips = "".join(f"<a class='dl' href='{html.escape(u)}' target='_blank' rel='noopener' title='{html.escape(i)}'>"
                    f"{html.escape(n)} <span>{html.escape(i)}</span> ↗</a>"
                    for n, i, u in data_links(spec.series, spec.tickers))
    data_html = f"<div class='dlinks'><b>데이터 원본</b>{chips}</div>" if chips else ""
    memo = (f"<details class='fold'><summary>해석할 때 주의할 점 · 근거 <span class='cnt'>{len(r.notes)}</span></summary>"
            f"<ul class='notes'>{notes}</ul><div class='src'>근거 자료: {src}</div></details>")
    tables = "".join(_table(t, df) for t, df in r.tables)
    err = (f"<details class='fold'><summary>오류 상세</summary><pre>{html.escape(r.error)}</pre></details>"
           if r.error else "")
    return f"""
<section id='{r.tool}' class='tool {cls}'>
  <div class='th'>
    <span class='badge {cls}'>{SIG_TEXT[r.signal]}</span>
    <h2>{html.escape(r.title)}</h2>
    <span class='asof'>기준 {html.escape(as_of)}</span>
  </div>
  <div class='tags'><span class='tag' title='{html.escape(USES[spec.use])}'>용도: {html.escape(spec.use)}</span>{f"<span class='tag'>선행: {html.escape(spec.lead)}</span>" if spec.lead else ''}</div>
  <p class='rule'><span class='concept'>{html.escape(spec.concept)}</span> “{html.escape(spec.rule)}”</p>
  <p class='headline'>{html.escape(r.headline)}</p>
  {f"<div class='kpis'>{kpi_html}</div>" if kpis else ''}
  {rest_html}
  {f"<div class='charts'>{''.join(chart_divs)}</div>" if chart_divs else ''}
  {tables}
  {data_html}
  {memo}
  {err}
  <div class='tid'>tool: <code>{r.tool}</code></div>
</section>"""


def _summary(results: list[ToolResult]) -> str:
    cols = []
    for s in SUMMARY_ORDER:
        rs = [r for r in results if r.signal == s]
        if not rs:
            continue
        items = "".join(f"<li><a href='#{r.tool}'><b>{html.escape(r.title.split(' (')[0])}</b>"
                        f"<span>{html.escape(r.headline)}</span></a></li>" for r in rs)
        cols.append(f"<div class='scol {SIG_CLASS[s]}'><h3><i></i>{SIG_TEXT[s]} <span class='cnt'>{len(rs)}</span></h3>"
                    f"<ul>{items}</ul></div>")
    return f"<div class='summary'>{''.join(cols)}</div>"


def _overview(chart_html: str | None) -> str:
    if not chart_html:
        return "<p class='rule'>한눈 차트를 만들지 못했습니다(데이터 없음 또는 --no-chart).</p>"
    # 숨겨진 화면에서 그리면 차트 폭이 0이 되므로, 처음 열 때 srcdoc을 넣는다 (data-srcdoc → JS)
    chips = "".join(f"<a class='dl' href='{html.escape(u)}' target='_blank' rel='noopener'>{html.escape(n)} <span>{html.escape(i)}</span> ↗</a>"
                    for n, i, u in data_links(["GS10", "FEDFUNDS", "WTISPLC", "DTWEXBGS", "TWEXBMTH", "CP"]))
    return f"""<section class='tool overview'>
  <p class='rule'>판단 없이 흐름만 보는 차트입니다. 유가·금리·달러가 함께 오를 때 이익이 꺾인다는 그의 2000년 관찰을 눈으로 확인하세요. 카드를 누르면 선이 켜지고 꺼지며, 드래그하면 확대됩니다.</p>
  <iframe class='ov' title='금리·유가·달러·기업이익 차트' data-srcdoc="{html.escape(chart_html, quote=True)}"></iframe>
  <div class='dlinks'><b>데이터 원본</b>{chips}</div>
</section>"""


def _ngdp_view(ngdp: dict | None, chart_divs: list[str], sub: str) -> str:
    if not ngdp:
        return ""
    kp = "".join(f"<div class='kpi'><div class='k'>{html.escape(k)}</div><div class='v'>{html.escape(v)}</div></div>"
                 for k, v in ngdp["kpis"].items())
    rows = "".join(f"<tr><td><b>{html.escape(r)}</b></td><td>{html.escape(q)}</td>"
                   f"<td><a href='https://chian.io/projects/stanley-druckenmiller/{html.escape(u)}' target='_blank' rel='noopener'>{html.escape(s)}</a></td></tr>"
                   for r, q, s, u in ngdp["factcheck"])
    return f"""<div class='view' id='v-chart-ngdp' data-title='매크로 차트 · 명목GDP vs 금리'>
<h2 class='vt'>명목GDP vs 금리 — 10년물 · 기준금리</h2><div class='sub'>{sub}</div>
__ENAV__
<section class='tool overview'>
  <p class='headline'>팩트체크: 그가 '명목GDP를 따라간다'고 한 금리는 <u>10년물 국채금리</u>입니다. 기준금리는 명목성장보다 한참 낮을 때 '연준이 너무 완화적'이라는 증거로 썼습니다(2003년 9% vs 1%).</p>
  <div class='kpis'>{kp}</div>
  <div class='charts'>{''.join(chart_divs)}</div>
  <details class='fold' open><summary>원문 대조</summary><div class='tblwrap'><table class='tbl fc'><thead><tr><th>금리</th><th>그의 말 (요지)</th><th>출처</th></tr></thead><tbody>{rows}</tbody></table></div>
  <ul class='notes'><li>단서: 그는 '조작되지 않을 때'라는 조건을 붙였습니다 — 연준이 국채를 대량 매입하던 2010년대엔 10년물이 명목성장보다 낮게 눌려 있었습니다. 채권 단계의 '채권 황금률' 툴이 이 괴리를 신호로 판정합니다.</li>
  <li>명목GDP는 분기 데이터(1~2개월 지연), 금리는 분기 평균입니다. 위 숫자의 10년물·기준금리는 최신 월 값입니다.</li></ul></details>
  <div class='dlinks'><b>데이터 원본</b>{''.join(f"<a class='dl' href='{html.escape(u)}' target='_blank' rel='noopener'>{html.escape(n)} <span>{html.escape(i)}</span> ↗</a>" for n, i, u in data_links(['GDP', 'GS10', 'FEDFUNDS']))}</div>
  <p class='rule'><a href='#bond_ngdp'>→ 채권 황금률 툴(신호 판정) 보기</a> · <a href='#mars_fed_funds'>→ 화성인 금리 게임 툴 보기</a></p>
</section></div>"""


def _updates(rows: list[dict] | None) -> str:
    """이번 실행에서 원천(FRED/Yahoo)을 확인한 결과. 새 데이터가 들어온 시리즈를 위에 보여준다."""
    if not rows:
        return ""
    changed = [r for r in rows if r["_s"] in ("new", "revised", "first")]
    failed = [r for r in rows if r["_s"] == "offline"]
    if changed:
        items = "".join(
            f"<li><b>{html.escape(r['시리즈'])}</b> {html.escape(r['결과'])} — "
            + (f"+{r['추가']}개, 최신 {html.escape(r['최신 마지막'])}" if r["추가"] else f"과거 값 {r['개정']}개 수정")
            + "</li>" for r in changed[:12])
        more = f"<li>…외 {len(changed) - 12}개</li>" if len(changed) > 12 else ""
        head = f"이번 실행에서 <b>{len(changed)}개 시리즈</b>가 새로 바뀌어 리포트에 반영했습니다."
        body = f"<ul class='upd'>{items}{more}</ul>"
    else:
        head, body = f"원천 {len(rows)}개를 확인했고, 받아 둔 데이터가 이미 최신입니다.", ""
    if failed:
        head += f" <span class='warn'>확인 실패 {len(failed)}개(받아 둔 데이터로 계산): {html.escape(', '.join(r['시리즈'] for r in failed))}</span>"
    cols = ["원천", "시리즈", "결과", "이전 마지막", "최신 마지막", "추가", "개정"]
    tbl = pd.DataFrame([{c: r[c] for c in cols} for r in rows])
    return (f"<div class='updbox{' has' if changed else ''}'><div class='uh'><b>데이터 업데이트</b> · {head}</div>{body}"
            f"{_table('전체 확인 결과', tbl)}</div>")


def _layer_cards(layer_groups) -> str:
    out = []
    for i, layer, group in layer_groups:
        tools = "".join(f"<li class='{SIG_CLASS[r.signal]}'><i></i>{html.escape(r.title.split(' (')[0])}</li>"
                        for r in group)
        out.append(f"<a class='mcard' href='#macro-{i}'><div class='mt'><span class='ln'>{i}</span>{html.escape(layer)}</div>"
                   f"<div class='md'>{html.escape(LAYER_NOTE.get(layer, ''))}</div><ul class='mtools'>{tools}</ul></a>")
    return "".join(out)


def _home(results: list[ToolResult], layer_groups, etc_pages, earnings: list[dict] | None = None,
          reference: dict | None = None) -> str:
    from .links import LINKS

    counts = {s: sum(1 for r in results if r.signal == s) for s in SUMMARY_ORDER}
    dots = "".join(f"<span class='{SIG_CLASS[s]}'><i></i>{SIG_TEXT[s]} {counts[s]}</span>"
                   for s in SUMMARY_ORDER if counts[s])
    layers = " · ".join(f"{i}. {html.escape(l)}" for i, l, _ in layer_groups)
    views = [f"<a class='mcard main' href='#macro'><div class='mt'>매크로 분석</div>"
             f"<div class='md'>도구 {len(results)}개를 SD의 읽는 순서로 — {layers}</div>"
             f"<div class='mdots'>{dots}</div></a>"]
    if earnings is not None:
        latest = ", ".join(f"{d.get('company') or d.get('ticker')} {d.get('period')}" for d in earnings[:3]) or "아직 없음"
        views.append(f"<a class='mcard' href='#earnings'><div class='mt'>실적·컨콜</div>"
                     f"<div class='md'>주요 기업 실적 숫자 · 가이던스 · 질의응답 쟁점 · 매크로 연결 — 정리본 {len(earnings)}개</div>"
                     f"<div class='md'>최근: {html.escape(latest)}</div></a>")
    if etc_pages:
        views.append(f"<a class='mcard' href='#{etc_pages[0][0]}'><div class='mt'>매크로 차트</div>"
                     f"<div class='md'>{' · '.join(html.escape(n) for _, n in etc_pages)} — 판단 없이 시장 흐름만</div></a>")
    if reference:
        n = len(reference["items"])
        views.append(f"<a class='mcard' href='#ref'><div class='mt'>참고자료</div>"
                     f"<div class='md'>유용한 사이트(데이터·연준·한국은행·BIS) + SD 인터뷰·강연·기고 {n}개 정리와 그걸 합친 판단 틀</div></a>")
    ext = "".join(f"<a class='mcard ext' href='{html.escape(u)}' target='_blank' rel='noopener'>"
                  f"<div class='mt'>{html.escape(n)} <span class='arrow'>↗</span></div><div class='md'>{html.escape(d)}</div>"
                  f"<div class='url'>{html.escape(u)}</div></a>" for n, u, d in LINKS)
    return f"""
<h3 class='mh'>메뉴</h3><div class='menu'>{''.join(views)}</div>
<h3 class='mh'>매크로 분석 — 읽는 순서 <span class='mhs'>원인 → 방향 → 표현 → 확인 → 크기</span></h3><div class='menu'>{_layer_cards(layer_groups)}</div>
<h3 class='mh'>외부 자료 <span class='mhs'>새 탭에서 열림 · 전체 목록(데이터·연준·한국은행·BIS 등)은 <a href='#ref-sites'>참고자료 → 유용한 사이트</a></span></h3><div class='menu'>{ext}</div>
<div class='order'><b>용도 태그</b> — 각 도구는 '타이밍'(언제)·'사이즈'(얼마나)·'배경'(수년 구조)으로 구분됩니다. SD는 밸류에이션으로 타이밍을 잡지 않았습니다. 규칙의 원문 대조: 참고자료 · RULES.md</div>"""


CSS = """
:root{--bg:#f6f5f2;--panel:#fff;--ink:#1d1f23;--mute:#5f646c;--line:#e3e1dc;--soft:#f1efea;
  --ok:#2a9d6a;--watch:#c08a00;--alert:#d14343;--na:#8a8f98;--link:#2f6fdb}
@media (prefers-color-scheme: dark){:root{--bg:#16171a;--panel:#1f2125;--ink:#e9e7e2;--mute:#a0a6ae;--line:#30333a;--soft:#272a2f;--link:#7fa7ea}}
*{box-sizing:border-box} html{scroll-padding-top:64px}
body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.65 -apple-system,"Apple SD Gothic Neo","Pretendard","Noto Sans KR",sans-serif;word-break:keep-all}
header.top{position:sticky;top:0;z-index:5;background:var(--bg);border-bottom:1px solid var(--line)}
header.top .in{max-width:1120px;margin:0 auto;padding:8px 16px;display:flex;gap:4px;align-items:center;overflow-x:auto;scrollbar-width:thin}
header.top .brand{flex:none;font-weight:750;margin-right:8px;color:var(--ink);text-decoration:none;letter-spacing:-.3px}
header.top a[data-v], header.top a.extl{flex:none;font-size:13.5px;color:var(--ink);text-decoration:none;padding:5px 12px;border-radius:99px;border:1px solid transparent}
header.top a[data-v]:hover, header.top a.extl:hover{border-color:var(--line)}
header.top a.on{background:var(--ink);color:var(--bg)}
header.top a.extl{color:var(--link)}
header.top .sp{flex:1 0 8px}
.lnav{display:flex;gap:6px;flex-wrap:wrap;align-items:center;margin:4px 0 14px;font-size:13.5px}
.lnav a{padding:4px 11px;border:1px solid var(--line);border-radius:99px;text-decoration:none;color:var(--ink)}
.lnav a.on{background:var(--ink);color:var(--bg)}
.mcard.main{border-width:2px}
main{max-width:1120px;margin:0 auto;padding:24px 16px 64px}
h1{font-size:28px;margin:0 0 6px;letter-spacing:-.4px} .sub{color:var(--mute);font-size:14px}
.view{display:none} .view.on{display:block}
.vt{font-size:24px;margin:0 0 4px;letter-spacing:-.3px}
.demo{background:#fff3cd;color:#6b4e00;border:1px solid #e8cf7a;padding:10px 14px;border-radius:8px;margin:14px 0;font-size:14px}
.mh{font-size:15px;margin:30px 0 10px} .mhs{font-size:12.5px;font-weight:400;color:var(--mute);margin-left:6px}
.menu{display:grid;grid-template-columns:repeat(auto-fill,minmax(min(100%,300px),1fr));gap:12px}
.mcard{display:block;background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:16px 18px;color:inherit;text-decoration:none;transition:border-color .15s,transform .15s}
.mcard:hover{border-color:var(--mute);transform:translateY(-1px)}
.mcard .mt{font-size:18px;font-weight:700;display:flex;align-items:center;gap:8px;letter-spacing:-.2px}
.mcard .md{font-size:14px;color:var(--mute);margin-top:4px;line-height:1.5}
.mcard .mdots{display:flex;gap:12px;flex-wrap:wrap;margin-top:10px;font-size:13px} .mcard .mdots span{display:inline-flex;align-items:center;gap:5px}
.mcard .mtools{list-style:none;margin:10px 0 0;padding:0;display:flex;flex-wrap:wrap;gap:4px 12px;font-size:13px}
.mcard .mtools li{display:inline-flex;align-items:center;gap:5px}
.mcard.ext{border-style:dashed} .mcard .arrow{color:var(--link)} .mcard .url{font-size:12px;color:var(--link);margin-top:8px}
.ln{flex:none;width:28px;height:28px;border-radius:50%;background:var(--ink);color:var(--bg);display:inline-flex;align-items:center;justify-content:center;font-weight:700;font-size:14px}
i{display:inline-block;width:9px;height:9px;border-radius:50%;background:var(--na);flex:none}
.ok i{background:var(--ok)} .watch i{background:var(--watch)} .alert i{background:var(--alert)}
.summary{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,300px),1fr));gap:12px;margin:16px 0 8px}
.scol{background:var(--panel);border:1px solid var(--line);border-top:4px solid var(--na);border-radius:10px;padding:12px 16px}
.scol.ok{border-top-color:var(--ok)} .scol.watch{border-top-color:var(--watch)} .scol.alert{border-top-color:var(--alert)}
.scol h3{margin:0 0 6px;font-size:16px;display:flex;align-items:center;gap:8px}
.cnt{font-size:12px;font-weight:500;color:var(--mute);background:var(--soft);border-radius:99px;padding:1px 8px}
.scol ul{list-style:none;margin:0;padding:0} .scol li+li{border-top:1px solid var(--line)}
.scol a{display:block;padding:9px 0;color:inherit;text-decoration:none}
.scol a b{display:block;font-size:15px} .scol a span{display:block;font-size:13.5px;color:var(--mute);line-height:1.5}
.scol a:hover b{color:var(--link)}
.layer{display:flex;gap:14px;align-items:flex-start;margin:4px 0 10px}
.layer .ln{width:34px;height:34px;font-size:16px}
.layer h2{margin:0;font-size:24px;letter-spacing:-.3px} .layer p{margin:2px 0 0;color:var(--mute);font-size:14px}
.jump{display:flex;gap:6px;flex-wrap:wrap;margin:6px 0 0}
.jump a{display:inline-flex;align-items:center;gap:6px;font-size:13px;color:var(--ink);text-decoration:none;padding:4px 10px;border:1px solid var(--line);border-radius:99px;background:var(--panel)}
.tags{display:flex;gap:6px;flex-wrap:wrap;margin-top:6px} .tag{font-size:12px;color:var(--mute);background:var(--soft);border-radius:4px;padding:1px 8px}
.order{margin:28px 0 0;padding:12px 16px;border:1px dashed var(--line);border-radius:10px;font-size:14px;color:var(--mute)}
.order b{color:var(--ink)}
iframe.ov{width:100%;height:960px;border:0;display:block;margin-top:10px;background:transparent}
.tool{background:var(--panel);border:1px solid var(--line);border-left:5px solid var(--na);border-radius:10px;padding:20px 24px;margin-top:20px}
.tool.overview{border-left-color:var(--link);margin-top:12px}
.tool.ok{border-left-color:var(--ok)} .tool.watch{border-left-color:var(--watch)} .tool.alert{border-left-color:var(--alert)}
.th{display:flex;align-items:center;gap:10px;flex-wrap:wrap} .th h2{font-size:21px;margin:0;letter-spacing:-.3px}
.asof{margin-left:auto;font-size:13px;color:var(--mute)}
.badge{font-size:13px;font-weight:600;padding:2px 10px;border-radius:99px;background:var(--na);color:#fff;white-space:nowrap}
.badge.ok{background:var(--ok)} .badge.watch{background:var(--watch)} .badge.alert{background:var(--alert)}
.rule{margin:6px 0 0;color:var(--mute);font-size:14px}
.concept{font-size:12px;border:1px solid var(--line);border-radius:4px;padding:0 6px;margin-right:6px;white-space:nowrap}
.headline{font-size:17.5px;font-weight:600;line-height:1.55;margin:14px 0;padding:12px 16px;background:var(--soft);border-radius:8px}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,170px),1fr));gap:10px;margin:12px 0}
.kpi{border:1px solid var(--line);border-radius:8px;padding:10px 14px}
.kpi .k{font-size:13px;color:var(--mute);line-height:1.35} .kpi .v{font-size:22px;font-weight:650;font-variant-numeric:tabular-nums;margin-top:2px}
dl.more{display:grid;grid-template-columns:repeat(auto-fill,minmax(min(100%,250px),1fr));gap:2px 24px;margin:4px 0 12px;font-size:14px}
dl.more div{display:flex;justify-content:space-between;gap:12px;padding:5px 0;border-bottom:1px dashed var(--line)}
dl.more dt{color:var(--mute)} dl.more dd{margin:0;font-weight:600;font-variant-numeric:tabular-nums;text-align:right}
.charts{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,460px),1fr));gap:12px;margin-top:8px}
.chart{min-height:340px;border:1px solid var(--line);border-radius:8px;padding:4px 6px}
details.fold{margin-top:10px;border:1px solid var(--line);border-radius:8px;padding:0 14px}
details.fold summary{cursor:pointer;padding:9px 0;font-size:14px;font-weight:600;list-style-position:inside}
details.fold[open] summary{border-bottom:1px solid var(--line);margin-bottom:8px}
.tblwrap{overflow-x:auto;padding-bottom:10px}
.dlinks{display:flex;flex-wrap:wrap;gap:6px;align-items:center;margin-top:12px;font-size:13px}
.dlinks b{font-size:13px;color:var(--mute);margin-right:4px}
a.dl{display:inline-flex;align-items:center;gap:5px;padding:3px 10px;border:1px solid var(--line);border-radius:99px;color:var(--link);text-decoration:none;background:var(--panel)}
a.dl span{color:var(--mute);font-size:11.5px} a.dl:hover{border-color:var(--link)}
.updbox{margin:16px 0 0;padding:12px 16px;border:1px solid var(--line);border-radius:10px;background:var(--panel);font-size:14px}
.updbox.has{border-color:var(--link)} .updbox .uh{color:var(--mute)} .updbox .uh b{color:var(--ink)}
.updbox ul.upd{margin:8px 0 0;padding-left:20px} .updbox .warn{color:var(--alert)}
.tbl.fc td{white-space:normal;text-align:left;vertical-align:top} .tbl.fc th{text-align:left} .tbl.fc a{color:var(--link)}
.tbl{border-collapse:collapse;font-size:14px;font-variant-numeric:tabular-nums}
.tbl th{font-size:12.5px;color:var(--mute);font-weight:600;background:var(--soft)}
.tbl th,.tbl td{border-bottom:1px solid var(--line);padding:6px 14px;text-align:right;white-space:nowrap}
.tbl th:first-child,.tbl td:first-child{text-align:left} .tbl tbody tr:hover{background:var(--soft)}
.notes{font-size:14.5px;padding-left:20px;margin:6px 0} .notes li+li{margin-top:6px}
.src{font-size:13px;color:var(--mute);padding:6px 0 12px} .src a{color:var(--link)}
.tid{font-size:11px;color:var(--mute);margin-top:12px}
pre{white-space:pre-wrap;font-size:12px} footer{color:var(--mute);font-size:13px;margin-top:40px}
@media (max-width:600px){.tool{padding:16px} .asof{margin-left:0;width:100%} h1{font-size:23px}}
"""

JS = """
function theme(){const d=matchMedia('(prefers-color-scheme: dark)').matches;
  return {ink:d?'#c9c7c2':'#3a3d42', grid:d?'#2c2f35':'#ebe9e4', btn:d?'#2a2d33':'#f1efea', act:d?'#4a4f58':'#d9d6cf', hov:d?'#26282d':'#fff'};}
// 보이는 기간에 맞춰 세로축을 다시 잡는다 (Plotly는 x를 좁혀도 y를 전체 기간 기준으로 둔다)
function fitY(gd){
  const r=gd.layout.xaxis.range; if(!r) return;
  const a=String(r[0]).slice(0,10), b=String(r[1]).slice(0,10), upd={};
  for(const ax of ['y','y2']){
    let lo=Infinity, hi=-Infinity;
    for(const t of gd.data){ if((t.yaxis||'y')!==ax || t.visible==='legendonly') continue;
      t.x.forEach((x,i)=>{const v=t.y[i]; if(v!=null && x>=a && x<=b){lo=Math.min(lo,v);hi=Math.max(hi,v);}}); }
    if(!isFinite(lo)) continue;
    if(gd.data.some(t=>t.type==='bar'&&(t.yaxis||'y')===ax)){lo=Math.min(lo,0);hi=Math.max(hi,0);}
    for(const s of gd.layout.shapes||[]) if(s.type==='line'&&s.yref!=='paper'&&ax==='y'){lo=Math.min(lo,s.y0);hi=Math.max(hi,s.y0);}
    const p=(hi-lo)*0.07||1; upd[(ax==='y'?'yaxis':'yaxis2')+'.range']=[lo-p,hi+p];
  }
  Plotly.relayout(gd, upd);
}
function drawOne(gd){
  const sp=SPECS[gd.id], t=theme();
  const L=JSON.parse(JSON.stringify(sp.layout));
  L.font={color:t.ink, family:'-apple-system,"Apple SD Gothic Neo","Noto Sans KR",sans-serif'};
  if(L.xaxis) L.xaxis.gridcolor=t.grid; if(L.yaxis) L.yaxis.gridcolor=t.grid; if(L.yaxis2) L.yaxis2.gridcolor='rgba(0,0,0,0)';
  if(L.xaxis&&L.xaxis.rangeselector){L.xaxis.rangeselector.bgcolor=t.btn; L.xaxis.rangeselector.activecolor=t.act;}
  (L.updatemenus||[]).forEach(u=>{u.bgcolor=t.btn; u.activecolor=t.act; u.bordercolor=t.grid;});
  L.hoverlabel={bgcolor:t.hov, font:{color:t.ink}};
  Plotly.react(gd, sp.data, L, {responsive:true, displayModeBar:false}).then(()=>{
    fitY(gd); gd._drawn=true;
    if(!gd._fit){ gd._fit=true; gd.on('plotly_relayout', e=>{ if(Object.keys(e).some(k=>k.startsWith('xaxis'))) fitY(gd); }); }
  });
}
// 화면(view)이 처음 보일 때 그린다 — 숨겨진 상태에서 그리면 폭이 0이 된다
function prepare(view){
  view.querySelectorAll('.chart').forEach(gd=>{ if(!gd._drawn) drawOne(gd); else Plotly.Plots.resize(gd); });
  view.querySelectorAll('iframe.ov[data-srcdoc]').forEach(f=>{
    const fit=()=>{try{const d=f.contentDocument; if(d&&d.body) f.style.height=(d.documentElement.scrollHeight+4)+'px';}catch(e){}};
    f.addEventListener('load',()=>{fit(); try{new ResizeObserver(fit).observe(f.contentDocument.body);}catch(e){} setTimeout(fit,800);});
    f.srcdoc=f.dataset.srcdoc; f.removeAttribute('data-srcdoc');
  });
}
function route(){
  const h=decodeURIComponent(location.hash.slice(1)) || 'home';
  let view=document.getElementById('v-'+h), target=null;
  if(!view){ target=document.getElementById(h); view=target ? target.closest('.view') : document.getElementById('v-home'); }
  document.querySelectorAll('.view').forEach(v=>v.classList.toggle('on', v===view));
  const key=view.id.slice(2);
  document.querySelectorAll('header.top a[data-v]').forEach(a=>a.classList.toggle('on', a.dataset.v===key || key.startsWith(a.dataset.v+'-')));
  document.title=view.dataset.title+' · '+TITLE;
  prepare(view);
  if(target && target.tagName==='DETAILS') target.open=true;
  if(target && target!==view) target.scrollIntoView(); else window.scrollTo(0,0);
}
window.addEventListener('hashchange', route);
route();
matchMedia('(prefers-color-scheme: dark)').addEventListener('change', ()=>document.querySelectorAll('.chart').forEach(gd=>{ if(gd._drawn) drawOne(gd); }));
"""


def render(results: list[ToolResult], recessions, demo: bool = False, as_of: str | None = None,
           title: str = "SD 매크로 대시보드", chart_html: str | None = None, ngdp: dict | None = None,
           updates: list[dict] | None = None, earnings: list[dict] | None = None,
           reference: dict | None = None, markets: dict | None = None) -> str:
    """메뉴: 홈 / 매크로 분석(요약 + 1~5층) / 실적·컨콜 / 매크로 차트(지수·채권·원자재·통화·한눈 차트·명목GDP) / 참고자료.
    화면은 #해시로 하나씩 연다. 탭은 data-v 접두어로 하위 화면까지 켜진다(macro-3 → macro)."""
    from .links import LINKS

    charts_js, layer_groups, layer_views = [], [], []
    ngdp_divs = []
    if ngdp:
        for ch in ngdp["charts"]:
            cid = f"c{len(charts_js)}"
            charts_js.append((cid, chart_spec(ch, recessions)))
            ngdp_divs.append(f"<div class='chart' id='{cid}'></div>")
    layer_of = {r.tool: get_tool(r.tool).layer for r in results}
    for i, layer in enumerate(LAYERS, 1):
        group = [r for r in results if layer_of[r.tool] == layer]
        if not group:
            continue
        layer_groups.append((i, layer, group))
        secs = []
        for r in group:
            divs = []
            for ch in r.charts:
                cid = f"c{len(charts_js)}"
                charts_js.append((cid, chart_spec(ch, recessions)))
                divs.append(f"<div class='chart' id='{cid}'></div>")
            secs.append(_section(r, divs))
        jump = "".join(f"<a class='{SIG_CLASS[r.signal]}' href='#{r.tool}'><i></i>{html.escape(r.title.split(' (')[0])}</a>"
                       for r in group)
        layer_views.append(
            f"<div class='view' id='v-macro-{i}' data-title='매크로 분석 · {i}. {html.escape(layer)}'>"
            f"<div class='layer'><span class='ln'>{i}</span><div><h2>{html.escape(layer)}</h2>"
            f"<p>{html.escape(LAYER_NOTE.get(layer, ''))}</p></div></div>"
            f"__LNAV{i}__<div class='jump'>{jump}</div>{''.join(secs)}</div>")

    lnav = lambda cur: ("<div class='lnav'><b>매크로 분석</b>"
                        + f"<a href='#macro' class='{'on' if cur == 0 else ''}'>요약</a>" + "".join(
        f"<a href='#macro-{i}' class='{'on' if i == cur else ''}'>{i}. {html.escape(layer)}</a>" for i, layer, _ in layer_groups)
        + "</div>")
    layer_views = [v.replace(f"__LNAV{i}__", lnav(i)) for (i, _l, _g), v in zip(layer_groups, layer_views)]
    banner = ("<div class='demo'>DEMO — 합성(가짜) 데이터입니다. 화면·로직 확인용이며 실제 시장 상태가 아닙니다. "
              "실데이터: <code>python -m druck run</code></div>") if demo else ""
    gen = datetime.now(timezone(timedelta(hours=9))).strftime("%Y-%m-%d %H:%M") + " (한국시간)"
    sub = (f"생성 {gen}" + (" · 기준 시점 " + html.escape(as_of) if as_of else "")
           + f" · 데이터 {'합성(DEMO)' if demo else 'FRED / Yahoo'} · 차트의 회색 음영 = NBER 경기침체")
    def add_chart(spec: dict) -> str:
        cid = f"c{len(charts_js)}"
        charts_js.append((cid, spec))
        return cid

    etc_pages = [(f"chart-{g['key']}", g["name"]) for g in (markets or {}).get("groups", [])]
    etc_pages += ([("chart-overview", "한눈 차트")] if chart_html else []) + ([("chart-ngdp", "명목GDP vs 금리")] if ngdp else [])
    enav = lambda cur: ("<div class='lnav'><b>매크로 차트</b>" + "".join(
        f"<a href='#{k}' class='{'on' if k == cur else ''}'>{html.escape(n)}</a>" for k, n in etc_pages) + "</div>")
    market_html = m_views(markets, sub, enav, add_chart)
    tabs = ["<a href='#home' data-v='home'>홈</a>",
            "<a href='#macro' data-v='macro'>매크로 분석</a>"]
    if earnings is not None:
        tabs.append("<a href='#earnings' data-v='earnings'>실적·컨콜</a>")
    if etc_pages:
        tabs.append(f"<a href='#{etc_pages[0][0]}' data-v='chart'>매크로 차트</a>")
    tabs.append("<a href='#ref' data-v='ref'>참고자료</a>")
    tabs.append("<span class='sp'></span>")
    tabs += [f"<a class='extl' href='{html.escape(u)}' target='_blank' rel='noopener'>{html.escape(n)} ↗</a>"
             for n, u, _ in LINKS]
    specs = json.dumps(dict(charts_js), ensure_ascii=False)
    return f"""<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>{html.escape(title)}</title>
<script src="{PLOTLY}"></script>
<style>{CSS}{E_CSS}{R_CSS}{M_CSS}</style></head><body>
<header class='top'><div class='in'><a class='brand' href='#home'>내 주식 사이트</a>{''.join(tabs)}</div></header>
<main>
<div class='view' id='v-home' data-title='홈'>
<h1>{html.escape(title)}</h1>
<div class='sub'>{sub}</div>
{banner}
{m_strip(markets)}
{_updates(updates)}
{_home(results, layer_groups, etc_pages, earnings, reference)}
</div>
<div class='view' id='v-macro' data-title='매크로 분석'>
<h2 class='vt'>매크로 분석</h2><div class='sub'>{sub} · 항목을 누르면 해당 도구로 이동합니다</div>
{lnav(0)}
{banner}
{_summary(results)}
<h3 class='mh'>읽는 순서 <span class='mhs'>원인 → 방향 → 표현 → 확인 → 크기</span></h3>
<div class='menu'>{_layer_cards(layer_groups)}</div>
</div>
{''.join(layer_views)}
{market_html}
<div class='view' id='v-chart-overview' data-title='매크로 차트 · 한눈 차트'>
<h2 class='vt'>한눈 차트 — 미국 금리 · 유가 · 달러 · 기업이익</h2><div class='sub'>{sub}</div>
{enav('chart-overview')}
{_overview(chart_html)}
</div>
{_ngdp_view(ngdp, ngdp_divs, sub).replace('__ENAV__', enav('chart-ngdp'))}
{e_view(earnings, sub) if earnings is not None else ''}
{r_view(reference, sub)}
<footer>규칙과 인용은 SD 인터뷰 원자료(chian.io 지식 베이스·interviewrecords.com 등)를 바탕으로 한 해석입니다. 투자 권유가 아니며, SD 본인도 "3주마다 생각을 바꾼다"고 말합니다.</footer>
</main>
<script>
const SPECS = {specs};
const TITLE = {json.dumps(title, ensure_ascii=False)};
{JS}
{E_JS}
</script>
</body></html>"""
