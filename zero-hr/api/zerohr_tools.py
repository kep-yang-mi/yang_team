# -*- coding: utf-8 -*-
"""zerohr_tools.py — Everyday People Agent Function Call 도구 구현 (DATA_CONTRACT §17).

세 페르소나 시스템(급여·온보딩·인사 총괄)의 agent 가 호출하는 도구의 본체. 화면(site/)과 같은
data/stats/*.json · data/clean/*.csv · reports/*.json 을 읽기 전용으로 읽으므로 숫자가 같다(reconciliation-policy).
재계산은 하지 않는다 — insight.run_scenario 만 month-end-forecast.json.scenario.formula 를 적용한다.

공개 API:
  dispatch(name, arguments, root=None) -> 봉투 dict
    {status, asOfDate, role, data, provenance:{source, script}, claims:{implemented, mockup, approvalPending}}
    오류: {status:"error", error, hint, code(400|404), asOfDate, role, tool}
  ToolError(code, message, hint)
Python 3.9 표준 라이브러리만.
"""
import copy
import csv
import datetime as _dt
import json
import math
import os
import re
import uuid

from api import catalog

DEFAULT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FORBIDDEN_KEYS = ("birthDate", "riskScore", "avgRiskScore")   # 어느 role 에도 없다 (pii-minimization-policy)
NAME_KEY = "name"
RECOMMENDATION_RULE = "gapME ≤ −4 → 채용 가속 / gapME ≥ +5 → TO 재검토/이동배치 / 그 외 정상 관리"
DEPT_RE = re.compile(r"^D(0[1-9]|1[01])$")


class ToolError(Exception):
    def __init__(self, code, message, hint=""):
        Exception.__init__(self, message)
        self.code = code
        self.message = message
        self.hint = hint


# ──────────────────────────────────────────────────────────────────────────
# 데이터 로딩 (읽기 전용, mtime 캐시)
# ──────────────────────────────────────────────────────────────────────────
class Store(object):
    FILES = {
        "stats": "data/stats/headcount-stats.json",
        "forecast": "data/stats/month-end-forecast.json",
        "attrition": "data/stats/attrition-risk.json",
        "payroll": "data/stats/payroll-close.json",
        "onboarding": "data/stats/onboarding-plan.json",
        "automation": "data/stats/automation-effect.json",
        "cleansing": "data/clean/cleansing-summary.json",
        "dispatch": "reports/monthly-report-dispatch.json",
        "master": "data/clean/headcount-master.clean.csv",
        "joiners": "data/clean/planned-joiners.clean.csv",
    }

    def __init__(self, root):
        self.root = os.path.abspath(root)
        self._cache = {}

    def path(self, key):
        return os.path.join(self.root, self.FILES[key])

    def get(self, key):
        p = self.path(key)
        if not os.path.exists(p):
            raise ToolError(404, "데이터 없음: %s" % self.FILES[key],
                            "선행 단계 산출물이 없다. zerohr-orchestrator 로 공통 데이터 계층을 먼저 생성한다")
        mtime = os.path.getmtime(p)
        hit = self._cache.get(key)
        if hit and hit[0] == mtime:
            return hit[1]
        if p.endswith(".csv"):
            with open(p, encoding="utf-8", newline="") as f:
                data = list(csv.DictReader(f))
        else:
            with open(p, encoding="utf-8") as f:
                data = json.load(f)
        self._cache[key] = (mtime, data)
        return data

    def rel(self, key):
        return self.FILES[key]


_STORES = {}


def get_store(root=None):
    root = os.path.abspath(root or DEFAULT_ROOT)
    if root not in _STORES:
        _STORES[root] = Store(root)
    return _STORES[root]


# ──────────────────────────────────────────────────────────────────────────
# PII 마스킹 · 조직 범위 제한
# ──────────────────────────────────────────────────────────────────────────
def strip_keys(obj, keys):
    """keys 에 든 키를 재귀적으로 제거한 복사본."""
    if isinstance(obj, dict):
        return {k: strip_keys(v, keys) for k, v in obj.items() if k not in keys}
    if isinstance(obj, list):
        return [strip_keys(v, keys) for v in obj]
    return obj


def mask_for_role(data, role):
    keys = set(FORBIDDEN_KEYS)
    if role in catalog.NO_NAME_ROLES:
        keys.add(NAME_KEY)
    return strip_keys(data, keys)


def scope_to_dept(obj, dept_code):
    """orgLead: deptCode 를 가진 dict 목록은 자기 조직 행만, D코드 키 dict 는 자기 조직 키만 남긴다."""
    if isinstance(obj, dict):
        if obj and all(isinstance(k, str) and DEPT_RE.match(k) for k in obj.keys()):
            return {k: scope_to_dept(v, dept_code) for k, v in obj.items() if k == dept_code}
        return {k: scope_to_dept(v, dept_code) for k, v in obj.items()}
    if isinstance(obj, list):
        if obj and all(isinstance(x, dict) and "deptCode" in x for x in obj):
            return [scope_to_dept(x, dept_code) for x in obj if x.get("deptCode") == dept_code]
        return [scope_to_dept(x, dept_code) for x in obj]
    return obj


