# SD 매크로 대시보드

SD(유명 매크로 투자자)가 연설·인터뷰·기고 56개(1994~2026)에서 밝힌 **판단 규칙을 실제 데이터로 돌리는 개인 주식 사이트**입니다.

**사이트: https://sunjm1214-cell.github.io/sd-macro/** — 설치 없이 PC·폰 어디서나 열면 됩니다.

## 메뉴

| 메뉴 | 내용 |
|---|---|
| 홈 | 주요 시세 띠(1개월 변화), 메뉴, 이번 갱신에서 바뀐 데이터 |
| **매크로 분석** | 요약(도구 21개를 경고 → 주시 → 양호 순으로) + SD의 읽는 순서 1~5층: 유동성·연준(원인) → 채권(방향) → 통화(표현) → 주식·이익(확인) → 누적 위험(크기) |
| **실적·컨콜** | 기업별 분기 정리본 — 숫자, 가이던스, 핵심 포인트, 경영진 톤, 질의응답, 매크로 연결, SD식 시각 |
| **매크로 차트** | 판단 없이 시장 흐름만 — 주요 지수 · 채권·금리(수익률 곡선 포함) · 원자재 · 통화, 한눈 차트(금리·유가·달러·이익), 명목GDP vs 금리 |
| **참고자료** | 유용한 사이트(데이터·차트 / 연준 / 한국은행 간행물 / BIS·국제기구 / SD 자료) + SD 인터뷰 56개 정리(연도별, 원본 링크)와 그걸 합친 판단 틀 |

신호등: 🟢 양호(경고 없음) / 🟡 주시 / 🔴 SD식 경고 / ⚪ 판단불가(데이터 없음).
도구마다 용도 태그가 있습니다 — **타이밍**(언제) · **사이즈**(얼마나) · **배경**(수년 구조). SD는 밸류에이션으로 타이밍을 잡지 않았습니다.
색은 한국식: 시세 상승 빨강 ▲, 하락 파랑 ▼.

## 운영 — 자동으로 돌아갑니다

- **매일 아침 7:10(한국시간)** GitHub Actions가 FRED·Yahoo 최신 데이터를 받아 사이트를 다시 만들어 올립니다(`.github/workflows/site.yml`). 저장소에 무언가 올라와도(예: 컨콜 정리본) 바로 다시 만듭니다.
- 만들기 전에 테스트를 먼저 돌립니다. 테스트가 실패하면 사이트는 바뀌지 않고 이전 것이 그대로 남습니다.
- **지금 바로 갱신**: 저장소 **Actions → site → Run workflow** (5분 정도).
- 홈 제목 아래 "생성 …(한국시간)"이 마지막으로 만든 시각입니다.
- FRED는 저장소 비밀값 `FRED_API_KEY`(무료)로 공식 API를 씁니다. GitHub 서버에서는 키 없는 공개 다운로드가 막히기 때문입니다. 키를 바꾸려면 Settings → Secrets and variables → Actions.

## 내용 추가하기

- **컨콜 정리본**: `earnings/<티커>/<기간>.json` 파일 하나가 카드 하나입니다(예: `earnings/NVDA/FY2027Q3.json`, 형식은 `earnings/_template.json`). Claude에게 "○○ 컨콜 정리해줘"라고 하면 이 형식으로 만들어 저장소에 올립니다.
- **참고자료(인터뷰)**: `sources/notes/<번호>-<날짜>-<이름>.md`로 정리하고, interviewrecords.com 목록에 없던 자료는 `sources/extra_index.json`에 한 줄 추가합니다. 파일 이름 앞 숫자들이 그 노트가 다루는 자료 번호입니다.
- **매크로 차트 종목**: `druck/markets.py`의 `GROUPS`에 한 줄. 원천 후보를 여러 개 적으면(`[("y","KRW=X"),("f","DEXKOUS")]`) 앞의 것이 막힐 때 다음 것을 씁니다.
- **유용한 사이트**: `druck/links.py`의 `SITES`(분류별)에 한 줄. 위쪽 메뉴 오른쪽 바로가기는 `LINKS`.
- **매크로 분석 도구**: 아래 '새 도구 추가하기'.

