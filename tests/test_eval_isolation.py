import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from host.train_jev import EVAL_FILE, EXAM, MULTI, NONE, POS


class EvalIsolationTests(unittest.TestCase):
    def test_eval_file_not_in_hand_rows(self):
        held = {str(item.get("text") or "").strip() for item in json.loads(EVAL_FILE.read_text(encoding="utf-8")).get("cases") or []}
        held |= set(EXAM)
        held.discard("")
        trained = set()
        for lines in POS.values():
            trained.update(lines)
        trained.update(line for line, _labels in MULTI)
        trained.update(NONE)
        leaked = sorted(trained & held)
        self.assertEqual(leaked, [])

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


if __name__ == "__main__":
    unittest.main()
