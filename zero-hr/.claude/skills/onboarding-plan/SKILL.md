---
name: onboarding-plan
description: "정제 데이터(입사 예정자 27·마스터 427·퇴사 예정자)와 이직 리스크·월말 예측에서 온보딩 담당 전용 파생 '온보딩 계획'(data/stats/onboarding-plan.json, DATA_CONTRACT v2 §11 + §4-5)을 생성·대사한다 — ISO 주차별 입사 타임라인, 조직별 배치(입사자 수·월말까지 수·조직장 VP·버디 후보), 준비 체크리스트 6항목 상태(가상·seed 고정), 입사 90일 코호트(riskBand 조인), 퇴사 예정 14명 중 재직 1년 미만 비율, 온보딩 담당 fitCriteria 미충족 gap, 핸드오프 로그 07-onboarding. '온보딩 계획', '온보딩 보드', '입사 예정자 타임라인', '주차별 입사', '조직별 배치', '버디 후보', '온보딩 체크리스트', '90일 코호트', '조기 이탈률', 'Onboarding 데이터', 'onboard.json 원천'을 만들거나 클린저·리스크·예측·니즈 데이터가 바뀐 뒤 '다시/재실행/수정/보완/업데이트'할 때 반드시 이 스킬을 사용한다. 급여 대상 파생은 payroll-close, 인원 통계는 headcount-stats, 월말 예측은 month-end-forecast가 담당한다."
---

# onboarding-plan — 온보딩 계획 생성 (DATA_CONTRACT v2 §11)

온보딩 담당은 매주 월요일 "이번 주·다음 주에 누가 어느 조직으로 오나, 준비는 됐나, 누가 버디를 하나, 최근 입사자 중 흔들리는 사람은 없나, 곧 나가는 사람 중 1년도 안 된 사람이 얼마나 되나"를 확인한다.
그 답은 정제 입사 예정자·마스터·퇴사 예정자·이직 리스크·월말 예측에 흩어져 있다 — 이 스킬은 그것을 한 파일(`data/stats/onboarding-plan.json`)로 모은다.
Everyday People Agent **Onboarding**(`site/onboard/`)은 이 파일만 읽으므로 여기 없는 것은 화면에 없다.

## 입력 / 출력

| 구분 | 경로 | 필수 | 용도 |
|---|---|---|---|
| 입력 | `data/clean/planned-joiners.clean.csv` | 필수 | §3-3 입사 예정자 27(9월 19 + 10월 8) → timeline·byDepartment·checklist |
| 입력 | `data/clean/headcount-master.clean.csv` | 필수 | §3-1 정제 마스터 427 → 버디 후보·조직장·90일 코호트·재직기간 |
| 입력 | `data/clean/planned-leavers.clean.csv` | 권장 | §3-4 퇴사 예정자 → earlyAttrition(없으면 0/0 + gap) |
| 입력 | `data/reference/org-chart.csv` | 선택 | §1 조직 11 순서·명칭 |
| 입력 | `data/stats/attrition-risk.json` | 선택 | §4-3 `byEmployee[].riskBand` 조인(없으면 null + gap) |
| 입력 | `data/stats/month-end-forecast.json` | 선택 | §4-2 `totals.plannedIn`(19)과 월말 이전 입사 예정 수 교차 대사 |
| 입력 | `personas/persona-needs.json` | 선택 | §9 온보딩 담당(`code: onboarding`) `fitCriteria`·`requiredFields` 검사 → gaps |
| 출력 | `data/stats/onboarding-plan.json` | — | §11 + §4-5 shape. 유일한 작성자는 스크립트 |
| 출력 | `_workspace/handoff/07-onboarding.md` | — | 핸드오프 로그 5절(스크립트가 시작 시 쓰고 종료 시 덮어쓴다) |

원천(`data/raw/`)은 읽지 않는다. 원천은 중복 사번·미정규 조직명을 포함해 타임라인 합계가 27과 어긋나고, 그 보정은 클린징 로그에만 있어야 한다(GLOSSARY 관계 절).

## 절차

