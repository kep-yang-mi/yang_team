# 데이터 계약: ZeroHR 실시간 HR 리포트

용어는 `.claude/GLOSSARY.md`를 따른다. 이 문서는 **파일 경로·컬럼·JSON 필드의 정본**이다.
모든 스크립트·에이전트·검증자는 이 계약을 기준으로 읽고 쓴다. 계약에 없는 필드가 필요하면 계약을 먼저 고친다.

- 표기: CSV 헤더와 JSON 필드는 모두 **camelCase**. 원천(raw) CSV만 고객사 양식(한글 헤더)을 그대로 쓴다.
- 인코딩: UTF-8. 원천은 BOM이 있을 수 있다(읽을 때 `utf-8-sig`).
- 일자: 정제 이후는 항상 `YYYY-MM-DD`. 월은 `YYYY-MM`.
- 기준일(`asOfDate`): **2026-09-23**. 월말: 2026-09-30. 다음 달 말: 2026-10-31.
- 실행 환경: Python 3.9 표준 라이브러리만 사용(pandas 없음). `csv`, `json`, `random`, `datetime`, `statistics`.
- 난수: 가상 원천 생성은 `random.seed(20260923)`으로 고정 — 재실행 시 같은 데이터가 나와야 대사가 가능하다.

---

## 0. 디렉토리

```
zero-hr/
├── data/reference/org-chart.csv          # 조직 체계 (신뢰 기준표, 결함 없음)
├── data/raw/                             # ① 원천 데이터 (결함 포함) + 주입 결함 정답지
├── data/clean/                           # ② 정제 데이터 + 클린징 로그
├── data/stats/                           # ③ 인원 통계 · 월말 인원 예측 · 이직 리스크
├── personas/persona-needs.json           # 페르소나 3종 니즈 데이터 (제품 fit 기준)
├── products/product-comparison.json      # 제품 3종 비교 결과
├── site/                                 # ④ Vercel 정적 사이트: 허브 + 제품 3 + 데이터 스냅샷
│   ├── index.html                        #    허브 + 제품 비교
│   ├── insight/index.html                #    ZeroHR Insight (인사 총괄) — 리포트 뷰 3종
│   ├── payroll/index.html                #    ZeroHR Payroll (급여 담당)
│   ├── onboard/index.html                #    ZeroHR Onboard (온보딩 담당)
│   ├── data/{insight,payroll,onboard}.json  # 제품별 스냅샷
│   └── config.js                         #    Supabase URL/anon key (선택, 없으면 내장 JSON)
├── reports/                              # ④ 월초 리포트 (md + html + 발송 명세)
├── supabase/                             # 스키마 SQL + 적재/검증 스크립트
├── tests/                                # 로컬 테스트 (unittest)
└── _workspace/                           # 실행 메타·중간 산출물 (run_meta.json 등)
```

## 1. 조직 체계 — `data/reference/org-chart.csv`

고객사 ㈜온다테크의 정규 조직 구조. **본부 > 실 > 팀** 3단계. 이 표가 조직 정규화의 유일한 기준이다.

컬럼: `divisionCode,division,divisionEn,officeCode,office,officeEn,teamCode,team,formerNames,establishedOn`
- 영문 라벨(대시보드 부제·경영진 요약용): CEO직속=Corporate · 기술본부=Engineering · 사업본부=Sales & Marketing · 운영본부=Operations / 경영지원실=Corporate Services · 플랫폼개발실=Platform Engineering · AI연구실=Data & AI · 인프라실=Infrastructure · 디자인실=Design · 국내영업실=Domestic Sales · 글로벌사업실=Global Business · 마케팅실=Marketing · 고객경험실=Customer Experience · 품질관리실=Quality
- `formerNames`: 구 명칭을 `;`로 구분 (예: `서버개발팀;백엔드개발팀`). 없으면 빈 값
- `establishedOn`: 팀 발족일. 신설 예정 팀은 미래 일자

| divisionCode | division | officeCode | office | teamCode | team | formerNames | establishedOn |
|---|---|---|---|---|---|---|---|
| D0 | CEO직속 | O01 | 경영지원실 | T011 | 경영기획팀 | 전략기획팀 | 2019-01-01 |
| D0 | CEO직속 | O01 | 경영지원실 | T012 | 인사팀 | 피플팀 | 2019-01-01 |
| D0 | CEO직속 | O01 | 경영지원실 | T013 | 재무팀 | | 2019-01-01 |
| D0 | CEO직속 | O01 | 경영지원실 | T014 | 법무팀 | | 2021-03-01 |
| D1 | 기술본부 | O11 | 플랫폼개발실 | T111 | 백엔드팀 | 서버개발팀 | 2019-01-01 |
| D1 | 기술본부 | O11 | 플랫폼개발실 | T112 | 프론트엔드팀 | 웹개발팀 | 2019-01-01 |
| D1 | 기술본부 | O11 | 플랫폼개발실 | T113 | 모바일팀 | 앱개발팀 | 2020-01-01 |
| D1 | 기술본부 | O12 | AI연구실 | T121 | AI모델팀 | ML팀 | 2022-01-01 |
| D1 | 기술본부 | O12 | AI연구실 | T122 | 데이터팀 | 데이터플랫폼팀 | 2021-01-01 |
| D1 | 기술본부 | O12 | AI연구실 | T123 | AI에이전트팀 | | 2026-10-01 |
| D1 | 기술본부 | O13 | 인프라실 | T131 | SRE팀 | 인프라팀 | 2019-01-01 |
| D1 | 기술본부 | O13 | 인프라실 | T132 | 보안팀 | 정보보호팀 | 2020-06-01 |
| D1 | 기술본부 | O14 | 디자인실 | T141 | 프로덕트디자인팀 | UX팀 | 2020-01-01 |
| D2 | 사업본부 | O21 | 국내영업실 | T211 | 영업1팀 | | 2019-01-01 |
| D2 | 사업본부 | O21 | 국내영업실 | T212 | 영업2팀 | | 2021-01-01 |
| D2 | 사업본부 | O22 | 글로벌사업실 | T221 | 글로벌영업팀 | 해외영업팀 | 2022-01-01 |
| D2 | 사업본부 | O22 | 글로벌사업실 | T222 | 파트너십팀 | 제휴팀 | 2022-07-01 |
| D2 | 사업본부 | O23 | 마케팅실 | T231 | 브랜드팀 | 브랜드마케팅팀 | 2019-01-01 |
| D2 | 사업본부 | O23 | 마케팅실 | T232 | 퍼포먼스마케팅팀 | 디지털마케팅팀 | 2020-01-01 |
| D3 | 운영본부 | O31 | 고객경험실 | T311 | CS팀 | 고객지원팀 | 2019-01-01 |
| D3 | 운영본부 | O31 | 고객경험실 | T312 | 운영팀 | | 2019-01-01 |
| D3 | 운영본부 | O32 | 품질관리실 | T321 | QA팀 | 품질보증팀 | 2019-01-01 |

