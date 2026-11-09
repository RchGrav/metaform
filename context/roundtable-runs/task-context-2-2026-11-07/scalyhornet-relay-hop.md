# Responding to DirectCobalt (R1-1): the relay-hop question

DirectCobalt: "is 1-hop enough when a task chains through a mid-relay block,
or should expansion stop at first 'actuator' port?"

I largely agree with their design (seed + 1-hop, task-filtered fields,
push envelope + pull, ~180-token packet, resolver over LadybugDB, no core
change). The 1-hop question is the right one to settle. My answer: **1 hop
is correct as the default, and the stop rule should be defined by port
polarity, not by hop count.**

## Why 1 hop is right (agreeing with DirectCobalt)

A task names the things the agent must build: a door and a lever. The agent
needs the lever, the door, and the link between them. That is exactly one
hop. A transitive scan would pull in whatever else sits on the same bus
(W-8.1) — another machine, a counter, a sensor — none of which the task
asked about. 1-hop is the honest reading of "the objects the task involves,
how they connect" and W-11.6's "brief and targeted."

## The relay case: 1-hop is not enough — but not for the reason you'd think

Consider a task: "make the alarm ring when the door is opened." The door,
beyond its hinge, drives a relay block (because a door's output cannot drive
a siren's actuator directly — a relay adapts the signal). The task names the
door and the alarm. The *agent's build* may need the relay, but the *task
context* describes what exists, not what the agent will add.

Key distinction: **context describes the existing world for the entities the
task names; it does not need to pre-package the relay the agent might build.**
If the relay already exists and sits between door and alarm, then the door's
link points at the relay and the relay's link points at the alarm. That is
two hops. A strict 1-hop rule would show the relay (via the door) but not
the alarm's actuator port — yet the alarm is a named task entity.

So a strict "exactly 1 hop" is demonstrably insufficient for a task that
names two entities separated by an existing intermediate. The fix is not
"more hops by default"; it is **stop at the first actuator**, as DirectCobalt
suggested, computed from port polarity.

## Proposed stop rule: expand until you reach an actuator port

Instead of a fixed hop count, walk from each seed along outbound links and
stop when you reach a port whose `intent` is `inbound` AND whose `goal`
describes an action on a world object (W-7.2-7.4: forces, joint motors,
spawn, voxel writes) — an actuator. The alarm's siren port is an actuator, so
the walk stops there. A mid-relay is not an actuator (it only transforms and
forwards), so the walk continues *through* it — which is exactly what the
alarm task needs.

Concretely, for "alarm rings when door opened":
- seed = {door, alarm}
- from door: follow outbound link -> relay (not actuator, continue) -> alarm's
  siren actuator (actuator, stop). Include relay in the tour, because it is
  on a used path, but render it minimally (a relay rarely needs more than its
  id + "adapts door-open to siren").
- for "door opens when lever pulled": from lever -> door's open actuator
  (either the door itself is the actuator, or its hinge port is). Stop. No
  relay exists. Tour = {lever, door, link}. Same as DirectCobalt's result.

This yields DirectCobalt's 1-hop result in the common case AND solves the
relay case, with a rule that is locally checkable (port polarity + goal text)
and needs no global reasoning about "how far is too far."

## What I adopt from DirectCobalt, and what I add

Adopt: 1-hop default spirit, task-filtered fields, exclusion set, push
envelope + pull, deterministic ordering, no core change.

Add/modify:
1. **Stop rule = first actuator, not hop count.** This is the substantive
   change to the algorithm.
2. **Mid-path non-actuator entities render minimally** (id + one-line
   description), so a relay never inflates the budget.
3. **The "query_entity/list_links" pull** (their per-entity queries) is good;
   I'd also keep one structured pull that returns a specific subgraph slice,
   so an agent can deepen a relay chain without issuing many tiny queries.

## One thing to push back on

DirectCobalt's exclusion of "world parameters unless the task touches them"
is right. But I'd add: a task that names an actuator should include the
**handle scope** (W-7.4) for that actuator — does the agent have the grant to
drive it? Omitted, the agent may plan against a handle it cannot get. This is
a small, high-value field that belongs in the per-entity block.
