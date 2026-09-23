---
name: product-build
description: "페르소나 fit에 맞춘 제품 3종(Insight 인사 총괄 / Payroll Close 급여 담당 / Onboarding 온보딩 담당)과 허브의 정적 페이지를 만든다 — 공통 데이터 계층(data/stats, data/clean)·니즈 데이터·제품 비교에서 site/data/{insight,payroll,onboard,comparison}.json 스냅샷을 스크립트로 조립하고, references/page-template.md 골격(시스템 폰트·CSS 토큰·라이트/다크·공통 헤더·내장 JSON·Supabase 덮어쓰기·Chart.js·375px·접근성)과 references/product-specs.md 화면 초안(섹션·차트·표 ↔ fit 기준)대로 site/{insight,payroll,onboard}/index.html과 site/index.html을 작성해 스냅샷을 내장한다. '제품 만들어줘', '대시보드 페이지', 'Insight/Payroll/Onboard 화면', '허브 페이지', '스냅샷 조립', 'site/data 갱신', '리포트 뷰', '권한별 대시보드' 요청과, 상류 산출물·니즈 데이터·제품 비교가 바뀌어 페이지나 스냅샷을 '다시/재실행/수정/보완/업데이트/재내장'할 때 반드시 이 스킬을 사용한다. 통계·예측·급여 마감·온보딩 계획 자체는 만들지 않으며(선행 스킬 담당), 제품 채점은 product-judge, 배포는 release-engineer가 한다."
---

# product-build — 페르소나 fit 제품 페이지 구축

## 왜 이 스킬인가

세 페르소나(인사 총괄·급여 담당·온보딩 담당)는 같은 회사의 같은 데이터를 보지만 **묻는 질문이 다르다**. 그래서 제품을 세 개 만들고
같은 니즈 데이터로 비교한다(GLOSSARY 관계 절: 니즈 데이터 → 제품 → 제품 비교). 이 스킬은 그 가운데 단계 — 니즈 데이터의 fit 기준을
화면 요구로 읽어, 공통 데이터 계층의 산출물을 **한 번도 재계산하지 않고** 제품별 스냅샷으로 조립하고, 페르소나가 첫 화면에서
자기 질문의 답을 보게 페이지를 만든다.

숫자를 페이지에서 다시 계산하지 않는 이유: 세 제품이 같은 파일(`data/stats/*.json`)을 실어야 "같은 지표는 같은 값"(reconciliation-policy)이
저절로 성립한다. 페이지 JS가 합계를 내기 시작하면 제품마다 다른 숫자가 나오고 대사가 깨진다.

## 산출물과 소비자

| 산출물 | 경로 | 소비자 |
|---|---|---|
| 제품 스냅샷 | `site/data/insight.json` · `payroll.json` · `onboard.json` · `comparison.json` (DATA_CONTRACT §5) | 제품 HTML(내장), release-engineer(Supabase `report_snapshots` 적재), people-data-auditor(`tests/test_reconciliation.py`) |
| 제품 페이지 | `site/insight/index.html` · `site/payroll/index.html` · `site/onboard/index.html` | 페르소나(고객사), product-judge(3 렌즈), `tests/test_site.py` |
| 허브 | `site/index.html` | 전체 진입점, 제품 비교 표시 |

`site/config.js`(Supabase URL/anon key)와 `site/vercel.json`은 배포 산출물이므로 release-engineer가 만든다. 페이지는 `config.js`가 없어도 동작해야 한다.

## 입력

| 경로 | 필수 | 어느 제품 | 용도 |
|---|---|---|---|
| `data/stats/headcount-stats.json` | insight 필수 | insight, payroll(부분집합) | 인원 통계 |
| `data/stats/month-end-forecast.json` | insight 필수 | insight, (payroll·onboard 대사) | 월말 예측·TO 과부족·인사이트 |
| `data/stats/attrition-risk.json` | 선택 | insight | 리스크 집계·HR 뷰 개인 목록 |
| `data/clean/cleansing-summary.json` | 선택 | insight, payroll | 보정 건수·미해결 항목 |
| `data/clean/headcount-master.clean.csv` | 선택 | insight(hrDirectory), onboard(subset) | 성명 조인 명부 — 재직·휴직자, 5개 필드만 |
| `data/stats/automation-effect.json` | 선택 | insight | 자동화 효과(그대로 내장) |
| `data/stats/payroll-close.json` | payroll 필수 | payroll | 급여 마감 |
| `data/stats/onboarding-plan.json` | onboard 필수 | onboard | 온보딩 계획 |
| `data/clean/planned-joiners.clean.csv` | 선택 | onboard | 입사 예정자(birthDate 제외) |
| `personas/persona-needs.json` | 선택(강력 권장) | 전 제품 | fit 기준 → 섹션 `data-fit`, 핵심 질문 → 화면 순서 |
| `products/product-comparison.json` | 선택 | comparison(허브) | product-judge 산출 — 첫 빌드 때는 없다 |