판단 규칙과 원자료 대조 기록은 [RULES.md](RULES.md)에 있습니다(2-2장이 54개 인터뷰를 합친 틀).

## 매크로 분석 도구 (21개)

| 층 | 툴 | 그의 규칙 (원자료 확인) | 주요 데이터 | 근거 |
|---|---|---|---|---|
| ① | `clarity` 명확성 점검 | 연준 완화·원자재 돌파·시장 폭 신고가·타이트한 신용·경기민감주 주도가 한 방향이면 크게, 엇갈리면 '안 한다'(자본 보존). 신용은 수준=Baa, 방향=하이일드 | GDP, FEDFUNDS, BAA10Y, BAMLH0A0HYM2, Yahoo: CPER, RSP, SPY, 업종 ETF | TomorrowX 2026 |
| ① | `global_liquidity` 글로벌 중앙은행 유동성 | 연준·ECB·일본은행 자산 합산의 1년 증감(속도)과 가속도 — 연 1조 매입이 −6천억으로 가는 변화가 위험 | WALCL, ECBASSETSW, JPNASSETS, DEXUSEU, DEXJPUS | CNBC 2017, Real Vision 2018 |
| ① | `liquidity` 유동성 | 시장을 움직이는 건 연준과 유동성. 수준보다 변화율 — 연 1조 달러 매입이 1년 만에 0으로 가는 것 자체가 충격 | WALCL, WTREGEN, RRPONTSYD, M2SL, GDP | Lost Tree 2015, Real Vision 2018, GS 2021 |
| ① | `m2_vs_ip` SD 유동성 규칙 | 통화 공급이 산업생산보다 훨씬 빨리 늘면 주식은 대체로 오른다 — 차이(M2 − 산업생산)가 1년 새 +5%p 이상 벌어지면 가장 강함(60년 검증), 축소·역전은 연준 긴축과 겹칠 때만 경고 | M2SL, INDPRO, FEDFUNDS | 2009 은행 FX 강연 |
| ① | `mars_fed_funds` 화성인 금리 게임 | 데이터만 보면 금리는 몇 %? 2003년 명목성장 9% vs 기준금리 1% → 답 3~6% | FEDFUNDS, PCEPILFE, UNRATE, NROU, GDP | Lost Tree 2015, Endgame 2016, Real Vision 2018 |
| ① | `inflation_rule` 5% 규칙 | CPI 5% 초과 시 ① 기준금리>CPI 없이 안 내려왔고 ② 침체 없이 안 잡혔다 | CPIAUCSL, FEDFUNDS, USREC | Sohn 2022 |
| ① | `financial_conditions` 금융여건 | 이론이 아니라 시장을 본다 — 주식·금 신고가, 신용 타이트, 성장 추세 이상인데 인하하면 인플레 재점화 | SPY, GLD, BAA10Y, GDPC1, GDPPOT, NFCI | Bloomberg 2024 |
| ② | `bond_ngdp` 채권 황금률 | "10년물은 명목GDP 근처에서 거래돼야 한다" — 한참 아래면 국채 숏의 위험보상이 좋다 | GS10, GDP, TREAST | Bloomberg 2024, Norges 2023 |
| ② | `copper_gold` 구리/금 비율 | 구리가 금보다 강하면 성장, 약하면 둔화. 10년물과 엇갈리면 금리 상승이 성장 때문이 아님 | Yahoo: HG=F, GC=F (없으면 CPER, GLD), DGS10 | TomorrowX 2026 |
| ② | `yield_curve` 수익률곡선 | 깊은 역전 뒤엔 침체 — 단 연준이 국채를 사는 동안엔 신호가 없다 | T10Y3M, T10Y2Y, TREAST | USC 2023, Sohn 2022 |
| ③ | `dollar` 달러 | 구매력 고평가 + 외국인 과다보유 + 경상적자 → 순매수만 멈춰도 달러는 혼자 내려간다 | RBUSBIS, IIPUSNETIQ, IEABC | Morgan Stanley 2026 |
| ③ | `policy_divergence` 주요국 정책 격차 | 미국과 유로존·일본 기준금리가 동시에 반대로 꺾이면 통화 추세(보통 2~3년) | FEDFUNDS, ECBDFR, IRSTCI01JPM156N | Bloomberg 2015, DealBook 2015, Norges 2023 |
| ③ | `em_stress` 신흥국 스트레스 | 유동성 축소는 늘 신흥국에서 먼저 — 신흥국 주식·달러채가 미국 대비 밀리는지 | Yahoo: EEM, SPY, EMB, IEF | Real Vision 2018, DealBook 2015 |
| ④ | `sector_leadership` 시장 내부 | 최고의 경제 예측기는 시장 내부 — 트럭·소매·주택·소형주·금속이 방어주 대비 52주 상대 저점이면 6~12개월 뒤 경제가 꺾인다 | Yahoo: XRT, IYT, ITB, IWM, XME vs XLP, XLU | ECNY 2019, Sohn 2022·2023 |
| ④ | `profit_headwind` 이익 역풍 | 유가·금리·달러 동시 상승은 이익에 언제나 끔찍했다 (하이먼 50/25/25, −36% vs 컨센서스 +18%) | CP, WTISPLC, DTWEXBGS, GS10, FEDFUNDS | Sohn 2022, Norges 2023 |
| ④ | `profit_peak` 이익 정점 | 이익이 정점을 찍기 전에 침체가 온 적은 없다 | CP, USREC, GDP | ECNY 2019 |
| ④ | `sentiment` 소비자심리 | 천장은 소비자 신뢰가 높을 때, 바닥은 침체·나쁜 실적 속에서 | UMCSENT | Novak 인터뷰 |
| ⑤ | `valuation` 밸류에이션 | 1982년 GDP의 50%·침체된 이익의 8배 vs 2022년 150%·부풀려진 이익의 18~19배 — 크기 판단용 | NCBEILQ027S, GDP, CP, GS5 | Delivering Alpha 2022 |
| ⑤ | `equity_risk_premium` 주식 위험 프리미엄 | 이익수익률 − 10년 실질금리. 얇으면 주식 보상이 작다 — 크기 판단용 | CP, NCBEILQ027S, DFII10, GS10 | Delivering Alpha 2022, Robin Hood 2023 |
| ⑤ | `credit` 신용 | 현금흐름은 꺾였는데 부채만 늘면 미래에서 빌린 성장. 스프레드 폭발은 그에게 매수 기회 | BAA10Y, BAMLH0A0HYM2(방향), BCNSDODNS, CNCF | Endgame 2016, Lost Tree 2015, GS 2021 |
| ⑤ | `fiscal` 재정 지배 | 완전고용 속 대규모 적자는 역사상 처음, 이자비용이 세수·지출을 잠식, 호황기에 총알을 다 썼다 | FYFSGDA188S, A091RC1Q027SBEA, FGRECPT, FGEXPND | ECNY 2019, Sohn 2023, Norges 2023 |

