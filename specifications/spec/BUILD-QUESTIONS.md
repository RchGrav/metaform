# Build questions

Questions the build raised. Each names the record it concerns, what the build did meanwhile, and what it blocks. The orchestrator takes them to Rich.

## Step 1, storage

**Q1. How is a blind-spot layer recognized? (STORE-040, LAYER-015)**
`answer` must refuse an item that is not in a blind-spot layer, and reads must show `open` for an unanswered challenge, but no layer kind, tag or field marks a layer as a blind-spot layer.
Meanwhile: `answer` accepts an item of any knowledge layer (kind `layer`) and refuses items of the intake, memory and correction layers. An unanswered item shows no state, so `open` is never shown.
Blocks: showing `open` on unanswered challenges.

**Q2. An explicitly empty list setting. (STORE-002, CLI-013, CLI-014)**
A list setting is stored one row per member, so an empty list has no rows and cannot be told apart from nothing stored. A folder then cannot override a parent folder's list with an empty one, for example `set --modules ''` below a narrowed folder.
Meanwhile: storing an empty list stores nothing, so the folder inherits again.
Blocks: nothing in the first working test.

**Q3. The join of an exported subtype. (STORE-027)**
The document's subtype rows carry the columns of `subtypes`, which has no join column; the join lives in `subtype_ids`. Without it an import cannot rebuild the subtype's identity row.
Meanwhile: each exported subtype row carries one extra member, `join_id`.
Blocks: nothing.

**Q4. Putting an element back needs a lookup by address. (STORE-017, STORE-005)**
An `add` in a correction layer reuses the most recently removed element at that address. No listed index finds element rows by address, so the lookup would scan.
Meanwhile: the store adds `CREATE INDEX elements_by_address ON elements(address)`.
Blocks: nothing.

**Q5. Is an intake element a node when the intake layer is not toggled on? (STORE-014, LAYER-019)**
STORE-014 says an element made by a layer is absent from a node read whose selection excludes that layer. LAYER-019 acceptance 2 says `set --layers practices` makes a node read return the practices layer's items, which needs the node itself to be found with the intake layer off.
Meanwhile: elements of the metaform, added by the intake or a correction layer, are always nodes; an element a knowledge or memory layer created shows only where its layer reaches. The intake layer's joins and items are still filtered by selection like any layer's, STORE-025.
Blocks: nothing in the first working test, where every layer is on.

**Q6. The next step in STORE-026's example names a verb that does not exist. (STORE-026, BASE-038)**
The example says `Next: metaform map add-element code.probe.echo`, and BASE-038 has no `add-element` verb; adding an element is `knowledge op=add-element`.
Meanwhile: the error's next step is `metaform map knowledge op=add-element layer=<layer> address=<address>`.
Blocks: nothing.

**Q7. A self join from an intake submission. (D11, D82, BASE-039)**
Answered by D82: a self join is stored as given with a notice, by `intake_submit` since step 10 and by `add_join` since step 12. Nothing refuses it.
Blocks: nothing.

**Q8. Property ids have no identity row. (STORE-033, STORE-039)**
`identities.kind` allows element, join, subtype and item, but `correct`, `edit`, `remove` and `history` also take property ids.
Meanwhile: a bare id not in `identities` is looked up through the `properties` `UNIQUE(property_id, layer_id)` index.
Blocks: nothing.

## Step 2, common base and modules

**Q9. The template's purpose. (BASE-019, MCP-008)**
BASE-019 says the template declares every field with none filled and loads when a copy is enabled; MCP-008 says a module whose `purpose` is empty fails to load.
Meanwhile: the template's `purpose` holds one placeholder sentence telling the author what to write, ending `Details: metaform help template.`, so a copy loads. Its other fields are empty.
Blocks: nothing.

**Q10. Discarding a layer whose items keep identity rows. (STORE-032, STORE-033)**
`discard` keeps every identity row and deletes the layer row, but `item_ids.layer_id` references `layers`, so the layer row cannot go while its items' `item_ids` rows stay.
Meanwhile: `discard` deletes the discarded layer's `item_ids` rows and keeps their `identities` rows, so an item id is still never reused.
Blocks: nothing.

## Step 3, CLI and settings

**Q11. Is `--quiet` a setting or a verb control? (D32, CLI-004, CLI-031)**
D32 says `--quiet` is a setting because people want it to stick, while CLI-031 has `-q` and `--quiet` suppress output on the one `set` or `unset` call they are given on; on `set`, a setting switch is stored, so `set --quiet` cannot mean both.
Meanwhile: `-q` and `--quiet` stay verb controls of `set` and `unset`, never stored.
Blocks: nothing in the first working test.

