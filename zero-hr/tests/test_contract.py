# -*- coding: utf-8 -*-
"""test_contract.py — DATA_CONTRACT v2 §1·§2·§3 계약 테스트 + §2-7 정본 대사(정제 마스터 집계).

실행: python3 -m unittest discover -s tests -v
선행: generate_synthetic_sources.py --self-check → cleanse.py 가 data/ 아래 산출물을 만들어 두어야 한다.
"""
import csv
import datetime as dt
import json
import math
import os
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AS_OF = dt.date(2026, 9, 23)
MONTH_END = dt.date(2026, 9, 30)


def p(rel):
    return os.path.join(ROOT, rel)


def read_csv(rel, encoding="utf-8-sig"):
    with open(p(rel), encoding=encoding, newline="") as f:
        return list(csv.DictReader(f))


def header_of(rel):
    with open(p(rel), encoding="utf-8-sig", newline="") as f:
        return next(csv.reader(f))


def counter(values):
    out = {}
    for v in values:
        out[v] = out.get(v, 0) + 1
    return out


# §2-7 정본
DEPTS = [  # code, name, group, HC, OL, TO, in, out
    ("D01", "CEO Office", "Executive", 10, 0, 10, 0, 0), ("D02", "Product", "Build", 51, 3, 54, 3, 1),
    ("D03", "Engineering", "Build", 104, 6, 112, 5, 4), ("D04", "Design", "Build", 25, 1, 26, 1, 1),
    ("D05", "Data & AI", "Build", 40, 2, 34, 2, 1), ("D06", "Sales", "Go-To-Market", 58, 3, 62, 3, 3),
    ("D07", "Marketing", "Go-To-Market", 30, 1, 32, 1, 1), ("D08", "Customer Success", "Go-To-Market", 40, 3, 42, 2, 1),
    ("D09", "People", "Operations", 18, 1, 18, 1, 0), ("D10", "Finance", "Operations", 19, 1, 20, 1, 1),
    ("D11", "Legal & Compliance", "Operations", 11, 0, 12, 0, 1),
]
GROUP_ACTIVE = {"Executive": 10, "Build": 220, "Go-To-Market": 128, "Operations": 48}
EMP_TYPE_ALL = {"정규직": 354, "계약직": 31, "인턴": 19, "파견": 23}
EMP_TYPE_LEAVE = {"정규직": 19, "계약직": 2}
GENDER = {"여성": 188, "남성": 195, "미응답": 23}
AGE_BAND = {"20대": 82, "30대": 221, "40대": 83, "50대+": 20}
JOB_FAMILY = {"Engineering": 116, "Product": 55, "Design": 25, "Sales": 58, "Marketing": 30, "Customer Success": 40,
              "People": 18, "Finance": 19, "Legal": 11, "Data/AI": 24, "Executive": 10}
LEVEL = {"IC1": 33, "IC2": 65, "IC3": 82, "Senior": 89, "Lead": 55, "Manager": 44, "Director": 25, "VP": 13}
TENURE_BAND = {"1년 미만": 54, "1~3년": 151, "3~5년": 103, "5년+": 98}
TOTAL_BAND = {"0~3년": 56, "3~7년": 137, "7~12년": 142, "12년+": 71}
STAGE = {"Seed": 49, "Series A": 151, "Scale-up": 140, "Enterprise": 66}
REASONS = {"자발퇴사": 5, "계약만료": 3, "조직개편": 2, "성과/적합도": 2, "개인사유": 2}
LEVEL_ORDER = ["IC1", "IC2", "IC3", "Senior", "Lead", "Manager", "Director", "VP"]

