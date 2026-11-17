# Changelog

Each change to the module contract, newest first, so a module copied from the template can follow it.

## Unreleased

- 2026-11-17, decision t-legacy-keep (kickoff Phase 3, `docs/plans/old-store-removal.md` step 2): for a project whose map is in the project store, hello shows the project-store way. It tests `metaform.project.holds(stored_name(id))` and then reads and writes through `metaform.project.run` and `overlay_records`: the greetings are records of its overlay `hello_greetings` at its own element `<project>.code.module.hello`, the overlay defined on `OVERLAY_NOT_DEFINED` and the element added with the record on `ELEMENT_NOT_IN_SKELETON`; `todo` and `done` write a ticket of the `tickets` overlay, done by the revision it read; `forget` deletes the greeting records by id; `basedemo` returns `{"map": ...}`; `report` saves under run id `hello`. Other projects take the old path unchanged.

- `base-restore` is declared `person_says=True` (UX review round 1, 2026-10-17), showing a verb that is the person's decision: an agent's confirm never runs it.
- `noncedemo` is gone with the nonce service, BASE-050: work is handed to an agent over ACP, the hand-off as its first prompt and its identity in `METAFORM_ROLE`, `METAFORM_SESSION`, `METAFORM_WORK` and `METAFORM_NODE`, or by its ticket id, so hello has no nonce to show. `metaform <nonce>` no longer runs anything.

- Public chassis services, BASE-004 and QUAL-016: `basedemo` reads shared home/project, layer, query and record conversion services and shows project backups and the removal preview. `base-restore [name]` restores a backup and `base-remove` removes an empty project's registration, both with the existing `Verb.caution` confirmation. Existing `follow` demonstrates `Context.listen`. These examples keep user modules on the same public services as shipped modules.

- Public module-owned DAO operations: `Module.data` declares `Data` with named `Operation` handlers, record contributions and item-write contributions. `DataTx.tables()` joins an operation's metaform tables to its current transaction. Hello's existing `visit` uses `count_visit`; the template includes `data=`. `Table.from_sql` adopts an existing table layout, with persisted `on_remove` rules and module-owned historical upgrade callbacks.

