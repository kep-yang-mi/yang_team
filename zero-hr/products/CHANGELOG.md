# Changelog — Everyday People Agent (제품 변경 이력)

모든 주목할 변경을 이 파일에 기록한다. 형식은 [Keep a Changelog](https://keepachangelog.com/ko/1.1.0/)를 따르고,
버전은 DATA_CONTRACT §16 규칙 — `v{major}.{minor}`: 심판 라운드마다 minor +1, 통합 제품 재구성이면 major +1.
항목마다 `근거`(인풋 파일·심판 점수 변화)와 `영향 받은 fitCriteria id`를 적는다.
항목은 `product-evolution` 스킬의 `scripts/changelog.py`가 쓴다 — 손으로 쓰지 않는다(버전 규칙이 스크립트에 있다).

## [Unreleased]

## [v2.0] - 2026-09-23
### Changed
- (rebuild) 통합 제품(app)을 Insight 골격 + Payroll Close·Onboarding 강점 흡수로 구성하고 역할 탭 6종을 열었다
  - 근거: bestFit=insight(종합 7.62) 골격 채택, 차점 Onboarding(6.90)·Payroll Close(6.85)의 충족 섹션을 역할 탭으로 흡수
  - 근거: 심판 필수 수정 해소 — ①조직 단위 TO 과부족·권고 배지를 공통 계층으로 승격(전 역할 노출) ②급여·온보딩 섹션에 data-role 게이트 적용(경영진·경영기획에서 성명 비노출) ③stale 퇴사 예정자(예정일 경과)를 일할 표에서 경고 배지로 위험 섹션과 연결 ④위험 표 어휘 이원화(담당자 즉시 확인 / 고객사 HR 확인 대기) 흡수
  - 근거: 온보딩의 주차 경계 각주(27명=horizonEnd 합계, 19명=월말 이전)와 버디 후보 카드를 원형 그대로 이식
  - 근거: 심판 점수 insight panel 5.23 / wCov 1.0; payroll panel 3.7 / wCov 1.0; onboard panel 3.8 / wCov 1.0; bestFit insight
  - 영향 받은 fitCriteria id: H-F1, H-F3, H-F4, H-F13, P-F1, P-F2, P-F6, P-F8, O-F1, O-F2, O-F3, O-F5

## [v1.0] - 2026-09-23
### Added
- (judge) 페르소나 3종 제품(Insight·Payroll Close·Onboarding)을 심판 3명이 각자 루브릭으로 채점하고 비교표를 만들었다
  - 근거: 심판 점수 — 인사 총괄 옹호자 10.0/1.3/1.7, 급여 담당 옹호자 2.7/9.0/1.0, 온보딩 담당 옹호자 3.0/0.8/8.7
  - 근거: 기계 채점 — 세 제품 모두 담당 페르소나 fit 기준 가중 충족률 1.0, PII 검사 9건 전부 통과
  - 근거: 종합 = 0.5×가중충족률×10 + 0.5×패널점수 → Insight 7.62 · Onboarding 6.90 · Payroll Close 6.85, bestFit=insight
  - 근거: 심판 점수 insight panel 5.23 / wCov 1.0; payroll panel 3.7 / wCov 1.0; onboard panel 3.8 / wCov 1.0; bestFit insight
  - 영향 받은 fitCriteria id: H-F1, H-F4, H-F5, H-F6, H-F15, P-F1, P-F6, P-F14, O-F1, O-F2, O-F3, O-F13
