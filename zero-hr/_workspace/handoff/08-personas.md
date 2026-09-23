# 08-personas — persona-needs-analyst — 2026-09-23

## 시도한 것
- 페르소나 3종(head-of-hr→insight / payroll→payroll / onboarding→onboard)의 §9 객체를 JTBD 셀프 인터뷰(스킬 A2) 방식으로 도출하고 `shared`(commonNeeds 7 / conflicts 5 / dataLayerImplications 8)까지 종합해 `personas/persona-needs.json`을 한 번에 작성(persona+synthesis 통합 실행).
- 참고 프로필(`references/*.md`)의 후보 목록에서 선택·구체화·폐기: H9(연 1회 TO 계획)·P9(연말정산) JTBD는 월간 리듬 밖이라 폐기, O-F4(newTeamOnboarding, v1 시나리오)는 v2 계약에 없어 폐기하고 `byDepartment[].deptLeadEmpId`로 대체. 모든 evidence·source·requiredFields를 v2 경로(byOrgGroup/byDepartment/level/Seed~Enterprise, monthEndActive/monthEndTotal, toGapAsOf)로 작성.
- §9 확장 필드 추가(의도된 확장): 페르소나별 `rubric{lens, qualitative[≥4, 0~10]}`(product-judge 옹호자 렌즈), `assumptions[]`, `sources[]`(웹 조사 URL). 출처는 `_workspace/persona-needs-sources.json`에도 복제.
- 웹 조사 3건(4대보험 취득·상실 기한 / 30-60-90 체크인·조기 이탈 / 경영진 headcount 대시보드 관행) 수행, 각 페르소나 `sources`에 URL·usedFor 기록.

## 본 데이터·근거
- `.claude/agents/persona-needs-analyst.md`, `.claude/skills/persona-needs/SKILL.md` + `references/{head-of-hr,payroll,onboarding}.md`
- `.claude/GLOSSARY.md`(v2 — 페르소나·제품·리포트 뷰·급여 마감·온보딩 계획·심판·루브릭 행, 소리내어 검증 2~5, 정책 표)
- `.claude/DATA_CONTRACT.md` v2 §2-7(정본 수치: 재직 406·휴직 21·TO 422·입사 19·퇴사 14·월말 411·gap −16/−11, 조직별 표, 퇴사 사유 5/3/2/2/2), §3(정제 컬럼), §4-1~4-4(stats/forecast/attrition/automation 경로), §5(뷰 4종·PII), §6(dispatch.json), §8(수작업 40h = 8/12/12/8), §9(스키마), §10(payroll-close: monthEndActive=411 assert, monthEndTotal 432), §11(onboarding-plan: timeline 27 assert, deptLeadEmpId, earlyAttrition), §15~§16(통합 제품·진화 루프 — rubric 필드 근거)
- `zero-company/zero_company_external_brief.md` §6~§10(Executive Snapshot, 권한별 대시보드 보이는 것/숨기는 것, 월초 이메일 제목)
- 웹: help.mobiletax.kr/insurance/11, shoplworks.com(4대보험 가이드), peoplehum.com(30-60-90 playbook), ks-agents.com(30/60/90 guide, 90일 이탈 <10%), drivetrain.ai(headcount dashboard), agile-hr-analytics.com(CHRO KPI)
- JTBD 셀프 인터뷰 요약: H — 가장 바쁜 날은 월초 경영회의, 실패 비용은 "경영진 앞 정정", 금기는 경영진·조직장 뷰의 개인명 / P — 가장 바쁜 날은 20일경 대상 확정, 실패 비용은 과지급·미지급, 금기는 급여액 표시·퇴직자 잔존 / O — 가장 바쁜 날은 월요일 2주 점검과 D-7, 실패 비용은 "첫날 자리 없음", 금기는 리스크 점수·생년월일 노출.

## 실패한 것
- 상류 산출물(`data/stats/*.json`, `data/clean/*`)이 아직 디스크에 없어 실제 값(휴직 처리 구분별 인원, 90일 코호트 수, 계약 만료 정확 수)으로 문장을 더 구체화하지 못함 — 계약 정본 수치와 "≥8명" 같은 계약 하한만 사용.
- 4대보험 **상실** 신고 기한은 출처 간 서술이 갈림(건강·고용·산재 14일 이내 vs 전부 다음 달 15일). 캘린더에 둘을 모두 반영하고 payroll `assumptions`에 기록. 고객사 규정 확인 필요.
- v1 계약 전용 시나리오(newTeamOnboarding/AI에이전트팀, separations.ytd, 기준일 gap 필드 부재)는 v2에서 사라졌거나 해소되어 contractGaps 없음. 단, §9 스키마에 `rubric`/`assumptions`/`sources` 필드가 없어 이 파일은 §9의 상위집합이다 — people-data-auditor가 "계약에 없는 키" 검사를 한다면 허용 목록에 세 키를 추가해야 한다(contractGap 1건).

