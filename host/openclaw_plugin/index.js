import { spawn } from "node:child_process";
import { readFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { definePluginEntry } from "openclaw/plugin-sdk/plugin-entry";

const root = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const python = join(root, ".venv", "Scripts", "python.exe");
const worker = join(root, "host", "preface_worker.py");
const portFile = join(root, "runtime", "preface.port");

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
  spawn(python, [worker], {
    cwd: root,
    windowsHide: true,
    stdio: "ignore",
    detached: true,
  }).unref();
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
  if (!port) return "【技能柜】这次没能启动选择。自己做，不要翻技能柜。";
  try {
    const response = await fetch(`http://127.0.0.1:${port}/preface`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ task, source: "openclaw" }),
      signal: AbortSignal.timeout(170000),
    });
    const body = await response.json();
    return String(body.preface || "");
  } catch {
    return "【技能柜】这次没能完成选择。自己做，不要翻技能柜。";
  }
}

export default definePluginEntry({
  id: "jev-skill-kit",
  name: "技能柜",
  description: "JEV 在模型开口前选定自己做，或选定哪几份技能和插件。",
  register(api) {
    api.on("before_prompt_build", async (event) => {
      const task = String(event.prompt || "").trim();
      if (!task || task.includes("【技能柜】")) return;
      const preface = await prefaceFor(task);
      if (!preface) return;
      return { prependContext: preface };
    });
  },
});
