# roundtables

Brings the person's question to a table of agents, through the person's Roundtable 2 engine, `roundtable` (https://github.com/RchGrav/roundtable): the seats debate it, build on each other's ideas, and go on until the question is answered, and when the table ends the person's system agent writes its report. The engine runs the table; this module connects Metaform to it and ports nothing of it.

## Purpose

A question gets better answers from several agents than from one: each adds what it does best, Jev (through OpenRouter) keeps only what is new and on the topic, a synthesizer names the ideas collected, every seat ranks them and explains its choices, and a host summarises. Its main use is brainstorming, an idea that is not in the project yet, so the question is the table's whole frame: it is limited to no part and to no project. An Address given focuses it on that part, whose context from the map opens the table. Its seats read the project's folder when the question touches it, and its record stays with the project. The table exists for its report: the person's system agent writes it from the saved record when the table ends.

## Template version

The template changelog version this module started from: 0.3.0.

## Declaration

`SUPPORTED_OS` is Linux and macOS: a table's follower and the engine's servers are detached into a session of their own. `DEPENDENCIES` is empty. `SHIPS_DISABLED` is false. `MODULE` declares the verbs below and the tables.

### Toolbar items and panes

None of its own. The web page's roundtable stage (web, `page/app/roundtable/stage.js`) opens and chairs a table through the web server's `/api/roundtable-open`, `/api/roundtable-chair` and `/api/roundtable`, which run `open`, the chair's verbs, `events` and `status`.

## Common base used

`metaform.settings` declares the two settings and reads `jev` and dispatch's agent commands. `metaform.data` gives the module's own tables. `metaform.outline.markdown` writes the part as the opening holds it, and `metaform.module.node_items` lists the memories at it. `metaform.module.provided` finds dispatch's `dispatch.seats` and `orchestration.transport`. `metaform.events.announced` announces each write of a follower, and `Context.publish` publishes `roundtables.event`. `metaform.prompt_files` serves `resources/prompts.xml`. `metaform.home` places the logs. Nothing else of Metaform is imported.

### Provides

Nothing. It uses dispatch's `dispatch.seats` and `orchestration.transport`, and memory's `memory.record`.

## Prompts

`resources/prompts.xml` holds `connect`, `instructions` and `rules`; `opening_question`, which every seat of a table with no Address reads first, the question alone; and `opening`, which every seat of a table about a part reads first, filled with `address`, `part` (the element and the joins it receives and provides, with their purposes and encounter functions), `memories` (the titles of the memories at the part, `no_memories` when none) and `question`. The engine adds its own discussion instructions and the topic after either. `report_request` is the project update that asks the system agent for the report; `outcome_*` the memory a table leaves; `adopted*` an adopted idea's ticket.

## Verbs

- `open <topic> [address=] [seats] [host=] [synthesizer=] [rounds=] [spend=]`, write, open world: open a table on the question, focused on the part at `address` when one is given. `seats` is a JSON list in speaking order, `roundtables_seats` when left out: `claude/<model>`, `codex/<model>` and `gemini/<model>` are Metaform's own agents, seated on the engine's ACP client with dispatch's commands (`dispatch_claude`, `dispatch_codex`, `dispatch_gemini`); any other id is an OpenRouter model. The host is the first seat when none is named, never the engine's own default, which would seat an agent nobody chose. The question is the table's one topic. Refused while `jev` is off, since the question, and the part's context when there is one, go to OpenRouter; when fewer agent slots are free than seats; and when `spend` passes `roundtables_spend`. Returns the table's id.
- `comment <table> <text>`, `hold <table>`, `continue <table>`, `advance <table>`, `reseat <table> <seat>`, `end <table>`, write, open world: the chair's controls, as the engine offers them, passed with the table's chair token.
- `status <table> [report=true]`, read: the table's state, seats, spend, follower, answer, `saved`, `recorded`, `handed`, and `report`, the report's path once the system agent has written it, with its text as `report_text` with `report=true`.
- `tables`, read: every table of the project, newest first.
- `events <table> [after=<seq>]`, read: the table's events after a cursor.
- `follow <table>`, write, open world: start a table's follower again when it stopped before the table ended.
- `adopt <table> <idea> [address=] [title=]`, write, the person's decision, secondary to the report: an idea of an ended table, by its id (`I2`), made one ticket of kind enhancement. On a table about a part, the ticket is at the part the idea concerns, the table's Address unless `address` names another; an `address` with no current element on the map is filed as given, and the answer passes on the map's notice that says so. On a table with no part, an idea may concern nothing that exists yet, so it is never forced onto a nearby element: the ticket is at `address` when the map holds that element, else at the project's top element (its DE, else its first root element), with the named Address in its note as `proposed`; nothing is added to the map. Its task carries the idea, the question, the answer and the report (the saved record before the report is written); its note names the table as its source. It is held by no one, so Full Auto starts it like any ticket. Kept as the table's `adopted` event, so adopting the same idea again gives the same ticket. An agent's call is refused with the caution and the command the person runs.
- `run <table>`, command line only: the follower itself, which `open` and `follow` start detached.

## Settings

- `roundtables_engine`, `roundtable`, global, the person's: the command that runs the engine.
- `roundtables_spend`, 2, the person's: the most US dollars one table spends through OpenRouter; `open` may only lower it.
- `roundtables_seats`, `claude/opus`, `codex/astra`, `codex/sol`, `claude/fable`, the person's: the seats, in speaking order, of a table opened without any named, as the page's stage opens one. A model is a short name, such as `opus` or `sol`, which means the newest release of its family when the table opens, or an exact value, such as `gpt-6-sol`, which pins one; one the agent does not offer is refused, naming the nearest.

## Events

A follower publishes each event of its table on the bus as `roundtables.event`, `{table, seq, kind, audience, ...}`, and writes it to the `events` table in the same transaction as the cursor that says it was told; that write's `map.changed` names the kind `roundtables` and the table's own, `roundtables:<table>`, so a page watching one table reads only for it, and so every other process of the home, the web page's server among them, hears it and reads the one table's events after the seq it holds. Kinds: `turn` and `veto` (a seat's turn, kept or vetoed, with its scores), `stage` (the open topic and its stage), `ideas` (the synthesis), `rankings`, `summary` (the host's), `state`, `seat_lost` and `operational` (the engine's operational events), `end` (with `answered`, `answer`, whether the report was saved, `saved`, the folder of the saved files, and `recorded`, the memory's name, or `unrecorded` and why), and `adopted` (an idea made a ticket, with its `work_id` and `address`). `state`, `seat_lost`, `operational`, `end` and `adopted` have the audience `person`: they are the person's, and nothing of them goes to a seat or Jev.

The follower hears the table through the engine's own page server, started for it alone on a free loopback port with a token only it holds: the page's events stream says when anything of the table moves, and the follower reads only what moved. That server looks at the engine's store about once a second, in the engine's process; nothing here waits on a clock.

## Guardrails

- Each seat takes one of dispatch's agent slots for as long as its seats run, and a follower that stops ends its table first, through dispatch's own admission gate, so tables and tickets share `dispatch_agents` and `dispatch_machine_agents`. A table needs a slot for every seat when it opens; dispatch off refuses it, since nothing would count them.
- A table spends at most `spend`, at most `roundtables_spend`, through OpenRouter; the engine also holds its own most.
- Seats read and change nothing. The engine gives Claude Code only Read, Grep and Glob, runs Codex read-only, offers no file writes or terminals, and refuses every permission a seat asks to write; this module never names an MCP server for a seat. The tables carry no Metaform tool.
- Operational events reach the person, never a seat or Jev.
- The tables and their events are in the project's store, so a base switch, a clear or a restore never takes them.
- The report is the person's system agent's to write. The engine still has a seat write its own report when a table ends, since the engine always does; this module does not ask for it, save it or show it.

## What a table leaves in the project

When a table ends, however it ends, its follower saves its record, keeps its outcome as a memory, and hands the record to the person's system agent, which writes the report: the table's outcome, and what the person reads.

- The record is saved under `docs/roundtables/<n>-<topic>/` in the project's folder, `<n>` the engine's number for the table and `<topic>` the question in lower-case words: `export.json` (the engine's export, with every turn, every topic's rankings and the Borda count derived from them) and `mechanical-report.md` (the engine's text of the record). Written once; a follower started again keeps the folder.
- The record is handed to the person's system agent as one project update of kind `roundtable_report`, through dispatch's `orchestration.transport`, once. Its inbox names it, `project roundtable report`, and never puts it whole into the agent's turn; it starts the agent's turn, since the person waits for the report. The update, `report_request`, asks the agent to read the record on demand (`status`, `events`, `export.json`), write the report (the question; each seat's position and why; where they agreed and disagreed; what was decided and what was left open; the ideas worth acting on, each with where it would live) as `report.md` beside the record, and show the person a link to it and a few lines in chat. The person sees the update too, in the chat's project updates. With dispatch off, the `end` event says no report is being written, as `unhanded`.
- One memory is recorded at the table's Address, or at the project's top element for a table about no part, through memory's `memory.record`, under memory's own rules, its writer `roundtables`: the question, the host's answer, the top three ideas by the Borda count with what the synthesis said of each, each seat's explanation of its top three, where the record is saved, which it cites, so the memory is marked stale if the file changes, and where the system agent was asked to write the report. Each engine text is quoted whole as one observation. Memory is what happened at the table; what it established about the project is the person's to judge, through `adopt` or knowledge an agent writes later, and the follower writes no knowledge layer item itself.
- `status` shows `saved`, `recorded` and `handed`. With memory off, or no element on the map, the files are still saved and the `end` event says why nothing was recorded.

## Sync and async

Every verb is synchronous. An engine call runs its MCP client on an event loop of its own for the call, with a deadline of 180 s. The follower is a process of its own, blocked on the events stream between changes.

## Layers

It writes no layer: its tables are at the project's place, version 2.

- `tables`, keyed by `table_id`: the Address (empty for a table about no part), topic, opening, seats, host, synthesizer, rounds and spend it was opened with; its state and reason; the engine's `discussion`, chair token and A2A ids; `seated`, the seats' names; `follower`, its pid while it runs; `followed`, the cursors of what was told and where its record was saved, its memory kept and its record handed; `answer` and `answered`; `created` and `ended`. Index on `created`.
- `events`, keyed by `(table_id, seq)`: `kind`, `audience`, `payload` and `at`.

## Lifecycle and cleanup

No `start` or `stop`. A follower ends with its table: it gives its slots back, ends the page server it started and clears its pid. A follower stopped before its table, by SIGTERM or SIGHUP (dispatch's Stop all, or a removal of the project, asks it so; a metaform's clear or switch leaves the table be), by an error or by its page server failing, tells the person why with an `operational` event `follower_stopped`, ends the table through a page server of its own and follows it until the engine has closed its seats; only then do the slots go back. When the engine no longer holds a table its follower tells its `end` with that reason. A failure while opening refuses the table with the error, and a table the engine opened before the failure, found by the table's id at the start of its engine subject, is ended the same way. A follower killed outright gives its slots back with it, since the gate counts only live processes; `follow` starts it again, and it goes on from its cursors. Its logs are under the home's `run/roundtables`.

## Modules relied on

dispatch, for the agent slots, the agent commands and the project update that hands the record to the system agent. memory's items are read through the chassis's `node_items`, and a table's outcome is recorded through `memory.record`; without memory the opening says none are kept and nothing is recorded. map, for the tickets `adopt` files.

## Systems supported

Linux and macOS.

## Resources owned

For each running table, its follower process and the engine page server it started.

## Installed and direct wheel

The same in both. The engine is installed apart: `uv tool install <path to roundtable>`, or `roundtables_engine` set to its command. `OPENROUTER_API_KEY` must be set where Metaform runs.

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
