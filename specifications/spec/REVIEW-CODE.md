# Code review against the quality standard and the spec

Branch `chassis` at `3e610e7`, reviewed 2026-09-25. Scope: all of `src/metaform`, with `src/metaform/data/` and `src/metaform/modules/`. The bar is `specifications/code_quality_standards.md` through QUAL-001. The contract is this folder.

Each finding gives the place, what is wrong, the record or standard item it breaks, why it matters, and the fix. Findings marked "run" were reproduced in an isolated `METAFORM_HOME`. The rest are read from the code; the one inferred behavior is marked "inferred".

## Count

| Severity | Count |
|---|---|
| Critical | 1 |
| High | 11 |
| Medium | 11 |
| Low | 7 |

## Tool results

Pyright 1.1.414 and ruff 0.16.9 were installed into `.venv` with `uv pip`. The repo has no pyright or ruff configuration, so each ran with its own defaults, plus one strict pyright run from a scratch config.

- `pyright src`, basic mode, with the venv interpreter: 34 errors, 20 outside tests.
  - `data/store.py:416`, four errors: the descriptor dict is `dict[str, str | int]`, so `name`, `name_length` and `role` reach `Element(...)` and `short_name` with the wrong types.
  - `modules/intake/__init__.py:115,124`: `elements` may be None where it is iterated.
  - `cli.py:537`: the sink lambda returns `int`, not `None`.
  - `tui.py`: 13 errors, Optional subscripts at 243, 246, 247, 386, 409, 411, 426 and 540, None iterated at 468, and a wrong `FormattedTextControl` text type at 124 and 126.
  - Tests: 14 errors, Optional member access in `intake/tests/test_intake.py` and `map/tests/test_map.py`.
  - Without `--pythonpath .venv/bin/python`, pyright does not find `mcp` or `prompt_toolkit` and reports 47. Nothing in the repo pins the interpreter.
- `pyright`, strict mode over `src/metaform` with tests excluded, the QUAL-004 mode: 750 errors.
  - By file: `tui.py` 469, `modules/intake/__init__.py` 60, `data/store.py` 43, `cli.py` 35, `modules/intake/schema.py` 30, `instructions.py` 14, `data/exchange.py` 13, `install.py` 12, `data/ids.py` 12, `data/corrections.py` 11, and 51 across the other files.
  - Mostly unknown or partially unknown types from `Any` at boundaries, missing parameter types, private usage and unnecessary isinstance.
- `ruff check src`, ruff 0.16.9 defaults: 50 errors.
  - 15 BLE001 blind `except Exception`.
  - 6 I001 unsorted imports, for example `tui.py:6` and `modules/intake/__init__.py:9`.
  - 5 F541 f-strings without placeholders.
  - 4 UP017 and 4 F401 unused imports, including `install.py:24` `__version__` and `modules/intake/__init__.py:21` `Store`.
  - 3 SIM118, 2 SIM102, 2 ISC004, 2 PLW1510 `subprocess.run` without `check`, 2 TRY004, 1 SIM117 and 1 RUF059.
  - 2 S110 try-except-pass, at `loader.py:184` and `tui.py:333`, and 1 S112 try-except-continue, at `instructions.py:40`.
  - `ruff check --isolated` gives 46.

---

## Critical

### C1 `intake_submit` over MCP reads a server-side file, or the server's own stdin
- Where: `modules/intake/__init__.py:75-86`, called from `submit` at line 92. `modules/mcp/server.py:113` passes arguments through unchecked.
- What: `_elements` treats any string `elements` as a path and reads it. When the value is `-`, it calls `sys.stdin.read()`. The code never checks `ctx.surface`. Over MCP the schema declares an array, but nothing enforces the schema, see H1. An agent that sends `"elements": "-"` makes the stdio server read its own JSON-RPC input stream to EOF. That consumes the protocol messages, and the server hangs. A string path reads any file the server user can read, and the text of the Stop depends on whether the file exists and whether it parses.
- Breaks: MCP-002, the stdio transport. BASE-039, whose input over MCP is the array. The standard's items on clear boundaries and explicit failure behavior.
- Why it matters: one malformed tool call disables the agent's whole MCP session, with no error returned.
- Fix: accept the file and `-` forms only when `ctx.surface == 'cli'`. Over MCP, refuse a string with a Stop naming the array form. Fixing H1 also closes this.

