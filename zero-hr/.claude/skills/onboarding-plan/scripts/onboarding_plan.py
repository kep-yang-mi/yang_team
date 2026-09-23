#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""onboarding_plan.py — 온보딩 계획(onboarding-plan) 파생 데이터 생성. DATA_CONTRACT v2 §11 (+§4-5 shape 보충).

정제 데이터(②)와 이직 리스크(③)에서만 계산한다 — 원천(data/raw/)은 읽지 않는다. Python 3.9 표준 라이브러리만.

입력 (--root 기준):
  data/clean/planned-joiners.clean.csv     필수  §3-3 입사 예정자 27 (9월 19 + 10월 8)
  data/clean/headcount-master.clean.csv    필수  §3-1 정제 마스터 427 (버디 후보·조직장·90일 코호트·재직기간)
  data/clean/planned-leavers.clean.csv     권장  §3-4 퇴사 예정자 → earlyAttrition (없으면 0/0 + gap)
  data/reference/org-chart.csv             선택  §1 조직 순서·명칭
  data/stats/attrition-risk.json           선택  §4-3 riskBand 조인 (없으면 riskBand=null + gap)
  data/stats/month-end-forecast.json       선택  §4-2 totals.plannedIn(19)과 월말 이전 입사 예정 수 교차 대사
  personas/persona-needs.json              선택  §9 온보딩 담당 fitCriteria·requiredFields 검사 → gaps
출력:
  data/stats/onboarding-plan.json          §11 shape (asOfDate, horizonEnd, timeline, byDepartment, checklist,
                                            earlyTenureCohort, earlyAttrition, provenance)
  _workspace/handoff/07-onboarding.md      핸드오프 로그(Operating Rule 2, 5개 H2) — 시작 시 1회, 종료 시 덮어쓰기
  stdout 마지막 줄: 요약 JSON 1행

