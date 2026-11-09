---
name: open-field-lists-design
description: "Unfinished MCP design the founder asked to come back to: field lists, layer listing and reading one field"
metadata:
  node_type: memory
  type: project
  originSessionId: b09b07b3-bc99-40d2-8e74-5d0c4363eefb
  modified: 2026-11-02T22:22:29.723Z
---

On 2026-11-02 the founder asked to return to this design. It was interrupted by the main database work and is not finished.

- A read with no command names the field it wants: `{".": {"layers": []}}`. It works at any address. An empty `{}` still returns everything. Not built. It needs a change to `mcp-tools.proposed.json`, which is protected.
- `values` and `arrays` list the fields the tool accepts. They act as input validation, and they are left out when layers are listed. `values` are `name`, `name_length`, `role`, `uri`, `status`. The founder said both go on root. The founder said "base was superceded by layers that are the same". The agent's reading of that line is not confirmed.
- `layers` lists the project's own layers, and only listed layers can be created. Each entry will also hold a sentence and grammatical rules for each field. The sentence must read correctly with the field values in it, and it formats a readable dump of the layer.
- `values` and `arrays` define what a dump of `.` returns.
- Intent: limit what a dump of `.` returns, limit which layers can be created, and control which arrays come back when a layer's details are dumped or a layer is included.

The agent suggested moving `values` and `arrays` to the main database. The founder did not agree to that.

The founder said on 2026-11-02: `investigations` and `couplings` are not approved and the names are terrible. The founder said to drop ICE: it was a nice-to-have, not a core requirement, and its value is in question. Settings are the agent's job and go in the global database; do not bring them into intake discussion. The map is for durable knowledge. Ephemeral knowledge goes in a ticket.

Founder's design now lives in `~/brain/Universal Intake & Layer Architecture Documentation Set.md` (2026-11-02). It supersedes values/arrays with root `intake`, `system` and `layers` dictionaries. Settled: `{"orphaned": {}}` returns a bare array, because it is a query; wrapping it in an object is misleading. `technical_name` counts words. `name` must differ from `technical_name`. Roles are the founder's four in `~/brain/roles.md`: Definitive, Supportive, Notable, Divergent. Supportive means coupled, which retires ICE. CQU is an inference term, not a role, and never part of an address.

**How to apply:** Do not treat any of this as decided or built until the founder says so. Removing the `project` field from the schema is a related open item, and it needs the founder's direct word.
