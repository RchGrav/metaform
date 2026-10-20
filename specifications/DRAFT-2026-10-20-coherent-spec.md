# DRAFT coherent specification, 2026-10-20

**Status: draft for the owner's review. Nothing in it is approved.** Written by a helper agent for the system agent, on no ticket. Code at `797a523b`; board files at `bc5bd3a5`.

## About this draft

- **Why it exists.** The records in `01-map.md` to `11-context.md` were written over five weeks, one conversation at a time. Many describe a product that has since changed. Many carry agents' wording stamped as the owner's. The owner: "a coherent specification was never done properly from the beginning everything just kept taking notes out of context" (`f9f108ee`, 2026-10-20T01:25:45Z).
- **What it is.** One design, written from what the product must do. It follows `docs/architecture/2026-10-20-target-architecture.md` (defects D1 to D11, decisions M1 to M9) and `2026-10-20-remediation-plan.md` (steps R0 and 0 to 34).
- **Order of authority.** Functionality first; the code is the reference for what is built; CLAUDE.md and the commits of 2026-10-19 and 20 outrank older records. The owner: "Don't these agents understand that the requirements are secondary to the functionality?" (`f9f108ee`, 2026-10-20T01:25:01Z) and "The specifications are dated and have changed, so if you're following the specifications, that might be a problem." (`f9f108ee`, 2026-10-20T01:25:29Z)
- **Whose words.** Every rule below is this draft's wording, not the owner's. The owner's words appear only as exact quotes with transcript and timestamp. Transcripts are Claude Code session files in `~/.claude/projects/-home-rich-metaform/`: `f9f108ee` = `f9f108ee-6be4-4f62-8526-be5ad54c8f0f.jsonl`, `627d03a9` = `627d03a9-d0b5-42d9-a578-f8697b3a1aa3.jsonl`, `37e756d2` = `37e756d2-12a8-4fe1-8367-6cbe13a6e68a.jsonl`. Commit subjects are quoted as commit text; the git author is the owner's account, which does not prove who wrote them. Why this matters, in the owner's words about an agent's memory definition: "It's not my fucking specification." and "I didn't write that instruction." (`f9f108ee`, 2026-10-20T00:49:20Z and 00:49:24Z)
- **Evidence scope.** Built labels and numerical measurements describe the historical baseline, not ongoing uncommitted repairs. Source-verification details live in the target architecture’s Verification and limits section. PM routes open decisions to the owner.
- **Record form.** Each record: **Rule** (what must hold), **Why**, **Check** (how to prove it), **Built** (state at `797a523b`, with plan step if not). Old records map to these in section 12.
- **Terms.** As in the glossary (`metaform://metaform`; CLAUDE.md). AUE, RE, PE, OP, EF, CQU, Join, Address and CEL are used exactly.

---

## 1. Principles

### 1.1 Functionality first
- **Rule:** Each part is judged by whether the product works for the person: fast, reliable, cheap in tokens, doing what it is for. A record that blocks working functionality is refined openly, with its why.
- **Why:** The records were often ideas at their date; their purpose outranks their words.
- **Check:** Every record in this draft names a check that measures function, not wording.
- **Built:** n/a.

### 1.2 Reactive, and handlers do only what the event requires
- **Rule:** No polling. A changed state is announced by the entity that changed it, on the existing bus or the relay of `map.changed`. A handler filters on the event alone, reads only the records named, ignores its own writes, and merges bursts. An upstream that forces polling is isolated in one dedicated worker thread.
- **Why:** CLAUDE.md sections 1 and 2; 2026-10-15 measured ten idle runners at about 80% of a core each.
- **Check:** For each event path: 60 s idle CPU before and after; a burst of unrelated events causes zero reads.
- **Built:** Mostly (A5 F4). Not yet: per-call change checks in the store and MCP listing (plan step 16); A2A follower polling on the server loop (AM, `a2a_out.py:449-486`).

### 1.3 Cheaper frames, never fewer
- **Rule:** Hot paths follow CLAUDE.md sections 3 to 5: fixed object shapes, zero allocation per frame, batched GPU updates, `requestAnimationFrame` only. Performance work lowers the cost of a frame; it never caps, throttles or pauses the frame rate.
- **Why:** The map is a live display.
- **Check:** Frame time median, p95, p99 on the real GPU, before and after; draw calls from `renderer.info`.
- **Built:** Mostly. `warm3d` allocates per frame (AW W8; plan step 27).

### 1.4 Metaform never gates or judges inference
- **Rule:** Metaform enforces mechanics only. It never judges a model's names, structure or content.
- **Why:** The model's judgment is the product's value; mechanics are what code can prove.
- **Check:** No verb refuses on content quality; refusals name a mechanical fault and one next step.
- **Built:** Yes, except memory's one-fact and title refusals (section 7; plan step 18).

### 1.5 Context once
- **Rule:** An agent receives what it needs once per context epoch, on whichever path, and nothing it does not need. Every model call has a cause the person can see.
- **Why:** Cache reads were 98.2% of recorded tokens and $1,758.75 was spent in one week (cost audit). The owner: "i'm not adding more context on top of context on top of context" (`f9f108ee`, 2026-10-20T00:53:23Z).
- **Check:** Zero duplicate bytes per epoch at the delivery boundary; one invocation record per paid call.
- **Built:** Partly (sections 5 and 6).

---

## 2. Map and layers

### 2.1 C(T) and the functional map
- **Rule:** A metaform is C(T) = { (r_i ∧ p_i ∧ e) }: receiving elements, providing elements and their encounters, as a tripartite mesh of elements and purpose joins that cannot express a cycle. A join runs one way: the RE owns it, the PE serves it. The element-to-element view is derived and may cycle. Any artifact can be mapped; its Defining Element stands for it.
- **Why:** A frozen core that allows mutation, not transformation, is what lets agents work on a part without losing what it is for.
- **Check:** MAP-002 and MAP-003 tests (`projection.py:298-322`, A1).
- **Built:** Yes.

### 2.2 Namespace and Address
- **Rule:** The namespace is a tree of types. An Address names a type, narrows trunk to leaf, and reads as a proper noun reversed. Every prefix is a type. One element per Address per map; an element is its Address and cannot be moved. Every element carries one role. The store does not judge namespace content.
- **Why:** The Address is where knowledge, memory and work attach and from where they inherit.
- **Check:** MAP-010 to MAP-017 tests.
- **Built:** Yes.

### 2.3 Joins, encounters and refs
- **Rule:** A purpose join records one encounter in full (RE, PE, OP, EF, IFD). Every encounter is a function or a property. A ref is one record of the `sources` layer, on an element or a join, named `{ref_id}@{address}:{join}`; refs never move or inherit.
- **Why:** Refs tie the map to the artifact's files exactly; one record each keeps them addressable (layout 22).
- **Check:** `data/refs.py` tests; `sqlite.COMPATIBLE_FROM = '22'` (`sqlite.py:26`).
- **Built:** Yes.

### 2.4 The base map is the intake's alone
- **Rule:** The base holds only the intake's elements and purpose joins, grows only by refinement (`map refine`), and never changes otherwise. A knowledge write naming a finished base goes to a knowledge layer, with a notice naming it. Genre, style, medium and encoding stay out of the base during intake. Porting is a layer swap.
- **Why:** Ports, scoped knowledge and specialist routing (`functional_context`, `59195de7`) all stand on an exact C(T).
- **Check:** A1's scratch-home probe: `add_element` and `add_property` on a finished base return a notice naming the knowledge layer; the base is unchanged.
- **Built:** Refinement yes (`8af918f6`). Guard no (plan step 25).

### 2.5 Knowledge layers and scoped knowledge
- **Rule:** Outside the base, knowledge lives in knowledge layers (CELs). A CEL is attached to a base element with `map knowledge op=link-context`. Its items marked `instruction` apply at that element and every Address toward the leaves from it, or only where their `applies_to` says; they never show on a sibling branch. Ordinary items stay at their node. Property records travel as LAYER-005 says. Functional joins never travel. Dotted CEL names are allowed; a name equal to a root is refused; existing `scope@content` names stay readable. Any Address that does not exist can be created in a knowledge layer.
- **Why:** Broad scope made fresh contexts expensive (one memory entity, 1,287,404 characters over 116 receipts, cost audit). Explicit attachment sends knowledge only where it applies.
- **Check:** Phase-one tests (`c4f449fc`); an instruction at `code.store` reaches a worker at `code.store.memory` once and not one at `code.graph`.
- **Built:** Yes (`reads.py:290-333`; pushed once as `map:effective_context`, `runner.py:4299`). Unbounded size of that push: AP PROMPT-02.

### 2.6 Layer visibility
- **Rule:** Every datum is a layer or linked to one. Select, mask and hide decide which layers reach each Address; hiding keeps data stored and hides everything attached, memories included. Properties apply toward the leaves and are visible toward the trunk.
- **Why:** Layers can be taken off and put back on demand (CEL).
- **Check:** LAYER-002 to LAYER-008 tests (`selection.py:59-120`, `reads.py:159-258`).
- **Built:** Yes.

---

## 3. Store

### 3.1 Op log, projection, and reads that lock nothing
- **Rule:** Each base is an append-only op log; each process holds a projection built from it. A read never takes the file's writer lock once the file exists and never holds the projection lock: it reads the state current when it starts. A write builds a private next state and publishes it at commit with one swap; a rollback or failed COMMIT drops it, and no reader ever sees it.
- **Why:** A read waited 3.84 s behind a waiting write, against 0.003 s without it (A1 F1); a reader saw a rolled-back type (AS STORE-A1). This is the store side of the owner's "When you click anything, everything freezes up." (`f9f108ee`, 2026-10-20T01:10:55Z)
- **Check:** `freeze.py` read under 50 ms; AS's scheduled-reader probe prints `False`; determinism test passes.
- **Built:** No (plan steps 1, 2, 15). Layout is 22 (`sqlite.py:25`).

### 3.2 Catch-up by event
- **Rule:** A long-lived process records the sequence its projection reached and reads the log only when `map.changed` names its base at a later sequence, after its own write, or after a relay reconnect. A read with nothing new opens no connection. Module enable and disable arrive as events. A short-lived CLI process catches up on open.
- **Why:** The per-call floor of 1.38 to 7.4 ms is change-checking (A1 F3); the event already exists (BASE-053).
- **Check:** 1,000 reads with no change: 0 SQL statements. 100 `map.changed` for another base: 0 log reads. Relay drop and reconnect: no missed op.
- **Built:** No (plan step 16).

