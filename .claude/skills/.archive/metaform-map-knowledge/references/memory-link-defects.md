# Defects that block memory relations (2026-10-15 investigation)

- `create_relations` with `node=` refuses any end not joined at that node (src/metaform/modules/memory/__init__.py:690-695). The "Entity with name X not found" it returns does not say the entity exists at another node.
- Relating without `node=` prints "no node will show" the relation and tells the agent to pass node or address (__init__.py:578-584, 703-706). Passing node gets the relation refused. Item reads and the memory network do show cross-node relations, so the notice is wrong.
- The memory instructions say "Never read or search the whole graph" (src/metaform/modules/memory/resources/prompts.xml:40). That removes the usual way an agent finds memories at other nodes.
- `create_entities` with an existing name at a node joins that entity there and adds observations (__init__.py:627-637). This is the only path to one memory joined at several nodes, and no agent-facing text describes it.
