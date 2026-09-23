# 참고 프로필 — 온보딩 담당 (onboarding → Onboarding)

이 파일은 **후보 목록**이다. 정답이 아니다. 계약 수치(월말 입사 예정 19명 — Engineering 5·Sales 3·Product 3·Customer Success 2·Data & AI 2·Design 1·Marketing 1·People 1·
Finance 1, 10월 8명 — Engineering 3·Data & AI 2·Sales 2·Product 1, 타임라인 합계 27, 체크리스트 6항목, 버디 후보 최대 3명)로 문장을 구체화하고,
JTBD 셀프 인터뷰 답변에 따라 항목을 고르고 버린다.
evidence·source·requiredFields는 DATA_CONTRACT **v2** §11(`onboarding-plan.json`: `byDepartment[].deptLeadEmpId`, `joinersByMonthEnd`, `earlyTenureCohort`, `earlyAttrition`) 경로다.

**경계:** 채용 파이프라인(공고·면접)은 다루지 않는다(GLOSSARY 제외 절). 입사 예정자는 "입사일 확정" 이후만이다.
신설 조직 시나리오(`newTeamOnboarding`)는 v2 계약에 없다 — 조직장 유무는 `byDepartment[].deptLeadEmpId`로 본다.

## 1. 누구인가 (profile 후보)

㈜온다테크 Operations 그룹 People 조직의 **온보딩 담당**(People Ops, 레벨 IC2~IC3). 입사일이 확정된 사람이 첫날 계정·장비·교육·버디가 준비된 상태로
출근하게 만든다. IT·총무·보안·조직장 네 곳에 요청을 보내고 회신을 스프레드시트로 추적한다. 한 달의 리듬: 매주 월요일 향후 2주 점검 →
입사 D-7/D-3/D-0 이벤트 → D+30/60/90 면담. 절대 틀리면 안 되는 것: **입사자가 첫날 아무도 모르는 자리에 앉는 것**.
이번 달 특이 사항: 월말까지 19명이 9개 조직에 나뉘어 입사하고, Engineering에만 5명(10월 3명 추가)이 몰린다.

## 2. 목표 후보 (goals)

- 입사 예정자 전원(월말 19·10월 8)이 입사일에 계정·장비·교육·버디가 준비된 상태로 첫날을 맞게 한다
- 같은 조직에 몰리는 입사자(Engineering 월말 5·horizon 8)를 묶어 일괄 온보딩을 계획하고 조직장을 확인한다
- 입사 90일 코호트를 추적해 조기 이탈 신호(리스크 등급)를 조직장에게 먼저 전달한다
- 조직장·IT·총무·보안과 준비 상태를 한 화면(체크리스트 매트릭스)으로 공유한다
- 입사 예정자 데이터 오류(소속 변형·일자 포맷)를 입사 전에 해소한다

## 3. JTBD 후보 (jobsToBeDone — 5개 이상 고른다)

| id | job | trigger | frequency | importance |
|---|---|---|---|---|
| O1 | 매주 월요일 다음 2주 입사 예정자를 주차별로 보고 준비 체크리스트를 시작한다 | 매주 월요일 | weekly | 5 |
| O2 | 입사자마다 배치 조직·조직장·직군·레벨·고용유형을 확인해 조직 소개·좌석·장비를 준비한다 | 입사 D-7 | event | 5 |
| O3 | 같은 조직에 몰리는 입사자(Engineering 5명)를 묶어 공통 교육·팀 빌딩을 계획하고 조직장 배정을 확인한다 | 조직별 입사 3명 이상 | event | 4 |
| O4 | 입사자마다 같은 조직의 버디 후보(재직 2~6년·IC3~Lead·리스크 낮음, 최대 3명)를 고르고 배정한다 | 입사 D-3 | event | 4 |
| O5 | 입사 90일 이내 재직자의 30/60/90일 면담을 관리하고 리스크 등급 높음 신호를 조직장에 전달한다 | 매월 11~20일 | monthly | 4 |
| O6 | 퇴사 예정 14명 중 재직 1년 미만 비율(조기 이탈률)을 조직별로 보고 온보딩 개선점을 찾는다 | 분기 초 | quarterly | 3 |
| O7 | 입사 예정자의 미해결 플래그(소속 변형·일자 포맷)를 입사 전에 채용·조직장과 확인해 해소한다 | 수시 | event | 3 |
| O8 | 다음 달 입사 예정자(10월 8명)를 확정해 IT·총무에 월간 수요를 예고한다 | 매월 21~말일 | monthly | 3 |

