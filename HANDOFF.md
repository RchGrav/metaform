# Handoff, 2026-11-16 (end of day)

Branch `feat/project-tool`, pushed; every item below is committed there unless it says otherwise.

## How to work (the person's rules from today)

- Do the work yourself. No subagents unless the person asks or a multi-agent mode is on: they cost twice and today
  they spent most of the day's usage.
- Every feature lands as its own commit and is pushed; an assignment is not done until then.
- Change only what the assignment is about (`AGENTS.md`, "Scope is the assignment"). A bug found on the way goes in
  `docs/plans/bugs-to-fix.md`, not into the code.
- Read the code, its history and its specs before changing or removing anything.
- Speak plainly. Check with short text, not screenshots or long printouts.

## Accomplished today

**Dispatch and the agent protocol** (plan: `docs/plans/dispatch-owns-acp.md`)
- Step 0: Fast mode is keyed to ACP's `speed` option, so it no longer switches Claude Code's Ultracode; the call window
  shows the harness's main options with the rest under "More from <harness>".
- Step 1: what each harness offers is kept once in the home (`dispatch/offered.py`), asked of the harness itself.
- Step 2a: a new protocol layer, `dispatch/acp/`: one model of a session, a connection that asks for v2 and falls back
  to v1, a v1 and a v2 adapter, the setting `dispatch_acp_v2`. Tested with the fake agent on both versions. Claude
  Code's and Codex's adapters both select v2.
- Client files and terminals ("Files/Terminals through Metaform") deleted: an editor feature, never used by the
  harnesses, and it forced the old protocol version.
- The plan gained profiles (one definition of how an agent launches; a workflow may override the prompt) and how the
  software-factory pattern maps onto Metaform.

**The page**
- 3D map: no line from every element to the root; joins as long as before 2026-10-17, measured between shapes; the
  camera "pivot" slipped in on 2026-10-18 removed, so a selected element can be dragged again.
- Element panel: "What an agent assigned here receives", a small picture of the element, what it wants and what
  wants it, from the project tool's own answer (`/api/local-view`), with Wants and Wanted by lists; "Known as".
- Chat: the harness picker comes back after Stop agent; Claude Code's subagent option left out of the chat; a message
  is no longer shown twice.

**The project**
- `metaform` registered and mapped by an intake (46 elements, 66 joins).
- `AGENTS.md`: "Scope is the assignment" and "Landing work".
- Plan for specifications on the map: `docs/plans/specifications-overlay.md`, porting the Rust branch's tested design
  (archive `/mnt/c/spec_roundtrip.zip`).

## What remains, in order

1. **Step 2b: move `runner.Session` onto `dispatch/acp/`**, one concern at a time in the plan's order (open and
   initialize; session new, resume, close; the prompt turn; updates; permissions and elicitation; config options;
   logins; the probes), dispatch tests passing after each, one commit each. The notes for the move are in the plan
   under step 2. Started work to read first, in the worktree `/home/rich/metaform-dispatch-acp`: commit `17e2c1e2` on
   `feat/dispatch-acp` (additions to the layer, not reviewed) and branch `wip/runner-move-partial` (a half-done,
   untested edit of `runner.py`; read it, do not merge it). Then one live Claude Code and one live Codex session from
   the page on v2, after asking the person, since they spend tokens.
2. **Step 3: the registry.** The three hard-coded harnesses replaced by the ACP Registry; this also fixes the map
   naming its harness element "Claude Code, Codex, Google Antigravity".
3. **Step 4: profiles and assignments.**
4. **Steps 5 to 7:** the launch service, roundtables on dispatch, dispatch required.
5. **Specifications on the map** (`docs/plans/specifications-overlay.md`).
6. **Bugs** in `docs/plans/bugs-to-fix.md`: `dispatch wait` cannot follow an intake; one dispatch test, two
   settings-screen tests and one recovery test fail, each before today's changes; the harness element's name.

## How to check a change here

- One test: `uv run pytest -n 0 path/to/test.py -k name`. In the worktree use its own `.venv/bin/python -m pytest`.
- After changing Python, `metaform web restart`; page files are served from disk.
- What a harness answers: `metaform dispatch options agent=<agent> --json`.

---

# Earlier handoff: what had been done before this session

Branch `feat/project-tool`, pushed. As of 2026-11-16.

## The project store

- A new store for each project's map, on LadybugDB: one database per project under `~/.metaform/maps`.
- One process per home owns the databases. Every other process sends it commands. Writes wait in a queue, are committed in groups, and can be sent twice without being done twice. Reads never wait on a write and share at most four connections per database.
- The map's shape follows one rule: an object is a step in an address, a list is an overlay, a plain value is a field. An element holds five fields: `technical_name`, `name`, `role`, `ref`, `status`.
- Overlays are defined under `<project>.overlay`. A definition holds its description, instruction, and each field's type, rule and example. Input is checked against it, and a refusal says what was wrong and how to correct it.
- Every project is given three overlays: `wants`, `tickets` and `memories`. Tickets and memories use the field names the old system already had.

## The one tool

- One MCP tool, `project`, on the server named `metaform`. Its arguments are one command; the project's name leads every path. It keeps no session.
- No command is a tool any more. Agents run `metaform <module> <verb>` in their shell.
- The old server is deleted: the catalog, every command-as-a-tool, the rule that refused a call until its instructions were read, the records of what each agent had been shown, and the old map views.
- An agent is given its rules and its task at start, and nothing else. An agent on the intake is given its task alone.
- `metaform mcp serve --http` serves the same small server, with the same sign-in checks and A2A beside it.

## Intake

- The intake module serves the new procedure, `digital_typology.xml`, byte for byte, with the request in the procedure's own slot.
- An intake agent records with the `project` tool, into the new store.
- The old intake recording is deleted: the module went from 1,673 lines to 212.

## The page

- The map, the element panel, the Layers control, the board and the Memories section read the new store.
- The board creates, moves, renames and deletes tickets in the new store. Start agent hands the agent the ticket; the agent takes it, notes it and closes it itself.
- The page redraws within about a second of a write.
- Clearing a project removes its map from the new store.
- A project switch takes about 2.5 seconds, down from about 7.
- With no project chosen, the page no longer shows error banners.

## The lead agent

- The chat box is the lead: one agent for the whole home. It lives in a `workspace` project of its own, stays in the chat box across project switches, and can work on any project.
- The chat works with no project registered and before any intake.
- The lead's task text says how to lead a team: team members are Metaform agents started with `metaform dispatch helper`, visible on the page.
- A helper tells the lead it is done itself, with one note its own prompt asks for. Metaform no longer writes that line.

## Faults found by running it for real, and fixed

- The store's service kept running old code after an update. A caller now replaces it.
- Reading connections piled up until the engine reported "buffer pool is full".
- A fault inside the service dropped the caller's connection instead of answering.
- The packaged dependency list did not name the database engine.
- The server behind the `project` tool was not kept running under `hold`.

## Housekeeping

- `CLAUDE.md` describes the server and the store as they are now, and states that the intake procedure and its semantics are the founder's.
- Tests of deleted code were deleted with it. The server, intake and store tests pass.
- All projects were removed from the home on 2026-11-16; `intake-trial` and `clear-trial` were registered afterwards for testing.
