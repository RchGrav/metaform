# Test review 2

Scope: every test added or changed since commit 3e610e7, found with
`git diff --stat 3e610e7..HEAD -- tests conftest.py src/metaform/modules/*/tests`.
Judged against the spec records in `specifications/spec/00-index.md` through `08-projects.md`
(section 09, the viewer, names no requirement any changed test protects, so it was not needed).
No implementation file was read. Each test is judged against the requirement it names.

Most of this changeset is a large, careful realignment from an older refusal-based design to the
current one: no agent submission is ever refused for its content, BASE-044 and STORE-026; what does
not fit is stored with a notice; an operation aimed at something that cannot change writes nothing
and returns a notice. The great majority of the changed tests carry out that realignment correctly
and precisely, checking the exact resulting state after a notice, not just that a notice exists.
That work is sound. The findings below are the exceptions.

## Findings

### 1. tests/test_build.py:66, `test_a_build_carries_only_the_enabled_modules_and_their_dependencies`

Requirement: BASE-022, BASE-041.

```
assert not [name for name in names if name.startswith('metaform/modules/') and '/tests/' in name]
```

What it fails to protect: nothing in BASE-022 or BASE-041 says the build excludes a module's
`tests/` folder. BASE-041's Build text says the wheel carries "each enabled module, from any
place, copied to `metaform/modules/<id>/`," with no exclusion named. BASE-019 describes a shipped
module's folder as including `tests/` as one of its four required parts. Read together, the spec
says to copy the whole module folder, tests included; this assertion enforces the opposite and
cites no record for it. This is an invention: a real one, since shipping test code in a release
wheel is a fair thing to want, but it is not in the record the test names, and it is not
grounded elsewhere in sections 01-09.

Fix: either state the exclusion in BASE-041 (What this means: "each enabled module's code is
copied, excluding its `tests/` folder") and then keep this assertion, or drop the assertion here
and raise the gap as a question for the record instead of encoding it into a test.

### 2. tests/test_install.py:171, `test_a_config_that_is_not_a_json_object_is_refused_naming_it_and_its_backup`

Requirement: MCP-015.

What it fails to protect: MCP-015 covers previewing changes, showing where backups will go, and
writing only after confirmation. It says nothing about a malformed existing config file, whether
the installer backs it up before failing, or that the error names the backup's path. This test
invents that whole failure path: it writes a JSON file with a leading `//` comment, expects
`install cursor` to fail, expects a backup to already exist at that point, and expects the backup's
path to appear in the error text. None of those three claims is stated anywhere in MCP-015.

Fix: if this handling is wanted, add it to MCP-015 as its own sentence (a config that cannot be
parsed as JSON refuses with the config path and its backup path named), then this test protects it.
As written, the test asserts implementation choices no record makes.

### 3. tests/test_install.py:183, `test_a_tool_command_that_hangs_stops_at_its_timeout`

Requirement: MCP-015.

What it fails to protect: MCP-015 has no timeout language at all. The only timeout named anywhere
in section 06 is MCP-017's, and MCP-017 is explicit that its 30-second limit belongs to the proof
step (the JSON-RPC exchange over stdio after registration), not to running a tool's own
registration command (e.g. `claude mcp add ...`). This test patches a chassis constant,
`install.TOOL_TIMEOUT`, that MCP-015 never mentions, to make a registration command time out, and
checks for the message "did not finish." That is a real and reasonable feature to want, but it is
not what MCP-015 states, and the test names the wrong record (or an unwritten one).

Fix: state a registration-command timeout in MCP-015 (or a new record) with its value and its
wording, then this test protects it. As written it enforces a specific mechanism and message that
exist only in the test.

### 4. tests/test_lifecycle.py:147, `test_a_module_whose_dependency_is_not_installed_is_reported_and_not_imported`

Requirement: BASE-015, BASE-037.

What it fails to protect: this test declares `DEPENDENCIES = ('surely-not-an-installed-distribution>=1.0',)`
on a module whose `__init__.py` raises `SystemExit` if it ever runs, and expects the module to be
listed as `error` with the missing distribution's name in the reason, and never imported. Neither
BASE-015 nor BASE-037 describes a dependency-availability check. BASE-015 reads `SUPPORTED_OS`,
`DEPENDENCIES`, `SHIPS_DISABLED` and `REQUIRES_CHASSIS` as literals with `ast`, "never executed,"
but says nothing about verifying that the packages named in `DEPENDENCIES` are installed before
loading, or refusing the module when they are not. BASE-037's five listed refusal reasons
(reserved id, duplicate id, missing `SUPPORTED_OS`, wrong `MODULE.id`, duplicate verb, invalid tool
name, import error) do not include an unmet dependency. This test names a check that section 04
never describes.

Fix: if the chassis is meant to pre-check declared dependencies against the environment before
import, add that as its own requirement (build detail and acceptance) under BASE-015 or BASE-037,
then keep this test. As written, it tests behavior beyond both named records.

### 5. tests/test_lifecycle.py:63, `test_unload_waits_for_tasks_then_stops_and_a_failing_stop_is_reported`

Requirement: BASE-018, QUAL-010.

What it fails to protect, in part: the test's core claim (spawned task finishes before `stop`
runs, `stop` runs once, unload completes and the module is fully withdrawn: settings gone,
`sys.modules` entry gone) is solidly grounded in BASE-018. One extra assertion,
`assert 'RuntimeError: stop failed' in found.problem`, goes further: BASE-018 states that "a
`start` that raises unloads the module and reports the error as its load problem," naming `start`
specifically; it says nothing about what happens to `found.problem` when `stop` raises instead.
This one assertion is a reasonable extrapolation from the pattern, not something the record states.

