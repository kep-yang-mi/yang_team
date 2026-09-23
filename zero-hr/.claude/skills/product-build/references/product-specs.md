# 제품별 화면 구성 초안 — 페르소나 fit 매핑

제품은 니즈 데이터(`personas/persona-needs.json`)의 fit 기준에 맞춰 만든다. 이 문서는 각 제품의 섹션·차트·표 초안을
**fit 기준 후보(id) ↔ 스냅샷 데이터 경로**로 묶어 둔 것이다. id는 `persona-needs` 스킬의 참고 프로필 후보이므로,
실제 니즈 파일의 id·문장과 다르면 **니즈 파일이 이긴다** — 섹션의 `data-fit`은 항상 실제 파일에서 채운다.

목차: 0 fit 매핑 규칙 · 1 Insight · 2 Payroll Close · 3 Onboarding · 4 허브 · 5 계약 정렬 메모(v1→v2)

## 0. fit 매핑 규칙 — evidence 접두 → 섹션

니즈 파일의 `fitCriteria[].evidence`를 스냅샷 키로 바꿔 어느 섹션이 어느 기준을 맡는지 정한다. 기준 문장을 읽고 감으로 배치하지 않는 이유:
product-judge가 같은 규칙으로 `data-evidence`를 대조하므로, 규칙이 다르면 빌더는 "충족"이라 하고 심판은 "미충족"이라 하게 된다.

| evidence 접두 (니즈 파일) | 스냅샷 키 (data-evidence) | 제품 | 비고 |
|---|---|---|---|
| `headcount-stats.` | `stats.` | insight | Payroll은 `statsSubset.` |
| `month-end-forecast.` | `forecast.` | insight | Payroll 화면은 예측을 직접 쓰지 않고 `payrollClose.payrollHeadcount.monthEnd`를 쓴다 |
| `attrition-risk.` | `attrition.` | insight | 개인 행은 HR 뷰만 |
| `cleansing-summary.` | `cleansingSummary.` | insight, payroll | |
| `automation-effect.` | `automationEffect.` | insight | 추정 표기 필수 |
| `headcount-master.clean.` | `hrDirectory[]` / `hrDirectorySubset[]` | insight(HR 뷰), onboard | 성명 조인 전용 |
| `payroll-close.` | `payrollClose.` | payroll | |
| `onboarding-plan.` | `onboardingPlan.` | onboard | |
| `planned-joiners.clean.` | `plannedJoiners[]` | onboard | `unresolvedFlags` 배지 |
| `site/{product}/index.html {뷰명|공통 헤더}` | (헤더/뷰 자체) | 해당 제품 | `data-section="header"` 또는 뷰 선택기 |
| `policy:pii-minimization-policy` | (부정 기준 — 없어야 하는 것) | 전 제품 | 반환값 `pii`로 자기 보고, 심판이 grep |
| `reconciliation:{A}={B}` | (두 값 비교) | 전 제품 | `build_snapshots.py` 요약의 `reconciliation.checks`가 증거 |
| `reports/` | (제품 밖) | — | Insight에 월초 리포트 링크만. 충족 여부는 mailer 산출물로 심판이 판단 |
| `api/tools.json {tool prefix}` | (제품 밖 — Function Call 인터페이스 §17) | 전 제품 | 화면은 헤더에 '이 데이터를 도구로 호출' 링크(`../api/` 또는 카탈로그). 충족 여부는 `api/tools.json`·`tests/test_api.py`·`_workspace/api-demo.md`로 심판이 판단 |

evidence가 위 표 어디에도 없으면 그 기준은 만들 수 없는 것이다 — 반환값 `fitCoverage.criteriaUncovered`에 사유와 함께 적는다.

## 1. Insight — 인사 총괄 (head-of-hr) · `site/insight/index.html` · `site/data/insight.json`

스냅샷: `{stats, forecast, attrition, cleansingSummary, hrDirectory, automationEffect}`.
핵심 질문: "지금 현원은? TO 대비 어디가 비었나? 월말·다음 달은? 누가 흔들리나? 데이터는 믿을 만한가?"

### 1-1. 뷰(권한) 선택기 — `data-section="views"` · H-F2

라디오 4개: `executive`(경영진) · `hr`(HR) · `planning`(경영기획) · `orgLead`(조직장). URL `?view=`로 진입 가능, 마지막 선택은 `localStorage`(try/catch).
같은 지표는 뷰가 달라도 같은 값 — 뷰는 **필터**이지 재계산이 아니다. 모든 섹션은 하나의 `DATA`에서 그린다.

