---
name: people-data-integration
description: "고객사 원천 HR 데이터 4종(인원현황 마스터·TO 계획·입사 예정자·퇴사 예정자)과 조직 체계(org-chart)·스테이지 경계일을 DATA_CONTRACT v2 §1·§2 그대로 **가상 생성**하고, 의도적으로 주입한 결함의 정답지(injected-defects.json)를 남긴다. 파이프라인의 첫 단계(①)이며 '원천 데이터 생성', '가상 데이터', '데모 데이터 만들어', '인원현황 마스터 생성', 'TO 계획 원천', '입퇴사 예정자 원천', '결함 주입', '정답지', 'synthetic sources', 'people-data-integration', 'collect 단계' 요청 시 반드시 이 스킬을 사용할 것. 원천을 '다시', '재생성', '재실행', '수정', '보완', '업데이트', '기준일 바꿔서', '시드 그대로 다시' 만들라는 후속 요청도 이 스킬로 처리한다. 클린징(정제)은 people-data-cleansing 담당이므로 제외."
---

# people-data-integration — 원천 4종 + 조직 체계 가상 생성 (DATA_CONTRACT v2 §1·§2)

데모 고객사 ㈜온다테크의 원천 데이터를 **정답 → 결함 주입 → 정답지** 순서로 만든다.
클린저는 이 정답지로 재현율을 대사하고, 통계·예측·제품은 정제 결과가 §2-7 정본(재직 406 · 휴직 21 · TO 422 · in 19 · out 14)과
정확히 일치하는지 검증하므로, 이 단계에서 수치가 어긋나면 이후 모든 단계가 어긋난다. 생성은 반드시 번들 스크립트 한 곳에서만 한다.

## 입력 / 출력

| 구분 | 경로 | 비고 |
|---|---|---|
| 입력 | (없음 — 정본은 스크립트 상수) | `.claude/DATA_CONTRACT.md` §1·§2-7이 정본. 상수가 계약과 다르면 계약을 먼저 고친다 |
| 출력 | `data/reference/org-chart.csv` | §1 4그룹 > 11조직, `formerNames` 별칭 사전, 11행 |
| 출력 | `data/reference/company-stages.json` | Seed/Series A/Scale-up/Enterprise 경계일 — 재직 406의 입사일 순위 49/151/140/66으로 산출 |
| 출력 | `data/raw/headcount-master.csv` | §2-1 한글 헤더 15열, 정답 427 + 중복 8 = 435행, utf-8-sig |
| 출력 | `data/raw/to-plan.csv` · `planned-joiners.csv` · `planned-leavers.csv` | §2-2~2-4: 11 / 27 / 19행 |
| 출력 | `data/raw/injected-defects.json` | §2-6 정답지: `summary`·`bySource`·`defects[]`(rowRef/field/defectType/rawValue/trueValue[/assignedValue]) |
| stdout | 마지막 줄 요약 JSON 1행 | 워크플로우가 파싱하는 반환 데이터 |

## 절차

1. 실행 (기본값이 곧 데모 설정):
   ```bash
   python3 /Users/yang/development/zero-hr/.claude/skills/people-data-integration/scripts/generate_synthetic_sources.py \
     --root /Users/yang/development/zero-hr --as-of 2026-09-23 --self-check
   ```
   `--self-check`는 항상 켠다. 쓴 파일을 다시 읽어 정답지로 복원한 뒤 §2-7 전 수치와 §2-5 결함 건수를 121개 항목으로 대조한다.
2. stdout 마지막 줄을 읽는다. `status: "ok"` 이고 `selfCheck.passed: true` 여야 다음 단계(클린저)로 넘긴다.
   `status: "self-check-failed"` 이면 `selfCheck.failed[]`에 어긋난 항목이 "기대 X, 실제 Y"로 적힌다 — 파일은 이미 써졌지만 넘기지 않는다.
3. `selfCheck.aggregates`(조직별 HC/OL, 그룹 합, 속성 분포 8종, 레벨-재직기간 상관, 90일 내 계약 만료 수, in/out/사유)를 핸드오프 로그 `## 검증된 것`에 그대로 옮긴다.
4. 핸드오프 로그 `_workspace/handoff/01-collect.md`(시도/근거/실패/검증/인계점 5절)를 남긴다.

