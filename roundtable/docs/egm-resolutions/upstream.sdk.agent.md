# OpenRouter Agent SDK — finding resolutions

Participant: OminousSiege. Assessed against `element.md` and the six supplied files under `source/adapters/openrouter-acp/`. Source citations below are relative to `source/`. These are decisions and proposed changes; the source and original element have not been changed.

## GF1 — Accept the responsibility gap; qualify the wording

The SDK provides the agent loop and dispatches adapter-supplied tools. That is a legitimate form of “tool execution,” but the current description fails to identify who implements the actual operations. `src/tools.ts:3–9,318–456` explicitly defines `read_file`, `list_directory`, `write_file`, and `run_command` using the SDK helper. The SDK is therefore more than an input checker, but this integration does not obtain its filesystem and shell implementations from it.

Likewise, conversational continuity exists across prompts in a live session: `src/adapter.ts:144–159` supplies a `StateAccessor` whose load/save functions access `session.state`. Storage belongs to the adapter's in-memory session map (`119,221–235`); `loadSession: false` (`176`) and deletion on close (`290–294`) mean there is no supported restoration after close or process exit.

**Change:** Rewrite the want as: “Supplies the model/tool agent loop, validates and dispatches adapter-defined tools, and uses an adapter-provided StateAccessor for conversation continuity within a live session.” Document that the adapter owns tool implementations and nonpersistent state. No persistence implementation is required unless restoration becomes an explicit requirement. The package-wide claim that no file/shell tools ship with the SDK is stated in a local comment; the installed SDK itself was not supplied for independent inspection.

## GF2 — Accept

`src/sdk-patch.ts:24–48` replaces `ModelResult.prototype.startTurnBroadcasterExecution`, attaches a rejection handler to the execution promise, and throws if the method is absent. `src/adapter.ts:33–36` invokes it during module initialization, before the adapter can start. The patch comment describes a duplicate rejection escaping when the stream consumer fails or is cancelled; the consumer is intended to preserve the actual turn error. This is a concrete dependency on private SDK behavior, not an optional fallback.

**Change:** Add this workaround and its startup failure condition to the description's integration constraints/gaps. Record that an SDK upgrade must reassess the private method and error-delivery behavior. Keep the current guard until a verified upstream fix permits removing the patch. Cancellation and broken-stream checks should establish that a failed turn reports its error without terminating other sessions; the referenced tests are not included in this snapshot, so their passage is not established here. Nothing in this finding alone justifies removing the protective patch now.

## GF3 — Accept the facts and documentation gap

`package.json:25–26` exactly pins `@openrouter/agent` to `1.0.1` and `@openrouter/sdk` to `0.13.67`. `src/adapter.ts:226–232` creates the client with an `HTTPClient` delegating to the injected `options.fetch` and explicitly sets `retryConfig: { strategy: "none" }`. The entry point supplies `globalThis.fetch` (`src/index.ts:9`), so “custom fetcher” means an injection/wrapping point, not necessarily a different production transport. Catalog requests use the same injected fetch directly (`src/adapter.ts:209`).

**Change:** Document the pinned pair, transport injection, and disabled client retries. Explain that errors surface to the ACP caller instead of waiting for SDK retry backoff, as the local comment intends. Pins and disabled retries are deliberate integration choices, not defects requiring an upgrade or restored retries. Do not generalize this setting to every possible provider-side or agent-loop retry.

## GF4 — Accept, with scope qualification

The integration explicitly assumes the Responses endpoint (`src/models.ts:19–20`) and only advertises catalog entries containing both `supported_parameters: "tools"` and endpoint `/api/v1/responses` (`64–70`). It does not accept every published model identifier. Session creation also requires `openrouter/auto` to survive this filtering (`src/adapter.ts:214–218`), and configuration changes must choose an offered model (`245–250`). These are necessary advertised capabilities, not proof that every matching model will succeed at runtime. The endpoint actually called inside the upstream SDK is described by a source comment; its implementation is outside this snapshot.

