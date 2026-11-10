// The grammar of a want's `why` and `how` (R-3.17, R-6.17; documentation set, module 6.4). The
// first test checks the rule on texts. The others perform commands through the command line, as
// an agent's harness does, on a new home in a temporary folder.

import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { mkdirSync, mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { test } from "node:test";

import { breaksGrammar } from "../src/rules.ts";

const MAIN = new URL("../src/main.ts", import.meta.url).pathname;
const GAME = "code.engine.game";
const ROUTER = "code.engine.router";
const MESSAGE =
  "why is one fragment that starts with a base verb; how is one fragment that starts with a verb ending in -s. No leading 'to', no subject, no '-ing' verb, no values. Detail belongs in a knowledge layer.";
const WHY_PLACEHOLDER = "<base verb phrase, as: drain raw frames from the network interface card>";
const HOW_PLACEHOLDER = "<verb phrase ending in -s, as: holds descriptor pointers across contiguous memory segments>";

const PASSES: Record<string, string[]> = {
  why: [
    "Receive player input and collision telemetry for frame simulation.",
    "drain raw frames from the network interface card",
    "String the tokens into one line",
    "ping the peer",
    "Verify the S256 challenge of OAuth2 over HTTP/2 as utf-8 on x86-64",
  ],
  how: [
    "Dispatches subscribed runtime event streams.",
    "holds descriptor pointers across contiguous memory segments",
    "  Stores: frames on disk  ",
    "Verifies S256 challenges for OAuth2 clients.",
    "passes checking results on",
  ],
};
const BREAKS: Record<string, string[]> = {
  why: [
    "to drain raw frames",
    "To: drain raw frames",
    "draining raw frames",
    "Parsing, then storing",
    "The router needs parameters",
    "it needs parameters",
    "keep frames. Store them on disk",
    "keep frames; store them on disk",
    "keep frames!\nstore them",
    "score answers from 0 to 5",
    "wait 3.9 seconds",
    "retry 5",
    "list items 1-5",
  ],
  how: [
    "holding descriptor pointers",
    "hold descriptor pointers",
    "The router stores parameters.",
    "this stores parameters",
    "its parameters are stored",
    "Stores parameters. Decodes them first.",
    "Returns yes/no confidences and 0 to 5 scores from the JEV model.",
    "...",
  ],
};

/** A new home with the game element and the procedure's own example of a want. */
function seeded(): { call: (command: unknown) => any; remove: () => void } {
  const work = mkdtempSync(join(tmpdir(), "metaform-node-test-"));
  const home = join(work, "home");
  const project = join(work, "project");
  mkdirSync(home);
  mkdirSync(project);
  const call = (command: unknown): any => {
    const done = spawnSync(
      process.execPath,
      [MAIN, "call", "--home", home, "--project", project, JSON.stringify(command)],
      { encoding: "utf8" },
    );
    return JSON.parse(done.stdout);
  };
  assert.deepEqual(
    call({ add: { [GAME]: { technical_name: "game engine", name: "Quake core", role: "Definitive" } } }),
    { status: "ok" },
  );
  const example = {
    why: "Receive player input and collision telemetry for frame simulation.",
    how: "Dispatches subscribed runtime event streams.",
    direction: "inbound",
  };
  assert.deepEqual(call({ update: { [GAME]: { wants: { [ROUTER]: example } } } }), { status: "ok" });
  return { call, remove: () => rmSync(work, { recursive: true, force: true }) };
}

test("grammar: the rule on texts", () => {
  for (const [field, texts] of Object.entries(PASSES)) {
    for (const text of texts) {
      assert.equal(breaksGrammar(field, text), false, `${field}: ${text}`);
    }
  }
  for (const [field, texts] of Object.entries(BREAKS)) {
    for (const text of texts) {
      assert.equal(breaksGrammar(field, text), true, `${field}: ${text}`);
    }
  }
});

test("grammar: a refusal names the parts that broke the rule, and stores nothing", () => {
  const at = seeded();
  try {
    const command = { update: { [GAME]: { wants: { [ROUTER]: { how: "The router stores parameters." } } } } };
    const answer = at.call(command);
    assert.deepEqual(Object.keys(answer), ["update", "status", "code", "message", "tested_sentence", "remediation"]);
    assert.deepEqual(answer, {
      ...command,
      status: "error",
      code: "GRAMMAR_CONSTRAINT_VIOLATION",
      message: MESSAGE,
      tested_sentence:
        "code.engine.game (Quake core) requires code.engine.router in order to Receive player input and collision telemetry for frame simulation, which The router stores parameters.",
      remediation: { update: { [GAME]: { wants: { [ROUTER]: { how: HOW_PLACEHOLDER } } } } },
    });
    // Both parts break the rule. The first want that breaks it is reported, and the valid want
    // before it in the same command is not stored. The want is new, so the remediation has the
    // whole want: a want needs all of its fields.
    const several = at.call({
      update: {
        [GAME]: {
          wants: {
            "code.engine.store": { why: "keep frames", how: "holds frames on disk", direction: "inbound" },
            "code.engine.zeta": { how: "holding frames", why: "to keep frames", direction: "inbound" },
            "code.engine.alpha": { why: "keep 5 frames", how: "holds frames", direction: "inbound" },
          },
        },
      },
    });
    const parts = several.remediation.update[GAME].wants["code.engine.zeta"];
    assert.deepEqual(Object.entries(parts), [["why", WHY_PLACEHOLDER], ["how", HOW_PLACEHOLDER], ["direction", "inbound"]]);
    assert.equal(
      several.tested_sentence,
      "code.engine.game (Quake core) requires code.engine.zeta in order to to keep frames, which holding frames.",
    );
    assert.equal(at.call({ [GAME]: { wants: {} } })[GAME].wants[ROUTER].how, "Dispatches subscribed runtime event streams.");
    assert.equal(at.call({ "code.engine.store": {} }).code, "NOT_FOUND");
  } finally {
    at.remove();
  }
});

test("grammar: a part the command does not write is not checked", () => {
  const at = seeded();
  try {
    const ok = { status: "ok" };
    assert.deepEqual(at.call({ update: { [GAME]: { wants: { [ROUTER]: { how: "Stores decoded parameters." } } } } }), ok);
    assert.deepEqual(at.call({ update: { [GAME]: { wants: { [ROUTER]: { direction: "outbound" } } } } }), ok);
    assert.deepEqual(at.call({ update: { [GAME]: { status: "built" } } }), ok);
  } finally {
    at.remove();
  }
});
