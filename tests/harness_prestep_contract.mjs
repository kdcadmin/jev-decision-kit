import { mkdtemp, readFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";

import { apply, alreadyPrefaced, foldPreface, note, resolveKitRoot, subagentDispatch } from "../host/harness_plugin/index.js";

function fail(message, value) {
  console.error(message, value);
  process.exit(1);
}

const hooks = {};
apply({
  on(name, fn, options) {
    hooks[name] = { hook: fn, options };
  },
});

for (const name of ["agent/pre-step", "subagent/start", "subagent/end"]) {
  if (typeof hooks[name]?.hook !== "function") fail("missing " + name, hooks[name]);
}
// Subagent lifecycle dispatch is scope-filtered by the delegating parent, so a
// bare listener never sees it.
for (const name of ["subagent/start", "subagent/end"]) {
  if (hooks[name].options?.global !== true) fail(name + " must be registered with { global: true }", hooks[name].options);
}

// The host loads its own copy of this plugin, so the kit root is looked up:
// env override, then a pointer file, then two levels up.
const installedDir = join(tmpdir(), "jev-installed-copy");
if (resolveKitRoot({ JEV_KIT_ROOT: "C:/explicit" }, installedDir, () => "") !== "C:/explicit") {
  fail("JEV_KIT_ROOT must win over every pointer");
}
if (resolveKitRoot({}, installedDir, (path) => (path.endsWith("kit-root.txt") ? "C:/from-pointer" : "")) !== "C:/from-pointer") {
  fail("a pointer file must beat the default root");
}
if (resolveKitRoot({}, installedDir, () => "") !== join(installedDir, "..", "..")) {
  fail("without any pointer the root stays two levels up");
}
// A profile that installed this plugin as a `file:` dependency keeps the source
// path in its manifest, which survives a reinstall that drops pointer files.
const profileModuleDir = join(tmpdir(), "jev-profile", "node_modules", "dsh-jev-skill-kit");
const manifest = JSON.stringify({
  dependencies: { "dsh-jev-skill-kit": "file:D:/somewhere/jev-decision-kit/host/harness_plugin" },
});
const fromManifest = resolveKitRoot({}, profileModuleDir, (path) => (path.endsWith("package.json") ? manifest : ""));
if (fromManifest !== join("D:/somewhere/jev-decision-kit/host/harness_plugin", "..", "..")) {
  fail("a file: dependency must locate the kit", fromManifest);
}
// A linked install keeps the same path in the manifest.
const linkManifest = JSON.stringify({
  dependencies: { "dsh-jev-skill-kit": "link:D:/somewhere/jev-decision-kit/host/harness_plugin" },
});
const fromLink = resolveKitRoot({}, profileModuleDir, (path) => (path.endsWith("package.json") ? linkManifest : ""));
if (fromLink !== join("D:/somewhere/jev-decision-kit/host/harness_plugin", "..", "..")) {
  fail("a link: dependency must locate the kit", fromLink);
}

const started = subagentDispatch({
  id: "run-9",
  model: "DeepSeek-V4-Flash",
  reasoningEffort: "high",
  task: "并行查资料",
  provider: "deepseek",
}, "start");
if (started.child_id !== "run-9" || started.model !== "DeepSeek-V4-Flash" || started.effort !== "high") {
  fail("subagent start must keep model and effort", started);
}
const ended = subagentDispatch({ id: "run-9", stopReason: "completed" }, "end");
if (ended.state !== "completed" || ended.child_id !== "run-9") fail("subagent end must keep id", ended);

const hook = hooks["agent/pre-step"].hook;

const original = [{ role: "user", content: [{ type: "text", text: "写成一份 Word" }] }];

const rejected = await hook({ messages: original }, async () => ({ kind: "reject" }));
if (rejected?.kind !== "reject" || Array.isArray(rejected)) {
  fail("reject not forwarded", rejected);
}

const skipped = await hook(
  { messages: [{ role: "user", content: [{ type: "text", text: "jev-decision: 已选定：docx。读完照做。" }] }] },
  async () => ({ kind: "enter", messages: original, startsRequestSeries: true }),
);
if (skipped?.kind !== "enter" || skipped.startsRequestSeries !== true || skipped.messages !== original) {
  fail("enter without inject must spread decision", skipped);
}

const folded = foldPreface(
  { kind: "enter", messages: original, startsRequestSeries: true },
  original,
  "jev-decision: 这次自己做，不要翻技能柜。",
);
if (folded.startsRequestSeries !== true || folded.messages === original) {
  fail("fold must copy messages and keep flags", folded);
}
if (folded.messages[0].source !== original[0].source || folded.messages[0].role !== "user") {
  fail("fold must keep producer source", folded.messages[0]);
}
if (folded.messages[0].content[0]?.text !== "jev-decision: 这次自己做，不要翻技能柜。\n\n") {
  fail("fold must prefix preface", folded.messages[0].content);
}
if (folded.messages[0].source?.kind === "plugin") {
  fail("must not mint a plugin source kind", folded.messages[0]);
}

// Only a leading marker means "this turn was already decided": a user who merely
// types jev-decision: somewhere must still get a selection.
if (!alreadyPrefaced("jev-decision: 已选定：docx。")) fail("a leading marker must count as folded");
if (!alreadyPrefaced("  \njev-decision: 已选定：docx。")) fail("leading whitespace must not hide the marker");
if (!alreadyPrefaced("【技能柜】已选定：docx。")) fail("the legacy marker must still count as folded");
if (alreadyPrefaced("你说 jev-decision: 这样写就行")) fail("a mid-text mention must not count as folded");
if (alreadyPrefaced("你说【技能柜】这样写就行")) fail("a mid-text legacy mention must not count as folded");
if (alreadyPrefaced("帮我写一份 Word")) fail("a plain task must not count as folded");
if (alreadyPrefaced("")) fail("nothing must not count as folded");

// A skipped or failed report must leave one JSON line behind, not disappear.
const folder = await mkdtemp(join(tmpdir(), "jev-plugin-log-"));
try {
  const logPath = join(folder, "harness-plugin.log");
  await note("report-skipped", "reason=no-worker", logPath);
  await note("report-failed", "connect ECONNREFUSED", logPath);
  const lines = (await readFile(logPath, "utf8")).trim().split("\n");
  const first = JSON.parse(lines[0]);
  const last = JSON.parse(lines[lines.length - 1]);
  if (lines.length !== 2 || first.kind !== "report-skipped" || last.kind !== "report-failed") {
    fail("note must append one JSON line per call", lines);
  }
  if (typeof first.at !== "string" || first.detail !== "reason=no-worker") {
    fail("note must record time and detail", first);
  }
} finally {
  await rm(folder, { recursive: true, force: true });
}

// The host process may be unable to write that log at all, so a failed worker
// bootstrap must also name its cause inside the injected preface itself.
const barren = await mkdtemp(join(tmpdir(), "jev-barren-root-"));
process.env.JEV_KIT_ROOT = barren;
process.env.JEV_WORKER_WAIT_MS = "300";
try {
  const probe = await import("../host/harness_plugin/index.js?diagnostics");
  const probeHooks = {};
  probe.apply({
    on(name, fn) {
      probeHooks[name] = fn;
    },
  });
  const messages = [{ role: "user", content: [{ type: "text", text: "请派两个子代理并行查资料" }] }];
  const decision = await probeHooks["agent/pre-step"](
    { messages },
    async () => ({ kind: "enter", messages, startsRequestSeries: true }),
  );
  const injected = String(decision?.messages?.[0]?.content?.[0]?.text || "");
  if (!injected.startsWith("jev-decision: 这次没能启动选择（")) fail("fallback must name its cause", injected);
  // Every failing step must survive: later failures merge, they do not replace.
  if (!injected.includes("读不到端口文件")) fail("fallback must report the unreadable port file", injected);
  if (!injected.includes("spawn")) fail("fallback must report the failed spawn", injected);
  if (injected.includes("原因未知")) fail("fallback must not fall back to 原因未知", injected);
} finally {
  delete process.env.JEV_KIT_ROOT;
  delete process.env.JEV_WORKER_WAIT_MS;
  await rm(barren, { recursive: true, force: true });
}

console.log("ok");
