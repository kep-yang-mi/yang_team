---
name: month-end-forecast
description: "정제 데이터(data/clean/)에서 DATA_CONTRACT v2 §4-2 월말 인원 예측(data/stats/month-end-forecast.json)을 계산한다 — 조직(11)·조직 그룹(4)·전체의 재직 기준 forecastMonthEnd·toGapAsOf·toGapMonthEnd·toFillRate, 조직별 권고(정상 관리/채용 가속/TO 재검토·이동배치), 다음 달(10월) 전망, 리스크 반영 시나리오(riskAdjusted), 인력계획 인사이트 3종·즉시 액션, 시나리오 플래너 기본값, 핸드오프 로그 04-forecast. 트리거: '월말 인원 예측', '월말 예측', '인원 예측', 'TO 과부족', 'TO 충족률', 'TO 대비', '다음 달 전망', '10월 전망', '채용 가속', 'TO 재검토', '이동배치', '권고', '인력계획 인사이트', '즉시 액션', '리스크 시나리오', '시나리오 플래너', 'forecast', 그리고 클린징 직후·attrition-risk.json 신규 직후·TO 계획 변경 직후. 후속 요청 '예측 다시/재실행/수정/보완/업데이트', 'TO 바뀌었으니 다시 계산', '리스크 반영해서 다시', '가정 문장 보완', '정본과 대조'에도 반드시 이 스킬을 쓴다. 인원 통계(headcount-stats)와 리스크 점수화(attrition-risk) 자체는 다른 스킬 담당."
---

# month-end-forecast — 월말 인원 예측 (DATA_CONTRACT v2 §4-2)

재직 인원에 월말까지 입사 예정을 더하고 퇴사 예정을 빼면 월말 인원 예측이고, TO와 비교하면 TO 과부족이다(GLOSSARY 소리내어 검증 2: 406 + 19 − 14 = 411, TO 422 대비 −11; Engineering −7·Sales −4 채용 가속, Data & AI +7 TO 재검토).
숫자는 전부 `scripts/forecast.py`가 계산한다. 세 제품과 월초 리포트가 같은 숫자를 봐야 하고(`reconciliation-policy`), 급여 마감 `monthEndActive`(411 assert)와 온보딩 계획 `timeline`(27 assert)이 이 파일에 대사되므로 여기가 틀리면 하류가 같이 틀린다. LLM이 손으로 더하면 재실행마다 달라진다.

## 입력·출력 (계약 경로 그대로)

| 구분 | 경로 | 비고 |
|---|---|---|
| 입력 | `data/reference/org-chart.csv` | 조직 그룹(4) > 조직(11) 골격·순서. 없으면 마스터·TO의 코드로 골격 구성 + 경고 |
| 입력(필수) | `data/clean/headcount-master.clean.csv` | `activeHeadcount` = `status` 재직(휴직 제외) |
| 입력(필수) | `data/clean/to-plan.clean.csv` | `deptCode, toHeadcount, effectiveMonth`(기준월 행 우선) |
| 입력(필수) | `data/clean/planned-joiners.clean.csv` | `plannedHireDate ≤ 월말` → 월말 / 다음 달 말까지 → nextMonth |
| 입력(필수) | `data/clean/planned-leavers.clean.csv` | `unknown-emp`·마스터 비재직 제외, stale은 월말 퇴사로 반영(§4-5) |
| 입력(선택) | `data/stats/attrition-risk.json` | 없으면 `riskAdjusted: null` + assumptions 명시 |
| 입력(선택) | `_workspace/forecast-narrative.json` | 에이전트 판단 보완 `{assumptions[], handoffNotes[]}` |
| 출력 | `data/stats/month-end-forecast.json` | §4-2 shape. 스크립트가 유일한 작성자 |
| 출력 | `_workspace/handoff/04-forecast.md` | 핸드오프 로그 5절(시작·종료 시 기록) |
| stdout | 마지막 줄 요약 JSON 1행 | 워크플로우가 파싱하는 **반환 데이터**(사람용 메시지 아님) |

원천(`data/raw/`)은 읽지 않는다. 통계·예측은 정제 데이터에서만 계산한다(GLOSSARY 관계 조항).

## 실행

