# 데이터 계약 v2: Zero Company HR — Everyday People Agent (브리프 정본 반영)

용어는 `.claude/GLOSSARY.md`(v2)를 따른다. 이 문서는 **파일 경로·컬럼·JSON 필드·데모 수치의 정본**이다.
데모 수치는 사용자 제공 브리프 `zero-company/zero_company_external_brief.md` §5~§10의 값을 그대로 채택했다.
모든 스크립트·에이전트·검증자는 이 계약을 기준으로 읽고 쓴다. 계약에 없는 필드가 필요하면 계약을 먼저 고친다.

- 표기: CSV 헤더와 JSON 필드는 **camelCase**. 원천(raw) CSV만 고객사 양식(한글 헤더)을 그대로 쓴다.
- 인코딩 UTF-8(원천은 `utf-8-sig`로 읽기). 일자는 정제 이후 `YYYY-MM-DD`, 월은 `YYYY-MM`.
- 기준일 `asOfDate` **2026-09-23**, 월말 2026-09-30, 다음 달 말 2026-10-31.
- 실행 환경: Python 3.9 표준 라이브러리만. 난수 `random.seed(20260923)` 고정(재실행 동일).
- v1(본부>실>팀 22팀 구조)은 `_workspace/DATA_CONTRACT.v1.md`에 보관. v1 기준 산출물·스크립트는 이 v2로 정렬한다.

---

## 0. 디렉토리

```
zero-hr/
├── zero-company/                         # 회사 형상 정본(브리프) + ZERO_COMPANY_OS.md + DR-*.md
├── data/reference/org-chart.csv          # 조직 체계(신뢰 기준표) · company-stages.json(스테이지 경계일)
├── data/raw/                             # ① 원천 4종(결함 포함) + injected-defects.json
├── data/clean/                           # ② 정제 4종 + cleansing-log.jsonl + cleansing-summary.json
├── data/stats/                           # ③ headcount-stats · month-end-forecast · attrition-risk · payroll-close · onboarding-plan · automation-effect
├── personas/persona-needs.json           # 페르소나 3종 니즈 데이터
├── products/product-comparison.json      # 제품 3종 비교
├── site/                                 # ④ Vercel 정적 사이트 (허브 + 제품 3 + data/*.json + config.js)
├── reports/                              # ④ 월초 리포트 md/html + org-forecast CSV + dispatch.json
├── supabase/                             # schema.sql · seed.py · verify.py · apply_schema.sh
├── tests/                                # unittest
└── _workspace/                           # run_meta.json · handoff/*.md(핸드오프 로그) · 중간 산출물
```

## 1. 조직 체계 — `data/reference/org-chart.csv`

**조직 그룹(4) > 조직(11)** 2단계. 조직명은 영문 정규 표기. 이 표가 조직 정규화의 유일한 기준이다.

컬럼: `orgGroupCode,orgGroup,deptCode,department,formerNames,establishedOn`
- `formerNames`: 구 명칭·동의어를 `;`로 구분. 조직 정규화의 별칭 사전으로 쓴다

| orgGroupCode | orgGroup | deptCode | department | formerNames |
|---|---|---|---|---|
| G0 | Executive | D01 | CEO Office | Executive Office;CEO Staff;경영지원 |
| G1 | Build | D02 | Product | Product Management;PM;프로덕트 |
| G1 | Build | D03 | Engineering | R&D;Eng;Engineering Dept;개발 |
| G1 | Build | D04 | Design | UX;Product Design;디자인 |
| G1 | Build | D05 | Data & AI | Data and AI;Data/AI;AI Lab;Data Science |
| G2 | Go-To-Market | D06 | Sales | Sales Team;BizDev;영업 |
| G2 | Go-To-Market | D07 | Marketing | Growth;Growth Marketing;마케팅 |
| G2 | Go-To-Market | D08 | Customer Success | Customer Support;CS;CX;고객지원 |
| G3 | Operations | D09 | People | HR;People Team;Human Resources;인사 |
| G3 | Operations | D10 | Finance | Finance & Accounting;Accounting;재무 |
| G3 | Operations | D11 | Legal & Compliance | Legal and Compliance;Legal&Compliance;Legal;법무 |

`data/reference/company-stages.json` — 스테이지 경계일(생성기가 §2-7 스테이지 분포를 만족하도록 산출):
`{"stages":[{"stage":"Seed","from":"2019-01-01","to":"..."},{"stage":"Series A",...},{"stage":"Scale-up",...},{"stage":"Enterprise","from":"...","to":"9999-12-31"}]}`
클린저는 이 경계로 `stage`를 **입사일에서 파생**한다(브리프 §5.2 "파생 필드: stage").

## 2. 원천 데이터 (①) — `data/raw/`

고객사 양식(한글 헤더). **결함 포함**, 정답지 `injected-defects.json`.

### 2-1. `headcount-master.csv` — 인원현황 마스터 (현재 임직원만)
헤더(순서 고정): `사번,성명,성별,생년월일,소속,직군,레벨,고용유형,재직상태,휴직유형,휴직시작일,입사일,계약종료일,입사전경력(개월),최종수정일`
- 정답 기준 **427행**(재직 406 + 휴직 21) + 중복(구버전) 행 8행 = 원천 435행. 퇴직자 행 없음
- `사번` `E`+4자리. `성명` 한국식 가상 이름. `계약종료일`은 계약직·인턴·파견만(정규직 빈값). 기준일 이후 90일 내 만료 ≥ 8명
- 스테이지 컬럼 없음(클린징 파생). 퇴사일 없음(현재 임직원만)
- 속성 분포는 §2-7 정본을 **정확히** 만족한다

### 2-2. `to-plan.csv` — TO 계획
헤더: `조직,정원,기준월` — 11행, 정원은 §2-7 TO 열 그대로(합 422). `조직` 표기 결함 3건, `기준월` 변형(`2026-09`,`2026.09`,`202609`,`2026년 9월`)

### 2-3. `planned-joiners.csv` — 입사 예정자
헤더: `성명,소속,직군,레벨,고용유형,성별,생년월일,입사예정일,입사전경력(개월)`
- **27행**: 2026-09-24~09-30 입사 **19명**(조직별 §2-7 `in` 열 그대로) + 2026-10-01~10-31 **8명**(Engineering 3, Data & AI 2, Sales 2, Product 1)
- 결함: 소속 변형 2, 일자 포맷 3, 성별 변형 1

### 2-4. `planned-leavers.csv` — 퇴사 예정자
헤더: `사번,성명,소속,퇴사예정일,퇴직사유`
- **19행**: 2026-09-30 이전 유효 **14명**(조직별 §2-7 `out` 열, 사유별 §2-7 표) — 이 중 1명은 예정일 2026-09-15(`stale-planned-leaver`, 마스터는 재직) / 2026-10 **4명**(Engineering 1, Sales 1, Customer Success 1, Marketing 1) / 마스터에 없는 사번 **1행**(`unknown-emp`, 예측 제외)
- 결함: 위 2건 + 일자 포맷 2 + 퇴직사유 자유 텍스트(예 `자발적 퇴사`, `계약 기간 만료`, `조직 개편에 따른`, `성과 부진`, `개인 사정`) 6

### 2-5. 주입 결함 — 반드시 포함할 유형과 건수 (마스터 기준, 브리프 §5.2 정합)

