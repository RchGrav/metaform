# Orchestration contract verification

## Exact candidate and command

- Candidate commit: `8c9bf81eaa6876b5dc34766574ebb1eece2a5851`
- Candidate tree: `0491a3ce9f3d0814c835de60f6070211ccf9dd57`
- Source status before the run: clean for orchestration and workflow.
- Environment: Linux, Python 3.12.14, pytest 9.1.1; one pytest worker (`-n0`).
- JUnit start: `2026-10-18T07:27:15.767167Z` (normalized from its recorded UTC−05:00 timestamp).

```sh
.venv/bin/pytest -n0 src/metaform/modules/orchestration/tests --junitxml=evidence/gc-orchestration/orchestration-contracts.xml
```

**Result: 27 passed in 30.45 seconds; exit status 0.** JUnit records 27 tests,
zero failures, zero errors and zero skips (suite time 30.506 seconds).

The machine-readable result is [orchestration-contracts.xml](orchestration-contracts.xml).
[contract-snapshots.json](contract-snapshots.json) preserves selected records
read back through the public Store API from this run's isolated fixtures. These
records supplement the assertions that exercised transitions; they do not by
themselves establish ACP delivery. Repeated authored prompt text inside role
publication result envelopes is omitted from the snapshot, with source,
version identities and body hashes retained.

## Workflow successor and return contracts

The tests execute the existing workflow catalogue, frozen run executor,
continuations and public revision integration. Full test names and timings are
in JUnit; the implementation scenarios are in
[test_orchestration.py](../../src/metaform/modules/orchestration/tests/test_orchestration.py).

| Contract | Exercised behavior and observed result |
| --- | --- |
| Frozen history and immediate return | `test_workflow_revision_preserves_frozen_history_variables_and_return_route` replaced the requested frozen logic while retaining `target=7` and `steps_completed=2`. Original run `34ed824c22fd44e1ba838308fe91cdd9` remains cancelled history; successor `ef1609c0da7c59cda3e23248f9df9ed8` completed. Its return resumed caller `23d9cf44d0524e8ebf554b6b249718c6`, retaining `caller_progress="retained"` and assigning `ok=true`. Replaying the revision reused the successor. |
| Genuine user pause | `test_workflow_adaptation_keeps_user_pause_and_binds_operative_successor` published revision 2 and changed the GC's recorded run to `8bc0761d67cc5990a1939464d0c10353`. That successor remains `input_required` with the exact question “Which duration did you request?” No answer or execution progress was invented. Original `b3862fa91ae5447b81708b232776fee8` remains cancelled history. |
| Completed and active parallel branches | `test_workflow_successor_retains_completed_branch_and_active_child_returns` retained the completed first branch's original history and reparented only the active second branch. Successor `8579cf5de7195e6394e7a12b9cb25bb1` completed with `progress="kept"`, `first=true` and `second=false`. The first branch still points to the original run; the second returned to the successor. |

### Source advancement and crash recovery

Both parametrizations of
`test_workflow_recovery_follows_successor_and_newer_source_without_reopening_completed_run`
advanced the operative source after the first frozen successor committed. The
`False` case exercises the detected inter-store race; the `True` case also raises
an `OSError` at that point to simulate controller loss. Recovery constructs a new
runtime service and follows the recorded successor, preserving the authored
revision separately from the later operative source.

| Case | Original authored change | Recovered operative run |
| --- | --- | --- |
| Race without crash | Change `e726f301bc15561fb7176a1b17ee8ab0` preserves publication 1 → 2; its operative binding is revision 3. | `091caa3e738759808b9ad001c42754fa`, containing the newer selection-and-keyboard-focus instruction. |
| Crash after successor commit | Change `c39db2c57c1a5856a1e99c04c3b903a6` preserves publication 1 → 2; its operative binding is revision 3. | `3724f754fce2519c9cf24626537cfe1f`, containing the same later instruction. |

Each scenario asserts that the GC change order identifies published revision 2,
current revision 3, the newer content and the usable successor. The intermediate
successor remains cancelled history. After the recovered run completes, a later
revision 4 publishes with `run=null` and `previous_run` naming that completed
execution; completed work is not reopened.

## Post-delivery missing-role commissioning

`test_post_delivery_fqc_missing_role_gets_commission_gc_and_retains_original_return`
executes these transitions against real work and orchestration stores:

1. GC `d0ac0facbb7c5b4888b973417e111f3b` delivers its root. Independent FQC
   `7bcbae912679544a856937812b57d235` requests `focus_observer`, including the
   keyboard-interaction context.
2. Request `c5b574aa817b5f4ea2f164f42fee7ee8` records a separate corrective GC,
   `c3f9da7e838652eb8df36c858f9848d8`, as commissioner. That GC owns its own team
   and links to the original root; the original GC remains delivered. The old GC
   is refused when it tries to commission this different GC's recorded request.
3. The correct GC commissions Role Creator `cc764f5d8ef144f8969b7e645dc7f17c`.
   Publication registers `metaform://role/focus_observer` and selected/actual duty
   version `31ff781f7b3247d892a09bfe478c9dc9` under
   `agents:generated_proj_focus_observer`. Source history records bound session
   `creator` and actual calling runner `creator-runner`.
4. Specialist `2e10d64300534bdc9467cf51196f9dd7` inherits the FQC's team and
   returns to that FQC. The test checks that supplied keyboard context reaches
   its assignment, the same original call key reuses this child, and its return
   contains “Keyboard focus remains on duration.” with observed evidence. A
   recorded FQC resume is queued; no original-root launch is created.
5. A user stop then cancels remaining continuations. The snapshot consequently
   shows the FQC and commissioner stopped, the creator and specialist returned,
   and the original GC still delivered. A further missing-role call is refused
   by the retained stop tombstone.

## Other contracts in this run and scope

The remaining passing tests cover atomic claims, nested capacity-one calls,
role reuse, independent FQC corrections, active GC reservation access for
FQC-called specialists without swarm authority, adaptive file publication and
transport notification, strict recommendations and actual newer user direction,
public-board completion with mixed event concerns, stop/restart, handoff returns,
per-caller result-key identity, and optional installed BMAD source/menu/version
handling. The sessionless-agent regression confirms that omitting a session does
not classify an agent's text as a new user instruction.

The deterministic transport scenarios assert a maximum of one occupied slot
where capacity one is configured. The suite also uses actual workflow execution
and public board operations. Real runner subprocess, ACP/MCP recipient-turn,
process cancellation/load, configured admission and live PM/UI notification
evidence belongs to the separate integrated and lifecycle suites for this same
candidate. No production adapter or external BMAD installation is implied by
these isolated contract fixtures.
