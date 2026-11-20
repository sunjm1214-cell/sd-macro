"""오프라인 테스트: 합성 데이터와 작은 예제로 로직을 검증한다.  실행: python -m pytest -q"""
import numpy as np
import pandas as pd
import pytest

from druck import make_context, run_all, run_tool
from druck.core import Signal
from druck.data import parse_fred_csv
from druck.stats import _ALIAS, episodes, ols, percentile_rank, predict, to_billions
from druck.tools import profit_headwind as ph


# ------------------------------------------------------------------ stats

def test_ols_matches_lstsq():
    rng = np.random.default_rng(0)
    X = pd.DataFrame(rng.normal(size=(200, 3)), columns=["a", "b", "c"])
    y = 1.5 + X @ np.array([2.0, -1.0, 0.5]) + rng.normal(0, 0.1, 200)
    fit = ols(pd.Series(y), X, nw_lags=4)
    ref, *_ = np.linalg.lstsq(np.column_stack([np.ones(200), X.to_numpy()]), y, rcond=None)
    assert np.allclose(fit["coef"].to_numpy(), ref)
    assert fit["r2"] > 0.99
    assert predict(fit, {"a": 1, "b": 1, "c": 1}) == pytest.approx(ref.sum())


def test_newey_west_widens_se_with_autocorrelation():
    rng = np.random.default_rng(1)
    n = 400
    x = np.cumsum(rng.normal(size=n)) * 0.1
    e = np.convolve(rng.normal(size=n + 7), np.ones(8), "valid")  # 강한 자기상관 잔차
    y = 0.3 * x + e
    plain = ols(pd.Series(y), pd.DataFrame({"x": x}))
    hac = ols(pd.Series(y), pd.DataFrame({"x": x}), nw_lags=8)
    assert hac["se"]["x"] > plain["se"]["x"]


def test_episodes_merge_and_min_len():
    idx = pd.date_range("2000-01-31", periods=12, freq=_ALIAS["M"])
    m = pd.Series([0, 1, 1, 0, 1, 0, 0, 0, 1, 0, 0, 0], index=idx).astype(bool)
    assert episodes(m) == [(idx[1], idx[2]), (idx[4], idx[4]), (idx[8], idx[8])]
    assert episodes(m, merge_gap=1) == [(idx[1], idx[4]), (idx[8], idx[8])]
    assert episodes(m, min_len=2) == [(idx[1], idx[2])]


def test_to_billions_detects_millions():
    s = pd.Series([800_000.0, 900_000.0, 750_000.0])  # 백만 달러로 된 TGA
    assert to_billions(s, 10, 2000).iloc[0] == pytest.approx(800.0)
    s2 = pd.Series([800.0, 900.0])  # 이미 십억
    assert to_billions(s2, 10, 2000).iloc[0] == pytest.approx(800.0)


def test_percentile_rank():
    h = pd.Series(range(100), dtype=float)
    assert percentile_rank(h, 50.0) == pytest.approx(50.5)
    assert percentile_rank(h, 1000.0) == 100.0


@pytest.mark.parametrize("header", ["observation_date", "DATE"])
def test_parse_fred_csv_both_formats(header):
    text = f"{header},GS10\n2020-01-01,1.76\n2020-02-01,.\n2020-03-01,0.87\n"
    s = parse_fred_csv(text, "GS10")
    assert list(s.round(2)) == [1.76, 0.87]
    assert s.index[0] == pd.Timestamp("2020-01-01")


# ------------------------------------------------------------------ tools

@pytest.fixture(scope="module")
def ctx():
    return make_context(demo=True)


def test_all_tools_run_on_demo(ctx):
    res = run_all(ctx)
    assert len(res) >= 14
    for r in res:
        assert r.error is None, f"{r.tool}: {r.error}"
        assert r.signal != Signal.NA, r.tool
        assert r.headline and r.metrics


def test_tools_follow_reading_order():
    from druck.registry import LAYERS, all_tools
    layers = [s.layer for s in all_tools()]
    assert layers == sorted(layers, key=LAYERS.index)  # 유동성·연준 → 채권 → 통화 → 주식·이익 → 누적 위험
    assert all(s.use in ("타이밍", "사이즈", "배경") for s in all_tools())


