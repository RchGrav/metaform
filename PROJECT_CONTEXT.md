# Project context: Metaform (with Roundtable)

**Prepared:** 2026-11-08, by an agent, for the owner and for developers.
**Status labels:** **Verified** (checked against files, git or checksums), **Stated** (written in a source document), **Inferred** (the preparer's reading of the evidence), **Unknown**, **Conflicting**, **Potentially outdated**.

---

## 1. What the target is

**Metaform** is the context tool for development agents. It is made up of the intake procedure, the functional map (the "functional namespace"), the one MCP tool and the map server. The owner describes it as "a functional topology capable of forming intake from intent, greenfield, to brownfield or any type of project code or not code". It can refine a specification and re-save it, act as a formboard for realigning hard-to-refactor code, and serve as a context management system inside any project. **Stated** (`metaform/SPEC.md` §1, owner 2026-11-07).

**Roundtable** was added at the owner's request. It is a multi-agent system in which agents from different models discuss and build toward a goal the user sets, with a cheap judge (JEV) that vetoes unproductive messages. **Stated** (`roundtable/README.md` §1).

### Whole project or a part?

- **Metaform is a component that was developed inside a wider repository.** **Verified.** It lived in `~/topogee/metaform/` inside `RchGrav/topogee`. That repository also develops Topogee (the shared world), a C service launcher and Roundtable. The owner, `DECISIONS.md` "Where Metaform lives": Metaform is kept "as part of this private repo to later replace the existing private metaform repo."
- **This copy is partial.** Material about the following is not here:
  - **Unknown / not available:** the earlier private `RchGrav/metaform` repository (the Python chassis-and-modules system the preprint and `reference/` describe).
  - **Unknown / not available:** `/home/rich/metaform-tasks`, where the old Roundtables module lived (cited in `SPEC.md` §11). That path does not exist on this machine. **Verified.**
  - **Unknown / not available:** `RchGrav/tempo`, where the mutation framework lives (cited in `SPEC.md` §11).
  - **Not copied, by design:** the Topogee world, its server and client, and the service launcher. See section 4.
- **Roundtable is a separate project that is closely tied to Metaform.** **Inferred**, from the following evidence:
  - Its functional map is a Metaform map (`roundtable/metaform.json`).
  - It is the main worked example of Metaform layers (`roundtable/docs/egm-map-layers.md`).
  - `SPEC.md` §11 records the owner wanting a roundtable module again: an agent owns a Metaform map and runs a roundtable on it.

## 2. Where it came from

| Destination | Source | Notes |
|---|---|---|
| `metaform/` | `~/topogee/metaform/` at `main` b65dba2 | Working tree, including the git-ignored `verification/latest-schema-check-results.json` |
| `roundtable/` | `~/topogee/roundtable/` | The refined version of `~/roundtable` (owner, 2026-11-08) |
| `context/topogee-repo/` | Selected files from `~/topogee` | Same relative paths as in the repository |
| `context/brain/` | `~/brain/` | All files except `.obsidian/` |
| `context/roundtable-original-2026-11-05/` | `~/roundtable/` | Not a git repository; snapshot of 2026-11-05 |
| `context/roundtable-runs/` | `~/roundtable-runs/` | EGM run outputs, 2026-11-07 |
| `context/claude-memory-topogee-sessions/` | `~/.claude/projects/-home-rich-topogee/memory/` | Agent memory notes |
| `context/git-history/` | Generated from `~/topogee` git | Logs for `metaform/`, `roundtable/`, the supporting documents and all branches, plus `repo-state.txt` |

Git state at copy time (**Verified**, `context/git-history/repo-state.txt`):
- `main` is at b65dba2.
- Four branches are not merged into `main`: dropped-items, entity-id-floor, inventories, ready-persist. None of them touch Metaform or the governing documents.
- A second worktree, `~/topogee-storage`, is on branch `retire-summoned`. It has no Metaform differences from `main`.

## 3. What was copied

### 3.1 In scope (working copies)

**`metaform/`**, 94 files:
- `SPEC.md`, `SPECIFICATION.md`
- `Intake.md`, `Intake.xml`, `intake.mmd`
- the schema, the tool contract and the examples
- `validate_metaform.py`, `tests/`, `verification/`, `tools/`
- `agents/`
- `docs/`: designs, the EGM review, the preprint, the documentation set, concepts, proposals
- `rust/`: three crates
- `server/`: the Node test harness

**`roundtable/`**:
- a Rust workspace of five crates (bus, acp-host, roundtable, roundtable-web, agent-monitor)
- the TypeScript adapter `adapters/openrouter-acp`
- docs, including the EGM layer work
- `metaform.json`

### 3.2 Supporting context: `context/topogee-repo/`

These were chosen because Metaform documents cite them, or because they hold the owner's decisions and statements about Metaform.

- **Governance and decisions:**
  - `AGENTS.md`, `CLAUDE.md`, `DECISIONS.md`, `DEVELOPMENT.md`, `README.md`
  - `TOPOGEE.md`, the owner's opening statement. It uses "Topogee" for Metaform.
  - `TASTE.md`, `EXPECTATIONS.md`
  - Their editor backups (`*.md~`), which differ from the current files.
- **The stray root `Intake.md`.** It is untracked and older than `metaform/Intake.md`. It is kept only as evidence. See C-2.
- **Owner statements and onboarding:**
  - `docs/README.md`, `reading-the-top.md`, `pushback.md`, `countermeasures.md`, `claims.md`, `why.md`
  - `address-only-example.md`, `owner-statements-2026-10-30.md`, `owner-statements-2026-10-31.md`, `owner-explanations.md`
  - `owner-design-guidance.md`, `taste.md`, `trouble-log.md`
- **Designs:**
  - `docs/designs/storage.md`, the storage design for Metaform maps. It also covers world storage.
  - `service-launcher.md`, which covers how the launcher starts the Metaform server.
  - `cli-design.md`, which covers the `topogee metaform …` commands.
  - `world-system-spec.md`, kept only because it is the subject of the one real Rust-store intake and states how Metaform stays outside the world.
- **Evidence:**
  - `reference/` (all of it). It is hash-locked by `source-register.json`.
  - `tools/verify_bootstrap.py`, `.github/workflows/validate.yml`, `.mcp.json`, `.codex/config.toml`
- **Process records:**
  - `_bmad-output/`, the forge session that designed the tool vocabulary, and the draft "Topogee Navigator" initiative requirements.
  - `.design-review/`, the reviewer's board.
  - The roundtable spec-review session `docs/roundtables/session-20261104-24c67015/`, with its `19-…` folder, analysis and review.
- **Agent definitions:** `.claude/agents/metaform-intake.md`, `metaform-layer.md`, `.claude/skills/metaform/`, `topogee-dev/` and `data-expert/`.
- **Experiments:** `metaform-crash`, `ladybug-concurrency`, `map-viewer`, `intake-runs`, `intake-blocks`.

### 3.3 Excluded on purpose

| Excluded | Reason |
|---|---|
| `metaform/rust/target/` (3.6 GB), `metaform/server/node_modules/` (140 MB), `__pycache__/` | Build output and dependencies |
| `~/topogee/topogee/` (world crates, client, content, 114 GB target), `~/topogee/launcher/` | Separate projects. Metaform has no code dependency on them (**Verified**: no Cargo or npm path dependencies leave `metaform/`). The launcher is an optional runtime tie (section 5.4). |
| World designs, world roundtables (1, 4–7, 20, session-20261105), `docs/world-ideas.md`, block-damage statement, `experiments/agent-crash`, `world-crash` | Topogee world only |
| `_bmad/`, `.agents/skills/bmad-*`, `skills-lock.json`, `.v6-v7-migration-backup-*` | BMAD tooling, not Metaform |
| `~/roundtable/archaeology/` | The older Python Roundtable. The owner pointed to the Rust one. |
| `~/roundtable/target/`, `review/round3/probe/target/`, `review/round3/alloyed-tmp/`, `adapters/openrouter-acp/dist/` and `node_modules/` | Build output and test temporaries |
| Three ELF test executables in `~/roundtable/review/` (`round3/alloyed-engine-probe`, `round2/env-order`, `round2/scope-dangling`) | Compiled binaries. Their `.rs` and `.log` files are kept. |
| `~/topogee/~/.metaform-rust/` | A stray folder holding an empty `server.lock`. A `~` path was not expanded. **Inferred.** |
| `~/brain/.obsidian/`, `*:Zone.Identifier` | Editor and Windows metadata |
| Runtime map databases: `~/.metaform/` (Node harness: projects topogee, roundtable, topogee-roundtable), `~/.metaform-rust/` (Rust server: project topogee, holding the intake of `world-system-spec.md`, 61 elements and 114 wants per `.design-review/README.md`), `~/.topogee/map.lbug` (oldest) | Machine-specific live stores. Copying a live database with its WAL could give an inconsistent copy. They hold the only real intake results. The owner does not need those past results kept or exported (owner decision, 2026-11-08), so they were not copied. |
| Session transcripts (`~/.claude/projects/*`, 20 `~/.codex/sessions` files that mention Metaform, 2026-10-31 to 2026-11-07) | Large and personal. The Codex sessions were **not reviewed**. |

No credentials were found in the copy. **Verified:** a pattern scan found only the test placeholder `"test-key-not-real"` in the Roundtable adapter tests. Roundtable needs `OPENROUTER_API_KEY` in the environment. **Stated** (adapter tests and README).

## 4. Relationship to the wider repository

| Part of `~/topogee` | Relationship to Metaform |
|---|---|
| Topogee world (`topogee/`, `docs/designs/world-*`) | Separate product. It mentions Metaform only in comments. **Verified.** The world spec was used as an intake test subject. |
| Service launcher (`launcher/`, C, from HoldOn) | The Metaform server can start through it (`metaform/rust/crates/metaform-server/src/start.rs`: the `METAFORM_LAUNCHER` variable or `hold` on PATH; it requires the `topogee/services` store). The launcher has no Metaform code. **Verified.** |
| Roundtable | Copied here. Its map is a Metaform map. |
| Repository governance (`AGENTS.md`, `CLAUDE.md`, `DECISIONS.md`) | Governs both products. About 80% concerns Metaform. **Inferred.** |

## 5. Technical setup

### 5.1 Languages and components

| Component | Path | Language and stack | Status |
|---|---|---|---|
| Map server (the design) | `metaform/rust/` | Rust, edition 2024. Crates: `metaform-core` (model, naming, validation, commands), `metaform-store` (LadybugDB graph, fair writer), `metaform-server` (`metaform` binary: `serve`, `mcp`, `call`, `settings`). rmcp 3.9, MCP protocol 2026-07-28. | Partly built. **Stated** (`metaform/docs/designs/metaform-rust.md` "Progress"). |
| Node test harness | `metaform/server/` | TypeScript, `@topogee/mcp-server`, Ladybug 0.22.0, MCP SDK 2.4.0 | "Not the design and never a source for it." **Stated** (`DECISIONS.md`, owner). |
| Contract validator and tests | `metaform/validate_metaform.py`, `metaform/tests/*.py` | Python 3.12+ | 29 contract tests per `verification/bootstrap-status.json`. **Stated.** |
| Roundtable | `roundtable/` | Rust workspace with five crates, plus a TypeScript OpenRouter ACP adapter | Working system per its docs. Not run here. |

### 5.2 What is built in the Rust server

**Stated** (`metaform-rust.md` Progress and `.design-review/README.md`). **Not verified by running.**

- **Built:**
  - the map model and commands (add, update, delete, orphaned, reads)
  - the Ladybug graph store: `Element` nodes with `CONTAINS` and `WANTS` edges, with maps as partitions of a project database
  - one server per home, with stdio forwarders over `<home>/server.sock`
  - a fair writer, and writes that survive SIGKILL
  - `goto`
  - change announcements
  - standalone maps (`mcp --map`)
  - settings (`settings.json`)
  - `metaform call`
  - start through the launcher
- **Not built:**
  - layers and the layer walk (wait on the owner's "unified layer approach")
  - chaining (waits on the owner's contract decision)
  - skills push
  - tasks
  - search
  - the memory module
  - the refusal codes of R-5.24
  - the `direction` field and its value names (formerly `intent`)

### 5.3 Build and test commands

These were run from this folder on 2026-11-08, after preparation. **Verified.**

```sh
python3 metaform/tests/check_contract.py          # 30 tests, OK
python3 metaform/tests/check_tool_input.py        # 13 tests, OK
python3 tools/verify_bootstrap.py                 # PASS (see below)
(cd metaform/rust && cargo build --release -p metaform-server --offline)   # OK, 31 s from the local crate cache
(cd metaform/rust && METAFORM_LAUNCHER= cargo test --offline)              # core 4, store 6, server 13: all pass
```

- **Server smoke test.** `metaform call` against a throwaway home: `add`, the index read `{".": {}}` and `orphaned` all returned the expected results.
- **Python version.** The checks passed with the system Python's jsonschema 4.10.3. `requirements-dev.txt` pins 4.26.0.
- **Not run:**
  - `(cd metaform/server && npm test)`. It needs `npm install`, and the Node harness is not the design.
  - Roundtable's build and tests (`cd roundtable && cargo test`).

**`tools/verify_bootstrap.py` at the root** is a port of the original, which is kept unchanged in `context/topogee-repo/tools/`. It checks four things:
- the 121 preserved-source hashes, read from `context/topogee-repo/source-register.json`
- that every `context/` file still matches `MANIFEST.sha256`, because `context/` is read-only
- portable links. A link in `metaform/*.md` that resolves under `context/topogee-repo/` at its old repository path counts as relocated.
- the exact schema, tool and skill appendices in `SPECIFICATION.md`, plus the presence of the required files

`.github/workflows/validate.yml` runs the same three Python checks, on Boat, as the original did. It will run only once this folder has a GitHub remote.

### 5.4 Configuration and runtime ties

- **MCP registration.** `.mcp.json` at the root, added 2026-11-08, is the original configuration unchanged:
  - `boat-docs`
  - `metaform`, which runs `metaform/rust/target/release/metaform mcp --home ${HOME}/.metaform-rust --project .`
  - Because `--project .` now names this folder, agents here get their own project map in the shared home `~/.metaform-rust`. The map of `~/topogee` stays as it is.
  - Rebuild the release binary after any server change.
  - `.codex/config.toml` is copied unchanged.
- **Home folders.** `~/.metaform-rust` belongs to the Rust server. `~/.metaform` belongs to the Node harness, and the Rust server refuses it.
- **Environment variables:** `METAFORM_LAUNCHER` (optional) and `OPENROUTER_API_KEY` (Roundtable). The values are not recorded here.
- **Broken tool:** `experiments/map-viewer/server.mjs` runs `../../mcp-server/src/main.ts`, which no longer exists. It is now `metaform/server`. **Verified.**
- **Absolute path:** `experiments/intake-blocks/` reads `/home/rich/brain/Intake.xml` by absolute path and checks its sha256. **Stated** by the workflows review.

### 5.5 Architecture in brief

**Stated** across `SPEC.md` §2–5 and `TOPOGEE.md`.

1. An intake agent runs the owner's procedure (`metaform/Intake.md` 3.1) on any artifact: code, specification, manual or screenplay. It records the project's functional form as a tree of dotted addresses.
2. Each element has `technical_name`, `name`, `role`, `uri`, `status` and `wants`.
   - `role` is one of Definitive, Supportive, Notable or Divergent, and exactly one element is Definitive.
   - `wants` is a dictionary keyed by provider address. Each entry holds `why` (OP), `how` (EF) and `direction` (IFD; called `intent` in the current intake, schema and code).
3. One map server per home owns the store. Agents reach it through a stdio forwarder and one MCP tool, `project-map`.
   - The tool takes JSON commands: `add`, `update`, `delete`, `orphaned`, addressed reads and `goto`.
   - Agents see the form, never the store (R-2.1).
4. Non-functional knowledge is kept apart from the functional map as layers on the same addresses: sources, skills, memory, tickets and inbox. A context resolver composes what an agent at an address needs (`TOPOGEE.md` §2–3). Layers are not built yet.
5. Planned and not specified yet: the Composer and Facilitator pipeline, ACP harness control, agent inboxes, and the context-threshold handoff (`TOPOGEE.md` §4–5, `SPEC.md` §11).

## 6. Which document governs what

**Stated** precedence (`DECISIONS.md` "Source precedence"): current owner decisions, then the current specification, then labelled technical proposals, then preserved historical evidence. "Later founder corrections govern earlier documents."

| Subject | Governing document | Last changed |
|---|---|---|
| Specification the build follows | `metaform/SPEC.md`. Status line: "The founder has not reviewed this document." | 2026-11-08 |
| Owner decisions | `context/topogee-repo/DECISIONS.md`. Later sections override earlier ones. | 2026-11-07 |
| Owner's design source | `metaform/docs/documentation-set.md`. **The owner's copy in `context/brain/` is newer** (C-6). | Imported 2026-11-07 (from the 2026-11-02 version) |
| Intake procedure | `metaform/Intake.md` (Digital Typology Intake 3.1). Protected. | 2026-11-07 |
| Stored-document schema | `metaform/metaform.schema.json` | 2026-11-07 |
| Tool contract | `metaform/mcp-tools.proposed.json` | 2026-11-07 |
| Rust server design | `metaform/docs/designs/metaform-rust.md`. Agent draft, not reviewed. | 2026-11-08 |
| Storage | `context/topogee-repo/docs/designs/storage.md` | 2026-11-08 |
| Opening statement | `context/topogee-repo/TOPOGEE.md`. The owner's text; uses old names. | 2026-11-02 |
| Older draft | `metaform/SPECIFICATION.md` | Superseded where it conflicts |
| Superseded designs | `metaform/docs/designs/metaform-server*.md` | Carry a "Storage superseded" banner |
| Roundtable functional spec | `roundtable/README.md` | 2026-11-07 |

## 7. Conflicts and stale statements

The answer to "is there one cohesive spec?" is **no**. **Verified.**
- `metaform/SPEC.md` is the most current and is mostly consistent with itself.
- The repository-level guidance files (`AGENTS.md`, `DEVELOPMENT.md`, `docs/README.md`, the early sections of `DECISIONS.md`) still describe the state of 31 Oct to 3 Nov.

Each item below was checked against the files. File references are to the copies here.

| # | Conflict | Newer side | Resolved? |
|---|---|---|---|
| C-1 | **Server language.** `DECISIONS.md` "Technical choices still to make" still lists the runtime language (Python, Node or hybrid) as open, and its "The chassis" section (3 Nov) says the map server "stays a standalone Node MCP server". | `SPEC.md` R-4.6, "Decided 2026-11-07: Rust", although its status line still begins "Proposed". `DECISIONS.md` "The Node server is a test harness". | Yes, by later text. The old lines were never edited. Also stale: `AGENTS.md`, the original `README.md` and `verification/bootstrap-status.json` ("runtime_language: not selected"). |
| C-2 | **Current intake prompt.** `DECISIONS.md` (sections of 31 Oct and 3 Nov), `AGENTS.md`, `DEVELOPMENT.md` and `docs/README.md` say `Intake.xml`. | `metaform/Intake.md` 3.1 (`SPEC.md`, `CLAUDE.md`, `metaform/README.md`). Later `DECISIONS.md` calls `Intake.xml` "the tested record from before the change". | Yes, in practice. The stale untracked root `Intake.md` (old goal, function and ICE wording) has been carried into `metaform/Intake.md`. **Verified.** |
| C-3 | **Storage layout.** This changed five times:<br>1. JSON files (3 Nov, recorded as decided)<br>2. one `project.lbug` per project (documentation set; `CLAUDE.md`)<br>3. one database per map (commit ee41126; `AGENTS.md`)<br>4. maps as partitions of the project database (`SPEC.md` R-4.1, `storage.md` 2.2)<br>5. `DECISIONS.md` still also says "JSON is the default" | Partitions (2026-11-07 17:08), marked as a default "for the founder's confirmation" | **Open:** waits for owner confirmation (D-17). |
| C-4 | **Direction (formerly intent).** `SPEC.md` R-3.6 (Decided) names the field `direction` (owner decision, 2026-11-08) with the values `inbound`, `outbound` and `two-way`. | The schema, the contract, `metaform-canonical.json`, `Intake.md`, both servers and the stored maps still use `intent` with `send`, `receive` and `send_receive`. | **Open:** decided but not applied. Applying it needs the owner's instruction for the protected files. Note that `SPEC.md` D-2 says it is closed by R-3.6. |
| C-5 | **Old vocabulary in `TOPOGEE.md`.** It uses roles CQU, DE, SE and NE, plus `name_length`, `goal` and `function`. The current terms are Definitive, Supportive, Notable and Divergent, `technical_name`, `why` and `how`, and CQU is not a role. | Current terms | **Owner's call:** agents may not edit `TOPOGEE.md`. Old terms also remain in `metaform/docs/metaform-concepts.md`, `DEVELOPMENT.md` and the initiative draft. |
| C-6 | **The owner edited the documentation set after it was imported.** `context/brain/Universal Intake & Layer Architecture Documentation Set.md` (11-07 16:06) differs from `metaform/docs/documentation-set.md`:<br>- In the §6.4 example, `wants` changed from an array to a dictionary.<br>- Root `skills` lost its brackets. The result is invalid JSON, and it contradicts `DECISIONS.md` ("root `skills` stay lists"). | Brain copy | **Open.** The project copy is stale. `DECISIONS.md` and `SPEC.md` §11 call it "unchanged". |
| C-7 | **The owner's query note is newer than the project copy.** `context/brain/mcp_query.md` (11-01) adds a query item, and a definition of `name` as an alias that differs from the address term. `metaform/docs/mcp-query-source.md` is the older backup. | Brain copy | **Open.** The "alias" definition appears nowhere in `SPEC.md`. |
| C-8 | **Product name.** `DECISIONS.md` "Settled requirements" says "Product: Topogee Navigator", and so do `SPECIFICATION.md` and the initiative draft. | `DECISIONS.md` 11-07: two products, Topogee (world) and Metaform (context tool). | **Owner's call** (left open explicitly). `SPEC.md` is titled "Topogee Specification" on purpose, because `topogee` is the umbrella command. |
| C-9 | **Commands that do not exist.** `DECISIONS.md` says the Metaform server "already has CLI commands … `topogee metaform server status \| stop \| restart`". | No such code exists. It is only in the `cli-design.md` draft. **Verified.** | Stale claim. |
| C-10 | **`SPEC.md` vs `SPECIFICATION.md`.** `DECISIONS.md` line 3 and `AGENTS.md` point to `SPECIFICATION.md` as the full or current spec. `SPECIFICATION.md` points to `TOPOGEE-SPEC.md`, a file renamed to `SPEC.md`. | `SPEC.md` | Yes (`CLAUDE.md`, `SPEC.md`), but the pointers are stale. |
| C-11 | **Rust documentation lags the code.** `rust/README.md` and `metaform-rust.md` §1 say "two crates" (there are three). `rust/README.md` says announcements and the launcher start are not built, while the Progress table says they are. `metaform-rust.md` shows a `registry.json`, but the code keeps the registry in `metaform.lbug`. | Code and Progress table | Documentation drift. |
| C-12 | **Settings storage.** `SPEC.md` R-4.8 says global values are in the main database, then that they move to `settings.json`. | The code uses `settings.json`. | Text inconsistent within R-4.8. |
| C-13 | **Root scopes.** The procedure lists seven, including `collection`. The documentation set lists six. | Not resolved | **Open** (D-11). |
| C-14 | **`un_built` vs `not_built`.** The owner said "MISS is now not_built" (`owner-statements-2026-10-30.md`). | The repository and the owner's later `intake-new.md` both use `un_built`. | **Probably settled. Inferred.** |
| C-15 | **Supportive definition.** `SPEC.md` R-3.13 uses `roles.md` wording. `Intake.md` keeps its tuned DE/SE/NE definitions under the new labels. | Deliberate (`DECISIONS.md` "technical_name and the four roles") | The two texts differ. Worth a look. |
| C-16 | **`TOPOGEE.md` line 16 (Intent)** was changed by an agent from the owner's `receives`/`sends`/`send-receive` wording. | Matches the owner's later intent decision | Edit made in a file reserved to the owner. **Authorization inferred.** |
| C-17 | **Settled requirements that are not Metaform.** `DECISIONS.md` "Settled requirements" includes Topogee-world and other items: camera and depth sensors, peer scoring, agent launch, WebTransport. | n/a | Scope mixing. Only the items on the namespace, wants, naming, intake, storage, the one tool and progressive delivery are Metaform. **Inferred.** |

Also noted:
- **Verified:** one file in `context/brain/recovered/` fails its own `SHA256SUMS` check (`commit-copies/2026-10-12_06edcf80e741/rich/intake.xml`, which holds the older v1.1 prompt).
- **Stated by the agent notes only:** the memory notes in `context/claude-memory-topogee-sessions/` hold owner intent not recorded elsewhere:
  - Intake terms need about 8,000 tokens before they make sense.
  - The "patches" model: one clarification per observed failure.
  - An unfinished field-list design.

## 8. How the work was done: workflows

**Verified** from session transcripts: the Claude Code Workflow tool was never used. The "workflows" were these processes:

| # | Date | Process | Output (location here) |
|---|---|---|---|
| 1 | 10-30 | Bootstrap source audit (BMAD PM plus three agents) | `context/topogee-repo/reference/`, `source-register.json`, `DECISIONS.md`, `DEVELOPMENT.md` |
| 2 | 10-31 | BMAD forge "mcp-intake-tool-design": tool vocabulary and the one-tool decision | `context/topogee-repo/_bmad-output/forge/` |
| 3 | 10-31 | BMAD initiative ("Topogee Navigator" draft requirements R1–R18, not confirmed) | `context/topogee-repo/_bmad-output/initiative-topogee-navigator/` |
| 4 | 11-01 to 11-02 | Intake trial runs, procedure 3.1, five agents | `context/topogee-repo/experiments/intake-runs/`, `intake-blocks/`. The scratch files are lost. |
| 5 | 11-03 | EGM brainstorm and draft of the map-server design | `metaform/docs/designs/metaform-server-design.md` (**inferred**) |
| 6 | 11-03 | EGM five-stage review of that design. Verdict: not ready to build. | `metaform/docs/designs/egm-review/` |
| 7 | 11-04 | Roundtable 10-panel spec review (map/world link, storage, safeguards) | `context/topogee-repo/docs/roundtables/session-20261104-24c67015/` |
| 8 | 11-07 | EGM elephant and goldfish layers on the Roundtable map, then one roundtable per element, then a resolution check | `roundtable/metaform.json`, `roundtable/docs/egm-*`, `context/roundtable-runs/` |
| 9 | 11-07 to 11-08 | "Xander" design-review loop: Rust build steps, the launcher, and the intake of the world spec into Metaform | `.design-review/`, `metaform/rust/` |
| 10 | 11-07 to 11-08 | "Jorge" data expert: LadybugDB storage and crash tests | `docs/designs/storage.md`, `experiments/metaform-crash`, `metaform/verification/` (**inferred**) |
| 11 | ongoing | CI: `.github/workflows/validate.yml`, run on Boat | Runs the contract tests and `verify_bootstrap.py` |

## 9. Unresolved questions and assumptions

- **Assumption:** `~/topogee/roundtable` is the Roundtable to develop (owner, 2026-11-08).
- **Assumption:** `main` at b65dba2 is the latest Metaform state. No unmerged branch touches it. **Verified.**
- **Verified (2026-11-08):** the Rust server builds and passes its tests here. The Python contract checks pass. Roundtable and the Node harness were not built.
- **Unknown:** what, if anything, to bring in from the earlier private repository. It was renamed to `RchGrav/metaform-archive` on 2026-11-08, when this folder became `RchGrav/metaform`. A review of what fits this project is in progress.
- **Decided:** the live map databases (section 3.3) are not exported into this folder (owner decision, 2026-11-08).
- **Not done:** the Codex session history was not reviewed.

## 10. Suggested next steps for developers

1. Decide the conflicts that need the owner (`OWNER_REVIEW_SPEC.md` §7). Then update the stale lines in the governing documents. Those documents are now in `context/`, so first decide where the live copies of `DECISIONS.md` and `AGENTS.md` belong.
2. ~~`git init`~~ Done 2026-11-08. Commit 1 is the consolidated snapshot. Commit 2 is the standalone wiring. There is no remote yet.
3. ~~Port `verify_bootstrap.py` and CI~~ Done (section 5.3).
4. ~~Build the Rust server and add `.mcp.json`~~ Done (sections 5.3 and 5.4). Restart Claude Code in this folder to load the `metaform` MCP server.
5. Fix `experiments/map-viewer/server.mjs` (dead `mcp-server` path) and the absolute path in `intake-blocks`. These are copies in `context/`, so a fix belongs in a working copy.
6. Add a GitHub remote, so CI runs and the Full Auto push rule can apply.
