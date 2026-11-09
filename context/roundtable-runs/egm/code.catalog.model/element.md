# Map element `code.catalog.model`: OpenRouter model selection

This document is one element of the functional map of Roundtable, a program in which several AI agents discuss a user's objective in turns while an evaluator checks each message. The map records what each part of the program must do, what it relies on, and knowledge about it. Paths are relative to the Roundtable folder.

## Properties
```json
{
  "package": "agent host library (reusable; basis for the chassis)",
  "name": "OpenRouter model selection",
  "name_length": 2,
  "role": "SE",
  "uri": "crates/acp-host/src/models.rs"
}
```

## What other parts rely on it for (their wants)
- `code.roster.participant`: goal: Offer the OpenRouter models a participant can use. Function: Lists current OpenRouter model ids. Intent: receive

## What it relies on (its wants)
- `upstream.gateway.llm`: goal: Obtain the current list of selectable models instead of a fixed list. Function: Publishes model identifiers and metadata through GET /api/v1/models. Intent: receive

## Layer `references`
```json
[
  {
    "path": "README.md",
    "sections": [
      "9.4 OpenRouter Support"
    ]
  }
]
```

## Layer `elephant` (the project author's account of this element)
```json
{
  "date": "2026-11-07",
  "design": "Let the chair pick participants by OpenRouter model id from OpenRouter's live catalog, not a fixed list.",
  "sources": [
    "README.md §9.4"
  ],
  "built": "acp-host/src/models.rs reads the catalog; the web page lists the models for OpenRouter seats.",
  "gaps": []
}
```

## The review findings to resolve

Two reviewers who had never seen this project read the description above and the code. Their findings follow. Severity: Blocker means the description says something the code does not do; Major means an important gap; Nit means a small one.

- **GF1** (Major, egm-codebase-details, elephant: built (page lists the models)): The page only offers datalist hints on focus, for openrouter-acp, pi-acp, opencode* (prefixed 'openrouter/') or commands containing 'openrouter' (crates/roundtable-web/assets/index.html:423-434); input is free text, not checked against the catalog; the list is cached once per page load (index.html:429).
- **GF2** (Major, egm-codebase-details, failure modes (missing)): /api/models returns 502 with the error (crates/roundtable-web/src/app.rs:222-228); the page swallows it and shows an empty list (index.html:429 `.catch(() => ({}))`).
- **GF3** (Major, egm-codebase-details, how the selection is used (missing)): The chosen id becomes a generic 'model' session option (crates/roundtable-web/src/tables.rs:124-126) set via set_config; if the harness does not advertise it, only a warning is recorded and the seat joins (crates/roundtable/src/engine.rs:987-990).
- **GF4** (Nit, egm-codebase-details, unstated details): MODELS_URL (crates/acp-host/src/models.rs:6); optional bearer key (models.rs:23-26) from OPENROUTER_API_KEY or POST /api/settings (app.rs:135, 234-241); only id/name/context_length kept (models.rs:9-15); no server caching (app.rs:222-224).
- **GF5** (Nit, egm-codebase-details, properties: uri): uri names only models.rs; the element also relies on the /api/models route (app.rs:146) and the page logic (index.html:423-434).
- **GF6** (Major, egm-comprehension, function / filtering): It does not say whether all catalog models are offered or only those able to drive ACP tool use (participants must call MCP tools).
- **GF7** (Major, egm-comprehension, failure behaviour): No behaviour is given when the catalog fetch or API authentication fails, and the no-fixed-list rule removes the obvious fallback.
- **GF8** (Nit, egm-comprehension, upstream.gateway.llm): Host, authentication and refresh/caching of 'current' models are unstated.
- **GF9** (Nit, egm-comprehension, elephant.built; terms chair, seat): Wants name code.roster.participant as the consumer while built names 'the web page'; chair and seat are undefined.

The code for this part is copied into the `source` folder here, under the same paths as above.
