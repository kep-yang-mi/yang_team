#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Zero Company HR — Supabase seed (DATA_CONTRACT §13).

정제 데이터(data/clean/*.clean.csv · cleansing-log.jsonl · data/reference/org-chart.csv)를
PostgREST 로 upsert 하고, site/data/{product}.json 을 report_snapshots 에 product 당 1행 적재한다.

- 표준 라이브러리만(urllib). Python 3.9.
- upsert: Prefer: resolution=merge-duplicates, 배치 200.
- 자격증명은 환경변수(SUPABASE_URL · SUPABASE_SERVICE_ROLE_KEY)에서만 읽고 값은 절대 출력하지 않는다.
- report_snapshots 는 append(멱등 갱신) — 페이지는 product 별 최신 created_at 1행만 읽는다.
- 마지막 stdout 한 줄은 요약 JSON.

사용:
  python3 supabase/seed.py --root . --dry-run
  python3 supabase/seed.py --root . --only tables
  python3 supabase/seed.py --root .
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

BATCH = 200
TIMEOUT = 60

PRODUCTS = ["insight", "payroll", "onboard", "comparison", "app", "decision"]

# ---------------------------------------------------------------- 값 변환 helpers


def _s(v):
    """빈 문자열은 NULL 로."""
    if v is None:
        return None
    v = v.strip()
    return v or None


def _i(v):
    v = _s(v)
    if v is None:
        return None
    try:
        return int(float(v))
    except ValueError:
        return None


def _f(v):
    v = _s(v)
    if v is None:
        return None
    try:
        return float(v)
    except ValueError:
        return None


def _d(v):
    """YYYY-MM-DD 만 통과. 그 외는 NULL(정제 단계에서 이미 표준화됨)."""
    v = _s(v)
    if v is None:
        return None
    if len(v) == 10 and v[4] == "-" and v[7] == "-":
        return v
    return None


# ---------------------------------------------------------------- 파일 → 행 변환

def read_csv(path):
    with open(path, "r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def rows_departments(root):
    path = os.path.join(root, "data", "reference", "org-chart.csv")
    if not os.path.exists(path):
        return []
    return [
        {
            "dept_code": _s(r.get("deptCode")),
            "department": _s(r.get("department")),
            "org_group_code": _s(r.get("orgGroupCode")),
            "org_group": _s(r.get("orgGroup")),
            "former_names": _s(r.get("formerNames")),
            "established_on": _d(r.get("establishedOn")),
        }
        for r in read_csv(path)
        if _s(r.get("deptCode"))
    ]


def rows_employees(root):
    path = os.path.join(root, "data", "clean", "headcount-master.clean.csv")
    if not os.path.exists(path):
        return []
    return [
        {
            "emp_id": _s(r.get("empId")),
            "name": _s(r.get("name")),
            "gender": _s(r.get("gender")),
            "birth_date": _d(r.get("birthDate")),
            "age_band": _s(r.get("ageBand")),
            "org_group_code": _s(r.get("orgGroupCode")),
            "org_group": _s(r.get("orgGroup")),
            "dept_code": _s(r.get("deptCode")),
            "department": _s(r.get("department")),
            "job_family": _s(r.get("jobFamily")),
            "level": _s(r.get("level")),
            "stage": _s(r.get("stage")),
            "employment_type": _s(r.get("employmentType")),
            "status": _s(r.get("status")),
            "leave_type": _s(r.get("leaveType")),
            "leave_start": _d(r.get("leaveStart")),
            "hire_date": _d(r.get("hireDate")),
            "contract_end_date": _d(r.get("contractEndDate")),
            "prior_experience_months": _i(r.get("priorExperienceMonths")),
            "tenure_years": _f(r.get("tenureYears")),
            "tenure_year": _i(r.get("tenureYear")),
            "tenure_band": _s(r.get("tenureBand")),
            "total_experience_years": _f(r.get("totalExperienceYears")),
            "total_experience_band": _s(r.get("totalExperienceBand")),
            "unresolved_flags": _s(r.get("unresolvedFlags")),
            "source_row_index": _i(r.get("sourceRowIndex")),
        }
        for r in read_csv(path)
        if _s(r.get("empId"))
    ]


def rows_to_plan(root):
    path = os.path.join(root, "data", "clean", "to-plan.clean.csv")
    if not os.path.exists(path):
        return []
    return [
        {
            "dept_code": _s(r.get("deptCode")),
            "department": _s(r.get("department")),
            "org_group_code": _s(r.get("orgGroupCode")),
            "to_headcount": _i(r.get("toHeadcount")),
            "effective_month": _s(r.get("effectiveMonth")),
        }
        for r in read_csv(path)
        if _s(r.get("deptCode"))
    ]


def rows_planned_joiners(root):
    path = os.path.join(root, "data", "clean", "planned-joiners.clean.csv")
    if not os.path.exists(path):
        return []
    return [
        {
            "joiner_id": _s(r.get("joinerId")),
            "name": _s(r.get("name")),
            "dept_code": _s(r.get("deptCode")),
            "department": _s(r.get("department")),
            "job_family": _s(r.get("jobFamily")),
            "level": _s(r.get("level")),
            "employment_type": _s(r.get("employmentType")),
            "gender": _s(r.get("gender")),
            "birth_date": _d(r.get("birthDate")),
            "planned_hire_date": _d(r.get("plannedHireDate")),
            "prior_experience_months": _i(r.get("priorExperienceMonths")),
            "unresolved_flags": _s(r.get("unresolvedFlags")),
        }
        for r in read_csv(path)
        if _s(r.get("joinerId"))
    ]


def rows_planned_leavers(root):
    path = os.path.join(root, "data", "clean", "planned-leavers.clean.csv")
    if not os.path.exists(path):
        return []
    out = []
    for r in read_csv(path):
        emp_id = _s(r.get("empId"))
        term = _d(r.get("plannedTerminationDate"))
        if not emp_id or not term:
            continue  # 복합 PK 구성 불가 행은 적재하지 않는다(seed 요약의 skipped 로 보고)
        out.append(
            {
                "emp_id": emp_id,
                "planned_termination_date": term,
                "dept_code": _s(r.get("deptCode")),
                "separation_type": _s(r.get("separationType")),
                "separation_reason": _s(r.get("separationReason")),
                "unresolved_flags": _s(r.get("unresolvedFlags")),
            }
        )
    return out


def rows_cleansing_log(root):
    path = os.path.join(root, "data", "clean", "cleansing-log.jsonl")
    if not os.path.exists(path):
        return []
    out = []
    seen = set()
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            canonical = json.dumps(rec, sort_keys=True, ensure_ascii=False)
            log_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
            if log_hash in seen:  # 동일 레코드 중복 행 — upsert 배치 내 충돌 방지
                continue
            seen.add(log_hash)
            corrected = rec.get("correctedValue")
            out.append(
                {
                    "log_hash": log_hash,
                    "source": rec.get("source"),
                    "row_ref": rec.get("rowRef"),
                    "field": rec.get("field"),
                    "raw_value": None if rec.get("rawValue") is None else str(rec.get("rawValue")),
                    "corrected_value": None if corrected is None else str(corrected),
                    "rule": rec.get("rule"),
                    "confidence": rec.get("confidence"),
                    "unresolved": bool(rec.get("unresolved")),
                }
            )
    return out


TABLES = [
    # (table, on_conflict 컬럼, 행 생성 함수)
    ("departments", "dept_code", rows_departments),
    ("employees", "emp_id", rows_employees),
    ("to_plan", "dept_code", rows_to_plan),
    ("planned_joiners", "joiner_id", rows_planned_joiners),
    ("planned_leavers", "emp_id,planned_termination_date", rows_planned_leavers),
    ("cleansing_log", "log_hash", rows_cleansing_log),
]


# ---------------------------------------------------------------- 스냅샷

def snapshot_rows(root, as_of_date):
    """site/data/{product}.json → report_snapshots 행. payload 는 파일 내용 그대로."""
    out = []
    data_dir = os.path.join(root, "site", "data")
    for product in PRODUCTS:
        path = os.path.join(data_dir, product + ".json")
        if not os.path.exists(path):
            continue
        with open(path, "r", encoding="utf-8") as fh:
            payload = json.load(fh)
        row_as_of = as_of_date
        if isinstance(payload, dict) and isinstance(payload.get("asOfDate"), str):
            row_as_of = payload["asOfDate"]
        out.append(
            {
                "product": product,
                "as_of_date": row_as_of,
                "payload": payload,
                "_bytes": os.path.getsize(path),
            }
        )
    return out


def default_as_of(root):
    path = os.path.join(root, "data", "stats", "month-end-forecast.json")
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as fh:
                return json.load(fh).get("asOfDate")
        except (ValueError, OSError):
            pass
    return None


# ---------------------------------------------------------------- PostgREST

class Rest(object):
    def __init__(self, base_url, service_key):
        self.base = base_url.rstrip("/") + "/rest/v1"
        self._key = service_key

    def _headers(self, prefer):
        return {
            "apikey": self._key,
            "Authorization": "Bearer " + self._key,
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Prefer": prefer,
        }

    def post(self, table, rows, prefer, on_conflict=None):
        url = self.base + "/" + table
        if on_conflict:
            url += "?on_conflict=" + urllib.parse.quote(on_conflict, safe=",")
        body = json.dumps(rows, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(url, data=body, headers=self._headers(prefer), method="POST")
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                return resp.status, resp.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")[:400]
            raise RuntimeError(
                "PostgREST %s %s -> HTTP %s: %s" % ("POST", table, exc.code, detail)
            )
        except urllib.error.URLError as exc:
            raise RuntimeError("PostgREST %s %s -> network error: %s" % ("POST", table, exc.reason))

# ---------------------------------------------------------------- main

def main(argv=None):
    ap = argparse.ArgumentParser(description="Supabase seed (PostgREST upsert, stdlib only)")
    ap.add_argument("--root", default=os.getcwd(), help="프로젝트 루트")
    ap.add_argument("--dry-run", action="store_true", help="네트워크 호출 없이 적재 계획만 출력")
    ap.add_argument("--only", choices=["tables", "snapshots", "all"], default="all")
    ap.add_argument("--as-of", default=None, help="report_snapshots.as_of_date (기본: month-end-forecast.asOfDate)")
    args = ap.parse_args(argv)

    root = os.path.abspath(args.root)
    as_of = args.as_of or default_as_of(root)

    summary = {
        "status": "ok",
        "mode": "dry-run" if args.dry_run else "apply",
        "only": args.only,
        "root": root,
        "asOfDate": as_of,
        "tables": {},
        "snapshots": [],
        "errors": [],
    }

    plan_tables = []
    if args.only in ("tables", "all"):
        for table, conflict, fn in TABLES:
            rows = fn(root)
            plan_tables.append((table, conflict, rows))
            summary["tables"][table] = {"rows": len(rows), "loaded": 0, "batches": 0}

    plan_snapshots = []
    if args.only in ("snapshots", "all"):
        plan_snapshots = snapshot_rows(root, as_of)
        for snap in plan_snapshots:
            summary["snapshots"].append(
                {
                    "product": snap["product"],
                    "asOfDate": snap["as_of_date"],
                    "payloadBytes": snap["_bytes"],
                    "loaded": False,
                }
            )

    if args.dry_run:
        # 네트워크 호출 없음. 자격증명 존재 여부만 표시(값은 읽지 않는다).
        summary["envPresent"] = {
            "SUPABASE_URL": bool(os.environ.get("SUPABASE_URL")),
            "SUPABASE_SERVICE_ROLE_KEY": bool(os.environ.get("SUPABASE_SERVICE_ROLE_KEY")),
        }
        for table, _conflict, rows in plan_tables:
            sys.stderr.write("[dry-run] upsert %-16s %4d rows (%d batch)\n"
                             % (table, len(rows), (len(rows) + BATCH - 1) // BATCH))
        for snap in plan_snapshots:
            sys.stderr.write("[dry-run] insert report_snapshots product=%-10s payload=%d bytes\n"
                             % (snap["product"], snap["_bytes"]))
        print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
        return 0

    url = os.environ.get("SUPABASE_URL", "").strip()
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    if not url or not key:
        summary["status"] = "error"
        summary["errors"].append(
            "SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY 환경변수가 비어 있습니다. "
            "`set -a; source .env.local; set +a` 후 다시 실행하세요."
        )
        print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
        return 1

    rest = Rest(url, key)

    for table, conflict, rows in plan_tables:
        loaded = 0
        batches = 0
        for start in range(0, len(rows), BATCH):
            chunk = rows[start:start + BATCH]
            try:
                rest.post(
                    table,
                    chunk,
                    prefer="resolution=merge-duplicates,return=minimal",
                    on_conflict=conflict,
                )
            except RuntimeError as exc:
                summary["status"] = "error"
                summary["errors"].append(str(exc))
                break
            loaded += len(chunk)
            batches += 1
            sys.stderr.write("upsert %-16s %d/%d\n" % (table, loaded, len(rows)))
        summary["tables"][table]["loaded"] = loaded
        summary["tables"][table]["batches"] = batches
        if summary["status"] == "error":
            break

    if summary["status"] != "error":
        for idx, snap in enumerate(plan_snapshots):
            row = {"product": snap["product"], "as_of_date": snap["as_of_date"], "payload": snap["payload"]}
            try:
                rest.post("report_snapshots", [row], prefer="return=minimal")
            except RuntimeError as exc:
                summary["status"] = "error"
                summary["errors"].append(str(exc))
                break
            summary["snapshots"][idx]["loaded"] = True
            sys.stderr.write("insert report_snapshots product=%s\n" % snap["product"])

    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0 if summary["status"] == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())
