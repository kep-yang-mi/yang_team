#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""payroll_close.py — 급여 마감(payroll-close) 파생 데이터 생성. DATA_CONTRACT v2 §10 + §4-5.

급여액·보상은 다루지 않는다 — "누가 급여 대상인가"와 이벤트만. Python 3.9 표준 라이브러리만.

입력 (정제 데이터만 읽는다 — 원천 data/raw/ 금지):
  data/clean/headcount-master.clean.csv   필수  §3-1 (427 = 재직 406 + 휴직 21, 퇴직 행 없음)
  data/clean/planned-joiners.clean.csv    필수  §3-3
  data/clean/planned-leavers.clean.csv    필수  §3-4 (성명 없음 → 마스터 조인)
  data/stats/month-end-forecast.json      권장  §4-2 — totals.forecastMonthEnd(411) == monthEndActive assert. 없으면 ok-unverified
  data/reference/org-chart.csv            선택  §1 조직 순서·명칭
  data/stats/headcount-stats.json         선택  §4-1 재직/휴직 소프트 대사 + 니즈 근거 해소
  data/clean/cleansing-summary.json       선택  §3-6 니즈 근거 해소 전용
  personas/persona-needs.json             선택  §9 급여 담당 requiredFields·fitCriteria → 체크리스트 보강
출력:
  data/stats/payroll-close.json                      (대사 통과 또는 예측 없음)
  _workspace/payroll-close.unreconciled.json         (예측과 불일치 시, exit 2; --allow-mismatch면 계약 경로에 씀)
  _workspace/handoff/06-payroll.md                   (핸드오프 로그 — 실행 시작·종료 시 기록, 5개 H2 고정)
  stdout 마지막 줄: 요약 JSON 1행 (진행 로그는 stderr)
