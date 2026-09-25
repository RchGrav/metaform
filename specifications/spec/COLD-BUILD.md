# Cold build check

Run of QUAL-011 on 2026-09-24. The builder read only specifications/, spec/ first, then the sources the index lists. It read no code, history or other files. Gaps already listed in OPEN-QUESTIONS.md are left out. Each item names the record, what the builder would have to guess, and why the text is not enough.

## Blocking the first working test

Ordered by the build order in 00-index.md.

1. BASE-006, 009, 010, 014, 015, 018, CLI-005 to CLI-017, CLI-026, MCP-002 to MCP-006, QUAL-003, QUAL-012. These records define behavior as "exists as", "Existing" or "current" code: `Stop`, `Context`, `call`, the `Module` fields, `loader.discover`, `RESERVED`, `ALWAYS`, `docs.overview` text, `settings._scope`, `status()`, `tui.py`, `serve`, `tools`, `run_tool`, `_surface`, `module_metadata.read`, the pyproject minimum Python. A builder with only the spec must reinvent all of it. Missing.
2. STORE-002, STORE-003, CLI-001. `add project <id> <path>` appears only as an example. The id becomes a folder name, but its allowed characters, case rules, and what happens on a duplicate id, a duplicate path or a missing path are not stated. Missing.
3. STORE-009, MAP-016, STORE-024 add_element. When the address is already held, the call returns the existing element. The spec does not say what happens to the supplied name, name_length, role, extra and layer: dropped, an error, or a revision. It also does not cover the case where the held element belongs to another layer. Ambiguous.
4. BASE-028, STORE-023. The spec does not say what `ctx.store` is when the folder resolves to no project, or when a chassis verb runs, or what `Store(project_id)` does for an unregistered id: None, `Stop`, and with which Next line. Missing.
5. BASE-006, MCP-005. The shape of `Verb.nouns` is not given: names, count, optional or variadic, types. Without it the parser, the usage lines and the MCP `nouns` array schema cannot be built. BASE-006 says usage comes from the declaration, but `Verb` has no usage field. Missing.
6. MCP-005, CLI-010. "A switch that takes a value is a string argument" leaves open whether int and list settings are strings or JSON numbers and arrays over MCP. It also leaves open how a list is written on the CLI, for example with commas. Ambiguous.
7. MCP-003, STORE-023. The content of a tool result is not stated: CLI text, JSON of the frozen dataclasses, or both. STORE-023's "CLI and MCP return equal results" needs one representation. An intake agent needs the returned ids to write joins and refs. Missing.
8. BASE-017, BASE-022, MCP-004, STORE-026. A `map` module ships enabled, has the tool `map_where` and the command `metaform map element add`, but no record defines its id, verbs, nouns, or which STORE-024 and STORE-025 operations it exposes. Missing.
9. Build order step 6, MCP-009, D38. No record defines the intake module. Missing are its id, its verbs besides `prompt`, whether it or `map` owns the map writes, its concise instructions, which file it serves (Canonical_Intake.xml or Canonical_Intake_test.xml), and where the "stored intake instructions" live.
10. LAYER-001, STORE-013, STORE-016. Not given for the intake layer: the name, which is unique per store; the variable text; the module value; and the provenance fields workflow, prompt, model, role and blinded. The spec also does not say who supplies model and role, the agent through a tool argument or the module. Missing.
11. MCP-009. "Has an intake" means an intake layer exists, but the spec does not say how a layer is recognized as an intake layer: by module, by `result_id` not null, or by name. LAYER-001 creates the layer at the start of the run, so an empty or half-written intake would clear the notice. That conflicts with MAP-040's "whole or not at all".
12. MAP-040 against Canonical_Intake.xml 1.1. In 1.1, and in Sonnet_Intake.xml, the `<element>` nested in a join repeats the provider's address. It reads as the provider's definition, not as an absorbed part. MAP-040 maps "a join nested inside a join" to a subtype, a form only the test schema has. Several providers appear only nested, never as root elements. Ambiguous.
13. MAP-040, MAP-021. In 1.1, refs appear only inside the nested element. MAP-040 puts refs on root elements and joins, and the test schema adds join-level refs. The builder cannot tell whether a nested element's refs belong to the provider element, the join or a subtype. Ambiguous.
14. MAP-042, MAP-017. MAP-042 expects one element with role AUE. The 1.1 schema only permits one, and Sonnet_Intake.xml has none. The spec does not say who creates the AUE element or what its address is when the intake omits it. Missing.
15. MCP-007, MCP-009, CLI-005. The chassis base text is described only by topic. The no-intake notice is given only as a "shape". The status "intake state line" points to a section that gives no wording. The builder would write all three texts. Missing.
16. MCP-024, MCP-007. The set of modules on in the first test is not stated, so the instruction sections are unknown: mcp itself, map, intake, memory. The "demo modules" that must stay disabled are never named. Missing.
17. MCP-010, MCP-016. The spec does not say how the installer finds `<source>`: the wheel it runs from, the output of `metaform build` and where that goes, or a distribution name. The case where it runs under uvx or `python <wheel>` is also open. Missing.
18. MCP-013. Not given: the minimum Python version the check enforces, how each tool noun is detected, and the per-OS uv install command for the Next line. Missing.
19. MCP-015. For tools registered through their own command, such as `claude mcp add`, the spec does not say which file is previewed and backed up, for example `~/.claude.json`. Also missing: the form of the single confirmation in the interactive path, and the timestamp format of the backup folder.
20. MCP-021, MCP-014. The spec does not say whether `install claude` also writes `~/.agents/skills/`, although MCP-014 acceptance limits it to "skill folders for Claude". The skill text beyond two sentences is not given. Antigravity has a folder but no tool noun or detection rule. Ambiguous.
21. MCP-024 acceptance. The automated run of steps 2 to 7 needs rules that are not given: whether install runs against faked tools, which intake fixture step 7 stores and through which calls, and which working folder the scripted client starts the server in. Missing.

