# Native Metaform variants implementation plan

**Goal:** Implement the agreed naming and receiving-purpose semantics, Native
oversight updates, and cloned variants that regenerate affected knowledge by
reissuing its producing prompts.

**Spec:** [Native Metaform variants](native-metaform-variants-specification.md).
Read the [source discussion](../docs/semantics/names-receivers-and-variants.md)
and the canonical [semantic contract](../docs/SPEC.md) with it.

**Status:** Implementation handoff. The behavior is agreed; the specific open
contracts listed in the specification still require design decisions. This
plan does not supply invented field names or algorithms for those decisions.

**Architecture proposal:** Extend the existing reified knowledge and prompt
provenance facilities with base/variant association and producing-context
dependencies. Use the existing prompt/workflow and continuation mechanisms to
reissue operations against variant knowledge. Native oversight updates and
variant regeneration operate on their respective represented understanding.

**Current stack:** Python 3.11+, JSON schemas, shared SQLite knowledge service,
JSON portable knowledge, optional Ladybug analysis copies, CLI/MCP, Flask
workbench, and persisted workflow execution.

The specification-writing prompt's guidance informs the handoff: separate
agreed behavior from implementation proposals, trace existing components, and
give each unit an observable verification outcome. The units below are ordered
by their semantic and data dependencies. They are future work, not checks run
as part of the documentation update.

## 1. Resolve the record contracts

**Depends on:** R1–R3 and the specification's open decisions.

**Inspect:** `src/metaform/data/schemas.json`, `src/metaform/schemas.py`,
`src/metaform/knowledge.py`, `src/metaform/graph.py`, and the current runtime
semantic sources under `src/metaform/data/semantics/`.

- [ ] Settle the exterior receiving-purpose record's fields and multiplicity.
  Apply the established exterior/external distinction, receiver-owned OP joins,
  and Parametric tunables array described in R2–R3.
- [ ] Settle existing trunk names and record migration under Namespace plus
  `length`; include `code` / Program Code as the concrete unresolved case.
- [ ] Specify base/variant identity and the reference remapping needed for a
  clone that preserves independently reusable global Type knowledge.
- [ ] Specify the producing-context association: how a result identifies its
  originating prompt, semantic inputs, and relationships that influenced it.
  Use owner-qualified Element and reified-join references already present in
  `knowledge.py` when they express the decided contract.
- [ ] Record the chosen contracts in the feature specification, with concrete
  examples for Property / Medium, Dependency, an exterior receiver, a variant,
  and produced knowledge. Preserve the source equations and unresolved meaning
  until Rich supplies the relevant clarification.

**Deliverable:** Concrete record and operation contracts sufficient for the
following units. Model-facing typing changes depend on the unresolved semantic
choices; the general agreed Name extraction rule can be exercised independently.

## 2. Implement naming and typed receiving-purpose intake

**Depends on:** Unit 1's naming and OP contracts. Realizes R1–R3.

**Modify:** `src/metaform/data/schemas.json`, `src/metaform/data/rulebook.json`,
`src/metaform/prompts.py`, `src/metaform/intake.py`, `src/metaform/graph.py`,
and the relevant name consumers in `src/metaform/backends.py`,
`src/metaform/knowledge.py`, and the workbench. Update runtime semantic prompts
through their authored-source revision process. Preserve existing instruction
files and unrelated edits.

- [ ] Add focused examples that begin with Video Driver and place Network
  Driver as its sibling; verify extraction with different `length` values.
- [ ] Implement extraction of the final `length` Namespace components, reversed
  and space-joined. Apply the agreed migration to the Element Name field and
  update Element search/display consumers while preserving unrelated titles.
- [ ] Supply the agreed Name rule and exterior/OP contracts to intake. Keep
  semantic naming and OP inference in the model's task; deterministic code
  supplies storage, extraction, and retrieval.
- [ ] Follow an exterior receiving-purpose record and both supplied game
  relationships through intake, storage, and prepared context. Verify the
  DE attachment, receiver-owned OP, EF reference, and Property / Medium versus
  Dependency distinction.
- [ ] Verify source-specific handoff: Native project OP relationships remain
  separately attributable when preparing independent Latent inference.

**Verification:** Extend `tests/test_intake_pipeline.py`,
`tests/test_intake_handoff.py`, `tests/test_intake_prompt_upgrade.py`,
`tests/test_graph_perspectives.py`, and `tests/test_viewer_semantics.py` where
their existing responsibilities apply. Demonstrate V1–V3 with real prepared
assignments as well as record fixtures. Update rule seed provenance with the
actual runtime revision once it changes.

## 3. Record producing context and create independent variants

**Depends on:** Unit 1's variant and producing-context contracts. Realizes R5
and the provenance required by R6–R7.

**Modify:** `src/metaform/prompts.py` (`snapshot`, `prepare`, `record_test`),
`src/metaform/workflow.py` (`Engine.frame`, `next`, `submit`),
`src/metaform/intake.py` (`_assignment`, `_remember`, `_commit_inference`),
and the knowledge/graph implementation. Reuse `src/metaform/history.py` where
capturing the base can use its existing history responsibility.

- [ ] Retain the producing prompt and the decided semantic dependency records
  with derived knowledge at the operation boundary where both are available.
  Check that separate operations with different graph contexts remain
  distinguishable even when they use the same prompt.
