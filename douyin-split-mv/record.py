"""Record 1080x1920 split MV. Output stays local (gitignored mp4)."""
from __future__ import annotations

import http.server
import os
import socketserver
import threading
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
HERE = Path(__file__).resolve().parent
FONT = Path(r"C:\Windows\Fonts\NotoSansSC-VF.ttf")
PORT = 8767
DURATION_MS = 44500


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def log_message(self, format, *args):
        return

    def do_GET(self):
        if self.path.startswith("/fonts/NotoSansSC-VF.ttf") and FONT.exists():
            self.send_response(200)
            self.send_header("Content-Type", "font/ttf")
            self.send_header("Cache-Control", "public, max-age=86400")
            self.end_headers()
            self.wfile.write(FONT.read_bytes())
            return
        return super().do_GET()


def serve():
    httpd = socketserver.TCPServer(("127.0.0.1", PORT), Handler)
    httpd.allow_reuse_address = True
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd


def main():
    out_dir = HERE / "_rec"
    out_dir.mkdir(exist_ok=True)
    for old in out_dir.glob("*"):
        old.unlink()
    serve()
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome")
        context = browser.new_context(
            viewport={"width": 1080, "height": 1920},
            device_scale_factor=1,
            record_video_dir=str(out_dir),
            record_video_size={"width": 1080, "height": 1920},
        )
        page = context.new_page()
        page.goto(f"http://127.0.0.1:{PORT}/douyin-split-mv/index.html", wait_until="load")
        page.wait_for_timeout(DURATION_MS)
        page.close()
        context.close()
        browser.close()
    clips = list(out_dir.glob("*.webm"))
    if not clips:
        raise SystemExit("no webm recorded")
    dest = HERE / "split-raw.webm"
    clips[0].replace(dest)
    print(dest)


if __name__ == "__main__":
    main()
