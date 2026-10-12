# mcp

Serves Metaform's tools to AI tools over MCP.

## Purpose

The mcp module starts the Model Context Protocol server a host launches with `uvx --from <source> metaform mcp serve`, or that a person starts once with `metaform mcp serve --http` for every AI tool to reach over Streamable HTTP. Every command is its own tool: each surfaced module verb is `<module>_<verb>`, such as `map_where` or `intake_start`, and the chassis's own commands are `metaform_<command>`. A tool is described once, where it is listed: the verb's summary, and its caution when it has one; its input schema typed and described from the verb's declaration; and its annotations from the effect the verb declares, MCP-003. Module instructions, the stored prompts, the reports and what a module declares are served as resources, MCP-037. It ships enabled.

## Template version

Started from template 0.2.0.

## Declaration

`SUPPORTED_OS = ('linux', 'macos', 'windows')`, `DEPENDENCIES = ('mcp>=2.2',)`, `SHIPS_DISABLED = False`. `MODULE` declares one verb, `serve`, for the CLI only, and a transport, so it runs whatever the folder's command surface.

## Common base used

`metaform.module` for the declaration, `Context`, the module registry, the command surface, the composed instructions, the per-call context, the argument checks and the report functions; `metaform.settings` for tool switch schemas and the `set` tool.

## Prompts

`resources/prompts.xml` holds the connect message's `instructions` and `instructions_end`, the `glossary` served at `metaform://glossary`, the `tool_index` heading and the `rules_heading` of the block that follow it there, MCP-031; the forms the person is shown, `consent_caution`, `consent_go` and `consent_settings`, and `consent_declined`, what the agent is told when the person says no; `view_selected`, the line a view tells the agent about the node the person selected, `view_unbuilt`, and `view_read`, the one text line of a view's read; `view_show` and `view_state`, the descriptions of a view's own tools, and `view_shown` and `view_absent`, what `view_show` answers; and `task_working`, a task's status while its tool runs.

## Verbs

`serve`: runs the server over stdio until the host closes it, or with `--http` over Streamable HTTP at `http://127.0.0.1:<mcp_port>/mcp` until it is stopped. It is never itself a tool. Beside the module tools it always serves the chassis tools `metaform_set`, `metaform_feedback`, `metaform_list_reports`, `metaform_read_report`, `metaform_instructions` and `metaform_register`, which narrowing never hides, and while the chassis is on the folder's command surface, `metaform_add_origin`, `metaform_list_origins`, `metaform_add_variant`, `metaform_list_variants`, `metaform_extract`, `metaform_prompts`, `metaform_prompt`, `metaform_save_prompt` and `metaform_clear_project`, the history, prompt and clear commands as tools. `metaform_clear_project` removes the project's bases and reports, as `metaform clear project` does; a backup is made first, and `metaform restore project` brings it back. It is `destructiveHint` true, and like any tool with a caution it runs only with the person's yes: given in a form their AI tool shows, or as `confirm=true` where no form can be shown; without it, it says what it would remove.

Consent, CLI-011 and MCP-006: a call with a caution, and an agent asking to change a setting only the person sets, are put to the person where their AI tool shows forms (MCP elicitation) and `mcp_consent` is `ask`, the default. On the 2026-07-28 wire the call answers `input_required` with the form, and the client calls again with the person's answer and the state it was given, which the SDK seals and binds to the call and its arguments; each answer counts once. On the 2025 handshake the server sends `elicitation/create` while the call waits. The form carries the caution with one box to tick, and each setting as a field with its choices, the agent's value filled in and its help as the reason it is the person's. A dispatched agent's calls are never put to a form. Where none can be shown, `confirm=true` and the refusal of a person-only setting stand.

