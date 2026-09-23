#!/usr/bin/env python3
"""mechanical_scoring.py — 심판의 '사실' 부분을 결정적으로 계산한다 (product-judge SKILL.md §2~§4, §6).

기계 채점(fit 기준 충족)과 PII 부정 검사는 렌즈와 무관하므로 세 심판이 같은 값을 써야 한다.
심판 agent 는 이 스크립트의 출력을 받아 **정성 루브릭(§5)만** 채점한다 — 사람이 판단할 곳에만 판단을 쓴다.

출력: _workspace/judging/mechanical.json
  {asOfDate, products:{code:{criteriaMet:[{id,weight,met,evidence|reason}], coverage, weightedCoverage,
   sections:[{dataSection,dataFit[],dataEvidence[]}], piiChecks:[{check,passed,detail}]}},
   advocate:{persona:{product:{coverage,weightedCoverage,met:[id]}}}, warnings:[]}
"""
import argparse
import json
import os
import re
import sys

ROOT = os.environ.get("ZERO_HR_ROOT") or os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))))))
PRODUCTS = ("insight", "payroll", "onboard")
PERSONA_OF = {"insight": "head-of-hr", "payroll": "payroll", "onboard": "onboarding"}
# evidence 접두 → 스냅샷 키 (product-specs.md §0 / SKILL.md §2)
PREFIX_MAP = {
    "headcount-stats.": {"insight": "stats.", "payroll": "statsSubset.", "onboard": None},
    "month-end-forecast.": {"insight": "forecast.", "payroll": "payrollClose.payrollHeadcount.", "onboard": None},
    "attrition-risk.": {"insight": "attrition.", "payroll": None, "onboard": "onboardingPlan."},
    "cleansing-summary.": {"insight": "cleansingSummary.", "payroll": "cleansingSummary.", "onboard": None},
    "automation-effect.": {"insight": "automationEffect.", "payroll": None, "onboard": None},
    "headcount-master.clean.": {"insight": "hrDirectory[]", "payroll": None, "onboard": "hrDirectorySubset[]"},
    "payroll-close.": {"insight": None, "payroll": "payrollClose.", "onboard": None},
    "onboarding-plan.": {"insight": None, "payroll": None, "onboard": "onboardingPlan."},
    "planned-joiners.clean.": {"insight": None, "payroll": None, "onboard": "plannedJoiners[]"},
}
RE_SECTION = re.compile(r"<(?:section|header|footer|div|nav|aside)\b([^>]*)>", re.I)
RE_ATTR = re.compile(r'(data-section|data-fit|data-evidence|data-views|data-role)\s*=\s*"([^"]*)"')
AMOUNT_TOKENS = ("salary", "급여액", "지급액", "계좌", "세액")


def load_json(path):
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def dig(obj, path):
    """점 경로. `[]` 는 배열로 내려가 첫 원소를 본다(존재·비어있지 않음 판정이 목적)."""
    cur = obj
    for token in [t for t in re.split(r"\.", path) if t]:
        arr = token.endswith("[]")
        key = token[:-2] if arr else token
        if isinstance(cur, dict) and key in cur:
            cur = cur[key]
        elif isinstance(cur, list) and cur and isinstance(cur[0], dict) and key in cur[0]:
            collected = []
            for row in cur:
                if not isinstance(row, dict) or key not in row:
                    continue
                value = row[key]
                if isinstance(value, list):
                    collected.extend(value)
                else:
                    collected.append(value)
            cur = collected or None
        else:
            return None
        if arr and isinstance(cur, list):
            if not cur:
                return None
    return cur


def non_empty(value):
    if value is None:
        return False
    if hasattr(value, "__len__"):
        return len(value) > 0
    return True


def parse_sections(html):
    out = []
    for attr_text in RE_SECTION.findall(html):
        attrs = dict(RE_ATTR.findall(attr_text))
        if "data-section" not in attrs and "data-fit" not in attrs:
            continue
        attrs.setdefault("data-section", "(header)")
        out.append({
            "dataSection": attrs["data-section"],
            "dataFit": [x for x in re.split(r"[\s,]+", attrs.get("data-fit", "")) if x],
            "dataEvidence": [x for x in re.split(r"[\s,]+", attrs.get("data-evidence", "")) if x],
            "dataViews": [x for x in re.split(r"[\s,]+", attrs.get("data-views", "")) if x],
        })
    return out


def split_evidence(ev):
    """evidence 는 `; ` 로 여러 경로를 담을 수 있다 — 하나하나 판정하고 모두 참이어야 충족이다."""
    return [x.strip() for x in ev.split(";") if x.strip()]