원천(`data/raw/`)은 읽지 않는다. 통계·예측·파생은 정제 데이터에서만 계산한다는 관계 규칙이 제품에도 적용된다.

## 절차

### 1. 니즈 데이터를 화면 요구로 읽는다
`personas/persona-needs.json`에서 담당 페르소나의 `keyQuestions`(첫 화면 순서), `kpis[].source`(타일), `fitCriteria[]`(섹션·evidence), `requiredFields`, PII 범위를 뽑는다.
`references/product-specs.md` §0의 규칙으로 evidence 접두를 스냅샷 키로 바꿔, 기준마다 맡을 섹션을 정한다. 맡을 섹션이 없는 기준은 지금 적어 둔다(반환값 `fitCoverage.criteriaUncovered`).
니즈 파일이 없으면 product-specs.md의 후보 id로 진행하고 `gaps`에 `missing-input: personas/persona-needs.json`을 남긴다 — 페이지는 만들되 fit 자기 보고는 "미확인"이다.

### 2. 스냅샷을 조립한다
```bash
python3 .claude/skills/product-build/scripts/build_snapshots.py --root /Users/yang/development/zero-hr --as-of 2026-09-23 --product insight
```
- `--product {insight|payroll|onboard|comparison|all}` (기본 `all`). 에이전트 인자 `hub`는 `comparison`으로 넘긴다.
- `--as-of` 기본 2026-09-23. 상류 산출물의 `asOfDate`와 다르면 `as-of-mismatch` gap이 난다 — 기준일을 바꾸려면 상류부터 재실행한다.
- 산출: `site/data/{product}.json` (들여쓰기 2, UTF-8). stdout **마지막 줄**이 요약 JSON 1행, 진행 로그는 stderr.
- 종료 코드: `0` 작성 완료(요약 `status` ok/partial) · `1` 필수 입력 누락(해당 제품 미작성) · `2` 인자 오류.
- 스냅샷 구성(§5)과 이 스크립트가 정한 부분집합:
  - `hrDirectory`: 정제 마스터 `status ∈ {재직, 휴직}` 행의 `empId,name,teamCode,team,position` — 생년월일 제외, 팀·사번 순
  - `statsSubset`: `asOfDate, client, totals, byOrgGroup, byDepartment, byAttributeAll{employmentType,status,leaveType}, byAttribute{employmentType}, crossTabs{departmentByEmploymentType}, provenance`
  - `plannedJoiners`: 정제 입사 예정자 전 컬럼에서 `birthDate`만 제거
  - `hrDirectorySubset`: `hrDirectory` 중 입사 예정자가 배치되는 조직(`onboardingPlan.byDepartment[].deptCode`)의 행만
  - `comparison`: `products/product-comparison.json` 그대로. 없으면 §12 shape의 빈 자리표시자(`products: []`) + gap
- 대사 검사(요약 `reconciliation.checks`): 현원(stats=forecast), 명부 수=현원, 리스크 밴드 합=현원, 급여 월말=예측 월말, 급여 예정 입퇴사=예측 in/out, 타임라인 합=정제 입사 예정 유효 행, 월말 이전 입사 예정=예측 plannedIn, 체크리스트 행=타임라인 합. 한쪽 입력이 없으면 `match: null`(미검사), 다르면 `false` → `status: partial`.

### 3. 페이지를 만든다
`references/page-template.md` 골격으로 시작해 `references/product-specs.md`의 섹션 순서대로 채운다. 순서를 지키는 이유: 섹션 순서가 곧 페르소나의 핵심 질문 순서다.
- 모든 `<section>`에 `data-section` · `data-fit` · `data-evidence`(Insight는 `data-views`도)를 단다 — product-judge가 이것으로 채점한다.
- 뷰(Insight)는 필터다. `DATA` 하나에서 그리고 `hidden`으로 숨긴다. 뷰마다 다른 계산을 두지 않는다.
- 렌더 함수는 멱등(컨테이너 비우고 다시 채움, 차트 `destroy()` 후 재생성) — Supabase 덮어쓰기가 두 번째 렌더를 부른다.
- 빈 데이터는 숨기지 말고 "데이터 없음 — {경로} 미생성"으로 보인다. 누락이 보여야 상류를 고친다.
- 차트는 Chart.js(jsdelivr) 하나만 외부 로드, 없으면 표만. 차트마다 표. 축 하나. 범주 색은 정체성 고정. 상태 색은 상태에만.
- PII: Insight는 HR 뷰에서만 성명(리스크는 점수 없이 등급만), 경영진·경영기획·조직장 뷰는 집계/사번. Payroll·Onboard는 성명 허용, 생년월일은 어디에도 없음.

### 4. 스냅샷을 내장한다
```bash
python3 .claude/skills/product-build/scripts/build_snapshots.py --root /Users/yang/development/zero-hr --product insight --embed
```
`--embed`는 `site/{product}/index.html`(허브는 `site/index.html`)의 `<script id="report-data" type="application/json">` 블록 안을 스냅샷으로 바꾼다(`</`·`<!--` 이스케이프). HTML이 없거나 블록이 없으면 `embed-skipped` gap → `partial`.
JSON을 손으로 붙이지 않는다. 다음 `--embed`가 덮어쓰고, 손으로 넣은 값은 대사되지 않는다.

