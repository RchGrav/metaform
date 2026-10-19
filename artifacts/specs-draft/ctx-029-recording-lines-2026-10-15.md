# CTX-029 recording lines: drafts for the owner (code.store.memory#3, 2026-10-15)

Each line below replaced the 2026-10-11 sentence "Use Metaform's memory tool to store what you learn under the
functional namespace of your assignment, …" or a line that asked to record what is learned without the split between
memory and knowledge. All are in the tree now, each marked a draft in its comment. The owner approves, rewords or
replaces each (open question 4).

| Where | Draft wording |
|---|---|
| dispatch `record` (full brief, read on demand) | +> Record what happened in the work as memory at the ticket's node, `metaform memory create_entities '<entities>' node=<the address under at in the ticket read>`, or for a ticket on a join, receiver=<its receiver> provider=<its provider> in place of node; and what is now known to be true of the project in the map's knowledge layers, as steps 5 and 6 of the memory prompt say. |
| dispatch `on_ticket_done`, `on_stopped_open`, `on_failure` | Record what happened in the work at `<node/>` as memory, and what is now known to be true of the project in the map's knowledge layers, as steps 5 and 6 of the memory prompt say. |
| dispatch `work_record` (after the work sentence in the first turn) | Record what happened in the work at `<node/>` as memory, and what is now known to be true of the project in the map's knowledge layers, as the memory prompt says. |
| memory `orient` | 2. Read the memories on that element, which map where lists. Record what happened in the work there as memory, and what is now known to be true of the project in the map's knowledge layers, as steps 5 and 6 of the memory prompt say: metaform instructions memory. |
| memory `connect` (fits the 2,048-character connect message) | – memory: read and record what happened in the work at a node, on its RE |
| memory `locked_read` (new, CTX-023) | LOCKED: every agent reads this memory and none can change or delete it; only the person unlocks it. |
| memory Module `purpose` | A graph of entities, observations and relations, the MCP reference memory server's, kept apart from the map and tied to its nodes: what happened in the work at each node. Give node to work with the memories at a node of the map; leave it out for the whole graph. Record there what happened in the work; what is now known to be true of the project goes to the map's knowledge layers, as the memory prompt says. Details: metaform help memory. |
| memory `create_entities` summary | Record what happened in the work at a node of the map: new memory entities with their observations. What is true of the project goes to the knowledge layers. Without node, they go in the memory graph joined to no node. |
| map Module `purpose` (its last sentence) | Record what happened in the work at a node with the memory tools, and what is now known to be true of the project with knowledge, naming the layer on every call: create it, add, edit and remove its objects one at a time, and finish it when the task is done. |

Kept, as CTX-029 says: memory's rule "Record each memory at the RE whose goal it serves, never at a PE that provides
for it." Not listed by CTX-029 and left as written: the chassis guide's step 3, "Record on the map what you learn and
decide as you work." (`src/metaform/resources/prompts.xml:69`).

## Record lines for the owner to amend (the code is the reference)

- CTX-022 Status: "Locking is the exception and is not built": built now.
- CTX-023 Build: "To build. There is no lock …": built: tables version 7, `lock`/`unlock` on the command line and the
  page's memory panel, refused under an agent's `METAFORM_ROLE`.
- CTX-025 Build: the end check, the relation narrowing and `_unshown` are changed; the far end of a cross-node relation
  in `read_graph` is named by its entity name, not yet cited as `<address>#<n>  <title>` (the `#n` read cites it).
- CTX-026 Build: built as `<instructions>` with `<instructions_unassigned>`; `metaform_instructions module=memory`
  still returns the element unfilled, outside the prompt store (chassis `instructions.py`), a follow-up.
- CTX-028 Build: the worker's first turn is built (`runner.handed`); the MCP push, the show-once key and the
  compaction remain with code.adapter.context#4, #5 and code.dispatcher.agent#41; the first turns of the system, talk,
  sentinel and prep agents with code.dispatcher.agent#40.
