# Metaform, the Python form

This folder holds the Python form of Metaform. It gives an agent the one tool, `project-map`, over stdio MCP, with the commands, answers and refusals of the Rust form. It stores maps in SQLite, laid out as a structure of arrays: one narrow table for each field and each layer. It uses the Python standard library only.

The design is `metaform/docs/designs/sqlite-forms.md`. The requirement is `SPEC.md` R-4.6.

## Start it

The form needs Python 3.12 or later. Put this folder on `PYTHONPATH`:

```sh
export PYTHONPATH=metaform/python

python3 -m metaform mcp  [--home DIR] [--project DIR]    # stdio MCP for an agent harness; DIR defaults to .
python3 -m metaform call [--home DIR] [--project DIR] '<json command>' | -
                                                         # one tool command. Exit 0 ok, 1 refused, 2 usage error.
python3 -m metaform projects [--home DIR]                # every registered project: id, name, folder
```

The home is `--home`, or `METAFORM_HOME`, or `~/.metaform-sqlite`. The form makes the home on first use. The Node form uses the same store format, so either form can open a home the other made. The form refuses the Rust form's home, because that home has another format.

An example:

```sh
python3 -m metaform call '{"add": {"code.engine.game": {"technical_name": "game engine", "name": "Quake core", "role": "Definitive"}}}'
python3 -m metaform call '{"map": {}}'
```

## Perform its checks

```sh
python3 metaform/conformance/run.py --form python
PYTHONPATH=metaform/python python3 -m unittest discover -s metaform/python/tests
```

| Check | What it establishes |
|---|---|
| The conformance check | The form's answers equal the Rust form's recorded answers on every recorded step, in value and in key order. It establishes nothing about commands the cases do not hold. |
| `test_layout_is_one_table_for_each_field_and_layer` | Each field and each layer has its own table, no row holds two of an element's values, and an appended record writes one row. |
| `test_processes_that_write_at_once_all_have_their_writes_kept` | Four processes that write one map at the same time all have every acknowledged write kept. |
| `test_an_ended_process_loses_no_acknowledged_write` | After a writing process is ended with SIGKILL, the database opens, every acknowledged write is present and no element is half written. It does not establish survival of power loss. |
| `test_a_refused_write_stores_nothing` | A refused write leaves every table as it was and makes no new table. |
| `test_a_home_with_another_format_marker_or_none_is_refused` | The form refuses a home with another marker, and a home with files and no marker, and writes nothing there. |

## The source files

Each file names the Rust module it ports, so a reader can compare the forms file by file.

| File | Rust module | What it holds |
|---|---|---|
| `shape.py` | `metaform-core/src/shape.rs` | The check of a command's shape |
| `names.py` | `metaform-core/src/names.rs` | Address rules, snake_case and camelCase |
| `rules.py` | `metaform-core/src/rules.rs` | The `technical_name`, `name`, `role` and layer-value rules |
| `model.py` | `metaform-core/src/model.rs` | The map, an element and an effect |
| `commands.py` | `metaform-core/src/commands.rs` | `add`, `update`, `delete` and the order of checks |
| `reads.py` | `metaform-core/src/reads.rs` | Addressed reads, raw dumps, `map`, `orphaned`, `goto` |
| `refusal.py` | `metaform-core/src/refusal.rs` | The error codes and the refusal |
| `specification.py` | `metaform-core/src/specification.rs` | Layer definitions and Markdown blocks |
| `tool.py` | `metaform-server/src/tool.rs` | `Presence`: what `goto` already delivered on this connection |
| `store.py` | `metaform-store/src/lib.rs` | The home, the format marker, one transaction for each command |
| `registry.py` | `metaform-store/src/registry.rs` | The project registry and the project id |
| `tables.py` | `metaform-store/src/graph.rs` (its role) | The SQLite tables: load a map, store an effect as a difference |
| `mcp.py` | the `rmcp` crate (its role) | The stdio MCP server |
| `values.py` | `serde_json` and the Rust standard library (their role) | JSON and text handled as the Rust form handles them |
| `__main__.py` | `metaform-server/src/main.rs`, `call.rs` | The command line |

## What this form does not offer

These differences from the Rust form come from section 2 of the design.

- **No server.** Each agent's process opens the database itself. SQLite's write lock puts the writers in a line.
- **No fair queue.** SQLite's line for the write lock is not first come, first served. A command that waits more than five seconds for the database answers `INTERNAL_ERROR` and says that nothing was stored.
- **No change announcements (R-4.10).** The server does not offer the `resources` capability. A process cannot learn of another process's commit without polling, and polling is ruled out.
- **No graph workspace.** `metaform gui` needs change announcements.
- **No specification export or import (R-6.28) yet.** They are CLI commands, not part of the agents' tool.
- **No JSON Schema check.** The hand-written shape check gives every message an agent reads.
- **No `serve`, `settings`, `set`, `unset` or `--map`.** The design's command line has `mcp`, `call` and `projects` only.
- **Numbers.** A whole number in a JSON command, such as `3.0`, stays `3.0` here, as in the Rust form. The Node form reads it as `3`. A caller must not rely on the difference.