### 3.3 Where tables live
- **Rule:** A table lives in the store its writers share. The base file holds the op log and the tickets (`work`, `work_steps`, `work_links`, `messages`), which change with the map. Dispatch, orchestration and the invocation ledger live in project-level stores. A move keeps every row and backs up first.
- **Why:** Ticket links follow renamed Addresses (`map/storage.py:283`); other tables share no transaction with the map and only add to its write lock.
- **Check:** Base `sqlite_master` holds no `orchestration.*` or `dispatch.*`; row counts equal across the move.
- **Built:** A1 F2’s copy held 250 orchestration assignments and 804 transitions in the active base [R]. Move: plan step 22. Tickets moving is owner decision M6.

### 3.4 Snapshots and space
- **Rule:** A snapshot is written outside the write transaction, newest only, and kept only where loading it beats replay. Free pages are reclaimed by incremental vacuum.
- **Why:** On one copy replay took 179 ms and snapshot-plus-replay 335 ms; snapshots are written under the write lock (A1 F6; AS STORE-A7).
- **Check:** Cold open ≤ full replay at three history sizes; file within 10% of pages in use.
- **Built:** No (plan step 26).

### 3.5 A reader gets what it shows
- **Rule:** A list returns list fields; a record read by id returns everything. A board card is: id, node, address, condition or kind, title or first line, column, position, glyph, agent, age, steps, steps done. Steps and links for a page come in one query. A result is made plain once.
- **Why:** The board carried 870,424 bytes for 158 cards where 120,812 serve it (A1 F4).
- **Check:** ≤ 150 KB and ≤ 10 ms for 158 cards; SQL count per list constant in its length; `map work id=<id>` returns task, steps, resolution.
- **Built:** No (plan step 14).

---

## 4. Chassis and modules

### 4.1 One declaration drives every surface
- **Rule:** A module declares `Module`, `Verb`, `Noun` and settings once; that declaration produces the CLI command, its help, its MCP tool, its validation and its settings screen. A verb receives one `Context` and returns data shown the same way everywhere. Modules reach Metaform only through the public base. Any new capability goes into `modules/template` and its CHANGELOG.
- **Why:** Anyone can write a module without editing the chassis or another module.
- **Check:** A synthetic module's verb appears on CLI, MCP and help with no other edit.
- **Built:** Yes, except the mcp module's hardcoded tables of other modules' tools (section 6.4; plan step 28).

### 4.2 The chassis runs alone
- **Rule:** The chassis runs as a CLI with every module off; MCP is a module; it runs with only `mcp` enabled.
- **Why:** A user installs only what they use.
- **Check:** AM's probe: stdio and HTTP initialize, list and call with only `mcp` enabled.
- **Built:** Yes (AM). The wheel still carries every module's dependencies (AM; `hatch_build.py:28-40`).

### 4.3 Settings
- **Rule:** Settings are declared by their owner in code; one declaration drives switch, help, validation, `config --show` and the settings screen. Values are stored by scope and owner in the home database. Defaults are never written.
- **Why:** One source of truth per setting.
- **Check:** CLI-010 to CLI-024 tests.
- **Built:** Yes.

---

## 5. Agent coordination

### 5.1 Roles
- **Rule:** Four roles do the work.
  - **The person** decides and can always stop, start and message any agent.
  - **The system agent** writes tickets, names the specialist each needs, and keeps the board. It does not do the work itself.
  - **A worker** takes one ticket and works it as the named specialist.
  - **The Facilitator** authors a named reusable specialist only for an explicit library-maintenance request. Missing ticket metadata never starts it automatically.
- **Why:** A coordinator per ticket doubled the agents per ticket. The owner: "we need to kill the gc role" (`627d03a9`, 2026-10-19T00:35:27Z); "we need to have the ticket writer write the specialist they need for each ticket thats you" and "we need an agent to create specialists" (`627d03a9`, 2026-10-19T00:47:22Z); of the system agent, "It's supposed to be managing the Kanban and writing tickets. That's it." (`37e756d2`, 2026-10-19T01:02:07Z). Built in `59195de7` ("Route tickets to reusable specialists and add editable graph inspection") and `c0209306` ("Facilitate missing specialist expertise and continue original tickets").
- **Check:** With Jev off and an empty library, each admitted ticket starts one implementer session. Unnamed tickets create zero Facilitators. Explicit requests for the same named specialist share one authoring operation.
- **Built:** Partly. GC code remains (`orchestration/state.py:671`); Facilitator per unnamed ticket (plan R0, steps 6, 22).

### 5.2 One ticket, one agent, filed to done
- **Rule:** A ticket's work is one worker session. The worker closes it with resolution and evidence, and the session ends. Choosing its specialist, recording and reviewing add no session unless the person explicitly requests separate work. Missing expertise uses the existing implementer duty. Nothing reopens a done ticket except the person or new evidence of a fault. Recovery and the rework limit stay as dispatch's duties.
- **Why:** Every added session repays the whole startup context; A3 F3 records 120 assessment tickets among 181 root tickets [R]. The owner: "we do need the freaking track tickets and we do need to see shit get done" (`f9f108ee`, 2026-10-20T01:21:31Z).
- **Check:** A small real ticket (QUAL-014) shows one session in `dispatch_sessions` and its cost in the ledger.
- **Built:** No: record turn, assessment ticket and completion wake still run (plan steps 8, 9, 10, 12).

### 5.3 Start and the gate
- **Rule:** A start comes from the person, the system agent at the person's word, or Full Auto, and passes one gate (`_admit`: halt, machine cap, Full Auto cap for automatic starts, the day's budget). A start is never refused for want of a specialist: the ticket starts under the existing implementer duty if no valid named role is available. Full Auto off starts nothing by itself and stops nothing already running.
- **Why:** A start refused upstream of the gate looks like a broken button. The owner: "Well, full auto off is supposed to not allow more to start. The existing ones should keep running. But more shouldn't start and I should be able to broadcast until everybody to stop or they should listen." (`37e756d2`, 2026-10-19T01:03:15Z)
- **Check:** Orchestration on, Jev off, empty library: `dispatch_start` never answers `needs_specialist`.
- **Built:** Gate yes. `needs_specialist` return still at `dispatch/__init__.py:3171` (plan step 6).

### 5.4 Stop
- **Rule:** One stop record per ticket, kept with its session in dispatch, plus the halt for everything. Any start on the person's word clears that ticket's stop. The person's stop is never refused.
- **Why:** A stop kept in four places let a restarted ticket never finish (`dispatch/__init__.py:3180`; `orchestration/state.py:1048`).
- **Check:** AD D1's acceptance.
- **Built:** No (plan steps 6, 22).

### 5.5 Review only when asked
- **Rule:** By default no review runs. When the person turns review on, it is one pass in the same ticket on a changed candidate; it fixes what it finds, files a ticket only for what it cannot fix, at most once per finding, and never reopens a done ticket.
- **Why:** Separate review tickets were the largest spend concentration ($235.20 for one family, cost audit).
- **Check:** Default: delivering a ticket creates no assessment assignment.
- **Built:** No: `orchestration_reviews` defaults to 1 (`orchestration/__init__.py:27`). Owner decision M4.

### 5.6 Consent
- **Rule:** The person's standing choices decide: the permission policy for acts on the machine (`dispatch_prompts`) and person-only settings for control over agents. A verb is the person's alone only when its act cannot be undone or it changes a part's purpose.
- **Why:** Overlapping gates made agents ask after the person had said yes. The owner, on `approve-all`: "yes that is my setting why do I need to give permission thats my question" (`f9f108ee`, 2026-10-20T01:00:03Z).
- **Check:** With `approve-all`, the system agent's reversible dispatch and orchestration verbs run with no card or refusal; an irreversible verb still asks.
- **Built:** Partly; eight mechanisms decide independently (A3 F7).

### 5.7 Budget and the invocation ledger
- **Rule:** Every paid call is admitted against the person's budget right before it is sent, whatever caused it. Each call writes one invocation record: cause, recipient, ticket, context epoch, model, component fingerprints and byte counts, usage, cost, and whether usage is measured, estimated or unknown. Each finished ticket reports its sessions, calls and cost.
- **Why:** Without it no change can be shown cheaper (cost audit P0). The owner: "somehow i burned up half of my fucking account" (`f9f108ee`, 2026-10-20T01:09:05Z).
- **Check:** Cost audit section 1 acceptance; a queued continuation after budget exhaustion makes zero calls.
- **Built:** No (plan step 11).

---

## 6. Context delivery

### 6.1 Connect
- **Rule:** At connect the server sends the directive and links to the blocks that apply to this agent; the agent reads each whole before anything else, once per context epoch. A block links only the agent's own role, read from its own session's assignment, never inherited from the process that started it. No paragraph appears in two blocks. The person's first-run onboarding never pre-empts the person's request.
- **Why:** The current decision (`a0f67e19`, "Connect directive back to its original wording: before you do anything else, read every resource linked below, whole"; the owner: "Well, get rid of that. I didn't say applicable.", `f9f108ee`, 2026-10-20T01:30:13Z). Inherited roles cost every helper the 10,691-character triage block (A2 F6).
- **Check:** A helper connects with `metaform://role/helper` only; paragraph-hash check finds no repeat across blocks.
- **Built:** Directive yes. Role leak: `harness.py:248` omits `METAFORM_AUTHORED_ROLE` (plan step 7).

### 6.2 One delivery ledger
- **Rule:** Everything Metaform gives an agent session (connect blocks, resources, tool guides, glossaries, notices, pushed node content, bodies inside tool results) goes through one chassis ledger per session and epoch, keyed by content. A body already given is a reference. A body is marked given only after delivery. A compaction, known only from ACP's compaction signal, starts a new epoch and pushes nothing by itself. It works with every optional module off.
- **Why:** Five ledgers meant each fix left another path repeating (A2 F2).
- **Check:** The glossary through three paths delivers once per epoch, also with `agents` disabled.
- **Built:** No (plan step 19).

Startup retention is separate from content delivery. Confirm checkpoint with the retained key when available. Missing proof permits one needed contextual read. Never search logs for the key. Never schedule another turn or dump all context. Prove this with a retained-key case, a missing-key case and repeated checkpoint calls: only the needed component becomes readable once.

### 6.3 Results
- **Rule:** A verb's result is what the caller's next decision needs: a write returns what it changed and handles; a read returns the fields asked for. One encoding: text, with structured content only where a host is shown to read it instead. A next step names the tool call or resource, never a command line.
- **Why:** `orchestration_claim` returned 9,058 characters with the task six times (A2 F3).
- **Check:** `orchestration_claim` under 1 KB, task once, no `role_snapshot`.
- **Built:** Shaping yes; declared results no (plan steps 19, 20).

