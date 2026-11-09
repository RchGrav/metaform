# openrouter-acp

An ACP (Agent Client Protocol) agent that runs any OpenRouter model through the
OpenRouter Agent SDK (`@openrouter/agent`). It implements path 2 of
`Roundtable_ACP_Integration_Design.md` §7.3: the SDK supplies the agent loop,
the tool dispatch and the conversation state; this adapter is the ACP agent side
around it. One adapter process serves any number of sessions, each on any
OpenRouter model id.

## Launch

```sh
OPENROUTER_API_KEY=... node roundtable/adapters/openrouter-acp/dist/index.js
```

or `npx ./roundtable/adapters/openrouter-acp`, from the repository root. The agent speaks ACP v1
as newline-delimited JSON-RPC on stdin/stdout. Diagnostics go to stderr.

Build and test (Node.js 22.18 or later):

```sh
npm install      # also builds dist/
npm test         # builds, type-checks, runs test/*.test.ts (no network, no key)
```

## API key

The adapter reads `OPENROUTER_API_KEY` from its environment. If the variable is
missing or empty, `session/new` (and `session/prompt`) fail with JSON-RPC error
`-32000` "Authentication required: OPENROUTER_API_KEY is not set ...".
`initialize` works without a key. Commands that the model runs do not get the
key in their environment.

## ACP surface (v1)

| Method | Behaviour |
|---|---|
| `initialize` | Returns protocol version 1, `loadSession: false`, prompt capabilities all `false` (text and resource links only), MCP `http`/`sse` `false`, `sessionCapabilities.close`, no auth methods. |
| `session/new` | `cwd` must be an absolute directory. It becomes the session root. The adapter reads OpenRouter's catalog (`GET https://openrouter.ai/api/v1/models`) and returns one config option, `model` (category `model`). The option lists every catalog model that supports tool calling and is served on `/api/v1/responses`, the endpoint the Agent SDK uses. The session starts on `openrouter/auto`. |
| `session/set_config_option` | `configId: "model"`, `value`: one of the listed model ids. It applies from the next prompt. |
| `session/prompt` | Runs the Agent SDK loop with the session's conversation state. Assistant text arrives as `agent_message_chunk` updates. Tool use arrives as `tool_call` (pending), then `tool_call_update` (in_progress, then completed or failed). The response's `stopReason` is `end_turn`, `max_tokens`, `refusal` or `cancelled`. Provider and loop errors come back as JSON-RPC errors. |
| `session/cancel` | Aborts the running turn: the model request, the tool executions and any command process group. The prompt returns `cancelled`, and the session stays usable. |
| `session/close` | Cancels any running turn and removes the session. |

Not implemented, and not advertised: `session/load`, `session/resume`,
`session/list`, `authenticate`, `additionalDirectories`, client-supplied MCP
servers (`session/new` rejects a non-empty `mcpServers`), image, audio and
embedded-resource prompt content, and ACP v2.

## Tools

The Agent SDK has no built-in file or shell tools. The adapter gives the model
four tools, defined with the SDK's `tool()` helper:

| Tool | ACP kind | Permission |
|---|---|---|
| `read_file` `{path}` | read | no |
| `list_directory` `{path?}` | read | no |
| `write_file` `{path, content}` (creates parent directories) | edit, with a diff | `session/request_permission` |
| `run_command` `{command}` (`/bin/sh -c`, stdin closed, cwd = session root) | execute | `session/request_permission` |

Permission options are `allow_once` and `reject_once`. If the client rejects or
cancels, the tool does not run, its update ends as `failed`, and the model gets
an error result.

File paths resolve against the session root. A path that leaves the root, either
directly or through a symbolic link, fails before any permission request.
Commands start in the session root but are not sandboxed. A shell command can
reach anything the adapter's user can reach, so the permission request is the
control for commands. There are no timeouts on model requests, tools or
commands. The SDK's automatic retry of failed requests is turned off, so errors
reach the client.
