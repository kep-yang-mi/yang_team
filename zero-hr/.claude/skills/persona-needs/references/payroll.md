# 참고 프로필 — 급여 담당 (payroll → Payroll Close)

이 파일은 **후보 목록**이다. 정답이 아니다. 계약 수치(재직 406·휴직 21·총원 427, 고용유형 정규직 354·계약직 31·인턴 19·파견 23, 퇴사 예정 14 중 계약만료 3,
월말 입사 예정 19, 90일 내 계약 만료 ≥ 8명)로 문장을 구체화하고, JTBD 셀프 인터뷰 답변에 따라 항목을 고르고 버린다.
evidence·source·requiredFields는 DATA_CONTRACT **v2** §10(`payroll-close.json`: `monthEndActive`/`monthEndTotal`, `byDepartment`, `risks[].unresolvedFlag`) 경로다.

**경계:** 급여액·보상·세액·계좌는 다루지 않는다(GLOSSARY 제외 절). 이 페르소나의 니즈는 "**누가 급여 대상이고 어떤 이벤트가 있는가**"에 한정한다.
금액을 요구하는 fit 기준은 만들지 않는다 — 계약에 그 필드가 없다.

## 1. 누구인가 (profile 후보)

㈜온다테크 Operations 그룹 People 조직의 **급여 담당**(1명, 레벨 Senior). 매월 급여일(25일 가정) 전에 급여 대상 인원(재직 406 + 휴직 21 = 427)을 확정해
외부 급여 시스템에 넘긴다. 당월 입·퇴사자와 휴직자 때문에 대상이 매달 바뀌고, 지금은 마스터·입사 예정·퇴사 예정 파일 세 개를 사번으로 대조해 손으로 찾는다.
한 달의 리듬: 월초 전월 신고 → 월중 대상 확정 → 25일 지급 → 월말 다음 달 준비. 절대 틀리면 안 되는 것: **과지급·미지급**.
퇴직 처리 안 된 사람에게 급여가 나가거나 입사자가 빠지는 사고가 가장 큰 공포다. 급여 대상은 재직+휴직 전원이지만 TO 비교는 재직만 쓴다는 것을 안다.

## 2. 목표 후보 (goals)

- 월말 급여 대상 인원(재직+휴직)을 빠짐없이·중복 없이 확정하고 인사 총괄의 월말 예측(411)과 같은 숫자를 본다
- 당월 입·퇴사자(일할 계산 대상)와 휴직자 21명의 처리 구분을 급여 확정 전에 놓치지 않는다
- 90일 내 계약 만료 예정자(계약직·인턴·파견 73명 중 8명 이상)를 미리 파악해 연장/종료 시점을 놓치지 않는다
- 원천 데이터 오류(상태 불일치·중복·stale 퇴사 예정)로 인한 과지급·미지급을 급여 확정 전에 막는다
- 급여액·보상은 이 화면에서 다루지 않는다 — "누가 대상이고 어떤 이벤트가 있는가"만

## 3. JTBD 후보 (jobsToBeDone — 5개 이상 고른다)

| id | job | trigger | frequency | importance |
|---|---|---|---|---|
| P1 | 매월 급여 확정 전에 급여 대상 인원(재직+휴직)을 확정하고 전월·월말 예측과 대사한다 | 매월 20일경 | monthly | 5 |
| P2 | 당월 입사·퇴사자를 뽑아 일할 계산 대상과 근무일수·비율(근무일수/30)을 확정한다 | 매월 20일경 | monthly | 5 |
| P3 | 휴직자 21명의 급여 처리 구분(육아휴직→무급(정부 급여)/질병휴직→유급/기타→무급)을 확인한다 | 매월 16~20일 | monthly | 4 |
| P4 | 90일 내 계약 만료 예정자를 월별로 파악해 조직장·인사 총괄에 연장 여부를 확인한다 | 매월 1~5일 | monthly | 4 |
| P5 | 입·퇴사 이벤트를 4대보험 취득·상실 신고 기한에 맞춰 목록화한다 | 입·퇴사 발생 시 | event | 3 |
| P6 | 재직상태·휴직유형·계약종료일·퇴사 예정일 불일치 같은 급여 오류 위험을 급여 확정 전에 해소한다 | 매월 16~20일 | monthly | 5 |
| P7 | 고용유형·조직 그룹·조직별 급여 대상 집계(기준일·월말)를 Finance에 전달한다 | 매월 21~25일 | monthly | 3 |
| P8 | 비자발적 퇴직(계약만료 3·조직개편 2·성과/적합도 2) 예정자의 정산 일정을 준비한다 | 퇴사 예정 확정 시 | event | 3 |

