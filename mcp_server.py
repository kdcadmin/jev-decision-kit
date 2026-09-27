# Stdio MCP server for the local skill cabinet.
from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import cabinet

CONTENT_LIMIT = 20000
KNOWN_PROTOCOLS = ("2025-06-18", "2025-03-26", "2024-11-05")

TOOLS = [
    {
        "name": "get_skill",
        "description": "读取 JEV 这次已经选定的技能正文。不能用来浏览或改选技能。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "JEV 选定的技能目录名"}
            },
            "required": ["name"],
            "additionalProperties": False,
        },
    },
]


def log(message: str) -> None:
    print(message, file=sys.stderr, flush=True)


def read_message():
    while True:
        line = sys.stdin.buffer.readline()
        if not line:
            return None
        if line.lower().startswith(b"content-length:"):
            length = int(line.split(b":", 1)[1].strip())
            while True:
                header = sys.stdin.buffer.readline()
                if header in (b"\r\n", b"\n", b""):
                    break
            body = sys.stdin.buffer.read(length)
            return json.loads(body.decode("utf-8")), True
        stripped = line.strip()
        if not stripped:
            continue
        return json.loads(stripped.decode("utf-8")), False


def write_message(payload: dict, framed: bool) -> None:
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    if framed:
        header = f"Content-Length: {len(body)}\r\n\r\n".encode("ascii")
        sys.stdout.buffer.write(header + body)
    else:
        sys.stdout.buffer.write(body + b"\n")
    sys.stdout.buffer.flush()


def tool_result(text: str, is_error: bool = False) -> dict:
    return {"content": [{"type": "text", "text": text}], "isError": is_error}


def allowed_skill_names() -> set[str]:
    memory = cabinet.load_memory()
    calls = memory.get("calls") or []
    if not calls:
        return set()
    latest = calls[0]
    if latest.get("method") != "skill":
        return set()
    return {str(name) for name in (latest.get("skills") or []) if name}


def call_tool(name: str, arguments: dict) -> dict:
    if not isinstance(arguments, dict):
        arguments = {}
    if name == "get_skill":
        requested = str(arguments.get("name", "")).strip()
        allowed = allowed_skill_names()
        if requested not in allowed:
            return tool_result("JEV 这次没有选定这个技能。不要改选。", is_error=True)
        skill = cabinet.read_skill(requested)
        content = skill.get("content") or ""
        truncated = len(content) > CONTENT_LIMIT
        if truncated:
            content = content[:CONTENT_LIMIT]
        payload = {
            "name": skill["name"],
            "category": skill["category"],
            "summary": skill.get("summary") or "",
            "path": skill.get("path") or "",
            "scripts": skill.get("scripts") or [],
            "truncated": truncated,
            "content": content,
        }
        return tool_result(json.dumps(payload, ensure_ascii=False))
    raise ValueError(f"unknown tool {name}")


def handle(message: dict) -> dict | None:
    method = message.get("method")
    msg_id = message.get("id")
    params = message.get("params") or {}
    if method in {"notifications/initialized", "notifications/cancelled"} or msg_id is None and method and method.startswith("notifications/"):
        return None
    if method == "initialize":
        requested = str(params.get("protocolVersion") or "")
        version = requested if requested in KNOWN_PROTOCOLS else KNOWN_PROTOCOLS[-1]
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "protocolVersion": version,
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "jev-skill-kit", "version": "0.1.0"},
                "instructions": "选技能的是 JEV，不是你。宿主已经把选定结果放在这轮开头。结果是自己做，就自己做，不要读技能。结果列出了技能，就读完照做，不要再挑选。get_skill 只能读取已经选定的名字。",
            },
        }
    if method == "ping":
        return {"jsonrpc": "2.0", "id": msg_id, "result": {}}
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": msg_id, "result": {"tools": TOOLS}}
    if method == "tools/call":
        try:
            result = call_tool(str(params.get("name") or ""), params.get("arguments") or {})
        except Exception as exc:
            log(traceback.format_exc())
            result = tool_result(str(exc), is_error=True)
        return {"jsonrpc": "2.0", "id": msg_id, "result": result}
    if msg_id is None:
        return None
    return {
        "jsonrpc": "2.0",
        "id": msg_id,
        "error": {"code": -32601, "message": f"method not found: {method}"},
    }


def main() -> None:
    log("jev-skill-kit mcp ready")
    while True:
        incoming = read_message()
        if incoming is None:
            return
        message, framed = incoming
        if not isinstance(message, dict):
            continue
        response = handle(message)
        if response is not None:
            write_message(response, framed)


if __name__ == "__main__":
    main()
