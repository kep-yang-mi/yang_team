# 도메인 용어집: Zero Company HR — Everyday People Agent (v2, 브리프 정본 반영)

이 하네스의 모든 에이전트·스킬·스키마·산출물 경로는 이 문서의 용어만 사용한다.
용어를 바꾸면 관련 이름도 함께 바꾼다. 데이터 컬럼·JSON 필드의 정확한 정의는 `.claude/DATA_CONTRACT.md`(v2)가 정본이다.
회사 형상의 정본은 `zero-company/zero_company_external_brief.md`(사용자 제공)이며, 이 용어집은 그 문서의 어휘를 따른다.

## 회사 컨텍스트 (Zero Company OS)

| 용어 | 정의 | 표기 | 비고 |
|------|------|------|------|
| Zero Company | agent가 회사의 반복 운영 기능을 수행하고 사람이 미션·판단·관계를 담당하는 **agent-native company OS**. 미션: 누구나 작은 팀으로도 완전한 회사를 설립·운영·확장할 수 있게 한다 | `zero-company` | 정본: 브리프 §1~§3 |
| Company OS 상위 레이어 | Mission · Rules · Role · Workflow · Memory · Human Gate — 회사를 구성하는 6개 층. 이 하네스에서 Mission=CLAUDE.md 상단, Rules=정책 스킬, Role=`.claude/agents/`, Workflow=오케스트레이터+Workflow 스크립트, Memory=`_workspace/`·핸드오프 로그·DR, Human Gate=승인 gate 정책 | `os-layers` | |
| Operating Rules | 브리프 §3의 규칙: R1 모든 agent는 역할을 가진다 / R2 중간 발견과 실패 로그를 공유한다 / R3 하네스 방식으로 복잡한 업무를 나눈다 / R4 사람은 승인 gate를 담당한다 / R5 모든 결과는 재사용 가능한 자산으로 남긴다 / R6(제안) 완료 기준은 사전 정의된 지표로만 판단한다 | `operating-rules` | R6는 브리프 R1의 "완료 기준" 조항을 독립 규칙으로 승격한 제안 — 사용자 원문 확인 필요 |
| 첫 제품 | **Zero Company HR — Everyday People Agent.** HR Operations Agent Platform: Workday처럼 HR 데이터를 다루지만 HRIS가 아니라 agent가 HR 운영 업무(집계·분석·예측·대시보드·리포트)를 직접 수행한다 | `everyday-people-agent` | 제품 브랜드 = Everyday People Agent, 플랫폼명 = Zero Company HR |
| 고객사 | 제품을 쓰는 (사람이 있는) 회사. 데모 고객사는 가상 기업 **㈜온다테크**(영문 조직명을 쓰는 IT 스타트업, 재직 406·휴직 21) | `client` | |
| 데모 4역할 | 브리프 §3 R3의 역할 분할: 데이터 통합 agent / 클린징 agent / 분석 agent / 배포 agent + owner agent(종합). 이 하네스의 세분 에이전트는 이 4역할에 매핑된다(아래 표) | `demo-roles` | |
| 승인 gate | 사람이 승인해야 하는 행위: 외부 발송, 채용/해고 결정, 민감정보 접근, 재무 지출, 법적 리스크 액션, 조직 구조 변경. agent는 실행·제안까지, 결정은 사람 | `approval-gate` | 정책 `approval-gate-policy` |
| 핸드오프 로그 | R2에 따라 모든 실행자가 남기는 기록: 무엇을 시도했는가 / 어떤 데이터·근거를 봤는가 / 무엇이 실패했는가 / 무엇이 검증됐는가 / 다음 agent가 어디서 이어받는가 | `handoff-log` | 경로 `_workspace/handoff/{단계}.md`, 정책 `handoff-log-policy` |
| 재사용 자산 | R5: md 보고서, CSV/JSON, Dashboard HTML, 실행 로그, 권한별 view, 다음 액션 | `assets` | 모든 단계의 산출물이 이 중 하나여야 한다 |
| 결정 기록 (DR) | 말로 하는 결정은 없다. 제안/근거/옵션/기본안/기한/fallback | `decision-record` | `zero-company/DR-*.md` |
| 기대 효과 | ① 월 리포트 수작업 → 완전 자동화(리소스 80% 절감) ② 경영진 실시간 인원 현황 조회 ③ 인력계획 선제 대응 ④ 월간 리포트 자동 생성·배포 | `expected-effects` | 증빙 DATA_CONTRACT §8 |
| 세션 실행 제약 | Build Day 세션에서 외부 발신·영구 스케줄 등록·배포 자격증명은 사용자 승인/제공이 필요 — 승인 gate와 일치하므로 산출물은 "발송/배포 준비 완료"까지 만든다 | `session-constraint` | |