연말정산(P9 후보, yearly)은 월간 리듬 밖이라 보통 버린다 — 캘린더 `연 1회(1~2월)`에만 남긴다.

## 4. 월간 캘린더 초안 (calendar)

| when | task |
|---|---|
| 매월 1~3일 | 전월 급여 대상 대사, 당월 입사 예정자·90일 내 계약 만료자 확인, 전월 퇴사자 상실 신고 준비 |
| 매월 4~10일 | 전월 입·퇴사자 4대보험 취득·상실 신고(다음 달 15일 기한) 및 원천세 신고(10일) 자료 확인 |
| 매월 11~20일 | 급여 대상 확정(휴직·복직·입퇴사 반영), 일할 계산 대상 목록 확정, 급여 오류 위험 점검·해소 |
| 매월 21~말일 | 급여 지급(25일 가정), Finance에 고용유형·조직별 집계 전달, 월말 퇴사 예정자 반영, 다음 달 계약 만료자 통보 |
| 수시 | 입사자 발생 시 건강보험 취득 신고(14일 이내), 퇴사자 발생 시 퇴직 정산 일정 확인 |
| 연 1회(1~2월) | 연말정산 대상자(중도 퇴사자 포함) 확정 |

일정(급여일 25일, 신고 기한)은 가정이다 — `assumptions`에 적고 웹 조사로 확인한다.

## 5. 핵심 질문 후보 (keyQuestions)

- 이번 달 급여 대상은 몇 명(427 → 월말 432)이고 전월·월말 예측 대비 누가 늘고 줄었나?
- 당월 입사·퇴사자는 누구이고 근무일수·일할 비율은 얼마인가?
- 휴직자 21명은 누구이고 급여 처리는 무급(정부 급여)/유급/무급 중 무엇인가?
- 90일 내 계약 만료자는 누구이고 월별로 몇 명인가?
- 재직인데 퇴사 예정일이 지났거나(stale), 마스터에 없는 사번(unknown-emp), 휴직인데 유형이 없는 사람이 있나?
- 월말 예정 입·퇴사자를 반영한 월말 급여 인원은 인사 총괄의 월말 예측 411과 같은가?
- 마감 체크리스트에서 아직 안 끝난 항목은 무엇인가?

## 6. KPI 후보 (kpis — source는 스냅샷 키 경로)

| name | definition | source |
|---|---|---|
| 급여 대상 인원(기준일) | 재직 406 + 휴직 21 = 427 (§10 `payrollHeadcount.asOfTotal`) | `payrollClose.payrollHeadcount.asOfTotal` |
| 급여 대상 재직 인원(월말) | = 월말 인원 예측 411 (§10 대사 규칙 `monthEndActive` = forecast.totals.forecastMonthEnd assert) | `payrollClose.payrollHeadcount.monthEndActive` |
| 급여 대상 총원(월말) | 월말 재직 411 + 휴직 21 = 432 (§10 `monthEndTotal`) | `payrollClose.payrollHeadcount.monthEndTotal` |
| 일할 계산 대상 수 | 당월 입사자 + 월말까지 입사 예정(19) + 월말까지 퇴사 예정(14) (§10 `prorations`) | `payrollClose.prorations.joinersInPeriod; payrollClose.prorations.plannedJoinersByMonthEnd; payrollClose.prorations.plannedLeaversByMonthEnd` |
| 휴직 처리 구분별 인원 | 무급(정부 급여)/유급/무급, 합 21 (§10 `leaves.byTreatment`) | `payrollClose.leaves.byTreatment` |
| 90일 내 계약 만료 수 | contractEndDate ≤ 기준일+90 (≥ 8명), 월별 건수 (§10 `contracts`) | `payrollClose.contracts.expiringWithin90Days; payrollClose.contracts.byMonth` |
| 급여 오류 위험 건수 | 미해결 플래그 중 급여 영향(status-inconsistency·missing-required·stale-planned-leaver·unknown-emp) (§10 `risks`) | `payrollClose.risks` |
| 마감 체크리스트 완료율 | status=done ÷ 전체 항목 (§10 `checklist`) | `payrollClose.checklist` |

## 7. 통증점 후보 (pains — 예산 12h)

| pain | costHoursPerMonth |
|---|---|
| 마스터·입사 예정·퇴사 예정 파일 취합과 사번 대사(중복 8행·상태 불일치 찾기) | 5 |
| 입퇴사자 근무일수·일할 비율·휴직 처리 구분 수기 계산 | 4 |
| 계약 만료 통보 목록과 Finance 전달용 고용유형·조직별 집계표 작성 | 3 |

