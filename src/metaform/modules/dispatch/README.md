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
- `MODULE`: the verbs below, one `map.changed` subscription, no `start`, `stop` or `status` hook.

## Common base used

- `metaform.module` for the declaration, `Context`, `Stop` and the verb context's `publish_async`.
- `metaform.settings` for the three start commands.
- `metaform.data` for the work record (`ticket`, `take_work`), the questions (`ask`, `messages`), and the `dispatch` layer (`layer`, `add_item`, `edit`, `layer_items`).
- `metaform.events` through `ctx.publish_async('map.changed', ...)` after each write the runner makes, and the module's own subscription.
- `metaform.nonce` to request the agent's nonce and an agent's hand-off nonce, read it in `handoff` through `nonce.reached()`, and close a session's nonce when the session ends.

The runner also imports `acp`, the SDK, and nothing else outside the standard library. The module reads its own `resources/prompts.xml` with the standard library, because the prompt reader is not part of the public base.

## Prompts

`resources/prompts.xml`:

- `instructions`: `dispatch is active.`, listed under "modules available." in the instructions agents read.
- `nodes`: the line before the namespace nodes in what `metaform <nonce>` prints.
- `handed`: what `handoff id=<work id>` prints, the nonce to give the next agent.
- `handoff`: the one prompt the agent is sent. It tells the agent its ticket is taken for it, to read it with `metaform map work id=<id>` and work it, and how to plan, report each step and close it. `metaform <nonce>` serves the same text, then the `nodes` line and the nodes.

## Verbs

- `start <id> <agent>`, tool `dispatch` command `start`: starts `run` as a process detached from the terminal and returns at once with `state: starting`, the work id, the agent, the runner's pid and its log file. It refuses a ticket that is done or taken, and a start command not found on this system.
- `run <id> <agent>`, CLI only: the ACP session for one ticket in this process, until it ends. A person may run it in a terminal to watch it.
- `message <id> <text>...`: sends the text to the running agent as `session/prompt`; returns `sent: true`.
- `stop <id>`: sends `session/cancel`, answers every waiting permission request as cancelled, closes the agent's input and ends its process group; returns `stopped: true`.
- `handoff`: run through a nonce, `metaform <nonce>`, the hand-off prompt followed by the namespace nodes of the work, the where read of the ticket's node and of each node it links. Run as `handoff id=<work id>`, it makes a new nonce for that ticket and prints `metaform <nonce>` for the agent the work is handed to; it takes nothing. A nonce made this way is not closed by the module.

`message` and `stop` with no agent running on the ticket name `metaform dispatch start <id> <agent>` as the next step.

## Settings

- `dispatch_claude`, default `npx -y @agentclientprotocol/claude-agent-acp`.
- `dispatch_codex`, default `npx -y @agentclientprotocol/codex-acp`.
- `dispatch_gemini`, default `gemini --acp`.

`start` and `run` read the one for the agent named. Each command runs the person's own installed agent under the person's own login, with the person's environment passed through unchanged. Metaform never reads, stores or sends credentials, and never answers an agent's authentication; an agent that needs a login says so in the failure note, and the person logs in with the agent itself.

## Events

- Publishes `map.changed` after each write the runner makes, since those writes are made inside one long command and would otherwise be announced only when it ends.
- Subscribes to `map.changed`. The subscriber runs in whichever process changed the map: a command, the MCP server or the web server. It finds the project's running sessions on the `dispatch` layer and sends each runner `changed` over its loopback control port, and the runner reads the questions it asked. This is how an answer given from the web GUI, the CLI or MCP reaches the agent without polling, QUAL-015. In a runner process the subscriber does nothing.

## Sync and async

`run` is a coroutine, as are the runner's ACP handlers. `start`, `message`, `stop`, `handoff` and the subscriber are plain functions. The runner makes each store call in a worker thread, so its loop is never held by a write.

## Layers

`dispatch`, kind `layer`, mutable, hideable, made ready on the first run so it is seen in context. At the ticket's node it holds:

- one session record per run, its value a sentence of the agent, the session id and its state, its `extra` holding `dispatch: session`, the work id, agent, session id, nonce, the runner's pid, its control port and token, and `state` running or ended, with how it ended;
- notes, `extra` `dispatch: note` with the work id, agent, session id and the update's kind. A tool call is one note, changed in place as its status changes. Each run of the agent's message or thought text is one note. The plan and each other kind of update is one note, kept at its latest. Each turn's end is one note.

The steps on the ticket stay the agent's own, MAP-053. The session id is also on the work record, in `taken_by`, as `<agent> <session id>`, because a work record has no `extra`.

## Lifecycle and cleanup

No `start` or `stop` hook. A runner owns one agent process group, one loopback listening socket and its tasks. The session ends when a prompt turn ends with the ticket done, when `stop` is run, when the agent's process ends, or on Ctrl+C in a foreground `run`. Ending closes the nonce, ends the agent's process group and marks the session record ended.

## Modules relied on

None by import. The agent reaches Metaform through `mcp`'s server, `python -m metaform mcp serve` with the runner's own Python, and through the command line.

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
