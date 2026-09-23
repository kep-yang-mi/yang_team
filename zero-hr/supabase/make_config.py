#!/usr/bin/env python3
"""make_config.py — 배포 시점에 site/config.js 를 환경변수로 생성한다.

anon 키는 브라우저에 노출되는 publishable 키지만, 저장소에 넣지 않는다 — 키 교체가 커밋 이력에 남으면
회수가 번거롭고, 저장소를 포크한 사람이 우리 프로젝트에 쓰기 때문이다. `.gitignore` 가 site/config.js 를 막는다.
config.js 가 없으면 페이지는 내장 스냅샷으로 동작한다(성능·정확도 동일, '실시간'만 빠진다).
"""
import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


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


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=ROOT)
    args = ap.parse_args(argv)
    load_env(os.path.join(args.root, ".env.local"))
    url = os.environ.get("SUPABASE_URL", "")
    anon = os.environ.get("SUPABASE_ANON_KEY", "")
    if not url or not anon:
        print(json.dumps({"status": "skipped", "reason": "SUPABASE_URL/ANON_KEY 없음 — 내장 스냅샷으로 동작"}, ensure_ascii=False))
        return 0
    path = os.path.join(args.root, "site", "config.js")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("// 배포 시 supabase/make_config.py 가 생성한다. 커밋하지 않는다(.gitignore).\n")
        fh.write("window.ZEROHR_CONFIG = %s;\n" % json.dumps({"supabaseUrl": url, "supabaseAnonKey": anon}, ensure_ascii=False))
    print(json.dumps({"status": "ok", "path": "site/config.js", "supabaseHost": url.split("//")[-1].split("/")[0]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
