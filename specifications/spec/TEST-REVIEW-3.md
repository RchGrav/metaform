# Test review 3

Scope: every test added or changed since the second round, found with
`git -C /home/rich/metaform diff --stat 23df23b~3..HEAD -- tests conftest.py src/metaform/modules/*/tests`:
`conftest.py`, `src/metaform/modules/mcp/tests/test_mcp.py`, `tests/test_base.py`, `tests/test_build.py`,
`tests/test_cli.py`, `tests/test_first_working_test.py`, `tests/test_lifecycle.py`, `tests/test_reports.py`.
Judged against the spec records in `specifications/spec/00-index.md` through `09-viewer.md`. No implementation
file was read. Each test is judged against the requirement it names.

Most of this changeset is small: encoding fixes (`encoding='utf-8'` added to `subprocess.run` calls in
`conftest.py`, `test_base.py`, `test_build.py`, `test_first_working_test.py`) that carry no assertion changes
and raise no test-design question, a new UTF-8-on-a-constrained-pipe test, two MCP schema-description tests,
a rewrite of the import-ownership test pair, a marker fix, a tightened help-layout test, and a new
concurrency test for report writes. Two findings below; both are modest.

## Findings

### 1. tests/test_reports.py:120, `test_writes_to_one_file_at_the_same_time_all_survive`

Marked STORE-006 and BASE-045.

```
reports.write(None, 'run-1', 'feedback', text)
...
content = (reports.folder(None) / 'run-1-feedback.md').read_text(encoding='utf-8')
```

What it fails to protect, as marked: STORE-006 is "every write operation is one transaction, and many
processes can write to the same store at once without losing or corrupting data," and its Build section
names the SQLite pragmas and transaction boundaries of a project's store. This test passes `None` for the
project, which is exactly the case STORE-043 describes as having no store at all: "Feedback with no project
is listed from the home's `reports/` folder by reading its file names, since there is no store." A test that
deliberately picks the one case the spec says has no store cannot be protecting a requirement about
transactional writes to a store. What it does protect, correctly and well, is BASE-045's own sentence, "A
second write for the same run id and kind appends a new section... so nothing is overwritten": it widens the
check-then-write race with a monkeypatched `Path.exists` and eight threads released by a `Barrier`, and
would fail if concurrent writers lost each other's sections. That part is a real, well-built test.

I ran it: it passes.

Fix: drop the `STORE-006` marker, or move the same technique to a call that does go through a project's
store (`reports.write` with a real project) so the marker names what is actually exercised.

### 2. tests/test_cli.py:575, `test_a_module_page_leaves_out_an_empty_section_and_keeps_its_rows_narrow`

```
assert roots.index("The map's entry") <= 2 + 40 + 2
```

This is now derived from CLI-029's own text, "the left column is padded to its widest entry of at most 40
characters, plus two spaces," so it is no longer the ungrounded number round 2 flagged. But it does not bind
that requirement: the widest verb signature in the `map` module that stays on one line is
`findings [flag] [layer] [limit] [after]`, 39 characters, one short of the 40-character cap. Padding pads to
the widest actual entry, not to the cap, so this assertion (39 + 2 + 2 = 43, checked against 44) would pass
unchanged if the cap were raised to 45 or removed outright; it cannot catch a build that gets the "at most
40" number wrong. The two new checks alongside it are sound and do bind real behavior: `knowledge`, whose
signature is well over 40 characters, is confirmed to wrap to its own line, and its help text on the next
line is confirmed to land at the same column as `roots`'s, which does test cross-row alignment.

Fix: this is a minor completeness gap, not a wrong test. If the exact cap value is meant to be enforced,
assert it against a verb whose one-line signature is between 40 and roughly 45 characters (or against a
fixture module built for the purpose), so a wrong cap actually moves the column. Not worth doing only for
this; the wrap-and-align checks already carry the real weight of CLI-029 here.

## Design rule check: no refusal for content

Checked every changed test again for a hard refusal where BASE-044/STORE-026 call for a notice. The
rewritten `tests/test_lifecycle.py` pair (import meeting a metaform another project owns; import into
another registered project) both now follow the rule precisely: the first checks a written-nothing,
notice-carrying report instead of a raised `StoreError`, and the second is a new test for the success path
the rule implies. No further violation found in this round's changes.

## Resolution of round 2's nine findings

1. **test_build.py:66, wheel excludes `tests/`.** Resolved by spec: BASE-041's Build now reads "each enabled
   module... copied to `metaform/modules/<id>/`... without its `tests/` folder, which a running wheel never
   uses." The test is unchanged and now matches a stated record.
