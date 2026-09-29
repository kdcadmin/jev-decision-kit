import json
import sys
import unittest
from datetime import date, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from host.writer_protocol import append, compact_read, ensure, roll_if_new_day, session_hint, today_stamp
from host.writer_protocol.mcp import TOOLS, call_tool, handle


class WriterProtocolTests(unittest.TestCase):
    def test_creates_missing_protocol_and_compact_read_stays_short(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".git").mkdir()
            path = ensure(root)
            self.assertTrue(path.is_file())
            append(root, "Cursor", ["host/writer_protocol/__init__.py"], "完成", "建引擎")
            body = compact_read(root)
            self.assertTrue(body.startswith("jev-writer:"))
            self.assertIn("host/writer_protocol/__init__.py", body)
            self.assertLess(len(body), 3500)
            hint = session_hint(root)
            self.assertTrue(hint.startswith("jev-writer:"))
            self.assertNotIn("## 2. 硬规则", hint)

    def test_new_calendar_day_archives_yesterday_and_keeps_standing_rules(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".git").mkdir()
            yesterday = (date.today() - timedelta(days=1)).isoformat()
            (root / "WRITER-PROTOCOL.md").write_text(
                f"# 写者协议\n\n<!-- writer-day: {yesterday} -->\n\n"
                "## 2. 硬规则\n\n文件级单写者。KEEP_STANDING。\n\n"
                "## 7. 今天的台账\n\n| 时间 | 写者 | 范围 | 状态 | 提交 |\n"
                "|---|---|---|---|---|\n"
                "| 10:00 | Cursor | foo.py | 完成 | abc |\n\n"
                "## 昨日摘要\n\n旧摘要\n",
                encoding="utf-8",
            )
            self.assertTrue(roll_if_new_day(root))
            archive = root / "writer-log" / f"{yesterday}.md"
            self.assertTrue(archive.is_file())
            now = (root / "WRITER-PROTOCOL.md").read_text(encoding="utf-8")
            self.assertIn(today_stamp(), now)
            self.assertIn("KEEP_STANDING", now)
            self.assertIn("foo.py", now)
            self.assertIn("新的一天", now)

    def test_mcp_read_and_append_round_trip(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".git").mkdir()
            listed = handle({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
            names = {tool["name"] for tool in listed["result"]["tools"]}
            self.assertEqual(names, {"writer_protocol_read", "writer_protocol_append"})
            self.assertEqual(len(TOOLS), 2)
            read = call_tool("writer_protocol_read", {"root": str(root)})
            self.assertFalse(read["isError"])
            self.assertIn("jev-writer:", read["content"][0]["text"])
            added = call_tool(
                "writer_protocol_append",
                {"root": str(root), "writer": "Cursor", "files": ["a.py"], "status": "完成", "note": "测"},
            )
            self.assertFalse(added["isError"])
            payload = json.loads(added["content"][0]["text"])
            self.assertTrue(payload["ok"])
            compact = compact_read(root)
            self.assertIn("a.py", compact)


if __name__ == "__main__":
    unittest.main()
