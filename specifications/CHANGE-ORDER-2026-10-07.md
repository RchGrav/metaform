# Change order, 2026-10-07

The decisions of 2026-10-06 and 2026-10-07, in the order they are to be built, each with what it changes, why, and
what it depends on. Written so the work can be picked up by anyone from this file alone. Records referenced are in
this folder; nothing here replaces a record, and each item below becomes or amends one when it is built.

Status of each item: **done** (committed on `chassis`), **decided** (agreed, not built), **open** (needs the owner's
answer, named).

## 0. Done on 2026-10-06, for the record

- Web GUI stabilized: dispatch events batched on the page (one refresh per 500 ms, incremental chat and agent
  window, chat dock pinned to its session) and in the server and runner (lines announced at most every 0.25 s,
  bursts merged per page). Commits on `chassis`. VIEW-018, VIEW-039, BASE-052 amended.
- `dispatch_autostart` switched off by hand after 981 sessions in one day; the loop is item 5.
- Seahorse as the 17th agent glyph; agents drawn on the 2D map. VIEW-035, VIEW-040.
- `map ask` carries the question form through the MCP tool's named fields; a missing part is a notice, never a
  refusal. MAP-050 amended. A refusal was built and withdrawn the same day: no gate on an inference step.
- `metaform prompts review`: a terminal review of every prompt agents read, with purpose comments on all 70,
  editing in place when exact, a packet for an agent otherwise, and `metaform prompt register` for prompts kept
  anywhere. MCP-031 amended, STORE-044. Every prompt element now has a purpose comment.
- Two ultrareviews over 24 runtime files, 10 findings, all fixed: commits `7e2a148`, `6962b36`.
- Branches: `main-historic` is the old line; `main` and `chassis` are the same commit. Nothing pushed.
- Jev experiments in `artifacts/jev-experiments/` (untracked): recall in 3 calls, 6 of 6 on the challenge with
  the scoring question "this memory is directly relevant"; the reversed-address entry; shaping rules; profiles.
- Event-log prototype in `artifacts/store-prototype/eventgraph.py` (untracked): six independent processes, one
  SQLite log, identical projections, Cypher over the graph.

## 1. Naming: base, id, objects

**Built, 2026-10-07, on branch `store-oplog`, commit `Naming, change order item 1`; STORE-041 amended.** First, because every later item writes tables and records under these names.

- The object a project has one or more of, with its own store, is a **base**; one is active. The layer the intake
  writes is `base`. "Metaform" names only the system. `metaform_id` becomes `base_id`; the `metaforms` table becomes
  `bases`; `map metaforms`, `add-metaform` become `map bases`, `add-base`; the records that say "the metaform"
  meaning this object say "the base".
- A layer is named for what it holds or what it is, never for what produced it: `base`, `memory`, `sources`, and a
  knowledge layer for its variable.
- Every object's identifier is `id` on its own record. A reference to another object is `<object>_id`. Nothing
  else is ever named id. The nine current names (`element_id`, `item_id`, `work_id`, `message_id`, ...) as primary
  keys go.
- One **objects** registry, `id` and kind, replacing `element_ids`, `join_ids`, `item_ids`, so any id is one indexed
  lookup whatever it identifies.
- Why: one concept, one name, one index. Nine names for one thing is the design flaw; the registries were a
  workaround for not having one object table.
- Build: one store layout upgrade, done as item 2's upgrade so the data is rewritten once.

## 2. The store as an event log, the graph in memory

**Built, 2026-10-07, on branch `store-oplog`; the record is STORE-046.** The draft it was built from is the text below.

- SQLite stays, one file per base in the home, standard library only. Inside it: `ops` (seq, session_id, op, kind,
  id, layer_id, data as JSON; append only), `objects`, `snapshots`, and the modules' own declared tables as today.
- Every write is one appended op row, add, change or remove, under `BEGIN IMMEDIATE`; nothing is ever edited.
- Every process holds the base as a networkx `DiGraph`: elements as nodes, joins as edges from receiver to each
  provider carrying the purpose, items as nodes attached to their target, all carrying `layer_id`. A layer is a
  view by that attribute. Reads never touch SQLite for structure.
- Opening a base loads the log (whole at first; a snapshot plus replay when a log is large enough to need it).
  A process catches up by reading ops past the last sequence it applied, on `map.changed` or before a read.
- Queries are Cypher through grandcypher over the graph, for agents and tools, beside the networkx reads.
- The `current_*` tables go: the newest version of an object is the newest op for its id.
- Upgrades write a new file from the old one opened read-only and rebuild the projection from it; the old file is
  never changed in place.
