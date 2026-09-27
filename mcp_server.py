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
        "description": "读取 JEV 这次已经选定的技能正文。必须带 decision_id。不能用来浏览或改选技能。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "JEV 选定的技能目录名"},
                "decision_id": {"type": "string", "description": "前言里的 decision_id"},
                "offset": {"type": "integer", "description": "从第几个字符继续读", "minimum": 0},
            },
            "required": ["name", "decision_id"],
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


def allowed_skill_names(decision_id: str) -> set[str]:
    wanted = (decision_id or "").strip()
    if not wanted:
        return set()
    memory = cabinet.load_memory()
    for latest in memory.get("calls") or []:
        if str(latest.get("id") or "") != wanted:
            continue
        if latest.get("method") != "skill":
            return set()
        return {str(name) for name in (latest.get("skills") or []) if name}
    return set()


def call_tool(name: str, arguments: dict) -> dict:
    if not isinstance(arguments, dict):
        arguments = {}
    if name == "get_skill":
        requested = str(arguments.get("name", "")).strip()
        decision_id = str(arguments.get("decision_id") or arguments.get("decisionId") or "").strip()
        try:
            offset = max(0, int(arguments.get("offset") or 0))
        except (TypeError, ValueError):
            offset = 0
        if not decision_id:
            return tool_result("缺少 decision_id。用前言里的那一次决定来读。", is_error=True)
        memory = cabinet.load_memory()
        known = {str(item.get("id") or "") for item in memory.get("calls") or []}
        if decision_id not in known:
            return tool_result("决定已过期。不要改选，也不要猜别的技能。", is_error=True)
        allowed = allowed_skill_names(decision_id)
        if requested not in allowed:
            return tool_result("JEV 这次没有选定这个技能。不要改选。", is_error=True)
        skill = cabinet.read_skill(requested)
        content = skill.get("content") or ""
        chunk = content[offset : offset + CONTENT_LIMIT]
        payload = {
            "name": skill["name"],
            "category": skill["category"],
            "summary": skill.get("summary") or "",
            "path": skill.get("path") or "",
            "scripts": skill.get("scripts") or [],
            "decisionId": decision_id,
            "offset": offset,
            "nextOffset": offset + len(chunk) if offset + len(chunk) < len(content) else None,
            "truncated": offset + len(chunk) < len(content),
            "totalChars": len(content),
            "content": chunk,
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
                "instructions": "选技能的是 JEV，不是你。宿主已经把选定结果放在这轮开头。结果是自己做，就自己做，不要读技能。结果列出了技能，就读完照做，不要再挑选。get_skill 必须带前言里的 decision_id，只能读取已经选定的名字，超长正文用 offset 续读。",
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
