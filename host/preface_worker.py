# One process scores with JEV. Hermes and OpenClaw ask it before the model speaks.
from __future__ import annotations

import json
import os
import secrets
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "runtime"
PORT_FILE = RUNTIME / "preface.port"
LOCK_FILE = RUNTIME / "preface.lock"
TOKEN_FILE = RUNTIME / "preface.token"
sys.path.insert(0, str(ROOT))

import cabinet


def _preface(task: str, source: str) -> str:
    try:
        return cabinet.host_preface(task, source)
    except Exception as exc:
        print("[preface] " + str(exc), flush=True)
        return "【技能柜】这次没能完成选择。自己做，不要翻技能柜。"


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args) -> None:
        print("[preface] " + (fmt % args), flush=True)

    def _send(self, code: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if self.path != "/health":
            self._send(404, {"ok": False})
            return
        self._send(200, {"ok": True})

    def do_POST(self) -> None:
        if self.path != "/preface":
            self._send(404, {"ok": False})
            return
        wanted = ""
        try:
            wanted = TOKEN_FILE.read_text(encoding="utf-8").strip()
        except OSError:
            wanted = ""
        got = (self.headers.get("X-Kit-Token") or "").strip()
        if not wanted or got != wanted:
            self._send(403, {"preface": "【技能柜】这次没能完成选择。自己做，不要翻技能柜。"})
            return
        length = int(self.headers.get("Content-Length", "0") or "0")
        raw = self.rfile.read(length) if length else b"{}"
        try:
            data = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            self._send(400, {"preface": ""})
            return
        task = str((data or {}).get("task") or "")
        source = str((data or {}).get("source") or "host")
        self._send(200, {"preface": _preface(task, source)})


def main() -> None:
    RUNTIME.mkdir(parents=True, exist_ok=True)
    TOKEN_FILE.write_text(secrets.token_urlsafe(24), encoding="utf-8")
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    port = server.server_address[1]
    PORT_FILE.write_text(str(port), encoding="utf-8")
    LOCK_FILE.write_text(str(os.getpid()), encoding="utf-8")
    print("[preface] listening " + str(port), flush=True)
    try:
        server.serve_forever()
    finally:
        PORT_FILE.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
