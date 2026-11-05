# roundtables

Brings the person's question to agents through the Roundtable 2 engine, which ships inside this module. The page shows the live transcript with readable message and source references, then the finished synthesis, rankings, answer and saved record. Roundtable Follow-through prepares research, architecture, intake, a plan, detailed tickets and an execution outline through assigned tasks. The system controls stage progression without a coordinator agent.

## Purpose

A question gets better answers from several agents than from one: each adds what it does best, optional Jev judging (through OpenRouter) filters novelty, a synthesizer names the ideas collected, every seat ranks them and explains its choices, and a host summarises. Its main use is brainstorming, an idea that is not in the project yet, so the question is the table's whole frame: it is limited to no part and to no project. An Address given focuses it on that part, whose context from the map opens the table. Its seats read the project's folder when the question touches it, and its record stays with the project. The page shows the finished synthesis and answer beside links to the saved record.

## Template version

The template changelog version this module started from: 0.3.0.

## Declaration

`SUPPORTED_OS` is Linux and macOS: a table's follower and the engine's servers are detached into a session of their own. `DEPENDENCIES` is the shipped engine's own requirements: `mcp`, `agent-client-protocol`, `a2a-sdk[http-server]`, `httpx` and `uvicorn`. `SHIPS_DISABLED` is false. `MODULE` declares the verbs below and the tables.

### Toolbar items and panes

None of its own. The web page's roundtable stage (web, `page/app/roundtable/stage.js`) opens a table and shows it through the web server's `/api/roundtable-open` and `/api/roundtable`, which run `open`, `events` and `status`. The chair can read cited evidence, comment and use the session controls while the discussion runs.

## Common base used

`metaform.settings` declares the settings and reads `jev` and dispatch's agent commands. `metaform.data` gives the module's own tables. `metaform.outline.markdown` writes the part as the opening holds it, and `metaform.module.node_items` lists the memories at it. `metaform.module.provided` finds dispatch's `dispatch.seats`, shared `agent.name` and design-intake providers, plus `task.lifecycle`. `metaform.events.announced` announces each write of a follower, and `Context.publish` publishes `roundtables.event`. `metaform.prompt_files` serves `resources/prompts.xml`. `metaform.home` places the logs. Nothing else of Metaform is imported.

### Provides

Nothing. It uses dispatch's `dispatch.seats`, `agent.name` and design-intake providers, tasks' `task.lifecycle`, and memory's `memory.record`.

## Prompts

`resources/prompts.xml` holds `connect`, `instructions` and `rules`; `opening_question`, which every seat of a table with no Address reads first, the question alone; and `opening`, which every seat of a table about a part reads first, filled with `address`, `part` (the element and the joins it receives and provides, with their purposes and encounter functions), `memories` (the titles of the memories at the part, `no_memories` when none) and `question`. The engine adds its own discussion instructions and the topic after either. `outcome_*` the memory a table leaves; `adopted*` an adopted idea's ticket.

The `session_*` prompts hold the person's session messages. The participating agents jointly author their own
documents in the shared session folder. The transcript and its references remain available while they collaborate.

## Verbs

