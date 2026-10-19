---
name: metaform-intake-findings
description: Use when editing intake findings, same_as or intake show.
category: development
---

# Metaform intake findings

Record one defect once. When a finding names a defect already open at another part, give `same_as=<address of the element where it is open>` on the second `intake element` or `intake purpose` call. Do not open a second ticket.

Why: text matching cannot find duplicates. Two flask tickets for one defect (35a62198 trouble, 19d75fe3 missing) shared no wording. Only the agent recording the intake knows they are one defect.

Code rules, in `src/metaform/modules/intake/__init__.py`:
- `_same_as` appends the new note to the open ticket, adds the calling part to its links, and closes that part's untaken open finding as `Recorded once in <id>`.
- With nothing open at the named element, the finding is recorded at its own part and a `same_as` notice says so.
- `intake show` marks a linked part with the ticket's condition and `kept_in`, and stops marking it once the ticket is done.
- Field wording lives in `prompts.xml` `<fields>`. `test_each_recorded_field_is_described_once` checks it, so change the words there, not in tool code.
- When behaviour changes, update the intake README and the MAP-046 build note in `specifications/01-map.md`.

Test pattern: replay the duplicate case with `recorded(run, project, ...)` and `Store('timer')`. Assert one open ticket that links the second part, `kept_in` in show, and nothing open after `finish_work`. Run it alone with `uv run pytest -n 0 <file> -k <name>`.

Open decision: the intake procedure (`intake.axiom`) does not mention `same_as`, so agents see it only in the field text. Do not change the procedure without the owner deciding.
