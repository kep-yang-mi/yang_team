---
name: headcount-stats
description: "정제 데이터(data/clean/)에서 DATA_CONTRACT §4-1 인원 통계 data/stats/headcount-stats.json 을 전부 계산한다 — totals(총원 427·재직 406·휴직 21·TO 422·기준일 gap −16·입사 예정 19·퇴사 예정 14), 조직 그룹(4)/조직(11)별, 속성별 8종(재직 406 기준), 총원 427 기준(byAttributeAll), 크로스탭 7종, 경력, 퇴사 예정 사유·월별, 데이터 품질, 그리고 §2-7 정본 분포 대조(targetCheck)와 핸드오프 로그(03-stats). 클린징이 끝난 직후, '인원 통계', '인원현황', '재직 인원', '휴직 인원', '총원', '조직별 인원', '조직 그룹별 인원', '속성별 분포', '고용유형/성별/연령대/직군/레벨/재직기간/총경력/스테이지 분포', '크로스탭', '퇴사 예정 사유', '기준일 TO 과부족', 'headcount-stats' 요청 시 반드시 이 스킬을 사용할 것. 통계를 '다시', '재실행', '수정', '보완', '업데이트', '기준일 바꿔서' 산출하라는 후속 요청도 이 스킬로 처리한다. 월말 예측·권고는 month-end-forecast, 이직 리스크는 attrition-risk 담당이므로 제외."
---

# headcount-stats — 인원 통계 집계

정제 데이터에서 `data/stats/headcount-stats.json`을 결정적으로 계산한다.
이 산출물은 세 제품(Insight·Payroll Close·Onboarding)과 월초 리포트가 공유하는 **공통 데이터 계층**의 첫 번째 숫자다.
여기서 나온 `totals.activeHeadcount`(406)가 TO 비교의 기준이고 월말 예측(406+19−14=411)의 출발점이며,
뷰마다 숫자가 달라지면 결함이므로 집계는 반드시 번들 스크립트 한 곳에서만 수행한다. 손으로 세거나 다른 경로로 재계산해 덮어쓰지 않는다.

## 입력 / 출력 (DATA_CONTRACT 경로 그대로)

| 구분 | 경로 | 비고 |
|---|---|---|
| 입력(필수) | `data/clean/headcount-master.clean.csv` | §3-1. people-data-cleanser 산출. 1사번 1행(427), 퇴직 행 없음. utf-8-sig로 읽는다 |
| 입력(권장) | `data/reference/org-chart.csv` | §1. 조직 그룹(4) > 조직(11) 골격과 순서. 재직 0인 조직도 `byDepartment`에 남긴다 |
| 입력(권장) | `data/clean/to-plan.clean.csv` | §3-2. `toHeadcount` → `toGapAsOf`(재직 − TO) |
| 입력(권장) | `data/clean/planned-joiners.clean.csv` | §3-3. `plannedHireDate ≤ 월말` → `totals.plannedIn` |
| 입력(권장) | `data/clean/planned-leavers.clean.csv` | §3-4. `totals.plannedOut`·`plannedSeparations` |
| 입력(선택) | `data/reference/company-stages.json` | `stage` 빈값 보충용. 클린저가 채우는 것이 정상 |
| 출력 | `data/stats/headcount-stats.json` | §4-1 shape 그대로, 계약 외 필드 없음 |
| 출력 | `_workspace/handoff/03-stats.md` | 핸드오프 로그(5절 고정). 실행 시작·종료 시 스크립트가 쓴다 |
| stdout | 요약 JSON 한 줄 | 워크플로우가 파싱하는 **반환 데이터**(사람용 메시지 아님) |

원천(`data/raw/`)은 절대 읽지 않는다. 통계는 정제 데이터에서만 계산한다(GLOSSARY 관계 조항).

## 절차

1. 정제 마스터가 있는지 확인한다. 없으면 실행하지 말고 "클린징 선행 필요"(`blocked`)로 반환한다.
2. 스크립트를 실행한다.
   ```bash
   python3 /Users/yang/development/zero-hr/.claude/skills/headcount-stats/scripts/compute_stats.py \
     --root /Users/yang/development/zero-hr --as-of 2026-09-23
   ```
   `--root` 기본값은 프로젝트 루트, `--as-of` 기본값은 `2026-09-23`. 기준일을 바꾸면 월말 범위·파생 보충값·정본 대조 적용 여부가 그 날짜 기준으로 바뀐다.
   종료 코드: `0` 정상 · `1` 오류 또는 내부 대사 실패(산출물 없음) · `3` 필수 입력 없음(blocked).
