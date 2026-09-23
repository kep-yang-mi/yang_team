# 참고 프로필 — 인사 총괄 (head-of-hr → Insight)

이 파일은 **후보 목록**이다. 정답이 아니다. persona-needs-analyst는 여기서 출발해 브리프·계약 수치로 문장을 구체화하고,
JTBD 셀프 인터뷰 답변에 따라 항목을 고르고 버린다. 그대로 복사하면 세 페르소나가 같은 톤이 되어 fit 비교가 무의미해진다.
evidence·source·requiredFields는 DATA_CONTRACT **v2**(조직 그룹 `byOrgGroup` > 조직 `byDepartment`, `deptCode`, `level`, 스테이지 Seed~Enterprise, 뷰 4종) 경로다.

## 1. 누구인가 (profile 후보)

㈜온다테크(영문 조직명을 쓰는 IT 스타트업, 재직 406·휴직 21·총원 427) Operations 그룹 **People 조직(재직 18명)의 Director 겸 인사 총괄**.
급여 담당·온보딩 담당을 포함한 People 조직을 이끌고 CEO와 경영기획에 보고한다. 매월 초 경영회의에서 "전월 결산 + 당월 전망"(재직 406 · 월말 예측 411 · 월말 TO 대비 −11)을
발표하고, 수시로 "지금 몇 명이냐"는 질문을 받는다. 한 달의 리듬: 월초 보고 → 월중 조치(채용 가속·면담) → 월말 예측 점검. 절대 틀리면 안 되는 것:
**경영진 앞에서 숫자를 정정하는 일**. 경영진·HR·경영기획·조직장 네 독자에게 각각 다른 권한의 뷰를 배포하는 유일한 페르소나다.

## 2. 목표 후보 (goals)

- 매월 초 경영진에게 재직 인원·월말 예측·TO 과부족을 정정 없이 한 번에 보고한다
- 조직별 권고(Engineering −7·Sales −4 채용 가속, Data & AI +7 TO 재검토·이동배치)를 숫자 근거와 함께 상신한다 — 결정은 승인 gate(사람)
- 이직 리스크 높음 재직자를 조직장보다 먼저 파악해 선제 대응한다
- 권한별 뷰 4종(경영진/HR/경영기획/조직장)을 배포하되 같은 지표는 어느 뷰에서도 같은 값이 되게 한다
- 리포트 수작업을 없애고 원천 데이터의 미해결 항목을 건수·질문으로 관리한다

## 3. JTBD 후보 (jobsToBeDone — 5개 이상 고른다)

| id | job | trigger | frequency | importance |
|---|---|---|---|---|
| H1 | 매월 초 경영진에게 전월 결산과 당월 전망(재직 406·월말 예측 411·TO 대비 −16→−11)을 보고한다 | 월초 | monthly | 5 |
| H2 | 경영진·경영기획이 묻기 전에 조직 그룹·조직별 TO 과부족을 기준일과 월말 기준으로 파악해 둔다 | 수시 | weekly | 5 |
| H3 | 조직별 권고(채용 가속/TO 재검토·이동배치)와 즉시 액션 3건을 근거와 함께 상신한다 | 권고 발생 시 | monthly | 4 |
| H4 | 이직 리스크 높음 재직자를 조직별로 파악하고 조직장과 면담 계획을 세운다 | 월중 | monthly | 4 |
| H5 | 퇴사 예정 14명의 퇴직사유·퇴직 구분(자발/비자발)과 소규모 조직 영향(Legal & Compliance 월말 −2)을 점검한다 | 월말 | monthly | 3 |
| H6 | 경영진·HR·경영기획·조직장에 권한별 뷰를 배포하되 경영진·경영기획·조직장에는 익명 집계만 보인다 | 월초 | monthly | 5 |
| H7 | 원천 데이터의 미해결 항목을 건수·확인 질문으로 파악해 담당자에게 회신을 요청한다 | 월말 | monthly | 3 |
| H8 | 경영기획의 what-if(채용 달성률·추가 이탈)를 리스크 반영 시나리오로 검토해 다음 달 말 전망을 조정한다 | 월중 | monthly | 2 |

연 1회 TO 계획 수립(H9 후보)은 월간 리듬 밖이고 계약에 추이 데이터가 없어 보통 버린다.

## 4. 월간 캘린더 초안 (calendar)

