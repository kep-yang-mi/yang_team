# 02-cleanse — 데이터 클린징 (people-data-cleanser)

- 실행: 2026-09-23 · 기준일 2026-09-23 · 스킬 `people-data-cleansing` · 스크립트 `.claude/skills/people-data-cleansing/scripts/cleanse.py`
- 명령: `python3 /Users/yang/development/zero-hr/.claude/skills/people-data-cleansing/scripts/cleanse.py --root /Users/yang/development/zero-hr --as-of 2026-09-23`
- 결과: `status: ok`, 0.01초. 검증: `python3 -m unittest tests.test_contract tests.test_cleansing -v` → 35/35 통과

## 시도한 것

1. v1 클린저(22팀 경로 매칭·자모 유사도·직책)를 버리고 v2 §2-8 규칙만 담은 **압축 재작성**을 했다(약 480행). 원천은 `utf-8-sig`로 읽고 절대 쓰지 않는다. `data/clean/`만 덮어쓴다.
2. 처리 순서를 **중복 해소 → 필드 정규화 → 논리 검사 → 파생**으로 고정했다. 중복은 사번별 `최종수정일` 최신 행(동일하면 뒤 행)만 남기고 제거 행마다 `duplicate` 로그(correctedValue = 살아남은 rowIndex)를 쓴다.
3. 조직 정규화(`OrgResolver`)는 org-chart의 `department`·`formerNames`만 기준으로 5단계로 분류한다: NFKC·공백 정리로 정규명 일치 → `org-whitespace`(1.0) / 대소문자·공백·`&`↔`and` 무시 일치 → `org-variant`(0.98) / formerNames 일치 → `org-old-name`(0.95) / 편집거리 ≤ 2 → `org-typo`(0.9) / 그 외 → 직군 기본 매핑으로 임시 배정 + `org-unknown`(0.5, 미해결). 조직 그룹은 org-chart에서 붙인다.
4. 일자 파서 하나로 `YYYY/MM/DD`·`YYYY.MM.DD`·`YYYYMMDD`·`YY.MM.DD`(20xx)·`YYYY년 M월 D일`·Excel 일련번호(4~6자리, 1899-12-30 기준)를 ISO로 바꾼다. 마스터 `입사일`만 rule `hire-date-format`, 나머지 일자(휴직시작일·계약종료일·생년월일·입사예정일·퇴사예정일·TO 기준월)는 `date-format`.
5. 코드 사전 매핑(성별·고용유형·재직상태·레벨) → `code-variant`, 퇴직사유 키워드 매핑 → `reason-freetext` + `separationType`(자발적/비자발적) 파생. 매핑 불가 값은 원값 유지 + `warnings`.
6. 논리 검사: 재직인데 입사일 > 기준일 → `date-logic`(값 유지, 재직기간 0) / 휴직인데 휴직유형 없음 → `기타` + `status-inconsistency` / 계약직·인턴·파견인데 계약종료일 없음 → `missing-required` / 퇴사 예정일 < 기준일 → `stale-planned-leaver` / 퇴사 예정 사번 미존재 → `unknown-emp`. 모두 `unresolvedFlags`에 `;`로 기록하고 행은 남긴다. 미해결마다 고객사 HR 확인 질문을 `unresolvedItems`에 넣었다.
7. 파생: ageBand(만 나이), tenureYears(2자리)/tenureYear/tenureBand, totalExperienceYears/Band, stage(company-stages.json), orgGroupCode/orgGroup. 생성기와 같은 공식을 쓴다.
8. `tests/test_contract.py`(계약 스키마·도메인 + §2-7 정본 독립 대사)와 `tests/test_cleansing.py`(정답지 재현율·rule/값 일치·미해결 플래그·요약 수치·중복 규칙·결정성)를 작성했다.

## 본 데이터·근거

- `.claude/DATA_CONTRACT.md` v2 §2-8(보정 규칙·confidence·unresolved), §3-1~3-6(정제 스키마·로그·요약), §14(테스트 요건), §7(핸드오프).
- `data/raw/*.csv` 4종(435/11/27/19행), `data/reference/org-chart.csv`(11행, formerNames), `data/reference/company-stages.json`(경계 4개).
- `data/raw/injected-defects.json`(127건) — 클린저 로직은 읽지 않고 **테스트에서만** 로그와 대사.
- 수집 단계 핸드오프 `_workspace/handoff/01-collect.md`의 인계점(중복 먼저, 분류 순서, 미래 입사 2명, org-unknown 2명 처리 기대값).

## 실패한 것

- 첫 테스트 실행에서 `test_org_fields_consistent_with_org_chart`가 KeyError — 입사 예정자 정제 스키마(§3-3)에는 `orgGroupCode`가 없는데 테스트가 있다고 가정했다. 테스트를 고쳤다(컬럼이 있을 때만 검사). 클린저 출력은 계약대로였다.
- 계약 §3-6 예시의 `unresolvedItems[].question` 문구는 org-unknown만 예시가 있어 나머지 5유형의 질문 문구는 내가 정했다(요약 파일 참조). 계약에 문구 정본이 필요하면 §3-6에 추가 제안.
- `orgNameCorrections`를 17로 맞추기 위해 §2-5의 "17건"을 **해결된 org-* 4유형 합**으로 해석했다(org-unknown 2는 `orgUnknown` 별도 키). §2-5 표 합(19)과의 불일치는 수집 단계 로그에 기록됨. 계약 문구 정정 제안 유지.
- 전체 `python3 -m unittest discover -s tests -v`에서는 다른 agent가 만든 `tests/test_reconciliation.py`가 `data/stats/month-end-forecast.json` 등 하류 산출물이 아직 없어 setUpClass 오류 2건, `test_site.py`는 7건 skip — **내 단계의 실패가 아니라 하류 미실행**이다. 내 소유 테스트 35건은 전부 통과.
- 에이전트 정의(`.claude/agents/people-data-cleanser.md`)는 요청 범위 밖이라 만들지 않았다.