CLEAN_HEADERS = {
    "data/clean/headcount-master.clean.csv": ["empId", "name", "gender", "birthDate", "ageBand", "orgGroupCode", "orgGroup", "deptCode",
                                              "department", "jobFamily", "level", "stage", "employmentType", "status", "leaveType",
                                              "leaveStart", "hireDate", "contractEndDate", "priorExperienceMonths", "tenureYears",
                                              "tenureYear", "tenureBand", "totalExperienceYears", "totalExperienceBand",
                                              "unresolvedFlags", "sourceRowIndex"],
    "data/clean/to-plan.clean.csv": ["deptCode", "department", "orgGroupCode", "toHeadcount", "effectiveMonth"],
    "data/clean/planned-joiners.clean.csv": ["joinerId", "name", "deptCode", "department", "jobFamily", "level", "employmentType",
                                             "gender", "birthDate", "plannedHireDate", "priorExperienceMonths", "unresolvedFlags"],
    "data/clean/planned-leavers.clean.csv": ["empId", "deptCode", "plannedTerminationDate", "separationType", "separationReason",
                                             "unresolvedFlags"],
}
RAW_HEADERS = {
    "data/raw/headcount-master.csv": ["사번", "성명", "성별", "생년월일", "소속", "직군", "레벨", "고용유형", "재직상태", "휴직유형",
                                      "휴직시작일", "입사일", "계약종료일", "입사전경력(개월)", "최종수정일"],
    "data/raw/to-plan.csv": ["조직", "정원", "기준월"],
    "data/raw/planned-joiners.csv": ["성명", "소속", "직군", "레벨", "고용유형", "성별", "생년월일", "입사예정일", "입사전경력(개월)"],
    "data/raw/planned-leavers.csv": ["사번", "성명", "소속", "퇴사예정일", "퇴직사유"],
}
DOMAINS = {
    "gender": {"여성", "남성", "미응답"}, "status": {"재직", "휴직"}, "employmentType": {"정규직", "계약직", "인턴", "파견"},
    "leaveType": {"육아휴직", "질병휴직", "기타", ""}, "level": set(LEVEL_ORDER), "stage": set(STAGE),
    "jobFamily": set(JOB_FAMILY), "ageBand": set(AGE_BAND), "tenureBand": set(TENURE_BAND), "totalExperienceBand": set(TOTAL_BAND),
}
REQUIRED = ["data/reference/org-chart.csv", "data/reference/company-stages.json", "data/raw/headcount-master.csv",
            "data/raw/injected-defects.json", "data/clean/headcount-master.clean.csv", "data/clean/cleansing-summary.json"]


def is_iso(s):
    try:
        dt.date.fromisoformat(s)
        return True
    except ValueError:
        return False


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        missing = [r for r in REQUIRED if not os.path.exists(p(r))]
        if missing:
            raise AssertionError("선행 산출물 없음(생성기 → 클린저 먼저 실행): %s" % missing)
        cls.master = read_csv("data/clean/headcount-master.clean.csv")
        cls.active = [r for r in cls.master if r["status"] == "재직"]
        cls.on_leave = [r for r in cls.master if r["status"] == "휴직"]
        cls.to_plan = read_csv("data/clean/to-plan.clean.csv")
        cls.joiners = read_csv("data/clean/planned-joiners.clean.csv")
        cls.leavers = read_csv("data/clean/planned-leavers.clean.csv")
        cls.org = read_csv("data/reference/org-chart.csv")
        with open(p("data/reference/company-stages.json"), encoding="utf-8") as f:
            cls.stages = json.load(f)["stages"]


class TestReference(Base):
    def test_org_chart_11_rows_and_columns(self):
        self.assertEqual(header_of("data/reference/org-chart.csv"),
                         ["orgGroupCode", "orgGroup", "deptCode", "department", "formerNames", "establishedOn"])
        self.assertEqual(len(self.org), 11)
        self.assertEqual([r["deptCode"] for r in self.org], [d[0] for d in DEPTS])
        self.assertEqual([r["department"] for r in self.org], [d[1] for d in DEPTS])
        self.assertEqual([r["orgGroup"] for r in self.org], [d[2] for d in DEPTS])
        by_code = dict((r["deptCode"], r) for r in self.org)
        self.assertIn("Legal and Compliance", by_code["D11"]["formerNames"].split(";"))
        self.assertIn("HR", by_code["D09"]["formerNames"].split(";"))
        self.assertEqual(len(set(r["orgGroupCode"] for r in self.org)), 4)

    def test_company_stages_contiguous(self):
        self.assertEqual([s["stage"] for s in self.stages], ["Seed", "Series A", "Scale-up", "Enterprise"])
        self.assertEqual(self.stages[0]["from"], "2019-01-01")
        self.assertEqual(self.stages[-1]["to"], "9999-12-31")
        for a, b in zip(self.stages, self.stages[1:]):
            self.assertEqual(dt.date.fromisoformat(a["to"]) + dt.timedelta(days=1), dt.date.fromisoformat(b["from"]))


