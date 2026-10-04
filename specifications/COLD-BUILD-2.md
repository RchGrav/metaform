# Cold build check, run 2

Points where a builder working only from specifications/ would have to guess, choose between readings, or invent. Items already in OPEN-QUESTIONS.md or in a section's Open questions list are left out. Ordered by the build order in 00-index.md.

## Blocking the first working test

1. **STORE-005, STORE-020, STORE-019.** The plan test forbids any `SCAN` outside `layers()` and the project list. A correct build still scans: FTS5 `search` plans report `SCAN item_text VIRTUAL TABLE INDEX`, resolving the root selection reads `layers()` and the whole of `root_selection`, and removing hidden layers reads the whole of `hidden_layers`. The step 1 test, written first, fails on a correct build, and the spec does not say which reads are exempt.

2. **STORE-024, STORE-013, STORE-007.** Every write takes `layer`, and `layers` has both `layer_id` and a unique `name`. No record says which one the operations accept. BASE-036 and BASE-043 pass the name, and `intake begin` returns the name. STORE-007 says how element, join, subtype and item ids are made, but nothing says how a `layer_id` is made.

3. **STORE-024 `add_join`, STORE-025 `element`, BASE-038 node nouns.** A ref is "address or element id". An id is 32 lowercase hex characters, STORE-007, which also passes the address check of STORE-008 as a one-segment address. No rule says which reading wins, so `add_join` in the fixture intake can resolve the wrong way.

4. **BASE-035, BASE-038, BASE-039.** Noun kinds are `str`, `int` and `json` only. `new-layer` takes the nouns mutable, hideable and transitive, and `intake begin` takes blinded, and all four are booleans. There is no CLI form for a boolean noun and no MCP schema type for one. CLI-015's `--name` and `--no-name` apply to settings, not nouns.

5. **MCP-003, CLI-027.** MCP-003 types each noun "by CLI-027 and BASE-035", but CLI-027 covers only setting kinds. The JSON Schema for a `json` noun, used by `refs` and `extra`, is not given. `list_tools` has to produce it for `map_add-element` and `map_add-join`.

6. **BASE-041.** The spec does not say how `metaform build` makes a wheel from an installed Metaform that has no source tree. It names no build tool or backend, and does not say how METADATA and RECORD are written. It names `uv pip download`, which uv does not provide as far as I know, and "or an equivalent" leaves the method open. MCP-024 builds the wheel in its first automated step.

7. **BASE-041, BASE-024, BASE-026.** In the first test `mcp` is on, and its dependencies are compiled. BASE-041 says a compiled distribution "is not carried and makes the build print which module needs it", and also that the wheel takes "a platform tag when a carried dependency is compiled". It does not say whether the build fails or goes on, or which tag the wheel then gets.

8. **MCP-002.** The spec gives the call `Server('metaform', version=..., instructions=..., on_list_tools=..., on_call_tool=...)`. The low-level `Server` in the `mcp` 1.x SDK that I know registers handlers with decorators and has no `on_list_tools` or `on_call_tool` keywords. No SDK version is pinned beyond `mcp>=1.10`, so the builder has to choose between the spec's form and the SDK's.

9. **MCP-008, MCP-024, BASE-038 to BASE-040, MCP-001.** MCP-024 checks that the instructions hold the sections of map, intake, memory and mcp. MCP-008 refuses an empty `purpose`. None of the four `purpose` texts is given, so agent-facing text would be invented. MCP-007 gives no separator between sections beyond the `## <id>` heading.

10. **MCP-024, MCP-017, MCP-010.** The proof step runs `uvx --from <wheel> metaform mcp serve`, which fetches `mcp` from PyPI. The spec does not say whether the automated test may use the network, or how CI gets a warm uv cache. Step "starts `metaform mcp serve` with that folder as its working folder" does not say whether that is the registered uvx command or the test's own interpreter. It also does not say how the temporary `METAFORM_HOME` reaches it: the registered command carries no environment, so this relies on inheritance nobody states.

11. **CLI-010, CLI-019, CLI-021, BASE-039, BASE-038.** Only `settings.number` and `settings.choice` are named. There are no named functions, or ways of passing `scope`, `short`, `switches`, `group`, `label`, `min` or `max`, for `str`, `bool` and `list` settings. Step 3 needs them for `project` and `commands`, the map's `raw`, and the intake's `intake_file`. `intake_file` also has no stated kind or default.

12. **MCP-024, MCP-015.** The test "checks ... the backups". The fake `claude` writes nothing, and a fresh temporary home has no `~/.claude.json`. MCP-015 backs up only existing files, so the test has nothing to check unless a fixture config is created first, and the spec does not say what that fixture holds.

## Other gaps