## High

### H1 MCP tool arguments are never validated or converted
- Where: `modules/mcp/server.py:105-118` `_prepare` and `:121-142` `run_tool`.
- What: nouns and switches are copied from the JSON arguments as they come. The MCP path skips everything the CLI path does:
  - no required-noun check;
  - no kind check for `int`, `bool` or `json`;
  - no `settings.parse`, so no select-choice check and no min or max;
  - no `settings.SettingError` handling.

  The SDK's low-level `Server` does not validate `input_schema`; mcp 2.2.0 was checked. Run:
  - `helloworld_greet {}` returns `Error: KeyError: 'name'` with `Next: metaform list modules`.
  - `helloworld_greet {"name":"x","loud":"no"}` shouts, because the string is truthy.
  - `helloworld_wait {"seconds":"abc"}` returns a raw `TypeError`.
  - `helloworld_greet {"name":{"a":1}}` stores a dict.
- Breaks: MCP-005, MCP-006 and CLI-027, which require one written form per kind and the same error and Next line as the CLI. BASE-035, which fixes the MCP form of each noun kind. The standard's strong typing at boundaries.
- Why it matters: the same verb behaves differently on the two surfaces. Agents get wrong results or an unhelpful Next line.
- Fix: put one chassis function in the common base that turns a JSON arguments dict into nouns and switches for a `Verb`. It checks required nouns, checks each noun's JSON type against its kind or `schema`, and puts every switch through `settings.parse`, or through a typed check for booleans and lists, raising `Stop`. The MCP module calls it in `_prepare`.

### H2 A second intake is accepted into a metaform that already has one
- Where: `modules/intake/__init__.py:89-142`.
- What: `submit` never checks `store.has_intake()`. Run: two submissions of the same elements make two intake layers. The second layer's elements resolve to the first layer's elements, and every join is stored twice, so `joins('code.app')` returns 2.
- Breaks: MAP-045, where each metaform holds one intake map. MAP-040 and STORE-032, where the intake map is the base the correction stack applies to.
- Why it matters: the map gets duplicate joins, and `status` points at the latest intake layer while element identity stays with the first. A second intake cannot be corrected away cleanly.
- Fix: inside the atomic block, refuse the submission when the active metaform already has an intake. The Stop names `metaform add metaform <name>`, the confirmed way to start over.

### H3 Hidden and masked layers reach agents through search, links and the memory module
- Where:
  - `data/store.py:1301-1303`: `links_to` with `layer` given skips the resolver.
  - `data/store.py:1411-1416`: `search` with `layer` given skips it. Without `layer`, it checks only `res.start` and never the select and mask at the item's address.
  - `modules/memory/__init__.py:142-155`: `read_graph` goes through `layer_items`, `search_nodes` through `search(layer=...)`.
  - `modules/memory/__init__.py:172`: `open_nodes` goes through `links_to(layer=...)`.
- What: run: after `store.hide('memory')`, `store.node` correctly omits the memory, but `memory read-graph` and `memory search-nodes` still return it. The memory module's own `details` says the layer "takes part in select and mask like any layer".
- Breaks: LAYER-006, where hiding removes a layer from every view and agent context. LAYER-007 and STORE-019, where selection applies on every path by which knowledge reaches an agent. MCP-024, the first working test, where memory visibility follows select and mask. The `data/store.py` docstring, which says no read bypasses selection.
- Why it matters: the read paths agents use most, search and read-graph, ignore the switch the orchestrator uses to control what an agent sees.
- Fix: in `search` and `links_to`, always filter through `res.reaches(layer_id, address_of(target))` unless `raw=True`, and treat `layer` as a narrowing filter, never a bypass. Make `read_graph` use a context read: take the memory layer's items and keep each only where `res.reaches` holds at its target, or add a `raw` switch for the unfiltered form. Add a test per path: hide, then mask, and each read omits the memory.

