# dispatch

`dispatch intake project_name=<Architect-project-name> text=<complete-design>` creates a separate project for a roundtable build before planning. It chooses a free lowercase hyphenated folder under the user's home, registers it through the standard project registry, then launches the existing intake agent on the design there. Existing paths and registered ids reserve names. Collisions use `-2`, `-3` and onward. The result includes `project`, `folder` and the intake launch state. Wait for the normal intake completion before planning. A failed launch returns the registered identity and error for retry through `dispatch intake` in that folder with the same design. Without `project_name`, intake continues to use the current project.

Metaform starts an agent on a ticket through the Agent Client Protocol, BASE-052.

Session reads select live sessions by default: running, waiting, or ended within one hour. `history=true` and `after=<next>` page older ended sessions, 50 per page by default. `id=<ticket or session id>`, `session=<session id>`, `ids=<ticket id list>` and `session_ids=<session id list>` select explicit records. `latest=true` selects one session before its thread is read. Detail reads preserve complete state and transcripts. Legacy sessions without recorded end times appear in history.

## Purpose

Reopening an ended chat through `talk session=` restores the selected session, including agent names.
Explicit session selection preserves context regardless of the new-chat default `dispatch_resume_chats`.
If restoration is unavailable, the call reports failure without starting a replacement.
A helper resumed for conversation retains its name, brief and history and stays available after replies.
Explicit `dispatch resume` follows the same helper conversation lifecycle.

dispatch starts Claude Code, Codex or Google Antigravity on a work record in the project's folder with Metaform's MCP server. What the agent does shows as notes at the ticket's node, each permission it asks for is a question there, and a person can message it or stop it. Details: `metaform help dispatch`.

`metaform dispatch interrupt <work id>` cancels the current turn and keeps the session available. Messages already
sent stay queued in arrival order. `session=<session id>` restricts the request to the chat you opened. The reply
reports cancellation requested; live status stays busy, with `interrupting=true`, until the turn actually returns.
Interrupting an idle agent does nothing. `stop` ends the entire session and its process group.

## Template version

The template changelog version this module started from: the Unreleased contract after 0.3.0.

## Declaration

- `SUPPORTED_OS = ('linux', 'macos', 'windows')`. Process handling is per system: see Systems supported.
- `DEPENDENCIES = ('agent-client-protocol==1.0.0rc2',)`, the official ACP Python SDK, imported as `acp`. The version is pinned to the current client implementation. The chassis gains no dependency.
- `SHIPS_DISABLED = True`. Enable it with `metaform enable dispatch`.
- `MODULE`: the verbs below, `work.requeued`, `dispatch.rework-limit` and raw `signal.raised` subscriptions, no `start`, `stop` or `status` hook.

## Shared participant names

`agent.name` provides the existing `session_name(identity)` generator through the public provider interface. Roundtables use it for persistent generated names and keep model mappings and score keys private.

## Common base used

- `metaform.module` for the declaration, `Context`, `Stop`, the verb context's `publish_async`, and `work_reads`, through which it reads a ticket's agent glyph as the map module shows it under `map`, BASE-035.
- `metaform.settings` for the three start commands.
- `metaform.data` for the work record (`ticket`, `take_work`), the permission prompts as questions (`ask`, `messages`), and the `dispatch` layer (`layer`, `add_item`, `edit`, `layer_items`).
- `metaform.events` through `ctx.publish_async('map.changed', ...)` after each write the runner makes, and `ctx.listen`, the base's listener for `map.changed` published in other processes, BASE-053.
- `metaform.prompt_files` to read its own `resources/prompts.xml`.

The runner also imports `acp`, the SDK, and nothing else outside the standard library.

`dispatch.roundtable_permissions` captures the standard launch prompt policy and native agent mode for roundtable
setup. `dispatch.permission_choice` exposes the same ACP allow-once selection used by ordinary agent sessions;
roundtables use these providers rather than defining another permission policy.

## Work signals

`metaform dispatch signals [id=<work id>] [active=false]` reads BASE-057 signals. The same verb is available as
the MCP `dispatch` tool with `command=signals`. Ticket reads and the web GUI's sessions response include active signals. Reads do not
change ownership or recover work. With `jev` on and its triage decision chosen, a read of the waiting signals sends
them to Jev to be sorted, which spends the person's credit, so `signals` is declared effect `write` and `open_world`,
never read-only, H17.

Signals are JSON records of kind `signal` in the project's `signals` table since tables version 18, each naming the
metaform it was raised on, `base`, so a permission request of an agent pinned to a metaform no longer active still
reaches the person after a switch; one of a metaform the project no longer holds is not read. Signals a runner on
older code still writes into a metaform's `lines` are carried into it by `carry_conversations`. The conversations themselves, each
session and its thread, are the project's since tables version 17: `agent_sessions`, `session_lines` and
`session_attempts` in `modules/dispatch.sqlite3`, which no clear, restore, new base or switch of bases removes;
`carry_conversations` moves what a metaform's store still holds of them there, idempotently, on each read of the
sessions and through `home.CARRIERS` before a clear and after a restore, PROJ-026. With no element on the map the
person's conversations hang on `conversation-system`, a work id that is no ticket, so their agent needs no intake. A source and signal key identify one active signal, so repeated evidence raises one event.
Activation publishes `signal.raised`, clearing publishes `signal.cleared`, and each also publishes `map.changed`
with the signal payload so other processes and open pages receive it through the existing relay.
A producer may name its signal's `key`, kept on the record as `signal_key`, and clear it itself by publishing the same key with `clear` true. `setup-not-working` is the one any module raises when a feature the person set up is not working, with `feature`, `set_up`, `look` and `report`: the person's system agent takes each such signal as its next turn, after any turn in flight, when it hears it and when it starts, and clears it as it takes it, so each is given once; the turn is the `<setup_trouble>` prompt. While no system agent runs, the web page shows one closable notice whose action starts it.
Crash recovery, reset and fallback session release clear permission signals after ending their session.
The settings are `dispatch_spin_calls` (40 unique tool calls without a completed step), `dispatch_spin_minutes`
(10 minutes), and `dispatch_repeat_failures` (3 consecutive failed calls with the same title, kind and input).
The defaults allow ordinary investigation and retries before asking the orchestrator to intervene. Settings can
be changed with `metaform set --dispatch-spin-calls`, `--dispatch-spin-minutes`, and `--dispatch-repeat-failures`.
Real ticket steps clear spinning signals and reset their counts. Prep sessions and idle chat time do not count.
Elapsed time is evaluated on the next incoming session or map event, with no timer or polling. A silent session
therefore raises its time signal when another event arrives. Permission waiting is reported separately and ends
when its request is answered or cancelled.

Session ends with unfinished work and requeues also raise signals. Dispatch owns the rework
counter, BASE-056: `dispatch_rework_limit` defaults to 3 consecutive agent attempts ending with the ticket open
and no completed ticket step. Set it with `metaform set --dispatch-rework-limit 3`; 0 disables the pause. An attempt
must send a prompt. Person stops, startup failures before a prompt, idle resumes and preparation or system chats
do not count. A completed step or ticket clears the streak. Editing notes, changing the plan and making tool calls
do not establish ticket progress. This uses recorded progress, without judging whether the finished step meets
acceptance.

