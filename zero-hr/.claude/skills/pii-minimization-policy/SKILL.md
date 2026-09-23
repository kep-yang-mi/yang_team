---
name: pii-minimization-policy
description: "개인 식별 정보(성명·생년월일·개인 리스크 점수) 최소화 정책. 어느 뷰·제품·리포트·데이터 파일에 성명이 허용되고 어디에는 없어야 하는지(DATA_CONTRACT §5·§15, 브리프 §9)를 정하고 grep으로 검증하는 방법을 준다. 리포트 뷰(executive/hr/planning/orgLead)·제품(Insight/Payroll Close/Onboarding)·통합 제품 역할 탭·월초 리포트·스냅샷·data/stats 파일을 만들거나 검사하는 모든 에이전트가 참조한다. 트리거: PII, 개인정보, 성명 노출, 생년월일, 익명화, 뷰별 권한, 경영진 뷰에 이름, 리스크 점수 표시, 성명 조인, hrDirectory."
---

# pii-minimization-policy — 개인 식별은 업무가 필요한 자리에만

## 규칙
개인 식별 정보는 **HR 뷰·Payroll Close·Onboarding(그리고 통합 제품의 hr·payroll·onboarding 탭) 밖으로 나가지 않는다.**
경영진·경영기획·조직장 뷰와 월초 리포트는 집계와 사번(`empId`/`joinerId`)만 쓴다. 생년월일은 정제 마스터 밖 **어디에도** 없다.
이직 리스크는 어느 화면에서도 **점수(`riskScore`)를 보이지 않고 등급(`riskBand`)만** 보인다. 급여액·보상은 범위 밖이다(GLOSSARY 제외).

## 왜
브리프 §9는 "같은 데이터를 모두에게 동일하게 보여주지 않는다"를 제품의 정의로 삼는다. 경영진이 개인명을 보면 "누가 나가는가"가 회의 안건이 되어
집계 리포트가 인사 조치 도구로 변질되고, 조직장이 타 조직 개인을 보면 조직 간 신뢰가 깨진다. 리스크 점수는 규칙 기반 추정치인데 숫자로 보이면
평가 점수처럼 읽힌다 — 등급은 "면담 우선순위"로, 점수는 "낙인"으로 소비된다. 생년월일은 연령대(`ageBand`)로 모든 업무가 끝나므로 남겨 둘 이유가 없고,
남겨 두면 스냅샷·Supabase·리포트 첨부로 퍼져 나가는 경로가 늘어난다. 최소화는 정보를 숨기는 게 아니라 **경로를 줄이는 것**이다.

## 경계표 — 어디에 무엇이 허용되는가
| 자리 | 성명 | 생년월일 | 리스크 | 비고 |
|---|---|---|---|---|
| `data/clean/headcount-master.clean.csv` | O | O | — | 유일한 원본. HR 뷰·급여·온보딩 조인의 출처 |
| `data/stats/headcount-stats.json` · `month-end-forecast.json` | X | X | — | `plannedJoiners/Leavers`도 사번·joinerId만 |
| `data/stats/attrition-risk.json` | X | X | 점수+등급(파일) | `byEmployee`에 `name` 없음. 화면은 등급만 |
| `data/stats/payroll-close.json` · `onboarding-plan.json` | O(업무상) | X | 등급만 | `ageBand`도 불필요. 코호트·`earlyAttrition`은 사번만 |
| `site/data/insight.json` | `hrDirectory`만 | X | 파일엔 점수, 화면은 등급 | `hrDirectory` = `empId,name,deptCode,department,level` 5필드 |
| Insight `executive` · `planning` · `orgLead` 뷰 | X | X | 밴드 집계만 | orgLead는 타 조직도 숨김, 건수만 |
| Insight `hr` 뷰 | O(조인) | X | 등급만 | 개인 목록·명부·클린징 오류 허용 |
| `site/data/payroll.json` · Payroll Close 화면 | O | X | X | 금액·계좌·세금 필드 없음 |
| `site/data/onboard.json` · Onboarding 화면 | O(입사 예정자·버디·조직장) | X(`plannedJoiners`에서 `birthDate` 제거) | 등급만 | 코호트는 사번만 |
| 통합 제품 `app` 탭 | `hr`·`payroll`·`onboarding`만 | X | 등급만 | §15. 나머지 3탭은 사번/집계 |
| `reports/*`(md/html/CSV) · dispatch | X | X | 밴드 집계만 | 경영진·경영기획·조직장이 함께 받는다 |
| 반환 JSON · 핸드오프 로그 · 심판/감사 산출물 | X | X | 집계 | 개인 행을 인용하지 않는다(사번·경로·건수만) |

## 어떻게 지키나
- 스냅샷 조립·병합은 **복사**만 한다. 성명이 필요한 자리는 `hrDirectory*`로 사번 조인하고, 정제 CSV를 페이지에 직접 싣지 않는다.
- Insight·app의 섹션은 `data-views`/`data-role`로 허용 뷰를 선언하고, `hr`(또는 `payroll`/`onboarding`)이 없는 섹션의 렌더 코드는 `hrDirectory`·`.name`을 참조하지 않는다.
- 리스크 표시 코드는 `riskBand`만 읽는다. `riskScore`는 정렬 키로도 쓰지 않는다(정렬 순서가 점수를 드러낸다).
- 리포트 템플릿은 `plannedSeparations.bySeparationReason`·`attrition.summary` 같은 집계 키만 읽는다.
- 빌더·mailer·통합 빌더는 반환값 `pii: {namesShownIn, birthDateAnywhere, riskScoreShown}`로 자기 보고한다.

## 어떻게 검증하나 (감사자·심판)
```bash
# 1. 생년월일이 정제 마스터 밖에 없다
grep -rl '"birthDate"' site/data data/stats reports 2>/dev/null            # 기대: 없음
# 2. 성명 필드가 허용 키 밖에 없다 (허용: hrDirectory*, payrollClose.*, onboardingPlan.timeline/byDepartment.buddyCandidates, plannedJoiners)
python3 -c "import json;d=json.load(open('site/data/insight.json'));print([k for k in ('stats','forecast','attrition') if '\"name\"' in json.dumps(d.get(k)) ])"   # 기대: []
# 3. 리스크 점수가 화면 코드에 없다
grep -n 'riskScore' site/*/index.html site/app/index.html 2>/dev/null       # 기대: 없음
# 4. 경영진·경영기획·조직장 전용 섹션이 명부를 참조하지 않는다
grep -n 'data-views="[^"]*"' site/insight/index.html | grep -v hr            # 이 섹션들의 렌더 함수에서 hrDirectory grep → 기대: 없음
# 5. 리포트에 성명이 없다 — 정제 마스터 성명 목록으로 grep
python3 -c "import csv;print(sum(1 for r in csv.DictReader(open('data/clean/headcount-master.clean.csv',encoding='utf-8')) if r['name'] in open('reports/monthly-report-2026-10.md',encoding='utf-8').read()))"   # 기대: 0
```
위반은 점수·상태와 무관하게 **fail/mustFix**다. 위반 값을 검사 산출물에 인용하지 않는다 — 섹션명·경로·건수만 적는다.
