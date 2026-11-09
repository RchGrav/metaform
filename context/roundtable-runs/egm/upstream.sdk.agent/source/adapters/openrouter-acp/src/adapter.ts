// ACP agent side, backed by the OpenRouter Agent SDK.
//
// Implements ACP v1: initialize, session/new, session/set_config_option,
// session/prompt (streaming session/update), session/cancel, session/close.
// Every session holds its own OpenRouter conversation state; the `model`
// config option selects the OpenRouter model id used for subsequent prompts.

import { randomUUID } from "node:crypto";
import { promises as fs } from "node:fs";
import { createRequire } from "node:module";
import path from "node:path";
import {
  agent,
  methods,
  PROTOCOL_VERSION,
  RequestError,
  type AgentApp,
  type AgentContext,
  type ContentBlock,
  type SessionConfigOption,
  type SessionConfigSelectOption,
  type StopReason,
} from "@agentclientprotocol/sdk";
import {
  callModel,
  OpenRouter,
  type ConversationState,
  type OpenResponsesResult,
  type StateAccessor,
} from "@openrouter/agent";
import { HTTPClient } from "@openrouter/sdk";
import { CatalogError, fetchModelOptions, INITIAL_MODEL } from "./models.js";
import { patchModelResult } from "./sdk-patch.js";
import { createTools } from "./tools.js";

patchModelResult();

const pkg = createRequire(import.meta.url)("../package.json") as { name: string; version: string };

export const MODEL_CONFIG_ID = "model";

export interface AdapterOptions {
  /** Environment to read OPENROUTER_API_KEY from (normally process.env). */
  env: Record<string, string | undefined>;
  /** fetch used for every OpenRouter HTTP request (normally globalThis.fetch). */
  fetch: typeof fetch;
}

interface Turn {
  controller: AbortController;
}

interface Session {
  id: string;
  root: string;
  model: string;
  models: SessionConfigSelectOption[];
  openrouter: OpenRouter;
  state: ConversationState | null;
  turn: Turn | null;
}

function modelOption(session: Session): SessionConfigOption {
  return {
    id: MODEL_CONFIG_ID,
    name: "Model",
    description: "OpenRouter model id used for this session's prompts",
    category: "model",
    type: "select",
    currentValue: session.model,
    options: session.models,
  };
}

/** Converts an ACP prompt to the text parts of one OpenRouter user message. */
function promptToText(prompt: ContentBlock[]): string[] {
  return prompt.map((block) => {
    switch (block.type) {
      case "text":
        return block.text;
      case "resource_link":
        return `Resource: [${block.title ?? block.name}](${block.uri})`;
      default:
        throw RequestError.invalidParams(
          undefined,
          `prompt content type "${block.type}" is not supported (promptCapabilities advertises text and resource_link only)`,
        );
    }
  });
}

