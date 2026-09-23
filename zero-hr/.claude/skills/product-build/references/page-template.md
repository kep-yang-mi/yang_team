# 공통 페이지 골격 — Zero Company HR 제품 4페이지

제품 3종(`site/insight/`, `site/payroll/`, `site/onboard/`)과 허브(`site/index.html`)는 이 골격에서 시작한다.
골격을 공유하는 이유: 세 페르소나가 같은 회사의 같은 데이터를 보므로, 헤더·출처 배지·색·표 규칙이 다르면
"같은 지표가 다르게 보이는" 착시가 생긴다. 화면 구성(섹션·차트·표)만 `product-specs.md`에서 제품별로 달라진다.

목차: 1 파일 골격 · 2 CSS 토큰 · 3 공통 헤더 · 4 데이터 로딩(내장 + Supabase 덮어쓰기) · 5 Chart.js 규칙 · 6 표·타일 · 7 375px · 8 접근성 · 9 섹션 마킹(fit 추적) · 10 체크리스트

## 1. 파일 골격

- 정적 HTML 1개, 빌드 없음. CSS·JS는 인라인. 외부 로드는 **Chart.js 1개**(`cdn.jsdelivr.net/npm/`)와 `../config.js`뿐.
- 허용 CDN: `cdnjs.cloudflare.com`, `cdn.jsdelivr.net/npm/` — `tests/test_site.py`가 이 외 도메인을 결함으로 잡는다.
- 폰트는 시스템 폰트만(Google Fonts 금지 — 오프라인 열람이 요건).
- 제품 페이지의 상대 경로: `../config.js`, 허브 링크 `../index.html`. 허브에서는 `config.js`, `insight/index.html`.
  Vercel `cleanUrls`에서 `/insight` → `../config.js`는 `/config.js`로 풀리고, 로컬 `file://`에서도 같은 상대 경로가 동작한다.

```html
<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Insight — ㈜온다테크</title>
<meta name="description" content="Zero Company HR · Everyday People Agent — 인사 총괄용 실시간 HR 리포트">
<style>/* §2 토큰 + 레이아웃 */</style>
</head>
<body>
<header class="app-header">…§3…</header>
<main id="main">
  <section data-section="kpi" data-views="executive hr planning orgLead" data-fit="" data-evidence="">…</section>
</main>
<footer class="app-footer">데이터 정본: <code>site/data/insight.json</code> · 생성 스크립트: build_snapshots.py · 추정치는 "추정"으로 표기</footer>

<script id="report-data" type="application/json">
{}
</script>
<script src="../config.js"></script>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.js" crossorigin="anonymous"></script>
<script>/* §4 로딩 → render(DATA) */</script>
</body>
</html>
```

`report-data` 블록의 `{}`는 자리표시자다. `build_snapshots.py --embed`가 이 블록 안을 스냅샷 JSON으로 바꾼다(`</`→`<\/` 이스케이프 포함).
손으로 JSON을 붙여 넣지 않는다 — 다음 실행에서 덮어써지고, 손으로 넣은 값은 대사되지 않는다.

## 2. CSS 변수 토큰 (라이트/다크) — Anthropic 디자인 시스템

**토큰·타입 스케일·컴포넌트 규칙의 정본은 `references/design-system.md`다(사용자 지정 2026-09-23).** 이 절의 예전 토큰(파랑 계열 series, 그림자)은 폐기. 페이지는 design-system.md §1의 `:root` 블록을 그대로 복사해 쓰고, Google Fonts 링크 1개만 외부 스타일시트로 허용한다.
다크는 OS 설정(`prefers-color-scheme`)과 뷰어 토글(`data-theme`) 둘 다 존중한다 — `:root:not([data-theme="light"])` 가드 + `:root[data-theme="dark"]` 재정의.

핵심만 요약: 캔버스 `#f0eee6` / 카드 `#faf9f5` / 잉크 `#141413` / 헤어라인 `#cccbc8` / 단일 액센트 클레이 `#d97757`(hover `#c6613f`) / 그림자 없음 / 카드 radius 24px / 헤드라인 serif · UI sans · 코드 mono / 차트 series 대지색 4(`#d97757 #3d3d3a #b8965e #7f8b74`), 발산 `#c6613f`↔`#7f8b74`.

```css
html { background: var(--bg); }
body { margin: 0; background: var(--bg); color: var(--ink); font-family: var(--font-sans); line-height: 1.5; -webkit-text-size-adjust: 100%; }
h1, h2, h3, .kpi-value { font-family: var(--font-serif); }
section { background: var(--surface); border: 1px solid var(--line); border-radius: var(--radius); padding: 24px; margin: 16px 0; box-shadow: none; }
main { max-width: var(--max-w); margin: 0 auto; padding: 0 16px; }
.muted { color: var(--ink-muted); } .num { font-variant-numeric: tabular-nums; }
```
텍스트는 항상 잉크 토큰(`--ink`, `--ink-2`, `--ink-muted`)을 입는다 — 값·라벨·범례를 시리즈 색으로 칠하지 않는다. 시리즈 색은 옆의 마크가 정체성을 나른다.

