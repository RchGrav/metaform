# GhostShade: evidence boundaries

The supplied source snapshot contains exactly three files. This limits what can be independently established from the findings.

| File | Evidence |
| --- | --- |
| `source/adapters/openrouter-acp/src/models.ts:19–20` | Identifies the Agent SDK endpoint as `/api/v1/responses`; the request invocation itself is not included. |
| `source/adapters/openrouter-acp/src/models.ts:43–81` | Catalog request always includes bearer authorization, follows `links.next`, filters for tools and the Responses endpoint, deduplicates accepted IDs, returns value/name options, and fails if no options remain. |
| `source/crates/acp-host/src/models.rs:8–29` | One catalog request, optional bearer authorization, deserialization into id/name/context_length, and propagation of request/status/JSON errors. |
| `source/crates/roundtable/src/jev.rs:16–18,125–175` | Default alpha decisions URL and JEV model; configurable public URL/model fields; blank keys treated as absent; missing-key error before sending; authenticated POST containing model/state/questions; HTTP, decoding, missing-answer, and range errors returned. |

Not supplied: `adapter.ts`, `tools.ts`, `tables.rs`, README, integration design, the JEV caller, or run logs. Consequently, SDK invocation details beyond the catalog comment, catalog ordering, seat key forwarding, shell environment filtering, caller fallback behavior, usage frequency, and the alleged 68 HTTP 402 failures are not independently verified here. An assertion repeated in a review finding is not additional source evidence.
