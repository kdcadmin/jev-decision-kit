import tempfile
import unittest
import json
import threading
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

import cabinet
from host import delegation
from host import preface_worker
from host import hermes_plugin
from host.hermes_plugin.install import install_plugin
from host.hermes_plugin.install import install_shell_hooks, uninstall_shell_hooks
from host.hermes_core_patch import install as install_core_patch, undo as undo_core_patch
from host.hermes_shell_hook import handle as handle_shell_hook


class DelegationTests(unittest.TestCase):
    def test_each_child_gets_own_effort_and_explicit_level_wins(self):
        tasks = [{"goal": "搜索资料"}, {"goal": "调试复杂架构"}, {"goal": "写摘要", "reasoning_effort": "xhigh"}]
        self.assertEqual(["low", "high", "xhigh"], [t["reasoning_effort"] for t in delegation.assign_task_efforts(tasks)])
        self.assertNotIn("reasoning_effort", tasks[0])
        with patch.object(cabinet, "load_config", return_value={"delegationEnabled": True}), \
             patch.object(hermes_plugin, "record_task_efforts") as record_efforts:
            directive = hermes_plugin.pre_tool_call("delegate_task", {"tasks": tasks})
            self.assertEqual(["low", "high", "xhigh"], [t["reasoning_effort"] for t in directive["args"]["tasks"]])
            single = handle_shell_hook({"hook_event_name": "pre_tool_call", "tool_name": "delegate_task", "tool_input": {"goal": "搜索资料"}})
            self.assertEqual("low", single["args"]["tasks"][0]["reasoning_effort"])
            self.assertEqual(2, record_efforts.call_count)
        with patch.object(cabinet, "load_config", return_value={"delegationEnabled": False}):
            self.assertIsNone(hermes_plugin.pre_tool_call("delegate_task", {"tasks": tasks}))

    def test_hermes_core_patch_and_shell_config_are_reversible(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            installed = Path.home() / ".hermes" / "hermes-agent" / "tools" / "delegate_tool.py"
            core = root / "delegate_tool.py"
            backup = installed.with_name(installed.name + ".jev.bak")
            if not backup.exists():
                self.skipTest("local Hermes source backup is unavailable")
            baseline = backup.read_bytes()
            core.write_bytes(baseline)
            self.assertTrue(install_core_patch(core))
            self.assertFalse(install_core_patch(core))
            self.assertTrue(undo_core_patch(core))
            self.assertEqual(baseline, core.read_bytes())
            config = root / "config.yaml"
            config.write_text("hooks: {}\nother: true\n", encoding="utf-8")
            self.assertTrue(install_shell_hooks(config)["changed"])
            self.assertFalse(install_shell_hooks(config)["changed"])
            self.assertTrue(uninstall_shell_hooks(config))
            self.assertEqual("hooks: {}\nother: true\n", config.read_text(encoding="utf-8"))

    def test_decisions_and_observed_events_are_separate(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(delegation, "LOG", Path(folder) / "events.json"):
            chosen = delegation.decide("请派两个子代理并行查资料", "hermes", True)
            self.assertEqual(("delegate", 2, "medium"), (chosen["recommendation"], chosen["agents"], chosen["effort"]))
            self.assertEqual("尚未创建子代理", chosen["model"])
            self.assertIn("明确要求并行或子代理", chosen["detail"])
            delegation.observed("hermes", "started", "child-1", "查资料")
            rows = delegation.entries()
            self.assertEqual(["observed", "decision"], [row["kind"] for row in rows])
            self.assertEqual("started", rows[0]["state"])
            self.assertEqual("未上报模型", rows[0]["model"])
            self.assertEqual("未上报强度", rows[0]["effort"])
            shown = delegation.present({"kind": "decision", "source": "web", "task": "写成一份周报",
                                        "recommendation": "solo", "effort": "host-configured"})
            self.assertEqual("网页试选，无模型", shown["model"])
            self.assertEqual("medium", shown["effort"])
            self.assertIn("保持单代理", shown["detail"])
            live = delegation.observed("hermes", "started", "child-2", "查资料", "DeepSeek-V4", "high", "provider=deepseek")
            shown_live = delegation.present(live)
            self.assertEqual("DeepSeek-V4", shown_live["model"])
            self.assertEqual("high", shown_live["effort"])
            self.assertIn("provider=deepseek", shown_live["detail"])

    def test_test_source_does_not_pollute_call_log(self):
        with patch.object(cabinet, "record_call") as record, patch.object(cabinet, "load_config", return_value={"selectorEnabled": False, "delegationEnabled": False}):
            cabinet.route_task("做一个视频", "test")
            record.assert_not_called()
        with patch.object(cabinet, "load_memory", return_value={"calls": [
            {"source": "test", "id": "1"}, {"source": "web", "id": "2"}], "rules": []}):
            self.assertEqual(["2"], [row["id"] for row in cabinet.calls_view()["calls"]])

    def test_authenticated_host_event_reaches_log(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            token = root / "token"
            token.write_text("local-secret", encoding="utf-8")
            with patch.object(delegation, "LOG", root / "events.json"), patch.object(preface_worker, "TOKEN_FILE", token):
                server = ThreadingHTTPServer(("127.0.0.1", 0), preface_worker.Handler)
                thread = threading.Thread(target=server.serve_forever, daemon=True)
                thread.start()
                try:
                    body = json.dumps({"source": "hermes", "state": "started", "child_id": "child-42"}).encode()
                    request = urllib.request.Request(
                        f"http://127.0.0.1:{server.server_address[1]}/dispatch-event",
                        data=body,
                        headers={"X-Kit-Token": "local-secret", "Content-Type": "application/json"},
                        method="POST",
                    )
                    with urllib.request.urlopen(request, timeout=3) as response:
                        self.assertEqual(200, response.status)
                    self.assertEqual("child-42", delegation.entries()[0]["childId"])
                finally:
                    server.shutdown()
                    server.server_close()
                    thread.join(timeout=3)

    def test_hermes_stop_without_child_id_is_still_visible(self):
        with patch.object(hermes_plugin, "report_dispatch_event") as report:
            hermes_plugin.subagent_stop(parent_session_id="parent-1", child_status="completed")
            self.assertEqual("unknown:parent-1", report.call_args.kwargs["child_id"])
            self.assertEqual("completed", report.call_args.kwargs["state"])

    def test_hermes_start_and_stop_use_same_child_session_id(self):
        with patch.object(hermes_plugin, "report_dispatch_event") as report:
            hermes_plugin.subagent_start(child_subagent_id="agent-1", child_session_id="session-1", child_goal="查资料")
            hermes_plugin.subagent_stop(child_subagent_id="agent-1", child_session_id="session-1", child_status="completed")
            self.assertEqual(["session-1", "session-1"], [call.kwargs["child_id"] for call in report.call_args_list])

    def test_hermes_install_shim_tracks_project_plugin(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "jev-skill-kit"
            result = install_plugin(target)
            self.assertTrue(result["changed"])
            shim = (target / "__init__.py").read_text(encoding="utf-8")
            self.assertIn("from host.hermes_plugin import register", shim)
            self.assertIn("subagent_start", (target / "plugin.yaml").read_text(encoding="utf-8"))
            self.assertFalse(install_plugin(target)["changed"])

    def test_delegation_toggle_does_not_reconfigure_hosts(self):
        with patch.object(cabinet, "load_config", return_value={"selectorEnabled": True, "delegationEnabled": False}), \
             patch.object(cabinet, "_write_config"), patch("hosts.sync_hosts") as sync:
            result = cabinet.save_config({"delegationEnabled": True})
            self.assertTrue(result["config"]["delegationEnabled"])
            sync.assert_not_called()


if __name__ == "__main__":
    unittest.main()
