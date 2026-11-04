# roundtables

Brings the person's question to agents through the Roundtable 2 engine, which ships inside this module. The page shows the finished synthesis, rankings, answer and saved transcript. Roundtable Follow-through prepares research, architecture, intake, a plan, detailed tickets and an execution outline through assigned tasks. The system controls stage progression without a coordinator agent.

## Purpose

A question gets better answers from several agents than from one: each adds what it does best, optional Jev judging (through OpenRouter) filters novelty, a synthesizer names the ideas collected, every seat ranks them and explains its choices, and a host summarises. Its main use is brainstorming, an idea that is not in the project yet, so the question is the table's whole frame: it is limited to no part and to no project. An Address given focuses it on that part, whose context from the map opens the table. Its seats read the project's folder when the question touches it, and its record stays with the project. The page shows the finished synthesis and answer beside links to the saved record.

## Template version

The template changelog version this module started from: 0.3.0.

## Declaration

`SUPPORTED_OS` is Linux and macOS: a table's follower and the engine's servers are detached into a session of their own. `DEPENDENCIES` is the shipped engine's own requirements: `mcp`, `agent-client-protocol`, `a2a-sdk[http-server]`, `httpx` and `uvicorn`. `SHIPS_DISABLED` is false. `MODULE` declares the verbs below and the tables.

### Toolbar items and panes

None of its own. The web page's roundtable stage (web, `page/app/roundtable/stage.js`) opens a table and shows it through the web server's `/api/roundtable-open` and `/api/roundtable`, which run `open`, `events` and `status`. The person asks the question once and then only watches; the chair's verbs are for the command line and agents.

## Common base used

`metaform.settings` declares the settings and reads `jev` and dispatch's agent commands. `metaform.data` gives the module's own tables. `metaform.outline.markdown` writes the part as the opening holds it, and `metaform.module.node_items` lists the memories at it. `metaform.module.provided` finds dispatch's `dispatch.seats` and design-intake providers, plus `task.lifecycle`. `metaform.events.announced` announces each write of a follower, and `Context.publish` publishes `roundtables.event`. `metaform.prompt_files` serves `resources/prompts.xml`. `metaform.home` places the logs. Nothing else of Metaform is imported.

### Provides

Nothing. It uses dispatch's `dispatch.seats` and design-intake providers, tasks' `task.lifecycle`, and memory's `memory.record`.

## Prompts

`resources/prompts.xml` holds `connect`, `instructions` and `rules`; `opening_question`, which every seat of a table with no Address reads first, the question alone; and `opening`, which every seat of a table about a part reads first, filled with `address`, `part` (the element and the joins it receives and provides, with their purposes and encounter functions), `memories` (the titles of the memories at the part, `no_memories` when none) and `question`. The engine adds its own discussion instructions and the topic after either. `outcome_*` the memory a table leaves; `adopted*` an adopted idea's ticket.

The `session_*` prompts hold the person's session messages. The participating agents jointly author their own
documents in the shared session folder. There is no automatic minutes or summary writer.

## Verbs

- `open <topic> [address=] [seats] [host=] [synthesizer=] [judging=] [reply_limit=] [spend=]`, write, open world: open a table on the question, focused on the part at `address` when one is given. `seats` is a JSON list in speaking order, `roundtables_seats` when left out: `claude/<model>`, `codex/<model>` and `antigravity/<model>` are Metaform's own agents, seated on the engine's ACP client with dispatch's commands (`dispatch_claude`, `dispatch_codex`, `dispatch_antigravity`); any other id is an OpenRouter model. The host is the first seat when none is named, never the engine's own default, which would seat an agent nobody chose. The question is the table's one topic. `reply_limit` sets the maximum characters in each discussion reply, 512 by default. The selected limit ends the opening instructions and each turn prompt; longer replies are truncated before judging. Synthesis, ranking explanations and reports retain their stage-specific limits. Judged tables require `jev` and an OpenRouter credential. ACP-only tables with `judging=false` require neither; when fewer agent slots are free than seats; and when `spend` passes `roundtables_spend`. Returns the table's id.
- `comment <table> <text>`, `hold <table>`, `continue <table>`, `advance <table>`, `reseat <table> <seat>`, `end <table>`, write, open world: the chair's controls, as the engine offers them, passed with the table's chair token.
  The GUI exposes Hold, Continue, discussion comments and End discussion beside the transcript. End discussion invokes `advance` immediately at the next gap, without minimum rounds. Comments can be queued while held, without resuming AI turns. They enter at the next gap between turns. Continue resumes the same table. On a completed table, Continue discussion uses its saved host summary with fresh seat contexts, the same visible identity, project and lineup. It appends a topic without removing prior topics or outputs. Plan review comments remain separate.
  Start remembers the participant lineup in this browser per project. Save participants stores the chosen order and models in the existing `roundtables_seats` project setting without starting agents. A fresh browser uses those defaults.
  ACP seats use the project as their workspace. Their harnesses provide file tools and request permissions through ACP.
