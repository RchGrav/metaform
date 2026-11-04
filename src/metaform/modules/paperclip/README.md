# paperclip

Metaform and a [Paperclip](https://github.com/paperclipai/paperclip) server working the same tickets. The design, the sources and what is still to build are in `artifacts/swarm-2026-10-11/PAPERCLIP-INTEGRATION.md`.

## Purpose

Paperclip runs agents in heartbeats against issues, with an org chart, budgets and approvals. This module ties each Paperclip issue it knows to a ticket at an Address, so an agent Paperclip runs reads the brief of the node its issue works on, Metaform's tickets can be sent to Paperclip's agents, and an agent Paperclip runs with its process adapter hands its issues to dispatch, with comments on the issue and messages at the Address crossing between the two. It uses Paperclip's REST API, its issue documents and comments, its issue monitors and its process adapter, and nothing of its own on Paperclip's side.

## Template version

The template changelog version this module started from: 0.2.0.

## Declaration

`SUPPORTED_OS` is all three systems: the module makes HTTP calls with the standard library. `DEPENDENCIES` is `websockets`, for the one stream it follows, Paperclip's live events. `SHIPS_DISABLED` is True, since it needs a Paperclip server most projects do not run. `REMOTE_AGENT` is False: it reaches a Paperclip server on the person's own machine or network. `MODULE` declares the verbs below, the `links` and `bridged` tables, a `status` line and a `work_read` hook.

### Toolbar items and panes

None. The person works Paperclip in Paperclip's own board; tickets tied to issues show the issue in `map work id=<id>`.

## Common base used

`metaform.settings` declares the eight settings and reads `dispatch_autostart`. `metaform.data` gives `Node`, `Store`, `WorkRecord`, `now`, the table declarations and `status`, the one status vocabulary Paperclip's issue states are mapped to; tickets and messages are written and read with map's operations, `store.add_work`, `store.take_work`, `store.move_work`, `store.finish_work`, `store.ticket`, `store.tell`, `store.messages`, `store.graph` and `store.numbers_of`. `metaform.jev` chooses an issue's Address (`pick_one`) when the person has turned Jev on; nothing chooses a ticket's Paperclip agent for the person. `metaform.prompt_files` reads this module's prompts. `metaform.module` gives `node_brief`, `first_line` and `Stop`, and `surface`, `tool_arguments`, `context` and `call`, with which the module runs other modules' declared verbs as the command line runs them, as the mcp module's A2A does: dispatch's `sessions`, `stop`, `cancel` and `autostart`, and map's `reply`.

## Prompts

`resources/prompts.xml` holds the template's four elements, `connect` and `rules` empty for the person to write, and the prose this module sends: `taken`, the comment `heartbeat` posts on an issue it takes, with `taken_state`, whether dispatch starts it or it waits for the person; `unrouted`, the one comment on an assigned issue it cannot place; `ended`, the comment `sync` posts when the ticket ends; `failed`, the question card on a failed ticket's issue; `comment`, the title of each comment written as a message at the Address; and `jev_route`, what Jev is asked when an issue names no Address. A question sent to Paperclip is the question as written at the Address, with its suggestions as the choices, so it has no prompt of its own. The issue document it keeps is data, not prose.

## Verbs

All return JSON-ready data, except `brief`, which returns the brief's text.

- `metaform paperclip status`, `paperclip_status`: the server and company used, `GET /api/health`, who the token speaks for, `GET /api/agents/me`, and `agent_config`, the process-adapter configuration to paste into a Paperclip agent: `command` the absolute path of `metaform` (or of Python with `-m metaform`), `args` `["paperclip", "heartbeat"]`, `cwd` this folder. Paperclip spawns without a shell and looks `command` up as one file, so the command and its arguments are apart. `read`, `open_world`.
- `metaform paperclip brief [issue=<id>]`, `paperclip_brief`: the brief of the Address an issue works on. An explicit `issue=` wins, then the gateway's `x-paperclip-issue-id` in `ctx.identity`, then `PAPERCLIP_TASK_ID` from a local agent run. This lets calls through a shared HTTP gateway resolve their own issue while retaining the command line and stdio fallback. The Address is the link's, else the `address:` line of the issue's `metaform` document. `read`, `open_world`.
- `metaform paperclip links`, `paperclip_links`: the issues tied to tickets here. `read`.
- `metaform paperclip link <issue> <address>`: ties an issue a Paperclip agent works to an Address: a ticket there, taken by the issue so dispatch never starts an agent on it too, and the issue's `metaform` document. Command line only. `write`, `open_world`.
- `metaform paperclip send <id> [assignee=<agent>]`, `paperclip_send`: sends an open ticket nobody holds to Paperclip as an issue, with an idempotency key so a second send replays the first issue. The ticket is taken for Paperclip before the issue is made, so dispatch's autostart cannot take it meanwhile, and given back to its column when the issue cannot be made. The assignee is named by id or short name, resolved to its id as Paperclip's create requires; with none named or set, Jev chooses among the company's agents when it is on (`choose_agent`, kept at the ticket's Address), else the issue goes to Paperclip's backlog. A repeat send repairs a missing issue document. Each send, new or repeat, starts the project's watcher, detached, when none runs. Its `next` says how the ticket follows the issue: the watcher's process when one runs here, else `sync`, `watch` and `web start`. `write`, `open_world`.
- `metaform paperclip sync`: for each link, an issue closed in Paperclip closes its ticket, done as completed and cancelled as cancelled, an issue done resolved with its assignee's last comment, cut to 2,000 characters, else `<PAP-n> is done in Paperclip.`, and ends the dispatch session on it through dispatch's own verbs: `cancel` for a cancelled issue, `stop` first for a done one. For an issue a Paperclip agent works, each new comment on it, but Paperclip's own notices and this module's comments, becomes a message at the Address while its ticket is open, so what that agent found is kept at the RE. For an issue a Metaform agent works, what was said crosses first: each new comment on it, but Paperclip's own notices and this module's comments, becomes a message at the Address; each open question at the Address that belongs to this ticket, a dispatched agent's permission request or a question asked with the ticket named, goes out once as a question card only a person may answer (`ask_user_questions`, `human_only`, `wake_assignee`), and its answer comes back through `map reply`, kept beside the question; a card whose question was answered here first is withdrawn. Then a ticket a Metaform agent ended, or a ticket the person cancelled on an issue a Paperclip agent works, is reported once on its issue with its resolution: `done`, `cancelled`, or for a failed ticket `in_review` with a card asking whether to try again (the issue goes to `todo` and the next heartbeat takes it as a new ticket) or close it (`cancelled`). While the ticket is open the issue's monitor is set again when it has fired. A link that fails is listed under `failed`. Command line only. `write`, `open_world`.
- `metaform paperclip watch`: follows every link until stopped (Ctrl-C or SIGTERM), so tickets follow their issues with no one running `sync`, and ends by itself after a sync that leaves no link to follow, or once paperclip is disabled here. It syncs every link at its start and each time Paperclip's live events stream (`/api/companies/<company>/events/ws`, the WebSocket Paperclip's own pages follow) opens again, since what happened while it was closed was never heard; between those it syncs one link when an `activity.logged` event names that link's issue, or when a `map.changed` from another process names its ticket, or, naming no ticket, wrote tickets or messages. Every other event is dropped unread, and a burst costs one sync. A dropped stream reconnects after 1 s, doubling to 60 s. Nothing syncs on a timer, but for a server that answers the stream 404, which cannot push: then it syncs every `paperclip_check_minutes`, from the stream's own thread. `send` starts it, and so does `web start` from any folder, detached, when issues a Paperclip agent works are open and none runs. Each line it says reaches its log as it is said. Its process is in `run/paperclip/<project>.json` in the Metaform home, its log beside it, and it holds `run/paperclip/<project>.lock` locked while it runs: a lock no process holds is a watcher gone, a crash included. Command line only. `write`, `open_world`.
  Change, 2026-10-15, dispatched ticket 2ede3067 (code.system.management.knowledge#32), the no-polling rule: before, it synced every `paperclip_check_minutes` and wrote a beat every 20 seconds that others read as alive for a minute. Why: a watcher runs for days beside the work; a timer costs CPU and requests all that time to learn mostly nothing, and a beat says a crashed watcher lives for up to a minute.
- `metaform paperclip heartbeat`: one heartbeat of a Paperclip agent whose adapter is `process` running this command. It syncs, then reads the agent's assignments from `GET /api/agents/me/inbox-lite` (the company's issue list for a board caller) and checks out each `todo` or `in_progress` issue whose `metaform` document names an Address, or whose Address Jev chooses (`paperclip_jev_route`), writes a ticket there in To do, posts the `taken` comment, sets an `external_service` monitor so Paperclip wakes the agent every `paperclip_check_minutes` rather than reading the run as stuck (one attempt, timing out one interval later), and writes the issue's earlier comments at the Address. With `dispatch_autostart` on it then runs dispatch's `autostart`, which starts the waiting tickets as the web server would, and needs no web server. An issue it cannot place gets one `unrouted` comment and is listed in the result. Command line only. `write`, `open_world`.

