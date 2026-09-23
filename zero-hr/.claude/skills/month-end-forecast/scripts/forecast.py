#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""forecast.py — 월말 인원 예측 · TO 과부족 · 인력계획 인사이트 (DATA_CONTRACT v2 §4-2 / §4-5).

정제 데이터(②)만 읽는다. TO 비교·예측의 출발점은 **재직 인원(휴직 제외)** 이다.
  data/reference/org-chart.csv            조직 그룹(4) > 조직(11) 골격·순서
  data/clean/headcount-master.clean.csv   activeHeadcount = status 재직
  data/clean/to-plan.clean.csv            toHeadcount (기준월 행 우선)
  data/clean/planned-joiners.clean.csv    plannedHireDate ≤ 월말 → plannedIn / 다음 달 말까지 → nextMonth
  data/clean/planned-leavers.clean.csv    unknown-emp·마스터 비재직 제외, stale(예정일 경과)은 월말 퇴사로 반영
  data/stats/attrition-risk.json          선택 — 없으면 riskAdjusted = null + assumptions 명시
출력: data/stats/month-end-forecast.json · 핸드오프 로그 _workspace/handoff/04-forecast.md(시작·종료 시)
stdout 마지막 줄 = 요약 JSON 1행(워크플로우 반환 데이터).

결정적 규칙: recommendation = gapME ≤ −4 → 채용 가속 / gapME ≥ +5 → TO 재검토/이동배치 / 그 외 정상 관리.
인사이트 = 채용 가속 묶음 · TO 재검토 묶음 · 퇴사 영향 점검(재직 ≤ 12 이고 plannedOut ≥ 1).
시나리오 기본값: forecast = active + round(plannedIn × rate) − plannedOut − extraAttrition (rate 1.0, extra 0).
권고·즉시 액션은 제안이다 — 채용/TO 결정은 승인 gate(사람). 스크립트는 제안까지만 만든다.

