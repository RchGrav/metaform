# Semantic preservation and transition matrix

All XML locations refer to `Canonical_Intake_old_flattened_original.xml` (the original user-attached file). Their semantics are not replaced by a generic database schema.

| Original XML locus | Preserved behavior in candidate spec | Changed implementation exposure |
| --- | --- | --- |
| `core_concepts` AUE/AT and `goal` | inspect the artifact as a function-bearing thing, not its medium/style | semantic batch instead of per-object storage calls |
| `core_concepts` RE/OP/PE/EF | OP is receiver's active why; EF is providing element's encounter-specific how | `providers[provider_address].op` / `.ef` |
| `core_concepts` IFD and examples | substantive satisfying flow, not merely request/parameter | `ifd` values `send|receive|both` |
| `core_concepts` CQU; `cqu_entity_rules` | concrete value-driving external receiver type; not generic user/developer | address `downstream.cqu.*` (actual address inferred with rules) |
| DE/SE/NE definitions | roles distinguished by defining contribution, support, external demand | ordinary element `role`; provider/receiver are link positions |
| ICE definition; steps 5, 11, 12; response instruction | detect indivisible coupling during tracing and prove it on closure | current `ice` boolean represents pair property only; block grouping not yet expressed |
| namespace_rules 1-11 | type-level, reverse-readable, industry terminology, project `name` priority, no coined words | dotted nested keys + `name_length`; full-graph checks outside JSON Schema |
| constraints and steps 3, 7-10 | survey, recursive tracing, gap closure, avoid parametric and incidental variants | reasoning loop retains depth, applying coherent blocks |
| steps 11-12 | anneal while keeping functionality and ICE; final readback/correction | read full pure map via `global_functional`; batch refinements |
| response_protocol instructions 120, 136 | old one-object-at-a-time tool delivery | explicitly superseded; **no** one object per MCP call |
| old XML result/tree output | flattened recursive `<join type="purpose" purpose="…" function="…">` | superseded serialization: receiver-owned `providers` dictionary with `op`, `ef`, `ifd` |
| constraints 55 | no intake refusal/gating, grade/refine results afterward | validation receipts and advisory notices, no invented content blocks |

**Non-goal:** Do not silently change the old process text, remove its legitimate checks, or translate process syntax as if it were already the new API.
