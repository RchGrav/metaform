---
name: metaform-dispatch
description: Use when editing dispatch resume or spend budgets.
category: development
---

# Dispatch: resume ownership and spend budgets

Automatic resume and spend caps are the two places dispatch can start paid agents, or reset a limit, by mistake. Guard both, and count live candidates before any change lands.

## Automatic resume runs only for sessions this home started

- Every automatic resume (the supervisor's retry, Stay connected, Call's resumed conversation, automatic recovery) passes over any session row whose `origin` is not this home's `origin()`. Explicit `dispatch resume <id> session=<sid>` stays the only path for other homes' rows.
- Check ownership with `foreign(row)`; never decide from the row's `state` or `how` alone. A dead runner reads as ended, which is not the person's stop.
- Any code that writes a session row sets `origin`: runner take() on insert and on resume, and serve open(). A row seeded by hand for a resume test needs `'origin': module.origin()`, or it is foreign and the test proves nothing.
- Legacy rows (no `origin`, before sessions table version 13) are never resumed automatically. Before landing such a change, count the live candidates in the real home, read-only, and report what will stop resuming.
- Prove the guard with a copied home: copy the home, point `METAFORM_HOME` at the copy, and build a fresh context and `Store` per home. Then mutate the guard in a `/tmp` copy as `verify-guard-test-by-mutation` describes. The copy must start nothing.
- Incident and file map: `references/copied-home-incident.md`.

## Spend lives in the project store

- Write every turn's spend to the project-level `spending` table (dispatch tables version 14), never to a per-metaform table. A base removed from the project takes its rows with it, and the cap resets.
- Write from runner `spend()` and `cost_spent()` into `spending`. Read only through `spend_rows(store, filters)`, which runs `carry_spend` first. `spent`, `session_cost`, `run_of` and `dispatch spend` all go through it.
- The per-metaform `spend` stays declared so older runners still load and write; `carry_spend` moves their rows on every read. Do not gate the carry behind a once-only marker, or an old runner's later rows stay out of the budgets for good.
- A metaform that cannot be read raises. Never wrap a budget read in `except StoreError: continue`; a skipped store is a silent reset.
- Tests seed spend straight into the project table: `Store('proj', module='dispatch').tables()` then `tx.insert('spending', {...})` with the SPEND columns.
- A table cannot change place under its own name, so a move is a new table name plus a carry. Store upgrade rules are in `metaform-development`.

## Every change

- Each change gets a dispatch `CHANGELOG.md` Unreleased entry naming its ticket. A resume-guard change also gets a sentence in the README's "Supervisor and budgets" section; the README's `spend` row changes only when that verb's output changes.
- Running servers and runners keep the old code until restarted; say so in the report.
