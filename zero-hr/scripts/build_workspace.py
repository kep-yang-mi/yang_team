"""Build the single-page Zero HR workspace after generating product pages.

Run from any directory: python3 zero-hr/scripts/build_workspace.py
The existing app is the dashboard source; API JSON and email reports stay intact.
"""
import html
import json
import re
from pathlib import Path

SITE = Path(__file__).resolve().parents[1] / 'site'
ITEMS = [
    ('dashboard', '/#dashboard', '◫', '통합 대시보드'),
    ('insight', '/#insight', '↗', '인원 분석'),
    ('payroll', '/#payroll', '▤', '급여 마감'),
    ('onboard', '/#onboarding', '⊕', '온보딩'),
    ('report', '/#report', '▧', '월초 리포트'),
    ('decision', '/#decision', '◇', '채택 근거'),
    ('integrations', '/#integrations', '⌘', '시스템 연동'),
    ('before', 'https://claude.ai/code/artifact/7e13938a-4161-4a07-b4be-d010dc6f33cb', '↗', 'Before 사이트'),
]


def strip_frame(source):
    source = re.sub(r'\n?<!-- workspace:start -->.*?<!-- workspace:end -->', '', source, flags=re.S)
    source = source.replace('<link rel="stylesheet" href="/assets/workspace.css">\n', '')
    source = re.sub(r' data-workspace-page="[^"]+"', '', source)
    return source


def frame(source, key, title):
    source = strip_frame(source)
    nav = ''
    for item, url, icon, label in ITEMS:
        if item == 'decision':
            nav += '<div class="workspace-group">WORKSPACE</div>'
        current = ' aria-current="page"' if item == key else ''
        external = ' target="_blank" rel="noopener noreferrer"' if item == 'before' else ''
        nav += f'<a href="{url}"{current}{external}><span class="workspace-icon" aria-hidden="true">{icon}</span>{label}</a>'
    shell = f'''<!-- workspace:start -->
<aside class="workspace-sidebar" aria-label="Zero HR 워크스페이스">
  <a class="workspace-brand" href="/"><span class="workspace-mark" aria-hidden="true">z</span><span>Zero HR<small>Everyday People Agent</small></span></a>
  <div class="workspace-company">㈜온다테크<small>People Operations Workspace</small></div>
  <div class="workspace-group">PEOPLE OPERATIONS</div>
  <nav class="workspace-nav" aria-label="전체 메뉴">{nav}</nav>
  <div class="workspace-footer">하나의 데이터, 연결된 HR 업무<br>가상 데이터 기반 데모</div>
</aside>
<div class="workspace-topbar"><strong>워크스페이스 &nbsp; / &nbsp; {title}</strong><span>Zero Company HR</span></div>
<!-- workspace:end -->'''
    source = source.replace('</head>', '<link rel="stylesheet" href="/assets/workspace.css">\n</head>')
    source = re.sub(r'<body([^>]*)>', lambda m: f'<body{m[1]} data-workspace-page="{key}">\n{shell}', source, count=1)
    source = source.replace('← 허브', '대시보드').replace('>허브</a>', '>대시보드</a>')
    return source