| 뷰 | 보는 것 | 숨기는 것(PII) |
|---|---|---|
| executive | 총계 KPI, 본부(조직 그룹) 단위 현황·예측·과부족, 인사이트, 리스크 요약(밴드 집계), 자동화 효과 | 성명·사번·개인 목록·팀 단위 상세 |
| hr | 전부 + 속성 통계·크로스탭·경력·퇴직 분석·리스크 개인 목록(성명 조인)·클린징 로그 요약·미해결 질문·명부 | 생년월일(어디에도 없음) |
| planning | 팀 단위 TO 과부족·월말/다음 달 예측·리스크 반영 시나리오·입퇴사 예정(사번/joinerId만)·인사이트·시나리오 플래너 | 성명 |
| orgLead | 선택한 조직(본부/실/팀) 하나의 현원·예측·과부족·입퇴사 예정 **건수** | 타 조직 상세, 성명, 사번 |

### 1-2. 섹션 초안 (표시 순서)

| # | data-section | 뷰 | 구성 | data-evidence | fit 후보 |
|---|---|---|---|---|---|
| 1 | `header` | 전체 | 공통 헤더 + 월초 리포트 링크(`reports/monthly-report-2026-10.html`, 있을 때만) | — | H-F11, H-F12 |
| 2 | `kpi` | 전체 | 타일: 현원(재직+휴직) · 실근무 · 휴직 · TO · 기준일 TO 대비 · 월말 예측 · 월말 TO 대비 · TO 충족률 · 입사/퇴사 예정 · 퇴직 YTD · 미해결 건수 | `stats.totals.*` `forecast.totals.*` | H-F1(부분), H-F8(건수) |
| 3 | `division-gap` | executive, planning, hr | 본부별 현원/월말 예측/TO 발산 막대 + 표(HC·TO·in·out·ME·gap 기준일/월말) | `forecast.byDivision[]` | **H-F1** |
| 4 | `insights` | executive, planning, hr | 인사이트 카드: type 배지 · label · rationale · action | `forecast.insights[]` | **H-F4** |
| 5 | `risk-summary` | executive, planning, hr | 밴드 집계 타일 + 본부별 기대 이탈(3개월) 표. 개인 없음 | `attrition.summary` `attrition.byDivision[]` | H-F5(부분) |
| 6 | `automation-effect` | executive, hr | 수작업 40h vs 검토 8h, 절감률 80% "(추정)" 타일 + breakdown 표 | `automationEffect.*` | H-F10 |
| 7 | `team-forecast` | planning, hr | 팀별 표: TO·현원·in·out·월말·gap(기준일/월말)·다음 달(in/out/ME/gap)·리스크 반영 ME. 팀 gap 발산 막대 | `forecast.byTeam[]` `forecast.byTeam[].nextMonth` `forecast.byTeam[].riskAdjusted` | **H-F5** |
| 8 | `planned-moves` | planning, hr | 입사 예정(joinerId·팀·일자·고용유형) / 퇴사 예정(empId·팀·일자·구분) 두 표. planning은 사번만, hr은 `hrDirectory` 조인으로 성명 표시 가능 | `forecast.plannedJoiners[]` `forecast.plannedLeavers[]` | H-F13 |
| 9 | `scenario` | planning | 시나리오 플래너(GLOSSARY v2): 채용 달성률 %·추가 이탈 인원 슬라이더 → 월말·다음 달 인원 재계산(클라이언트, "시나리오(가정)" 표기, 저장 안 함) | `forecast.totals` `forecast.byTeam[]` | (v2 항목 — 니즈 파일에 기준이 있을 때만 data-fit) |
| 10 | `attributes` | hr | 속성별 막대 8종(고용유형·성별·연령대·직군·직책·연차·스테이지·휴직유형) + 크로스탭 선택 표 6종 | `stats.byAttribute.*` `stats.crossTabs.*` | **H-F9** |
| 11 | `experience` | hr | 재직기간·총경력 평균/중앙값 타일 + 히스토그램 2개 + 본부별 표 | `stats.experience.*` | H-F9(보조) |
| 12 | `separations` | hr | 퇴직 YTD 합계·유형·사유 표, 월별 추이 선 차트(자발/비자발/기타), 본부·연차 구간 표, 전년 비교 | `stats.separations.ytd.*` `stats.separations.prevYear` | **H-F6** |
| 13 | `risk-people` | hr | 리스크 높음(→중간) 개인 목록: empId·성명(`hrDirectory` 조인)·팀·직책·밴드·topFactors. **점수는 표시하지 않고 밴드만**. 팀 필터 | `attrition.byEmployee[]` `hrDirectory[]` | **H-F7** |
| 14 | `data-quality` | hr | 보정 규칙별 건수 표, 미해결 건수, 미해결 항목 표(source·rowRef·field·rawValue·question) | `cleansingSummary.correctionsByRule` `cleansingSummary.unresolvedItems[]` | **H-F8** |
| 15 | `directory` | hr | 명부 검색 표(empId·성명·팀·직책). 생년월일 없음 | `hrDirectory[]` | (H-F7 보조) |
| 16 | `org-lead` | orgLead | 조직 선택(본부→실→팀 셀렉트) → 그 조직만: 현원·월말·TO·gap 타일 + 입사/퇴사 예정 **건수** + 하위 조직 표 | `forecast.byDivision[]` `forecast.byOffice?` `forecast.byTeam[]` | (v2 항목) |

