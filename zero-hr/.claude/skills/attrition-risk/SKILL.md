---
name: attrition-risk
description: "정제 마스터(data/clean/headcount-master.clean.csv)와 정제 TO 계획에서 재직자(406명)별 이직 리스크 점수(0~100)·밴드(높음/중간/낮음)·근거 요인과 조직(11)·조직 그룹(4)별 3개월 기대 이탈 인원을 규칙 기반 모델 rule-based-v1로 산출해 data/stats/attrition-risk.json(DATA_CONTRACT §4-3)과 핸드오프 로그 _workspace/handoff/05-attrition.md를 만든다. 이직 리스크, 이탈 위험, attrition risk, 리스크 점수/밴드, 기대 이탈, 리스크 반영 시나리오(riskAdjusted) 입력, 요인·가중치 조정, '높음이 너무 많다/적다' 같은 분포 지적, 그리고 attrition-risk.json을 다시/재실행/수정/보완/업데이트/기준일 바꿔서 산출할 때 반드시 이 스킬을 사용한다. 인원 통계(headcount-stats)·월말 예측(month-end-forecast) 자체는 다른 스킬이 맡는다."
---

# attrition-risk — 이직 리스크 점수 (rule-based-v1)

## 목적

재직자마다 "이 사람이 왜 이직 위험이 있는가"를 요인으로 설명할 수 있는 점수를 매기고, 조직·조직 그룹별로 향후 3개월 기대 이탈 인원을 낸다.
결과는 `headcount-forecaster`가 리스크 반영 시나리오(`riskAdjusted`)로, Everyday People Agent Insight의 HR 뷰가 개인 목록으로, Onboarding이 버디 후보 선별과 90일 코호트로 쓴다.
규칙 기반을 쓰는 이유: 고객사 퇴직 이력이 범위 밖(GLOSSARY 제외 항목)이라 학습 모델을 검증할 수 없고, HR이 개인에게 면담을 제안할 때 근거를 말로 설명해야 하기 때문이다.

## 언제 쓰는가
- 오케스트레이터가 클린징(02) 완료 후 통계(03)와 병렬로 05-attrition 단계를 호출할 때
- 이직 리스크·이탈 위험·기대 이탈·리스크 밴드 관련 요청, 가중치 조정 요청, "높음이 너무 많다/적다" 피드백
- 정제 마스터·정제 TO 계획이 바뀌어 attrition-risk.json을 다시 만들어야 할 때

쓰지 않는 경우: 원천(`data/raw/`)에서 직접 계산하려 할 때(금지 — 리스크는 정제 데이터에서만), 인원 통계나 월말 예측 자체를 만들 때.

## 입력·출력

| 구분 | 경로 | 비고 |
|---|---|---|
| 입력(필수) | `data/clean/headcount-master.clean.csv` | DATA_CONTRACT §3-1. utf-8-sig로 읽음. 없으면 종료 코드 2 |
| 입력(권장) | `data/reference/org-chart.csv` | §1. 조직 순서·명칭. 재직 0 조직까지 `byDepartment`에 포함 |
| 입력(권장) | `data/clean/to-plan.clean.csv` | §3-2. `dept-understaffed` 요인(gapAsOf = 재직 − TO < 0). 없으면 요인 0명 + warning |
| 입력(선택) | `data/stats/headcount-stats.json` | §4-1. 있으면 `totals.activeHeadcount`(406) 대사 |
| 출력 | `data/stats/attrition-risk.json` | §4-3 shape |
| 출력 | `_workspace/handoff/05-attrition.md` | 핸드오프 로그. 실행 시작 시 1차, 종료 시 확정(5개 H2) |
| stdout | 마지막 줄 요약 JSON 1행 | 워크플로우가 파싱. 개인 행 없음 |

## 실행 절차

1. 정제 마스터가 있는지 확인한다. 없으면 실행하지 말고 `people-data-cleanser` 선행을 요구한다(스크립트를 돌려도 종료 코드 2 + 실패 로그만 남는다). 스모크 테스트는 스크래치패드 픽스처 루트(`--root`)로만 한다.
2. 스크립트를 실행한다.
   ```bash
   python3 /Users/yang/development/zero-hr/.claude/skills/attrition-risk/scripts/score_attrition.py \
     --root /Users/yang/development/zero-hr --as-of 2026-09-23
   ```
   옵션:
   - `--weights '{"tenure-1-3y":18,"level-ic":3}'` — 지정한 요인의 **기본** 가중치만 재정의(나머지 유지). 알 수 없는 요인명은 오류(종료 코드 2, `knownFactors` 반환)
   - `--no-calibrate` — 밴드 분포 보정을 끄고 기본 가중치 그대로(진단용, 하류에 넘기지 않는다)
   - `--top-factors N` — `byEmployee.topFactors` 최대 개수(기본 3)
