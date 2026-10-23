---
name: metaform-memory-graph-reuse
description: Use when joining or searching Metaform memory entities.
category: development
---

# Reuse existing memory entities; search one word at a time

Before creating a memory entity, find the one that already exists. If it exists, index it at the new node with `memory_join` (one memory, two indexes) instead of `memory_create_entities`, which copies it.

- Look up first: `memory_joins` with `entity=<name>`, then `memory_search_nodes` with one distinctive word.
- Search with a single word per call. At a node, multi-word queries such as `model picker catalog runtime` and `facilitator runtime choice agent model effort` returned `{}`, while the single word `model` and an exact entity name returned results. An empty `{}` on a phrase means retry with one word, not that nothing exists.
- Index a found entity at the node: `memory_join` with `entity` and `node`. The reply gives the item id at that node.
- Relate it to the node's functional element with `memory_create_relations` when the specialist serves that element, for example `repairs settings pickers for`.
- Read unread notices with `memory_read_unread` for the node before acting on it.
