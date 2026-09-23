# -*- coding: utf-8 -*-
"""test_logic_risks.py — 외부 독립 검증(validation-summary.md)에서 지적된 논리 위험 4건 + 행별 항등식을 고정한다 (DR-004).

같은 숫자가 여러 JSON에 복사되어 있는 것은 대사 증거가 아니므로, 이 테스트는 **정제 CSV에서 독립 재집계**해 JSON과 대조한다.
"""
import csv
import json
import os
import unittest
from collections import Counter
from datetime import date

ROOT = os.environ.get("ZERO_HR_ROOT") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AS_OF = date(2026, 9, 23)
MONTH_END = date(2026, 9, 30)


def read_csv(rel):
    path = os.path.join(ROOT, rel)
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def read_json(rel):
    path = os.path.join(ROOT, rel)
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


class TestLeaverLogic(unittest.TestCase):
    def setUp(self):
        self.master = read_csv("data/clean/headcount-master.clean.csv")
        self.leavers = read_csv("data/clean/planned-leavers.clean.csv")
        if self.master is None or self.leavers is None:
            self.skipTest("정제 데이터 없음")
        self.status = {r["empId"]: r["status"] for r in self.master}

    def test_leaver_empid_unique(self):
        """위험 2: 퇴사 예정자 복원 추출로 동일 사번 중복."""
        ids = [r["empId"] for r in self.leavers]
        dup = [k for k, v in Counter(ids).items() if v > 1]
        self.assertEqual(dup, [], "퇴사 예정자 사번 중복: %s" % dup)

    def test_planned_out_counts_active_only_and_month_window(self):
        """위험 1·3: 재직 기준 plannedOut은 휴직자·마스터 없는 사번·10월 예정을 제외하고 stale(예정일 < 기준일)은 포함한다."""
        forecast = read_json("data/stats/month-end-forecast.json")
        if forecast is None:
            self.skipTest("forecast 없음")
        independent = 0
        for r in self.leavers:
            emp = r["empId"]
            if emp not in self.status:
                continue  # unknown-emp
            if self.status[emp] != "재직":
                continue  # 휴직자는 재직 인원 차감 대상이 아니다 (§4-5)
            d = date.fromisoformat(r["plannedTerminationDate"])
            if d <= MONTH_END:
                independent += 1
        self.assertEqual(independent, forecast["totals"]["plannedOut"])
        self.assertEqual(independent, 14)

    def test_unknown_emp_flagged(self):
        unknown = [r for r in self.leavers if r["empId"] not in self.status]
        self.assertEqual(len(unknown), 1)
        self.assertIn("unknown-emp", unknown[0].get("unresolvedFlags", ""))


class TestExperienceConsistency(unittest.TestCase):
    def setUp(self):
        self.master = read_csv("data/clean/headcount-master.clean.csv")
        if self.master is None:
            self.skipTest("정제 마스터 없음")

    def test_total_experience_not_less_than_tenure(self):
        """위험 4: 재직기간 > 총경력 모순."""
        bad = [r["empId"] for r in self.master
               if float(r["totalExperienceYears"]) + 1e-9 < float(r["tenureYears"])]
        self.assertEqual(bad, [], "총경력 < 재직기간: %s" % bad[:5])

    def test_age_at_hire_plausible(self):
        """입사 시점 만 나이 ≥ 18 + 입사 전 경력."""
        bad = []
        for r in self.master:
            birth = date.fromisoformat(r["birthDate"])
            hire = date.fromisoformat(r["hireDate"])
            age_at_hire = (hire - birth).days / 365.25
            prior = int(r["priorExperienceMonths"] or 0) / 12.0
            if age_at_hire < 18 + prior - 0.5:
                bad.append(r["empId"])
        self.assertEqual(bad, [], "입사 시 나이 < 18 + 입사 전 경력: %s" % bad[:5])

    def test_hire_not_after_as_of_unless_flagged(self):
        bad = [r["empId"] for r in self.master
               if date.fromisoformat(r["hireDate"]) > AS_OF and "date-logic" not in r.get("unresolvedFlags", "")]
        self.assertEqual(bad, [])


class TestIndependentRecount(unittest.TestCase):
    """정제 CSV → 독립 재집계 → JSON 대조 (복사된 숫자가 아닌 재계산으로 대사)."""

    def setUp(self):
        self.master = read_csv("data/clean/headcount-master.clean.csv")
        self.to = read_csv("data/clean/to-plan.clean.csv")
        self.joiners = read_csv("data/clean/planned-joiners.clean.csv")
        self.leavers = read_csv("data/clean/planned-leavers.clean.csv")
        self.stats = read_json("data/stats/headcount-stats.json")
        self.forecast = read_json("data/stats/month-end-forecast.json")
        if None in (self.master, self.to, self.joiners, self.leavers, self.stats, self.forecast):
            self.skipTest("입력 또는 산출물 없음")

    def test_department_rows_and_identities(self):
        active = Counter(r["deptCode"] for r in self.master if r["status"] == "재직")
        on_leave = Counter(r["deptCode"] for r in self.master if r["status"] == "휴직")
        to = {r["deptCode"]: int(r["toHeadcount"]) for r in self.to}
        status = {r["empId"]: r["status"] for r in self.master}
        j_in = Counter(r["deptCode"] for r in self.joiners if date.fromisoformat(r["plannedHireDate"]) <= MONTH_END)
        l_out = Counter(r["deptCode"] for r in self.leavers
                        if status.get(r["empId"]) == "재직" and date.fromisoformat(r["plannedTerminationDate"]) <= MONTH_END)
        rows = {r["deptCode"]: r for r in self.forecast["byDepartment"]}
        self.assertEqual(len(rows), 11)
        for code, row in rows.items():
            self.assertEqual(row["activeHeadcount"], active[code], code)
            self.assertEqual(row["toHeadcount"], to[code], code)
            self.assertEqual(row["plannedIn"], j_in[code], code)
            self.assertEqual(row["plannedOut"], l_out[code], code)
            # 행별 항등식 (browser-check.md)
            self.assertEqual(row["forecastMonthEnd"], row["activeHeadcount"] + row["plannedIn"] - row["plannedOut"], code)
            self.assertEqual(row["toGapMonthEnd"], row["forecastMonthEnd"] - row["toHeadcount"], code)
            self.assertEqual(row["toGapAsOf"], row["activeHeadcount"] - row["toHeadcount"], code)
        srows = {r["deptCode"]: r for r in self.stats["byDepartment"]}
        for code in rows:
            self.assertEqual(srows[code]["onLeave"], on_leave[code], code)
        t = self.forecast["totals"]
        self.assertEqual((sum(active.values()), sum(on_leave.values()), sum(to.values()), sum(j_in.values()), sum(l_out.values())),
                         (t["activeHeadcount"], self.stats["totals"]["onLeave"], t["toHeadcount"], t["plannedIn"], t["plannedOut"]))
        self.assertEqual(t["forecastMonthEnd"], t["activeHeadcount"] + t["plannedIn"] - t["plannedOut"])


if __name__ == "__main__":
    unittest.main()