## 내 컴퓨터에서 직접 돌리기 (선택)

사이트는 자동으로 갱신되므로 보통은 필요 없습니다. 과거 시점을 돌려 보거나 코드를 고칠 때만 씁니다. Windows는 폴더의 `run.bat`을 더블클릭해도 됩니다.

```bash
git clone https://github.com/sunjm1214-cell/sd-macro && cd sd-macro
pip install -r requirements.txt
python -m druck run --open                 # 실데이터로 사이트 한 장(druck_report.html)을 만들어 열기
python -m druck run --demo --open          # 인터넷 없이 합성 데이터로 화면 확인
python -m druck run --as-of 2026-01-23     # 과거 시점 기준으로 (그가 '크게 걸던' 2026년 1월)
python -m druck list                       # 도구 목록·규칙·파라미터
python -m druck scenario --oil 30 --dollar 10 --rate 1.0 --consensus 8   # 금리·유가·달러 → 기업이익 시나리오
```

- 받은 데이터는 `~/.druck_cache`에 저장되고, 실행할 때마다 원천과 비교해 바뀐 것만 갱신합니다. 확인 없이 빨리 돌리려면 `--offline`.
- 판정 기준값은 `--param 도구이름.파라미터=값`으로 바꿀 수 있습니다(예: `--param clarity.clear_share=0.7`).
- FRED 공식 API를 쓰려면 환경변수 `FRED_API_KEY`를 설정합니다(없으면 공개 CSV).

