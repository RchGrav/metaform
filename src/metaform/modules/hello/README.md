# Hello World

A demonstration of every Metaform module feature, each working once.

## Purpose

hello greets names, keeps each greeting as an item of a layer in the project's store, and publishes an event for every greeting. It exists to show how a module behaves on the CLI and over MCP.

## Template version

Started from template 0.2.0.

## Declaration

`SUPPORTED_OS = ('linux', 'macos', 'windows')`, `DEPENDENCIES = ()`, `SHIPS_DISABLED = True`, so it is off until `metaform enable hello`. `MODULE` declares its verbs, one subscription, `start` and `stop` hooks, a status hook, and `default='history'`, so `metaform hello` with no verb runs `history`; `metaform hello --help` still prints the syntax.

## Common base used

`basedemo` returns the package source metadata fingerprint as `code_print`, using the public `metaform.module.code_print()` service. Long-running modules use it to detect changed code before attempting schema recovery; it does not guarantee that a replacement can open the store, STORE-029 and QUAL-016.

`metaform.module` for the declaration, `Context`, `Stop`, and the report functions `save_report`, `feedback`, `list_reports` and `read_report`. `metaform.settings` for its five settings, one of each kind. `metaform.data` for its layer, its work records and its own tables.

`basedemo` also uses `metaform.home` for the active home, project lookup and project previews, `settings.toggled_layers` for the folder's layers, and `refresh_modules` from `metaform.module`. It uses `metaform.data` for named reads, `plain` and `NewerStore`. `base-restore` and `base-remove` call the project services of `metaform.home`. These examples show that user modules can use the same capabilities as shipped modules without importing private chassis code, BASE-004 and QUAL-016.

## Prompts

`resources/prompts.xml` holds `instructions`, `hello is active.`, listed in the instructions agents read under "modules available." while hello is on, MCP-031.

## Verbs

- `greet <name> [--loud]`: returns the greeting and publishes `hello.greeted`. Tool `hello_greet`.
- `wait <seconds>`: waits, then returns `waited <n> s`. Tool `hello_wait`.
- `history`: returns the names greeted so far. The default verb. Tool `hello_history`.
- `forget [--confirm]`: deletes the greeting layer. A caution verb. Tool `hello_forget`, with `confirm`.
- `beep`: rings the terminal bell, on Windows only.
- `todo <task>`: writes a `missing` work record on the module's own element, `code.module.hello`, with the task, and keeps how many names hello had greeted then in its own table `todos`, keyed by the work id; returns the record id. `metaform map work id=<id>` shows that count under `hello`, through `work_read`, BASE-035. Tool `hello_todo`.
- `done <id> <resolution>`: marks that record done, its resolution kept beside it. Tool `hello_done`.
- `count`: says `hello has greeted <n> names.` with `ctx.say` and returns `{"greeted": n}`. With `--json` the sentence goes to standard error and only the data to standard output; over MCP it is a line of the result. Tool `hello_count`.
- `welcome <name>`: an async verb that publishes `hello.greeted` with `await ctx.publish_async(...)`; `ctx.publish` inside a running loop is refused, BASE-009. Returns `welcome, <name>`. Tool `hello_welcome`.
- `follow`: waits for the next change to the map made in another process and shows it, `{"changed": [<payload>]}`. It listens with `ctx.listen`, BASE-053, whose handler runs in the listener's own thread and hands the payload to the verb's loop with `call_soon_threadsafe`; the listener closes when the verb returns. Only on the command line, since over MCP it would hold the tool call until the map changed.
- `later <name> <seconds>`: starts a task with `ctx.spawn` that greets the name after the seconds, and returns at once. The task belongs to hello: it runs on after the verb returns for as long as the process runs, as the MCP server does, and the chassis cancels it when the process ends or hello unloads, BASE-018. From the command line the process ends at once, so the name is not greeted. Tool `hello_later`.
- `greet-favorite`: greets the `--favorite` name. With none set it raises `Stop('No favorite is set.', 'metaform set --favorite <name>')`, which the CLI prints as `Error:` and `Next:` lines with exit 2, CLI-009. Tool `hello_greet-favorite`.
- `uptime`: returns how long ago `start` ran in this process. Tool `hello_uptime`.
- `repeat <name> [--times <n>]`: returns the greeting `--times` times. Tool `hello_repeat`.
- `greet-friends [--friends <names>]`: greets each name in `--friends` and publishes `hello.greeted` for each. Tool `hello_greet-friends`.
- `report <text>`: saves a report with `save_report`, run id and layer the id of `hello.greetings`, and returns the file name; the layer's provenance then carries it as a `report` ref, BASE-045. Tool `hello_report`.
- `feedback <text>`: saves feedback on the Metaform process with `feedback` and returns the project, the run id and the file names. Tool `hello_feedback`.
- `reports`: returns the file names `list_reports` gives for this project, one a line. Tool `hello_reports`.
- `read-report <name>`: returns one listed file's text exactly with `read_report`; a name that is not listed stops with `Next: metaform list reports`. Tool `hello_read-report`.
- `visit <name>`: counts a visit by the name in hello's own table `visits`, beside the map, and returns `<name>: <n> visits`. It reads the row by its key and adds or changes it in one transaction. Tool `hello_visit`.
- `note <text>`: keeps a note in hello's own project-level table `notes` and returns its id. Tool `hello_note`.
- `notes`: returns the notes in time order, read through the table's index on `at`. Tool `hello_notes`.
- `basedemo`: reads the shared home, project and layer services, runs named map reads, and shows the selected project's backups and removal preview. It demonstrates the public base without clearing, restoring or removing a project. Tool `hello_basedemo`.
- `base-restore [name] [--confirm]`: restores the selected project's named backup, or its newest backup when no name is supplied. The existing `Verb.caution` confirmation applies, and the project services back up its current contents before replacing them. It is declared `person_says=True`, the person's decision: a command an agent runs, or an agent's `confirm` over MCP, is refused with the command the person runs, and only the person's `--confirm` or their yes to their AI tool's form runs it. Tool `hello_base-restore`.
- `base-remove [--confirm]`: removes the selected empty project's registration and folder selections, retaining its source files, history and backups. A nonempty project must be cleared first. The existing `Verb.caution` confirmation applies. Tool `hello_base-remove`.

