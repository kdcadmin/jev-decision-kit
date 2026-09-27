import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from host.gate import decision_from_votes
from host.tool_memory import collect_turns, remembered_doors


class ToolMemoryTests(unittest.TestCase):
    def test_finished_browser_call_becomes_a_door(self):
        samples = collect_turns(
            [
                {"role": "user", "content": "帮我把这个后台页面点开并登录", "source": "hermes"},
                {
                    "role": "assistant",
                    "tool_calls": [{"name": "browser_exec", "arguments": {}}],
                },
                {"role": "tool", "content": "clicked"},
            ]
        )
        self.assertEqual(samples[0][1], {"web-act"})

    def test_next_sentence_can_drop_the_door(self):
        samples = collect_turns(
            [
                {"role": "user", "content": "写成一份 Word", "source": "hermes"},
                {
                    "role": "assistant",
                    "tool_calls": [{"name": "skill_view", "arguments": {"name": "docx"}}],
                },
                {"role": "tool", "content": "ok"},
                {"role": "user", "content": "不要写 Word"},
            ]
        )
        self.assertEqual(samples, [])

    def test_a_remembered_phrasing_can_open_its_door(self):
        samples = [{"task": "帮我把这个后台页面点开并登录", "doors": ["web-act"]}]
        self.assertIn("web-act", remembered_doors("帮我把这个后台页面点开并登录一下", samples))
        self.assertEqual(remembered_doors("今天天气很好", samples), set())
        gates = [
            {"id": "web-act", "label": "操作网页", "blurb": "操作", "items": [{"name": "agent-browser", "path": "a"}]}
        ]
        decided = decision_from_votes(
            {"web-act": 0.75},
            gates,
            None,
            {},
            task="帮我把这个后台页面点开并登录一下",
            remembered={"web-act"},
        )
        self.assertEqual(decided["skills"][0]["name"], "agent-browser")

    def test_current_negation_beats_habit(self):
        from unittest.mock import patch

        import cabinet

        with patch("host.tool_memory.remembered_doors", return_value={"office-docx"}):
            routed = cabinet.route_task("不要用 Word", "test", record=False)
        self.assertEqual(routed["method"], "think")
        self.assertEqual(routed["skills"], [])

    def test_fixture_habit_can_recover_named_thesis(self):
        from unittest.mock import patch

        import cabinet
        from host.tool_memory import remembered_doors
        import json

        samples = json.loads((ROOT / "tests" / "memory_fixture.json").read_text(encoding="utf-8"))
        with patch(
            "host.tool_memory.remembered_doors",
            lambda text, samples_arg=None, line=0.72: remembered_doors(text, samples, line),
        ):
            routed = cabinet.route_task("不要用 PDF，给我论文", "test", record=False)
        self.assertEqual([item["name"] for item in routed["skills"]], ["chinese-thesis-workbench"])


if __name__ == "__main__":
    unittest.main()
