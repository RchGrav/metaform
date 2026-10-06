# web

Metaform's one web GUI for the user: one server per Metaform home, serving every registered project.

## Purpose

People see the map in a browser. `metaform web` starts the server and prints its address; run again from any folder, it prints the address it already runs at. `metaform web stop` stops it. Before an intake, agents start it and tell the user the address, while `--web-autostart` is on, so the map can be watched as it is recorded. It ships enabled.

`metaform web serve v000001 v000002` reconstructs saved web variants and serves their static files together, each from its own temporary folder on an OS-assigned port at `127.0.0.1`, PROJ-019. It prints `<variant id>  http://127.0.0.1:<port>/` for each; open those addresses in browser tabs. `metaform web serve all` serves every variant of the latest origin, or add `origin=<id>` to select an earlier origin. The command runs in the terminal until Ctrl+C, then closes its listeners and removes its temporary folders. The Metaform GUI remains its own server on its fixed port.

Clear project in the header clears the selected project as `metaform clear project <project> --confirm` does, PROJ-025 and VIEW-019: it shows the command's caution, what goes and what stays, asks on the page, then clears through the same chassis operation and names any file it could not remove with what to do. Every open page then shows the project with no metaform until the next intake.

The `colors` picker in the header chooses one of the page's color themes, dark and light, VIEW-023. Each theme is one block of `page/app.css`, `:root[data-theme="<name>"]`, and defines the same colors; the script and the other rules hold none. In every theme each node, link and line holds 3 to 1 against its background, and each 2D label 4.5 to 1 against its box. The choice is kept in the browser's local storage and changes no setting. `page/theme.js` applies it before the page is drawn.

The page shows each node's condition from its work records, MAP-046: a node with an open `missing` record is drawn ghostly, at 70% opacity, and turns solid when its task is done; one with an open `broken` record flashes red until it is resolved; `exclude` keeps its look. The panel lists the selected object's records with their note, task, held and reviewed flags, and the resolution once done. `/api/work` is the store's `work` read.

Board opens the project's Kanban. Prioritize tasks with each card's Top, Up and Down buttons or by dragging it within its column. Higher cards come first; the stored order survives reopening the board and determines distribution and an agent's next waiting ticket, To do before Backlog. Reordering within a column keeps the ticket's assignment, progress and completion.

Add Task and each board card offer Eligible agents, defaulting to Any agent. Choose one or more agent types, or restore Any agent. The card shows the choice, saved through `/api/eligible` as the map module's ticket setting. The Start window enables a ticket only for an eligible agent. Start all selects eligible tickets before choosing one per glyph, leaving skipped cards' assignments and order intact.

Add Task can start the new ticket immediately: check Start an agent now and choose Claude Code, Codex or Gemini CLI. Add Element uses the same ACP dispatch for its validation ticket, with the validation prompt kept verbatim. A launch failure leaves the recorded ticket available on the board for another attempt.

To run a stored workflow, open Add Task at its target node, choose a Workflow subroutine, and edit its Entry call arguments. For example, `workflow.quality.code.review(target=this)` passes the first linked node as the target. Task text is optional and can supply additional context. Check Start an agent now to run it through ACP, or leave it queued. The agent starts the call with `workflow run`, follows the stored procedure, and records its returned result on the ticket. The picker lists callable workflows selected in the active project's folder settings, matching the context dispatched agents use. No workflow nonce is created until the agent starts the call, so a failed ACP launch leaves a retryable ticket without a stranded workflow run.

Autostart agents at the top of the menu bar controls automatic ticket dispatch, VIEW-042. It is separate from `--web-autostart`, which starts the GUI before an intake. Checked, it starts waiting work on free board glyphs, one agent per glyph, including tickets with unanswered questions; with undistributed tickets, `--dispatch-agents` sets the limit, 5 by default. Administration's Agents control changes that limit. Unchecked, Start all and each ticket's Start remain available. Answers reach the current ticket holder and remain on the ticket without changing its board placement. Chat beside a question opens its agent's session or starts a new agent with a new glyph to read the question and continue the ticket.

