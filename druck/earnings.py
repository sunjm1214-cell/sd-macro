"""실적·컨콜 정리 화면.

정리본은 저장소의 earnings/<티커>/<기간>.json 에 한 분기씩 둔다 (예: earnings/NVDA/FY2027Q3.json).
파일만 추가하면 리포트의 '실적·컨콜' 탭에 자동으로 나타난다. 형식은 earnings/_template.json 참고.

필드 (없는 필드는 그냥 빠진다)
  ticker, company, sector, period, period_end, call_date, updated
  region        "미국" | "그 외"  — 화면을 미국 / 그 외 국가로 나눈다 (없으면 "미국")
  country       그 외 국가일 때 나라 이름 (예: "대만", "한국")
  ai_role       "인프라" | "활용 사례" | "둘 다" | "" — SD 2026: 인프라보다 활용 사례를 본다
  headline      한 줄 결론
  verdict       "good" | "mixed" | "bad"  (실적 자체의 평가 — 주가 판단 아님)
  numbers       [{label, value, vs, good}]   실적 숫자 (vs = 컨센서스·전년 대비 등, good = true/false/null)
  guidance      [{label, value, note}]       회사 가이던스
  points        ["…"]                       핵심 포인트
  tone          {label, text}               경영진 톤
  qa            [{q, a}]                    질의응답 쟁점
  macro         ["…"]                       매크로 연결 (금리·달러·유가·설비투자 등 → druck 툴과 연결)
  druck_lens    ["…"]                       SD식으로 볼 점
  watch         ["…"]                       다음 분기 확인할 것
  caveats       ["…"]                       확인 못 한 것·주의
  sources       [{title, url}]
"""
from __future__ import annotations

import html
import re
import json
from pathlib import Path

DEFAULT_DIR = Path(__file__).resolve().parent.parent / "earnings"
VERDICT = {"good": ("ok", "좋음"), "mixed": ("watch", "엇갈림"), "bad": ("alert", "나쁨")}
REGIONS = [("us", "미국"), ("intl", "그 외 국가")]


def region(d: dict) -> str:
    """'us' 또는 'intl'."""
    r = str(d.get("region") or "미국").strip()
    return "us" if r in ("미국", "US", "us", "USA") else "intl"


def _anchor(d: dict) -> str:
    f = d.get("_file") or f"{d.get('ticker')}/{d.get('period')}"
    return "e-" + re.sub(r"[^0-9A-Za-z가-힣_-]+", "-", f.rsplit(".", 1)[0].replace("/", "-")).strip("-")


def _first_sentence(t: str) -> str:
    t = str(t or "")
    m = re.search(r"[.。]\s", t)
    return t[: m.start() + 1] if m and m.start() < 140 else (t if len(t) <= 140 else t[:138] + "…")


def load(folder: str | Path | None = None) -> list[dict]:
    """earnings/ 아래 모든 정리본을 읽는다. 깨진 파일은 건너뛰고 경고만 남긴다."""
    folder = Path(folder) if folder else DEFAULT_DIR
    out = []
    if not folder.exists():
        return out
    for p in sorted(folder.glob("*/*.json")):
        if p.name.startswith("_"):
            continue
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            d = {"ticker": p.parent.name, "period": p.stem, "headline": f"정리본을 읽지 못했습니다: {e}",
                 "verdict": "bad"}
        d.setdefault("ticker", p.parent.name)
        d.setdefault("period", p.stem)
        d["_file"] = f"{p.parent.name}/{p.name}"
        out.append(d)
    # 최근 컨콜이 위로
    out.sort(key=lambda d: (d.get("call_date") or "", d.get("ticker")), reverse=True)
    return out


def _e(v) -> str:
    return html.escape(str(v)) if v is not None else ""


def _li(items) -> str:
    return "".join(f"<li>{_e(x)}</li>" for x in items or [])


