import { apply } from "../host/harness_plugin/index.js";

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

console.log("ok");