- `open <topic> [address=] [seats] [host=] [synthesizer=] [judging=] [reply_limit=] [spend=]`, write, open world: open a table on the question, focused on the part at `address` when one is given. `seats` is a JSON list in speaking order, `roundtables_seats` when left out: `claude/<model>`, `codex/<model>` and `antigravity/<model>` are Metaform's own agents, seated on the engine's ACP client with dispatch's commands (`dispatch_claude`, `dispatch_codex`, `dispatch_antigravity`); any other id is an OpenRouter model. The host is the first seat when none is named, never the engine's own default, which would seat an agent nobody chose. The question is the table's one topic. `reply_limit` sets the base discussion allowance, 512 characters by default. Each participant receives its current promised limit after private reply credits. Longer replies are truncated to that promised limit before judging. Synthesis, ranking explanations and reports retain their stage-specific limits. Judged tables require `jev` and an OpenRouter credential. ACP-only single-roundtable tables with `judging=false` require neither; sessions with subsequent topics still use Jev for private topic comparison; when fewer agent slots are free than seats; and when `spend` passes `roundtables_spend`. Returns the table's id.
- `comment <table> <text>`, `hold <table>`, `continue <table>`, `advance <table>`, `reseat <table> <seat>`, `end <table>`, write, open world: the chair's controls, as the engine offers them, passed with the table's chair token.
  The GUI exposes Hold, Continue, discussion comments and End discussion beside the transcript. End discussion invokes `advance` immediately at the next gap, without minimum rounds. Comments can be queued while held, without resuming AI turns. They enter at the next gap between turns. Continue resumes the same table. On a completed table, Continue discussion uses its saved host summary with fresh seat contexts, the same visible identity, project and lineup. It appends a topic without removing prior topics or outputs. Plan review comments remain separate.
  Controls use the current engine phase independently of transcript playback. End discussion remains visible and
  finishes the current discussion. If another roundtable remains, each participant privately proposes its next topic.
  During private topic selection, scoring and farewell, End discussion is disabled with an explanation while End session remains available. Errors identify the panel number
  rather than the engine's internal session id.
  End session stays available during discussion, private topic selection, scoring and farewell, including while held. It
  invokes `end` to save the current record and documents and stop the remaining phases. The page retains the session.
  Abort remains a separate action that archives the run and clears it from the page.
  Start remembers the participant lineup in this browser per project. Save participants stores the chosen order and models in the existing `roundtables_seats` project setting without starting agents. A fresh browser uses those defaults.
  ACP seats use the project as their workspace. Their harnesses provide file tools and request permissions through ACP.
- `permit <table> request=<id> option=<id>`, command line or page: return the person's selected option to the waiting
  ACP request. Requests not covered by the selected standard prompt policy display the options supplied by the agent.
  Setup shows the same permission controls as an ordinary agent launch, once per selected agent type. The
  `permissions` object maps agent names to `prompts` and native ACP `mode`; omitted choices use project settings.
  Choices are captured when the table opens and persist through discussions, private topic selection and recovered seat sessions.
- `status <table> [report=true]`, read: the table's state, seats, spend, follower, answer, every topic's synthesis and rankings as `topics`, `saved`, `recorded`, and `report`, the mechanical transcript's saved path. `report=true` includes its text as `report_text`.
- `tables`, read: every table of the project, newest first.
- `events <table> [after=<seq>]`, read: the table's events after a cursor.
- `reference <table> <reference>`, read: an accepted message by its public ID, a cited project file with an optional
  line number, or a quoted literal `rg`/`grep` search. The page opens the result in its reading window through
  `/api/roundtable?reference=...`. Reads stay bounded to the selected project.
- `follow <table>`, write, open world: start a table's follower again when it stopped before the table ended.
- `adopt <table> <idea> [address=] [title=]`, write, the person's decision, secondary to the report: an idea of an ended table, by its id (`I2`), made one ticket of kind enhancement. On a table about a part, the ticket is at the part the idea concerns, the table's Address unless `address` names another; an `address` with no current element on the map is filed as given, and the answer passes on the map's notice that says so. On a table with no part, an idea may concern nothing that exists yet, so it is never forced onto a nearby element: the ticket is at `address` when the map holds that element, else at the project's top element (its DE, else its first root element), with the named Address in its note as `proposed`; nothing is added to the map. Its task carries the idea, the question, the answer and the report (the saved record before the report is written); its note names the table as its source. It is held by no one, so Full Auto starts it like any ticket. Kept as the table's `adopted` event, so adopting the same idea again gives the same ticket. An agent's call is refused with the caution and the command the person runs.
- `run <table>`, command line only: the follower itself, which `open` and `follow` start detached.

