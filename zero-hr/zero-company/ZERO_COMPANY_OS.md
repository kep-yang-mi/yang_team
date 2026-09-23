# Zero Company OS — 형상 정리본 (하네스 매핑)

원문: `zero_company_external_brief.md` (사용자 제공, 2026-09-23). 이 문서는 원문을 바꾸지 않고, 원문의 개념이 이 저장소의 **어느 파일·어느 agent로 구현되는지**를 한 장에 매핑한다.
용어는 `.claude/GLOSSARY.md`, 데이터 정본은 `.claude/DATA_CONTRACT.md`.

## 1. 한 줄 정의

**Zero Company = agent가 회사의 반복 운영 기능을 수행하고, 사람이 미션·판단·관계를 담당하는 agent-native company OS.**
첫 spin-off = **Zero Company HR (제품 브랜드 Everyday People Agent)** — Workday처럼 HR 데이터를 다루되, agent가 데이터 통합·클린징·분석·리포트 배포까지 직접 수행하는 HR Operations Agent Platform.

## 2. Company OS 6층 ↔ 저장소

| OS 층 | 뜻 | 이 저장소에서의 구현 |
|---|---|---|
| Mission | 회사가 존재하는 이유 | `CLAUDE.md` 상단 3줄, 브리프 §2 |
| Rules | agent들이 함께 일하는 운영 규칙 R1~R5 | 정책 스킬 4종 `.claude/skills/{handoff-log,reconciliation,pii-minimization,approval-gate}-policy/` |
| Role | 역할을 가진 agent | `.claude/agents/*.md` (14 역할) — 각 파일이 역할·입력·산출·완료 기준을 가진다 (R1) |
| Workflow | 역할들이 협업하는 순서 | `.claude/skills/zerohr-orchestrator/SKILL.md` (owner agent) + 각 역할 스킬 `.claude/skills/*/SKILL.md` |
| Memory | 중간 발견·실패·결정의 기록 | `_workspace/handoff/NN-단계.md` (R2), `_workspace/run_meta.json`, `zero-company/DR-*.md`, `products/CHANGELOG.md` |
| Human Gate | 사람이 결정하는 지점 | `approval-gate-policy`: 외부 발송·배포·채용/해고·민감정보·지출·법적·조직 변경 → agent는 "준비 완료"까지 (R4) |

## 3. 브리프 §3 R3의 데모 4역할 ↔ 하네스 agent

| 브리프 역할 | 하네스 agent | 스킬 | 산출 (R5 재사용 자산) |
|---|---|---|---|
| 데이터 통합 agent | `people-data-collector` | `people-data-integration` | 원천 4종 CSV + 조직 체계 + 주입 결함 정답지 |
| 클린징 agent | `people-data-cleanser` | `people-data-cleansing` | 정제 CSV 4종 + 클린징 로그(jsonl) + 요약 |
| 분석 agent | `headcount-statistician` · `headcount-forecaster` · `attrition-risk-scorer` · `payroll-close-analyst` · `onboarding-plan-analyst` | 각 동명 스킬 | 인원 통계 · 월말 예측 · 이직 리스크 · 급여 마감 · 온보딩 계획 (JSON) |
| 배포 agent | `product-builder` ×3 · `unified-product-builder` · `monthly-report-mailer` · `release-engineer` | `product-build` · `product-evolution` · `monthly-report` | 제품 HTML 4종(권한별 뷰) + 월초 이메일 md/html + dispatch 명세 |
| owner agent | `zerohr-orchestrator`(스킬) + `people-data-auditor` · `product-judge` ×3 | `zerohr-orchestrator` · `product-judge` | 종합 보고 · 테스트 결과 · 제품 비교 |
| (제품 발견) | `persona-needs-analyst` | `persona-needs` | 페르소나 3종 니즈 데이터 |

## 4. 서비스 개발 프로세스 (사용자 가이드라인 5단계) ↔ 구현

| 단계 | 구현 |
|---|---|
| 1. 프러덕트 3개를 만들어 비교 | Insight(인사 총괄) / Payroll Close(급여 담당) / Onboarding(온보딩 담당) — `site/{insight,payroll,onboard}/` |
| 2. 페르소나 니즈를 데이터로 산출, fit에 맞춰 제작 | `personas/persona-needs.json`(JTBD·KPI·통증점·fit 기준·루브릭) → 각 제품 섹션에 `data-fit` 표기 |
| 3. 3명의 agent가 각자의 루브릭으로 평가 | `product-judge` ×3 (`persona-advocate:{payroll,onboarding,head-of-hr}`) + `rubric-{persona}.md` → `products/product-comparison.json` |
| 4. 평가에 따라 하나의 제품 | `unified-product-builder` → `site/app/` (승자 골격 + 차점 강점, 역할 탭 6종) |
| 5. Changelog + 다른 페르소나 인풋으로 진화 | `products/CHANGELOG.md` + `products/inputs/{persona}-{date}.json` → `product-evolution` 스킬 루프 |

## 5. 기대 효과 ↔ 증빙

| 기대 효과 | 증빙 파일 |
|---|---|
| 월 리포트 수작업 → 완전 자동화(80%) | `_workspace/run_meta.json` durations · `data/stats/automation-effect.json` |
| 경영진 실시간 조회 | `site/app/index.html?role=executive` (스냅샷 내장, Supabase 덮어쓰기 옵션) |
| 인력계획 선제 대응 | `data/stats/month-end-forecast.json` (권고·인사이트·시나리오 플래너·리스크 반영) |
| 월간 리포트 자동 생성·배포 | `reports/monthly-report-2026-10.{md,html}` + `monthly-report-dispatch.json`(ready-to-send) |

## 6. 데모와 실서비스의 차이

단 하나: 01 collect 단계에서 **가상 원천 생성기**가 **고객사 파일 복사**로 바뀐다. 이후 12단계는 동일하다. 그래서 가상 데이터에 결함을 의도적으로 주입하고 정답지를 남긴다 — 클린징 규칙이 실데이터에서도 동작함을 미리 증명하기 위해서다.
