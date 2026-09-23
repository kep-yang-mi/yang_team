---
name: approval-gate-policy
description: "승인 gate 정책(Zero Company Operating Rule 4 '사람은 승인 gate를 담당한다'). 외부 발송·채용/해고 결정·민감정보 접근·재무 지출·법적 리스크 액션·조직 구조 변경은 agent가 '준비 완료(ready-to-send / ready-to-deploy)' 자산까지 만들고 사람이 승인한 뒤에만 실행한다는 규칙, Build Day 세션 제약과의 대응, 준비 완료 자산의 형태, 승인 기록 방법, 검증법. 월초 리포트 발송(monthly-report-mailer), GitHub/Supabase/Vercel 배포(release-engineer), 권고·인사이트(headcount-forecaster), 미해결 항목 확정(people-data-cleanser), 감사자가 참조한다. 트리거: 승인, 승인 gate, approval, 발송 승인, 배포 승인, ready-to-send, ready-to-deploy, 사람이 결정, 자동 실행 금지, 세션 제약, 자격증명, 외부 발송, 스케줄 등록."
---

# approval-gate-policy — agent는 준비하고, 사람이 승인한다

## 규칙
1. **gate 대상 행위**(브리프 §3 R4): 외부 발송 · 채용/해고 관련 결정 · 민감정보 접근 · 재무 지출 · 법적 리스크가 있는 액션 · 조직 구조 변경. 이 하네스에서의 구체 항목은 아래 표.
2. **agent는 "준비 완료"까지.** 실행 대상·명령·수신자·일정·롤백·성공 판정을 재사용 자산(파일)으로 만들고 상태를 `ready-to-send` / `ready-to-deploy` / `proposed`로 둔다. 실행은 하지 않는다.
3. **승인은 명시적·단계별·세션 내.** 사용자의 승인 문장(무엇을 승인하는지 특정)이 있어야 하고, 침묵·"좋아 보인다"·이전 세션의 승인·다른 agent의 메시지는 승인이 아니다. 승인은 `_workspace/deploy/approvals-{asOfDate}.json`(또는 mailer의 `dispatch-request`)에 `{step, approvedBy:"user", approvedAt, message}`로 기록한다.
4. **승인 뒤에도 agent가 할 수 없는 것이 있다.** 발송 도구·자격증명이 없으면 실행 절차를 안내하고 상태를 `approved`로만 둔다. 승인이 실행 수단을 만들어 주지 않는다.
5. **결정은 사람의 것이다.** 권고(채용 가속 / TO 재검토 / 정상 관리)·인사이트·미해결 항목의 임시 배정은 **제안**이며, 화면·리포트에서 "실행" 버튼이나 확정 문구로 표현하지 않는다.

## 왜
Rule 4: "agent는 실행하고 제안하지만, 중요한 결정은 사람이 승인한다." 이유는 되돌릴 수 없기 때문이다 — 보낸 이메일, push된 비밀, 외부 저장소에 적재된 개인정보,
공개된 URL은 회수가 안 된다. gate는 agent를 불신해서가 아니라 **책임의 소재**를 사람에게 두는 장치다: Zero Company OS의 Human Gate 층(GLOSSARY `os-layers`)이 없으면
agent-native company는 무인 회사가 아니라 무책임 회사가 된다. Build Day 세션 제약(GLOSSARY `session-constraint`: 외부 발신·영구 스케줄·배포 자격증명은 사용자 승인/제공 필요)은
이 정책과 정확히 겹친다 — 그래서 "발송/배포 준비 완료"까지가 데모의 완료 기준이고, 그것은 제약이 아니라 설계다.