## Settings

- `roundtables_spend`, 2, the person's: the most US dollars one table spends through OpenRouter; `open` may only lower it.
- `roundtables_token_budget`, 0: counted tokens per participant per discussion. Zero disables the limit. Setup captures this default, and `budget <table> <token_budget>` or the
  live budget control changes the limit without clearing usage already recorded in the current phase.
  A runner started before token-budget support must first be held, finish stopping, and be continued to load the
  new code. Live edits refuse that older active runner rather than claim enforcement it cannot provide.
- `roundtables_token_basis`, `uncached`: uncached input plus output, including cache writes and excluding cache
  reads. `output` counts generated output only. `all` also counts cached input. Setup captures the project's choice.
  Existing tables without a saved choice retain `all`. To change an existing table's basis, stop its runner first,
  then use `budget <table> <token_budget> token_basis=uncached`. This recounts only the current phase from saved
  usage and clears that phase's old warnings. Earlier phases and full usage records remain intact. Editing the
  limit without specifying a basis preserves the table's choice.
- `roundtables_seats`, `claude/opus`, `codex/astra`, `codex/sol`, `claude/fable`, the person's: the seats, in speaking order, of a table opened without any named, as the page's stage opens one. A model is a short name, such as `opus` or `sol`, which means the newest release of its family when the table opens, or an exact value, such as `gpt-6-sol`, which pins one; one the agent does not offer is refused, naming the nearest.

## Completion and context handoff

The Git history identifies two causes of the lost completion behavior. On 2026-10-22, `b8b0db19` removed the
engine's quiet/no-kept and sufficiency completion paths and required unanimous PASS. On 2026-11-04, `541b2c20`
set session novelty thresholds to zero and added a separate Jev-free collaboration phase. On-topic repetition
could therefore remain accepted, while collaboration relied on a separate DONE/file handoff. Current behavior
restores meaningful contribution gates and actual quiet-cycle completion, keeps file work in discussion and
chooses subsequent topics privately. These changes follow the person's corrected rules, while historical records
retain the rules and references captured when they ran.

The stage opens on the participants' transcript with the chair's comment box available. Clickable message and source
references replace the automatic Haiku Breakdown. Haiku generation stops only after those reference readers are
available, so removing the summary does not leave the chair with unreadable citations. Participants write and
summarize shared documents inline while the judged discussion continues. Busy participants are skipped while others speak.
There is no separate intertopic collaboration phase, DONE barrier or `next-topic.md` handoff.

New accepted messages have public IDs such as `R1-1`, `R1-2` and `R2-1`: the panel number and a contiguous counter
of accepted messages within that panel. Vetoes, PASS replies and failures receive no public ID and consume no number in that
counter. Database cursors and owner audit resources retain their private submission numbers. Existing records keep
their recorded references rather than being renumbered.

A participant returning from work can contribute one optional inline comment citing several earlier public IDs,
or reply PASS. It need not make up each skipped turn or answer each intervening message separately. Its entire reply,
including references, fits its current private allowance. The base is 512 characters by default. Each actual PASS
banks one base allowance, and each accepted peer message missed while doing native work banks one more. A veto
earns no credit. At the default base, the next limit is `512 * (1 + PASS credits + missed accepted messages)`.
An accepted reply spends the credits offered for that reply, while newer credits remain available. The promised
limit survives retries and remains authoritative for truncation and judging. Neither the ledger nor the allowance
is broadcast to peers. The same three Jev checks evaluate every substantive reply against the latest accepted discussion.

Clicking a public message ID opens that accepted message. A source citation such as `src/module.py:42` opens the
referenced file and line. Quoted literal `rg` or `grep` references open bounded search results through the same project
read API. The reader resolves those references without executing a supplied shell command.

Notes lists those shared files. Each selected note opens in a separate reading window with rendered Markdown,
normal scrolling and its own filename. The file list remains available while the document is open.

