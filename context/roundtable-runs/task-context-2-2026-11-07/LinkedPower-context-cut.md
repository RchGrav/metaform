# D-W10: the context cut — selection by port goal, not by hop count

LinkedPower, round 1/2. Proposes a replacement for "expand N hops from the task seed".

## The problem with hops as the selection rule

DirectCobalt and ScalyHornet both answer D-W10 with a traversal seeded on the
entities the task names and expanded a fixed number of link hops. Hops are a
*storage* distance, not a *task* distance. The world graph is built to be
reused: one wireless bus channel can carry lever signals, door signals and
lamp signals at once (W-8.2, W-8.1). A 1-hop cut from `door` therefore either
misses the relay box three rooms away or drags in every other device on the
channel. Raising the hop count to fix the first case makes the second worse.
Truncation caps (8 entities, 512 tokens) do not fix this either: they cut *after*
selection, so a noisy neighbour can push out the relay the agent needed.

## The rule I propose: close the circuit, stop at satisfied intent

The task text names a *state change* ("door opens when lever is pulled"), not a
graph region. So select by whether each neighbouring port's `goal` (W-5.3) is
already met by another entity in the set.

1. **Task parse into three slots.** Every task in this world has the same
   shape, because W-5.5 intent records and W-5.3 ports are written that way:
   - `subject` — the entity that changes state (`door`)
   - `trigger` — the entity the player acts on (W-7.5 `use` port, `lever`)
   - `condition` — what must hold between them (`pulled` -> door inbound)
   A task that does not parse into these three slots is *under-specified*, and
   the correct response is to return a question, not a bigger context. This is
   itself a brevity mechanism: "which door?" costs 6 tokens; 40 entities cost 400.

2. **Seed** with `subject` and `trigger` only (resolve names through the graph's
   entity index; if a name is ambiguous, ask, do not guess).

3. **Fixpoint expansion bounded by need, not depth.** For the subject entity,
   list its manifest `inbound` ports. Each port carries a `goal`. A port whose
   `goal` is satisfied by any link already in the set is *closed* and contributes
   no expansion. A port whose goal is *not* satisfied is an open requirement;
   follow exactly the links whose *sink type matches that port's WIT type*
   (W-5.4 guarantees the type check passed when the link was made), and add
   those source entities. Repeat until no open requirement remains or a per-port
   visit counter (default 2) stops a cycle. If a requirement has no link at all,
   stop and report the unmet port — this is the case where the task is asking the
   agent to *build* a connection that does not exist yet.

4. **Stop-rule for the relay case.** DirectCobalt asks whether to stop at the
   first actuator port. No. A relay entity that only forwards a signal has no
   `goal` of its own on that path — its manifest's inbound port goal is "receive
   lever state", which the lever satisfies; its outbound port goal is "carry
   lever state to a consumer", which is not satisfied until the door is in the
   set. So relay boxes *are* traversed, and by construction nothing else on the
   channel is, because those other devices' ports are satisfied by their own
   sources and never become open requirements of the door. Hop count becomes an
   output of the algorithm, not an input.

## What this buys, concretely

- The set size is bounded by the number of *unmet requirements* of the task's
  entities, which is small and task-specific, not by world degree.
- A shared bus with 30 devices yields the lever, the relay, the door, and the
  links between them — because no other device is a matched-type source of the
  door's open inbound goal.
- The unmet-port report tells the agent what to *create*, which is the actual
  build task. Context selection converges with the build plan instead of
  competing with it.

## Delivery (agrees with both peers, adds the budget source)

Push a fixed 5-field envelope (ACP, W-11.7): `task_id`, `subject_id`,
`trigger_id`, `budget_tokens`, `unmet_ports[]`. The packet is pulled with
`get_task_context(task_id)` and is regenerated after any `use`-event or link
change, so it cannot go stale mid-build. Budget defaults to 400 tokens, chosen
because it is roughly one Mindcraft turn's command docs plus memory (W-11.1) and
short enough to force the port-goal filter to do the work. Two pull tools only:
`expand_port(entity_id, port_name)` (follow one requirement the agent did not
get) and `describe_entity(entity_id)` (full description, on demand). That keeps
the initial packet inside budget while leaving the graph reachable.

## Falsifiable checks

- **Relay:** with a 3-hop bus, does the set include the relay and exclude the
  two other devices? (Fails if selection is hop-based.)
- **Ambiguity:** two doors named "door" -> does the system ask instead of
  dumping both? (Fails if seed is name-based without disambiguation.)
- **Unmet:** remove the door link -> does the packet contain `unmet_ports`
  naming the door's inbound port, and no invented entities? (Fails if resolver
  fabricates a link.)

## Concession to make honestly

This requires the `goal` field on every port to be *written*, and W-5.3 only
requires it to exist. If most ports have empty goals, the fixpoint has nothing
to test. Mitigation: when a port's goal is empty, fall back to "type match plus
link kind" and flag the entity as low-confidence in the packet, so the owner can
see which content blocks context selection from working. This is measurable and
becomes a content-quality metric rather than a hidden failure.
