#!/usr/bin/env python3
"""changelog.py — products/CHANGELOG.md(Keep a Changelog)에 항목을 추가/내보내기.

버전 규칙(DATA_CONTRACT §16): v{major}.{minor}
  - 첫 항목은 v1.0
  - kind=judge   : 심판 라운드 → minor +1   (v1.0 → v1.1)
  - kind=rebuild : 통합 제품 재구성 → major +1, minor 0   (v1.3 → v2.0)
항목마다 `근거`(인풋 파일·심판 점수 변화)와 `영향 받은 fitCriteria id`를 남긴다.

하위 명령:
  add      항목 추가 (Unreleased 바로 아래에 새 버전 절 삽입)
  export   CHANGELOG를 JSON 배열로 stdout에 (통합 제품 스냅샷 app.json의 changelog 키)
  current  현재 최신 버전 출력 (없으면 none)

Python 3.9 표준 라이브러리만. 종료 코드 0 완료 / 1 파일·입력 오류 / 2 인자 오류.
"""
import argparse
import datetime as dt
import json
import os
import re
import sys

VERSION_RE = re.compile(r"^## \[v(\d+)\.(\d+)\](?: - (\d{4}-\d{2}-\d{2}))?\s*$")
UNRELEASED_RE = re.compile(r"^## \[Unreleased\]\s*$")
ENTRY_RE = re.compile(r"^- \((judge|rebuild|init)\) (.*)$")
BASIS_RE = re.compile(r"^  - 근거: (.*)$")
CRIT_RE = re.compile(r"^  - 영향 받은 fitCriteria id: (.*)$")

PREAMBLE = """# Changelog — Everyday People Agent (제품 변경 이력)

모든 주목할 변경을 이 파일에 기록한다. 형식은 [Keep a Changelog](https://keepachangelog.com/ko/1.1.0/)를 따르고,
버전은 DATA_CONTRACT §16 규칙 — `v{major}.{minor}`: 심판 라운드마다 minor +1, 통합 제품 재구성이면 major +1.
항목마다 `근거`(인풋 파일·심판 점수 변화)와 `영향 받은 fitCriteria id`를 적는다.
항목은 `product-evolution` 스킬의 `scripts/changelog.py`가 쓴다 — 손으로 쓰지 않는다(버전 규칙이 스크립트에 있다).

## [Unreleased]
"""


def read_lines(path):
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return f.read().splitlines()


def current_version(lines):
    for ln in lines or []:
        m = VERSION_RE.match(ln)
        if m:
            return int(m.group(1)), int(m.group(2))
    return None


def next_version(cur, kind):
    if cur is None:
        return (1, 0)
    major, minor = cur
    if kind == "rebuild":
        return (major + 1, 0)
    return (major, minor + 1)


def fmt(v):
    return "v{}.{}".format(*v)


def score_delta(before_path, after_path):
    """product-comparison.json 두 버전의 panelScore/weightedCoverage/bestFit 변화를 한 줄로"""
    def load(p):
        try:
            with open(p, encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError, TypeError):
            return None
    b, a = load(before_path) if before_path else None, load(after_path) if after_path else None
    if a is None:
        return None
    def idx(doc):
        return {p.get("code"): p.get("fitScore", {}) for p in (doc or {}).get("products", [])}
    bi, ai = idx(b), idx(a)
    parts = []
    for code in ("insight", "payroll", "onboard"):
        if code not in ai:
            continue
        ap = ai[code].get("panelScore")
        aw = ai[code].get("weightedCoverage")
        if code in bi:
            parts.append("{} panel {}→{} / wCov {}→{}".format(code, bi[code].get("panelScore"), ap, bi[code].get("weightedCoverage"), aw))
        else:
            parts.append("{} panel {} / wCov {}".format(code, ap, aw))
    bb = ((b or {}).get("comparison") or {}).get("bestFit")
    ab = ((a or {}).get("comparison") or {}).get("bestFit")
    parts.append("bestFit {}→{}".format(bb, ab) if b is not None else "bestFit {}".format(ab))
    return "; ".join(parts)


def build_entry(version, date, kind, section, summary, basis_lines, criteria):
    out = ["## [{}] - {}".format(fmt(version), date), "### {}".format(section), "- ({}) {}".format(kind, summary)]
    for b in basis_lines:
        out.append("  - 근거: {}".format(b))
    out.append("  - 영향 받은 fitCriteria id: {}".format(", ".join(criteria) if criteria else "(없음)"))
    out.append("")
    return out