Copying cited source excerpts to preserve their text across later revisions is a proposed follow-up. This version
reads the cited project files and does not copy excerpts automatically. Graph database storage of specifications
is deferred and is outside this version.

A judged discussion finishes after two complete quiet cycles with no accepted contribution and at least two actual
outcomes from every participant since the last accepted contribution or chair clarification. For each participant's
two latest outcomes, `PP`, `VV` and `VP` are finished, where `P` is an actual PASS and `V` is a veto. `PV` requires
one more correction opportunity. A busy skip, unavailable seat, missing reply, failure or pending judgment is not an
actual outcome and cannot age the quiet cycles. Acceptance or chair input resets progress. No separate Jev
sufficiency or completion call is made.

With judging off, the existing complete round of unanimous PASS still ends discussion. End discussion and the
120% per-agent phase budget can advance a phase independently of normal completion. Context size does not imply
PASS or a quiet round. Context handoffs invalidate earlier PASS votes without treating the handoff as a reply.
OpenRouter credit recovery requires explicit Continue. An exhausted dollar budget can be replaced with
`continue <table> spend=<amount>`, within configured caps.

With a token budget enabled, the first participant to reach 50% triggers a halfway notice for everyone, once per
delivered participant. From 80%, every turn repeats the instruction to wind down and arrange phase completion.
From 100%, every turn repeats closing instructions. Agents keep working. These notices never hold the session. At 120%,
the current discussion closes. A remaining roundtable starts private topic selection, and the last roundtable
proceeds to scoring and farewell. Each discussion starts fresh per-participant counters with the same configured
limit. The quiet-cycle rule or unanimous PASS can finish discussion earlier. Usage is counted once per completed physical turn, including PASS
and carry-forward replies. The default closing counter excludes cached reads. Full usage records retain them.
Reasoning tokens already included in output are not added again. Context-window occupancy is not spent usage.
Agents that omit usage cannot trigger a measured cap. A long
turn can overshoot a threshold before its usage report arrives. Saved shared documents survive automatic advancement.

Participants may elect a coordinator to track accepted decisions and document owners. Everyone keeps the same
permissions, and file work continues while other participants speak. This optional role adds no vote or completion
barrier. Private topic selection chooses the next topic.

Among participants, only the author receives a plain-language veto explanation, naming its failed checks. Peers receive neither the
rejected contribution nor veto notices, ratings or thresholds. The chair's private record retains the original
contribution and every failed check's recorded score and cutoff, with passing ratings omitted from the displayed
reason. This reports the failed conditions without generating a semantic rationale. The system writes no rejected
contribution or veto ledger to the participants' shared files.

In every new table, participants receive generated names through the public `agent.name` provider,
using dispatch's existing name generator and word lists. A private alias maps the model source and its occurrence
to an opaque identity, display name and profile key. The alias survives new sessions and lineup reordering.
Provider and model metadata remain available to the chair, while peer prompts use the generated identities.
The shared session folder contains `participants.md` with generated names only. The private mapping from model
sources to participant identities remains in the engine database.
The first alias for a source retains its existing profile and aggregate score. Additional occurrences have their
own profile keys. Earlier profile totals, seat names and transcripts are preserved rather than rewritten or split.
Standalone engine homes use the same provider. Existing tables retain their recorded labels.

The live controls show each participant's reported count, percentage and current discussion. A fresh discussion
shows zero before its first reply. Private topic selection shows only aggregate proposal progress; proposal text,
authorship and comparison scores remain private. A single tool-using turn can include several model calls, so its
first usage report can be large. The displayed counting basis identifies whether cached input is included.