- A module's long-running process hears `map.changed` published in other processes, BASE-053: `ctx.listen(handler)` returns a `Listener`, a loopback port recorded under the home's `run/listeners`, and the bus hands each `map.changed` to every listener of another process, one more entry each in the deliveries. The handler runs in the listener's thread; close the listener when the process is done. The web module's `/api/notify` and its subscriber, and dispatch's subscriber and `changed` request, are gone. hello's `follow` shows it.
- A module's own fields on a work record, BASE-035 and STORE-045: hello's `todo` keeps how many names it had greeted in its table `todos`, keyed by the work id, and `MODULE.work_read` shows it as `{"greeted": <count>}` under `hello` in `metaform map work id=<id>`. hello's tables are version 2; a store at version 1 gains `todos` and keeps its visits.
- hello's own tables, STORE-045: `MODULE.tables` declares `visits`, beside the map, and `notes`, in the project's store; `visit` counts a name in one transaction, `note` keeps a note, and `notes` reads them through the index on `at`. A clear of the project removes the visits and keeps the notes.
- hello's `noncedemo` replaces `task`, `brief` and `finish`, BASE-050: one verb is the entry and its nonce's function, keeps its step in the nonce's value, and closes one nonce to hand on another. The words after a nonce that name none of its module's commands reach the nonce's function, so `metaform <nonce> next` runs it with `next`; a function that declares no nouns still refuses them.
- hello shows each public import once: `ctx.say` in `count`, `ctx.publish_async` in `welcome`, `ctx.spawn` in `later`, `Stop` in `greet-favorite`, `start` and `stop` in `uptime`, `Module.default` as `history`, `settings.number` as `--times` in `repeat`, `settings.items` as `--friends` in `greet-friends`, and `save_report`, `feedback`, `list_reports` and `read_report` in `report`, `feedback`, `reports` and `read-report`, BASE-019.
- The nonce service, BASE-050: a module imports `metaform.nonce` and requests a nonce with `nonce.request(module, function, value)`, where the function is one of the module's verbs. An agent runs `metaform <nonce>` for what that verb returns, `metaform <nonce> help` for the module's commands, and `metaform <nonce> <command>` for one of them; inside the verb `nonce.current()` is the record, `nonce.update` changes the value or the function the next run is sent, and `nonce.close` ends it. hello's `noncedemo` shows it.
- Work records, MAP-046 and STORE-042: the condition of an element or a join, a subtype join included, is its own record, apart from the map, written by any module through `store.add_work`, `store.edit_work` and `store.finish_work` and read with `store.work`; every element and join read carries `open_work`. The `flag` and `flag_note` fields of elements, joins and subtypes are gone. helloworld's `todo` and `done` show it.
- An element is its address, `name_length` and role, MAP-012 and STORE-009: `store.add_element(layer, address, name_length=, role=, refs=, extra=)` writes no name and no descriptor item, `Element` has no `name` and no `descriptors`, and every element read returns `reading` and `short_name`. The project's name for a functionality is the join's `name`: `store.add_join(..., name=)`, and `store.add_subtype(..., name=)` for the subtype join, MAP-020. An element recorded again at an address it held before is the same element, with everything attached to it, STORE-009.
- A subtype is a join of type `subtype`, MAP-030 and STORE-011: `store.add_subtype(layer, join, address, ...)` writes a join inside its parent join that holds the element at `address`, an ordinary element record. Its node is `Node('join', join_id)`; the `subtype:` node form is gone. `store.edit` and `store.correct` move a join with `receiver`, `provider` or `parent`, and never move an element, MAP-003 and MAP-015.
- `store.where(address, full=False)` is one read of an address: the element, what relies on it, what it relies on, the subtype joins inside those joins and the one holding it, its open work records and the layers in context at it; its plain data leaves out ids and empty fields unless `full`, STORE-025.
- Nothing a module sends is refused for its content, BASE-044: a ref whose key or value is not text is kept in the record's `extra` under `refs` with a notice, STORE-012; over MCP a `str` noun or a text setting sent another JSON value reaches the verb as its JSON text with a notice, BASE-035 and MCP-005.
- The topic `map.changed`, `{project, base_id}`: the chassis fires it after any command that changes a project's map, and the web server after the page's own writes, so a module does nothing to announce its writes and any module can subscribe; the web module passes it to its server, which pushes it to each open page, VIEW-018. A module publishes it itself only for work done outside a command, in a spawned task. helloworld's greeting shows it.
- Nothing polls for a change and nothing a person or an agent waits on blocks behind slow work, QUAL-015; what happened is published.

## 0.3.0

- `Verb` gains `transport`: a transport verb, such as `mcp serve`, runs whatever the folder's command surface, CLI-022 and MCP-004.
- The common base gains `tool_arguments` and `setting_value`, which check a tool call's arguments as the command line does, MCP-005; `on_this_system`, BASE-016; and `feedback`, `save_report`, `list_reports` and `read_report`, BASE-045.
- A write that does not fit is stored as given and its result carries `notices`, each with `where` and `message`; only a call that cannot be read raises `Stop`, BASE-044 and STORE-026.
- Elements, joins and subtypes carry `flag` and `flag_note`, MAP-046 and STORE-042.

## 0.2.0

- `Verb` takes `nouns` as `Noun` records and `switches` as setting keys; `Adverb` is gone, CLI-012 and BASE-035.
- `Context` carries `project`, `store`, `nouns` as a dict, `switches`, `surface`; `Context.data` is gone, keep data as a layer through `ctx.store`, STORE-022.
- `Module` gains `start`, `stop` and `status`; `Status` adds status lines and one notice, BASE-018 and BASE-035.
- A module declares `SHIPS_DISABLED` and `DEPENDENCIES` as literals, read before import, BASE-015 and BASE-017.
- A verb may declare `supported_os` and `surfaces`, BASE-016 and BASE-035.
- A verb returns its result; the CLI and MCP show the same data, BASE-036.

## 2026-10-18

Added authored role providers, owning prompt rendering, generated duty versions and persistent per-agent context epoch receipts. Documented response-boundary acknowledgements and count revisions.
