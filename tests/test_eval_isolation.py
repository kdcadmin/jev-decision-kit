import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from host.plugin_inventory import plugin_gates
from host.train_jev import BLIND_FILE, EVAL_FILE, MULTI, NONE, POS, held_out_texts
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
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.yaml"
            path.write_text(original, encoding="utf-8")
            sync_hermes(True, path)
            backup = Path(str(path) + ".jev.bak")
            self.assertTrue(backup.is_file())
            self.assertEqual(backup.read_text(encoding="utf-8"), original)
            self.assertIn("jev-skill-kit:", path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