def contains_key(obj, key):
    if isinstance(obj, dict):
        return key in obj or any(contains_key(v, key) for v in obj.values())
    if isinstance(obj, list):
        return any(contains_key(v, key) for v in obj)
    return False


# ──────────────────────────────────────────────────────────────────────────
# 인자 검증 (input_schema 기반의 최소 검증 — 표준 라이브러리만)
# ──────────────────────────────────────────────────────────────────────────
def validate_arguments(tool, arguments):
    schema = tool["input_schema"]
    props = schema["properties"]
    args = dict(arguments or {})
    unknown = sorted(set(args) - set(props))
    if unknown:
        raise ToolError(400, "알 수 없는 인자: %s" % ", ".join(unknown), "허용 인자: %s" % ", ".join(sorted(props)))
    for req in schema.get("required", []):
        if req not in args or args[req] is None:
            raise ToolError(400, "필수 인자 누락: %s" % req, props[req].get("description", ""))
    for k, spec in props.items():
        if k not in args or args[k] is None:
            if "default" in spec:
                args[k] = spec["default"]
            continue
        v = args[k]
        t = spec.get("type")
        if t == "string" and not isinstance(v, str):
            raise ToolError(400, "%s 는 문자열이어야 한다" % k, spec.get("description", ""))
        if t == "integer" and (isinstance(v, bool) or not isinstance(v, int)):
            if isinstance(v, float) and v == int(v):
                args[k] = v = int(v)
            else:
                raise ToolError(400, "%s 는 정수여야 한다" % k, spec.get("description", ""))
        if t == "number" and (isinstance(v, bool) or not isinstance(v, (int, float))):
            raise ToolError(400, "%s 는 숫자여야 한다" % k, spec.get("description", ""))
        if t == "object" and not isinstance(v, dict):
            raise ToolError(400, "%s 는 객체여야 한다" % k, spec.get("description", ""))
        if "enum" in spec and v not in spec["enum"]:
            raise ToolError(400, "%s 값 '%s' 은 허용되지 않는다" % (k, v), "허용: %s" % ", ".join(spec["enum"]))
        if "pattern" in spec and isinstance(v, str) and not re.match(spec["pattern"], v):
            raise ToolError(400, "%s 형식 오류: '%s'" % (k, v), spec.get("description", ""))
        if "minimum" in spec and isinstance(v, (int, float)) and v < spec["minimum"]:
            raise ToolError(400, "%s 는 %s 이상이어야 한다" % (k, spec["minimum"]), spec.get("description", ""))
        if "maximum" in spec and isinstance(v, (int, float)) and v > spec["maximum"]:
            raise ToolError(400, "%s 는 %s 이하여야 한다" % (k, spec["maximum"]), spec.get("description", ""))
        if "minLength" in spec and isinstance(v, str) and len(v) < spec["minLength"]:
            raise ToolError(400, "%s 는 비어 있을 수 없다" % k, spec.get("description", ""))
        if "maxLength" in spec and isinstance(v, str) and len(v) > spec["maxLength"]:
            raise ToolError(400, "%s 는 %d자 이하" % (k, spec["maxLength"]), spec.get("description", ""))
    return args


def _dept_index(store):
    return {d["deptCode"]: d["department"] for d in store.get("stats")["byDepartment"]}


def _require_known_dept(store, code):
    idx = _dept_index(store)
    if code not in idx:
        raise ToolError(404, "조직 코드 없음: %s" % code, "허용 조직: %s" % ", ".join("%s %s" % kv for kv in sorted(idx.items())))
    return idx[code]


def _round_half_up(x):
    return int(math.floor(x + 0.5))


# ──────────────────────────────────────────────────────────────────────────
# 도구 구현 — 각 함수는 (data, provenance, claims) 를 돌려준다
# ──────────────────────────────────────────────────────────────────────────
def _prov(store, key, extra=None):
    d = store.get(key)
    p = d.get("provenance", {}) if isinstance(d, dict) else {}
    prov = {"source": store.rel(key), "script": p.get("script", "")}
    if extra:
        prov.update(extra)
    return prov


CHECKLIST_MOCKUP = "checklist[].status 는 스크립트가 만든 초기값(pending|done) — 실제 마감 진행 상태가 아니다"
RECO_PENDING = "권고(채용 가속·TO 재검토/이동배치·퇴사 영향 점검)의 채택은 사람의 승인 gate — 이 응답은 제안이다"