## Settings

`--greeting`, default `hello`. `--loud`, default off, also greet's switch. `--favorite`, a select whose choices are the names greeted in this folder's project. `--times`, a number from 1 to 10, default 1, repeat's switch. `--friends`, a list, default empty, written `--friends ada,bob`, greet-friends' switch.

## Events

Publishes `hello.greeted` with `{"name": ...}`, from `greet` with `ctx.publish` and from `welcome` and `later` with `ctx.publish_async`. Subscribes to it to record the name, and finishes its layer on the first greeting so it is seen in context. It has no code to announce the write: the chassis fires `map.changed` when the greet command ends, so an open web GUI shows the greeting at once, VIEW-018 and QUAL-016.

## Sync and async

`wait`, `welcome`, `later` and `follow` are coroutines, and so is the task `later` spawns. Every other verb, the subscriber and the hooks are plain functions.

## Work records

A module keeps the condition of an object as a work record, apart from the map, MAP-046 and STORE-042: `store.add_work(Node('element', address), 'missing', task=...)`, `store.edit_work(id, {...})` and `store.finish_work(id, resolution)`. `todo` and `done` show it; the status line counts the open ones, `Hello: 1 greeted, 1 to do`; the web GUI draws the element ghostly while a missing record is open and solid once it is done. Every element and join read, a subtype join's included, carries `open_work`, the conditions of its open records.

## Tables

`MODULE.tables` declares hello's own tables at version 2, STORE-045. `visits(name, times)`, keyed by `name`, has `place='metaform'`: it is the table `"hello.visits"` in the metaform's store, and goes with the metaform when the project is cleared. `notes(note_id, text, at)`, keyed by `note_id` with an index on `at`, has `place='project'`: it is in `projects/<project>/modules/hello.sqlite3`, and a clear of the project's metaforms keeps it. The chassis creates both on first use and carries both through export and import. `note` and `notes` reach them with `ctx.require_store().tables()`. `visit` uses its declared DAO operation.