Fix: either state in BASE-018 that a failing `stop` is also recorded as the module's problem, or
drop that one assertion and keep the rest, which is sound.

### 6. tests/test_lifecycle.py:215, `test_an_import_is_one_unit_and_a_metaform_owned_by_another_project_is_refused_first`

Requirement: STORE-027, STORE-006.

What it fails to protect, and where it goes beyond the record: the test exports project "one",
then calls `import_document(document, 'two')` and expects a `StoreError` naming "one", with nothing
written to the target home. STORE-027 says the opposite is the supported path: "Import with no
project uses the project record in the document; with a project id, it imports into that
registered project," and "Importing into a registered project keeps that project's path and
target." That sentence exists specifically to describe redirecting an exported document at a
different registered project than the one it came from; nothing in STORE-027 refuses that
redirection, and nothing ties a document's own embedded project id to the target project id as a
precondition. This test asserts a refusal for exactly the case the record describes as supported,
which is also in tension with the no-refusal design rule, BASE-044/STORE-026: this is not a call
that "cannot be read at all," and it does not "damage the store itself," the only two grounds
STORE-026 gives for a `StoreError`.

I ran it: it currently passes, so it is protecting a real refusal in the code, and no other test in
this changeset exercises the "import into a different registered project" success path that
STORE-027's own sentence describes.

Fix: read STORE-027 again with Rich to settle whether importing a document into a project other
than the one it names is meant to succeed (as the current text reads) or to be refused (as this
test asserts); the record needs a stated rule either way, and the test should follow it, not
invent it.

### 7. tests/test_lifecycle.py:256, `test_registering_a_project_whose_folder_another_holds_is_refused_by_name`

Marked STORE-027; actually protects STORE-031.

