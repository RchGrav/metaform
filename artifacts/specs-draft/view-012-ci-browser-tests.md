# VIEW-012 draft amendment: the browser tests in CI

Draft for Rich, from ticket code.suite.test#4 (system review 2026-10-14, H20). Not applied to `specifications/09-viewer.md`.

## What the record says now

VIEW-012 Build: "CI installs the browser on Linux, macOS and Windows and runs them with every test."

## What the code does now

- `pyproject.toml:49` leaves the browser tests out of every default run (`addopts ... -m "not browser"`); `conftest.py` marks each test that uses the `browser` fixture `browser`. Until this ticket, CI ran plain `pytest -q`, so it ran none of the 178.
- `.github/workflows/checks.yml` now has a step, Browser tests, VIEW-012, on every leg of the matrix (Linux, macOS and Windows, Python 3.11 and 3.14). It runs `uv run pytest -q -m browser` after the other tests. A path filter (`dorny/paths-filter`) runs it only when the push or pull request changes `src/metaform/modules/web/**`, `src/metaform/modules/mcp/**`, `scripts/**`, `conftest.py`, `pyproject.toml`, `uv.lock` or the workflow itself.

## Proposed amendment text

- Amendment, 2026-10-14, the browser tests in CI: the scripted checks are marked `browser` and the default test run leaves them out, since they take most of a full run's time. CI runs them in their own step, `pytest -m browser`, on Linux, macOS and Windows, after the other tests. The step runs when a change touches the web module, the mcp module (whose MCP Apps views are drawn from the page), the view build in `scripts/`, the test setup in `conftest.py`, the pinned dependencies, or the workflow. A change elsewhere does not run them. Why: the page had no CI protection, and the page split and the removal of the bar both landed without CI loading the page once; the path filter keeps the time the step costs to the changes that can reach the page. Acceptance: a push that changes a file under `src/metaform/modules/web` shows the browser tests' step run and pass on all three systems; a push that changes only a specification shows it skipped.

## Difference left for Rich to decide

- A change in the chassis (for example `src/metaform/data/` or `src/metaform/settings.py`) can break the page through the server's reads, and the path filter does not run the browser tests for it. Widening the filter to `src/metaform/**` would run them on almost every change.

## Added by ticket code.suite.test#6, 2026-10-14

- The browser step now has `timeout-minutes: 60` and the job `timeout-minutes: 120`, so a hung leg (Windows ran 5:55 in run 37151689060) fails within two hours. `workflow_dispatch:` lets a run be started by hand on a branch.
- For the Build line, Rich's wording to choose: "CI runs the scripted checks in their own step, `pytest -m browser`, on Linux, macOS and Windows; the step is path-filtered to changes that can reach the page, as above, and is limited to 60 minutes."
- Not yet seen green on any system in CI: every checks.yml run since 2026-10-04 was refused before starting with "recent account payments have failed" (latest seen: 38617176609). A dispatched run also runs only pushed code, and these changes are uncommitted.
