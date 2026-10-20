# Remediation plan

Date: 2026-10-20. Code: `797a523b`, and `bc5bd3a5` for the board files. Companion to `2026-10-20-target-architecture.md` (the design, defects D1 to D11, owner decisions M1 to M9). Review short names (A1 to A5, AS, AW, AD, AM, AP, AQ) and evidence marks are as defined there.

Proposal for the owner's review. No code changed. Historical evidence uses the target document’s baseline. Current working-tree repairs require rechecking before implementation. PM routes unresolved owner decisions.

## Rules for every step

- One step lands alone, with its check, before the next that depends on it. Steps marked *independent* can run in parallel, each as one ticket worked by one agent.
- Tests protect changed behavior and adjacent contracts. Start with focused checks (`uv run pytest -n 0 <file> -k <name>`). Run required checks. Broaden only for unresolved risk or failures.
- Event-path steps carry CLAUDE.md section 2 Rule 5: 60 s idle CPU before and after, and a burst of events that do not concern the handler causing zero reads.
- Delete means delete. Each removal's commit names what went and why (QUAL-017).
- A spec record changes after its code lands, by the Design Authority role, never by the builder.

## Conflicts between reviews, resolved

| # | Conflict | Resolution | Why |
|---|---|---|---|
| C1 | A1 F2 moves tickets, dispatch and orchestration out of the base file. AS says a split needs a stated atomicity contract, not a default. | Move orchestration and legacy dispatch tables to the project store (they share no transaction with the map). Keep tickets in the base file (owner decision M6). | Rekey updates `work_links` through a store transaction (`map/storage.py:283`) [R]; that it shares the map write's transaction is [I], to confirm before any move. Once reads open no connection (step 16), schema size no longer costs reads. |
| C2 | A1 F1 wants an immutable projection swapped at commit. AS says fix rollback isolation first and measure copying cost before immutability. | Step 1 fixes rollback isolation with the current locks. Step 15 moves to publish-at-commit only after measuring copy cost on the live-size base. | Correctness first; the swap design also closes the race, but its cost is unmeasured. |
| C3 | A1 F6 deletes snapshots (replay 179 ms against 335 ms). AS says do not delete on one benchmark; bound retention. | Step 26: write outside the transaction, newest only, then benchmark three history sizes and decide. | One copy is one data point; taking the write lock to snapshot is wrong either way. |
| C4 | A3 calls orchestration a second launcher to delete. AD shows `Transport.launch` uses dispatch's admission, and the transition outbox has recovery value. | One gate exists already. Delete the GC machinery and orchestration's own stop state. Keep durable launch intents until dispatch demonstrates equivalent deduplication and restart recovery. Remove automatic per-ticket role creation first (step R0). | GC removal does not prove the outbox redundant. Recovery must survive removal; the gate stays. |
| C5 | A3 says every delivery queues an assessment. AD shows the bound `len(reviews) < orchestration_reviews`, default 1. | Both true: one assessment ticket per delivery by default (`state.py:1109`, `orchestration/__init__.py:27`) [R]. Step 9 sets the default to 0 (owner decision M4). | A3 F3 records 120 review tickets among 181 root tickets [R]; one ticket is one agent. |
| C6 | A2 calls `agent.actions` dead code. AM MCP-A5 establishes no shipped production consumer, leaving external contracts open. | Baseline `git grep` finds its function and provider declaration (`mcp/__init__.py:180`, `:296`); no shipped production consumer [R]. Step 19 removes it only after checking supported external consumers and passing catalog checks. | No shipped production consumer found; external contracts need verification before removal. |
| C7 | A1 F5 says scoped knowledge replaced CTX-004/006/007. A4 says CTX-024 inheritance for memory is unbuilt. AS declines to choose inheritance. | Knowledge: scoped as built (`c4f449fc`). Memory: build CTX-024 (confirmed 2026-10-15 per its status line) on keyed reads (step 17). | Different record kinds. CTX-024's status is the record's; the Address is the scope Metaform adds to the reference server. |
| C8 | A5 R4 claims every card is rebuilt. AW notes keyed cards (then uncommitted) preserve unchanged nodes. | Both held at their commits: `bc5bd3a5` now keys cards (its subject: 400 of 500 cards rebuilt per move, now 0). Step 14 measures from `bc5bd3a5`; whole-record reads and the whole-record card signature remain. | The tree changed under A5's measurement. |
| C9 | A2 F2 wants one ledger in the chassis. Cost audit section 2 names `agents/roles.py` as shared receipt owner. | Move the `agents/roles.py` ledger into the chassis beside `shown.py` (step 19). | Both agree on one ledger; the chassis copy works with `agents` disabled (`module.py:1320-1329`, A2) [R]. |
| C10 | VIEW-039 runs dispatch as a CLI process so the person's environment reaches the agent. A5 wants verbs in process. | Verbs in process; only the runner is a process, started with the person's environment (step 13). | The record's reasons hold in process; the process start costs 0.70 s per click (A5) [R]. |

