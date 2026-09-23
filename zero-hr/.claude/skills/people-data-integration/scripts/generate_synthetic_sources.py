#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
generate_synthetic_sources.py — 가상 원천 4종 + 조직 체계 생성기 (DATA_CONTRACT v2 §1·§2)

데모 고객사 ㈜온다테크의 원천 데이터를 "고객사에서 받은 그대로"의 형상(한글 헤더, 결함 포함)으로 만들고,
주입한 결함의 정답지(injected-defects.json)를 남긴다. 정답 기준(true) 상태는 §2-7 정본 수치를 **정확히** 만족한다.

산출물 (--root 기준):
  data/reference/org-chart.csv            §1  조직 그룹(4) > 조직(11), formerNames 별칭 사전
  data/reference/company-stages.json      §1  스테이지 경계일 (재직 406 입사일 순위 49/151/140/66 으로 산출)
  data/raw/headcount-master.csv           §2-1 427행(재직 406 + 휴직 21) + 중복 구버전 8행 = 435행
  data/raw/to-plan.csv                    §2-2 11행, 정원 합 422
  data/raw/planned-joiners.csv            §2-3 27행 (9월 말까지 19 + 10월 8)
  data/raw/planned-leavers.csv            §2-4 19행 (9월 유효 14 + 10월 4 + 마스터에 없는 사번 1)
  data/raw/injected-defects.json          §2-6 정답지
  _workspace/handoff/01-collect.md        핸드오프 로그 (5개 H2)

CLI:
  python3 generate_synthetic_sources.py --root /Users/yang/development/zero-hr --as-of 2026-09-23 --self-check
  --no-bom       원천 CSV를 BOM 없는 utf-8로 쓴다 (기본은 utf-8-sig — 고객사 엑셀 내보내기 형상)
  --self-check   생성 후 원천을 다시 읽어 §2-8 규칙으로 정답 상태를 복원하고 §2-7 정본과 대조한다 (불일치 시 exit 1)
  --check-only   생성하지 않고 기존 산출물에 self-check만 수행한다

