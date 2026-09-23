# 디자인 시스템 — Anthropic (사용자 지정, 2026-09-23)

출처: https://styles.refero.design/style/d469cba4-c448-4a43-a033-883f8bfcdc42 (Anthropic 스타일 추출). 모든 제품 페이지(허브·Insight·Payroll Close·Onboarding·통합 app)와 월초 리포트 HTML은 이 토큰만 쓴다.
비유: "따뜻한 양피지 위의 과학 현장 노트" — 조용한 아이보리 면, 편집형 세리프 헤드라인, 단 하나의 클레이 액센트. **그림자·그라데이션·글로우 없음.** 높이는 면 톤 차이와 1px 헤어라인으로만.

## 1. 토큰 (라이트 = 원본, 다크 = 파생)

```css
:root {
  /* 면 */
  --bg: #f0eee6;          /* Ivory Medium — 페이지 캔버스 */
  --surface: #faf9f5;     /* Ivory Light — 카드·패널 */
  --surface-2: #e3dacc;   /* Oat Warm — 묶음 패널·강조 배경 */
  --surface-hero: #f5e3c7;/* Manilla — 히어로/Executive Snapshot 카드 */
  /* 잉크 */
  --ink: #141413;         /* Slate Dark — 본문·헤드라인 */
  --ink-2: #3d3d3a;       /* Slate Medium */
  --ink-muted: #87867f;   /* Cloud Dark — 보조 라벨 */
  --ink-faint: #b0aea5;   /* Cloud Medium — 비활성 */
  --line: #cccbc8;        /* Stone — 헤어라인 */
  --line-strong: #87867f;
  /* 액센트 (하나만) */
  --accent: #d97757;      /* Clay — 주요 CTA·선택된 탭 표시·핵심 지표 강조 */
  --accent-deep: #c6613f; /* Clay Deep — hover/pressed */
  --on-accent: #ffffff;
  /* 상태 (텍스트 병기 필수) */
  --good: #6f8f6a; --warning: #b8965e; --critical: #c6613f; --neutral: #87867f;
  /* 차트 — 따뜻한 대지색 4 + 보조 4 */
  --series-1: #d97757; --series-2: #3d3d3a; --series-3: #b8965e; --series-4: #7f8b74;
  --series-5: #8c5a6b; --series-6: #a17c4a; --series-7: #5f6f7a; --series-8: #b0aea5;
  --diverge-neg: #c6613f; --diverge-pos: #7f8b74; --diverge-mid: #cccbc8;
  /* 타이포 */
  --font-serif: "Source Serif 4", "Noto Serif KR", Georgia, "Times New Roman", serif;
  --font-sans: "Inter", "Noto Sans KR", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  --font-mono: "IBM Plex Mono", ui-monospace, SFMono-Regular, Menlo, monospace;
  --font: var(--font-sans);
  /* 형태 */
  --radius: 24px;         /* 카드 */
  --radius-btn: 12px;     /* 아웃라인 버튼 */
  --radius-cta: 8px;      /* 채움 버튼 */
  --radius-badge: 0px;    /* 배지·내비·링크는 각 */
  --shadow: none;
  --max-w: 1280px;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --bg: #141413; --surface: #1f1f1e; --surface-2: #2a2a28; --surface-hero: #2f2a22;
    --ink: #faf9f5; --ink-2: #e3dacc; --ink-muted: #b0aea5; --ink-faint: #87867f;
    --line: #3d3d3a; --line-strong: #87867f;
    --series-2: #cccbc8; --diverge-mid: #3d3d3a;
  }
}
:root[data-theme="dark"] {
  --bg: #141413; --surface: #1f1f1e; --surface-2: #2a2a28; --surface-hero: #2f2a22;
  --ink: #faf9f5; --ink-2: #e3dacc; --ink-muted: #b0aea5; --ink-faint: #87867f;
  --line: #3d3d3a; --line-strong: #87867f;
  --series-2: #cccbc8; --diverge-mid: #3d3d3a;
}
```

