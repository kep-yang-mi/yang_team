---
name: payroll-close
description: "급여 담당(payroll) 페르소나 전용 파생 데이터 '급여 마감'(data/stats/payroll-close.json, DATA_CONTRACT v2 §10·§4-5)을 정제 데이터와 월말 인원 예측에서 생성한다 — 급여 대상 인원(기준일 재직 406/휴직 21/총원 427 → 월말 재직 411/총원 432, 고용유형별·조직별), 일할 계산 대상(당월 입사자 + 월말까지 입·퇴사 예정), 휴직자 급여 처리 구분(무급(정부 급여)/유급/무급), 90일 내 계약 만료, 급여 오류 위험(미해결 항목), 마감 체크리스트(pending|done), 예측 대사(monthEndActive == forecastMonthEnd), 핸드오프 로그 06-payroll. 급여액·보상은 다루지 않는다. '급여 마감', '급여 대상 인원', '월말 급여 명부', '일할 계산 대상', '휴직자 급여 처리', '계약 만료 예정', '급여 오류 위험', '마감 체크리스트', 'payroll-close.json', 'Payroll Close 데이터/스냅샷' 요청과, 급여 마감을 '다시/재실행/수정/보완/업데이트/기준일 변경'하라는 후속 요청에 반드시 사용. 인원 통계·월말 예측·이직 리스크 자체는 선행 단계(headcount-stats, month-end-forecast, attrition-risk)의 일이며 여기서 만들지 않는다."
---

# 급여 마감 (payroll-close) — DATA_CONTRACT v2 §10 + §4-5

급여 담당은 매월 말 "이번 달 급여를 **누구에게, 어떤 구분으로** 지급하는가"를 확정해야 한다.
정제 마스터·입퇴사 예정자·월말 예측에는 그 답이 흩어져 있다. 이 스킬은 그것을 급여 담당의 작업 순서대로
한 파일(`data/stats/payroll-close.json`)로 모은다. 급여액은 HRIS의 영역이므로 다루지 않는다(GLOSSARY "제외").

## 입력 / 출력

| 구분 | 경로 | 필수 | 용도 |
|---|---|---|---|
| 입력 | `data/clean/headcount-master.clean.csv` | 필수 | 재직·휴직(총원 427), 당월 입사, 계약종료일, 미해결 플래그 (§3-1) |
| 입력 | `data/clean/planned-joiners.clean.csv` | 필수 | 월말까지 입사 예정 (§3-3) |
| 입력 | `data/clean/planned-leavers.clean.csv` | 필수 | 월말까지 퇴사 예정 (§3-4, 성명 없음 → 마스터 조인) |
| 입력 | `data/stats/month-end-forecast.json` | 권장 | `totals.forecastMonthEnd`(411) == `monthEndActive` assert, 조직별 `forecastMonthEnd` 대조. 없으면 경고 후 진행 |
| 입력 | `data/reference/org-chart.csv` | 선택 | 조직 11개 순서·명칭(`byDepartment`는 재직 0이어도 전 조직) |
| 입력 | `data/stats/headcount-stats.json` | 선택 | `totals.activeHeadcount/onLeave` 소프트 대사 + 니즈 근거 해소 |
| 입력 | `data/clean/cleansing-summary.json` | 선택 | 니즈 근거 해소 전용 |
| 입력 | `personas/persona-needs.json` | 선택 | 급여 담당 `requiredFields`·`fitCriteria` → 체크리스트 보강 |
| 출력 | `data/stats/payroll-close.json` | — | §10 + §4-5 shape (아래) |
| 출력 | `_workspace/handoff/06-payroll.md` | — | 핸드오프 로그 5절(실행 시작·종료 시 기록) |
| 출력(대사 실패) | `_workspace/payroll-close.unreconciled.json` | — | 진단용 초안. 계약 경로에는 쓰지 않는다 |

원천(`data/raw/`)은 절대 읽지 않는다 — 통계는 정제 데이터에서만 계산한다(GLOSSARY 관계 규칙).

## 절차