Tasks, BASE-030: a verb declared `task=True`, such as `hello_wait`, called by a client that declares `io.modelcontextprotocol/tasks` on the request, is answered at once with a task while the verb runs on in the server, its status in the vocabulary of `metaform.data.status`. The task is written to the project's `tool_tasks` table before the call is answered, and kept for a day, its `ttlMs`; the server marks the tasks it runs alive every ten seconds, so a client polling after that server stopped, a relay's replacement or an HTTP restart, is told the task failed rather than that it does not exist. `tasks/get` gives its status and, once it is done, the tool's result. `tasks/cancel`, from any server of the project, asks the verb to stop, as the extension's cooperative cancellation has it: the task reads cancelled once the verb has stopped, which an `async` verb does at its next `await`, and completed with its result when the verb finished first, as a verb run in a thread always does, so a task never reads cancelled while its effect still lands. A verb declared `task='run'` returns a workflow run the server itself advances to its end, and answers with that run as the task, by its run id: `tasks/get` maps the run's status through `metaform.data.status`, a run paused on the person asks its question as a form under a key of that one pause, `tasks/update` takes the person's answer through the workflow module's `answer`, and `tasks/cancel` cancels the run through its `cancel`. No shipped verb declares it yet: a task is only for work the server advances by itself, since a host gives the model a task's result only once it ends, so `workflow_assign`, whose run id the calling agent must act on, answers as any tool does. A folder that is no project's answers without a task. A client that does not declare the extension gets no task, and `tasks/*` answer it -32021.

