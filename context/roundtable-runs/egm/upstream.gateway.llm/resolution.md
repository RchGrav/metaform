# OpenRouter review resolutions

Prepared by GhostShade from `element.md` and the supplied source snapshot. These are decisions and proposed changes; no source changes are made. Source paths below are relative to `source/`.

Three source files were supplied in this element's `source/`: the two catalog readers and `jev.rs`. The sibling element `code.adapter.agent` additionally ships `adapter.ts` and `tools.ts` at `../code.adapter.agent/source/adapters/openrouter-acp/src/` (verified present), so GF1/GF5 claims citing those two files ARE re-verifiable from the workspace. Only `tables.rs` is absent from all copies, and only claims about historical runs lack evidence. The evidence inventory is in `GhostShade-evidence.md`.

# Merge addendum (UnifiedRazor, second/third rounds)

The header caveat in the merged draft ("`adapter.ts`/`tools.ts` cannot be re-verified") is outdated. They are in this workspace: the sibling element `code.adapter.agent` ships them at `../code.adapter.agent/source/adapters/openrouter-acp/src/` (verified: `adapter.ts`, `tools.ts`, `models.ts`, etc.). Verified directly there:
- `adapter.ts:127-136` — throws `authRequired` / "OPENROUTER_API_KEY is not set in the environment of the openrouter-acp adapter process" (was GF5, adapter half — now confirmed);
- `tools.ts:34` — `WITHHELD_ENV = ["OPENROUTER_API_KEY"]`, stripped at `:256-257` before spawning `/bin/sh` (GF5, key-withholding — now confirmed);
- `adapter.ts:226-231` — `retryConfig: { strategy: "none" }` (new confirmed fact: the adapter does not retry).
Only `tables.rs` is in neither this copy nor the sibling's, so only its two citations (GF2 `:76-79`, GF5 `:68-70`) keep the "needs confirmation" flag. The scope note (line 5) and GF5 (line 58) have since been corrected to reflect that `adapter.ts`/`tools.ts` ARE verifiable; `GhostShade-evidence.md:12` still lists them as "not supplied" and is the one remaining stale artifact — it should be read as describing only this element's `source/`, not the whole workspace.

## GF4 consequence added (fail-open)
Per `jev.rs:1-3` ("the caller shares the contribution unjudged on error"), the `Err("no OpenRouter key configured")` at `jev.rs:153` silently disables JEV's veto rather than aborting the round. The description should record this fail-open consequence of a missing key, not just the missing call.

## GF9 rejection
Corroborated from two directions: the sibling element's own report that the adapter is listed first in the harness catalog, and `models.ts:3-5` ("every time a session is created"). "Rarely used" has no telemetry support; per-session selectability is the verifiable statement.

## GF1 — Accept the endpoint correction; change the description

The adapter catalog explicitly identifies the Agent SDK's endpoint as `/api/v1/responses` and admits models only when their advertised endpoints include that value (`adapters/openrouter-acp/src/models.ts:19–20,64–68`). Describing this as “chat completions” is ambiguous and can incorrectly imply the Chat Completions API. The actual SDK invocation cited by the reviewer is absent from this snapshot, but the supplied endpoint contract supports the correction.

Replace the adapter want's function with: **“Runs inference for the selected published OpenRouter model identifier; the openrouter-acp Agent SDK integration uses the Responses API (`POST /api/v1/responses`).”** Keep other adapter implementations' routes separate unless verified. Do not switch the code to Chat Completions to match the wording: no requirement or defect justifies that change. The mismatch is in the description, rather than proof that inference is unimplemented.

## GF2 — Accept the missing integration; qualify the ordering claim

The built account names the catalog, OpenCode seats, and JEV, but omits openrouter-acp. Its supplied catalog implementation provides direct evidence of that integration. Add **“the openrouter-acp integration, which obtains session model options from OpenRouter and selects models compatible with tools and Responses”** to `elephant.built`.

The assertion that this adapter is offered first depends on the missing `crates/roundtable-web/src/tables.rs`; it is not independently established. Ordering is not needed to correct the omission and should not be added as an enduring service responsibility. No source change is warranted by the omission alone.

## GF3 — Accept; describe both catalog consumers and their different contracts

Both readers call `GET https://openrouter.ai/api/v1/models`, but their outputs and request behavior differ:

| Consumer | Supplied behavior |
| --- | --- |
| `crates/acp-host/src/models.rs:8–29` | Makes one request, adds bearer authorization only when passed a key, and returns `id`, `name`, and optional `context_length`. No pagination or capability filter is implemented. |
| `adapters/openrouter-acp/src/models.ts:43–81` | Sends bearer authorization using its required key argument, follows `links.next`, filters for `tools` and `/api/v1/responses`, deduplicates accepted IDs, and returns model value/name choices. Throws when no compatible options remain. |

Expand the catalog description to distinguish the general listing from adapter session choices. Attribute filtering and pagination to the callers, rather than to OpenRouter itself. A published identifier in the host listing is not by itself a guarantee of compatibility with the adapter.

