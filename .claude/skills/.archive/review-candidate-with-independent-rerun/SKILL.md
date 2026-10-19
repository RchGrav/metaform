---
name: review-candidate-with-independent-rerun
description: Use when reviewing a returned fix or FQC candidate.
category: development
---

# Re-run a returned candidate yourself before accepting it

Accept a builder's "verified" claim only after you have run the named check yourself and seen it can fail: make its condition false on a copy and confirm the failure the check exists to catch.

- Run the touched test file with its filter (`uv run pytest -m browser -n 0 PATH -k NAME`) and put the counts in your check-in evidence.
- Prove the check is live: on a copy with the condition made false, the test must fail with the expected error (a `TimeoutError` for a wait). Delete the copy afterwards. Wait-specific detail is in `playwright-waits-sync-predicates`.
- Sweep the same defect class across the scope the assignment names, not only the lines the builder touched, and list each file:line you checked.
- A defect outside the reviewed scope is filed as a new ticket with file:line, fix steps and a verify check, and named in your check-in. It does not reopen an accepted candidate.
- A failure that belongs to another open ticket is cited by that ticket's id, never counted against the candidate.

Evidence from the episode: the reviewer's own rerun and negative copy confirmed the 2D wait, while a sweep of the same class filed two more waits as a new ticket instead of reopening the review.