def payroll_get_close_summary(store, a, ctx):
    p = store.get("payroll")
    if a.get("payPeriod") and a["payPeriod"] != p["payPeriod"]:
        raise ToolError(404, "급여 기간 데이터 없음: %s" % a["payPeriod"], "현재 데이터의 급여 기간은 %s 이다. payPeriod 를 생략하거나 %s 로 호출한다" % (p["payPeriod"], p["payPeriod"]))
    data = {
        "payPeriod": p["payPeriod"], "periodStart": p["periodStart"], "periodEnd": p["periodEnd"],
        "payrollHeadcount": copy.deepcopy(p["payrollHeadcount"]),
        "checklist": copy.deepcopy(p["checklist"]),
        "reconciliation": copy.deepcopy(p["provenance"].get("reconciliation", {})),
        "rules": copy.deepcopy(p["provenance"].get("rules", {})),
        "counts": {"joinersInPeriod": len(p["prorations"]["joinersInPeriod"]),
                   "plannedJoinersByMonthEnd": len(p["prorations"]["plannedJoinersByMonthEnd"]),
                   "plannedLeaversByMonthEnd": len(p["prorations"]["plannedLeaversByMonthEnd"]),
                   "onLeave": len(p["leaves"]["onLeave"]), "contractsExpiringWithin90Days": len(p["contracts"]["expiringWithin90Days"]),
                   "risks": len(p["risks"])},
    }
    claims = {"implemented": ["payrollHeadcount·checklist·reconciliation 은 data/stats/payroll-close.json 을 그대로 읽는다(재계산 없음)",
                              "monthEndActive 411 = month-end-forecast.totals.forecastMonthEnd 411 대사(reconciliation.matched)"],
              "mockup": [CHECKLIST_MOCKUP], "approvalPending": []}
    return data, _prov(store, "payroll"), claims


def payroll_list_prorations(store, a, ctx):
    p = store.get("payroll")
    pr = p["prorations"]
    kind = a["kind"]
    data = {"kind": kind, "payPeriod": p["payPeriod"], "rule": p["provenance"].get("rules", {}).get("proratedRatio", "당월 근무일수 / 30, 소수 3자리")}
    if kind in ("actual", "all"):
        data["joinersInPeriod"] = copy.deepcopy(pr["joinersInPeriod"])
    if kind in ("planned", "all"):
        data["plannedJoinersByMonthEnd"] = copy.deepcopy(pr["plannedJoinersByMonthEnd"])
        data["plannedLeaversByMonthEnd"] = copy.deepcopy(pr["plannedLeaversByMonthEnd"])
    data["counts"] = {k: len(v) for k, v in data.items() if isinstance(v, list)}
    claims = {"implemented": ["prorations.* 를 payroll-close.json 에서 그대로 읽는다. proratedRatio 는 상류 스크립트가 계산"],
              "mockup": [], "approvalPending": ["퇴사 예정자 최종 정산·입사 예정자 급여 등록은 급여 시스템에서 사람이 확정한다"]}
    return data, _prov(store, "payroll"), claims


def payroll_list_leave_treatments(store, a, ctx):
    p = store.get("payroll")
    data = {"payPeriod": p["payPeriod"], "onLeave": copy.deepcopy(p["leaves"]["onLeave"]), "byTreatment": copy.deepcopy(p["leaves"]["byTreatment"]),
            "treatmentRule": copy.deepcopy(p["provenance"].get("rules", {}).get("leaveTreatment", {})), "count": len(p["leaves"]["onLeave"])}
    claims = {"implemented": ["leaves 를 payroll-close.json 에서 그대로 읽는다"], "mockup": [],
              "approvalPending": ["휴직유형 미상(status-inconsistency) 건은 HR 확인 후 처리 구분 확정"]}
    return data, _prov(store, "payroll"), claims


def payroll_list_contract_expirations(store, a, ctx):
    p = store.get("payroll")
    within = int(a.get("withinDays", 90))
    as_of = _dt.date.fromisoformat(p["asOfDate"])
    limit = as_of + _dt.timedelta(days=within)
    rows = [r for r in p["contracts"]["expiringWithin90Days"] if _dt.date.fromisoformat(r["contractEndDate"]) <= limit]
    if within >= 90:
        by_month = copy.deepcopy(p["contracts"]["byMonth"])
        note = "byMonth 는 payroll-close.json 값(90일 창)"
    else:
        by_month = {}
        for r in rows:
            m = r["contractEndDate"][:7]
            by_month[m] = by_month.get(m, 0) + 1
        note = "byMonth 는 withinDays=%d 필터의 표시용 집계 — 대사 대상 아님" % within
    data = {"asOfDate": p["asOfDate"], "withinDays": within, "windowEnd": limit.isoformat(), "expiring": copy.deepcopy(rows), "count": len(rows), "byMonth": by_month, "note": note}
    claims = {"implemented": ["contracts.expiringWithin90Days 를 읽고 withinDays 로 필터만 한다"], "mockup": [],
              "approvalPending": ["계약 갱신·종료 결정은 사람(채용/해고 관련 결정 gate)"]}
    return data, _prov(store, "payroll"), claims


