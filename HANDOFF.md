# Handoff, 2026-11-17: bring the Python project store to the person's design

**Read this first. It overrides the order further down.** It replaces an earlier version of this section written the
same afternoon, which said to port the Rust build as it stood; that would have undone the person's later decisions.

**The design is the Rust form in `core/` plus the decisions the person made after it**, in the session of 2026-11-15
21:00 to 2026-11-16 that moved the work to Python (transcript `~/.claude/projects/-home-rich-metaform/db78ce04-*.jsonl`;
the Rust session before it is summarized in `rich/other_fable_recap.md`). Every rule below names its source.

**From the Rust form (`core/`), confirmed by the person 2026-11-17:**
- The graph: `(Map) -ROOT-> (Element) -CONTAINS-> (Element) ...` for the namespace tree, `(Element) -DEPENDS_ON
  {why, how, direction}-> (Element)` for wants, `(Element) -HOLDS-> (record)` for overlay records. Everything is
  reached by edges, nothing by matching address text (`core/metaform/rust/crates/metaform-store/src/graph.rs`).
- The intake procedure as Markdown sections, `core/metaform/intake/procedure/`, each also a resource,
  `metaform://intake/<section>`, and `{"help": "intake"}`, `{"help": "intake/<section>"}` (`core/SPECIFICATION.md` 7.3,
  decisions 31 and 33; `CLAUDE.md` Prompts). The procedure is sliced because much of its context is reused by other
  operations. **Delivered two ways, as the person set out on 2026-11-17:** an agent performing an intake is given the
  sections inline in its prompt, in `sections.md` order, with no resource to read; a long-running agent is given, with
  each tool that needs some of that context, the person's words "Must read these URI to perform ... properly" and the
  sections' addresses. The same address named by five tools is read once in that context, which is the reason for the
  slicing. The Rust build did only the second way.
- A refusal carries the corrected command wherever one follows (`metaform-core/src/rules.rs`, `shape.rs`).

**The person's later decisions (db78ce04, times are 2026-11-15/16), which stay:**
- 00:53 "There isnt a go to that was a stateful idea": no `goto`.
- 01:28 one `ref` per element: an entry point, an external link, or `project://` to another project.
- 22:18 layers are called overlays, and they are arrays by default; 01:40 an overlay exists only when defined under the
  overlay root, and its definition holds its error templates, example, schema, and required and optional fields.
- 22:26 overlay records stored as structs of arrays, a column per field, not arrays of structs.
- 00:52 the tool is named `project`; 00:58 paths lead with the project's name (`metaform.code...`).
- 03:19 a single-writer service owns the database; other processes send it writes.
- 01:15 no command is an MCP tool; the one tool is `project`.

**What the Python store gets wrong against that** (seen in a copy of the live map, `docs/plans/old-store-removal.md`):
the tree is not stored (parents are empty nodes with no `CONTAINS` edge), there is no `Map` node or `ROOT` edge and the
project root is empty, overlay records are joined to elements by address text instead of `HOLDS` edges, the intake is
served as one XML file, `help intake` is refused, and several refusals carry no corrected command.

**More of the person's decisions from the same session** (`L` numbers are from the Rust session's log, which the person
pasted into db78ce04 at 01:08):
- 01:21 "ladybug was how we started, albiet we have a nested structure now.. one I really need for you to fully grasp":
  the nested structure is the point. The port flattened it; this is the main fault.
- L2695, L3269: the base map is light. An agent is given the list of addresses and the wants overlay; `map` sends only
  the base map.
- L2562, L2626: one `ref` on an element in the base map, and a `ref` on each record of an overlay. A ref is an entry
  point or a discrete reference, never an index of the code; more data goes in an overlay.
- 01:44: the person's examples of commands and answers, such as delete of an element still wanted being refused with
  the remediation that removes the want; `name` is an alias that does not match the address.
- 03:09 "If fields come back filled with examples that IS NOT the design."

**Settled on 2026-11-17 from those reasons, without asking:** no `raw dump`, because agents are given the light base
map and nothing the person has said needs the whole nested form read back; and a field an element does not define is
refused, not kept in `extra`, because the base map holds only well-named fields and any other data belongs in an
overlay.

**The work, each a commit, pushed:** tests first for each rule above (from `core/`'s tests where they apply, rewritten
for the later decisions where they differ); then the store's graph edges; then the intake sections at the highest
reasoning level; then the readers; ask the person before a new intake.

---

# Handoff, 2026-11-16 (evening)

Branch `feat/project-tool`, pushed; every item below is committed there unless it says otherwise.

## Why this work, and where to start

