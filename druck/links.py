"""첫 화면 '외부 자료' 메뉴에 들어갈 사이트 목록.

종합 매크로 툴로 키워 가면서 자주 보는 사이트를 여기에 한 줄씩 추가하면 된다.
(이름, 주소, 한 줄 설명)
"""

LINKS: list[tuple[str, str, str]] = [
    ("Macrotrends", "https://www.macrotrends.net/",
     "수십 년치 장기 차트 — 주식·지수·원자재·금리·환율·경제지표를 한곳에서"),
]


# ---------------------------------------------------------------- 지표 원본 데이터 링크
FRED_URL = "https://fred.stlouisfed.org/series/{}"
YAHOO_URL = "https://finance.yahoo.com/quote/{}"

SERIES_NAMES: dict[str, str] = {
    "A091RC1Q027SBEA": "연방정부 이자 지급", "BAA10Y": "Baa 회사채 − 10년물 스프레드",
    "BAMLH0A0HYM2": "하이일드 OAS", "BCNSDODNS": "비금융기업 부채", "CNCF": "기업 순현금흐름",
    "CP": "기업이익(세후)", "CPIAUCSL": "CPI(소비자물가)", "DTWEXBGS": "광의 달러지수(명목)",
    "FDHBFIN": "외국인 보유 미 국채", "FEDFUNDS": "기준금리(연방기금금리)", "FGEXPND": "연방정부 지출",
    "FGRECPT": "연방정부 수입", "FYFSGDA188S": "연방 재정수지/GDP", "GDP": "명목GDP", "GDPC1": "실질GDP",
    "GDPPOT": "잠재GDP(CBO)", "GFDEBTN": "연방부채 총액", "GFDEGDQ188S": "연방부채/GDP", "GS10": "10년물 국채금리",
    "GS5": "5년물 국채금리", "IEABC": "경상수지", "IIPUSNETIQ": "순국제투자포지션(NIIP)", "M2SL": "M2 통화량",
    "NCBEILQ027S": "비금융기업 주식 시가총액", "NFCI": "시카고연준 금융여건지수", "NROU": "자연실업률(CBO)",
    "PCEPILFE": "근원 PCE 물가", "RBUSBIS": "달러 실질실효환율(BIS)", "RRPONTSYD": "역레포 잔액",
    "RTWEXBGS": "달러 실질실효환율(연준)", "T10Y2Y": "10년−2년 금리차", "T10Y3M": "10년−3개월 금리차",
    "TREAST": "연준 보유 국채", "TWEXBMTH": "광의 달러지수(구, 2019년 종료)", "UMCSENT": "미시간대 소비자심리",
    "UNRATE": "실업률", "USREC": "NBER 경기침체 구간", "WALCL": "연준 총자산", "WTISPLC": "WTI 유가",
    "WTREGEN": "재무부 일반계정(TGA)", "ECBASSETSW": "ECB 총자산", "JPNASSETS": "일본은행 총자산",
    "DEXUSEU": "달러/유로 환율", "DEXJPUS": "엔/달러 환율", "ECBDFR": "ECB 예금금리", "IRSTCI01JPM156N": "일본 콜금리(월)",
    "DFII10": "10년 실질금리(TIPS)", "DGS10": "10년물 국채금리(일별)",
}
TICKER_NAMES: dict[str, str] = {
    "SPY": "S&P 500", "GLD": "금", "XRT": "소매", "IYT": "운송", "ITB": "주택건설", "IWM": "러셀2000",
    "XME": "금속·광업", "XLP": "필수소비재", "XLU": "유틸리티",
    "CPER": "구리", "RSP": "S&P 500 동일가중", "EEM": "신흥국 주식", "EMB": "신흥국 달러 국채", "IEF": "미 7~10년 국채",
    "HG=F": "구리 선물", "GC=F": "금 선물",
}


def data_links(series=(), tickers=()) -> list[tuple[str, str, str]]:
    """(표시 이름, ID, 주소) 목록 — 리포트의 '데이터 원본' 칩에 쓴다."""
    out = [(SERIES_NAMES.get(s, s), s, FRED_URL.format(s)) for s in series]
    out += [(TICKER_NAMES.get(t, t), t, YAHOO_URL.format(t)) for t in tickers]
    return out
