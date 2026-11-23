"""첫 화면 '외부 자료' 메뉴에 들어갈 사이트 목록.

종합 매크로 툴로 키워 가면서 자주 보는 사이트를 여기에 한 줄씩 추가하면 된다.
(이름, 주소, 한 줄 설명)
"""

LINKS: list[tuple[str, str, str]] = [
    ("Macrotrends", "https://www.macrotrends.net/",
     "수십 년치 장기 차트 — 주식·지수·원자재·금리·환율·경제지표를 한곳에서"),
]


# ---------------------------------------------------------------- 참고자료 '유용한 사이트'
# (분류, [(이름, 주소, 한 줄 설명)]) — 참고자료 화면 맨 위에 카드로 나온다. 한 줄씩 추가하면 된다.
SITES: list[tuple[str, list[tuple[str, str, str]]]] = [
    ("데이터·차트", [
        ("FRED", "https://fred.stlouisfed.org/", "세인트루이스 연준의 경제 데이터베이스 — 이 사이트 매크로 분석 데이터 대부분의 원천"),
        ("FRED 블로그", "https://fredblog.stlouisfed.org/", "FRED 차트 하나로 경제 현상 하나를 짧게 설명"),
        ("Macrotrends", "https://www.macrotrends.net/", "수십 년치 장기 차트 — 주식·지수·원자재·금리·환율"),
        ("한국은행 경제통계시스템(ECOS)", "https://ecos.bok.or.kr/", "한국 금리·환율·통화량·국제수지 등 공식 통계"),
        ("BIS 데이터 포털", "https://data.bis.org/", "국가별 신용·부채·실질실효환율·부동산 가격 — 달러 도구의 실질실효환율 원천"),
        ("CME FedWatch", "https://www.cmegroup.com/markets/interest-rates/cme-fedwatch-tool.html", "금리 선물로 본 FOMC 회의별 인상·인하 확률"),
        ("애틀랜타 연준 GDPNow", "https://www.atlantafed.org/cqer/research/gdpnow", "이번 분기 미국 성장률 실시간 추정치"),
        ("미 재무부 Fiscal Data", "https://fiscaldata.treasury.gov/", "재정적자·국채 발행·이자비용·TGA 잔고 — 재정 도구의 배경"),
    ]),
    ("연준(Fed)", [
        ("FOMC 회의 일정·성명·점도표", "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm", "회의 일정, 성명서, 경제전망(SEP·점도표), 의사록"),
        ("H.4.1 연준 대차대조표", "https://www.federalreserve.gov/releases/h41/", "매주 목요일 — 연준 자산·TGA·역레포. 유동성 도구의 원천"),
        ("베이지북", "https://www.federalreserve.gov/monetarypolicy/publications/beige-book-default.htm", "12개 지역 연준의 현장 경기 일화 — SD식 '바텀업 매크로'"),
        ("FEDS Notes", "https://www.federalreserve.gov/econres/notes/feds-notes/default.htm", "연준 이사회 경제학자들의 짧은 분석 노트"),
        ("Liberty Street Economics (뉴욕 연준 블로그)", "https://libertystreeteconomics.newyorkfed.org/", "금융시장·국채시장·가계부채·공급망 압력지수 분석"),
        ("On the Economy (세인트루이스 연준 블로그)", "https://www.stlouisfed.org/on-the-economy", "경제 이슈를 데이터로 쉽게 풀어 쓴 글"),
    ]),
    ("한국은행", [
        ("간행물 전체", "https://www.bok.or.kr/portal/singl/newsData/list.do?menuNo=200699", "한국은행 정기 간행물 모음"),
        ("통화신용정책보고서", "https://www.bok.or.kr/portal/singl/newsData/list.do?menuNo=200067", "기준금리 결정 배경과 물가·성장 판단 (연 4회)"),
        ("경제전망보고서", "https://www.bok.or.kr/portal/singl/newsData/list.do?menuNo=200066", "성장률·물가 전망과 근거"),
        ("금융안정보고서", "https://www.bok.or.kr/portal/singl/newsData/list.do?menuNo=200068", "가계부채·부동산·금융기관 위험 점검"),
        ("BOK 이슈노트", "https://www.bok.or.kr/portal/singl/newsData/list.do?menuNo=200433", "현안 하나를 깊게 다루는 짧은 연구"),
        ("해외경제 포커스", "https://www.bok.or.kr/portal/singl/newsData/list.do?menuNo=200437", "미국·중국·유럽 등 해외 경제 동향 정리"),
        ("금융통화위원회 의사록", "https://www.bok.or.kr/portal/singl/newsData/list.do?menuNo=201154", "금통위원별 의견 — 다음 금리 방향의 힌트"),
        ("한국은행 블로그", "https://www.bok.or.kr/portal/singl/newsData/list.do?menuNo=201106", "한국은행 직원들이 쉽게 쓴 경제 글"),
    ]),
    ("BIS·국제기구", [
        ("BIS Quarterly Review", "https://www.bis.org/publications/qr", "분기별 국제 금융시장·은행 동향 (3·6·9·12월)"),
        ("BIS Annual Economic Report", "https://www.bis.org/publications/aer", "'중앙은행들의 중앙은행'이 보는 한 해의 큰 그림 (매년 6월)"),
        ("BIS Bulletin", "https://www.bis.org/publications/bulletin", "시의성 있는 주제를 다룬 짧은 분석"),
        ("중앙은행 총재 연설 모음 (BIS)", "https://www.bis.org/speeches/central-bank", "세계 중앙은행 인사들의 연설 — 정책 방향 변화를 먼저 읽는 곳"),
        ("IMF 세계경제전망(WEO)", "https://www.imf.org/en/Publications/WEO", "국가별 성장률·물가 전망 (4·10월)"),
        ("ECB 블로그", "https://www.ecb.europa.eu/press/blog/html/index.en.html", "유럽중앙은행 인사들의 정책 설명 — 정책 격차 도구와 같이"),
    ]),
    ("SD 자료", [
        ("interviewrecords.com — SD 인터뷰 목록", "https://www.interviewrecords.com/?q=drucken&focus=stanley-druckenmiller", "아래 정리한 인터뷰 54개의 원본 목록"),
        ("SD 지식 베이스 (chian.io)", "https://chian.io/projects/stanley-druckenmiller/sources", "인터뷰 요약·발췌·녹취 모음 — 도구별 근거 링크의 원천"),
    ]),
]


