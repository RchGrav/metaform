# Module verb and setting changes

A verb or setting change lands as one unit: the module's `__init__.py` declaration, its `README.md`, its `CHANGELOG.md` Unreleased entry, and the spec record it cites, edited in place. Tests go into the module's existing test file, never a new one.

## Verbs and nouns
- Noun order: write required nouns first. The CLI refuses `wait id=X until=done` with "id= comes after the required nouns", so write `until=done id=X` in examples, in any `next` string the verb returns, and in tests.
- Refusing after a reservation: give the reservation back to its prior column before raising, or the autostart loop requeues it forever. Refuse before reserving whenever the refusal can be known up front.
- A verb that needs a new runner op works only in agent sessions started after the change; an older runner answers "No request attach." Such a verb must undo its own side effects before it raises: remove the copied files and the folder it made (`rmdir` the parent when empty), then `ls` the target to confirm nothing is left. Check the refusal in a live session as well as in tests.
- A launch option that a surface passes through (the web page, MCP, the CLI) is checked once, in the verb that acts on it: `dispatch start` checks `prompts=` and `mode=`, and the web server only forwards them. Never copy the check into the surface, or the surfaces drift. The page sends only the values the person changed, so an untouched default never overrides a stored setting. A person-only option is refused for agents inside the verb, so every surface gets the same refusal.

## Settings
- Match the module's existing settings. Dispatch's settings are `person_only=True`, so a new dispatch setting is too.
- Fixed-set settings are choice settings. Declare the choices once: the TUI, the web page, `metaform set` and Tab completion all offer that same pick list. Never a free-text field for a fixed set; the person picks and never types. `choice_help` gives each choice its plain-words text.
- A group of settings for one thing sets `section`, for example `Agent options/Claude Code`. The TUI opens a section as a submenu; the web page shows it under its own heading after the top-level rows.
- List settings cannot be emptied: an empty list is stored as no rows and reads back as the default, so "cleared" never sticks. For a list the person may switch off, give it a sentinel word (`none`) that the check accepts alone and maps to `None` before the role check. Refuse misspelt members in the check, since a misspelt role would hold nothing back while seeming to.
- Renaming or removing a setting: Metaform processes started before the change (the MCP server, live runners, agent sessions) still read the old key until restarted. Name the restart in the report.
- Splitting one list setting into one setting per key: a folder's stored list hides its parent's whole list, but per-key settings inherit one key at a time. The migration must write `default` for each key that only a parent's list set, or the parent's value starts applying in child folders. Test that case: the parent sets a key the child's list does not mention, and the child must read `default`.
- A one-time migration runs at the first process start on the person's real home, so run it against a copy of the stored rows before it ships. If a migration bug has already written live settings, state the rows and the proposed correction, and wait for a yes before writing them.

## Data
- Adding a column to a module table: add a nullable `Column` with no default, bump `version` by one, and leave `compatible_from` where it was. The chassis adds a missing column to an existing store, so no migration is needed. Put a comment on the table saying which version added the column and why older code still reads it.

## Code hygiene
- Module imports: a module imports only the public base `metaform.module`, never `metaform.harness` or `metaform.install`. Expose what you need there as a wrapper (as `child_environment` and `mcp_server` were). A test's PUBLIC set enforces this.
- Child processes: any process Metaform starts gets `child_environment(**own)` rather than a copy of `os.environ`, so an identity inherited from a parent (`METAFORM_ROLE`, `METAFORM_SESSION`, `METAFORM_WORK`, `METAFORM_NODE`) never describes the wrong session. Pass the child's own values through `**own`.
- New helper names: before adding a `def`, grep the file for `^def NAME` and `NAME(`. A second `def` with the same name silently replaces the first, so every earlier caller breaks at runtime. In dispatch, a second `spawn` replaced the resume/intake launcher and the failure surfaced only as "spawn() missing 3 required positional arguments". Pick a distinct name.
- Pyright on `**kwargs` built from a conditional: bind the dict first with an annotation, `given_by: dict[str, Any] = {'by': role} if (role := f()) else {}`, then unpack it. The same family hits `.get()` on a dict read from JSON: annotate the read as `Any`, check it with `isinstance`, then `cast(dict[str, Any], value)`.
- Pyright errors are judged by diff: list the error lines, then intersect them with `git diff -U0 FILES` hunks. Only errors inside a hunk are yours to fix; the rest are reported with line numbers as pre-existing.
- Shared checkout: another agent may edit the same file while you work. Re-read before editing, and when scripting a replacement, assert the target string occurs exactly once.
- Lint: `uv run ruff check CHANGED FILES`. mypy is not installed.

## Tests
- Run `uv run pytest FILE -k NAME -q`. Keep to one happy path and at most two edge cases per feature. Never run the full suite except for final verification.
- Dispatch is disabled in a fresh test home. A test that reads dispatch's tables or settings calls `loader.set_enabled('dispatch', True)` first; without it `Store(..., module='dispatch')` raises `dispatch declares no tables.`
- Concurrency tests: an exception raised inside a `threading.Thread` does not fail pytest. Have the thread catch its exception into a list and assert the list is empty along with the outcome. Then remove the guard (for example the `store.atomic()` block) and confirm the test fails; a test that passes either way proves nothing.
- Guards under test: to show a test depends on a check, break that one comparison, run the filtered test, confirm it fails, then restore from a copy made before the edit. Do not rely on `git diff` to confirm the restore, since a shared checkout holds other tickets' uncommitted work in the same file.
- Authored prompts: a prompt the owner has not written ships as an empty element in the module's `resources/prompts.xml`, and the code treats empty as off. Tests point `METAFORM_PROMPTS` at a stand-in file in the tests folder that carries a placeholder for that element. Never write placeholder wording into the shipped prompts file.
- Prompt comments in `resources/prompts.xml` are product documentation and are never sent. Keep every comment line within 120 columns.
- Docstrings and comments cite the spec record they implement by its ID (for example `BASE-052`) at the end of the sentence, as the surrounding code does.

## Spec drafting
- Specs are written with Rich (see AGENTS.md). Draft the bullet beside its neighbours in the ticket note: what the change means, why, and an Acceptance line naming the new tests. Edit the spec file only when he asks.
