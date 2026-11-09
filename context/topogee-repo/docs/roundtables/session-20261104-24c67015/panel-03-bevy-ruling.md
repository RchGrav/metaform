# P3: Bevy ruling

**Status:** Panel conclusions. Owner acceptance is not established. Written by Opus (synthesis lead). Astra, Sol and Fable review it.

**Source baseline:** branch `intake-3.1`, HEAD `24a72b3`. The session folder is uncommitted.

## Relies on

- P1: the authority order. Current owner decisions govern over the spec. `TOPOGEE-SPEC.md` governs over `SPECIFICATION.md`.
- P1: the decided/proposed status rule.
- P2: the ECS mapping needs no engine. Addresses are stable string keys; a Bevy `Entity` is not stable across restarts (P2, T28).
- P2: the resolver performs three operations (C-2).

## Challenges

- Design Alternative C rejects hosting partly because the chassis language "(D-9) is not decided" (`docs/designs/metaform-server-design.md:887–888`). This ground is stale. `DECISIONS.md:124` (2026-11-03) settles D-9: the chassis is Rust and uses Bevy. Sol records it in `contradictions.md`.
- Correction to the shared notes: the D-9 settlement is at `DECISIONS.md:124`, not design `:124`.

## Ruling

**Link addresses to Bevy entities. Do not host the map or the MCP server inside Bevy.** All four seats agree.

| Ground | Holder | Basis |
|---|---|---|
| An owner decision excludes hosting. | Fable | `DECISIONS.md:124`: the map server "stays a standalone Node MCP server". R-4.4 is Decided: the map server "is not the chassis" (`TOPOGEE-SPEC.md:217`, `:221`). R-2.11 (`:77`). The author rejected Alternative C on "a process, not the chassis" (design `:889–890`). |
| The criteria favour the link under angle A. | Opus, Astra | See the criteria table. Astra supports the link "without claiming every criterion favours it" (T119). |

## Criteria

| Criterion | Angle A (PM tool) | Angle B (world and hardware) |
|---|---|---|
| Iteration speed | The link avoids full Bevy on non-world projects (world-ideas `:123`: `bevy_ecs` 67 crates, full `bevy` 394). | Close to neutral. A world project builds full Bevy either way (Opus T106, `judgment`). |
| Sync hop | Not applicable | Hosting might remove the map-to-world hop. Nobody has measured the hop. The panel keeps this possible gain (Astra T119). P4 L-6 measures it. |
| Coupling and maintenance | Hosting moves the R-4.7 write queue into the Bevy schedule (Opus T105, `judgment`; Astra T119: no evidence yet). | Same as angle A |
| Testability | A linked map tests in Node with no Rust runtime (CLAUDE.md stub rule). | World tests stub the link, not the map (Opus T104). |
| Fit for non-world projects | A project with no chassis uses the map as an ordinary MCP server, with no link CEL (R-2.11). Hosting starts Bevy for every project. | Unaffected (Fable T110, Opus T111) |

Opus withdrew the claim that all criteria favour the link under A and none favour hosting under B (T111).

## Measurement (Opus T118)

| Target | Unique crates |
|---|---|
| `bevy_ecs` 0.20.1 | 70 |
| `bevy --no-default-features` | 78 |
| full `bevy` | 403 |

- **Method:** `cargo tree -e normal,build`, cargo 1.88, Linux. Unique crates, root included.
- This method differs from the method behind world-ideas `:123` (67/394). Compare rows within one method only.
- These numbers count dependencies. World-ideas `:123` reports a 20-second clean build for `bevy_ecs` alone. Nobody has measured build time for the 78-crate or 403-crate class.
- The 78-crate count does not show that a headless stack is sufficient (Astra; world-ideas `:104`).

## Tests the panel requires

| Test | Establishes | Owner |
|---|---|---|
| End the map process; the world keeps ticking. End the world; `status` goes `stale` within the L-6 budget. | Failure isolation only, not release compatibility (Opus, Astra T190, `judgment`) | Chassis panel (Sol T189) |
| Supported map/world version pairs, tested separately | Release compatibility (Astra T190, `judgment`) | Chassis panel. All four seats accept (Sol's carry-forward note). |
| Linked versus hosted build comparison | Evidence for L-5 condition 2, not a P3 gate (Fable; Opus and Sol accept) | Chassis panel |

## Flip conditions

**Review triggers (L-4).** Any one reopens review. None reverses the ruling.

1. A Rust map server is proposed. This adjusts R-4.6.
2. Measured link cost exceeds the L-6 budget.
3. A named module needs same-tick map reads. Dormant until such a module exists. The world reads link status through the link runtime, not the map (Fable T181).

**Owner override (L-4a).** Under the P1 authority order, an owner ruling on Alternative C overrides P3 directly (Opus T111, Fable T113).

**Reversal conditions (L-5).** A reversal must meet all four:

1. The map still stands alone with no chassis (R-2.11).
2. Isolation and recovery tests pass. The linked/hosted build comparison is evidence here.
3. The reversal shows a measured gain over the link.
4. The owner approves (Opus T104).

## Ledger rows

| Row | Ruling |
|---|---|
| L-1 | Ratified by all four seats |
| L-2 | Amended (Astra T115, Sol T117). Only the world link crosses. The chassis controller boundary stays open (SPEC `:77–79`, design `:595`, `DECISIONS.md:124`, map `code.framework.plugin`). |
| L-3 | Ratified, scoped to runtime component state (Sol T144, Astra T145). **R5 (F4):** "Bevy never stores wants" applies to the world server only. Chassis data control stays open under R-2.11 (`:79`). |
| L-4 | Review triggers 1–3 as above. All four seats. |
| L-4a | New. Owner override of P3. |
| L-5 | Reversal conditions 1–4 as above |
| L-28 | Disputed. See Open Questions. |

## Decisions Made

- Link, not host, on both grounds. Keep the possible sync-hop gain.
- The D-9 ground in Alternative C is stale. The rejection stands on R-4.4 and R-2.11.
- The isolation test proves isolation only. Version pairs need a separate test.
- L-1, L-3 ratified. L-2 amended. L-4, L-4a, L-5 agreed as written above.

## Open Questions Handed Forward

Each item carries a recommendation (chair instruction T125). Owner proposals marked "Fable" come from a vetoed turn and await seat acceptance in review.

| Item | Recommendation | Basis | Blocks |
|---|---|---|---|
| L-28 chassis pin and headless stack | One workspace `bevy` version. The chassis uses `default-features = false` with `MinimalPlugins`; the world adds render features on the same version. The owner confirms. Astra and Sol keep L-28 Proposed until stack sufficiency and build time are measured. | Opus T126, Fable T134, `judgment`. `DECISIONS.md:124` requires Bevy and leaves module connections open. `metaform-canonical.json:96`, `:268` name the Chassis but no Bevy plugins or `bevy_app` (Astra T207, Fable verified). The `MinimalPlugins` choice is Fable's inference only. | L-28 |
| Isolation verification and version pairs | The chassis panel owns both. | Sol T189, Astra T190 | L-5 condition 2 |
| Build time for each stack | The chassis panel measures clean and incremental build time with one method. | `judgment` | L-28 |
| C-5 storage | R3, beside Sol's L-60 checks (Fable) | L-10 verification needs link CEL persistence. | Link CEL persistence |