## 4. 월간 캘린더 초안 (calendar)

| when | task |
|---|---|
| 매주 월요일 | 향후 2주 입사 예정자 점검, 체크리스트 진행률 확인, 지연 항목 IT·총무 독촉 |
| 입사 D-7 | 계정 발급·장비 지급을 IT/총무에 요청하고 조직장에게 배치·좌석을 확인한다 |
| 입사 D-3 | 버디 배정 확정, 보안 교육 일정 확정 |
| 입사 D-0 | 조직 소개·오리엔테이션 진행, 체크리스트 완료 확인 |
| 입사 D+30/60/90 | 30/60/90일 면담, 수습 평가 일정 안내(수습 3개월 가정), 리스크 등급 확인 |
| 매월 1~3일 | 당월 입사 예정자 전체 확정, 조직별 일괄 온보딩 편성(Engineering 5명) |
| 매월 21~말일 | 다음 달 입사 예정자(8명) 확인, IT·총무 월간 수요 예고, 90일 코호트 리스크 점검 |
| 분기 초 | 조기 이탈률(퇴사 예정 중 1년 미만) 리뷰와 온보딩 개선점 정리 |

## 5. 핵심 질문 후보 (keyQuestions)

- 이번 주·다음 주에 누가 어느 조직으로 입사하나?
- 각 입사자의 체크리스트 6항목은 어디까지 됐고 입사일까지 남은 항목은 무엇인가?
- 입사자가 몰리는 조직은 어디이고(Engineering 5명) 그 조직의 조직장은 누구인가?
- 각 입사자에게 붙일 같은 조직 버디 후보는 누구인가?
- 입사 90일 이내 인원은 몇 명이고 그중 리스크 높음은 몇 명인가?
- 퇴사 예정자 중 재직 1년 미만은 몇 명이고 어느 조직인가?
- 소속 표기나 입사 예정일이 이상한 입사 예정자가 있나?

## 6. KPI 후보 (kpis — source는 스냅샷 키 경로)

| name | definition | source |
|---|---|---|
| 향후 입사 예정 수 | 기준일~horizonEnd(2026-10-31) 입사 예정자 27명(월말 19 + 10월 8) — 타임라인 합계 = 정제 입사 예정자 assert (§11) | `onboardingPlan.timeline; plannedJoiners` |
| 체크리스트 완료율 | done ÷ (입사자 × 6항목) (§11 `checklist.status`) | `onboardingPlan.checklist.status` |
| 조직별 일괄 온보딩 대상 조직 수 | 월말 입사 예정 3명 이상 조직 수(Engineering 5·Sales 3·Product 3) (§11 `byDepartment[].joinersByMonthEnd`) | `onboardingPlan.byDepartment[].joinersByMonthEnd` |
| 버디 후보 확보율 | 버디 후보 ≥ 1인 조직 ÷ 입사 예정 조직(9) (§11 `byDepartment[].buddyCandidates`) | `onboardingPlan.byDepartment[].buddyCandidates` |
| 90일 코호트 규모·고위험 수 | 기준일 기준 입사 90일 이내 재직자 수와 riskBand=높음 수 (§11 `earlyTenureCohort`) | `onboardingPlan.earlyTenureCohort.count; onboardingPlan.earlyTenureCohort.highRiskCount` |
| 조기 이탈률 | 퇴사 예정자(14) 중 재직기간 1년 미만 비율 (§11 `earlyAttrition.rate`; 업계 벤치마크는 참고치) | `onboardingPlan.earlyAttrition.rate` |

## 7. 통증점 후보 (pains — 예산 12h)

| pain | costHoursPerMonth |
|---|---|
| 입사 예정자 명단 취합·소속 확인(채용·조직장 왕복, 소속 변형 2·일자 포맷 3 정리) | 4 |
| 체크리스트 스프레드시트 수동 관리와 IT·총무 독촉 | 5 |
| 버디 선정·30/60/90일 면담 일정 관리 | 3 |

합 12h(§8 40h 중 수집·통합 8h의 입사 예정자 취합 몫 + 리포트·조율 몫).

