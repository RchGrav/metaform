// The stdio MCP server: one JSON-RPC message on each line of stdin, one reply on each line of
// stdout. The Rust form uses the `rmcp` crate for this; the replies here were copied from that
// form's replies, request by request. The capabilities do not offer `resources`, because this
// form has no change announcements (design document, section 2).
//
// A client may speak in two ways. A 2026-07-28 client sends no `initialize`, and every request
// carries its protocol version in `_meta`. An older client sends `initialize` first.

import type { Json, JsonObject } from "./json.ts";
import { get, isObject, obj, parse, stringify } from "./json.ts";
import type { MapTool } from "./tool.ts";

const PROTOCOL_VERSION = "io.modelcontextprotocol/protocolVersion";
const CLIENT_CAPABILITIES = "io.modelcontextprotocol/clientCapabilities";
/** The protocol version whose requests carry `_meta` and whose results carry `resultType`. */
const STATELESS = "2026-07-28";
/** The versions an `initialize` may ask for. Another version gets the last of these. */
const WITH_HANDSHAKE = ["2024-11-05", "2025-03-26", "2025-06-18", "2025-11-25"];
const SUPPORTED = [...WITH_HANDSHAKE, STATELESS];

const INVALID_REQUEST = -32600;
const METHOD_NOT_FOUND = -32601;
const INVALID_PARAMS = -32602;
const UNSUPPORTED_VERSION = -32022;

/** A JSON-RPC error that is the reply to a request. */
class ProtocolError {
  code: number;
  message: string;
  data: Json | undefined;

  constructor(code: number, message: string, data?: Json) {
    this.code = code;
    this.message = message;
    this.data = data;
  }
}

export class Server {
  private tool: MapTool;
  private serverInfo: JsonObject;
  /** True once an older client has sent `initialize`. */
  private initialized = false;

  constructor(tool: MapTool, version: string) {
    this.tool = tool;
    this.serverInfo = obj(["name", "metaform"], ["version", version]);
  }

  private capabilities(): JsonObject {
    return obj(["tools", obj()]);
  }

  /** The reply to one line, as one line of JSON, or `null` when the line gets no reply. */
  handle(line: string): string | null {
    let message: Json;
    try {
      message = parse(line);
    } catch {
      return null;
    }
    const invalid = stringify(
      obj(["jsonrpc", "2.0"], ["error", obj(["code", INVALID_REQUEST], ["message", "Invalid request"])]),
    );
    if (!isObject(message) || message.get("jsonrpc") !== "2.0") {
      return invalid;
    }
    const id = message.get("id");
    const method = message.get("method");
    const params = message.get("params");
    const idIsValid = id === undefined || typeof id === "string" || (typeof id === "number" && Number.isInteger(id));
    if (!idIsValid || (params !== undefined && !isObject(params))) {
      return invalid;
    }
    if (typeof method !== "string") {
      // A reply to a request this server never sent, or a message with no method.
      return message.has("result") || message.has("error") ? null : invalid;
    }
    if (id === undefined) {
      // A notification, such as `notifications/initialized`, gets no reply.
      return null;
    }
    const reply = obj(["jsonrpc", "2.0"], ["id", id]);
    try {
      reply.set("result", this.request(method, params ?? obj()));
    } catch (problem) {
      if (!(problem instanceof ProtocolError)) {
        throw problem;
      }
      const error = obj(["code", problem.code], ["message", problem.message]);
      if (problem.data !== undefined) {
        error.set("data", problem.data);
      }
      reply.set("error", error);
    }
    return stringify(reply);
  }