## 검증된 것

- 요약(`data/clean/cleansing-summary.json`): rowsIn 435/11/27/19 → rowsOut **427**/11/27/19 · duplicatesRemoved **8** · orgNameCorrections **17** · orgUnknown 2 · hireDateCorrections **31** · unresolvedCount **12** · warnings 0건
- correctionsByRule(전 원천 합산 127 = 정답지 127): duplicate 8 · org-old-name 6 · org-variant 9(마스터 4 + TO 3 + 입사 2) · org-typo 3 · org-whitespace 4 · org-unknown 2 · hire-date-format 31 · date-format 15(마스터 6 + TO 4 + 입사 3 + 퇴사 2) · date-logic 2 · status-inconsistency 3 · missing-required 3 · code-variant 33(마스터 32 + 입사 1) · reason-freetext 6 · stale-planned-leaver 1 · unknown-emp 1
- 정답지 대사: **재현율 127/127 = 1.00**(같은 source+rowIndex+field), rule = defectType 127/127, correctedValue = trueValue 115/115(해결 건 전부), 정답지 밖 보정 0건
- 정제 마스터 독립 집계 = §2-7 정본: 재직 **406** · 휴직 **21** · 조직별 HC/OL 11행 전부 일치 · 그룹 Executive 10/Build 220/Go-To-Market 128/Operations 48 · 고용유형(427) 354/31/19/23(휴직 19/2) · 성별 188/195/23 · 연령대 82/221/83/20 · 직군 116/55/25/58/30/40/18/19/11/24/10 · 레벨 33/65/82/89/55/44/25/13 · 재직기간 54/151/103/98 · 총경력 56/137/142/71 · 스테이지 49/151/140/66. 파생 4종을 §2-8 공식으로 재계산해도 동일.
- TO 422(조직별 일치, effectiveMonth 전부 `2026-09`) · 입사 예정 19(+10월 8) · 퇴사 예정 14(+10월 4, unknown 1) · 사유 5/3/2/2/2 · Executive Snapshot 406/21/422/−16/19/14/**411**/**−11** · 권고 Engineering·Sales 채용 가속, Data & AI TO 재검토/이동배치
- 결정성: 임시 루트에서 생성기+클린저 재실행 → data/ 13개 파일 SHA-256 동일. 원천 미변경(원천에 중복 8행·`Legal and Compliance`·`HR`·`Growth Lab` 등 결함이 그대로 남아 있음을 테스트로 확인)

## 다음 agent 인계점

- **headcount-statistician**(→ forecaster, attrition, payroll, onboarding)이 이어받는다. 읽을 파일: `data/clean/headcount-master.clean.csv`(427행, `status` 재직 406/휴직 21), `to-plan.clean.csv`(11), `planned-joiners.clean.csv`(27, `joinerId` J001~J027), `planned-leavers.clean.csv`(19), `cleansing-summary.json`(데이터 품질 절용). `data/raw/`는 읽지 말 것.
- 통계 규칙 주의: `plannedOut` 14 = 퇴사 예정 중 `unknown-emp` 제외 + 예정일 ≤ 2026-09-30(stale E0251 2026-09-15 **포함**). 10월 4명은 `byMonth["2026-10"]`. date-logic 2명(E0426·E0427)은 재직 406에 포함되며 tenureYears 0.00·Enterprise.
- 고객사 HR 확인 질문 12건(`cleansing-summary.json.unresolvedItems` 그대로):
  1. E0031 / E0049 / E0273 — 휴직 상태인데 휴직유형이 없습니다. 유형을 확인해 주세요(기타로 임시 배정)
  2. E0046(계약직) / E0350(인턴) / E0370(인턴) — 계약종료일이 없습니다. 계약종료일을 확인해 주세요
  3. E0281 소속 `Platform` — 어느 조직 소속입니까?(직군 Engineering 기준 Engineering으로 임시 배정)
  4. E0306 소속 `Growth Lab` — 어느 조직 소속입니까?(직군 Marketing 기준 Marketing으로 임시 배정)
  5. E0426 입사일 2026-10-10 / E0427 입사일 2026-10-21 — 재직 상태인데 입사일이 기준일 이후입니다(재직기간 0으로 집계)
  6. 퇴사 예정 E0251 2026-09-15 — 예정일이 기준일 이전인데 마스터는 재직입니다. 실제 퇴사 여부 확인(예측에서는 퇴사 반영)
  7. 퇴사 예정 E9999 — 마스터에 없는 사번입니다(예측 제외)
- 급여 마감(payroll-close)용 힌트: 9월 입사 재직자 5명(E0419 09-05, E0420 09-08, E0422 09-10, E0424 09-10, E0425 09-20), 계약 만료 90일 내 24명, 휴직 21 = 육아휴직 12/질병휴직 5/기타 4(기타 3은 status-inconsistency 미확인 → risks에 올릴 것).
- 리포트 데이터 품질 절 문구: "부서명 정규화 17건(+미해결 2건 임시 배정), 입사일자 보정 31건, 중복 8행 제거, 미해결 12건 확인 요청, 브리프 §7 조직 그룹 합 불일치는 조직표 기준 채택".