```bash
# 기본: 계산 + 산출물 + 핸드오프 로그 + §2-7 정본 대조
python3 /Users/yang/development/zero-hr/.claude/skills/month-end-forecast/scripts/forecast.py \
  --root /Users/yang/development/zero-hr --as-of 2026-09-23 --self-check

# 에이전트가 가정·인계 메모를 보탤 때(숫자는 그대로, 문장만 병합)
python3 .claude/skills/month-end-forecast/scripts/forecast.py --self-check --narrative _workspace/forecast-narrative.json

# 기존 산출물만 검사(재계산·핸드오프 로그 없음) — 재호출 전 상태 확인·감사용
python3 .claude/skills/month-end-forecast/scripts/forecast.py --check-only --self-check
```

옵션: `--root`(기본 `/Users/yang/development/zero-hr`) · `--as-of`(기본 `2026-09-23`) · `--self-check` · `--check-only` · `--narrative PATH`.
종료 코드: `0` ok · `1` error(내부 대사 실패·예외 — 파일은 썼을 수 있다. 무엇이 틀렸는지 열어볼 수 있어야 하므로 대사 실패에도 일단 쓴다) · `2` partial(self-check 불일치) · `3` blocked(필수 입력 없음).
순서: `people-data-cleanser` 완료 후. `headcount-statistician`·`attrition-risk-scorer`와 병렬 단계 다음에 실행한다. 리스크가 나중에 나오면 재실행해 `riskAdjusted`만 채운다(기본 예측 숫자는 불변).

## 계산 규칙 (§4-2 · §4-5 구현)

- 월말 = 기준일이 속한 달의 말일(2026-09-30), 다음 달 말 = 그 다음 달 말일(2026-10-31). `--as-of`에서 파생하며 하드코딩하지 않는다.
- `activeHeadcount` = 조직별 `status = 재직` 행 수. 휴직자는 TO 비교에 넣지 않는다(v2 — 휴직자는 자리를 채우지 못하므로 TO 충족의 근거가 아니다). status가 재직/휴직 밖이면 경고(클린저 표기 정규화 문제).
- `toHeadcount`: 조직마다 `effectiveMonth == 기준월` 행 → 기준월 이하 최신 행 → 마지막 행 순으로 고른다. 같은 조직 행이 여럿이면 경고.
- `plannedIn` = `plannedHireDate ≤ 월말`, `nextMonth.plannedIn` = 월말 < 예정일 ≤ 다음 달 말. 그 밖은 미반영 + 경고. 입사 예정자의 미해결 플래그는 반영 여부에 영향을 주지 않는다(입사일이 확정된 사람이므로).
- `plannedOut` 판정 순서(§4-5 "예정일 ≤ 월말 ∧ unknown-emp 제외 ∧ 마스터에서 재직인 사번"):
  1. `unknown-emp` 플래그 또는 마스터에 없는 사번 → **제외**(`excluded.notInMaster`). 뺄 사람이 현원에 없다.
  2. 예정일 파싱 실패 → 제외 + 경고(`excluded.badDate`).
  3. 마스터 상태가 재직이 아님(휴직) → 제외 + 경고(`excluded.notActive`). 재직 기준 예측에서 빠지지만 급여 마감 `monthEndTotal`에는 반영해야 하므로 반환 데이터로 드러낸다.
  4. 조직은 **마스터의 `deptCode`**를 쓴다 — 재직을 센 조직에서 빼야 조직 대사가 맞는다. 퇴사 예정 파일의 조직과 다르면 경고.
  5. `plannedTerminationDate ≤ 월말` → 월말 반영. 예정일이 이미 지난 `stale-planned-leaver`(또는 예정일 < 기준일)도 **월말 퇴사로 반영**하고 `excluded.stale`에 사번을 남긴다(§2-8: 마스터는 아직 재직이므로 월말에는 빠져 있어야 한다). 다음 달 말까지 → `nextMonth.plannedOut`.