def test_bond_ngdp_flags_repressed_yields():
    from druck.core import Context

    class Src:
        overrides = {}

        def get(self, sid):
            q = pd.date_range("2000-01-01", "2024-12-31", freq="QS")
            if sid == "GDP":  # 명목성장 6%
                return pd.Series(10000 * 1.06 ** (np.arange(len(q)) / 4), index=q)
            if sid == "GS10":  # 10년물 2% → 괴리 −4%p
                return pd.Series(2.0, index=pd.date_range("2000-01-01", "2024-12-01", freq="MS"))
            raise KeyError(sid)

    class Wrap(Src):
        def get(self, sid):
            from druck.core import DataUnavailable
            try:
                return super().get(sid)
            except KeyError as e:
                raise DataUnavailable(str(e))

    r = run_tool("bond_ngdp", Context(fred=Wrap()))
    assert r.signal == Signal.ALERT, r.headline
    assert r.metrics["괴리 (10년물 − 명목성장)"].startswith("-4")


def test_as_of_truncates_data():
    c = make_context(demo=True, as_of="2007-06-30")
    r = run_tool("inflation_rule", c)
    assert r.as_of <= "2007-06"
    r2 = run_tool("mars_fed_funds", c)
    assert r2.as_of == "2007-06"


def test_scenario_is_linear_in_inputs(ctx):
    r = run_tool("profit_headwind", ctx, scenario_oil_pct=30, scenario_dollar_pct=10, scenario_rate_pp=1)
    fit, sc = r.data["fit"], r.data["scenario"]
    c = fit["coef"]
    expected = c["상수"] + 10 * c["달러(%)"] + 30 * c["유가(%)"] + 1 * c["금리(%p)"]
    assert sc["예측"] == pytest.approx(expected)
    assert "시나리오 결과" in [t for t, _ in r.tables]


def test_out_of_sample_has_no_lookahead(ctx):
    df = ph.build_frame(ctx, "GS10", 4, "1975-01-01")
    base = ph.out_of_sample(df, 4)
    cut = df.index[int(len(df) * 0.7)]
    poisoned = df.copy()
    poisoned.loc[poisoned.index > cut, "향후이익(%)"] = 1e6  # 미래 타깃 오염
    again = ph.out_of_sample(poisoned, 4)
    # cut 이후 타깃이 실현되는 시점(cut + 4분기) 이전의 예측은 바뀌면 안 된다
    safe = base.index[base.index <= cut + pd.DateOffset(months=12)]
    assert np.allclose(base[safe], again[safe])


def test_unknown_param_rejected(ctx):
    with pytest.raises(TypeError):
        run_tool("liquidity", ctx, nonsense=1)


def test_missing_series_gives_na_not_crash():
    c = make_context(demo=True)
    c.fred.overrides = {}
    orig = c.fred._build

    def broken(sid):
        if sid == "CP":
            from druck.core import DataUnavailable
            raise DataUnavailable("테스트용 누락")
        return orig(sid)

    c.fred._build = broken
    r = run_tool("profit_peak", c)
    assert r.signal == Signal.NA and "누락" in r.headline


def test_report_renders(ctx, tmp_path):
    from druck.report import render
    res = run_all(ctx, ["profit_headwind", "yield_curve"])
    html = render(res, ctx.recessions(), demo=True)
    assert "DEMO" in html and "Plotly.react" in html and "profit_headwind" in html
    assert "class='summary'" in html and "class='kpis'" in html


def test_to_freq_drops_partial_last_period():
    from druck.stats import to_freq
    days = pd.bdate_range("2024-01-01", "2024-10-02")  # 10월은 이틀치뿐
    s = pd.Series(1.0, index=days)
    m = to_freq(s, "M")
    assert m.index[-1] == pd.Timestamp("2024-09-30")
    assert to_freq(s, "M", complete=False).index[-1] == pd.Timestamp("2024-10-31")
    monthly = pd.Series(1.0, index=pd.date_range("2024-01-01", "2024-10-01", freq="MS"))
    assert to_freq(monthly, "M").index[-1] == pd.Timestamp("2024-10-31")  # 월별→월은 그대로


# ------------------------------------------------------------------ 한눈 차트

def test_macro_chart_renders_all_series_on_demo():
    from druck.chart import collect, render
    ctx = make_context(demo=True)
    keys = [s["key"] for s in collect(ctx)]
    assert keys == ["gs10", "ff", "oil", "usd", "cp"]
    page = render(ctx, demo=True)
    assert "DEMO" in page and "plotly" in page


def test_ngdp_view_compares_10y_and_fed_funds(ctx):
    from druck.ngdp_view import build
    from druck.report import render
    v = build(ctx)
    assert any("10년물 − 명목성장" in k for k in v["kpis"]) and any("기준금리 − 명목성장" in k for k in v["kpis"])
    assert v["factcheck"][0][0] == "10년물 국채"  # 명목GDP를 따라가는 건 10년물 (원문 팩트체크)
    page = render(run_all(ctx, ["bond_ngdp"]), ctx.recessions(), demo=True, ngdp=v)
    assert "id='v-chart-ngdp'" in page and "href='#chart-ngdp'" in page