1. **선행 산출물 확인.** 정제 CSV 3종이 없으면 실행하지 않고 `input-missing`으로 반환한다 — 정제 데이터 없이 만든 급여 마감은 대사할 수 없어 쓸모가 없다.
2. **실행.**
   ```bash
   python3 .claude/skills/payroll-close/scripts/payroll_close.py --root /Users/yang/development/zero-hr --as-of 2026-09-23
   ```
   - `--root` 기본 `/Users/yang/development/zero-hr`, `--as-of` 기본 `2026-09-23`
   - `--allow-mismatch`: 예측과 불일치해도 계약 경로에 쓴다(진단 전용, 종료 코드는 그대로 2)
   - 종료 코드: `0` 정상(예측 없으면 `status: ok-unverified`) · `2` 대사 실패 · `3` 필수 입력 누락 · `4` 계약 불일치(정제 CSV 헤더 ≠ §3) · `1` 그 외
   - stdout **마지막 줄**이 요약 JSON 1행. 진행 로그는 stderr. 핸드오프 로그는 모든 종료 경로에서 남는다
3. **요약 판독.** `reconciliation.matched` → `targetCheck`(데모 기준일만) → `payrollHeadcount` → `risks`·`checklist.pending` → `personaNeeds` 순.
4. **대사 실패(2).** `reconciliation.byDepartmentMismatches`로 어느 조직이 어긋났는지 특정한다. 원인은 거의 항상 예측과 이 스킬의 **plannedOut 규칙 차이**(§4-5 공통 규칙: 예정일 ≤ 월말 ∧ unknown-emp 제외 ∧ 마스터 재직 — 휴직자 퇴사 예정 처리가 흔한 갈림)다. 스크립트나 산출물을 손보지 말고 불일치를 그대로 반환한다 — 어느 쪽이 맞는지는 `reconciliation-policy` 절차(감사자·예측자 확인)로 결정한다.
5. **계약 불일치(4).** `missingColumns`를 그대로 반환한다. 정제 CSV 헤더가 계약 §3과 다르다는 뜻이므로 클린저·계약 정렬이 먼저다.
6. **위험 해석.** `risks[].unresolvedFlag`가 클린저 어휘(§2-5)면 "고객사 HR 확인 대기", 급여 파생 어휘(§4-5)면 "급여 담당 즉시 확인"으로 구분해 `notes`에 요약한다.
7. **구조화 반환.** 마지막 텍스트는 사람용 메시지가 아니라 워크플로우가 받는 반환 데이터다(아래 shape).

## 산출물 구조 — `data/stats/payroll-close.json`

계약 §10의 최상위 키와 §4-5 shape 보충을 **그대로** 쓴다. 계약에 없는 필드는 산출물에 넣지 않는다(필요하면 `contractGaps`로 보고).

```json
{"asOfDate":"2026-09-23","payPeriod":"2026-09","periodStart":"2026-09-01","periodEnd":"2026-09-30",
 "payrollHeadcount":{"asOfActive":406,"asOfOnLeave":21,"asOfTotal":427,"monthEndActive":411,"monthEndTotal":432,
   "byEmploymentType":{"정규직":{"asOfTotal":354,"monthEndTotal":0},"계약직":{"asOfTotal":31,"monthEndTotal":0},"인턴":{"asOfTotal":19,"monthEndTotal":0},"파견":{"asOfTotal":23,"monthEndTotal":0}},
   "byDepartment":[{"deptCode":"D03","department":"Engineering","asOfActive":104,"asOfOnLeave":6,"asOfTotal":110,"plannedIn":5,"plannedOut":4,"monthEndActive":105,"monthEndTotal":111}]},
 "prorations":{"joinersInPeriod":[{"empId":"E0411","name":"","deptCode":"D03","hireDate":"2026-09-08","employmentType":"정규직","workedDays":23,"proratedRatio":0.767}],
   "plannedJoinersByMonthEnd":[{"joinerId":"J001","name":"","deptCode":"D03","plannedHireDate":"2026-09-28","workedDays":3,"proratedRatio":0.1}],
   "plannedLeaversByMonthEnd":[{"empId":"","name":"","deptCode":"","plannedTerminationDate":"2026-09-30","separationType":"자발적","workedDays":30,"proratedRatio":1.0}]},
 "leaves":{"onLeave":[{"empId":"","name":"","deptCode":"","leaveType":"육아휴직","leaveStart":"","payrollTreatment":"무급(정부 급여)"}],"byTreatment":{"무급(정부 급여)":0,"유급":0,"무급":0}},
 "contracts":{"expiringWithin90Days":[{"empId":"","name":"","deptCode":"","employmentType":"계약직","contractEndDate":""}],"byMonth":{"2026-09":0,"2026-10":0,"2026-11":0,"2026-12":0}},
 "risks":[{"empId":"","issue":"","impact":"","unresolvedFlag":"status-inconsistency"}],
 "checklist":[{"item":"당월 입사자 일할 계산 확인","count":0,"status":"done"}],
 "provenance":{"sources":[],"script":".claude/skills/payroll-close/scripts/payroll_close.py","asOfDate":"","rules":{},"reconciliation":{},"personaNeeds":{},"warnings":[]}}
```

