---
name: product-evolution
description: "진화 루프(evolution) — 새 페르소나 또는 기존 페르소나의 새 요구가 페르소나 인풋(products/inputs/{persona}-{YYYY-MM-DD}.json, DATA_CONTRACT §16)으로 들어오면 제품을 진화시키는 절차: scripts/validate_input.py로 인풋 검증(evidence가 계약 경로인지, 아니면 backlog.md 적재) → personas/persona-needs.json 갱신 → 심판(product-judge) 재채점·aggregate(--archive-as로 이전 버전을 products/history/에 보관) → 통합 제품(unified-product-builder) 재빌드 → scripts/changelog.py로 products/CHANGELOG.md 항목(버전 v{major}.{minor}: 심판 라운드 minor+1, 통합 재구성 major+1, 근거·영향 fitCriteria id) → 핸드오프 로그 13-evolve. '새 페르소나가 들어왔다', '인풋 반영', '페르소나 인풋 검증', '요구 추가', '재채점하고 제품 업데이트', '제품 진화', '변경 이력/CHANGELOG 남겨', '버전 올려', 'products/inputs', 'backlog' 요청과 인풋 후 '다시/재실행/수정/보완/업데이트/재채점/재빌드' 시 반드시 이 스킬을 사용한다. 하네스 자체의 회고·개선은 harness:evolve(다른 것)."
---

# product-evolution — 인풋이 들어오면 제품이 진화한다

## 왜 이 스킬인가
제품은 고정물이 아니다(§16). 데모의 세 페르소나는 출발점이고, 고객사에는 재무 통제·조직장·법무처럼 다른 질문을 가진 사람이 있다.
그들의 요구를 **채팅으로 받아 손으로 화면을 고치면** 두 가지가 사라진다 — 왜 바뀌었는지(근거)와 그 변경이 기존 페르소나의 fit을 얼마나 깎았는지(점수).
그래서 인풋은 파일이고, 니즈 데이터를 거치고, 심판이 다시 채점하고, 그 델타가 변경 이력이 된다. 진화 루프는 harness `evolve`(하네스 개선)와 다르다 —
이것은 **제품**의 진화다.

## 산출물과 소비자
| 산출물 | 경로 | 소비자 |
|---|---|---|
| 페르소나 인풋 | `products/inputs/{persona}-{YYYY-MM-DD}.json` (사용자·에이전트가 넣음) | `scripts/validate_input.py` |
| 백로그 | `products/inputs/backlog.md` (계약 밖 evidence) | 계약 관리자(harness 스킬로 DATA_CONTRACT 확장) |
| 갱신된 니즈 | `personas/persona-needs.json` (페르소나 추가/갱신) | product-judge, product-builder, unified-product-builder |
| 이전 비교 보관 | `products/history/{version}.json` | `changelog.py add --before` |
| 새 비교 | `products/product-comparison.json` | unified-product-builder, hub refresh |
| 변경 이력 | `products/CHANGELOG.md` (+ `changelog.py export` → `site/data/app.json.changelog`) | 통합 제품 화면, 사용자 |
| 핸드오프 | `_workspace/handoff/13-evolve.md` | 다음 라운드 |

## 절차 (한 인풋 = 한 라운드)

### 0. 현재 버전을 읽는다
```bash
python3 .claude/skills/product-evolution/scripts/changelog.py current        # 예: v1.0 (없으면 none)
```

### 1. 인풋 검증
```bash
python3 .claude/skills/product-evolution/scripts/validate_input.py products/inputs/finance-controller-2026-09-23.json
```
- 스키마(§16): `persona`(kebab-case) · `title` · `submittedAt`(YYYY-MM-DD) · `source`(interview|survey|ticket|agent) · `needs[{id,need,importance 1~5}]` · `fitCriteria[{id,criterion,weight 1~5,evidence}]` · `rubric{lens,scoring}`
- evidence 접두가 계약 경로(§3~§12, `site/`, `reports/`, `policy:`, `reconciliation:`)면 통과. **아니면 거절하지 않고** `products/inputs/backlog.md`에 "계약 확장 필요"로 적재하고 그 기준은 이번 라운드에서 뺀다 — 계약 밖 evidence를 채점하면 심판이 `unverifiable`만 내기 때문이다
- 종료 코드 1(스키마 위반)이면 여기서 멈추고 오류를 인풋 제출자에게 되돌린다. `warnings`(파일명 규약·id 접두)는 진행한다

### 2. 니즈 데이터 갱신 (`persona-needs-analyst`)
- 새 페르소나: `personas[]`에 §9 객체를 추가한다. 인풋의 `needs`→`goals`/`jobsToBeDone`, `fitCriteria` 그대로, `rubric`은 심판 루브릭의 출발점. `product`는 가장 가까운 기존 제품 코드(재무 통제 → `payroll` 등) 또는 `app`
- 기존 페르소나의 새 요구: 해당 페르소나의 `fitCriteria`에 추가/갱신(id는 유지, 새 id는 이어서). `shared.conflicts`를 다시 본다(예: 재무는 집계만 vs 급여는 성명 필수)
- 시간 예산(`pains` 합 40h)이 바뀌면 `automation-effect`와의 대사에 영향 — `contractGaps`로 적는다

