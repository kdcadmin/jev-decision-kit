import { spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const kit = join(dirname(fileURLToPath(import.meta.url)), "..", "..", "..");
const pythonWin = join(kit, ".venv", "Scripts", "python.exe");
const pythonPosix = join(kit, ".venv", "bin", "python");
const python = existsSync(pythonWin) ? pythonWin : (existsSync(pythonPosix) ? pythonPosix : "python");
const MARK = "jev-writer:";

function hint(cwd) {
  const result = spawnSync(python, ["-m", "host.writer_protocol", "hint", "--root", cwd], {
    cwd: kit,
    encoding: "utf8",
    windowsHide: true,
    timeout: 8000,
  });
  const text = String(result.stdout || "").trim();
  return text.startsWith(MARK) ? text : "";
}

export default {
  id: "writer-protocol",
  name: "写者协议",
  description: "工作区写者协议：没有就创建，开口前只塞一句精简提示。",
  register(api) {
    api.on("before_prompt_build", async (event) => {
      const task = String(event.prompt || "").trimStart();
      if (!task || task.startsWith(MARK) || task.startsWith("jev-decision:")) return;
      const cwd = String(event.cwd || process.cwd());
      const text = hint(cwd);
      if (!text) return;
      return { prependContext: text };
    });
  },
};
