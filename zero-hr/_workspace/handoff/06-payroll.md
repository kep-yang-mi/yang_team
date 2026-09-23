# 06-payroll — payroll-close-analyst — 2026-09-23

상태: ok · 기록: 2026-09-23 17:10:52 · 스크립트: `.claude/skills/payroll-close/scripts/payroll_close.py`

## 시도한 것
- `.claude/skills/payroll-close/scripts/payroll_close.py --root /Users/yang/development/zero-hr --as-of 2026-09-23` 실행 시작
- 정제 CSV 3종을 읽고 REQUIRED_COLUMNS로 계약 §3 헤더를 검사
- 급여 대상 인원 집계: 기준일 재직 406 + 휴직 21 = 총원 427 → 월말 재직 411(+19 −14) / 월말 총원 432
- 일할 계산 대상(당월 입사 5 · 월말까지 입사 예정 19 · 퇴사 예정 14), 휴직 처리 21, 90일 계약 만료 24, 위험 14건 산출
- 산출물 기록: `data/stats/payroll-close.json` (indent 2, UTF-8, 시각 필드 없음 — 같은 입력이면 같은 파일)
- 페르소나 니즈 반영: applied=True, 미확보 필드 0, 미충족 기준 0, 검증 불가 0

## 본 데이터·근거
- 입력 예정: data/clean/headcount-master.clean.csv · data/clean/planned-joiners.clean.csv · data/clean/planned-leavers.clean.csv · data/stats/month-end-forecast.json(대사 기준) · data/reference/org-chart.csv · personas/persona-needs.json(선택)
- 정제 데이터 행 수: 마스터 427 · 입사 예정 27 · 퇴사 예정 19 (헤더 §3 준수)
- 조직 체계 org-chart.csv: 조직 11개 (byDepartment 순서·명칭 기준)
- month-end-forecast.totals.forecastMonthEnd = 411 (조직별 11개 대조)

## 실패한 것
- (없음)

## 검증된 것
- 대사 일치: monthEndActive 411 == forecast.totals.forecastMonthEnd 411, 조직별 forecastMonthEnd 전부 일치
- headcount-stats 재직/휴직 대사: 406/21 vs 406/21
- 내부 합계 일치: byDepartmentAsOfTotal, byDepartmentMonthEndActive, byDepartmentMonthEndTotal, byEmploymentTypeAsOfTotal, byEmploymentTypeMonthEndTotal, byTreatmentSum, contractsByMonthSum
- §2-7 정본 대조(406/21/427/411/432, 고용유형 354/31/19/23): 일치
- 급여 대상 427(재직 406+휴직 21) → 월말 재직 411 / 월말 총원 432 · 일할 대상 5/19/14 · 휴직 처리 {"무급(정부 급여)": 12, "유급": 5, "무급": 4} · 계약 만료 24 · 위험 14(date-logic,hire-after-as-of,missing-required,org-unknown,stale-planned-leaver,status-inconsistency,unknown-emp) · 체크리스트 pending 6/7

## 다음 agent 인계점
- product-builder(09-products): `data/stats/payroll-close.json`를 site/data/payroll.json = {payrollClose, statsSubset, cleansingSummary}에 싣는다. monthEndActive(재직 기준)와 monthEndTotal(휴직 포함)을 구분 표기
- product-judge(persona-advocate:payroll): fitCriteria evidence가 이 산출물 경로를 가리킨다. 미충족 기준은 checklist의 '니즈 기준 미충족 [id]' 항목
- people-data-auditor(11-test): test_reconciliation.py에서 payrollHeadcount asOfActive/asOfOnLeave/asOfTotal/monthEndActive/monthEndTotal = 406/21/427/411/432 대사
- onboarding-plan-analyst(07-onboarding)는 병렬 형제 — 이 산출물을 읽지 않는다