### H4 CLI async verbs that spawn tasks break shutdown
- Where: `cli.py:495-515` `_run_async`, `module.py:154-157` `Context.spawn`, `loader.py:167-173` `spawn`, `loader.py:176-179` `_unload`.
- What: `_run_async` runs the verb on a fresh loop and then `loop.close()`s it without cancelling or awaiting the tasks the verb spawned. The tasks stay in the module's `tasks` set. At exit, `atexit` calls `reset` and then `_unload`, whose `task.cancel()` raises `RuntimeError: Event loop is closed`; this was reproduced with the same asyncio sequence. `_unload` has no guard, so `stop` never runs and the modules after it are never unloaded. Python also prints "Task was destroyed but it is pending". The loop also closes without `shutdown_asyncgens`.
- Breaks: BASE-018: shutdown cancels tasks, waits, then calls `stop`. QUAL-010, shutdown with work in flight. The standard's item on reliable shutdown paths.
- Why it matters: this is the exact silent lifecycle failure QUAL-010 exists to catch. The first module that uses `ctx.spawn` from a CLI verb leaks and skips its cleanup.
- Fix: in `_run_async`, before closing the loop, await the owning module's task shutdown, the same code as `unload_async` without the stop, then `loop.run_until_complete(loop.shutdown_asyncgens())`. In `_unload`, skip tasks whose loop is closed and are therefore already finished.

### H5 Unload and shutdown do not follow the stated order, and failures vanish
- Where: `loader.py:176-188` `_unload`, `loader.py:191-207` `unload_async`.
- What:
  - The sync `_unload`, used by `reset`, `set_enabled`, `atexit` and a failed start, cancels tasks and calls `stop` at once, without waiting for the tasks to finish.
  - A `stop` that raises is swallowed with `pass`, and nothing reports it.
  - `unload_async` does wait, but nothing calls it.
  - When `stop` raises in `unload_async`, `item.module` is already None while its settings and `sys.modules` entry stay, which leaves a half-unloaded module.
- Breaks: BASE-018: cancel, wait for them to finish, then call `stop`. The standard: explicit failure behavior, no ambiguous state.
- Why it matters: `stop` can release resources that running tasks still use, and a failing `stop` is never known.
- Fix: keep one unload procedure. When a loop owns the tasks, await them. When no loop runs, run `asyncio.gather(..., return_exceptions=True)` on the tasks' own loop if it is open. Then call `stop` in `try/finally` so withdrawal always completes, and record a `stop` failure as the module's `problem` so `list modules` shows it. Delete `unload_async` or make it the single path.

### H6 Reload leaves stale code, and entry-point modules lose their settings
- Where: `loader.py:73-86` `_import`, `loader.py:187-188` and `:206-207`, which pop only the package name. `settings.py:108-122`, where settings are declared at import time.
- What:
  - Run: after `loader.reset()`, `metaform_module_system_intake.schema` stays in `sys.modules`. The next import reuses the old submodule, so a reload never picks up a changed submodule, and a setting declared in a submodule is never declared again.
  - For entry-point modules, `_unload` removes nothing from `sys.modules`. `_import` then gets the cached package from `importlib.import_module`, and its module-level `settings.*(...)` calls never run again. After any reset, including `enable` and `disable` of any module and every settings-screen refresh, see M2, the module's settings are gone from the schema, help, `set` and the settings screen.
- Breaks: BASE-018, where load, unload and load show each setting exactly once. CLI-024, where settings return with their module.
- Why it matters: after an ordinary `metaform enable x` in the same process, a third-party module is silently missing its switches.
- Fix: on unload, pop the package and every `sys.modules` key under `<import_name>.`. For entry points, either run a declared registration function on every load instead of relying on import side effects, or record the settings each module declared at first import and re-register them on load.

### H7 Import is not one transaction and can leave an orphaned store
- Where: `data/exchange.py:159-191` `import_document`, `:194-209` `_import_store`, `home.py:195-201` `register`, `home.py:371-378` `import_metaform`.
- What:
  - One import makes a base-database write in `register`, one committed store transaction per metaform, then another base write in `import_metaform`, in that order. A failure part way through leaves the earlier metaforms imported.
  - The store is committed before the metaform row exists. When the metaform id already belongs to a different project, which happens when importing with the `project` argument, the store is written under this project's path. `import_metaform` then returns False, and the data is unreachable while the report says "skipped".
  - `register` uses `INSERT OR IGNORE`, so a conflict on `path_key` is silently ignored. The later `metaforms` insert then fails its foreign key with a raw `IntegrityError` from the base database.
  - `register` computes `path_key` with `normcase` only, while `home.path_key` resolves the path.