- `permit <table> request=<id> option=<id>`, command line or page: return the person's selected option to the waiting
  ACP request. Requests not covered by the selected standard prompt policy display the options supplied by the agent.
  Setup shows the same permission controls as an ordinary agent launch, once per selected agent type. The
  `permissions` object maps agent names to `prompts` and native ACP `mode`; omitted choices use project settings.
  Choices are captured when the table opens and persist through panels, collaboration, and recovered seat sessions.
- `status <table> [report=true]`, read: the table's state, seats, spend, follower, answer, every topic's synthesis and rankings as `topics`, `saved`, `recorded`, and `report`, the mechanical transcript's saved path. `report=true` includes its text as `report_text`.
- `tables`, read: every table of the project, newest first.
- `events <table> [after=<seq>]`, read: the table's events after a cursor.
- `follow <table>`, write, open world: start a table's follower again when it stopped before the table ended.
- `adopt <table> <idea> [address=] [title=]`, write, the person's decision, secondary to the report: an idea of an ended table, by its id (`I2`), made one ticket of kind enhancement. On a table about a part, the ticket is at the part the idea concerns, the table's Address unless `address` names another; an `address` with no current element on the map is filed as given, and the answer passes on the map's notice that says so. On a table with no part, an idea may concern nothing that exists yet, so it is never forced onto a nearby element: the ticket is at `address` when the map holds that element, else at the project's top element (its DE, else its first root element), with the named Address in its note as `proposed`; nothing is added to the map. Its task carries the idea, the question, the answer and the report (the saved record before the report is written); its note names the table as its source. It is held by no one, so Full Auto starts it like any ticket. Kept as the table's `adopted` event, so adopting the same idea again gives the same ticket. An agent's call is refused with the caution and the command the person runs.
- `run <table>`, command line only: the follower itself, which `open` and `follow` start detached.

## Settings

- `roundtables_spend`, 2, the person's: the most US dollars one table spends through OpenRouter; `open` may only lower it.
- `roundtables_token_budget`, 0: reported input, cached input and output tokens per participant per panel and per
  collaboration. Zero disables the limit. Setup captures this default, and `budget <table> <token_budget>` or the
  live budget control changes the limit without clearing usage already recorded in the current phase.
  A runner started before token-budget support must first be held, finish stopping, and be continued to load the
  new code. Live edits refuse that older active runner rather than claim enforcement it cannot provide.
- `roundtables_seats`, `claude/opus`, `codex/astra`, `codex/sol`, `claude/fable`, the person's: the seats, in speaking order, of a table opened without any named, as the page's stage opens one. A model is a short name, such as `opus` or `sol`, which means the newest release of its family when the table opens, or an exact value, such as `gpt-6-sol`, which pins one; one the agent does not offer is refused, naming the nearest.

## Completion and context handoff

Discussion finishes when every participant voluntarily replies PASS in one complete round, the person chooses End
discussion, or any participant reaches 120% of its configured token budget. Vetoes, failures, skipped turns, round
counts and context size never imply PASS. Comments and context handoffs reset prior votes. Credit recovery requires
explicit Continue. An exhausted dollar budget can be replaced with `continue <table> spend=<amount>`, within
configured caps.

With a token budget enabled, the first participant to reach 50% and 80% triggers warnings for everyone. At 100%,
agents receive closing instructions. At 120%, discussion advances into collaboration, or collaboration advances to
the submitted next topic without waiting for every DONE. After the final collaboration, scoring follows. Each new
panel and collaboration starts fresh per-participant counters with the same configured limit. Agents can finish
earlier through the normal PASS and DONE flow. Usage is counted once per completed physical turn, including PASS
and carry-forward replies. Cached tokens count once, and reasoning tokens already included in output are not added
again. Context-window occupancy is not spent usage. Agents that omit usage cannot trigger a measured cap. A long
turn can overshoot a threshold before its usage report arrives. Saved shared documents survive automatic advancement.

`roundtables_judging` selects the default novelty filter. Setup exposes the same choice for each new table. With judging off, every substantive reply is retained within the existing character reply limit, including repetitions. Synthesis, ranking, explanation and host stages remain unchanged.

