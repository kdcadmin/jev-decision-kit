import json
import os
import tempfile
import threading
import unittest
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

from host import preface_client
from web import server as web_server


class WorkerLifecycleTests(unittest.TestCase):
    def test_worker_port_reports_only_a_healthy_worker(self):
        with tempfile.TemporaryDirectory() as folder:
            port_file = Path(folder) / "preface.port"
            with patch.object(preface_client, "PORT_FILE", port_file):
                self.assertIsNone(preface_client.worker_port())
                port_file.write_text("64141", encoding="utf-8")
                with patch.object(preface_client, "_healthy", return_value=False):
                    self.assertIsNone(preface_client.worker_port())
                with patch.object(preface_client, "_healthy", return_value=True):
                    self.assertEqual(64141, preface_client.worker_port())

    def test_worker_port_rejects_an_impossible_port(self):
        with tempfile.TemporaryDirectory() as folder:
            port_file = Path(folder) / "preface.port"
            port_file.write_text("99999", encoding="utf-8")
            with patch.object(preface_client, "PORT_FILE", port_file), \
                 patch.object(preface_client, "_healthy", return_value=True):
                self.assertIsNone(preface_client.worker_port())

    def test_keepalive_tick_survives_a_failing_starter(self):
        with patch("host.preface_client.ensure_worker", side_effect=OSError("spawn failed")):
            self.assertIsNone(web_server._ensure_worker_once())
        with patch("host.preface_client.ensure_worker", return_value=None):
            self.assertIsNone(web_server._ensure_worker_once())
        with patch("host.preface_client.ensure_worker", return_value=4321):
            self.assertEqual(4321, web_server._ensure_worker_once())

    def test_kit_root_pointer_is_published_for_installed_plugins(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch.object(web_server, "ROOT", Path(folder) / "kit"), \
                 patch.dict(os.environ, {"LOCALAPPDATA": folder}, clear=False):
                web_server._publish_kit_root()
            pointer = Path(folder) / "jev-skill-kit" / "root.txt"
            self.assertEqual(str(Path(folder) / "kit"), pointer.read_text(encoding="utf-8"))

    def test_health_endpoint_reports_the_preface_worker(self):
        server = ThreadingHTTPServer(("127.0.0.1", 0), web_server.Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with patch.object(preface_client, "worker_port", return_value=4321):
                with urllib.request.urlopen(
                    f"http://127.0.0.1:{server.server_address[1]}/api/health", timeout=5
                ) as response:
                    body = json.load(response)
            self.assertTrue(body["ok"])
            self.assertEqual(4321, body["prefaceWorker"])
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)


if __name__ == "__main__":
    unittest.main()
