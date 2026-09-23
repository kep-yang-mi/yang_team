#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""render_report.py — 월초 리포트 렌더러. DATA_CONTRACT v2 §6 · 브리프 §10.

공통 데이터 계층의 수치를 **그대로 읽어**(재계산 금지) 네 파일을 만든다:
  reports/monthly-report-{발송월}.md / .html    발송월 = 기준일 다음 달 (2026-09-23 → 2026-10). HTML은 인라인 스타일
  reports/org-forecast-{기준월}.csv              조직별 예측 CSV(§6 열 10개, 11행)
  reports/monthly-report-dispatch.json           발송 명세: 수신자 4그룹(@ondatech.example), 0 9 1 * *, ready-to-send, approval-gate
제목: [Zero Company] {기준월} HR Headcount Forecast. 본문 요약 5불릿은 브리프 §10 문장 그대로.

입력: data/stats/headcount-stats.json(필수) · month-end-forecast.json(필수) · attrition-risk.json · payroll-close.json(집계만) ·
      automation-effect.json · data/clean/cleansing-summary.json (선택). PII 스캔용 정제 성명 목록(본문에 쓰지 않음).
정책: pii-minimization(성명·생년월일·개인 점수 없음) · reconciliation(stats↔forecast↔payroll 일치 아니면 쓰지 않음) ·
      approval-gate(발송 없음, ready-to-send까지) · handoff-log(실행 시작·종료 시 _workspace/handoff/10-report.md).
