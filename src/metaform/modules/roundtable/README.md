# roundtable

A discussion among models at an Address, where only real contributions are kept, BASE-066.

## Purpose

The person, or their head agent, opens a table at an Address with an opening message and its seats. The seats speak in turn, round robin, in a fixed order, each at most 512 characters, and a submission enters the discussion only when Jev finds it new, valuable, relevant and worth keeping, each at `roundtable_keep` (83 per cent) or above. A vetoed submission is shown to every seat as its verdict, the four questions with their nouls and a link to its text. The table ends after a full round that kept nothing, at its most rounds or OpenRouter spend, or when its chair ends it, and one model writes the report into `docs/roundtables/`. Models differ in what they are good at; one discussion lets each add what it does best, while the veto removes repetition, agreement for its own sake and drift without telling any model how to behave.

## Template version

The template changelog version this module started from: 0.3.0, with the Unreleased changes, and the resource templates this module added to it.

## Declaration

`SUPPORTED_OS` is Linux, macOS and Windows: the module needs nothing but the standard library and the network. `DEPENDENCIES` is empty. `SHIPS_DISABLED` is False: a table is opened only on purpose, so having the module on costs nothing until then. `REMOTE_AGENT` is False: a table runs a process of its own and calls models; an agent in a sandbox takes part as a seat through the command line of the home that runs the table. `MODULE` declares the verbs below, the tables in `store.py`, and two resource templates.

The code is in parts, each under 500 lines: `store.py` the tables, `seats.py` who sits and a model's turn through OpenRouter, `harness.py` a harness seat's turn in its own dispatch session, `judge.py` Jev's four nouls, `render.py` every text a seat, the head agent, the review and the report read, `chair.py` who may chair and how turns reach the head agent, and `runner.py` the process that runs a table. The table as a place: `names.py` each seat's short name, `scene.py` where the seats sit and what each sees, `controls.py` a seat's turn, look and look-at, `toolloop.py` a model seat's turn with its controls as tools, `explore.py` the seats' time to explore, `stage.py` the runner's watch server and headless renderer, and `resources/scene/` the scene module, the watch page and the render page.

### Toolbar items and panes

None of its own. The web page shows a running table in its Roundtable tab and opens one from the Agents menu, both drawn by the web module through the web server's `/api/roundtable`, which runs `list`, `status`, `scene`, `read`, `seats`, `open`, `hold`, `comment`, `continue`, `end` and `watch`; the tab draws the table with this module's `resources/scene/scene.js`, served by the web server at `/roundtable/scene.js`. The runner's own loopback watch page stays, its address in `status`.

## Common base used

`metaform.module` for the declaration, `Context`, `Stop`, `child_environment` for the detached runner, `surface`, `context` and `call` to run dispatch's verbs without importing dispatch, and `Resource` for the resource templates. `metaform.data` for the tables, STORE-045. `metaform.settings` for the seven settings. `metaform.prompt_files` for every word in `resources/prompts.xml`, MCP-031. `metaform.jev` for Jev's client: its endpoint, `Config`, `Question`, `post`, `checked` and `tokens`. The roundtable does not go through `jev.ask`, since the setting `jev` governs the decisions Metaform makes by itself; a roundtable is opened on purpose, so the switch does not hold it back, and Jev failing pauses the table and says why instead of falling back. `metaform.home` for the home folder that keeps OpenRouter's model list for a day, and the pictures a look saves on the command line, `run/looks/`. The MCP server already turns a verb result's `image`, `{data, mimeType}`, into the tool's image content, as web `look` uses it, so the looks need nothing new in the public base. Playwright, when installed, for the headless renderer; it is not a declared dependency.

The module adds one thing to the public base: a `Resource` whose URI holds `{field}` parts is a resource template, listed by the MCP server among the resource templates and read by calling its verb with the fields as nouns, MCP-037. `metaform://roundtable/discussion{discussion}/submission{submission}` and `metaform://roundtable/discussion{discussion}/review` are its first two.

### Provides

Nothing.

## Prompts

