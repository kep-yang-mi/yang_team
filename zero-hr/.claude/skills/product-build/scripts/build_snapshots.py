#!/usr/bin/env python3
"""build_snapshots.py — 제품 스냅샷 조립기 (product-build 스킬).

data/stats/* · data/clean/* · personas/* · products/* 에서 DATA_CONTRACT §5 표의 제품별 스냅샷을
조립해 site/data/{insight,payroll,onboard,comparison}.json 에 쓴다. --embed 를 주면 각 제품 HTML의
<script id="report-data" type="application/json"> 블록에 같은 스냅샷을 내장한다.

스냅샷 구성 (DATA_CONTRACT §5 표):
  insight    = {stats, forecast, attrition, cleansingSummary, hrDirectory, automationEffect}
  payroll    = {payrollClose, statsSubset, cleansingSummary}
  onboard    = {onboardingPlan, plannedJoiners, hrDirectorySubset}
  comparison = products/product-comparison.json (§12) 그대로 — 없으면 §12 shape 의 빈 자리표시자

규칙:
- 숫자를 여기서 다시 계산하지 않는다. 상류 산출물을 그대로 싣고, 같은 지표가 서로 같은지만 검사한다(대사).
  세 제품이 같은 파일을 읽어야 "같은 지표는 같은 값"(reconciliation-policy)이 저절로 성립한다.
- hrDirectory 는 정제 마스터의 재직·휴직자에서 empId,name,teamCode,team,position 만 뽑는다(생년월일 제외).
- plannedJoiners 는 정제 입사 예정자에서 birthDate 를 뺀다. hrDirectorySubset 은 입사 예정자가 배치되는 팀의 명부만.
- Insight 의 automationEffect 는 data/stats/automation-effect.json 을 그대로 넣는다.
- Python 3.9 표준 라이브러리만. 원천/정제 CSV 는 utf-8-sig 로 읽고 산출물은 utf-8 로 쓴다.
- 컬럼명은 DATA_CONTRACT v1 을 정본으로 쓰되, GLOSSARY v2 정렬(orgCode/level 등)에 대비해
  COLUMN_CANDIDATES 의 후보 컬럼을 순서대로 찾는다. 후보로 대체하면 gap(column-fallback)에 남긴다.

사용법:
  python3 build_snapshots.py --root /Users/yang/development/zero-hr --as-of 2026-09-23 \
      --product {insight|payroll|onboard|comparison|all} [--embed]
stdout 마지막 줄에 결과 요약 JSON 한 줄을 출력한다. 진행 로그는 stderr.
종료 코드: 0 = 요청한 제품 모두 작성(ok/partial), 1 = 필수 입력 누락으로 작성 못한 제품 있음, 2 = 인자 오류.
"""
import argparse
import calendar
import csv
import json
import os
import re
import sys
from collections import OrderedDict
from datetime import date
from typing import Any, Dict, List, Optional, Tuple

DEFAULT_ROOT = "/Users/yang/development/zero-hr"
DEFAULT_AS_OF = "2026-09-23"
SCRIPT_REL = ".claude/skills/product-build/scripts/build_snapshots.py"
PRODUCT_CODES = ("insight", "payroll", "onboard", "comparison", "app", "decision")

# 입력 경로 (DATA_CONTRACT v1 정본)
INPUT_REL = OrderedDict([
    ("stats", os.path.join("data", "stats", "headcount-stats.json")),
    ("forecast", os.path.join("data", "stats", "month-end-forecast.json")),
    ("attrition", os.path.join("data", "stats", "attrition-risk.json")),
    ("cleansingSummary", os.path.join("data", "clean", "cleansing-summary.json")),
    ("master", os.path.join("data", "clean", "headcount-master.clean.csv")),
    ("automationEffect", os.path.join("data", "stats", "automation-effect.json")),
    ("payrollClose", os.path.join("data", "stats", "payroll-close.json")),
    ("onboardingPlan", os.path.join("data", "stats", "onboarding-plan.json")),
    ("plannedJoiners", os.path.join("data", "clean", "planned-joiners.clean.csv")),
    ("personaNeeds", os.path.join("personas", "persona-needs.json")),
    ("productComparison", os.path.join("products", "product-comparison.json")),
])
OUTPUT_REL = OrderedDict([(code, os.path.join("site", "data", "%s.json" % code)) for code in PRODUCT_CODES])
HTML_REL = OrderedDict([
    ("insight", os.path.join("site", "insight", "index.html")),
    ("payroll", os.path.join("site", "payroll", "index.html")),
    ("onboard", os.path.join("site", "onboard", "index.html")),
    ("comparison", os.path.join("site", "index.html")),
    ("app", os.path.join("site", "app", "index.html")),
    ("decision", os.path.join("site", "decision", "index.html")),
])

