---
name: people-data-cleansing
description: "원천 4종(data/raw/*.csv)을 DATA_CONTRACT v2 §2-8 결정적 규칙으로 정제해 §3 정제 데이터(data/clean/*.clean.csv)·클린징 로그(cleansing-log.jsonl)·요약(cleansing-summary.json)을 만든다 — 조직 정규화(구명칭·변형·오탈자·공백 → deptCode + 조직 그룹), 일자 보정(YYYY/MM/DD·YYYYMMDD·Excel 일련번호 → ISO), 표기 정규화(성별·고용유형·재직상태·레벨·퇴직사유), 중복 해소, 파생 필드(연령대·재직기간·총경력·스테이지). 원천 생성 직후, '클린징', '정제', '데이터 정리', '부서명 정규화', '입사일 보정', '중복 제거', '미해결 항목', '클린징 로그', 'cleanse', 'people-data-cleansing' 요청 시 반드시 이 스킬을 사용할 것. 정제를 '다시', '재실행', '수정', '보완', '업데이트', '기준일 바꿔서' 하라는 후속 요청도 이 스킬로 처리한다. 통계 집계는 headcount-stats 담당이므로 제외."
---

# people-data-cleansing — 데이터 클린징 (DATA_CONTRACT v2 §2-8 → §3)

원천은 고객사 양식(한글 헤더, 표기 불일치, 중복)을 그대로 갖고 있다. 이 스킬은 그것을 **한 번의 결정적 실행**으로 정제 데이터로 바꾸고,
바꾼 모든 값을 로그 1행으로 남긴다. 통계·예측·리스크·제품은 오직 정제 데이터만 읽으므로, 여기서 재직 406 / 휴직 21이 나오지 않으면
이후 어떤 단계도 정본과 맞지 않는다. 원천은 절대 덮어쓰지 않고, 미해결 행도 지우지 않는다(플래그 + 확인 질문).

## 입력 / 출력

| 구분 | 경로 | 비고 |
|---|---|---|
| 입력(필수) | `data/raw/headcount-master.csv` · `to-plan.csv` · `planned-joiners.csv` · `planned-leavers.csv` | people-data-integration 산출물. utf-8-sig, §2 한글 헤더 |
| 입력(필수) | `data/reference/org-chart.csv` | 조직 정규화의 유일한 기준(`department`·`formerNames`) + 조직 그룹 |
| 입력(필수) | `data/reference/company-stages.json` | `stage` 파생 경계일 |
| 출력 | `data/clean/headcount-master.clean.csv` | §3-1 26열, 1사번 1행 427 |
| 출력 | `data/clean/to-plan.clean.csv` · `planned-joiners.clean.csv` · `planned-leavers.clean.csv` | §3-2~3-4 |
| 출력 | `data/clean/cleansing-log.jsonl` | §3-5 보정 1건 1행. `rule` = §2-5 defectType 어휘(정답지 대사용) |
| 출력 | `data/clean/cleansing-summary.json` | §3-6 + `orgUnknown`·`correctionsBySource`·`warnings`·`provenance` |
| stdout | 마지막 줄 요약 JSON 1행 | 워크플로우가 파싱하는 반환 데이터 |

## 절차

1. 원천 4종과 참조 2종이 있는지 확인한다. 없으면 실행하지 않고 `blocked`(수집 선행 필요)로 반환한다.
2. 실행:
   ```bash
   python3 /Users/yang/development/zero-hr/.claude/skills/people-data-cleansing/scripts/cleanse.py \
     --root /Users/yang/development/zero-hr --as-of 2026-09-23
   ```
   종료 코드 `0` 정상 · `1` 오류(산출물 불완전) · `3` 선행 산출물 없음.
3. 요약 JSON을 읽는다. 데모 정본이면 `totals` = 427/406/21, `duplicatesRemoved` 8, `orgNameCorrections` 17, `hireDateCorrections` 31,
   `unresolvedCount` 12, `warnings` 빈 배열이어야 한다. 하나라도 다르면 원천이 바뀐 것이므로 수집 단계의 `selfCheck`를 먼저 본다.