def build_home(app, report, cards):
    """Keep the six-role product and add the other material to the same DOM."""
    app = app.replace('../', '/')
    app = app.replace('Everyday People Agent — 통합</title>', 'Zero HR — 통합 워크스페이스</title>')
    for section, target in [('kpi', 'dashboard'), ('department-gap', 'insight'),
                            ('payroll-close', 'payroll'), ('timeline', 'onboarding')]:
        app = app.replace(f'<section data-section="{section}"',
                          f'<section id="{target}" data-section="{section}"', 1)
    report_body = re.search(r'<main id="main" class="workspace-report">(.*?)</main>', report, re.S)[1]
    comparison = json.loads((SITE / 'data/decision.json').read_text())['comparison']
    rows = []
    for product in comparison['products']:
        score = product['fitScore']
        rows.append('<tr><td>{}</td><td>{}</td><td>{:.1f}%</td><td>{:.1f}</td></tr>'.format(
            html.escape(product['name']), html.escape(product['persona']),
            score['weightedCoverage'] * 100, score['panelScore']))
    judges = []
    for judge in comparison['judges']:
        scores = ''.join('<td>{:g}</td>'.format(judge['scores'][key])
                         for key in ('insight', 'payroll', 'onboard'))
        judges.append('<tr><td>{}</td>{}</tr>'.format(html.escape(judge['judge']), scores))
    extras = f'''<section id="report" class="workspace-extra">
      <h2>월초 리포트</h2><p class="muted">2026년 10월 발송용 인원 현황과 월말 예측</p>
      <div class="workspace-report-content">{report_body}</div>
    </section>
    <section id="decision" class="workspace-extra">
      <h2>채택 근거</h2><p>{html.escape(comparison['comparison']['summary'])}</p>
      <div class="wrap"><table><thead><tr><th>제품</th><th>페르소나</th><th>가중 충족률</th><th>패널 점수</th></tr></thead><tbody>{''.join(rows)}</tbody></table></div>
      <h3>심판별 점수</h3><div class="wrap"><table><thead><tr><th>심판</th><th>Insight</th><th>Payroll</th><th>Onboarding</th></tr></thead><tbody>{''.join(judges)}</tbody></table></div>
      <p>채택: Insight의 정보 구조에 급여 마감과 온보딩 기능을 통합했습니다.</p>
      <details><summary>루브릭과 변경 이력 상세</summary><p><a href="/decision/">채점 과정 전체 보기</a></p></details>
    </section>
    <section id="integrations" class="workspace-extra">
      <h2>시스템 연동</h2><p>기존 시스템에서 사용할 수 있는 Function Call 18종입니다. <a href="/api/index.json">카탈로그 JSON</a></p>
      <div class="integration-tools">{''.join(cards)}</div>
    </section>'''
    app = app.replace('</main>', extras + '\n</main>', 1)
    return app.replace('</body>', '<script src="/assets/workspace.js"></script>\n</body>', 1)


def build():
    # Preserve the original presentation hub as background material, outside the main workflow.
    about = SITE / 'about' / 'index.html'
    if not about.exists():
        about.parent.mkdir(exist_ok=True)
        hub = (SITE / 'index.html').read_text()
        hub = re.sub(r'(href|src)="(?!https?:|/|#)([^"]+)"', r'\1="/\2"', hub)
        about.write_text(hub)
    for key, directory, title in [('dashboard', 'app', '통합 대시보드'), ('insight', 'insight', '인원 분석'),
                                  ('payroll', 'payroll', '급여 마감'), ('onboard', 'onboard', '온보딩'),
                                  ('decision', 'decision', '채택 근거')]:
        path = SITE / directory / 'index.html'
        path.write_text(frame(path.read_text(), key, title))
    about.write_text(frame(about.read_text(), 'about', '서비스 소개'))

    report = SITE / 'reports/monthly-report-2026-10.html'
    source = report.read_text()
    if 'class="workspace-report"' not in source:
        source = source.replace('</head>', '<meta name="viewport" content="width=device-width, initial-scale=1"></head>')
        source = re.sub(r'<body[^>]*>', '<body><main id="main" class="workspace-report">', source, count=1)
        source = source.replace('</body>', '</main></body>')
    report.write_text(frame(source, 'report', '월초 리포트'))

    catalog = json.loads((SITE / 'api/index.json').read_text())
    cards = []
    for tool in catalog['tools']:
        name, desc = html.escape(tool['name']), html.escape(tool['description'])
        schema = html.escape(json.dumps(tool.get('input_schema', {}), ensure_ascii=False, indent=2))
        link = f'<a href="/api/{html.escape(tool["static"], quote=True)}">스냅샷 보기 →</a>' if tool.get('static') else '<span>HTTP · MCP 서버로 호출</span>'
        cards.append(f'<article><h2>{name}</h2><p>{desc}</p>{link}<details><summary>입력 매개변수</summary><pre>{schema}</pre></details></article>')
    page = '''<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Zero HR — 시스템 연동</title>
<style>body{background:#f0eee6;color:#292923;font-family:Inter,-apple-system,sans-serif;line-height:1.6}main{max-width:1400px;margin:auto}h1{font-size:26px;margin-top:28px}a{color:#a55339}summary{cursor:pointer}</style></head><body>
<main id="main"><h1>시스템 연동</h1><p>인원 분석·급여·온보딩 데이터를 기존 시스템에서 함께 사용하세요.</p><p>정적 스냅샷 기준 · <a href="/api/index.json">Function Call 카탈로그 JSON</a></p><div class="integration-tools">'''
    page += ''.join(cards) + '</div></main><script id="report-data" type="application/json">{}</script></body></html>'
    target = SITE / 'integrations/index.html'
    target.parent.mkdir(exist_ok=True)
    target.write_text(frame(page, 'integrations', '시스템 연동'))

    app = (SITE / 'app/index.html').read_text()
    (SITE / 'index.html').write_text(build_home(app, report.read_text(), cards))


if __name__ == '__main__':
    build()
