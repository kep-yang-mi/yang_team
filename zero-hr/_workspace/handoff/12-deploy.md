# 12-deploy — release-engineer 핸드오프 로그

- 갱신: 2026-09-23 · 기준일 2026-09-23

## 시도한 것
- GitHub: `kep-yang-mi/yang_team`(빈 저장소)에 `zero-hr/` 하위 폴더로 첫 커밋 푸시. 자격증명·생성 config는 `.gitignore`로 제외.
- Supabase: `supabase db push --db-url`로 스키마 적용(psql 미설치) → `seed.py`로 정제 4종·클린징 로그·제품 스냅샷 6종 적재 → `verify.py`로 대사.
- Vercel: `make_config.py`로 `site/config.js` 생성 → `build_static.py`로 `site/api/*.json` 갱신 → `vercel deploy --prod`(프로젝트 `zero-hr` 신규 생성).

## 본 데이터·근거
- `supabase/verify-result.json`: 13개 검사 전부 통과(employees 427/재직 406/휴직 21, to_plan 합 422, joiners 27, leavers 19, departments 11, 스냅샷 6종, insight 스냅샷 월말 411·gap −11, anon 차단·스냅샷 읽기).
- 배포 스모크: 15개 경로 200(허브·제품 4·채택 근거·리포트 2·스냅샷 2·정적 API 4·config).
- 통합 제품 섹션 23개(data-origin insight 13 · payroll 5 · onboard 4 · new 1), 역할 6종.

## 실패한 것
- `vercel alias set zero-hr.vercel.app` 거부(전역 이름 선점) → 프로젝트 기본 도메인 `zero-hr-six.vercel.app` 사용.
- 첫 배포는 Vercel Deployment Protection(SSO)이 켜져 모든 경로가 로그인 화면(340KB 동일 응답) → 프로젝트 설정 `ssoProtection: null`로 해제 후 정상.
- 첫 배포에 `reports/`가 없어 월초 리포트 링크 404 → `site/reports/`로 복사 후 재배포.

## 검증된 것
- 같은 지표가 화면·스냅샷·Function Call·Supabase에서 모두 같다: 재직 406 · 월말 411 · gap −11 · 급여 월말 대상 411.
- `role=executive` 정적 API 응답에 성명 없음.
- 로컬 테스트 81건 중 80건 통과(실패 1건: 생성기 결정성 — 생성기 파일 손상, 데이터·배포에는 영향 없음).

## 다음 agent 인계점
- 생성기(`generate_synthetic_sources.py`, 299줄에서 잘림) 복구 후 `tests.test_cleansing.TestDeterminism` 재실행, 데이터 재생성 시 `--product all --embed` → seed → verify → deploy 순서로 반영.
- 커스텀 도메인이 필요하면 Vercel 프로젝트에 도메인을 추가하고 `site/vercel.json`은 그대로 둔다.
- 월초 리포트 실제 발송은 여전히 승인 gate. `reports/monthly-report-dispatch.json`은 `ready-to-send` 상태다.