## 생성 규칙 (스크립트가 구현한 정의)

- **정답 인구**: 조직별 HC/OL을 §2-7 표대로 배치 → 재직기간 구간(54/151/103/98)을 무작위 배정하고 입사일로 환산 → 총경력 구간은 재직기간 순위와 짝지은 뒤 근접 순위끼리만 교환(양의 상관 + `총경력 ≥ 재직기간` 보장) → 연령대는 총경력 순위와 같은 방식(나이 ≥ 20 + 총경력) → 레벨은 경력 점수 순위로 배정하되 조직마다 VP 1(CEO Office 3), 재직 18명 이상 조직은 Director 1을 먼저 확보.
- **직군**: Data & AI = Data/AI 24 + Engineering 12 + Product 4, 그 외 조직은 자기 직군 100%.
- **고용유형**: 재직 406 = 정규직 335/계약직 29/인턴 19/파견 23, 휴직 21 = 정규직 19/계약직 2 → 총원 354/31/19/23. 인턴은 저경력 60명 중에서, CEO Office는 전원 정규직.
- **스테이지**: 재직 406을 입사일로 정렬해 49/200/340번째 경계에서 날짜가 겹치지 않게 조정한 뒤 경계일을 `company-stages.json`에 쓴다. 클린저가 이 파일로 파생하면 Seed 49 / Series A 151 / Scale-up 140 / Enterprise 66이 나온다.
- **미해결 유형의 정답 처리**: `date-logic` 2명은 정답 자체가 미래 입사일(재직기간 0, 1년 미만 구간·Enterprise), `org-unknown` 2명은 정답 조직 = 직군 기본 매핑 조직(Growth Lab→Marketing, Platform→Engineering), `missing-required` 3명은 정답 계약종료일이 빈값. 그래서 클린저가 §2-8대로 처리하면 집계가 정본과 정확히 같다.
- **퇴사 예정**: 14명(조직별 out, 사유 자발퇴사 5·계약만료 3·조직개편 2·성과/적합도 2·개인사유 2, 계약만료는 계약직/인턴/파견에게만, 1명은 기준일 −8일 = 2026-09-15 stale) + 다음 달 4명(Eng/Sales/CS/Marketing) + 마스터에 없는 사번 `E9999` 1행. 퇴사 예정자는 전원 재직자.
- **입사 예정**: 월말까지 19명(조직별 in) + 다음 달 8명(Engineering 3, Data & AI 2, Sales 2, Product 1).
- **계약종료일**: 계약직·인턴·파견만. 기준일 후 90일 내 만료를 10명 이상 강제(계약만료 퇴사자 포함 ≥ 8 보장).
- **중복 8행**: 같은 사번의 구버전(옛 소속명 5 · 한 단계 낮은 레벨 3), `최종수정일`이 더 오래됨. 5행은 정답 행 바로 앞, 3행은 임의 위치.
- **결함 주입**(마스터): org-old-name 6 · org-variant 4 · org-typo 3 · org-whitespace 4(앞/뒤/중간/전각 공백) · org-unknown 2 · hire-date-format 31(`/` 20, `.` 6, `YYYYMMDD` 3, Excel 일련번호 2) · date-format 6(휴직시작일 3, 계약종료일 3) · date-logic 2 · status-inconsistency 3 · missing-required 3 · duplicate 8 · code-variant 32(성별 8, 고용유형 9, 재직상태 8, 레벨 7). TO 계획 3+4, 입사 예정 2+3+1, 퇴사 예정 2+6+1+1. 주입 외 노이즈는 없다 — 클린징 로그는 정답지와 1:1이어야 한다.
- **결정성**: `random.seed(20260923)` 고정. 같은 `--as-of`면 바이트 단위로 같은 파일. 이름·사번은 매 실행 같다.

## stdout 요약 JSON (반환 데이터)

