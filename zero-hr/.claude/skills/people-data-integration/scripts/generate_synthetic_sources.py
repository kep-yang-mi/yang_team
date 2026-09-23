#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""generate_synthetic_sources.py — Zero Company HR 가상 원천 생성기 v2 (skill: people-data-integration)

DATA_CONTRACT v2 §1·§2를 구현한다.
  1) 정답(true) 인구를 먼저 만든다 — §2-7의 조직별 HC/OL/in/out, 고용유형(427), 그리고 재직 406 기준
     성별·연령대·직군·레벨·재직기간·총경력·스테이지 분포를 **정확히** 만족한다.
  2) §2-5의 결함 유형·건수를 원천 CSV에 주입한다. 주입 값은 §2-8 결정적 보정 규칙으로 정답에 되돌아가는 값만 쓴다.
  3) 주입 내역을 §2-6 정답지(injected-defects.json)로 남긴다.
  4) --self-check: 쓴 파일을 다시 읽어 정답지로 복원한 뒤 §2-7 전 수치·결함 건수를 대조한다.

산출물
  data/reference/org-chart.csv          §1 조직 체계(4 그룹 > 11 조직)
  data/reference/company-stages.json    §1 스테이지 경계일(재직 406의 입사일 순위 49/151/140/66)
  data/raw/headcount-master.csv         §2-1 (427 + 중복 8 = 435행, 한글 헤더, 결함 포함)
  data/raw/to-plan.csv                  §2-2 (11행)
  data/raw/planned-joiners.csv          §2-3 (27행)
  data/raw/planned-leavers.csv          §2-4 (19행)
  data/raw/injected-defects.json        §2-6 정답지

사용법
  python3 generate_synthetic_sources.py [--root DIR] [--as-of YYYY-MM-DD] [--self-check]
  --check-only: 기존 파일을 변경하지 않고 검증만 한다.
  --no-bom: CSV를 BOM 없는 UTF-8로 쓴다. 기본 출력은 기존 배포본과 동일하다.

