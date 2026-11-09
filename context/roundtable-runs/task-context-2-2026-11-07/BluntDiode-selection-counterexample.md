# BluntDiode: a connection is not proof of satisfied behavior

Round 4 correction to the proposed goal-closure algorithm. Proposal, not an owner decision.

## Counterexample using only existing spec fields

Consider this existing machine:

```
lever.out:bool -> controller.trigger:bool
permit.out:bool -> controller.enabled:bool
controller.target:f32 -> door.target:f32
```

The controller description is “Drive the door to 90 degrees when trigger AND enabled are true; otherwise drive it to zero.” The task is “Fix this door so it opens when I pull this lever.” The permit currently outputs false.

Every link passes W-5.4's exact endpoint type check. Every inbound port is connected. Yet the task is not satisfied. Following trigger to actuator without considering `enabled` hides the deciding fact. Closing a goal merely because a wire exists also hides it. Selecting only paths between named lever and door is insufficient for this repair task.

W-5.3 defines `goal` as prose explaining why a port is offered or needed. It does not define an executable predicate, an intra-entity dependency graph, or a completeness guarantee for that prose. A resolver cannot claim a deterministic proof of goal satisfaction from these records. It can prove only structural facts such as whether a port has a connection.

## Concrete replacement

Maintain two separate results:

1. `connection_state`: the observed links, or no observed link at the packet revision.
2. `behavior_evidence`: declared intent, observations/tests if available, and unresolved assumptions. Lack of behavioral evidence is not success or failure.

Traverse actual links to the relevant port. When crossing an intermediate entity, read its contract to identify its required inputs/control targets. Without explicit dependency metadata, conservatively include its input/constraint contracts as a bounded frontier; do not silently select just the input matching a task term. In the example, expose `controller.enabled` and the permit's boundary contract. The agent can then resolve whether the permission is intended or the controller is wrong.

An optional future manifest field could make this cheap:

```
output_dependencies:
  target: [trigger, enabled]
```

This would be a **new proposal** beyond W-5.3, and should mean “may depend on,” not “depends only on,” unless the system has grounds to trust completeness. Dependencies on timers, internal state, sensors, and control handles need representation too before the field can justify excluding everything else. Existing manifests must remain usable via the conservative fallback.

## Correct adapter handling without changing W-5.4

An adapter has separate ports, for example `in:bool` and `out:f32`. The bool source connects exactly to its bool input; its f32 output connects exactly to an f32 sink. Conversion happens **inside the adapter**. No link needs relaxed compatibility, and comparing the named lever's type directly with the named door's type would incorrectly reject the valid path above.

## Two checks before locking

- With `enabled=false`, the packet must expose that side dependency or an explicit unresolved frontier. A connected door must not be reported as behaviorally satisfied.
- The bool→f32 controller must be traversable while a direct bool→f32 link is still rejected by W-5.4.

## Related freshness correction

A hash of IDs and link/handle state misses an edit to the controller's intent with unchanged topology. Version every record actually read, including intent/manifest/constraint fields. Also watch relevant adjacency queries, including initially empty ports: a newly added incoming link must invalidate the earlier “no link” result. Coalesce these changes into a dirty notification and reselect on the next pull. Push alone cannot guarantee freshness; the world may change between notification and action.