def test_compare_detects_new_and_revised_data():
    from druck.data import compare
    idx = pd.date_range("2024-01-01", periods=6, freq="MS")
    old = pd.Series([1.0, 2, 3, 4, 5, 6], index=idx)
    assert compare(old, old.copy())["status"] == "same"
    longer = pd.concat([old, pd.Series([7.0], index=[pd.Timestamp("2024-07-01")])])
    c = compare(old, longer)
    assert c["status"] == "new" and c["added"] == 1
    rev = old.copy(); rev.iloc[2] = 3.5
    assert compare(old, rev)["status"] == "revised"
    assert compare(None, old)["status"] == "first"


def test_every_tool_links_to_its_source_data():
    from druck.links import SERIES_NAMES, data_links
    from druck.registry import all_tools
    for s in all_tools():
        links = data_links(s.series, s.tickers)
        assert links, s.name
        for name, sid, url in links:
            assert url.startswith("https://") and sid in url
            if "fred" in url:
                assert sid in SERIES_NAMES, f"{s.name}: {sid} 한글 이름 없음"


def test_earnings_load_and_render(tmp_path):
    import json
    from druck.earnings import load, view
    (tmp_path / "AAA").mkdir()
    (tmp_path / "AAA" / "FY2026Q1.json").write_text(json.dumps({"company": "에이", "call_date": "2026-01-01",
        "headline": "<b>좋음</b>", "numbers": [{"label": "매출", "value": "$1B", "vs": "+5%", "good": True}]}), encoding="utf-8")
    (tmp_path / "BBB").mkdir()
    (tmp_path / "BBB" / "FY2026Q2.json").write_text("{깨진 파일", encoding="utf-8")
    (tmp_path / "_template.json").write_text("{}", encoding="utf-8")
    items = load(tmp_path)
    assert [d["ticker"] for d in items] == ["AAA", "BBB"]  # 날짜 있는 것이 위, 깨진 파일도 카드로 남는다
    html_ = view(items)
    assert "&lt;b&gt;좋음&lt;/b&gt;" in html_ and "읽지 못했습니다" in html_


def test_repo_earnings_files_are_valid():
    from druck.earnings import load
    for d in load():
        assert d.get("headline") and "읽지 못했습니다" not in d["headline"], d["_file"]


def test_report_has_all_views(ctx):
    from druck.reference import load
    from druck.report import render
    res = run_all(ctx)
    page = render(res, ctx.recessions(), demo=True, earnings=[], reference=load(), chart_html="<p>x</p>")
    from druck.markets import build as build_markets
    page = render(res, ctx.recessions(), demo=True, earnings=[], reference=load(), chart_html="<p>x</p>",
                  markets=build_markets(ctx))
    for vid in ("v-home", "v-macro", "v-macro-1", "v-earnings", "v-chart-overview", "v-chart-idx", "v-chart-rates",
                "v-chart-cmd", "v-chart-fx", "v-ref"):
        assert f"id='{vid}'" in page, vid
    for tab in ("매크로 분석", "실적·컨콜", "매크로 차트", "참고자료"):
        assert f">{tab}</a>" in page
    assert "class='tstrip'" in page and "기타 매크로" not in page
    assert "매크로 판단" not in page and "근거 도구" not in page and "__LNAV" not in page and "__ENAV" not in page


def test_reference_covers_every_source():
    from druck.reference import load, view
    d = load()
    assert d and len(d["items"]) >= 56
    done = [x["n"] for x in d["items"] if x["status"].startswith("done")]
    assert all(n in d["owner"] for n in done)  # 읽었다고 한 자료는 모두 노트가 있다
    page = view(d)
    assert "id='ref-56'" in page and "<table" in page


def test_markets_changes_and_units(ctx):
    """가격은 %, 금리는 bp. 1년 변화가 실제 값과 맞는다."""
    import pandas as pd
    from druck.markets import _changes, build
    idx = pd.date_range("2025-01-01", "2026-01-01", freq="D")
    p = pd.Series(100.0, index=idx); p.iloc[-1] = 110
    assert round(_changes(p, "price")["1년"], 6) == 10
    r = pd.Series(4.0, index=idx); r.iloc[-1] = 4.25
    assert round(_changes(r, "rate")["1년"], 6) == 25
    m = build(ctx)
    ok = [x for g in m["groups"] for x in g["rows"] if "last" in x]
    assert len(ok) >= 25 and any(g["curve"] for g in m["groups"])