- 팀 22개 (AI에이전트팀은 2026-10-01 신설 예정 — 기준일 현원 0, TO 계획과 입사 예정자만 존재)
- 직군 ↔ 팀의 자연스러운 대응: 개발(백엔드·프론트엔드·모바일·SRE·보안·QA), AI연구(AI모델·AI에이전트), 데이터(데이터팀), 디자인(프로덕트디자인), 영업(영업1·2·글로벌영업·파트너십), 마케팅(브랜드·퍼포먼스), 경영지원(경영기획·인사·재무·법무), 운영(CS·운영). 팀장·실장·본부장은 해당 팀의 직군을 따른다.

## 2. 원천 데이터 (①) — `data/raw/`

고객사 양식 그대로(한글 헤더). **결함을 포함**하며, 결함은 `injected-defects.json`에 정답지로 남긴다.

### 2-1. `headcount-master.csv` — 인원현황 마스터

헤더(순서 고정):
`사번,성명,성별,생년월일,소속,직군,직책,스테이지,고용유형,재직상태,휴직유형,휴직시작일,입사일,퇴사일,계약종료일,입사전경력(개월),퇴직사유,최종수정일`

- `계약종료일`: 계약직·파견·인턴만 값이 있다(정규직은 빈값). 계약직은 입사일+12개월 또는 +24개월, 인턴은 +3~6개월, 파견은 +12개월 근방. 기준일 이후 90일 내 만료가 8명 이상 있어야 한다(급여 마감·HR 뷰에서 사용)

- `사번`: `E` + 4자리 (E0001~). 중복 행이 있을 수 있다(구버전 행). `최종수정일`이 늦은 행이 최신
- 규모: 기준일 현원(재직+휴직) **정확히 406명**(정제·중복 해소·상태 보정 후 기준), 퇴직자 행 약 70명(퇴사일 2025-01-01 ~ 2026-09-22, 그중 2026년 약 40명), 중복 행 6~10행
- **팀별 목표치는 §2-7 표의 값을 정확히 맞춘다** (데모 시나리오 수치가 사용자와 합의된 값이므로 ±허용 없음)
- 직책 분포: 본부장 1/본부(CEO직속은 없음), 실장 1/실, 팀장 1/팀(현원 0인 팀 제외), 파트장은 15명 이상 팀에 1~3명, 나머지 팀원. 임원은 C-level 3명(CEO직속 소속, 직군 경영지원)
- 스테이지 S1~S5: 재직기간·직책과 상관되게(팀장 이상은 S4~S5, 1~2년차는 S1~S2 위주)
- 휴직: 현원의 3~5%. 휴직유형 육아휴직(다수)/질병휴직/기타
- 고용유형: 정규직 약 82%, 계약직 약 10%, 파견 약 4%, 인턴 약 4%
- 성별: 전체 남 58% 여 42% 내외, 직군별 편차 허용(CS·마케팅·경영지원은 여성 비율 높게)
- 연령: 20대 22%, 30대 48%, 40대 24%, 50대 이상 6% 내외
- 입사전경력(개월): 연령·스테이지와 상관되게 0~300

### 2-2. `to-plan.csv` — TO 계획

헤더: `본부,실,팀,정원,기준월`
- 22개 팀 전부. `정원`은 §2-7 표의 TO 값 그대로(합계 **422**)
- `팀` 표기에 결함 허용(구 명칭·공백·영문). `기준월` 표기 변형(`2026-09`, `2026.09`, `202609`, `2026년 9월`)

### 2-3. `planned-joiners.csv` — 입사 예정자

헤더: `성명,소속,직군,직책,스테이지,고용유형,성별,생년월일,입사예정일,입사전경력(개월)`
- **27명**: 입사예정일 2026-09-24~09-30에 **19명**(팀별 배분은 §2-7 `in` 열 그대로), 2026-10-01~10-31에 8명(AI에이전트팀 3, 백엔드 1, 보안 1, 글로벌영업 1, 데이터 1, CS 1)
- 결함: 소속 영문/구명칭 1~2건, 일자 포맷 변형 2~3건

### 2-4. `planned-leavers.csv` — 퇴사 예정자

헤더: `사번,성명,소속,퇴사예정일,퇴직사유`
- **19행**: 퇴사예정일이 2026-09-30 이전인 유효 행 **14명**(팀별 배분은 §2-7 `out` 열 그대로; 이 14명 중 1명은 예정일 2026-09-15로 이미 지난 `stale-planned-leaver`), 2026-10-01~10-31에 4명(백엔드 1, CS 1, 영업1 1, 데이터 1), 그리고 마스터에서 이미 퇴직 처리된 사번 1행(`already-separated`, 예측에서 제외)
- 결함: 위 2건 외에 일자 포맷 변형 1~2건

### 2-5. 주입 결함 — 반드시 포함할 유형