def insert_entry(lines, entry):
    """[Unreleased] 절 다음(다음 ## 헤더 앞)에 삽입. Unreleased가 없으면 첫 ## [v 앞, 그것도 없으면 끝."""
    if lines is None:
        lines = PREAMBLE.splitlines()
    idx_unrel = next((i for i, ln in enumerate(lines) if UNRELEASED_RE.match(ln)), None)
    if idx_unrel is not None:
        j = idx_unrel + 1
        while j < len(lines) and not lines[j].startswith("## "):
            j += 1
        # keep exactly one blank line between Unreleased block and new entry
        body = lines[idx_unrel + 1:j]
        while body and body[-1].strip() == "":
            body.pop()
        return lines[:idx_unrel + 1] + body + [""] + entry + lines[j:]
    idx_first = next((i for i, ln in enumerate(lines) if VERSION_RE.match(ln)), None)
    if idx_first is not None:
        return lines[:idx_first] + entry + lines[idx_first:]
    return lines + [""] + entry


def export(lines):
    versions, cur, entry, section = [], None, None, None
    for ln in lines or []:
        m = VERSION_RE.match(ln)
        if m:
            cur = {"version": "v{}.{}".format(m.group(1), m.group(2)), "date": m.group(3), "entries": []}
            versions.append(cur)
            entry, section = None, None
            continue
        if UNRELEASED_RE.match(ln):
            cur, entry, section = None, None, None
            continue
        if cur is None:
            continue
        if ln.startswith("### "):
            section = ln[4:].strip()
            continue
        m = ENTRY_RE.match(ln)
        if m:
            entry = {"kind": m.group(1), "section": section, "summary": m.group(2).strip(), "basis": [], "criteria": []}
            cur["entries"].append(entry)
            continue
        if entry is not None:
            m = BASIS_RE.match(ln)
            if m:
                entry["basis"].append(m.group(1).strip())
                continue
            m = CRIT_RE.match(ln)
            if m:
                raw = m.group(1).strip()
                entry["criteria"] = [] if raw.startswith("(") else [c.strip() for c in raw.split(",") if c.strip()]
    return versions


def main(argv=None):
    ap = argparse.ArgumentParser(description="products/CHANGELOG.md 항목 추가·내보내기 (DATA_CONTRACT §16 버전 규칙)")
    ap.add_argument("--root", default="/Users/yang/development/zero-hr")
    ap.add_argument("--file", default="products/CHANGELOG.md")
    sub = ap.add_subparsers(dest="cmd")

    a = sub.add_parser("add", help="항목 추가 (버전 자동 증가)")
    a.add_argument("--kind", required=True, choices=["judge", "rebuild"], help="judge=심판 라운드(minor+1) / rebuild=통합 제품 재구성(major+1)")
    a.add_argument("--summary", required=True, help="한 문장 요약")
    a.add_argument("--basis", action="append", default=[], help="근거 (반복 가능)")
    a.add_argument("--input", default=None, help="촉발한 페르소나 인풋 파일 products/inputs/*.json")
    a.add_argument("--criteria", default="", help="영향 받은 fitCriteria id, 콤마 구분")
    a.add_argument("--before", default=None, help="이전 product-comparison.json (products/history/vX.Y.json)")
    a.add_argument("--after", default=None, help="현재 product-comparison.json")
    a.add_argument("--date", default=None, help="YYYY-MM-DD (기본 오늘)")
    a.add_argument("--section", default=None, choices=["Added", "Changed", "Fixed", "Removed"], help="기본: 첫 버전 Added, 이후 Changed")
    a.add_argument("--dry-run", action="store_true")

    sub.add_parser("export", help="JSON 배열로 stdout에 (최신 버전 먼저)")
    sub.add_parser("current", help="현재 최신 버전 출력")
    args = ap.parse_args(argv)

    if not args.cmd:
        ap.print_help()
        return 2
    path = os.path.join(os.path.abspath(args.root), args.file)
    lines = read_lines(path)

    if args.cmd == "current":
        cur = current_version(lines)
        print(fmt(cur) if cur else "none")
        return 0
    if args.cmd == "export":
        print(json.dumps(export(lines), ensure_ascii=False, indent=2))
        return 0

    cur = current_version(lines)
    ver = next_version(cur, args.kind)
    date = args.date or dt.date.today().isoformat()
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", date):
        print(json.dumps({"status": "error", "error": "bad-date", "date": date}, ensure_ascii=False))
        return 2
    section = args.section or ("Added" if cur is None else "Changed")
    basis = list(args.basis)
    if args.input:
        basis.insert(0, "인풋 `{}`".format(args.input))
    delta = score_delta(os.path.join(args.root, args.before) if args.before else None,
                        os.path.join(args.root, args.after) if args.after else None)
    if delta:
        basis.append("심판 점수 " + delta)
    if not basis:
        basis.append("(근거 미기재 — --basis/--input/--after 로 남길 것)")
    criteria = [c.strip() for c in args.criteria.split(",") if c.strip()]
    entry = build_entry(ver, date, args.kind, section, args.summary, basis, criteria)
    new_lines = insert_entry(lines, entry)
    result = {"status": "ok", "version": fmt(ver), "previous": fmt(cur) if cur else None, "kind": args.kind,
              "section": section, "path": args.file, "criteria": criteria, "dryRun": args.dry_run}
    if args.dry_run:
        result["entry"] = "\n".join(entry)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(new_lines).rstrip("\n") + "\n")
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
