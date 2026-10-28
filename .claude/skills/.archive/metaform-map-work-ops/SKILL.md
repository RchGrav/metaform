---
name: metaform-map-work-ops
description: Use when writing ticket progress via map_work op=step.
category: development
---

# Metaform map_work operations

Progress on a ticket goes through `map_work` with an explicit `op`. There is no `note` op.

- Valid ops: `list`, `glyphs`, `add`, `edit`, `take`, `plan`, `step`, `move`, `distribute`, `done`, `remove`. With `id=` and no `op`, the call only reads the ticket.
- Record progress with `op=step`, `id=<ticket id>`, `said=<one line of what changed and what is next>`.
- `text=` is not a step argument. A step sent with `text=` is answered "Notice: text: map work has no noun text; it was ignored", so the words are lost; put every word in `said=`.
- Reading a ticket: `map_work id=<id>` with `view=full` gives the full record, `view=count` gives a count. A `fields=` list naming ticket keys (`id`, `status`, `steps_done`, `map.item`) is refused: "No record here holds id, status, steps_done, map.item; they hold number, said, at." Use the view arguments, not `fields=`, and read the ticket's `done`, `resolution` and `steps_done` from `view=full`.
- When a `map_work` call is refused, read the error's "Next:" line and call with the arguments its schema lists; do not retry the same op.
- `op=done` on a ticket whose fault is already fixed on main does not close it when the fix is unproven: the reply is "fix landed, watching: this ticket closes only with proof that the fix held, so it stays open in its column until then." Put the before/after proof in the resolution and expect the ticket to sit in "fix landed, watching" until that proof is run; do not re-send `done` to force it closed.
- Closing a ticket takes `op=done` with both `resolution=` and `why=` on the first call. There is no `close` op: `op=close` is refused with "'close' is not a work operation: op=list, glyphs, add, edit, take, plan, step, move, distribute, done or remove". A `done` with `resolution=` and no `why=` is refused with "The resolution has no why. Next: add why", so send `why="one line saying why it was resolved this way"` with the resolution. A done that reads "its resolution was kept" on a record already closed changes nothing.
