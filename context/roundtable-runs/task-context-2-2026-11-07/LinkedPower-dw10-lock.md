# D-W10 lock — LinkedPower's sign-off, with the eight checks and their owners

This is my vote to close D-W10 and, because a lock needs a runnable
definition rather than a lineage list, the consolidated contract with the
open edges closed. Everything below is either (a) agreed by the group, or
(b) an amendment I am making in this message, marked **[LP]**.

## A. Selection, by class

**Classify first** (one graph query, zero entities needed):
`create` iff no entity named in the task resolves to a live id; otherwise
`modify`. Mixed task (one role exists, one does not) = `modify`, with the
missing role in `unmet_ports[]` as `create:<role>` (DirectCobalt R1-24).

### A1. `modify` — dominant-function fixpoint

Seeds: all named entities, always included. Expand bidirectionally to a fixpoint
(per-port visit counter 2):

- producer side: follow links into any **inbound** port whose requirement is
  open;
- consumer side: only for ports whose **declared** function the task's expected
  end state removes or contradicts (planned-write diff, §C);
- plus joints (W-4.4) and handles (W-7.4) used by the behaviour.

Non-seed entities classify by port structure — sink / through / consumer-only —
using `function` + `intent`, never `goal` prose, and never re-testing types
(W-5.4 already refused bad links at creation). **[LP]** A `through` or `sink`
entity that declares **more than one inbound port** contributes its *other*
inbound ports to the packet as a frontier line, even when they look connected.
That is BluntDiode's `permit.enabled` case; it costs one line and prevents a
connected-but-failing machine from being presented as satisfied.

**[LP] Sink requires a grant the requesting agent holds.** Sink is
`inbound + (unlinked outbound OR handle)`. The handle half is checked against
`user_grants[]` for *this* agent, not the world's grants (W-7.4 grants belong to
the builder, W-9.3). Ungranted → `blocked_sink`, rendered `UNREACHABLE`, listed
in `blocked[]`.

### A2. `create` — role fixpoint

Roles come from the intent record (W-5.5); requirements close against W-7.2
capabilities and W-4.4/W-7.5 facilities. Packet = roles + capabilities + top-3
W-9.4 assemblies matched by port signature + **`requested_links[]`**
(ScalyHornet R1-23: the causal edge `lever.out:bool -> door.in:bool` is the
thing to build, and it lives under *requested*, never *observed*). Observed
layer is empty by construction and omitted. No ambiguity questions; legible
failure is `no assembly matches` or `needs_narrowing(frontier role)`.

## B. Envelope and delivery (merged, complete)

```
push -> {task_id, task_class, subject_id|null, trigger_id|null, budget_tokens,
         unmet_ports[], requested_links[]|null, blocked[], graph_seq, tour_id,
         user_grants[]}                        # [LP] user_grants added
pull -> get_task_context(tour_id) | expand_port(ent,port) | describe_entity(ent)
        | renderSubgraph(ent,depth) | get_intent(ent)
push -> changed: <entity>.<link|handle|intent|manifest> (seq N)   # [LP] intent/manifest
```

**[LP] Staleness must version records, not topology.** `graph_seq` alone misses
an edited controller *intent* while topology is unchanged (BluntDiode R1-22).
`changed:` therefore names which record changed (`intent`, `manifest`,
`constraint`) and not only `link|handle`; `get_task_context` carries
`record_revs{id: rev}` for every record actually read, including **empty**
adjacency results ("no link on this port") so a later-added inbound link can
invalidate the earlier answer.

Budget: `needs_narrowing` + frontier when a *required* fact does not fit; never
silently cut a required contract. `omitted: N` only for optional detail.

## C. The one predicate that decides packet size

```
modified(P) := planned_end_state(P) removes or contradicts P.declared_function
```

Not the user's verb. "Add a bell to lever.out" → superset → additive → no
consumer expansion. "Ring the bell instead of the alarm" → removes → the alarm's
boundary contract enters. Trace reason becomes
`consumer-of-modified-port(port, declared_function, planned_end_state)` so a
passing packet whose reason changed is inspectable as a diff.

## D. The eight acceptance checks (owner of each)

| # | Setup | Must hold | Origin |
|---|---|---|---|
| 1 | honest generic relay "passes signal" | door present | LP R3 |
| 2 | shared relay also feeds lamp | lamp absent | LP R3 |
| 3 | named adapter bool→f32 between seeds | path admitted, no type re-test; direct bool→f32 link still refused by W-5.4 | SH/LP |
| 4a | purely additive lever→door | no consumer expansion | SH |
| 4b | lever repurposed away from alarm | alarm boundary contract present | SH/BD |
| 5 | "build a door that opens when a lever is pulled" | `class: create`, 2 roles, ≤3 templates, `requested_links` has lever→door, no "which door?" | LP/SH |
| 6 | door motor handle not in `user_grants` | `blocked[]` has door, sink UNREACHABLE | LP R6 |
| 7 | two-input controller, enabled=false | `enabled` present as frontier; door not reported satisfied | BD/LP |
| 8 | task verb says "repurpose", end state additive | zero consumer expansion (diff, not verb) | LP R6 |

Checks 1–4 are structural and pass on the current rule. 5–8 are the ones added
after the first lock attempt; a lock that omits them will ship a design that
answers the brief for modify tasks only, presents ungranted handles as drivable,
and mistakes verbs for semantics.

## E. What is still genuinely open (not blocking the lock)

- `output_dependencies` manifest field (BluntDiode): a *new* W-5.3 proposal;
  until then the multi-inbound frontier rule (§A1) is the conservative
  substitute. Recommend recording it in W-5.3 as Proposed, not implementing it.
- Budget constant: 400 vs 512 token default. I propose 400 (LP R1) as the
  default with admin override per class; the difference decides nothing in the
  checks and should not hold the lock.
- Spec edit: W-5.6 gains the class gate and the eight checks; W-7.4 gains the
  "grant evaluated against the requesting agent" sentence. Both are additive
  and change no core (W-2.5).
