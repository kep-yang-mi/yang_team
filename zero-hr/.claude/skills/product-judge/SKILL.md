---
name: product-judge
description: "심판(product-judge) 절차 — 페르소나 옹호자 3명(급여 담당 payroll / 온보딩 담당 onboarding / 인사 총괄 head-of-hr)이 각자 루브릭(references/rubric-{persona}.md)으로 제품 3종(Insight·Payroll Close·Onboarding)을 채점하는 방법: personas/persona-needs.json의 fitCriteria를 site/*/index.html의 data-fit·data-evidence와 site/data/*.json 스냅샷 경로로 기계 채점(evidence 접두→스냅샷 키 매핑), 정성 항목 0~10 채점, PII 부정 검사 grep, coverage·weightedCoverage·panelScore 계산, _workspace/judging/{persona}.json 출력, 그리고 scripts/aggregate_judgments.py로 세 결과를 products/product-comparison.json(DATA_CONTRACT §12: fitScore·bestFit·summary·recommendation·judges[])으로 병합하는 절차. '제품 채점', '심판', '제품 비교', 'fit 점수', 'panelScore', 'bestFit', 'product-comparison 만들어/갱신', '재채점/다시 채점', '새 페르소나 인풋 반영 후 채점', 'mustFix 목록' 요청 시 반드시 이 스킬을 사용한다. 제품 페이지 작성은 product-build, 통합은 unified-product-builder, 인풋 검증·변경 이력은 product-evolution이 담당."
---

# product-judge — 세 렌즈로 채점하고 하나의 비교표로 병합한다

## 왜 이 스킬인가
세 제품은 같은 공통 데이터 계층을 세 페르소나의 질문으로 나눠 보여 준 **시안**이다. 한 사람이 채점하면 자기 습관에 가까운 시안에 기운다.
그래서 심판 패널(harness team-patterns "심판 패널": N개 시안 → 병렬 심사 → 승자 골격 + 차점자 장점 접목)을 쓴다 — 페르소나마다 옹호자 한 명, 각자 루브릭.
기계 채점(fit 기준 충족)은 렌즈와 무관한 **사실**이므로 세 심판이 같아야 하고, 정성 채점은 렌즈마다 **달라야** 정보가 된다. 병합 스크립트가 전자를 과반으로, 후자를 평균으로 합친다.

## 산출물과 소비자
| 산출물 | 경로 | 소비자 |
|---|---|---|
| 심판별 판정 | `_workspace/judging/{persona}.json` (payroll · onboarding · head-of-hr) | `scripts/aggregate_judgments.py`, product-evolution(델타), unified-product-builder(mustFix 상세) |
| 제품 비교 | `products/product-comparison.json` (§12) | product-builder(hub refresh → `site/data/comparison.json`), unified-product-builder(bestFit 골격), people-data-auditor, CHANGELOG 근거 |
| 이전 라운드 보관 | `products/history/{version}.json` (`--archive-as`) | product-evolution CHANGELOG 점수 델타 |

## 입력
`personas/persona-needs.json`(필수 — 채점표) · `site/{insight,payroll,onboard}/index.html` · `site/data/{insight,payroll,onboard}.json` · `references/rubric-{persona}.md` ·
`.claude/skills/product-build/references/product-specs.md` §0(evidence 매핑) · 선택 `reports/monthly-report-dispatch.json`(`reports/` evidence) · 재채점 시 이전 `_workspace/judging/{persona}.json`.

## 절차 — 심판 1인 (persona 인자 1개, 3회 병렬)

### 1. 채점표를 만든다
`persona-needs.json`에서 세 페르소나의 `fitCriteria[{id, criterion, weight, evidence}]`를 전부 읽는다. 제품↔담당 페르소나: insight→head-of-hr(H-F*), payroll→payroll(P-F*), onboard→onboarding(O-F*).
- **기계 채점표**(criteriaMet): 제품마다 **담당 페르소나**의 기준 — 세 심판이 같은 표를 쓴다
- **옹호자 커버리지표**(advocateCoverage): **내 페르소나**의 기준을 세 제품 각각에 — 통합 제품이 무엇을 흡수할지의 근거