No code change follows automatically: these consumers can legitimately need different lists. If the intended requirement is that the host listing always equals the adapter's runnable choices, that requirement must be made explicit before aligning their implementations. Similarly, the one-request reader is not proven broken without evidence that pagination is required for its use.

## GF4 — Accept; document the separate JEV contract

`crates/roundtable/src/jev.rs:16–18,133–175` establishes the default route `POST https://openrouter.ai/api/alpha/decisions`, default model `~typesafe/jev-latest`, bearer authentication, and JSON body `{model, state, questions}`. URL and model are public fields initialized to those defaults, so the description should not call them immutable.

Add this route as a distinct dependency for JEV evaluation. Describe its named numeric answers: `noul` values must be within 0–1, and scores within their question's criteria range. Missing or blank keys prevent an HTTP call and produce an error; HTTP failures, unreadable answers, missing answers, and out-of-range values also produce errors. Label the configured default endpoint as alpha, as its path indicates.

The file's module comment says callers share contributions unjudged on error, but the caller is absent. Attribute that fallback to the caller and verify it there before stating it as observed end-to-end behavior. No JEV implementation change is required by this documentation omission.

## GF5 — Partly supported; accept credential documentation, reserve the specific claims

The supplied code proves that the adapter catalog sends a bearer token (`models.ts:45–52`) and JEV requires a nonblank configured key (`jev.rs:133–155`). The host catalog can request the listing without a key (`models.rs:17–27`). Document these distinctions instead of stating that every OpenRouter operation requires a configured key.

The claim that a seat key arrives only when `share_openrouter_key` is enabled cites `tables.rs`, which is absent from all copies; it remains unverified, not disproved, and should be confirmed before being written as fact. The claims that the adapter reads `OPENROUTER_API_KEY` (`adapter.ts:127-136`, `authRequired`) and removes it from model-run commands (`tools.ts:34`, `WITHHELD_ENV`, applied at `:256-257`) ARE confirmed from the sibling element's source (see merge addendum line 9-12), so they may be documented as verified — subject to verifying that the sibling file matches the deployed adapter build. If confirmed, describe the environment variable, opt-in forwarding, and command-environment filtering as separate responsibilities of the integration. Do not infer broad credential isolation from one environment filter. No source defect is established here.

## GF6 — Accept the missing functional dependency; avoid inventing a consumer boundary

The account says OpenRouter supplies JEV, yet the wants contain only participant inference and catalog retrieval. JEV's concrete dependency is confirmed by `jev.rs:152–175`. Add a want for `upstream.judge.llm` describing authenticated structured decisions over state and named questions, using the contract in GF4.

Also make OpenCode-backed participant inference explicit, consistent with the existing built account, while noting its implementation is not supplied here. If `code.adapter.agent` already encompasses OpenCode seats, expand that want rather than inventing a duplicate map element. These edits explain which consumer needs which operation; they do not require changes to working inference code.

## GF7 — Accept the prerequisite gap; do not treat the run statistic as verified

Add operation-specific credential prerequisites from GF5 and explain that external inference and decisions depend on account funding or allowances and service limits applicable to the chosen route/model. Catalog availability does not demonstrate that a later inference or evaluation request will succeed. Avoid fixed balances, rates, or a universal paid-credit requirement without authoritative evidence.

The alleged “68 HTTP 402 credit errors” in run 1 is not present in the supplied files. Retain it only as a reviewer-reported observation until run logs establish the count, route, response details, and impact. The snapshot shows JEV returning non-success statuses as errors (`jev.rs:158–159`), but does not establish credit exhaustion detection, retry behavior in callers, or the cause of that run's failures. Do not prescribe retries or billing-handling code on that evidence alone. Exact current provider limits would require separate verification.

## GF8 — Partly accept as reference completeness; correct the proposed endpoint

The existing models URI is appropriate for the catalog and is not false merely because it is the sole link. However, the expanded description should provide references for each distinct API dependency: Models, Responses, and the alpha Decisions route. In particular, GF1 establishes that Responses is the relevant adapter API; adding only a Chat Completions reference would perpetuate the mismatch. Retain the canonical models URI if the map schema allows only one property URI and add other references in a supported description/reference section. Verify documentation destinations before inserting them; no new documentation URLs are asserted here. No source change is needed.

## GF9 — Reject as a required correction

Nothing supplied establishes that `code.adapter.agent` is rarely used. Being offered first, even if confirmed, would not establish frequency of use. A wants list describes a dependency's responsibility, not its popularity; a rarely selected integration still needs correct behavior.

Keep the adapter want. If usage frequency becomes relevant to a maintenance decision, record it separately with a time period and telemetry or other evidence. Do not label the adapter rare or remove its contract on the basis of this finding.

## Resulting scope

The supported resolutions require a clearer map description: distinguish catalog consumers, identify Responses-based participant inference, describe JEV's authenticated Decisions API, and record operation-specific prerequisites. The findings do not establish a source defect requiring implementation changes. Claims dependent on omitted files or run logs remain explicitly unverified; no implementation changes or runtime tests were performed for this document-only task.