4. 정답지 대사: `python3 -m unittest tests.test_cleansing -v` — 주입 결함이 같은 `source+rowIndex+field`로 로그에 있는지(재현율 ≥ 0.97), rule 일치, correctedValue = trueValue, 미해결 플래그를 검사한다.
5. 핸드오프 로그 `_workspace/handoff/02-cleanse.md`를 남긴다. `## 다음 agent 인계점`에 미해결 12건의 질문 목록(`unresolvedItems`)을 그대로 옮긴다 — 고객사 HR에 확인할 항목이다.

## 보정 규칙 (스크립트가 구현한 §2-8)

처리 순서는 **중복 해소 → 필드 정규화 → 논리 검사 → 파생**이다. 중복을 먼저 지우므로 제거된 구버전 행의 옛 소속명은 보정으로 세지 않는다(그래서 17이 나온다).

| 상황 | 처리 | rule | confidence | unresolved |
|---|---|---|---|---|
| 같은 사번 복수 행 | `최종수정일` 최신 행만(동일하면 뒤 행). 제거 행마다 로그, `correctedValue` = 살아남은 rowIndex | `duplicate` | 1.0 | no |
| 소속: NFKC·공백 정리하면 정규명 | 앞뒤·중간·전각 공백 제거 | `org-whitespace` | 1.0 | no |
| 소속: 대소문자·공백·`&`↔`and` 무시하면 정규명 | 정규명으로 | `org-variant` | 0.98 | no |
| 소속: `formerNames` 별칭 | 정규 조직으로 | `org-old-name` | 0.95 | no |
| 소속: 편집거리 ≤ 2 | 가장 가까운 정규명/별칭 | `org-typo` | 0.9 | no |
| 소속: 매칭 없음 | 직군→조직 기본 매핑으로 임시 배정 + 질문 | `org-unknown` | 0.5 | **yes** |
| 입사일 포맷 변형 | `YYYY/MM/DD`·`YYYY.MM.DD`·`YYYYMMDD`·`YY.MM.DD`(20xx)·`YYYY년 M월 D일`·Excel 일련번호(1899-12-30 기준) → ISO | `hire-date-format` | 1.0 | no |
| 그 외 일자 포맷(휴직시작일·계약종료일·생년월일·입사예정일·퇴사예정일·TO 기준월) | 같은 파서 → ISO / `YYYY-MM` | `date-format` | 1.0 | no |
| 재직인데 입사일 > 기준일 | 값 유지, 재직기간 0으로 집계 | `date-logic` | null | **yes** |
| 휴직인데 휴직유형 없음 | `기타` 임시 배정 | `status-inconsistency` | 0.6 | **yes** |
| 계약직/인턴/파견인데 계약종료일 없음 | 빈값 유지 | `missing-required` | null | **yes** |
| 성별·고용유형·재직상태·레벨 변형 | 사전 매핑(F/female/여→여성, 빈값→미응답 / 정규·Regular·FT→정규직, Intern→인턴, Dispatch→파견 / 재직중·Active→재직, 휴직중·Leave→휴직 / ic1→IC1, IC-2→IC2, Sr→Senior, Mgr→Manager, Dir→Director) | `code-variant` | 1.0 | no |
| 퇴직사유 자유 텍스트 | 키워드(자발/계약·만료/조직·개편/성과·적합/개인/건강/정년) → 정규 사유. `separationType` 자발적(자발퇴사·개인사유·건강)/비자발적 | `reason-freetext` | 0.9 | no |
| 퇴사 예정일 < 기준일 | 플래그(예측에서는 퇴사로 반영) | `stale-planned-leaver` | null | **yes** |
| 퇴사 예정 사번이 마스터에 없음 | 플래그(예측 제외). 조직은 파일의 소속을 정규화 | `unknown-emp` | null | **yes** |

- **파생**: `ageBand`(기준일 만 나이 20대/30대/40대/50대+), `tenureYears`((기준일−입사일).days/365.25, 2자리, 미래 입사는 0), `tenureYear`(floor+1), `tenureBand`(1년 미만/1~3년/3~5년/5년+), `totalExperienceYears`(입사전경력/12 + tenureYears), `totalExperienceBand`(0~3년/3~7년/7~12년/12년+), `stage`(company-stages.json 경계, 경계 밖 미래 입사는 마지막 스테이지), `orgGroupCode/orgGroup`(org-chart).
- 퇴사 예정자의 `deptCode`는 **마스터 조직**을 쓴다(파일의 소속이 다르면 경고만).
- 매핑되지 않는 값은 원값을 유지하고 `warnings`에 적는다 — 조용히 버리지 않는다. 데모 원천에서는 경고가 0건이어야 한다.
- `unresolvedFlags`는 rule 이름을 `;`로 이어 쓴다. 미해결 행도 정제 데이터에 남기고 통계에 포함된다.