def judge_criterion(code, crit, html, sections, snap, ctx):
    """여러 evidence 를 각각 판정해 합친다."""
    parts = split_evidence(crit.get("evidence") or "")
    if len(parts) <= 1:
        return _judge_one(code, crit, html, sections, snap, ctx)
    results = [_judge_one(code, dict(crit, evidence=part), html, sections, snap, ctx) for part in parts]
    verifiable = [r for r in results if r["met"] is not None]
    if not verifiable:
        return {"id": crit["id"], "weight": crit["weight"], "met": None,
                "reason": "unverifiable: " + "; ".join(r.get("reason") or "" for r in results)[:200]}
    failed = [r for r in verifiable if not r["met"]]
    if failed:
        return {"id": crit["id"], "weight": crit["weight"], "met": False,
                "reason": "; ".join(filter(None, (r.get("reason") for r in failed)))[:300],
                "partial": "%d/%d 충족" % (len(verifiable) - len(failed), len(verifiable))}
    return {"id": crit["id"], "weight": crit["weight"], "met": True,
            "evidence": " | ".join(filter(None, (r.get("evidence") for r in verifiable)))[:400]}


def _judge_one(code, crit, html, sections, snap, ctx):
    """SKILL.md §3: (a) data-fit 섹션 존재 (b) evidence 접두 일치 (c) 스냅샷 경로 비어 있지 않음."""
    cid, ev = crit["id"], (crit.get("evidence") or "")
    owning = [s for s in sections if cid in s["dataFit"]]
    if ev.startswith("policy:"):
        passed = all(c["passed"] for c in ctx["pii"])
        return {"id": cid, "weight": crit["weight"], "met": bool(passed and owning or passed),
                "evidence": "PII 부정 검사 %d건 전부 통과" % len(ctx["pii"]) if passed else None,
                "reason": None if passed else "PII 검사 실패"}
    if ev.startswith("reconciliation:"):
        body = ev.split(":", 1)[1]
        if "=" not in body:
            return {"id": cid, "weight": crit["weight"], "met": None, "reason": "unverifiable: 비교식 형식 아님"}
        left_p, right_p = [x.strip() for x in body.split("=", 1)]
        left = ctx["resolve"](left_p)
        right = ctx["resolve"](right_p)
        def reduce_list(v):
            """숫자 목록은 합(조직별 값의 전사 합계), 그 밖의 목록은 건수로 비교한다."""
            if not isinstance(v, list):
                return v
            if v and all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in v):
                return sum(v)
            return len(v)

        if isinstance(left, list) or isinstance(right, list):
            left, right = reduce_list(left), reduce_list(right)
        ok = left is not None and right is not None and left == right
        return {"id": cid, "weight": crit["weight"], "met": bool(ok),
                "evidence": "%s=%s vs %s=%s" % (left_p, left, right_p, right) if ok else None,
                "reason": None if ok else "대사 불일치 %s=%s / %s=%s" % (left_p, left, right_p, right)}
    if ev.startswith("api/"):
        catalog = ctx["catalog"]
        prefix = ev.split(" ", 1)[1].rstrip("*") if " " in ev else ""
        names = [t["name"] for t in catalog if t["name"].startswith(prefix)] if catalog else []
        ok = bool(names)
        return {"id": cid, "weight": crit["weight"], "met": ok,
                "evidence": "api/tools.json: %s" % ", ".join(names[:4]) if ok else None,
                "reason": None if ok else "도구 카탈로그에 %s 없음" % prefix}
    if ev.startswith("reports/"):
        ok = os.path.exists(os.path.join(ctx["root"], "reports", "monthly-report-dispatch.json")) and "monthly-report" in html
        return {"id": cid, "weight": crit["weight"], "met": ok,
                "evidence": "reports/monthly-report-dispatch.json + 페이지 링크" if ok else None,
                "reason": None if ok else "리포트 산출물 또는 링크 없음"}
    if ev.startswith("site/"):
        ok = bool(owning) or ('data-section="header"' in html)
        return {"id": cid, "weight": crit["weight"], "met": ok,
                "evidence": "섹션 %s" % ",".join(s["dataSection"] for s in owning) if ok else None,
                "reason": None if ok else "해당 화면 요소 없음"}
    prefix = next((p for p in PREFIX_MAP if ev.startswith(p)), None)
    if prefix is None:
        return {"id": cid, "weight": crit["weight"], "met": None, "reason": "unverifiable: 매핑 없는 evidence %r" % ev}
    key = PREFIX_MAP[prefix][code]
    if key is None:
        return {"id": cid, "weight": crit["weight"], "met": None, "reason": "unverifiable: %s 제품에 해당 없음" % code}
    rest = ev[len(prefix):]
    path = key.rstrip("[]") + ("" if key.endswith("[]") else "") + rest if not key.endswith("[]") else key[:-2]
    value = dig(snap, path)
    if value is None and rest:
        value = dig(snap, key.split(".")[0] + "." + rest)
    ok_data = non_empty(value)
    if not owning:
        return {"id": cid, "weight": crit["weight"], "met": False,
                "reason": "data-fit 에 %s 를 단 섹션 없음%s" % (cid, "" if ok_data else " (스냅샷 경로도 비어 있음)")}
    top = key.split(".")[0].rstrip("[]")
    ev_match = any(e.split(".")[0].rstrip("[]") == top for s in owning for e in s["dataEvidence"]) or not any(
        s["dataEvidence"] for s in owning)
    if not ev_match:
        return {"id": cid, "weight": crit["weight"], "met": False, "reason": "data-evidence 불일치(기대 %s.)" % top}
    if not ok_data:
        return {"id": cid, "weight": crit["weight"], "met": False, "reason": "스냅샷 경로 %s 비어 있음" % path}
    length = len(value) if hasattr(value, "__len__") else None
    return {"id": cid, "weight": crit["weight"], "met": True,
            "evidence": "site/%s/index.html data-section=%s data-fit=%s · %s.json %s%s" % (
                code, owning[0]["dataSection"], cid, code, path, "[%d]" % length if length is not None else "")}


