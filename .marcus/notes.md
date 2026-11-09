# Marcus working notes: Metaform

Notes kept by Marcus (the `mcp-expert` skill) for MCP work on this project. Read this file at the start of each session. Verify any file, symbol or version named here before relying on it.

## Context

- Project root: `/home/rich/metaform`. Orientation: `START_HERE.md`, then `OWNER_REVIEW_SPEC.md`, `PROJECT_CONTEXT.md`, `metaform/SPEC.md`.
- `.mcp.json` registers two servers:
  - `metaform`: local Rust stdio server, `metaform/rust/target/release/metaform mcp --home ${HOME}/.metaform-rust --project .`. It exposes one tool, `project-map` (seen in the session tool list on 2026-11-08).
  - `boat-docs`: remote HTTP docs server, `https://docs.boat.dev/mcp`.
- Rust workspace: `metaform/rust/crates/{metaform-core, metaform-store, metaform-server}`. An older Node/TypeScript server is in `metaform/server/`.
- `metaform/SPEC.md` is the specification the build follows. Its status is "in progress", not reviewed by the founder (the owner).
- Writing rules: `TASTE.md` (plain technical English) and `EXPECTATIONS.md` (decide supported gaps, bring back only owner-dependent decisions with a recommendation).

## Constraints

- Protected: `metaform/Intake.md`, the schema and the tool contract. Do not change them without the owner's direct instruction.
- `context/` is preserved evidence. Read it; do not edit it.

## Decisions