- `forecast.byOffice`는 계약 §4-2에 없다(본부·팀만). orgLead 뷰의 실 단위는 `stats.byOffice`(현원)로만 채우고 예측은 팀 합산으로 만든다 — 합산은 표시용이며 대사 대상이 아님을 각주로 적는다.
- 리스크는 어느 뷰에서도 **점수(riskScore)를 표시하지 않는다**(니즈 데이터의 PII 원칙: 등급만).

### 1-3. 차트 색

본부/조직 그룹 4개 → `--series-1..4` 코드 순 고정. TO 과부족 → 발산(`--diverge-neg`/`--diverge-pos`). 퇴직 유형 3개 → `--series-1..3`. 속성별 단일 시리즈 막대 → `--series-1`.

## 2. Payroll Close — 급여 담당 (payroll) · `site/payroll/index.html` · `site/data/payroll.json`

스냅샷: `{payrollClose, statsSubset, cleansingSummary}`. 급여액·수당·계좌는 어디에도 없다(GLOSSARY 제외).
핵심 질문: "이번 달 누구에게, 어떤 구분으로 지급하나? 일할 대상은? 휴직자는? 곧 끝나는 계약은? 틀릴 위험은?"
화면 순서는 급여 담당의 마감 작업 순서다 — 체크리스트를 맨 위에 두는 이유는 "pending만 보면 되게" 하기 위함.

| # | data-section | 구성 | data-evidence | fit 후보 |
|---|---|---|---|---|
| 1 | `header` | 공통 헤더 + 급여 기간(`payPeriod`, `periodStart`~`periodEnd`) | `payrollClose.payPeriod` | P-F10 |
| 2 | `kpi` | 타일: 기준일 급여 대상 · 월말 급여 대상(= 월말 예측, "예측과 일치 ✓" 배지) · 월말까지 입사/퇴사 예정 · 휴직 · 90일 내 계약 만료 · 위험 건수 · 체크리스트 pending | `payrollClose.payrollHeadcount.asOf` `payrollClose.payrollHeadcount.monthEnd` | **P-F1** |
| 3 | `checklist` | 마감 체크리스트 표(item·count·status), pending 먼저 정렬, 상태 배지(✓ done / · pending) | `payrollClose.checklist[]` | P-F8 |
| 4 | `headcount` | 고용유형별 막대(asOf vs monthEnd 2시리즈) + 본부별 표 + 팀별 표(22팀, asOf·in·out·monthEnd). `statsSubset.totals.headcount`와 같은 값 각주 | `payrollClose.payrollHeadcount.byEmploymentType` `.byDivision[]` `.byTeam[]` `statsSubset.totals` | P-F7 |
| 5 | `prorations-actual` | 당월 확정 입사자 표 / 확정 퇴사자 표: 성명·팀·일자·근무일수·비율(소수 3자리) | `payrollClose.prorations.joinersInPeriod[]` `.leaversInPeriod[]` | **P-F2** |
| 6 | `prorations-planned` | 월말까지 입사 예정 / 퇴사 예정 표(확정과 다른 배경·"예정" 배지). `already-separated` 제외 표시 | `payrollClose.prorations.plannedJoinersByMonthEnd[]` `.plannedLeaversByMonthEnd[]` | P-F3, P-F12 |
| 7 | `leaves` | 처리 구분 타일 3종(무급(정부 급여)/유급/무급) + 휴직자 표(성명·팀·유형·시작일·처리) | `payrollClose.leaves.byTreatment` `payrollClose.leaves.onLeave[]` | P-F4 |
| 8 | `contracts` | 월별 만료 건수 막대(0 포함) + 90일 내 만료 표(성명·팀·고용유형·만료일, D-day) | `payrollClose.contracts.byMonth` `.expiringWithin90Days[]` | P-F5 |
| 9 | `risks` | 위험 표: empId·issue·impact·unresolvedFlag 배지. 어휘 구분: 클린저 어휘 = "고객사 HR 확인 대기", 파생 어휘 = "급여 담당 즉시 확인" | `payrollClose.risks[]` | **P-F6**, P-F12 |
| 10 | `data-quality` | 미해결 건수(Insight와 같은 값) + 미해결 항목 표 | `cleansingSummary.unresolvedCount` `cleansingSummary.unresolvedItems[]` | P-F11 |

