# Target architecture

Date: 2026-10-20. Code: `797a523b` on `main`, plus the card-keying edits to `web/page/app/board/board.js`, `board/refs.js`, `core/dom.js` and `live/ops.js`, read uncommitted and committed during the write as `bc5bd3a5` ("Board: a move or a map op no longer makes every card again; 400 of 500 cards rebuilt per move, now 0"). Line numbers in those files are as at `bc5bd3a5`. Nothing in this design depends on that commit. Earlier draft included live-store readings at 2026-10-20T01:53Z. This completion uses named historical review measurements instead of presenting those readings as fresh proof.

Written by a helper agent for the system agent, on no ticket. Design proposal for the owner's review. No code changed.

## Completion scope and evidence

This completes the existing draft. It does not approve product decisions. The PM takes decisions M1 to M9 to the owner. No ticket or runtime setting changes belong to this assignment.

1. Project effect: replace fragmented plans with one proposed design. Preserve existing product behavior until each repair proves its result.
2. Benefit: responsive views, committed reads, fewer paid sessions, durable scoped memory.
3. Existing rationale: WAL, shared transactions, recovery outboxes and specialist publication solve real consistency or recovery problems. Remove their demonstrated costs without losing those protections.
4. Action: stop automatic role-creation fan-out first. Repair read isolation before removing locks. Shape reads before adding processes. Measure completed work rather than agents started.

The review baseline is `797a523b`, with board keying at `bc5bd3a5`. The working tree contains unrelated, ongoing repairs. Historical file lines and Built labels below refer to that baseline. They do not describe every uncommitted repair. [R] means historical source or measurement in a cited review. Historical timings, payload sizes, database counts and costs were checked against their source reports, not rerun as current measurements. Proposed limits are acceptance targets, not achieved results.

Fresh source verification: `src/metaform/modules/orchestration/routing.py:_route` calls `SERVICE.claim(... create=True)` when no role is selected. With Jev unavailable, that branch requires no classification result. `state.py:Orchestration.request_role` shares an existing creator only when `name` is nonempty. Thus unnamed tickets create separate role-authoring sessions. Graph lookup and exact-path coverage matched generation `2026-10-20T02:46:38Z`; direct source reads confirmed both branches. This establishes the mechanism, not a new live session count.

Cost-first priority: D5's automatic Facilitator path, then D1's read isolation and waiting locks, D3's failed controls, D6's oversized view reads, D2's CLI subprocesses, D4's lifecycle duplication, D7/D8's memory and delivery amplification, D9/D10's repeated discovery and accounting gaps, D11's stale records. Defect identifiers remain stable for existing references.

## How to read this

- **Test applied.** Does the product work for the person: fast, reliable, cheap in tokens, doing what it is for. Specification records are evidence of intent only.
- **Newer wins.** CLAUDE.md as it reads now, the commits of 2026-10-19 and 20 (`17983a5f`, `59195de7`, `c0209306`, `d0985e90`, `222ca950`, `e50dc6d9`, `a0f67e19`, `5a6d9f61`), and the cost audit outrank older records.
- **The cost audit.** The brief names `docs/reviews/2026-10-19-api-cost-and-token-waste-audit.md`. No such file exists. The audit is `docs/reviews/2026-10-19-token-waste-analysis.md` ("API cost and token waste audit; 2026-10-19", commit `e00f582a`).
- **Inputs.** Five area reviews and six later audits, all in `docs/architecture/`:

  | Short name | File | Code reviewed |
  |---|---|---|
  | A1 | `2026-10-20-map-layers-store.md` | `e50dc6d9` |
  | A2 | `2026-10-20-mcp-server.md` | `e50dc6d9` |
  | A3 | `2026-10-20-dispatch-orchestration.md` | `fb39f10f` |
  | A4 | `2026-10-20-memory.md` | `ed44563e` |
  | A5 | `2026-10-20-web.md` | `fb39f10f` |
  | AS, AW, AD, AM, AP, AQ | `2026-10-20-audit-store.md`, `2026-10-20-audit-web.md`, `2026-10-20-audit-dispatch.md`, `2026-10-20-audit-mcp.md`, `2026-10-20-audit-prompts-context.md`, `2026-10-20-audit-quality-cruft.md` | `5a6d9f61` to `797a523b` |