- 성명은 포함한다(급여 업무상 필요 — 계약 §5 Payroll 앱). 생년월일·연령대·급여액은 넣지 않는다(`pii-minimization-policy`).
- `byDepartment`는 조직 체계 11조직 전부(재직 0이어도) — 입사 예정만 있는 조직도 월말 급여 대상이 되기 때문이다. `checklist[].status` ∈ `pending|done`. `contracts.byMonth`는 90일 창에 걸치는 모든 월(0건도 키 유지). 빈 속성 값은 `"미상"` 버킷.
- `provenance`는 계약이 `{}`로 열어 둔 자유 영역이다: `sources`, `script`, `rules`(적용 규칙), `reconciliation`(대사 결과), `personaNeeds`, `warnings`.
- 시각 필드를 넣지 않는다 — 같은 입력이면 같은 파일이 나와 diff로 변경을 확인할 수 있다.

## 계산 규칙 (Why 포함)

| 항목 | 규칙 | 이유 |
|---|---|---|
| `asOfActive` / `asOfOnLeave` / `asOfTotal` | 마스터 `status` 재직 / 휴직 / 둘의 합 | 휴직자도 급여 명부에 있어야 한다(무급이라도). `headcount-stats.totals.activeHeadcount/onLeave`와 같아야 한다 |
| `plannedIn` | 입사 예정자 중 `plannedHireDate ≤ 월말` | 예정일이 기준일 이전인데 마스터에 없으면 포함하되 `date-logic` 위험 |
| `plannedOut` | 퇴사 예정자 중 `plannedTerminationDate ≤ 월말`, 마스터에 없는 사번(`unknown-emp`) 제외, `stale-planned-leaver` 포함 | §4-5 공통 규칙. 예정일이 지났어도 마스터가 재직이면 월말에는 빠져 있어야 한다 |
| 휴직자 퇴사 예정 | `monthEndActive`에서 빼지 않고 `monthEndTotal`에서만 뺀다 + `leaver-not-active` 위험 | 예측은 재직 기준(406)이라 휴직자는 애초에 없다. 급여 명부(총원)에서는 빠져야 한다(§4-5) |
| `monthEndActive` | `asOfActive + plannedIn − plannedOut(재직자만)` | 계약 §10 assert: `forecast.totals.forecastMonthEnd`(411)와 같아야 한다 |
| `monthEndTotal` | `asOfTotal + plannedIn − plannedOut(휴직자 포함)` | 월말 급여 명부 총원(432) |
| `byEmploymentType` | `{유형: {asOfTotal, monthEndTotal}}` 총원 기준, 정규 4유형 키 고정 | §4-5. 합 = `asOfTotal` / `monthEndTotal` (내부 대사) |
| `joinersInPeriod` | 마스터 `hireDate ∈ [월초, 기준일]`, 근무일수 = 입사일~월말 | 이미 입사해 마스터에 있는 당월 입사자. 마스터에 퇴직 행이 없으므로 "당월 이미 퇴직" 목록은 없다(§2-1) |
| `proratedRatio` | 근무일수 ÷ 당월 일수(9월=30), 소수 3자리, 0~1 | 계약 §10 |
| 휴직 처리 | 육아휴직→`무급(정부 급여)`, 질병휴직→`유급`, 기타/공란→`무급` | 계약 §10. 공란은 `status-inconsistency` 위험을 함께 남긴다(클린저가 이미 플래그했으면 중복 생성 안 함) |
| 계약 만료 | 재직+휴직 중 `contractEndDate ∈ [기준일, 기준일+90일]` | 급여 담당은 갱신/종료 결정을 급여 반영 전에 받아야 한다. 기준일 이전 만료는 `contract-expired-active` 위험 |
| 위험 dedup | 같은 (사번, 플래그, 이슈)는 1건 | 같은 사람이 같은 이유로 두 번 목록에 오르면 급여 담당이 건수를 잘못 센다 |
| 체크리스트 | 대상 1건 이상이면 `pending`, 0건이면 `done`; 대사 항목은 일치 시 `done`, 불일치·미수행이면 `pending` | "확인할 것이 없음"과 "확인 완료"를 같은 값으로 두어 급여 담당이 pending만 보면 되게 한다 |
| `targetCheck` | 기준일이 2026-09-23일 때만 §2-7 정본(406/21/427/411/432, 354/31/19/23)과 대조 | 데모 데이터 검증용. 불일치는 종료 코드를 바꾸지 않고 반환값으로 알린다 — 원인은 상류(정제·예측)일 가능성이 높다 |

