---
name: metaform-memory-observations
description: Use when writing or deleting Metaform memory observations.
category: development
---

# Metaform memory observations: one fact each, checked after every write

Write each observation as one sentence stating one fact about the entity. The store refuses an observation holding two facts (a semicolon, a line break or a second sentence) and names the observation it refused.

- Send the delete and the add as separate calls. In one batch the delete landed and the add was refused, which left the entity without its new lines. Read the add's reply before anything else, and re-send a refused add alone once it is split.
- To replace a stale line, read the entity's current text with `open_nodes` for its exact wording, delete that text, then add each corrected fact as its own observation.
- Keep only facts that will still hold after the next change. Dated history of a fix belongs in the ticket note, not in the memory.
- Pass `node=` on every call. Shapes: `memory_add_observations` takes `observations: [{entityName, contents: [...]}]`; `memory_delete_observations` takes `deletions: [{entityName, observations: [exact old text]}]`.
