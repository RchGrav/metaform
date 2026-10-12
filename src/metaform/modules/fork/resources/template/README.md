# template

The empty start of every Metaform module. Copy this folder to begin a module; every heading below is one a module's README answers.

## Purpose

What the module is for, in two to four sentences.

## Template version

The template changelog version this module started from: 0.2.0.

## Declaration

`SUPPORTED_OS`, `DEPENDENCIES`, `SHIPS_DISABLED` and `MODULE`, with what each is set to and why.

### Toolbar items and panes

The tools the module adds to the web GUI's toolbar, `MODULE.toolbar`, and the panes it adds to its workspace, `MODULE.panes`, with why a person uses each. Declare them with `ToolbarItem` and `Pane` of `metaform.module`; they are defaults the person rearranges on the page, and a disabled module's tools and panes go with it.

A `ToolbarItem(id, title, description, icon=...)` does exactly one thing: `verb=` runs one of the module's verbs with fixed `arguments=`, never one that reaches agents or the network; `pane=` shows a pane, the module's own by id or another's as `<module>.<id>`; `page=` runs a command the page carries, such as `search` or `add-task`; `link=` opens an `http(s)://` or `metaform://` address or a file under `resources/`. `selection=` names the noun that receives the selected node's address, and the tool is off while nothing is selected. `group=` shares one toolbar slot with the tools of that group, the first shown and the rest behind it; `placement=` is `toolbar` or `extra`, the tools behind the toolbar's last slot; `order=` sorts, lowest first; `shortcut=` is a key such as `Alt+B`.

A `Pane(id, title, description, icon=...)` shows exactly one thing: `verb=`, a `read` verb of the module, run with `arguments=` and the selection whenever the pane shows, the selection changes or the map changes; `page=`, a view the page draws itself; or `resource=`, a `.md`, `.txt` or `.html` file under `resources/`, the HTML in a sandboxed frame. `area=` is where it starts, `left`, `main`, `right`, `bottom` or `float`; `group=` the tab group it joins there; `visible=` whether it starts on; `order=`, `min_width=` and `min_height=` its place and least size. Keep what a person reads or types into on the right and leave the left to the maps.

The description is one line saying why a person uses it, not its title again; it is the tooltip. The icon is a name from `metaform.module.ICONS` or an SVG under `resources/`. Ids are lowercase letters, digits and hyphens, unique in the module. The loader refuses a module whose tool or pane names a verb it does not declare, a noun its verb does not take, a pane verb that writes, or a file it does not carry. The template's `about` tool shows its `about` pane, `resources/pane.md`.

## Common base used