## Ordered steps

**R0. Missing expertise starts no extra agent (D5).** First implementation step.
- Change: remove `_route`’s automatic `SERVICE.claim(... create=True)` fallback. Preserve named specialist selection. If no valid specialist is bound, start the ticket once under the existing implementer duty. Jev unavailable is an ordinary fallback condition. Deduplicate any explicitly requested library authoring by specialty before admission.
- Check: fake ACP adapter, Jev off, empty library, several admitted tickets. Each gets one worker session, zero role-creator sessions, no `needs_specialist` refusal. Hold one ticket, exhaust capacity, restart runner -> held/capacity policies persist; each remaining launch occurs once. One representative real ticket then goes filed -> done in one session. Count calls and cost when ledger exists.
- Deletes: per-ticket creator commissions from unnamed routing, not the reusable role library or explicit authoring capability.


R0 stops automatic session multiplication. Phase 1 repairs clicks. Phase 2 stops paid work with no cause. Phase 3 makes reads proportional. Phase 4 cleans delivery and memory. Phase 5 removes what is left.

### Phase 0: the gate builders stand on

**0. CI lint passes.** *Independent.*
- Change: fix the tracked Ruff errors: `map/storage.py:610` (FURB192), `web/tests/test_zz_diag_tmp.py` (F811, SIM115), the archived `page_smoke.py` under `web/page/app/.claude/skills/.archive/` (AQ QUALITY-001) [R].
- Check: `uv run ruff check src tests conftest.py` exits 0 on a clean tracked checkout.
- Deletes: the temporary diagnostic test if it has no maintained purpose.

### Phase 1: clicks answer, buttons work

**1. Rollback cannot leak into a read (D1).**
- Change: projection lookup, freshness check and read lease are atomic against writers; rollback and a failed COMMIT invalidate any projection a started reader holds (AS STORE-A1).
- Check: AS's scheduled-reader probe through the real opener prints `reader_saw_rolled_back_type: False`, also with an injected COMMIT failure.
- Deletes: nothing.

**2. Readers stop taking the writer lock (D1).** After step 1.
- Change: `sqlite.opened` takes `writer_lock` for a reader only to create a file or switch it to WAL (`sqlite.py:160`).
- Check: A1's `freeze.py`: the read during a waiting in-process write takes under 50 ms (was 3.84 s). STORE-006's concurrency tests pass alone.
- Deletes: the read path's acquisition of `writer_lock` on an existing file.

**3. The page re-keys after a restart (D3).** *Independent.*
- Change: `GET /api/page-key` under `page_cookie`'s check; the page calls it when the stream's `hello` comes from a new process, and re-keys and retries once on the no-key 403.
- Check: test server, open page, `metaform web stop`, `metaform web`, click Move to top: 200, card moves, no reload (was 403, A5) [R]. An agent process still gets 403.
- Deletes: nothing yet (step 21 replaces process-local keys).

**4. `/api/save-prompt` leaves `PERSONS_WRITES` (D3).** *Independent.*
- Change: remove it from `web/server.py:3539`, as `65b11ec5` did on every other surface.
- Check: an agent's POST to `/api/save-prompt` succeeds in a test home.
- Deletes: that gate.

**5. The board keeps its Done column (D6).** *Independent.*
- Change: `boardFromTickets` merges named tickets into `B.tickets` by id under the board's own Done cutoff.
- Check: A5's `probe2.py` prints Done `[39]` across one ticket event (was `[0]`); AW W2's Node probe keeps the Done id.
- Deletes: the replacement `B.tickets = boardTickets(S.tickets)` (`live/ops.js:313`).