MCP Apps, `io.modelcontextprotocol/ui`, stable revision 2026-01-26, with the draft's App-Provided Tools and listing-level `_meta.ui`: to a client that declares it, or to every client with `mcp_apps_offer` always, each view-opening tool carries `_meta.ui.resourceUri`: `map_where` and `map_roots` open `ui://metaform/map`, the web GUI's 2D and 3D map run in the AI tool's frame and focused on the address; `map_item` and `map_node` open `ui://metaform/node`, the node with what relies on it, what it relies on and its numbered items (#n, title, why), each opened in place; `dispatch_sessions` and `dispatch_start` open `ui://metaform/trace`, a ticket's agent sessions and their threads, read again every two seconds while the view is on screen (an `unchanged` answer when nothing moved, since the agent's lines grow in place); `metaform_instructions` and `map_glossary` open `ui://metaform/glossary`, the call's own answer, then the terms of `metaform://glossary` as written, the tools and the rules, searchable. The views are listed in `resources/list` with their `_meta.ui`, which their read carries too, with a cache hint: no origin in their content policy, since every byte they run is in the document and every read goes through the host; `clipboardWrite`, to copy an Address; a border for all but the map. The address templates point at the node view. All the views speak to their host through the official MCP Apps SDK, `@modelcontextprotocol/ext-apps` 2.0.3, kept in `resources/views/ext-apps.js` with its license, under `bridge.js`: the SDK makes the handshake, reports the view's size, and carries the calls; `bridge.js` waits for the handshake before a read, takes the host's theme, style variables, fonts, container size, safe area and display modes (inline and full screen, and for the trace, floating, `pip`), opens the web GUI where the host opens links, and stops what it runs when the host tears the view down. The views read through `metaform_view`, listed only to such a client with `visibility: ["app"]`, so its model never sees it; its data goes once, as structured content, with one line of text. The picture is shared both ways. Selecting a node tells the agent in one line which Address the person is looking at (`ui/update-model-context`, from `view_selected`, with the Address as structured content). An Address the agent names in a later Metaform call, its `address`, `item`, `node` (`element:` taken off), `element` or `receiver`, is kept per client and read by the open views through `metaform_view`'s `focus`, and each turns to it once, quietly; and a view offers its host two tools of its own, `metaform_view_show` and `metaform_view_state`, which a host that calls a view's tools lists to its agent while the view is open. Every result keeps its full text, which is all an AI tool without MCP Apps, such as Claude Code, receives. The map view is the page's files built into one document by `scripts/build_map_view.mjs` (`npm --prefix scripts ci` first), with `resources/views/map.js` after the page's frame code for turning and the full-screen and web GUI buttons; the wheel and sdist build runs it, `scripts/hatch_views.py`, and CI runs it before the tests; it records the files it was made of and their SHA-256, and where it is missing or older than the page, the server says so on stderr and the node view stands in.

The tool list is sorted by name and the same on every connection to a folder; it changes only when a module is enabled, disabled or narrowed off the surface, and the change is announced with `notifications/tools/list_changed`, on a `subscriptions/listen` stream for a 2026-07-28 client, MCP-004. On the 2026-07-28 wire the lists carry `ttlMs` 60000 and `cacheScope` private. Each tool's annotations are set explicitly from the verb's `effect` and `open_world`, BASE-006: `readOnlyHint` and `idempotentHint` for `read`, `destructiveHint` for `remove`, `openWorldHint` for a verb that starts or steers agents or reaches the network. A result that is a JSON object is also given as `structuredContent`; no tool declares an `outputSchema`, since no verb declares the shape of its result.

Beyond this machine, `oauth.py`: a server with `mcp_public_url` set, or `mcp_bind` anything but loopback, is a Metaform Node's and starts only when the Node's authorization server is running (its introspection credential is in `<home>/run/node-introspection`); otherwise it stops with the next step, so nothing is served anonymously. Exposed, it is an OAuth 2.1 resource server built from the MCP SDK's own pieces: every request to `/mcp` needs a bearer token whose audience is exactly `<public url>/mcp` (RFC 8707), checked by introspection (RFC 7662) at the Node's authorization server; a request without one is answered 401 with `WWW-Authenticate: Bearer resource_metadata=...`, and the Protected Resource Metadata (RFC 9728) at `/.well-known/oauth-protected-resource/mcp` names the Node as the authorization server and offers `mcp:read` and `mcp:write`. A tool call short of its tool's scope (`mcp:read` for a read, `mcp:write` for a write or removal, `mcp:dispatch` for a dispatch tool or one that starts agents) is answered 403 `insufficient_scope` naming the scope, the July specification's step-up challenge. Host and Origin are checked against the public name. A2A on the same port then takes only tokens for `<public url>/a2a` with `a2a:tickets`, its Agent Card names the public URLs and an OAuth 2.0 authorization-code scheme at the Node, and no static A2A token is made. The views' `focus` is kept per signed-in account, so two people using one AI tool never turn each other's views. See the node module and docs/guides/metaform-node.md.

An alias, CLI-039, adds no tool: every command of its modules is already a tool of its own.

Every call's arguments are read as the command line reads them. A missing required noun is an error with the command line's next step. A text noun or a text setting sent another JSON value, such as `purpose: 12`, reaches the verb as that value's JSON text, with the notice `<name> is text; what was sent was kept as its JSON text.`; a whole-number or true-or-false noun or setting sent another kind cannot be read as that kind and is an error, as on the command line. An argument the tool does not know is kept in the record's `extra` when the verb takes one, otherwise ignored, and named in a notice either way. The chassis tools other than `set` read their arguments by their declared JSON types the same way: a text argument sent another type is kept as its JSON text with the notice, and a whole number, true or false, or a list sent another type stops the call, as does an argument the tool does not declare.

## Settings

The module declares `mcp_server='serve'`. The chassis installer and provisioning help derive the launch command
from that declaration. With no enabled server provider, setup copies skills and supported instruction pointers
and reminders and skips MCP registration and proof. The chassis global setting `install_server` defaults to empty,
selecting the sole eligible provider automatically. If several modules declare a server, set it to the chosen
module id with `metaform set --install-server <id>`.

`mcp_http`, switch `--http`, serves one run over Streamable HTTP on 127.0.0.1 instead of stdio. It is meant for the
command line: stored, every `metaform mcp serve` in its scope serves HTTP, those AI tools and dispatch start over
stdio included. The SDK checks each request's Host and Origin against 127.0.0.1 and localhost, so a web page cannot
reach the server through DNS rebinding. Over HTTP there is no relay; a client reconnects.

`mcp_port`, global, 7434 by default, switch `--mcp-port` or `--port`, is the port it listens on.

`mcp_transport`, global, `stdio` by default or `http`, is how `metaform install` registers the server. stdio
registers the `uvx` command, so each AI tool starts its own server in the folder it opens. http registers
`http://127.0.0.1:<mcp_port>/mcp`, the one server started with `metaform mcp serve --http`, which serves the folder it
was started in; the install proof then asks that address, and nothing answering fails with the next step
`metaform mcp serve --http`. By hand, for Claude Code:

```
metaform mcp serve --http --port 7434
claude mcp add --transport http --scope user metaform http://127.0.0.1:7434/mcp
```

`mcp_recovery` selects `relay` (the default) or `manual` when the server starts. Relay keeps the host connection
when a pre-dispatch schema check refuses a newer store and the package code on disk has changed. It starts a
replacement using the same Python interpreter, working folder and environment, replays the host's initialization
internally, and retries only refused calls. Manual returns the ordinary schema error, leaving restart to the host.
Unchanged code never starts a replacement. A host pinned to an old wheel must select a newer package source.
The `set` tool stores any setting for the server's folder.

`mcp_consent`, person only, `ask` by default or `confirm`, is how a call that needs the person's yes is confirmed; see Consent above. `mcp_apps`, on by default, offers the map, node, trace and glossary views to AI tools that show MCP Apps; `mcp_apps_offer`, `declared` by default, offers them only to AI tools that declare the extension, and `always` to every AI tool, for a host that shows them without declaring it, such as the specification's basic-host. `mcp_tasks`, on by default, answers a verb declared `task=True` or `task='run'` with a task to AI tools that declare the tasks extension.

## A2A

While `mcp_a2a` is on (global, person-only, on by default), `metaform mcp serve --http` also serves A2A 1.0 on the
same port, built on the official `a2a-sdk`, `a2a.py`. Other agents send Metaform work as tickets:

- `GET /.well-known/agent-card.json` is the public Agent Card. It names no project. Its one skill is the ticket, since
  every A2A message makes one; the skill says to send with `returnImmediately` and follow the task, and how long a
  waiting send is held. The card declares the bearer scheme and the Address extension,
  `https://metaform.ing/a2a/address-context/v1`, which a client need not activate.
- `POST /a2a` is the JSON-RPC binding and `/a2a/rest` the HTTP+JSON binding. A request names another registered
  project as its tenant: in its `tenant` parameter, or over HTTP+JSON under `/a2a/rest/{tenant}/`. Both need
  `Authorization: Bearer <token>`, the token in `<home>/run/a2a-token`, made on the first start, readable by its owner
  alone, and used by nothing else; delete the file and restart to change it. A request without it gets 401 with a
  `WWW-Authenticate` challenge, and every A2A route refuses a Host or Origin that is not this machine's, as the MCP
  endpoint does.
- `SendMessage` whose `contextId` is an Address the map holds opens a ticket there through `map work op=add`. A
  message with no `contextId` gets a task and a context of Metaform's own in `input-required`, its status offering
  the Addresses whose words fit; the client's reply on that task, with its `taskId` and `contextId`, names one and the
  ticket opens there, under the same task id. Any other `contextId` is refused, as A2A requires. The extension's
  metadata may give a `title`, a `kind` (broken, flawed or enhancement) and, in a reply, the `address`; nothing else
  is taken from a sender, so which agent works a ticket stays the person's. The ticket lands in To do and starts only
  when `dispatch_autostart` is on. A message sent again with the same `messageId` gets the task it made. A push
  configuration on the send is checked first, so a refused webhook opens nothing. Without `returnImmediately`, the
  send waits up to `mcp_a2a_wait` seconds (30 by default) for the task to end or need input, and not at all while
  nothing starts tickets by itself.
- A2A sees only what A2A made: the tickets its messages opened and its questions. `GetTask`, `CancelTask`,
  `SubscribeToTask` and the push configuration calls answer any other id, the person's own tickets and workflow runs
  among them, as not found, and `ListTasks` leaves them out, as A2A 1.0 sections 3.1.4 and 3.3.2 ask.
- A task's state is the one status vocabulary of work, `metaform.data.status`, converted by its `a2a`. A ticket is
  submitted while it waits, working once an agent takes it, completed with its resolution as an artifact, or canceled
  or failed as its work record's outcome says, with no artifact. A2A's interrupted states ask the client to act, so
  a ticket whose agent waits on Metaform's person (to log it in, to answer its permission or question, or after it
  stopped with the ticket open) reads as working, with `waitingOn: person` and a `reason` in the extension's
  metadata, and its status message names the wait. Input-required is only the question naming an Address, which the
  client answers.