| defectType | 설명 | 건수 |
|---|---|---|
| `org-old-name` | 구 명칭 (`HR`,`R&D`,`Customer Support`,`UX`,`AI Lab`,`BizDev`) | 6 |
| `org-variant` | 표기 변형 (`Legal and Compliance`,`Legal&Compliance`,`Data and AI`,`Customer success`) | 4 |
| `org-typo` | 오탈자 (`Enginering`,`Marketting`,`Finanace`) | 3 |
| `org-whitespace` | 앞뒤·중간·전각 공백 | 4 |
| `org-unknown` | 조직 체계에 없는 이름 (`Growth Lab`,`Platform`) → 직군으로 임시 배정 + 미해결 | 2 |
| `hire-date-format` | 입사일 포맷: `YYYY/MM/DD` 20 · `YYYY.MM.DD` 6 · `YYYYMMDD` 3 · Excel 일련번호 2 | **31** |
| `date-format` | 휴직시작일·계약종료일 포맷 변형 | 6 |
| `date-logic` | 재직인데 입사일이 기준일 이후 → 미해결 | 2 |
| `status-inconsistency` | 휴직인데 휴직유형 없음 → `기타` + 미해결 | 3 |
| `missing-required` | 계약직/인턴인데 계약종료일 없음 → 미해결 | 3 |
| `duplicate` | 같은 사번 2행(구버전: 옛 소속명 또는 옛 레벨, 최종수정일 이름) | 8 |
| `code-variant` | 성별(`F`,`M`,`female`,`male`,`여`,`남`), 고용유형(`정규`,`Regular`,`FT`,`계약`,`Contract`,`Intern`,`Dispatch`), 재직상태(`재직중`,`Active`,`휴직중`,`Leave`), 레벨(`ic1`,`IC-2`,`Sr`,`Mgr`,`Dir`) | ≥ 30 |
| (to-plan) `org-variant` | 조직 표기 3 · 기준월 포맷 4 | 7 |
| (joiners) `org-variant`/`date-format`/`code-variant` | 2 / 3 / 1 | 6 |
| (leavers) `date-format`/`reason-freetext`/`stale-planned-leaver`/`unknown-emp` | 2 / 6 / 1 / 1 | 10 |

부서명 **보정**(org-old-name/variant/typo/whitespace) 마스터 합계 = **17**(브리프 "부서명 정규화 17건") — `org-unknown` 2건은 보정이 아니라 미해결 플래그이므로 17에 포함하지 않는다. 입사일 포맷 = **31**(브리프 "입사일자 보정 31건"). to-plan `기준월` 포맷 변형의 defectType은 `date-format`.

### 2-6. `injected-defects.json`
```json
{ "seed":20260923,"generatedAt":"2026-09-23",
  "summary":{"org-old-name":6,"hire-date-format":31,"...":0},
  "defects":[{"source":"headcount-master","rowRef":{"사번":"E0123","rowIndex":45},"field":"소속","defectType":"org-variant","rawValue":"Legal and Compliance","trueValue":"D11"}] }
```
- `trueValue`: 소속은 `deptCode`, 일자는 ISO, 코드성 값은 정규 값, 중복은 살아남을 행의 `rowIndex`, 미해결 유형은 `"(unresolved)"` + 임시 배정값. `rowIndex`는 헤더 제외 0부터

### 2-7. 정본 수치 (브리프 §6~§8 — 정확히 일치시킬 것)

**조직별** (HC=재직, OL=휴직, ME=HC+in−out, gapAsOf=HC−TO, gapME=ME−TO):

| deptCode | department | orgGroup | HC | OL | TO | in | out | ME | gapAsOf | gapME | recommendation |
|---|---|---|---|---|---|---|---|---|---|---|---|
| D01 | CEO Office | Executive | 10 | 0 | 10 | 0 | 0 | 10 | 0 | 0 | 정상 관리 |
| D02 | Product | Build | 51 | 3 | 54 | 3 | 1 | 53 | −3 | −1 | 정상 관리 |
| D03 | Engineering | Build | 104 | 6 | 112 | 5 | 4 | 105 | −8 | −7 | 채용 가속 |
| D04 | Design | Build | 25 | 1 | 26 | 1 | 1 | 25 | −1 | −1 | 정상 관리 |
| D05 | Data & AI | Build | 40 | 2 | 34 | 2 | 1 | 41 | +6 | +7 | TO 재검토/이동배치 |
| D06 | Sales | Go-To-Market | 58 | 3 | 62 | 3 | 3 | 58 | −4 | −4 | 채용 가속 |
| D07 | Marketing | Go-To-Market | 30 | 1 | 32 | 1 | 1 | 30 | −2 | −2 | 정상 관리 |
| D08 | Customer Success | Go-To-Market | 40 | 3 | 42 | 2 | 1 | 41 | −2 | −1 | 정상 관리 |
| D09 | People | Operations | 18 | 1 | 18 | 1 | 0 | 19 | 0 | +1 | 정상 관리 |
| D10 | Finance | Operations | 19 | 1 | 20 | 1 | 1 | 19 | −1 | −1 | 정상 관리 |
| D11 | Legal & Compliance | Operations | 11 | 0 | 12 | 0 | 1 | 10 | −1 | −2 | 정상 관리 |
| **합계** | | | **406** | **21** | **422** | **19** | **14** | **411** | **−16** | **−11** | |

조직 그룹(재직): Executive 10 · Build 220 · Go-To-Market 128 · Operations 48. (브리프 §7의 215/119/62는 조직표 합과 불일치 — 조직표를 정본으로 하고 이 사실을 리포트 데이터 품질 절에 기록한다)

**속성 분포 (재직 406 기준, 고용유형만 총원 427 기준)**:

| 속성 | 분포 |
|---|---|
| 고용유형(427) | 정규직 354, 계약직 31, 인턴 19, 파견 23 |
| 성별 | 여성 188, 남성 195, 미응답 23 |
| 연령대 | 20대 82, 30대 221, 40대 83, 50대+ 20 |
| 직군 | Engineering 116, Product 55, Design 25, Sales 58, Marketing 30, Customer Success 40, People 18, Finance 19, Legal 11, Data/AI 24, Executive 10 |
| 레벨 | IC1 33, IC2 65, IC3 82, Senior 89, Lead 55, Manager 44, Director 25, VP 13 |
| 재직기간 구간 | 1년 미만 54, 1~3년 151, 3~5년 103, 5년+ 98 |
| 총경력 구간 | 0~3년 56, 3~7년 137, 7~12년 142, 12년+ 71 |
| 스테이지 | Seed 49, Series A 151, Scale-up 140, Enterprise 66 (입사일 순위로 경계 결정) |

- 직군↔조직: Data & AI(40) = Data/AI 24 + Engineering 12 + Product 4. 나머지 조직은 자기 직군 100%
- 레벨 제약: 조직마다 VP ≥ 1(CEO Office는 3), 재직 18명 이상 조직은 Director ≥ 1. 레벨은 재직기간·총경력과 양의 상관
- 휴직 21의 조직 배분은 OL 열. 휴직자 고용유형은 정규직 19·계약직 2(고용유형 427 합계 유지)

**퇴사 예정자(14) 사유**: 자발퇴사 5, 계약만료 3, 조직개편 2, 성과/적합도 2, 개인사유 2. 계약만료는 계약직·인턴·파견에게만