사용법: python3 render_report.py --root R --as-of 2026-09-23
종료 코드: 0 ok · 1 error · 2 대사 실패 · 3 필수 입력 없음 · 4 PII 검출.  stdout 마지막 줄 = 요약 JSON 1행(반환 데이터).
"""
import argparse
import calendar
import csv
import datetime
import html
import json
import os
import sys
from collections import OrderedDict

DEFAULT_ROOT = "/Users/yang/development/zero-hr"
DEFAULT_AS_OF = "2026-09-23"
AGENT = "monthly-report-mailer"
STAGE = "10-report"
DOMAIN = "ondatech.example"
RECIPIENTS = OrderedDict([  # 가상 주소 — 도메인은 계약 §6 고정
    ("executive", ["ceo@", "cfo@", "coo@"]),
    ("hr", ["hr-head@", "people-ops@"]),
    ("planning", ["planning-lead@", "corp-planning@"]),
    ("orgLead", ["lead-ceo-office@", "lead-product@", "lead-engineering@", "lead-design@", "lead-data-ai@", "lead-sales@",
                 "lead-marketing@", "lead-cs@", "lead-people@", "lead-finance@", "lead-legal@"]),
])
REL = OrderedDict([
    ("stats", "data/stats/headcount-stats.json"), ("forecast", "data/stats/month-end-forecast.json"),
    ("risk", "data/stats/attrition-risk.json"), ("payroll", "data/stats/payroll-close.json"),
    ("auto", "data/stats/automation-effect.json"), ("cleansing", "data/clean/cleansing-summary.json"),
    ("master", "data/clean/headcount-master.clean.csv"), ("joiners", "data/clean/planned-joiners.clean.csv"),
])
HANDOFF_REL = "_workspace/handoff/%s.md" % STAGE
UNRECONCILED_REL = "_workspace/monthly-report.unreconciled.json"
MINUS = "−"  # 브리프 표기(−)
CSV_COLS = ["deptCode", "department", "orgGroup", "toHeadcount", "activeHeadcount", "plannedIn", "plannedOut",
            "forecastMonthEnd", "toGapMonthEnd", "recommendation"]
BRIEF_ORG_GROUP_ACTIVE = OrderedDict([("Executive", 10), ("Build", 215), ("Go-To-Market", 119), ("Operations", 62)])  # 브리프 §7
SECTIONS = ["시도한 것", "본 데이터·근거", "실패한 것", "검증된 것", "다음 agent 인계점"]


# ---------------------------------------------------------------- 유틸
def load_json(root, key):
    path = os.path.join(root, REL[key])
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def signed(n):
    n = int(n)
    return ("+%d" % n) if n > 0 else ((MINUS + "%d" % -n) if n < 0 else "0")


def month_end(d):
    return datetime.date(d.year, d.month, calendar.monthrange(d.year, d.month)[1])


def next_month(d):
    return month_end(d) + datetime.timedelta(days=1)


def join_kv(dct):
    return ", ".join("%s %s" % (k, v) for k, v in (dct or {}).items()) or "없음"


# ---------------------------------------------------------------- 핸드오프 로그 (handoff-log-policy: 5절 고정, 개인 행 인용 금지)
class Handoff:
    def __init__(self, root, as_of, argv_text):
        self.path = os.path.join(root, HANDOFF_REL)
        self.as_of = as_of
        self.started = datetime.datetime.now().replace(microsecond=0).isoformat()
        self.s = OrderedDict((k, []) for k in SECTIONS)
        self.s["시도한 것"].append("실행: `%s` (시작 %s)" % (argv_text, self.started))

    def add(self, section, text):
        self.s[section].append(text)

    def write(self, phase):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        lines = ["# %s — %s · asOfDate %s · %s %s" % (STAGE, AGENT, self.as_of, phase,
                                                        datetime.datetime.now().replace(microsecond=0).isoformat()), ""]
        for k in SECTIONS:
            lines.append("## " + k)
            lines.extend("- " + t for t in (self.s[k] or ["없음"]))
            lines.append("")
        with open(self.path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))


# ---------------------------------------------------------------- 문서 모델(md/html 공통)
class Doc:
    def __init__(self):
        self.blocks = []

    def h(self, level, text):
        self.blocks.append(("h", level, text))

    def p(self, text):
        self.blocks.append(("p", text))

    def ul(self, items):
        self.blocks.append(("ul", list(items)))

    def table(self, headers, rows):
        self.blocks.append(("table", headers, [[str(c) for c in r] for r in rows]))

    def md(self):
        out = []
        for b in self.blocks:
            if b[0] == "h":
                out.append("#" * b[1] + " " + b[2])
            elif b[0] == "p":
                out.append(b[1])
            elif b[0] == "ul":
                out.append("\n".join("- " + i for i in b[1]))
            else:
                out.append("| " + " | ".join(b[1]) + " |")
                out.append("|" + "|".join("---" for _ in b[1]) + "|")
                out.extend("| " + " | ".join(c.replace("|", "\\|") for c in r) + " |" for r in b[2])
            out.append("")
        return "\n".join(out).rstrip() + "\n"

    def html(self, title):
        e = html.escape
        parts = ['<!DOCTYPE html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
                 '<title>%s</title></head>' % e(title),
                 '<body style="font-family:-apple-system,Segoe UI,Helvetica,Arial,sans-serif;max-width:860px;margin:24px auto;'
                 'padding:0 16px;color:#1f2937;background:#ffffff;line-height:1.55">']
        for b in self.blocks:
            if b[0] == "h":
                parts.append('<h%d style="margin:%dpx 0 8px">%s</h%d>' % (b[1], 28 if b[1] <= 2 else 18, e(b[2]), b[1]))
            elif b[0] == "p":
                parts.append('<p style="margin:6px 0">%s</p>' % e(b[1]))
            elif b[0] == "ul":
                parts.append("<ul>" + "".join("<li>%s</li>" % e(i) for i in b[1]) + "</ul>")
            else:
                parts.append('<div style="overflow-x:auto"><table style="border-collapse:collapse;width:100%;font-size:14px;margin:8px 0"><thead><tr>'
                             + "".join('<th style="border:1px solid #d1d5db;background:#f3f4f6;padding:6px 8px;text-align:left">%s</th>' % e(h) for h in b[1])
                             + "</tr></thead><tbody>"
                             + "".join("<tr>" + "".join('<td style="border:1px solid #d1d5db;padding:6px 8px">%s</td>' % e(c) for c in r) + "</tr>" for r in b[2])
                             + "</tbody></table></div>")
        parts.append("</body></html>")
        return "\n".join(parts) + "\n"


# ---------------------------------------------------------------- 대사 · PII
def reconcile(stats, fc, payroll):
    """stats↔forecast↔payroll 같은 지표 같은 값 (reconciliation-policy). 검사 건수와 불일치 목록을 돌려준다."""
    fails, checked = [], 0
    st, ft = stats["totals"], fc["totals"]
    for k in ("activeHeadcount", "toHeadcount", "toGapAsOf", "plannedIn", "plannedOut"):
        checked += 1
        if st.get(k) != ft.get(k):
            fails.append({"field": "totals." + k, "stats": st.get(k), "forecast": ft.get(k)})
    s_dept = dict((d["deptCode"], d) for d in stats["byDepartment"])
    for d in fc["byDepartment"]:
        checked += 1
        s = s_dept.get(d["deptCode"])
        if s is None or s["activeHeadcount"] != d["activeHeadcount"] or s["toHeadcount"] != d["toHeadcount"]:
            fails.append({"field": "byDepartment." + d["deptCode"], "stats": s and [s["activeHeadcount"], s["toHeadcount"]],
                          "forecast": [d["activeHeadcount"], d["toHeadcount"]]})
    if len(fc["byDepartment"]) != len(stats["byDepartment"]):
        fails.append({"field": "byDepartment.rows", "stats": len(stats["byDepartment"]), "forecast": len(fc["byDepartment"])})
    if payroll:
        checked += 1
        pm = (payroll.get("payrollHeadcount") or {}).get("monthEndActive")
        if pm != ft["forecastMonthEnd"]:
            fails.append({"field": "payroll.monthEndActive", "payroll": pm, "forecast": ft["forecastMonthEnd"]})
    return fails, checked


def pii_names(root):
    names = set()
    for key in ("master", "joiners"):
        path = os.path.join(root, REL[key])
        if os.path.exists(path):
            with open(path, encoding="utf-8-sig", newline="") as f:
                for r in csv.DictReader(f):
                    n = (r.get("name") or "").strip()
                    if len(n) >= 3:
                        names.add(n)
    return names


def brief_group_note(stats):
    """브리프 §7 조직 그룹 합과 조직표(stats.byOrgGroup) 재직 합이 다르면 기록 문장을 돌려준다(삭제 금지, 재계산 아님 — 값 비교만)."""
    actual = OrderedDict((g["orgGroup"], g["activeHeadcount"]) for g in stats.get("byOrgGroup", []))
    if not actual or all(actual.get(k) == v for k, v in BRIEF_ORG_GROUP_ACTIVE.items()):
        return None
    return ("브리프 §7 조직 그룹 재직 합(%s)은 조직표 합(%s)과 불일치 — 조직표(headcount-stats.byOrgGroup)를 정본으로 채택하고 브리프 값은 기록만 한다"
            % (" / ".join("%s %d" % kv for kv in BRIEF_ORG_GROUP_ACTIVE.items()), " / ".join("%s %s" % kv for kv in actual.items())))


# ---------------------------------------------------------------- 본문
def build(stats, fc, risk, auto, cleansing, subject, as_of, send_at, csv_rel):
    d = Doc()
    st, ft = stats["totals"], fc["totals"]
    nm = ft.get("nextMonth") or {}
    hire = [x["department"] for x in fc["byDepartment"] if x["recommendation"] == "채용 가속"]
    review = [x["department"] for x in fc["byDepartment"] if x["recommendation"] == "TO 재검토/이동배치"]
    d.h(1, subject)
    d.p("고객사 %s · 기준일 %s · 월말 %s · 발송 예정 %s · 생성: Zero Company HR — Everyday People Agent (agent 자동 생성, 승인 gate 대기)"
        % (stats.get("client", ""), as_of.isoformat(), fc["monthEnd"], send_at))

    d.h(2, "요약")  # 브리프 §10 본문 요약 5불릿 — 문장 그대로
    d.ul(["현재 재직 %d명 / 월말 예측 %d명" % (st["activeHeadcount"], ft["forecastMonthEnd"]),
          "총 TO 대비 월말 gap %s명" % signed(ft["toGapMonthEnd"]),
          "채용 가속 필요: %s" % (", ".join(hire) or "없음"),
          "TO 재검토 필요: %s" % (", ".join(review) or "없음"),
          "첨부: 권한별 대시보드 링크, 조직별 forecast CSV"])
    d.p("즉시 액션 %d건: %s" % (len(fc.get("immediateActions") or []), " · ".join(fc.get("immediateActions") or []) or "없음"))
    d.p("첨부 경로: site/insight/index.html (권한별 대시보드) · %s (조직별 forecast CSV)" % csv_rel)

    d.h(2, "Executive Snapshot")
    rows = [["현재 재직 인원", st["activeHeadcount"]], ["휴직 인원", st["onLeave"]], ["총 TO", ft["toHeadcount"]],
            ["현재 TO 대비", signed(ft["toGapAsOf"])], ["입사 예정", ft["plannedIn"]], ["퇴사 예정", ft["plannedOut"]],
            ["월말 예측 인원", ft["forecastMonthEnd"]], ["월말 TO 대비", signed(ft["toGapMonthEnd"])]]
    if ft.get("toFillRate") is not None:
        rows.append(["TO 충족률(월말)", "%.1f%%" % (ft["toFillRate"] * 100)])
    if nm:
        rows.append(["다음 달 말 전망", "%s (입사 %s / 퇴사 %s, TO 대비 %s)" % (nm.get("forecastNextMonthEnd"), nm.get("plannedIn"), nm.get("plannedOut"),
                                                                     signed(nm.get("toGapNextMonthEnd", 0)))])
    d.table(["지표", "값"], rows)
    d.p("산술 검증: 월말 예측 인원 = 현재 재직 %d + 입사 예정 %d %s 퇴사 예정 %d = %d · 월말 TO Gap = %d %s %d = %s"
        % (st["activeHeadcount"], ft["plannedIn"], MINUS, ft["plannedOut"], ft["forecastMonthEnd"], ft["forecastMonthEnd"], MINUS, ft["toHeadcount"], signed(ft["toGapMonthEnd"])))

    d.h(2, "조직별 인원 예측")
    ol = dict((x["deptCode"], x.get("onLeave", 0)) for x in stats["byDepartment"])
    d.table(["조직", "조직 그룹", "TO", "현재 재직", "휴직", "입사 예정", "퇴사 예정", "월말 예측", "현재 Gap", "월말 Gap", "권고"],
            [[x["department"], x["orgGroup"], x["toHeadcount"], x["activeHeadcount"], ol.get(x["deptCode"], 0), x["plannedIn"], x["plannedOut"],
              x["forecastMonthEnd"], signed(x["toGapAsOf"]), signed(x["toGapMonthEnd"]), x["recommendation"]] for x in fc["byDepartment"]]
            + [["합계", "", ft["toHeadcount"], ft["activeHeadcount"], st["onLeave"], ft["plannedIn"], ft["plannedOut"], ft["forecastMonthEnd"],
                signed(ft["toGapAsOf"]), signed(ft["toGapMonthEnd"]), ""]])
    if fc.get("byOrgGroup"):
        d.table(["조직 그룹", "TO", "현재 재직", "월말 예측", "월말 Gap", "다음 달 말"],
                [[g["orgGroup"], g["toHeadcount"], g["activeHeadcount"], g["forecastMonthEnd"], signed(g["toGapMonthEnd"]),
                  (g.get("nextMonth") or {}).get("forecastNextMonthEnd", "")] for g in fc["byOrgGroup"]])
    d.h(3, "인력계획 인사이트")
    d.ul(["[%s] %s — %s → %s" % (i["type"], i["label"], i["detail"], i["action"]) for i in fc.get("insights") or []] or ["권고 없음 — 전 조직 TO 임계값 이내"])
    d.p("판정 규칙: 월말 Gap ≤ %s4 → 채용 가속 / ≥ +5 → TO 재검토/이동배치 / 그 외 정상 관리(제안이며 결정은 사람의 승인 gate). 가정: %s"
        % (MINUS, " · ".join(fc.get("assumptions") or []) or "명시된 가정 없음"))
    if risk:
        s = risk.get("summary") or {}
        d.h(3, "리스크 반영 시나리오 (규칙 기반 추정)")
        d.p("이직 리스크 등급 분포(재직자): 높음 %s · 중간 %s · 낮음 %s. 3개월 기대 이탈 %s명(추정). 등급 집계만 인용하며 개인 점수·명단은 싣지 않는다."
            % (s.get("높음"), s.get("중간"), s.get("낮음"), s.get("expectedAttritionNext3Months")))
        ra = [x for x in fc["byDepartment"] if (x.get("riskAdjusted") or {}).get("forecastNextMonthEndRiskAdjusted") is not None]
        if ra:
            d.table(["조직", "다음 달 말(기본)", "기대 이탈(추정)", "다음 달 말(리스크 반영)"],
                    [[x["department"], (x.get("nextMonth") or {}).get("forecastNextMonthEnd", ""), x["riskAdjusted"].get("expectedAttrition"),
                      x["riskAdjusted"]["forecastNextMonthEndRiskAdjusted"]] for x in ra])

    d.h(2, "인원 통계 요약 (재직 %d 기준)" % st["activeHeadcount"])
    labels = OrderedDict([("employmentType", "고용유형(총원 %d)" % st["headcount"]), ("gender", "성별"), ("ageBand", "연령대"), ("jobFamily", "직군"),
                          ("level", "직책/레벨"), ("tenureBand", "재직기간"), ("totalExperienceBand", "총경력"), ("stage", "스테이지")])
    rows = []
    for k, lab in labels.items():
        src = (stats.get("byAttributeAll") or {}).get("employmentType") if k == "employmentType" else (stats.get("byAttribute") or {}).get(k)
        rows.append([lab, join_kv(src)])
    d.table(["분류", "분포"], rows)
    ex = stats.get("experience") or {}
    if ex:
        d.p("평균 재직기간 %.2f년(중앙값 %.2f) · 평균 총경력 %.2f년(중앙값 %.2f)"
            % (ex.get("avgTenureYears", 0), ex.get("medianTenureYears", 0), ex.get("avgTotalExperienceYears", 0), ex.get("medianTotalExperienceYears", 0)))

    ps = stats.get("plannedSeparations") or {}
    d.h(2, "퇴직사유별 예정 퇴직 구분 (월말까지 %s명)" % ps.get("total", ft["plannedOut"]))
    d.table(["퇴직사유", "예정 인원"], [[k, v] for k, v in (ps.get("bySeparationReason") or {}).items()] or [["(없음)", 0]])
    d.ul(["퇴직 구분: " + join_kv(ps.get("bySeparationType")),
          "조직별: " + join_kv(ps.get("byDepartment")),
          "월별(다음 달 포함): " + join_kv(ps.get("byMonth"))])

    d.h(2, "데이터 품질")
    dq = stats.get("dataQuality") or {}
    items = []
    if cleansing:
        items.append("클린징: 원천 %s행 → 정제 %s행(중복 제거 %s), 부서명 정규화 %s건, 입사일자 보정 %s건, 조직 구조 정규화 %s개 조직 → 4개 조직 그룹"
                     % ((cleansing.get("rowsIn") or {}).get("headcount-master"), (cleansing.get("rowsOut") or {}).get("headcount-master"),
                        cleansing.get("duplicatesRemoved"), cleansing.get("orgNameCorrections"), cleansing.get("hireDateCorrections"),
                        len(cleansing.get("orgGroupMapping") or {})))
    else:
        items.append("클린징 요약(data/clean/cleansing-summary.json) 없음 — 부서명 정규화·입사일자 보정 건수 미기재(people-data-cleanser 재실행 후 리포트 재생성)")
    unresolved = "미해결 항목 %s건(정제 마스터 기준, 고객사 HR 확인 대기): %s" % (dq.get("unresolvedCount", 0), join_kv(dq.get("unresolvedByFlag")))
    if cleansing and cleansing.get("unresolvedCount") is not None:
        unresolved += " · 원천 4종 합산 %s건" % cleansing.get("unresolvedCount")
    items.append(unresolved)
    notes = list(dq.get("briefDiscrepancies") or [])
    computed = brief_group_note(stats)
    if computed and not notes:
        notes.append(computed)
    items.extend(notes)
    if not notes:
        items.append("브리프 정본 수치와의 불일치: 없음(조직 그룹 재직 합 일치)")
    d.ul(items)

    d.h(2, "자동화 효과 (추정)")
    if auto:
        a, m = auto.get("automated") or {}, auto.get("manualBaseline") or {}
        d.p("수작업 기준 월 %s시간(%s) → 파이프라인 %.0f초 + 사람 검토 %s시간/월, 절감률 %.0f%%. %s"
            % (m.get("hoursPerMonth"), m.get("basis", "가정"), float(a.get("pipelineSeconds") or 0), a.get("humanReviewHoursPerMonth"),
               float(auto.get("savingRate") or 0) * 100, auto.get("note", "")))
    else:
        d.p("데이터 없음 — data/stats/automation-effect.json 부재(automation_effect.py 선행 실행 필요). 절감률은 추정치이며 여기서 만들지 않는다.")

    d.h(2, "부록: 정의")
    d.ul(["재직 인원 = 상태 재직(TO 비교·예측 기준) · 휴직 인원 별도 · 총원 = 재직 + 휴직",
          "월말 예측 인원 = 현재 재직 + 월말까지 입사 예정 %s 월말까지 퇴사 예정(예정일 경과 건 포함, 마스터에 없는 사번 제외)" % MINUS,
          "TO Gap = 재직(또는 월말 예측) %s TO. 양수 초과, 음수 부족. TO 충족률 = 월말 예측 / TO" % MINUS,
          "권고 = 결정적 규칙(위 판정 규칙)에 따른 제안. 채용·TO·조직 변경 결정은 사람의 승인 gate",
          "이 리포트는 집계만 포함하며 성명·생년월일·개인 리스크 점수를 싣지 않는다(pii-minimization-policy). 원본: data/stats/headcount-stats.json, month-end-forecast.json"])
    return d, hire, review


# ---------------------------------------------------------------- 실행
def render(root, as_of, log):
    stats, fc = load_json(root, "stats"), load_json(root, "forecast")
    missing = [REL[k] for k, v in (("stats", stats), ("forecast", fc)) if v is None]
    if missing:
        log.add("실패한 것", "필수 입력 없음: %s → headcount-statistician / headcount-forecaster 선행 필요" % ", ".join(missing))
        log.add("다음 agent 인계점", "상류 산출물 생성 후 이 스크립트를 그대로 재실행")
        return 3, OrderedDict([("status", "input-missing"), ("missing", missing), ("handoffLog", HANDOFF_REL)])
    optional = OrderedDict((k, load_json(root, k)) for k in ("payroll", "risk", "auto", "cleansing"))
    payroll, risk, auto, cleansing = optional["payroll"], optional["risk"], optional["auto"], optional["cleansing"]
    log.add("본 데이터·근거", "`%s` asOfDate %s, byDepartment %d행 · `%s` asOfDate %s, monthEnd %s, byDepartment %d행"
            % (REL["stats"], stats.get("asOfDate"), len(stats["byDepartment"]), REL["forecast"], fc.get("asOfDate"), fc.get("monthEnd"), len(fc["byDepartment"])))
    for k, v in optional.items():
        log.add("본 데이터·근거", "`%s` %s" % (REL[k], "읽음" if v else "없음(선택 — 해당 절 축약)"))
    log.add("본 데이터·근거", "근거: DATA_CONTRACT §6(파일·제목·본문 순서·dispatch) · §8(자동화 효과) · §2-7(브리프 그룹 합 불일치 기록) · 브리프 §10(요약 5불릿)")
    for k, v in optional.items():
        if v is None:
            log.add("실패한 것", "선택 입력 `%s` 없음 → 해당 절을 '없음/데이터 없음'으로 렌더(건너뛴 검사: %s)" % (REL[k], "payroll.monthEndActive 대사" if k == "payroll" else "없음"))
    if stats.get("asOfDate") != as_of.isoformat() or fc.get("asOfDate") != as_of.isoformat():
        log.add("실패한 것", "입력 asOfDate(%s/%s)가 인자 %s와 다름 — 상류 기준일 확인" % (stats.get("asOfDate"), fc.get("asOfDate"), as_of.isoformat()))

    fails, checked = reconcile(stats, fc, payroll)
    if fails:
        path = os.path.join(root, UNRECONCILED_REL)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"asOfDate": as_of.isoformat(), "stage": STAGE, "failures": fails}, f, ensure_ascii=False, indent=2)
        log.add("실패한 것", "대사 실패 %d건(검사 %d건) — 진단 `%s`. reports/ 미작성. 원인 후보: headcount-statistician↔headcount-forecaster↔payroll-close-analyst 중 상류 불일치"
                % (len(fails), checked, UNRECONCILED_REL))
        log.add("다음 agent 인계점", "people-data-auditor가 어느 상류가 틀렸는지 판정 → 해당 단계 재실행 → 이 스크립트 재실행")
        return 2, OrderedDict([("status", "reconciliation-failed"), ("reconciliation", {"matched": False, "checked": checked, "mismatches": fails}),
                               ("diagnostic", UNRECONCILED_REL), ("handoffLog", HANDOFF_REL)])
    log.add("검증된 것", "대사 %d건 일치: totals 5필드(재직 %s·TO %s·gapAsOf %s·입사 %s·퇴사 %s), 조직별 재직·TO %d행%s"
            % (checked, stats["totals"]["activeHeadcount"], stats["totals"]["toHeadcount"], stats["totals"]["toGapAsOf"], stats["totals"]["plannedIn"],
               stats["totals"]["plannedOut"], len(fc["byDepartment"]), ", payroll.monthEndActive = %s" % fc["totals"]["forecastMonthEnd"] if payroll else ""))

    period, send_month = as_of.strftime("%Y-%m"), next_month(as_of)
    subject = "[Zero Company] %s HR Headcount Forecast" % period
    send_at = send_month.isoformat() + "T09:00:00+09:00"
    stem = "monthly-report-%s" % send_month.strftime("%Y-%m")
    csv_rel = "reports/org-forecast-%s.csv" % period
    doc, hire, review = build(stats, fc, risk, auto, cleansing, subject, as_of, send_at, csv_rel)
    md, html_text = doc.md(), doc.html(subject)
    hits = sorted(n for n in pii_names(root) if n in md)
    if hits:
        log.add("실패한 것", "PII 검출: 정제 성명 %d건이 본문에 포함 → 파일 미작성(exit 4). 원인 후보: 상류 JSON의 label/detail 필드에 성명 유입" % len(hits))
        log.add("다음 agent 인계점", "상류 산출물(insights·dataQuality 문장)에서 성명 제거 후 재실행. dispatch status는 blocked-pii로 취급")
        return 4, OrderedDict([("status", "pii-violation"), ("pii", {"namesFound": len(hits)}), ("note", "성명이 본문에 포함되어 파일을 쓰지 않음"),
                               ("handoffLog", HANDOFF_REL)])

    rep = os.path.join(root, "reports")
    os.makedirs(rep, exist_ok=True)
    with open(os.path.join(rep, stem + ".md"), "w", encoding="utf-8") as f:
        f.write(md)
    with open(os.path.join(rep, stem + ".html"), "w", encoding="utf-8") as f:
        f.write(html_text)
    with open(os.path.join(root, csv_rel), "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(CSV_COLS)
        for x in fc["byDepartment"]:
            w.writerow([x[c] for c in CSV_COLS])
    recipients = OrderedDict((g, [a + DOMAIN for a in addrs]) for g, addrs in RECIPIENTS.items())
    dispatch = OrderedDict([  # §6 필드만 — 본문 파일 경로 필드는 계약에 없어 넣지 않는다(contractGaps)
        ("sendAt", send_at), ("schedule", "0 9 1 * *"), ("recipients", recipients), ("subject", subject),
        ("attachments", ["site/insight/index.html", csv_rel]), ("status", "ready-to-send"), ("gate", "approval-gate: 외부 발송"),
    ])
    with open(os.path.join(rep, "monthly-report-dispatch.json"), "w", encoding="utf-8") as f:
        json.dump(dispatch, f, ensure_ascii=False, indent=2)

    artifacts = ["reports/%s.md" % stem, "reports/%s.html" % stem, csv_rel, "reports/monthly-report-dispatch.json"]
    domains_ok = all(a.endswith("@" + DOMAIN) for v in recipients.values() for a in v)
    dq = stats.get("dataQuality") or {}
    brief_recorded = bool(dq.get("briefDiscrepancies")) or brief_group_note(stats) is not None
    log.add("시도한 것", "산출 4종: %s (제목 `%s`, 발송월 %s, 기준월 %s)" % (", ".join(artifacts), subject, send_month.strftime("%Y-%m"), period))
    log.add("검증된 것", "요약 5불릿(브리프 §10 문장): 재직 %d / 월말 %d · gap %s · 채용 가속 %s · TO 재검토 %s · 첨부 2종; 즉시 액션 %d건"
            % (stats["totals"]["activeHeadcount"], fc["totals"]["forecastMonthEnd"], signed(fc["totals"]["toGapMonthEnd"]), ", ".join(hire) or "없음",
               ", ".join(review) or "없음", len(fc.get("immediateActions") or [])))
    log.add("검증된 것", "PII: 정제 성명 %d건 스캔 → 본문 포함 0건 · CSV %d행(§6 열 10개) · dispatch 수신자 %d명 전원 @%s(%s) · status ready-to-send · gate 기재"
            % (len(pii_names(root)), len(fc["byDepartment"]), sum(len(v) for v in recipients.values()), DOMAIN, "OK" if domains_ok else "위반"))
    log.add("검증된 것", "데이터 품질 절: 클린징 건수 %s · 미해결 %s건 · 브리프 그룹 합 불일치 기록 %s · 자동화 효과 절 %s"
            % ("%s/%s" % (cleansing.get("orgNameCorrections"), cleansing.get("hireDateCorrections")) if cleansing else "미기재",
               dq.get("unresolvedCount", 0), "있음" if brief_recorded else "없음(불일치 없음)", "추정 표기" if auto else "데이터 없음"))
    log.add("다음 agent 인계점", "people-data-auditor: `%s` 요약 수치 ↔ forecast.totals, `%s` 11행 ↔ §2-7, PII 0건, dispatch 제목·도메인" % (artifacts[0], csv_rel))
    log.add("다음 agent 인계점", "release-engineer: `%s`를 사이트와 함께 push·배포(Insight 헤더 링크 대상). 발송·cron(`0 9 1 * *`) 등록은 승인 gate — dispatch.json + 발송 요청서로 승인 요청" % artifacts[1])
    log.add("다음 agent 인계점", "승인 대기: 외부 발송(status ready-to-send, sent 없음). 승인 뒤에도 이 스크립트는 발송하지 않는다")
    log.add("다음 agent 인계점", "contractGaps: §6 dispatch.json에 본문(md/html) 경로 필드 없음 — 발송 실행자는 artifacts[0..1]을 본문으로 쓴다")
    return 0, OrderedDict([
        ("status", "ok"), ("asOfDate", as_of.isoformat()), ("reportMonth", period), ("sendMonth", send_month.strftime("%Y-%m")), ("subject", subject),
        ("artifacts", artifacts),
        ("summaryNumbers", OrderedDict([("activeHeadcount", stats["totals"]["activeHeadcount"]), ("forecastMonthEnd", fc["totals"]["forecastMonthEnd"]),
                                        ("toGapMonthEnd", fc["totals"]["toGapMonthEnd"]), ("hiringAcceleration", hire), ("toReview", review),
                                        ("immediateActions", len(fc.get("immediateActions") or [])),
                                        ("orgNameCorrections", cleansing.get("orgNameCorrections") if cleansing else None),
                                        ("hireDateCorrections", cleansing.get("hireDateCorrections") if cleansing else None)])),
        ("reconciliation", OrderedDict([("matched", True), ("checked", checked), ("mismatches", []), ("csvRows", len(fc["byDepartment"])),
                                        ("briefDiscrepancyRecorded", brief_recorded)])),
        ("automationEffect", OrderedDict([("applied", bool(auto)), ("pipelineSeconds", ((auto or {}).get("automated") or {}).get("pipelineSeconds")),
                                          ("savingRate", (auto or {}).get("savingRate")), ("estimateLabelPresent", True)])),
        ("pii", OrderedDict([("namesFound", 0), ("birthDateFound", False), ("riskScoreFound", False)])),
        ("dispatch", OrderedDict([("status", "ready-to-send"), ("gate", dispatch["gate"]), ("sendAt", send_at), ("schedule", "0 9 1 * *"),
                                  ("recipients", OrderedDict((g, len(v)) for g, v in recipients.items())), ("recipientDomainsOk", domains_ok),
                                  ("attachments", dispatch["attachments"])])),
        ("optionalInputsUsed", [k for k, v in (("payroll", payroll), ("attrition", risk), ("automationEffect", auto), ("cleansingSummary", cleansing)) if v]),
        ("contractGaps", ["§6 dispatch.json에 본문(md/html) 경로 필드가 없다 — 발송 실행자가 리포트 파일을 찾을 필드(예: body) 제안"]),
        ("handoffLog", HANDOFF_REL),
    ])


def main(argv=None):
    p = argparse.ArgumentParser(description="월초 리포트 렌더 (DATA_CONTRACT v2 §6)")
    p.add_argument("--root", default=DEFAULT_ROOT)
    p.add_argument("--as-of", dest="as_of", default=DEFAULT_AS_OF)
    a = p.parse_args(argv)
    log = Handoff(a.root, a.as_of, "python3 %s --root %s --as-of %s" % (os.path.basename(__file__), a.root, a.as_of))
    log.add("다음 agent 인계점", "실행 중 — 종료 시 이 로그를 덮어쓴다")
    log.write("시작")
    log.s["다음 agent 인계점"] = []
    try:
        code, summary = render(a.root, datetime.date.fromisoformat(a.as_of), log)
    except Exception as e:  # noqa: BLE001
        code, summary = 1, OrderedDict([("status", "error"), ("errorType", type(e).__name__), ("error", str(e)), ("handoffLog", HANDOFF_REL)])
        log.add("실패한 것", "예외 %s: %s → reports/ 미작성. 스크립트를 즉석에서 고치지 않고 입력 shape(DATA_CONTRACT §4-1·§4-2)을 먼저 확인" % (type(e).__name__, str(e)[:200]))
    try:
        log.write("종료 exit %d" % code)
    except OSError as e:
        summary["handoffLogError"] = str(e)
    print(json.dumps(summary, ensure_ascii=False))
    return code


if __name__ == "__main__":
    sys.exit(main())
