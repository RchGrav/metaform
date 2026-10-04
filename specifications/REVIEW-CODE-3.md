# Code review, third round

Branch `chassis`, reviewed 2026-09-25, at commit `0f2157b`. Scope: all of `src/metaform`, with `src/metaform/data/` and `src/metaform/modules/`. The bar is `rich/code_quality_standards.md`. The contract is `specifications/00-index.md` through sections 01 to 09.

This round starts from `specifications/REVIEW-CODE-2.md`, the second round's findings, and `specifications/BUILD-LOG.md` from "Windows, from the first CI run" to the end, step 19. It checks the two findings the second round left, N1 and L8, against the code as it stands now, reads the full diff since the second round commit, `git diff 23df23b~3..HEAD -- src`, and then makes a full pass over the rest of `src/metaform`.

Sections 08 and 09 of the spec, projects history and the viewer, are still not built. Nothing in `src/metaform` implements origins, variants, reconstruction or the viewer. That is not a defect; it is not there to review.

## Count

New findings from this round only.

| Severity | Count |
|---|---|
| Critical | 0 |
| High | 0 |
| Medium | 0 |
| Low | 0 |

## Tool results

- `.venv/bin/pyright` from the repo root, strict mode over `src/metaform`, tests excluded, per `pyproject.toml`'s `[tool.pyright]`: 0 errors, 0 warnings, 0 informations.
- `.venv/bin/ruff check src tests conftest.py`, ruff 0.16.9, ruff's default rules since QUAL-005's rule set is still open, Q47: 100 errors. By rule: I001 29, PLW1510 14, FURB167 11, ISC004 9, UP017 8, RUF059 8, BLE001 8, SIM118 3, SIM117 3, TRY004 2, SIM102 2, UP035 1, S112 1, RUF022 1. This is one more than the second round's 99, all in I001, unsorted imports: `cli.py` gained `import codecs` and `import io` for the UTF-8 fix, and the repository's own import style, one name per line, is not what ruff's default `isort` rule wants. `.github/workflows/checks.yml` runs this exact command with no `continue-on-error`, so the lint step of CI fails today, the documented open state of Q47, not a new finding.
- `.venv/bin/python -m pytest -q -p no:cacheprovider`: 417 passed, 0 failed, in 309.62s, about 5 minutes 10 seconds. Three more tests than the second round's 414, from step 19's fixes.

Note, not part of this review: the working tree carries uncommitted changes to `tests/test_cli.py` and `tests/test_reports.py`, a new test and a marker removal, that predate this session. They are test-only, already present before this review started, and are left untouched, per the instruction to change no file but this one.

## Status of the second round's open findings

### N1 Two concurrent report or feedback writes to the same run and kind silently destroy one of them
Fixed. `src/metaform/reports.py:46-52`, `write`: the file is opened with `'x'`, exclusive create, inside a `try`, and only a `FileExistsError` falls back to append with a new dated section. Create and append are now one step each, with no check-then-act gap between them.
- Run: reproduced the second round's exact race, updated for the fix. Two threads called `metaform.reports.write(None, 'racerun', 'feedback', text)` with different text, with `pathlib.Path.exists` patched to sleep 0.2s on the feedback path so both would have seen the file missing under the old code. Steps:
  ```
  METAFORM_HOME=/tmp/mf-review-3/racehome
  python /tmp/mf-review-3/race_test.py
  ```
  Result: `~/racehome/reports/racerun-feedback.md` held `TEXT FROM THREAD 1`, then a dated section with `TEXT FROM THREAD 2`. Both threads' text survived, where the same test against the second round's code lost one whole write with no error. `tests/test_reports.py::test_writes_to_one_file_at_the_same_time_all_survive` covers the same case and is in the passing suite above.

### L8 Two `# type: ignore` suppressions carry no stated reason
Fixed. Both comments now carry a reason on the line above:
- `src/metaform/data/records.py:45`: "Every Record subclass is a dataclass; the base class itself is not, so the checker cannot know that."
- `src/metaform/install.py:279`: "A tool that does not merge a config always has an add command; the catalogue guarantees it."

## What changed since the second round, read in full

