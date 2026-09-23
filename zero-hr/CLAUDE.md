# Zero Company HR — Everyday People Agent

Zero Company는 agent가 회사의 반복 운영 기능을 수행하고 사람이 미션·판단·관계를 담당하는 **agent-native company OS**다.
첫 제품 Zero Company HR(브랜드: Everyday People Agent)은 HR Operations Agent Platform — Workday처럼 HR 데이터를 다루되 agent가 집계·분석·예측·대시보드·리포트를 직접 수행한다.
형상 정본: `zero-company/zero_company_external_brief.md` (Operating Rules R1~R5: 역할 / 중간 발견·실패 로그 공유 / 하네스 분할 / 사람의 승인 gate / 재사용 자산).
고객사(사람이 있는 회사)의 인원현황 마스터·TO 계획·입퇴사 예정 데이터를 받아
**실시간 HR 리포트(인원 통계 + 조직별 인원 예측)**를 무인으로 생산·배포한다.

- Zero Company 형상: `zero-company/` (브리프 원문 + ZERO_COMPANY_OS.md 정리본 + DR). 이 하네스가 곧 회사의 운영 조직(데모 4역할 + owner)이다
- 기대 효과 4종(완전 자동화·실시간 조회·선제 대응·자동 배포)의 증빙: `.claude/DATA_CONTRACT.md` §8
- 공유 언어: `.claude/GLOSSARY.md` · 데이터 정본: `.claude/DATA_CONTRACT.md`
- 결정 기록: `zero-company/DR-*.md` (말로 하는 결정은 없다)

## 하네스: 실시간 HR 리포트

**목표:** 고객사 원천 데이터 4종 → 클린징 → 인원 통계·월말 인원 예측·이직 리스크·급여 마감·온보딩 계획 → 페르소나 니즈 → 제품 3종 → 심판 3명 채점 → 통합 제품(app) + 월초 리포트 + 변경 이력을 한 번의 워크플로우로 생산한다.

**트리거:** HR 리포트, 인원 통계, 인원현황, TO 과부족, 월말 인원 예측, 입퇴사 예정, 이직 리스크, 급여 마감, 온보딩 계획, HR 대시보드, 권한별 대시보드, 월초 리포트, 제품 3종 비교, 심판/채점, 통합 제품, 페르소나 인풋/진화, '다시 실행/재실행/업데이트/수정/보완/재채점' 관련 작업 요청 시 `zerohr-orchestrator` 스킬을 사용하라. 새 페르소나 인풋(`products/inputs/*.json`) 반영은 그 안의 Phase 13(`product-evolution`). 하네스 자체의 회고·개선은 `harness:evolve`. 단순 질문(용어 정의, 파일 위치)은 직접 응답 가능.

**실행 환경 제약:** Python 3.9 표준 라이브러리만(pandas 없음). 외부 발신·배포·영구 스케줄은 승인 gate(사람) — 산출물은 "발송/배포 준비 완료"까지 만들고 사용자 승인 후 실행한다. 모든 단계는 `_workspace/handoff/`에 핸드오프 로그를 남긴다.

**변경 이력:**
| 날짜 | 변경 내용 | 대상 | 사유 |
|------|----------|------|------|
| 2026-09-23 | 초기 구성 (harness v2, 워크플로우 모드) | 전체 | Fable 5.1 Build Day — Everyday 테마 과제 |
| 2026-09-23 | 용어집·데이터 계약 v2 (브리프 정본 채택: 4그룹·11조직, 레벨 IC1~VP, 재직 406/휴직 21/TO 422, 제품명 Everyday People Agent, 조직장 뷰, 핸드오프 로그·승인 gate 정책) | GLOSSARY, DATA_CONTRACT, 전 스크립트(정렬 패스) | 사용자 제공 zero_company_external_brief.md |
| 2026-09-23 | 스크립트 9종 v2 정렬 재작성(생성기·클린저·통계·예측·리스크·급여·온보딩·리포트·스냅샷) + 테스트 6종 + 데이터 생성·게이트 1 통과(406/21/422/−16/19/14/411/−11) | 전 스크립트, tests/, data/ | v1(본부>실>팀) 잔재로 브리프 수치 불일치 |
| 2026-09-23 | 오케스트레이터 `zerohr-orchestrator`(13+1단계 하이브리드), 에이전트 7종 추가(collector·cleanser·mailer·judge·auditor·release·unified-builder), 정책 4종, 심판·진화 스킬, 계약 §15(통합 제품)·§16(변경 이력·인풋) | .claude/skills, .claude/agents, DATA_CONTRACT | 제품 3종 → 심판 3명 → 통합 제품 → 진화 루프(사용자 5단계 가이드라인) |
| 2026-09-23 | 외부 에이전트팀 산출물 3건 선별 채택 → `claims-boundary-policy`, `tests/test_logic_risks.py`, 행별 항등식 테스트, 재무팀장 인풋(진화 루프 첫 인풋) | 정책·tests·products/inputs | DR-004, `_workspace/external-review/REVIEW.md` |
| 2026-09-23 | Function Call 인터페이스 §17 + `api-integrator` + `function-call-api` 스킬 + 페르소나 fit 기준 3건(H-F15·P-F14·O-F13) | DATA_CONTRACT, api/, personas | 사용자 요구: 급여·온보딩·인사 총괄 시스템의 agent가 도구로 호출 |

**제품 3종(페르소나 fit):** Everyday People Agent — Insight(인사 총괄, 권한별 뷰 4종) · Payroll Close(급여 담당) · Onboarding(온보딩 담당). 니즈 데이터 `personas/persona-needs.json` → 제품 → `products/product-comparison.json` 비교.

**배포 파이프라인:** 로컬 테스트(`python3 -m unittest discover -s tests`) → GitHub 커밋 → Supabase 적재·검증(`supabase/`) → Vercel 정적 배포(`site/`).