def payroll_list_risks(store, a, ctx):
    p = store.get("payroll")
    by_flag = {}
    for r in p["risks"]:
        by_flag[r["unresolvedFlag"]] = by_flag.get(r["unresolvedFlag"], 0) + 1
    data = {"payPeriod": p["payPeriod"], "risks": copy.deepcopy(p["risks"]), "count": len(p["risks"]),
            "byUnresolvedFlag": by_flag, "note": "byUnresolvedFlag 는 표시용 집계. 성명은 원본에 없다(사번만)"}
    claims = {"implemented": ["risks 를 payroll-close.json 에서 그대로 읽는다"], "mockup": [],
              "approvalPending": ["미해결 항목 확정(어느 조직·휴직 여부·계약종료일)은 고객사 HR 의 답 → people-data-cleanser 재실행"]}
    return data, _prov(store, "payroll"), claims


def onboarding_get_timeline(store, a, ctx):
    o = store.get("onboarding")
    flags = {r["joinerId"]: r.get("unresolvedFlags", "") for r in store.get("joiners")}
    weeks = copy.deepcopy(o["timeline"])
    if a.get("week"):
        weeks = [w for w in weeks if w["week"] == a["week"]]
        if not weeks:
            raise ToolError(404, "해당 주에 입사 예정자 없음: %s" % a["week"], "타임라인의 주: %s" % ", ".join(w["week"] for w in o["timeline"]))
    for w in weeks:
        for j in w["joiners"]:
            j["unresolvedFlags"] = [f for f in flags.get(j["joinerId"], "").split(";") if f]
        w["count"] = len(w["joiners"])
    rec = o["provenance"].get("reconciliation", {})
    data = {"asOfDate": o["asOfDate"], "horizonEnd": o["horizonEnd"], "week": a.get("week"), "timeline": weeks,
            "totals": {"joiners": sum(w["count"] for w in weeks), "timelineJoiners": rec.get("timelineJoiners"), "monthEndJoiners": rec.get("monthEndJoiners"),
                       "forecastPlannedIn": rec.get("forecastPlannedIn")}}
    claims = {"implemented": ["timeline 을 onboarding-plan.json 에서 읽고 planned-joiners.clean.csv 의 unresolvedFlags 를 joinerId 로 조인"], "mockup": [], "approvalPending": []}
    return data, _prov(store, "onboarding", {"joinedWith": store.rel("joiners")}), claims


ROSTER_FIELDS = ("empId", "name", "deptCode", "department", "level", "jobFamily", "employmentType", "status")


def onboarding_get_department_plan(store, a, ctx):
    o = store.get("onboarding")
    code = a["deptCode"]
    dept_name = _require_known_dept(store, code)
    plan = next((copy.deepcopy(d) for d in o["byDepartment"] if d["deptCode"] == code), None)
    master = store.get("master")
    roster = [{k: r.get(k, "") for k in ROSTER_FIELDS} for r in master if r["deptCode"] == code]
    roster.sort(key=lambda r: r["empId"])
    joiners = [copy.deepcopy(j) for w in o["timeline"] for j in w["joiners"] if j["deptCode"] == code]
    lead = None
    if plan and plan.get("deptLeadEmpId"):
        lead = next(({k: r.get(k, "") for k in ROSTER_FIELDS} for r in master if r["empId"] == plan["deptLeadEmpId"]), {"empId": plan["deptLeadEmpId"]})
    data = {"deptCode": code, "department": dept_name, "plan": plan, "deptLead": lead, "plannedJoiners": joiners,
            "roster": roster, "rosterCount": len(roster),
            "rules": {"buddy": o["provenance"].get("buddyRule"), "deptLead": o["provenance"].get("deptLeadRule")},
            "note": None if plan else "입사 예정자 없음 — onboarding-plan.byDepartment 에 이 조직이 없다(명부만 반환)"}
    claims = {"implemented": ["byDepartment[deptCode] 와 timeline 은 onboarding-plan.json, 명부 subset 은 headcount-master.clean.csv 에서 읽는다(8필드)"],
              "mockup": [], "approvalPending": ["버디 배정·조직장 확인은 온보딩 담당의 결정"]}
    return data, _prov(store, "onboarding", {"joinedWith": store.rel("master")}), claims