1. **BUILD-BRIEF, QUAL-011, CLI-010, CLI-015, BASE-017, STORE-031, MCP-014.** Many records give only a change to current code, in the form "the current X does Y; that changes". Behavior the spec never states exists only in that code: the nouns of `list` and `add`, `enable module` and `disable module`, the `config --show` layout, `tui.py` and `docs.overview`. A cold build with no repository cannot reproduce it.

2. **MCP-010.** The source is "that wheel's absolute path" when Metaform runs "from a wheel file, directly or under uvx". Under uvx the package is installed into an environment, and the spec gives no way to find the wheel it came from.

3. **BASE-039.** The spec does not say when the "byte copy at build time" of Canonical_Intake.xml is made: a repo build hook, `metaform build`, or a checked-in file. Filling `<target>` attributes gives no escaping rule for values that hold `"`, `&` or `<`, which inline targets will.

4. **BASE-039, STORE-024.** Layer names have one-second resolution. `layer()` returns the existing layer when kind, module, variable and properties match, and provenance is not compared. Two `intake begin` calls in the same second therefore share one layer without an error.

5. **MAP-040, STORE-012, STORE-032.** A nested 1.1 element whose address an element already holds adds its refs to that element "while the intake layer is open". `add_ref` checks the owner's own layer. When the existing element belongs to an earlier, complete intake, the ref is refused, and MAP-040 does not say what happens then.

6. **MCP-009, MCP-007.** The spec does not say whether the no-intake notice appears when the folder resolves to no project. MCP-017's probe hits this case, since it runs in the user's home.

7. **MCP-017.** The probe reads "one JSON response per line". It does not say what to do with server notifications or log messages that arrive before a response.

8. **MCP-019.** "Read each tool's registration before writing" gives no read mechanism for any tool, and the fake tools in MCP-024 cannot answer one.

9. **BASE-036.** The readable CLI form is "one `key: value` line per top-level field". The spec does not say how a field whose value is a list or an object, such as refs or a joins list, is printed.

10. **BASE-037.** Folder modules import as `metaform_module_<place>_<id>`, but the strings used for place are not given.

11. **STORE-020.** The FTS5 triggers are only described as "kept in step". The spec does not give the delete and update trigger form an external-content table needs, or say whether superseded revisions and JSON quoting in `value` are indexed and matched.

12. **STORE-027.** The spec does not give the shape of entries in `requires` or `hidden`, or the fields of each row object beyond "a `current` flag".

13. **CLI-006.** The spec says what `metaform help intro` covers but not its text.

14. **STORE-006.** The spec says "Each data access operation opens `BEGIN IMMEDIATE`". It does not say whether that includes reads, which would then take the write lock and serialize every reader.

## Contradictions

1. **STORE-032 vs CLI-028.** STORE-032 says status "still shows the no-intake notice" while an intake layer is open, and MCP-009 says the same for instructions. CLI-028 line 9 prints `Intake: open layer <name>` in that case, as a separate branch with no notice.

2. **MAP-012 vs Canonical_Intake.xml.** MAP-012 says it follows the intake's reading example and gives "event data bus program code". The intake text gives `code.bus.data.event` as "event data bus code".

3. **MAP-032 vs STORE-011.** MAP-032 says "until then the store allows none of the three". STORE-011's schema has no rule against one element being a subtype in two joins, and STORE open question 4 says the store currently allows it.

4. **BASE-038.** The record says "The only switch is `--raw`" and also that `refs` and `extra` "are `json` nouns or switches".

5. **BASE-019 vs QUAL-006.** BASE-019 puts the template's tests inside the template folder. QUAL-006 says tests live in `tests/`.

6. **STORE-024 vs STORE-032.** STORE-024 says `layer()` returns a layer that is "open". STORE-032 says a mutable layer, memory included, is created complete.

7. **STORE-019 vs STORE-035 and LAYER-007.** STORE-019 starts resolution from "all layers unless the read supplies one". STORE-035 and LAYER-007 start from every complete layer.

8. **STORE-036 vs STORE-024.** STORE-036 and BASE-038's `new-layer` say `layer(...)` takes `sources`. The `layer` signature in STORE-024 has no `sources` parameter.

9. **BASE-039 `discard` vs STORE-017 and STORE-024.** `discard` removes an open intake layer "and everything written to it". STORE-017's acceptance forbids any `DELETE` on `elements`, `joins` or `subtypes`, and STORE-024 has no operation that removes a layer.

10. **SETTLED.md vs MCP-010.** SETTLED gives the registration as `uvx --from <wheel or distribution> metaform mcp`. MCP-010 and MCP-016 give `... metaform mcp serve`. The spec wins under the Authority rule, but the source still says otherwise.

11. **STORE-013 vs BASE-038 and CLI-001.** STORE-013 shows layers through `list layers`. The chassis `list` verb's nouns are never given, and the layer listing is specified as `map layers` and `query layers`.

12. **QUAL-011 vs BUILD-BRIEF.** QUAL-011 has the cold build agent work with no repository. BUILD-BRIEF and many records depend on the current `src/metaform` code for any behavior they do not change, so a spec-only build cannot reach a complete list.

