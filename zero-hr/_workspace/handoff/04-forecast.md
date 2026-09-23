# 04-forecast — headcount-forecaster — 2026-09-23

## 시도한 것
- 실행 종료 2026-09-23T17:10:52: `python3 .claude/skills/month-end-forecast/scripts/forecast.py --root /Users/yang/development/zero-hr --as-of 2026-09-23 --self-check` → status `ok`
- 재직 기준(휴직 제외)으로 조직 11 × (TO/HC/in/out/ME/gapAsOf/gapME/권고) 계산, 조직 그룹·전체 합산, 다음 달 전망, 리스크 반영 시나리오(적용), 인사이트 3건·즉시 액션 3건, 시나리오 기본값 산출
- 산출물 `data/stats/month-end-forecast.json` 작성(§4-2 shape)

## 본 데이터·근거
- 계약: DATA_CONTRACT v2 §4-2(shape·권고 규칙·인사이트) · §4-5(plannedOut 판정: unknown-emp 제외·재직 사번만·stale 포함) · §2-7(정본 대조) · §2-8(stale/unknown-emp 보정 규칙)
- `data/reference/org-chart.csv`: 11조직
- `data/clean/headcount-master.clean.csv`: 427행(재직 406 · 휴직 21)
- `data/clean/to-plan.clean.csv`: 11행(합 422)
- `data/clean/planned-joiners.clean.csv`: 27행(월말까지 19 · 다음 달 8 · 범위 밖 0 · 파싱 실패 0)
- `data/clean/planned-leavers.clean.csv`: 19행(월말까지 14 · 다음 달 4 · unknown-emp 1 · 비재직 0 · stale 1 · 범위 밖 0)
- `data/stats/attrition-risk.json`: byDepartment 11조직, 3개월 기대 이탈 합 36.88

## 실패한 것
- 마스터에 없는 사번(unknown-emp) 제외: E9999

## 검증된 것
- 내부 대사 통과: Σ byDepartment = Σ byOrgGroup = totals(5개 필드), 조직별 산식, 권고 규칙 재적용, 목록 건수
- §2-7 정본 대조(--self-check): 통과(조직 11행 · 그룹 4 · 전체 · 다음 달 · 인사이트 3종)
- 전체: 재직 406 + 입사 예정 19 − 퇴사 예정 14 = 월말 411, TO 422 대비 −11(기준일 −16), toFillRate 0.9739, 다음 달 말 415(−7)
- 권고: Engineering −7(채용 가속), Data & AI +7(TO 재검토/이동배치), Sales −4(채용 가속)
- stale 퇴사 예정(월말 퇴사로 반영): E0251

## 다음 agent 인계점
- payroll-close-analyst: `payrollHeadcount.monthEndActive` = `totals.forecastMonthEnd`(411) assert. 휴직자 퇴사 예정(없음)은 여기서 제외됐으니 급여 `monthEndTotal`에서 별도 반영
- onboarding-plan-analyst: `plannedJoiners` 27건 = plannedIn 19 + nextMonth.plannedIn 8(타임라인 합계 대사)
- product-builder: Insight 경영진/경영기획/조직장 뷰는 `byDepartment`·`byOrgGroup`·`totals`·`insights`·`scenario`(플래너 기본값)를 그대로 읽는다. 개인 식별 없음(사번·joinerId만)
- monthly-report-mailer: 본문 요약 = totals(406/411/−11) + insights(채용 가속·TO 재검토) + immediateActions 3건
- people-data-auditor: stdout `targetCheck`가 §2-7 사전 검사. 불일치는 클린저(activeHeadcount)·입퇴사 예정 파일(plannedIn/Out)·TO 정규화(toHeadcount)로 돌려보낸다
- approval-gate: 권고(채용 가속·TO 재검토/이동배치·퇴사 영향 점검)와 즉시 액션은 제안이며 채용/TO 결정은 사람이 승인한다
