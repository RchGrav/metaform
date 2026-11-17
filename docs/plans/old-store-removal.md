# One map: removing the old store

Status: plan, 2026-11-17. Asked for by the person: "clean up the CLI commands and anything else pointing to the old map;
we have dual systems in play right now and that's very confusing."

## The problem

Two stores hold a project's map and tickets, and different parts of Metaform read different ones.

- **The project store** (new, LadybugDB, one database per project under `~/.metaform/maps`, held by one service per
  home). The page and the MCP `project` tool read and write it: the map, and the overlays `wants`, `tickets` and
  `memories`. The intake records into it. The board creates, moves and closes tickets in it.
- **The old store** (SQLite, under `~/.metaform/projects/<project>/`). Every `metaform map` verb reads and writes it,
  and so do dispatch, the web server's older reads, memory, tasks, autoticket, paperclip, roundtables, A2A and fork.
  For `metaform` it holds no elements.

There is no command line for the project store: it is reached only through the `project` tool and the page.

**What it costs, seen on 2026-11-17.** The system agent ran `metaform map where` and `map children`, got nothing
back, and told the person the map was empty, when the page showed it full. It then filed a ticket with `metaform map
work`, into the old store, so it is not on the board the person looks at. Agents are sent to the old commands by the
prompts and skills that name them (below).

## What still uses the old store

Calls to the old map and ticket store, by file (counted 2026-11-17; tests left out):

| Calls | File | Uses it for |
|---|---|---|
| 45 | `modules/map/__init__.py` | every `metaform map` verb |
| 17 | `modules/dispatch/__init__.py` | work records: start, wait, claims, merges, notes |
| 12 | `modules/web/server.py` | older page reads beside `project_map.py` |
| 8 | `modules/memory/__init__.py` | memories at map nodes |
| 7 | `modules/hello/__init__.py` | the demonstration module |
| 5 each | `modules/tasks/skill_layer.py`, `modules/paperclip/__init__.py` | skills at nodes; Paperclip issues as tickets |
| 4 each | `settings.py`, `archive.py`, `modules/mcp/a2a.py`, `modules/fork/review.py`, `modules/autoticket/faults.py` | |
| 3 each | `modules/roundtables/pipeline.py`, `modules/mcp/a2a_out.py`, `modules/dispatch/runner.py`, `modules/dispatch/merge.py`, `cli.py` | |
| 1 or 2 | `tasks/protocol.py`, `roundtables/__init__.py`, `dispatch/task_sessions.py`, `reports.py`, `roundtables/follow.py`, `roundtables/execution_outline.py`, `map/glossary.py`, `map/around.py`, `dispatch/ticket_merge.py`, `dispatch/serve.py`, `dispatch/orchestration.py`, `agents/__init__.py` | |

Text that sends agents to the old commands (`metaform map where`, `children`, `work`, `find` and the rest):
`.claude/skills/metaform-development/SKILL.md` (18) and its `references/ticket-work.md` (9),
`modules/map/resources/prompts.xml` (6), `modules/map/README.md` (4), `skill/metaform-node/` (5),
`skills/sentinel/references/procedure.axiom` (2), `modules/dispatch/README.md` (2).

## The `map` verbs, by what the project store has for them

- **The map itself:** `where`, `children`, `roots`, `element`, `joins`, `identity`, `find`, `search`, `markdown`,
  `mermaid`, `xml`, `refine`. The project store holds the map; these read it through the project engine.
- **Tickets:** `work`, `boards`, `item`. The project store has the `tickets` overlay, which the board already uses.
- **Questions and messages for the person:** `ask`, `reply`, `reopen`, `messages`. No overlay yet.
- **Layers and knowledge:** `layers`, `tag`, `untag`, `layer`, `node`, `context`, `links`, `citing`, `knowledge`,
  `select`, `mask`, `clear`, `hide`, `unhide`, `reexamined`. The project store has overlays in their place.
- **Bases:** `bases`, `add-base`, `activate`, `remove-base`, `collapse`, `promote`, `history`. No counterpart yet.
- **Other:** `cypher`, `critic`, `challenges`, `answer`, `approve`, `glossary`, `term`, `guide`. No counterpart yet.

## The plan

