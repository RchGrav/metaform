# roundtable

A discussion among models at an Address, where only real contributions are kept, BASE-066.

## Purpose

The person, or their head agent, opens a table at an Address with an opening message and its seats. The seats speak in turn, round robin, in a fixed order, each at most 512 characters, and a submission enters the discussion only when Jev finds it new, valuable, relevant and worth keeping, each at `roundtable_keep` (83 per cent) or above. A vetoed submission is shown to every seat as its verdict, the four questions with their nouls and a link to its text. The table ends after a full round that kept nothing, or when its chair ends it, and one model writes the report into `docs/roundtables/`. Models differ in what they are good at; one discussion lets each add what it does best, while the veto removes repetition, agreement for its own sake and drift without telling any model how to behave.

## Template version

The template changelog version this module started from: 0.3.0, with the Unreleased changes, and the resource templates this module added to it.

## Declaration

`SUPPORTED_OS` is Linux, macOS and Windows: the module needs nothing but the standard library and the network. `DEPENDENCIES` is empty. `SHIPS_DISABLED` is False: a table is opened only on purpose, so having the module on costs nothing until then. `REMOTE_AGENT` is False: a table runs a process of its own and calls models; an agent in a sandbox takes part as a seat through the command line of the home that runs the table. `MODULE` declares the verbs below, the tables in `store.py`, and two resource templates.

The code is in parts, each under 500 lines: `store.py` the tables, `seats.py` who sits and a model's turn through OpenRouter, `judge.py` Jev's four nouls, `render.py` every text a seat, the head agent, the review and the report read, `chair.py` who may chair and how turns reach the head agent, and `runner.py` the process that runs a table.

### Toolbar items and panes

None yet. The page that shows a table, with its five-second pause and its Hold, comment, Continue and End controls, is built later in the web module; it marks the person watching with `roundtable watch` and reads the turns with `roundtable read`.

## Common base used

`metaform.module` for the declaration, `Context`, `Stop`, `child_environment` for the detached runner, `surface`, `context` and `call` to run dispatch's verbs without importing dispatch, and `Resource` for the resource templates. `metaform.data` for the tables, STORE-045. `metaform.settings` for the five settings. `metaform.prompt_files` for every word in `resources/prompts.xml`, MCP-031. `metaform.jev` for Jev's client: its endpoint, `Config`, `Question`, `post`, `checked` and `tokens`. The roundtable does not go through `jev.ask`, since the setting `jev` governs the decisions Metaform makes by itself; a roundtable is opened on purpose, so the switch does not hold it back, and Jev failing pauses the table and says why instead of falling back. `metaform.home` for the home folder that keeps OpenRouter's model list for a day.

The module adds one thing to the public base: a `Resource` whose URI holds `{field}` parts is a resource template, listed by the MCP server among the resource templates and read by calling its verb with the fields as nouns, MCP-037. `metaform://roundtable/discussion{discussion}/submission{submission}` and `metaform://roundtable/discussion{discussion}/review` are its first two.

### Provides

Nothing.

## Prompts

Every word sent to a seat, to Jev, to the head agent and to the reporter is in `resources/prompts.xml`, MCP-031. `seat_first` and `seat_next` are what a seat receives on its turn, with `turn_entry`, `verdict`, `verdict_over` and `verdict_none` for each turn and `over_limit` when a reply runs over 512 characters; nothing else is said to a seat, no instruction on how to respond. `jev_new`, `jev_valuable`, `jev_relevant` and `jev_keep`, each with its `_true` and `_false` criteria, are Jev's four nouls. `chair_turn`, `chair_vetoed`, `chair_held` and `chair_ended` are what the head agent receives. `review_intro` and `review_line` make the review; `report`, `record_opening` and `record_entry` the reporter's prompt. `connect` is empty, so the connect message stays short; `instructions` names the verbs and the resources. Its rule: only the person and their head agent open a table or use its chair controls.

## Verbs

| Verb | What it does | Effect |
|---|---|---|
| `open <address> seats=<seats> [subject=] -- <opening>` | Opens a table at an Address with the seats named, in that order, and starts its runner; the caller chairs it. There is no default line-up. Returns the number, the seats in order, and where the turns are sent. | write, open world |
| `comment <discussion> -- <text>` | A chair's comment, entered inline at the next gap between turns, unjudged, with no limit. | write |
| `hold <discussion>` | Holds the table after the turn in flight, until it is continued. | write |
| `continue <discussion>` | Runs a held table again, judging first a submission Jev left unjudged; in a pause, starts the next turn now. | write, open world |
| `end <discussion>` | Ends the table and writes the report; on an ended table whose report failed, asks for it again. | write, open world |
| `watch <discussion>` | Says the person is watching, for eight seconds; the page renews it while the table is open on it. The person only. | write |
| `status <discussion>` | The state, whose turn it is, each seat's submissions kept against turns taken, the report. | read |
| `list` | The project's tables, newest first. | read |
| `read <discussion> [since=]` | Every turn after a cursor, as the seats see it, with its nouls, for the person's surfaces. | read |
| `turn <discussion> <seat> [wait=]` | An agent seat's turn: what happened since its last reply; with `wait`, up to that many seconds for its turn. | read |
| `submit <discussion> <seat> -- <text>` | An agent seat's submission on its turn. Over 512 characters it is told once and may send it again; a second overrun is stored as vetoed, over 512. | write |
| `submission <discussion> <submission>` | The text a seat submitted, and nothing else. | read |
| `review <discussion>` | The full review: the four questions, the array's order, every submission in short form. | read |
| `run <discussion>` | The table's runner, started detached; on the command line only. | write, open world |

