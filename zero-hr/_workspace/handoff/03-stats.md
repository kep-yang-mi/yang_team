# 03-stats — headcount-statistician — 2026-09-23

## 시도한 것

- 시작 2026-09-23T17:10:52 / 종료 2026-09-23T17:10:52 — `python3 .claude/skills/headcount-stats/scripts/compute_stats.py --root /Users/yang/development/zero-hr --as-of 2026-09-23`
- 상태: **ok**
- 정제 마스터 → totals·byOrgGroup·byDepartment·byAttribute(재직)·byAttributeAll(총원)·crossTabs 7종·experience 집계, TO·입퇴사 예정에서 toHeadcount·plannedIn·plannedOut·plannedSeparations 집계 (§4-1·§4-5)
- 대사(딕셔너리 합 assert) 통과 시에만 `data/stats/headcount-stats.json` 작성, §2-7 정본 대조는 stdout targetCheck 로만 보고

## 본 데이터·근거

- 계약: `.claude/DATA_CONTRACT.md` §2-7(정본 수치)·§2-8(stale/unknown-emp)·§3(정제 컬럼)·§4-1(shape)·§4-5(합계 규칙)
- 입력 행수: {"headcountMaster": 427, "toPlan": 11, "plannedJoiners": 27, "plannedLeavers": 19}
- 입력 존재: {"orgChart": true, "companyStages": true, "toPlan": true, "plannedJoiners": true, "plannedLeavers": true}
- 월말 2026-09-30 · 퇴사 예정 제외/특기: {"unknownEmp": ["E9999"], "notActive": [], "badDate": [], "stale": ["E0251"]}
- totals: {"headcount": 427, "activeHeadcount": 406, "onLeave": 21, "toHeadcount": 422, "toGapAsOf": -16, "plannedIn": 19, "plannedOut": 14, "unresolvedCount": 10}
- byOrgGroup(재직): Executive 10, Build 220, Go-To-Market 128, Operations 48

## 실패한 것

- 경고: 마스터에 없는 퇴사 예정 사번 1건 제외(unknown-emp): E9999
- 경고: 예정일이 기준일 이전인 퇴사 예정(stale) 1건 — 월말 퇴사로 반영(§2-8): E0251

## 검증된 것

- 내부 대사 66항목 통과 (byAttribute 8종 합=재직, byAttributeAll 합=총원/휴직, crossTabs 7종 셀 합=재직, Σ byDepartment = Σ byOrgGroup = totals, plannedSeparations 합=plannedOut)
- §2-7 정본 대조 93항목 전부 일치 — 속성 분포 8종: employmentType 일치, gender 일치, ageBand 일치, jobFamily 일치, level 일치, tenureBand 일치, totalExperienceBand 일치, stage 일치
- 산출물 `data/stats/headcount-stats.json` (UTF-8, §4-1 키 전부, 계약 외 필드 없음)

## 다음 agent 인계점

- `headcount-forecaster`(04): `byDepartment[].activeHeadcount`(출발점)·`toHeadcount`·`toGapAsOf`, `totals.plannedIn/plannedOut`(§4-5 정의) — forecast.totals 와 같아야 함
- `attrition-risk-scorer`(05, 병렬): `totals.activeHeadcount` 로 점수화 대상 수 대사
- `payroll-close-analyst`(06): `byAttributeAll.employmentType`(427)·`status`·`leaveType` → payrollHeadcount
- `onboarding-plan-analyst`(07): `plannedSeparations.byTenureBand` → earlyAttrition, `experience.byDepartment` → 버디 후보 참고
- `product-builder`(09): 파일 전체를 `site/data/insight.json.stats` 로 내장. crossTabs 행 키는 라벨(department·jobFamily·orgGroup명)
- `monthly-report-mailer`(10): `dataQuality.briefDiscrepancies`·`unresolvedByFlag` → 데이터 품질 절
- `people-data-auditor`(11): stdout targetCheck(§2-7)·reconciliation 결과를 test_reconciliation 사전 검사로 사용