- **Marks.** [R]: historical evidence checked against the named review or baseline source. [I]: inference requiring its proving check. Fresh verification is stated separately above.
- **Owner's words.** Only exact quotes, with transcript and timestamp. Transcripts are Claude Code session files in `~/.claude/projects/-home-rich-metaform/`. Abbreviations: `f9f108ee` = `f9f108ee-6be4-4f62-8526-be5ad54c8f0f.jsonl`, `627d03a9` = `627d03a9-d0b5-42d9-a578-f8697b3a1aa3.jsonl`, `37e756d2` = `37e756d2-12a8-4fe1-8367-6cbe13a6e68a.jsonl`. Commit subjects are quoted as commit text; the git author is the owner's account, which does not prove who wrote the words.

---

## 1. What the product must do

What the owner reports, in his words:
- "Half the time you click the buttons and they don't even do anything because everything's frozen. When you click anything, everything freezes up." (`f9f108ee`, 2026-10-20T01:10:55Z)
- "The board is so fucking slow you can barely use it." (`f9f108ee`, 2026-10-20T01:10:05Z)
- "somehow i burned up half of my fucking account" (`f9f108ee`, 2026-10-20T01:09:05Z)
- "Nothing I've asked to be done on them has been done. I keep asking for stuff. None of it gets done." (`f9f108ee`, 2026-10-20T01:08:18Z)
- "need the architecture figured out i need it proper before we do more on top of it we can't keep building on a bad foundation" (`f9f108ee`, 2026-10-20T01:13:00Z)
- "Don't these agents understand that the requirements are secondary to the functionality?" (`f9f108ee`, 2026-10-20T01:25:01Z)

From these, five working outcomes. Every part below serves one of them.

| # | Outcome | Measure |
|---|---|---|
| O1 | Every click answers at once, while agents write. | Click to painted change under 200 ms on the live project; no read waits on a write. |
| O2 | Every button works every time, restarts included. | Zero refusals of the person's own clicks after a server restart. |
| O3 | A ticket goes from filed to done by one agent, and stays done. | One session per ticket; no reopen by bookkeeping. |
| O4 | Each paid model call has a cause the person can see. | Dollars per verified completed ticket, from a per-call ledger. |
| O5 | An agent gets what it needs once, and nothing it does not. | Zero duplicate bytes per context epoch at the delivery boundary. |

---

## 2. Root defects, ranked across all areas

Ranked by how much each stops O1 to O5 for the person. Each cites its evidence.

### D1. One waiting write freezes every read in a process (O1)

- `sqlite.opened` takes the file's in-process `writer_lock` for reads too (`sqlite.py:160`) [R]. A write holds it while `BEGIN IMMEDIATE` waits up to `BUSY_SECONDS = 30` (`sqlite.py:27`; `data/session.py:220`) [R]. Every read also holds the projection lock (`session.py:268`) [R].
- Measured: a read waited 3.84 s behind a write that waited on another process; 0.003 s without it (A1 F1) [R]. Same effect at 0.503 s on a fresh file (AS STORE-A2) [R].
- The web server is threaded, so one click that writes holds every read of that base: board, map, panels (A1 F1) [R].
- Correctness defect on the same path: a concurrent reader can see a rolled-back write (AS STORE-A1, probe `reader_saw_rolled_back_type: True`) [R]. A COMMIT failure leaves the projection ahead of disk until the next consistency check (AS) [R].

### D2. Clicks wait on a new Python process (O1)

- `web/server.py` calls `cli_result`, `run_dispatch`, `metaform_cli` or `subprocess.run` at 22 call sites [R] (A5 counted 32 route handlers at `fb39f10f` by a different method [R]).
- Each start costs 0.70 to 0.78 s and 73 MB on an empty home before the verb runs (A5 F2) [R]. Start, Stop, Message, Cancel, settings and the Review notice pay it.
- An in-process path exists and is used by `dispatch autostart`: `module_verb` (`web/server.py:3707`) [R].

