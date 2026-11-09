# Intake rubric: is this a useful Metaform?

## Use

Apply this rubric to the representation actually produced and the artifact it claims to describe. It is an evaluation lens, not a mandatory list of artifact categories. A folder of photographs need not contain interfaces, test suites, or runtime dependencies; a contract need not resemble a repository. Report the relevant strengths, defects, and evidence. Do not manufacture missing categories to complete a checklist.

A useful initial Metaform allows a capable newcomer to understand what the artifact is, who receives its result, what its principal Elements contribute, and how to target the region relevant to a task. It should remain useful before detailed implementation analysis.

## Evaluation dimensions

| Dimension | Useful representation | Defect to identify | Evidence to inspect |
| --- | --- | --- | --- |
| Defining identity | A representative composite captures the artifact's combined result and meaningful boundary | DE is only an entry point, file container, implementation medium, or idealized product pitch | DE description, upstream receivers, source account |
| Tripartite meaning | Each receiver is bound to its own purpose and the provider Type's single EF | Receiver/purpose lists can cross-pair; EF and OP restate each other; source functions substitute for artifact capabilities | Selected Type, actual binding, OP join, concrete receiving use |
| Coarse usefulness | Principal functions/properties are legible without implementation trivia | Either a vague inventory with no relationships or a near-repetition of every symbol, constant, and callback | Functional summary, size of local neighborhoods, representative EFs |
| Actual/Type separation | Project details live on actuals/evidence; Type knowledge remains reusable | Same-Type actuals collapse; Type description names local paths; actual role is mistaken for Type meaning | Shared-Type actuals, Type definitions, binding realizations |
| Typological placement | Each prefix is meaningful and narrowing is Function/Encounter by relationship | Classifier/folder/encoding scaffolding; placement chosen by spelling rather than meaning | Namespace path, naming/length, narrowing reason |
| Relationship quality | OP role belongs to the receiver and explains why the provider participates | Generic “depends on” arrows, invented membership OPs, duplicate same-purpose joins, unjustified propagation | Purposes, roles, signals, participants, direct neighborhoods |
| Evidence and neutrality | Observed/inferred/reused material is traceable; actual shape is not rewritten into preferred design | Outside conclusions inside Native descriptions, proposed components presented as existing, coverage notes repeated as capabilities | Source/prompt/activity provenance, proposed findings |
| Expandability | Stable IDs and evidence handles allow deeper work at a chosen region | More detail requires a new whole Metaform or changes the parent's identity without explanation | Target resolution, refinement links, patch behavior |
| Orientation economy | Reused Type understanding and bounded context support a subsequent task | Repeated full-project passes, universal completion recursion, presentation work in semantic intake | Assignment history, prompt/context sizes, read envelopes |

The role of a property is evaluated at its actual receiving purpose. A provider can be necessary for one function yet merely supportive to the artifact's overall identity. Source completeness, formal schema validity, and semantic usefulness should be reported separately.

## Recording an assessment

For each material finding, record the affected target, the represented claim, the evidence examined, the semantic defect or strength, and the smallest useful repair. A narrative classification of **useful**, **useful with localized repairs**, or **needs structural realignment** is enough for an overall assessment. These labels describe the reviewer’s conclusion; they are not publication states or runtime admission controls.

Optional dimension scores can help compare repeated runs, but must identify what was actually assessed. Do not aggregate irrelevant dimensions into a universal weighted quality score. A missing receiver relationship is a concrete semantic defect; a missing software-specific category in a photograph collection is not.

## Belongs in initial intake

Include a fact or Element when it explains defining identity, a principal capability, an important receiving purpose, an actual requirement/property, a meaningful boundary, or a relationship necessary to orient later work. Include a notable implementation distinction when its omission would change that understanding. Coarse does not mean suppressing a genuine architectural constraint.

Defer details that mainly explain how to perform a later task: line-by-line behavior, exact constants, individual test cases, optimization advice, best practices, stylistic improvements, speculative risks, alternative architectures, or exhaustive API enumeration. These can be expansion output, evidence, or knowledge layers. The distinction is purpose, not a fixed list of forbidden subjects.

## Practical checks

Ask a fresh reader to explain the artifact's combined result, a principal receiver's purpose, one provider/receiver relationship, and a task-relevant namespace target using the Metaform alone. Then compare that explanation with selected artifact evidence. The test is whether the shape supports a correct orientation, not whether the reader repeats the schema vocabulary.

Examine two actuals sharing one Type: do they remain distinct, and can shared knowledge be reused without copying their local properties to each other? Examine one language/medium property attached to a narrow branch: is it visible at the trunk without becoming applicable to siblings? Examine one proposed improvement: is it distinguishable from existing structure? These are small but meaningful semantic witnesses.

For a non-software artifact, use the same questions. In a maintenance guide, the owner receives procedural understanding; diagrams and procedures contribute to that purpose; printing format is not the guide's defining function. In a photo collection, image content and surrounding collection context can establish the artifact's role without inventing software-style dependencies.

## Applying the rubric to MGM

The MGM sample is useful with significant localized and structural repairs. Its Defining Element, actual identities, Type references, and meaningful subsystem relationships are valuable. All tested references resolve. However, Native already includes latent-assessment provenance, several EFs descend into implementation detail, and proposed outside contracts appear as actual structure. The mandatory second graph is a process-level realignment issue rather than a defect in every individual relationship. [04](04-sample-intake.md)

Use those concrete witnesses in prompt refinement. Do not train the new prompt merely to emit 58 fewer or more nodes, match one expected taxonomy, or repeat a canned statement that no runtime validation occurred.