**Executive Snapshot (테스트 상수)**: 재직 406 · 휴직 21 · 총 TO 422 · 현재 TO 대비 −16 · 입사 예정 19 · 퇴사 예정 14 · 월말 예측 411 · 월말 TO 대비 −11

### 2-8. 결정적 보정 규칙 (생성기 trueValue = 클린저 correctedValue)

| 상황 | 보정 | confidence | unresolved |
|---|---|---|---|
| 소속 구명칭·변형·오탈자·공백 | org-chart의 `department`/`formerNames` 정규화 매칭(대소문자·공백·`&`↔`and` 무시, 오탈자는 편집거리 ≤ 2) → `deptCode` | 0.95~1.0 | false |
| 소속이 어떤 조직에도 매칭 안 됨 (`org-unknown`) | 직군→조직 기본 매핑(Engineering→D03, Product→D02, Design→D04, Sales→D06, Marketing→D07, Customer Success→D08, People→D09, Finance→D10, Legal→D11, Data/AI→D05, Executive→D01)으로 임시 배정 | 0.5 | **true** |
| 일자 포맷 변형 | ISO 변환. 2자리 연도 20xx. Excel 일련번호 1899-12-30 기준 | 1.0 | false |
| 재직인데 입사일 > 기준일 | 그대로 두고 플래그(통계에는 포함, 재직기간 0) | - | true |
| 휴직인데 휴직유형 없음 | `기타` | 0.6 | true |
| 계약직/인턴/파견인데 계약종료일 없음 | 빈값 유지, 플래그 | - | true |
| 같은 사번 복수 행 | `최종수정일` 최신 행만(동일하면 뒤 행) | 1.0 | false |
| 성별·고용유형·재직상태·레벨 변형 | 사전 매핑 (F/female/여→여성, M/male/남→남성, 빈값→미응답 / 정규·Regular·FT→정규직, 계약·Contract→계약직, Intern→인턴, Dispatch→파견 / 재직중·Active→재직, 휴직중·Leave→휴직 / ic1→IC1, IC-2→IC2, Sr→Senior, Mgr→Manager, Dir→Director) | 1.0 | false |
| 퇴직사유 자유 텍스트 | 키워드 매핑(자발→자발퇴사, 계약·만료→계약만료, 조직·개편→조직개편, 성과·적합→성과/적합도, 개인→개인사유, 건강→건강, 정년→정년) | 0.9 | false |
| 퇴사 예정일 < 기준일 (`stale-planned-leaver`) | 플래그, 월말 예측에서는 퇴사로 반영 | - | true |
| 퇴사 예정자 사번이 마스터에 없음 (`unknown-emp`) | 플래그, 예측 제외 | - | true |
| 파생 | `ageBand`(기준일 만 나이), `tenureYears`((기준일−입사일).days/365.25, 2자리), `tenureYear`(floor+1), `tenureBand`, `totalExperienceYears`(입사전경력/12+tenureYears), `totalExperienceBand`, `stage`(company-stages.json), `orgGroupCode/orgGroup`(org-chart) | - | - |

## 3. 정제 데이터 (②) — `data/clean/`

### 3-1. `headcount-master.clean.csv`
`empId,name,gender,birthDate,ageBand,orgGroupCode,orgGroup,deptCode,department,jobFamily,level,stage,employmentType,status,leaveType,leaveStart,hireDate,contractEndDate,priorExperienceMonths,tenureYears,tenureYear,tenureBand,totalExperienceYears,totalExperienceBand,unresolvedFlags,sourceRowIndex`
- 정규 값: `gender` 여성|남성|미응답 · `status` 재직|휴직 · `employmentType` 정규직|계약직|인턴|파견 · `leaveType` 육아휴직|질병휴직|기타|(빈값) · `level` IC1|IC2|IC3|Senior|Lead|Manager|Director|VP · `stage` Seed|Series A|Scale-up|Enterprise · `jobFamily` Engineering|Product|Design|Sales|Marketing|Customer Success|People|Finance|Legal|Data/AI|Executive
- `ageBand` 20대|30대|40대|50대+ · `tenureBand` 1년 미만|1~3년|3~5년|5년+ · `totalExperienceBand` 0~3년|3~7년|7~12년|12년+
- `unresolvedFlags` `;` 구분. 미해결 행도 삭제하지 않는다. 1사번 1행(427행)

### 3-2. `to-plan.clean.csv` — `deptCode,department,orgGroupCode,toHeadcount,effectiveMonth`
### 3-3. `planned-joiners.clean.csv` — `joinerId,name,deptCode,department,jobFamily,level,employmentType,gender,birthDate,plannedHireDate,priorExperienceMonths,unresolvedFlags` (`joinerId` J001~)
### 3-4. `planned-leavers.clean.csv` — `empId,deptCode,plannedTerminationDate,separationType,separationReason,unresolvedFlags`
### 3-5. `cleansing-log.jsonl` — `{"source","rowRef":{"사번","rowIndex"},"field","rawValue","correctedValue","rule","confidence","unresolved"}` — `rule`은 §2-5 defectType 어휘와 동일(정답지 대사)
### 3-6. `cleansing-summary.json`
```json
{"asOfDate":"2026-09-23","rowsIn":{"headcount-master":435,"to-plan":11,"planned-joiners":27,"planned-leavers":19},"rowsOut":{"headcount-master":427,"to-plan":11,"planned-joiners":27,"planned-leavers":19},
 "duplicatesRemoved":8,"correctionsByRule":{"org-variant":4,"hire-date-format":31},"orgNameCorrections":17,"hireDateCorrections":31,
 "orgGroupMapping":{"D01":"Executive","D02":"Build"},"derivedFields":["ageBand","tenureBand","totalExperienceBand","stage"],
 "unresolvedCount":0,"unresolvedItems":[{"source":"headcount-master","rowRef":{},"field":"소속","rawValue":"Growth Lab","question":"어느 조직 소속입니까? (직군 Marketing 기준 Marketing으로 임시 배정)"}]}
```

## 4. 통계·예측 (③) — `data/stats/`

### 4-1. `headcount-stats.json`
```json
{"asOfDate":"2026-09-23","client":"㈜온다테크",
 "totals":{"headcount":427,"activeHeadcount":406,"onLeave":21,"toHeadcount":422,"toGapAsOf":-16,"plannedIn":19,"plannedOut":14,"unresolvedCount":0},
 "byOrgGroup":[{"orgGroupCode":"G1","orgGroup":"Build","activeHeadcount":220,"onLeave":12,"headcount":232,"toHeadcount":226,"toGapAsOf":-6}],
 "byDepartment":[{"deptCode":"D03","department":"Engineering","orgGroupCode":"G1","orgGroup":"Build","activeHeadcount":104,"onLeave":6,"headcount":110,"toHeadcount":112,"toGapAsOf":-8}],
 "byAttribute":{"employmentType":{},"gender":{},"ageBand":{},"jobFamily":{},"level":{},"tenureBand":{},"totalExperienceBand":{},"stage":{}},
 "byAttributeAll":{"employmentType":{"정규직":354,"계약직":31,"인턴":19,"파견":23},"status":{"재직":406,"휴직":21},"leaveType":{}},
 "crossTabs":{"departmentByEmploymentType":{},"departmentByGender":{},"departmentByAgeBand":{},"departmentByLevel":{},"jobFamilyByLevel":{},"jobFamilyByStage":{},"orgGroupByTenureBand":{}},
 "experience":{"avgTenureYears":0.0,"medianTenureYears":0.0,"avgTotalExperienceYears":0.0,"medianTotalExperienceYears":0.0,"byDepartment":[{"deptCode":"D03","avgTenureYears":0.0,"avgTotalExperienceYears":0.0}]},
 "plannedSeparations":{"total":14,"bySeparationReason":{"자발퇴사":5,"계약만료":3,"조직개편":2,"성과/적합도":2,"개인사유":2},"bySeparationType":{},"byDepartment":{},"byTenureBand":{},"byMonth":{"2026-09":14,"2026-10":4}},
 "dataQuality":{"unresolvedCount":0,"unresolvedByFlag":{},"briefDiscrepancies":["브리프 §7 조직 그룹 합(215/119/62)은 조직표 합(220/128/48)과 불일치 — 조직표 기준 채택"]},
 "provenance":{"source":"data/clean/headcount-master.clean.csv","script":".claude/skills/headcount-stats/scripts/compute_stats.py"}}
```
- `byAttribute`는 **재직 406** 기준(각 딕셔너리 합 = 406 assert). `byAttributeAll`은 427 기준. `plannedSeparations`는 정제 퇴사 예정자 중 unknown-emp 제외(월별 합 18, 9월 14)

