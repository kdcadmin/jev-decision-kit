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

    def test_latest_decision_serves_hosts_without_an_id(self):
        from datetime import datetime, timedelta
        from unittest.mock import patch

        import mcp_server

        now = datetime.now().astimezone()
        fresh = (now - timedelta(seconds=30)).isoformat(timespec="seconds")
        stale = (now - timedelta(hours=3)).isoformat(timespec="seconds")
        memory = {"calls": [
            {"id": "stale1", "at": stale, "method": "skill", "skills": ["pdf"], "source": "cursor"},
            {"id": "fresh1", "at": fresh, "method": "skill", "skills": ["docx"], "source": "harness"},
        ], "rules": {}}
        with patch.object(cabinet, "load_memory", return_value=memory):
            self.assertEqual("fresh1", mcp_server.latest_decision_id())
            self.assertEqual("fresh1", mcp_server.latest_decision_id("harness"))
            self.assertEqual("", mcp_server.latest_decision_id("cursor"))
        only_stale = {"calls": [{"id": "stale1", "at": stale, "method": "skill", "skills": ["pdf"], "source": "cursor"}], "rules": {}}
        with patch.object(cabinet, "load_memory", return_value=only_stale):
            self.assertEqual("", mcp_server.latest_decision_id())

    def test_get_skill_without_an_id_reads_the_latest_decision(self):
        import json as jsonlib
        from datetime import datetime
        from unittest.mock import patch

        import mcp_server

        now = datetime.now().astimezone().isoformat(timespec="seconds")
        memory = {"calls": [{"id": "fresh1", "at": now, "method": "skill", "skills": ["docx"], "source": "harness"}], "rules": {}}
        skill = {"name": "docx", "category": "docs", "content": "正文内容", "summary": "", "path": "", "scripts": []}
        with patch.object(cabinet, "load_memory", return_value=memory), \
             patch.object(cabinet, "read_skill", return_value=skill):
            result = mcp_server.call_tool("get_skill", {"name": "docx"})
            self.assertFalse(result["isError"], result)
            payload = jsonlib.loads(result["content"][0]["text"])
            self.assertEqual("fresh1", payload["decisionId"])
            self.assertEqual("正文内容", payload["content"])
            refused = mcp_server.call_tool("get_skill", {"name": "pdf"})
            self.assertTrue(refused["isError"])

    def test_github_backslash_cannot_escape(self):
        with self.assertRaises(ValueError):
            cabinet.parse_github("https://github.com/ada/demo/tree/main/..\\..\\Windows")


if __name__ == "__main__":
    unittest.main()
