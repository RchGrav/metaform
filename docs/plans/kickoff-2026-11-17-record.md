# Kickoff 2026-11-17: what was done, phase by phase

Source of the work: `rich/metaform_factory_kickoff_2026-11-17.zip`, the person's kickoff archive. The work followed its
`DEVELOPMENT_KICKOFF.md` Phases 0 to 5, at the person's `/goal`: "inside of the rich folder you will find a kickoff
archive, follow its plan through to completion". Run by AtomicRespect (session
`91c96c16-7a53-4c04-a3da-00dee6342154`), with Metaform helpers as independent verifiers, experiment arms and parallel
implementers. Phase 0 and the first slice are in `kickoff-2026-11-17-slice1.md`. Every change is its own pushed commit
on `feat/project-tool` with a `Metaform-Session` trailer naming who made it. Each verdict is a `verifications` record at
`metaform.code.graph.knowledge`.

## Decisions taken, with their reasons

The kickoff reserves product semantics for the owner. The person's `/goal` asked for the plan to be carried through,
so each decision below adopts the kickoff's own proposal and is recorded here to be reviewed or reversed.

| Finding | Decision | Reason |
|---|---|---|
| F02 record identity | Each overlay record keeps an id (`r-` + 16 hex digits) and a revision. An edit that names them is refused when stale (`RECORD_MOVED`, `RECORD_GONE`, `RECORD_CHANGED`). An edit by position alone works as before. | OVERLAY_CONTRACT section 2. Checking only when a client names the id keeps today's read-modify-write clients working. |
| F03 schema evolution | A definition change that would leave stored records outside it is refused (`DEFINITION_INCOMPATIBLE`). The refusal names the records and offers the fix: update the records first, or for a new required field, define it as optional first. | OVERLAY_CONTRACT section 3 allows rejecting an incompatible change unless a migration is supplied. |
| F05 memory | The page reads and writes the memory layer. Old memories-overlay records are listed apart and labelled, never mixed in. | The founder, 2026-11-17: memory is "all stored in the memory layer", never an overlay. |
| F07 root blocks | The root holds the specification's blocks, the project's own description, and no other overlay. Built in Phase 5 (`b6749507`); the first cut (`cace8c54`) had refused root text. | F07: choose root support explicitly; the design says blocks at the top of the map are the project's own description. |
| F09 ticket identity | A ticket id names one ticket in the project (`TICKET_ID_TAKEN`). `map work op=take by=` is exclusive and claims with the revision it read. | The tickets overlay is the tool's own contract. Other overlays may still repeat values. |
| F10 context | A context manifest is kept for each slice. No versioned aggregate read was built. | F10: keep a manifest now; build an assembler only where measurements show a benefit. |
| F11 trust boundary | Disclosed, not changed (below). | F11: disclose the actual boundary; do not add a static roster. |
| F12 definition metadata | Only the structural rules a real format needs: the specification's block rules. No general schema platform. | F12: do not build one speculatively. |
| F13 relationship identity | A want is named by holder, element and ref, as the store keys it. The page's enumerated join id is never used as a key. | F13: settle identity before relationship-based handoffs expand. None exist yet. |

## Trust boundary (F11), as checked

The project-store service listens on 127.0.0.1 only. A caller must prove the key in `~/.metaform/maps/service.json`,
which only the home's user can read (mode 600). Inside that boundary nothing limits which element or overlay a caller
writes: every agent runs as the person's user, and a profile's role or a worktree path is not enforcement. The map
database `~/.metaform/maps/metaform.lbug` is mode 644, readable by any local user. That is harmless on a single-user
machine, but it should be 600 before Metaform runs where other users log in. It was recorded, not changed.

## Phase 1: the comparison experiment (VALIDATION_PLAN section 3), one paired feasibility run

Both arms got the same workload (F04, stated as the observed failure), the same criteria, the same starting commit
`c4c2e031` and the same tools. Each worked in a fresh worktree and was told not to read later history. The scoring
used one hidden acceptance test that neither arm saw, the F04 regression test, run against each arm's change.

| | A: ticket only (`helper-6a684a16`) | B: plus functional context (`helper-7680e5a6`) |
|---|---|---|
| Hidden acceptance test | passed, 73 of 73 | passed, 73 of 73 |
| Elapsed | 2 min 05 s | 2 min 05 s |
| Cost (session record) | $0.863 | $0.767 |
| Total tokens | 1,179,941 | 945,331 |
| Output tokens | 10,722 | 9,442 |
| Repair | the display read carries descriptions by key; `layers` uses it | the same design |

One pair proves nothing on its own; VALIDATION_PLAN says so. B's context came from the slice-1 mapping, which this run
does not count. Both arms converged on the design that had already been committed (`3b9fdd9d`). The diffs are kept in
`/tmp/kickoff-chars/exp-a.diff` and `exp-b.diff`. The plan's next step, five pairs, waits on the owner's numeric
targets.

## Phase 5: two implementers in parallel, and the combined-commit check

Two helpers worked at the same time in separate worktrees and branches, both from `1bb6d833`, on different functional
regions. Both regions sit on the shared overlay contract:

- **Root support (F07)**, `helper-d9c31cfd`, in the project store: `HOLDS` reaches every overlay table from the root as
  well as from elements. The root holds the specification's blocks, the project's own description, and only those;
  another overlay at the root is refused by name. Integrated as `b6749507`. It cherry-picked cleanly onto the moved
  head. The combined store, MCP, memory and intake tests passed (86, 18, 52, 8). On a copy of the live map, integrity
  was clean and the specification round-tripped; live, the export stayed byte-identical.
