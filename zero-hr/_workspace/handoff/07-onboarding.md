# 07-onboarding — onboarding-plan-analyst — ok (2026-09-23T17:10:52 → 2026-09-23T17:10:52)

## 시도한 것
- 2026-09-23T17:10:52: `python3 .claude/skills/onboarding-plan/scripts/onboarding_plan.py --root /Users/yang/development/zero-hr --as-of 2026-09-23 --seed 20260923`
- 정제 입사 예정자·마스터에서 timeline(ISO 주차)·byDepartment(버디·조직장 VP)·checklist(가상, seed 20260923)·earlyTenureCohort(90일)·earlyAttrition(퇴사 예정 중 1년 미만) 생성
- data/stats/onboarding-plan.json에 §11 shape로 작성, 종료 status=ok

## 본 데이터·근거
- 입력 존재 여부: data/clean/planned-joiners.clean.csv=O, data/clean/headcount-master.clean.csv=O, data/clean/planned-leavers.clean.csv=O, data/reference/org-chart.csv=O, data/stats/attrition-risk.json=O, data/stats/month-end-forecast.json=O, personas/persona-needs.json=O
- 정제 입사 예정자 27행(유효 27, 무효 0) · 정제 마스터 427행 · 퇴사 예정자 19행 · riskBand 조인 406명
- 계약 근거: §11 버디 규칙(재직 2~6년·리스크 낮음·IC3~Lead·≤3), §4-5 byDepartment=입사 예정 ≥1 조직만, §4-5 plannedOut 모집단(≤월말·unknown-emp 제외·재직) = earlyAttrition 분모, §2-7 조직마다 VP ≥ 1 → deptLeadEmpId=VP
- fitCriteria 12건·requiredFields(onboarding-plan.*) 1건 검사(personas/persona-needs.json)

## 실패한 것
- (없음)

## 검증된 것
- 타임라인 합계 27 vs 정제 입사 예정자 27행(유효 27·무효 0) → match=True (무효 행이 있으면 false — 타임라인이 정제 행 전부를 담아야 §11 assert)
- 월말(2026-09-30) 이전 입사 예정 19 vs forecast.totals.plannedIn 19 → monthEndMatch=True
- 주차 5개(isocalendar), 입사 예정 조직 9개, 버디 후보 ≥1 조직 9개, 체크리스트 행 27 = 타임라인 27
- 90일 코호트 12명(고위험 1) · 조기 이탈 1/14 = 0.0714
- PII: earlyTenureCohort·earlyAttrition에 성명·생년월일 없음, timeline·buddyCandidates에 생년월일 없음

## 다음 agent 인계점
- product-builder(onboard): `data/stats/onboarding-plan.json`를 site/data/onboard.json의 onboardingPlan으로 내장. O-F7(미해결 플래그)은 plannedJoiners 조인으로 표시(타임라인에는 unresolvedFlags 없음 — 계약 §11)
- product-judge(onboarding 옹호자): provenance.gaps의 fit-criterion-unmet 0건(없음)이 감점 근거
- people-data-auditor: tests/test_reconciliation.py에서 timelineJoiners=27·monthEndJoiners=19·earlyAttrition.totalLeavers=14 대조
- 재실행 조건: 클린저·attrition-risk·forecast·persona-needs 갱신 시 같은 명령으로 재실행(멱등, seed 고정)
