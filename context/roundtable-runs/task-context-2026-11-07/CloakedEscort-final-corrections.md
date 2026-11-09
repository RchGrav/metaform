# Two final corrections to D-W10 B7 — CloakedEscort

The latest consolidated draft incorporates the change boundary, adjacency revisions, transaction guard, and structural/runtime distinction. The following correct two remaining claims in B7 without changing the selected architecture.

## 1. Declared temporal labels are not verification of code behavior

B7 currently says an optional `stability: maintained | pulse | edge | any` field makes the behavior check decidable. It makes **label comparison** decidable, not a module's conformance to its label.

Counterexample: modules M1 and M2 have byte-identical manifests with `stability=maintained`. M1 maintains `true` until release. M2 emits `true` for one step then `false`. The edit plan for both declares `behaviour=preserved`. All values and links are WIT-compatible booleans. Comparing the declarations returns the same answer for both modules, although their runtime behavior differs. Moving the label to a link does not distinguish M1 from M2 either.

W-5.3 declares fields describing ports; W-6.1 gives blocks WASM code. Nothing supplied proves that arbitrary code conforms to declared temporal labels. The boundary algorithm should therefore use the reliable, inspectable event **module/state/configuration changed**, rather than treat a producer's declaration as a proof that behavior is preserved.

Proposed replacement text:

> Behavioral declarations assist retrieval and expose potential conflicts; matching declarations do not establish implementation conformance. A module replacement conservatively changes all exposed ports unless an independent, applicable verification mechanism establishes a narrower footprint. Unknown conformance remains explicit. Existing consumer goal/function/intent fields supply the preservation obligations for the agent to inspect and test. This context-selection decision adds no mandatory temporal enum to W-5.3. Content may define structured temporal contracts and corresponding validators separately.

Why this is sufficient for D-W10: the context system is deciding **what the agent must see**, not proving arbitrary generated programs correct. A conservative footprint retrieves the alarm contract even if the agent claims its pulse change preserves behavior. Tests or runtime guards can supply evidence of correctness within their stated scope; neither a label nor an acknowledgement is that evidence.

Required case: replace M1 with M2 under identical `maintained` declarations. Boundary computation must still include the alarm contract, and validation must not report behavioral conformance solely because labels match.

## 2. Proportional to fan-out does not imply a token ceiling

W-5.4 allows one output to connect to multiple inputs. Neither it nor B7 caps the number. Consequently a one-port edit with 10,000 consumers produces up to 10,000 relevant contract records. The draft's fixed-fan-out-2 example proves independence from unrelated world size, but does not establish the claimed ~1200-token maximum.

Proposed replacement text:

> Validation cost is proportional to the inspected change boundary. Each response page obeys the delivery budget and carries a continuation reference, boundary revision, and complete/incomplete status. An edit is not boundary-validated while required pages remain unexamined. The agent may instead narrow its edit to avoid changing a shared producer, or propose a task split that preserves the shared-boundary obligations. Query caps and permission failures produce explicit unresolved boundaries, never successful validation by omission. Revalidate the completed boundary at guarded application.

This is a worst-case rule, not an instruction to load all fan-out by default. A producer behavior change requires consumer obligations; attaching an independent consumer to an unchanged producer need not retrieve every existing consumer's implementation.

Required case: attach enough distinct consumers to exceed one response budget, then replace the producer module. Expect a capped response, `complete=false`, and continuation; no `validated` result after only the first page. A subsequent consumer insertion must invalidate the completed boundary revision before application.
