## MCP agent context: July 2026 reference

This is the native role's authored July 2026 reference snapshot. Determine the actual installed adapter and negotiated protocol before applying version-specific claims. Verify exact published behavior from the relevant official source when it matters.

Protocol baseline: **2026-07-28**. MCP Apps extension baseline: **2026-01-26**, as published in the official repository at the end of July 2026. These are separate version identifiers.

### Context flow

1. A server publishes server guidance, tool descriptors, prompt templates and resources.
2. An MCP client retrieves the relevant surfaces.
3. The host assembles model messages, tool definitions and selected content.
4. The model chooses tools and supplies arguments; the client sends `tools/call`.
5. The server returns results; the host supplies relevant result content to the model.
6. An MCP App can send messages or update its model context through the host.

MCP standardizes the server/client payloads. It does **not** define a universal final system prompt, message ordering or host serialization. Exact server-authored wording is recoverable from source or responses; exact final model input requires a host trace.

### Author instructions in the correct surface

| Intended content | Surface | Delivery |
|---|---|---|
| Server-wide operating guidance | `server/discover` result `instructions` | Host decides model placement; no prescribed message role. |
| Tool selection, sequencing and technical format | `tools/list` tool `description` | Host exposes the descriptor as a model tool. |
| Argument meaning, units and structure | `inputSchema` and property descriptions | SDK emits JSON Schema; host translates to its tool format. |
| User-selectable reusable request | `prompts/list`, then `prompts/get` | Returns `user`/`assistant` messages, not a system-message role. |
| Retrieved document/data | `resources/read`, embedded resources or tool results | Host selects content for context. A resource listing is not a read. |
| Outcome and actionable feedback | `tools/call` result `content` / `structuredContent` | Host presents the result to the model. |
| UI-originated chat request | `ui/message` / `app.sendMessage` | Host adds a conversation message and can follow up. |
| Live UI state for future turns | `ui/update-model-context` / `app.updateModelContext` | Replaces previous context from that view; host may defer and use only the latest update. |

A README prompt, source comment or `AGENTS.md` is not automatically delivered by MCP. Tool descriptions can contain substantial instructions without exposing a `prompts/get` template.

### July request/response contract

- The core `initialize` / `notifications/initialized` handshake and protocol sessions were removed. Use per-request metadata; servers must implement `server/discover`, although clients need not call it before every operation.
- Every request includes `params._meta["io.modelcontextprotocol/protocolVersion"]` and `params._meta["io.modelcontextprotocol/clientCapabilities"]`. `clientInfo` is optional and SHOULD be included.
- Results include `resultType: "complete"` or `"input_required"`. An absent field from an earlier-version server is interpreted as `"complete"`.
- Cacheable results include `ttlMs` and `cacheScope`; discovery is cacheable. Keep unchanged tool catalogs in deterministic order.
- Streamable HTTP POST requests carry `Mcp-Method` and, for named methods, `Mcp-Name`; protocol version is conveyed using the specified HTTP header and request metadata.
- Cross-call application state uses explicit handles returned by a tool and supplied to subsequent tools. It is not implicit connection/session state.
- Server-requested client input uses **multi round-trip requests (MRTR)**: return `input_required` with `inputRequests`; the client retries the original method with `inputResponses`, any opaque `requestState`, and a new JSON-RPC ID.
- Change notification streams use `subscriptions/listen`, replacing the old GET stream and resource subscription RPCs.

### Deprecated and replaced approaches

Do not present older sample mechanics as the current approach.

| Older mechanism | Status | Migration |
|---|---|---|
| Core initialization handshake / `Mcp-Session-Id` | Removed in the July core | Per-request metadata, discovery and explicit application handles. |
| Direct server-initiated requests on an open connection | Replaced; unsupported in July | MRTR input requests within a result, followed by client retry. |
| Roots | **Deprecated in 2026-07-28** | Pass paths through tool arguments, resource URIs or configuration. |
| Sampling | **Deprecated in 2026-07-28** | Integrate directly with LLM provider APIs for new designs. |
| Logging feature | **Deprecated in 2026-07-28** | `stderr` for stdio; OpenTelemetry for observability. |
| Sampling `includeContext: "thisServer"` / `"allServers"` | **Deprecated since 2025-11-25** | Omit or use `"none"` while maintaining legacy Sampling. |
| Legacy HTTP+SSE transport | **Deprecated since 2025-03-26** | Streamable HTTP. SSE response framing within it remains valid. |
| Flat `_meta["ui/resourceUri"]` | **Deprecated by MCP Apps** | Nested `_meta.ui.resourceUri`. |
| OAuth Dynamic Client Registration | **Deprecated in 2026-07-28** | Client ID Metadata Documents. |