RE_EMBED = re.compile(r'<script\b[^>]*id="report-data"[^>]*>.*?</script>', re.S | re.I)


def visible_markup(html):
    """내장 스냅샷 JSON을 뺀 마크업 — 화면에 실제로 그려지는 부분만 PII 검사한다."""
    return RE_EMBED.sub("", html)


def pii_checks(code, html_full, snap):
    html = visible_markup(html_full)
    out = []
    text = json.dumps(snap, ensure_ascii=False) if snap else ""
    out.append({"check": "스냅샷에 birthDate 없음", "passed": '"birthDate"' not in text, "detail": "site/data/%s.json" % code})
    out.append({"check": "HTML에 riskScore 표시 없음", "passed": "riskScore" not in html, "detail": "site/%s/index.html (내장 JSON 제외)" % code})
    if code == "payroll":
        hits = [t for t in AMOUNT_TOKENS if t in html]
        hits = [t for t in hits if not re.search(r"[^<>]{0,40}%s[^<>]{0,40}(없|다루지|제외|아닙)" % re.escape(t), html)]
        out.append({"check": "금액·계좌 필드 없음", "passed": not hits, "detail": ",".join(hits) or "0건"})
    if code == "insight":
        exec_only = re.findall(r'<section\b[^>]*data-views="([^"]*)"[^>]*>(.{0,4000}?)</section>', html, re.S)
        bad = [v for v, body in exec_only if "hr" not in v.split() and re.search(r"hrDirectory|\.name\b", body)]
        out.append({"check": "경영진·경영기획·조직장 섹션에 성명 조인 없음", "passed": not bad, "detail": ",".join(bad) or "0건"})
    if code == "onboard":
        cohort = re.search(r'data-section="cohort"(.{0,6000}?)</section>', html, re.S)
        body = cohort.group(1) if cohort else ""
        out.append({"check": "90일 코호트에 성명 없음", "passed": "\\.name" not in body and "joiner.name" not in body,
                    "detail": "data-section=cohort"})
    return out


