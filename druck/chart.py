"""한눈 차트 — 미국 금리·유가·달러·기업이익을 한 차트에 겹쳐 보는 HTML.

판단 규칙 없이 '흐름'만 눈으로 보기 위한 것. 보기 방식 세 가지:
 - 실제값: 각자 단위 그대로, 축 4개
 - 시작=100: 보이는 구간의 첫 값을 100으로 맞춰 상대 흐름 비교 (금리는 오른쪽 축에 % 그대로)
 - 전년비: 유가·달러·이익은 % 변화, 금리는 %p 변화 (하이먼 회귀가 쓰던 형태)
확대하면 '시작=100' 기준점과 세로축 범위가 보이는 구간에 맞춰 다시 계산된다.

  python -m druck chart --open
"""
from __future__ import annotations

import html
import json
import math
from datetime import datetime

import pandas as pd

from .core import Context, DataUnavailable
from .report import PLOTLY
from .stats import to_freq
from .tools.profit_headwind import dollar_index

START = "1970-01-01"


def _pts(s: pd.Series) -> dict:
    s = s[s.index >= START].dropna()
    return {"x": [d.strftime("%Y-%m-%d") for d in s.index],
            "y": [None if math.isnan(v) else round(float(v), 4) for v in s.to_numpy()]}


def _yoy(s: pd.Series, periods: int, kind: str) -> pd.Series:
    return s - s.shift(periods) if kind == "rate" else (s / s.shift(periods) - 1.0) * 100.0


def collect(ctx: Context) -> list[dict]:
    """차트에 올릴 시리즈. 못 받은 건 건너뛴다."""
    specs = [
        # key, 이름, 단위, 종류(rate=%p 변화 / level=% 변화), 색, 처음에 보일지, 실제값 축, 데이터 함수
        ("gs10", "미 10년물 금리", "%", "rate", "#2f6fdb", True, "y",
         lambda: to_freq(ctx.series("GS10"), "M"), "FRED GS10 (월평균)"),
        ("ff", "기준금리", "%", "rate", "#7fa7ea", False, "y",
         lambda: to_freq(ctx.series("FEDFUNDS"), "M"), "FRED FEDFUNDS (월평균)"),
        ("oil", "WTI 유가", "$", "level", "#e0782b", True, "y2",
         lambda: to_freq(ctx.series("WTISPLC"), "M"), "FRED WTISPLC (월평균, 배럴당 달러)"),
        ("usd", "달러지수(광의)", "", "level", "#2a9d6a", True, "y3",
         lambda: dollar_index(ctx), "FRED DTWEXBGS, 2006년 이전은 TWEXBMTH를 비율로 연결 (월평균)"),
        ("cp", "기업이익(세후)", "조$", "level", "#b8448a", True, "y4",
         lambda: to_freq(ctx.series("CP"), "Q") / 1000.0, "FRED CP (분기, 연율, 조 달러)"),
    ]
    out = []
    for key, name, unit, kind, color, on, axis, fn, src in specs:
        try:
            s = fn()
        except DataUnavailable:
            continue
        periods = 4 if key == "cp" else 12
        y = _yoy(s, periods, kind)
        last = s.dropna()
        out.append({
            "key": key, "name": name, "unit": unit, "kind": kind, "color": color, "on": on, "axis": axis,
            "src": src, "raw": _pts(s), "yoy": _pts(y),
            "last": {"date": last.index[-1].strftime("%Y-%m-%d"), "v": round(float(last.iloc[-1]), 4),
                     "yoy": None if pd.isna(y.iloc[-1]) else round(float(y.iloc[-1]), 2)},
        })
    if not out:
        raise DataUnavailable("차트에 올릴 데이터를 하나도 받지 못했습니다")
    return out


def render(ctx: Context, demo: bool = False, as_of: str | None = None, embed: bool = False) -> str:
    """embed=True면 메인 리포트 안에 끼워 넣을 용도로 제목·설명을 숨긴다."""
    series = collect(ctx)
    rec = [[a.strftime("%Y-%m-%d"), (b + pd.offsets.MonthEnd(0)).strftime("%Y-%m-%d")]
           for a, b in ctx.recessions() if b >= pd.Timestamp(START)]
    payload = json.dumps({"series": series, "rec": rec}, ensure_ascii=False)
    gen = datetime.now().strftime("%Y-%m-%d %H:%M")
    banner = ("<div class='demo'>DEMO — 합성(가짜) 데이터입니다. 실데이터: <code>python -m druck chart</code></div>"
              if demo else "")
    sources = "".join(f"<li><b>{html.escape(s['name'])}</b> — {html.escape(s['src'])}</li>" for s in series)
    page = PAGE.format(plotly=PLOTLY, payload=payload, banner=banner, sources=sources,
                       sub=f"생성 {gen}" + (f" · 기준 시점 {html.escape(as_of)}" if as_of else "")
                       + f" · 데이터 {'합성(DEMO)' if demo else 'FRED'} · 회색 음영 = NBER 경기침체")
    return page.replace("<body>", "<body class='embed'>", 1) if embed else page