### D3. The person's write key dies with the server process (O2)

- Keys live only in server memory (`PAGE_KEYS = 64`, `web/server.py:106`; `self.page_keys`, `:442`) [R]. After any restart every route in `PERSONS_WRITES` (`:3538`) is refused [R], dispatch start included.
- It happened to the owner: "what the fuck is tyhis I cant start fucking tickets? /api/dispatch-start is the person's to do on the page itself, and this request carries no key this server gave a page it served." (`f9f108ee`, 2026-10-20T01:02:40Z)
- The page learns of a new server from the stream's `hello` but never asks for a key (A5 F1; AW W3) [R].
- `/api/save-prompt` is still in `PERSONS_WRITES` (`:3539`) [R], though `65b11ec5` removed that gate everywhere else (A5) [R].

### D4. One ticket runs through two state machines (O3)

- Dispatch (starter, gate, sessions) and orchestration (routing, transitions, assignments, teams, assessments, corrections) both hold ticket state. Orchestration's `Transport.launch` calls dispatch's admission (AD) [R], so there is one gate but two schedulers and two stop records.
- Start can answer `needs_specialist` (`dispatch/__init__.py:3171`) [R] even when routing has commissioned a Facilitator (AD) [R].
- A start on the person's word through the system agent does not clear the assignment's stop: `owner.reopen` runs only `if person_asks(ctx)` (`dispatch/__init__.py:3180-3181`) [R]; `returned()` then returns early on `held.get('stop')` (`orchestration/state.py:1048-1049`) [R]. The ticket can never finish through check-in (AD D1) [R].
- GC-era code remains: a `claim` with `create` uses `'gc'` as placeholder role (`orchestration/state.py:671`) [R]. The owner's direction: "we need to kill the gc role" (`627d03a9`, 2026-10-19T00:35:27Z).

### D5. Paid turns with no work behind them (O3, O4)

- **Record-on-finish turn.** `dispatch_record_on_finish` defaults to `'when-missing'` (`dispatch/__init__.py:406`) [R]; `record_prompt` (`runner.py:4745`) [R] decides from whether this session wrote memory. The cost audit lists it P1.
- **Assessment per delivery.** Each delivery queues an assessment ticket while fewer than `orchestration_reviews` exist (`state.py:1109`; default 1, `orchestration/__init__.py:27`) [R]. A3 F3 records 120 of 181 root tickets as functional-assessment tickets [R]. Root-ticket counts differ from all-ticket counts. One family cost $235.20 (cost audit) [R].
- **Completion wakes.** `board.finished` raises a signal for every finished ticket (`dispatch/board.py:116-126`) [R]; with no system agent running it can start one (cost audit) [R].
- **Facilitator per unnamed ticket** when the library has no fit (A3 F2) [R].
- **No budget check per paid call.** `turn()` (`runner.py:4465`) and `prompted()` (`:4516`) admit without a budget check (AD D2) [V for the lines, R for the gap].

### D6. Every reader gets whole records (O1, O5)

- Board: 870,424 bytes for 158 cards; 120,812 without `task`, `note`, `said`, `resolution` (A1 F4) [R]. `WorkRecord` building runs two queries per ticket (`map/storage.py:838`, `:848`) [R]. `as_json` runs `plain` again (`results.py:15-16`) [R].
- The board's Done column empties on any ticket event: `boardFromTickets` sets `B.tickets = boardTickets(S.tickets)` (`live/ops.js:311-314`) [R], and `S.tickets` holds open tickets only (`loading/load.js:75`, `open: true`) [R]. Measured 39 Done cards to 0 (A5 F3) [R].
- Chat re-reads its whole thread on each event (`dock/helpdesk.js:90`, `agents/asking.js:111` pass no cursor) [R]; dispatch already takes `since` (A5; AW W4) [R].

### D7. Memory became a re-read work log (O5, O4)

