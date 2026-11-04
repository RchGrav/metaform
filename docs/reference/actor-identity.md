# The actor identity model

MIN-3. Written before the schema, because both product lanes resolve through it and retrofitting it
means touching both. It takes the sketch in `docs/research/Metaform as a Spatial Agentic Development
Environment.md:547` as the starting shape, answers the three properties the playground side asked
for in `docs/playground/actor-binding.md` §1, and makes one correction to the sketch that those
properties force.

The whole of it is one sentence: **an actor instance is who acted, a body is what it acted through,
and a session is where the call came from — three separate columns, never one inferred from
another.**

## 1. The correction: the runtime session is not on the identity row

The sketch lists `runtime_session_id` as a field of `ActorInstance`. Read as identity that is wrong
in both directions, and each direction is already live in the repo:

- **A session is not enough to identify an actor.** The playground needs one process to act as two
  actors on consecutive calls without mutating its own environment. If the session were on the
  identity row, the only way to switch actors would be to make a new session or edit the old one.
- **An actor does not need a session.** A roundtable OpenRouter seat
  (`roundtable/seats.py`, `openrouter:<model>`) has no ACP session at all; it is a full participant
  with a conversation and a turn order. So would an `a2a:` seat. If identity required a runtime
  session, half the seat kinds could not be actors.

So the session moves off the identity row and becomes two other things:

- a **binding**, `session_actors`: which actor instance a session acts as *by default*. One row per
  session, rewritten freely, and nothing resolves from it when the call names an actor;
- **provenance**, a column on each op-log record: the session the call was made in, kept because the
  measurement rig joins on it (`dispatch.spend`, keyed `(session_id, seq)`).

`agent_definition`, `project`, `world`, `conversation` and `task` stay on the row. They are what the
actor *is*; the session is where it was reached this time.

## 2. The row

```text
actor_instances                 place='metaform' — beside the map and the op log, so the join is local
    actor_instance_id   the handle every operation resolves from
    agent_definition    what kind of agent: a dispatch agent id, or a roundtable seat id
    project             the project
    world               the world (base) it participates in
    camera              its own camera, nullable
    conversation        the conversation it speaks in, nullable
    task                the ticket it works, nullable
    parent              another actor instance — lineage, never identity
    opened / closed     when it came to the world and when it left
```

`body` is deliberately **not** a column; §3 says why. `runtime_session` is **not** a column; §1 says
why. `camera` stays on the row because a camera is per-actor and outlives any one body — an actor
that hands a body back and takes another keeps looking from the same place.

`parent` is lineage and nothing else. A child actor's operations resolve from its own
`actor_instance_id`, never the parent's, which is exactly the trouble the research note named: a
visible child figure that is not independently embodied because its tool calls still resolve through
its parent. Lineage answers "who spawned this"; it never answers "who is acting".

## 3. A body is held, not owned

The playground's third property — a body id is not an agent id; one agent may hold a body, hand it
back and take another — means body cannot be a column on either side. `body → actor` is not a
function, and neither is `actor → body`; both are functions of *time*. So the holding is its own
table with a span:

```text
actor_bodies                    place='metaform'
    body                the body on the map
    actor_instance_id   who holds it
    from / until        the span, `until` null while it is held
```

One live row per body (`until IS NULL` unique per body), which is also where "another figure at work
has that character" (`web/__init__.py:808`) becomes a real constraint rather than page state.

This is why the record in §4 carries both ids. The renderer draws the body; the rig joins on the
session; an audit of who did it needs the actor instance. A record that kept only the body would
lose the actor across a hand-back, and a record that kept only the actor could not be drawn.

## 4. Resolution, recorded as well as applied

One function, called per call, with no process state in it:

```text
resolve(actor=<given>, session=shown.session(), project, world)
    → (actor_instance_id, body, actor_source)
```

- `actor=<body id>` → the actor instance holding that body now. `actor_source='given'`.
- `actor=none` → the declared null binding. `actor_source='given'`, `body` null, and the actor
  instance is still resolved from the session binding, because *something* acted even when no body
  did. A verb that needs a figure to move refuses with `refusal.kind=invalid`, per the playground
  doc §1.
- omitted → the session's binding (`session_actors`), and the body that actor instance holds, if
  any. `actor_source='session'`.
- omitted, no binding → the person's mascot. `actor_source='mascot'`.

`actor_source` is stored, not derived, so the four cases stay distinguishable afterwards:

| `actor_source` | `body` | reads as |
|----------------|--------|----------|
| `given` | a body | that body was named on the call |
| `given` | null | a null binding that was **declared** |
| `session` | a body | inherited from the session's actor, which holds a body |
| `session` | null | inherited from a session whose actor holds **no** body |
| `mascot` | the mascot's body | no actor was named and no session was bound |

The two middle rows are the pair the measurement rig cannot tell apart without the column, which is
the playground's second property.

### What this replaces

`ask_page` reads `METAFORM_WORK` and `METAFORM_TASK_NAME` out of the process environment
(`web/__init__.py`). Those two reads are the implicit caller in its clearest form: the ticket and
the task name come from whatever the process was started with, so two actors in one process is an
environment write. Under this model `work` is the resolved actor instance's `task` and `role` follows
from its `agent_definition`, both read from the row rather than the environment. The environment
keeps exactly one job: seeding the **session binding** when a dispatch run starts. It is a default,
never a decision.

## 5. Protocol independence

ACP, MCP and A2A transport `actor_instance_id`, `body`, `world`; they do not own them. The roundtable
seat kinds make the point concretely — `acp:claude/haiku`, `openrouter:<model>`, `agent:<name>` and
`a2a:<peer>` are four transports for one notion of a participant, and the identity row is identical
across all four. MCP's 2026-07-28 spec is stateless and has removed protocol-level sessions, so
there is nothing on that side to resolve from even if we wanted to.

The test that keeps this honest: no name from `modules/mcp`, `modules/dispatch`'s ACP layer or any
A2A peer code appears in the actor tables or in `resolve()`.

## 6. Where it lands, and in what order

Declared with `Table(...)` in the chassis (`data/tables.py` idiom, `place='metaform'`), not in a
module, because `web`, `map` and `dispatch` all consume it and none of them owns it.

Two sequencing facts worth stating plainly:

- **This is blocked on MIN-2.** 195 paths are uncommitted on `land-main-wip-2026-10-14`. Nothing
  here gets built until that lands green.
- **It has to land before MIN-12's first migration.** The playground doc's §5 record needs `actor`,
  `actor_source` and `session` from the first op-log migration, because adding identity columns
  after records exist means a migration *and* a re-run of anything already measured. If MIN-12 is
  about to write its first migration, the three columns go in it whether or not the rest of this
  model is built yet.

## 7. What the two consuming engineers are being asked

- **Playground**: the three properties are accepted as stated. The one thing that differs from your
  §1 is that `actor=none` still resolves an actor instance (from the session) while resolving a null
  *body* — so a declared null is attributable rather than anonymous. Confirm that is compatible with
  the `B0` arm, where nothing of the actor may enter the render or the `world` stream.
- **Roundtable**: a seat looks like one actor instance per seat per table — `agent_definition` the
  seat id, `conversation` the table, `body` and `camera` null for a seat that never embodies. Two
  questions. Does a seat that is re-opened across tables want one actor instance per table (my
  assumption) or one per seat identity with the table as a span? And does a multi-model seat ever
  need two `agent_definition` values on one row, or is that two actor instances with a `parent`?
