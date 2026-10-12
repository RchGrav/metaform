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

To run a stored workflow, open Add Task at its target node, choose a Workflow subroutine, and edit its Entry call arguments. For example, `workflow.quality.code.review(target=this)` passes the first linked node as the target. Task text is optional and can supply additional context. Check Start an agent now to run it through ACP, or leave it queued. The agent starts the call with `workflow run`, follows the stored procedure, and records its returned result on the ticket. The picker lists callable workflows selected in the active project's folder settings, matching the context dispatched agents use. No workflow run is recorded until the agent starts the call, so a failed ACP launch leaves a retryable ticket without a stranded run.

Autostart agents at the top of the menu bar controls automatic ticket dispatch, VIEW-042. It is separate from `--web-autostart`, which starts the GUI before an intake. Checked, it starts waiting work on free board glyphs, one agent per glyph, including tickets with unanswered questions; with undistributed tickets, `--dispatch-agents` sets the limit, 5 by default. Administration's Agents control changes that limit. Unchecked, Start all and each ticket's Start remain available. Answers reach the current ticket holder and remain on the ticket without changing its board placement. Chat beside a question opens its agent's session or starts a new agent with a new glyph to read the question and continue the ticket.

In the large area, the 2D map opens fitted to the whole diagram and eases to each new fit as nodes arrive or go. Clicking a node switches to a readable fit: the whole diagram while it fits above the minimum text size, otherwise centered on the selected node at that minimum. Keys 1 to 9 set the minimum from 8 to 24 px, 2 px apart; 5, 16 px, is the default. Fit, F and Home return to the whole diagram. Wheel zoom leaves both modes and holds the person's zoom until another click or Fit. In the small area, selection keeps the person's zoom and Fit cycles the views described by VIEW-008. Camera moves and wheel zoom ease in and out; dragging interrupts a move and follows the hand.

## Template version

Started from template 0.3.0.

## Declaration

`SUPPORTED_OS = ('linux', 'macos', 'windows')`, `DEPENDENCIES = ()`, `SHIPS_DISABLED = False`. `MODULE` declares `start`, its default verb, `stop`, the CLI-only `serve`, and a status hook. It subscribes to nothing. Its panes are the page's two views of the map, `map2d` on the left and `map3d` in the main area; the other modules declare the rest, under Toolbar and panes.

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
- `--web-toolbar`, `--web-layout` and `--web-workspaces`, JSON text, default empty, for the whole home: the toolbar and the panes as the person arranged them, and the person's named workspaces. Empty is the defaults the modules declare; `metaform unset --web-toolbar` returns to them. Their shapes are under Toolbar and panes. `config --show` and the settings screen show the JSON text in a text field, and `set` takes it checked against its shape; the page is where they are arranged.
- `--web-workspace`, a choice of `Default` and the saved workspaces, default `Default`, for the whole home: the workspace the page opens with and resets to.

## The server

`server.py` runs the standard library's threading HTTP server. Every request must carry a `Host` header naming the server's own address and port; on a wildcard bind only the port is checked, since the token guards every request there. On a bind address other than loopback, every request needs the home's token, kept in `run/web-token`: as `?t=` on the page URL, which also sets an `HttpOnly`, `SameSite=Strict` cookie, as that cookie, or as the `X-Metaform-Token` header. It serves `page/` at `/`, `vendor/` under `/vendor/`, `/api/server` with its process id and home, `/api/projects` with every registered project, `/api/clear-preview` with what clearing a project removes and keeps, each read of the data access object by its query name under `/api/<read>`, such as `/api/where`, `/api/work` and `/api/intake-recording`, with `/api/node` carrying what the modules add to a node's read as `map node` does, and the stored prompts' reads. The memory module's reads are `/api/memory-graph`, the whole graph with each join saying whether its memory shows at its node in the page's layers, `/api/memory-orphaned`, for the orphaned menu, and `/api/memory-note` for a node's one note; each runs the memory module's command in the server, as a tool call runs it, VIEW-031 and VIEW-034. `/api/events` is one server-sent events stream per open page, held open. The server's loop waits for a connection with no timeout and nothing in it polls. Its seventeen writes, VIEW-011, are POSTs from its own page, with the page's `Origin` and a JSON body: `/api/apply-layers`, `/api/save-prompt`, `/api/clear-project`, which clears only with `confirm` true, `/api/remove-project`, `/api/answer`, `/api/reopen`, which reopens a question answered by mistake, `/api/read`, `/api/task`, `/api/element`, `/api/restore`, `/api/note`, which writes the node's one note with `memory note`, `/api/memory`, which runs memory commands that write in order, `/api/move`, and `/api/dispatch-start`, `/api/dispatch-message` and `/api/dispatch-stop`, which run `metaform dispatch start`, `message` and `stop` in the project's folder, with a message's text after `--`, and `/api/dispatch-prompts`, VIEW-039. `GET /api/dispatch-agents` lists the agents dispatch starts, with whether each one's start command is found on this machine and which is the default, and its POST sets the default; `/api/dispatch-intake`, `/api/dispatch-resume`, `/api/dispatch-permit` and `/api/dispatch-configure` run `metaform dispatch intake`, `resume`, `permit` and `configure`, with an intake's text, a permission's option and a setting's value after `--`, VIEW-039 and VIEW-045. After a write that changed the map the server fires `map.changed` on the module event bus, as the chassis does after a command, VIEW-018, and pushes each change `changes.announce` returns to every open page. It writes what went wrong to `run/web.log`.