폰트 로드(허용된 외부 스타일시트는 Google Fonts만):
`<link rel="preconnect" href="https://fonts.googleapis.com">` + `<link href="https://fonts.googleapis.com/css2?family=Source+Serif+4:opsz,wght@8..60,400;8..60,600&family=Inter:wght@400;500;600;700&family=Noto+Serif+KR:wght@400;600&family=Noto+Sans+KR:wght@400;500;700&family=IBM+Plex+Mono&display=swap" rel="stylesheet">`
(Anthropic Serif/Sans/Mono는 비공개 서체 → 위가 공개 대체. 로드 실패 시 시스템 폰트로 자연 폴백.)

## 2. 타입 스케일

| 역할 | 서체 | 크기 / 행간 / 자간 | 용도 |
|---|---|---|---|
| Display | serif 400 | 48px(모바일 34) / 1.1 / 0 | 허브 히어로 한 줄 |
| Heading | serif 600 | 32px(모바일 26) / 1.1 / −0.12px | 페이지 제목 `h1` |
| Subheading | serif 600 | 24px / 1.3 / −0.05px | 섹션 제목 `h2` |
| Body | sans 400 | 16px / 1.5 / −0.08px | 본문·표 |
| Caption | sans 500 | 12px / 1.4 / −0.24px | 라벨·각주·배지(대문자 아님, 자간만) |
| KPI 숫자 | serif 600, tabular-nums | 40px / 1.0 | 타일 값 |
| Mono | mono 400 | 14px | 코드·경로·runId |

## 3. 컴포넌트

- **카드/섹션**: `background: var(--surface); border: 1px solid var(--line); border-radius: var(--radius); padding: 24px~32px;` 그림자 없음. 묶음 패널은 `--surface-2`.
- **Executive Snapshot / 핵심 KPI 묶음**: `--surface-hero`(Manilla) 1장만. 나머지 타일은 `--surface`.
- **버튼**: 채움 CTA `--accent` + 흰 글자, radius 8px, padding 12px 24px — 페이지당 1~2개(승인 요청·리포트 열기). 아웃라인 `1px solid var(--line-strong)`, radius 12px, 투명 배경. 뷰/역할 선택기는 **아웃라인 세그먼트**, 선택 항목만 `--accent` 2px 하단선 + `--ink` 글자(채움 금지).
- **링크**: 항상 밑줄(`--ink`), hover 시 `--accent-deep`.
- **배지**: 각(0px), `1px solid`, 12px caption. 상태 색은 배지 테두리·점(●)에만, 글자는 `--ink`. 권고 배지: 채용 가속 `--critical` 테두리 / TO 재검토 `--warning` / 정상 관리 `--neutral`.
- **표**: 헤어라인 행 구분(`--line`), 헤더 caption `--ink-muted`, 숫자 우측 정렬 tabular-nums, 짝수 행 배경 없음(면 톤은 카드가 담당).
- **차트**: 조직 그룹 4 → `--series-1..4` 코드 순 고정. TO 과부족 → `--diverge-neg/pos`. 격자 `--line`, 축 글자 `--ink-muted`, 범례 텍스트 `--ink`. 배경 투명.
- **헤더**: 좌 브랜드(serif "Everyday People Agent" + sans 제품명), 우 고객사·기준일·출처 배지·허브 링크·다크 토글. 하단 1px `--line`.
- **푸터 `data-section="claims"`**: `--surface-2` 패널, 3열(구현됨 / 목업·준비 완료 / 승인 대기) 표.

## 4. 금지

그림자, 그라데이션, 파란·차가운 회색 계열, 둥근 배지, 대문자 강제(`text-transform: uppercase`), 두 번째 액센트 색, 시리즈 색으로 칠한 본문 텍스트, 아이콘 폰트(외부 스크립트). 이모지는 상태 표기에 쓰지 않는다(글자 배지로).