### 위험 어휘 (`risks[].unresolvedFlag`)

두 부류를 섞지 않는다 — 감사자가 클린징 정답지와 기계적으로 대사하고, 급여 담당은 파생 어휘만 오늘 처리하기 때문이다.

- 클린저 어휘(§2-5 그대로): `org-unknown`, `date-logic`, `date-format`, `status-inconsistency`, `missing-required`, `stale-planned-leaver`, `unknown-emp`
- 급여 파생 어휘(§4-5 허용 3종): `contract-expired-active`(계약종료일 < 기준일인데 재직/휴직), `hire-after-as-of`(입사일 > 기준일인데 재직/휴직), `leaver-not-active`(퇴사 예정자가 마스터에서 휴직)
- 그 외 상황(정규직에 계약종료일, 정규 값 아닌 고용유형, 조직 체계에 없는 코드)은 새 어휘를 만들지 않고 `provenance.warnings`에 적는다

## 페르소나 니즈 반영

`personas/persona-needs.json`이 있으면 `code == "payroll"` 페르소나의 `requiredFields`와 `fitCriteria[].evidence`를 실제 산출물·정제 헤더·선택 입력에 대해 해소해 본다.
- 점 경로: `payroll-close.prorations.joinersInPeriod[].proratedRatio`, `headcount-master.clean.unresolvedFlags` 등. 별칭 `forecast`/`stats`/`payroll`/`payrollClose`/`master`/`joiners`/`leavers`/`cleansingSummary` 허용
- `policy:…`, `site/…`, `reports/…` 접두어는 데이터 필드가 아니므로 통과(product-judge·mailer의 몫). `reconciliation:A=B`는 A·B 둘 다 해소돼야 통과. `;`로 이어진 복수 근거는 전부 해소돼야 통과
- 해소 결과: 미확보(`False`) → 체크리스트 `니즈 필드 미확보: …` / `니즈 기준 미충족 [id]: …` 1건씩. 출처 미생성·미상(`None`) → `니즈 근거 검증 불가: N건` 1건. 니즈 파일이 없거나 깨져 있거나 payroll 페르소나가 없으면 건너뛰고 `personaNeeds.applied=false` + `reason`
- 급여액 필드를 요구하는 니즈는 만들지 않고 미확보로 남긴다 — 제품 범위(GLOSSARY 제외)의 결정이다

## 핸드오프 로그 — `_workspace/handoff/06-payroll.md`

스크립트가 **실행 시작 시** 한 번(상태 `실행 중`), **종료 시** 한 번(모든 종료 코드) 덮어쓴다. 5개 H2 고정: `## 시도한 것` / `## 본 데이터·근거` / `## 실패한 것` / `## 검증된 것` / `## 다음 agent 인계점`.
시작 기록을 남기는 이유: 중간에 죽어도 다음 실행자가 어디까지 왔는지 안다(Operating Rule 2). 종료 기록에는 대사 결과·정본 대조·내부 합계·경고·pending 건수와 하류(product-builder / product-judge / people-data-auditor) 인계점이 들어간다.

## 반환 JSON (스크립트 stdout 마지막 줄 = 워크플로우 소비용)