- [ ] Implement the agreed clone representation, preserving the base
  association and remapping variant-owned references, including references to
  joins, according to Unit 1's contract.
- [ ] Change a Medium relationship in the clone. Verify that reading the base
  still returns its original relationship and derived knowledge.
- [ ] Verify that prompt and dependency associations remain usable from the
  variant after cloning; exercise shared-Type references and joins on joins.

**Verification:** Extend `tests/test_knowledge_store.py`,
`tests/test_knowledge_contract.py`, `tests/test_knowledge_dependencies.py`, and
add feature-specific variant tests when the concrete operation interface is
settled. Verify the record-handling portion of V5.

## 4. Examine oversights and update Native understanding

**Depends on:** Typed OP representation and producing-context retention.
Realizes R4 independently of target variant regeneration.

**Reuse:** Graph assembly in `src/metaform/knowledge.py`, prepared prompts in
`src/metaform/prompts.py`, workflow execution in `src/metaform/workflow.py`, and
scoped source handling in `src/metaform/graph.py`.

- [ ] Prepare an examination operation with Native understanding and the
  selected latent Elements/joins. Preserve the user's requested distinction
  between non-issues and oversights.
- [ ] Apply the operation's identified oversight understanding to Native
  records. Retain the operation's producing context through Unit 3's contract.
- [ ] Retrieve Native understanding and prepare a subsequent operation to
  demonstrate that the recovered understanding participates in later work.
- [ ] Demonstrate V4 with inspectable assignments, answers, and resulting
  source-specific records; check both storage behavior and live reasoning.

**Verification:** Use existing graph perspective and workflow tests plus a
feature fixture with one non-issue and one oversight. The latent result's
structural presence alone is not the examination answer.

## 5. Detach affected reasoning and reissue its producing prompts

**Depends on:** Unit 3 and the decided dependency tracing and prompt revision
policies. Realizes R6–R7.

**Modify:** The knowledge operation surface in `src/metaform/knowledge.py`,
prompt preparation in `src/metaform/prompts.py`, persisted workflow execution,
and `src/metaform/continuation.py` as required by variant context.

- [ ] Implement the specified dependency tracing over the changed relationship
  and derived results, accounting for reified references and knowledge derived
  from other knowledge. Use a fixture containing both affected and unaffected
  reasoning so the selected set is observable.
- [ ] Detach the selected reasoning from the variant's active understanding.
  Retain the associations needed to find and reissue its producing operations.
- [ ] Issue those operations against the variant's new Medium relationship,
  following the decided prompt/rule revision and ordering policies. Verify the
  effective inputs and record associations of each assignment.
- [ ] Attach the produced knowledge to the variant with the new producing
  context. Resume a partially answered run and verify the same variant context.
- [ ] Perform V5 with a live model and inspect whether the new guidance
  reflects JavaScript and the affected functional Types. Keep this evidence
  distinct from fixture-based record and workflow correctness.

**Verification:** Add a dedicated variant-regeneration test module after Unit 1
defines the operation surface; reuse `tests/test_intake_pipeline.py` and the
existing continuation/runtime fixtures for the supported execution paths.
Retain assignments, answers, and resulting knowledge for semantic review.

## 6. Integrate inspection, continuation, and portability

**Depends on:** The completed variant and regeneration operations.

**Modify as needed:** `src/metaform/modules/graph.py`,
`src/metaform/data/modules/graph.json`, `src/metaform/viewer.py`,
`src/metaform/static/workbench.js`, `src/metaform/templates/index.html`,
`src/metaform/knowledge_export.py`, and `src/metaform/portable.py`.

- [ ] Expose the decided operation interface through the existing shared
  CLI/MCP command mechanism. Keep commands and UI labels tied to the specified
  actions without prescribing a new management subsystem.
- [ ] Make the selected base or variant, changed typed OP, producing prompt,
  and regenerated knowledge inspectable in the workbench.
- [ ] Preserve the needed variant and execution references through capture,
  export, and resumed portable work. Exercise V6 using the existing selected
  knowledge export and continuation facilities.
- [ ] Update `docs/workflows.md`, `docs/architecture.md`, `docs/next-version.md`,
  `README.md`, and `docs/current-work.md` to describe the actual implementation
  and remaining evidence needs.

**Verification:** Extend `tests/test_knowledge_export.py`,
`tests/test_portable_knowledge.py`, and relevant viewer tests. Run the focused
tests after each implementation unit, then the repository suite and distribution
checks appropriate to the final code change. Record actual commands/results
at implementation time.

## Review handoff

The baseline is `88ce18d399d630e4350db86d6d339c6f8c438681`; refresh it and local
changes before implementing. The workbench already has unrelated in-progress
edits. Read the specification and source discussion before assessing the plan.

Review whether the implementation preserves receiver-owned OP typing, the
agreed Namespace construction/extraction rule, independent source perspectives,
Native oversight updates, and the clone/change/detach/reissue operation. Check
that producing-context records support the claimed dependency tracing and that
renewed reasoning is attached to the correct variant. Keep open semantic
choices distinct from implementation proposals.

The current deliverable is documentation. Its verification consists of checking
source quotations and the accepted rule, local references, cross-document
consistency, and the scoped diff. Runtime tests and semantic demonstrations in
this plan are future implementation work.