- Breaks: STORE-027, where import runs in one transaction. STORE-006.
- Why it matters: import is the backup and restore path. A partial or orphaned import breaks the rule that importing never loses data.
- Fix:
  - Validate the whole document first, see H8.
  - Check metaform ownership across all projects before writing, and refuse a metaform id owned by another project.
  - Write the base rows and the store rows as one unit: begin the base transaction, write each store, and commit the base last. On any failure, roll back the base and delete any store file created in this run.
  - Make `register` report a conflict as a StoreError instead of ignoring it, and use `path_key`.

### H8 Import documents are not validated, and their keys become SQL identifiers
- Where: `data/exchange.py:310-315` `_insert`, `:169` `home.Project(**entry['project'])`, and every `row['...']` access in `_import_rows`.
- What:
  - `_insert` builds the column list from the keys of each JSON row and puts them into the SQL text.
  - Missing keys raise `KeyError`, extra keys on `project` raise `TypeError`, and unknown columns raise `sqlite3.OperationalError`. None of these is a StoreError, so the user gets a type name and `Next: metaform help`.
  - A crafted key can inject SQL into the INSERT, for example a column list followed by a `SELECT` that copies other rows of the store.
- Breaks: STORE-026, where every error names one next step. The standard's strong typing at boundaries. STORE-023, where only the data access object's own queries run.
- Why it matters: import is the path by which other people's work, and agent work, enters a store.
- Fix: define the document shape once as typed records for each table: allowed columns and types. Check every row against it before any write, and build the SQL only from the fixed column lists in `schema.py`. Report all problems as one StoreError with each path.

### H9 The published package cannot start the MCP server
- Where: `pyproject.toml:10` and `:16`, `modules/mcp/__init__.py:15`, `module_metadata.py:114-118`, `loader.py:110-155`.
- What:
  - `[project].dependencies` lists only `prompt_toolkit`, and `mcp>=2.2` sits in the `dev` extra. The mcp module ships enabled and imports `mcp` and `anyio` only inside `serve`.
  - A wheel built from `pyproject.toml`, the repo wheel of BASE-022 and the published distribution of MCP-010, installs without `mcp`, so `uvx --from <it> metaform mcp serve` fails with a raw `ImportError`.
  - `DEPENDENCIES` is parsed but never checked at load, so `list modules` shows mcp as `on`.
  - Only `metaform build` writes module dependencies into `Requires-Dist`.
- Breaks: MCP-010, BASE-021 and BASE-022. BASE-015, where dependencies are read before import and reported.
- Why it matters: the documented install path yields a server that does not start.
- Fix: put `mcp>=2.2` in `[project].dependencies`, or in an extra that the uvx registration names. Make discovery check each `DEPENDENCIES` requirement with `importlib.metadata` and report a missing one as the module's load problem.

### H10 The installer proof leaks the child process when the server does not answer
- Where: `probe.py:113-128`.
- What: `open_session` creates the `Session`, and so the subprocess, internally. When `initialize` times out, hits EOF or fails, the exception escapes before `session` is assigned in `probe`. The `finally` block sees `None`, so the child is never closed or killed. Its stderr, the useful diagnosis, is also lost from the reason.
- Breaks: MCP-017. The standard's item on resource leakage on failure paths.
- Why it matters: every failed proof leaves a stray server process, on Windows too, and the report omits why it failed.
- Fix: create the `Session` in `probe` itself, inside the `try`, and call `request('initialize', ...)` on it there, so `finally` always closes it. Have `open_session` close the session before it re-raises.

### H11 QUAL-003, QUAL-004 and QUAL-005 are not in place
- Where: the repo root has no `.github/workflows`. `pyproject.toml` has no `[tool.pyright]` and no `[tool.ruff]`. `modules/template/` has no workflow file.
- What:
  - Nothing runs type checking, lint or tests on Linux, macOS and Windows.
  - Strict pyright over the chassis gives 750 errors. Basic mode gives 34.
  - Ruff results depend on the installed ruff version, because no rule set is pinned.
  - Five `# type: ignore` comments carry no reason: `data/records.py:34`, `settings.py:104`, `data/store.py:1409`, `install.py:251` and the one in the bootstrap text.