**Q12. The status line for a project with no metaform yet. (CLI-028, STORE-041)**
Line 5a shows the active metaform's name, but a project has no metaform until its first write creates `main`.
Meanwhile: status shows `Metaform: none yet` until then.
Blocks: nothing.

## Step 4, map and layers

**Q13. BASE-043's example names a verb that does not exist. (BASE-043, BASE-038)**
The example is `metaform map add-join <layer> <receiver> <provider> ... non_goal=...`, with the fields positional; BASE-038 has no `add-join` verb, and in `knowledge` every field is a named noun.
Meanwhile: the rule is built in the shared parser (required nouns positional, optional ones `name=value`, an optional noun before the required ones refused) and tested with a scratch module; `knowledge op=add-join` takes every field as `name=value`.
Blocks: nothing.

**Q14. The kind of the `value` noun of `map knowledge`. (BASE-038, STORE-015)**
One noun `value` serves an item's or property's value, which is any JSON value, and a ref's value, which is text. BASE-038 does not give its kind.
Meanwhile: `value` is a `json` noun, so on the CLI a text value is written as JSON, `value='"Profile first."'`; for `add-ref` it must be a JSON string.
Blocks: nothing.

## Step 6, MCP

**Q15. The `set` tool. (PROJ-005, CLI-033, MCP-003, MCP-024)**
PROJ-005 has an agent call a tool named `set` to select a project for the server's folder, and MCP-024 lists `set` with `layers` among the tools, but MCP-003 makes every tool a module verb named `<module>_<verb>`, and `set` is a chassis verb.
Meanwhile: the mcp module serves one extra tool named `set`, with one property per setting and `glue`, storing for the server's folder exactly as `metaform set` does.
Blocks: nothing.

**Q16. The next step when a call has no project. (STORE-023, PROJ-005)**
STORE-023 gives `Next: metaform add project <id> <path>`; PROJ-005 gives `Next: metaform set --project <id>`. PROJ-005 also has status and the instructions list the registered projects, while CLI-028 and MCP-009 end those texts with the register line.
Meanwhile: with no project registered the next step is `metaform add project <id> <path>`; with some registered it is `metaform set --project <id>`. The instructions add `Registered projects: <ids>.` just before the register line; status does not list them.
Blocks: nothing.

**Q17. Toggling layers for one tool call. (CLI-033, MCP-003)**
CLI-033 says `layers` may be given on a single tool call, but MCP-003 lists only `project` as the property every tool takes.
Meanwhile: every tool also takes an optional `layers` array for that call only.
Blocks: nothing.

## Step 7, intake

**Q18. `elements` is required in the schema and named on the command line. (BASE-039, BASE-043, BASE-035)**
BASE-039 makes `elements` required in the tool's input schema and a named argument `elements=<path>` on the CLI, but a required noun is positional, BASE-043, and a noun has one kind on both surfaces while `elements` is an array over MCP and a path on the CLI.
Meanwhile: `elements` is declared optional, so the CLI takes `elements=<path>`; its declaration carries the array schema, which the MCP server uses as the property's schema; the check refuses a submission without it, naming `elements: is required`. The tool's `required` list therefore does not name `elements`.
Blocks: nothing.

**Q19. MAP-040's real intake result. (MAP-040, BASE-039)**
The acceptance submits a real intake result such as the MGM map; no such result in the tool's schema is in this repository, and the build does not read other repositories.
Meanwhile: the tests submit a three-element fixture with a subtype, refs and a non-goal, `tests/fixtures/intake_timer.json`.
Blocks: nothing; a real result can be added as a fixture when one is supplied.

## Step 8, installer, skill and build

**Q20. Gemini's registration command. (MCP-016, E2)**
The table's form is `gemini mcp add --scope user metaform uvx --from <source> metaform mcp serve`, with no `--` before the server's own arguments. The local `gemini mcp add --help` takes options after the command, so `--from` may be read as a Gemini option.
Meanwhile: the command is built exactly as the table gives it; it is not proven against a real Gemini CLI.
Blocks: nothing in the first working test, which registers Claude Code, Codex and Cursor.

**Q21. A built wheel's system modules as entry points. (BASE-041, BASE-037)**
BASE-041 writes a `[metaform.modules]` entry point for every module the wheel carries, and those modules are also in the wheel's system place, so BASE-037's duplicate rule would report each one as an error once the wheel is installed.
Meanwhile: discovery skips an entry point whose package is `metaform.modules.<id>`, the module already found in the system place.
Blocks: nothing.