In the large area, the 2D map opens fitted to the whole diagram and eases to each new fit as nodes arrive or go. Clicking a node switches to a readable fit: the whole diagram while it fits above the minimum text size, otherwise centered on the selected node at that minimum. Keys 1 to 9 set the minimum from 8 to 24 px, 2 px apart; 5, 16 px, is the default. Fit, F and Home return to the whole diagram. Wheel zoom leaves both modes and holds the person's zoom until another click or Fit. In the small area, selection keeps the person's zoom and Fit cycles the views described by VIEW-008. Camera moves and wheel zoom ease in and out; dragging interrupts a move and follows the hand.

## Template version

Started from template 0.3.0.

## Declaration

`SUPPORTED_OS = ('linux', 'macos', 'windows')`, `DEPENDENCIES = ()`, `SHIPS_DISABLED = False`. `MODULE` declares `start`, its default verb, `stop`, the CLI-only `serve`, and a status hook. It subscribes to nothing.

## Common base used

`metaform.module` for the declaration, `Context`, `Status`, `Stop` and `Subscription`; `metaform.settings` for its three settings; `metaform.home` for the home's folder and the registered projects.

## Prompts

`resources/prompts.xml` holds `instructions`, `web is active.`, listed in the instructions agents read under "modules available.", and `autostart`, which follows it on web's line while `web_autostart` is on and which `metaform status` shows before the intake, VIEW-015 and MCP-031.

## Verbs

- `start`, the default, so `metaform web` runs it: when this home's server answers at the address in `run/web.json`, returns `state: running` with its address; otherwise checks the port and bind address are free, starts `server.py` as a process detached from the terminal with a pipe as its standard output, waits on the pipe for the server's one line saying it listens, then asks it once, and returns `state: started` with its address. The wait is one wait for a message, limited to 15 seconds so the command never hangs on a server that neither answers nor ends, QUAL-015. On a bind address other than loopback the address ends with `?t=<token>`, and `token` is returned too. A port held by another program stops with `Next: metaform set --web-port <port>`; an address it cannot bind stops with `Next: metaform set --web-bind <address>`. Tool `web_start`.
- `stop`: opens the recorded server's events stream, ends the server, reads the stream until the system closes it with the process, removes `run/web.json`, and returns `state: stopped`, or `state: not running`. Tool `web_stop`.
- `serve <variant id>... | all [origin=<id>]`: reconstructs through the chassis's `Store.extract`, then serves each folder's static files on a separate OS-assigned loopback port. A selector waits for connections without polling. Ctrl+C closes the servers and removes the temporary copies. CLI only; this command runs for the lifetime of the comparison.

## Settings

- `--web-port`, a number, default 7433, for the whole home.
- `--web-bind`, text, default `127.0.0.1`, for the whole home. At a wildcard address, `0.0.0.0` or `::`, the printed address uses the machine's host name.
- `--web-autostart`, on or off, default on, per folder. While on, the status hook's notice tells agents to start the GUI before an intake and give the user its address.

## The server

