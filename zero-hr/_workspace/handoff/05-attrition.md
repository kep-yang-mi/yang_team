# 05-attrition — attrition-risk-scorer — 2026-09-23 (완료)

## 시도한 것
- `python3 .claude/skills/attrition-risk/scripts/score_attrition.py --root .` (소요 0.138s)
- 모델 rule-based-v1: 요인 7개(신호 3·기초 4), 밴드 경계 {"높음": "score>=60", "중간": "35<=score<60", "낮음": "score<35"}, 기대 확률 {"높음": 0.35, "중간": 0.12, "낮음": 0.03}
- 보정: 적용 — 신호군 배율 1.16 · 기초군 배율 1.10 · targetMet=True (목표 높음 8~15% · 중간 25~35%)
- 가중치 재정의(--weights): 없음

## 본 데이터·근거
- `data/clean/headcount-master.clean.csv`: 427행(사번 유일) → 재직 406(점수화) · 휴직 21(제외) · 기타 0
- `data/reference/org-chart.csv`: 조직 11개
- `data/clean/to-plan.clean.csv`: 조직 11개, gapAsOf<0 조직 D02, D03, D04, D06, D07, D08, D10, D11
- `data/stats/headcount-stats.json`: 없음(대사 생략)
- 요인 유병률(재직 406명 기준): tenure-1-3y 151(37.2%), level-stagnation 1(0.2%), contract-expiring 24(5.9%), job-family-eng-data-ai 140(34.5%), age-20s-30s 303(74.6%), dept-understaffed 338(83.3%), level-ic 180(44.3%)
- 실효 가중치: {"tenure-1-3y": 26, "level-stagnation": 28, "contract-expiring": 41, "job-family-eng-data-ai": 11, "age-20s-30s": 8, "dept-understaffed": 9, "level-ic": 6}

## 실패한 것
- (없음)

## 검증된 것
- byEmployee 406행 = summary 밴드 합 406 = byDepartment 재직 합 406 = byOrgGroup 재직 합 406
- headcount-stats.totals.activeHeadcount 대사: 생략(파일 없음)
- byEmployee 키 = §4-3 5개(empId, deptCode, riskScore, riskBand, topFactors)만 — 성명·생년월일·연령대 없음 (pii-minimization-policy)
- 밴드 분포: 높음 44(10.8%) · 중간 118(29.1%) · 낮음 244(60.1%) — 목표 충족
- summary.expectedAttritionNext3Months = 36.88 (0.35×44 + 0.12×118 + 0.03×244), 평균 점수 32.1
- model.bands 문자열 = 계약 §4-3과 동일

## 다음 agent 인계점
- 산출물 `data/stats/attrition-risk.json` (§4-3). 요약 JSON은 stdout 마지막 줄
- **headcount-forecaster**: `byDepartment[].expectedAttritionNext3Months`(deptCode 조인) ÷ 3 → `riskAdjusted.expectedAttrition`. 퇴사 예정자가 점수화 모집단에 포함되므로 plannedOut과 이중 계산 가능 — assumptions에 명시할 것
- **onboarding-plan-analyst**: `byEmployee[].riskBand`(empId 조인) → 버디 후보(낮음만)·90일 코호트 밴드
- **product-builder(insight)**: `summary`·`byOrgGroup`·`byDepartment`는 executive/planning/orgLead 뷰(집계만), `byEmployee`는 hr 뷰에서만 정제 마스터와 조인해 성명 표시
- **monthly-report-mailer**: `summary`·`byOrgGroup` 집계만 인용(개인 행 금지)
- **people-data-auditor**: 위 '검증된 것' 항목을 정제 마스터에서 독립 재계산으로 대사. 상위 기대 이탈 조직: D03 14.94, D06 5.14, D02 3.29, D07 2.84, D05 2.83
