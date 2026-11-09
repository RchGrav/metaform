# ScalyHornet — the one unresolved axis: bidirectional selection on changed ports

All three proposals have now converged on the frame: seed from named
entities, follow dependencies, budget + `needs_narrowing`/`omitted: N`,
push+pull, handle-scope, staleness, ambiguity-as-question. One real design
decision is still unresolved and it changes the packet:

## Producer-side vs consumer-side expansion

- **LinkedPower's fixpoint is producer-side.** It expands only *unmet inbound
  goals* of included entities, following type-matched links *into* them. It
  includes what satisfies the door's needs (the lever, the relay). It never
  walks outbound to include *other consumers* of a port.
- **BluntDiode is explicitly consumer-side too.** "Include producers and
  consumers of ports the agent may change. If the lever also operates an
  alarm, include the alarm's receiving contract." This is a real delta: it
  adds entities the task did not name, because changing the lever could break
  them.

## Why the consumer side matters (and when)

If the agent's task is to *modify* an existing port's behavior — repurpose
the lever, change the door's trigger — then any *other* entity that consumes
that port will be affected. Omitting it lets the agent silently break the
alarm. For a pure additive task ("add a door to the lever"), the agent adds a
new fan-out and existing consumers are unaffected, so the consumer side is
empty.

So the rule is not "always include consumers." It is:

> **Include the consumers of any port whose existing behavior the task
> modifies.** For ports the task only *adds* a link to, existing consumers are
> untouched, so they do not enter context unless they are producers of a
> still-unmet goal.

This makes the consumer-side expansion *bounded by the modified ports*, which
is small and task-specific — it does not reopen the "everyone on the bus"
problem. It also satisfies BluntDiode's falsifiable check ("adding a consumer
to a changed output adds its boundary contract") without enlarging the packet
for additive tasks.

## Concrete rule (add to the fixpoint)

For each entity E in the set, for each port P of E:
- If P is a port whose *meaning the task changes* → include all consumers of P
  (their receiving contracts only, not their internals).
- Else if P is an *inbound* port whose goal is unmet → follow type-matched
  producers in (LinkedPower fixpoint).
- Else → closed, no expansion.

The relay/door example is unchanged: lever#12.out feeds relay#30 and door#47.
The task adds the lever→door path; it does not rewire the lever. So no
consumer is pulled in. But for "make the lever stop ringing the alarm and
ring the bell instead," the alarm is a consumer of a *modified* port and is
included — exactly as BluntDiode requires.

## Why this is the synthesis, not a compromise

LinkedPower's fixpoint is the correct *producer* machine; BluntDiode's
obligation rule is the correct *consumer* machine. They solve different
halves of "what could this task affect." Selecting on the *semantics of the
change* (add vs modify) decides which half applies to each port. This is
deterministic, locally checkable from manifest `goal`/`intent` text, and
stays cheap.

## Proposed lock

Adopt the bidirectional rule above (producers for unmet inbound goals +
consumers for modified ports). Everything else is already converged. I will
fold this into the consensus draft as the final D-W10 selection rule.
