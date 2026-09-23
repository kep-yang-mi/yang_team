#!/usr/bin/env python3
"""server.py — Function Call 인터페이스 HTTP 서버 (DATA_CONTRACT §17-2).

GET  /health            상태
GET  /tools             Anthropic tool_use 카탈로그
GET  /tools/openai      OpenAI function 카탈로그
POST /call  {"name": "...", "arguments": {...}}   → 봉투 응답

표준 라이브러리만 사용. 데이터는 읽기 전용으로 로드하며 재계산하지 않는다(run_scenario 제외).
"""
import argparse
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from api import zerohr_tools as tools  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class Handler(BaseHTTPRequestHandler):
    server_version = "ZeroHR-FunctionCall/1.0"

    def _send(self, code, payload):
        body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        sys.stderr.write("[api] %s\n" % (fmt % args))

    def do_OPTIONS(self):
        self._send(204, {})

    def do_GET(self):
        path = self.path.split("?")[0].rstrip("/") or "/"
        if path == "/health":
            self._send(200, {"status": "ok", "root": self.server.zerohr_root, "tools": len(tools.list_tools())})
        elif path == "/tools":
            self._send(200, tools.list_tools())
        elif path == "/tools/openai":
            self._send(200, tools.list_tools_openai())
        elif path == "/":
            self._send(200, {"status": "ok", "endpoints": ["/health", "/tools", "/tools/openai", "POST /call"]})
        else:
            self._send(404, {"status": "error", "error": "not-found", "hint": "GET /tools 또는 POST /call"})

    def do_POST(self):
        if self.path.split("?")[0].rstrip("/") != "/call":
            self._send(404, {"status": "error", "error": "not-found", "hint": "POST /call"})
            return
        try:
            length = int(self.headers.get("Content-Length") or 0)
            payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
        except (ValueError, TypeError) as exc:
            self._send(400, {"status": "error", "error": "invalid-json", "hint": str(exc)})
            return
        name = payload.get("name")
        if not name:
            self._send(400, {"status": "error", "error": "missing-name", "hint": "{\"name\": \"insight.get_executive_snapshot\"}"})
            return
        try:
            result = tools.dispatch(name, payload.get("arguments") or {}, root=self.server.zerohr_root)
        except tools.ToolError as exc:
            self._send(400, {"status": "error", "error": str(exc), "hint": "GET /tools 로 스키마 확인"})
            return
        except Exception as exc:  # 데이터 결손 등
            self._send(500, {"status": "error", "error": "%s: %s" % (type(exc).__name__, exc), "hint": "상류 산출물 확인"})
            return
        self._send(200, result)


def serve(root, port):
    httpd = HTTPServer(("127.0.0.1", port), Handler)
    httpd.zerohr_root = root
    sys.stderr.write("[api] http://127.0.0.1:%d  (tools=%d, root=%s)\n" % (port, len(tools.list_tools()), root))
    return httpd


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=ROOT)
    ap.add_argument("--port", type=int, default=8787)
    args = ap.parse_args(argv)
    httpd = serve(args.root, args.port)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        httpd.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
