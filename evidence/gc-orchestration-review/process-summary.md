# Review fix process verification

Candidate: `03766976928aae6139563cdd9ec7075dd3541d7d`.

Tree: `f8dbc2419e340f98f951fbe1aef57f24975ace71`. Runtime and prompt bytes are those of the committed candidate.

Results: **15 passed**, 0 failed, 0 errors, 0 skipped.

These are real ACP adapter subprocesses and supplied stdio MCP servers driven by fake models. Live-model judgment is separate evidence.

## Reproduction

```sh
METAFORM_CANDIDATE_LABEL=03766976928aae6139563cdd9ec7075dd3541d7d METAFORM_IDLE_EVIDENCE=/workspace/scratch/243b683ad142/metaform/evidence/gc-orchestration-review/idle-candidate.json .venv/bin/python -m pytest -n 2 -q src/metaform/modules/dispatch/tests/test_orchestration_runtime.py src/metaform/modules/dispatch/tests/test_orchestration_transport.py src/metaform/modules/dispatch/tests/test_orchestration_peer_teams.py --basetemp=/tmp/metaform-gc-review-037669-process --junitxml=evidence/gc-orchestration-review/process-runtime.xml --maxfail=2
```

Execution used the environment in which runner and adapter process IDs agree with `/proc`. The 60-second CPU test reads both actual process IDs through `/proc`; it fails if either cannot be read.

## Capacity and runtime cases

| Scenario | Result | Capacity limit | Peak observed use | Within limit |
|---|---|---:|---:|---|
| `test_actual_acp_compaction_redelivers_native_role_assignment_and_functional_memory` | passed | [1] | 1 | True |
| `test_capacity_one_gc_requests_and_commissions_own_missing_role_then_receives_specialist_and_fqc` | passed | [1] | 1 | True |
| `test_capacity_one_gc_worker_specialist_return_and_independent_fqc` | passed | [1] | 1 | True |
| `test_discovery_threaded_peer_delivery_and_gc_descendant_broadcast_and_interruption[True]` | passed | [3] | 3 | True |
| `test_independent_fqc_change_order_reaches_gc_and_user_with_strict_recommendation_when_selected[strict]` | passed | [1] | 1 | True |
| `test_discovery_threaded_peer_delivery_and_gc_descendant_broadcast_and_interruption[False]` | passed | [3] | 3 | True |
| `test_independent_fqc_change_order_reaches_gc_and_user_with_strict_recommendation_when_selected[adaptive]` | passed | [1] | 1 | True |
| `test_installed_bmad_menu_and_source_reach_managed_specialist_and_return_to_gc` | passed | [1] | 1 | True |
| `test_user_stops_a_suspended_gc_and_its_live_child_without_restarting_pending_work` | passed | [1] | 1 | True |
| `test_worker_missing_role_returns_through_gc_creator_published_duty_and_registered_reuse` | passed | [1] | 1 | True |

## GC self-request journey

`gc-self-role-journey.json` contains the actual MCP request and commission, the still-running GC immediately after requesting, the role publication and version receipt, capacity-one parent/child execution, the specialist result in the resumed GC prompt together with its retained plan, the independently linked FQC context, and actual PM receipt/reconnect.

## Retained evidence

- `process-runtime.xml`: unmodified JUnit result.
- `process-summary.json`: candidate, exact command, cases, assignment ownership, process IDs, capacity samples, and archive file hashes.
- `process-traces.tar.gz`: lossless ACP/MCP recipient logs, event logs and runtime snapshots.
- `cross-team-recipients.json`: actual peer delivery, ownership boundaries and capacity-three evidence.
- `idle-candidate.json`: actual runner/adapter 60-second idle CPU observation.