### 4-2. `month-end-forecast.json`
```json
{"asOfDate":"2026-09-23","monthEnd":"2026-09-30","nextMonthEnd":"2026-10-31",
 "assumptions":["입사 예정자는 예정일에 전원 입사","퇴사 예정자는 예정일에 전원 퇴사(예정일이 지난 stale 건 포함)","TO 비교는 재직 인원 기준(휴직 제외)","마스터에 없는 사번의 퇴사 예정은 제외"],
 "byDepartment":[{"deptCode":"D03","department":"Engineering","orgGroupCode":"G1","orgGroup":"Build","toHeadcount":112,"activeHeadcount":104,"plannedIn":5,"plannedOut":4,"forecastMonthEnd":105,"toGapAsOf":-8,"toGapMonthEnd":-7,"recommendation":"채용 가속",
   "nextMonth":{"plannedIn":3,"plannedOut":1,"forecastNextMonthEnd":107,"toGapNextMonthEnd":-5},"riskAdjusted":{"expectedAttrition":0.0,"forecastNextMonthEndRiskAdjusted":0.0}}],
 "byOrgGroup":[{"orgGroupCode":"G1","orgGroup":"Build","toHeadcount":226,"activeHeadcount":220,"plannedIn":11,"plannedOut":7,"forecastMonthEnd":224,"toGapAsOf":-6,"toGapMonthEnd":-2,"nextMonth":{}}],
 "totals":{"toHeadcount":422,"activeHeadcount":406,"toGapAsOf":-16,"plannedIn":19,"plannedOut":14,"forecastMonthEnd":411,"toGapMonthEnd":-11,"toFillRate":0.9739,"nextMonth":{"plannedIn":8,"plannedOut":4,"forecastNextMonthEnd":415,"toGapNextMonthEnd":-7}},
 "plannedJoiners":[{"joinerId":"J001","deptCode":"D03","plannedHireDate":"2026-09-28","employmentType":"정규직"}],
 "plannedLeavers":[{"empId":"E0123","deptCode":"D06","plannedTerminationDate":"2026-09-30","separationType":"자발적","separationReason":"자발퇴사"}],
 "insights":[{"type":"채용 가속 필요","scope":"department","codes":["D03","D06"],"label":"Engineering, Sales","detail":"Engineering −7, Sales −4","action":"채용 pipeline 점검"},
             {"type":"TO 재검토 필요","scope":"department","codes":["D05"],"label":"Data & AI","detail":"+7 초과 예상","action":"TO 재배분 또는 내부 이동배치"},
             {"type":"퇴사 영향 점검","scope":"department","codes":["D11"],"label":"Legal & Compliance","detail":"재직 11명 조직에서 1명 퇴사 예정, 월말 −2","action":"업무 공백·인수인계 점검"}],
 "immediateActions":["Engineering/Sales 채용 pipeline 점검","Data & AI TO 재검토","Legal & Compliance 퇴사 영향 점검"],
 "scenario":{"parameters":{"hiringAchievementRate":1.0,"extraAttrition":0},"formula":"forecast = active + round(plannedIn × rate) − plannedOut − extraAttrition"},
 "provenance":{}}
```
**결정적 규칙:** `recommendation` = gapME ≤ −4 → `채용 가속` / gapME ≥ +5 → `TO 재검토/이동배치` / 그 외 `정상 관리`. 인사이트 = 채용 가속 조직 묶음, TO 재검토 조직 묶음, `퇴사 영향 점검`(재직 ≤ 12 이고 plannedOut ≥ 1). `riskAdjusted`는 attrition-risk.json 조직별 `expectedAttritionNext3Months`/3을 다음 달 말에 반영(없으면 null + assumptions에 명시). `toFillRate` = forecastMonthEnd/toHeadcount 4자리

### 4-3. `attrition-risk.json`
```json
{"asOfDate":"2026-09-23","model":{"name":"rule-based-v1","factors":[{"factor":"tenure-1-3y","weight":20,"rationale":"..."}],"bands":{"높음":"score>=60","중간":"35<=score<60","낮음":"score<35"},"expectedProbability":{"높음":0.35,"중간":0.12,"낮음":0.03}},
 "byEmployee":[{"empId":"E0123","deptCode":"D03","riskScore":72,"riskBand":"높음","topFactors":["tenure-1-3y","level-stagnation"]}],
 "byDepartment":[{"deptCode":"D03","activeHeadcount":104,"높음":0,"중간":0,"낮음":0,"avgRiskScore":0.0,"expectedAttritionNext3Months":0.0}],
 "byOrgGroup":[],"summary":{"높음":0,"중간":0,"낮음":0,"expectedAttritionNext3Months":0.0}}
```
- 재직자 406만 점수화. `byEmployee`에 성명 없음. 밴드 분포 높음 8~15%, 중간 25~35%. 요인 후보: 재직 1~3년, 20~30대, Engineering/Data-AI 직군, 레벨 정체(재직 3년+ 인데 IC1/IC2), 계약 만료 90일 내, 소속 조직 TO 부족(과부하), 레벨 IC

### 4-4. `automation-effect.json` — §8 참조

