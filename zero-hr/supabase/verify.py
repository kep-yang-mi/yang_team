#!/usr/bin/env python3
"""verify.py — Supabase 적재 결과를 계약 정본과 대사한다 (DATA_CONTRACT §13, §14).

적재가 "성공했다"는 seed 의 자기 보고이고, 이 스크립트는 **저장소에서 다시 읽어** 계약 수치와 맞는지 본다.
같은 숫자가 두 곳에 있다는 사실만으로는 대사가 아니기 때문이다(reconciliation-policy).

검사: 행 수(employees 427 / to_plan 11·합 422 / planned_joiners 27 / planned_leavers 19 / departments 11),
      상태 분해(재직 406 · 휴직 21), 제품별 최신 스냅샷 존재와 그 안의 월말 예측(411)·gap(−11) 일치,
      anon 키로 employees 가 보이지 않는지(pii-minimization-policy).
산출: supabase/verify-result.json · 종료 코드 0 통과 / 2 불일치 / 3 환경 없음.
"""
import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TIMEOUT = 30
EXPECTED = {"employees": 427, "to_plan": 11, "planned_joiners": 27, "planned_leavers": 19, "departments": 11}


def load_env(path):
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k, v = k.strip(), v.strip().strip('"').strip("'")
            if k and v and not os.environ.get(k):
                os.environ[k] = v


def rest(url, key, path, params=None, want_count=False):
    q = urllib.parse.urlencode(params or {})
    full = "%s/rest/v1/%s%s" % (url.rstrip("/"), path, ("?" + q) if q else "")
    req = urllib.request.Request(full, headers={
        "apikey": key, "Authorization": "Bearer " + key,
        "Accept": "application/json",
        "Prefer": "count=exact" if want_count else "",
    })
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            body = resp.read().decode("utf-8")
            cr = resp.headers.get("Content-Range") or ""
            count = None
            if "/" in cr:
                tail = cr.rsplit("/", 1)[1]
                count = int(tail) if tail.isdigit() else None
            return json.loads(body or "[]"), count, None
    except urllib.error.HTTPError as exc:
        return None, None, "HTTP %s %s" % (exc.code, exc.read().decode("utf-8", "replace")[:160])
    except Exception as exc:
        return None, None, "%s: %s" % (type(exc).__name__, exc)


def check(results, name, actual, expected, note=""):
    ok = actual == expected
    results.append({"check": name, "expected": expected, "actual": actual, "passed": ok, "note": note})
    return ok


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=ROOT)
    args = ap.parse_args(argv)
    load_env(os.path.join(args.root, ".env.local"))
    url = os.environ.get("SUPABASE_URL")
    svc = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    anon = os.environ.get("SUPABASE_ANON_KEY")
    if not url or not svc:
        print(json.dumps({"status": "blocked", "error": "SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY 없음"}, ensure_ascii=False))
        return 3

    forecast_path = os.path.join(args.root, "data", "stats", "month-end-forecast.json")
    forecast = json.load(open(forecast_path, encoding="utf-8")) if os.path.exists(forecast_path) else {}
    totals = (forecast.get("totals") or {})
    results = []

    for table, expected in EXPECTED.items():
        rows, count, err = rest(url, svc, table, {"select": "*", "limit": 1}, want_count=True)
        if err:
            results.append({"check": "%s 행 수" % table, "expected": expected, "actual": None, "passed": False, "note": err})
            continue
        check(results, "%s 행 수" % table, count, expected)

    for status, expected in (("재직", 406), ("휴직", 21)):
        rows, count, err = rest(url, svc, "employees", {"select": "emp_id", "status": "eq.%s" % status, "limit": 1}, want_count=True)
        check(results, "employees status=%s" % status, count if not err else None, expected, err or "")

    rows, _, err = rest(url, svc, "to_plan", {"select": "to_headcount"})
    to_sum = sum(int(r.get("to_headcount") or 0) for r in (rows or [])) if not err else None
    check(results, "to_plan 정원 합", to_sum, 422, err or "")

    products = ["insight", "payroll", "onboard", "comparison", "app", "decision"]
    present = []
    for product in products:
        rows, _, err = rest(url, svc, "report_snapshots",
                            {"select": "product,as_of_date,created_at", "product": "eq.%s" % product,
                             "order": "created_at.desc", "limit": 1})
        if rows:
            present.append(product)
    local = [p for p in products if os.path.exists(os.path.join(args.root, "site", "data", "%s.json" % p))]
    check(results, "report_snapshots 제품 수", sorted(present), sorted(local), "로컬 스냅샷과 같은 집합")

    rows, _, err = rest(url, svc, "report_snapshots",
                        {"select": "payload", "product": "eq.insight", "order": "created_at.desc", "limit": 1})
    snap_me = None
    if rows and rows[0].get("payload"):
        snap_me = (((rows[0]["payload"].get("forecast") or {}).get("totals") or {}).get("forecastMonthEnd"))
    check(results, "최신 insight 스냅샷 월말 예측", snap_me, totals.get("forecastMonthEnd", 411))
    snap_gap = None
    if rows and rows[0].get("payload"):
        snap_gap = (((rows[0]["payload"].get("forecast") or {}).get("totals") or {}).get("toGapMonthEnd"))
    check(results, "최신 insight 스냅샷 월말 gap", snap_gap, totals.get("toGapMonthEnd", -11))

    if anon:
        rows, count, err = rest(url, anon, "employees", {"select": "emp_id", "limit": 1}, want_count=True)
        blocked = bool(err) or not rows
        results.append({"check": "anon 은 employees 를 볼 수 없다", "expected": True, "actual": blocked,
                        "passed": blocked, "note": (err or "")[:120]})
        rows, count, err = rest(url, anon, "report_snapshots", {"select": "product", "limit": 1}, want_count=True)
        ok = not err and rows is not None
        results.append({"check": "anon 은 report_snapshots 를 읽을 수 있다", "expected": True, "actual": ok,
                        "passed": ok, "note": (err or "")[:120]})

    failed = [r for r in results if not r["passed"]]
    out = {"status": "ok" if not failed else "mismatch", "asOfDate": forecast.get("asOfDate"),
           "checks": results, "failed": len(failed), "total": len(results)}
    with open(os.path.join(args.root, "supabase", "verify-result.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=2)
    print(json.dumps({"status": out["status"], "passed": len(results) - len(failed), "total": len(results),
                      "failed": [{"check": r["check"], "expected": r["expected"], "actual": r["actual"], "note": r["note"]} for r in failed]},
                     ensure_ascii=False))
    return 0 if not failed else 2


if __name__ == "__main__":
    sys.exit(main())