2. **test_install.py:171, malformed config names its backup.** Resolved by spec: MCP-015's Build now reads
   "a JSON config that is not an object holding an `mcpServers` object... is left unchanged and the install
   stops, naming the file and its backup." The test itself was not touched in this round (it is outside the
   round's diff, since it already asserted this), and now matches a stated record.
3. **test_install.py:183, tool command timeout.** Substantially resolved by spec: MCP-015's Build now reads
   "Each tool's own command, such as `claude mcp add`, has two minutes to finish; one that does not stops
   the install, naming the tool." That grounds the existence of a registration-command timeout, its value,
   and that the failure names the tool, none of which existed in round 2. One small gap remains: the record
   does not give the literal message text, and the test still checks for the substring "did not finish" and
   still reaches the timeout through the internal name `install.TOOL_TIMEOUT`. Given the record now states
   the mechanism and value, this is a minor wording gap, not a fresh finding.
4. **test_lifecycle.py:147, dependency check.** Resolved by spec: BASE-015's Build now reads "Each
   `DEPENDENCIES` requirement is checked against the installed distributions, by name and version, still
   without importing the module; a module whose requirement is not installed is not imported, and its
   reason names the requirement," and BASE-037 cross-references it. The test is unchanged and now matches a
   stated record.
5. **test_lifecycle.py:63, failing stop reported.** Resolved by spec: BASE-018's Build now reads "A `stop`
   that raises is reported as the module's problem in `list modules`, and its withdrawal completes all the
   same." The test is unchanged and now matches a stated record.
6. **test_lifecycle.py:215, import into another project's metaform.** Resolved by test: renamed to
   `test_an_import_meeting_a_metaform_another_project_owns_writes_nothing_of_it_and_names_the_owner`, marked
   STORE-027, STORE-026, BASE-044; it now checks a written-nothing, notice-carrying report instead of a
   raised `StoreError`, matching STORE-027's now-explicit sentence, "when another project owns it, nothing
   of it is written and a notice names that project, BASE-044." A new test,
   `test_a_document_imports_into_another_registered_project_which_keeps_its_own_path`, was added for the
   success path STORE-027 describes and round 2 found untested, and it is sound: it imports a document whose
   embedded project is not registered in the target home under a different, already-registered project id,
   and checks the metaform lands there while the target project's own path and target are kept.
7. **test_lifecycle.py:256, marker names STORE-027 but protects STORE-031.** Resolved: the marker is now
   `@pytest.mark.req('STORE-031')`.
8. **test_cli.py:628, folder-targeted `set` wording.** Resolved by spec: CLI-022's Build now gives the exact
   line, "`Success: updated 1 key for <folder>`, or `Success: no changes for <folder>`." The test is
   unchanged and now matches a stated record.
9. **test_cli.py:575, 80-column check.** Resolved, with the residual gap in finding 2 above: the number is
   now derived from CLI-029's stated column rule (40 characters plus two spaces) instead of being invented,
   and two further checks were added that do bind real behavior, the wrap-to-own-line rule for an
   over-length verb and the alignment of its continuation line with a normal row.

All nine of round 2's findings are resolved or substantially resolved; none was left as a bare test change
with no grounding record.

## Changed tests found sound

`conftest.py`, `tests/test_base.py`, `tests/test_build.py` and `tests/test_first_working_test.py`: the
`encoding='utf-8'` additions carry no assertion change and raise no design question.

`tests/test_cli.py`'s new `test_output_is_utf8_whatever_the_encoding_the_system_gives_a_pipe` is sound: it
sets `PYTHONIOENCODING=cp1252`, a real Windows pipe default with no arrow character, and checks the exact
CLI-022/CLI-031 output line, `  tmux: false → true`, survives it. This is QUAL-002's cross-platform
requirement applied to a real, previously-broken case, checked by behavior.

`src/metaform/modules/mcp/tests/test_mcp.py`'s two changes are sound. The first adds checks that
`map_joins`'s `element` and `raw` properties, `memory_add-observations`'s `text` property, and
`map_knowledge`'s `op` property each carry a `description`, with `raw`'s checked word-for-word against what
`metaform help map joins` prints and `op`'s checked to name `add-item`; this is MCP-003's own new sentence,
"each noun and switch property carries the noun's or the setting's help as its `description`... such as the
values `map_knowledge`'s `op` takes," verified almost literally. The second checks a boolean switch's schema
carries the exact help text declared on the same fixture module in the same test, `'Use tmux.'`; the
expected text is not invented, it is the string the test itself declares.

`tests/test_lifecycle.py`'s two changed/added import tests: sound, as detailed in finding 6's resolution
above.