The counter survives process restarts in a per-ticket `progress` row in the existing `lines` table, outside ACP
transcripts. It records the baseline when an agent takes the ticket and identifies an attempt by its runner, so repeated
release, resumed ACP session ids, manual requeues, reset and verified-dead recovery cannot count the same attempt
twice. No table upgrade or separate scheduler is needed. It begins with observed attempts after installation,
without inferring failures from old sessions that have no baseline.

Reaching the limit announces `dispatch.rework-limit` with `work_id`, `attempts`, `limit` and a streak identity.
One active signal represents each streak; recorded progress or disabling the limit clears it. Explicit starts and
resumes remain available. Ticket progress events reconcile the counter without polling.

## Prompts

`resources/prompts.xml`:

- `instructions`: `dispatch is active.`, listed under "modules available." in the instructions agents read.
- `work` and `work_record`: the one sentence of the hand-off, ahead of the node brief: work the ticket with the `map_work` tool, and, while the memory module is on, record what happened in the work as memory at its node and what is true of the project as knowledge, as the memory prompt says (a draft, CTX-029). An agent's first turn starts with the owner's memory prompt, filled with its ticket's element, while the memory module is on (CTX-026 to CTX-028). How to plan, report each step with its choices and close a ticket is on the `map_work` tool's description and its `op` argument, read when the agent uses it, so it is not pushed.
- `handoff` and `record`: the full brief, no longer sent to any agent; `handoff id=<work id> full=true` prints it ahead of the hand-off. It stays as written while three of its rules, which attach to no tool, wait on a decision.
- `talk`, `system`, `prep`: the conversation agents the person summons from the page, each with its `@CONDITION`, P041.
- `mascot`: the one sentence `system` gains while the person has a mascot, `web_mascot`: it speaks as that character, reads its persona when it needs it from the web module's `persona_<character>`, whose file the sentence names, and acts through the mascot's tools that are on the surface, of `web_say`, `web_go`, `web_point`, `web_emote`, `web_look`, `web_see` and `web_turn`. Nothing more of the mascot is pushed.
- `on_ticket_done`, `on_stopped_open`, `on_failure`: the owner's sentence on recording what was learned at the ticket's node, the turn an agent is given at each end of its ticket's life its setting asks for, P033.
- `work_link`: the request, sent once at the end of a ticket agent's first prompt and never as a turn of its own, to link the files that are entry points of the functionality it works on with `dispatch_link`, so later agents get that node's context. It asks; no write is refused for want of a link. It replaced the lock on writing unlinked files, withdrawn 2026-10-18.
- `peer_note`: the line used for explicit note reads and permitted actionable delivery: whether it is a note, a question or a reply, the sender's agent, ticket number and title, the note, that it is a fellow agent's and not the person's, information only, and how to answer it with `reply=<id>`.

## Assigned tasks and persistent project agents

`metaform dispatch system` opens the `user_agent` assigned task. `metaform tasks read name=<name>` reads one
canonical task definition; `metaform tasks assign name=<name> text="..."` starts a dedicated agent with selected
skills and an optional working folder. The named tasks are `user_agent`, `project_agent`, `composer`,
`facilitator`, `architect` and `intake`. See [the task API](../tasks/README.md) for their exact resources and
lifecycle operations.

A `project_agent` keeps its native ACP session between tickets and receives queued messages and partner-completion
wakes through native events. Project agent skills are selected at functional nodes from the skill layer, the layer `skills`;
reusable skills are served through the MCP Skills extension. Task and skill reads deliver the selected document.

The agent board lives in temporary SQLite at `.metadata/<project-id>/sessions.sqlite`. It retains Next, Current
and Past task phrases with canonical node names, ratings, reported context usage and worksheet completion.
Project agents coordinate partnerships through messages. A completed checklist is appended to the ticket, and both
counterpart ratings complete the round. Finished runs end their contexts and clear completed board records.

## Context and provenance

Exact request provenance is available with `map work op=sources id=<work-id> [source_id=<source-id>]`. Ordinary
ticket and assignment context carries source references and read commands. `map work op=add` and `edit` can take
`source={"text":"<exact source>","reference":"<origin>"}` while task text remains the current interpretation.
Subsequent task or plan changes do not replace the stored source. Actual caller provenance distinguishes user,
agent and change-order direction. A review retains its candidate and requirements revision; newer direction does
not discard unrelated findings. Each finding needs its own supported disposition and later change reference.

Context receipts record accepted delivery, rather than knowledge of the model's hidden context. A retention marker
is diagnostic. Observed compaction changes the context epoch; an omitted marker alone does not prove compaction.
Explicit rereads remain available. Optional `agent.context.changes` providers attach compact references to changed
consumed knowledge on the next already-scheduled turn. Providers coalesce external changes, retain correction and
deletion identities, suppress unrelated or own writes, and acknowledge only the exact accepted revision. The
`agent.context` records accepted instruction deliveries independently of assigned tasks. Neither path
starts a model turn for routine freshness, and no guide or full memory body is broadcast automatically.

