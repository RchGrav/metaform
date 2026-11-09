# CanineMantis — evidence notes for upstream.gateway.llm review

Verified against the copies in `source/` and `../code.adapter.agent/source/`.

- GF1: `models.ts:20` `AGENT_ENDPOINT = "/api/v1/responses"`; `adapter.ts:150-161` go through
  `callModel(session.openrouter, …)`. No chat-completions request exists in this element.
- GF2: the element whose review is `code.adapter.agent` says (GF1 of that element) the adapter is
  "listed first in the harness catalog (crates/roundtable-web/src/tables.rs:76-99)". That
  contradicts "leaves out the openrouter-acp adapter".
- GF3: `acp-host/models.rs:18-28` single GET, optional key, keeps `id/name/context_length`, no
  `links.next`; `openrouter-acp/models.ts:43-81` requires key, follows `links.next`, filters by
  `supported_parameters ∋ tools` and `endpoints ∋ /api/v1/responses`.
- GF4: `jev.rs:16` `DECISIONS_URL = https://openrouter.ai/api/alpha/decisions`; `:18`
  `~typesafe/jev-latest`; `:153` `Err("no OpenRouter key configured")`; body at `:154`.
- GF5: `adapter.ts:127-136` throws `authRequired` without `OPENROUTER_API_KEY`; `tools.ts:34`
  `WITHHELD_ENV = ["OPENROUTER_API_KEY"]`, applied at `:256-257`. `tables.rs` is not in this
  element's `source/` copy, so the `share_openrouter_key`/`:68-70` claim is unverifiable here.
- GF9: no call-count data in this run; "rarely used" is an inference from GF2, not a measurement.