### 4-5. shape 보충 (작성자 보고 계약 공백 반영)
- `totals.unresolvedCount`(stats) = 정제 마스터 행 중 `unresolvedFlags`가 비어 있지 않은 행 수. `cleansing-summary.unresolvedCount` = 4개 원천 합산(값이 다를 수 있음, 각자 정의대로)
- `byAttribute.*` 딕셔너리 합 = 406(재직). 단 `byAttributeAll.leaveType` 합 = 21(휴직자만), `byAttributeAll.employmentType`·`status` 합 = 427
- `crossTabs.*` = `{행 라벨: {열 값: 인원}}` 2단 딕셔너리, 행 키는 **라벨**(department명·jobFamily·orgGroup명, 코드 아님). 셀 합 = 406
- 빈 값 버킷: 속성 값이 비어 있으면 `"미상"` 버킷(정제 데이터에서는 발생하지 않아야 하며 발생 시 dataQuality에 기록)
- 구조화 반환값(워크플로우 schema)에는 산출물 외 필드(`targetCheck`, `status`, `handoffLog`)를 둘 수 있다 — 산출물 JSON에는 넣지 않는다
- payroll-close: `payrollHeadcount.byEmploymentType` = `{유형: {asOfTotal, monthEndTotal}}`, `byDepartment[]` = `{deptCode, department, asOfActive, asOfOnLeave, asOfTotal, plannedIn, plannedOut, monthEndActive, monthEndTotal}`. `checklist[].status` ∈ pending|done. `contracts.byMonth`는 90일 창에 걸치는 모든 월(0건도 키 유지). `risks[].unresolvedFlag`는 §2-5 어휘 + 급여 파생 어휘(contract-expired-active, hire-after-as-of, leaver-not-active) 허용
- onboarding-plan: `byDepartment[]`는 입사 예정자 ≥ 1인 조직만. `earlyAttrition.byDepartment` = `{deptCode: {department, under1YearLeavers, totalLeavers, rate}}`. `provenance` = `{sources[], script, reconciliation{timelineJoiners, plannedJoinersValidRows, match, monthEndJoiners, forecastPlannedIn, monthEndMatch}, gaps[{kind, criterionId, criterion, weight, evidence, reason}]}`
- forecast/payroll 공통: `plannedOut` = 예정일 ≤ 월말 ∧ unknown-emp 제외 ∧ 마스터에서 재직인 사번(휴직자의 퇴사 예정은 재직 기준 예측에서 제외하되 급여 마감 monthEndTotal에는 반영)

## 5. 제품·사이트 (④) — `site/`

플랫폼 **Zero Company HR**, 제품 브랜드 **Everyday People Agent**. 세 앱은 같은 공통 데이터 계층을 읽고 페르소나 파생(§10, §11)을 얹는다.

| 앱 | 페르소나 | 경로 | 스냅샷 | 핵심 화면 |
|---|---|---|---|---|
| Insight | 인사 총괄 | `site/insight/index.html` | `site/data/insight.json` = `{stats, forecast, attrition, cleansingSummary, hrDirectory, automationEffect}` | 리포트 뷰 4종 역할 선택기: `executive`(총원·TO 과부족·조직별 월말 예측·리스크 요약, 개인명 없음) / `hr`(개인 단위 마스터·클린징 오류·입퇴사 예정자·퇴직사유·이직 리스크 개인 목록) / `planning`(TO·조직별 현재/예측·증감 원인·**시나리오 플래너**, 개인 식별 없음) / `orgLead`(조직 선택 → 본인 조직의 현재/예측·입퇴사 예정 요약만, 타 조직 숨김) |
| Payroll Close | 급여 담당 | `site/payroll/index.html` | `site/data/payroll.json` = `{payrollClose, statsSubset, cleansingSummary}` | 월말 급여 대상 확정 · 일할 계산 대상 · 휴직 처리 · 계약 만료 · 급여 오류 위험 · 체크리스트 |
| Onboarding | 온보딩 담당 | `site/onboard/index.html` | `site/data/onboard.json` = `{onboardingPlan, plannedJoiners, hrDirectorySubset}` | 주차별 타임라인 · 조직 배치 · 체크리스트 · 버디 · 90일 코호트 |
| 허브 | 전체 | `site/index.html` | `site/data/comparison.json` = §12 + 페르소나 요약 |
| 통합 제품(app) | 전체(역할 탭 6) | `site/app/index.html` | `site/data/app.json` = §15 (`build_snapshots.py --product app --embed`) | Everyday People Agent 소개(미션 한 줄) + 앱 3 진입 카드 + fit 비교 + Zero Company OS 4역할 흐름도 |

- 각 HTML은 스냅샷 JSON을 `<script id="report-data" type="application/json">`으로 내장하고, `site/config.js`의 `window.ZEROHR_CONFIG={supabaseUrl,supabaseAnonKey}`가 있으면 `report_snapshots`에서 product별 최신 `payload`를 fetch해 덮어쓴다(실패 시 내장 유지, 출처 배지 갱신)
- 공통 헤더: 앱명 · Everyday People Agent · 고객사 · 기준일 · 데이터 출처(내장/Supabase) · 허브 링크. 시스템 폰트, CSS 변수 토큰(라이트/다크), 외부 스크립트는 cdnjs.cloudflare.com·cdn.jsdelivr.net/npm/만, 375px 폭 가로 스크롤 없음
- 같은 지표는 앱·뷰가 달라도 같은 값(`reconciliation-policy`). 개인 식별은 `pii-minimization-policy`
- `vercel.json`: `{"cleanUrls":true,"trailingSlash":false}` — 정적 배포

## 6. 월초 리포트 (④) — `reports/`
- `monthly-report-2026-10.md` / `.html`(인라인 스타일): 제목 **`[Zero Company] 2026-09 HR Headcount Forecast`**. 본문 요약: 현재 재직 406 / 월말 예측 411 · 총 TO 대비 월말 gap −11 · 채용 가속 필요: Engineering, Sales · TO 재검토 필요: Data & AI · 즉시 액션 3건 · 첨부: 권한별 대시보드 링크, 조직별 forecast CSV. 이어서 Executive Snapshot 표, 조직별 예측 표(§2-7 열), 인원 통계 요약, 퇴사 예정 사유, 데이터 품질(클린징 17/31건·미해결·브리프 불일치), 자동화 효과, 부록(정의)
- `org-forecast-2026-09.csv`: `deptCode,department,orgGroup,toHeadcount,activeHeadcount,plannedIn,plannedOut,forecastMonthEnd,toGapMonthEnd,recommendation`
- `monthly-report-dispatch.json`: `{"sendAt":"2026-10-01T09:00:00+09:00","schedule":"0 9 1 * *","recipients":{"executive":[...],"hr":[...],"planning":[...],"orgLead":[...]},"subject":"[Zero Company] 2026-09 HR Headcount Forecast","attachments":["site/insight/index.html","reports/org-forecast-2026-09.csv"],"status":"ready-to-send","gate":"approval-gate: 외부 발송"}` — 수신자는 `@ondatech.example`만

## 7. 실행 메타·핸드오프 로그 — `_workspace/`
- `run_meta.json`: `{"runId","startedAt","finishedAt","asOfDate","phasesCompleted":[],"artifacts":[],"durations":{"collect":0,"cleanse":0,"stats":0,"forecast":0,"attrition":0,"payroll":0,"onboarding":0,"personas":0,"products":0,"report":0,"test":0,"deploy":0,"totalSeconds":0}}`
- **핸드오프 로그(Operating Rule 2)** `_workspace/handoff/{NN-단계}.md` — 단계: 01-collect, 02-cleanse, 03-stats, 04-forecast, 05-attrition, 06-payroll, 07-onboarding, 08-personas, 09-products, 10-report, 11-test, 12-deploy. 각 파일은 5개 절 고정: `## 시도한 것` / `## 본 데이터·근거` / `## 실패한 것` / `## 검증된 것` / `## 다음 agent 인계점`

## 8. 기대 효과 4종의 증빙

| 기대 효과 | 기능 요건 | 증빙 |
|---|---|---|
| ① 완전 자동화(80% 절감) | 원천 4종 → 제품·리포트까지 사람 개입 없이 오케스트레이터 1회 실행 | `run_meta.json` durations + `data/stats/automation-effect.json` |
| ② 경영진 실시간 조회 | Insight 경영진 뷰를 링크 하나로, 재실행 시 Supabase 스냅샷 갱신 | Vercel URL + Supabase `report_snapshots` |
| ③ 인력계획 선제 대응 | 월말 예측 + TO 과부족 + 권고/인사이트 + 시나리오 플래너 + 리스크 시나리오 | `month-end-forecast.json` |
| ④ 월간 리포트 자동 생성·배포 | 같은 통계에서 리포트 md/html/CSV + 수신자·일정 명세 | `reports/*` + dispatch.json |

