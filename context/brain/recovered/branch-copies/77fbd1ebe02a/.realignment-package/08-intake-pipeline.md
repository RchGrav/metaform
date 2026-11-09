# Coarse intake and progressive analysis

## Intended result

Initial intake produces a useful typological skeleton of the artifact: its Defining Element, relevant receivers, what they need from it, the principal functions/properties that make it that thing, and the joins explaining their participation. It also records enough evidence and unresolved questions to revisit a region later. It is not a source-symbol census, a full design review, or a mandatory collection of best practices.

The existing whole-artifact assignment and incremental `intake.put` transport are suitable foundations. The change is to their semantic question, output model, and completion transition. [S03](evidence/source-index.md#s03)

## One coherent process

| Stage | Input | Semantic question | Output and contribution | Later extension |
| --- | --- | --- | --- | --- |
| 1. Establish source and artifact scope | Supplied location/material, surrounding context, existing source manifest and model when available | What artifact is being understood, and what evidence is available? | Source manifest, artifact boundary, relevant evidence handles; no mandatory full semantic pass | Read more evidence for a named question |
| 2. Establish the defining relationship | Scope and representative evidence | What combined result makes this artifact what it is, who receives it, and for what purposes? | Defining Element, exterior or other relevant receivers, initial OP joins, concise functional account | Refine a boundary or receiver purpose without replacing the artifact ID |
| 3. Follow the purposeful frontier | Current Element and its receiving-purpose context, reusable Type definitions | What principal EFs/properties does this Element require to perform its role? | Reused or new actuals, Type bindings, OP joins, meaningful namespace placements | Expand one Element, Type, join, or region |
| 4. Publish the collected shape | Incremental records, source/Type references, unresolved frontier | Does this account orient a subsequent agent at the intended resolution? | Foundation revision, annotations, optional depth opportunities, exact provenance | Any later analysis adds local detail or knowledge |

Stages 2 and 3 normally occur in the same whole-artifact semantic assignment, not in separate agents that rediscover the project. Stage 1 can be mostly deterministic inventory plus targeted reading. Stage 4 is reference/shape assembly and a concise rubric-based assessment of the produced account, not a second independent rewrite of every Element.

## Frontier semantics

Start with the Defining Element's receiving-purpose relationships. For the current Element, identify the meaningful capabilities and properties it needs; that Element becomes the receiver of the corresponding joins. Follow the provider's own requirements at the same useful resolution. Reuse an actual identity when encountering the same thing again. Retain multiple meaningful OPs between the same participants rather than deduplicating them merely by endpoints.

A frontier entry is an unanswered purpose or a region whose resolution can be deepened. It is not “every Type newly referenced anywhere must receive a new Latent assignment.” Reusable Type recognition can draw on latent knowledge during intake; the separate blind-spot analysis is a different task, not the only place where a model may use Type expertise.

The walk accounts for the represented purposes. It does not require an exhaustive expansion of every implementation dependency. When a coarse provider adequately explains the purpose, preserve it at that resolution. A lower-level implementation detail is included initially only when omitting it would materially misrepresent identity, a principal capability, boundary, or relationship. No fixed node quota or file-count rule defines coarseness.

## Source use and neutrality

Read enough of the artifact to distinguish behavior from slogans. Repository guides and prior accounts are useful evidence, but record their provenance and reuse explicitly. Source code, file names, and implementation terminology do not automatically dictate Type boundaries. Equally, do not replace the actual artifact with an idealized generic architecture because it is familiar.

Initial intake may record a surprising actual relationship. It does not have to normalize it into a best-practice design. Contradictions in evidence can be attached as observations or unresolved questions without forcing an outside review into the structural description. Keep source coverage and “not runtime-tested” information on the intake activity rather than repeating them in every EF.

The initial functional account can contain a diagram and freeform explanation. Its diagram depicts the collected artifact, not proposed missing components. Store the account once and link its relevant regions; do not repeat a full diagram in every Type worker's prompt.

## Prompt composition

Use `prompts/runtime/intake.md` with the target record schema, the selected namespace/description rules, available source handles, and reusable Type context. Include the minimal semantics of DE, receiver/OP/EF, roles, classification, Function/Encounter narrowing, and local property placement. Keep the complete platform-expert foundation out of this prompt.

Preserve rule provenance from the existing prompt snapshot system. Runtime prompts receive the rule excerpts needed for their role, not the complete platform-development manual or unrelated collaboration instructions. The source prompt, rendered assignment, rule revisions, inputs, and published output must be recoverable from the intake activity.

## Completion and outside analysis

Native completion publishes the foundation and completes initial intake. It may return available next operations, including expansion and blind-spot analysis; it does not automatically run all of them. When a user explicitly asks for intake and outside review together, execute the second operation against the completed foundation and attach its result as a distinct layer.

Replace the present automatic transition from Native to `archaeology`. Keep existing receipts, incremental submissions, run locks, and host-answer transport. Version running assignments so a previously issued v1 graph answer is not interpreted as a new layer answer. [S03](evidence/source-index.md#s03), [21](21-migration.md)

## Targeted expansion

An expansion request carries a model/revision, target, purpose, and desired question or resolution. Targets can be an actual Element, Type, namespace branch, OP join, or bounded graph region. The context builder supplies that region, direct relevant joins, applicable Types, and evidence handles. It does not reconstruct the entire project.

Use `prompts/runtime/expand.md`. Output a structural patch, source evidence, refinement links, and a concise account of what became more precise. Existing IDs remain for the same actual things. Finer Elements are linked to their coarse parent through explicit refinement relationships; their Type namespaces follow Type meaning rather than mirroring the actual's folder hierarchy.

An expansion can also discover that the earlier shape was wrong. Represent that as an explicit correction with before/after references and the reason, not a silent replacement under the claim of “adding detail.” Layer dependencies affected by the patch are then evaluated through the normal impact model.

Enqueue expansion through the existing workflow/continuation machinery. A job records its base revision, target selector, purpose, source/prompt snapshots, pending assignments, and patch contributions. Concurrent non-overlapping contributions can be rebased by record identity; a conflicting edit returns the exact competing records. A failed or partial job retains its contributions and provenance without erasing the useful existing foundation.

## Inference work removed from the default path

Remove per-Type proofreader stages, recursively spawned global Latent completion passes, compulsory full outside analysis, per-Type SVG generation, repeated run qualifications in actual descriptions, and similarity recomputation during ordinary publication/read. Reuse Type definitions and selected context rather than asking each worker to rediscover them.

Do not remove meaningful recursive purpose discovery. Do not remove actual-specific descriptions to achieve a smaller output. Efficiency comes from a single useful question at a useful resolution, reused Type knowledge, and selective elaboration—not from flattening the semantic model.
