"""'참고자료' 화면 — 학습한 SD 인터뷰 전부와 그걸 합친 판단 틀.

원자료:
  sources/interviewrecords_index.json  interviewrecords.com 목록 54개 (번호·날짜·제목·링크·처리 상태)
  sources/extra_index.json             목록 밖에서 추가로 읽은 자료 (#55~)
  sources/notes/<번호들>-<날짜>-<이름>.md  인터뷰별 정리 노트 (한국어 의역)
  RULES.md 2-2장                        54개를 합친 '하나의 틀' (4개 질문 · 자산별 방향표)
노트 파일 이름 앞의 숫자들(예: 41-42-43-2024-…)이 그 노트가 다루는 자료 번호다.
"""
from __future__ import annotations

import html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "sources"


def _e(v) -> str:
    return html.escape(str(v))


# ---------- 아주 작은 마크다운 → HTML (노트·RULES.md에 쓰인 문법만) ----------
_URL = re.compile(r"(?<![\"'(=])(https?://[^\s)<>·]+)")


_NAME = re.compile(r"\b(?:Stanley F\. |Stanley |Stan )?Druckenmiller(?:'s)?\b")


def _sd(h: str) -> str:
    """화면에 보이는 글자에서만 이름을 SD로 (태그 속성·URL은 그대로)."""
    parts = re.split(r"(<[^>]+>)", h)
    out = []
    for p in parts:
        if p.startswith("<") or p.startswith("http"):
            out.append(p)
        else:
            out.append(_NAME.sub("SD", p))
    return "".join(out)