## 검증된 것
- `python3 -c "import json;json.load(open('personas/persona-needs.json'))"` 통과(UTF-8, ensure_ascii 없음, 들여쓰기 2).
- 카운트: head-of-hr JTBD 8 / fit 14 / weight5 비율 0.21 / pains 16h / KPI 11 · payroll JTBD 8 / fit 13 / 0.23 / 12h / KPI 8 · onboarding JTBD 8 / fit 12 / 0.25 / 12h / KPI 6. pains 합 **40h** = `automation-effect.manualBaseline.hoursPerMonth`.
- 모든 weight 1~5, id 중복 없음, requiredFields에 `birthDate` 없음, evidence·source에 v1 토큰(byDivision/byTeam/position/S1/newTeamOnboarding) 없음.
- evidence·KPI source의 파일 스템·말단 토큰이 DATA_CONTRACT.md v2 본문에 모두 존재함을 스크립트로 확인(policy:/site//reports/ 접두어 제외).
- 필수 기준 포함 확인 — H: 뷰 4종(H-F2), 조직별 TO gap 한 화면(H-F1), 월말 예측+권고(H-F4), 리스크 요약 등급만(H-F5), 데이터 품질(H-F7), 리포트 발송 준비(H-F8), 자동화 효과(H-F9), PII(H-F3) / P: 대사 monthEndActive=forecast(P-F1), 일할 실제+예정(P-F2·F3), 휴직 처리(P-F4), 계약 만료 90d(P-F5), 오류 위험+플래그(P-F6), 체크리스트(P-F8), 금액 없음·성명 허용(P-F9) / O: 주차 타임라인 이번·다음 주(O-F1), 조직 배치+조직장(O-F2), 체크리스트 매트릭스(O-F3), 버디(O-F4), 90일 코호트 등급(O-F5), 조기 이탈률(O-F6), 입사자 미해결 플래그(O-F7), 생년월일 없음(O-F9).
- `shared.conflicts`에 성명 vs 익명(P,O↔H), 재직 기준 TO vs 재직+휴직 급여(P↔H) 포함.

## 다음 agent 인계점
- **product-builder**: `fitCriteria[].criterion`이 화면 요구, `evidence`가 데이터 위치. Insight는 역할 선택기 4종(executive/hr/planning/orgLead)과 H-F3·H-F5·H-F13의 PII 규칙을 마크업 수준에서 지켜야 함. Payroll Close는 monthEndActive(411)와 monthEndTotal(432)을 구분 표기(P-F1, conflicts 2번). Onboarding은 타임라인 합계 27과 월말 19를 함께 표기(O-F8, conflicts 5번).
- **product-judge(persona-advocate ×3)**: `fitCriteria` id·weight로 coverage/weightedCoverage, `rubric.qualitative`(H-Q1~5 / P-Q1~5 / O-Q1~5, 0~10)로 panelScore. `reconciliation:` evidence는 두 경로의 값이 같은지로 판정.
- **payroll-close-analyst / onboarding-plan-analyst**: `requiredFields`·`evidence`가 §10·§11 경로를 가리킴. 특히 `payroll-close.risks[].unresolvedFlag`에 stale-planned-leaver·unknown-emp·status-inconsistency·missing-required 4종, `onboarding-plan.byDepartment[].deptLeadEmpId`, `earlyTenureCohort.members[].riskBand`가 채워져야 O-F5·P-F6 채점 가능. 미충족은 `provenance.gaps.criterionId`로 되돌려 주면 evidence를 고침.
- **people-data-auditor**: §9 최소 요건 검사 시 확장 키 `rubric`/`assumptions`/`sources` 3개를 허용 목록에 추가(contractGap). 그 외 §9 준수.
- **monthly-report-mailer**: H-F8은 `reports/monthly-report-dispatch.json.status=ready-to-send`와 `gate` 표기를 요구.
- 출처·가정 사본: `_workspace/persona-needs-sources.json`.
