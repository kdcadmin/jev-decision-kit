# Read MCP server names from local host configs. Nothing here is offered to JEV.
from __future__ import annotations

import json
import re
from pathlib import Path

_SERVER_HEADER = re.compile(r"^\[mcp_servers\.([^.\]]+)\]\s*$")


def _enabled(value) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return True
    return str(value).strip().lower() not in {"false", "0", "no", "off"}


def servers_from_map(host: str, raw) -> list[dict]:
    if not isinstance(raw, dict):
        return []
    found = []
    for name, spec in raw.items():
        enabled = True
        if isinstance(spec, dict) and "enabled" in spec:
            enabled = _enabled(spec.get("enabled"))
        found.append({"name": str(name), "host": host, "enabled": enabled})
    return found


def servers_from_yaml(text: str) -> list[dict]:
    found = []
    current = None
    in_block = False
    for line in text.splitlines():
        if not in_block:
            if line.startswith("mcp_servers:"):
                in_block = True
            continue
        if line and not line.startswith((" ", "\t")):
            break
        stripped = line.strip()
        if line.startswith("  ") and not line.startswith("   ") and stripped.endswith(":") and not stripped.startswith("-"):
            current = {"name": stripped[:-1], "host": "Hermes", "enabled": True}
            found.append(current)
            continue
        if current is not None and stripped.startswith("enabled:"):
            current["enabled"] = _enabled(stripped.split(":", 1)[1].strip())
    return found


def servers_from_toml(text: str) -> list[dict]:
    names = []
    seen = set()
    for line in text.splitlines():
        match = _SERVER_HEADER.match(line.strip())
        if not match:
            continue
        name = match.group(1)
        if name in seen:
            continue
        seen.add(name)
        names.append({"name": name, "host": "Codex", "enabled": True})
    return names


def _read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeError):
        return None


def list_mcp_servers(home: Path | None = None) -> dict:
    root = home or Path.home()
    servers = []
    cursor = _read_json(root / ".cursor" / "mcp.json")
    if isinstance(cursor, dict):
        servers.extend(servers_from_map("Cursor", cursor.get("mcpServers")))
    claw = _read_json(root / ".openclaw" / "openclaw.json")
    if isinstance(claw, dict):
        mcp = claw.get("mcp") if isinstance(claw.get("mcp"), dict) else {}
        servers.extend(servers_from_map("OpenClaw", mcp.get("servers")))
    minimax = root / ".openclaw" / "mcp-minimax.json"
    if minimax.is_file() and isinstance(_read_json(minimax), dict):
        servers.append({"name": "minimax", "host": "OpenClaw", "enabled": True})
    hermes = root / ".hermes" / "config.yaml"
    if hermes.is_file():
        try:
            servers.extend(servers_from_yaml(hermes.read_text(encoding="utf-8", errors="replace")))
        except OSError:
            pass
    codex = root / ".codex" / "config.toml"
    if codex.is_file():
        try:
            servers.extend(servers_from_toml(codex.read_text(encoding="utf-8", errors="replace")))
        except OSError:
            pass
    servers.sort(key=lambda item: (item["host"], item["name"]))
    if home is None:
        from host.board import apply_rows

        servers = apply_rows(servers, "mcp")
        servers.sort(key=lambda item: (item["host"], item["name"]))
    return {
        "note": "这些 MCP 只在这里查看。JEV 不会挑选它们。",
        "servers": servers,
    }