ACP compaction observations retain one entity per session and `compactionId`, persisted in `state.compactions` and one stable timeline row. Lifecycle updates preserve omitted fields, replace concrete summary/error values and clear explicit nulls. Summary chunks append in receive order, while a replacement summary supersedes earlier chunks. The v1 transport replaces `_meta` objects. Completed IDs advance the parent delivery epoch once. Repeated completion, history replay and child compactions do not advance it again. Failed, cancelled and unknown statuses remain observable without inferred control behavior. Optional disclosed summaries are user-visible adapter output, with retained semantic context still unknown. Missing IDs remain explicitly labeled legacy observations. The [ACP compaction contract](https://agentclientprotocol.com/rfds/session-compaction) defines these wire semantics.

See [the audit implementation record](../../../../docs/reviews/acp-context-implementation.md) and
[measurements](../../../../docs/reviews/acp-audit-measurements.md) for evidence and limits.

## Verbs

- `start <id> <agent>`, tool `dispatch` command `start`: starts `run` as a process detached from the terminal and returns at once with `state: starting`, the work id, the agent, the runner's pid and its log file. It refuses a ticket that is done or taken, a ticket whose agent glyph's agent is at work on another ticket, VIEW-040, and a start command not found on this system.
- `run <id> <agent>`, CLI only, `open_world`: the ACP session for one ticket in this process, until it ends. A person may run it in a terminal to watch it. On a ticket with an agent glyph, VIEW-040, once the ticket is done it runs a session for the glyph's next ticket not done and not taken, in board order, To do before Backlog, each by its place, and so on until the glyph has none waiting or a session ends with its ticket open; its result then adds `glyph` and `worked`, the work ids in the order worked. It refuses what `start` refuses.
- `message <id> <text>...`: accepts the text for the running agent as `session/prompt`; returns `sent: true`. During a turn, messages and question answers wait in arrival order until the turn ends. One prompt runs at a time. Stop discards the waiting prompts.
- `broadcast [system=true] <text>...`, `open_world`: tells every session running on the project at once, each as `message` tells one, so it reaches each agent at its next turn as the person's own; the person's system agent only with `system=true`. Each receiving thread keeps the line under `broadcast:<id>`, and one line of the broadcast is kept in `lines` under session `broadcasts`: its id, `at`, `text`, each recipient with `delivered` and a failure's `reason`, and the sessions `left_out`. Refused with no session to tell.
- `broadcasts [limit=<n>]`, read: the broadcasts kept on the project, newest first.
- `stop <id> [session=<session id>]`: cancels the selected session, resolves its waiting native permission requests, and ends its agent process group. With no session named, it selects the latest running session.
- `stop-all [home=true]`: explicitly stops project sessions, or this home’s sessions when requested, including runners still starting. It records the halt and reports stopped sessions and failures.
- `new <id> [session=<session id>]`: explicitly ends the selected session and starts a fresh context for its conversation or ticket. Required launch configuration is checked before the prior session ends.
- `handoff id=<work id> [full=true]`: the hand-off: the `work` sentence, followed while memory is on by the owner's sentence on recording at the node, `work_record`; then the ticket's fields, the person's note at its node whole when one is set (`the person's note here:`, read through the memory module's `memory.note`), the nodes it links by address, the OP and EF of the joins its node receives as RE, at most three, the node's brief with the counts there and the calls that read them, and `Links:` with `metaform://<address>` and the ticket's own item, `metaform://<address>/items/<n>`, never what is held there, MCP-039; a runner also sends the two links as ACP `resource_link` blocks beside the text. The reads are named as MCP tool calls in the hand-off a runner sends and over MCP, and as commands on the command line. `full=true` puts the full brief, which is no longer sent, ahead of it. An agent hands work on by giving the next agent the ticket's id; that agent runs this to read its work. An agent dispatch starts over ACP needs none of it: it is sent the same hand-off as its first turn, its counts recorded as told to its session, and its MCP server knows its ticket from `METAFORM_WORK`.
- `raise <node> -- <text>`, CLI only, `open_world`: the person raises an issue on a node; a user-agent conversation takes it up at that node with the report as its text.
- `recover`: explicitly applies dead-runner recovery and reports tickets released or deferred with their reasons. Session reads preserve ownership.
- `wait until=done|stopped|signal [id=<work id>] [since=<UTC time>]`, tool `dispatch` command `wait`: blocks until the ticket is done, its agent stopped with it open (a `stopped-open` or `not-smooth` signal of its latest session), or any signal is raised on it, for at most `dispatch_wait_seconds`. With an id it reads the ticket as it is now, and a done ticket ends any wait. With no id it wakes for any ticket of the project that met the condition at or after `since`, the time of the call when none is given. The answer has `state` (the condition met, or `pending` at the limit), `work_id`, `woke` (each ticket with `state`, `at` and, for stopped and signal, its `signals`), `since`, and `next`, the call that hears what comes after it. A ticket that changes between two calls is not lost; one that changed in the same second the answer was read may be named again. It wakes on `map.changed` from other processes through `ctx.listen` and ignores bare thread lines; the limit ends the one wait, QUAL-015.
- `sessions [id=<work id>|<name>] [thread=false] [since=<seq>]`: live sessions by default; with id, a ticket's sessions or, given an agent's name, the latest session of that name alone; or cursor-paged ended history; `thread=false` leaves threads out. `history=true`, `limit` and `after` page old ended sessions. `ids` and `session_ids` batch only named records. `since` returns only each thread's lines begun after that seq, one range read of the `(session_id, seq)` index, with each session's state line so `states` stays whole, for an incremental thread read. A line grown in place, such as an agent message as it streams, keeps the seq it began with, so it is returned while it grows only when it began after `since`.

- `agents`: the agents dispatch starts, for the person to choose from: each one's `agent`, `label`, start `command`, whether that command is `available` on this system (its first word found on PATH, by PATHEXT on Windows), the `path` found, whether it is the `default`, and the `next` step when it is not found; with a project, `room`, how many more agents may be summoned now.
- `intake [agent=<agent>] [resume=true] [map=extend|new [name=<name>]] [-- <text>]`: starts an agent on the project's intake. Its first turn is the intake exactly as `intake prompt` serves it, with the person's text in its prompt slot; the text reaches the runner in the launch's `raised` row, never in an argument, and the runner clears it once read. It holds no ticket: its work id is `intake-<token>`, and `message`, `interrupt`, `stop`, `permit` and `configure` take it as they take a ticket's id. It counts as a summoned agent, its launch holding its slot in `raised` until its session is made, and stays to talk until stopped. A second intake while one runs or starts is refused, naming the one at work, for as long as its runner lives: the launch is noted under the project's intake lock and its runner holds `intake.agent` until it ends, and `sessions` lists the launch as `starting` until its session is made; `stop` ends it while starting. `map=` is the person's choice on a mapped project: `extend` checks and extends the map in use, `new` starts a new map beside it, named `name` or by its date, and the agent's `intake start` follows it; an intake being recorded that no agent of Metaform's started is refused unless `resume=true`, which starts the agent to resume it.
- `helper [agent=<agent>] [wait=true] -- <brief>`, `open_world`, code.dispatcher.agent#78: starts a helper agent with a brief and no ticket, for quick work the person's system agent hands off so it stays reachable in the chat: a diagnosis, a small fix, a check. Only the person and their system agent start one; any other agent is refused and asks the system agent with a note. Use it, never a harness's own background subagents, which Metaform cannot see. Its work id is `helper-<token>`; the brief reaches the runner in the launch's `raised` row, as an intake's words do, and is kept in the session's state as `brief`, so `sessions id=<work id>` shows it and its whole thread, during and after. It runs through the same gate and runner as any agent: a figure on the map at the DE, listed in the Agents menu as `Helper: <brief>`, its thread live in the chat, counted in `spend`, and reached by `message`, `interrupt`, `stop` and `stop-all`. Its first turn is the `helper` prompt with the brief. When its turns are drained it records one UI-only project update of kind `result`, state `done` or `failed`, named `helper <token>`, the words saying where its result is read, and ends; neither completion nor failure alone wakes the system agent or enters a later turn. A turn the person interrupted is not followed by the report: the helper waits for what they say. `resume` brings an ended helper back with its brief. It takes the helper capacity, never a ticket agent's slot (below).
- `resume <id> [session=<session id>]`: resumes an ended session in place, the latest of the ticket when none is named; an agent's name, as `id` or `session`, names the latest session of that name, so `resume CosmicArgon` calls that context back, through `session/resume` where the agent offers it and otherwise `session/load`, whose replay is not written into the thread again. The session's own row runs again and its thread goes on. An agent whose ticket is still taken by that session goes on as its agent; any other session comes back as a summoned conversation. It sends nothing: the agent waits for the person's next message. A session whose agent offered neither, or whose folder is gone, is refused with `talk session=<work id>:<session id>` as the next step.
- `permit <id> <request> -- <option>`, CLI only: answers a waiting permission request with the option named by its id or its name, at once; its question at the node, when there is one, is closed with the option's name. A question the agent asked through elicitation is answered the same way, the words being the answer, or `decline`. Not offered over MCP, so an agent cannot answer its own request.
- `configure <id> <setting> -- <value>`, CLI only: sets one of a running session's settings as its state lists them: the agent's modes as the setting `mode`, through `session/set_mode`, and each config option, a model among them, through `session/set_config_option`; a choice by its value or its name, a switch by on or off. The thread notes the change. Not offered over MCP, so an agent cannot change its own mode.
- `prompts <id> <prompts> [session=] [confirm=true]`, CLI only: chooses how one running session's permission requests are answered from now on, `ask_all`, `approve-reads` or `approve-all` as `dispatch_prompts` takes them, for that session alone, over its launch's `prompts` and the project's setting. The runner keeps it in the session's state line, so it holds when the session is resumed, applies it to the session's later requests at once, and approves each request waiting now that the choice allows with the agent's allow-once option. `approve-all` lets the agent act without asking, so it is refused without `confirm=true`. The person's own, as `start`'s `prompts=` is. A running session's read carries `prompts` and `prompts_from` (`session`, `launch` or `project`), what is in force now and whose choice it is. Not offered over MCP.
- `options [agent=<agent>] [prime=true]`: what each agent offered at its last session in this project, from the `catalog` table, by agent and version: each setting with its `key` (its ACP category when reserved, `mode`, `model`, `model_config` or `thought_level`, else its id), `name`, `current` value and `choices`, the value its own setting gives it as `chosen` and that setting's key as `setting`, its auth methods and its extensions (`steering`, `auth_status`, `logout`, `resume`, `load`, `fork`, `close`). An agent that has not run shows none, with `options agent=<agent> prime=true` as `next`: that starts the agent, makes one session with no MCP server, reads what `session/new` answered, closes it with `session/close` where offered and ends the agent, with no prompt and so no tokens.
- `tune <id> [model=<value>] [effort=<value>]`: sets the ticket’s native model and effort choices, applied over adapter defaults. `none` clears a choice. Values are checked against the adapter’s advertised options and applied to a running session when supported. The operation records the actual caller.
- `cancel <id> [-- <reason>]`: cancels the ticket and its running native session, records the actual caller and reason, and retains the session history.
- `login <agent> [method=<id>]`, CLI only, the person's: the agent's ACP auth methods, asked as a client that can run a terminal login so every method is listed. An `agent` method is called with `authenticate`; a `terminal` method runs the agent's command with the method's arguments and environment in this terminal, refused with the reason when there is none, and then the agent is started afresh and asked whether it is logged in, by its authStatus or by whether `session/new` answers, ACP's terminal authentication; an `env_var` method names the variables to set. With several methods and none named, they are listed.
- `spend [id=<work id>]`: what was spent today, on the ticket and by run: `tokens`, an estimate of what is billed, the cost agents reported by currency, `costs` (with `cost` and `currency` when there is one currency), and `unmetered` per measure: under `tokens` the sessions whose agent reported no usage, under `cost` those whose agent reports no cost, as Codex; with each budget, and a notice when a cost budget is set and an agent reports no cost.
- `registry [agent=<id>] [add=<id>] [remove=<id>] [upgrade=true] [refresh=true]`: the ACP Registry's agents, each with its version, its distributions, whether one runs here and the version pinned here; dispatch's own agents with the registry's version beside the command set for each and the `metaform set` that pins it. `add`, `remove` and `upgrade` are the person's.
- `publication [out=<folder>] [id=] [version=] [package=] [license_url=] ...`, CLI only: the registry entry that would publish `dispatch serve` (run with `uvx`), with its icon, checked against the registry's `agent.schema.json` and its CI rules, `problems` listing what keeps it from passing; with `out`, written as `<id>/agent.json` and `<id>/icon.svg` for review. Nothing is sent: publishing is the person's pull request to github.com/agentclientprotocol/registry.
- `note [target_project=<id>] to=<session id, work id, address#n or system>|at=<Address>|file=<path>|topic=<words>|reply=<note id> [wait=<seconds>] -- <text>`: every registered agent can discover and message its peers, including conversations, editor sessions, independent assessments and queued swarm members. `to=system` is the person's system agent of this project or of `target_project=`, named by project, not by session: while none of its sessions runs, the note is kept in its last conversation's thread, marked `waiting`, and its next system session, resumed or new, takes it; a reply to a system agent whose session ended waits the same way, while a reply to an ended ticket agent is refused. Notes that arrive while one waits for its turn join that turn, so a burst is one turn; the person's word and a relayed decision never join one. The sender comes from the actual registered session; naming a role does not impersonate one. Notes and threaded replies enter the recipient's normal turn queue and do not interrupt it. A queued or suspended assignment keeps its messages until its recorded continuation. The existing `peer:<id>` thread line retains sender, team, assignment and recipient session identities, with `queued`, `delivered`, `read`, `replied` or `failed` delivery states. `wait=` waits for replies for up to 120 seconds through the existing event relay. `decision=true` marks a note that relays the person's decision: only the person's own system agent sends one, in the turn the person's message started, and it is refused otherwise. Its line is a `user_direction` that carries that message as `decision`; each recipient's assignment keeps it as the person's direction, so a review under way closes on it, and each runner takes it into the turn in flight where the agent offers steering, else ahead of every prompt waiting. A runner gives a session the same words from the same sender once while the first still waits for its turn: a second note of the same kind, sender, reply, relayed message and words, spacing aside, is marked delivered and gives no turn. Once a turn has carried the first, the same words come again. There are no fixed message-length, hourly, pair-rate or recipient-count caps; configured controls and the dynamic blacklist govern operation.
- `link file=<path> node=<Address>`: links a file to the element whose functionality it realizes, code.dispatcher.agent#3d: the path, from the project folder or the caller's working folder (a worktree's file named as in the worktree), is added as a `path` ref to the element's item of the `sources` layer, the refs the runner places files by, beside the refs it holds; its first item there is made when it has none, and the `sources` layer when the project has none. An Address no element has yet is made first in the map's base. Linking a file again changes nothing (`linked: false`). Answers `file`, `node`, `linked`, `made` and `said`. A running runner reads the sources layer again on the change, so the file is placed at once.
- `notes [note=<id>] [limit=]`, a read: the caller's notes, sent and received, the latest first, each with `states` by receiver; `note=` gives one note and the replies threaded to it.
- `peers [at=<Address>|file=<path>|topic=<words>]`, a read: who is at work where, each agent on an open, taken ticket with its `work_id`, `item`, `title`, `address`, `agent`, `activity`, `files` (the latest first, each with its `action`, the file `lines` its calls named and how many lines its edits `changed`) and what it `said` last, the caller's own marked `yours`. With a filter it answers who else is in that part or file before an edit, with `ready`, the note that asks them.
- `fork <id> [session=] [fork=<fork id>] -- <text>`: ACP's `session/fork` where the agent offers it, a side conversation keeping the session's context, given the same Metaform server and identity, its thread a child of the session's; with `fork=`, the text goes to that fork as its next turn.
- `serve [agent=<agent>|none] [-- <adapter command>]`, CLI only, a transport, BASE-062: Metaform as an editor's ACP agent over standard input and output, registered by `metaform install zed` and `metaform install jetbrains`. With an agent behind it, a transparent proxy: every message passes through as it was, the editor's client capabilities and the agent's requests of the editor included; `session/new`, `session/load` and `session/resume` gain Metaform's MCP server with the session's `METAFORM_SESSION`; `session/list` adds the dispatch sessions of the same agent; the agent's slash commands gain Metaform's, its MCP tools by name, answered by Metaform with no turn; and the session is recorded on the held ticket "Sessions from editors", so the dock and the 3D layer show it; `message session=<id>` reaches that session, steered into the turn in flight when the agent offers `_session/steering`, else in a turn of its own after any in flight, and `interrupt session=<id>` cancels its turn; without `session=`, the latest session still running. The agent's order is kept: a response Metaform takes holds the agent's next line until it is passed on. `session/fork` is handled as `session/new`; `session/delete` keeps the session out of Metaform's list pages too, which carry the agent's titles and last activity. Messages pass to the editor first and are recorded after, on a task per session. Turns are sequential: an editor prompt waits for the page's turn. An agent's terminal login is rewritten so the editor's login terminal runs it through serve (`METAFORM_SERVE_LOGIN`). Editor sessions take no `dispatch_agents` slot. A session a runner or another editor is running is refused to `session/load`; `session/list` follows the agent's own pages and filters by `cwd`. Notices (Session Notices where the editor takes them) say when the agent is missing or Metaform's server was not added; Metaform's own messages carry a `messageId`; `$/cancel_request` is honoured. With `agent=none`, or when the setting's agent is not found, Metaform alone: its commands, `session/list` and `session/load` of the project's dispatch sessions, and the `serve_free_text` prompt for free text; no model starts.

Session control has no role-based authority filter. Messages retain their actual sender identity. Native permission responses remain distinct from mode and configuration changes.

`message`, `stop`, `permit` and `configure` with no agent running on the ticket name `metaform dispatch start <id> <agent>` as the next step.

Eligible agents is a map-owned ticket setting, MAP-058. Explicit `start` and `run` refuse an agent outside the list. A glyph's runner selects its next eligible ticket in board order and leaves skipped tickets' glyphs and positions intact. Chat uses the configured agent when eligible, otherwise the first listed agent. Tickets with no list allow Any agent.

## Settings

- `dispatch_claude`, default `npx -y @agentclientprotocol/claude-agent-acp@0.89.1`, the ACP Registry's claude-acp.
- `dispatch_codex`, default `npx -y @agentclientprotocol/codex-acp@2.2.2`, the registry's codex-acp.
- `dispatch_antigravity`, default `metaform dispatch adapter antigravity-acp@1.4.1`. The launcher installs Google LLC's native ACP archive once, then replaces itself with its pinned executable. Linux runs `agy_acp_server.par --uid=`, macOS runs `agy_acp_server.par`, Windows runs `agy_acp_server.exe`. The manifest ships at `resources/registry/antigravity-acp.json`, copied from the [official ACP Registry](https://github.com/agentclientprotocol/registry/blob/main/antigravity-acp/agent.json) on 2026-10-21. Login remains in Antigravity. `dispatch registry add=antigravity-acp` explicitly installs the registry's current version and updates the command.
- The registry is read again after 24 hours (`REGISTRY_HOURS`), or at once with `refresh=true`.
- `dispatch_registry_agents`, global: the ACP Registry's other agents dispatch starts, each pinned as `<id>@<version>` by `registry add=<id>`, which keeps its entry and, for a binary, its archive checked against its sha256 and unpacked, under `agents/<id>/<version>` in the Metaform home. `dispatch_registry_url`, the registry's `latest` file by default, or a private mirror's file; `dispatch_registry_hours`, 24, how long a read is kept.
- `dispatch_client_files` and `dispatch_client_terminal`, on: the runner offers ACP's `fs/*` and `terminal/*`, confined to the session's folder; one terminal keeps 1024 KB of output when the agent names no limit (`TERMINAL_KB`).
- Each turn is an OpenTelemetry `invoke_agent` span with its `gen_ai.usage` attributes, recorded only where an OpenTelemetry SDK is set up.
- `dispatch_record_on_stop` and `dispatch_record_on_failure`, off: as `dispatch_record_on_finish`, once per session when an agent stops with its ticket open or its turn ends in an error.
- `dispatch_abandoned_branch_days`, 30: a ticket closed without merging keeps its committed branch this long, with `dispatch_worktrees` on.
- `dispatch_agent`, claude by default: the adapter selected for an explicit launch when none is named. Choosing another adapter for one launch leaves this default unchanged.
- `dispatch_agents` and `dispatch_machine_agents`: configured project and machine agent capacity used by native resource-limited launches. Explicit user conversations, intake and temporary helpers retain their existing capacity treatment.
- `--dispatch-wait-seconds`, 50 by default, a switch of `wait` alone, never stored (`per_call`): the longest one `wait` blocks before it answers `pending`; below Codex's tool timeout of about 60 s, so the agent calling it gets an answer.
- `dispatch_record_on_finish`, `when-missing` by default, labeled Record on finish. When an agent's ticket is done, the runner gives it one more turn, the `on_ticket_done` prompt with `<node/>` filled by the element's address or `join:<id>`, before the session ends: `when-missing` sends it only when no memory join or observation at the ticket's node has `by` equal to the session's `runner`, `always` sends it every time, `off` never. It holds the owner's sentence on recording at the node, P033; nothing is sent when it is emptied, or while the memory module is not on the project's surface.
- `dispatch_<agent>_<option>`, one setting for each of an agent's options, so setting one never touches another: for claude, codex and antigravity `dispatch_<agent>_mode`, `dispatch_<agent>_model`, `dispatch_<agent>_effort` (ACP `thought_level`) and `dispatch_<agent>_fast` (`model_config`), and `dispatch_claude_agent` and `dispatch_codex_collaboration_mode`, options without an ACP category. Each is `default`, which sends nothing and leaves the agent's own, or a value the agent offered at its last session here, its choices in the agent's own words; only `default` until it has run once or been primed, and a value it never offered is refused with the list. Applied with `session/set_config_option` (`session/set_mode` for a mode) when a session starts, is loaded or resumed, mode first, then model, model_config and thought_level, so a model switch never undoes the effort chosen with it. They sit in the section `Agent options/<agent's name>`: the TUI opens it as a menu, agent, option, value; the web settings screen shows each agent's under its heading. They replace `dispatch_agent_options`, whose stored entries move to them once as dispatch starts. A resume or load that names no settings leaves the catalog's as they were.
- A message to a turn in flight is delivered into it with `_session/steering` when the agent advertises it in its initialize answer's `_meta.steering.supported`; with an agent that does not, it waits for the turn's end.
- `dispatch_silence_seconds`, 300 by default: a turn that passes this long with no update from the agent raises the `silent` signal, naming `dispatch interrupt`. The clock is one timer per turn, started again by every update while a turn is in flight, so a turn silent twice is signalled twice, and stopped while a permission request or a question waits for the person.
- `dispatch_elicitation`, `ask` by default: a question the head agent puts to the person through ACP's elicitation, a form or a page to open, is asked on the page as a card and, when the session has a node and no field is secret, at the node too; `decline` answers it no at once. `dispatch_prompts` never answers one. A form of one question, a choice and its free-text companion (claude-agent-acp's "Other", codex-acp's note), takes a choice, the person's own words, or both; any form takes `name: value` lines; the answer is held to the schema's limits and fields left out take their default; an answer that fills no field is asked again, never sent as an empty accept. Any other agent, a ticket's agent among them, never asks the person, VIEW-045: its question is answered at once with the `decide` prompt in each own-words field, telling it to decide and record why in its ticket, or declined when the form has no such field.
- Each session keeps 64 KB of the agent's stderr in its thread, redacted (`STDERR_KB`).
- `dispatch_budget_ticket`, `dispatch_budget_run` and `dispatch_budget_day`, billable tokens, and `dispatch_budget_cost_ticket` and `dispatch_budget_cost_day`, hundredths of the currency the agent reports, all 0 by default, meaning no limit, until the person sets them, M01. Billable tokens are input, output and cache writes, with cache reads at a tenth, as each agent reports them at a turn's end; cost is what each usage update added to the session's running total. A run is one runner with every retry of its sessions. `dispatch_budget_action`, `signal` by default: a budget reached raises the `budget` signal and nothing more starts or retries; `interrupt` also cancels the turn in flight. The adapters report tokens, and claude-agent-acp its cost, only as a turn ends, so during a turn the token budgets are held against an estimate from the context in use the agent reports after each model call, which can stop a runaway turn part way; cost budgets act at the turn's end, each currency held on its own. A cost reported before the runner's first prompt, as after a load or resume, is the session's baseline.
- `dispatch_recovery`, `manual` by default. `automatic` verifies runner death and cleans up its abandoned agent before returning its ticket to To do. Set it with `metaform set --dispatch-recovery=automatic`, or restore manual recovery with `metaform set --dispatch-recovery=manual`.
- `dispatch_serve_agent`, `default` by default: the agent `serve` passes through when no command follows `--`: `default` is `dispatch_agent`, `none` is Metaform alone. Metaform's commands are always the editor's slash commands, and editor sessions are always recorded for the page; an agent that takes MCP over ACP gets Metaform's server that way.

`start` and `run` read the one for the agent named. Each command runs the person's own installed agent under the person's own login, with the person's environment passed through unchanged except that the folder of the interpreter running Metaform comes first on PATH, so `metaform` and `python` in the agent's shell reach the install that dispatched it. Metaform never reads, stores or sends credentials. An agent that needs a login raises the `login-needed` signal, from an `auth_required` answer to `session/new` or a logged-out `_auth/status_update`, and the person logs in with `dispatch login <agent>`, which runs the agent's own login; nothing logs in by itself.

## Events

- Publishes `map.changed` after each write the runner makes, since those writes are made inside one long command and would otherwise be announced only when it ends.
- The runner listens for `map.changed` through the base, `ctx.listen`, BASE-053: each one published in another process, a command, the MCP server, the web server or another runner, for the runner's project, makes it read the questions it asked and those its agent asked itself. This is how an answer given from the web GUI, the CLI or MCP reaches the agent without polling, QUAL-015. The runner's own writes do not reach its listener. A change to the map itself makes it read the sources layer's refs again when it next places a file. The control port takes `status`, `message`, `interrupt`, `stop`, `permit`, `configure` and `prompts`.
- A new permission request announces `dispatch_tables` `dispatch.session_lines` and `dispatch.permissions`, with its `permission-waiting` signal carrying `request` beside `message_id`.

## What ACP gives beyond text

Every session is named as it starts (`names.py`, `session_name`): two words from the lists in `resources/names`, `adjectives.txt` and `nouns.txt`, 256 words each, worked out from the session's id alone. The id's UTF-8 bytes are hashed with 32-bit FNV-1a, the hash is folded to 16 bits, the high byte picks the adjective and the low byte the noun, and the two are capitalized and joined with nothing between, `StableComet`. The same id always gives the same name, so a resumed session keeps its name. Two live sessions may share a name; that is accepted, and nothing avoids a clash. The name is kept on the session's state line, `name`, in the write that records the session. The agent is told it in one line, the `named` prompt, at the head of its first turn and of its first turn after a compaction, since it signs its messages with it. `sessions`, `talk session=` and `resume` take a name where they take a session id, for the latest session of that name. The page names an agent first and its ticket's number after it, and a figure under the pointer is named beside it with the model and the thinking level it runs. No table changes.

Each session keeps a few lines whose text is JSON, read back structured by `sessions`:

- `state`, one per session, kept at its latest and returned under `states` by session id, out of the thread: the agent and its `agent_info`, its `capabilities` (`load`, `resume`, `list`, `close`, `fork`, `delete`, `image`, `audio`, `embedded_context`, and the extensions `steering`, `auth_status`, `logout`), the `cwd` it works in, its `settings` (each `id`, `name`, `description`, `category`, `type` select or boolean, `current`, `options` with `value`, `name`, `description` and `group`, and `source`, `mode` or `option`), its slash `commands` (`name`, `description`, `hint`), its `plan` entries, its `usage` and `tokens`, its `title`, its `name`, whether and how it was `resumed`, and the parts of the map it has `touched`, the latest first.
- `tool_detail`, one per tool call that names a file or a terminal, attached to the call's own line as `data`: its `diffs`, each a unified `patch` with the lines `added` and `removed`, its `locations` with their lines, its `terminals`, and the `nodes` each file belongs to on the map, with `exact`. A file belongs to the parts whose refs in the `sources` layer name it, `exact` true, or else the nearest folder holding it, `exact` false.
- `permission`, one per request, in the thread where it was asked, with `data`: its `request` id, the `message_id` of its question at the node when there is one, the tool call, its `options` with their ids, names and kinds, the call's detail, and its `state`, waiting, answered, unmatched or cancelled, with the option `chosen`.
- `elicitation`, one per question the agent put to the person through ACP's `elicitation/create`, with `data`: its `request`, `message_id`, `message`, its `fields` (key, title, type, choices, required) or its `url` and `host`, the `suggestions` offered, its scope, `session_id`, `tool_call_id` and `subagent`, whether it is `secret` (a `_meta` marks a field so; its answer is never kept), a `deadline` the agent gave, and its `state`, waiting, answered, declined, cancelled, completed (after `elicitation/complete`, which also answers a waiting one accept) or withdrawn (the agent's `$/cancel_request`, answered with -32800). A permission request the agent withdraws the same way is closed `withdrawn`. The page draws each as a card answered with its own buttons, and the chat says "Waiting for your answer". The client advertises `clientCapabilities.elicitation.form` and `.url`, so claude-agent-acp's AskUserQuestion, codex-acp's request for input and an MCP server's form or sign-in reach the person instead of being answered empty. A question waiting raises `question-waiting`.
- `agent_notice`: one per ACP session notice, `severity`, `title` and `description`, live only, never replayed; the client advertises `clientCapabilities.session.notices`.

- `stderr`: the agent's standard error, batched each second into one line, anything that looks like a credential replaced by `[redacted]`, up to `dispatch_stderr_kb` a session; the runner's log has it all, redacted, and a failure note carries its last lines.
- `subagent`: one per subagent session the agent started, P016, with `data`: its `session_id`, `name`, `task`, `state`, when it `started`, and `fork`, true only for a fork made with `session/fork`. Its own thread is kept under its session id, and `sessions` returns each with its `lines` under `subagents`. The client advertises `clientCapabilities.subagents`, so claude-agent-acp and codex-acp send `subagent_spawned` and `subagent_state_update` and give a subagent's updates its own session id; the SDK's schema does not know the two updates yet, so the runner reads them as they arrive, through the connection's observer.
- `state` also holds `spent`, the session's tokens and cost so far, and `auth`, the login the agent pushes with `_auth/status_update` when it advertises authStatus; `capabilities` adds `steering`, `auth_status` and `logout`.

The client offers its own file reads and writes, ACP's `fs/*`, and its own terminals, `terminal/*`, while `dispatch_client_files` and `dispatch_client_terminal` are on, as they are by default, each confined to the folder the session works in; it takes boolean config options and takes subagent sessions.

## Native launch and observation

Explicit launches use `start_runner` and the existing process ledger, configured capacity and budgets, and halt
records. Live subjects are reused to avoid duplicate conversations. Runner logs remain under
`run/dispatch/logs/` in the Metaform home.

Each runner holds a native lease. The web server's `dispatch.deaths` provider observes lease release and reports
verified unexpected exits to pages and other processes. This observation preserves session records and cleanup
without selecting or starting replacement work. `dispatch recover` explicitly applies the configured recovery
policy and reports released or deferred tickets. Session reads remain observational.

## Budgets and explicit resumption

Configured token and cost budgets continue to apply to native execution. Usage and session origin remain
recorded. Explicit `resume` and selected-session chat restoration use the adapter's actual load/resume support
and reuse an existing live runner. Further work is launched explicitly through dispatch or assigned tasks.

## Sync and async

Startup and restart check runner status before the reservation transaction. Inside that transaction, scheduling
uses stored session rows and reuses checked status only for unchanged runner identities and sequences. New or
changed running rows block startup. Admission runs before reservation and again at the spawn gate. Runner socket
waits and legacy spending transfers therefore hold no reservation write lock.

`run` and `wait` are coroutines, as are the runner's ACP handlers. `start`, `message`, `stop` and `handoff` are plain functions, and the listener hands each change to the runner's loop with `call_soon_threadsafe`. The runner makes each store call in a worker thread, so its loop is never held by a write.

## Layers

`dispatch`, kind `layer`, mutable, hideable, made ready on the first run so it is seen in context. At the ticket's node it holds:

- one session record per run, its value a sentence of the agent, the session id and its state, its `extra` holding `dispatch: session`, the work id, agent, session id, the recovery evidence, the runner's pid, its control port and token, and `state` running or ended, with how it ended;
- notes, `extra` `dispatch: note` with the work id, agent, session id and the update's kind. A tool call is one note, changed in place as its status changes. Each run of the agent's message or thought text is one note. The plan and each other kind of update is one note, kept at its latest. Each turn's end is one note.

The steps on the ticket stay the agent's own, MAP-053. The session id is also on the work record, in `taken_by`, as `<agent> <session id>`, because a work record has no `extra`.

## Ticket commits

A resolved ticket closes directly through done or a move to Done. Small reversible fixes proceed directly. Additional validation names its acceptance
condition and a concrete reason from the requested outcome, material risk or an explicit project requirement.
Use the smallest adequate check, then stop. Do not add routine test suites, critics or repeated check cycles.
Preserve requested reviews, configured checks and application data validation. Record the resolution and
available evidence. User confirmation after delivery never gates closure. Commit, merge, push, activation, review and delivery receipts never gate closure.
Saving the ticket's feature commit is a separate delivery step. The saved candidate remains available for explicit
local integration through `dispatch merge`. Delivery failures are reported separately and never keep a resolved error open.
The ticket or assignment retains ticket identity, artifacts, verification and available branch and commit IDs.
Projects without Git record the checked result without inventing commits or missing-commit faults.
Actual recurrence or supported review findings may reopen faults. An actual unresolved repair cannot be reported
as successful. Restart only when the particular project and repair require it; restart never gates closure.
Commit subjects use the ticket
title. Commit bodies retain the resolution, its why and a canonical `Ticket state` JSON snapshot of map-owned ticket
rows and citation metadata. The archive compares that snapshot with current state before deleting a ticket, so a
same-second completion with unchanged resolution cannot discard newer notes or progress. Five trailers retain
ticket identity: `Metaform-Ticket`
(work id), `Metaform-Number` (Address and number), `Metaform-Node` (Address), `Metaform-Board` (board name, empty for
the first board), and `Metaform-Agent` (agent id and name). Empty completions make empty commits with the same
message. `Metaform-Target` preserves the attachment as `element:<address>` or `join:<id>` so archive counts keep
join work separate from its receiver element. Configured checks contribute verification evidence; an unset
test command does not strand work.
Ticket branches and dirty worktrees stay intact. Repeated delivery recovers its journal without another feature
commit. Direct closure clears a resolved fault ticket's light through the existing completion events.

Ordinary local integration accepts a dirty project checkout (`merge.advance`, 2026-10-21). Clean paths take the integrated
content. Modified paths receive its hunks through a three-way merge in the working copy and, when staged, their
index entries. Conflicting local paths remain unchanged and are reported in the integration result. The ticket stays
closed in every case.

The ticket's explicit `Merge` action passes its expected saved `head` to `dispatch merge`. A verified saved
implementation and a recorded result are required, including for already-Done tickets. The action integrates
locally, never pushes, preserves peer staging and nonconflicting dirty files, then removes
only the clean registered ticket worktree. Its branch remains available. Conflicting local paths roll back this
attempt without advancing the shared branch. Active agents and explicit stops prevent the action. Dispatch
admission covers final landing and cleanup, while the project Git lock serializes merges and repeated requests.
An open submission reaches Done after safe cleanup. Existing Done timestamps and resolution stay unchanged.
Uncommitted, untracked or ignored work, new commits or uncertain ownership retain the directory with a precise
cleanup reason. `Clean worktree` retries cleanup after an integrated candidate without another merge.
Integration and cleanup evidence use the existing candidate journal and scoped ticket events. Board refreshes
read saved metadata without Git commands. Older Done candidates remain visible beyond the archive cutoff.

Ordinary completion and explicit local integration never push. Explicit publishing and manual reviews remain
available when requested. Runtime activation remains separate from ticket closure. Resolve conflicts while preserving peer work.

New ticket worktrees start from committed HEAD. Shared staged changes, unstaged edits, deletions and untracked
files stay in the shared checkout. The recorded starting commit still excludes dirty startup snapshots from
merges of older ticket branches.

Cancelled and failed tickets make no completion commit. Uncommitted worktree edits stay until the existing
abandoned-branch retention expires. A failed feature commit is reported as separate delivery trouble
at `code.dispatcher.agent`; the resolved source ticket remains closed.

Shared-checkout commits use a private Git index. The runner retains startup dirty paths and every successful file
write separately from its bounded activity display. Earlier changes, overlapping writers and files changed after
the recorded write prevent attribution and are reported instead of committed. Only explicitly linked files qualify;
temporary output and diagnostic files stay out. Peer staging and unrelated uncommitted edits remain intact.

Explicit publishing handles rejected pushes without rewriting history or automatically stashing peer edits.
Git conflicts are aborted and reported once to the system agent's inbox. Commit and explicit publishing results
remain in the session thread. Repeated completion recovers the ticket commit rather than making another one.

## Lifecycle and cleanup

No `start` or `stop` hook. A runner owns one agent process group, one loopback listening socket and its tasks. The session ends when a prompt turn ends with the ticket done, when `stop` is run, when the agent's process ends, or on Ctrl+C in a foreground `run`. Ending ends the agent's process group and marks the session record ended.

Session reads, including MCP, CLI, the ticket's `work_read` and the workbench, verify stored running rows against the ticket, the recorded pid and the runner's authenticated `status` reply. The reply checks the ACP adapter as well as the runner. A completed ticket, a pid whose command line is not `dispatch run <work id>`, a refused control connection or a reply for another session reads as ended. A runner on a glyph goes on to the glyph's next ticket in the same process, so its command line names the work id it started on; its own reply shows it runs the later ticket. A timeout or an older runner without status reads as running only when its pid runs that work id. Reads keep the stored row and transcript intact. An idle adapter on an open ticket remains running and can receive another message.

Public session reads also report `activity`, separately from lifecycle: `working` for an executing prompt turn,
`waiting` for a permission request or an idle turn with its own unanswered questions, and `idle` for no executing
turn or wait. The runner reports these from its turn and wait tracking, never from a PID. An older runner retains
its lifecycle uncertainty; one unambiguous latest `end_turn` supports `idle`, while later output, tied latest
records or incomplete telemetry yield `unknown`. Reads persist no guesses. Turn and permission transitions
announce a dispatch refresh; idle and waiting sessions keep their tickets, questions and message controls.

A failed background callback wakes the runner into shutdown. Cleanup still closes the agent, listener and control server when a database schema change prevents a final transcript or session write. If the runner cannot release its ticket and mark the session ended, it retries in a fresh process using the code on disk. If that also fails, the runner log names the session and ticket and gives the command to return the ticket to To do. The schema compatibility check remains in force.

On Linux and macOS, SIGTERM ends the session and takes no next ticket. Cleanup waits for an in-flight startup acquisition so an adapter or ticket cannot arrive after cleanup finishes. A forced kill, including process termination on Windows, cannot run cleanup. The default manual policy preserves its ticket's ownership until the person or orchestrator returns it, MAP-049. With automatic recovery selected, `dispatch recover` verifies process birth identities and exact session ownership, ends the abandoned agent group and returns work to To do with its progress intact. No timer polls for death. Birth identities and resource ownership are kept privately in the session row's `recovery` column, added by tables version 9, which older runners' code still reads and writes, STORE-029. Ticket ownership and the initial session row commit together, so a forced kill cannot leave an acquired ticket without its recovery record. Slow process cleanup holds no project write lock, and a final atomic ownership check preserves reassignment during cleanup. Legacy sessions, unreadable processes, changed ownership, reused adapter PIDs and unverified surviving groups require manual attention. Live agent group cleanup requires Linux 6.9 or later with pidfd process-group signalling, which binds the signal to the verified process even if its numeric PID is reused. On macOS, Windows or kernels without this capability, recovery defers live agent cleanup to a person instead of signalling a recyclable PID. Python builds without pidfd APIs use the equivalent libc syscalls on 64-bit x86-64 and arm64 Linux; other unsupported builds report manual cleanup. An already empty verified POSIX group needs no signal. A deferred recovery reports its reason and the manual return command. Reads remain observational regardless of policy.

An agent that asks a question keeps working during its turn. If it ends the turn with its own question unanswered,
the session ends and returns the ticket to To do with its progress intact; its glyph can proceed to another ticket
it has not attempted during this run. Questions do not change board selection or placement. Answers reach the
current ticket holder, including a successor to the asker, and remain available to later agents. Questions added or
reopened while the session runs are tracked on map changes, with each answer revision delivered once and permission
answers kept on their ACP response path. A session explicitly opened with Chat follows the originating question and receives
its answer while the person and agent discuss it. `start` reserves a ticket atomically before launching the runner,
which transfers the reservation to its ACP session; a failed launch releases the reservation.

## Modules relied on

None by import. A ticket's agent glyph comes from the map module's `work_read` through the base's `work_reads`; with the map module off the surface no ticket has a glyph and each is worked alone. The agent reaches Metaform through `mcp`'s server, `python -m metaform mcp serve` with the runner's own Python, and through the command line.

## Systems supported

Linux, macOS and Windows, QUAL-002. The start command's first word is found with `shutil.which`, so `npx` is `npx.cmd` on Windows. ACP goes over byte pipes, so no newline is translated. The agent starts in its own process group, `start_new_session` on Linux and macOS, `CREATE_NEW_PROCESS_GROUP` with `CREATE_NO_WINDOW` on Windows, and stopping ends the group, `killpg` or `taskkill /T /F`, because `npx` starts the agent as a grandchild. No text from a person or a ticket goes in an argument.

## Resources owned

The runner's log, `metaform-dispatch-<work id>.log` in the system's temporary folder, written by `start`; the agent's process group; the control socket on 127.0.0.1. All but the log are released when the session ends.

## Installed and direct wheel

The installed Metaform carries `agent-client-protocol` when the module is built into the wheel, BASE-015 and `build.py`. `start` runs the runner as `sys.executable -m metaform`, as the web module runs its server, so a directly run wheel whose package is not importable by its Python cannot start a runner.

## Demonstration

```
metaform enable dispatch
metaform map work open=true              # pick a ticket's work id
metaform dispatch start <work id> claude
metaform map messages                    # a permission request waits here
metaform map reply <message id> answer="Allow"
metaform dispatch message <work id> "also run the tests"   # audio=<clip> adds a spoken recording where the agent takes audio
metaform dispatch stop <work id>
```

Stored choices migrate once per home and once per map upgrade: command settings, default agents, option settings, roundtable seats, ticket agents and eligibility. Explicit Antigravity settings win collisions. A custom command keeps its value. The retired shipped command becomes the native launcher. Historical sessions retain their original identities. Google’s documented Antigravity `.gemini` paths remain intact.

## Informational delivery

Routine notes and project updates stay in records and the UI. They never prompt or resume an agent, join a user turn, or replay at startup. `dispatch notes` reads retained peer messages explicitly. The UI folds their bodies by default.

Current questions require current sender ownership. Child results require the recorded active caller or handoff successor. The runner rechecks queued requests before delivery. Small `peer_delivery` rows use the existing session/kind index for restart recovery. Older peer rows without delivery metadata remain readable history. User direction and stops retain priority. No schema migration or polling is added.
