# Map element `upstream.gateway.llm`: OpenRouter

This document is one element of the functional map of Roundtable, a program in which several AI agents discuss a user's objective in turns while an evaluator checks each message. The map records what each part of the program must do, what it relies on, and knowledge about it. Paths are relative to the Roundtable folder.

## Properties
```json
{
  "name": "OpenRouter",
  "name_length": 2,
  "uri": "https://openrouter.ai/docs/api/api-reference/models/get-models"
}
```

## What other parts rely on it for (their wants)
- `code.adapter.agent`: goal: Run inference for the participant's selected model id. Function: Routes chat completions to the selected provider model. Intent: send_receive
- `code.catalog.model`: goal: Obtain the current list of selectable models instead of a fixed list. Function: Publishes model identifiers and metadata through GET /api/v1/models. Intent: receive

## Layer `references`
```json
[
  {
    "path": "README.md",
    "sections": [
      "9.4 OpenRouter Support",
      "5 JEV"
    ]
  },
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
  "design": "OpenRouter supplies the participant models and JEV.",
  "sources": [
    "README.md §9.4"
  ],
  "built": "Used for the model catalog, for OpenRouter seats on OpenCode, and for JEV's decision route.",
  "gaps": []
}
```

## The review findings to resolve

Two reviewers who had never seen this project read the description above and the code. Their findings follow. Severity: Blocker means the description says something the code does not do; Major means an important gap; Nit means a small one.

- **GF1** (Blocker, egm-codebase-details, wants: code.adapter.agent): 'Routes chat completions to the selected provider model' is false. The adapter goes through the Agent SDK to POST /api/v1/responses (adapters/openrouter-acp/src/models.ts:19-20; adapter.ts:150-161).
- **GF2** (Major, egm-codebase-details, elephant.built): The list of uses leaves out the openrouter-acp adapter, which still runs OpenRouter models and is offered first in the catalog (crates/roundtable-web/src/tables.rs:76-79), even though the document's own wants list it.
- **GF3** (Major, egm-codebase-details, wants: code.catalog.model): Two separate catalog readers, neither described. acp-host's reads one page, sends the key only if one exists, and keeps only id, name and context_length (crates/acp-host/src/models.rs:8-29). The adapter's always sends the key, follows links.next across pages, and keeps only models with tool support on /api/v1/responses (adapters/openrouter-acp/src/models.ts:43-81).
- **GF4** (Major, egm-codebase-details, whole document): The JEV route is not described. It is POST https://openrouter.ai/api/alpha/decisions, an alpha route, with bearer auth, body {model, state, questions} and model ~typesafe/jev-latest (crates/roundtable/src/jev.rs:16-18, 152-155). No key means no JEV call (jev.rs:153).
- **GF5** (Nit, egm-codebase-details, whole document): The adapter reads OPENROUTER_API_KEY from its environment and hides it from commands the model runs (adapters/openrouter-acp/src/adapter.ts:127-136; tools.ts:34). Seats get the key only when share_openrouter_key is set (crates/roundtable-web/src/tables.rs:68-70).
- **GF6** (Major, egm-comprehension, wants vs. elephant): The wants list only the adapter and the catalog; OpenCode seats and JEV's decision route (relied on by upstream.judge.llm) are named as users but not described as functions.
- **GF7** (Major, egm-comprehension, assumed prerequisites): No mention of the API key, credit or rate limits, though run 1 failed on 68 HTTP 402 credit errors.
- **GF8** (Nit, egm-comprehension, properties uri): Links only the models endpoint, not the chat completions or decisions routes.
- **GF9** (Nit, egm-comprehension, wants): Doesn't say that its listed user code.adapter.agent is rarely used.

The code for this part is copied into the `source` folder here, under the same paths as above.
