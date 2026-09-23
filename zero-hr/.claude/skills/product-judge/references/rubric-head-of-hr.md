# 루브릭 — 인사 총괄 옹호자 (`persona-advocate:head-of-hr`)

## 렌즈
"**월초 경영진 보고를 이 화면 하나로 끝낼 수 있고, 권한별로 안전하게 공유할 수 있는가.**" 인사 총괄은 매월 1~3일 경영진에게 재직·TO 과부족·월말/다음 달 전망·권고를 보고하고,
같은 데이터를 경영진·HR·경영기획·조직장에게 각자의 권한만큼 열어 준다(브리프 §9). 그가 두려워하는 것은 두 가지다 — 숫자가 뷰마다 다른 것, 개인명이 새는 것.
홈 제품은 Insight(`insight`)지만 세 제품 모두 채점한다: 홈이 아닌 제품은 "경영진 보고 준비 또는 HR 운영에서 이 화면을 열 이유가 있는가"로 본다.

## 공통 앵커 (모든 항목)
| 점수 | 뜻 |
|---|---|
| 0 | 해당 정보가 화면에 없다 |
| 3 | 있지만 조직 단위 또는 권한 경계가 없어 보고·공유에 쓸 수 없다 |
| 5 | 쓸 수 있으나 인사 총괄이 엑셀로 다시 정리해야 한다 |
| 8 | 화면만으로 보고 또는 공유가 끝난다 |
| 10 | 끝나고, 경영진의 다음 질문("그래서 뭘 하죠?")에 화면이 답한다 |

## 정성 항목
| id | 항목 | 필수 | 8점 조건 | 10점 추가 조건 | 근거 섹션(후보) |
|---|---|---|---|---|---|
| R1 | 한 화면 TO 과부족 | must | 조직 그룹(4)·조직(11) 단위로 재직/TO/월말 예측/gap(기준일·월말)이 한 표·한 차트에 있다(−16 → −11) | 발산 막대에 채용 가속·TO 재검토 조직이 색·라벨로 바로 보인다 | `department-gap`, `kpi` |
| R2 | 예측·권고의 결정 가능성 | must | 조직별 `recommendation` 라벨(정상 관리/채용 가속/TO 재검토·이동배치)과 다음 달 전망, 즉시 액션 3건 | 인사이트 카드에 숫자 근거(Engineering −7·Sales −4·Data & AI +7)와 action이 있고, 시나리오 플래너가 "가정"으로 표기된다 | `insights`, `department-forecast`, `scenario` |
| R3 | 권한별 뷰 분리의 정확성 | must | 4뷰(executive/hr/planning/orgLead)가 있고 뷰 전환 시 같은 KPI가 같은 값, 경영진·경영기획·조직장 뷰에 성명 없음, 조직장 뷰는 자기 조직만 | URL `?view=`로 링크 공유가 되고 뷰별 "숨긴 것" 안내가 있다 | `views`, 뷰별 `data-views` |
| R4 | 데이터 신뢰 신호 | nice | 클린징 보정 건수(17/31)·미해결 건수·미해결 질문 표·출처 배지(내장/Supabase)·기준일 | 브리프 불일치(215/119/62 vs 220/128/48) 기록이 보이고 정제 마스터 대사 결과가 표시된다 | `data-quality`, `header` |
| R5 | 리스크 해석 가능성 | nice | 밴드 집계·조직별 기대 이탈(3개월)이 경영진 뷰에, HR 뷰에 개인 목록(성명·등급·요인) — **점수 없음** | 요인 정의·가중치 근거(rule-based-v1)가 열린다 | `risk-summary`, `risk-people` |
| R6 | 경영진 보고 재사용 | nice | 월초 리포트 링크(`reports/monthly-report-2026-10.html`)와 조직별 forecast CSV, 자동화 효과 "(추정)" 타일 | 리포트 수치 = 화면 수치임이 표시되고 dispatch 상태(ready-to-send)가 보인다 | `header`, `automation-effect` |

제품 점수 = 6항목 평균(소수 1자리). must 항목이 3점 이하면 `mustFix`에 올린다.

## 홈이 아닌 제품을 볼 때
- Payroll Close: `headcount`(고용유형·조직별 급여 대상)와 `data-quality`는 R1·R4 참조용(5점 상한 — TO·권고 없음). 성명이 많은 화면이라 R3는 "권한 분리 없음"으로 0~3
- Onboarding: `teams`의 조직별 입사 예정과 `early-attrition`은 R2·R5의 보조(3~5점). R3는 0~3
- 낮은 점수는 결함이 아니라 통합 제품에서 이 화면들이 `hr`·`payroll`·`onboarding` 탭 뒤로 들어가야 함을 말한다

## 실격 조건 (해당 시 제품 점수 상한 적용 + `mustFix`)
| 조건 | 상한 | 확인 방법 |
|---|---|---|
| 경영진·경영기획·조직장 뷰 전용 섹션이 성명(`hrDirectory`·`.name`)을 참조한다 | 3 | `grep -n 'data-views="[^"]*"' site/insight/index.html \| grep -v '\bhr\b'` → 해당 섹션 렌더 코드에서 `hrDirectory|\.name` grep 0건 |
| 뷰마다 같은 지표가 다른 값이다(뷰별 재계산) | 3 | 렌더 코드에 뷰 조건부 합산(`reduce`·`sum` in view branch) 없음; KPI가 `DATA.stats.totals`·`DATA.forecast.totals`만 읽음 |
| 이직 리스크 **점수**가 어느 뷰에든 보인다 | 5 | `grep -c riskScore site/insight/index.html` → 0 |
| 권고를 "실행" 버튼·확정 문구로 만든다(승인 gate 위반) | 3 | `grep -niE '<button[^>]*>(실행|승인|채용 시작)' site/insight/index.html` → 0 |
| 생년월일이 스냅샷에 있다 | 3 | `grep -c birthDate site/data/insight.json` → 0 |

## must-have vs nice-to-have 요약
- **must-have**: R1 TO 과부족 · R2 예측·권고 · R3 권한별 뷰. 이 셋이 없으면 월초 보고는 여전히 엑셀이고 공유는 여전히 PDF다
- **nice-to-have**: R4 신뢰 신호 · R5 리스크 · R6 재사용. 없어도 보고는 되지만 "이 숫자 믿어도 되나"에 답하지 못한다

## note 작성법
점수마다 `note`에 근거 섹션(`data-section`)과 있었던 것/빠진 것을 한 문장으로. 예: `"department-gap에 11조직 gap은 있으나 recommendation 열이 없어 R2 5점"`.