Python 3.9 표준 라이브러리만. random.seed(20260923) 고정 — 같은 인자면 같은 파일이 나온다.
마지막 stdout 1행은 워크플로우가 파싱하는 요약 JSON이다.
"""

import argparse
import csv
import datetime as dt
import json
import os
import random
import sys
import time
import unicodedata

SEED = 20260923
DEFAULT_ROOT = "/Users/yang/development/zero-hr"
DEFAULT_AS_OF = "2026-09-23"
COMPANY_FOUNDED = dt.date(2019, 1, 1)
SCRIPT_REL = ".claude/skills/people-data-integration/scripts/generate_synthetic_sources.py"

# ---------------------------------------------------------------------------
# §1 조직 체계
# ---------------------------------------------------------------------------
ORG_HEADER = ["orgGroupCode", "orgGroup", "deptCode", "department", "formerNames", "establishedOn"]
ORG_ROWS = [
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
DEPT = {r[2]: {"orgGroupCode": r[0], "orgGroup": r[1], "deptCode": r[2], "department": r[3],
               "formerNames": r[4], "establishedOn": r[5]} for r in ORG_ROWS}
DEPT_ORDER = [r[2] for r in ORG_ROWS]
DEPT_NAME = {r[2]: r[3] for r in ORG_ROWS}

# §2-7 조직별 정본: deptCode -> (HC 재직, OL 휴직, TO, in(9월), out(9월))
ORG_TRUTH = {
    "D01": (10, 0, 10, 0, 0), "D02": (51, 3, 54, 3, 1), "D03": (104, 6, 112, 5, 4), "D04": (25, 1, 26, 1, 1),
    "D05": (40, 2, 34, 2, 1), "D06": (58, 3, 62, 3, 3), "D07": (30, 1, 32, 1, 1), "D08": (40, 3, 42, 2, 1),
    "D09": (18, 1, 18, 1, 0), "D10": (19, 1, 20, 1, 1), "D11": (11, 0, 12, 0, 1),
}
# 10월 입사 예정 8 / 10월 퇴사 예정 4
OCT_JOINERS = {"D03": 3, "D05": 2, "D06": 2, "D02": 1}
OCT_LEAVERS = {"D03": 1, "D06": 1, "D08": 1, "D07": 1}

# 직군 ↔ 조직 (§2-7). Data & AI 조직만 혼합(Data/AI 24 + Engineering 12 + Product 4)
DEPT_FAMILY = {"D01": "Executive", "D02": "Product", "D03": "Engineering", "D04": "Design", "D05": "Data/AI",
               "D06": "Sales", "D07": "Marketing", "D08": "Customer Success", "D09": "People", "D10": "Finance",
               "D11": "Legal"}
FAMILY_DEPT = {v: k for k, v in DEPT_FAMILY.items()}          # §2-8 org-unknown 임시 배정 매핑
D05_FAMILY_MIX = [("Data/AI", 24), ("Engineering", 12), ("Product", 4)]

# §2-7 속성 분포 (재직 406 기준; 고용유형만 총원 427)
LEVELS = ["IC1", "IC2", "IC3", "Senior", "Lead", "Manager", "Director", "VP"]
LEVEL_COUNTS = [33, 65, 82, 89, 55, 44, 25, 13]
GENDER_COUNTS = [("여성", 188), ("남성", 195), ("미응답", 23)]
AGE_BANDS = [("20대", 82, 23, 29), ("30대", 221, 30, 39), ("40대", 83, 40, 49), ("50대+", 20, 50, 58)]
TENURE_BANDS = [("1년 미만", 54, 1, 365), ("1~3년", 151, 366, 1095), ("3~5년", 103, 1096, 1826), ("5년+", 98, 1827, None)]
EXP_BANDS = [("0~3년", 56, 0.0, 3.0), ("3~7년", 137, 3.0, 7.0), ("7~12년", 142, 7.0, 12.0), ("12년+", 71, 12.0, 30.0)]
STAGE_COUNTS = [("Seed", 49), ("Series A", 151), ("Scale-up", 140), ("Enterprise", 66)]
EMP_TYPE_ACTIVE = {"정규직": 335, "계약직": 29, "인턴": 19, "파견": 23}      # 427 기준 354/31/19/23 − 휴직 19/2
EMP_TYPE_LEAVE = {"정규직": 19, "계약직": 2}
EMP_TYPE_ALL = {"정규직": 354, "계약직": 31, "인턴": 19, "파견": 23}
CONTRACT_TYPES = ("계약직", "인턴", "파견")
LEAVER_REASONS = [("자발퇴사", 5), ("계약만료", 3), ("조직개편", 2), ("성과/적합도", 2), ("개인사유", 2)]
OCT_LEAVER_REASONS = ["자발퇴사", "개인사유", "자발퇴사", "조직개편"]
LEAVE_TYPES = ["육아휴직", "질병휴직", "기타"]
MIN_EXPIRING_90D = 8

# ---------------------------------------------------------------------------
# §2 원천 헤더 (순서 고정)
# ---------------------------------------------------------------------------
MASTER_HEADER = ["사번", "성명", "성별", "생년월일", "소속", "직군", "레벨", "고용유형", "재직상태", "휴직유형",
                 "휴직시작일", "입사일", "계약종료일", "입사전경력(개월)", "최종수정일"]
TO_HEADER = ["조직", "정원", "기준월"]
JOINER_HEADER = ["성명", "소속", "직군", "레벨", "고용유형", "성별", "생년월일", "입사예정일", "입사전경력(개월)"]
LEAVER_HEADER = ["사번", "성명", "소속", "퇴사예정일", "퇴직사유"]

# ---------------------------------------------------------------------------
# §2-5 결함 사전
# ---------------------------------------------------------------------------
ORG_OLD_NAME = [("D09", "HR"), ("D03", "R&D"), ("D08", "Customer Support"), ("D04", "UX"), ("D05", "AI Lab"), ("D06", "BizDev")]
ORG_VARIANT = [("D11", "Legal and Compliance"), ("D11", "Legal&Compliance"), ("D05", "Data and AI"), ("D08", "Customer success")]
ORG_TYPO = [("D03", "Enginering"), ("D07", "Marketting"), ("D10", "Finanace")]
ORG_WHITESPACE = [("D06", " Sales"), ("D02", "Product "), ("D08", "Customer  Success"), ("D03", "Engineering　")]
ORG_UNKNOWN = [("D07", "Growth Lab"), ("D03", "Platform")]        # 직군 매핑으로 자기 조직에 임시 배정되는 조합만
HIRE_DATE_KINDS = [("slash", 20), ("dot", 6), ("compact", 3), ("excel", 2)]
TO_ORG_VARIANTS = [("D11", "Legal and Compliance"), ("D05", "Data/AI"), ("D08", "Customer Support")]
TO_MONTH_VARIANTS = ["2026.09", "202609", "2026년 9월", "2026/09"]
JOINER_ORG_VARIANTS = [("D05", "Data and AI"), ("D08", "Customer success")]
GENDER_VARIANTS = {"여성": ["F", "female", "여"], "남성": ["M", "male", "남"]}
EMP_VARIANTS = {"정규직": ["정규", "Regular", "FT"], "계약직": ["계약", "Contract"], "인턴": ["Intern"], "파견": ["Dispatch"]}
STATUS_VARIANTS = {"재직": ["재직중", "Active"], "휴직": ["휴직중", "Leave"]}
LEVEL_VARIANTS = {"IC1": ["ic1"], "IC2": ["IC-2"], "Senior": ["Sr"], "Manager": ["Mgr"], "Director": ["Dir"]}
CODE_VARIANT_PLAN = [("성별", GENDER_VARIANTS, 8), ("고용유형", EMP_VARIANTS, 9), ("재직상태", STATUS_VARIANTS, 8), ("레벨", LEVEL_VARIANTS, 8)]
REASON_FREETEXT = {"자발퇴사": "자발적 퇴사", "계약만료": "계약 기간 만료", "조직개편": "조직 개편에 따른", "성과/적합도": "성과 부진",
                   "개인사유": "개인 사정"}

# §2-8 역매핑 사전 (self-check 가 쓰는 정규화 규칙 = 클린저와 동일)
CODE_MAP = {
    "성별": {"F": "여성", "female": "여성", "여": "여성", "M": "남성", "male": "남성", "남": "남성", "": "미응답"},
    "고용유형": {"정규": "정규직", "Regular": "정규직", "FT": "정규직", "계약": "계약직", "Contract": "계약직", "Intern": "인턴", "Dispatch": "파견"},
    "재직상태": {"재직중": "재직", "Active": "재직", "휴직중": "휴직", "Leave": "휴직"},
    "레벨": {"ic1": "IC1", "IC-2": "IC2", "Sr": "Senior", "Mgr": "Manager", "Dir": "Director"},
}
REASON_KEYWORDS = [("자발", "자발퇴사"), ("만료", "계약만료"), ("계약", "계약만료"), ("개편", "조직개편"), ("조직", "조직개편"),
                   ("성과", "성과/적합도"), ("적합", "성과/적합도"), ("개인", "개인사유"), ("건강", "건강"), ("정년", "정년")]

# ---------------------------------------------------------------------------
# 한국식 가상 이름
# ---------------------------------------------------------------------------
SURNAMES = ["김", "이", "박", "최", "정", "강", "조", "윤", "장", "임", "한", "오", "서", "신", "권", "황", "안", "송", "류", "전",
            "홍", "고", "문", "양", "손", "배", "백", "허", "유", "남", "심", "노", "하", "곽", "성", "차", "주", "우", "구", "민"]
GIVEN_F = ["서연", "지우", "하은", "민서", "지민", "수아", "예은", "지아", "채원", "은서", "유진", "다은", "소율", "예린", "수빈", "지현",
           "서현", "하린", "지윤", "나은", "혜원", "가은", "세아", "윤서", "시은", "보라", "미래", "혜진", "아름", "단비", "슬기", "지영"]
GIVEN_M = ["민준", "서준", "도윤", "예준", "시우", "하준", "지호", "주원", "준서", "건우", "현우", "우진", "선우", "유찬", "정우", "승현",
           "동현", "태윤", "민재", "재원", "성민", "영준", "준혁", "지훈", "상우", "태현", "승우", "경민", "재현", "규민", "한결", "도현"]
GIVEN_N = ["지원", "현서", "수현", "하늘", "은채", "다현", "서영", "민경", "지성", "진영", "세진", "혜성", "유경", "승민", "예지", "찬영"]

# ---------------------------------------------------------------------------
# 전역 실행 컨텍스트 (기준일)
# ---------------------------------------------------------------------------
CTX = {}


def set_context(as_of):
    CTX["as_of"] = as_of
    CTX["month_end"] = dt.date(as_of.year, as_of.month, 1) + dt.timedelta(days=40)
    CTX["month_end"] = CTX["month_end"].replace(day=1) - dt.timedelta(days=1)
    nm = CTX["month_end"] + dt.timedelta(days=1)
    CTX["next_month_end"] = (nm.replace(day=1) + dt.timedelta(days=40)).replace(day=1) - dt.timedelta(days=1)
    CTX["max_tenure_days"] = (as_of - COMPANY_FOUNDED).days


def iso(d):
    return d.isoformat() if isinstance(d, dt.date) else (d or "")


def days(n):
    return dt.timedelta(days=n)


def parse_iso(s):
    return dt.date.fromisoformat(s)


def rand_date(start, end):
    """start~end 사이 임의 일자 (양끝 포함)."""
    span = (end - start).days
    return start + days(random.randint(0, max(span, 0)))


def age_on(birth, on):
    a = on.year - birth.year
    if (on.month, on.day) < (birth.month, birth.day):
        a -= 1
    return a


def birth_for_age(age, on):
    """기준일 on 에 만 age 세가 되는 생년월일 (경계일 제외)."""
    latest = dt.date(on.year - age, on.month, on.day) - days(1)          # 만 age 되는 마지막 날 직전
    earliest = dt.date(on.year - age - 1, on.month, on.day) + days(2)    # 만 age+1 되기 이틀 전
    return rand_date(earliest, latest)


def weighted(pairs):
    total = sum(w for _, w in pairs)
    r = random.uniform(0, total)
    acc = 0.0
    for v, w in pairs:
        acc += w
        if r <= acc:
            return v
    return pairs[-1][0]


def expand(pairs):
    out = []
    for v, n in pairs:
        out.extend([v] * n)
    return out


def date_variant(d, kind):
    if kind == "slash":
        return d.strftime("%Y/%m/%d")
    if kind == "dot":
        return d.strftime("%Y.%m.%d")
    if kind == "compact":
        return d.strftime("%Y%m%d")
    if kind == "excel":
        return str((d - dt.date(1899, 12, 30)).days)
    return iso(d)


def make_name(gender, used):
    for _ in range(500):
        s = random.choice(SURNAMES)
        pool = GIVEN_F if gender == "여성" else GIVEN_M if gender == "남성" else GIVEN_N + GIVEN_F + GIVEN_M
        n = s + random.choice(pool)
        if n not in used:
            used.add(n)
            return n
    n = random.choice(SURNAMES) + random.choice(GIVEN_N) + str(len(used))
    used.add(n)
    return n


def tenure_years(hire, as_of):
    return round((as_of - hire).days / 365.25, 2) if hire <= as_of else 0.0


def tenure_band(ty):
    return "1년 미만" if ty < 1 else "1~3년" if ty < 3 else "3~5년" if ty < 5 else "5년+"


def exp_band(x):
    return "0~3년" if x < 3 else "3~7년" if x < 7 else "7~12년" if x < 12 else "12년+"


def age_band(age):
    return "20대" if age < 30 else "30대" if age < 40 else "40대" if age < 50 else "50대+"


def total_exp(prior_months, ty):
    return round(prior_months / 12.0 + ty, 2)


# ---------------------------------------------------------------------------
# 파일 IO · 핸드오프 로그
# ---------------------------------------------------------------------------
def write_csv(path, header, rows, bom):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8-sig" if bom else "utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=header, lineterminator="\n")
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in header})


def read_csv(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
        f.write("\n")


def write_handoff(root, sections):
    """핸드오프 로그 5개 H2 고정 (handoff-log-policy). sections: dict(절 이름 -> 줄 목록)."""
    path = os.path.join(root, "_workspace", "handoff", "01-collect.md")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    order = ["시도한 것", "본 데이터·근거", "실패한 것", "검증된 것", "다음 agent 인계점"]
    lines = ["# 01-collect — people-data-collector 핸드오프 로그", "",
             "- 갱신: %s · 기준일 %s · seed %d" % (dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), iso(CTX.get("as_of")), SEED), ""]
    for sec in order:
        lines.append("## " + sec)
        body = sections.get(sec) or ["- (없음)"]
        lines.extend(body)
        lines.append("")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return path