PII: 성명 허용(업무상 필요), 생년월일·연령대 없음, 리스크 없음(급여와 무관), 금액 필드 없음 — P-F9는 "없음"을 심판이 grep으로 확인한다.
색: 고용유형 4종 → `--series-1..4` 고정(정규직·계약직·파견·인턴 순). 상태 배지만 `--good`/`--warning`.

## 3. Onboarding — 온보딩 담당 (onboarding) · `site/onboard/index.html` · `site/data/onboard.json`

스냅샷: `{onboardingPlan, plannedJoiners, hrDirectorySubset}`.
핵심 질문: "이번 주·다음 주 누가 어느 팀으로 오나? 준비됐나? 버디는? 신설팀은 한 번에? 최근 입사자 중 흔들리는 사람은?"

| # | data-section | 구성 | data-evidence | fit 후보 |
|---|---|---|---|---|
| 1 | `header` | 공통 헤더 + 기간(`asOfDate`~`horizonEnd`) | `onboardingPlan.horizonEnd` | O-F12 |
| 2 | `kpi` | 타일: 입사 예정 총원 · 이번 주 · 다음 주 · 신설팀 입사 · 90일 코호트 · 코호트 고위험 · 1년 미만 이탈률 | `onboardingPlan.timeline[]` `.earlyTenureCohort.count` `.earlyAttrition.rate` | — |
| 3 | `timeline` | ISO 주차 탭/열: 주차마다 입사자 카드(성명·팀·일자·고용유형·직책·스테이지). 기준일이 속한 주 = "이번 주", 다음 = "다음 주" 강조. `plannedJoiners`를 joinerId로 조인해 `unresolvedFlags` 배지. horizonEnd 이후는 "이후 입사"로 구분 | `onboardingPlan.timeline[]` `plannedJoiners[].unresolvedFlags` | **O-F1**, O-F8, O-F11, O-F9(합계 각주) |
| 4 | `teams` | 팀 카드: 입사 예정 수 · 신설 배지 · 팀장(`teamLeadEmpId` → `hrDirectorySubset` 조인, 없으면 "팀장 미정") · 현 팀 인원(subset 수) · 버디 후보 표(성명·재직기간·리스크 등급) | `onboardingPlan.byTeam[]` `onboardingPlan.byTeam[].buddyCandidates[]` `hrDirectorySubset[]` | O-F2, O-F5 |
| 5 | `checklist` | 입사자 × 6항목 매트릭스(✓/·), 입사자별 진행률, 항목별 완료율. "가상 생성(seed 고정)" 각주 | `onboardingPlan.checklist.items` `onboardingPlan.checklist.status[]` | **O-F3** |
| 6 | `new-team` | 신설팀 일괄 온보딩 카드: 팀·발족일·입사자(joinerId→타임라인 조인 성명)·notes(임시 리더) · "일괄 세션" 체크 | `onboardingPlan.newTeamOnboarding[]` | **O-F4** |
| 7 | `cohort` | 입사 90일 코호트 표: empId·팀·입사일·경과일·리스크 등급(성명 없음). 고위험 먼저 | `onboardingPlan.earlyTenureCohort.members[]` | O-F6 |
| 8 | `early-attrition` | 1년 미만 이탈률 타일 + 본부별 막대·표 | `onboardingPlan.earlyAttrition` `onboardingPlan.earlyAttrition.byDivision` | O-F7 |

PII: 입사 예정자·버디 후보·팀장 성명 허용(업무상), 생년월일·연령대 없음(`plannedJoiners`에서 birthDate 제거됨), 코호트는 사번만, 리스크는 등급만(점수 없음) — O-F10.
색: 체크리스트 done `--good`/pending `--ink-muted`(텍스트 병기). 리스크 등급 높음 `--critical`·중간 `--warning`·낮음 `--good`(항상 글자와 함께). 본부 → `--series-1..4`.