  /** The result of one request. Throws `ProtocolError` for a request the server does not answer. */
  private request(method: string, params: JsonObject): JsonObject {
    if (method === "initialize" && typeof params.get("protocolVersion") === "string") {
      const asked = params.get("protocolVersion") as string;
      this.initialized = true;
      return obj(
        ["protocolVersion", WITH_HANDSHAKE.includes(asked) ? asked : WITH_HANDSHAKE[WITH_HANDSHAKE.length - 1]],
        ["capabilities", this.capabilities()],
        ["serverInfo", this.serverInfo],
      );
    }
    const stateless = this.isStateless(method, params);
    if (stateless) {
      if (method === "server/discover") {
        return obj(
          ["resultType", "complete"],
          ["supportedVersions", SUPPORTED],
          ["capabilities", this.capabilities()],
          ["ttlMs", 0],
          ["cacheScope", "private"],
          ["_meta", obj(["io.modelcontextprotocol/serverInfo", this.serverInfo])],
        );
      }
    } else if (method === "ping") {
      return obj();
    }
    if (method === "tools/list") {
      const tools: Json = [this.tool.definition];
      return stateless
        ? obj(["resultType", "complete"], ["ttlMs", 0], ["cacheScope", "private"], ["tools", tools])
        : obj(["tools", tools]);
    }
    if (method === "tools/call") {
      const name = params.get("name");
      const given = params.get("arguments");
      if (typeof name !== "string" || (given !== undefined && !isObject(given))) {
        throw new ProtocolError(METHOD_NOT_FOUND, method);
      }
      // MCP lists an unknown tool as a protocol error (JSON-RPC -32602), not a tool result.
      if (name !== this.tool.name) {
        throw new ProtocolError(INVALID_PARAMS, `unknown tool ${name}; the only tool is ${this.tool.name}`);
      }
      const answer = this.tool.call(given ?? obj());
      const result = obj(["content", [obj(["type", "text"], ["text", answer.text])]], ["isError", answer.refused]);
      return stateless ? new Map([["resultType", "complete"], ...result]) : result;
    }
    throw new ProtocolError(METHOD_NOT_FOUND, method);
  }

  /**
   * Whether a request is a 2026-07-28 request, which carries its protocol version and the
   * client's capabilities in `_meta`. Throws when the request is neither that nor a request
   * after `initialize`.
   */
  private isStateless(method: string, params: JsonObject): boolean {
    const meta = params.get("_meta");
    const version = get(meta, PROTOCOL_VERSION);
    const capabilities = get(meta, CLIENT_CAPABILITIES);
    if (version === undefined && capabilities === undefined) {
      // An `initialize` that reaches this point did not name a protocol version.
      if ((this.initialized && method !== "initialize") || method === "ping") {
        return false;
      }
      throw new ProtocolError(
        INVALID_PARAMS,
        `request _meta is missing or has malformed required fields: ${PROTOCOL_VERSION}, ${CLIENT_CAPABILITIES}`,
      );
    }
    const malformed: string[] = [];
    if (typeof version !== "string") {
      malformed.push(PROTOCOL_VERSION);
    }
    if (!isObject(capabilities)) {
      malformed.push(CLIENT_CAPABILITIES);
    }
    if (malformed.length > 0) {
      throw new ProtocolError(
        INVALID_PARAMS,
        `request _meta is missing or has malformed required fields: ${malformed.join(", ")}`,
      );
    }
    if (!SUPPORTED.includes(version as string)) {
      throw new ProtocolError(
        UNSUPPORTED_VERSION,
        "Unsupported protocol version",
        obj(["requested", version as string], ["supported", SUPPORTED]),
      );
    }
    return version === STATELESS;
  }
}

/**
 * Serve MCP on stdin and stdout until stdin closes. `ended` is called once, after the last
 * reply.
 */
export function serve(server: Server, ended: () => void): void {
  let waiting = "";
  const answer = (line: string): void => {
    const reply = line.trim() === "" ? null : server.handle(line);
    if (reply !== null) {
      process.stdout.write(`${reply}\n`);
    }
  };
  process.stdout.on("error", () => {
    // The client closed its end. No reply can reach it.
    ended();
    process.exit(0);
  });
  process.stdin.setEncoding("utf8");
  process.stdin.on("data", (chunk: string) => {
    waiting += chunk;
    for (let end = waiting.indexOf("\n"); end !== -1; end = waiting.indexOf("\n")) {
      const line = waiting.slice(0, end);
      waiting = waiting.slice(end + 1);
      answer(line);
    }
  });
  process.stdin.on("end", () => {
    answer(waiting);
    ended();
  });
}
