# Zero Company HR — Everyday People Agent

**Zero Company**는 agent가 회사의 반복 운영 기능을 수행하고 사람이 미션·판단·관계를 담당하는 agent-native company OS다.
그 위에 세운 첫 스타트업이 **Zero Company HR**이고, 제품 브랜드는 **Everyday People Agent** — Workday처럼 HR 데이터를 다루되
수집·정제·분석·예측·배포를 agent가 직접 수행하는 HR Operations Agent Platform이다.

데모 고객사는 가상 기업 ㈜온다테크(재직 406 · 휴직 21 · 총원 427 · 조직 11개)이며, 모든 데이터는 agent가 생성한 가상 데이터다.

## 무엇이 만들어지는가

| 산출물 | 경로 | 내용 |
|---|---|---|
| 원천 → 정제 | `data/raw/` → `data/clean/` | 결함 127건을 주입한 원천 4종과 정답지, 그리고 §2-8 규칙으로 정제한 데이터 + 클린징 로그 |
| 통계·예측 | `data/stats/` | 인원 통계, 월말 인원 예측·TO 과부족·권고, 이직 리스크, 급여 마감, 온보딩 계획, 자동화 효과 |
| 제품 | `site/` | 단일 화면 워크스페이스(`/`) · 역할 탭 6종 · 월초 리포트 · 채택 근거 · Function Call 카탈로그 · Before 사이트 링크. 기존 개별 주소도 유지 |
| 리포트 | `reports/` | 월초 리포트 md/html, 조직별 forecast CSV, 발송 명세(ready-to-send) |
| Function Call | `api/` · `site/api/` | 도구 18개 카탈로그, HTTP 서버, MCP stdio 서버, 정적 스냅샷 |
| 근거 | `_workspace/handoff/` · `products/` | 단계별 핸드오프 로그, 심판 채점, 제품 비교, 변경 이력 |

Executive Snapshot(정본): 재직 406 · 휴직 21 · 총 TO 422 · 기준일 TO 대비 −16 · 입사 예정 19 · 퇴사 예정 14 · **월말 예측 411** · 월말 TO 대비 −11.
`411 = 406 + 19 − 14`, `−11 = 411 − 422`. 이 숫자는 화면·리포트·Function Call 응답 어디서나 같다.

## 빠른 실행

사이트 페이지를 다시 생성한 뒤에는 `python3 scripts/build_workspace.py`로 공통 메뉴와 단일 화면을 재구성한다. Vercel의 정적 배포 루트는 `site/`이다.

Python 3.9 표준 라이브러리만 쓴다(설치 불필요).

```bash
ROOT=$PWD; AS=2026-09-23
python3 .claude/skills/people-data-integration/scripts/generate_synthetic_sources.py --root $ROOT --as-of $AS --self-check
python3 .claude/skills/people-data-cleansing/scripts/cleanse.py        --root $ROOT --as-of $AS
python3 .claude/skills/headcount-stats/scripts/compute_stats.py        --root $ROOT --as-of $AS
python3 .claude/skills/attrition-risk/scripts/score_attrition.py       --root $ROOT --as-of $AS
python3 .claude/skills/month-end-forecast/scripts/forecast.py          --root $ROOT --as-of $AS --self-check
python3 .claude/skills/payroll-close/scripts/payroll_close.py          --root $ROOT --as-of $AS
python3 .claude/skills/onboarding-plan/scripts/onboarding_plan.py      --root $ROOT --as-of $AS
python3 .claude/skills/monthly-report/scripts/automation_effect.py     --root $ROOT --as-of $AS
python3 .claude/skills/monthly-report/scripts/render_report.py         --root $ROOT --as-of $AS
python3 .claude/skills/product-build/scripts/build_snapshots.py        --root $ROOT --as-of $AS --product all --embed
python3 -m unittest discover -s tests
```

고객사 실데이터로 바꾸려면 **첫 줄(가상 원천 생성)만** 고객사 파일 복사로 바꾸면 된다. 나머지는 동일하다.

화면 보기: `cd site && python3 -m http.server 8080` → <http://localhost:8080/>

## Function Call — 세 시스템에서 호출

급여·온보딩·인사 총괄은 각자 쓰는 시스템이 따로 있다. 화면은 보조이고, 그 시스템의 agent가 도구로 호출하는 경로가 본체다.

```bash
python3 api/server.py --root $PWD --port 8787      # HTTP: GET /tools, POST /call
python3 api/mcp_server.py                          # MCP stdio (등록 예시: api/mcp.example.json)
python3 api/build_static.py --root $PWD            # 정적 배포용 site/api/*.json
curl -s localhost:8787/call -d '{"name":"insight.get_executive_snapshot","arguments":{"role":"executive"}}'
```

도구 18개: `payroll.*`(급여 마감·일할·휴직·계약 만료·위험) · `onboarding.*`(타임라인·조직 배치·체크리스트·코호트) ·
`insight.*`(스냅샷·조직별 예측·인사이트·속성 통계·리스크·데이터 품질·시나리오) · `report.get_monthly_dispatch` · `approval.request`.
모든 응답은 `role`에 따라 개인정보를 가리고, 외부 효과가 있는 행위는 실행하지 않고 승인 대기 기록만 남긴다.

## 제품을 어떻게 골랐는가

페르소나 3종의 니즈를 데이터(`personas/persona-needs.json`)로 만들고, 제품 3종을 만든 뒤,
페르소나 옹호자 심판 3명이 각자의 루브릭으로 **세 제품 모두**를 채점했다. 종합 = `0.5 × 가중 충족률 × 10 + 0.5 × 패널 점수`.

| 제품 | 가중 충족률 | 패널 점수 | 종합 |
|---|---:|---:|---:|
| Insight | 100% | 5.2 | **7.62** |
| Onboarding | 100% | 3.8 | 6.90 |
| Payroll Close | 100% | 3.7 | 6.85 |

채택: **Insight 골격 + 나머지 강점 흡수 → 통합 제품(`site/app/`)**. 과정 전체는 `site/decision/`에서 볼 수 있다.
새 페르소나가 `products/inputs/`에 인풋을 넣으면 재채점 → 재빌드 → `products/CHANGELOG.md` 기록으로 제품이 진화한다.

## 하네스 (Zero Company OS)

- 역할 = `.claude/agents/` 15종 · 방법 = `.claude/skills/` · 조율 = `zerohr-orchestrator` 스킬
- 공유 언어 = `.claude/GLOSSARY.md` · 데이터 정본 = `.claude/DATA_CONTRACT.md` · 회사 형상 = `zero-company/`
- 정책: 핸드오프 로그 · 대사 · 개인정보 최소화 · 승인 gate · 주장 범위 구분
- 사람이 결정하는 것: 외부 발송, 배포, 채용/해고, 민감정보 접근, 조직 변경

## 범위 (claims-boundary-policy)

구현됨: 파이프라인 전 단계 스크립트와 테스트, 역할 필터 화면, Function Call 도구·서버.
목업·준비 완료: 월초 이메일(가상 수신자, `ready-to-send`), Supabase 실시간 갱신(`config.js` 있을 때), 온보딩 체크리스트 상태(seed 고정).
승인 대기: 실제 발송·배포, 권고의 채택. 역할 뷰는 **표시 필터**이며 접근 통제가 아니다.
