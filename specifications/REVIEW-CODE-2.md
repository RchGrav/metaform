# Code review, second round

Branch `chassis`, reviewed 2026-09-25. Scope: all of `src/metaform`, with `src/metaform/data/` and `src/metaform/modules/`. The bar is `rich/code_quality_standards.md`. The contract is `specifications/00-index.md` through sections 01 to 09.

This round starts from `specifications/REVIEW-CODE.md`, the first round's findings. It checks what `specifications/BUILD-LOG.md` steps 10 to 18 say was done about each one against the code as it stands now, then looks for what is new. Findings marked "run" were reproduced. The rest are read from the code.

Sections 08 and 09 of the spec, projects history and the viewer, are not built yet. Nothing in `src/metaform` implements origins, variants or the viewer, and the build order in `00-index.md` puts the viewer after the fix pass. That is not a defect; it is simply not there to review.

## Count

New findings from this round only. The status of every first-round finding is in the next section, not counted again here.

| Severity | Count |
|---|---|
| Critical | 0 |
| High | 1 |
| Medium | 0 |
| Low | 1 |

## Tool results

- `.venv/bin/pyright` from the repo root, strict mode over `src/metaform` with tests excluded, per `pyproject.toml`'s `[tool.pyright]`: 0 errors, 0 warnings, 0 informations.
- `.venv/bin/ruff check src tests conftest.py`, ruff 0.16.9, the rule set left at ruff's defaults since QUAL-005's rule set is still open, Q47: 99 errors. By rule: I001 28, PLW1510 14, FURB167 11, ISC004 9, UP017 8, RUF059 8, BLE001 8, SIM118 3, SIM117 3, TRY004 2, SIM102 2, UP035 1, RUF022 1, S112 1. `ruff check src` alone, the first round's scope: 46 errors. `.github/workflows/checks.yml` runs this exact command with no `continue-on-error`, so the lint step of CI fails today. This is the documented open state of Q47, not a new finding.
- `.venv/bin/python -m pytest -q -p no:cacheprovider`: 414 passed, 0 failed, in 247.17s, about 4 minutes 7 seconds.

## First-round findings

### C1 `intake_submit` over MCP reads a server-side file, or the server's own stdin
Fixed. `src/metaform/modules/intake/__init__.py:94-112`, `_elements`: a string `elements` is read as a path or standard input only when `ctx.surface == 'cli'`. Over MCP a string `elements` returns a notice, `'elements is text; over MCP it is the array of elements itself.'`, and nothing is read. The MCP path never touches `sys.stdin` or the filesystem for this noun.

### H1 MCP tool arguments are never validated or converted
Fixed. `src/metaform/modules/mcp/server.py:170-189`, `_prepare`, calls `tool_arguments` at `src/metaform/module.py:236-243`, which calls `grammar.from_json` at `src/metaform/grammar.py:212-237`. That function raises on a missing required noun and on a noun whose JSON type does not match its kind, and routes every switch through `switch_value`, which runs `settings.parse`. The `set` tool, `src/metaform/modules/mcp/server.py:127-153`, runs every value through `settings.checked` before storing any. Each error carries the same message and Next line the CLI gives for the same problem.

### H2 A second intake is accepted into a metaform that already has one
Fixed. `src/metaform/modules/intake/__init__.py:123-134`, `_target`: when the active metaform already has an intake, a new metaform `intake-<UTC timestamp>` is created and the submission is written there; the earlier metaform is kept whole and stays selectable. `submit`, lines 168-173, adds a notice naming both metaforms and the way back.

### H3 Hidden and masked layers reach agents through search, links and the memory module
Fixed. `src/metaform/data/reads.py`: `search`, lines 357-391, and `links_to`, lines 260-286, filter every result through `res.reaches` unless `raw=True`; a named `layer` narrows the read and never bypasses selection. `layer_items`, lines 106-164, takes an optional resolver and filters through the same `res.reaches` test when one is given. `src/metaform/modules/memory/__init__.py`: `read_graph`, `search_nodes` and `open_nodes` call `layer_items` with `in_context=True` or the store's `search`/`links_to` with their default `raw=False`, so masked and hidden memory no longer reaches these paths.