def _card(d: dict) -> str:
    cls, vtxt = VERDICT.get(d.get("verdict", ""), ("na", "평가 없음"))
    tk = _e(d.get("ticker"))
    nums = "".join(
        f"<div class='kpi'><div class='k'>{_e(n.get('label'))}</div><div class='v'>{_e(n.get('value'))}</div>"
        + (f"<div class='vs {'up' if n.get('good') is True else 'dn' if n.get('good') is False else ''}'>{_e(n.get('vs'))}</div>"
           if n.get("vs") else "") + "</div>" for n in d.get("numbers") or [])
    guide = "".join(f"<tr><td><b>{_e(g.get('label'))}</b></td><td>{_e(g.get('value'))}</td><td>{_e(g.get('note'))}</td></tr>"
                    for g in d.get("guidance") or [])
    qa = "".join(f"<div class='qa'><div class='q'>Q. {_e(x.get('q'))}</div><div class='a'>A. {_e(x.get('a'))}</div></div>"
                 for x in d.get("qa") or [])
    tone = d.get("tone") or {}
    src = " · ".join(f"<a href='{_e(s.get('url'))}' target='_blank' rel='noopener'>{_e(s.get('title'))}</a>"
                     for s in d.get("sources") or [])
    meta = " · ".join(x for x in [
        f"기간 종료 {_e(d['period_end'])}" if d.get("period_end") else "",
        f"컨콜 {_e(d['call_date'])}" if d.get("call_date") else "",
        f"정리 {_e(d['updated'])}" if d.get("updated") else ""] if x)
    tags = "".join(f"<span class='tag'>{_e(t)}</span>" for t in [d.get("country"), d.get("sector"), d.get("ai_role") and f"AI: {d['ai_role']}"] if t)

    def block(title, body, open_=False):
        return f"<details class='fold'{' open' if open_ else ''}><summary>{title}</summary>{body}</details>" if body else ""

    return f"""
<section class='tool ecard {cls}' id='{_anchor(d)}' data-tk='{tk}' data-rg='{region(d)}'>
  <div class='th'><span class='badge {cls}'>{vtxt}</span><h2>{tk} <span class='cname'>{_e(d.get('company'))}</span> · {_e(d.get('period'))}</h2>
    <span class='asof'>{meta}</span></div>
  <div class='tags'>{tags}</div>
  <p class='headline'>{_e(d.get('headline'))}</p>
  {f"<div class='kpis'>{nums}</div>" if nums else ''}
  {f"<div class='tblwrap'><table class='tbl fc'><thead><tr><th>가이던스</th><th>값</th><th>메모</th></tr></thead><tbody>{guide}</tbody></table></div>" if guide else ''}
  {f"<h3 class='eh'>핵심 포인트</h3><ul class='notes'>{_li(d.get('points'))}</ul>" if d.get('points') else ''}
  {f"<p class='rule'><span class='concept'>경영진 톤: {_e(tone.get('label'))}</span>{_e(tone.get('text'))}</p>" if tone else ''}
  {block(f"질의응답 쟁점 <span class='cnt'>{len(d.get('qa') or [])}</span>", qa, True)}
  {block("매크로 연결", f"<ul class='notes'>{_li(d.get('macro'))}</ul>" if d.get('macro') else '')}
  {block("SD식으로 보면", f"<ul class='notes'>{_li(d.get('druck_lens'))}</ul>" if d.get('druck_lens') else '', True)}
  {block("다음 분기에 확인할 것", f"<ul class='notes'>{_li(d.get('watch'))}</ul>" if d.get('watch') else '')}
  {block("확인 못 한 것 · 주의", f"<ul class='notes'>{_li(d.get('caveats'))}</ul>" if d.get('caveats') else '')}
  {f"<div class='src'>출처: {src}</div>" if src else ''}
  <div class='tid'>파일: <code>earnings/{_e(d.get('_file', ''))}</code></div>
</section>"""


def _overview(items: list[dict]) -> str:
    """지역별 한눈 표: 기업 · 기간 · 평가 · 한 줄."""
    out = []
    for rg, name in REGIONS:
        rows = [d for d in items if region(d) == rg]
        if not rows:
            continue
        trs = "".join(
            f"<tr data-rg='{rg}' data-tk='{_e(d.get('ticker'))}'><td><a href='#{_anchor(d)}'><b>{_e(d.get('company') or d.get('ticker'))}</b></a>"
            f"<div class='etk'>{_e(d.get('ticker'))}{' · ' + _e(d.get('country')) if d.get('country') else ''}</div></td>"
            f"<td>{_e(d.get('period'))}<div class='etk'>컨콜 {_e(d.get('call_date'))}</div></td>"
            f"<td><span class='badge {VERDICT.get(d.get('verdict', ''), ('na', ''))[0]}'>{VERDICT.get(d.get('verdict', ''), ('na', '평가 없음'))[1]}</span></td>"
            f"<td class='eone'>{_e(_first_sentence(d.get('headline')))}</td></tr>" for d in rows)
        out.append(f"<div class='erg' data-rg='{rg}'><h3 class='eh'>{name} <span class='cnt'>{len(rows)}</span></h3>"
                   f"<div class='tblwrap'><table class='tbl eov'><thead><tr><th>기업</th><th>기간</th><th>평가</th><th>한 줄</th></tr></thead>"
                   f"<tbody>{trs}</tbody></table></div></div>")
    return f"<section class='tool overview'>{''.join(out)}</section>" if out else ""