| when | task |
|---|---|
| 매월 1~3일 | 월초 리포트 발송(매월 1일 09:00, 제목 `[Zero Company] 2026-09 HR Headcount Forecast`) 승인 후 경영회의 보고 |
| 매월 4~10일 | 미해결 항목 회신 취합, 권고(채용 가속/TO 재검토)에 따른 조치를 조직장·경영기획과 협의해 상신 |
| 매월 11~20일 | 이직 리스크 높음 인원 면담 계획, 조직장 미팅, 경영기획 시나리오 검토 |
| 매월 21~말일 | 월말 예측 점검(입사 예정 19·퇴사 예정 14 확정), 다음 달 전망 초안, 다음 리포트 수신자 확인 |
| 수시 | 경영진 질의 대응("지금 재직 인원은?", "Engineering 몇 명 부족?") |
| 분기 초 | 조직 건강 지표(휴직 21·퇴직 구분·속성 분포) 리뷰 |

## 5. 핵심 질문 후보 (keyQuestions)

- 지금 재직 인원은 몇 명이고 TO 422 대비 어느 조직이 비었나? (기준일 −16)
- 월말과 다음 달 말에 조직별 인원은 몇 명이 되고 TO 대비 얼마인가? (월말 411·−11, 다음 달 415·−7)
- 어느 조직에 채용 가속·TO 재검토·이동배치가 필요하고 즉시 액션은 무엇인가?
- 퇴사 예정 14명의 사유·구분은 무엇이고 어느 조직에 영향이 큰가?
- 이직 리스크 높음 인원은 몇 명이고 어느 조직에 몰려 있나?
- 원천 데이터에 아직 확인 안 된 항목은 몇 건이고 누가 답해야 하나?
- 이번 달 리포트는 발송 준비가 됐고, 사람 손은 얼마나 줄었나?

## 6. KPI 후보 (kpis — source는 스냅샷 키 경로)

| name | definition | source |
|---|---|---|
| 재직 인원 | status=재직, TO 비교·예측의 기준 (406, §4-1 `totals.activeHeadcount`) | `stats.totals.activeHeadcount` |
| 총원 | 재직 + 휴직 = 427 (§4-1 `totals.headcount`) | `stats.totals.headcount` |
| 휴직 인원 | status=휴직 (21) | `stats.totals.onLeave` |
| TO 과부족(기준일) | 재직 − TO = −16 (§4-2 `totals.toGapAsOf`) | `forecast.totals.toGapAsOf` |
| 월말 예측 인원 | 재직 + 월말까지 입사 예정 − 퇴사 예정 = 411 (§4-2) | `forecast.totals.forecastMonthEnd` |
| TO 과부족(월말) | 월말 예측 − TO = −11 | `forecast.totals.toGapMonthEnd` |
| TO 충족률 | 월말 예측 ÷ TO = 0.9739 (§4-2 4자리) | `forecast.totals.toFillRate` |
| 다음 달 말 예측 인원 | 411 + 10월 입사 8 − 10월 퇴사 4 = 415 (§4-2 `totals.nextMonth`) | `forecast.totals.nextMonth.forecastNextMonthEnd` |
| 이직 리스크 높음 인원 | riskBand=높음 재직자 수 (§4-3 `summary`, 밴드 8~15%) | `attrition.summary.높음` |
| 미해결 항목 수 | 규칙으로 보정 못한 행 수 (§3-6 `unresolvedCount`) | `cleansingSummary.unresolvedCount` |
| 리포트 자동화 절감률 | 수작업 40h 대비 0.8 (§8, 추정 표기 필수) | `automationEffect.savingRate` |

## 7. 통증점 후보 (pains — 예산 16h)

| pain | costHoursPerMonth |
|---|---|
| 조직별 엑셀 취합(마스터·TO·입퇴사 예정 4종)과 버전 맞추기 | 2 |
| 조직명 변형(Legal and Compliance 등 17건)·상태·레벨 표기 정리와 중복 제거 | 2 |
| 조직별 집계·TO 비교·월말 예측·권고 수기 계산과 재검산 | 6 |
| 리포트 작성, 권한별(경영진/HR/경영기획/조직장) 4버전 분리, 배포 | 6 |

합 16h. 항목을 바꿔도 합은 16이다(§8 40h 중 집계·예측 12h의 절반 + 리포트 작성·배포 8h 대부분 + 취합·클린징 몫).

## 8. 필요 필드 후보 (requiredFields — `{파일 스템}.{컬럼}`)