## Resolution

Blocking the first working test:
1. STORE-005 names the reads allowed a whole-table read, `layers`, `projects`, `root_selection`, `hidden_layers`, and the FTS5 index match of `item_text`; its plan test checks exactly those.
2. STORE-007 generates layer ids as UUID4 hex; STORE-013 makes every layer argument a layer reference, an id or a name, and forbids names in the id form.
3. STORE-007 and STORE-008: an address may never be in the id form, so an argument is an id exactly when it matches `^[0-9a-f]{32}$`; BASE-038 and STORE-024 state it for nouns and refs.
4. BASE-035 adds the `bool` noun kind, its CLI form `true` or `false`, and its MCP schema; BASE-038 types mutable, hideable, transitive and blinded as `bool` nouns.
5. BASE-035 gives the MCP schema of every noun kind, with `json` nouns carrying their own `schema`; BASE-038 gives the schemas of `refs` and `extra`; MCP-003 points to BASE-035.
6. BASE-041 writes the wheel with `zipfile` from the installed package, with `METADATA`, `WHEEL` and `RECORD` per PEP 427, and resolves carried dependencies with `uv pip compile` and `uv pip install --target`, both verified.
7. BASE-041: a compiled dependency is not carried, stays in `Requires-Dist`, the build succeeds and names it with its module, and the wheel is always `py3-none-any`.
8. MCP-002 pins `mcp>=2.2`, where the low-level `Server` takes `on_list_tools` and `on_call_tool` as constructor arguments; the current chassis runs on mcp 2.2.0.
9. MCP-008 gives the exact `purpose` text of map, intake, memory and mcp; MCP-007 gives the exact assembly and separators.
10. MCP-024 states network or a warm uv cache, that the registered uvx command is what starts, and that every process inherits the test environment including `METAFORM_HOME`.
11. CLI-010 names one declaration function per kind, `text`, `number`, `boolean`, `items`, `choice`, with the common keyword arguments; BASE-039 declares `intake_file`.
12. MCP-024 adds a `.cursor/mcp.json` fixture with an existing entry, installs `cursor` too, and checks its merge and its byte-identical backup.

Other gaps:
1. CLI-031 states every chassis verb's nouns, switches, output and errors; CLI-026 already states the settings screen; CLI-006 states the overview and now the intro text; QUAL-011 requires records to state full behavior.
2. MCP-010 uses `METAFORM_WHEEL`, set by the bootstrap of BASE-042, for a direct run, and `last_build` otherwise, uvx included.
3. BASE-039: the resource is a checked-in copy kept equal to the spec file by a repository test; target attributes are XML-escaped in a stated order.
4. BASE-039: layer names carry six random hex characters, and `begin` is refused while an intake layer is open.
5. MAP-040: when the existing element belongs to a complete layer, the nested element's refs go onto the join that holds it.
6. MCP-009: a folder with no project gets a register line instead of the notice.
7. MCP-017: how each kind of line on standard output is handled, and what fails the proof.
8. MCP-019: the `installs` table in the base database, STORE-002, records what was set up; JSON-merged configs are also read.
9. BASE-036: list and object values print as compact JSON on their line; a list result prints one line per entry.
10. BASE-037: place is `system` or `user`.
11. STORE-020 gives the three FTS5 triggers, indexes every revision, returns current ones, and quotes search text.
12. STORE-027 gives the row object members, the `hidden` list and the `requires` entries.
13. CLI-006 gives the intro text.
14. STORE-006: reads use a deferred `BEGIN`, writes `BEGIN IMMEDIATE`.

Contradictions:
1. CLI-028 now keeps the notice while an intake layer is open and adds a line naming the open layer, matching STORE-032 and MCP-009.
2. MAP-012 now follows the rule without a root phrase, and the disagreement inside the Canonical Intake's two examples is NEW map question 16.
3. MAP-032 and STORE-011 now agree: the store refuses a second holder of a subtype address.
4. BASE-038: `refs` and `extra` are nouns only; `--raw` is the only switch.
5. QUAL-006 collects module tests in their module folders, matching BASE-019.
6. STORE-024: an immutable layer is created open and a mutable one complete, matching STORE-032.
7. STORE-019 starts from the read's root, else the project's `root_selection`, else every complete layer, matching STORE-035.
8. STORE-024's `layer` signature takes `sources`.
9. STORE-024 adds `discard`, and STORE-017 allows deletes only inside it, only of an open layer; BASE-039 and STORE-032 use it.
10. Not changed here: SETTLED.md is outside this pass. The spec wins under the index's authority rule; SETTLED.md's registration line should read `metaform mcp serve`.
11. STORE-013 now shows layers through `query layers` and `map layers`.
12. QUAL-011 and CLI-031, with the fills above, make the spec stand alone; BUILD-BRIEF's reference to current code is a starting point only.
