---
name: zerohr-orchestrator
description: "Zero Company HR(Everyday People Agent) 하네스의 owner agent. 고객사 원천 4종(인원현황 마스터·TO 계획·입사 예정자·퇴사 예정자) → 클린징 → 인원 통계·월말 인원 예측·이직 리스크·급여 마감·온보딩 계획 → 페르소나 니즈 → 제품 3종(Insight/Payroll Close/Onboarding) → 심판 3명 채점 → 통합 제품(app) → 월초 리포트·변경 이력까지 한 번에 조율한다. 트리거: 'HR 리포트 만들어줘', '인원 통계', '인원현황', 'TO 과부족', '월말 인원 예측', '입퇴사 예정', '이직 리스크', 'HR 대시보드', '권한별 대시보드', '월초 리포트', '제품 3개 비교', '심판/채점', '통합 제품', '데모 실행', '파이프라인 돌려줘'. 후속 작업도 반드시 이 스킬: '다시 실행', '재실행', '업데이트', '수정', '보완', '예측만 다시', '제품만 다시', '재채점', '새 페르소나 인풋 반영', '이전 결과 개선', 'TO 바뀌었으니 다시'. 용어 정의·파일 위치 같은 단순 질문은 직접 답한다."
---

# ZeroHR Orchestrator — Everyday People Agent의 owner agent

Zero Company OS의 Operating Rule 3(하네스 분할)에 따라 복잡한 HR 운영 업무를 역할별 agent에 나누고, 마지막에 이 owner가 종합한다.
사람은 승인 gate(Rule 4)만 담당한다: 외부 발송·배포·조직 변경은 "준비 완료" 산출물을 보고 사람이 결정한다.

## 실행 모드: 하이브리드

| Phase | 모드 | 이유 |
|---|---|---|
| ①②③ 데이터 계층 | **서브에이전트 순차/병렬** (스크립트 결정적) | 스크립트가 숫자를 계산하므로 에이전트는 실행·검증·판독만. 의존 순서가 고정 |
| 페르소나 → 제품 3종 | **서브에이전트 병렬 3** | 제품은 서로 독립. 같은 니즈 데이터·같은 공통 계층을 읽는다 |
| 심판 3명 → 비교 | **워크플로우 심판 패널** 또는 서브에이전트 병렬 3 + 결정적 집계 스크립트 | 채점은 상호 비교가 필요하므로 배리어가 정당. 집계는 `aggregate_judgments.py`가 결정적으로 |
| 통합 제품 → 변경 이력 | **서브에이전트 단발** | 승자 골격 + 차점 강점 흡수. 결과는 자산으로 |
| 검증 | **서브에이전트(auditor)** | 경계면 교차 비교(통계↔예측↔급여↔온보딩↔스냅샷↔리포트) |

Workflow 도구가 쓰이는 경우 이 스킬 트리거가 옵트인이다. 기본 규모는 에이전트 ≤ 10개.

## 에이전트 구성 (누가) ↔ 스킬 (어떻게)

