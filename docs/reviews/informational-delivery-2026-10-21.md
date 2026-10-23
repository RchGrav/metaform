Informational delivery repair. Author: silent-agent.

Outcome: Routine peer notes, progress, completion announcements, plan results and roundtable notices remain records. They do not prompt or resume a model, replay at startup, or join unrelated user turns. Explicit reads retain the records. The UI folds peer bodies for deliberate expansion.

Reason: Earlier dispatch delivered peer information as normal turns and replayed project notifications. That supported coordination but spent context without requested work. The repair preserves coordination through current questions, blockers, user direction and owned child continuations. C(T) remains unchanged. The user's Claude Max exhaustion report establishes user experience, not measured attribution. No usage savings are claimed.

Mechanism: Existing session lines hold small peer_delivery metadata. Restart selects that kind through the existing session/kind index. Ownership checks precede selected body reads. Queued requests are checked again before the model call. Closed, stopped, withdrawn, resolved and superseded requests cannot revive work. Child returns follow the recorded immediate caller and handoff successor. Project updates retain UI records without a model recipient. No schema migration, polling or inference classifier was added.

Local Git evidence:

- Main baseline: 4a477d2dbdacdb87ced82295ce94ec8d3d2b68cf.
- Isolated worktree: /tmp/metaform-silent-context, branch fix/informational-context.
- Snapshot of preexisting local product edits: 8421c5c7. This snapshot is isolated, not integrated as a new main commit.
- Product repair: bd618279.
- Deterministic prompt/resume counters: 432e4f8d.
- Final typed metadata fix: d0026bd0.
- Evidence artifact: ca6462f2, followed by a documentation-only concurrency correction.
- Integration: Applied the candidate delta to /home/rich/metaform. At application, main HEAD and its exact staged diff were unchanged. All 48 other dirty paths were byte-preserved. The fifteen task files matched the candidate. A concurrent peer then committed f9530497, adding ticket-merge functionality and documentation. Those changes remain intact. Thirteen task files still match the candidate exactly; README/spec differences are the peer's additions. Main HEAD is now f9530497.
- Integration commit: none. Creating a clean-HEAD integration commit conflicts with preexisting edits in five files. The verified working-tree integration preserves those edits and the existing staging. No push occurred.

Changed files, including this evidence artifact:

```text
docs/reviews/informational-delivery-2026-10-21.md
specifications/04-chassis-modules.md
src/metaform/modules/dispatch/README.md
src/metaform/modules/dispatch/orchestration.py
src/metaform/modules/dispatch/peering.py
src/metaform/modules/dispatch/resources/prompts.xml
src/metaform/modules/dispatch/runner.py
src/metaform/modules/dispatch/signals.py
src/metaform/modules/dispatch/tests/test_autostart_cost.py
src/metaform/modules/dispatch/tests/test_cross_project.py
src/metaform/modules/dispatch/tests/test_dispatch.py
src/metaform/modules/dispatch/tests/test_informational_delivery.py
src/metaform/modules/dispatch/tests/test_orchestration_transport.py
src/metaform/modules/orchestration/state.py
src/metaform/modules/orchestration/tests/test_orchestration.py
src/metaform/modules/web/page/app/session/apps.js
```

Deterministic evidence:

- Baseline reproduction fails test_notifications_never_prompt_or_piggyback[peer-False-worker]: a routine note queues an unwanted turn.
- Thirty-six kind/idle/busy/recipient combinations each produce zero informational prompt calls and zero resume calls. Each subsequent explicit user message produces exactly one unchanged prompt.
- The owning child continuation produces one prompt. Repeated delivery produces none. Unrelated and stopped recipients receive none.
- A restart with 100 historical peer rows reads only peer_delivery metadata, produces no model call and leaves the historical note readable.
- Withdrawn, resolved, superseded and reassigned requests produce zero model calls. Current questions, blockers and user direction remain deliverable.
- Peer UI rendering check passes: collapsed details, recorded status and the full retained body on expansion. Node syntax check passes.

Checks, run with fake transports or fake ACP adapters only:

```sh
.venv/bin/pytest -n0 -q src/metaform/modules/dispatch/tests/test_informational_delivery.py
.venv/bin/pytest -n0 -q src/metaform/modules/dispatch/tests/test_cross_project.py
.venv/bin/pytest -n0 -q src/metaform/modules/dispatch/tests/test_orchestration_transport.py -k 'managed_continuation or unrelated_bursts'
.venv/bin/pytest -n0 -q src/metaform/modules/orchestration/tests/test_orchestration.py -k 'return or handoff or result_sent or default_delivery'
.venv/bin/pytest -n0 -q src/metaform/modules/dispatch/tests/test_startup_repair.py
.venv/bin/pytest -n0 -q src/metaform/modules/dispatch/tests/test_autostart_cost.py src/metaform/modules/dispatch/tests/test_dispatch.py -k 'last_ticket_of_a_plan or helper_that_finishes'
.venv/bin/pyright src/metaform/modules/dispatch/orchestration.py src/metaform/modules/dispatch/runner.py src/metaform/modules/dispatch/peering.py src/metaform/modules/dispatch/signals.py src/metaform/modules/orchestration/state.py
node --check src/metaform/modules/web/page/app/session/apps.js
git diff --check
```