## Layers

`hello.greetings`, a knowledge layer, mutable and hideable, with provenance module `hello`, workflow `greet`, role `module`. Its items attach to the element `code.module.hello` the layer creates for them.

## Lifecycle and cleanup

`start` runs once when hello loads, before its first verb, subscriber or tool call, and records when it ran; `uptime` reads that. `stop` runs once when hello unloads or the process ends, after the chassis has cancelled the tasks `later` spawned, and clears it. Unloading leaves the layer and the report files in place.

## Modules relied on

None.

## Systems supported

Linux, macOS and Windows. `beep` runs on Windows only.

## Resources owned

Its layer, and the report and feedback files `report` and `feedback` write under the home's `projects/<id>/reports/`, never in the project folder.

## Installed and direct wheel

The same in both: its data lives in the project store of the Metaform home the run uses.

## Demonstration

```
metaform enable hello
metaform add project demo .
metaform hello greet world --loud
metaform hello history
metaform hello basedemo
metaform hello todo "greet in every language"
metaform hello done <id> "greets in Latin now"
metaform hello forget --confirm
```

Each public import a module can use, and the command that shows it:

| Import | Command |
|---|---|
| `ctx.say` | `metaform hello count`, and `metaform hello count --json` to see the sentence leave standard output |
| `ctx.publish_async` | `metaform hello welcome ada` |
| `ctx.spawn` | `metaform hello later ada 5`; over MCP, `later` with name `ada` and seconds `5`, then `history` after five seconds |
| `Stop` from a verb | `metaform hello greet-favorite` with no favorite set |
| `start` and `stop` | `metaform hello uptime` |
| `Module.default` | `metaform hello` |
| `settings.number` | `metaform hello repeat ada --times 3` |
| `settings.items` | `metaform set --friends ada,bob`, then `metaform hello greet-friends` |
| `save_report` | `metaform hello report "Greets in English only."` |
| `feedback` | `metaform hello feedback "The greet help was clear."` |
| `list_reports` | `metaform hello reports` |
| `read_report` | `metaform hello read-report <name>`, a name `reports` lists |
| Shared home/project, layer, query and record conversion services | `metaform hello basedemo` |
| `restore_project` | `metaform hello base-restore name=<backup> --confirm` |
| `remove_project` | `metaform hello base-remove --confirm`, with an empty project selected |
| `Context.listen` | `metaform hello follow`, then change the map in another process |

`MODULE.data` declares `count_visit` as a DAO operation. `visit` calls
`store.count_visit(name)`; the handler gets `DataTx` and reaches `visits`
through `tx.tables()` on the same transaction. A call inside `Store.atomic()`
commits or rolls back with the native map writes in that block.

## Authored roles and delivered context

Contribute `AgentRoleDefinition(name, purpose, prompts)` values as `Provides('agent.roles', definitions)`.
Each prompt is its existing prompt-store identity, in delivery order. `metaform agents resolve name=<name>`
and `metaform://role/<name>` resolve the definition through the enabled provider and its owning renderer.
An authored role is a responsibility separate from the operational `METAFORM_ROLE`; inspection changes no binding.
The hello module contributes `hello.greeter`; the template keeps an empty declaration.

`Provides('prompt.render', renderer)` supplies owning-module bindings as `renderer(ctx, component, bindings)`.
The resolver then renders the actual selected prompt-store version and reports a fallback separately. Generated
duties may be stored without an XML element through the `agent.role` service used by the GC's Role Creator.

`prepare_agent_context(folder, session, components)` selects exact component bodies still due in the current
epoch. `record_agent_context` acknowledges only bodies handed to the harness; rendering and queuing do not
acknowledge them. `advance_agent_context` is for completed compaction or recovery without retained context.
Both inline turns and a worker's separate MCP process use the same recipient identity and persistent ledger.
A module returning knowledge can use `ctx.queue_context(components, epoch)`, with each component's exact
`delivered_value`; MCP records only complete bodies that survive response shaping.
`Count.revisions` identifies changed entries whose totals stayed the same, and `Count.updated` counts updated
unread bodies without changing the existing total/new/mine tuple.
