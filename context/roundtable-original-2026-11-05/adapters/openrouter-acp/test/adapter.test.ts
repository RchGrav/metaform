// ACP-surface tests for the OpenRouter adapter.
//
// The adapter (built output in dist/) runs in-process against the official ACP
// TypeScript client from @agentclientprotocol/sdk, so every exchange goes
// through the SDK's JSON-RPC layer. OpenRouter is replaced by
// mock-openrouter.ts: no network, no API key, no paid calls. The real
// @openrouter/agent loop runs unmodified on top of the mock.

import { strict as assert } from "node:assert";
import { execFileSync, spawn } from "node:child_process";
import { lstat, mkdir, mkdtemp, readFile, readlink, rm, symlink, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { createInterface } from "node:readline";
import { after, before, describe, it } from "node:test";
import { fileURLToPath } from "node:url";
import {
  client,
  methods,
  RequestError,
  type ClientContext,
  type RequestPermissionRequest,
  type RequestPermissionResponse,
  type SessionUpdate,
} from "@agentclientprotocol/sdk";
import { createAdapter } from "../dist/adapter.js";
import { mockOpenRouter, type MockOpenRouter, type ScriptedTurn } from "./mock-openrouter.ts";

const ADAPTER_DIR = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const KEY_ENV = { OPENROUTER_API_KEY: "test-key-not-real" };

interface Harness {
  ctx: ClientContext;
  mock: MockOpenRouter;
  updates: SessionUpdate[];
  permissions: RequestPermissionRequest[];
  /** The adapter's disconnect path (src/index.ts calls it when the client goes away). */
  abortAll(reason: string): void;
  newSession(cwd?: string): Promise<string>;
  prompt(sessionId: string, text: string): Promise<string>;
}

interface HarnessOptions {
  turns?: ScriptedTurn[];
  env?: Record<string, string | undefined>;
  onPermission?: (
    request: RequestPermissionRequest,
    harness: Harness,
  ) => RequestPermissionResponse | Promise<RequestPermissionResponse>;
  onUpdate?: (update: SessionUpdate, harness: Harness, sessionId: string) => void;
}

let workspace: string;

/** Runs `body` with an in-process ACP client connected to a fresh adapter. */
async function withAdapter(options: HarnessOptions, body: (h: Harness) => Promise<void>): Promise<void> {
  const mock = mockOpenRouter(options.turns ?? []);
  const { app, abortAll } = createAdapter({ env: options.env ?? KEY_ENV, fetch: mock.fetch });
  const harness = { mock, updates: [], permissions: [], abortAll } as unknown as Harness;
  const acpClient = client({ name: "test-client" })
    .onNotification(methods.client.session.update, ({ params }) => {
      harness.updates.push(params.update);
      options.onUpdate?.(params.update, harness, params.sessionId);
    })
    .onRequest(methods.client.session.requestPermission, async ({ params }) => {
      harness.permissions.push(params);
      if (options.onPermission === undefined) throw new Error("unexpected permission request");
      return options.onPermission(params, harness);
    });
  await acpClient.connectWith(app, async (ctx) => {
    harness.ctx = ctx;
    harness.newSession = async (cwd = workspace) =>
      (await ctx.request(methods.agent.session.new, { cwd, mcpServers: [] })).sessionId;
    harness.prompt = async (sessionId, text) =>
      (await ctx.request(methods.agent.session.prompt, { sessionId, prompt: [{ type: "text", text }] }))
        .stopReason;
    const init = await ctx.request(methods.agent.initialize, { protocolVersion: 1, clientCapabilities: {} });
    assert.equal(init.protocolVersion, 1);
    await body(harness);
  });
}

const allow = (): RequestPermissionResponse => ({ outcome: { outcome: "selected", optionId: "allow" } });
const reject = (): RequestPermissionResponse => ({ outcome: { outcome: "selected", optionId: "reject" } });

function toolUpdates(updates: SessionUpdate[], toolCallId: string) {
  return updates.filter(
    (u) => (u.sessionUpdate === "tool_call" || u.sessionUpdate === "tool_call_update") && u.toolCallId === toolCallId,
  ) as Array<SessionUpdate & { status?: string; content?: any[] }>;
}

function messageText(updates: SessionUpdate[]): string[] {
  return updates.flatMap((u) =>
    u.sessionUpdate === "agent_message_chunk" && u.content.type === "text" ? [u.content.text] : [],
  );
}

async function rejectsWith(promise: Promise<unknown>, code: number, pattern: RegExp): Promise<void> {
  await assert.rejects(promise, (error: unknown) => {
    assert.ok(error instanceof RequestError, `expected RequestError, got ${String(error)}`);
    assert.equal(error.code, code);
    assert.match(`${error.message} ${JSON.stringify(error.data ?? null)}`, pattern);
    return true;
  });
}

before(async () => {
  workspace = await mkdtemp(path.join(tmpdir(), "openrouter-acp-test-"));
});

after(async () => {
  await rm(workspace, { recursive: true, force: true });
});

describe("initialize", () => {
  it("advertises only implemented capabilities", async () => {
    const mock = mockOpenRouter([]);
    const { app } = createAdapter({ env: {}, fetch: mock.fetch });
    await client({ name: "t" }).connectWith(app, async (ctx) => {
      const init = await ctx.request(methods.agent.initialize, { protocolVersion: 1, clientCapabilities: {} });
      assert.deepEqual(init.agentCapabilities, {
        loadSession: false,
        promptCapabilities: { image: false, audio: false, embeddedContext: false },
        mcpCapabilities: { http: false, sse: false },
        sessionCapabilities: { close: {} },
      });
      assert.deepEqual(init.authMethods, []);
      assert.equal(init.agentInfo?.name, "openrouter-acp");
    });
    assert.equal(mock.requests.length, 0, "initialize must not call OpenRouter");
  });
});

describe("session/new", () => {
  it("fails loudly when OPENROUTER_API_KEY is absent", async () => {
    await withAdapter({ env: {} }, async (h) => {
      await rejectsWith(h.newSession(), -32000, /OPENROUTER_API_KEY is not set/);
      assert.equal(h.mock.requests.length, 0);
    });
  });

  it("offers a model option built from the published catalog", async () => {
    await withAdapter({}, async (h) => {
      const response = await h.ctx.request(methods.agent.session.new, { cwd: workspace, mcpServers: [] });
      assert.ok(response.sessionId.length > 0);
      const [option] = response.configOptions ?? [];
      assert.ok(option !== undefined && option.type === "select");
      assert.equal(option.id, "model");
      assert.equal(option.category, "model");
      assert.equal(option.currentValue, "openrouter/auto");
      // Catalog entries without tool support or without the Responses endpoint are not offered.
      assert.deepEqual(
        (option.options as Array<{ value: string }>).map((o) => o.value),
        ["openrouter/auto", "anthropic/claude-test", "openai/gpt-test"],
      );
      const [catalogRequest] = h.mock.requests;
      assert.equal(catalogRequest?.url, "https://openrouter.ai/api/v1/models");
      assert.equal(catalogRequest?.headers.get("authorization"), "Bearer test-key-not-real");
    });
  });

  it("rejects a relative cwd, a missing directory and client MCP servers", async () => {
    await withAdapter({}, async (h) => {
      await rejectsWith(h.newSession("relative/dir"), -32602, /absolute/);
      await rejectsWith(h.newSession(path.join(workspace, "does-not-exist")), -32602, /not a usable directory/);
      await rejectsWith(
        h.ctx.request(methods.agent.session.new, {
          cwd: workspace,
          mcpServers: [{ name: "x", command: "/bin/true", args: [], env: [] }],
        }),
        -32602,
        /MCP servers/,
      );
    });
  });
});

describe("session/set_config_option", () => {
  it("selects a catalog model, which the next prompt uses", async () => {
    await withAdapter({ turns: [{ text: ["ok"] }] }, async (h) => {
      const sessionId = await h.newSession();
      const response = await h.ctx.request(methods.agent.session.setConfigOption, {
        sessionId,
        configId: "model",
        value: "anthropic/claude-test",
      });
      assert.equal(response.configOptions[0]?.currentValue, "anthropic/claude-test");
      assert.equal(await h.prompt(sessionId, "hi"), "end_turn");
      assert.equal(h.mock.responseRequests()[0].model, "anthropic/claude-test");
    });
  });

  it("rejects models not in the catalog option and unknown option ids", async () => {
    await withAdapter({}, async (h) => {
      const sessionId = await h.newSession();
      await rejectsWith(
        h.ctx.request(methods.agent.session.setConfigOption, { sessionId, configId: "model", value: "acme/no-tools" }),
        -32602,
        /not a model offered/,
      );
      await rejectsWith(
        h.ctx.request(methods.agent.session.setConfigOption, { sessionId, configId: "temperature", value: "1" }),
        -32602,
        /unknown config option/,
      );
    });
  });
});

describe("session/prompt", () => {
  it("streams agent_message_chunk updates and ends with end_turn", async () => {
    await withAdapter({ turns: [{ text: ["Hel", "lo, ", "table."] }] }, async (h) => {
      const sessionId = await h.newSession();
      assert.equal(await h.prompt(sessionId, "Say hello"), "end_turn");
      assert.deepEqual(messageText(h.updates), ["Hel", "lo, ", "table."]);
      const [request] = h.mock.responseRequests();
      assert.equal(request.model, "openrouter/auto");
      assert.equal(request.stream, true);
      assert.deepEqual(request.input, [{ role: "user", content: [{ type: "input_text", text: "Say hello" }] }]);
      assert.deepEqual(
        request.tools.map((t: { name: string }) => t.name).sort(),
        ["list_directory", "read_file", "run_command", "write_file"],
      );
    });
  });

  it("keeps the conversation across prompts", async () => {
    await withAdapter({ turns: [{ text: ["first"] }, { text: ["second"] }] }, async (h) => {
      const sessionId = await h.newSession();
      await h.prompt(sessionId, "one");
      await h.prompt(sessionId, "two");
      const input = h.mock.responseRequests()[1].input;
      assert.equal(input[0].content[0].text, "one");
      assert.equal(input[1].content[0].text, "first");
      assert.equal(input.at(-1).content[0].text, "two");
    });
  });

  it("reports a broken model stream as a prompt error; the session stays usable", async () => {
    const turns: ScriptedTurn[] = [
      { text: ["partial"], fail: new Error("upstream connection reset") },
      { text: ["recovered"] },
    ];
    await withAdapter({ turns }, async (h) => {
      const sessionId = await h.newSession();
      await rejectsWith(h.prompt(sessionId, "first"), -32603, /upstream connection reset/);
      assert.equal(await h.prompt(sessionId, "second"), "end_turn");
    });
  });

  it("rejects prompt content types that are not advertised", async () => {
    await withAdapter({}, async (h) => {
      const sessionId = await h.newSession();
      await rejectsWith(
        h.ctx.request(methods.agent.session.prompt, {
          sessionId,
          prompt: [{ type: "image", data: "AAAA", mimeType: "image/png" }],
        }),
        -32602,
        /not supported/,
      );
    });
  });
});

describe("tools", () => {
  it("asks permission before write_file, writes on allow, and reports the tool lifecycle", async () => {
    const turns: ScriptedTurn[] = [
      {
        text: ["Writing."],
        toolCalls: [{ callId: "call_w", name: "write_file", args: { path: "out/notes.txt", content: "hello\n" } }],
      },
      { text: ["Written."] },
    ];
    await withAdapter({ turns, onPermission: allow }, async (h) => {
      const sessionId = await h.newSession();
      assert.equal(await h.prompt(sessionId, "write it"), "end_turn");

      const target = path.join(workspace, "out", "notes.txt");
      assert.equal(await readFile(target, "utf8"), "hello\n");

      assert.equal(h.permissions.length, 1);
      const permission = h.permissions[0]!;
      assert.equal(permission.sessionId, sessionId);
      assert.equal(permission.toolCall.toolCallId, "call_w");
      assert.equal(permission.toolCall.kind, "edit");
      assert.deepEqual(permission.toolCall.content, [{ type: "diff", path: target, oldText: null, newText: "hello\n" }]);
      assert.deepEqual(permission.options.map((o) => o.kind), ["allow_once", "reject_once"]);

      const lifecycle = toolUpdates(h.updates, "call_w");
      assert.equal(lifecycle[0]?.sessionUpdate, "tool_call");
      assert.equal(lifecycle[0]?.status, "pending");
      assert.deepEqual(
        lifecycle.slice(1).map((u) => u.status).filter((s) => s !== undefined),
        ["in_progress", "completed"],
      );
      assert.deepEqual(messageText(h.updates), ["Writing.", "Written."]);

      const followUp = h.mock.responseRequests()[1].input;
      const output = followUp.find((item: any) => item.type === "function_call_output");
      assert.equal(output.call_id, "call_w");
      assert.deepEqual(JSON.parse(output.output), { path: path.join("out", "notes.txt"), bytesWritten: 6 });
    });
  });

  it("does not run a command the client rejects and tells the model", async () => {
    const marker = path.join(workspace, "rejected-marker");
    const turns: ScriptedTurn[] = [
      { toolCalls: [{ callId: "call_r", name: "run_command", args: { command: `touch ${marker}` } }] },
      { text: ["Understood."] },
    ];
    await withAdapter({ turns, onPermission: reject }, async (h) => {
      const sessionId = await h.newSession();
      assert.equal(await h.prompt(sessionId, "run it"), "end_turn");
      await assert.rejects(readFile(marker), { code: "ENOENT" });
      assert.equal(h.permissions[0]?.toolCall.kind, "execute");
      const lifecycle = toolUpdates(h.updates, "call_r");
      assert.equal(lifecycle.at(-1)?.status, "failed");
      assert.ok(!lifecycle.some((u) => u.status === "in_progress"));
      const output = h.mock.responseRequests()[1].input.find((item: any) => item.type === "function_call_output");
      assert.match(output.output, /denied permission/);
    });
  });

  it("runs an allowed command in the session cwd without the OpenRouter key in its environment", async () => {
    const turns: ScriptedTurn[] = [
      {
        toolCalls: [
          { callId: "call_c", name: "run_command", args: { command: 'pwd; printf "%s" "${OPENROUTER_API_KEY-withheld}"' } },
        ],
      },
      { text: ["Ran."] },
    ];
    const previous = process.env.OPENROUTER_API_KEY;
    process.env.OPENROUTER_API_KEY = "must-not-leak";
    try {
      await withAdapter({ turns, onPermission: allow }, async (h) => {
        const sessionId = await h.newSession();
        assert.equal(await h.prompt(sessionId, "run"), "end_turn");
        const output = h.mock.responseRequests()[1].input.find((item: any) => item.type === "function_call_output");
        const result = JSON.parse(output.output);
        assert.equal(result.exitCode, 0);
        assert.equal(result.stdout, `${workspace}\nwithheld`);
      });
    } finally {
      if (previous === undefined) delete process.env.OPENROUTER_API_KEY;
      else process.env.OPENROUTER_API_KEY = previous;
    }
  });

  it("reads and lists files without a permission request", async () => {
    await writeFile(path.join(workspace, "readme.txt"), "contents");
    const turns: ScriptedTurn[] = [
      {
        toolCalls: [
          { callId: "call_l", name: "list_directory", args: {} },
          { callId: "call_f", name: "read_file", args: { path: "readme.txt" } },
        ],
      },
      { text: ["Read."] },
    ];
    await withAdapter({ turns }, async (h) => {
      const sessionId = await h.newSession();
      assert.equal(await h.prompt(sessionId, "look"), "end_turn");
      assert.equal(h.permissions.length, 0);
      const outputs = h.mock.responseRequests()[1].input.filter((item: any) => item.type === "function_call_output");
      const byId = Object.fromEntries(outputs.map((o: any) => [o.call_id, JSON.parse(o.output)]));
      assert.ok(byId.call_l.entries.includes("readme.txt"));
      assert.equal(byId.call_f.content, "contents");
      assert.equal(toolUpdates(h.updates, "call_f").at(-1)?.status, "completed");
    });
  });

  it("confines file tools to the session cwd, including through symlinks", async () => {
    const outside = await mkdtemp(path.join(tmpdir(), "openrouter-acp-outside-"));
    await writeFile(path.join(outside, "secret.txt"), "secret");
    await symlink(outside, path.join(workspace, "escape"));
    const turns: ScriptedTurn[] = [
      {
        toolCalls: [
          { callId: "call_up", name: "read_file", args: { path: "../secret.txt" } },
          { callId: "call_abs", name: "read_file", args: { path: path.join(outside, "secret.txt") } },
          { callId: "call_link", name: "write_file", args: { path: "escape/new.txt", content: "x" } },
        ],
      },
      { text: ["Blocked."] },
    ];
    try {
      await withAdapter({ turns }, async (h) => {
        const sessionId = await h.newSession();
        assert.equal(await h.prompt(sessionId, "escape"), "end_turn");
        assert.equal(h.permissions.length, 0, "a confinement failure must not reach the permission step");
        await assert.rejects(readFile(path.join(outside, "new.txt")), { code: "ENOENT" });
        for (const id of ["call_up", "call_abs", "call_link"]) {
          assert.equal(toolUpdates(h.updates, id).at(-1)?.status, "failed", id);
        }
        const outputs = h.mock.responseRequests()[1].input.filter((item: any) => item.type === "function_call_output");
        for (const output of outputs) assert.match(output.output, /outside the session working directory/);
      });
    } finally {
      await rm(path.join(workspace, "escape"));
      await rm(outside, { recursive: true, force: true });
    }
  });

  it("refuses dangling symlinks that lead outside the session cwd", async () => {
    const outside = await mkdtemp(path.join(tmpdir(), "openrouter-acp-outside-"));
    await mkdir(path.join(outside, "sub"));
    const dir = path.join(workspace, "dangling-out");
    await mkdir(dir);
    // A link to a missing file outside the root (the F02 reproduction).
    await symlink(path.join(outside, "created.txt"), path.join(dir, "direct"));
    // A chain of dangling links that ends outside the root.
    await symlink(path.join(outside, "chained.txt"), path.join(dir, "chain2"));
    await symlink("chain2", path.join(dir, "chain1"));
    // ".." in link text is resolved after the preceding link (esc -> outside/sub),
    // so it leads to outside/dotdot.txt, not lexically to dangling-out/dotdot.txt.
    await symlink(path.join(outside, "sub"), path.join(dir, "esc"));
    await symlink("esc/../dotdot.txt", path.join(dir, "dotdot"));
    const turns: ScriptedTurn[] = [
      {
        toolCalls: [
          { callId: "call_direct", name: "write_file", args: { path: "dangling-out/direct", content: "x" } },
          { callId: "call_chain", name: "write_file", args: { path: "dangling-out/chain1", content: "x" } },
          { callId: "call_dotdot", name: "write_file", args: { path: "dangling-out/dotdot", content: "x" } },
          { callId: "call_read", name: "read_file", args: { path: "dangling-out/direct" } },
        ],
      },
      { text: ["Blocked."] },
    ];
    try {
      await withAdapter({ turns }, async (h) => {
        const sessionId = await h.newSession();
        assert.equal(await h.prompt(sessionId, "escape"), "end_turn");
        assert.equal(h.permissions.length, 0, "a confinement failure must not reach the permission step");
        for (const name of ["created.txt", "chained.txt", "dotdot.txt"]) {
          await assert.rejects(lstat(path.join(outside, name)), { code: "ENOENT" }, name);
        }
        await assert.rejects(lstat(path.join(dir, "dotdot.txt")), { code: "ENOENT" });
        for (const id of ["call_direct", "call_chain", "call_dotdot", "call_read"]) {
          assert.equal(toolUpdates(h.updates, id).at(-1)?.status, "failed", id);
        }
        const outputs = h.mock.responseRequests()[1].input.filter((item: any) => item.type === "function_call_output");
        assert.equal(outputs.length, 4);
        for (const output of outputs) assert.match(output.output, /outside the session working directory/);
      });
    } finally {
      await rm(dir, { recursive: true, force: true });
      await rm(outside, { recursive: true, force: true });
    }
  });

  it("writes through symlinks that stay inside the session cwd, and writes ordinary new files", async () => {
    const dir = path.join(workspace, "links-in");
    await mkdir(dir);
    await writeFile(path.join(dir, "target.txt"), "old");
    await symlink("target.txt", path.join(dir, "existing"));
    await symlink("made.txt", path.join(dir, "dangling"));
    const turns: ScriptedTurn[] = [
      {
        toolCalls: [
          { callId: "call_existing", name: "write_file", args: { path: "links-in/existing", content: "new" } },
          { callId: "call_dangling", name: "write_file", args: { path: "links-in/dangling", content: "made" } },
          { callId: "call_plain", name: "write_file", args: { path: "links-in/plain/new.txt", content: "plain" } },
        ],
      },
      { text: ["Written."] },
    ];
    try {
      await withAdapter({ turns, onPermission: allow }, async (h) => {
        const sessionId = await h.newSession();
        assert.equal(await h.prompt(sessionId, "write"), "end_turn");
        assert.equal(h.permissions.length, 3);
        for (const id of ["call_existing", "call_dangling", "call_plain"]) {
          assert.equal(toolUpdates(h.updates, id).at(-1)?.status, "completed", id);
        }
        // The link to an existing file writes that file; the links themselves are untouched.
        assert.equal(await readFile(path.join(dir, "target.txt"), "utf8"), "new");
        assert.ok((await lstat(path.join(dir, "existing"))).isSymbolicLink());
        assert.equal(await readlink(path.join(dir, "existing")), "target.txt");
        const existingPermission = h.permissions.find((p) => p.toolCall.toolCallId === "call_existing")!;
        assert.deepEqual(existingPermission.toolCall.content, [
          { type: "diff", path: path.join(dir, "target.txt"), oldText: "old", newText: "new" },
        ]);
        // A dangling link inside the root creates its in-root target.
        assert.equal(await readFile(path.join(dir, "made.txt"), "utf8"), "made");
        assert.ok((await lstat(path.join(dir, "dangling"))).isSymbolicLink());
        assert.equal(await readFile(path.join(dir, "plain", "new.txt"), "utf8"), "plain");
      });
    } finally {
      await rm(dir, { recursive: true, force: true });
    }
  });

  it("re-checks confinement at write time when the file became a symlink during the permission request", async () => {
    const outside = await mkdtemp(path.join(tmpdir(), "openrouter-acp-outside-"));
    const dir = path.join(workspace, "swap");
    const turns: ScriptedTurn[] = [
      { toolCalls: [{ callId: "call_swap", name: "write_file", args: { path: "swap/file.txt", content: "x" } }] },
      { text: ["Blocked."] },
    ];
    try {
      await withAdapter(
        {
          turns,
          onPermission: async () => {
            await mkdir(dir);
            await symlink(path.join(outside, "swapped.txt"), path.join(dir, "file.txt"));
            return allow();
          },
        },
        async (h) => {
          const sessionId = await h.newSession();
          assert.equal(await h.prompt(sessionId, "write"), "end_turn");
          assert.equal(h.permissions.length, 1);
          assert.equal(toolUpdates(h.updates, "call_swap").at(-1)?.status, "failed");
          await assert.rejects(lstat(path.join(outside, "swapped.txt")), { code: "ENOENT" });
          const output = h.mock.responseRequests()[1].input.find((item: any) => item.type === "function_call_output");
          assert.match(output.output, /outside the session working directory/);
        },
      );
    } finally {
      await rm(dir, { recursive: true, force: true });
      await rm(outside, { recursive: true, force: true });
    }
  });
});

describe("session/cancel", () => {
  it("stops a streaming turn with stopReason cancelled; the session stays usable", async () => {
    let cancelSent = false;
    const turns: ScriptedTurn[] = [
      { text: ["partial"], hold: new Promise<void>(() => {}) },
      { text: ["after cancel"] },
    ];
    await withAdapter(
      {
        turns,
        onUpdate: (update, h, sessionId) => {
          if (!cancelSent && update.sessionUpdate === "agent_message_chunk") {
            cancelSent = true;
            void h.ctx.notify(methods.agent.session.cancel, { sessionId });
          }
        },
      },
      async (h) => {
        const sessionId = await h.newSession();
        assert.equal(await h.prompt(sessionId, "long task"), "cancelled");
        assert.equal(await h.prompt(sessionId, "next"), "end_turn");
        assert.deepEqual(messageText(h.updates), ["partial", "after cancel"]);
        const input = h.mock.responseRequests()[1].input;
        assert.equal(input.at(-1).content[0].text, "next");
      },
    );
  });

  it("kills a running command and ends the turn cancelled; history stays well-formed", async () => {
    const turns: ScriptedTurn[] = [
      { toolCalls: [{ callId: "call_s", name: "run_command", args: { command: "exec sleep 1000" } }] },
      { text: ["resumed"] },
    ];
    await withAdapter(
      {
        turns,
        onPermission: allow,
        onUpdate: (update, h, sessionId) => {
          if (update.sessionUpdate === "tool_call_update" && update.status === "in_progress") {
            void h.ctx.notify(methods.agent.session.cancel, { sessionId });
          }
        },
      },
      async (h) => {
        const sessionId = await h.newSession();
        assert.equal(await h.prompt(sessionId, "sleep"), "cancelled");
        assert.equal(toolUpdates(h.updates, "call_s").at(-1)?.status, "failed");
        assert.equal(await h.prompt(sessionId, "continue"), "end_turn");
        const input = h.mock.responseRequests()[1].input;
        const call = input.find((item: any) => item.type === "function_call");
        const output = input.find((item: any) => item.type === "function_call_output");
        assert.equal(call.call_id, "call_s");
        assert.equal(output.call_id, "call_s", "the interrupted call must carry an output");
      },
    );
  });

  /**
   * Runs a command whose shell (the process-group leader) exits while a background
   * job keeps the output pipes open, waits until the leader has exited and been
   * reaped, then calls `stop`. The turn must end cancelled, which requires the
   * background job to be killed: the command settles only when its pipes close.
   */
  async function stopAfterLeaderExit(stop: (h: Harness, sessionId: string) => void): Promise<void> {
    const fifos = await mkdtemp(path.join(tmpdir(), "openrouter-acp-fifo-"));
    const leaderFifo = path.join(fifos, "leader");
    const readyFifo = path.join(fifos, "ready");
    execFileSync("mkfifo", [leaderFifo, readyFifo]);
    // The background job is started before the shell opens leaderFifo for writing,
    // so only the shell holds the write end: the job's `cat` reaches EOF when the
    // shell exits. The job then reports $$ (the shell's pid, which is the command's
    // process-group ID) and holds stdout/stderr open in a long sleep.
    const command = `{ cat ${leaderFifo} >/dev/null; echo $$ > ${readyFifo}; exec sleep 1000; } & exec 3>${leaderFifo}; exit 0`;
    const turns: ScriptedTurn[] = [
      { toolCalls: [{ callId: "call_bg", name: "run_command", args: { command } }] },
      { text: ["resumed"] },
    ];
    let group: number | undefined;
    let stopping: Promise<void> | undefined;
    try {
      await withAdapter(
        {
          turns,
          onPermission: allow,
          onUpdate: (update, h, sessionId) => {
            if (update.sessionUpdate !== "tool_call_update" || update.status !== "in_progress") return;
            stopping = (async () => {
              group = Number((await readFile(readyFifo, "utf8")).trim());
              assert.ok(Number.isInteger(group) && group > 1, `process group ${group}`);
              // The leader's pid is the group ID, which the kernel does not reuse while
              // the background job is alive; ESRCH therefore means the leader has been
              // reaped (and Node has recorded its exit). Yield to the event loop until then.
              for (;;) {
                try {
                  process.kill(group, 0);
                } catch (error) {
                  if ((error as NodeJS.ErrnoException).code === "ESRCH") break;
                  throw error;
                }
                await new Promise((resolve) => setImmediate(resolve));
              }
              stop(h, sessionId);
            })();
          },
        },
        async (h) => {
          const sessionId = await h.newSession();
          assert.equal(await h.prompt(sessionId, "background"), "cancelled");
          await stopping;
          assert.equal(toolUpdates(h.updates, "call_bg").at(-1)?.status, "failed");
          assert.equal(await h.prompt(sessionId, "continue"), "end_turn");
        },
      );
    } finally {
      // Clean up the test's process group whatever happened above.
      if (group !== undefined) {
        try {
          process.kill(-group, "SIGKILL");
        } catch (error) {
          if ((error as NodeJS.ErrnoException).code !== "ESRCH") throw error;
        }
      }
      await rm(fifos, { recursive: true, force: true });
    }
  }

  it("kills background jobs that outlive the shell when the turn is cancelled", async () => {
    await stopAfterLeaderExit((h, sessionId) => void h.ctx.notify(methods.agent.session.cancel, { sessionId }));
  });

  it("kills background jobs that outlive the shell when the client disconnects", async () => {
    await stopAfterLeaderExit((h) => h.abortAll("client connection closed"));
  });

  it("ends the turn cancelled when cancel arrives during a permission request", async () => {
    const marker = path.join(workspace, "cancel-marker");
    const turns: ScriptedTurn[] = [
      { toolCalls: [{ callId: "call_p", name: "run_command", args: { command: `touch ${marker}` } }] },
    ];
    await withAdapter(
      {
        turns,
        onPermission: async (request, h) => {
          // ACP: the client cancels, then answers pending permission requests with `cancelled`.
          await h.ctx.notify(methods.agent.session.cancel, { sessionId: request.sessionId });
          return { outcome: { outcome: "cancelled" } };
        },
      },
      async (h) => {
        const sessionId = await h.newSession();
        assert.equal(await h.prompt(sessionId, "touch"), "cancelled");
        await assert.rejects(readFile(marker), { code: "ENOENT" });
        assert.equal(h.mock.remaining(), 0);
      },
    );
  });
});

describe("session/close", () => {
  it("removes the session", async () => {
    await withAdapter({}, async (h) => {
      const sessionId = await h.newSession();
      assert.deepEqual(await h.ctx.request(methods.agent.session.close, { sessionId }), {});
      await rejectsWith(h.prompt(sessionId, "hi"), -32002, /not found/i);
    });
  });
});

describe("stdio process", () => {
  it("answers initialize over stdin/stdout and fails session/new loudly without a key", async () => {
    const env = { ...process.env };
    delete env.OPENROUTER_API_KEY;
    const child = spawn(process.execPath, [path.join(ADAPTER_DIR, "dist", "index.js")], {
      env,
      stdio: ["pipe", "pipe", "inherit"],
    });
    const lines = createInterface({ input: child.stdout })[Symbol.asyncIterator]();
    const send = (message: object) => child.stdin.write(`${JSON.stringify(message)}\n`);
    const next = async () => JSON.parse((await lines.next()).value as string);

    send({
      jsonrpc: "2.0",
      id: 0,
      method: "initialize",
      params: { protocolVersion: 1, clientCapabilities: {}, clientInfo: { name: "roundtable", version: "1.0.0" } },
    });
    const init = await next();
    assert.equal(init.id, 0);
    assert.equal(init.result.protocolVersion, 1);
    assert.equal(init.result.agentInfo.name, "openrouter-acp");

    send({ jsonrpc: "2.0", id: 1, method: "session/new", params: { cwd: workspace, mcpServers: [] } });
    const created = await next();
    assert.equal(created.id, 1);
    assert.equal(created.error.code, -32000);
    assert.match(created.error.message, /OPENROUTER_API_KEY is not set/);

    const exited = new Promise<number | null>((resolve) => child.on("exit", (code) => resolve(code)));
    child.stdin.end();
    assert.equal(await exited, 0);
  });
});