- `CancelTask` is `dispatch cancel`, as MCP's `tasks/cancel` is, and withdraws a question no ticket was opened for.
  `ListTasks` lists the tickets and questions, newest first. `SendStreamingMessage` and `SubscribeToTask` stream
  each change over Server-Sent Events until the task ends or asks the client for input, when the stream closes as
  the SDK's own server closes it; a task that can no longer be read ends its stream as failed.
- Streams, waiting sends and push watches read a task again when its project announces a change: `map.changed` from
  this process, through the module's subscription, or from any other process of the home, through `events.listen`,
  BASE-053. A change only to an agent's thread lines wakes nothing, since no state is read from them. A slow read
  every 20 seconds covers what announces nothing.
- Push notifications go only to webhooks the person lists in `mcp_a2a_webhooks` (global, person-only), matched by
  scheme, host, port and path; with none listed the card offers no push. Configurations are kept in the project's
  database, `a2a_push`; a push watch follows its task through input-required to its end, and is watched again after
  a restart.

The extended card, `GetExtendedAgentCard`, lists one interface per registered project, its id as the tenant. The
wording other agents read, the card, the status messages and the errors, is in `resources/prompts.xml` under `a2a_`.

## Resources

`resources/list` serves `metaform://glossary`, `metaform://instructions`, the composed instructions, and each surfaced module's declared resources; the templates are `metaform://instructions/{module}`, `metaform://prompts/{name}` and `metaform://reports/{name}`. A command's arguments are in its tool's input schema, so no resource repeats them. `metaform://glossary` ends with the tool index and the rules block: every enabled module's `<rules>`, one line each, `[<module>] <rule> Why: <why>`. `completion/complete` fills an Address one segment at a time, from the map's own `children` read, for the address templates and for a slash command's `address`, `node` or `item` argument; a number at an address, or `<address>#<n>`, from the items numbered there; a module id and a stored prompt's name for their templates. A client that names `metaform://<address>` in a `subscriptions/listen` stream, or in `resources/subscribe` on the 2025 handshake, is sent `notifications/resources/updated` for it when an item is numbered there, by this server's calls or another process of the home: a one-line notice to read the brief again, never the items. The views, `ui://metaform/map`, `node`, `trace` and `glossary`, are listed with their `_meta.ui` only to a client the views are offered to. A module declares a resource with `Resource(uri, name, description, verb)` in its `Module.resources`; reading it runs that verb with no arguments. The intake module declares `metaform://intake/procedure` and `metaform://intake/schema`. A change to the surface is announced with `notifications/resources/list_changed`, as for tools and prompts.