## 4. 허브 — `site/index.html` · `site/data/comparison.json` (§12)

| # | data-section | 구성 | data-evidence |
|---|---|---|---|
| 1 | `header` | 브랜드(Zero Company HR · Everyday People Agent) · 고객사 · 기준일 · 출처 배지 | `asOfDate` |
| 2 | `products` | 제품 카드 3장(고정 순서 insight → payroll → onboard): 표시명·페르소나·한 줄 역할·진입 링크·fit 타일(coverage·weightedCoverage·panelScore) | `products[]` |
| 3 | `comparison` | 비교 표: fit 3지표 · 공통 계층 재사용률 · 고유 기능 · 구축 공수(agentMinutes·linesOfHtml) · 강점 · 갭 | `products[].fitScore` `products[].sharedLayerReuse` `products[].buildEffort` |
| 4 | `criteria` | 기준 충족 매트릭스: 제품별 `criteriaMet[]`(id·met ✓/✗·evidence). 페르소나별 그룹 | `products[].fitScore.criteriaMet[]` |
| 5 | `verdict` | bestFit · summary · recommendation + 심판 3명 점수 표·노트 | `comparison.*` `judges[]` |
| 6 | `pipeline` | 공통 데이터 계층 → 페르소나 → 제품 → 심판 흐름 한 줄(정적 텍스트) | — |

- `products`가 비어 있으면(첫 빌드, product-judge 이전) 카드는 링크만 살리고 fit 타일·비교·매트릭스는 "제품 비교 대기 중 — product-judge 실행 후 `--product comparison --embed`" 안내를 보인다. 페이지는 그 상태로도 완전해야 한다.
- 기준 문장(criterion)은 §12에 없어 id만 보인다 — 계약 확장 제안은 반환값 `contractGaps`에.

## 5. 계약 정렬 — DATA_CONTRACT v2 확정 (2026-09-23)

v2 계약이 확정되었다. 위 §1~§4의 v1 키는 아래 표로 읽는다. **스냅샷은 v2 키만 갖는다.**

| v1 표기(위 표) | v2 키(스냅샷 실제) | 비고 |
|---|---|---|
| `byDivision` / `division-gap` | `forecast.byOrgGroup[]` (조직 그룹 4) | 라벨 "조직 그룹" |
| `byTeam` / `team-forecast` / `byOffice` | `forecast.byDepartment[]` (조직 11) — 실(office) 계층은 없다 | orgLead 뷰는 조직 1개 선택 |
| `teamCode` / `team` | `deptCode` / `department` | hrDirectory·onboarding·payroll 전부 |
| `position` | `level` (IC1~VP) | |
| `headcount`(=406) | `activeHeadcount`(406, TO 기준) · `headcount`(427 총원) · `onLeave`(21) | KPI 타일 3개로 분리 |
| `forecast.totals.headcount` | `forecast.totals.activeHeadcount` | |
| `payrollClose.payrollHeadcount.asOf/monthEnd` | `.asOfTotal`(427) / `.monthEndActive`(411) / `.monthEndTotal`(432) | |
| `onboardingPlan.byTeam[]`/`teamLeadEmpId` | `onboardingPlan.byDepartment[]` / `deptLeadEmpId` | |
| 스테이지 S1~S5 | Seed / Series A / Scale-up / Enterprise | |
| `stats.separations.ytd` | `stats.plannedSeparations` (퇴사 예정자 기준: total 14, bySeparationReason, bySeparationType, byDepartment, byTenureBand, byMonth) | 과거 퇴직 이력은 범위 밖 |
| `insights[]` 3유형 | `forecast.insights[]`(type/scope/codes/label/detail/action) + `forecast.immediateActions[]` + `forecast.byDepartment[].recommendation` | 조직 표에 권고 열 추가 |
| 제품 표시명 ZeroHR * | Insight / Payroll Close / Onboarding (브랜드 Everyday People Agent) | |
| 뷰 3종 | 4종 executive / hr / planning / orgLead | |

**통합 제품 `app`(§15):** `site/app/index.html` · 스냅샷 `site/data/app.json` = insight ∪ payroll ∪ onboard 구성 요소 + `comparison` + `changelog{path,markdown}`. 역할 탭 6종(`?role=executive|hr|planning|orgLead|payroll|onboarding`). 각 섹션 `data-section` · `data-role` · `data-fit` · `data-origin`.
