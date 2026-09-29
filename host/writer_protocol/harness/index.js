import { spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const kit = join(dirname(fileURLToPath(import.meta.url)), "..", "..", "..");
const pythonWin = join(kit, ".venv", "Scripts", "python.exe");
const pythonPosix = join(kit, ".venv", "bin", "python");
const python = existsSync(pythonWin) ? pythonWin : (existsSync(pythonPosix) ? pythonPosix : "python");
const MARK = "jev-writer:";

function alreadyHinted(task) {
  return String(task ?? "").trimStart().startsWith(MARK);
}

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

function messageText(value) {
  if (typeof value === "string") return value.trim();
  if (Array.isArray(value)) return value.map(messageText).filter(Boolean).join("\n").trim();
  if (!value || typeof value !== "object") return "";
  if (typeof value.text === "string") return value.text.trim();
  if (typeof value.content === "string") return value.content.trim();
  if (Array.isArray(value.content)) return messageText(value.content);
  if (Array.isArray(value.messages)) return messageText(value.messages);
  return "";
}

function prepend(message, text) {
  const prefix = { type: "text", text: `${text}\n\n` };
  const content = Array.isArray(message?.content) ? [prefix, ...message.content] : [prefix];
  return { ...message, content };
}

export function apply(ctx) {
  ctx.on("agent/pre-step", async (payload, next) => {
    const decision = await next();
    if (decision?.kind !== "enter") return decision;
    const task = messageText(payload?.messages);
    if (!task || alreadyHinted(task)) return decision;
    const cwd = String(payload?.agent?.session?.header?.cwd || process.cwd());
    const text = hint(cwd);
    if (!text) return decision;
    const messages = decision.messages;
    if (!Array.isArray(messages) || messages.length === 0) return decision;
    const nextMessages = messages.slice();
    nextMessages[0] = prepend(nextMessages[0], text);
    return { ...decision, messages: nextMessages };
  });
}
