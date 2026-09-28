import sys
import time
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import cabinet


def _wait(job_id: str) -> dict:
    current = {}
    for _ in range(50):
        current = cabinet.install_job(job_id) or {}
        if current.get("state") != "running":
            return current
        time.sleep(0.02)
    raise AssertionError("install job did not finish: " + str(current))


class Proc:
    def __init__(self):
        self.returncode = None

    def poll(self):
        self.returncode = 0
        return 0

    def wait(self, timeout=None):
        self.returncode = 0
        return 0


class InstallJobTests(unittest.TestCase):
    def test_repo_without_skill_md_fails_when_cabinet_gains_nothing(self):
        seen = {}

        def popen(cmd, **kwargs):
            seen["cmd"] = cmd
            return Proc()

        with patch.object(cabinet, "install_github", side_effect=FileNotFoundError("这个链接里没有 SKILL.md")):
            with patch.object(cabinet, "_catalog_names", return_value={"already"}):
                with patch.object(cabinet.shutil, "which", return_value="hermes"):
                    with patch.object(cabinet.subprocess, "Popen", side_effect=popen):
                        job = cabinet.begin_install("https://github.com/example/no-skill")
                        current = _wait(job["id"])
        self.assertEqual(current["state"], "failed")
        self.assertIn("没有新的技能", current["message"])
        self.assertEqual(seen["cmd"][0], "hermes")
        self.assertIn("https://github.com/example/no-skill", seen["cmd"][2])
        self.assertNotIn("--yolo", seen["cmd"])

    def test_hermes_done_only_after_a_new_skill_lands(self):
        names = iter(({"already"}, {"already", "fresh"}))

        def catalog():
            return next(names)

        with patch.object(cabinet, "install_github", side_effect=FileNotFoundError("这个链接里没有 SKILL.md")):
            with patch.object(cabinet, "_catalog_names", side_effect=catalog):
                with patch.object(cabinet.shutil, "which", return_value="hermes"):
                    with patch.object(cabinet.subprocess, "Popen", return_value=Proc()):
                        job = cabinet.begin_install("https://github.com/example/made-skill")
                        current = _wait(job["id"])
        self.assertEqual(current["state"], "done")
        self.assertEqual(current["progress"], 100)
        self.assertEqual(current["copied"][0]["name"], "fresh")

    def test_existing_skill_copies_without_calling_hermes(self):
        with patch.object(cabinet, "install_github", return_value={"message": "已复制进技能柜", "copied": [{"name": "demo"}]}):
            with patch.object(cabinet, "_catalog_names", return_value={"demo"}):
                with patch.object(cabinet.subprocess, "Popen") as popen:
                    job = cabinet.begin_install("https://github.com/example/has-skill")
                    current = _wait(job["id"])
        self.assertEqual(current["state"], "done")
        self.assertEqual(current["copied"][0]["name"], "demo")
        popen.assert_not_called()

    def test_missing_repo_stays_chinese_and_skips_hermes(self):
        with patch.object(cabinet, "install_github", side_effect=RuntimeError("fatal: repository 'https://github.com/example/missing.git/' not found")):
            with patch.object(cabinet.subprocess, "Popen") as popen:
                job = cabinet.begin_install("https://github.com/example/missing")
                current = _wait(job["id"])
        self.assertEqual(current["state"], "failed")
        self.assertEqual(current["message"], "这个仓库不存在，或现在访问不到。")
        self.assertNotIn("fatal", current["message"])
        popen.assert_not_called()


if __name__ == "__main__":
    unittest.main()