def onboarding_get_checklist(store, a, ctx):
    o = store.get("onboarding")
    status = copy.deepcopy(o["checklist"]["status"])
    if a.get("joinerId"):
        status = [s for s in status if s["joinerId"] == a["joinerId"]]
        if not status:
            raise ToolError(404, "입사 예정자 없음: %s" % a["joinerId"], "joinerId 는 J001~J%03d" % len(o["checklist"]["status"]))
    items = list(o["checklist"]["items"])
    pending = {it: sum(1 for s in status if s.get(it) == "pending") for it in items}
    data = {"items": items, "status": status, "count": len(status), "pendingByItem": pending, "note": o["provenance"].get("checklistNote")}
    claims = {"implemented": ["checklist 를 onboarding-plan.json 에서 읽는다"],
              "mockup": ["체크리스트 status 는 seed 고정 가상 생성(random.seed(%s)) — 실제 진행 상태가 아니다" % o["provenance"].get("seed")], "approvalPending": []}
    return data, _prov(store, "onboarding"), claims


def onboarding_get_early_tenure_cohort(store, a, ctx):
    o = store.get("onboarding")
    data = {"asOfDate": o["asOfDate"], "earlyTenureCohort": copy.deepcopy(o["earlyTenureCohort"]), "earlyAttrition": copy.deepcopy(o["earlyAttrition"])}
    claims = {"implemented": ["earlyTenureCohort·earlyAttrition 을 onboarding-plan.json 에서 읽는다. 사번·집계만"],
              "mockup": [], "approvalPending": ["riskBand 는 rule-based-v1 추정 등급 — 면담 우선순위 참고, 인사 조치 근거 아님"]}
    return data, _prov(store, "onboarding"), claims


def insight_get_executive_snapshot(store, a, ctx):
    s = store.get("stats")
    f = store.get("forecast")
    st, ft = s["totals"], f["totals"]
    data = {"asOfDate": s["asOfDate"], "monthEnd": f["monthEnd"], "client": s.get("client"),
            "activeHeadcount": st["activeHeadcount"], "onLeave": st["onLeave"], "headcount": st["headcount"],
            "toHeadcount": ft["toHeadcount"], "toGapAsOf": ft["toGapAsOf"], "plannedIn": ft["plannedIn"], "plannedOut": ft["plannedOut"],
            "forecastMonthEnd": ft["forecastMonthEnd"], "toGapMonthEnd": ft["toGapMonthEnd"], "toFillRate": ft["toFillRate"],
            "nextMonth": copy.deepcopy(ft.get("nextMonth", {})), "unresolvedCount": st.get("unresolvedCount"),
            "reconciliation": {"statsActiveHeadcount": st["activeHeadcount"], "forecastActiveHeadcount": ft["activeHeadcount"], "match": st["activeHeadcount"] == ft["activeHeadcount"]}}
    claims = {"implemented": ["totals 는 headcount-stats.json(재직·휴직·총원) + month-end-forecast.json(TO·예정·월말) 값 그대로"],
              "mockup": [], "approvalPending": []}
    return data, {"source": "%s, %s" % (store.rel("stats"), store.rel("forecast")), "script": "%s, %s" % (s["provenance"].get("script", ""), f["provenance"].get("script", ""))}, claims


def insight_get_department_forecast(store, a, ctx):
    f = store.get("forecast")
    by_dept = copy.deepcopy(f["byDepartment"])
    by_group = copy.deepcopy(f["byOrgGroup"])
    code = a.get("deptCode")
    if code:
        _require_known_dept(store, code)
        by_dept = [d for d in by_dept if d["deptCode"] == code]
        groups = {d["orgGroupCode"] for d in by_dept}
        by_group = [g for g in by_group if g["orgGroupCode"] in groups]
    data = {"asOfDate": f["asOfDate"], "monthEnd": f["monthEnd"], "nextMonthEnd": f["nextMonthEnd"], "deptCode": code,
            "byDepartment": by_dept, "byOrgGroup": by_group, "totals": copy.deepcopy(f["totals"]) if not code else None,
            "recommendationRule": RECOMMENDATION_RULE, "assumptions": list(f["assumptions"])}
    claims = {"implemented": ["byDepartment/byOrgGroup/totals 는 month-end-forecast.json 값 그대로(필터만)"],
              "mockup": ["riskAdjusted 는 attrition-risk 기대 이탈을 반영한 시나리오(추정)"], "approvalPending": [RECO_PENDING]}
    return data, _prov(store, "forecast"), claims


def insight_get_insights(store, a, ctx):
    f = store.get("forecast")
    data = {"asOfDate": f["asOfDate"], "monthEnd": f["monthEnd"], "insights": copy.deepcopy(f["insights"]), "immediateActions": list(f["immediateActions"]),
            "assumptions": list(f["assumptions"]), "gate": f["provenance"].get("gate"), "recommendationRule": RECOMMENDATION_RULE}
    claims = {"implemented": ["insights·immediateActions 는 month-end-forecast.json 값 그대로"], "mockup": [], "approvalPending": [RECO_PENDING]}
    return data, _prov(store, "forecast"), claims