function stopReasonOf(response: OpenResponsesResult): StopReason {
  if (response.status === "incomplete") {
    const reason = response.incompleteDetails?.reason;
    if (reason === "max_output_tokens") return "max_tokens";
    if (reason === "content_filter") return "refusal";
    throw RequestError.internalError(
      undefined,
      `OpenRouter returned an incomplete response (reason: ${reason ?? "not given"})`,
    );
  }
  const refused = response.output.some(
    (item) => item.type === "message" && item.content.some((part) => part.type === "refusal"),
  );
  return refused ? "refusal" : "end_turn";
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

export interface Adapter {
  app: AgentApp;
  /** Aborts every running turn (and the commands they started). */
  abortAll(reason: string): void;
}

export function createAdapter(options: AdapterOptions): Adapter {
  const sessions = new Map<string, Session>();

  const getSession = (sessionId: string): Session => {
    const session = sessions.get(sessionId);
    if (session === undefined) throw RequestError.sessionNotFound(sessionId);
    return session;
  };

  const apiKey = (): string => {
    const key = options.env.OPENROUTER_API_KEY;
    if (key === undefined || key.trim() === "") {
      throw RequestError.authRequired(
        undefined,
        "OPENROUTER_API_KEY is not set in the environment of the openrouter-acp adapter process",
      );
    }
    return key;
  };

  const runTurn = async (
    session: Session,
    client: AgentContext,
    text: string[],
    signal: AbortSignal,
  ): Promise<StopReason> => {
    const state: StateAccessor = {
      load: async () => session.state,
      save: async (next) => {
        session.state = next;
      },
    };
    const result = callModel(session.openrouter, {
      model: session.model,
      input: [
        {
          role: "user",
          content: text.map((part) => ({ type: "input_text" as const, text: part })),
        },
      ],
      tools: createTools({ sessionId: session.id, root: session.root, client }),
      state,
      signal,
    });
    for await (const delta of result.getTextStream()) {
      await client.notify(methods.client.session.update, {
        sessionId: session.id,
        update: { sessionUpdate: "agent_message_chunk", content: { type: "text", text: delta } },
      });
    }
    return stopReasonOf(await result.getResponse());
  };

  const app = agent({ name: pkg.name });

  app.onRequest(methods.agent.initialize, () => ({
    protocolVersion: PROTOCOL_VERSION,
    agentCapabilities: {
      loadSession: false,
      promptCapabilities: { image: false, audio: false, embeddedContext: false },
      mcpCapabilities: { http: false, sse: false },
      sessionCapabilities: { close: {} },
    },
    authMethods: [],
    agentInfo: { name: pkg.name, title: "OpenRouter Agent SDK", version: pkg.version },
  }));

  app.onRequest(methods.agent.session.new, async ({ params }) => {
    const key = apiKey();
    if (!path.isAbsolute(params.cwd)) {
      throw RequestError.invalidParams(undefined, `cwd must be an absolute path: ${params.cwd}`);
    }
    if (params.mcpServers.length > 0) {
      throw RequestError.invalidParams(
        undefined,
        "this adapter does not connect to client-supplied MCP servers; send mcpServers: []",
      );
    }
    if (params.additionalDirectories !== undefined && params.additionalDirectories.length > 0) {
      throw RequestError.invalidParams(undefined, "additionalDirectories is not supported (not advertised)");
    }
    let root: string;
    try {
      root = await fs.realpath(params.cwd);
      if (!(await fs.stat(root)).isDirectory()) throw new Error("not a directory");
    } catch (error) {
      throw RequestError.invalidParams(undefined, `cwd ${params.cwd} is not a usable directory: ${errorMessage(error)}`);
    }

    let models: SessionConfigSelectOption[];
    try {
      models = await fetchModelOptions(options.fetch, key);
    } catch (error) {
      if (error instanceof CatalogError) throw RequestError.internalError(undefined, error.message);
      throw error;
    }
    if (!models.some((model) => model.value === INITIAL_MODEL)) {
      throw RequestError.internalError(
        undefined,
        `OpenRouter's model catalog no longer lists ${INITIAL_MODEL}, the model new sessions start on`,
      );
    }

    const session: Session = {
      id: randomUUID(),
      root,
      model: INITIAL_MODEL,
      models,
      openrouter: new OpenRouter({
        apiKey: key,
        httpClient: new HTTPClient({ fetcher: (request) => options.fetch(request) }),
        // The SDK's default retries 5XX/connection errors with timed backoff for
        // up to an hour; errors are surfaced to the client instead.
        retryConfig: { strategy: "none" },
      }),
      state: null,
      turn: null,
    };
    sessions.set(session.id, session);
    return { sessionId: session.id, configOptions: [modelOption(session)] };
  });

  app.onRequest(methods.agent.session.setConfigOption, ({ params }) => {
    const session = getSession(params.sessionId);
    if (params.configId !== MODEL_CONFIG_ID) {
      throw RequestError.invalidParams(undefined, `unknown config option "${params.configId}"`);
    }
    const value = params.value;
    if (typeof value !== "string" || !session.models.some((model) => model.value === value)) {
      throw RequestError.invalidParams(
        undefined,
        `"${String(value)}" is not a model offered by this session's ${MODEL_CONFIG_ID} option`,
      );
    }
    session.model = value;
    return { configOptions: [modelOption(session)] };
  });

  app.onRequest(methods.agent.session.prompt, async ({ params, client, signal }) => {
    const session = getSession(params.sessionId);
    apiKey();
    if (session.turn !== null) {
      throw RequestError.invalidRequest(undefined, "a prompt turn is already running in this session");
    }
    const text = promptToText(params.prompt);
    const turn: Turn = { controller: new AbortController() };
    const abort = () => turn.controller.abort(new Error("session/prompt request aborted"));
    signal.addEventListener("abort", abort, { once: true });
    session.turn = turn;
    try {
      const stopReason = await runTurn(session, client, text, turn.controller.signal);
      return { stopReason };
    } catch (error) {
      if (turn.controller.signal.aborted) return { stopReason: "cancelled" as const };
      if (error instanceof RequestError) throw error;
      throw RequestError.internalError(undefined, `OpenRouter agent turn failed: ${errorMessage(error)}`);
    } finally {
      signal.removeEventListener("abort", abort);
      session.turn = null;
    }
  });

  app.onNotification(methods.agent.session.cancel, ({ params }) => {
    const session = sessions.get(params.sessionId);
    if (session === undefined) {
      // A notification has no response; report the client error on stderr.
      process.stderr.write(`openrouter-acp: session/cancel for unknown session ${params.sessionId}\n`);
      return;
    }
    session.turn?.controller.abort(new Error("turn cancelled by session/cancel"));
  });

  app.onRequest(methods.agent.session.close, ({ params }) => {
    const session = getSession(params.sessionId);
    session.turn?.controller.abort(new Error("turn cancelled by session/close"));
    sessions.delete(session.id);
    return {};
  });

  const abortAll = (reason: string) => {
    for (const session of sessions.values()) session.turn?.controller.abort(new Error(reason));
  };

  return { app, abortAll };
}
