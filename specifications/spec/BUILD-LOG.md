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

## Step 12: notices everywhere, and the data access object split

Started by the stopped fix pass, reviewed and finished in the next session.

- Records built: BASE-044 and STORE-026 through every write of STORE-024: nothing is refused for its content. What does not fit is stored as given with a notice: an empty variable, a layer without provenance (an empty record), a taken layer name (numbered), text that is not text (its JSON text), an `extra` that is not an object (`{"value": ...}`), a list of answers or of records (one item each), a role on a knowledge layer's element (kept in its descriptor, no role), an item, property or plan at an address or type address with no element (one is made in the writing layer, STORE-008), a property on a join or subtype (orphaned), a link or target id that names nothing (orphaned), a C answer without its link, an answer outside a blind-spot layer or after approval, a select or mask at an address out of form, a removal of something still used (what used it is orphaned). An operation aimed at something that cannot change writes nothing and returns a notice naming the operation that does: the intake after its write, a finished correction layer, memory through the knowledge tool, finishing twice, discarding the intake, memory or a stacked correction, peeling a knowledge layer or one below the top, hiding a layer that is not hideable, selecting, masking or hiding a correction layer, a correction in a knowledge layer or of a knowledge layer's thing, a correction's receiver key. Only a reference that names nothing, an unreadable argument and `approve` raise. STORE-017 and STORE-034: `finish` never refuses a correction layer; a retype onto an address another current element holds, or that an earlier retype of the layer took, stays unapplied in the new `unapplied` table, and what a removal leaves pointing at nothing is orphaned and named. LAYER-001: an object sent without a layer goes to a new building layer `unnamed-<UTC timestamp>`, owned by the calling module, Q40. LAYER-002, LAYER-010. BASE-043: an unknown `name=value` on a verb with an `extra` noun is kept in the record's `extra` with a notice, on the CLI and over MCP. CLI-033: `set --layers` keeps a name that is neither a layer nor a tag, with a notice, and it turns nothing on; a setting's check can now return notices, which `set`, the `set` tool and the settings screen show. STORE-027 carries `unapplied`.
- Findings fixed: M3 (ill-typed values are stored as JSON text with a notice), M4 (a role only on the intake's and corrections' elements), M5 (peel deletes the `remove` rows its relocations wrote, marked `generated: relocation`, and its `unapplied` marks), M7 (`store.py` is the facade; `writes`, `layering`, `challenges`, `reads`, `views`, `rows` and `paging` hold the operations, each taking the open `Tx`), M11 (a layer's properties page on `(element_id, property_id)` through the extended index; `search` resumes after rank and row), L5 (an edit onto a subtype's address is stored with a notice).
- Also: the map verbs `remove` and `discard` return the store's result, BASE-038, instead of claiming a removal a notice may have declined; `hide`, `tag` and the selection verbs report the real state with the store's notices; the memory verbs return the store's notices; `effective_selection` reads an address out of form as given, since a select there is stored as given; `receiver` reaches a correction so it is named in a notice instead of dropped.
- Spec: STORE-017 names the `unapplied` table and peel's notice; STORE-024 says its last column is notices; STORE-027 lists `element_roles`, `findings` and `unapplied` in the document.
- Tests: the stopped pass rewrote the refusal tests to notices (`test_store_operations.py`'s table of 51 conditions, `test_store_layers.py`, `test_store_corrections.py`, `test_store_challenges.py`, `test_map.py`, `test_memory.py`, `test_cli.py`); with `store.py` unwired they failed, 71 in all. Two older tests in `test_store_map.py` still expected refusals the spec now turns into notices, STORE-008 and STORE-026, and were rewritten to the spec. Added, each seen failing first: two retypes onto one free address, and an unapplied retype through export and import. Whole suite: 395 passed, 3 failed on Q39.
- Not done: stores written before this step lack `unapplied` and keep two CHECK constraints the layout dropped; per Q37 nothing migrates them.
- Questions raised: Q39 to Q41.

## Step 13: the manual-test defects

- D9: every module verb on the CLI takes `--project` and `--layers` for one call, as every tool does over MCP, CLI-011, CLI-021, CLI-033 acceptance 2 and BASE-028.
- D11: `map layers`, `map stack` and `map metaforms` print one aligned row each on the CLI: a layer's name, kind, module, tags, `ready` or `building`, and `on`, `off` or, for a stacked correction layer, `applied`, then `hidden` and `re-examine` when they hold, CLI-033, LAYER-019 and STORE-036; a metaform's name, created time and `active`. `--json` and MCP keep the data, BASE-036.
- D12: an `element=` noun written as a node, such as `type:code` or `join:<id>`, is read as that node, so a property sent to a join is stored orphaned, and one sent to a type address goes on the element there, STORE-039 and STORE-008. It had made an element at the literal address `join:<id>`.
- Found already fixed: D13 and D20 in step 10; D15 and D16 in step 12, since an observation at an unknown element now makes it in memory with a notice and a correction's `receiver` is named in a notice; D17, whose export with `layer=` across two metaforms now succeeds.
- Also: step 12's autofix of import order had expanded the imports of `store.py`, `writes.py`, `reads.py` and `views.py` to one name per line; they are back in the repository's style.
- Tests added, each seen failing first: `test_a_property_named_by_node_attaches_by_the_nodes_kind`, `test_layers_stack_and_metaforms_read_as_one_aligned_row_each` and `test_project_and_layers_pass_on_one_call_to_any_module_verb`.- D2 in part: a help row whose left cell is longer than 40 characters goes on its own line with its help under it, so the `knowledge` usage no longer pads every row of `metaform help map`. Its `op` and `layer` still show as optional, Q44.
- D3: `metaform help <module> <verb>` for a verb outside this system prints what running it prints, `<module> <verb> runs on <systems>.` and `Next: metaform help <module>`, BASE-016.
- D5: a module page leaves out `Verbs` when the module has none, CLI-029.
- D6: `list modules` shows an off module's summary, read without importing from the literal `summary` of `MODULE = Module(...)`, BASE-037 and BASE-015.
- D7: `set` reports a key as updated when its stored state changes, not only its value, CLI-015; `unset` reports a key as reset whenever it deletes a stored value, CLI-017.
- D8: `set ... folder=<path>` names the folder in its first line, `Success: updated 1 key for <path>`, CLI-022.
- D10: the settings screen prints each row as `config --show` does, `* key: value  (glued)`, `  key: value  (set)`, with CLI-031's value rule, through one formatter, CLI-026.
- Tests added, each seen failing first: `test_a_module_page_leaves_out_an_empty_section_and_keeps_its_rows_narrow`, `test_an_off_module_lists_with_the_summary_it_shows_when_on`, `test_set_and_unset_report_what_is_stored_whatever_the_value`, `test_set_for_another_folder_names_that_folder`, `test_screen_rows_read_as_config_show_rows`, and a help assertion in the BASE-016 test.
- Open: D1 is Q42, D4 is Q43, D14 waits on Q1, D18 comes after the viewer, D19 is deferred by D41.
- Questions raised: Q42 to Q44.

## Step 14: the remaining low findings and M2

- Findings fixed:
  - M2: the settings screen reads the cached discovery and no longer resets the loader on every refresh, so no module's `start` runs again; enabling or disabling still resets, BASE-037 and BASE-018.
  - L1: the roles, subtype roles and flags are defined once in `data/records.py` and exported by `metaform.data`, which the intake schema imports; the store's unused `SCHEMA_VERSION` is gone and export and import use `sqlite.SCHEMA_VERSION`; `ALWAYS` lives in `docs.py`; the CLI and help check a verb's systems through `module.on_this_system`.
  - L2: `set`, on the CLI and through the `set` tool, parses and checks every value before it stores any, so one that does not fit stores none. Each is still stored in its own transaction, since `home.base` opens one per write.
  - L3: a new file's table count and version are read in one transaction, so a file another process creates between the two reads is never refused as an earlier Metaform's, STORE-029.
  - L4: helloworld looks for its layer instead of catching every error; the loader's reason for a module with no purpose no longer carries a `Next:` line naming helloworld.
  - L6: a failed uv step names its last line of error text; each uv step has a ten-minute timeout; a module's `tests/` folder is left out of built wheels.
  - Pyright's basic error in `cli.py`: the sink passed to the context is a function returning None.
- Open: L7 is Q45.
- Tests added, each seen failing first: `test_refreshing_the_screen_starts_no_module_again`, `test_set_with_one_value_that_does_not_fit_stores_none_of_them`, `test_a_file_another_connection_creates_between_the_first_reads_is_not_refused`; a reason assertion in the module refusal test; a no-tests assertion in the build test. Whole suite: 406 passed, 3 failed on Q39.
- Questions raised: Q45.

## Step 15: M6, the installer on partial failure

- Each tool is recorded in `installs` as soon as its registration succeeds, so a later tool's failure never hides it from the next run, which then removes its entry before adding it again, MCP-019.
- When `add` fails after a `remove` that also failed, the error names both.
- A merged JSON config is written to a temporary file beside it and moved into place with `os.replace`.
- A config that is not a JSON object holding an `mcpServers` object, such as one with comments, is left unchanged and refused with a Stop naming the file and its backup, and the next step names the entry to add by hand, MCP-015.
- Every tool command has a two-minute timeout; one that does not finish fails the install naming the tool.
- Tests added, each seen failing first: `test_a_tool_that_fails_after_another_registered_leaves_that_one_recorded_for_the_rerun`, `test_a_config_that_is_not_a_json_object_is_refused_naming_it_and_its_backup`, `test_a_tool_command_that_hangs_stops_at_its_timeout`.
- Not done: the proof still starts the registered command once per tool, and never through the tool's own entry; M6 lists no fix for it, and MCP-017 proves the command.

## Step 16: M1, nothing blocks a running loop

- `ctx.publish_async(topic, payload)` delivers from an async verb: an async subscriber is awaited in the running loop, and a plain one runs in a worker thread, with the deliveries `publish` returns, BASE-009 and BASE-010. A subscriber cancelled on its own is reported `cancelled`; the publisher's own cancellation propagates.
- `ctx.publish` called while a loop runs raises a `RuntimeError` naming `publish_async`; `call` given a coroutine while a loop runs raises instead of waiting for it on a worker thread's loop.
- The settings screen runs discovery and enable and disable through `asyncio.to_thread`, so a module's async `start` and `stop` run on a loop of their own there.
- Spec: BASE-009, BASE-010 and the `Context` methods say so.
- Tests added: `test_an_async_publish_never_blocks_its_loop_and_a_sync_one_there_is_refused`, seen failing first; `test_the_screen_loads_and_turns_off_a_module_whose_start_and_stop_are_async`, which passed before, since the old `call` hid a blocking thread, and guards the screen after `call` changed.

## Step 17: strict typing, the settings screen, and the checks in CI

- QUAL-004: `[tool.pyright]` in `pyproject.toml` sets strict mode over `src/metaform`, tests excluded, with Python 3.11. Strict errors went from 702 to 0. The main changes:
  - JSON is narrowed through `as_object`, `as_list` and `descriptor_of` in `data/ids.py`, and elsewhere by a `cast` after each check.
  - A parameter that checks what an agent sent is typed as what it accepts.
  - Context managers return `Generator`.
  - Default factories name their element types.
  - `add_join`'s `Outcome` is handled where the intake writer reads a join id.
- M9: the settings screen is typed. Its groups are `_Row` records. Its names follow the spec: `backend`, `modules`, `glued`, `_toggle_glue`. The unused `module` and `declarations` parameters are gone. A refresh that fails after a failed change adds its error to the status line instead of passing. The dead text naming `compatible`, a `metaform modules load` command and single-file modules is gone. F5 reads the stored values again.
- M8 in part: `settings.scope_of` and `own_scope_of` are public and the CLI uses them. `session.open_store` is public and export uses it. A setting's owner outside `owned_by` is still read from the call stack, now through `inspect.currentframe`, because pytest imports a module's package outside the loader when it collects the module's tests. Moving `Context` construction and the registries into one module is not done.
- QUAL-003: `.github/workflows/checks.yml` runs pyright, ruff and pytest with uv on ubuntu, macOS and Windows, with Python 3.11 and 3.14. The template carries `.github/workflows/checks.yml`, which checks out Metaform, places the module among its modules and runs the same three checks on it, Q46.
- QUAL-005 in part: `[tool.ruff]` sets 120-character lines and Python 3.11, with ruff's default rules until the rule set is chosen, section 07 question 1, Q47. The dev extra pins pyright 1.1.414 and ruff 0.16.9, so the checks give the same results everywhere. Ruff's defaults find 107 problems, 27 of them import order in a form the repository does not use; none is fixed until the rule set is chosen, so the lint step fails.
- Tests: the screen tests use the new names. Whole suite: 411 passed, 3 failed on Q39.
- Questions raised: Q46 and Q47.

## Step 18: M10, the module contract typed

- `metaform.module` states the shapes of the contract:
  - `VerbFunction`, `Handler`, `Hook` and `StatusHook` for a verb, a subscriber, `start` and `stop`, and `status`. Each may be a plain function or a coroutine function, BASE-009 and BASE-035.
  - `NounKind` and `Surface` as `Literal` types for a noun's kind and a verb's surfaces. `Context.surface` is a `Surface`.
- `metaform.data` exports `NodeKind`, `LayerKind`, `Op` and `Answer` as `Literal` types for a node's kind, a layer's kind, a row's op and a challenge's state.
  - `Node.of(kind, id)` checks a kind read as text before typing it, and `Node.parse` uses it.
  - A row's layer kind and op are typed as the schema's CHECK constraints keep them.
- The help pages and the CLI take `Module`, `Verb` and `Found`. The loader types module places as `Traversable`. Typing them found two unguarded paths, now guarded: a verb lookup on a module that did not load, and the systems of a verb that names none.
- Whole suite: 411 passed, 3 failed on Q39. Strict pyright: 0 errors.

## The Canonical Intake reconciled

- `f93c91b` changed VRE to VE on a copy of the intake taken from `cd8dadb`, older than the tested version adopted in `e1acea0`, so it dropped that version's vested-entity rules, the `media.photo` examples, step 9c, the role VE instruction and the nested subtype join. Rich: an obvious fix.
- `specifications/Canonical_Intake.xml` and the served copy are now the tested version with every change `f93c91b` made: VRE to VE, 17 places; `traverse`; `variants`; `Supportive Element`, already in the tested version; the name comment `Canonical Name (Project official terminology) or Informal Name`. `of of` was already fixed there.
- Not carried over: `f93c91b`'s replacement of `subtype` by `Vested Entity` in step 11, the platformer example and the response instruction, where a VE, a party outside the AUE, cannot be an absorbed internal part; the words stay `subtype`.
- Also fixed: step 1's `DET elements`, a term the file never defines, now reads `NE elements`.
- The response schema is the tested version's, which `intake_submit` already follows: a purpose join holds its refs and its subtype joins; AUE stays in the top-level element's role list. The older copy's provider element nested inside a purpose join is not restored.
- The handoff's four intake questions are answered by this. The byte-copy tests and the first working test pass.

## Windows, from the first CI run

- CI ran the suite on Windows for the first time. 42 tests failed there, from two causes that never show on Linux or macOS, QUAL-002:
  - A pipe on Windows defaults to cp1252. `set` writes an arrow and the intake prompt has other characters cp1252 lacks, so the CLI raised `UnicodeEncodeError`. The CLI now reads and writes UTF-8 whatever the system gives a pipe; a Windows console and every other system is UTF-8 already. The tests decode what the CLI prints as UTF-8.
  - The installer's proof started its command by its bare name, and Windows cannot start a `.cmd` launcher that way. The proof now starts the full path `shutil.which` finds, as registration already did.
- Test added, seen failing first on Linux with `PYTHONIOENCODING=cp1252`, which gives any system the Windows pipe: `test_output_is_utf8_whatever_the_encoding_the_system_gives_a_pipe`.

## Step 19: the second review, test review and manual test

- The critic review, `REVIEW-CODE-2.md`, found every first-round finding fixed but those open by decision, and two new ones:
  - N1: two report writes at once for one run and kind could replace each other, since the file was checked for and then written. It is now created with exclusive create, or appended to when it exists, in one step, BASE-045.
  - L8: the last two `# type: ignore` comments say why.
- The test review, `TEST-REVIEW-2.md`, found nine tests protecting behavior no record stated, or stating it wrongly:
  - Six behaviors built from the first review are now stated in their records, recommended: wheels without module tests, BASE-041; the dependency check before import, BASE-015 and BASE-037; a failing `stop`, BASE-018; the installer's refusal of a config that is not an object, its timeout, its atomic merge and its recording, MCP-015; the folder at the end of `set`'s first line, CLI-022; help rows of at most 40 characters on the left, CLI-029.
  - An import meeting a metaform another project owns raised an error. STORE-027 has no conflict case and STORE-026 raises only for what cannot be read, so it now writes nothing of that metaform, counts it skipped and names the owner in a notice. A test covers STORE-027's own path, a document imported into a different registered project.
  - One test named STORE-027 for STORE-031's rule; its marker is fixed. The help-row test checks the stated rule instead of an 80-column guess.
- The manual test, `MANUAL-TEST-2.md`: 86 checks, 78 pass. The 8 failures are D1, Q42; D2's rest, Q44; D4, Q43; D14, Q1; D19, deferred by D41; D18's three commands, not built; and the web GUI, not built. Thirteen of round one's defects are fixed. A real Claude run over MCP found the map's entry at once.
  - It also showed an agent guessing `map_knowledge`'s `op` five times, since the tool schema carried no help. Every noun and switch property now carries its help as its `description`, MCP-003.
- Q7's paragraph, written before step 12, is marked answered: D82 stores a self join as given with a notice.
- Tests added or changed, each seen failing first: `test_writes_to_one_file_at_the_same_time_all_survive`; `test_an_import_meeting_a_metaform_another_project_owns_writes_nothing_of_it_and_names_the_owner`; the MCP schema test, now requiring descriptions. Added: `test_a_document_imports_into_another_registered_project_which_keeps_its_own_path`, which passed at once, since the path already worked.