### 6.4 Tools
- **Rule:** Every command is its own typed tool from its verb's declaration. A host that loads tools on demand gets a stable, sorted full list; another host gets a per-session list that only grows. Reading an index changes no list. Each command has typed validation. Preserve existing catalog compatibility until the measured host path proves a replacement. The list is computed when the surface changes. An HTTP session is named by `Mcp-Session-Id` or a provisioned header, through transport metadata or a provisioned binding. A model-provided handle alone never establishes identity or authority. Legacy `Mcp-Session-Id` applies only on negotiated legacy transports; July clients use per-request metadata, as the local MCP research describes. `project` is withheld from dispatched agents.
- **Why:** Per-module loading cost 39,391 bytes for map (A2 F1); per-request listing cost 38 ms (A2 F4).
- **Check:** Tool-definition bytes for a scripted session below 39,391; 100 calls with no surface change cause 0 rebuilds.
- **Built:** No (plan steps 16, 20, 28).

### 6.5 What an agent is told about its node
- **Rule:** Once per session, a summary of about `node_summary_bytes` (2 KB) and the instruction items that apply; anything more is a count with the call that reads it. Memories are a count on arrival (section 7.3). Nothing is pushed into a turn in flight.
- **Why:** The 2 KB budget holds only if every push honours it; the effective-context push does not (AP PROMPT-02).
- **Check:** Enlarging a knowledge subtree does not enlarge the startup payload proportionally; instructions stay whole.
- **Built:** Partly. Startup reference and onboarding fixes: plan step 34.

---

## 7. Memory

### 7.1 The standard MCP memory server, with an Address
- **Rule:** Memory is the MCP reference memory server: entities `{name, entityType, observations}`, relations `{from, to, relationType}`, its nine tools with its arguments and results. Metaform adds one thing, an Address to hang each memory at: an optional `node` on `create_entities`, and `join`, `unjoin`, `rekey`, `orphaned`, `map_moved` to keep it there. Nothing else is required to write.
- **Why:** Models already know the reference server; each departure spends that. The owner: "This is exactly fucking like that! Except for you have a fucking place to hang the fucking memories! That's all!" (`f9f108ee`, 2026-10-20T00:47:17Z), and on content, "It's supposed to be durable atomic memories that are valuable." (`f9f108ee`, 2026-10-20T00:53:59Z). Commit `d0985e90`: "CTX-020: memory is the standard memory server with an Address to hang memories at" (co-authored by Claude per its trailer).
- **Check:** A conformance test replays the reference's tool calls with no node and compares results field for field.
- **Built:** Graph and nine tools yes. Departures: required title and why, one-fact refusal, one-line results, 20 verbs, citations and `watch` (A4 LAYER-013; plan step 18).

### 7.2 Addressed reads
- **Rule:** A read at a node returns the memories hung there and at each prefix toward the trunk, filtered by layer reach, plus every relation with an end among them. It reads those entities only, never the whole graph. Siblings do not inherit. Without a node, reads act on the whole graph.
- **Why:** The Address is the design's one addition, and it is the part not built (A4 defect 5); whole-graph reads grow with the graph (AS STORE-A4).
- **Check:** A memory at `code.store` reads at `code.store.memory`, not at `code.graph`; a node read on 1,000 entities touches one entity's rows.
- **Built:** No (plan step 17).

### 7.3 Delivery: a count on arrival, nothing pushed
- **Rule:** On arriving at a node, an agent is told in one line how many applying memories this session has not been sent; nothing when zero. Reading is the agent's call. A per-entity receipt is the proposed policy, pending M3. Do not drop version/deletion history until that decision and migration proof exist.
- **Why:** Treating every edit as new made one entity read in 125 sessions over 24 versions [R]. The reference server pushes nothing.
- **Check:** 50 edits by session B at `code.x` cause zero memory reads for session A at `code.y`.
- **Built:** Arrival line yes; per-entity record no; bookkeeping A4 defect 4’s historical tables held 6,736 withdrawal rows with 0 entities [R] (plan step 17). Whether an edit counts as new: owner decision M3.

### 7.4 No ticket ties
- **Rule:** No ticket, turn or module writes or requires a memory. A ticket's disposition is recorded on the ticket. Agents create, update and delete memories during their work when something will help the next agent at that Address.
- **Why:** The ticket flow produced work logs (61 of 195 pre-clear entity names carried ticket ids or dates, A4). The owner: "Tickets don't own memories. The memory prompt does. Tickets have nothing to do with memories." (`f9f108ee`, 2026-10-20T00:45:56Z); "agents are supposed to be deleting and updating memory" (`f9f108ee`, 2026-10-20T00:41:01Z).
- **Check:** A worker closes having written no memory; zero prompts after done; `grep -rn "dispatch_record_on_\|work_record" src/metaform` empty.
- **Built:** No (plan step 8).

### 7.5 The memory prompt
- **Rule:** Every agent receives the memory prompt once per session and again after a compaction. Its text is the one the owner approves. No other prompt defines memory as work history or asks for an edit on every arrival.
- **Why:** The shipped text (`memory/resources/prompts.xml:59`) came from `4f2966c8`; `orient` and `connect` still say "what happened in the work" (`:12`, `:42`).
- **Check:** Shipped `instructions` equals the approved text byte for byte; no shipped prompt contains "what happened in the work".
- **Built:** Delivery yes. Text: owner decision M1. Memory and knowledge split: owner decision M2.

### 7.6 Kept beyond the reference
- **Rule:** A memory can be locked: every agent reads it, none changes it; lock and unlock are CLI only. Memory shows as a layer named `memory` that selection turns off. Memories survive a cleared intake.
- **Why:** CTX-023 and LAYER-012 describe existing protections. Preserve them until review resolves any change. Their historical status does not prove owner authorship.
- **Check:** Existing lock tests; a masked node delivers no memory body.
- **Built:** Yes.

---

## 8. Web

### 8.1 Process layout
- **Rule:** The request process serves files, store reads and writes, module verbs in process, the stream and one timer thread. Log and file watchers run in a services process under the watchdog. Each agent's runner is its own process, started with the person's environment. Nothing a click waits on starts a process.
- **Why:** Each child Python process costs 0.70 to 0.78 s and 73 MB before its verb runs (A5 F2).
- **Check:** `strace -f -e trace=execve` shows no `python` exec on any click; each answers under 200 ms.
- **Built:** No (plan steps 13, 23).

### 8.2 Changes over the one stream
- **Rule:** One SSE stream per page. `map.changed` with `tables`, `work_ids`, `session_ids`, `kinds`, `seq` is the only change channel. A view applies only the ids named into the set it holds and never replaces its set with another view's. A thread is read past its last drawn line. Batches flush by their deadline under load; per-page pending events are bounded. The stream's closing is how the page knows the server is gone; health is asked only on a stream error or a failed read.
- **Why:** The board lost its Done column on every ticket event (`live/ops.js:313`) [R]; the chat re-read whole threads.
- **Check:** Done count unchanged across one ticket event; ten chat events on a 2,000-line thread under 50 KB.
- **Built:** Stream and filtering yes (A5 F4). Not yet: steps 5, 14, 24.

Snapshot reads carry committed sequence. Buffer stream events while taking a snapshot, apply newer revisions, discard already-applied mutation identities. Sequence gaps, overflow and reconnect force a scoped authoritative reread. A test must inject a write during initial load, duplicate delivery, stream loss and overflow. Every view must converge without losing Done records or ordered control events.

### 8.3 Writes
- **Rule:** Each page write calls the operation the CLI and tools use, in the server's process, with the same checks and settings. A write answers with the records it changed; the page applies them and does not read again. The person's consent travels as the request's context, never through a file or the environment.
- **Why:** Same reasons as the CLI path, without the process start.
- **Check:** A Top click makes one `POST /api/move` and no board read.
- **Built:** No (plan steps 13, 14).

### 8.4 The person's buttons survive restarts
- **Rule:** An agent cannot press the person's buttons by posting as the page. A page whose server is new gets a new key under the same check a page load has; under the watchdog, keys come from a secret it holds in memory and passes to each server. A refusal the page can resolve itself is resolved, not shown.
- **Why:** After a restart every person's write was refused (`web/server.py:106`, `:442`, `:3538`). The owner: "what the fuck is tyhis I cant start fucking tickets? /api/dispatch-start is the person's to do on the page itself, and this request carries no key this server gave a page it served." (`f9f108ee`, 2026-10-20T01:02:40Z)
- **Check:** Restart, then Move to top: 200, no reload; an agent's POST still 403.
- **Built:** No (plan steps 3, 4, 21).

### 8.5 The board
- **Rule:** A kanban of the project's tickets that follows the store. It reads card fields; a card's detail and history read the ticket whole. It shows open work and a bounded recent Done window that survives events. Board open under 300 ms with no long task over 100 ms.
- **Why:** The owner: "The board is so fucking slow you can barely use it." (`f9f108ee`, 2026-10-20T01:10:05Z). Measured 801 to 1,159 ms to painted cards (A5 F3).
- **Check:** A5's `probe.py` three opens each under 300 ms; under 2,500 DOM nodes.
- **Built:** No (plan steps 5, 14). Saved and restored boards: owner decision M8.

### 8.6 The map's look
- **Rule:** A nearer label is always drawn over a farther one, across every atlas page, with labels batched. Label facing and scale, the collapse default and how joins are drawn are the owner's choice, recorded once.
- **Why:** Four commits on 2026-10-17 changed the look without one record (A5 F5). The owner: "The map and the labels look like absolute shit. They originally looked good. I don't know what happened." (`f9f108ee`, 2026-10-20T01:07:56Z)
- **Check:** Two-page overlap scene draws near over far from both sides; draw calls within 2 of before.
- **Built:** Depth order across pages no (plan step 27). Look: owner decision M5.

---

## 9. Quality and proof

### 9.1 Proof by behaviour
- **Rule:** Tests protect changed behavior and adjacent contracts. Use isolated fixtures for network and heavy I/O. Run required checks. Broaden only when risk or failures justify it. Fixtures, simulations and real runs are named for what they are. A change to the ticket lifecycle is proven by one real run (one small ticket, one session, its cost).
- **Why:** No real run shows a ticket going filed to done on the current path (A3 root defect 9).
- **Check:** Plan step 12 recorded.
- **Built:** Fixtures only.

### 9.2 CI
- **Rule:** pyright strict on `src/metaform`, Ruff, pytest on Linux, macOS, Windows, Python 3.11 and 3.14. The tracked checkout passes Ruff.
- **Why:** Builders stand on a green gate.
- **Check:** `uv run ruff check src tests conftest.py` exits 0.
- **Built:** Ruff fails on tracked files (AQ QUALITY-001; plan step 0).

### 9.3 Review is one pass, when asked
- **Rule:** A critic or test-gaming review checks a finished build when asked, once, and fixes what it can in the same pass. It is never a ticket per change.
- **Why:** Review chains were the largest spend concentration (cost audit).
- **Check:** No review assignment exists unless the person asked.
- **Built:** See 5.5.

### 9.4 Removing needs the same permission as building
- **Rule:** A removal's commit names what goes and why.
- **Why:** Deletions are design changes.
- **Check:** Commit messages of plan steps.
- **Built:** Yes (QUAL-017).