**Who may chair.** `open`, `comment`, `hold`, `continue` and `end` are the person's, on the page and on the command line with no agent session, and the head agent's: the session dispatch started with `system=true`, whose runner gives its agent METAFORM_ROLE `system`, METAFORM_SESSION and METAFORM_WORK, and which dispatch reports running on that ticket under that runner id. Every other agent session, and every call over MCP from no such session, is refused before anything is written. Any agent may take a seat.

**Seats.** A seat is written as a model id, `anthropic/claude-haiku-5.5` (or `openrouter:<model>`), called through OpenRouter with OPENROUTER_API_KEY; or as `agent:<name>`, an agent that reads its turn with `turn` and answers with `submit`, waiting up to `roundtable_agent_wait` seconds before its turn passes with no submission. The first agent session that submits for a seat answers for it from then on, MCP-042. A harness dispatch runs over ACP and an A2A peer, MCP-040, are seats the record names that are not built yet; `acp:` and `a2a:` seats are refused with that said.

**What a seat sees.** Each seat is one running conversation: a model's messages are kept in its seat row and grow with each turn, and an agent seat keeps its own. On its first turn a seat receives the opening and every turn before its own; on each later turn only the turns since its last reply, its own vetoed ones among them as their verdicts. A turn that entered reads as its text; a vetoed one as its verdict and the link `metaform://roundtable/discussion<N>/submission<M>`.

**The head agent as chair.** Each turn, as it lands, is sent into the head agent's own running session through dispatch's `message` verb, in order, none skipped, a vetoed submission with its verdict and its text, credited to the roundtable. A delivered cursor on the table means a restart neither skips nor repeats a turn. The table never waits for the head agent; a turn it cannot be given now is tried again after the next one.

**The person watching.** While the page renews `watch`, each turn is followed by `roundtable_pause` seconds in which hold, a comment, continue or end take effect; while nobody watches, the next turn follows at once.

## Settings

All are `person_only`: they decide which models are called on the person's account and how much the table spends.

| Setting | Default | Read by |
|---|---|---|
| `roundtable_keep` | 83 (per cent) | the runner, as the bar for each of the four nouls; the review |
| `roundtable_pause` | 5 seconds | the runner, after each turn while the person watches |
| `roundtable_agent_wait` | 300 seconds | the runner, on an agent seat's turn |
| `roundtable_reporter` | anthropic/claude-opus-5.5 | the runner, for the report |

Jev is reached through the chassis's `jev_endpoint` and `jev_model`.

## Events

None published or subscribed. The runner writes only the module's own tables and the report file.

## Sync and async

Every verb is synchronous. `turn` with `wait` and `run` take long; `run` is never an MCP tool.

## Layers

None: the roundtable writes no layer. Its tables, `place='project'`, so a clear of the map keeps them, version 1: `discussions`, one row per table, keyed by its number in the project, with its Address, subject, opening, chair, seats in order, state and reason, where the table is (round, position, kept this round), the head agent's delivered cursor, the person's watch, the runner's beat, a submission Jev did not judge, and the report; `seats`, one per seat keyed by table and position, with its running conversation, its last seen turn, an agent seat's pending turn and reply, and its kept and taken counts; `submissions`, every submission and comment keyed by table and number, with its round, seat, kind (`seat`, `person`, `head`, `none`), text, whether it was accepted, its four nouls and whether it ran over 512; `waiting`, the comments queued for the next gap. Every verb reads and writes them through `ctx.require_store().tables()`.

## Lifecycle and cleanup

No `start` or `stop`. `open` starts the table's runner as a detached process, `python -m metaform roundtable run <N>`, with METAFORM_ROLE `roundtable`; `comment`, `continue` and `end` start one again when the runner has stopped. A runner beats every five seconds; one silent for thirty seconds has stopped. The runner ends when the table has ended and its report is written, its log in the system's temporary folder, `metaform-roundtable-<project>-<N>.log`.

## Modules relied on

dispatch, reached through its `sessions` verb to know the head agent and its `message` verb to deliver turns, never by import. Without dispatch the person chairs alone. The mcp module serves the tools and the resource templates.

## Systems supported

Linux, macOS and Windows. No verb narrows them.

## Resources owned

The runner process of each running table, and its log. The report files under `docs/roundtables/` in the project's folder belong to the project. OpenRouter's model list is kept in the home at `cache/roundtable-models.json` for a day.

## Installed and direct wheel

The same in both: the module uses only the standard library and the public base. The runner is started with the Python that runs Metaform.

## Demonstration

```bash
metaform roundtable open code.alarm.audible seats=anthropic/claude-haiku-5.5,agent:me subject="timer chime" -- "What should a kitchen timer's chime sound like?"
metaform roundtable turn 1 agent:me wait=300
metaform roundtable submit 1 agent:me -- "Rise in pitch on each repeat, capped below an alarm."
metaform roundtable review 1
metaform roundtable end 1
```
