# 01-collect — 원천 4종 + 조직 체계 가상 생성 (people-data-collector)

- 실행: 2026-09-23 · 기준일 2026-09-23 · 스킬 `people-data-integration` · 스크립트 `.claude/skills/people-data-integration/scripts/generate_synthetic_sources.py`
- 명령: `python3 /Users/yang/development/zero-hr/.claude/skills/people-data-integration/scripts/generate_synthetic_sources.py --root /Users/yang/development/zero-hr --as-of 2026-09-23 --self-check`
- 결과: `status: ok`, `selfCheck.passed: true` (121/121), 0.02초

## 시도한 것

1. v1 생성기(본부>실>팀 22팀, 직책, 스테이지 컬럼)를 패치하지 않고 v2 계약(§1·§2)에 맞춰 **압축 재작성**했다. v1에서 빌린 것: 결함 주입 로그 클래스, 일자 변형 함수(Excel 일련번호 1899-12-30 기준), 시드 고정, 재읽기 self-check 패턴.
2. 정답 인구를 먼저 만들었다. 조직별 HC/OL → 재직기간 구간(54/151/103/98) 무작위 배정 → 총경력 구간을 재직기간 순위와 짝지은 뒤 근접 순위(±45)만 교환(양의 상관 + 총경력 ≥ 재직기간 보장) → 연령대를 총경력 순위와 같은 방식(나이 ≥ 20 + 총경력) → 고용유형(인턴은 저경력 60명 중, CEO Office 전원 정규직) → 성별 무작위 → 레벨은 경력 점수 순위로 배정하되 조직별 VP(CEO Office 3, 나머지 1)와 재직 18명 이상 조직 Director 1을 먼저 확보.
3. 스테이지는 재직 406의 입사일 순위 49/200/340 경계에서 날짜가 겹치지 않게 +1일 조정한 뒤 경계일을 `company-stages.json`으로 썼다(Seed 2019-01-01~2020-03-07 / Series A ~2023-08-23 / Scale-up ~2025-07-30 / Enterprise 2025-07-31~).
4. 미해결 유형의 정답을 **클린저의 임시 배정값과 같게** 설계했다: date-logic 2명은 정답 자체가 미래 입사일(재직기간 0), org-unknown 2명은 정답 조직 = 직군 기본 매핑 조직(Growth Lab→Marketing D07, Platform→Engineering D03), missing-required 3명은 정답 계약종료일 빈값. 이렇게 하지 않으면 클린저가 §2-8대로 처리했을 때 §2-7 분포가 어긋난다.
5. 결함을 주입하고(마스터 12유형 105건 + TO 7 + 입사 6 + 퇴사 10 = 127건) 정답지 `injected-defects.json`(`summary`·`bySource`·`defects[]`, 미해결은 `trueValue:"(unresolved)"` + `assignedValue`)을 남겼다.
6. `--self-check`로 쓴 파일을 다시 읽어 정답지로 복원한 뒤 §2-7 전 수치·§2-5 결함 건수를 121개 항목으로 대조했다.

## 본 데이터·근거

- `.claude/DATA_CONTRACT.md` v2 §1(조직표·formerNames·stages 스키마), §2-1~2-6(헤더·행 수·결함 유형·정답지 스키마), §2-7(정본 수치 전부), §2-8(보정 규칙 = trueValue 정의), §7(핸드오프 5절), §14(테스트).
- `.claude/GLOSSARY.md` v2 — 재직 인원/휴직/총원, 레벨 IC1~VP, 스테이지 = 입사 시점 회사 단계, 퇴직 구분.
- `zero-company/zero_company_external_brief.md` §5~§8 — 계약이 채택한 원 수치(427/406/21/422/19/14, 클린징 17건·31건).
- 기존 v1 스크립트 두 개(기법만 참조, 구조는 폐기).

## 실패한 것

- **1차 self-check 실패 1건**: "마스터 org-* 합계 기대 17, 실제 19". §2-5 표의 org-* 5유형 건수 합은 6+4+3+4+2 = **19**인데 같은 절이 "org-* 마스터 합계 = 17"이라고 적어 계약 내부가 불일치한다. 브리프 원문이 "부서명 정규화 … 17건 **보정**"이므로 **해결된 보정 4유형(old-name·variant·typo·whitespace) = 17, org-unknown 2는 미해결 플래그(보정 아님)**로 해석해 self-check와 클린저 `orgNameCorrections` 정의를 맞췄다. 계약 §2-5 문구를 "해결된 org-* 합계 = 17 (+ org-unknown 2 미해결)"로 고치는 것을 제안한다 — 이 파일은 내 소유가 아니라 수정하지 않았다.
- 계약 §2-5 "(to-plan) org-variant | 조직 표기 3 · 기준월 포맷 4"에서 기준월 포맷의 defectType이 명시되지 않아 `date-format`으로 정했다(로그 rule도 동일).
- 브리프 §7 조직 그룹 합(Build 215 / GTM 119 / Ops 62)은 조직표 합(220/128/48)과 불일치 — 계약 지시대로 조직표를 정본으로 했다. 통계 단계가 `dataQuality.briefDiscrepancies`에 적어야 한다.
- 에이전트 정의 파일(`.claude/agents/people-data-collector.md`, `people-data-cleanser.md`)은 이번 산출 범위에 없어 만들지 않았다. 스킬 2종은 완성.

## 검증된 것

self-check 121/121 통과 (`selfCheck.aggregates` 그대로):