| defectType | 설명 | 최소 건수 |
|---|---|---|
| `org-old-name` | 구 명칭 사용 (`서버개발팀`) | 12 |
| `org-typo` | 오탈자 (`프론트앤드팀`, `백앤드팀`) | 6 |
| `org-english` | 영문 표기 (`Backend Team`, `Data Team`) | 6 |
| `org-path` | 경로 표기 (`기술본부>플랫폼개발실>백엔드팀`, `기술본부/…`) | 10 |
| `org-whitespace` | 앞뒤·중간 공백, 전각 문자 (` 백엔드 팀 `) | 8 |
| `org-parent-only` | 팀 없이 실만 (`플랫폼개발실`) → 미해결 후보 | 3 |
| `date-format` | `2024.03.01` / `20240301` / `2024/3/1` / `24-03-01` / `2024년 3월 1일` / Excel 일련번호(`45352`) | 40 |
| `date-logic` | 퇴사일 < 입사일 (연도 오타), 휴직시작일 < 입사일 | 4 |
| `status-inconsistency` | 퇴직인데 퇴사일 없음 / 재직인데 퇴사일 있음 / 휴직인데 휴직유형 없음 | 6 |
| `duplicate` | 같은 사번 2행 (구버전은 소속·스테이지가 옛 값) | 6 |
| `code-variant` | 성별(`M`/`F`/`male`/`남성`), 고용유형(`정규`/`Regular`/`FT`/`계약`/`Contract`/`Intern`), 재직상태(`재직중`/`Active`/`휴직중`/`퇴사`/`Resigned`) | 30 |
| `reason-freetext` | 퇴직사유 자유 텍스트 (`타사 이직`, `이직(경쟁사)`, `개인 사정으로`, `계약 기간 만료`, `정년 퇴직`) | 20 |
| `stale-planned-leaver` | 퇴사 예정일이 이미 지남 | 1 |
| `already-separated` | 퇴사 예정자가 마스터에서 이미 퇴직 | 1 |

### 2-6. `injected-defects.json` — 주입 결함 정답지

```json
{
  "seed": 20260923,
  "generatedAt": "2026-09-23",
  "summary": { "org-old-name": 12, "date-format": 41, "...": 0 },
  "defects": [
    { "source": "headcount-master", "rowRef": { "사번": "E0123", "rowIndex": 45 },
      "field": "소속", "defectType": "org-old-name",
      "rawValue": "서버개발팀", "trueValue": "T111" }
  ]
}
```
- `trueValue`: 소속은 팀 코드, 일자는 ISO, 코드성 값은 정규 값, 중복은 살아남아야 할 행의 `rowIndex`
- `rowIndex`는 헤더 제외 0부터


### 2-7. 팀별 목표치 (정본 — 데모 시나리오 수치)

정제 후 기준일 현원(HC), TO, 월말(≤2026-09-30) 입사 예정(in)·퇴사 예정(out), 월말 예측(ME = HC + in − out), TO 과부족(gap = ME − TO).

| teamCode | team | HC | TO | in | out | ME | gap |
|---|---|---|---|---|---|---|---|
| T011 | 경영기획팀 | 8 | 8 | 0 | 0 | 8 | 0 |
| T012 | 인사팀 | 9 | 9 | 1 | 1 | 9 | 0 |
| T013 | 재무팀 | 10 | 10 | 0 | 0 | 10 | 0 |
| T014 | 법무팀 | 4 | 4 | 0 | 0 | 4 | 0 |
| T111 | 백엔드팀 | 46 | 50 | 4 | 2 | 48 | −2 |
| T112 | 프론트엔드팀 | 29 | 31 | 2 | 1 | 30 | −1 |
| T113 | 모바일팀 | 21 | 22 | 1 | 1 | 21 | −1 |
| T121 | AI모델팀 | 26 | 24 | 0 | 1 | 25 | +1 |
| T122 | 데이터팀 | 20 | 18 | 1 | 0 | 21 | +3 |
| T123 | AI에이전트팀 | 0 | 6 | 0 | 0 | 0 | −6 |
| T131 | SRE팀 | 17 | 18 | 1 | 0 | 18 | 0 |
| T132 | 보안팀 | 11 | 14 | 1 | 0 | 12 | −2 |
| T141 | 프로덕트디자인팀 | 16 | 16 | 0 | 1 | 15 | −1 |
| T211 | 영업1팀 | 23 | 25 | 1 | 1 | 23 | −2 |
| T212 | 영업2팀 | 22 | 22 | 1 | 2 | 21 | −1 |
| T221 | 글로벌영업팀 | 17 | 20 | 1 | 1 | 17 | −3 |
| T222 | 파트너십팀 | 10 | 10 | 0 | 0 | 10 | 0 |
| T231 | 브랜드팀 | 12 | 12 | 0 | 0 | 12 | 0 |
| T232 | 퍼포먼스마케팅팀 | 14 | 14 | 1 | 1 | 14 | 0 |
| T311 | CS팀 | 44 | 42 | 2 | 1 | 45 | +3 |
| T312 | 운영팀 | 27 | 27 | 1 | 1 | 27 | 0 |
| T321 | QA팀 | 20 | 20 | 1 | 0 | 21 | +1 |
| **합계** | | **406** | **422** | **19** | **14** | **411** | **−11** |

본부 합계: CEO직속 HC 31/TO 31/ME 31/gap 0 · 기술본부 HC 186/TO 199/in 10/out 6/ME 190/gap **−9** · 사업본부 HC 98/TO 103/in 4/out 5/ME 97/gap **−6** · 운영본부 HC 91/TO 89/in 4/out 2/ME 93/gap **+4**.
이 수치에서 인사이트 규칙(§4-2)이 "채용 가속 필요: Engineering(기술본부), Sales(국내영업실·글로벌사업실)" 와 "TO 재검토 필요: Data & AI(AI연구실 — 기존 팀 초과 + 신설 AI에이전트팀 미충원)" 를 도출해야 한다.