1. **입력 확인.** 필수 2종이 없으면 실행하지 않는다(스크립트도 exit 1로 거부하고 실패 로그를 남긴다). 클린저 선행을 요청한다.
2. **실행.**
   ```bash
   python3 .claude/skills/onboarding-plan/scripts/onboarding_plan.py --root /Users/yang/development/zero-hr --as-of 2026-09-23
   ```
   - `--root` 기본 `/Users/yang/development/zero-hr`, `--as-of` 기본 `2026-09-23`, `--seed` 기본 `20260923`(체크리스트 난수 — 바꾸지 않는다)
   - 종료 코드 `0` 파일 작성(`status` ok|partial) · `1` 필수 입력 없음 · `2` 인자 오류. stdout **마지막 줄**이 요약 JSON 1행
   - `partial` = `missing-input`·`invalid-row`·`reconciliation-mismatch` gap 중 하나라도 있을 때. `fit-criterion-unmet`·`beyond-horizon`·`past-planned-hire`·`dept-lead-fallback`만 있으면 `ok`
3. **검증(완성 조건).** 산출물을 열어 아래 표를 확인한다. 하나라도 어긋나면 완성이 아니다.
4. **반환 + 핸드오프.** 요약 JSON과 `provenance.gaps`를 에이전트 정의의 구조화 출력 shape으로 반환한다. 최종 텍스트는 사람용 메시지가 아니라 반환 데이터다. 핸드오프 로그는 스크립트가 썼는지(`handoffLog` 경로, 5개 H2) 확인한다.

### 검증 표

| 확인 | 기준 | 왜 |
|---|---|---|
| `provenance.reconciliation.match` | `true` — 타임라인 합계 = 정제 입사 예정자 행 수(**27**, 무효 행 0) | §11 assert. 제품 3종이 같은 입사 예정자 수를 봐야 한다 |
| `provenance.reconciliation.monthEndMatch` | `true` 또는 `null`(예측 없음) — 월말 이전 입사 예정(**19**) = `forecast.totals.plannedIn` | Insight·Payroll Close의 월말 입사 수와 Onboarding 주간 보드가 같아야 한다 |
| `horizonEnd` | `2026-10-31`. 10월 입사 8명(Engineering 3·Data & AI 2·Sales 2·Product 1)이 타임라인에 있다 | §2-3 |
| `timeline[].week`/`weekStart` | `YYYY-Www`, 월요일. 9/28~10/4가 `2026-W40` 한 주 | `isocalendar()` |
| `byDepartment[]` | 입사 예정 ≥ 1 조직만(데모 9). Engineering `joiners` 8 / `joinersByMonthEnd` 5. `deptLeadEmpId`는 재직 VP | §4-5, §2-7 |
| `byDepartment[].buddyCandidates` | 각 ≤ 3, 같은 조직 재직, `tenureYears` 2.0~6.0, `level` ∈ IC3/Senior/Lead, `riskBand` 전부 `낮음`(리스크 파일 있을 때) | §11 버디 규칙 |
| `checklist` | `items` = 계정 발급·장비 지급·보안 교육·조직 소개·버디 배정·30일 면담(순서 고정), `status` 길이 = 27 | 체크리스트 없는 입사자는 화면에서 빈 행 |
| `earlyTenureCohort` | `members[]`에 `name`·`birthDate` 없음, `riskBand`는 등급만 | pii-minimization-policy |
| `earlyAttrition.totalLeavers` | **14** = §4-5 plannedOut 모집단(예정일 ≤ 월말 ∧ unknown-emp 제외 ∧ 마스터 재직) | Insight "퇴사 예정 14"와 같은 모집단 |
| 산출물 전체 | 문자열 `birthDate` 없음 | pii-minimization-policy |

## 산출물 구조 — `data/stats/onboarding-plan.json` (§11)