| 단계 | 에이전트(`.claude/agents/`) | 스킬 | 산출(계약 §) |
|---|---|---|---|
| 01 collect | `people-data-collector` | `people-data-integration` | `data/raw/*`, `data/reference/*` (§1, §2) |
| 02 cleanse | `people-data-cleanser` | `people-data-cleansing` | `data/clean/*` (§3) |
| 03 stats | `headcount-statistician` | `headcount-stats` | `data/stats/headcount-stats.json` (§4-1) |
| 04 forecast | `headcount-forecaster` | `month-end-forecast` | `data/stats/month-end-forecast.json` (§4-2) |
| 05 attrition | `attrition-risk-scorer` | `attrition-risk` | `data/stats/attrition-risk.json` (§4-3) |
| 06 payroll | `payroll-close-analyst` | `payroll-close` | `data/stats/payroll-close.json` (§10) |
| 07 onboarding | `onboarding-plan-analyst` | `onboarding-plan` | `data/stats/onboarding-plan.json` (§11) |
| 08 personas | `persona-needs-analyst` | `persona-needs` | `personas/persona-needs.json` (§9) |
| 09 products | `product-builder` ×3 | `product-build` | `site/{insight,payroll,onboard}/index.html`, `site/data/*.json`, `site/index.html` (§5) |
| 09b judge | `product-judge` ×3 (payroll / onboarding / head-of-hr 옹호자) | `product-judge` | `_workspace/judging/*.json` → `products/product-comparison.json` (§12) |
| 09c unify | `unified-product-builder` | `product-build` + `product-evolution` | `site/app/index.html`, `site/data/app.json`, `products/CHANGELOG.md` (§15, §16) |
| 10 report | `monthly-report-mailer` | `monthly-report` | `reports/*`, `data/stats/automation-effect.json` (§6, §8) |
| 11 test | `people-data-auditor` | (tests/) | `python3 -m unittest discover -s tests` 결과 |
| 12 deploy | `release-engineer` | — | `site/config.js`, `supabase/*` — **승인 gate** |
| 13 evolve | `unified-product-builder` + `product-judge` | `product-evolution` | 인풋 → 재채점 → 재빌드 → CHANGELOG |
| 14 api | `api-integrator` | `function-call-api` | `api/tools.json`(도구 카탈로그) · `api/server.py`(HTTP) · `api/mcp_server.py`(MCP) · `site/api/*.json`(정적) · `_workspace/api-demo.md` (§17) — 급여·온보딩·인사 총괄 **시스템의 agent가 Function Call로 호출**하는 본체 |

공유 정책(전 에이전트): `handoff-log-policy`, `reconciliation-policy`, `pii-minimization-policy`, `approval-gate-policy`, `claims-boundary-policy`(구현/목업/승인 대기 구분·실행자 공통 조건·결과 6단 서식).

## 워크플로우

### Phase 0: 컨텍스트 확인 (초기 / 후속 / 부분 재실행)

1. `_workspace/run_meta.json`과 `data/clean/` 존재를 확인한다.
   - 둘 다 없음 → **초기 실행** (Phase 1부터)
   - 있음 + 부분 수정 요청("예측만", "제품만", "재채점") → **부분 재실행**: 해당 단계와 그 하류만. 상류 산출물은 그대로 읽는다
   - 있음 + 새 입력(고객사가 새 원천 파일 제공, TO 변경, 기준일 변경) → 기존 `_workspace/`를 `_workspace_{YYYYMMDD-HHMM}/`로 옮기고 **새 실행**
   - `products/inputs/*.json`에 처리되지 않은 페르소나 인풋이 있음 → Phase 13 진화 루프
2. 하류 의존: collect→cleanse→{stats, attrition}→forecast→{payroll, onboarding}→products→judge→unify→report→test. 상류가 바뀌면 하류 전부 재실행이 원칙(reconciliation-policy).
3. 새 runId를 만들어 `_workspace/run_meta.json`에 기록하고 단계마다 `durations`를 갱신한다.

### Phase 1: 데이터 계층 (①②③) — 결정적 스크립트, 에이전트는 실행·검증·판독

순서대로 실행한다. 각 스크립트는 마지막 stdout 줄에 요약 JSON을 낸다. 실패 코드가 나오면 그 단계에서 멈추고 핸드오프 로그의 `## 실패한 것`을 채운 뒤 사용자에게 보고한다.

```bash
ROOT=/Users/yang/development/zero-hr; AS_OF=2026-09-23
python3 $ROOT/.claude/skills/people-data-integration/scripts/generate_synthetic_sources.py --root $ROOT --as-of $AS_OF --self-check
python3 $ROOT/.claude/skills/people-data-cleansing/scripts/cleanse.py --root $ROOT --as-of $AS_OF
python3 $ROOT/.claude/skills/headcount-stats/scripts/compute_stats.py --root $ROOT --as-of $AS_OF
python3 $ROOT/.claude/skills/attrition-risk/scripts/score_attrition.py --root $ROOT --as-of $AS_OF
python3 $ROOT/.claude/skills/month-end-forecast/scripts/forecast.py --root $ROOT --as-of $AS_OF
python3 $ROOT/.claude/skills/payroll-close/scripts/payroll_close.py --root $ROOT --as-of $AS_OF
python3 $ROOT/.claude/skills/onboarding-plan/scripts/onboarding_plan.py --root $ROOT --as-of $AS_OF
```

