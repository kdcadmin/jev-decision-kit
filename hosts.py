# Point Hermes and OpenClaw at this project when the selector is on.
from __future__ import annotations

import json
import re
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


def sync_hermes(enabled: bool) -> dict:
    path = Path.home() / ".hermes" / "config.yaml"
    if not path.is_file():
        return {"name": "hermes", "present": False, "enabled": False}
    text = path.read_text(encoding="utf-8")
    block = _hermes_block(enabled)
    pattern = re.compile(r"\n  jev-skill-kit:\n(?:    .*\n)*")
    if pattern.search("\n" + text if not text.startswith("\n") else text) or "\n  jev-skill-kit:\n" in "\n" + text:
        text2 = re.sub(r"(?m)^  jev-skill-kit:\n(?:    .*\n)*", lambda _match: block, text, count=1)
    elif "\nmcp_servers:\n" in "\n" + text or text.startswith("mcp_servers:\n"):
        text2 = text.replace("mcp_servers:\n", "mcp_servers:\n" + block, 1)
    else:
        text2 = text.rstrip() + "\n\nmcp_servers:\n" + block
    if text2 != text:
        path.write_text(text2, encoding="utf-8")
    return {"name": "hermes", "present": True, "enabled": enabled}


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
