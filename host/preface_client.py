# Ask the long-lived preface worker. It scores with the local JEV head.
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "runtime"
PORT_FILE = RUNTIME / "preface.port"
LOCK_FILE = RUNTIME / "preface.lock"
PYTHON = ROOT / ".venv" / "Scripts" / "python.exe"
WORKER = ROOT / "host" / "preface_worker.py"
POST_TIMEOUT = 170


def message_text(value) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        parts = []
        for item in value:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                text = item.get("text") or item.get("content") or ""
                if isinstance(text, str):
                    parts.append(text)
        return "\n".join(part for part in parts if part).strip()
    return str(value or "").strip()


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _read_port() -> int | None:
    try:
        port = int(PORT_FILE.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return None
    if port <= 0 or port > 65535:
        return None
    return port


def _healthy(port: int) -> bool:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=0.4) as response:
            return response.status == 200
    except (OSError, urllib.error.URLError):
        return False


def _clear_stale_lock() -> None:
    try:
        pid = int(LOCK_FILE.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return
    if not _pid_alive(pid):
        LOCK_FILE.unlink(missing_ok=True)
        PORT_FILE.unlink(missing_ok=True)


def _start_worker() -> None:
    RUNTIME.mkdir(parents=True, exist_ok=True)
    _clear_stale_lock()
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        fd = os.open(str(LOCK_FILE), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        return
    try:
        os.write(fd, str(os.getpid()).encode("ascii"))
    finally:
        os.close(fd)
    python = str(PYTHON if PYTHON.is_file() else Path(sys.executable))
    subprocess.Popen(
        [python, str(WORKER)],
        cwd=str(ROOT),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=flags,
    )


def _wait_port() -> int | None:
    deadline = time.time() + 8
    while time.time() < deadline:
        port = _read_port()
        if port and _healthy(port):
            return port
        time.sleep(0.2)
    return None


def ensure_worker() -> int | None:
    port = _read_port()
    if port and _healthy(port):
        return port
    _start_worker()
    port = _wait_port()
    if port:
        return port
    LOCK_FILE.unlink(missing_ok=True)
    return None


def preface_for(task: str, source: str) -> str:
    text = message_text(task)
    if not text or "【技能柜】" in text:
        return ""
    port = ensure_worker()
    if not port:
        return "【技能柜】这次没能启动选择。自己做，不要翻技能柜。"
    payload = json.dumps({"task": text, "source": source}, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        f"http://127.0.0.1:{port}/preface",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=POST_TIMEOUT) as response:
            body = json.loads(response.read().decode("utf-8"))
    except (OSError, urllib.error.URLError, json.JSONDecodeError):
        return "【技能柜】这次没能完成选择。自己做，不要翻技能柜。"
    if not isinstance(body, dict):
        return ""
    return str(body.get("preface") or "")