def _inline(s: str) -> str:
    s = _e(s)
    s = re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+)\)",
               lambda m: f"<a href='{m.group(2)}' target='_blank' rel='noopener'>{m.group(1)}</a>", s)
    s = _URL.sub(lambda m: f"<a href='{m.group(1)}' target='_blank' rel='noopener'>{m.group(1)}</a>", s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    return _sd(s)


def md(text: str, skip_title: bool = False) -> str:
    out, para, lists = [], [], []  # lists: 열린 <ul>/<ol>의 들여쓰기 스택
    lines = text.splitlines()

    def flush_para():
        if para:
            out.append("<p>" + _inline(" ".join(para)) + "</p>")
            para.clear()

    def close_lists(to: int = -1):
        while lists and lists[-1][0] > to:
            out.append(f"</li></{lists.pop()[1]}>")

    i = 0
    while i < len(lines):
        ln = lines[i]
        st = ln.strip()
        if not st:
            flush_para(); close_lists(); i += 1; continue
        if st.startswith("|") and i + 1 < len(lines) and re.match(r"^\s*\|[\s:|-]+\|\s*$", lines[i + 1]):
            flush_para(); close_lists()
            head = [c.strip() for c in st.strip("|").split("|")]
            rows = []
            i += 2
            while i < len(lines) and lines[i].strip().startswith("|"):
                rows.append([c.strip() for c in lines[i].strip().strip("|").split("|")])
                i += 1
            out.append("<div class='tblwrap'><table class='tbl fc'><thead><tr>"
                       + "".join(f"<th>{_inline(h)}</th>" for h in head) + "</tr></thead><tbody>"
                       + "".join("<tr>" + "".join(f"<td>{_inline(c)}</td>" for c in r) + "</tr>" for r in rows)
                       + "</tbody></table></div>")
            continue
        m = re.match(r"^(#{1,4})\s+(.*)", st)
        if m:
            flush_para(); close_lists()
            if not (skip_title and len(m.group(1)) == 1):
                lvl = min(5, len(m.group(1)) + 2)
                out.append(f"<h{lvl} class='rh'>{_inline(m.group(2))}</h{lvl}>")
            i += 1; continue
        m = re.match(r"^(\s*)([-*]|\d+\.)\s+(.*)", ln)
        if m:
            flush_para()
            ind, kind = len(m.group(1)), ("ol" if m.group(2)[0].isdigit() else "ul")
            if lists and ind < lists[-1][0]:
                close_lists(ind)
            if lists and ind == lists[-1][0]:
                out.append("</li><li>")
            else:
                out.append(f"<{kind}><li>")
                lists.append((ind, kind))
            out.append(_inline(m.group(3)))
            i += 1; continue
        if lists:  # 목록 항목의 이어지는 줄
            out.append(" " + _inline(st)); i += 1; continue
        para.append(st); i += 1
    flush_para(); close_lists()
    return "".join(out)


# ---------- 자료 목록 ----------
def _note_nums(name: str) -> list[int]:
    nums = []
    for part in name.split("-"):
        if part.isdigit() and len(part) <= 2:
            nums.append(int(part))
        else:
            break
    return nums


def _status(st: str) -> tuple[str, str, int | None]:
    """(배지 글자, css, 다른 노트 번호)."""
    m = re.search(r"covered by #(\d+)", st)
    if m:
        return f"#{m.group(1)}에 포함", "cov", int(m.group(1))
    m = re.search(r"#(\d+)과 동일", st)
    if st.startswith("done") and m:
        return "정리", "ok", None
    if st.startswith("done"):
        return "정리", "ok", None
    if st.startswith("unavailable"):
        return "볼 수 없음", "na", None
    if st.startswith("skipped"):
        return "근거 제외", "na", None
    return st, "na", None


def load() -> dict | None:
    try:
        items = json.loads((SRC / "interviewrecords_index.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    try:
        items += json.loads((SRC / "extra_index.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        pass
    notes, owner = {}, {}
    for p in sorted((SRC / "notes").glob("*.md")):
        if p.name.startswith("_"):
            continue
        nums = _note_nums(p.stem)
        if not nums:
            continue
        notes[nums[0]] = p.read_text(encoding="utf-8")
        for n in nums:
            owner[n] = nums[0]
    try:
        cov = (SRC / "notes" / "_coverage.md").read_text(encoding="utf-8")
    except OSError:
        cov = ""
    try:
        rules = (ROOT / "RULES.md").read_text(encoding="utf-8")
        a = rules.index("### 질문 ①")
        b = rules.index("### 실데이터 점검 기록") if "### 실데이터 점검 기록" in rules else rules.index("## 3.")
        frame = rules[a:b]
    except (OSError, ValueError):
        frame = ""
    return {"items": items, "notes": notes, "owner": owner, "coverage": cov, "frame": frame}


def view(ref: dict | None, sub: str = "") -> str:
    if not ref:
        return ("<div class='view' id='v-ref' data-title='참고자료'><h2 class='vt'>참고자료</h2>"
                "<p class='rule'>sources/ 폴더를 찾지 못해 이 화면을 만들 수 없습니다.</p></div>")
    items = sorted(ref["items"], key=lambda x: (x["date"], x["n"]), reverse=True)
    notes, owner = ref["notes"], ref["owner"]
    n_notes = len(notes)
    n_seen = sum(1 for x in items if not x["status"].startswith(("unavailable", "skipped")))
    years, rows = {}, []
    for x in items:
        years.setdefault(x["date"][:4], []).append(x)
    for y, xs in years.items():
        rows.append(f"<h3 class='ry' id='ref-{y}'>{y}</h3>")
        for x in xs:
            badge, css, cov_n = _status(x["status"])
            o = owner.get(x["n"])
            if cov_n is None and o is not None and o != x["n"]:
                cov_n = o
            body = ""
            if o is not None and o == x["n"]:
                body = md(notes[o], skip_title=True)
            elif cov_n is not None:
                body = f"<p class='rule'>같은 인터뷰 — <a href='#ref-{cov_n}'>#{cov_n} 정리</a>에 함께 담았습니다.</p>"
            elif css == "na":
                body = f"<p class='rule'>{_e(x['status'])}</p>"
            head = (f"<span class='rn'>#{x['n']}</span><span class='rd'>{_e(x['date'])}</span>"
                    f"<span class='rt'>{_sd(_e(x['title']))}</span><span class='rb {css}'>{_e(badge)}</span>")
            link = f"<a class='src' href='{_e(x['url'])}' target='_blank' rel='noopener'>원본 ↗</a>"
            rows.append(f"<details class='ref' id='ref-{x['n']}'><summary>{head}</summary>"
                        f"<div class='rbody'>{link}{body}</div></details>")
    jump = "".join(f"<a href='#ref-{y}'>{y}</a>" for y in years)
    frame = md(ref["frame"]) if ref["frame"] else ""
    cov = md(ref["coverage"], skip_title=True) if ref["coverage"] else ""
    return f"""<div class='view' id='v-ref' data-title='참고자료'>
<h2 class='vt'>참고자료 — SD 인터뷰 정리</h2><div class='sub'>{sub}</div>
<section class='tool overview'>
  <p class='headline'>인터뷰·강연·기고 {len(items)}개(1994~2026)를 확인해 {n_seen}개를 노트 {n_notes}개로 정리했습니다.</p>
  <p class='rule'>같은 인터뷰를 자른 클립은 전체본 노트 하나에 함께 담았습니다. 비공개로 바뀐 영상과 제3자 해설은 근거에서 뺐습니다.</p>
  <p class='rule'>원문은 영상 자막·기사이며, 여기 적힌 것은 짧은 인용 외에는 요지를 옮긴 의역입니다. 자료 번호는 interviewrecords.com 목록 순서이고, #55부터는 목록 밖에서 추가로 읽은 최신 자료입니다.</p>
  <details class='fold'><summary>합친 틀 — 4개 질문과 자산별 방향표</summary><div class='rbody'>{frame}</div></details>
  <details class='fold'><summary>못 읽었거나 다른 정리에 합친 자료</summary><div class='rbody'>{cov}</div></details>
</section>
<div class='lnav'><b>연도</b>{jump}</div>
{''.join(rows)}
</div>"""


CSS = """
.ry{font-size:17px;margin:22px 0 8px}
details.ref{background:var(--panel);border:1px solid var(--line);border-radius:10px;margin:6px 0}
details.ref>summary{cursor:pointer;list-style:none;padding:10px 14px;display:flex;gap:10px;align-items:baseline;flex-wrap:wrap}
details.ref>summary::-webkit-details-marker{display:none}
details.ref[open]>summary{border-bottom:1px solid var(--line)}
.rn{font-weight:700;color:var(--mute);min-width:34px} .rd{color:var(--mute);font-size:13.5px;min-width:86px}
.rt{flex:1 1 300px;font-weight:600}
.rb{font-size:12px;padding:1px 8px;border-radius:99px;border:1px solid var(--line);color:var(--mute)}
.rb.ok{color:var(--ok);border-color:var(--ok)} .rb.cov{color:var(--link)}
.rbody{padding:4px 16px 14px;font-size:15px} .rbody .src{float:right;font-size:13px;margin-top:8px}
.rbody ul,.rbody ol{padding-left:20px;margin:6px 0} .rbody li{margin:3px 0}
.rh{margin:14px 0 6px;font-size:15.5px} h3.rh{font-size:17px}
"""
