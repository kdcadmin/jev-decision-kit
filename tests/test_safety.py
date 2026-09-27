import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import cabinet


class SafetyTests(unittest.TestCase):
    def test_push_keeps_extra_origin_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            kit = root / "kit"
            origin = root / "origin"
            kit.mkdir(parents=True, exist_ok=True)
            origin.mkdir(parents=True, exist_ok=True)
            (kit / "a.txt").write_text("new", encoding="utf-8")
            (origin / "a.txt").write_text("old", encoding="utf-8")
            (origin / "keep.txt").write_text("keep", encoding="utf-8")
            cabinet._mirror(kit, origin, delete_extra=False)
            self.assertEqual((origin / "a.txt").read_text(encoding="utf-8"), "new")
            self.assertEqual((origin / "keep.txt").read_text(encoding="utf-8"), "keep")

    def test_get_skill_needs_this_decision(self):
        memory = {"calls": [{"id": "a1", "method": "skill", "skills": ["docx"]}, {"id": "b2", "method": "skill", "skills": ["pdf"]}], "rules": {}}
        original = cabinet.load_memory
        cabinet.load_memory = lambda: memory
        try:
            from mcp_server import allowed_skill_names

            self.assertEqual(allowed_skill_names("a1"), {"docx"})
            self.assertEqual(allowed_skill_names("b2"), {"pdf"})
            self.assertEqual(allowed_skill_names(""), set())
        finally:
            cabinet.load_memory = original

    def test_github_backslash_cannot_escape(self):
        with self.assertRaises(ValueError):
            cabinet.parse_github("https://github.com/ada/demo/tree/main/..\\..\\Windows")


if __name__ == "__main__":
    unittest.main()