### H4 CLI async verbs that spawn tasks break shutdown
Fixed. `src/metaform/cli.py:593-622`, `_run_async`: after the verb's own task finishes, the module's tasks on that same loop are found through `loader.tasks_of` and passed to `loader.finish_tasks`, which cancels and awaits them; then `loop.shutdown_asyncgens()` runs before `loop.close()`. Shutdown afterward finds no running tasks on that loop.

### H5 Unload and shutdown do not follow the stated order, and failures vanish
Fixed. `src/metaform/loader.py:211-268`: `finish_tasks` cancels pending tasks and, for each task's own loop, awaits them there when that loop is neither closed nor already running; `_unload` calls `finish_tasks` before `_withdraw`, and `_withdraw`, lines 229-238, calls `stop` in `try/finally` with the settings and `sys.modules` withdrawal always running in `finally`, and a raised `stop` is recorded as `item.problem`. `unload_async`, lines 249-268, awaits the tasks and, for a coroutine `stop`, awaits it with the same `try/finally` shape.

### H6 Reload leaves stale code, and entry-point modules lose their settings
Fixed. `src/metaform/loader.py:111-114`, `_forget`: drops the module's package and every `sys.modules` key that starts with `<import_name>.`, called from both `_withdraw` and `unload_async`. A reload now re-imports every submodule, so a submodule's `settings.*` declarations run again.

### H7 Import is not one transaction and can leave an orphaned store
Fixed. `src/metaform/data/exchange.py:310-360`, `import_document`: the whole document is validated first, then `_plan`, lines 281-307, decides each metaform's project and checks ownership by `home.metaform_owner` before anything is written. Each store opens `BEGIN IMMEDIATE` and stays open; the base database's rows are written and, only after that, every store commits. On any failure every open store is rolled back, closed, and any store file this run created is removed by `home.remove_store`. `src/metaform/home.py:201-210`, `register_in`, now looks up the target path by `path_key` and raises a named `StoreError` on a conflict instead of the earlier `INSERT OR IGNORE`.

### H8 Import documents are not validated, and their keys become SQL identifiers
Fixed. `src/metaform/data/exchange.py:211-268`, `_validate`, checks the whole document against a fixed shape before any write, collecting every problem with its path. `columns`, lines 177-186, reads each table's real column list from the schema itself with `PRAGMA table_info`, and `_insert`, lines 485-490, builds its SQL only from that fixed list, never from a document's own keys. A malformed document is refused whole, with every problem named, before any row is written.

### H9 The published package cannot start the MCP server
Partly fixed, the rest open by the owner's decision, Q38. `src/metaform/loader.py:120-132` and `:164-167`, `missing_dependencies` and `discover`, now check each module's `DEPENDENCIES` before import and record a missing one as the module's load problem, so `list modules` and `mcp serve` report what is missing instead of raising a raw `ImportError`. `src/metaform/modules/mcp/__init__.py:15` declares `DEPENDENCIES = ('mcp>=2.2',)`. `pyproject.toml:10-16` still lists only `prompt_toolkit` in `[project].dependencies`, with `mcp` staying in the `dev` extra, so a wheel built straight from `pyproject.toml` by hatchling still cannot serve MCP; `metaform build`'s own wheel does carry `mcp` in its `Requires-Dist`, per BUILD-LOG step 11. This split is the documented state of Q38, not left silently.

### H10 The installer proof leaks the child process when the server does not answer
Fixed. `src/metaform/probe.py:127-145`, `probe`: the `Session` is created inside `probe`'s own `try`, and `session.close()` runs in a `finally` that always executes. `open_session`, lines 116-124, closes the session before re-raising on any failure during `initialize`.

