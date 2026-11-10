# Metaform, the Node form

This folder holds the Node form of Metaform. It gives an agent the one tool, `project-map`, over stdio MCP, with the commands, answers and refusals of the Rust form. It stores its data in SQLite as a structure of arrays. The design is `metaform/docs/designs/sqlite-forms.md`; it carries out `SPEC.md` R-4.6.

The form is TypeScript that Node 26 or later runs directly. It has no build step and no dependencies: it uses only Node's built-in modules, and `node:sqlite` for the store.

## Start

Give the commands from the repository's root.

```text
node metaform/node/src/main.ts mcp  [--home DIR] [--project DIR]
node metaform/node/src/main.ts call [--home DIR] [--project DIR] '<json command>' | -
node metaform/node/src/main.ts projects [--home DIR]
```

- `mcp` serves the tool on stdin and stdout for an agent harness, until stdin closes. `--project` defaults to the current folder.
- `call` performs one tool command and prints the answer. `-` reads the command from stdin. The exit status is 0 for an answer, 1 for a refusal and 2 for a usage error or a store failure.
- `projects` prints every project registered in the home: its id, name and folder.

The home is the folder the form writes under. It is `--home`, or `METAFORM_HOME`, or `~/.metaform-sqlite`. The form writes nothing into a project's own folder.

An example:

```text
node metaform/node/src/main.ts call --project . '{"map": {}}'
```

## The store

```text
<home>/store.format              one line: sqlite-soa 1
<home>/metaform.db               the project registry
<home>/projects/<id>/project.db  one project's maps
<home>/projects/<id>/source.txt  the project's folder
```

A project's database has one narrow table for each field (`f_<name>`) and for each layer (`l_<name>`), keyed by element. No table holds an element as one record. A write is one transaction that stores only the difference the command made. The design document, sections 3 and 4, gives the tables and the steps of a write.

The form refuses a home whose `store.format` holds anything else, and a home that has files and no `store.format`. The Rust form's home has another format and is refused.

There is no server. Each agent's process opens the database itself, and SQLite's write lock puts the writers in a line. A write that waits more than five seconds for the lock gets the answer `INTERNAL_ERROR`, which says that the command stored nothing.

## Checks

```text
python3 metaform/conformance/run.py --form node    from the repository's root
npm test                                           from metaform/node
```

- The conformance check performs every recorded case through this form's MCP server and compares each answer with the Rust form's recorded answer, key order included. It establishes nothing about inputs the cases do not hold.
- `npm test` performs `node --test`, which finds `test/store.test.ts`. The five tests cover the store: the layout of the tables, writes by several processes at once, a writer ended with SIGKILL, a refused write, and the format marker. The ended-process test does not establish survival of power loss.

## What this form does not offer

These differences from the Rust form come from the design document, section 2.

| Subject | Rust form | This form | Reason |
|---|---|---|---|
| Change announcements (R-4.10) | Pushed to subscribers after each commit | Not offered. The MCP capabilities do not list `resources`. | A process cannot learn of another process's commit without polling. |
| Graph workspace | `metaform gui` | Not offered | The workspace's host needs change announcements. |
| `instructions` in the `initialize` answer | A text that tells the agent about `metaform gui` | Not given | The text is about the graph workspace, which this form does not offer. |
| Specification export and import (R-6.28) | `metaform specification` | Not offered yet | It is a CLI command, not part of the tool. It can be ported with no change to the store. |
| Maps that belong to no project | `--map NAME` | Not offered | The design's command line has `--home` and `--project` only. |
| Settings | `metaform settings`, `set`, `unset` | Not offered | The settings belong to the Rust form's server. |
| Schema check | The shape check, then the JSON Schema files | The shape check only | The shape check gives every message an agent reads. |
| Fair queue for writes (R-4.7) | The server's writer serves clients in turn | SQLite's write lock, which is not first come, first served | Under heavy writing by many processes, one process can wait longer than another. |
| Numbers | `1.0` stays `1.0` | `1.0` comes back as `1`; a whole number above 2^53 loses digits | JavaScript has one number type. A caller must not rely on the difference. |

## Source files

Each core file ports the Rust module of the same name in `metaform/rust/crates/metaform-core/src/`, function by function.

| File | What it holds |
|---|---|
| `src/shape.ts`, `names.ts`, `rules.ts`, `model.ts`, `commands.ts`, `reads.ts`, `refusal.ts`, `specification.ts` | The ports of the Rust core modules. |
| `src/json.ts` | JSON values that keep the order of an object's keys, with a parser and a writer. |
| `src/text.ts` | Text operations and a sorted map that give what Rust's standard library gives. |
| `src/tool.ts` | The tool's definition from `metaform/mcp-tools.proposed.json`, and `Presence`, which makes `goto` deliver each part of a summary sheet once per connection. |
| `src/mcp.ts` | The stdio MCP server. |
| `src/store.ts`, `registry.ts`, `database.ts` | The home and its format marker, the project registry, and a project's database. |
| `src/main.ts` | The command line. |
