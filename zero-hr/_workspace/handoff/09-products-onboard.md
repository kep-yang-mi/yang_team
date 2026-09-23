# 09-products-onboard — product-builder(onboard) · asOfDate 2026-09-23 · 2026-09-23

## 시도한 것
- `site/onboard/index.html` 신규 작성 — page-template.md 골격(시스템 폰트·CSS 토큰 라이트/다크·공통 헤더 5요소 + 기간(asOfDate~horizonEnd)·내장 JSON·Supabase 덮어쓰기·Chart.js jsdelivr 1개·375px·접근성) + product-specs.md §3 순서(kpi → timeline → departments → checklist → next-month → cohort → early-attrition → reconciliation) + 푸터 `data-section="claims"`.
- `python3 .claude/skills/product-build/scripts/build_snapshots.py --root /Users/yang/development/zero-hr --as-of 2026-09-23 --product onboard --embed` → `site/data/onboard.json` 95,776 bytes 조립·내장, 요약 status=ok, gaps 0.
- `python3 -m unittest tests.test_site -v` 실행.
- 렌더 확인: Chrome 확장 미연결(`tabs_context_mcp` 실패) → `python3 -m http.server 8767` HTTP 200 확인 후 Python으로 내장 JSON 파싱·외부 스크립트 도메인·섹션 속성·주차 강조 로직·JS 문법(node `new Function`)을 검사하고 서버 종료.
- 디자인 시스템 적용(코디네이터 지시, `references/design-system.md` 기준): CSS 토큰을 Anthropic 스타일로 교체 — 캔버스 #f0eee6 / 카드 #faf9f5(radius 24px, 1px #cccbc8, 그림자 없음) / 잉크 #141413 / 단일 액센트 클레이 #d97757(이번 주 강조·일괄 온보딩 표시에만) / 대지색 series 4 / 상태색은 배지 테두리만. 헤드라인·KPI 숫자 serif(Source Serif 4 + Noto Serif KR), UI sans(Inter + Noto Sans KR), 코드 mono(IBM Plex Mono) — Google Fonts `<link>` 1개 추가(허용된 유일한 외부 스타일시트). 이모지(✓/✗/·) → 글자 배지(완료/대기/일치/불일치), 둥근 배지 → 각 배지, KPI 묶음은 `--surface-hero`(Manilla) 1장, claims 푸터는 `--surface-2` 패널 3열 표. 파랑·그라데이션·그림자·uppercase 잔재 0건(grep).
- v2 키만 사용: `byDepartment[].deptCode/department/joiners/joinersByMonthEnd/buddyCandidates[]/deptLeadEmpId`, `level`, `hrDirectorySubset[]` 5필드. `newTeamOnboarding`은 v2에 없어 섹션을 만들지 않음(대신 월말 3명 이상 조직을 "일괄 온보딩 대상"으로 강조).

## 본 데이터·근거
- `site/data/onboard.json` = `{onboardingPlan, plannedJoiners(27행, birthDate 없음), hrDirectorySubset(406행, 9조직)}`; `onboardingPlan.asOfDate` 2026-09-23 · `horizonEnd` 2026-10-31 · timeline 5주(W39 13 · W40 8 · W41 2 · W42 2 · W44 2) · byDepartment 9 · checklist 27행 × 6항목 · earlyTenureCohort 12(고위험 1) · earlyAttrition 1/14 = 0.0714.
- `personas/persona-needs.json` persona `onboarding`: keyQuestions 7 → 섹션 순서, kpis 6 → 타일, fitCriteria O-F1~O-F13 → `data-fit`.
- 계약·정책: DATA_CONTRACT §5(스냅샷 구성)·§11(onboarding-plan shape)·§17(api/tools.json 링크), product-specs §0 evidence 접두 표·§3·§5(v1→v2), pii-minimization-policy(성명은 입사 예정자·버디·조직장만, 코호트 사번만, 등급만), reconciliation-policy(페이지 재계산 금지 — 27·19는 `provenance.reconciliation`에서 읽음), claims-boundary-policy(체크리스트 = 목업 표기).
- `_workspace/handoff/07-onboarding.md` 인계점: O-F7은 `plannedJoiners` 조인으로 표시(타임라인에 unresolvedFlags 없음) → 그대로 구현.

