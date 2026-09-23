---
name: reconciliation-policy
description: "대사(reconciliation) 정책 — 같은 지표는 제품·뷰·리포트·스냅샷·데이터 저장소 어디서나 같은 값이어야 하고, 모든 집계는 정제 마스터에서 독립 재계산으로 검증되며, 페이지는 재계산하지 않고, 예측·리스크·자동화 효과는 가정을 명시하고, 불일치(예: 브리프 215/119/62 vs 조직표 220/128/48)는 삭제하지 않고 기록한다. 통계·예측·리스크·급여 마감·온보딩·제품·통합 제품·리포트·Supabase 적재·감사 등 숫자를 만들거나 옮기거나 검사하는 모든 에이전트가 참조한다. 트리거: 대사, 정합성, 숫자 불일치, 같은 지표 다른 값, 독립 재계산, 정본 수치, 가정 명시, 브리프 불일치, 재계산 금지."
---

# reconciliation-policy — 같은 지표는 같은 값, 정본은 정제 마스터

## 규칙
1. **정본은 정제 마스터다.** 통계·예측·리스크·파생은 `data/clean/`에서만 계산한다. 원천(`data/raw/`)은 결함이 있어 정본이 될 수 없다.
2. **독립 재계산으로 대사한다.** 산출물을 쓰는 쪽이 자기 안에서 합을 검사하고(Σ조직 = totals 등), 감사자는 정제 마스터에서 **같은 정의로 다시 세어** 대조한다. 정본을 복사해 놓고 "일치"라 하지 않는다.
3. **같은 지표는 같은 값.** 재직 406·휴직 21·TO 422·입사 19·퇴사 14·월말 411·gap −11은 stats/forecast/payroll/onboarding/스냅샷 3종/app/리포트/CSV/Supabase 어디서나 같다. 스냅샷·리포트·Supabase는 상류 파일을 **복사**한다(바이트 동일).
4. **페이지·탭·뷰는 재계산하지 않는다.** 필터와 표시만. 표시용 합산(조직장 뷰 슬라이스, 시나리오 플래너)은 "표시용, 대사 대상 아님"/"시나리오(가정)" 각주를 단다.
5. **가정은 명시한다.** 예측 `assumptions[]`, 리스크 `model.factors[].rationale`·`expectedProbability`, 자동화 효과 `basis`·`note`, 급여 `proratedRatio` 산식, 온보딩 체크리스트 가상 생성 seed. 추정치는 화면·리포트에 "(추정)"이 붙는다.
6. **클린징은 원천을 덮어쓰지 않는다.** 보정은 로그로(원천 + 로그 = 정제). 미해결은 삭제가 아니라 플래그.
7. **불일치는 기록하고 삭제하지 않는다.** 브리프 §7의 조직 그룹 합 215/119/62는 조직표 합 220/128/48과 다르다 — 조직표를 정본으로 채택하고 그 사실을 `headcount-stats.dataQuality.briefDiscrepancies`와 리포트 데이터 품질 절에 남긴다. 대사 실패 산출물은 `_workspace/*.unreconciled.json`으로 남긴다.

## 왜
세 제품과 리포트가 같은 회사를 말하는데 숫자가 다르면 사용자는 **어느 것도** 믿지 않는다 — 한 곳의 오차가 전체의 신뢰를 지운다. 페이지 JS가 합계를 내기 시작하면
제품마다 다른 반올림·필터가 끼어 "뷰마다 다른 숫자"가 생기고, 그 원인은 파일이 아니라 코드 곳곳에 흩어져 찾을 수 없다. 독립 재계산이 필요한 이유는
복사본끼리의 일치는 아무것도 증명하지 못하기 때문이다 — 같은 버그를 복사했을 뿐이다. 불일치를 지우지 않는 이유는 그것이 데이터 품질의 **증거**이기 때문이다:
브리프 수치와 조직표가 다르다는 기록이 남아 있어야 고객사가 어느 표를 고칠지 결정할 수 있다. 가정을 적는 이유는 예측이 틀렸을 때 "입력이 틀렸나, 가정이 틀렸나"를 가를 수 있어야 하기 때문이다.

## 정본 수치 (데모 · DATA_CONTRACT §2-7)
Executive Snapshot: 재직 406 · 휴직 21 · 총원 427 · TO 422 · gapAsOf −16 · 입사 예정 19 · 퇴사 예정 14 · 월말 411 · gapME −11 · toFillRate 0.9739.
조직 11행(HC/OL/TO/in/out/ME/gapAsOf/gapME/recommendation)과 속성 분포 8종은 계약 §2-7 표가 정본이다 — 에이전트 정의의 숫자를 정본으로 쓰지 않는다.
권고 규칙: gapME ≤ −4 → 채용 가속 / ≥ +5 → TO 재검토·이동배치 / 그 외 정상 관리.

## 어떻게 지키나
| 역할 | 해야 할 것 |
|---|---|
| 통계·예측·리스크·파생 생산자 | 스크립트 내부 assert(Σ = totals, 도메인), `--self-check`로 정본 대조, 불일치는 `status: partial` + `mismatches[left/right/source]`로 반환. 값을 맞추지 않는다 |
| 급여·온보딩 | `monthEndActive`·타임라인 합을 정제 데이터에서 **다시 계산**한 뒤 예측과 대조. 불일치면 계약 경로에 쓰지 않고 `_workspace/*.unreconciled.json` |
| 제품·통합 빌더 | 스냅샷은 `data/stats/*.json` 복사. 조립 스크립트의 `reconciliation.checks`를 반환. 페이지에서 값을 맞추지 않는다 |
| 리포트 | 같은 stats 파일에서 렌더. 요약 수치 ↔ forecast 대조 후 `ready-to-send` |
| 배포 | `verify.py`가 Supabase 행 수·합계를 정제 데이터와 대조 → `verify-result.json`. 불일치면 Vercel 단계 중단 |
| 감사자 | 경계면 표(양쪽 동시 읽기)로 값 비교. 정본과 같은 쪽이 맞다. 고치지 않고 `owner`·`fix`를 지목 |

## 어떻게 검증하나
```bash
python3 -m unittest discover -s tests -v                     # test_reconciliation: §2-7 11행 × 9열 + Snapshot + 속성 8종이 stats/forecast/payroll/onboarding/site 스냅샷에서 일치
python3 -c "import csv,collections as c;r=list(csv.DictReader(open('data/clean/headcount-master.clean.csv',encoding='utf-8')));print(c.Counter(x['status'] for x in r))"   # 독립 재계산: 재직 406 / 휴직 21
python3 -c "import json;s=json.load(open('data/stats/headcount-stats.json'));f=json.load(open('data/stats/month-end-forecast.json'));print(s['totals']['activeHeadcount'],f['totals']['activeHeadcount'],f['totals']['forecastMonthEnd'])"   # 406 406 411
python3 -c "import json;a=json.dumps(json.load(open('data/stats/month-end-forecast.json')),sort_keys=True);b=json.dumps(json.load(open('site/data/insight.json'))['forecast'],sort_keys=True);print(a==b)"   # 스냅샷 바이트 동일: True
grep -c "215/119/62" data/stats/headcount-stats.json reports/monthly-report-2026-10.md   # 불일치 기록 보존: 각 ≥ 1
```
불일치 기록 형식: `{"boundary","metric","left":{"path","value"},"right":{"path","value"},"canonical","owner","fix"}` — "숫자가 다르다"는 기록이 아니다.
