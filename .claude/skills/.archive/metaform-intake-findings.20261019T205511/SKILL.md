---
name: metaform-intake-findings
description: Use when intake same_as, kept_in or a duplicate finding.
category: development
---

# Intake keeps one defect once

When intake finds a defect already recorded at another element in the same run, record the second finding with `same_as=ADDRESS` naming that element. It joins the open ticket there, so one ticket carries the defect and no second ticket looks untouched. Do not file a second ticket by hand.

- A kept part's intake assessment stores the ticket id as `kept_in` in its evidence. `intake show` reads that part with the ticket's condition, note and `kept_in`.
- Recording the kept part again, OK included, takes its link off the ticket. A ticket an agent has taken is left as it is.
- If the kept ticket is taken and lacks the new note, the note is not dropped: the part gets its own ticket, and the two tickets link each other.
- A node's view, open-work count and light count only count tickets filed at that node (VIEW-035). A linked part does not show the defect there. Never write a doc or spec line that says it does.
- Open for the person: whether node views and lights should count an intake finding that links them, and whether the Canonical Intake procedure should mention `same_as` (today only the field description does).
- Test: `test_one_defect_found_at_two_elements_is_one_ticket_linking_both` in `src/metaform/modules/intake/tests/test_intake.py`; run `uv run pytest -n 0 src/metaform/modules/intake/tests/test_intake.py -k one_defect`.
- Spec: the MAP-046 build note in `specifications/01-map.md`, dated 2026-10-19.
