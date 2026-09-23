#!/usr/bin/env python3
"""aggregate_judgments.py — 심판 3명의 판정(_workspace/judging/{persona}.json)을
products/product-comparison.json(DATA_CONTRACT §12)으로 결정적으로 병합한다.

- criteriaMet[].met : 심판 과반(유효 판정 중). 불일치는 stdout 요약 `disagreements`에 남긴다
- coverage / weightedCoverage : 과반 met 기준 재계산 (unverifiable 제외)
- panelScore : 심판 scores.{product} 평균 (0~10, 소수 2자리)
- bestFit : 최대 composite = 0.5 * weightedCoverage * 10 + 0.5 * panelScore
- summary / recommendation : 템플릿 문장 (재실행 동일)

Python 3.9 표준 라이브러리만. 종료 코드 0 완료 / 1 입력 누락 / 2 인자 오류.
"""
import argparse
import glob
import json
import os
import re
import shutil
import sys

PRODUCTS = ["insight", "payroll", "onboard"]
DISPLAY = {"insight": "Insight", "payroll": "Payroll Close", "onboard": "Onboarding"}
DEFAULT_PERSONA = {"insight": "head-of-hr", "payroll": "payroll", "onboard": "onboarding"}
SHARED_KEYS = {"stats", "forecast", "attrition", "cleansingSummary", "hrDirectory", "automationEffect",
               "statsSubset", "hrDirectorySubset", "plannedJoiners"}
COMMON_SECTIONS = {"header", "kpi", "data-quality", "checklist", "views"}
JUDGE_ORDER = ["head-of-hr", "payroll", "onboarding"]


def load_json(path, default=None):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def rel(root, path):
    return os.path.relpath(path, root)


def persona_map(needs):
    """persona code -> {product, fitCriteria}; product -> persona code"""
    by_code, by_product = {}, {}
    for p in (needs or {}).get("personas", []):
        code = p.get("code")
        by_code[code] = {"product": p.get("product"), "fitCriteria": p.get("fitCriteria", [])}
        if p.get("product") in PRODUCTS:
            by_product[p["product"]] = code
    for prod in PRODUCTS:
        by_product.setdefault(prod, DEFAULT_PERSONA[prod])
    return by_code, by_product


def majority_met(votes):
    """votes: list of True/False/None -> (met, valid_count, disagreement)"""
    valid = [v for v in votes if v is not None]
    if not valid:
        return None, 0, False
    yes = sum(1 for v in valid if v)
    met = yes * 2 > len(valid) if len(valid) > 1 else bool(valid[0])
    disagreement = 0 < yes < len(valid)
    return met, len(valid), disagreement


def sections_in_html(path):
    try:
        html = open(path, encoding="utf-8").read()
    except OSError:
        return set(), 0
    secs = set(re.findall(r'data-section="([^"]+)"', html))
    return secs, html.count("\n") + 1


def shared_reuse(snapshot):
    if not isinstance(snapshot, dict):
        return 0.0
    keys = [k for k, v in snapshot.items() if v not in (None, {}, [])]
    if not keys:
        return 0.0
    return round(sum(1 for k in keys if k in SHARED_KEYS) / len(keys), 4)


def summary_text(ranking, judges_n):
    if not ranking:
        return "채점 결과 없음", "심판을 먼저 실행한다."
    best = ranking[0]
    runner = ranking[1] if len(ranking) > 1 else None
    s = ("심판 {n}명(페르소나 옹호자 렌즈)이 제품 3종을 채점했다. bestFit은 {bn}(가중 충족률 {wc:.0%}, 패널 {ps:.1f}/10, 종합 {c:.2f})"
         .format(n=judges_n, bn=DISPLAY[best["code"]], wc=best["weightedCoverage"], ps=best["panelScore"], c=best["composite"]))
    if runner:
        s += ", 차점은 {rn}(종합 {c:.2f})".format(rn=DISPLAY[runner["code"]], c=runner["composite"])
    s += ". 종합 = 0.5×가중충족률×10 + 0.5×패널 점수."
    others = [DISPLAY[r["code"]] for r in ranking[1:]]
    r = ("통합 제품(app)은 {bn}의 정보 구조를 골격으로 하고, {others}의 충족 섹션(strengths·criteriaMet met=true)을 역할 탭으로 흡수한다. "
         "각 제품 gaps의 [must-fix] 항목을 통합 전에 해소한다.").format(bn=DISPLAY[best["code"]], others="·".join(others) if others else "다른 제품")
    return s, r


