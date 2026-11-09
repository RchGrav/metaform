# ACP harness — review resolutions

Prepared by GammaLiquid from `element.md` and the supplied source snapshot; augmented by SternSalmon (see `SternSalmon-resolution.md`).

The snapshot contains only `source/crates/acp-host/src/launch.rs`. References below use its line numbers. The web catalog, OpenRouter adapter, RPC client, design documents, registry-source audit, and recorded runs are absent. A finding can correctly identify missing documentation without its underlying runtime claims being independently verified here. No finding establishes a code defect that requires changing the supplied launcher.

## GF1 — OpenRouter harness omitted

**Decision: Accept the documentation concern provisionally; the specific implementation claims are unverified.**

The element describes the participating coding agents, so a first-party ACP adapter belongs in its known-harness inventory if the cited catalog and adapter contain what the reviewer reports. “Any registered or user-supplied ACP command” does not adequately document a separately supplied adapter. However, neither `crates/roundtable-web/src/tables.rs` nor `adapters/openrouter-acp/src/adapter.ts` is supplied. OpenRouter's absence from `builtin()` (lines 78–90) establishes nothing about a separate web catalog.

**Change:** Add an explicit investigation entry: “Reported first-party harness: `openrouter-acp`; verify catalog placement in `crates/roundtable-web/src/tables.rs:76–99` and protocol declaration in `adapters/openrouter-acp/src/adapter.ts:3`.” After inspecting those files, replace “reported” with the verified behavior and record its launch path and protocol version. Do not add OpenRouter to this launcher's built-in list solely to make the lists match: the finding cites a different catalog, which may already supply it.

## GF2 — Pinned fallback versions omitted

**Decision: Accept. Confirmed directly.**

`builtin()` constructs these exact commands (lines 79–88):

| Harness | Built-in command |
| --- | --- |
| Claude Code | `npx -y @agentclientprotocol/claude-agent-acp@0.101.0` |
| Codex | `npx -y @agentclientprotocol/codex-acp@2.5.0` |
| Pi | `npx -y pi-acp@0.0.34` |
| OpenCode | `npx -y opencode-ai@1.19.5 acp` |

**Change:** Record this table in `investigations`, tied to the supplied snapshot. Describe selection precisely: a registry fetch, HTTP-status, or JSON-decoding error returns the built-in catalog with a warning (lines 215–230). A successfully decoded registry is parsed first, then built-ins whose IDs are absent are appended (lines 221–228). A present ID suppresses its fallback even if that registry entry is unavailable; this is not fallback after a failed agent launch. The pins apply to built-in commands, not every launch. Registry entries can use registry packages or an installed binary whose version differs (lines 117–130).

No launcher change is needed. In particular, package versions are not evidence of ACP wire-protocol versions, and a built-in `npx` command does not guarantee operation without network access.

## GF3 — v1 URI versus claimed v2 operation

**Decision: Accept as a documentation ambiguity, not a demonstrated protocol mismatch.**

A v1 overview may be a useful reference even if other versions are supported. The URI alone neither limits the harness to v1 nor disproves the author's account of v2 runs. This file contains no protocol negotiation. Its registry URL's `/v1/` identifies the registry endpoint and does not establish the agents' ACP wire versions.

**Change:** Label the existing URI explicitly as the ACP v1 reference. If the v2 claims are retained, add the exact versioned v2 specification or draft they mean and cite negotiation evidence from the runs. Until that evidence is supplied, qualify v2 as an author-reported observation rather than describing dual-version support as verified. Do not replace the URI with an assumed v2 URL or change launcher code.

## GF4 — Evidence only covers launching

**Decision: Accept. Confirmed evidence limitation.**

The only supplied module selects launch specifications; it does not initialize agents, create sessions, set session configuration, send prompts, or consume updates. Its tests (lines 274–339) cover launch resolution, environment filtering, and command parsing. They do not substantiate the RPC list, run history, or the registry-wide version claim.

**Change:** Preserve the want as a requirement of `code.client.agent`, clearly separated from verified implementation behavior. Attach RPC-client implementation references and representative initialize/session/update traces when available. For the historical claims, cite run artifacts with dates, harness releases, and negotiated protocol versions; for the registry audit, cite its scope and evidence. Mark these claims unverified in this snapshot until then. Missing evidence is not proof the behavior is absent, so deleting the requirement or inventing missing code is unwarranted.

## GF5 — Consequence of the v2 “gap” unspecified

**Decision: Accept the missing compatibility explanation; do not accept the implied v2 requirement as established.**

