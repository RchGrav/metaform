# Metaform — corrected specification package (candidate v0.4)

This package is a **concrete correction**, not a claim that the complete product specification is finalized. It uses the latest uploaded **`metaform_schema(1).json`** as the current structural baseline, the uploaded **`Canonical_Intake(2).xml`** for semantic fidelity, and the user's explicit decisions from the design discussion for agent tooling and orchestration.

## Authority order for this package

1. User's current explicit decisions, including **provider join**, `op`, receiver-owned `providers`, two functional tools, three read modes, no unsolicited informational turns.
2. **Latest user-uploaded logical JSON schema** (`05_source_unchanged/latest_user_schema_original.json`), except where explicitly corrected in `03_provenance/CHANGELOG_AND_CONFLICTS.md`.
3. **Original semantic definitions and reasoning guidance** from the old flattened Canonical Intake XML, excluding its obsolete per-object tool delivery/flattened payload shape.
4. Corrected candidate specification, for implementation elaboration and owner acceptance.
5. Prior engineering drafts and historical conversion schemas as context only. Their seven-tool proposal and flattened `join type="purpose"` are **not binding**.

**DO NOT** merge older formats into the new JSON or hand database tables/IDs/Cypher to reasoning agents. **DO NOT** turn a proposed example into a requirement. **DO NOT** modify Canonical Intake source text silently.

## Navigation

- `01_specification/METAFORM_FUNCTIONAL_CORE_v0.4_CANDIDATE.md` — corrected technical specification and requirements.
- `02_contract/metaform_functional_namespace.schema.json` — conservative annotated correction of the user's logical schema.
- `02_contract/example_provider_join.json` — conforming minimal serialization fixture.
- `02_contract/example_agent_semantic_batch_PROPOSED.json` — *proposal*, intentionally not a DB edit form.
- `03_provenance/CHANGELOG_AND_CONFLICTS.md` — every correction, unresolved contradiction, acceptance boundary.
- `03_provenance/SEMANTIC_TRACEABILITY.md` — semantic crosswalk from original XML to proposed contract.
- `04_execution/DEPENDENCY_ORDER_AND_REVIEW_GATE.md` — bounded work order with owner checkpoint.
- `04_execution/PRO_SPEC_PASS_INSTRUCTIONS.md` — Pro assignment using this package, no owner questions in a long run.
- `05_source_unchanged/` — originals retained byte-for-byte; historical drafts explicitly nonauthoritative.

## Scope and budget

No legacy code has been copied. No repository modifications have been made. A real implementation/acceptance test of the chassis or LadybugDB has **not** been run. The physical DB table schema is **not yet specified**; that absence is not a reason for the agent to invent a new public logical schema.