## 실패한 것
- 브라우저 렌더 미확인: Claude in Chrome 확장이 연결되지 않아 스크린샷·콘솔 오류 0·375px 가로 스크롤을 실제 브라우저에서 보지 못함. Python/node 검사로 대체(렌더 미확인 — 다음 실행자가 `cd site && python3 -m http.server 8767` 후 `/onboard/` 열어 확인 필요).
- `tests.test_site` 11건 중 1건 FAIL — `test_payroll_has_no_amount_fields`: `site/data/payroll.json`의 `payrollClose.provenance.rules.pii` 문자열("…급여액 없음")에 금지어 '급여액'이 포함. **payroll 빌더/payroll-close-analyst 소관**(onboard 산출물과 무관). 나머지 10건 ok/skip.
- O-F11 evidence 중 `month-end-forecast.totals.nextMonth.plannedIn`은 onboard 스냅샷(§5)에 없어 대조하지 못함 — 조직별 10월 인원은 `byDepartment[].joiners − joinersByMonthEnd`(표시용 뺄셈, 각주)로만 표시.
- O-F13(`api/tools.json onboarding.*`)은 제품 밖 산출물 — 헤더에 `../api/tools.json` 링크만 걸었고 `api/`는 이 시점에 없음(api-integrator 담당). 링크는 배포 전까지 404.
- `unresolvedFlags`가 27행 모두 빈 값이어서 플래그 배지는 "플래그 없음"만 렌더됨(로직은 값이 있으면 클린저 어휘 그대로 배지).

## 검증된 것
- 스크립트 대사(자기 검사) 3/3 일치: timeline(joiners)=planned-joiners.clean(validRows) 27=27 · byMonthEnd=forecast.totals.plannedIn 19=19 · checklist.status.length=timeline 27=27. `reconciliation.matched: true`.
- 내장 JSON 파싱 OK(`<\/` 이스케이프 복원 후), 최상위 키 3개. 외부 `<script src>`는 `cdn.jsdelivr.net/npm/chart.js@4.4.1` 1개, `<link href>` 없음.
- 주차 강조: 기준일 2026-09-23 ∈ 2026-W39(09-21~) → "이번 주"(13명), 2026-W40(09-28~) → "다음 주"(8명) — Python으로 같은 규칙 재현 확인.
- PII grep: HTML에 `riskScore`·`birthDate`·`ageBand` 0건, 스냅샷에 `"birthDate"` 0건, 코호트 members에 `name` 없음. 성명은 timeline·byDepartment.buddyCandidates·hrDirectorySubset(조직장 조인)에만.
- 섹션 속성: header/kpi/timeline/departments/checklist/next-month/cohort/early-attrition/reconciliation/claims 전부 `data-section`·`data-fit`·`data-evidence` 보유. 인라인 JS 문법 OK(node `new Function`).
- 독립 대사는 하지 않았다 — people-data-auditor(`tests/test_reconciliation.py`)가 정제 CSV에서 재집계해야 운영 판정.

## 다음 agent 인계점
- product-judge(onboarding 옹호자): `site/onboard/index.html` 섹션 `data-fit` 매핑 — O-F1/O-F7/O-F10 → timeline · O-F2/O-F4 → departments · O-F3 → checklist · O-F5/O-F9 → cohort(+ footer claims) · O-F6 → early-attrition · O-F8 → kpi + reconciliation · O-F11 → next-month(부분: forecast nextMonth 미대조) · O-F12/O-F13 → header(O-F13은 api/ 산출물로 판정). 반환값 `fitCoverage`는 자기 보고.
- api-integrator: `api/tools.json`(onboarding.get_timeline·get_department_plan·get_checklist·get_early_tenure_cohort)을 만들면 헤더 링크 `../api/tools.json`이 살아난다. 정적 배포용은 `site/api/*.json`(§17-2) — 경로가 바뀌면 헤더 링크 1곳만 수정.
- payroll 빌더 / payroll-close-analyst: `payrollClose.provenance.rules.pii` 문구의 '급여액'이 `test_payroll_has_no_amount_fields`를 깨뜨림 — 문구를 "금액 필드 없음"으로 바꾸거나 테스트 금지어 범위를 조정.
- release-engineer: `site/data/onboard.json`을 `report_snapshots(product='onboard')`에 적재하면 헤더 배지가 `Supabase · 2026-09-23`으로 바뀜(config.js 있을 때만). `../config.js` 404는 정상 경로.
- 허브(hub) 빌더: 카드 링크 `onboard/index.html`, 표시명 Onboarding(온보딩 담당).
- 재실행: 상류(onboarding-plan.json·planned-joiners.clean.csv·headcount-master.clean.csv) 갱신 시 `--product onboard --embed`만 재실행(HTML 불변). 렌더 확인은 브라우저 연결 후 `http://localhost:8767/onboard/`에서 콘솔 오류 0·타일 27/19·이번 주 강조·375px 가로 스크롤 없음을 확인할 것.
- contractGaps: 없음(§5 밖 키 추가하지 않음). 다음 달 입사 대조를 위해 onboard 스냅샷에 `forecast.totals.nextMonth.plannedIn` 한 값이 있으면 O-F11 대조가 가능 — 계약 확장 제안으로만 남김.