Deprecated features remain available during their migration window. Roots, Sampling, Logging and Dynamic Client Registration become eligible for removal in the first revision released on or after **2027-07-28**. Core breaking changes are separate from this deprecation window.

`prompts/get`, tool descriptions, resources and MCP Apps remain active. The Apps `ui/initialize` handshake is a separate view/host leg and was **not** removed with core initialization.

### MCP Apps routing

- Declare extension `io.modelcontextprotocol/ui` and link a tool using `_meta.ui.resourceUri` to a `ui://` resource with MIME type `text/html;profile=mcp-app`.
- `_meta.ui.visibility` defaults to `["model", "app"]`. `["app"]` hides a server tool from the model while retaining app access. `["model"]` excludes app calls.
- The host fetches and renders the UI and forwards tool inputs/results to it. UI HTML is not automatically model prompt text.
- Tool-result `content` and `structuredContent` are model-facing data. Result `_meta` carries UI/host metadata and is not intended for model context.
- `app.registerTool` exposes live view tools through a supporting host; these are separate from server tools.
- UI messages and replacement context travel through the host. Logs do not automatically update model context.

### Exact sample wording

The official Map server's `show-map` description is:

```text
Display an interactive world map zoomed to a specific bounding box. Use the GeoCode tool to find the bounding box of a location. The widget is interactive and exposes tools for navigation (fly to locations) and querying the current view.
```

The registered lookup tool is named `geocode`; “GeoCode” above preserves the source wording.

Everything's `simple-prompt` returns `role: "user"` with:

```text
This is a simple prompt without arguments.
```

Everything's `args-prompt` renders this source template:

```typescript
`What's weather in ${location}?`
```

Everything's `completable-prompt` renders:

```typescript
`Please promote ${name} to the head of the ${department} team.`
```

The **deprecated Sampling demonstration** requests this system prompt:

```text
You are a helpful test server.
```

And this user message template:

```typescript
`Resource ${name} context: ${prompt}`
```

The client may modify or omit the requested sampling system prompt. This is a separate generation, not the main agent's system prompt.

### Sources and scope

The companion PDF catalogs all seven official reference servers and all 26 MCP Apps example directories at the July cutoff, with exact descriptions, argument definitions, prompt callbacks and app feedback. It embeds UTF-8 context data and original source excerpts.

- [July specification](https://modelcontextprotocol.io/specification/2026-07-28)
- [July changelog](https://modelcontextprotocol.io/specification/2026-07-28/changelog)
- [Deprecated features](https://modelcontextprotocol.io/specification/2026-07-28/deprecated)
- [Discovery](https://modelcontextprotocol.io/specification/2026-07-28/server/discover)
- [MRTR](https://modelcontextprotocol.io/specification/2026-07-28/basic/patterns/mrtr)
- [Reference servers, pinned July source](https://github.com/modelcontextprotocol/servers/tree/76d64c822f5125032f89eb71dbdb94e42b434821)
- [MCP Apps, pinned July source](https://github.com/modelcontextprotocol/ext-apps/tree/4e4886c5ff7125f5332bd29685e94076caeaac24)

This reference describes published surfaces, not private host prompts or an observed production-agent transcript.

### The full reference

The complete reference, 99 pages, catalogs all seven official reference servers and all 26 MCP Apps example directories at the July cutoff, with exact descriptions, argument definitions, prompt callbacks, app feedback, wire examples and a migration map. Read it when a question needs the exact wording or payload of a sample:

- `docs/reference/mcp-agent-context-reference-july-2026.pdf`, the reference itself. Its embedded `source-excerpts.zip` holds the original source excerpts; extract it with `pdfdetach -saveall`.
- `docs/reference/mcp-agent-context-july-2026/context-corpus.json`, the reference's embedded UTF-8 context data, searchable: `baseline`, `source_revisions`, `records`, `app_feedback`, `server_instructions`, `fetch_prompt_source` and `sampling_sources`.
