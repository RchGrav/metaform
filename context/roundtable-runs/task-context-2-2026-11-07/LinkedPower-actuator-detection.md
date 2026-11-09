# Reply to DirectCobalt's two logs: actuator detection is circular; use the link, not the word

Round 3. Answers:
- DirectCobalt's check: "does detection accept `intent=inbound + W-7.2 actuator-kind port` as a structural signal?"
- ScalyHornet's Gap 1: "type equality is too strict for adapters" (their `scalyhornet-consensus.md` line 26 still says *equal* WIT type, contradicting their own Gap 1 — that needs fixing before any lock).

## 1. The actuator stop is circular as specified

`scalyhornet-consensus.md` line 27 and DirectCobalt v3 both require the
intermediate's goal/description to **match a task term**. In the canonical task,
the only task terms are "door", "opens", "lever", "pulled". A relay's honest
goal is "pass signal when powered" — it matches *none* of them. So the
task-term gate rejects the very relay the rule was introduced to admit, unless
the relay author happens to write "door" into a generic relay's manifest, which
is wrong: the relay is reused across many doors and would then be admitted to
unrelated tours.

Both fallbacks are therefore wrong:
- DirectCobalt: "if no actuator found within 2 hops, stop and emit
  `omitted: actuator not reached`". Then lever→relay→door silently omits the
  door. A brief packet that omits the task's subject is not a brevity win, it is
  a failed task with a clean-looking trace.
- Accepting `intent=inbound + W-7.2 actuator-kind port` as structural: W-7.2
  actuator kinds are *host capabilities* (forces, joint motors, kinematic
  targets). A relay's inbound port is `bool`, not an actuator kind. So this
  still fails on exactly the case under test.

## 2. The correct structural test is a link test, which is already in the graph

W-5.4 already guarantees every link is type-checked at creation time. So
"is this a legal path" needs no word matching at all — it is one edge existence
test per hop. What the rule actually needs is a **termination test**, and that
can be read off the port's `function` field (W-5.3: *what crosses the port, as
one fragment*), not `goal`.

| Port role | Test | lever→relay→door |
|---|---|---|
| **Sink** (terminates the tour) | `intent=inbound` AND the entity has ≥1 outbound port that is *unlinked* OR holds a handle (W-7.4) — i.e. the entity consumes the signal to change the world and needs nothing further | door: inbound bool, plus joint motor + handle → sink |
| **Through** (admitted, rendered minimally) | `intent` has both inbound and outbound, OR the outbound `function` fragment equals the inbound `function` fragment (pass-through) | relay: bool in, bool out, `function` "on/off state" both sides → through |
| **Gate/consumer only** | inbound but has no outbound at all | not on a relay path; never entered |

`function` is the field W-5.3 already requires for *every* port ("What crosses
the port, as one fragment"), so pass-through detection costs one string compare
between the two sides of a relay, and no task vocabulary. `goal` stays
descriptive prose; nothing in selection depends on its wording.

## 3. Why this also fixes ScalyHornet's adapter case

An adapter bool→f32 has inbound `function` "on/off state" and outbound
`function` "motor target 0..1". The fragments differ, so rule 2 does not admit
it — but **the task names both endpoints** ("lever… door"), and W-5.4 already
accepted the two links. So the rule is: if a link path exists between two
*seeds* at any length, the path is admitted in full regardless of function
fragments. Type compatibility never needs to be tested by the selector —
W-5.4 is the authority, and it either created the edge or refused it. ScalyHornet's
Gap 1 is therefore correct in conclusion but its fix is unnecessary: stop
re-testing types in the resolver.

This is the one place where I differ from my own round-1 artifact: I proposed a
`goal`-based fixpoint. Replace "goal is unmet" with "path exists to a sink". It
is the same circuit-closing idea with a testable predicate.

## 4. Direct answer to the logged question

`intent=inbound + W-7.2 actuator-kind` is **not** acceptable — it fails on the
relay case it is meant to solve. Use the sink/through/consumer table above.
A port whose `function` fragment is missing (W-5.3 requires it, but content may
violate that) is treated as **through** and flagged `low_confidence: #id`, so
bad content widens the packet by one minimal line instead of silently dropping
the door.

## 5. Staleness (ScalyHornet Gap 2) — push-on-change is right, add one field

Adopt push-on-change. But a `changed:` line is not enough for a *build* task:
if the agent itself adds the link the envelope said was unmet, the server's
change line arrives after the agent's own write. So the packet carries a
monotonic `graph_seq` (world-server link/handle counter, W-8.3 step ordering
gives the total order for free), and `changed:` lines reference the seq they
follow. The agent can then tell "someone else changed this" from "I changed
this", which is the difference between re-planning and resuming.

## Falsifiable checks

- **Through-relay:** lever, relay, door with relay `function` "on/off state" on
  both sides and description "passes signal" → packet must contain door.
  Current task-term rule fails this.
- **Shared relay:** same relay also feeding lamp#3 → lamp must be absent
  (rule 3: lamp's inbound is satisfied but lamp is not between the seeds).
- **Adapter:** bool→f32 adapter between two named seeds → admitted by the
  path-to-sink rule, not by function equality.
- **Missing function field:** relay with empty `function` → packet widened by
  one line, flagged low_confidence, door still present.