### 3. 심판 재채점 (`product-judge` ×N + aggregate)
- 새 페르소나에는 `.claude/skills/product-judge/references/rubric-{persona}.md`가 있어야 심판 인스턴스가 뛴다. 없으면 인풋의 `rubric.lens/scoring`으로 **먼저** 루브릭 파일을 만든다(앵커 0/3/5/8/10, must/nice, 실격 조건 — 기존 세 루브릭 형식). 이것은 `harness` 스킬 범위의 파일 추가이므로 사용자 확인 후 만든다
- 기존 세 심판 + 새 심판을 병렬로 재실행 → 이전 비교를 보관하며 병합:
```bash
python3 .claude/skills/product-judge/scripts/aggregate_judgments.py --archive-as $(python3 .claude/skills/product-evolution/scripts/changelog.py current) [--allow-partial]
```
  (`--allow-partial`은 새 심판이 아직 없을 때 3명으로 병합)
- **심판 라운드가 끝나면 minor 버전 항목을 남긴다**:
```bash
python3 .claude/skills/product-evolution/scripts/changelog.py add --kind judge --summary "재무 통제 페르소나 인풋 반영 — 심판 재채점" \
  --input products/inputs/finance-controller-2026-09-23.json --criteria FC-F1,FC-F2,FC-F3 \
  --before products/history/v1.0.json --after products/product-comparison.json
```

### 4. 통합 제품 재빌드 (`unified-product-builder`, `kind: rebuild`)
- `bestFit`이 바뀌었거나 새 역할 탭이 생기면 통합 제품 재구성이다 → `--kind rebuild`(major +1). bestFit이 같고 섹션만 늘면 빌더가 판단해 `judge` 라운드의 일부로 둔다(항목 추가 없음, 3절 항목의 `--basis`에 "통합 제품 섹션 N개 추가")
```bash
python3 .claude/skills/product-evolution/scripts/changelog.py add --kind rebuild --summary "bestFit insight→payroll — 통합 제품 골격 교체, finance 탭 추가" \
  --input products/inputs/finance-controller-2026-09-23.json --criteria FC-F1,P-F1 --after products/product-comparison.json
```
- 통합 빌더는 `changelog.py export`를 `site/data/app.json.changelog`에 싣는다 — 화면의 "변경 이력" 섹션이 이 라운드를 보여 준다

### 5. 검증·핸드오프
- `people-data-auditor`(scope `products`)로 새 비교·통합 제품·PII를 검사한다
- `_workspace/handoff/13-evolve.md`(5절): 시도(인풋 파일·버전 before→after)/근거(validate 결과·심판 델타)/실패(backlog 적재 항목·unverifiable)/검증(감사 결과)/다음 인계점(계약 확장 필요 항목, 승인 대기 배포)

## 버전 규칙 (§16 — `changelog.py`가 강제한다)
| 상황 | kind | 버전 | 예 |
|---|---|---|---|
| 첫 심판 라운드(초기 3제품 비교) | judge | v1.0 | 초기 구축 |
| 첫 통합 제품 | rebuild | (이미 v1.0이면) v2.0 · 아니면 v1.0 | 초기 통합 |
| 인풋 후 재채점 | judge | minor +1 | v2.0 → v2.1 |
| bestFit 변경·탭 추가·골격 교체 | rebuild | major +1, minor 0 | v2.1 → v3.0 |
| 스냅샷만 갱신(데이터 재실행) | — | 항목 없음 | 제품이 바뀐 게 아니다 |

## 스크립트 요약
- `scripts/validate_input.py {input} [--root] [--backlog products/inputs/backlog.md] [--no-backlog] [--strict]` → stdout JSON `{valid, errors[], warnings[], evidence[{id,evidence,prefix,known,contract,resolved}], backlogged[], backlogFile}`. 종료 0 유효 / 1 무효 / 2 파일 오류
- `scripts/changelog.py add --kind judge|rebuild --summary S [--input P] [--criteria A,B] [--basis B]* [--before P] [--after P] [--date D] [--section] [--dry-run]` → `{version, previous, kind, section, path, criteria}` · `export` → JSON 배열 `[{version, date, entries[{kind, section, summary, basis[], criteria[]}]}]` · `current` → `vX.Y` | `none`

## 하지 않는 것
- 인풋을 채팅에서 바로 화면 수정으로 옮기지 않는다(파일 → 니즈 → 심판 → 빌드 순서) · CHANGELOG를 손으로 쓰지 않는다 · 계약 밖 evidence를 채점하지 않는다(backlog) · 하네스 파일(에이전트·정책)을 고치지 않는다 — 그건 `harness:evolve`