**Q22. Importing system modules from a directly run wheel. (BASE-037, BASE-042)**
BASE-037 imports folder modules under `metaform_module_<place>_<id>` from their `__init__.py` file, which cannot be done for a module inside a zip.
Meanwhile: a system module inside a directly run wheel is imported as `metaform.modules.<id>`; on disk the BASE-037 name is kept.
Blocks: nothing.

**Q23. A home written by the earlier chassis. (STORE-029, D24)**
The base database in `~/.metaform` on this machine was written by the earlier chassis and has no schema version, so every command except `metaform --version` stops with the next step to rename it. D24 says pre-1.0 data is dropped; the build does not touch the file.
Meanwhile: the error names the file and the rename.
Blocks: running the new build against `~/.metaform` until that file is moved.

## Test review

**Q24. The chassis's own dependency now ships compiled. (BASE-026, BASE-041)**
BASE-026 says `prompt_toolkit` is pure Python and a build with no modules resolves with no compiled distribution. `prompt_toolkit` needs `wcwidth`, and the current `wcwidth` wheel carries `_wcwidth_c.abi3.so`. The build therefore names `wcwidth` as compiled and leaves it out of `_vendor`, so a direct run of a wheel with no network needs `wcwidth` installed.
Meanwhile: the build does exactly what BASE-041 says for a compiled dependency; the test checks that it is named and not carried.
Blocks: BASE-024's offline direct run on a machine without `wcwidth`, until a pure `wcwidth` is pinned or the requirement changes.

**Q25. STORE-020's "one item row and no other row". (STORE-020, STORE-007, STORE-033)**
Adding an observation writes the `items` row, its `current_items` pointer, and the `item_ids` and `identities` rows that STORE-007 and STORE-033 require for every item, so "no other row" cannot hold as written.
Meanwhile: the test requires exactly those four rows and nothing else.
Blocks: nothing.


## Step 10, intake and reporting

**Q26. The words of the stop rule and the feedback request in the instructions. (MCP-007, BASE-044, CLI-034)**
MCP-007 says the base text always tells agents to stop and submit a trouble report instead of retrying, and asks for process feedback when `--debug` is on, but gives no words; the base text itself "reads exactly" the earlier paragraph.
Meanwhile: the base text keeps its paragraph and gains a second one, the intake footer's own sentence: `If you cannot continue, stop and submit a trouble report with the feedback tool, attaching what you have in its shape field; do not retry.` With `--debug` on, one more paragraph follows: `Submit feedback on the Metaform process with the feedback tool: bad semantics, a tool that did not match its schema, where you got stuck.`
Blocks: nothing.

**Q27. `map where` with no address. (BASE-038, BASE-043)**
BASE-038 says `where` with no address returns the entry, but `address` is a required noun, and required nouns are positional, BASE-043; an optional one is written `address=...`.
Meanwhile: `address` stays required and positional; an empty address, `metaform map where ''` or `map_where {"address": ""}`, returns what `roots` returns. `map_where {}` is an error naming the missing noun.
Blocks: nothing.

**Q28. How the chassis lets `mcp serve` run on any surface. (CLI-022, MCP-004, BASE-001, BASE-035)**
The chassis may not name a module, so it needs a declaration to tell a transport from a command an agent runs; BASE-035's `Verb` has none.
Meanwhile: `Verb` gains `transport: bool = False`; a transport verb runs whatever the surface. `mcp serve` declares it. The template changelog records it as 0.3.0.
Blocks: nothing.

**Q29. An `intake_submit` with no `elements` at all. (BASE-039, BASE-044)**
A missing required field is "stored empty", but an intake with no elements at all would set `has_intake()` true with an empty map.
Meanwhile: a call with no `elements` is a call that cannot be read: nothing is stored and one notice says to save the result with the `feedback` tool's `shape` field.
Blocks: nothing.

**Q30. The export document and the new tables. (STORE-027, STORE-042, STORE-043, STORE-009)**
The document's member list predates `findings`, `element_roles` and `reports`, so a round trip would lose the flags.
Meanwhile: each metaform in the document also carries `element_roles` and `findings`, and import adds them for the layers it adds. `reports` rows are not carried, because their files are not in the document.
Blocks: nothing.

**Q31. Discarding a layer's findings without a scan. (STORE-042, STORE-032, STORE-005)**
`findings` has indexes by flag and by target, but not by layer, so `discard` would scan it.
Meanwhile: the store adds `CREATE INDEX findings_by_layer ON findings(layer_id)`, as with Q4.
Blocks: nothing.

**Q32. Text or a file in `feedback report=` and `shape=` on the CLI. (BASE-045)**
BASE-045 lets report and shape be text, a file path or `-`, without saying how the two are told apart.
Meanwhile: `-` reads standard input; a value that names an existing file reads it; any other value is the text itself. Over MCP they are always text.
Blocks: nothing.

