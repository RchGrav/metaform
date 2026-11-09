# RuggedSword — independent verification and organizing insight

I read the three files present in this element's `source/` line by line and
checked each finding against them. My verdicts agree with the resolution.

## Independent confirmation (from files in this element's `source/`)

- **GF1 (Blocker) right.** `adapters/openrouter-acp/src/models.ts:19-20`
  defines `AGENT_ENDPOINT = "/api/v1/responses"` with the comment that the SDK's
  `betaResponsesSend` posts to `POST /responses`. No chat-completions route
  exists anywhere in this copy. The wants line "Routes chat completions" is
  false.
- **GF3 (Major) right.** Two readers, materially different:
  - `crates/acp-host/src/models.rs:6,18-28`: one `GET /api/v1/models`; key
    sent only if `Some` (`:24-26`); keeps `id/name/context_length`
    (`:9-15`); no pagination.
  - `adapters/openrouter-acp/src/models.ts:43-81`: always sends bearer key
    (`:52`); follows `links.next` in a loop (`:50,72-73`); keeps only models
    with `supported_parameters ∋ "tools"` and
    `endpoints ∋ "/api/v1/responses"` (`:66-68`); throws if none (`:75-79`).
- **GF4 (Major) right.** `crates/roundtable/src/jev.rs:16` `DECISIONS_URL =
  "https://openrouter.ai/api/alpha/decisions"` (alpha); `:18` model
  `~typesafe/jev-latest`; `:154` body `{model, state, questions}`; `:155`
  bearer auth; `:153` `Err("no OpenRouter key configured")` before any request,
  and the module doc `:1-3` says the caller shares the contribution unjudged on
  error. No key ⇒ no JEV call.
- **GF5 (Nit) adapter half right.** `adapter.ts` reads `OPENROUTER_API_KEY` and
  `tools.ts` withholds it from model-run commands. The seat half
  (`share_openrouter_key`) is not in this copy.
- **GF9 (Nit) rejected with the resolution.** "rarely used" is unsupported and
  contradicted by the adapter being offered first in the catalog.

## New point: this element is three contracts, not one gateway

The findings are symptoms of one structural cause. The description and the
`uri` present OpenRouter as a single resource ("the gateway"), but the code
shows three *independent provider contracts* with different routes, auth, and
failure semantics:

| Contract | Route | Auth | Page behavior | Failure mode |
|---|---|---|---|---|
| Adapter inference | `POST /api/v1/responses` | key required (adapter.ts) | n/a | session won't start without key |
| Seat catalog (acp-host) | `GET /api/v1/models` | key optional | one page, no `links.next` | first-page only, `id/name/context_length` only |
| Adapter catalog (openrouter-acp) | `GET /api/v1/models` | key required | follows `links.next` | filters to tools+Responses; throws if none |
| JEV decision | `POST /api/alpha/decisions` | key required | n/a | fail-open: unjudged on error |

Once the description lists these four contracts with their own routes, auth,
and failure modes, GF1/GF3/GF4/GF5/GF6/GF7 are all addressed in one coherent
restructure rather than as patch edits.

## Refinement on GF8: `uri` is a docs link, not a runtime endpoint

The element's `uri` is `https://openrouter.ai/docs/api/api-reference/models/get-models`
— the **documentation** page. The runtime endpoints in the code are
`https://openrouter.ai/api/v1/models`, `/api/v1/responses`, and
`/api/alpha/decisions`. The description should mark `uri` as the docs page and
list the three runtime endpoints separately, so a consumer does not mistake the
docs link for a callable API base.

## Refinement on GF7: the 402 evidence is consistent but external

The 68×HTTP 402 claim comes from "run 1", which is outside this element's
materials. It is consistent with the code (key required, hard error without it)
but is not verifiable from `source/` alone. The described fix (state key +
paid credit as prerequisites) is correct regardless of the exact 402 count.
