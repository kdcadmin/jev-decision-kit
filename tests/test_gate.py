import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from host.gate import GATE, available_gates, decision_from_votes, format_preface, noul_questions
import cabinet


class GateTests(unittest.TestCase):
    def test_door_is_short_and_present(self):
        catalog = cabinet.load_catalog()
        gates = available_gates(catalog)
        ids = {gate["id"] for gate in gates}
        self.assertGreaterEqual(len(gates), 18)
        self.assertLess(len(gates), 30)
        self.assertIn("market-data", ids)
        self.assertIn("vox-video", ids)
        self.assertNotIn("github-project-video", ids)
        self.assertNotIn("minimax-gen", ids)
        self.assertNotIn("minimax-music", ids)
        self.assertNotIn("gif-sticker", ids)
        questions = noul_questions(gates)
        self.assertNotIn("swot-analysis", questions)
        self.assertNotIn("think", questions)
        self.assertIn("market-data", questions)
        self.assertEqual(questions["market-data"]["type"], "noul")

    def test_choice_returns_the_door_skill(self):
        catalog = {"skills": []}
        gates = [
            {
                "id": "market-data",
                "label": "行情",
                "blurb": "查股价",
                "items": [{"name": "china-stock-data", "path": "D:\\kit\\china-stock-data", "summary": "dirty"}],
            }
        ]
        decided = decision_from_votes({"market-data": 0.7}, gates, None, {}, task="现在多少钱")
        self.assertEqual(decided["method"], "skill")
        self.assertEqual(decided["skills"][0]["name"], "china-stock-data")
        self.assertEqual(decided["skills"][0]["summary"], "查股价")

    def test_added_skill_survives_think(self):
        by_name = {"meeting-minutes": {"name": "meeting-minutes", "summary": "纪要", "path": "D:\\kit\\meeting-minutes"}}
        decided = decision_from_votes({}, [], {"add": ["meeting-minutes"], "remove": []}, by_name)
        self.assertEqual(decided["method"], "skill")
        self.assertEqual(decided["skills"][0]["name"], "meeting-minutes")

    def test_preface_for_think_and_skill(self):
        think = format_preface({"enabled": True, "method": "think", "skills": []}, {})
        self.assertIn("自己做", think)
        self.assertIn("【技能柜】", think)
        skill = format_preface(
            {"enabled": True, "method": "skill", "skills": [{"name": "docx"}]},
            {"docx": "按模板写"},
        )
        self.assertIn("## docx", skill)
        self.assertIn("按模板写", skill)
        self.assertIn("已选定：docx。", skill)

    def test_several_doors_stay_and_low_ones_drop(self):
        gates = [
            {"id": "market-data", "label": "行情", "blurb": "查股价", "items": [{"name": "china-stock-data", "path": "a"}]},
            {"id": "office-docx", "label": "Word", "blurb": "写文档", "items": [{"name": "docx", "path": "b"}]},
            {"id": "xiaohei", "label": "小黑插图", "blurb": "配图", "items": [{"name": "xiaohei-illustration", "path": "c"}]},
            {"id": "thesis", "label": "论文", "blurb": "写论文", "items": [{"name": "chinese-thesis-workbench", "path": "d"}]},
        ]
        decided = decision_from_votes(
            {"market-data": 0.91, "office-docx": 0.72, "xiaohei": 0.61, "thesis": 0.16},
            gates,
            None,
            {},
            task="查股价，写成 Word，再配一张小黑风格的图",
        )
        self.assertEqual(
            [skill["name"] for skill in decided["skills"]],
            ["china-stock-data", "docx", "xiaohei-illustration"],
        )
        self.assertEqual(decided["label"], "行情、Word、小黑插图")

    def test_one_door_can_bring_two_skills(self):
        gates = [
            {
                "id": "godot",
                "label": "Godot",
                "blurb": "改游戏",
                "items": [
                    {"name": "godot-gamedev", "path": "a"},
                    {"name": "godot-ai-mcp", "path": "b"},
                ],
            }
        ]
        decided = decision_from_votes({"godot": 0.8}, gates, None, {}, task="改一下 Godot")
        self.assertEqual([skill["name"] for skill in decided["skills"]], ["godot-gamedev", "godot-ai-mcp"])

    def test_unnamed_high_score_is_dropped_and_five_named_doors_stay(self):
        gates = [
            {"id": "knowledge", "label": "资料库", "blurb": "建库", "items": [{"name": "knowledge-pipeline", "path": "a"}]},
            {"id": "git-backup", "label": "远程备份", "blurb": "备份", "items": [{"name": "git-remote-backup", "path": "b"}]},
            {"id": "market-data", "label": "行情", "blurb": "查股价", "items": [{"name": "china-stock-data", "path": "c"}]},
            {"id": "web-read", "label": "读网页", "blurb": "读网页", "items": [{"name": "web-access", "path": "d"}]},
            {"id": "office-docx", "label": "Word", "blurb": "写文档", "items": [{"name": "docx", "path": "e"}]},
            {"id": "office-pptx", "label": "幻灯片", "blurb": "做片子", "items": [{"name": "pptx", "path": "f"}]},
            {"id": "xiaohei", "label": "小黑插图", "blurb": "配图", "items": [{"name": "xiaohei-illustration", "path": "g"}]},
        ]
        decided = decision_from_votes(
            {
                "knowledge": 0.9,
                "git-backup": 0.88,
                "market-data": 0.83,
                "web-read": 0.81,
                "office-docx": 0.8,
                "office-pptx": 0.75,
                "xiaohei": 0.65,
            },
            gates,
            None,
            {},
            task="查股价和涨跌，写成一份 Word，配一张小黑风格的配图，再做一份幻灯片，并打开 https://example.com",
        )
        self.assertEqual(
            [skill["name"] for skill in decided["skills"]],
            ["china-stock-data", "web-access", "docx", "pptx", "xiaohei-illustration"],
        )

    def test_named_door_can_pass_at_point_four(self):
        gates = [
            {"id": "office-docx", "label": "Word", "blurb": "写文档", "items": [{"name": "docx", "path": "a"}]},
            {"id": "xiaohei", "label": "小黑插图", "blurb": "配图", "items": [{"name": "xiaohei-illustration", "path": "b"}]},
            {"id": "knowledge", "label": "资料库", "blurb": "建库", "items": [{"name": "knowledge-pipeline", "path": "c"}]},
        ]
        decided = decision_from_votes(
            {"office-docx": 0.45, "xiaohei": 0.3, "knowledge": 0.9},
            gates,
            None,
            {},
            task="写成 Word，再配一张小黑风格的图",
        )
        self.assertEqual([skill["name"] for skill in decided["skills"]], ["docx"])

    def test_negation_drops_the_named_door(self):
        gates = [
            {"id": "office-docx", "label": "Word", "blurb": "写文档", "items": [{"name": "docx", "path": "a"}]},
            {"id": "office-xlsx", "label": "表格", "blurb": "表格", "items": [{"name": "xlsx", "path": "b"}]},
        ]
        decided = decision_from_votes(
            {"office-docx": 0.9, "office-xlsx": 0.8},
            gates,
            None,
            {},
            task="把数字放进 Excel，不要写 Word",
        )
        self.assertEqual([skill["name"] for skill in decided["skills"]], ["xlsx"])

    def test_trailing_negation_and_not_a_false_friend(self):
        from host.gate import sentence_names

        pdf = {"id": "office-pdf", "words": ("PDF", "pdf")}
        docx = {"id": "office-docx", "words": ("Word", "word", "docx")}
        self.assertFalse(sentence_names("给我 Word 就行，PDF 不要", pdf))
        self.assertTrue(sentence_names("请特别做一份 PDF 报告", pdf))
        self.assertTrue(sentence_names("分别导出 PDF 和 Word", pdf))
        self.assertFalse(sentence_names("这段代码里的 word 变量是什么意思", docx))
        self.assertFalse(sentence_names("请解释 PDF 和 Word 的区别", docx))
        self.assertFalse(sentence_names("我说的是WordPress建站，不是Word文档", docx))

    def test_clause_negation_does_not_cancel_the_next_job(self):
        from host.gate import sentence_names

        read = {"id": "web-read", "words": ("网页", "网址", "链接", "http", "https")}
        act = {"id": "web-act", "words": ("点击", "填写", "填表", "提交", "登录")}
        self.assertFalse(sentence_names("不要读网页，只要点击登录", read))
        self.assertTrue(sentence_names("不要读网页，只要点击登录", act))

    def test_word_next_to_chinese_and_reclaim(self):
        from host.gate import format_preface, sentence_names

        docx = {"id": "office-docx", "words": ("Word", "word", "docx")}
        pdf = {"id": "office-pdf", "words": ("PDF", "pdf")}
        xlsx = {"id": "office-xlsx", "words": ("表格", "Excel", "excel", "xlsx")}
        self.assertTrue(sentence_names("用Word写一份报告", docx))
        self.assertTrue(sentence_names("不要 PDF 只要 Word", docx))
        self.assertFalse(sentence_names("不要 PDF 只要 Word", pdf))
        self.assertTrue(sentence_names("不要用 Word，还是用 Word 吧", docx))
        self.assertTrue(sentence_names("先解释 PDF 和 Word 的区别，然后导出 Word", docx))
        self.assertFalse(sentence_names("先解释 PDF 和 Word 的区别，然后导出 Word", pdf))
        self.assertTrue(sentence_names("做一个表格对比 PDF 和 Word 的区别", xlsx))
        self.assertFalse(sentence_names("这个 PDF 有什么用", pdf))
        self.assertFalse(sentence_names("Word 怎么用", docx))
        self.assertFalse(sentence_names("Excel 和表格有什么区别", xlsx))
        self.assertFalse(sentence_names("PDF 是什么", pdf))
        pptx = {"id": "office-pptx", "words": ("幻灯片", "ppt", "PPT", "pptx", "演示文稿")}
        self.assertTrue(sentence_names("不要用 PDF，给我 pptx", pptx))
        self.assertFalse(sentence_names("不要用 PDF，给我 pptx", pdf))
        self.assertTrue(sentence_names("记成一份表格", xlsx))
        self.assertTrue(sentence_names("导出成 Excel", xlsx))
        self.assertTrue(sentence_names("做成一份 xlsx", xlsx))
        preface = format_preface(
            {"enabled": True, "method": "skill", "skills": [{"name": "docx"}, {"name": "pdf"}]},
            {"docx": "x" * 30000, "pdf": "y" * 30000},
        )
        self.assertTrue(preface.startswith("【技能柜】已选定：docx、pdf。"))
        self.assertIn("docx", preface[:80])
        self.assertIn("pdf", preface[:80])

    def test_route_uses_the_door(self):
        routed = cabinet.route_task("看一下茅台现在多少钱", "test", record=False)
        names = [skill["name"] for skill in routed["skills"]]
        self.assertEqual(routed["method"], "skill")
        self.assertEqual(names, ["china-stock-data"])
        self.assertEqual(routed["category"], "market-data")

    def test_answer_key_matches_the_door(self):
        catalog = cabinet.load_catalog()
        ids = {gate["id"] for gate in available_gates(catalog)} | {"think"}
        tasks = json.loads((ROOT / "tests" / "gate_tasks.json").read_text(encoding="utf-8"))
        self.assertGreaterEqual(len(tasks), 20)
        for item in tasks:
            self.assertIn(item["expect"], ids)
        declared = {entry["id"] for entry in GATE}
        self.assertTrue(declared <= ids)

    def test_named_jobs_from_the_eval_set_stay_open(self):
        expect = {
            "盯盘今天有没有提醒": "盯盘",
            "读一下这个 PDF": "PDF",
            "把这张表算一下": "表格",
            "在网页上把这个表单填完": "操作网页",
            "宁德时代今天涨了多少，整理进 Excel": "行情、表格",
            "最近一个月大家在讨论什么": "近三十天",
        }
        for text, label in expect.items():
            routed = cabinet.route_task(text, "test", record=False)
            self.assertEqual(routed["label"], label, text)


if __name__ == "__main__":
    unittest.main()