3. stdout 마지막 줄의 요약 JSON을 읽는다.
   - `status: "ok"`이고 `reconciliation.passed: true`면 산출물이 계약의 대사 조건을 만족한 것이다.
   - `status: "error"`, `errorType: "reconciliation"`이면 산출물을 쓰지 않았다. 집계 내부 모순이므로 정제 데이터 이상(상태 도메인 이탈·중복 사번·조직 코드 이탈)을 먼저 의심한다.
4. `targetCheck`를 본다. §2-7 정본(조직표 11행 HC/OL/TO, 조직 그룹 10/220/128/48, 속성 분포 8종, 퇴사 사유 5/3/2/2/2, 월별 14/4, Executive Snapshot)과 다르면 `mismatches`에 항목이 적힌다. 이는 **집계 오류가 아니라 정제 결과가 시나리오와 다르다는 신호**이므로 통계를 고치지 말고 반환값에 그대로 실어 오케스트레이터가 클린저를 재호출하게 한다. `applicable: false`(기준일 ≠ 2026-09-23)이면 참고용이다.
5. `_workspace/handoff/03-stats.md`가 이번 실행 시각으로 갱신됐는지 확인한다. "다음 agent 인계점"이 비어 있으면 결함이다.
6. `warnings`·`contractGaps`를 반환값에 옮긴다. 경고는 삼키지 않는다 — 감사자(people-data-auditor)가 같은 항목을 독립 재계산할 때 근거가 된다.

## 계산 규칙 (스크립트가 구현한 정의)

정의를 알아야 결과를 설명할 수 있고, 감사자와 수치가 다를 때 어디서 갈렸는지 찾을 수 있다.

- **총원(headcount)** = `status`가 `재직` 또는 `휴직`인 행(427). **재직(activeHeadcount)** = 재직만(406), **휴직(onLeave)** = 휴직만(21). 그 밖의 상태는 총원에서 제외하고 경고한다(정제 데이터에는 없어야 한다). 마스터에 퇴직 행은 없다(GLOSSARY 제외 항목).
- **TO 비교는 재직 기준**: `toGapAsOf = activeHeadcount − toHeadcount`(조직·그룹·전체 모두). 휴직자를 포함하면 월말 예측·급여 마감 monthEndActive와 어긋난다.
- **byDepartment / byOrgGroup**: org-chart 순서로 전 조직을 나열한다(재직 0 포함). 마스터·TO에만 있는 코드는 뒤에 붙이고 경고한다. 항목은 `deptCode, department, orgGroupCode, orgGroup, activeHeadcount, onLeave, headcount, toHeadcount, toGapAsOf`(그룹은 코드·라벨만 다름). 그룹은 조직의 합이다.
- **byAttribute(재직 406 기준)**: `employmentType, gender, ageBand, jobFamily, level, tenureBand, totalExperienceBand, stage` 8종, 값→인원 딕셔너리. 관측된 값만 싣고(0 키 없음) 순서는 §3-1 정규 값 순서. 빈 값은 `미상` 버킷에 넣어 **합 = 406**을 유지하고 `dataQuality.emptyValueBuckets`에 기록한다.
- **byAttributeAll(총원 427 기준)**: `employmentType`(354/31/19/23)·`status`(406/21)는 합 427, `leaveType`은 휴직자만(합 21). 브리프 §7이 고용유형만 총원 기준으로 적었기 때문에 이 셋만 기준이 다르다.
- **crossTabs**: `{행 라벨: {열 값: 인원}}` 2단 딕셔너리, 행 키는 **라벨**(department명·jobFamily·orgGroup명, 코드 아님). 7종 — `departmentByEmploymentType, departmentByGender, departmentByAgeBand, departmentByLevel, jobFamilyByLevel, jobFamilyByStage, orgGroupByTenureBand`. 재직 406 기준. 행은 조직표 순서 전부(0행 포함), 열은 표 안에서 관측된 값의 합집합(직사각형, 0 채움) — 제품이 표로 그대로 그릴 수 있게 하기 위해서다.
- **experience**: 재직자의 `tenureYears`·`totalExperienceYears` 평균·중앙값(소수 2자리)과 조직별 평균(`byDepartment`, 조직표 순서, 재직 0이면 0.0). 정제 컬럼이 비어 있을 때만 `hireDate`·`priorExperienceMonths`로 §2-8 공식으로 보충하고 경고한다. `ageBand`·`stage`도 같은 방식(생년월일 만 나이 / company-stages.json).
- **plannedIn** = 정제 입사 예정자 중 `plannedHireDate ≤ 월말`(19). 다음 달 입사(8)는 세지 않는다(예측 단계 담당).
- **plannedOut / plannedSeparations** (§4-5 forecast·payroll 공통 정의): 정제 퇴사 예정자 중 ① `unknown-emp` 플래그 또는 마스터에 없는 사번 제외 ② 예정일 파싱 실패 제외 ③ 마스터 상태가 재직인 사번만(휴직자의 퇴사 예정은 재직 기준 집계에서 제외 + 경고) ④ 예정일이 기준일 이전인 `stale-planned-leaver`는 **월말 퇴사로 반영**(§2-8). 조직은 마스터의 조직을 쓴다(퇴사 파일과 다르면 경고).
  - `total` = 예정일 ≤ 월말인 유효 건수(14) = `totals.plannedOut`
  - `bySeparationReason`·`bySeparationType`·`byDepartment`(라벨 키)·`byTenureBand`(마스터 재직기간 구간)는 월말 기준(합 14)
  - `byMonth`는 유효 건 전부(`2026-09: 14, 2026-10: 4`, 합 18)
