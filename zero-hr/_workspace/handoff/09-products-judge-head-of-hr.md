# 09 · Products Judge — head-of-hr (인사 총괄 옹호자)

## 시도
- 읽음: `.claude/agents/product-judge.md`, `.claude/skills/product-judge/SKILL.md` §5·§7, `.claude/skills/product-judge/references/rubric-head-of-hr.md`
- `personas/persona-needs.json`의 `head-of-hr` persona 전체(goals·jobsToBeDone·keyQuestions·kpis·fitCriteria H-F1~H-F15·rubric) 확인
- `_workspace/judging/mechanical.json` 재사용: `advocate["head-of-hr"]` (insight weightedCoverage 1.0, payroll 0.434, onboard 0.6857) + `products.{insight,payroll,onboard}.criteriaMet/coverage/piiChecks` 그대로 복사
- 세 제품 HTML을 `grep -o 'data-section=' `·`data-views=`·python 슬라이스로 훑음: `site/insight/index.html`(19개 section, 7종 view 조합), `site/payroll/index.html`(11개 section, data-views 0건), `site/onboard/index.html`(10개 section, data-views 0건)
- Insight 핵심 렌더 함수 확인: `renderDeptGap`(recBadge 색상 분기 badge-rec-hire/to/ok), `renderRiskPeople`(riskBand만 렌더, riskScore 미노출), `VIEW_DESC`(4뷰 안내문), `history.replaceState`(URL ?view=/?dept= 공유)
- 임베디드 JSON에서 직접 확인: `forecast.insights[]`(Engineering −7·Sales −4·Data & AI +7·Legal & Compliance, action 포함), `cleansingSummary`(unresolvedCount=12, correctionsByRule 15종), `stats.dataQuality.briefDiscrepancies`(215/119/62 vs 220/128/48 — 루브릭 예시와 정확히 일치)
- `api/tools.json`에서 `insight.get_executive_snapshot`·`get_department_forecast`·`get_insights` 설명 전문 확인(role별 PII 필터 명시)
- `reports/monthly-report-2026-10.md`(첫 60행) + `reports/monthly-report-dispatch.json`(status=ready-to-send, 4그룹 수신자, attachments에 CSV 포함) 대조
- 실격 조건 grep: `riskScore`(payroll/onboard 0건, insight는 임베디드 JSON에만 있고 렌더 0건) · `<button>실행/승인/채용 시작`(3제품 0건) · `birthDate`(3개 스냅샷 0건) · payroll/onboard `data-views=` 0건(뷰 분리 자체 부재 확인)

## 근거
- 루브릭 파일: `rubric-head-of-hr.md`(항목 R1~R6, must=R1·R2·R3 / nice=R4·R5·R6, 비home 상한: payroll headcount/data-quality 5점, onboard teams/early-attrition 3~5점)
- 니즈 파일 asOfDate: 2026-09-23 (persona-needs.json 최상위 asOfDate와 일치)
- mechanical.json asOfDate: 2026-09-23, warnings: []

## 실패 / unverifiable
- 없음 — 세 제품 모두 HTML·스냅샷 존재, `data-fit` 속성 전부 확인 가능. mechanical.json의 `criteriaMet`은 각 제품 자기 담당 페르소나 기준(H-F*/P-F*/O-F*)이 이미 전부 met(coverage 1.0)이라 재검증만 수행(재현 확인, 새 grep 없음)
- advocateCoverage(H-F* 기준을 payroll/onboard에 적용)는 mechanical.json에서 이미 계산된 값을 그대로 복사: payroll weightedCoverage 0.434(met 5/14), onboard 0.6857(met 6/9)

## 검증
- 기계 채점 재확인: 3제품 × 자기 기준 전부(insight 15, payroll 14, onboard 13) = 42건, 전부 met:true (복사 전 재현 grep 통과)
- PII 검사: 9건(제품당 3건) 전부 passed
- 정성 채점: 6항목 × 3제품 = 18건, 전부 앵커 대응 note 작성(section 인용). 평균 재계산 확인: insight 10.0, payroll 1.3(=8/6), onboard 1.7(=10/6)
- 실격 조건 5종 × 3제품 grep 전부 통과(위반 없음) — 상한 적용 없음

## 다음 인계점
- `_workspace/judging/head-of-hr.json` — `scripts/aggregate_judgments.py`가 `payroll.json`·`onboarding.json`과 함께 과반 병합해 `products/product-comparison.json` §12 생성
- `unified-product-builder`가 볼 mustFix 4건: payroll R1/R2(TO·gap·recommendation 부재), payroll R3(뷰 분리 부재로 사번+성명 노출), onboard R1(TO 개념 부재), onboard R3(뷰 분리 부재로 성명 노출) — 공통 결론: **payroll·onboarding 탭은 통합 제품에서 hr/payroll/onboarding role 전용으로 게이트하고, TO·gap·recommendation은 Insight의 department-gap·insights 섹션을 공통 계층으로 승격해 재사용해야 한다**
- niceToHave 4건(payroll에 attrition 요약·리포트 링크 병기, onboard에 data-quality 표·리포트 링크 병기)은 통합 시 낮은 우선순위 개선