```json
{"asOfDate":"2026-09-23","horizonEnd":"2026-10-31",
 "timeline":[{"week":"2026-W39","weekStart":"2026-09-21","joiners":[{"joinerId":"J001","name":"...","deptCode":"D03","department":"Engineering","plannedHireDate":"2026-09-28","employmentType":"정규직","level":"IC2"}]}],
 "byDepartment":[{"deptCode":"D03","department":"Engineering","joiners":8,"joinersByMonthEnd":5,"buddyCandidates":[{"empId":"...","name":"...","tenureYears":3.2,"level":"Senior","riskBand":"낮음"}],"deptLeadEmpId":"..."}],
 "checklist":{"items":["계정 발급","장비 지급","보안 교육","조직 소개","버디 배정","30일 면담"],"status":[{"joinerId":"J001","계정 발급":"done","장비 지급":"pending","보안 교육":"pending","조직 소개":"pending","버디 배정":"done","30일 면담":"pending"}]},
 "earlyTenureCohort":{"definition":"기준일 기준 입사 90일 이내 재직자","members":[{"empId":"...","deptCode":"...","hireDate":"...","daysSinceHire":0,"riskBand":"중간"}],"count":0,"highRiskCount":0},
 "earlyAttrition":{"definition":"퇴사 예정자(14) 중 재직기간 1년 미만 비율","under1YearLeavers":0,"totalLeavers":14,"rate":0.0,"byDepartment":{"D03":{"department":"Engineering","under1YearLeavers":0,"totalLeavers":4,"rate":0.0}}},
 "provenance":{"sources":["..."],"script":".claude/skills/onboarding-plan/scripts/onboarding_plan.py",
   "reconciliation":{"timelineJoiners":27,"plannedJoinersValidRows":27,"match":true,"monthEndJoiners":19,"forecastPlannedIn":19,"monthEndMatch":true},
   "gaps":[{"kind":"fit-criterion-unmet","criterionId":"O-F4","criterion":"...","weight":4,"evidence":"...","reason":"..."}],
   "seed":20260923,"checklistNote":"...","buddyRule":"...","deptLeadRule":"...","pii":"...","fitCriteriaChecked":{"fitCriteria":12,"requiredFields":1}}}
```

- 최상위 키와 `timeline`·`byDepartment`·`checklist`·`earlyTenureCohort`·`earlyAttrition`의 필드는 §11·§4-5 그대로다. 계약에 없는 최상위·항목 필드를 추가하지 않는다 — 필요하면 `contractGaps`로 보고한다
- `provenance`는 계약 4키(`sources, script, reconciliation, gaps`) 뒤에 실행 메타(`seed, checklistNote, buddyRule, deptLeadRule, pii, fitCriteriaChecked`)를 덧붙인다. 체크리스트가 가상임을 산출물 안에 말할 자리가 계약에 없기 때문이며, 이 확장은 contractGap으로 보고돼 있다
- 성명은 `timeline[].joiners`·`buddyCandidates`에만(온보딩 업무상 필요). 생년월일·연령대·리스크 점수는 어디에도 없다

## 계산 규칙 (Why 포함)

| 항목 | 규칙 | 이유 |
|---|---|---|
| `timeline` | 유효한 `plannedHireDate`가 있는 **모든** 정제 행. 주차 = `date.isocalendar()`, `weekStart` = 그 주 월요일. 주 안은 입사일·joinerId 순 | 합계 27 assert가 표시 범위보다 우선. horizonEnd 이후 행은 넣되 `beyond-horizon` gap |
| `horizonEnd` | 기준일이 속한 달의 다음 달 말(2026-10-31) | 10월 입사 8명이 IT·총무 월간 수요 예고에 필요(O-F11) |
| `byDepartment` | 입사 예정 ≥ 1 조직만, org-chart 순서. `joinersByMonthEnd` = 입사일 ≤ 월말 | §4-5. 입사 없는 조직은 온보딩 담당의 화면에 없어야 한다 |
| `deptLeadEmpId` | 조직 재직자 중 `level = VP`, 최장 재직, 동률 사번 오름차순. VP 없으면 최고 레벨 + `dept-lead-fallback` gap | §2-7 "조직마다 VP ≥ 1". 조직도에 리더 컬럼이 없으므로 레벨로 정한다 |
| `buddyCandidates` | 같은 조직 재직(휴직 제외) ∧ `tenureYears` 2.0~6.0 ∧ `level` ∈ {IC3, Senior, Lead} ∧ `riskBand = 낮음` → 재직기간 긴 순 최대 3 | §11. 리스크 파일이 없으면 리스크 조건을 빼고 `missing-input` gap — 조건을 몰래 완화하지 않는다 |
| `checklist.status` | `random.seed(20260923)` 고정. 항목별 리드타임(계정 14일·장비 10일·보안 3일·조직 소개 당일·버디 7일·30일 면담은 입사 후 30일)으로 입사일이 가까울수록 done 확률↑. 버디 후보 없는 조직의 "버디 배정"은 항상 pending | 실제 진행 시스템이 없다. seed 고정이라 재실행 동일. 버디 pending은 난수가 아니라 데이터 근거 |
| `earlyTenureCohort` | `status = 재직` ∧ 기준일−90일 ≤ `hireDate` ≤ 기준일. `riskBand` 조인, `highRiskCount` = `높음` 수 | 재직 전제(GLOSSARY `재직 인원`). 입사일 > 기준일(`date-logic` 행)은 자연히 제외 |
| `earlyAttrition` | 퇴사 예정자 중 예정일 ≤ 월말 ∧ 마스터에 있음 ∧ 마스터 `status = 재직`(= §4-5 plannedOut 모집단, 14). `under1YearLeavers` = `tenureYears < 1`. `rate` 4자리. `byDepartment` = `{deptCode: {department, under1YearLeavers, totalLeavers, rate}}` | 예측의 `plannedOut`과 같은 14명이어야 제품 간 숫자가 같다. `tenureYears`는 정제 마스터 값(없으면 입사일로 계산) |
| `reconciliation.match` | `timelineJoiners == plannedJoinersValidRows` ∧ 무효 행 0 | 무효 행이 있으면 타임라인이 정제 행 전부를 담지 못한 것 — 클린저 미해결과 대조 |
| `reconciliation.monthEndMatch` | `monthEndJoiners == forecast.totals.plannedIn`. 예측 없으면 `null` | 선택 입력이라 결손은 실패가 아니라 "미검증" |

