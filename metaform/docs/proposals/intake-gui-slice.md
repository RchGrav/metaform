# Proposal: slim intake GUI

Status: draft for founder confirmation. Nothing here is built or approved.

## What exists in the old repository

Read-only source: `RchGrav/metaform`, clone at `src/metaform/modules/web/page/app/intake/intake.js`.

- The intake UI is 395 lines of browser JavaScript. It imports about twenty modules of the old page (dock, board, live stream, agent pickers, admin), so it cannot be lifted out unchanged.
- The old server is the Python standard-library threading HTTP server (`modules/web/server.py`), not Flask. The word "flask" in that repository appears only as a project name in messages and tests.
- The old intake backend is `modules/intake/__init__.py` (about 1,650 lines). It uses the old field names `purpose`, `ef`, `ifd` and "purpose record". The current specification uses `goal`, `function`, `intent` and `wants[]`. Its behavior is a reference, not a drop-in backend.

Conclusion: reuse the behavior and layout ideas. Rewrite the slice.

## Scope of slice 1

In:
1. Show whether a project has an intake: none, being recorded, left unfinished, or complete.
2. Show the recorded map as a list of elements by namespace address. For each element, show its `wants[]` entries: `goal`, `function`, `intent`, and `ice` when set.
3. Start an intake: show the intake prompt for the chosen project, with a copy action. The agent runs it, not the GUI.
4. Finish and discard, each behind an explicit confirmation.

Out:
- The rest of the old page: workspace, views, 3D agents, voice, ultra, dock, dispatch, sessions, admin.
- Live updates. The stated constraint is no recurring polling, and no transport has been selected. Slice 1 reloads on explicit user action.
- Agent launch from the GUI. Orchestration is a later slice.
- Multi-user access and authentication.

## Vocabulary

The stored names follow `DECISIONS.md`. Intake definitions (RE, PE, OP, EF, IFD, CQU, ICE) do not change.

| Intake term | Stored name |
|---|---|
| OP | `goal` |
| EF | `function` |
| IFD | `intent` |
| PE relationship | a `wants[]` entry under the receiver |

Display labels in the GUI should use the stored names, with the intake term in parentheses on first use.

## Constraints (founder, recorded in DECISIONS.md)

- The chassis, settings system and module approach are the base. Any intake backend lands as a module.
- No new tools without a founder decision.
- Keep worktree provisioning and feature commits.
- Target about 500 lines per source file.

## Open decisions for the founder

1. **Data source for slice 1.** The database is not built. Options:
   - a. Read the nested JSON document from a file in the project. *(Superseded: maps are stored in LadybugDB, not files; R-4.1.)*
   - b. Read from a LadybugDB stub. This tests the real path earlier, but it depends on a backend that does not exist.
   - My recommendation: a.
2. **Start mechanism.** Options:
   - a. Show the prompt with a copy button. The person pastes it into their agent.
   - b. Launch an agent from the GUI. This needs orchestration, which is not built.
   - My recommendation: a for slice 1.
3. **Front-end stack.** The old page is plain browser JavaScript served by a static server. Options:
   - a. Plain HTML and JavaScript, served by a small Node server. This matches the Node work for MCP.
   - b. A framework. More setup, and no benefit for a view this small.
   - My recommendation: a. This is an inference from the existing code and the MCP work, and it does not settle the runtime choice.

## Acceptance (criteria for later, not results)

- Given a project with a recorded intake, the page lists every element and every `wants[]` entry, with the stored field names.
- Given no intake, the page offers to start one and shows the prompt.
- Finish and discard each ask for confirmation and do nothing until it is given.
- The page makes no recurring requests.

No test results exist yet for any of these.
