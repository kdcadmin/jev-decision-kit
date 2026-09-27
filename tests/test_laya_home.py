import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import cabinet


class LayaHomeTests(unittest.TestCase):
    def test_ready_directory_wins(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            (folder / "model.safetensors").write_bytes(b"x")
            (folder / "rl_agent_config.json").write_text("{}", encoding="utf-8")
            bundled = folder / "bundled"
            self.assertEqual(cabinet.pick_model_dir(str(folder), bundled), folder)

    def test_missing_directory_uses_the_project_copy(self):
        with tempfile.TemporaryDirectory() as tmp:
            bundled = Path(tmp) / "models" / "laya"
            chosen = cabinet.pick_model_dir(str(Path(tmp) / "missing"), bundled)
            self.assertEqual(chosen, bundled)

    def test_empty_setting_uses_the_project_copy(self):
        with tempfile.TemporaryDirectory() as tmp:
            bundled = Path(tmp) / "models" / "laya"
            self.assertEqual(cabinet.pick_model_dir("", bundled), bundled)


if __name__ == "__main__":
    unittest.main()