합 12h(§8 40h 중 수집·통합 8h·클린징 12h의 급여 대사 몫).

## 8. 필요 필드 후보 (requiredFields — `{파일 스템}.{컬럼}`)

`headcount-master.empId` `headcount-master.name` `headcount-master.deptCode` `headcount-master.orgGroupCode` `headcount-master.employmentType`
`headcount-master.status` `headcount-master.leaveType` `headcount-master.leaveStart` `headcount-master.hireDate` `headcount-master.contractEndDate`
`headcount-master.ageBand` `headcount-master.unresolvedFlags`
`planned-joiners.joinerId` `planned-joiners.name` `planned-joiners.deptCode` `planned-joiners.employmentType` `planned-joiners.plannedHireDate` `planned-joiners.unresolvedFlags`
`planned-leavers.empId` `planned-leavers.deptCode` `planned-leavers.plannedTerminationDate` `planned-leavers.separationType` `planned-leavers.separationReason` `planned-leavers.unresolvedFlags`
`month-end-forecast.totals.forecastMonthEnd` `headcount-stats.totals.headcount` `cleansing-summary.unresolvedItems`

성명은 업무상 필요(급여 시스템 대조)하므로 허용. 생년월일은 요구하지 않는다(`ageBand`). 퇴사일 컬럼은 마스터에 없다 — 퇴사 예정은 `planned-leavers`에서만 온다.

## 9. 결정 후보 (decisions)

급여 대상 인원 확정 승인 · 일할 계산 대상·근무일수 확정 · 휴직 처리 구분 확정 · 계약 만료 연장 여부 확인 요청(조직장·인사 총괄) · 오류 위험 항목 보류/확인 요청 ·
Finance 전달 집계 승인 · 4대보험 취득·상실 신고 대상 확정

## 10. fit 기준 후보 (fitCriteria — 8개 이상 고른다, weight 5는 1/3 이하)

| id | criterion | weight | evidence |
|---|---|---|---|
| P-F1 | 월말 급여 대상 재직 인원이 월말 인원 예측(411)과 대사 규칙대로 일치하고, 월말 총원(432)은 휴직 21을 더한 값으로 별도 표시된다 | 5 | `reconciliation:payroll-close.payrollHeadcount.monthEndActive=month-end-forecast.totals.forecastMonthEnd; payroll-close.payrollHeadcount.monthEndTotal` |
| P-F2 | 당월 입사자(일할 계산 대상)를 성명·조직·입사일·고용유형·근무일수·일할 비율(근무일수/30, 3자리)과 함께 목록으로 본다 | 5 | `payroll-close.prorations.joinersInPeriod` |
| P-F3 | 월말까지 입사 예정(19)·퇴사 예정(14)이 확정 입사자와 구분된 목록으로 근무일수·비율과 함께 보인다 | 4 | `payroll-close.prorations.plannedJoinersByMonthEnd; payroll-close.prorations.plannedLeaversByMonthEnd` |
| P-F4 | 휴직자 21명 목록(성명·조직·휴직유형·시작일)과 급여 처리 구분(무급(정부 급여)/유급/무급) 집계를 본다 | 4 | `payroll-close.leaves.onLeave; payroll-close.leaves.byTreatment` |
| P-F5 | 90일 내 계약 만료 예정자(계약직·인턴·파견) 목록과 월별(2026-10/11/12) 건수를 본다 | 4 | `payroll-close.contracts.expiringWithin90Days; payroll-close.contracts.byMonth` |
| P-F6 | 급여 오류 위험이 사번·이슈·영향·미해결 플래그(status-inconsistency·missing-required·stale-planned-leaver·unknown-emp)와 함께 표시되고 급여 확정 전 확인 대상으로 구분된다 | 5 | `payroll-close.risks[].unresolvedFlag; payroll-close.risks[].impact; planned-leavers.clean.unresolvedFlags; headcount-master.clean.unresolvedFlags` |
| P-F7 | 고용유형(정규직 354·계약직 31·인턴 19·파견 23)·조직별 급여 대상 집계를 기준일과 월말 기준으로 본다 | 3 | `payroll-close.payrollHeadcount.byEmploymentType; payroll-close.payrollHeadcount.byDepartment` |
| P-F8 | 마감 체크리스트가 항목·건수·상태(done/pending)로 표시되고 완료율을 알 수 있다 | 3 | `payroll-close.checklist` |
| P-F9 | 급여액·세액·수당·계좌는 어디에도 나타나지 않고(스키마에 금액 필드 없음), 성명은 표시되되 생년월일 대신 연령대만 보인다 | 4 | `policy:pii-minimization-policy; payroll-close.payrollHeadcount; site/payroll/index.html` |
| P-F10 | 급여 기간(payPeriod 2026-09, periodStart~periodEnd)과 기준일이 공통 헤더에 표시된다 | 2 | `payroll-close.payPeriod; payroll-close.periodStart; payroll-close.periodEnd; site/payroll/index.html 공통 헤더` |
| P-F11 | 미해결 항목 건수가 Insight의 클린징 요약과 같은 수치다 | 2 | `reconciliation:site/data/payroll.json.cleansingSummary.unresolvedCount=cleansing-summary.unresolvedCount` |
| P-F12 | 퇴사 예정자가 퇴직 구분(자발/비자발)과 사유(계약만료 3·조직개편 2·성과/적합도 2 등)로 구분되어 정산 준비 목록으로 보인다 | 3 | `payroll-close.prorations.plannedLeaversByMonthEnd[].separationType; planned-leavers.clean.separationReason` |
| P-F13 | 기준일 급여 대상 총원(427)이 인원 통계의 총원과 같은 값이다 | 3 | `reconciliation:payroll-close.payrollHeadcount.asOfTotal=headcount-stats.totals.headcount` |

