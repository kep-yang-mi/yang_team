# 루브릭 — 온보딩 담당 옹호자 (`persona-advocate:onboarding`)

## 렌즈
"**이번 주·다음 주 누가 어느 조직으로 오고**, 준비가 됐고, 누가 맞이하는가를 월요일 아침에 이 화면 하나로 알 수 있는가." 온보딩 담당의 단위는 주(ISO 주차)와 조직이다 —
입사 예정자 27명(월말까지 19)이 6주에 걸쳐 11개 조직으로 흩어져 들어오고, Engineering 5명처럼 묶이는 조직은 같은 세션으로 처리한다.
홈 제품은 Onboarding(`onboard`)이지만 세 제품 모두 채점한다: 홈이 아닌 제품은 "입사 준비 중 이 화면을 열 이유가 있는가"로 본다.

## 공통 앵커 (모든 항목)
| 점수 | 뜻 |
|---|---|
| 0 | 해당 정보가 화면에 없다 |
| 3 | 있지만 주차 또는 조직 단위로 잘리지 않아 준비 계획에 쓸 수 없다 |
| 5 | 쓸 수 있으나 온보딩 담당이 명부·캘린더를 따로 열어야 한다 |
| 8 | 화면만으로 그 주의 준비가 끝난다 |
| 10 | 끝나고, 누구에게 무엇을 요청할지(조직장·버디·장비)까지 화면이 말해 준다 |

## 정성 항목
| id | 항목 | 필수 | 8점 조건 | 10점 추가 조건 | 근거 섹션(후보) |
|---|---|---|---|---|---|
| R1 | 주차별 타임라인 가독성 | must | ISO 주차별 입사자 카드(성명·조직·일자·고용유형·레벨), 이번 주/다음 주 강조, 합계 = 27 각주 | horizonEnd 이후 입사가 구분되고 월말(19) 경계가 보인다 | `timeline`, `kpi` |
| R2 | 조직 배치와 조직장 식별 | must | 조직별 입사 예정 수와 조직장(`deptLeadEmpId` 조인, 없으면 "미정")이 있다 | 조직의 현 인원·TO 부족(채용 가속 조직) 맥락이 함께 보인다 | `teams` |
| R3 | 체크리스트 진행 추적 | must | 입사자 × 6항목 매트릭스, 입사자별 진행률, "가상 생성(seed 고정)" 각주 | 항목별 완료율과 입사일까지 남은 일수 대비 지연 강조 | `checklist` |
| R4 | 버디 후보 적합성 | nice | 조직마다 후보 ≤3(성명·재직기간·레벨·리스크 등급)이 규칙(재직 2~6년·낮음·IC3~Lead) 그대로 | 후보가 없는 조직에 이유("조건 충족자 없음")가 보인다 | `teams` |
| R5 | 조기 이탈 신호 | nice | 90일 코호트(사번·조직·입사일·경과일·등급, 고위험 먼저)와 1년 미만 이탈률 | 조직별 이탈률과 코호트 고위험 수가 KPI로 올라온다 | `cohort`, `early-attrition` |
| R6 | 미해결 배지 노출 | nice | `plannedJoiners[].unresolvedFlags`가 타임라인 카드에 배지로 보인다 | 배지에서 클린저 질문(어느 조직인가 등)이 읽힌다 | `timeline` |

제품 점수 = 6항목 평균(소수 1자리). must 항목이 3점 이하면 `mustFix`에 올린다.

## 홈이 아닌 제품을 볼 때
- Insight: `planned-moves`(입사 예정 joinerId·조직·일자)는 R1의 골격으로 재사용 가능(5점 상한 — 주차 묶음·성명 없음). `risk-people`(HR 뷰)의 등급은 R4·R5의 근거(5점 상한)
- Payroll Close: `prorations-planned`의 예정 입사자(성명·조직·일자)는 R1 참조용(3~5점). 나머지는 대개 0
- 낮은 점수는 결함이 아니라 통합 제품이 `onboarding` 탭으로 무엇을 흡수해야 하는지의 지도다

## 실격 조건 (해당 시 제품 점수 상한 적용 + `mustFix`)
| 조건 | 상한 | 확인 방법 |
|---|---|---|
| 생년월일이 화면 또는 스냅샷에 있다 | 3 | `grep -c birthDate site/data/onboard.json site/onboard/index.html` → 0 (`plannedJoiners`에서 제거됐어야) |
| 90일 코호트·이탈률에 성명이 있다 | 5 | `python3 -c "import json;m=json.load(open('site/data/onboard.json'))['onboardingPlan']['earlyTenureCohort']['members'];print(any('name' in x for x in m))"` → False |
| 이직 리스크 **점수**가 보인다 | 5 | `grep -c riskScore site/onboard/index.html` → 0 (등급만) |
| 타임라인 합이 정제 입사 예정자 수(27)와 다르다 | 5 | `sum(len(w['joiners']) for w in timeline)` vs `len(plannedJoiners)` |

## must-have vs nice-to-have 요약
- **must-have**: R1 주차 타임라인 · R2 조직 배치·조직장 · R3 체크리스트. 이 셋이 없으면 월요일 준비 회의를 이 화면으로 할 수 없다
- **nice-to-have**: R4 버디 · R5 조기 이탈 · R6 미해결 배지. 없어도 입사일은 맞지만 정착 품질이 떨어진다

## note 작성법
점수마다 `note`에 근거 섹션(`data-section`)과 있었던 것/빠진 것을 한 문장으로. 예: `"teams에 조직별 입사 수는 있으나 deptLeadEmpId 조인이 없어 조직장이 비어 5점"`.