- Breaks: QUAL-003, QUAL-004 and QUAL-005, all confirmed.
- Why it matters: every other finding here would have been caught earlier, or kept from coming back, by these gates.
- Fix:
  - Add the three-system GitHub Actions matrix that QUAL-003 specifies.
  - Add `[tool.pyright]` with `typeCheckingMode = "strict"` for `src/metaform`.
  - Add `[tool.ruff]` with the chosen rule set; the rule set is an open question.
  - Copy the workflow into `modules/template/`.
  - Give each suppression a reason.
  - Then burn down the strict errors, starting with the common base: `module.py`, `data/`, `settings.py`, `context.py`.

## Medium

### M1 `module.call` inside a running loop blocks that loop
- Where: `module.py:160-171`. It is reached from `events.publish` at `events.py:28` when an async verb publishes in the MCP server's loop, and from `loader.discover` and `reset` inside the settings screen's `asyncio.run`.
- What: in a running loop, `call` runs the coroutine on a new loop in a worker thread, then blocks the calling loop on `.result()`. A sync subscriber also runs on the loop thread. The server cannot service other requests or deliver cancellation until every subscriber finishes. A subscriber's `ctx.spawn` binds to a loop that ends when `asyncio.run` returns.
- Breaks: BASE-009, where long work can be async without blocking other work in the same loop. BASE-031.
- Fix: give `Context` and `events.publish` an async path. Add `async def publish_async`, which awaits async subscribers and runs sync ones in `asyncio.to_thread`. Use it whenever a loop is running, and make `call` raise when it is invoked inside a running loop instead of hiding the block.

### M2 Every settings-screen refresh stops and restarts every module
- Where: `tui.py:47-49` `_Backend.rows`, called by `refresh` at line 284 after every action.
- What: `rows()` calls `loader.reset()` and then `discover()`. That runs every module's `stop` and `start` hooks, cancels their tasks, and hits H6 each time.
- Breaks: BASE-018, where `start` runs once per process. BASE-037, where discovery is cached and only `enable` and `disable` reset it.
- Fix: read `loader.discover()` without resetting. `loader.set_enabled` already resets when module state changes.

### M3 Ill-typed field values escape as raw errors
- Where:
  - `data/store.py:69-75` `_write` catches only `IntegrityError`.
  - `data/store.py:379-420`: `name_length` and `role` are unchecked in `add_element`.
  - `data/store.py:457-489`: `add_join` text fields are unchecked.
  - `data/store.py:679-707` `_changed_columns` writes arbitrary values.
- What: run: `add_join(..., purpose={'a': 1})` raises `sqlite3.ProgrammingError`, and `add_element(..., name_length='abc')` raises `TypeError` from `short_name`. On the CLI, the user sees `Error: ProgrammingError...` with `Next: metaform help`. Over MCP, the Next line is `metaform list modules`.
- Breaks: STORE-026 and CLI-009, which require an error that states what is wrong and one next command. MCP-006. The standard's typing at boundaries.
- Fix: in each write, check the shape of every column value, text or None for the text columns and int or None for `name_length`, and raise StoreError naming the field. Do not widen the except clause.

### M4 Elements from knowledge layers take any role string
- Where: `data/store.py:30`, where `ROLES` is never used, `:379-420` `add_element`, and the `map knowledge` noun help at `modules/map/__init__.py:283`, which invites the roles.
- What: run: `add_element('k1', 'code.y', role='BOGUS')` in a knowledge layer stores the role, and `element('code.y').role == 'BOGUS'`.
- Breaks: MAP-017, where the role is one of AUE, VE, DE, SE or NE. STORE-009 and D48, where an element made by a layer other than the intake carries no role.
- Fix: in `add_element`, refuse `role` unless the layer kind is `intake`, and there check it against `ROLES`. Update the noun help.

### M5 Peel leaves the automatically written relocation removals in the layer (inferred)
- Where: `data/corrections.py:135-170` `_write_relocation_removals` runs in `apply`, and `:237-245` `peel` never removes those rows.
- What: finishing a correction that moves an element writes `remove` rows for the moved element's intake joins. Peel returns the layer to building but keeps those rows. If the author then edits the element's change back to its old address and finishes again, the stale `remove` rows still apply, and the joins are removed with no relocation. This is traced from the code; it was not run.
- Breaks: STORE-017. The standard's item on state corruption across reversible paths.
- Fix: mark the generated rows, for example with a fixed `reason` prefix or a `generated` column. Delete them in `peel` before recomputing, so `apply` regenerates them from the layer's current content.

