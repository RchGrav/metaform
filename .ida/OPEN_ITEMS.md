---
title: "Open items"
type: open-items
status: active
created: 2026-11-08
updated: 2026-11-09
---

Priorities and next steps are Ida's recommendations unless an entry says the owner agreed them. The owner's existing questions Q1 to Q10 are in `OWNER_REVIEW_SPEC.md` §7 and are not repeated here.

# Risks

## R-001 — A worktree, moved folder or clone gets a new, empty map
- Type: Risk
- Status: Open
- Priority: High
- Raised: 2026-11-08
- Evidence / basis: Verified in code. The server identifies a project by its canonical absolute folder path (`metaform-store/src/registry.rs:20-55`). A forwarder that connects from an unknown folder registers it as a new project at once, with no message (`metaform-server/src/lib.rs:162-176`). `context/topogee-repo/DECISIONS.md:109` keeps the rule of one worktree for each piece of work.
- Affected user or system: Every agent working in a worktree; the owner if the repository is moved, renamed or cloned to another machine.
- Impact or value: The agent sees an empty map and may start a new intake. Knowledge splits across maps, and the original map is left behind under the old path. This defeats the purpose of the map in the exact workflow the owner requires.
- Next step / owner: Owner decision Q-011. Engineering can then key a project by the git common directory and add a CLI command that attaches a folder to an existing project.

## R-002 — The only real intake exists in one uncheckpointed database with no export
- Type: Risk
- Status: Resolved (2026-11-08)
- Priority: n/a
- Review or resolution: 2026-11-08. The owner decided that the past intake needs no backup or export. This was relayed by metaform-d2 and recorded in `PROJECT_CONTEXT.md:107` (committed in `1b0a1df`). An export command is still needed for the export-equals-import acceptance test (`SPEC.md` §9), but that is a build item, not a data-loss risk.
- Raised: 2026-11-08
- Evidence / basis: Verified. `~/.metaform-rust/projects/-home-rich-topogee001/` holds `project.lbug` (4 KB) and `project.lbug.wal` (256 KB, last written 2026-11-07 21:04). `.design-review/README.md` says this is the intake of `world-system-spec.md`, 61 elements and 114 wants (Stated, not checked). The Rust server has no export command (no match for `export` in its crates). `SPEC.md` §9 says existing maps are cleared and rebuilt.
- Affected user or system: The owner; the only evidence of a full intake run on the Rust server.
- Impact or value: A disk problem, a Ladybug upgrade or a "clear and rebuild" step loses it. It is also the natural fixture for the export-equals-import acceptance test.
- Next step / owner: Copy the folder while no server runs. Build export early, because acceptance (§9) needs it anyway. When the `intent` → `direction` rename (R-3.6) is applied, this map needs a migration (noted by metaform-d2).

## R-003 — Drift findings from intake have nowhere valid to go
- Type: Risk
- Status: Open
- Priority: Medium
- Raised: 2026-11-08
- Evidence / basis: Verified conflict. `metaform/Intake.md:157` tells the intake agent to record drift and `un_built` reasons "in the native investigation knowledge layer". `SPEC.md` R-6.13 says `investigations` is not a layer, and R-3.16 sends such notes to a ticket. Tickets are not built (R-5.31). Not listed in `PROJECT_CONTEXT.md` §7.
- Affected user or system: The intake agent; any later agent that trusts the map.
- Impact or value: Today the intake agent must either drop these findings or write them where the spec forbids. Nothing else detects when a project changes and its map goes stale, so a stale map can lead to the unsafe change Metaform exists to prevent.
- Next step / owner: Owner decision Q-012. The intake is protected.

## R-004 — The socket protects against other OS users, but not between agents of one user
- Type: Risk
- Status: Open (known as D-8)
- Priority: Low
- Raised: 2026-11-08
- Evidence / basis: Verified. The socket is set to mode 0600 (`metaform-server/src/lib.rs:114`). Any process of the same user can open any map, including private maps (comment above `check_map_name` in `lib.rs`).
- Affected user or system: In-game agents that own private maps (R-4.15), if they run as the same OS user.
- Impact or value: Private maps are not private until agent identity exists.
- Next step / owner: Covered by owner question Q10 (D-8). Note the dependency when private maps are built.

## R-005 — Roundtable approves every agent shell command by default
- Type: Risk
- Status: Open (gate RT-G18 awaits the owner)
- Priority: High
- Raised: 2026-11-08
- Evidence / basis: Verified by Ida. Under the default `Inside` rule, a request is allowed when every path it names is inside the workspace, or when it names no path (`roundtable/crates/acp-host/src/permission.rs:168-176`, test at `:207`). The OpenRouter adapter's `run_command` names only the workspace root (`adapters/openrouter-acp/src/tools.ts:446`), so every command passes. Only three variables are removed from agent environments (`crates/roundtable/src/config.rs:55`). Inferred, not tested: an agent's shell can read the server's environment through `/proc`, because both run as the same user.
- Affected user or system: The chair's user account and any credentials in its environment.
- Impact or value: An agent, or a prompt injected into one, can run any command the user can run.
- Next step / owner: Owner decision on RT-G18. Ida recommends `permissions.execute = refuse` by default, with an explicit per-table opt-in or a harness sandbox.