def insight_get_attribute_stats(store, a, ctx):
    s = store.get("stats")
    attr = a["attribute"]
    dist = s["byAttribute"].get(attr)
    if dist is None:
        raise ToolError(404, "속성 없음: %s" % attr, "허용: %s" % ", ".join(sorted(s["byAttribute"])))
    data = {"asOfDate": s["asOfDate"], "attribute": attr, "basis": "재직 %d" % s["totals"]["activeHeadcount"], "distribution": copy.deepcopy(dist), "total": sum(dist.values())}
    if attr in s.get("byAttributeAll", {}):
        data["distributionAll"] = copy.deepcopy(s["byAttributeAll"][attr])
        data["basisAll"] = "총원 %d(휴직 포함)" % s["totals"]["headcount"]
    claims = {"implemented": ["byAttribute[attribute] 는 headcount-stats.json 값 그대로(합 = 재직 406)"], "mockup": [], "approvalPending": []}
    return data, _prov(store, "stats"), claims


def insight_get_attrition_summary(store, a, ctx):
    r = store.get("attrition")
    code = a.get("deptCode")
    by_dept = copy.deepcopy(r["byDepartment"])
    if code:
        _require_known_dept(store, code)
        by_dept = [d for d in by_dept if d["deptCode"] == code]
    m = r["model"]
    data = {"asOfDate": r["asOfDate"], "deptCode": code, "summary": copy.deepcopy(r["summary"]) if not code else None,
            "byDepartment": by_dept, "byOrgGroup": copy.deepcopy(r["byOrgGroup"]) if not code else None,
            "model": {"name": m["name"], "bands": copy.deepcopy(m["bands"]), "expectedProbability": copy.deepcopy(m["expectedProbability"]),
                      "factors": [{"factor": x["factor"], "rationale": x.get("rationale", "")} for x in m["factors"]], "assumptions": list(m.get("assumptions", []))}}
    if ctx["role"] == "hr":
        emp = [{"empId": e["empId"], "deptCode": e["deptCode"], "riskBand": e["riskBand"], "topFactors": list(e.get("topFactors", []))}
               for e in r["byEmployee"] if not code or e["deptCode"] == code]
        emp.sort(key=lambda e: e["empId"])   # 점수 순 정렬 금지(정렬이 점수를 드러낸다) — 사번 순
        data["byEmployee"] = emp
        data["byEmployeeNote"] = "role=hr 전용. 등급만(점수 없음). 사번 순 정렬"
    claims = {"implemented": ["summary/byDepartment/byOrgGroup 은 attrition-risk.json 값(점수 필드 제거). byEmployee 는 role=hr 에서만 사번·등급"],
              "mockup": ["expectedAttritionNext3Months 는 밴드별 확률 가정(0.35/0.12/0.03)의 시나리오 — 예측을 대체하지 않는다"],
              "approvalPending": ["면담·리텐션 조치는 사람의 결정(민감정보 접근 gate)"]}
    return data, _prov(store, "attrition"), claims


def insight_get_data_quality(store, a, ctx):
    c = store.get("cleansing")
    s = store.get("stats")
    keep = ("asOfDate", "rowsIn", "rowsOut", "duplicatesRemoved", "correctionsByRule", "correctionsBySource", "orgNameCorrections", "orgUnknown",
            "hireDateCorrections", "unresolvedCount", "unresolvedItems", "warnings")
    data = {"cleansingSummary": {k: copy.deepcopy(c[k]) for k in keep if k in c}, "statsDataQuality": copy.deepcopy(s.get("dataQuality", {})),
            "note": "cleansing-summary.unresolvedCount 는 원천 4종 합산, stats.dataQuality.unresolvedCount 는 정제 마스터 행 기준(정의가 다르다, §4-5)"}
    claims = {"implemented": ["cleansing-summary.json 요약 + headcount-stats.dataQuality 값 그대로"], "mockup": [],
              "approvalPending": ["unresolvedItems 의 질문은 고객사 HR 이 답한다 — 임시 배정은 확정이 아니다"]}
    return data, {"source": "%s, %s" % (store.rel("cleansing"), store.rel("stats")), "script": c.get("provenance", {}).get("script", "")}, claims


