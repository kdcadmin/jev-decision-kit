import sys
import time
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import cabinet


class InstallJobTests(unittest.TestCase):
    def test_repo_without_skill_md_is_handed_to_hermes(self):
        seen = {}

        class Proc:
            def __init__(self):
                self.returncode = None

            def poll(self):
                self.returncode = 0
                return 0

            def wait(self, timeout=None):
                self.returncode = 0
                return 0

        def popen(cmd, **kwargs):
            seen["cmd"] = cmd
            seen["cwd"] = kwargs.get("cwd")
            return Proc()

        with patch.object(cabinet, "install_github", side_effect=FileNotFoundError("这个链接里没有 SKILL.md")):
            with patch.object(cabinet.shutil, "which", return_value="hermes"):
                with patch.object(cabinet.subprocess, "Popen", side_effect=popen):
                    job = cabinet.begin_install("https://github.com/example/no-skill")
                    for _ in range(50):
                        current = cabinet.install_job(job["id"])
                        if current and current["state"] != "running":
                            break
                        time.sleep(0.02)
                    else:
                        self.fail("install job did not finish: " + str(current))
        self.assertEqual(current["state"], "done")
        self.assertEqual(current["progress"], 100)
        self.assertEqual(seen["cmd"][0], "hermes")
        self.assertIn("https://github.com/example/no-skill", seen["cmd"][2])
        self.assertNotIn("--yolo", seen["cmd"])
        self.assertEqual(seen["cwd"], str(ROOT))

    def test_existing_skill_copies_without_calling_hermes(self):
        with patch.object(cabinet, "install_github", return_value={"message": "已复制进技能柜", "copied": [{"name": "demo"}]}):
            with patch.object(cabinet.subprocess, "Popen") as popen:
                job = cabinet.begin_install("https://github.com/example/has-skill")
                for _ in range(50):
                    current = cabinet.install_job(job["id"])
                    if current and current["state"] != "running":
                        break
                    time.sleep(0.02)
                else:
                    self.fail("install job did not finish: " + str(current))
        self.assertEqual(current["state"], "done")
        self.assertEqual(current["copied"][0]["name"], "demo")
        popen.assert_not_called()


if __name__ == "__main__":
    unittest.main()