## gaps 어휘 (`provenance.gaps[].kind`)

하류(product-builder·product-judge·people-data-auditor)가 이 어휘로 분기한다. 새 kind를 만들지 않는다.

| kind | 뜻 | status | 후속 |
|---|---|---|---|
| `missing-input` | 선택 입력 결손·파싱 실패(리스크·퇴사 예정자·조직도·예측·니즈) | partial | 해당 단계 실행 후 재실행 |
| `invalid-row` | `plannedHireDate` 없음/비정상 → 타임라인 제외(`criterionId` = joinerId) | partial | 클린저 `unresolvedItems`와 대조 |
| `reconciliation-mismatch` | 월말 이전 입사 예정 ≠ `forecast.totals.plannedIn` | partial | 클린저·예측 입력 차이 확인 후 두 단계 재실행 |
| `beyond-horizon` | horizonEnd 이후 입사 예정(타임라인에는 포함) | ok | 제품에서 "이후 입사"로 구분 |
| `past-planned-hire` | 입사 예정일 ≤ 기준일 | ok | 마스터 반영 여부 확인 |
| `dept-lead-fallback` | 조직에 재직 VP 없음 → 최고 레벨 대체(`criterionId` = deptCode) | ok | 클린저·수집기의 §2-7 레벨 제약 확인 |
| `fit-criterion-unmet` | 온보딩 담당 `fitCriteria`의 `evidence`가 이 산출물에서 해소되지 않음(`criterionId`·`weight` 동봉) | ok | product-builder(onboard)가 다른 데이터로 충족하거나 심판이 감점 |
| `required-field-missing` | `requiredFields`의 `onboarding-plan.*` 경로가 산출물에 없음 | ok | 계약·스크립트 정렬 |

### fit evidence 해소 규약 (persona-needs 스킬과 동일)
- `;`로 이어진 복수 근거는 전부 해소돼야 충족. 미해소 사유는 `reason`에 `; `로 합친다
- `onboarding-plan.`/`onboardingPlan.` 접두: 산출물 안의 점 경로가 존재하고 비어 있지 않음. `[]`는 **어느 원소든** 해소되면 충족(첫 조직에 버디가 없다고 필드가 없는 것이 아니다)
- `planned-joiners`·`headcount-master`·`planned-leavers`·`attrition-risk`·`org-chart`·`month-end-forecast` 접두: 파일 존재만 확인(값 검증은 그 단계의 몫)
- `reconciliation:A=B`: 양쪽 해소 ∧ `provenance.reconciliation.match` ∧ `monthEndMatch ≠ false` ∧ 무효 행 0
- `policy:`·`site/`·`reports/` 접두: 데이터 필드가 아니므로 통과(product-judge의 몫)
- 그 밖: "이 스크립트가 만들지 않는 데이터"로 미충족 — 제품 단계에서 판단