```json
{"status":"ok","mode":"synthetic-sources","asOfDate":"2026-09-23","client":"㈜온다테크","seed":20260923,
 "artifacts":["data/reference/org-chart.csv","data/reference/company-stages.json","data/raw/headcount-master.csv","..."],
 "rows":{"headcount-master":435,"to-plan":11,"planned-joiners":27,"planned-leavers":19,"org-chart":11},
 "defectSummary":{"org-old-name":6,"org-variant":9,"hire-date-format":31,"duplicate":8,"code-variant":33,"...":0},
 "defectsBySource":{"headcount-master":{"org-old-name":6,"org-variant":4,"org-typo":3,"org-whitespace":4,"org-unknown":2,"hire-date-format":31,"...":0}},
 "stages":[{"stage":"Seed","from":"2019-01-01","to":"2020-03-07"}],
 "selfCheck":{"passed":true,"checks":121,"failed":[],"aggregates":{"byDepartment":{},"byOrgGroup":{},"gender":{},"level":{},"stage":{},"levelTenureCorrelation":0.69}},
 "durationSeconds":0.02}
```
실패 시 `{"status":"self-check-failed","selfCheck":{"passed":false,"failed":["조직별 TO: 기대 …, 실제 …"]}}` 또는 `{"status":"error","errorType":"RuntimeError","error":"후보 부족: …"}`.
`defectSummary`는 원천 4종 합산(예: org-variant 9 = 마스터 4 + TO 3 + 입사 2), 마스터 단독 수치는 `defectsBySource.headcount-master`를 본다.

## 해석상 주의 — 부서명 정규화 "17건"

§2-5 표의 마스터 org-* 5유형 합은 19(6+4+3+4+2)지만 "부서명 정규화 17건 보정"은 **해결된 보정** 4유형(old-name·variant·typo·whitespace)의 합이다.
`org-unknown` 2건은 보정이 아니라 미해결 플래그(임시 배정)로 따로 센다. 클린저의 `orgNameCorrections`(17)와 `orgUnknown`(2)도 같은 정의를 쓴다.

## 오류 처리

- `RuntimeError: 후보 부족` — 결함을 심을 행이 모자람. 계약 수치를 바꿨을 때만 발생한다. `TARGET_DEPT`·분포 상수와 결함 건수를 함께 조정한다.
- `AssertionError`(구간 불일치) — 재직기간/총경력/연령 구간 경계 마진(`TENURE_RANGE`, `TOTAL_RANGE` 0.08, 나이 하한)이 깨진 경우. 상수를 고치기 전에 `--as-of`를 계약값으로 되돌려 재현되는지 먼저 확인한다.
- `self-check-failed` — `failed[]`의 첫 항목부터 본다. 대개 미해결 유형의 정답 처리 규칙(위 "미해결 유형의 정답 처리")을 어긴 수정 때문이다.
- 파일은 매번 전부 덮어쓴다(원천은 이 스킬의 산출물이므로 예외). `data/clean/` 이하는 건드리지 않는다.

## 재실행 · 수정 · 보완

- 다시 만들라는 요청은 같은 명령을 그대로 실행한다. 이전 산출물을 읽거나 병합하지 않는다 — 시드 고정이라 재실행이 곧 재현이다.
- 기준일 변경은 `--as-of`만 바꾼다. 월말·다음 달·stale(−8일)·90일 창이 모두 그 날짜 기준으로 재계산된다. 단 §2-7 정본 수치는 기준일과 무관한 상수다.
- 수치·분포·결함 건수를 바꾸는 요청은 먼저 `.claude/DATA_CONTRACT.md` §2-5·§2-7을 고치고, 그 다음 스크립트 상수(`TARGET_DEPT`, `GENDER` … `EXPECTED_DEFECTS`)와 `tests/test_contract.py`의 정본 상수를 같이 바꾼다. 계약이 정본이다.
- 원천을 바꾼 뒤에는 반드시 클린저(people-data-cleansing)를 재호출하고 `python3 -m unittest discover -s tests -v`를 돌린다.

## 핸드오프

- 다음 단계: `people-data-cleansing`(`cleanse.py`). 넘겨줄 것: 요약 JSON의 `artifacts`, `defectsBySource`, `stages`.
- 로그 위치: `_workspace/handoff/01-collect.md`. `## 검증된 것`에 `selfCheck.aggregates`를, `## 다음 agent 인계점`에 미해결 12건(마스터 10 + 퇴사 예정 2)이 클린저에서 플래그로 나와야 한다는 점을 적는다.