## Other gaps

1. LAYER-005, MAP-011, STORE-025. No read returns the applying set, the visible set or the inherited context. The spec does not say how transitive items attached to an element, join or subtype travel, whether by the element's current address or not at all. It also does not say which index serves the descendant read of the visible set.
2. LAYER-008, STORE-025. `node(target, selection=None)` does not say how the raw form, with every stored layer, is requested as distinct from the in-context form.
3. LAYER-007. "The project supplies the starting selection". No table stores a project starting selection. STORE-019 says all layers. The spec does not say whether one can be set, or where.
4. LAYER-007. "Selection data that cannot be applied faithfully is kept and reported as unresolved". The spec does not say when that happens, how it is reported, or where.
5. LAYER-011, STORE-017. "Layers that depend on it are marked for re-examination". No field or table holds the mark, and nothing says how it is cleared. D14 covers only the source list.
6. LAYER-012, STORE-020, STORE-024. Not given for the default memory layer: its name, module and variable text. The spec also does not say how `layer()` recognizes memory to waive provenance, by name or by module, or which call creates it "on first use".
7. LAYER-013, CLI-021. The CLI and tool names of the memory operations, their owning module, and their argument shapes are not given. For example, do they take entity arrays like the reference server? CLI-021 cites a `memory` command group that no record defines.
8. STORE-020, STORE-025. The spec does not say whether the FTS table indexes every layer's items or only memory's, and whether search leaves out hidden and unselected layers.
9. STORE-007, STORE-015. Items have identity ids but no `item_ids` table. `revise`, `retire`, `revisions` and `revision` take a bare id, so the builder does not know how the kind, and so the table, is found.
10. STORE-017, STORE-024. The format of `changes` in `revise` is not given: which fields may change, how refs are kept or dropped, and how a retype updates `current_elements.address` and writes `types` rows.
11. STORE-017. Retiring an element or join does not say what happens to its current joins, subtypes and items. They could stay pointing at a retired node, be retired too, or be refused.
12. STORE-024 `layer()`. For "the same properties", the spec does not say whether variable, module and provenance are compared or only the three booleans.
13. STORE-015, STORE-024. `value` is "JSON". The spec does not say whether any JSON value is allowed or only an object, or how `value` and `extra` differ for an item.
14. STORE-010, MAP-020. The allowed values of `joins.type` besides `purpose` are not given, and the test schema's subtype join has no type. The spec does not say whether None for purpose, function, relation or observation is refused, while STORE-026 accepts an empty string.
15. MAP-012. The spec does not say what `short_name` returns when name_length is null, zero or larger than the segment count.
16. STORE-027, BASE-002. The CLI grammar of export and import is not given: a file argument or stdout, how a project is chosen, the "chosen layers" form. A partial export does not say whether it includes the elements and types that the items reference.
17. STORE-027. The export document has no project record. So on import into an empty home, the source of the project id, path and target is not given. It also does not say whether `row` integers are kept, or how `refs.owner_row` is remapped into a store that already has rows.
18. BASE-002. The grammar of `metaform query` is not given, nor which reads it exposes or how it relates to the where and element commands.
19. BASE-022, BASE-024. For `metaform build`, the output path and file name are not given, nor how user-place and entry-point modules are packed or how `DEPENDENCIES` become wheel metadata. The spec says pure-Python dependencies are "carried inside the wheel", which is not a standard wheel mechanism, and gives no method.
20. BASE-023. Not given: how `__main__.py` prepares the runtime, where it unpacks, and how it points the home at its subfolder, for example through `METAFORM_HOME`.
21. BASE-018. The signatures of `start(ctx)` and `stop(ctx)` are not given, nor when they run relative to registration. The spec also does not say how a running task is registered to its owning module.
22. BASE-031. How "cancel requested" is shown on the CLI and over MCP is not stated. The exit code for cancelled is only recommended.
23. BASE-016. For a verb filtered by OS, the spec does not say what `metaform help <module>` shows, or which next step the verb's own help page gives.
24. CLI-021, CLI-022. The spec does not say whether `--project` must be a registered id, which group names `--commands` accepts, for example module ids plus `chassis`, or whether naming an absent module is an error.
25. CLI-005. The display format for "selected here or inherited" and the exact status lines for a narrowed surface are not given.
26. MCP-014, MCP-016. The table and the tool nouns do not line up one to one. VS Code and Copilot CLI are given nouns `vscode` and `copilot`, Factory and Claude Desktop have no noun, and detection "by config folder" is not given per tool.
27. MCP-017. The proof step does not give a timeout, or say from which folder's surface "N tools" is counted.
28. MCP-002, STORE-006. Tool calls run in worker threads. The spec does not say whether each operation opens its own SQLite connection or shares one per process or per thread.
29. QUAL-014. The marker that labels a test as fixture, simulation or real is not named.

