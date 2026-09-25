# Build log

One entry per build step of `00-index.md`: the step, the records it satisfies, the tests added, the commit, and the questions it raised.

## Step 1: storage and the data access object

- Records satisfied: STORE-001 to STORE-041 at the data access object, including the settings and module-state tables of the base database, built against the storage text of commit f8dd39a (paged reads, no attachment at a bare type address, `moved` and `stack_at`, `layer_fields`, no transitive flag, list settings one row per member). With them, the storage side of LAYER-001 to LAYER-007, LAYER-010 to LAYER-012, MAP-002, MAP-003, MAP-010, MAP-013, MAP-015, MAP-016, MAP-020 to MAP-022, MAP-030, MAP-031, MAP-044 and MAP-045.
- Tests added: `tests/test_home.py`, `tests/test_store_map.py`, `tests/test_store_layers.py`, `tests/test_store_corrections.py`, `tests/test_store_reads.py`, `tests/test_store_operations.py` (every STORE-024 operation's rows, every listed error, and the query plan of every write), `tests/test_store_exchange.py`, `tests/test_store_challenges.py`, `tests/test_store_concurrency.py`; shared helpers in `tests/storekit.py`. 202 tests, each marked with its requirement and `kind('fixture')`. Whole suite: 264 passed. No existing test was removed in this step.
- Not yet covered: STORE-005's timing thresholds on a store loaded to a million items. The plan test covers every read and write; the timed load is left for a separate run with the storage-proof loader.
- Commit: bbd2fce.
- Questions raised: Q1 to Q8 in BUILD-QUESTIONS.md.

## Step 2: the common base and the module contract

- Records satisfied: BASE-001, BASE-004, BASE-006, BASE-009, BASE-010, BASE-013 to BASE-019, BASE-028 for verbs and event deliveries, BASE-032, BASE-033, BASE-034, BASE-035, BASE-036, BASE-037 and BASE-043 for module verbs; STORE-022, the helloworld history as a layer; MCP-008's load check; CLI-012 and CLI-019 through helloworld's `--loud` and `--favorite`. The template module is now `helloworld`, a new empty `template` sits beside it, and both ship disabled.
- Tests added: `tests/test_base.py` (contract, discovery refusals, lifecycle, events, per-verb systems, READMEs), `src/metaform/modules/helloworld/tests/test_helloworld.py`, `src/metaform/modules/template/tests/test_template.py`; pytest collects `tests` and `src/metaform/modules`. Shared fixtures moved to the root `conftest.py`. Whole suite: 268 passed.
- Tests removed, because the spec replaces what they protected: `tests/test_map.py` and its fixture (XML import of an intake result, which the spec forbids; the map module is rebuilt in step 4), `tests/test_mcp.py` (the single `nouns` array schema, replaced by MCP-003; rebuilt in step 6), `tests/test_modules.py` (the old template demo, replaced by the helloworld and base tests).
- Commit: 5ff5870.
- Questions raised: Q9 and Q10.

## Step 3: CLI and settings

- Records satisfied: CLI-001 to CLI-025 and CLI-027 to CLI-033, CLI-026 kept (settings screen retested), PROJ-002, PROJ-003 with D57 (a project's folder stops a selection made above it), PROJ-007 (`folder=<path>`), BASE-029, BASE-031 (exit codes, Ctrl+C cancels an async verb), and the CLI side of STORE-027 and STORE-028 (`export`, `import`, `query`). `--commands` is now `--modules`; `--layers` is the starting selection; `unset all` resets only what is stored at the folder, D36.
- Tests added: `tests/test_cli.py`, 49 tests. `tests/test_settings_cli.py` was removed: the spec replaces its page header form, its `enable module <id>` grammar, its value-style booleans and the `--commands` name, and every requirement it protected is now in `tests/test_cli.py`. Whole suite: 295 passed.
- Not built: `metaform import wheel=<name>-<version>`, BASE-025, which the first working test does not use.
- Commit: 9b0e2d0.
- Questions raised: Q11 and Q12.

## Step 4: the map and layer records and operations

- Records satisfied: BASE-038, the `map` module, shipping enabled with every verb of its table and `--raw`; MAP-010, MAP-011, MAP-012 (readings and short names), MAP-014 (roots as data in `roots.json`), MAP-022 and MAP-044 through the module; LAYER-006, LAYER-007, LAYER-008, LAYER-015, LAYER-016, LAYER-018 and LAYER-019 end to end on the CLI. Select and mask resolution and the direct reads are the data access object's, built in step 1.
- Tests added: `src/metaform/modules/map/tests/test_map.py`, 10 tests; one grammar case added to `tests/test_base.py`. `src/metaform/modules/` is now a package, so a module's settings stay its own however it is imported. Whole suite: 305 passed.
- Commit: e0c8596.
- Questions raised: Q13 and Q14.

## Step 5: the memory module

- Records satisfied: BASE-040, LAYER-012, LAYER-013 and STORE-020 through the `memory` module, shipping enabled: the nine reference operations at elements, joins and subtypes; the memory layer made on the first write, recognized by its kind, with no provenance; relations shown when opening either end; memory masked and selected like any layer; D18, an entity named that the map does not hold becomes an element in the memory layer.
- Tests added: `src/metaform/modules/memory/tests/test_memory.py`, 9 tests. Whole suite: 314 passed.
- Commit: f2dd73d.
- Questions raised: none.

## Step 6: the MCP module

- Records satisfied: MCP-001 to MCP-008 and MCP-025; BASE-003 and BASE-026 (`mcp` is the module's dependency, no longer the chassis's); BASE-028 for tool calls; BASE-036 and STORE-023 (the CLI's `--json` and the tool return the same data); PROJ-005 (a server outside every project selects one with the `set` tool); LAYER-018's access by tool. The chassis `mcp` verb and `mcp_server.py` are gone; `metaform mcp serve` belongs to the `mcp` module. The public base gained the registry, surface, instructions and context functions the module needs, so it has no private access.
- Tests added: `src/metaform/modules/mcp/tests/test_mcp.py`, 11 tests through real protocol traffic with the SDK's client; the chassis import test now also blocks the `mcp` library. Whole suite: 325 passed.
- Commit: e05036b.
- Questions raised: Q15 to Q17.

## Step 7: the intake module

- Records satisfied: BASE-039, MAP-040, MAP-041, MAP-042, MAP-043 and MCP-009, with LAYER-001 and STORE-032 for the intake layer. `intake prompt` serves the stored text with only its `<target>` attributes filled and `{project_id}` replaced, then the submit line; `intake submit` checks the whole submission, lists every problem with its path, and stores it in one atomic write as `intake-<timestamp>-<hex>`; the status hook gives `Intake: none yet` with the notice, or `Intake: complete`. `resources/Canonical_Intake.xml` is a byte copy of the specification's file.
- Tests added: `src/metaform/modules/intake/tests/test_intake.py`, 10 tests, and the fixture `tests/fixtures/intake_timer.json`. Whole suite: 335 passed.
- Commit: 2acf1f7.
- Questions raised: Q18 and Q19.

## Step 8: the installer, the skill and the build

- Records satisfied: MCP-010, MCP-013 to MCP-019, MCP-021 and MCP-023; BASE-021 to BASE-026, BASE-041 and BASE-042 (the build the first working test runs). `metaform install` checks the system, Python, uv and the source first, lists every known tool with unverified ones marked, previews each change with its backup, registers `uvx --from <wheel> metaform mcp serve`, copies the one fixed skill, proves every registration with `metaform.probe`, and ends with one next step; a re-run replaces its entry. `metaform build` writes the wheel with `zipfile`, carries pure-Python dependencies from `uv pip compile` and `uv pip install --target`, and names each compiled one with the module that needs it. `metaform --version` answers without discovery.
- Tests added: `tests/test_install.py` (10 tests, with the fake tools of `tests/fakes.py`) and `tests/test_build.py` (6 tests, including `uvx --from <wheel>` and `pip install` of the wheel). Whole suite: 351 passed.
- Not built: `metaform uninstall`, MCP-020, and the terminal checklist screen of MCP-014 beyond a line prompt; D41 leaves repair and uninstall out of the first test. MCP-022 needs each real tool and is not automated.
- Commit: c86bc51.
- Questions raised: Q20 to Q23.

## Step 9: the first working test

- Records satisfied: MCP-024, automated as a simulation: `metaform build`; `metaform install claude codex cursor` against fake Claude Code and Codex executables and a real Cursor file with its byte-identical backup; the skill copies; a passing proof through the real `uvx --from <wheel> metaform mcp serve`; a project registered with no intake; a connection whose instructions hold the base text, the sections of intake, map, mcp and memory, and the no-intake notice; `intake_prompt` equal to the stored file but for its target; a submission missing one purpose refused whole with the notice kept; the corrected submission stored; a new connection without the notice; the tool list holding every tool the record names; memory written at the DE element and at a join on one connection and opened on a second; `map_mask` of the memory layer at the element's address hiding it from `map_node` until `map_clear`, with the join's memory following its receiver's address.
- Also: every test now names its requirement and its kind, and collection fails on a test that does not or that names an ID absent from the spec, QUAL-009, QUAL-014 and E4.
- Tests added: `tests/test_first_working_test.py`, 1 test, about 14 seconds with a warm uv cache. It was written after steps 1 to 8, whose parts it drives end to end, so it passed when first run. Whole suite: 352 passed.
- Not done: MCP-024's recorded manual run in a real AI tool. It needs a person, or a host session, with a real Claude Code or Codex, and it would write that tool's real user configuration, which this build does not touch. QUAL-014 counts the first working test done only with that real run.
- Commit: 2cf8fd2.
- Questions raised: none new.

## Test-gaming review, after step 9

- A review agent given only the spec records and the tests, QUAL-007, flagged 22 items. Fixed: STORE-028's mask now checked on `query`, `map` and the MCP read; the event tests read the subscriber's stored effect and a second subscriber witnesses helloworld's event; MCP-007 compares sections with the enabled modules exactly; `uvx --from <wheel> metaform mcp serve` is proved; the direct-run test runs `help`, `set`, `export` and `import`; a build with no modules is checked for compiled files; a one-call override and the `set` tool against the CLI; `--json` with messages and a stray warning on standard error; BASE-006, BASE-009, BASE-016 and BASE-035 checked over MCP; the caution refusal over MCP leaves the history; the AST check of `sqlite3` imports covers every module; filler asserts and misplaced requirement marks removed (MAP-014, MCP-011, BASE-003, BASE-023, BASE-028, LAYER-013 on those tests); the unrecorded provider-mask assertion removed from the first working test.
- Left open: the settings screen tests drive the screen's methods rather than key presses (CLI-026); the Ctrl+C test is POSIX only and does not check partial writes (BASE-031, QUAL-010); no test installs a different Metaform version to compare byte for byte (BASE-023); STORE-005's timing medians; an import killed as a process rather than failing (STORE-006); `--layers` on one CLI call (CLI-033); a changed declared default (CLI-023); a concurrent reader during an intake (BASE-039).
- The review found one real defect report, Q24. Whole suite: 355 passed.


## Step 10: intake and reporting, stable first

Done first, at Rich's priority, as its own step.

- Records built: BASE-039 as now written: `intake_submit` never refuses a submission for its content, stores what does not fit as given and names each part in a notice with its path, stores a second intake as a new active metaform `intake-<UTC timestamp>` and keeps the first whole, saves `report` and `feedback`, writes finding flags, and returns the metaform and the findings count with the notices. BASE-044 for the intake path and for `add_element`, `add_join` and `add_subtype` (an address out of form, a provider that names no element, a self join, a join to a subtype's address, a subtype's purpose, role or held address are stored as given with a notice; a join end given as an unknown id and a subtype with no join still stop, since they cannot be stored). BASE-045, STORE-043 and STORE-016 refs: `metaform feedback`, `metaform list reports`, `metaform read report`, the tools `feedback`, `list_reports` and `read_report`, files under the home, one `reports` row each, appended sections, layer provenance refs, and all three on every surface. MAP-046 and STORE-042: `findings` rows, `flag` and `flag_note` on every element, join and subtype read, `map findings`, flags through `map knowledge`. STORE-009 `element_roles` and STORE-025 `roots`: `map roots`, and `map where ''` returning the same. CLI-034: chassis `--debug`, default off, and `--report`, default on; the intake footer carries the stop rule always, the report line with `--report`, the feedback line with `--debug`; MCP-007's instructions always carry the stop rule and add the feedback request with `--debug`. The trouble report is always asked for, per section 04 question 12. MCP-008's new map text and the intake status line `Start with: metaform map roots`. STORE-041: a taken metaform name is numbered with a notice.
- Findings fixed: C1 (`elements` as text over MCP is one notice; no file or standard input is read), H1 (every tool call's nouns and switches are checked by kind as the CLI checks them, with the CLI's next step; the `set` tool checks its values; unknown arguments are noticed), H2 (a second intake becomes a new active metaform, never a duplicate in the first), H8 (an import document is checked whole before anything is written, every problem named with its path, and the SQL names only the store's own columns).
- Defects fixed: D13 (`map roots`, the entry in the map instructions and in status), D20 (`mcp serve` runs on any surface; narrowing narrows its tools).
- Tests: `src/metaform/modules/intake/tests/test_intake.py` rewritten from the refusals to the notices; new `tests/test_reports.py` and `tests/test_store_entry.py`; added to `test_mcp.py`, `test_store_reads.py`, `test_store_exchange.py`, `test_store_operations.py` (a table of every write that stores with a notice), `test_home.py` and `test_store_map.py`; `test_first_working_test.py` follows MCP-024 as now written (stored with a notice, flags, report, feedback, `list_reports`, `read_report`, `map_findings`, `feedback`). Every new test was run and seen failing before the code: 30 failed, 23 passed. Whole suite: 376 passed.
- Questions raised: Q26 to Q37.

## Step 11: high findings H3 to H7, H9 and H10

- Findings fixed:
  - H3: `search` and `links_to` apply select, mask and hiding at each item's node in context, and a named layer narrows and never widens; `search` takes `raw`. `layer_items` reads a named layer directly, LAYER-008, and with `in_context=True` as an agent's context read; the memory module's `read-graph`, `search-nodes` and `open-nodes` read memory in context. LAYER-006, LAYER-007, STORE-019.
  - H4: an async CLI verb's spawned tasks are cancelled and waited for on its own loop, and its async generators shut down, before the loop closes; shutdown then finds nothing running and calls `stop`. BASE-018, QUAL-010.
  - H5: one unload procedure: cancel the tasks, wait for each on its loop, then `stop` in `try/finally`; a failing `stop` is the module's problem in `list modules`, and its settings and code are withdrawn either way. `unload_async` awaits instead of blocking.
  - H6: unload drops the package and every submodule from `sys.modules`, for every place, so a reload runs changed submodules and an entry-point module's settings return with every load. CLI-024.
  - H7: import checks the document, the target project of each metaform and each metaform's owner before writing; writes each store in an open transaction, commits the base database, then each store; on any failure rolls every store back and removes every store file it created. Registration refuses a folder another project holds, by name, through `path_key`. STORE-027 as now written: missing `requires` are stored orphaned with a notice naming each and the next step.
  - H9 in part: discovery checks each `DEPENDENCIES` requirement is installed before import and reports a missing one as the load problem, BASE-015. The repository wheel's own dependencies are Q38.
  - H10: `probe` creates its session inside its own `try` and always stops the server; a failed proof keeps the server's standard error in its reason. MCP-017.
- Tests: new `tests/test_lifecycle.py`, 12 tests, each seen failing first (8 failed); `test_store_exchange.py`'s layer-limited import follows STORE-027's notices. Whole suite: 386 passed.
- Questions raised: Q38.
