---
name: dispatch-spend-budgets
description: Use when editing dispatch spend or budget caps.
category: development
---

# Spend lives in the project store, so removing a base never resets a budget

Write every turn's spend to the project-level `spending` table (dispatch tables version 14), never to a per-metaform table: a base removed from the project takes its rows out of the day, ticket and run budgets, and the cap resets.

- Write from `runner.py` `spend()` and `cost_spent()` into `'spending'`. Read only through `spend_rows(store, filters)`, which runs `carry_spend` first and then reads `spending` once. `spent`, `session_cost`, `run_of` and `dispatch spend` all go through it.
- The per-metaform `spend` stays declared so runners started before version 14 still load and write. `carry_spend` moves their rows across on every read. Do not gate the carry behind a once-only marker: an old runner's later rows would then stay out of the budgets for good.
- A metaform that cannot be read raises. Never wrap a budget read in `except StoreError: continue`; a skipped store is a silent reset.
- Tests seed spend straight into the project table: `with Store('proj', module='dispatch').tables() as tx: tx.insert('spending', {...})`, with the SPEND columns (`session_id`, `seq`, `work_id`, `run`, `day`, `tokens`, `cost`, `currency`, ...).
- A table cannot change place under its name, so a move is a new table name plus a carry. The upgrade check is in `metaform-development` (Store upgrades).
- Each change gets a dispatch `CHANGELOG.md` Unreleased entry naming its ticket. The README's `spend` row changes only when the verb's output changes.