def main(argv=None):
    ap = argparse.ArgumentParser(description="심판 판정 3개 → products/product-comparison.json (§12)")
    ap.add_argument("--root", default="/Users/yang/development/zero-hr")
    ap.add_argument("--as-of", default="2026-09-23")
    ap.add_argument("--judging-dir", default="_workspace/judging")
    ap.add_argument("--needs", default="personas/persona-needs.json")
    ap.add_argument("--out", default="products/product-comparison.json")
    ap.add_argument("--build-meta", default=None, help="{product:{agentMinutes,sharedLayerReuse,uniqueFeatures}} JSON")
    ap.add_argument("--archive-as", default=None, metavar="vX.Y", help="기존 out을 products/history/vX.Y.json으로 보관")
    ap.add_argument("--allow-partial", action="store_true", help="심판 3명 미만이어도 병합")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    root = os.path.abspath(args.root)
    jdir = os.path.join(root, args.judging_dir)
    warnings, disagreements = [], []

    judge_files = sorted(glob.glob(os.path.join(jdir, "*.json")))
    judges = []
    for jf in judge_files:
        j = load_json(jf)
        if not isinstance(j, dict) or "judge" not in j or "scores" not in j:
            warnings.append("판정 파일 형식 불일치, 건너뜀: " + rel(root, jf))
            continue
        judges.append(j)
    judges.sort(key=lambda j: JUDGE_ORDER.index(j.get("persona")) if j.get("persona") in JUDGE_ORDER else 99)
    if len(judges) < 3 and not args.allow_partial:
        print(json.dumps({"status": "error", "error": "judges-missing", "found": [j.get("judge") for j in judges],
                          "expected": 3, "hint": "--allow-partial"}, ensure_ascii=False))
        return 1
    if not judges:
        print(json.dumps({"status": "error", "error": "no-judges", "dir": args.judging_dir}, ensure_ascii=False))
        return 1

    needs = load_json(os.path.join(root, args.needs))
    if needs is None:
        print(json.dumps({"status": "error", "error": "persona-needs-missing", "path": args.needs}, ensure_ascii=False))
        return 1
    by_code, by_product = persona_map(needs)
    build_meta = load_json(os.path.join(root, args.build_meta), {}) if args.build_meta else {}

    html_sections = {p: sections_in_html(os.path.join(root, "site", p, "index.html")) for p in PRODUCTS}
    products_out, ranking = [], []
    for prod in PRODUCTS:
        persona = by_product[prod]
        criteria = by_code.get(persona, {}).get("fitCriteria", [])
        if not criteria:
            warnings.append("{}: 페르소나 {} fitCriteria 없음".format(prod, persona))
        crit_out, met_w, tot_w, met_n, tot_n = [], 0, 0, 0, 0
        for c in criteria:
            cid, w = c.get("id"), int(c.get("weight", 1) or 1)
            votes, evid = [], {}
            for j in judges:
                for r in (j.get("criteriaMet") or {}).get(prod, []) or []:
                    if r.get("id") == cid:
                        votes.append(r.get("met"))
                        if r.get("met") is not None:
                            evid.setdefault(bool(r.get("met")), r.get("evidence") or r.get("reason") or "")
                        break
                else:
                    votes.append(None)
            met, valid, dis = majority_met(votes)
            if dis:
                disagreements.append({"product": prod, "id": cid, "votes": votes})
            if met is None:
                crit_out.append({"id": cid, "met": False, "evidence": "unverifiable — 모든 심판이 판정 불가(evidence 경로 확인)"})
                continue
            tot_n += 1
            tot_w += w
            if met:
                met_n += 1
                met_w += w
            crit_out.append({"id": cid, "met": bool(met), "evidence": evid.get(bool(met), "")})
        coverage = round(met_n / tot_n, 4) if tot_n else 0.0
        wcov = round(met_w / tot_w, 4) if tot_w else 0.0
        scores = [j["scores"].get(prod) for j in judges if isinstance(j.get("scores"), dict) and j["scores"].get(prod) is not None]
        panel = round(sum(scores) / len(scores), 2) if scores else 0.0
        if not scores:
            warnings.append("{}: 심판 점수 없음".format(prod))
        composite = round(0.5 * wcov * 10 + 0.5 * panel, 4)

        snap = load_json(os.path.join(root, "site", "data", prod + ".json"), {})
        meta = build_meta.get(prod, {}) if isinstance(build_meta, dict) else {}
        secs, lines = html_sections[prod]
        others = set().union(*(html_sections[o][0] for o in PRODUCTS if o != prod))
        unique = sorted(secs - others - COMMON_SECTIONS)
        text = {c.get("id"): c.get("criterion", "") for c in criteria}
        weight = {c.get("id"): int(c.get("weight", 1) or 1) for c in criteria}
        strengths = ["[{}] {}".format(r["id"], text.get(r["id"], "")) for r in crit_out if r["met"] and weight.get(r["id"], 0) >= 4][:6]
        gaps = ["[{}] {}".format(r["id"], text.get(r["id"], "")) for r in crit_out if not r["met"]]
        for j in judges:
            for item in j.get("mustFix", []) or []:
                if item.get("product") == prod:
                    gaps.append("[must-fix:{}] {}".format(j.get("persona"), item.get("issue", "")))
            for item in j.get("niceToHave", []) or []:
                if item.get("product") == prod:
                    gaps.append("[nice-to-have:{}] {}".format(j.get("persona"), item.get("issue", "")))

        products_out.append({
            "code": prod, "name": "Everyday People Agent — " + DISPLAY[prod], "persona": persona,
            "fitScore": {"coverage": coverage, "weightedCoverage": wcov, "panelScore": panel, "criteriaMet": crit_out},
            "sharedLayerReuse": meta.get("sharedLayerReuse", shared_reuse(snap)),
            "uniqueFeatures": meta.get("uniqueFeatures", unique),
            "buildEffort": {"agentMinutes": meta.get("agentMinutes", 0), "linesOfHtml": lines},
            "strengths": strengths, "gaps": gaps,
        })
        ranking.append({"code": prod, "composite": composite, "weightedCoverage": wcov, "panelScore": panel})

    ranking.sort(key=lambda r: (-r["composite"], PRODUCTS.index(r["code"])))
    summary, recommendation = summary_text(ranking, len(judges))
    out_doc = {
        "asOfDate": args.as_of,
        "products": products_out,
        "comparison": {"bestFit": ranking[0]["code"] if ranking else None, "summary": summary, "recommendation": recommendation,
                       "formula": "composite = 0.5 * weightedCoverage * 10 + 0.5 * panelScore", "ranking": ranking},
        "judges": [{"judge": j.get("judge"), "scores": j.get("scores"), "notes": j.get("notes", "")} for j in judges],
    }

    out_path = os.path.join(root, args.out)
    if args.dry_run:
        print(json.dumps(out_doc, ensure_ascii=False, indent=2))
        return 0
    if args.archive_as and os.path.exists(out_path):
        hist = os.path.join(root, "products", "history")
        os.makedirs(hist, exist_ok=True)
        shutil.copyfile(out_path, os.path.join(hist, args.archive_as + ".json"))
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out_doc, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(json.dumps({"status": "ok" if not warnings else "partial", "out": args.out, "bestFit": out_doc["comparison"]["bestFit"],
                      "ranking": ranking, "judges": len(judges), "disagreements": disagreements, "warnings": warnings,
                      "archived": (args.archive_as + ".json") if args.archive_as else None}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
