---
name: monthly-report
description: "공통 데이터 계층(headcount-stats · month-end-forecast, 선택으로 attrition-risk · payroll-close · cleansing-summary · automation-effect)의 수치를 재계산 없이 그대로 읽어 DATA_CONTRACT v2 §6 월초 리포트 4종을 만든다 — reports/monthly-report-2026-10.md/.html(제목 '[Zero Company] 2026-09 HR Headcount Forecast'), reports/org-forecast-2026-09.csv, reports/monthly-report-dispatch.json(수신자 4그룹 executive/hr/planning/orgLead @ondatech.example, 매월 1일 09:00, status ready-to-send, gate 'approval-gate: 외부 발송'). §8 automation-effect.json 생성도 포함. 통계·예측이 끝난 직후, '월초 리포트', '월간 리포트', '리포트 이메일', '이메일 초안', '발송 준비', 'dispatch', 'org-forecast CSV', '자동화 효과', 'automation-effect' 요청 시 반드시 이 스킬을 사용할 것. 리포트를 '다시', '재실행', '수정', '보완', '업데이트', '재발송 준비', '수신자 바꿔서' 만들라는 후속 요청도 이 스킬로 처리한다. 실제 발송·cron 등록은 승인 gate(사람) — 이 스킬은 '발송 준비 완료'까지만 한다."
---

# monthly-report — 월초 리포트 렌더·발송 준비 (DATA_CONTRACT v2 §6·§8)

## 왜 이 스킬인가

기대 효과 ④(월간 리포트 자동 생성·배포)의 증빙이다. 경영진·HR·경영기획·조직장이 같은 숫자를 보는 것이 핵심이므로 **리포트는 재계산하지 않는다** — `headcount-stats.json`과 `month-end-forecast.json`에서 읽어 배치만 한다. 숫자를 한 번 더 계산하면 뷰마다 값이 갈리고 `reconciliation-policy`가 깨진다. 외부 발송은 Operating Rule 4의 승인 gate이므로 산출물은 "발송 준비 완료(ready-to-send)"까지다.

## 입력

| 구분 | 경로 | 비고 |
|---|---|---|
| 필수 | `data/stats/headcount-stats.json` | §4-1 — 재직/휴직/TO, 속성 분포, 퇴사 예정 사유, 데이터 품질 |
| 필수 | `data/stats/month-end-forecast.json` | §4-2 — 조직별 예측·권고·인사이트·즉시 액션 |
| 선택 | `data/stats/attrition-risk.json` | 리스크 반영 시나리오 절 |
| 선택 | `data/stats/payroll-close.json` | `monthEndActive` 대사만(성명은 읽지 않음) |
| 선택 | `data/clean/cleansing-summary.json` | 데이터 품질 절(클린징 17/31건·미해결) |
| 선택 | `data/stats/automation-effect.json` | 자동화 효과 절(`automation_effect.py`가 생성) |
| 선택 | `_workspace/run_meta.json` | `durations` → `automation-effect.pipelineSeconds` |
| PII 스캔용 | `data/clean/headcount-master.clean.csv` · `planned-joiners.clean.csv` | 성명 목록으로 결과를 스캔만 한다(본문에 쓰지 않음) |

## 출력

| 경로 | 내용 |
|---|---|
| `data/stats/automation-effect.json` | §8 — 수작업 40h/월 vs 파이프라인 초 + 검토 8h, savingRate 0.8, 추정 명시 |
| `reports/monthly-report-2026-10.md` / `.html` | 제목 → 요약(재직 406/월말 411 · gap −11 · 채용 가속 Engineering, Sales · TO 재검토 Data & AI · 즉시 액션 3건 · 첨부) → Executive Snapshot 표 → 조직별 예측 표(§2-7 열) + 조직 그룹 표 + 인사이트 → 인원 통계 요약(속성 8종) → 퇴사 예정 사유 → 데이터 품질 → 자동화 효과 → 부록(정의). HTML은 인라인 스타일, 외부 리소스 없음 |
| `reports/org-forecast-2026-09.csv` | `deptCode,department,orgGroup,toHeadcount,activeHeadcount,plannedIn,plannedOut,forecastMonthEnd,toGapMonthEnd,recommendation` 11행 |
| `reports/monthly-report-dispatch.json` | `sendAt 2026-10-01T09:00:00+09:00` · `schedule "0 9 1 * *"` · `recipients{executive,hr,planning,orgLead}`(모두 `@ondatech.example`) · `subject` · `attachments[site/insight/index.html, reports/org-forecast-2026-09.csv]` · `status ready-to-send` · `gate "approval-gate: 외부 발송"` |