`roundtables_judging` selects the default filter. Setup exposes the same choice for each new table. A substantive
contribution is tested by three independent Jev checks in one request: new information or a position on a recently mentioned matter, value to
the discussion, and relevance to the current topic. Each must reach 70% (0.70). There is no fourth combined
keep/overall check. Repeating or developing a position is judged under those checks instead of being automatically
rejected by a text-repeat rule. Historical judgments retain the criteria and cutoffs captured when they were made.
With judging off, every substantive reply is retained within the character reply limit, including repetitions.
Synthesis, ranking, explanation and host stages remain unchanged.

`roundtables_context_tokens` sets the native seat/editor context handoff trigger, 24,000 estimated tokens by
default. The engine's `config.toml` can lower individual triggers through `[context_budgets]` keyed by exact seat id.
This trigger is independent of Jev's judging window.

`roundtables_judging_context_tokens` defaults to a desired cap of 50,000 estimated tokens for the judging request.
Jev receives escaped XML containing the complete original instructions, current topic, full candidate and a
sliding window of recent accepted responses and chair clarifications. Older whole responses leave the window first.
Rejected contributions and private carry-forward material are excluded. Jev sees neutral seat positions rather
than provider or model names.

The encoded request must also fit within 80% of the configured 65,536-token request limit and each question within
80% of its 32,000-token limit, including the shared state and question text. These leave 20% headroom. With the
standard limits, the bounds are 52,428 tokens for the whole request and 25,600 for each question, so the effective
history can be smaller than the desired 50,000 cap. Required instructions and the candidate are never shortened.
Sliding the judging window does not restart native seat contexts or alter the visible transcript.

Before exhaustion, every participant receives a carry-forward request at twice the discussion character limit. Notes retain attribution and exact text outside novelty filtering. One fresh synthesizer context edits shared continuation, preserving original person instructions, decisions, evidence references, disagreements and open questions. Code attaches every intact note to the shared continuation. Seat sessions start afresh. The visible transcript retains all original turns and adds a context-handoff marker. Saved notes survive a failed editor request, so Continue retries the unfinished step. Unjudged tables use the same handoff independently of Jev.

A held runner closes its seats. Comments remain queued or enter without resuming turns. Explicit Continue restarts it. Starting an engine server never resumes other live or held tables.

Each participant has an ordered inbox checkpointed at the transport's send receipt. Busy participants accumulate
new contributions while others speak. Inputs that were not sent stay queued. Delivered inputs are not replayed
after a missing reply, cancellation or Continue. An interrupted native request remains unfinished until its
reply is saved. Continue asks it to finish and supplies only newly queued contributions. Budget warnings have their
own delivery receipts; acknowledging a closing instruction does not count as completing the closing reply.

Carry-forward requests use that same inbox. They omit the shared continuation and the participant's own replies
when those already exist in its conversation. Context estimates count the native conversation's system text once.
A fresh context receives its original instructions and saved continuation once. Saved notes remain intact.

Opening with `chain=<number>` runs a session containing that many discussions. The page uses the same flow for one
roundtable. Participants create shared documents while discussion continues. Busy seats are skipped while available
seats speak. When every seat is busy, the runner waits for actual completion or chair-control events without timed cycling.

Between discussions, each participant receives one private next-topic request. No proposal or proposer identity is
announced. Jev compares every unordered pair once in one request, asking whether the two proposals are similar.
The same similarity probability is credited to both proposals. Each proposal's pair scores are averaged, and the
highest average wins without a minimum threshold. Exact ties preserve every tied winning text verbatim and without
attribution, joined without a model-written synthesis. A sole proposal wins directly. The owner sees aggregate
collection and judging progress. There is no shared-file requirement for choosing the next topic.

After the final discussion, each agent submits private scorecards. Only aggregate scores are shared and added to
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

The module uses tables version 8, compatible from 5. Version 8 adds the live observer's account independently of
participant documents and follower events. Version 7 adds the chair's mutable token budget independently
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

It writes no layer: its tables are at the project's place, version 8. Earlier discussions and events remain intact. The obsolete proposal table is removed.

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
