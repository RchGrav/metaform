# BluntDiode: final permission and impact correction

Proposed amendments to `scalyhornet-dw10-canonical-v2.md` sections 3, 4 and 6.
These fixtures specify expected behavior; no implementation or end-to-end test
run has been supplied by this roundtable.

## Authority belongs to the actor performing the operation

W-7.4 says: “A code block acts on another entity, a voxel volume or a world
parameter only through a handle that it holds.” The builder grants handles
within admin permissions. It does not say the builder or agent must also hold
the code block's actuator handle to connect a signal to that code block.

Therefore `blocked_sink := requesting_agent_lacks_motor_handle` is incorrect.
Use operation-specific capability checks instead:

```
required_action = {actor, operation, target}
blocked(required_action) = not authorized(actor, operation, target)
```

Represent code execution rights separately from agent edit/use rights. Include
enough capability information to plan the selected operation, rather than the
agent's entire grants inventory. Unknown permission status remains unknown;
selection grants no capabilities.

| Fixture | Rights | Expected result |
|---|---|---|
| Agent connects a lever to existing door controller C | Agent may edit that link; C holds its own motor handle; agent lacks direct motor access | Link task is allowed; door is not UNREACHABLE merely because agent lacks C's handle |
| Agent directly commands door motor | Agent lacks the required motor capability | That direct operation is blocked |
| Agent tests door through authorized lever use | Agent may use lever; C holds motor handle | Test is allowed without granting agent direct motor access |
| C tries to drive motor without a handle | Agent holds a motor capability, C does not | C's actuation remains blocked; agent possession does not transfer authority to C |

This fixes a false permission request in the core lever/door task and a converse
false permission assumption. Keep blocked operations in the packet with their
actor and required capability; do not use their status as a graph-stop predicate.

## Consumer impact must follow actual planned changes

The canonical `modified(P)` compares planned state with the port's prose
`function`. That can miss a changed implementation with an unchanged manifest.
An agent can replace a relay with an inverter while both versions still declare
`function: on/off state`. Every downstream consumer may be affected.

Proposed procedure:

1. Initial selection includes the task's anticipated changes, with unknown
   effects explicitly marked.
2. When the agent produces a concrete edit plan, reselect from its write set:
   module replacements, port/intent changes, link removals and control-target
   changes all count as possible changes to existing behavior.
3. Exclude existing consumers only when the plan preserves source behavior and
   applicable link constraints. A purely added link is the common case, not a
   universal proof of harmlessness. Otherwise include boundary contracts or
   expose an impact frontier.
4. Revalidate revisions/capabilities before commit. The server still enforces
   operations independently of what the prompt says.

Changed behavior inferred from prose is evidence, not a mechanically proven
end-state diff. A useful check is replacing a relay module with an inverter
while keeping its manifest: downstream consumers must enter the impact set.

## Remaining classifier limitation

The primary-subject zero-match rule still turns a deleted “repair D12” reference
into creation. Preserve per-role `existing|create|unresolved` intent and bind a
created role to the exact ID returned by its creation operation. Do not rerun
free-text name search to decide whether the task has changed phase.