class TestRawSources(Base):
    def test_raw_headers_and_row_counts(self):
        expected = {"data/raw/headcount-master.csv": 435, "data/raw/to-plan.csv": 11,
                    "data/raw/planned-joiners.csv": 27, "data/raw/planned-leavers.csv": 19}
        for rel, header in RAW_HEADERS.items():
            self.assertEqual(header_of(rel), header, rel)
            self.assertEqual(len(read_csv(rel)), expected[rel], rel)

    def test_raw_master_keeps_defects(self):
        raw = read_csv("data/raw/headcount-master.csv")
        ids = [r["사번"] for r in raw]
        self.assertEqual(len(ids) - len(set(ids)), 8, "중복 8행이 원천에 남아 있어야 한다(원천 미덮어쓰기)")
        orgs = set(r["소속"] for r in raw)
        self.assertTrue({"Legal and Compliance", "HR", "R&D", "Growth Lab", "Platform"} <= orgs)
        self.assertTrue(any("/" in r["입사일"] for r in raw))
        self.assertTrue(all(r["계약종료일"] == "" for r in raw if r["고용유형"] in ("정규직", "정규", "Regular", "FT")))

    def test_injected_defects_summary(self):
        with open(p("data/raw/injected-defects.json"), encoding="utf-8") as f:
            inj = json.load(f)
        self.assertEqual(inj["seed"], 20260923)
        m = inj["bySource"]["headcount-master"]
        self.assertEqual(m["org-old-name"] + m["org-variant"] + m["org-typo"] + m["org-whitespace"], 17)
        self.assertEqual(m["org-unknown"], 2)
        self.assertEqual(m["hire-date-format"], 31)
        self.assertEqual(m["duplicate"], 8)
        self.assertEqual(m["date-format"], 6)
        self.assertEqual(m["date-logic"], 2)
        self.assertEqual(m["status-inconsistency"], 3)
        self.assertEqual(m["missing-required"], 3)
        self.assertGreaterEqual(m["code-variant"], 30)
        self.assertEqual(inj["bySource"]["to-plan"], {"org-variant": 3, "date-format": 4})
        self.assertEqual(inj["bySource"]["planned-joiners"], {"org-variant": 2, "date-format": 3, "code-variant": 1})
        self.assertEqual(inj["bySource"]["planned-leavers"], {"date-format": 2, "reason-freetext": 6, "stale-planned-leaver": 1, "unknown-emp": 1})
        for d in inj["defects"]:
            self.assertEqual(set(d.keys()) >= {"source", "rowRef", "field", "defectType", "rawValue", "trueValue"}, True)
            self.assertIn("rowIndex", d["rowRef"])
        hire_fmt = [d for d in inj["defects"] if d["defectType"] == "hire-date-format"]
        kinds = counter("excel" if d["rawValue"].isdigit() and len(d["rawValue"]) == 5 else
                        "compact" if d["rawValue"].isdigit() else "dot" if "." in d["rawValue"] else "slash" for d in hire_fmt)
        self.assertEqual(kinds, {"slash": 20, "dot": 6, "compact": 3, "excel": 2})


