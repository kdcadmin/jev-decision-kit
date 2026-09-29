import { spawn, spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import { readFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const pythonWin = join(root, ".venv", "Scripts", "python.exe");
const pythonPosix = join(root, ".venv", "bin", "python");
const python = existsSync(pythonWin) ? pythonWin : (existsSync(pythonPosix) ? pythonPosix : "python");
const worker = join(root, "host", "preface_worker.py");
const portFile = join(root, "runtime", "preface.port");
const tokenFile = join(root, "runtime", "preface.token");

async function readPort() {
  try {
    const text = await readFile(portFile, "utf8");
    const port = Number(text.trim());
    return Number.isInteger(port) && port > 0 ? port : null;
  } catch {
    return null;
  }
}

async function healthy(port) {
  try {
    const response = await fetch(`http://127.0.0.1:${port}/health`, { signal: AbortSignal.timeout(400) });
    return response.ok;
  } catch {
    return false;
  }
}

function startWorker() {
  const child = spawn(python, [worker], {
    cwd: root,
    windowsHide: true,
    stdio: "ignore",
    detached: true,
  });
  child.on("error", () => {});
  child.unref();
}

async function ensureWorker() {
  const existing = await readPort();
  if (existing && (await healthy(existing))) return existing;
  startWorker();
  const deadline = Date.now() + 8000;
  while (Date.now() < deadline) {
    const port = await readPort();
    if (port && (await healthy(port))) return port;
    await new Promise((resolve) => setTimeout(resolve, 200));
  }
  return null;
}

async function prefaceFor(task) {
  const port = await ensureWorker();
  if (!port) return "jev-decision: 这次没能启动选择。自己做，不要翻技能柜。";
  try {
    const response = await fetch(`http://127.0.0.1:${port}/preface`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Kit-Token": await readFile(tokenFile, "utf8").then((text) => text.trim()).catch(() => "") },
      body: JSON.stringify({ task, source: "openclaw" }),
      signal: AbortSignal.timeout(170000),
    });
    const body = await response.json();
    return String(body.preface || "");
  } catch {
    return "jev-decision: 这次没能完成选择。自己做，不要翻技能柜。";
  }
}

async function reportDispatch(event) {
  const port = await ensureWorker();
  if (!port || !event.child_id) return;
  try {
    await fetch(`http://127.0.0.1:${port}/dispatch-event`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Kit-Token": await readFile(tokenFile, "utf8").then((text) => text.trim()).catch(() => "") },
      body: JSON.stringify({ source: "openclaw", ...event }),
      signal: AbortSignal.timeout(3000),
    });
  } catch { /* Logging must not block the host. */ }
}

// Export the runtime entry directly: this checkout lives outside OpenClaw's
// node_modules tree, so a bare `openclaw/plugin-sdk/*` import cannot resolve.
export default {
  id: "jev-skill-kit",
  name: "技能柜",
  description: "jev-decision 在模型开口前选定自己做，或选定哪几份技能和插件。",
  register(api) {
    api.on("subagent_spawned", (event) => reportDispatch({
      state: "started", child_id: String(event.childSessionKey || event.runId || ""),
      task: String(event.task || ""), model: String(event.resolvedModel || ""),
    }));
    api.on("subagent_ended", (event) => reportDispatch({
      state: event.outcome === "ok" ? "completed" : (event.outcome === "killed" ? "aborted" : "error"),
      child_id: String(event.targetSessionKey || event.runId || ""),
      detail: String(event.error || event.reason || event.outcome || ""),
    }));
    api.on("before_prompt_build", async (event) => {
      const task = String(event.prompt || "").trim();
      const folded = String(task ?? "").trimStart();
      const parts = [];
      if (!folded.startsWith("jev-writer:") && existsSync(join(root, "host", "writer_protocol", "__init__.py"))) {
        const hint = spawnSync(python, ["-m", "host.writer_protocol", "hint", "--root", String(event.cwd || process.cwd())], {
          cwd: root,
          encoding: "utf8",
          windowsHide: true,
          timeout: 8000,
        });
        const writer = String(hint.stdout || "").trim();
        if (writer.startsWith("jev-writer:")) parts.push(writer);
      }
      if (task && !folded.startsWith("jev-decision:") && !folded.startsWith("【技能柜】")) {
        const preface = await prefaceFor(task);
        if (preface) parts.push(preface);
      }
      if (!parts.length) return;
      return { prependContext: parts.join("\n\n") };
    });
  },
};
