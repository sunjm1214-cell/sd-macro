# druck-macro — SD 매크로 분석 툴킷

SD가 연설·인터뷰에서 밝힌 **판단 규칙을 실제 데이터로 돌리는 도구 모음**입니다.
규칙과 인용은 [Stanley Druckenmiller Knowledge Base (chian.io)](https://chian.io/projects/stanley-druckenmiller/sources)의 원자료에서 뽑았습니다.

각 툴은 하나의 규칙을 담당하고 **경고등(🟢 양호 / 🟡 주시 / 🔴 경고 / ⚪ 판단불가)** 하나를 내며,
전체 결과는 차트가 들어간 HTML 리포트 한 장으로 나옵니다.

## 빠른 시작

**가장 쉬운 방법: 폴더의 `run.bat`을 더블클릭.** 첫 화면은 메뉴입니다 — 한눈 차트 / 명목GDP vs 금리 / 신호 요약 / SD 읽는 순서 5단계 / 외부 자료(Macrotrends 등).
외부 사이트는 `druck/links.py`에 한 줄씩 추가하면 첫 화면 메뉴와 위쪽 탭에 나타납니다. 최신 데이터로 툴 15개 리포트와 금리·유가·달러·기업이익 한눈 차트를
한 번에 만들어 브라우저로 엽니다. (`druck_report.html` 하나에 모두 들어 있고, 차트만 따로 `macro_chart.html`로도 저장)

```bash
pip install -r requirements.txt          # pandas, numpy (+ 업종 툴용 yfinance)

python -m druck run --open               # FRED 실데이터로 전체 실행 → druck_report.html (한눈 차트 포함)
python -m druck run --demo --open        # 인터넷 없이 합성 데이터로 화면 확인
python -m druck list                     # 툴 목록, 규칙, 파라미터
```

FRED는 **API 키 없이** 받습니다(공개 CSV). 받은 데이터는 `~/.druck_cache`에 저장됩니다.

**실행할 때마다 최신 데이터인지 확인합니다.** FRED·Yahoo의 모든 시리즈를 병렬로 다시 받아 저장된 것과 비교하고,
새 관측치가 추가됐거나 과거 값이 개정된 시리즈만 갱신한 뒤 리포트를 다시 만듭니다. 무엇이 바뀌었는지는 터미널과
리포트 첫 화면 '데이터 업데이트'에 나옵니다. 인터넷이 안 되면 받아 둔 데이터로 계산합니다. 확인 없이 빨리 돌리려면 `--offline`.

각 툴 아래 **데이터 원본** 칩을 누르면 해당 지표의 FRED / Yahoo Finance 원본 페이지가 새 탭에서 열립니다.
요청이 많아 막히면 무료 키를 받아 `export FRED_API_KEY=...`로 설정하면 공식 API를 씁니다.

### 예시: 금리·유가·달러 → 기업이익

```bash
python -m druck scenario --oil 30 --dollar 10 --rate 1.0 --consensus 8
```
```
시나리오: 달러 +10%, 유가 +30%, 금리 +1%p  (향후 4분기)
  상수(평균 이익 성장)    +x.x%p
  달러(%)      기여        -x.x%p   (계수 …, t=…)
  유가(%)      기여        -x.x%p
  금리(%p)     기여        -x.x%p
  → 예상 기업이익 변화    -x.x%
  컨센서스 +8.0% 대비 괴리 …
```

### 금리·유가·달러·기업이익 한 차트로 보기

`python -m druck run`을 실행하면 리포트 맨 위(요약 아래)에 자동으로 들어갑니다. 차트만 따로 만들려면:
```bash
python -m druck chart --open             # → macro_chart.html
```
판단 없이 흐름만 보는 차트입니다. 10년물 금리(기준금리는 카드 눌러 켜기), WTI, 광의 달러지수, 세후 기업이익을 겹쳐 그립니다.
- **실제값**: 각자 단위 그대로 축 4개 · **시작=100**: 보이는 구간 첫 달=100 (금리는 오른쪽 축 %) · **전년비**: %(금리는 %p)
- 드래그로 확대하면 기준점과 세로축이 그 구간에 맞춰 다시 계산됩니다. `--as-of`, `--demo`도 됩니다.

### 과거 시점으로 돌아가 보기

```bash
python -m druck run --as-of 2000-09-30     # 2000년 노동절 직후, 그가 국채 350%를 샀던 시점
python -m druck run --as-of 2003-12-31     # '화성인 게임'을 했던 시점
python -m druck run --as-of 2021-05-11     # WSJ "The Fed Is Playing With Fire" 날
```
`--as-of`는 그 날짜 **이후 데이터를 잘라낼 뿐**, 당시 발표되던 수정 전 수치(빈티지)는 아닙니다. GDP·이익은 이후 수정되었으므로 실제 그 시점에 보이던 것과 다를 수 있습니다.

### 파라미터 바꾸기

```bash
python -m druck run --param mars_fed_funds.r_star=0.5 --param yield_curve.primary=T10Y2Y
python -m druck run profit_headwind --param profit_headwind.rate_series=GS2 --param profit_headwind.horizon_q=6
```

### 파이썬에서 쓰기

```python
from druck import make_context, run_tool
ctx = make_context()                                   # demo=True, as_of="2007-06-30" 가능
r = run_tool("profit_headwind", ctx, scenario_oil_pct=30, scenario_dollar_pct=10, scenario_rate_pp=1)
print(r.signal.label, r.headline)
r.data["fit"]["coef"]        # 회귀 계수 (pandas Series)
r.data["frame"]              # 분기별 원자료 (DataFrame)
```

## 사이트 구성 (하나의 사이트)

리포트 한 장이 곧 사이트입니다. 위쪽 탭으로 이동합니다.

| 메뉴 | 내용 |
|---|---|
| 홈 | 주요 시세 띠(1개월 변화) · 메뉴 · 데이터 업데이트 현황 |
| **매크로 분석** | 요약(신호 요약: 경고 → 주시 → 양호) + SD의 읽는 순서 1~5층(유동성·연준 → 채권 → 통화 → 주식·이익 → 누적 위험)의 도구 상세 |
| **실적·컨콜** | 기업별 분기 정리본 — 실적 숫자, 가이던스, 핵심 포인트, 경영진 톤, 질의응답, 매크로 연결, SD식 시각 (`druck/earnings.py`) |
| **매크로 차트** | 판단 없이 시장 흐름만 — 주요 지수(S&P·나스닥·다우·러셀·VIX·코스피·코스닥·니케이·유로스톡스·상해), 채권·금리(미 3개월~30년·실질금리·10-2년·하이일드·한국 10년), 원자재(WTI·브렌트·금·은·구리·천연가스), 통화(달러인덱스·원/달러·엔·유로·위안·비트코인), 한눈 차트, 명목GDP vs 금리. 종목은 `druck/markets.py`의 GROUPS에 한 줄로 추가 |
| **참고자료** | SD 인터뷰·강연·기고 56개 정리와 그걸 합친 판단 틀 (`druck/reference.py` ← `sources/`, RULES.md 2-2장) |

### 참고자료 추가

새 인터뷰를 읽으면 `sources/notes/<번호>-<날짜>-<이름>.md`로 정리하고, 목록에 없던 자료는 `sources/extra_index.json`에 한 줄 추가합니다. 사이트를 다시 만들면 참고자료에 자동으로 들어갑니다.

### 컨콜 정리본 추가

`earnings/<티커>/<기간>.json` 파일 하나가 카드 하나입니다 (예: `earnings/NVDA/FY2027Q3.json`). 형식은 `earnings/_template.json`.
Claude에게 "○○ 컨콜 정리해줘"라고 하면 이 형식으로 파일을 만들어 넣습니다. `ai_role`(인프라/활용 사례)은 카드에 표시됩니다.

### 어디서든 보기 (GitHub Pages)

`.github/workflows/site.yml`이 매일 아침 7:10(한국시간)과 저장소가 바뀔 때마다 최신 데이터로 사이트를 다시 만들어 올립니다.
1. GitHub에 저장소를 만들고 이 폴더를 올린다
2. 저장소 Settings → Pages → Source를 **GitHub Actions**로
3. Actions 탭에서 `site` 실행 → 주소로 접속: https://sunjm1214-cell.github.io/sd-macro/

## 툴 목록

리포트는 SD의 읽는 순서대로 묶입니다: **① 유동성·연준(원인) → ② 채권(방향) → ③ 통화(표현) → ④ 주식·이익(확인) → ⑤ 누적 위험(크기·배경)**.
각 툴에는 **용도**(타이밍 = 언제 / 사이즈 = 얼마나 / 배경 = 수년 구조)와 **선행 기간**이 붙습니다. 그는 밸류에이션으로 타이밍을 잡지 않았습니다.
모든 규칙은 원자료와 대조했고, 그 기록은 [RULES.md](RULES.md)에 있습니다.

| 층 | 툴 | 그의 규칙 (원자료 확인) | 주요 데이터 | 근거 |
|---|---|---|---|---|
| ① | `clarity` 명확성 점검 | 연준 완화·원자재 돌파·시장 폭 신고가·타이트한 신용·경기민감주 주도가 한 방향이면 크게, 엇갈리면 '안 한다'(자본 보존). 신용은 수준=Baa, 방향=하이일드 | GDP, FEDFUNDS, BAA10Y, BAMLH0A0HYM2, Yahoo: CPER, RSP, SPY, 업종 ETF | TomorrowX 2026 |
| ① | `global_liquidity` 글로벌 중앙은행 유동성 **(신규)** | 연준·ECB·일본은행 자산 합산의 1년 증감(속도)과 가속도 — 연 1조 매입이 −6천억으로 가는 변화가 위험 | WALCL, ECBASSETSW, JPNASSETS, DEXUSEU, DEXJPUS | CNBC 2017, Real Vision 2018 |
| ① | `liquidity` 유동성 | 시장을 움직이는 건 연준과 유동성. 수준보다 변화율 — 연 1조 달러 매입이 1년 만에 0으로 가는 것 자체가 충격 | WALCL, WTREGEN, RRPONTSYD, M2SL, GDP | Lost Tree 2015, Real Vision 2018, GS 2021 |
| ① | `mars_fed_funds` 화성인 금리 게임 | 데이터만 보면 금리는 몇 %? 2003년 명목성장 9% vs 기준금리 1% → 답 3~6% | FEDFUNDS, PCEPILFE, UNRATE, NROU, GDP | Lost Tree 2015, Endgame 2016, Real Vision 2018 |
| ① | `inflation_rule` 5% 규칙 | CPI 5% 초과 시 ① 기준금리>CPI 없이 안 내려왔고 ② 침체 없이 안 잡혔다 | CPIAUCSL, FEDFUNDS, USREC | Sohn 2022 |
| ① | `financial_conditions` 금융여건 **(신규)** | 이론이 아니라 시장을 본다 — 주식·금 신고가, 신용 타이트, 성장 추세 이상인데 인하하면 인플레 재점화 | SPY, GLD, BAA10Y, GDPC1, GDPPOT, NFCI | Bloomberg 2024 |
| ② | `bond_ngdp` 채권 황금률 **(신규)** | "10년물은 명목GDP 근처에서 거래돼야 한다" — 한참 아래면 국채 숏의 위험보상이 좋다 | GS10, GDP, TREAST | Bloomberg 2024, Norges 2023 |
| ② | `copper_gold` 구리/금 비율 **(신규)** | 구리가 금보다 강하면 성장, 약하면 둔화. 10년물과 엇갈리면 금리 상승이 성장 때문이 아님 | Yahoo: HG=F, GC=F (없으면 CPER, GLD), DGS10 | TomorrowX 2026 |
| ② | `yield_curve` 수익률곡선 | 깊은 역전 뒤엔 침체 — 단 연준이 국채를 사는 동안엔 신호가 없다 | T10Y3M, T10Y2Y, TREAST | USC 2023, Sohn 2022 |
| ③ | `dollar` 달러 | 구매력 고평가 + 외국인 과다보유 + 경상적자 → 순매수만 멈춰도 달러는 혼자 내려간다 | RBUSBIS, IIPUSNETIQ, IEABC | Morgan Stanley 2026 |
| ③ | `policy_divergence` 주요국 정책 격차 **(신규)** | 미국과 유로존·일본 기준금리가 동시에 반대로 꺾이면 통화 추세(보통 2~3년) | FEDFUNDS, ECBDFR, IRSTCI01JPM156N | Bloomberg 2015, DealBook 2015, Norges 2023 |
| ③ | `em_stress` 신흥국 스트레스 **(신규)** | 유동성 축소는 늘 신흥국에서 먼저 — 신흥국 주식·달러채가 미국 대비 밀리는지 | Yahoo: EEM, SPY, EMB, IEF | Real Vision 2018, DealBook 2015 |
| ④ | `sector_leadership` 시장 내부 **(재작성)** | 최고의 경제 예측기는 시장 내부 — 트럭·소매·주택·소형주·금속이 방어주 대비 52주 상대 저점이면 6~12개월 뒤 경제가 꺾인다 | Yahoo: XRT, IYT, ITB, IWM, XME vs XLP, XLU | ECNY 2019, Sohn 2022·2023 |
| ④ | `profit_headwind` 이익 역풍 | 유가·금리·달러 동시 상승은 이익에 언제나 끔찍했다 (하이먼 50/25/25, −36% vs 컨센서스 +18%) | CP, WTISPLC, DTWEXBGS, GS10, FEDFUNDS | Sohn 2022, Norges 2023 |
| ④ | `profit_peak` 이익 정점 | 이익이 정점을 찍기 전에 침체가 온 적은 없다 | CP, USREC, GDP | ECNY 2019 |
| ④ | `sentiment` 소비자심리 **(신규)** | 천장은 소비자 신뢰가 높을 때, 바닥은 침체·나쁜 실적 속에서 | UMCSENT | Novak 인터뷰 |
| ⑤ | `valuation` 밸류에이션 | 1982년 GDP의 50%·침체된 이익의 8배 vs 2022년 150%·부풀려진 이익의 18~19배 — 크기 판단용 | NCBEILQ027S, GDP, CP, GS5 | Delivering Alpha 2022 |
| ⑤ | `equity_risk_premium` 주식 위험 프리미엄 **(신규)** | 이익수익률 − 10년 실질금리. 얇으면 주식 보상이 작다 — 크기 판단용 | CP, NCBEILQ027S, DFII10, GS10 | Delivering Alpha 2022, Robin Hood 2023 |
| ⑤ | `credit` 신용 | 현금흐름은 꺾였는데 부채만 늘면 미래에서 빌린 성장. 스프레드 폭발은 그에게 매수 기회 | BAA10Y, BAMLH0A0HYM2(방향), BCNSDODNS, CNCF | Endgame 2016, Lost Tree 2015, GS 2021 |
| ⑤ | `fiscal` 재정 지배 | 완전고용 속 대규모 적자는 역사상 처음, 이자비용이 세수·지출을 잠식, 호황기에 총알을 다 썼다 | FYFSGDA188S, A091RC1Q027SBEA, FGRECPT, FGEXPND | ECNY 2019, Sohn 2023, Norges 2023 |

## 새 툴 추가하기

1. `druck/tools/_template.py`를 복사해 `druck/tools/새이름.py`로 저장 (밑줄로 시작하지 않게)
2. `@tool(name=..., title=..., concept=..., rule=..., sources=...)`를 채우고 `run(ctx, ...)`에서 `ToolResult`를 반환
3. 끝. `python -m druck list`와 리포트에 자동으로 나타납니다.

규칙:
- 데이터는 반드시 `ctx.series("FRED_ID")` / `ctx.price("티커")`로 받습니다. 그래야 `--as-of`, `--demo`, 캐시가 자동으로 적용됩니다.
- FRED에 없는 데이터(컨센서스 EPS, 하이일드 발행 등급 비중, TIC 포지셔닝 등)는 CSV로 넣습니다: `python -m druck run --csv mydata.csv` (첫 열 날짜, 열 이름이 곧 시리즈 ID). 툴에서는 `ctx.series("열이름")`으로 똑같이 읽습니다.
- 데이터가 없으면 `DataUnavailable`을 올리세요. 리포트에 '판단불가'로 표시되고 나머지 툴은 계속 돕니다.
- 합성 데이터(`--demo`)에서도 돌리려면 `druck/demo.py`의 `_build()`에 새 ID를 추가합니다.

다음에 만들 만한 툴 (원자료에 근거가 있지만 데이터가 FRED에 없는 것):
- **가격 vs 뉴스**: 실적이 좋은데 주가가 3~4개월 못 오르면 6개월 뒤 무언가 터진다 (Barron's 1988) — 실적 서프라이즈 데이터 필요. 2026년 본인은 "경쟁 때문에 효과가 줄었다"고 평가
- **신용의 질**: B등급 비중 28%→71%, 커버넌트 라이트 20%→60% (Lost Tree 2015) — 발행 통계 CSV 필요
- **국채 입찰 수요**: 그가 꼽은 신뢰 붕괴의 첫 방아쇠 '실패한 국채 입찰' (Norges 2023) — 재무부 입찰 결과 CSV 필요
- **원자재 공급**: 구리 "8년간 의미 있는 공급 없음" (Morgan Stanley 2026)

## 테스트

```bash
pip install pytest && python -m pytest -q
```
합성 데이터로 모든 툴 실행, 회귀 계산(numpy와 일치), Newey-West, 표본외 검증의 미래정보 누출 없음, 단위 정규화, FRED CSV 두 형식 파싱 등을 확인합니다.

## 한계와 주의

- **규칙의 해석은 이 툴의 것입니다.** 임계값(예: 테일러 괴리 ±2%p, 적자 5%)은 그가 말한 사례 수치를 바탕으로 정한 기본값이며, SD가 공식화한 기준이 아닙니다. 모두 파라미터로 바꿀 수 있습니다.
- 이익 역풍 모델은 단순 3변수 회귀입니다. 리포트의 **표본외 R²**가 0 이하이면 역사 평균보다 나을 게 없다는 뜻이니, 그가 쓴 방식대로 *컨센서스와의 괴리*를 찾는 용도로 보세요.
- 하이일드 스프레드(ICE)는 FRED에서 제공 기간이 짧을 수 있어, 역사가 10년 미만이면 자동으로 Baa−10년 스프레드(1986~)로 판단합니다.
- 그는 2022년 '침체 온다'고 했다가 틀렸고 공개적으로 인정했습니다. 규칙은 확률을 높이는 도구이지 예언이 아닙니다.
- 투자 권유가 아닙니다.