| deptCode | department | HC | OL | TO | in | out |
|---|---|---|---|---|---|---|
| D01 | CEO Office | 10 | 0 | 10 | 0 | 0 |
| D02 | Product | 51 | 3 | 54 | 3 | 1 |
| D03 | Engineering | 104 | 6 | 112 | 5 | 4 |
| D04 | Design | 25 | 1 | 26 | 1 | 1 |
| D05 | Data & AI | 40 | 2 | 34 | 2 | 1 |
| D06 | Sales | 58 | 3 | 62 | 3 | 3 |
| D07 | Marketing | 30 | 1 | 32 | 1 | 1 |
| D08 | Customer Success | 40 | 3 | 42 | 2 | 1 |
| D09 | People | 18 | 1 | 18 | 1 | 0 |
| D10 | Finance | 19 | 1 | 20 | 1 | 1 |
| D11 | Legal & Compliance | 11 | 0 | 12 | 0 | 1 |
| 합계 | | 406 | 21 | 422 | 19 | 14 |

- 조직 그룹(재직): Executive 10 · Build 220 · Go-To-Market 128 · Operations 48
- 고용유형(427): 정규직 354 · 계약직 31 · 인턴 19 · 파견 23 (휴직 21 = 정규직 19 · 계약직 2)
- 재직 406: 성별 여성 188/남성 195/미응답 23 · 연령대 20대 82/30대 221/40대 83/50대+ 20 · 직군 Engineering 116/Product 55/Design 25/Sales 58/Marketing 30/Customer Success 40/People 18/Finance 19/Legal 11/Data/AI 24/Executive 10(Data & AI = Data/AI 24 + Engineering 12 + Product 4) · 레벨 IC1 33/IC2 65/IC3 82/Senior 89/Lead 55/Manager 44/Director 25/VP 13 · 재직기간 1년 미만 54/1~3년 151/3~5년 103/5년+ 98 · 총경력 0~3년 56/3~7년 137/7~12년 142/12년+ 71 · 스테이지 Seed 49/Series A 151/Scale-up 140/Enterprise 66
- 레벨–재직기간 피어슨 상관 0.69(> 0.3). VP: CEO Office 3, 나머지 10개 조직 각 1. Director ≥ 1: 재직 18명 이상 9개 조직 전부.
- 퇴사 예정 14 사유: 자발퇴사 5 · 계약만료 3 · 조직개편 2 · 성과/적합도 2 · 개인사유 2 (계약만료 3명 전원 계약직/인턴/파견, stale 1명 E0251 2026-09-15) + 10월 4명(Eng/Sales/CS/Marketing) + unknown-emp E9999 = 19행
- 입사 예정 19(조직별 in 일치) + 10월 8(Engineering 3, Data & AI 2, Sales 2, Product 1) = 27행
- 계약종료일 90일 내 만료 24명(≥ 8). 정규직 계약종료일 빈값. 당월(9월) 입사 재직자 5명(급여 일할 계산 데모 가능).
- 결함(마스터): org-old-name 6 · org-variant 4 · org-typo 3 · org-whitespace 4 · org-unknown 2 · hire-date-format 31(`/`20 `.`6 `YYYYMMDD`3 Excel 2) · date-format 6 · date-logic 2 · status-inconsistency 3 · missing-required 3 · duplicate 8 · code-variant 32. TO: org-variant 3 · date-format 4. 입사: org-variant 2 · date-format 3 · code-variant 1. 퇴사: date-format 2 · reason-freetext 6 · stale 1 · unknown-emp 1. 총 127건.
- 행 수: 마스터 435(427+8) · TO 11 · 입사 27 · 퇴사 19 · org-chart 11. 결정성: 임시 루트 재실행 시 7개 파일 SHA-256 동일(`tests/test_cleansing.TestDeterminism`).

## 다음 agent 인계점

- **people-data-cleanser**가 이어받는다. 입력: `data/raw/*.csv` 4종 + `data/reference/org-chart.csv` + `data/reference/company-stages.json`. 정답지 `data/raw/injected-defects.json`은 대사(테스트)용이며 클린저 로직이 읽으면 안 된다.
- 클린저가 §2-8대로 처리하면 나와야 하는 값: rowsIn 435/11/27/19 → rowsOut 427/11/27/19, duplicatesRemoved 8, orgNameCorrections 17(+ org-unknown 2), hireDateCorrections 31, 미해결 12건(마스터 10: org-unknown 2 · date-logic 2 · status-inconsistency 3 · missing-required 3 / 퇴사 예정 2: stale 1 · unknown-emp 1), 경고 0건.
- 주의: **중복 해소를 먼저** 하고 조직 정규화를 해야 17이 나온다(제거되는 구버전 5행이 옛 소속명을 갖고 있다). 조직 분류 순서는 공백 → 변형(&↔and·대소문자) → 구명칭(formerNames) → 편집거리 ≤ 2 → unknown이어야 `Legal and Compliance`가 org-variant(formerNames에 있어도)로 분류된다.
- 미래 입사일 2명(E0426 2026-10-10, E0427 2026-10-21)은 재직기간 0·1년 미만·Enterprise로 집계돼야 분포가 맞는다. org-unknown 2명(E0281 Platform→D03, E0306 Growth Lab→D07)은 직군 기본 매핑으로 배정돼야 조직별 HC가 맞는다.
- 통계 단계에 전달할 데이터 품질 메모: 브리프 §7 그룹 합(215/119/62) vs 조직표 합(220/128/48) 불일치, §2-5 "17건" 해석(해결 보정만).
