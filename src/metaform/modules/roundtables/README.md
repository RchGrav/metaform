# roundtables

Brings the person's question to a table of agents at an Address of the project, through the person's Roundtable 2 engine, `roundtable` (https://github.com/RchGrav/roundtable): the seats debate it from the part's context, build on each other's ideas, and go on until the question is answered. The engine runs the table; this module connects Metaform to it and ports nothing of it.

## Purpose

A question about one part of a project gets better answers from several agents than from one: each adds what it does best, Jev (through OpenRouter) keeps only what is new and on the topic, a synthesizer names the ideas collected, every seat ranks them and explains its choices, and a host summarises. The table works inside the project the person is in: it opens on the part's own context from the map, its seats read the project's folder, and its record stays with the project.

## Template version

The template changelog version this module started from: 0.3.0.

## Declaration

`SUPPORTED_OS` is Linux and macOS: a table's follower and the engine's servers are detached into a session of their own. `DEPENDENCIES` is empty. `SHIPS_DISABLED` is false. `MODULE` declares the verbs below and the tables.

### Toolbar items and panes

None of its own. The web page's roundtable stage (web, `page/app/roundtable/stage.js`) opens and chairs a table through the web server's `/api/roundtable-open`, `/api/roundtable-chair` and `/api/roundtable`, which run `open`, the chair's verbs, `events` and `status`.

## Common base used

`metaform.settings` declares the two settings and reads `jev` and dispatch's agent commands. `metaform.data` gives the module's own tables. `metaform.outline.markdown` writes the part as the opening holds it, and `metaform.module.node_items` lists the memories at it. `metaform.module.provided` finds dispatch's `dispatch.seats`. `metaform.events.announced` announces each write of a follower, and `Context.publish` publishes `roundtables.event`. `metaform.prompt_files` serves `resources/prompts.xml`. `metaform.home` places the logs. Nothing else of Metaform is imported.

### Provides

Nothing. It uses dispatch's `dispatch.seats` and memory's `memory.record`.

## Prompts

`resources/prompts.xml` holds `connect`, `instructions` and `rules`, and `opening`, which every seat reads first, filled with `address`, `part` (the element and the joins it receives and provides, with their purposes and encounter functions), `memories` (the titles of the memories at the part, `no_memories` when none) and `question`. The engine adds its own discussion instructions and the topic after it.

## Verbs

- `open <address> <topic> [seats] [host=] [synthesizer=] [reporter=] [rounds=] [spend=]`, write, open world: open a table. `seats` is a JSON list in speaking order, `roundtables_seats` when left out: `claude/<model>`, `codex/<model>` and `gemini/<model>` are Metaform's own agents, seated on the engine's ACP client with dispatch's commands (`dispatch_claude`, `dispatch_codex`, `dispatch_gemini`); any other id is an OpenRouter model. The host is the first seat when none is named, never the engine's own default, which would seat an agent nobody chose. The question is the table's one topic. Refused while `jev` is off, since the part's context goes to OpenRouter; when fewer agent slots are free than seats; and when `spend` passes `roundtables_spend`. Returns the table's id.
- `comment <table> <text>`, `hold <table>`, `continue <table>`, `advance <table>`, `reseat <table> <seat>`, `end <table>`, write, open world: the chair's controls, as the engine offers them, passed with the table's chair token.
- `status <table> [report=true]`, read: the table's state, seats, spend, follower, answer, and its saved report with `report=true`.
- `tables`, read: every table of the project, newest first.
- `events <table> [after=<seq>]`, read: the table's events after a cursor.
- `follow <table>`, write, open world: start a table's follower again when it stopped before the table ended.
- `adopt <table> <idea> [address=] [title=]`, write, the person's decision: an idea of an ended table, by its id (`I2`), made one ticket of kind enhancement at the part it concerns, the table's Address unless `address` names another. Its task carries the idea, the question, the answer and the saved report (the JSON export when the engine wrote no report); its note names the table as its source. An `address` with no current element on the map is filed as given, and the answer passes on the map's notice that says so. It is held by no one, so Full Auto starts it like any ticket. Kept as the table's `adopted` event, so adopting the same idea again gives the same ticket. An agent's call is refused with the caution and the command the person runs.
- `run <table>`, command line only: the follower itself, which `open` and `follow` start detached.

## Settings

- `roundtables_engine`, `roundtable`, global, the person's: the command that runs the engine.
- `roundtables_spend`, 2, the person's: the most US dollars one table spends through OpenRouter; `open` may only lower it.
- `roundtables_seats`, `claude/opus`, `claude/sonnet`, `claude/haiku`, the person's: the seats, in speaking order, of a table opened without any named, as the page's stage opens one.

## Events

A follower publishes each event of its table on the bus as `roundtables.event`, `{table, seq, kind, audience, ...}`, and writes it to the `events` table in the same transaction as the cursor that says it was told; that write's `map.changed` names the kind `roundtables` and the table's own, `roundtables:<table>`, so a page watching one table reads only for it, and so every other process of the home, the web page's server among them, hears it and reads the one table's events after the seq it holds. Kinds: `turn` and `veto` (a seat's turn, kept or vetoed, with its scores), `stage` (the open topic and its stage), `ideas` (the synthesis), `rankings`, `summary` (the host's), `state`, `seat_lost` and `operational` (the engine's operational events), `end` (with `answered`, `answer`, whether the report was saved, `saved`, the folder of the saved files, and `recorded`, the memory's name, or `unrecorded` and why), and `adopted` (an idea made a ticket, with its `work_id` and `address`). `state`, `seat_lost`, `operational`, `end` and `adopted` have the audience `person`: they are the person's, and nothing of them goes to a seat or Jev.

The follower hears the table through the engine's own page server, started for it alone on a free loopback port with a token only it holds: the page's events stream says when anything of the table moves, and the follower reads only what moved. That server looks at the engine's store about once a second, in the engine's process; nothing here waits on a clock.

## Guardrails

- Each seat takes one of dispatch's agent slots for as long as its seats run, and a follower that stops ends its table first, through dispatch's own admission gate, so tables and tickets share `dispatch_agents` and `dispatch_machine_agents`. A table needs a slot for every seat when it opens; dispatch off refuses it, since nothing would count them.
- A table spends at most `spend`, at most `roundtables_spend`, through OpenRouter; the engine also holds its own most.
- Seats read and change nothing. The engine gives Claude Code only Read, Grep and Glob, runs Codex read-only, offers no file writes or terminals, and refuses every permission a seat asks to write; this module never names an MCP server for a seat. The tables carry no Metaform tool.
- Operational events reach the person, never a seat or Jev.
- The tables and their events are in the project's store, so a base switch, a clear or a restore never takes them.
- The report is always saved: the engine's, or its mechanical report written from the record when no model wrote one.

## What a table leaves in the project

When a table ends, its follower keeps its outcome where it was asked, so the next agent working at that part knows what was decided and why, and the person can find it again.

- The engine's files are saved under `docs/roundtables/<n>-<topic>/` in the project's folder, `<n>` the engine's number for the table and `<topic>` the question in lower-case words: `report.md` (the report as the engine serves it, the mechanical one when no model wrote it), `mechanical-report.md` (the engine's report from the record alone) and `export.json` (the engine's export, the same JSON it writes beside its report, with every topic's rankings and the Borda count derived from them). Written once; a follower started again keeps the folder.
- One memory is recorded at the table's Address through memory's `memory.record`, under memory's own rules, its writer `roundtables`: the question, the host's answer, the top three ideas by the Borda count with what the synthesis said of each, each seat's explanation of its top three, and where the report is saved, which it cites, so the memory is marked stale if the file changes; when the engine wrote no report it says so and cites the saved JSON export instead, since memory refuses a citation of a missing file. Each engine text is quoted whole as one observation. Memory is what happened at the table; what it established about the project is the person's to judge, through `adopt` or knowledge an agent writes later, and the follower writes no knowledge layer item itself.
- `status` shows `saved` and `recorded`. With memory off, the files are still saved and the `end` event says why nothing was recorded.