### 데모 4역할 ↔ 하네스 에이전트 매핑

| 브리프 역할 | 하네스 에이전트 | 산출 |
|---|---|---|
| 데이터 통합 agent | `people-data-collector` | 통합 HR 데이터셋(원천 4종 + 조직 체계) |
| 클린징 agent | `people-data-cleanser` | 정제 데이터 + 클린징 로그 |
| 분석 agent | `headcount-statistician`, `headcount-forecaster`, `attrition-risk-scorer`, `payroll-close-analyst`, `onboarding-plan-analyst` | 인원 통계 + 월말 예측 + 리스크 + 페르소나 파생 |
| 배포 agent | `product-builder`, `monthly-report-mailer`, `release-engineer` | 권한별 대시보드(제품 3종) + 월초 이메일 + 배포 |
| owner agent (종합) | `zerohr-orchestrator`(스킬) + `people-data-auditor`, `product-judge` | 종합·검증·비교 |
| (페르소나) | `persona-needs-analyst` | 니즈 데이터 |

## 핵심 개념 — 데이터 (① 수집·통합)

| 용어 | 정의 | 표기 | 비고 |
|------|------|------|------|
| 인원현황 마스터 | 현재 임직원(재직+휴직) 1인 1행의 기준 데이터. 데모: **427명** | `headcount-master` | 동의어: 인원현황Master 독스, 인사 마스터 |
| TO 계획 | 조직(부서)별 정원. 데모: **11개 조직, 총 422** | `to-plan` | "TO 관리"는 TO 계획을 관리하는 행위 |
| 입사 예정자 | 입사일이 확정된 미래 입사자. 마스터에 없음. 데모: 월말까지 **19명** | `planned-joiners` | |
| 퇴사 예정자 | 퇴사일이 확정된 현재 재직자. 데모: 월말까지 **14명** | `planned-leavers` | 퇴직사유는 여기서만 집계(과거 퇴직 이력은 범위 밖) |
| 조직 체계 | **조직 그룹(4) > 조직(11)** 2단계. Executive{CEO Office} / Build{Product, Engineering, Design, Data & AI} / Go-To-Market{Sales, Marketing, Customer Success} / Operations{People, Finance, Legal & Compliance} | `org-chart` | 조직명은 영문 정규 표기 |
| 원천 데이터 | 고객사에서 받은 그대로의 4종. 표기 불일치·오류 포함 | `raw` | `data/raw/` |
| 가상 원천 생성 | 데모용 원천을 에이전트가 생성. 결함을 의도적으로 주입하고 정답지를 남긴다 | `synthetic-sources` | |
| 주입 결함 정답지 | 주입한 결함의 목록(정답) | `injected-defects` | |

## 핵심 개념 — 클린징 (②)

| 용어 | 정의 | 표기 |
|------|------|------|
| 조직 정규화 | 부서 표기 변형(`Legal and Compliance`→`Legal & Compliance` 등)을 조직 체계의 정규 코드로 매핑 + 4개 조직 그룹 부여 | `org-normalization` |
| 일자 보정 | `YYYY/MM/DD` 등 포맷을 ISO로 통일, 논리 오류 교정 | `date-correction` |
| 표기 정규화 | 성별·고용유형·재직상태·레벨·퇴직사유의 표기 변형을 정규 값으로 | `code-normalization` |
| 중복 해소 | 같은 사번 복수 행 중 최신 행만 | `dedup` |
| 파생 필드 | 클린징에서 만드는 필드: 연령대, 재직기간 구간, 총경력 구간, **스테이지** | `derived-fields` |
| 클린징 로그 | 보정 1건 1행 기록 + 신뢰도 | `cleansing-log` |
| 미해결 항목 | 규칙으로 못 고친 행. 플래그 후 고객사 HR에 확인 질문 | `unresolved` |

