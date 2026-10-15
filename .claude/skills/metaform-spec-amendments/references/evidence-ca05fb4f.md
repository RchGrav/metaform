SKIPPED [4] src/metaform/modules/dispatch/tests/test_dispatch.py:37: the lock on unlinked files is off until the rules and prompts for linking are in place, code#1e
2 passed, 4 skipped, 150 deselected in 16.86s

Draft text written for the owner: "CTX-060 to CTX-064 are built but all off under LINK_LOCK=False (runner.py:143), their lock tests skip; CTX-063's ref record and CTX-065 are built"

Memory observation: "On 2026-10-15 every lock record (CTX-060 to CTX-064) said built while runner.py's LINK_LOCK was False, so none of them held; the passing-looking acceptance tests were skipping, not passing."