Which of `metaform.module`, `metaform.settings`, `metaform.data`, `metaform.events`, `metaform.prompt_files`, `metaform.axiom`, `metaform.home`, `metaform.outline` and `metaform.finish_xml` the module uses, and for what. Through `metaform.axiom` a module checks a prompt's structure before it stores or sends it, `axiom.notices(where, text)`, and keeps or sends it unchanged, MCP-035 and BASE-057. Through `metaform.prompt_files` a module reads its own `resources/prompts.xml`, `prompt_files.text(resources.files(__name__), name)`, or `prompt_files.required` when a missing prompt is a defect, MCP-031. Through `metaform.data` a module reads and writes the map's layers and the work records: the condition of an element or a join, a subtype join included, `missing` (the thing does not exist at all, or is not built yet), `broken` (exists, not working, not connected or orphaned), `flawed` (works but is not right), `enhancement` (works, could be better) or `exclude` (outside the scope, or conflicting with a superseding specification), kept apart from the map with a note and a task, `store.add_work`, `store.edit_work`, `store.finish_work` and `store.work`, MAP-046 and STORE-042; hello's `todo` shows it. Through `metaform.data` a module also declares tables of its own, `Tables`, `Table`, `Column` and `Index`, and reads and writes them in `store.tables()`, STORE-045; hello's `visit`, `note` and `notes` show it. Through `metaform.module` a module adds to the read of a node with `Module(node_read=...)`, a function of the context and the node that returns plain data, shown under the module's id in `map where` and `map node`, or None for nothing, BASE-035; hello's `node_read` shows it. A module keeps its own fields on a work record, such as a dispatched agent's session id, in a table of its own keyed by the work id, STORE-045, so the work table's layout never changes for them, and shows them with `Module(work_read=...)`, a function of the context and the work record that returns plain data, shown under the module's id in `map work id=<id>`, or None for nothing, BASE-035; hello's `todo` and `work_read` show it. A module says how much it holds at a node, and never what, with `Module(node_count=...)`, a function of the context and a tuple of element addresses that returns a `Count`: the word for one and for several, at each address how many, how many the last session there wrote and how many the calling session wrote, and its `counts` prompt, the line saying how to read them; an agent orienting on its node is told these counts for the node and its direct neighbours once per session, and after that only what changed, MCP-039. memory's `node_count` shows it. A module numbers what it writes at an address, MCP-037: each item, a memory, a question, a ticket, takes `store.number(address)`, the next number of that address's one counter in the project's database, which counts up from 1 and never reuses a number, kept with the item and shown in hex, `metaform.data.reference(address, n)`, `code.manager.route#1f`; a module's upgrade numbers the items it already holds with `tx.number(address)` in creation order. Every such write carries a short title, and one that records knowledge or a decision a short why; the verb refuses one without them with `metaform.module.titled(ctx, what, title, why, why_needed=...)`, whose one-line next step says which is missing. The module reads one item back with `Module(item_read=...)`, a function of the context, the address and the number that returns plain data, `kind`, `title`, `why`, `body` and `links`, or None, served at `metaform://<address>#<n>` and by `map item`. memory's `item_read` shows it. It lists them with `Module(items_at=...)`, `items_at(ctx, address, before, limit)`, a function or coroutine returning those numbered below `before` (all when None), newest first, at most `limit`, each `number`, `kind`, `title` and `why`, in one read, and names the kinds it numbers with `Module(item_kinds=(...))`, so a list asked for other kinds skips it; `metaform.module.node_items` merges every module's list for a node's brief, and `items_page` pages it with MCP's opaque `cursor` and `nextCursor`. A module with `item_read` and no `items_at` is read number by number, the slow way. memory's `items_at` shows it.

Shipped modules and a user's modules share these public services, BASE-004 and QUAL-016, so an extension can use the same capabilities without importing private chassis code. `metaform.module` offers `project_for(folder, named=None)` for folder context, `surface(folder)`, `on_surface(group, folder)`, `aliases(folder)`, `command_summary(name)` and `chassis_version()` to describe the available commands, and `refresh_modules()` for a long-running process to load or drop modules enabled or disabled since it started. `settings.toggled_layers(folder)` reads the folder's chosen layers. `metaform.events` offers `listen(module, handler)` for a process with no `Context`, the same as `ctx.listen`, and `announce(folder, surface)` for a long-running process to publish the pending map changes of a call it ran.

`metaform.home` offers the home and its projects: `home()`, `project(id)` and `projects()`; `to_clear(project)` and `clear_project(project)`; `backups(project)` and `restore_project(project, name=None)`; and `not_empty(project)`, `removal_caution(project)` and `remove_project(project)`. The caller obtains the operation's confirmation through its declared `Verb.caution`. `remove_project` enforces that the project is empty and keeps its source files, history and backups. `metaform.data` offers `query_reads()` to list named reads and `query_read(store, name, arguments)` to run one with its existing text argument conversions. `Record` supports module-defined records, `plain(value)` converts nested records to JSON-ready data, and `NewerStore` identifies a store requiring newer code. `metaform.outline.markdown(store, address=None, selection=None, raw=False)` and `metaform.finish_xml.xml(store, address=None, selection=None, raw=False)` are the shared map document writers. The map command and web export use them directly so each format has one implementation, BASE-004, MAP-052, MAP-059 and VIEW-024. Hello's `basedemo` shows the shared reads and removal preview, `base-restore` and `base-remove` show the project actions, and its existing `follow` shows `Context.listen`.

