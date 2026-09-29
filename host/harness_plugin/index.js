import { spawn } from "node:child_process";
import { readFileSync } from "node:fs";
import { appendFile, readFile, stat, writeFile } from "node:fs/promises";
import { homedir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const moduleDir = dirname(fileURLToPath(import.meta.url));
const PACKAGE_NAME = "dsh-jev-skill-kit";
const MARKER = "jev-decision:";
const LEGACY_MARKER = "【技能柜】";

/**
 * Only a leading marker means this turn was already decided: a user who merely
 * types the marker mid-sentence must still get a selection.
 */
export function alreadyPrefaced(task) {
  const body = String(task ?? "").trimStart();
  return body.startsWith(MARKER) || body.startsWith(LEGACY_MARKER);
}

function readPointer(path) {
  try {
    return readFileSync(path, "utf8").trim();
  } catch {
    return "";
  }
}

/**
 * A host that installs this plugin as a `file:` or `link:` dependency keeps the
 * source path in the profile manifest, so the kit can be found after a reinstall
 * that also drops pointer files.
 */
function rootFromProfileManifest(dir, read) {
  const text = read(join(dir, "..", "..", "package.json"));
  if (!text) return "";
  try {
    const manifest = JSON.parse(text);
    const spec = (manifest.dependencies || {})[PACKAGE_NAME] || (manifest.devDependencies || {})[PACKAGE_NAME];
    if (typeof spec === "string" && (spec.startsWith("file:") || spec.startsWith("link:"))) {
      return join(spec.slice(5), "..", "..");
    }
  } catch {
    /* A manifest that is not JSON tells us nothing. */
  }
  return "";
}

/**
 * The host may load an installed copy of this plugin from outside the kit (a
 * profile's node_modules, for example), so the kit root is looked up, never
 * assumed from the module's own location.
 */
export function resolveKitRoot(env = process.env, dir = moduleDir, read = readPointer) {
  if (env.JEV_KIT_ROOT) return env.JEV_KIT_ROOT;
  const shared = join(env.LOCALAPPDATA || env.USERPROFILE || homedir(), "jev-skill-kit", "root.txt");
  for (const pointer of [join(dir, "kit-root.txt"), shared]) {
    const found = read(pointer).trim();
    if (found) return found;
  }
  const installed = rootFromProfileManifest(dir, read);
  return installed || join(dir, "..", "..");
}

const root = resolveKitRoot();
const python = join(root, ".venv", "Scripts", "python.exe");
const worker = join(root, "host", "preface_worker.py");
const portFile = join(root, "runtime", "preface.port");
const tokenFile = join(root, "runtime", "preface.token");
const logFile = process.env.JEV_HARNESS_LOG || join(root, "runtime", "harness-plugin.log");
const LOG_LIMIT_BYTES = 262_144;
const workerWaitMs = Math.max(50, Number(process.env.JEV_WORKER_WAIT_MS) || 8000);

// Filled by every failed ensureWorker() so a fallback preface can name its own
// cause: the host process may be unable to write the log at all.
let lastFailure = "";

export const name = "jev-skill-kit";

function reason(value) {
  return String(value ?? "").replace(/\s+/g, " ").trim().slice(0, 160);
}

function remember(cause) {
  const text = reason(cause);
  if (!text) return;
  lastFailure = (lastFailure ? `${lastFailure}；${text}` : text).slice(0, 300);
}

// The injected preface is the one channel that needs no file and no socket, so
// give it every cause instead of the log's shorter per-line budget.
function injectedReason() {
  return String(lastFailure ?? "").replace(/\s+/g, " ").trim().slice(0, 260) || "原因未知";
}

/**
 * Best-effort diagnostics. A failed observation must never interrupt the agent,
 * but it must also not vanish without a trace: every skipped or failed report
 * leaves one JSON line in `runtime/harness-plugin.log`.
 */
export async function note(kind, detail = "", logPath = logFile) {
  const line = JSON.stringify({
    at: new Date().toISOString(),
    kind,
    detail: String(detail ?? "").slice(0, 500),
  }) + "\n";
  try {
    let size = 0;
    try {
      size = (await stat(logPath)).size;
    } catch {
      size = 0;
    }
    // One bounded file beats an unbounded log on every pre-step.
    if (size > LOG_LIMIT_BYTES) await writeFile(logPath, line, "utf8");
    else await appendFile(logPath, line, "utf8");
  } catch {
    /* Diagnostics must never interrupt the agent. */
  }
}

function noteAsync(kind, detail) {
  void note(kind, detail);
}

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
  let child;
  try {
    child = spawn(python, [worker], {
      cwd: root,
      windowsHide: true,
      stdio: "ignore",
      detached: true,
    });
  } catch (error) {
    remember(`spawn 抛错 ${reason(error?.message || error)}`);
    noteAsync("worker-spawn-threw", lastFailure);
    return;
  }
  child.on("error", (error) => {
    remember(`spawn 报错 ${reason(error?.message || error)}`);
    noteAsync("worker-spawn-error", lastFailure);
  });
  child.on("exit", (code, signal) => {
    remember(`spawn 的进程退出 pid=${child.pid} code=${code} signal=${signal}`);
    noteAsync("worker-exit", lastFailure);
  });
  noteAsync("worker-spawn", `pid=${child.pid} python=${python}`);
  child.unref();
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

async function ensureWorker() {
  lastFailure = "";
  const existing = await readPort();
  if (existing) {
    if (await healthy(existing)) return existing;
    remember(`端口 ${existing} 上的 worker 探活失败`);
    noteAsync("worker-unhealthy", `port=${existing}`);
  } else {
    remember(`读不到端口文件 ${portFile}`);
    noteAsync("worker-port-unreadable", `file=${portFile}`);
  }
  startWorker();
  const deadline = Date.now() + workerWaitMs;
  while (Date.now() < deadline) {
    const port = await readPort();
    if (port && (await healthy(port))) return port;
    await new Promise((resolve) => setTimeout(resolve, 200));
  }
  remember(`${workerWaitMs}ms 内没有可用的 worker`);
  noteAsync("worker-not-ready", `waitedMs=${workerWaitMs} file=${portFile}`);
  return null;
}

async function prefaceFor(task) {
  const port = await ensureWorker();
  if (!port) return `jev-decision: 这次没能启动选择（${injectedReason()}）。自己做，不要翻技能柜。`;
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
  } catch (error) {
    const detail = reason(error?.message || error);
    noteAsync("preface-failed", detail);
    return `jev-decision: 这次没能完成选择（${detail || "原因未知"}）。自己做，不要翻技能柜。`;
  }
}