## 새 도구 추가하기

1. `druck/tools/_template.py`를 복사해 `druck/tools/새이름.py`로 저장 (밑줄로 시작하지 않게)
2. `@tool(name=..., title=..., concept=..., rule=..., sources=...)`를 채우고 `run(ctx, ...)`에서 `ToolResult`를 반환
3. 끝. `python -m druck list`와 리포트에 자동으로 나타납니다.

규칙:
- 데이터는 반드시 `ctx.series("FRED_ID")` / `ctx.price("티커")`로 받습니다. 그래야 `--as-of`, `--demo`, 캐시가 자동으로 적용됩니다.
- FRED에 없는 데이터(컨센서스 EPS, 하이일드 발행 등급 비중, TIC 포지셔닝 등)는 CSV로 넣습니다: `python -m druck run --csv mydata.csv` (첫 열 날짜, 열 이름이 곧 시리즈 ID). 툴에서는 `ctx.series("열이름")`으로 똑같이 읽습니다.
- 데이터가 없으면 `DataUnavailable`을 올리세요. 리포트에 '판단불가'로 표시되고 나머지 툴은 계속 돕니다.
- 합성 데이터(`--demo`)에서도 돌리려면 `druck/demo.py`의 `_build()`(또는 시장 지표는 `MARKET_DEMO`)에 새 ID를 추가합니다.

## 테스트

```bash
pip install pytest && python -m pytest -q
```
합성 데이터로 모든 도구 실행, 화면 구성(메뉴·화면 ID), 시장 변화 단위(%·bp), 참고자료 노트 연결, 회귀 계산, 미래정보 누출 없음 등을 확인합니다. 사이트를 만들기 전에 자동으로 실행됩니다.

## 한계와 주의

- **규칙의 해석은 이 툴의 것입니다.** 임계값(예: 테일러 괴리 ±2%p, 적자 5%)은 그가 말한 사례 수치를 바탕으로 정한 기본값이며, SD가 공식화한 기준이 아닙니다. 모두 파라미터로 바꿀 수 있습니다.
- 이익 역풍 모델은 단순 3변수 회귀입니다. 리포트의 **표본외 R²**가 0 이하이면 역사 평균보다 나을 게 없다는 뜻이니, 그가 쓴 방식대로 *컨센서스와의 괴리*를 찾는 용도로 보세요.
- 하이일드 스프레드(ICE)는 무료 FRED에서 2023년 11월 이후만 제공됩니다. 그래서 신용의 '수준'(역사 대비 얼마나 좁은가)은 Baa−10년물(1986~)로, '방향'(넓어지는가)은 하이일드 3개월 변화로 봅니다.
- 그는 2022년 '침체 온다'고 했다가 틀렸고 공개적으로 인정했습니다. 규칙은 확률을 높이는 도구이지 예언이 아닙니다.
- 투자 권유가 아닙니다.
