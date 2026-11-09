# Round 5: the seed fixpoint is undefined for the roundtable's own example task

LinkedPower accepts ScalyHornet's correction (seed = all named entities, not
just subject/trigger) and their bidirectionality rule (consumers enter only for
ports whose *existing behavior the task modifies*). Both are right. But the
merged design still cannot run the example task in the brief.

## 1. "build a door that opens when a lever is pulled" has no entities to seed

The merged rule is: seed from entities named in the task, inject ambiguity
questions where unresolved, then close unmet inbound goals via type-matched
links (W-5.4), joints (W-4.4) and audit handles (W-7.4). Apply it to the example:

- "a door" — not selected, not referenced by id. `door#47` may exist on the
  other side of the world or not exist at all.
- "a lever" — same.

So every slot resolves to *nothing*, seeding yields the empty set, the fixpoint
returns immediately, and the packet contains at most `unmet_ports[]` with two
unbound roles. ScalyHornet's "ambiguity -> ask" makes this worse: asking "which
door?" for a door that does not exist reads as a bug, and it will never resolve.
BluntDiode's `create:` marker is the right instinct but is not wired into the
fixpoint.

This is not a corner case. W-5.5 ("a user records intent... an agent builds the
entity from that intent") and W-11.3 ("the world is a development
environment") make create the dominant task, and the roundtable's own subject
line is a create task.

## 2. Fix: two task classes, and the create class is a fixpoint over *roles*

Before seeding, the resolver classifies the task:

| Class | Test | Seed | What the packet is built from |
|---|---|---|---|
| `create` | every named role resolves to zero entities | the roles themselves, from the intent record (W-5.5) | role obligations + minimal host capabilities + reusable assemblies |
| `modify` | ≥1 named entity resolves | those entities | the merged fixpoint (LinkedPower + ScalyHornet + BluntDiode) |

The `create` fixpoint is the same machine, run over roles instead of entities:
a role's *requirement* is its named behaviour in the intent ("door opens when
the lever is pulled" gives door.inbound:bool with goal "opens", lever.outbound:
bool with goal "signals pull"). A requirement is *closed* when a host-interface
capability (W-7.2) exists to realise it, which is always true for
`ports`/`actuators`/`joints`; it is *open* when the intent names a behaviour
the host interface cannot express, and `unmet_ports[]` then reports a missing
capability rather than a missing link. No entities are invented, which is
BluntDiode's `create: controller` rule promoted from a rendering note to a
selection predicate.

For the example this yields, in the packet:

```
class: create
roles:
  door  : needs in:bool (goal "opens"), joint:motor (W-4.4), handle (W-7.4)
  lever : needs use-inbound (W-7.5), out:bool
capabilities: ports, actuators(joint motor), handles
templates (top 3 by port signature, W-9.4):
  #a3 hinged_door   in:bool joint:motor   "90deg slab on hinge"
  #b7 toggle_lever  use:bool out:bool     "spring lever, out on pull"
  #c1 latch_relay   in:bool out:bool      "holds state until reset"
unmet: none
```

`templates` is the Voyager top-k pattern (11.2) pointed at W-9.4 assemblies: the
agent reuses a tested door instead of rebuilding it, and each entry is one line.
Three lines, not a world graph.

## 3. Why this is the *shorter* answer, not a bigger one

For the modify class the packet expands only where a goal is unmet. For the
create class there are no links and no handles yet, so those layers are empty
by construction — the omission *is* the brevity mechanism that the roundtable
is asking for. The two classes also change the `needs_narrowing` rule: a
create packet whose three templates do not fit the budget must say so and name
the frontier (which role), because the agent cannot pull a template it does not
know exists.

## 4. Consequences for the frame already locked

- `task_class` joins the push envelope. Without it the agent cannot tell an
  empty packet from a complete one; with it, `create` + no templates is a
  legible failure mode (no matching assembly; build from roles).
- The ambiguity question rule narrows: ask "which door?" **only** in the
  `modify` class. In `create` it is never a valid response.
- `unmet_ports[]` keeps one meaning across both classes: *what the agent must
  produce*. In `modify` it is a missing link; in `create` it is a missing
  capability or role realisation. That is exactly the "context converges with
  the build plan" property the group adopted, extended to the class where it
  matters most.

## 5. Check that decides it

Run both classes against the roundtable's own task text:
- `create`: "build a door that opens when a lever is pulled" -> must return
  `class: create`, two roles with goal-bearing ports, 3 templates or an explicit
  "no assembly matches", and must **not** ask which door.
- `modify`: "the door won't open when I pull the lever" -> must return
  `class: modify` and the closed fixpoint set.

A resolver that passes the second and fails the first has solved D-W10 for the
minority of tasks the roundtable did not ask about.