def view(items: list[dict], sub: str = "") -> str:
    """리포트의 '실적·컨콜' 화면 (id='v-earnings'). 미국 / 그 외 국가로 나눈다."""
    n_rg = {rg: sum(region(d) == rg for d in items) for rg, _ in REGIONS}
    rchips = f"<a href='#' class='on' data-r=''>전체 <span class='cnt'>{len(items)}</span></a>" + "".join(
        f"<a href='#' data-r='{rg}'>{name} <span class='cnt'>{n_rg[rg]}</span></a>" for rg, name in REGIONS if n_rg[rg])
    seen, chips = set(), "<a href='#' class='on' data-f=''>전체 기업</a>"
    for d in sorted(items, key=lambda d: (region(d) != "us", str(d.get("company") or d.get("ticker")))):
        t = d.get("ticker")
        if t in seen:
            continue
        seen.add(t)
        chips += f"<a href='#' data-f='{_e(t)}' data-rg='{region(d)}'>{_e(d.get('company') or t)}</a>"
    body = "".join(_card(d) for d in items) or (
        "<section class='tool overview'><p class='headline'>아직 정리한 컨콜이 없습니다.</p>"
        "<p class='rule'>earnings/티커/기간.json 파일을 추가하면 여기에 나타납니다. 형식: earnings/_template.json</p></section>")
    return f"""<div class='view' id='v-earnings' data-title='실적·컨콜'>
<h2 class='vt'>실적·컨콜 정리</h2><div class='sub'>{sub}{' · ' if sub else ''}정리본 {len(items)}개 · 기업 {len(seen)}곳 · 최근 컨콜이 위 · 기업 이름을 누르면 해당 카드로</div>
<div class='efilter rg'>{rchips}</div>
{_overview(items)}
<div class='efilter tk'>{chips}</div>
{body}
</div>"""


CSS = """
.efilter{display:flex;gap:6px;flex-wrap:wrap;margin:14px 0 0}
.efilter a{font-size:13px;color:var(--ink);text-decoration:none;padding:4px 12px;border:1px solid var(--line);border-radius:99px;background:var(--panel)}
.efilter a.on{background:var(--ink);color:var(--bg);border-color:var(--ink)}
.ecard .cname{font-weight:500;color:var(--mute);font-size:16px}
.ecard .kpi .vs{font-size:12.5px;color:var(--mute);margin-top:2px} .ecard .kpi .vs.up{color:var(--ok)} .ecard .kpi .vs.dn{color:var(--alert)}
.ecard .eh{font-size:15px;margin:16px 0 4px}
.qa{padding:8px 0;border-bottom:1px dashed var(--line);font-size:14.5px} .qa:last-child{border-bottom:0}
.qa .q{font-weight:600} .qa .a{color:var(--mute);margin-top:2px}
.efilter.rg a{font-size:14px;font-weight:600;padding:6px 16px}
.efilter .cnt{font-weight:400;opacity:.7;margin-left:2px}
.erg{margin-top:4px} .erg + .erg{margin-top:18px}
.eov td,.eov th{vertical-align:top;text-align:left!important} .eov td:first-child{white-space:nowrap} .eov a{color:var(--ink)}
.etk{font-size:12px;color:var(--mute)} .eone{font-size:13.5px;color:var(--mute);min-width:260px}
"""

JS = """
(function(){
  const st={r:'',f:''};
  const apply=()=>{
    document.querySelectorAll('.efilter.rg a').forEach(x=>x.classList.toggle('on',x.dataset.r===st.r));
    document.querySelectorAll('.efilter.tk a').forEach(x=>{
      x.classList.toggle('on',x.dataset.f===st.f);
      x.style.display=(!x.dataset.rg||!st.r||x.dataset.rg===st.r)?'':'none';});
    const ok=el=>(!st.r||el.dataset.rg===st.r)&&(!st.f||el.dataset.tk===st.f);
    document.querySelectorAll('.ecard').forEach(c=>c.style.display=ok(c)?'':'none');
    document.querySelectorAll('.eov tbody tr').forEach(r=>r.style.display=ok(r)?'':'none');
    document.querySelectorAll('.erg').forEach(g=>g.style.display=(!st.r||g.dataset.rg===st.r)?'':'none');
  };
  document.querySelectorAll('.efilter.rg a').forEach(a=>a.addEventListener('click',e=>{e.preventDefault();st.r=a.dataset.r;st.f='';apply();}));
  document.querySelectorAll('.efilter.tk a').forEach(a=>a.addEventListener('click',e=>{e.preventDefault();st.f=a.dataset.f;apply();}));
})();
"""