`headcount-master.empId` `headcount-master.status` `headcount-master.leaveType` `headcount-master.deptCode` `headcount-master.orgGroupCode`
`headcount-master.employmentType` `headcount-master.gender` `headcount-master.ageBand` `headcount-master.jobFamily` `headcount-master.level` `headcount-master.stage`
`headcount-master.tenureBand` `headcount-master.totalExperienceBand` `headcount-master.unresolvedFlags` `headcount-master.name`(HR 뷰 조인 전용)
`to-plan.toHeadcount` `to-plan.effectiveMonth` `planned-joiners.plannedHireDate` `planned-joiners.deptCode`
`planned-leavers.plannedTerminationDate` `planned-leavers.deptCode` `planned-leavers.separationType` `planned-leavers.separationReason`
`org-chart.orgGroupCode` `org-chart.deptCode`
`attrition-risk.byEmployee.riskBand` `attrition-risk.byDepartment` `attrition-risk.summary` `cleansing-summary.unresolvedItems` `automation-effect.savingRate`

생년월일(`birthDate`)은 요구하지 않는다 — `ageBand`로 충분하다.

## 9. 결정 후보 (decisions)

채용 가속/보류 상신(Engineering·Sales) · TO 재배분·이동배치 건의(Data & AI) · 퇴사 영향 점검 지시(Legal & Compliance) · 이직 리스크 면담 대상·우선순위 선정 ·
미해결 항목 확인 요청 발신 · 월초 리포트 발송 승인 요청(승인 gate) · 권한별 뷰 수신자 지정

## 10. fit 기준 후보 (fitCriteria — 8개 이상 고른다, weight 5는 1/3 이하)

| id | criterion | weight | evidence |
|---|---|---|---|
| H-F1 | 조직 그룹(4)·조직(11)별 TO 과부족을 기준일(−16)과 월말(−11) 기준으로 한 화면에서 본다 | 5 | `month-end-forecast.byDepartment[].toGapAsOf; month-end-forecast.byDepartment[].toGapMonthEnd; month-end-forecast.byOrgGroup[].toGapMonthEnd` |
| H-F2 | 권한별 뷰 4종(executive/hr/planning/orgLead)을 역할 선택기로 전환하며 같은 지표(재직 406·월말 411·gap −11)는 어느 뷰에서도 같은 값이다 | 5 | `site/insight/index.html executive; site/insight/index.html hr; site/insight/index.html planning; site/insight/index.html orgLead; reconciliation:site/data/insight.json.forecast.totals=month-end-forecast.totals` |
| H-F3 | 경영진·경영기획·조직장 뷰에는 성명·생년월일·개인 리스크 점수가 나타나지 않고 조직 단위 집계와 사번만 보인다 | 5 | `policy:pii-minimization-policy; site/insight/index.html executive; site/insight/index.html planning` |
| H-F4 | 조직별 월말 예측과 권고(정상 관리/채용 가속/TO 재검토·이동배치)가 인사이트 3건의 detail·action과 함께 표시된다 | 4 | `month-end-forecast.byDepartment[].forecastMonthEnd; month-end-forecast.byDepartment[].recommendation; month-end-forecast.insights[]; month-end-forecast.immediateActions` |
| H-F5 | 이직 리스크 요약이 경영진 뷰에는 등급(높음/중간/낮음) 건수와 조직별 분포만, 점수 없이 표시된다 | 4 | `attrition-risk.summary; attrition-risk.byDepartment; site/insight/index.html executive; policy:pii-minimization-policy` |
| H-F6 | HR 뷰에서만 이직 리스크 높음 인원 목록을 성명 조인으로 조직별·요인과 함께 본다 | 4 | `attrition-risk.byEmployee[].riskBand; attrition-risk.byEmployee[].topFactors; headcount-master.clean.name; site/insight/index.html hr` |
| H-F7 | 미해결 항목 건수와 확인 질문 목록, 브리프 불일치(조직 그룹 합 215/119/62 vs 220/128/48) 기록을 데이터 품질 절에서 본다 | 3 | `cleansing-summary.unresolvedItems; cleansing-summary.unresolvedCount; headcount-stats.dataQuality.briefDiscrepancies` |
| H-F8 | 월초 리포트가 같은 통계로 생성되어 status=ready-to-send이고 제목·발송 일정·권한별 수신자·승인 gate가 표기된다 | 3 | `reports/monthly-report-dispatch.json.status; policy:approval-gate-policy` |
| H-F9 | 자동화 효과(수작업 40h vs 자동화 후 검토 8h, 절감률 0.8)가 "추정" 표기와 함께 보인다 | 2 | `automation-effect.savingRate; automation-effect.manualBaseline; automation-effect.note` |
| H-F10 | 속성별 통계(고용유형·성별·연령대·직군·레벨·재직기간·총경력·스테이지, 재직 406 기준)와 조직×레벨 등 크로스탭을 본다 | 3 | `headcount-stats.byAttribute.level; headcount-stats.byAttribute.tenureBand; headcount-stats.byAttribute.stage; headcount-stats.crossTabs.departmentByLevel` |
| H-F11 | 퇴사 예정 14명의 퇴직사유(자발퇴사 5·계약만료 3·조직개편 2·성과/적합도 2·개인사유 2)와 퇴직 구분 집계를 조직별 영향과 함께 본다 | 3 | `headcount-stats.plannedSeparations.bySeparationReason; headcount-stats.plannedSeparations.bySeparationType; headcount-stats.plannedSeparations.byDepartment` |
| H-F12 | 경영기획 뷰에서 다음 달 말 전망(415·−7)과 리스크 반영 시나리오, 채용 달성률·추가 이탈을 바꾸는 시나리오 플래너를 조직별로 본다 | 3 | `month-end-forecast.byDepartment[].nextMonth; month-end-forecast.byDepartment[].riskAdjusted; month-end-forecast.scenario; site/insight/index.html planning` |
| H-F13 | 조직장 뷰는 조직을 선택하면 본인 조직의 현재/예측 인원과 입퇴사 예정 요약만 보이고 타 조직 상세는 숨긴다 | 4 | `site/insight/index.html orgLead; month-end-forecast.byDepartment; policy:pii-minimization-policy` |
| H-F14 | 기준일 2026-09-23·고객사·데이터 출처(내장/Supabase)가 공통 헤더에 표시된다 | 2 | `site/insight/index.html 공통 헤더; headcount-stats.asOfDate` |

