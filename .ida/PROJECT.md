---
title: "Project overview: Metaform and Roundtable"
type: project
status: active
created: 2026-11-08
updated: 2026-11-09
---

## Purpose

**Confirmed** (`metaform/SPEC.md` §1): Metaform is the context tool for development agents. An intake agent records a project's functional form as a tree of dotted addresses. Each element records which other elements it wants, why and how. Agents then work from a small, relevant part of that map, so they use fewer tokens and do not change things they do not understand.

**Confirmed** (`roundtable/README.md` §1): Roundtable is a multi-agent discussion tool written in Rust. Agents from different models work toward a goal the user sets, and a judge (JEV) vetoes unproductive messages. Its own functional map is a Metaform map (`roundtable/metaform.json`).

## Intended users and stakeholders

- Development agents in Claude Code, Codex and other harnesses. **Confirmed.**
- The project owner, who reviews the map and the specification. **Assumption** (`OWNER_REVIEW_SPEC.md` §2 marks it Inferred).
- Several people and agents at once, with conflict-safe writes. **Confirmed.**
- In-game agents that own their own Metaform instance (R-4.14). **Confirmed** as intent.

## Goals and success measures

- Map any kind of project, greenfield or brownfield (R-1.2).
- Round-trip a specification: take it in, refine it, export it (R-1.2). Not built.
- Measure context use consistently, with and without Metaform (R-1.3). This is the evidence for the preprint's central claim. Not built.

## Constraints and dependencies

- The intake procedure (`metaform/Intake.md`), schema and tool contract are protected. They change only on the owner's direct instruction.
- One MCP tool (`project-map`). New tools need an owner decision.
- No recurring polling. No temporary foundations (R-1.1).
- Maps are stored in LadybugDB and written only by the map server. Nothing is written into a project's own folder (R-4.1).
- MCP protocol `2026-07-28`.

## Current stage and status

- Consolidated into this folder from `~/topogee` on 2026-11-08. **Verified:** the remote is `RchGrav/metaform` on GitHub. The owner's old repository is now `RchGrav/metaform-archive` (stated by metaform-d2).
- **Recorded in `SPEC.md` R-3.6 (commit `db8c9f8`, owner decision 2026-11-08):** the want field `intent` is renamed `direction`, with values `inbound`, `outbound` and `two-way`. Not applied yet to the intake, schema, contract, servers or stored maps.
- `metaform/SPEC.md` has not been reviewed by the owner.
- **Verified 2026-11-08 by Ida:** the Python contract checks pass (30 and 13 tests), `tools/verify_bootstrap.py` passes, and the Rust tests pass (core 4, store 6, server 13).
- The Rust server is partly built. Layers, chaining, search, memory, tickets, export, the R-5.24 refusal codes, the new intent values and token measurement are not built.
- **Verified 2026-11-08 by a subagent:** Roundtable builds with no warnings, and `cargo test` gives 91 passed, 0 failed, 2 ignored. The 2 ignored tests need root and eBPF. The OpenRouter adapter's tests were not run, because `node_modules` is absent.
- Roundtable runs locally: `roundtable serve` serves a web UI on 127.0.0.1:4180 with a chair token, and `roundtable run table.json` runs without the UI. Agents connect over ACP. Owner gates still open: RT-G06, G09, G10, G12 to G16, G18, G19, G21.

## Confirmed context and decisions

See `context/topogee-repo/DECISIONS.md` and `metaform/SPEC.md`. Known conflicts are listed in `PROJECT_CONTEXT.md` §7 and the owner's questions in `OWNER_REVIEW_SPEC.md` §7.

## Assumptions and unknowns

- **Resolved 2026-11-08 (DEC-001):** the live map databases in `~/.metaform-rust`, `~/.metaform` and `~/.topogee` do not need to be kept or exported.
- **Unknown:** whether the map is meant to follow git branches or to be one map per project.

## Sources checked

`START_HERE.md`, `OWNER_REVIEW_SPEC.md`, `PROJECT_CONTEXT.md`, `metaform/SPEC.md`, `metaform/rust/crates/metaform-server/src/lib.rs`, `metaform/rust/crates/metaform-store/src/registry.rs` and `lib.rs`, `metaform/Intake.md` (line 157), `context/topogee-repo/DECISIONS.md` (line 109), `~/.metaform-rust/projects/`.