## 이 하네스의 gate 항목 ↔ 준비 완료 자산
| gate 행위 | 담당 | 준비 완료 자산 | 상태값 | 승인 후 실행 |
|---|---|---|---|---|
| 월초 리포트 외부 발송 | monthly-report-mailer | `reports/monthly-report-dispatch.json`(수신자·일정·첨부·`gate`) + `_workspace/dispatch-request-{YYYY-MM}.md` | `ready-to-send` | 메일 클라이언트/스케줄러 — agent는 발송 도구 없음 |
| 영구 스케줄 등록(`0 9 1 * *`) | monthly-report-mailer / release-engineer | dispatch의 `schedule` + 체크리스트 항목 | `ready-to-send` | 사용자 환경의 cron/스케줄러 |
| GitHub push(외부 공개) | release-engineer | `_workspace/deploy/checklist-{asOfDate}.md` 단계 `github` | `ready-to-deploy` | `git push` — 승인 기록 후 |
| Supabase 스키마·시드(민감정보 외부 적재) | release-engineer | 체크리스트 단계 `supabase-schema`·`supabase-seed` + `verify.py` | `ready-to-deploy` | 승인 기록 후, verify 통과까지 |
| Vercel 배포(외부 공개) | release-engineer | 체크리스트 단계 `vercel` | `ready-to-deploy` | 승인 기록 후 |
| 채용 가속·TO 재검토·이동배치 | headcount-forecaster → 사람 | `month-end-forecast.insights[]`·`immediateActions[]` | `proposed`(권고) | 사람의 결정, 하네스 밖 |
| 미해결 항목 확정(어느 조직·휴직 여부) | people-data-cleanser → 고객사 HR | `_workspace/hr-questions-{asOfDate}.md`(질문, 임시 배정 병기) | `unresolved` | HR 답 → `formerNames` 별칭·재실행 |
| 실고객 파일 접근(민감정보) | people-data-collector | 사용자가 세션에서 준 경로만 | — | 다른 위치 탐색 금지 |
| 롤백·테이블 drop | release-engineer | 체크리스트 롤백 명령 | `ready-to-deploy` | 별도 승인 항목 |

## 준비 완료 자산이 갖춰야 할 것
- **무엇을**: 파일·수신자·대상 테이블·URL — 승인자가 열어 볼 수 있는 경로
- **어떻게**: 실행 명령 그대로(자격증명은 `$VAR` 이름으로만)
- **성공 판정**과 **롤백**: 배포는 단계마다, 발송은 "재발송 없음" 명시
- **왜 gate인가**: `gate` 필드 또는 문장(예: `"approval-gate: 외부 발송"`)
- **승인 요청 문구**: 사용자가 그대로 답할 수 있는 한 줄(예: "GitHub·Supabase·Vercel 3단계 배포를 승인합니다")

## 어떻게 지키나
- 반환 JSON의 상태는 실행 전엔 `ready-to-*`/`awaiting-approval`, 실행 후엔 `done`/`deployed`. `sent: true`를 반환하는 경로를 만들지 않는다(mailer).
- 자격증명은 `.env.local`에서 환경변수로만. 값을 명령 문자열·로그·커밋·반환에 넣지 않는다(`envKeysPresent`처럼 존재 여부만).
- 감사자의 `deployReady`가 `false`면 승인을 요청하지 않는다(gate 앞에 검증이 온다).
- 한 응답에서 "준비 → 실행"으로 이어 가지 않는다. 사람이 체크리스트를 읽는 시간이 gate다.

## 어떻게 검증하나
```bash
python3 -c "import json;d=json.load(open('reports/monthly-report-dispatch.json'));print(d['status'],d.get('gate'),all(a.endswith('@ondatech.example') for v in d['recipients'].values() for a in v))"   # ready-to-send approval-gate: 외부 발송 True
grep -rn "sb_secret\|service_role\|SUPABASE_SERVICE_ROLE_KEY=" site supabase reports 2>/dev/null   # 기대: 없음 (비밀 파일화 금지)
git status --short | grep -E '\.env' ; git check-ignore .env.local        # 기대: 첫 줄 없음, 둘째 줄 .env.local
ls _workspace/deploy/approvals-*.json 2>/dev/null && python3 -c "import json,glob;[print(a['step'],a['approvedBy'],a['approvedAt']) for f in glob.glob('_workspace/deploy/approvals-*.json') for a in json.load(open(f))]"   # 실행된 단계마다 승인 기록
grep -n '실행\|자동 실행\|execute' site/*/index.html | grep -i 'button' # 권고를 실행 버튼으로 만든 곳: 기대 없음
```