### M6 The installer is neither idempotent nor safe on partial failure
- Where: `install.py:259-279`, `install.py:159-164` `_merge`, `install.py:167-169` `_run`.
- What:
  - `_record` runs only after every tool is registered. When the second tool fails, the first tool is registered but not recorded. The next run then skips `remove` and calls `add` again, which duplicates the entry or fails on "already exists".
  - The result of `remove` is ignored.
  - `_merge` overwrites the user's config in place, so a crash mid-write corrupts it. It crashes with a raw `JSONDecodeError` on JSON with comments, which VS Code-style files allow, and on a top level that is not an object.
  - `subprocess.run` has no timeout, so a hanging `claude mcp add` hangs the install.
  - The proof at `install.py:282` probes the same command once per tool. It never shows that the tool's registered entry works.
- Breaks: MCP-015, MCP-017 and MCP-019.
- Fix:
  - Record each tool right after its registration succeeds.
  - Check the `remove` result.
  - Write merged configs to a temporary file in the same folder and `os.replace` it.
  - Refuse unparsable configs with a Stop naming the file and the backup.
  - Give every subprocess a timeout.

### M7 `data/store.py` is one 1482-line class with nine responsibilities
- Where: `data/store.py:46-1440`.
- What: one `Store` class holds about 90 methods:
  - layer administration;
  - map writes;
  - items and properties;
  - edit and remove;
  - corrections;
  - challenges and plans;
  - record building;
  - reads with paging;
  - metaform pass-throughs to `home`.

  Private helpers are shared across all of them.
- Breaks: the standard's small, cohesive components with stable interfaces, and code easy to inspect, test and change.
- Why it matters: STORE-023 makes this the only door to the data. Every module author reads it, and every change risks the rest.
- Fix: keep `Store` as the thin public facade. Move the writes, the reads, the record builders and the challenges into separate internal modules that each take a `Tx`, the way `corrections.py` and `selection.py` already do.

### M8 Hidden coupling through import-time registries, frame inspection and lazy-import cycles
- Where:
  - `settings.py:79`, `:97-105` `_declaring_module`, which walks `sys._getframe` to guess the owner.
  - `docs.py:38-50` and `cli.py:554-626`, which register help at import.
  - The function-level imports in `module.py`, `settings.py`, `context.py`, `instructions.py` and `events.py`, which exist to break cycles.
  - `cli.py:66` and `:307`, which use `settings._scope` and `_own_scope`.
  - `data/exchange.py:19`, which imports `session._open`.
- What: ownership of a setting depends on who is on the call stack when it is declared. Importing a module has global side effects. The import graph is cyclic, and the private helpers of one module are used from another.
- Breaks: the standard: no hidden coupling, clear ownership.
- Fix:
  - Give ownership explicitly: `loader` passes the owner into `settings.owned_by`, and a declaration made outside it is a programming error, not a stack guess.
  - Make `_scope` public as the documented `scope_of`.
  - Expose the connection opener from `session` as a public function.
  - Break the cycle by moving `Context` construction and the registries into one module that the others import one way.

### M9 `tui.py` is untyped, carries legacy names and swallows errors
- Where: `tui.py`, 603 lines.
- What:
  - 469 strict errors and 13 basic ones, for example Optional subscripts at 243 and 540.
  - Parameters that do nothing: `module` at line 96 and `declarations` at 282.
  - Names from an older design: `runtime`, `plugins`, `pins`.
  - `except Exception: pass` at 333.
  - Imports out of order at 6-26.
- Breaks: QUAL-004, strict typing of the chassis. The standard's easy-to-inspect code and explicit failure behavior.
- Fix: type the backend and the screen state as dataclasses. Drop the unused parameters. Rename to the spec's terms: module, glued. Report the refresh failure in the status line instead of passing.

### M10 The module contract is typed as `Any` where it crosses the boundary
- Where:
  - `module.py:59,92,110-112`: `Callable[..., Any]` for `run`, `handler`, `start`, `stop` and `status`.
  - `module.py:40`: `Noun.kind: str`.
  - `data/records.py`: `kind`, `state` and `op` are plain `str`.
  - `data/store.py:136,457,585,887`: element refs are `Any`, and `changes` is `dict[str, Any]`.
  - `loader.py:32,40`: `SYSTEM` and `Found.path` are `Any`.
  - `docs.py:160-240`: `module` and `verb` are `Any`.