async function reportDispatch(event) {
  const child = String(event?.child_id || "");
  const port = await ensureWorker();
  if (!port) {
    noteAsync("report-skipped", `reason=no-worker state=${event?.state || ""} child=${child}`);
    return;
  }
  if (!child) {
    noteAsync("report-skipped", `reason=no-child-id state=${event?.state || ""}`);
    return;
  }
  try {
    const token = await readFile(tokenFile, "utf8").then((text) => text.trim()).catch(() => "");
    const response = await fetch(`http://127.0.0.1:${port}/dispatch-event`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Kit-Token": token },
      body: JSON.stringify({ source: "harness", ...event }),
      signal: AbortSignal.timeout(3000),
    });
    if (!response.ok) noteAsync("report-rejected", `status=${response.status} child=${child}`);
  } catch (error) {
    noteAsync("report-failed", `${String(error?.message || error)} child=${child}`);
  }
}

function prependPreface(message, preface) {
  const prefix = { type: "text", text: `${preface}\n\n` };
  const content = Array.isArray(message?.content)
    ? [prefix, ...message.content]
    : typeof message?.content === "string"
      ? [prefix, { type: "text", text: message.content }]
      : [prefix];
  return { ...message, content };
}

export function foldPreface(decision, payloadMessages, preface) {
  if (decision?.kind !== "enter" || !preface) return decision;
  const messages = decision.messages;
  if (!Array.isArray(messages) || messages.length === 0) return decision;
  const originals = Array.isArray(payloadMessages) ? payloadMessages : [];
  let index = messages.findLastIndex((message) => originals.includes(message));
  if (index < 0) index = 0;
  const next = messages.slice();
  next[index] = prependPreface(next[index], preface);
  return { ...decision, messages: next };
}

export function firstFilled(...values) {
  for (const value of values) {
    if (value == null || typeof value === "object") continue;
    const text = String(value).trim();
    if (text) return text;
  }
  return "";
}

export function subagentDispatch(info, phase) {
  const id = firstFilled(info?.id, info?.runId, info?.agent?.id);
  const model = firstFilled(
    info?.model, info?.resolvedModel, info?.modelId,
    info?.agent?.model, info?.header?.model, info?.llm,
  );
  const effort = firstFilled(
    info?.reasoningEffort, info?.reasoning_effort, info?.effort, info?.thinking,
    info?.agent?.reasoningEffort, info?.agent?.reasoning_effort,
  );
  if (phase === "end") {
    const stop = firstFilled(info?.stopReason, info?.diagnostic, info?.error, info?.detail);
    const state = stop === "completed" ? "completed" : (stop === "aborted" ? "aborted" : "error");
    return { state, child_id: id, model, effort, detail: stop };
  }
  return {
    state: "started",
    child_id: id,
    task: firstFilled(info?.task, info?.goal, info?.prompt, info?.agent?.task),
    model,
    effort,
    detail: firstFilled(info?.provider, info?.detail, info?.agent?.provider),
  };
}

export function apply(ctx) {
  // Subagent lifecycle events are scope-filtered: dispatch keys the carrier by
  // the delegating parent, so a plugin listener only sees them with
  // `{ global: true }` (same as the harness' own subagent listeners).
  ctx.on("subagent/start", (info) => reportDispatch(subagentDispatch(info, "start")), { global: true });
  ctx.on("subagent/end", (info) => reportDispatch(subagentDispatch(info, "end")), { global: true });
  ctx.on("agent/pre-step", async (payload, next) => {
    const decision = await next();
    if (decision?.kind !== "enter") return decision;
    const task = messageText(payload?.messages);
    if (!task || alreadyPrefaced(task)) return decision;
    const preface = await prefaceFor(task);
    if (!preface) return decision;
    return foldPreface(decision, payload?.messages, preface);
  });
}
