---
name: metaform-memory-durable-atomic
description: Use when writing or testing Metaform memories.
category: development
---

# Memories are durable, atomic, valuable facts

A memory is one fact that stays true beyond the session that wrote it and that a later agent at that address is better off knowing. Record one fact per observation. A work log (what was done, tried or decided in one session) is not a memory.

- Before writing, ask: will this still be true after this work, and would a later agent at this address act differently because of it? If not, write nothing. An empty write is correct when nothing durable was learned.
- Knowledge (what an element is, how it behaves, its constraints, medium, style) goes in knowledge layers, not in memory.
- Relate memories to each other with create_relations in active voice.
- Memory reaches an agent on arrival at a node as one line, "N new memories". Never push memory content on every turn, and never force a write.

## Testing

- Mechanics: run only the delivery tests, `uv run pytest -n 0 src/metaform/modules/memory/tests/test_delivery.py`. They prove delivery, not use.
- Use: run one small live ticket at a node that has one real pitfall memory. Check the transcript: did the agent get the one-line notice, read the memory, and avoid the pitfall unprompted? How many characters reached it? Did it write anything, and was that write durable?