## 8. 필요 필드 후보 (requiredFields — `{파일 스템}.{컬럼}`)

`planned-joiners.joinerId` `planned-joiners.name` `planned-joiners.deptCode` `planned-joiners.department` `planned-joiners.jobFamily` `planned-joiners.level`
`planned-joiners.employmentType` `planned-joiners.plannedHireDate` `planned-joiners.unresolvedFlags`
`org-chart.deptCode` `org-chart.department` `org-chart.establishedOn`
`headcount-master.empId` `headcount-master.name` `headcount-master.deptCode` `headcount-master.level` `headcount-master.tenureYears` `headcount-master.hireDate` `headcount-master.status`
`planned-leavers.empId` `planned-leavers.deptCode` `planned-leavers.plannedTerminationDate`
`attrition-risk.byEmployee.riskBand` `onboarding-plan.byDepartment.deptLeadEmpId`

성명은 업무상 필요(첫날 맞이·버디 연결). 생년월일은 요구하지 않는다(`ageBand`). 리스크는 등급만, 점수는 요구하지 않는다.

## 9. 결정 후보 (decisions)

버디 배정 · 조직별 일괄 온보딩 편성(Engineering) · 입사 준비 완료/보류 판단 · 90일 면담 대상 우선순위 · 소속·일자 미해결 입사자 확인 요청 ·
IT·총무 월간 수요 통보 · 조직장 미배정 조직 임시 리더 요청(승인 gate: 조직 구조 변경)

## 10. fit 기준 후보 (fitCriteria — 8개 이상 고른다, weight 5는 1/3 이하)

| id | criterion | weight | evidence |
|---|---|---|---|
| O-F1 | 주차별 입사 타임라인에 입사 예정자 27명 전원이 성명·조직·입사 예정일·고용유형·레벨과 함께 보이고, 기준일 기준 이번 주·다음 주가 강조된다 | 5 | `onboarding-plan.timeline[].weekStart; onboarding-plan.timeline[].joiners; site/onboard/index.html` |
| O-F2 | 조직별 배치 현황(입사자 수·월말까지 수·조직장 사번)을 보고 입사자가 몰린 조직(Engineering 월말 5·horizon 8)이 묶여 보인다 | 5 | `onboarding-plan.byDepartment[].joiners; onboarding-plan.byDepartment[].joinersByMonthEnd; onboarding-plan.byDepartment[].deptLeadEmpId` |
| O-F3 | 입사자별 체크리스트 6항목(계정 발급·장비 지급·보안 교육·조직 소개·버디 배정·30일 면담) 상태가 매트릭스로 보이고 진행률을 알 수 있다 | 5 | `onboarding-plan.checklist.items; onboarding-plan.checklist.status` |
| O-F4 | 입사자마다 같은 조직 버디 후보(최대 3명, 재직기간·레벨·리스크 등급)를 본다 | 4 | `onboarding-plan.byDepartment[].buddyCandidates` |
| O-F5 | 입사 90일 코호트 목록(사번·조직·입사일·경과일·리스크 등급)과 고위험 수를 본다 | 4 | `onboarding-plan.earlyTenureCohort.members; onboarding-plan.earlyTenureCohort.count; onboarding-plan.earlyTenureCohort.highRiskCount` |
| O-F6 | 조기 이탈률(퇴사 예정 14명 중 재직 1년 미만 비율)과 조직별 분포를 본다 | 3 | `onboarding-plan.earlyAttrition.rate; onboarding-plan.earlyAttrition.under1YearLeavers; onboarding-plan.earlyAttrition.byDepartment` |
| O-F7 | 입사 예정자의 미해결 플래그(소속 변형·일자 포맷·성별 변형)가 타임라인 목록에 표시되어 입사 전 확인 대상이 된다 | 3 | `planned-joiners.clean.unresolvedFlags; onboarding-plan.timeline[].joiners` |
| O-F8 | 타임라인 입사자 합계가 정제 입사 예정자 행 수(27)와 같고, 월말 이전 합계(19)가 월말 예측의 plannedIn과 같다 | 3 | `reconciliation:onboarding-plan.timeline[].joiners=planned-joiners.clean; reconciliation:onboarding-plan.byDepartment[].joinersByMonthEnd=month-end-forecast.totals.plannedIn` |
| O-F9 | 생년월일은 어디에도 나타나지 않고, 이직 리스크는 점수 없이 등급(높음/중간/낮음)만 표시된다 | 4 | `policy:pii-minimization-policy; onboarding-plan.earlyTenureCohort.members[].riskBand; site/onboard/index.html` |
| O-F10 | 입사자별 D-7/D-3/D-0 남은 일수가 기준일 기준으로 표시되어 이번 주 할 일을 뽑을 수 있다 | 2 | `onboarding-plan.timeline[].joiners[].plannedHireDate; onboarding-plan.asOfDate` |
| O-F11 | 다음 달 입사 예정(10월 8명: Engineering 3·Data & AI 2·Sales 2·Product 1)이 조직별로 보여 IT·총무 월간 수요 예고에 쓸 수 있다 | 3 | `onboarding-plan.byDepartment[].joiners; month-end-forecast.totals.nextMonth.plannedIn` |
| O-F12 | 기준일·고객사·데이터 출처(내장/Supabase)·horizonEnd가 공통 헤더에 표시된다 | 2 | `site/onboard/index.html 공통 헤더; onboarding-plan.horizonEnd` |