def coverage(rows):
    verifiable = [r for r in rows if r["met"] is not None]
    met = [r for r in verifiable if r["met"]]
    wsum = sum(r["weight"] for r in verifiable) or 1
    return (round(len(met) / len(verifiable), 4) if verifiable else 0.0,
            round(sum(r["weight"] for r in met) / wsum, 4), len(verifiable), len(met))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=ROOT)
    args = ap.parse_args(argv)
    root = args.root
    needs = load_json(os.path.join(root, "personas", "persona-needs.json"))
    if needs is None:
        print(json.dumps({"status": "blocked", "error": "personas/persona-needs.json 없음"}, ensure_ascii=False))
        return 3
    by_persona = {p["code"]: p for p in needs["personas"]}
    catalog = load_json(os.path.join(root, "api", "tools.json"))
    warnings, products, snaps, htmls = [], {}, {}, {}
    for code in PRODUCTS:
        html_path = os.path.join(root, "site", code, "index.html")
        snap_path = os.path.join(root, "site", "data", "%s.json" % code)
        if not os.path.exists(html_path):
            warnings.append("%s 페이지 없음" % code)
            continue
        htmls[code] = open(html_path, encoding="utf-8").read()
        snaps[code] = load_json(snap_path)

    stats_files = {}
    for stem in ("headcount-stats", "month-end-forecast", "attrition-risk", "payroll-close",
                 "onboarding-plan", "automation-effect"):
        stats_files[stem] = load_json(os.path.join(root, "data", "stats", "%s.json" % stem))
    stats_files["cleansing-summary"] = load_json(os.path.join(root, "data", "clean", "cleansing-summary.json"))

    def clean_rows(stem):
        """`planned-joiners.clean` 같은 정제 CSV 는 행 수로 비교한다."""
        path = os.path.join(root, "data", "clean", "%s.csv" % stem)
        if not os.path.exists(path):
            return None
        with open(path, encoding="utf-8-sig") as fh:
            return max(sum(1 for _ in fh) - 1, 0)

    def resolver(code):
        def resolve(path):
            if path.endswith(".clean") or ".clean." not in path and path.endswith("clean"):
                rows = clean_rows(path)
                if rows is not None:
                    return rows
            m_clean = re.match(r"([\w-]+)\.clean$", path)
            if m_clean:
                rows = clean_rows(m_clean.group(1) + ".clean")
                if rows is not None:
                    return rows
            # 1) 계약 파일 이름으로 시작하면 원본 산출물에서 바로 읽는다
            stem = path.split(".")[0]
            if stem in stats_files and stats_files[stem] is not None:
                v = dig(stats_files[stem], path[len(stem) + 1:]) if len(path) > len(stem) else stats_files[stem]
                if v is not None:
                    return v
            # 2) site/data/{product}.json.{경로} 형태
            m = re.match(r"site/data/(\w+)\.json\.(.+)", path)
            if m and snaps.get(m.group(1)) is not None:
                v = dig(snaps[m.group(1)], m.group(2))
                if v is not None:
                    return v
            for c in (code,) + PRODUCTS:
                if snaps.get(c) is None:
                    continue
                stem = path.split(".")[0]
                key = {"payroll-close": "payrollClose", "month-end-forecast": "forecast",
                       "headcount-stats": "stats", "attrition-risk": "attrition",
                       "onboarding-plan": "onboardingPlan", "cleansing-summary": "cleansingSummary"}.get(stem, stem)
                v = dig(snaps[c], key + path[len(stem):])
                if v is not None:
                    return v
            return None
        return resolve

    for code in htmls:
        sections = parse_sections(htmls[code])
        pii = pii_checks(code, htmls[code], snaps.get(code))
        ctx = {"pii": pii, "root": root, "catalog": catalog, "resolve": resolver(code)}
        persona = by_persona[PERSONA_OF[code]]
        rows = [judge_criterion(code, c, htmls[code], sections, snaps.get(code), ctx) for c in persona["fitCriteria"]]
        cov, wcov, verif, met = coverage(rows)
        products[code] = {"persona": PERSONA_OF[code], "criteriaMet": rows, "coverage": cov,
                          "weightedCoverage": wcov, "verifiable": verif, "met": met,
                          "sections": sections, "piiChecks": pii}
    advocate = {}
    for pcode, persona in by_persona.items():
        advocate[pcode] = {}
        for code in htmls:
            sections = parse_sections(htmls[code])
            ctx = {"pii": products[code]["piiChecks"], "root": root, "catalog": catalog, "resolve": resolver(code)}
            rows = [judge_criterion(code, c, htmls[code], sections, snaps.get(code), ctx) for c in persona["fitCriteria"]]
            cov, wcov, verif, met = coverage(rows)
            advocate[pcode][code] = {"coverage": cov, "weightedCoverage": wcov, "verifiable": verif,
                                     "met": [r["id"] for r in rows if r["met"]],
                                     "unmet": [{"id": r["id"], "reason": r.get("reason")} for r in rows if r["met"] is False]}
    out = {"asOfDate": needs.get("asOfDate"), "products": products, "advocate": advocate, "warnings": warnings,
           "script": ".claude/skills/product-judge/scripts/mechanical_scoring.py"}
    out_dir = os.path.join(root, "_workspace", "judging")
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "mechanical.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=2)
    print(json.dumps({"status": "ok", "out": "_workspace/judging/mechanical.json",
                      "products": {c: {"coverage": products[c]["coverage"], "weightedCoverage": products[c]["weightedCoverage"],
                                       "met": "%d/%d" % (products[c]["met"], products[c]["verifiable"]),
                                       "piiFailed": [x["check"] for x in products[c]["piiChecks"] if not x["passed"]]}
                                   for c in products},
                      "warnings": warnings}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