## 3. 공통 헤더

헤더 5요소는 세 제품·허브 모두 같은 자리에 같은 순서로 둔다: **제품명 · 고객사 · 기준일 · 데이터 출처 · 허브 링크**.
페르소나 fit 기준에 "기준일·고객사·데이터 출처가 공통 헤더에 표시된다"(H-F11 / P-F10 / O-F12 후보)가 들어 있으므로 헤더가 곧 채점 대상이다.

```html
<header class="app-header">
  <div class="brand">
    <span class="brand-os">Zero Company HR · Everyday People Agent</span>
    <h1 id="product-name">Insight <span class="muted">— 인사 총괄</span></h1>
  </div>
  <dl class="meta">
    <div><dt>고객사</dt><dd id="meta-client">㈜온다테크</dd></div>
    <div><dt>기준일</dt><dd id="meta-as-of" class="num">—</dd></div>
    <div><dt>데이터 출처</dt><dd><span id="source-badge" class="badge" aria-live="polite" data-source="embedded">내장</span></dd></div>
  </dl>
  <nav aria-label="제품 이동"><a href="../index.html">← 허브</a></nav>
</header>
```

- 제품 표시명(GLOSSARY v2): `Insight`(인사 총괄) · `Payroll Close`(급여 담당) · `Onboarding`(온보딩 담당) · 허브 `Zero Company HR`.
  코드(`insight`/`payroll`/`onboard`)와 경로는 DATA_CONTRACT를 따른다 — 표시명만 바뀌어도 코드는 바뀌지 않는다.
- `#meta-as-of`는 스냅샷 안의 `asOfDate`(insight: `stats.asOfDate`, payroll: `payrollClose.asOfDate`, onboard: `onboardingPlan.asOfDate`, 허브: `asOfDate`)로 채운다. 하드코딩하지 않는다.
- 출처 배지 값: `내장`(embedded) → Supabase 성공 시 `Supabase · {as_of_date}`(live) → 실패 시 `내장 (실시간 조회 실패)`. `data-source` 속성도 같이 바꾼다(테스트·심판이 읽는다).
- Payroll 헤더에는 급여 기간(`payPeriod` · `periodStart`~`periodEnd`)을 기준일 옆에 한 칸 더 둔다(P-F10 후보).

## 4. 데이터 로딩 — 내장 JSON + Supabase 덮어쓰기

순서: ① 내장 JSON을 파싱해 **즉시 렌더** ② `window.ZEROHR_CONFIG`가 있으면 `report_snapshots`에서 제품별 최신 payload를 가져와 덮어쓰고 재렌더 ③ 실패하면 내장 유지.
내장을 먼저 그리는 이유: 오프라인·Supabase 미설정·RLS 오류 어느 경우에도 빈 화면이 없어야 한다(기대 효과 ②의 "링크 하나로 열람").

```js
(function () {
  var PRODUCT = 'insight'; // payroll | onboard | comparison(허브)
  var DATA = null;

  function readEmbedded() {
    var el = document.getElementById('report-data');
    try { return JSON.parse(el.textContent); } catch (e) { console.error('embedded JSON parse failed', e); return null; }
  }
  function setSource(kind, label) {
    var b = document.getElementById('source-badge');
    if (!b) return;
    b.dataset.source = kind; b.textContent = label;
  }
  function asOfOf(d) { // 제품별 asOfDate 위치
    return (d && ((d.stats && d.stats.asOfDate) || (d.payrollClose && d.payrollClose.asOfDate) ||
            (d.onboardingPlan && d.onboardingPlan.asOfDate) || d.asOfDate)) || '—';
  }
  function render(d) {
    DATA = d;
    document.getElementById('meta-as-of').textContent = asOfOf(d);
    // 섹션별 render 함수 호출 — product-specs.md 의 섹션 순서대로
  }
  async function overlayFromSupabase() {
    var cfg = window.ZEROHR_CONFIG;
    if (!cfg || !cfg.supabaseUrl || !cfg.supabaseAnonKey) return;
    var url = cfg.supabaseUrl.replace(/\/+$/, '') +
      '/rest/v1/report_snapshots?product=eq.' + encodeURIComponent(PRODUCT) +
      '&select=as_of_date,created_at,payload&order=created_at.desc&limit=1';
    try {
      var res = await fetch(url, { headers: { apikey: cfg.supabaseAnonKey, Authorization: 'Bearer ' + cfg.supabaseAnonKey, Accept: 'application/json' } });
      if (!res.ok) throw new Error('HTTP ' + res.status);
      var rows = await res.json();
      if (!rows.length || !rows[0].payload) throw new Error('no snapshot row');
      render(rows[0].payload);
      setSource('live', 'Supabase · ' + (rows[0].as_of_date || asOfOf(rows[0].payload)));
    } catch (e) {
      console.warn('report_snapshots fetch failed; keeping embedded data', e);
      setSource('embedded', '내장 (실시간 조회 실패)');
    }
  }

  var embedded = readEmbedded();
  if (embedded) { render(embedded); setSource('embedded', '내장'); }
  else { setSource('embedded', '내장 데이터 없음'); }
  overlayFromSupabase();
})();
```