- Ticket flow writes memory: the record turns (D5), `work_record` in every brief, roundtable outcomes as memories (A4 defect 1) [R].
- Prompts still define memory as work history: `orient` "Record what happened in the work there as memory" (`memory/resources/prompts.xml:12`), `connect` (`:42`) [R]. The arrival line asks for an edit on every visit (`:21`) [R]. The shipped `instructions` (`:59`) [R] was replaced in `4f2966c8` (`git log -S`) [R].
- Every edit makes an entity new for every session: one entity has 130 receipts over 125 sessions and 24 versions (agents store, read-only) [R].
- Bookkeeping outlives memories: 0 entities, 6,736 withdrawal rows, 1,092 encounters in A4 defect 4’s historical store [R].
- Inheritance along the Address (CTX-024) is not built; reads match the exact key (A4 defect 5) [R].
- The owner on what memory is: "This is exactly fucking like that! Except for you have a fucking place to hang the fucking memories! That's all!" (`f9f108ee`, 2026-10-20T00:47:17Z), after asking about "the fucking standard memory server" (00:47:00Z).

### D8. Context reaches agents by many paths, some twice (O5)

- "Once" is kept in five ledgers with different keys and compaction rules; verb results use none (A2 F2) [R]. `TOLD` (`mcp/server.py:638`) and `_READ_ON` (`:1684`) never reset [R].
- A helper inherits its parent's `METAFORM_AUTHORED_ROLE`: the chassis scrub list `IDENTITY` (`harness.py:248`) omits it [R], and `links` falls back to the environment (`mcp/server.py:2031`) [R]. Cost: the 10,691-character triage block to every helper (A2 F6) [R]. Intake also gets triage (AP PROMPT-01) [R].
- A write returns storage rows: `orchestration_claim` returned 9,058 characters with the task six times (A2 F3) [R].
- Tools load per module: opening map lists 39,391 bytes for 38 tools (A2) [R].

### D9. Each call pays for checking change instead of hearing it (O1)

- Per store call: `_follow_enabled` (`data/store.py:84`) [R], a new connection, a schema parse, an extension check and a catch-up query: 1.38 ms inside a request, 7.4 ms outside (A1 F3) [R].
- MCP `listing()` rebuilds the surface once per tool: 38 ms per listing (A2 F4) [R]; 20 rebuilds for 19 tools (AM MCP-A2) [R].
- CLAUDE.md section 2 names this failure: "a handler that re-reads or recomputes everything on every event is polling triggered by events".

### D10. Cost per completed ticket is unknowable (O4)

- No per-invocation ledger links prompt components to usage (cost audit P0) [R]. No change can be shown cheaper.

### D11. The specification does not describe the product (all)

- 429 records in `specifications/01-map.md` to `11-context.md` [R]. Many describe a SQL store that was replaced by the op log (A1 section 0) [R]; CTX-020's body argues the definition it replaced (A4) [R]; agents' wording is stamped as the owner's (A4 attribution).
- The owner: "a coherent specification was never done properly from the beginning everything just kept taking notes out of context" (`f9f108ee`, 2026-10-20T01:25:45Z).

---

## 3. The design

### 3.1 Process layout

| Process | Holds | Never holds |
|---|---|---|
| Web request process | Static files; store reads and writes; module verbs in process through `module_verb`; the SSE stream; one timer heap on one thread; the agent starter (event-driven, cheap). | A child Python process for a click; log or file watchers. |
| Services process, under the watchdog | Each project's background watchers (autoticket log watchers; memory `watch` while it exists). | Anything a click waits on. |
| Runner, one per agent session | The ACP connection, turns, budget admission per paid call, the invocation ledger writes. | Ticket routing. |
| MCP server, one per agent session (stdio) or shared (HTTP) | The tool surface, cached per surface state; the chassis delivery ledger. | Other modules' policy tables. |
| Watchdog | Restarts the web process; holds the page-key secret in memory and passes it on its pipe. | Health polling. |

Cross-process change travels only on the existing relay of `map.changed` (BASE-053; `changes.note`). No new mechanism.

### 3.2 Store