## 11. 루브릭 후보 (rubric — 심판 `persona-advocate:onboarding`의 정성 렌즈, 4개 이상)

lens: "온보딩 담당 옹호자 — 입사자가 첫날 자기 자리·계정·버디를 갖고 시작하는가"

| id | item | scale |
|---|---|---|
| O-Q1 | 첫날 준비 가시성: 입사일까지 남은 항목이 누구 것인지 한눈에 보여 독촉 대상이 바로 나오는가 | 0~10 |
| O-Q2 | 묶음 계획성: Engineering처럼 몰리는 조직을 묶어 일괄 온보딩을 짤 수 있는 정보(인원·조직장·일자)가 모여 있는가 | 0~10 |
| O-Q3 | 버디 적합성: 후보의 재직기간·레벨·리스크 등급이 보여 점수 없이도 안심하고 배정할 수 있는가 | 0~10 |
| O-Q4 | 조기 이탈 선제성: 90일 코호트·조기 이탈률이 조직장 대화의 근거로 바로 쓰일 만큼 구체적인가 | 0~10 |
| O-Q5 | 주간 리듬 적합성: 월요일 아침 "이번 주·다음 주"만 보고 하루 계획을 세울 수 있는가 | 0~10 |

## 12. 이 페르소나의 PII 범위

- 성명 허용(입사자 맞이·버디 연결). 생년월일은 `ageBand`
- 이직 리스크는 버디 제외·코호트 경고에 `riskBand`만 사용. 점수와 요인은 노출하지 않는다 — 버디 후보를 고르는 데 점수는 필요 없다

## 13. 관련 수치 (문장 구체화용 — 계약 §2-3·§2-7·§11)

월말 입사 예정 19명(Engineering 5·Sales 3·Product 3·Customer Success 2·Data & AI 2·Design 1·Marketing 1·People 1·Finance 1) + 10월 8명(Engineering 3·Data & AI 2·Sales 2·Product 1) = 타임라인 27(assert).
입사 예정자 결함: 소속 변형 2·일자 포맷 3·성별 변형 1. 소리내어 검증 5: "온보딩 담당의 니즈가 조직별 배치를 요구하면 온보딩 계획이 Engineering 입사 예정 5명을 묶고 Onboarding이 체크리스트를 보여준다."
체크리스트 6항목: 계정 발급·장비 지급·보안 교육·조직 소개·버디 배정·30일 면담. 버디 후보: 같은 조직 재직자, 재직 2~6년, 리스크 낮음, 레벨 IC3~Lead, 최대 3명 (§11).
90일 코호트: 기준일 기준 입사 90일 이내 재직자(재직기간 1년 미만 54명 중 일부). 조기 이탈: 퇴사 예정 14명 중 재직 1년 미만 비율. 조직장 사번은 `byDepartment[].deptLeadEmpId`.

## 14. 웹 조사 검색어 (2~3건, 출처 URL 기록)

- "신입사원 온보딩 체크리스트 입사 전 준비 계정 장비 버디" — 체크리스트 항목·D-7 관행 확인
- "onboarding 30 60 90 day check-in early attrition" — O5·O6 관행, 벤치마크는 참고치로만
- "수습기간 3개월 평가 면담" — D+90 일정 가정 확인