Every word sent to a seat, to Jev, to the head agent and to the reporter is in `resources/prompts.xml`, MCP-031. `seat_first` and `seat_next` are what a seat receives on its turn, with `turn_entry`, `verdict`, `verdict_over` and `verdict_none` for each turn and `over_limit` when a reply runs over 512 characters; nothing else is said to a seat, no instruction on how to respond. `jev_new`, `jev_valuable`, `jev_relevant` and `jev_keep`, each with its `_true` and `_false` criteria, are Jev's four nouls. `chair_turn`, `chair_vetoed`, `chair_held` and `chair_ended` are what the head agent receives. `review_intro` and `review_line` make the review; `report`, `record_opening` and `record_entry` the reporter's prompt. `connect` is empty, so the connect message stays short; `instructions` names the verbs and the resources. Its rule: only the person and their head agent open a table or use its chair controls.

## Verbs

| Verb | What it does | Effect |
|---|---|---|
| `open <address> seats=<seats> [subject=] [rounds=] [spend=] -- <opening>` | Opens a table at an Address with the seats named, in that order, and starts its runner; the caller chairs it. There is no default line-up. `rounds` and `spend` (US dollars, such as `0.50`) replace `roundtable_rounds` and `roundtable_spend` for this table; a head agent may set them only at or below the settings. Returns the number, the seats in order, and where the turns are sent. | write, open world |
| `comment <discussion> -- <text>` | A chair's comment, entered inline at the next gap between turns, unjudged, with no limit. | write |
| `hold <discussion>` | Holds the table after the turn in flight, until it is continued. | write |
| `continue <discussion>` | Runs a held table again, judging first a submission Jev left unjudged; in a pause, starts the next turn now. | write, open world |
| `end <discussion>` | Ends the table and writes the report; on an ended table whose report failed, asks for it again. | write, open world |
| `watch <discussion>` | Says the person is watching, for eight seconds; the page renews it while the table is open on it. The person only. | write |
| `status <discussion>` | The state, whose turn it is, its most rounds and dollars and what it has spent, each seat's submissions kept against turns taken, the report. | read |
| `list` | The project's tables, newest first. | read |
| `read <discussion> [since=]` | Every turn after a cursor, as the seats see it, with its nouls, for the person's surfaces. | read |
| `turn <discussion> <seat> [wait=]` | An agent seat's turn: what happened since its last reply; with `wait`, up to that many seconds for its turn. | read |
| `submit <discussion> <seat> -- <text>` | An agent seat's submission on its turn. Over 512 characters it is told once and may send it again; a second overrun is stored as vetoed, over 512. | write |
| `submission <discussion> <submission>` | The text a seat submitted, and nothing else. | read |
| `review <discussion>` | The full review: the four questions, the array's order, every submission in short form. | read |
| `rotate [degrees=] [to=]` | As a seat, turn your figure in place: by degrees, positive to your right, or to a facing in degrees from facing the table. Returns your new facing and who is in front of you. | read |
| `look` | As a seat, see straight ahead from your own eyes: the picture (image content over MCP, a file under the home on the command line) and what is in view, each with its bearing and distance. | read |
| `look-at <name>` | As a seat, turn to face a seat by its name, or the plant, and look. | read |
| `scene <discussion>` | The table as its scene module draws it: every seat's place, facing, name, ring, hand and bubble, the table's sizes and the eye camera's; for the web page's Roundtable tab. On the command line only, so no tool. | read |
| `seats` | The seats a table can be opened with: each agent dispatch starts with the models it offered at its last session here, OpenRouter's models (the list kept in the home for a day), whether `OPENROUTER_API_KEY` is set, and the `roundtable_rounds`, `roundtable_spend` and `roundtable_pause` in force; for the page's Open roundtable form. On the command line only. | read, open world |
| `run <discussion>` | The table's runner, started detached; on the command line only. | write, open world |

**Who may chair.** `open`, `comment`, `hold`, `continue` and `end` are the person's, on the page and on the command line with no agent session, and the head agent's: the session dispatch started with `system=true`, whose runner gives its agent METAFORM_ROLE `system`, METAFORM_SESSION and METAFORM_WORK, and which dispatch reports running on that ticket under that runner id. Every other agent session, and every call over MCP from no such session, is refused before anything is written. Any agent may take a seat.

**Seats.** A seat is written as a model id, `anthropic/claude-haiku-5.5` (or `openrouter:<model>`), called through OpenRouter with OPENROUTER_API_KEY; as `acp:<agent>/<model>`, a harness dispatch runs over ACP on the person's own login, never an API key; or as `agent:<name>`, an agent that reads its turn with `turn` and answers with `submit`, waiting up to `roundtable_agent_wait` seconds before its turn passes with no submission. The first agent session that submits for a seat answers for it from then on, MCP-042. An A2A peer, MCP-040, is a seat the record names that is not built yet; `a2a:` seats are refused with that said.