- **unresolvedCount** = 정제 마스터 행 중 `unresolvedFlags`가 비어 있지 않은 행 수(`totals`와 `dataQuality` 동일 값). `unresolvedByFlag`는 플래그 어휘별 건수.
- **dataQuality.briefDiscrepancies** = 고정 문장 1건: 브리프 §7 조직 그룹 합(215/119/62)이 조직표 합(220/128/48)과 불일치 — 조직표 기준 채택.
- **provenance** = `source`, `script` 두 키만.

## 대사(assert) — 스크립트 안에서 강제 (§4-5)

다음이 하나라도 어긋나면 산출물을 쓰지 않고 `errorType: reconciliation`으로 종료한다.

- `byAttribute.*` 8개 딕셔너리 합 = `totals.activeHeadcount`
- `byAttributeAll.employmentType`·`status` 합 = `totals.headcount`, `byAttributeAll.leaveType` 합 = `totals.onLeave`
- `crossTabs.*` 7개 표의 셀 합 = `totals.activeHeadcount`
- `byDepartment`·`byOrgGroup`의 `activeHeadcount / onLeave / headcount / toHeadcount` 합 = `totals`, 항목마다 `headcount = active + onLeave`, `toGapAsOf = active − to`
- `totals.activeHeadcount + totals.onLeave = totals.headcount`, `totals.toGapAsOf = active − to`
- `experience.byDepartment` 길이 = `byDepartment` 길이
- `plannedSeparations`의 `bySeparationReason / bySeparationType / byDepartment / byTenureBand` 합 = `total` = `totals.plannedOut`, `byMonth`(월말 이하) 합 = `total`
- `dataQuality.unresolvedCount = totals.unresolvedCount`

## 정본 대조(targetCheck) — stdout 전용

§2-7 정본과 대조한 결과를 stdout 요약에만 싣는다(산출물 JSON에는 넣지 않는다 — §4-5 "구조화 반환값에는 산출물 외 필드를 둘 수 있다").
항목: 조직표 11행 `activeHeadcount/onLeave/toHeadcount` · 조직 그룹 재직 10/220/128/48 · `totals` 7종(427/406/21/422/−16/19/14) ·
**속성 분포 8종**(고용유형은 427 기준, 나머지 406 기준 — `attributeDistributions`에 종별 통과 여부) · 퇴사 사유 5/3/2/2/2 · 월별 14/4.
`applicable`은 기준일이 2026-09-23일 때만 `true`. 불일치는 클린저 재호출 신호이지 이 스킬의 수정 대상이 아니다.

## stdout 요약 JSON (워크플로우 소비용)