- `forecastMonthEnd = active + plannedIn − plannedOut` · `toGapAsOf = active − TO` · `toGapMonthEnd = forecastMonthEnd − TO` · `toFillRate = forecastMonthEnd / TO`(4자리, 전체만).
- **권고(결정적)**: `toGapMonthEnd ≤ −4` → `채용 가속` / `≥ +5` → `TO 재검토/이동배치` / 그 외 `정상 관리`. 임계값은 계약 §4-2 — 바꾸려면 계약이 먼저다.
- 다음 달: `forecastNextMonthEnd = forecastMonthEnd + nextIn − nextOut`, `toGapNextMonthEnd = forecastNextMonthEnd − TO`. TO는 기준월 값을 유지한다(다음 달 TO 미수령 — assumptions에 명시).
- `riskAdjusted`(조직별): `expectedAttrition = expectedAttritionNext3Months / 3`(2자리), `forecastNextMonthEndRiskAdjusted = forecastNextMonthEnd − expectedAttrition`. 기본 예측을 대체하지 않는 **시나리오**이며 퇴사 예정자와 일부 중복될 수 있음을 가정에 적는다. 리스크 파일이 없거나 파싱에 실패하면 전 조직 `null` + assumptions에 명시.
- `byOrgGroup`·`totals`는 조직 합(`toGapAsOf`·`toGapMonthEnd`·`nextMonth` 포함). org-chart의 그룹 순서를 따른다.
- `plannedJoiners`(joinerId·deptCode·plannedHireDate·employmentType)·`plannedLeavers`(empId·deptCode·plannedTerminationDate·separationType·separationReason)는 다음 달 말까지 유효 행만, **성명 없음**(`pii-minimization-policy` — 이 파일은 경영진·경영기획·조직장 뷰로 흘러간다).
- `scenario` = `{"parameters":{"hiringAchievementRate":1.0,"extraAttrition":0},"formula":"forecast = active + round(plannedIn × rate) − plannedOut − extraAttrition"}` — Insight 경영기획 뷰의 시나리오 플래너가 이 식으로 클라이언트에서 재계산한다. 스크립트는 기본값만 낸다.
- `provenance`: `client`·`sources`·`script`·`generatedAt`·`attritionRiskUsed`·`headcountBasis: active`·`contractVersion: v2`·`gate`(승인 gate 문구). 계약이 `{}`로 열어 둔 자리다.

## 인사이트·즉시 액션 (결정적 — §4-2)

| type | 조건 | detail 예 | action |
|---|---|---|---|
| `채용 가속 필요` | 권고 = 채용 가속 조직 묶음 | `Engineering −7, Sales −4` | `채용 pipeline 점검` |
| `TO 재검토 필요` | 권고 = TO 재검토/이동배치 묶음 | `+7 초과 예상` | `TO 재배분 또는 내부 이동배치` |
| `퇴사 영향 점검` | 재직 ≤ 12 이고 plannedOut ≥ 1 | `재직 11명 조직에서 1명 퇴사 예정, 월말 −2` | `업무 공백·인수인계 점검` |

- 각 인사이트는 `scope: department`, `codes[]`(조직 순서), `label`(조직명 나열). 순서는 채용 가속 → TO 재검토 → 퇴사 영향.
- `immediateActions` = 인사이트별 1문장: `Engineering/Sales 채용 pipeline 점검` · `Data & AI TO 재검토` · `Legal & Compliance 퇴사 영향 점검`(월초 리포트 §6 "즉시 액션 3건"이 이 문자열을 그대로 쓴다 — 어휘를 바꾸지 않는다).
- 인사이트 0건이면 결함이 아니다. assumptions에 "전 조직 TO 임계값 이내 — 권고 없음"이 남는다.
- **권고·인사이트·즉시 액션은 제안이다**(`approval-gate-policy`). 채용/TO 결정은 사람이 하므로 `provenance.gate`와 stdout `gate`에 그 사실을 남긴다. 에이전트가 문장을 보탤 때도 "검토 제안", "확인 요청" 어휘를 쓴다.

## 자기 대조 (`--self-check`) · 내부 대사

- **targetCheck**(`--self-check`, 기준일 2026-09-23에서만 `applicable`): §2-7 조직표 **11행 전부** × (toHeadcount/activeHeadcount/plannedIn/plannedOut/forecastMonthEnd/toGapAsOf/toGapMonthEnd/recommendation) + 조직 그룹 4(TO/HC/ME = Executive 10/10/10 · Build 226/220/224 · Go-To-Market 136/128/129 · Operations 50/48/48 — 브리프 §7의 215/119/62가 아니라 조직표 합) + 전체(422/406/−16/19/14/411/−11/0.9739) + 다음 달(8/4/415/−7) + 인사이트 3종의 `codes`(D03·D06 / D05 / D11). 정본 밖 deptCode가 있으면 `unexpected`로 보고.
- 불일치는 `targetCheck.mismatches[{scope, code, field, expected, actual}]`(scope: department·orgGroup·totals·totals.nextMonth·insights). **스크립트를 고치기 전에 상류를 본다** — `activeHeadcount` 불일치는 클린징(조직 정규화·중복 해소·상태 정규화), `plannedIn/Out`은 입·퇴사 예정 파일의 일자·플래그, `toHeadcount`는 TO 정규화, `insights`는 위 셋의 결과다.
- 내부 대사(항상 실행): `Σ byDepartment = Σ byOrgGroup = totals`(5개 필드), 조직별 산식(forecastMonthEnd·toGap·nextMonth), 권고 규칙 재적용, `toFillRate`, `len(plannedJoiners) = plannedIn + nextMonth.plannedIn`(퇴사 동일), 인사이트 필수 필드. 실패하면 exit 1.