The stop-reason statement is also correct: `src/adapter.ts:92–105` maps incomplete `max_output_tokens` to `max_tokens`, incomplete `content_filter` to `refusal`, and unknown or absent incomplete reasons to an ACP internal error. Otherwise it detects refusal content or returns `end_turn`; cancellation is handled separately (`270–273`).

**Change:** Document model eligibility, the initial-model requirement, and these outcome mappings. Replace “runs any OpenRouter model” in `package.json:5` with “runs eligible OpenRouter models supporting tools on the Responses endpoint.” Retain explicit errors for unknown incomplete reasons; mapping them to successful completion would hide an unresolved result. No broader model support or changed error policy is established as a requirement.

## GF5 — Accept as confirmation, not a defect

All supplied imports of `@openrouter/agent` occur in `src/adapter.ts`, `src/tools.ts`, and `src/sdk-patch.ts` under the OpenRouter adapter. This supports “Used only inside the OpenRouter adapter” for the supplied source.

**Change:** None required. Retain the statement. Because the snapshot contains only this adapter, it does not independently prove the absence of imports elsewhere in the full project.

## GF6 — Not established; reject the proposed factual assertion

No supplied file mentions OpenCode, usage frequency, deprecation, or a replacement decision. “Used only inside the OpenRouter adapter” identifies a consumer, not how often that consumer runs. The existing description also does not explicitly claim this adapter is the main path. Adding “rarely used and superseded by OpenCode” would substitute unsupported operational history for an omission.

**Change:** Do not add that claim on this evidence. If a maintained architecture record, routing configuration, or author decision establishes replacement status, cite it and update the lifecycle description then. The unavailable referenced design section cannot be assumed to provide that evidence.

## GF7 — Accept the missing boundary; reject the implication that dispatch is absent

The adapter genuinely executes its four local tools through the SDK. It also explicitly rejects any client-supplied MCP servers (`src/adapter.ts:190–194`), and the file tools use `resolveInRoot` path checks (`src/tools.ts:113–124,336,363,399,413`). These restrictions belong to the adapter, not an established limitation of the upstream SDK. GF1 and GF7 describe overlapping ownership/documentation issues.

**Change:** Name the four adapter tools, MCP rejection, file-path restrictions, and adapter-managed ACP lifecycle/permissions. Reads and listings do not request permission; writes and commands do (`src/tools.ts:333,360,396,443`; permission handling at `204–229`). State explicitly that `run_command` starts `/bin/sh -c` with the session directory as its working directory (`254–263,448`): that does not sandbox shell filesystem access. Avoid describing every tool as confined to the session folder, or the file path checks as a comprehensive process sandbox. Adding MCP support or changing tool policy is not necessary to correct this description.

## GF8 — Accept as a small discoverability improvement

The display name and documentation URL do not identify the exact installed package. The manifest provides that identity and version (`package.json:25–26`); the integration is TypeScript on Node.js, with ESM packaging and Node `>=22.18` (`6,14–15`).

**Change:** Add dependency metadata: primary package `@openrouter/agent`, installed version `1.0.1`, companion client `@openrouter/sdk` `0.13.67`, and integration language/runtime TypeScript/Node.js. Distinguish these from the adapter's own `openrouter-acp` version `0.1.0`. Follow the map's metadata schema rather than inventing unsupported fields if it is constrained.

## GF9 — Partially accept; absence of records is not proof that no evaluation occurred

The supplied element records no suitability investigation or decision, while `gaps: []` omits the concrete private-API coupling and integration limits established above. However, an empty list does not prove that nothing was checked or that an unprovided schema requires another layer.

**Change:** Add an evidence-backed suitability account in the existing description or a supported decision layer: suitable for the current adapter's model/tool loop with adapter-supplied tools and live-session state; dependent on the pinned SDK pair and private-method patch; restricted to eligible catalog models; no session restoration or client-supplied MCP support in this adapter. Record SDK implementation, runtime tests, the referenced design document, and OpenCode replacement status as unverified in this assessment. Record actual integration constraints in gaps without turning every deliberate scope limit into a promised feature. This resolves the ambiguity without inventing investigations or a migration decision.