고객사 실데이터가 들어오면 1행(생성기)만 "파일 복사"로 바뀌고 나머지는 동일하다 — 그것이 데모와 실서비스의 유일한 차이다.

**게이트 1(대사):** `headcount-stats.totals` = 재직 406 / 휴직 21 / TO 422 / gap −16, `month-end-forecast.totals.forecastMonthEnd` = 411 / gap −11 (데모 정본 §2-7). 실데이터면 정본 대신 정제 마스터 독립 재계산과 대조한다.

### Phase 2: 페르소나 니즈 (08)

`persona-needs-analyst`를 1회 호출한다(3 페르소나를 한 에이전트가 종합하는 편이 `shared.conflicts`를 잡기 쉽다). 이미 `personas/persona-needs.json`이 있고 인풋 변경이 없으면 건너뛴다.

### Phase 3: 제품 3종 (09) — 병렬 서브에이전트 3

단일 메시지에서 `product-builder` 3개를 병렬 호출한다. 프롬프트에 반드시 넣는 것: 제품 코드(insight/payroll/onboard), 담당 페르소나, 니즈 데이터 경로, 스냅샷 조립 명령(`build_snapshots.py --product {code} --embed`), `product-specs.md`의 해당 절, PII 규칙, 반환 스키마(`product-builder.md` 구조화 출력). 허브(`site/index.html`)는 insight 빌더가 함께 만든다.

### Phase 4: 심판 패널 (09b) — 병렬 3 + 결정적 집계

1. 세 제품이 모두 있을 때만 시작한다(배리어 정당: 심판은 상호 비교한다).
2. `product-judge`를 `persona=payroll`, `persona=onboarding`, `persona=head-of-hr`로 병렬 3 호출. 각자 `_workspace/judging/{persona}.json`을 쓴다.
3. `python3 .claude/skills/product-judge/scripts/aggregate_judgments.py --root $ROOT` → `products/product-comparison.json`.
4. `build_snapshots.py --product comparison --embed`로 허브에 비교 결과를 내장한다.

### Phase 5: 통합 제품 + 변경 이력 (09c)

`unified-product-builder` 1회. 입력: `products/product-comparison.json`(bestFit·strengths·mustFix), 제품 3 페이지, 니즈 데이터. 출력: `site/app/index.html`, `site/data/app.json`, `products/CHANGELOG.md` v1.0 항목(근거 = 심판 점수). 심판의 `mustFix`는 통합 제품에서 반드시 해소한다.

### Phase 5b: Function Call 인터페이스 (14)

`api-integrator` 1회(제품 3종과 병렬 가능 — 같은 `data/stats`를 읽는다). 산출: 도구 카탈로그 18개(payroll.* / onboarding.* / insight.* / report.* / approval.*), HTTP·MCP 서버, 정적 `site/api/`, `tests/test_api.py`, 데모 호출 기록. 세 페르소나의 fit 기준(H-F15·P-F14·O-F13)은 이 산출물로 심판이 판정한다.
스크립트 순서(재실행 시): `python3 api/build_catalog.py` → `python3 api/build_static.py --root $ROOT` → `python3 -m unittest tests.test_api`.

### Phase 5c: 채택 근거 페이지 (09d)

`unified-product-builder`가 통합 제품 직후 `site/decision/index.html`(§18)을 만든다: `build_snapshots.py --product decision --embed`. 사용자 요구 — "어떤 기준으로 최종 서비스를 채택했는지 과정과 설득"을 루브릭 항목 단위로 화면에 보인다. 허브·app 헤더에서 링크.

### Phase 6: 리포트 (10) → 검증 (11)

```bash
python3 $ROOT/.claude/skills/monthly-report/scripts/automation_effect.py --root $ROOT --as-of $AS_OF
python3 $ROOT/.claude/skills/monthly-report/scripts/render_report.py --root $ROOT --as-of $AS_OF
python3 -m unittest discover -s $ROOT/tests -v
```
`people-data-auditor`가 테스트 결과를 판독하고 경계면(통계↔예측↔급여↔온보딩↔스냅샷↔리포트)을 교차 비교한다. 실패는 상류 단계로 돌려보내고 재실행한다.

### Phase 7: 배포 준비 (12) — 승인 gate