def insight_run_scenario(store, a, ctx):
    f = store.get("forecast")
    rate = float(a["hiringAchievementRate"])
    extra = int(a["extraAttrition"])
    formula = f["scenario"]["formula"]

    def compute(row, extra_att):
        active, p_in, p_out, to = row["activeHeadcount"], row["plannedIn"], row["plannedOut"], row["toHeadcount"]
        fc = active + _round_half_up(p_in * rate) - p_out - extra_att
        gap = fc - to
        reco = "채용 가속" if gap <= -4 else ("TO 재검토/이동배치" if gap >= 5 else "정상 관리")
        return {"activeHeadcount": active, "plannedIn": p_in, "plannedInApplied": _round_half_up(p_in * rate), "plannedOut": p_out, "extraAttrition": extra_att,
                "toHeadcount": to, "forecastMonthEnd": fc, "toGapMonthEnd": gap, "toFillRate": round(fc / float(to), 4) if to else None, "recommendation": reco}

    code = a.get("deptCode")
    if code:
        _require_known_dept(store, code)
        row = next(d for d in f["byDepartment"] if d["deptCode"] == code)
        scope = {"scope": "department", "deptCode": code, "department": row["department"]}
        baseline = {"forecastMonthEnd": row["forecastMonthEnd"], "toGapMonthEnd": row["toGapMonthEnd"], "recommendation": row["recommendation"]}
        result = compute(row, extra)
        by_dept = None
    else:
        t = f["totals"]
        scope = {"scope": "company"}
        baseline = {"forecastMonthEnd": t["forecastMonthEnd"], "toGapMonthEnd": t["toGapMonthEnd"], "toFillRate": t["toFillRate"]}
        result = compute(t, extra)
        by_dept = [dict({"deptCode": d["deptCode"], "department": d["department"]}, **compute(d, 0)) for d in f["byDepartment"]]
    data = dict(scope, **{
        "asOfDate": f["asOfDate"], "monthEnd": f["monthEnd"],
        "parameters": {"hiringAchievementRate": rate, "extraAttrition": extra}, "formula": formula,
        "baselineParameters": copy.deepcopy(f["scenario"]["parameters"]), "baseline": baseline, "scenario": result, "byDepartment": by_dept,
        "recommendationRule": RECOMMENDATION_RULE,
        "assumptions": ["시나리오(가정) — 대사 대상 아님. 기본 예측은 baseline", "round 는 반올림(0.5 올림, 화면 Math.round 와 동일)",
                        "extraAttrition 은 전사(또는 지정 조직)에만 적용, 조직별 목록은 rate 만 적용", "TO 는 기준월 TO 고정"] + list(f["assumptions"]),
    })
    claims = {"implemented": ["month-end-forecast.json.scenario.formula 로 재계산(유일한 계산 도구). 기본 예측 값은 파일에서 읽는다"],
              "mockup": ["시나리오 결과는 가정값 — 저장되지 않으며 화면·리포트 수치가 아니다"], "approvalPending": [RECO_PENDING]}
    return data, _prov(store, "forecast", {"computation": "api/zerohr_tools.py:insight_run_scenario"}), claims


def report_get_monthly_dispatch(store, a, ctx):
    d = store.get("dispatch")
    data = copy.deepcopy(d)
    data["recipientCount"] = sum(len(v) for v in d.get("recipients", {}).values())
    data["sent"] = False
    claims = {"implemented": ["dispatch 자산(reports/monthly-report-dispatch.json)을 그대로 읽는다. 리포트 본문은 같은 data/stats 에서 렌더"],
              "mockup": ["status=ready-to-send — 발송되지 않았다. 수신자는 @ondatech.example 예시 주소"],
              "approvalPending": ["외부 발송(approval-gate: 외부 발송) — approval.request(action='send-monthly-report') 로 승인 대기 기록"]}
    return data, {"source": store.rel("dispatch"), "script": ".claude/skills/monthly-report/scripts"}, claims


def approval_request(store, a, ctx):
    now = _dt.datetime.now().replace(microsecond=0)
    action = a["action"]
    if not re.match(r"^[a-z0-9][a-z0-9\-]*$", action):
        raise ToolError(400, "action 은 kebab-case 여야 한다: %s" % action, "예 send-monthly-report, adopt-recommendation")
    payload = a.get("payload") or {}
    if contains_key(payload, "name") or contains_key(payload, "birthDate"):
        raise ToolError(400, "payload 에 성명·생년월일을 넣을 수 없다", "사번(empId/joinerId)·경로·건수만 적는다(pii-minimization-policy)")
    if any(re.search(r"(secret|token|password|api[_-]?key)", k, re.I) for k in payload):
        raise ToolError(400, "payload 에 자격증명 키를 넣을 수 없다", "자격증명은 $VAR 이름으로만 언급한다(approval-gate-policy)")
    as_of = _as_of(store)
    apr_id = "apr-%s-%s" % (now.strftime("%Y%m%d-%H%M%S"), uuid.uuid4().hex[:6])
    rec = {"id": apr_id, "status": "pending", "action": action, "payload": payload, "requestedBy": a.get("requestedBy") or ctx["role"],
           "role": ctx["role"], "requestedAt": now.isoformat(), "asOfDate": as_of, "gate": "approval-gate: %s" % action,
           "approvalPhrase": "'%s' 승인 요청(%s)을 승인합니다" % (action, apr_id),
           "note": "agent 는 실행하지 않았다. 사용자의 명시적 승인 문장 뒤에 사람의 환경에서 실행한다(approval-gate-policy 3·4)",
           "approvedBy": None, "approvedAt": None}
    d = os.path.join(store.root, "_workspace", "approvals")
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, apr_id + ".json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(rec, fh, ensure_ascii=False, indent=2)
    data = {"approvalId": apr_id, "status": "pending", "action": action, "path": os.path.relpath(path, store.root), "approvalPhrase": rec["approvalPhrase"], "executed": False}
    claims = {"implemented": ["_workspace/approvals/{id}.json 에 pending 기록을 남긴다(파일만, 외부 효과 없음)"], "mockup": [],
              "approvalPending": ["%s — 사람의 승인 후 실행" % action]}
    return data, {"source": data["path"], "script": "api/zerohr_tools.py:approval_request"}, claims


