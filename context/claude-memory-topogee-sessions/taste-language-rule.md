---
name: taste-language-rule
description: "Planned project-wide language rule set: TASTE, a custom ASD-STE100 subset for tickets, context and agent communication; founder rules in docs/taste.md are the starting point"
metadata:
  node_type: memory
  type: project
  originSessionId: 64f72fa6-1e3a-44a5-9ed3-c89e8167ad8a
  modified: 2026-11-02T12:27:15.622Z
---

The system will have a project-wide rule set for how it uses tickets and context. It is TASTE, Topogee Agentic Simplified Technical English, a custom subset of ASD-STE100.

**Why:** Models paraphrase, and they increasingly communicate through assumed shared understanding. In this system agents talk to each other and context follows the functional topology, while an agent cannot tell its own context from shared context. Fixed language rules reduce the drift that this causes.

**How to apply:** The founder's 10 writing rules in `docs/taste.md` (2026-11-02) are the starting point, to be customized from there. Whether TASTE covers the authored intake method is undecided.

Rules the founder has stated:

- The same term is used for things that are the same.
- Industry terms are used when reasoning on functionality.
- The `name` field holds the project's own name, not the industry name. Since 2026-11-02 the spec says they must differ: `name` may never equal `technical_name`. Example: `document.dialect.project` with name_length 2 reads as Project Dialect, the full reading is Project Dialect Document, and the name is TASTE.

The `name` rule exists because agents collapsed that field into the industry name. `flask_intake.json` (2026-10-29) has 29 of 29 names equal to the reversed short name.
