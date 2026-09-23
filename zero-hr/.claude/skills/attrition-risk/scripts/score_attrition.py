#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
score_attrition.py — 이직 리스크 점수 (attrition-risk, model rule-based-v1)

DATA_CONTRACT v2 §4-3 구현. Python 3.9 표준 라이브러리만 사용(pandas 없음).

입력
  {root}/data/clean/headcount-master.clean.csv   필수  (§3-1 정제 마스터, 427행 = 재직 406 + 휴직 21)
  {root}/data/reference/org-chart.csv            권장  (§1 조직 그룹 4 > 조직 11 — byDepartment/byOrgGroup 순서·명칭)
  {root}/data/clean/to-plan.clean.csv            권장  (§3-2 — dept-understaffed 요인 입력; 없으면 요인 0명 + warning)
  {root}/data/stats/headcount-stats.json         선택  (§4-1 — totals.activeHeadcount(406) 대사)
출력
  {root}/data/stats/attrition-risk.json          (§4-3 shape)
  {root}/_workspace/handoff/05-attrition.md      핸드오프 로그 (실행 시작 시 1차, 종료 시 확정 — handoff-log-policy)
  stdout 마지막 줄: 요약 JSON 1행 (워크플로우가 파싱; 개인 행 없음)

사용법
  python3 score_attrition.py [--root DIR] [--as-of YYYY-MM-DD]
                             [--weights '{"tenure-1-3y":20,...}'] [--no-calibrate] [--top-factors 3]

설계 요지
  - 재직(status=재직) 406명만 점수화한다. 휴직자는 TO 비교·예측의 기준 모집단(재직 인원)이 아니므로 제외(§4-3).
  - 점수 = 해당 요인 실효 가중치의 합(0~100 캡). 요인은 참/거짓만 판정해 개인별 근거(topFactors)를 그대로 설명한다.
  - 밴드 경계(높음>=60, 중간 35~59, 낮음<35)와 밴드별 3개월 기대 이탈 확률(0.35/0.12/0.03)은 계약이 고정한다.
    분포 목표(높음 8~15%, 중간 25~35%)는 경계가 아니라 가중치로 맞춘다: 신호군/기초군 배율 2개를 격자 탐색(결정적).
  - byEmployee에는 성명·생년월일·연령대·소속명을 넣지 않는다(pii-minimization-policy). HR 뷰가 사번으로 마스터에 조인한다.