IMPLEMENTATIONS = {
    "payroll.get_close_summary": payroll_get_close_summary,
    "payroll.list_prorations": payroll_list_prorations,
    "payroll.list_leave_treatments": payroll_list_leave_treatments,
    "payroll.list_contract_expirations": payroll_list_contract_expirations,
    "payroll.list_risks": payroll_list_risks,
    "onboarding.get_timeline": onboarding_get_timeline,
    "onboarding.get_department_plan": onboarding_get_department_plan,
    "onboarding.get_checklist": onboarding_get_checklist,
    "onboarding.get_early_tenure_cohort": onboarding_get_early_tenure_cohort,
    "insight.get_executive_snapshot": insight_get_executive_snapshot,
    "insight.get_department_forecast": insight_get_department_forecast,
    "insight.get_insights": insight_get_insights,
    "insight.get_attribute_stats": insight_get_attribute_stats,
    "insight.get_attrition_summary": insight_get_attrition_summary,
    "insight.get_data_quality": insight_get_data_quality,
    "insight.run_scenario": insight_run_scenario,
    "report.get_monthly_dispatch": report_get_monthly_dispatch,
    "approval.request": approval_request,
}
SIDE_EFFECT_TOOLS = ("approval.request",)


def _as_of(store):
    for key in ("stats", "forecast", "payroll", "onboarding"):
        try:
            return store.get(key)["asOfDate"]
        except Exception:
            continue
    return None


# ──────────────────────────────────────────────────────────────────────────
# 디스패치
# ──────────────────────────────────────────────────────────────────────────
def dispatch(name, arguments=None, root=None):
    """도구 이름과 인자로 봉투를 돌려준다. 예외는 던지지 않고 status:error 봉투로 돌려준다."""
    store = get_store(root)
    role = (arguments or {}).get("role") or "executive"
    try:
        tool = catalog.find(name)
        if tool is None:
            raise ToolError(404, "도구 없음: %s" % name, "GET /tools 또는 api/tools.json 의 이름을 쓴다. 예: %s" % ", ".join(catalog.tool_names()[:3]))
        args = validate_arguments(tool, arguments)
        role = args["role"]
        ctx = {"role": role, "deptCode": args.get("deptCode")}
        if role == "orgLead" and not ctx["deptCode"]:
            has_dept_arg = "deptCode" in tool["input_schema"]["properties"]
            raise ToolError(400, "orgLead 는 deptCode 가 필요하다",
                            "조직장은 자기 조직만 본다. deptCode 를 함께 넘긴다(D01~D11)" if has_dept_arg else "이 도구는 조직 범위 인자가 없어 orgLead 로 호출할 수 없다. executive 또는 hr 로 호출한다")
        data, prov, claims = IMPLEMENTATIONS[name](store, args, ctx)
        if role == "orgLead":
            data = scope_to_dept(data, ctx["deptCode"])
        data = mask_for_role(data, role)
        return {"status": "ok", "asOfDate": _as_of(store), "role": role, "tool": name, "data": data, "provenance": prov,
                "claims": {"implemented": claims.get("implemented", []), "mockup": claims.get("mockup", []), "approvalPending": claims.get("approvalPending", [])}}
    except ToolError as e:
        return {"status": "error", "code": e.code, "error": e.message, "hint": e.hint, "asOfDate": _as_of(store) if store else None, "role": role, "tool": name}


def list_tools():
    return catalog.anthropic_tools()


def list_tools_openai():
    return catalog.openai_tools()


if __name__ == "__main__":   # 간이 CLI: python3 api/zerohr_tools.py insight.get_executive_snapshot '{"role":"hr"}'
    import sys
    n = sys.argv[1] if len(sys.argv) > 1 else "insight.get_executive_snapshot"
    a = json.loads(sys.argv[2]) if len(sys.argv) > 2 else {}
    print(json.dumps(dispatch(n, a), ensure_ascii=False, indent=2))