## Sync and async

Every verb is synchronous. An engine call runs its MCP client on an event loop of its own for the call, with a deadline of 180 s. The follower is a process of its own, blocked on the events stream between changes.

## Layers

It writes no layer: its tables are at the project's place, version 1.

- `tables`, keyed by `table_id`: the Address, topic, opening, seats, host, synthesizer, reporter, rounds and spend it was opened with; its state and reason; the engine's `discussion`, chair token and A2A ids; `seated`, the seats' names; `follower`, its pid while it runs; `followed`, the cursors of what was told; `report` and `report_error`; `answer` and `answered`; `created` and `ended`. Index on `created`.
- `events`, keyed by `(table_id, seq)`: `kind`, `audience`, `payload` and `at`.

## Lifecycle and cleanup

No `start` or `stop`. A follower ends with its table: it gives its slots back, ends the page server it started and clears its pid. A follower stopped before its table, by SIGTERM or SIGHUP (dispatch's Stop all, or a removal of the project, asks it so; a metaform's clear or switch leaves the table be), by an error or by its page server failing, tells the person why with an `operational` event `follower_stopped`, ends the table through a page server of its own and follows it until the engine has closed its seats; only then do the slots go back. When the engine no longer holds a table its follower tells its `end` with that reason. A failure while opening refuses the table with the error, and a table the engine opened before the failure, found by the table's id at the start of its engine subject, is ended the same way. A follower killed outright gives its slots back with it, since the gate counts only live processes; `follow` starts it again, and it goes on from its cursors. Its logs are under the home's `run/roundtables`.

## Modules relied on

dispatch, for the agent slots and the agent commands. memory's items are read through the chassis's `node_items`, and a table's outcome is recorded through `memory.record`; without memory the opening says none are kept and nothing is recorded. map, for the tickets `adopt` files.

## Systems supported

Linux and macOS.

## Resources owned

For each running table, its follower process and the engine page server it started.

## Installed and direct wheel

The same in both. The engine is installed apart: `uv tool install <path to roundtable>`, or `roundtables_engine` set to its command. `OPENROUTER_API_KEY` must be set where Metaform runs.

## Demonstration

```bash
metaform set --jev
metaform roundtables open code.gateway.messaging "How should agents in different projects reach each other?" '["claude/haiku", "deepseek/deepseek-v4.1-flash"]' spend=0.50
metaform roundtables events <table>
metaform roundtables hold <table>
metaform roundtables end <table>
metaform roundtables status <table> report=true
```
