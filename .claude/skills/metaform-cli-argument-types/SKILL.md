---
name: metaform-cli-argument-types
description: Use when a CLI or MCP argument is compared or stored.
category: development
---

# Metaform CLI and MCP argument types

Values from `metaform` CLI and MCP calls arrive as text. Normalise them before any equality test or branch.

- Convert numeric fields such as `name_length` through the module's shared helper (`_whole` in the intake module) before comparing with stored integers. A raw `'2' == 2` comparison silently takes the wrong path.
- Compare ref lists as normalised `(key, value)` pairs, not as raw objects.
- A verification pass that gives back the values already stored must write nothing. Skip the write when the held item already matches, or the finished base's layer bytes change.
- Test each branch with a case where the argument arrives as text, not only with Python values.
