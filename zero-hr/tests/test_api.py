# -*- coding: utf-8 -*-
"""test_api.py — Function Call 인터페이스 검사 (DATA_CONTRACT §17-3).

화면과 도구가 같은 값을 주는지, role 에 따라 개인정보가 가려지는지, 승인 gate 가 실행 대신 기록만 남기는지를 본다.
"""
import json
import os
import sys
import threading
import unittest
import urllib.request

ROOT = os.environ.get("ZERO_HR_ROOT") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

try:
    from api import zerohr_tools as tools
except Exception as exc:  # pragma: no cover
    tools = None
    IMPORT_ERROR = exc


def contains_key_deep(obj, key):
    if isinstance(obj, dict):
        if key in obj:
            return True
        return any(contains_key_deep(v, key) for v in obj.values())
    if isinstance(obj, list):
        return any(contains_key_deep(v, key) for v in obj)
    return False


@unittest.skipIf(tools is None, "api 모듈 임포트 실패")
class TestCatalog(unittest.TestCase):
    def test_every_tool_has_schema_and_dispatch(self):
        catalog = tools.list_tools()
        self.assertGreaterEqual(len(catalog), 18)
        for tool in catalog:
            self.assertIn("name", tool)
            self.assertIn("description", tool)
            self.assertIsInstance(tool.get("input_schema"), dict, tool["name"])
            self.assertEqual(tool["input_schema"].get("type"), "object", tool["name"])

    def test_openai_catalog_matches(self):
        a = sorted(t["name"] for t in tools.list_tools())
        b = sorted(t["function"]["name"] for t in tools.list_tools_openai())
        self.assertEqual(a, b)

    def test_unknown_tool_returns_error_envelope(self):
        """없는 도구는 예외가 아니라 오류 봉투로 돌려준다 — 호출한 agent 가 힌트를 읽고 고칠 수 있어야 한다."""
        res = tools.dispatch("insight.does_not_exist", {}, root=ROOT)
        self.assertEqual(res["status"], "error")
        self.assertIn("hint", res)


@unittest.skipIf(tools is None, "api 모듈 임포트 실패")
class TestReconciliation(unittest.TestCase):
    def test_payroll_month_end_equals_forecast(self):
        pay = tools.dispatch("payroll.get_close_summary", {"payPeriod": "2026-09", "role": "payroll"}, root=ROOT)
        snap = tools.dispatch("insight.get_executive_snapshot", {"role": "executive"}, root=ROOT)
        self.assertEqual(pay["status"], "ok")
        self.assertEqual(snap["status"], "ok")
        self.assertEqual(pay["data"]["payrollHeadcount"]["monthEndActive"], snap["data"]["forecastMonthEnd"])
        self.assertEqual(snap["data"]["forecastMonthEnd"], 411)
        self.assertEqual(snap["data"]["activeHeadcount"], 406)
        self.assertEqual(snap["data"]["toGapMonthEnd"], -11)

    def test_onboarding_timeline_total(self):
        res = tools.dispatch("onboarding.get_timeline", {"role": "onboarding"}, root=ROOT)
        total = sum(len(w.get("joiners") or []) for w in res["data"]["timeline"])
        self.assertEqual(total, 27)

    def test_scenario_uses_contract_formula(self):
        base = tools.dispatch("insight.run_scenario", {"hiringAchievementRate": 1.0, "extraAttrition": 0}, root=ROOT)
        self.assertEqual(base["data"]["scenario"]["forecastMonthEnd"], 411)
        self.assertEqual(base["data"]["baseline"]["forecastMonthEnd"], 411)
        cut = tools.dispatch("insight.run_scenario", {"hiringAchievementRate": 0.5, "extraAttrition": 3}, root=ROOT)
        self.assertLess(cut["data"]["scenario"]["forecastMonthEnd"], 411)


