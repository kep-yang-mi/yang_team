# -*- coding: utf-8 -*-
"""test_site.py — DATA_CONTRACT §14: 제품 페이지·스냅샷 검사 (내장 JSON, 외부 스크립트 허용 목록, 뷰 4종, PII 스냅샷 규칙)."""
import glob
import json
import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = os.path.join(ROOT, "site")
ALLOWED_SCRIPT_HOSTS = ("cdnjs.cloudflare.com", "cdn.jsdelivr.net")
VIEWS = ("executive", "hr", "planning", "orgLead")
RE_REPORT_DATA = re.compile(r'<script\b[^>]*\bid\s*=\s*"report-data"[^>]*>(.*?)</script>', re.DOTALL | re.IGNORECASE)
RE_SCRIPT_SRC = re.compile(r'<script\b[^>]*\bsrc\s*=\s*"([^"]+)"', re.IGNORECASE)
RE_BIRTH = re.compile(r"\d{4}-\d{2}-\d{2}")


def pages():
    return sorted(glob.glob(os.path.join(SITE, "**", "index.html"), recursive=True))


def load_snapshot(code):
    path = os.path.join(SITE, "data", "%s.json" % code)
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


class TestSitePages(unittest.TestCase):
    def setUp(self):
        self.pages = pages()
        if not self.pages:
            self.skipTest("site/**/index.html 없음 — product-builder 이전")

    def test_embedded_json_present_and_valid(self):
        for page in self.pages:
            with open(page, encoding="utf-8") as fh:
                html = fh.read()
            m = RE_REPORT_DATA.search(html)
            self.assertIsNotNone(m, "%s: <script id=\"report-data\"> 없음" % page)
            body = m.group(1).strip()
            if body:  # 허브는 비교 전 빈 자리표시자를 가질 수 있다
                try:
                    json.loads(body.replace("<\\/", "</"))
                except ValueError as exc:
                    self.fail("%s: 내장 JSON 파싱 실패 — %s" % (page, exc))

    def test_external_scripts_allowlisted(self):
        for page in self.pages:
            with open(page, encoding="utf-8") as fh:
                html = fh.read()
            for src in RE_SCRIPT_SRC.findall(html):
                if src.startswith("http"):
                    self.assertTrue(any(h in src for h in ALLOWED_SCRIPT_HOSTS),
                                    "%s: 허용되지 않은 외부 스크립트 %s" % (page, src))

    def test_insight_has_four_views(self):
        page = os.path.join(SITE, "insight", "index.html")
        if not os.path.exists(page):
            self.skipTest("insight 페이지 없음")
        with open(page, encoding="utf-8") as fh:
            html = fh.read()
        for view in VIEWS:
            self.assertIn(view, html, "insight: 뷰 %s 없음" % view)

    def test_app_has_six_roles(self):
        page = os.path.join(SITE, "app", "index.html")
        if not os.path.exists(page):
            self.skipTest("통합 제품(app) 없음 — unified-product-builder 이전")
        with open(page, encoding="utf-8") as fh:
            html = fh.read()
        for role in VIEWS + ("payroll", "onboarding"):
            self.assertIn(role, html, "app: 역할 %s 없음" % role)
        self.assertIn("data-origin", html, "app: 섹션 출처(data-origin) 표기 없음")


class TestSnapshotPii(unittest.TestCase):
    def test_hr_directory_has_no_birthdate(self):
        for code in ("insight", "app"):
            snap = load_snapshot(code)
            if snap is None:
                continue
            for row in (snap.get("hrDirectory") or []):
                self.assertNotIn("birthDate", row, "%s.hrDirectory 에 생년월일" % code)
                self.assertEqual(sorted(row.keys()), sorted(["empId", "name", "deptCode", "department", "level"]),
                                 "%s.hrDirectory 필드 초과" % code)

    def test_attrition_by_employee_has_no_name(self):
        for code in ("insight", "app"):
            snap = load_snapshot(code)
            if snap is None or not snap.get("attrition"):
                continue
            for row in snap["attrition"].get("byEmployee") or []:
                self.assertNotIn("name", row, "%s.attrition.byEmployee 에 성명" % code)

    def test_planned_joiners_have_no_birthdate(self):
        for code in ("onboard", "app"):
            snap = load_snapshot(code)
            if snap is None:
                continue
            for row in (snap.get("plannedJoiners") or []):
                self.assertNotIn("birthDate", row, "%s.plannedJoiners 에 생년월일" % code)

    def test_payroll_has_no_amount_fields(self):
        for code in ("payroll", "app"):
            snap = load_snapshot(code)
            if snap is None or not snap.get("payrollClose"):
                continue
            text = json.dumps(snap["payrollClose"], ensure_ascii=False)
            for bad in ("salary", "amount", "급여액", "지급액", "계좌"):
                # "급여액 없음" 같은 부정 서술(provenance.rules.pii)은 위반이 아니다 — 범위를 밝히는 문장이다
                hits = [m.start() for m in re.finditer(re.escape(bad), text)]
                real = [i for i in hits
                        if not re.search(r"(없|다루지|제외|아닙|미포함)", text[i:i + 40])]
                self.assertEqual(real, [], "%s.payrollClose 에 금액/계좌 필드 %s (%d건)" % (code, bad, len(real)))

    def test_same_metric_same_value_across_snapshots(self):
        insight, payroll, app = load_snapshot("insight"), load_snapshot("payroll"), load_snapshot("app")
        if insight is None:
            self.skipTest("insight 스냅샷 없음")
        me = insight["forecast"]["totals"]["forecastMonthEnd"]
        active = insight["stats"]["totals"]["activeHeadcount"]
        if payroll is not None and payroll.get("payrollClose"):
            self.assertEqual(payroll["payrollClose"]["payrollHeadcount"]["monthEndActive"], me)
            self.assertEqual(payroll["payrollClose"]["payrollHeadcount"]["asOfActive"], active)
        if app is not None:
            self.assertEqual(app["forecast"]["totals"]["forecastMonthEnd"], me)
            self.assertEqual(app["stats"]["totals"]["activeHeadcount"], active)

    def test_department_row_identities_in_snapshots(self):
        """browser-check.md: 행별 현재+입사−퇴사=월말, 월말−TO=Gap, 11행, 합계 406/19/14/411/−11."""
        for code in ("insight", "app"):
            snap = load_snapshot(code)
            if snap is None:
                continue
            rows = snap["forecast"]["byDepartment"]
            self.assertEqual(len(rows), 11, code)
            for r in rows:
                self.assertEqual(r["forecastMonthEnd"], r["activeHeadcount"] + r["plannedIn"] - r["plannedOut"], (code, r["deptCode"]))
                self.assertEqual(r["toGapMonthEnd"], r["forecastMonthEnd"] - r["toHeadcount"], (code, r["deptCode"]))
            sums = (sum(r["activeHeadcount"] for r in rows), sum(r["plannedIn"] for r in rows), sum(r["plannedOut"] for r in rows),
                    sum(r["forecastMonthEnd"] for r in rows), sum(r["toGapMonthEnd"] for r in rows))
            self.assertEqual(sums, (406, 19, 14, 411, -11), code)

    def test_claims_boundary_block_present(self):
        """claims-boundary-policy: 허브·통합 제품 푸터에 '이 화면의 범위' 블록."""
        for rel in ("index.html", os.path.join("app", "index.html")):
            page = os.path.join(SITE, rel)
            if not os.path.exists(page):
                continue
            with open(page, encoding="utf-8") as fh:
                self.assertIn('data-section="claims"', fh.read(), rel)


if __name__ == "__main__":
    unittest.main()
