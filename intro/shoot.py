# Shoot the live cabinet page at a fixed desktop size.
import base64
import json
import os
import socket
import struct
import time
import urllib.request
from pathlib import Path

HOST = "127.0.0.1"
PORT = 9333
OUT = Path(r"D:\jev-decision-kit\intro\frames")
OUT.mkdir(parents=True, exist_ok=True)


class CDP:
    def __init__(self, url: str) -> None:
        rest = url.removeprefix("ws://")
        host_port, path = rest.split("/", 1)
        host, port = host_port.split(":")
        self.sock = socket.create_connection((host, int(port)))
        key = base64.b64encode(os.urandom(16)).decode()
        req = (
            f"GET /{path} HTTP/1.1\r\n"
            f"Host: {host}:{port}\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\n"
            "Sec-WebSocket-Version: 13\r\n\r\n"
        )
        self.sock.sendall(req.encode())
        buf = b""
        while b"\r\n\r\n" not in buf:
            buf += self.sock.recv(4096)
        self.extra = buf.split(b"\r\n\r\n", 1)[1]
        self.seq = 0

    def _read_exact(self, n: int) -> bytes:
        buf = self.extra[:n]
        self.extra = self.extra[n:]
        while len(buf) < n:
            chunk = self.sock.recv(n - len(buf))
            if not chunk:
                raise ConnectionError("socket closed")
            buf += chunk
        return buf

    def recv(self) -> dict:
        while True:
            header = self._read_exact(2)
            opcode = header[0] & 0x0F
            length = header[1] & 0x7F
            if length == 126:
                length = struct.unpack(">H", self._read_exact(2))[0]
            elif length == 127:
                length = struct.unpack(">Q", self._read_exact(8))[0]
            payload = self._read_exact(length)
            if opcode == 0x8:
                raise ConnectionError("websocket closed")
            if opcode == 0x1:
                return json.loads(payload.decode())

    def call(self, method: str, params: dict | None = None) -> dict:
        self.seq += 1
        ident = self.seq
        body = json.dumps({"id": ident, "method": method, "params": params or {}})
        data = body.encode()
        mask = os.urandom(4)
        frame = bytearray([0x81])
        n = len(data)
        if n < 126:
            frame.append(0x80 | n)
        elif n < 65536:
            frame.append(0x80 | 126)
            frame += struct.pack(">H", n)
        else:
            frame.append(0x80 | 127)
            frame += struct.pack(">Q", n)
        frame += mask
        frame += bytes(b ^ mask[i % 4] for i, b in enumerate(data))
        self.sock.sendall(frame)
        while True:
            message = self.recv()
            if message.get("id") == ident:
                if "error" in message:
                    raise RuntimeError(message["error"])
                return message.get("result") or {}

    def evaluate(self, expression: str):
        result = self.call(
            "Runtime.evaluate",
            {"expression": expression, "returnByValue": True, "awaitPromise": True},
        )
        remote = result.get("result") or {}
        if remote.get("subtype") == "error":
            raise RuntimeError(remote.get("description") or remote)
        return remote.get("value")

    def wait_for(self, expression: str, timeout: float = 20) -> str:
        deadline = time.time() + timeout
        last = ""
        while time.time() < deadline:
            last = self.evaluate(expression) or ""
            if last:
                return last
            time.sleep(0.4)
        raise TimeoutError(last or expression)

    def shot(self, name: str) -> None:
        data = self.call("Page.captureScreenshot", {"format": "png", "fromSurface": True})["data"]
        path = OUT / name
        path.write_bytes(base64.b64decode(data))
        print(name, path.stat().st_size, flush=True)


def main() -> None:
    tabs = json.loads(urllib.request.urlopen(f"http://{HOST}:{PORT}/json/list", timeout=10).read().decode())
    page = next(tab for tab in tabs if tab.get("type") == "page")
    cdp = CDP(page["webSocketDebuggerUrl"])
    cdp.call("Page.enable")
    cdp.call("Runtime.enable")
    cdp.call(
        "Emulation.setDeviceMetricsOverride",
        {"width": 1440, "height": 810, "deviceScaleFactor": 1, "mobile": False},
    )
    cdp.call("Page.navigate", {"url": "http://127.0.0.1:8765/"})
    cdp.wait_for("document.getElementById('count') && document.getElementById('count').textContent.includes('239') ? 'ready' : ''", 30)
    time.sleep(0.6)
    cdp.shot("01-cabinet.png")

    cdp.evaluate("document.querySelector('[data-view=library]').click()")
    cdp.wait_for("document.body.innerText.includes('anthropics/skills') ? 'cards' : ''", 20)
    cdp.evaluate("document.querySelector('.lib-card').click()")
    cdp.wait_for(
        "(() => { const t = document.querySelector('#lib-detail')?.innerText || ''; return t.includes('注意') || t.includes('项目介绍') && !t.includes('正在读') ? 'intro' : ''; })()",
        25,
    )
    time.sleep(0.4)
    cdp.shot("02-library.png")

    cdp.evaluate("document.querySelector('[data-view=cabinet]').click()")
    time.sleep(0.3)
    cdp.evaluate(
        """
        (() => {
          const input = document.getElementById('task');
          input.value = '查一下贵州茅台最近的股价和行情';
          input.dispatchEvent(new Event('input', { bubbles: true }));
          document.getElementById('route-form').requestSubmit();
          return 'sent';
        })()
        """
    )
    cdp.wait_for(
        "(() => { const t = document.getElementById('ticket')?.innerText || ''; return t.includes('做法') ? t.slice(0, 80) : ''; })()",
        90,
    )
    time.sleep(0.4)
    cdp.shot("03-weights.png")

    cdp.evaluate("document.querySelector('[data-view=calls]').click()")
    cdp.wait_for("document.body.innerText.includes('删掉记录') ? 'calls' : ''", 20)
    time.sleep(0.4)
    cdp.shot("04-calls.png")
    print("done", flush=True)


if __name__ == "__main__":
    main()
