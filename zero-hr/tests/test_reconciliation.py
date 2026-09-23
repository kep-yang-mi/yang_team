# -*- coding: utf-8 -*-
"""test_reconciliation.py — DATA_CONTRACT v2 §14: §2-7 정본 수치가 공통 데이터 계층 전 산출물에서 일치하는지 대사.

필수: data/stats/headcount-stats.json · month-end-forecast.json (없으면 실패 — 통계·예측 단계 선행 필요)
선택: payroll-close.json · onboarding-plan.json · site/data/*.json · reports/org-forecast-2026-09.csv (없으면 skip)
루트는 환경변수 ZERO_HR_ROOT 로 바꿀 수 있다(픽스처 검증용).
실행: python3 -m unittest tests.test_reconciliation -v
"""
import csv
import json
import os
import unittest

ROOT = os.environ.get("ZERO_HR_ROOT", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
REC_HIRE, REC_REVIEW, REC_NORMAL = "채용 가속", "TO 재검토/이동배치", "정상 관리"

# §2-7 조직표: deptCode → (department, orgGroup, HC, OL, TO, in, out, ME, gapAsOf, gapME, recommendation)
DEPT_TABLE = {
    "D01": ("CEO Office", "Executive", 10, 0, 10, 0, 0, 10, 0, 0, REC_NORMAL),
    "D02": ("Product", "Build", 51, 3, 54, 3, 1, 53, -3, -1, REC_NORMAL),
    "D03": ("Engineering", "Build", 104, 6, 112, 5, 4, 105, -8, -7, REC_HIRE),
    "D04": ("Design", "Build", 25, 1, 26, 1, 1, 25, -1, -1, REC_NORMAL),
    "D05": ("Data & AI", "Build", 40, 2, 34, 2, 1, 41, 6, 7, REC_REVIEW),
    "D06": ("Sales", "Go-To-Market", 58, 3, 62, 3, 3, 58, -4, -4, REC_HIRE),
    "D07": ("Marketing", "Go-To-Market", 30, 1, 32, 1, 1, 30, -2, -2, REC_NORMAL),
    "D08": ("Customer Success", "Go-To-Market", 40, 3, 42, 2, 1, 41, -2, -1, REC_NORMAL),
    "D09": ("People", "Operations", 18, 1, 18, 1, 0, 19, 0, 1, REC_NORMAL),
    "D10": ("Finance", "Operations", 19, 1, 20, 1, 1, 19, -1, -1, REC_NORMAL),
    "D11": ("Legal & Compliance", "Operations", 11, 0, 12, 0, 1, 10, -1, -2, REC_NORMAL),
}
ORG_GROUP_ACTIVE = {"Executive": 10, "Build": 220, "Go-To-Market": 128, "Operations": 48}
SNAPSHOT = {"activeHeadcount": 406, "onLeave": 21, "toHeadcount": 422, "toGapAsOf": -16,
            "plannedIn": 19, "plannedOut": 14, "forecastMonthEnd": 411, "toGapMonthEnd": -11}
NEXT_MONTH = {"plannedIn": 8, "plannedOut": 4, "forecastNextMonthEnd": 415, "toGapNextMonthEnd": -7}
ATTRIBUTES = {
    "gender": {"여성": 188, "남성": 195, "미응답": 23},
    "ageBand": {"20대": 82, "30대": 221, "40대": 83, "50대+": 20},
    "jobFamily": {"Engineering": 116, "Product": 55, "Design": 25, "Sales": 58, "Marketing": 30, "Customer Success": 40,
                  "People": 18, "Finance": 19, "Legal": 11, "Data/AI": 24, "Executive": 10},
    "level": {"IC1": 33, "IC2": 65, "IC3": 82, "Senior": 89, "Lead": 55, "Manager": 44, "Director": 25, "VP": 13},
    "tenureBand": {"1년 미만": 54, "1~3년": 151, "3~5년": 103, "5년+": 98},
    "totalExperienceBand": {"0~3년": 56, "3~7년": 137, "7~12년": 142, "12년+": 71},
    "stage": {"Seed": 49, "Series A": 151, "Scale-up": 140, "Enterprise": 66},
}
EMPLOYMENT_TYPE_ALL = {"정규직": 354, "계약직": 31, "인턴": 19, "파견": 23}
SEPARATION_REASONS = {"자발퇴사": 5, "계약만료": 3, "조직개편": 2, "성과/적합도": 2, "개인사유": 2}
ONBOARDING_JOINERS_TOTAL = 27


def path(rel):
    return os.path.join(ROOT, rel)


def load(rel):
    with open(path(rel), encoding="utf-8") as f:
        return json.load(f)


def load_optional(rel):
    return load(rel) if os.path.exists(path(rel)) else None


def by_code(rows):
    return dict((r["deptCode"], r) for r in rows)


class TestHeadcountStats(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.stats = load("data/stats/headcount-stats.json")

    def test_executive_snapshot_totals(self):
        t = self.stats["totals"]
        self.assertEqual(t["activeHeadcount"], SNAPSHOT["activeHeadcount"])
        self.assertEqual(t["onLeave"], SNAPSHOT["onLeave"])
        self.assertEqual(t["headcount"], SNAPSHOT["activeHeadcount"] + SNAPSHOT["onLeave"])
        self.assertEqual(t["toHeadcount"], SNAPSHOT["toHeadcount"])
        self.assertEqual(t["toGapAsOf"], SNAPSHOT["toGapAsOf"])
        self.assertEqual(t["plannedIn"], SNAPSHOT["plannedIn"])
        self.assertEqual(t["plannedOut"], SNAPSHOT["plannedOut"])

    def test_department_table_hc_ol_to(self):
        rows = by_code(self.stats["byDepartment"])
        self.assertEqual(sorted(rows), sorted(DEPT_TABLE))
        for code, exp in DEPT_TABLE.items():
            with self.subTest(deptCode=code):
                r = rows[code]
                self.assertEqual((r["department"], r["orgGroup"]), (exp[0], exp[1]))
                self.assertEqual((r["activeHeadcount"], r["onLeave"], r["toHeadcount"], r["toGapAsOf"]), (exp[2], exp[3], exp[4], exp[8]))
                self.assertEqual(r["headcount"], exp[2] + exp[3])

    def test_org_groups(self):
        groups = dict((g["orgGroup"], g["activeHeadcount"]) for g in self.stats["byOrgGroup"])
        self.assertEqual(groups, ORG_GROUP_ACTIVE)

    def test_attribute_distributions(self):
        for key, exp in ATTRIBUTES.items():
            with self.subTest(attribute=key):
                self.assertEqual(dict(self.stats["byAttribute"][key]), exp)
                self.assertEqual(sum(exp.values()), SNAPSHOT["activeHeadcount"])
        self.assertEqual(dict(self.stats["byAttributeAll"]["employmentType"]), EMPLOYMENT_TYPE_ALL)
        self.assertEqual(sum(self.stats["byAttribute"]["employmentType"].values()), SNAPSHOT["activeHeadcount"])

    def test_cross_tabs_sum_to_active(self):
        for name, table in self.stats["crossTabs"].items():
            with self.subTest(crossTab=name):
                self.assertEqual(sum(sum(r.values()) for r in table.values()), SNAPSHOT["activeHeadcount"])

    def test_planned_separations(self):
        ps = self.stats["plannedSeparations"]
        self.assertEqual(ps["total"], SNAPSHOT["plannedOut"])
        self.assertEqual(dict(ps["bySeparationReason"]), SEPARATION_REASONS)
        self.assertEqual(ps["byMonth"].get("2026-09"), 14)
        self.assertEqual(ps["byMonth"].get("2026-10"), 4)


class TestMonthEndForecast(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fc = load("data/stats/month-end-forecast.json")
        cls.stats = load("data/stats/headcount-stats.json")

    def test_executive_snapshot_totals(self):
        t = self.fc["totals"]
        for k, v in SNAPSHOT.items():
            if k != "onLeave":
                with self.subTest(field=k):
                    self.assertEqual(t[k], v)
        self.assertEqual(t["toFillRate"], round(411 / 422.0, 4))
        self.assertEqual(dict(t["nextMonth"]), NEXT_MONTH)

    def test_department_table(self):
        rows = by_code(self.fc["byDepartment"])
        self.assertEqual(sorted(rows), sorted(DEPT_TABLE))
        for code, exp in DEPT_TABLE.items():
            with self.subTest(deptCode=code):
                r = rows[code]
                self.assertEqual(r["department"], exp[0])
                self.assertEqual(r["orgGroup"], exp[1])
                self.assertEqual(r["activeHeadcount"], exp[2], "HC")
                self.assertEqual(r["toHeadcount"], exp[4], "TO")
                self.assertEqual(r["plannedIn"], exp[5], "in")
                self.assertEqual(r["plannedOut"], exp[6], "out")
                self.assertEqual(r["forecastMonthEnd"], exp[7], "ME")
                self.assertEqual(r["toGapAsOf"], exp[8], "gapAsOf")
                self.assertEqual(r["toGapMonthEnd"], exp[9], "gapME")
                self.assertEqual(r["recommendation"], exp[10])

    def test_stats_and_forecast_agree(self):
        s, f = by_code(self.stats["byDepartment"]), by_code(self.fc["byDepartment"])
        for code in DEPT_TABLE:
            self.assertEqual((s[code]["activeHeadcount"], s[code]["toHeadcount"]), (f[code]["activeHeadcount"], f[code]["toHeadcount"]))
        self.assertEqual(self.stats["totals"]["activeHeadcount"], self.fc["totals"]["activeHeadcount"])

    def test_insights_and_actions(self):
        types = dict((i["type"], i) for i in self.fc["insights"])
        self.assertEqual(types["채용 가속 필요"]["codes"], ["D03", "D06"])
        self.assertEqual(types["TO 재검토 필요"]["codes"], ["D05"])
        self.assertEqual(types["퇴사 영향 점검"]["codes"], ["D11"])
        self.assertEqual(len(self.fc["immediateActions"]), 3)

    def test_planned_lists_are_pii_free(self):
        for j in self.fc["plannedJoiners"]:
            self.assertNotIn("name", j)
            self.assertNotIn("birthDate", j)
        for lv in self.fc["plannedLeavers"]:
            self.assertNotIn("name", lv)
        self.assertEqual(len(self.fc["plannedJoiners"]), 27)
        self.assertEqual(len(self.fc["plannedLeavers"]), 18)


class TestDownstream(unittest.TestCase):
    def test_payroll_close(self):
        p = load_optional("data/stats/payroll-close.json")
        if p is None:
            self.skipTest("payroll-close.json 없음 — payroll-close-analyst 미실행")
        hc = p["payrollHeadcount"]
        self.assertEqual(hc["monthEndActive"], SNAPSHOT["forecastMonthEnd"])
        self.assertEqual(hc["asOfActive"], SNAPSHOT["activeHeadcount"])
        self.assertEqual(hc["asOfOnLeave"], SNAPSHOT["onLeave"])

    def test_onboarding_plan(self):
        o = load_optional("data/stats/onboarding-plan.json")
        if o is None:
            self.skipTest("onboarding-plan.json 없음 — onboarding-plan-analyst 미실행")
        self.assertEqual(sum(len(w["joiners"]) for w in o["timeline"]), ONBOARDING_JOINERS_TOTAL)

    def test_site_snapshots(self):
        checked = 0
        insight = load_optional("site/data/insight.json") or load_optional("site/data/app.json")
        if insight is not None:
            self.assertEqual(insight["stats"]["totals"]["activeHeadcount"], SNAPSHOT["activeHeadcount"])
            self.assertEqual(insight["forecast"]["totals"]["forecastMonthEnd"], SNAPSHOT["forecastMonthEnd"])
            self.assertEqual(insight["forecast"]["totals"]["toGapMonthEnd"], SNAPSHOT["toGapMonthEnd"])
            checked += 1
        payroll = load_optional("site/data/payroll.json")
        if payroll is not None:
            self.assertEqual(payroll["payrollClose"]["payrollHeadcount"]["monthEndActive"], SNAPSHOT["forecastMonthEnd"])
            checked += 1
        onboard = load_optional("site/data/onboard.json")
        if onboard is not None:
            self.assertEqual(sum(len(w["joiners"]) for w in onboard["onboardingPlan"]["timeline"]), ONBOARDING_JOINERS_TOTAL)
            checked += 1
        if not checked:
            self.skipTest("site/data/*.json 없음 — product-builder 미실행")

    def test_org_forecast_csv(self):
        rel = "reports/org-forecast-2026-09.csv"
        if not os.path.exists(path(rel)):
            self.skipTest(rel + " 없음 — monthly-report 미실행")
        with open(path(rel), encoding="utf-8", newline="") as f:
            rows = list(csv.DictReader(f))
        self.assertEqual(len(rows), 11)
        for r in rows:
            exp = DEPT_TABLE[r["deptCode"]]
            self.assertEqual((int(r["forecastMonthEnd"]), int(r["toGapMonthEnd"]), r["recommendation"]), (exp[7], exp[9], exp[10]))


if __name__ == "__main__":
    unittest.main()