- **One op log per base, one projection per process.** Kept as built (STORE-046).
- **Readers lock nothing.** A reader never takes `writer_lock` once the file exists; only creation and the switch to WAL do. A write builds its changes on a private next state and publishes it at commit with one reference swap; a rollback or failed COMMIT drops it. This fixes D1's freeze and the rollback race in one design.
- **Catch-up by event.** A listening process records the sequence its projection reached and reads the log only when `map.changed` names its base at a later sequence, after its own write, or after a relay reconnect (gap recovery). A read with nothing new opens no connection. Module enable and disable arrive as events. A CLI process keeps catch-up on open.
- **Placement.** Orchestration and legacy dispatch tables leave the base file for the project store. Tickets stay in the base file: rekey updates `work_links` through a store transaction (`map/storage.py:283`) [R], which keeps tickets consistent with the map when they share a file [I], and once reads open no connection, the schema-size cost (0.909 ms against 0.110 ms, A1 F2 [R]) no longer lands on reads. Tickets move only if a measurement after the lock fix shows write contention still hurts O1.
- **Snapshots.** Written outside the write transaction, newest only. Kept or deleted by a benchmark at three history sizes (A1 measured replay 179 ms against snapshot-plus-replay 335 ms on one copy [R]). Incremental vacuum on.
- **Base guard.** A knowledge write naming a finished base goes to a knowledge layer, with a notice naming it (CTX-001; A1 F5 probe [R]).
- **Scoped knowledge as built** (`c4f449fc`): CEL attached by `map knowledge op=link-context`; instruction items inherit toward the leaves, ordinary items stay local, joins never travel.

### 3.3 Data flow, store to page

1. **First draw:** each view makes one read shaped for what it shows.
   - Board cards: id, node, address, condition or kind, title or first line, column, position, glyph, agent, age, steps, steps done. Target under 150 KB for 158 cards.
   - Card detail and history: the ticket whole, by id.
   - Chat: lines past the last drawn `since`.
   - Agents key: session rows only.
2. **Changes:** `map.changed` carries `tables`, `work_ids`, `session_ids`, `kinds`, `seq` (CLAUDE.md section 2, Rule 1). A view applies only the ids named, by id, into the set it holds. One view never replaces another's set; the board keeps its Done window.
3. **Writes:** a write answers with the records it changed. The page applies them; the matching event draws nothing (Rule 3).
4. **Reads are store reads or module read verbs in process.** Steps and links for a page come in one query. A result is made plain once.

Snapshot and stream share a committed sequence. Establish stream delivery before taking the view snapshot, buffer newer events, then apply only revisions beyond that snapshot. A disconnect, missing sequence or overflow invalidates the affected view. Reconnect obtains authoritative scoped state before applying later events. Queues have bounds. Nonreplaceable control events retain order. A mutation response includes its revision or operation identity, so its matching event cannot redraw it twice or hide another writer’s update. Failed writes never emit committed change events. Busy writes have bounded waits and actionable responses.

### 3.4 The person's authority on the page

- The key's purpose stays: an agent cannot press the person's buttons by posting as the page.
- A page whose stream says `hello` from a new server gets a new key under the same check a page load has (`page_cookie`).
- Reconnect re-keying is the first fix. Persist keys across request-server replacements only if needed, through a watchdog-held secret. Watchdog replacement still uses re-keying. Never blindly replay a write whose outcome is unknown.
- A refusal the page can resolve itself is resolved, not shown.

### 3.5 Agent coordination at least cost

One ticket is one agent, filed to done. The path:

1. **Filed with its specialist.** The system agent writes the ticket and names the specialist. The owner: "we need to have the ticket writer write the specialist they need for each ticket thats you" (`627d03a9`, 2026-10-19T00:47:22Z). The system agent's job: "It's supposed to be managing the Kanban and writing tickets. That's it." (`37e756d2`, 2026-10-19T01:02:07Z)
2. **Missing specialist.** Missing role metadata never starts another agent. An unbound ticket runs its one worker under the existing implementer duty. That worker uses the ticket and functional context to do the work. Specialist authoring is separate, explicit library maintenance. Deduplicate it by a named specialty before any launch; never commission from each unnamed ticket. Publication may bind waiting tickets but never relaunch completed work. Commit `c0209306` supplies the earlier continuation intent, not proof that per-ticket creation is cheap.
3. **Start.** From the person, the system agent at the person's word, or Full Auto. All go through the one gate (`_admit`), kept as built. A start is never refused for want of a specialist: the ticket uses the existing implementer duty when no named specialist is available. Any start on the person's word clears that ticket's stop.
4. **Full Auto.** Off starts nothing by itself; the person's own starts still run. The owner: "Well, full auto off is supposed to not allow more to start. The existing ones should keep running. But more shouldn't start and I should be able to broadcast until everybody to stop or they should listen." (`37e756d2`, 2026-10-19T01:03:15Z)
5. **Work.** One runner session. First turn: hand-off, the role URL once, the memory prompt once, the node summary within `node_summary_bytes`. The rest on demand (`17983a5f`, "Keep agent messages brief and recover context on demand").
6. **Done.** The worker closes the ticket with resolution and evidence. The session ends. No record turn, no assessment ticket, no completion wake. Review, if the person asks for it, is one pass in the same ticket on a changed candidate that fixes what it finds.
7. **Stop.** One stop record per ticket, in dispatch beside the session, plus the halt for everything.
8. **Consent.** The person's standing choice holds. With `dispatch_prompts=approve-all`, reversible acts do not ask. The owner, on that setting: "yes that is my setting why do I need to give permission thats my question" (`f9f108ee`, 2026-10-20T01:00:03Z). A verb is the person's alone only when its act cannot be undone.
9. **Measure.** Every paid call is admitted against the budget right before it is sent and writes one invocation record: cause, recipient, ticket, epoch, component fingerprints and byte counts, usage, cost (cost audit section 1). Each finished ticket reports its sessions, calls and cost.

Orchestration keeps specialist lookup and explicit library publication. Dispatch owns admission, ownership, recovery and completion. Retain durable launch intents until an equivalent idempotent dispatch continuation proves recovery. Do not delete the outbox before proving restart safety.

### 3.6 Context delivery

- **Connect.** The directive and links to the blocks that apply; the agent reads each whole, once per context epoch. This is the current decision: `a0f67e19` "Connect directive back to its original wording: before you do anything else, read every resource linked below, whole". The owner, on the dropped qualifier: "Well, get rid of that. I didn't say applicable." (`f9f108ee`, 2026-10-20T01:30:13Z). Within it: a block links only the agent's own role, read from its own assignment, and no paragraph appears in two blocks.
- **One ledger.** One chassis ledger per session and epoch, keyed by content, used by every output path, tool results included, working with every optional module off. A body already given is a reference. A body is marked given only after delivery.
- **Retention proof.** Confirm a startup checkpoint on the first necessary turn with the retained key, when available. Missing proof permits one needed contextual read. It never triggers an automatic dump, a recovery turn or a search for the key. Explicit recovery remains possible when the host lost content.
- **Results.** A write returns what it changed and handles; a read returns the fields asked for; one encoding (text, with `structuredContent` only where a host is shown to read it instead).
- **Tools.** Every command its own typed tool. A host that loads tools on demand gets a stable sorted full list; another host gets a per-session list that only grows. No untyped `arguments` path. The listing is computed per surface change.
- **Ownership.** Restrictions and roles are declared by the module that owns them; the mcp module knows no module by name.

### 3.7 Memory = the standard MCP memory server + an Address

