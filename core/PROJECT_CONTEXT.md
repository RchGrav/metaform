# Project context: Metaform, archive of 2026-11-15

This document says what this folder holds, where each file came from, what was left out and why, and how to build and test the tool. The specification is [SPECIFICATION.md](SPECIFICATION.md).

Each claim that matters carries one mark: **Verified** (checked on 2026-11-15 by the means stated), **Stated in source material**, **Inferred**, **Unknown**, **Conflicting** or **Potentially outdated**.

## 1. What this archive is

- **Target.** Metaform as it stands in the source repository on 2026-11-15: the specification, the Rust form of the tool, and the files the tool is built from. The founder identified this version as the correct one and asked for one specification and one archive. **Stated by the founder, 2026-11-15.**
- **Purpose of the target.** Metaform keeps a map of what a project does, for development agents. It gives them one MCP tool, `project-map`, to read and write the map. **Stated in source material** (`metaform/SPEC.md`, section 1).
- **Whole or part.** This archive is a part of the source repository, chosen on purpose. It holds one of the three forms of the tool, and none of the earlier documents. Sections 4 and 5 list what was left out. **Verified** by the inventory in section 3.
- **Standing alone.** The Rust workspace in this archive builds and passes its tests with no other file of the repository (section 7). **Verified.** The command `metaform gui` needs a built web page, which is not in this archive. **Verified** by reading `metaform/rust/crates/metaform-web/src/main.rs`.

## 2. Source and preparation

| Item | Value |
|---|---|
| Source folder | `/home/rich/metaform` |
| Branch and commit | `fable-climb`, `1798c6e` (2026-11-15). The last commit before this preparation is `3da482d` (2026-11-12). |
| Preparation date | 2026-11-15 |
| Changes to the source during preparation | The founder gave two instructions on 2026-11-15 while the archive was prepared: a role is written by its full name, and Coupled Element is a new role. Commit `874b0a0` makes that change in the tool, the schema, the contract, the help, the examples and the procedure, and records it in `metaform/SPEC.md` with the founder's statements on layer definitions. Commit `1798c6e` makes the tool's examples follow the stored form that the founder wrote. The folder `archive/` was added and is not tracked by git. |
| State of the copied files | Every copied file under `metaform/` equals its committed version at the commit above. `guidance/TASTE.md` is the working copy, which differs from the committed version by an edit that is not committed. `founder/intake_best.xml` is not tracked by git. **Verified** by `git status` and by comparing each copy with its source. |

## 3. What is in the archive

| Path | Source path | Last changed in git | Note |
|---|---|---|---|
| `SPECIFICATION.md` | written for this archive | | The one specification. |
| `PROJECT_CONTEXT.md`, `README.md`, `MANIFEST.sha256` | written for this archive | | |
| `metaform/rust/` (51 files) | `metaform/rust/` | 2026-11-15, `1798c6e` | The Cargo workspace: every file that git tracks. Build output is not copied. |
| `metaform/intake/procedure/` (12 files) | `metaform/intake/procedure/` | 2026-11-15, `874b0a0` | The whole intake procedure, as the tool serves it. `build.rs` compiles it into the server. |
| `metaform/metaform.schema.json` | same path | 2026-11-15, `874b0a0` | The schema of the stored form. The core library embeds it. |
| `metaform/mcp-tools.proposed.json` | same path | 2026-11-15, `874b0a0` | The contract. The core library embeds it. |
| `metaform/mcp-tool.published.json` | same path | 2026-11-11, `f0849ee` | The published definition. The server embeds it. |
| `metaform/tool-help.json` | same path | 2026-11-15, `1798c6e` | The help text. The core library embeds it. |
| `metaform/tool-examples.json` | same path | 2026-11-15, `1798c6e` | The founder's examples. A test reads it. |
| `metaform/intake-example.json` | same path | 2026-11-15, `1798c6e` | A stored map. Two tests read it. |
| `metaform/metaform-canonical.json` | same path | 2026-11-15, `874b0a0` | A stored map of an earlier system. One test reads it. It is test data. |
| `founder/intake_best.xml` | `rich/intake_best.xml` | not tracked; saved 2026-11-12 07:54 | The founder's working copy of the procedure. Included so that it is not lost: the repository holds it in no commit. |
| `guidance/CLAUDE.md`, `guidance/TASTE.md`, `guidance/EXPECTATIONS.md` | the repository's root | | The rules for agents that work on Metaform. |

The files under `metaform/` keep their paths, because the Rust code reads them by relative path from each crate.

`guidance/CLAUDE.md` refers to files that are not in this archive, such as `START_HERE.md` and `context/`. Section 12 of the specification restates its rules that concern Metaform.

## 4. What was left out, and why

The founder asked for one version. A file was left out when it belongs to an earlier generation of the design, repeats the specification, or is not Metaform. Each item is in the source repository at the commit above.