파일명 규칙: 리포트 md/html은 **발송월**(기준일 다음 달 = 2026-10), CSV와 제목은 **기준월**(2026-09).

## 실행

```bash
cd /Users/yang/development/zero-hr
python3 .claude/skills/monthly-report/scripts/automation_effect.py --root . --as-of 2026-09-23   # §8 (먼저)
python3 .claude/skills/monthly-report/scripts/render_report.py     --root . --as-of 2026-09-23   # §6
```
두 스크립트 모두 stdout 마지막 줄이 요약 JSON 1행(반환 데이터)이다. `render_report.py` 종료 코드: `0` ok · `1` 오류 · `2` 대사 실패(`_workspace/monthly-report.unreconciled.json`에 진단, reports/ 미작성) · `3` 필수 입력 없음 · `4` PII 검출(미작성).
선행: `headcount-stats` → `month-end-forecast`(→ 선택으로 attrition-risk · payroll-close) 다음에 실행한다.

## 정책

- **PII (`pii-minimization-policy`)**: 본문·CSV·dispatch 어디에도 성명·생년월일을 넣지 않는다. 리포트는 경영진·조직장에게 가므로 HR 뷰 밖이다. 렌더 결과를 정제 성명 목록(3자 이상)으로 스캔해 하나라도 섞이면 파일을 쓰지 않고 exit 4. `plannedLeavers`의 사번도 본문에 나열하지 않는다(집계만).
- **대사 (`reconciliation-policy`)**: 쓰기 전에 `stats.totals`(activeHeadcount·toHeadcount·toGapAsOf·plannedIn·plannedOut) = `forecast.totals`, 조직별 재직·TO 일치, payroll이 있으면 `monthEndActive = forecastMonthEnd`(411)를 검사한다. 불일치면 리포트를 만들지 않는다 — 어느 상류가 틀렸는지 진단 파일로 돌려보낸다.
- **승인 gate (`approval-gate-policy`)**: 발송·cron 등록·외부 API 호출을 하지 않는다. dispatch.json은 사람이 승인하면 그대로 실행할 수 있는 명세다. 수신자 도메인은 `ondatech.example`만.
- 숫자 서술은 스크립트가 규칙 문장으로 만든다. 에이전트는 문장을 손으로 고치지 않고, 바꿔야 하면 스크립트 규칙을 고친다(재실행 시 덮어써지므로).

## 재실행·수정

- 상류(통계·예측·리스크·급여)가 바뀌면 그냥 다시 실행한다. 결정적이라 같은 입력이면 같은 리포트가 나온다.
- 수신자 변경 요청은 `render_report.py`의 `RECIPIENTS`(그룹 4종 고정, 도메인 고정)를 고치고 재실행한다. 그룹을 늘리거나 실제 도메인을 쓰는 요청은 계약 §6·승인 gate 사안이므로 실행하지 않고 보고한다.
- 제목 형식·파일명·CSV 열은 §6 고정. 바꾸려면 계약이 먼저다.

## 핸드오프

- 실행 후 `_workspace/handoff/10-report.md`(시도/근거/실패/검증/인계점 5절)를 남긴다.
- 하류: `release-engineer`(사이트·Supabase 배포, dispatch.json을 승인 요청에 첨부) · `people-data-auditor`(`tests/test_reconciliation.py`의 `org-forecast` CSV 대사).
- 반환 데이터 예: `{"status":"ok","subject":"[Zero Company] 2026-09 HR Headcount Forecast","artifacts":[...4개],"summary":{"activeHeadcount":406,"forecastMonthEnd":411,"toGapMonthEnd":-11,"immediateActions":[...3]},"recipientsCount":17,"dispatch":{"status":"ready-to-send","gate":"approval-gate: 외부 발송"}}`