`automation-effect.json`: `{"asOfDate":"2026-09-23","manualBaseline":{"hoursPerMonth":40,"breakdown":{"수집·통합":8,"클린징":12,"집계·예측":12,"리포트 작성·배포":8},"basis":"중견 스타트업 HR 월간 인원 리포트 수작업 공수 추정(가정)"},"automated":{"pipelineSeconds":0,"humanReviewHoursPerMonth":8,"breakdown":{"미해결 항목 확인":3,"리포트 검토·승인(승인 gate)":5}},"savingRate":0.8,"note":"가정 기반 추정치. 고객사 실측으로 갱신"}`

## 9. 페르소나 니즈 데이터 — `personas/persona-needs.json`
```json
{"asOfDate":"2026-09-23","client":"㈜온다테크",
 "personas":[{"code":"head-of-hr","title":"인사 총괄","titleEn":"Head of HR","product":"insight","profile":"...","goals":["..."],
   "jobsToBeDone":[{"id":"H1","job":"매월 초 경영진에게 인원 현황과 다음 달 전망을 보고한다","trigger":"월초","frequency":"monthly","importance":5}],
   "calendar":[{"when":"매월 1~3일","task":"..."}],"keyQuestions":["..."],"kpis":[{"name":"TO 충족률","definition":"...","source":"forecast.totals.toFillRate"}],
   "pains":[{"pain":"엑셀 취합 수작업","costHoursPerMonth":12}],"requiredFields":["headcount-master.status","to-plan.toHeadcount"],"decisions":["채용 가속/보류","TO 재배분"],
   "fitCriteria":[{"id":"H-F1","criterion":"조직별 TO 과부족을 한 화면에서 본다","weight":5,"evidence":"month-end-forecast.byDepartment"}]}],
 "shared":{"commonNeeds":["..."],"conflicts":["급여는 성명 필수 vs 경영진 뷰는 익명"],"dataLayerImplications":["..."]}}
```
- 페르소나마다 `jobsToBeDone` ≥ 5, `fitCriteria` ≥ 8(weight 1~5, evidence). `pains.costHoursPerMonth` 합 ≈ 40h(§8 정합)
- 확장 키(v2.1): 페르소나마다 `rubric{lens, qualitative[{id,item,scale}]}`(심판의 정성 렌즈), `assumptions[]`, `sources[]`(웹 조사 URL). 검증자는 이 세 키를 허용한다

## 10. 급여 마감 — `data/stats/payroll-close.json`
```json
{"asOfDate":"2026-09-23","payPeriod":"2026-09","periodStart":"2026-09-01","periodEnd":"2026-09-30",
 "payrollHeadcount":{"asOfActive":406,"asOfOnLeave":21,"asOfTotal":427,"monthEndActive":411,"monthEndTotal":432,"byEmploymentType":{"정규직":354,"계약직":31,"인턴":19,"파견":23},"byDepartment":[{"deptCode":"D03","asOfTotal":110,"monthEndActive":105,"monthEndTotal":111}]},
 "prorations":{"joinersInPeriod":[{"empId":"E0411","name":"...","deptCode":"D03","hireDate":"2026-09-08","employmentType":"정규직","workedDays":23,"proratedRatio":0.767}],
               "plannedJoinersByMonthEnd":[{"joinerId":"J001","name":"...","deptCode":"D03","plannedHireDate":"2026-09-28","workedDays":3,"proratedRatio":0.1}],
               "plannedLeaversByMonthEnd":[{"empId":"...","name":"...","deptCode":"...","plannedTerminationDate":"2026-09-30","separationType":"자발적","workedDays":30,"proratedRatio":1.0}]},
 "leaves":{"onLeave":[{"empId":"...","name":"...","deptCode":"...","leaveType":"육아휴직","leaveStart":"...","payrollTreatment":"무급(정부 급여)"}],"byTreatment":{"무급(정부 급여)":0,"유급":0,"무급":0}},
 "contracts":{"expiringWithin90Days":[{"empId":"...","name":"...","deptCode":"...","employmentType":"계약직","contractEndDate":"..."}],"byMonth":{"2026-10":0,"2026-11":0,"2026-12":0}},
 "risks":[{"empId":"...","issue":"휴직인데 휴직유형 없음 → 기타로 보정(미확인)","impact":"급여 처리 구분 오류 위험","unresolvedFlag":"status-inconsistency"}],
 "checklist":[{"item":"입사자 일할 계산 확인","count":0,"status":"pending"}],"provenance":{}}
```
- `proratedRatio` = 당월 근무일수/30, 3자리. 휴직 처리: 육아휴직→`무급(정부 급여)`, 질병휴직→`유급`, 기타→`무급`. `monthEndActive` = forecast.totals.forecastMonthEnd(411) assert

## 11. 온보딩 계획 — `data/stats/onboarding-plan.json`
```json
{"asOfDate":"2026-09-23","horizonEnd":"2026-10-31",
 "timeline":[{"week":"2026-W39","weekStart":"2026-09-21","joiners":[{"joinerId":"J001","name":"...","deptCode":"D03","department":"Engineering","plannedHireDate":"2026-09-28","employmentType":"정규직","level":"IC2"}]}],
 "byDepartment":[{"deptCode":"D03","department":"Engineering","joiners":8,"joinersByMonthEnd":5,"buddyCandidates":[{"empId":"...","name":"...","tenureYears":3.2,"level":"Senior","riskBand":"낮음"}],"deptLeadEmpId":"..."}],
 "checklist":{"items":["계정 발급","장비 지급","보안 교육","조직 소개","버디 배정","30일 면담"],"status":[{"joinerId":"J001","계정 발급":"done","장비 지급":"pending"}]},
 "earlyTenureCohort":{"definition":"기준일 기준 입사 90일 이내 재직자","members":[{"empId":"...","deptCode":"...","hireDate":"...","daysSinceHire":0,"riskBand":"중간"}],"count":0,"highRiskCount":0},
 "earlyAttrition":{"definition":"퇴사 예정자(14) 중 재직기간 1년 미만 비율","under1YearLeavers":0,"totalLeavers":14,"rate":0.0,"byDepartment":{}},
 "provenance":{}}
```
- 버디 후보: 같은 조직 재직자 중 재직 2~6년, 리스크 낮음, 레벨 IC3~Lead, 최대 3명. 타임라인 합계 = 정제 입사 예정자 27 assert