**Step 1. Stop the confusion now.** Small, and nothing is deleted.
- Tickets go to one place: `metaform map work` (add, edit, step, close, list) and every module that makes a ticket
  (dispatch, autoticket, paperclip) write and read the `tickets` overlay through the project engine, so a ticket made
  anywhere is on the board.
- The map's read verbs (`where`, `children`, `roots`, `element`, `joins`, `find`, `search`, `markdown`, `mermaid`,
  `xml`) answer from the project store through the project engine, in the same answer shape where it can be kept.
- A `map` verb with no counterpart yet refuses on a project whose map is in the project store, saying so and naming
  the `project` tool, instead of answering from the old store as if it were the map.
- The prompts, skills and READMEs above name the `project` tool, or the verbs that now read the project store.

**Step 2. Move each module onto the project engine,** one module per commit, its tests passing: dispatch (work records
become tickets; also fixes `dispatch wait` on an intake, bug 1), the web server's older reads, memory (onto the
`memories` overlay), tasks, autoticket, paperclip, roundtables, A2A, fork, and `hello` and `template`, which show
module developers the way.

**Step 3. The features with no counterpart,** each by the person's decision: made an overlay of the project store,
or deleted. Questions and messages, layers and knowledge, bases, Cypher, the critic, and the glossary.

**Step 4. Delete the old store's map:** its tables and the code that served them, with the store layout raised once
and existing projects moved (`metaform-store-layout-upgrade`). The old store keeps only what is not the map, if
anything, such as settings and module tables.

## Decisions for the person

1. **Which features without a counterpart to keep** (step 3): questions and messages for the person, layers and
   knowledge, bases, Cypher queries, the blind-spot critic, the glossary. Each kept one becomes an overlay of the
   project store; each dropped one is deleted with its verbs.
2. **The command line for the project store.** Proposed: the `map` verbs that stay read and write the project store,
   so agents and people keep the commands they know, and the `project` tool and the CLI are one engine. The other way
   is one generic command, `metaform project '<command as JSON>'`, the same form as the tool, with the `map` verbs
   removed.

## The project store follows `core/` (confirmed by the person, 2026-11-17)

The person confirmed the Rust store's graph as the structure, from `core/metaform/rust/crates/metaform-store/src/graph.rs`:

```
(Map) -ROOT-> (Element) -CONTAINS-> (Element) -CONTAINS-> (Element) ...   the namespace tree, as edges
(Element) -DEPENDS_ON {why, how, direction}-> (Element)                    wants, as edges
(Element) -HOLDS-> (Record)                                                layer records, as edges
```

Node and edge types, with their properties: `Map(id)`; `Element(key, mapId, address, technicalName, name, role, uri,
status, childMap, extra)`; `Record(key, mapId, layer, ordinal, data)`; `ROOT` (Map to Element); `CONTAINS` (Element to
Element); `DEPENDS_ON(why, how, direction, extra)` (Element to Element); `HOLDS` (Element to Record). The stored form an
agent reads back with `raw dump` is the nested JSON of `core/metaform/intake-example.json`: the project's name on top
with `id`, `name` and `project`, each address segment a level, `refs` a list, and `wants` a list inside the wanting
element.

The Python store built on 2026-11-16 (`src/metaform/project/store.py`) departs from it, seen in a copy of the live
`metaform` map on 2026-11-17:

- Only wants are edges (`Wants`). The tree is not stored: a parent such as `upstream.code.harness` is a separate empty
  node with no edge to its child. There is no `Map` node, no `ROOT` and no `CONTAINS`.
- Overlay records are one node type per overlay (`ov_tickets`, `ov_memories`, ...), tied to their element by an
  address string, not a `HOLDS` edge.
- An element holds one `ref` text, not a `refs` list; there is no `extra`, so any other field is refused.
- The project's `Root` node is unconnected and, for `metaform`, empty.
- There is no `raw dump`, so the stored form cannot be read back in the nested shape.

The commands and answers differ too (2026-11-17, the Rust tests' commands sent to the Python tool): `goto`,
`raw dump` and `help intake` are refused; a root `technical_name` answers `FIELD_MISMATCH` with no remediation instead
of `TECHNICAL_NAME_ALIGNMENT_FAILURE`; an unknown field or overlay records given as an object are refused with no
remediation, where Rust stores the field in `extra` or answers with the corrected list. The role checks match.
