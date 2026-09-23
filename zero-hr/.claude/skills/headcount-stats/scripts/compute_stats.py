#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""compute_stats.py — 인원 통계(headcount-stats) 집계기. DATA_CONTRACT v2 §4-1 · §4-5.

정제 데이터(data/clean/)에서만 읽는다. 원천(data/raw/)은 읽지 않는다.
  data/clean/headcount-master.clean.csv   필수 — 총원 427 = 재직 406 + 휴직 21 (1사번 1행, 퇴직 행 없음)
  data/reference/org-chart.csv            권장 — 조직 그룹(4) > 조직(11) 골격·순서
  data/reference/company-stages.json      선택 — stage 가 비어 있는 행의 보충용
  data/clean/to-plan.clean.csv            권장 — toHeadcount (TO 비교는 재직 인원 기준)
  data/clean/planned-joiners.clean.csv    권장 — totals.plannedIn (월말까지)
  data/clean/planned-leavers.clean.csv    권장 — totals.plannedOut · plannedSeparations
                                                 (unknown-emp 제외 · 마스터 재직자만 · stale 포함 — §4-5)
출력: data/stats/headcount-stats.json (§4-1 shape). stdout 마지막 줄 = 요약 JSON 1행(워크플로우 반환 데이터).
핸드오프 로그: _workspace/handoff/03-stats.md — 실행 시작 시 1회, 종료 시 1회(성공·실패 모두) 쓴다 (Operating Rule 2).

대사(assert, §4-5): byAttribute.* 8개 합 = 406(재직) · byAttributeAll.employmentType/status 합 = 427 · leaveType 합 = 21 ·
crossTabs.* 7개 셀 합 = 406 · Σ byDepartment = Σ byOrgGroup = totals · plannedSeparations 합 = totals.plannedOut.
실패하면 산출물을 쓰지 않고 errorType=reconciliation 으로 종료한다.
targetCheck: §2-7 정본(조직표 HC/OL/TO · 조직 그룹 · 속성 분포 8종 · 퇴사 예정 사유/월별 · Executive Snapshot)과 대조해
stdout 요약에만 싣는다(산출물에는 넣지 않는다). 불일치는 집계 오류가 아니라 정제 데이터 확인 신호다.