- `site/config.js`는 `window.ZEROHR_CONFIG = { supabaseUrl: "...", supabaseAnonKey: "..." };` 한 줄이며 release-engineer가 만든다. 없으면 404 한 번 나고 내장으로 동작한다 — 그것이 정상 경로다.
- anon 키는 `report_snapshots` select 전용(RLS). 페이지는 쓰기·다른 테이블 조회를 하지 않는다.
- 렌더 함수는 **멱등**이어야 한다(두 번 호출돼도 표가 두 배로 늘지 않게 — 컨테이너 `innerHTML`을 비우고 다시 채운다; 차트는 `destroy()` 후 재생성).

## 5. Chart.js 규칙

차트는 있어도 되고 없어도 되는 보조 수단이다. 표가 정본이고 차트는 그 위의 요약이다 — Chart.js CDN이 막힌 환경(오프라인)에서도 페이지가 완전해야 한다.

- `window.Chart`가 없으면 차트 영역을 숨기고 표만 보인다. 차트마다 같은 데이터의 표(`<details>` 접힘 허용)를 반드시 둔다.
- 폼 선택: 크기 비교 = 가로 막대 · 시간 추이(퇴직 월별) = 선 · 극성(TO 과부족) = 발산 색 막대 · 한 숫자 = 차트가 아니라 타일. 파이/도넛은 6조각 이하 부분-전체에만.
- **축은 하나.** 이중 축 금지. 척도가 다른 두 지표는 차트 두 개.
- 범주 색은 정체성에 고정: 본부(조직 그룹) → `--series-1..4`를 코드 순(D0/D1/D2/D3 또는 Executive/Build/Go-To-Market/Operations)으로 배정하고 필터해도 바꾸지 않는다. 9번째 범주는 "기타"로 접는다.
- TO 과부족: 음수 `--diverge-neg`, 양수 `--diverge-pos`, 0 `--diverge-mid`. 부호는 색만이 아니라 라벨(`+3`/`−2`, U+2212)로도 드러낸다.
- 상태 색(`--good` 등)은 상태 의미에만(체크리스트 done/pending, 리스크 밴드) — 시리즈 색으로 쓰지 않는다. 항상 텍스트 라벨과 함께.
- 옵션 기본값: `animation:false`, `responsive:true`, `maintainAspectRatio:false`, 컨테이너 `.chart{position:relative;height:280px}`(모바일 220px), 격자 `--line` 실선 헤어라인, 축 글자 `--ink-muted`, 범례는 2시리즈 이상일 때만, 모든 점에 숫자 라벨 금지(극값만).
- 색은 `getComputedStyle(document.documentElement).getPropertyValue('--series-1').trim()`로 읽고, `matchMedia('(prefers-color-scheme: dark)')` change 이벤트에서 차트를 `destroy()` 후 재생성한다.
- `<canvas>`에는 `role="img"`와 `aria-label`(제목 + 한 줄 요약)을 준다.

```js
function token(name) { return getComputedStyle(document.documentElement).getPropertyValue(name).trim(); }
var CHARTS = {};
function barChart(id, labels, values, opts) {
  if (!window.Chart) return;
  if (CHARTS[id]) { CHARTS[id].destroy(); }
  var ctx = document.getElementById(id);
  var colors = opts.colors || labels.map(function () { return token('--series-1'); });
  CHARTS[id] = new Chart(ctx, {
    type: 'bar',
    data: { labels: labels, datasets: [{ label: opts.label || '', data: values, backgroundColor: colors, borderRadius: 4, maxBarThickness: 28 }] },
    options: { indexAxis: opts.horizontal ? 'y' : 'x', animation: false, responsive: true, maintainAspectRatio: false,
      plugins: { legend: { display: false }, tooltip: { enabled: true } },
      scales: { x: { grid: { color: token('--line') }, ticks: { color: token('--ink-muted') } },
                y: { grid: { color: token('--line') }, ticks: { color: token('--ink-muted') } } } }
  });
}
matchMedia('(prefers-color-scheme: dark)').addEventListener('change', function () { if (DATA) render(DATA); });
```

