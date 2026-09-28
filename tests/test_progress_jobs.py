import sys
import time
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import cabinet


def _wait(kind: str, job_id: str) -> dict:
    current = {}
    for _ in range(80):
        current = cabinet.progress_job(kind, job_id) or {}
        if current.get("state") != "running":
            return current
        time.sleep(0.02)
    raise AssertionError("job did not finish: " + str(current))


class ProgressJobTests(unittest.TestCase):
    def test_scan_job_reports_copied_skills(self):
        with patch.object(cabinet, "scan_skills", return_value={"copied": [{"name": "demo"}], "skippedDuplicates": 2}):
            job = cabinet.begin_scan()
            current = _wait("scan", job["id"])
        self.assertEqual(current["state"], "done")
        self.assertEqual(current["progress"], 100)
        self.assertEqual(current["copied"][0]["name"], "demo")
        self.assertIn("新复制 1 个", current["message"])

    def test_memory_job_keeps_progress_when_retrain_is_refused(self):
        report = {"kept": 3, "doors": {"web-act": 2}}
        with patch("host.tool_memory.extract_tool_memory", return_value=report):
            with patch("host.train_jev.train", side_effect=RuntimeError("回归下降")):
                with patch("host.jev.cache_clear"), patch("host.jev.load_head"):
                    job = cabinet.begin_memory()
                    current = _wait("memory", job["id"])
        self.assertEqual(current["state"], "done")
        self.assertEqual(current["kept"], 3)
        self.assertFalse(current["retrained"])
        self.assertIn("未写入权重", current["message"])

    def test_plugin_job_returns_the_scanned_list(self):
        payload = {"note": "插件说明", "plugins": [{"host": "Hermes", "name": "browser", "selectable": True}]}
        with patch("host.plugin_inventory.list_plugins", return_value=payload):
            job = cabinet.begin_plugins()
            current = _wait("plugins", job["id"])
        self.assertEqual(current["state"], "done")
        self.assertEqual(current["plugins"][0]["name"], "browser")
        self.assertEqual(current["note"], "插件说明")


if __name__ == "__main__":
    unittest.main()
