# 09 — product-judge (persona-advocate:onboarding) 핸드오프

## 1. 시도 (읽은 파일 · grep/python 명령)
- `.claude/agents/product-judge.md`, `.claude/skills/product-judge/SKILL.md` §5·§7, `.claude/skills/product-judge/references/rubric-onboarding.md` 전문
- `personas/persona-needs.json` → `persona=onboarding`의 `keyQuestions`·`rubric`(O-Q1~O-Q5)·`fitCriteria`(O-F1~O-F13) 전부
- `_workspace/judging/mechanical.json` → `products.{insight,payroll,onboard}.criteriaMet/coverage/weightedCoverage/sections/piiChecks`와 `advocate.onboarding.{insight,payroll,onboard}` 그대로 복사(재계산 없음)
- `site/onboard/index.html`(111KB) — `grep -o 'data-section="[^"]*"'`로 10개 섹션 확인 후 python으로 `timeline`·`departments`·`checklist`·`next-month`·`cohort`·`early-attrition`·`reconciliation`·`kpi`·`header` 슬라이스, JS 렌더 로직(`awk 'NR>=267 && NR<=600'`)에서 이번 주/다음 주 배지·D-day·버디 후보 없음 문구·체크리스트 진행률·코호트 정렬 로직 확인
- `site/insight/index.html`(204KB) — `planned-moves`·`risk-people`·`department-gap`·`org-lead` 섹션 슬라이스
- `site/payroll/index.html`(82KB) — `prorations-planned`·`headcount`·`risks`·`checklist` 섹션 슬라이스
- `site/data/onboard.json`·`insight.json`·`payroll.json` — python으로 `onboardingPlan.timeline[0]`·`byDepartment[0]`·`checklist`·`earlyTenureCohort`·`earlyAttrition`·`provenance`, `forecast.plannedJoiners[0]`, `payrollClose.prorations.plannedJoinersByMonthEnd[0]` 필드 직접 확인(성명·주차·레벨 유무)
- `api/tools.json` — `onboarding.get_timeline`·`get_department_plan`·`get_checklist`·`get_early_tenure_cohort` 4종 설명·role별 PII 마스킹 규칙 확인

## 2. 근거 (루브릭 버전 · 니즈 파일 asOfDate)
- 루브릭: `rubric-onboarding.md`(R1~R6, must=R1·R2·R3 / nice=R4·R5·R6, 실격 조건 4종)
- 니즈 파일: `personas/persona-needs.json` `asOfDate`와 동일 스코프(2026-09-23), fitCriteria O-F1~O-F13 13개
- 기계 채점: `mechanical.json` — Onboard 자기 제품 coverage 1.0(13/13), Insight advocateCoverage 0.8636(met 5/6), Payroll advocateCoverage 0.8636(met 5/6, Onboard와 동일 목록) — 그대로 복사

## 3. 실패 (unverifiable · 열 수 없는 스냅샷)
- 없음 — 세 제품 HTML·스냅샷 모두 정상 파싱, `unverifiable` 처리 대상 없음
- 특기: O-F7(미해결 플래그 배지)은 코드·evidence 경로는 met이나, `onboard.json.plannedJoiners[].unresolvedFlags`가 27건 전부 빈 문자열이라 배지 노출 자체는 이번 스냅샷으로 실증 불가 — 정성 점수(R6=8)에 반영, 제품 결함 아님을 note에 명시

## 4. 검증 (기계 채점 수 · PII 검사 수)
- 기계 채점: 3개 제품 `criteriaMet` 합계 15(insight)+14(payroll)+13(onboard)=42건 그대로 복사, 재계산 없음
- 옹호자 커버리지(advocateCoverage): O-F1~O-F13(13개 기준) × 3개 제품 = 39 판정, `mechanical.json`에서 그대로 복사
- PII 검사: 3개 제품 × 3건 = 9건 전부 `passed: true`(생년월일 없음, riskScore 없음, 90일 코호트 성명 없음/경영진 성명 조인 없음/급여 금액 필드 없음) — 그대로 복사
- 정성 채점: R1~R6 × 3개 제품 = 18개 항목, 전부 `data-section` 근거 인용

## 5. 다음 인계점
- `aggregate_judgments.py`가 읽을 파일: `_workspace/judging/onboarding.json`(본 산출물), 같은 경로에 `payroll.json`·`head-of-hr.json`(병렬 심판)
- 통합 빌더가 볼 mustFix 4건: Insight(department-gap 조직장 미조인, 체크리스트 섹션 부재) · Payroll(headcount 조직장·클러스터링 부재, checklist 도메인 불일치) — 전부 "Onboard 탭을 그대로 흡수" 방향 근거
- Onboard 자체는 must 항목(R1·R2·R3) 전부 8점 이상으로 mustFix 없음 — `scores.onboard=8.7`이 세 제품 중 최고
- niceToHave 6건 중 4건은 Onboard 자체 개선(조직별 이탈률 KPI 승격·지연 배지·TO 맥락 연결·플래그 실증), 2건은 Insight/Payroll이 참고용 필드(성명·레벨·주차)를 보강하면 좋다는 제안