- What: the spec fixes these shapes in BASE-035 and STORE-024, but the code does not state them, so pyright cannot check a module against the contract.
- Breaks: QUAL-004 and the standard's strong typing where interfaces cross boundaries.
- Fix:
  - Use `Callable[[Context], Any | Awaitable[Any]]` for verbs, start, stop and status, and `Callable[[dict[str, Any], Context], Any | Awaitable[Any]]` for handlers.
  - Use `Literal` types for noun kinds, node kinds, layer kinds, ops and challenge states.
  - Use `str | Node` for element refs.
  - Use `Traversable` for module paths.

### M11 Two reads page by scanning
- Where: `data/store.py:1169-1173`, the property phase of `layer_items`, and `:1404-1409` `search`.
- What:
  - `layer_items` compares `c.element_id || c.property_id > ?`, which no index can seek, so each page re-reads every property of the layer.
  - `search` pages with `OFFSET`, which re-ranks and skips all earlier matches, and shifts results when items change between pages.
- Breaks: STORE-005, where every read goes to its answer through an index and no read scans.
- Fix:
  - Page properties with a row-value comparison on `current_properties_by_layer`: `(element_id, property_id) > (?, ?)` with the index extended to include `property_id`.
  - For search, keep the FTS rank but use a stable cursor, such as rank plus rowid, or accept OFFSET and say so in STORE-025.

## Low

### L1 One fact defined in several places
- Where:
  - The schema version is in three places: `sqlite.py:15` `SCHEMA_VERSION`, `data/schema.py:10` `SCHEMA_VERSION`, which is unused, and `data/exchange.py:22` `SCHEMA`.
  - The OS check is written three times: `cli.py:490`, `docs.py:160` and `modules/mcp/server.py:27`, and the last re-derives the OS name instead of calling `module_metadata.current_os`.
  - `ALWAYS` is defined in both `cli.py:460` and `docs.py:40`.
  - The roles and the address pattern are in `data/store.py:30-31`, `data/ids.py:13` and `modules/intake/schema.py:14-16`.
- Fix: one definition each, imported where used.

### L2 `set` with several settings applies them one at a time
- Where: `cli.py:259-266` and `modules/mcp/server.py:86-102`.
- What: when the second value is invalid, the first is already stored and the error hides that.
- Fix: parse and check all values first, then store them in one `home.base(write=True)` transaction.

### L3 A race when a base database or store is first created
- Where: `sqlite.py:34-39`.
- What: the version is read, then the tables are counted, outside any transaction. Another process that commits the schema between those two reads makes this one refuse the file as "written by an earlier Metaform".
- Fix: read the version and the table count inside `BEGIN IMMEDIATE`.

### L4 The example module teaches a blind except
- Where: `modules/helloworld/__init__.py:33-37`, and `loader.py:92-94`, which puts "Next: ..." text inside a ValueError message.
- What: `_names` turns every store error, a locked database included, into "no names". Authors copy helloworld, BASE-019.
- Fix: check `store.layers(...)` for the layer and let real errors raise. Carry the next step in a `Stop`, not in message text.

### L5 An edit can move an element onto a subtype's address
- Where: `data/store.py:689-692`.
- What: `address` edits check the format but not `_is_subtype`, so the address ends up held by both an element and a subtype.
- Breaks: MAP-016 and D4.
- Fix: apply the same check `add_element` makes at line 399.

### L6 Build details
- Where: `build.py:89-92` and `:146-155`.
- What: the uv failure message prints a Python list. Subprocesses have no timeout. Module `tests/` folders are carried into built wheels.
- Fix: join the stderr tail, add timeouts, and skip `tests/` in `_walk` for modules.

### L7 The MCP `set` tool takes no `project`
- Where: `modules/mcp/server.py:76-79`.
- Breaks: MCP-025, where every tool accepts an optional `project`.
- Fix: add it, or record in MCP-025 that `set` is exempt because it stores folder settings.

---

## What holds up

These parts were checked and are sound: the one-connection-per-operation session with explicit `BEGIN IMMEDIATE` and rollback on `BaseException`; `atomic()` joining through a `ContextVar`; the selection resolver's trunk-to-leaf rule; literal-only module metadata read with `ast`; the CLI's Error and Next contract for `Stop`; and the correction stack's recompute-from-rows design.