### 5. 렌더 확인
페이지를 열어(브라우저 도구 또는 `python3 -m http.server` + `site/`) 확인한다: 내장 렌더, 콘솔 오류 0, 다크 모드, 375px 가로 스크롤 없음, 헤더 5요소, 뷰 전환 시 같은 KPI 값.
`config.js`를 임시로 두지 않는다 — 있으면 실제 Supabase를 부른다. 실시간 경로는 release-engineer가 적재 후 확인한다.

### 6. 자기 보고 → 반환
`build_snapshots.py` 요약 + 섹션의 `data-fit` 집계로 에이전트 정의의 "구조화 출력" shape을 만든다. `fitCoverage.coverage`는 자기 보고이지 채점이 아니다 — 공식 점수는 product-judge의 `product-comparison.json`이다.
핸드오프 로그를 `_workspace/handoff/product-build-{product}.md`에 남긴다(시도/근거/실패/검증/다음 인계점).

## 허브 2단계

허브는 product-judge **이전**에 한 번(카드+링크, 비교는 "대기 중"), **이후**에 한 번(`--product comparison --embed`) 만든다.
첫 빌드에서 `product-comparison.json`이 없는 것은 결함이 아니라 순서다 — `status: partial`과 `missing-input` gap이 그것을 말한다.
두 번째 실행은 HTML을 다시 쓰지 않고 스냅샷 내장만 갱신하면 된다(허브 렌더는 `products` 유무로 분기한다).

## 스크립트 요약 JSON (stdout 마지막 줄)

```json
{"status":"partial","asOfDate":"2026-09-23","monthEnd":"2026-09-30","script":".claude/skills/product-build/scripts/build_snapshots.py","embed":true,
 "products":{"insight":{"status":"ok","path":"site/data/insight.json","bytes":183422,
   "components":{"stats":true,"forecast":true,"attrition":true,"cleansingSummary":true,"hrDirectory":true,"automationEffect":true},
   "embedded":"site/insight/index.html","required":["stats","forecast"],"checks":[{"product":"insight","check":"stats.totals.headcount=forecast.totals.headcount","left":406,"right":406,"match":true}]},
  "comparison":{"status":"partial","path":"site/data/comparison.json","bytes":120,"components":{"productComparison":false},"embedded":"site/index.html","required":[],"checks":[]}},
 "reconciliation":{"matched":true,"checked":9,"skipped":2,"mismatches":[]},
 "gaps":[{"product":"comparison","kind":"missing-input","path":"products/product-comparison.json","effect":"선택 입력 없음 — …"}]}
```

`gaps[].kind` 어휘: `missing-input` · `missing-column` · `column-fallback`(v2 컬럼으로 대체, 정보) · `as-of-mismatch` · `reconciliation-mismatch`(요약 `mismatches`로도 표시) · `invalid-shape` · `embed-skipped` · `size-warning`(정보).

## 하지 않는 것
- 통계·예측·리스크·급여 마감·온보딩 계획을 페이지나 스크립트에서 재계산하지 않는다. 표시용 합산(orgLead 실 단위 등)은 각주로 "표시용, 대사 대상 아님"을 적는다.
- 계약 §5에 없는 스냅샷 최상위 키를 추가하지 않는다. 필요하면 반환값 `contractGaps`에 적는다(예: 허브에 기준 문장을 보이려면 §5 comparison.json에 페르소나 fitCriteria 요약이 필요).
- `site/config.js`·`vercel.json`·Supabase 적재는 하지 않는다(release-engineer). 월초 리포트는 링크만 건다(monthly-report-mailer).
- 페르소나 fit 점수를 스스로 확정하지 않는다. 자기 보고는 `fitCoverage`, 공식 채점은 product-judge.

## 재실행 / 수정 / 보완
- 상류 산출물이 바뀌면 `--product all --embed` 한 번이면 된다. 스크립트는 멱등이고 HTML은 내장 블록만 바뀐다.
- 피드백이 화면(순서·차트·라벨)이면 HTML만 고치고 스냅샷은 그대로. 데이터가 틀렸다면 상류를 고친다 — 페이지에서 보정하지 않는다.
- 니즈 데이터가 바뀌면 `data-fit`·`data-evidence`를 다시 맞추고 `fitCoverage`를 다시 낸다. id는 persona-needs-analyst가 유지하므로 매핑만 갱신하면 된다.
- DATA_CONTRACT는 v2가 정본이다. 위 §1~§4의 화면 초안에 남은 v1 키(byDivision/byTeam/position 등)는 `references/product-specs.md` §5 표로 v2 키로 읽는다. 통합 제품 `app`(§15)은 `--product app --embed`로 스냅샷을 조립한다.