체크리스트 상태는 가상이며 random.seed(20260923) 고정으로 재실행 시 동일하다.
종료 코드: 0 = 산출물 작성(status ok|partial) · 1 = 필수 입력 없음 · 2 = 인자 오류
"""
import argparse
import csv
import json
import os
import random
import sys
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

DEFAULT_ROOT = "/Users/yang/development/zero-hr"
DEFAULT_AS_OF = "2026-09-23"
DEFAULT_SEED = 20260923

PATH_JOINERS = "data/clean/planned-joiners.clean.csv"
PATH_MASTER = "data/clean/headcount-master.clean.csv"
PATH_LEAVERS = "data/clean/planned-leavers.clean.csv"
PATH_ORG = "data/reference/org-chart.csv"
PATH_RISK = "data/stats/attrition-risk.json"
PATH_FORECAST = "data/stats/month-end-forecast.json"
PATH_PERSONAS = "personas/persona-needs.json"
PATH_OUTPUT = "data/stats/onboarding-plan.json"
PATH_HANDOFF = "_workspace/handoff/07-onboarding.md"
SCRIPT_REF = ".claude/skills/onboarding-plan/scripts/onboarding_plan.py"
ALL_SOURCES = (PATH_JOINERS, PATH_MASTER, PATH_LEAVERS, PATH_ORG, PATH_RISK, PATH_FORECAST, PATH_PERSONAS)

CHECKLIST_ITEMS = ["계정 발급", "장비 지급", "보안 교육", "조직 소개", "버디 배정", "30일 면담"]   # §11 순서 고정
CHECKLIST_LEAD_DAYS = {"계정 발급": 14, "장비 지급": 10, "보안 교육": 3, "조직 소개": 0, "버디 배정": 7, "30일 면담": -30}
LEVEL_LADDER = ["IC1", "IC2", "IC3", "Senior", "Lead", "Manager", "Director", "VP"]
DEPT_LEAD_LEVEL = "VP"          # §2-7 레벨 제약: 조직마다 VP ≥ 1 → 조직장 = 최장 재직 VP
BUDDY_LEVELS = ("IC3", "Senior", "Lead")   # §11 레벨 IC3~Lead
BUDDY_TENURE = (2.0, 6.0)                 # §11 재직 2~6년
BUDDY_RISK_BAND = "낮음"                  # §11 리스크 낮음
BUDDY_MAX = 3
EARLY_TENURE_DAYS = 90
ACTIVE = "재직"
HIGH_RISK = "높음"

HANDOFF_SECTIONS = ["시도한 것", "본 데이터·근거", "실패한 것", "검증된 것", "다음 agent 인계점"]
KNOWN_FILES = {"planned-joiners": PATH_JOINERS, "headcount-master": PATH_MASTER, "planned-leavers": PATH_LEAVERS,
               "attrition-risk": PATH_RISK, "org-chart": PATH_ORG, "month-end-forecast": PATH_FORECAST}
PASS_PREFIXES = ("policy:", "site/", "reports/")          # 데이터 필드가 아님 — product-judge의 몫
PLAN_PREFIXES = ("onboarding-plan.", "onboardingPlan.")
DEGRADING_GAPS = {"missing-input", "invalid-row", "reconciliation-mismatch"}   # 하나라도 있으면 status=partial


# ---------------------------------------------------------------- helpers
def parse_iso(v: Optional[str]) -> Optional[date]:
    v = (v or "").strip()
    try:
        return date.fromisoformat(v[:10]) if v else None
    except ValueError:
        return None


def parse_float(v: Optional[str]) -> Optional[float]:
    try:
        return float((v or "").strip())
    except ValueError:
        return None


def read_csv(path: str) -> List[Dict[str, str]]:
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        return [dict(r) for r in csv.DictReader(f)]


def read_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8-sig") as f:
        return json.load(f)


def month_end_of(d: date) -> date:
    nxt = date(d.year + (d.month == 12), 1 if d.month == 12 else d.month + 1, 1)
    return nxt - timedelta(days=1)


def iso_week(d: date) -> Tuple[str, str]:
    """isocalendar()로만 주차를 만든다 — 월 경계(9/28~10/4)와 주 경계가 달라 직접 계산하면 어긋난다."""
    y, w, wd = d.isocalendar()
    return "%04d-W%02d" % (y, w), (d - timedelta(days=wd - 1)).isoformat()


def tenure_of(row: Dict[str, str], as_of: date) -> Optional[float]:
    t = parse_float(row.get("tenureYears"))
    if t is not None:
        return t
    hire = parse_iso(row.get("hireDate"))
    return None if hire is None else round(max(0, (as_of - hire).days) / 365.25, 2)


def gap(kind: str, reason: str, **extra: Any) -> Dict[str, Any]:
    g = {"kind": kind, "criterionId": None, "criterion": None, "weight": None, "evidence": None, "reason": reason}
    g.update(extra)
    return g


def write_handoff(root: str, title_status: str, sections: Dict[str, List[str]]) -> str:
    """핸드오프 로그(Operating Rule 2). 5개 H2 고정 — 다음 agent가 같은 위치에서 같은 절을 읽는다."""
    path = os.path.join(root, PATH_HANDOFF)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    lines = ["# 07-onboarding — onboarding-plan-analyst — %s" % title_status, ""]
    for h in HANDOFF_SECTIONS:
        lines.append("## " + h)
        lines.extend(sections.get(h) or ["- (없음)"])
        lines.append("")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return PATH_HANDOFF


# ---------------------------------------------------------------- sections
def build_timeline(joiners: List[Dict[str, str]], dept_name: Dict[str, str]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """§11 timeline[]: ISO 주차별 입사 예정자. 유효한 plannedHireDate가 있는 모든 행(horizon 이후 포함 — 합계 27 assert가 우선)."""
    weeks: Dict[str, Dict[str, Any]] = {}
    invalid = []
    for r in joiners:
        hire = parse_iso(r.get("plannedHireDate"))
        if hire is None:
            invalid.append({"joinerId": r.get("joinerId"), "rawValue": r.get("plannedHireDate", "")})
            continue
        label, start = iso_week(hire)
        bucket = weeks.setdefault(label, {"week": label, "weekStart": start, "joiners": []})
        code = r.get("deptCode", "")
        bucket["joiners"].append({"joinerId": r.get("joinerId", ""), "name": r.get("name", ""), "deptCode": code,
                                  "department": dept_name.get(code) or r.get("department", ""), "plannedHireDate": hire.isoformat(),
                                  "employmentType": r.get("employmentType", ""), "level": r.get("level", "")})
    for b in weeks.values():
        b["joiners"].sort(key=lambda j: (j["plannedHireDate"], j["joinerId"]))
    return [weeks[k] for k in sorted(weeks)], invalid


def build_by_department(flat: List[Dict[str, Any]], master: List[Dict[str, str]], dept_order: List[str], dept_name: Dict[str, str],
                        risk: Dict[str, Dict[str, Any]], risk_available: bool, as_of: date, month_end: date,
                        gaps: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """§11/§4-5 byDepartment[]: 입사 예정자 ≥ 1인 조직만. deptLeadEmpId = 재직 VP 중 최장 재직(동률: 사번↑).
    VP가 없으면 최고 레벨로 대체하고 gap(dept-lead-fallback)에 남긴다 — §2-7 제약(조직마다 VP ≥ 1) 위반 신호."""
    joiners_by_dept: Dict[str, List[Dict[str, Any]]] = {}
    for j in flat:
        joiners_by_dept.setdefault(j["deptCode"], []).append(j)
    active_by_dept: Dict[str, List[Dict[str, str]]] = {}
    for r in master:
        if r.get("status") == ACTIVE:
            active_by_dept.setdefault(r.get("deptCode", ""), []).append(r)
    codes = [c for c in dept_order if c in joiners_by_dept] + sorted(c for c in joiners_by_dept if c not in dept_order)
    out = []
    for code in codes:
        members = active_by_dept.get(code, [])
        js = joiners_by_dept[code]
        department = dept_name.get(code) or js[0]["department"]
        vps = sorted((m for m in members if m.get("level") == DEPT_LEAD_LEVEL),
                     key=lambda m: (-(tenure_of(m, as_of) or 0.0), m.get("empId", "")))
        lead_id: Optional[str] = vps[0]["empId"] if vps else None
        if lead_id is None:
            ranked = sorted(members, key=lambda m: (-(LEVEL_LADDER.index(m["level"]) if m.get("level") in LEVEL_LADDER else -1),
                                                    -(tenure_of(m, as_of) or 0.0), m.get("empId", "")))
            lead_id = ranked[0]["empId"] if ranked else None
            gaps.append(gap("dept-lead-fallback", "%s(%s)에 재직 VP 없음 — 최고 레벨 %s로 대체(§2-7 조직마다 VP ≥ 1 확인)"
                            % (department, code, lead_id or "없음(재직자 0)"), evidence="onboarding-plan.byDepartment[].deptLeadEmpId", criterionId=code))
        candidates = []
        for m in members:
            t = tenure_of(m, as_of)
            band = (risk.get(m.get("empId", "")) or {}).get("riskBand") if risk_available else None
            if m.get("level") in BUDDY_LEVELS and t is not None and BUDDY_TENURE[0] <= t <= BUDDY_TENURE[1] \
                    and (not risk_available or band == BUDDY_RISK_BAND):
                candidates.append({"empId": m.get("empId", ""), "name": m.get("name", ""), "tenureYears": t,
                                   "level": m.get("level", ""), "riskBand": band})
        candidates.sort(key=lambda c: (-c["tenureYears"], c["empId"]))
        out.append({"deptCode": code, "department": department, "joiners": len(js),
                    "joinersByMonthEnd": sum(1 for j in js if date.fromisoformat(j["plannedHireDate"]) <= month_end),
                    "buddyCandidates": candidates[:BUDDY_MAX], "deptLeadEmpId": lead_id})
    return out


def build_checklist(flat: List[Dict[str, Any]], by_dept: List[Dict[str, Any]], as_of: date, seed: int) -> Dict[str, Any]:
    """§11 checklist: 가상 상태. 입사일이 가까울수록 done 확률↑. random.seed 고정 + joinerId 정렬 → 재실행 동일."""
    random.seed(seed)
    buddy_ok = {d["deptCode"]: bool(d["buddyCandidates"]) for d in by_dept}
    rows = []
    for j in sorted(flat, key=lambda x: x["joinerId"]):
        days_until = (date.fromisoformat(j["plannedHireDate"]) - as_of).days
        row: Dict[str, Any] = {"joinerId": j["joinerId"]}
        for item in CHECKLIST_ITEMS:
            lead = CHECKLIST_LEAD_DAYS[item]
            if item == "버디 배정" and not buddy_ok.get(j["deptCode"], False):
                row[item] = "pending"   # 버디 후보 없는 조직 — 데이터 근거 pending(난수 아님)
                continue
            if lead < 0:
                p = 0.9 if days_until <= lead else 0.0
            elif lead == 0:
                p = 0.95 if days_until <= 0 else 0.05
            elif days_until > lead:
                p = 0.10
            else:
                p = 0.5 + 0.45 * (1.0 - max(days_until, 0) / float(lead))
            row[item] = "done" if random.random() < p else "pending"
        rows.append(row)
    return {"items": list(CHECKLIST_ITEMS), "status": rows}


def build_cohort(master: List[Dict[str, str]], risk: Dict[str, Dict[str, Any]], as_of: date) -> Dict[str, Any]:
    """§11 earlyTenureCohort: 기준일 기준 입사 90일 이내 재직자(status=재직). 성명·생년월일 없음."""
    since = as_of - timedelta(days=EARLY_TENURE_DAYS)
    members = []
    for r in master:
        hire = parse_iso(r.get("hireDate"))
        if r.get("status") != ACTIVE or hire is None or not (since <= hire <= as_of):
            continue
        members.append({"empId": r.get("empId", ""), "deptCode": r.get("deptCode", ""), "hireDate": hire.isoformat(),
                        "daysSinceHire": (as_of - hire).days, "riskBand": (risk.get(r.get("empId", "")) or {}).get("riskBand")})
    members.sort(key=lambda m: (m["hireDate"], m["empId"]))
    return {"definition": "기준일 기준 입사 %d일 이내 재직자" % EARLY_TENURE_DAYS, "members": members, "count": len(members),
            "highRiskCount": sum(1 for m in members if m["riskBand"] == HIGH_RISK)}


def build_early_attrition(leavers: List[Dict[str, str]], master_by_id: Dict[str, Dict[str, str]], dept_name: Dict[str, str],
                          as_of: date, month_end: date) -> Dict[str, Any]:
    """§11 earlyAttrition: 퇴사 예정자(14) 중 재직기간 1년 미만 비율. 모집단은 §4-5 plannedOut 규칙과 동일 —
    예정일 ≤ 월말 ∧ unknown-emp 제외(마스터에 없음) ∧ 마스터에서 재직. 그래야 forecast.totals.plannedOut(14)과 같은 14명이다."""
    total, under, by_dept = 0, 0, {}
    for lv in leavers:
        d = parse_iso(lv.get("plannedTerminationDate"))
        m = master_by_id.get(lv.get("empId", ""))
        if d is None or d > month_end or m is None or m.get("status") != ACTIVE:
            continue
        t = tenure_of(m, as_of)
        if t is None:
            continue
        code = m.get("deptCode") or lv.get("deptCode", "")
        entry = by_dept.setdefault(code, {"department": dept_name.get(code) or m.get("department", ""), "under1YearLeavers": 0, "totalLeavers": 0, "rate": 0.0})
        entry["totalLeavers"] += 1
        entry["under1YearLeavers"] += int(t < 1.0)
        total += 1
        under += int(t < 1.0)
    for e in by_dept.values():
        e["rate"] = round(e["under1YearLeavers"] / e["totalLeavers"], 4) if e["totalLeavers"] else 0.0
    return {"definition": "퇴사 예정자(%d) 중 재직기간 1년 미만 비율" % total, "under1YearLeavers": under,
            "totalLeavers": total, "rate": round(under / total, 4) if total else 0.0,
            "byDepartment": {k: by_dept[k] for k in sorted(by_dept)}}


# ---------------------------------------------------------------- fit criteria
def resolve_path(obj: Any, dotted: str) -> bool:
    """점 경로 존재·비어있지 않음. `[]`(리스트)는 어느 원소든 나머지 경로가 해소되면 충족 —
    첫 원소만 보면 '첫 조직에 버디 후보가 없다'가 '필드가 없다'로 오판된다."""
    segs = [s for s in dotted.replace("[]", "").split(".") if s]

    def walk(cur: Any, i: int) -> bool:
        if isinstance(cur, list):
            return any(walk(el, i) for el in cur)
        if i == len(segs):
            return cur is not None and not (isinstance(cur, (list, dict, str)) and len(cur) == 0)
        if not isinstance(cur, dict) or segs[i] not in cur:
            return False
        return walk(cur[segs[i]], i + 1)
    return walk(obj, 0)


def resolve_evidence(root: str, plan: Dict[str, Any], ev: str) -> Optional[str]:
    """persona-needs 스킬의 evidence 규약. None = 충족, str = 미충족 사유.
    `;`로 이어진 복수 근거는 전부, `reconciliation:A=B`는 양쪽 해소 + 실제 대사 일치, policy:/site//reports/는 통과."""
    parts = [p.strip() for p in ev.split(";") if p.strip()]
    if not parts:
        return "evidence 미기재"
    reasons = []
    for p in parts:
        if p.startswith(PASS_PREFIXES):
            continue
        if p.startswith("reconciliation:"):
            sides = [s.strip() for s in p[len("reconciliation:"):].split("=", 1)]
            if len(sides) != 2:
                reasons.append("reconciliation 표기 오류: %s" % p)
                continue
            for s in sides:
                r = resolve_evidence(root, plan, s)
                if r:
                    reasons.append(r)
            rec = plan["provenance"]["reconciliation"]
            invalid_rows = [g for g in plan["provenance"]["gaps"] if g["kind"] == "invalid-row"]
            if not rec["match"] or rec["monthEndMatch"] is False or invalid_rows:
                reasons.append("대사 불일치(provenance.reconciliation: match=%s, monthEndMatch=%s, invalid-row %d건)"
                               % (rec["match"], rec["monthEndMatch"], len(invalid_rows)))
            continue
        if p.startswith(PLAN_PREFIXES):
            if not resolve_path(plan, p.split(".", 1)[1]):
                reasons.append("onboarding-plan.json에 evidence 경로가 없거나 비어 있음: %s" % p)
            continue
        head = p.split(".")[0].split(" ")[0]
        if head in KNOWN_FILES:
            if not os.path.exists(os.path.join(root, KNOWN_FILES[head])):
                reasons.append("evidence 원천 파일 없음: %s" % KNOWN_FILES[head])
            continue
        reasons.append("이 스크립트가 만들지 않는 데이터를 evidence로 요구(%s) — 제품 단계에서 충족 여부 확인" % p)
    uniq = [r for i, r in enumerate(reasons) if r not in reasons[:i]]   # 같은 사유 중복 제거(reconciliation 양쪽이 같은 이유로 실패할 때)
    return "; ".join(uniq) if uniq else None