- 2026-11-08: Notes live in `.marcus/` at the project root (owner's instruction).
- 2026-11-08: Working mode is Review of the existing MCP server, chosen by Marcus after the owner said "do what you do best".

## Review findings (2026-11-08, server layer only)

Scope: `metaform-server/src/*`, `mcp-tools.proposed.json`, SPEC sections 1, 2, 4.2, 5, 8–10. Not assessed: `metaform-core` command semantics, `metaform-store` internals, name conversion, Roundtable.

Checks run 2026-11-08, all passing: `check_contract.py` (30), `check_tool_input.py` (13), `verify_bootstrap.py`, `cargo test --offline` (23 tests).

1. Contract text shows store terms to agents. The tool description says "nested namespace" and "Tool name is provisional". The schema description says "storage remains a nested namespace" and "Validate this input before any mutation" (an implementation instruction). This conflicts with R-2.1, R-2.2 and R-4.12. The contract is protected, so this is an owner decision.
2. Tool definition is 12,217 characters of JSON and is loaded into every agent context. The 279-character description is a small part of it. Nothing measures it: R-1.3 token counting is not built (no token code in `rust/crates/*/src`).
3. One tool carries reads, writes and deletes (R-5.1 and R-5.26 are Decided). Consequence: host permission rules work per tool, so a user cannot allow reads and still gate deletes. `DEPENDENCY_LOCK` and the four-step delete (R-5.25) limit the harm.
4. Store failures (`Failure::Store`, `tool.rs` `call_tool`) return plain text, not the refusal shape with a code. `INTERNAL_ERROR` is Proposed (R-5.24). `call.rs` tells a refusal from a server failure by the presence of `code`, so a wrapped store failure must keep exit 2.
5. Latent relay bug: `resources/unsubscribe` removes every resource subscription from the replay list (`relay.rs`, `note_client_line`). It is harmless while the server has one resource. It becomes real when `skill://` resources become subscribable (R-5.32). Fix it then by matching the URI.
6. The server trusts the handshake's folder path (`lib.rs` `open_project`). Only the forwarder canonicalizes it. The socket is 0600, so only the same user can connect. Low risk.
7. `add` grows arrays, so a retry after a write whose answer was lost can duplicate entries. The relay's restart error tells the agent to read the map first. A host-side timeout on `tools/call` gives no such message. This is a risk only; nothing has been observed (R-5.20).

- 2026-11-09: Finding 4 decided by Marcus: store failures stay plain text with `isError` set. Reason: R-5.20 (Decided) allows tool logic only to fix an observed issue, and none is observed. `INTERNAL_ERROR` is only Proposed. Revisit when an agent is seen mishandling a store failure. Lesson: the owner corrected me for bringing this to them; per `EXPECTATIONS.md`, a question the SPEC answers is mine to decide.
- 2026-11-09: Built the R-1.3 fixed-overhead baseline. `one_tool_over_mcp_2026_07_28` asserts the compact `tools/list` result equals `TOOLS_LIST_BYTES` (11,762 bytes). Commit `06d31e3` on branch `tools-list-size-baseline`, pushed; not merged; not accepted by the owner.

## Open questions

- Owner: apply the `intent` → `direction` rename (decided 2026-11-08, SPEC R-3.6; recorded in this repository by commit `6a984e1`) to the protected contract. `mcp-tools.proposed.json` still uses `intent` (lines 302, 356, 379, 408, 554 on 2026-11-09), with the old values `send`, `receive`, `send_receive`. Recommendation: do it in the same owner-approved change as finding 1, so the contract changes once.

- Owner: rewrite the protected contract text (finding 1)? Recommendation: yes, as agent-facing text with no store terms.

## Risks

- Ambiguous retry of non-idempotent `add` (finding 7).
- Not verified against current sources: the protocol claims in SPEC section 8 (sessions removed in `2026-07-28`, SEP-2575, SEP-2640). The test `one_tool_over_mcp_2026_07_28` passes, which shows rmcp negotiates that version.

## Next actions

1. Done 2026-11-09 (`06d31e3`). When the contract rewrite lands, update `TOOLS_LIST_BYTES` and report the change in size.
2. Fix finding 5 when R-5.32 is built.

## Coordination

- Ida (project-insight agent; notes in `/home/rich/metaform/.ida/`) owns three items. First, Roundtable approves every agent shell command by default (RT-G18). Second, projects keyed by absolute path give each worktree or moved folder a new, empty map. Third, `~/.metaform-rust/projects/-home-rich-topogee001` has no backup or export. Do not work on these. Ida will report if a fix changes the handshake or `map_uri`.
- Ida's Q-011 (not decided, not built) proposes one map per repository, keyed by the git common directory, plus a CLI command to attach a moved folder. The handshake stays `{"project": <folder>}`, and the server resolves the folder. My input, sent 2026-11-08: the server canonicalizes too (this closes finding 6). Make project ids opaque, so `map_uri` stays stable. Fall back to the canonical path for folders outside git. State that branches sharing one map is intended, if it is. Keep `-home-rich-topogee001` reachable through any re-keying. Ida accepted all of this into Q-011 (2026-11-08). Nothing is built until the owner answers.
- 2026-11-09: My point about keeping `-home-rich-topogee001` reachable is withdrawn. Ida's DEC-001 records that the owner does not need past maps kept or exported (relayed by session metaform-d2; recorded here by commit `9c181df`; Ida has not confirmed it with the owner directly).
- R-1.3 split: Marcus measures the fixed overhead (`tools/list` size test). Ida's O-001 measures per-task tokens from harness transcripts.

- Commit hashes `db8c9f8` and `1b0a1df` in earlier entries belong to the old `~/topogee` repository. They are not in this repository's history (checked 2026-11-09).
- 2026-11-09: `CLAUDE.md` now carries the feature-commit rule (uncommitted on 2026-11-09): after a passing test, commit and push without asking, one branch per feature. Any server change Marcus builds follows it.
- 2026-11-09: `.gitignore` now lists `.marcus/` (uncommitted on 2026-11-09). These notes are local only and are not pushed.

## Session log

- 2026-11-08: Created `.marcus/`. Read `START_HERE.md` and the SPEC. Reviewed the server layer and the contract. Ran all checks (passing). Recorded findings 1–7.
- 2026-11-09: Read notes. Checked commits since 2026-11-08 (`db8c9f8`, `1b0a1df`, docs only; no server code changed) and Ida's notes. Recorded the pending rename's effect on the contract and withdrew the topogee001 point after DEC-001.
- 2026-11-09 (second session): Read notes. No server code changed since the consolidation commits. Corrected commit references to this repository. Recorded the feature-commit rule and that `.marcus/` is gitignored.
- 2026-11-09 (second session, cont.): Owner pointed out that finding 4 should not have been brought to them. Decided it under R-5.20. Built and pushed the `tools/list` size baseline (23 tests pass). The map for this project is empty, so there is no features layer to name in commits yet.