- No FTS index: Jev reads every memory title in one call; the `search` commands match over the graph in memory.
  FTS5 returns only if a store grows past what one Jev request can scan.
- Kùzu was proposed and rejected: upstream archived October 2025 (Apple acquisition); the log needs no second
  engine. A resident process holding one graph (item 8) is where this ends; the per-process projection is the step
  that needs no new process.
- Why: the base is 10 KB and a store a few megabytes; it fits in memory and every graph question becomes
  microseconds. An ordered log replayed deterministically gives history, provenance, variants and recovery from one
  mechanism. Two processes at one sequence have identical graphs. Two corruptions came from SQLite as the live
  structure under concurrent writers; one appending writer and readers on a projection is the shape that cannot
  corrupt.
- The DAO (`data/store.py`, the "data access object" element) is the only place that changes: reads answer from
  the graph, writes append ops and apply them. Modules, tools and the CLI keep their surface.
- Depends on: item 1 (same upgrade). Dependencies added to the chassis: `networkx`, `grand-cypher` (PyPI name).
- Acceptance: opening from log alone equals snapshot plus replay; every current read returns the same answer from
  the graph as from SQLite today; removing one op and replaying removes exactly its effect; the concurrency suite
  passes with writers appending and readers on projections.

## 3. The page applies ops

**Built, 2026-10-07, on branch `store-oplog`; VIEW-018 amended.** The web page receives the ops since its last sequence and applies them to what is drawn: add this
node, update that label, move this card. It stops rebuilding the map, the panel and the board on every change.
This is what ends the shuddering; item 2 makes it possible and does not do it. Done with item 2, not after.

## 4. Memory: one file in the home, recall by concept

**Decided.**
- One `memory.sqlite3` in the Metaform home, shared by every project, same op-log shape as a base. Each memory
  carries `base_id` when it is about a project and `node_id` when it is about a node; a memory about a tool, a
  harness or the person carries neither and is shared across projects. Memories outlive bases; a collapsed or
  deleted base does not strand them. Export of a base copies its memories by `base_id`.
- A memory is one claim in plain words, attached to the element or purpose it is about, with the condition under
  which it applies as a sentence Jev can test. The memory prompt is rewritten to produce claims; the current one
  produces audit records ("Observed and verified ..., Evidence ..., Valid while ...") and that is why today's
  memories read as compliance notes. The owner's judgment, 2026-10-06: the recorded memories are not worthwhile context.
- Recall, conceptual not lexical, a concept being a purpose on the map: (1) Jev places the text on the map by one
  choice over the reversed addresses; (2) the graph expands to the purposes those elements serve and are served
  by, one hop each way, no model call; (3) one Jev call judges every memory attached there: directly relevant,
  condition holds now, an agent would get this wrong without it; (4) one more hop through what Jev marks; (5) the
  result carries the concept path, "because X serves purpose P and this records a failure of P". Three or four
  calls, about a second, a fraction of a cent, no embeddings, every step explainable.
- Proven pieces: entry by reversed address ties the best placement at a sixth of the cost; the title scan is the
  net that reaches memories filed elsewhere; the scoring question "this memory is directly relevant" returned
  exactly the target on all six challenge cases. See `artifacts/jev-experiments/README.md`.
- Depends on: item 2 for the graph; item 6 for the `jev` service.

## 5. Dispatch: sessions live, work is saved, no shared checkout

**Decided**, with one open point.
- A session lives as long as its ticket. The runner no longer ends a session when a turn finishes with the ticket
  open; the agent waits for the next message or answer in the same conversation. Ending happens when the ticket is
  done, when the person stops it, or after a bounded idle time. This was a choice ("work never stops"), not a limit
  of ACP, and it caused the 981 restarts and made working agents unreachable. BASE-052 amendment drafted.
- Messages and answers reach a working agent through the adapter's steering (`_session/steering`, advertised at
  initialize by claude-agent-acp 0.86.0) when offered, else as the next prompt. The runner reads what each adapter
  supports; Codex and Gemini adapters may not offer it.
- `dispatch_worktrees` on by default. Each agent in its own worktree on a branch per ticket; a project with no
  origin is given one before its first agent starts.
- The runner, not the agent, commits: a checkpoint on the ticket's branch at every step filed and at session end;
  recovery does the same for a dead runner. A checkpoint says nothing about readiness; the branch is squashed to
  one commit when it merges through the review flow (VIEW-044).
- When a session ends: commit, collect the variant (PROJ-017; the option to leave the worktree is withdrawn),
  verify both, then remove the worktree. If either save cannot be proven the worktree stays and the ticket carries
  a signal. A worktree is a folder; the commits and the variant are the record; removing the folder loses nothing.
