# Orchestration review fixes and verification

Tested runtime candidate: **`03766976928aae6139563cdd9ec7075dd3541d7d`**.

Tree: **`f8dbc2419e340f98f951fbe1aef57f24975ace71`**.

This follow-up corrects the two defects reported against the previous delivery, `de9ce05bd055bb60d349c2af1a1e05b2744d9f19`. The only production file changed is `src/metaform/modules/orchestration/state.py`. Authored prompts, the module interfaces and unrelated code retain their delivered versions. The exact production diff is [state-fix.diff](state-fix.diff), with provenance in [candidate.json](candidate.json).

## Fixes

### GC requests a missing specialist role itself

The original request path suspended every requester. When the requester was also the commissioning GC, this removed the only agent able to commission the Role Creator. The subsequent wake operation saw the GC's earlier running state and recorded no launch continuation.

The request now suspends its caller only when that caller differs from the commissioning GC. A GC requesting its own missing role stays active to receive the request and commission it. The existing `commission(wait=true)` transition then suspends the GC while the Role Creator executes. Existing worker requests retain their suspension and GC notification behavior.

The new process journey follows the complete return path: the generated specialist belongs to the original GC, its result reaches that GC's resumed ACP context with retained work, the GC delivers, and an independent `functionality` FQC receives its candidate and validation evidence. Delivery and assessment then reach actual PM context.

### Commissioning obeys the configured dynamic blacklist

Ordinary delegation already called `held_role(ctx)` to consult `roles_without_authority`; commissioning omitted that check. Commission now performs the same check before resolving the creator or creating work.

The regression checks both CLI and MCP calls. With `worker` configured in the blacklist, both delegation and commissioning refuse. Refused commissioning changes no assignments, role requests, transitions or work records. Removing `worker` from the configuration permits commissioning the same request. No new role policy or fixed list was introduced.

## Regression and process results

| Verification | Result | Evidence |
| --- | --- | --- |
| Reproductions on previous delivery | Both reported defects failed as expected | [regressions-before.xml](regressions-before.xml) |
| Initial corrected reproductions | 2 passed | [regressions-after.xml](regressions-after.xml) |
| Complete orchestration contract suite on the committed candidate | 29 passed in 34.56 seconds | [orchestration-contracts.xml](orchestration-contracts.xml), [regression explanation](regression-tests.md) |
| Actual process suite on the committed candidate | 15 passed in 336.20 seconds; no failures, errors or skips | [process-runtime.xml](process-runtime.xml), [process explanation](process-summary.md) |
| Ruff for changed source and tests | Passed | [ruff.txt](ruff.txt) |
| Strict Pyright for the changed production file | 0 errors, 0 warnings | [pyright.txt](pyright.txt) |

The reviewer's test file was not present in the available checkout or current repository tree. Equivalent behavioral reproductions were added as `test_review_regressions.py`, and both failures were captured before editing production code. The full contract suite includes those two cases; the earlier two-case runs are not additional unique coverage.

The process suite contains ten runtime journeys, four capacity/event/identity/idle tests, and one concurrent-team communication test. All passed without changing fixtures or production code after the candidate commit. These process fixtures use real ACP/MCP transport and scripted fake models; real-model execution is separate evidence.

### Actual GC self-request evidence

Root work **`e3ff2c36d84346c4869d4144e5a97fa7`** completed the added journey. [gc-self-role-journey.json](gc-self-role-journey.json) retains the GC's actual MCP request and commission, the running assignment after requesting, Role Creator publication, generated-duty receipt, specialist return in the resumed GC's prompt, independent FQC context, and actual PM delivery/reconnect.

[process-traces.tar.gz](process-traces.tar.gz) contains 34 lossless trace and record files. Each member's size and SHA-256 is recorded in [process-summary.json](process-summary.json). Original evidence from the first delivery remains in the adjacent `gc-orchestration` directory and is identified by its earlier candidate.

### Capacity and process identity

The serial journeys, including GC self-request, creation, specialist return, independent assessment and PM reconnect, used project and machine capacity **one**. Communication/interruption journeys used **three**. Every recorded sample remained within its configured limits.

Execution used the environment in which process IDs agree with `/proc`. The existing idle test read both actual runner and adapter PIDs throughout a **60.000133-second** observation. Runner CPU was **0.02 seconds**, approximately **0.0333% of one core**; adapter CPU was **0.0 seconds**. This is one observation at the host's timer resolution. The raw measurement is [idle-candidate.json](idle-candidate.json).

## Complete real-model journey

The same committed candidate completed an isolated Metaform journey using **GPT-6.1 Sol (`gpt-6.1-sol`, low effort)** through the official **Codex ACP adapter 2.2.2**, **Codex CLI 0.160.1** and **ACP SDK 1.9.0**. These were actual model sessions and model-issued tools, separate from both the initial connectivity probe and the scripted ACP fixtures above. No production or prompt files were changed during the run.