## 11. 루브릭 후보 (rubric — 심판 `persona-advocate:head-of-hr`의 정성 렌즈, 4개 이상)

lens: "인사 총괄 옹호자 — 경영진 앞에서 숫자를 정정하지 않고 보고할 수 있는가"

| id | item | scale |
|---|---|---|
| H-Q1 | 숫자 일관성: 4개 뷰와 월초 리포트에서 재직·월말 예측·gap이 한 번도 어긋나지 않는가 | 0~10 |
| H-Q2 | 권고의 설득력: 채용 가속·TO 재검토 권고가 근거 수치와 즉시 액션까지 이어져 그대로 상신 가능한가 | 0~10 |
| H-Q3 | 익명성 자신감: 경영진·조직장 뷰를 링크로 그대로 보내도 개인 식별 걱정이 없는가 | 0~10 |
| H-Q4 | 30초 응답: 첫 화면만으로 "지금 몇 명? 어디가 비었나?"에 즉답할 수 있는가 | 0~10 |
| H-Q5 | 데이터 품질 투명성: 미해결·불일치를 숨기지 않고 무엇을 확인해야 하는지 보이는가 | 0~10 |

## 12. 이 페르소나의 PII 범위 (브리프 §9 · 계약 §5)

- 경영진 뷰: 총원·TO 과부족·조직별 월말 예측·리스크 요약. 개인명·상세 퇴직자 리스트 없음
- 경영기획 뷰: TO·조직별 현재/예측·증감 원인·시나리오 플래너. 개인 식별정보 없음(입퇴사 예정은 사번/joinerId만)
- 조직장 뷰: 본인 조직의 현재/예측·입퇴사 예정 요약. 타 조직 상세 없음
- HR 뷰: 개인 단위 마스터·클린징 오류·입퇴사 예정자·퇴직사유·리스크 개인 목록. 성명 허용, 생년월일은 연령대로. 보상·민감정보는 별도 권한
- 월초 리포트: 집계·사번만

## 13. 관련 수치 (문장 구체화용 — 계약 §2-7)

재직 406 / 휴직 21 / 총원 427 / TO 422 / 기준일 gap −16 / 월말 입사 예정 19 / 퇴사 예정 14 / 월말 예측 411 / 월말 gap −11 / 다음 달 말 415·−7.
조직 그룹 재직(조직표 합): Executive 10 · Build 220 · Go-To-Market 128 · Operations 48 — 브리프 §7의 215/119/62와 불일치, 조직표가 정본이며 `dataQuality.briefDiscrepancies`에 기록된다.
권고: Engineering −7·Sales −4 채용 가속 / Data & AI +7 TO 재검토·이동배치 / Legal & Compliance −2 퇴사 영향 점검.
퇴사 예정 사유: 자발퇴사 5·계약만료 3·조직개편 2·성과/적합도 2·개인사유 2. 클린징: 조직명 17건·입사일 31건 보정.

## 14. 웹 조사 검색어 (2~3건, 출처 URL 기록)

- "headcount reporting dashboard executive monthly" — H1 경영진 보고 항목(총원·입퇴사·자발/비자발·리스크 요약) 관행
- "CHRO HR dashboard KPIs headcount attrition" — H2·H4 KPI 구성
- "TO fill rate headcount plan definition" — TO 충족률 정의가 §4-2 `toFillRate`와 같은지