@unittest.skipIf(tools is None, "api 모듈 임포트 실패")
class TestRolePii(unittest.TestCase):
    def test_executive_role_has_no_names(self):
        for name, args in (("insight.get_executive_snapshot", {}), ("insight.get_department_forecast", {}),
                           ("insight.get_attrition_summary", {}), ("onboarding.get_timeline", {})):
            res = tools.dispatch(name, dict(args, role="executive"), root=ROOT)
            self.assertFalse(contains_key_deep(res["data"], "name"), "%s(role=executive) 에 성명" % name)

    def test_payroll_role_keeps_names(self):
        res = tools.dispatch("payroll.list_prorations", {"kind": "actual", "role": "payroll"}, root=ROOT)
        rows = res["data"].get("joinersInPeriod") or []
        self.assertTrue(rows)
        self.assertTrue(any("name" in r for r in rows))

    def test_no_birthdate_or_riskscore_for_any_role(self):
        for role in ("executive", "hr", "planning", "orgLead", "payroll", "onboarding"):
            for name in ("insight.get_attrition_summary", "onboarding.get_early_tenure_cohort",
                         "payroll.get_close_summary", "insight.get_department_forecast"):
                args = {"role": role}
                if role == "orgLead":
                    args["deptCode"] = "D03"   # 조직장은 자기 조직을 지정해야 한다
                res = tools.dispatch(name, args, root=ROOT)
                if res.get("status") != "ok":
                    continue   # 역할이 허용되지 않는 조합은 오류 봉투 — PII 노출이 아니다
                self.assertFalse(contains_key_deep(res["data"], "birthDate"), "%s/%s 에 생년월일" % (name, role))
                self.assertFalse(contains_key_deep(res["data"], "riskScore"), "%s/%s 에 리스크 점수" % (name, role))

    def test_envelope_shape(self):
        res = tools.dispatch("insight.get_data_quality", {"role": "hr"}, root=ROOT)
        for key in ("status", "asOfDate", "role", "data", "provenance", "claims"):
            self.assertIn(key, res)


@unittest.skipIf(tools is None, "api 모듈 임포트 실패")
class TestApprovalGate(unittest.TestCase):
    def test_request_only_writes_pending_record(self):
        res = tools.dispatch("approval.request",
                             {"action": "send-monthly-report", "payload": {"month": "2026-09"}}, root=ROOT)
        self.assertEqual(res["status"], "ok")
        data = res["data"]
        self.assertEqual(data["status"], "pending")
        path = os.path.join(ROOT, data["path"])
        self.assertTrue(os.path.exists(path))
        with open(path, encoding="utf-8") as fh:
            saved = json.load(fh)
        self.assertEqual(saved["status"], "pending")
        os.remove(path)


@unittest.skipIf(tools is None, "api 모듈 임포트 실패")
class TestHttpServer(unittest.TestCase):
    def test_tools_and_call(self):
        from api import server as api_server
        httpd = api_server.serve(ROOT, 0)
        port = httpd.server_address[1]
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        try:
            with urllib.request.urlopen("http://127.0.0.1:%d/tools" % port, timeout=10) as resp:
                catalog = json.loads(resp.read().decode("utf-8"))
            self.assertGreaterEqual(len(catalog), 18)
            body = json.dumps({"name": "insight.get_executive_snapshot", "arguments": {"role": "executive"}}).encode("utf-8")
            req = urllib.request.Request("http://127.0.0.1:%d/call" % port, data=body,
                                         headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                out = json.loads(resp.read().decode("utf-8"))
            self.assertEqual(out["data"]["forecastMonthEnd"], 411)
        finally:
            httpd.shutdown()
            httpd.server_close()


@unittest.skipIf(tools is None, "api 모듈 임포트 실패")
class TestStaticSnapshots(unittest.TestCase):
    def test_static_files_match_live_dispatch(self):
        static_dir = os.path.join(ROOT, "site", "api")
        if not os.path.isdir(static_dir):
            self.skipTest("site/api 없음 — build_static.py 이전")
        path = os.path.join(static_dir, "insight.get_executive_snapshot.json")
        if not os.path.exists(path):
            self.skipTest("정적 스냅샷 없음")
        with open(path, encoding="utf-8") as fh:
            static = json.load(fh)
        live = tools.dispatch("insight.get_executive_snapshot", {"role": "executive"}, root=ROOT)
        self.assertEqual(static["data"]["forecastMonthEnd"], live["data"]["forecastMonthEnd"])


if __name__ == "__main__":
    unittest.main()