**The purpose.** Metaform starts AI agents and gives each one the part of the project it needs. The `dispatch`
module starts and talks to them over the Agent Client Protocol (ACP). The person's aim, restated this evening: **no
harness is named in Metaform's code.** ACP exists so a client drives any harness one standard way, and ACP's
registry lists them (46 today: Claude Code, Codex, Gemini CLI, Cursor, Goose, Factory Droid and the rest). Today
three are typed into the code (`AGENTS`), the rest can only be pinned from a shell, and an intake named the map's
harness element after those three. After that come profiles: one saved definition of how an agent starts (harness,
model, reasoning level, Claude Code's `agent`, startup prompt), so the person can set up a team with roles.

**Next: step 3a of `docs/plans/dispatch-owns-acp.md`, the registry as the list** (written there in full, commit
`57405a8a`): a checklist of every registry harness that can start here, found ones first; checking installs it into
the home and asks it over ACP (ready, needs login, cannot start); launch by registry id; `AGENTS`, `BUILTIN`,
`PROFILE_ONLY` and the runner's `== 'claude'` removed; registry icons beside every harness name, and a badge at the
upper left of each agent's character showing its harness, with model, reasoning level and context window on hover.
The badge matters for safety: the person twice had Codex running when they thought it was Claude and the reverse.

**Then step 2b**, moving `runner.Session` onto `dispatch/acp/`. Reviewed this evening; see "Open decisions".

## What happened this evening

- **Reviewed for 2b:** the plan, the `acp/` layer, commit `17e2c1e2` in the worktree `/home/rich/metaform-dispatch-acp`
  (sound: the SDK tells observers after the bytes are written, so `Client.written` holds; build on it), and branch
  `wip/runner-move-partial` (one untested 1,000-line pass; a lookup only).
- **The system agent's chat was stuck on "Please stand by".** Cause: `leads()` in `web/server.py` cached "not the
  workspace's" for the system agent's work id, asked while it started, so every read went to the project on screen.
  Fixed in `d71dc909`, test in `71df1887`; the web server runs that code (fingerprint `bc1d142b9536`, restarted
  00:44 UTC) and a headless Call attached ("With your system agent · Ready"). Its earlier turn had failed on a DNS error reaching Anthropic's API (bug 9).
- **Bugs recorded** in `docs/plans/bugs-to-fix.md` (`e3fc6466`), 9 to 14: a system agent stuck after a network error;
  the SDK dropping Claude Code's `subagent_update` and `session_message`; `user_agent` answering `session_id: null`;
  no handler for `auth/status_update`; harnesses still named in code; "lead" versus "system agent".
- **Names.** The person's choice: it is the **system agent**, never "the lead". New code says system agent.
- **Icons.** An earlier session told the person they could not show which harness an agent runs; that was wrong.
  Showing a harness's registry icon beside its name to identify it is fine. The agent characters stay as each
  agent's own identity; the harness badge is added beside them.
- **`AGENTS.md`, "Landing work"** (`bf3dd117`): every agent task ends with a commit labelled with what it did and a
  push, and the agent does not stop before that step.

## Open decisions (the person's)

1. **Order:** 3a before 2b was proposed, so the runner's options code is rewritten once (3b, options by id, after
   2b). The person went on to shape 3a without saying otherwise; confirm before starting.
2. **How 2b lands:** every SDK call and callback shares one stdio stream, so the plan's "tests pass after each
   concern" cannot hold past the first. Proposed: one switch commit with every dispatch test green, built concern by
   concern in the worktree; or a temporary bridge so each concern lands alone.
3. **Claude Code handing work to Codex** through the `codex-rescue` plugin is invisible to dispatch (plan issue 18):
   flag it on the agent when it happens, keep the plugin out of Metaform's sessions, or leave it.
4. **Fresh start check:** the restart alone cleared the bad cache, so the fix itself is proven by its test, not yet
   by a system agent started from scratch (that spends a Claude turn; ask first).

## What remains, in order

1. **Step 3a**, the registry as the list (above).
2. **Step 2b**, `runner.Session` onto `dispatch/acp/` (plan, step 2, with the notes for the move). Then one live
   Claude Code and one live Codex session from the page, after asking the person.
3. **Step 3b**, options by id; the settings per harness name go.
4. **Step 4: profiles and assignments**, each profile naming harness, model, reasoning level, `agent` and prompt.
   Designed only; nothing built.
5. **Steps 5 to 7:** the launch service, roundtables on dispatch, dispatch required.
6. **Specifications on the map** (`docs/plans/specifications-overlay.md`).
7. **Bugs** in `docs/plans/bugs-to-fix.md`.

## How to work (the person's rules)

- Do the work yourself. No subagents unless the person asks or a multi-agent mode is on.
- Every task ends with its work committed, labelled with what it did, and pushed; no asking first and no waiting for
  a test. Leave nothing uncommitted or half working.
- A task ends committed, pushed and running: restart what serves it after the last commit, check the running code
  is the committed code (the "code" fingerprint in `~/.metaform/run/web.log` against `code_print()`; it hashes every
  `.py`, tests included), check the behaviour, and tell the person exactly what to do so they can test it. Never
  report a change as not running or not committed.
- Change only what the assignment is about. A bug found on the way goes in `docs/plans/bugs-to-fix.md`.
- Read the code, its history and its specs before changing or removing anything.
- Speak plainly. Check with short text, not screenshots or long printouts.

## Accomplished earlier on 2026-11-16

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