**Harness seats.** `<agent>` is one of dispatch's agents, `dispatch agents`: `claude` for Claude Code, `codex` for Codex, or a registry agent the person pinned. `<model>` is a model the agent offers, as `dispatch options agent=<agent>` lists it, by its value (`opus`, `gpt-6-astra`), its name (`Opus 5.5`) or a full id ending with its name (`claude-opus-5-5`); `open` resolves it to the value and names the seat by it, `acp:claude/opus`, so two seats are never one model twice. An agent that has not run in the project yet is opened with a notice, and its model is checked when its session starts; one it does not take ends the session, and the seat leaves the table. `open` refuses an agent dispatch does not start or whose start command is not found, and needs the dispatch module on.

Each harness seat is one dispatch session for the life of the table, so it keeps its own conversation. The sessions hang on one held ticket per table, `Roundtable <N>` at the table's Address, made when the runner first starts the seats and closed when the table ends: every dispatch session belongs to a work record, held means autostart never starts it, and one per table keeps the board to one card however many harnesses sit. The runner starts every harness seat's session as it starts, through `dispatch seat`, so each is ready by its turn. dispatch starts them as seats: role `seat`, no turn of its own, the seat's model over the person's choices, a mode that only reads (Codex's `read-only`, Claude Code's `default`), Claude Code's built-in tools cut to `Read`, `Grep` and `Glob` with `Bash`, `Edit`, `Write` and the rest refused by name and no MCP server but Metaform's, so the folder's own Claude Code allow rules cannot let a seat write without asking, every permission request answered at once with reads allowed and the rest refused, file writes and terminals through the client refused, questions declined, only the reading tools on its MCP server, no `ANTHROPIC_API_KEY`, `ANTHROPIC_AUTH_TOKEN`, `OPENAI_API_KEY` or `CODEX_API_KEY` in its environment, and no agent slot taken. On its turn the seat is sent its seat view with dispatch's `message` (the thread shows it from the roundtable); its reply is the last text the agent wrote in that turn, read from the session's thread after the session reads idle. Over 512 characters it is told once and given one retry, as a model seat is. A turn that runs past `roundtable_agent_wait` is interrupted with dispatch's `interrupt` and passes with no submission; the session stays, and its next turn carries only what followed. A session that ends, or does not start in time, takes the seat away: that turn is recorded with the reason, its later turns are skipped, and `status` shows it `gone`. `status` gives each harness seat its session's whole id and `reported`, the model its agent reports the session runs, so the record says which model each seat really was. When the table ends, the runner closes the held ticket and stops each seat's session with dispatch's `stop session=`; a seat whose session is made after that ends itself, since its ticket is closed.

**What a seat sees.** Each seat is one running conversation: a model's messages are kept in its seat row and grow with each turn, an agent seat keeps its own, and a harness seat's is its dispatch session, with a copy of what it was sent and said in its row. On its first turn a seat receives the opening and every turn before its own; on each later turn only the turns since its last reply, its own vetoed ones among them as their verdicts. A turn that entered reads as its text; a vetoed one as its verdict and the link `metaform://roundtable/discussion<N>/submission<M>`.

**The head agent as chair.** Each turn, as it lands, is sent into the head agent's own running session through dispatch's `message` verb, in order, none skipped, a vetoed submission with its verdict and its text, credited to the roundtable. A delivered cursor on the table means a restart neither skips nor repeats a turn. The table never waits for the head agent; a turn it cannot be given now is tried again after the next one.