## Proposed consolidated description

“The OpenRouter adapter uses the TypeScript/Node.js integration of `@openrouter/agent` 1.0.1 with `@openrouter/sdk` 0.13.67 to run the model/tool agent loop. The adapter supplies four tools—read_file, list_directory, write_file, run_command—and in-memory conversation state through StateAccessor. State persists across prompts only within a live session; session restoration and client-supplied MCP servers are unsupported. File tools apply session-root path checks; shell commands run from that root with client permission and are not filesystem-sandboxed by those checks. Model choices are catalog entries advertising tools and `/api/v1/responses`; new sessions require eligible `openrouter/auto`. The adapter injects fetch, disables client SDK retries, translates response outcomes to ACP, and applies a guarded private-method patch to handle a duplicate promise rejection. The supplied source identifies this adapter as the SDK consumer; project-wide usage and replacement status have not been verified.”

Additional evidence boundaries are recorded in [OminousSiege-evidence.md](OminousSiege-evidence.md). No runtime tests were run: this task resolves description findings, and the snapshot lacks installed dependencies, SDK internals, test files, and the TypeScript configurations referenced by the manifest.

---

## Addendum — independent audit notes (ClawedIodine)

I independently re-read all six files under `source/adapters/openrouter-acp/` and re-checked the cited
lines. I concur with the verdicts above (GF1, GF2, GF4, GF7, GF8 change the description; GF5 no
change; GF6 reject; GF9 partial) and with the care taken on GF7's sandbox caveat and GF9's
"empty gaps is not proof of no evaluation". Three points add what the text above leaves open:

1. **GF3 is right on facts but weak *as a finding*.** It is filed Major yet states no discrepancy —
   it only lists two pins, a fetcher, and a retry setting. Its actionable content ("these are
   undocumented") is the same discoverability gap GF8 raises. The distinct, document-worthy items
   are (a) the non-default policy: `retryConfig:{strategy:"none"}` and the injected `HTTPClient`
   (`adapter.ts:226-232`) deliberately surface errors instead of the SDK's hour-long backoff, and
   (b) the exact pins are the mechanism that keeps GF2's private-method patch valid — a caret range
   would let an SDK bump silently change the method the patch overwrites. Record this coupling; do
   not "fix" the code. GF3 and GF8 should be resolved together to avoid redundant edits.

2. **No finding examined the `references` layer, and it is misleading for this element.**
   `properties.uri` points at the SDK's docs, but the sole `references` entry is design doc §7.3
   "OpenRouter models are selected by their published identifiers". `models.ts:43-80` shows the
   adapter does *not* use published identifiers statically: it fetches the catalog live on every
   `session/new` and filters it by `tools` + `/api/v1/responses`. §7.3 describes the `model` config
   option, not the SDK element, and the design doc is not in this snapshot. When editing
   `element.md`, re-scope or annotate that reference so it is not read as a claim about SDK
   behavior, and state in the investigations/decisions layer whether the SDK's own docs were
   consulted. This also strengthens GF9's "no investigations recorded" point with a concrete example.

3. **On GF6, separate diagnosis from remedy (supports the reject).** The diagnosis — a reader sees
   exactly one consumer in `wants` and may assume main-path status — is fair. The remedy the finding
   demands, "rarely used and superseded by OpenCode", is unsourced: `grep -rin opencode source/`
   returns nothing, and §7.3 is about identifiers, not lifecycle. Reject as stated; any future
   lifecycle/status claim belongs in the `elephant` layer with its own citation, not inferred from
   this finding. GF7/GF1 overlap (two cuts at the same "tool execution" sentence) is already noted
   above; the corrected `wants` line should be written once, not patched twice.