```json
{"status":"ok | ok-unverified | reconciliation-failed | input-missing | contract-mismatch | error",
 "asOfDate":"2026-09-23","payPeriod":"2026-09","artifact":"data/stats/payroll-close.json","handoffLog":"_workspace/handoff/06-payroll.md",
 "payrollHeadcount":{"asOfActive":406,"asOfOnLeave":21,"asOfTotal":427,"monthEndActive":411,"monthEndTotal":432},
 "plannedIn":19,"plannedOut":14,"plannedOutFromLeave":0,
 "byEmploymentType":{"정규직":{"asOfTotal":354,"monthEndTotal":0}},
 "prorations":{"joinersInPeriod":0,"plannedJoinersByMonthEnd":19,"plannedLeaversByMonthEnd":14},
 "leaves":{"onLeave":21,"byTreatment":{"무급(정부 급여)":0,"유급":0,"무급":0}},
 "contracts":{"expiringWithin90Days":0,"byMonth":{"2026-09":0,"2026-10":0,"2026-11":0,"2026-12":0}},
 "risks":0,"riskFlags":[],"checklist":{"total":7,"pending":0},
 "reconciliation":{"recomputedMonthEndActive":411,"forecastMonthEnd":411,"matched":true,"byDepartmentMismatches":[],"statsActiveHeadcount":406,"statsOnLeave":21,"statsMatched":true,"internal":{"byDepartmentMonthEndActive":true}},
 "targetCheck":{"applicable":true,"matched":true,"mismatches":[]},
 "personaNeeds":{"applied":true,"missingFields":[],"missingCriteria":[],"unverifiable":[]},
 "warnings":[]}
```

- 실패 경로: `input-missing`이면 `missing[]`·`requires`, `contract-mismatch`면 `missingColumns{}`, `error`면 `error`가 추가되고 나머지 집계 키는 없다. `handoffLog`는 항상 있다
- 에이전트(`payroll-close-analyst`)는 여기에 `status` 판정(`ok`인데 `targetCheck` 불일치면 `partial`), `topRisks[]`(파생 어휘 우선 최대 5건, 성명 없음), `notes`를 더해 반환한다
- 반환값에 §4-5가 허용한 산출물 외 필드(`targetCheck`, `status`, `handoffLog`, `plannedIn/plannedOut`)가 있다 — 산출물 JSON에는 넣지 않는다

## 재실행 / 수정 / 보완

- 정제 데이터·예측·니즈 데이터가 갱신되면 그냥 다시 실행한다. 스크립트는 결정적이라 같은 입력이면 같은 파일이 나온다
- 기준일을 바꾸려면 `--as-of`만 바꾼다. 급여 기간·월말·90일 창이 따라오고 `targetCheck`는 `applicable: false`
- 산출물의 숫자를 손으로 고치지 않는다. 규칙 변경(휴직 처리 매핑, 계약 만료 창, 일할 분모)은 DATA_CONTRACT §10 개정이 먼저다
- 대사 실패 뒤 상류가 고쳐지면 재실행한다. `_workspace/payroll-close.unreconciled.json`은 진단 이력으로 남긴다

## 계약 갭 (구현하지 않고 보고한 것)

- `plannedJoinersByMonthEnd[]`에 `employmentType`, `plannedLeaversByMonthEnd[]`에 `separationReason`·`employmentType`이 있으면 급여 담당이 정산 구분을 바로 볼 수 있지만 §10에 없어 넣지 않았다(정제 CSV에서 조인 가능)
- `byDepartment[]`에 `orgGroupCode/orgGroup`이 없어 Payroll 앱의 조직 그룹 집계는 `product-builder`가 org-chart로 조인해야 한다
- `payrollHeadcount`에 `plannedIn/plannedOut` 총계가 없다 — 반환값에만 있다

## 하지 않는 것

- 급여액·수당·보상·계좌·세금 계산 — HRIS 본연의 기능
- 근태·휴가 일단위 기록 — 휴직 여부만 상태로 다룬다
- 인원 통계·월말 예측·이직 리스크 생성 — 선행 단계 산출물을 읽기만 한다
- 제품 스냅샷 `site/data/payroll.json` 조립 — `product-builder`의 일
- 계약 갱신/종료·퇴사 정산 결정 — 사람의 승인 gate. 이 스킬은 "확인 대상"까지만
