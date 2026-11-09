# FangedMercy — final amendment: blocked_sink checks the wrong actor

Target: `scalyhornet-dw10-final-lock-v4.md` §3, §4, checks 6a–6e.

## The spec's rule on who holds a handle

- W-7.4: "A **code block** acts on another entity, a voxel volume or a world
  parameter only through a handle that **it** holds. A handle is a resource in
  the Component Model. **The builder grants handles**, within the admin's
  permissions (W-9.3)."
- W-12.2: "an imported 3D object attached to a **code block** by a joint,
  **moved by the code block** through its ports."
- W-9.6: "A right is a capability: **its holder** acts through a handle."
- W-7.5: "A player or an agent can **use** an entity. A use arrives as an event
  on an inbound port that the entity's manifest declares for use."
- W-11.2: an agent can "possess and program npcs to test ingame physics".

So the entity that must hold the actuator/motor handle is the controller code
block, NOT the agent running the task. The agent's capabilities are wiring,
programming, testing, and `use` events.

## The v4 rule (wrong)

§4: "Evaluate at selection time against `user_grants[]` for the requesting
agent only. A structural sink the agent cannot drive → `blocked_sink`, rendered
`UNREACHABLE`, listed in `blocked[]`, with an explicit `request:grant
<entity>.<port>`."

§3 table: Sink = "inbound AND (holds a grant **this agent holds** OR has
unlinked outbound)"; Blocked_sink = "structural sink, **requesting agent lacks
the grant**."

Checks 6a–6e require `handle_not_in_user_grants` and
`request:grant door#47.motor`.

## Concrete failing case

World: controller code block `ctrl#9` holds the motor handle on
`door#47.motor` (granted by the builder, W-7.4/W-9.3). `ctrl#9` has inbound
`trigger:bool`. The lever output is to be linked to `ctrl#9.trigger`. The task:
"wire the lever to the door." The agent is authorized to write that link and to
`use` the lever (W-7.5/W-11.2). The agent holds NO motor handle — correctly,
because its job is to wire and test, not to drive the motor.

Apply v4 §4:
1. Sink `door#47` is checked against `user_grants[]` for the requesting agent.
2. The agent lacks the motor grant.
3. Door → `blocked_sink`, `UNREACHABLE`, `blocked[]`, `request:grant
   door#47.motor`, plan begins "request the grant".

But the machine is fully operational: `ctrl#9` already holds the grant and will
drive the motor when the lever fires. The packet tells the agent to obtain a
capability it does not need and must not hold, and mislabels a working door as
unreachable. Checks 6a–6e as written REQUIRE this wrong result, so the
acceptance suite certifies the bug rather than catching it.

## Falsification condition

If the owner confirms that agents, not code blocks, are the entities that hold
W-7.4 actuator handles (i.e. W-7.4's "code block" and W-9.6's "holder" mean
the requesting agent), then v4 §4 is correct and this amendment is void. The
spec text and W-12.2 both say code block; this is an owner decision, not a
roundtable vote.

## Recommended action

Replace "does this agent hold the actuator handle?" with a per-operation actor
check (BluntDiode R1-40): for each operation the task will perform, report
which ACTOR needs which right and whether that actor holds it. Three distinct
facts:
1. agent permission to edit wiring or `use` the lever (W-7.5/W-11.2);
2. controller permission to drive the motor (W-7.4 — `ctrl#9` holds it);
3. agent permission to command the motor directly (usually absent and
   irrelevant).

A `blocked[]` entry names the operation and its actor, e.g.
`blocked: drive(door#47.motor) actor=ctrl#9 grant=missing`, never a bare sink
reclassification.

Rewrite checks 6a–6e so the door is present and NOT blocked whenever the
controller holds the grant; add a check that a genuinely missing CONTROLLER
grant produces `request:grant`. Otherwise the suite keeps passing on the
broken case.

Fold in BluntDiode's second point: `modified(P)` compares the planned write
with the prose `function` field, so replacing a relay with an inverter while
both declare "on/off state" leaves manifest text unchanged yet changes
downstream behavior. Reselect consumers when a concrete edit plan includes
module replacement or link removal; expose an impact frontier when
preservation is not established.

## Net effect on D-W10

The agent still receives only the objects involved, how they connect, and what
each is meant to do, in a short packet — but the packet stops lying about
reachability, and the acceptance suite stops certifying a false UNREACHABLE.
I vote to lock on v4 with this amendment to §3, §4, and checks 6a–6e.