## 핵심 개념 — 통계·예측 (③)

| 용어 | 정의 | 표기 | 비고 |
|------|------|------|------|
| 기준일 | **2026-09-23** | `asOfDate` | 월말 2026-09-30, 다음 달 말 2026-10-31 |
| 재직 인원 | 상태 재직인 인원. **TO 비교·예측의 기준** | `activeHeadcount` | 데모 406 |
| 휴직 인원 | 상태 휴직 | `onLeave` | 데모 21 |
| 총원 | 재직 + 휴직 (마스터 행 수) | `headcount` | 데모 427 |
| 재직상태 | 재직 / 휴직 | `status` | 휴직유형: 육아휴직·질병휴직·기타 |
| 고용유형 | 정규직 / 계약직 / 인턴 / 파견 | `employmentType` | 총원 기준 354/31/19/23 |
| 성별 | 여성 / 남성 / 미응답 | `gender` | |
| 연령대 | 20대 / 30대 / 40대 / 50대+ | `ageBand` | |
| 직군 | Engineering / Product / Design / Sales / Marketing / Customer Success / People / Finance / Legal / Data/AI / Executive | `jobFamily` | 조직과 다를 수 있다(Data & AI 조직에 Engineering 직군 등) |
| 레벨 | 직책/레벨 사다리: IC1 / IC2 / IC3 / Senior / Lead / Manager / Director / VP | `level` | 브리프 "직책/레벨" |
| 스테이지 | 입사 당시 회사 성장 단계: Seed / Series A / Scale-up / Enterprise. **입사일에서 파생** | `stage` | 경계일은 `data/reference/company-stages.json` |
| 재직기간 | 입사일~기준일 (년) | `tenureYears` | 구간 `tenureBand`: 1년 미만 / 1~3년 / 3~5년 / 5년+ |
| 연차 | floor(재직기간)+1 ("N년차") | `tenureYear` | |
| 총경력 | 입사 전 경력(개월/12) + 재직기간 | `totalExperienceYears` | 구간 `totalExperienceBand`: 0~3년 / 3~7년 / 7~12년 / 12년+ |
| 퇴직사유 | 자발퇴사 / 개인사유 / 계약만료 / 조직개편 / 성과·적합도 / 건강 / 정년 | `separationReason` | 퇴사 예정자에서 집계 |
| 퇴직 구분 | 자발적(자발퇴사·개인사유·건강) / 비자발적(계약만료·조직개편·성과·적합도·정년) | `separationType` | |
| TO 과부족 | 재직 인원 − TO (양수 초과, 음수 부족). 기준일 기준(−16)과 월말 기준(−11) | `toGap` | |
| 월말 인원 예측 | 재직 + 월말까지 입사 예정 − 월말까지 퇴사 예정 = 월말 조직별 인원 | `month-end-forecast` | 406+19−14=411 |
| 권고 | 조직별 예측에 붙는 결정적 판정: 정상 관리 / 채용 가속 / TO 재검토·이동배치 | `recommendation` | 규칙 DATA_CONTRACT §4-2 |
| 인력계획 인사이트 | 권고를 묶은 조치 목록 + 즉시 액션(채용 pipeline 점검, TO 재검토, 퇴사 영향 점검) | `insights` | |
| 시나리오 플래너 | 경영기획 뷰의 what-if: 채용 달성률·추가 이탈 가정을 바꿔 월말 인원을 재계산 | `scenario-planner` | 브리프 §12 고도화 항목 |
| 이직 리스크 | 재직자별 이직 가능성 점수(0~100)·등급. 규칙 기반, 요인 명시 | `attrition-risk` | 예측의 "리스크 반영 시나리오"에 결합 |
| 대사 | 집계가 정제 마스터에서 독립 재계산한 값과 일치하는지 확인 | `reconciliation` | |
| 자동화 효과 | 수작업 대비 절감 공수 추정 + 파이프라인 실행 시간 | `automation-effect` | 추정임을 명시 |

