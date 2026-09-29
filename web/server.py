# Local skill cabinet page. Edits and moves stay inside this project.
from __future__ import annotations

import json
import os
import secrets
import socket
import sys
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import cabinet

WEB = Path(__file__).resolve().parent
HOST = "127.0.0.1"
PORT = 8765
TOKEN = secrets.token_urlsafe(24)
WORKER_KEEPALIVE_SECONDS = 10


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args) -> None:
        print("[kit] " + (fmt % args), flush=True)

    def _local(self) -> bool:
        host = (self.headers.get("Host") or "").split(":")[0]
        return host in {"127.0.0.1", "localhost"}

    def _origin_ok(self) -> bool:
        origin = (self.headers.get("Origin") or "").strip()
        if not origin:
            return True
        return origin.startswith("http://127.0.0.1") or origin.startswith("http://localhost")

    def _allowed_write(self) -> bool:
        return (
            self._local()
            and self._origin_ok()
            and (self.headers.get("X-Kit-Token") or "") == TOKEN
        )

    def _json(self, code: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store, must-revalidate")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        if length > 1_500_000:
            raise ValueError("body too large")
        raw = self.rfile.read(length) if length else b"{}"
        data = json.loads(raw.decode("utf-8"))
        if not isinstance(data, dict):
            raise ValueError("json object required")
        return data

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        try:
            if not self._local():
                self._json(403, {"error": "local only"})
                return
            if parsed.path == "/":
                self._file(WEB / "index.html", "text/html; charset=utf-8")
                return
            if parsed.path == "/api/token":
                self._json(200, {"token": TOKEN})
                return
            if parsed.path == "/api/catalog":
                self._json(200, cabinet.catalog_view())
                return
            if parsed.path == "/api/skill":
                name = parse_qs(parsed.query).get("name", [""])[0]
                self._json(200, cabinet.read_skill(name))
                return
            if parsed.path == "/api/health":
                from host.jev import WEIGHTS
                from host.preface_client import worker_port

                self._json(200, {"ok": True, "modelReady": WEIGHTS.is_file(), "prefaceWorker": worker_port()})
                return
            if parsed.path == "/api/progress":
                kind = parse_qs(parsed.query).get("kind", [""])[0]
                job_id = parse_qs(parsed.query).get("id", [""])[0]
                job = cabinet.progress_job(kind, job_id)
                if not job:
                    self._json(404, {"error": "没有这次任务"})
                    return
                self._json(200, job)
                return
            if parsed.path == "/api/settings":
                self._json(200, cabinet.public_config())
                return
            if parsed.path == "/api/calls":
                self._json(200, cabinet.calls_view())
                return
            if parsed.path == "/api/delegation":
                from host.delegation import entries

                self._json(200, {"enabled": cabinet.public_config()["delegationEnabled"], "entries": entries()})
                return
            if parsed.path == "/api/mcp":
                from host.mcp_inventory import list_mcp_servers

                self._json(200, list_mcp_servers())
                return
            if parsed.path == "/api/plugins":
                job_id = parse_qs(parsed.query).get("id", [""])[0]
                if job_id:
                    job = cabinet.progress_job("plugins", job_id)
                    if not job:
                        self._json(404, {"error": "没有这次任务"})
                        return
                    self._json(200, job)
                    return
                from host.plugin_inventory import list_plugins

                self._json(200, list_plugins())
                return
            if parsed.path == "/api/library":
                self._json(200, cabinet.library_view())
                return
            if parsed.path == "/api/library/install":
                job_id = parse_qs(parsed.query).get("id", [""])[0]
                job = cabinet.install_job(job_id)
                if not job:
                    self._json(404, {"error": "没有这次安装"})
                    return
                self._json(200, job)
                return
            self._json(404, {"error": "not found"})
        except Exception as exc:
            self._json(400, {"error": str(exc)})

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        try:
            if not self._allowed_write():
                self._json(403, {"error": "local page only"})
                return
            body = self._read_json()
            if parsed.path == "/api/move":
                self._json(200, cabinet.move_skill(str(body.get("name", "")), str(body.get("category", ""))))
                return
            if parsed.path == "/api/save":
                self._json(200, cabinet.save_skill(str(body.get("name", "")), body.get("content")))
                return
            if parsed.path == "/api/route":
                self._json(200, cabinet.route_task(str(body.get("task", "")), "web"))
                return
            if parsed.path == "/api/settings":
                self._json(200, cabinet.save_config(body))
                return
            if parsed.path == "/api/rules":
                self._json(200, cabinet.update_rule(body))
                return
            if parsed.path == "/api/calls/delete":
                self._json(200, cabinet.delete_call(str(body.get("id") or "")))
                return
            if parsed.path == "/api/scan":
                self._json(200, cabinet.begin_scan())
                return
            if parsed.path == "/api/memory/tools":
                self._json(200, cabinet.begin_memory())
                return
            if parsed.path == "/api/sync":
                chosen = str(body.get("direction") or "")
                skill_name = str(body.get("name") or "").strip() or None
                self._json(200, cabinet.sync_skills(chosen, skill_name, preview=bool(body.get("preview"))))
                return
            if parsed.path == "/api/folders/pick":
                chosen = cabinet.pick_folder()
                if not chosen:
                    self._json(200, {"path": "", "cancelled": True, "extraScanRoots": cabinet.load_config().get("extraScanRoots") or []})
                    return
                report = cabinet.import_folder(chosen)
                report["path"] = chosen
                report["cancelled"] = False
                self._json(200, report)
                return
            if parsed.path == "/api/folders":
                report = cabinet.import_folder(str(body.get("path", "")).strip())
                report["cancelled"] = False
                self._json(200, report)
                return
            if parsed.path == "/api/library/refresh":
                self._json(200, cabinet.refresh_library())
                return
            if parsed.path == "/api/plugins/refresh":
                self._json(200, cabinet.begin_plugins())
                return
            if parsed.path == "/api/library/search":
                self._json(200, cabinet.search_library(str(body.get("q") or "")))
                return
            if parsed.path == "/api/library/install":
                self._json(200, cabinet.begin_install(str(body.get("url") or "")))
                return
            if parsed.path == "/api/library/local":
                self._json(200, cabinet.install_local(str(body.get("path") or "")))
                return
            if parsed.path == "/api/pick-folder":
                chosen = cabinet.pick_folder()
                self._json(200, {"path": chosen, "cancelled": not bool(chosen)})
                return
            if parsed.path in {"/api/plugins/toggle", "/api/mcp/toggle"}:
                from host.board import set_enabled

                kind = "plugin" if "plugins" in parsed.path else "mcp"
                set_enabled(kind, str(body.get("host") or ""), str(body.get("name") or ""), bool(body.get("enabled")))
                self._json(200, _listed(kind))
                return
            if parsed.path in {"/api/plugins/delete", "/api/mcp/delete"}:
                from host.board import hide_row

                kind = "plugin" if "plugins" in parsed.path else "mcp"
                hide_row(kind, str(body.get("host") or ""), str(body.get("name") or ""))
                self._json(200, _listed(kind))
                return
            if parsed.path == "/api/plugins/add":
                from host.board import add_row, plugin_from_source

                add_row("plugin", plugin_from_source(str(body.get("kind") or ""), str(body.get("source") or "")))
                self._json(200, _listed("plugin"))
                return
            if parsed.path == "/api/mcp/add":
                from host.board import add_row, mcp_from_source

                add_row("mcp", mcp_from_source(str(body.get("kind") or ""), str(body.get("source") or "")))
                self._json(200, _listed("mcp"))
                return
            if parsed.path == "/api/library/peek":
                self._json(200, cabinet.peek_github(str(body.get("url") or "")))
                return
            if parsed.path == "/api/library/read":
                self._json(200, cabinet.read_github_skill(str(body.get("url") or ""), str(body.get("path") or "")))
                return
            if parsed.path == "/api/folders/remove":
                roots = cabinet.forget_root(str(body.get("path", "")).strip())
                self._json(200, {"extraScanRoots": roots})
                return
            self._json(404, {"error": "not found"})
        except Exception as exc:
            traceback.print_exc()
            self._json(400, {"error": str(exc)})

    def _file(self, path: Path, content_type: str) -> None:
        data = path.read_bytes()
        if path.name == "index.html":
            data = data.replace(b"__KIT_TOKEN__", TOKEN.encode("ascii"))
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        # 本机页面不需要缓存：不禁止的话浏览器会按启发式缓存，改完看不出效果（白白怀疑"没改好"）
        self.send_header("Cache-Control", "no-store, must-revalidate")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def _listed(kind: str) -> dict:
    if kind == "plugin":
        from host.plugin_inventory import list_plugins

        return list_plugins()
    from host.mcp_inventory import list_mcp_servers

    return list_mcp_servers()


def _warm_model() -> None:
    try:
        from host.jev import load_head

        load_head()
        print("[kit] jev ready", flush=True)
    except Exception as exc:
        print("[kit] jev warmup skipped: " + str(exc), flush=True)


def _refresh_library() -> None:
    try:
        if cabinet.library_is_stale():
            cabinet.refresh_library()
            print("[kit] library refreshed", flush=True)
    except Exception as exc:
        print("[kit] library refresh skipped: " + str(exc), flush=True)


def _publish_kit_root() -> None:
    """Tell installed copies of the host plugin where this kit really lives.

    The host loads its own copy of the plugin, and that copy's directory says
    nothing about this checkout.
    """
    try:
        shared = Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "jev-skill-kit"
        shared.mkdir(parents=True, exist_ok=True)
        (shared / "root.txt").write_text(str(ROOT), encoding="utf-8")
    except OSError as exc:
        print("[kit] kit root pointer skipped: " + str(exc), flush=True)


def _ensure_worker_once() -> int | None:
    from host.preface_client import ensure_worker

    try:
        port = ensure_worker()
    except Exception as exc:
        print("[kit] preface worker skipped: " + str(exc), flush=True)
        return None
    if not port:
        print("[kit] preface worker unavailable", flush=True)
    return port


def _keep_worker() -> None:
    """Own the preface worker: hosts only reuse it, and hosts are not asked to spawn.

    Spawning from a host plugin process proved unreliable, so the long-lived page
    server keeps one healthy worker alive instead.
    """
    import time

    while True:
        _ensure_worker_once()
        time.sleep(WORKER_KEEPALIVE_SECONDS)


def main() -> None:
    import threading

    _publish_kit_root()
    threading.Thread(target=_warm_model, daemon=True).start()
    threading.Thread(target=_refresh_library, daemon=True).start()
    threading.Thread(target=_keep_worker, daemon=True).start()
    class KitServer(ThreadingHTTPServer):
        allow_reuse_address = False

        def server_bind(self) -> None:
            if sys.platform == "win32":
                self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            super().server_bind()

    server = KitServer((HOST, PORT), Handler)
    print(f"skill cabinet http://{HOST}:{PORT}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
