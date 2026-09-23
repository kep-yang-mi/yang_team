# -*- coding: utf-8 -*-
"""test_cleansing.py — §14: 주입 결함 정답지 ↔ 클린징 로그 대사(재현율 ≥ 0.97), 미해결 플래그, 요약 수치, 결정성.

실행: python3 -m unittest discover -s tests -v
"""
import csv
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GEN = os.path.join(ROOT, ".claude/skills/people-data-integration/scripts/generate_synthetic_sources.py")
CLEANSE = os.path.join(ROOT, ".claude/skills/people-data-cleansing/scripts/cleanse.py")
RULES = {"org-old-name", "org-variant", "org-typo", "org-whitespace", "org-unknown", "hire-date-format", "date-format",
         "date-logic", "status-inconsistency", "missing-required", "duplicate", "code-variant", "reason-freetext",
         "stale-planned-leaver", "unknown-emp"}
UNRESOLVED_RULES = {"org-unknown", "date-logic", "status-inconsistency", "missing-required", "stale-planned-leaver", "unknown-emp"}
RAW_FILES = ["data/raw/headcount-master.csv", "data/raw/to-plan.csv", "data/raw/planned-joiners.csv", "data/raw/planned-leavers.csv",
             "data/raw/injected-defects.json", "data/reference/org-chart.csv", "data/reference/company-stages.json"]
CLEAN_FILES = ["data/clean/headcount-master.clean.csv", "data/clean/to-plan.clean.csv", "data/clean/planned-joiners.clean.csv",
               "data/clean/planned-leavers.clean.csv", "data/clean/cleansing-log.jsonl", "data/clean/cleansing-summary.json"]


def p(rel, root=ROOT):
    return os.path.join(root, rel)