- **The graph is the reference's.** Entities `{name, entityType, observations}`, relations `{from, to, relationType}`, the nine tools with the reference's arguments and results.
- **The Address is one optional argument.** `node` on `create_entities`; `join`, `unjoin`, `rekey`, `orphaned`, `map_moved` keep memories hung where they apply.
- **Addressed reads.** At a node: memories hung there and at each prefix toward the trunk, one keyed read per prefix, filtered by layer reach; then only those entities' rows. Never the whole graph for a node read.
- **Delivery.** On arrival, one line with the count of applying memories this session has not been sent; nothing when zero. One record per (session, epoch, entity) is the proposal. Whether an edit makes an entity new again stays open (M3). Preserve existing receipts and deletion history until PM obtains that decision and migration checks pass.
- **No ticket ties.** The owner: "Tickets don't own memories. The memory prompt does. Tickets have nothing to do with memories." (`f9f108ee`, 2026-10-20T00:45:56Z). Agents create, update and delete: "agents are supposed to be deleting and updating memory" (`f9f108ee`, 2026-10-20T00:41:01Z). What a memory is: "It's supposed to be durable atomic memories that are valuable." (`f9f108ee`, 2026-10-20T00:53:59Z)
- **No added context.** The owner: "i'm not adding more context on top of context on top of context" (`f9f108ee`, 2026-10-20T00:53:23Z). Memory pushes nothing beyond the arrival count.
- **The prompt is the owner's.** The `instructions` element holds text the owner approves (section 5, decision M1).
- **Kept beyond the reference:** the lock (CTX-023), CLI only; the layer gate (LAYER-012).

### 3.8 The map's look

Labels stay batched and draw nearest over farthest across all atlas pages (A5 F5; AW W7). Facing, scaling, collapse default and join drawing are the owner's choice of look; four commits on 2026-10-17 changed them without one record. The owner: "The map and the labels look like absolute shit. They originally looked good. I don't know what happened." (`f9f108ee`, 2026-10-20T01:07:56Z)

---

## 4. What to delete

Each goes when its step in the remediation plan lands. Remove means delete, not switch off.

| Delete | Where | Defect |
|---|---|---|
| Read path's `writer_lock` on an existing file | `sqlite.py:160` | D1 |
| Projection lock held across reads | `data/session.py:268` | D1 |
| `cli_result`, `run_dispatch`, `metaform_cli` on every route a verb serves in process | `web/server.py:3472`, `:3498`, `:3570` | D2 |
| `PAGE_KEYS` and process-local `page_keys` | `web/server.py:106`, `:442` | D3 |
| `/api/save-prompt` in `PERSONS_WRITES` | `web/server.py:3539` | D3 |
| `needs_specialist` return from `start()` | `dispatch/__init__.py:3171` | D4 |
| GC machinery: `delegate`, `call`, `handoff`, teams, `gc_assignment_id` routing, `owned_gc`, GC broadcast, `'gc'` placeholder | `orchestration/state.py:671`, `dispatch/orchestration.py` | D4 |
| Orchestration's own stop state and second scheduler (`drain` as launcher) | `orchestration/state.py:1234` | D4 |
| Record-on-finish, -stop, -failure turns, settings, prompts; `record_prompt` | `dispatch/__init__.py:406`, `:434`, `:442`; `runner.py:4684`, `:4714`, `:4745`; `dispatch/resources/prompts.xml` | D5, D7 |
| `board.finished` as a wake | `dispatch/board.py:116` | D5 |
| `work_record` and the brief's `record` line; `memory.record` and roundtable outcome memories | per A4 delete table | D7 |
| `memory/delivery.py` and its three tables (`encounters`, `entry_revisions`, `withdrawals`) | 239 lines [R] | D7 |
| `read_unread` and the `refine` notice | `memory/resources/prompts.xml:21`, `:28` | D7 |
| Required `title`/`why`, the one-fact refusal, one-line MCP write results | per A4 | D7 |
| `boardFromTickets`'s replacement of the board's set; `renderBoard` after the board's own writes | `live/ops.js:311-314` | D6 |
| Second `plain` in `as_json` | `results.py:16` | D6 |
| `TOLD`, `_READ_ON`, `Given`, separate glossary keys, folded into one ledger | `mcp/server.py:638`, `:1684` | D8 |
| `RESTRICTED_STEERING_TOOLS`, `HELD_OPS`, `HELD_ARGUMENTS` | `mcp/catalog.py:22-35` | D8 |
| `agent.actions` provider | `mcp/__init__.py:180`, `:296`; `mcp/server.py:1293`. Baseline `git grep` finds the function and provider declaration; no shipped production consumer was found (AM MCP-A5) [R] | D8 |
| Per-call `loader.follow_enabled` | `data/store.py:84-86` | D9 |
| Per-request listing rebuild | `mcp/server.py:996` | D9 |
| Stale record text (SQL tables, query plans, wrong layout numbers, polling sentences) | `specifications/` | D11 |

