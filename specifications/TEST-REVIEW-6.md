# Test review 6

Scope: every test added or changed since `d21920f`, by a test-review agent on Sonnet, 2026-09-26, judged only against the records each test names and Q53; no implementation file was read. `tests/test_history.py`, the MCP history tools test, the label check in `test_web.py`, and the changes in `tests/test_cli.py` and `tests/test_reports.py`.

## Findings and what was done

1. The report concurrency test ran eight threads of one process, which the in-process lock alone keeps apart, so the file lock that keeps processes apart was never exercised; with it disabled the test still passed. A second test now starts six separate processes that write to one report at once and checks every text is there and exactly five of them carry a section heading. With the file lock disabled it failed three runs in five on Linux; with it, six runs in six passed.
2. PROJ-014's second acceptance line, that a variant of the earlier unit still reconstructs after re-anchoring, was untested. The test now collects a variant against the first origin, re-anchors, checks the first unit's files are byte-identical and its variant count is kept, and extracts that variant.
3. The label check after zooming re-checked only the ceiling of 80, so a label set frozen at load would pass. The page now exposes which elements are labelled, and the test requires that set to change when zooming moves the camera; with the choice frozen at load, it fails.

## Continuation: the uninstall and wheel pull tests

Commits `7eb1b6e` and `e9676ab` came in before this round's starting commit and no earlier review covered their tests, so the reviewer read them in a second pass: the three MCP-020 uninstall tests in `tests/test_install.py` and the two BASE-025 wheel pull tests in `tests/test_store_exchange.py`.

4. No test told apart removing the home's own skill copy only once no set-up tool is left from removing it on every uninstall: the partial uninstall checked the cross-agent copy survives, but not the home's. It now checks both. Removing the home's copy on every uninstall fails it.

The reviewer found the rest of both files sound, naming the partial uninstall as the check that tells removing Metaform's entry apart from rolling a config back to its install backup.

## Coverage notes

The reviewer checked the rest of `test_history.py`, the MCP tools test and the module-off CLI test line by line against PROJ-010 to PROJ-018, PROJ-023, PROJ-024 and Q53, and found no loose check or wrong marker.