# 제품별 구성 요소: (필수, 선택). 필수가 없으면 그 제품은 error, 선택이 없으면 partial.
COMPOSITION = OrderedDict([
    ("insight", (("stats", "forecast"), ("attrition", "cleansingSummary", "hrDirectory", "automationEffect"))),
    ("payroll", (("payrollClose",), ("statsSubset", "cleansingSummary"))),
    ("onboard", (("onboardingPlan",), ("plannedJoiners", "hrDirectorySubset"))),
    ("comparison", ((), ("productComparison",))),
    ("app", (("stats", "forecast"), ("attrition", "cleansingSummary", "hrDirectory", "automationEffect",
                                       "payrollClose", "onboardingPlan", "plannedJoiners", "comparison", "changelog"))),
    ("decision", (("personaNeeds",), ("judging", "productComparison", "changelog", "unified", "inputs"))),
])
CHANGELOG_REL = os.path.join("products", "CHANGELOG.md")
JUDGING_DIR_REL = os.path.join("_workspace", "judging")
INPUTS_DIR_REL = os.path.join("products", "inputs")
RE_SECTION_TAG = re.compile(r"<section\b[^>]*>", re.IGNORECASE)
RE_ATTR = re.compile(r'(data-section|data-origin|data-role|data-fit|data-views)\s*=\s*"([^"]*)"')

CURRENT_STATUSES = ("재직", "휴직")
HR_DIRECTORY_FIELDS = ("empId", "name", "deptCode", "department", "level")  # DATA_CONTRACT v2 §3-1
# 출력 키는 계약 v1 이름. 원천 컬럼은 후보 중 첫 번째로 존재하는 것을 쓴다(v2 정렬 대비).
COLUMN_CANDIDATES = OrderedDict([
    ("empId", ("empId",)),
    ("name", ("name",)),
    ("deptCode", ("deptCode", "teamCode", "orgCode")),
    ("department", ("department", "team", "org", "orgName")),
    ("level", ("level", "position")),
    ("status", ("status",)),
    ("plannedHireDate", ("plannedHireDate",)),
])
PLANNED_JOINER_EXCLUDE = ("birthDate",)  # pii-minimization-policy: 생년월일은 어디에도 싣지 않는다
STATS_SUBSET_TOP = ("asOfDate", "client", "totals", "byOrgGroup", "byDepartment", "byAttributeAll")
STATS_SUBSET_ATTRIBUTES = ("employmentType", "status", "leaveType")
STATS_SUBSET_CROSSTABS = ("departmentByEmploymentType",)
EMBED_WARN_BYTES = 4 * 1024 * 1024  # 내장 JSON 이 이보다 크면 경고(페이지 총량 16MB 한도 대비 여유)
DOWNGRADE_KINDS = ("missing-input", "reconciliation-mismatch", "as-of-mismatch", "missing-column", "embed-skipped", "invalid-shape")