`link`, `sync`, `watch` and `heartbeat` are on the command line only: tying issues, and running Paperclip's process agent, are the person's setup. `send` hands work to an orchestrator that spends from its own budgets; map's own ticket writes are open to agents.

## Settings

They say where Metaform calls out to and which agents it hands work to.

- `paperclip_url`, `http://localhost:3100`: the server. `PAPERCLIP_API_URL` wins during a heartbeat.
- `paperclip_token_env`, `PAPERCLIP_API_KEY`: the environment variable holding the bearer token. The token is never stored.
- `paperclip_company`, empty: the company id. `PAPERCLIP_COMPANY_ID` wins during a heartbeat.
- `paperclip_assignee`, empty: the agent `send` assigns to, by id or short name; empty sends the issue to Paperclip's backlog unassigned. A switch of `send`.
- `paperclip_project`, empty: the project `send` files issues under. A switch of `send`.
- `paperclip_check_minutes`, 10: how often Paperclip wakes the Metaform agent to check an issue a Metaform agent works, through the issue's monitor; and how often `watch` syncs, only for a server with no live events stream.
- Jev chooses the Address of an issue that names none while `jev` is on and `jev_decisions` includes `paperclip.route`, which an empty list does. The setting `paperclip_jev_route` folded into that decision point in the settings cleanup of 2026-10-15; where it was off, paperclip's start carries it once into a `jev_decisions` that leaves `paperclip.route` out.