## 핵심 개념 — 페르소나·제품

| 용어 | 정의 | 표기 |
|------|------|------|
| 페르소나 | 고객사 HR의 대표 사용자 3종: 인사 총괄(head-of-hr) / 급여 담당(payroll) / 온보딩 담당(onboarding) | `persona` |
| 니즈 데이터 | 페르소나별 요구의 데이터 표현(목표·JTBD·캘린더·핵심 질문·KPI·통증점·필요 필드·결정·fit 기준) | `persona-needs` |
| 제품 | Everyday People Agent의 앱 3종: **Insight**(인사 총괄 — 실시간 HR 리포트, 권한별 뷰 4종) / **Payroll Close**(급여 담당 — 월말 급여 마감 보드) / **Onboarding**(온보딩 담당 — 입사 예정자 온보딩 보드) | `product` (`insight`/`payroll`/`onboard`) |
| 리포트 뷰 | Insight의 권한별 화면 4종: 경영진 `executive` / HR `hr` / 경영기획 `planning` / 조직장 `orgLead` | `report-views` |
| 공통 데이터 계층 | 3제품이 공유하는 ①②③ 산출물 | `shared-data-layer` |
| 급여 마감 | 급여 담당 파생: 급여 대상 인원(재직·휴직), 일할 계산 대상, 휴직 처리 구분, 계약 만료, 급여 오류 위험 — **급여액은 다루지 않는다** | `payroll-close` |
| 온보딩 계획 | 온보딩 담당 파생: 주차별 입사 타임라인, 조직 배치, 체크리스트, 버디 후보, 90일 코호트, 1년 미만 예정 퇴직 | `onboarding-plan` |
| fit 점수 | 제품의 페르소나 니즈 충족률 + 심판 점수 | `fitScore` |
| 제품 비교 | 3제품의 fit·재사용·고유 기능·공수 비교 | `product-comparison` |
| 허브 | 제품 3 진입 + 비교를 담은 랜딩 | `hub` |
| 월초 리포트 | 매월 1일 09:00 발송 이메일. 제목 `[Zero Company] 2026-09 HR Headcount Forecast` | `monthly-report` |

## 핵심 개념 — 배포·검증

| 용어 | 정의 | 표기 |
|------|------|------|
| 사이트 | Vercel 정적 사이트: 허브 + 제품 3 + 스냅샷 | `site` |
| 데이터 저장소 | Supabase(Postgres) 정제 데이터·스냅샷 테이블 | `datastore` |
| 스냅샷 | 한 실행이 만든 제품별 데이터 JSON | `snapshot` |
| 로컬 테스트 | 대사·계약·결함 재현율·사이트 검사(unittest) | `local-test` |
| 배포 | 로컬 테스트 → GitHub(kep-yang-mi/yang_team) → Supabase → Vercel | `deploy` |

## 관계

- 마스터는 임직원을 여러 명 갖고, 각 임직원은 조직 하나에 속하며, 조직은 조직 그룹 하나에 속한다
- TO 계획은 조직마다 하나. 퇴사 예정자는 마스터의 재직자, 입사 예정자는 마스터에 없다
- 정제 데이터는 원천 + 클린징 로그로 재구성 가능하다(감사 추적). 통계·예측·리스크·파생은 정제 데이터에서만 계산한다
- 월말 인원 예측은 TO 계획과 결합해 TO 과부족과 권고를 만들고, 권고를 묶어 인사이트가 된다
- 세 제품은 같은 공통 데이터 계층을 읽는다 — 같은 지표는 같은 값
- 니즈 데이터 → 제품 → 제품 비교(같은 니즈 데이터로 채점)
- 모든 단계는 핸드오프 로그를 남기고, 외부 발송·배포는 승인 gate를 지난다

