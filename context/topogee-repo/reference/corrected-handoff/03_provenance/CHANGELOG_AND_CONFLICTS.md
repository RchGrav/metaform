# Explicit correction ledger and source conflicts

## Changes made to the **derived** JSON Schema (original retained unchanged)

| Change | Reason | Status |
| --- | --- | --- |
| `$schema` changed to explicit Draft 2020-12 URI; `$id` supplied | make validation dialect explicit, avoid ambiguous latest schema URL | Technical normalization, not data-model change |
| Root description rewritten to say **provider join**, RE-owned `providers`, `op` and `ef` | user explicitly corrected `purpose join` terminology, operative purpose field name | Agreed vocabulary |
| ProviderRecord title/description corrected | provider relationship not a purpose record/DB row | Agreed vocabulary |
| `ifd.enum = [send,receive,both]` | original XML schema specifies those 3 singular values; examples also use inflected words, so any existing data using `sends/receives` needs explicit normalization in migration | Schema validation proposed; migration needed for legacy values |
| Forbid flattened join aliases `purpose`, `function`, `joins` in a provider record while leaving other extensions open | do not silently allow legacy mislabeled join fields alongside `op`/`ef` | Candidate enforcement of explicit user correction |
| `ice` boolean description corrected | it had mistakenly copied the IFD description | Clear source typo fixed; ICE block identifiers **not** represented |
| `name` description changed to project canonical name if specified, else industry term | user-authored original Canonical Intake rule 11 | Original semantic wording recovered |
| Optional node-level `ef` fields **preserved but labeled legacy-compatible** | original XML says context-specific EF resides in receiver-owned relationship, yet latest schema allows element-level EF | Unresolved: do not delete/repurpose automatically |

**Not changed:** user's `providers` object structure; flat root namespace, native array/scalar values; open extra properties; roles or their semantics; `ice` type; `op`/`ef` required fields for joins; user originals. This is a **candidate correction**, not an unreviewed final promotion.

## Conflicts whose resolution is NOT silently assumed

1. **Root wrapper conflict.** Earlier historical contract required `{ "metaform": {...} }`; latest user upload describes direct namespace keys at the document root. This package follows the latest upload and quarantines older wrapper examples.
2. **Old XML `join type="purpose"` / `purpose` / `function`.** Older flattened serialization labels are NOT carried forward: current `providers` map uses `op`, `ef`, `ifd`. Original XML remains the source for meaning and intent, not its output shape.
3. **Old per-object intake calls vs approved block apply.** Per-object instruction is superseded. Recursive reasoning, CQU inference, namespace checks, ICE trace, reconciliation and proof are preserved.
4. **ICE boolean vs numeric group/block IDs.** Latest schema's `ice` cannot alone encode multiple disjoint indivisible blocks. Do not assume one global block or infer a block number from `true`.
5. **Node-level `op`/`ef` vs encounter-specific join fields.** Source has both. Current user expects correct field semantics; the candidate retains optional nodes to avoid deleting author data while requiring full provider joins for encounter representation. Must decide if node-level fields are meaningful distinct properties or legacy duplicates.
6. **`name`/`label` descriptions vary between root and namespace node.** The candidate corrects `name` where original rule is explicit; `label` needs a consistent final definition before enforcing exclusivity.
7. **CQU vs role enum.** Older process defines downstream CQU as a receiver with `role=CQU`; latest schema describes DE|SE|NE roles in prose but does not enforce an enum. Do not omit CQU from the system or force it into DE/SE/NE.
8. **IFD inflection.** XML formal schema uses `send|receive|both`; XML examples say `sends`, `receives`. Candidate validates formal values and lists migration concern.
9. **Six/seven old MCP tools vs two functional tools.** Earlier 3-paradigm draft names `orient/discover/inspect/acquire/invoke/subscribe/unsubscribe`; later discussion explicitly converged on **one functional view with three modes + one functional apply**. Older draft names cannot become mandatory tools in the clean rebuild.
10. **Message wake semantics.** Old peering code references informational notes; the user expressly prohibits log/progress/completion notifications waking models. Direct agent-to-agent contact/assignment/handoff remains distinct.
11. **ASD-STE100 descriptions.** Latest JSON says `op` and `ef` strictly follow STE100; JSON Schema can validate strings but not this linguistic standard. The intake requirements need a defined assessment method, not a misleading JSON-only proof.
12. **Physical schema absent.** No approved LadybugDB/SQLite table schema is included; chassis owns it. It must be engineered from the accepted semantic contract, not reverse-promoted from legacy tables.

## Source preservation

`05_source_unchanged/latest_user_schema_original.json` and `05_source_unchanged/Canonical_Intake_old_flattened_original.xml` are copied from the conversation attachments byte-for-byte. The previous v0.3 draft is included **only for provenance**, with its superseded statements clearly noted here. Do not auto-adopt old instructions or prompts.