### 2. evidence 접두 → 스냅샷 키 (product-specs.md §0 표를 그대로 쓴다)
| evidence 접두 | 스냅샷 키 | 제품 | 판정 방법 |
|---|---|---|---|
| `headcount-stats.` | `stats.` (payroll은 `statsSubset.`) | insight, payroll | 경로 존재·비어 있지 않음 |
| `month-end-forecast.` | `forecast.` | insight | 〃 (payroll 화면은 `payrollClose.payrollHeadcount.monthEnd*`로 대체) |
| `attrition-risk.` | `attrition.` | insight | 〃, 개인 행은 HR 뷰만 |
| `cleansing-summary.` | `cleansingSummary.` | insight, payroll | 〃 |
| `automation-effect.` | `automationEffect.` | insight | 〃 + 화면에 "(추정)" |
| `headcount-master.clean.` | `hrDirectory[]` / `hrDirectorySubset[]` | insight(HR 뷰), onboard | 배열 비어 있지 않음 |
| `payroll-close.` | `payrollClose.` | payroll | 경로 존재·비어 있지 않음 |
| `onboarding-plan.` | `onboardingPlan.` | onboard | 〃 |
| `planned-joiners.clean.` | `plannedJoiners[]` | onboard | 〃 |
| `site/{product}/index.html {뷰명\|공통 헤더}` | (헤더/뷰 자체) | 해당 제품 | `data-section="header"` 또는 뷰 선택기 존재 |
| `policy:pii-minimization-policy` | (부정 기준) | 전 제품 | 4절 PII 검사 결과가 모두 통과 |
| `reconciliation:{A}={B}` | (두 값 비교) | 전 제품 | 스냅샷의 두 경로 값이 같다 |
| `reports/` | (제품 밖) | insight | `reports/monthly-report-dispatch.json` 존재 + Insight 헤더에 링크 |
| 그 외 | — | — | `met: null, reason: "unverifiable"` — 분모에서 제외 |

### 3. 기계 채점 — 세 가지가 모두 참이어야 `met: true`
```bash
P=insight; ID=H-F1
grep -o "<section[^>]*data-fit=\"[^\"]*\b$ID\b[^\"]*\"[^>]*>" site/$P/index.html            # (a) data-fit에 id가 있는 섹션
grep -o "<section[^>]*data-fit=\"[^\"]*\b$ID\b[^\"]*\"[^>]*>" site/$P/index.html | grep -o 'data-evidence="[^"]*"'   # (b) 그 섹션의 evidence
python3 -c "
import json,re,sys
d=json.load(open('site/data/$P.json')); path='forecast.byDepartment[]'            # (c) 변환된 경로가 스냅샷에 있고 비어 있지 않다
cur=d
for k in [k for k in re.split(r'\.|\[\]',path) if k]:
    cur=cur.get(k) if isinstance(cur,dict) else None
print(bool(cur) and (len(cur)>0 if hasattr(cur,'__len__') else True))"
```
- (b)의 `data-evidence`가 (c)에서 변환한 키와 같은 최상위 키로 시작해야 한다(`forecast.` ≠ `stats.`). 다르면 `met: false, evidence: "data-evidence 불일치"`
- `data-fit`이 HTML에 하나도 없으면 전부 `met: false`(빌더 결함, unverifiable 아님) + `mustFix: "data-fit 속성 부재"`
- evidence 문자열에는 `site/{P}/index.html data-section={name} data-fit={id} · {P}.json {path}[{len}]`처럼 **재현 가능한 위치**를 적는다

### 4. PII 부정 검사 (`pii-minimization-policy` 검증 절 + 루브릭 실격 조건)
제품별로 최소: `birthDate` 0건(스냅샷·HTML) · `riskScore` HTML 0건 · Insight 경영진/경영기획/조직장 전용 섹션의 `hrDirectory|\.name` 참조 0건 · Payroll 금액 필드 0건 · Onboard 코호트 성명 0건.
결과를 `piiChecks.{product}[]`에 `{check, passed, detail}`로. 실패는 점수와 별개로 `mustFix` + 루브릭 상한 적용.

### 5. 정성 채점 — 루브릭 앵커에 댄다
`references/rubric-{persona}.md`의 항목(R1~R6)마다 세 제품을 0/3/5/8/10 앵커 문장에 대고 채점한다. 홈이 아닌 제품은 루브릭의 "홈이 아닌 제품을 볼 때" 상한을 따른다.
`note`에는 근거 `data-section`과 있었던 것/빠진 것. `scores.{product}` = 항목 평균(소수 1자리), 실격이면 상한. must 항목 ≤ 3 → `mustFix`, nice 항목 미충족 → `niceToHave`.