### H11 QUAL-003, QUAL-004 and QUAL-005 are not in place
Fixed for QUAL-003 and QUAL-004; QUAL-005 confirmed in part, the rule set and suppression format left open by the owner, Q47, not relitigated here. `.github/workflows/checks.yml` runs pyright, ruff and pytest on ubuntu-latest, macos-latest and windows-latest with Python 3.11 and 3.14, each check reporting independently of the one before it; `modules/template/` carries its own copy. `pyproject.toml` has `[tool.pyright]` with `typeCheckingMode = "strict"` over `src/metaform`; strict pyright now gives 0 errors, confirmed by this round's run, against 750 in the first round. `[tool.ruff]` exists with a line length and target version but no chosen rule set; ruff's defaults still fail, 99 problems over `src tests conftest.py`, and the lint job has no `continue-on-error`, so CI's lint step fails today, exactly the state Q47 records. Of the five `# type: ignore` comments the first round found with no reason, three are gone or now sit next to comments that explain them; two remain with no stated reason, `src/metaform/data/records.py:45` and `src/metaform/install.py:279`. See L8 below.

### M1 `module.call` inside a running loop blocks that loop
Fixed. `src/metaform/events.py:46-70`, `publish_async`, awaits an async subscriber on the running loop and runs a sync one through `asyncio.to_thread`; `publish`, lines 19-27, raises `RuntimeError` naming `publish_async` when called inside a running loop, instead of silently blocking it. `src/metaform/module.py:184-200`, `call`, raises the same way when asked to run a coroutine inside a running loop.

### M2 Every settings-screen refresh stops and restarts every module
Fixed. `src/metaform/tui.py:69-70`, `_Backend.rows`, reads the cached `loader.discover()` and does not call `loader.reset()`; the comment there states only `enable` and `disable` reset it, which is what `loader.set_enabled` does.

### M3 Ill-typed field values escape as raw errors
Fixed. `src/metaform/data/writes.py`: `add_element`, `add_join` and `add_subtype` check each field's shape with helpers such as `rows.text`, `rows.whole_number` and `rows.address_form`, and a field that does not fit is stored as given with a `Notice`, never left to raise a raw `sqlite3` exception.

### M4 Elements from knowledge layers take any role string
Fixed. `src/metaform/data/writes.py:64-68`, `add_element`: a role is only accepted for a layer whose kind is in `METAFORM_KINDS`, intake or correction, and there it is checked against `ROLES`; elsewhere it is kept in the descriptor with a notice explaining why. `add_subtype` checks a subtype's role against `SUBTYPE_ROLES` the same way.

### M5 Peel leaves the automatically written relocation removals in the layer
Fixed. `src/metaform/data/corrections.py:16`, the `RELOCATION` marker `'generated: relocation'`, tags the `remove` rows a relocation's `finish` writes automatically; `peel` deletes rows carrying that marker before the layer's content is recomputed, so a later re-finish regenerates them from the layer's current content instead of compounding stale ones.

### M6 The installer is neither idempotent nor safe on partial failure
Fixed. `src/metaform/install.py`: `_record` is called right after each tool's own registration succeeds, not once at the end, so a later tool's failure never hides an earlier success from the next run. `_merge`, lines 160-180, writes the merged config to a temporary file and moves it into place with `os.replace`. Every `subprocess.run` call carries `timeout=TOOL_TIMEOUT`.

### M7 `data/store.py` is one 1482-line class with nine responsibilities
Fixed. `src/metaform/data/store.py` is now 424 lines and is a thin facade: each method opens its transaction and calls one operation of `writes.py` (537 lines), `reads.py` (480), `layering.py` (318), `corrections.py` (296), `challenges.py` (103) or `views.py` (227), each taking the open `Tx`.

