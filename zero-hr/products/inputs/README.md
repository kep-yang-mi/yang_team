# products/inputs — 페르소나 인풋

새 페르소나(또는 기존 페르소나의 새 요구)가 제품에 넣는 요구를 **파일**로 받는 자리다(DATA_CONTRACT §16, GLOSSARY `persona-input`).
인풋이 들어오면 `product-evolution` 스킬이 검증 → 니즈 갱신 → 심판 재채점 → 통합 제품 재빌드 → `products/CHANGELOG.md` 항목 순서로 처리한다.
채팅으로 요구를 말하는 대신 파일을 만드는 이유: 왜 바뀌었는지(근거)와 그 변경이 기존 페르소나의 fit을 얼마나 바꿨는지(심판 점수 델타)가 남아야 하기 때문이다.

## 파일명
`{persona}-{YYYY-MM-DD}.json` — 예: `finance-controller-2026-09-23.json`. `persona`는 kebab-case, 날짜는 `submittedAt`과 같게.
`example-*.json`은 데모용 예시라 파일명 규약 검사를 건너뛴다.

## 스키마 (§16)
```json
{
  "persona": "finance-controller",
  "title": "재무 통제",
  "submittedAt": "2026-09-23",
  "source": "interview",
  "needs": [
    {"id": "FC-N1", "need": "조직 그룹별 월말 급여 대상 인원을 Finance 예산 코드로 본다", "importance": 4}
  ],
  "fitCriteria": [
    {"id": "FC-F1", "criterion": "조직 그룹(4) 단위 월말 급여 대상 인원을 한 표에서 본다", "weight": 4, "evidence": "payroll-close.payrollHeadcount.byDepartment"}
  ],
  "rubric": {"lens": "분기 인건비 예측을 갱신하는 재무 통제 담당이 이 화면만으로 인원 기준을 확정할 수 있는가", "scoring": "0~10, 기준: 0 없음 / 3 ... / 5 ... / 8 ... / 10 ..."}
}
```
| 필드 | 규칙 |
|---|---|
| `persona` | `^[a-z][a-z0-9-]*$`. 기존 코드(`head-of-hr`·`payroll`·`onboarding`)면 "기존 페르소나의 새 요구"로 처리 |
| `title` | 한글 표시명. 영문은 선택 `titleEn` |
| `submittedAt` | `YYYY-MM-DD` |
| `source` | `interview` \| `survey` \| `ticket` \| `agent` |
| `needs[]` | `id`(권장 `{접두}-N{n}`), `need`, `importance` 1~5 정수 |
| `fitCriteria[]` | `id`(권장 `{접두}-F{n}`), `criterion`(화면에 있어야 할 것 한 문장), `weight` 1~5 정수, `evidence`(아래 계약 경로) |
| `rubric` | `lens`(옹호자의 한 문장 질문), `scoring`(0~10 앵커 설명). 새 페르소나면 심판 루브릭 파일의 출발점 |

## `evidence`에 쓸 수 있는 접두 (계약 경로)
`headcount-master.clean.` · `to-plan.clean.` · `planned-joiners.clean.` · `planned-leavers.clean.` · `cleansing-summary.` · `headcount-stats.` · `month-end-forecast.` · `attrition-risk.` · `automation-effect.` ·
`payroll-close.` · `onboarding-plan.` · `persona-needs.` · `product-comparison.` · `site/{product}/index.html ...` · `reports/` · `policy:pii-minimization-policy` · `reconciliation:{A}={B}`

이 밖의 evidence는 **거절되지 않는다** — `validate_input.py`가 `backlog.md`에 "계약 확장 필요"로 적재하고 그 기준은 이번 라운드 채점에서 빠진다.
계약(DATA_CONTRACT)을 확장한 뒤 재검증하면 다음 라운드에 들어간다.

## 제출 → 처리
```bash
python3 .claude/skills/product-evolution/scripts/validate_input.py products/inputs/finance-controller-2026-09-23.json   # 검증 (종료 0이면 진행)
# 이후는 product-evolution 스킬 절차 2~5 (니즈 갱신 → 재채점 → 재빌드 → CHANGELOG → 13-evolve)
```
예시 파일: `example-finance-controller.json`(유효, 데모에서 "새 페르소나가 들어온다"를 보여 주는 용도).