## stdout 요약 JSON (반환 데이터)

```json
{"status":"ok","mode":"cleansing","asOfDate":"2026-09-23",
 "artifacts":["data/clean/headcount-master.clean.csv","...","data/clean/cleansing-log.jsonl","data/clean/cleansing-summary.json"],
 "rowsIn":{"headcount-master":435,"to-plan":11,"planned-joiners":27,"planned-leavers":19},
 "rowsOut":{"headcount-master":427,"to-plan":11,"planned-joiners":27,"planned-leavers":19},
 "duplicatesRemoved":8,"orgNameCorrections":17,"orgUnknown":2,"hireDateCorrections":31,
 "correctionsByRule":{"duplicate":8,"org-old-name":6,"org-variant":9,"org-typo":3,"org-whitespace":4,"org-unknown":2,"hire-date-format":31,"date-format":15,"date-logic":2,"status-inconsistency":3,"missing-required":3,"code-variant":33,"reason-freetext":6,"stale-planned-leaver":1,"unknown-emp":1},
 "unresolvedCount":12,"totals":{"headcount":427,"activeHeadcount":406,"onLeave":21},"warnings":[],"durationSeconds":0.01}
```
실패 시 `{"status":"blocked|error","errorType":"FileNotFoundError|CleanseError|...","error":"..."}`. `blocked`는 선행 산출물 없음, `CleanseError`는 원천 헤더가 §2와 다름.
`orgNameCorrections`는 마스터의 해결된 org-* 4유형 합(17)이고 `org-unknown`(2)은 `orgUnknown`으로 따로 센다(§2-5 "17건" 해석 — people-data-integration SKILL 참조).

## 오류 처리

- `blocked` — 수집 단계(people-data-integration)를 먼저 돌린다. 이 스킬은 원천을 만들지 않는다.
- `CleanseError: 헤더 누락` — 원천이 계약 양식이 아니다. 원천을 고치지 말고 수집 단계에 돌려보낸다(원천 불변).
- `warnings`가 비어 있지 않음 — 매핑 사전에 없는 값이 있다. 값이 정당한 새 표기라면 §2-8 사전(계약)을 먼저 확장한 뒤 `GENDER_MAP` 등 스크립트 사전에 추가한다. 로그 없이 값을 고치지 않는다.
- `totals`가 406/21이 아님 — 클린저 문제가 아니라 원천/정답 문제일 가능성이 크다. `tests.test_cleansing`의 재현율·rule 일치가 통과하는지 먼저 보고, 통과하면 수집 단계 `selfCheck`를 본다.

## 재실행 · 수정 · 보완

- 원천이 바뀌었으면 그대로 다시 실행한다. 결정적이므로 이전 산출물을 읽거나 병합하지 않는다(`data/clean/`을 전부 덮어쓴다).
- 기준일 변경은 `--as-of`만 바꾼다. 연령대·재직기간·총경력·date-logic·stale 판정이 모두 그 날짜 기준으로 바뀐다.
- "이 값이 왜 이렇게 됐나"는 `cleansing-log.jsonl`에서 `rowRef.rowIndex`(원천 헤더 제외 0부터)로 찾는다. 정제 마스터의 `sourceRowIndex`가 같은 인덱스다.
- 규칙을 바꾸는 요청은 §2-8 계약 표를 먼저 고친다. rule 어휘를 새로 만들면 생성기 defectType과 `tests/test_cleansing.py`의 `RULES`에도 같이 넣는다.

## 핸드오프

- 다음 단계: `headcount-stats`(정제 마스터·TO·입퇴사 예정 읽음), 이어서 forecast·attrition·payroll·onboarding. 모두 `data/clean/`만 읽는다.
- 로그 위치: `_workspace/handoff/02-cleanse.md`. `## 검증된 것`에 요약 수치와 재현율, `## 다음 agent 인계점`에 미해결 12건 질문과 "date-logic 2명은 재직기간 0·Enterprise로 집계됨", "stale 1명은 예측에서 퇴사 반영·unknown-emp 1명은 예측 제외"를 적는다.