## 반환 JSON (워크플로우 소비용)

스크립트 요약(stdout 마지막 줄)을 뼈대로 에이전트 정의 "구조화 출력" shape(`status, asOfDate, horizonEnd, artifacts, handoffLog, summary, reconciliation, unresolved, provenanceGaps, contractGaps, notes`)으로 반환한다. 요약 예:

```json
{"status":"ok","asOfDate":"2026-09-23","horizonEnd":"2026-10-31","output":"data/stats/onboarding-plan.json","handoffLog":"_workspace/handoff/07-onboarding.md","timelineJoiners":27,"weeks":6,"departmentsWithJoiners":9,"monthEndJoiners":19,"nextMonthJoiners":8,"byDepartment":[{"deptCode":"D03","department":"Engineering","joiners":8,"joinersByMonthEnd":5,"buddyCandidates":3,"deptLeadEmpId":"E0001"}],"buddyCoverage":{"departmentsWithBuddy":9,"departmentsWithJoiners":9},"checklistRows":27,"earlyTenureCohort":{"count":0,"highRiskCount":0},"earlyAttrition":{"rate":0.0,"under1YearLeavers":0,"totalLeavers":14},"reconciliation":{"timelineJoiners":27,"plannedJoinersValidRows":27,"match":true,"monthEndJoiners":19,"forecastPlannedIn":19,"monthEndMatch":true},"plannedJoinersRowsIn":27,"unresolved":[],"fitCriteriaChecked":{"fitCriteria":12,"requiredFields":1},"gapCount":0,"gapKinds":[],"provenanceGaps":[]}
```

`notes`에는 체크리스트가 가상임과 대사 결과 한 줄, `partial`이면 먼저 돌려야 할 상류 단계를 적는다. 성명은 반환에 싣지 않는다.

## 핸드오프 로그 — `_workspace/handoff/07-onboarding.md`

스크립트가 시작 시 "실행 중"으로 쓰고 종료 시 덮어쓴다(Operating Rule 2). 5개 H2 고정: `## 시도한 것`(명령·생성 항목·status) / `## 본 데이터·근거`(입력 존재 여부·행 수·계약 조항·fit 검사 건수) / `## 실패한 것`(gaps 전부) / `## 검증된 것`(대사 27·19, 주차·조직·버디·체크리스트 수, 코호트·조기 이탈, PII) / `## 다음 agent 인계점`(product-builder·product-judge·people-data-auditor·재실행 조건).
스크립트가 로그를 쓰기 전에 죽으면(traceback) 에이전트가 같은 5절로 직접 남긴다 — 다음 실행자가 같은 벽에 다시 부딪히지 않게.

## 재실행 / 수정 / 보완
- 정제 데이터·리스크·예측·니즈가 갱신되면 같은 명령으로 재실행한다. 결정적(seed 고정, 시각 필드는 핸드오프 로그에만)이라 같은 입력이면 같은 파일 — diff로 변경을 확인한다
- 기준일은 `--as-of`만 바꾼다. 월말·horizonEnd·90일 창이 따라온다
- 규칙(버디·리드타임·조직장·모집단)을 바꾸려면 DATA_CONTRACT §11 개정이 먼저다. 스크립트 상수(`BUDDY_*`, `CHECKLIST_LEAD_DAYS`, `DEPT_LEAD_LEVEL`, `EARLY_TENURE_DAYS`)는 계약을 따라간다
- 산출물 숫자를 손으로 고치지 않는다. 숫자가 이상하면 입력이나 규칙이 이상한 것이다

## 하지 않는 것
- 급여 대상·일할 계산(`payroll-close`), 인원 통계(`headcount-stats`), 월말 예측(`month-end-forecast`), 리스크 점수(`attrition-risk`)를 재계산하지 않는다 — 같은 숫자를 두 곳에서 만들면 갈라진다
- 실제 진행 상태를 아는 척하지 않는다 — 체크리스트는 가상이며 `provenance.checklistNote`가 그것을 말한다
- 버디를 "배정"하거나 조직 배치를 "결정"하지 않는다 — 후보와 제안까지. 결정은 온보딩 담당(사람)의 몫(approval-gate-policy 정신)
- 제품 스냅샷 `site/data/onboard.json` 조립 — `product-builder`의 일
