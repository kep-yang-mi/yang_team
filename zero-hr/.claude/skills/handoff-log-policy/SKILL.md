---
name: handoff-log-policy
description: "핸드오프 로그 정책(Zero Company Operating Rule 2 '중간 발견과 실패 로그를 공유한다' + Rule 5 '모든 결과는 재사용 가능한 자산으로 남긴다'). 모든 실행자가 _workspace/handoff/{NN-단계}.md에 5개 고정 절(시도한 것/본 데이터·근거/실패한 것/검증된 것/다음 agent 인계점)을 남기고, 산출물은 md·CSV·JSON·HTML·로그·뷰·다음 액션 중 하나의 재사용 자산이어야 한다는 규칙과 그 이유, 형식, 검증법. 파이프라인의 모든 에이전트와 오케스트레이터가 참조한다. 트리거: 핸드오프, 핸드오프 로그, handoff, 실패 로그, 중간 발견 공유, 인계, 다음 agent, 재사용 자산, Rule 2, Rule 5, _workspace/handoff."
---

# handoff-log-policy — 다음 실행자가 이어받을 수 있게 남긴다

## 규칙
1. **모든 실행자는 단계마다 핸드오프 로그를 남긴다.** 경로 `_workspace/handoff/{NN-단계}.md`. 병렬 인스턴스는 `{NN-단계}-{인스턴스}.md`(예: `09-products-judge-payroll.md`).
2. **절은 5개, 순서와 제목 고정.** `## 시도한 것` / `## 본 데이터·근거` / `## 실패한 것` / `## 검증된 것` / `## 다음 agent 인계점`. 비어 있는 절도 "없음"으로 남긴다 — 절이 빠지면 "안 봤는지 없었는지"를 다음 실행자가 모른다.
3. **산출물은 재사용 자산이다(R5).** md 보고서 · CSV/JSON 데이터 · Dashboard HTML · 실행 로그 · 권한별 뷰 · 다음 액션 — 이 중 하나의 형식으로 파일에 남는다. 채팅 답변만으로 끝나는 단계는 없다.
4. **실패도 자산이다.** 대사 실패·unresolved·unverifiable·건너뛴 검사는 "실패한 것"에 원인 후보와 함께 적는다. 성공만 적은 로그는 다음 실행자를 같은 벽에 다시 부딪히게 한다.
5. **개인 행을 인용하지 않는다.** 로그에는 사번·경로·건수·명령만(`pii-minimization-policy`).

## 왜
브리프 Rule 2: "여러 agent가 각자 많이 시도하는 것보다, 검증된 중간 발견과 실패 로그를 공유할 때 문제 해결 효율이 올라간다."
워크플로우에서 각 에이전트는 자기 컨텍스트만 갖고 시작한다 — 앞 단계가 무엇을 봤고 무엇에 실패했는지를 파일로 남기지 않으면 다음 에이전트는 같은 파일을
다시 열고 같은 실패를 반복한다. 특히 "실패한 것"이 중요한 이유: 성공 경로는 산출물 자체가 말해 주지만 실패 경로(시도했으나 안 된 것, 열 수 없던 evidence, 건너뛴 검사)는
로그가 아니면 어디에도 남지 않는다. Rule 5가 붙는 이유는 Zero Company의 산출물은 사람에게 보내는 답이 아니라 **다음 agent(또는 다음 달의 같은 agent)** 의 입력이기 때문이다.
`_workspace/`가 회사 OS의 Memory 층(GLOSSARY `os-layers`)이다.

## 단계 번호 (DATA_CONTRACT §7 + §16)
`01-collect` · `02-cleanse` · `03-stats` · `04-forecast` · `05-attrition` · `06-payroll` · `07-onboarding` · `08-personas` · `09-products` · `10-report` · `11-test` · `12-deploy` · `13-evolve`.
병렬 인스턴스 예: `08-personas-{personaCode}` · `09-products-{insight|payroll|onboard|hub}` · `09-products-judge-{persona}` · `09-products-app`.
※ 기존 에이전트 정의 일부가 `persona-needs-{code}.md`·`product-build-{product}.md`·`payroll-close.md`·`attrition.md` 같은 이름을 쓴다 — 정렬 패스에서 위 규약으로 맞춘다. 규약이 이긴다.

## 형식
```markdown
# {NN-단계} — {에이전트명} · {asOfDate} · {실행 시각}

## 시도한 것
- 실행 명령·인자 (예: `python3 .claude/skills/month-end-forecast/scripts/forecast.py --as-of 2026-09-23 --self-check`)
- 재호출이면: 이전 산출물과 무엇이 달라졌는가

## 본 데이터·근거
- 읽은 파일과 그 asOfDate·행 수 (예: `data/clean/headcount-master.clean.csv` 427행)
- 근거로 삼은 계약 절·정책 (예: DATA_CONTRACT §4-2 권고 규칙)

## 실패한 것
- 대사 불일치·unresolved·unverifiable·건너뛴 검사 — 각각 원인 후보와 돌려보낼 단계 (없으면 "없음")

## 검증된 것
- 통과한 대사·self-check·테스트와 그 값 (예: 406=406, 411=411, 재현율 0.98)

## 다음 agent 인계점
- 다음 단계가 읽을 파일 경로와 키
- 아직 열려 있는 것 (승인 대기, HR 확인 질문, 계약 확장 제안 `contractGaps`)
```

## 어떻게 지키나
- 반환 JSON에 `handoffLog` 경로를 싣는다. 로그를 쓰지 못했으면 `status`가 `ok`가 될 수 없다.
- 로그는 산출물을 쓴 **뒤**에 쓴다(검증된 것에 실제 값을 적기 위해). 스크립트 stdout 요약을 그대로 붙이지 말고 다음 실행자가 읽을 문장으로 옮긴다.
- 재호출 시 기존 로그를 덮어쓰되, 이전 실행의 "실패한 것"이 해소됐으면 "검증된 것"에 "이전 실패 X 해소"로 남긴다 — 델타가 진화 루프의 근거다.
- 계약에 없는 필드가 필요했던 지점은 "다음 agent 인계점"에 `contractGaps`로 적는다. 즉석에서 계약 밖 필드를 만들지 않는다.

## 어떻게 검증하나
```bash
ls _workspace/handoff/                                                   # 실행된 단계마다 파일이 있다
for f in _workspace/handoff/*.md; do for h in "## 시도한 것" "## 본 데이터·근거" "## 실패한 것" "## 검증된 것" "## 다음 agent 인계점"; do grep -q "^$h" "$f" || echo "MISSING $h in $f"; done; done   # 기대: 출력 없음
grep -L "asOfDate\|2026-09-23" _workspace/handoff/*.md                   # 기준일 없는 로그: 기대 없음
```
감사자(`people-data-auditor`)는 5절 존재를 검사하고, 오케스트레이터는 각 단계 반환값의 `handoffLog` 경로가 실제 파일인지 확인한다.