---

## 10. Carried unchanged until reviewed

The records listed in section 12 as "Kept, carried" remain historical intent awaiting review: projects and history (`08-projects.md`), the command line (`05-cli-settings.md`), the installer (MCP-010 to MCP-024), the world (`10-world.md`), file locks (CTX-060 to CTX-064), prompt addressing (CTX-080 to CTX-087), the person's note (CTX-088 to CTX-090), the viewer's records not refined in section 12, workflows, builds, forks and optional modules. These records were not assessed against function in this pass. None adds work to this foundation repair. Conflicts resolve through current functionality and PM review.

## 11. Open decisions for the owner

| # | Decision | Draft's recommendation |
|---|---|---|
| M1 | Text of the memory `instructions` element. CTX-026's 2026-10-17 amendment says the owner delivered a block; this draft did not find that delivery in the transcripts it searched. | Owner names the text. |
| M2 | CTX-021 (knowledge never in memory) against category d of CTX-026's 2026-10-17 block. | Owner rules. |
| M3 | Does an edited memory count as new for sessions that read it? | No. |
| M4 | `orchestration_reviews` default. | 0. |
| M5 | Map look: facing, scale rate, `web_map_depth` default, join purpose vertex. | Pick from side-by-side screenshots. |
| M6 | Tickets ever leave the base file? | Only on measured contention after plan step 2. |
| M7 | Consensus mode (VIEW-043). | Withdraw. |
| M8 | Saved boards. The owner: "I just wish you could save and restore boards, you know, clear the board, save it as a name, start a new board, bring back the old board once the problem's fixed." (`f9f108ee`, 2026-10-20T01:20:49Z) | Build after plan step 14. |
| M9 | Memory citations, `watch` and per-address numbering. | Delete with code facts kept out of memory. |

---

## 12. Old records mapped

Every record heading in `specifications/01-map.md` to `11-context.md` at `797a523b` (429 records, `grep -cE '^#+ *[A-Z]+-[0-9]+'`). Verdicts:

Totals: 11 Dropped, 157 Kept, 191 Kept, carried, 70 Refined; 429 in all.

- **Kept**: the functional intent is retained in the named section of this draft. This does not ratify historical wording or owner attribution.
- **Kept, carried**: retained for traceability only, not assessed or approved in this pass (section 10).
- **Refined**: the intent stands; the named section is its new text, for the reason given.
- **Dropped**: retired, for the reason given.

Sources in the Why column: A1 to A5 and the audits as named in `docs/architecture/2026-10-20-target-architecture.md`; "cost audit" is `docs/reviews/2026-10-19-token-waste-analysis.md`.

### `01-map.md`

| Record | Title | Verdict | Into | Why |
|---|---|---|---|---|
| MAP-001 | C(T) is the theory behind how a metaform works | Kept | §2.1 | Holds as built (A1 appendix A). |
| MAP-002 | The functional map is a tripartite mesh that cannot express a cycle | Kept | §2.1 | Holds as built (A1 appendix A). |
| MAP-003 | A join runs one way: the receiver owns it and the provider serves it | Kept | §2.1 | Holds as built (A1 appendix A). |
| MAP-004 | The element-to-element view is derived and may cycle | Kept | §2.1 | Holds as built (A1 appendix A). |
| MAP-005 | A metaform is a multi-dimensional mesh that works through type understanding | Kept | §2.1 | Holds as built (A1 appendix A). |
| MAP-006 | Metaform engineers the context agents work in | Kept | §2.1 | Holds as built (A1 appendix A). |
| MAP-010 | The namespace is a tree of Types, and an address names a Type | Kept | §2.2 | Holds as built (A1 appendix A). |
| MAP-011 | Every prefix of an address is a Type, and inference runs from trunk to leaf | Kept | §2.2 | Holds as built (A1 appendix A). |
| MAP-012 | An address reads as its name when reversed | Kept | §2.2 | Holds as built (A1 appendix A). |
| MAP-013 | The namespace rules govern the functional map, and the store does not judge them | Kept | §2.2 | Holds as built (A1 appendix A). |
| MAP-014 | Root Types | Kept | §2.2 | Holds as built (A1 appendix A). |
| MAP-015 | An element is its address in the namespace, and it cannot be moved | Kept | §2.2 | Holds as built (A1 appendix A). |
| MAP-016 | One element per address per project in a map | Kept | §2.2 | Holds as built (A1 appendix A). |
| MAP-017 | Every element carries exactly one role | Kept | §2.2 | Holds as built (A1 appendix A). |
| MAP-020 | A purpose join records one encounter in full | Kept | §2.3 | Holds as built. |
| MAP-021 | Refs are an ordered key and value list in the sources layer | Refined | §2.3 | Layout 22 made each ref one record of `sources` (`sqlite.py:26`); "one item there carrying them" is overtaken (A1 section 0). |
| MAP-022 | Every encounter is a function or a property | Kept | §2.3 | Holds as built. |
| MAP-030 | Annealing places an absorbed element in its parent's join | Kept | §2.1 | Holds as built. |
| MAP-031 | An element held only by subtype joins is never a root and never a node of the outer map | Kept | §2.1 | Holds as built. |
| MAP-032 | Subtype nesting and ownership limits | Kept | §2.1 | Holds as built. |
| MAP-040 | An intake result becomes map records | Kept | §2.4 | Intake result becomes map records; holds. |
| MAP-041 | Metaform works on any artifact, and the artifact's boundary stays explicit | Kept | §2.1 | Holds; not contradicted by newer work. |
| MAP-042 | The artifact is not an element; its Defining Element stands for it | Kept | §2.1 | Holds; not contradicted by newer work. |
| MAP-043 | Reasoning that needs the artifact receives the artifact | Kept | §2.1 | Holds; not contradicted by newer work. |
| MAP-044 | A new element joins the metaform on either side of a join | Kept | §2.1 | Holds; not contradicted by newer work. |
| MAP-045 | A project can have more than one metaform | Kept | §2.1 | Holds; not contradicted by newer work. |
| MAP-046 | A call to attention is a status in the status layer, and its phase sets the node's light | Refined | §5.2 | Built as work records and assessment state, not a `status` layer; its own Build is "Open" (A1). |
| MAP-047 | An intake result is judged by what it says about the project | Kept | §2.4 | Not contradicted. |
| MAP-048 | Tasks are written on the nodes the work concerns, and one command hands an agent everything the map holds there | Kept | §5.2 | Holds as built (`map/storage.py`, A1). |
| MAP-049 | The task list is a work queue | Refined | §3.5 | Lists return list fields; the 2026-10-06 "read whole" sentence costs 7× what the board shows (A1 F4). |
| MAP-053 | An agent says how many steps it plans, and reports each as it finishes it | Kept | §5.2 | Holds as built (`map/storage.py`, A1). |
| MAP-054 | A join can be promoted to an element that accepts joins | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| MAP-055 | The workflow root holds workflow elements, outside intake and outside any project's metaform | Kept | §10 | Workflow; open in its own record. |
| MAP-056 | A logic requirement is a subroutine, called by its workflow element's address and its name | Kept | §10 | Workflow; open in its own record. |
| MAP-057 | `this` in added logic is the element the logic is on, and its values are addressed in Python's syntax | Kept | §10 | Workflow; open in its own record. |
| MAP-058 | A ticket names the agents eligible to work it, and any agent is eligible unless the user specifies otherwise | Kept | §5.2 | Holds as built (`map/storage.py`, A1). |
| MAP-050 | An agent asks its question at the node it concerns | Kept | §5.2 | Holds as built (`map/storage.py`, A1). |
| MAP-051 | A completed task is kept as past work at its node | Kept | §5.2 | Holds as built (`map/storage.py`, A1). |
| MAP-052 | The map is written out as a short Markdown document | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| MAP-059 | The map is written out as an XML document with every field, for review | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |

### `02-layers.md`

| Record | Title | Verdict | Into | Why |
|---|---|---|---|---|
| LAYER-001 | Everything Metaform holds is a layer | Refined | §2.6 | Holds; the record says `unnamed_`, the code writes `unnamed-<stamp>` (A1). Record follows code. |
| LAYER-002 | A layer carries one inferred variable | Kept | §2.6 | Holds (`selection.py:59-120`, `reads.py:159-258`, A1). |
| LAYER-003 | A layer item attaches on an element, on a join, or on a new element and join | Kept | §2.6 | Holds (`selection.py:59-120`, `reads.py:159-258`, A1). |
| LAYER-004 | A layer declares its properties | Kept | §2.6 | Holds (`selection.py:59-120`, `reads.py:159-258`, A1). |
| LAYER-005 | Properties apply up toward the leaves and are visible down toward the trunk | Kept | §2.6 | Holds (`selection.py:59-120`, `reads.py:159-258`, A1). |
| LAYER-006 | Hiding removes a layer from view and keeps it stored | Kept | §2.6 | Holds (`selection.py:59-120`, `reads.py:159-258`, A1). |
| LAYER-007 | Select and mask decide which layers reach each address | Kept | §2.6 | Holds (`selection.py:59-120`, `reads.py:159-258`, A1). |
| LAYER-008 | Layers are read directly | Kept | §2.6 | Holds (`selection.py:59-120`, `reads.py:159-258`, A1). |
| LAYER-009 | Comparing is a view, not a stored record | Kept | §2.6 | Holds. |
| LAYER-010 | Provenance is one record per layer, and one per intermediary diff | Kept | §2.6 | Holds. |
| LAYER-011 | Correction layers are chronological, stacked, and the only way to change the metaform | Dropped |; | Overtaken by LAYER-025: versions live in the base layer, kind `base` (A1 section 0). |
| LAYER-012 | Memory shows as a layer named memory, with no provenance, that layer selection turns off | Kept | §7.6 | Address-side and cheap (A4). |
| LAYER-013 | Memory is a graph of its own, presented at each node exactly as the MCP reference memory server | Refined | §7.1 | "Exactly as the reference" is the rule; the build departs (title, why, one-fact refusal, one-line results, 20 verbs) (A4). |
| LAYER-014 | Blind spot analysis over the one Inference Metaform comes in two types, each its own layer | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| LAYER-015 | The blind-spot challenge workflow | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| LAYER-016 | Knowledge layers carry whatever their prompt asks for | Kept | §2.5 | Holds (A1). |
| LAYER-017 | Prompts and workflows are preprocessed against the metaform | Kept | §2.5 | Holds (A1). |
| LAYER-018 | Knowledge layers are written through one read-write tool | Kept | §2.5 | Holds (A1). |
| LAYER-019 | Layers are tagged, listed and toggled | Kept | §2.5 | Holds (A1). |
| LAYER-020 | A knowledge layer is built by a for-each prompt run at each node | Kept | §2.5 | Holds (A1). |
| LAYER-021 | Items carry flags, and there are no categories of layer or kinds of item | Kept | §2.5 | Holds (A1). |
| LAYER-022 | A project is read from its roots | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| LAYER-023 | An ideation agent adds the single most valuable missing feature | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| LAYER-024 | An operation prompt takes the intake's seven-section shape | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| LAYER-025 | The metaform is refined in its own layer, named intake, and no change makes a new layer | Refined | §2.4 | Holds except its Build: a finished intake taking writes is overtaken by CTX-001 and `8af918f6` (refinement only) (A1). |
| LAYER-026 | Balancing the books: the metaform is collapsed into a single layer, and that becomes the data going forward | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| LAYER-027 | A workflow is recorded in a workflow-owned layer, its source of truth | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| LAYER-028 | A layer's name is a namespace root, so a layer's work on an element has its own address | Refined | §2.5 | Dotted CEL names allowed since `c4f449fc`; "one valid namespace segment" is overtaken (A1). |
| LAYER-029 | A work claim reserves the part of the map a chosen proposal touches until its work has landed | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |

