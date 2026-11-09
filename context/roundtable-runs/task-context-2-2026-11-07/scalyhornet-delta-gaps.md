# ScalyHornet — delta on DirectCobalt's v2 (two gaps)

DirectCobalt's v2 (bounded BFS, max 2 hops, hop-2 conditioned on type-chain +
task-term) is the right shape. Two gaps remain that I nominate to close.

## Gap 1: the type-chain check is too strict for adapters

The hop-2 condition (a) says "port WIT type matches the seeded task's signal
type chain." W-5.4 links only equal WIT types. That is correct for *links*,
but the *context selection* should not assume a relay is type-identity. In
this world a relay/adaptor exists precisely to transform a signal (W-7.2
lists sensors and actuators; W-12.2 builds actuators through code). A real
chain is:

    lever.out:bool -> relay.in:bool -> relay.out:f32 -> door.motor.in:f32

Here the relay is type-transforming (bool -> f32). A strict equality check
would reject hop 2 to the door even though the relay is exactly the intended
intermediate and the task names the door.

Fix: make condition (a) a **compatibility check, not an equality check**.
Admit a hop-2 intermediate if its inbound port is link-compatible with the
previous outbound (==) AND its outbound port is either the same type OR is a
type the task's named actuator accepts. In short: don't let the *selection*
rule be stricter than the *link* rule; the world may legitimately contain a
typed adapter between two named entities. Keep it deterministic — this is a
static, finite type check, still much cheaper than lexical scoring.

## Gap 2: the tour goes stale while a task runs

The envelope is pushed once at task start and the tour is static. But the
world builds while tasks run (W-11.3, W-11.4). Between the push and the
agent's work, a link may be added/removed, an entity rebuilt, or a handle
revoked. The agent would silently work from stale context.

Fix: put a small **version stamp** on the envelope: a hash of the tour's
entity/link set. Two options:
- The agent's pull `get_task_context(tour_id)` includes the version it has;
  the server returns `{unchanged}` if the hash matches, else the refreshed
  tour. Cheap: one hash compare.
- Or the server pushes a one-line `changed: door#47.link (old->new)` notice
  when a tour entity's link/handle changes. Costs a push only on actual
  change, not every turn.

I recommend the second (push-on-change), because it costs nothing in the
common no-change case and is the smallest possible signal. The version-stamp
is the fallback if push-on-change proves noisy.

## Minor: tour lifecycle

Give the tour an expiry or an explicit close (task end). A long task resends
the envelope on a refresh, not a new tour id. This is a bookkeeping line,
not a design change.

## Net

The two real additions are (1) relax the type chain to compatibility so typed
adapters don't break selection, and (2) a staleness signal so a tour doesn't
go stale mid-task. Both are small, deterministic, and keep W-11.6 intact.
