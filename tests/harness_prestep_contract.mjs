import { apply, foldPreface } from "../host/harness_plugin/index.js";

const hooks = {};
apply({
  on(name, fn) {
    hooks[name] = fn;
  },
});

const hook = hooks["agent/pre-step"];
if (typeof hook !== "function") {
  console.error("missing agent/pre-step");
  process.exit(1);
}

const original = [{ role: "user", content: [{ type: "text", text: "写成一份 Word" }] }];

const rejected = await hook({ messages: original }, async () => ({ kind: "reject" }));
if (rejected?.kind !== "reject" || Array.isArray(rejected)) {
  console.error("reject not forwarded", rejected);
  process.exit(1);
}

const skipped = await hook(
  { messages: [{ role: "user", content: [{ type: "text", text: "【技能柜】已选定" }] }] },
  async () => ({ kind: "enter", messages: original, startsRequestSeries: true }),
);
if (skipped?.kind !== "enter" || skipped.startsRequestSeries !== true || skipped.messages !== original) {
  console.error("enter without inject must spread decision", skipped);
  process.exit(1);
}

const folded = foldPreface(
  { kind: "enter", messages: original, startsRequestSeries: true },
  original,
  "【技能柜】自己做，不要翻技能柜。",
);
if (folded.startsRequestSeries !== true || folded.messages === original) {
  console.error("fold must copy messages and keep flags", folded);
  process.exit(1);
}
if (folded.messages[0].source !== original[0].source || folded.messages[0].role !== "user") {
  console.error("fold must keep producer source", folded.messages[0]);
  process.exit(1);
}
if (folded.messages[0].content[0]?.text !== "【技能柜】自己做，不要翻技能柜。\n\n") {
  console.error("fold must prefix preface", folded.messages[0].content);
  process.exit(1);
}
if (folded.messages[0].source?.kind === "plugin") {
  console.error("must not mint a plugin source kind", folded.messages[0]);
  process.exit(1);
}

console.log("ok");
