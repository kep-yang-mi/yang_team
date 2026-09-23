#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""cleanse.py — Zero Company HR(Everyday People Agent) ② 클린징 (skill: people-data-cleansing)

DATA_CONTRACT v2 §2-8 "결정적 보정 규칙"과 §3 "정제 데이터"를 그대로 구현한다.
  입력 : data/reference/org-chart.csv          §1   조직 그룹(4) > 조직(11). formerNames = 조직 정규화 별칭 사전
         data/reference/company-stages.json   §1   스테이지 경계일 (입사일 → stage 파생)
         data/raw/headcount-master.csv         §2-1 utf-8-sig · 한글 헤더 · 중복(구버전) 행 포함
         data/raw/to-plan.csv                  §2-2
         data/raw/planned-joiners.csv          §2-3
         data/raw/planned-leavers.csv          §2-4
  출력 : data/clean/headcount-master.clean.csv §3-1 1사번 1행 + 파생 필드(ageBand·tenure*·totalExperience*·stage·orgGroup*)
         data/clean/to-plan.clean.csv          §3-2
         data/clean/planned-joiners.clean.csv  §3-3 joinerId J001~
         data/clean/planned-leavers.clean.csv  §3-4
         data/clean/cleansing-log.jsonl        §3-5 원천 필드 단위 1행. rule = §2-5 defectType 어휘(정답지와 기계적 대사)
         data/clean/cleansing-summary.json     §3-6
         _workspace/handoff/02-cleanse.md      §7   핸드오프 로그 — 시작 시 1회 쓰고 종료 시 덮어쓴다 (Operating Rule 2)
  stdout: 마지막 줄에 요약 JSON 1행 — 워크플로우가 파싱하는 반환 데이터