## 6. 표·타일

- KPI 타일: `<div class="tile"><span class="tile-label">월말 예측 인원</span><strong class="tile-value num">411</strong><span class="tile-sub muted">TO 422 대비 −11</span></div>`. 값은 `toLocaleString('ko-KR')`, 비율은 소수 1자리 `%`. 추정치(자동화 효과·시나리오)는 라벨에 "(추정)".
- 표: `<table>`에 `<caption>` 필수, 숫자 열은 `class="num"` 우측 정렬, 헤더 `scope="col"`. 20행 넘는 목록은 검색 입력(`<input type="search" aria-label="…">`)과 "더 보기"로 나눈다. 정렬은 클라이언트 측, 데이터는 건드리지 않는다.
- 표를 감싸는 `.table-wrap{overflow-x:auto}` — 페이지가 아니라 표만 가로 스크롤한다.
- 빈 상태: 데이터가 `null`이면 섹션을 숨기지 말고 "데이터 없음 — {상류 산출물 경로} 미생성"을 표시한다(누락이 보여야 고칠 수 있다).
- 미해결 플래그(`unresolvedFlags`)는 행 옆 배지로. 어휘는 클린저 것 그대로(`org-parent-only` 등) — 번역하지 않는다(감사자가 grep한다).

## 7. 375px 대응

- 헤더는 `flex-wrap: wrap`, `dl.meta`는 세로 스택. 타일 그리드 `grid-template-columns: repeat(auto-fit, minmax(150px, 1fr))`.
- 좌우 여백 16px(`--gutter`), 이미지·캔버스 `max-width:100%`. 가로 스크롤은 `.table-wrap` 안에서만 — `html, body { overflow-x: hidden }`은 쓰지 않는다(문제를 숨긴다).
- 역할 선택기·주차 탭은 가로 스크롤 가능한 pill 목록(`overflow-x:auto; white-space:nowrap`).
- 확인 방법: 브라우저 폭 375px에서 `document.documentElement.scrollWidth <= 375`.

## 8. 접근성

- 텍스트 대비 4.5:1 이상(잉크 토큰은 두 모드 모두 충족). 시리즈 색 위에 글자를 올리지 않는다.
- 역할 선택기는 `<fieldset><legend>보기 권한</legend>` + 라디오. 현재 뷰는 `aria-current`. 섹션 표시/숨김은 `hidden` 속성.
- 배지·상태는 색 + 텍스트(✓/·/!) 조합. 리스크 밴드는 "높음/중간/낮음" 글자가 항상 붙는다.
- `<html lang="ko">`, 스킵 링크 `<a href="#main">본문으로</a>`, 포커스 링 유지(§2 `:focus-visible`).
- 라이브 갱신 배지 `aria-live="polite"`. 차트 캔버스 `role="img"` + `aria-label`.

## 9. 섹션 마킹 — fit 추적

모든 `<section>`에 세 속성을 단다. product-judge와 `tests/test_site.py`가 이것으로 "어느 기준을 어느 데이터로 충족했는가"를 기계적으로 읽는다.

```html
<section data-section="division-gap" data-views="executive planning"
         data-fit="H-F1" data-evidence="forecast.byDivision[].toGapMonthEnd forecast.byDivision[].forecastMonthEnd">
```

- `data-section`: product-specs.md의 섹션 id. `data-views`: 이 섹션이 보이는 뷰(Insight만; 다른 제품은 생략).
- `data-fit`: `personas/persona-needs.json`의 `fitCriteria[].id`(공백 구분). 니즈 파일이 없으면 비워 두고 반환값 `gaps`에 적는다.
- `data-evidence`: 실제로 렌더한 스냅샷 키 경로(공백 구분). 기준의 `evidence`와 접두가 일치해야 충족으로 친다.

## 10. 페이지 완성 체크리스트

- [ ] `report-data` 블록이 있고 `--embed` 후 JSON이 파싱된다 (`JSON.parse` 오류 없음)
- [ ] 외부 `<script src>`가 Chart.js(jsdelivr)뿐이고 `<link href>`가 없다
- [ ] 헤더 5요소가 채워지고 기준일이 스냅샷에서 왔다
- [ ] `config.js` 없이 열어도 내장으로 렌더, 있으면 배지가 Supabase로 바뀐다
- [ ] 다크 모드에서 배경·표·차트가 모두 토큰을 따른다
- [ ] 375px에서 페이지 가로 스크롤 없음
- [ ] 차트마다 표가 있고, 축은 하나, 범주 색은 정체성 고정
- [ ] 뷰/제품별 PII 규칙(product-specs.md)대로 성명·생년월일이 나타나지 않는다
- [ ] 모든 섹션에 `data-section`·`data-fit`·`data-evidence`가 있다