`roundtables_context_tokens` sets the common seat/editor handoff trigger, 24,000 estimated tokens by default. The engine's `config.toml` can lower individual triggers through `[context_budgets]` keyed by exact seat id. `roundtables_judging_context_tokens` defaults to 24,000 and applies only while judging. The smallest active trigger wins. Request framing, participant notes and editor output reserve additional headroom. Estimates include original instructions, seat history, shared continuation, new turns and judging criteria. Native TypeSafe documents 64K per request and 32K per question at https://docs.typesafe.ai/models. The OpenRouter route has no confirmed higher effective limits. No native long-context header is enabled.

Before exhaustion, every participant receives a carry-forward request at twice the discussion character limit. Notes retain attribution and exact text outside novelty filtering. One fresh synthesizer context edits shared continuation, preserving original person instructions, decisions, evidence references, disagreements and open questions. Code attaches every intact note to the shared continuation. Seat sessions start afresh. The visible transcript retains all original turns and adds a context-handoff marker. Saved notes survive a failed editor request, so Continue retries the unfinished step. Unjudged tables use the same handoff independently of Jev.

A held runner closes its seats. Comments remain queued or enter without resuming turns. Explicit Continue restarts it. Starting an engine server never resumes other live or held tables.

Opening with `chain=<number>` runs a session containing that many discussions. After each discussion, agents collaborate
on saved materials and the next topic. The page uses this session flow even for one roundtable. During panels and
collaboration, busy seats are skipped immediately while available seats contribute in a fair rotation. When all seats
are busy, the runner waits for completion or chair-control events. No timed cycling is used. A skipped seat never
supplies an implicit PASS or Done. Collaboration normally waits for every participant to finish. Its 120% token cap
advances without that barrier. `next-topic.md` must contain the next topic before another panel opens. If it is
missing, the table holds with a clear reason instead of inventing a topic.

After the final collaboration, each agent submits private scorecards. Only aggregate scores are shared and added to
profiles. Agents then exchange farewells and explicitly finish. The document browser reads their shared session folder.

Roundtable agent connections offer ACP v2 and retain ACP v1 support. Each connection uses its negotiated protocol.
In v2, the prompt response acknowledges insertion and `state_update` reports activity and completion. In v1, the
prompt response completes the turn. Permission requests use the same ACP relay for every agent.

A peer selecting v1 is reconnected with v1 initialization so its capabilities are advertised correctly. A peer that
rejects v2 or returns legacy initialization fields gets the same fresh v1 negotiation. Authentication, session and
runtime failures never change the selected protocol. Cancellation closes active work and outstanding requests.

Initialization checks on 2026-11-04 verified v2 with Claude `0.100.0` and Codex `2.5.0`. Antigravity `1.4.5` returns
legacy fields when offered v2 and negotiates a valid v1 connection when offered v1.

## Events

A follower publishes each event of its table on the bus as `roundtables.event`, `{table, seq, kind, audience, ...}`, and writes it to the `events` table in the same transaction as the cursor that says it was told; that write's `map.changed` names the kind `roundtables` and the table's own, `roundtables:<table>`, so a page watching one table reads only for it, and so every other process of the home, the web page's server among them, hears it and reads the one table's events after the seq it holds. Kinds: `turn` and `veto` (a seat's turn, kept or vetoed, with its scores), `stage` (the open topic and its stage), `ideas` (the synthesis), `rankings`, `summary` (the host's), `state`, `seat_lost` and `operational` (the engine's operational events), `end` (with `answered`, `answer`, whether the report was saved, `saved`, the folder of the saved files, and `recorded`, the memory's name, or `unrecorded` and why), and `adopted` (an idea made a ticket, with its `work_id` and `address`). `state`, `seat_lost`, `operational`, `end` and `adopted` have the audience `person`: they are the person's, and nothing of them goes to a seat or Jev.

The follower hears the table through the engine's own page server, started for it alone on a free loopback port with a token only it holds: the page's events stream says when anything of the table moves, and the follower reads only what moved. That server looks at the engine's store about once a second, in the engine's process; nothing here waits on a clock.

## Guardrails

- Each seat takes one of dispatch's agent slots for as long as its seats run, and a follower that stops ends its table first, through dispatch's own admission gate, so tables and tickets share `dispatch_agents` and `dispatch_machine_agents`. A table needs a slot for every seat when it opens; dispatch off refuses it, since nothing would count them.
- A table spends at most `spend`, at most `roundtables_spend`, through OpenRouter; the engine also holds its own most.
- Each agent's harness provides its native tools. ACP carries permission requests and the person's selected responses.
  Session prompts describe the work and phase. Metaform sets no Claude-specific tool allowlist or file permission gate.