### `03-storage.md`

| Record | Title | Verdict | Into | Why |
|---|---|---|---|---|
| STORE-001 | All data lives in the Metaform home | Kept | §3.3 | Holds (A1). |
| STORE-002 | The chassis database holds what belongs to no project | Kept | §3.3 | Holds (A1). |
| STORE-003 | Each metaform has one store | Kept | §3.3 | Holds (A1). |
| STORE-004 | One row per thing | Refined | §3.1 | Specifies SQL tables, indexes and query plans; overtaken by the op log and projection (STORE-046; `data/schema.py`). Acceptance becomes behaviour and timing (A1 section 0, F7). |
| STORE-005 | Every read goes straight to its answer through an index | Refined | §3.1 | Specifies SQL tables, indexes and query plans; overtaken by the op log and projection (STORE-046; `data/schema.py`). Acceptance becomes behaviour and timing (A1 section 0, F7). |
| STORE-006 | Writes are atomic and safe with many writers | Refined | §3.1 | Its Build takes the writer lock for reads, defeating its own WAL promise; a read waited 3.84 s (A1 F1). |
| STORE-007 | Identity is a stable id that survives change | Refined | §3.1 | Specifies SQL tables, indexes and query plans; overtaken by the op log and projection (STORE-046; `data/schema.py`). Acceptance becomes behaviour and timing (A1 section 0, F7). |
| STORE-008 | Type addresses are rows in a tree | Refined | §3.1 | Specifies SQL tables, indexes and query plans; overtaken by the op log and projection (STORE-046; `data/schema.py`). Acceptance becomes behaviour and timing (A1 section 0, F7). |
| STORE-009 | Elements | Refined | §3.1 | Specifies SQL tables, indexes and query plans; overtaken by the op log and projection (STORE-046; `data/schema.py`). Acceptance becomes behaviour and timing (A1 section 0, F7). |
| STORE-010 | Joins are owned by their receiver and run one way | Refined | §3.1 | Specifies SQL tables, indexes and query plans; overtaken by the op log and projection (STORE-046; `data/schema.py`). Acceptance becomes behaviour and timing (A1 section 0, F7). |
| STORE-011 | Subtype joins live inside one join | Kept | §2.3 | Logical rule holds. |
| STORE-012 | Refs | Refined | §2.3 | One record per ref in `sources` (layout 22). |
| STORE-013 | Layers and their declared behavior | Refined | §3.1 | Specifies SQL tables, indexes and query plans; overtaken by the op log and projection (STORE-046; `data/schema.py`). Acceptance becomes behaviour and timing (A1 section 0, F7). |
| STORE-014 | Everything belongs to the layer that produced it | Kept | §2.3 | Logical rule holds. |
| STORE-015 | Layer items carry one variable at one node | Refined | §3.1 | Specifies SQL tables, indexes and query plans; overtaken by the op log and projection (STORE-046; `data/schema.py`). Acceptance becomes behaviour and timing (A1 section 0, F7). |
| STORE-016 | Provenance is one record per layer | Refined | §3.1 | Specifies SQL tables, indexes and query plans; overtaken by the op log and projection (STORE-046; `data/schema.py`). Acceptance becomes behaviour and timing (A1 section 0, F7). |
| STORE-017 | Correction layers are stacked in order and are the only way to change the metaform | Dropped |; | Overtaken by LAYER-025 (A1 section 0). |
| STORE-018 | Mutable layers change in place | Kept | §7.6 | Memory tables at project level, mutable; holds. |
| STORE-019 | Selection and mask are stored where the flow changes | Refined | §3.1 | Specifies SQL tables, indexes and query plans; overtaken by the op log and projection (STORE-046; `data/schema.py`). Acceptance becomes behaviour and timing (A1 section 0, F7). |
| STORE-020 | Memory is kept in the memory module's project-level tables, tied to the map by joins of type memory | Kept | §7.6 | Memory tables at project level, mutable; holds. |
| STORE-021 | Unknown fields survive | Kept | §3.1 | Holds (A1 appendix A). |
| STORE-022 | A module keeps its own data through the data access object | Kept | §3.1 | Holds (A1 appendix A). |
| STORE-023 | The data access object is the only way to the data | Kept | §3.1 | Holds (A1 appendix A). |
| STORE-024 | Write operations | Kept | §3.1 | Holds (A1 appendix A). |
| STORE-025 | Read operations | Refined | §3.5 | Read operations return list fields for lists, whole records by id (A1 F4). |
| STORE-026 | Errors name one next step and never judge content | Kept | §3.1 | Holds (A1 appendix A). |
| STORE-027 | Export and import carry a project whole | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| STORE-028 | Query goes through the read operations | Kept | §3.1 | Holds (A1 appendix A). |
| STORE-029 | The store records its schema version | Refined | §3.1 | Says layout 20; code says 22 (`sqlite.py:25-26`). |
| STORE-030 | A directly run wheel uses the normal data folder | Kept | §3.1 | Holds (A1 appendix A). |
| STORE-031 | Project records, ids and targets | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| STORE-032 | Layer kinds, building and finishing | Kept | §3.1 | Holds (A1 appendix A). |
| STORE-033 | Every identity id resolves to its kind in one read | Refined | §3.1 | Specifies SQL tables, indexes and query plans; overtaken by the op log and projection (STORE-046; `data/schema.py`). Acceptance becomes behaviour and timing (A1 section 0, F7). |
| STORE-034 | What a correction may change, and what removal does to what depends on the removed thing | Refined | §2.4 | Correction-layer mechanics overtaken by LAYER-025; what removal does to dependants stays. |
| STORE-035 | Context reads: the applying set, the visible set and the starting selection | Refined | §2.5 | Context reads are scoped knowledge as built (`c4f449fc`). |
| STORE-036 | Re-examination marks | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| STORE-037 | Each operation opens its own connection | Refined | §3.2 | A transaction opens its own connection; a read answered from the projection opens none (A1 F3). |
| STORE-038 | Layer tags | Kept | §3.1 | Holds (A1 appendix A). |
| STORE-039 | Properties are their own records | Refined | §3.1 | Specifies SQL tables, indexes and query plans; overtaken by the op log and projection (STORE-046; `data/schema.py`). Acceptance becomes behaviour and timing (A1 section 0, F7). |
| STORE-040 | Challenge states and plans | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| STORE-041 | Bases and the active base | Kept | §3.3 | Holds (A1). |
| STORE-042 | Work records are their own rows, apart from the map | Refined | §3.3 | Work rows stay in the base file (M6); lists read card fields. |
| STORE-043 | Reports are files with one row each | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| STORE-044 | Prompts are versioned records, and provenance references the exact version | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| STORE-045 | A module declares its own tables and reaches them through the data access object | Refined | §3.3 | A table lives in the store its writers share; orchestration and dispatch leave the base file (A1 F2, AS; plan C1). |
| STORE-046 | The store is an op log, and the base lives in memory | Refined | §3.1, §3.2, §3.4 | Catch-up by event, snapshots outside the transaction, sizes no longer "about ten kilobytes" (A1 F3, F6). |

### `04-chassis-modules.md`