Recorded results: Cross-project 8 passed. Managed continuation/event filtering 13 passed. Orchestration return/handoff 14 passed. Withdrawal/closed-caller additions 4 passed. Startup blockers 9 passed. Plan/helper UI updates 2 passed. Focused notification/transport selection 64 passed before the final additional counter test. Integrated notification tests initially passed 49 cases. Final integrated rerun: 50 passed in 86.49 seconds. Pyright: zero errors and warnings. Ruff: all checks passed. git diff --check: clean.

Idle CPU evidence used the same fake-adapter fixture with native orchestration disabled. Initial attempts with orchestration enabled suspended before adapter startup; those attempts measured nothing. Over 60.0016 seconds, baseline runner used 0.04 CPU seconds, 0.0667% of one core. Over 60.0176 seconds, candidate runner used 0.03 CPU seconds, 0.0500%. Fake adapter used zero measured CPU seconds in both. This is an idle-loop check, not an inference cost measurement.

Original verification found one baseline failure in test_rules_reach_an_agent_once_per_context_epoch. Follow-up acceptance replaced its obsolete replay expectation and found a second-turn rules replay after compaction. The runner now bootstraps rules only for a new conversation. The updated retained-context test passes. Startup-authority files owned by the other helper were not edited. Legacy peer rows without delivery metadata remain explicit-read history; canonical assignment transitions still recover owned continuations. Existing long-lived runners retain loaded Python code until their normal restart. No live runner restart, Claude call, live inference test, additional helper, board operation or stop-all was performed.

Memory maintenance corrected Ticket completion reference delivery, Agent message line and Research helper ticket findings. Removed stale automatic-delivery observations and obsolete dispatch_helpers/helper_result claims. Added current ownership, metadata replay and UI-only helper-result facts through canonical memory operations.


Follow-up, 2026-10-22: Read the four explicitly requested dispatch notes. Restored the withdrawn memory deletion before further maintenance. See `memory-restoration-2026-10-22.md` for verified content, preserved later writes and unavailable metadata. Then corrected only the two stale automatic-delivery observations in `Agent message line`; earlier targeted dispatch observations remain present.

The Caveman skill was read. Existing runtime rules carry the user's concise output constraints. Dispatch communication guidance requests one summary phrase, short sentences and explicit detail reads. New-conversation tests verify unchanged authored rules are delivered once. Repeated turns and compaction deliver no automatic rules copy. No live inference was used to claim model compliance.

Duplicate queued text under another note ID now remains a readable record, without a false delivered receipt. Tests use the real receipt path and fake acceptance callbacks. They cover duplicate IDs before and after acceptance, restart, rejected sends and retry. Accepted child result: one prompt, zero resumes, 60 UTF-8 text bytes. Accepted question: one prompt, zero resumes, 98 UTF-8 text bytes. Repeated delivery and restart add zero prompts or bytes. A forced pre-acceptance rejection adds one failed prompt attempt, zero accepted bytes, then permits one successful retry. Routine notifications: zero prompt calls, resume calls and prompt bytes across all 36 role/busy/kind combinations. These are deterministic fixture measurements, not model-token or billing estimates.

Follow-up integration applied five product/spec/test files to the existing checkout. All 332 unrelated dirty paths and the exact staged diff were unchanged at application. No instruction files were changed. Existing runners still require their normal restart to load changed Python.

Follow-up commands:

```sh
PYTHONPATH=/tmp/metaform-silent-context/src /home/rich/metaform/.venv/bin/pytest -n0 -q src/metaform/modules/dispatch/tests/test_informational_delivery.py src/metaform/modules/dispatch/tests/test_orchestration_transport.py -k 'not managed_continuation and not idle_cpu and not unrelated_bursts'
PYTHONPATH=/home/rich/metaform/src .venv/bin/pytest -n0 -q -s src/metaform/modules/dispatch/tests/test_informational_delivery.py src/metaform/modules/dispatch/tests/test_orchestration_transport.py -k 'accepted_delivery or rules_reach_retained or startup_checkpoint'
.venv/bin/pyright src/metaform/modules/dispatch/runner.py
.venv/bin/ruff check src/metaform/modules/dispatch/runner.py src/metaform/modules/dispatch/tests/test_informational_delivery.py src/metaform/modules/dispatch/tests/test_orchestration_transport.py
git diff --check
```

Integrated follow-up selection: six passed, 108 deselected. Pyright: zero errors or warnings. Ruff and whitespace checks pass.

Follow-up candidate commit: `127ea92c`. Broader deterministic selection: 100 passed, 14 deselected in 218.10 seconds. Local integration remains a working-tree patch preserving peer changes and staging; no main integration commit or public push.
