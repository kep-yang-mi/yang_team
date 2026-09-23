#!/usr/bin/env python3
"""build_static.py — 인자 없는 읽기 도구의 결과를 site/api/ 에 미리 계산해 둔다 (DATA_CONTRACT §17-2).

Vercel 정적 배포에서도 세 시스템의 agent가 fetch 한 번으로 같은 값을 받게 하기 위함이다.
role 은 executive(기본) — 성명이 필요한 도구는 정적으로 만들지 않는다.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from api import zerohr_tools as tools  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKIP_PREFIX = ("approval.",)


def argless(tool):
    schema = tool.get("input_schema") or {}
    required = schema.get("required") or []
    return [r for r in required if r != "role"] == []


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=ROOT)
    ap.add_argument("--role", default="executive")
    args = ap.parse_args(argv)
    out_dir = os.path.join(args.root, "site", "api")
    os.makedirs(out_dir, exist_ok=True)
    written, skipped = [], []
    catalog = tools.list_tools()
    for tool in catalog:
        name = tool["name"]
        if name.startswith(SKIP_PREFIX) or not argless(tool):
            skipped.append(name)
            continue
        try:
            payload = tools.dispatch(name, {"role": args.role}, root=args.root)
        except Exception as exc:
            skipped.append("%s (%s)" % (name, type(exc).__name__))
            continue
        path = os.path.join(out_dir, "%s.json" % name)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2)
        written.append(os.path.relpath(path, args.root))
    index = {
        "service": "Zero Company HR — Everyday People Agent",
        "role": args.role,
        "note": "정적 스냅샷. 인자가 필요한 도구와 approval.* 은 api/server.py 또는 api/mcp_server.py 로 호출한다.",
        "tools": [{"name": t["name"], "description": t["description"],
                   "static": os.path.basename("%s.json" % t["name"]) if "%s.json" % t["name"] in
                   [os.path.basename(w) for w in written] else None,
                   "input_schema": t["input_schema"]} for t in catalog],
    }
    with open(os.path.join(out_dir, "index.json"), "w", encoding="utf-8") as fh:
        json.dump(index, fh, ensure_ascii=False, indent=2)
    print(json.dumps({"status": "ok", "written": len(written), "skipped": skipped,
                      "outDir": os.path.relpath(out_dir, args.root)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