## Prompts

The prompts in `resources/prompts.xml`, each an element named for the prompt, and where each is served, MCP-031. `instructions` is listed in the instructions agents read under "modules available."; a copy writes its own module name in place of `template`. `prompt_files.module_commands(id)` reads a loaded module's declared slash commands through the public base, returning an empty list when the module is not found.

`rules` holds the module's rules, MCP-031: `<rule why="the reason">One sentence.</rule>` each, a rule an agent keeps while it works with the module and the reason it holds. The MCP server lists the rules of every enabled module at the end of `metaform://glossary`, one line each, `[<module>] <rule> Why: <why>`, so an agent reads each once. A rule without a why stops the module loading. The template's is empty; memory's shows one.

## Verbs

Each verb, what it returns, and its CLI form `metaform <id> <verb>` and tool form `<id>_<verb>`, and its `effect`, `read`, `write` or `remove`, with `open_world` when it reaches agents or the network; the MCP server gives them to hosts as the tool's annotations. Mark a verb that can take long `task=True`: an AI tool that declares the MCP tasks extension is answered with a task it polls, and every other caller waits as before, BASE-030; hello's `wait` shows it. A cancel stops an `async` verb at its next `await`; a verb run in a thread finishes, and its task completes with its result, so a task never reads cancelled while its effect lands. A verb that returns `{'run': <run id>}`, a workflow run record the server itself advances to its end, such as an agent Metaform starts and steers, is marked `task='run'`: it runs as ever, and that run is the task, followed until it ends. A task only for work the server advances by itself: a host gives the model a task's result only once it ends, so a verb whose result the calling agent must act on, such as workflow's `assign`, is marked neither. A verb's `caution` is put to the person in their AI tool where it can show a form, so the agent does not answer for them, MCP-006.

## Settings

Each setting the module declares, its default, and which verbs read it as a switch.

## Events

The topics the module publishes and those it subscribes to. After any command that changes a project's map, the chassis fires `map.changed` with `project` and `base_id`, no id meaning the project's bases changed, and the web server does the same after the page's own writes; a module does nothing to announce its writes, and any module can subscribe to it, as the web module does to redraw its open pages, VIEW-018. The chassis fires it when the command ends, so writes a module makes outside a command, in a task it spawned, and writes made inside a verb that runs on for a long time, such as `dispatch run` or a server run in the foreground, reach an open web GUI while it runs only when the module publishes `map.changed` itself after each write, with the project and the id of the metaform it wrote to: `ctx.publish('map.changed', {'project': ..., 'metaform_id': ...})`, or `await ctx.publish_async(...)` from a coroutine. The chassis still fires it once for the command when the command ends. dispatch's runner shows it, publishing after each write it makes. A module whose own process runs on, such as a server or a runner, hears `map.changed` published in other processes with `listener = ctx.listen(handler)`, BASE-053: the handler gets each payload in the listener's own thread, so code on a loop hands it over with `loop.call_soon_threadsafe`, and `listener.close()` ends it. Its own process's changes reach it through its own code, not the listener. hello's `follow` shows it. Nothing polls for a change, and nothing a person or an agent waits on blocks behind slow work, QUAL-015.

## Sync and async

Which verbs and subscribers are coroutines.

## Layers

The layers the module writes, their mutable and hideable declaration, and their provenance. The tables the module declares in `MODULE.tables`, STORE-045: each table's columns, key, indexes and place, `metaform` beside the map or `project` kept through a clear; the version, and what its `upgrade` moves at each raise; and which verbs read and write each table in `ctx.require_store().tables()`.

## Lifecycle and cleanup

What `start` and `stop` do, the tasks the module spawns, and what unload leaves behind.

## Modules relied on

Other modules this one needs, reached through their verbs and events, never by import.

## Systems supported

The systems in `SUPPORTED_OS`, and any verb that narrows them.

## Resources owned

Files, processes or connections the module owns, and when it releases them.

## Installed and direct wheel

How the module behaves in an installed Metaform and in a directly run wheel.

## Demonstration

A short command sequence that shows the module working.