```json
{"status":"ok","asOfDate":"2026-09-23","output":"data/stats/headcount-stats.json","handoffLog":"_workspace/handoff/03-stats.md",
 "rowsIn":{"headcountMaster":427,"toPlan":11,"plannedJoiners":27,"plannedLeavers":19},
 "totals":{"headcount":427,"activeHeadcount":406,"onLeave":21,"toHeadcount":422,"toGapAsOf":-16,"plannedIn":19,"plannedOut":14,"unresolvedCount":0},
 "byOrgGroup":[{"orgGroupCode":"G1","orgGroup":"Build","activeHeadcount":220,"onLeave":12,"toGapAsOf":-6}],
 "dataQuality":{"unresolvedCount":0,"unresolvedByFlag":{},"emptyValueBuckets":{},"briefDiscrepancies":["..."]},
 "reconciliation":{"passed":true,"checks":80,"failed":[]},
 "targetCheck":{"applicable":true,"passed":true,"checks":0,"mismatches":[],
                "attributeDistributions":{"employmentType":{"passed":true,"mismatches":0,"basis":427},"gender":{"passed":true,"mismatches":0,"basis":406}},
                "unexpectedDeptCodes":[]},
 "warnings":[],"contractGaps":[]}
```

실패 시: `{"status":"blocked","errorType":"FileNotFoundError","error":"...","handoffLog":"..."}`(exit 3) 또는
`{"status":"error","errorType":"reconciliation|ValueError|KeyError|...","error|reconciliation":...,"handoffLog":"..."}`(exit 1).
이 텍스트는 사람용 메시지가 아니라 반환 데이터다.

## 핸드오프 로그 (`_workspace/handoff/03-stats.md`)

Operating Rule 2. 스크립트가 실행 시작 시 "시도한 것"만 채운 골격을 쓰고, 종료 시(성공·대사 실패·blocked 모두) 5절을 채워 덮어쓴다.
- 시도한 것: 명령·시작/종료 시각·상태·집계 범위
- 본 데이터·근거: 계약 절, 입력 행수·존재 여부, 월말, 퇴사 예정 제외/특기 사번, totals, 조직 그룹 재직
- 실패한 것: 오류, 대사 실패 항목, §2-7 불일치, 경고, 계약 갭
- 검증된 것: 내부 대사 항목 수, 정본 대조 결과(속성 8종 종별), 산출물 경로
- 다음 agent 인계점: forecaster·attrition·payroll·onboarding·product-builder·mailer·auditor가 읽을 필드

## 재실행 · 수정 · 보완

- 정제 데이터가 바뀌었으면(클린저 재호출 후) 그냥 다시 실행한다. 스크립트는 결정적이므로 같은 입력이면 같은 출력이 나온다 — 이전 산출물을 읽어 병합하지 않는다.
- 기준일 변경 요청은 `--as-of`만 바꾼다. 코드 수정 없이 재실행한다.
- "특정 수치가 이상하다"는 피드백은 먼저 계산 규칙 절과 대조해 정의 차이인지 데이터 차이인지 가른다. 정의 차이면 DATA_CONTRACT를 먼저 고친 뒤 스크립트를 고친다(계약이 정본). 데이터 차이면 이 스킬의 문제가 아니라 클린저 재호출 대상이다.
- 계약에 없는 필드를 추가하지 않는다. 필요하면 반환값의 `contractGaps`로 올린다.

## 알려진 경계

- 휴직자의 퇴사 예정은 §4-5 재직 기준 정의에 따라 `plannedOut`·`plannedSeparations`에서 제외한다. 사유 집계에 넣을지는 계약이 정하지 않았으므로 발생 시 `contractGaps`로 올린다(데모 데이터에서는 발생하지 않는다).
- `dataQuality.emptyValueBuckets`는 §4-5 "빈 값 발생 시 dataQuality에 기록" 조항의 구현이며 키 이름은 계약이 정하지 않았다. 정제 데이터가 정상이면 항상 `{}`다.
- `org-chart.csv`가 없으면 재직 0인 조직이 `byDepartment`에서 빠진다. 예측 단계가 11개 조직 전부를 기대하므로 이 경고는 무시하지 말고 반환한다.
- 핸드오프 로그는 최신 실행 1건만 남는다(덮어쓰기). 실행 이력 보존은 오케스트레이터의 `_workspace_{timestamp}/` 이동 규칙을 따른다.
