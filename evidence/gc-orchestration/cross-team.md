# Two independent GC teams: actual ACP recipient evidence

## Candidate and result

Production candidate: `8c9bf81eaa6876b5dc34766574ebb1eece2a5851`.
Production tree: `0491a3ce9f3d0814c835de60f6070211ccf9dd57`.
Only the new focused test was added for this check; no production source changed.
Test SHA-256: `a6c28f3f77b446c0a22754dfffe2f3ecd97ffdc67a0c37e54220e969af8e1e1a`.

```sh
.venv/bin/pytest -n0 src/metaform/modules/dispatch/tests/test_orchestration_peer_teams.py --basetemp=/tmp/metaform-peer-teams-8c9bf81 --junitxml=evidence/gc-orchestration/cross-team.xml
.venv/bin/ruff check src/metaform/modules/dispatch/tests/test_orchestration_peer_teams.py
.venv/bin/pyright src/metaform/modules/dispatch/tests/test_orchestration_peer_teams.py
```

Result: **1 passed in 10.49 s**, pytest exit 0; Ruff passed; Pyright reported 0 errors and 0 warnings. JUnit records 1 test,
0 failures, 0 errors and 0 skipped,
with suite time 10.567 s. The runner used Python 3.12.14 / pytest 9.1.1.
Local socket/subprocess access was required by the existing fake ACP fixture.
An initial restricted-environment attempt could not start a runner and is not counted as runtime evidence.

The test calls the existing public CLI using the actual runner identities recorded by dispatch. The classic
`fake_agent.py` logs ACP requests and holds each turn until the test releases its gate; it does not fabricate
receipt or cancellation records. Both root tickets start through `Dispatch(..., orchestration=True)` and A
creates its child through public `orchestration delegate` with `wait=false`.

## Observed participants and capacity

| Participant | Work | ACP session | Operational / authored role |
| --- | --- | --- | --- |
| GC A | `39553ec9459748dcae23a1407dc77753` | `fake-session-1` | worker / gc |
| GC B | `312c3c66f9c44b3699b5cd73a72cf634` | `fake-session-2` | worker / gc |
| A's child | `9d9ddd8a2b2342c5b36f1c9dc4137df9` | `fake-session-3` | worker / implementer |

The two GC assignments have distinct team IDs. The child is a member of A's team.
Public `dispatch peers` enumerated all three live assignments. Public `dispatch agents` reported
project limit 3 / used 3 and machine limit 3 / used 3 while both GCs and the child were live.

## Actual delivery and authority results

1. A sends `CROSS_TEAM_NOTE` to B. The sender receives note ID `c8b25c653bc82805` and normal-turn
   delivery status. The text is absent from B's current in-flight prompt. After B's first turn ends,
   B's second ACP `session/prompt` contains the note.
2. B replies with `CROSS_TEAM_REPLY`, note ID `d73564c9dc97e311`, with the original note ID as
   `reply_to`. After A's initial turn ends, A's second ACP prompt contains that reply. Kept peer rows
   attribute the first note to A's actual assignment and the reply to B's actual assignment.
3. A's `OWN_SWARM_ONLY` broadcast lists exactly A's child as recipient, and its actual next ACP prompt
   contains the broadcast. B's recipient prompts contain neither that marker nor the attempted foreign direction.
4. A's attempted interruption of B returns exit code 2: “Only the recorded GC can interrupt a member
   of its own swarm.” Neither GC receives `session/cancel`; no adapter receives `_session/steering`.
   B remains alive on the same recorded running session after the denied attempt and A's later child interruption.
5. A interrupts its own child. Exactly one ACP `session/cancel` is observed, naming `fake-session-3`.
   The child's following ACP prompt contains `OWN_CHILD_NEW_DIRECTION`, and its assignment retains the
   pending direction. The evidence captures three child prompts versus two for each GC.

`cross-team-recipients.json` contains the public responses, actual recipient prompt bodies, threaded note rows,
assignment ownership, capacity observation, refusal, cancellation and steering observations before cleanup.
`cross-team.xml` contains the machine-readable test result. The test then stops only its isolated test home.

This focused check establishes the concurrent-team communication and ownership boundary. The separate integrated
swarm suite covers worker-called descendants, capacity-one suspension, corrections, changes and recovery.