RE_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
RE_REPORT_DATA = re.compile(
    r'(<script\b[^>]*\bid\s*=\s*"report-data"[^>]*>)(.*?)(</script>)',
    re.DOTALL | re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# 유틸
# ---------------------------------------------------------------------------

def log(msg: str) -> None:
    sys.stderr.write(msg + "\n")


def dig(obj: Any, path: str) -> Any:
    """점 경로로 중첩 값을 읽는다. 없으면 None."""
    cur = obj
    for part in path.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return None
    return cur


def first_key(d: Any, keys: Tuple[str, ...]) -> Any:
    if not isinstance(d, dict):
        return None
    for k in keys:
        if k in d and d[k] not in (None, ""):
            return d[k]
    return None


def is_iso_date(value: Any) -> bool:
    if not isinstance(value, str) or not RE_ISO_DATE.match(value):
        return False
    try:
        date.fromisoformat(value)
    except ValueError:
        return False
    return True


def month_end_of(as_of: date) -> date:
    return date(as_of.year, as_of.month, calendar.monthrange(as_of.year, as_of.month)[1])


def make_gap(product: str, kind: str, path: str, effect: str) -> Dict[str, str]:
    return OrderedDict([("product", product), ("kind", kind), ("path", path), ("effect", effect)])


def make_check(product: str, name: str, left: Any, right: Any) -> Dict[str, Any]:
    if left is None or right is None:
        match = None  # 한쪽 입력이 없어 검사 불가 — 실패가 아니라 미검사
    else:
        match = left == right
    return OrderedDict([("product", product), ("check", name), ("left", left), ("right", right), ("match", match)])


# ---------------------------------------------------------------------------
# 입력 로딩 (실행 1회당 파일 1회 읽기)
# ---------------------------------------------------------------------------

class Inputs:
    def __init__(self, root: str, as_of: str) -> None:
        self.root = root
        self.as_of = as_of
        self._json_cache = {}  # type: Dict[str, Tuple[Any, Optional[str]]]
        self._csv_cache = {}  # type: Dict[str, Tuple[Any, Optional[str]]]

    def path(self, key: str) -> str:
        return os.path.join(self.root, INPUT_REL[key])

    def rel(self, key: str) -> str:
        return INPUT_REL[key]

    def json(self, key: str) -> Tuple[Any, Optional[str]]:
        if key in self._json_cache:
            return self._json_cache[key]
        path = self.path(key)
        if not os.path.exists(path):
            result = (None, "missing")  # type: Tuple[Any, Optional[str]]
        else:
            try:
                with open(path, "r", encoding="utf-8-sig") as fh:
                    result = (json.load(fh), None)
            except (OSError, ValueError) as exc:
                result = (None, "unreadable: %s" % exc)
        self._json_cache[key] = result
        return result

    def csv(self, key: str) -> Tuple[Any, Optional[str]]:
        """(header, rows) 를 돌려준다. rows 는 dict 목록."""
        if key in self._csv_cache:
            return self._csv_cache[key]
        path = self.path(key)
        if not os.path.exists(path):
            result = (None, "missing")  # type: Tuple[Any, Optional[str]]
        else:
            try:
                with open(path, "r", encoding="utf-8-sig", newline="") as fh:
                    reader = csv.DictReader(fh)
                    rows = [dict(r) for r in reader]
                    header = list(reader.fieldnames or [])
                result = ((header, rows), None)
            except (OSError, csv.Error) as exc:
                result = (None, "unreadable: %s" % exc)
        self._csv_cache[key] = result
        return result


def take_json(inputs: Inputs, key: str, product: str, required: bool,
              gaps: List[Dict[str, str]], components: Dict[str, bool]) -> Any:
    """JSON 입력을 읽고 구성 요소 존재 여부·gap·asOfDate 불일치를 기록한다."""
    obj, err = inputs.json(key)
    components[key] = obj is not None
    if obj is None:
        kind = "missing-input"
        effect = ("필수 입력 없음 — 제품 스냅샷 작성 불가" if required
                  else "선택 입력 없음 — 해당 구성 요소 null, 관련 화면은 '데이터 없음'으로 표시")
        gaps.append(make_gap(product, kind, inputs.rel(key), "%s (%s)" % (effect, err)))
        return None
    as_of = obj.get("asOfDate") if isinstance(obj, dict) else None
    if as_of is not None and as_of != inputs.as_of:
        gaps.append(make_gap(product, "as-of-mismatch", inputs.rel(key),
                             "asOfDate %s ≠ 요청 기준일 %s — 상류 재실행 필요" % (as_of, inputs.as_of)))
    return obj


def resolve_columns(header: List[str], keys: Tuple[str, ...], product: str, source_rel: str,
                    gaps: List[Dict[str, str]]) -> Dict[str, Optional[str]]:
    resolved = OrderedDict()  # type: Dict[str, Optional[str]]
    for key in keys:
        found = None
        for cand in COLUMN_CANDIDATES.get(key, (key,)):
            if cand in header:
                found = cand
                break
        if found is None:
            gaps.append(make_gap(product, "missing-column", source_rel,
                                 "컬럼 %s 없음(후보 %s) — 해당 필드 null" % (key, "/".join(COLUMN_CANDIDATES.get(key, (key,))))))
        elif found != key:
            gaps.append(make_gap(product, "column-fallback", source_rel,
                                 "%s ← %s 로 대체 — DATA_CONTRACT v2 정렬 시 출력 키 재확인" % (key, found)))
        resolved[key] = found
    return resolved


# ---------------------------------------------------------------------------
# 구성 요소 빌더
# ---------------------------------------------------------------------------

def build_hr_directory(inputs: Inputs, product: str, gaps: List[Dict[str, str]]) -> Optional[List[Dict[str, Any]]]:
    """정제 마스터의 재직·휴직자 → empId,name,teamCode,team,position (생년월일 제외)."""
    data, err = inputs.csv("master")
    if data is None:
        gaps.append(make_gap(product, "missing-input", inputs.rel("master"),
                             "정제 마스터 없음 — hrDirectory 생략, HR 뷰 성명 조인 불가 (%s)" % err))
        return None
    header, rows = data
    cols = resolve_columns(header, HR_DIRECTORY_FIELDS + ("status",), product, inputs.rel("master"), gaps)
    status_col = cols.get("status")
    out = []  # type: List[Dict[str, Any]]
    for row in rows:
        if status_col is not None:
            status = (row.get(status_col) or "").strip()
            if status not in CURRENT_STATUSES:
                continue
        entry = OrderedDict()  # type: Dict[str, Any]
        for field in HR_DIRECTORY_FIELDS:
            col = cols.get(field)
            entry[field] = (row.get(col) or "").strip() if col else None
        out.append(entry)
    out.sort(key=lambda e: ((e.get("deptCode") or ""), (e.get("empId") or "")))
    return out


def build_stats_subset(stats: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Payroll 이 쓰는 인원 통계 부분집합: 총계·본부·팀·고용유형/재직상태/휴직유형·본부×고용유형."""
    if not isinstance(stats, dict):
        return None
    subset = OrderedDict()  # type: Dict[str, Any]
    for key in STATS_SUBSET_TOP:
        if key in stats:
            subset[key] = stats[key]
    by_attr = stats.get("byAttribute") if isinstance(stats.get("byAttribute"), dict) else {}
    subset["byAttribute"] = OrderedDict((k, by_attr.get(k)) for k in STATS_SUBSET_ATTRIBUTES if k in by_attr)
    cross = stats.get("crossTabs") if isinstance(stats.get("crossTabs"), dict) else {}
    subset["crossTabs"] = OrderedDict((k, cross.get(k)) for k in STATS_SUBSET_CROSSTABS if k in cross)
    if "provenance" in stats:
        subset["provenance"] = stats["provenance"]
    return subset


def build_planned_joiners(inputs: Inputs, product: str,
                          gaps: List[Dict[str, str]]) -> Tuple[Optional[List[Dict[str, Any]]], Optional[int], Optional[int]]:
    """정제 입사 예정자(birthDate 제외). (rows, validRows, monthEndRows) 를 돌려준다."""
    data, err = inputs.csv("plannedJoiners")
    if data is None:
        gaps.append(make_gap(product, "missing-input", inputs.rel("plannedJoiners"),
                             "정제 입사 예정자 없음 — plannedJoiners 생략, 미해결 플래그 표시 불가 (%s)" % err))
        return None, None, None
    header, rows = data
    keep = [h for h in header if h not in PLANNED_JOINER_EXCLUDE]
    cols = resolve_columns(header, ("plannedHireDate",), product, inputs.rel("plannedJoiners"), gaps)
    date_col = cols.get("plannedHireDate")
    month_end = month_end_of(date.fromisoformat(inputs.as_of)).isoformat()
    out = []  # type: List[Dict[str, Any]]
    valid = 0
    by_month_end = 0
    for row in rows:
        entry = OrderedDict((h, (row.get(h) or "").strip()) for h in keep)
        out.append(entry)
        hire = (row.get(date_col) or "").strip() if date_col else ""
        if is_iso_date(hire):
            valid += 1
            if hire <= month_end:
                by_month_end += 1
    return out, valid, by_month_end


def build_hr_directory_subset(directory: Optional[List[Dict[str, Any]]], onboarding_plan: Optional[Dict[str, Any]],
                              joiners: Optional[List[Dict[str, Any]]]) -> Optional[List[Dict[str, Any]]]:
    """입사 예정자가 배치되는 팀의 명부만 — 온보딩 담당이 팀장·팀 규모를 볼 최소 범위."""
    if directory is None:
        return None
    teams = set()
    for team in (dig(onboarding_plan, "byDepartment") or dig(onboarding_plan, "byTeam") or []):
        code = first_key(team, ("deptCode", "teamCode", "orgCode"))
        if code:
            teams.add(code)
    if not teams:
        for joiner in (joiners or []):
            code = first_key(joiner, ("deptCode", "teamCode", "orgCode"))
            if code:
                teams.add(code)
    return [e for e in directory if e.get("deptCode") in teams]


# ---------------------------------------------------------------------------
# 제품별 조립
# ---------------------------------------------------------------------------

def assemble_insight(inputs: Inputs) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
    product = "insight"
    gaps = []  # type: List[Dict[str, str]]
    checks = []  # type: List[Dict[str, Any]]
    components = OrderedDict()  # type: Dict[str, bool]
    stats = take_json(inputs, "stats", product, True, gaps, components)
    forecast = take_json(inputs, "forecast", product, True, gaps, components)
    attrition = take_json(inputs, "attrition", product, False, gaps, components)
    cleansing = take_json(inputs, "cleansingSummary", product, False, gaps, components)
    directory = build_hr_directory(inputs, product, gaps)
    components["hrDirectory"] = directory is not None
    automation = take_json(inputs, "automationEffect", product, False, gaps, components)

    headcount = dig(stats, "totals.headcount")
    active = dig(stats, "totals.activeHeadcount")
    checks.append(make_check(product, "stats.totals.activeHeadcount=forecast.totals.activeHeadcount",
                             active, dig(forecast, "totals.activeHeadcount")))
    checks.append(make_check(product, "stats.totals.toGapAsOf=forecast.totals.toGapAsOf",
                             dig(stats, "totals.toGapAsOf"), dig(forecast, "totals.toGapAsOf")))
    checks.append(make_check(product, "hrDirectory.length=stats.totals.headcount",
                             len(directory) if directory is not None else None, headcount))
    if isinstance(dig(attrition, "summary"), dict):
        bands = dig(attrition, "summary")
        band_sum = sum(int(bands.get(b) or 0) for b in ("높음", "중간", "낮음"))
        checks.append(make_check(product, "attrition.summary(bands)=stats.totals.activeHeadcount", band_sum, active))
    master_unresolved = None
    if isinstance(dig(cleansing, "unresolvedItems"), list):
        master_unresolved = len([i for i in cleansing["unresolvedItems"] if i.get("source") == "headcount-master"])
    checks.append(make_check(product, "cleansingSummary.unresolvedItems(headcount-master)=stats.totals.unresolvedCount",
                             master_unresolved, dig(stats, "totals.unresolvedCount")))

    meta = OrderedDict([("gaps", gaps), ("checks", checks), ("components", components)])
    if stats is None or forecast is None:
        return None, meta
    snapshot = OrderedDict([
        ("stats", stats), ("forecast", forecast), ("attrition", attrition),
        ("cleansingSummary", cleansing), ("hrDirectory", directory), ("automationEffect", automation),
    ])
    return snapshot, meta


def assemble_payroll(inputs: Inputs) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
    product = "payroll"
    gaps = []  # type: List[Dict[str, str]]
    checks = []  # type: List[Dict[str, Any]]
    components = OrderedDict()  # type: Dict[str, bool]
    payroll_close = take_json(inputs, "payrollClose", product, True, gaps, components)
    stats = take_json(inputs, "stats", product, False, gaps, components)
    components["statsSubset"] = stats is not None
    cleansing = take_json(inputs, "cleansingSummary", product, False, gaps, components)
    # 예측은 내장하지 않고 대사에만 쓴다 — Payroll 화면의 월말 인원은 payrollClose 가 단일 출처
    forecast, _ = inputs.json("forecast")

    checks.append(make_check(product, "payrollClose.payrollHeadcount.asOfTotal=stats.totals.headcount",
                             dig(payroll_close, "payrollHeadcount.asOfTotal"), dig(stats, "totals.headcount")))
    checks.append(make_check(product, "payrollClose.payrollHeadcount.monthEndActive=forecast.totals.forecastMonthEnd",
                             dig(payroll_close, "payrollHeadcount.monthEndActive"), dig(forecast, "totals.forecastMonthEnd")))
    checks.append(make_check(product, "payrollClose.prorations.plannedJoinersByMonthEnd=forecast.totals.plannedIn",
                             _length(dig(payroll_close, "prorations.plannedJoinersByMonthEnd")), dig(forecast, "totals.plannedIn")))
    checks.append(make_check(product, "payrollClose.prorations.plannedLeaversByMonthEnd=forecast.totals.plannedOut",
                             _length(dig(payroll_close, "prorations.plannedLeaversByMonthEnd")), dig(forecast, "totals.plannedOut")))

    meta = OrderedDict([("gaps", gaps), ("checks", checks), ("components", components)])
    if payroll_close is None:
        return None, meta
    snapshot = OrderedDict([
        ("payrollClose", payroll_close), ("statsSubset", build_stats_subset(stats)), ("cleansingSummary", cleansing),
    ])
    return snapshot, meta


def assemble_onboard(inputs: Inputs) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
    product = "onboard"
    gaps = []  # type: List[Dict[str, str]]
    checks = []  # type: List[Dict[str, Any]]
    components = OrderedDict()  # type: Dict[str, bool]
    plan = take_json(inputs, "onboardingPlan", product, True, gaps, components)
    joiners, valid_rows, month_end_rows = build_planned_joiners(inputs, product, gaps)
    components["plannedJoiners"] = joiners is not None
    directory = build_hr_directory(inputs, product, gaps)
    subset = build_hr_directory_subset(directory, plan, joiners)
    components["hrDirectorySubset"] = subset is not None
    forecast, _ = inputs.json("forecast")

    timeline_total = None
    if isinstance(dig(plan, "timeline"), list):
        timeline_total = sum(len(week.get("joiners") or []) for week in plan["timeline"] if isinstance(week, dict))
    checks.append(make_check(product, "onboardingPlan.timeline(joiners)=planned-joiners.clean(validRows)",
                             timeline_total, valid_rows))
    checks.append(make_check(product, "planned-joiners.clean(byMonthEnd)=forecast.totals.plannedIn",
                             month_end_rows, dig(forecast, "totals.plannedIn")))
    checks.append(make_check(product, "onboardingPlan.checklist.status.length=timeline(joiners)",
                             _length(dig(plan, "checklist.status")), timeline_total))

    meta = OrderedDict([("gaps", gaps), ("checks", checks), ("components", components)])
    if plan is None:
        return None, meta
    snapshot = OrderedDict([
        ("onboardingPlan", plan), ("plannedJoiners", joiners), ("hrDirectorySubset", subset),
    ])
    return snapshot, meta


def assemble_comparison(inputs: Inputs) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
    product = "comparison"
    gaps = []  # type: List[Dict[str, str]]
    checks = []  # type: List[Dict[str, Any]]
    components = OrderedDict()  # type: Dict[str, bool]
    comparison = take_json(inputs, "productComparison", product, False, gaps, components)
    persona_needs, _ = inputs.json("personaNeeds")

    if comparison is None:
        # product-judge 가 아직 돌지 않은 첫 빌드 — 허브는 '비교 대기' 상태로 렌더링한다 (§12 shape 유지)
        snapshot = OrderedDict([
            ("asOfDate", inputs.as_of), ("products", []),
            ("comparison", OrderedDict([("bestFit", None), ("summary", ""), ("recommendation", "")])),
            ("judges", []),
        ])  # type: Dict[str, Any]
    else:
        snapshot = comparison
        for key in ("products", "comparison", "judges"):
            if key not in comparison:
                gaps.append(make_gap(product, "invalid-shape", inputs.rel("productComparison"),
                                     "§12 최상위 키 %s 없음 — product-judge 재실행" % key))
    codes = sorted(p.get("code") for p in (snapshot.get("products") or []) if isinstance(p, dict))
    if comparison is not None:
        checks.append(make_check(product, "productComparison.products(codes)=insight,onboard,payroll",
                                 ",".join(str(c) for c in codes), "insight,onboard,payroll"))
    if isinstance(persona_needs, dict) and comparison is not None:
        persona_products = sorted(p.get("product") for p in (persona_needs.get("personas") or []) if isinstance(p, dict))
        checks.append(make_check(product, "personaNeeds.personas(product)=productComparison.products(code)",
                                 ",".join(str(c) for c in persona_products), ",".join(str(c) for c in codes)))
    meta = OrderedDict([("gaps", gaps), ("checks", checks), ("components", components)])
    return snapshot, meta


def assemble_app(inputs: Inputs) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
    """통합 제품(§15): 세 제품 스냅샷의 합집합 + 제품 비교 + 변경 이력. 숫자는 재계산하지 않는다."""
    product = "app"
    gaps = []  # type: List[Dict[str, str]]
    checks = []  # type: List[Dict[str, Any]]
    components = OrderedDict()  # type: Dict[str, bool]
    stats = take_json(inputs, "stats", product, True, gaps, components)
    forecast = take_json(inputs, "forecast", product, True, gaps, components)
    attrition = take_json(inputs, "attrition", product, False, gaps, components)
    cleansing = take_json(inputs, "cleansingSummary", product, False, gaps, components)
    directory = build_hr_directory(inputs, product, gaps)
    components["hrDirectory"] = directory is not None
    automation = take_json(inputs, "automationEffect", product, False, gaps, components)
    payroll_close = take_json(inputs, "payrollClose", product, False, gaps, components)
    plan = take_json(inputs, "onboardingPlan", product, False, gaps, components)
    joiners, valid_rows, month_end_rows = build_planned_joiners(inputs, product, gaps)
    components["plannedJoiners"] = joiners is not None
    comparison = take_json(inputs, "productComparison", product, False, gaps, components)
    changelog_path = os.path.join(inputs.root, CHANGELOG_REL)
    changelog = None  # type: Optional[Dict[str, Any]]
    if os.path.exists(changelog_path):
        with open(changelog_path, "r", encoding="utf-8") as fh:
            changelog = OrderedDict([("path", CHANGELOG_REL), ("markdown", fh.read())])
    else:
        gaps.append(make_gap(product, "missing-input", CHANGELOG_REL, "변경 이력 없음 — 통합 제품의 changelog 탭은 '기록 없음'으로 표시"))
    components["changelog"] = changelog is not None

    active = dig(stats, "totals.activeHeadcount")
    checks.append(make_check(product, "stats.totals.activeHeadcount=forecast.totals.activeHeadcount",
                             active, dig(forecast, "totals.activeHeadcount")))
    checks.append(make_check(product, "payrollClose.payrollHeadcount.monthEndActive=forecast.totals.forecastMonthEnd",
                             dig(payroll_close, "payrollHeadcount.monthEndActive"), dig(forecast, "totals.forecastMonthEnd")))
    checks.append(make_check(product, "planned-joiners.clean(byMonthEnd)=forecast.totals.plannedIn",
                             month_end_rows, dig(forecast, "totals.plannedIn")))
    if isinstance(dig(attrition, "summary"), dict):
        bands = dig(attrition, "summary")
        band_sum = sum(int(bands.get(b) or 0) for b in ("높음", "중간", "낮음"))
        checks.append(make_check(product, "attrition.summary(bands)=stats.totals.activeHeadcount", band_sum, active))

    meta = OrderedDict([("gaps", gaps), ("checks", checks), ("components", components)])
    if stats is None or forecast is None:
        return None, meta
    snapshot = OrderedDict([
        ("stats", stats), ("forecast", forecast), ("attrition", attrition), ("cleansingSummary", cleansing),
        ("hrDirectory", directory), ("automationEffect", automation), ("payrollClose", payroll_close),
        ("onboardingPlan", plan), ("plannedJoiners", joiners), ("comparison", comparison), ("changelog", changelog),
    ])
    return snapshot, meta


def _read_text(path: str) -> Optional[str]:
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as fh:
        return fh.read()


def extract_unified_sections(root: str) -> Optional[List[Dict[str, Any]]]:
    """site/app/index.html 의 <section> 태그에서 data-section/data-origin/data-role/data-fit 을 뽑는다 (통합 결정 표)."""
    html_text = _read_text(os.path.join(root, HTML_REL["app"]))
    if html_text is None:
        return None
    out = []  # type: List[Dict[str, Any]]
    for tag in RE_SECTION_TAG.findall(html_text):
        attrs = dict((k, v) for k, v in RE_ATTR.findall(tag))
        if "data-section" not in attrs:
            continue
        out.append(OrderedDict([
            ("dataSection", attrs.get("data-section")),
            ("dataOrigin", attrs.get("data-origin")),
            ("dataRole", [x for x in re.split(r"[\s,]+", attrs.get("data-role", "")) if x]),
            ("dataFit", [x for x in re.split(r"[\s,]+", attrs.get("data-fit", "")) if x]),
        ]))
    return out


def assemble_decision(inputs: Inputs) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
    """채택 근거 페이지(§18): 페르소나 니즈 + 심판 3명 원본 + 비교 + 변경 이력 + 통합 섹션 출처 + 대기 인풋."""
    product = "decision"
    gaps = []  # type: List[Dict[str, str]]
    checks = []  # type: List[Dict[str, Any]]
    components = OrderedDict()  # type: Dict[str, bool]
    needs = take_json(inputs, "personaNeeds", product, True, gaps, components)
    comparison = take_json(inputs, "productComparison", product, False, gaps, components)
    judging = OrderedDict()  # type: Dict[str, Any]
    for code in ("payroll", "onboarding", "head-of-hr"):
        path = os.path.join(inputs.root, JUDGING_DIR_REL, "%s.json" % code)
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as fh:
                judging[code] = json.load(fh)
        else:
            judging[code] = None
            gaps.append(make_gap(product, "missing-input", os.path.join(JUDGING_DIR_REL, "%s.json" % code),
                                 "심판 %s 결과 없음 — 루브릭 절은 '심판 대기 중'" % code))
    components["judging"] = any(v is not None for v in judging.values())
    changelog_text = _read_text(os.path.join(inputs.root, CHANGELOG_REL))
    changelog = OrderedDict([("path", CHANGELOG_REL), ("markdown", changelog_text)]) if changelog_text is not None else None
    components["changelog"] = changelog is not None
    unified_sections = extract_unified_sections(inputs.root)
    components["unified"] = unified_sections is not None
    if unified_sections is None:
        gaps.append(make_gap(product, "missing-input", HTML_REL["app"], "통합 제품 없음 — 통합 결정 절은 '대기 중'"))
    pending_inputs = []  # type: List[Dict[str, Any]]
    inputs_dir = os.path.join(inputs.root, INPUTS_DIR_REL)
    if os.path.isdir(inputs_dir):
        for name in sorted(os.listdir(inputs_dir)):
            if name.endswith(".json") and not name.startswith("example-"):
                with open(os.path.join(inputs_dir, name), "r", encoding="utf-8") as fh:
                    try:
                        obj = json.load(fh)
                    except ValueError:
                        continue
                pending_inputs.append(OrderedDict([
                    ("file", os.path.join(INPUTS_DIR_REL, name)), ("persona", obj.get("persona")), ("title", obj.get("title")),
                    ("submittedAt", obj.get("submittedAt")), ("needs", len(obj.get("needs") or [])),
                    ("fitCriteria", len(obj.get("fitCriteria") or [])), ("origin", obj.get("origin")),
                ]))
    components["inputs"] = True
    if comparison is not None:
        codes = sorted(p.get("code") for p in (comparison.get("products") or []) if isinstance(p, dict))
        checks.append(make_check(product, "productComparison.products(codes)=insight,onboard,payroll",
                                 ",".join(str(c) for c in codes), "insight,onboard,payroll"))
        judge_names = sorted(j.get("judge") for j in (comparison.get("judges") or []) if isinstance(j, dict))
        file_names = sorted("persona-advocate:%s" % k for k, v in judging.items() if v is not None)
        checks.append(make_check(product, "productComparison.judges=judging files", ",".join(map(str, judge_names)), ",".join(file_names)))
    meta = OrderedDict([("gaps", gaps), ("checks", checks), ("components", components)])
    if needs is None:
        return None, meta
    personas = []
    for per in (needs.get("personas") or []):
        personas.append(OrderedDict([(k, per.get(k)) for k in ("code", "title", "titleEn", "product", "keyQuestions", "pains", "fitCriteria", "rubric") if k in per]))
    snapshot = OrderedDict([
        ("asOfDate", needs.get("asOfDate", inputs.as_of)), ("personas", personas), ("shared", needs.get("shared")),
        ("judging", judging), ("comparison", comparison), ("changelog", changelog),
        ("unified", OrderedDict([("sections", unified_sections)])), ("pendingInputs", pending_inputs),
    ])
    return snapshot, meta


ASSEMBLERS = OrderedDict([
    ("insight", assemble_insight), ("payroll", assemble_payroll),
    ("onboard", assemble_onboard), ("comparison", assemble_comparison), ("app", assemble_app),
    ("decision", assemble_decision),
])


def _length(value: Any) -> Optional[int]:
    return len(value) if isinstance(value, list) else None


# ---------------------------------------------------------------------------
# 쓰기·내장
# ---------------------------------------------------------------------------

def write_snapshot(root: str, code: str, snapshot: Dict[str, Any]) -> Tuple[str, int]:
    rel = OUTPUT_REL[code]
    path = os.path.join(root, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    text = json.dumps(snapshot, ensure_ascii=False, indent=2)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
        fh.write("\n")
    return rel, len(text.encode("utf-8"))


def embed_json_text(snapshot: Dict[str, Any]) -> str:
    """<script type=application/json> 안에 안전하게 들어가는 JSON 텍스트.
    '</' 와 '<!--' 가 스크립트 블록을 조기 종료/이스케이프 상태로 바꾸므로 JSON 유효 이스케이프로 치환한다."""
    text = json.dumps(snapshot, ensure_ascii=False, separators=(",", ":"))
    return text.replace("</", "<\\/").replace("<!--", "<\\u0021--")


def embed_snapshot(root: str, code: str, snapshot: Dict[str, Any], gaps: List[Dict[str, str]]) -> Optional[str]:
    rel = HTML_REL[code]
    path = os.path.join(root, rel)
    if not os.path.exists(path):
        gaps.append(make_gap(code, "embed-skipped", rel, "HTML 없음 — 페이지를 먼저 만든 뒤 --embed 재실행"))
        return None
    with open(path, "r", encoding="utf-8") as fh:
        html = fh.read()
    if not RE_REPORT_DATA.search(html):
        gaps.append(make_gap(code, "embed-skipped", rel,
                             '<script id="report-data" type="application/json"> 블록 없음 — page-template.md 골격 확인'))
        return None
    payload = embed_json_text(snapshot)
    if len(payload.encode("utf-8")) > EMBED_WARN_BYTES:
        gaps.append(make_gap(code, "size-warning", rel, "내장 JSON %d bytes — hrDirectory 범위·불필요 키 축소 검토" % len(payload)))
    new_html = RE_REPORT_DATA.sub(lambda m: m.group(1) + "\n" + payload + "\n" + m.group(3), html, count=1)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(new_html)
    return rel


# ---------------------------------------------------------------------------
# 실행
# ---------------------------------------------------------------------------

def product_status(snapshot: Optional[Dict[str, Any]], meta: Dict[str, Any]) -> str:
    if snapshot is None:
        return "error"
    if any(g["kind"] in DOWNGRADE_KINDS for g in meta["gaps"]):
        return "partial"
    if any(c["match"] is False for c in meta["checks"]):
        return "partial"
    return "ok"


def run(root: str, as_of: str, products: List[str], embed: bool) -> Dict[str, Any]:
    inputs = Inputs(root, as_of)
    results = OrderedDict()  # type: Dict[str, Any]
    all_gaps = []  # type: List[Dict[str, str]]
    all_checks = []  # type: List[Dict[str, Any]]
    for code in products:
        log("[product-build] assembling %s" % code)
        snapshot, meta = ASSEMBLERS[code](inputs)
        entry = OrderedDict()  # type: Dict[str, Any]
        entry["status"] = product_status(snapshot, meta)
        entry["path"] = OUTPUT_REL[code]
        entry["bytes"] = 0
        entry["components"] = meta["components"]
        entry["embedded"] = None
        entry["required"] = list(COMPOSITION[code][0])
        if snapshot is not None:
            rel, size = write_snapshot(root, code, snapshot)
            entry["bytes"] = size
            log("[product-build] wrote %s (%d bytes)" % (rel, size))
            if embed:
                entry["embedded"] = embed_snapshot(root, code, snapshot, meta["gaps"])
                entry["status"] = product_status(snapshot, meta)  # embed gap 반영
        else:
            log("[product-build] %s: required input missing — not written" % code)
        entry["checks"] = meta["checks"]
        results[code] = entry
        all_gaps.extend(meta["gaps"])
        all_checks.extend(meta["checks"])

    statuses = [r["status"] for r in results.values()]
    if "error" in statuses:
        overall = "error"
    elif "partial" in statuses:
        overall = "partial"
    else:
        overall = "ok"
    mismatches = [c for c in all_checks if c["match"] is False]
    summary = OrderedDict([
        ("status", overall),
        ("asOfDate", as_of),
        ("monthEnd", month_end_of(date.fromisoformat(as_of)).isoformat()),
        ("script", SCRIPT_REL),
        ("embed", embed),
        ("products", results),
        ("reconciliation", OrderedDict([
            ("matched", len(mismatches) == 0),
            ("checked", len([c for c in all_checks if c["match"] is not None])),
            ("skipped", len([c for c in all_checks if c["match"] is None])),
            ("mismatches", mismatches),
        ])),
        ("gaps", all_gaps),
    ])
    return summary


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Zero Company HR 제품 스냅샷(site/data/*.json) 조립")
    parser.add_argument("--root", default=DEFAULT_ROOT, help="프로젝트 루트 (기본 %s)" % DEFAULT_ROOT)
    parser.add_argument("--as-of", dest="as_of", default=DEFAULT_AS_OF, help="기준일 YYYY-MM-DD (기본 %s)" % DEFAULT_AS_OF)
    parser.add_argument("--product", default="all", choices=list(PRODUCT_CODES) + ["all"],
                        help="조립할 제품 (기본 all)")
    parser.add_argument("--embed", action="store_true",
                        help="site/{product}/index.html (허브는 site/index.html) 의 report-data 블록에 스냅샷을 내장")
    args = parser.parse_args(argv)

    try:
        date.fromisoformat(args.as_of)
    except ValueError:
        parser.error("--as-of 는 YYYY-MM-DD 형식이어야 합니다: %r" % args.as_of)
    root = os.path.abspath(args.root)
    if not os.path.isdir(root):
        parser.error("--root 가 디렉토리가 아닙니다: %s" % root)

    products = list(PRODUCT_CODES) if args.product == "all" else [args.product]
    summary = run(root, args.as_of, products, args.embed)
    sys.stdout.write(json.dumps(summary, ensure_ascii=False) + "\n")
    sys.stdout.flush()
    return 1 if summary["status"] == "error" else 0


if __name__ == "__main__":
    sys.exit(main())