| Left out | Why |
|---|---|
| `metaform/SPEC.md` | The record of every decision with its date, source and reason. It also holds every superseded decision, so it reads as several versions at once. The specification cites its requirement numbers. |
| `metaform/SPECIFICATION.md`, `metaform/PROJECT_SPECIFICATION.md`, `metaform/DESIGN.md`, `OWNER_REVIEW_SPEC.md`, `PROJECT_CONTEXT.md`, `START_HERE.md` | Earlier specifications and guides. Each uses terms that the founder has since replaced. |
| `metaform/Intake.md`, `metaform/Intake.xml`, `metaform/intake.mmd`, `metaform/intake/pure_intake.xml`, `metaform/intake/intake.proposed.xml`, `metaform/intake/stripped/` | Earlier and experimental texts of the intake procedure. The current procedure is in the archive, at `metaform/intake/procedure/`. |
| `metaform/docs/` | Design notes, the founder's documentation set of 2026-11-02, the concepts document, the preprint and the trouble log. They are background, and several use earlier terms. |
| `metaform/node/`, `metaform/python/`, `metaform/conformance/` | The Node and Python forms and the cases that compare the three forms. They still use the terms from before 2026-11-12 (`dev/HANDOFF.md`), and they do not have the role change of 2026-11-15. |
| `metaform/workspace/` | The web page. The founder rejected the pages that exist. |
| `metaform/tests/`, `metaform/validate_metaform.py`, `metaform/requirements-dev.txt`, `metaform/verification/`, `metaform/tools/`, `metaform/agents/`, `metaform/SKILL.proposed.md`, `metaform/owner-skills-example.json`, `metaform/provider-reference-example.json` | Checks and material for the earlier contract and forms. The Rust tests do not read them. |
| `metaform/rust/target/` | Build output, about 15 GB. |
| `roundtable/` | Roundtable is a separate tool. |
| `context/` | Preserved source material from earlier repositories. It holds the drifting versions. |
| `dev/` | Working notes: the handoff of 2026-11-12, prompts and notes for the web page, and scripts for test intakes. |
| `.mcp.json`, `.codex/`, `.github/`, `.claude/`, agent note folders, `MANIFEST.sha256` of the repository, `tools/` | Settings of the source repository and its checks. |
| `rich/intake_best.xml~`, `TASTE.md~`, `TASTE_Backup.md` | Editor backups. |

No credentials were found in the copied files. **Verified** by a search for key, token and password patterns.

## 5. What is known to be missing

- **The dependencies of the Rust workspace are not in the archive.** `metaform/rust/Cargo.lock` fixes the version and checksum of each of 191 packages. A build needs them from crates.io or from a local cargo cache. **Verified.**
- **No toolchain file.** The workspace uses Rust edition 2024. The build of 2026-11-15 used cargo 1.99.1 and rustc 1.99.1. The lowest version that works is **Unknown**.
- **The web page.** `metaform gui` reports that the page is not built.
- **The records of decisions.** A reader who needs the date and reason of a decision needs `metaform/SPEC.md` from the source repository.

## 6. What the tool is made of

**Stated in source material and verified by reading the code**, unless marked.

- **Language and layout.** Rust, one Cargo workspace, four crates: `metaform-core`, `metaform-store`, `metaform-server` and `metaform-web`.
- **Main dependencies.** `lbug` 0.22.3 (LadybugDB, the graph database), `rmcp` 3.9 (MCP), `tokio`, `axum` 0.8.9, `jsonschema` 0.60.2 and `serde_json`.
- **Entry points.** The binary `metaform` (`crates/metaform-server/src/main.rs`) and the binary `metaform-web` (`crates/metaform-web/src/main.rs`).
- **Interface for agents.** One MCP tool, `project-map`, over stdio, through `metaform mcp`.
- **Data flow.** An agent's MCP process relays to one server for each home, over a Unix socket. The server checks each command in `metaform-core`, and `metaform-store` writes it to a LadybugDB database in one transaction.
- **Files embedded at build time.** The four JSON files named in section 3 and the folder `metaform/intake/procedure/`.
- **Settings of the machine.** The home is `--home`, or `METAFORM_HOME`, or `~/.metaform`. `METAFORM_LAUNCHER` names a launcher for the server; an empty value means none. The archive needs no secret.

The specification, sections 8 and 9, describes the server and the store.

## 7. Build and test

```sh
cd metaform/rust
cargo build --release -p metaform-server
METAFORM_LAUNCHER= cargo test
```

- `cargo build --release -p metaform-server` builds the `metaform` binary at `target/release/metaform`.
- `METAFORM_LAUNCHER= cargo test` runs the tests with no launcher, so each test starts its own server in a temporary home.

