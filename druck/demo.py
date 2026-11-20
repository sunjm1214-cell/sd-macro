"""합성(가짜) 데이터 소스 — 인터넷 없이 툴 전체를 돌려보기 위한 것.

실제 역사의 대략적 모양(침체 시기, 인플레 파동, 금리 경로)을 흉내 내지만 숫자는 가짜다.
리포트에는 'DEMO' 배너가 붙는다. 투자 판단에 쓰지 말 것.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .core import DataUnavailable
from .stats import _ALIAS

END = pd.Timestamp("2026-09-30")
MONTHS = pd.date_range("1960-01-31", END, freq=_ALIAS["M"])

# 실제 NBER 침체 구간 (공개된 사실)
RECESSIONS = [("1960-04", "1961-02"), ("1969-12", "1970-11"), ("1973-11", "1975-03"), ("1980-01", "1980-07"),
              ("1981-07", "1982-11"), ("1990-07", "1991-03"), ("2001-03", "2001-11"), ("2007-12", "2009-06"),
              ("2020-02", "2020-04")]


def _yr(idx) -> np.ndarray:
    return idx.year + (idx.month - 0.5) / 12


def _anchor(points: dict[float, float], idx) -> np.ndarray:
    xs, ys = zip(*sorted(points.items()))
    return np.interp(_yr(idx), xs, ys)


class DemoSource:
    def __init__(self, seed: int = 7):
        self.rng = np.random.default_rng(seed)
        self._m = self._build_monthly()
        self._cache: dict[str, pd.Series] = {}
        self.overrides: dict[str, pd.Series] = {}

    # ------------------------------------------------------------------ 월간 핵심 경로
    def _build_monthly(self) -> pd.DataFrame:
        idx, rng = MONTHS, self.rng
        rec = pd.Series(0.0, index=idx)
        for a, b in RECESSIONS:
            rec[(idx >= pd.Timestamp(a)) & (idx <= pd.Timestamp(b) + pd.offsets.MonthEnd(0))] = 1.0
        n = len(idx)

        def ar(sd, rho=0.9):
            e = rng.normal(0, sd, n)
            out = np.zeros(n)
            for i in range(1, n):
                out[i] = rho * out[i - 1] + e[i]
            return out

        infl = _anchor({1960: 1.5, 1966: 3, 1970: 6, 1972: 3.3, 1974.9: 12, 1976.5: 5.5, 1980.2: 14.5, 1983: 3.5,
                        1986.5: 1.5, 1990.8: 6.2, 1994: 2.7, 1998.5: 1.6, 2000.5: 3.6, 2002: 1.4, 2005.8: 4.5,
                        2008.5: 5.4, 2009.5: -1.5, 2011.7: 3.8, 2015.3: -0.1, 2018.5: 2.8, 2020.4: 0.3,
                        2021.5: 5.3, 2022.5: 9.0, 2023.5: 3.1, 2024.5: 3.0, 2025.5: 2.7, 2026.7: 3.1}, idx) + ar(0.15)
        core_pce = _anchor({1960: 1.5, 1970: 4.8, 1975: 9, 1980: 9.5, 1983: 4.5, 1990: 4.2, 1998: 1.5, 2007: 2.2,
                            2010: 1.3, 2015: 1.4, 2019: 1.8, 2020.4: 1.0, 2022.1: 5.5, 2023.5: 4.2, 2024.6: 2.7,
                            2025.5: 2.8, 2026.7: 2.8}, idx) + ar(0.08)
        ff = _anchor({1960: 3.5, 1961: 1.5, 1966: 5, 1968: 4.5, 1969.5: 9, 1971.2: 4, 1973.7: 10.5, 1975: 5.5,
                      1977: 5, 1980.3: 17, 1980.6: 9, 1981.5: 19, 1982.9: 9, 1984.6: 11.5, 1986.9: 6, 1989.3: 9.8,
                      1992.8: 3, 1994: 3, 1995.2: 6, 1998.8: 4.8, 2000.5: 6.5, 2001.9: 2, 2003.5: 1, 2004.4: 1,
                      2006.5: 5.25, 2007.6: 5.25, 2008.9: 0.2, 2015.9: 0.15, 2018.9: 2.4, 2019.5: 2.4,
                      2020.2: 1.6, 2020.3: 0.08, 2022.1: 0.08, 2023.6: 5.33, 2024.7: 5.33, 2024.95: 4.4,
                      2025.7: 4.3, 2026.7: 3.6}, idx) + ar(0.03, 0.5)
        ff = np.clip(ff, 0.05, None)
        u_base = _anchor({1960: 5.5, 1969: 3.5, 1975.4: 9, 1979: 5.8, 1982.9: 10.8, 1989: 5.3, 1992.5: 7.8,
                          2000: 4, 2003.5: 6.1, 2007: 4.5, 2009.9: 10, 2015: 5.3, 2019.9: 3.5, 2020.3: 14.7,
                          2021: 6.5, 2022.5: 3.5, 2024: 3.9, 2025.5: 4.2, 2026.7: 4.4}, idx)
        u = u_base + ar(0.06, 0.6)
        nrou = _anchor({1960: 5.4, 1978: 6.2, 1990: 5.6, 2005: 4.9, 2020: 4.4, 2027: 4.3}, idx)
        y10 = _anchor({1960: 4.1, 1969: 6.5, 1975: 7.8, 1981.8: 15.3, 1986: 7.5, 1990: 8.5, 1993.8: 5.4,
                       1994.9: 7.8, 1998.8: 4.5, 2000: 6.5, 2003.5: 3.6, 2006.5: 5.1, 2008.9: 2.4, 2011: 3.4,
                       2012.5: 1.6, 2013.9: 3, 2016.5: 1.5, 2018.8: 3.2, 2020.5: 0.6, 2021.9: 1.5, 2022.8: 4,
                       2023.8: 4.9, 2024.7: 3.8, 2025.2: 4.5, 2026.7: 4.2}, idx) + ar(0.08, 0.7)
        y2 = np.clip(y10 - _anchor({1960: 0.8, 1978.9: -1.4, 1980: -1.8, 1983: 1.6, 1989.3: -0.2, 1992.5: 2.6,
                                     2000.3: -0.4, 2003.5: 2.4, 2006.8: -0.15, 2010: 2.7, 2018.9: 0.2,
                                     2019.6: -0.05, 2021: 1.3, 2022.9: -0.6, 2023.5: -1.0, 2024.6: -0.2,
                                     2025.5: 0.5, 2026.7: 0.7}, idx) + ar(0.05, 0.5), 0.05, None)
        y3m = np.clip(ff - 0.15 + ar(0.05, 0.3), 0.01, None)
        # 실물 성장 (실질, 연율 %) — 침체 때 마이너스
        g = 3.0 - 6.5 * rec.to_numpy() + ar(0.4, 0.7)
        ngdp_growth = g + infl  # 명목
        # 달러·유가: 로그 랜덤워크 + 역사적 앵커
        usd = np.exp(_anchor({1960: 4.6, 1973: 4.5, 1979: 4.4, 1985.2: 4.85, 1988: 4.5, 1995.3: 4.45,
                              2002.1: 4.85, 2008.3: 4.45, 2011.5: 4.43, 2015.2: 4.7, 2017: 4.75, 2018.1: 4.62,
                              2020.3: 4.8, 2021.5: 4.67, 2022.8: 4.88, 2024: 4.8, 2025: 4.87, 2025.5: 4.78,
                              2026.7: 4.74}, idx) + ar(0.01, 0.8))
        oil = np.exp(_anchor({1960: 1.06, 1973.5: 1.3, 1974.2: 2.4, 1979: 2.7, 1980.5: 3.6, 1985.9: 3.3,
                              1986.3: 2.6, 1990.8: 3.4, 1991.5: 3.0, 1998.9: 2.4, 2000.7: 3.4, 2001.9: 3.0,
                              2008.5: 4.9, 2009.1: 3.7, 2011.3: 4.6, 2014.5: 4.6, 2016.1: 3.4, 2018.8: 4.25,
                              2020.3: 3.0, 2022.4: 4.7, 2023.5: 4.3, 2024.5: 4.35, 2025.5: 4.1, 2026.7: 4.15}, idx)
                     + ar(0.03, 0.8))
        df = pd.DataFrame({"rec": rec, "infl": infl, "core": core_pce, "ff": ff, "u": u, "nrou": nrou,
                           "y10": y10, "y2": y2, "y3m": y3m, "g": g, "ngdp_g": ngdp_growth, "usd": usd,
                           "oil": oil}, index=idx)
        # 물가 지수 (CPI, 근원 PCE)
        df["cpi"] = 30 * np.exp(np.cumsum(df["infl"] / 1200))
        df["pce"] = 20 * np.exp(np.cumsum(df["core"] / 1200))
        df["gdp"] = 540 * np.exp(np.cumsum(df["ngdp_g"] / 1200))
        # 기업이익: 성장 + 달러·유가·금리 역풍(12개월 선행 영향) + 잡음
        usd_y = np.log(df["usd"]).diff(12).fillna(0) * 100
        oil_y = np.log(df["oil"]).diff(12).fillna(0) * 100
        rate_y = df["y10"].diff(12).fillna(0)
        hw = (-0.45 * usd_y - 0.06 * oil_y - 2.0 * rate_y).shift(9).fillna(0)
        pre = (rec.shift(-9).fillna(0).rolling(10, min_periods=1).max() - rec).clip(0)  # 침체 직전 몇 달 이익 둔화
        pg = df["ngdp_g"] * 1.3 - 14 * rec - 10 * pre + hw + ar(2.0, 0.6)
        df["cp"] = 25 * np.exp(np.cumsum(pg / 1200))
        df["m2"] = 300 * np.exp(np.cumsum((df["ngdp_g"] + _anchor({1960: 0, 2008: 1, 2009: 3, 2012: 1, 2020.2: 0,
                                                                  2020.4: 60, 2021.5: 10, 2022.3: -2,
                                                                  2023.4: -9, 2024: 0, 2027: 0}, idx)) / 1200))
        df["hy"] = np.clip(3.3 + 4.5 * rec.rolling(6, min_periods=1).mean() + 0.8 * (df["u"] - df["nrou"]).clip(0)
                           + _anchor({1960: 0, 2008.8: 9, 2009.6: 0, 2020.25: 4, 2020.6: 0, 2027: 0}, idx)
                           + ar(0.15, 0.85), 2.4, None)
        df["mcap_gdp"] = _anchor({1960: 80, 1966: 85, 1974.9: 40, 1982.5: 38, 1987.6: 60, 1990.8: 52,
                                  2000.2: 165, 2002.7: 85, 2007.7: 105, 2009.2: 60, 2014: 110, 2018.7: 140,
                                  2020.2: 105, 2021.9: 200, 2022.8: 150, 2024: 175, 2025.3: 165,
                                  2026.7: 205}, idx) * np.exp(ar(0.02, 0.8))
        df["reer"] = 100 * np.exp(_anchor({1960: 0, 1985.2: 0.32, 1995.3: -0.05, 2002: 0.2, 2011.5: -0.08,
                                           2016: 0.12, 2022.8: 0.25, 2025: 0.26, 2025.6: 0.2, 2026.7: 0.17},
                                          idx) + ar(0.008, 0.85))
        return df

    # ------------------------------------------------------------------ 주기 변환 도우미
    def _q(self, col, how="last"):
        r = self._m[col].resample("QS")
        s = r.last() if how == "last" else r.mean()
        return s

    def _daily(self, s_monthly: pd.Series, noise=0.0, start=None):
        d = pd.bdate_range(start or s_monthly.index[0], END)
        out = s_monthly.reindex(s_monthly.index.union(d)).interpolate("time").reindex(d)
        if noise:
            out = out + self.rng.normal(0, noise, len(out))
        return out.dropna()

    def _build(self, sid: str) -> pd.Series:
        m = self._m
        ms = lambda s: s.set_axis(s.index - pd.offsets.MonthBegin(1))  # 월 시작 날짜 (FRED 관행)
        if sid == "USREC":
            return ms(m["rec"])
        if sid == "CPIAUCSL":
            return ms(m["cpi"])
        if sid == "PCEPILFE":
            return ms(m["pce"])["1959":]
        if sid == "FEDFUNDS":
            return ms(m["ff"])["1960":]
        if sid == "UNRATE":
            return ms(m["u"])
        if sid == "NROU":
            q = m["nrou"].resample("QS").mean()
            ext = pd.Series(4.3, index=pd.date_range(q.index[-1] + pd.offsets.QuarterBegin(1), periods=20, freq="QS"))
            return pd.concat([q, ext])
        if sid == "GDP":
            return self._q("gdp", "mean")
        if sid == "CP":
            return self._q("cp", "mean").iloc[:-1]  # 이익은 한 분기 늦게 나온다
        if sid == "GS10":
            return ms(m["y10"])
        if sid == "GS2":
            return ms(m["y2"])["1976":]
        if sid == "WTISPLC":
            return ms(m["oil"])
        if sid == "TWEXBMTH":
            return ms(m["usd"] * 1.0)["1973":"2019-12"]
        if sid == "DTWEXBGS":
            return self._daily(m["usd"]["2006":] * 1.22, noise=0.15)
        if sid == "T10Y2Y":
            return self._daily(m["y10"]["1976-06":] - m["y2"]["1976-06":], noise=0.03)
        if sid == "T10Y3M":
            return self._daily(m["y10"]["1982":] - m["y3m"]["1982":], noise=0.03)
        if sid == "M2SL":
            return ms(m["m2"])
        if sid == "BAMLH0A0HYM2":
            return self._daily(m["hy"]["1996-12":], noise=0.05)
        if sid == "NCBEILQ027S":  # 백만 달러
            return (self._q("mcap_gdp") / 100 * self._q("gdp") * 1000)["1960":]
        if sid == "BAA10Y":
            return self._daily(1.0 + 0.45 * m["hy"]["1986":], noise=0.02)
        if sid == "RBUSBIS":
            return ms(m["reer"])["1994":]
        if sid in ("WALCL", "WTREGEN", "RRPONTSYD"):
            return self._fed_bs(sid)
        if sid == "FYFSGDA188S":
            yrs = range(1960, 2026)
            base = _anchor({1960: 0, 1975: -3, 1983: -5.8, 1989: -2.8, 1992: -4.5, 2000: 2.3, 2004: -3.4,
                            2007: -1.1, 2009: -9.8, 2015: -2.4, 2019: -4.6, 2020: -14.7, 2021: -11.8,
                            2022: -5.3, 2023: -6.2, 2024: -6.3, 2025: -5.9}, pd.DatetimeIndex([f"{y}-06-30" for y in yrs]))
            return pd.Series(base, index=pd.DatetimeIndex([f"{y}-01-01" for y in yrs]))
        if sid == "A091RC1Q027SBEA":
            q = self._q("gdp", "mean")
            share = _anchor({1960: 1.2, 1985: 3.2, 1991: 3.4, 2000: 2.5, 2013: 1.9, 2020: 1.8, 2021.5: 1.9,
                             2023: 2.9, 2024.5: 3.4, 2026.7: 3.6}, q.index + pd.offsets.QuarterEnd(0))
            return q * share / 100
        if sid == "FGRECPT":
            q = self._q("gdp", "mean")
            return q * 0.17
        if sid == "GFDEGDQ188S":
            q = self._q("gdp", "mean")
            return pd.Series(_anchor({1966: 40, 1981: 31, 1995: 64, 2001: 55, 2008: 64, 2012: 99, 2019: 106,
                                      2020.5: 128, 2022: 119, 2026.7: 124}, q.index + pd.offsets.QuarterEnd(0)),
                             index=q.index)["1966":]
        if sid == "GFDEBTN":  # 백만 달러
            gd = self._build("GFDEGDQ188S")
            return gd / 100 * self._q("gdp", "mean").reindex(gd.index) * 1000
        if sid == "FDHBFIN":  # 십억 달러
            tot = self._build("GFDEBTN")["1970":] / 1000
            share = _anchor({1970: 12, 1990: 18, 2000: 30, 2008: 31, 2012: 33, 2015: 32, 2019: 30, 2021: 24,
                             2023: 23, 2026.7: 21}, tot.index + pd.offsets.QuarterEnd(0))
            return tot * share / 100
        if sid == "BCNSDODNS":  # 십억 달러
            q = self._q("gdp", "mean")
            lev = _anchor({1960: 30, 1990: 41, 2000: 45, 2008: 46, 2015: 43, 2019: 47, 2020.5: 53,
                           2022: 46, 2026.7: 44}, q.index + pd.offsets.QuarterEnd(0))
            return q * lev / 100
        if sid == "GS5":
            return ms(m["y10"] - 0.4)
        if sid == "TREAST":  # 백만 달러, 주간
            w = pd.date_range("2002-12-18", END, freq="W-WED")
            v = np.interp(_yr(w), [2002.9, 2008.9, 2010, 2011.5, 2014.8, 2017.8, 2019.7, 2020.2, 2020.5, 2022.3,
                                   2024.5, 2025.9, 2026.8], [630, 480, 770, 1650, 2460, 2450, 2100, 2500, 4000,
                                                              5770, 4500, 4200, 4250])
            return pd.Series(v * 1000, index=w)
        if sid in ("GDPC1", "GDPPOT"):
            q = self._m["g"].resample("QS").mean()
            g = q if sid == "GDPC1" else pd.Series(_anchor({1960: 3.8, 1980: 3.2, 2000: 3.0, 2010: 2.0, 2027: 2.0},
                                                         q.index + pd.offsets.QuarterEnd(0)), index=q.index)
            return 3000 * np.exp(np.cumsum(g / 400))
        if sid == "NFCI":
            w = pd.date_range("1971-01-08", END, freq="W-FRI")
            hy = m["hy"].reindex(m.index.union(w)).interpolate("time").reindex(w)
            return (hy - 4.5) / 1.6 + pd.Series(self.rng.normal(0, 0.05, len(w)), index=w)
        if sid == "UMCSENT":
            infl, u = m["infl"], m["u"]
            return ms(np.clip(105 - 3.2 * infl - 2.2 * (u - 4) - 12 * m["rec"] + 0 * u, 50, 112))["1952-11":]
        if sid == "CNCF":
            cp = self._q("cp", "mean").iloc[:-1]
            return cp * 1.25 + pd.Series(self.rng.normal(0, 0.02, len(cp)), index=cp.index) * cp
        if sid == "IIPUSNETIQ":  # 백만 달러
            q = self._q("gdp", "mean")["2006":]
            share = _anchor({2006: -10, 2012: -25, 2017: -45, 2020: -60, 2021.9: -78, 2023: -72, 2026.7: -82},
                            q.index + pd.offsets.QuarterEnd(0))
            return q * share / 100 * 1000
        if sid == "IEABC":  # 백만 달러, 분기(연율 아님)
            q = self._q("gdp", "mean")["1999":]
            share = _anchor({1999: -3, 2006: -6, 2009: -2.6, 2014: -2.1, 2019: -2.1, 2022: -3.8, 2026.7: -3.6},
                            q.index + pd.offsets.QuarterEnd(0))
            return q * share / 100 / 4 * 1000
        if sid == "FGEXPND":
            q = self._q("gdp", "mean")
            return q * 0.21
        raise DataUnavailable(f"DEMO: {sid} 합성 데이터 없음 (druck/demo.py에 추가 가능)")

    def _fed_bs(self, sid):
        w = pd.date_range("2002-12-18", END, freq="W-WED")
        y = _yr(w)
        walcl = np.interp(y, [2002.9, 2008.7, 2008.95, 2014.8, 2017.8, 2019.7, 2020.2, 2020.5, 2022.3, 2024.5,
                              2025.9, 2026.8], [730, 900, 2250, 4500, 4450, 3760, 4200, 7100, 8960, 7200, 6550, 6600])
        tga = np.interp(y, [2002.9, 2008.7, 2009, 2015.5, 2016, 2020.3, 2020.6, 2021.6, 2022.5, 2023.4,
                            2023.8, 2026.8], [5, 5, 100, 150, 350, 350, 1700, 300, 650, 60, 750, 850])
        rrp = np.interp(y, [2002.9, 2013.7, 2014, 2017, 2020.9, 2021.3, 2021.9, 2022.9, 2023.3, 2024, 2025.3,
                            2026.8], [0, 0, 100, 300, 50, 50, 1500, 2300, 2200, 700, 100, 20])
        noise = self.rng.normal(0, 1, len(w))
        if sid == "WALCL":
            return pd.Series((walcl + noise * 8) * 1000, index=w)  # 백만 달러
        if sid == "WTREGEN":
            return pd.Series(np.clip(tga + noise * 20, 1, None) * 1000, index=w)  # 백만 달러 (단위 정규화 테스트)
        d = pd.bdate_range("2003-02-07", END)
        return pd.Series(np.interp(_yr(d), y, rrp), index=d).clip(0)  # 십억 달러

    def get(self, sid: str) -> pd.Series:
        if sid in self.overrides:
            return self.overrides[sid].copy()
        if sid in MARKET_DEMO:
            return market_demo(sid).rename(sid)
        if sid not in self._cache:
            self._cache[sid] = self._build(sid).astype(float).dropna().rename(sid)
        return self._cache[sid].copy()


# 매크로 차트용 합성 시세: id → (최근 수준, 연 추세, 일 변동성, 종류)
MARKET_DEMO = {
    "^GSPC": (6600, .09, .010, "p"), "^IXIC": (22000, .12, .013, "p"), "^DJI": (46000, .07, .009, "p"),
    "^RUT": (2400, .05, .013, "p"), "^VIX": (18, 0, .06, "m"), "^KS11": (3900, .06, .011, "p"),
    "^KQ11": (880, .03, .013, "p"), "^N225": (48000, .08, .012, "p"), "^STOXX50E": (5600, .05, .010, "p"),
    "000001.SS": (3800, .02, .011, "p"),
    "DGS3MO": (3.9, 0, .03, "r"), "DGS2": (3.7, 0, .04, "r"), "DGS5": (3.9, 0, .045, "r"), "DGS10": (4.4, 0, .045, "r"),
    "DGS30": (4.9, 0, .04, "r"), "DFII10": (1.9, 0, .04, "r"), "T10Y2Y": (0.6, 0, .03, "r"),
    "IRLTLT01KRM156N": (2.9, 0, .0, "r"),
    "DCOILWTICO": (62, .02, .02, "p"), "DCOILBRENTEU": (66, .02, .02, "p"), "GC=F": (4000, .10, .010, "p"),
    "SI=F": (48, .09, .018, "p"), "HG=F": (4.9, .05, .014, "p"), "NG=F": (3.8, 0, .03, "p"),
    "DX-Y.NYB": (99, 0, .004, "p"), "KRW=X": (1450, .01, .005, "p"), "JPY=X": (152, .01, .006, "p"),
    "EURUSD=X": (1.16, 0, .005, "p"), "CNY=X": (7.1, 0, .002, "p"), "BTC-USD": (95000, .3, .03, "p"),
    "ECBASSETSW": (6.2e6, .08, .004, "p"), "JPNASSETS": (7.4e6, .10, .003, "p"),
    "DEXUSEU": (1.16, 0, .005, "p"), "DEXJPUS": (152, .01, .006, "p"),
    "ECBDFR": (2.0, 0, .0, "r"), "IRSTCI01JPM156N": (0.5, 0, .0, "r"),
    "DFEDTARU": (3.75, 0, .0, "r"), "CL=F": (62, .02, .02, "p"), "USO": (75, .02, .02, "p"), "DBC": (23, .03, .01, "p"),
    "EEM": (52, .04, .012, "p"), "EMB": (95, .02, .004, "p"), "IEF": (95, .01, .003, "p"),
}


def market_demo(sid: str) -> pd.Series:
    level, drift, vol, kind = MARKET_DEMO[sid]
    r = np.random.default_rng(sum(ord(c) * 31 ** i for i, c in enumerate(sid)))
    idx = pd.bdate_range("2000-01-03", END)
    if sid == "IRLTLT01KRM156N":
        idx = pd.date_range("2000-01-01", END, freq="MS")
        return pd.Series(np.clip(5 - np.linspace(0, 2.2, len(idx)) + r.normal(0, .15, len(idx)).cumsum() * .1, .5, None), index=idx)
    n = len(idx)
    if kind == "r":  # 평균회귀 금리
        x = np.zeros(n)
        for i in range(1, n):
            x[i] = x[i - 1] + .002 * (level - x[i - 1]) + r.normal(0, vol)
        return pd.Series(x - x[-1] + level, index=idx)
    if kind == "m":  # VIX
        x = np.zeros(n)
        for i in range(1, n):
            x[i] = x[i - 1] * .97 + r.normal(0, vol * 3)
        return pd.Series(np.clip(level * np.exp(x), 9, None), index=idx)
    lr = np.cumsum(r.normal(drift / 252, vol, n))
    return pd.Series(level * np.exp(lr - lr[-1]), index=idx)


class DemoPrices:
    """합성 ETF 가격. 선행 업종(주택·운송·소매)이 최근 S&P 대비 약해지도록 만든다."""

    DRIFT = {"SPY": 0.10, "ITB": 0.06, "IYT": 0.07, "XRT": 0.05, "IWM": 0.07, "XLI": 0.09, "XME": 0.05,
             "XLP": 0.08, "XLU": 0.07, "GLD": 0.07, "CPER": 0.04, "RSP": 0.09}
    RECENT = {"ITB": -0.30, "IYT": -0.12, "XRT": -0.05, "IWM": -0.08, "XLI": 0.02, "SPY": 0.0, "XME": -0.10,
              "XLP": 0.06, "XLU": 0.05, "GLD": 0.15, "CPER": -0.15, "RSP": -0.06}

    def __init__(self, seed: int = 11):
        self.rng = np.random.default_rng(seed)
        self.idx = pd.bdate_range("2006-01-02", END)
        self.market = np.cumsum(self.rng.normal(0.08 / 252, 0.009, len(self.idx)))

    def get(self, ticker: str) -> pd.Series:
        if ticker in MARKET_DEMO:
            return market_demo(ticker).rename(ticker)
        if ticker not in self.DRIFT:
            raise DataUnavailable(f"DEMO: {ticker} 없음")
        r = np.random.default_rng(sum(ord(c) * 31 ** i for i, c in enumerate(ticker)))
        n = len(self.idx)
        idio = np.zeros(n) if ticker == "SPY" else np.cumsum(r.normal((self.DRIFT[ticker] - 0.10) / 252, 0.006, n))
        tilt = np.zeros(n)
        k = 200
        tilt[-k:] = np.linspace(0, self.RECENT[ticker], k)
        beta = 1.0 if ticker == "SPY" else 1.2
        return pd.Series(100 * np.exp(beta * self.market + idio + tilt), index=self.idx, name=ticker)