Python 3.9 표준 라이브러리만. random.seed(20260923) 고정 — 재실행 시 같은 파일. 마지막 줄에 요약 JSON 1행.
"""

import argparse
import csv
import datetime as dt
import json
import math
import os
import random
import sys
import time

SEED = 20260923
DEFAULT_ROOT = "/Users/yang/development/zero-hr"
DEFAULT_AS_OF = "2026-09-23"
EXCEL_EPOCH = dt.date(1899, 12, 30)
COMPANY_START = dt.date(2019, 1, 1)
CLIENT = "㈜온다테크"

PATHS = {
    "org-chart": "data/reference/org-chart.csv",
    "company-stages": "data/reference/company-stages.json",
    "headcount-master": "data/raw/headcount-master.csv",
    "to-plan": "data/raw/to-plan.csv",
    "planned-joiners": "data/raw/planned-joiners.csv",
    "planned-leavers": "data/raw/planned-leavers.csv",
    "injected-defects": "data/raw/injected-defects.json",
}

# ---------------------------------------------------------------------------
# §1 조직 체계 · §2 헤더
# ---------------------------------------------------------------------------
ORG_HEADER = ["orgGroupCode", "orgGroup", "deptCode", "department", "formerNames", "establishedOn"]
ORG_CHART = [
    ("G0", "Executive", "D01", "CEO Office", "Executive Office;CEO Staff;경영지원", "2019-01-01"),
    ("G1", "Build", "D02", "Product", "Product Management;PM;프로덕트", "2019-01-01"),
    ("G1", "Build", "D03", "Engineering", "R&D;Eng;Engineering Dept;개발", "2019-01-01"),
    ("G1", "Build", "D04", "Design", "UX;Product Design;디자인", "2019-01-01"),
    ("G1", "Build", "D05", "Data & AI", "Data and AI;Data/AI;AI Lab;Data Science", "2019-01-01"),
    ("G2", "Go-To-Market", "D06", "Sales", "Sales Team;BizDev;영업", "2019-01-01"),
    ("G2", "Go-To-Market", "D07", "Marketing", "Growth;Growth Marketing;마케팅", "2019-01-01"),
    ("G2", "Go-To-Market", "D08", "Customer Success", "Customer Support;CS;CX;고객지원", "2019-01-01"),
    ("G3", "Operations", "D09", "People", "HR;People Team;Human Resources;인사", "2019-01-01"),
    ("G3", "Operations", "D10", "Finance", "Finance & Accounting;Accounting;재무", "2019-01-01"),
    ("G3", "Operations", "D11", "Legal & Compliance", "Legal and Compliance;Legal&Compliance;Legal;법무", "2019-01-01"),
]
DEPT_CODES = [r[2] for r in ORG_CHART]
DEPT_NAME = dict((r[2], r[3]) for r in ORG_CHART)
NAME_TO_CODE = dict((r[3], r[2]) for r in ORG_CHART)
FORMER = dict((r[2], r[4].split(";")) for r in ORG_CHART)

MASTER_HEADER = ["사번", "성명", "성별", "생년월일", "소속", "직군", "레벨", "고용유형", "재직상태",
                 "휴직유형", "휴직시작일", "입사일", "계약종료일", "입사전경력(개월)", "최종수정일"]
TO_HEADER = ["조직", "정원", "기준월"]
JOINER_HEADER = ["성명", "소속", "직군", "레벨", "고용유형", "성별", "생년월일", "입사예정일", "입사전경력(개월)"]
LEAVER_HEADER = ["사번", "성명", "소속", "퇴사예정일", "퇴직사유"]

# ---------------------------------------------------------------------------
# §2-7 정본 수치
# ---------------------------------------------------------------------------
# deptCode: (HC 재직, OL 휴직, TO, in, out)
TARGET_DEPT = [
    ("D01", 10, 0, 10, 0, 0), ("D02", 51, 3, 54, 3, 1), ("D03", 104, 6, 112, 5, 4), ("D04", 25, 1, 26, 1, 1),
    ("D05", 40, 2, 34, 2, 1), ("D06", 58, 3, 62, 3, 3), ("D07", 30, 1, 32, 1, 1), ("D08", 40, 3, 42, 2, 1),
    ("D09", 18, 1, 18, 1, 0), ("D10", 19, 1, 20, 1, 1), ("D11", 11, 0, 12, 0, 1),
]
DEPT_TARGET = dict((r[0], r) for r in TARGET_DEPT)
JOB_FAMILY_OF_DEPT = {"D01": "Executive", "D02": "Product", "D03": "Engineering", "D04": "Design", "D05": "Data/AI",
                      "D06": "Sales", "D07": "Marketing", "D08": "Customer Success", "D09": "People",
                      "D10": "Finance", "D11": "Legal"}
D05_FAMILIES = [("Data/AI", 24), ("Engineering", 12), ("Product", 4)]
OCT_JOINERS = [("D03", 3), ("D05", 2), ("D06", 2), ("D02", 1)]
OCT_LEAVERS = [("D03", 1), ("D06", 1), ("D08", 1), ("D07", 1)]
OCT_LEAVER_REASONS = ["자발퇴사", "개인사유", "조직개편", "자발퇴사"]

EMP_TYPE_ALL = [("정규직", 354), ("계약직", 31), ("인턴", 19), ("파견", 23)]
EMP_TYPE_LEAVE = [("정규직", 19), ("계약직", 2)]
GENDER = [("여성", 188), ("남성", 195), ("미응답", 23)]
AGE_BAND = [("20대", 82), ("30대", 221), ("40대", 83), ("50대+", 20)]
AGE_RANGE = {"20대": (23, 29), "30대": (30, 39), "40대": (40, 49), "50대+": (50, 61)}
LEVELS = [("IC1", 33), ("IC2", 65), ("IC3", 82), ("Senior", 89), ("Lead", 55), ("Manager", 44), ("Director", 25), ("VP", 13)]
LEVEL_ORDER = [l for l, _ in LEVELS]
TENURE_BAND = [("1년 미만", 54), ("1~3년", 151), ("3~5년", 103), ("5년+", 98)]
TENURE_RANGE = {"1년 미만": (0.03, 0.97), "1~3년": (1.03, 2.97), "3~5년": (3.03, 4.97), "5년+": (5.03, 7.65)}
TOTAL_BAND = [("0~3년", 56), ("3~7년", 137), ("7~12년", 142), ("12년+", 71)]
TOTAL_RANGE = {"0~3년": (0.0, 3.0), "3~7년": (3.0, 7.0), "7~12년": (7.0, 12.0), "12년+": (12.0, 24.0)}
STAGE = [("Seed", 49), ("Series A", 151), ("Scale-up", 140), ("Enterprise", 66)]
LEAVER_REASONS = [("자발퇴사", 5), ("계약만료", 3), ("조직개편", 2), ("성과/적합도", 2), ("개인사유", 2)]
CONTRACT_TYPES = ("계약직", "인턴", "파견")
LEAVE_TYPES = [("육아휴직", 12), ("질병휴직", 5), ("기타", 4)]

# §2-5 기대 결함 건수 (self-check 대조용)
EXPECTED_DEFECTS = {
    "headcount-master": {"org-old-name": 6, "org-variant": 4, "org-typo": 3, "org-whitespace": 4, "org-unknown": 2,
                         "hire-date-format": 31, "date-format": 6, "date-logic": 2, "status-inconsistency": 3,
                         "missing-required": 3, "duplicate": 8, "code-variant": 32},
    "to-plan": {"org-variant": 3, "date-format": 4},
    "planned-joiners": {"org-variant": 2, "date-format": 3, "code-variant": 1},
    "planned-leavers": {"date-format": 2, "reason-freetext": 6, "stale-planned-leaver": 1, "unknown-emp": 1},
}

SURNAMES = ["김", "이", "박", "최", "정", "강", "조", "윤", "장", "임", "한", "오", "서", "신", "권", "황", "안", "송",
            "전", "홍", "유", "고", "문", "양", "손", "배", "백", "허", "남", "심", "노", "하", "곽", "성", "차", "주",
            "우", "구", "민", "류", "나", "진", "지", "엄", "채", "원", "천", "방", "공", "현"]
SYLLABLES = ["민", "서", "지", "현", "수", "영", "준", "우", "하", "은", "도", "윤", "예", "아", "시", "연", "재", "원",
             "성", "진", "호", "태", "주", "경", "승", "유", "채", "다", "소", "정", "혜", "규", "빈", "율", "찬", "건",
             "석", "훈", "희", "나", "라", "리", "선", "동", "인", "상", "기", "환", "철", "미"]


# ---------------------------------------------------------------------------
# 공통 유틸 · 파생 규칙 (§2-8과 동일 — 클린저와 같은 공식)
# ---------------------------------------------------------------------------
def iso(d):
    return d.isoformat() if d else ""


def days(n):
    return dt.timedelta(days=n)


def month_end(d):
    nxt = dt.date(d.year + (d.month // 12), d.month % 12 + 1, 1)
    return nxt - days(1)


def next_month_range(d):
    first = month_end(d) + days(1)
    return first, month_end(first)


def rand_date(lo, hi):
    if hi < lo:
        hi = lo
    return lo + days(random.randint(0, (hi - lo).days))


def age_on(birth, on):
    a = on.year - birth.year
    if (on.month, on.day) < (birth.month, birth.day):
        a -= 1
    return a


def same_day_year(d, year):
    try:
        return d.replace(year=year)
    except ValueError:
        return d.replace(year=year, day=28)


def birth_for_age(age, on):
    hi = same_day_year(on, on.year - age)
    lo = same_day_year(on, on.year - age - 1) + days(1)
    b = rand_date(lo, hi)
    assert age_on(b, on) == age
    return b


def age_band(age):
    if age < 30:
        return "20대"
    if age < 40:
        return "30대"
    if age < 50:
        return "40대"
    return "50대+"


def tenure_years(hire, as_of):
    if hire > as_of:
        return 0.0
    return round((as_of - hire).days / 365.25, 2)


def tenure_band(t):
    if t < 1:
        return "1년 미만"
    if t < 3:
        return "1~3년"
    if t < 5:
        return "3~5년"
    return "5년+"


def total_exp(prior_months, tenure):
    return round(prior_months / 12.0 + tenure, 2)


def total_band(x):
    if x < 3:
        return "0~3년"
    if x < 7:
        return "3~7년"
    if x < 12:
        return "7~12년"
    return "12년+"


def stage_of(hire_iso, stages):
    for s in stages:
        if s["from"] <= hire_iso <= s["to"]:
            return s["stage"]
    return stages[-1]["stage"]


def expand(pairs):
    out = []
    for v, n in pairs:
        out.extend([v] * n)
    return out


def counter(values):
    out = {}
    for v in values:
        out[v] = out.get(v, 0) + 1
    return out


def date_variant(d, kind):
    if kind == "slash":
        return "%d/%02d/%02d" % (d.year, d.month, d.day)
    if kind == "dot":
        return "%d.%02d.%02d" % (d.year, d.month, d.day)
    if kind == "compact":
        return "%04d%02d%02d" % (d.year, d.month, d.day)
    if kind == "short-dot":
        return "%02d.%02d.%02d" % (d.year % 100, d.month, d.day)
    if kind == "korean":
        return "%d년 %d월 %d일" % (d.year, d.month, d.day)
    if kind == "excel":
        return str((d - EXCEL_EPOCH).days)
    raise ValueError(kind)


class NamePool(object):
    def __init__(self):
        self.used = set()

    def next(self):
        while True:
            n = random.choice(SURNAMES) + random.choice(SYLLABLES) + random.choice(SYLLABLES)
            if n not in self.used:
                self.used.add(n)
                return n


# ---------------------------------------------------------------------------
# 정답 인구 생성
# ---------------------------------------------------------------------------
def build_active(as_of):
    active = []
    for code, hc, _ol, _to, _i, _o in TARGET_DEPT:
        fams = [JOB_FAMILY_OF_DEPT[code]] * hc
        if code == "D05":
            fams = expand(D05_FAMILIES)
            random.shuffle(fams)
        for f in fams:
            active.append({"dept": code, "jobFamily": f, "status": "재직", "leaveType": "", "leaveStart": None,
                           "future": False, "contractEnd": None, "missingEnd": False})
    random.shuffle(active)

    # 재직기간 구간 → 입사일
    bands = expand(TENURE_BAND)
    random.shuffle(bands)
    for e, b in zip(active, bands):
        lo, hi = TENURE_RANGE[b]
        e["tenureBand"] = b
        e["tenure"] = random.uniform(lo, hi)
    under1 = [e for e in active if e["tenureBand"] == "1년 미만"]
    random.shuffle(under1)
    for e in under1[:2]:                     # date-logic: 재직인데 입사일이 기준일 이후(미해결, 재직기간 0)
        e["future"] = True
        e["tenure"] = 0.0
        e["hire"] = as_of + days(random.randint(6, 40))
    for e in under1[2:4]:                    # 당월 입사자(급여 일할 계산 데모용)
        e["tenure"] = random.randint(3, 21) / 365.25
    for e in active:
        if not e["future"]:
            e["hire"] = as_of - days(int(round(e["tenure"] * 365.25)))
        e["tenure"] = tenure_years(e["hire"], as_of)
        assert tenure_band(e["tenure"]) == e["tenureBand"]

    # 총경력 구간: 재직기간 순위와 짝지은 뒤 근접 순위끼리 무작위 교환(양의 상관 유지, 실현 가능성 검사)
    order = sorted(active, key=lambda x: (x["tenure"], random.random()))
    for e, b in zip(order, expand(TOTAL_BAND)):
        e["totalBand"] = b

    def exp_feasible(band, tenure):
        return tenure < TOTAL_RANGE[band][1] - 0.3

    n = len(order)
    for _ in range(5000):
        i = random.randrange(n)
        j = min(n - 1, max(0, i + random.randint(-45, 45)))
        a, b = order[i], order[j]
        if a is b:
            continue
        if exp_feasible(b["totalBand"], a["tenure"]) and exp_feasible(a["totalBand"], b["tenure"]):
            a["totalBand"], b["totalBand"] = b["totalBand"], a["totalBand"]
    for e in active:
        lo, hi = TOTAL_RANGE[e["totalBand"]]
        lo = max(lo, e["tenure"])
        total = random.uniform(lo + 0.08, hi - 0.08)
        e["prior"] = max(0, int(round((total - e["tenure"]) * 12)))
        e["totalExp"] = total_exp(e["prior"], e["tenure"])
        assert total_band(e["totalExp"]) == e["totalBand"], (e["totalExp"], e["totalBand"])

    # 고용유형(재직 406 = 정규직 335 / 계약직 29 / 인턴 19 / 파견 23; 휴직 21이 정규직 19·계약직 2를 채워 427 합계 유지)
    by_exp = sorted(active, key=lambda x: (x["totalExp"], random.random()))
    pool = [e for e in by_exp if e["dept"] != "D01"]
    for e in random.sample(pool[:60], 19):
        e["empType"] = "인턴"
    rest = [e for e in pool if "empType" not in e and e["totalExp"] < 12]
    others = random.sample(rest, 23 + 29)
    for e in others[:23]:
        e["empType"] = "파견"
    for e in others[23:]:
        e["empType"] = "계약직"
    for e in active:
        e.setdefault("empType", "정규직")

    # 연령대: 총경력 순위와 짝지은 뒤 근접 교환. 나이 ≥ 20 + ceil(총경력)
    def age_feasible(band, total):
        return AGE_RANGE[band][1] >= 20 + math.ceil(total)

    for e, b in zip(by_exp, expand(AGE_BAND)):
        e["ageBand"] = b
    for _ in range(5000):
        i = random.randrange(n)
        j = min(n - 1, max(0, i + random.randint(-60, 60)))
        a, b = by_exp[i], by_exp[j]
        if a is b:
            continue
        if age_feasible(b["ageBand"], a["totalExp"]) and age_feasible(a["ageBand"], b["totalExp"]):
            a["ageBand"], b["ageBand"] = b["ageBand"], a["ageBand"]
    for e in active:
        lo, hi = AGE_RANGE[e["ageBand"]]
        lo = max(lo, 20 + int(math.ceil(e["totalExp"])))
        e["age"] = random.randint(lo, hi)
        e["birth"] = birth_for_age(e["age"], as_of)
        assert age_band(age_on(e["birth"], as_of)) == e["ageBand"]

    # 성별
    genders = expand(GENDER)
    random.shuffle(genders)
    for e, g in zip(active, genders):
        e["gender"] = g

    # 레벨: 경력 점수 순위. 조직마다 VP ≥ 1(CEO Office 3), 재직 18명 이상 조직은 Director ≥ 1
    for e in active:
        e["score"] = e["totalExp"] + 0.5 * e["tenure"] + random.gauss(0, 1.5)
    remaining = dict(LEVELS)
    for code, hc, _ol, _to, _i, _o in TARGET_DEPT:
        members = sorted([e for e in active if e["dept"] == code], key=lambda x: -x["score"])
        nvp = 3 if code == "D01" else 1
        for e in members[:nvp]:
            e["level"] = "VP"
            remaining["VP"] -= 1
        if hc >= 18:
            members[nvp]["level"] = "Director"
            remaining["Director"] -= 1
    assert remaining["VP"] == 0
    rest = sorted([e for e in active if "level" not in e], key=lambda x: -x["score"])
    idx = 0
    for lv in reversed(LEVEL_ORDER):
        for _ in range(remaining[lv]):
            rest[idx]["level"] = lv
            idx += 1
    assert idx == len(rest)

    # 계약종료일(계약직·인턴·파견): 90일 내 만료 ≥ 10 보장, 3명은 누락(missing-required, 미해결)
    contract = [e for e in active if e["empType"] in CONTRACT_TYPES]
    for e in contract:
        if e["future"]:
            e["contractEnd"] = e["hire"] + days(random.randint(120, 365))
        elif e["empType"] == "인턴":
            e["contractEnd"] = as_of + days(random.randint(7, 200))
        else:
            e["contractEnd"] = as_of + days(random.randint(10, 540))
    random.shuffle(contract)
    for e in contract[:10]:
        if not e["future"]:
            e["contractEnd"] = as_of + days(random.randint(5, 85))
    missing = [e for e in contract[10:] if e["empType"] in ("계약직", "인턴") and not e["future"]][:3]
    for e in missing:
        e["contractEnd"] = None
        e["missingEnd"] = True
    return active


def build_on_leave(as_of):
    on_leave = []
    for code, _hc, ol, _to, _i, _o in TARGET_DEPT:
        for _ in range(ol):
            on_leave.append({"dept": code, "jobFamily": JOB_FAMILY_OF_DEPT[code], "status": "휴직",
                             "future": False, "contractEnd": None, "missingEnd": False})
    types = expand(EMP_TYPE_LEAVE)
    random.shuffle(types)
    leave_types = expand(LEAVE_TYPES)
    random.shuffle(leave_types)
    for e, t, lt in zip(on_leave, types, leave_types):
        e["empType"] = t
        e["leaveType"] = lt
        e["tenure"] = random.uniform(1.2, 7.0)
        e["hire"] = as_of - days(int(round(e["tenure"] * 365.25)))
        e["tenure"] = tenure_years(e["hire"], as_of)
        e["tenureBand"] = tenure_band(e["tenure"])
        e["prior"] = random.randint(0, 120)
        e["totalExp"] = total_exp(e["prior"], e["tenure"])
        e["totalBand"] = total_band(e["totalExp"])
        e["age"] = random.randint(max(26, 20 + int(math.ceil(e["totalExp"]))), 45)
        e["birth"] = birth_for_age(e["age"], as_of)
        e["ageBand"] = age_band(e["age"])
        e["gender"] = random.choice(["여성", "여성", "남성", "미응답"])
        e["level"] = random.choice(["IC2", "IC3", "Senior", "Lead", "Manager"])
        lo = max(e["hire"] + days(90), as_of - days(365))
        e["leaveStart"] = rand_date(lo, as_of - days(7))
        if t == "계약직":
            e["contractEnd"] = as_of + days(random.randint(30, 400))
    return on_leave


def finalize_population(active, on_leave, as_of):
    everyone = active + on_leave
    # 사번: 입사 순서 ± 45일 노이즈
    everyone.sort(key=lambda e: (e["hire"].toordinal() + random.randint(-45, 45), random.random()))
    names = NamePool()
    for i, e in enumerate(everyone):
        e["id"] = "E%04d" % (i + 1)
        e["name"] = names.next()
        lo = max(e["hire"], as_of - days(400))
        if lo > as_of:
            lo = as_of - days(5)
        e["modified"] = rand_date(lo, as_of)
    everyone.sort(key=lambda e: e["id"])
    # 스테이지 경계: 재직 406 입사일 순위(49/151/140/66). 경계 순위에서 같은 날짜가 겹치지 않게 조정
    cuts = [49, 200, 340]
    while True:
        ranked = sorted(active, key=lambda e: (e["hire"], e["id"]))
        changed = False
        for c in cuts:
            if ranked[c - 1]["hire"] == ranked[c]["hire"]:
                ranked[c]["hire"] += days(1)
                changed = True
        if not changed:
            break
    for e in active:
        e["tenure"] = tenure_years(e["hire"], as_of)
        e["totalExp"] = total_exp(e["prior"], e["tenure"])
        assert tenure_band(e["tenure"]) == e["tenureBand"]
        assert total_band(e["totalExp"]) == e["totalBand"]
    stages = [{"stage": "Seed", "from": iso(COMPANY_START), "to": iso(ranked[48]["hire"])},
              {"stage": "Series A", "from": iso(ranked[48]["hire"] + days(1)), "to": iso(ranked[199]["hire"])},
              {"stage": "Scale-up", "from": iso(ranked[199]["hire"] + days(1)), "to": iso(ranked[339]["hire"])},
              {"stage": "Enterprise", "from": iso(ranked[339]["hire"] + days(1)), "to": "9999-12-31"}]
    for e in everyone:
        e["stage"] = stage_of(iso(e["hire"]), stages)
    return everyone, names, stages


def choose_leavers(active, as_of):
    """§2-4: 월말까지 유효 14(조직별 out, 사유 5/3/2/2/2, 1명 stale) + 다음 달 4."""
    me = month_end(as_of)
    nm_first, nm_last = next_month_range(as_of)
    excluded = set(id(e) for e in active if e["future"] or e["missingEnd"])
    slots = []
    for code, _hc, _ol, _to, _i, out in TARGET_DEPT:
        slots.extend([code] * out)
    chosen = set()
    leavers = []
    # 계약만료 3: 계약직/인턴/파견 재직자가 있는 조직 슬롯에 배정(서로 다른 조직 우선)
    contract_by_dept = {}
    for e in active:
        if e["empType"] in CONTRACT_TYPES and id(e) not in excluded:
            contract_by_dept.setdefault(e["dept"], []).append(e)
    slot_depts = sorted(set(slots), key=lambda c: -len(contract_by_dept.get(c, [])))
    for code in slot_depts[:3]:
        e = random.choice(contract_by_dept[code])
        chosen.add(id(e))
        slots.remove(code)
        d = me if random.random() < 0.6 else rand_date(as_of + days(1), me)
        e["contractEnd"] = d
        leavers.append({"emp": e, "date": d, "reason": "계약만료", "stale": False, "month": "current"})
    reasons = expand([(r, n) for r, n in LEAVER_REASONS if r != "계약만료"])
    random.shuffle(reasons)
    for code, reason in zip(slots, reasons):
        cands = [e for e in active if e["dept"] == code and id(e) not in chosen and id(e) not in excluded]
        e = random.choice(cands)
        chosen.add(id(e))
        d = me if random.random() < 0.6 else rand_date(as_of + days(1), me)
        leavers.append({"emp": e, "date": d, "reason": reason, "stale": False, "month": "current"})
    stale = random.choice([l for l in leavers if l["reason"] != "계약만료"])
    stale["stale"] = True
    stale["date"] = as_of - days(8)
    for (code, n), reason in zip(OCT_LEAVERS, OCT_LEAVER_REASONS):
        for _ in range(n):
            cands = [e for e in active if e["dept"] == code and id(e) not in chosen and id(e) not in excluded
                     and e["empType"] == "정규직"]
            e = random.choice(cands)
            chosen.add(id(e))
            leavers.append({"emp": e, "date": rand_date(nm_first, nm_last), "reason": reason, "stale": False,
                            "month": "next"})
    random.shuffle(leavers)
    return leavers


def build_joiners(as_of, names):
    me = month_end(as_of)
    nm_first, nm_last = next_month_range(as_of)
    joiners = []

    def make(code, lo, hi, month):
        fam = JOB_FAMILY_OF_DEPT[code]
        if code == "D05":
            fam = random.choice(["Data/AI", "Data/AI", "Engineering"])
        emp_type = random.choice(["정규직"] * 6 + ["계약직", "인턴"])
        level = random.choice(["IC1", "IC2", "IC2", "IC3", "Senior", "Lead"])
        prior = {"IC1": (0, 18), "IC2": (12, 48), "IC3": (36, 84), "Senior": (72, 150), "Lead": (96, 180)}[level]
        prior_m = random.randint(*prior)
        age = random.randint(max(24, 21 + prior_m // 12), 26 + prior_m // 12 + 6)
        return {"name": names.next(), "dept": code, "jobFamily": fam, "level": level, "empType": emp_type,
                "gender": random.choice(["여성", "남성", "남성", "여성", "미응답"]), "birth": birth_for_age(age, as_of),
                "date": rand_date(lo, hi), "prior": prior_m, "month": month}

    for code, _hc, _ol, _to, inn, _o in TARGET_DEPT:
        for _ in range(inn):
            joiners.append(make(code, as_of + days(1), me, "current"))
    for code, n in OCT_JOINERS:
        for _ in range(n):
            joiners.append(make(code, nm_first, nm_last, "next"))
    random.shuffle(joiners)
    return joiners


# ---------------------------------------------------------------------------
# 원천 렌더링 + 결함 주입
# ---------------------------------------------------------------------------
class DefectLog(object):
    def __init__(self):
        self.defects = []
        self.used = set()

    def free(self, source, idx, field):
        return (source, idx, field) not in self.used

    def add(self, source, emp_id, idx, field, dtype, raw, true, assigned=None):
        key = (source, idx, field)
        assert key not in self.used, key
        self.used.add(key)
        d = {"source": source, "rowRef": {"사번": emp_id, "rowIndex": idx}, "field": field, "defectType": dtype,
             "rawValue": raw, "trueValue": true}
        if assigned is not None:
            d["assignedValue"] = assigned
        self.defects.append(d)

    def summary(self):
        return counter(d["defectType"] for d in self.defects)

    def by_source(self):
        out = {}
        for d in self.defects:
            out.setdefault(d["source"], {})
            out[d["source"]][d["defectType"]] = out[d["source"]].get(d["defectType"], 0) + 1
        return out


def master_row(e):
    return [e["id"], e["name"], e["gender"], iso(e["birth"]), DEPT_NAME[e["dept"]], e["jobFamily"], e["level"],
            e["empType"], e["status"], e["leaveType"], iso(e.get("leaveStart")), iso(e["hire"]),
            iso(e["contractEnd"]), str(e["prior"]), iso(e["modified"])]


H = dict((h, i) for i, h in enumerate(MASTER_HEADER))


def pick(cands, k, label):
    if len(cands) < k:
        raise RuntimeError("후보 부족: %s (필요 %d, 보유 %d)" % (label, k, len(cands)))
    return random.sample(cands, k)


def build_master(everyone, log):
    """435행(정답 427 + 중복 8)을 만들고 §2-5 결함을 주입한다. 반환: rows(list[list[str]])."""
    src = "headcount-master"
    # 중복 8: 구버전 행(옛 소속명 5, 옛 레벨 3), 최종수정일 더 오래됨
    dup_cands = [e for e in everyone if not e["future"] and e["tenure"] >= 1.5 and (e["modified"] - e["hire"]).days >= 40]
    dups = pick(dup_cands, 8, "duplicate")
    entries = [("true", e, None) for e in everyone]
    for k, e in enumerate(dups):
        old = master_row(e)
        if k < 5:
            old[H["소속"]] = FORMER[e["dept"]][0]
        else:
            li = LEVEL_ORDER.index(e["level"])
            old[H["레벨"]] = LEVEL_ORDER[max(0, li - 1)] if li > 0 else "IC2"
        old_mod = max(e["hire"], e["modified"] - days(random.randint(90, 600)))
        if old_mod >= e["modified"]:
            old_mod = e["modified"] - days(1)
        old[H["최종수정일"]] = iso(old_mod)
        pos = [i for i, en in enumerate(entries) if en[1] is e][0]
        at = pos if k < 5 else random.randrange(len(entries) + 1)
        entries.insert(at, ("dup", e, old))
    rows = []
    idx_of = {}
    for i, (kind, e, old) in enumerate(entries):
        if kind == "true":
            rows.append(master_row(e))
            idx_of[e["id"]] = i
        else:
            rows.append(old)
    for kind, e, old in entries:
        if kind == "dup":
            i = rows.index(old)
            log.add(src, e["id"], i, "사번", "duplicate", old[H["최종수정일"]], idx_of[e["id"]])

    def ri(e):
        return idx_of[e["id"]]

    def setv(e, field, value):
        rows[ri(e)][H[field]] = value

    active = [e for e in everyone if e["status"] == "재직"]
    on_leave = [e for e in everyone if e["status"] == "휴직"]
    org_used = set()

    def org_cands(code, extra=None):
        return [e for e in everyone if e["dept"] == code and e["id"] not in org_used and (extra is None or extra(e))]

    def org_defect(e, dtype, raw, true=None, assigned=None):
        org_used.add(e["id"])
        setv(e, "소속", raw)
        log.add(src, e["id"], ri(e), "소속", dtype, raw, true if true is not None else e["dept"], assigned)

    # org-old-name 6
    for code, raw in [("D09", "HR"), ("D03", "R&D"), ("D08", "Customer Support"), ("D04", "UX"), ("D05", "AI Lab"), ("D06", "BizDev")]:
        org_defect(random.choice(org_cands(code)), "org-old-name", raw)
    # org-variant 4
    for code, raw in [("D11", "Legal and Compliance"), ("D11", "Legal&Compliance"), ("D05", "Data and AI"), ("D08", "Customer success")]:
        org_defect(random.choice(org_cands(code)), "org-variant", raw)
    # org-typo 3
    for code, raw in [("D03", "Enginering"), ("D07", "Marketting"), ("D10", "Finanace")]:
        org_defect(random.choice(org_cands(code)), "org-typo", raw)
    # org-whitespace 4 (앞·뒤·중간·전각)
    for code, raw in [("D03", " Engineering"), ("D06", "Sales "), ("D08", "Customer  Success"), ("D05", "Data　&　AI")]:
        org_defect(random.choice(org_cands(code)), "org-whitespace", raw)
    # org-unknown 2 → 직군 기본 매핑으로 임시 배정(정답 조직 = 임시 배정 조직이라 집계 불변)
    for code, raw in [("D07", "Growth Lab"), ("D03", "Platform")]:
        e = random.choice(org_cands(code, lambda x: x["status"] == "재직" and x["jobFamily"] == JOB_FAMILY_OF_DEPT[code]))
        org_defect(e, "org-unknown", raw, "(unresolved)", code)

    # hire-date-format 31 (slash 20 · dot 6 · compact 3 · excel 2)
    hd_cands = [e for e in everyone if not e["future"]]
    kinds = ["slash"] * 20 + ["dot"] * 6 + ["compact"] * 3 + ["excel"] * 2
    for e, kind in zip(pick(hd_cands, 31, "hire-date-format"), kinds):
        raw = date_variant(e["hire"], kind)
        setv(e, "입사일", raw)
        log.add(src, e["id"], ri(e), "입사일", "hire-date-format", raw, iso(e["hire"]))
    # date-logic 2
    for e in [x for x in active if x["future"]]:
        log.add(src, e["id"], ri(e), "입사일", "date-logic", iso(e["hire"]), "(unresolved)", iso(e["hire"]))
    # date-format 6: 휴직시작일 3 + 계약종료일 3
    for e, kind in zip(pick(on_leave, 3, "date-format/leave"), ["slash", "dot", "short-dot"]):
        raw = date_variant(e["leaveStart"], kind)
        setv(e, "휴직시작일", raw)
        log.add(src, e["id"], ri(e), "휴직시작일", "date-format", raw, iso(e["leaveStart"]))
    ce_cands = [e for e in everyone if e["contractEnd"]]
    for e, kind in zip(pick(ce_cands, 3, "date-format/contract"), ["slash", "compact", "korean"]):
        raw = date_variant(e["contractEnd"], kind)
        setv(e, "계약종료일", raw)
        log.add(src, e["id"], ri(e), "계약종료일", "date-format", raw, iso(e["contractEnd"]))
    # status-inconsistency 3: 휴직인데 휴직유형 빈값 (정답 기타)
    for e in pick([e for e in on_leave if e["leaveType"] == "기타"], 3, "status-inconsistency"):
        setv(e, "휴직유형", "")
        log.add(src, e["id"], ri(e), "휴직유형", "status-inconsistency", "", "(unresolved)", "기타")
    # missing-required 3
    for e in [x for x in everyone if x["missingEnd"]]:
        log.add(src, e["id"], ri(e), "계약종료일", "missing-required", "", "(unresolved)", "")

    # code-variant 32
    def code_defects(field, key, pairs, filt=None):
        used = set()
        for raw, true in pairs:
            cands = [e for e in everyone if e[key] == true and e["id"] not in used and (filt is None or filt(e))]
            e = random.choice(cands)
            used.add(e["id"])
            setv(e, field, raw)
            log.add(src, e["id"], ri(e), field, "code-variant", raw, true)

    code_defects("성별", "gender", [("F", "여성"), ("M", "남성"), ("female", "여성"), ("male", "남성"), ("여", "여성"),
                                  ("남", "남성"), ("", "미응답"), ("", "미응답")])
    code_defects("고용유형", "empType", [("정규", "정규직"), ("Regular", "정규직"), ("FT", "정규직"), ("계약", "계약직"),
                                       ("Contract", "계약직"), ("Intern", "인턴"), ("Dispatch", "파견"), ("정규", "정규직"),
                                       ("계약", "계약직")])
    code_defects("재직상태", "status", [("재직중", "재직"), ("Active", "재직"), ("휴직중", "휴직"), ("Leave", "휴직"),
                                      ("재직중", "재직"), ("Active", "재직"), ("Leave", "휴직"), ("재직중", "재직")])
    code_defects("레벨", "level", [("ic1", "IC1"), ("IC-2", "IC2"), ("Sr", "Senior"), ("Mgr", "Manager"), ("Dir", "Director"),
                                 ("ic1", "IC1"), ("Sr", "Senior")])
    return rows


def build_to_plan(as_of, log):
    src = "to-plan"
    month = "%04d-%02d" % (as_of.year, as_of.month)
    variants = {"D11": "Legal and Compliance", "D05": "Data and AI", "D08": "Customer success"}
    month_variants = ["%04d.%02d" % (as_of.year, as_of.month), "%04d.%02d" % (as_of.year, as_of.month),
                      "%04d%02d" % (as_of.year, as_of.month), "%d년 %d월" % (as_of.year, as_of.month)]
    month_rows = random.sample(range(len(TARGET_DEPT)), 4)
    rows = []
    for i, (code, _hc, _ol, to, _i, _o) in enumerate(TARGET_DEPT):
        name = DEPT_NAME[code]
        m = month
        if code in variants:
            name = variants[code]
            log.add(src, "", i, "조직", "org-variant", name, code)
        if i in month_rows:
            m = month_variants[month_rows.index(i)]
            log.add(src, "", i, "기준월", "date-format", m, month)
        rows.append([name, str(to), m])
    return rows


def build_joiner_rows(joiners, log):
    src = "planned-joiners"
    rows = []
    for j in joiners:
        rows.append([j["name"], DEPT_NAME[j["dept"]], j["jobFamily"], j["level"], j["empType"], j["gender"],
                     iso(j["birth"]), iso(j["date"]), str(j["prior"])])
    d05 = [i for i, j in enumerate(joiners) if j["dept"] == "D05"]
    d08 = [i for i, j in enumerate(joiners) if j["dept"] == "D08"]
    for i, raw in [(random.choice(d05), "Data and AI"), (random.choice(d08), "Customer success")]:
        rows[i][1] = raw
        log.add(src, "", i, "소속", "org-variant", raw, joiners[i]["dept"])
    for i, kind in zip(random.sample(range(len(joiners)), 3), ["slash", "dot", "compact"]):
        raw = date_variant(joiners[i]["date"], kind)
        rows[i][7] = raw
        log.add(src, "", i, "입사예정일", "date-format", raw, iso(joiners[i]["date"]))
    fem = [i for i, j in enumerate(joiners) if j["gender"] == "여성"]
    i = random.choice(fem)
    rows[i][5] = "F"
    log.add(src, "", i, "성별", "code-variant", "F", "여성")
    return rows


FREETEXT = {"자발퇴사": ["자발적 퇴사", "자발적 이직"], "계약만료": ["계약 기간 만료"], "조직개편": ["조직 개편에 따른"],
            "성과/적합도": ["성과 부진"], "개인사유": ["개인 사정"]}


def build_leaver_rows(leavers, as_of, names, log):
    src = "planned-leavers"
    me = month_end(as_of)
    unknown = {"emp": {"id": "E9999", "name": names.next(), "dept": "D06"}, "date": me, "reason": "개인사유",
               "stale": False, "month": "current", "unknown": True}
    all_rows = list(leavers) + [unknown]
    random.shuffle(all_rows)
    rows = []
    for l in all_rows:
        rows.append([l["emp"]["id"], l["emp"]["name"], DEPT_NAME[l["emp"]["dept"]], iso(l["date"]), l["reason"]])
    for i, l in enumerate(all_rows):
        if l.get("unknown"):
            log.add(src, l["emp"]["id"], i, "사번", "unknown-emp", l["emp"]["id"], "(unresolved)", "")
        if l["stale"]:
            log.add(src, l["emp"]["id"], i, "퇴사예정일", "stale-planned-leaver", iso(l["date"]), "(unresolved)", iso(l["date"]))
    real = [i for i, l in enumerate(all_rows) if not l.get("unknown") and not l["stale"]]
    for i, kind in zip(random.sample(real, 2), ["slash", "dot"]):
        raw = date_variant(all_rows[i]["date"], kind)
        rows[i][3] = raw
        log.add(src, all_rows[i]["emp"]["id"], i, "퇴사예정일", "date-format", raw, iso(all_rows[i]["date"]))
    # reason-freetext 6: 자발 2 · 계약 1 · 조직 1 · 성과 1 · 개인 1
    need = [("자발퇴사", 2), ("계약만료", 1), ("조직개편", 1), ("성과/적합도", 1), ("개인사유", 1)]
    for reason, n in need:
        cands = [i for i, l in enumerate(all_rows) if l["reason"] == reason and not l.get("unknown")]
        for k, i in enumerate(random.sample(cands, n)):
            raw = FREETEXT[reason][k % len(FREETEXT[reason])]
            rows[i][4] = raw
            log.add(src, all_rows[i]["emp"]["id"], i, "퇴직사유", "reason-freetext", raw, reason)
    return rows


# ---------------------------------------------------------------------------
# 파일 I/O
# ---------------------------------------------------------------------------
def write_csv(path, header, rows, bom=True):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8-sig" if bom else "utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(header)
        for r in rows:
            w.writerow(r)


def read_csv(path):
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
        f.write("\n")


# ---------------------------------------------------------------------------
# 생성 본체
# ---------------------------------------------------------------------------
def generate(root, as_of, bom=True):
    random.seed(SEED)
    active = build_active(as_of)
    on_leave = build_on_leave(as_of)
    everyone, names, stages = finalize_population(active, on_leave, as_of)
    leavers = choose_leavers(active, as_of)
    joiners = build_joiners(as_of, names)

    log = DefectLog()
    master_rows = build_master(everyone, log)
    to_rows = build_to_plan(as_of, log)
    joiner_rows = build_joiner_rows(joiners, log)
    leaver_rows = build_leaver_rows(leavers, as_of, names, log)

    p = dict((k, os.path.join(root, v)) for k, v in PATHS.items())
    write_csv(p["org-chart"], ORG_HEADER, [list(r) for r in ORG_CHART], bom)
    write_json(p["company-stages"], {"asOfDate": iso(as_of), "basis": "재직 406명의 입사일 순위 Seed 49 / Series A 151 / Scale-up 140 / Enterprise 66",
                                     "stages": stages})
    write_csv(p["headcount-master"], MASTER_HEADER, master_rows, bom)
    write_csv(p["to-plan"], TO_HEADER, to_rows, bom)
    write_csv(p["planned-joiners"], JOINER_HEADER, joiner_rows, bom)
    write_csv(p["planned-leavers"], LEAVER_HEADER, leaver_rows, bom)
    write_json(p["injected-defects"], {"seed": SEED, "generatedAt": iso(as_of), "client": CLIENT,
                                       "summary": log.summary(), "bySource": log.by_source(),
                                       "total": len(log.defects), "defects": log.defects})
    return {"rows": {"headcount-master": len(master_rows), "to-plan": len(to_rows), "planned-joiners": len(joiner_rows),
                     "planned-leavers": len(leaver_rows), "org-chart": len(ORG_CHART)},
            "defectSummary": log.summary(), "defectsBySource": log.by_source(), "stages": stages}


# ---------------------------------------------------------------------------
# self-check: 파일을 다시 읽어 정답지로 복원 → §2-7 대조
# ---------------------------------------------------------------------------
def restore(rows, defects, source):
    by_ref = {}
    removed = set()
    for d in defects:
        if d["source"] != source:
            continue
        if d["defectType"] == "duplicate":
            removed.add(d["rowRef"]["rowIndex"])
            continue
        by_ref[(d["rowRef"]["rowIndex"], d["field"])] = d
    out = []
    for i, row in enumerate(rows):
        if i in removed:
            continue
        r = dict(row)
        r["_rowIndex"] = i
        for field in list(row.keys()):
            d = by_ref.get((i, field))
            if d is None:
                continue
            if d["trueValue"] == "(unresolved)":
                r[field] = d.get("assignedValue", r[field])
            else:
                r[field] = str(d["trueValue"])
        if source in ("headcount-master", "planned-joiners", "planned-leavers") and r.get("소속") in NAME_TO_CODE:
            r["소속"] = NAME_TO_CODE[r["소속"]]
        if source == "to-plan" and r.get("조직") in NAME_TO_CODE:
            r["조직"] = NAME_TO_CODE[r["조직"]]
        out.append(r)
    return out


def self_check(root, as_of):
    p = dict((k, os.path.join(root, v)) for k, v in PATHS.items())
    failed = []
    checks = [0]

    def check(cond, msg):
        checks[0] += 1
        if not cond:
            failed.append(msg)

    def eq(actual, expected, label):
        check(actual == expected, "%s: 기대 %s, 실제 %s" % (label, expected, actual))

    with open(p["injected-defects"], encoding="utf-8") as f:
        inj = json.load(f)
    defects = inj["defects"]
    # 복원 과정이 손상된 원천을 정답지 값으로 가리지 않도록 먼저 연결을 검증한다.
    raw_sources = {s: read_csv(p[s]) for s in EXPECTED_DEFECTS}
    observed_by_source = {}
    refs = set()
    for defect in defects:
        source = defect["source"]
        index = defect["rowRef"]["rowIndex"]
        field = defect["field"]
        ref = (source, index, field)
        check(ref not in refs, "중복 결함 참조: %s" % (ref,))
        refs.add(ref)
        row = raw_sources[source][index]
        # duplicate의 rawValue는 기존 계약상 구버전의 최종수정일이다.
        raw_field = "최종수정일" if defect["defectType"] == "duplicate" else field
        eq(row[raw_field], defect["rawValue"], "결함 원천값 %s" % (ref,))
        if source in ("headcount-master", "planned-leavers"):
            eq(row["사번"], defect["rowRef"]["사번"], "결함 사번 %s" % (ref,))
        counts = observed_by_source.setdefault(source, {})
        kind = defect["defectType"]
        counts[kind] = counts.get(kind, 0) + 1
    eq(inj["total"], len(defects), "결함 total")
    eq(inj["summary"], counter(d["defectType"] for d in defects), "결함 summary")
    eq(inj["bySource"], observed_by_source, "결함 bySource")
    eq(inj["generatedAt"], iso(as_of), "정답지 기준일")
    with open(p["company-stages"], encoding="utf-8") as f:
        stages = json.load(f)["stages"]
    raw_master = read_csv(p["headcount-master"])
    eq(len(raw_master), 435, "원천 마스터 행 수")
    master = restore(raw_master, defects, "headcount-master")
    eq(len(master), 427, "정답 마스터 행 수")
    eq(len(set(r["사번"] for r in master)), 427, "사번 유일성")
    check(all(r["소속"] in DEPT_CODES for r in master), "복원 후 소속이 deptCode가 아닌 행 존재")
    for field in ("생년월일", "입사일", "최종수정일"):
        check(all(dt.date.fromisoformat(r[field]) for r in master), "복원 후 %s ISO 아님" % field)

    active = [r for r in master if r["재직상태"] == "재직"]
    on_leave = [r for r in master if r["재직상태"] == "휴직"]
    eq(len(active), 406, "재직")
    eq(len(on_leave), 21, "휴직")
    for code, hc, ol, _to, _i, _o in TARGET_DEPT:
        eq(sum(1 for r in active if r["소속"] == code), hc, "%s 재직" % code)
        eq(sum(1 for r in on_leave if r["소속"] == code), ol, "%s 휴직" % code)
    eq(counter(r["고용유형"] for r in master), dict(EMP_TYPE_ALL), "고용유형(427)")
    eq(counter(r["고용유형"] for r in on_leave), dict(EMP_TYPE_LEAVE), "휴직자 고용유형")
    eq(counter(r["성별"] for r in active), dict(GENDER), "성별(406)")
    eq(counter(age_band(age_on(dt.date.fromisoformat(r["생년월일"]), as_of)) for r in active), dict(AGE_BAND), "연령대(406)")
    fam_expected = {"Engineering": 116, "Product": 55, "Design": 25, "Sales": 58, "Marketing": 30, "Customer Success": 40,
                    "People": 18, "Finance": 19, "Legal": 11, "Data/AI": 24, "Executive": 10}
    eq(counter(r["직군"] for r in active), fam_expected, "직군(406)")
    eq(counter(r["직군"] for r in active if r["소속"] == "D05"), dict(D05_FAMILIES), "Data & AI 직군 구성")
    for code, hc, _ol, _to, _i, _o in TARGET_DEPT:
        members = [r for r in active if r["소속"] == code]
        if code != "D05":
            check(all(r["직군"] == JOB_FAMILY_OF_DEPT[code] for r in members), "%s 직군 100%% 아님" % code)
        vps = sum(1 for r in members if r["레벨"] == "VP")
        check(vps == (3 if code == "D01" else 1) if code == "D01" else vps >= 1, "%s VP 수 %d" % (code, vps))
        if hc >= 18:
            check(any(r["레벨"] == "Director" for r in members), "%s Director 없음" % code)
    eq(counter(r["레벨"] for r in active), dict(LEVELS), "레벨(406)")
    tenures = [tenure_years(dt.date.fromisoformat(r["입사일"]), as_of) for r in active]
    eq(counter(tenure_band(t) for t in tenures), dict(TENURE_BAND), "재직기간 구간(406)")
    totals = [total_exp(int(r["입사전경력(개월)"]), t) for r, t in zip(active, tenures)]
    eq(counter(total_band(x) for x in totals), dict(TOTAL_BAND), "총경력 구간(406)")
    eq(counter(stage_of(r["입사일"], stages) for r in active), dict(STAGE), "스테이지(406)")
    # 레벨 ↔ 재직기간 양의 상관 (피어슨)
    ranks = [LEVEL_ORDER.index(r["레벨"]) for r in active]
    n = len(ranks)
    mx, my = sum(ranks) / n, sum(tenures) / n
    cov = sum((a - mx) * (b - my) for a, b in zip(ranks, tenures))
    vx = math.sqrt(sum((a - mx) ** 2 for a in ranks)) * math.sqrt(sum((b - my) ** 2 for b in tenures))
    corr = cov / vx if vx else 0.0
    check(corr > 0.3, "레벨-재직기간 상관 %.3f ≤ 0.3" % corr)
    # 계약종료일: 정규직 빈값, 90일 내 만료 ≥ 8
    check(all(r["계약종료일"] == "" for r in master if r["고용유형"] == "정규직"), "정규직에 계약종료일 존재")
    win = [r for r in master if r["계약종료일"] and as_of <= dt.date.fromisoformat(r["계약종료일"]) <= as_of + days(90)]
    check(len(win) >= 8, "90일 내 계약 만료 %d < 8" % len(win))
    # 미해결 유형 존재
    future = [r for r in active if dt.date.fromisoformat(r["입사일"]) > as_of]
    eq(len(future), 2, "date-logic 행 수")

    # to-plan
    to_rows = restore(read_csv(p["to-plan"]), defects, "to-plan")
    eq(len(to_rows), 11, "TO 행 수")
    eq(dict((r["조직"], int(r["정원"])) for r in to_rows), dict((c, t) for c, _h, _o, t, _i, _x in TARGET_DEPT), "조직별 TO")
    eq(sum(int(r["정원"]) for r in to_rows), 422, "TO 합계")
    check(all(r["기준월"] == "%04d-%02d" % (as_of.year, as_of.month) for r in to_rows), "복원 후 기준월 비정규")

    # joiners
    me = month_end(as_of)
    nm_first, nm_last = next_month_range(as_of)
    jr = restore(read_csv(p["planned-joiners"]), defects, "planned-joiners")
    eq(len(jr), 27, "입사 예정 행 수")
    jdates = [dt.date.fromisoformat(r["입사예정일"]) for r in jr]
    cur = [r for r, d in zip(jr, jdates) if as_of < d <= me]
    nxt = [r for r, d in zip(jr, jdates) if nm_first <= d <= nm_last]
    eq(len(cur), 19, "월말까지 입사 예정")
    eq(len(nxt), 8, "다음 달 입사 예정")
    eq(counter(r["소속"] for r in cur), dict((c, i) for c, _h, _o, _t, i, _x in TARGET_DEPT if i), "조직별 in")
    eq(counter(r["소속"] for r in nxt), dict(OCT_JOINERS), "다음 달 조직별 in")
    check(all(r["성별"] in ("여성", "남성", "미응답") for r in jr), "입사 예정자 성별 비정규")

    # leavers
    lr = restore(read_csv(p["planned-leavers"]), defects, "planned-leavers")
    eq(len(lr), 19, "퇴사 예정 행 수")
    ids = dict((r["사번"], r) for r in master)
    unknown = [r for r in lr if r["사번"] not in ids]
    eq(len(unknown), 1, "unknown-emp 행 수")
    known = [r for r in lr if r["사번"] in ids]
    ldates = [dt.date.fromisoformat(r["퇴사예정일"]) for r in known]
    valid = [r for r, d in zip(known, ldates) if d <= me]
    octo = [r for r, d in zip(known, ldates) if nm_first <= d <= nm_last]
    eq(len(valid), 14, "월말까지 퇴사 예정(유효)")
    eq(len(octo), 4, "다음 달 퇴사 예정")
    eq(sum(1 for r, d in zip(known, ldates) if d < as_of), 1, "stale 건수")
    eq(counter(ids[r["사번"]]["소속"] for r in valid), dict((c, o) for c, _h, _l, _t, _i, o in TARGET_DEPT if o), "조직별 out")
    eq(counter(ids[r["사번"]]["소속"] for r in octo), dict(OCT_LEAVERS), "다음 달 조직별 out")
    eq(counter(r["퇴직사유"] for r in valid), dict(LEAVER_REASONS), "퇴직사유(14)")
    check(all(ids[r["사번"]]["고용유형"] in CONTRACT_TYPES for r in valid if r["퇴직사유"] == "계약만료"), "계약만료가 정규직에 배정")
    check(all(ids[r["사번"]]["재직상태"] == "재직" for r in known), "퇴사 예정자가 휴직자")

    # 결함 건수
    for source, expected in EXPECTED_DEFECTS.items():
        actual = inj["bySource"].get(source, {})
        for k, v in expected.items():
            eq(actual.get(k, 0), v, "결함 %s/%s" % (source, k))
    # 해결된 조직명 보정 17건과 미해결 조직명 2건은 별도 집계한다.
    org_total = sum(inj["bySource"]["headcount-master"].get(k, 0) for k in ("org-old-name", "org-variant", "org-typo", "org-whitespace"))
    eq(org_total, 17, "마스터 org-* 보정 합계(미해결 org-unknown 제외)")
    eq(inj["bySource"]["headcount-master"].get("org-unknown", 0), 2, "org-unknown")
    check(inj["bySource"]["headcount-master"].get("code-variant", 0) >= 30, "code-variant < 30")
    hd = [d for d in defects if d["defectType"] == "hire-date-format"]
    eq(len(hd), 31, "hire-date-format")
    excel = [d for d in hd if d["rawValue"].isdigit() and len(d["rawValue"]) == 5]
    eq(len(excel), 2, "Excel 일련번호")

    aggregates = {
        "byDepartment": dict((c, {"HC": sum(1 for r in active if r["소속"] == c), "OL": sum(1 for r in on_leave if r["소속"] == c)}) for c in DEPT_CODES),
        "byOrgGroup": counter(dict((r[2], r[1]) for r in ORG_CHART)[r["소속"]] for r in active),
        "employmentType427": counter(r["고용유형"] for r in master),
        "gender": counter(r["성별"] for r in active),
        "ageBand": counter(age_band(age_on(dt.date.fromisoformat(r["생년월일"]), as_of)) for r in active),
        "jobFamily": counter(r["직군"] for r in active),
        "level": counter(r["레벨"] for r in active),
        "tenureBand": counter(tenure_band(t) for t in tenures),
        "totalExperienceBand": counter(total_band(x) for x in totals),
        "stage": counter(stage_of(r["입사일"], stages) for r in active),
        "levelTenureCorrelation": round(corr, 3),
        "contractEndWithin90Days": len(win),
        "plannedIn": len(cur), "plannedOut": len(valid), "reasons": counter(r["퇴직사유"] for r in valid),
    }
    return {"passed": not failed, "checks": checks[0], "failed": failed, "aggregates": aggregates}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Zero Company HR 가상 원천 생성기 v2 (DATA_CONTRACT §1·§2)")
    parser.add_argument("--root", default=DEFAULT_ROOT)
    parser.add_argument("--as-of", default=DEFAULT_AS_OF)
    parser.add_argument("--self-check", action="store_true", help="생성 후 파일을 다시 읽어 §2-7 전 수치와 대조")
    parser.add_argument("--check-only", action="store_true", help="기존 산출물을 변경하지 않고 self-check만 수행")
    parser.add_argument("--no-bom", action="store_true", help="CSV를 BOM 없는 UTF-8로 생성")
    args = parser.parse_args(argv)
    started = time.time()
    result = {"status": "ok", "mode": "synthetic-sources", "asOfDate": args.as_of, "client": CLIENT, "seed": SEED,
              "root": args.root, "artifacts": list(PATHS.values())}
    try:
        as_of = dt.date.fromisoformat(args.as_of)
        if not args.check_only:
            gen = generate(args.root, as_of, bom=not args.no_bom)
            result.update(gen)
        if args.self_check or args.check_only:
            sc = self_check(args.root, as_of)
            result["selfCheck"] = sc
            if not sc["passed"]:
                result["status"] = "self-check-failed"
    except Exception as exc:  # noqa: BLE001
        result["status"] = "error"
        result["errorType"] = type(exc).__name__
        result["error"] = str(exc)
    result["durationSeconds"] = round(time.time() - started, 3)
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["status"] == "ok" else 2


if __name__ == "__main__":
    sys.exit(main())
