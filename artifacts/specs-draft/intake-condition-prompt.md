# Proposed: the intake's `<condition>` field text

For Rich. Ticket 97085c0e (code.processor.intake#d), 2026-10-15. Nothing here is in the code: `src/metaform/modules/intake/resources/prompts.xml` holds your wording as it was at commit b3d942e.

## Where it is

`src/metaform/modules/intake/resources/prompts.xml`, the `<condition>` element under `<fields><element>` and again under `<fields><purpose>`. An agent recording an intake reads it as the description of the `condition` argument of `intake_element` and `intake_purpose`.

## Your text now (b3d942e, restored)

> MISS, BKN or OK, as the intake procedure marks a part, or broken, missing, trouble or ok: MISS and missing are stored as missing, not built yet; BKN and broken as trouble, which needs a note saying what is wrong and what corrects it; OK as ok. Recording it again replaces the last.

## What changed in the code since

- OK no longer opens a work record (ticket 9de74d83). Each one used to make an empty card on the board.
- OK closes any finding the intake recorded at that part that no agent has taken.
- OK is kept at the part as an item of the `checked` layer, so `intake show` reads `ok` back (ticket 97085c0e).
- A note given with OK is kept as a plain note in the critic layer, as a note with no condition is.
- A later MISS or BKN at the part takes the `checked` item away.

## Proposed text

If you want agents told this, the sentence about OK could read:

> OK as ok, the part's normal state: it opens no ticket, closes a finding recorded there before, and is kept as a check that the read-back shows; a note given with it is kept as a plain note.

The rest of the element would stay as written. Your current text is still accurate, since OK is still stored as ok. The proposal only adds what happens around it.
