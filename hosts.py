# Point Hermes and OpenClaw at this project when the selector is on.
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def python_exe() -> str:
    candidate = ROOT / ".venv" / "Scripts" / "python.exe"
    if candidate.is_file():
        return str(candidate)
    return sys.executable


def mcp_command() -> dict:
    return {
        "command": python_exe(),
        "args": [str(ROOT / "mcp_server.py")],
        "enabled": True,
        "requestTimeoutMs": 180000,
        "env": {"USE_TF": "0", "PYTHONUTF8": "1"},
    }


def _hermes_block(enabled: bool) -> str:
    flag = "true" if enabled else "false"
    exe = python_exe()
    script = str(ROOT / "mcp_server.py")
    return (
        "  jev-skill-kit:\n"
        f"    command: {exe}\n"
        "    args:\n"
        f"    - {script}\n"
        "    timeout: 180\n"
        "    env:\n"
        "      USE_TF: '0'\n"
        "      PYTHONUTF8: '1'\n"
        f"    enabled: {flag}\n"
    )


def upsert_mcp_block(text: str, block: str) -> str:
    if not block.endswith("\n"):
        block += "\n"
    lines = text.splitlines(keepends=True)
    if not lines:
        return "mcp_servers:\n" + block
    parent = next((index for index, line in enumerate(lines) if line.startswith("mcp_servers:")), None)
    if parent is None:
        return text.rstrip() + "\n\nmcp_servers:\n" + block

    def server_key(line: str) -> bool:
        return line.startswith("  ") and not line.startswith("    ") and bool(line.strip())

    start = None
    limit = len(lines)
    for index in range(parent + 1, len(lines)):
        line = lines[index]
        if line.strip() and not line.startswith((" ", "\t")):
            limit = index
            break
    for index in range(parent + 1, limit):
        if lines[index].startswith("  jev-skill-kit:"):
            start = index
            break
    if start is None:
        lines.insert(limit, block)
        return "".join(lines)
    end = start + 1
    while end < limit:
        line = lines[end]
        if server_key(line) and not line.startswith("  jev-skill-kit:"):
            break
        end += 1
    lines[start:end] = [block]
    return "".join(lines)


def sync_hermes(enabled: bool, path: Path | None = None) -> dict:
    path = path or (Path.home() / ".hermes" / "config.yaml")
    if not path.is_file():
        return {"name": "hermes", "present": False, "enabled": False}
    text = path.read_text(encoding="utf-8")
    text2 = upsert_mcp_block(text, _hermes_block(enabled))
    if text2 != text:
        backup = path.with_name(path.name + ".jev.bak")
        if not backup.is_file():
            backup.write_text(text, encoding="utf-8")
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_text(text2, encoding="utf-8")
        tmp.replace(path)
    return {"name": "hermes", "present": True, "enabled": enabled, "backup": str(path.with_name(path.name + ".jev.bak"))}


def sync_openclaw(enabled: bool) -> dict:
    if not (Path.home() / ".openclaw" / "openclaw.json").is_file():
        return {"name": "openclaw", "present": False, "enabled": False}
    command = shutil.which("openclaw") or shutil.which("openclaw.cmd")
    if not command:
        return {"name": "openclaw", "present": True, "enabled": enabled, "warning": "找不到 openclaw 命令"}
    payload = mcp_command()
    payload["enabled"] = enabled
    line = [command, "mcp", "set", "jev-skill-kit", json.dumps(payload, ensure_ascii=False)]
    try:
        completed = subprocess.run(
            line,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=90,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"name": "openclaw", "present": True, "enabled": enabled, "warning": str(exc)}
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip().splitlines()
        return {"name": "openclaw", "present": True, "enabled": enabled, "warning": detail[-1] if detail else "openclaw mcp set failed"}
    return {"name": "openclaw", "present": True, "enabled": enabled}


def sync_hosts(enabled: bool) -> list[dict]:
    return [sync_hermes(enabled), sync_openclaw(enabled)]