## 소리내어 검증

1. "원천 마스터의 `Legal and Compliance`가 조직 정규화를 거쳐 `Legal & Compliance`(Operations 그룹)가 되면, 인원 통계가 조직·그룹 단위로 집계된다."
2. "재직 406에 입사 예정 19를 더하고 퇴사 예정 14를 빼면 월말 411이고, TO 422와 비교하면 −11이며, Engineering −7·Sales −4는 채용 가속, Data & AI +7은 TO 재검토가 된다."
3. "경영진 뷰는 그룹·조직 단위 과부족을, 조직장 뷰는 자기 조직만, HR 뷰는 개인 단위를 본다."
4. "급여 담당의 니즈가 일할 계산 대상을 요구하면 급여 마감이 당월 입·퇴사자를 뽑고 Payroll Close가 보여준다."
5. "온보딩 담당의 니즈가 조직별 배치를 요구하면 온보딩 계획이 Engineering 입사 예정 5명을 묶고 Onboarding이 체크리스트를 보여준다."

## 규칙 (정책)

| 규칙 | 적용 대상 | 정책 스킬 |
|------|----------|----------|
| 개인 식별 정보는 HR 뷰·Payroll·Onboarding 밖으로 나가지 않는다. 경영진·경영기획·조직장 뷰와 월초 리포트는 집계/사번만 | 리포트 뷰, 리포트, 리스크 | `pii-minimization-policy` |
| 모든 집계는 정제 마스터에서 독립 재계산으로 대사되고, 제품·뷰·리포트 간 같은 지표는 같은 값. 클린징은 원천을 덮어쓰지 않고 로그로. 예측·리스크는 가정 명시 | 통계·예측·제품·리포트 | `reconciliation-policy` |
| 모든 실행자는 핸드오프 로그(시도/근거/실패/검증/다음 인계점)를 남긴다 (R2) | 전 에이전트 | `handoff-log-policy` |
| 외부 발송·채용/해고·민감정보·지출·법적 액션·조직 변경은 사람이 승인한다. agent는 제안·초안·준비 완료까지 (R4) | mailer, release, forecaster(권고), auditor | `approval-gate-policy` |
| 산출물은 재사용 자산 형식(md/CSV/JSON/HTML/로그/뷰/다음 액션)으로만 남긴다 (R5) | 전 에이전트 | (handoff-log-policy 자산 조항) |

## 제외

- 급여액·보상·평가: HRIS 본연 기능. 급여 마감은 "누가 대상인가"만
- 채용 파이프라인(공고·면접): 입사일 확정 이후만
- 과거 퇴직 이력·퇴직률 추세: 데모 마스터는 현재 임직원만(427). 퇴직 구분은 퇴사 예정자 기준
- 이직 리스크 ML 학습: 규칙 기반만

## 용어 변경 이력

| 날짜 | 이전 | 이후 | 사유 | 함께 리네임한 대상 |
|------|------|------|------|------------------|
| 2026-09-23 | - | 초기 작성(v1) | Build Day 하네스 구축 | - |
| 2026-09-23 | 본부>실>팀(22팀, 한글) / 직책(팀원~임원) / 스테이지 S1~S5 / 현원=재직+휴직 / ZeroHR | 조직 그룹>조직(4>11, 영문) / 레벨(IC1~VP) / 스테이지=입사 시점 회사 단계 / 재직 인원 기준 TO / Everyday People Agent | 사용자 제공 브리프를 정본으로 채택 | DATA_CONTRACT v2, 스크립트·테스트·스키마(정렬 패스에서 일괄) |

## 추가 용어 (v2.1 — 제품 통합·진화)