def read_csv(rel):
    with open(p(rel), encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def sha(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def ref_key(source, row_ref, field):
    return (source, int(row_ref["rowIndex"]), field)


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        for rel in ["data/raw/injected-defects.json", "data/clean/cleansing-log.jsonl", "data/clean/cleansing-summary.json"]:
            if not os.path.exists(p(rel)):
                raise AssertionError("선행 산출물 없음(생성기 → 클린저 먼저 실행): %s" % rel)
        with open(p("data/raw/injected-defects.json"), encoding="utf-8") as f:
            cls.injected = json.load(f)
        with open(p("data/clean/cleansing-log.jsonl"), encoding="utf-8") as f:
            cls.log = [json.loads(line) for line in f if line.strip()]
        with open(p("data/clean/cleansing-summary.json"), encoding="utf-8") as f:
            cls.summary = json.load(f)
        cls.log_by_ref = {}
        for e in cls.log:
            cls.log_by_ref.setdefault(ref_key(e["source"], e["rowRef"], e["field"]), []).append(e)
        cls.master = read_csv("data/clean/headcount-master.clean.csv")
        cls.leavers = read_csv("data/clean/planned-leavers.clean.csv")


class TestLogSchema(Base):
    def test_log_entry_shape_and_rule_vocabulary(self):
        self.assertGreater(len(self.log), 0)
        for e in self.log:
            self.assertEqual(set(e.keys()), {"source", "rowRef", "field", "rawValue", "correctedValue", "rule", "confidence", "unresolved"})
            self.assertIn(e["rule"], RULES, e)
            self.assertIn("사번", e["rowRef"])
            self.assertIn("rowIndex", e["rowRef"])
            self.assertIn(e["source"], {"headcount-master", "to-plan", "planned-joiners", "planned-leavers"})
            self.assertIsInstance(e["unresolved"], bool)
            self.assertEqual(e["unresolved"], e["rule"] in UNRESOLVED_RULES, e)
            if e["confidence"] is not None:
                self.assertTrue(0.0 <= e["confidence"] <= 1.0)

    def test_defect_type_vocabulary_equals_rule_vocabulary(self):
        types = set(d["defectType"] for d in self.injected["defects"])
        self.assertTrue(types <= RULES, types - RULES)


class TestRecall(Base):
    def test_recall_of_injected_defects(self):
        defects = self.injected["defects"]
        hits = [d for d in defects if ref_key(d["source"], d["rowRef"], d["field"]) in self.log_by_ref]
        recall = len(hits) / float(len(defects))
        missed = [d for d in defects if d not in hits]
        self.assertGreaterEqual(recall, 0.97, "재현율 %.4f, 누락 %s" % (recall, missed[:5]))

    def test_rule_agreement_and_value_agreement(self):
        """같은 rowRef+field 에서 rule = defectType, correctedValue = trueValue(해결 건)."""
        rule_ok = val_ok = val_n = 0
        for d in self.injected["defects"]:
            es = self.log_by_ref.get(ref_key(d["source"], d["rowRef"], d["field"]), [])
            if not es:
                continue
            if any(e["rule"] == d["defectType"] for e in es):
                rule_ok += 1
            if d["trueValue"] != "(unresolved)":
                val_n += 1
                if any(str(e["correctedValue"]) == str(d["trueValue"]) for e in es):
                    val_ok += 1
        n = len(self.injected["defects"])
        self.assertGreaterEqual(rule_ok / float(n), 0.95, "rule 일치율")
        self.assertGreaterEqual(val_ok / float(val_n), 0.97, "correctedValue 일치율")

    def test_no_spurious_corrections(self):
        """정답지에 없는 보정은 없어야 한다(원천에 주입 외 노이즈가 없으므로 로그 = 정답지)."""
        injected_keys = set(ref_key(d["source"], d["rowRef"], d["field"]) for d in self.injected["defects"])
        extra = [e for e in self.log if ref_key(e["source"], e["rowRef"], e["field"]) not in injected_keys]
        self.assertLessEqual(len(extra), max(3, int(0.03 * len(self.log))), extra[:5])


class TestUnresolved(Base):
    def test_unresolved_flags_in_master(self):
        flagged = {}
        for r in self.master:
            for fl in [x for x in r["unresolvedFlags"].split(";") if x]:
                flagged.setdefault(fl, []).append(r)
        self.assertEqual(len(flagged.get("org-unknown", [])), 2)
        self.assertEqual(len(flagged.get("date-logic", [])), 2)
        self.assertEqual(len(flagged.get("status-inconsistency", [])), 3)
        self.assertEqual(len(flagged.get("missing-required", [])), 3)
        for r in flagged["date-logic"]:
            self.assertEqual(r["tenureYears"], "0.00")
            self.assertEqual(r["tenureBand"], "1년 미만")
            self.assertGreater(r["hireDate"], "2026-09-23")
        for r in flagged["status-inconsistency"]:
            self.assertEqual((r["status"], r["leaveType"]), ("휴직", "기타"))
        for r in flagged["missing-required"]:
            self.assertIn(r["employmentType"], ("계약직", "인턴", "파견"))
            self.assertEqual(r["contractEndDate"], "")
        for r in flagged["org-unknown"]:
            self.assertEqual(r["deptCode"], {"Marketing": "D07", "Engineering": "D03"}[r["jobFamily"]])

    def test_unresolved_flags_in_leavers(self):
        stale = [r for r in self.leavers if "stale-planned-leaver" in r["unresolvedFlags"]]
        unknown = [r for r in self.leavers if "unknown-emp" in r["unresolvedFlags"]]
        self.assertEqual(len(stale), 1)
        self.assertEqual(len(unknown), 1)
        self.assertEqual(unknown[0]["empId"], "E9999")

    def test_unresolved_items_in_summary_have_questions(self):
        self.assertEqual(self.summary["unresolvedCount"], len(self.summary["unresolvedItems"]))
        self.assertEqual(self.summary["unresolvedCount"], 12)
        for item in self.summary["unresolvedItems"]:
            self.assertTrue(item["question"])
            self.assertIn(item["flag"], UNRESOLVED_RULES)


class TestSummary(Base):
    def test_summary_counts(self):
        s = self.summary
        self.assertEqual(s["asOfDate"], "2026-09-23")
        self.assertEqual(s["rowsIn"], {"headcount-master": 435, "to-plan": 11, "planned-joiners": 27, "planned-leavers": 19})
        self.assertEqual(s["rowsOut"], {"headcount-master": 427, "to-plan": 11, "planned-joiners": 27, "planned-leavers": 19})
        self.assertEqual(s["duplicatesRemoved"], 8)
        self.assertEqual(s["orgNameCorrections"], 17)
        self.assertEqual(s["hireDateCorrections"], 31)
        self.assertEqual(s["correctionsByRule"]["duplicate"], 8)
        self.assertEqual(s["correctionsByRule"]["hire-date-format"], 31)
        self.assertGreaterEqual(s["correctionsByRule"]["code-variant"], 30)
        self.assertEqual(s["orgGroupMapping"]["D01"], "Executive")
        self.assertEqual(s["orgGroupMapping"]["D11"], "Operations")
        self.assertTrue({"ageBand", "tenureBand", "totalExperienceBand", "stage"} <= set(s["derivedFields"]))
        self.assertEqual(s["warnings"], [])

    def test_summary_matches_log(self):
        by_rule = {}
        for e in self.log:
            by_rule[e["rule"]] = by_rule.get(e["rule"], 0) + 1
        self.assertEqual(self.summary["correctionsByRule"], by_rule)
        master = [e for e in self.log if e["source"] == "headcount-master"]
        self.assertEqual(sum(1 for e in master if e["rule"] in ("org-old-name", "org-variant", "org-typo", "org-whitespace")), 17)
        self.assertEqual(sum(1 for e in master if e["rule"] == "hire-date-format"), 31)

    def test_dedup_keeps_latest_modified_row(self):
        raw = read_csv("data/raw/headcount-master.csv")
        kept = dict((r["empId"], int(r["sourceRowIndex"])) for r in self.master)
        for e in [x for x in self.log if x["rule"] == "duplicate"]:
            emp_id = e["rowRef"]["사번"]
            removed = raw[e["rowRef"]["rowIndex"]]
            survivor = raw[kept[emp_id]]
            self.assertEqual(int(e["correctedValue"]), kept[emp_id])
            self.assertEqual(removed["사번"], emp_id)
            self.assertLessEqual(removed["최종수정일"], survivor["최종수정일"])


class TestDeterminism(unittest.TestCase):
    def test_generator_and_cleanser_are_deterministic(self):
        """임시 루트에서 생성기+클린저를 다시 돌려 data/ 와 바이트 단위로 같은지 본다(원천은 덮어쓰지 않았음을 함께 증명)."""
        tmp = tempfile.mkdtemp(prefix="zerohr-det-")
        try:
            r1 = subprocess.run([sys.executable, GEN, "--root", tmp, "--as-of", "2026-09-23", "--self-check"],
                                capture_output=True, text=True, check=False)
            self.assertEqual(r1.returncode, 0, r1.stdout[-800:] + r1.stderr[-800:])
            self.assertEqual(json.loads(r1.stdout.strip().splitlines()[-1])["status"], "ok")
            r2 = subprocess.run([sys.executable, CLEANSE, "--root", tmp, "--as-of", "2026-09-23"],
                                capture_output=True, text=True, check=False)
            self.assertEqual(r2.returncode, 0, r2.stdout[-800:] + r2.stderr[-800:])
            self.assertEqual(json.loads(r2.stdout.strip().splitlines()[-1])["status"], "ok")
            for rel in RAW_FILES + CLEAN_FILES:
                self.assertEqual(sha(p(rel, tmp)), sha(p(rel)), "비결정적 산출물: %s" % rel)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
