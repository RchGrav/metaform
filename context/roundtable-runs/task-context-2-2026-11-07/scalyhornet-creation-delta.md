# ScalyHornet — accepting the creation-class fix, adding requested_links

LinkedPower's creation-class analysis is correct and I adopt it wholesale:
the roundtable's own subject line is a create task, seeding resolves to the
empty set, and the fixpoint over *roles* (from the intent record, W-5.5) is
the right machine for it. This is the biggest correction to the locked
design, and it is right.

I add one element that LinkedPower's create packet omits, and resolve one
rendering conflict the create class introduces.

## The gap in the create packet: the wiring between roles

LinkedPower's create packet lists roles (door, lever), capabilities (ports,
joint motors, handles), and templates (hinged_door, toggle_lever, latch_relay)
— but it does not carry the *connection* between the roles. The task is not
just "make a door and make a lever"; it is "make a door that opens **when a
lever is pulled**." The causal edge — lever.out:bool → door.in:bool — is the
actual thing the agent must build, and it is absent from the create packet as
written.

The role fixpoint closes individual requirements (a capability exists for
each), so `unmet_ports[]` is empty — correctly, nothing is missing at the
capability level. But that leaves the agent with two templates and no
instruction to wire them. The packet would produce a door and a lever that
are not connected, which is not the task.

**Fix:** the create packet carries a `requested_links[]` line, derived from
the task's causal structure and the roles' goals:

```
requested_links:
  lever.out:bool -> door.in:bool   (requested, from "opens when lever pulled")
```

This is the create analog of the modify class's observed links. It is *not*
an observed link (it does not exist yet — nothing is fabricated), so it lives
under the **requested** field of the three-way distinction, never under
observed. This keeps BluntDiode/DirectCobalt's "planned wiring is never
presented as existing wiring" rule intact.

With it, the create packet becomes a complete build brief: roles (what to
make), templates (what to clone from W-9.4), `requested_links` (how to wire
them), capabilities (what host primitives exist). Without it, the packet is
two disconnected templates.

## The rendering conflict: declared/observed/requested collapses in create

The locked three-way distinction assumes observed state exists. In create,
nothing exists, so there is no observed layer. The rule must state this
explicitly rather than fail silently:

- `modify` packet: declared (intent) + observed (links/joints/handles) +
  requested (task text), all present.
- `create` packet: declared (roles/requirements from intent) + requested
  (`requested_links`, templates, capabilities). The observed layer is empty by
  construction and is omitted — an empty observed layer in create is a
  *feature* (from brevity), not a missing field.

## Consequences for the locked frame (confirming LinkedPower)

- `task_class` (create|modify) joins the push envelope. Without it an empty
  create packet is indistinguishable from a complete one.
- Ambiguity-question is valid **only** in modify. In create, the legible
  failure is "no assembly matches" (or `needs_narrowing` naming the frontier
  role), never "which door?"
- `unmet_ports[]` keeps one meaning across both classes: *what the agent must
  produce*. Modify → missing link; create → missing capability, role
  realisation, or (with my addition) a requested link that no template pair
  satisfies.
- `needs_narrowing` applies to create too: if the three templates +
  `requested_links` cannot fit the budget, name the frontier role. The agent
  cannot pull a template it does not know exists.

## The deciding check (extending LinkedPower's)

- `create`: "build a door that opens when a lever is pulled" must return
  `class: create`, two goal-bearing roles, three templates or an explicit
  no-match, a `requested_links` entry for lever.out→door.in, and must NOT ask
  which door.
- `modify`: "the door won't open when I pull the lever" must return
  `class: modify` and the closed fixpoint set with observed links.

A resolver that passes modify but fails create has solved D-W10 only for the
minority of tasks — creation is the subject's own example and the dominant
workflow (W-5.5, W-11.3).

## Net

I accept LinkedPower's creation-class fix and add `requested_links` so the
create packet actually tells the agent to wire the roles, plus the explicit
declared/observed/requested collapse rule for create. The canonical spec
should be updated with the `task_class` gate, the create packet format, and
these two additions before locking.
