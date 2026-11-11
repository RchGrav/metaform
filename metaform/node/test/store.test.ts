// The store's tests (design document `metaform/docs/designs/sqlite-forms.md`, section 5). Each
// test uses a new home and performs its commands through the command line or the stdio MCP
// server, as an agent does. The conformance check, not these tests, compares answers with the
// Rust form's.

import assert from "node:assert/strict";
import { spawn, spawnSync } from "node:child_process";
import type { ChildProcessWithoutNullStreams } from "node:child_process";
import { mkdirSync, mkdtempSync, readFileSync, readdirSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { createInterface } from "node:readline";
import { DatabaseSync } from "node:sqlite";
import { test } from "node:test";

const MAIN = new URL("../src/main.ts", import.meta.url).pathname;
const META = {
  "io.modelcontextprotocol/protocolVersion": "2026-07-28",
  "io.modelcontextprotocol/clientInfo": { name: "metaform-node-test", version: "1" },
  "io.modelcontextprotocol/clientCapabilities": {},
};

type Place = { home: string; project: string; remove: () => void };

/** A new home and a new project folder. The home does not exist yet unless `make` is true. */
function place(make = true): Place {
  const work = mkdtempSync(join(tmpdir(), "metaform-node-test-"));
  const home = join(work, "home");
  const project = join(work, "project");
  mkdirSync(project);
  if (make) {
    mkdirSync(home);
  }
  return { home, project, remove: () => rmSync(work, { recursive: true, force: true }) };
}

/** One tool command through `call`: the answer, the exit status and what was written to stderr. */
function call(at: Place, command: unknown): { answer: any; status: number | null; stderr: string } {
  const done = spawnSync(
    process.execPath,
    [MAIN, "call", "--home", at.home, "--project", at.project, JSON.stringify(command)],
    { encoding: "utf8" },
  );
  return { answer: done.stdout ? JSON.parse(done.stdout) : null, status: done.status, stderr: done.stderr };
}

/** One stdio MCP connection to a server process of its own. */
class Connection {
  process: ChildProcessWithoutNullStreams;
  private next = 0;
  private waiting = new Map<number, (answer: any) => void>();

  constructor(at: Place) {
    this.process = spawn(process.execPath, [MAIN, "mcp", "--home", at.home, "--project", at.project]);
    createInterface({ input: this.process.stdout }).on("line", (line) => {
      const reply = JSON.parse(line);
      this.waiting.get(reply.id)?.(JSON.parse(reply.result.content[0].text));
      this.waiting.delete(reply.id);
    });
  }

  /** Send one tool command. The promise resolves with the answer when the server acknowledges it. */
  send(command: unknown): Promise<any> {
    this.next += 1;
    const id = this.next;
    const params = { name: "project-map", arguments: command, _meta: META };
    this.process.stdin.write(`${JSON.stringify({ jsonrpc: "2.0", id, method: "tools/call", params })}\n`);
    return new Promise((resolve) => this.waiting.set(id, resolve));
  }

  /** Close stdin and wait for the server process to end. */
  close(): Promise<void> {
    return new Promise((resolve) => {
      this.process.on("close", () => resolve());
      this.process.stdin.end();
    });
  }
}

/** The one project database of a home, opened for reading. */
function projectDatabase(at: Place): DatabaseSync {
  const [id] = readdirSync(join(at.home, "projects"));
  return new DatabaseSync(join(at.home, "projects", id, "project.db"), { readOnly: true });
}

/** Every table of a database with its number of rows. */
function tables(db: DatabaseSync): Record<string, number> {
  const out: Record<string, number> = {};
  const names = db.prepare("SELECT name FROM sqlite_schema WHERE type = 'table' ORDER BY name").all();
  for (const { name } of names as { name: string }[]) {
    const quoted = `"${name.replaceAll('"', '""')}"`;
    out[name] = (db.prepare(`SELECT count(*) AS rows FROM ${quoted}`).get() as { rows: number }).rows;
  }
  return out;
}

/** A number as letters, because an underscore before a digit does not survive storage. */
function letters(n: number): string {
  return String(n).replace(/\d/g, (digit) => "abcdefghij"[Number(digit)]);
}

/** A complete element for `code.part_<letters>`: three intake fields, a note and a layer of two records. */
function part(n: number): Record<string, unknown> {
  return { technical_name: `part ${letters(n)}`, name: `Part ${n}`, role: "Supportive", note: `note ${n}`, sources: ["a", "b"] };
}

test("layout: each field and each layer has its own table, and no table holds a whole element", () => {
  const at = place();
  try {
    const writes = [
      { add: { "code.engine": { technical_name: "engine", name: "Game Engine", role: "Definitive", status: "un_built" } } },
      {
        add: {
          "code.engine.render_loop": {
            technical_name: "render loop",
            name: "Frame Pump",
            role: "Supportive",
            sources: ["src/loop.rs", "src/frame.rs"],
            memory: [],
            wants: { "code.engine": { why: "draw frames", how: "calls the engine", direction: "outbound" } },
          },
        },
      },
      { add: { "code.engine.render_loop": { sources: ["src/timer.rs"] } } },
      { update: { "code.engine": { specification: [{ level: 1, title: "Purpose", text: "The engine runs the game." }] } } },
    ];
    for (const write of writes) {
      assert.equal(call(at, write).answer.status, "ok");
    }
    const db = projectDatabase(at);
    const found = tables(db);
    // The specification layer's definition, which the store writes, has four more scalar fields.
    assert.deepEqual(Object.keys(found), [
      "element", "f_description", "f_format", "f_instruction", "f_name", "f_role", "f_status", "f_technicalName",
      "f_template", "field", "holds", "l_memory", "l_sources", "l_specification", "layer", "map", "wants",
    ]);
    // Elements: the root, code, code.engine, code.engine.render_loop, and the three of the definition.
    assert.equal(found.element, 7);
    assert.equal(found.f_technicalName, 3);
    assert.equal(found.f_status, 1);
    assert.equal(found.l_memory, 0, "a layer with no records has no rows");
    assert.equal(found.holds, 3, "holds names each layer an element has, the one with no records too");
    assert.equal(found.wants, 1);
    const loop = db.prepare("SELECT key FROM element WHERE address = ?").get("code.engine.renderLoop") as { key: number };
    assert.ok(loop, "an address is stored in camelCase");
    assert.deepEqual(
      db.prepare("SELECT ordinal, data FROM l_sources WHERE element = ? ORDER BY ordinal").all(loop.key).map((row) => ({ ...row })),
      [
        { ordinal: 0, data: '"src/loop.rs"' },
        { ordinal: 1, data: '"src/frame.rs"' },
        { ordinal: 2, data: '"src/timer.rs"' },
      ],
    );
    assert.deepEqual({ ...db.prepare('SELECT value FROM "f_name" WHERE element = ?').get(loop.key) }, { value: '"Frame Pump"' });
    // No table has a column for a second field, and no row holds two fields of one element.
    for (const name of Object.keys(found)) {
      const columns = (db.prepare(`PRAGMA table_info("${name}")`).all() as { name: string }[]).map((c) => c.name);
      if (name.startsWith("f_")) {
        assert.deepEqual(columns, ["element", "value"]);
      } else if (name.startsWith("l_")) {
        assert.deepEqual(columns, ["element", "ordinal", "data"]);
      } else if (name === "element") {
        assert.deepEqual(columns, ["key", "map", "address", "parent"]);
      }
      for (const row of db.prepare(`SELECT * FROM "${name}"`).all()) {
        const text = JSON.stringify(row);
        assert.ok(!(text.includes("Frame Pump") && text.includes("render loop")), `${name} holds two fields in one row`);
      }
    }
    db.close();
  } finally {
    at.remove();
  }
});

test("two processes: every acknowledged write of several processes on one map is present", async () => {
  const at = place(false);
  try {
    // The processes start at the same time on a home that does not exist yet.
    const connections = [0, 1, 2, 3].map(() => new Connection(at));
    const acknowledged: string[] = [];
    await Promise.all(
      connections.map(async (connection, process) => {
        for (let n = 0; n < 25; n += 1) {
          const address = `code.part_${letters(process)}.item_${letters(n)}`;
          const answer = await connection.send({ add: { [address]: { name: `Part ${process} ${n}`, sources: [address] } } });
          assert.equal(answer.status, "ok", JSON.stringify(answer));
          acknowledged.push(address);
        }
      }),
    );
    await Promise.all(connections.map((connection) => connection.close()));
    assert.equal(acknowledged.length, 100);
    const { addresses } = call(at, { map: {} }).answer;
    for (const address of acknowledged) {
      assert.ok(addresses.includes(address), `${address} was acknowledged and is not in the map`);
    }
  } finally {
    at.remove();
  }
});

test("ended process: after SIGKILL every acknowledged write is present and no element is half written", async () => {
  const at = place();
  try {
    const connection = new Connection(at);
    const acknowledged: number[] = [];
    // The writes are sent without a wait for each answer, so the process is ended while it writes.
    for (let n = 0; n < 400; n += 1) {
      connection.send({ add: { [`code.part_${letters(n)}`]: part(n) } }).then((answer) => {
        assert.equal(answer.status, "ok");
        acknowledged.push(n);
      });
    }
    await new Promise<void>((resolve) => {
      const look = setInterval(() => {
        if (acknowledged.length >= 40) {
          clearInterval(look);
          resolve();
        }
      }, 1);
    });
    const ended = new Promise((resolve) => connection.process.on("close", resolve));
    connection.process.kill("SIGKILL");
    await ended;
    const known = [...acknowledged];
    assert.ok(known.length < 400, "the process ended before its last write");
    const dump = call(at, { ".code": {} });
    assert.equal(dump.status, 0, dump.stderr);
    const stored = dump.answer[".code"];
    const name = (n: number): string => `part_${letters(n)}`;
    for (const n of known) {
      assert.ok(stored[name(n)], `write ${n} was acknowledged and is not stored`);
    }
    let present = 0;
    for (let n = 0; n < 400; n += 1) {
      if (stored[name(n)] !== undefined) {
        present += 1;
        assert.deepEqual(stored[name(n)], part(n), `element ${n} is half written`);
      }
    }
    assert.ok(present >= known.length);
    // The database takes a new write after the ended process.
    assert.equal(call(at, { add: { "code.after": { note: "written after the ended process" } } }).answer.status, "ok");
  } finally {
    at.remove();
  }
});

test("a refused write stores nothing, and makes no table", () => {
  const at = place();
  try {
    assert.equal(call(at, { add: { "code.engine": { technical_name: "engine", name: "Game Engine", role: "Definitive" } } }).answer.status, "ok");
    const before = (() => {
      const db = projectDatabase(at);
      try {
        return tables(db);
      } finally {
        db.close();
      }
    })();
    const refused = [
      // A new field, a new layer and a new element, in a write that a rule of the map refuses.
      { add: { "code.cache": { brand_new: "value", sources: ["a"], role: "bogus" } } },
      // A list at a name that is not a layer.
      { update: { "code.engine": { other_new: "value", unknown_layer: ["a"] } } },
      // A second Definitive element.
      { add: { "code.second": { fresh_field: 1, role: "Definitive" } } },
    ];
    for (const write of refused) {
      const done = call(at, write);
      assert.equal(done.status, 1);
      assert.equal(done.answer.status, "error");
    }
    const db = projectDatabase(at);
    assert.deepEqual(tables(db), before);
    db.close();
    assert.deepEqual(call(at, { map: {} }).answer.addresses, [
      "code", "code.engine", "layer", "layer.document", "layer.document.specification",
    ]);
  } finally {
    at.remove();
  }
});

test("the format marker: a home in another format, or with files and no marker, is refused", () => {
  const other = place();
  const unmarked = place();
  try {
    writeFileSync(join(other.home, "store.format"), "metaform-store 1\n");
    writeFileSync(join(unmarked.home, "metaform.lbug"), "data of another store");
    for (const [at, reason] of [[other, 'says "metaform-store 1"'], [unmarked, "no store.format"]] as [Place, string][]) {
      const files = readdirSync(at.home);
      const done = call(at, { map: {} });
      assert.equal(done.status, 2);
      assert.equal(done.answer, null);
      assert.match(done.stderr, /^metaform: .* Nothing was changed\. Use another home \(METAFORM_HOME or --home\)\.\n$/);
      assert.ok(done.stderr.includes(reason), done.stderr);
      assert.deepEqual(readdirSync(at.home), files, "the refused home is as it was");
    }
    // A new home gets the marker, and the same home opens again.
    const fresh = place(false);
    try {
      assert.equal(call(fresh, { map: {} }).status, 0);
      assert.ok(readdirSync(fresh.home).includes("store.format"));
      assert.equal(call(fresh, { map: {} }).status, 0);
    } finally {
      fresh.remove();
    }
  } finally {
    other.remove();
    unmarked.remove();
  }
});

/** The name of each definition a schema refers to. */
function refs(schema: any, found: Set<string>): Set<string> {
  if (Array.isArray(schema)) {
    schema.forEach((item) => refs(item, found));
  } else if (schema !== null && typeof schema === "object") {
    for (const [key, value] of Object.entries(schema)) {
      if (key === "$ref" && typeof value === "string" && value.startsWith("#/$defs/")) {
        found.add(value.slice("#/$defs/".length).split("/")[0]);
      } else {
        refs(value, found);
      }
    }
  }
  return found;
}

test("help: the schema of help itself, one node of the contract for each name, and the refusal", () => {
  const names = ["add", "update", "delete", "orphaned", "goto", "map", "addressed read", "raw dump", "help"];
  const contract = JSON.parse(readFileSync(new URL("../../mcp-tools.proposed.json", import.meta.url), "utf8"));
  const input = contract.tools[0].inputSchema;
  const at = place(false);
  /** The node that `help` answers with for one name. */
  const help = (name: string): any => {
    const answer = call(at, { help: name }).answer;
    assert.deepEqual(Object.keys(answer.help), [name], JSON.stringify(answer));
    return answer.help[name];
  };
  try {
    // A project with no map yet answers, as it does for `map`.
    assert.deepEqual(call(at, { help: {} }).answer, {
      help: { type: "object", properties: { help: { enum: names } }, required: ["help"] },
    });
    // A command name answers with the contract's own entry, and no `$defs`.
    const found = new Set<string>();
    for (const name of names) {
      const entry = help(name);
      assert.ok(input.oneOf.some((form: unknown) => JSON.stringify(form) === JSON.stringify(entry)), name);
      assert.ok(!("$defs" in entry), name);
      refs(entry, found);
    }
    const add = input.oneOf.find((form: any) => form.required?.[0] === "add");
    assert.equal(JSON.stringify(help("add")), JSON.stringify(add));
    assert.match(help("raw dump").description, /^A key that starts with a period is a raw dump/);
    // A definition name answers with the contract's own definition.
    assert.equal(JSON.stringify(help("NamespaceNode")), JSON.stringify(input.$defs.NamespaceNode));
    // Every `$ref` in any answer names a definition that help answers.
    const seen = new Set<string>();
    for (let waiting = [...found]; waiting.length > 0; waiting = [...found].filter((name) => !seen.has(name))) {
      for (const definition of waiting) {
        seen.add(definition);
        const node = help(definition);
        assert.equal(JSON.stringify(node), JSON.stringify(input.$defs[definition]), definition);
        refs(node, found);
      }
    }
    assert.ok(seen.size > 5, [...seen].join(" "));
    for (const value of ["nope", "$defs", 7, { x: 1 }, [], null, ""]) {
      assert.deepEqual(call(at, { help: value }).answer, {
        help: value,
        status: "error",
        code: "FIELD_MISMATCH",
        message: "help takes {}, the name of a command, or the name of a definition a schema refers to",
        remediation: { help: {} },
      });
    }
  } finally {
    at.remove();
  }
});
