# Review regression verification

Tested candidate: `03766976928aae6139563cdd9ec7075dd3541d7d`.
Candidate tree: `f8dbc2419e340f98f951fbe1aef57f24975ace71`.

## Reproduction and correction

The reviewer's `test_review_regressions.py` was absent from the available local checkout and current repository tree. The two reported defects were reproduced in a new test file under that name through the public orchestration verbs, isolated work/prompt stores and the existing deterministic capacity transport.

On the previous delivery, `de9ce05bd055bb60d349c2af1a1e05b2744d9f19`, both regressions failed in 1.66 seconds:

- A GC calling a missing specialist role suspended its only running session. After draining, no agent was running and its role-request message remained queued without a launch continuation.
- With `worker` in the configured `roles_without_authority`, ordinary delegation raised `Stop`, while commission created a Role Creator instead of refusing the call.

The fixed GC request remains actionable by its GC. The test observes the GC receiving that request, commissioning the Role Creator, and the creator launching within capacity one. A retry preserves the original request identity.

Commission now uses the same existing dynamic configuration check as delegation. The test exercises both CLI and MCP surfaces and asserts that refused commissioning leaves assignments, requests, transitions and work unchanged. Removing `worker` from the configured blacklist then permits that same request to be commissioned.

The initial fixed run passed both tests in 1.97 seconds. The complete orchestration suite then passed **29 tests in 34.56 seconds on the committed candidate**, including existing worker-initiated role creation, publication, reuse and return; independent FQC corrections; workflow continuations; and optional BMAD role contracts.

## Commands and reports

Baseline reproduction and initial correction:

```sh
.venv/bin/python -m pytest -n 0 -q \
  src/metaform/modules/orchestration/tests/test_review_regressions.py \
  --basetemp=/tmp/metaform-review-regressions-before \
  --junitxml=/tmp/metaform-review-regressions-before.xml

.venv/bin/python -m pytest -n 0 -q \
  src/metaform/modules/orchestration/tests/test_review_regressions.py \
  --basetemp=/tmp/metaform-review-regressions-after \
  --junitxml=/tmp/metaform-review-regressions-after.xml
```

Exact committed candidate:

```sh
.venv/bin/python -m pytest -n 0 -q \
  src/metaform/modules/orchestration/tests \
  --basetemp=/tmp/metaform-review-0376697-contracts \
  --junitxml=evidence/gc-orchestration-review/orchestration-contracts.xml
```

The unchanged original JUnit files are [regressions-before.xml](regressions-before.xml), [regressions-after.xml](regressions-after.xml), and [orchestration-contracts.xml](orchestration-contracts.xml). [regression-tests.json](regression-tests.json) records exact identities, source hashes and assertions.

These contract tests use a deterministic transport. The process tests and real-model harness journey are separate verification evidence; their results are not implied by these 29 passes.
