# P2: ECS without an engine

**Status:** Panel conclusions. Owner acceptance is not established.

## Relies on

- P1: source status rule and crosswalk.

## Challenges

- `TOPOGEE.md` §2 wording that the resolver composites "parent prefix layers" for any address request. See C-2.

## Direct source checks

- `docs/world-ideas.md:88` records the owner's ECS observation: "sounds like the exact pattern we need". The brainstorm does not settle hosting.
- R-4.1 says "JSON is the default" (`TOPOGEE-SPEC.md:188`). Its status says "Built on Ladybug, not yet on JSON" (line 195).
- Current code imports `lb` from `@ladybugdb/core` (`mcp-server/src/store.ts:10`). Lines 31–35 define the current element and want tables.
- Source baseline: `24a72b37cf76574f1c9b140aad6e10fec0983daf`. These source checks do not establish runtime behavior.

## Mapping (cited, `TOPOGEE.md` §2)

| ECS part | Topogee | Specified storage or owner |
|---|---|---|
| Entity | functional namespace address | map (JSON) |
| Component | CEL: sources, skills, memory, tickets, inbox; proposed world CEL and device CEL | layer files (R-5.1 `layer`) |
| Resource | project settings, root skills, global topology (`.` read, R-5.11) | map server |
| System | Context Resolver, Composer, Facilitator | processes that query address + CEL + resource |

Judgment (Opus): the pattern needs no engine. Addresses are stable string keys, so they survive restarts. A Bevy `Entity` does not (T28).

Astra's scope correction after T85: this conceptual mapping does not decide the host. P3 owns the hosting ruling and its flip conditions.

## Resolver scope (Sol T72, Opus T79, Fable T80, Sol T82)

The sources distinguish visibility from delivery:

| Operation | What crosses address boundaries | Source |
|---|---|---|
| Layer list | Names only. Inherited to the leaf. An element can add or negate (`-`). | R-6.1–R-6.4 |
| `goto` | Nothing from other addresses' layers. Gives counts, not records. | R-5.30 |
| Resolver (System) | Parent prefix layers are composited. | `TOPOGEE.md` §2 |
| `upstream`, `downstream` | Do not inherit the project's layer list. | R-6.5 |

- Ticket context (R-5.31) selects context in the way `goto` does. Its relation to the resolver is unspecified.
- Consequence for P4 (Fable T80): device CEL delivery belongs to the resolver or ticket path, not `goto`.
- Proposed constraint (Opus T79): device limits must sit on the bound address. A parent prefix must not supply them.
- Check status: performed on spec text only. `goto` is "Not built". Runtime checks stay Proposed (Sol T82).

## Decisions Made

1. Addresses are entities. CELs are components. This mapping alone requires no engine. P3 decides hosting.
2. Layer names inherit. Layer records do not, through `goto`.
3. Device CEL delivery is specified on the resolver or ticket path in P4.

## Open Questions Handed Forward

| Question | Decision trigger |
|---|---|
| Does the resolver composite parent records, or only names? | The owner rules on C-2, or the resolver is specified. |
| Runtime check: parent/child visibility through `goto` | `goto` is built. |
| Runtime check: device CEL delivery through ticket context and the resolver | Resolver and ticket context are built. |