PAGE = """<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>금리·유가·달러·이익</title>
<script src="{plotly}"></script>
<style>
:root{{--bg:#f6f5f2;--panel:#fff;--ink:#1d1f23;--mute:#666b73;--line:#e3e1dc;--acc:#1d1f23;--accink:#fff;--up:#d14343;--dn:#2f6fdb}}
@media (prefers-color-scheme: dark){{:root{{--bg:#16171a;--panel:#1f2125;--ink:#e9e7e2;--mute:#9aa0a8;--line:#30333a;--acc:#e9e7e2;--accink:#16171a;--up:#ef6b6b;--dn:#6d9cf0}}}}
*{{box-sizing:border-box}} body{{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 -apple-system,"Apple SD Gothic Neo","Pretendard","Noto Sans KR",sans-serif}}
main{{max-width:1280px;margin:0 auto;padding:24px 16px 48px}}
h1{{font-size:24px;margin:0 0 4px;letter-spacing:-.3px}} .sub{{color:var(--mute);font-size:13px}}
.demo{{background:#fff3cd;color:#6b4e00;border:1px solid #e8cf7a;padding:10px 14px;border-radius:8px;margin:12px 0;font-size:14px}}
.cards{{display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:8px;margin:16px 0 12px}}
.card{{background:var(--panel);border:1px solid var(--line);border-top:4px solid var(--c);border-radius:8px;padding:9px 12px;cursor:pointer;user-select:none}}
.card.off{{opacity:.4}} .card .n{{font-size:13px;color:var(--mute)}} .card .v{{font-size:20px;font-weight:650;font-variant-numeric:tabular-nums}}
.card .d{{font-size:12px;color:var(--mute);font-variant-numeric:tabular-nums}} .up{{color:var(--up)}} .dn{{color:var(--dn)}}
.bar{{display:flex;flex-wrap:wrap;gap:8px 16px;align-items:center;margin:4px 0 8px}}
.seg{{display:inline-flex;border:1px solid var(--line);border-radius:8px;overflow:hidden;background:var(--panel)}}
.seg button{{border:0;background:none;color:var(--ink);padding:6px 12px;font:inherit;font-size:14px;cursor:pointer}}
.seg button+button{{border-left:1px solid var(--line)}} .seg button.on{{background:var(--acc);color:var(--accink)}}
.hint{{font-size:13px;color:var(--mute)}}
.panel{{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:8px 4px}}
#chart{{height:min(72vh,640px);min-height:420px}}
.notes{{color:var(--mute);font-size:13px;padding-left:18px;margin-top:16px}}
body.embed main{{padding:4px 2px 8px}} body.embed main>h1, body.embed .sub, body.embed .demo, body.embed .notes{{display:none}}
body.embed .cards{{margin-top:4px}}
</style></head><body><main>
<h1>미국 금리 · 유가 · 달러 · 기업이익</h1>
<div class="sub">{sub}</div>
{banner}
<div class="cards" id="cards"></div>
<div class="bar">
  <div class="seg" id="mode">
    <button data-m="raw" class="on">실제값</button><button data-m="idx">시작=100</button><button data-m="yoy">전년비</button>
  </div>
  <div class="seg" id="range">
    <button data-y="3">3년</button><button data-y="5">5년</button><button data-y="10">10년</button><button data-y="20" class="on">20년</button><button data-y="0">전체</button>
  </div>
  <span class="hint" id="hint"></span>
</div>
<div class="panel"><div id="chart"></div></div>
<ul class="notes">
  <li>위 카드를 누르면 그 선을 켜고 끕니다. 차트를 드래그하면 확대, 더블클릭하면 원래대로 돌아갑니다.</li>
  <li><b>시작=100</b>은 보이는 구간 첫 달을 100으로 맞춥니다. 금리는 수준 자체가 의미 있어 오른쪽 축에 %로 그대로 둡니다.</li>
  <li><b>전년비</b>: 유가·달러·기업이익은 1년 전 대비 %, 금리는 1년 전 대비 %p 변화. SD·하이먼이 2000년에 본 게 이 세 가지가 함께 오르는 모습이었습니다.</li>
  <li>기업이익은 분기 데이터라 발표가 늦습니다(최근 분기가 1~2분기 뒤처짐).</li>
  {sources}
</ul>
</main>
<script>
const D = {payload};
const AX_RAW = {{y:{{title:'금리 %',side:'left'}}, y2:{{title:'WTI $',side:'right'}}, y3:{{title:'달러지수',side:'right',pos:1}}, y4:{{title:'기업이익 조$',side:'left',pos:0}}}};
let mode='raw', years=20, xr=null;
const on = Object.fromEntries(D.series.map(s=>[s.key,s.on]));

function dark(){{return matchMedia('(prefers-color-scheme: dark)').matches;}}
function fmt(v,d){{return v==null?'-':v.toLocaleString('ko-KR',{{minimumFractionDigits:d,maximumFractionDigits:d}});}}
function dec(s){{return s.key==='usd'?1:2;}}

function cards(){{
  document.getElementById('cards').innerHTML = D.series.map(s=>{{
    const L=s.last, u=s.kind==='rate'?'%p':'%', cls=L.yoy==null?'':(L.yoy>0?'up':'dn');
    const val = s.unit==='$'?'$'+fmt(L.v,2):fmt(L.v,dec(s))+(s.unit&&s.unit!=='$'?' '+s.unit:'');
    return `<div class="card${{on[s.key]?'':' off'}}" style="--c:${{s.color}}" data-k="${{s.key}}">
      <div class="n">${{s.name}}</div><div class="v">${{val}}</div>
      <div class="d">${{L.date.slice(0,7)}} · 1년 전 대비 <span class="${{cls}}">${{L.yoy==null?'-':(L.yoy>0?'+':'')+fmt(L.yoy,s.kind==='rate'?2:1)+u}}</span></div></div>`;
  }}).join('');
  document.querySelectorAll('.card').forEach(c=>c.onclick=()=>{{on[c.dataset.k]=!on[c.dataset.k];cards();draw();}});
}}

function lastDate(){{let m='';for(const s of D.series){{const x=s.raw.x;if(x.length&&x[x.length-1]>m)m=x[x.length-1];}}return m;}}
function firstDate(){{let m='9999';for(const s of D.series){{if(s.raw.x.length&&s.raw.x[0]<m)m=s.raw.x[0];}}return m;}}
function presetRange(){{
  const end=lastDate(); if(!years) return [firstDate(), end];
  const d=new Date(end); d.setFullYear(d.getFullYear()-years); return [d.toISOString().slice(0,10), end];
}}

// 모드별 (x, y, 축, 단위)
function view(s){{
  if(mode==='raw') return {{x:s.raw.x, y:s.raw.y, axis:s.axis, unit:s.unit}};
  if(mode==='yoy') return {{x:s.yoy.x, y:s.yoy.y, axis:s.kind==='rate'?'y2':'y', unit:s.kind==='rate'?'%p':'%'}};
  if(s.kind==='rate') return {{x:s.raw.x, y:s.raw.y, axis:'y2', unit:'%'}};
  const i=s.raw.x.findIndex((x,j)=>x>=xr[0] && s.raw.y[j]!=null);
  const b=i<0?null:s.raw.y[i];
  return {{x:s.raw.x, y:s.raw.y.map(v=>v==null||!b?null:v/b*100), axis:'y', unit:''}};
}}

function yRange(vals, extra){{
  let lo=Infinity, hi=-Infinity;
  for(const v of vals.concat(extra||[])) if(v!=null){{lo=Math.min(lo,v);hi=Math.max(hi,v);}}
  if(!isFinite(lo)) return undefined;
  const p=(hi-lo)*0.06||1; return [lo-p, hi+p];
}}

function draw(){{
  const dk=dark(), ink=dk?'#c9c7c2':'#3a3d42', grid=dk?'#2c2f35':'#ebe9e4';
  const traces=[], vis={{}};
  for(const s of D.series){{
    if(!on[s.key]) continue;
    const v=view(s);
    const hv = s.unit==='$'&&mode==='raw' ? '$%{{y:,.2f}}' : (mode==='idx'&&s.kind!=='rate' ? '%{{y:.1f}}' : '%{{y:,.2f}}'+(v.unit&&v.unit!=='$'?' '+v.unit:''));
    traces.push({{x:v.x, y:v.y, name:s.name, yaxis:v.axis, type:'scatter', mode:'lines', connectgaps:true,
      line:{{color:s.color, width:s.key==='ff'?1.4:2, dash:s.key==='ff'?'dot':'solid', shape:s.key==='cp'?'linear':'spline', smoothing:.3}},
      hovertemplate:hv+'<extra>'+s.name+'</extra>'}});
    (vis[v.axis]=vis[v.axis]||[]).push(...v.y.filter((_,j)=>v.x[j]>=xr[0]&&v.x[j]<=xr[1]));
  }}
  const used=Object.keys(vis);
  const L={{paper_bgcolor:'rgba(0,0,0,0)', plot_bgcolor:'rgba(0,0,0,0)', font:{{color:ink, family:'-apple-system,"Apple SD Gothic Neo","Noto Sans KR",sans-serif'}},
    margin:{{l:10,r:10,t:10,b:10}}, hovermode:'x unified', showlegend:false, dragmode:'zoom',
    hoverlabel:{{bgcolor:dk?'#26282d':'#fff', bordercolor:grid, font:{{color:ink}}}},
    xaxis:{{range:xr, gridcolor:grid, type:'date', automargin:true, rangeslider:{{visible:true, thickness:.07, bgcolor:'rgba(0,0,0,0)', bordercolor:grid}}}},
    shapes:D.rec.map(([a,b])=>({{type:'rect', xref:'x', yref:'paper', x0:a, x1:b, y0:0, y1:1, fillcolor:dk?'rgba(255,255,255,.07)':'rgba(0,0,0,.07)', line:{{width:0}}, layer:'below'}}))}};
  const col = ax => (D.series.find(s=>on[s.key] && view(s).axis===ax && s.key!=='ff')||{{}}).color || ink;
  if(mode==='raw'){{
    const left=used.includes('y4'), right=used.includes('y3');
    L.xaxis.domain=[left?0.07:0, right?0.93:1];
    for(const ax of ['y','y2','y3','y4']){{
      const k=ax==='y'?'yaxis':'yaxis'+ax.slice(1), a=AX_RAW[ax], c=col(ax);
      L[k]={{title:{{text:a.title, font:{{color:c, size:12}}}}, tickfont:{{color:c}}, side:a.side, range:yRange(vis[ax]||[]),
        gridcolor:ax==='y'?grid:'rgba(0,0,0,0)', zeroline:false, automargin:true, visible:used.includes(ax)}};
      if(ax!=='y') L[k].overlaying='y';
      if(a.pos!=null) Object.assign(L[k],{{anchor:'free', position:a.pos}});
    }}
    if(!used.includes('y')) L.yaxis.visible=false;
  }} else {{
    const base = mode==='idx' ? [100] : [0];
    L.xaxis.domain=[0,1];
    L.yaxis={{title:{{text:mode==='idx'?'시작=100':'전년비 %', font:{{size:12}}}}, gridcolor:grid, zeroline:false, automargin:true, range:yRange(vis.y||[], base), visible:!!vis.y}};
    L.yaxis2={{title:{{text:mode==='idx'?'금리 %':'금리 전년비 %p', font:{{color:'#2f6fdb', size:12}}}}, tickfont:{{color:'#2f6fdb'}}, overlaying:'y', side:'right',
      gridcolor:'rgba(0,0,0,0)', zeroline:mode==='yoy', zerolinecolor:'rgba(47,111,219,.35)', automargin:true, range:yRange(vis.y2||[], mode==='yoy'?[0]:[]), visible:!!vis.y2}};
    L.shapes.push({{type:'line', xref:'paper', x0:0, x1:1, yref:'y', y0:base[0], y1:base[0], line:{{color:dk?'rgba(255,255,255,.4)':'rgba(0,0,0,.35)', width:1, dash:'dot'}}}});
  }}
  Plotly.react('chart', traces, L, {{responsive:true, displayModeBar:false, scrollZoom:false}});
  document.getElementById('hint').textContent = xr[0].slice(0,7)+' ~ '+xr[1].slice(0,7);
}}

function setRange(r){{xr=[String(r[0]).slice(0,10), String(r[1]).slice(0,10)]; draw();}}

document.querySelectorAll('#mode button').forEach(b=>b.onclick=()=>{{
  document.querySelectorAll('#mode button').forEach(x=>x.classList.toggle('on',x===b)); mode=b.dataset.m; draw();}});
document.querySelectorAll('#range button').forEach(b=>b.onclick=()=>{{
  document.querySelectorAll('#range button').forEach(x=>x.classList.toggle('on',x===b)); years=+b.dataset.y; setRange(presetRange());}});

cards();
xr=presetRange(); draw();
document.getElementById('chart').on('plotly_relayout', e=>{{
  if(e['xaxis.autorange']){{ document.querySelectorAll('#range button').forEach(x=>x.classList.toggle('on', +x.dataset.y===years)); setRange(presetRange()); return; }}
  const r = e['xaxis.range'] || (e['xaxis.range[0]']!==undefined ? [e['xaxis.range[0]'], e['xaxis.range[1]']] : null);
  if(r){{ document.querySelectorAll('#range button').forEach(x=>x.classList.remove('on')); setRange(r); }}
}});
matchMedia('(prefers-color-scheme: dark)').addEventListener('change', draw);
</script>
</body></html>"""
