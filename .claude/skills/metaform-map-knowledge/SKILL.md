---
name: metaform-map-knowledge
description: Use when recording memories, layers, refs or file links.
category: development
---

# Metaform map knowledge: layers, memory and refs

Put each piece of knowledge in a layer named for its element, each memory at the address it concerns, and each file linked before it is written. The store accepts some bad shapes silently, so read the response's `notices` and `on` field back after every write.

## Layers: named for their element
- A layer is named by its element's short name: the Address reversed and cut to `name_length` segments. The cpp best-practices layer is named `cpp`, never `code.cpp.best_practices`, `unnamed-<time>` or a free label. The store refuses the six project roots (code, document, media, data, upstream, downstream).
- Always pass `layer=` on a knowledge write. Without it the value lands in `unnamed-<timestamp>`. Agents do not create layers unless the person asks; then `op=create` needs `mutable=true hideable=true`.
- Add the element first into the named layer, then the property. Run `metaform map layers` before a spec or ticket names a layer.
- A property link settles at the longest common prefix of its addresses and never moves toward the leaves. Detail: `references/knowledge-placement.md`.

## Memory: atomic facts, linked to what they concern
- Search or open the existing entity first and add an observation to it, rather than a near-duplicate.
- One fact per observation, in one sentence. Split semicolons and second sentences; paragraph observations get purged. The store checks this on the whole call: any observation holding more than one fact refuses the call and lists the offenders (`N observation(s) hold more than one fact`). Split each one and send the same call again; do not retry it with the semicolon pair intact.
- Each new entity needs a `title` and a `why`. Relate it to the entities it concerns with `create_relations`, in active voice.
- Read named entities by name. A whole-node graph read can exceed the tool's output limit.
- When code makes an observation false, delete the old text and add the new one, dated and with its line cited. Read the cited line first.
- Memory is not knowledge, and no tool links a memory to a layer yet, so put a memory at the node of the knowledge it concerns. Cross-node blockers: `references/memory-link-defects.md`.

## Refs and file links
- A `ref_id` is dotted segments of letters, digits and underscores; for code, its qualified name (`metaform.data.refs`). Hyphens and spaces are refused, so keep a title in `why=`.
- A ref is named `{ref_id}@{address}`, and it never moves. Refs are not properties: never justify a ref's place by transitivity or the moving-link rule.
- Link every file before its first edit, including a script that writes it: `dispatch_link file=<path> node=<Address> ref=<ref_id> why=<why>`. Never link refs through `map knowledge op=add-element`, which replaces the refs last linked at that element.
- Run `metaform map where` on the Address first. `dispatch_link` at a missing Address creates the element. Never create an element just to hold refs.
- To undo a mistaken element, remove its ref from the sources layer by id first, then remove the element with `map refine` (remove true). Removing the element first orphans the ref.
- Ref naming, derived second names and the history of the rule: `references/ref-links.md`.