**Names.** Every seat has a short name, made from its model when the table opens and kept on its seat row: the model's family word, capitalised, passing over a maker's line, a version or a size (`acp:codex/gpt-6-astra` is Astra, `google/gemini-4-argon` Gemini, `anthropic/claude-haiku-5.5` Haiku, `deepseek/deepseek-v4.1-flash` DeepSeek, `z-ai/glm-5.3` GLM), a word with no vowel in capitals, an agent seat by its own name, and a repeat at the same table with 2, then 3. The name is what every turn is credited to, in what the seats see, in Jev's state, the review and the record, in the bubbles and in `status`; a submission keeps it in `name`. A table opened before names has them made from its seats when read. `status` gives whose turn it is by name, `turn_of`. The head agent, when it chairs, goes by a name made the same way: its comments are credited to the model its session's harness runs, as `dispatch options` gives it for that agent (the value its `dispatch_<agent>_model` setting chose, else the one it last reported; its `default` read as the model the agent says that is, so Claude Code's default is Opus), or the harness's own name, Claude, when no model is listed, and with 2 when a seat already has the name. It is kept on the comment's `name`; a comment made before this, or one whose session dispatch cannot place, reads as the head agent, the prompt `name_head`.

**The table as a place.** The seats sit in speaking order round a round table, the first nearest the person's view and the rest clockwise from above, each seat's figure (one of the web page's figures, `agents3d.js`, each seat a different one, wearing its harness's ring) fixed at its chair, a plant in the middle. A figure never leaves its chair; it turns about its own vertical axis to any facing. A seat that has not turned faces the middle of the table. Every seat has three controls: `rotate`, `look` and `look-at`. A harness seat calls them as Metaform's tools in its own session (`roundtable_rotate`, `roundtable_look`, `roundtable_look-at`): they are declared `read`, since they write nothing in the project or the map, only the seat's own facing, and a seat's session serves only the tools that read; dispatch approves a seat's calls of Metaform's own tools. A control acts only for the caller's own seat: a harness seat is known by its dispatch session (the session whose runner id is the caller's METAFORM_SESSION on the caller's METAFORM_WORK, the table's held ticket, named `roundtable:<table>:<position>`), an agent seat names its table and seat and is let through only from the session that answers for it, and every other caller is refused. A model seat through OpenRouter has the same controls as tools, `turn`, `look` and `look_at`, in a tool loop on its turn and while it explores: chat completions with tools, at most six rounds of calls, then one call with the tools withheld whose text is its answer; a model that takes no tools is asked without them. A look's picture reaches a model whose OpenRouter `input_modalities` include image as image content after the tools' answers (the model list is kept in the home for a day); every model gets what is in view as a list, and the conversation it keeps replaces each picture with a line, so a picture is sent once. The tools are a registry, `toolloop.register`, so another control is one more entry. A look's list gives the seat's facing in degrees from its home facing, who is in front of it in words, and everything in view, nearest the middle first, with its bearing from straight ahead (positive to the right), its distance and where it is in words.

**Exploring.** Before the first turn, every harness seat and model seat is sent, at once, exactly "Please take a moment to explore your controls." (`explore` in the prompts), and may turn and look until it answers or `roundtable_explore` seconds pass (60 by default); a harness seat still busy then is interrupted. Its answer is not a submission. An agent seat is sent nothing and may use its controls at any time. The discussion starts when every seat has answered or the time is up. A table explores once: one that has had a turn never does, so a runner started again goes on where the table is. Round mode is otherwise unchanged.

**The watch page and the renderer.** The runner starts a small HTTP server of its own on the loopback (standard library) and keeps its address and a token on the table, `scene`, while it runs; `status` shows the address as `watch`. It serves the watch page, the scene module `resources/scene/scene.js`, and the web module's vendored three.js and `page/agents3d.js`, read and never changed. The watch page shows the table from above, polling `/state` twice a second: who faces whom, figures turning to their facings, raised hands, and each kept answer in a bubble over its seat for about five seconds. The same scene module draws a seat's eye view: the runner owns one headless Chromium through Playwright, WebGL in software (SwiftShader), started on the first look and stopped with the runner, which renders the eye view from the seat's eyes (`eyeOf`), level along its facing, to a 640 by 480 PNG; a look from another process asks the runner for it at `/look` with the token. Playwright and its Chromium are optional: without them, or with no runner running, a look gives the list and says why there is no picture. The raised hand is a placeholder of primitives, `makeHand` in the scene module, standing in for the person's own hand model; nothing raises a hand yet.

**The person watching.** While the page renews `watch`, each turn is followed by `roundtable_pause` seconds in which hold, a comment, continue or end take effect; while nobody watches, the next turn follows at once.

## Settings

All are `person_only`: they decide which models are called on the person's account and how much the table spends.

| Setting | Default | Read by |
|---|---|---|
| `roundtable_keep` | 83 (per cent) | the runner, as the bar for each of the four nouls; the review |
| `roundtable_pause` | 5 seconds | the runner, after each turn while the person watches |
| `roundtable_agent_wait` | 300 seconds | the runner, on an agent seat's turn, and on a harness seat's, for its session to start and for each reply |
| `roundtable_explore` | 60 seconds | the runner, for the seats' time to explore their controls before the first turn |
| `roundtable_rounds` | 8 | the runner, as the most rounds a table runs, unless it was opened with `rounds=` |
| `roundtable_spend` | 2 (US dollars) | the runner, as the most a table spends through OpenRouter, unless it was opened with `spend=` |
| `roundtable_reporter` | anthropic/claude-opus-5.5 | the runner, for the report |

Jev is reached through the chassis's `jev_endpoint` and `jev_model`.

**Limits.** A table ends itself, with its report written, after its last round or once it has spent its most through OpenRouter, and its reason says which. Spend is the usage cost OpenRouter returns with each answer, every model seat's calls, Jev's judgments and an OpenRouter reporter's report, kept on the table as `spent`; a harness seat costs nothing here. The rounds limit is checked as a round ends, the spend limit before each turn, so the turn in flight finishes. When OpenRouter refuses a model seat's turn for want of credits, HTTP 402, the table holds once with that reason and records nothing for the turn; `continue` gives the same seat its turn again.

## Events

None published or subscribed. The runner writes only the module's own tables and the report file.

## Sync and async

Every verb is synchronous. `turn` with `wait` and `run` take long; `run` is never an MCP tool.

## Layers

None: the roundtable writes no layer. Its tables, `place='project'`, so a clear of the map keeps them, version 4, compatible from 1: version 2 added the harness seats' columns, version 3 the scene's (`discussions.explored`, `explore_until` and `scene`, the watch server's address and token; `seats.name` and `facing`, a bearing in degrees, none at its home facing; `submissions.name`), version 4 the limits (`discussions.rounds` and `spend`, the table's own, none for the settings', and `spent`): `discussions`, one row per table, keyed by its number in the project, with its Address, subject, opening, chair, seats in order, state and reason, where the table is (round, position, kept this round), the head agent's delivered cursor, the person's watch, the runner's beat, a submission Jev did not judge, the report, and `seat_work`, the held ticket its harness seats hang on; `seats`, one per seat keyed by table and position, with its running conversation, its last seen turn, an agent seat's pending turn and reply, its kept and taken counts, and a harness seat's `agent`, `model`, dispatch `session`, `cursor` (the last line of its session's thread read) and `gone` (why it left the table); `submissions`, every submission and comment keyed by table and number, with its round, seat, kind (`seat`, `person`, `head`, `none`), text, whether it was accepted, its four nouls and whether it ran over 512; `waiting`, the comments queued for the next gap. Every verb reads and writes them through `ctx.require_store().tables()`.

## Lifecycle and cleanup

No `start` or `stop`. `open` starts the table's runner as a detached process, `python -m metaform roundtable run <N>`, with METAFORM_ROLE `roundtable`; `comment`, `continue` and `end` start one again when the runner has stopped. A runner beats every five seconds; one silent for thirty seconds has stopped. The runner starts the harness seats' sessions as it starts, and stops them when the table ends, before the report, closing their held ticket. The runner ends when the table has ended and its report is written, its log in the system's temporary folder, `metaform-roundtable-<project>-<N>.log`; each harness seat's runner logs to `metaform-dispatch-seat-<ticket>.log`.

## Modules relied on

dispatch, reached through its verbs, never by import: `sessions` to know the head agent and to follow a harness seat's session, `message` to deliver turns to the head agent and to a harness seat, `agents` and `options` to check a harness seat as the table opens, `seat` to start one, `interrupt` for a turn past its time and `stop` when the table ends. map's `work` makes and closes a table's held ticket. Without dispatch the person chairs alone and no harness seat is seated. The mcp module serves the tools and the resource templates.

## Systems supported

Linux, macOS and Windows. No verb narrows them.

## Resources owned

The runner process of each running table, its log, its loopback watch server, and its headless Chromium while it runs. The report files under `docs/roundtables/` in the project's folder belong to the project. OpenRouter's model list is kept in the home at `cache/roundtable-models.json` for a day.

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

A table of Claude Code and Codex seats, on the person's subscriptions, beside models through OpenRouter:

```bash
metaform enable dispatch
metaform dispatch options agent=claude prime=true   # once, so open checks the models; no prompt, no tokens
metaform dispatch options agent=codex prime=true
metaform roundtable open code.alarm.audible seats=acp:claude/opus,acp:codex/gpt-6-astra,moonshotai/kimi-k3 -- "What should a kitchen timer's chime sound like?"
```
