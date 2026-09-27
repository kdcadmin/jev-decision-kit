import { spawn } from "node:child_process";
import { readFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const python = join(root, ".venv", "Scripts", "python.exe");
const worker = join(root, "host", "preface_worker.py");
const portFile = join(root, "runtime", "preface.port");
const tokenFile = join(root, "runtime", "preface.token");

export const name = "jev-skill-kit";

async function readPort() {
  try {
    const port = Number((await readFile(portFile, "utf8")).trim());
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

function messageText(value) {
  if (typeof value === "string") return value.trim();
  if (Array.isArray(value)) {
    return value.map(messageText).filter(Boolean).join("\n").trim();
  }
  if (!value || typeof value !== "object") return "";
  if (typeof value.text === "string") return value.text.trim();
  if (typeof value.content === "string") return value.content.trim();
  if (Array.isArray(value.content)) return messageText(value.content);
  if (Array.isArray(value.messages)) return messageText(value.messages);
  return "";
}

async function prefaceFor(task) {
  const port = await ensureWorker();
  if (!port) return "【技能柜】这次没能启动选择。自己做，不要翻技能柜。";
  try {
    const token = await readFile(tokenFile, "utf8").then((text) => text.trim()).catch(() => "");
    const response = await fetch(`http://127.0.0.1:${port}/preface`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Kit-Token": token },
      body: JSON.stringify({ task, source: "harness" }),
      signal: AbortSignal.timeout(170000),
    });
    const body = await response.json();
    return String(body.preface || "");
  } catch {
    return "【技能柜】这次没能完成选择。自己做，不要翻技能柜。";
  }
}

function userMessage(text) {
  return {
    role: "user",
    content: [{ type: "text", text }],
    source: { kind: "plugin", plugin: "jev-skill-kit" },
  };
}

export function apply(ctx) {
  ctx.on("agent/pre-step", async (payload, next) => {
    const decision = await next();
    if (decision?.kind !== "enter") return decision;
    const task = messageText(payload?.messages);
    if (!task || task.includes("【技能柜】")) return decision;
    const preface = await prefaceFor(task);
    if (!preface) return decision;
    return { ...decision, messages: [...decision.messages, userMessage(preface)] };
  });
}
