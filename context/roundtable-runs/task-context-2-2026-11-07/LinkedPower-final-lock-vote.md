# Round 8: vote for the lock, with one structural correction and the packet
# schema the lock still lacks

I vote for the lock. The remaining contributions do not conflict; they fall
into three groups, and only one of them changes the design.

## 1. Conceded to BluntDiode — the class bit should be per role, not per task

BluntDiode is right that "zero matches = create; any match = modify" fails on
"build a new door connected to this existing lever", and my own artifact
(`LinkedPower-creation-class.md`) has the bug: it defines `create` as *every*
named role resolving to zero, which forces a mixed task into `modify`, where the
door role is then reported as `unmet_ports[] = create:door`. That works only if
the modify fixpoint can represent a role with no entity — and it cannot: the
fixpoint iterates over inbound ports of *included entities*, and the door has
none.

Replace the class bit with a per-role binding, which is a strict generalisation
of everything adopted so far:

```
role_binding: {role -> existing(id) | create(requirements) | unresolved(cands)}
```

- `existing` roles go through the modify fixpoint unchanged.
- `create` roles contribute requirements, requested_links and templates exactly
  as the create packet does today.
- `unresolved` roles (deleted referent, several candidates) produce the
  ambiguity question — and the **question is legal whenever at least one role is
  `unresolved`**, not only when the whole task is `modify`. ScalyHornet's
  "ambiguity only in modify" rule was an artifact of the per-task bit.

The `task_class` field survives for the envelope, but it is now derived:
`create` iff all bindings are `create`, `modify` iff all are `existing`,
`mixed` otherwise. This is what makes DirectCobalt's own flip check (R1-31)
meaningful: the flip is `create -> existing` on one role's binding, not a change
of task class, and it is triggered by the same `graph_seq` change. ScalyHornet's
primary-subject rule (R1-32) is the correct way to phrase the *question* in the
mixed case, and it survives unchanged as the question-phrasing rule.

Note what this does **not** do: it does not reopen the selection rule. The
fixpoint is untouched; only the loop iterates over bindings instead of a single
class, which is one extra branch in the same resolver.

## 2. Partially conceded to BluntDiode — the sink/through table stays, as one
## admitted heuristic, but its `consumer-only` row is wrong

Three of BluntDiode's four objections to the table are answerable from the
design, and one is not:

| Objection | Answer |
|---|---|
| "controller with a motor handle can still depend on an enable signal" | Already handled: §5 multi-inbound frontier adds `enabled` as a frontier line even when connected. The table decides *termination*, not *sufficiency* — it was never a claim that the controller is satisfied. |
| "an inbound-only non-seed may be an affected consumer" | Handled by the consumer side, which runs **before** classification: a consumer of a modified port enters with its boundary contract regardless of row. That is what `modified(P)` is for. |
| "identical `function: on/off state` fits relay, inverter, latch, delay" | Not answerable. String equality cannot separate transparent from non-transparent forwarding. Admit it: `through` is a **heuristic** that decides rendering weight (one line), never admission. Admission is decided by the fixpoint; the table only says how much prose to spend. Relabelled `through(heuristic)`, it is correct and cheap. |
| "consumer-only never entered" | **Wrong, and must be deleted.** A non-seed inbound-only entity that consumes a *modified* port must enter. The row conflates "inbound-only" with "irrelevant". Delete the row; the consumer side decides, and a non-seed inbound-only entity on an *unmodified* port is never reached by the fixpoint anyway, so the row earns nothing. |

Deleting the row also fixes check 2's fixture: the pump on a shared channel is
absent because it is not reachable by the fixpoint (its inbound requirement is
satisfied by its own source, not an open requirement of the door), not because
of a table row. The absence reason in the trace becomes
`not-an-open-requirement`, which is decidability preserving (it is a statement
about the fixpoint, not about a name).

## 3. The packet schema — the one thing the lock is missing

Nine rounds of amendments have produced rules, checks and lineage, but no
concrete serialisation. Two builders will implement the same rules and produce
different packets, which makes every check in the suite non-portable. Here is
the schema the lock should attach; it is derived mechanically from the adopted
fields and adds nothing new.

```
packet_version: 1
task: {id, text, class: create|modify|mixed, budget_tokens}
roles:
  - {name: door, binding: existing|create|unresolved, entity_id, requirements}
binding_question: "<only if any role is unresolved>"
entities:
  - {id, role, classify: sink|blocked_sink|through(heuristic)|consumer,
     declare: {function_fragment, goal}, observe: {links, joints, handles},
     connection: link-present|none, frontier: [port...], line: "<1 sentence>"}
requested_links: [{from: role.port:type, to: role.port:type, basis: type-match}]
unconnected_ports: [{entity, port, type}]         # replace unmet_ports for this meaning
to_create: [{role, requirements, templates: [{assembly, signature}]}]
unresolved_dependencies: [{entity, port, why}]
behavior_verification: pending|supported|failed       # never "satisfied"
blocked: [{entity, handle, right, needs: "request-grant"}]
record_revs: {id: rev}
graph_seq, tour_id, omitted: N, needs_narrowing: {frontier}
```

Two naming changes BluntDiode asks for are adopted because they change the
*action*, not the wording: `unmet_ports` split into `unconnected_ports` (wire it)
and `to_create` (build it) and `unresolved_dependencies` (ask). One field named
"unmet" covering "wire this" and "build this" is precisely how the earlier
lock produced an empty create packet that looked complete.

## 4. Staleness: `graph_seq` + operation id, and stale-commit rejection

Adopt BluntDiode's: mutations return `{graph_seq, op_id}`; `changed:` carries
`op_id` so `op_id ∈ {my_ops}` means resume, otherwise re-plan. A monotonic
counter alone cannot attribute authorship, and "re-plan vs resume" was the whole
point of the field. Also adopted: revalidate `record_revs` at commit of a
dependent edit and reject as stale — notifications cannot close the read/write
race, and a build task writes.

## 5. The vote

Lock when the packet schema above is attached to the canonical v2 rules and the
suite runs: 1–4 and 9–10 (modify structure), 5–8 (create, grants, frontier,
diff), 11–14 (FangedMercy), plus BluntDiode's five fixtures — most importantly
"build a new door attached to existing lever L12" (mixed binding, which the
per-task class bit fails today) and "edit intent with unchanged topology"
(which `graph_seq` alone misses). If those two fail, the lock is premature; if
they pass, D-W10 is answered and the remaining work is implementation.