### 6. 계산
- `coverage` = met / (전체 − unverifiable), `weightedCoverage` = Σ(met weight) / Σ(verifiable weight), 소수 4자리
- `advocateCoverage.{product}` = 내 페르소나 기준으로 같은 계산 + `met: [id...]`
- 제품 종합 `scores.{product}`는 5절. **panelScore는 심판이 계산하지 않는다** — 병합 스크립트가 세 심판 평균으로 낸다

### 7. 출력
`_workspace/judging/{persona}.json`에 에이전트 정의(`product-judge.md` 구조화 출력) shape 그대로 쓰고 같은 JSON을 반환한다. 핸드오프 로그 `_workspace/handoff/09-products-judge-{persona}.md`(5절).
다른 파일은 쓰지 않는다 — 심판은 제품을 고치지 않는다.

## 절차 — 병합 (오케스트레이터가 세 심판 완료 후 1회)
```bash
python3 .claude/skills/product-judge/scripts/aggregate_judgments.py --root /Users/yang/development/zero-hr --as-of 2026-09-23 [--archive-as v1.0] [--build-meta _workspace/build-meta.json] [--allow-partial]
```
- 입력: `_workspace/judging/*.json`(기본 3개 필수), `personas/persona-needs.json`, `site/**`, 선택 `--build-meta`(`{insight:{agentMinutes,sharedLayerReuse,uniqueFeatures}}` — product-builder 반환값에서 오케스트레이터가 모음)
- `criteriaMet[].met` = 세 심판 **과반**(유효 판정 중). 불일치는 stdout 요약 `disagreements`에 남는다(규칙 적용 오류 신호)
- `panelScore` = 심판 `scores.{product}` 평균(소수 2자리). `coverage`·`weightedCoverage` = 과반 met 기준 재계산
- `sharedLayerReuse` = 스냅샷 비null 최상위 키 중 공통 계층 키(stats·forecast·attrition·cleansingSummary·hrDirectory·automationEffect·statsSubset·hrDirectorySubset·plannedJoiners) 비율. `uniqueFeatures` = 그 제품에만 있는 `data-section`(header·kpi·data-quality·checklist 제외). `buildEffort.linesOfHtml` = `wc -l`
- `strengths` = 충족 기준 중 weight ≥ 4의 criterion 문장(≤ 6). `gaps` = 미충족 기준 + `[must-fix:{judge}] ...` + `[nice-to-have:{judge}] ...`
- **bestFit** = 최대 `0.5 × weightedCoverage × 10 + 0.5 × panelScore`. `comparison.ranking[]`·`formula`에 기록(§12 확장 — 계약에 반영 제안)
- `summary`·`recommendation`은 템플릿 문장(스크립트 내) — 결정적이라 재실행이 같은 문장을 낸다
- `--archive-as vX.Y`: 기존 `product-comparison.json`을 `products/history/vX.Y.json`으로 보관한 뒤 덮어쓴다(진화 루프)
- stdout 마지막 줄 요약: `{"status","out","bestFit","ranking":[{"code","composite","weightedCoverage","panelScore"}],"judges","disagreements":[...],"warnings":[...]}` · 종료 코드 0 완료 / 1 입력 누락 / 2 인자 오류

## 재채점 / 다시 / 새 페르소나
- 제품 HTML만 바뀜 → 세 심판 재실행(기계·PII 전부, 정성은 바뀐 섹션 항목만) → 병합 `--archive-as {현재 버전}`
- 니즈 데이터가 바뀜(새 인풋, product-evolution) → 새 페르소나는 `references/rubric-{persona}.md`가 있어야 심판 인스턴스가 뛴다. 없으면 인풋의 `rubric.lens/scoring`으로 루브릭 파일을 **먼저** 만든다(harness 스킬 또는 사용자) — 앵커 없는 점수는 재현되지 않는다
- 점수 델타(이전 `_workspace/judging/*.json`·`products/history/*.json` 대비)는 `product-evolution`의 `changelog.py add --before --after`가 근거로 쓴다

## 하지 않는 것
- 제품·스냅샷·니즈 파일을 고치지 않는다(mustFix로 되돌린다) · panelScore를 심판이 계산하지 않는다 · 앵커 없이 점수를 주지 않는다 · 심판 산출물에 성명을 인용하지 않는다(섹션명·사번·건수만)
