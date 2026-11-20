"""명령줄 실행.

  python -m druck list                         툴 목록
  python -m druck run                          전체 실행 → druck_report.html (한눈 차트 포함)
  python -m druck run profit_headwind liquidity
  python -m druck run --demo                   합성 데이터로 실행 (인터넷 불필요)
  python -m druck run --as-of 2007-06-30       과거 시점에서 보이던 데이터만으로 실행
  python -m druck chart --open                 금리·유가·달러·기업이익 한 차트 → macro_chart.html
  python -m druck scenario --oil 30 --dollar 10 --rate 1.0 [--consensus 8]
  python -m druck run --param mars_fed_funds.r_star=0.5 --param yield_curve.primary=T10Y2Y
"""
from __future__ import annotations

import argparse
import ast
import sys
import webbrowser
from pathlib import Path

from . import make_context
from .core import Signal
from .registry import all_tools, run_all, run_tool


def _parse_params(items: list[str]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for it in items or []:
        key, _, val = it.partition("=")
        tool_name, _, p = key.partition(".")
        if not p or not _:
            raise SystemExit(f"--param 형식: 툴이름.파라미터=값  (받은 값: {it})")
        try:
            v = ast.literal_eval(val)
        except (ValueError, SyntaxError):
            v = val
        out.setdefault(tool_name, {})[p] = v
    return out


def _print_summary(results):
    w = max(len(r.title) for r in results) if results else 10
    print()
    for r in results:
        print(f"{r.signal.label:<8} {r.title:<{w}}  {r.headline}")
    print()


def cmd_list(_args):
    for s in all_tools():
        print(f"{s.name:<20} {s.title}")
        print(f"{'':<20} 규칙: {s.rule}")
        if s.params:
            print(f"{'':<20} 파라미터: {', '.join(f'{k}={v!r}' for k, v in s.params.items())}")
        print()


def _check_data(ctx, args):
    """실행할 때 원천(FRED/Yahoo)에 새 데이터가 있는지 병렬로 확인한다. 바뀐 것만 캐시를 고친다."""
    if args.demo or args.offline:
        return []
    from .data import update_rows
    from .tools.sector_leadership import CYCLICALS, DEFENSIVES
    sids = {"USREC", "GDP", "GS10", "FEDFUNDS", "WTISPLC", "CP", "DTWEXBGS", "TWEXBMTH"}
    for s in all_tools():
        sids.update(s.series)
    print(f"데이터 확인 중... (FRED {len(sids)}개 + 시장 지표, 가격 {len(CYCLICALS) + len(DEFENSIVES) + 4}개 + 시장 지표)", file=sys.stderr)
    from .markets import all_ids
    m_fred, m_yahoo = all_ids()
    sids.update(m_fred)
    ctx.fred.prefetch(sorted(sids))
    if ctx.prices is not None:
        tool_tickers = {t for s in all_tools() for t in s.tickers}
        ctx.prices.prefetch(sorted({"SPY", "GLD", "CPER", "RSP", *CYCLICALS, *DEFENSIVES, *m_yahoo, *tool_tickers}), workers=4)
    rows = update_rows(ctx.fred, ctx.prices)
    changed = [r for r in rows if r["_s"] in ("new", "revised", "first")]
    failed = [r for r in rows if r["_s"] == "offline"]
    if changed:
        print(f"업데이트 {len(changed)}개:", file=sys.stderr)
        for r in changed:
            extra = f"+{r['추가']}개 → {r['최신 마지막']}" if r["추가"] else f"과거 값 {r['개정']}개 수정"
            print(f"  · {r['원천']} {r['시리즈']}: {r['결과']} ({extra})", file=sys.stderr)
    else:
        print("모든 데이터가 이미 최신입니다 (새 데이터 없음).", file=sys.stderr)
    if failed:
        print(f"확인 실패 {len(failed)}개(받아 둔 데이터로 계산): " + ", ".join(r["시리즈"] for r in failed), file=sys.stderr)
    return rows


def cmd_run(args):
    ctx = make_context(demo=args.demo, as_of=args.as_of, refresh=args.refresh, csv=args.csv,
                       check_updates=not (args.demo or args.offline))
    updates = _check_data(ctx, args)
    params = _parse_params(args.param)
    if any(v is not None for v in (args.oil, args.dollar, args.rate, args.consensus)):
        p = params.setdefault("profit_headwind", {})
        for k, v in (("scenario_oil_pct", args.oil), ("scenario_dollar_pct", args.dollar),
                     ("scenario_rate_pp", args.rate), ("consensus_pct", args.consensus)):
            if v is not None:
                p[k] = v
    if args.demo:
        print("합성 데이터로 실행 중...", file=sys.stderr)
    results = run_all(ctx, args.tools or None, params)
    _print_summary(results)
    from .report import render
    out = Path(args.out)
    chart_html = None
    if not args.no_chart:  # 한눈 차트도 같이 만들어 리포트 안에 넣고, 따로 파일로도 저장
        from . import chart
        try:
            chart_html = chart.render(ctx, demo=args.demo, as_of=args.as_of, embed=True)
            standalone = out.with_name("macro_chart.html")
            standalone.write_text(chart.render(ctx, demo=args.demo, as_of=args.as_of), encoding="utf-8")
            print(f"한눈 차트: {standalone.resolve()} (리포트 안에도 포함)")
        except Exception as e:  # 차트가 실패해도 리포트는 만든다
            print(f"[경고] 한눈 차트 생략: {e}", file=sys.stderr)
    ngdp = None
    try:  # 명목GDP vs 금리 화면 (판단 없이 데이터만)
        from .ngdp_view import build
        ngdp = build(ctx)
    except Exception as e:
        print(f"[경고] 명목GDP vs 금리 화면 생략: {e}", file=sys.stderr)
    from .earnings import load as load_earnings
    earnings = load_earnings(args.earnings_dir)
    print(f"실적·컨콜 정리본 {len(earnings)}개", file=sys.stderr)
    markets = None
    try:  # 매크로 차트: 주요 지수 · 채권·금리 · 원자재 · 통화
        from .markets import build as build_markets
        markets = build_markets(ctx)
        miss = [r["name"] for g in markets["groups"] for r in g["rows"] if "err" in r]
        if miss:
            print(f"[경고] 매크로 차트 데이터 없음 {len(miss)}개: " + ", ".join(miss), file=sys.stderr)
    except Exception as e:
        print(f"[경고] 매크로 차트 생략: {e}", file=sys.stderr)
    breadth = None
    if not args.offline:
        try:  # 매크로 차트: 시장 폭 (ADL) — S&P 500 · 나스닥 100 구성 종목으로 계산
            from .breadth import build as build_breadth
            breadth = build_breadth(ctx, demo=args.demo)
            for v in breadth.values():
                print(f"시장 폭 {v['name']}: " + (f"[경고] {v['err']}" if "err" in v else f"{v['n']}종목 · {v['state']}"),
                      file=sys.stderr)
        except Exception as e:
            print(f"[경고] 시장 폭 생략: {e}", file=sys.stderr)
    from .reference import load as load_reference
    reference = load_reference()  # 참고자료: sources/ 의 인터뷰 정리
    out.write_text(render(results, ctx.recessions(), demo=args.demo, as_of=args.as_of, chart_html=chart_html,
                          ngdp=ngdp, updates=updates, earnings=earnings, reference=reference, markets=markets, breadth=breadth), encoding="utf-8")
    print(f"리포트: {out.resolve()}")
    if args.open:
        webbrowser.open(out.resolve().as_uri())
    bad = [r for r in results if r.signal == Signal.NA]
    if bad:
        print(f"판단불가 {len(bad)}개: " + ", ".join(f"{r.tool}({r.headline[:60]})" for r in bad), file=sys.stderr)


def cmd_scenario(args):
    ctx = make_context(demo=args.demo, as_of=args.as_of, refresh=args.refresh)
    r = run_tool("profit_headwind", ctx, scenario_oil_pct=args.oil, scenario_dollar_pct=args.dollar,
                 scenario_rate_pp=args.rate, consensus_pct=args.consensus, horizon_q=args.horizon)
    if r.signal == Signal.NA:
        raise SystemExit(r.headline)
    sc = r.data["scenario"]
    fit = r.data["fit"]
    print(f"\n시나리오: 달러 {args.dollar:+g}%, 유가 {args.oil:+g}%, 금리 {args.rate:+g}%p  (향후 {args.horizon}분기)")
    print(f"  상수(평균 이익 성장)  {sc['상수']:+6.1f}%p")
    for k, v in sc["기여"].items():
        print(f"  {k:<10} 기여      {v:+6.1f}%p   (계수 {fit['coef'][k]:+.3f}, t={fit['t'][k]:+.1f})")
    print(f"  → 예상 기업이익 변화  {sc['예측']:+6.1f}%")
    if args.consensus is not None:
        print(f"  컨센서스 {args.consensus:+.1f}% 대비 괴리 {sc['예측'] - args.consensus:+.1f}%p")
    print(f"\n  참고: 지금 실제 조합 기준 모델 예측 {r.data['pred_now']:+.1f}%, 표본내 R² {fit['r2']:.2f}"
          + ("   [DEMO 데이터]" if args.demo else ""))


def cmd_chart(args):
    from .chart import render
    ctx = make_context(demo=args.demo, as_of=args.as_of, refresh=args.refresh,
                       check_updates=not (args.demo or args.offline))
    print("데이터 받는 중..." if not args.demo else "합성 데이터로 실행 중...", file=sys.stderr)
    out = Path(args.out)
    out.write_text(render(ctx, demo=args.demo, as_of=args.as_of), encoding="utf-8")
    print(f"차트: {out.resolve()}")
    if args.open:
        webbrowser.open(out.resolve().as_uri())


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):  # Windows 콘솔(cp949)에서 이모지 출력 오류 방지
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    ap = argparse.ArgumentParser(prog="druck", description="SD 매크로 분석 툴킷")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list", help="툴 목록").set_defaults(fn=cmd_list)

    def common(p):
        p.add_argument("--demo", action="store_true", help="합성 데이터 사용 (인터넷 불필요)")
        p.add_argument("--as-of", help="이 날짜까지의 데이터만 사용 (예: 2007-06-30)")
        p.add_argument("--refresh", action="store_true", help="캐시 무시하고 다시 받기")
        p.add_argument("--offline", action="store_true",
                       help="새 데이터 확인 없이 받아 둔 데이터로만 실행 (기본: 실행할 때마다 원천에 새 데이터가 있는지 확인)")

    r = sub.add_parser("run", help="툴 실행 + HTML 리포트")
    r.add_argument("tools", nargs="*", help="실행할 툴 이름 (생략 시 전체)")
    common(r)
    r.add_argument("--out", default="druck_report.html")
    r.add_argument("--open", action="store_true", help="리포트를 브라우저로 열기")
    r.add_argument("--no-chart", action="store_true", help="한눈 차트(금리·유가·달러·이익)를 빼고 만들기")
    r.add_argument("--csv", help="시리즈를 덮어쓸 CSV (첫 열 날짜, 열 이름=FRED ID)")
    r.add_argument("--param", action="append", help="툴이름.파라미터=값 (여러 번 가능)")
    r.add_argument("--earnings-dir", help="컨콜 정리본 폴더 (기본: 저장소의 earnings/)")
    r.add_argument("--oil", type=float, help="이익 역풍 시나리오: 유가 변화 %%")
    r.add_argument("--dollar", type=float, help="이익 역풍 시나리오: 달러 변화 %%")
    r.add_argument("--rate", type=float, help="이익 역풍 시나리오: 금리 변화 %%p")
    r.add_argument("--consensus", type=float, help="월가 이익 성장 컨센서스 %%")
    r.set_defaults(fn=cmd_run)

    c = sub.add_parser("chart", help="금리·유가·달러·기업이익 한 차트 (HTML)")
    common(c)
    c.add_argument("--out", default="macro_chart.html")
    c.add_argument("--open", action="store_true", help="차트를 브라우저로 열기")
    c.set_defaults(fn=cmd_chart)

    s = sub.add_parser("scenario", help="금리·유가·달러 시나리오 → 기업이익 변화")
    common(s)
    s.add_argument("--oil", type=float, default=0.0)
    s.add_argument("--dollar", type=float, default=0.0)
    s.add_argument("--rate", type=float, default=0.0)
    s.add_argument("--consensus", type=float)
    s.add_argument("--horizon", type=int, default=4, help="몇 분기 뒤 이익 (기본 4)")
    s.set_defaults(fn=cmd_scenario)

    args = ap.parse_args(argv)
    args.fn(args)


if __name__ == "__main__":
    main()
