# Map element `code.adapter.agent`: OpenRouter ACP adapter

This document is one element of the functional map of Roundtable, a program in which several AI agents discuss a user's objective in turns while an evaluator checks each message. The map records what each part of the program must do, what it relies on, and knowledge about it. Paths are relative to the Roundtable folder.

## Properties
```json
{
  "package": "agent host library: separate ACP agent binary (reusable)",
  "name": "OpenRouter ACP adapter",
  "name_length": 2,
  "role": "SE",
  "uri": "Roundtable_ACP_Integration_Design.md#73-openrouter-models-are-selected-by-their-published-identifiers"
}
```

## What other parts rely on it for (their wants)
- `code.client.agent`: goal: Talk to OpenRouter-model participants through the same ACP lifecycle as every other harness. Function: Serves the ACP agent side for any OpenRouter model id. Intent: send_receive

## What it relies on (its wants)
- `upstream.gateway.llm`: goal: Run inference for the participant's selected model id. Function: Routes chat completions to the selected provider model. Intent: send_receive
- `upstream.sdk.agent`: goal: Run an OpenRouter-selected model as a full agent with tools and conversation state. Function: Supplies the agent loop, tool execution and conversational state. Intent: receive

## Layer `references`
```json
[
  {
    "path": "README.md",
    "sections": [
      "9.4 OpenRouter Support"
    ]
  },
  {
    "path": "Roundtable_ACP_Integration_Design.md",
    "sections": [
      "7.3"
    ]
  }
]
```

## Layer `investigations`
```json
[
  {
    "topic": "build or reuse",
    "note": "Two routes run OpenRouter models as ACP participants: Pi + pi-acp (existing), or this adapter around the OpenRouter Agent SDK (to be built; one adapter serves every model id). The design lists both as useful. Which to build first is not yet decided."
  }
]
```

## Layer `archaeology`
```json
[
  {
    "finding": "Python called OpenRouter models directly through chat completions, outside ACP, so they did not share the ACP session lifecycle.",
    "path": "archaeology/src/metaform/modules/roundtables/roundtable/openrouter.py"
  }
]
```

## Layer `elephant` (the project author's account of this element)
```json
{
  "date": "2026-11-07",
  "design": "Run OpenRouter models as Roundtable participants through ACP, using the OpenRouter Agent SDK behind an ACP adapter.",
  "sources": [
    "Roundtable_ACP_Integration_Design.md §7.3",
    "README.md §9.4"
  ],
  "built": "adapters/openrouter-acp wraps the OpenRouter Agent SDK as an ACP agent. It refuses tool servers and keeps its file tools inside the session folder.",
  "gaps": [
    "Its seats get no Roundtable tools, because it refuses tool servers.",
    "The owner moved OpenRouter models to OpenCode: \"not ori .. we said opencode\" (2026-11-06), so this adapter is rarely used."
  ]
}
```

## The review findings to resolve

Two reviewers who had never seen this project read the description above and the code. Their findings follow. Severity: Blocker means the description says something the code does not do; Major means an important gap; Nit means a small one.

- **GF1** (Blocker, egm-codebase-details, investigations: build or reuse): 'This adapter around the OpenRouter Agent SDK (to be built ...). Which to build first is not yet decided' is false. The adapter exists (adapters/openrouter-acp/src/adapter.ts) and is listed first in the harness catalog (crates/roundtable-web/src/tables.rs:76-99). This also contradicts the document's own elephant.built.
- **GF2** (Blocker, egm-codebase-details, wants (relied on by code.client.agent)): 'Serves the ACP agent side for any OpenRouter model id' is false. Only catalog models that list 'tools' and are served on /api/v1/responses are offered (adapters/openrouter-acp/src/models.ts:36-71). set_config_option rejects any other value (adapter.ts:245-251). session/new fails if openrouter/auto is missing from the catalog (adapter.ts:214-219).
- **GF3** (Blocker, egm-codebase-details, its wants: upstream.gateway.llm): 'Routes chat completions': the SDK's callModel calls the Responses endpoint, POST /api/v1/responses (adapters/openrouter-acp/src/models.ts:19-20; adapter.ts:150-161).
- **GF4** (Major, egm-codebase-details, elephant.built): 'Keeps its file tools inside the session folder' holds for read_file, list_directory and write_file (tools.ts:113-125, 135-146, 411-415). It leaves out that run_command runs `/bin/sh -c` in the session folder with no path confinement and no time limit. Only OPENROUTER_API_KEY is removed from its environment, and cancelling kills the whole process group (tools.ts:248-264, 277-287, 431-453). write_file and run_command ask for permission first (tools.ts:204-229).
- **GF5** (Major, egm-codebase-details, whole document): The ACP surface and its limits are undocumented: ACP v1 (adapter.ts:3); loadSession false; no MCP over HTTP or SSE (adapter.ts:173-183); prompts accept only text and resource_link (adapter.ts:76-90); one turn at a time per session (adapter.ts:259-261); OPENROUTER_API_KEY required (adapter.ts:127-136); additionalDirectories refused (adapter.ts:196-198); the SDK's hour-long retry is turned off (adapter.ts:229-231); a new session starts on openrouter/auto (models.ts:17).
- **GF6** (Major, egm-comprehension, investigations vs. elephant): The investigation says the adapter is 'to be built' and the route is undecided between Pi and this adapter. The elephant layer says it is built and the owner chose OpenCode. The stale investigation leaves the element's status unclear.
- **GF7** (Major, egm-comprehension, elephant gaps): 'Refuses tool servers' and 'Roundtable tools' are undefined; a reader can't tell what is refused, how, or what seats lose.
- **GF8** (Major, egm-comprehension, elephant gaps): The owner quote uses the undefined name 'ori'. 'Rarely used' is vague: is it still selectable, by whom, and is it kept or retired?
- **GF9** (Nit, egm-comprehension, wants): Wants both the gateway (chat completions) and the SDK (agent loop) without saying whether OpenRouter is called directly or only through the SDK.
- **GF10** (Nit, egm-comprehension, properties): 'agent host library' and role 'SE' are undefined.

The code for this part is copied into the `source` folder here, under the same paths as above.