- 가상 원천 생성기는 **정답(true) 값 기준으로 이 표를 정확히 만족**시킨 뒤 결함을 주입한다. 즉 중복 행·상태 오류를 포함한 원천의 겉보기 수치는 달라도, 정제 후 수치는 표와 같아야 한다
- HC에는 휴직자가 포함된다(휴직 약 3~5%). 실근무 인원 = HC − 휴직

### 2-8. 결정적 보정 규칙 (생성기·클린저·검증자 공통)

같은 결함에 대해 생성기의 `trueValue`와 클린저의 `correctedValue`가 반드시 같아지도록 규칙을 고정한다.

| 상황 | 보정 | confidence | unresolved |
|---|---|---|---|
| 소속이 구 명칭·오탈자·영문·경로·공백 변형 | 조직 체계의 `team`/`formerNames`/영문 라벨/공백 제거 후 매칭 → 팀 코드 | 0.95~1.0 | false |
| 소속이 실만 있고 팀 없음 (`org-parent-only`) | 그 실의 팀 중 **직군이 일치하는 팀이 하나뿐이면** 그 팀, 아니면 실의 첫 팀을 임시 배정 | 0.5 | **true** |
| 일자 포맷 변형 | ISO로 변환. 2자리 연도는 20xx. Excel 일련번호는 1899-12-30 기준 | 1.0 | false |
| 퇴사일 < 입사일 (`date-logic`) | 퇴사일의 연도를 입사일 연도 이후로 해석할 수 있으면(연도 오타) 보정, 아니면 그대로 두고 플래그 | 0.7 / - | false / true |
| 휴직시작일 < 입사일 | 휴직시작일을 입사일로 보정 | 0.7 | true |
| 재직인데 퇴사일이 기준일 이전 | **상태를 퇴직으로 보정** (퇴사일이 우선) | 0.8 | true |
| 퇴직인데 퇴사일 없음 | 상태 유지(퇴직), 퇴사일 빈값, `separations` 집계에서 월 미상으로 분류 | - | true |
| 휴직인데 휴직유형 없음 | 휴직유형 `기타` | 0.6 | true |
| 같은 사번 복수 행 | `최종수정일` 최신 행만 유지 (동일하면 뒤 행) | 1.0 | false |
| 성별·고용유형·재직상태 표기 변형 | 사전 매핑 (M/male/남성→남, F/female/여성→여, 정규/Regular/FT→정규직, 계약/Contract→계약직, Dispatch→파견, Intern→인턴, 재직중/Active→재직, 휴직중/Leave→휴직, 퇴사/Resigned/Terminated→퇴직) | 1.0 | false |
| 퇴직사유 자유 텍스트 | 키워드 매핑 (이직·타사·경쟁사→이직, 창업→창업, 학업·유학→학업, 개인·가정→개인사정, 건강·질병→건강, 계약·만료→계약만료, 권고→권고사직, 정년→정년, 징계·해고→징계해고) | 0.9 | false |
| 퇴사 예정일이 기준일 이전 (`stale-planned-leaver`) | 플래그. 월말 예측에서는 퇴사로 반영 | - | true |
| 퇴사 예정자가 마스터에서 이미 퇴직 (`already-separated`) | 플래그. 예측에서 제외 | - | true |

## 3. 정제 데이터 (②) — `data/clean/`

### 3-1. `headcount-master.clean.csv`

헤더:
`empId,name,gender,birthDate,ageBand,divisionCode,division,officeCode,office,teamCode,team,jobFamily,position,stage,employmentType,status,leaveType,leaveStart,hireDate,terminationDate,contractEndDate,priorExperienceMonths,tenureYears,tenureYear,tenureBand,totalExperienceYears,separationType,separationReason,unresolvedFlags,sourceRowIndex`

- 정규 값: `gender` 남|여 · `status` 재직|휴직|퇴직 · `employmentType` 정규직|계약직|파견|인턴 · `leaveType` 육아휴직|질병휴직|기타|(빈값) · `position` 팀원|파트장|팀장|실장|본부장|임원 · `stage` S1~S5 · `jobFamily` 개발|AI연구|데이터|디자인|영업|마케팅|경영지원|운영
- `ageBand` 20대|30대|40대|50대 이상 — 기준일 만 나이
- `tenureYears` = (기준일 또는 퇴사일 − 입사일).days / 365.25, 소수 2자리
- `tenureYear` = floor(tenureYears) + 1 · `tenureBand` 1~2년차|3~5년차|6~10년차|11년차 이상
- `totalExperienceYears` = priorExperienceMonths/12 + tenureYears, 소수 2자리
- `separationType` 자발적|비자발적|기타|(빈값) · `separationReason` 이직|창업|학업|개인사정|건강|계약만료|권고사직|정년|징계해고|사망|(빈값)
  - 자발적: 이직·창업·학업·개인사정·건강 / 비자발적: 계약만료·권고사직·정년·징계해고 / 기타: 사망·기타
- `unresolvedFlags`: `;` 구분 (예: `org-parent-only;date-logic`). 빈값이면 완전 정제. **미해결 행도 삭제하지 않는다**
- 중복 해소 후 1사번 1행. `sourceRowIndex`는 살아남은 원천 행

### 3-2. `to-plan.clean.csv`
`teamCode,team,officeCode,divisionCode,toHeadcount,effectiveMonth`

### 3-3. `planned-joiners.clean.csv`
`joinerId,name,teamCode,team,jobFamily,position,stage,employmentType,gender,birthDate,plannedHireDate,priorExperienceMonths,unresolvedFlags` — `joinerId`는 `J001`부터 부여

### 3-4. `planned-leavers.clean.csv`
`empId,teamCode,plannedTerminationDate,separationType,separationReason,unresolvedFlags`
- `already-separated`는 `unresolvedFlags`에 표기하고 예측에서 제외, `stale-planned-leaver`는 플래그 후 **월말 예측에서는 퇴사로 반영**(예정일이 지났으므로)