| Record | Title | Verdict | Into | Why |
|---|---|---|---|---|
| BASE-001 | The chassis runs completely on its own as a CLI | Kept | §4.1 | Chassis and module contract; not contradicted by newer work. |
| BASE-002 | The chassis owns the data, the settings and the CLI | Kept | §4.1 | Chassis and module contract; not contradicted by newer work. |
| BASE-003 | The chassis does not run workflows, and MCP is a module | Kept | §4.1 | Chassis and module contract; not contradicted by newer work. |
| BASE-004 | One common base that every module builds on | Kept | §4.1 | Chassis and module contract; not contradicted by newer work. |
| BASE-005 | The data access object is the only way modules keep data | Kept | §4.1 | Chassis and module contract; not contradicted by newer work. |
| BASE-006 | Modules declare verbs with nouns, switches and their effect | Kept | §4.1 | Chassis and module contract; not contradicted by newer work. |
| BASE-007 | Module switches are settings | Kept | §4.1 | Chassis and module contract; not contradicted by newer work. |
| BASE-008 | Modules declare their settings in code | Kept | §4.1 | Chassis and module contract; not contradicted by newer work. |
| BASE-009 | Verbs run sync or async the same way | Kept | §4.1 | Chassis and module contract; not contradicted by newer work. |
| BASE-010 | Events connect modules | Kept | §4.1 | Chassis and module contract; not contradicted by newer work. |
| BASE-011 | A user error states what happened and one next command | Kept | §4.1 | Chassis and module contract; not contradicted by newer work. |
| BASE-012 | Each module adds concise instructions for agents | Kept | §4.1 | Chassis and module contract; not contradicted by newer work. |
| BASE-013 | Destructive verbs act only with --confirm | Kept | §4.1 | Chassis and module contract; not contradicted by newer work. |
| BASE-014 | Modules load from the system place, the user place, entry points and the project place | Kept | §4.1 | Chassis and module contract; not contradicted by newer work. |
| BASE-015 | Compatibility is read before any module code runs | Kept | §4.1 | Chassis and module contract; not contradicted by newer work. |
| BASE-016 | A verb may narrow its own compatibility | Kept | §4.1 | Chassis and module contract; not contradicted by newer work. |
| BASE-017 | Modules are enabled and disabled by name, and hello and template ship disabled | Kept | §4.1 | Chassis and module contract; not contradicted by newer work. |
| BASE-018 | Module lifecycle is owned and reversible | Kept | §4.1 | Chassis and module contract; not contradicted by newer work. |
| BASE-019 | Two example modules: hello shows the features, template is the empty start of every module | Kept | §4.1 | Chassis and module contract; not contradicted by newer work. |
| BASE-020 | Versioning and compatibility | Kept | §4.1 | Chassis and module contract; not contradicted by newer work. |
| BASE-021 | Packaging uses pyproject.toml and uv, and clients start the MCP server with uvx | Kept | §4.1 | Chassis and module contract; not contradicted by newer work. |
| BASE-022 | The repo wheel carries every repo module, and the local build carries the enabled ones | Kept | §4.1 | Chassis and module contract; not contradicted by newer work. |
| BASE-023 | A wheel runs directly, isolated from any installed Metaform's code | Kept | §4.1 | Chassis and module contract; not contradicted by newer work. |
| BASE-024 | A directly run wheel works in hosted code execution environments | Kept | §4.1 | Chassis and module contract; not contradicted by newer work. |
| BASE-025 | A directly run wheel uses the normal data folder | Kept | §4.1 | Chassis and module contract; not contradicted by newer work. |
| BASE-026 | The chassis depends only on the standard library and pure-Python packages | Kept | §4.1 | Chassis and module contract; not contradicted by newer work. |
| BASE-027 | Metaform offers to maintain a user's fork, CI and wheel | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| BASE-028 | Context travels with each operation | Kept | §4.1 | Chassis and module contract; not contradicted by newer work. |
| BASE-029 | Every capability shows which module owns it | Kept | §4.1 | Chassis and module contract; not contradicted by newer work. |
| BASE-030 | Work state never depends on the client that started it | Kept | §4.1 | Chassis and module contract; not contradicted by newer work. |
| BASE-031 | Cancellation is reported truthfully | Kept | §4.1 | Chassis and module contract; not contradicted by newer work. |
| BASE-032 | Every event delivery reaches a terminal outcome | Kept | §4.1 | Chassis and module contract; not contradicted by newer work. |
| BASE-033 | Events announce and deliver; they do not run workflows | Kept | §4.1 | Chassis and module contract; not contradicted by newer work. |
| BASE-034 | Every shipped module has a developer README | Kept | §4.1 | Chassis and module contract; not contradicted by newer work. |
| BASE-035 | The module and verb declarations in full | Kept | §4.1 | Chassis and module contract; not contradicted by newer work. |
| BASE-036 | A verb's result is data, shown the same way on every surface | Refined | §6.3 | One JSON text block overtaken by triage shaping (2026-10-17); results become declared (A2 F3). |
| BASE-037 | Discovery and loading in full | Kept | §4.1 | Chassis and module contract; not contradicted by newer work. |
| BASE-038 | The map module | Kept | §4.1 | Chassis and module contract; not contradicted by newer work. |
| BASE-039 | The intake module | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| BASE-040 | The memory module | Refined | §7 | The memory module per section 7. |
| BASE-041 | The build command | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| BASE-042 | A directly run wheel bootstraps from itself | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| BASE-043 | Optional nouns are written as name=value | Kept | §4.1 | Chassis and module contract; not contradicted by newer work. |
| BASE-044 | Agent submissions are never blocked | Kept | §4.1 | Chassis and module contract; not contradicted by newer work. |
| BASE-045 | Process feedback and intake reports are saved, reviewable and part of provenance | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| BASE-046 | The chassis is fixed, and everything that plugs into it is a module | Kept | §4.1 | Chassis and module contract; not contradicted by newer work. |
| BASE-047 | Installing a wheel goes through an install stage that never downgrades | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| BASE-048 | Metaform ships a metaform of itself, to develop itself | Kept | §4.1 | Chassis and module contract; not contradicted by newer work. |
| BASE-049 | Modules are planned whose details wait for a stable core | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| BASE-050 | An agent reaches its work through its ACP session or by an id the work already has, and the chassis issues no handoff code | Kept | §5.2 | Holds. |
| BASE-051 | A workflow is reusable procedure stored as callable logic, made by ingest or authoring and run by one executor | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| BASE-052 | The dispatch module starts an agent on a ticket through ACP | Refined | §5.2 | One session per ticket stays; record-on-finish goes; its "`on_ticket_done` ships empty" is contradicted by the code (A3). |
| BASE-053 | A module's long-running process hears map changes made in other processes, through the base | Kept | §3.2 | Holds; the relay is the change channel. |
| BASE-054 | Work is shared among six roles, and each holds one job: the person, the orchestrator, the workflow builder, the evaluator, the loop controller and the workers | Dropped | §5.1 | Six roles overtaken twice: GC model (`4f2966c8`), then the owner's removal of the GC (A3). Replaced by 5.1's four roles. |
| BASE-055 | All incoming work goes first to the workflow agent, which writes a short Axiom workflow for it, seeds its rules at the nodes and registers its loops | Dropped | §5.1 | Workflow builder first was never built; the ticket writer names the specialist (A3). |
| BASE-056 | The loop controller in the workflow module owns every loop: code counts the attempts, opens each pass as a ticket and ends the run | Dropped | §5.2 | Reduced to dispatch's recovery (`recovery.py`) and rework limit (`progress.py`), as its own 2026-10-04 amendment advised (A3). |
| BASE-057 | Code raises signals about the work, and the orchestrator decides what to do about them | Dropped |; | Already deleted 2026-10-16; board signals are the system agent's (A3). |
| BASE-058 | Exclude is an ignore list the intake honors, like gitignore | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| BASE-059 | Skills are universal: one folder, deployed where a harness discovers skills, indexed over MCP where it does not, always loadable by address | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| BASE-060 | The build panel: four builds from the web GUI, and a project round trip to a remote agent | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| BASE-062 | Editors mount Metaform as their ACP agent | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| BASE-063 | Refactoring intake prepares reusable knowledge before implementation | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| BASE-064 | Optional bulk provider classification during refactor preparation | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| BASE-065 | Code intake places indexed functions upfront and delegates the remainder | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |

### `05-cli-settings.md`

| Record | Title | Verdict | Into | Why |
|---|---|---|---|---|
| CLI-001 | Commands are verbs, arguments are nouns, switches are adverbs | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| CLI-002 | `all` is an argument | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| CLI-003 | `--` ends switch parsing | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| CLI-004 | Long switches take two dashes, single letters take one | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| CLI-005 | `metaform` alone shows status | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| CLI-006 | `metaform help` is a brief overview ending with tips | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| CLI-007 | `help <thing>` is the man page; `--help` and `-h` give syntax | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| CLI-008 | `help commands` and `help switches` are the indexes | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| CLI-009 | Every error ends with exactly one Next line | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| CLI-010 | One schema drives every surface | Kept | §4.1 | One schema drives every surface; holds. |
| CLI-011 | Every long switch is a setting | Refined | §5.6 | Person-only list partly overtaken by gate removals (`65b11ec5`, `d0985e90`, `222ca950`) (A3). |
| CLI-012 | Module switches are declared once and are settings | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| CLI-013 | Settings have three states: default, set, glued | Kept | §4.3 | Holds. |
| CLI-014 | A stored setting belongs to a folder and its subfolders | Kept | §4.3 | Holds. |
| CLI-015 | Booleans have two forms and never toggle | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| CLI-016 | A glued value inverts with the opposite form | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| CLI-017 | `unset all --unglue` always returns to the safe defaults | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| CLI-018 | `--confirm` is never a setting | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| CLI-019 | Select settings take choices from a list or from module data | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| CLI-020 | Metaform works with zero configuration | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| CLI-021 | Working context is made of ordinary folder settings | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| CLI-022 | Narrowing the command surface hides and blocks, and states the way back | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| CLI-023 | Defaults are never written, and a changed default never replaces a stored value | Kept | §4.3 | Holds. |
| CLI-024 | A module's settings survive while the module is absent | Kept | §4.3 | Holds. |
| CLI-025 | Everything works without prompts | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| CLI-026 | The settings screen | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| CLI-027 | Values of each setting kind on each surface | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| CLI-028 | The status lines | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| CLI-029 | Help page and syntax layouts | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| CLI-030 | Values the context settings accept | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| CLI-031 | The chassis verbs in full | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| CLI-032 | The command tree has a few top-level objects | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| CLI-033 | `--layers` toggles the layers on for a folder | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| CLI-034 | `--debug` and `--report` decide what agents are asked to report | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| CLI-035 | The command line follows mvm's design | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| CLI-036 | Everything a person reads is short, whole and plain | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| CLI-037 | The top menu shows names, and a module's commands are reached inside it | Refined | §6.4 | With MCP-003: commands reached inside modules, typed per command. |
| CLI-038 | The working folder decides what is shown, and holds the continuity of the work | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| CLI-039 | An alias is one top-level name that stands for several modules | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| CLI-040 | `set` and `unset` are for configuration settings only | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| CLI-041 | `metaform start` maps the project in this folder with one command | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| CLI-042 | `metaform demo` shows Metaform at work with one command and no questions | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |

### `06-mcp-install.md`