# ---------------------------------------------------------------- 지표 원본 데이터 링크
FRED_URL = "https://fred.stlouisfed.org/series/{}"
WB_URL = "https://data.worldbank.org/indicator/{ind}?locations={c}"
YAHOO_URL = "https://finance.yahoo.com/quote/{}"

SERIES_NAMES: dict[str, str] = {
    "A091RC1Q027SBEA": "연방정부 이자 지급", "BAA10Y": "Baa 회사채 − 10년물 스프레드",
    "BAMLH0A0HYM2": "하이일드 OAS", "BCNSDODNS": "비금융기업 부채", "CNCF": "기업 순현금흐름",
    "CP": "기업이익(세후)", "CPIAUCSL": "CPI(소비자물가)", "DTWEXBGS": "광의 달러지수(명목)",
    "FDHBFIN": "외국인 보유 미 국채", "FEDFUNDS": "기준금리(연방기금금리)", "FGEXPND": "연방정부 지출",
    "FGRECPT": "연방정부 수입", "FYFSGDA188S": "연방 재정수지/GDP", "GDP": "명목GDP", "GDPC1": "실질GDP",
    "GDPPOT": "잠재GDP(CBO)", "GFDEBTN": "연방부채 총액", "GFDEGDQ188S": "연방부채/GDP", "GS10": "10년물 국채금리",
    "GS5": "5년물 국채금리", "IEABC": "경상수지", "IIPUSNETIQ": "순국제투자포지션(NIIP)", "INDPRO": "산업생산지수", "M2SL": "M2 통화량",
    "NCBEILQ027S": "비금융기업 주식 시가총액", "NFCI": "시카고연준 금융여건지수", "NROU": "자연실업률(CBO)",
    "PCEPILFE": "근원 PCE 물가", "RBUSBIS": "달러 실질실효환율(BIS)", "RRPONTSYD": "역레포 잔액",
    "RTWEXBGS": "달러 실질실효환율(연준)", "T10Y2Y": "10년−2년 금리차", "T10Y3M": "10년−3개월 금리차",
    "TREAST": "연준 보유 국채", "TWEXBMTH": "광의 달러지수(구, 2019년 종료)", "UMCSENT": "미시간대 소비자심리",
    "UNRATE": "실업률", "USREC": "NBER 경기침체 구간", "WALCL": "연준 총자산", "WTISPLC": "WTI 유가",
    "WTREGEN": "재무부 일반계정(TGA)", "ECBASSETSW": "ECB 총자산", "JPNASSETS": "일본은행 총자산",
    "DEXUSEU": "달러/유로 환율", "DEXJPUS": "엔/달러 환율", "ECBDFR": "ECB 예금금리", "IRSTCI01JPM156N": "일본 콜금리(월)",
    "DFII10": "10년 실질금리(TIPS)", "DGS10": "10년물 국채금리(일별)",
    "DFEDTARU": "연방기금 목표금리 상단(일별)", "DGS2": "2년물 국채금리(일별)",
    "WB:CHN:FM.LBL.BMNY.GD.ZS": "중국 광의통화/GDP(세계은행)", "WB:JPN:FM.LBL.BMNY.GD.ZS": "일본 광의통화/GDP(세계은행)",
    "WB:USA:FM.LBL.BMNY.GD.ZS": "미국 광의통화/GDP(세계은행)",
}


def series_url(sid: str) -> str:
    """FRED 시리즈 주소. 'WB:국가:지표'는 세계은행 지표 페이지."""
    if sid.startswith("WB:"):
        _, c, ind = sid.split(":", 2)
        return WB_URL.format(ind=ind, c=c)
    return FRED_URL.format(sid)
TICKER_NAMES: dict[str, str] = {
    "SPY": "S&P 500", "GLD": "금", "XRT": "소매", "IYT": "운송", "ITB": "주택건설", "IWM": "러셀2000",
    "XME": "금속·광업", "XLP": "필수소비재", "XLU": "유틸리티",
    "CPER": "구리", "RSP": "S&P 500 동일가중", "EEM": "신흥국 주식", "EMB": "신흥국 달러 국채", "IEF": "미 7~10년 국채",
    "HG=F": "구리 선물", "GC=F": "금 선물", "CL=F": "WTI 원유 선물", "USO": "원유 ETF", "DBC": "원자재 종합 ETF",
}


def data_links(series=(), tickers=()) -> list[tuple[str, str, str]]:
    """(표시 이름, ID, 주소) 목록 — 리포트의 '데이터 원본' 칩에 쓴다."""
    out = [(SERIES_NAMES.get(s, s), s, series_url(s)) for s in series]
    out += [(TICKER_NAMES.get(t, t), t, YAHOO_URL.format(t)) for t in tickers]
    return out
