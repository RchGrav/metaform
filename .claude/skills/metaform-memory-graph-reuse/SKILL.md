---
name: metaform-memory-graph-reuse
description: Use when joining or moving Metaform memory entities.
category: development
---

# Metaform memory placement

A memory is joined to the element that owns the behaviour it describes, never to the element of the ticket that surfaced it.

- Before adding a memory, search for an existing entity (`memory_joins`, `memory_read_unread`) and reuse it rather than creating a duplicate.
- Find the owner from the map (`map_find` on the functional behaviour). Join the memory there with `memory_join`, then remove the wrong join with `memory_unjoin` by its join id.
- A ticket's element holds memories about that ticket's work; a contract of code the ticket merely touches belongs at the code's owner.
- When you add to a node's memory, first merge repeats into one observation and delete observations and entities that are outdated, with `memory_delete_observations` and `memory_delete_entities`.
- Check each observation against the current source before keeping it, and name the receiving node in the ticket step when a memory moves.
- Write one fact per observation, in one sentence. `memory_add_observations` rejects an observation holding a semicolon, a line break or a second sentence; split it into separate observations and send the call again. Use the same rule when a repeat is merged into one observation.
- `memory_create_entities` also rejects an entity without a `title` (one line saying what it is) and a `why` (one line saying why it is worth keeping), and it applies the one-fact rule to every observation in the same call. Pass `node=element:<owner>` on creation, or the entity has no functional index. Build each entity with its title, why and single-fact observations in the first call; a rejected call creates nothing, so retry it whole. `memory_create_relations` fails with "Entity ... not found" until both of its endpoints exist, so create the entities first.
- Through `metaform_catalog`, the call's parameters go inside `arguments`, never at the top level. A top-level `observations` is dropped and the call fails with "add_observations needs <observations>". Pass `observations` as an array of `{entityName, contents}` objects, not as a JSON string. `memory_join` takes `entity` and `node` inside `arguments` the same way.