### 3-5. `cleansing-log.jsonl` — 1행 1보정
```json
{"source":"headcount-master","rowRef":{"사번":"E0123","rowIndex":45},"field":"소속","rawValue":"서버개발팀","correctedValue":"T111","rule":"org-old-name","confidence":0.98,"unresolved":false}
```
`rule` 값은 2-5의 `defectType`과 같은 어휘를 쓴다 — 그래야 정답지와 기계적으로 대사된다.

### 3-6. `cleansing-summary.json`
```json
{ "asOfDate":"2026-09-23", "rowsIn":{"headcount-master":0,"to-plan":0,"planned-joiners":0,"planned-leavers":0},
  "rowsOut":{...}, "duplicatesRemoved":0, "correctionsByRule":{"org-old-name":0}, "unresolvedCount":0,
  "unresolvedItems":[{"source":"headcount-master","rowRef":{},"field":"소속","rawValue":"플랫폼개발실","question":"어느 팀 소속입니까?"}] }
```

## 4. 통계·예측 (③) — `data/stats/`

### 4-1. `headcount-stats.json` — 인원 통계
```json
{
  "asOfDate":"2026-09-23", "client":"㈜온다테크",
  "totals":{"headcount":0,"activeHeadcount":0,"onLeave":0,"separatedYtd":0,"turnoverRateYtd":0.0,"unresolvedCount":0},
  "byDivision":[{"divisionCode":"D1","division":"기술본부","headcount":0,"activeHeadcount":0,"onLeave":0}],
  "byOffice":[{"officeCode":"O11","office":"플랫폼개발실","divisionCode":"D1","headcount":0,"activeHeadcount":0,"onLeave":0}],
  "byTeam":[{"teamCode":"T111","team":"백엔드팀","officeCode":"O11","divisionCode":"D1","headcount":0,"activeHeadcount":0,"onLeave":0}],
  "byAttribute":{"employmentType":{},"status":{},"gender":{},"ageBand":{},"jobFamily":{},"position":{},"tenureBand":{},"stage":{},"leaveType":{}},
  "crossTabs":{"divisionByEmploymentType":{},"divisionByGender":{},"divisionByAgeBand":{},"jobFamilyByStage":{},"jobFamilyByGender":{},"positionByGender":{}},
  "experience":{"avgTenureYears":0.0,"medianTenureYears":0.0,"avgTotalExperienceYears":0.0,"medianTotalExperienceYears":0.0,
                "tenureYearsHistogram":{"0-1":0,"1-3":0,"3-5":0,"5-10":0,"10+":0},
                "totalExperienceHistogram":{"0-3":0,"3-7":0,"7-12":0,"12-20":0,"20+":0},
                "byDivision":[{"divisionCode":"D1","avgTenureYears":0.0,"avgTotalExperienceYears":0.0}]},
  "separations":{"ytd":{"total":0,"bySeparationType":{},"bySeparationReason":{},
                        "byMonth":[{"month":"2026-01","count":0,"자발적":0,"비자발적":0,"기타":0}],
                        "byDivision":{},"byTenureBand":{}},
                 "prevYear":{"total":0,"bySeparationType":{}}},
  "provenance":{"source":"data/clean/headcount-master.clean.csv","script":".claude/skills/headcount-stats/scripts/compute_stats.py"}
}
```
- 속성 통계와 크로스탭은 **현원(재직+휴직)** 기준. 퇴직자는 `separations`에서만 집계
- `turnoverRateYtd` = 2026년 퇴직자 수 ÷ ((2025-12-31 현원 + 기준일 현원)/2), 소수 4자리
- 모든 카운트 딕셔너리의 합은 `totals.headcount`와 같아야 한다 (대사 조건)

### 4-2. `month-end-forecast.json` — 월말 인원 예측 + TO 과부족
```json
{
  "asOfDate":"2026-09-23","monthEnd":"2026-09-30","nextMonthEnd":"2026-10-31",
  "assumptions":["입사 예정자는 예정일에 전원 입사한다","퇴사 예정자는 예정일에 전원 퇴사한다","휴직자는 현원에 포함한다","..."],
  "byTeam":[{"teamCode":"T111","team":"백엔드팀","officeCode":"O11","divisionCode":"D1",
             "toHeadcount":0,"headcount":0,"plannedIn":0,"plannedOut":0,"forecastMonthEnd":0,
             "toGapAsOf":0,"toGapMonthEnd":0,
             "nextMonth":{"plannedIn":0,"plannedOut":0,"forecastNextMonthEnd":0,"toGapNextMonthEnd":0},
             "riskAdjusted":{"expectedAttrition":0.0,"forecastNextMonthEndRiskAdjusted":0.0}}],
  "byDivision":[{"divisionCode":"D1","division":"기술본부","toHeadcount":0,"headcount":0,"plannedIn":0,"plannedOut":0,"forecastMonthEnd":0,"toGapMonthEnd":0,"nextMonth":{...}}],
  "totals":{"toHeadcount":0,"headcount":0,"plannedIn":0,"plannedOut":0,"forecastMonthEnd":0,"toGapMonthEnd":0,"toFillRate":0.0,"nextMonth":{...}},
  "plannedJoiners":[{"joinerId":"J001","teamCode":"T111","plannedHireDate":"2026-09-28","employmentType":"정규직"}],
  "plannedLeavers":[{"empId":"E0123","teamCode":"T311","plannedTerminationDate":"2026-09-30","separationType":"자발적"}],
  "insights":[{"type":"채용 가속 필요","scope":"division","code":"D1","label":"기술본부 (Engineering)","toGapMonthEnd":-9,"rationale":"...","action":"..."},
              {"type":"채용 가속 필요","scope":"office","code":"O21+O22","label":"국내영업실·글로벌사업실 (Sales)","toGapMonthEnd":-6,"rationale":"...","action":"..."},
              {"type":"TO 재검토 필요","scope":"office","code":"O12","label":"AI연구실 (Data & AI)","toGapMonthEnd":-2,"rationale":"기존 팀 초과(+4) + 신설 AI에이전트팀 미충원(−6)","action":"TO 재배분 검토"}],
  "provenance":{...}
}
```