What an agent is given is shown as the agent is given it, MCP-037, so the person and the agents see the same thing. `/api/brief?address=` is a node's brief, `metaform.module.node_view`, the same answer the MCP map view's `brief` read gives: the text an agent reads at `metaform://<address>` exactly, from `metaform.module.node_brief`, the read the MCP server serves, with its size against the folder's `node_summary_bytes`, the latest number taken there and the items numbered there, newest first, each with its number, title and why, forty at a time, paged as MCP pages a list: a page with more after it gives `nextCursor`, passed back unchanged as `cursor=`, of the kinds named in `kind=` when given, from `metaform.module.node_items`, the list the MCP server's views read too: one read per module through its `items_at` hook, never one per number. It is read in the folder's own layers and active base, as an agent reads it, whatever the page shows. `/api/item?item=<address>#<n>` is one item as an agent reads it at `metaform://<address>#<n>`, its text and fields, its links among them, `metaform.module.item_view`, the answer the MCP views' `item` read gives too. `/api/agent-view` starts the folder's own MCP server, the one AI tools are registered with, and reads it over MCP as an agent connecting does, as the MCP Inspector reads a server: the server/discover result with its capabilities and the instructions sent at connect, counted in characters against the 2,048 Claude Code keeps; `metaform://glossary`, with the bytes its tool index takes; every tool, resource, resource template and prompt the lists give, each entry as received with its size, the tools largest first; with `address=` that node's brief; and what an agent pays before its first call, counted as Claude Code sends it to the model, each tool named `mcp__metaform__<tool>` with its description and input schema only: with tool search, Claude Code's default (the connect message, the tool names and any tool marked `anthropic/alwaysLoad`), with every tool loaded as the connect message asks, and without tool search (every tool in full). `/api/mermaid` is the map as a Mermaid flowchart from `metaform.outline.mermaid`, the writer `map mermaid` uses, with the page's layers, `direction=`, the roots the page leaves out, `leave_out=`, and `labels=`; a diagram past Mermaid's default limits also carries the notice in `X-Metaform-Notice`, which the page shows. On the page these are the side column's Brief tab, with its items by kind, each opened and its links to other memories followed to their node and back; What an agent sees…, from the Brief tab or the Agents menu, a dialog with what is paid before the first call, kept to the web GUI: in an AI tool's map view the brief draws neither it nor Copy as Mermaid, then the connect message, the glossary, the tools, each opened to its entry and schema, the resources and templates, the prompts and the brief, each with its size; and the Export menu's Mermaid (.mmd) and Copy as Mermaid. An item numbered past the latest this browser was shown at an address is marked unseen, apart from the agent's own New in the brief. The side column's tabs are the panes declared in the node group, map's Object, Brief and Provenance and the chassis's Prompt, in their declared order and with their titles and descriptions from `/api/workspace`.

## Toolbar and panes