Python 3.9 표준 라이브러리만. 사용법: python3 compute_stats.py --root R --as-of 2026-09-23
종료 코드: 0 정상 · 1 오류/대사 실패 · 3 필수 입력 없음(blocked)
"""
import argparse
import calendar
import csv
import json
import os
import statistics
import sys
from datetime import date, datetime

DEFAULT_ROOT = "/Users/yang/development/zero-hr"
DEFAULT_AS_OF = "2026-09-23"
CLIENT_NAME = "㈜온다테크"
AGENT_NAME = "headcount-statistician"
PHASE = "03-stats"
SCRIPT_REL = ".claude/skills/headcount-stats/scripts/compute_stats.py"

REL = {
    "master": "data/clean/headcount-master.clean.csv",
    "org": "data/reference/org-chart.csv",
    "stages": "data/reference/company-stages.json",
    "to": "data/clean/to-plan.clean.csv",
    "joiners": "data/clean/planned-joiners.clean.csv",
    "leavers": "data/clean/planned-leavers.clean.csv",
    "out": "data/stats/headcount-stats.json",
    "handoff": "_workspace/handoff/%s.md" % PHASE,
}
FLAG_UNKNOWN_EMP = "unknown-emp"
FLAG_STALE = "stale-planned-leaver"
UNKNOWN = "미상"
HANDOFF_SECTIONS = ["시도한 것", "본 데이터·근거", "실패한 것", "검증된 것", "다음 agent 인계점"]

# 정규 값 순서(§3-1) — 딕셔너리 키 순서를 결정적으로 만든다. 관측된 값만 싣는다(0 키 없음, 계약 예시와 동일).
ORDER = {
    "employmentType": ["정규직", "계약직", "인턴", "파견"],
    "status": ["재직", "휴직"],
    "gender": ["여성", "남성", "미응답"],
    "ageBand": ["20대", "30대", "40대", "50대+"],
    "jobFamily": ["Engineering", "Product", "Design", "Sales", "Marketing", "Customer Success",
                  "People", "Finance", "Legal", "Data/AI", "Executive"],
    "level": ["IC1", "IC2", "IC3", "Senior", "Lead", "Manager", "Director", "VP"],
    "tenureBand": ["1년 미만", "1~3년", "3~5년", "5년+"],
    "totalExperienceBand": ["0~3년", "3~7년", "7~12년", "12년+"],
    "stage": ["Seed", "Series A", "Scale-up", "Enterprise"],
    "leaveType": ["육아휴직", "질병휴직", "기타"],
    "separationReason": ["자발퇴사", "개인사유", "계약만료", "조직개편", "성과/적합도", "건강", "정년"],
    "separationType": ["자발적", "비자발적"],
}
ATTRIBUTES_ACTIVE = ["employmentType", "gender", "ageBand", "jobFamily", "level",
                     "tenureBand", "totalExperienceBand", "stage"]
CROSS_TABS = [
    ("departmentByEmploymentType", "department", "employmentType"),
    ("departmentByGender", "department", "gender"),
    ("departmentByAgeBand", "department", "ageBand"),
    ("departmentByLevel", "department", "level"),
    ("jobFamilyByLevel", "jobFamily", "level"),
    ("jobFamilyByStage", "jobFamily", "stage"),
    ("orgGroupByTenureBand", "orgGroup", "tenureBand"),
]
BRIEF_DISCREPANCY = "브리프 §7 조직 그룹 합(215/119/62)은 조직표 합(220/128/48)과 불일치 — 조직표 기준 채택"

# ---- §2-7 정본 (stdout targetCheck 전용 — 산출물에는 넣지 않는다)
EXPECTED_DEPT = {  # deptCode: (재직 HC, 휴직 OL, TO)
    "D01": (10, 0, 10), "D02": (51, 3, 54), "D03": (104, 6, 112), "D04": (25, 1, 26), "D05": (40, 2, 34),
    "D06": (58, 3, 62), "D07": (30, 1, 32), "D08": (40, 3, 42), "D09": (18, 1, 18), "D10": (19, 1, 20), "D11": (11, 0, 12),
}
EXPECTED_GROUP_ACTIVE = {"G0": 10, "G1": 220, "G2": 128, "G3": 48}
EXPECTED_TOTALS = {"headcount": 427, "activeHeadcount": 406, "onLeave": 21, "toHeadcount": 422,
                   "toGapAsOf": -16, "plannedIn": 19, "plannedOut": 14}
EXPECTED_ATTR = {  # 8종 — employmentType 만 총원 427, 나머지 재직 406
    "employmentType": {"정규직": 354, "계약직": 31, "인턴": 19, "파견": 23},
    "gender": {"여성": 188, "남성": 195, "미응답": 23},
    "ageBand": {"20대": 82, "30대": 221, "40대": 83, "50대+": 20},
    "jobFamily": {"Engineering": 116, "Product": 55, "Design": 25, "Sales": 58, "Marketing": 30, "Customer Success": 40,
                  "People": 18, "Finance": 19, "Legal": 11, "Data/AI": 24, "Executive": 10},
    "level": {"IC1": 33, "IC2": 65, "IC3": 82, "Senior": 89, "Lead": 55, "Manager": 44, "Director": 25, "VP": 13},
    "tenureBand": {"1년 미만": 54, "1~3년": 151, "3~5년": 103, "5년+": 98},
    "totalExperienceBand": {"0~3년": 56, "3~7년": 137, "7~12년": 142, "12년+": 71},
    "stage": {"Seed": 49, "Series A": 151, "Scale-up": 140, "Enterprise": 66},
}
EXPECTED_SEP_REASON = {"자발퇴사": 5, "계약만료": 3, "조직개편": 2, "성과/적합도": 2, "개인사유": 2}
EXPECTED_SEP_MONTH = {"2026-09": 14, "2026-10": 4}


# ---------------------------------------------------------------- 유틸
def read_csv(path):
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8-sig", newline="") as f:
        return [dict((k.strip(), (v or "").strip()) for k, v in row.items() if k) for row in csv.DictReader(f)]


def parse_date(s):
    try:
        return date.fromisoformat((s or "").strip())
    except ValueError:
        return None


def to_float(s, default=None):
    try:
        return float(s)
    except (TypeError, ValueError):
        return default


def month_end(d):
    return date(d.year, d.month, calendar.monthrange(d.year, d.month)[1])


def r2(x):
    return round(x, 2)


def mean2(xs):
    return r2(statistics.mean(xs)) if xs else 0.0


def median2(xs):
    return r2(statistics.median(xs)) if xs else 0.0


def tenure_band(years):
    if years < 1:
        return "1년 미만"
    if years < 3:
        return "1~3년"
    if years < 5:
        return "3~5년"
    return "5년+"


def experience_band(years):
    if years < 3:
        return "0~3년"
    if years < 7:
        return "3~7년"
    if years < 12:
        return "7~12년"
    return "12년+"


def age_band(birth, as_of):
    if birth is None:
        return ""
    age = as_of.year - birth.year - (1 if (as_of.month, as_of.day) < (birth.month, birth.day) else 0)
    if age < 30:
        return "20대"
    if age < 40:
        return "30대"
    if age < 50:
        return "40대"
    return "50대+"


def stage_for(hire, stages):
    if hire is None or not stages:
        return ""
    for s in stages:
        lo, hi = parse_date(s.get("from")) or date.min, parse_date(s.get("to")) or date.max
        if lo <= hire <= hi:
            return s.get("stage", "")
    return ""


def counts(rows, key, order):
    """값→인원 딕셔너리. 정규 순서 → 그 밖은 정렬. 빈 값은 '미상' 버킷(합계 보존)."""
    c = {}
    for r in rows:
        v = r.get(key) or UNKNOWN
        c[v] = c.get(v, 0) + 1
    out = dict((k, c[k]) for k in order if k in c)
    for k in sorted(k for k in c if k not in order):
        out[k] = c[k]
    return out


def cross_tab(rows, row_key, col_key, row_order, col_order):
    """{행 라벨: {열 값: 인원}} — 행은 row_order 전부(0행 포함), 열은 관측된 값의 합집합(직사각형, 0 채움)."""
    grouped = {}
    for r in rows:
        rk, ck = r.get(row_key) or UNKNOWN, r.get(col_key) or UNKNOWN
        grouped.setdefault(rk, {})
        grouped[rk][ck] = grouped[rk].get(ck, 0) + 1
    observed = set(c for row in grouped.values() for c in row)
    cols = [c for c in col_order if c in observed] + sorted(c for c in observed if c not in col_order)
    row_keys = list(row_order) + sorted(k for k in grouped if k not in row_order)
    return dict((rk, dict((c, grouped.get(rk, {}).get(c, 0)) for c in cols)) for rk in row_keys)


def write_handoff(root, as_of, sections):
    """핸드오프 로그(5개 H2 고정). 성공·실패 모두 쓴다."""
    path = os.path.join(root, REL["handoff"])
    os.makedirs(os.path.dirname(path), exist_ok=True)
    lines = ["# %s — %s — %s" % (PHASE, AGENT_NAME, as_of), ""]
    for title in HANDOFF_SECTIONS:
        lines.append("## " + title)
        lines.append("")
        lines.extend(sections.get(title) or ["- (없음)"])
        lines.append("")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return REL["handoff"]


# ---------------------------------------------------------------- 집계
def compute(root, as_of):
    warnings, gaps = [], []
    master = read_csv(os.path.join(root, REL["master"]))
    if master is None:
        raise FileNotFoundError(REL["master"] + " 없음 — people-data-cleanser 선행 필요")
    org_rows = read_csv(os.path.join(root, REL["org"]))
    to_rows = read_csv(os.path.join(root, REL["to"]))
    joiners = read_csv(os.path.join(root, REL["joiners"]))
    leavers = read_csv(os.path.join(root, REL["leavers"]))
    stages = None
    stages_path = os.path.join(root, REL["stages"])
    if os.path.exists(stages_path):
        with open(stages_path, encoding="utf-8") as f:
            stages = (json.load(f) or {}).get("stages")
    rows_in = {"headcountMaster": len(master), "toPlan": len(to_rows or []),
               "plannedJoiners": len(joiners or []), "plannedLeavers": len(leavers or [])}

    # 조직 골격: org-chart 순서 → 마스터·TO 에만 있는 코드는 뒤에 추가
    depts = {}
    if org_rows:
        for r in org_rows:
            depts[r["deptCode"]] = {"deptCode": r["deptCode"], "department": r["department"],
                                    "orgGroupCode": r["orgGroupCode"], "orgGroup": r["orgGroup"]}
    else:
        warnings.append(REL["org"] + " 없음 — 마스터의 조직 코드로 골격을 구성함(재직 0인 조직은 빠질 수 있음)")

    def ensure_dept(code, r, origin):
        if code not in depts:
            if org_rows:
                warnings.append("조직 체계에 없는 deptCode %s (%s) — 클린저 org-normalization 확인" % (code, origin))
            depts[code] = {"deptCode": code, "department": r.get("department") or code,
                           "orgGroupCode": r.get("orgGroupCode") or UNKNOWN, "orgGroup": r.get("orgGroup") or UNKNOWN}

    for r in master:
        code = r.get("deptCode") or UNKNOWN
        ensure_dept(code, r, "마스터")
        r["deptCode"] = code
        r["department"] = depts[code]["department"]          # 크로스탭 행 라벨은 org-chart 정규 라벨
        r["orgGroup"] = depts[code]["orgGroup"]
        r["orgGroupCode"] = depts[code]["orgGroupCode"]

    # 파생 컬럼 보충(클린저가 비워 둔 경우만 — 정제 데이터가 정본이다)
    filled = {}
    for r in master:
        hire = parse_date(r.get("hireDate"))
        if to_float(r.get("tenureYears")) is None:
            r["tenureYears"] = "%.2f" % (max(0.0, (as_of - hire).days / 365.25) if hire else 0.0)
            filled["tenureYears"] = filled.get("tenureYears", 0) + 1
        ty = float(r["tenureYears"])
        if not r.get("tenureBand"):
            r["tenureBand"] = tenure_band(ty)
            filled["tenureBand"] = filled.get("tenureBand", 0) + 1
        if to_float(r.get("totalExperienceYears")) is None:
            r["totalExperienceYears"] = "%.2f" % (to_float(r.get("priorExperienceMonths"), 0) / 12.0 + ty)
            filled["totalExperienceYears"] = filled.get("totalExperienceYears", 0) + 1
        if not r.get("totalExperienceBand"):
            r["totalExperienceBand"] = experience_band(float(r["totalExperienceYears"]))
            filled["totalExperienceBand"] = filled.get("totalExperienceBand", 0) + 1
        if not r.get("ageBand"):
            r["ageBand"] = age_band(parse_date(r.get("birthDate")), as_of)
            filled["ageBand"] = filled.get("ageBand", 0) + 1
        if not r.get("stage"):
            r["stage"] = stage_for(hire, stages)
            filled["stage"] = filled.get("stage", 0) + 1
    if filled:
        warnings.append("정제 마스터의 파생 필드 빈값을 스크립트가 보충함 %s — 클린저 derived-fields 확인"
                        % json.dumps(filled, ensure_ascii=False))

    # 재직/휴직
    active, on_leave, other = [], [], []
    for r in master:
        st = r.get("status")
        (active if st == "재직" else on_leave if st == "휴직" else other).append(r)
    if other:
        warnings.append("status 가 재직|휴직 이 아닌 행 %d건 — 총원에서 제외(클린저 code-normalization 확인)" % len(other))
    current = active + on_leave
    ids = [r.get("empId") for r in master]
    if len(set(ids)) != len(ids):
        warnings.append("중복 사번 %d건 — 클린저 dedup 확인" % (len(ids) - len(set(ids))))

    # TO
    to_by_dept = {}
    if not to_rows:
        warnings.append(REL["to"] + " 없음 — toHeadcount 0 으로 계산")
    for r in to_rows or []:
        code = r.get("deptCode") or UNKNOWN
        ensure_dept(code, r, "TO 계획")
        to_by_dept[code] = to_by_dept.get(code, 0) + int(to_float(r.get("toHeadcount"), 0))
    missing_to = [c for c in depts if c not in to_by_dept]
    if to_rows and missing_to:
        warnings.append("TO 계획에 없는 조직 %s — toHeadcount 0" % ",".join(missing_to))

    # 입사 예정(월말까지)
    m_end = month_end(as_of)
    planned_in, bad_join = 0, 0
    for j in joiners or []:
        d = parse_date(j.get("plannedHireDate"))
        if d is None:
            bad_join += 1
            continue
        if d <= m_end:
            planned_in += 1
    if joiners is None:
        warnings.append(REL["joiners"] + " 없음 — plannedIn 0 으로 계산")
    if bad_join:
        warnings.append("입사 예정일 파싱 실패 %d건 — plannedIn 에서 제외(클린저 date-correction 확인)" % bad_join)

    # 퇴사 예정 — §4-5: unknown-emp 제외 ∧ 마스터 재직 사번. stale(예정일 < 기준일)은 퇴사로 반영(§2-8)
    master_by_id = dict((r["empId"], r) for r in current)
    valid, excluded = [], {"unknownEmp": [], "notActive": [], "badDate": [], "stale": []}
    if leavers is None:
        warnings.append(REL["leavers"] + " 없음 — plannedOut 0 · plannedSeparations 비움")
    for lv in leavers or []:
        flags = [f for f in (lv.get("unresolvedFlags") or "").split(";") if f]
        emp_id = lv.get("empId")
        if FLAG_UNKNOWN_EMP in flags or emp_id not in master_by_id:
            excluded["unknownEmp"].append(emp_id)
            continue
        d = parse_date(lv.get("plannedTerminationDate"))
        if d is None:
            excluded["badDate"].append(emp_id)
            continue
        emp = master_by_id[emp_id]
        if emp.get("status") != "재직":
            excluded["notActive"].append(emp_id)
            continue
        if d < as_of or FLAG_STALE in flags:
            excluded["stale"].append(emp_id)
        if lv.get("deptCode") and lv.get("deptCode") != emp.get("deptCode"):
            warnings.append("퇴사 예정자 %s 의 조직(%s)이 마스터(%s)와 다름 — 마스터 조직으로 집계"
                            % (emp_id, lv.get("deptCode"), emp.get("deptCode")))
        valid.append(dict(lv, _date=d, department=emp["department"], tenureBand=emp.get("tenureBand") or UNKNOWN))
    if excluded["unknownEmp"]:
        warnings.append("마스터에 없는 퇴사 예정 사번 %d건 제외(unknown-emp): %s"
                        % (len(excluded["unknownEmp"]), ",".join(str(x) for x in excluded["unknownEmp"])))
    if excluded["badDate"]:
        warnings.append("퇴사 예정일 파싱 실패 %d건 제외: %s" % (len(excluded["badDate"]), ",".join(excluded["badDate"])))
    if excluded["notActive"]:
        warnings.append("휴직 상태 사번의 퇴사 예정 %d건 — 재직 기준 plannedOut·plannedSeparations 에서 제외(§4-5): %s"
                        % (len(excluded["notActive"]), ",".join(excluded["notActive"])))
        gaps.append("휴직자의 퇴사 예정을 plannedSeparations(사유 집계)에 넣을지 계약 §4-1 이 정하지 않음 — §4-5 재직 기준으로 제외함")
    if excluded["stale"]:
        warnings.append("예정일이 기준일 이전인 퇴사 예정(stale) %d건 — 월말 퇴사로 반영(§2-8): %s"
                        % (len(excluded["stale"]), ",".join(excluded["stale"])))
    by_month_end = [lv for lv in valid if lv["_date"] <= m_end]

    # ---- 산출물 조립
    def dept_entry(info, n_active, n_leave):
        to = to_by_dept.get(info["deptCode"], 0)
        return {"deptCode": info["deptCode"], "department": info["department"],
                "orgGroupCode": info["orgGroupCode"], "orgGroup": info["orgGroup"],
                "activeHeadcount": n_active, "onLeave": n_leave, "headcount": n_active + n_leave,
                "toHeadcount": to, "toGapAsOf": n_active - to}

    by_dept = [dept_entry(info, sum(1 for r in active if r["deptCode"] == code),
                          sum(1 for r in on_leave if r["deptCode"] == code)) for code, info in depts.items()]
    groups = {}
    for d in by_dept:
        g = groups.setdefault(d["orgGroupCode"], {"orgGroupCode": d["orgGroupCode"], "orgGroup": d["orgGroup"],
                                                  "activeHeadcount": 0, "onLeave": 0, "headcount": 0,
                                                  "toHeadcount": 0, "toGapAsOf": 0})
        for k in ("activeHeadcount", "onLeave", "headcount", "toHeadcount"):
            g[k] += d[k]
        g["toGapAsOf"] = g["activeHeadcount"] - g["toHeadcount"]
    by_group = list(groups.values())

    unresolved_rows = [r for r in master if (r.get("unresolvedFlags") or "").strip()]
    unresolved_by_flag = {}
    for r in unresolved_rows:
        for f in r["unresolvedFlags"].split(";"):
            if f.strip():
                unresolved_by_flag[f.strip()] = unresolved_by_flag.get(f.strip(), 0) + 1

    total_to = sum(to_by_dept.values())
    totals = {"headcount": len(current), "activeHeadcount": len(active), "onLeave": len(on_leave),
              "toHeadcount": total_to, "toGapAsOf": len(active) - total_to,
              "plannedIn": planned_in, "plannedOut": len(by_month_end), "unresolvedCount": len(unresolved_rows)}

    by_attr = dict((k, counts(active, k, ORDER[k])) for k in ATTRIBUTES_ACTIVE)
    by_attr_all = {"employmentType": counts(current, "employmentType", ORDER["employmentType"]),
                   "status": counts(current, "status", ORDER["status"]),
                   "leaveType": counts(on_leave, "leaveType", ORDER["leaveType"])}
    empty_buckets = dict((k, v[UNKNOWN]) for k, v in by_attr.items() if UNKNOWN in v)
    for k, v in by_attr_all.items():
        if UNKNOWN in v:
            empty_buckets["all." + k] = v[UNKNOWN]
    if empty_buckets:
        warnings.append("속성 빈값 '미상' 버킷 발생 %s — 정제 데이터에서는 없어야 함(클린저 확인)"
                        % json.dumps(empty_buckets, ensure_ascii=False))

    dept_order = [d["department"] for d in by_dept]
    group_order = [g["orgGroup"] for g in by_group]
    cross = {}
    for name, rk, ck in CROSS_TABS:
        ro = dept_order if rk == "department" else group_order if rk == "orgGroup" else ORDER[rk]
        cross[name] = cross_tab(active, rk, ck, ro, ORDER[ck])

    ten = [float(r["tenureYears"]) for r in active]
    exp_ = [float(r["totalExperienceYears"]) for r in active]
    exp_by_dept = []
    for d in by_dept:
        rows = [r for r in active if r["deptCode"] == d["deptCode"]]
        exp_by_dept.append({"deptCode": d["deptCode"],
                            "avgTenureYears": mean2([float(r["tenureYears"]) for r in rows]),
                            "avgTotalExperienceYears": mean2([float(r["totalExperienceYears"]) for r in rows])})
    experience = {"avgTenureYears": mean2(ten), "medianTenureYears": median2(ten),
                  "avgTotalExperienceYears": mean2(exp_), "medianTotalExperienceYears": median2(exp_),
                  "byDepartment": exp_by_dept}

    by_month = {}
    for lv in sorted(valid, key=lambda x: x["_date"]):
        k = lv["_date"].strftime("%Y-%m")
        by_month[k] = by_month.get(k, 0) + 1
    separations = {"total": len(by_month_end),
                   "bySeparationReason": counts(by_month_end, "separationReason", ORDER["separationReason"]),
                   "bySeparationType": counts(by_month_end, "separationType", ORDER["separationType"]),
                   "byDepartment": counts(by_month_end, "department", dept_order),
                   "byTenureBand": counts(by_month_end, "tenureBand", ORDER["tenureBand"]),
                   "byMonth": by_month}

    stats = {"asOfDate": as_of.isoformat(), "client": CLIENT_NAME, "totals": totals,
             "byOrgGroup": by_group, "byDepartment": by_dept,
             "byAttribute": by_attr, "byAttributeAll": by_attr_all, "crossTabs": cross,
             "experience": experience, "plannedSeparations": separations,
             "dataQuality": {"unresolvedCount": len(unresolved_rows),
                             "unresolvedByFlag": dict(sorted(unresolved_by_flag.items())),
                             "emptyValueBuckets": empty_buckets,
                             "briefDiscrepancies": [BRIEF_DISCREPANCY]},
             "provenance": {"source": REL["master"], "script": SCRIPT_REL}}
    meta = {"rowsIn": rows_in, "monthEnd": m_end.isoformat(), "excludedLeavers": excluded,
            "inputsPresent": {"orgChart": bool(org_rows), "companyStages": bool(stages), "toPlan": bool(to_rows),
                              "plannedJoiners": joiners is not None, "plannedLeavers": leavers is not None}}
    return stats, warnings, gaps, meta


def reconcile(stats, m_end):
    """대사(§4-5): 모든 카운트 합이 totals 와 일치해야 한다. 하나라도 어긋나면 산출물을 쓰지 않는다."""
    t = stats["totals"]
    checks, failed = 0, []

    def check(name, actual, expected):
        nonlocal checks
        checks += 1
        if actual != expected:
            failed.append({"check": name, "actual": actual, "expected": expected})

    for k, v in stats["byAttribute"].items():
        check("byAttribute.%s" % k, sum(v.values()), t["activeHeadcount"])
    check("byAttributeAll.employmentType", sum(stats["byAttributeAll"]["employmentType"].values()), t["headcount"])
    check("byAttributeAll.status", sum(stats["byAttributeAll"]["status"].values()), t["headcount"])
    check("byAttributeAll.leaveType", sum(stats["byAttributeAll"]["leaveType"].values()), t["onLeave"])
    for k, table in stats["crossTabs"].items():
        check("crossTabs.%s" % k, sum(sum(row.values()) for row in table.values()), t["activeHeadcount"])
    for arr in ("byDepartment", "byOrgGroup"):
        for f in ("activeHeadcount", "onLeave", "headcount", "toHeadcount"):
            check("%s.%s" % (arr, f), sum(d[f] for d in stats[arr]), t[f])
        for d in stats[arr]:
            check("%s[%s].headcount" % (arr, d.get("deptCode") or d.get("orgGroupCode")), d["activeHeadcount"] + d["onLeave"], d["headcount"])
            check("%s[%s].toGapAsOf" % (arr, d.get("deptCode") or d.get("orgGroupCode")), d["toGapAsOf"], d["activeHeadcount"] - d["toHeadcount"])
    check("totals.active+onLeave", t["activeHeadcount"] + t["onLeave"], t["headcount"])
    check("totals.toGapAsOf", t["toGapAsOf"], t["activeHeadcount"] - t["toHeadcount"])
    check("experience.byDepartment.length", len(stats["experience"]["byDepartment"]), len(stats["byDepartment"]))
    sep = stats["plannedSeparations"]
    for k in ("bySeparationReason", "bySeparationType", "byDepartment", "byTenureBand"):
        check("plannedSeparations.%s" % k, sum(sep[k].values()), sep["total"])
    check("plannedSeparations.byMonth(<=monthEnd)", sum(v for m, v in sep["byMonth"].items() if m <= m_end[:7]), sep["total"])
    check("plannedSeparations.total", sep["total"], t["plannedOut"])
    check("dataQuality.unresolvedCount", stats["dataQuality"]["unresolvedCount"], t["unresolvedCount"])
    return {"passed": not failed, "checks": checks, "failed": failed}


def target_check(stats, as_of_str):
    """§2-7 정본 대조 — 집계 오류가 아니라 정제 데이터가 시나리오와 다르다는 신호. 산출물에는 넣지 않는다."""
    mismatches, checks = [], 0

    def cmp(section, key, expected, actual):
        nonlocal checks
        checks += 1
        if expected != actual:
            mismatches.append({"section": section, "key": key, "expected": expected, "actual": actual})

    by_code = dict((d["deptCode"], d) for d in stats["byDepartment"])
    for code, (hc, ol, to) in EXPECTED_DEPT.items():
        d = by_code.get(code)
        if d is None:
            mismatches.append({"section": "byDepartment", "key": code, "expected": "존재", "actual": "없음"})
            checks += 1
            continue
        cmp("byDepartment.activeHeadcount", code, hc, d["activeHeadcount"])
        cmp("byDepartment.onLeave", code, ol, d["onLeave"])
        cmp("byDepartment.toHeadcount", code, to, d["toHeadcount"])
    by_group = dict((g["orgGroupCode"], g) for g in stats["byOrgGroup"])
    for code, hc in EXPECTED_GROUP_ACTIVE.items():
        cmp("byOrgGroup.activeHeadcount", code, hc, by_group.get(code, {}).get("activeHeadcount"))
    for k, v in EXPECTED_TOTALS.items():
        cmp("totals", k, v, stats["totals"].get(k))
    attr_result = {}
    for attr, expected in EXPECTED_ATTR.items():
        actual = stats["byAttributeAll"]["employmentType"] if attr == "employmentType" else stats["byAttribute"][attr]
        before = len(mismatches)
        for key in sorted(set(expected) | set(actual)):
            cmp("byAttribute.%s" % attr if attr != "employmentType" else "byAttributeAll.employmentType",
                key, expected.get(key, 0), actual.get(key, 0))
        n = len(mismatches) - before
        attr_result[attr] = {"passed": n == 0, "mismatches": n, "basis": 427 if attr == "employmentType" else 406}
    sep = stats["plannedSeparations"]
    for key in sorted(set(EXPECTED_SEP_REASON) | set(sep["bySeparationReason"])):
        cmp("plannedSeparations.bySeparationReason", key, EXPECTED_SEP_REASON.get(key, 0), sep["bySeparationReason"].get(key, 0))
    for key in sorted(set(EXPECTED_SEP_MONTH) | set(sep["byMonth"])):
        cmp("plannedSeparations.byMonth", key, EXPECTED_SEP_MONTH.get(key, 0), sep["byMonth"].get(key, 0))
    return {"applicable": as_of_str == DEFAULT_AS_OF, "passed": not mismatches, "checks": checks,
            "mismatches": mismatches, "attributeDistributions": attr_result,
            "unexpectedDeptCodes": sorted(c for c in by_code if c not in EXPECTED_DEPT)}


# ---------------------------------------------------------------- 핸드오프 로그 본문
def handoff_sections(cmd, started, as_of, status, stats=None, meta=None, recon=None, tc=None,
                     warnings=None, gaps=None, error=None):
    warnings, gaps = warnings or [], gaps or []
    tried = ["- 시작 %s / 종료 %s — `%s`" % (started, datetime.now().isoformat(timespec="seconds"), cmd),
             "- 상태: **%s**" % status,
             "- 정제 마스터 → totals·byOrgGroup·byDepartment·byAttribute(재직)·byAttributeAll(총원)·crossTabs 7종·experience 집계, "
             "TO·입퇴사 예정에서 toHeadcount·plannedIn·plannedOut·plannedSeparations 집계 (§4-1·§4-5)",
             "- 대사(딕셔너리 합 assert) 통과 시에만 `%s` 작성, §2-7 정본 대조는 stdout targetCheck 로만 보고" % REL["out"]]
    evidence = ["- 계약: `.claude/DATA_CONTRACT.md` §2-7(정본 수치)·§2-8(stale/unknown-emp)·§3(정제 컬럼)·§4-1(shape)·§4-5(합계 규칙)"]
    if meta:
        evidence.append("- 입력 행수: %s" % json.dumps(meta["rowsIn"], ensure_ascii=False))
        evidence.append("- 입력 존재: %s" % json.dumps(meta["inputsPresent"], ensure_ascii=False))
        evidence.append("- 월말 %s · 퇴사 예정 제외/특기: %s" % (meta["monthEnd"], json.dumps(meta["excludedLeavers"], ensure_ascii=False)))
    if stats:
        evidence.append("- totals: %s" % json.dumps(stats["totals"], ensure_ascii=False))
        evidence.append("- byOrgGroup(재직): %s" % ", ".join("%s %d" % (g["orgGroup"], g["activeHeadcount"]) for g in stats["byOrgGroup"]))
    failed = []
    if error:
        failed.append("- 오류: %s" % error)
    if recon and not recon["passed"]:
        failed.append("- 대사 실패 %d건(산출물 미작성): %s" % (len(recon["failed"]), json.dumps(recon["failed"], ensure_ascii=False)))
    if tc and tc["applicable"] and not tc["passed"]:
        failed.append("- §2-7 정본 불일치 %d건(집계 오류 아님 — 정제 데이터 확인 신호): %s"
                      % (len(tc["mismatches"]), json.dumps(tc["mismatches"][:20], ensure_ascii=False)))
    failed.extend("- 경고: %s" % w for w in warnings)
    failed.extend("- 계약 갭: %s" % g for g in gaps)
    verified = []
    if recon:
        verified.append("- 내부 대사 %d항목 %s (byAttribute 8종 합=재직, byAttributeAll 합=총원/휴직, crossTabs 7종 셀 합=재직, "
                        "Σ byDepartment = Σ byOrgGroup = totals, plannedSeparations 합=plannedOut)"
                        % (recon["checks"], "통과" if recon["passed"] else "실패"))
    if tc:
        if tc["applicable"]:
            verified.append("- §2-7 정본 대조 %d항목 %s — 속성 분포 8종: %s"
                            % (tc["checks"], "전부 일치" if tc["passed"] else "불일치 %d건" % len(tc["mismatches"]),
                               ", ".join("%s %s" % (k, "일치" if v["passed"] else "불일치") for k, v in tc["attributeDistributions"].items())))
        else:
            verified.append("- §2-7 정본 대조는 기준일 %s ≠ %s 이므로 비적용(참고용 %d항목 중 불일치 %d)"
                            % (as_of, DEFAULT_AS_OF, tc["checks"], len(tc["mismatches"])))
    if stats:
        verified.append("- 산출물 `%s` (UTF-8, §4-1 키 전부, 계약 외 필드 없음)" % REL["out"])
    nxt = [
        "- `headcount-forecaster`(04): `byDepartment[].activeHeadcount`(출발점)·`toHeadcount`·`toGapAsOf`, "
        "`totals.plannedIn/plannedOut`(§4-5 정의) — forecast.totals 와 같아야 함",
        "- `attrition-risk-scorer`(05, 병렬): `totals.activeHeadcount` 로 점수화 대상 수 대사",
        "- `payroll-close-analyst`(06): `byAttributeAll.employmentType`(427)·`status`·`leaveType` → payrollHeadcount",
        "- `onboarding-plan-analyst`(07): `plannedSeparations.byTenureBand` → earlyAttrition, `experience.byDepartment` → 버디 후보 참고",
        "- `product-builder`(09): 파일 전체를 `site/data/insight.json.stats` 로 내장. crossTabs 행 키는 라벨(department·jobFamily·orgGroup명)",
        "- `monthly-report-mailer`(10): `dataQuality.briefDiscrepancies`·`unresolvedByFlag` → 데이터 품질 절",
        "- `people-data-auditor`(11): stdout targetCheck(§2-7)·reconciliation 결과를 test_reconciliation 사전 검사로 사용",
    ]
    if status != "ok":
        nxt.insert(0, "- **선행 조치 필요**: 상태 %s — 위 실패 항목을 해소한 뒤 이 스크립트를 재실행한다(결정적이므로 재실행이 곧 갱신)" % status)
    return {"시도한 것": tried, "본 데이터·근거": evidence, "실패한 것": failed or ["- 없음"],
            "검증된 것": verified or ["- (검증 전 종료)"], "다음 agent 인계점": nxt}


# ---------------------------------------------------------------- 진입점
def main(argv=None):
    p = argparse.ArgumentParser(description="Zero Company HR 인원 통계 집계 (DATA_CONTRACT v2 §4-1)")
    p.add_argument("--root", default=DEFAULT_ROOT)
    p.add_argument("--as-of", dest="as_of", default=DEFAULT_AS_OF)
    a = p.parse_args(argv)
    started = datetime.now().isoformat(timespec="seconds")
    cmd = "python3 %s --root %s --as-of %s" % (SCRIPT_REL, a.root, a.as_of)
    try:
        handoff = write_handoff(a.root, a.as_of, {
            "시도한 것": ["- 시작 %s — `%s`" % (started, cmd), "- (실행 중 — 종료 시 이 로그를 갱신한다)"]})
    except OSError as e:
        print(json.dumps({"status": "error", "errorType": "OSError", "error": "핸드오프 로그 작성 실패: %s" % e,
                          "asOfDate": a.as_of}, ensure_ascii=False))
        return 1
    try:
        as_of = date.fromisoformat(a.as_of)
        stats, warnings, gaps, meta = compute(a.root, as_of)
        recon = reconcile(stats, meta["monthEnd"])
        if not recon["passed"]:
            write_handoff(a.root, a.as_of, handoff_sections(cmd, started, a.as_of, "error", stats, meta, recon, None, warnings, gaps))
            print(json.dumps({"status": "error", "errorType": "reconciliation", "asOfDate": a.as_of, "handoffLog": handoff,
                              "reconciliation": recon, "warnings": warnings, "contractGaps": gaps}, ensure_ascii=False))
            return 1
        out = os.path.join(a.root, REL["out"])
        os.makedirs(os.path.dirname(out), exist_ok=True)
        with open(out, "w", encoding="utf-8") as f:
            json.dump(stats, f, ensure_ascii=False, indent=2)
        tc = target_check(stats, a.as_of)
        if tc["applicable"] and not tc["passed"]:
            warnings.append("§2-7 정본과 불일치 %d건 — 집계 오류가 아니라 정제 데이터 확인 신호(people-data-cleanser)" % len(tc["mismatches"]))
        write_handoff(a.root, a.as_of, handoff_sections(cmd, started, a.as_of, "ok", stats, meta, recon, tc, warnings, gaps))
        print(json.dumps({
            "status": "ok", "asOfDate": a.as_of, "output": REL["out"], "handoffLog": handoff,
            "rowsIn": meta["rowsIn"], "totals": stats["totals"],
            "byOrgGroup": [{"orgGroupCode": g["orgGroupCode"], "orgGroup": g["orgGroup"], "activeHeadcount": g["activeHeadcount"],
                            "onLeave": g["onLeave"], "toGapAsOf": g["toGapAsOf"]} for g in stats["byOrgGroup"]],
            "dataQuality": stats["dataQuality"], "reconciliation": recon, "targetCheck": tc,
            "warnings": warnings, "contractGaps": gaps,
        }, ensure_ascii=False))
        return 0
    except FileNotFoundError as e:
        write_handoff(a.root, a.as_of, handoff_sections(cmd, started, a.as_of, "blocked", error=str(e)))
        print(json.dumps({"status": "blocked", "errorType": "FileNotFoundError", "error": str(e), "asOfDate": a.as_of,
                          "handoffLog": handoff}, ensure_ascii=False))
        return 3
    except Exception as e:  # noqa: BLE001
        write_handoff(a.root, a.as_of, handoff_sections(cmd, started, a.as_of, "error", error="%s: %s" % (type(e).__name__, e)))
        print(json.dumps({"status": "error", "errorType": type(e).__name__, "error": str(e), "asOfDate": a.as_of,
                          "handoffLog": handoff}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    sys.exit(main())