| 용어 | 정의 | 표기 | 비고 |
|------|------|------|------|
| 심판 | 페르소나 옹호자 렌즈로 제품을 채점하는 agent 3종(급여 담당 옹호자 / 온보딩 담당 옹호자 / 인사 총괄 옹호자). 각자 자기 루브릭을 가진다 | `product-judge` (`persona-advocate:{persona}`) | 산출 `products/product-comparison.json` §12 |
| 루브릭 | 심판이 쓰는 채점 기준표: fit 기준 충족(가중) + 렌즈별 정성 항목(0~10) | `rubric` | 심판 스킬 `references/rubric-{persona}.md` |
| 통합 제품 | 심판 결과로 3제품을 하나로 합친 제품. 코드 `app`, 표시명 Everyday People Agent. 역할 탭 6종 | `unified-product` (`app`) | §15 |
| 변경 이력 | 제품이 어떤 인풋·채점으로 어떻게 바뀌었는지의 버전 기록 | `changelog` | `products/CHANGELOG.md` §16 |
| 페르소나 인풋 | 새/기존 페르소나가 제품에 넣는 요구(니즈·fit 기준·루브릭) | `persona-input` | `products/inputs/*.json` §16 |
| 진화 루프 | 인풋 → 니즈 갱신 → 재채점 → 재빌드 → 변경 이력 | `evolution` | 스킬 `product-evolution` |
| Function Call 인터페이스 | 페르소나의 기존 시스템(급여·온보딩·인사 총괄) 안의 agent가 Everyday People Agent를 도구로 호출하는 경로. 도구 카탈로그 + HTTP/MCP 서버 | `function-call-api` | §17. 화면과 같은 공통 계층을 읽는다 |
| 도구 카탈로그 | Function Call용 도구 정의 목록(name·description·input_schema) | `tool-catalog` | `api/tools.json` |
| 승인 요청 | agent가 실행 대신 남기는 "승인 대기" 기록 | `approval-request` | `_workspace/approvals/`, 승인 gate |
| 통합 제품 빌더 | 심판 결과로 통합 제품(app)을 만드는 배포 agent | `unified-product-builder` | §15. 데모 4역할 매핑의 "배포 agent"에 속한다 |
| API 연동자 | Function Call 인터페이스(카탈로그·HTTP·MCP 서버·정적 API)를 만드는 배포 agent | `api-integrator` | §17 |
| 배포 준비 완료 | 배포 산출물·명령·체크리스트가 갖춰졌으나 승인 전인 상태(`ready-to-send`와 짝) | `ready-to-deploy` | `_workspace/deploy/checklist-{asOfDate}.md` |
| 필수 수정 / 개선 권고 | 심판이 통합 제품에 요구하는 것: 반드시 해소(mustFix) / 있으면 좋음(niceToHave) | `mustFix` / `niceToHave` | 심판 산출 `_workspace/judging/{persona}.json` |
| 옹호 충족률 | 심판이 자기 페르소나 기준으로만 계산한 충족률 | `advocateCoverage` | 심판 산출 |
| 종합 점수·순위 | 0.5·가중 충족률·10 + 0.5·패널 점수 → bestFit 결정 | `composite` / `ranking` | §12 `comparison.formula`·`comparison.ranking` |
| 패널 점수 | 심판 3명 정성 점수(0~10) 평균 | `panelScore` | §12 |
| 채점 기록 / 배포 기록 / HR 확인 질문 | `_workspace/judging/` · `_workspace/deploy/` · `_workspace/hr-questions-{asOfDate}.md` | — | Memory 층 |
| 제품 이력 / 백로그 | 이전 버전 비교 JSON · 계약 밖 evidence 요구 적재 | `products/history/` · `products/inputs/backlog.md` | §16 |
| 섹션 출처 | 통합 제품 섹션이 어느 제품에서 왔는가 | `data-origin` | §15 |
| 핸드오프 하위 인스턴스 | 병렬 실행 단계의 로그 파일 규칙 `{NN-단계}-{인스턴스}.md` (예 `09-products-insight`, `09-products-judge-payroll`, `09-products-app`) | — | handoff-log-policy |
| 채택 근거 페이지 | 루브릭 채점 과정·종합 순위·통합 결정·변경 이력을 보여주는 설득 페이지 | `decision` | §18 `site/decision/`, 스냅샷 `site/data/decision.json` |