`server.py` runs the standard library's threading HTTP server. Every request must carry a `Host` header naming the server's own address and port; on a wildcard bind only the port is checked, since the token guards every request there. On a bind address other than loopback, every request needs the home's token, kept in `run/web-token`: as `?t=` on the page URL, which also sets an `HttpOnly`, `SameSite=Strict` cookie, as that cookie, or as the `X-Metaform-Token` header. It serves `page/` at `/`, `vendor/` under `/vendor/`, `/api/server` with its process id and home, `/api/projects` with every registered project, `/api/clear-preview` with what clearing a project removes and keeps, each read of the data access object by its query name under `/api/<read>`, such as `/api/where`, `/api/work` and `/api/intake-recording`, with `/api/node` carrying what the modules add to a node's read as `map node` does, and the stored prompts' reads. The memory module's reads are `/api/memory-graph`, the whole graph with each join saying whether its memory shows at its node in the page's layers, `/api/memory-orphaned`, for the orphaned menu, and `/api/memory-note` for a node's one note; each runs the memory module's command in the server, as a tool call runs it, VIEW-031 and VIEW-034. `/api/events` is one server-sent events stream per open page, held open. The server's loop waits for a connection with no timeout and nothing in it polls. Its seventeen writes, VIEW-011, are POSTs from its own page, with the page's `Origin` and a JSON body: `/api/apply-layers`, `/api/save-prompt`, `/api/clear-project`, which clears only with `confirm` true, `/api/remove-project`, `/api/answer`, `/api/reopen`, which reopens a question answered by mistake, `/api/read`, `/api/task`, `/api/element`, `/api/restore`, `/api/note`, which writes the node's one note with `memory note`, `/api/memory`, which runs memory commands that write in order, `/api/move`, and `/api/dispatch-start`, `/api/dispatch-message` and `/api/dispatch-stop`, which run `metaform dispatch start`, `message` and `stop` in the project's folder, with a message's text after `--`, and `/api/dispatch-prompts`, VIEW-039. After a write that changed the map the server fires `map.changed` on the module event bus, as the chassis does after a command, VIEW-018, and pushes each change `changes.announce` returns to every open page. It writes what went wrong to `run/web.log`.

## Events

Automatic dispatch is checked when the server starts, when its page saves the dispatch settings, and on selection-relevant `map.changed` events. One worker coalesces changes and starts batches sequentially, so page reads remain responsive and simultaneous changes do not launch competing batches. Questions do not block selection or park unfinished tickets, which return to To do. Answers change no board placement because a question records a dependency within the task, not evidence that the whole task is unavailable. `/api/dispatch-autostart` reads and saves these project settings through GET and POST; `/api/dispatch-chat` starts or reopens a question's chat through POST.

Hears `map.changed`, which the chassis fires after any command that changes a project's map, VIEW-018, through the base's listener, BASE-053: the server opens it with `events.listen('web', ...)` once it listens, and each `map.changed` published in another process, a command, the MCP server or a dispatch runner, reaches it and is pushed to every open page, which redraws without a reload. The changes of the page's own writes are pushed from what `events.announce` returns. A change to a project no longer registered is not pushed, since a page has nothing of it to read. With no server running nothing listens, and nothing is sent.

## Sync and async

Every verb is a plain function.

## Layers

None. The web GUI reads through the data access object and writes only what VIEW-011 names.

## Lifecycle and cleanup

No `start` or `stop` hooks, and no tasks. The server is its own process, detached from the terminal that started it; `metaform web stop` ends it, and so do logout and restart. Inside other Metaform commands only the `map.changed` subscriber runs, once per command that changed the map.

## Modules relied on

None by import. The web GUI reads through the chassis's data access object and settings. Its dispatch controls run `metaform dispatch` on the command line, so they work while the dispatch module is enabled and say `metaform enable dispatch` while it is not, VIEW-039.

## Systems supported

Linux, macOS and Windows. On POSIX the server runs in a new session; on Windows as a detached process with no console.

## Resources owned

`page/`, the GUI's HTML, CSS and scripts, and `page/agent-glyphs/`, the flat icon of each agent figure, Metaform's own, VIEW-039; and `vendor/`, the bundled libraries with their licenses, VIEW-003. Under the home: `run/web.json`, the running server's record, with its address, process id and nonce; `run/web-token`, the token for bind addresses other than loopback; `run/web.log`, what went wrong in the server.

## Installed and direct wheel

The same in both; the page and the vendor files travel inside the module.

## Demonstration

```
metaform web
metaform web --json
metaform set --web-port 7500
metaform web stop
```
