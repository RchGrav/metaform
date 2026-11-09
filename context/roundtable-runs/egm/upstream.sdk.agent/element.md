# Map element `upstream.sdk.agent`: OpenRouter Agent SDK

This document is one element of the functional map of Roundtable, a program in which several AI agents discuss a user's objective in turns while an evaluator checks each message. The map records what each part of the program must do, what it relies on, and knowledge about it. Paths are relative to the Roundtable folder.

## Properties
```json
{
  "name": "OpenRouter Agent SDK",
  "name_length": 2,
  "uri": "https://openrouter.ai/docs/agent-sdk/overview"
}
```

## What other parts rely on it for (their wants)
- `code.adapter.agent`: goal: Run an OpenRouter-selected model as a full agent with tools and conversation state. Function: Supplies the agent loop, tool execution and conversational state. Intent: receive

## Layer `references`
```json
[
  {
    "path": "Roundtable_ACP_Integration_Design.md",
    "sections": [
      "7.3 OpenRouter models are selected by their published identifiers"
    ]
  }
]
```

## Layer `elephant` (the project author's account of this element)
```json
{
  "date": "2026-11-07",
  "design": "The OpenRouter Agent SDK runs OpenRouter models as agents.",
  "sources": [
    "Roundtable_ACP_Integration_Design.md §7.3"
  ],
  "built": "Used only inside the OpenRouter adapter.",
  "gaps": []
}
```

## The review findings to resolve

Two reviewers who had never seen this project read the description above and the code. Their findings follow. Severity: Blocker means the description says something the code does not do; Major means an important gap; Nit means a small one.

- **GF1** (Major, egm-codebase-details, wants: code.adapter.agent): 'Supplies ... tool execution and conversational state' overstates it. The SDK ships no file or shell tools. The adapter defines all four, and the SDK only checks their input and calls them (adapters/openrouter-acp/src/tools.ts:1-9, 318-456). The conversation state lives in the adapter's memory for each session, reached through a StateAccessor; it is lost on session/close, and session loading is not offered (adapter.ts:144-149, 176, 290-294).
- **GF2** (Major, egm-codebase-details, whole document): Undocumented coupling: the adapter replaces a private SDK method, ModelResult.startTurnBroadcasterExecution, to stop a floating promise from crashing the process, and refuses to start if that method is gone (adapters/openrouter-acp/src/sdk-patch.ts:24-48; adapter.ts:33-36).
- **GF3** (Major, egm-codebase-details, whole document): Exact pins @openrouter/agent 1.0.1 and @openrouter/sdk 0.13.67 (adapters/openrouter-acp/package.json:25-26). The OpenRouter client gets a custom HTTPClient fetcher, and SDK retries are turned off with retryConfig {strategy: 'none'} (adapter.ts:226-232).
- **GF4** (Major, egm-codebase-details, whole document): The SDK calls POST /api/v1/responses, so only models served there with tool support can run (adapters/openrouter-acp/src/models.ts:19-20, 64-71). The adapter converts the SDK's result status into ACP stop reasons, and any other incomplete reason becomes an error (adapter.ts:92-106).
- **GF5** (Nit, egm-codebase-details, elephant.built): 'Used only inside the OpenRouter adapter' is accurate: the only source files importing @openrouter/agent are under adapters/openrouter-acp/src.
- **GF6** (Major, egm-comprehension, elephant): Doesn't say that its only user is rarely used and superseded by OpenCode, so a reader would assume it is on the main path.
- **GF7** (Major, egm-comprehension, wants): Promises 'tool execution' while the adapter refuses tool servers and limits file tools to the session folder; the SDK's own tools and Roundtable's tools are not told apart.
- **GF8** (Nit, egm-comprehension, properties): No package name, language or version, so the dependency cannot be found in the adapter's manifest.
- **GF9** (Nit, egm-comprehension, layers): No investigations or decisions about suitability, and the empty gaps list doesn't say whether anything was checked.

The code for this part is copied into the `source` folder here, under the same paths as above.