class TestCleanSchema(Base):
    def test_clean_headers(self):
        for rel, header in CLEAN_HEADERS.items():
            self.assertEqual(header_of(rel), header, rel)

    def test_master_domains_and_keys(self):
        self.assertEqual(len(self.master), 427)
        self.assertEqual(len(set(r["empId"] for r in self.master)), 427)
        for r in self.master:
            self.assertRegex(r["empId"], r"^E\d{4}$")
            for col, dom in DOMAINS.items():
                self.assertIn(r[col], dom, "%s %s=%r" % (r["empId"], col, r[col]))
            self.assertTrue(is_iso(r["birthDate"]) and is_iso(r["hireDate"]), r["empId"])
            for col in ("leaveStart", "contractEndDate"):
                self.assertTrue(r[col] == "" or is_iso(r[col]), (r["empId"], col, r[col]))
            self.assertEqual(r["status"] == "휴직", r["leaveType"] != "", r["empId"])
            self.assertTrue(r["priorExperienceMonths"].isdigit())
            self.assertEqual(int(r["tenureYear"]), int(math.floor(float(r["tenureYears"]))) + 1)
            self.assertAlmostEqual(float(r["totalExperienceYears"]),
                                   round(int(r["priorExperienceMonths"]) / 12.0 + float(r["tenureYears"]), 2), places=2)
            self.assertTrue(r["sourceRowIndex"].isdigit())
        for r in self.master:
            if r["employmentType"] == "정규직":
                self.assertEqual(r["contractEndDate"], "", r["empId"])

    def test_org_fields_consistent_with_org_chart(self):
        by_code = dict((r["deptCode"], r) for r in self.org)
        for r in self.master + self.to_plan + self.joiners:
            ref = by_code[r["deptCode"]]
            self.assertEqual(r["department"], ref["department"])
            for col in ("orgGroupCode", "orgGroup"):  # §3-3 입사 예정자에는 없는 컬럼
                if col in r:
                    self.assertEqual(r[col], ref[col])

    def test_to_plan_clean(self):
        self.assertEqual(len(self.to_plan), 11)
        self.assertEqual(dict((r["deptCode"], int(r["toHeadcount"])) for r in self.to_plan), dict((d[0], d[5]) for d in DEPTS))
        self.assertEqual(sum(int(r["toHeadcount"]) for r in self.to_plan), 422)
        self.assertTrue(all(r["effectiveMonth"] == "2026-09" for r in self.to_plan))

    def test_joiners_clean(self):
        self.assertEqual(len(self.joiners), 27)
        self.assertEqual([r["joinerId"] for r in self.joiners], ["J%03d" % i for i in range(1, 28)])
        for r in self.joiners:
            self.assertTrue(is_iso(r["plannedHireDate"]) and is_iso(r["birthDate"]))
            self.assertIn(r["gender"], DOMAINS["gender"])
            self.assertIn(r["employmentType"], DOMAINS["employmentType"])
            self.assertIn(r["level"], DOMAINS["level"])
            self.assertIn(r["jobFamily"], DOMAINS["jobFamily"])

    def test_leavers_clean(self):
        self.assertEqual(len(self.leavers), 19)
        for r in self.leavers:
            self.assertTrue(is_iso(r["plannedTerminationDate"]))
            self.assertIn(r["separationReason"], {"자발퇴사", "개인사유", "계약만료", "조직개편", "성과/적합도", "건강", "정년"})
            self.assertIn(r["separationType"], {"자발적", "비자발적"})
            expected = "자발적" if r["separationReason"] in ("자발퇴사", "개인사유", "건강") else "비자발적"
            self.assertEqual(r["separationType"], expected)