What it fails to protect: the test registers project "proj" on a folder, then registers project
"twin" on the same folder, and expects `StoreError` naming "proj". That is STORE-031's rule
exactly ("A path already registered under another id is refused, naming that id") and has nothing
to do with STORE-027 (export and import). It names a requirement it does not test, and the
requirement it does test, STORE-031, is not named. This is a marker defect, not a logic defect:
the assertion is correct and the behavior is real, but a requirement listing built from these
markers (QUAL-009's orphan check) would show STORE-031 as untested here and STORE-027 as protected
by a test that has nothing to do with it.

Fix: change the marker to `@pytest.mark.req('STORE-031')`.

### 8. tests/test_cli.py:628, `test_set_for_another_folder_names_that_folder`

Requirement: CLI-022, PROJ-007.

```
assert lines(run('set', '--modules', 'chassis', f'folder={job}'))[0] == f'Success: updated 1 key for {job}'
```

What it fails to protect: CLI-022's Build section gives the exact text of `set`'s output for the
ordinary case ("Success: updated `<n>` key" / "keys") but for the folder-targeted case it says
only that the command "stores the same value for that folder and prints the same lines, naming the
folder." It does not give the literal wording "for `<folder>`" appended to the first line; that
phrasing exists only in this test. The behavior being checked (the folder is named somewhere in the
output) is real and grounded; the exact string is not.

Fix: either add the literal first-line wording to CLI-022's Build text (as the record does for
every other exact output string in that section) and keep this assertion, or loosen the assertion
to check that the folder path appears in the output without pinning the exact sentence.

### 9. tests/test_cli.py:575, `test_a_module_page_leaves_out_an_empty_section_and_keeps_its_rows_narrow`

Requirement: CLI-029.

```
roots = next(line for line in run('help', 'map').stdout.splitlines() if line.strip().startswith('roots'))
assert roots.index("The map's entry") < 80
```

The first half of this test (an empty module's help page omits the `Verbs` heading) is squarely
CLI-029's "Empty sections are left out." The second half, the 80-column check on one row of the
`map` module's verb list, has no basis in CLI-029: the record describes the module page's sections
("`Verbs` with one row per verb") but states no column width or alignment rule for that listing
(unlike CLI-006's overview, which does state "Column alignment pads the left column to its widest
entry plus two spaces"). The number 80 is not derived from any record.

Fix: if row width for the module verb list is meant to be bounded, state it in CLI-029 with the
column rule; otherwise drop the second assertion, which checks a formatting property the spec does
not require.

## Design rule check: no refusal for content

I checked every changed test for a refusal that the spec now resolves as a notice, per BASE-044
and STORE-026. Every prior violation I found (STORE-034 corrections, add_join/add_property/add_item
targets, layer creation without a variable or provenance, metaform name collisions, hide/select/mask
on the wrong layer kind, malformed addresses, C-answer without a link, and more) has already been
corrected in this changeset to notice-based assertions that check the resulting stored state, not
just that no exception was raised. That work is thorough and I found no further violations of this
rule beyond finding 6 above, which is the one place a test still expects a hard refusal where the
named record's own words describe the opposite outcome.

## Changed tests found sound

Everything not listed above, including the large rewrites in
`src/metaform/modules/intake/tests/test_intake.py`, `src/metaform/modules/map/tests/test_map.py`,
`src/metaform/modules/mcp/tests/test_mcp.py`, `tests/test_store_operations.py` (the ERRORS to
NOTICES restructuring), `tests/test_store_corrections.py`, `tests/test_store_map.py`,
`tests/test_store_layers.py`, `tests/test_store_reads.py`, `tests/test_store_entry.py`,
`tests/test_store_exchange.py`, `tests/test_store_concurrency.py`, `tests/test_reports.py`,
`tests/test_home.py`, `tests/test_base.py`, `tests/test_tui.py`,
`src/metaform/modules/memory/tests/test_memory.py`, and
`src/metaform/modules/helloworld/tests/test_helloworld.py`, checks against its named requirement's
actual text, would fail on a build that got that requirement wrong, and asserts the specific
resulting state rather than only the presence of a notice or the absence of an error. In several
places (the STORE-034 correction tests, the intake findings and flag tests, the memory
select-and-mask test across every read path, the MCP argument-kind test, the MCP elements-as-string
security test) the tests are unusually thorough: they check exact addresses, exact notice
locations, exact stored values, and, in the security-relevant cases, that nothing leaked through a
side path.