**Q33. The way back named after a second intake. (BASE-039, CLI-031)**
BASE-039 writes the way back as `metaform activate <earlier name>`; the chassis verb is `metaform activate metaform <name>`.
Meanwhile: the notice names `metaform activate metaform <earlier name>`, the command that works.
Blocks: nothing.

**Q34. A tool argument the tool does not declare. (BASE-043, BASE-044, MCP-003)**
The schema says `additionalProperties: false`, and the SDK does not enforce it; BASE-043 keeps an unknown `name=value` in the record's `extra`, which only verbs with an `extra` noun have.
Meanwhile: since step 12, on both surfaces, an unknown argument of a verb with an `extra` noun is kept in the record's `extra` with one `Notice:` line, BASE-043; for any other verb it is named in a notice and ignored. The call still runs.
Blocks: nothing.

**Q35. The roles index after a correction. (STORE-009, STORE-017)**
`element_roles` is written with each descriptor that carries a role and follows `edit`, `remove` and `discard` of it; a correction layer that changes an intake descriptor's role writes its own descriptor version, and the index row of the intake layer stays as the intake wrote it.
Meanwhile: `roots` picks the entry by the intake layer's roles and shows each element's current role from its descriptors.
Blocks: nothing in the first working test.

**Q36. Where a subtype's flag is given. (MAP-046, BASE-039)**
BASE-039 puts `flag` on element objects and join objects; a subtype join is a join object and its `element` is an element object.
Meanwhile: the subtype's flag is the subtype join's `flag`, else its element's.
Blocks: nothing.

**Q37. Stores written before this step. (STORE-029, D24)**
The layout gained `element_roles`, `findings` and `reports` while the schema version stays 1, so a store written by the earlier build lacks them.
Meanwhile: nothing migrates them, per D24; such a store is re-created.
Blocks: nothing.

## Step 11, high findings

**Q38. The repository wheel and the `mcp` module's dependency. (BASE-022, BASE-026, BASE-041, MCP-010)**
The repository wheel carries every repo module, BASE-022, but the chassis's `[project].dependencies` must stay pure Python, BASE-026, and is copied as `CHASSIS_DEPENDENCIES`, which a `metaform build` without the `mcp` module must not list, BASE-041. So a wheel built by hatchling from `pyproject.toml` carries the `mcp` module without `mcp` in its `Requires-Dist`, and `uvx --from` it cannot start the server. Adding each repo module's `DEPENDENCIES` to the repository wheel means making the dependency list dynamic, which changes where `CHASSIS_DEPENDENCIES` comes from.
Meanwhile: `mcp>=2.2` stays in the `dev` extra; the installer registers the wheel `metaform build` writes, whose `Requires-Dist` names `mcp`; and discovery now reads each module's `DEPENDENCIES` before import and reports a missing one as the module's load problem, so `list modules` and `mcp serve` say what is missing instead of raising an import error.
Blocks: publishing a repository wheel that serves MCP.

## Step 12, notices everywhere and the data access object split

**Q39. The Canonical Intake file and the served copy. (BASE-039, MAP-040)**
`f93c91b` changed VRE to VE in `specifications/Canonical_Intake.xml`, and the same commit also removed text the served copy `resources/Canonical_Intake.xml` still has: the four rules on vested entities ("We call an entity outside the artifact vested...", "The VEs that matter are the ones whose purpose drives changes...", "The VE that drives the most improvement...", "Never the person who asked for the intake..."), "named at its most specific reusable type level" and the rule on one person holding several roles, the five `media.photo` examples, step 9c, the instruction that a VE outside the AUE is an element with role VE, and the nested subtype join in the response schema. It reads as an edit made on a copy older than the served one. Which text is current?
Meanwhile: neither file is changed. The byte-copy tests fail: `test_the_served_intake_is_the_stored_file_byte_for_byte`, `test_prompt_serves_the_intake_with_only_its_target_filled` and the first working test.
Blocks: the three tests, and adopting the VE wording in the served intake.

**Q40. The module that owns an unnamed layer. (LAYER-001, STORE-013)**
A write sent without a layer goes to a new building layer `unnamed-<UTC timestamp>`, and a layer records the module that owns it.
Meanwhile: it records the module whose verb made the write, which `context.build` passes to `Store`; a `Store` built without a module records an empty module. The layer has no variable and an empty provenance record, and the one notice says so.
Blocks: nothing.

