# Changelog

Each change to the module contract, newest first, so a module copied from the template can follow it.

## Unreleased

- The words after a nonce, BASE-050: words that name none of the module's commands reach the nonce's function as its words, so `metaform <nonce> next` runs the function as `metaform <module> <function> next` would, with the nonce reached. The function takes them through a noun, `Noun('step', ..., required=False, many=True)`; a function that declares no nouns still refuses them and names `metaform <nonce> help`. hello's `noncedemo` shows it, and replaces `task`, `brief` and `finish`.
- Nonces, BASE-050: a nonce is seven digits, the first never zero. `nonce.reached()` returns the nonce the running command came through, or `None` when it did not come through one, so one verb can be the module's entry and also its nonce's function. A closed nonce and one never issued print exactly `Error: Invalid or Unknown Nonce`. A closed nonce's record is kept, so its number is never issued again.
- The nonce service, BASE-050: a module imports `metaform.nonce` and requests a nonce with `nonce.request(module, function, value)`, where the function is one of the module's verbs. An agent runs `metaform <nonce>` for what that verb returns, `metaform <nonce> help` for the module's commands, and `metaform <nonce> <command>` for one of them; inside the verb `nonce.current()` is the record, `nonce.update` changes the value or the function the next run is sent, and `nonce.close` ends it. helloworld's `task` shows it.
- Work records, MAP-046 and STORE-042: the condition of an element or a join, a subtype join included, is its own record, apart from the map, written by any module through `store.add_work`, `store.edit_work` and `store.finish_work` and read with `store.work`; every element and join read carries `open_work`. The `flag` and `flag_note` fields of elements, joins and subtypes are gone. helloworld's `todo` and `done` show it.
- An element is its address, `name_length` and role, MAP-012 and STORE-009: `store.add_element(layer, address, name_length=, role=, refs=, extra=)` writes no name and no descriptor item, `Element` has no `name` and no `descriptors`, and every element read returns `reading` and `short_name`. The project's name for a functionality is the join's `name`: `store.add_join(..., name=)`, and `store.add_subtype(..., name=)` for the subtype join, MAP-020. An element recorded again at an address it held before is the same element, with everything attached to it, STORE-009.
- A subtype is a join of type `subtype`, MAP-030 and STORE-011: `store.add_subtype(layer, join, address, ...)` writes a join inside its parent join that holds the element at `address`, an ordinary element record. Its node is `Node('join', join_id)`; the `subtype:` node form is gone. `store.edit` and `store.correct` move a join with `receiver`, `provider` or `parent`, and never move an element, MAP-003 and MAP-015.
- `store.where(address, full=False)` is one read of an address: the element, what relies on it, what it relies on, the subtype joins inside those joins and the one holding it, its open work records and the layers in context at it; its plain data leaves out ids and empty fields unless `full`, STORE-025.
- Nothing a module sends is refused for its content, BASE-044: a ref whose key or value is not text is kept in the record's `extra` under `refs` with a notice, STORE-012; over MCP a `str` noun or a text setting sent another JSON value reaches the verb as its JSON text with a notice, BASE-035 and MCP-005.
- The topic `map.changed`, `{project, metaform_id}`: the chassis fires it after any command that changes a project's map, and the web server after the page's own writes, so a module does nothing to announce its writes and any module can subscribe; the web module passes it to its server, which pushes it to each open page, VIEW-018. A module publishes it itself only for work done outside a command, in a spawned task. helloworld's greeting shows it.
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