Root ticket **`fcc7915d466e450eac7a45284cf63ddd`** requested a small configuration-label normalizer at `code.label.normalizer`. Its GC requested the missing `label_normalizer` role itself and remained active to commission the Role Creator. The GC then suspended through the existing capacity mechanism. Role Creator published `metaform://role/label_normalizer`, with generated duty version **`27355977ddd54ff4b210b9aac6ca367e`**. The original specialist call continued, and its result returned to the same GC ACP session.

The specialist produced `label_tools.py` and `test_label_tools.py`, candidate **`label-normalizer-d6b63545`**. Its 11 unit tests passed. The GC independently ran those tests, checked six direct acceptance cases and verified both file hashes before delivering the root ticket. Two independent `functionality` assessments then passed: one automatically created by delivery and a second explicitly requested by the GC during completion reconciliation. Both used separate model sessions. The first also checked all 29 Python Unicode whitespace characters and five idempotence cases.

Three actual `dispatch:user-update` components reached the PM through `acp_prompt` at **2026-10-18 09:04:06 UTC**. The PM read the ticket, role, GC validation and FQC records and issued a visible completion response. This establishes recipient context and response, beyond a saved notification record. Each PM update appeared once in its actual input; the retained role/common instructions likewise appeared once per actor in the recorded inputs.

Project and machine capacity were both **one**. Retained observations never exceeded one, and the suspend/relaunch transitions show progress through the GC, creator, specialist and assessment stages. After the PM response and public CLI cleanup, all managed sessions had ended and both capacity readings were **0/1**.

Start with [the live-run report](live-model/README.md) and [live-journey.json](live-model/live-journey.json). The package includes generated source and tests, exact prompt/version and PM notification receipts, actual model command results, runtime assignments and continuations, capacity observations, and six official harness thread exports. [pm-response.txt](live-model/pm-response.txt) contains the PM's visible final response. The operational exports omit internal model reasoning and authentication account fields; they retain task/role inputs, visible model messages, completed tool calls/results and runtime identities. The scripted process traces above remain lossless and are identified separately.

### Observed live-run limitations

The two requested `state.py` defects are fixed. The live run also exposed these existing integration behaviors, which were preserved and recorded:

- GC delivery created an automatic FQC, and the GC's later explicit assessment call created a second. Both ran serially and passed; assessment requests are not coalesced in this case.
- Two informational pass-result sends to the already-ended GC remained pending. There were no corrective findings in this run, and the PM actually received both results. This run therefore does not establish a new GC launch for a passing assessment.
- The first FQC marked its work done before supplying a rich check-in, leaving the terminal assignment's evidence list empty. Its actual command evidence and detailed root-ticket note are retained. The second FQC recorded structured evidence.
- The PM encountered stale waiting/condition/progress fields alongside the authoritative delivered/completed records. Its conversational session also attempted assignment check-in and was rejected because it had no work assignment; it still consumed the notifications and reported the result.
- Official Codex `thread/read` omitted the in-flight commissioning MCP item when suspension interrupted its turn. The native transcript retains the in-progress tool identifier and suspension notice; durable creator launch/publication and the resumed real GC establish the transition. The adapter also emitted a goals-feature-disabled notice after cancellation, then resumed and completed.

This single real-model journey required no specification adaptation or corrective work and did not exercise generated-role reuse, peer interruption or compaction. The passing process tests establish those transitions separately, including adaptive publication/change orders/actual user-recipient delivery and strict-mode recommendations. The live run is evidence of one completed model-driven journey, not a claim that every acceptance scenario was repeated with a real model.

## Reproduction

```sh
.venv/bin/python -m pytest -n 0 -q \
  src/metaform/modules/orchestration/tests \
  --basetemp=/tmp/metaform-review-0376697-contracts \
  --junitxml=evidence/gc-orchestration-review/orchestration-contracts.xml

METAFORM_CANDIDATE_LABEL=03766976928aae6139563cdd9ec7075dd3541d7d \
METAFORM_IDLE_EVIDENCE="$PWD/evidence/gc-orchestration-review/idle-candidate.json" \
.venv/bin/python -m pytest -n 2 -q \
  src/metaform/modules/dispatch/tests/test_orchestration_runtime.py \
  src/metaform/modules/dispatch/tests/test_orchestration_transport.py \
  src/metaform/modules/dispatch/tests/test_orchestration_peer_teams.py \
  --basetemp=/tmp/metaform-gc-review-037669-process \
  --junitxml=evidence/gc-orchestration-review/process-runtime.xml \
  --maxfail=2
```

Fixture projects belong outside the source checkout because the existing project-history fixture detects ancestor Git repositories. These tests use isolated homes. In this execution environment, actual process tests require unsandboxed execution so their process IDs and `/proc` refer to the same namespace.