3. stdout 마지막 줄 요약 JSON을 읽는다. `status: "ok"`, `model.calibration.targetMet: true`, `warnings: []`면 완료다.
4. `targetMet: false`면 [가중치 조정 지침](#가중치-조정-지침)을 따라 **1회** 조정 후 재실행한다.
5. [산출물 검증 체크리스트](#산출물-검증-체크리스트)를 확인하고 구조화 출력(반환 JSON)을 만든다.
6. 핸드오프 로그는 스크립트가 썼다. 가중치를 조정했으면 **마지막 실행 뒤** `## 시도한 것`에 "1차 결과 → 조정 요인·이유 → 2차 결과"를 한 줄 덧붙인다(실행마다 덮어쓰므로 순서가 중요하다).

실행 시간: 406명 기준 1초 미만(보정 격자 탐색 포함). 같은 입력이면 같은 출력(결정적 — 난수 없음).

## 모델 정의 — rule-based-v1

### 점수
`riskScore = min(100, Σ 해당 요인의 실효 가중치)`. 요인은 참/거짓만 판정하고 정도(degree)는 쓰지 않는다 — 정도를 넣으면 근거 설명이 "0.7만큼 정체"처럼 모호해진다.
`topFactors`는 해당 요인을 실효 가중치 내림차순으로 최대 3개.

### 밴드 (계약 고정)
`높음: score>=60` · `중간: 35<=score<60` · `낮음: score<35`. 이 경계는 DATA_CONTRACT §4-3이 고정하므로 **바꾸지 않는다**. 분포는 가중치로 조정한다.

### 기대 이탈 확률 (3개월, 계약 §4-3)
높음 0.35 · 중간 0.12 · 낮음 0.03. `expectedAttritionNext3Months = Σ(밴드별 확률 × 인원)`, 소수 2자리. 조직·조직 그룹·전사 각각 계산한다.
`headcount-forecaster`는 조직별 값을 1/3로 월할해 다음 달 말 `riskAdjusted`에 반영한다. 시나리오이며 기본 예측을 대체하지 않는다.

### 요인 (7개)

| factor | 군 | 기본 가중치 | 판정 | Why |
|---|---|---|---|---|
| `tenure-1-3y` | 신호 | 22 | `1.0 <= tenureYears < 3.0` (tenureBand 1~3년) | 역량이 시장에서 인정받고 첫 이직 창이 열리는 구간. 일반적으로 이직률 최고 구간(데모 151명, 37%) |
| `level-stagnation` | 신호 | 24 | `tenureYears >= 3.0` 이고 `level` ∈ {IC1, IC2} | 레벨은 재직기간과 양의 상관(§2-7 제약)이므로 3년+ IC1/IC2는 뚜렷한 승급 정체. 승급 좌절은 자발퇴사의 대표 동기 |
| `contract-expiring` | 신호 | 35 | `employmentType` ∈ {계약직, 인턴, 파견} 이고 `(contractEndDate − asOf).days <= 90` (경과 포함) | 가장 확실한 이탈 이벤트. 만료가 지났는데 재직이면 갱신 미반영이라 동일 취급(데모 ≥ 8명) |
| `job-family-eng-data-ai` | 기초 | 10 | `jobFamily` ∈ {Engineering, Data/AI} | 외부 수요 최대 직군(데모 140명, 34%) → 단독으로 밴드를 못 바꾸게 작게 |
| `age-20s-30s` | 기초 | 7 | `ageBand` ∈ {20대, 30대} | 이동 비용 낮음. 재직 75%(303명)가 해당 → 작게 |
| `dept-understaffed` | 기초 | 8 | 소속 조직의 기준일 `gapAsOf = 재직 − TO < 0` (정제 마스터 재직 수 − 정제 TO 계획) | 정원 미달 조직은 1인당 부하가 커져 번아웃·이탈 증가. 데모에서 11개 중 8개 조직(약 80%)이 해당하므로 조직 단위 **기초** 요인. §4-2 '채용 가속'(≤ −4)보다 넓은 정의라 신호로 두면 전원이 중간이 된다 |
| `level-ic` | 기초 | 5 | `level` ∈ {IC1, IC2, IC3} | 관리·리드 레벨은 보상·역할로 결속이 큼. 재직 45%(180명)가 해당 → 최소 가중치 |

기본 가중치 설계 논리: 기초 4개 합(30)만으로는 낮음, 신호 1개 + 기초 전부(≤ 57) = 중간, 신호 2개 이상 + 기초 = 높음, 계약 만료(35) + 기초 25 이상 = 높음이 되도록 잡았다.
계약 §4-3 요인 후보(재직 1~3년, 20~30대, Engineering/Data-AI 직군, 레벨 정체, 계약 만료 90일 내, 소속 조직 TO 부족, 레벨 IC)를 그대로 구현했고 추가 요인은 없다.
조직 TO 과부족은 `headcount-stats`를 기다리지 않고 정제 마스터·정제 TO 계획에서 직접 계산한다 — 그래야 `headcount-statistician`과 병렬 실행이 된다.

### 밴드 분포 보정 (결정적)
목표: **높음 8~15%, 중간 25~35%**. 극단 분포(높음 30% 또는 2%)는 HR이 목록을 보지 않거나 조치 대상이 없어 쓸모가 없다.

스크립트는 요인을 신호군·기초군으로 나누고 배율 2개를 격자 탐색한다(0.5~2.0, 0.05 간격 → 최적점 주변 0.01 정밀). 목적 함수 우선순위: ① 범위 위반량 최소 ② 배율이 1.0에 가까울 것(최소 조정) ③ 목표 중앙(11.5%/30%)에 가까울 것.
실효 가중치 = `round(기본 × 군 배율)`이며, `model.factors[].weight`에는 **실효** 가중치를, `rationale`에는 "정의. 이유. 기본 N × 신호군 배율 k → 실효 W. 해당 인원 n명(x%)"를 적어 감사 가능하게 한다.
배율이 2개인 이유: 하나로는 높음과 중간을 동시에 맞출 수 없는 분포가 있다. 점수화 대상이 20명 미만이면 보정을 건너뛰고 warning을 낸다.

### 대상
`status = 재직`만 점수화한다(휴직 제외). TO 비교·월말 예측의 모집단(재직 인원)과 같아야 forecaster가 기대 이탈을 그대로 뺄 수 있기 때문이다. 제외한 휴직 수는 `reconciliation.onLeaveExcluded`로 드러낸다.
퇴사 예정자도 재직이면 점수화하되, `plannedOut`과 이중 계산될 수 있음을 `assumptions`로 forecaster에 알린다. 미해결 플래그가 있는 행도 제외하지 않는다.

## 산출물 검증 체크리스트

실행 후 반드시 확인한다. 하나라도 어긋나면 반환값 `warnings`에 적는다(스크립트가 앞 3개는 내부 대사로 강제하며 실패 시 산출물을 쓰지 않는다).
- [ ] `byEmployee` 각 행의 키가 `empId, deptCode, riskScore, riskBand, topFactors` 5개뿐이다 — 성명·생년월일·연령대·소속명 없음 (pii-minimization-policy)
- [ ] `byEmployee` 행 수 = `summary` 밴드 합 = `byDepartment` 재직 합 = `byOrgGroup` 재직 합 (reconciliation-policy)
- [ ] 위 값 = `headcount-stats.totals.activeHeadcount`(데모 406) — stats 파일이 있을 때 `reconciliation.headcountMatchesStats: true`
- [ ] `byDepartment`에 조직 체계 11조직이 전부 있고(재직 0 포함) `byOrgGroup`에 G0~G3 4개가 있다
- [ ] `model.bands`가 계약 문자열과 정확히 같다: `{"높음":"score>=60","중간":"35<=score<60","낮음":"score<35"}`
- [ ] `expectedAttritionNext3Months` = 0.35×높음 + 0.12×중간 + 0.03×낮음 (소수 2자리)
- [ ] `model.calibration.targetMet: true` — 아니면 가중치 조정 지침으로
- [ ] 각 `model.factors[].rationale`에 정의·이유·기본→실효 가중치·해당 인원이 적혀 있다
- [ ] `_workspace/handoff/05-attrition.md`가 "(완료)" 헤더와 5개 H2를 갖는다

## 반환 JSON (구조화 출력)

최종 텍스트는 사람용 메시지가 아니라 워크플로우가 파싱하는 **반환 데이터**다. 스크립트 stdout 요약을 바탕으로 아래 shape을 반환한다. 개인 행은 넣지 않는다.

```json
{
  "status": "ok",
  "asOfDate": "2026-09-23",
  "artifacts": ["data/stats/attrition-risk.json"],
  "handoffLog": "_workspace/handoff/05-attrition.md",
  "elapsedSeconds": 0.0,
  "model": {"name": "rule-based-v1", "factorCount": 7,
            "calibration": {"applied": true, "signalScale": 1.16, "baselineScale": 1.10, "targetMet": true, "target": {"높음": "8~15%", "중간": "25~35%"}},
            "weightsOverridden": {}},
  "scoredEmployees": 406,
  "summary": {"높음": 0, "중간": 0, "낮음": 0, "expectedAttritionNext3Months": 0.0},
  "bandShares": {"높음": 0.0, "중간": 0.0, "낮음": 0.0},
  "avgRiskScore": 0.0,
  "byOrgGroup": [{"orgGroupCode": "G1", "orgGroup": "Build", "activeHeadcount": 220, "높음": 0, "중간": 0, "낮음": 0, "avgRiskScore": 0.0, "expectedAttritionNext3Months": 0.0}],
  "topRiskDepartments": [{"deptCode": "D03", "department": "Engineering", "activeHeadcount": 104, "높음": 0, "avgRiskScore": 0.0, "expectedAttritionNext3Months": 0.0}],
  "factorPrevalence": {"tenure-1-3y": 0, "level-stagnation": 0, "contract-expiring": 0, "job-family-eng-data-ai": 0, "age-20s-30s": 0, "dept-understaffed": 0, "level-ic": 0},
  "factorInputs": {"understaffedDepts": ["D02", "D03"], "deptGapAsOf": {"D03": -8}, "toPlanFound": true},
  "reconciliation": {"scoredEmployees": 406, "onLeaveExcluded": 21, "masterRows": 427, "bandSumMatches": true, "byDepartmentHeadcountSum": 406, "byOrgGroupHeadcountSum": 406, "byEmployeeKeysContractOnly": true, "statsFileFound": true, "statsActiveHeadcount": 406, "headcountMatchesStats": true},
  "assumptions": ["밴드별 3개월 이탈 확률 높음 0.35 / 중간 0.12 / 낮음 0.03 (계약 §4-3) — 시나리오이며 예측을 대체하지 않는다",
                  "요인은 참/거짓 판정, 점수는 실효 가중치 합(0~100 캡). 밴드 경계 고정, 분포는 배율로 보정",
                  "재직 406명만 점수화(휴직 21 제외) — TO 비교·예측 모집단과 동일",
                  "퇴사 예정자도 재직이면 점수화 — riskAdjusted에서 plannedOut과 이중 계산 가능",
                  "dept-understaffed는 기준일 gapAsOf<0 조직 소속 여부"],
  "warnings": [],
  "contractGaps": []
}
```
`status: "error"`일 때는 `error`와 `requires`(선행 에이전트명)를 넣고 `artifacts`는 빈 배열, `handoffLog`는 실패 로그 경로로 둔다. `topRiskDepartments`는 기대 이탈 내림차순 상위 5조직.

## 가중치 조정 지침

보정이 `targetMet: false`를 내거나 분포 피드백을 받았을 때만 조정한다. 조정은 **원인이 되는 요인 하나 또는 둘**에 한정한다.

1. `factorPrevalence`를 본다. 어떤 신호 요인이 재직의 40% 이상에 걸리면 그 요인이 중간을 부풀린다 → 기본 가중치를 낮춘다(예: `tenure-1-3y` 22→16). 어떤 신호 요인도 10% 이상 걸리지 않으면 높음이 부족하다 → 가장 흔한 신호 요인을 올린다.
2. 기초 요인은 합이 30을 넘지 않게 유지한다. 넘으면 신호 요인 하나만으로 높음(60)에 닿아 "신호 2개 이상"이라는 모델 논리가 깨진다.
3. `--weights`로 재실행하고, 반환값 `model.weightsOverridden`·`assumptions`와 핸드오프 로그 `## 시도한 것`에 "무엇을 왜" 바꿨는지 적는다.
4. 요인 판정 자체를 바꿔야 하면(예: 계약 만료 창 90일→60일, TO 부족 임계 gapAsOf<0 → ≤ −4) 스크립트 상단 상수(`CONTRACT_WINDOW_DAYS`, `UNDERSTAFFED_GAP_BELOW`, `STAGNATION_TENURE_YEARS`)와 `FACTORS`의 `definition`·`why`, 이 문서의 요인 표를 함께 고친다. 정의만 바꾸고 문서를 안 바꾸면 rationale이 거짓이 된다.

## 핸드오프 로그 (handoff-log-policy)

스크립트가 `_workspace/handoff/05-attrition.md`를 두 번 쓴다: 실행 시작 시 "(실행 중)" 헤더로 1차(시도한 것만 채움), 정상 종료 시 "(완료)"로 5개 절 확정, 실패 시 "(실패)"로 원인·선행 필요·인계점만.
- `## 시도한 것`: 명령·옵션, 모델·요인 수, 보정 배율·targetMet, 가중치 재정의
- `## 본 데이터·근거`: 입력 4종 존재 여부와 행 수, gapAsOf<0 조직, 요인 유병률, 실효 가중치
- `## 실패한 것`: warnings 전부(없으면 "(없음)")
- `## 검증된 것`: 대사 4종, PII 키 검사, 밴드 분포와 목표 충족, 기대 이탈 산식, bands 문자열
- `## 다음 agent 인계점`: forecaster·onboarding·product-builder·mailer·auditor가 읽을 필드와 상위 기대 이탈 조직

"(실행 중)" 헤더가 남아 있으면 스크립트가 중간에 죽은 것이다 — stdout 오류를 보고 재실행한다.

## 알려진 제약·가정
- 퇴직 이력이 범위 밖(현재 임직원 427만)이라 "조직 퇴직률"·"최근 휴직 복귀" 같은 이력 기반 요인은 쓰지 않는다. 계약 §4-3 요인 후보 7개만 구현한다.
- `dept-understaffed`는 기준일 기준(재직 − TO)이며 월말 예측 gap이 아니다. 월말 기준으로 바꾸면 forecaster 산출물에 의존하게 되어 병렬 실행이 깨진다.
- `byDepartment`·`byOrgGroup`은 재직 0 조직도 행으로 남긴다(모두 0). 소비자는 `deptCode`/`orgGroupCode`로 조인한다.
- 정제 마스터에 중복 사번이 남아 있으면 뒤 행을 유지하고 `warnings`에 남긴다 — 클린저 결함 신호다.
- 재직상태가 재직/휴직이 아닌 행은 점수화에서 제외한다(건수 `warnings`).

## 계약 갭 (contractGaps — 만들지 않고 보고)
스크립트 stdout `contractGaps`에 아래가 실려 온다. 반환값에 그대로 옮긴다.
- `model.calibration`·`model.assumptions[]`: §4-3 `model` shape에 없음. reconciliation-policy(가정 명시)를 위해 둠 → 계약 §4-3 보충 필요
- `byDepartment[].department/orgGroupCode/orgGroup/toGapAsOf`: §4-3에 없음(§4-1·§4-2 `byDepartment`와 같은 명칭 열 + 요인 근거) → 보충 필요
- `byOrgGroup[]` shape: §4-3이 `[]`로 비워 둠 → `byDepartment`와 동일 필드 + `orgGroupCode`/`orgGroup`으로 정의
- `provenance`: §4-3에 없음(§4-1·§4-2·§10·§11은 보유) → 보충 필요

## 후속 소비자
- `headcount-forecaster`: `byDepartment[].expectedAttritionNext3Months` ÷ 3 → `riskAdjusted.expectedAttrition` (deptCode 조인)
- `onboarding-plan-analyst`: `byEmployee[].riskBand` (empId 조인 — 버디 후보 = 낮음, 90일 코호트 밴드)
- `product-builder`(Insight): HR 뷰만 `byEmployee` + 정제 마스터 조인(성명), 그 외 뷰는 `summary`·`byOrgGroup`·`byDepartment`
- `monthly-report-mailer`: `summary`·`byOrgGroup` 집계만 인용
- `people-data-auditor`: 위 검증 체크리스트를 독립 재계산으로 확인