## Contradictions

Items marked blocking sit on the first-test build path.

1. Blocking. MCP-001, BASE-021 and MCP-010 run `metaform mcp` with no verb. CLI-001 and BASE-006 require `metaform <module> <verb>` and name tools `<module>_<verb>`.
2. Blocking. MCP-017 has the installer use the SDK's stdio client. D28 makes install a chassis verb, and BASE-026 and MCP-001 keep `mcp` out of the chassis, whose import must succeed without it.
3. Blocking. MCP-009 requires the served text to be byte-identical to the stored intake instructions. MAP-043 requires the served instructions to contain the project id and target value.
4. Blocking. Canonical Intake says "Return only the final xml shape" with `deliverable_format="xml"`, and MCP-009 serves it unaltered. MAP-040, LAYER-001 and STORE-024 have the agent write through tools. Whichever answer D8 gets, the served text contradicts it.
5. Blocking. MAP-041 puts the target type and value on the project record. STORE-002's `projects` table has only `project_id`, `path` and `path_key`.
6. Blocking. STORE-025 and STORE-028 cite chassis commands `metaform where`, `element`, `layer`, `identity` and `revisions`. CLI-001's chassis verb list has none of them. STORE-026 uses `metaform map element add` and MCP-004 uses `map_where`, which are module commands.
7. Blocking. The 1.1 schema allows role AUE on a nested element. STORE-011 allows only DE, SE and NE on subtypes. MAP-017 requires a role on subtypes, while STORE-011 and STORE-024 allow null.
8. Blocking. MAP-010 and MAP-013 say the store checks address form: lowercase, digits and underscores. STORE-008 says no address is refused and takes the address "as given", and STORE-026 lists no malformed-address error.
9. Blocking. STORE-012 and STORE-024 have `add_ref` add refs to the current revision of an existing thing. STORE-017 says a thing in an immutable layer changes only by a new revision.
10. CLI-024 keys a stored setting by owner and key. STORE-002's `settings` key is scope and key, with no owner column. CLI-013 names "saved and glued tables", while STORE-002 names `settings` and `glue`.
11. CLI-009 says every error exits 2. BASE-031 says failed exits 1, and recommends 2 for cancelled.
12. BASE-002 says `export` writes every project's data. STORE-027 exports one project or chosen layers, and its document has no form for more than one project.
13. LAYER-013 says memory entities are elements and joins. STORE-020 says they are elements, joins, subtypes and type addresses.
14. LAYER-006 recommends hiding a single item. D20 recommends whole layers only.
15. STORE-005 forbids a SCAN in any STORE-025 read. `layers()` lists every layer, and the default root selection of "all layers" in STORE-019 must read the whole `layers` table.
16. BASE-009 awaits a coroutine in the running loop inside the MCP server. MCP-002 runs tool calls in a worker thread, where no loop is running.
17. MAP-012's rule reads `code.loop.main` as "main loop code". The Canonical Intake reading example gives "main loop program code".
18. REQUIREMENTS-corrections.md says nothing in it applies until Rich approves. TRACE.md reads REQUIREMENTS.md with the corrections applied.
19. 00-index.md says SETTLED.md is now carried by the records, while SETTLED.md's header says it holds design "the spec has not absorbed yet". TRACE marks REQ-001 to REQ-003 NOT COVERED, while the index's Authority section carries them.