## 11. 루브릭 후보 (rubric — 심판 `persona-advocate:payroll`의 정성 렌즈, 4개 이상)

lens: "급여 담당 옹호자 — 25일에 과지급·미지급 0건으로 급여 대상을 넘길 수 있는가"

| id | item | scale |
|---|---|---|
| P-Q1 | 누락·중복 방어: 입사자 누락·퇴직자 잔존을 화면이 먼저 잡아주는가(오류 위험이 눈에 띄는 위치에 있는가) | 0~10 |
| P-Q2 | 대사 신뢰: 월말 인원이 인사 총괄 숫자(411)와 같음이 화면에서 확인되어 Finance에 그대로 넘길 수 있는가 | 0~10 |
| P-Q3 | 이벤트 완결성: 입사·퇴사·휴직·계약 만료 네 이벤트가 한 곳에서 일자·처리 구분과 함께 보이는가 | 0~10 |
| P-Q4 | 경계 준수: 급여액을 요구하지 않고도 마감 업무가 끝나는가(금액 필드 부재가 결함으로 느껴지지 않는가) | 0~10 |
| P-Q5 | 체크리스트 실행성: 남은 항목이 무엇이고 누구에게 확인해야 하는지 바로 행동으로 옮길 수 있는가 | 0~10 |

## 12. 이 페르소나의 PII 범위

- 성명 허용(급여 시스템 대조에 필수). 생년월일은 `ageBand`. 이직 리스크 점수·등급은 이 제품에 없다(급여 업무와 무관)
- 급여액·세액·수당·계좌는 계약에 없고 다루지 않는다. 브리프 §9: 보상/민감정보는 별도 권한

## 13. 관련 수치 (문장 구체화용 — 계약 §2-7·§10)

급여 대상(기준일) = 재직 406 + 휴직 21 = 427 (`asOfTotal`). 월말 재직 411(`monthEndActive` = 예측 assert) + 휴직 21 = 432(`monthEndTotal`).
월말 입사 예정 19, 퇴사 예정 14(자발퇴사 5·계약만료 3·조직개편 2·성과/적합도 2·개인사유 2). 미해결 플래그: stale-planned-leaver 1·unknown-emp 1·status-inconsistency 3·missing-required 3.
고용유형(총원): 정규직 354·계약직 31·인턴 19·파견 23 → 계약 만료 후보군 73명, 90일 내 만료 ≥ 8명. 휴직자 고용유형 정규직 19·계약직 2.
일할 비율 = 근무일수/30, 소수 3자리. 휴직 처리: 육아휴직→무급(정부 급여), 질병휴직→유급(회사 규정 가정), 기타→무급 (§10).

## 14. 웹 조사 검색어 (2~3건, 출처 URL 기록)

- "4대보험 취득신고 상실신고 기한 14일 15일" — P5 trigger 확인(출처마다 상실 기한 서술이 갈리면 둘 다 `assumptions`에 적는다)
- "급여 마감 체크리스트 입사자 퇴사자 일할계산 휴직자" — P2·P3·체크리스트 항목 관행
- "육아휴직 급여 고용보험 회사 무급" — 휴직 처리 구분 가정 확인