class TestReconciliation(Base):
    """정제 마스터·TO·입퇴사 예정을 독립 집계해 §2-7 정본과 대조한다."""

    def test_headcount_totals(self):
        self.assertEqual(len(self.active), 406)
        self.assertEqual(len(self.on_leave), 21)

    def test_by_department(self):
        for code, _n, _g, hc, ol, _to, _i, _o in DEPTS:
            self.assertEqual(sum(1 for r in self.active if r["deptCode"] == code), hc, "%s HC" % code)
            self.assertEqual(sum(1 for r in self.on_leave if r["deptCode"] == code), ol, "%s OL" % code)

    def test_by_org_group(self):
        self.assertEqual(counter(r["orgGroup"] for r in self.active), GROUP_ACTIVE)

    def test_employment_type_on_427(self):
        self.assertEqual(counter(r["employmentType"] for r in self.master), EMP_TYPE_ALL)
        self.assertEqual(counter(r["employmentType"] for r in self.on_leave), EMP_TYPE_LEAVE)

    def test_attribute_distributions_on_active_406(self):
        self.assertEqual(counter(r["gender"] for r in self.active), GENDER)
        self.assertEqual(counter(r["ageBand"] for r in self.active), AGE_BAND)
        self.assertEqual(counter(r["jobFamily"] for r in self.active), JOB_FAMILY)
        self.assertEqual(counter(r["level"] for r in self.active), LEVEL)
        self.assertEqual(counter(r["tenureBand"] for r in self.active), TENURE_BAND)
        self.assertEqual(counter(r["totalExperienceBand"] for r in self.active), TOTAL_BAND)
        self.assertEqual(counter(r["stage"] for r in self.active), STAGE)

    def test_derived_fields_recomputed(self):
        """ageBand·tenureBand·totalExperienceBand·stage 가 §2-8 공식으로 재계산해도 같다."""
        for r in self.active:
            birth = dt.date.fromisoformat(r["birthDate"])
            age = AS_OF.year - birth.year - (1 if (AS_OF.month, AS_OF.day) < (birth.month, birth.day) else 0)
            band = "20대" if age < 30 else "30대" if age < 40 else "40대" if age < 50 else "50대+"
            self.assertEqual(r["ageBand"], band, r["empId"])
            hire = dt.date.fromisoformat(r["hireDate"])
            t = 0.0 if hire > AS_OF else round((AS_OF - hire).days / 365.25, 2)
            self.assertEqual(float(r["tenureYears"]), t, r["empId"])
            self.assertEqual(r["tenureBand"], "1년 미만" if t < 1 else "1~3년" if t < 3 else "3~5년" if t < 5 else "5년+")
            x = float(r["totalExperienceYears"])
            self.assertEqual(r["totalExperienceBand"], "0~3년" if x < 3 else "3~7년" if x < 7 else "7~12년" if x < 12 else "12년+")
            stage = [s["stage"] for s in self.stages if s["from"] <= r["hireDate"] <= s["to"]]
            self.assertEqual(r["stage"], stage[0] if stage else "Enterprise", r["empId"])

    def test_job_family_vs_department(self):
        d05 = [r for r in self.active if r["deptCode"] == "D05"]
        self.assertEqual(counter(r["jobFamily"] for r in d05), {"Data/AI": 24, "Engineering": 12, "Product": 4})
        own = {"D01": "Executive", "D02": "Product", "D03": "Engineering", "D04": "Design", "D06": "Sales", "D07": "Marketing",
               "D08": "Customer Success", "D09": "People", "D10": "Finance", "D11": "Legal"}
        for code, fam in own.items():
            self.assertTrue(all(r["jobFamily"] == fam for r in self.active if r["deptCode"] == code), code)

    def test_level_constraints_and_tenure_correlation(self):
        for code, _n, _g, hc, _ol, _to, _i, _o in DEPTS:
            members = [r for r in self.active if r["deptCode"] == code]
            vps = sum(1 for r in members if r["level"] == "VP")
            if code == "D01":
                self.assertEqual(vps, 3)
            else:
                self.assertGreaterEqual(vps, 1, code)
            if hc >= 18:
                self.assertGreaterEqual(sum(1 for r in members if r["level"] == "Director"), 1, code)
        ranks = [LEVEL_ORDER.index(r["level"]) for r in self.active]
        tenures = [float(r["tenureYears"]) for r in self.active]
        n = len(ranks)
        mx, my = sum(ranks) / n, sum(tenures) / n
        cov = sum((a - mx) * (b - my) for a, b in zip(ranks, tenures))
        den = math.sqrt(sum((a - mx) ** 2 for a in ranks)) * math.sqrt(sum((b - my) ** 2 for b in tenures))
        self.assertGreater(cov / den, 0.3, "레벨-재직기간 상관")
        mean_by_level = [sum(t for r, t in zip(self.active, tenures) if r["level"] == lv) / max(1, sum(1 for r in self.active if r["level"] == lv))
                         for lv in LEVEL_ORDER]
        self.assertLess(mean_by_level[0], mean_by_level[-1])

    def test_contract_end_within_90_days(self):
        win = [r for r in self.master if r["contractEndDate"] and AS_OF <= dt.date.fromisoformat(r["contractEndDate"]) <= AS_OF + dt.timedelta(days=90)]
        self.assertGreaterEqual(len(win), 8)

    def test_planned_joiners_by_department(self):
        cur = [r for r in self.joiners if AS_OF < dt.date.fromisoformat(r["plannedHireDate"]) <= MONTH_END]
        nxt = [r for r in self.joiners if dt.date(2026, 10, 1) <= dt.date.fromisoformat(r["plannedHireDate"]) <= dt.date(2026, 10, 31)]
        self.assertEqual(len(cur), 19)
        self.assertEqual(len(nxt), 8)
        self.assertEqual(counter(r["deptCode"] for r in cur), dict((d[0], d[6]) for d in DEPTS if d[6]))
        self.assertEqual(counter(r["deptCode"] for r in nxt), {"D03": 3, "D05": 2, "D06": 2, "D02": 1})

    def test_planned_leavers_by_department_and_reason(self):
        ids = dict((r["empId"], r) for r in self.master)
        unknown = [r for r in self.leavers if r["empId"] not in ids]
        self.assertEqual(len(unknown), 1)
        self.assertIn("unknown-emp", unknown[0]["unresolvedFlags"])
        known = [r for r in self.leavers if r["empId"] in ids]
        valid = [r for r in known if dt.date.fromisoformat(r["plannedTerminationDate"]) <= MONTH_END]
        octo = [r for r in known if dt.date(2026, 10, 1) <= dt.date.fromisoformat(r["plannedTerminationDate"]) <= dt.date(2026, 10, 31)]
        self.assertEqual(len(valid), 14)
        self.assertEqual(len(octo), 4)
        self.assertEqual(counter(r["deptCode"] for r in valid), dict((d[0], d[7]) for d in DEPTS if d[7]))
        self.assertEqual(counter(r["deptCode"] for r in octo), {"D03": 1, "D06": 1, "D08": 1, "D07": 1})
        self.assertEqual(counter(r["separationReason"] for r in valid), REASONS)
        for r in valid:
            self.assertEqual(r["deptCode"], ids[r["empId"]]["deptCode"])
            self.assertEqual(ids[r["empId"]]["status"], "재직")
            if r["separationReason"] == "계약만료":
                self.assertIn(ids[r["empId"]]["employmentType"], ("계약직", "인턴", "파견"))
        stale = [r for r in valid if dt.date.fromisoformat(r["plannedTerminationDate"]) < AS_OF]
        self.assertEqual(len(stale), 1)
        self.assertEqual(stale[0]["plannedTerminationDate"], "2026-09-15")
        self.assertIn("stale-planned-leaver", stale[0]["unresolvedFlags"])

    def test_executive_snapshot(self):
        active = len(self.active)
        to = sum(int(r["toHeadcount"]) for r in self.to_plan)
        ids = set(r["empId"] for r in self.master)
        planned_in = sum(1 for r in self.joiners if AS_OF < dt.date.fromisoformat(r["plannedHireDate"]) <= MONTH_END)
        planned_out = sum(1 for r in self.leavers if r["empId"] in ids and dt.date.fromisoformat(r["plannedTerminationDate"]) <= MONTH_END)
        self.assertEqual((active, len(self.on_leave), to, active - to, planned_in, planned_out), (406, 21, 422, -16, 19, 14))
        self.assertEqual(active + planned_in - planned_out, 411)
        self.assertEqual(active + planned_in - planned_out - to, -11)
        to_by = dict((r["deptCode"], int(r["toHeadcount"])) for r in self.to_plan)
        for code, _n, _g, hc, _ol, to_d, inn, out in DEPTS:
            me = hc + inn - out
            gap = me - to_d
            rec = "채용 가속" if gap <= -4 else "TO 재검토/이동배치" if gap >= 5 else "정상 관리"
            self.assertEqual(to_by[code], to_d)
            expected_rec = {"D03": "채용 가속", "D06": "채용 가속", "D05": "TO 재검토/이동배치"}.get(code, "정상 관리")
            self.assertEqual(rec, expected_rec, code)


if __name__ == "__main__":
    unittest.main()
