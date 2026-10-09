# Test review 8

Scope: the tests step 27 added for the Encounter Function's word, Function or Encounter, by a test-review agent on Sonnet, 2026-09-26, judged against the owner's words that day and MAP-020, MAP-030, MAP-040, BASE-039, STORE-017 and VIEW-006; no implementation file was read. Two store tests in `tests/test_store_corrections.py`, two intake tests and the added assertions in `test_intake.py`, the fixture `tests/fixtures/intake_timer.json`, and the browser test in `test_web.py`.

## Findings and what was done

1. The closed-choice store test read only what the write returned, so a stored row that differed from it would pass. It now reads the join and the subtype back and requires no `ef` there, with the other word in `extra`, as MAP-020's third acceptance line says.
2. The missing-word intake test checked that the notice contained the letters "ef", which "left" or "reference" would satisfy. It now requires the notice to begin with "ef is missing".
3. The relocation check covered only the join's word, although the test names the subtype too. It now requires the subtype's removed row to keep its word; with the word dropped from the subtype's relocation copy, it fails.

The intake text and tool schema test, the submission assertions and the browser test were found sound. No part of the requirement was left without a test.