| Record | Title | Verdict | Into | Why |
|---|---|---|---|---|
| MCP-001 | MCP is a module | Kept | §4.1 | Current; MCP-030 broken by the hardcoded tables (A2 F5), MCP-031 by Python descriptions in `server.py`. |
| MCP-002 | The server speaks MCP over stdio or Streamable HTTP through the official SDK's low-level server | Refined | §6.4 | Listing computed per surface change, not per request (CLAUDE.md section 2; A2 F4). |
| MCP-003 | Each command is one tool, built from the same declaration as its CLI command | Refined | §6.4 | Overtaken by `ec469e74` module-owned discovery; both old and new fail per-command loading (A2 F1). |
| MCP-004 | The tool list follows the folder's command surface | Refined | §6.4 | Overtaken by `ec469e74` module-owned discovery; both old and new fail per-command loading (A2 F1). |
| MCP-005 | Tool arguments follow the command grammar, and booleans appear once | Kept | §6.4 | Holds. |
| MCP-006 | Every tool error ends with one next step | Refined | §5.6 | `person_says` only for acts that cannot be undone (A3 F7). |
| MCP-007 | Server instructions are composed live from the base text and each module's instructions | Dropped |; | Already superseded by MCP-031 and MCP-029 (A2). |
| MCP-008 | Each module adds concise instructions that defer to help | Dropped |; | Already superseded by MCP-031 and MCP-029 (A2). |
| MCP-009 | A folder with no intake gets the onboarding, registered or not, and an aborted intake is named | Refined | §6.1 | Onboarding is the `metaform://firstrun` block for the person's own sessions; it must not pre-empt the request (A2; AP PROMPT-03). |
| MCP-010 | AI tools start the server with uvx | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| MCP-011 | The server serves the right project when the host starts it outside the project folder | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| MCP-012 | Remote hosting comes later | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| MCP-013 | Setup checks first | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| MCP-014 | The installer asks by default, and named tools or `all` set up without asking | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| MCP-015 | A preview comes before AI setup writes, and every changed file is backed up | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| MCP-016 | Each tool is registered through its own mechanism, per OS | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| MCP-017 | Setup proves each tool can start the server | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| MCP-018 | Setup ends with a finish screen and one next step | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| MCP-019 | Running setup again is safe | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| MCP-020 | `metaform uninstall` removes what setup added | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| MCP-021 | One fixed skill is copied to each chosen tool's global skill folder | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| MCP-022 | Each skill path is proven by the tool loading the skill | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| MCP-023 | The installer works on Linux, macOS and Windows | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| MCP-024 | The first working test runs installer, instructions and delegation end to end | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| MCP-025 | Every tool takes an optional project | Refined | §6.4 | `project` is also withheld from dispatched agents (`mcp/server.py:190`, A2); the record says so. |
| MCP-027 | Offering an intake, the agent suggests a blind spot challenge and a best-practices layer | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| MCP-028 | An unfamiliar harness is asked on its first run to provision what it supports | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| MCP-029 | The connect message is an order: use Metaform, what each module is for, then read the glossary | Refined | §6.1 | Overtaken by the block links and `a0f67e19`: every linked block read whole; own role only; no repeats (A2). |
| MCP-030 | An agent reaches the work handed to it over MCP by its ACP session or by the work's own id, as on the command line | Kept | §4.1 | Current; MCP-030 broken by the hardcoded tables (A2 F5), MCP-031 by Python descriptions in `server.py`. |
| MCP-031 | Prompts are authored in XML files, addressed by name, and never written in Python | Kept | §4.1 | Current; MCP-030 broken by the hardcoded tables (A2 F5), MCP-031 by Python descriptions in `server.py`. |
| MCP-032 | Slash commands are MCP prompts the server serves, each running at most one verb | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| MCP-033 | The slash commands are prompt, tasks, messages, intake, refine, web, config and status | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| MCP-034 | The workflow agent is a skill the Metaform MCP server serves, so every harness reads the same text | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| MCP-035 | Every prompt is a complete set of instructions: what to do, how, how it works and when | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| MCP-036 | Installation reaches agents opened directly in their harness | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| MCP-037 | What an agent needs is served as resources, every address resolves, and every command's arguments are in its tool | Refined | §6.1 | Glossary is `metaform://metaform`; `metaform://<module>/tools` added; `metaform://tools` removed (A2). |
| MCP-038 | A next step read over MCP names the tool call or resource, never a command line | Kept | §6.3 | Holds. |
| MCP-039 | An agent is told what is at its node as counts with the calls that read them, once per agent session | Refined | §6.2, §6.5 | Merged with CTX-041 into one ledger; "never what it holds" overtaken for the worked node by CTX-040 (A2). |
| MCP-040 | Metaform talks to the A2A peers the person names, and to no other | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| MCP-041 | An agent sends a peer a message about an Address, and follows it to its end | Refined | §1.2 | The follower re-reads a peer on a timer on the server loop; move to a dedicated worker or an event (AM). |
| MCP-042 | Every A2A message says which agent sent it, and Metaform checks it | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| MCP-043 | An exchange survives restarts | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |

### `07-quality.md`

| Record | Title | Verdict | Into | Why |
|---|---|---|---|---|
| QUAL-001 | The code quality standard is the bar | Kept | §9.1, §9.2 | Holds. |
| QUAL-002 | Everything works on Linux, macOS and Windows | Kept | §9.1, §9.2 | Holds. |
| QUAL-003 | CI proves cross-platform on every change | Kept | §9.1, §9.2 | Holds. |
| QUAL-004 | Strict type checking of the common base and the chassis | Kept | §9.1, §9.2 | Holds. |
| QUAL-005 | One lint configuration | Kept | §9.1, §9.2 | Holds. |
| QUAL-006 | Tests exist only to protect the design | Kept | §9.1, §9.2 | Holds. |
| QUAL-007 | A test-gaming review agent checks the tests | Refined | §9.3 | Review agents run once on a finished build when asked, never as a ticket per change (cost audit). |
| QUAL-008 | A critic review against the standard before merge | Refined | §9.3 | Review agents run once on a finished build when asked, never as a ticket per change (cost audit). |
| QUAL-009 | Traceability between requirements and tests | Kept | §9.1, §9.2 | Holds. |
| QUAL-010 | Lifecycle checks where the standard names a real risk | Kept | §9.1, §9.2 | Holds. |
| QUAL-011 | The cold build check of this spec | Kept | §9.1, §9.2 | Holds. |
| QUAL-012 | The existing chassis tests are reviewed against the spec | Kept | §9.1, §9.2 | Holds. |
| QUAL-013 | Documentation shows who owns what, and there is one current contract | Kept | §9.1, §9.2 | Holds. |
| QUAL-014 | Fixtures, simulations and real runs are named for what they are | Refined | §9.1 | A lifecycle change is proven by one real run; none exists for filed to done (A3). |
| QUAL-015 | No polling and no blocking | Kept | §1.2 | Holds. |
| QUAL-016 | A capability added for a feature reaches every module author | Kept | §4.1 | Holds. |
| QUAL-017 | Removing needs the same permission as building | Kept | §9.4 | Holds. |

### `08-projects.md`

| Record | Title | Verdict | Into | Why |
|---|---|---|---|---|
| PROJ-001 | A project is a registered source location with all its Metaform data in the home | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| PROJ-002 | A working folder is a key in the home, and every folder gets its own context | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| PROJ-003 | A folder's project defaults to the project that contains it, and selection follows the settings pattern | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| PROJ-004 | Selecting a project records the orchestrator's working folder, which is also how work resumes | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| PROJ-005 | Every surface resolves the project the same way, including a server started outside any project | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| PROJ-006 | A worktree is its own working folder wherever it lives | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| PROJ-007 | A worker's own folder can carry a narrowed context while the orchestrator keeps its own | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| PROJ-010 | History is chassis data kept in the home | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| PROJ-011 | Every history operation uses the same artifact boundary | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| PROJ-012 | An origin records the commit it is based on | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| PROJ-013 | Origin identity has a long form and a short form | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| PROJ-014 | An origin is never overwritten, and a new baseline starts a new origin unit | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| PROJ-015 | Variants of one origin are siblings | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| PROJ-016 | A variant stores only what changed against its origin | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| PROJ-017 | Collecting a worktree or workfolder keeps it as a variant, committed or not | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| PROJ-018 | Any variant, several, or all reconstruct with Python alone | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| PROJ-019 | Web variants can be served side by side | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| PROJ-020 | The export unit is a whole origin unit, delivered as a wheel | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| PROJ-021 | Import never loses data | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| PROJ-022 | Pending physical work travels with continuation | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| PROJ-023 | History records and payload layout | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| PROJ-024 | History commands | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| PROJ-025 | Clearing a project removes its metaforms and its reports, and keeps everything else | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| PROJ-030 | A clear backs the project up first, and a backup is brought back by one command | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| PROJ-031 | An empty project is taken off the list by one command, and nothing of it is deleted | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| PROJ-026 | A project's folder in the home holds everything of the project | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| PROJ-027 | A project is exported as a plain zip whose provenance and data are sealed inside it | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| PROJ-028 | A restored project comes in under the next number | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| PROJ-029 | A small source is kept whole, with no diffs | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |

### `09-viewer.md`

| Record | Title | Verdict | Into | Why |
|---|---|---|---|---|
| VIEW-001 | Metaform has one web GUI, and the viewer is its first view | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| VIEW-002 | The web GUI is one server for the user, on one fixed port, started with `metaform web` | Refined | §8.2 | "Every 5 s" watchdog and "every 2 s" page health checks overtaken by the code and CLAUDE.md section 1 (A5). |
| VIEW-003 | The viewer works offline with every script bundled | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| VIEW-004 | The viewer reads only through the data access object and follows every visibility rule | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| VIEW-005 | The 3D view floats the metaform in space in its tripartite form and untangles it | Refined | §8.6, M5 | Overtaken in fact by `0019ec90` (joins drawn without a purpose vertex); owner decides (A5). |
| VIEW-006 | Edges and nodes are colored by layer and by kind | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| VIEW-007 | Viewing never changes settings; a separate control applies the layer choice | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| VIEW-008 | The left window holds the whole map in 2D, and the camera moves to the selected object | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| VIEW-009 | The inspector shows everything about the selected object | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| VIEW-010 | The viewer stays responsive through rendering technique, not by hiding structure | Refined | §8.6, M5 | Overtaken in fact by `5ebf9f8a` (`web_map_depth=auto` collapses maps over 200 parts); owner decides (A5). |
| VIEW-011 | The viewer writes exactly eighteen things | Refined | §8.3 | "Exactly eighteen" overtaken (62 POST routes, A5); its CLI-process Build is defect D2. |
| VIEW-012 | The viewer is accepted by hand and by automated checks | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| VIEW-013 | The viewer shows provenance, and prompts can be edited as new versions | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| VIEW-014 | Correction layers are removed one at a time from the top, with a warning | Refined | §2.4 | Correction layers were overtaken by LAYER-025; the record is checked against the page before its text is changed. |
| VIEW-015 | Before an intake, agents start the web GUI and tell the user its address | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| VIEW-016 | Going inside a node replaces the 2D map with the node's own graph | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| VIEW-017 | In 3D, every item of the layers turned on is its own node | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| VIEW-018 | Open pages follow every change to the map; nothing polls | Refined | §8.2 | Holds; names `app.js` where code is `live/ops.js`; adds "never replace another view's set" and "read past the last line" (A5). |
| VIEW-019 | The page clears the selected project after saying what goes and what stays | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| VIEW-020 | Each node's look shows the state of the work on it | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| VIEW-021 | An open question glows at its node, and a Messages button leads to the oldest | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| VIEW-022 | Clicking a property node shows its reach | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| VIEW-023 | The page offers a variety of color themes, and the graph stands clear of the background in each | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| VIEW-024 | The page exports the map from a menu, as Markdown or XML | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| VIEW-025 | The nodes are drawn as a material that obeys reality, in every theme | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| VIEW-026 | A property's reach travels as a wave | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| VIEW-027 | A part not built yet is a ghost | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| VIEW-028 | The two views change places on demand | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| VIEW-030 | A right-click on a node opens its menu, and messages are read in a floating window | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| VIEW-032 | A task is added at a node from its menu, in an editor that links nodes and names them inline | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| VIEW-033 | A person adds an element to the map and joins it, and an agent can validate it first | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| VIEW-034 | A node holds one note, the person's | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| VIEW-031 | The memories of a node open as a graph of their own | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| VIEW-029 | A node that needs attention gives off light, in both views | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| VIEW-035 | A ticket is a light on its node, and the agent working it walks the map to the node and circles it | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| VIEW-036 | A node's menu opens its work history | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| VIEW-037 | A classic kanban board of the project's tickets | Refined | §8.5 | Intent holds; "it reads `work`" is how whole-record reads came about (A5 R4). |
| VIEW-038 | The 3D labels wrap, read clearly, keep the draw order, and the hover says what a part does | Refined | §8.6, M5 | Depth-order sentence stays; look overtaken by `9a887f1b`; "15 times a second" rest contradicts CLAUDE.md section 4 rule 5 (A5). |
| VIEW-039 | Agents are started on tickets, followed, messaged and stopped from the page | Refined | §5.3, §8.1 | Verbs run in process; only the runner is a process (plan C10). |
| VIEW-040 | Agent glyphs on the board, and work distributed over N agents | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| VIEW-041 | The 2D map is in one of seven modes, and its mode alone sets its zoom | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| VIEW-042 | A question never holds up work: agents keep working or exit, a question opens a chat, and Autostart agents decides what starts | Refined | §5.3 | Autostart renamed Full Auto; a start is never refused for want of a specialist (A3). |
| VIEW-043 | Consensus mode: when every open ticket is frozen on a question, voting agents settle what they agree on, and only a write-in, a comment or a tie waits for the person | Dropped | M7 | Proposed retirement: no newer functional need established (A3). PM must obtain M7 before removal. |
| VIEW-044 | A worktree that passes its tests and merges cleanly waits fifteen minutes for review, then merges itself, unless the person steps in | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| VIEW-045 | The person meets purpose-defined agents only: an issue raised on a node starts a sentinel that brings proposals | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| VIEW-046 | Upstream and downstream are shown as toggles beside the layers | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| VIEW-047 | The map is searched from the header, and a result chosen is selected in both views | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| VIEW-048 | Windows stack, Escape closes the top one, and what can be put back is undone rather than asked | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| VIEW-049 | The build panel is a window of the page | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| VIEW-050 | A2A exchanges are shown where the work is | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| VIEW-051 | Every error shows on screen, with what happened, the next step and Report a problem | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |

### `10-world.md`

| Record | Title | Verdict | Into | Why |
|---|---|---|---|---|
| WORLD-001 | The playground is one world per project, and the log of its operations is its authority | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| WORLD-002 | Modules declare tabs, and the tabs take the place the map toolbars held | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| WORLD-003 | Every operation names its kind, its entity, its actors and the revision it was planned from | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| WORLD-004 | An entity carries `functional_refs`, which tie it to the Metaform nodes it stands for | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| WORLD-005 | An in-world act and an out-of-world edit are two classes of operation in one log | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| WORLD-006 | Undo is a read of the log and an operation appended to it | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| WORLD-007 | The world survives a reload because the log is the only thing that is stored | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| WORLD-008 | The world host is an interface, so the page hosts the world now and a server can later | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| WORLD-009 | `web_see` answers at a level of detail, with a field of view the agent sets | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| WORLD-010 | Every act answers with what changed | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| WORLD-011 | Targets are named by address and relation, and every number carries its unit and frame | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| WORLD-012 | A seeded tick record lets any moment be replayed with the input the model had | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| WORLD-013 | What cut 1 does not include | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |

### `11-context.md`

| Record | Title | Verdict | Into | Why |
|---|---|---|---|---|
| CTX-001 | The base map is the intake's alone and holds only elements and purpose joins | Kept | §2.4 | Holds; CTX-001 guard not built (A1 F5). |
| CTX-002 | Nothing in the base travels | Kept | §2.4 | Holds; CTX-001 guard not built (A1 F5). |
| CTX-003 | Genre, style, medium and encoding stay out of the base during intake and are recorded as knowledge after it | Kept | §2.4 | Holds; CTX-001 guard not built (A1 F5). |
| CTX-004 | Everything the intake did not make is a property held in a knowledge layer | Refined | §2.5 | Overtaken by scoped knowledge (`c4f449fc`): explicit attachment, instruction items inherit, ordinary items local, joins never travel (A1 section 0). |
| CTX-005 | Every property layer is the same kind, and medium is one example among many | Kept | §2.5 | Holds. |
| CTX-006 | A property applies at its link Address and at every Address above it toward the leaves, on every branch | Refined | §2.5 | Overtaken by scoped knowledge (`c4f449fc`): explicit attachment, instruction items inherit, ordinary items local, joins never travel (A1 section 0). |
| CTX-007 | A property is visible toward the trunk without applying there, and siblings do not inherit it | Refined | §2.5 | Overtaken by scoped knowledge (`c4f449fc`): explicit attachment, instruction items inherit, ordinary items local, joins never travel (A1 section 0). |
| CTX-008 | A property has one link to one base Address | Refined | §2.5 | One link per property record; scoped attachments supersede the rest (A1). |
| CTX-009 | When a property is recorded on another branch, its link moves toward the trunk to where the branches meet | Dropped |; | Automatic move toward the trunk never built; overtaken by explicit `link-context`. May return as an option (A1). |
| CTX-010 | Any Address that does not exist can be created | Kept | §2.5 | Holds. |
| CTX-011 | Naming a new node makes a knowledge layer for it | Refined | §2.5 | Dotted CEL names; `scope@content` names stay readable (`c4f449fc`). |
| CTX-012 | Porting is a layer swap, and the base never changes | Kept | §2.4 | Holds; CTX-001 guard not built (A1 F5). |
| CTX-013 | Hiding a layer hides everything attached to it, its memories included | Kept | §2.6 | Holds. |
| CTX-014 | A property layer bound at a function is inherited by everything under that function | Kept | §2.5 | Holds. |
| CTX-015 | Clicking an item or the node it is linked at makes the path where it applies glow, on both maps | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| CTX-020 | A memory is what an agent writes because it will help other agents, kept in the memory graph at an Address | Refined | §7.1, §7.4 | Requirement sentence matches the direction (`d0985e90`); its Why, How it shows ("an entity of type `fix`") and Build still argue the replaced work-history definition (A4). |
| CTX-021 | Knowledge is what is true of the project, and it is written to knowledge layers, never to memory | Refined | §7.5, M2 | Conflicts with category d of CTX-026's 2026-10-17 block; held for the owner's ruling (A4). |
| CTX-022 | Any agent may create, read, update or delete any memory | Kept | §7.4 | Holds; no ownership checks, as the reference. |
| CTX-023 | Every agent can read a locked memory, and no agent can change or delete it | Kept | §7.6 | Holds; CLI only. |
| CTX-024 | A memory applies at the Address it is linked at and at every Address above it toward the leaves | Kept | §7.2 | Holds as intent; CTX-024 not built (A4 defect 5). |
| CTX-025 | Memories are related to each other across Addresses | Kept | §7.2 | Holds as intent; CTX-024 not built (A4 defect 5). |
| CTX-026 | Every agent works by the owner's memory prompt, sent word for word | Refined | §7.5, M1 | The shipped element is not the record's 2026-10-17 block; it was replaced in `4f2966c8` (`git log -S`). Owner names the text. |
| CTX-027 | The memory prompt is filled with the project and the agent's assigned element | Kept | §7.5 | Holds; fill matters only if the approved text has places. |
| CTX-028 | The memory prompt is sent once per session, with the first context pushed, and again after a compaction | Kept | §7.5 | Holds; fill matters only if the approved text has places. |
| CTX-029 | No prompt tells an agent to put everything it learns in memory | Refined | §7.4, §7.5 | Its reasoning rests on memory as work history; the dropped rule against activity logs is right again (A4). |
| CTX-030 | The existing memories are reprocessed into memory and knowledge, nothing lost, on a copy first | Dropped |; | Historical clear instruction: "Delete every fucking memory now." (`f9f108ee`, 2026-10-20T00:44:20Z); the live graph was emptied then (A4). The pre-clear copy `memory.sqlite3.before-clear-2026-10-18` remains. |
| CTX-040 | What applies where an agent works is pushed to it; the agent does not fetch it | Refined | §6.5, §7.3 | Push is the node summary and instruction items; memories are a count on arrival (2026-10-19 change, `memory/resources/prompts.xml` comment) (A4 defect 8). |
| CTX-041 | Nothing is pushed twice in one agent session | Refined | §6.2, §7.3, M3 | "At most once" stays; one chassis ledger; edit question to the owner. |
| CTX-042 | Where an agent works is known from what it does, placed exactly by refs | Kept | §6.5 | Holds. |
| CTX-043 | A push waits for the agent's next turn and never interrupts the turn in flight | Kept | §6.5 | Holds. |
| CTX-044 | What does not fit the node summary budget is listed by reference | Kept | §6.5 | Holds. |
| CTX-045 | A compaction clears what the session was sent and pushes nothing by itself | Kept | §6.2 | Holds. |
| CTX-046 | Compaction is known only from ACP's compaction signal | Kept | §6.2 | Holds. |
| CTX-047 | A resumed session keeps what it was sent when its conversation reopens | Kept | §6.5 | Holds. |
| CTX-048 | One agent session is one record across its processes, and an HTTP client is named by a header | Refined | §6.4 | Session named by `Mcp-Session-Id` or a provisioned header, never a model-passed `session_handle` (A2 F5). |
| CTX-049 | Agents connected over MCP get the same pushes on calls naming an Address | Kept | §6.2 | Holds. |
| CTX-050 | Something written at a node an agent has worked at reaches it without a fresh visit | Refined | §7.3 | Mid-work pushes overtaken by the arrival-only rule; a change reaches the agent as a count on its next arrival. |
| CTX-060 | A file of the project that no ref names exactly is locked for writing until it is linked to its function | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| CTX-061 | The lock holds in every permission mode, ahead of every automatic approval | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| CTX-062 | Writes are prevented before they land, never caught after | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| CTX-063 | One call links a file to the element it realizes and lifts the lock at once | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| CTX-064 | Paths the project's ignore list holds are read-only to agents, always | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| CTX-065 | A ref is a stable record in the sources layer, on an element or on a join | Kept | §2.3 | Holds. |
| CTX-066 | A ref is named {ref_id}@{address}:{join} | Kept | §2.3 | Holds. |
| CTX-080 | What was called logic is called prompt: the prompt root, the prompt layer, prompt joins and add_prompt | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| CTX-081 | Any join can store a prompt, held in the prompt layer | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| CTX-082 | Every module prompt has the address prompt.<module>:<tag> | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| CTX-083 | The Agents module tracks each role's prompts by their addresses, served through the prompt store, so an override is what agents are sent | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| CTX-084 | {this} in a prompt is the node being worked on, read with its stored field names | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| CTX-085 | Refs read flat on {this}, by their names | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| CTX-086 | The intake names each element's main artifact ref main | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| CTX-087 | Field names that are nouns are reserved and cannot be ref names | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| CTX-088 | Elements and joins of the base hold no note, and every note already there moves word for word to the critic layer | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| CTX-089 | The person's note is the one note at a node, and only the person writes it | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| CTX-090 | The person's note is pushed whole to an agent working at its node, once per session | Kept, carried | §10 | Not assessed against function in this pass; no review found it blocking. |
| CTX-091 | Metaform never gates or judges inference; it enforces mechanics only | Kept | §1.4 | Holds; supports the start-path change (A3). |
