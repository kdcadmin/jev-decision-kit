import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from host.mcp_inventory import list_mcp_servers


class McpInventoryTests(unittest.TestCase):
    def test_lists_names_and_skips_secrets(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            (home / ".cursor").mkdir()
            (home / ".cursor" / "mcp.json").write_text(
                json.dumps({"mcpServers": {"godot-ai": {"command": "secret-bin", "env": {"TOKEN": "nope"}}}}),
                encoding="utf-8",
            )
            (home / ".openclaw").mkdir()
            (home / ".openclaw" / "openclaw.json").write_text(
                json.dumps({"mcp": {"servers": {"jev-skill-kit": {"command": "python", "enabled": True}}}}),
                encoding="utf-8",
            )
            (home / ".openclaw" / "mcp-minimax.json").write_text(
                json.dumps({"command": "node", "env": {"KEY": "hidden"}}),
                encoding="utf-8",
            )
            (home / ".hermes").mkdir()
            (home / ".hermes" / "config.yaml").write_text(
                "mcp_servers:\n  studio-api:\n    command: node\n    enabled: true\n    env:\n      TOKEN: hidden\nplatforms:\n  api_server:\n    port: 1\n",
                encoding="utf-8",
            )
            (home / ".codex").mkdir()
            (home / ".codex" / "config.toml").write_text(
                "[mcp_servers.node_repl]\ncommand = 'secret'\n\n[mcp_servers.node_repl.env]\nTOKEN = 'hidden'\n",
                encoding="utf-8",
            )
            report = list_mcp_servers(home)
            names = {(item["host"], item["name"]) for item in report["servers"]}
            self.assertEqual(
                names,
                {("Cursor", "godot-ai"), ("龙虾", "jev-skill-kit"), ("龙虾", "minimax"), ("Hermes", "studio-api"), ("Codex", "node_repl")},
            )
            blob = json.dumps(report)
            self.assertNotIn("secret", blob)
            self.assertNotIn("hidden", blob)
            self.assertNotIn("TOKEN", blob)


if __name__ == "__main__":
    unittest.main()
