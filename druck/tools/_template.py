"""새 툴 템플릿.

사용법
1. 이 파일을 복사해서 이름을 바꾼다 (밑줄로 시작하지 않게):  druck/tools/real_rates.py
2. @tool(...)의 name을 고유하게 바꾸고 run()을 채운다.
3. 끝. `python -m druck list`에 자동으로 나타난다.

규칙
- 데이터는 반드시 ctx.series("FRED_ID") / ctx.price("티커")로 받는다.
  (그래야 --as-of 과거 시점 재현, --demo 합성 데이터, 캐시가 모두 자동으로 동작)
- 데이터가 없으면 DataUnavailable을 올리면 '판단불가'로 처리된다.
- 신호 의미: OK=경고 없음, WATCH=주시, ALERT=SD식 경고.
- 규칙은 반드시 원자료에서 확인한 것만 쓴다. 출처와 대조 기록은 RULES.md에 남긴다.
- 파라미터는 키워드 인자 + 기본값으로. CLI에서 --param real_rates.threshold=2 로 바뀐다.
- --demo로 돌릴 때 새 FRED ID가 합성 데이터에 없으면 '판단불가'가 된다. druck/demo.py의 SPECS에 추가하면 된다.

예시: 실질금리 툴 (10년물 TIPS 수익률)
"""
from __future__ import annotations

from ..core import Chart, Context, Signal, ToolResult
from ..registry import tool
from ..stats import fdate, fmt, percentile_rank, to_freq
from . import src


@tool(
    name="template_real_rates",          # ← 고유 이름으로 변경
    title="(예시) 10년 실질금리",
    concept="유동성 > 실적",
    rule="마이너스 실질금리는 허들레이트가 사라졌다는 뜻이고, 자본이 위험자산으로 밀려난다.",
    sources=[src("Real Vision 2018 (마이너스 실질금리)", "sources/real-vision-monetary-policy-2018")],
    order=999,
    series=["DFII10"],
    layer="유동성·연준",   # 유동성·연준 / 채권 / 통화 / 주식·이익 / 누적 위험 — 리포트가 이 순서로 묶는다
    use="타이밍",          # 타이밍(언제) / 사이즈(얼마나) / 배경(수년 구조)
    lead="수개월",          # 선행 기간 — 그의 18개월 룰을 의식해서 적는다
)
def run(ctx: Context, negative_alert: float = 0.0) -> ToolResult:
    r = to_freq(ctx.series("DFII10"), "M")
    t, now = r.index[-1], float(r.iloc[-1])
    sig = Signal.ALERT if now < negative_alert else Signal.OK
    return ToolResult(
        signal=sig,
        headline=f"10년 실질금리 {now:.2f}% (역사적 {percentile_rank(r, now):.0f}% 분위)",
        metrics={"기준월": fdate(t), "10년 실질금리": fmt(now, "%", 2)},
        notes=["예시 툴입니다."],
        charts=[Chart("10년 TIPS 수익률", {"실질금리": r}, y_title="%", hlines=[(0, "")])],
        as_of=fdate(t),
    )
