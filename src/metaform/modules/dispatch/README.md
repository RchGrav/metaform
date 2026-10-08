# dispatch

Metaform starts an agent on a ticket through the Agent Client Protocol, BASE-052.

## Purpose

dispatch starts Claude Code, Codex or Gemini CLI on one ticket, one ACP session per ticket, in the project's folder with Metaform's MCP server. What the agent does shows as notes at the ticket's node, each permission it asks for is a question there, and a person can message it or stop it. Details: `metaform help dispatch`.

## Template version

The template changelog version this module started from: the Unreleased contract after 0.3.0.

## Declaration

- `SUPPORTED_OS = ('linux', 'macos', 'windows')`. Process handling is per system: see Systems supported.
- `DEPENDENCIES = ('agent-client-protocol>=0.12.1,<0.13',)`, the official ACP Python SDK, imported as `acp`. Its API has changed between minor versions before 1.0, so the minor version is pinned. The chassis gains no dependency.
- `SHIPS_DISABLED = True`. Enable it with `metaform enable dispatch`.
- `MODULE`: the verbs below, `work.requeued`, `dispatch.rework-limit` and raw `signal.raised` subscriptions, no `start`, `stop` or `status` hook.

## Common base used

- `metaform.module` for the declaration, `Context`, `Stop`, the verb context's `publish_async`, and `work_reads`, through which it reads a ticket's agent glyph as the map module shows it under `map`, BASE-035.
- `metaform.settings` for the three start commands.
- `metaform.data` for the work record (`ticket`, `take_work`), the permission prompts as questions (`ask`, `messages`), and the `dispatch` layer (`layer`, `add_item`, `edit`, `layer_items`).
- `metaform.events` through `ctx.publish_async('map.changed', ...)` after each write the runner makes, and `ctx.listen`, the base's listener for `map.changed` published in other processes, BASE-053.
- `metaform.nonce` to request the agent's nonce and an agent's hand-off nonce, read it in `handoff` through `nonce.reached()`, and close a session's nonce when the session ends.
- `metaform.prompt_files` to read its own `resources/prompts.xml`.
- `metaform.axiom` to check each prompt before it is sent, MCP-035 and BASE-057; a flagged prompt is sent unchanged with a notice line and `signal.raised`.

The runner also imports `acp`, the SDK, and nothing else outside the standard library.

## Work signals

`metaform dispatch signals [id=<work id>] [active=false]` reads BASE-057 signals. The same verb is available as
the MCP `dispatch` tool with `command=signals`. Ticket reads and the web GUI's sessions response include active signals. Reads do not
change ownership or recover work.

Signals are JSON records of kind `signal` in the existing dispatch `lines` table. This keeps storage compatible
with live runners. A source and signal key identify one active signal, so repeated evidence raises one event.
Activation publishes `signal.raised`, clearing publishes `signal.cleared`, and each also publishes `map.changed`
with the signal payload so other processes and open pages receive it through the existing relay.
Raw prompt signals from the workflow module are collected through the event bus too.
Crash recovery, reset and fallback session release clear permission signals after ending their session.

The settings are `dispatch_spin_calls` (40 unique tool calls without a completed step), `dispatch_spin_minutes`
(10 minutes), and `dispatch_repeat_failures` (3 consecutive failed calls with the same title, kind and input).
The defaults allow ordinary investigation and retries before asking the orchestrator to intervene. Settings can
be changed with `metaform set --dispatch-spin-calls`, `--dispatch-spin-minutes`, and `--dispatch-repeat-failures`.
Real ticket steps clear spinning signals and reset their counts. Prep sessions and idle chat time do not count.
Elapsed time is evaluated on the next incoming session or map event, with no timer or polling. A silent session
therefore raises its time signal when another event arrives. Permission waiting is reported separately and ends
when its request is answered or cancelled.

Session ends with unfinished work, requeues and incomplete prompts also raise signals. The separate rework
counter, owned by ticket `88d5a05958c04257baf716c0272500ae`, announces `dispatch.rework-limit` with `work_id`,
`attempts` and `limit`; dispatch records and publishes its signal. That counter is not implemented by this feature.
Detection takes no recovery action. Under D119, the orchestrator may stop a spinning or crashed agent, ask the
workflow agent to repair its execution instructions and restart it. Changes to the goal remain with the person.

## Prompts

`resources/prompts.xml`:

- `instructions`: `dispatch is active.`, listed under "modules available." in the instructions agents read.
- `nodes`: the line before the namespace nodes in what `metaform <nonce>` prints.
- `handed`: what `handoff id=<work id>` prints, the nonce to give the next agent.
- `handoff`: the one prompt the agent is sent. It tells the agent its ticket is taken for it, to read it with `metaform map work id=<id>` and work it, and how to plan, report each step and close it. `metaform <nonce>` serves the same text, then the `nodes` line and the nodes.
- `talk`, `system`, `prep`: the conversation agents the person summons from the page.

## Verbs

- `start <id> <agent>`, tool `dispatch` command `start`: starts `run` as a process detached from the terminal and returns at once with `state: starting`, the work id, the agent, the runner's pid and its log file. It refuses a ticket that is done or taken, a ticket whose agent glyph's agent is at work on another ticket, VIEW-040, and a start command not found on this system.
- `run <id> <agent>`, CLI only: the ACP session for one ticket in this process, until it ends. A person may run it in a terminal to watch it. On a ticket with an agent glyph, VIEW-040, once the ticket is done it runs a session for the glyph's next ticket not done and not taken, in board order, To do before Backlog, each by its place, and so on until the glyph has none waiting or a session ends with its ticket open; its result then adds `glyph` and `worked`, the work ids in the order worked. It refuses what `start` refuses.
- `message <id> <text>...`: accepts the text for the running agent as `session/prompt`; returns `sent: true`. During a turn, messages and question answers wait in arrival order until the turn ends. One prompt runs at a time. Stop discards the waiting prompts.
- `stop <id>`: sends `session/cancel`, answers every waiting permission request as cancelled, closes the agent's input and ends its process group; returns `stopped: true`.
- `handoff`: run through a nonce, `metaform <nonce>`, the hand-off prompt followed by the namespace nodes of the work, the where read of the ticket's node and of each node it links. Run as `handoff id=<work id>`, it makes a new nonce for that ticket and prints `metaform <nonce>` for the agent the work is handed to; it takes nothing. A nonce made this way is not closed by the module.
- `raise <node> -- <text>`: the person raises an issue on a node; a held ticket holds the report and an agent starts on it in the chat with the workflow module's `sentinel` skill as its first turn, served whole with the report bound as its input, VIEW-045.
- `autostart`, when enabled, starts the free glyphs in board order over the tickets that have not been tried: open, not taken, not held, with a task. A ticket an agent stopped on stays taken until the person puts it back; nothing restarts by itself. Without distributed glyphs it fills the configured agent slots.
- `recover` applies the dead runner recovery setting and reports tickets released or deferred with their reasons. Autostart applies it before selecting tickets, including when automatic agent starts are off. Session reads preserve ownership.

`message` and `stop` with no agent running on the ticket name `metaform dispatch start <id> <agent>` as the next step.

Eligible agents is a map-owned ticket setting, MAP-058. Explicit `start` and `run` refuse an agent outside the list. A glyph's runner selects its next eligible ticket in board order and leaves skipped tickets' glyphs and positions intact. Autostart and Chat use the configured agent when eligible, otherwise the first listed agent. Tickets with no list allow Any agent.

## Settings

- `dispatch_claude`, default `npx -y @agentclientprotocol/claude-agent-acp`.
- `dispatch_codex`, default `npx -y @agentclientprotocol/codex-acp`.
- `dispatch_gemini`, default `gemini --acp`.
- `dispatch_autostart`, false by default, labeled Autostart agents; separate from the web GUI autostart setting.
- `dispatch_agent`, codex by default, the agent for automatic starts.
- `dispatch_agents`, 5 by default, the number of simultaneous agents when tickets have not been distributed.
- `dispatch_recovery`, `manual` by default. `automatic` verifies runner death and cleans up its abandoned agent before returning its ticket to To do. Set it with `metaform set --dispatch-recovery=automatic`, or restore manual recovery with `metaform set --dispatch-recovery=manual`.

`start` and `run` read the one for the agent named. Each command runs the person's own installed agent under the person's own login, with the person's environment passed through unchanged. Metaform never reads, stores or sends credentials, and never answers an agent's authentication; an agent that needs a login says so in the failure note, and the person logs in with the agent itself.

## Events

- Publishes `map.changed` after each write the runner makes, since those writes are made inside one long command and would otherwise be announced only when it ends.
- The runner listens for `map.changed` through the base, `ctx.listen`, BASE-053: each one published in another process, a command, the MCP server, the web server or another runner, for the runner's project, makes it read the questions it asked and those its agent asked itself. This is how an answer given from the web GUI, the CLI or MCP reaches the agent without polling, QUAL-015. The runner's own writes do not reach its listener. The control port takes only `message` and `stop`.

