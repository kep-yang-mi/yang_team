# 10-report — monthly-report-mailer 핸드오프 로그 (2026-09-23)

## 시도한 것
- `.claude/skills/monthly-report/scripts/render_report.py`를 DATA_CONTRACT **v2 §6**으로 전면 재작성(937행 → 315행). 산출 4종: `reports/monthly-report-2026-10.md`·`.html`(인라인 스타일), `reports/org-forecast-2026-09.csv`(§6 열 10개·11행), `reports/monthly-report-dispatch.json`(수신자 4그룹 executive/hr/planning/**orgLead**, 전부 `@ondatech.example`, `sendAt 2026-10-01T09:00:00+09:00`, `schedule 0 9 1 * *`, `status ready-to-send`, `gate approval-gate: 외부 발송`, attachments `site/insight/index.html`·CSV).
- 본문 순서(§6): 제목 → 요약(재직/월말·gap·채용 가속·TO 재검토·즉시 액션 3건·첨부) → Executive Snapshot → 조직별 예측 표(§2-7 열) + 조직 그룹 표 + 인사이트/판정 규칙/가정 → (리스크 시나리오, 있으면) → 인원 통계 요약(속성 8종) → 퇴사 예정 사유 → 데이터 품질(클린징 요약·미해결·브리프 불일치) → 자동화 효과 → 부록 정의.
- 신규 `.claude/skills/monthly-report/scripts/automation_effect.py`(§8): `_workspace/run_meta.json` durations → `pipelineSeconds`(없으면 0 + note), 수작업 40h/검토 8h/savingRate 0.8.
- 신규 `.claude/skills/monthly-report/SKILL.md`(63행).

## 본 데이터·근거
- DATA_CONTRACT v2 §6·§7·§8·§4-1·§4-2·§10(payroll monthEndActive 대사), 브리프 §9(조직장 권한)·§10(이메일 예시), GLOSSARY 정책(pii-minimization·reconciliation·approval-gate).
- 실데이터 부재 → 픽스처(`_workspace/fixtures/stats-forecast-report/`, 삭제됨)로 렌더.

## 실패한 것
- 실데이터 미검증(**untested against real data**). 리스크 시나리오 절(`attrition-risk.json`)·급여 대사 절(`payroll-close.json`)·클린징 요약 절은 선택 입력 부재로 분기만 존재.
- PII 스캔은 정제 성명(3자 이상)의 부분 문자열 검사라 이론상 오탐 가능(조직명·문구와 우연히 겹칠 때). 발생하면 exit 4와 `names` 건수로 드러난다.

## 검증된 것 (픽스처 기준)
- `render_report.py` exit 0, 4개 파일 생성. 요약 문장이 §6과 동일(재직 406 / 월말 411 · gap −11 · Engineering, Sales · Data & AI · 즉시 액션 3건). 본문에 픽스처 성명 0건.
- dispatch 수신자 17명 전부 `@ondatech.example`, 4그룹 키 존재. CSV 11행이 forecast.byDepartment와 일치(`tests/test_reconciliation.py::test_org_forecast_csv` 통과).
- 대사 실패 경로: forecast.totals.activeHeadcount를 405로 훼손 → exit 2, `_workspace/monthly-report.unreconciled.json` 진단, reports/ 미작성. PII 경로: 인사이트 라벨에 성명 주입 → exit 4, 미작성. 입력 없음 → exit 3.
- `automation_effect.py`: run_meta 없음 → pipelineSeconds 0 · 있음(durations 합) → 4.3 반영.

## 다음 agent 인계점
- 실행 순서: `compute_stats.py` → `forecast.py` → `automation_effect.py` → `render_report.py`(모두 `--root /Users/yang/development/zero-hr --as-of 2026-09-23`). 선택 입력(attrition-risk·payroll-close·cleansing-summary)이 나중에 생기면 **재실행**만 하면 해당 절이 채워진다.
- `release-engineer`: `reports/monthly-report-dispatch.json`을 승인 요청에 첨부. 실제 발송·cron 등록은 사용자 승인 후(approval-gate). `pipelineSeconds`는 오케스트레이터가 `run_meta.json`을 쓴 뒤 `automation_effect.py`를 다시 돌려 갱신.
- `people-data-auditor`: `python3 -m unittest tests.test_reconciliation -v` — payroll/onboarding/site 스냅샷이 생기면 skip이 실제 검사로 바뀐다(monthEndActive 411 · timeline 27 · 스냅샷 totals).
