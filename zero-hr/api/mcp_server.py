#!/usr/bin/env python3
"""mcp_server.py — Function Call 인터페이스 MCP stdio 서버 (DATA_CONTRACT §17-2).

JSON-RPC 2.0 over stdio, 줄 단위(newline-delimited). initialize / notifications/initialized /
tools/list / tools/call / ping 을 처리한다. 표준 라이브러리만 사용.

등록 예시는 api/mcp.example.json 참조.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from api import zerohr_tools as tools  # noqa: E402

ROOT = os.environ.get("ZERO_HR_ROOT") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROTOCOL_VERSION = "2025-06-18"


def result(req_id, payload):
    return {"jsonrpc": "2.0", "id": req_id, "result": payload}


def error(req_id, code, message):
    return {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}}


def handle(req):
    method = req.get("method")
    req_id = req.get("id")
    params = req.get("params") or {}
    if method == "initialize":
        return result(req_id, {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": "zerohr-function-call", "version": "1.0.0"},
            "instructions": "Zero Company HR — Everyday People Agent. 급여·온보딩·인사 총괄 시스템의 agent가 "
                            "인원 통계·월말 예측·급여 마감·온보딩 계획을 도구로 호출한다. 외부 효과가 있는 행위는 "
                            "approval.request 로 승인 대기 기록만 남긴다.",
        })
    if method in ("notifications/initialized", "initialized"):
        return None
    if method == "ping":
        return result(req_id, {})
    if method == "tools/list":
        return result(req_id, {"tools": tools.list_tools()})
    if method == "tools/call":
        name = params.get("name")
        args = params.get("arguments") or {}
        try:
            payload = tools.dispatch(name, args, root=ROOT)
        except tools.ToolError as exc:
            return result(req_id, {"content": [{"type": "text", "text": "도구 오류: %s" % exc}], "isError": True})
        except Exception as exc:
            return result(req_id, {"content": [{"type": "text", "text": "%s: %s" % (type(exc).__name__, exc)}], "isError": True})
        text = json.dumps(payload, ensure_ascii=False, indent=2)
        return result(req_id, {"content": [{"type": "text", "text": text}], "isError": False})
    if req_id is None:
        return None
    return error(req_id, -32601, "Method not found: %s" % method)


def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except ValueError:
            sys.stdout.write(json.dumps(error(None, -32700, "Parse error")) + "\n")
            sys.stdout.flush()
            continue
        response = handle(req)
        if response is not None:
            sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
            sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