- Operational events reach the person. Token-budget instructions also reach seats at their next available turn,
  outside novelty judging.
- The tables and their events are in the project's store, so a base switch, a clear or a restore never takes them.
- The page shows the engine's result directly. The system pipeline assigns preparation tasks. The engine's reporter output is not saved or shown by this module.

## What a table leaves in the project

When a table ends, its follower saves the record and keeps its outcome as a memory. Its end event and status supply every topic's synthesis, Borda order and points, the final answer and saved record location. The page shows this result immediately and keeps it available when the person leaves and returns. New table starts another discussion.

- The record is saved under `docs/roundtables/<n>-<topic>/` in the project's folder, `<n>` the engine's number for the table and `<topic>` the question in lower-case words: `export.json` (the engine's export, with every turn, every topic's rankings and the Borda count derived from them) and `mechanical-report.md` (the engine's text of the record). A resumed follower keeps the folder. Explicit completed-table continuation writes its next complete record under `continuation-<n>/`, preserving earlier files and stage outputs.
- One memory is recorded at the table's Address, or at the project's top element for a table about no part, through memory's `memory.record`, under memory's own rules, its writer `roundtables`: the question, the host's answer, the top three ideas by the Borda count with what the synthesis said of each, each seat's explanation of its top three, where the record is saved, which it cites, so the memory is marked stale if the file changes. Each engine text is quoted whole as one observation. Memory is what happened at the table; what it established about the project is the person's to judge, through `adopt` or knowledge an agent writes later, and the follower writes no knowledge layer item itself.
- `status` shows `saved`, `recorded` and `topics`; `report` names the saved mechanical transcript, with its text included by `report=true`. The page links the transcript and complete export through `/api/roundtable?project=<project>&table=<table>&file=mechanical-report.md` or `file=export.json`. Only these saved record filenames are accepted. With memory off, or no element on the map, the files are still saved and the `end` event says why nothing was recorded.

## Follow-through

After a table ends, its saved result stays on the page and its seats are released before preparation starts.
The system pipeline controls progression. It starts no coordinator or presentation agent.
Both direct and guided tables enter this same preparation flow. Preparation tickets attach to the source map
at the table's functional Address or its top element.

Each output stays available with its question. Only the person's current decision starts the next stage:

1. Roundtable result -> Researcher.
2. Research -> Architect.
3. Architecture -> existing intake, creating the design's separate project and functional map.
4. Completed intake -> Planner in that project.
5. Full plan -> separate plan review. Comments stay in review. Return to Planner starts a fresh revision.
   Only approval starts Decomposer.
6. Decomposer -> a system-written execution outline containing the board and every ticket's id, title,
   stored completion dependencies and full expected outcome.
7. Execution outline -> person approval -> facilitation of the approved board through current project agent
   tasks, paired contributions, registered worksheets and peer review.

A no stops the pipeline. Preparation tickets do not authorize implementation. Decomposer creates its fresh
board inactive and its tickets held until the outline is approved. Dispatch admission, stops and capacity apply to every assigned task. Stage labels describe work, not privileges.
Launch requests grant no ownership of agents. Intake uses its existing authored task instructions.
Task request keys prevent duplicate launches when a reply is lost. Launch failures remain attached to the same
stage ticket. Native session events retry launches refused before startup, including when a slot becomes free.
A running task is reused on recovery, and a new attempt receives a new key after an ended task.
Cancelled tasks stop their pipeline. Retries retain the original stage request time, so a later user halt
still prevents their launch. A crash between ticket creation and its reservation can leave an unlaunched
ticket because those stores commit separately. Missing reserved tickets remain errors and are never recreated.

`roundtables follow-through <table>` prepares or recovers a handoff. `roundtables review <table>` reads the full
current output. `roundtables submit` publishes an assigned stage file from its worktree into the source project's
saved record. Architecture supplies `project_name`; decomposition supplies its actual `board`. Cross-project
stage calls supply `origin`, the source project id. The page's decisions carry both the SHA-256 of the reviewed
bytes and the stage revision. Changed bytes or a stale revision require another review. Comments and revision
requests remain in the pipeline record. Status and events carry metadata rather than deliverable bodies.

The module uses tables version 7, compatible from 5. Version 7 adds the chair's mutable token budget independently
of follower cursors, so older active followers cannot overwrite a live edit. Version 6 adds only the
current refused stage launches. Successful launches remove them, and stopped or obsolete stages cannot restart.
Version 5 persists the preparation choice and prevents older writers from applying incompatible review transitions. Upgrade preserves finished discussions,
events and follower cursors. Version 3 proposal decisions remain historical evidence; their direct Planner
route is removed. Recovered tables begin at the roundtable decision rather than inheriting execution approval.

## Automate Ticket Creation

Creation offers `Automate Ticket Creation`, off by default. `open automate_ticket_creation=true` saves the choice
with the table. Enabled preparation advances Researcher, Architect, Intake, Planner and Decomposer after each saved
output, without transition decisions. Decomposer creates a fresh named board in the target project and populates
complete tickets with prerequisites. It leaves the active board setting unchanged. Inactive-board admission keeps
these tickets from starting, so automated preparation needs no ticket holds. The system writes the execution
outline beside the plan. It remains available for later review. Facilitator never starts automatically.
Default-off tables retain the existing person decisions and held decomposition tickets.

## Sync and async

Every verb is synchronous. An engine call runs its MCP client on an event loop of its own for the call, with a deadline of 180 s. The follower is a process of its own, blocked on the events stream between changes.

## Layers

It writes no layer: its tables are at the project's place, version 7. Earlier discussions and events remain intact. The obsolete proposal table is removed.

- `tables`, keyed by `table_id`: the Address (empty for a table about no part), topic, opening, seats, host, synthesizer and spend it was opened with; its state and reason; the engine's `discussion`, chair token and A2A ids; `seated`, the seats' names; `follower`, its pid while it runs; `followed`, the cursors of what was told and where its record was saved, its memory kept and its result topics retained; `answer` and `answered`; `created` and `ended`. Index on `created`.
- `events`, keyed by `(table_id, seq)`: `kind`, `audience`, `payload` and `at`.

## Lifecycle and cleanup

No `start` or `stop`. A follower ends with its table: it gives its slots back, ends the page server it started and clears its pid. A follower stopped before its table, by SIGTERM or SIGHUP (dispatch's Stop all, or a removal of the project, asks it so; a metaform's clear or switch leaves the table be), by an error or by its page server failing, tells the person why with an `operational` event `follower_stopped`, ends the table through a page server of its own and follows it until the engine has closed its seats; only then do the slots go back. When the engine no longer holds a table its follower tells its `end` with that reason. A failure while opening refuses the table with the error, and a table the engine opened before the failure, found by the table's id at the start of its engine subject, is ended the same way. A follower killed outright gives its slots back with it, since the gate counts only live processes; `follow` starts it again, and it goes on from its cursors. Its logs are under the home's `run/roundtables`.

## Modules relied on

dispatch, for the agent slots and agent commands. memory's items are read through the chassis's `node_items`, and a table's outcome is recorded through `memory.record`; without memory the opening says none are kept and nothing is recorded. map, for the tickets `adopt` files.

## Systems supported

Linux and macOS.

## Resources owned

For each running table, its follower process and the engine page server it started.

## Installed and direct wheel

The same in both: the engine is in the wheel, so nothing is installed apart and nothing is looked up on PATH. `OPENROUTER_API_KEY` is required for Jev judging and OpenRouter seats. ACP-only unjudged tables use their agent logins.

## The shipped engine

`roundtable/` is the Roundtable 2 engine, copied from https://github.com/RchGrav/roundtable at revision 65359b27d72e4ee07325bde90a61bbfb0786f06f, its `src/roundtable` package with its `resources`. That repository is private and is not on PyPI, so a dependency on it would fail for every other person; the copy ships it with Metaform. It carries no licence file; it is the work of Metaform's own author. The embedded copy now also owns participant-controlled completion, optional judging and inline handoff. The original packaging change was: its runner starts a table's detached process as `python -m` of its own package, `__package__`, where the origin named the top-level `roundtable`. Every process of the engine is `<Metaform's interpreter> -m metaform.modules.roundtables.roundtable <serve|web|run>`, `engine.command`. Its home and settings are its own, `ROUNDTABLE_HOME` (`~/.roundtable` by default) and its `config.toml`. To update it, copy the origin's `src/roundtable` over `roundtable/` without `__pycache__`, keep the runner's line, and record the new revision here. The module's tests run it with the engine's own fakes, carried in `tests/`: `fakes.py`, its stub of OpenRouter and Jev from `scripts/check.py`, and `fake_agent.py`, its fake ACP agent from `dev/`.

## Demonstration

```bash
metaform set --jev
metaform roundtables open "How could agents in different projects reach each other?" '["claude/haiku", "deepseek/deepseek-v4.1-flash"]' spend=0.50
metaform roundtables open "How should this part hand over a peer's task?" address=code.gateway.messaging
metaform roundtables events <table>
metaform roundtables hold <table>
metaform roundtables end <table>
metaform roundtables status <table> report=true
```
