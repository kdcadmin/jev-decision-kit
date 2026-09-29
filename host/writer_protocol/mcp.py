"""Stdio MCP for the workspace writer protocol. JEV does not select this."""
from __future__ import annotations

import json
import sys
from host.writer_protocol import append, compact_read, ensure, find_workspace, session_hint

TOOLS = [
    {
        "name": "writer_protocol_read",
        "description": "读取本工作区写者协议的精简台账（今日行 + 昨日摘要）。没有文件就会创建。不要用它挑选技能。",
        "inputSchema": {
            "type": "object",
            "properties": {"root": {"type": "string", "description": "工作区目录，默认当前目录"}},
            "additionalProperties": False,
        },
    },
    {
        "name": "writer_protocol_append",
        "description": "把这一次改动记进今日台账。每改一批文件调用一次。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "writer": {"type": "string"},
                "files": {"type": "array", "items": {"type": "string"}},
                "status": {"type": "string"},
                "note": {"type": "string"},
                "commit": {"type": "string"},
                "root": {"type": "string"},
            },
            "required": ["writer"],
            "additionalProperties": False,
        },
    },
]


def _read():
    line = sys.stdin.buffer.readline()
    if not line:
        return None
    if line.lower().startswith(b"content-length:"):
        length = int(line.split(b":", 1)[1].strip())
        while True:
            header = sys.stdin.buffer.readline()
            if header in (b"\r\n", b"\n", b""):
                break
        return json.loads(sys.stdin.buffer.read(length).decode("utf-8")), True
    stripped = line.strip()
    return (json.loads(stripped.decode("utf-8")), False) if stripped else _read()


def _write(payload: dict, framed: bool) -> None:
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    if framed:
        sys.stdout.buffer.write(f"Content-Length: {len(body)}\r\n\r\n".encode("ascii") + body)
    else:
        sys.stdout.buffer.write(body + b"\n")
    sys.stdout.buffer.flush()


def _result(text: str, is_error: bool = False) -> dict:
    return {"content": [{"type": "text", "text": text}], "isError": is_error}


def call_tool(name: str, arguments: dict) -> dict:
    if not isinstance(arguments, dict):
        arguments = {}
    root = arguments.get("root") or None
    try:
        if name == "writer_protocol_read":
            ensure(root)
            return _result(compact_read(root))
        if name == "writer_protocol_append":
            files = arguments.get("files") or []
            if isinstance(files, str):
                files = [part.strip() for part in files.split(",") if part.strip()]
            row = append(
                root,
                str(arguments.get("writer") or ""),
                [str(item) for item in files],
                str(arguments.get("status") or "进行中"),
                str(arguments.get("note") or ""),
                str(arguments.get("commit") or ""),
            )
            return _result(json.dumps(row, ensure_ascii=False))
        return _result("没有这个工具。", True)
    except (OSError, ValueError) as exc:
        return _result(str(exc), True)


def handle(message: dict) -> dict | None:
    method = message.get("method")
    req_id = message.get("id")
    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "writer-protocol", "version": "0.1.0"},
                "instructions": (
                    "动手前 writer_protocol_read。改完文件 writer_protocol_append。"
                    "不要提交 WRITER-PROTOCOL.md 和 writer-log/。"
                    f" 提示：{session_hint(find_workspace())}"
                ),
            },
        }
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": req_id, "result": {"tools": TOOLS}}
    if method == "tools/call":
        params = message.get("params") or {}
        return {"jsonrpc": "2.0", "id": req_id, "result": call_tool(str(params.get("name") or ""), params.get("arguments") or {})}
    if method == "notifications/initialized" or req_id is None:
        return None
    return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32601, "message": "Method not found"}}


def run() -> None:
    while True:
        parsed = _read()
        if parsed is None:
            return
        message, framed = parsed
        reply = handle(message)
        if reply is not None:
            _write(reply, framed)