- **Autoticket on the project store (F01)**, `helper-21d039ab`: a store project's fault is filed in its `tickets`
  overlay, matched by id or title at the element, and reopened with the fix that did not hold. Non-store projects keep
  the old path. Integrated as `1014e158`.

**The combined-commit check found a real interaction.** On its own branch, autoticket's new test passed. Combined with
`64cc8690`, made in parallel, it failed. That commit had `map work done` add the resolution on the note's first line,
and autoticket rewrites that status line whole on each recurrence, so the resolution was erased. Neither change was
wrong alone. It was fixed on the lead's side in `ea275fa4`: the resolution goes in its own paragraph. After that,
autoticket's test file showed only its 2 failures that already fail at `c4c2e031`. Collision rate for this pair: one
true contract collision (the shape of the note), and no textual merge conflict.

## Phase 5: release and rollback drill

In a throwaway worktree at HEAD, one feature commit was reverted alone, the board change `156e2598`. Its code came out
cleanly. The test file needed one hand fix, removing that feature's own test, because every feature's tests had been
appended to the end of `tests/test_project_tool.py`. After the revert, all 83 remaining tests passed, and the board
code no longer named record ids. Reverting the guard `bf00e3a4` alone conflicts in its source too: the specification
command (`cace8c54`) is built on the same `MODULE` line, a real dependency. **Lesson:** a test placed beside the tests
of its own area, not appended at the end, keeps a rollback mechanical.

## Completion ledger (F16)

Each claim is kept separate: the source is present; tests are present; those tests were run (filtered, as `CLAUDE.md`
requires); the change is integrated on `feat/project-tool` and pushed; it was seen working on the live system; and the
live data was migrated where it had to be.

| Change | Commit | Source | Tests | Run | Integrated | Seen live | Data |
|---|---|---|---|---|---|---|---|
| F04 overlay descriptions on the page | 3b9fdd9d, d562f042 | yes | yes | yes | yes | yes: page `/api/layers` | not needed |
| F03 incompatible definition change refused | 553f5968, 3718c462 | yes | yes | yes | yes | not exercised on live data | not needed |
| F02 record ids and revisions | 5b98a61a, 3718c462 | yes | yes | yes | yes | yes: live tickets carry ids | yes: 70 records on a copy first, then live, content identical |
| Board edits by record id | 156e2598 | yes | yes | yes | yes | page restarted; not clicked by a person | not needed |
| `map work` on the project store | dff2e98d, 64cc8690, ea275fa4 | yes | yes | yes | yes | yes: live list, competing take refused | not needed |
| F07 root holds the project's description | b6749507 | yes | yes | yes | yes | yes: live export unchanged after the upgrade | yes: root pairs added on open, checked by integrity() |
| Autoticket files to the store's tickets | 1014e158 | yes | yes | yes | yes | web restarted; no live fault observed yet | not needed |
| F05 memory from the memory layer | 40b125d9 | yes | yes | yes | yes | page restarted; the live graph is empty | old overlay records listed apart (none live) |
| F14 full-depth walk | 8f92f721 | yes | yes | yes | yes | not exercised (live depth < 30) | not needed |
| F15 upgrade integrity | 262ef8bf | yes | yes | yes | yes | live copy reports no problems | not needed |
| F09 unique ticket ids, exclusive take | 886aa1b0, 64cc8690 | yes | yes | yes | yes | yes: competing take refused | live ids already unique |
| F01 old map verbs refuse on store projects | bf00e3a4 | yes | yes | yes | yes | yes: `map where` refused live | not needed |
| Orient prompt names the project tool | 2cf3c9cd | yes | none (wording) | n/a | yes | not observed in an agent's guide | not needed |
| F06 specification overlay and document | cace8c54 | yes | yes | yes | yes | yes: live round trip byte for byte, 22 sections | the overlay is added to each project on open |
| Element read carries its blocks | 1f8ca27e | yes | yes | yes | yes | no blocks are live yet | not needed |
| 3D map region proposal | 1bb6d833 | document | round-trip checked | yes | yes | not imported: awaits the person | not imported |
| Verifications overlay and records | live map only | definition on the map | n/a | n/a | yes | yes | 12 verdicts recorded |

## Baseline facts carried, not caused here

- **CI:** GitHub starts no job ("recent account payments have failed or your spending limit needs to be increased").
  No commit on this branch has CI evidence.
- `src/metaform/modules/map/tests/test_map.py`: 9 failures, identical at the audit's commit `c4c2e031` before any
  kickoff work.
- `src/metaform/modules/autoticket/tests/test_autoticket.py`: 2 failures, identical at `c4c2e031`.

## Waiting on the person

1. The placement of the 3D map's requirements (`specification-region-3d-map.proposed.md`), then
   `metaform map specification op=import file=docs/plans/specification-region-3d-map.proposed.md --project metaform`.
2. Every decision in the table above, to keep or reverse.
3. GitHub billing, so that CI runs.
4. The numeric targets for widening the experiment from one pair to five (VALIDATION_PLAN section 4).
5. Which features with no counterpart in the store to keep (`old-store-removal.md` step 3): questions and messages,
   layers and knowledge, bases, Cypher, the critic, the glossary. The worker protocol's pairs and rounds are built on
   old-store tickets and need their own migration.