**인사이트 규칙 (결정적):**
- `채용 가속 필요`: 본부 단위 `toGapMonthEnd ≤ −5`, 또는 같은 기능의 실 묶음(국내영업실+글로벌사업실 = Sales) 합계 `≤ −5`
- `TO 재검토 필요`: 실 단위에서 초과 팀(gap ≥ +1)과 부족 팀(gap ≤ −3)이 공존하거나, 신설 팀(현원 0)이 있음 — 재배분 여지
- `초과 인원 검토`: 팀 단위 `toGapMonthEnd ≥ +3`
- 인사이트마다 `rationale`(숫자 근거)과 `action`(다음 달 권고 조치) 필수
- `forecastMonthEnd` = headcount + plannedIn(≤ monthEnd) − plannedOut(≤ monthEnd)
- `toGap*` = 인원 − toHeadcount (양수 초과, 음수 부족). `toFillRate` = forecastMonthEnd / toHeadcount
- `riskAdjusted`는 `attrition-risk.json`의 팀별 `expectedAttritionNext3Months`를 1/3로 월할하여 다음 달 말에 반영. 시나리오이며 기본 예측을 대체하지 않는다

### 4-3. `attrition-risk.json` — 이직 리스크 (고도화)
```json
{
  "asOfDate":"2026-09-23",
  "model":{"name":"rule-based-v1","factors":[{"factor":"tenure-2-4y","weight":20,"rationale":"..."}],
           "bands":{"높음":"score>=60","중간":"35<=score<60","낮음":"score<35"}},
  "byEmployee":[{"empId":"E0123","teamCode":"T111","riskScore":72,"riskBand":"높음","topFactors":["tenure-2-4y","stage-stagnation"]}],
  "byTeam":[{"teamCode":"T111","headcount":0,"높음":0,"중간":0,"낮음":0,"avgRiskScore":0.0,"expectedAttritionNext3Months":0.0}],
  "byDivision":[...],
  "summary":{"높음":0,"중간":0,"낮음":0,"expectedAttritionNext3Months":0.0}
}
```
- 재직자만(휴직 포함) 점수화. `byEmployee`에는 **성명을 넣지 않는다** — HR 뷰가 정제 마스터에서 조인한다
- `expectedAttritionNext3Months` = Σ(밴드별 확률 × 인원): 높음 0.35, 중간 0.12, 낮음 0.03 (모델 문서에 명시)

## 5. 제품·사이트 (④) — `site/`

세 제품은 **같은 공통 데이터 계층**을 읽고, 페르소나 전용 파생 데이터(§10 급여 마감, §11 온보딩 계획)를 얹는다.

| 제품 | 페르소나 | 경로 | 스냅샷 | 핵심 화면 |
|---|---|---|---|---|
| ZeroHR Insight | 인사 총괄 (head-of-hr) | `site/insight/index.html` | `site/data/insight.json` = `{stats, forecast, attrition, cleansingSummary, hrDirectory, automationEffect}` | 리포트 뷰 3종(경영진 `executive` / HR `hr` / 경영기획 `planning`) 역할 선택기 — 인원 통계 · 월말 예측 · TO 과부족 · 인사이트 · 이직 리스크 |
| ZeroHR Payroll | 급여 담당 (payroll) | `site/payroll/index.html` | `site/data/payroll.json` = `{payrollClose, statsSubset, cleansingSummary}` | 월말 급여 대상 확정 · 일할 계산 대상 · 휴직 처리 · 계약 만료 · 급여 오류 위험 |
| ZeroHR Onboard | 온보딩 담당 (onboarding) | `site/onboard/index.html` | `site/data/onboard.json` = `{onboardingPlan, plannedJoiners, hrDirectorySubset}` | 주차별 입사 타임라인 · 팀 배치 · 체크리스트 · 신설팀 · 버디 · 90일 코호트 |
| 허브 | 전체 | `site/index.html` | `site/data/comparison.json` = §13 | 제품 3 진입 카드 + 페르소나별 니즈 충족(fit) 비교 |

- 각 제품 HTML은 스냅샷 JSON을 `<script id="report-data" type="application/json">`으로 **내장**하고, `site/config.js`에 Supabase 설정이 있으면 `report_snapshots` 최신 행을 fetch해 **덮어쓴다**(실시간). fetch 실패 시 내장 데이터로 동작 — 오프라인에서도 열린다
- 공통 헤더: 제품명 · 고객사 · 기준일(`asOfDate`) · 데이터 출처(내장/Supabase) · 허브로 돌아가기
- 같은 지표는 제품·뷰가 달라도 같은 값 — `reconciliation-policy`. 개인 식별은 `pii-minimization-policy`(Insight HR 뷰, Payroll·Onboard는 업무상 성명 필요 → 성명 허용하되 생년월일은 연령대로)
- 외부 스크립트는 cdnjs.cloudflare.com 또는 cdn.jsdelivr.net/npm/ 만 허용(차트는 Chart.js 또는 순수 SVG). 폰트는 시스템 폰트. 모바일 폭(375px)에서 가로 스크롤 없이 열려야 한다
- `vercel.json`: `{"cleanUrls": true, "trailingSlash": false}` — 정적 배포, 빌드 없음

## 6. 월초 리포트 (④) — `reports/`

