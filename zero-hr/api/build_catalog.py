# -*- coding: utf-8 -*-
"""build_catalog.py — api/catalog.py(단일 원본) → api/tools.json(Anthropic) + api/tools.openai.json(OpenAI).

실행: python3 api/build_catalog.py [--root ROOT] [--check]
  --check : 파일을 쓰지 않고 현재 파일이 원본과 같은지만 확인(다르면 exit 1). 테스트·CI 용.
두 파일은 같은 원본에서 나오므로 서로 어긋날 수 없다. 손으로 고치지 말 것.
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from api import catalog  # noqa: E402


def render(root):
    return {
        os.path.join(root, "api", "tools.json"): json.dumps(catalog.anthropic_tools(), ensure_ascii=False, indent=2) + "\n",
        os.path.join(root, "api", "tools.openai.json"): json.dumps(catalog.openai_tools(), ensure_ascii=False, indent=2) + "\n",
    }


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=os.path.dirname(HERE))
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args(argv)
    files = render(a.root)
    drift = []
    for path, text in files.items():
        if a.check:
            cur = open(path, encoding="utf-8").read() if os.path.exists(path) else None
            if cur != text:
                drift.append(path)
        else:
            with open(path, "w", encoding="utf-8") as f:
                f.write(text)
    n = len(catalog.TOOLS)
    if a.check:
        print(json.dumps({"tools": n, "drift": drift, "ok": not drift}, ensure_ascii=False))
        return 1 if drift else 0
    print(json.dumps({"tools": n, "static": len(catalog.static_tool_names()), "written": sorted(os.path.relpath(p, a.root) for p in files)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
