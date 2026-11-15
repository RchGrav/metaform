# Roundtable accolades and recognition

The original session instruction promises that a participant's score will be added to its identity for future sessions, together with accolades and recognition for its efforts. The complete original instruction is preserved in [the recognition instruction](../../evidence/roundtable-original-recognition-instruction.md), with its source path and checksum.

## Original recognition promise

```text
Notice: At the end you will be scoring each other on your ability to cooperate and the value you brought to this exercise. You will not know who gave you each score and you will see the final ranking at the end including your rank in the line up, additionally this score will be added to your agents identity as part of your profile in future sessions as well as accolades and recognition for your efforts.
```

The complete historical opening also contains the earlier intertopic process. The current process is governed by [the consolidated roundtable specification](../../specifications/12-roundtables.md). The earlier recognition promise remains recorded for review.

## Current recorded recognition

The [scoring implementation](../../src/metaform/modules/roundtables/roundtable/stages.py) awards weighted points for Efficient, Alert & Aware, Thorough and Coordination, with a five-point bonus for improving the final work beyond critiquing it. The [full rubric and score-storage reference](roundtable-agent-ratings.md) includes the detailed original instruction, exact current roundtable prompts and persistence rules.

The [roundtable profile store](../../src/metaform/modules/roundtables/roundtable/store.py) retains the cumulative score, rating count, session count, display name and update timestamp. The session publishes aggregate rankings. Future session context receives the saved numeric profile through `session_profile`.

## Accolade mechanism still missing

Those profile records and the current profile prompt do not define named accolades, an award ledger, award criteria or an accolade-delivery mechanism. The existing `test_future_session_context_contains_only_aggregate_profile_scores` in [the session tests](../../src/metaform/modules/roundtables/tests/test_session.py) explicitly expects aggregate scores without accolade text in the carried context.

The original promise therefore goes beyond the currently implemented profile behavior. The archive retains the promise, all current prompts, the complete scoring and profile source, and the existing tests so this gap can be reviewed and refined. It does not invent award names or rules absent from the available design material.
