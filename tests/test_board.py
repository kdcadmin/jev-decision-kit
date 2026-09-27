import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from host.board import apply_rows, mcp_from_source, plugin_from_source


class BoardTests(unittest.TestCase):
    def test_switch_hides_and_added_rows_stay_out_of_secrets(self):
        scanned = [{"name": "latex", "host": "Codex", "enabled": True, "canSelect": True, "selectable": True, "words": ["latex"]}]
        board = {
            "pluginHidden": [],
            "pluginEnabled": {"Codex\tlatex": False},
            "pluginAdded": [{"name": "demo-plugin", "source": "D:\\plugins\\demo", "kind": "local", "blurb": "本地"}],
            "mcpHidden": ["Cursor\tgodot-ai"],
            "mcpEnabled": {},
            "mcpAdded": [{"name": "desk", "source": "https://example.com/mcp", "kind": "link"}],
        }
        plugins = apply_rows(scanned, "plugin", board)
        latex = next(item for item in plugins if item["name"] == "latex")
        self.assertFalse(latex["enabled"])
        self.assertFalse(latex["selectable"])
        self.assertTrue(any(item["name"] == "demo-plugin" and item["host"] == "技能柜" for item in plugins))
        servers = apply_rows(
            [{"name": "godot-ai", "host": "Cursor", "enabled": True}, {"name": "node_repl", "host": "Codex", "enabled": True}],
            "mcp",
            board,
        )
        names = {item["name"] for item in servers}
        self.assertNotIn("godot-ai", names)
        self.assertIn("desk", names)
        self.assertNotIn("TOKEN", str(plugins))

    def test_sources(self):
        plugin = plugin_from_source("github", "https://github.com/ada/demo-plugin")
        self.assertEqual(plugin["name"], "demo-plugin")
        mcp = mcp_from_source("link", "https://example.com/mcp")
        self.assertEqual(mcp["kind"], "link")
        with self.assertRaises(ValueError):
            plugin_from_source("package", "not a package")
        with self.assertRaises(ValueError):
            mcp_from_source("github", "https://gitlab.com/a/b")


if __name__ == "__main__":
    unittest.main()
