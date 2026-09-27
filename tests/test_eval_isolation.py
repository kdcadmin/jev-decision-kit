import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from host.plugin_inventory import plugin_gates
from host.train_jev import BLIND_FILE, EVAL_FILE, MULTI, NONE, POS, held_out_texts, replace_if_not_worse
from hosts import upsert_mcp_block, sync_hermes


class EvalIsolationTests(unittest.TestCase):
    def test_eval_file_not_in_hand_rows(self):
        held = held_out_texts()
        trained = set()
        for lines in POS.values():
            trained.update(lines)
        trained.update(line for line, _labels in MULTI)
        trained.update(NONE)
        for gate in plugin_gates():
            for word in gate.get("words") or ():
                trained.add("请用" + str(word) + "做这件事")
        leaked = sorted(trained & held)
        self.assertEqual(leaked, [])

    def test_blind_set_is_disjoint_from_regression(self):
        regression = {str(item.get("text") or "") for item in json.loads(EVAL_FILE.read_text(encoding="utf-8")).get("cases") or []}
        blind = {str(item.get("text") or "") for item in json.loads(BLIND_FILE.read_text(encoding="utf-8")).get("cases") or []}
        self.assertGreaterEqual(len(blind), 30)
        self.assertEqual(sorted(regression & blind), [])

    def test_memory_fixture_is_not_an_eval_sentence(self):
        held = held_out_texts()
        samples = json.loads((ROOT / "tests" / "memory_fixture.json").read_text(encoding="utf-8"))
        texts = [str(item.get("task") or "").strip() for item in samples]
        self.assertEqual([text for text in texts if text in held], [])
        from host.tool_memory import remembered_doors

        self.assertIn("thesis", remembered_doors("不要用 PDF，给我论文", samples))
        self.assertIn("web-act", remembered_doors("填表提交之后导出成 PDF", samples))
        self.assertEqual(remembered_doors("不要用 Word", samples), set())

    def test_asking_sentences_do_not_open_doors(self):
        import cabinet

        questions = [
            "这个 PDF 有什么用",
            "PDF 到底怎么用",
            "Word 怎么用",
            "PDF 用不了怎么办",
            "Word 和 Excel 哪个好用",
            "PDF 是什么",
            "Excel 和表格有什么区别",
            "什么是 Word",
        ]
        for text in questions:
            routed = cabinet.route_task(text, "test", record=False)
            self.assertEqual(routed["skills"], [], text)
            self.assertEqual(routed["method"], "think", text)

    def test_thesis_request_is_named(self):
        from host.gate import sentence_names

        thesis = {"id": "thesis", "words": ("论文",)}
        self.assertTrue(sentence_names("不要用 PDF，给我论文", thesis))


class HostYamlTests(unittest.TestCase):
    def test_upsert_keeps_neighbors_and_writes_backup(self):
        original = "mcp_servers:\n  studio-api:\n    command: node\n    enabled: true\nplatforms:\n  api_server:\n    port: 1\n"
        block = "  jev-skill-kit:\n    command: py\n    enabled: true\n"
        added = upsert_mcp_block(original, block)
        self.assertIn("studio-api:", added)
        self.assertIn("jev-skill-kit:", added)
        self.assertIn("platforms:", added)
        again = upsert_mcp_block(added, "  jev-skill-kit:\n    command: py2\n    enabled: false\n")
        self.assertEqual(again.count("jev-skill-kit:"), 1)
        self.assertIn("command: py2", again)
        self.assertIn("studio-api:", again)
        self.assertIn("platforms:", again)
        self.assertIn("api_server:", again)
        last = (
            "mcp_servers:\n"
            "  jev-skill-kit:\n"
            "    command: old\n"
            "model:\n"
            "  name: keep-me\n"
        )
        updated = upsert_mcp_block(last, "  jev-skill-kit:\n    command: new\n")
        self.assertIn("model:", updated)
        self.assertIn("keep-me", updated)
        self.assertGreater(updated.index("model:"), updated.index("jev-skill-kit:"))
        self.assertGreater(updated.index("name: keep-me"), updated.index("model:"))
        hermes = (
            "mcp_servers:\n"
            "  studio-api:\n"
            "    command: node\n"
            "  jev-skill-kit:\n"
            "    command: old\n"
            "    enabled: true\n"
            "platforms:\n"
            "  api_server:\n"
            "    extra:\n"
            "      port: 8647\n"
        )
        same = upsert_mcp_block(hermes, "  jev-skill-kit:\n    command: old\n    enabled: true\n")
        self.assertIn("platforms:", same)
        self.assertLess(same.index("jev-skill-kit:"), same.index("platforms:"))
        self.assertGreater(same.index("api_server:"), same.index("platforms:"))
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.yaml"
            path.write_text(original, encoding="utf-8")
            sync_hermes(True, path)
            backup = Path(str(path) + ".jev.bak")
            self.assertTrue(backup.is_file())
            self.assertEqual(backup.read_text(encoding="utf-8"), original)
            self.assertIn("jev-skill-kit:", path.read_text(encoding="utf-8"))


class TrainPublishTests(unittest.TestCase):
    def test_replace_if_not_worse_restores_old_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "head.json"
            path.write_text("old", encoding="utf-8")
            calls = {"n": 0}

            def score() -> int:
                calls["n"] += 1
                return 5 if calls["n"] == 1 else 3

            kept, before, after = replace_if_not_worse(path, {"ok": 1}, score)
            self.assertFalse(kept)
            self.assertEqual((before, after), (5, 3))
            self.assertEqual(path.read_text(encoding="utf-8"), "old")

    def test_replace_if_not_worse_keeps_equal_or_better(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "head.json"
            path.write_text("old", encoding="utf-8")
            calls = {"n": 0}

            def score() -> int:
                calls["n"] += 1
                return 5

            kept, before, after = replace_if_not_worse(path, {"ok": 1}, score)
            self.assertTrue(kept)
            self.assertEqual((before, after), (5, 5))
            self.assertIn('"ok": 1', path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