## 핸드오프 로그 (`handoff-log-policy`)

스크립트가 `_workspace/handoff/04-forecast.md`를 **두 번** 쓴다. 시작 시 "실행 중" 상태로, 정상·비정상 종료 시 전체 내용으로 덮어쓴다 — 로그에 "실행 중" 문구가 남아 있으면 프로세스가 중간에 죽은 것이다. `--check-only`는 로그를 건드리지 않는다(검사는 실행이 아니다).

| 절 | 내용 |
|---|---|
| 시도한 것 | 실행 명령·시각·status, 계산 범위, 산출물 경로, narrative 병합 건수 |
| 본 데이터·근거 | 계약 조항(§4-2·§4-5·§2-7·§2-8), 입력 파일별 행 수·분류(재직/휴직, 월말/다음 달/제외), 리스크 파일 사용 여부 |
| 실패한 것 | 내부 대사 실패, 정본 불일치 목록, 경고, 제외 사번(unknown-emp·비재직·파싱 실패). 없으면 "없음" |
| 검증된 것 | 내부 대사·targetCheck 결과, 전체 산식(406+19−14=411, −11), 권고 조직, stale 반영 사번 |
| 다음 agent 인계점 | payroll-close-analyst(411 assert·notActive 반영) · onboarding-plan-analyst(27 대사) · product-builder · monthly-report-mailer · people-data-auditor · 승인 gate 문구 · (리스크 미적용 시) 재실행 안내 · narrative `handoffNotes` |

## 가정·인계 메모 보완 (`--narrative`)

산출물 JSON을 손으로 편집하지 않는다 — 재실행하면 덮어써지고, 숫자를 건드리면 하류 대사가 깨진다. 판단으로 보탤 내용은 `_workspace/forecast-narrative.json`에 쓰고 `--narrative`로 넘긴다:

```json
{"assumptions": ["Data & AI 초과 +7 중 Engineering 직군 12명의 D03 이관 가능성 검토(제안)"],
 "handoffNotes": ["경영기획팀 제안: Engineering 10월 말 잔여 −5에 대해 추가 오퍼 규모 검토 — 결정은 승인 gate"]}
```

- `assumptions`는 기본 가정 뒤에 덧붙는다(중복 문장은 추가하지 않음). 기본 가정은 지울 수 없다 — 계산이 실제로 그 가정 위에서 이루어졌기 때문이다.
- `handoffNotes`는 핸드오프 로그 "다음 agent 인계점" 끝에 붙는다. 허용되지 않은 키는 무시하고 경고한다.
- 문장에는 근거 숫자와 "제안" 어휘를 남긴다. 숫자 없는 권고는 경영기획팀이 검토할 수 없고, 결정 어휘는 승인 gate를 침범한다.

## stdout 요약 JSON (반환 데이터)

```json
{"status":"ok|partial|error|blocked","asOfDate":"2026-09-23","monthEnd":"2026-09-30","nextMonthEnd":"2026-10-31",
 "output":"data/stats/month-end-forecast.json","handoffLog":"_workspace/handoff/04-forecast.md",
 "totals":{"toHeadcount":422,"activeHeadcount":406,"plannedIn":19,"plannedOut":14,"forecastMonthEnd":411,"toGapAsOf":-16,"toGapMonthEnd":-11,"toFillRate":0.9739,
           "nextMonth":{"plannedIn":8,"plannedOut":4,"forecastNextMonthEnd":415,"toGapNextMonthEnd":-7}},
 "byOrgGroup":[{"orgGroupCode":"G1","orgGroup":"Build","forecastMonthEnd":224,"toGapMonthEnd":-2,"toGapNextMonthEnd":3}],
 "recommendations":{"D03":"채용 가속","D05":"TO 재검토/이동배치","D06":"채용 가속"},
 "insights":[{"type":"채용 가속 필요","codes":["D03","D06"],"label":"Engineering, Sales","detail":"Engineering −7, Sales −4","action":"채용 pipeline 점검"}],
 "immediateActions":["Engineering/Sales 채용 pipeline 점검","Data & AI TO 재검토","Legal & Compliance 퇴사 영향 점검"],
 "assumptions":["..."],"riskAdjustedApplied":true,
 "riskScenarioTotals":{"expectedAttritionNextMonth":12.18,"forecastNextMonthEndRiskAdjusted":402.82},
 "excluded":{"notInMaster":["E9999"],"notActive":[],"badDate":[],"stale":["E0300"],"beyondHorizon":0},
 "counts":{"byDepartment":11,"plannedJoiners":27,"plannedLeavers":18,"insights":3},
 "consistency":{"passed":true,"failures":[]},"targetCheck":{"applicable":true,"passed":true,"mismatches":[]},
 "warnings":[],"gate":"approval-gate: 권고와 즉시 액션은 제안이며 채용/TO 결정은 사람이 승인한다"}
```