"""

import argparse
import csv
import json
import os
import sys
import time
from datetime import datetime

DEFAULT_ROOT = "/Users/yang/development/zero-hr"
DEFAULT_AS_OF = "2026-09-23"

MASTER_PATH = os.path.join("data", "clean", "headcount-master.clean.csv")
TO_PLAN_PATH = os.path.join("data", "clean", "to-plan.clean.csv")
ORG_CHART_PATH = os.path.join("data", "reference", "org-chart.csv")
STATS_PATH = os.path.join("data", "stats", "headcount-stats.json")
OUTPUT_PATH = os.path.join("data", "stats", "attrition-risk.json")
HANDOFF_PATH = os.path.join("_workspace", "handoff", "05-attrition.md")
SCRIPT_REL = ".claude/skills/attrition-risk/scripts/score_attrition.py"
AGENT_NAME = "attrition-risk-scorer"
STAGE_NAME = "05-attrition"

MODEL_NAME = "rule-based-v1"
BANDS = {"높음": "score>=60", "중간": "35<=score<60", "낮음": "score<35"}
BAND_PROBABILITY = {"높음": 0.35, "중간": 0.12, "낮음": 0.03}   # §4-3 expectedProbability (3개월)
BAND_TARGET = {"높음": (0.08, 0.15), "중간": (0.25, 0.35)}       # 분포 목표(극단 방지)
BAND_TARGET_MID = {"높음": 0.115, "중간": 0.30}

SCORED_STATUS = "재직"                       # §4-3: 재직자 406만 점수화
ON_LEAVE_STATUS = "휴직"
NON_REGULAR = ("계약직", "인턴", "파견")
ENG_DATA_AI = ("Engineering", "Data/AI")
IC_LEVELS = ("IC1", "IC2", "IC3")
STAGNATION_LEVELS = ("IC1", "IC2")
CONTRACT_WINDOW_DAYS = 90
STAGNATION_TENURE_YEARS = 3.0
UNDERSTAFFED_GAP_BELOW = 0                  # gapAsOf < 0 (소속 조직 TO 부족)

HANDOFF_SECTIONS = ("시도한 것", "본 데이터·근거", "실패한 것", "검증된 것", "다음 agent 인계점")
BY_EMPLOYEE_KEYS = ("empId", "deptCode", "riskScore", "riskBand", "topFactors")   # §4-3 — 이 외 키 금지(PII)

# 요인 정의 (factor, group, base weight, definition, why)
# group: signal = 개인 이탈 신호(드물고 강함), baseline = 널리 분포하는 인구·조직 특성(흔하고 약함)
FACTORS = [
    ("tenure-1-3y", "signal", 22,
     "재직기간 1년 이상 3년 미만 (tenureBand 1~3년)",
     "역량이 시장에서 인정받기 시작하고 첫 이직 창이 열리는 구간 — 일반적으로 이직률이 가장 높은 재직 구간"),
    ("level-stagnation", "signal", 24,
     "재직기간 %.0f년 이상인데 레벨이 IC1 또는 IC2" % STAGNATION_TENURE_YEARS,
     "레벨은 재직기간과 양의 상관이므로 3년+ IC1/IC2는 뚜렷한 승급 정체 신호 — 승급 좌절은 자발퇴사의 대표 동기"),
    ("contract-expiring", "signal", 35,
     "고용유형 계약직·인턴·파견이고 계약종료일이 기준일로부터 %d일 이내(경과 포함)" % CONTRACT_WINDOW_DAYS,
     "계약 만료는 가장 확실한 이탈 이벤트. 만료일이 지났는데 재직이면 갱신 미반영이므로 동일하게 취급"),
    ("job-family-eng-data-ai", "baseline", 10,
     "직군이 Engineering 또는 Data/AI",
     "외부 수요가 가장 큰 직군 — 같은 조건이면 이직 기회 자체가 많다. 재직의 약 1/3이 해당하므로 단독으로 밴드를 바꾸지 않게 작게"),
    ("age-20s-30s", "baseline", 7,
     "연령대가 20대 또는 30대",
     "커리어 초·중반은 이동 비용이 낮다. 재직의 약 75%가 해당하므로 단독으로 밴드를 바꾸지 않도록 작게"),
    ("dept-understaffed", "baseline", 8,
     "소속 조직의 기준일 TO 과부족(재직 − TO)이 %d 미만 (gapAsOf<0)" % UNDERSTAFFED_GAP_BELOW,
     "정원 미달 조직은 1인당 업무 부하가 커져 번아웃·이탈이 늘어난다. 데모에서는 11개 중 8개 조직이 해당해 재직의 약 80%가 걸리므로 조직 단위 기초 요인으로 작게"),
    ("level-ic", "baseline", 5,
     "레벨이 IC1~IC3 (개인 기여자)",
     "관리·리드 레벨은 보상·역할로 조직 결속이 커서 이탈이 적다. 재직의 약 45%가 해당 → 최소 가중치"),
]
FACTOR_ORDER = [f[0] for f in FACTORS]
FACTOR_GROUP = {f[0]: f[1] for f in FACTORS}

# 산출물 JSON에 들어 있으나 §4-3에 명시되지 않은 보충 필드 — 계약 갱신 후보(만들지 않고 보고: contractGaps)
KNOWN_CONTRACT_GAPS = [
    "attrition-risk.json model.calibration(보정 배율·targetMet·target)와 model.assumptions[]는 §4-3 model shape에 없음 — reconciliation-policy(가정 명시)를 위해 추가, 계약 §4-3 보충 필요",
    "attrition-risk.json byDepartment[]의 department/orgGroupCode/orgGroup/toGapAsOf는 §4-3에 없음(§4-1·§4-2 byDepartment와 같은 명칭 열 + dept-understaffed 요인 근거) — 계약 §4-3 보충 필요",
    "attrition-risk.json byOrgGroup[] shape은 §4-3이 []로 비워 둠 — byDepartment와 동일 필드에 orgGroupCode/orgGroup을 둔 형태로 정의",
    "attrition-risk.json provenance{source,toPlan,script,weightsOverridden}는 §4-3에 없음(§4-1·§4-2·§10·§11은 모두 provenance 보유) — 계약 §4-3 보충 필요",
]


# ---------------------------------------------------------------- utils

def parse_iso(s):
    s = (s or "").strip()
    try:
        return datetime.strptime(s[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def to_float(s):
    try:
        return float(str(s).strip())
    except (TypeError, ValueError):
        return None


def read_csv(path):
    with open(path, "r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def band_of(score):
    return "높음" if score >= 60 else ("중간" if score >= 35 else "낮음")


def pct(n, d):
    return round(100.0 * n / d, 1) if d else 0.0


# ---------------------------------------------------------------- handoff log (handoff-log-policy)

def write_handoff(root, as_of_text, phase, sections):
    """_workspace/handoff/05-attrition.md — 5개 H2 고정. phase: '실행 중' | '완료' | '실패'."""
    path = os.path.join(root, HANDOFF_PATH)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    lines = ["# %s — %s — %s (%s)" % (STAGE_NAME, AGENT_NAME, as_of_text, phase), ""]
    for h in HANDOFF_SECTIONS:
        lines.append("## " + h)
        items = sections.get(h) or ["- (없음)"]
        lines.extend(items)
        lines.append("")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
    return HANDOFF_PATH


def handoff_start(root, as_of_text, argv_text):
    return write_handoff(root, as_of_text, "실행 중", {
        "시도한 것": ["- 실행 시작 %s: `%s`" % (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), argv_text),
                   "- 모델 %s, 요인 %d개(신호 %d·기초 %d), 밴드 경계 %s" % (
                       MODEL_NAME, len(FACTORS), sum(1 for f in FACTORS if f[1] == "signal"),
                       sum(1 for f in FACTORS if f[1] == "baseline"), json.dumps(BANDS, ensure_ascii=False))],
        "본 데이터·근거": ["- (실행 중 — 종료 시 갱신)"],
        "실패한 것": ["- (실행 중 — 종료 시 갱신)"],
        "검증된 것": ["- (실행 중 — 종료 시 갱신)"],
        "다음 agent 인계점": ["- (실행 중 — 비정상 종료 시 이 로그가 남아 있으면 스크립트가 중단된 것이다. stdout 오류를 확인하고 재실행)"],
    })


def handoff_failure(root, as_of_text, argv_text, error, requires=None):
    return write_handoff(root, as_of_text, "실패", {
        "시도한 것": ["- `%s`" % argv_text],
        "본 데이터·근거": ["- 입력 경로: `%s`(필수), `%s`(권장), `%s`(권장), `%s`(선택)" % (MASTER_PATH, ORG_CHART_PATH, TO_PLAN_PATH, STATS_PATH)],
        "실패한 것": ["- %s" % error] + (["- 선행 필요: `%s`" % requires] if requires else []),
        "검증된 것": ["- (없음 — 산출물 미작성)"],
        "다음 agent 인계점": ["- `%s` 미작성. %s" % (OUTPUT_PATH, ("`%s` 실행 후 이 단계를 재실행" % requires) if requires else "오류를 해결한 뒤 재실행"),
                          "- headcount-forecaster는 이 파일 없이도 실행 가능(riskAdjusted=null) — 단 리스크 시나리오가 빠진다"],
    })


# ---------------------------------------------------------------- loading

def load_org_chart(root, warnings):
    """§1: orgGroupCode,orgGroup,deptCode,department,formerNames,establishedOn → 조직 순서 목록."""
    path = os.path.join(root, ORG_CHART_PATH)
    if not os.path.exists(path):
        warnings.append("org-chart.csv 없음 — byDepartment/byOrgGroup은 마스터에 등장하는 조직만 포함(재직 0 조직 누락 가능)")
        return []
    out = []
    for r in read_csv(path):
        if (r.get("deptCode") or "").strip():
            out.append({k: (r.get(k) or "").strip() for k in ("orgGroupCode", "orgGroup", "deptCode", "department")})
    return out


def load_to_plan(root, warnings):
    """§3-2: deptCode → toHeadcount. 없으면 {} (dept-understaffed 요인 0명)."""
    path = os.path.join(root, TO_PLAN_PATH)
    if not os.path.exists(path):
        warnings.append("to-plan.clean.csv 없음 — dept-understaffed 요인은 0명")
        return {}
    to = {}
    for r in read_csv(path):
        code = (r.get("deptCode") or "").strip()
        n = to_float(r.get("toHeadcount"))
        if code and n is not None:
            to[code] = int(n)
    return to


def load_master(root, as_of, warnings):
    path = os.path.join(root, MASTER_PATH)
    if not os.path.exists(path):
        raise FileNotFoundError(path)
    by_id, dup = {}, 0
    for r in read_csv(path):
        emp = (r.get("empId") or "").strip()
        if not emp:
            continue
        if emp in by_id:
            dup += 1
        by_id[emp] = r
    if dup:
        warnings.append("정제 마스터에 중복 사번 %d건 — 뒤 행 유지(클린저 확인 필요)" % dup)
    employees = []
    for emp, r in by_id.items():
        hire = parse_iso(r.get("hireDate"))
        tenure = to_float(r.get("tenureYears"))
        if tenure is None and hire is not None:
            tenure = round(max(0, (as_of - hire).days) / 365.25, 2)
        employees.append({
            "empId": emp,
            "deptCode": (r.get("deptCode") or "").strip(),
            "department": (r.get("department") or "").strip(),
            "orgGroupCode": (r.get("orgGroupCode") or "").strip(),
            "orgGroup": (r.get("orgGroup") or "").strip(),
            "status": (r.get("status") or "").strip(),
            "jobFamily": (r.get("jobFamily") or "").strip(),
            "level": (r.get("level") or "").strip(),
            "ageBand": (r.get("ageBand") or "").strip(),
            "employmentType": (r.get("employmentType") or "").strip(),
            "contractEnd": parse_iso(r.get("contractEndDate")),
            "tenureYears": tenure,
        })
    return employees


# ---------------------------------------------------------------- factors / scoring

def evaluate_factors(e, as_of, understaffed_depts):
    t = e["tenureYears"]
    present = []
    if t is not None and 1.0 <= t < 3.0:
        present.append("tenure-1-3y")
    if t is not None and t >= STAGNATION_TENURE_YEARS and e["level"] in STAGNATION_LEVELS:
        present.append("level-stagnation")
    if e["employmentType"] in NON_REGULAR and e["contractEnd"] is not None \
            and (e["contractEnd"] - as_of).days <= CONTRACT_WINDOW_DAYS:
        present.append("contract-expiring")
    if e["jobFamily"] in ENG_DATA_AI:
        present.append("job-family-eng-data-ai")
    if e["ageBand"] in ("20대", "30대"):
        present.append("age-20s-30s")
    if e["deptCode"] in understaffed_depts:
        present.append("dept-understaffed")
    if e["level"] in IC_LEVELS:
        present.append("level-ic")
    return present


def effective_weights(base, scales):
    return {f: max(0, int(round(base[f] * scales[FACTOR_GROUP[f]]))) for f in FACTOR_ORDER}


def score_all(present_sets, weights):
    return [min(100, sum(weights[p] for p in present)) for present in present_sets]


def band_shares(scores):
    counts = {"높음": 0, "중간": 0, "낮음": 0}
    for s in scores:
        counts[band_of(s)] += 1
    n = len(scores)
    return {b: (counts[b] / n if n else 0.0) for b in counts}, counts


def range_penalty(shares):
    pen = 0.0
    for b, (lo, hi) in BAND_TARGET.items():
        pen += max(0.0, lo - shares[b]) + max(0.0, shares[b] - hi)
    return pen


def calibrate(present_sets, base):
    """신호군/기초군 배율 2개 격자 탐색. 목적: ① 범위 위반 최소 ② 배율 1.0에 가깝게 ③ 목표 중앙에 가깝게. 결정적."""
    def objective(ks, kb):
        shares, _ = band_shares(score_all(present_sets, effective_weights(base, {"signal": ks, "baseline": kb})))
        mid = sum(abs(shares[b] - BAND_TARGET_MID[b]) for b in BAND_TARGET_MID)
        return (round(range_penalty(shares), 6), round(abs(ks - 1.0) + abs(kb - 1.0), 6), round(mid, 6)), shares

    best = None
    grid = [round(0.5 + 0.05 * i, 2) for i in range(31)]
    for ks in grid:
        for kb in grid:
            obj, shares = objective(ks, kb)
            if best is None or obj < best[0]:
                best = (obj, ks, kb, shares)
    ks0, kb0 = best[1], best[2]
    for i in range(-5, 6):
        for j in range(-5, 6):
            ks, kb = round(ks0 + 0.01 * i, 2), round(kb0 + 0.01 * j, 2)
            if 0.5 <= ks <= 2.0 and 0.5 <= kb <= 2.0:
                obj, shares = objective(ks, kb)
                if obj < best[0]:
                    best = (obj, ks, kb, shares)
    obj, ks, kb, shares = best
    return {"signal": ks, "baseline": kb}, obj[0] == 0.0, shares


def aggregate(rows):
    counts = {"높음": 0, "중간": 0, "낮음": 0}
    for r in rows:
        counts[r["riskBand"]] += 1
    hc = len(rows)
    avg = round(sum(r["riskScore"] for r in rows) / hc, 1) if hc else 0.0
    expected = round(sum(BAND_PROBABILITY[b] * counts[b] for b in counts), 2)
    return counts, hc, avg, expected


# ---------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser(description="이직 리스크 점수 (rule-based-v1, DATA_CONTRACT v2 §4-3)")
    ap.add_argument("--root", default=DEFAULT_ROOT)
    ap.add_argument("--as-of", default=DEFAULT_AS_OF)
    ap.add_argument("--weights", default=None, help='기본 가중치 재정의 JSON (예: \'{"tenure-1-3y":20}\') — 지정 요인만')
    ap.add_argument("--no-calibrate", action="store_true", help="밴드 분포 보정을 끄고 기본 가중치 그대로 적용")
    ap.add_argument("--top-factors", type=int, default=3, help="byEmployee.topFactors 최대 개수")
    args = ap.parse_args()
    started = time.time()
    argv_text = "python3 %s %s" % (SCRIPT_REL, " ".join(sys.argv[1:]))

    def fail(msg, **extra):
        out = {"status": "error", "error": msg, "asOfDate": args.as_of, "artifacts": []}
        try:
            out["handoffLog"] = handoff_failure(args.root, args.as_of, argv_text, msg, extra.get("requires"))
        except OSError as ex:
            out["handoffLogError"] = str(ex)
        out.update(extra)
        print(json.dumps(out, ensure_ascii=False))
        return 2

    warnings = []
    as_of = parse_iso(args.as_of)
    if as_of is None:
        return fail("--as-of 형식 오류(YYYY-MM-DD): %s" % args.as_of)

    base = {f[0]: f[2] for f in FACTORS}
    overridden = {}
    if args.weights:
        try:
            overridden = {k: int(v) for k, v in json.loads(args.weights).items()}
        except (ValueError, TypeError, AttributeError):
            return fail("--weights JSON 파싱 실패")
        unknown = [k for k in overridden if k not in base]
        if unknown:
            return fail("알 수 없는 요인: %s" % unknown, knownFactors=FACTOR_ORDER)
        base.update(overridden)

    # 핸드오프 로그 1차(실행 시작)
    try:
        handoff_start(args.root, as_of.isoformat(), argv_text)
    except OSError as ex:
        warnings.append("핸드오프 로그 시작 기록 실패: %s" % ex)

    try:
        employees = load_master(args.root, as_of, warnings)
    except FileNotFoundError as ex:
        return fail("정제 마스터 없음: %s — people-data-cleanser 선행 필요" % ex, requires="people-data-cleanser")

    scored = [e for e in employees if e["status"] == SCORED_STATUS]
    on_leave = sum(1 for e in employees if e["status"] == ON_LEAVE_STATUS)
    other = len(employees) - len(scored) - on_leave
    if other:
        warnings.append("재직상태가 재직/휴직이 아닌 행 %d건 — 점수화 제외(클린저 확인 필요)" % other)
    if not scored:
        return fail("점수화 대상(재직) 0명", requires="people-data-cleanser")
    n = len(scored)

    org = load_org_chart(args.root, warnings)
    to_plan = load_to_plan(args.root, warnings)

    # 조직 목록: org-chart 순서 + 마스터에만 있는 코드(경고)
    dept_index = list(org)
    known = set(d["deptCode"] for d in org)
    for e in scored:
        if e["deptCode"] not in known:
            known.add(e["deptCode"])
            dept_index.append({"orgGroupCode": e["orgGroupCode"], "orgGroup": e["orgGroup"],
                               "deptCode": e["deptCode"], "department": e["department"]})
            warnings.append("조직 체계에 없는 조직 코드 '%s'가 마스터에 존재" % e["deptCode"])

    active_by_dept = {}
    for e in scored:
        active_by_dept[e["deptCode"]] = active_by_dept.get(e["deptCode"], 0) + 1
    dept_gap = {d: active_by_dept.get(d, 0) - to for d, to in to_plan.items()}
    understaffed = sorted(d for d, g in dept_gap.items() if g < UNDERSTAFFED_GAP_BELOW)

    present_sets = [evaluate_factors(e, as_of, set(understaffed)) for e in scored]

    # 보정
    scales = {"signal": 1.0, "baseline": 1.0}
    if args.no_calibrate or n < 20:
        if n < 20 and not args.no_calibrate:
            warnings.append("점수화 대상이 20명 미만이라 밴드 분포 보정을 건너뜀")
        shares, _ = band_shares(score_all(present_sets, effective_weights(base, scales)))
        target_met = range_penalty(shares) == 0.0
        if not target_met:
            warnings.append("보정 없이(기본 가중치) 밴드 분포가 목표 범위 밖 — 진단용 결과이며 하류에 넘기려면 보정 실행 필요")
    else:
        scales, target_met, shares = calibrate(present_sets, base)
        if not target_met:
            warnings.append("보정 후에도 밴드 분포가 목표 범위 밖 — factorPrevalence를 보고 --weights로 조정 권장")
    calib_applied = not (scales["signal"] == 1.0 and scales["baseline"] == 1.0)
    weights = effective_weights(base, scales)
    scores = score_all(present_sets, weights)

    prevalence = {f: 0 for f in FACTOR_ORDER}
    for present in present_sets:
        for p in present:
            prevalence[p] += 1

    # byEmployee (성명 없음 — §4-3 키 5개만)
    by_employee = []
    for e, present, s in zip(scored, present_sets, scores):
        ordered = sorted(present, key=lambda p: (-weights[p], FACTOR_ORDER.index(p)))
        by_employee.append({"empId": e["empId"], "deptCode": e["deptCode"], "riskScore": s,
                            "riskBand": band_of(s), "topFactors": ordered[:max(0, args.top_factors)]})
    by_employee.sort(key=lambda r: (-r["riskScore"], r["empId"]))

    # byDepartment — 조직 체계 순서(재직 0 조직 포함)
    emp_by_dept = {}
    for r in by_employee:
        emp_by_dept.setdefault(r["deptCode"], []).append(r)
    by_department = []
    for d in dept_index:
        counts, hc, avg, expected = aggregate(emp_by_dept.get(d["deptCode"], []))
        by_department.append({"deptCode": d["deptCode"], "department": d["department"],
                              "orgGroupCode": d["orgGroupCode"], "orgGroup": d["orgGroup"],
                              "activeHeadcount": hc, "높음": counts["높음"], "중간": counts["중간"], "낮음": counts["낮음"],
                              "avgRiskScore": avg, "expectedAttritionNext3Months": expected,
                              "toGapAsOf": dept_gap.get(d["deptCode"])})

    # byOrgGroup — 조직 그룹 순서
    group_order, group_label, dept_group = [], {}, {}
    for d in dept_index:
        dept_group[d["deptCode"]] = d["orgGroupCode"]
        if d["orgGroupCode"] not in group_label:
            group_order.append(d["orgGroupCode"])
            group_label[d["orgGroupCode"]] = d["orgGroup"]
    emp_by_group = {}
    for r in by_employee:
        emp_by_group.setdefault(dept_group.get(r["deptCode"], ""), []).append(r)
    by_org_group = []
    for g in group_order:
        counts, hc, avg, expected = aggregate(emp_by_group.get(g, []))
        by_org_group.append({"orgGroupCode": g, "orgGroup": group_label[g], "activeHeadcount": hc,
                             "높음": counts["높음"], "중간": counts["중간"], "낮음": counts["낮음"],
                             "avgRiskScore": avg, "expectedAttritionNext3Months": expected})

    counts_all, _, avg_all, expected_all = aggregate(by_employee)
    summary = {"높음": counts_all["높음"], "중간": counts_all["중간"], "낮음": counts_all["낮음"],
               "expectedAttritionNext3Months": expected_all}

    factors_out = []
    for factor, group, _, definition, why in FACTORS:
        k = scales[group]
        rationale = "%s. %s. 기본 가중치 %d × %s군 배율 %.2f → 실효 %d. 해당 인원 %d명(%.1f%%)" % (
            definition, why, base[factor], "신호" if group == "signal" else "기초", k, weights[factor],
            prevalence[factor], pct(prevalence[factor], n))
        if factor == "dept-understaffed":
            rationale += ". 해당 조직: %s" % (", ".join(understaffed) if understaffed else "없음")
        factors_out.append({"factor": factor, "weight": weights[factor], "rationale": rationale})

    assumptions = [
        "밴드별 3개월 이탈 확률 높음 0.35 / 중간 0.12 / 낮음 0.03 (계약 §4-3) — 기대 이탈 인원은 시나리오이며 예측을 대체하지 않는다",
        "요인은 참/거짓 판정, 점수는 실효 가중치 합(0~100 캡). 밴드 경계(60/35)는 계약 고정, 분포 목표(높음 8~15%·중간 25~35%)는 신호군·기초군 배율로 보정",
        "재직(status=재직) %d명만 점수화(휴직 %d명 제외) — TO 비교·예측 기준 모집단과 동일" % (n, on_leave),
        "퇴사 예정자도 재직이면 점수화 — headcount-forecaster의 riskAdjusted에서 plannedOut과 이중 계산 가능",
        "dept-understaffed는 기준일 TO 과부족(재직 − TO) < 0 인 조직 소속 여부(월말 예측이 아닌 기준일 기준)",
    ]

    output = {
        "asOfDate": as_of.isoformat(),
        "model": {"name": MODEL_NAME, "factors": factors_out, "bands": dict(BANDS),
                  "expectedProbability": dict(BAND_PROBABILITY),
                  "calibration": {"applied": calib_applied, "signalScale": scales["signal"],
                                  "baselineScale": scales["baseline"], "targetMet": bool(target_met),
                                  "target": {"높음": "8~15%", "중간": "25~35%"}},
                  "assumptions": assumptions},
        "byEmployee": by_employee,
        "byDepartment": by_department,
        "byOrgGroup": by_org_group,
        "summary": summary,
        "provenance": {"source": MASTER_PATH, "toPlan": TO_PLAN_PATH if to_plan else None,
                       "script": SCRIPT_REL, "weightsOverridden": overridden},
    }

    # 산출 전 검증 (pii-minimization / reconciliation)
    pii_ok = all(set(r.keys()) == set(BY_EMPLOYEE_KEYS) for r in by_employee)
    if not pii_ok:
        return fail("byEmployee에 계약 §4-3 외 키 존재 — PII 유출 위험으로 산출물 미작성")
    band_sum_ok = (summary["높음"] + summary["중간"] + summary["낮음"]) == n
    dept_sum = sum(d["activeHeadcount"] for d in by_department)
    group_sum = sum(g["activeHeadcount"] for g in by_org_group)
    if not band_sum_ok or dept_sum != n or group_sum != n:
        return fail("내부 대사 실패: summary 밴드 합 %d / byDepartment 합 %d / byOrgGroup 합 %d vs 점수화 %d" % (
            summary["높음"] + summary["중간"] + summary["낮음"], dept_sum, group_sum, n))

    out_path = os.path.join(args.root, OUTPUT_PATH)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(output, fh, ensure_ascii=False, indent=2)
        fh.write("\n")

    # 대사 (비치명): headcount-stats.totals.activeHeadcount
    recon = {"scoredEmployees": n, "onLeaveExcluded": on_leave, "masterRows": len(employees),
             "bandSumMatches": band_sum_ok, "byDepartmentHeadcountSum": dept_sum, "byOrgGroupHeadcountSum": group_sum,
             "byEmployeeKeysContractOnly": pii_ok,
             "statsFileFound": False, "statsActiveHeadcount": None, "headcountMatchesStats": None}
    stats_path = os.path.join(args.root, STATS_PATH)
    if os.path.exists(stats_path):
        try:
            with open(stats_path, "r", encoding="utf-8") as fh:
                stats_hc = (json.load(fh).get("totals") or {}).get("activeHeadcount")
            recon.update({"statsFileFound": True, "statsActiveHeadcount": stats_hc, "headcountMatchesStats": stats_hc == n})
            if stats_hc != n:
                warnings.append("재직 인원 불일치: headcount-stats.totals.activeHeadcount=%s vs 점수화 %d" % (stats_hc, n))
        except (ValueError, OSError) as ex:
            warnings.append("headcount-stats.json 읽기 실패: %s" % ex)

    band_shares_out = {b: round(counts_all[b] / n, 4) for b in counts_all}
    top_depts = sorted(by_department, key=lambda d: (-d["expectedAttritionNext3Months"], d["deptCode"]))[:5]
    elapsed = round(time.time() - started, 3)

    # 핸드오프 로그 확정(실행 종료)
    handoff_sections = {
        "시도한 것": [
            "- `%s` (소요 %.3fs)" % (argv_text, elapsed),
            "- 모델 %s: 요인 %d개(신호 3·기초 4), 밴드 경계 %s, 기대 확률 %s" % (
                MODEL_NAME, len(FACTORS), json.dumps(BANDS, ensure_ascii=False), json.dumps(BAND_PROBABILITY, ensure_ascii=False)),
            "- 보정: %s — 신호군 배율 %.2f · 기초군 배율 %.2f · targetMet=%s (목표 높음 8~15%% · 중간 25~35%%)" % (
                "적용" if calib_applied else "미적용(배율 1.0)", scales["signal"], scales["baseline"], target_met),
            "- 가중치 재정의(--weights): %s" % (json.dumps(overridden, ensure_ascii=False) if overridden else "없음"),
        ],
        "본 데이터·근거": [
            "- `%s`: %d행(사번 유일) → 재직 %d(점수화) · 휴직 %d(제외) · 기타 %d" % (MASTER_PATH, len(employees), n, on_leave, other),
            "- `%s`: %s" % (ORG_CHART_PATH, ("조직 %d개" % len(org)) if org else "없음"),
            "- `%s`: %s" % (TO_PLAN_PATH, ("조직 %d개, gapAsOf<0 조직 %s" % (len(to_plan), ", ".join(understaffed) or "없음")) if to_plan else "없음(dept-understaffed 0명)"),
            "- `%s`: %s" % (STATS_PATH, ("activeHeadcount=%s" % recon["statsActiveHeadcount"]) if recon["statsFileFound"] else "없음(대사 생략)"),
            "- 요인 유병률(재직 %d명 기준): %s" % (n, ", ".join("%s %d(%.1f%%)" % (f, prevalence[f], pct(prevalence[f], n)) for f in FACTOR_ORDER)),
            "- 실효 가중치: %s" % json.dumps(weights, ensure_ascii=False),
        ],
        "실패한 것": (["- %s" % w for w in warnings] if warnings else ["- (없음)"]),
        "검증된 것": [
            "- byEmployee %d행 = summary 밴드 합 %d = byDepartment 재직 합 %d = byOrgGroup 재직 합 %d" % (n, n, dept_sum, group_sum),
            "- headcount-stats.totals.activeHeadcount 대사: %s" % (
                ("일치(%d)" % n if recon["headcountMatchesStats"] else "불일치(stats %s vs %d)" % (recon["statsActiveHeadcount"], n)) if recon["statsFileFound"] else "생략(파일 없음)"),
            "- byEmployee 키 = §4-3 5개(empId, deptCode, riskScore, riskBand, topFactors)만 — 성명·생년월일·연령대 없음 (pii-minimization-policy)",
            "- 밴드 분포: 높음 %d(%.1f%%) · 중간 %d(%.1f%%) · 낮음 %d(%.1f%%) — 목표 %s" % (
                counts_all["높음"], 100 * band_shares_out["높음"], counts_all["중간"], 100 * band_shares_out["중간"],
                counts_all["낮음"], 100 * band_shares_out["낮음"], "충족" if target_met else "미충족"),
            "- summary.expectedAttritionNext3Months = %.2f (0.35×%d + 0.12×%d + 0.03×%d), 평균 점수 %.1f" % (
                expected_all, counts_all["높음"], counts_all["중간"], counts_all["낮음"], avg_all),
            "- model.bands 문자열 = 계약 §4-3과 동일",
        ],
        "다음 agent 인계점": [
            "- 산출물 `%s` (§4-3). 요약 JSON은 stdout 마지막 줄" % OUTPUT_PATH,
            "- **headcount-forecaster**: `byDepartment[].expectedAttritionNext3Months`(deptCode 조인) ÷ 3 → `riskAdjusted.expectedAttrition`. 퇴사 예정자가 점수화 모집단에 포함되므로 plannedOut과 이중 계산 가능 — assumptions에 명시할 것",
            "- **onboarding-plan-analyst**: `byEmployee[].riskBand`(empId 조인) → 버디 후보(낮음만)·90일 코호트 밴드",
            "- **product-builder(insight)**: `summary`·`byOrgGroup`·`byDepartment`는 executive/planning/orgLead 뷰(집계만), `byEmployee`는 hr 뷰에서만 정제 마스터와 조인해 성명 표시",
            "- **monthly-report-mailer**: `summary`·`byOrgGroup` 집계만 인용(개인 행 금지)",
            "- **people-data-auditor**: 위 '검증된 것' 항목을 정제 마스터에서 독립 재계산으로 대사. 상위 기대 이탈 조직: %s" % (
                ", ".join("%s %.2f" % (d["deptCode"], d["expectedAttritionNext3Months"]) for d in top_depts) or "없음"),
        ],
    }
    try:
        handoff_rel = write_handoff(args.root, as_of.isoformat(), "완료", handoff_sections)
    except OSError as ex:
        handoff_rel = None
        warnings.append("핸드오프 로그 기록 실패: %s" % ex)

    result = {
        "status": "ok", "asOfDate": as_of.isoformat(),
        "artifacts": [OUTPUT_PATH.replace(os.sep, "/")],
        "handoffLog": handoff_rel.replace(os.sep, "/") if handoff_rel else None,
        "elapsedSeconds": elapsed,
        "model": {"name": MODEL_NAME, "factorCount": len(FACTORS), "calibration": output["model"]["calibration"],
                  "weightsOverridden": overridden},
        "scoredEmployees": n,
        "summary": summary,
        "bandShares": band_shares_out,
        "avgRiskScore": avg_all,
        "byOrgGroup": by_org_group,
        "topRiskDepartments": [{k: d[k] for k in ("deptCode", "department", "activeHeadcount", "높음", "avgRiskScore", "expectedAttritionNext3Months")} for d in top_depts],
        "factorPrevalence": prevalence,
        "factorInputs": {"understaffedDepts": understaffed, "deptGapAsOf": dept_gap, "toPlanFound": bool(to_plan)},
        "reconciliation": recon,
        "assumptions": assumptions,
        "warnings": warnings,
        "contractGaps": list(KNOWN_CONTRACT_GAPS),
    }
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