- `reports/monthly-report-2026-10.md` — 본문 (한국어). 구조: 요약 KPI → 9월 결산(조직별 현원·TO 과부족·퇴직) → 10월 전망(입·퇴사 예정, 월말 예측, 리스크 시나리오) → 데이터 품질(미해결 항목) → 부록(정의)
- `reports/monthly-report-2026-10.html` — 이메일용 HTML(인라인 스타일, 외부 리소스 없음)
- `reports/monthly-report-dispatch.json` — 발송 명세: `{"sendAt":"2026-10-01T09:00:00+09:00","schedule":"0 9 1 * *","recipients":{"executive":[...],"hr":[...],"planning":[...]},"subject":"...","attachments":["dashboard/index.html"],"status":"ready-to-send","gate":"session-constraint"}`
- 수신자는 가상 주소(`@ondatech.example`)만 사용

## 7. 실행 메타 — `_workspace/run_meta.json`
`{"runId":"...","startedAt":"...","finishedAt":"...","asOfDate":"2026-09-23","phasesCompleted":[...],"artifacts":[...],"durations":{"collect":0,"cleanse":0,"stats":0,"forecast":0,"attrition":0,"publish":0,"totalSeconds":0}}`

## 8. 기대 효과 4종의 증빙 산출물

| 기대 효과 | 기능 요건 | 증빙 |
|---|---|---|
| ① 월 리포트 수작업 → 완전 자동화 (리소스 80% 절감) | 원천 4종 투입 → 대시보드·월초 리포트까지 **사람 개입 없이** 한 번의 오케스트레이터 실행으로 완료 | `_workspace/run_meta.json`의 단계별 실행 시간 + `data/stats/automation-effect.json` (수작업 공수 추정 vs 자동화 후 검토 공수, 절감률 — 추정임을 명시) |
| ② 경영진 실시간 인원 현황 조회 | 대시보드 경영진 뷰: 기준일·현원·월말 예측·TO 충족률·본부별 현황을 링크 하나로 열람. 재실행 시 갱신 | `dashboard/index.html` + claude.ai Artifact 링크 |
| ③ 인력계획 선제 대응 | 월말 인원 예측 + TO 과부족 + 인사이트(채용 가속/TO 재검토/초과 검토) + 이직 리스크 시나리오 | `data/stats/month-end-forecast.json`의 `insights`, `riskAdjusted` |
| ④ 월간 리포트 자동 생성·배포 | 같은 통계에서 월초 리포트 md/html을 생성하고 수신자·일정(`0 9 1 * *`)까지 명세 | `reports/monthly-report-2026-10.*` + `reports/monthly-report-dispatch.json` |

`data/stats/automation-effect.json`:
```json
{"asOfDate":"2026-09-23","manualBaseline":{"hoursPerMonth":40,"breakdown":{"수집·통합":8,"클린징":12,"집계·예측":12,"리포트 작성·배포":8},"basis":"중견기업 HR 월간 인원 리포트 수작업 공수 추정(가정)"},
 "automated":{"pipelineSeconds":0,"humanReviewHoursPerMonth":8,"breakdown":{"미해결 항목 확인":3,"리포트 검토·승인":5}},
 "savingRate":0.8,"note":"절감률은 가정 기반 추정치이며 고객사 실측으로 갱신한다"}
```


## 9. 페르소나 니즈 데이터 — `personas/persona-needs.json`

```json
{
  "asOfDate":"2026-09-23","client":"㈜온다테크",
  "personas":[
    {"code":"head-of-hr","title":"인사 총괄","titleEn":"Head of HR","product":"insight",
     "profile":"...", "goals":["..."],
     "jobsToBeDone":[{"id":"H1","job":"매월 초 경영진에게 인원 현황과 다음 달 전망을 보고한다","trigger":"월초","frequency":"monthly","importance":5}],
     "calendar":[{"when":"매월 1~3일","task":"..."},{"when":"수시","task":"..."}],
     "keyQuestions":["지금 우리 현원은? TO 대비 어디가 비었나?"],
     "kpis":[{"name":"TO 충족률","definition":"...","source":"forecast.totals.toFillRate"}],
     "pains":[{"pain":"엑셀 취합 수작업","costHoursPerMonth":12}],
     "requiredFields":["headcount-master.status","to-plan.toHeadcount","planned-leavers"],
     "decisions":["채용 가속/보류","TO 재배분"],
     "fitCriteria":[{"id":"H-F1","criterion":"본부별 TO 과부족을 한 화면에서 본다","weight":5,"evidence":"month-end-forecast.byDivision"}]
    }
  ],
  "shared":{"commonNeeds":["..."],"conflicts":["급여는 성명 필수 vs 경영진 뷰는 익명"],"dataLayerImplications":["..."]}
}
```
- 페르소나마다 `jobsToBeDone` 5개 이상, `fitCriteria` 8개 이상(각각 `weight` 1~5와 어느 데이터로 충족되는지 `evidence`)
- `pains.costHoursPerMonth`의 합이 §8 자동화 효과의 수작업 기준(40h)과 정합해야 한다

## 10. 급여 마감 — `data/stats/payroll-close.json` (급여 담당 전용)

```json
{
  "asOfDate":"2026-09-23","payPeriod":"2026-09","periodStart":"2026-09-01","periodEnd":"2026-09-30",
  "payrollHeadcount":{"asOf":0,"monthEnd":0,"byEmploymentType":{},"byDivision":[],"byTeam":[]},
  "prorations":{"joinersInPeriod":[{"empId":"E0411","name":"...","teamCode":"T111","hireDate":"2026-09-08","employmentType":"정규직","workedDays":0,"proratedRatio":0.0}],
                "leaversInPeriod":[{"empId":"...","name":"...","teamCode":"...","terminationDate":"2026-09-12","separationType":"자발적","workedDays":0,"proratedRatio":0.0}],
                "plannedJoinersByMonthEnd":[...],"plannedLeaversByMonthEnd":[...]},
  "leaves":{"onLeave":[{"empId":"...","name":"...","teamCode":"...","leaveType":"육아휴직","leaveStart":"...","payrollTreatment":"무급(정부 급여)"}],
            "byTreatment":{"무급(정부 급여)":0,"유급":0,"무급":0}},
  "contracts":{"expiringWithin90Days":[{"empId":"...","name":"...","teamCode":"...","employmentType":"계약직","contractEndDate":"..."}],"byMonth":{"2026-10":0,"2026-11":0,"2026-12":0}},
  "risks":[{"empId":"...","issue":"재직 상태인데 퇴사일 존재 → 퇴직으로 보정(미확인)","impact":"급여 과지급 위험","unresolvedFlag":"status-inconsistency"}],
  "checklist":[{"item":"입사자 일할 계산 확인","count":0,"status":"pending"}],
  "provenance":{...}
}
```
- `proratedRatio` = 당월 근무일수 / 당월 일수(30), 소수 3자리. 휴직자 급여 처리 구분: 육아휴직→`무급(정부 급여)`, 질병휴직→`유급`(회사 규정 가정), 기타→`무급`
- `payrollHeadcount.monthEnd`는 `month-end-forecast.totals.forecastMonthEnd`와 같아야 한다 (대사)