종료 코드: 0 정상 · 2 대사 실패 · 3 필수 입력 누락 · 4 계약 불일치(정제 CSV 헤더) · 1 그 외
"""
import argparse
import calendar
import csv
import json
import os
import sys
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

DEFAULT_ROOT = "/Users/yang/development/zero-hr"
DEFAULT_AS_OF = "2026-09-23"

STAGE = "06-payroll"
AGENT = "payroll-close-analyst"
PATH_MASTER = "data/clean/headcount-master.clean.csv"
PATH_JOINERS = "data/clean/planned-joiners.clean.csv"
PATH_LEAVERS = "data/clean/planned-leavers.clean.csv"
PATH_ORG_CHART = "data/reference/org-chart.csv"
PATH_FORECAST = "data/stats/month-end-forecast.json"
PATH_STATS = "data/stats/headcount-stats.json"
PATH_CLEANSING_SUMMARY = "data/clean/cleansing-summary.json"
PATH_PERSONA_NEEDS = "personas/persona-needs.json"
PATH_OUTPUT = "data/stats/payroll-close.json"
PATH_UNRECONCILED = "_workspace/payroll-close.unreconciled.json"
PATH_HANDOFF = "_workspace/handoff/06-payroll.md"
SCRIPT_PATH = ".claude/skills/payroll-close/scripts/payroll_close.py"

ACTIVE, ON_LEAVE = "재직", "휴직"
EMPLOYMENT_TYPES = ["정규직", "계약직", "인턴", "파견"]
LEAVE_TREATMENT = {"육아휴직": "무급(정부 급여)", "질병휴직": "유급", "기타": "무급"}   # §10
TREATMENT_ORDER = ["무급(정부 급여)", "유급", "무급"]
CONTRACT_WINDOW_DAYS = 90
PERSONA_CODE = "payroll"
UNKNOWN_BUCKET = "미상"   # §4-5 빈 값 버킷

# §2-7 정본(데모 기준일에서만 대조). 대조 실패는 종료 코드를 바꾸지 않고 targetCheck로 반환한다 — 원인은 상류(정제·예측)일 가능성이 높다
TARGETS = {"asOfActive": 406, "asOfOnLeave": 21, "asOfTotal": 427, "monthEndActive": 411, "monthEndTotal": 432,
           "byEmploymentType": {"정규직": 354, "계약직": 31, "인턴": 19, "파견": 23}}

REQUIRED_COLUMNS = {
    "headcount-master": ["empId", "name", "deptCode", "employmentType", "status", "leaveType", "leaveStart",
                         "hireDate", "contractEndDate", "unresolvedFlags"],
    "planned-joiners": ["joinerId", "name", "deptCode", "plannedHireDate"],
    "planned-leavers": ["empId", "deptCode", "plannedTerminationDate", "separationType", "unresolvedFlags"],
}

# 클린저 미해결 어휘(§2-5/§2-8) → 급여 관점 이슈·영향
FLAG_RISK = {
    "org-unknown": ("소속이 조직 체계에 없어 직군 기준 임시 배정", "조직별 급여 대상 집계·비용 배부 오류 위험"),
    "date-logic": ("재직인데 입사일이 기준일 이후(플래그, 재직기간 0)", "입사 전 급여 발생·일할 계산 오류 위험"),
    "status-inconsistency": ("휴직인데 휴직유형 없음 → 기타로 보정(미확인)", "휴직 급여 처리 구분 오류 위험"),
    "missing-required": ("계약직/인턴/파견인데 계약종료일 없음", "계약 만료 급여 종료 시점 미확정 위험"),
    "stale-planned-leaver": ("퇴사 예정일이 이미 지남 → 월말 예측에서는 퇴사로 반영", "퇴직 처리 누락 시 급여 과지급 위험"),
    "unknown-emp": ("퇴사 예정자 사번이 마스터에 없음 → 예측 제외", "퇴직 정산 대상 오류 위험"),
    "date-format": ("일자 포맷 미확정(파싱 불가)", "급여 기간 산정 오류 위험"),
}
# 급여 파생 어휘 — §4-5가 허용한 3종만. 그 외 상황은 §2-5 어휘에 issue 텍스트로 구분한다
DERIVED_FLAGS = {
    "contract-expired-active": ("계약종료일이 기준일 이전인데 재직/휴직", "계약 갱신 미반영 시 급여 지급 근거 부재"),
    "leaver-not-active": ("퇴사 예정자가 마스터에서 휴직 상태 → 재직 기준 예측(monthEndActive) 제외, 총원(monthEndTotal)에는 반영", "퇴직 정산 기준 상태 확인 필요"),
    "hire-after-as-of": ("입사일이 기준일 이후인데 재직/휴직", "입사 전 급여 발생 위험"),
}
# 산출물 shape(§10 + §4-5) — 계약에 없는 필드는 산출물에 넣지 않는다
KEYS_BY_DEPT = ("deptCode", "department", "asOfActive", "asOfOnLeave", "asOfTotal", "plannedIn", "plannedOut", "monthEndActive", "monthEndTotal")
KEYS_JOINER_IN = ("empId", "name", "deptCode", "hireDate", "employmentType", "workedDays", "proratedRatio")
KEYS_PLANNED_JOINER = ("joinerId", "name", "deptCode", "plannedHireDate", "workedDays", "proratedRatio")
KEYS_PLANNED_LEAVER = ("empId", "name", "deptCode", "plannedTerminationDate", "separationType", "workedDays", "proratedRatio")
KEYS_ON_LEAVE = ("empId", "name", "deptCode", "leaveType", "leaveStart", "payrollTreatment")
KEYS_EXPIRING = ("empId", "name", "deptCode", "employmentType", "contractEndDate")


class ContractMismatch(Exception):
    def __init__(self, gaps: Dict[str, List[str]]) -> None:
        super().__init__("contract mismatch: %s" % gaps)
        self.gaps = gaps


# ---------------------------------------------------------------- helpers
def log(msg: str) -> None:
    sys.stderr.write("[payroll-close] " + msg + "\n")


def read_csv_rows(path: str) -> Tuple[List[Dict[str, str]], List[str]]:
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        rows = [dict(r) for r in reader]
        return rows, list(reader.fieldnames or [])


def read_json(path: str) -> Optional[Any]:
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def parse_date(v: Optional[str]) -> Optional[date]:
    v = (v or "").strip()
    try:
        return date.fromisoformat(v[:10]) if v else None
    except ValueError:
        return None


def iso(d: Optional[date]) -> Optional[str]:
    return d.isoformat() if d else None


def flags_of(v: Optional[str]) -> List[str]:
    return [x.strip() for x in (v or "").split(";") if x.strip()]


def month_key(d: date) -> str:
    return "%04d-%02d" % (d.year, d.month)


def months_between(start: date, end: date) -> List[str]:
    keys, (y, m) = [], (start.year, start.month)
    while (y, m) <= (end.year, end.month):
        keys.append("%04d-%02d" % (y, m))
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return keys


def worked(start: date, end: date, days_in_month: int) -> int:
    return max(0, min((end - start).days + 1, days_in_month))


def ratio(days: int, days_in_month: int) -> float:
    return round(days / float(days_in_month), 3)


def project(row: Dict[str, Any], keys: Tuple[str, ...]) -> Dict[str, Any]:
    return {k: row.get(k) for k in keys}


def count_by(rows: List[Dict[str, Any]], key: str) -> Dict[str, int]:
    out: Dict[str, int] = {}
    for r in rows:
        k = r.get(key, "") or UNKNOWN_BUCKET
        out[k] = out.get(k, 0) + 1
    return out


# ---------------------------------------------------------------- handoff log (Operating Rule 2)
def new_state(root: str, as_of_text: str) -> Dict[str, Any]:
    return {"status": "실행 중", "root": root, "asOf": as_of_text,
            "tried": ["`%s --root %s --as-of %s` 실행 시작" % (SCRIPT_PATH, root, as_of_text)],
            "evidence": ["입력 예정: %s · %s · %s · %s(대사 기준) · %s · %s(선택)" % (
                PATH_MASTER, PATH_JOINERS, PATH_LEAVERS, PATH_FORECAST, PATH_ORG_CHART, PATH_PERSONA_NEEDS)],
            "failed": [], "verified": [], "next": ["실행 중 — 종료 시 갱신된다"]}


def write_handoff(state: Dict[str, Any]) -> str:
    path = os.path.join(state["root"], PATH_HANDOFF)
    os.makedirs(os.path.dirname(path), exist_ok=True)

    def sec(title: str, items: List[str]) -> str:
        body = "\n".join("- " + x for x in items) if items else "- (없음)"
        return "## %s\n%s\n\n" % (title, body)
    text = "# %s — %s — %s\n\n상태: %s · 기록: %s · 스크립트: `%s`\n\n" % (
        STAGE, AGENT, state["asOf"], state["status"], datetime.now().strftime("%Y-%m-%d %H:%M:%S"), SCRIPT_PATH)
    text += sec("시도한 것", state["tried"]) + sec("본 데이터·근거", state["evidence"]) + sec("실패한 것", state["failed"])
    text += sec("검증된 것", state["verified"]) + sec("다음 agent 인계점", state["next"])
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return PATH_HANDOFF


# ---------------------------------------------------------------- build
def build(root: str, as_of: date, warnings: List[str], state: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    period_start = as_of.replace(day=1)
    dim = calendar.monthrange(as_of.year, as_of.month)[1]
    period_end = as_of.replace(day=dim)
    window_end = as_of + timedelta(days=CONTRACT_WINDOW_DAYS)

    master, mh = read_csv_rows(os.path.join(root, PATH_MASTER))
    joiners, jh = read_csv_rows(os.path.join(root, PATH_JOINERS))
    leavers, lh = read_csv_rows(os.path.join(root, PATH_LEAVERS))
    gaps = {}
    for name, headers in (("headcount-master", mh), ("planned-joiners", jh), ("planned-leavers", lh)):
        missing = [c for c in REQUIRED_COLUMNS[name] if c not in headers]
        if missing:
            gaps[name] = missing
    if gaps:
        raise ContractMismatch(gaps)
    state["evidence"].append("정제 데이터 행 수: 마스터 %d · 입사 예정 %d · 퇴사 예정 %d (헤더 §3 준수)" % (len(master), len(joiners), len(leavers)))
    state["tried"].append("정제 CSV 3종을 읽고 REQUIRED_COLUMNS로 계약 §3 헤더를 검사")

    # 조직 순서: org-chart(§1) → 마스터/입사예정자에서 보강
    depts: List[Dict[str, str]] = []
    org_path = os.path.join(root, PATH_ORG_CHART)
    if os.path.exists(org_path):
        for r in read_csv_rows(org_path)[0]:
            if r.get("deptCode"):
                depts.append({"deptCode": r.get("deptCode", ""), "department": r.get("department", "")})
        state["evidence"].append("조직 체계 org-chart.csv: 조직 %d개 (byDepartment 순서·명칭 기준)" % len(depts))
    else:
        warnings.append("org-chart.csv 없음 — 조직 순서·명칭을 정제 데이터에서 유도")
    dept_by_code = {d["deptCode"]: d for d in depts}
    for r in master + joiners:
        code = r.get("deptCode", "")
        if code and code not in dept_by_code:
            dept_by_code[code] = {"deptCode": code, "department": r.get("department", code)}
            depts.append(dept_by_code[code])
            if os.path.exists(org_path):
                warnings.append("조직 체계에 없는 조직 코드 '%s'" % code)

    master_by_id = {r.get("empId", ""): r for r in master}
    risks: List[Dict[str, str]] = []

    def add_risk(emp_id: str, flag: str, issue: Optional[str] = None, impact: Optional[str] = None) -> None:
        pair = FLAG_RISK.get(flag) or DERIVED_FLAGS.get(flag) or ("미해결 항목 (%s)" % flag, "급여 산정 근거 확인 필요")
        risks.append({"empId": emp_id, "issue": issue or pair[0], "impact": impact or pair[1], "unresolvedFlag": flag})

    # 1. 급여 대상 인원 (기준일): 재직 + 휴직 = 총원
    active = [r for r in master if r.get("status") == ACTIVE]
    leave_rows = [r for r in master if r.get("status") == ON_LEAVE]
    other = len(master) - len(active) - len(leave_rows)
    if other:
        warnings.append("재직상태가 재직/휴직이 아닌 마스터 행 %d건 — 급여 대상에서 제외" % other)
    payroll_rows = active + leave_rows

    # 2. 월말까지 입사 예정 (plannedIn): 예정일 ≤ 월말
    planned_joiners: List[Dict[str, Any]] = []
    for j in joiners:
        d = parse_date(j.get("plannedHireDate"))
        if d is None:
            add_risk(j.get("joinerId", ""), "date-format", "입사 예정일 미확정(파싱 불가) → 급여 등록 대상에서 제외", "입사자 급여 등록 누락 위험")
            continue
        if d > period_end:
            continue
        if d <= as_of:
            add_risk(j.get("joinerId", ""), "date-logic", "입사 예정일이 기준일 이전인데 마스터 미등록", "입사 처리 누락 시 급여 미지급 위험")
        w = worked(max(d, period_start), period_end, dim)
        planned_joiners.append({"joinerId": j.get("joinerId", ""), "name": j.get("name", ""), "deptCode": j.get("deptCode", ""),
                                "plannedHireDate": iso(d), "employmentType": j.get("employmentType", ""),
                                "workedDays": w, "proratedRatio": ratio(w, dim)})

    # 3. 월말까지 퇴사 예정 (plannedOut): 예정일 ≤ 월말, unknown-emp(마스터 없음) 제외, stale 포함(퇴사로 반영)
    #    §4-5: 휴직자의 퇴사 예정은 monthEndActive(재직 기준)에서 제외하되 monthEndTotal에는 반영
    planned_leavers: List[Dict[str, Any]] = []
    for lv in leavers:
        emp_id, fl = lv.get("empId", ""), flags_of(lv.get("unresolvedFlags"))
        d = parse_date(lv.get("plannedTerminationDate"))
        if d is None:
            add_risk(emp_id, "date-format", "퇴사 예정일 미확정(파싱 불가) → 정산 대상에서 제외", "퇴직 정산 누락 위험")
            continue
        if d > period_end:
            continue
        m = master_by_id.get(emp_id)
        if m is None or m.get("status") not in (ACTIVE, ON_LEAVE):
            add_risk(emp_id, "unknown-emp")
            continue
        if m.get("status") == ON_LEAVE:
            add_risk(emp_id, "leaver-not-active")
        if "stale-planned-leaver" in fl:
            add_risk(emp_id, "stale-planned-leaver")
        w = worked(max(parse_date(m.get("hireDate")) or period_start, period_start), d, dim)
        planned_leavers.append({"empId": emp_id, "name": m.get("name", ""), "deptCode": lv.get("deptCode") or m.get("deptCode", ""),
                                "plannedTerminationDate": iso(d), "separationType": lv.get("separationType", ""),
                                "employmentType": m.get("employmentType", ""), "status": m.get("status", ""),
                                "workedDays": w, "proratedRatio": ratio(w, dim)})
    out_active_rows = [x for x in planned_leavers if x["status"] == ACTIVE]
    out_leave_rows = [x for x in planned_leavers if x["status"] == ON_LEAVE]

    # 4. 집계 — §4-5: byEmploymentType = {유형: {asOfTotal, monthEndTotal}} (총원 기준)
    type_all, type_in, type_out = count_by(payroll_rows, "employmentType"), count_by(planned_joiners, "employmentType"), count_by(planned_leavers, "employmentType")
    type_keys = EMPLOYMENT_TYPES + sorted((set(type_all) | set(type_in)) - set(EMPLOYMENT_TYPES))
    by_employment_type = {k: {"asOfTotal": type_all.get(k, 0),
                              "monthEndTotal": type_all.get(k, 0) + type_in.get(k, 0) - type_out.get(k, 0)} for k in type_keys}
    for k in type_keys[len(EMPLOYMENT_TYPES):]:
        warnings.append("정규 값이 아닌 고용유형 '%s' %d건" % (k, type_all.get(k, 0) + type_in.get(k, 0)))

    a_d, l_d, in_d = count_by(active, "deptCode"), count_by(leave_rows, "deptCode"), count_by(planned_joiners, "deptCode")
    out_a_d, out_l_d = count_by(out_active_rows, "deptCode"), count_by(out_leave_rows, "deptCode")
    by_department = []
    for d in depts:
        c = d["deptCode"]
        a, l, i, oa, ol = a_d.get(c, 0), l_d.get(c, 0), in_d.get(c, 0), out_a_d.get(c, 0), out_l_d.get(c, 0)
        by_department.append({"deptCode": c, "department": d["department"], "asOfActive": a, "asOfOnLeave": l, "asOfTotal": a + l,
                              "plannedIn": i, "plannedOut": oa + ol, "monthEndActive": a + i - oa, "monthEndTotal": a + l + i - oa - ol})

    as_of_active, as_of_on_leave = len(active), len(leave_rows)
    month_end_active = as_of_active + len(planned_joiners) - len(out_active_rows)
    month_end_total = as_of_active + as_of_on_leave + len(planned_joiners) - len(planned_leavers)
    state["tried"].append("급여 대상 인원 집계: 기준일 재직 %d + 휴직 %d = 총원 %d → 월말 재직 %d(+%d −%d) / 월말 총원 %d" % (
        as_of_active, as_of_on_leave, as_of_active + as_of_on_leave, month_end_active, len(planned_joiners), len(out_active_rows), month_end_total))

    # 5. 당월 입사자(마스터에 이미 있음): hireDate ∈ [월초, 기준일]. 마스터에 퇴직 행이 없으므로 당월 퇴직자 목록은 없다(§2-1)
    joiners_in_period = []
    for r in payroll_rows:
        hd = parse_date(r.get("hireDate"))
        if hd and hd > as_of:
            add_risk(r.get("empId", ""), "hire-after-as-of")
        elif hd and period_start <= hd <= as_of:
            w = worked(hd, period_end, dim)
            joiners_in_period.append({"empId": r.get("empId", ""), "name": r.get("name", ""), "deptCode": r.get("deptCode", ""),
                                      "hireDate": iso(hd), "employmentType": r.get("employmentType", ""),
                                      "workedDays": w, "proratedRatio": ratio(w, dim)})
    joiners_in_period.sort(key=lambda x: (x["hireDate"], x["empId"]))
    planned_joiners.sort(key=lambda x: (x["plannedHireDate"], x["joinerId"]))
    planned_leavers.sort(key=lambda x: (x["plannedTerminationDate"], x["empId"]))

    # 6. 휴직자 급여 처리 구분
    on_leave, by_treatment = [], {k: 0 for k in TREATMENT_ORDER}
    for r in leave_rows:
        lt = (r.get("leaveType") or "").strip()
        treatment = LEAVE_TREATMENT.get(lt)
        if treatment is None:
            treatment = LEAVE_TREATMENT["기타"]
            if "status-inconsistency" not in flags_of(r.get("unresolvedFlags")):
                add_risk(r.get("empId", ""), "status-inconsistency", "휴직인데 휴직유형 '%s' → 무급으로 가정" % (lt or "(빈값)"))
        on_leave.append({"empId": r.get("empId", ""), "name": r.get("name", ""), "deptCode": r.get("deptCode", ""),
                         "leaveType": lt or "기타", "leaveStart": iso(parse_date(r.get("leaveStart"))), "payrollTreatment": treatment})
        by_treatment[treatment] += 1
    on_leave.sort(key=lambda x: (x["leaveStart"] or "", x["empId"]))

    # 7. 90일 내 계약 만료 (재직+휴직). byMonth는 창에 걸치는 모든 월(0건도 키 유지)
    expiring, by_month = [], {k: 0 for k in months_between(as_of, window_end)}
    for r in payroll_rows:
        cd = parse_date(r.get("contractEndDate"))
        if cd is None:
            continue
        if r.get("employmentType") == "정규직":
            warnings.append("정규직 %s 에 계약종료일 존재 — 고용유형 확인 필요" % r.get("empId", ""))
        if cd < as_of:
            add_risk(r.get("empId", ""), "contract-expired-active")
        elif cd <= window_end:
            expiring.append({"empId": r.get("empId", ""), "name": r.get("name", ""), "deptCode": r.get("deptCode", ""),
                             "employmentType": r.get("employmentType", ""), "contractEndDate": iso(cd)})
            by_month[month_key(cd)] += 1
    expiring.sort(key=lambda x: (x["contractEndDate"], x["empId"]))

    # 8. 급여 오류 위험 — 마스터 미해결 플래그(총원) + 위 파생. 같은 (사번, 플래그, 이슈)는 1건
    for r in payroll_rows:
        for fl in flags_of(r.get("unresolvedFlags")):
            add_risk(r.get("empId", ""), fl)
    seen, deduped = set(), []
    for rk in risks:
        key = (rk["empId"], rk["unresolvedFlag"], rk["issue"])
        if key not in seen:
            seen.add(key)
            deduped.append(rk)
    risks = deduped
    state["tried"].append("일할 계산 대상(당월 입사 %d · 월말까지 입사 예정 %d · 퇴사 예정 %d), 휴직 처리 %d, 90일 계약 만료 %d, 위험 %d건 산출" % (
        len(joiners_in_period), len(planned_joiners), len(planned_leavers), len(on_leave), len(expiring), len(risks)))

    # 9. 대사: forecast.totals.forecastMonthEnd == monthEndActive (assert) + 조직별 forecastMonthEnd; stats 소프트 대사; 내부 합계
    forecast = read_json(os.path.join(root, PATH_FORECAST))
    recon: Dict[str, Any] = {"recomputedMonthEndActive": month_end_active, "forecastMonthEnd": None, "matched": None,
                             "byDepartmentMismatches": [], "statsActiveHeadcount": None, "statsOnLeave": None, "statsMatched": None,
                             "internal": {}}
    if forecast is None:
        warnings.append("month-end-forecast.json 없음 — monthEndActive(%d) 대사를 건너뜀(assert skip)" % month_end_active)
    else:
        fc_total = (forecast.get("totals") or {}).get("forecastMonthEnd")
        recon["forecastMonthEnd"] = fc_total
        fc_depts = {d.get("deptCode"): d for d in (forecast.get("byDepartment") or [])}
        for row in by_department:
            fd = fc_depts.get(row["deptCode"])
            if fd is not None and fd.get("forecastMonthEnd") != row["monthEndActive"]:
                recon["byDepartmentMismatches"].append({"deptCode": row["deptCode"], "payrollClose": row["monthEndActive"],
                                                        "forecast": fd.get("forecastMonthEnd")})
        recon["matched"] = (fc_total == month_end_active) and not recon["byDepartmentMismatches"]
        state["evidence"].append("month-end-forecast.totals.forecastMonthEnd = %s (조직별 %d개 대조)" % (fc_total, len(fc_depts)))
    stats = read_json(os.path.join(root, PATH_STATS))
    if stats is not None:
        t = stats.get("totals") or {}
        recon["statsActiveHeadcount"], recon["statsOnLeave"] = t.get("activeHeadcount"), t.get("onLeave")
        recon["statsMatched"] = (t.get("activeHeadcount") == as_of_active and t.get("onLeave") == as_of_on_leave)
        if not recon["statsMatched"]:
            warnings.append("headcount-stats 재직/휴직(%s/%s) vs 급여 마감(%d/%d) 불일치" % (
                t.get("activeHeadcount"), t.get("onLeave"), as_of_active, as_of_on_leave))
    internal = {
        "byDepartmentAsOfTotal": sum(x["asOfTotal"] for x in by_department) == as_of_active + as_of_on_leave,
        "byDepartmentMonthEndActive": sum(x["monthEndActive"] for x in by_department) == month_end_active,
        "byDepartmentMonthEndTotal": sum(x["monthEndTotal"] for x in by_department) == month_end_total,
        "byEmploymentTypeAsOfTotal": sum(v["asOfTotal"] for v in by_employment_type.values()) == as_of_active + as_of_on_leave,
        "byEmploymentTypeMonthEndTotal": sum(v["monthEndTotal"] for v in by_employment_type.values()) == month_end_total,
        "byTreatmentSum": sum(by_treatment.values()) == len(on_leave),
        "contractsByMonthSum": sum(by_month.values()) == len(expiring),
    }
    recon["internal"] = internal
    if not all(internal.values()):
        warnings.append("내부 합계 불일치: %s" % [k for k, v in internal.items() if not v])

    # 10. 체크리스트 (§4-5: status ∈ pending|done — 대상 0건 = done)
    def item(name: str, count: int) -> Dict[str, Any]:
        return {"item": name, "count": count, "status": "pending" if count else "done"}
    checklist = [
        item("당월 입사자 일할 계산 확인", len(joiners_in_period)),
        item("월말까지 입사 예정자 급여 등록 준비", len(planned_joiners)),
        item("월말까지 퇴사 예정자 최종 정산 준비", len(planned_leavers)),
        item("휴직자 급여 처리 구분 확인", len(on_leave)),
        item("90일 내 계약 만료자 갱신·종료 확인", len(expiring)),
        item("급여 오류 위험(미해결 항목) 확인", len(risks)),
        {"item": "급여 대상 인원 월말 예측 대사(forecastMonthEnd == monthEndActive)", "count": 0 if recon["matched"] else 1,
         "status": "done" if recon["matched"] else "pending"},
    ]

    out: Dict[str, Any] = {
        "asOfDate": iso(as_of), "payPeriod": month_key(as_of), "periodStart": iso(period_start), "periodEnd": iso(period_end),
        "payrollHeadcount": {"asOfActive": as_of_active, "asOfOnLeave": as_of_on_leave, "asOfTotal": as_of_active + as_of_on_leave,
                             "monthEndActive": month_end_active, "monthEndTotal": month_end_total,
                             "byEmploymentType": by_employment_type,
                             "byDepartment": [project(x, KEYS_BY_DEPT) for x in by_department]},
        "prorations": {"joinersInPeriod": [project(x, KEYS_JOINER_IN) for x in joiners_in_period],
                       "plannedJoinersByMonthEnd": [project(x, KEYS_PLANNED_JOINER) for x in planned_joiners],
                       "plannedLeaversByMonthEnd": [project(x, KEYS_PLANNED_LEAVER) for x in planned_leavers]},
        "leaves": {"onLeave": [project(x, KEYS_ON_LEAVE) for x in on_leave], "byTreatment": by_treatment},
        "contracts": {"expiringWithin90Days": [project(x, KEYS_EXPIRING) for x in expiring], "byMonth": by_month},
        "risks": risks,
        "checklist": checklist,
        "provenance": {},
    }
    cleansing_summary = read_json(os.path.join(root, PATH_CLEANSING_SUMMARY))
    persona = apply_persona_needs(root, out,
                                  {"payroll-close": out, "month-end-forecast": forecast, "headcount-stats": stats, "cleansing-summary": cleansing_summary},
                                  {"headcount-master": mh, "planned-joiners": jh, "planned-leavers": lh})
    out["provenance"] = {
        "sources": [PATH_MASTER, PATH_JOINERS, PATH_LEAVERS, PATH_FORECAST, PATH_ORG_CHART, PATH_PERSONA_NEEDS],
        "script": SCRIPT_PATH, "asOfDate": iso(as_of),
        "rules": {"payrollHeadcount": "급여 대상 = 재직 + 휴직(총원). monthEndActive = 재직 + plannedIn − plannedOut(재직자만), monthEndTotal = 총원 + plannedIn − plannedOut(휴직자 포함)",
                  "plannedIn": "정제 입사 예정자 중 예정일 ≤ 월말", "plannedOut": "정제 퇴사 예정자 중 예정일 ≤ 월말, 마스터에 없는 사번(unknown-emp) 제외, stale 포함",
                  "proratedRatio": "당월 근무일수 / %d, 소수 3자리" % dim, "leaveTreatment": LEAVE_TREATMENT,
                  "contractWindowDays": CONTRACT_WINDOW_DAYS, "derivedFlags": sorted(DERIVED_FLAGS), "pii": "성명 포함(급여 업무), 생년월일·연령대·급여액 없음"},
        "reconciliation": recon, "personaNeeds": persona, "warnings": warnings,
    }
    target = target_check(as_of, out["payrollHeadcount"], by_employment_type)
    summary = {
        "payrollHeadcount": {k: out["payrollHeadcount"][k] for k in ("asOfActive", "asOfOnLeave", "asOfTotal", "monthEndActive", "monthEndTotal")},
        "plannedIn": len(planned_joiners), "plannedOut": len(planned_leavers), "plannedOutFromLeave": len(out_leave_rows),
        "byEmploymentType": by_employment_type,
        "prorations": {"joinersInPeriod": len(joiners_in_period), "plannedJoinersByMonthEnd": len(planned_joiners),
                       "plannedLeaversByMonthEnd": len(planned_leavers)},
        "leaves": {"onLeave": len(on_leave), "byTreatment": by_treatment},
        "contracts": {"expiringWithin90Days": len(expiring), "byMonth": by_month},
        "risks": len(risks), "riskFlags": sorted(set(r["unresolvedFlag"] for r in risks)),
        "checklist": {"total": len(checklist), "pending": sum(1 for c in checklist if c["status"] != "done")},
        "reconciliation": recon, "targetCheck": target, "personaNeeds": persona, "warnings": warnings,
    }
    return out, summary


def target_check(as_of: date, ph: Dict[str, Any], by_type: Dict[str, Dict[str, int]]) -> Dict[str, Any]:
    """§2-7 정본 대조 — 데모 기준일에서만 의미가 있다."""
    if iso(as_of) != DEFAULT_AS_OF:
        return {"applicable": False, "reason": "기준일이 데모 기준일(%s)과 다름" % DEFAULT_AS_OF}
    mismatches = []
    for k, v in TARGETS.items():
        if k == "byEmploymentType":
            for t, n in v.items():
                actual = (by_type.get(t) or {}).get("asOfTotal")
                if actual != n:
                    mismatches.append({"metric": "byEmploymentType.%s.asOfTotal" % t, "expected": n, "actual": actual})
        elif ph.get(k) != v:
            mismatches.append({"metric": k, "expected": v, "actual": ph.get(k)})
    return {"applicable": True, "matched": not mismatches, "mismatches": mismatches}


# ---------------------------------------------------------------- persona needs (§9 → checklist)
ALIASES = {"forecast": "month-end-forecast", "stats": "headcount-stats", "payroll": "payroll-close", "payrollClose": "payroll-close",
           "master": "headcount-master", "joiners": "planned-joiners", "leavers": "planned-leavers", "cleansingSummary": "cleansing-summary"}


def resolve_ref(ref: str, jsons: Dict[str, Any], headers: Dict[str, List[str]]) -> Optional[bool]:
    """evidence 참조가 산출물·정제 헤더에서 해소되는가. True 해소 / False 미확보 / None 검증 불가(출처 미생성·미상)."""
    ref = (ref or "").strip()
    if not ref or ref.startswith(("policy:", "site/", "reports/")):
        return True   # 데이터 필드가 아니다 — product-judge·mailer의 몫
    if ref.startswith("reconciliation:"):
        ref = ref[len("reconciliation:"):].replace("=", ";")
    if ";" in ref:
        rs = [resolve_ref(p, jsons, headers) for p in ref.split(";") if p.strip()]
        return False if any(r is False for r in rs) else (None if any(r is None for r in rs) else True)
    ref = ref.split(" ")[0]
    parts = [p for p in ref.replace("[]", "").replace(".json", "").replace(".clean", "").replace(".csv", "").split(".") if p]
    if not parts:
        return None
    src, rest = ALIASES.get(parts[0], parts[0]), parts[1:]
    if src in jsons:
        node = jsons[src]
        if node is None:
            return None
        for k in rest:
            if isinstance(node, list):
                if not node:
                    return True
                node = node[0]
            if not isinstance(node, dict) or k not in node:
                return False
            node = node[k]
        return True
    if src in headers:
        return True if not rest else rest[0] in headers[src]
    return None


def apply_persona_needs(root: str, out: Dict[str, Any], jsons: Dict[str, Any], headers: Dict[str, List[str]]) -> Dict[str, Any]:
    result: Dict[str, Any] = {"applied": False, "missingFields": [], "missingCriteria": [], "unverifiable": []}
    path = os.path.join(root, PATH_PERSONA_NEEDS)
    if not os.path.exists(path):
        result["reason"] = "persona-needs.json 없음 — 건너뜀"
        return result
    try:
        personas = (read_json(path) or {}).get("personas") or []
    except Exception as exc:  # noqa: BLE001 — 니즈 파일 결함이 급여 마감을 막지 않는다
        result["reason"] = "persona-needs.json 파싱 실패: %s" % exc
        return result
    persona = next((p for p in personas if isinstance(p, dict) and p.get("code") == PERSONA_CODE), None)
    if persona is None:
        result["reason"] = "persona code '%s' 없음" % PERSONA_CODE
        return result
    result["applied"] = True
    for f in persona.get("requiredFields") or []:
        ok = resolve_ref(str(f), jsons, headers)
        if ok is False:
            result["missingFields"].append(str(f))
        elif ok is None:
            result["unverifiable"].append(str(f))
    for c in persona.get("fitCriteria") or []:
        if not isinstance(c, dict):
            continue
        ok = resolve_ref(str(c.get("evidence") or ""), jsons, headers)
        if ok is False:
            result["missingCriteria"].append({k: c.get(k) for k in ("id", "criterion", "weight", "evidence")})
        elif ok is None:
            result["unverifiable"].append("%s:%s" % (c.get("id"), c.get("evidence")))
    for f in result["missingFields"]:
        out["checklist"].append({"item": "니즈 필드 미확보: %s" % f, "count": 1, "status": "pending"})
    for c in result["missingCriteria"]:
        out["checklist"].append({"item": "니즈 기준 미충족 [%s]: %s" % (c.get("id"), c.get("criterion")), "count": 1, "status": "pending"})
    if result["unverifiable"]:
        out["checklist"].append({"item": "니즈 근거 검증 불가(출처 미생성/미상): %d건" % len(result["unverifiable"]),
                                 "count": len(result["unverifiable"]), "status": "pending"})
    return result


# ---------------------------------------------------------------- main
def finish(state: Dict[str, Any], line: Dict[str, Any], code: int) -> int:
    line["handoffLog"] = write_handoff(state)
    print(json.dumps(line, ensure_ascii=False))
    return code


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="급여 마감(payroll-close) — DATA_CONTRACT v2 §10")
    ap.add_argument("--root", default=DEFAULT_ROOT)
    ap.add_argument("--as-of", default=DEFAULT_AS_OF)
    ap.add_argument("--allow-mismatch", action="store_true", help="예측과 불일치해도 계약 경로에 쓴다(종료 코드는 2)")
    args = ap.parse_args(argv)
    root = os.path.abspath(args.root)
    state = new_state(root, args.as_of)
    write_handoff(state)   # 실행 시작 기록 — 중간에 죽어도 다음 실행자가 어디까지 왔는지 안다
    as_of = parse_date(args.as_of)
    if as_of is None:
        state["status"], state["failed"] = "error", ["--as-of 형식 오류: %s (YYYY-MM-DD 필요)" % args.as_of]
        state["next"] = ["오케스트레이터가 asOfDate 인자를 고쳐 재실행"]
        return finish(state, {"status": "error", "error": "--as-of 형식 오류: %s" % args.as_of}, 1)
    missing = [p for p in (PATH_MASTER, PATH_JOINERS, PATH_LEAVERS) if not os.path.exists(os.path.join(root, p))]
    if missing:
        state["status"], state["failed"] = "input-missing", ["필수 입력 없음: %s" % ", ".join(missing)]
        state["next"] = ["people-data-cleanser(02-cleanse)가 먼저 실행되어야 한다 — 정제 데이터 없이 만든 급여 마감은 대사할 수 없다"]
        return finish(state, {"status": "input-missing", "missing": missing, "requires": "people-data-cleanser"}, 3)
    warnings: List[str] = []
    try:
        out, summary = build(root, as_of, warnings, state)
    except ContractMismatch as exc:
        state["status"], state["failed"] = "contract-mismatch", ["정제 CSV 헤더가 DATA_CONTRACT v2 §3과 다름: %s" % json.dumps(exc.gaps, ensure_ascii=False)]
        state["next"] = ["DATA_CONTRACT §3 ↔ people-data-cleanser ↔ 이 스크립트 REQUIRED_COLUMNS 정렬 패스가 먼저다 — 스크립트를 즉석에서 고치지 않는다"]
        return finish(state, {"status": "contract-mismatch", "missingColumns": exc.gaps,
                              "note": "정제 CSV 헤더가 DATA_CONTRACT v2 §3과 다르다"}, 4)
    except Exception as exc:  # noqa: BLE001
        state["status"], state["failed"] = "error", ["예외 %s: %s" % (type(exc).__name__, exc)]
        state["next"] = ["예외 메시지를 반환값 notes에 그대로 싣고 harness/evolve로 넘긴다"]
        return finish(state, {"status": "error", "error": "%s: %s" % (type(exc).__name__, exc)}, 1)

    recon = summary["reconciliation"]
    matched = recon["matched"]
    failed = matched is False
    target_path = os.path.join(root, PATH_UNRECONCILED if (failed and not args.allow_mismatch) else PATH_OUTPUT)
    os.makedirs(os.path.dirname(target_path), exist_ok=True)
    with open(target_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
        f.write("\n")
    log("wrote %s" % target_path)
    artifact = os.path.relpath(target_path, root)
    status = "reconciliation-failed" if failed else ("ok" if matched else "ok-unverified")

    # 핸드오프 로그 마무리
    ph, tc, pn = summary["payrollHeadcount"], summary["targetCheck"], summary["personaNeeds"]
    state["status"] = status
    state["tried"].append("산출물 기록: `%s` (indent 2, UTF-8, 시각 필드 없음 — 같은 입력이면 같은 파일)" % artifact)
    state["tried"].append("페르소나 니즈 반영: applied=%s, 미확보 필드 %d, 미충족 기준 %d, 검증 불가 %d" % (
        pn.get("applied"), len(pn.get("missingFields", [])), len(pn.get("missingCriteria", [])), len(pn.get("unverifiable", []))))
    if pn.get("reason"):
        state["failed"].append("persona-needs 미반영: %s" % pn["reason"])
    for w in warnings:
        state["failed"].append("경고: " + w)
    if failed:
        state["failed"].append("대사 실패: monthEndActive %s ≠ forecastMonthEnd %s, 조직별 불일치 %s — 원인 후보는 plannedOut 규칙 차이(stale/unknown-emp/휴직자 처리)이며 단정하지 않는다" % (
            ph["monthEndActive"], recon["forecastMonthEnd"], json.dumps(recon["byDepartmentMismatches"], ensure_ascii=False)))
    elif matched:
        state["verified"].append("대사 일치: monthEndActive %d == forecast.totals.forecastMonthEnd %s, 조직별 forecastMonthEnd 전부 일치" % (ph["monthEndActive"], recon["forecastMonthEnd"]))
    else:
        state["failed"].append("예측 파일 없음 — 대사 미수행(ok-unverified). headcount-forecaster(04-forecast) 후 재실행 필요")
    if recon.get("statsMatched") is not None:
        (state["verified"] if recon["statsMatched"] else state["failed"]).append(
            "headcount-stats 재직/휴직 대사: %s/%s vs %d/%d" % (recon["statsActiveHeadcount"], recon["statsOnLeave"], ph["asOfActive"], ph["asOfOnLeave"]))
    ok_internal = [k for k, v in recon["internal"].items() if v]
    if ok_internal:
        state["verified"].append("내부 합계 일치: " + ", ".join(ok_internal))
    if tc.get("applicable"):
        (state["verified"] if tc["matched"] else state["failed"]).append(
            "§2-7 정본 대조(406/21/427/411/432, 고용유형 354/31/19/23): %s" % ("일치" if tc["matched"] else json.dumps(tc["mismatches"], ensure_ascii=False)))
    state["verified"].append("급여 대상 %d(재직 %d+휴직 %d) → 월말 재직 %d / 월말 총원 %d · 일할 대상 %d/%d/%d · 휴직 처리 %s · 계약 만료 %d · 위험 %d(%s) · 체크리스트 pending %d/%d" % (
        ph["asOfTotal"], ph["asOfActive"], ph["asOfOnLeave"], ph["monthEndActive"], ph["monthEndTotal"],
        summary["prorations"]["joinersInPeriod"], summary["prorations"]["plannedJoinersByMonthEnd"], summary["prorations"]["plannedLeaversByMonthEnd"],
        json.dumps(summary["leaves"]["byTreatment"], ensure_ascii=False), summary["contracts"]["expiringWithin90Days"],
        summary["risks"], ",".join(summary["riskFlags"]), summary["checklist"]["pending"], summary["checklist"]["total"]))
    state["next"] = [
        "product-builder(09-products): `%s`를 site/data/payroll.json = {payrollClose, statsSubset, cleansingSummary}에 싣는다. monthEndActive(재직 기준)와 monthEndTotal(휴직 포함)을 구분 표기" % artifact,
        "product-judge(persona-advocate:payroll): fitCriteria evidence가 이 산출물 경로를 가리킨다. 미충족 기준은 checklist의 '니즈 기준 미충족 [id]' 항목",
        "people-data-auditor(11-test): test_reconciliation.py에서 payrollHeadcount asOfActive/asOfOnLeave/asOfTotal/monthEndActive/monthEndTotal = 406/21/427/411/432 대사",
        "onboarding-plan-analyst(07-onboarding)는 병렬 형제 — 이 산출물을 읽지 않는다",
    ]
    if failed:
        state["next"].insert(0, "대사 실패 — 산출물은 `%s`에만 있다. reconciliation-policy 절차(감사자·예측자 확인) 후 재실행. 어느 쪽이 맞는지 이 단계는 판정하지 않는다" % artifact)
    line = {"status": status, "asOfDate": out["asOfDate"], "payPeriod": out["payPeriod"], "artifact": artifact}
    line.update(summary)
    return finish(state, line, 2 if failed else 0)


if __name__ == "__main__":
    sys.exit(main())