원천은 덮어쓰지 않는다. 정답지(data/raw/injected-defects.json)는 읽지 않는다 — 정답을 보고 고치면 재현율 검사가 무의미해진다.
같은 입력이면 같은 출력(결정적). Python 3.9 표준 라이브러리만(pandas·match·X|Y 없음).
사용법: python3 cleanse.py [--root /Users/yang/development/zero-hr] [--as-of 2026-09-23]
종료 코드: 0 정상(status ok|partial) · 1 오류 · 3 필수 입력 없음
"""

import argparse
import csv
import json
import math
import os
import re
import sys
import time
import traceback
import unicodedata
from datetime import date, datetime, timedelta

# ---------------------------------------------------------------------------
# 상수 — 경로·헤더 (DATA_CONTRACT §0 · §1 · §2 · §3 · §7)
# ---------------------------------------------------------------------------

DEFAULT_ROOT = "/Users/yang/development/zero-hr"
DEFAULT_AS_OF = "2026-09-23"
EXCEL_EPOCH = date(1899, 12, 30)  # Excel 일련번호 기준일 (§2-8)
PHASE = "02-cleanse"
AGENT = "people-data-cleanser"
SCRIPT_REL = ".claude/skills/people-data-cleansing/scripts/cleanse.py"

ORG_CHART_PATH = "data/reference/org-chart.csv"
STAGES_PATH = "data/reference/company-stages.json"
RAW_PATHS = {
    "headcount-master": "data/raw/headcount-master.csv",
    "to-plan": "data/raw/to-plan.csv",
    "planned-joiners": "data/raw/planned-joiners.csv",
    "planned-leavers": "data/raw/planned-leavers.csv",
}
CLEAN_PATHS = {
    "headcount-master": "data/clean/headcount-master.clean.csv",
    "to-plan": "data/clean/to-plan.clean.csv",
    "planned-joiners": "data/clean/planned-joiners.clean.csv",
    "planned-leavers": "data/clean/planned-leavers.clean.csv",
}
LOG_PATH = "data/clean/cleansing-log.jsonl"
SUMMARY_PATH = "data/clean/cleansing-summary.json"
HANDOFF_PATH = "_workspace/handoff/%s.md" % PHASE
SOURCES = ["headcount-master", "to-plan", "planned-joiners", "planned-leavers"]

# §2 원천 헤더 — 필수 컬럼(순서는 검사하지 않고 존재만 검사한다: 고객사 양식은 열이 더 있을 수 있다)
RAW_HEADERS = {
    "headcount-master": ["사번", "성명", "성별", "생년월일", "소속", "직군", "레벨", "고용유형", "재직상태",
                         "휴직유형", "휴직시작일", "입사일", "계약종료일", "입사전경력(개월)", "최종수정일"],
    "to-plan": ["조직", "정원", "기준월"],
    "planned-joiners": ["성명", "소속", "직군", "레벨", "고용유형", "성별", "생년월일", "입사예정일", "입사전경력(개월)"],
    "planned-leavers": ["사번", "성명", "소속", "퇴사예정일", "퇴직사유"],
}
# §3 정제 헤더 — 순서 고정
CLEAN_HEADERS = {
    "headcount-master": ["empId", "name", "gender", "birthDate", "ageBand", "orgGroupCode", "orgGroup", "deptCode",
                         "department", "jobFamily", "level", "stage", "employmentType", "status", "leaveType",
                         "leaveStart", "hireDate", "contractEndDate", "priorExperienceMonths", "tenureYears",
                         "tenureYear", "tenureBand", "totalExperienceYears", "totalExperienceBand",
                         "unresolvedFlags", "sourceRowIndex"],
    "to-plan": ["deptCode", "department", "orgGroupCode", "toHeadcount", "effectiveMonth"],
    "planned-joiners": ["joinerId", "name", "deptCode", "department", "jobFamily", "level", "employmentType",
                        "gender", "birthDate", "plannedHireDate", "priorExperienceMonths", "unresolvedFlags"],
    "planned-leavers": ["empId", "deptCode", "plannedTerminationDate", "separationType", "separationReason",
                        "unresolvedFlags"],
}
ORG_REQUIRED_COLUMNS = ["orgGroupCode", "orgGroup", "deptCode", "department"]
EXPECTED_DEPT_COUNT = 11

# §2-5 defectType 어휘 — 로그의 rule 은 반드시 이 어휘만 쓴다 (정답지 injected-defects.json 과 기계적 대사)
DEFECT_TYPES = ["org-old-name", "org-variant", "org-typo", "org-whitespace", "org-unknown",
                "hire-date-format", "date-format", "date-logic", "status-inconsistency", "missing-required",
                "duplicate", "code-variant", "reason-freetext", "stale-planned-leaver", "unknown-emp"]
ORG_CORRECTION_RULES = ["org-old-name", "org-variant", "org-typo", "org-whitespace"]  # orgNameCorrections(17) 산정 대상
FUZZY_MAX_DISTANCE = 2   # §2-8 오탈자 편집거리 ≤ 2
FUZZY_MIN_KEY_LEN = 4    # 'HR'·'PM'·'CS' 같은 짧은 별칭끼리는 편집거리 2 안에 서로 들어오므로 짧은 키는 퍼지 매칭에서 뺀다

# ---------------------------------------------------------------------------
# 상수 — 정규 값·사전 매핑 (§2-8, §3-1)  키는 norm_key() 로 정규화된 형태
# ---------------------------------------------------------------------------

DERIVED_FIELDS = ["ageBand", "tenureYears", "tenureYear", "tenureBand", "totalExperienceYears",
                  "totalExperienceBand", "stage", "orgGroupCode", "orgGroup"]

JOB_FAMILIES = ["Engineering", "Product", "Design", "Sales", "Marketing", "Customer Success",
                "People", "Finance", "Legal", "Data/AI", "Executive"]
JOB_FAMILY_SYNONYMS = {
    "eng": "Engineering", "engineer": "Engineering", "development": "Engineering", "developer": "Engineering",
    "개발": "Engineering", "software": "Engineering",
    "pm": "Product", "productmanagement": "Product", "프로덕트": "Product",
    "ux": "Design", "designer": "Design", "productdesign": "Design", "디자인": "Design",
    "영업": "Sales", "bizdev": "Sales",
    "마케팅": "Marketing", "growth": "Marketing",
    "cs": "Customer Success", "cx": "Customer Success", "customersupport": "Customer Success", "고객지원": "Customer Success",
    "hr": "People", "humanresources": "People", "인사": "People",
    "accounting": "Finance", "재무": "Finance",
    "legalandcompliance": "Legal", "legal&compliance": "Legal", "legalcompliance": "Legal", "compliance": "Legal", "법무": "Legal",
    "dataai": "Data/AI", "data&ai": "Data/AI", "dataandai": "Data/AI", "data": "Data/AI", "ai": "Data/AI",
    "datascience": "Data/AI", "ml": "Data/AI", "데이터": "Data/AI",
    "exec": "Executive", "clevel": "Executive", "c-level": "Executive", "경영진": "Executive", "임원": "Executive",
}
# §2-8 org-unknown: 직군 → 조직 기본 매핑 (임시 배정, confidence 0.5, unresolved)
JOB_FAMILY_DEFAULT_DEPT = {
    "Engineering": "D03", "Product": "D02", "Design": "D04", "Sales": "D06", "Marketing": "D07",
    "Customer Success": "D08", "People": "D09", "Finance": "D10", "Legal": "D11", "Data/AI": "D05",
    "Executive": "D01",
}

LEVELS = ["IC1", "IC2", "IC3", "Senior", "Lead", "Manager", "Director", "VP"]
LEVEL_SYNONYMS = {
    "sr": "Senior", "snr": "Senior", "시니어": "Senior",
    "ld": "Lead", "리드": "Lead", "teamlead": "Lead",
    "mgr": "Manager", "매니저": "Manager",
    "dir": "Director", "디렉터": "Director",
    "vicepresident": "VP", "vp": "VP", "부사장": "VP",
}
GENDER_MAP = {
    "여성": "여성", "여": "여성", "f": "여성", "female": "여성", "여자": "여성", "w": "여성", "woman": "여성",
    "남성": "남성", "남": "남성", "m": "남성", "male": "남성", "남자": "남성", "man": "남성",
    "미응답": "미응답", "": "미응답", "n/a": "미응답", "na": "미응답", "none": "미응답", "unknown": "미응답",
    "무응답": "미응답", "비공개": "미응답", "-": "미응답",
}
EMPLOYMENT_MAP = {
    "정규직": "정규직", "정규": "정규직", "regular": "정규직", "ft": "정규직", "fulltime": "정규직", "full-time": "정규직",
    "permanent": "정규직", "정규직원": "정규직",
    "계약직": "계약직", "계약": "계약직", "contract": "계약직", "contractor": "계약직", "기간제": "계약직",
    "fixed-term": "계약직", "fixedterm": "계약직", "계약직원": "계약직",
    "인턴": "인턴", "intern": "인턴", "internship": "인턴", "인턴십": "인턴", "인턴사원": "인턴",
    "파견": "파견", "dispatch": "파견", "dispatched": "파견", "파견직": "파견", "agency": "파견", "파견직원": "파견",
}
STATUS_MAP = {
    "재직": "재직", "재직중": "재직", "active": "재직", "employed": "재직", "근무": "재직", "근무중": "재직", "working": "재직",
    "휴직": "휴직", "휴직중": "휴직", "leave": "휴직", "onleave": "휴직", "on-leave": "휴직", "loa": "휴직", "휴직자": "휴직",
}
LEAVE_TYPE_MAP = {
    "육아휴직": "육아휴직", "육아": "육아휴직", "parental": "육아휴직", "parentalleave": "육아휴직", "maternity": "육아휴직",
    "paternity": "육아휴직", "출산": "육아휴직", "출산휴가": "육아휴직",
    "질병휴직": "질병휴직", "질병": "질병휴직", "병가": "질병휴직", "sick": "질병휴직", "sickleave": "질병휴직",
    "medical": "질병휴직", "상병": "질병휴직",
    "기타": "기타", "other": "기타", "etc": "기타", "기타휴직": "기타",
}
CONTRACT_TYPES = ["계약직", "인턴", "파견"]  # §2-8 missing-required 대상

SEPARATION_REASONS = ["자발퇴사", "개인사유", "계약만료", "조직개편", "성과/적합도", "건강", "정년"]
# §2-8 키워드 매핑 — 순서가 규칙의 일부다 (앞 항목이 먼저 매칭)
REASON_KEYWORDS = [
    (("자발", "이직", "전직", "resign", "voluntary"), "자발퇴사"),
    (("계약", "만료", "contract"), "계약만료"),
    (("조직", "개편", "restructur"), "조직개편"),
    (("성과", "적합", "performance"), "성과/적합도"),
    (("개인", "personal"), "개인사유"),
    (("건강", "health", "질병"), "건강"),
    (("정년", "retire"), "정년"),
]
SEPARATION_TYPE = {
    "자발퇴사": "자발적", "개인사유": "자발적", "건강": "자발적",
    "계약만료": "비자발적", "조직개편": "비자발적", "성과/적합도": "비자발적", "정년": "비자발적",
}
# 소속 표기에서 떼어내도 뜻이 같은 접미어 — 'Sales Team', 'Design 팀' 처럼 고객사 습관으로 붙는 말
ORG_SUFFIX_WORDS = ["team", "dept", "department", "division", "group", "org"]
ORG_SUFFIX_KO = ["팀", "부", "실", "본부", "그룹", "조직"]

# §2-7 정본 — 산출물에는 넣지 않고 stdout targetCheck 로만 보고 (데모 고객사 ㈜온다테크 기준)
EXPECTED = {
    "rowsIn": {"headcount-master": 435, "to-plan": 11, "planned-joiners": 27, "planned-leavers": 19},
    "rowsOut": {"headcount-master": 427, "to-plan": 11, "planned-joiners": 27, "planned-leavers": 19},
    "activeHeadcount": 406, "onLeave": 21, "headcount": 427, "toHeadcount": 422,
    "duplicatesRemoved": 8, "orgNameCorrections": 17, "hireDateCorrections": 31,
    "plannedInByMonthEnd": 19, "plannedOutByMonthEnd": 14,
}

ZERO_WIDTH_RE = re.compile(u"[​‌‍﻿]")
WS_RE = re.compile(r"\s+")
NON_ALNUM_RE = re.compile(u"[^0-9a-z가-힣]")
EMP_ID_RE = re.compile(r"^E\d{4}$")


class CleanseError(Exception):
    """실행을 계속할 수 없는 오류 (입력 누락·헤더 불일치)."""

    def __init__(self, message, exit_code=1):
        Exception.__init__(self, message)
        self.exit_code = exit_code


# ---------------------------------------------------------------------------
# 문자열·일자 헬퍼
# ---------------------------------------------------------------------------

def nfkc(s):
    """전각→반각, 제로폭 문자 제거. 모든 값 비교의 첫 단계."""
    s = unicodedata.normalize("NFKC", s or "")
    return ZERO_WIDTH_RE.sub("", s)


def ws_norm(s):
    """공백 정규화: NFKC → 연속 공백 1칸 → 앞뒤 제거. 원본과 다르면 org-whitespace 후보."""
    return WS_RE.sub(" ", nfkc(s)).strip()


def norm_key(s):
    """코드성 값 매칭 키: NFKC → 공백 전부 제거 → 소문자."""
    return WS_RE.sub("", nfkc(s)).strip().lower()


def org_key(s):
    """조직명 매칭 키: 소문자 · '&'↔'and' 동일시 · 공백/구두점 제거 (§2-8 '대소문자·공백·&↔and 무시')."""
    k = nfkc(s).lower().replace("&", "and")
    return NON_ALNUM_RE.sub("", k)


def levenshtein(a, b, limit):
    """편집거리. limit 를 넘으면 limit+1 을 돌려준다(조기 종료)."""
    if abs(len(a) - len(b)) > limit:
        return limit + 1
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (0 if ca == cb else 1)))
        if min(cur) > limit:
            return limit + 1
        prev = cur
    return prev[-1]


_DATE_PATTERNS = [
    (re.compile(r"^(\d{4})[-./](\d{1,2})[-./](\d{1,2})(?:[T\s]\d{1,2}:\d{2}(?::\d{2})?(?:\.\d+)?)?$"), "ymd4"),
    (re.compile(u"^(\\d{4})\\s*년\\s*(\\d{1,2})\\s*월\\s*(\\d{1,2})\\s*일?$"), "ymd4"),
    (re.compile(r"^(\d{4})(\d{2})(\d{2})$"), "ymd4"),
    (re.compile(r"^(\d{2})[-./](\d{1,2})[-./](\d{1,2})$"), "ymd2"),
    (re.compile(u"^(\\d{2})\\s*년\\s*(\\d{1,2})\\s*월\\s*(\\d{1,2})\\s*일?$"), "ymd2"),
    (re.compile(r"^(\d{5})(?:\.0+)?$"), "excel"),
]


def parse_date(raw, as_of, birth=False):
    """일자 문자열 → ISO 'YYYY-MM-DD'. 빈값 → '', 해석 불가 → None.
    §2-8: 2자리 연도는 20xx, Excel 일련번호는 1899-12-30 기준(5자리만 — 'YYYY' 4자리는 일련번호로 보지 않는다).
    생년월일(birth=True)만 예외 — 20xx 해석이 기준일 이후가 되면 19xx 로 본다(미래 출생은 불가능하므로)."""
    s = nfkc(raw).strip()
    if not s:
        return ""
    for pat, kind in _DATE_PATTERNS:
        m = pat.match(s)
        if not m:
            continue
        try:
            if kind == "excel":
                serial = int(m.group(1))
                if 20000 <= serial <= 80000:  # 1954-09-19 ~ 2119-01-19
                    return (EXCEL_EPOCH + timedelta(days=serial)).isoformat()
                return None
            y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
            if kind == "ymd2":
                y += 2000
                if birth and y > as_of.year:
                    y -= 100
            return date(y, mo, d).isoformat()
        except ValueError:
            return None
    return None


_MONTH_RE = re.compile(u"^(\\d{4})\\s*[-./년]?\\s*(\\d{1,2})\\s*월?$")


def parse_month(raw, as_of):
    """기준월 → 'YYYY-MM'. 빈값 → '', 해석 불가 → None. (`2026-09`,`2026.09`,`202609`,`2026년 9월`,`2026/9`)"""
    s = nfkc(raw).strip()
    if not s:
        return ""
    m = _MONTH_RE.match(s)
    if m:
        y, mo = int(m.group(1)), int(m.group(2))
        if 1 <= mo <= 12:
            return "%04d-%02d" % (y, mo)
        return None
    iso = parse_date(s, as_of)
    if iso:
        return iso[:7]
    return None


def parse_int(raw):
    """정수 필드('50', '50명', '1,200', '36개월'). 빈값/해석 불가 → None."""
    s = nfkc(raw).strip()
    if not s:
        return None
    digits = re.sub(r"[^\d-]", "", s)
    if not digits or digits == "-":
        return None
    try:
        return int(digits)
    except ValueError:
        return None


def age_band(birth_iso, as_of):
    """§2-8 ageBand: 기준일 만 나이. 20대 | 30대 | 40대 | 50대+ (30세 미만은 모두 20대)."""
    if not birth_iso:
        return ""
    b = date.fromisoformat(birth_iso)
    age = as_of.year - b.year - (1 if (as_of.month, as_of.day) < (b.month, b.day) else 0)
    if age < 30:
        return "20대"
    if age < 40:
        return "30대"
    if age < 50:
        return "40대"
    return "50대+"


def tenure_band(years):
    if years < 1:
        return "1년 미만"
    if years < 3:
        return "1~3년"
    if years < 5:
        return "3~5년"
    return "5년+"


def total_experience_band(years):
    if years < 3:
        return "0~3년"
    if years < 7:
        return "3~7년"
    if years < 12:
        return "7~12년"
    return "12년+"


def fmt2(x):
    return "%.2f" % x


def month_end(as_of):
    first_next = (as_of.replace(day=1) + timedelta(days=32)).replace(day=1)
    return first_next - timedelta(days=1)


# ---------------------------------------------------------------------------
# 조직 정규화 (org-normalization) — org-chart.csv 가 유일한 기준
# ---------------------------------------------------------------------------

class OrgMatch(object):
    __slots__ = ("deptCode", "rule", "confidence", "note")

    def __init__(self, dept_code, rule=None, confidence=None, note=""):
        self.deptCode = dept_code
        self.rule = rule
        self.confidence = confidence
        self.note = note


class OrgResolver(object):
    """자유 텍스트 소속 → deptCode. 매칭 순서(= rule 판정 순서):
    정규 표기 그대로 → 공백만 다름(org-whitespace) → 대소문자·&/and·구두점만 다름(org-variant)
    → formerNames 별칭(org-old-name) → 접미어(Team/팀…) 제거 후 재시도(org-variant) → 편집거리≤2(org-typo) → 없음(org-unknown)."""

    def __init__(self, org_rows):
        self.depts = []          # org-chart 순서
        self.by_code = {}
        self.by_name = {}        # 정규 department 표기(공백 정규화) → deptCode
        self.by_key = {}         # org_key(department) → deptCode
        self.former_by_key = {}  # org_key(formerName) → deptCode
        self.warnings = []
        for r in org_rows:
            d = {}
            for c in ORG_REQUIRED_COLUMNS + ["formerNames", "establishedOn"]:
                d[c] = ws_norm(r.get(c, ""))
            if not d["deptCode"] or not d["department"]:
                continue
            if d["deptCode"] in self.by_code:
                self.warnings.append("org-chart: deptCode %s 중복 — 첫 행만 사용" % d["deptCode"])
                continue
            self.depts.append(d)
            self.by_code[d["deptCode"]] = d
            self.by_name[d["department"]] = d["deptCode"]
            self.by_key.setdefault(org_key(d["department"]), d["deptCode"])
        for d in self.depts:
            for fn in d["formerNames"].split(";"):
                k = org_key(fn)
                if not k:
                    continue
                if k in self.by_key and self.by_key[k] != d["deptCode"]:
                    self.warnings.append("org-chart: 별칭 '%s'(%s)이 다른 조직의 정규 표기와 충돌 — 정규 표기 우선" % (fn.strip(), d["deptCode"]))
                    continue
                if k in self.former_by_key and self.former_by_key[k] != d["deptCode"]:
                    self.warnings.append("org-chart: 별칭 '%s'이 %s·%s 에 중복 — 앞 조직 우선" % (fn.strip(), self.former_by_key[k], d["deptCode"]))
                    continue
                self.former_by_key.setdefault(k, d["deptCode"])
        # 퍼지 후보: 정규 키 + 별칭 키 중 길이 ≥ FUZZY_MIN_KEY_LEN
        self._fuzzy_pool = []
        for k, code in list(self.by_key.items()) + list(self.former_by_key.items()):
            if len(k) >= FUZZY_MIN_KEY_LEN:
                self._fuzzy_pool.append((k, code))

    def _exact_or_alias(self, key):
        if key in self.by_key:
            return self.by_key[key], "org-variant"
        if key in self.former_by_key:
            return self.former_by_key[key], "org-old-name"
        return None, None

    def _strip_suffix(self, ws):
        toks = ws.split(" ")
        if len(toks) >= 2 and toks[-1].lower().rstrip(".") in ORG_SUFFIX_WORDS + ORG_SUFFIX_KO:
            return " ".join(toks[:-1])
        for suf in ORG_SUFFIX_KO:
            if len(ws) > len(suf) + 1 and ws.endswith(suf):
                return ws[:-len(suf)].strip()
        return None

    def _fuzzy(self, key):
        if len(key) < FUZZY_MIN_KEY_LEN:
            return None
        best = FUZZY_MAX_DISTANCE + 1
        codes = set()
        for k, code in self._fuzzy_pool:
            d = levenshtein(key, k, FUZZY_MAX_DISTANCE)
            if d < best:
                best, codes = d, set([code])
            elif d == best:
                codes.add(code)
        if best > FUZZY_MAX_DISTANCE:
            return None
        if len(codes) != 1:
            return ("", True)  # 서로 다른 조직과 같은 거리 → 모호 → 미해결로 넘긴다
        return (codes.pop(), False)

    def resolve(self, raw):
        s = nfkc(raw)
        ws = ws_norm(s)
        if not ws:
            return OrgMatch(None, note="empty")
        # 1. 정규 표기 (공백 차이만 있으면 org-whitespace)
        if ws in self.by_name:
            code = self.by_name[ws]
            if raw == ws:
                return OrgMatch(code)  # 원천 그대로 정규 표기 — 보정 없음
            return OrgMatch(code, "org-whitespace", 1.0)
        key = org_key(ws)
        # 2. 대소문자·&/and·구두점 변형 → 3. 별칭
        code, rule = self._exact_or_alias(key)
        if code:
            return OrgMatch(code, rule, 0.98 if rule == "org-variant" else 0.95)
        # 4. 접미어 제거 후 재시도 ('Sales Team', 'Design 팀')
        stripped = self._strip_suffix(ws)
        if stripped:
            code, rule = self._exact_or_alias(org_key(stripped))
            if code:
                return OrgMatch(code, "org-variant", 0.95, note="suffix")
        # 5. 오탈자 — 편집거리 ≤ 2
        fz = self._fuzzy(key)
        if fz:
            code, ambiguous = fz
            if ambiguous:
                return OrgMatch(None, note="ambiguous")
            return OrgMatch(code, "org-typo", 0.9)
        return OrgMatch(None, note="unmatched")


class StageTable(object):
    """company-stages.json 경계일로 입사일 → stage. 경계 밖(첫 from 이전)은 첫 스테이지로 두고 건수를 센다."""

    def __init__(self, stages):
        self.stages = []
        for s in stages:
            self.stages.append((s["stage"], s.get("from") or "0001-01-01", s.get("to") or "9999-12-31"))
        self.stages.sort(key=lambda x: x[1])
        self.before_first = 0

    def names(self):
        return [s[0] for s in self.stages]

    def lookup(self, hire_iso):
        if not hire_iso or not self.stages:
            return ""
        for stage, start, end in self.stages:
            if start <= hire_iso <= end:
                return stage
        if hire_iso < self.stages[0][1]:
            self.before_first += 1
            return self.stages[0][0]
        return self.stages[-1][0]


# ---------------------------------------------------------------------------
# 클린저
# ---------------------------------------------------------------------------

class RowCtx(object):
    """행 하나의 로그·플래그 누적기. unresolved 로그는 자동으로 unresolvedFlags 에 들어간다."""

    def __init__(self, cleanser, source, row_ref):
        self.cleanser = cleanser
        self.source = source
        self.row_ref = row_ref
        self.flags = []

    def log(self, field, raw, corrected, rule, confidence, unresolved=False, question=None):
        self.cleanser.log(self.source, self.row_ref, field, raw, corrected, rule, confidence, unresolved, question)
        if unresolved and rule not in self.flags:
            self.flags.append(rule)

    def flags_str(self):
        return ";".join(self.flags)


class Cleanser(object):

    def __init__(self, root, as_of, resolver, stages):
        self.root = root
        self.as_of = as_of
        self.as_of_iso = as_of.isoformat()
        self.month_end_iso = month_end(as_of).isoformat()
        self.resolver = resolver
        self.stages = stages
        self.log_entries = []
        self.unresolved_items = []
        self.warnings = list(resolver.warnings)
        self.degradations = []  # 산출물은 썼지만 하류가 알아야 할 결손 → status partial
        self.rows_in = {}
        self.rows_out = {}
        self.duplicates_removed = 0
        self.master_by_id = {}
        self.clean = dict((k, []) for k in SOURCES)
        self.counters = {"emptyBirth": 0, "emptyPrior": 0, "leaveTypeOnActive": 0,
                         "contractEndOnRegular": 0, "statusOutOfDomain": 0}

    # ---- 로그 -----------------------------------------------------------
    def log(self, source, row_ref, field, raw, corrected, rule, confidence, unresolved, question=None):
        if rule not in DEFECT_TYPES:
            raise CleanseError("내부 오류: 계약 어휘 밖 rule '%s'" % rule)
        self.log_entries.append({
            "source": source, "rowRef": dict(row_ref), "field": field, "rawValue": raw,
            "correctedValue": corrected, "rule": rule, "confidence": confidence, "unresolved": bool(unresolved),
        })
        if unresolved:
            self.unresolved_items.append({
                "source": source, "rowRef": dict(row_ref), "field": field, "rawValue": raw,
                "flag": rule, "question": question or "확인이 필요합니다.",
            })

    # ---- 공통 정규화 -----------------------------------------------------
    def norm_code(self, ctx, field, raw, mapping, allow_empty, question_hint):
        """사전 매핑 표기 정규화. 매핑 불가는 값을 지우지 않고(원천 보존) 플래그만 — 값을 지우면 하류 대사가 조용히 어긋난다."""
        s = ws_norm(raw)
        key = norm_key(s)
        if not key:
            if allow_empty:
                return ""
            if "" in mapping:  # 성별: 빈값 → 미응답 (§2-8)
                ctx.log(field, raw, mapping[""], "code-variant", 1.0)
                return mapping[""]
            ctx.log(field, raw, "", "code-variant", None, True, "'%s' 값이 비어 있습니다. %s" % (field, question_hint))
            return ""
        canon = mapping.get(key)
        if canon is None:
            ctx.log(field, raw, s, "code-variant", None, True,
                    "'%s' 값 '%s'을(를) 정규 값으로 매핑할 수 없습니다. %s" % (field, s, question_hint))
            return s
        if canon != raw:
            ctx.log(field, raw, canon, "code-variant", 1.0)
        return canon

    def norm_job_family(self, ctx, raw):
        mapping = dict((norm_key(j), j) for j in JOB_FAMILIES)
        mapping.update(JOB_FAMILY_SYNONYMS)
        return self.norm_code(ctx, "직군", raw, mapping, False, "직군은? (%s)" % "/".join(JOB_FAMILIES))

    def norm_level(self, ctx, raw):
        mapping = dict((norm_key(l), l) for l in LEVELS)
        mapping.update(LEVEL_SYNONYMS)
        s = ws_norm(raw)
        key = re.sub(r"[-._\s]", "", nfkc(s)).lower()  # 'IC-2' → 'ic2', 'Sr.' → 'sr'
        if not key:
            ctx.log("레벨", raw, "", "code-variant", None, True, "레벨 값이 비어 있습니다. 레벨은? (%s)" % "/".join(LEVELS))
            return ""
        canon = mapping.get(key)
        if canon is None:
            ctx.log("레벨", raw, s, "code-variant", None, True,
                    "레벨 '%s'을(를) 정규 값으로 매핑할 수 없습니다. 레벨은? (%s)" % (s, "/".join(LEVELS)))
            return s
        if canon != raw:
            ctx.log("레벨", raw, canon, "code-variant", 1.0)
        return canon

    def norm_date(self, ctx, field, raw, rule="date-format", birth=False):
        """일자 보정. 입사일만 rule='hire-date-format'(§2-5 어휘), 나머지는 'date-format'."""
        iso = parse_date(raw, self.as_of, birth=birth)
        if iso == "":
            return ""
        if iso is None:
            ctx.log(field, raw, "", rule, None, True,
                    "일자 '%s'을(를) 해석할 수 없습니다. 올바른 일자(YYYY-MM-DD)는?" % ws_norm(raw))
            return ""
        if iso != raw:
            ctx.log(field, raw, iso, rule, 1.0)
        return iso

    def norm_reason(self, ctx, raw):
        """퇴직사유 → (separationReason, separationType). 빈값 → ('', '')."""
        s = ws_norm(raw)
        if not s:
            return "", ""
        compact = norm_key(s).replace(u"·", "/")
        for canon in SEPARATION_REASONS:
            if compact == norm_key(canon):
                if canon != raw:
                    ctx.log("퇴직사유", raw, canon, "reason-freetext", 1.0)
                return canon, SEPARATION_TYPE[canon]
        low = s.lower()
        for kws, canon in REASON_KEYWORDS:
            if any(k in low for k in kws):
                ctx.log("퇴직사유", raw, canon, "reason-freetext", 0.9)
                return canon, SEPARATION_TYPE[canon]
        ctx.log("퇴직사유", raw, "", "reason-freetext", None, True,
                "퇴직사유 '%s'을(를) 정규 사유(%s)로 매핑할 수 없습니다. 어느 사유입니까?" % (s, "/".join(SEPARATION_REASONS)))
        return "", ""

    def resolve_org(self, ctx, field, raw, job_family):
        """소속 → 조직 dict(없으면 빈 dict). org-unknown 은 직군→조직 임시 배정 + 미해결(§2-8)."""
        m = self.resolver.resolve(raw)
        if m.deptCode is not None:
            dept = self.resolver.by_code[m.deptCode]
            if m.rule:
                ctx.log(field, raw, m.deptCode, m.rule, m.confidence)
            return dept
        shown = ws_norm(raw)
        fallback = JOB_FAMILY_DEFAULT_DEPT.get(job_family or "")
        dept = self.resolver.by_code.get(fallback, {}) if fallback else {}
        if dept:
            q = "어느 조직 소속입니까? (직군 %s 기준 %s으로 임시 배정)" % (
                job_family, dept["department"])
        elif job_family:
            q = "소속 '%s'은(는) 조직 체계에 없고 직군 '%s'의 기본 조직도 없어 임시 배정하지 못했습니다. 어느 조직 소속입니까?" % (
                shown or "(빈값)", job_family)
        else:
            q = "소속 '%s'은(는) 조직 체계에 없습니다. 어느 조직입니까?" % (shown or "(빈값)")
        if m.note == "ambiguous":
            q += " (여러 조직과 비슷해 자동 매칭하지 않음)"
        ctx.log(field, raw, dept.get("deptCode", ""), "org-unknown", 0.5 if dept else None, True, q)
        return dept

    # ---- ① 인원현황 마스터 -----------------------------------------------
    def cleanse_master(self, rows):
        source = "headcount-master"
        self.rows_in[source] = len(rows)
        groups, order = {}, []
        for idx, row in rows:
            raw_id = row.get("사번", "")
            emp = norm_key(raw_id).upper()
            gkey = emp if emp else "__blank_%d" % idx
            if gkey not in groups:
                groups[gkey] = []
                order.append(gkey)
            groups[gkey].append((idx, row, raw_id, emp))
        # 중복 해소를 먼저 한다: 구버전 행은 최신 행에 대체되므로 개별 보정하지 않는다(로그·17건 산정 오염 방지)
        survivors = []
        for gkey in order:
            members = groups[gkey]
            if len(members) == 1:
                survivors.append(members[0])
                continue

            def sort_key(m):
                iso = parse_date(m[1].get("최종수정일", ""), self.as_of)
                return (iso or "", m[0])  # 최종수정일 최신, 동일하면 뒤 행 (§2-8)

            ranked = sorted(members, key=sort_key)
            keep = ranked[-1]
            for m in ranked[:-1]:
                self.log(source, {"사번": m[3], "rowIndex": m[0]}, "사번", m[1].get("최종수정일", ""), keep[0], "duplicate", 1.0, False)
                self.duplicates_removed += 1
            survivors.append(keep)
        survivors.sort(key=lambda m: m[0])
        for idx, row, raw_id, emp in survivors:
            rec = self.cleanse_master_row(idx, row, emp, raw_id)
            self.clean[source].append(rec)
            if emp:
                self.master_by_id[emp] = rec
        self.rows_out[source] = len(self.clean[source])

    def cleanse_master_row(self, idx, row, emp_id, raw_emp_id):
        ctx = RowCtx(self, "headcount-master", {"사번": emp_id, "rowIndex": idx})
        if emp_id != raw_emp_id:
            ctx.log("사번", raw_emp_id, emp_id, "code-variant", 1.0)
        if not EMP_ID_RE.match(emp_id):
            self.warnings.append("headcount-master rowIndex %d: 사번 '%s'이(가) E+4자리 형식이 아님(값은 유지)" % (idx, raw_emp_id))

        name = ws_norm(row.get("성명", ""))
        gender = self.norm_code(ctx, "성별", row.get("성별", ""), GENDER_MAP, False, "성별은? (여성/남성/미응답)")
        job_family = self.norm_job_family(ctx, row.get("직군", ""))
        level = self.norm_level(ctx, row.get("레벨", ""))
        employment_type = self.norm_code(ctx, "고용유형", row.get("고용유형", ""), EMPLOYMENT_MAP, False, "고용유형은? (정규직/계약직/인턴/파견)")
        status = self.norm_code(ctx, "재직상태", row.get("재직상태", ""), STATUS_MAP, False, "재직상태는? (재직/휴직 — 퇴직자는 마스터 범위 밖)")
        leave_type = self.norm_code(ctx, "휴직유형", row.get("휴직유형", ""), LEAVE_TYPE_MAP, True, "휴직유형은? (육아휴직/질병휴직/기타)")
        if status not in ("재직", "휴직"):
            self.counters["statusOutOfDomain"] += 1

        # org-normalization (직군은 org-unknown 임시 배정에 쓴다)
        dept = self.resolve_org(ctx, "소속", row.get("소속", ""), job_family)

        birth = self.norm_date(ctx, "생년월일", row.get("생년월일", ""), birth=True)
        leave_start = self.norm_date(ctx, "휴직시작일", row.get("휴직시작일", ""))
        hire = self.norm_date(ctx, "입사일", row.get("입사일", ""), rule="hire-date-format")
        contract_end = self.norm_date(ctx, "계약종료일", row.get("계약종료일", ""))
        self.norm_date(ctx, "최종수정일", row.get("최종수정일", ""))  # 산출물엔 없지만 포맷 보정은 로그로 남긴다
        if not hire and not ws_norm(row.get("입사일", "")):
            ctx.log("입사일", row.get("입사일", ""), "", "hire-date-format", None, True, "입사일이 비어 있습니다. 입사일은?")
        if not birth:
            self.counters["emptyBirth"] += 1

        # date-logic: 재직(휴직 포함)인데 입사일 > 기준일 → 그대로 두고 플래그, 재직기간 0 (§2-8)
        hire_after_as_of = False
        if hire and status in ("재직", "휴직") and hire > self.as_of_iso:
            hire_after_as_of = True
            ctx.log("입사일", row.get("입사일", ""), hire, "date-logic", None, True,
                    "재직 상태인데 입사일(%s)이 기준일 이후입니다. 입사일을 확인해 주세요 (재직기간 0으로 집계)" % hire)

        # status-inconsistency: 휴직인데 휴직유형 없음 → 기타 (0.6, 미해결)
        if status == "휴직" and not leave_type:
            ctx.log("휴직유형", row.get("휴직유형", ""), "기타", "status-inconsistency", 0.6, True,
                    "휴직 상태인데 휴직유형이 없습니다. 유형을 확인해 주세요 (기타로 임시 배정)")
            leave_type = "기타"
        if status == "재직" and leave_type:
            self.counters["leaveTypeOnActive"] += 1

        # missing-required: 계약직/인턴/파견인데 계약종료일 없음 → 빈값 유지, 플래그
        if employment_type in CONTRACT_TYPES and not contract_end:
            ctx.log("계약종료일", row.get("계약종료일", ""), "", "missing-required", None, True,
                    "%s인데 계약종료일이 없습니다. 계약종료일을 확인해 주세요" % employment_type)
        if employment_type == "정규직" and contract_end:
            self.counters["contractEndOnRegular"] += 1

        # 파생 필드 (§2-8 파생 행)
        prior = parse_int(row.get("입사전경력(개월)", ""))
        if prior is None:
            self.counters["emptyPrior"] += 1
        tenure_years = tenure_year = t_band = total_exp = te_band = ""
        if hire:
            if hire_after_as_of:
                ty = 0.0
            else:
                ty = round((self.as_of - date.fromisoformat(hire)).days / 365.25, 2)
            tenure_years = fmt2(ty)
            tenure_year = str(int(math.floor(ty)) + 1)
            t_band = tenure_band(ty)
            te = round((prior or 0) / 12.0 + ty, 2)
            total_exp = fmt2(te)
            te_band = total_experience_band(te)
        stage = self.stages.lookup(hire) if self.stages else ""

        return {
            "empId": emp_id, "name": name, "gender": gender, "birthDate": birth,
            "ageBand": age_band(birth, self.as_of),
            "orgGroupCode": dept.get("orgGroupCode", ""), "orgGroup": dept.get("orgGroup", ""),
            "deptCode": dept.get("deptCode", ""), "department": dept.get("department", ""),
            "jobFamily": job_family, "level": level, "stage": stage,
            "employmentType": employment_type, "status": status, "leaveType": leave_type,
            "leaveStart": leave_start, "hireDate": hire, "contractEndDate": contract_end,
            "priorExperienceMonths": "" if prior is None else str(prior),
            "tenureYears": tenure_years, "tenureYear": tenure_year, "tenureBand": t_band,
            "totalExperienceYears": total_exp, "totalExperienceBand": te_band,
            "unresolvedFlags": ctx.flags_str(), "sourceRowIndex": str(idx),
        }

    # ---- ② TO 계획 -------------------------------------------------------
    def cleanse_to_plan(self, rows):
        source = "to-plan"
        self.rows_in[source] = len(rows)
        seen = {}
        for idx, row in rows:
            ctx = RowCtx(self, source, {"사번": "", "rowIndex": idx})
            dept = self.resolve_org(ctx, "조직", row.get("조직", ""), None)
            to = parse_int(row.get("정원", ""))
            if to is None:
                self.warnings.append("to-plan rowIndex %d: 정원 '%s' 해석 불가 → 빈값" % (idx, row.get("정원", "")))
                self.degradations.append("to-plan 정원 미해석 rowIndex %d" % idx)
            raw_month = row.get("기준월", "")
            month = parse_month(raw_month, self.as_of)
            if month is None:
                ctx.log("기준월", raw_month, "", "date-format", None, True,
                        "기준월 '%s'을(를) 해석할 수 없습니다. YYYY-MM 으로 무엇입니까?" % ws_norm(raw_month))
                month = ""
            elif month != raw_month:
                ctx.log("기준월", raw_month, month, "date-format", 1.0)
            code = dept.get("deptCode", "")
            if code:
                if code in seen:
                    self.warnings.append("to-plan: 조직 %s 가 rowIndex %d 와 %d 에 중복 — 예측 단계 이중 집계 위험" % (code, seen[code], idx))
                seen[code] = idx
            else:
                self.degradations.append("to-plan 조직 미매핑 rowIndex %d ('%s')" % (idx, ws_norm(row.get("조직", ""))))
            self.clean[source].append({
                "deptCode": code, "department": dept.get("department", ""), "orgGroupCode": dept.get("orgGroupCode", ""),
                "toHeadcount": "" if to is None else str(to), "effectiveMonth": month,
            })
        self.rows_out[source] = len(self.clean[source])
        missing = [d["deptCode"] for d in self.resolver.depts if d["deptCode"] not in seen]
        if missing:
            self.warnings.append("to-plan 에 없는 조직: %s (예측 단계에서 TO 0 취급 위험)" % ",".join(missing))

    # ---- ③ 입사 예정자 ---------------------------------------------------
    def cleanse_joiners(self, rows):
        source = "planned-joiners"
        self.rows_in[source] = len(rows)
        for n, (idx, row) in enumerate(rows, 1):
            jid = "J%03d" % n  # §3-3 joinerId J001~ : 원천 행 순서. 미해결 행도 번호를 받는다(행을 버리지 않으므로)
            ctx = RowCtx(self, source, {"사번": "", "rowIndex": idx})
            name = ws_norm(row.get("성명", ""))
            job_family = self.norm_job_family(ctx, row.get("직군", ""))
            level = self.norm_level(ctx, row.get("레벨", ""))
            employment_type = self.norm_code(ctx, "고용유형", row.get("고용유형", ""), EMPLOYMENT_MAP, False, "고용유형은? (정규직/계약직/인턴/파견)")
            gender = self.norm_code(ctx, "성별", row.get("성별", ""), GENDER_MAP, False, "성별은? (여성/남성/미응답)")
            birth = self.norm_date(ctx, "생년월일", row.get("생년월일", ""), birth=True)
            planned = self.norm_date(ctx, "입사예정일", row.get("입사예정일", ""))
            if not planned and not ws_norm(row.get("입사예정일", "")):
                ctx.log("입사예정일", row.get("입사예정일", ""), "", "date-format", None, True,
                        "입사예정일이 비어 있습니다. 월말 예측에 넣을 수 없습니다. 입사예정일은?")
            if planned and planned <= self.as_of_iso:
                ctx.log("입사예정일", row.get("입사예정일", ""), planned, "date-logic", None, True,
                        "입사예정일 %s이(가) 기준일 %s 이전입니다. 이미 입사했다면 마스터에 있어야 합니다. 확인 바랍니다." % (planned, self.as_of_iso))
            if not planned:
                self.degradations.append("planned-joiners %s 입사예정일 없음" % jid)
            dept = self.resolve_org(ctx, "소속", row.get("소속", ""), job_family)
            prior = parse_int(row.get("입사전경력(개월)", ""))
            self.clean[source].append({
                "joinerId": jid, "name": name, "deptCode": dept.get("deptCode", ""), "department": dept.get("department", ""),
                "jobFamily": job_family, "level": level, "employmentType": employment_type, "gender": gender,
                "birthDate": birth, "plannedHireDate": planned,
                "priorExperienceMonths": "" if prior is None else str(prior),
                "unresolvedFlags": ctx.flags_str(),
            })
        self.rows_out[source] = len(self.clean[source])

    # ---- ④ 퇴사 예정자 ---------------------------------------------------
    def cleanse_leavers(self, rows):
        source = "planned-leavers"
        self.rows_in[source] = len(rows)
        seen = {}
        for idx, row in rows:
            raw_id = row.get("사번", "")
            emp = norm_key(raw_id).upper()
            ctx = RowCtx(self, source, {"사번": emp, "rowIndex": idx})
            if emp != raw_id:
                ctx.log("사번", raw_id, emp, "code-variant", 1.0)
            master = self.master_by_id.get(emp)
            job_family = master["jobFamily"] if master else None
            dept = self.resolve_org(ctx, "소속", row.get("소속", ""), job_family)
            # 조직 코드는 마스터가 정본 — 같은 사람의 조직이 두 파일에서 달라지면 통계·예측이 어긋난다
            dept_code = master["deptCode"] if (master and master["deptCode"]) else dept.get("deptCode", "")
            if master and master["deptCode"] and dept.get("deptCode") and dept["deptCode"] != master["deptCode"]:
                self.warnings.append("planned-leavers rowIndex %d (%s): 소속 %s 이(가) 마스터 조직 %s 과 달라 마스터를 따름" % (
                    idx, emp, dept["deptCode"], master["deptCode"]))
            planned = self.norm_date(ctx, "퇴사예정일", row.get("퇴사예정일", ""))
            if not planned and not ws_norm(row.get("퇴사예정일", "")):
                ctx.log("퇴사예정일", row.get("퇴사예정일", ""), "", "date-format", None, True,
                        "퇴사예정일이 비어 있습니다. 월말 예측에 넣을 수 없습니다. 퇴사예정일은?")
            if master is None:
                ctx.log("사번", raw_id, "", "unknown-emp", None, True,
                        "마스터에 없는 사번입니다. 사번을 확인해 주세요 (예측에서 제외)")
            elif planned and planned < self.as_of_iso:
                ctx.log("퇴사예정일", row.get("퇴사예정일", ""), planned, "stale-planned-leaver", None, True,
                        "퇴사 예정일(%s)이 기준일 이전인데 마스터에는 재직 상태입니다. 실제 퇴사 여부를 확인해 주세요" % planned)
            sep_reason, sep_type = self.norm_reason(ctx, row.get("퇴직사유", ""))
            if master is not None and master["status"] == "휴직":
                self.warnings.append("planned-leavers rowIndex %d (%s): 휴직자의 퇴사 예정 — 재직 기준 예측에서는 제외, 급여 마감 총원에는 반영(§4-5)" % (idx, emp))
            if emp in seen:
                self.warnings.append("planned-leavers: 사번 %s 가 rowIndex %d 와 %d 에 중복" % (emp, seen[emp], idx))
            seen[emp] = idx
            self.clean[source].append({
                "empId": emp, "deptCode": dept_code, "plannedTerminationDate": planned,
                "separationType": sep_type, "separationReason": sep_reason,
                "unresolvedFlags": ctx.flags_str(),
            })
        self.rows_out[source] = len(self.clean[source])

    # ---- 집계 ------------------------------------------------------------
    def corrections_by_rule(self):
        counts = {}
        for e in self.log_entries:
            counts[e["rule"]] = counts.get(e["rule"], 0) + 1
        return counts

    def corrections_by_source(self):
        counts = {source: {} for source in SOURCES}
        for entry in self.log_entries:
            by_rule = counts[entry["source"]]
            rule = entry["rule"]
            by_rule[rule] = by_rule.get(rule, 0) + 1
        return counts

    def unresolved_by_flag(self):
        counts = {}
        for e in self.log_entries:
            if e["unresolved"]:
                counts[e["rule"]] = counts.get(e["rule"], 0) + 1
        return dict((r, counts[r]) for r in DEFECT_TYPES if r in counts)

    def org_name_corrections(self):
        """브리프 '부서명 정규화 17건' = 마스터 소속 보정 중 해결된 것(org-unknown 임시 배정은 보정이 아니라 미해결)."""
        return sum(1 for e in self.log_entries
                   if e["source"] == "headcount-master" and e["field"] == "소속" and e["rule"] in ORG_CORRECTION_RULES)

    def hire_date_corrections(self):
        return sum(1 for e in self.log_entries
                   if e["source"] == "headcount-master" and e["field"] == "입사일" and e["rule"] == "hire-date-format"
                   and not e["unresolved"])

    def org_group_mapping(self):
        return dict((d["deptCode"], d["orgGroup"]) for d in self.resolver.depts)

    def headcounts(self):
        master = self.clean["headcount-master"]
        active = sum(1 for r in master if r["status"] == "재직")
        on_leave = sum(1 for r in master if r["status"] == "휴직")
        return {"headcount": active + on_leave, "activeHeadcount": active, "onLeave": on_leave,
                "rows": len(master), "statusOutOfDomain": self.counters["statusOutOfDomain"]}

    def planned_counts(self):
        joiners = self.clean["planned-joiners"]
        leavers = self.clean["planned-leavers"]
        j_me = sum(1 for r in joiners if r["plannedHireDate"] and r["plannedHireDate"] <= self.month_end_iso)
        valid = [r for r in leavers if "unknown-emp" not in r["unresolvedFlags"].split(";")]
        l_me = sum(1 for r in valid if r["plannedTerminationDate"] and r["plannedTerminationDate"] <= self.month_end_iso)
        l_me_active = sum(1 for r in valid if r["plannedTerminationDate"] and r["plannedTerminationDate"] <= self.month_end_iso
                          and self.master_by_id.get(r["empId"], {}).get("status") == "재직")
        return {"plannedJoiners": {"total": len(joiners), "byMonthEnd": j_me},
                "plannedLeavers": {"total": len(leavers), "knownEmp": len(valid), "byMonthEnd": l_me,
                                   "byMonthEndActive": l_me_active}}

    def to_total(self):
        return sum(int(r["toHeadcount"]) for r in self.clean["to-plan"] if r["toHeadcount"])

    def domain_violations(self):
        """정제 값이 §3-1 정규 값 밖인 셀 수(빈값 제외). 0이어야 test_contract 가 통과한다."""
        domains = {"gender": ["여성", "남성", "미응답"], "status": ["재직", "휴직"],
                   "employmentType": ["정규직", "계약직", "인턴", "파견"], "leaveType": ["육아휴직", "질병휴직", "기타"],
                   "level": LEVELS, "jobFamily": JOB_FAMILIES,
                   "stage": self.stages.names() if self.stages else []}
        bad = {}
        for r in self.clean["headcount-master"]:
            for col, dom in domains.items():
                v = r.get(col, "")
                if v and dom and v not in dom:
                    bad[col] = bad.get(col, 0) + 1
        return bad

    def target_check(self):
        hc = self.headcounts()
        pc = self.planned_counts()
        actual = {
            "rowsIn": dict((k, self.rows_in.get(k, 0)) for k in SOURCES),
            "rowsOut": dict((k, self.rows_out.get(k, 0)) for k in SOURCES),
            "activeHeadcount": hc["activeHeadcount"], "onLeave": hc["onLeave"], "headcount": hc["headcount"],
            "toHeadcount": self.to_total(), "duplicatesRemoved": self.duplicates_removed,
            "orgNameCorrections": self.org_name_corrections(), "hireDateCorrections": self.hire_date_corrections(),
            "plannedInByMonthEnd": pc["plannedJoiners"]["byMonthEnd"], "plannedOutByMonthEnd": pc["plannedLeavers"]["byMonthEndActive"],
        }
        mismatches = []
        for k, exp in EXPECTED.items():
            if isinstance(exp, dict):
                for src, v in exp.items():
                    if actual[k].get(src) != v:
                        mismatches.append({"metric": "%s.%s" % (k, src), "expected": v, "actual": actual[k].get(src)})
            elif actual[k] != exp:
                mismatches.append({"metric": k, "expected": exp, "actual": actual[k]})
        return {"basis": "DATA_CONTRACT §2-7 데모 정본(㈜온다테크) — 실고객 데이터에서는 참고값", "passed": not mismatches,
                "mismatches": mismatches}

    def summary(self):
        return {
            "asOfDate": self.as_of_iso,
            "rowsIn": dict((k, self.rows_in.get(k, 0)) for k in SOURCES),
            "rowsOut": dict((k, self.rows_out.get(k, 0)) for k in SOURCES),
            "duplicatesRemoved": self.duplicates_removed,
            "correctionsByRule": self.corrections_by_rule(),
            "correctionsBySource": self.corrections_by_source(),
            "orgNameCorrections": self.org_name_corrections(),
            "orgUnknown": sum(1 for e in self.log_entries
                              if e["source"] == "headcount-master" and e["rule"] == "org-unknown"),
            "hireDateCorrections": self.hire_date_corrections(),
            "orgGroupMapping": self.org_group_mapping(),
            "derivedFields": list(DERIVED_FIELDS),
            "unresolvedCount": len(self.unresolved_items),
            "unresolvedItems": self.unresolved_items,
            "warnings": list(self.warnings),
            "provenance": {
                "rawSources": dict(RAW_PATHS),
                "orgChart": ORG_CHART_PATH,
                "stages": STAGES_PATH,
                "script": SCRIPT_REL,
            },
        }

    # ---- 산출물 ----------------------------------------------------------
    def write_outputs(self):
        os.makedirs(os.path.join(self.root, "data", "clean"), exist_ok=True)
        for source in SOURCES:
            path = os.path.join(self.root, CLEAN_PATHS[source])
            with open(path, "w", encoding="utf-8", newline="") as f:
                w = csv.DictWriter(f, fieldnames=CLEAN_HEADERS[source], lineterminator="\n", extrasaction="ignore")
                w.writeheader()
                for rec in self.clean[source]:
                    w.writerow(rec)
        with open(os.path.join(self.root, LOG_PATH), "w", encoding="utf-8") as f:
            for e in self.log_entries:
                f.write(json.dumps(e, ensure_ascii=False) + "\n")
        with open(os.path.join(self.root, SUMMARY_PATH), "w", encoding="utf-8") as f:
            json.dump(self.summary(), f, ensure_ascii=False, indent=1)
            f.write("\n")

    def result(self, started, status):
        hc = self.headcounts()
        pc = self.planned_counts()
        return {
            "status": status,
            "asOfDate": self.as_of_iso,
            "monthEnd": self.month_end_iso,
            "artifacts": [CLEAN_PATHS[s] for s in SOURCES] + [LOG_PATH, SUMMARY_PATH],
            "rowsIn": dict((k, self.rows_in.get(k, 0)) for k in SOURCES),
            "rowsOut": dict((k, self.rows_out.get(k, 0)) for k in SOURCES),
            "duplicatesRemoved": self.duplicates_removed,
            "correctionsByRule": self.corrections_by_rule(),
            "orgNameCorrections": self.org_name_corrections(),
            "hireDateCorrections": self.hire_date_corrections(),
            "headcount": hc["headcount"], "activeHeadcount": hc["activeHeadcount"], "onLeave": hc["onLeave"],
            "toHeadcount": self.to_total(),
            "plannedJoiners": pc["plannedJoiners"], "plannedLeavers": pc["plannedLeavers"],
            "unresolvedCount": len(self.unresolved_items),
            "unresolvedByFlag": self.unresolved_by_flag(),
            "domainViolations": self.domain_violations(),
            "targetCheck": self.target_check(),
            "warnings": self.warnings,
            "degradations": self.degradations,
            "handoffLog": HANDOFF_PATH,
            "durationSeconds": round(time.time() - started, 2),
        }


# ---------------------------------------------------------------------------
# 입력 읽기
# ---------------------------------------------------------------------------

def read_csv_rows(path, required_columns, label):
    """(rowIndex, dict) 목록. rowIndex 는 헤더 제외 0부터의 물리 행 번호(빈 줄도 번호를 소비) — 정답지 rowRef 규약(§2-6)."""
    if not os.path.isfile(path):
        raise CleanseError("%s 없음: %s" % (label, path), 3)
    with open(path, encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f)
        try:
            header = next(reader)
        except StopIteration:
            raise CleanseError("%s 이(가) 비어 있음: %s" % (label, path), 3)
        header = [ws_norm(h) for h in header]
        missing = [c for c in required_columns if c not in header]
        if missing:
            raise CleanseError("%s 헤더에 필수 컬럼 없음 %s (실제: %s)" % (label, missing, header), 1)
        rows = []
        for i, values in enumerate(reader):
            if not any(v.strip() for v in values):
                continue
            row = {}
            for k, h in enumerate(header):
                row[h] = values[k] if k < len(values) else ""
            rows.append((i, row))
    return rows


def read_stages(path):
    """company-stages.json → StageTable. 없으면 None(경고·partial). 형식이 깨졌으면 오류."""
    if not os.path.isfile(path):
        return None
    with open(path, encoding="utf-8-sig") as f:
        data = json.load(f)
    stages = data.get("stages") if isinstance(data, dict) else None
    if not stages or not all(isinstance(s, dict) and s.get("stage") for s in stages):
        raise CleanseError("company-stages.json 형식 오류: {\"stages\":[{\"stage\",\"from\",\"to\"}]} 필요", 1)
    return StageTable(stages)


# ---------------------------------------------------------------------------
# 핸드오프 로그 (Operating Rule 2) — 5개 H2 고정
# ---------------------------------------------------------------------------

HANDOFF_SECTIONS = ["시도한 것", "본 데이터·근거", "실패한 것", "검증된 것", "다음 agent 인계점"]


def write_handoff(root, as_of_iso, sections):
    path = os.path.join(root, HANDOFF_PATH)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    lines = ["# %s — %s — %s" % (PHASE, AGENT, as_of_iso), ""]
    for title in HANDOFF_SECTIONS:
        lines.append("## %s" % title)
        lines.extend(sections.get(title) or ["- (없음)"])
        lines.append("")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def now_iso():
    return datetime.now().isoformat(timespec="seconds")


def handoff_start(root, as_of_iso, argv_text):
    write_handoff(root, as_of_iso, {
        "시도한 것": ["- %s 실행 시작: `python3 %s %s`" % (now_iso(), SCRIPT_REL, argv_text),
                   "- 절차: 중복 해소 → 표기 정규화 → 일자 보정 → 상태 정합 → 조직 정규화(별칭·정규화 매칭·편집거리≤2) + 조직 그룹 부여 → 파생 필드 → 정제 CSV 4종 + 로그 + 요약"],
        "본 데이터·근거": ["- 읽을 파일: %s, %s, %s" % (ORG_CHART_PATH, STAGES_PATH, ", ".join(RAW_PATHS[s] for s in SOURCES)),
                      "- 규칙: DATA_CONTRACT v2 §2-5(어휘) · §2-8(보정) · §3(정제 shape) · GLOSSARY 클린징 절",
                      "- 정답지 data/raw/injected-defects.json 은 읽지 않는다"],
        "실패한 것": ["- (실행 중)"],
        "검증된 것": ["- (실행 중)"],
        "다음 agent 인계점": ["- (실행 중 — 종료 시 갱신)"],
    })


def handoff_finish(root, cl, res, argv_text):
    tc = res["targetCheck"]
    fails = []
    if res["unresolvedCount"]:
        fails.append("- 규칙으로 못 고친 미해결 %d건(플래그별 %s) → cleansing-summary.unresolvedItems 의 질문을 고객사 HR 에 확인 요청" % (
            res["unresolvedCount"], json.dumps(res["unresolvedByFlag"], ensure_ascii=False)))
    for w in res["warnings"]:
        fails.append("- 경고: %s" % w)
    for d in res["degradations"]:
        fails.append("- 결손(partial): %s" % d)
    if not tc["passed"]:
        fails.append("- §2-7 정본 대조 불일치 %d건: %s" % (len(tc["mismatches"]), json.dumps(tc["mismatches"], ensure_ascii=False)))
    if not fails:
        fails = ["- 없음"]
    verified = [
        "- 행 수: 원천 %s → 정제 %s (중복 제거 %d)" % (json.dumps(res["rowsIn"], ensure_ascii=False), json.dumps(res["rowsOut"], ensure_ascii=False), res["duplicatesRemoved"]),
        "- 총원 %d = 재직 %d + 휴직 %d · TO 합 %d · 입사 예정 %d(월말까지 %d) · 퇴사 예정 %d(마스터 존재 %d, 월말까지 재직자 %d)" % (
            res["headcount"], res["activeHeadcount"], res["onLeave"], res["toHeadcount"],
            res["plannedJoiners"]["total"], res["plannedJoiners"]["byMonthEnd"],
            res["plannedLeavers"]["total"], res["plannedLeavers"]["knownEmp"], res["plannedLeavers"]["byMonthEndActive"]),
        "- 부서명 정규화 %d건 · 입사일 보정 %d건 · rule별 로그 %s" % (res["orgNameCorrections"], res["hireDateCorrections"], json.dumps(res["correctionsByRule"], ensure_ascii=False)),
        "- 정규 값 도메인 이탈: %s" % (json.dumps(res["domainViolations"], ensure_ascii=False) if res["domainViolations"] else "0건"),
        "- §2-7 정본 대조(targetCheck): %s" % ("통과" if tc["passed"] else "불일치 %d건(실패한 것 참조)" % len(tc["mismatches"])),
        "- 로그 rule 어휘 = §2-5 (%d행, 원천 필드 단위 1행) · 정제 헤더 = §3" % len(cl.log_entries),
    ]
    handover = [
        "- headcount-statistician · attrition-risk-scorer: `%s` (1사번 1행 %d, 파생 필드 %s 포함). unresolvedFlags 는 `;` 구분, 미해결 행도 통계에 포함" % (
            CLEAN_PATHS["headcount-master"], res["rowsOut"]["headcount-master"], ",".join(DERIVED_FIELDS)),
        "- headcount-forecaster: `%s`(deptCode 기준 TO) · `%s`(plannedHireDate ≤ 월말) · `%s`(unknown-emp 제외, stale-planned-leaver 포함, 휴직자는 재직 기준 예측 제외 §4-5)" % (
            CLEAN_PATHS["to-plan"], CLEAN_PATHS["planned-joiners"], CLEAN_PATHS["planned-leavers"]),
        "- payroll-close-analyst · onboarding-plan-analyst: unresolvedFlags 어휘 = org-unknown / date-logic / status-inconsistency / missing-required / stale-planned-leaver / unknown-emp / code-variant / date-format / hire-date-format",
        "- people-data-auditor: `%s` 의 rowRef(사번·rowIndex)+field 를 정답지와 대조. to-plan·planned-joiners 는 사번이 없어 rowRef.사번 이 빈값 — source+rowIndex+field 로 대조. `%s` 의 orgNameCorrections/hireDateCorrections/duplicatesRemoved 가 17/31/8(데모)" % (LOG_PATH, SUMMARY_PATH),
        "- 미해결 %d건의 질문은 `%s`.unresolvedItems — 답을 받으면 원천을 고치지 말고 org-chart formerNames·원천 재수집으로 반영해 클린징을 재실행한다(원천 보존·감사 추적)" % (res["unresolvedCount"], SUMMARY_PATH),
        "- 상태 %s · 소요 %.2fs · 반환 데이터는 stdout 마지막 줄 JSON" % (res["status"], res["durationSeconds"]),
    ]
    write_handoff(root, cl.as_of_iso, {
        "시도한 것": ["- %s 실행 완료: `python3 %s %s`" % (now_iso(), SCRIPT_REL, argv_text),
                   "- 중복 해소(최종수정일 최신) → 표기 정규화(성별·직군·레벨·고용유형·재직상태·휴직유형) → 일자 보정(ISO, 2자리 연도 20xx, Excel 일련번호) → 상태 정합(date-logic·status-inconsistency·missing-required) → 조직 정규화 + 4개 조직 그룹 부여(org-unknown 은 직군→조직 임시 배정) → 파생 필드 → 정제 CSV 4종 + cleansing-log.jsonl + cleansing-summary.json",
                   "- 원천은 덮어쓰지 않았고 정답지는 읽지 않았다"],
        "본 데이터·근거": ["- 원천: " + ", ".join("%s(%d행)" % (RAW_PATHS[s], res["rowsIn"][s]) for s in SOURCES),
                      "- 기준표: %s(%d개 조직, 그룹 %s) · %s(%s)" % (
                          ORG_CHART_PATH, len(cl.resolver.depts), json.dumps(sorted(set(cl.org_group_mapping().values())), ensure_ascii=False),
                          STAGES_PATH, ("스테이지 %s" % cl.stages.names()) if cl.stages else "없음 — stage 미파생"),
                      "- 규칙: DATA_CONTRACT v2 §2-5(defectType 어휘) · §2-8(결정적 보정 규칙·파생) · §3(정제 shape) · §4-5(unknown-emp/stale/휴직자 처리) · GLOSSARY 클린징 절",
                      "- 기준일 %s · 월말 %s" % (cl.as_of_iso, cl.month_end_iso)],
        "실패한 것": fails,
        "검증된 것": verified,
        "다음 agent 인계점": handover,
    })


def handoff_failure(root, as_of_iso, argv_text, error):
    write_handoff(root, as_of_iso, {
        "시도한 것": ["- %s 실행 실패: `python3 %s %s`" % (now_iso(), SCRIPT_REL, argv_text)],
        "본 데이터·근거": ["- 읽으려던 파일: %s, %s, %s" % (ORG_CHART_PATH, STAGES_PATH, ", ".join(RAW_PATHS[s] for s in SOURCES))],
        "실패한 것": ["- %s" % error, "- 산출물(data/clean/*)은 쓰지 않았다"],
        "검증된 것": ["- 없음"],
        "다음 agent 인계점": ["- 하류로 내려가지 않는다. 입력 누락이면 people-data-collector 재실행, 헤더 불일치면 계약 §2 와 원천 헤더를 대조한다"],
    })


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main(argv=None):
    ap = argparse.ArgumentParser(description="Zero Company HR ② 클린징 — DATA_CONTRACT v2 §2-8/§3 구현")
    ap.add_argument("--root", default=DEFAULT_ROOT, help="프로젝트 루트 (기본 %s)" % DEFAULT_ROOT)
    ap.add_argument("--as-of", default=DEFAULT_AS_OF, help="기준일 YYYY-MM-DD (기본 %s)" % DEFAULT_AS_OF)
    args = ap.parse_args(argv)
    started = time.time()
    root = os.path.abspath(args.root)
    argv_text = "--root %s --as-of %s" % (root, args.as_of)
    try:
        try:
            as_of = date.fromisoformat(args.as_of)
        except ValueError:
            raise CleanseError("--as-of 형식 오류: %s (YYYY-MM-DD)" % args.as_of, 1)
        if not os.path.isdir(root):
            raise CleanseError("--root 디렉토리 없음: %s" % root, 3)
        handoff_start(root, as_of.isoformat(), argv_text)

        org_rows = read_csv_rows(os.path.join(root, ORG_CHART_PATH), ORG_REQUIRED_COLUMNS, "조직 체계")
        resolver = OrgResolver([r for _i, r in org_rows])
        if not resolver.depts:
            raise CleanseError("조직 체계에 조직이 없음: %s" % ORG_CHART_PATH, 3)
        stages = read_stages(os.path.join(root, STAGES_PATH))
        raw = {}
        for source in SOURCES:
            raw[source] = read_csv_rows(os.path.join(root, RAW_PATHS[source]), RAW_HEADERS[source], "원천 %s" % source)

        cl = Cleanser(root, as_of, resolver, stages)
        if len(resolver.depts) != EXPECTED_DEPT_COUNT:
            cl.warnings.append("org-chart 조직 수 %d ≠ %d — 계약 §1 과 다름" % (len(resolver.depts), EXPECTED_DEPT_COUNT))
        if stages is None:
            cl.warnings.append("%s 없음 — stage 를 파생하지 못해 빈값으로 둠" % STAGES_PATH)
            cl.degradations.append("company-stages.json 없음(stage 빈값)")
        cl.cleanse_master(raw["headcount-master"])
        cl.cleanse_to_plan(raw["to-plan"])
        cl.cleanse_joiners(raw["planned-joiners"])
        cl.cleanse_leavers(raw["planned-leavers"])
        if stages is not None and stages.before_first:
            cl.warnings.append("입사일이 첫 스테이지 시작일 이전인 행 %d — 첫 스테이지(%s)로 둠" % (stages.before_first, stages.names()[0]))
        for k, msg in (("emptyBirth", "생년월일 빈값(ageBand 빈값) %d행"), ("emptyPrior", "입사전경력 빈값(0으로 계산) %d행"),
                       ("leaveTypeOnActive", "재직인데 휴직유형 있음 %d행(값 유지)"), ("contractEndOnRegular", "정규직인데 계약종료일 있음 %d행(값 유지)")):
            if cl.counters[k]:
                cl.warnings.append(msg % cl.counters[k])
        if cl.counters["statusOutOfDomain"]:
            cl.degradations.append("재직상태 정규 값 밖 %d행(재직/휴직 집계에서 빠짐)" % cl.counters["statusOutOfDomain"])
        cl.write_outputs()
        status = "partial" if cl.degradations else "ok"
        res = cl.result(started, status)
        handoff_finish(root, cl, res, argv_text)
        print(json.dumps(res, ensure_ascii=False))
        return 0
    except CleanseError as e:
        msg = str(e)
        if os.path.isdir(root):
            handoff_failure(root, args.as_of, argv_text, msg)
        print(json.dumps({"status": "error", "errorType": "CleanseError", "error": msg, "asOfDate": args.as_of,
                          "handoffLog": HANDOFF_PATH, "durationSeconds": round(time.time() - started, 2)}, ensure_ascii=False))
        return e.exit_code
    except Exception as e:  # 예기치 못한 오류도 반환 데이터로 남긴다 (stderr 에 traceback)
        traceback.print_exc(file=sys.stderr)
        msg = "%s: %s" % (type(e).__name__, e)
        if os.path.isdir(root):
            handoff_failure(root, args.as_of, argv_text, msg)
        print(json.dumps({"status": "error", "errorType": type(e).__name__, "error": msg, "asOfDate": args.as_of,
                          "handoffLog": HANDOFF_PATH, "durationSeconds": round(time.time() - started, 2)}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    sys.exit(main())
