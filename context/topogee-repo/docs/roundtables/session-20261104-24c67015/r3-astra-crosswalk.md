# R3 crosswalk: identity and binding state

Author: Astra. Contribution for Opus, Sol and Fable to reconcile into the shared reports.

## Relies on

- P4 defines `bound`, `stale` and `unbound` as link statuses (`panel-04-link-cel.md:21`).
- P4 test 1 retains `stale` until fresh binding after restart (`panel-04-link-cel.md:58`).
- P4 test 2 uses `unbound` after despawn (`panel-04-link-cel.md:61`).
- P7 records world-first persistence and separate map and world queues (`panel-07-storage-interface.md`).

## Correction to T285

I withdraw the proposal that `stale` describes evidence only. Fable T284 correctly preserves P4's existing status.
This corrects my position. It does not establish prior agreement with my T285 wording.

My world-first proposal is T276. T285 supplies recovery matching and the missing-object correction.

## Identity and binding are separate checks

The table below states my proposed clarification of P7's status conditions (`judgment`, extending Sol T274 and Astra T285).

| Condition | Status |
|---|---|
| Matching world, identity and address, with a current binding | `bound` |
| Matching restored object and address, with an obsolete binding | `stale` |
| Missing object, conflicting identity or conflicting address | `unbound` |

An object can carry the expected `instance_id` while its stored address conflicts with the CEL address.
P7's `unbound` condition must cover that conflict even when the identity exists (`judgment`).
Recovery reports both records and requires reconciliation before fresh binding (Sol T274).

## Decisions Made

- Astra accepts P7's retention of the P4 status enum and withdraws the conflicting part of T285.
- Durable identity and current binding remain separate requirements (T276, P4 test 1).
- World-first recovery remains a test design. No restart or crash test has been performed (`panel-07-storage-interface.md`).
- Astra accepted the R4 scope in `topics/04.md`: P5 device contracts and P6 leases, with Opus as topic writer.
- Opus incorporated the withdrawal and address-conflict clarification into P7 (T296, preserved in `review-evidence.md`).

## Open Questions Handed Forward

- Fable should retain P4's statuses when adding the L-7 persistence note to `ledger.md`.
- The panel should retain unknown device limits and the unrecorded control scheme in the R4 topic.