Owner decisions before deleting: citations, `watch` and per-address numbering in memory (M9); VIEW-043 consensus mode (M7). PM routes these decisions. Unapproved deletion remains a draft recommendation.

---

## 5. Decisions only the owner can make

| # | Decision | Recommendation | Why |
|---|---|---|---|
| M1 | Text of the memory `instructions` element. CTX-026's 2026-10-17 amendment says the owner delivered a block; this review did not find that delivery in the transcripts searched. | PM obtains the approved text. | Agents must not write the owner's prompt. |
| M2 | CTX-021 (knowledge never in memory) against category d of CTX-026's 2026-10-17 block ("Knowledge (implementation details, …)"). | Owner rules. | The two cannot both hold (A4). |
| M3 | Whether an edited memory counts as new (CTX-041). | Not new. | 24 versions × 125 sessions came from "new" (D7). |
| M4 | Default `orchestration_reviews`. | 0; review only when the person asks, one pass in the same ticket. | A3’s review-ticket concentration; "one ticket = one agent". |
| M5 | Map look: label facing and scale, `web_map_depth` default, join purpose vertex. | Side-by-side screenshots, then pick. | Four commits changed it without a record. |
| M6 | Whether tickets ever move out of the base file. | No, unless measured contention after D1's fix. | Atomic rekey of `work_links`. |
| M7 | Consensus mode (VIEW-043). | Withdraw. | Never built; nothing newer asks for it. |
| M8 | Saved boards. The owner: "I just wish you could save and restore boards, you know, clear the board, save it as a name, start a new board, bring back the old board once the problem's fixed." (`f9f108ee`, 2026-10-20T01:20:49Z) | Build after the board reads by card fields. | It is a request, not yet a decision on shape. |

| M9 | Memory citations, `watch` and per-address numbering. | Remove only after PM obtains the owner’s decision and existing references have a migration path. | Reference compatibility alone does not authorize losing existing data or handles. |

## Verification and limits

- Final document checks passed: 21 commit references resolved, 28 distinct directly cited transcript excerpts matched, 429 source records matched 429 mapping rows. Verdict totals: 157 kept, 191 carried, 70 refined, 11 proposed dropped. Carried records remain unassessed. Dropped records remain proposals until approval. Markdown code fences balanced. `git diff --cached --check` passed. No runtime test result is claimed.
- `git rev-parse --verify <id>^{commit}` resolved every cited commit. The three priority commits resolve to `17983a5faf1bb619233e17b7232a5da3bade92b9`, `59195de7ee208d3d2b60c00e9a51492dc8be65d9`, `c02093060711c692cd859cfd6bb0226b3374ab38`. Commit subjects are commit text. Authorship does not establish whose words they contain.
- Targeted reads checked each quoted user message at its cited transcript timestamp. Ellipses added by the earlier draft were removed from excerpts. Transcript identifiers are source references, not commit IDs. No retention key was recovered from logs.
- `git show 797a523b:src/metaform/modules/memory/delivery.py | wc -l` returned 239. The baseline web subprocess-pattern count returned 22. `git grep -n agent.actions 797a523b -- src` found its function and provider declaration. No shipped production consumer was found by the MCP audit; supported external consumers remain an explicit removal check.
- Specification headings and mapping rows both total 429. Counts per source: MAP 40, LAYER 29, STORE 46, BASE 64, CLI 42, MCP 42, QUAL 17, PROJ 29, VIEW 51, WORLD 13, CTX 56. `04-chassis-modules.md` also contains one MCP record. Mapping coverage uses record identity, not filename prefix.
- Cited repository paths were checked against the baseline tree or current files. Short source names resolve within their named module. `freeze.py` and `probe2.py` name historical temporary probes, not maintained repository commands. Recreate their stated fixtures if those files no longer exist. The audit path supplied in the brief is absent; the verified substitute is identified above.
- Read-only document verification establishes evidence consistency. It does not prove runtime repairs, current production counts, real GPU behavior or achieved cost reductions.
