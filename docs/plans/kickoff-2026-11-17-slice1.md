# Kickoff 2026-11-17, first slice: evidence record

Source of the work: `rich/metaform_factory_kickoff_2026-11-17.zip` (the person's kickoff archive). The assignment run is
its `prompts/05_kickoff.txt` (Phase 0 and the first slice of Phase 1 in `DEVELOPMENT_KICKOFF.md`). Run by AtomicRespect
(session `91c96c16-7a53-4c04-a3da-00dee6342154`) on 2026-11-17, at the person's `/goal`: "inside of the rich folder you
will find a kickoff archive, follow its plan through to completion".

## Phase 0: baseline

| What | Observed |
|---|---|
| Audit baseline | `c4c2e03105f84eb82431ece2262b19a71033647e` |
| Branch HEAD before this work | `c4c2e031`, the same commit: no target had changed since the audit |
| Running code | Web GUI: `/home/rich/metaform/.venv/bin/python -m metaform.modules.web.server` on 127.0.0.1:7433; `metaform` imports from `/home/rich/metaform/src`. The project-store service (`~/.metaform/maps/service.json`) runs the same checkout and restarts on a code change. What is live is the branch HEAD. |
| Tests run | Only filtered, as `CLAUDE.md` requires: `pytest tests/test_project_tool.py -k "find_each_definition_by_its_key or defined_overlay or two_definitions or map_of_a_project"`. The full suite was not run. |
| CI | Every recent `checks` run on `feat/project-tool` fails in 3 to 6 s, all six jobs. GitHub's annotation on each job: "The job was not started because recent account payments have failed or your spending limit needs to be increased." This is a GitHub billing condition, not a test failure. No test has run in CI at this baseline. Fixing it is the owner's action. |

## Phase 0: characterization on fixtures

Each case ran in a temporary Metaform home made for it, never in `~/.metaform`. The script was
`/tmp/kickoff-chars/chars.py`.

### F04: overlay keys are not reversibly parsed by the page (repaired here)

On `c4c2e031`, with definitions `mashtrac.overlay.review_findings`, `mashtrac.overlay.design_notes.team` and
`mashtrac.overlay.specifications.project`, `project_map.layers` listed `review_findings` and `team_design_notes` with
**empty descriptions**. `project_specifications` was correct. That is the audit's prediction, now observed.

### F02: position-based mutations can edit the wrong record (observed, not changed)

Records A, B, C at positions 0, 1, 2. One client reads B at position 1. Another deletes position 0, leaving B and C.
The first client's `update` of position 1 answers `ok` and **patches C**, not B. Observed: records `['B', 'C*']`, where
`*` marks the patch meant for B.

### F03: schema evolution does not recheck existing rows (observed, not changed)

The overlay has records B and C, both `kind: beta`, and `extra` set on one of them.

| Change | Answer | Rows afterwards |
|---|---|---|
| a. choices `alpha \| beta` narrowed to `alpha \| gamma` | `ok` | both still `beta`, now outside the definition |
| b. optional `extra` made required | `ok` | B still has no `extra` |
| c. new required field `owner` added | `ok` | neither row has `owner` |
| d. `title` changed from text to address | `ok` | titles `B`, `C` are not addresses |
| An unrelated patch afterwards (`title` of position 0) | `FIELD_MISMATCH` | the old rows now fail the new definition, so the overlay's records are stuck until repaired |

Narrowing to a single value (`alpha`) is refused, because a choice needs two or more values. That is the type rule, not
a compatibility check.

## The first ticket's path (source-store matrix)

| Surface | Reads tickets from |
|---|---|
| Page board and element panel | the project store's `tickets` overlay (commits `591cba79`, `2ac7ec1b`) |
| `project` tool (agents) | the project store |
| `metaform map work` (CLI) | the old per-project SQLite store. On 2026-11-16 its map for `metaform` read empty while the page showed the full map, and a ticket written there (`6303d492...`) does not appear in the project store. |

So the canonical ticket for this slice is a `tickets` record in the project store: **`t-f04-lookup`** at
`metaform.code.graph.knowledge`. It was not written to the old CLI store. The CLI's separate store is the split
old/new-store consumer the audit names for Phase 3.

## Phase 1: the slice

- **Functional region.** The join `code.interface.graphical -> code.graph.knowledge`, "inspect and maintain the
  displayed functional records". It was read from the live map; no namespace was invented.
- **Context manifest (flat).** Ticket `t-f04-lookup`; commit `c4c2e031`; namespaces `metaform.code.graph.knowledge`
  and `metaform.code.interface.graphical`; source `src/metaform/project/overlays.py` (`key_of`, `definitions`),
  `src/metaform/project/commands.py` (`_drawn`, `perform_drawn`), `src/metaform/modules/web/project_map.py`
  (`layers`); evidence: kickoff `AUDIT_FINDINGS.md` F02 to F04 and this record. Excluded: other overlays' records and
  the old CLI store.
- **Candidate.** `3b9fdd9dc7ea9a572c410f209c81b8c3576c2076`, "fix(web): the page finds each overlay's definition by
  its key (F04)". The store's display read (`_drawn`) lists each overlay by key with its stored address and
  description, and `layers` uses it instead of splitting the key. No naming rule was added. The `project` tool's
  commands are unchanged; the display read is not a tool command. Regression test:
  `tests/test_project_tool.py::test_the_pages_layers_find_each_definition_by_its_key_with_underscores_inside_a_step`.
  It failed on the baseline as described above and passes on the candidate, together with the neighbouring overlay
  tests (5 passed).
- **Live.** The web GUI was restarted after the commit. `project_map.layers('metaform', 'base')` lists `concerns`,
  `memories`, `subtypes`, `survey` and `tickets`, each with its description.
- **Verification.** See the section below, written from the independent verifier's report.

## Verification

An independent verifier, the Metaform helper `helper-4941cb8ec4be2c753e7fdfe82b4cbea1`, checked candidate `3b9fdd9d`
against the kickoff's original acceptance criteria. It changed nothing and ran the baseline in a separate worktree. Its
report (note `e8ecd9720f4fd652`):

| Criterion | Result |
|---|---|
| 1. Names with an underscore inside a step resolve to their stored definitions | accept |
| 2. Records and naming unchanged; the tool's answers identical | accept: byte-identical across `c4c2e031` and `3b9fdd9d` |
| 3. Nothing unrelated folded in | accept |
| 4. The regression test fails on the baseline and passes on the candidate | accept |
| 5. The live page lists `metaform`'s overlays with their descriptions | accept: `/api/layers` |

Verdict: **return**, for one new ruff finding in the test, `PLC0206` at `tests/test_project_tool.py:859`. It was fixed in
`d562f042`, with `ruff check` passing and the test passing. That one-line, test-only follow-up was re-checked by the
implementer, not again by the verifier, and is recorded here as such.

Integrated: `3b9fdd9d` and `d562f042` on `feat/project-tool`, pushed. Ticket `t-f04-lookup` is closed as completed.

## Decisions left for the owner (next tickets)

1. **Stable record identity (F02).** Choose durable record ids with separate order and expected-revision edits, so a
   stale edit is refused instead of landing on another record. Decide how a record keeps its id across
   `replace_record`, and whether an id is exposed in the `project` tool's read shape. Until then, shared ticket state
   has one writer.
2. **Schema compatibility (F03).** Choose what an incompatible definition change does: refuse it while rows break it,
   require a stated migration, or keep it as a proposed revision. Choose too how the affected records are reported.
   The observed cases above are the acceptance tests.
3. **CI billing.** GitHub will not start any job until the account's billing is fixed. Until then, no CI evidence
   exists for any commit.
4. **The old CLI ticket store.** `metaform map work` still writes to the old store. Moving it to the project store is
   Phase 3, and it needs the F02 contract first, because the CLI edits records by position.