## Resolution

Each gap, with the record that now closes it or the NEW question it became. Records marked recommended in their Status are engineering choices made to close the gap.

### Blocking the first working test

1. Behavior defined by existing code: BASE-035 declarations, `Stop` and `Context`; BASE-009 `call`; BASE-010 events; BASE-015 literals; BASE-021 pyproject; BASE-037 discovery and `RESERVED`, with BASE-014; CLI-006 overview text; CLI-008 indexes; CLI-013, CLI-014, CLI-016, CLI-017, CLI-018, CLI-019 settings behavior; CLI-022 always-shown commands; CLI-026 settings screen; CLI-028 status; CLI-029 help layouts; MCP-002 serve; MCP-003 tools; MCP-004 surface; MCP-006 errors; QUAL-003 minimum Python.
2. Project ids, duplicates and missing paths: STORE-031.
3. `add_element` on a held address: STORE-009.
4. `ctx.store` with no project and unregistered ids: STORE-023.
5. Shape of nouns: BASE-035 `Noun`, with BASE-043.
6. Setting kinds over MCP and list syntax: CLI-027.
7. Tool result content and returned ids: BASE-036, STORE-023.
8. The map module: BASE-038.
9. The intake module and its stored text: BASE-039.
10. The intake layer's name, variable and provenance: BASE-039.
11. Recognizing an intake layer and half-written intakes: STORE-032, MCP-009.
12. Nested elements in the 1.1 schema: MAP-040.
13. Where nested refs belong: MAP-040.
14. A result with no AUE element: MAP-040, MAP-042.
15. Base text, notice and status line wording: MCP-007, MCP-009, CLI-028.
16. Modules on in the first test: MCP-024.
17. Where the installer finds its source: MCP-010, BASE-041.
18. Python check, tool detection, uv install command: MCP-013, MCP-016.
19. Files backed up for command-registered tools, the confirmation, the timestamp: MCP-015.
20. `~/.agents/skills`, the skill text, Antigravity: MCP-014, MCP-021, MCP-016.
21. Rules of the automated first-test run: MCP-024.