- Pin the adapters: `npx -y` fetches an unpinned version on every start.
- Capture the agent's stderr into the transcript.
- Set the model and thinking level per ticket through the adapter's session model and effort options; today
  nothing sets them. This is where Jev's choice of model per task plugs in.
- **Built, 2026-10-08**, with the owner's decisions of that day: the runner keeps the session when a turn ends with the
  ticket open, the ticket stays taken, autostart starts only untried tickets, and agents ask nothing, VIEW-042,
  MAP-050 and BASE-052 amended. The rest of this item, worktrees, checkpoints, adapters, stderr and model per
  ticket, is still decided and not built.
- **Open:** a branch of an abandoned ticket, keep until removed, or remove after 30 days with the variant as
  the record. Recommended: 30 days.
- Depends on: nothing; can start now. Item 2 does not block it.

## 6. The `jev` service, optional

**Decided.** A chassis service, off by default, one `decide(state, questions)` call any module can use, answering
each question with its probabilities, confidence and an unsure flag, or nothing when the service is off or the key
is missing, so every caller keeps its current behavior. Key from `OPENROUTER_API_KEY`, never stored. Jev decides,
code owns the thresholds, an unsure answer goes back to the caller. Never a gate on an agent's inference. First
uses: recall (item 4); the model and thinking level for a ticket (item 5); the spin signal from meaning (an
agent's last steps repeating, proven on the four looping tickets); autostart ranking. Not the question form.

## 7. Prompts: one database, served everywhere

**Decided.** A chassis function, not a module.
- Every prompt is served from the prompt database through `prompt_files`, so all 41 call sites get it with no
  change. A module's `resources/prompts.xml` is the seed: `shipped()` records it the first time it is served and
  ships a changed text again only if nobody edited since. An edit in the review is a new version and is live at
  once in every process. When a module ships newer text over an edit, the review marks it and offers to take it.
- The purpose comment travels into the database as a column at seed time.
- `metaform prompts review` reads the database only.
- An optional write-back puts edits into the XML for git; the packets become that.
- The module template teaches it: prompts in `resources/prompts.xml` with a purpose comment, served from the
  database, never in code.
- Why: prompts are how this system enforces anything; a bad one spread over eleven files costs hours; one place,
  editable, live, is the fix. Enforcement is by prompt, never by gate.

## 8. The resident process

**Decided in direction, not scheduled.** One always-on process holds the one graph and drives agents over ACP;
MCP servers, runners and the CLI become its clients; the web GUI a window onto it. This is PAMI's home. Item 2
with one projection instead of many. Not before items 1 to 5.

## 9. Visibility

**Decided.** One status read, CLI and GUI, of everything that accumulates: worktrees with work not in `chassis`,
uncommitted trees, open questions by age, sessions per ticket per hour, prompt edits not applied, failing tests.
Every hour lost on 2026-10-06 was spent discovering a number that should have been on the screen.

## 10. Plugin, not module

**Decided.** Rename `module` to `plugin` everywhere: the `Module` class, the `modules/` folder, CLI verbs, MCP tool
names, the map element, specs, docs. About 5,600 lines in 253 files. Stored column names (`module_id`,
`module_state`) keep their names; old CLI spellings accepted as aliases for a release. Done on its own branch,
after items 1 to 5, since it touches every file they touch. Not reviewed by ultrareview: mechanical.

## 11. A green baseline

**Decided.** `main` passes its whole suite. A failing test is fixed or marked expected-to-fail with its ticket.
12 tests fail today as the accepted normal; that ends with item 2's upgrade, which touches most of them.

## 12. Housekeeping, needs the owner

- Old worktrees: 11 fully in `chassis` (removable), `a3b492c` (2 commits, superseded by `c100c06`),
  `intake-base039-revert` (4 uncommitted edits, nowhere else), two old-line trees. Remove with approval.
- `git prune` and `.git/gc.log`: unreachable objects, cleanup disabled until done.
- 33 orphaned MCP server processes from dead sessions; `pkill -f "metaform mcp serve"`.
- The Board's Distribute control is missing from the page while VIEW-040 and two tests expect it: intentional or
  regression.
- The 35 consensus messages of 2026-10-05: mark read or keep.
- Nothing is pushed since 2026-10-04; a push of `main` to a private branch is overdue.
- The third free ultrareview: hold for a finished feature branch, item 2 or 4, at the owner's call.

## Order

1 and 2 together (one upgrade), 3 with them; then 5; then 4 and 6 together; then 7; then 10; 9 whenever a day
has room; 8 when 1 to 5 are stable. 11 is a rule from item 2 onward. 12 as the owner answers.
