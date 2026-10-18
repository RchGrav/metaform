---
name: metaform-tools-behind-catalog
description: Use when Metaform memory or dispatch tools seem missing.
category: development
---

# Metaform tools sit behind metaform_catalog

Most Metaform verbs are not listed up front. Before saying a memory, dispatch or check-in tool is unreachable, call `metaform_catalog` with `tool` set to the verb name and `arguments` as its input (for example `tool: memory_read_unread`, `arguments: {node: ...}`). Only report it missing if the catalog call fails. A deferred metaform tool can also be loaded by its exact name: ToolSearch with `select:mcp__metaform__memory_add_observations` returned that tool at once, after a broad ToolSearch query for memory tools had not surfaced it.

- Each catalog verb takes its own argument shape, and a wrong guess comes back as an error that names the fields the record holds. Relations hold `from`, `to`, `relationType`; not `name`. Entity reads hold `join_id`, `entity`, `address`, `by`, `shows`; not `name` or `entityType`. Open with `view=count` or `view=full` rather than guessing `fields`. Read the error's `Next:` line and retry once with that shape.
- A search that matches nothing returns `{}`, not an error. Treat `{}` as "no match" and check the store before concluding something was deleted.

- A reply by `dispatch_note` to a sender whose session has ended returns "no longer at work"; the reply reaches no one. Do not retry it. Say the reply could not be delivered and put the result on the ticket.
- An "N memories; M unread" notice that repeats after the server reports 0 unread is a stale count. Read once through the catalog, note the mismatch, and move on. Do not keep re-reading each turn.
