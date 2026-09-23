#!/usr/bin/env python3
"""validate_input.py — 페르소나 인풋(products/inputs/{persona}-{YYYY-MM-DD}.json)을
DATA_CONTRACT §16 스키마로 검증하고, fitCriteria[].evidence 접두가 계약 경로인지 확인한다.

  - 스키마 위반           → errors, 종료 코드 1
  - 계약에 없는 evidence  → 거절하지 않고 products/inputs/backlog.md 에 "계약 확장 필요"로 적재 (종료 코드 0, --strict 면 1)
  - 파일명 규약·id 접두   → warnings

Python 3.9 표준 라이브러리만. 종료 코드 0 유효 / 1 무효(또는 --strict 백로그 발생) / 2 인자·파일 오류.
"""
import argparse
import csv
import datetime as dt
import json
import os
import re
import sys

SOURCES = {"interview", "survey", "ticket", "agent"}
PERSONA_RE = re.compile(r"^[a-z][a-z0-9-]*$")
ID_RE = re.compile(r"^[A-Z][A-Z0-9]{0,4}-[NF]\d+$")
FILENAME_RE = re.compile(r"^([a-z][a-z0-9-]*)-(\d{4}-\d{2}-\d{2})\.json$")

# evidence 접두 → (계약 절, 해석 파일). 파일이 None 이면 접두 존재만 확인.
CONTRACT_PREFIXES = {
    "headcount-master.clean.": ("§3-1", "data/clean/headcount-master.clean.csv"),
    "to-plan.clean.": ("§3-2", "data/clean/to-plan.clean.csv"),
    "planned-joiners.clean.": ("§3-3", "data/clean/planned-joiners.clean.csv"),
    "planned-leavers.clean.": ("§3-4", "data/clean/planned-leavers.clean.csv"),
    "cleansing-log.": ("§3-5", None),
    "cleansing-summary.": ("§3-6", "data/clean/cleansing-summary.json"),
    "headcount-stats.": ("§4-1", "data/stats/headcount-stats.json"),
    "month-end-forecast.": ("§4-2", "data/stats/month-end-forecast.json"),
    "attrition-risk.": ("§4-3", "data/stats/attrition-risk.json"),
    "automation-effect.": ("§8", "data/stats/automation-effect.json"),
    "persona-needs.": ("§9", "personas/persona-needs.json"),
    "payroll-close.": ("§10", "data/stats/payroll-close.json"),
    "onboarding-plan.": ("§11", "data/stats/onboarding-plan.json"),
    "product-comparison.": ("§12", "products/product-comparison.json"),
    "site/": ("§5", None),
    "reports/": ("§6", None),
    "policy:": ("정책 스킬(부정 기준)", None),
    "api/": ("§17 Function Call 인터페이스", None),
    "reconciliation:": ("대사 비교", None),
}


def resolve(root, prefix, evidence):
    """evidence 경로를 실제 파일에서 따라가 본다. (True/False/None=파일 없음·판정 불가)"""
    _, file = CONTRACT_PREFIXES[prefix]
    if not file:
        return None
    path = os.path.join(root, file)
    if not os.path.exists(path):
        return None
    rest = evidence[len(prefix):]
    keys = [k for k in re.split(r"\.|\[\]", rest) if k]
    if file.endswith(".csv"):
        try:
            with open(path, encoding="utf-8") as f:
                header = next(csv.reader(f))
        except (OSError, StopIteration):
            return None
        return (not keys) or keys[0] in header
    try:
        with open(path, encoding="utf-8") as f:
            cur = json.load(f)
    except (OSError, ValueError):
        return None
    for k in keys:
        if isinstance(cur, list):
            cur = cur[0] if cur else None
        if not isinstance(cur, dict) or k not in cur:
            return False
        cur = cur[k]
    return True


def check_items(items, field, id_key, text_key, num_key, errors, warnings, ids):
    if not isinstance(items, list) or not items:
        errors.append("{}: 비어 있지 않은 배열이어야 한다".format(field))
        return
    for i, it in enumerate(items):
        where = "{}[{}]".format(field, i)
        if not isinstance(it, dict):
            errors.append(where + ": 객체가 아니다")
            continue
        iid = it.get("id")
        if not isinstance(iid, str) or not iid:
            errors.append(where + ".id 누락")
        else:
            if iid in ids:
                errors.append(where + ".id 중복: " + iid)
            ids.add(iid)
            if not ID_RE.match(iid):
                warnings.append(where + ".id '{}' 는 권장 형식(예: FC-N1 / FC-F1)이 아니다".format(iid))
        if not isinstance(it.get(text_key), str) or not it.get(text_key).strip():
            errors.append("{}.{} 누락".format(where, text_key))
        n = it.get(num_key)
        if not isinstance(n, int) or isinstance(n, bool) or not 1 <= n <= 5:
            errors.append("{}.{} 는 1~5 정수여야 한다 (현재 {!r})".format(where, num_key, n))