## 11. 온보딩 계획 — `data/stats/onboarding-plan.json` (온보딩 담당 전용)

```json
{
  "asOfDate":"2026-09-23","horizonEnd":"2026-10-31",
  "timeline":[{"week":"2026-W39","weekStart":"2026-09-21","joiners":[{"joinerId":"J001","name":"...","teamCode":"T111","team":"백엔드팀","plannedHireDate":"2026-09-28","employmentType":"정규직","position":"팀원","stage":"S2"}]}],
  "byTeam":[{"teamCode":"T123","team":"AI에이전트팀","joiners":3,"isNewTeam":true,"teamLeadEmpId":null,"buddyCandidates":[{"empId":"...","name":"...","tenureYears":3.2,"riskBand":"낮음"}]}],
  "checklist":{"items":["계정 발급","장비 지급","보안 교육","팀 소개","버디 배정","30일 면담"],
               "status":[{"joinerId":"J001","계정 발급":"done","장비 지급":"pending","...":"..."}]},
  "newTeamOnboarding":[{"teamCode":"T123","team":"AI에이전트팀","establishedOn":"2026-10-01","joiners":["J020","J021","J022"],"notes":"팀장 미정 — 실장(AI연구실) 임시 리더"}],
  "earlyTenureCohort":{"definition":"기준일 기준 입사 90일 이내 재직자","members":[{"empId":"...","teamCode":"...","hireDate":"...","daysSinceHire":0,"riskBand":"중간"}],"count":0,"highRiskCount":0},
  "earlyAttrition":{"definition":"2025-01-01 이후 퇴직자 중 재직기간 1년 미만 비율","under1YearLeavers":0,"totalLeavers":0,"rate":0.0,"byDivision":{}},
  "provenance":{...}
}
```
- 체크리스트 상태는 가상 생성(입사일이 가까울수록 done 비율 높게). 버디 후보: 같은 팀 재직자 중 재직기간 2~6년, 이직 리스크 `낮음`, 직책 팀원·파트장, 최대 3명
- `timeline`의 입사 예정자 합계는 `planned-joiners.clean.csv`의 유효 행 수와 같아야 한다 (대사)

## 12. 제품 비교 — `products/product-comparison.json`

```json
{
  "asOfDate":"2026-09-23",
  "products":[{"code":"insight","name":"ZeroHR Insight","persona":"head-of-hr",
     "fitScore":{"coverage":0.0,"weightedCoverage":0.0,"panelScore":0.0,"criteriaMet":[{"id":"H-F1","met":true,"evidence":"..."}]},
     "sharedLayerReuse":0.0,"uniqueFeatures":["..."],"buildEffort":{"agentMinutes":0,"linesOfHtml":0},
     "strengths":["..."],"gaps":["..."]}],
  "comparison":{"bestFit":"...","summary":"...","recommendation":"..."},
  "judges":[{"judge":"persona-advocate:payroll","scores":{"insight":0,"payroll":0,"onboard":0},"notes":"..."}]
}
```
- `coverage` = 충족 기준 수 / 전체 기준 수, `weightedCoverage` = Σ(충족 weight)/Σ(weight). `panelScore`는 심판 3명(각 페르소나 옹호자 렌즈) 평균(0~10)

## 13. Supabase 데이터 저장소 — `supabase/`

- `supabase/schema.sql`: 테이블 `employees`(정제 마스터 컬럼 그대로, `emp_id` PK), `to_plan`, `planned_joiners`, `planned_leavers`, `cleansing_log`, `report_snapshots(id bigserial, product text, as_of_date date, payload jsonb, created_at timestamptz default now())`, RLS: anon은 `report_snapshots` select만
- `supabase/seed.py`: 정제 CSV/JSON → PostgREST(`/rest/v1/...`)로 upsert (service_role 키, 표준 라이브러리 `urllib`만)
- `supabase/verify.py`: 행 수·합계를 로컬 정제 데이터와 대사하고 결과를 `supabase/verify-result.json`에 기록
- 자격증명은 환경변수 `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_ANON_KEY`, `SUPABASE_DB_URL`(스키마 적용용) — 파일에 저장하지 않는다

## 14. 로컬 테스트 — `tests/`

`python3 -m unittest discover -s tests -v` 로 실행. 최소:
- `test_contract.py`: 정제 CSV 헤더·정규 값 도메인이 계약과 일치
- `test_reconciliation.py`: §2-7 표(406/422/19/14/411/−11)와 `headcount-stats`·`month-end-forecast`·`payroll-close`·`onboarding-plan`·제품 스냅샷 3종의 같은 지표가 모두 일치
- `test_cleansing.py`: `injected-defects.json`의 결함이 `cleansing-log.jsonl`에서 전부 잡혔는지(재현율), `org-parent-only` 등 미해결이 플래그됐는지
- `test_site.py`: `site/**/index.html`이 내장 JSON을 갖고, 외부 스크립트 도메인이 허용 목록뿐인지