Error next steps that a module wrote for the command line are read over MCP as the tool call or resource they stand for, MCP-038: `metaform map ask` as `call map_ask`, `metaform help map ask` as `call map_ask with the arguments its input schema lists`, `metaform help map` as `read resource metaform://instructions/map`.

## Events

Subscribes to `map.changed`, so the A2A server in this process, when one runs, reads the tasks it follows
again.

## Sync and async

`serve` runs the server's own loop, or uvicorn's with `--http`. Coroutine verbs are awaited in that loop, so a host's cancellation reaches them; plain verbs run in a worker thread.

## Layers

None.

## Lifecycle and cleanup

The server runs until its standard input closes. The relay owns routing tasks and any replacement process through
SDK transports. Calls already in progress finish before hand-over, with cancellation and host responses still
delivered to them. July subscription streams finish gracefully, so clients can reopen them. Errors after dispatch
are never replayed, because the call may already have committed a write. A failed replacement returns the schema
error and keeps the old session usable. Closing the host connection closes and reaps the replacement.

## Modules relied on

None; it serves the verbs of every module on the surface.

## Systems supported

Linux, macOS and Windows.

## Resources owned

Its standard input and output, for the protocol; with `--http`, the port `mcp_port` on 127.0.0.1, and with A2A on,
`<home>/run/a2a-token` and the tables `a2a_tasks`, `a2a_asks`, `a2a_push` and `tool_tasks` in each project's database.

## Installed and direct wheel

In an installed Metaform, uvx gives the server its own environment. A directly run wheel needs the `mcp` and `a2a-sdk` packages installed, since their dependencies are compiled.

## Demonstration

```
metaform mcp serve
metaform mcp serve --http --port 7434
```