“Only Claude Code and Codex use ACP v2” is a reported observation, not by itself a functional gap. A gap requires identifying a needed behavior that the other harnesses cannot provide. Neither the launcher's selection logic nor its package pins establish which protocol versions Roundtable requires or supports. The author's reported OpenCode v1 run also does not prove that every required operation works on v1.

**Change:** Replace the unexplained gap with a compatibility status that separates requirements, observations, and unknowns. State which negotiated versions the host supports and which required operations work for each tested harness/release, supported by client code and traces. Identify any concrete v1 limitation and its handling, such as capability checks, omission of an optional operation, or a clear unsupported-operation error. If no required behavior is missing, move the source-audit observation out of `gaps`. Pending evidence, use: “The author reports mixed ACP versions in recorded runs; the host's supported versions and any v1 limitations are not established by the supplied launcher.” No protocol upgrade is justified by this finding alone.

## GF6 — RPC method list lacks version and capability scope

**Decision: Accept the contract-clarity concern; version-dependent differences are not demonstrated here.**

The method list states the desired session workflow but does not distinguish mandatory operations from optional configuration or identify the protocol contract under which they are available. A list of method names alone cannot prove that v1 and v2 differ for those methods. `set_config_option` should also be checked against the actual wire method name and client API before the description treats it as an RPC name.

**Change:** Document the exact RPC names, supported protocol revision(s), and required capabilities alongside the want. State whether configuration is required or conditional and what the client does when an agent lacks it. Verify the session working directory and update/completion behavior in the client implementation. If that inspection finds unconditional calls to unsupported operations, fix the client to negotiate/check support or report incompatibility clearly. This is a conditional code recommendation, not a proven bug in `launch.rs`.

## GF7 — Pi has no run explanation or support status

**Decision: Accept the missing status; the reason cannot be inferred.**

Pi is explicitly offered by `builtin()` at `pi-acp@0.0.34` (line 87). That proves a launch recipe exists. Availability checks for built-ins establish the runner's presence (lines 195–198), not authentication, successful sessions, or feature compatibility. The author's “Pi has never run” needs a bounded scope; the launcher cannot verify a historical negative.

**Change:** Say: “Pi has a built-in launch recipe. The author reports no Pi runs in the recorded-run set as of 2026-11-07; runtime compatibility is unverified. The reason for no recorded run is not documented.” Add the actual reason if records establish it. Do not label Pi unsupported, broken, or fully supported solely from its catalog entry or lack of reported runs. No code change follows.

## GF8 — “Checked by their source” is ambiguous

**Decision: Accept.**

It is unclear which registry entries, repository revisions, and protocol declarations were inspected, or whether “version” means a package release, SDK dependency, declared protocol constant, or negotiated wire version. Those are different forms of evidence.

**Change:** Replace the phrase with a dated audit reference listing the registry snapshot and included agents, each harness release or commit, inspected file/symbol, and the conclusion that evidence supports. Keep source-declared protocol versions separate from versions observed during initialization. If no such audit record is available, use: “The author reports a source inspection dated 2026-11-07; the inspected registry scope, harness revisions, and protocol evidence are not supplied.” Remove or qualify the exclusive “only” claim until the audit supports its stated scope.

## Cross-cutting contradictions

Four fixes above, taken at face value, would write a falsehood into `element.md`. These are
the specific sentences to avoid; they matter because the other findings' advice ("record
exactly what the code proves") is only safe if these are respected.

1. **"tables.rs / adapter.ts prove OpenRouter is ACP v1."** Neither file is in the snapshot,
   and the adapter's own protocol declaration is exactly what is cited, not shown. Record it
   as *reported*, with the file/line, or omit the version. (GF1)
2. **"the built-ins fall back only when the registry is unreachable."** False. `autoselect`
   (222–231) also appends built-ins when the registry succeeds but omits their id, and a
   present id suppresses the fallback even if that registry entry is unavailable. Record both
   conditions. (GF2)
3. **"the URI is wrong / swap it for v2."** Swapping it misrepresents the v1 harnesses the
   element covers. Label the v1 URI and add the v2 document under `references` instead. (GF3)
4. **"acp-host launches v1 harnesses just like v2."** True in the launcher (no version gate),
   but do not upgrade that into "v1 harnesses are supported": the launcher neither reads a
   negotiated version nor any RPC, so launchability is not compatibility. State the
   negotiation question as open unless client evidence is supplied. (GF5)

## Disposition

These findings call for description and evidence improvements. GF2 and GF4 are directly confirmed by the supplied code; GF1's specific catalog and protocol assertions require the missing files. GF3 and GF5–GF8 correctly identify ambiguities without establishing protocol defects. Keep the existing launcher unchanged on this evidence. Resolve the missing-evidence items through explicit qualification now and replace those qualifications with cited results when the relevant artifacts are available.