**Verified on 2026-11-15.** The folder `metaform/` of this archive was copied to a separate scratch folder, and `METAFORM_LAUNCHER= cargo test --offline --no-fail-fast` was run there. Every test passed: 77 passed and 0 failed. The dependencies came from the local cargo cache.

What the check covered and did not cover:

- It covered a build of all four crates in the debug profile and every test of the workspace.
- It did not cover a release build, a build on another machine, or a build with a different version of Rust.
- It did not start the server for an agent, and no agent performed a test intake.
- One run of the same check, on the final source, ended with the store's test program giving no result, so only 66 tests reported. The log of that run was not kept, and the cause is **Unknown**. The failure did not repeat: the full check then passed, and the store's tests passed in 12 further runs, 3 in the source repository and 9 in the scratch copy.
- The first run, before the role change, failed, because a test reads `metaform/metaform-canonical.json`. That file was then added to the archive, and the next run passed.
- After the role change, the tool was also run once by hand through its server, with a temporary home. A role of `DE` was refused with the command that says `Defining Element`. That command and a `Coupled Element` were accepted, and `map`, a raw dump and `help` showed the new roles. This run used the build in the source repository, at the same source as this archive.
- Two older checks of the source repository, `metaform/tests/check_contract.py` and `metaform/tests/check_tool_input.py`, fail. They failed with the same counts before the role change. They are not in this archive.

To use the tool as an agent's MCP server, start `metaform/rust/target/release/metaform mcp --home <home> --project <folder>`. Use a home with a short path: the path of `<home>/server.sock` must be at most 107 bytes.

## 8. How the specification was prepared

- **Read in full:** `metaform/SPEC.md`, `metaform/PROJECT_SPECIFICATION.md`, `metaform/README.md`, `metaform/rust/README.md`, `dev/HANDOFF.md`, `START_HERE.md`, `CLAUDE.md`, the three tool files, `metaform/metaform.schema.json`, and the intake procedure's `sections.md` and its sections `title`, `prompt`, `goal`, `core_concepts`, `namespace_rules`, `method`, `constraints`, `completion_condition` and `response_protocol`.
- **Read in part:** `metaform/DESIGN.md` (sections 8 and 12 to 14), `metaform/docs/documentation-set.md` (modules 4 and 5), `dev/chained_map_storage.md`, and the openings of the other files in `dev/`.
- **Not read:** `metaform/SPECIFICATION.md`, `metaform/Intake.md`, `metaform/docs/designs/`, the preprint, the Node and Python forms, the web page, `context/`, and the sections `examples` and `cqu_rules` of the procedure.
- **The code.** The author of the specification read every source file of the four crates: the core library, the store, the server and the web host. Eight reviewers also read the code. Two reported what the code does, before the specification was written. Four compared sections 1 to 15 with the code, part by part, and reported 24 statements that were wrong or imprecise and the behaviour that was missing. The author checked those findings against the code, corrected the statements, and added sections 16 to 19, which state the exact behaviour. No reviewer ran the code.

Limits that follow:

- A statement marked Built rests on reading, and on the tests only where a test covers it. **Inferred** statements are marked in the specification.
- Sections 16 to 19 of the specification were written from the code. Two more reviewers then compared them with the code, part by part. They confirmed the rest and found 14 differences, all small, and all were corrected. The author also checked by script that each literal message quoted in those sections appears in the source.
- The specification follows the newest decision recorded in `metaform/SPEC.md` and `dev/HANDOFF.md`. A decision that the founder made and that neither file records is not in it. **Potentially outdated** for anything decided after 2026-11-12, other than the founder's statements of 2026-11-15 on layer definitions, roles, stateless MCP, work across projects, and the separation of MCP from the command line.
- The founder has not reviewed the specification.

This archive holds no separate specification for owner review. The founder asked for one specification, so `SPECIFICATION.md` serves that purpose, and its section 13 lists the decisions that are the founder's.

## 9. Known conflicts and open questions

- Section 13 of the specification lists the open decisions.
- Section 14 of the specification lists where the files in this archive disagree.
- Section 9.6 of the specification reports a possible defect in the store, inferred from the code and not run.
- **Conflicting:** the founder decided that each layer is kept in its own files, and the build keeps layer records in the map's database (specification, section 9.2).
- **Conflicting:** the founder decided that a layer's definition holds the structure of its records. The build keeps the checks of the one built layer in the code (specification, section 5.3).

## 10. Next steps that the evidence supports

1. The founder reviews `SPECIFICATION.md`, and settles the open decisions of its section 13 that block work: items 1, 2, 5 and 18. Item 18 is how a command names a project, now that MCP holds no session and Metaform is meant to work across projects.
2. Build the check of a layer's records against its definition (specification, section 5.3).
3. Run an intake on a code project with this version; none has been run.
4. Write a test for the path of section 9.6 before a home from before 2026-11-12 is used again.
