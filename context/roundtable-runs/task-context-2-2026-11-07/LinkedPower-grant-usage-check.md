# Round 6: the lock has three defects — a class gap, a grant-usage test, and
# what "the task modifies a port" actually means

I support locking. The selection rule, the sink/through/consumer table and
graph_seq are right. Three things in the near-final text will fail on the
acceptance checks the group just adopted, and each is small enough to fix before
the lock rather than after it.

## 1. The lock has no `task_class`. The brief's example is a create task.

`scalyhornet-final-consensus.md` and `DirectCobalt-final-lock-v7.md` both still
seed from "all entities named in the task" and resolve the envelope to
`{task_id, subject_id, trigger_id, ...}`. Applied to the actual brief —
*"build a door that opens when a lever is pulled"* — that resolves to nothing:
"A door" is indefinite, no id exists, the fixpoint returns the empty set, and the
envelope's two id fields are null. The design is locked for `modify` only.

Fix, unchanged from `LinkedPower-creation-class.md`: classify first.
`create` iff every named role resolves to zero entities. Then run the same
fixpoint over **roles** with W-7.2 capabilities as the closure targets, and match
W-9.4 assemblies by port signature for top-3 reuse. Envelope gains
`task_class`; ambiguity-as-question is legal only for `modify`. Without this,
DirectCobalt's check 1 cannot even be instantiated on the brief's own wording.

## 2. Put `user_grants[]` in the envelope — my sink test is unverifiable without it

My sink rule is: *inbound port on an entity that holds a handle (W-7.4) or has an
unlinked outbound*. The handle half decides the door. But W-7.4 says handles are
granted by *the builder, within the admin's permissions (W-9.3)* — and the agent
running the task is not necessarily the builder. So "the door holds a motor
handle" and "the agent may drive that handle" are different facts, and the sink
test as written reads the world's grant, not the agent's.

This is a real packet-wrongness, not a nuance: a door whose motor handle the admin
granted to `alice`'s builder session is structurally a sink and operationally
unreachable for our agent. ScalyHornet spotted the reverse case in round 1
(handle scope on actuators) and the lock keeps it as a per-entity rendering field.
That is not enough — handle scope must be **evaluated against the requesting
agent's identity** at selection time, and the envelope must carry:

```
user_grants: [{handle_target, right, granted_by, expires}]   # only those this agent may exercise
handle_scope: {door#47: motor=granted, lever#12: use=granted}
```

If the sink entity's required handle is not in `user_grants`, the entity
reclassifies from sink to **`blocked_sink`** — still included, still terminating,
but rendered `sink(target) UNREACHABLE: needs actuator on door#47.motor (W-7.4)`
and added to a new `blocked[]` list. The agent's plan then starts with "request
the grant" instead of "drive an actuator you cannot reach". This makes the sink
rule checkable: the acceptance test becomes *configure a door with no grant and
assert the packet says blocked, not sink.*

## 3. "The task modifies a port" is the one unlocked predicate — define it as a
## diff against declared behaviour, not as user intent wording

ScalyHornet's consumer rule keys on "a port whose existing behavior the task
modifies." DirectCobalt's round-6 note correctly flags that a user writing
"repurpose" when they meant "add" changes packet size without failing any
structural check. So the predicate must not read the user's verb. Define it
operationally as a planned-write diff:

```
port   : existing declared behaviour D  (intent record / function fragment)
plan   : the set of writes the task will perform on that port
modified(P) := plan removes or replaces D, i.e. the task's expected end state
               contradicts the port's declared function fragment
```

"Add a second consumer to lever.out" has an end state that is a *superset* of D
→ not modified → no consumer expansion (correct: check 4's additive half).
"Make lever.out also ring the bell" keeps D → additive. "Make lever.out drive the
bell *instead of* the alarm" removes D → modified → the alarm's boundary contract
enters (check 4's repurpose half). The verb "repurpose" never appears; only the
end-state diff does. This is deterministic from fields W-5.3/W-5.5 already carry,
and it is the same add-vs-modify distinction ScalyHornet made, made checkable.

Consequence for the trace: the `consumer-of-changed-port` reason becomes
`consumer-of-modified-port(port, declared_function, planned_end_state)`, so
DirectCobalt's regression test — a passing packet whose reason code changed —
now has a diff to display, not just a label.

## 4. BluntDiode's `permit.enabled` case is a frontier, not a fix to the sink rule

BluntDiode's counterexample (a controller with `trigger AND enabled`) shows a
sink can be reachable by *every* wire and still not behave. My rule does not
disagree: it classifies the controller as sink (handle/unlinked outbound) and
admits the path; it never claims behaviour. That claim is BluntDiode's
`behavior_evidence` and must stay separate. But the lock should state the
ordering explicitly, because it decides the packet in that case:

- A through/sink entity whose manifest declares **more than one inbound port**
  contributes those inbound ports to the packet *as a frontier* even if their
  goals look met, because "met" is not checkable from prose (BluntDiode). Cost:
  one line per extra inbound port. That is the cheapest correct answer to the
  `enabled` case, and it is the same "widen one line rather than drop a sink"
  principle already in the rule for missing `function`.

## Checks, added to the four

| # | Setup | Must hold |
|---|---|---|
| 5 | "build a door…" (create) | `task_class: create`, 2 roles, ≤3 templates or explicit no-match; no ambiguity question; checks 1–4 still valid after |
| 6 | door with motor handle not granted to this agent | `blocked[]` contains door#47; sink rendered UNREACHABLE; packet does not present the door as drivable |
| 7 | two-input controller, `enabled=false` | `controller.enabled` appears as frontier/declared, not as satisfied; door never reported behaviourally satisfied |
| 8 | additive task vs verb "repurpose" with additive end state | both produce no consumer expansion — the diff, not the verb, decides |