## R-006 — A hung JEV call or a stuck seat stalls the whole table
- Type: Risk
- Status: Open (JEV fix decided, not built: item 10, `jev.deadline_seconds`)
- Priority: High
- Raised: 2026-11-08
- Evidence / basis: Subagent report, verified in code by the subagent and not re-checked by Ida. The JEV HTTP client has no timeout (`crates/roundtable-web/src/app.rs:195`, `crates/roundtable/src/jev.rs:157`). A seat's `initialize` has no timer (`crates/acp-host/src/harness.rs:196`). A silent agent holds the floor, and the chair has no skip or cancel for one seat (`table.rs:294-305`).
- Affected user or system: The chair; every seat at the table.
- Impact or value: The table stops with no way out except End or a server restart. A seat stuck at startup is probably not stopped by End (inferred).
- Next step / owner: Build item 10. Add an `initialize` deadline and a chair command that skips or cancels one seat.

## R-007 — Nothing caps Roundtable's spending
- Type: Risk
- Status: Open
- Priority: Medium
- Raised: 2026-11-08
- Evidence / basis: Subagent report (verified in code by the subagent). There is no default reply limit (`config.rs:189-193`), the adapter starts on `openrouter/auto` with no step cap (`adapters/openrouter-acp/src/models.ts:17`, `adapter.ts:150-160`), and command output reaches the model without a size cap (`tools.ts:308`).
- Affected user or system: The owner's OpenRouter account.
- Impact or value: A long table, or a command that prints a large file, can run up cost with no warning.
- Next step / owner: Add a per-table budget and a spend meter. Cap command output.

# Questions

## Q-011 — What identifies a project: its folder, its repository or something else?
- Type: Question
- Status: Open
- Priority: High
- Raised: 2026-11-08
- Evidence / basis: R-001. R-4.1 forbids writing into the project's folder, which rules out an id file in the repository unless the owner allows it.
- Affected user or system: Map server, every agent.
- Impact or value: Decides whether worktrees share one map, and whether a map follows a branch.
- Next step / owner: Owner. Ida's recommendation, with Marcus's review (2026-11-08):
  1. Key a project by its git common directory, so all worktrees of one repository share one map. A folder outside git falls back to its canonical path, because Metaform covers projects that are not code (SPEC §1).
  2. Make the project id opaque, not derived from the path. Today `registry.rs` builds it from the encoded path plus a counter, and `announce.rs` `map_uri` embeds it. An opaque id keeps the URI stable through moves, attach and later changes to the keying rule, and keeps a store detail off the agent surface (R-2.1).
  3. Keep the handshake as `{"project": <folder>}`. The server canonicalizes the folder and resolves it to a project. This also closes Marcus's finding that the server trusts the handshake folder.
  4. Add a CLI command that attaches a folder to an existing project, for moves, clones and folders outside git.
  Existing maps do not need to survive re-keying (see DEC-001).
- **Consequence the owner must accept or reject:** with one map per repository, agents on diverging branches write `update` and `delete` into the same map. R-2.10 allows one intake agent at a time, but it does not prevent these collisions. If the map should follow branches instead, the key would include the branch, and merging maps becomes a new problem.

## Q-012 — Where do intake drift findings go until tickets exist?
- Type: Question
- Status: Open
- Priority: Medium
- Raised: 2026-11-08
- Evidence / basis: R-003.
- Affected user or system: The intake procedure (protected).
- Impact or value: Without an answer, intake loses evidence it is told to keep.
- Next step / owner: Owner. Ida recommends a minimal ticket store first, then one instructed edit to `Intake.md:157`.

# Opportunities

## O-001 — Capture "without Metaform" baselines now
- Type: Opportunity
- Status: Open
- Priority: Medium
- Raised: 2026-11-08
- Evidence / basis: R-1.3 is decided in principle and has no implementation. It is the evidence for the preprint's central claim.
- Affected user or system: The preprint; every later performance claim.
- Impact or value: Sessions run today without a count are lost baselines. Harness transcripts already record token usage, so a fixed task set and a script can start the comparison before the in-server counter exists.
- Next step / owner: Unassigned. Choose three to five repeatable tasks on a known project.

## O-002 — Mark Roundtable's README as superseded
- Type: Opportunity
- Status: Open
- Priority: Low
- Raised: 2026-11-08
- Evidence / basis: Subagent report. The owner has called `roundtable/README.md` "never my spec". The code differs from it on truncation, banking, JEV scoring, topics, timers and AgentSight, and the README omits the 10-round default, the rating round and identities. `PROJECT_CONTEXT.md` §6 still lists the README as Roundtable's functional spec.
- Affected user or system: New agents and contributors who read the README first.
- Impact or value: Agents build against a document the owner does not stand behind.
- Next step / owner: Owner to confirm which document governs Roundtable.