**6. A start is never refused for want of a specialist; the person's word clears the stop (D4).** *Independent.*
- Change: `start()` drops `owner.route` and the `needs_specialist` return (`dispatch/__init__.py:3171`); an unbound ticket uses the existing implementer duty (R0). Reopen when `person_asks(ctx)` or the start carries the person's word (`:3180`).
- Check: fake-adapter test in `dispatch/tests/test_direct_runtime.py`: orchestration on, Jev off, empty library: `dispatch_start` never answers `needs_specialist`, and one worker launches without waiting for role publication. AD D1's acceptance: a stopped ticket restarted on the person's word clears its own stop and check-in finishes it.
- Deletes: routing on the start path.

**7. Each agent is pointed at its own role (D8).** *Independent.*
- Change: add `METAFORM_AUTHORED_ROLE` to `IDENTITY` (`harness.py:248`); `links` reads the role from the session's own assignment only (`mcp/server.py:2031`); intake gets no triage role (AP PROMPT-01).
- Check: AM MCP-A1's acceptance: a helper connects with `metaform://role/helper` linked and no other; an intake through the fake adapter receives no triage duties; the system agent still receives triage.
- Deletes: the environment fallback for the authored role.

### Phase 2: no paid work without a cause

**8. No turn after done, and no ticket flow writes memory (D5, D7).** *Independent.*
- Change: delete the record-on-finish, -stop and -failure turns, their settings and prompts, `record_prompt`, `work_record`, the brief's `record` line, `memory.record` and roundtable outcome memories (A4 steps 1 and 2).
- Check: fake agent closes its ticket having written no memory; zero prompts after `done`. `grep -rn "dispatch_record_on_\|on_ticket_done\|work_record" src/metaform` is empty. A finished roundtable leaves the memory entity count unchanged.
- Deletes: `dispatch/__init__.py:406-446` settings; `runner.py:4684-4773` turns and `record_prompt`; prompts in `dispatch/resources/prompts.xml`; `roundtables/follow.py` outcome memory.

**9. Review is opt-in, one pass, same ticket (D5).** Needs M4.
- Change: `orchestration_reviews` default 0. When the person sets it above 0, the review runs as one pass in the same ticket on a changed candidate, fixes what it finds, files a ticket only for what it cannot fix, and never reopens a done ticket.
- Check: deliver a ticket with the default: no assessment assignment created. With 1: at most one pass, in the same ticket; an unchanged candidate starts nothing.
- Deletes: the reopen-from-done in `_correction` (`orchestration/state.py`).

