---
name: metaform-memory-upkeep
description: Use when writing or pruning Metaform memory observations.
category: development
---

# Metaform memory upkeep: write, check, delete

A memory is durable knowledge, never momentary status. Before keeping or adding an observation, check its claim against the code it names; delete any observation the code contradicts, in the same pass.

- Every new entity needs `title` (one line: what it is) and `why` (one line: why it is worth keeping). Without both, `memory_create_entities` is refused.
- Write each observation as one fact in one sentence: no semicolons, no line breaks, no second sentence. `memory_create_entities` refuses an observation that holds two facts; split it into one observation per fact and send the same call again.
- Pass `node=element:<address>` on create so the entity is indexed at that node. Without `node` it has no functional association.
- Create before you relate. A refused create writes nothing, so a `memory_create_relations` naming that entity then fails with "Entity with name ... not found". Fix the refusal, confirm the create returned "Recorded:", and only then send the relation.
- An existing name is skipped on create. Extend it with `memory_add_observations`, then index it with `memory_join`.
- Title and why are set only at creation; no memory tool edits them afterwards. To correct a stale title or why, `memory_delete_entities` the entity with `node=element:<address>`, then create it again under the same name with the same observations, `node=` and corrected `title`/`why`. Deleting also removes its joins and relations: re-send each relation, and confirm `memory_joins` shows one join at the node (the recreated join gets a new join_id).
- A fact already held by another entity keeps one home. Do not repeat it.
- When an observation is superseded, delete it with `memory_delete_observations` rather than leaving the old and new side by side.
- Read the node's unread memories (`memory_read_unread`) before maintaining them, and report only what changed.
