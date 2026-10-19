---
name: read-metaform-ticket-state
description: Use when reading a Metaform ticket's state or fields.
category: development
---

# Read a Metaform work record with its real fields

Run `uv run metaform map work id=<address>#<n> --json` (or `id=<work_id>`) and read the fields the record actually has: `done`, `held`, `resolution`, `task`, `note`, `taken`, `taken_by`, `said`, `steps`, `steps_done`, `map`, `dispatch`, `orchestration`. The output is wrapped in `results`, and a list may hold several records.

- There is no `column` or `state` field on the work record. Reading them returns None and looks like a missing ticket. Use `done` (a timestamp when closed) and `held`.
- A ticket closed as a duplicate has `done` set and `resolution` starting with "Duplicate of ...". Read `resolution` before assuming the work was dropped.
- Pipe through `python3 -c` with `r.get(k)` for only the keys you need, so the output stays short.
