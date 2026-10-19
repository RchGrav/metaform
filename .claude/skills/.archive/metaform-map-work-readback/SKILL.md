---
name: metaform-map-work-readback
description: Use when map_work reads a ticket's resolution or steps.
category: development
---

# Reading a ticket's result through map_work

Work records hold `number`, `said` (each step), and `at`. They do not hold `done`, `resolution`, `steps_done`, `steps` or `outcome` as field names, so a field-filtered read that asks for them errors.

To see a finished ticket's resolution, call `map_work` with the work id and `view=full`, and use `must_contain` to narrow to the record that carries the text you need. Read steps from `said`, not from a `steps` field.
