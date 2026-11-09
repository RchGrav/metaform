# W-1.4 Satisfaction Trace — final state (SeriousMagni)

**Status:** verification, 2026-11-07, final. Checks that `blueprint-spec.md` fully answers both halves of W-1.4: "What a feature blueprint holds and how agents write it are not specified yet."

## The two halves, closed

| Half of W-1.4 | Clause | Builds on |
|---|---|---|
| **What a blueprint holds** | §2, B-2.1–B-2.6 | W-5.1, W-4.1, W-3.5, W-9.4 |
| **How an agent writes it** | §3, B-3.1–B-3.7; §4, B-4.1–B-4.3 | W-5.5, W-9.1/9.6, W-11.3/11.4 |

Final state corroborated by independent machine-checks (AcuteNitrate final-verification): 19 defined `B-x.y` clauses, 0 referenced-but-undefined `B-x.y`, 0 `W-` ids absent from the world spec; both halves answered.

## The required build-on points (from the task)

| Task says "build on" | Clause | Check |
|---|---|---|
| W-5.3 manifest of ports | B-2.2 manifest layer: name/intent/WIT type/goal/function/description | ✓ |
| W-5.4 links | B-2.2 `links[]`; B-3.1 `link`; write-time WIT type check | ✓ |
| W-5.5 intent records | B-2.1 `intentRefs[]`; B-2.2 scoped intent; B-4.3 intent copy onto minted entity | ✓ |

## Q1. What does a feature blueprint hold? (final)

An agent-owned, design-time metaform, addressed by slots (`<blueprint-id>/<slot>.<port>`). It holds: blueprint-level `description`, `intentRefs[]`, provenance hashes (B-2.1); per-slot archetype + W-5.3 manifest layer (incl. `description`) + scoped intent (B-2.2); links over slot endpoints (B-2.2); the three-state assertion split — derived selectors, stored `expected`, server-only `outcomes` (B-2.3); typed `build_steps[]` (B-2.2); `limit_request` (clamped at submit) and `precision` (B-2.2); and the `agent_record` (B-3.5). It does **not** hold minted entity ids (W-4.1), voxel/WASM bytes (W-3.5), functional-map addresses (W-1.1), or authority of its own (MS-4) — B-2.5.

## Q2. How does an agent write it? (final)

Through MCP verbs over its own metaform (B-3.1): `open → add_node / add_external_role → declare_port → link → assert → grant → step → submit → outcome → release`, each a server-validated edit. Links type-check at write time against slot/archetype manifests, so W-5.4's "error at connection time" holds pre-instantiation and survives minting. `submit()` requires every *owned* slot to have a `place` step, clamps `limit_request`, and returns an **outcome digest** (W-11.6), not a dump. The loop is submit → observe `outcomes` → revise via `parentBlueprint` → resubmit, recorded in `cycles[]` (B-3.3, B-3.5). Cell claims (B-3.6) make staging deterministic.

## Verification results

- Nineteen `B-x.y` clauses defined; every cited W-id resolves to a defined requirement (checked by script).
- Both halves of W-1.4 are answered; the gap named in W-1.4 is closed.
- D-B4 settled on W-1.1 (Decided): separate resolver instance, never shared with the functional map; only the agent-side of D-W10 (task-context selection, W-5.6) remains Open.

## The single genuinely-open item (D-W10, agent side)

W-5.6 asks how an agent's task context is selected from the world graph and delivered. The blueprint-authoring slice is specified (B-3.2). The general in-world agent context (W-11.2) remains Open. Recommendation: reuse the same principle — a resolver selects the resolved layers of exactly the addresses the task concerns, bounded by W-11.6, never a traversal.