## 12. 제품 비교 — `products/product-comparison.json`
```json
{"asOfDate":"2026-09-23",
 "products":[{"code":"insight","name":"Everyday People Agent — Insight","persona":"head-of-hr",
   "fitScore":{"coverage":0.0,"weightedCoverage":0.0,"panelScore":0.0,"criteriaMet":[{"id":"H-F1","met":true,"evidence":"..."}]},
   "sharedLayerReuse":0.0,"uniqueFeatures":["..."],"buildEffort":{"agentMinutes":0,"linesOfHtml":0},"strengths":["..."],"gaps":["..."]}],
 "comparison":{"bestFit":"...","summary":"...","recommendation":"..."},
 "judges":[{"judge":"persona-advocate:payroll","scores":{"insight":0,"payroll":0,"onboard":0},"notes":"..."}]}
```
- `coverage` = 충족/전체, `weightedCoverage` = Σ충족 weight/Σweight, `panelScore` = 심판 3명(페르소나 옹호자 렌즈) 평균 0~10
- 확장(v2.1): `comparison.formula`("0.5·weightedCoverage·10 + 0.5·panelScore") · `comparison.ranking[{code,composite,weightedCoverage,panelScore}]` · `products[].gaps[]`에 `[must-fix:{judge}]`/`[nice-to-have:{judge}]` 접두 항목. 심판 개별 산출은 `_workspace/judging/{persona}.json`, 이전 버전은 `products/history/{version}.json`

## 13. Supabase — `supabase/`
- `schema.sql`: `departments`(org-chart 컬럼 snake_case, `dept_code` PK), `employees`(§3-1 snake_case, `emp_id` PK), `to_plan`(`dept_code` PK), `planned_joiners`(`joiner_id` PK), `planned_leavers`(`emp_id, planned_termination_date` PK), `cleansing_log`(`id bigserial`), `report_snapshots(id bigserial, product text, as_of_date date, payload jsonb, created_at timestamptz default now())`. RLS: 모든 테이블 enable, `anon`은 `report_snapshots` select만, `service_role` 전체
- `seed.py`: 정제 CSV/JSON → PostgREST upsert(`Prefer: resolution=merge-duplicates`, 배치 200, `urllib`만), report_snapshots에 product별 1행. `verify.py`: 행 수·합계(재직 406/휴직 21/TO 422/입사 19/퇴사 14)·최신 스냅샷 존재를 대사 → `supabase/verify-result.json`. `apply_schema.sh`: `supabase db push --db-url "$SUPABASE_DB_URL"`(migrations/ 사용) 또는 psql
- 자격증명: `.env.local`의 `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_ANON_KEY`, `SUPABASE_DB_URL` — 코드·커밋에 넣지 않는다

## 14. 로컬 테스트 — `tests/` (`python3 -m unittest discover -s tests -v`)
- `test_contract.py`: 정제 CSV 헤더·정규 값 도메인 = §3
- `test_reconciliation.py`: §2-7 조직표(11행 × HC/OL/TO/in/out/ME/gapAsOf/gapME/recommendation)와 Executive Snapshot(406/21/422/−16/19/14/411/−11), 속성 분포 8종이 headcount-stats·month-end-forecast·payroll-close·onboarding-plan·site/data/*.json에서 모두 일치
- `test_cleansing.py`: injected-defects의 각 결함이 cleansing-log에 같은 rowRef+field로 존재(재현율 ≥ 0.97), 미해결 유형(org-unknown/date-logic/status-inconsistency/missing-required/stale/unknown-emp) 플래그, orgNameCorrections=17·hireDateCorrections=31
- `test_site.py`: `site/**/index.html` 내장 JSON 존재, 외부 스크립트 도메인 허용 목록, 4개 뷰 키(executive/hr/planning/orgLead) 존재, PII 규칙(경영진 뷰 마크업에 hrDirectory 성명 미노출은 런타임이므로 스냅샷 규칙으로 검사)

## 15. 통합 제품 — `site/app/index.html` · `site/data/app.json` (제품 비교 이후)

제품 3종을 심판 3명이 채점한 뒤(§12) **하나의 제품**으로 합친다. 통합 제품 코드 `app`, 표시명 **Everyday People Agent**.
- 골격: `comparison.bestFit` 제품의 정보 구조를 기본으로 하고, 차점 제품의 `strengths`·`criteriaMet(met=true)` 섹션을 **역할 탭**으로 흡수한다
- 탭(역할) = 리포트 뷰 4종 + 급여 담당 `payroll` + 온보딩 담당 `onboarding` → 6개. 탭은 필터이며 재계산하지 않는다
- 스냅샷 `site/data/app.json` = `{stats, forecast, attrition, cleansingSummary, hrDirectory, automationEffect, payrollClose, onboardingPlan, plannedJoiners, comparison, changelog}`
- 각 섹션은 `data-section`·`data-role`(허용 역할 목록)·`data-fit`(충족하는 fitCriteria id)·`data-origin`(insight|payroll|onboard — 어느 제품에서 왔는가)을 가진다
- PII: 역할별 규칙은 §5의 뷰 규칙을 그대로 따른다. payroll·onboarding·hr 탭만 성명, 나머지는 사번/집계

## 16. 변경 이력·진화 루프 — `products/CHANGELOG.md` · `products/inputs/`

제품은 고정물이 아니다. 새 페르소나(또는 기존 페르소나의 새 요구)가 **인풋**을 넣으면 심판이 다시 채점하고 제품이 진화한다.
- `products/CHANGELOG.md`: Keep a Changelog 형식. 버전 `v{major}.{minor}` — 심판 라운드마다 minor +1, 통합 제품 재구성이면 major +1. 항목마다 `근거`(입력 파일·심판 점수 변화)와 `영향 받은 fitCriteria id`
- `products/inputs/{persona}-{YYYY-MM-DD}.json` — 페르소나 인풋 스키마:
```json
{"persona":"finance-controller","title":"재무 통제","submittedAt":"2026-09-23","source":"interview|survey|ticket|agent",
 "needs":[{"id":"FC-N1","need":"조직 그룹별 월말 급여 대상 인원을 Finance 예산 코드로 본다","importance":4}],
 "fitCriteria":[{"id":"FC-F1","criterion":"...","weight":4,"evidence":"payroll-close.payrollHeadcount.byDepartment"}],
 "rubric":{"lens":"...","scoring":"0~10, 기준: ..."} }