The page's toolbar, its panes and their places are one system, served by `workspace.py` under `/api/workspace`. Modules and the chassis declare what they offer, `ToolbarItem` and `Pane` of `metaform.module`, in their own `Module(toolbar=, panes=)`, the chassis in `metaform/panes.py`; this module lays the person's arrangement over those defaults and keeps it in four global settings. The design follows what works in Creative Cloud (Photoshop's Edit Toolbar with its Extra Tools, tool groups, Restore Defaults; panels docked, grouped as tabs and floated; named workspaces with Reset and a built-in one that cannot be deleted), VS Code (views contributed with a default container, moved by the person, Reset View Locations) and JetBrains (tool windows anchored left, right or bottom; layouts with a fixed Default). A contribution is a record with an id, a title, a one-line why as its tooltip, an icon and a default place; the person's arrangement is stored apart, keyed by id; what a module adds later lands in its declared place; a disabled module's tools and panes go and come back where they were.

An id is `<owner>.<id>`: `map.brief`, `chassis.search`. Every request below names the page's project as `?project=<id>` or in its body, since the project's folder decides which modules are on.

### Reads

`GET /api/workspace?project=<id>` answers with everything the page draws and edits:

- `items`: each tool, `{id, owner, title, description, icon, icon_url, action, selection, group, placement, order, shortcut}`. `icon` is a built-in name, or null with `icon_url` the module's SVG. `action` is `{kind: "verb", verb, arguments, effect, caution}`, `{kind: "pane", pane}`, `{kind: "page", page}` or `{kind: "link", url}`. `selection` is not null when the tool acts on the selected node, and the tool is then off while nothing is selected. `description` is the tooltip.
- `panes`: each pane, `{id, owner, title, description, icon, icon_url, content, selection, area, group, visible, order, min_width, min_height}`. `content` is `{kind: "page", page}`, a view the page draws; `{kind: "verb", verb, arguments, url}`, a read verb's result; or `{kind: "resource", url, type}`, a file of the module.
- `toolbar`: the arrangement to draw, `{"toolbar": [[id, ...], ...], "extra": [id, ...]}`. Each inner list is one slot: its first tool shows, the others are behind it. `extra` holds the tools behind the toolbar's last slot, `…`.
- `layout`: the panes to draw, `{"areas": {"left"|"main"|"right"|"bottom": {"size": px|null, "groups": [{"id", "tabs": [id, ...], "active": id|null, "size": share|null}]}}, "floating": [{"pane", "x", "y", "w", "h"}], "off": [id, ...]}`. Each group is one pane area of tabs, stacked in its area in order; `size` is an area's width (left, right) or height (bottom) in CSS pixels, null for main, which fills; a group's `size` is its share of its area, null for an equal share. A pane in `off` keeps its place and is not drawn: turning it on puts it back there. A floating pane with null coordinates is placed as `place()` places a window today.
- `defaults`: the same two built from the declarations alone, for Restore Defaults.
- `workspace` and `workspaces`: the active one and every one, `Default` first.
- `icons` and `areas`: the built-in icon names and the five areas, `float` last.

`GET /api/workspace/pane?project=<id>&pane=<id>&selection=<address>` runs a verb pane's verb, as a tool call runs it, with the page's layers when `layers=` is given as the other reads take it; it answers `{pane, result, chars}`, `chars` the length of the result's JSON, what an agent is handed. Read it when the pane shows, when the selection changes and on each `map.changed` event; a pane with `selection` and nothing selected shows that it follows the selection. `GET /api/workspace/file/<owner>/<path>?project=<id>` sends an icon, a pane's file or a linked file a contribution names, and nothing else; HTML comes with the `sandbox` policy, so show it in `<iframe sandbox src=...>`, where it has no reach into the page.

### Writes

Each is a POST from the page with a JSON body, the checks of every write of the server, and answers with the whole read above; every other open page hears `{topic: "workspace"}` on its stream and reads again.

- `/api/workspace/arrangement {project, toolbar?, layout?}` saves what the person left, in the shapes above. Ids of modules turned off now are kept in the setting from before, so they come back in place.
- `/api/workspace/reset {project, part?}`, part `toolbar` or `layout` or both: back to the active workspace as it was saved; for Default, the declared defaults.
- `/api/workspace/save {project, name}`: the current toolbar and layout as a workspace of that name, replacing one, and active. Default is never saved over.
- `/api/workspace/select {project, name}`: that workspace active, its toolbar and layout the current ones.
- `/api/workspace/delete {project, name}`: deletes one; Default cannot be deleted. Deleting the active one keeps the current arrangement, under Default.
- `/api/workspace/run {project, item, selection?, confirm?}` runs a `verb` tool's verb with its fixed arguments and the selection, and only a declared tool's. A caution verb answers 409 with its caution and `confirm: true`: ask with `confirmAct` and send again with `confirm: true`. It answers `{item, result}`; show the result in a window of its own, or offer a text result as a file to save.

### What the page builds

The page reads `/api/workspace` once its project is chosen, and draws from it alone; nothing of the toolbar or the panes' places is kept in local storage any more. The theme and the text size stay in the browser, as view preferences of that screen. The settings are global, so every project opens the same way. Use the page's existing parts: `splitter()` for the area and group splits, `place()` and `movable` windows for floating panes, writing their place to `layout.floating` instead of `metaform.places`, `confirmAct()` for a caution, and the overlay stack for menus.

- The toolbar: one row of slots under the header, each slot's shown tool as an icon button with its title as the label where there is room, the description as the tooltip and `aria-label`, and the shortcut as `aria-keyshortcuts`. A slot of several tools carries a small corner mark; a long press or the context menu opens its flyout, and choosing a tool there makes it the slot's shown one, saved. The last slot, `…`, opens the extra tools. A pane tool is pressed while its pane is on and shown; clicking it then turns the pane off. A tool whose pane or page command this page does not carry is left out.
- Edit Toolbar…, from the Window menu and the toolbar's context menu: a dialog of two lists, Toolbar and Extra tools, each tool with its icon, title and why. Drag a tool between the lists or within them; drop it on another tool to share that slot, out of a slot to give it its own. Restore Defaults puts `defaults.toolbar` in the dialog, Clear Tools moves every tool to Extra tools, Done saves with `/arrangement`, Cancel leaves it as it was. The same dialog works with the keyboard: Up and Down move the focus, Alt+Up and Alt+Down move the tool, Enter moves it to the other list.
- The Window menu, in the header: every pane with a check, on or off; then Workspaces: each workspace with a check on the active one, New Workspace…, which asks for a name and saves, Reset <active name>, and Delete Workspace…, which lists all but Default; then Edit Toolbar….
- Panes: four docking areas around the main one, left, right and bottom, and floating windows. Each area holds its groups stacked, each group a tab strip over one pane; the tabs follow `tabs`, showing those not in `off`. Drag a tab onto another group's strip to join it, onto an area's edge to start a group there, where blue drop zones show while dragging, or away from every zone to float it; Ctrl while dragging keeps it from docking. A tab's context menu has Move to Left, Main, Right, Bottom and Float, and Close, which turns it off. A pane is never drawn smaller than its `min_width` and `min_height`. An area with no group shown takes no room. Swap, today's button on each map, now exchanges the places of `web.map2d` and `web.map3d` and saves the layout.
- Views the page draws, by `page`: `map2d` (today's small 2D map), `map3d` (the 3D stage), `object`, `provenance` and `prompt` (today's side panel tabs), `settings` (today's settings dialog, as a pane), `dock` (the chat), `board` (the Kanban), `messages` (the questions waiting for the person).
- Commands the page runs, by `page`: `search`, `export-markdown`, `export-xml`, `build`, `shortcuts`, `layers` (the layer list), `add-task` and `add-element` (their windows, at the selected node), `dispatch-node` (Add Task at the selected node with Start an agent now checked), `agents` (the Agents menu), `intake` (Run an intake), `orphaned` (Orphaned memories).
- Built-in icons the page's set does not draw yet, to add as the others are drawn: `board`, `brief`, `chat`, `code`, `cube`, `eye`, `gauge`, `layers`, `map`, `memory`.
- On a screen narrower than 820 px the areas stack in the order main, right, left, bottom, and the layout is left as saved.

### The Default workspace

The maps are on the left and in the main area; everything a person reads or types into is on the right. A person reads from the right and turning to the left to read is uncomfortable, so nothing text-heavy or interactive starts on the left. Today the side panel stands on the left; Default moves it to the right.

| Area | Group | Tabs, in order (off at first in brackets) |
| --- | --- | --- |
| left, 360 px | map2d | 2D map |
| main | stage | 3D map, (Board) |
| right, 420 px | node | Object, Provenance, Prompt, Brief, What the agent sees, Memories, (Settings) |
| right | chat | Chat, (Messages) |
| bottom, 280 px | none | |

The default toolbar, in order: Search; Node brief; What the agent sees; Layers; Board; Add task with Add element behind it; Chat; Agent on this node; Memories; Run an intake; Settings. Extra tools: Export Markdown, Export XML, Export Mermaid and Copy as Mermaid, the export group, each a command of the page, Build, Agents, Orphaned memories, Keyboard shortcuts. Each, and why it earns its place:

- Search, chassis: finding a node by its words is the fastest way into a map too large to scan.
- Node brief, map: everything held at a node, in full, for the person, `map where contents=true`.
- What the agent sees, map: the node exactly as an agent is handed it, counted, with its length, so the person sees what a call costs an agent's context, `map where`.
- Layers, map: which knowledge shows changes every read; choosing it is constant.
- Board, map: the tickets in priority order are the work itself.
- Add task and Add element, map: the two ways a person writes onto the map, one slot.
- Chat, dispatch: the person's line to the system agent and every agent at work.
- Agent on this node, dispatch: from a node to an agent working on it in one step; it opens the page's dialog, since starting an agent runs in the person's environment.
- Memories, memory: what agents learned at a node, read beside it; knowledge attaches to the receiving element.
- Run an intake, intake: a map starts with an intake and is checked against the project with another.
- Settings, chassis: every setting and module of the folder without the command line.
- Exports, chassis and map: the map as a document to hand on, Mermaid for drawing it in docs and reviews.

A code map pane is to come from the module that builds it; the tools and the layout take it as they take any contribution.

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
