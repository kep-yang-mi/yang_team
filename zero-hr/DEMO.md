# 데모 진행 순서 (10분)

## 0. 준비
```bash
cd ~/development/zero-hr
cp reports/monthly-report-2026-10.* reports/org-forecast-2026-09.csv reports/monthly-report-dispatch.json site/reports/
cd site && python3 -m http.server 8080 &
python3 ../api/server.py --root .. --port 8787 &
```

## 1. 문제 (1분)
"HR 담당자는 매달 마스터·TO·입퇴사 예정 엑셀을 모아 조직별 인원과 월말 예측을 손으로 만든다. 세 페르소나가 이 일에 쓰는 시간이 월 40시간."
→ `site/decision/` ① 문제 절을 띄운다.

## 2. agent가 데이터를 만들고 정리한다 (2분)
```bash
python3 .claude/skills/people-data-cleansing/scripts/cleanse.py --root $PWD --as-of 2026-09-23 | tail -1
```
"원천에 결함 127건을 일부러 넣었고 정답지를 갖고 있다. 조직명 보정 17건, 입사일 포맷 31건, 중복 8건, 미해결 12건은 고치지 않고 질문으로 남긴다."
→ `data/clean/cleansing-summary.json`의 `unresolvedItems`를 보여준다. **못 고친 것을 감추지 않는 것이 핵심.**

## 3. 실시간 HR 리포트 (2분)
<http://localhost:8080/insight/?view=executive> → 경영진 뷰: 406 / 411 / −11, Engineering −7·Sales −4 채용 가속, Data & AI +7 TO 재검토.
역할을 HR → 경영기획 → 조직장으로 바꾼다. "같은 데이터, 다른 뷰. 숫자는 한 번도 달라지지 않는다."
경영기획 뷰의 시나리오 플래너에서 채용 달성률을 80%로 내려 본다.

## 4. 세 사람은 각자 다른 시스템을 쓴다 (2분)
```bash
curl -s localhost:8787/call -H 'content-type: application/json' \
  -d '{"name":"payroll.get_close_summary","arguments":{"payPeriod":"2026-09","role":"payroll"}}' | head -30
```
"급여 시스템의 agent가 이렇게 부른다. 월말 급여 대상 411은 인사 총괄이 보는 월말 예측 411과 같은 값이다."
`api/mcp.example.json`을 보여주며 "Claude Desktop·Claude Code에 MCP로 등록하면 그대로 도구가 된다."

## 5. 어떻게 이 제품을 골랐나 (2분)
<http://localhost:8080/decision/> → ④ 루브릭 히트맵: 심판 3명 × 제품 3종 점수, ⑤ 종합 순위(Insight 7.62), ⑥ 통합 결정(무엇을 흡수했나).
"제품을 하나 정해놓고 만든 게 아니라, 세 개를 만들고 세 렌즈로 채점해서 골랐다. 그 과정이 제품 안에 남아 있다."

## 6. 다음 사람이 들어오면 (1분)
`products/inputs/finance-lead-2026-09-23.json` → "재무팀장이 요구를 넣었다. 검증 → 니즈 갱신 → 재채점 → 재빌드 → 변경 이력."
```bash
python3 .claude/skills/product-evolution/scripts/validate_input.py products/inputs/finance-lead-2026-09-23.json | tail -5
```

## 7. 마무리
`reports/monthly-report-2026-10.md`와 dispatch `ready-to-send` 상태를 보여주며:
"발송은 사람이 승인한다. agent는 준비까지. 이것이 Zero Company의 승인 gate다."
