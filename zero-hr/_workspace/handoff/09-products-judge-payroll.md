# 09 · product-judge (persona-advocate: payroll) 핸드오프

## 1. 시도
- 읽음: `.claude/agents/product-judge.md`(구조화 출력 shape), `.claude/skills/product-judge/SKILL.md` §2~§7, `.claude/skills/product-judge/references/rubric-payroll.md`(R1~R6, 실격 조건, must/nice 구분), `personas/persona-needs.json`(payroll 페르소나 keyQuestions·rubric·fitCriteria 확인, head-of-hr 섹션도 열어 evidence 매핑 대조)
- 기계 채점 재계산은 하지 않고 `_workspace/judging/mechanical.json`의 `products.{insight,payroll,onboard}`(criteriaMet·coverage·sections·piiChecks)와 `advocate.payroll`(advocateCoverage 원본)을 그대로 복사
- `site/payroll/index.html`(전체 data-section 11개: header·kpi·checklist·headcount·prorations-actual·prorations-planned·leaves·contracts·risks·data-quality·claims) — 각 섹션 블록을 `python3` 정규식으로 슬라이스해 내용·배지 로직(JS)을 직접 확인
- `site/insight/index.html`, `site/onboard/index.html` — kpi·data-quality·planned-moves·timeline·checklist·departments 섹션을 슬라이스해 급여 마감 관점에서 재사용 가능한 필드(성명·일자·workedDays 등) 유무 확인
- `api/tools.json` — `payroll.*` 5개 도구(get_close_summary·list_prorations·list_leave_treatments·list_contract_expirations·list_risks) 설명을 읽고 마감 질문(R1~R5)과 1:1 대응 확인. `onboarding.*`·`insight.*` 네임스페이스도 확인(18개 도구 중)
- grep으로 실격 조건 4종 직접 재검증: `급여액|salary|amount|계좌|account|세금|tax`(payroll html+json), `birthDate`(payroll json), `riskScore`(payroll html), 대사 `payrollHeadcount.monthEndActive`=`forecast.totals.forecastMonthEnd`(411=411)

## 2. 근거
- 루브릭: `.claude/skills/product-judge/references/rubric-payroll.md`(공통 앵커 0/3/5/8/10, must=R1·R2·R5, nice=R3·R4·R6, 실격 조건 4종)
- 니즈 파일: `personas/persona-needs.json` `asOfDate: 2026-09-23`
- 기계 채점 소스: `_workspace/judging/mechanical.json`(`script: .claude/skills/product-judge/scripts/mechanical_scoring.py`, `asOfDate: 2026-09-23`, `warnings: []`)

## 3. 실패
- `unverifiable` 처리 대상 없음 — mechanical.json의 세 제품 모두 `criteriaMet` 전 항목이 `met: true`이고 `verifiable == met`(insight 15/15, payroll 14/14, onboard 13/13)
- 스냅샷 파싱 실패 없음, HTML 누락 없음 — 세 제품 모두 `data-fit` 존재
- 재채점 대상 아님 — `_workspace/judging/payroll.json` 이전 버전 없음(이번이 최초 생성)

## 4. 검증
- 기계 채점 복사: insight 15건 · payroll 14건 · onboard 13건 = 총 42건(전부 met:true, 직접 grep 재계산 없이 mechanical.json 신뢰 — 상류가 이미 evidence 3단 확인을 마쳤음)
- PII 부정 검사: 9건(제품별 3건) 전부 `passed: true` — mechanical.json 값과 직접 재확인한 grep(급여액/salary/amount/계좌/account/세금/tax → 0건 실제 값, birthDate → 0, riskScore(html) → 0) 일치
- 정성 채점(R1~R6 × 3제품) = 18건, 전부 `data-section` 근거 인용. payroll 6항목 평균 9.0(모든 must≥8), insight 6항목 평균 2.7(R2·R1만 5점 상한, 나머지 0~3), onboard 6항목 평균 1.0(R2만 5점 상한)
- 실격 조건 4종 재검증 — 전부 미해당(상한 적용 없음)

## 5. 다음 인계점
- `scripts/aggregate_judgments.py`가 이 파일과 `onboarding.json`·`head-of-hr.json`을 과반·평균으로 병합해 `products/product-comparison.json`(§12)을 만든다. `criteriaMet[].met`은 세 심판이 같아야 하는 사실 — 이번 인스턴스는 mechanical.json을 그대로 신뢰했으므로 다른 두 심판과 불일치가 나면 mechanical_scoring.py 결과 자체를 재검토해야 한다(내 grep 재확인으로는 이상 없음)
- `unified-product-builder`가 볼 것: mustFix 1건(payroll/prorations-planned — stale-planned-leaver 인라인 경고 부재, 이중 처리 위험) + niceToHave 4건(checklist 섹션 링크, leaves '기타' 미확인 라벨, insight kpi·onboard timeline이 payroll 구조를 흡수해야 한다는 신호)
- `advocateCoverage.insight`·`advocateCoverage.onboard`가 공통으로 `unmet: P-F6`(위험 어휘 구분) — 통합 제품의 payroll 탭은 이 어휘 구분(파생 플래그="급여 담당 즉시 확인" vs 클린저 플래그="고객사 HR 확인 대기")을 그대로 가져와야 한다
- 산출물: `_workspace/judging/payroll.json`(JSON 유효성 확인됨), `_workspace/handoff/09-products-judge-payroll.md`(본 파일)