사용법: python3 forecast.py [--root R] [--as-of 2026-09-23] [--self-check] [--check-only] [--narrative PATH]
종료 코드: 0 ok · 1 error(내부 대사 실패/예외) · 2 partial(--self-check 불일치) · 3 blocked(필수 입력 없음)
"""
import argparse
import calendar
import csv
import datetime
import json
import os
import sys
from collections import OrderedDict

DEFAULT_ROOT = "/Users/yang/development/zero-hr"
DEFAULT_AS_OF = "2026-09-23"
AGENT = "headcount-forecaster"
PHASE = "04-forecast"
SCRIPT_REL = ".claude/skills/month-end-forecast/scripts/forecast.py"
HANDOFF_REL = "_workspace/handoff/04-forecast.md"
REL = OrderedDict([
    ("org", "data/reference/org-chart.csv"),
    ("master", "data/clean/headcount-master.clean.csv"),
    ("to", "data/clean/to-plan.clean.csv"),
    ("joiners", "data/clean/planned-joiners.clean.csv"),
    ("leavers", "data/clean/planned-leavers.clean.csv"),
    ("risk", "data/stats/attrition-risk.json"),
    ("out", "data/stats/month-end-forecast.json"),
])
REQUIRED = ("master", "to", "joiners", "leavers")
FLAG_UNKNOWN_EMP = "unknown-emp"
FLAG_STALE = "stale-planned-leaver"
STATUS_ACTIVE = "재직"

REC_HIRE, REC_REVIEW, REC_NORMAL = "채용 가속", "TO 재검토/이동배치", "정상 관리"
THRESH_HIRE, THRESH_REVIEW, SMALL_DEPT = -4, 5, 12
INS_HIRE, INS_REVIEW, INS_IMPACT = "채용 가속 필요", "TO 재검토 필요", "퇴사 영향 점검"
GATE = "approval-gate: 권고(채용 가속·TO 재검토/이동배치·퇴사 영향 점검)와 즉시 액션은 제안이며 채용/TO 결정은 사람이 승인한다"

BASE_ASSUMPTIONS = [
    "입사 예정자는 예정일에 전원 입사",
    "퇴사 예정자는 예정일에 전원 퇴사(예정일이 지난 stale 건 포함)",
    "TO 비교는 재직 인원 기준(휴직 제외)",
    "마스터에 없는 사번의 퇴사 예정은 제외",
    "휴직자의 퇴사 예정은 재직 기준 예측에서 제외(급여 마감 총원에는 별도 반영)",
    "다음 달 TO는 기준월 TO를 그대로 적용(다음 달 TO 계획 미수령)",
]

# §2-7 정본 (--self-check 전용, as-of 2026-09-23 에서만 적용). 산출물에는 넣지 않는다.
EXPECTED_DEPT = OrderedDict([  # deptCode: (TO, HC, in, out, ME, gapAsOf, gapME, recommendation)
    ("D01", (10, 10, 0, 0, 10, 0, 0, REC_NORMAL)), ("D02", (54, 51, 3, 1, 53, -3, -1, REC_NORMAL)),
    ("D03", (112, 104, 5, 4, 105, -8, -7, REC_HIRE)), ("D04", (26, 25, 1, 1, 25, -1, -1, REC_NORMAL)),
    ("D05", (34, 40, 2, 1, 41, 6, 7, REC_REVIEW)), ("D06", (62, 58, 3, 3, 58, -4, -4, REC_HIRE)),
    ("D07", (32, 30, 1, 1, 30, -2, -2, REC_NORMAL)), ("D08", (42, 40, 2, 1, 41, -2, -1, REC_NORMAL)),
    ("D09", (18, 18, 1, 0, 19, 0, 1, REC_NORMAL)), ("D10", (20, 19, 1, 1, 19, -1, -1, REC_NORMAL)),
    ("D11", (12, 11, 0, 1, 10, -1, -2, REC_NORMAL)),
])
DEPT_FIELDS = ("toHeadcount", "activeHeadcount", "plannedIn", "plannedOut", "forecastMonthEnd",
               "toGapAsOf", "toGapMonthEnd", "recommendation")
EXPECTED_GROUP = OrderedDict([  # orgGroupCode: (TO, HC, ME) — 조직표 합(브리프 §7의 215/119/62 아님)
    ("G0", (10, 10, 10)), ("G1", (226, 220, 224)), ("G2", (136, 128, 129)), ("G3", (50, 48, 48)),
])
GROUP_FIELDS = ("toHeadcount", "activeHeadcount", "forecastMonthEnd")
EXPECTED_TOTALS = OrderedDict([("toHeadcount", 422), ("activeHeadcount", 406), ("toGapAsOf", -16), ("plannedIn", 19),
                               ("plannedOut", 14), ("forecastMonthEnd", 411), ("toGapMonthEnd", -11), ("toFillRate", 0.9739)])
EXPECTED_NEXT = OrderedDict([("plannedIn", 8), ("plannedOut", 4), ("forecastNextMonthEnd", 415), ("toGapNextMonthEnd", -7)])
EXPECTED_INSIGHTS = OrderedDict([(INS_HIRE, ["D03", "D06"]), (INS_REVIEW, ["D05"]), (INS_IMPACT, ["D11"])])
MINUS = "−"


# ---------------------------------------------------------------- 유틸
def read_csv(path):
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8-sig", newline="") as f:
        return [dict((k.strip(), (v or "").strip()) for k, v in row.items() if k) for row in csv.DictReader(f)]


def parse_date(s):
    try:
        return datetime.date.fromisoformat((s or "").strip())
    except ValueError:
        return None


def month_end(d):
    return datetime.date(d.year, d.month, calendar.monthrange(d.year, d.month)[1])


def signed(n):
    if n > 0:
        return "+%d" % n
    if n < 0:
        return MINUS + "%d" % -n
    return "0"


def flags(s):
    return [f for f in (s or "").split(";") if f]


def recommendation(gap):
    if gap <= THRESH_HIRE:
        return REC_HIRE
    if gap >= THRESH_REVIEW:
        return REC_REVIEW
    return REC_NORMAL


def now_iso():
    return datetime.datetime.now().replace(microsecond=0).isoformat()


# ---------------------------------------------------------------- 핸드오프 로그 (Operating Rule 2)
SECTIONS = ("시도한 것", "본 데이터·근거", "실패한 것", "검증된 것", "다음 agent 인계점")


def write_handoff(root, as_of, sections):
    path = os.path.join(root, HANDOFF_REL)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    lines = ["# %s — %s — %s" % (PHASE, AGENT, as_of), ""]
    for title in SECTIONS:
        lines.append("## " + title)
        lines.extend(sections.get(title) or ["- (없음)"])
        lines.append("")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return HANDOFF_REL


def handoff_start(root, as_of, argv_text):
    return write_handoff(root, as_of, {
        "시도한 것": ["- 실행 시작 %s: `python3 %s %s`" % (now_iso(), SCRIPT_REL, argv_text),
                   "- (실행 중 — 정상 종료 시 이 파일이 갱신된다. 이 문구가 남아 있으면 비정상 종료: 04-forecast 재실행)"],
        "본 데이터·근거": ["- 읽을 입력: " + ", ".join("`%s`" % REL[k] for k in ("org", "master", "to", "joiners", "leavers")),
                     "- 선택 입력: `%s`(있으면 riskAdjusted)" % REL["risk"]],
        "실패한 것": ["- (진행 중)"],
        "검증된 것": ["- (진행 중)"],
        "다음 agent 인계점": ["- (진행 중)"],
    })


def handoff_end(root, as_of, argv_text, fc, evidence, warnings, excluded, cons, tc, status, notes):
    t = fc["totals"]
    tried = ["- 실행 종료 %s: `python3 %s %s` → status `%s`" % (now_iso(), SCRIPT_REL, argv_text, status),
             "- 재직 기준(휴직 제외)으로 조직 11 × (TO/HC/in/out/ME/gapAsOf/gapME/권고) 계산, 조직 그룹·전체 합산, 다음 달 전망, "
             "리스크 반영 시나리오(%s), 인사이트 %d건·즉시 액션 %d건, 시나리오 기본값 산출" % (
                 "적용" if fc["provenance"]["attritionRiskUsed"] else "미적용", len(fc["insights"]), len(fc["immediateActions"])),
             "- 산출물 `%s` 작성(§4-2 shape)" % REL["out"]]
    if evidence.get("narrative"):
        tried.append("- `--narrative` 병합: assumptions %d건 추가" % evidence["narrative"])
    seen = ["- 계약: DATA_CONTRACT v2 §4-2(shape·권고 규칙·인사이트) · §4-5(plannedOut 판정: unknown-emp 제외·재직 사번만·stale 포함) · §2-7(정본 대조) · §2-8(stale/unknown-emp 보정 규칙)"]
    for k in ("org", "master", "to", "joiners", "leavers"):
        seen.append("- `%s`: %s" % (REL[k], evidence.get(k, "없음")))
    seen.append("- `%s`: %s" % (REL["risk"], evidence.get("risk", "없음")))
    failed = []
    if not cons["passed"]:
        failed.append("- 내부 대사 실패: " + "; ".join(cons["failures"]))
    if tc["applicable"] and not tc["passed"]:
        failed.append("- §2-7 정본 불일치 %d건(상류 확인 대상): " % len(tc["mismatches"]) + "; ".join(
            "%s/%s %s expected %s actual %s" % (m["scope"], m["code"], m["field"], m.get("expected"), m.get("actual")) for m in tc["mismatches"][:20]))
    for w in warnings:
        failed.append("- 경고: " + w)
    for k, label in (("notInMaster", "마스터에 없는 사번(unknown-emp) 제외"), ("notActive", "마스터 비재직(휴직) 퇴사 예정 제외"), ("badDate", "예정일 파싱 실패 제외")):
        if excluded.get(k):
            failed.append("- %s: %s" % (label, ", ".join(excluded[k])))
    if not failed:
        failed.append("- 없음")
    verified = ["- 내부 대사 %s: Σ byDepartment = Σ byOrgGroup = totals(5개 필드), 조직별 산식, 권고 규칙 재적용, 목록 건수" % ("통과" if cons["passed"] else "실패"),
                "- §2-7 정본 대조(--self-check): %s" % ("통과(조직 11행 · 그룹 4 · 전체 · 다음 달 · 인사이트 3종)" if tc["applicable"] and tc["passed"]
                                                       else ("불일치 %d건" % len(tc["mismatches"]) if tc["applicable"] else "미적용(기준일이 2026-09-23이 아니거나 옵션 미지정)")),
                "- 전체: 재직 %d + 입사 예정 %d − 퇴사 예정 %d = 월말 %d, TO %d 대비 %s(기준일 %s), toFillRate %s, 다음 달 말 %d(%s)" % (
                    t["activeHeadcount"], t["plannedIn"], t["plannedOut"], t["forecastMonthEnd"], t["toHeadcount"], signed(t["toGapMonthEnd"]),
                    signed(t["toGapAsOf"]), t["toFillRate"], t["nextMonth"]["forecastNextMonthEnd"], signed(t["nextMonth"]["toGapNextMonthEnd"])),
                "- 권고: " + ", ".join("%s %s(%s)" % (d["department"], signed(d["toGapMonthEnd"]), d["recommendation"]) for d in fc["byDepartment"] if d["recommendation"] != REC_NORMAL) or "- 권고: 전 조직 정상 관리",
                "- stale 퇴사 예정(월말 퇴사로 반영): %s" % (", ".join(excluded.get("stale") or []) or "없음")]
    nxt = ["- payroll-close-analyst: `payrollHeadcount.monthEndActive` = `totals.forecastMonthEnd`(%d) assert. 휴직자 퇴사 예정(%s)은 여기서 제외됐으니 급여 `monthEndTotal`에서 별도 반영" % (
        t["forecastMonthEnd"], ", ".join(excluded.get("notActive") or []) or "없음"),
           "- onboarding-plan-analyst: `plannedJoiners` %d건 = plannedIn %d + nextMonth.plannedIn %d(타임라인 합계 대사)" % (
               len(fc["plannedJoiners"]), t["plannedIn"], t["nextMonth"]["plannedIn"]),
           "- product-builder: Insight 경영진/경영기획/조직장 뷰는 `byDepartment`·`byOrgGroup`·`totals`·`insights`·`scenario`(플래너 기본값)를 그대로 읽는다. 개인 식별 없음(사번·joinerId만)",
           "- monthly-report-mailer: 본문 요약 = totals(406/411/%s) + insights(채용 가속·TO 재검토) + immediateActions %d건" % (signed(t["toGapMonthEnd"]), len(fc["immediateActions"])),
           "- people-data-auditor: stdout `targetCheck`가 §2-7 사전 검사. 불일치는 클린저(activeHeadcount)·입퇴사 예정 파일(plannedIn/Out)·TO 정규화(toHeadcount)로 돌려보낸다",
           "- " + GATE]
    if not fc["provenance"]["attritionRiskUsed"]:
        nxt.append("- attrition-risk-scorer 완료 후 04-forecast 재실행 → `riskAdjusted`만 채워진다(기본 예측 불변)")
    nxt.extend("- " + n for n in notes)
    return write_handoff(root, as_of, {"시도한 것": tried, "본 데이터·근거": seen, "실패한 것": failed, "검증된 것": verified, "다음 agent 인계점": nxt})


# ---------------------------------------------------------------- 계산
def load_narrative(path, warnings):
    with open(path, encoding="utf-8") as f:
        n = json.load(f)
    if not isinstance(n, dict):
        raise ValueError("narrative 는 객체여야 함")
    for k in n:
        if k not in ("assumptions", "handoffNotes"):
            warnings.append("narrative 키 %s 무시(허용: assumptions, handoffNotes)" % k)
    clean = lambda xs: [s.strip() for s in (xs or []) if isinstance(s, str) and s.strip()]  # noqa: E731
    return clean(n.get("assumptions")), clean(n.get("handoffNotes"))


def select_to(to_rows, as_of_month, warnings):
    grouped = OrderedDict()
    for r in to_rows:
        grouped.setdefault(r.get("deptCode"), []).append(r)
    chosen = {}
    for code, rows in grouped.items():
        if len(rows) > 1:
            warnings.append("TO 계획 deptCode %s 행 %d개 — 기준월 우선 선택" % (code, len(rows)))
        exact = [r for r in rows if (r.get("effectiveMonth") or "") == as_of_month]
        past = sorted([r for r in rows if (r.get("effectiveMonth") or "") <= as_of_month], key=lambda r: r.get("effectiveMonth") or "")
        pick = exact[-1] if exact else (past[-1] if past else rows[-1])
        chosen[code] = int(float(pick.get("toHeadcount") or 0))
    return chosen


def compute(root, as_of, narrative_path=None):
    warnings, evidence = [], {}
    for key in REQUIRED:
        if not os.path.exists(os.path.join(root, REL[key])):
            raise FileNotFoundError(REL[key] + " 없음 — people-data-cleanser 선행 필요")
    m_end = month_end(as_of)
    nm_end = month_end(m_end + datetime.timedelta(days=1))

    master = read_csv(os.path.join(root, REL["master"]))
    org_rows = read_csv(os.path.join(root, REL["org"]))
    to_rows = read_csv(os.path.join(root, REL["to"]))
    joiner_rows = read_csv(os.path.join(root, REL["joiners"]))
    leaver_rows = read_csv(os.path.join(root, REL["leavers"]))

    depts = OrderedDict()
    for r in org_rows or []:
        depts[r["deptCode"]] = OrderedDict([("deptCode", r["deptCode"]), ("department", r["department"]),
                                            ("orgGroupCode", r["orgGroupCode"]), ("orgGroup", r["orgGroup"])])
    if not org_rows:
        warnings.append(REL["org"] + " 없음 — 마스터·TO·입사 예정의 조직 코드로 골격 구성")
    for r in list(master) + list(to_rows) + list(joiner_rows):
        code = r.get("deptCode")
        if code and code not in depts:
            if org_rows:
                warnings.append("조직 체계에 없는 deptCode %s — 클린저(조직 정규화) 확인" % code)
            depts[code] = OrderedDict([("deptCode", code), ("department", r.get("department") or code),
                                       ("orgGroupCode", r.get("orgGroupCode") or "?"), ("orgGroup", r.get("orgGroup") or "?")])

    active = dict((c, 0) for c in depts)
    on_leave, other_status, master_by_id = 0, 0, {}
    for r in master:
        master_by_id[r["empId"]] = r
        st = r.get("status")
        if st == STATUS_ACTIVE:
            active[r["deptCode"]] += 1
        elif st == "휴직":
            on_leave += 1
        else:
            other_status += 1
    if other_status:
        warnings.append("마스터 status 가 재직/휴직이 아닌 행 %d — 클린저(표기 정규화) 확인" % other_status)
    if len(master_by_id) != len(master):
        warnings.append("마스터 중복 사번 %d — 클린저(중복 해소) 확인" % (len(master) - len(master_by_id)))
    evidence["master"] = "%d행(재직 %d · 휴직 %d)" % (len(master), sum(active.values()), on_leave)
    evidence["org"] = "%d조직" % len(org_rows) if org_rows else "없음"

    to = dict((c, 0) for c in depts)
    to.update(select_to(to_rows, as_of.strftime("%Y-%m"), warnings))
    evidence["to"] = "%d행(합 %d)" % (len(to_rows), sum(to.values()))

    joiners_in, joiners_next, beyond_j, bad_j = [], [], 0, 0
    for j in joiner_rows:
        d = parse_date(j.get("plannedHireDate"))
        if d is None:
            bad_j += 1
            warnings.append("입사 예정일 파싱 실패 joinerId=%s — 제외" % j.get("joinerId"))
        elif d <= m_end:
            joiners_in.append(j)
        elif d <= nm_end:
            joiners_next.append(j)
        else:
            beyond_j += 1
    if beyond_j:
        warnings.append("다음 달 말 이후 입사 예정 %d건은 반영하지 않음" % beyond_j)
    evidence["joiners"] = "%d행(월말까지 %d · 다음 달 %d · 범위 밖 %d · 파싱 실패 %d)" % (len(joiner_rows), len(joiners_in), len(joiners_next), beyond_j, bad_j)

    leavers_in, leavers_next = [], []
    excluded = OrderedDict([("notInMaster", []), ("notActive", []), ("badDate", []), ("stale", []), ("beyondHorizon", 0)])
    for lv in leaver_rows:
        fl = flags(lv.get("unresolvedFlags"))
        emp = master_by_id.get(lv.get("empId"))
        if FLAG_UNKNOWN_EMP in fl or emp is None:
            excluded["notInMaster"].append(lv.get("empId") or "?")
            continue
        d = parse_date(lv.get("plannedTerminationDate"))
        if d is None:
            excluded["badDate"].append(lv["empId"])
            warnings.append("퇴사 예정일 파싱 실패 empId=%s — 제외" % lv["empId"])
            continue
        if emp.get("deptCode") != lv.get("deptCode"):
            warnings.append("퇴사 예정자 %s 의 조직(%s)이 마스터(%s)와 다름 — 마스터 기준" % (lv["empId"], lv.get("deptCode"), emp.get("deptCode")))
        if emp.get("status") != STATUS_ACTIVE:
            warnings.append("퇴사 예정자 %s 는 마스터 상태 %s — 재직 기준 예측에서 제외(§4-5)" % (lv["empId"], emp.get("status")))
            excluded["notActive"].append(lv["empId"])
            continue
        lv = dict(lv, deptCode=emp["deptCode"], _date=d)
        if d < as_of or FLAG_STALE in fl:
            excluded["stale"].append(lv["empId"])
        if d <= m_end:
            leavers_in.append(lv)
        elif d <= nm_end:
            leavers_next.append(lv)
        else:
            excluded["beyondHorizon"] += 1
    evidence["leavers"] = "%d행(월말까지 %d · 다음 달 %d · unknown-emp %d · 비재직 %d · stale %d · 범위 밖 %d)" % (
        len(leaver_rows), len(leavers_in), len(leavers_next), len(excluded["notInMaster"]), len(excluded["notActive"]),
        len(excluded["stale"]), excluded["beyondHorizon"])

    def count(rows, code):
        return sum(1 for r in rows if r.get("deptCode") == code)

    risk_by_dept, risk_used = None, False
    risk_path = os.path.join(root, REL["risk"])
    if os.path.exists(risk_path):
        try:
            with open(risk_path, encoding="utf-8") as f:
                risk = json.load(f)
            risk_by_dept = dict((d["deptCode"], float(d.get("expectedAttritionNext3Months") or 0)) for d in risk.get("byDepartment", []))
            risk_used = True
            evidence["risk"] = "byDepartment %d조직, 3개월 기대 이탈 합 %.2f" % (len(risk_by_dept), sum(risk_by_dept.values()))
        except (ValueError, KeyError, TypeError, AttributeError) as e:
            warnings.append("attrition-risk.json 파싱 실패(%s) — riskAdjusted null" % e)
            evidence["risk"] = "파싱 실패"
    else:
        evidence["risk"] = "없음(선택 입력)"

    assumptions = list(BASE_ASSUMPTIONS)
    if risk_used:
        assumptions.append("리스크 반영 시나리오는 attrition-risk.json 의 조직별 3개월 기대 이탈의 1/3을 다음 달 말에 반영(기본 예측을 대체하지 않는 시나리오, 퇴사 예정자와 일부 중복 가능)")
    else:
        assumptions.append("attrition-risk.json 부재 — riskAdjusted 는 null(리스크 산출 후 재실행 시 채워짐)")

    by_dept = []
    for code, info in depts.items():
        a, t, pin, pout = active[code], to[code], count(joiners_in, code), count(leavers_in, code)
        me = a + pin - pout
        nin, nout = count(joiners_next, code), count(leavers_next, code)
        nme = me + nin - nout
        ra = None
        if risk_by_dept is not None:
            ea = round(risk_by_dept.get(code, 0.0) / 3.0, 2)
            ra = OrderedDict([("expectedAttrition", ea), ("forecastNextMonthEndRiskAdjusted", round(nme - ea, 2))])
        row = OrderedDict(info)
        row.update([("toHeadcount", t), ("activeHeadcount", a), ("plannedIn", pin), ("plannedOut", pout),
                    ("forecastMonthEnd", me), ("toGapAsOf", a - t), ("toGapMonthEnd", me - t),
                    ("recommendation", recommendation(me - t)),
                    ("nextMonth", OrderedDict([("plannedIn", nin), ("plannedOut", nout),
                                               ("forecastNextMonthEnd", nme), ("toGapNextMonthEnd", nme - t)])),
                    ("riskAdjusted", ra)])
        by_dept.append(row)

    def roll(rows, head):
        agg = OrderedDict((k, 0) for k in ("toHeadcount", "activeHeadcount", "plannedIn", "plannedOut", "forecastMonthEnd"))
        nxt = OrderedDict((k, 0) for k in ("plannedIn", "plannedOut", "forecastNextMonthEnd"))
        for d in rows:
            for k in agg:
                agg[k] += d[k]
            for k in nxt:
                nxt[k] += d["nextMonth"][k]
        agg["toGapAsOf"] = agg["activeHeadcount"] - agg["toHeadcount"]
        agg["toGapMonthEnd"] = agg["forecastMonthEnd"] - agg["toHeadcount"]
        nxt["toGapNextMonthEnd"] = nxt["forecastNextMonthEnd"] - agg["toHeadcount"]
        out = OrderedDict(head)
        out.update(agg)
        out["nextMonth"] = nxt
        return out

    by_group = []
    for gcode in OrderedDict((d["orgGroupCode"], 1) for d in by_dept):
        rows = [d for d in by_dept if d["orgGroupCode"] == gcode]
        by_group.append(roll(rows, [("orgGroupCode", gcode), ("orgGroup", rows[0]["orgGroup"])]))
    totals = roll(by_dept, [])
    nxt = totals.pop("nextMonth")
    totals["toFillRate"] = round(totals["forecastMonthEnd"] / float(totals["toHeadcount"]), 4) if totals["toHeadcount"] else 0.0
    totals["nextMonth"] = nxt

    # 인사이트·즉시 액션 (결정적 — §4-2). 권고는 제안: 결정은 승인 gate.
    name = dict((d["deptCode"], d["department"]) for d in by_dept)
    hire = [d for d in by_dept if d["recommendation"] == REC_HIRE]
    review = [d for d in by_dept if d["recommendation"] == REC_REVIEW]
    impact = [d for d in by_dept if d["activeHeadcount"] <= SMALL_DEPT and d["plannedOut"] >= 1]
    insights, actions = [], []

    def insight(kind, rows, detail, action):
        insights.append(OrderedDict([("type", kind), ("scope", "department"), ("codes", [d["deptCode"] for d in rows]),
                                     ("label", ", ".join(name[d["deptCode"]] for d in rows)), ("detail", detail), ("action", action)]))

    if hire:
        insight(INS_HIRE, hire, ", ".join("%s %s" % (name[d["deptCode"]], signed(d["toGapMonthEnd"])) for d in hire), "채용 pipeline 점검")
        actions.append("/".join(name[d["deptCode"]] for d in hire) + " 채용 pipeline 점검")
    if review:
        insight(INS_REVIEW, review, ", ".join("%s 초과 예상" % signed(d["toGapMonthEnd"]) for d in review), "TO 재배분 또는 내부 이동배치")
        actions.append("/".join(name[d["deptCode"]] for d in review) + " TO 재검토")
    if impact:
        insight(INS_IMPACT, impact, "; ".join("재직 %d명 조직에서 %d명 퇴사 예정, 월말 %s" % (d["activeHeadcount"], d["plannedOut"], signed(d["toGapMonthEnd"])) for d in impact),
                "업무 공백·인수인계 점검")
        actions.append("/".join(name[d["deptCode"]] for d in impact) + " 퇴사 영향 점검")
    if not insights:
        assumptions.append("전 조직 TO 임계값 이내 — 권고 없음")

    notes = []
    if narrative_path:
        extra, notes = load_narrative(narrative_path, warnings)
        added = [s for s in extra if s not in assumptions]
        assumptions.extend(added)
        evidence["narrative"] = len(added)

    def joiner_row(j):
        return OrderedDict([("joinerId", j.get("joinerId")), ("deptCode", j.get("deptCode")),
                            ("plannedHireDate", j.get("plannedHireDate")), ("employmentType", j.get("employmentType"))])

    def leaver_row(lv):
        return OrderedDict([("empId", lv["empId"]), ("deptCode", lv["deptCode"]), ("plannedTerminationDate", lv["_date"].isoformat()),
                            ("separationType", lv.get("separationType")), ("separationReason", lv.get("separationReason"))])

    forecast = OrderedDict([
        ("asOfDate", as_of.isoformat()), ("monthEnd", m_end.isoformat()), ("nextMonthEnd", nm_end.isoformat()),
        ("assumptions", assumptions), ("byDepartment", by_dept), ("byOrgGroup", by_group), ("totals", totals),
        ("plannedJoiners", [joiner_row(j) for j in sorted(joiners_in + joiners_next, key=lambda x: (x.get("plannedHireDate") or "", x.get("joinerId") or ""))]),
        ("plannedLeavers", [leaver_row(lv) for lv in sorted(leavers_in + leavers_next, key=lambda x: (x["_date"], x["empId"]))]),
        ("insights", insights), ("immediateActions", actions),
        ("scenario", OrderedDict([("parameters", OrderedDict([("hiringAchievementRate", 1.0), ("extraAttrition", 0)])),
                                  ("formula", "forecast = active + round(plannedIn × rate) − plannedOut − extraAttrition")])),
        ("provenance", OrderedDict([("client", "㈜온다테크"),
                                    ("sources", [REL[k] for k in ("org", "master", "to", "joiners", "leavers")] + ([REL["risk"]] if risk_used else [])),
                                    ("script", SCRIPT_REL), ("generatedAt", now_iso()), ("attritionRiskUsed", risk_used),
                                    ("headcountBasis", "active"), ("contractVersion", "v2"), ("gate", GATE)])),
    ])
    return forecast, warnings, excluded, evidence, notes


# ---------------------------------------------------------------- 대사
def consistency(fc):
    failures = []
    t = fc["totals"]
    for k in ("toHeadcount", "activeHeadcount", "plannedIn", "plannedOut", "forecastMonthEnd"):
        for arr in ("byDepartment", "byOrgGroup"):
            s = sum(d[k] for d in fc[arr])
            if s != t[k]:
                failures.append("Σ %s.%s=%d ≠ totals %d" % (arr, k, s, t[k]))
    for d in fc["byDepartment"]:
        if d["forecastMonthEnd"] != d["activeHeadcount"] + d["plannedIn"] - d["plannedOut"]:
            failures.append("%s forecastMonthEnd 산식 불일치" % d["deptCode"])
        if d["toGapAsOf"] != d["activeHeadcount"] - d["toHeadcount"] or d["toGapMonthEnd"] != d["forecastMonthEnd"] - d["toHeadcount"]:
            failures.append("%s toGap 산식 불일치" % d["deptCode"])
        if d["nextMonth"]["forecastNextMonthEnd"] != d["forecastMonthEnd"] + d["nextMonth"]["plannedIn"] - d["nextMonth"]["plannedOut"]:
            failures.append("%s nextMonth 산식 불일치" % d["deptCode"])
        if d["recommendation"] != recommendation(d["toGapMonthEnd"]):
            failures.append("%s recommendation 규칙 불일치" % d["deptCode"])
    if t["forecastMonthEnd"] != t["activeHeadcount"] + t["plannedIn"] - t["plannedOut"]:
        failures.append("totals forecastMonthEnd 산식 불일치")
    if t["toHeadcount"] and abs(t["toFillRate"] - round(t["forecastMonthEnd"] / float(t["toHeadcount"]), 4)) > 1e-9:
        failures.append("totals toFillRate 불일치")
    if len(fc["plannedJoiners"]) != t["plannedIn"] + t["nextMonth"]["plannedIn"]:
        failures.append("plannedJoiners 건수 ≠ plannedIn + nextMonth.plannedIn")
    if len(fc["plannedLeavers"]) != t["plannedOut"] + t["nextMonth"]["plannedOut"]:
        failures.append("plannedLeavers 건수 ≠ plannedOut + nextMonth.plannedOut")
    for i in fc["insights"]:
        if not i.get("codes") or not i.get("detail") or not i.get("action"):
            failures.append("인사이트 %s 필수 필드 누락" % i.get("type"))
    return OrderedDict([("passed", not failures), ("failures", failures)])


def target_check(fc):
    if fc["asOfDate"] != DEFAULT_AS_OF:
        return OrderedDict([("applicable", False), ("passed", True), ("mismatches", [])])
    mm = []

    def cmp(scope, code, field, expected, actual):
        if expected != actual:
            mm.append(OrderedDict([("scope", scope), ("code", code), ("field", field), ("expected", expected), ("actual", actual)]))

    by_code = dict((d["deptCode"], d) for d in fc["byDepartment"])
    for code, exp in EXPECTED_DEPT.items():
        d = by_code.get(code)
        if d is None:
            mm.append(OrderedDict([("scope", "department"), ("code", code), ("field", "missing"), ("expected", "row"), ("actual", None)]))
            continue
        for f, e in zip(DEPT_FIELDS, exp):
            cmp("department", code, f, e, d[f])
    for code in by_code:
        if code not in EXPECTED_DEPT:
            mm.append(OrderedDict([("scope", "department"), ("code", code), ("field", "unexpected"), ("expected", None), ("actual", "row")]))
    by_group = dict((g["orgGroupCode"], g) for g in fc["byOrgGroup"])
    for code, exp in EXPECTED_GROUP.items():
        g = by_group.get(code)
        if g is None:
            mm.append(OrderedDict([("scope", "orgGroup"), ("code", code), ("field", "missing"), ("expected", "row"), ("actual", None)]))
            continue
        for f, e in zip(GROUP_FIELDS, exp):
            cmp("orgGroup", code, f, e, g[f])
    for f, e in EXPECTED_TOTALS.items():
        cmp("totals", "*", f, e, fc["totals"][f])
    for f, e in EXPECTED_NEXT.items():
        cmp("totals.nextMonth", "*", f, e, fc["totals"]["nextMonth"][f])
    got = dict((i["type"], i["codes"]) for i in fc["insights"])
    for kind, codes in EXPECTED_INSIGHTS.items():
        cmp("insights", kind, "codes", codes, got.get(kind))
    return OrderedDict([("applicable", True), ("passed", not mm), ("mismatches", mm)])


# ---------------------------------------------------------------- 진입점
def summary(fc, status, handoff, excluded, cons, tc, warnings):
    risk_totals = None
    if fc["provenance"].get("attritionRiskUsed"):
        ea = round(sum((d.get("riskAdjusted") or {}).get("expectedAttrition", 0.0) for d in fc["byDepartment"]), 2)
        risk_totals = OrderedDict([("expectedAttritionNextMonth", ea),
                                   ("forecastNextMonthEndRiskAdjusted", round(fc["totals"]["nextMonth"]["forecastNextMonthEnd"] - ea, 2))])
    return OrderedDict([
        ("status", status), ("asOfDate", fc["asOfDate"]), ("monthEnd", fc["monthEnd"]), ("nextMonthEnd", fc["nextMonthEnd"]),
        ("output", REL["out"]), ("handoffLog", handoff), ("totals", fc["totals"]),
        ("byOrgGroup", [OrderedDict([("orgGroupCode", g["orgGroupCode"]), ("orgGroup", g["orgGroup"]), ("forecastMonthEnd", g["forecastMonthEnd"]),
                                     ("toGapMonthEnd", g["toGapMonthEnd"]), ("toGapNextMonthEnd", g["nextMonth"]["toGapNextMonthEnd"])]) for g in fc["byOrgGroup"]]),
        ("recommendations", OrderedDict((d["deptCode"], d["recommendation"]) for d in fc["byDepartment"])),
        ("insights", [OrderedDict([("type", i["type"]), ("codes", i["codes"]), ("label", i["label"]), ("detail", i["detail"]), ("action", i["action"])]) for i in fc["insights"]]),
        ("immediateActions", fc["immediateActions"]), ("assumptions", fc["assumptions"]),
        ("riskAdjustedApplied", bool(fc["provenance"].get("attritionRiskUsed"))), ("riskScenarioTotals", risk_totals),
        ("excluded", excluded),
        ("counts", OrderedDict([("byDepartment", len(fc["byDepartment"])), ("plannedJoiners", len(fc["plannedJoiners"])),
                                ("plannedLeavers", len(fc["plannedLeavers"])), ("insights", len(fc["insights"]))])),
        ("consistency", cons), ("targetCheck", tc), ("warnings", warnings), ("gate", GATE),
    ])


def main(argv=None):
    p = argparse.ArgumentParser(description="Zero Company HR 월말 인원 예측 (DATA_CONTRACT v2 §4-2)")
    p.add_argument("--root", default=DEFAULT_ROOT)
    p.add_argument("--as-of", dest="as_of", default=DEFAULT_AS_OF)
    p.add_argument("--self-check", action="store_true", help="§2-7 정본과 대조(불일치 시 exit 2)")
    p.add_argument("--check-only", action="store_true", help="기존 산출물만 검사, 쓰지 않음(핸드오프 로그도 쓰지 않음)")
    p.add_argument("--narrative", default=None, help="에이전트 판단 보완 JSON {assumptions[], handoffNotes[]}")
    a = p.parse_args(argv)
    argv_text = " ".join(sys.argv[1:] if argv is None else argv)
    out_path = os.path.join(a.root, REL["out"])
    try:
        as_of = datetime.date.fromisoformat(a.as_of)
    except ValueError:
        print(json.dumps({"status": "error", "errorType": "ValueError", "error": "--as-of 는 YYYY-MM-DD"}, ensure_ascii=False))
        return 1
    handoff = None
    try:
        if a.check_only:
            if not os.path.exists(out_path):
                print(json.dumps({"status": "blocked", "errorType": "FileNotFoundError", "error": REL["out"] + " 없음", "asOfDate": a.as_of}, ensure_ascii=False))
                return 3
            with open(out_path, encoding="utf-8") as f:
                fc = json.load(f)
            warnings, excluded = ["check-only: 기존 산출물 검사(재계산·핸드오프 로그 없음)"], {}
            cons = consistency(fc)
            tc = target_check(fc) if a.self_check else OrderedDict([("applicable", False), ("passed", True), ("mismatches", [])])
        else:
            handoff = handoff_start(a.root, a.as_of, argv_text)
            fc, warnings, excluded, evidence, notes = compute(a.root, as_of, a.narrative)
            os.makedirs(os.path.dirname(out_path), exist_ok=True)
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(fc, f, ensure_ascii=False, indent=2)
            cons = consistency(fc)
            tc = target_check(fc) if a.self_check else OrderedDict([("applicable", False), ("passed", True), ("mismatches", [])])
        status = "ok" if cons["passed"] and tc["passed"] else ("error" if not cons["passed"] else "partial")
        if handoff:
            handoff_end(a.root, a.as_of, argv_text, fc, evidence, warnings, excluded, cons, tc, status, notes)
        print(json.dumps(summary(fc, status, handoff, excluded, cons, tc, warnings), ensure_ascii=False))
        return {"ok": 0, "partial": 2}.get(status, 1)
    except FileNotFoundError as e:
        if handoff:
            write_handoff(a.root, a.as_of, {"시도한 것": ["- 실행 %s: `%s` → blocked" % (now_iso(), argv_text)],
                                            "본 데이터·근거": ["- 필수 입력 확인 실패"], "실패한 것": ["- " + str(e)],
                                            "검증된 것": ["- 없음"], "다음 agent 인계점": ["- people-data-cleanser 산출물(data/clean/ 4종) 생성 후 04-forecast 재실행"]})
        print(json.dumps({"status": "blocked", "errorType": "FileNotFoundError", "error": str(e), "asOfDate": a.as_of, "handoffLog": handoff}, ensure_ascii=False))
        return 3
    except Exception as e:  # noqa: BLE001
        if handoff:
            write_handoff(a.root, a.as_of, {"시도한 것": ["- 실행 %s: `%s` → error" % (now_iso(), argv_text)],
                                            "본 데이터·근거": ["- (예외 발생 지점까지)"], "실패한 것": ["- %s: %s" % (type(e).__name__, e)],
                                            "검증된 것": ["- 없음"], "다음 agent 인계점": ["- 입력 파일 헤더·값 도메인(§3) 확인 후 04-forecast 재실행"]})
        print(json.dumps({"status": "error", "errorType": type(e).__name__, "error": str(e), "asOfDate": a.as_of, "handoffLog": handoff}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    sys.exit(main())