`git diff 23df23b~3..HEAD -- src` touches eight files, two commits: the Windows fixes, `cli.py` and `probe.py`, and step 19's fixes for N1, L8, STORE-027's owner conflict, and MCP-003, in `reports.py`, `data/exchange.py`, `modules/mcp/server.py`, `data/records.py` and `install.py`. Each is read below; none introduces a new defect.

- `cli.py`, `_utf8_streams`: reconfigures `sys.stdin`, `stdout` and `stderr` to UTF-8 when each is a real `io.TextIOWrapper` and not already UTF-8, called once at the top of `main`. It skips anything that is not a `TextIOWrapper`, such as a captured stream under a test harness, so it changes nothing there. Matches QUAL-002 and the added test `test_output_is_utf8_whatever_the_encoding_the_system_gives_a_pipe`.
- `probe.py`, `Session.__init__`: resolves the command's first word through `shutil.which` before `Popen`, so a `.cmd` launcher on Windows starts the same way registration already starts it. `probe`'s own `except` and `finally` still both call `session.close()`; `close()` guards on `self.process.poll() is None`, so the second call is a no-op past the first.
- `data/exchange.py`, `_plan` and `import_document`: an owner conflict on import no longer raises. It appends a notice under `metaforms.<id>` naming the owning project and the way to reach it, counts it in `metaforms_skipped`, and continues planning the rest of the document. Traced the whole call path: `_import_rows` only ever runs for `Planned` entries, so a skipped metaform's rows are never touched; the notice format matches the rest of the file's notices, `{"where": ..., "message": ...}`. Matches STORE-027 and BASE-044 as BUILD-LOG step 19 states them, and the added test `test_an_import_meeting_a_metaform_another_project_owns_writes_nothing_of_it_and_names_the_owner` is in the passing suite.
- `modules/mcp/server.py`, `_described`: adds `noun.help` or `setting.help` as a schema property's `description`, only when the property has none already and the help text is non-empty. Used by `setting_schema` and by every noun property in `verb_schema`, so a module's own switches and every noun get their CLI help text over MCP too, closing the `map_knowledge` `op`-guessing gap MANUAL-TEST-2 found. Checked every call site with `grep`: no caller still expects the old undescribed schema shape.
- `data/records.py`, `install.py`: only the added `# type: ignore` reasons, L8 above.

## Full pass over the rest

Read in full: `data/writes.py`, `data/corrections.py`, `data/session.py`, `home.py`'s `base()` context manager, `modules/intake/__init__.py`, and `cli.py`'s status and report wiring. Grepped the whole tree for bare excepts, mutable default arguments and stray TODO, FIXME and HACK markers: every broad `except` carries a comment or a `noqa` reason already accounted for by the second round's H11 and L8; none is new. No mutable default arguments and no TODO markers exist in `src/metaform`.

Nothing in this pass turned up a Critical, High, Medium or Low finding. The write layer, the correction stack's apply and peel, the session's transaction boundaries and the intake module all still hold to BASE-044 and STORE-026: nothing an agent submits is refused for its content, and the only raises are for a reference that cannot be read at all or a store-protecting failure.

## Open by the owner's decision, not relitigated

Checked and confirmed unchanged, per the brief:
- H9 in part, Q38: `pyproject.toml`'s `[project].dependencies` still lists only `prompt_toolkit`; `mcp` stays in the `mcp` module's own `DEPENDENCIES`, not the chassis's.
- L7, Q45: `set_schema` in `modules/mcp/server.py` still builds its properties from `settings.SCHEMA` and `glue` only; the `set` tool still takes no `project`.
- The ruff rule set and suppression format, Q47: still ruff's defaults, still failing, as the tool results above show; expected.
- M8's registry and import-cycle restructuring: `settings.py:99` still reads a setting's owner outside `owned_by` through `inspect.currentframe`; `Context` construction and the registries are still not moved into one module.
- The web GUI and the history commands of sections 08 and 09: no source for either exists under `src/metaform`; stray `__pycache__` files from an earlier `viewer`/`web` module are build cache, not source, and are not part of this review.

## What holds up

Everything the second round checked still holds: the one-connection-per-operation session with `BEGIN IMMEDIATE` and rollback, the data access object's split into `writes`, `reads`, `layering`, `corrections`, `challenges` and `views`, the CLI's Error and Next contract, and the correction stack's recompute-from-rows design. The two fixes this round added, atomic report writes and the import owner-conflict notice, both hold under direct reproduction and under the full suite.