### Other gaps

1. Applying and visible reads: STORE-035.
2. Raw and in-context node reads: STORE-025.
3. Project starting selection: STORE-035, LAYER-007.
4. Unresolved selection: STORE-035, LAYER-007.
5. Re-examination marks: STORE-036, LAYER-011.
6. Default memory layer and its recognition: STORE-020, LAYER-012.
7. Memory command and tool names: BASE-040.
8. Search scope: STORE-020.
9. Finding a bare id's kind: STORE-033.
10. Format of `changes` and retyping: STORE-034.
11. Retiring nodes with dependents: STORE-034.
12. What "the same properties" compares: STORE-024.
13. `value` and `extra` of items: STORE-015.
14. Join types and empty fields: MAP-020.
15. `short_name` edge cases: MAP-012.
16. Export and import grammar and partial exports: STORE-027.
17. Project record, row numbers and ref owners in exports: STORE-027.
18. The query verb: STORE-028.
19. Build output, packing and carried dependencies: BASE-041.
20. The direct-run bootstrap: BASE-042.
21. `start`, `stop` and task ownership: BASE-018.
22. Showing cancel requested: BASE-031.
23. Help for a verb filtered by system: BASE-016.
24. Values of `--project` and `--commands`: CLI-030.
25. Status display of inherited and narrowed context: CLI-028.
26. Tool nouns and detection: MCP-016.
27. Proof timeout and folder: MCP-017.
28. Connections and threads: STORE-037.
29. Fixture, simulation and real marker: QUAL-014.

### Contradictions

1. `metaform mcp` with no verb: now `metaform mcp serve`, CLI only, MCP-001, MCP-010, BASE-021, BASE-035.
2. Installer using the SDK client: MCP-017 uses the chassis's standard-library probe.
3. Byte-identical text against filled target: BASE-039 and MCP-009 serve the stored text with only the target attributes and any `{project_id}` filled; MAP-043 updated.
4. XML answer against writing through tools: NEW question, chassis section question 9, and map section question 15.
5. Project target columns: STORE-002, STORE-031.
6. Chassis read commands: reads are `metaform query`, STORE-028, and the map module's verbs, BASE-038; STORE-025 and STORE-026 examples updated.
7. Roles on nested and subtype elements: MAP-040 maps the 1.1 nested element to the provider; MAP-017 and STORE-009 agree that the intake writes a role and the store does not refuse a missing one.
8. Address form checks: STORE-008 checks form only, matching MAP-010 and MAP-013.
9. `add_ref` on immutable things: STORE-012 and STORE-032 allow it only while the layer is open.
10. Settings keyed by owner, table names: STORE-002, CLI-013, CLI-024.
11. Exit codes: BASE-031 and CLI-009 now agree: 2 user error, 1 failure, 3 cancelled, 130 interrupted.
12. Export of every project: BASE-002 and STORE-027, with `all` and a multi-project document.
13. Memory entities: STORE-020 confirms elements and joins and marks subtypes and types recommended, matching LAYER-013.
14. Hiding one item: LAYER-006 now follows D20, whole layers only.
15. Listing reads against the no-scan rule: STORE-005 allows a scan only for the two listings.
16. Async verbs in the MCP server: BASE-009 and MCP-002; coroutine verbs run in the server loop, plain functions in a worker thread.
17. Reading of `code`: MAP-012 and MAP-014 follow the intake's example, main loop program code.
18. Corrections not yet approved: TRACE.md header.
19. Index against SETTLED.md and TRACE: TRACE.md now maps REQ-001 to REQ-003 to the index Authority section. SETTLED.md's header still says the spec has not absorbed it; that file is outside this pass and is left for the orchestrator to update.

### NEW design questions

- Chassis section question 9: the Canonical Intake response protocol and writing through tools.
- Chassis section question 10: optional record fields written as `name=value` nouns.