def check_fit(root: str, plan: Dict[str, Any], gaps: List[Dict[str, Any]]) -> Dict[str, int]:
    """온보딩 담당(code=onboarding)의 fitCriteria·requiredFields를 산출물에 대해 검사한다. 없으면 gap만 남기고 계속."""
    result = {"fitCriteria": 0, "requiredFields": 0}
    path = os.path.join(root, PATH_PERSONAS)
    if not os.path.exists(path):
        gaps.append(gap("missing-input", "persona-needs.json 없음 — fitCriteria 검사 생략(persona-needs-analyst 이후 재실행)", evidence=PATH_PERSONAS))
        return result
    try:
        persona = next((p for p in (read_json(path).get("personas") or []) if p.get("code") == "onboarding"), None)
    except (ValueError, AttributeError) as ex:
        gaps.append(gap("missing-input", "persona-needs.json 파싱 실패: %s" % ex, evidence=PATH_PERSONAS))
        return result
    if persona is None:
        gaps.append(gap("missing-input", "personas[].code == 'onboarding' 없음", evidence=PATH_PERSONAS))
        return result
    for c in persona.get("fitCriteria") or []:
        result["fitCriteria"] += 1
        reason = resolve_evidence(root, plan, str(c.get("evidence") or ""))
        if reason:
            gaps.append(gap("fit-criterion-unmet", reason, criterionId=c.get("id"), criterion=c.get("criterion"),
                            weight=c.get("weight"), evidence=c.get("evidence")))
    for rf in persona.get("requiredFields") or []:
        rf = str(rf).strip()
        if not rf.startswith(PLAN_PREFIXES):
            continue   # 다른 산출물의 필드는 그 단계의 몫
        result["requiredFields"] += 1
        if not resolve_path(plan, rf.split(".", 1)[1]):
            gaps.append(gap("required-field-missing", "requiredFields의 경로가 산출물에 없거나 비어 있음", evidence=rf, criterionId="requiredFields"))
    return result