### M8 Hidden coupling through import-time registries, frame inspection and lazy-import cycles
Partly fixed, the rest left open by the owner's decision, step 17. `src/metaform/settings.py`: `scope_of` and `own_scope_of` are now public, replacing the private `_scope`/`_own_scope` the CLI used before. `src/metaform/data/session.py:36`, `open_store`, is now public, and `data/exchange.py` uses it instead of a private import. `_declaring_module`, `settings.py:97`, still walks `inspect.currentframe()` to guess a setting's owner outside `owned_by`; BUILD-LOG step 17 records this as deliberate, because pytest imports a module's package outside the loader when it collects that module's tests. Moving `Context` construction and the registries into one module, to close the import cycle itself, was not done.

### M9 `tui.py` is untyped, carries legacy names and swallows errors
Fixed. `tui.py` is part of the 0-error strict pyright run. Its rows and backend state are typed dataclasses; the unused `module` and `declarations` parameters the first round found are gone; a refresh failure now appends to the status line instead of being caught and dropped.

### M10 The module contract is typed as `Any` where it crosses the boundary
Fixed. `src/metaform/module.py:30-40` declares `NounKind`, `Surface`, `VerbFunction`, `Handler`, `Hook` and `StatusHook` as typed `Literal` and `Callable` aliases. `src/metaform/data/records.py:15-18` declares `NodeKind`, `LayerKind`, `Op` and `Answer` as `Literal` types, exported from `metaform.data`.

### M11 Two reads page by scanning
Fixed. `src/metaform/data/reads.py`: `layer_items`, lines 152-157, pages the property phase with a row-value comparison, `(c.element_id, c.property_id) > (?, ?)`, on the extended `current_properties_by_layer` index. `search`, lines 371-391, resumes with a stable cursor of the FTS rank and rowid instead of `OFFSET`.

### L1 One fact defined in several places
Fixed. `SCHEMA_VERSION` is defined once, `src/metaform/sqlite.py:15`, and `data/exchange.py` imports it; the unused `data/schema.py` copy the first round found is gone. `ALWAYS` and the OS check are consolidated per BUILD-LOG step 14; confirmed for `SCHEMA_VERSION` directly in this round.

### L2 `set` with several settings applies them one at a time
Fixed. `src/metaform/cli.py:326-331`, `set_`: every given value is checked with `settings.checked` in one loop before the write loop at lines 336-344 stores any of them, so an invalid second value leaves the first unwritten too.

### L3 A race when a base database or store is first created
Fixed. `src/metaform/sqlite.py:34-45`, `prepare`: the table count and the version are both read inside one `BEGIN`/`COMMIT`, so a file another connection commits between the two reads is seen whole and never mistaken for an earlier Metaform's.

### L4 The example module teaches a blind except
Fixed. `src/metaform/modules/helloworld/__init__.py:33-38`, `_names`: checks `store.layers(...)` for the greeting layer by name instead of catching every store error.

### L5 An edit can move an element onto a subtype's address
Fixed. `src/metaform/data/writes.py:392-398`, inside `changed_columns`: an `address` edit checks `rows.subtype_holding` the same way `add_element` does, and stores the edit as given with a notice when the address is already a subtype's.

### L6 Build details
Fixed. `src/metaform/build.py:94-98` joins the stderr tail for a failed uv step instead of printing a Python list; line 94 gives every uv subprocess a timeout; line 163 excludes a module's `tests/` folder from the built wheel.

### L7 The MCP `set` tool takes no `project`
Open by the owner's decision, Q45, not relitigated. Confirmed unchanged: `src/metaform/modules/mcp/server.py:81-84`, `set_schema`, builds its properties from `settings.SCHEMA` plus `glue` and does not add `project`.

## New findings