**10. Completions do not wake anyone (D5).** *Independent.*
- Change: `board.finished` raises only for a ticket linked to an open fault.
- Check: no system agent running, Full Auto on: finishing an unrelated ticket starts no session (the cost audit's extra-triage-session test).
- Deletes: the unconditional `raised` in `dispatch/board.py:116-126`.

**11. Every paid call is admitted and recorded (D5, D10).** *Independent.*
- Change: one admission check right before each ACP send (`runner.py:4516` `prompted`), with fresh shared totals; one invocation record per call (cost audit section 1 fields). Fork usage reaches `spend`.
- Check: AD D2's acceptance (budget exhausted elsewhere: queued continuation makes zero ACP calls). Cost audit section 1 acceptance: success, interrupt, failure, resume and fork each write exactly one record; a per-ticket view gives dollars per completed ticket.
- Deletes: nothing.

**12. One real run as a baseline (O3, O4).** After R0 and steps 6, 8, 10, 11.
- Change: none. One small code ticket, named existing specialist, started by the person with Full Auto off.
- Check: ticket done; `dispatch_sessions` shows one session; the ledger gives its calls and cost. Recorded in this file.
- Deletes: nothing.

### Phase 3: reads cost what they answer

**13. Clicks run in the server's process (D2).**
- Change: dispatch, settings and merge routes call `module_verb` (`web/server.py:3707`); the vouch travels as request context (C10).
- Check: `strace -f -e trace=execve -p <server pid>` while each control is pressed shows no `python` exec; each answers under 200 ms on the test home (was at least 0.70 s).
- Deletes: `cli_result`, `run_dispatch`, `metaform_cli` (`:3472`, `:3498`, `:3570`) wherever a verb serves the route.

**14. Views read what they show (D6).**
- Change: board read by card fields; steps and links in one query per page; `as_json` drops its second `plain`; writes (`/api/move`, `/api/ticket`, `/api/eligible`, `/api/distribute`) answer with changed records; chat reads past `since` (forwarded through `Handler.dispatch_sessions`, AW W4); agents key reads session rows.
- Check: A1's `board.py`: ≤ 150 KB and ≤ 10 ms for 158 cards; SQL count per board read constant in card count (AS STORE-A6). A Top click: one `POST /api/move`, no board re-read. Ten chat line events on a 2,000-line thread total under 50 KB.
- Deletes: `results.py:16` second `plain`; `renderBoard` after the board's own writes.

**15. Projection published at commit (D1).** After steps 1 and 2.
- Change: measure copy cost of the live-size state first. If acceptable, writes build a private next state and swap it in at commit; reads hold no lock.
- Check: a write held open 2 s in one thread; a read in another returns the pre-write state in under 50 ms. STORE-046's determinism test passes.
- Deletes: the projection lock across reads (`session.py:268`).

**16. Catch-up and module state by event (D9).** After step 15.
- Change: listening processes catch up on `map.changed` past their sequence, after their own write, or after relay reconnect. Module enable and disable arrive as events. MCP listing is cached per surface state and invalidated by the events that change it.
- Check: 1,000 reads with no change issue 0 SQL statements (`set_trace_callback`). A burst of 100 `map.changed` for another base causes 0 log reads. A dropped relay and a write during reconnect converge before the next authoritative read. A burst of 100 `tools/call` with no surface change causes 0 surface rebuilds. Idle CPU over 60 s before and after.
- Deletes: per-call `loader.follow_enabled` (`data/store.py:84-86`); `extensions_ready` on the read path; per-request listing rebuild.

### Phase 4: context once, memory as designed

**17. Memory: keyed reads, scoped delivery, inheritance (D7).** Parts b/c proceed independently. Destructive bookkeeping migration waits for M3.
- Change, in three commits: (a) preserve the current bookkeeping until M3 is decided; then replace it on a backed-up copy with the approved receipt rule, verifying unread/deletion behavior before dropping old tables; (b) node reads, counts and writes read the joins at the key, then those entities only; (c) reads at a node include each prefix toward the trunk (CTX-024).
- Check: (a) 50 edits by session B at `code.x` cause zero memory reads for session A arriving at `code.y`; the upgraded copy holds no withdrawal rows (live: 6,736 [R]). (b) A node read on a 1,000-entity graph touches only its entity's rows. (c) CTX-024 acceptance: a memory at `code.store` reads at `code.store.memory`, absent at `code.graph`.
- Deletes: `memory/delivery.py`; `read_unread`; the `refine` notice; `memory.revision`.

**18. Memory prompts and surface (D7).** Needs M1 and M2.
- Change: `instructions` holds the owner's approved text; `orient` and `connect` drop "what happened in the work"; `counts` names the count only. Writes return the reference's results; `title`/`why` and the one-fact refusal go.
- Check: a test compares shipped `instructions` byte for byte with the approved text; no shipped `prompts.xml` contains "what happened in the work" or "merge repeats and remove". A conformance test replays the reference's tool calls with no node and compares results field for field.
- Deletes: the requirements and one-line results listed in A4's delete table. Citations, `watch` and numbering only if the owner says so.

**19. One delivery ledger; declared results (D8).** Keep public provider compatibility until external consumers are checked.
- Change: move the fingerprint ledger from `agents/roles.py` into the chassis (C9); route `TOLD`, `_READ_ON`, `Given` and the guide keys through it; tool results pass through it. `orchestration claim`, `delegate`, `inspect` return changed state and handles.
- Check: in one session the glossary read as resource, instructions and `map_glossary` delivers its body once, and once more after `compacted=true`; same with `agents` disabled. A missing retention proof enables one required contextual read, never a dump or extra turn. `orchestration_claim` result under 1 KB, task once, no `role_snapshot`.
- Deletes: `TOLD` (`mcp/server.py:638`), `_READ_ON` (`:1684`), `Given`; `agent.actions` (`mcp/__init__.py:180`, `:296`; `server.py:1293`) (C6).

**20. Trace the host, then set tool loading (D8).**
- Change: capture Claude Code request bodies headless for a scripted session. Answer: does `structuredContent` reach the model beside `content`; does `tools/list_changed` rewrite the cache; what does a stable full list cost with tool search on. Then: stable list for deferring hosts, growing list otherwise, no untyped path.
- Check: the three numbers recorded in A2's file; tool-definition bytes for the session below 39,391; a typed call over unkeyed HTTP succeeds.
- Deletes: module-replacing selection and its bookkeeping (`mcp/server.py:1321-1345`); the second result encoding if both reach the model.

### Phase 5: remove what the direction retired

**21. Optional key persistence (D3).** After step 3, only if reconnect re-keying fails its acceptance check.
- Change: if needed, keys use an HMAC secret held by the watchdog and passed through its pipe. Keep step 3 as recovery after watchdog replacement.
- Check: request-server replacement under the same watchdog keeps authority. Watchdog replacement recovers through step 3. Restarting both must not authorize an agent. Retry only a write proven rejected before mutation; ambiguous failures reread authoritative state.
- Deletes: `PAGE_KEYS`, process-local `page_keys` (`web/server.py:106`, `:442`).

**22. GC machinery and duplicate lifecycle state go (D4).** After R0 and step 12. Split removal and table migration into separate commits.
- Change: delete `delegate`, `call`, `handoff`, teams, `gc_assignment_id` routing, `owned_gc`, the GC broadcast and the `'gc'` placeholder; explicit role-publication continuations use idempotent dispatch starts after restart proof (C4); remaining orchestration tables move to the project store with an upgrade that backs up first (C1).
- Check: step 12's run repeated: one session, same or lower cost. `grep -rn "def delegate\|owned_gc\|'gc'" src/metaform/modules/orchestration` finds nothing. Base file's `sqlite_master` holds no `orchestration.*`; row counts equal before and after.
- Deletes: listed GC paths and orchestration's duplicate stop state. Delete the old outbox only after a crash between durable intent and launch, plus a crash after launch before acknowledgment, each recovers exactly once. Preserve historical rows readably. Raise compatibility only when required; prove backup restoration on a copy.

**23. Background watchers leave the request process (D2).** *Independent.*
- Change: measure watcher interference after bounded reads and in-process verbs. Move watchers to one existing supervised service process only if interference remains. Consolidate per-merge deadline timers into one owned scheduler. No new process per module.
- Check: `ls /proc/<pid>/task | wc -l` equal with 20 merges waiting and none; `py-spy dump` shows no watcher thread in the web server.
- Deletes: per-merge `threading.Timer` threads.

**24. Stream and pipe stay bounded.** *Independent.*
- Change: dispatch batching flushes on deadline after a successful dequeue too (AW W1); per-page pending events bounded with coalescing or overflow re-read (AW W6); ACP writes await `drain()` with byte bounds (AD D3).
- Check: AW W1's fake-clock saturated queue emits within the window; a paused consumer has bounded pending state; initial-load writes, sequence gaps and overflow converge by scoped reread; AD D3's stalled sink shows bounded bytes and preserved order.
- Deletes: nothing.

**25. Base guard (CTX-001).** *Independent.*
- Change: `writes.add_element` and `add_property` route a write naming a finished base to a knowledge layer with a notice.
- Check: A1's scratch-home probe returns a notice naming the knowledge layer; the base is unchanged.
- Deletes: nothing.

**26. Snapshots out of the write transaction (C3).** *Independent.*
- Change: write outside the transaction, newest only; benchmark cold open at three history sizes; incremental vacuum on.
- Check: cold open ≤ full replay at each size, or snapshots deleted; file size within 10% of pages in use.
- Deletes: older snapshots; snapshot writing inside the write transaction (`session.py:227`).

**27. Labels in depth order; no allocation per frame.** Needs M5 for the look.
- Change: label instances drawn nearest over farthest across atlas pages (AW W7); `warm3d` compares preallocated flags before building a key (AW W8).
- Check: two-page overlap scene shows near over far from both sides; `renderer.info.render.calls` within 2 of before; real-GPU frame time median, p95, p99 before and after (warn the owner first: probes share his GPU).
- Deletes: the per-frame closure and string in `warm3d` (`map3d/graph3d.js:283`, called each frame at `:384`).

**28. MCP knows no module by name (D8).**
- Change: `Verb` declares restrictions and held ops; roles and assignment reads move behind the owning module's provider; `modules/template` and its CHANGELOG get the new contract.
- Check: `grep -n "dispatch_\|map_work\|agents_" src/metaform/modules/mcp/catalog.py` finds nothing; a synthetic module's steering verb is withheld from a role without authority with no mcp edit.
- Deletes: `RESTRICTED_STEERING_TOOLS`, `HELD_OPS`, `HELD_ARGUMENTS` (`mcp/catalog.py:22-35`).

**29. The specification follows the code.** After each step.
- Change: the Design Authority applies `specifications/DRAFT-2026-10-20-coherent-spec.md` record by record as code lands, with date, process and ticket; corrects CLAUDE.md's connect-message sentence and `docs/reference/metaform-mcp-server.md`.
- Check: every `file:line` a record cites exists; every acceptance test it names exists; no record names a `current_*` table or a query plan.
- Deletes: overtaken record text.

## Remaining verified boundaries

**30. Isolate required peer polling (AM MCP-A4).**
- Change: keep stream-first A2A. Put upstream-required polling in one owned worker thread. Relay results through the existing bus.
- Check: fake nonstreaming peer executes refresh off the HTTP loop; streaming peers use no poll timer; cancellation joins the worker. Record idle CPU and unrelated-event reads.
- Deletes: fallback polling tasks on the HTTP engine loop.

**31. Bound upgrade fingerprint work (AM MCP-A6).**
- Change: exclude immutable bundled dependency trees from source scans. Retain package identity for dependency replacement.
- Check: installed only-MCP wheel performs no per-file stats under `_vendor`; source edits and package replacement still cause one safe handover with no replayed mutation.
- Deletes: dependency-tree scans on each eligible tool call.

**32. Isolate fork checks (AQ QUALITY-002).**
- Change: run checks and wheel assembly in temporary interpreter environments. Keep home isolation.
- Check: conflicting candidate dependencies produce order-independent outcomes; caller package inventory stays unchanged; success/failure clean up environments.
- Deletes: installs into the running interpreter.

**33. Preserve scaffold parity (AQ QUALITY-003).**
- Change: produce the packaged fallback from canonical template files, with explicit packaging differences.
- Check: a fork-only wheel scaffolds the current public contract, served-prompt guidance and changelog.
- Deletes: independently maintained stale fallback copies once generation proves parity. Preserve instruction files.

**34. Bound startup reference data (AP PROMPT-02/03).**
- Change: send complete applicable instructions once. Send counts/handles for structural knowledge. Keep onboarding subordinate to the active request; browser failure leaves CLI work available.
- Check: adding unrelated knowledge does not grow startup proportionally; required instructions remain complete; onboarding cannot preempt an authorized unrelated task.
- Deletes: full structural subtree injection and onboarding preemption wording.

## Dependency summary

- R0 first. Independent document-defined repairs: 0, 3, 4, 5, 6, 7, 8, 10, 11, 23, 24, 25, 26.
- Chains: 1 -> 2 -> 15 -> 16. 3 -> 21. R0, 6, 8, 10, 11 -> 12 -> 22. 17 -> 18 (18 needs M1, M2). 19 -> 20. 9 needs M4. 27 needs M5.

## Before Full Auto is turned on again

A3 found pending orchestration launches and three tickets paused by the 2026-10-19 stop-all; Full Auto drains and resumes them. The person decides whether they run. The owner: "and i'm not starting full auto with all those other tickets there that's why i want them all put aside so that these tickets can be worked on" (`f9f108ee`, 2026-10-20T01:19:25Z).

## Evidence recorded for this assignment

Only the three requested documents change. Evidence checks are recorded in the target architecture’s Verification and limits section. No runtime correctness tests were run for these documentation edits. Future implementation steps must execute their proving checks. Baseline timing limits are proposed targets. Full Auto remains unchanged.
