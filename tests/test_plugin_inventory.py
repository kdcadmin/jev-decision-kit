import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from host.gate import WORDS, decision_from_votes, format_preface
from host.plugin_inventory import list_plugins, plugin_gates


class PluginInventoryTests(unittest.TestCase):
    def test_reads_names_and_skips_secrets_and_mcp_wrapper(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            hermes = home / ".hermes" / "plugins"
            (hermes / "planning-with-files").mkdir(parents=True)
            (hermes / "planning-with-files" / "plugin.yaml").write_text(
                "name: planning-with-files\ndescription: keep a plan\ncommand: secret-bin\n",
                encoding="utf-8",
            )
            (hermes / "jev-skill-kit").mkdir()
            (hermes / "jev-skill-kit" / "plugin.yaml").write_text(
                "name: jev-skill-kit\ndescription: cabinet hook\n",
                encoding="utf-8",
            )
            codex = home / ".codex" / "plugins" / "cache" / "demo" / "codex-app-tools" / "1" / ".codex-plugin"
            codex.mkdir(parents=True)
            (codex / "plugin.json").write_text(
                json.dumps({"name": "codex-app-tools", "description": "mcp wrapper", "command": "secret-bin", "env": {"TOKEN": "hidden"}}),
                encoding="utf-8",
            )
            cached = home / ".cursor" / "plugins" / "cache" / "datadog" / "abc" / ".cursor-plugin"
            cached.mkdir(parents=True)
            (cached / "plugin.json").write_text(
                json.dumps({"name": "datadog", "description": "leftover cache", "token": "hidden"}),
                encoding="utf-8",
            )
            figma = home / ".cursor" / "plugins" / "local" / "figma" / ".cursor-plugin"
            figma.mkdir(parents=True)
            (figma / "plugin.json").write_text(
                json.dumps({"name": "figma", "description": "draw", "enabled": True, "token": "hidden"}),
                encoding="utf-8",
            )
            harness = home / "harness" / "profiles" / "desktop"
            harness.mkdir(parents=True)
            (harness / "package.json").write_text(
                json.dumps({"dsh": {"profile": {"bundles": ["@deepseek-ai/dsh-base", "@deepseek-ai/dsh-experimental-voice-input-bundle"]}}}),
                encoding="utf-8",
            )
            report = list_plugins(home, home / "harness")
            by_name = {item["name"]: item for item in report["plugins"]}
            self.assertTrue(by_name["planning-with-files"]["selectable"])
            self.assertFalse(by_name["jev-skill-kit"]["selectable"])
            self.assertFalse(by_name["codex-app-tools"]["selectable"])
            self.assertFalse(by_name["@deepseek-ai/dsh-base"]["selectable"])
            self.assertNotIn("datadog", by_name)
            self.assertTrue(by_name["figma"]["selectable"])
            self.assertTrue(by_name["@deepseek-ai/dsh-experimental-voice-input-bundle"]["selectable"])
            blob = json.dumps(report)
            self.assertNotIn("secret", blob)
            self.assertNotIn("hidden", blob)
            self.assertNotIn("TOKEN", blob)
            doors = {gate["id"] for gate in plugin_gates(home, home / "harness")}
            self.assertIn("plugin-figma", doors)
            self.assertIn("plugin-planning-with-files", doors)
            self.assertNotIn("plugin-jev-skill-kit", doors)
            self.assertNotIn("plugin-codex-app-tools", doors)

    def test_plugin_words_do_not_reuse_skill_words(self):
        taken = {word.casefold() for values in WORDS.values() for word in values}
        for gate in plugin_gates():
            for word in gate["words"]:
                self.assertNotIn(word.casefold(), taken, gate["id"])

    def test_named_plugin_stays_with_a_skill_and_negation_drops_it(self):
        figma = {
            "id": "plugin-figma",
            "label": "Figma",
            "blurb": "在 Figma 里做界面。",
            "words": ("Figma", "figma"),
            "items": [{"name": "figma", "path": "", "kind": "plugin", "host": "Cursor"}],
        }
        word = [
            {"id": "office-docx", "label": "Word", "blurb": "写文档", "items": [{"name": "docx", "path": "a"}]},
            figma,
        ]
        both = decision_from_votes(
            {"office-docx": 0.8, "plugin-figma": 0.7},
            word,
            None,
            {},
            task="用 Figma 出一版，再写成 Word",
        )
        self.assertEqual([item["name"] for item in both["skills"]], ["docx", "figma"])
        self.assertEqual(both["skills"][1]["kind"], "plugin")
        dropped = decision_from_votes(
            {"plugin-figma": 0.9},
            [figma],
            None,
            {},
            task="不要用 Figma",
        )
        self.assertEqual(dropped["skills"], [])
        preface = format_preface({"enabled": True, "method": "skill", "skills": both["skills"]}, {"docx": "按模板写"})
        self.assertIn("技能和插件", preface)
        self.assertIn("## docx", preface)
        self.assertIn("## 插件 figma", preface)
        self.assertIn("Cursor", preface)

    def test_live_plugins_keep_the_cabinet_hook_off_the_door(self):
        report = list_plugins()
        names = {item["name"] for item in report["plugins"]}
        self.assertIn("planning-with-files", names)
        self.assertIn("latex", names)
        self.assertNotIn("figma", names)
        self.assertNotIn("notion-workspace", names)
        self.assertNotIn("datadog", names)
        kit = next(item for item in report["plugins"] if item["name"] == "jev-skill-kit")
        self.assertFalse(kit["selectable"])
        doors = {gate["id"] for gate in plugin_gates()}
        self.assertIn("plugin-latex", doors)
        self.assertNotIn("plugin-jev-skill-kit", doors)
        self.assertNotIn("plugin-codex-app-tools", doors)


class HarnessPluginTests(unittest.TestCase):
    def test_harness_bundle_declares_patch_and_pre_step_hook(self):
        folder = ROOT / "host" / "harness_plugin"
        manifest = json.loads((folder / "package.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["name"], "dsh-jev-skill-kit")
        self.assertEqual(manifest["dsh"]["bundle"]["patch"], "./cordis.patch.yml")
        self.assertTrue((folder / "cordis.patch.yml").is_file())
        source = (folder / "index.js").read_text(encoding="utf-8")
        self.assertIn("agent/pre-step", source)
        self.assertIn("source: \"harness\"", source)


if __name__ == "__main__":
    unittest.main()