# ---------------------------------------------------------------- main
def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="온보딩 계획(onboarding-plan.json) — DATA_CONTRACT v2 §11")
    ap.add_argument("--root", default=DEFAULT_ROOT)
    ap.add_argument("--as-of", default=DEFAULT_AS_OF)
    ap.add_argument("--seed", type=int, default=DEFAULT_SEED, help="체크리스트 가상 상태 난수 seed (기본 %d, 바꾸지 않는다)" % DEFAULT_SEED)
    args = ap.parse_args(argv)
    root = args.root
    as_of = parse_iso(args.as_of)
    if as_of is None:
        print(json.dumps({"status": "error", "error": "--as-of 형식 오류: %s" % args.as_of}, ensure_ascii=False))
        return 2
    month_end = month_end_of(as_of)
    horizon_end = month_end_of(month_end + timedelta(days=1))
    cmd = "python3 %s --root %s --as-of %s --seed %d" % (SCRIPT_REF, root, as_of.isoformat(), args.seed)
    started = datetime.now().isoformat(timespec="seconds")
    present = {p: os.path.exists(os.path.join(root, p)) for p in ALL_SOURCES}

    # 핸드오프 로그 — 시작 (중단되어도 "무엇을 시도했는가"는 남는다)
    handoff = write_handoff(root, "실행 중 (%s)" % started, {
        "시도한 것": ["- %s 시작: `%s`" % (started, cmd)],
        "본 데이터·근거": ["- 입력 존재 여부: " + ", ".join("%s=%s" % (p, "O" if ok else "X") for p, ok in present.items()),
                      "- 계약: DATA_CONTRACT v2 §11, §4-5(onboarding-plan 보충), §3-1/§3-3/§3-4, §4-2 totals.plannedIn, §4-3 riskBand"],
        "실패한 것": ["- (실행 중)"], "검증된 것": ["- (실행 중)"], "다음 agent 인계점": ["- (실행 중)"]})

    missing = [p for p in (PATH_JOINERS, PATH_MASTER) if not present[p]]
    if missing:
        write_handoff(root, "실패 — 필수 입력 없음 (%s)" % started, {
            "시도한 것": ["- %s: `%s`" % (started, cmd)],
            "본 데이터·근거": ["- 입력 존재 여부: " + ", ".join("%s=%s" % (p, "O" if ok else "X") for p, ok in present.items())],
            "실패한 것": ["- 필수 입력 없음: %s — 산출물을 쓰지 않았다(exit 1)" % ", ".join(missing),
                       "- 원천(data/raw/)으로 대체하지 않았다 — 통계·파생은 정제 데이터에서만(GLOSSARY 관계 절)"],
            "검증된 것": ["- (없음)"],
            "다음 agent 인계점": ["- people-data-cleanser가 %s를 만든 뒤 이 스크립트를 재실행한다" % ", ".join(missing)]})
        print(json.dumps({"status": "error", "error": "필수 입력 없음 — people-data-cleanser 선행", "missing": missing,
                          "requires": "people-data-cleanser", "handoffLog": handoff}, ensure_ascii=False))
        return 1

    gaps: List[Dict[str, Any]] = []
    joiners = read_csv(os.path.join(root, PATH_JOINERS))
    master = read_csv(os.path.join(root, PATH_MASTER))
    master_by_id = {r.get("empId", ""): r for r in master}

    dept_order, dept_name = [], {}
    if present[PATH_ORG]:
        for r in read_csv(os.path.join(root, PATH_ORG)):
            if r.get("deptCode"):
                dept_order.append(r["deptCode"])
                dept_name[r["deptCode"]] = r.get("department", "")
    else:
        gaps.append(gap("missing-input", "org-chart.csv 없음 — 조직 순서·명칭을 정제 데이터로 대체", evidence=PATH_ORG))
    for r in master + joiners:
        dept_name.setdefault(r.get("deptCode", ""), r.get("department", ""))

    risk_available = present[PATH_RISK]
    risk: Dict[str, Dict[str, Any]] = {}
    if risk_available:
        try:
            risk = {e["empId"]: e for e in read_json(os.path.join(root, PATH_RISK)).get("byEmployee", []) if e.get("empId")}
        except (ValueError, AttributeError, TypeError) as ex:
            risk_available = False
            gaps.append(gap("missing-input", "attrition-risk.json 파싱 실패(%s) — riskBand=null, 버디 리스크 조건 미적용" % ex, evidence=PATH_RISK))
    else:
        gaps.append(gap("missing-input", "attrition-risk.json 없음 — riskBand=null, 버디 후보의 '리스크 낮음' 조건 미적용, highRiskCount=0", evidence=PATH_RISK))

    leavers: List[Dict[str, str]] = []
    if present[PATH_LEAVERS]:
        leavers = read_csv(os.path.join(root, PATH_LEAVERS))
    else:
        gaps.append(gap("missing-input", "planned-leavers.clean.csv 없음 — earlyAttrition은 0/0", evidence=PATH_LEAVERS))

    timeline, invalid = build_timeline(joiners, dept_name)
    flat = [j for b in timeline for j in b["joiners"]]
    by_dept = build_by_department(flat, master, dept_order, dept_name, risk, risk_available, as_of, month_end, gaps)
    checklist = build_checklist(flat, by_dept, as_of, args.seed)
    cohort = build_cohort(master, risk, as_of)
    early = build_early_attrition(leavers, master_by_id, dept_name, as_of, month_end)

    for inv in invalid:
        gaps.append(gap("invalid-row", "plannedHireDate 없음/비정상(%s) → 타임라인 제외" % inv["rawValue"], criterionId=inv["joinerId"], evidence=PATH_JOINERS))
    beyond = [j["joinerId"] for j in flat if date.fromisoformat(j["plannedHireDate"]) > horizon_end]
    past = [j["joinerId"] for j in flat if date.fromisoformat(j["plannedHireDate"]) <= as_of]
    if beyond:
        gaps.append(gap("beyond-horizon", "horizonEnd(%s) 이후 입사 예정 %s — 타임라인에는 포함(대사 조건)" % (horizon_end.isoformat(), beyond)))
    if past:
        gaps.append(gap("past-planned-hire", "입사 예정일이 기준일 이전 %s — 마스터 반영 여부 확인" % past))

    # 대사: 타임라인 합계 = 유효 행 수(27), 월말 이전 입사 예정 = forecast.totals.plannedIn(19)
    month_end_joiners = sum(1 for j in flat if date.fromisoformat(j["plannedHireDate"]) <= month_end)
    forecast_in: Optional[int] = None
    if present[PATH_FORECAST]:
        try:
            forecast_in = int((read_json(os.path.join(root, PATH_FORECAST)).get("totals") or {}).get("plannedIn"))
        except (TypeError, ValueError, AttributeError):
            forecast_in = None
            gaps.append(gap("missing-input", "month-end-forecast.json의 totals.plannedIn을 읽지 못함 — 월말 교차 대사 생략", evidence=PATH_FORECAST))
    else:
        gaps.append(gap("missing-input", "month-end-forecast.json 없음 — 월말 교차 대사(monthEndMatch) 생략", evidence=PATH_FORECAST))
    month_end_match = None if forecast_in is None else (month_end_joiners == forecast_in)
    if month_end_match is False:
        gaps.append(gap("reconciliation-mismatch", "월말 이전 입사 예정 %d vs forecast.totals.plannedIn %d" % (month_end_joiners, forecast_in), evidence=PATH_FORECAST))
    valid_rows = len(joiners) - len(invalid)
    recon = {"timelineJoiners": len(flat), "plannedJoinersValidRows": valid_rows, "match": len(flat) == valid_rows and not invalid,
             "monthEndJoiners": month_end_joiners, "forecastPlannedIn": forecast_in, "monthEndMatch": month_end_match}

    plan: Dict[str, Any] = {"asOfDate": as_of.isoformat(), "horizonEnd": horizon_end.isoformat(), "timeline": timeline,
                            "byDepartment": by_dept, "checklist": checklist, "earlyTenureCohort": cohort, "earlyAttrition": early,
                            "provenance": {"sources": [p for p in ALL_SOURCES if present[p]], "script": SCRIPT_REF,
                                           "reconciliation": recon, "gaps": gaps}}
    fit_checked = check_fit(root, plan, gaps)
    # §4-5 provenance 계약 키(sources/script/reconciliation/gaps) 뒤에 실행 메타를 덧붙인다 — 계약 확장 제안(contractGaps 보고)
    plan["provenance"].update({
        "seed": args.seed,
        "checklistNote": "체크리스트 상태는 가상 생성(random.seed(%d), 입사일 근접 → done 확률 상승). 실제 진행 상태가 아니다" % args.seed,
        "buddyRule": "같은 조직 재직자 중 재직 %.0f~%.0f년, 리스크 %s, 레벨 %s, 최대 %d명" % (BUDDY_TENURE[0], BUDDY_TENURE[1], BUDDY_RISK_BAND, "/".join(BUDDY_LEVELS), BUDDY_MAX),
        "deptLeadRule": "재직 %s 중 최장 재직(동률: 사번 오름차순), 없으면 최고 레벨 + gap(dept-lead-fallback)" % DEPT_LEAD_LEVEL,
        "pii": "timeline·buddyCandidates 성명 허용(온보딩 업무), 생년월일 없음. earlyTenureCohort·earlyAttrition은 사번·집계만",
        "fitCriteriaChecked": fit_checked})
    out_path = os.path.join(root, PATH_OUTPUT)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(plan, f, ensure_ascii=False, indent=2)
        f.write("\n")

    partial = (not recon["match"]) or month_end_match is False or any(g["kind"] in DEGRADING_GAPS for g in gaps)
    status = "partial" if partial else "ok"
    gap_kinds = sorted(set(g["kind"] for g in gaps))
    unmet = [g for g in gaps if g["kind"] == "fit-criterion-unmet"]
    unresolved = [{"joinerId": r.get("joinerId"), "unresolvedFlags": r.get("unresolvedFlags", "")} for r in joiners if (r.get("unresolvedFlags") or "").strip()]
    buddy_depts = sum(1 for d in by_dept if d["buddyCandidates"])
    finished = datetime.now().isoformat(timespec="seconds")

    # 핸드오프 로그 — 종료
    fails = [("- %s: %s%s" % (g["kind"], g["reason"], " [%s]" % g["criterionId"] if g.get("criterionId") else "")) for g in gaps] or ["- (없음)"]
    write_handoff(root, "%s (%s → %s)" % (status, started, finished), {
        "시도한 것": ["- %s: `%s`" % (started, cmd),
                   "- 정제 입사 예정자·마스터에서 timeline(ISO 주차)·byDepartment(버디·조직장 VP)·checklist(가상, seed %d)·earlyTenureCohort(90일)·earlyAttrition(퇴사 예정 중 1년 미만) 생성" % args.seed,
                   "- %s에 §11 shape로 작성, 종료 status=%s" % (PATH_OUTPUT, status)],
        "본 데이터·근거": ["- 입력 존재 여부: " + ", ".join("%s=%s" % (p, "O" if ok else "X") for p, ok in present.items()),
                      "- 정제 입사 예정자 %d행(유효 %d, 무효 %d) · 정제 마스터 %d행 · 퇴사 예정자 %d행 · riskBand 조인 %d명" % (len(joiners), valid_rows, len(invalid), len(master), len(leavers), len(risk)),
                      "- 계약 근거: §11 버디 규칙(재직 2~6년·리스크 낮음·IC3~Lead·≤3), §4-5 byDepartment=입사 예정 ≥1 조직만, §4-5 plannedOut 모집단(≤월말·unknown-emp 제외·재직) = earlyAttrition 분모, §2-7 조직마다 VP ≥ 1 → deptLeadEmpId=VP",
                      "- fitCriteria %d건·requiredFields(onboarding-plan.*) %d건 검사(%s)" % (fit_checked["fitCriteria"], fit_checked["requiredFields"], PATH_PERSONAS)],
        "실패한 것": fails,
        "검증된 것": ["- 타임라인 합계 %d vs 정제 입사 예정자 %d행(유효 %d·무효 %d) → match=%s (무효 행이 있으면 false — 타임라인이 정제 행 전부를 담아야 §11 assert)"
                   % (recon["timelineJoiners"], len(joiners), valid_rows, len(invalid), recon["match"]),
                   "- 월말(%s) 이전 입사 예정 %d vs forecast.totals.plannedIn %s → monthEndMatch=%s" % (month_end.isoformat(), month_end_joiners, forecast_in, month_end_match),
                   "- 주차 %d개(isocalendar), 입사 예정 조직 %d개, 버디 후보 ≥1 조직 %d개, 체크리스트 행 %d = 타임라인 %d" % (len(timeline), len(by_dept), buddy_depts, len(checklist["status"]), len(flat)),
                   "- 90일 코호트 %d명(고위험 %d) · 조기 이탈 %d/%d = %.4f" % (cohort["count"], cohort["highRiskCount"], early["under1YearLeavers"], early["totalLeavers"], early["rate"]),
                   "- PII: earlyTenureCohort·earlyAttrition에 성명·생년월일 없음, timeline·buddyCandidates에 생년월일 없음"],
        "다음 agent 인계점": ["- product-builder(onboard): `%s`를 site/data/onboard.json의 onboardingPlan으로 내장. O-F7(미해결 플래그)은 plannedJoiners 조인으로 표시(타임라인에는 unresolvedFlags 없음 — 계약 §11)" % PATH_OUTPUT,
                          "- product-judge(onboarding 옹호자): provenance.gaps의 fit-criterion-unmet %d건(%s)이 감점 근거" % (len(unmet), ", ".join(str(g["criterionId"]) for g in unmet) or "없음"),
                          "- people-data-auditor: tests/test_reconciliation.py에서 timelineJoiners=27·monthEndJoiners=19·earlyAttrition.totalLeavers=14 대조",
                          "- 재실행 조건: 클린저·attrition-risk·forecast·persona-needs 갱신 시 같은 명령으로 재실행(멱등, seed 고정)"]})

    summary = {"status": status, "asOfDate": as_of.isoformat(), "horizonEnd": horizon_end.isoformat(), "output": PATH_OUTPUT, "handoffLog": handoff,
               "timelineJoiners": len(flat), "weeks": len(timeline), "departmentsWithJoiners": len(by_dept),
               "monthEndJoiners": month_end_joiners, "nextMonthJoiners": sum(1 for j in flat if month_end < date.fromisoformat(j["plannedHireDate"]) <= horizon_end),
               "byDepartment": [{"deptCode": d["deptCode"], "department": d["department"], "joiners": d["joiners"], "joinersByMonthEnd": d["joinersByMonthEnd"],
                                 "buddyCandidates": len(d["buddyCandidates"]), "deptLeadEmpId": d["deptLeadEmpId"]} for d in by_dept],
               "buddyCoverage": {"departmentsWithBuddy": buddy_depts, "departmentsWithJoiners": len(by_dept)},
               "checklistRows": len(checklist["status"]),
               "earlyTenureCohort": {"count": cohort["count"], "highRiskCount": cohort["highRiskCount"]},
               "earlyAttrition": {k: early[k] for k in ("rate", "under1YearLeavers", "totalLeavers")},
               "reconciliation": recon, "plannedJoinersRowsIn": len(joiners),
               "unresolved": unresolved, "fitCriteriaChecked": fit_checked,
               "gapCount": len(gaps), "gapKinds": gap_kinds,
               "provenanceGaps": gaps}
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