## Sync and async

`run` is a coroutine, as are the runner's ACP handlers. `start`, `message`, `stop` and `handoff` are plain functions, and the listener hands each change to the runner's loop with `call_soon_threadsafe`. The runner makes each store call in a worker thread, so its loop is never held by a write.

## Layers

`dispatch`, kind `layer`, mutable, hideable, made ready on the first run so it is seen in context. At the ticket's node it holds:

- one session record per run, its value a sentence of the agent, the session id and its state, its `extra` holding `dispatch: session`, the work id, agent, session id, nonce, the runner's pid, its control port and token, and `state` running or ended, with how it ended;
- notes, `extra` `dispatch: note` with the work id, agent, session id and the update's kind. A tool call is one note, changed in place as its status changes. Each run of the agent's message or thought text is one note. The plan and each other kind of update is one note, kept at its latest. Each turn's end is one note.

The steps on the ticket stay the agent's own, MAP-053. The session id is also on the work record, in `taken_by`, as `<agent> <session id>`, because a work record has no `extra`.

## Lifecycle and cleanup

No `start` or `stop` hook. A runner owns one agent process group, one loopback listening socket and its tasks. The session ends when a prompt turn ends with the ticket done, when `stop` is run, when the agent's process ends, or on Ctrl+C in a foreground `run`. Ending closes the nonce, ends the agent's process group and marks the session record ended.

Session reads, including MCP, CLI, the ticket's `work_read` and the workbench, verify stored running rows against the ticket, the recorded pid and the runner's authenticated `status` reply. The reply checks the ACP adapter as well as the runner. A completed ticket, a pid whose command line is not `dispatch run <work id>`, a refused control connection or a reply for another session reads as ended. A runner on a glyph goes on to the glyph's next ticket in the same process, so its command line names the work id it started on; its own reply shows it runs the later ticket. A timeout or an older runner without status reads as running only when its pid runs that work id. Reads keep the stored row and transcript intact. An idle adapter on an open ticket remains running and can receive another message.

Public session reads also report `activity`, separately from lifecycle: `working` for an executing prompt turn,
`waiting` for a permission request or an idle turn with its own unanswered questions, and `idle` for no executing
turn or wait. The runner reports these from its turn and wait tracking, never from a PID. An older runner retains
its lifecycle uncertainty; one unambiguous latest `end_turn` supports `idle`, while later output, tied latest
records or incomplete telemetry yield `unknown`. Reads persist no guesses. Turn and permission transitions
announce a dispatch refresh; idle and waiting sessions keep their tickets, questions and message controls.

A failed background callback wakes the runner into shutdown. Cleanup still closes the agent, nonce, listener and control server when a database schema change prevents a final transcript or session write. If the runner cannot release its ticket and mark the session ended, it retries in a fresh process using the code on disk. If that also fails, the runner log names the session and ticket and gives the command to return the ticket to To do. The schema compatibility check remains in force.

On Linux and macOS, SIGTERM ends the session and takes no next ticket. Cleanup waits for an in-flight startup acquisition so an adapter, nonce or ticket cannot arrive after cleanup finishes. A forced kill, including process termination on Windows, cannot run cleanup. The default manual policy preserves its ticket's ownership until the person or orchestrator returns it, MAP-049. With automatic recovery selected, `dispatch recover` or the existing Autostart change events verify process birth identities and exact session ownership, end the abandoned agent group, close the nonce and return work to To do with its progress intact. No timer polls for death. Birth identities and resource ownership are kept privately in the existing handoff nonce, so enabling recovery adds no database schema upgrade beneath older runners. Ticket ownership and the initial session row commit together, so a forced kill cannot leave an acquired ticket without its recovery record. Slow process cleanup holds no project write lock, and a final atomic ownership check preserves reassignment during cleanup. Legacy sessions, unreadable processes, changed ownership, reused adapter PIDs and unverified surviving groups require manual attention. Live agent group cleanup requires Linux 6.9 or later with pidfd process-group signalling, which binds the signal to the verified process even if its numeric PID is reused. On macOS, Windows or kernels without this capability, recovery defers live agent cleanup to a person instead of signalling a recyclable PID. Python builds without pidfd APIs use the equivalent libc syscalls on 64-bit x86-64 and arm64 Linux; other unsupported builds report manual cleanup. An already empty verified POSIX group needs no signal. A deferred recovery reports its reason and the manual return command. Reads remain observational regardless of policy.

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
metaform dispatch message <work id> "also run the tests"
metaform dispatch stop <work id>
```
