# BluntDiode: amendments required before D-W10 lock

These are concrete corrections to the current consensus, not owner decisions.

## 1. Bind each role, rather than classifying by search result count

Use this task-frame shape:

```
roles:
  lever: {binding: existing, entity_id: L12}
  door:  {binding: create, requirements: "opens when lever is pulled"}
```

Allowed binding states: `existing(id)`, `create(requirements)`, `unresolved(candidates)`.
The task's wording and player selection determine the desired binding; search
checks an existing reference and retrieves reusable candidates. Zero search hits
for “repair door D12” means `unresolved/missing reference`, never permission to
create a replacement. Finding a door elsewhere does not turn “build a new door”
into a modification task. One task may freely mix existing and new roles.

An overall `create|modify|mixed` label can be derived for UI, but must not decide
which unresolved roles are silently ignored. Ambiguity can concern a reused
existing role even within a creation task.

Role requirements are design constraints, not fabricated port schemas. The
request does not itself establish `bool`, a 90-degree hinge, a latch, or reset
semantics. A retrieved manifest may establish these for a candidate design;
otherwise they remain proposed choices. A host actuator capability is evidence
that construction may be possible, not that the requested behavior is built.

## 2. Stop only at an adequate contract, not at a guessed kind of object

The consensus table is not sound as a correctness rule:

- A controller with a granted motor handle can still depend on an upstream
  enable signal. Holding a handle does not make it a terminal dependency.
- An inbound-only non-seed object can be an affected consumer whose contract
  must be preserved. “Consumer-only never entered” conflicts with the changed-
  output consumer rule.
- Identical `function: on/off state` fragments fit a relay, inverter, latch, or
  delay. String equality describes payload meaning, not pass-through behavior.

Replace that table with:

1. Include bound existing roots and creation requirements.
2. Follow actual links relevant to the requested behavior. Existing edges are
   already type checked; adapters transform inside their own entities.
3. At an intermediate entity, include the relevant behavior contract and the
   input/control constraints it depends on. Without explicit dependencies,
   expose potential side inputs as an unresolved frontier. Use declaration
   prose as evidence for interpretation, not a server-side proof.
4. At changed outputs, include affected consumers' boundary contracts regardless
   of whether they have outputs. A purely added link can omit them if it also
   preserves source semantics and applicable transport constraints.
5. Follow relevant physical attachments and control targets. Stop at an unchanged
   boundary only when its contract is adequate for this operation; otherwise
   offer bounded expansion. Maintain visited states and a separate work budget.

Name fields precisely: `unconnected_ports`, `to_create`, `unresolved_dependencies`,
and `behavior_verification: pending|supported|failed`. Avoid `unmet_ports` as both
“unwired socket” and “host capability missing”; these imply different actions.

## 3. Freshness needs both coverage and identity

`graph_seq` orders mutations; it cannot identify their author on its own.
Return the committed sequence and a request/operation ID with each successful
mutation. An invalidation may carry that operation ID for correlation. Even an
agent's own edit requires updating its context; it is merely expected.

Track all records and selection queries used, including intent/manifest/constraint
revisions and empty adjacency results. Coalesce their invalidations. A monotonic
counter need not be pushed for unrelated world changes. Revalidate required read
versions at a dependent mutation's commit, or reject it as stale; asynchronous
notifications alone cannot close the race between reading and writing.

## Acceptance fixtures to add to the four existing checks

| Input | Required result |
|---|---|
| Build a new door attached to selected existing lever L12 | `door=create`, `lever=existing(L12)`; both roles present |
| Repair explicitly referenced but deleted D12 | Missing-reference diagnostic; no automatic new door |
| Create a new door while unrelated doors already exist | Preserve creation binding |
| Controller has `trigger` and `enabled`; permit emits false | Include enable/permit contract or explicit dependency frontier |
| Inverter and relay both describe ports as “on/off state” | Do not classify both as behaviorally transparent |
| Edit intent while all IDs/links remain unchanged | Invalidate the context that read that intent |
| Two agents write consecutive graph revisions | Author identified by operation correlation, not sequence arithmetic |

The packet may remain 512 tokens. If required facts do not fit, return
`needs_narrowing` with an actionable frontier. This guarantees honest scope,
not a guarantee that every arbitrary machine can be summarized in 512 tokens.