```
- 인풋 처리 순서(스킬 `product-evolution`): 인풋 검증(evidence가 §3~§11 경로인지) → `persona-needs.json`에 페르소나 추가/갱신 → 심판 재채점(`product-comparison.json` 갱신, 이전 버전은 `products/history/{version}.json`) → 통합 제품 재빌드 → CHANGELOG 항목 → 핸드오프 로그 `13-evolve`
- 계약에 없는 evidence를 요구하는 인풋은 거절하지 않고 `products/inputs/backlog.md`에 "계약 확장 필요"로 적재한다

## 17. Function Call 인터페이스 — `api/` (페르소나별 기존 시스템 연동)

세 페르소나는 각자 메인으로 보는 시스템이 있다(급여 시스템 / 온보딩 시스템 / 인사 총괄 시스템). Everyday People Agent는 화면뿐 아니라 **그 시스템 안의 agent가 Function Call로 호출하는 도구**로 존재해야 한다. 같은 공통 데이터 계층을 읽으므로 화면과 도구의 숫자는 같다(reconciliation-policy).

### 17-1. 도구 카탈로그 — `api/tools.json`
Anthropic `tool_use` 형식 배열 `[{name, description, input_schema}]` (OpenAI function 형식으로의 변환은 `api/tools.openai.json`에 동일 내용). 이름은 `{persona-system}.{동사}_{자원}`.

| 호출 시스템(페르소나) | 도구 | 반환(계약 경로) |
|---|---|---|
| 급여 시스템(payroll) | `payroll.get_close_summary(payPeriod)` | §10 payrollHeadcount + checklist + reconciliation |
| | `payroll.list_prorations(kind: actual\|planned)` | §10 prorations.* |
| | `payroll.list_leave_treatments()` | §10 leaves |
| | `payroll.list_contract_expirations(withinDays=90)` | §10 contracts |
| | `payroll.list_risks()` | §10 risks |
| 온보딩 시스템(onboarding) | `onboarding.get_timeline(week?)` | §11 timeline (+plannedJoiners unresolvedFlags 조인) |
| | `onboarding.get_department_plan(deptCode)` | §11 byDepartment[deptCode] + 조직 명부 subset |
| | `onboarding.get_checklist(joinerId?)` | §11 checklist |
| | `onboarding.get_early_tenure_cohort()` | §11 earlyTenureCohort + earlyAttrition |
| 인사 총괄 시스템(head-of-hr) | `insight.get_executive_snapshot(role)` | §4-1 totals + §4-2 totals (8 지표) |
| | `insight.get_department_forecast(deptCode?, role)` | §4-2 byDepartment/byOrgGroup + recommendation |
| | `insight.get_insights()` | §4-2 insights + immediateActions |
| | `insight.get_attribute_stats(attribute)` | §4-1 byAttribute[attribute] |
| | `insight.get_attrition_summary(role, deptCode?)` | §4-3 summary/byDepartment (role=hr일 때만 byEmployee 사번·밴드) |
| | `insight.get_data_quality()` | §3-6 요약 + §4-1 dataQuality |
| | `insight.run_scenario(hiringAchievementRate, extraAttrition)` | §4-2 scenario 공식으로 재계산(가정 표기) |
| 공통 | `report.get_monthly_dispatch()` | §6 dispatch(ready-to-send) |
| 공통(승인 gate) | `approval.request(action, payload)` | 실행하지 않고 `_workspace/approvals/{id}.json`에 "승인 대기" 기록을 남기고 그 id를 반환 |

- 모든 도구는 `role` 인자(기본 `executive`)에 따라 `pii-minimization-policy`를 적용한다: `executive|planning|orgLead` → 성명 제거·사번 유지(orgLead는 자기 조직만) / `hr|payroll|onboarding` → 성명 허용. 생년월일·리스크 점수는 어느 role에도 없다.
- 반환은 항상 `{status, asOfDate, role, data, provenance:{source, script}, claims:{implemented|mockup|approvalPending}}` 봉투.

### 17-2. 서버 — `api/server.py`(HTTP, 표준 라이브러리) · `api/mcp_server.py`(MCP stdio, JSON-RPC 2.0)
- HTTP: `GET /tools` → 카탈로그, `POST /call {name, arguments}` → 봉투. `GET /health`. 포트 기본 8787. 데이터는 `data/stats/*.json`·`data/clean/*.csv`를 읽기 전용으로 로드(재계산 없음, `run_scenario`만 공식 적용).
- MCP: `initialize` / `tools/list` / `tools/call` 를 stdio JSON-RPC로 처리 — Claude Desktop·Claude Code `.mcp.json`에 등록 가능. 외부 패키지 없음.
- 정적 배포용 `site/api/{tool-name}.json`: 인자 없는 읽기 도구의 결과를 미리 계산해 Vercel에 함께 배포(role=executive 기본). 인자 있는 도구는 로컬/서버에서만.

### 17-3. 검증 — `tests/test_api.py`
- 카탈로그의 모든 도구가 `input_schema`를 갖고 서버 디스패치에 존재
- `payroll.get_close_summary` 의 monthEndActive = `insight.get_executive_snapshot` 의 forecastMonthEnd = 411
- role=executive 응답 어디에도 `name` 키·성명 없음, role=payroll 응답에는 성명 있음
- `approval.request` 는 파일만 남기고 외부 효과 없음
- 데모 호출 기록 `_workspace/api-demo.md`: 세 시스템의 agent가 각각 1회 이상 호출한 실제 응답 발췌

## 18. 채택 근거 페이지 — `site/decision/index.html` · `site/data/decision.json`

"우리가 어떤 기준으로 최종 서비스를 채택했는가"를 **과정 그대로** 보여주는 설득 페이지. 통합 제품(app)과 허브에서 링크한다. 심판 결과를 요약만 하지 않고 루브릭 항목 단위로 노출한다.

- 스냅샷 `site/data/decision.json` = `{asOfDate, personas:[{code,title,product,keyQuestions,fitCriteria[],rubric}], judging:{payroll, onboarding, "head-of-hr"}(= _workspace/judging/*.json 그대로), comparison(= §12), changelog{path,markdown}, unified:{sections:[{dataSection, dataOrigin, dataRole[], dataFit[]}]}(= site/app/index.html에서 추출)}`
- 섹션 순서(= 설득 순서): ① 문제와 세 페르소나(핵심 질문·통증 시간 40h) → ② 니즈를 데이터로: fit 기준 표(id·기준·가중치·evidence) → ③ 제품 3종 카드(각 첫 화면 스크린샷 대체 = 섹션 목록) → ④ **심판 3명의 루브릭**: 심판별 렌즈·정성 항목(0~10 anchors)·제품 3종 점수 히트맵 + 기준 충족 매트릭스(✓/✗/미판정) + mustFix/niceToHave → ⑤ 종합: `comparison.formula`, `ranking`(composite·weightedCoverage·panelScore), bestFit, 불일치(disagreements) → ⑥ 통합 결정: 승자 골격 + 흡수 섹션 표(`data-origin`별), mustFix 해소 여부 → ⑦ 변경 이력(CHANGELOG 렌더) + 다음 인풋(`products/inputs/` 대기 목록, 재무팀장 인풋) → ⑧ claims(구현/목업/승인 대기)
- 각 섹션 `data-section="problem|criteria|products|rubric|ranking|unify|changelog|claims"`. 점수 색은 단일 액센트 명도 스케일(디자인 시스템), 숫자 병기
- 심판 파일이 없으면 "심판 대기 중" 상태로 완전한 페이지여야 한다(허브와 같은 규칙)

### 17-4. Jev(TypeSafe System One) — 보류 중 (2026-09-23 사용자 지시)

판정 성격의 결정 지점에 선택적으로 붙일 수 있는 외부 결정 모델. `api/jev.py`에 클라이언트와 래퍼 4종이 있고 **키가 없으면 전부 규칙 기반 폴백**이므로 현재 파이프라인은 Jev 없이 동작한다.

| 결정 지점 | 원시형 | 래퍼 | 폴백 |
|---|---|---|---|
| 규칙으로 못 고친 소속명 → 조직 배정 | choice(11) | `classify_department` | 직군→조직 기본 매핑 + 미해결 플래그 |
| 자유 텍스트 퇴직사유 → 정규 사유 | choice(7) | `classify_separation_reason` | 키워드 매핑 |
| 심판 루브릭 항목 채점 | score(0~10 anchors) | `score_rubric_item` | 심판 에이전트의 정성 판단 |
| 승인 gate 판별 | noul ×2 | `needs_approval` | approval-gate-policy 목록(기본 "필요") |

규칙: 응답은 `_workspace/jev-cache/`에 캐시해 같은 입력 → 같은 판정(대사 성립), 판정 1건 1행을 `_workspace/jev-decisions.jsonl`에 남김, `confidence < 0.60`은 자동 채택하지 않고 미해결로 넘김. 키 자리: `.env.local`의 `TYPESAFE_API_KEY`.