### N1 Two concurrent report or feedback writes to the same run and kind silently destroy one of them
- Severity: High.
- Where: `src/metaform/reports.py:40-53`, `write`.
- What is wrong: `write` decides whether to append or to create by checking `target.exists()`, then acts on that answer a moment later. Two processes writing to the same file, the case BASE-045 names directly, a second submission for the same run id and kind, race on that check: both can see the file missing, and both then call `target.write_text(...)`, so the second call's `write_text` fully replaces the file the first call just created. The first submission's text is gone, with no error and no notice, and `store.save_report` then records only the size of whichever write landed last. This is not a rare interleaving: `STORE-006` says many processes write to the same project store at once by design, one MCP server process per agent, and `BASE-045` describes exactly this path, feedback or a report tied to the same intake layer's id from more than one call.
- Run: reproduced. Two threads called `metaform.reports.write(None, 'racerun', 'feedback', text)` with different text, with `pathlib.Path.exists` patched to sleep 0.2s on the feedback path so both see the file missing before either writes. Steps:
  ```
  METAFORM_HOME=/tmp/mf-review-2/racehome
  python /tmp/mf-review-2/race_test.py
  ```
  Result: `~/racehome/reports/racerun-feedback.md` held only `TEXT FROM THREAD 2`; thread 1's text was not in the file at all, and no error was raised by either call.
- Breaks: `BASE-045`, whose own acceptance line states "A second write for the same run id and kind appends a new section... so nothing is overwritten." It also works against the design's central rule that nothing an agent submits is ever lost: an agent's feedback or report can vanish with no notice telling anyone it happened.
- Why it matters: feedback and reports are the channel agents use to say what went wrong, including a trouble report they were told to send when they cannot continue, `intake/__init__.py`'s `ALWAYS` text. Losing one silently defeats the reason the feature exists, and nobody, not the agent, not the person reading `list_reports` later, learns that anything was lost.
- Fix: remove the check-then-act. Open the file unconditionally for append, `os.open(path, os.O_CREAT | os.O_APPEND | os.O_WRONLY)`, which is atomic against other appenders on the same filesystem for a single write; decide whether to write the section header from something read under the same lock as the write, such as the file's size right after opening, or serialize the whole read-decide-write with a lock file or with the project's own `BEGIN IMMEDIATE` write transaction, which the `reports` table write already needs.

### L8 Two `# type: ignore` suppressions carry no stated reason
- Severity: Low.
- Where: `src/metaform/data/records.py:45`, `Record.to_dict`, `# type: ignore[arg-type]`; `src/metaform/install.py:279`, `# type: ignore[misc]`.
- What is wrong: neither comment says why the suppression is needed. The first round's H11 found five such comments and named this as one of the standard's own items, an exception to a rule stating why next to the code it excuses; three of the five are gone or now sit next to an explaining comment, but these two were not given one.
- Breaks: the code quality standard's item on explicit, inspectable code; QUAL-005's rule that an exception to a check carries a reason, which the ruff `# noqa` comments elsewhere in the repo already follow, for example `tui.py:319`, `# noqa: BLE001  a group that cannot be described shows its error`.
- Why it matters: a suppression with no reason is a place a future strict-mode error could come back unnoticed, and a reader cannot tell whether it is still needed without re-deriving the type error pyright would otherwise report.
- Fix: add a short reason after each, in the same style as the repo's own `# noqa` comments, for example `# type: ignore[arg-type]  dataclasses.fields wants a dataclass type, not Self`.

## What holds up

Everything the first round checked and passed still holds under this round's reading: the one-connection-per-operation session with explicit `BEGIN IMMEDIATE` and rollback, `atomic()` joining through a `ContextVar`, the selection resolver's trunk-to-leaf rule, `data/selection.py`, which matches `(incoming & mask) | select` exactly and lets correction layers through unconditionally, literal-only module metadata read with `ast`, the CLI's Error and Next contract for `Stop`, and the correction stack's recompute-from-rows design. The data access object's split into `writes`, `reads`, `layering`, `challenges` and `views` is a clean design: each file has one job, and `Store` stays the one door STORE-023 requires.