## Events

Subscribes to `web.started`: for each registered project with paperclip on, issues a Paperclip agent works open and no watcher running, it starts `metaform paperclip watch` detached in that project's folder, as twilio starts its bridge; the web GUI serves every project, so where it was started does not matter. Publishes none.

## Sync and async

All verbs are plain functions; each Paperclip call waits at most 30 seconds.

## Layers

No layers. Two tables, `place='metaform'`, version 2, readable from version 1. `links`, keyed by `issue_id`, with indexes on `work_id` and `identifier`: the issue's id, identifier and company, the ticket's work id and Address, `works` (`paperclip` or `metaform`, the side doing the work), the issue's last seen `state`, the outcome `reported` on it, when it was `synced` and `linked`, and `comments_seen`, the last comment read. `bridged`, keyed by `issue_id` and `comment_id`, with an index on `message_id`: each comment, question and card that crossed, and which way (`in` a comment written as a message; `note` this module's own comment, or `unrouted`; `ask` a question sent as a card; `failed` a failed ticket's card; `done` a card answered, withdrawn or closed), so none crosses twice or back. Beside the work records, so a clear of the metaform drops them with their tickets. Every verb but `status` and `brief` reads them; `link`, `send`, `sync` and `heartbeat` write them.

## Lifecycle and cleanup

No `start` or `stop`, no tasks. The watcher `send` or `web start` starts runs until it is stopped or nothing is left to follow; it removes its record as it ends. Disabling the module leaves the table and the tickets.

## Modules relied on

map, for tickets, messages, replies and briefs. dispatch, when it is on: `heartbeat` runs its `autostart` for the tickets it took while `dispatch_autostart` is on, and `sync` ends a session through its `cancel` and `stop`. A dispatched agent carries none of the run's `PAPERCLIP_*` variables, which `harness.IDENTITY` strips from every process Metaform starts.

## Systems supported

Linux, macOS and Windows.

## Resources owned

None held between calls. Each call opens and closes its own HTTP connection.

## Installed and direct wheel

The same in both: standard library only.

## Demonstration

```
metaform enable paperclip
metaform set --paperclip-url http://localhost:3100 --paperclip-company <company id>
export PAPERCLIP_API_KEY=<agent or board key>   # none for a local_trusted server
metaform paperclip status
metaform paperclip link PAP-12 code.alarm.audible
metaform paperclip brief issue=PAP-12
metaform paperclip send <work id> assignee=<paperclip agent>
metaform paperclip sync
```

In Paperclip, an agent with `adapterType` `process` and the `adapterConfig` that `metaform paperclip status` prints as `agent_config` hands each issue assigned to it, whose `metaform` document reads `address: <address>`, to dispatch.
