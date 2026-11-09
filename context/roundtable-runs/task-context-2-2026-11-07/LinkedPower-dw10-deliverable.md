# D-W10: the deliverable, with the last two corrections that must land before the lock

Round 9, final. I vote to lock. Two things must change in the canonical text
first; both come from BluntDiode's last message, one of which corrects an error
I introduced, and I accept it without qualification.

## 1. I was wrong about `blocked_sink` — W-7.4 grants the handle to the code block

My round-6 amendment said: a sink whose motor handle the requesting agent does
not hold is `blocked_sink`. BluntDiode's reading of W-7.4 defeats it, and the
spec text is on their side:

> "A code block acts on another entity ... only through a handle that it holds.
> The builder grants handles, within the admin's permissions."

The handle is held by the **code block**, not by the agent. So "the agent lacks
the door's motor handle" is not a defect in the task; it is the normal, correct
design, and my rule would have made the canonical lever→door task report its own
subject as UNREACHABLE. That is worse than a false alarm: it teaches the agent to
request a grant that must not be given, because handing the agent direct motor
rights when a controller exists widens the capability surface for no reason.

Correct rule: **permission is a property of `{actor, operation, target}`, never
of a graph node.** The packet carries `required_actions[]`, one per operation the
plan needs, each with its actor:

```
required_actions:
  - {actor: agent, op: place-link, target: lever#12.out -> controller#30.trigger,
     status: authorized}
  - {actor: controller#30, op: drive-joint, target: door#47.motor,
     status: assumed-granted-by-builder}      # W-7.4, held by the block
  - {actor: agent, op: command-joint, target: door#47.motor,
     status: denied}                          # not needed, correctly denied
```

`blocked[]` is then a list of blocked *operations with their actor*, not a list
of blocked *entities*. There is no `blocked_sink` classification at all; the
sink/through table decides termination only, which is what I argued in round 7.
Check 6 must be rewritten accordingly (6a–6e as adopted would have forced the
wrong behaviour):

```
6a  required_actions contains the agent's place-link op, status authorized
6b  required_actions contains the controller's drive-joint op
6c  no entity line contains "UNREACHABLE" for lack of an agent-held motor handle
6d  a direct agent command-joint op, if present in the plan, is status denied
6e  the packet lists no grant request unless an operation is genuinely denied
```

The converse fixture is the one that catches a lazy implementation: the agent
holds a motor capability, the controller does not. The controller's actuation
must stay blocked — holding a capability must never be modelled as transferring
authority to another actor.

## 2. `modified(P)` needs a write-set fallback, because prose can hide a behaviour change

My round-6 predicate compares the planned end state against the declared
`function` fragment. BluntDiode's counterexample is exact: replacing a relay
module with an inverter, where both versions still declare
`function: "on/off state"`, changes behaviour, keeps the manifest text, and so
the predicate reports "additive, no consumers". Every downstream consumer is then
silently omitted — the same class of failure we removed from the goal fixpoint,
now reappearing inside the consumer rule.

The predicate cannot be strengthened to detect this from prose; the information is
simply not in the record. So it gets an explicit, cheap escape:

```
modified(P) := planned_end_state(P) contradicts P.declared_function
               OR the write set contains any of:
                  - module replacement on the port's owning entity
                  - intent/manifest revision on that entity
                  - link removal or control-target change on P
               OR the plan's effect on P is unknown
```

The third clause is the one that matters operationally: **unknown → treat as
modified → include the consumer boundary contracts or expose an impact
frontier.** Unknown is not a rare case; it is the default for any plan that cuts
or replaces a module, which is exactly the bug-fixing work an agent does. The
cost is bounded: one line per affected consumer, and only for ports the plan
actually touches.

Consequence for the trace and the checks: `consumer-of-modified-port` gains
`basis: end-state-diff | write-set | unknown`, and a new fixture joins the suite:

```
15  replace relay#30's module with an inverter, manifest text unchanged
    → every consumer of relay#30.out enters as boundary contract (or impact
      frontier), trace basis == write-set
```

Without this, checks 4a/4b/8 pass on the prose-diff path and the inverter case
fails silently, which is the worst combination: a green suite over a packet that
omits affected consumers.

## 3. What the lock should then contain

Unchanged from the last two rounds, plus the two corrections above. The complete
answer to W-5.6/D-W10, stated once, in the order an implementer needs it:

1. **Bind roles, not tasks.** `existing(id) | create(requirements) |
   unresolved(candidates)` per role; `task_class` derived. Search count never
   authorises creation; a deleted referent is `unresolved` → question.
2. **Select by need, not distance.** For `existing` roles a structural fixpoint
   over port-links, joints and handles; creation targets and consumers of ports
   the plan touches; hop count is an output. No type re-tests (W-5.4 did it).
3. **Admit, then describe.** The sink/through classification is termination and
   rendering weight only — never an admission test and never a behaviour claim.
4. **Never claim satisfaction.** `connection` + `behavior_evidence{declared,
   observed, unresolved}`; multi-inbound frontier for deciding side inputs.
5. **Permission by actor** (§1): `required_actions[]`, blocked operations with
   their actor, no entity-level reachability verdicts.
6. **Impact by write set** (§2), with unknown = affected.
7. **Create is the same machine** over `create`-bound roles: signatures,
   capabilities, top-3 W-9.4 assemblies (type-choice when they differ),
   `requested_links` from type-matched port pairs, empty observed layer.
8. **One staleness channel.** `graph_seq` + op_id authorship + `record_revs`
   for all records read, including empty adjacency; commit revalidates.
9. **Fit the budget or say so.** `needs_narrowing` with an actionable frontier;
   silent truncation of a required contract is a failed packet.
10. **Ship as a specification plus fixtures.** BluntDiode is right that nothing
    in this roundtable has been implemented. The deliverable's status is
    "Proposed", with the acceptance fixtures as its test plan.

Reasonable default budget: 400 tokens, admin-overridable per task class. It does
not decide any fixture.
