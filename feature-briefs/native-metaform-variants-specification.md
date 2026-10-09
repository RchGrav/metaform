# Native Metaform variants and regeneration of understanding

**Status:** Agreed product behavior from the owner's 2026-09-09 discussion;
implementation design choices are identified below. This documentation update
does not implement the behavior.

**Authority:** [Conversation semantics](../docs/semantics/names-receivers-and-variants.md),
the [agreed Name rule](../docs/rulebook/element/name.md#concise-form), and
[SPEC](../docs/SPEC.md). Explicit user corrections govern earlier descriptions.

**Inspected baseline:** `88ce18d399d630e4350db86d6d339c6f8c438681` in
`/home/rich/metaform`, plus existing uncommitted workbench changes. Source and
instruction files already modified by other work remain outside this change.
The project-enhancement specification guidance in
`prompts/metaform/project-enhancement-agent-prompt-creator.md` and its existing
generated shared-service specification prompt informed this document's structure.

## Purpose

The Native Metaform represents the project's developed understanding. A task
such as porting needs to carry that understanding into a different realization.
The user creates a clone, changes a meaningful relationship, and has the system
regenerate the knowledge that was derived through that relationship by asking
its originating prompts again.

For a game currently realized through C++, the change is to its Property of type
Medium: `code.cpp` becomes `code.javascript` in the variant's receiving
relationship. The resulting porting work is developed through the new semantic
context. Reusable prompts and the recorded relationships supply the means to
reconstruct affected understanding.

The same developed understanding supports examination of latent Elements and
joins for non-issues or oversights. Identified oversights update the Native
Metaform, improving the base from which later operations and variants begin.

## Semantic basis

The existing identity equation remains exact:

`C(T) = {(rᵢ ∧ pᵢ ∧ e)}`

Each conjunction binds the Receiving Entity `rᵢ`, that receiver's Operative
Purpose `pᵢ`, and the Type's single Encounter Function `e`. OP ownership remains
with the receiver throughout intake, cloning, relationship changes, and renewed
inference. The equation supplies semantic meaning; this feature does not turn
it into a runtime equality test.

Names identify Types at the appropriate functional specificity. Typed OP joins
express how the receiver uses another Element's EF. In the owner's examples:

| Receiver | EF provider | OP relationship | Type |
| --- | --- | --- | --- |
| `code.game` | `code.cpp` | Property | Medium |
| `code.game` | `code.game.rules` | Dependency | Unspecified |

The owner located Defining, Notable, Parametric, and Stylistic typing in the
receiver's OP relationship. Preserve the established terms and definitions;
the hierarchy relating these terms to Medium remains an open design question.

Native is the Contextual Metaform's project understanding. The independently
constructed Latent Metaform remains available for examination. The existing
shape-similarity layer continues to express structural presence and source
references. Reasoning about an oversight is performed by the comparison
operation, which then updates Native understanding.

## Requirements

### R1 — Construct a Namespace and recover its proper name

Apply the [agreed rule](../docs/rulebook/element/name.md#concise-form) verbatim.
The Namespace narrows in specificity. Locate the appropriate general position
and reuse existing components before adding the remaining modifiers.
`length` counts the words in the common name, including reused components.
The proper name is derived by reversing the final `length` components.

Given `code.system.driver.video`, Network Driver belongs at
`code.system.driver.network` with `length: 2`; Video Driver remains a sibling.
This replaces the separately authored Element Name field. `namespace` in the
worked examples denotes the record's Namespace ID; the runtime currently stores
that ID as the Element Table key. The replacement concerns Element Name, not
the independent titles of prompts, workflows, or projects.

### R2 — Resolve the exterior receiving purpose during intake

Intake resolves the Receiving Entity for the DE's EF and the OP that the receiver
has for it. A dedicated receiving-purpose record attaches that understanding
to the DE. Its logical contents identify the DE, the exterior receiver, and the
receiver's OP; the DE supplies the EF being received.

`exterior` means not part of the project. External means outside the
functionality being examined but still within the repository. Either may
provide an EF or receive one. Exterior is lightly defined and exempt from the
reverse-reading requirement applying to the other trunks. Environment, person,
group, system, and framework are tentative exterior subgroups. These meanings
follow the [current clarification](../docs/semantics/artifacts-and-functional-intake.md).

The record's field names, multiplicity, and graph attachment layout remain to be
settled. These choices do not change the receiver's ownership of its OP.

### R3 — Retain OP typing and the use expressed by joins

Intake describes actual artifacts, functions, and specific receiving purposes,
organized by Types. The Property / Medium relationship and the Dependency
relationship in the supplied examples remain distinguishable through storage,
retrieval, and prepared context. Roles belong to receiver-owned OP joins.
Notable is retired as a separate category because OP already explains
participation. Parametric is a Type's tunables array; its names reserve the
corresponding Namespace addresses, and tuning alone cannot constitute acceptance.

### R4 — Update Native understanding from oversight examination

An operation examines latent Elements and joins in relation to Native project
understanding and determines whether the differences are non-issues or
oversights. When an oversight is identified, the process updates the Native
Metaform with the recovered understanding. Subsequent Native retrieval and
prompt preparation expose that update. The independently authored Latent
perspective remains available with its source attribution.

### R5 — Clone the Native Metaform to create a variant

A variant begins as a clone of the Native Metaform, including the understanding
and producing-prompt relationships needed for later regeneration. The source
Native Metaform continues to represent the base project. The clone develops the
target realization. Its base association makes that relationship inspectable.

The selected model is a clone. A comparison with the base may describe its
changes as a diff; a sparse overlay is not required to represent the variant.

### R6 — Change a relationship and detach its affected reasoning

In the porting variant, replace the relevant game's Property / Medium link to
`code.cpp` with a link to `code.javascript`. Detach the reasoning derived from
the replaced `code.game`–`code.cpp` relationship from the variant's active
understanding. The base retains its original relationship and understanding.

The operation follows the semantic relationships on which the reasoning
depends, including affected derived reasoning. Shared namespace ancestry alone
does not express that dependence. The algorithm for identifying the complete
affected set remains to be designed from recorded producing context.

### R7 — Ask the producing prompts again

Find the prompts that gave birth to the detached knowledge and issue them again
with the variant's updated semantic context. Preserve the originating operation
while replacing the changed context. Attach the resulting knowledge to the
variant with its new producing context. Later work reasons through those new
results.

The system needs an association between derived knowledge, the prompt that
produced it, and the semantic records/relationships used to produce it. Existing
prompt snapshots retain source text, revision, rules, and inputs; the feature
must connect that information to the affected graph knowledge. Choosing how
prompt revisions and recorded rule/input snapshots participate in reissue is
an implementation design decision, not a license to substitute another task.

## Current implementation evidence

| Responsibility | Existing implementation | Remaining work |
| --- | --- | --- |
| Intake and source-specific knowledge | `src/metaform/intake.py`: `_assignment`, `_remember`, `_commit_inference`; `src/metaform/data/semantics/native.md` and `archaeology.md` | Explicit upstream receiving-purpose record and the clarified OP typing |
| Element and relationship contracts | `src/metaform/data/schemas.json`: `metaform:element`, `metaform:join` | `en` still exists; no `length`, exterior contract, or complete typed OP contract is declared |
| Prompt preparation and observations | `src/metaform/prompts.py`: `snapshot`, `prepare`, `record_test` | Per-knowledge association to originating prompts and semantic dependencies |
| Persisted assignments and answers | `src/metaform/workflow.py`: `Engine.frame`, `next`, `submit`; `src/metaform/continuation.py` | Variant-aware context and regeneration orchestration |
| Reified graph references and source views | `src/metaform/graph.py`, `src/metaform/knowledge.py`, `src/metaform/similarity.py` | Variant identity, clone/reference handling, and semantic dependency tracing |
| History and captured knowledge | `src/metaform/history.py`, `src/metaform/knowledge_export.py`, `src/metaform/portable.py` | Preserve variant and producing-context associations in the relevant capture/export paths |
| Workbench | `src/metaform/viewer.py`, `src/metaform/static/workbench.js`, `src/metaform/templates/index.html` | Expose base/variant selection, typed OPs, derived names, and regeneration results |

These are reusable implementation facilities, not evidence of a completed
clone-and-regenerate operation. No live model demonstration was performed for
this documentation change.

## Proposed implementation responsibilities

These are implementation proposals for the agreed behavior, not additional
semantic rules or settled wire schemas:

- **Intake** develops the Type placement, derived-name extent, exterior
  receiving purpose, and typed OP relationships.
- **The oversight operation** examines differences and authors updates to Native
  project understanding from identified oversights.
- **Knowledge storage** retains a separately addressable variant and its base
  association, reified relationships, producing prompts, and dependencies.
- **Prompt preparation and workflow execution** assemble the variant context,
  reissue the producing operations, and retain their answers and continuations.
- **The workbench and agent interfaces** let users examine the base, variant,
  changed relationship, affected knowledge, and new reasoning.

Reuse existing schemas, graph references, prompt snapshots, and workflow
execution where they express these responsibilities. Concrete field names,
commands, and UI controls have not been agreed. Extending selected-project
export to carry the variant and its execution dependencies follows the existing
portable-project capability; this does not specify a new archive format.

## Acceptance scenarios

### V1 — Placement reuses the right general position

Start with `code.system.driver.video`. Name Network Driver, locate
`code.system.driver`, and create the sibling `code.system.driver.network`.
Store `length: 2`; extraction yields Network Driver. Repeat with a common name
having a different word count to demonstrate that extraction uses `length`.

### V2 — Exterior purpose is explicit project understanding

Intake a game whose exterior receiver is Player Group. Retrieve the DE's
attached receiving-purpose record and observe the identified receiver and its
OP for the DE's EF together. Preparing work through that record makes the
upstream purpose available to reasoning about internal decisions.

### V3 — A Medium property remains distinct from a Dependency

Represent the supplied game/C++ and game/rules relationships. Read them through
storage and prepared context. The first is Property / Medium; the second is
Dependency. Their receiver-owned purposes and provider EFs remain connected.

### V4 — An oversight improves Native understanding

Prepare a Native graph and an independently authored Latent graph with two
differences. Have the examination operation identify one as a non-issue and one
as an oversight. The resulting Native update contains the understanding from
the identified oversight, and subsequent preparation uses it. The operation's
answer and resulting update are available to inspect; the Latent source
remains independently observable.

### V5 — A porting variant regenerates affected knowledge

Start with a Native game Metaform, its Property / Medium relationship to
`code.cpp`, and derived knowledge linked to its producing prompts and semantic
dependencies. Include separate knowledge whose producing context is unaffected.
Clone the Native Metaform, replace the variant's Medium provider with
`code.javascript`, and observe:

1. The base retains its C++ relationship and knowledge.
2. The variant detaches the affected derived reasoning; unaffected knowledge
   remains available.
3. The originating prompts are issued against the changed variant context.
4. Their answers become new knowledge associated with the variant and their
   producing context.
5. Later porting work uses the regenerated understanding.

Fixture tests can establish record handling and context delivery. A live model
demonstration must separately show that the renewed reasoning is specific to
the new Medium and the affected functional Types.

### V6 — Producing context survives continuation and capture

Pause regeneration with an issued assignment, resume it through the existing
continuation mechanism, and inspect the answer's variant association. Capture
and export the selected project's relevant variant, prompts, records, and
execution dependencies using existing portability facilities. The captured
knowledge retains the associations required to understand and continue that
work. This is proposed integration verification for the existing portability
contract.

## Decisions still needed for implementation

- The exterior receiving-purpose record's schema and multiplicity.
- Applying name extraction to exterior entries and existing trunk names. For
  example, the current root `code` is named Program Code, which cannot be
  reconstructed from the one-component address by the new rule alone.
- Migration of existing `en` records to Namespace and `length`, including any
  semantic placement corrections and dependent references.
- How a variant is identified and associated with its base; which references
  are cloned and which continue to identify independent shared Type knowledge.
- How producing-context dependencies are recorded and traced, including joins
  referring to joins and reasoning that depends on other derived knowledge.
- The originating prompt/rule revision policy, regeneration ordering, and
  treatment of older knowledge without recorded producing dependencies.

The [implementation plan](native-metaform-variants-implementation-plan.md)
identifies the affected components and verification for these decisions.