- `status`: `ok` = 대사·targetCheck 통과 · `partial` = 파일은 썼으나 targetCheck 불일치 · `error` = 내부 대사 실패·예외 · `blocked` = 필수 입력 없음. `riskAdjustedApplied: false`는 `ok`다(선택 입력).
- `riskScenarioTotals`는 stdout 전용 — 계약 §4-2에 전체 단위 `riskAdjusted`가 없어 파일에 쓰지 않는다. 리포트가 전체 시나리오를 쓰려면 `byDepartment[].riskAdjusted`를 합산하거나 계약을 먼저 고친다.
- `handoffLog`는 `--check-only`에서 `null`(로그를 쓰지 않았으므로).

## 재실행·수정 시

- "다시/재실행": 그냥 다시 실행한다(결정적 — `generatedAt`만 다르다). `totals`가 달라졌으면 어느 입력이 바뀌었는지(클린징 재실행·TO 갱신·리스크 신규)를 `warnings`·핸드오프 로그로 설명한다. 재실행 전 `--check-only --self-check`로 이전 상태를 남겨 두면 비교가 쉽다.
- "가정 바꿔서": 임계값(−4/+5)·재직 기준·stale 반영 같은 규칙 변경은 DATA_CONTRACT 개정 사안 → `contractGaps`로 올리고 실행하지 않는다. 문장 보완은 `--narrative`. 시나리오(채용 달성률·추가 이탈)는 산출물의 `scenario` 파라미터를 제품이 재계산하는 영역이다.
- `attrition-risk.json` 신규·갱신 후 재실행하면 `riskAdjusted`만 바뀌어야 한다 — 기본 예측이 달라졌다면 결함.

## 실패 시 대응

| 증상 | 원인 | 조치 |
|---|---|---|
| exit 3 `blocked` | 클린징 미실행(정제 4종 없음) | `people-data-cleanser` 먼저. 원천으로 대체 계산하지 않는다 |
| exit 1 `consistency.failures` | 조직 체계에 없는 deptCode, status 도메인 이탈, 중복 사번, 산식 불일치 | `warnings`와 함께 클린저로 돌려보낸다 |
| exit 2 `targetCheck.mismatches` | 정제 수치가 §2-7과 다름 | 상류(생성기·클린저·TO 정규화) 문제. mismatch를 scope별로 그대로 반환 |
| `riskAdjustedApplied: false` | `attrition-risk.json` 없음/파싱 실패 | 결함 아님. 리스크 산출 후 재실행 |
| 로그에 "실행 중" 잔존 | 프로세스 비정상 종료 | 04-forecast 재실행 |
| `excluded.notActive` 비어 있지 않음 | 휴직자의 퇴사 예정 | 결함 아님. 급여 마감이 `monthEndTotal`에 반영하도록 인계 |

## 계약과의 경계

- `byOrgGroup`·`totals`에는 `riskAdjusted`가 없다(계약 shape 준수). 전체 리스크 합계는 stdout `riskScenarioTotals`로만 낸다.
- `provenance`의 내부 필드(`client`·`headcountBasis`·`contractVersion`·`generatedAt`·`gate`)는 계약이 `{}`로 열어 둔 자리다.
- §2-7 기대값은 스크립트 상수(`EXPECTED_*`)에만 있고 산출물에는 넣지 않는다 — 산출물이 정본을 복사하면 대사가 자기 자신과의 비교가 된다.