`release-engineer`가 배포 산출물과 명령을 준비만 한다. 실제 GitHub push·Supabase 적재·Vercel 배포·이메일 발송은 사용자가 이 세션에서 명시적으로 승인한 뒤에만 실행한다. 세션 내 시연은 Artifact(비공개 링크)로 대체할 수 있다.

### Phase 8: 종합 보고

보고 서식은 `claims-boundary-policy` §5의 6단(상태/범위/결론/근거·검산/예외/결정 요청)을 따른다. 사용자에게 보고할 것: Executive Snapshot 8개 수치, 조직별 권고(채용 가속/TO 재검토), 클린징 요약(17/31/8·미해결 건수), 제품 3종 fit 점수와 bestFit, 통합 제품 링크, 리포트 dispatch 상태(ready-to-send), 테스트 결과, 누락·미검증 항목(침묵 절단 금지), 승인이 필요한 다음 액션.

### Phase 13: 진화 루프 (product-evolution)

`products/inputs/{persona}-{date}.json`이 새로 들어오면: `validate_input.py` → 니즈 데이터 갱신(persona-needs-analyst) → 심판 재채점(Phase 4) → 통합 제품 재빌드(Phase 5) → `changelog.py`로 버전 +0.1(구조 변경이면 +1.0) → `_workspace/handoff/13-evolve.md`.

## 데이터 전달 프로토콜

- **파일 기반이 기본.** 모든 단계는 계약 §0의 경로에 도메인 이름으로 쓴다(에이전트 이름을 파일명에 넣지 않는다).
- 서브에이전트 반환값은 각 에이전트 정의의 `## 구조화 출력` JSON. 오케스트레이터는 그 JSON의 `status`·`reconciliation`·`gaps`만 읽고 파일을 다시 열지 않는다.
- 핸드오프 로그 `_workspace/handoff/{NN-단계}.md`는 다음 에이전트의 첫 입력이다.

## 에러 핸들링

| 상황 | 전략 |
|---|---|
| 스크립트 종료 코드 ≠ 0 | 1회 재시도 없이 즉시 멈춤(결정적 스크립트는 재시도해도 같다). stderr를 핸드오프 로그 `## 실패한 것`에 남기고 담당 에이전트에게 수정 지시 |
| 게이트 1 대사 불일치 | 하류로 내려가지 않는다. 생성기(데모) 또는 클린징 규칙을 의심하고 `injected-defects` ↔ `cleansing-log` 재현율부터 확인 |
| 제품 빌더 1개 실패 | 나머지 2개로 심판을 진행하지 않는다(비교가 무의미). 실패 빌더만 재호출 |
| 심판 1명 무응답 | 2명 결과로 `panelScore`를 내되 `judges[]`에 결손 명시. 통합 제품은 진행 |
| 상충 수치(브리프 215/119/62 vs 조직표 220/128/48) | 삭제하지 않고 `dataQuality.briefDiscrepancies`에 병기, 리포트 데이터 품질 절에 기록 |
| 승인 없는 외부 액션 요청 | 실행하지 않고 "준비 완료" 산출물 + 실행 명령을 제시 |

## 테스트 시나리오

**정상 흐름:** 초기 실행 → Phase 1 스크립트 7개 통과(게이트 1: 406/21/422/−16/19/14/411/−11) → 니즈 데이터 → 제품 3 병렬 → 심판 3 병렬 → 비교 JSON(bestFit) → 통합 제품 → 리포트 ready-to-send → 테스트 전부 통과 → 종합 보고.

**에러 흐름:** 클린징 후 `orgNameCorrections`가 17이 아닌 15 → 게이트 1 앞에서 멈춤 → `injected-defects.json`의 org-* 17건과 `cleansing-log.jsonl`의 org-* 규칙 건수를 대조 → 매칭 규칙(편집거리·`&`↔`and`) 보정 → 클린징만 재실행 → 하류 전부 재실행.

**부분 재실행:** "TO가 바뀌었어, Engineering 112→118" → `data/raw/to-plan.csv` 수정 → cleanse부터 하류 재실행(stats/forecast/payroll/products/judge/unify/report) → CHANGELOG에 "TO 변경 반영" 항목.