**Q41. A correction layer named in `--layers`. (CLI-033, BASE-044, LAYER-011)**
CLI-033 keeps a name that is neither a layer nor a tag, with a notice. It says nothing of a correction layer, which `set --layers` still refuses, although a correction layer's select, mask and hide now write nothing and return a notice.
Meanwhile: the refusal stays. Recommended: keep the name with a notice that correction layers are always applied, so the setting follows the rule of the operations.
Blocks: nothing.

## Step 13, the manual-test defects

**Q42. `help modules`. (CLI-031, CLI-008, D1 of the manual test)**
CLI-031's `help` row lists the noun `modules` beside `intro`, `switches` and `agents`; CLI-008's indexes are `commands` and `switches`, and `help modules` is refused.
Meanwhile: refused. Recommended: read the table's `modules` as `commands`, since `list modules` already prints the module list.
Blocks: nothing.

**Q43. Where a verb page lists its optional nouns. (CLI-029, BASE-043, D4 of the manual test)**
CLI-029's page has a `Switches` section and none for nouns, and a verb page lists its optional nouns under `Switches`, though BASE-043 makes record fields nouns, not switches.
Meanwhile: unchanged. Recommended: a `Nouns` section after `Usage`, holding the optional nouns, with `Switches` kept for settings the verb reads.
Blocks: nothing.

**Q44. A noun that is required but written `name=value`. (BASE-038, BASE-043, D2 of the manual test)**
`map knowledge` needs `op=` on every call and `layer=` on every call but the adds, LAYER-001, yet both are optional nouns, since only optional nouns take the `name=value` form, so its usage shows `[op] [layer]`.
Meanwhile: unchanged; the verb stops with `knowledge op=<op> needs layer.` when one is missing. Recommended: a noun marked required and named, shown as `op=<op>` in usage, with the parser reading it by name.
Blocks: nothing.

## Step 14, low findings

**Q45. The `set` tool and `project`. (MCP-025, L7 of the code review)**
MCP-025 says every tool accepts an optional `project`; the `set` tool stores settings for the server's folder, and settings belong to folders, not projects, so a per-call project has nothing to act on.
Meanwhile: `set` takes no `project`. Recommended: record in MCP-025 that `set` is the exception, since it stores folder settings.
Blocks: nothing.

## Step 17, the checks

**Q46. What a template fork's CI checks out. (QUAL-003, BASE-019)**
A fork of the template is one module folder. Its tests use the Metaform repository's fixtures and live under `metaform.modules`, so they run only inside a Metaform checkout.
Meanwhile: the template's workflow checks out `RchGrav/metaform` at `chassis`, places the module under `src/metaform/modules/<repository name>`, and runs pyright, ruff and pytest on it. Recommended: the same, with the reference moved to the release branch once `chassis` is merged.
Blocks: a fork's CI, if the repository is private or the branch moves.

**Q47. Ruff's rule set and the form of a reasoned suppression. (QUAL-005, section 07 question 1)**
Ruff 0.16.9's defaults find 107 problems. The largest group, 27, is import order: ruff wraps a long import one name per line, and the repository aligns continuation lines under the opening parenthesis, which ruff cannot write. The others are real or near: unused imports, `subprocess.run` without `check`, blind excepts without a reason, `datetime.UTC`.
Meanwhile: ruff's defaults, nothing fixed, and the lint step fails. Recommended: ruff's defaults without `I001`, so the import style stays; and a suppression written `# noqa: <code>  <reason>`, as the code already writes them.
Blocks: a green lint step in CI.

## Step 19, CI

**Q48. A write that meets `database is locked` on Windows. (STORE-006, STORE-037, QUAL-002)**
`test_threads_of_one_process_writing_to_one_node_lose_nothing`, four threads writing 250 items each to one node, failed once in four Windows runs, on Python 3.14, with `OperationalError('database is locked')`; every other run passed, and on Linux sixteen threads writing 300 items each never fail. Each store operation opens its own connection, so the test opens and closes a thousand connections, and each one also sends `PRAGMA journal_mode=WAL`, which STORE-006 asks of every connection though WAL is kept in the file. Which statement met the lock, and why the five-second wait did not cover it, is not known.
Answered by evidence, step 22: a diagnosis job ran the test many times on Windows. It failed twice, both times at `BEGIN IMMEDIATE`, with `SQLITE_BUSY` after 8.55 and 7.19 seconds of waiting. SQLite's busy wait polls and is not fair, so one thread of four in one process could lose every retry to the other three until its wait ran out. Fixed: inside one process, writers to one store take turns on a lock of that store, so the busy wait only settles writers of different processes, and the wait is 30 seconds, STORE-006. `PRAGMA journal_mode=WAL` was not involved.

