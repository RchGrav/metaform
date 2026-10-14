---
name: metaform-module-development
description: Use when adding a Metaform module verb or setting.
category: development
---

# Metaform module changes

A verb or setting change lands as one unit: the module's `__init__.py` declaration, its `README.md`, its `CHANGELOG.md` Unreleased entry, and the spec record it cites, edited in place. Tests go into the module's existing test file, never a new one.

- Noun order: write required nouns first. The CLI refuses `wait id=X until=done` with "id= comes after the required nouns", so write `until=done id=X` in examples, in any `next` string the verb returns, and in tests.
- Settings: match the module's existing settings. The dispatch module's settings are `person_only=True`, so a new dispatch setting is too.
- Tests: run `uv run pytest <file> -k <name> -q`. Keep to one happy path and at most two edge cases per feature, and never run the full suite except for final verification.
- Concurrency tests: an exception raised inside a `threading.Thread` does not fail pytest. Have the thread catch its exception into a list and assert the list is empty along with the outcome. Then remove the guard (for example the `store.atomic()` block) and confirm the test fails; a test that passes either way proves nothing.
- Guards under test: to show a test depends on a check, break that one comparison, run the filtered test, confirm it fails, then restore from a copy made before the edit. Do not rely on `git diff` to confirm the restore, since a shared checkout holds other tickets' uncommitted work in the same file.
- Lint: `uv run ruff check <changed files>`. pyright reports errors in older code, so confirm its error lines fall outside your changes. mypy is not installed.
- Shared checkout: another agent may edit the same file while you work. Re-read before editing, and when scripting a replacement, assert the target string occurs exactly once.
- New helper names: before adding a `def` to a module, grep the file for `^def <name>` and for `<name>(`. A second `def` with the same name silently replaces the first, so every earlier caller breaks at runtime; in dispatch, a second `spawn` replaced the resume/intake launcher and the failure surfaced only as "spawn() missing 3 required positional arguments". Pick a distinct name instead.
- Authored prompts: a prompt the owner has not written ships as an empty element in the module's `resources/prompts.xml`, and the code treats empty as off. Tests point `METAFORM_PROMPTS` at a stand-in file in the tests folder that carries a placeholder for that element; never write placeholder wording into the shipped prompts file.
- Spec record: add a bullet beside its neighbours that states what the change means and why, plus an Acceptance line naming the new tests.
- Module imports: a module imports only the public base `metaform.module`, never `metaform.harness` or `metaform.install`. Expose what you need there as a wrapper (as `child_environment` and `mcp_server` were). A test's PUBLIC set enforces this, so a direct import fails the suite.
- Child processes: any process Metaform starts gets `child_environment(**own)` rather than a copy of `os.environ`, so an identity inherited from a parent (`METAFORM_ROLE`, `METAFORM_SESSION`, `METAFORM_WORK`, `METAFORM_NODE`) never describes the wrong session. Pass the child's own values through `**own`.
- Adding a column to a module table: add a nullable `Column` with no default, bump `version` by one, and leave `compatible_from` where it was. The chassis adds a missing column to an existing store, so no migration is needed. Put a comment on the table saying which version added the column and why older code still reads it.
- Refusing after a reservation: if a verb refuses after it has reserved a ticket, give the reservation back to its prior column before raising, or the autostart loop requeues it forever. Refuse before reserving whenever the refusal can be known up front.
- A verb that needs a new runner op works only in agent sessions started after the change; an older runner answers "No request attach." Such a verb must undo its own side effects before it raises: remove the copied files and the folder it made (`rmdir` the parent when empty), then `ls` the target to confirm nothing is left. Check the refusal in a live session as well as in tests.
- List settings cannot be emptied: an empty list is stored as no rows and reads back as the default, so "cleared" never sticks. For a list setting the person may switch off, give it a sentinel word (`none`) that the check accepts alone and maps to `None` before the role check. Refuse misspelt members in the check, since a misspelt role would hold nothing back while seeming to.
- Pyright on `**kwargs` built from a conditional: `**({'by': x} if x else {})` reports unknown argument types. Bind the dict first with an annotation, `given_by: dict[str, Any] = {'by': role} if (role := f()) else {}`, then unpack it. The same family hits `.get()` on a dict read from JSON ("Type of \"get\" is partially unknown"): annotate the read as `Any` first, check it with `isinstance`, then `cast(dict[str, Any], value)`.
- Pyright errors are judged by diff: list the error lines, then intersect them with `git diff -U0 <files>` hunks. Only errors inside a hunk are yours to fix; the rest are reported with their line numbers as pre-existing.
- Prompt comments in `resources/prompts.xml` are product documentation and are never sent. Keep every comment line within 120 columns, the same limit as the Python: rewrap a comment that runs past it instead of leaving the long line.
- Docstrings and comments cite the spec record they implement by its ID (for example `BASE-052`) at the end of the sentence, as the surrounding code does.