def main(argv=None):
    ap = argparse.ArgumentParser(description="페르소나 인풋 §16 스키마 + evidence 계약 경로 검증")
    ap.add_argument("input", help="products/inputs/{persona}-{YYYY-MM-DD}.json")
    ap.add_argument("--root", default="/Users/yang/development/zero-hr")
    ap.add_argument("--backlog", default="products/inputs/backlog.md")
    ap.add_argument("--no-backlog", action="store_true", help="백로그 파일에 쓰지 않는다(검사만)")
    ap.add_argument("--strict", action="store_true", help="계약 밖 evidence 가 있으면 종료 코드 1")
    args = ap.parse_args(argv)

    root = os.path.abspath(args.root)
    path = args.input if os.path.isabs(args.input) else os.path.join(root, args.input)
    if not os.path.exists(path):
        print(json.dumps({"valid": False, "errors": ["파일 없음: " + args.input]}, ensure_ascii=False))
        return 2
    try:
        with open(path, encoding="utf-8") as f:
            doc = json.load(f)
    except ValueError as e:
        print(json.dumps({"valid": False, "errors": ["JSON 파싱 실패: {}".format(e)]}, ensure_ascii=False))
        return 1

    errors, warnings, ids = [], [], set()
    if not isinstance(doc, dict):
        print(json.dumps({"valid": False, "errors": ["최상위가 객체가 아니다"]}, ensure_ascii=False))
        return 1

    persona = doc.get("persona")
    if not isinstance(persona, str) or not PERSONA_RE.match(persona or ""):
        errors.append("persona: kebab-case 문자열이어야 한다 (예: finance-controller)")
    if not isinstance(doc.get("title"), str) or not doc.get("title", "").strip():
        errors.append("title 누락")
    sub = doc.get("submittedAt")
    try:
        dt.date.fromisoformat(sub if isinstance(sub, str) else "")
    except ValueError:
        errors.append("submittedAt: YYYY-MM-DD 여야 한다")
    if doc.get("source") not in SOURCES:
        errors.append("source: {} 중 하나여야 한다".format("|".join(sorted(SOURCES))))

    check_items(doc.get("needs"), "needs", "id", "need", "importance", errors, warnings, ids)
    check_items(doc.get("fitCriteria"), "fitCriteria", "id", "criterion", "weight", errors, warnings, ids)

    rubric = doc.get("rubric")
    if not isinstance(rubric, dict):
        errors.append("rubric: {lens, scoring} 객체여야 한다")
    else:
        for k in ("lens", "scoring"):
            if not isinstance(rubric.get(k), str) or not rubric.get(k).strip():
                errors.append("rubric.{} 누락".format(k))

    # 파일명 규약
    base = os.path.basename(path)
    m = FILENAME_RE.match(base)
    if not base.startswith("example-"):
        if not m:
            warnings.append("파일명 '{}' 은 {{persona}}-{{YYYY-MM-DD}}.json 규약이 아니다".format(base))
        elif isinstance(persona, str) and (m.group(1) != persona or m.group(2) != sub):
            warnings.append("파일명의 persona/날짜({}, {})가 본문({}, {})과 다르다".format(m.group(1), m.group(2), persona, sub))

    # evidence 접두 검사
    evidence_report, backlog = [], []
    for it in doc.get("fitCriteria") or []:
        if not isinstance(it, dict):
            continue
        ev = it.get("evidence")
        if not isinstance(ev, str) or not ev.strip():
            errors.append("fitCriteria {} : evidence 누락".format(it.get("id")))
            continue
        prefix = next((p for p in CONTRACT_PREFIXES if ev.startswith(p)), None)
        rec = {"id": it.get("id"), "evidence": ev, "prefix": prefix, "known": prefix is not None,
               "contract": CONTRACT_PREFIXES[prefix][0] if prefix else None,
               "resolved": resolve(root, prefix, ev) if prefix else None}
        evidence_report.append(rec)
        if prefix is None:
            backlog.append(rec)
        elif rec["resolved"] is False:
            warnings.append("fitCriteria {}: evidence '{}' 경로를 현재 산출물에서 찾지 못함(접두는 계약 경로 — 필드 확인)".format(it.get("id"), ev))

    backlog_written = None
    if backlog and not args.no_backlog and not errors:
        bpath = os.path.join(root, args.backlog)
        os.makedirs(os.path.dirname(bpath), exist_ok=True)
        new = not os.path.exists(bpath)
        with open(bpath, "a", encoding="utf-8") as f:
            if new:
                f.write("# 페르소나 인풋 백로그 — 계약 확장 필요\n\n"
                        "`validate_input.py`가 DATA_CONTRACT 경로(§3~§12)에 없는 evidence를 만나면 거절하지 않고 여기에 적재한다(§16).\n"
                        "계약을 확장(필드 추가 → 스크립트 → 제품)한 뒤 해당 인풋을 재검증하면 항목을 지운다.\n\n"
                        "| 등록일 | 인풋 파일 | 페르소나 | 기준 id | evidence | 상태 |\n|---|---|---|---|---|---|\n")
            for rec in backlog:
                f.write("| {} | {} | {} | {} | `{}` | 계약 확장 필요 |\n".format(
                    dt.date.today().isoformat(), os.path.relpath(path, root), persona, rec["id"], rec["evidence"]))
        backlog_written = args.backlog

    valid = not errors
    out = {"valid": valid, "input": os.path.relpath(path, root), "persona": persona, "submittedAt": sub,
           "counts": {"needs": len(doc.get("needs") or []), "fitCriteria": len(doc.get("fitCriteria") or [])},
           "errors": errors, "warnings": warnings, "evidence": evidence_report,
           "backlogged": [r["id"] for r in backlog], "backlogFile": backlog_written}
    print(json.dumps(out, ensure_ascii=False, indent=2))
    if not valid:
        return 1
    if backlog and args.strict:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
