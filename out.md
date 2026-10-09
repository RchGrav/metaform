### **`metaform/docs/current-work.md`**

```markdown
# Current work

The [Metaform specification](SPEC.md) defines the product behavior, semantic
contract, and acceptance scenarios. The documentation is integrated; runtime
corrections are underway. Implementation and tests are evidence to compare
against the specification.

The [discussion handoff](discussion-handoff.md) collects subsequent semantic
clarifications and exploratory goals for coordination with an external agent.

## System review repairs — 2026-09-09

All 21 reproduced findings in the [system review](reviews/2026-09-09-end-to-end-system-review.md)
are repaired and covered by regression tests. The full suite passed 501 tests on
both Python 3.11 and 3.13; fresh installed-wheel checks passed on both, including
standalone export and service-free continuation. [Verification](verification.md)
records the scope and limits of that evidence.

The repairs preserve assignment and workfolder ownership, archive boundaries,
schema ownership, reused join identities, and independent Contextual/Latent
sources. Proof now prepares schema copies for latent inference. Dependency
scheduling follows eligible referenced Types, and similarity preserves qualified
reified references with fresh knowledge across CLI, viewer, and intake paths.
Viewer crash recovery and image output attribution/readiness are also corrected.
The broader semantic demonstrations and build work listed below remain open.

## Runtime corrections implemented

- Contextual and Latent Elements now retain independently readable source
  contents through scoped retrieval, search, assembly, export, command routing,
  and the viewer. Source edits and export/import preserve that separation across
  SQLite, JSON, and Ladybug. Proof corrections update the Contextual record.
- Structural similarity covers `01`, `10`, and `11` using node identities,
  join types, participant roles, and references, including cyclic references to
  joins. It contains structure and source references; Element contents, purposes,
  and join logic remain source-local. The viewer exposes a read-only similarity
  view and treats stored similarity joins as read-only in other views.
- Applying specialized workflows preserves revised prompt wording and gives
  source-owned embedded prompt declarations local IDs. Execution retains the
  specialized control flow while source prompt records remain unchanged.
- Type proof now returns Contextual corrections separately from prepared
  latent inference records, including for known Types awaiting inference. New global
  promotion, focal assignments, and incomplete-Type lookup use prepared records.
  Existing global definitions remain stored unchanged. Old issued assignments
  retain their snapshots; remaining unissued work receives preparation.

## Shared knowledge and portable projects

The shared knowledge service and portable-project implementation is integrated.
Its initial verification on 2026-09-08 passed 396 tests on both Python 3.11 and
3.13, plus rebuilt distribution checks,
including service-free nested continuation and re-export. Browser project
selection and installed Cypher refresh also passed; see [verification](verification.md).
This storage and runtime work preserves the semantic contract above.

- New installed projects use one authenticated user-local service per resolved
  home. Existing projects retain their configured backend until explicit
  `project connect`. Canonical-path registration, project selection, relocation,
  explicit copied-owner registration, verified liveness, and service stop are
  implemented. Runs, assignments, and workfolders remain project-local.
- Central SQLite retains owner-qualified records, independent Native/Latent
  sources, provenance, and transactional request receipts. Inference completion
  includes the global result and project Latent write in one transaction; retries
  recover committed responses and local workfolder cleanup. Inference lookup
  remains global-only and preserves precise reference owners and kinds.
- Selected export follows eligible project/global references using SQLite indexes
  in one read transaction. Its tests include unrelated global records and a
  concurrent writer. Ordinary graph mutations still reconstruct one owner
  partition; mutation scaling remains a practical limitation.
- Version 2 archives carry selected knowledge and executable dependencies,
  qualified schemas, source observations, historical evidence, assignments, and
  required assets. Portable JSON and local SQLite continue without the service,
  original home, or Cypher. The logical project owner remains stable and a
  separate `copy_id` identifies the working copy. Archive import accepts versions
  1 and 2 and retains history behavior; shared-service reconciliation is not
  implemented.
- Installed Ladybug analysis copies retain Cypher with explicit refresh and source
  revision metadata. Core knowledge, prompt, workflow, and export operations do
  not depend on those copies.

## Build corrections remaining

1. Reconcile intake records, the registered Element schema, and downstream graph
   storage against the contract. `entity_desc` already carries ED; the missing
   `ed` property in `metaform:element` alone does not demonstrate data loss.
   Schema-valid data does not establish semantic completeness. Preserve the
   established Element roles and their authored definitions throughout intake
   and later use.
2. Demonstrate the specified Encounter propagation and differentiated general
   operations using acceptance scenarios A-5 through A-8. Generic graph traversal
   and fixture answers do not establish those semantic outcomes. Nested or
   overlapping Encounter composition remains an open question in the specification.
3. Implement leaf-alias lookup and reservations at expanded Namespace addresses,
   and carry Parametric names from the intake array into address reservation
   without creating parameter nodes.
4. Complete the remaining rulebook content: Alias and Dependency entries and a
   descendant Description example. Existing Name and Description formulas remain
   exact; [seed provenance](rulebook/seed-sources.md) distinguishes their supplied
   wording from assistant-authored explanations and examples.

## Settled details retained for implementation

- The **Native Expert** examines the project to identify the **Defining Element**.
  Element descriptions describe the functional Types the code uses or realizes,
  whether locally implemented or framework-supplied, rather than descriptions
  of source code or written functions. The **Latent Expert** reasons from those
  Types. The broader contents of contextual Operative Purposes remain open.
- **Defining Element** is the established term. **Notable Element**,
  **Parametric Element**, and **Stylistic Element** retain their authored terms
  and definitions. The [glossary](../src/metaform/data/semantics/glossary.md)
  supplies those definitions.
- Alias names reserve only the corresponding expanded address for that Artifact
  Type. `code.cpp.11` may resolve to `code.cpp.cxx11`; `code.c.11` remains
  independently usable. The maintained [Aliases equations](semantics/inference_metaform_rules.md#aliases)
  are already bundled and delivered verbatim, with an explicit source override
  supported. Address resolution and reservation remain unimplemented.
- Parametric Elements use an array when present. Their names reserve the
  corresponding Namespace addresses and block competing Element nodes. A
  Parametric adjustment alone is not an imperative's acceptance signal. The owner's
  exact clarification is in the [worked explanations](semantics/understanding-and-work.md#parametric-intake-data-reservations-and-adjustments).
- Relationship typing belongs in the **intake join dictionary**; the intake
  shape does not itself specify the persistence layout. OP belongs to its
  Receiving Entity. Namespace ancestry alone does not establish an OP relationship.
- Project-level inference selects semantic Namespace placement. Different
  placement can identify different Elements even when both refer to Box2D;
  `code.game` is not a mandatory trunk. The [worked explanations](semantics/understanding-and-work.md)
  preserve the supplied examples and the distinction between intake vocabulary
  and the vocabulary used for working prompts.
- Each focal Type receives independent latent inference context. The global graph
  contains reusable, independently inferred Type dependency structures.
  Existing Type presence and completed inference are separate states. Current
  scheduling, completion, and reuse behavior is described in the
  [workflow format](workflows.md) and [architecture](architecture.md).

## Supporting implementation and verification

The existing build includes the rule and prompt editors, provider → receiver
relationship display with OP labels, Namespace labels, graph/list switching,
source filtering, and direct connection browsing. CLI/MCP routing, workflow
execution, history/export, packaging, CI, image generation, and module loading
are implemented supporting capabilities; their presence does not establish
additional core product requirements. Interface and scope decisions remain in
[workbench cleanup](workbench-cleanup.md).

The last recorded collection reset cleared the rejected example intake data;
input artifacts and the separate display fixture were retained. Live intake has
not been restarted during these corrections. Historical trial evidence and
its limitations remain in [MVP review](mvp-review.md).

Before the shared-service integration, the full runtime suite passed 248 tests; subsequent prompt migration and rulebook
checks passed 24 tests. The wheel build and browser
checks passed; browser checks covered distinct source records and read-only
similarity inspection. Similarity regressions cover 1,100 independent joins,
a 1,100-link chain, and a 1,100-join cycle. These checks establish implementation
behavior. A subsequent live comparison used four Type cases in two matched
repeats: combined proof/handoff preserved supplied role names that a separate
route lost, while both removed the tested project OPs. Four fresh downstream
Latent inference calls retained that difference; they do not establish a general
Latent-graph quality ranking. The selected built-in proof also produced four
accepted handoffs through the runtime. This does not certify arbitrary historical
global records as decontextualized. Use the
[acceptance scenarios](SPEC.md#acceptance-scenarios) to distinguish contract
behavior from supporting infrastructure tests and superseded expectations.
[Verification](verification.md) records the test commands and evidence limits.

```

### **`metaform/docs/mvp-review.md`**

```markdown
# Relationship display correction and intake reset

The owner directed the previous collected data to be cleared rather than patched.
The example and its isolated global store now contain no collected Elements,
joins, completed inferences, runs, pending assignments, or responses. The
example's `handler.py` and `module.json` source files remain.

The workbench is available at <http://127.0.0.1:43679/> while its local server
is running; <http://127.0.0.1:43679/?view=list> opens the list presentation.
Both Graph and List show only Metaform data and are empty after reset.
Rules contains five refreshed seeds; Prompts contains nine refreshed seeds.
The handler and dispatcher examples explain comprehensive functional parents,
single-word Namespace components, and deterministic construction. The original
Name and Description concise statements remain intact.

Intake has not restarted. The next work is to agree on the collected Element
and OP record shape before collecting new data. OP ownership, provider-to-
receiver display, and purpose labels must be represented faithfully. The
renderer now displays unambiguous provider → receiver relationships directly,
with OP labels. It does not turn join records into Element nodes. This does not
validate the discarded records or finalize the intake/storage contract.

The status counts are recorded locally in `dist/mvp-review/reset-status.json`.


## Preserved explanations

[Developed understanding, receiving relationships, and work](semantics/understanding-and-work.md)
contains the owner's exact statements, separately marked interpretation, and links to
his photograph examples in `media.photo.product.used/`. Name removal and complete
photo seed definitions remain proposals, not implementation changes.

## Display review

The Elements and Joins tables use the same filtered Metaform as the graph.
Selecting an Element shows the providers it receives from and the receivers it
supplies in that view. Selecting an arrow or a join row opens the OP editor.
Namespace lineage alone creates no displayed dependency edges. Joins without an
unambiguous pair of endpoints remain inspectable in List; the viewer does not
invent their direction or decompose them into false binary relationships.

The isolated browser-check fixture at `dist/graph-review/` uses exactly the
supplied `media.image.sheet.sprite → code.game.platformer.2d` relationship,
labeled “visual representation of objects.” It supplies no inferred definitions
and runs no intake. It is separate from the empty example project.
Browser captures are `dist/graph-review/direct-relationship.png` and
`dist/graph-review/mobile-list.png`; these are local verification artifacts.

Browser checks cover direction, exact OP, both neighborhood directions,
connection navigation, canvas and list inspection, filtering, and mobile layout,
with no writes or browser errors. API tests also preserve structured OP values,
provenance filters, partial records, and multi-party or join-referencing records.

Verification on 2026-09-08: **144 tests passed** with
`uv run --frozen pytest -q --basetemp=.test-tmp/graph-view-suite`.
`node --check src/metaform/static/workbench.js` and `git diff --check` passed.
The browser check script and captures are in `dist/graph-review/`. The full-suite
temporary directory must not be Git-ignored: intake file discovery respects Git
exclusions, so placing its project fixtures under ignored `dist/` hides their
input files. The failed ignored-directory run passed after correcting that test
invocation; production code was not changed for it.

```

### **`metaform/docs/ci.md`**

````markdown
# Metaform CI and fork setup

The repository is currently private while Metaform is tested and refined. CI
produces artifacts in the repository that runs it. Publication to a package
index, releases, or a public site is a separate operation.

## What the workflow does

`.github/workflows/wheel.yml` runs on pushes, pull requests, and manual dispatch.
It uses the current repository's checkout and locked dependencies. Both Python
3.11 and 3.13 run the source tests, build the wheel and extensionless archive,
and verify the installed package. The release check also creates an empty
Python environment to exercise the portable CLI/MCP, GUI, and export round trip.

Each Python job uploads `dist/*.whl` and `dist/metaform` to its run artifacts.
There are no Metaform-specific secrets to copy into a fork. The workflow has
`contents: read` permissions and uses the standard artifact upload action.

## Activate a fork

GitHub workflows are disabled in newly forked repositories by default.
The owner can enable them in the fork's Actions tab or use the packaged helper:

```sh
gh auth login
metaform package ci --repository YOUR_ACCOUNT/metaform
```

From the fork's checkout, `metaform package ci` resolves its `origin` remote.
It does not use GitHub CLI's inferred upstream repository. Explicit repository
arguments also accept GitHub URLs. To build another branch:

```sh
metaform package ci --repository YOUR_ACCOUNT/metaform --ref work/semantics
```

The command reads the selected repository, reads its `wheel.yml` workflow,
enables that workflow if disabled, and sends a workflow dispatch for the selected
ref. Without `--ref`, it uses that repository's default branch. Its result
contains the repository, visibility, ref, and build/workflow URL. GitHub API
errors are returned as errors; requesting a build is distinct from the build
succeeding.

An agent can call the same handler through MCP:

```json
{"command":"package.ci","arguments":{"repository":"YOUR_ACCOUNT/metaform"}}
```

That is the `metaform` routing tool's input. Clients exposing individual tools
can call `package.ci` with the inner arguments directly.

## GitHub requirements

The workflow file must be present on the repository's default branch for manual
dispatch. During development, pushing a branch containing the workflow can run
its push-triggered CI before that branch is merged.

The GitHub CLI uses the owner's existing authentication. Fine-grained credentials
need **Actions: write** for workflow activation and dispatch; classic credentials
need the `repo` scope for private repositories. Organization and repository
Actions policies still apply. An Actions policy that disables the feature must
be addressed in the repository or organization settings by an authorized owner.

Private-fork pull requests also depend on the parent repository's fork workflow
policy. A build running in the fork and a pull-request build running in its
parent are distinct runs. The helper activates the selected repository's
workflow; it leaves the parent's policies to its owner.

## References

- [Events and forked repositories](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows)
- [Enable and dispatch workflows through the API](https://docs.github.com/en/rest/actions/workflows)
- [Manual runs and the default branch requirement](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/manually-run-a-workflow)
- [Repository Actions settings and private forks](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/enabling-features-for-your-repository/managing-github-actions-settings-for-a-repository)

````

### **`metaform/docs/SPEC.md`**

````markdown
---
id: SPEC-metaform
sources:
  - README.md
  - docs/primer/01_full_explanation.md
  - docs/primer/02_specification_introduction.md
  - docs/primer/03_technical_account.md
  - docs/semantics/inference_metaform_rules.md
  - src/metaform/data/semantics/glossary.md
  - src/metaform/data/semantics/native.md
  - src/metaform/data/semantics/archaeology.md
  - docs/workflows.md
  - docs/workbench-cleanup.md
---

> **Canonical contract.** This document defines the intended semantic product behavior for Metaform. Explicit user-supplied definitions and corrections govern it. Repository implementation and tests are evidence to compare against this contract, not sources of truth by existence.

# Metaform

[Capabilities](#capabilities) · [Semantic contract](#semantic-contract) · [Acceptance scenarios](#acceptance-scenarios) · [Current work](current-work.md)

## Why

Metaform exists to amortize reusable inference: perform type-level semantic reasoning in advance, preserve it as a reusable Inference Metaform, and let later prompts and workflows begin from that developed understanding instead of repeatedly reconstructing the same prerequisites from raw artifacts. The desired effect is more reasoning available for higher-order work such as diagnosis, review, refactoring, porting, foresight, and open-ended project operations, while preserving semantic identity through change rather than freezing the present implementation.

## Capabilities

- **CAP-1 — Reusable inference preparation**
  - **intent:** The system can prepare reusable semantic understanding so later operations can address project and type meaning without reconstructing the same prerequisite inference from raw artifacts each time.
  - **success:** After preparation, a compact type-level instruction can produce project-specific results that depend on represented semantic relationships without restating those relationships in the instruction.

- **CAP-2 — Contextual Metaform**
  - **intent:** The system can construct a Contextual Metaform from the actual project or implementation plan, preserving project-local Elements and semantic relationships with contextual provenance.
  - **success:** Project-derived Receiving Entities, Operative Purposes, Encounter Functions, Elements, and joins are represented with provenance that distinguishes them from latent inference.

- **CAP-3 — Latent Metaform**
  - **intent:** The system can construct a project-decontextualized Latent Metaform from project-derived Artifact Types without receiving the project's joins or Operative Purposes.
  - **success:** A latent pass can produce relationships absent from the contextual layer, while its input does not expose the contextual joins or OP relationships that would supply the answer.

- **CAP-4 — Shape-similarity layer**
  - **intent:** The system maintains the Contextual and Latent Metaforms as complete, independent graphs and provides a separate structural similarity layer for observing where their shapes agree or differ.
  - **success:** Neither source graph is merged into the other and no semantic payload is copied into the similarity layer. The similarity layer records only structural correspondence and provenance references: contextual-only (`01`), latent-only (`10`), or structurally present in both (`11`). When the same nodes and join exist in both source graphs, the layer can show that structural agreement. If the source join contents differ, both source joins remain intact and independently observable with their provenance.

- **CAP-5 — Project-inferred strict typology**
  - **intent:** The system can infer a project-appropriate strict typology in which every namespace prefix is itself a promptable Artifact Type expressed through Function or Encounter rather than taxonomy filler.
  - **success:** The project-level typing inference selects a path whose prefixes are independently meaningful Artifact Types; class/domain filler is rejected; an encoding-only distinction does not qualify merely because it is a format name.

- **CAP-6 — Element roles**
  - **intent:** Intake identifies the established Element roles required by the semantic model and preserves their exact authored terms and definitions because those roles materially orient later inference.
  - **success:** The resulting Metaform retains the relevant Element roles using the established semantic terms verbatim; later inference can address those roles directly, and no layer substitutes alternate role names, taxonomy classes, synonyms, or paraphrases.

- **CAP-7 — Encounter propagation**
  - **intent:** The system can propagate an Encounter through the functional type structure so inference at each affected type is conditioned by the relevant realization or encounter.
  - **success:** If `code.bash` is linked to an installer type and `code.cpp` to a game-engine type, broad `code` reasoning can see both; each Encounter conditions the appropriate branch without leaking into an unrelated sibling branch solely through their common ancestor.

- **CAP-8 — Open-ended type-level operations**
  - **intent:** The system can execute general prompts across Artifact Types and their relationships without requiring a dedicated hard-coded operation for each reasoning task.
  - **success:** One instruction such as generating best practices or imperatives for every relevant type produces type-specific output conditioned by each type's connected Elements, Encounters, Receiving Entities, and Operative Purposes.

- **CAP-9 — Workflow specialization**
  - **intent:** The system can resolve a general workflow or prompt into the relevant project Artifact Types and semantic relationships while preserving the source operation's intent and control flow.
  - **success:** A specialized workflow addresses concrete project semantics without adding unrelated requirements or changing authored branching/sequence semantics.

- **CAP-10 — Bias/blindness comparison**
  - **intent:** The system can use contextual/latent divergence as an inference surface for examining project-local blind spots and alternative type knowledge.
  - **success:** An operation can select latent-only structure, compare it with contextual structure, and reason whether it is useful, already covered elsewhere, deliberately absent, or evidence of a local omission.

- **CAP-11 — Refactoring through semantic relations**
  - **intent:** The system can reason about refactoring through represented type meaning rather than treating the current implementation shape as the thing that must be preserved.
  - **success:** Refactoring guidance can consider radically different realizations through the relevant Functions, Encounters, Receiving Entities, Operative Purposes, and relationships needed by the work.

- **CAP-12 — Porting through Encounter change**
  - **intent:** The system can reason through a source and target Encounter to derive type-specific porting considerations and imperatives across the affected functional structure.
  - **success:** Changing an implementation Encounter such as language changes the derived guidance at each affected Artifact Type without mechanically treating source syntax or structure as the type definition.

- **CAP-13 — Coarse semantic representation**
  - **intent:** The Metaform represents enough type-level semantic shape to reason effectively without attempting to enumerate every true property, purpose, environment fact, or implementation detail.
  - **success:** The graph remains compact enough for reusable inference while still allowing later operations to deepen selectively through connected Elements and relationships when the task requires it.

- **CAP-14 — Shared knowledge and independent portable projects**
  - **intent:** Projects can use a shared knowledge service and carry their related understanding into a self-contained executable export.
  - **success:** Export follows global and selected-project relationships, including workflow dependencies, while other projects' local relationships remain outside its traversal. Source contents and provenance remain intact. The exported project can read and extend its JSON knowledge, continue work using local SQLite execution state, and export again without the service or Cypher. Installed backends retain Cypher for development and analysis.

## Constraints

- `C(T)` defines semantic type identity. It is part of the semantic model, not a required runtime mechanism.
- Contextual and Latent Metaforms must remain complete and independently observable; `01`/`10`/`11` belong to the shape-similarity view and encode structural presence, not confidence, truth, verification, precedence, or merged semantic content.
- The latent construction must not receive project joins or project Operative Purposes that collapse the independent perspective.
- The namespace is a strict typology, not a domain/class taxonomy. Every namespace prefix must itself express a valid Function or Encounter type.
- Established semantic terms are operative semantic content and must be preserved verbatim. The system must not paraphrase, rewrite, normalize, synonym-substitute, rename, collapse, or replace an established semantic term, including Element-role names.
- Canonical typology path/order is inferred at the project level; it is not selected by a universal lexical ordering rule.
- Each Artifact Type has one Encounter Function at its represented resolution. A materially different Encounter implies a different Type/variant, expressed through the typology rather than by adding another EF to the same Type.
- Receiving Entities and Operative Purposes are modeled coarsely enough to provide a useful reasoning frame rather than exhaustively enumerating every possible purpose. Apparent over-specificity is resolved by generalizing the Encounter Function or distinguishing the Receiving Entity where appropriate.
- Encounter-linked project properties remain project-local unless independently established as global type knowledge.
- The operation surface remains open-ended. Refactoring, porting, diagnosis, best-practice generation, foresight, and review are examples, not a closed operator catalog.
- The base Metaform need not encode every true environmental fact. Environmental context belongs only where it materially affects the semantic reasoning required.

## Semantic contract

### 1. Artifact Type identity

For an Artifact Type `T`, the formal identity is the exact set:

`C(T) = {(rᵢ ∧ pᵢ ∧ e)}`

where each conjunction binds:

- `rᵢ` — Receiving Entity: the **who or what** receiving the effect;
- `pᵢ` — Operative Purpose: the **why** owned by that Receiving Entity;
- `e` — the Type's single Encounter Function: the **how** through which the effect is realized or encountered.

`C(T)` is exact as a semantic definition. It is not a lower bound, partial signature, similarity measure, confidence score, or candidate identity projection.

An Artifact Type has one Encounter Function at the represented resolution. A materially different Encounter makes a different Type or variant, represented through a further typological distinction rather than by adding a second EF to the same Type.

Receiving Entities are connected at the most general level that still preserves the useful Operative Purpose. The goal is a coarse reasoning frame, not exhaustive enumeration of every purpose or possible receiver. If an apparent distinction forces the EF or OP into excessive specificity, the model should seek a more general Encounter Function or distinguish the Receiving Entity appropriately.

These definitions describe the semantic relationship that protects type meaning through change. They do not prescribe a runtime identity-checking mechanism.

### 2. Element roles

Element roles are semantic and materially affect inference. They are not taxonomy classes, and the specification must not rename them into class-oriented terminology.

The established role terms found in the semantic sources include **Defining Element**, **Notable Element**, **Parametric Element**, and **Stylistic Element**. Their exact names and definitions must be preserved as authored.

Intake identifies Element roles because those roles are part of the semantic shape used for later inference.

#### Element descriptions and expert roles

The **Native Expert** examines the project to identify the **Defining Element** and the functional Types the code uses or realizes. Element descriptions must describe those functional Types, whether locally implemented or supplied by a framework. They must not be descriptions of source code or of the written functions themselves.

The project supplies evidence for identifying these Types. Describing their functional meaning gives the **Latent Expert** a subject through which to draw on relevant expertise about capabilities, dependencies, Encounters, and receiving relationships. That Type understanding also lets later operations reason about different realizations of the same function.

#### Semantic term preservation

Defined semantic terms are operative semantic content. The system must preserve established terms verbatim. It must not paraphrase, rewrite, normalize, synonym-substitute, rename, collapse, or otherwise restate an established semantic term as a different term. This applies to Element-role names and to every other defined semantic term in Metaform.

New semantic records may be authored where the process calls for a new record, but an existing established term is not rewritten into alternate wording by intake, latent inference, similarity processing, storage, MCP presentation, workflow specialization, or another system layer.

### 3. Type meaning through change

The semantic relationship defines what the Type means independently of its present implementation. This allows substantial changes in realization without treating current code, structure, or content as a frozen core that must be preserved.

The identity definition is semantic guidance for reasoning about the Type; it does not itself prescribe an approval gate, lifecycle, or runtime check.

### 4. No frozen implementation context

The represented type meaning allows operations to reason about alternative realizations without making the current realization the definition of the thing.

### 5. Strict typology

The dotted namespace is a **typology**, not a taxonomy.

For `a.b.c`, each prefix is itself a promptable Artifact Type:

- `a`
- `a.b`
- `a.b.c`

No `domain.class.type` alignment layer exists. A segment belongs because the path speaks to a valid Function or Encounter sprung from its parent, not because a class label makes a hierarchy look regular.

Function expresses operative capability. Encounter expresses how a Function/type is encountered or realized, including variants such as programming language, style, genre, and similar forms. Encoding alone does not qualify as a type; an encoding name may appear where the path is actually expressing a Function, such as an encoder.

Every Element can be examined and prompted as an Artifact Type at the resolution under discussion.

### 6. Typology path and linked properties

The dotted path itself carries meaning because every prefix is independently promptable as an Artifact Type and therefore requires its own valid type-level name and description.

Canonical path/order is inferred at the project level. There is no universal lexical rule that mechanically decides whether, for example, a game-engine Type should be expressed under a game path or an engine path; project-level inference selects the typological path that best expresses the Type in context while keeping every prefix valid.

An Encounter does not have to be appended to the Artifact Type's dotted path. It can be linked as a property/relationship to the relevant type. For example an installer Type may be linked to `code.bash`, while a game-engine Type may be linked to `code.cpp`.

Project-local linked properties remain project-local. Their presence does not automatically promote them to global type knowledge.

### 7. Encounter propagation

Encounter is transitive through functional type structure in two distinct senses:

1. **Backward visibility:** an Encounter linked deeper in a branch is available when reasoning at broader ancestor types.
2. **Forward application:** from its attachment point, the Encounter conditions inference through the functional descendants of that branch.

Backward visibility does not cause an Encounter to fan back down unrelated sibling branches.

Example:

```text
code
├── installer            ↳ code.bash
└── game
    └── engine           ↳ code.cpp
        ├── renderer
        └── physics
```

Expected reasoning scope:

- `code` can reason with both Bash and C++ as Encounters present in its functional descendants;
- `installer` and its functional descendants reason through Bash;
- `game`, `engine`, `renderer`, and `physics` reason through C++ where that Encounter applies;
- `installer` does not inherit C++ merely because C++ is visible at `code`;
- `renderer` does not inherit Bash merely because Bash is visible at `code`.

Composition rules for nested or overlapping Encounters remain open.

### 8. Contextual and Latent Metaforms

The **Contextual Metaform** records project-local semantic understanding derived from the actual project or implementation plan.

The **Latent Metaform** is derived independently from project-derived Artifact Types without the project's joins and Operative Purposes supplying the relational answer. It develops its own type relationships from learned type knowledge.

The Contextual Metaform and Latent Metaform remain complete, independent graphs. They are not merged, averaged, or rewritten into a third semantic graph. Both remain directly viewable and observable, including through MCP.

A separate **shape-similarity layer** exists for one purpose: to show structural agreement and divergence between those two graphs. It contains no copied semantic payload from either source graph; it records only structural correspondence and provenance references.

Shape membership:

- `01` — structure present in the Contextual Metaform only
- `10` — structure present in the Latent Metaform only
- `11` — the same nodes and join structure are present in both

These values do not encode confidence, correctness, precedence, or semantic reconciliation. When both source graphs contain the same nodes and a join between them, the similarity layer may represent that structural agreement as `11`. If the source join contents differ, both source joins remain intact in their respective graphs and retain their own provenance; the similarity layer does not collapse, copy, or reconcile their contents.

### 9. Inference amortization

The Metaform stores reusable semantic understanding, not a catalog of completed task answers. The prompt/workflow and Metaform remain separable: a prompt describes an operation; the Metaform supplies previously inferred project/type meaning through which that operation is interpreted.

This permits general instructions such as:

- evaluate latent-only Elements for project usefulness or existing coverage;
- generate type-specific best practices or execution imperatives for every relevant Element;
- change an implementation Encounter and derive porting imperatives across affected functional types;
- evaluate a proposed refactor through connected Elements and their reciprocal Operative Purposes.

These are examples of open-ended operations, not a mandatory workflow library.

### 10. Coarse base shape and operation-specific depth

The Metaform's base semantic shape is intentionally coarse. It exists to put forward enough type knowledge and relationship structure to reason on, not to enumerate all possible facts about an artifact or to reproduce the implementation at another abstraction layer.

Later operations may select deeper connected Elements, properties, and relationships when the operation needs them. That additional depth is task-driven and open-ended; it is not required in order to mechanically police Artifact Type identity.

## Non-goals

- Reproduce the implementation as an exhaustive semantic graph.
- Preserve the present implementation shape as a proxy for identity.
- Treat contextual/latent agreement as proof of truth or confidence.
- Replace subsequent inference with stored completed answers.
- Make every current chassis feature—workbench, MCP exposure, packaging, CI, image generation, history/export—a core semantic product requirement merely because it exists in the repository.

## Success signal

A prepared Metaform can take a short, general type-level instruction and produce correctly differentiated reasoning across a heterogeneous project according to each Artifact Type's relevant semantic relationships, while enabling substantial changes of realization and open-ended higher-order reasoning.

## Semantic sources

The established Name, Description, typology, and Aliases equations are maintained in
[Inference Metaform Rules](semantics/inference_metaform_rules.md). The
[Aliases section](semantics/inference_metaform_rules.md#aliases) is bundled verbatim
for intake; `semantic_sources.aliases` can select an explicit source override.
The [glossary](../src/metaform/data/semantics/glossary.md) supplies the established
Element-role definitions. [Semantic Equation Preservation and Reuse](semantics/semantic_equation_reuse_rule.md)
defines how authored semantic equations are carried into later inference.

## Open Questions

- What should contextual Operative Purpose contents express? The Element-level description clarification does not settle this broader question.
- How do Encounter propagation and composition behave when multiple Encounters overlap within the same functional region or when a nested variant creates a new Type?
- When an environmental vector materially affects reasoning, how is it represented without making environmental detail part of the mandatory base shape?

## Acceptance scenarios

These scenarios define semantic demonstrations for the contract. They are intentionally independent of the current implementation and test suite.

### A-1 — Strict typology rejects class filler

Given proposed types:

- `code.cpp`
- `code.language.cpp`
- `code.game.platformer`
- `code.game.genre.platformer`

The typing operation accepts `code.cpp` and `code.game.platformer` when those paths speak to valid Encounters, and rejects the class-filler forms `code.language.cpp` and `code.game.genre.platformer`.

The reason must be semantic qualification of each path segment, not a hard-coded blacklist of the words `language` or `genre`.

### A-2 — Encoding name is judged by what the path expresses

Given:

- `document.html` where HTML is used only as document encoding;
- `code.html` where HTML is being treated as a language Encounter;
- `code.encoder.jpg` where JPG participates in an encoding Function;

The first fails type qualification, while the latter two can qualify because their paths speak to Encounter or Function rather than expressing an encoding as the Type.

### A-3 — Established semantic terms remain verbatim

Given an established semantic source containing terms such as **Receiving Entity**, **Operative Purpose**, **Encounter Function**, **Defining Element**, **Notable Element**, **Parametric Element**, or **Stylistic Element**, pass that material through intake, latent inference, storage, MCP retrieval, similarity processing, or workflow specialization.

Expected:

- the established term remains exactly the established term;
- no layer replaces it with a synonym, paraphrase, normalized label, alternate role name, or taxonomy-oriented class name.

### A-4 — Contextual and Latent graphs remain intact behind a similarity view

Given a Contextual Metaform containing a project-specific OP relationship for Artifact Type `X`, construct the Latent pass for `X` without that project OP relationship or project joins in its input.

Expected:

- the latent result is independently authored;
- the complete Contextual graph remains intact and observable;
- the complete Latent graph remains intact and observable;
- the shape-similarity layer contains no copied semantic payload from either graph;
- structure present only contextually is shown as `01`;
- structure present only latently is shown as `10`;
- when the same nodes and join structure exist in both graphs, the similarity layer can show `11`;
- if the two source joins have different contents, both source joins remain intact and separately attributable;
- `11` is never interpreted as confidence, truth, or semantic reconciliation.

### A-5 — Encounter propagation respects branch scope

Given:

```text
code
├── installer            ↳ code.bash
└── game
    └── engine           ↳ code.cpp
        ├── renderer
        └── physics
```

Expected:

- reasoning at `code` can account for both Bash and C++;
- `installer` and its functional descendants are conditioned by Bash;
- `game`, `engine`, `renderer`, and `physics` are conditioned by C++ where applicable;
- Bash does not flow into the game/engine branch merely because it is visible at `code`;
- C++ does not flow into the installer branch merely because it is visible at `code`.

### A-6 — One general instruction produces type-specific reasoning

Given the graph in A-5, issue one operation equivalent to: “For every relevant node type and its properties, derive ten best practices.”

Expected output is not one generic list copied to every node. At minimum:

- `code` can distinguish relevant Bash and C++ perspectives;
- `code.installer` yields installer reasoning conditioned by Bash;
- `code.game.engine` and its applicable descendants yield their own functional reasoning conditioned by C++.

The operation must not require dedicated hard-coded “Bash installer best practices” and “C++ game engine best practices” commands.

### A-7 — Workflow specialization preserves authored behavior

Given a general workflow containing authored sequence, branches, and prompts, specialize it against a project Metaform.

Expected:

- general terms resolve to relevant Artifact Types and relationships;
- source intent remains intact;
- existing control flow remains intact unless the source itself calls for a structural inference;
- no additional quality gates, preservation requirements, or hidden rounds appear merely because specialization occurred.

### A-8 — Refactor and porting reason through semantic structure

Given a type whose current realization uses one implementation Encounter, ask Metaform to reason about a substantial refactor or a port to another Encounter.

Expected:

- guidance is derived through the represented Functions, Encounters, Receiving Entities, Operative Purposes, and connected Elements relevant to the work;
- substantially different realizations can be considered through the same prepared semantic understanding;
- porting guidance can change with the target Encounter while remaining specific to each affected Artifact Type.

````

### **`metaform/docs/workflows.md`**

````markdown
# Executable workflow format

This document describes the current execution API. [SPEC](SPEC.md) defines
intended operation and specialization behavior; [current work](current-work.md)
tracks outstanding alignment and semantic demonstrations.

A workflow has an `id`, optional `intent` and `start`, and ordered `steps`.
Import creates an Element Table record for the procedure and each step, plus
membership and transition joins. The engine reconstructs its definition from
those records. Editing a transition join changes subsequent runs. Each frame
snapshots its steps and referenced rule expressions when it starts.

```json
{
  "id": "example.review",
  "steps": [
    {
      "id": "review",
      "prompt": "Review {{ inputs.element }} against its Operative Purposes.",
      "focal": "{{ inputs.element }}",
      "depth": 2,
      "schema": {
        "type": "object",
        "properties": {"revise": {"type": "boolean"}, "work": {"type": "string"}}
      },
      "transitions": [
        {"when": {"var": "steps.review.revise"}, "to": "revise"},
        {"to": "record"}
      ]
    },
    {"id": "revise", "prompt": "Perform: {{ steps.review.work }}", "next": "review"},
    {"id": "record", "prompt": "Record the completed work.", "next": null}
  ]
}
```

The sample specifies no extra quality rubric or frozen properties. Its condition
is an authored control-flow decision. There is no hidden round, recursion, or
graph-layer limit. `drive --steps` in the structured interface, or raw
`drive HARNESS STEPS`, gives an explicit execution budget. Hosts can also impose
their own protocol limits; the pending assignment remains durable if they stop.

| Step kind | Additional fields | Execution |
| --- | --- | --- |
| `prompt` (default) | `prompt`, optional `schema`, `focal`, `inputs`, `save_as` | Yield an assignment and wait for its answer |
| `branch` | `transitions` | Evaluate conditions and advance one structural step |
| `foreach` | `items`, `prompt` | Snapshot items, assign each one, retain ordered answers |
| `call` | `workflow`, `inputs` | Push a child workflow frame and return its result |
| `tool` | `tool`, `arguments` | Invoke the named chassis command and record its result |

`next: null` finishes a frame. Without transitions or `next`, execution continues
to the next ordered step. Transitions are evaluated in order; their `to` can be
null. A transition can reference `rule: "data.some_rule"`, whose record contains
`{"expression": ...}`. A top-level recursive run, created by `workflow.recurse`,
records its parent and carries the parent's saved values plus explicit inputs.

The expression environment includes `inputs`, `steps`, saved values, and during
foreach, `item` and `index`. `{ "var": "steps.review.revise" }` reads a value;
`{ "literal": value }` passes data without interpreting it as an expression.
Other supported operators: `and`, `or`, `if`, `==`, `===`, `!=`, `<`, `<=`, `>`,
`>=`, `+`, `-`, `*`, `/`, `%`, `!`, `in`, `cat`, and `count`. This is a small
Python-semantics expression language inspired by JsonLogic, not a compatible
implementation of all JsonLogic operators/coercions. Unknown condition operators
raise an execution error. There is no Python `eval` or implicit code execution.

Jinja expressions bind declared values in prompt text. A `file:relative/path`
prompt resolves relative to the imported workflow file. Plain-text imports retain
their source text. An inline prompt without a `prompt_ref` creates a prompt record
for that workflow step. An existing `prompt_ref` selects the referenced prompt
text at execution, including when inline text is also present. Imported prose is
not automatically parsed into a guessed branch structure.

Applying a specialization preserves revised inline wording when a step retains
its source `prompt_ref`: the revised text receives a specialization-local prompt
record. Embedded declarations that reuse source prompt IDs also receive local
IDs, with specialized step references updated together. Source prompts retain
their wording, and authored control flow remains in the specialized definition.

Prompt records and steps can attach semantic rules through `rule_codes`. The
selected rules use `metaform:semantic-rule`, with `rule_code`, `purpose`,
`concise`, and `priming`; they are distinct from the executable `metaform:rule`
conditions above. Prepared assignments carry the exact selected rule content
and revisions, with full priming for each assignment. A running workflow frame
retains its rule snapshots. Explicit concise-only rule preparation is available
for a context that has already received the priming.

The initial rule content and the status of its explanations and examples are
documented in [rule seed sources](rulebook/seed-sources.md). Editing stored
wording does not establish a new semantic agreement.

Optional `output` stores an answer as graph data:

```json
{
  "id": "data.learning.{{ item.id }}",
  "schema": "metaform:learning",
  "layer": "my_learning_layer",
  "subject": "{{ item.id }}"
}
```

An optional `tools` array controls the tools offered to the step's sampled or
subprocess agent. Default workflow tools browse the graph and read the working
copy. Operational information, selected graph data, schema, and prompt remain
separate fields in an assignment. `context: "fresh"` requests a separate empty
workfolder for an external harness; the intake Latent Expert always uses one.
Actor gateways and sampled tool calls bind the exact issued request ID as well
as the run. Tool calls and `continuation.current` retain that assignment even
when sibling assignments are active; caller-supplied IDs cannot select a
sibling's context. A completed binding remains bound to that completed request.
The coordinator retrieves subsequent work outside the binding with the run ID
and begins the newly issued nonce in its agent folder. Sampling requests
`includeContext: none`; this describes the
request to the host, not a guarantee about an external model's prior context.

The built-in intake uses native scan, combined Type proof and handoff preparation,
promotion, and individual latent inference assignments. Proof inputs contain the Type
table, applicable schemas, `new_type_ids` for correction eligibility, and
`handoff_ids` for preparation, without project joins or tools. Its `elements` and
`renames` update Contextual Types and references; separate `archaeology_objects`
preserve Type meaning while excluding project OP relationships, including those
embedded in notes. An optional `archaeology_schemas` map supplies prepared schema
copies by schema ID, including referenced definitions: project OP prose is
decontextualized while validation constraints and Type meaning are preserved.
Original schema registrations remain unchanged. Missing prepared entries use
global-only schema definitions; project-only definitions are omitted when no
prepared copy is available. New global promotion and initial latent inference
packets use prepared records. Lookup uses prepared records for incomplete Types while
retaining existing global definitions in storage. `intake.batch` provides ready
assignments for a host dispatcher; `intake.drive` runs each assignment in a
separate process with concurrency defaulting to four. The engine API is
`Intake.batch(run_id, limit)`; `next(run_id, request_id)` selects an exact request.
MCP keeps each focal Type in a separate sampling message, including when the
modern protocol carries independently keyed requests in one result.

Global presence and completed inference are distinct. Latent inference lookup returns
`inference_complete` outside the authored Type object; only a successful focal
assignment records `archaeology-complete`. The flag does not certify completion
of dependencies. Newly produced Types and existing incomplete global Types
referenced by contributed joins need their own assignments. Scheduling uses
eligible Element references with available definitions, preserving explicit
owner and kind. Legacy latent inference observations without a focal completion
marker remain eligible.

The global KG's composites are independently inferred Type dependency graphs.
The current completion path copies their owned dependency structures into
project storage and creates structural similarity records with source references
and `01`, `10`, or `11` membership. Source payloads remain independently available
through scoped graph reads and the viewer, as specified in [SPEC](SPEC.md).
Completed inference is stable for reuse across projects. `get` and `search`
return Types without joins; `intake.inference` deliberately retrieves an existing
global composite as expert context. Initial assignments contain no sibling or
native project joins. Focal structure and join ownership are retained so
reuse follows the selected Type's dependency graph, rather than every incoming
association reachable by an undirected graph walk. No separate composite
database is being added. The `inference` result contains `id`,
`inference_complete`, `status`, and `graph`; incomplete inference returns no graph,
and a legacy completion marker without a snapshot reports `unresolved_structure`.
Retrieval remains global-only: exact owner and kind references cannot silently
resolve to a same-named global record. Non-global and missing references remain
reported while captured joins retain their contents. Global Element lookup uses
current records, then the completion snapshot, then captured archive dependencies.

Two projects can initially schedule the same incomplete Type. In service mode,
`inference.commit` atomically checks completion, writes eligible global knowledge
and its completion observation, retains the project's Latent copy, and records a
project-scoped request receipt. The first completed graph is retained and late
outputs reuse it. Contributions and promotion also preserve their existing checks
inside service transactions. Stable request IDs recover a committed result after
a lost response; they do not imply exactly-once live scheduling.

Intake durably records its local transition and cleanup target before removing an
assignment's workfolder. A repeated answer can finish retained cleanup after a
local save failure. Portable JSON uses the same inference operations with local
locks, while retaining its separate-file crash boundary. The bounded live handoff
comparison and its semantic evidence limits remain in [current work](current-work.md).

Run transitions are serialized across processes. Replayed answer IDs return the
same receipt; repeated `next` calls return the same pending assignment. Assignment
execution is locked and completed execution results are cached before submission.
A process crash between an external side effect and its durable result can still
require reconciliation; arbitrary external tools are not promised exactly-once
execution. Debug events and workfolder diffs provide the evidence for recovery.

Project selection belongs to the client context, not the workflow definition.
A CLI `--project` selector, an MCP session selection, and a workbench tab each
identify their App; issued assignments and in-flight requests keep their captured
project. Workflow definitions and step/rule references can resolve through project
and global knowledge. Imported workflow and step attachments become ordinary
`workflow_attachment` joins, so they also participate in selected export.
Prepared prompt assembly keeps owner-labelled source graphs and structural
similarity separate, honoring its requested depth and source.

An executable version 2 archive carries selected workflow definitions, prompts,
schemas, rule revisions, nested workflow dependencies, assignments, and required
assets with JSON knowledge and restored local SQLite state. It preserves the
logical project owner with a separate portable copy identity, and continues
through the same answer/next/export operations without service or Cypher access.
Returning that archive uses portable history import; it does not reconcile
changes into a registered service owner.

````

### **`metaform/docs/serena-reference.md`**

```markdown
# Serena: server and deployment reference

Reviewed the upstream implementation on 2026-09-07. These are reference notes
for discussion, not additional Metaform requirements.

Metaform's CLI remains sufficient to operate the system. The owner currently
envisions MCP as an optional way to browse the knowledge graph. The browsing
surface itself, and any role beyond it, remain to be discussed.

| Pattern observed in Serena | Relevance to Metaform |
| --- | --- |
| The installed `serena` executable provides both ordinary commands and `start-mcp-server`. | One installed tool can expose optional MCP without making it the only entry point. |
| Explicit client setup handlers register the installed command with supported clients. Initialisation reports detected clients and their setup commands. | Installation and MCP registration can be separate, understandable actions. |
| MCP supplies an initial connection prompt and tools derived from the active context. | A reference for discussing how graph-browsing tools could explain themselves; no additional workflow exposure is implied. |
| In stdio mode, the client starts the server and server teardown calls the agent's cleanup. For HTTP connections, disconnecting a client leaves the agent active. | Process ownership and the lifetime of a connection are distinct decisions. |
| The dashboard serves Flask in a daemon thread attached to an agent instance, binds locally by default, chooses an available port, and exposes a heartbeat. | A running web interface can report the state of the process it belongs to. |
| Agent state is published to dashboard listeners before the dashboard starts accepting requests. | The initial screen can describe actual state immediately. |
| Dashboard enablement and opening a browser are separate settings. | Running a server does not require launching a browser. Metaform already has the requested no-auto-open behaviour. |

The implementation is visible in Serena's
[CLI](https://github.com/oraios/serena/blob/main/src/serena/cli.py),
[client setup handlers](https://github.com/oraios/serena/blob/main/src/serena/config/client_setup.py),
[MCP factory and lifetime handler](https://github.com/oraios/serena/blob/main/src/serena/mcp.py),
[agent initialisation and cleanup](https://github.com/oraios/serena/blob/main/src/serena/agent.py),
and [dashboard](https://github.com/oraios/serena/blob/main/src/serena/dashboard.py).

## Project scope

Serena's normal MCP agent maintains one active project at a time. Its
[running guide](https://github.com/oraios/serena/blob/main/docs/02-usage/020_running.md)
explains that sharing a running HTTP instance among clients is appropriate
when they work on the same project.

There is also a separate
[ProjectServer](https://github.com/oraios/serena/blob/main/src/serena/project_server.py).
It serves read-only project queries, loads registered projects on demand,
caches them, and holds a lock while executing against its temporarily selected
project. This is distinct from the dashboard and from a general multi-project
editing service.

For Metaform, the useful design question is where project selection belongs
and which process owns ongoing work. Choosing that requires discussion; the
presence of a web server alone does not answer it.

## Deployment

Serena's [installation guide](https://github.com/oraios/serena/blob/main/docs/02-usage/010_installation.md)
uses a user-installed Python tool. Its running guide also documents source,
container, and HTTP options. The explicit installed-command registration is
the most directly relevant pattern to Metaform's user-local installation.
Metaform's offline, self-contained archive remains a separate existing
requirement when considering those options.

```

### **`metaform/docs/workbench-cleanup.md`**

```markdown
# Workbench cleanup

This document records the completed cleanup of misleading presentation and
additions outside the agreed design. [SPEC](SPEC.md) defines intended semantic
behavior; [current work](current-work.md) tracks remaining work and sequencing.
The interface and server questions below remain open.

## What changed

- Removed the Doors module, its commands, GUI, and special continuation/export
  handling. Doors was an example of previous work.
- Stopped importing example workflows when an App opens. The two examples are
  retained under `examples/workflows/` for explicit use.
- Removed automatic browser and preview-tab opening. Starting a viewer or
  preview returns links.
- The initial graph selects records with contextual or latent provenance and
  their joins. Referenced participants, including joins on joins, remain
  connected. A project with no intake records displays an empty state.
- Supplied prompts, workflow definitions, and recorded responses remain
  inspectable in the prompt/workflow views and **All stored records**. They no
  longer appear as inferred project knowledge merely because they share its
  database. Authored and other sources have a neutral graph colour.
- The viewer identifies the selected project by name and full path. Project
  storage and shared global storage are labelled separately.

Existing saved records are preserved. The graph selection is a view over their
recorded provenance, not a change to intake acceptance or semantic rules.

## Retained capabilities and their purpose

| Capability | Requirement it serves | Current implementation |
| --- | --- | --- |
| CLI and loadable modules | Harness-independent chassis with a scoped command surface | The command router and module handlers remain. The existing MCP router also dispatches these handlers; its broader exposure needs discussion. |
| Contextual intake and independent latent inference | Collect project knowledge and latent type knowledge, keeping the source of each contribution | Intake assignments and answers are persisted; latent inference authors its own global joins without receiving project joins. |
| Graph inspection and editable prompts | Refine semantic wording and inspect the resulting knowledge | Records, relationships, prompts, and saved responses are accessible. The default graph now distinguishes intake data from supporting records. |
| Workflow conversion and execution | Turn a written process into stored, executable steps | Builder assignments, JSON definitions, conditions, loops, and continuations exist. The GUI currently exposes these through forms. |
| Versions and portable exports | Preserve work and provenance, including outside Git repositories and in offline execution | Checkpoints, reconstruction, export, re-import, and static previews remain. |
| Image generation, packaging, and CI | Work with images and distribute the tooling and its data | The imagegen module, wheel/standalone build, and fork-compatible CI remain. |
| Activity and data browsing | Inspect WIP, history, statistics, and dumps | The existing activity view and CLI/MCP data commands remain. |

## Design work still to discuss

The role currently envisioned for MCP is browsing the knowledge graph. The
browsing interface and any scope beyond it remain to be discussed. The current
implementation exposes broader module commands through MCP; retaining that
code during cleanup does not settle the intended MCP surface.

The desired workflow view is a named workflow that opens into its steps and
the prompts used by those steps. The current JSON form does not yet provide
that presentation. The built-in intake procedure also needs to be made
understandable through that view.

Saving an answer and note currently records an observation; it does not run an
agreed workflow-level evaluation. The labels now describe what is saved.

The viewer currently opens for one selected project per server process.
Separate projects can run separate viewers and share global knowledge. This
cleanup does not choose a new project-switching or shared-server model.

The cleanup left semantic source documents and authored base prompts unchanged.
The maintained Aliases section is now bundled verbatim and supplied to intake.
An explicit `semantic_sources.aliases` configuration selects an alternative
authored source.

[Serena reference notes](serena-reference.md) record relevant server and MCP
deployment patterns for that discussion. No Serena implementation is adopted
by this cleanup.

```

### **`metaform/docs/verification.md`**

````markdown
# Verification

The [specification's acceptance scenarios](SPEC.md#acceptance-scenarios) define
the semantic demonstrations. Passing implementation tests establish semantic
correctness only where their expectations follow that contract. Tests of
supporting infrastructure and tests encoding superseded assumptions serve
different purposes; the latter need correction alongside the implementation.
The current correction work is tracked in [Current work](current-work.md).

Before the documentation consolidation, the focused command
`.venv/bin/python -m pytest tests/test_core.py tests/test_intake_pipeline.py tests/test_rulebook.py tests/test_execution.py -q`
passed 54 tests. The terminology correction subsequently passed all 9 tests in
`tests/test_rulebook.py`. The existing merged-join test requires copied source
purposes, so its passing result does not demonstrate the specified structural
similarity layer. Fixture answers also do not establish the semantic reasoning
outcomes in A-5 through A-8.

## System review repairs — 2026-09-09

All 21 reproduced [review findings](reviews/2026-09-09-end-to-end-system-review.md)
were repaired and independently rechecked. The complete source suite, run with
each environment's `python -m pytest -q`, passed **501 tests on Python 3.11.6**
and **501 tests on Python 3.13.5** (124.77 and 124.63 seconds respectively).

The regression coverage includes parallel workfolder inheritance and abort
lifecycle, exact assignment binding and delayed MCP answers, repeated foreach
visits, directory replacement, archive symlink boundaries and exclusions,
schema ownership/migration, prepared schema handoffs, reused join identities,
dependency scheduling, qualified similarity, image attribution/readiness, and
viewer crash recovery with live legacy-instance reuse. Abort checks use real
fixture harness processes; viewer checks exercise HTTP endpoints.

Similarity retains exact maximum structural correspondence. The review's
eleven-join divergent fixture now completes in about 0.002 seconds with the same
ten matches, compared with the review's 26–30 seconds. This is a specific
regression result, not a general scaling guarantee. Raw graph, CLI, viewer, and
intake paths use fresh owner-aware knowledge rather than a detached snapshot.

`python tools/build_distribution.py` rebuilt the wheel and standalone archive.
Fresh wheel installations on Python 3.11 and 3.13 both passed
`python tools/check_distribution.py`: installed and direct-wheel CLI/MCP,
offline GUI/export, installed Ladybug/Cypher analysis, and shared-service portable
continuation with the service stopped and original home unavailable.

Provider responses and semantic answers in these regressions are fixtures. The
checks establish the repaired mechanics; no live model or image-provider trial
was performed for this repair batch. The semantic demonstrations identified in
[Current work](current-work.md#build-corrections-remaining) remain outstanding.

## Shared knowledge and portable projects — 2026-09-08

The full source suite passed **396 tests on Python 3.11.6** and **396 tests on
Python 3.13.5**, using each environment's `python -m pytest -q`. Focused
regressions cover owner-qualified references, independent source records,
transactional inference recovery, service startup/reuse and shutdown, project
selection, indexed export closure, captured dependencies and schema refresh.
The closure fixture includes 10,000 unrelated global records and a concurrent
writer. Review findings were repaired and independently rechecked.

`python tools/build_distribution.py` built the wheel and standalone archive.
Fresh installed-wheel environments on Python 3.11 and 3.13 both passed
`python tools/check_distribution.py`: installed and direct-wheel CLI/MCP,
intake completion and reuse, an empty-Python GUI/export round trip, verified
service reuse, and Cypher over a revision-labelled Ladybug copy. The shared
project export excluded unrelated global and other-project relationships, then
continued a nested workflow with `-S`, empty `PATH`/`PYTHONPATH`, the service
stopped and original home unavailable. Re-exporting and reopening retained the
pending request. A regression also proves that two archives with the same file
origin reuse their own working copies without resetting continuation.

A Chromium check opened two service-backed project tabs, changed one tab's
selected project without changing the other, and refreshed a Ladybug analysis
copy. Project/mode display and analysis status were correct, with no JavaScript
errors. This was a desktop check, not a complete accessibility or mobile audit.

Ordinary central graph mutations still reconstruct one owner partition; these
results do not establish large-corpus mutation performance. Live model reasoning
was not part of this feature verification.

## Earlier build checks

The earlier build was checked locally on Linux with Python 3.13.5 and official MCP SDK 2.1.1.
The full suite passed 138 tests with
`uv run --frozen pytest -q --basetemp=.test-tmp/final-verified`.
The rule editor, Metaform filters, and semantic field saves were also exercised
in Chromium, including keyboard operation and the mobile Rules view.

A live Codex intake of the repository's small example module exposed and led
to fixes for strict output-schema rejection, access to the assigned tool bridge,
and blocked answers being treated as completed intake. The native scan and Type proof completed. The first focal latent inference answer
exposed schema-valid optional participant/projection storage failures; after
repair it was replayed successfully. The original answer also contains model
formatting errors, retained for review in [the live trial notes](mvp-review.md).
A second independent focal assignment used the clarified schema, saved four
OP joins with referenced participants and no schema annotations, and displayed
its links in the Latent view. This does not establish semantic quality or
completion of the full latent pass.

## Executed checks

The automated suite exercises the following through real filesystem, SQLite,
subprocess, Git, HTTP, and MCP transports. Agent outputs are labeled fixtures;
they are not presented as model-generated expertise.

- Lazy drop-in module discovery, raw argument preservation, command hiding,
  always-available imagegen, removal, and abort.
- Native intake, individual fresh latent inference assignments, independent global
  joins, matching source-attributed joins, and no native join export.
- Concurrent answer replay, durable pending requests, rule snapshots, conditional
  loops, nested calls, foreach, related recursive runs, and tool steps.
- Graph-backed transition edits changing execution, exact prose imports,
  filesystem prompt binding, graph specialization with retained source, and
  schema annotations that retain the original answer.
- Cycles and n-ary participant traversal, aliases as lookup candidates,
  source-specific join IDs, additional schema forms and arbitrary layers,
  export/import retention, packaged custom schemas, and integrity cleanup.
- A real harness process using the scoped actor bridge to read project evidence;
  its separate Latent Expert process querying global records without local joins.
- Abort terminating an active harness; fresh workfolder cleanup and trace capture.
- Non-Git development copies, text and binary diffs, conflict checks, application
  back to the original ordinary directory, and cleanup.
- Global export and a real Git merge/push against a local bare remote, excluding
  native joins and unrelated source-code commits; later bundle updates loading
  once without resetting global contributions on each new project.
- Flask endpoints plus managed viewer startup/shutdown while the router remains
  responsive; imagegen dry-run integration without generating an image.
- Rules and prompt attachments edited through the GUI retain exact wording and
  existing fields. Graph perspectives retain reified participant closure;
  semantic editors preserve structured EF, OP, and join-logic values.
- Optional pairwise join projections and participant roles preserved through
  SQLite, JSON, Ladybug, intake ownership, completion, reuse, and viewer output.
- Exact semantic equation source and revision supplied to conversion and
  specialization without overwriting authored prompt text.
- Official SDK clients using both the 2025-11-25 and 2026-07-28 paths, sampling
  tool calls that read project evidence, blind global assignments, and debug mode.
- A separately installed wheel: installed CLI, installed stdio MCP, direct-wheel
  CLI, and direct-wheel stdio MCP outside the source checkout.

Reproduce with:

```sh
uv sync --frozen
uv run --frozen pytest -q
uv run --frozen python -m build --wheel --no-isolation
uv venv /tmp/metaform-wheel-check
uv pip install --python /tmp/metaform-wheel-check/bin/python dist/*.whl
/tmp/metaform-wheel-check/bin/python tools/check_distribution.py
```

The GitHub workflow runs the tests and wheel checks on Python 3.11 and 3.13 and
uploads the wheel, including for data-only updates. Its configuration is supplied;
local verification alone does not establish a GitHub Actions result.

## Revised intake and completed composites

The suite includes focused intake/rulebook checks for combined Type proof and
separate prepared handoffs, correction/reference remapping with preserved purposes,
completion-based reuse, and one-focal-Type fresh assignments. Global presence
does not imply completed inference; a focal completion marker does not mark
incidentally produced Types or certify dependency completion. Legacy latent inference
observations without `archaeology-complete` remain eligible for inference.

Transport/MCP checks also passed. Concurrent actor gateways and sampled tool
calls bind tools and `continuation.current` to the exact issued request ID,
overriding caller-supplied request and run IDs. Supplied assignment payloads omit
sibling assignments, and sampling requests `includeContext: none`. End-to-end
stdio tests cover native → proof → two independent one-Type jobs in both MCP
protocol modes, including mixed completion and further tool exchanges.

These checks verify supplied payloads, state transitions, and request binding.
Host compliance, a model's latent independence, and semantic correctness require
separate evidence.

Composite ownership checks passed: completed focal structures and join ownership
preserve stable inference across projects, concurrent authored join IDs remain
distinct, and A depending on B does not cause B's reused dependency graph to
import A.
Deliberate `intake.inference` retrieval is distinct from supplying sibling or
native project joins in an initial assignment. No live model result establishes
the intended unbiased expert inference.

The distribution check passed installed CLI/MCP, direct-wheel execution, and
the extensionless archive in an empty/offline Python environment. It exercised
GUI/export and packaged proof → inference → completed reuse.

Two projects can initially schedule the same incomplete Type. The shared global
commit lock preserves the first completed graph, and late outputs reuse it;
this does not establish exactly-once live scheduling. A legacy completion marker
without its structure snapshot reports `unresolved_structure`; ownership cannot
be fabricated. Records without completion markers remain eligible for inference.

## Not established by these checks

- The automated suite does not run live model or image generation. Provider capability probing,
  authored prompt construction, routing, and fixture execution are implemented.
  The bounded live handoff comparison is recorded in [current work](current-work.md);
  it does not establish general model reliability or the remaining semantic outcomes.
- The maintained Aliases section is now bundled and supplied verbatim, with
  configured source overrides retained. Its delivery is tested; model application
  of the equations still requires a live inference trial.
- No claim is made that a host obeys `includeContext: none`, that a subprocess is
  an OS sandbox, or that fixture agents prove independent latent reasoning.
- No empirical claim is made about saved inference, reduced omissions, automatic
  porting quality, or the semantic correctness of a generated metaform.
- Arbitrary external side effects cannot be guaranteed exactly once across a
  crash between the side effect and durable result recording.
- Distributed multi-host workers, production deployment of the viewer, and live
  package-index publication are not implemented or implied by the local chassis.

````

### **`metaform/docs/next-version.md`**

```markdown
# Metaform 0.2

Metaform prepares reusable type knowledge so subsequent
instructions can address the project through its Elements and joins. This
version makes the prompts and workflow operations inspectable and portable.

This document describes the 0.2 implementation. [SPEC](SPEC.md) defines intended
semantic behavior; [current work](current-work.md) tracks outstanding alignment.

## Start

Install the release wheel normally with pip, or install from the repository.
The installed dependencies include Ladybug and the MCP SDK. Run `metaform install`
to create the launcher in `~/.local/bin`; installed Ladybug support can hydrate
analysis copies of the shared knowledge. An optional destination argument selects
another user bin directory.
No package or extension downloads occur inside this setup command.

`metaform browse` starts the local Flask workbench and prints its URL. CLI and
stdio MCP commands remain available. A direct release wheel also runs without
an extension: `python metaform`. The release build includes pure-Python portable
dependencies under `_portable`; normal package installation uses its declared
dependencies. Native dependencies are not represented as portable pure Python.
Without the MCP SDK, stdio uses a standard-library transport for the 2025-11-25
tools/resources protocol. It returns assignments for the host to execute and
answer. Installed use retains SDK sampling and newer protocol features.

New installed projects use the shared knowledge service automatically. Existing
project directories keep legacy storage until `metaform project connect` adopts
them. `metaform --project <path-or-registered-id>` selects the invocation;
`project current` and `project list` expose its context and registrations.
`project select --project <path-or-id>` changes a client's selection; assignments
retain their issued project and each workbench tab uses a project-specific URL.
Use `project relocate --path <new-path>` after a move or `project connect --new`
after a copy. `service status` checks actual liveness and `service stop` stops the
verified instance. Selection creates no global active-project setting.

The main workbench has five views:

- **Graph:** recorded intake knowledge by default, with an explicit all-records
  view; force layout, short names, provenance, layers, project/global storage,
  node and reified-join editing, and a Cypher console.
- **Prompts:** authored text, input values, exact prepared input, harness runs or
  nonce handoffs, actual answers, review notes, and recorded responses.
- **Workflows:** source, builder handoff, executable JSON, step handoffs, answers,
  and application of completed conversion results.
- **Versions:** parent-linked checkpoints, file diffs, extraction, export,
  re-import, and static web previews on separate local ports.
- **Activity:** run state, recorded execution events, counts, and graph dumps.

The browser assets are shipped in the package; no CDN is used. Previews serve
static artifacts. An application that needs a build step or its own application
server still needs that process. Preview URLs are independent roots so `/assets`
works for each version. Preview commands return links for you to open.

## Prompts and workflow conversion

`data/prompts.json` supplies editable initial prompts for conversion,
specialization, continuity, module building, and self-review. Contextual and
latent intake prompts are seeded from the existing authored semantic files.
The exact maintained Aliases section is bundled and supplied to intake; an
explicit `semantic_sources.aliases` configuration selects an alternative authored
source. [Semantic rule seeds](rulebook/README.md) supply concise wording and
priming material with recorded revisions.

A prompt node has `entity_schema: metaform:prompt` and data containing `id`,
`name`, `text`, and its text SHA-256 revision. Editing preserves observations.
Imported inline prompts become prompt nodes, and steps reference them through
`prompt_ref` and `step_prompt` joins. A workflow may also supply a `prompts`
array. A running frame retains the prompt text and revision it received.
Subsequent runs resolve the edited prompt.

Template substitution uses the existing Jinja syntax, such as `{{ name }}`.
Source text and the rendered instruction are recorded separately. Arbitrary
answers remain answers; schema checking supplies annotations. Portable mode
retains schemas and answers and reports when its optional validator is absent.

`workflow convert` creates a builder assignment from the exact source, selected
Metaform, and the execution grammar. A configured harness may execute it; an
external model can answer through the nonce/answer interface. `workflow apply`
imports the returned workflow and records its derivation. Converting a natural
language process is an inference operation, not a deterministic text parser.
Its semantic quality is intended to be tested and refined in the workbench.

Supported execution forms are `prompt`, `branch`, `call`, `foreach`, `parallel`,
and `tool`. Sequence uses step order unless a transition selects another step.
Transitions can return to earlier steps. A `parallel` step contains `branches`
with workflow references or inline workflow definitions. Each branch gets its
own run and nonce, while inheriting the parent's development workfolder. The
parent waits for the branch results. The external orchestrator may dispatch ready
branches concurrently to any harness. Aborting a branch preserves the shared
folder; aborting its owner stops descendant harnesses and retains the folder
until their execution and trace capture finish.

## Handoff and continuity

The orchestrator passes `python metaform begin <nonce>`, rather than retelling
instructions. Metaform writes `.agentid/nonce` in that folder. Its JSON contents
locate the project, module, run, and issued request. Commands invoked in that
folder or its children use that continuation. The nonce names stored work, not a
persistent agent identity.

Assignments are recorded under `~/.metaform/assignments/<nonce>.json`. Their
inputs, exact prompts, responses, and workflow state reside with the project.
The default issuance uses a random nine-digit nonce and checks the assignment
index for collisions. Retrieving the same pending step returns the same nonce.
New steps receive new handoffs. An existing folder binding retains its exact
issued assignment, including after completion; it cannot advance to another
assignment. The coordinator requests subsequent work outside that binding using
the run ID, then begins the new nonce in its agent folder. Run origins record the
launch folder and target; workfolder records identify execution and application
locations.

CLI subprocesses launched by a harness inherit the scoped bridge. Plain
`metaform` routes through that bridge after a directory change instead of opening
the main router. File bindings cover separate CLI processes in a bound folder.
These are command-surface controls, not operating-system isolation from files
accessible to the same account. A separately launched process outside both the
binding's directory tree and the scoped harness environment has no association
with that continuation.

## Storage

The service owns global and registered-project knowledge in
`<METAFORM_HOME>/service/knowledge.sqlite3`. Elements, joins, observations, and
schemas use owner-qualified keys; `global` and `project:<uuid>` records may have
the same semantic ID without overwriting each other. Native, archaeology, authored,
and completion observations remain independent from ownership. Endpoint and
participant owner metadata retain precise cross-owner references.

CLI and MCP startup probe authenticated loopback health with a fresh challenge,
matching service and instance identity and readiness. OS-backed locks coordinate
startup and service ownership; a PID file or listener alone does not establish
liveness. The service performs knowledge operations while project-local SQLite
and files retain execution, assignments, and workfolders.

`project connect` reads the configured legacy SQLite, JSON, or Ladybug backend,
preserves original files, verifies copied source records, and writes the service
marker after commit. Conflicting existing content is reported for resolution.
Home global imports are tracked by source home and digest. Legacy paths remain
`.metaform/metaform.kg`, `metaform.json`, or `metaform.lbdb`, with global knowledge
under the selected home's `inference/` directory. Inspection alone does not adopt
an existing project.

In service mode, `metaform graph backend --name ladybug` explicitly refreshes
project and global analysis copies. Ladybug represents Elements, joins, and
observations as native `Record` nodes, with ordered role-bearing `Participant`
relationships. `graph cypher` queries these copies and reports their source
revision and refresh time. Operational writes leave their captured revision
unchanged until another refresh; Cypher changes stay in the analysis copy.
Legacy mode retains backend selection. Portable mode uses JSON and needs no
Cypher for graph, prompt, workflow, inference, or export operations.

Selected service export traverses owner/reference indexes within one SQLite read
transaction, including reified joins, both endpoints, and participants. It does
not materialize all global records first. Ordinary central graph mutations still
reconstruct and replace one owner partition within a transaction; large mutation
workloads remain a practical scaling limit.

Operational state remains in `.metaform/state.sqlite3`; archives serialize its
tables and restore a local SQLite database. Portable project/global knowledge is
stored in `.metaform/metaform.json` and `.metaform/home/inference/metaform.json`.
The portable dispatcher captures both JSON files under their locks and bypasses
service discovery and unrelated packaged inference.

Scoped graph reads and exports preserve each source's Element and join contents.
Structural similarity compares node identities and join structure, including
participant roles and references to joins. Its `01`, `10`, and `11` records carry
structure and provenance references. The viewer exposes Contextual, Latent, and
read-only similarity views. [Current work](current-work.md) tracks remaining
alignment with the [SPEC](SPEC.md).

## Versions and exports

History lives in `.metaform/history/`. `origin/` stores the baseline bytes. At a
Git repository root with Git available, the baseline comes from the starting
commit; an export checkpoint captures working-tree changes. For an ordinary
folder, the initial contents form the baseline. The manifest records which case
applies and the commit when present.

Each checkpoint references a parent and contains additions, modifications, and
deletions. Added and modified files are complete files under
`versions/<version>/files/`; they are compressed by the outer ZIP. Each version
also stores its project Metaform and work provenance. Export selects all current
project records and related global inference through eligible project/global
joins, workflow attachments, and explicit execution dependencies. Another
project's private joins do not expand that closure. Source observations and exact
historical snapshots travel with separately retained historical dependencies.
Schemas and module declarations follow their selecting records. Unrelated global
additions leave the selected knowledge digest unchanged. Unchanged file contents
are inherited from the parent chain.

The origin SHA-256 is derived from the canonical path/content-hash/mode manifest.
The initial suffix is `0000`. `mform_sha_id` is the full hash plus `_` and the
four-digit hexadecimal suffix. `mform_id` is the first 48 hash bits plus that
16-bit suffix, represented as 16 hexadecimal characters to preserve all bits
through JSON and JavaScript.

`package export` captures pending file or graph/run changes and produces one
executable `metaform-export/2` archive. The archive contains ordinary `origin/`
and `versions/` paths, selected graph JSON, owner-qualified schema and dependency
metadata, project-bound continuation assignments, active workfolders, retained
outputs, selected module folders and declared assets, and its portable runtime.
Shared modules enter closure when referenced or selected by configuration,
including retained portable module selections. A native Git
workfolder is exported with a file-based baseline so it can continue without Git.
No model, model credentials, or image-generation service is embedded.

On execution, the archive materializes a working copy in its sibling
`<mform_sha_id>` folder, or a suffixed sibling when history diverges. Subsequent
invocations reuse the copy whose saved bundle hash matches that archive. Edits are
made in the working copy; `package export` creates the returned archive. The ZIP
is not rewritten after every command. The portable copy preserves the logical
project UUID in `project_id`/`origin_project_id` and has its own `copy_id`; moving
that copy does not change the meaning of its explicit owner references. It can
resume pending work, edit source records, and export the continued archive with
the shared service and original home unavailable.

On re-import, pending local file or graph/run changes are captured first. If
incoming history includes every local version with matching content and origin,
the corresponding folder is replaced. Otherwise the incoming suffix increments
and both continuations remain. A staged replacement keeps the prior directory
until the new copy is ready. Both `metaform-export/1` and `/2` are accepted;
version 1 retains its supplied historical extent and is re-exported through the
selected closure. Archive import creates or updates a portable working copy,
including beside a connected project; shared-service reconciliation is not
implemented. Binary SHA-256 checks detect damaged stored files
when reconstructing a version. Path checks protect extraction boundaries.

`history_exclude` accepts additional path patterns. Chassis metadata, assignment
markers, and Git internals are separated from the project-file history to avoid
recursive capture. Selected custom module folders and active outputs are exported
in their own sections.

## Modules, self-targeting, and community

Modules live under `~/.metaform/modules/<module>/` or
`<project>/.metaform/modules/<module>/`. A `module.json` declares commands and
handlers. Handler files can use relative imports into child packages. Importing
one module does not import the other modules. `disable_argparse`, `raw_handler`,
`always_available`, and conditional command visibility remain available.

Prompt and workflow APIs are available to module handlers; a module may ship
its prompt/workflow/schema files alongside its Python code. See
`examples/module` for a concrete interface.

Target Metaform's checkout with intake to construct its own Metaform. The
editable module-builder and self-review prompts are available for that work.
`sync export` writes global inference as reviewable JSON in the source checkout;
`sync merge` merges and pushes that data through the configured remote. Data-only
updates trigger CI repackaging. Contributions can contain new modules, prompts,
workflows, schemas, or global type knowledge. Uploading is a user-invoked action.

## Validation scope

Shared-service and portable integration tests pass on Python 3.11 and 3.13.
Checks cover authenticated startup/reuse and races, owner isolation, request
receipts, inference rollback/recovery, indexed closure under concurrent writes,
source-preserving JSON copies, and revision-labelled Ladybug analysis copies.
Final full-suite and rebuilt-wheel evidence is recorded in [verification](verification.md).

Existing checks exercise real Ladybug storage and Cypher, reified joins on joins, prompt
revision snapshots, parallel handoffs, folder bindings, workflow conversion
application, binary file reconstruction, inclusive/divergent
imports, active workfolder continuation without Git, static previews, and a
portable archive under Python `-S`. Existing tests cover installed CLI/MCP
routing, blind latent inference, schemas, harness processes, and data synchronization.
The release check also creates an empty Python environment and exercises the
extensionless wheel's CLI/MCP, GUI launch, project export, and returned export's
GUI without installed dependencies or Git.

This feature verification did not run live model or image generation. Prepared
prompts and data paths are exercised; semantic quality needs real model testing.
A Chromium check exercised two project tabs, independent project selection and
Ladybug analysis-copy refresh, with no JavaScript errors.

## Research references

- [Ladybug Python API](https://docs.ladybugdb.com/client-apis/python/)
- [Ladybug concurrency](https://docs.ladybugdb.com/concurrency/)
- [Ladybug extensions](https://docs.ladybugdb.com/extensions/)
- [Ladybug MCP bridge](https://github.com/LadybugDB/mcp-server-ladybug)
- [MCP lifecycle and version negotiation](https://modelcontextprotocol.io/specification/2025-11-25/basic/lifecycle)
- [MCP stdio transport](https://modelcontextprotocol.io/specification/2025-11-25/basic/transports)
- [MCP tools and structured results](https://modelcontextprotocol.io/specification/2025-11-25/server/tools)

The Metaform router remains its own CLI/MCP implementation. The upstream bridge
was inspected, but its startup extension installs and text-table query responses
were not imported into the portable design.

```

### **`metaform/docs/architecture.md`**

```markdown
# Architecture and research

Research checked on 2026-09-05. These are implementation choices, not claims of
an empirically best orchestration system.

[SPEC](SPEC.md) defines intended semantic behavior. This document describes the
current chassis; [current work](current-work.md) tracks outstanding alignment.

## Shared chassis

JSON manifests describe commands independently of Python imports. The CLI builds
argparse entries from their input schemas. MCP exposes the same registry.
Takeover and command disabling operate at dispatch; raw input is delivered to
the owning module without main-parser interpretation. An always-available
command survives takeover. `abort` is intrinsic to the chassis.

Runtime state remains in project-local SQLite at `.metaform/state.sqlite3`.
Per-run file locks serialize transitions across CLI and server processes; local
transactions retain answers, run stacks, events, and workfolder identities.
Knowledge operations have a separate interface: `BoundGraph` adapts existing
per-owner methods, while `RemoteKnowledge` and `LocalKnowledge` dispatch the same
graph, schema, assembly, and inference operations.

New installed projects register with one user-local service per resolved
`METAFORM_HOME`. Its central database is `service/knowledge.sqlite3`. Legacy
projects continue using their configured SQLite, JSON, or Ladybug files until
`project connect` explicitly adopts them. Adoption preserves original files,
imports source records without generating replacement observations, reports
competing content, and publishes the service marker after transaction commit and
source verification. Global imports are tracked by source home and digest.
Portable mode selects local JSON before service discovery or ambient seeding.

The service uses authenticated loopback HTTP. Startup requires a fresh challenge
response matching the service, instance, and protocol identities and readiness;
endpoint files, PID values, and open ports alone are insufficient. OS-backed
startup and lifetime locks serialize discovery and ownership. `service status`
probes actual liveness; `service stop` addresses the verified instance. The service
owns knowledge and performs no model work.

A registered project UUID is separate from its canonical path and history ID.
`--project` accepts a path or registered ID; assignment binding takes precedence
over invocation selection. `project select` replaces an MCP session's selected
App for subsequent calls, while in-flight requests keep their captured App.
Workbench URLs identify projects so tabs remain independent. Moves use
`project relocate`; explicit `project connect --new` creates a new owner, copies
the registered source partition, and translates structured self-owner references.
Execution state stays with each project directory.

## MCP workflow orchestration

The implementation uses the official Python SDK 2.1 line. It supports the older
session protocol and the 2026-07-28 protocol, whose requests can return
`InputRequiredResult` and resume with input responses. This avoids trying to
make the server initiate unsupported modern sampling requests.
[Python SDK](https://github.com/modelcontextprotocol/python-sdk),
[sampling specification](https://modelcontextprotocol.io/specification/2026-07-28/client/sampling).

The modern tools specification disallows changing a tool catalog as a side effect
of another request. Consequently the modern server exposes a stable `metaform`
router, `abort`, and always-available tools. Available module commands are data
returned by the router. Older clients receive individual tools and list-change
notifications. This preserves the requested mode semantics across both protocols.
[Modern tools](https://modelcontextprotocol.io/specification/2026-07-28/server/tools),
[2025-11-25 tools](https://modelcontextprotocol.io/specification/2025-11-25/server/tools).

Sampling can itself call scoped tools, receive their results, and continue before
answering an assignment. A server-held continuation retains the same request ID
and explicit message history. The local intake agent can read repository files;
the Latent Expert receives global search/get/put tools without repository reads.
The host-answer loop remains available when client sampling is unavailable.
Durability is application-owned, rather than tied to experimental task APIs;
tasks changed to an extension in the modern protocol.
[Protocol changes](https://modelcontextprotocol.io/specification/2026-07-28/changelog).

Concurrent intake dispatch keeps each focal Type in a separate sampling message.
The modern protocol returns independently keyed requests in one
`InputRequiredResult`; completed answers remain retained while unfinished jobs
continue their own tool exchanges. The older protocol uses concurrent sampling
calls. Actor gateways and MCP tool calls bind the exact issued request ID, and
`continuation.current` resolves that assignment rather than a sibling request.

## Reified graph and executable logic

Elements retain the ET fields: `entity_desc`, `entity_schema`, `entity_json_obj`,
keyed in the shared store by `(owner, id)`. Owners are `global` or
`project:<uuid>`; semantic source and physical location are separate axes. Joins
have identities, endpoints, scope, and an arbitrary list of
role-bearing participants. This implements n-ary relations whose purposes,
conditions, and attribution can be addressed directly. Relations can participate
in further relations. It does not reduce every association to an unannotated
pair of nodes. W3C's n-ary pattern is useful here; ordinary RDF statement
reification and an n-ary domain relation are distinct concepts.
[W3C n-ary relations](https://www.w3.org/TR/swbp-n-aryRelations/).

Workflow membership and transitions are graph relations. A condition may refer
to a rule Element and that Element's serialized expression. The executable
snapshot is reconstructed from this graph, so graph logic is operational rather
than a decorative copy of code. The evaluator is deliberately small and explicit;
new operators can be implemented as code while workflow instances remain data.
[JsonLogic](https://jsonlogic.com/),
[SQLite JSON support](https://sqlite.org/json1.html).

References retain their authored strings. Optional `participants[].owner` and
endpoint `reference_owners` make cross-owner references precise. Unqualified
project references resolve locally, then globally; global references resolve in
global knowledge. Equal IDs in different owners remain independently addressable.
Element-address incidence can discover both selected-project and global joins;
references to joins compare qualified join identities. Endpoints remain relevant
even when a join also supplies participants.

Cycle-safe traversal follows endpoints, participants, and reified joins. Runtime
assembly retains owner partitions and honors caller depth, category, and source.
`knowledge.snapshot` follows the complete selected-project closure in one SQLite
read transaction, using owner/reference indexes rather than exporting the entire
global graph first. Other projects' private joins do not expand it; explicit
references outside the selected owners and missing bodies remain reported.
Current source relationships expand closure, while exact historical completion
bodies and their dependencies remain evidence. Similarity does not expand the
source traversal. Indexed selection has dedicated scale and concurrent-writer
checks. Ordinary central graph mutations currently reconstruct and replace one
owner partition inside their transaction; that remains a practical scale limit.

Source observations retain object contributions. Scoped retrieval, search,
assembly, and export use the selected source's latest record. Native and
Latent Expert joins have separate source identities even when their authored IDs
coincide. Structural similarity compares node identities, join types, participant
roles, and references, including references to joins. Its `01`, `10`, and `11`
records contain structure and source references; semantic contents stay in the
Contextual and Latent graphs. `graph.similarity` computes this view and the
completion path persists it under `merged`. The viewer exposes each source and
the read-only similarity view separately. The implementation does not claim
full PROV-O conformance.
[W3C PROV-O](https://www.w3.org/TR/prov-o/).

## Semantics and data movement

The graph does not impose an external taxonomy or normalize namespace semantics.
Element names and roles are authored through inference. Literal source statements
remain available separately from runtime controls. The [SPEC](SPEC.md) defines
the semantic contract, including preservation of established terms.
The active rulebook is seeded as `metaform:semantic-rule` records. Prompt and
step `rule_codes` select exact rule content and revisions for assignments;
workflow frames retain their snapshots. These records are distinct from
executable `metaform:rule` condition expressions. The maintained Aliases section
is bundled verbatim, with an explicit configured source override supported.
See [rule seed provenance](rulebook/seed-sources.md) for the distinction between
established source wording and assistant-authored priming explanations.

Intake inserts a combined Type proof and handoff preparation after the native
scan and before promotion. It receives Type records and their applicable schemas,
with separate lists identifying globally new Types eligible for correction and
Types awaiting inference. It receives no project joins or tools. Corrections
update local Types and remap references while preserving project content and
relationship purposes. Separate `archaeology_objects` retain Type meaning while
removing project OP relationships embedded in the records. New global promotion
and focal assignments use these prepared records. Latent inference lookup also uses
them for incomplete Types without overwriting existing global definitions.
Merely finding a global object is insufficient to establish completed inference.
[Verification](verification.md) records the implementation checks and their
semantic limits.

Each Latent Expert receives one focal Type in its own fresh subagent context.
Independent assignments may run concurrently, but a batch or cluster of sibling
Types must not be supplied as one inference context. Completion is attributed
only to the focal Type through `archaeology-complete`; additional produced Types
also require coverage. Previously completed inferred structure is reused.
Latent inference lookup reports `inference_complete` separately from the authored
object. That flag describes only its own focal assignment, not the dependency
closure. Legacy `archaeology` observations without `archaeology-complete` remain
eligible for inference. A completed dependency record is preserved when another
assignment contributes it incidentally.

`Intake.batch(run_id, limit)` exposes independent ready assignments through
`intake.batch`. `intake.drive` dispatches separate harness processes, with
concurrency defaulting to four. `next(run_id, request_id)` retrieves the exact
assignment; batch delivery belongs to the dispatcher, not the focal agent's
inference context.

Independently authored latent inference joins are stored globally; the current project
completion path copies completed focal dependency structures into project
storage and creates the structural similarity records described above. The independent graph
and similarity requirements are defined in [SPEC](SPEC.md). Schema forms
and layer names are open-ended, independent dimensions. The intended unbiased
expert structure is a semantic aim, not empirical proof of bias-free inference.
The global knowledge graph contains composites: Type dependency graphs inferred
independently of individual projects. Completed inference is stable reusable
expert knowledge; another project's use cannot redefine it. Type admission and
completed inference are distinct. No separate composite database is being added.

The implementation retains the focal authored structure in completion
provenance and records each join's `inference_type` and `authored_id`, with
namespaced stored IDs for concurrent contributions. Reuse follows this ownership
rather than importing every record reachable by undirected traversal. For
example, A depending on B does not make A part of B's dependency graph.
`intake.inference` deliberately retrieves the selected completed global
structure; `get` and `search` remain Type-only with completion status. No sibling
or project joins enter the initial assignment. Deliberate retrieval of global
composites supplies reusable expert context.

The `inference` result contains `id`, `inference_complete`, `status`, and `graph`.
Its completed graph holds focal-authored joins and explicitly named or referenced
Type members resolved from current global records, then captured completion
records, then retained archive dependencies. Incomplete results have no graph;
legacy completion markers without a stored snapshot report
`unresolved_structure`. The snapshot is on the completion observation, preserving
the authored Element record. `inference.commit` performs the completed check,
global contribution and completion observation, project Latent write, and durable
receipt in one central SQLite transaction. `inference.contribute` and promotion
also keep their existing checks and writes within that boundary. Receipts are
keyed by project context and request ID; reusing an ID with different arguments
reports a conflict. Retrying a committed request returns its original result,
allowing intake to recover its local run transition after a lost response.

Two projects may initially schedule the same incomplete Type; the first completed
graph is retained and late outputs reuse it in their project. This does not imply
exactly-once live scheduling. Portable inference uses the same logical dispatcher
with the existing local intake lock; its separate JSON files retain their local
crash boundary. Legacy completion markers without snapshots cannot supply
fabricated ownership; records without completion markers remain eligible.

Project archives use `metaform-export/2`. They carry the selected closure, source
observations, owner-qualified schemas, historical dependency material, selected
executable assets, and project-bound execution/assignment state. The exported
logical project UUID is preserved; a separate `copy_id` identifies the portable
working copy. JSON graph records and restored local SQLite execution state support
continued prompt/workflow operations and another export without the service,
Cypher, or unrelated packaged global inference. Imports accept versions 1 and 2
and retain inclusive-history replacement and divergent-history sibling behavior.
They create portable copies, not shared-service reconciliation.

Installed Ladybug stores are optional analysis copies. `graph backend --name
ladybug` refreshes the selected project's and global copies; `graph cypher`
queries them and reports their source revision and refresh time. Service writes
do not silently refresh those copies, and Cypher edits do not mutate operational
knowledge. The shared service and portable runtime remain usable without Cypher.

The separate `sync export` operation produces one JSON file per global object
or join, plus observations and an
index containing a content hash. Wheels load an updated indexed bundle once per
shared installation; a later project using the same unchanged bundle does not
reset local global contributions. Changed packaged versions update canonical
records while retaining prior observations. Native joins are never part of this
export path. Sync contributes only data from an isolated worktree based on shared
history; it does not push unrelated development commits. Git merges surface
conflicting edits for resolution.

## Distribution, interface, and remaining evidence

Git diff works on chassis-created repositories even when the original project
is an ordinary directory. Completed development copies remain available for
review and explicit application. Fresh latent inference copies are cleaned after
their assignment. File locks coordinate same-host execution and builds.
[Filelock](https://py-filelock.readthedocs.io/).

Flask provides the local inspection UI in a separate process. A production
deployment can use its WSGI application factory with a suitable WSGI server.
[Flask deployment](https://flask.palletsprojects.com/en/stable/deploying/).

CI tests, builds, and uploads wheels, including graph-data-only commits. It has
no automatic PyPI publishing or PR-merging step.
[GitHub Python workflows](https://docs.github.com/actions/guides/building-and-testing-python),
[PyPA packaging guidance](https://packaging.python.org/guides/publishing-package-distribution-releases-using-github-actions-ci-cd-workflows/).

Working control flow is not proof of semantic correctness. Current tests exercise
fixture agents through real processes and MCP clients. Comparative measurements
of token use, inference quality, omission rate, refactoring success, and model
context isolation remain future evaluations. The Aliases source is bundled;
live model/image-provider authentication remains necessary for provider runs.

```

### **`metaform/docs/discussion-handoff.md`**

```markdown
# Metaform discussion handoff

This note collects the owner's recent clarifications for an external agent helping
organize what needs to be conveyed back into Metaform's development. It records
understanding that had not yet been fully integrated into the specification or
runtime at the pushed checkpoint `7eab035`. It is a conversation handoff, not a
second specification or an instruction to implement the exploratory design.

Read the [specification](SPEC.md) for established definitions and the
[current work](current-work.md) for implementation status. Where the recent
clarifications below expose a mismatch, that mismatch needs reconciliation;
existing code and passing tests do not settle semantic intent.

## The purpose of the form

The graph expresses the system at the **Type level** because the Type level
speaks in the language of expertise. It represents functional Elements,
their relationships, and their purposes. That understanding supports reasoning
about the project and possible realizations beyond its present implementation.

The owner explains the name as **meta**, as in meta prompting, and **form**, as in
the form of the project. Prompts can address the represented form and its
information, allowing compact instructions to become precise project-specific
imperatives. The intended benefits are to eliminate hallucination, save
inference for higher-level reasoning, and make work specific enough that it
is not skipped. These are product aims, not demonstrated guarantees.

## Native and Latent Experts

The agreed names are **Native Expert** and **Latent Expert**. **Defining
Element** is the correct established term; the earlier substitution of
Intrinsic Element was a mistake. The existing definitions of Defining,
Notable, Parametric, and Stylistic Elements retain their operative meaning.

The Native Expert works within the frame of the project to identify its
Defining Element and the functional Elements it uses. These include Elements
realized within the project and those supplied by a framework it uses.

The owner's clarification extends beyond the wording of Element descriptions:

> “it speaks the structure of the project itself, its speaks about the
> functional elements on a more abstracted level”

The representation speaks to those Elements' own purposes, including locally
understood purposes. Files, source symbols, written functions, and descriptions
of the code itself do not belong at this level. The project provides evidence
for understanding its functional structure.

This distinction matters: project-local meaning can be expressed through
functional Types and their relationships. The owner corrected an earlier blanket
claim that nothing could speak to the project, then clarified the abstract
level at which it must do so. The precise representation of local Operative
Purposes still needs reconciliation with the current intake and handoff
implementation; the functional level itself has been clarified.

The Latent Expert develops independent Type-level understanding without the
Native project's OP relationships supplying its answer. Native and Latent
views support examination of bias and blind spots. The owner chose these expert
names partly to avoid the connotation of naming one expert “biased.”

## How authored prompts use Metaform

Project-resolved prompts depend on how they were authored before processing.
They refer to Metaform's structure and the information it contains to target
the work. Their authored operation determines how that information makes the
resulting imperatives specific to the project.

This clarification corrected the assistant's introduction of file and code
references into the explanation of Native intake. Project resolution does
not establish a requirement to place those references in the Native form.

The owner described these uses:

- Consider the Metaform object by object, including prompts concerning purpose.
- Produce checklists for points in the project, supporting inspection and remedy.
- Use Native and Latent views to expose and evaluate bias and blind spots.
- Support refactoring, deeper organization and analysis, and solving code issues.
- Evaluate a plan before implementation by comparing the shape it describes
  with the understanding available through Latent inference.

The opportunity is to collect reusable prompts applicable to both the resolved
project form and the independently inferred form. The owner described the potential
as a “universal improvement engine.” These examples communicate the intended
range of operations; they are not a closed catalog.

The assistant proposed distinguishing a prompt's instruction kind from how
it addresses the form: its subjects, relationships, perspectives, and required
information. That is a design suggestion awaiting discussion, not an agreed
schema. The last question about a formal prompt-resolution contract was not
answered before the repository checkpoint was requested.

## Prompt organization and workflow imports

The owner wants a solid GUI organization for prompts, including **intake prompts,
rule prompts, imperative prompts, and workflows**, with schemas developed
for them. The system should support importing workflows and working with
prompts processed into project-specific instructions.

The kinds, schema fields, relationships between source and processed prompts,
and GUI arrangement have not been finalized. The owner explicitly presented this
as a goal to understand before implementation. The newly added `prompts/`
collection was included in the repository push; its presence does not mean
these organization and processing capabilities have been implemented.

## Global knowledge, local data, and portability

The owner's stated direction is:

- **Global** is a system-level database.
- **Local** carries a project's own data. Its physical storage may also be
  system-level; project ownership and storage location are separate concerns.
- A project's Metaform can be exported portably, used on any harness, and
  reimported into the local project.
- Metaform maintains its own diffs independently of the project, with those
  diffs tied to project commits.

During intake, the Native Expert should use objects already available globally
when their Namespace addresses match. Missing objects are defined and proofed
and become part of the global database. Matching addresses should refer to
the corresponding established Type objects; local work uses those Types and
extends for what is missing.

An unanswered detail is what **extending** means in each case: adding missing
related or descendant Elements, enriching an existing global Type definition,
or both. No mutation, conflict-resolution, storage, or export schema has been
agreed from this discussion. The existing independently observable Native and
Latent graphs also need to be reconciled with this more explicit account of
shared global Type objects.

## Improving the workflows themselves

The owner sees a further opportunity if Metaform represents its own form and
understands its own rules: the provenance being collected could help identify
new ideas for improving the workflows. This connects the project's semantic
representation, reusable prompting, and observed work to improvement of the
system itself. The mechanism for proposing, evaluating, and adopting those
improvements remains exploratory.

## Implementation boundary at the checkpoint

The pushed checkpoint includes the Native/Latent Expert rename, Type-level
Element-description guidance, independently readable graph perspectives,
structural similarity, workflow specialization fixes, prompt migrations, and
The owner's prompt collection. The full suite passed **250 tests**, and the wheel
built successfully before the push.

The current Type proof step returns Contextual corrections separately from
prepared Latent inputs. It preserves Contextual records while preparing inputs
without Native OP relationships. A comparison favored the combined proof and
preparation call for preservation of semantic fields in the tested cases.
That comparison preceded the later clarifications above and does not establish
that the current separation expresses the final intended model. No subsequent
handoff redesign was implemented during the discussion.

The broader prompt organization, storage, portability, and workflow-improvement
discussion has not been implemented. Some underlying capabilities already
exist; the discussion does not certify them against these clarified goals.

## Working with this understanding

Semantic precision is central to the work. Preserve established terms,
definitions, and formulas; keep the owner's statements distinguishable from
assistant interpretations and suggestions. Clarify consequential ambiguities
in conversation before turning them into implementation decisions.

The owner wants the build corrected and the documentation surface kept tight.
This handoff was explicitly requested to help the external agent collect
critical understanding. Finalized decisions should be integrated into the
existing authoritative docs, avoiding a chain of alternate specifications
and deviation reports.

The owner's collaboration instructions are separate from behavior authored into
Metaform prompts. A correction to the assistant is not permission to invent
prompt requirements, gates, blacklists, whitelists, or an inverted version of
the behavior the owner asked to remove.

```

### **`metaform/docs/semantics/understanding-and-work.md`**

```markdown
# Developed understanding, receiving relationships, and work

Quoted statements from the owner's 2026-09-08 design discussion are preserved with
their informal spelling; expert role names follow the owner's subsequent terminology
correction. The Element definitions below are
quoted from the repository glossary. Other text provides source attribution and
links.

Related sources: [Metaform specification](../SPEC.md),
[Functional typology](functional_typology.md), [Aliases](inference_metaform_rules.md#aliases),
and [Rulebook](../rulebook/README.md). [Implementation status](../current-work.md).

## Functional lineage and Namespace seeding

> this is a metaform ontological typology, where domain and class dont apply

> we are at our core a functional typology with encounter encoded in it..  When placing things in the metaform we need structure by using function and then extend it by linking the encounter.

> code is program code settled..  its the function

> cxx26 is the encounter of code.cpp

> Metaforms deal with linking to core functions, encounters are realized by linking them into the graph as a transitive that effects all nodes back to the core function (its trunk) and forward through its branches.

> I mean thats why I made the rule that way so that the name space could be comprehensive and hold all handlers under that node

> this has a lot of reasons one it try to enforce determinism

> I think we need to provide guidence here, the way we give guidence is by seeding the name space, media.photo.personal (personal photo media)   I almost want to drop the name field and make it a hard rule that all namespace scopes reverse to describe your item with a few words as possible

### Game engines, placement, and identity at an address

> no it gets rid of code.game..  and moves it  to be a game engine,everything goes into the engine right?   code.engine.game.physics.box2d, and you know what as long as its sematic its correct..  maybe I am using box2d as a simulation for a circle packing proof and they want to link its at code.engine.box2d,   box2d engine program code " a framework that simulates 2D rigid body physics by calculating forces, collisions, and movement over discrete steps of time."

> it doesnt matter  by linking it someplace else it is creating a different unique element..  box2d game engine program code is  a 2D rigid body simulation library written in C++ that simulates the laws of physics for video games.

The owner further clarified alias scope:

> no you cant you can only do the alias for that artifact type

> you inference that it should ban 11 bans 7-11 windows 11 and everything 11 is blatenly wrong period, no deliberation needed

## Photographs: the contents and their defining participation

> description of personal photo for the purpose of the namespace means having a person or persons as the subject

> you can say portait photo media, vacation photo media, product photo media,   product photo media : a photo with an inanimate object as its subject for the purpose of resale.     media.photo.product.new/used

> no one cares the encoding its the contents

Definitions from the [glossary](../../src/metaform/data/semantics/glossary.md):

> **DE: Defining Element:** The named element whose removal, replacement, or loss of role would materially change the artifact’s identity, operative purpose, or defining behavior.

> **NE: Notable Element:** An carries the identity of an internal subsystem, but it does not carry the identity of the root Artifact Type. It is named because Elements address it or because it is a dependency of other Elements.

> **PE: Parametric Element:** A quality or quantity that can be tuned by changing a value. It does not have a specific named identity in individual Artifacts of that Type. It lives in a simple array and uses a one-word or `snake_case` name.

> **SE: Stylistic Element:** An Element that imbues a distinctive nature that groups others in the class or Type that share this quality. SE does more than describe function; it tangibly changes the encounter of Elements it is joined with, and that effect permeates all the way through to the Operative Purpose of the upstream Receiving Entity beyond the Element it is directly joined with. Genre is like this.

## EF, Receiving Entity, and the perspective expressed by OP

> then the seller and a buyer both have an operative purpose for the photo

> for the purposes of proof to conduct a buy sell transaction

> ones operative purpose is one perspective...   this is why we use the semantics we do like defining element, who or what does its encounter function serve what is their operative purpose

> the op isnt a separate thing its record with a type in the receiving entity its like a dependencies dictionary that names the edge you have all of the edges split up conveying sematics that arent true.. like making the claim that every node in the graph is ai receiving entity for its children and thats not true either

> In my mental model they do but I dont know if thats correct  In my head I am picturing a node in the graph as its full namespace name,  like code.game.platformer.2d having a dependency on  media.spritesheet and there is a one way join pointing from media.sprites --> code.game.platformer.2d and the edge being labeled something like "visual representation of objects"

> well then media.image.sheet.sprite

## Intake records and subsequent use

> so it was a joins dictionary and the dotted name should be its efid, and there should be a type enum with dependency or property , and operative_purpose was a test description

> but this record was an intake record

> not representative of how it was used

> You are conflating join types with element types anyway

> Sorry in the join dictionary

> Thats the intake schema

## Independent Type inference and contextual examination

> The Latent Expert only receives types not joins..   they cant be biased by the use in the project itself

> I honestly think that the global process should be spread out across subagents each getting a single object

> The reason I think that might be the move is because seeing things in a cluster is its own kind of bias

> I think we tell the archeologist it should check the types and composite types to identify inference that is reusable and align it from there

The owner's existing [photo examples](../../media.photo.product.used/) include one
[original](../../media.photo.product.used/origin.png), three
[good results](../../media.photo.product.used/good_results/), and two
[bad results](../../media.photo.product.used/bad_results/).
[Supplied explanation of the results](../../media.photo.product.used/bad_results/explanation.md).

> lightbox view was a clever way to reinforce its used nature

> those images were reasoned by examining the item

## Developed understanding enables the prompt writer's reasoning

> the language of the Latent Expert and the metaform typological language is not the language of prompting for workflows...    its a semantic language meant to drive proper intake and to build the structure prompts can rely on, workflows involvingh the data collected and the semantics we use to collect that data are not one in the same

> And that combined reasoning when you reason on the photo should give you all of its directly connected elements those descriptions form a prompt.. and remember intake and prompting use different vocabularies,  the intake allows the photo to be prompted not as the photo itself but as the purpose of the photo onto the ones its encounter function serves, maintain the objects physical condition precisely, create image showing how its used.   stuff like that

> see what you are missing about the metaform is its providing everything the prompt needs to reason about the prompt writer coming from latent space will see these things and reason on what you ask, please create prompting to help me sell this object..   then you have a photo processing pipeline

## Browsing and schema-dependent representations

> when a prompt is converted it becomes its own data structure, and depending on the schema, of which there could be different type some could be a "for every node" instruction some might be a workflow that as it is being worked it might be showing a variation of the hypergraph where each step is explicitly linking parts of the graph relative to the steps involved

> it should show the directly connected other nodes..    who or what is it acting as a dependency for and what dependencies does it have

## Parametric intake data, reservations, and adjustments

The owner subsequently specified:

> what about the parametric element array if any parametric elements exist, these get reserved in the name space, and block nodes of those names.. also parametrics may be used but never as an acceptance signal for am imperative.   improve the brightness of the photo is not a mutation its an adjustment and does not qualify alone as a acceptance target for prompts

```

### **`metaform/docs/semantics/README.md`**

```markdown
# Semantic source rules

The [Metaform specification](../SPEC.md) contains the current semantic contract:
exact Type identity `C(T) = {(rᵢ ∧ pᵢ ∧ e)}` with one Encounter Function,
established Element roles, strict typology, Encounter propagation, and independent
Contextual and Latent graphs with a separate shape-similarity layer.
[Current work](../current-work.md) records implementation status.

Start with [Developed understanding, receiving relationships, and work](understanding-and-work.md)
for the owner's quoted design statements, glossary definitions, and photograph examples.

These supplied source documents are preserved verbatim.

- [Semantic Equation Preservation and Reuse](semantic_equation_reuse_rule.md)
  — supplied as `Semantic Equation Reuse Rule.md`.
- [Inference Metaform Rules](inference_metaform_rules.md)
  — supplied as `Inference Metaform Rules.md`.
- [Functional typology and encounter](functional_typology.md)
  — settled `code` Name, functional structure, and supplied encounter examples
  from the 2026-09-07 development conversation.

The [Inference Metaform primer](../primer/README.md) provides the narrative
explanation alongside these source rules.

The [Rulebook](../rulebook/README.md) collects individual rules for tasks and
processes, beginning with Name and Description for completing the Element schema.

[Return to the project README](../../README.md)

```

### **`metaform/docs/semantics/semantic_equation_reuse_rule.md`**

```markdown
## Semantic Equation Preservation and Reuse

Treat every authoritative semantic statement, definition, rule, constraint, and example as a semantic equation.

A semantic equation may be referenced, selected, combined, ordered, applied, instantiated, or quoted when constructing prompts and performing inference. Its wording does not need to appear in every generated prompt unless the prompt requires the equation explicitly; however, any use of the equation must preserve the semantic relationship expressed by the source.

Do not rewrite, paraphrase, normalize, summarize, generalize, narrow, invert, reconcile, or replace a semantic equation on the assumption that another expression is equivalent.

When constructing a prompt:

1. Select the semantic equations required for the inference being performed.
2. Preserve each selected equation as an authoritative source constraint.
3. Compose instructions around those equations without modifying their semantics.
4. Derived instructions may operationalize an equation for the current task, but the derived instruction does not replace, amend, or become the source equation.
5. Maintain provenance between source semantics and any instruction, interpretation, implication, or conclusion derived from them.
6. Reuse an existing semantic equation rather than authoring a semantically equivalent replacement.
7. If a semantic equation must change, only an explicit source revision changes it. New inference does not modify prior source semantics.

Semantic equations are the maintained source of meaning. Prompts are temporary compositions that use them.
```

### **`metaform/docs/semantics/inference_metaform_rules.md`**

````markdown
# Inference Metaform Rules

## Metaform

A **Metaform** is a single-layer non-manifold mesh of type knowledge shaped to orient inference toward the expertise through which something is understood and acted upon.

## Latent Metaform

A **Latent Metaform** is a metaform representing the global, foundational form of expertise derived from the AI’s core parameters, free from immediate environmental influence. It serves as the baseline structural anchor.

## Contextual Metaform

A **Contextual Metaform** is the structural form of understanding that emerges when the AI operates *within* a specific project, environment, or prompt constraints. It contains the localized insights—and the accompanying blind spots—of that situational bubble.

## Inference Metaform

An **Inference Metaform** is the combination of the **Latent Metaform** and **Contextual Metaform** into a single non-manifold mesh of type knowledge.

---

# Metaform Typology

## Strict Typology

The namespace is a **strict typology**.

It does not follow a:

```text
domain.class
```

structure and it is not fixed length.

**Domain and class do not exist. Type and subtype do exist.**

Every section of the base, trunk, branches, and leaf must be interpretable as a type.

The base is a type.  
Every part of the trunk is a type.  
Every part of a branch is a type.  
The leaf is a type.

For:

```text
a.b.c
```

each part must qualify as a type:

```text
a
a.b
a.b.c
```

**To be a type, it must describe an encounter or a function, never an encoding.**

Full inference amortization by the archeologist must involve walking back from the leaf to the trunk and ensuring that each part of the chain is speaking to a specific type sprung from its parent.

A namespace component does not exist as a space filler to ensure alignment in a taxonomy namespace.

---

## Type Qualification

To be a **type**, it must describe an **encounter** or a **function**, never an **encoding**.

This qualification applies at every level of the namespace.

The word alone does not establish whether it qualifies. The meaning expressed by the path does.

---

## Singular Type Naming

The namespace is singular only.

```text
document     <- valid
documents    <- not valid
```

We are speaking to the singular type.

Namespace nouns are singular in form and proper.

The namespace names the singular type of **function or encounter**, never the singular deliverable work piece.

The type is singular in form and names a group in function.

---

## Function and Encounter

Types are either **function** or **encounter**.

An **encounter** speaks to a variant of something that has the same function.

Genre, style, and language are types of encounters.

### Game Genre

```text
code.game.platformer          <- valid
code.game.genre               <- not valid
code.game.genre.platformer    <- not valid
```

`platformer` is a genre of `code.game`. It carries the function of `code.game` as a specific genre with its own encounter.

`genre` is not the type.

The type is:

```text
code.game.platformer
```

---

## Programming Language

```text
code.cpp                <- valid
code.language.cpp       <- not valid
```

`cpp` is the encounter of `code`. It carries the function of computer code as a specific language with its own encounter.

The latter evokes a domain/class taxonomy.

`code.language` does not qualify because `code` refers to types of languages. `language` in the namespace is evoking class: a space filler to ensure alignment in the taxonomy namespace.

The Metaform Typology does not concern itself with that structure.

The type is:

```text
code.cpp
```

not:

```text
code.language.cpp
```

---

## Type and Subtype

While domain and class do not exist, the concepts of **type** and **subtype** do exist.

C++ is not a subtype of C because it is treated as its own language.

```text
code.c        <- valid
code.cpp      <- valid
code.c.cpp    <- not valid
```

---

## Interpret the Path, Not the Word

A namespace component is not interpreted by its word in isolation.

What matters is what the path is speaking to.

The same word can participate in different paths with different meaning.

The qualification remains:

> To be a type, it must describe an encounter or a function, never an encoding.

For example:

```text
document.word            <- not valid
```

speaks to the **Word document**, not to the program named Word.

The fact that `word` is also the name of a program is not the reason the path does not qualify.

The Word document remains an encoding or format distinction and does not describe an encounter or a function.

---

## Encoding Is Not Expressed

Format is neither a type nor a style. It is an encoding.

The Metaform Typology does not carry encoding in the namespace.

```text
jpg    <- encoding
png    <- encoding
```

Markdown is not a type of document. It is an encoding or format.

Word documents remain an encoding.

HTML under `document` speaks to the way written content is encoded.

Therefore:

```text
document.word            <- not valid
document.html            <- not valid when speaking to document encoding
```

These paths do not qualify as types because they describe encoding rather than encounter or function.

---

## Encoding Names Are Not Banned

Encoding names are not banned from the namespace.

The rule is not:

```text
jpg = not valid
png = not valid
```

The rule is:

> To be a type, it must describe an encounter or a function, never an encoding.

If the function is encoder or decoder, an encoding name can be used because in that form it is a **function**.

Examples:

```text
code.converter.image     <- valid
code.encoder.jpg         <- valid
code.encoder.png         <- valid
```

These paths describe functions.

`jpg` and `png` are encodings, but the paths are not expressing the encoding as the type.

---

## HTML

HTML demonstrates why the word itself cannot determine the type.

Placed under `document`:

```text
document.html            <- not valid
```

HTML speaks to the way written content is encoded.

The typology does not deal with encoding, only function and encounter.

Placed under `code`:

```text
code.html                <- valid
```

HTML can be valid because HTML is technically considered a language. People learn HTML as a language.

In that form it describes an encounter.

---

## Embedded Code

HTML can contain JavaScript.

Word documents can contain interactive code.

That does not make the document itself code.

Word documents remain an encoding.

HTML under `document` can speak to document encoding while HTML under `code` can speak to HTML as a language.

---

# Aliases

Aliases are required semantic runs of the namespace.

They must be preserved because they teach the distinction between the type and alternate names for that type.

All **metatype records** contain an `aliases` array. The purpose of this array is to prevent duplicates and ease searching.

## C

```text
code.c
code.c.c11
code.c.11                <- alias
```

## C++

```text
code.cpp
code.cc                  <- alias
code.cxx                 <- alias
code.cplusplus           <- alias
```

## C++11

```text
code.cpp.cxx11
code.cpp.cpp11           <- alias
code.cpp.11              <- alias
```

The alias forms do not replace or restructure the typology represented by the primary path.

## Intake clarification — 2026-09-08

The owner's supplied clarification:

> you also need the alias array, for the leaf (last word in the schema)   the most basic universal aliases that would likely be searched last part of the name space in alphanumric only, the purpose is to eliminate double entry and ease searching the name space they block those aliases from being used by other elements

> yes names can be reused they only reserve them at that specific address

---

# Required Semantic Runs

These examples are semantic equations for inference, not disposable illustrations.

## Strict Typology

```text
code.cpp                         <- valid
code.language.cpp                <- not valid
```

## Genre Encounter

```text
code.game.platformer             <- valid
code.game.genre                  <- not valid
code.game.genre.platformer       <- not valid
```

## Document Encoding

```text
document.word                    <- not valid
```

## Context Changes What the Path Expresses

```text
document.html                    <- not valid when speaking to document encoding
code.html                        <- valid when speaking to HTML as a language
```

## Encodings

```text
jpg                              <- encoding
png                              <- encoding
```

Encoding itself does not qualify as a type.

## Encoding Name Used in a Function

```text
code.converter.image             <- valid
code.encoder.jpg                 <- valid
code.encoder.png                 <- valid
```

## C Aliases

```text
code.c
code.c.c11
code.c.11                        <- alias
```

## C++ Aliases

```text
code.cpp
code.cc                          <- alias
code.cxx                         <- alias
code.cplusplus                   <- alias
```

## C++11 Aliases

```text
code.cpp.cxx11
code.cpp.cpp11                   <- alias
code.cpp.11                      <- alias
```

---

# Archeologist Rule

For a proposed namespace path, walk backward from the leaf to the trunk.

At every point in the chain, ensure that each part is speaking to a specific type sprung from its parent.

At every point, the type must qualify by describing:

```text
encounter
```

or:

```text
function
```

never:

```text
encoding
```

Do not impose:

```text
domain.class.type
```

Do not impose fixed path length.

Do not insert class terms to make a taxonomy align.

Do not determine validity from the isolated word.

Interpret what the path is speaking to and determine whether it describes an encounter or a function, never an encoding.

The namespace is a strict typology.

---

# Element

**Element** as a term speaks to a type.

Its further role in the general organization remains to be defined.
````

### **`metaform/docs/semantics/functional_typology.md`**

```markdown
# Functional typology and encounter

Settled with the owner on 2026-09-07. The statements and encounter table below are
preserved from that conversation. They establish the context for the rulebook's
`code` example.

## Structure and encounter

> we are at our core a functional typology with encounter encoded in it..  When placing things in the metaform we need structure by using function and then extend it by linking the encounter.

## The code trunk

> code is program code settled..  its the function

The Name of `code` is **program code**. This supersedes the earlier
`programming language` Name in the handoff's trunk example. The discussion of
broadening `code` to collect other meanings of the word did not establish a new
trunk or new branches.

> code.cpp this is an encounter of code as a function...

The maintained [Programming Language rule](inference_metaform_rules.md#programming-language)
and [Aliases](inference_metaform_rules.md#aliases) provide the namespace examples.
`code.language.*` remains a bad inference.

## Leaf variants and transitive encounter

The owner's clarification:

> code.cpp is an encounter because its a leaf varient of its core function code

The direction in `code.cpp.cxx26` was made explicit:

> cxx26 is the encounter of code.cpp

The core function remains `code`.

> Metaforms deal with linking to core functions, encounters are realized by linking them into the graph as a transitive that effects all nodes back to the core function (its trunk) and forward through its branches.

## Encounters of code.cpp

The owner's supplied table uses namespaces and aliases relative to `code.cpp`.
Descriptions are reproduced as supplied.

| Namespace | Aliases | Description |
|---|---|---|
| cxx26 | 26, cpp26 | A forthcoming standard that is actively being drafted by the ISO committee, aiming to introduce contract programming, structural reflection, and linear algebra libraries. |
| cxx23 | 23, cpp23 | A refined modern standard that prioritizes developer convenience by introducing standard library modules (import std) and dedicated formatting utilities (std::print). |
| cxx20 | 20, cpp20 | A massive, transformative upgrade to the language that radically changed how developers write software through the introduction of Concepts, Coroutines, and Ranges. |
| cxx17 | 17, cpp17 | A mid-sized enhancement package that polished the language by standardizing filesystem access (std::filesystem), unpacking syntax (structured bindings), and type-safe unions (std::variant). |
| cxx14 | 14, cpp14 | A deliberate, stabilization-focused release that acted as a bug-fix and refinement cycle to patch omissions left behind by the prior major overhaul. |
| cxx11 | 11, cpp11 | A revolutionary milestone that completely redefined the ecosystem into "Modern C++" by introducing game-changing features like move semantics, smart pointers, and type inference via auto. |

> That table is a table of encounters of code.cpp as a function.

## Use in the rulebook

The example seeds understanding of the rules and demonstrates their application.
Its reasoning belongs in the expansion alongside the concise rule. Notes shape
inference; they are not a change log.

[Rulebook](../rulebook/README.md)

## Namespace characters and dispatcher correction

The owner's subsequent corrections:

> we shouldnt have underscores in names...

> if its a dispatcher make ity code.dispatcher.command

> we only allow alphanumeric

The corrected path has `code` as its core function, `dispatcher` as its
functional branch, and `command` as the leaf encounter of `code.dispatcher`.
Each Namespace component is alphanumeric; periods link those components.
This concerns Namespace components, distinct from human-readable Element Names
such as **program code**. It does not restore the historical alphabetic-only
restriction, since the established `cxx23` encounter contains digits.

## Comprehensive functions and deterministic construction

The owner explained why the naming rule preserves single-word Type levels:

> I mean thats why I made the rule that way so that the name space could be comprehensive and hold all handlers under that node

> this has a lot of reasons one it try to enforce determinism

The worked handler path is `code.handler.command`. The handler function is
comprehensive across its encounters; command specializes that function. The
same reasoning establishes `code.dispatcher.command`. Joining the words as
`commanddispatcher` would satisfy the character restriction while preserving
the structural collapse. These distinctions belong in the priming of the
existing Name rule, not in a new naming taxonomy.

```

### **`metaform/docs/handoff/COLLABORATION_REVIEW.md`**

```markdown
# Collaboration review

## Practices worth carrying forward

The work was strongest when conceptual discussion was connected to concrete
source material and observable implementation. Exact rule wording was preserved,
repository changes were isolated and published with identifiable contents, and
software verification was distinguished from design interpretation.

The owner values an active sounding board. Offer specific judgments and useful
connections, help develop ideas, and explain concrete reasons for criticism.
When a decision becomes clear, carry the agreed work through to a usable result.

## Improvements for the next session

**Keep implementation aligned with the visible design.** Some implementation
choices advanced before their role and presentation had been jointly
understood. Begin from the named things and relationships the owner expects to
inspect, then choose the implementation that serves them. Surface consequential
new choices during the design conversation.

**Maintain decisions as they evolve.** Exact source preservation worked, but
later refinements to the rule presentation remained only in conversation.
Record a settled refinement when it happens and identify the affected source or
implementation, so the saved state continues to represent the current intent.

**Use examples to demonstrate meaning.** Example selection needs the same
semantic care as the rule text. Existing established material is the starting
point. A problem with an example should be addressed at the example; any proposed
change to a settled rule needs its own concrete semantic reason.

**Keep status explicit.** Distinguish accepted decisions, assistant proposals,
implemented behavior, and completed verification. This lets discussion remain
open without making provisional ideas look like product requirements.

These are development collaboration practices. The existing `AGENTS.md` keeps
that role separate from the instructions authored for Metaform's runtime agents.

```

### **`metaform/docs/handoff/CURRENT_WORK.md`**

```markdown
# Current work

Snapshot captured on 2026-09-07 at approximately 18:24 UTC.

## Goal to resume

Complete the rulebook's agreed representation, then continue with the owner on the
remaining Element-schema rules and their use in the task/workflow interface.
Establish a maintainable development continuity process in this persistent CLI
workspace while doing that work.

## Remote state

Repository: <https://github.com/RchGrav/metaform>

| Item | Verified state at capture |
| --- | --- |
| `main` | `8085b1ae811e9fe53bd660b9b7b80d7eace76805` |
| Workbench cleanup | Merged through PR #2; included in `main` |
| Rulebook PR | <https://github.com/RchGrav/metaform/pull/3> — open, unmerged |
| PR #3 branch | `codex/element-rulebook` |
| PR #3 head | `5e9acea1427a9a9abb0b6af298c046a2516479b8` |

The handoff package was prepared without changing these branches or PRs. The
new checkout and its present working-tree state are the starting workspace.

## What is saved

Main contains the semantic source documents, narrative primers, existing
`AGENTS.md`, and the workbench cleanup. PR #3 adds a rulebook index, separate Name
and Description entries, the supplied `code` example, and a navigation link from
the semantic-source index.

PR #3 preserves the complete sentences verbatim, but calls them expanded forms
and uses shorter phrases as concise forms. D02 in `DECISIONS.md` records the
later agreed correction. It has not yet been applied to that PR.

## Current implementation and scope

- The merged cleanup makes the default graph represent intake knowledge, with
  an empty state when none has been collected. Supporting records remain
  inspectable with their recorded provenance.
- Viewer and preview startup return links. Automatic browser opening was
  removed.
- Example workflows are retained under `examples/workflows/` for explicit use.
  Automatic example seeding and the earlier Doors implementation were removed
  in the merged cleanup.
- The workflow GUI still presents forms; the requested named-workflow-to-steps
  presentation remains work to design and implement.
- The rulebook changes are documentation. They have not implemented a Rules
  editor, rule attachment UI, or first-exposure delivery mechanism.
- The CLI remains sufficient to operate the system. The current MCP router
  exposes broader commands; the role the owner presently wants to discuss is graph
  browsing.
- The viewer currently serves one selected project per process. Multiple
  project viewers and shared global knowledge exist. The desired longer-term
  project-selection and server arrangement remains open.

`docs/workbench-cleanup.md` is the concise inventory of the retained chassis,
intake, workflow, graph, packaging, image generation, and provenance capabilities.
`docs/serena-reference.md` records implementation references for the server/MCP
discussion.

## Documentation items to reconcile during relevant work

- `docs/next-version.md` still says browsing opens a browser; the merged cleanup
  removed that behavior.
- The authoritative Aliases material is bundled in
  `docs/semantics/inference_metaform_rules.md`. Older verification/source notes
  describe it as missing, while runtime source wiring still needs review.
- Some older source examples use `code.language.cplusplus`. The maintained
  namespace rules identify `code.cpp` as valid and the intervening `language`
  level as invalid.

## Validation carried forward

The cleanup pass reported 50 passing tests and successful distribution/offline
CLI, MCP, viewer, and export checks. That is the last reported software
verification, not a new test run for this handoff. A complete browser visual
inspection was not performed in that workspace because its browser connection
was blocked.

PR #3 was checked for exact preservation of the supplied sentences and example,
valid local document links, and whitespace. Its remote tree matched the local
committed contents. The handoff itself is a documentation transfer.

```

### **`metaform/docs/handoff/HANDOFF.md`**

```markdown
# Metaform development handoff

## Next goal

Finish the rulebook for completing the Element schema, and work with the owner on how
its rules will be inspected, edited, and attached to tasks or workflows in the
next version. Begin with the established Name and Description rules.

The first concrete correction is in PR #3: its saved layout places the complete
rule sentences under “Expanded form.” The later agreed design makes those
sentences the concise formulas. Expanded material supplies additional detail and
worked examples alongside the formulas. The wording itself has been preserved.

Continue discussing the remaining rules and interface organization.
Rules are a concrete interface feature; their navigation placement is open.

## Starting context

Metaform prepares reusable semantic understanding so later instructions can
operate specifically through an artifact's Elements and relationships. The
current construction combines contextual examination of a composite artifact
with independent inference about its participating Types. Source attribution
remains available when the two perspectives are brought together.

The immediate product emphasis is making that work understandable: inspect
project knowledge, open a named workflow to its steps, and inspect the prompts
and applicable rules. The owner is refining the semantics through collaboration.

This archive is intended to be placed at the root of the existing
`RchGrav/metaform` checkout. It contains development continuity material. Its
top-level directory keeps extraction separate from the checkout's existing files.
Repository and PR status is recorded in `CURRENT_WORK.md`.

## Read next

1. The checkout's `AGENTS.md`; an unchanged copy is included here.
2. `RULE_WORDING.md` for the exact settled rule sentences and supplied example.
3. `DECISIONS.md` for the current design decisions, including later refinements.
4. `CURRENT_WORK.md` and `OPEN_QUESTIONS.md` for the implementation state and
   discussions to resume.
5. `COLLABORATION_REVIEW.md` and `CONTINUITY_PROCESS.md` for working practices to
   carry forward and refine in the persistent CLI workspace.

The repository's `docs/semantics/semantic_equation_reuse_rule.md` and
`docs/semantics/inference_metaform_rules.md` contain the maintained semantic
source rules. `docs/primer/02_specification_introduction.md` is a narrative
orientation. Its explanatory role is distinct from the rule sources.

Resume from the next goal above and the actual checkout state. The snapshot
below is dated; branches and pull requests may subsequently advance.

```

### **`metaform/docs/handoff/RULE_WORDING.md`**

````markdown
# Established rule wording

These are the established initial Name and Description rules for
completing the Element schema. The sentences below retain the supplied wording
verbatim, including its original grammar. They are the concise formulas under
the latest agreed arrangement.

## Name

The most basic universal name as a singular proper noun which places itself comfortably into the definitions of its children

## Description

The most basic universal statement that both defines uses the ancestral proper nouns of its lineage in reverse namespace order in a semantically proper statement but never name or include the most basic universal definition of the encounter or functions of its children

## Supplied trunk example

```yaml
code:
  name: programming language
  description: a set of precise instructions that tells a computer how to perform a task or process data
```

The other starting trunks are `document`, `media`, and `data`. Their corresponding
seed definitions were not settled in this discussion.

Expanded supporting material accompanies a rule on first exposure. The complete
set of wrong, substandard, and correct worked examples remains to be selected
from existing established material.

````

### **`metaform/docs/handoff/CONTINUITY_PROCESS.md`**

```markdown
# Development continuity process

This is a proposed starting structure for the next context to refine with the owner
inside the persistent CLI workspace.

## Small maintained records

| Record | Purpose |
| --- | --- |
| `docs/decisions.md` | Current agreed decisions, brief reasons, sources, and supersession references. |
| `docs/current-work.md` | Current goal, implementation state, repository references, verification, open questions, and the next work to resume. |
| Existing semantic source files | Exact authoritative wording and worked examples, referenced by the other records. |

The handoff's `DECISIONS.md`, `CURRENT_WORK.md`, and `OPEN_QUESTIONS.md` provide
initial content for that structure. Their long-term location and organization
can be refined in the new workspace. A short reference in the checkout's
`AGENTS.md` can make the maintained records discoverable.

## During collaboration

When a decision is settled, record its identifier, capture date, wording or
source reference, brief rationale, and implementation status. Keep proposals
identified as proposals. A later decision can supersede an earlier one, with
Git preserving the history.

Preserve semantic formulas in their authoritative files and reference them from
the decision record. Record which files or behavior need to reflect a changed
decision. This keeps an accepted refinement visible even before implementation.

After a meaningful unit of work, update the current goal and work state with the
actual branch, commit or PR, completed changes, verification performed, and
remaining work. Commit and publish those development records along with the
relevant work using the project's normal Git workflow.

## Before another handoff

Review the current decisions and working state against what was actually saved.
Write a short collaboration review of practices that helped and specific
adjustments that would improve the next session. Keep its observations factual
and useful to the work ahead.

Lead the handoff with the next goal and a concrete starting item. Then point to
the maintained decisions, exact semantic sources, current state, and open
questions. The owner and the agent shape the intended context together before the
handoff is finalized.

```

### **`metaform/docs/handoff/DECISIONS.md`**

```markdown
# Current design decisions

Captured on 2026-09-07 from the development conversation. These are settled
directions; open matters are in `OPEN_QUESTIONS.md`. Implementation status is
separate and recorded in `CURRENT_WORK.md`.

## D01 — Rulebook purpose

A rulebook contains the precise rules that attach to a task or a process used
to complete a task. Name and Description are separate rules for completing the
Element schema. Their established wording is in `RULE_WORDING.md`.

## D02 — Rule presentation

The concise component is the complete semantic formula, which may be a complex
single sentence. The expanded component is additional explanation and examples
provided alongside it. First exposure presents both; later repetition in the
same agent context can use the concise rule when needed.

The owner's final clarification:

> the expanced version need not repeat the concise version the expanded version is extra detail provided alongside the concise version to lock in correct understanding on first exposure to the rule.

This supersedes the earlier arrangement recorded in PR #3. Application of this
refinement to the repository remains outstanding.

## D03 — Worked examples

The expanded presentation brings one wrong, one substandard, and one correct
example together. Use existing established material; other entries can provide
additional examples by reference. The supplied `code` trunk is preserved in
`RULE_WORDING.md`. The complete example set is still to be selected.

## D04 — Rules in the interface

Rules are a concrete, inspectable and editable interface feature, attached to
tasks or processes. Their placement in navigation is open. The owner suggested they
may sit inside an area containing related things such as tasks.

## D05 — Recognizable presentation

The interface should expose the actual system through direct, descriptive names
and relationships. A named workflow opens into its steps and the prompts used
there. The project graph represents collected and inferred project information,
with source attribution visible. Supporting prompt and workflow records have
their own identifiable role.

These are serious engineering tools for understanding and refining the system.
Interface organization should preserve the owner's ability to reason about what he
is viewing. The relevant earlier cleanup is documented in
`docs/workbench-cleanup.md` in the checkout.

## D06 — Scope of the Metaform concept

The owner described a Metaform as using a semantic function to express an invariant;
in the current base form, that invariant is Type. Encounter Function, Receiving
Entity, and Operative Purpose are the principal dimensions discussed for this
form. The broader concept allows other dimensions and forms. This is a
conceptual clarification to carry into future definition work, rather than a
newly authored replacement definition.

## D07 — Construction and semantic source

Construction starts with the composite artifact and decomposes it into its
participating Elements. Operative Purpose belongs to receiving relationships.
The namespace's levels carry semantic meaning, and the work is stated at the
Type level. The maintained namespace and alias equations are in
`docs/semantics/inference_metaform_rules.md`.

Contextual and independent inference remain attributable. Global inference
authors its own joins without receiving the project's contextual OP joins.
The repository's semantic sources already describe this separation in detail.

## D08 — Collaboration and implementation scope

Brainstorming is an invitation to develop an idea together. Established work
can proceed; consequential unresolved design choices belong in the discussion.
Use exact semantic source wording when preserving rules and prompts. The
checkout's `AGENTS.md` contains the existing collaboration guidance.

The next version's detailed interface organization and broader MCP role remain
open matters, as recorded in `OPEN_QUESTIONS.md`.

```

### **`metaform/docs/handoff/OPEN_QUESTIONS.md`**

```markdown
# Discussions to resume

## Rulebook

- Develop the Alias and Dependency rule entries from existing source material
  and the owner's explanations. Alias equations already exist in
  `docs/semantics/inference_metaform_rules.md`; the typological process and OP
  dependency direction are described in
  `src/metaform/data/semantics/metaform-intake.source.md`.
- Develop the “rule rule”. The agreed concise-plus-supplement
  presentation is recorded in D02; a final rule sentence has not been settled.
- Select the complete wrong/substandard/correct example sets from existing
  material and retain the reason each example illustrates its category.
- Work out how the rulebook is stored and how applicable rules are attached to
  tasks or processes. The exact rule schema and runtime first-exposure tracking
  have not been designed.

## Record notes and terminology

The owner proposed a notes field. This is a schema proposal, not an implemented or
settled field. His supplied note for the `code` record is:

> We chose to use "programming language" over "computer code" because it better supported our desire to have all elements id's reverse into a natural description.

Element IDs, Type IDs, and Objects were left undecided. The assistant suggested
“namespace” for the particular sentence about reading lineage in reverse; the owner
has not finalized that naming choice. “Record” was also an assistant suggestion
for the stored representation.

## Interface organization

- Determine the containing area for tasks and related material, including
  rules. A dedicated top-level Rules navigation item has not been selected.
- Develop the named-workflow/step presentation and make the associated prompts
  and rules understandable in that context.
- Discuss how prompt trials relate to a concrete workflow and target. The
  existing answer/note storage is an observation facility; a workflow-level
  evaluation procedure has not been agreed.

## Server and MCP

Discuss project selection, process ownership, and graph browsing.
Serena was examined as a reference for running-server and deployment patterns.
Its patterns are reference material, not an adopted architecture. Broader MCP
workflow exposure remains open.

```

### **`metaform/docs/rulebook/format.md`**

````markdown
# Rule format under development

Current design, 2026-09-07. The discussed shape now has a working schema
(`metaform:semantic-rule`) and [seed data](../../src/metaform/data/rulebook.json).
Its descriptions and examples remain available for refinement.

## Established meaning

The owner clarified the concise component:

> consise is NOT the complete semantic rule, its the concisely accurate rule that is accurate and concise but should be reinforced with examples and explanations

The expansion reinforces the concise rule with freeform context and accepted
and rejected examples with reasons. First exposure primes latent understanding;
later use in that context can rely on the concise rule with confidence.

Field descriptions use descriptive wording such as “The rule stated,” not
imperatives such as “State the rule.” This distinguishes schema descriptions
from imperative content carried by actual rule records.

Rules are reasoning building blocks. The Element Name and Description rules do
not define the format of a rule record.

## Proposed field descriptions

The values here describe the fields. They are not seed-record contents.

```json
{
  "rule_code": "The rule’s unique reference, expressed using lowercase letters and digits.",
  "purpose": "The reasoning purpose served by the rule and the context in which it applies.",
  "concise": "The rule stated accurately and concisely.",
  "priming": {
    "context": "Extra freeform context clarifying the concise rule’s meaning on first exposure, including nuance, reasoning, and distinctions supporting accurate interpretation and application.",
    "examples": [
      {
        "example": "An accepted example.",
        "assessment": "accepted",
        "reason": "The reasoning establishing how the example satisfies the rule."
      },
      {
        "example": "A rejected example.",
        "assessment": "rejected",
        "reason": "The reasoning identifying where the example fails the rule and why."
      }
    ]
  }
}
```

`priming` and `context` were proposed as clearer names for `expansion` and
`explanation`. `rule_code` and `purpose` were proposed in response to the owner's
preference for a rule code and purpose over a complex applicability structure.

## Identifier direction

The owner proposed letters followed by digits, potentially expressing a rule type
and index. The interpretation offered was `^[a-z]+[0-9]+$`, requiring both parts.
The schema uses that pattern. The meanings of prefixes and index allocation
have not been established. The initial `r1` through `r4` references do not assign
a prefix taxonomy.

## Working seed data

The reviewable seed-data file contains Name, Description, function/encounter,
and Type-qualification rules. The settled Name and Description
sentences are available verbatim in their rulebook entries. The function/encounter
source statements and supplied examples are in
[Functional typology and encounter](../semantics/functional_typology.md).
Any newly composed concise sentence or example reasoning needs to remain
distinguishable from the owner's established source wording during review.

The schema is registered alongside the existing schemas. Seeds are inserted
only when their rule IDs are absent, preserving edits. The runtime's
`metaform:rule` schema describes executable transition expressions;
`metaform:semantic-rule` describes this reasoning-rule format.

[Rulebook](README.md)

````

### **`metaform/docs/rulebook/README.md`**

````markdown
# Rulebook

Rules attach to a task, or a process to complete a task. Each rule has a concise
rule and an expansion. The concise rule is the rule stated accurately and
concisely. The expansion conveys nuance, useful supporting explanation, and
accepted and rejected examples with reasons.

First exposure presents both to prime latent understanding so that later in the
same context the concise version can be used with confidence. The expansion
provides additional material alongside the concise rule.

The [rule format](format.md) records the field descriptions and identifier
direction. The [seed data](../../src/metaform/data/rulebook.json) contains actual
rules and priming material; [seed provenance](seed-sources.md) distinguishes
exact supplied statements from derived explanations and counterexamples.

Rules load as authored records under `rule:<rule_code>` using
`metaform:semantic-rule`. Startup adds missing seeds and preserves edited rules.

```sh
metaform rulebook get --rule_code r3
metaform rulebook prepare --rule_codes '["r3"]'
metaform rulebook put --rule @rule.json
```

Preparation includes priming by default. `--concise_only` requests concise
material for a context that has already received the priming. Automatic
assignment preparation always includes priming because a later workflow step
does not establish that the receiving agent shares an earlier context.

Prompt records and workflow steps can reference rules with
`"rule_codes": ["r1", "r2"]`. Prepared assignments contain exact rule content and
revisions in `rules`. Workflow frames retain these snapshots so later edits do
not silently change a running frame. The default intake references `r1` through
`r4`; existing authored prompt text is retained.

## Completing the Element schema

| Rule | Source |
| --- | --- |
| Name | [Name rule](element/name.md) |
| Description | [Description rule](element/description.md) |

The concise formulas in these two rules are the owner's supplied wording,
preserved verbatim. Each expansion includes the supplied `code` trunk, with its
Name now settled as **program code**. The
[functional typology and encounter clarification](../semantics/functional_typology.md)
records that decision and the supplied C++ encounter examples. The complete
accepted and rejected example sets and their reasons remain to be developed.

The Element schema's `notes` field is freeform context shaping inference, not a
change log.

### Further rules to discuss

Aliases and Dependencies are additional rules for completing the Element schema.
Their existing source material is available in
[Aliases](../semantics/inference_metaform_rules.md#aliases) and the
[typological process](../../src/metaform/data/semantics/metaform-intake.source.md#part-2--the-typological-process).

The rule governing how rules are authored and presented—the “rule rule”—is also
for discussion.

[Semantic source rules](../semantics/README.md)

````

### **`metaform/docs/rulebook/seed-sources.md`**

```markdown
# Rule seed sources

[The rule seed](../../src/metaform/data/rulebook.json) contains five records in
the [proposed rule format](format.md). `r1` through `r5` are neutral references;
they do not establish rule categories or a prefix taxonomy. Each record contains
actual rule content. Provenance belongs here, outside the inference context.

## Concise wording

| Record | Exact source | Status |
| --- | --- | --- |
| `r1` | [Name, Concise form](element/name.md#concise-form) | Established wording, copied verbatim. |
| `r2` | [Description, Concise form](element/description.md#concise-form) | Established wording, copied verbatim, including the original grammar “that both defines uses” and “but never name”. |
| `r3` | [Functional typology, Leaf variants and transitive encounter](../semantics/functional_typology.md#leaf-variants-and-transitive-encounter) | The owner's complete transitive-linking statement, copied verbatim, including “effects”. |
| `r4` | [Inference Metaform Rules, Strict Typology](../semantics/inference_metaform_rules.md#strict-typology) | Maintained Type-qualification sentence, copied verbatim. |

| `r5` | [Namespace characters](../semantics/functional_typology.md#namespace-characters-and-dispatcher-correction) | The owner's concise alphanumeric statement, copied verbatim. |

## Priming and examples

Purposes and connecting explanations are assistant-authored expressions of the
sources below. They do not replace the established concise wording. Examples
and their reasoning remain available for refinement.

- **`r1`:** The accepted `code` Name and Description are the supplied worked
  example in [element/name.md](element/name.md). Its program-code interpretation
  is settled in [functional_typology.md, The code trunk](../semantics/functional_typology.md#the-code-trunk).
  The rejected Name `C++ program code` and its reason are an assistant-derived
  narrow counterexample: the Name would place the child encounter into the
  identity of the core function. This is not a historical rejected record.
- **`r2`:** The accepted trunk example is supplied in
  [element/description.md](element/description.md). The rejected version appending
  “including C++” is an assistant-derived counterexample to the exact rule's
  exclusion of child names and definitions. It is not a historical rejected
  Description. The context concerning backwards reading reflects the owner's
  clarification in the current conversation that the check operates within the
  definition; fluency alone is insufficient. The seed intentionally does not
  invent an accepted full child Description to demonstrate ancestral naming.
- **`r3`:** The first three paragraphs of context reproduce the owner's statements
  from [functional_typology.md](../semantics/functional_typology.md), including
  their spelling. The accepted `code.cpp` example follows that source.
  `code.cpp.cxx23`, the functional-branch explanation, and the rejected permanent
  role and reversed-relation examples express the owner's subsequent clarification
  in the current conversation: code is the trunk, cpp is the encounter when it
  is the leaf, and cxx23 is the encounter when it is the leaf attached to cpp.
  The example sentences and reasons are assistant-authored from that
  clarification. The supplied standards table is encounter context; its release
  descriptions are not treated as universal Element Descriptions.
- **`r4`:** Accepted and rejected paths come from
  [inference_metaform_rules.md](../semantics/inference_metaform_rules.md),
  specifically Programming Language, Interpret the Path, Not the Word, Encoding
  Names Are Not Banned, and HTML. Reasons preserve those distinctions, with
  “program code” reflecting the owner's settled trunk Name. The older Programming
  Language explanation also says “`code` refers to types of languages”; that
  characterization is not imported into the seed because the later settled
  [code trunk statement](../semantics/functional_typology.md#the-code-trunk)
  establishes program code. Its rejection of `code.language.cpp` as a taxonomy
  space filler remains applicable and is preserved.

- **`r3` and `r5`, dispatcher correction:** the owner supplied
  `code.dispatcher.command` as the correction to the inferred
  `code.command_dispatcher`, then confirmed alphanumeric components. The
  function/encounter explanation and example reasons are assistant-authored
  applications of that correction. The distinction between Namespace
  components and human-readable Element Names follows the established
  **program code** Name. Existing authored rules and prompt attachments are
  preserved on startup; the example project's rule attachments are explicitly
  updated for this review.

- **`r1`, comprehensive parent:** The handler and dispatcher examples apply
  the owner's explanation that the namespace must hold all handlers under their
  function, and that the rules aim to enforce determinism. Their context and
  reasons are assistant-authored applications of the existing Name rule. The
  concise Name formula remains unchanged. Alphanumeric `commanddispatcher`
  is rejected for structural collapse, not for its characters.

```

### **`metaform/docs/rulebook/element/name.md`**

````markdown
# Name

For completing the Element schema.

## Concise form

The most basic universal name as a singular proper noun which places itself comfortably into the definitions of its children

## Expansion

### Worked example

Supplied `code` trunk:

```yaml
code:
  name: program code
  description: a set of precise instructions that tells a computer how to perform a task or process data
```

[Settled functional typology and encounter context](../../semantics/functional_typology.md)

````

### **`metaform/docs/rulebook/element/description.md`**

````markdown
# Description

For completing the Element schema.

## Concise form

The most basic universal statement that both defines uses the ancestral proper nouns of its lineage in reverse namespace order in a semantically proper statement but never name or include the most basic universal definition of the encounter or functions of its children

## Expansion

### Worked example

Supplied `code` trunk:

```yaml
code:
  name: program code
  description: a set of precise instructions that tells a computer how to perform a task or process data
```

[Settled functional typology and encounter context](../../semantics/functional_typology.md)

````

### **`metaform/docs/primer/02_specification_introduction.md`**

```markdown
# Inference Metaform
## Specification introduction

The Inference Metaform performs part of the semantic inference required for subsequent work in advance and represents the resulting understanding for reuse. This preparation establishes what an Element is, what its dependencies mean, how Encounters affect its realization, what receives its effects, what purposes those relationships serve, and what follows from relevant perspectives.

Reusing this understanding reduces the prerequisite reasoning that each downstream operation must reconstruct. The intended result is more effective inferential depth available for implementation, refactoring, porting, diagnosis, design, foresight, and other higher-order work. This concerns the starting point and use of task reasoning, not an increase in the model's physical capacity.

The system is fundamentally semantic. Its graph, namespace, prompts, and orchestration implement and expose semantic relationships rather than defining meaning through their incidental representations. Everything under examination can be treated as an Element, with Artifact Type supplying its semantic structural frame. Each prefix of a type path, such as `code.utility.disk`, is itself a promptable Artifact Type. A prefix qualifies through Function or Encounter rather than domain/class filler. Encoding alone does not qualify as a type; an encoding name may appear where the path expresses a Function, such as an encoder.

Preparation begins with deep contextual analysis of the actual project, repository, or implementation plan. The resulting Contextual Metaform represents functions, behavior, data structures, dependencies, Encounters, purposes, receiving relationships, and other materially present semantics. This contextual understanding is valuable but can carry blind spots arising from the project's architecture, terminology, assumptions, and history.

The Latent Expert examines project-derived Artifact Types individually, without the project's joins and without its Operative Purposes. It constructs its own relevant relationships from learned type knowledge. The resulting Latent Metaform provides a project-decontextualized perspective. The Contextual Metaform and Latent Metaform remain complete, independent graphs, directly viewable and observable, including through MCP. A separate shape-similarity layer contains only structural correspondence and provenance references, with no copied semantic payload. It records `01` for structure present contextually only, `10` for structure present latently only, and `11` for the same nodes and join structure present in both. These values do not encode confidence, correctness, precedence, or semantic reconciliation. If source join contents differ, both source joins remain intact in their respective graphs with their own provenance.

The semantic structure is represented in a knowledge graph of knowledge graphs using reified knowledge hypergraph semantics. Relationships can themselves be examined, with their roles, purposes, receivers, conditions, evidence, procedures, and other meaningful participants preserved. Local work can consequently be interpreted through project-wide relationships and other relevant perspectives rather than only through an agent's immediate reconstruction of nearby code.

The principal perspectival relationship combines Encounter Function—how; Receiving Entity—who or what; and Operative Purpose—why. These relationships operate at the selected resolution. A subsystem and its external receiver can have distinct receiving-purpose relationships without collapsing them into one mission-level purpose.

Encounters affect inference through the type structure. A language Encounter such as `code.c`, joined at `code.utility.disk`, is available when reasoning at broader ancestor types `code.utility` and `code`. From its attachment point, the Encounter conditions inference through the functional descendants of that branch. Backward visibility does not cause an Encounter to fan back down unrelated sibling branches. Its consequences can be resolved against Receiving Entity, Operative Purpose, and other represented perspectives.

Prompts and Metaforms are separately reusable. A prompt specifies an operation through the semantic structure; the Metaform makes previously inferred meaning available to that operation. Compact prompts can therefore engage project-specific implications without restating all of them. No particular reconciliation, engineering, foresight, or other prompt sequence defines the Metaform procedure.

Identity preservation concerns semantic relations rather than frozen implementation content. For an Artifact Type `T`, the formal identity is the exact set `C(T) = {(rᵢ ∧ pᵢ ∧ e)}`: each conjunction binds a Receiving Entity `rᵢ`, its Operative Purpose `pᵢ`, and the Type's single Encounter Function `e`. A materially different Encounter makes a different Type or variant, represented through a further typological distinction rather than by adding a second EF to the same Type. A realization may mutate substantially while its identity-defining relation remains invariant. This supports examining different refactorings or target-language realizations without making the current implementation the definition of the Type. The identity definition is semantic guidance for reasoning about the Type; it does not itself prescribe an approval gate, lifecycle, or runtime check.

The development demonstration provides an early proof of behavior, not quantified performance claims. The central architectural proposition is that previously performed inference, retained contextual and latent perspectives, and graph-wide semantic relationships together allow later work to reason from a more developed understanding rather than rebuilding that understanding within every attempt.

```

### **`metaform/docs/primer/README.md`**

```markdown
# Inference Metaform primer

These narrative explanations introduce Metaform's approach and mechanisms.
The [canonical specification](../SPEC.md) defines the semantic contract and
acceptance scenarios developed here.

The [semantic source rules](../semantics/README.md) are available alongside this
primer.

| Document | What it covers |
| --- | --- |
| [Full explanation](01_full_explanation.md) | Previously performed inference, contextual and latent understanding, Encounter propagation, prompting, and higher-order work. |
| [Specification introduction](02_specification_introduction.md) | A concise introduction to the approach and its principal relationships. |
| [Technical account](03_technical_account.md) | Semantic construction, provenance, type structure, propagation, identity, and inference reuse. |
| [Combined edition](inference_metaform_documentation.md) | All three explanations together, in their supplied order. |

Start with the full explanation for the narrative, or the specification
introduction for a shorter overview. The technical account develops the
mechanisms in more detail.

[Return to the project README](../../README.md)

```

### **`metaform/docs/primer/inference_metaform_documentation.md`**

````markdown
# Inference Metaform — Documentation Set

Three standalone versions: full explanation, specification introduction, and technical account.

---

# Inference Metaform
## Full explanation: previously performed inference, reusable meaning, and higher-order work

### What the system does

**The Inference Metaform performs and represents a portion of the reasoning required for subsequent work in advance. Reusing that inferred semantic understanding reduces the prerequisite reasoning each downstream operation must reconstruct, reserving more of its effective reasoning depth for higher-order work.**

The preparation is substantive inference. It develops understanding of what an Element is, what its dependencies mean, how it is realized through its Encounters, what receives its effects, what purposes those relationships serve, and what follows from relevant perspectives. That understanding is represented for reuse rather than being reconstructed entirely within every implementation, review, diagnosis, or design task.

The contextual and latent forms develop this understanding from different relational orientations. A knowledge graph of knowledge graphs represents it beyond the immediate working context. Later prompts operate through that semantic structure, allowing relatively compact instructions to engage highly specific, previously inferred meaning.

The fundamental subject is **semantics: what things are and what their relationships mean**. The system treats these relationships as literal semantics with mathematical definitions. The namespace, graph, prompts, and orchestration make those semantics available to computation and inference. They do not substitute for the semantic definitions themselves.

### Why local reasoning can become limiting

An agent working inside a project may need to reconstruct behavior, understand data structures, follow dependencies, interpret historical decisions, and resolve immediate implementation problems—all while attempting the requested change. Each activity can be necessary, but more local reasoning does not necessarily become higher-order reasoning about the system.

For example, an attempt may repeatedly examine how to accommodate a difficulty within the existing implementation without examining whether that difficulty is required by the function at all. The current realization can become the implicit definition of the thing being changed.

This is the contextual narrowing the Metaform addresses. Existing architecture, terminology, language, dependencies, and prior decisions influence which questions become apparent. A capable agent can reason coherently within that framing while overlooking a relevant possibility outside it.

Supplying more project material is not the same as resolving those relationships. Research on long-context language models has also shown that information being present does not guarantee its effective use: the position of relevant information affected performance in the tasks studied. That result supports the distinction between available information and usable understanding; it does not independently establish the Metaform's bias-reduction mechanism.[1]

The Metaform changes the starting point. An agent can examine a local difficulty through already-inferred functional, receiving, and purpose relationships instead of reconstructing all of them during the same attempt. This makes it possible to ask whether the obstacle belongs to the function or to its current realization while retaining the broader project meaning.

### The contextual and latent forms

Preparation begins in the actual repository, project, or implementation plan. The Native Expert examines the project to identify its Defining Element. It investigates functions, behavior, data structures, dependencies, receiving relationships, purposes, implementation Encounters, and other materially present semantics. For a plan, the subject is the proposed realization rather than an assumed existing implementation. Element descriptions express the functional Types the code uses or realizes, whether locally implemented or framework-supplied; they do not describe source code or written functions. Those Type descriptions orient the expertise used in later inference.

This produces the **Contextual Metaform**: how the project understands and realizes its Elements. Its detailed local knowledge is valuable. Its immersion in the project's own relationships also makes contextual bias and blind spots a central concern.

The Latent Expert receives the project-derived Artifact Types **individually, without the project's joins and without the project's Operative Purpose**. It does not receive the contextual graph and merely elaborate its existing arrangement. Instead, it examines each Element through learned type knowledge and develops its own dependencies, relationships, requirements, purposes, and other relevant structure.

This produces the **Latent Metaform**: how each Element is understood from its type without the project's relational framing supplying the answer. It is project-decontextualized, not absolutely free of the model's learned biases.

The Contextual Metaform and Latent Metaform remain complete, independent graphs. They are not merged, averaged, or rewritten into a third semantic graph. Both remain directly viewable and observable, including through MCP. A difference can reveal an overlooked dependency, a deliberate specialization, a different realization of the same function, or an inappropriate generalization. Those differences remain material for subsequent inference.

A separate shape-similarity layer shows structural agreement and divergence between the two graphs. It contains no copied semantic payload from either source graph; it records only structural correspondence and provenance references. Shape membership uses two bits:

| Value | Meaning |
|---|---|
| `01` | Structure present in the Contextual Metaform only |
| `10` | Structure present in the Latent Metaform only |
| `11` | The same nodes and join structure are present in both |

These values do not encode confidence, correctness, precedence, or semantic reconciliation. When both source graphs contain the same nodes and a join between them, the similarity layer can represent that structural agreement as `11`. If the source join contents differ, both source joins remain intact in their respective graphs and retain their own provenance; the similarity layer does not collapse, copy, or reconcile their contents.

The relationship between these forms and amortization is direct: **the system performs the work of developing differently oriented understanding, then makes that work reusable**. Blind-spot analysis and inference amortization are therefore connected mechanisms, not unrelated benefits.

### Elements, types, and perspectival meaning

Everything under examination can be treated as an **Element**. An **Artifact Type** supplies the semantic structural frame for the Element currently being examined.

The dotted namespace participates in that interpretation. In `code.utility.disk`, the meanings of `code`, `code.utility`, and `code.utility.disk` each contribute type structure. They are not merely folder levels or labels attached after analysis.

Names and descriptions provide concise, basic, unambiguous lexical handles. They help refer to an Element, but its identity is not established by string equality. Type and relationships carry the semantics.

The principal perspectival relationship discussed here combines:

| Dimension | Meaning |
|---|---|
| **Encounter Function** | How |
| **Receiving Entity** | Who or what |
| **Operative Purpose** | Why |

Together, these orient interpretation toward how something operates or is encountered, what receives it, and why that relationship exists. They are not three independent annotations to be read separately.

A Receiving Entity can be a person, system, subsystem, process, component, or another entity occupying that role at the selected resolution. Receiving relationships can continue across resolutions, with a distinct purpose at each relationship. A function serving a subsystem, a subsystem serving a node, and a node serving an operator need not share one undifferentiated purpose.

This preserves the relationship between local work and broader meaning without replacing every local purpose with an ultimate mission statement. Other represented perspectives can also participate; the three dimensions are not a ceiling on the semantic structure.

### Encounter changes inference through the type structure

**Function** concerns operative capability. **Encounter** concerns the form through which something is expressed, experienced, or encountered. Programming language is therefore materially significant to code reasoning.

Suppose `code.c` is joined as an Encounter at `code.utility.disk`. The functional type remains `code.utility.disk`; the language is not flattened into `code.utility.disk.c`.

The Encounter propagates transitively backward through the functional type ancestry:

```text
code.utility.disk → code.utility → code
```

The Encounter is available when reasoning at broader ancestor types. From its attachment point, it conditions inference through the functional descendants of that branch. Backward visibility does not cause an Encounter to fan back down unrelated sibling branches.

This is more than adding C-specific advice to one component. The Encounter changes how the relevant functional structure is understood: realization of functions, data representation, interfaces, dependencies, memory semantics, error behavior, operating-system interaction, and other relevant consequences. Those consequences can themselves be examined through Receiving Entity, Operative Purpose, and other represented perspectives.

In a mixed-language project, language joins occur where the languages actually occur. The graph preserves that composition while allowing the consequences of each Encounter to be reasoned through the type structure.

The dotted namespace is a strict typology: every prefix must itself express a valid Function or Encounter type. Encoding alone does not qualify as a type; an encoding name may appear where the path is actually expressing a Function, such as an encoder. Thus `document.html` fails when HTML is used only as document encoding, while `code.html` can qualify as a language Encounter and `code.encoder.jpg` can qualify as an encoding Function.

### A knowledge graph of knowledge graphs

The repository's semantic understanding is represented in a **knowledge graph of knowledge graphs**, using reified knowledge hypergraph semantics.

A relationship can itself be represented as something inference examines. Rather than recording only that one component depends on another, the represented relationship can include the participants' roles, the purpose being satisfied, the Receiving Entity, conditions, evidence, procedures, or other meaningful participants.

This matters because the reason for a dependency may be central to a change. Knowing that two Elements are connected is not equivalent to understanding what one requires from the other or why that requirement exists.

Each part of the Metaform can potentially resolve knowledge through any relevant perspective represented in the graph. Local work is therefore not confined to what an agent has reconstructed from the current code fragment. Its meaning can be examined through other functions, receiving relationships, Encounters, and project-wide purposes.

The graph makes previously inferred understanding available. **It does not replace inference with stored answers.** Subsequent operations still reason through the represented relationships and can derive further understanding from them.

### What changes about prompting

The prompt and the Metaform are separately reusable resources. A good prompt expresses an inference operation; the Metaform provides the semantic orientation through which that operation is interpreted.

Consequently, a prompt need not restate every dependency, implementation consequence, receiving relationship, and project-specific implication. Much of that inferential preparation has already happened. The prompt can direct what to compare, examine, derive, or reconsider through the available structure.

This differs in emphasis from established uses of *meta-prompting*. Zhang and colleagues describe meta-prompting around formal task structure and structured prompt transformations. Their work already gives structure a central role; meta-prompting is not simply elaborate role assignment.[2] Suzgun and Kalai describe another approach in which high-level instructions coordinate tailored expert queries and integrate their results.[3]

The defining commitment of the Inference Metaform is **reusable, previously inferred semantic understanding of the subject**, including the contextual and latent orientations, type structure, perspectival relationships, and Encounter propagation. Prompt construction or orchestration can operate through it, but neither is its fundamental definition.

The following are exploratory prompts, not a prescribed procedure. The first two are user-supplied possibilities that have not been tested here.

**Refactoring**

> Compare the proposed plan's shape with the Metaform. Infer where the refactoring becomes complex or difficult to follow. Consider representing that planning with a schema called `refactor_planning` as a layer in the knowledge metagraph.

This directs comparison between represented project meaning and a proposed realization. The possible schema layer would represent newly inferred planning knowledge; it is not an established required schema.

**Porting**

> Link `code.langA` and `code.langB`; work node by node to name and identify function-specific considerations and derive imperatives for addressing them.

This engages multiple Encounters through the functional structure. Their backward propagation and subsequent forward inference make the operation more substantial than collecting local language-conversion tips.

Two further exploratory possibilities illustrate other directions.

**Diagnosis**

> Examine the reported difficulty through the affected Functions, Receiving Entities, and Operative Purposes. Infer which difficulties follow from the functions themselves and which follow from their current realization.

**Foresight**

> Examine differences between contextual and latent relationships through the purposes of their Receiving Entities. Infer which differences suggest useful capabilities that the current realization has not developed.

These prompts ask inference to operate through relationships. They are not generic requests with Metaform terminology added. They also do not define a closed set of operations: implementation, review, decomposition, synthesis, testing, ideation, and other work can engage the same semantic structure differently.

### Protecting type rather than frozen implementation

A content-level frozen core preserves identity by preserving some part of the artifact. The Metaform approach instead places the invariant in semantic relations, allowing the realization to change without requiring arbitrary implementation content to remain untouched.

For an Artifact Type `T`, the formal identity is the exact set:

`C(T) = {(rᵢ ∧ pᵢ ∧ e)}`

Each conjunction binds a Receiving Entity `rᵢ`—the who or what receiving the effect; its Operative Purpose `pᵢ`—the why owned by that Receiving Entity; and the Type's single Encounter Function `e`—the how through which the effect is realized or encountered.

The important distinction is between preserving the thing's identity and preserving its present construction. A realization can change substantially while retaining its identity-defining semantic relationship. An Artifact Type has one Encounter Function at the represented resolution. A materially different Encounter makes a different Type or variant, represented through a further typological distinction rather than by adding a second EF to the same Type.

Mutation changes the realization while preserving the relevant semantic identity. Transformation changes what the thing is in that semantic sense.

For refactoring, the prepared understanding allows the agent to examine a different structure without treating the existing structure as the definition of the subsystem. For porting, the contextual view describes the current realization, while a target Encounter can orient how the function is realized differently. The objective is preservation of semantic function and receiving-purpose relationships, not mechanical translation of syntax.

**The system removes the need for the core to be a thing. The invariant becomes a relation.**

`C(T)` is exact as a semantic definition. It is not a lower bound, partial signature, similarity measure, confidence score, or candidate identity projection. The identity definition is semantic guidance for reasoning about the Type; it does not itself prescribe an approval gate, lifecycle, or runtime check.

### Why previously performed inference can support deeper work

The AI-side account concerns **effective inferential depth**: how much subsequent reasoning can build on an already-developed understanding. It does not increase the model's physical layers, parameters, context window, or literal compute capacity.

There is relevant precedent for distinguishing what a model knows from what a particular reasoning arrangement elicits. Chain-of-thought prompting research showed that intermediate reasoning demonstrations could improve performance on the studied reasoning tasks.[4] Least-to-most prompting explicitly used answers to earlier subproblems to support later ones.[5] SELF-DISCOVER developed reasoning structures before applying them to task instances.[6]

These studies support the plausibility of arranging prior reasoning to assist later reasoning. They are not measurements of the Inference Metaform or proof of its particular semantics.

Here, the proposed causal mechanism is specific. Preparation has already inferred relationships that would otherwise be prerequisites inside the task. Subsequent inference can start from those relationships, examine their consequences, compare realizations, or follow their effects through other perspectives. Its starting understanding is more developed.

An agent implementing a change can therefore work on how alternative realizations satisfy the represented function, rather than spending the entire attempt determining what that function means while changing it. The graph-wide relationships also allow local problems to remain connected to broader meaning as new obstacles appear.

The intended reductions follow from that mechanism. Repeated semantic reconstruction is reduced by reuse. Contextual omissions can become visible through the retained latent view. Unsupported gap filling can be reduced where relevant relationships have already been inferred and represented. Alignment can improve because effects are interpreted through their Receiving Entities and Operative Purposes rather than only through nearby code.

Reproducibility likewise concerns reuse of the semantic orientation, not identical wording or one predetermined solution. Different operations can reason from the same prepared meaning while producing different, appropriate realizations or conclusions.

The broader possibility is not limited to coding. Wherever the system represents Elements, types, Encounters, purposes, and receiving relationships, the same principle can support work across different artifact kinds. This is a capability proposition grounded in the semantic mechanisms, not a claim that every application has already been demonstrated.

### Development status

The supplied conversation is an **early proof of behavior during development**. Within a worked scenario, the agent used the described perspectives to produce contextual and latent analysis, element-specific development imperatives, and foresight, culminating in a storage-utility work report.

The important observation is that different instructions could engage the prepared semantic understanding and produce specific reasoning. The report is one result of that use—not the definition of the Metaform and not its canonical workflow.

The demonstration does not quantify reasoning gains, establish general superiority in refactoring or porting, or demonstrate elimination of hallucination. Those are distinct from the mechanism it illustrates: **perform part of the required inference beforehand, preserve its semantic results from different orientations, and let subsequent work reason through that understanding rather than reconstructing it entirely afresh.**

---

## Research references

These references support the external AI comparisons, not the system's definitions or unmeasured performance claims. The system account follows the supplied semantics and development conversation.

[1] Nelson F. Liu et al. *Lost in the Middle: How Language Models Use Long Contexts*. Transactions of the Association for Computational Linguistics, 12:157–173, 2024. DOI: 10.1162/tacl_a_00638.

[2] Yifan Zhang, Yang Yuan, and Andrew Chi-Chih Yao. *Meta Prompting for AI Systems*. arXiv:2311.11482, version 10, 2026.

[3] Mirac Suzgun and Adam Tauman Kalai. *Meta-Prompting: Enhancing Language Models with Task-Agnostic Scaffolding*. arXiv:2401.12954, 2024.

[4] Jason Wei et al. *Chain-of-Thought Prompting Elicits Reasoning in Large Language Models*. arXiv:2201.11903, 2022.

[5] Denny Zhou et al. *Least-to-Most Prompting Enables Complex Reasoning in Large Language Models*. ICLR, 2023. arXiv:2205.10625.

[6] Pei Zhou et al. *Self-Discover: Large Language Models Self-Compose Reasoning Structures*. arXiv:2402.03620, 2024.


---

# Inference Metaform
## Specification introduction

The Inference Metaform performs part of the semantic inference required for subsequent work in advance and represents the resulting understanding for reuse. This preparation establishes what an Element is, what its dependencies mean, how Encounters affect its realization, what receives its effects, what purposes those relationships serve, and what follows from relevant perspectives.

Reusing this understanding reduces the prerequisite reasoning that each downstream operation must reconstruct. The intended result is more effective inferential depth available for implementation, refactoring, porting, diagnosis, design, foresight, and other higher-order work. This concerns the starting point and use of task reasoning, not an increase in the model's physical capacity.

The system is fundamentally semantic. Its graph, namespace, prompts, and orchestration implement and expose semantic relationships rather than defining meaning through their incidental representations. Everything under examination can be treated as an Element, with Artifact Type supplying its semantic structural frame. Each prefix of a type path, such as `code.utility.disk`, is itself a promptable Artifact Type. A prefix qualifies through Function or Encounter rather than domain/class filler. Encoding alone does not qualify as a type; an encoding name may appear where the path expresses a Function, such as an encoder.

Preparation begins with deep contextual analysis of the actual project, repository, or implementation plan. The resulting Contextual Metaform represents functions, behavior, data structures, dependencies, Encounters, purposes, receiving relationships, and other materially present semantics. This contextual understanding is valuable but can carry blind spots arising from the project's architecture, terminology, assumptions, and history.

The Latent Expert examines project-derived Artifact Types individually, without the project's joins and without its Operative Purposes. It constructs its own relevant relationships from learned type knowledge. The resulting Latent Metaform provides a project-decontextualized perspective. The Contextual Metaform and Latent Metaform remain complete, independent graphs, directly viewable and observable, including through MCP. A separate shape-similarity layer contains only structural correspondence and provenance references, with no copied semantic payload. It records `01` for structure present contextually only, `10` for structure present latently only, and `11` for the same nodes and join structure present in both. These values do not encode confidence, correctness, precedence, or semantic reconciliation. If source join contents differ, both source joins remain intact in their respective graphs with their own provenance.

The semantic structure is represented in a knowledge graph of knowledge graphs using reified knowledge hypergraph semantics. Relationships can themselves be examined, with their roles, purposes, receivers, conditions, evidence, procedures, and other meaningful participants preserved. Local work can consequently be interpreted through project-wide relationships and other relevant perspectives rather than only through an agent's immediate reconstruction of nearby code.

The principal perspectival relationship combines Encounter Function—how; Receiving Entity—who or what; and Operative Purpose—why. These relationships operate at the selected resolution. A subsystem and its external receiver can have distinct receiving-purpose relationships without collapsing them into one mission-level purpose.

Encounters affect inference through the type structure. A language Encounter such as `code.c`, joined at `code.utility.disk`, is available when reasoning at broader ancestor types `code.utility` and `code`. From its attachment point, the Encounter conditions inference through the functional descendants of that branch. Backward visibility does not cause an Encounter to fan back down unrelated sibling branches. Its consequences can be resolved against Receiving Entity, Operative Purpose, and other represented perspectives.

Prompts and Metaforms are separately reusable. A prompt specifies an operation through the semantic structure; the Metaform makes previously inferred meaning available to that operation. Compact prompts can therefore engage project-specific implications without restating all of them. No particular reconciliation, engineering, foresight, or other prompt sequence defines the Metaform procedure.

Identity preservation concerns semantic relations rather than frozen implementation content. For an Artifact Type `T`, the formal identity is the exact set `C(T) = {(rᵢ ∧ pᵢ ∧ e)}`: each conjunction binds a Receiving Entity `rᵢ`, its Operative Purpose `pᵢ`, and the Type's single Encounter Function `e`. A materially different Encounter makes a different Type or variant, represented through a further typological distinction rather than by adding a second EF to the same Type. A realization may mutate substantially while its identity-defining relation remains invariant. This supports examining different refactorings or target-language realizations without making the current implementation the definition of the Type. The identity definition is semantic guidance for reasoning about the Type; it does not itself prescribe an approval gate, lifecycle, or runtime check.

The development demonstration provides an early proof of behavior, not quantified performance claims. The central architectural proposition is that previously performed inference, retained contextual and latent perspectives, and graph-wide semantic relationships together allow later work to reason from a more developed understanding rather than rebuilding that understanding within every attempt.


---

# Inference Metaform
## Technical account: semantic construction, propagation, identity, and inference reuse

### 1. Semantic basis and inferential role

The Inference Metaform represents previously performed semantic inference for use by subsequent operations. The reusable result is not limited to retrieved facts, summaries, or completed task answers. It includes inferred type understanding, dependency meaning, Encounter consequences, receiving relationships, purposes, and their implications across relevant perspectives.

The technical claim is that task execution can begin from this developed understanding. Reducing reconstruction of those prerequisites reserves more effective inferential depth for reasoning about consequences, alternative realizations, and higher-order changes. This is a causal claim about the arrangement and reuse of inference, not a numerical resource equation or a modification of the model's physical architecture.

Elements, type relations, joins, perspectives, and identity relations have literal semantic meanings and mathematical definitions. Graph storage, namespace strings, and natural-language prompts are representations and mechanisms operating through those meanings. Definitions not provided in the supplied material remain unspecified in this account.

### 2. Contextual construction and project-decontextualized inference

The Native Expert constructs the Contextual Metaform by examining the actual project or plan to identify its Defining Element. In code, this includes functional behavior, data structures, implementation Encounters, dependencies, receiving relationships, and purposes, rather than only lexical or module-level structure.

Contextual relational bias is central to the construction. Existing relationships can make one realization appear intrinsic to a function, or make a locally established dependency appear exhaustive. The contextual view records the project's understanding while the second perspective allows that understanding to be examined differently.

For latent analysis, the project-derived Artifact Types are supplied individually, with the project's joins and Operative Purpose absent from that input. The Latent Expert infers each Element's relevant dependencies, requirements, relationships, purposes, and other structure from learned type knowledge. The resulting Latent Metaform contains its own joins and purposes; removing the project's joins from the input does not remove relational inference from the latent process.

The separation concerns the project relational framing. It neither assumes a bias-free model nor discards the contextual understanding. The Contextual Metaform and Latent Metaform remain complete, independent graphs. They are not merged, averaged, or rewritten into a third semantic graph. Both remain directly viewable and observable, including through MCP.

### 3. Provenance semantics

A separate shape-similarity layer shows structural agreement and divergence between the two graphs. It contains no copied semantic payload from either source graph; it records only structural correspondence and provenance references. Shape membership is:

| Contextual structural presence | Latent structural presence | Representation |
|---|---|---|
| Present | Absent | `01` |
| Absent | Present | `10` |
| Present | Present | `11` |

When both source graphs contain the same nodes and a join between them, the similarity layer can represent that structural agreement as `11`. If the source join contents differ, both source joins remain intact in their respective graphs and retain their own provenance; the similarity layer does not collapse, copy, or reconcile their contents.

These values do not encode confidence, correctness, precedence, or semantic reconciliation. Matching lexical strings is not the definition of Artifact Type identity. This account does not supply a new correspondence algorithm.

### 4. Type structure, lexicalization, and operative characteristics

An Artifact Type supplies a semantic structural frame for the Element under examination. In the established example, each of the following has type meaning:

```text
code
code.utility
code.utility.disk
```

The path is therefore part of inference, not merely a storage address. Concise names and descriptions are lexical handles for semantic Elements. Natural-language instructions can lexicalize an operation through that structure without becoming the primary definition of its meaning.

Function denotes operative capability. Encounter denotes the form through which something is expressed, experienced, or encountered. A mixed-language project represents language Encounters where they occur rather than replacing the functional type with a language-suffixed path.

The dotted namespace is a strict typology: every prefix must itself express a valid Function or Encounter type. Encoding alone does not qualify as a type; an encoding name may appear where the path is actually expressing a Function, such as an encoder. Thus `document.html` fails when HTML is used only as document encoding, while `code.html` can qualify as a language Encounter and `code.encoder.jpg` can qualify as an encoding Function.

### 5. Encounter propagation and perspectival resolution

With `code.c` joined at `code.utility.disk`, the supplied backward propagation is:

```text
code.utility.disk → code.utility → code
```

This is backward visibility through functional type ancestry: the Encounter is available when reasoning at broader ancestor types. Forward application conditions inference from the attachment point through the functional descendants of that branch. Backward visibility does not cause an Encounter to fan back down unrelated sibling branches. Composition rules for nested or overlapping Encounters remain open.

The operation is not equivalent to annotating the attachment point with language advice. Its consequences can affect realization of functions, data representations, interfaces, dependencies, memory semantics, error behavior, and operating-system interactions. Those consequences can then be examined through other perspectives represented in the graph.

Every part of the Metaform can potentially resolve knowledge from any relevant represented perspective. No fixed traversal order through the principal perspectives is implied by this statement.

The perspectival dimensions and propagation concern semantic operations with intended literal mathematical definitions. The supplied account establishes the roles, their interaction, and the propagation direction. It does not specify numerical coordinates or a vector-space algebra for these inference orientations, so no such formalization is assigned here.

### 6. Tripartite relation and semantic identity

For an Artifact Type `T`, the formal identity is the exact set:

`C(T) = {(rᵢ ∧ pᵢ ∧ e)}`

Each conjunction binds a Receiving Entity `rᵢ`, its Operative Purpose `pᵢ`, and the Type's single Encounter Function `e`.

Encounter Function supplies the how, Receiving Entity the who or what, and Operative Purpose the why. The conjunction is relational: the function is interpreted according to its receiver and the purpose of that relationship at the selected resolution.

Receiving entities can themselves participate in further receiving relationships. Each relationship can have its own Operative Purpose. This recursive structure preserves intermediate meanings rather than substituting one ultimate purpose for all local relations.

`C(T)` is exact as a semantic definition. It is not a lower bound, partial signature, similarity measure, confidence score, or candidate identity projection. An Artifact Type has one Encounter Function at the represented resolution. A materially different Encounter makes a different Type or variant, represented through a further typological distinction rather than by adding a second EF to the same Type.

The intended mutation/transformation distinction uses semantic identity. Mutation changes the realization while retaining its identity-defining relation. Transformation changes that identity. The invariant therefore need not be preserved artifact content: substantial restructuring or a different implementation Encounter need not require a frozen implementation core.

The identity definition is semantic guidance for reasoning about the Type; it does not itself prescribe an approval gate, lifecycle, or runtime check.

### 7. Knowledge graph of knowledge graphs

The semantic representation is a knowledge graph of knowledge graphs with reified knowledge hypergraph semantics. Relations are available as subjects of inference, not only as links between subjects.

A dependency's meaning can include the dependent function, the required capability, the purpose satisfied, a receiving role, conditions, evidence, procedures, and other meaningful participants. Reducing this to pairwise adjacency can omit precisely the information needed to distinguish alternative realizations.

Contextual and latent forms retain their own relationships within this representation. Other represented perspectives can be brought to bear on either view and on their agreement or divergence. The significance of the structure is its ability to make prior semantic inference available beyond the local working fragment while supporting further inference through that meaning.

Schema-backed layers can represent further inferred understanding. The proposed `refactor_planning` layer is an exploratory example of that possibility, not an established mandatory layer or a supplied schema definition.

### 8. Prompts as operations through represented semantics

A prompt specifies an inference operation through the available semantic structure. The Metaform supplies previously inferred meaning; the prompt directs the current work. Each can be reused independently.

The user-supplied refactoring example compares a plan's shape with the Metaform, examines where the refactoring becomes difficult to follow, and considers representing that planning through `refactor_planning`. The user-supplied porting example links `code.langA` and `code.langB` and examines functions node by node to derive considerations and imperatives. Both remain untested exploratory possibilities.

Their significance is structural engagement. The refactoring prompt examines a proposed realization against represented meaning. The porting prompt engages two Encounters through the ancestry-and-forward-inference mechanism. Neither defines a universal workflow or a closed operator list.

Refactoring can therefore examine alternatives to present organization without equating that organization with type identity. Porting can preserve semantic function and receiving-purpose relationships while deriving a destination realization through another Encounter. The previously performed inference supplies meaning from which to evaluate those alternatives.

### 9. Effective inferential depth and local narrowing

Without reusable preparation, a task may require reconstructing semantic prerequisites and solving the requested problem within the same attempt. With the Metaform, some prerequisites have already been inferred and represented. Subsequent inference can reason from them to further consequences rather than starting again with raw project material.

This advances the starting point of task reasoning. It also changes what comparisons are available: whether a dependency is intrinsic to a function, whether a difficulty belongs to the current realization, or whether an alternative Encounter could realize the same receiving-purpose relationship differently.

The mechanism combines two effects. Contextual and latent construction supplies differently oriented understanding, including divergences that can expose local bias. Amortization reuses the inference that developed this understanding. Graph-wide relationships keep local work examinable through the larger semantic structure. None of these effects is adequately described as merely shortening a prompt.

Related research shows that earlier subproblem solutions can support later reasoning and that reasoning structures can be prepared for subsequent task use.[1][2] Those findings support the general plausibility of prior inferential preparation, not the effectiveness of this particular system.

Later work still performs inference through the represented understanding. Effective depth refers to reduced prerequisite reconstruction and a more developed basis for higher-order work, rather than a specified number of physical neural layers.

### 10. Formal and empirical status

The semantic contract establishes exact conjunction-set Type identity, one Encounter Function per Type, structural presence in the shape-similarity layer, complete independent Contextual and Latent Metaforms, and branch-scoped Encounter propagation. Composition rules for nested or overlapping Encounters remain open. These semantic definitions do not prescribe runtime identity checking or a correspondence algorithm.

The development conversation provides an early proof of behavior: the agent engaged the prepared perspectives through different instructions and produced specific analysis and imperatives. It does not establish quantified inference savings or elimination of hallucination.

The architectural claim remains precise: **upfront semantic inference is represented for reuse; the retained contextual and latent orientations support reasoning beyond project-local framing; and subsequent operations can devote more of their effective depth to higher-order work because some necessary understanding has already been developed.**

---

## Research references

These references support the limited external comparison in Section 9. The system semantics are supplied definitions, not deductions from these papers.

[1] Denny Zhou et al. *Least-to-Most Prompting Enables Complex Reasoning in Large Language Models*. ICLR, 2023. arXiv:2205.10625.

[2] Pei Zhou et al. *Self-Discover: Large Language Models Self-Compose Reasoning Structures*. arXiv:2402.03620, 2024.

````

### **`metaform/docs/primer/01_full_explanation.md`**

````markdown
# Inference Metaform
## Full explanation: previously performed inference, reusable meaning, and higher-order work

### What the system does

**The Inference Metaform performs and represents a portion of the reasoning required for subsequent work in advance. Reusing that inferred semantic understanding reduces the prerequisite reasoning each downstream operation must reconstruct, reserving more of its effective reasoning depth for higher-order work.**

The preparation is substantive inference. It develops understanding of what an Element is, what its dependencies mean, how it is realized through its Encounters, what receives its effects, what purposes those relationships serve, and what follows from relevant perspectives. That understanding is represented for reuse rather than being reconstructed entirely within every implementation, review, diagnosis, or design task.

The contextual and latent forms develop this understanding from different relational orientations. A knowledge graph of knowledge graphs represents it beyond the immediate working context. Later prompts operate through that semantic structure, allowing relatively compact instructions to engage highly specific, previously inferred meaning.

The fundamental subject is **semantics: what things are and what their relationships mean**. The system treats these relationships as literal semantics with mathematical definitions. The namespace, graph, prompts, and orchestration make those semantics available to computation and inference. They do not substitute for the semantic definitions themselves.

### Why local reasoning can become limiting

An agent working inside a project may need to reconstruct behavior, understand data structures, follow dependencies, interpret historical decisions, and resolve immediate implementation problems—all while attempting the requested change. Each activity can be necessary, but more local reasoning does not necessarily become higher-order reasoning about the system.

For example, an attempt may repeatedly examine how to accommodate a difficulty within the existing implementation without examining whether that difficulty is required by the function at all. The current realization can become the implicit definition of the thing being changed.

This is the contextual narrowing the Metaform addresses. Existing architecture, terminology, language, dependencies, and prior decisions influence which questions become apparent. A capable agent can reason coherently within that framing while overlooking a relevant possibility outside it.

Supplying more project material is not the same as resolving those relationships. Research on long-context language models has also shown that information being present does not guarantee its effective use: the position of relevant information affected performance in the tasks studied. That result supports the distinction between available information and usable understanding; it does not independently establish the Metaform's bias-reduction mechanism.[1]

The Metaform changes the starting point. An agent can examine a local difficulty through already-inferred functional, receiving, and purpose relationships instead of reconstructing all of them during the same attempt. This makes it possible to ask whether the obstacle belongs to the function or to its current realization while retaining the broader project meaning.

### The contextual and latent forms

Preparation begins in the actual repository, project, or implementation plan. The Native Expert examines the project to identify its Defining Element. It investigates functions, behavior, data structures, dependencies, receiving relationships, purposes, implementation Encounters, and other materially present semantics. For a plan, the subject is the proposed realization rather than an assumed existing implementation. Element descriptions express the functional Types the code uses or realizes, whether locally implemented or framework-supplied; they do not describe source code or written functions. Those Type descriptions orient the expertise used in later inference.

This produces the **Contextual Metaform**: how the project understands and realizes its Elements. Its detailed local knowledge is valuable. Its immersion in the project's own relationships also makes contextual bias and blind spots a central concern.

The Latent Expert receives the project-derived Artifact Types **individually, without the project's joins and without the project's Operative Purpose**. It does not receive the contextual graph and merely elaborate its existing arrangement. Instead, it examines each Element through learned type knowledge and develops its own dependencies, relationships, requirements, purposes, and other relevant structure.

This produces the **Latent Metaform**: how each Element is understood from its type without the project's relational framing supplying the answer. It is project-decontextualized, not absolutely free of the model's learned biases.

The Contextual Metaform and Latent Metaform remain complete, independent graphs. They are not merged, averaged, or rewritten into a third semantic graph. Both remain directly viewable and observable, including through MCP. A difference can reveal an overlooked dependency, a deliberate specialization, a different realization of the same function, or an inappropriate generalization. Those differences remain material for subsequent inference.

A separate shape-similarity layer shows structural agreement and divergence between the two graphs. It contains no copied semantic payload from either source graph; it records only structural correspondence and provenance references. Shape membership uses two bits:

| Value | Meaning |
|---|---|
| `01` | Structure present in the Contextual Metaform only |
| `10` | Structure present in the Latent Metaform only |
| `11` | The same nodes and join structure are present in both |

These values do not encode confidence, correctness, precedence, or semantic reconciliation. When both source graphs contain the same nodes and a join between them, the similarity layer can represent that structural agreement as `11`. If the source join contents differ, both source joins remain intact in their respective graphs and retain their own provenance; the similarity layer does not collapse, copy, or reconcile their contents.

The relationship between these forms and amortization is direct: **the system performs the work of developing differently oriented understanding, then makes that work reusable**. Blind-spot analysis and inference amortization are therefore connected mechanisms, not unrelated benefits.

### Elements, types, and perspectival meaning

Everything under examination can be treated as an **Element**. An **Artifact Type** supplies the semantic structural frame for the Element currently being examined.

The dotted namespace participates in that interpretation. In `code.utility.disk`, the meanings of `code`, `code.utility`, and `code.utility.disk` each contribute type structure. They are not merely folder levels or labels attached after analysis.

Names and descriptions provide concise, basic, unambiguous lexical handles. They help refer to an Element, but its identity is not established by string equality. Type and relationships carry the semantics.

The principal perspectival relationship discussed here combines:

| Dimension | Meaning |
|---|---|
| **Encounter Function** | How |
| **Receiving Entity** | Who or what |
| **Operative Purpose** | Why |

Together, these orient interpretation toward how something operates or is encountered, what receives it, and why that relationship exists. They are not three independent annotations to be read separately.

A Receiving Entity can be a person, system, subsystem, process, component, or another entity occupying that role at the selected resolution. Receiving relationships can continue across resolutions, with a distinct purpose at each relationship. A function serving a subsystem, a subsystem serving a node, and a node serving an operator need not share one undifferentiated purpose.

This preserves the relationship between local work and broader meaning without replacing every local purpose with an ultimate mission statement. Other represented perspectives can also participate; the three dimensions are not a ceiling on the semantic structure.

### Encounter changes inference through the type structure

**Function** concerns operative capability. **Encounter** concerns the form through which something is expressed, experienced, or encountered. Programming language is therefore materially significant to code reasoning.

Suppose `code.c` is joined as an Encounter at `code.utility.disk`. The functional type remains `code.utility.disk`; the language is not flattened into `code.utility.disk.c`.

The Encounter propagates transitively backward through the functional type ancestry:

```text
code.utility.disk → code.utility → code
```

The Encounter is available when reasoning at broader ancestor types. From its attachment point, it conditions inference through the functional descendants of that branch. Backward visibility does not cause an Encounter to fan back down unrelated sibling branches.

This is more than adding C-specific advice to one component. The Encounter changes how the relevant functional structure is understood: realization of functions, data representation, interfaces, dependencies, memory semantics, error behavior, operating-system interaction, and other relevant consequences. Those consequences can themselves be examined through Receiving Entity, Operative Purpose, and other represented perspectives.

In a mixed-language project, language joins occur where the languages actually occur. The graph preserves that composition while allowing the consequences of each Encounter to be reasoned through the type structure.

The dotted namespace is a strict typology: every prefix must itself express a valid Function or Encounter type. Encoding alone does not qualify as a type; an encoding name may appear where the path is actually expressing a Function, such as an encoder. Thus `document.html` fails when HTML is used only as document encoding, while `code.html` can qualify as a language Encounter and `code.encoder.jpg` can qualify as an encoding Function.

### A knowledge graph of knowledge graphs

The repository's semantic understanding is represented in a **knowledge graph of knowledge graphs**, using reified knowledge hypergraph semantics.

A relationship can itself be represented as something inference examines. Rather than recording only that one component depends on another, the represented relationship can include the participants' roles, the purpose being satisfied, the Receiving Entity, conditions, evidence, procedures, or other meaningful participants.

This matters because the reason for a dependency may be central to a change. Knowing that two Elements are connected is not equivalent to understanding what one requires from the other or why that requirement exists.

Each part of the Metaform can potentially resolve knowledge through any relevant perspective represented in the graph. Local work is therefore not confined to what an agent has reconstructed from the current code fragment. Its meaning can be examined through other functions, receiving relationships, Encounters, and project-wide purposes.

The graph makes previously inferred understanding available. **It does not replace inference with stored answers.** Subsequent operations still reason through the represented relationships and can derive further understanding from them.

### What changes about prompting

The prompt and the Metaform are separately reusable resources. A good prompt expresses an inference operation; the Metaform provides the semantic orientation through which that operation is interpreted.

Consequently, a prompt need not restate every dependency, implementation consequence, receiving relationship, and project-specific implication. Much of that inferential preparation has already happened. The prompt can direct what to compare, examine, derive, or reconsider through the available structure.

This differs in emphasis from established uses of *meta-prompting*. Zhang and colleagues describe meta-prompting around formal task structure and structured prompt transformations. Their work already gives structure a central role; meta-prompting is not simply elaborate role assignment.[2] Suzgun and Kalai describe another approach in which high-level instructions coordinate tailored expert queries and integrate their results.[3]

The defining commitment of the Inference Metaform is **reusable, previously inferred semantic understanding of the subject**, including the contextual and latent orientations, type structure, perspectival relationships, and Encounter propagation. Prompt construction or orchestration can operate through it, but neither is its fundamental definition.

The following are exploratory prompts, not a prescribed procedure. The first two are user-supplied possibilities that have not been tested here.

**Refactoring**

> Compare the proposed plan's shape with the Metaform. Infer where the refactoring becomes complex or difficult to follow. Consider representing that planning with a schema called `refactor_planning` as a layer in the knowledge metagraph.

This directs comparison between represented project meaning and a proposed realization. The possible schema layer would represent newly inferred planning knowledge; it is not an established required schema.

**Porting**

> Link `code.langA` and `code.langB`; work node by node to name and identify function-specific considerations and derive imperatives for addressing them.

This engages multiple Encounters through the functional structure. Their backward propagation and subsequent forward inference make the operation more substantial than collecting local language-conversion tips.

Two further exploratory possibilities illustrate other directions.

**Diagnosis**

> Examine the reported difficulty through the affected Functions, Receiving Entities, and Operative Purposes. Infer which difficulties follow from the functions themselves and which follow from their current realization.

**Foresight**

> Examine differences between contextual and latent relationships through the purposes of their Receiving Entities. Infer which differences suggest useful capabilities that the current realization has not developed.

These prompts ask inference to operate through relationships. They are not generic requests with Metaform terminology added. They also do not define a closed set of operations: implementation, review, decomposition, synthesis, testing, ideation, and other work can engage the same semantic structure differently.

### Protecting type rather than frozen implementation

A content-level frozen core preserves identity by preserving some part of the artifact. The Metaform approach instead places the invariant in semantic relations, allowing the realization to change without requiring arbitrary implementation content to remain untouched.

For an Artifact Type `T`, the formal identity is the exact set:

`C(T) = {(rᵢ ∧ pᵢ ∧ e)}`

Each conjunction binds a Receiving Entity `rᵢ`—the who or what receiving the effect; its Operative Purpose `pᵢ`—the why owned by that Receiving Entity; and the Type's single Encounter Function `e`—the how through which the effect is realized or encountered.

The important distinction is between preserving the thing's identity and preserving its present construction. A realization can change substantially while retaining its identity-defining semantic relationship. An Artifact Type has one Encounter Function at the represented resolution. A materially different Encounter makes a different Type or variant, represented through a further typological distinction rather than by adding a second EF to the same Type.

Mutation changes the realization while preserving the relevant semantic identity. Transformation changes what the thing is in that semantic sense.

For refactoring, the prepared understanding allows the agent to examine a different structure without treating the existing structure as the definition of the subsystem. For porting, the contextual view describes the current realization, while a target Encounter can orient how the function is realized differently. The objective is preservation of semantic function and receiving-purpose relationships, not mechanical translation of syntax.

**The system removes the need for the core to be a thing. The invariant becomes a relation.**

`C(T)` is exact as a semantic definition. It is not a lower bound, partial signature, similarity measure, confidence score, or candidate identity projection. The identity definition is semantic guidance for reasoning about the Type; it does not itself prescribe an approval gate, lifecycle, or runtime check.

### Why previously performed inference can support deeper work

The AI-side account concerns **effective inferential depth**: how much subsequent reasoning can build on an already-developed understanding. It does not increase the model's physical layers, parameters, context window, or literal compute capacity.

There is relevant precedent for distinguishing what a model knows from what a particular reasoning arrangement elicits. Chain-of-thought prompting research showed that intermediate reasoning demonstrations could improve performance on the studied reasoning tasks.[4] Least-to-most prompting explicitly used answers to earlier subproblems to support later ones.[5] SELF-DISCOVER developed reasoning structures before applying them to task instances.[6]

These studies support the plausibility of arranging prior reasoning to assist later reasoning. They are not measurements of the Inference Metaform or proof of its particular semantics.

Here, the proposed causal mechanism is specific. Preparation has already inferred relationships that would otherwise be prerequisites inside the task. Subsequent inference can start from those relationships, examine their consequences, compare realizations, or follow their effects through other perspectives. Its starting understanding is more developed.

An agent implementing a change can therefore work on how alternative realizations satisfy the represented function, rather than spending the entire attempt determining what that function means while changing it. The graph-wide relationships also allow local problems to remain connected to broader meaning as new obstacles appear.

The intended reductions follow from that mechanism. Repeated semantic reconstruction is reduced by reuse. Contextual omissions can become visible through the retained latent view. Unsupported gap filling can be reduced where relevant relationships have already been inferred and represented. Alignment can improve because effects are interpreted through their Receiving Entities and Operative Purposes rather than only through nearby code.

Reproducibility likewise concerns reuse of the semantic orientation, not identical wording or one predetermined solution. Different operations can reason from the same prepared meaning while producing different, appropriate realizations or conclusions.

The broader possibility is not limited to coding. Wherever the system represents Elements, types, Encounters, purposes, and receiving relationships, the same principle can support work across different artifact kinds. This is a capability proposition grounded in the semantic mechanisms, not a claim that every application has already been demonstrated.

### Development status

The supplied conversation is an **early proof of behavior during development**. Within a worked scenario, the agent used the described perspectives to produce contextual and latent analysis, element-specific development imperatives, and foresight, culminating in a storage-utility work report.

The important observation is that different instructions could engage the prepared semantic understanding and produce specific reasoning. The report is one result of that use—not the definition of the Metaform and not its canonical workflow.

The demonstration does not quantify reasoning gains, establish general superiority in refactoring or porting, or demonstrate elimination of hallucination. Those are distinct from the mechanism it illustrates: **perform part of the required inference beforehand, preserve its semantic results from different orientations, and let subsequent work reason through that understanding rather than reconstructing it entirely afresh.**

---

## Research references

These references support the external AI comparisons, not the system's definitions or unmeasured performance claims. The system account follows the supplied semantics and development conversation.

[1] Nelson F. Liu et al. *Lost in the Middle: How Language Models Use Long Contexts*. Transactions of the Association for Computational Linguistics, 12:157–173, 2024. DOI: 10.1162/tacl_a_00638.

[2] Yifan Zhang, Yang Yuan, and Andrew Chi-Chih Yao. *Meta Prompting for AI Systems*. arXiv:2311.11482, version 10, 2026.

[3] Mirac Suzgun and Adam Tauman Kalai. *Meta-Prompting: Enhancing Language Models with Task-Agnostic Scaffolding*. arXiv:2401.12954, 2024.

[4] Jason Wei et al. *Chain-of-Thought Prompting Elicits Reasoning in Large Language Models*. arXiv:2201.11903, 2022.

[5] Denny Zhou et al. *Least-to-Most Prompting Enables Complex Reasoning in Large Language Models*. ICLR, 2023. arXiv:2205.10625.

[6] Pei Zhou et al. *Self-Discover: Large Language Models Self-Compose Reasoning Structures*. arXiv:2402.03620, 2024.

````

### **`metaform/docs/primer/03_technical_account.md`**

````markdown
# Inference Metaform
## Technical account: semantic construction, propagation, identity, and inference reuse

### 1. Semantic basis and inferential role

The Inference Metaform represents previously performed semantic inference for use by subsequent operations. The reusable result is not limited to retrieved facts, summaries, or completed task answers. It includes inferred type understanding, dependency meaning, Encounter consequences, receiving relationships, purposes, and their implications across relevant perspectives.

The technical claim is that task execution can begin from this developed understanding. Reducing reconstruction of those prerequisites reserves more effective inferential depth for reasoning about consequences, alternative realizations, and higher-order changes. This is a causal claim about the arrangement and reuse of inference, not a numerical resource equation or a modification of the model's physical architecture.

Elements, type relations, joins, perspectives, and identity relations have literal semantic meanings and mathematical definitions. Graph storage, namespace strings, and natural-language prompts are representations and mechanisms operating through those meanings. Definitions not provided in the supplied material remain unspecified in this account.

### 2. Contextual construction and project-decontextualized inference

The Native Expert constructs the Contextual Metaform by examining the actual project or plan to identify its Defining Element. In code, this includes functional behavior, data structures, implementation Encounters, dependencies, receiving relationships, and purposes, rather than only lexical or module-level structure.

Contextual relational bias is central to the construction. Existing relationships can make one realization appear intrinsic to a function, or make a locally established dependency appear exhaustive. The contextual view records the project's understanding while the second perspective allows that understanding to be examined differently.

For latent analysis, the project-derived Artifact Types are supplied individually, with the project's joins and Operative Purpose absent from that input. The Latent Expert infers each Element's relevant dependencies, requirements, relationships, purposes, and other structure from learned type knowledge. The resulting Latent Metaform contains its own joins and purposes; removing the project's joins from the input does not remove relational inference from the latent process.

The separation concerns the project relational framing. It neither assumes a bias-free model nor discards the contextual understanding. The Contextual Metaform and Latent Metaform remain complete, independent graphs. They are not merged, averaged, or rewritten into a third semantic graph. Both remain directly viewable and observable, including through MCP.

### 3. Provenance semantics

A separate shape-similarity layer shows structural agreement and divergence between the two graphs. It contains no copied semantic payload from either source graph; it records only structural correspondence and provenance references. Shape membership is:

| Contextual structural presence | Latent structural presence | Representation |
|---|---|---|
| Present | Absent | `01` |
| Absent | Present | `10` |
| Present | Present | `11` |

When both source graphs contain the same nodes and a join between them, the similarity layer can represent that structural agreement as `11`. If the source join contents differ, both source joins remain intact in their respective graphs and retain their own provenance; the similarity layer does not collapse, copy, or reconcile their contents.

These values do not encode confidence, correctness, precedence, or semantic reconciliation. Matching lexical strings is not the definition of Artifact Type identity. This account does not supply a new correspondence algorithm.

### 4. Type structure, lexicalization, and operative characteristics

An Artifact Type supplies a semantic structural frame for the Element under examination. In the established example, each of the following has type meaning:

```text
code
code.utility
code.utility.disk
```

The path is therefore part of inference, not merely a storage address. Concise names and descriptions are lexical handles for semantic Elements. Natural-language instructions can lexicalize an operation through that structure without becoming the primary definition of its meaning.

Function denotes operative capability. Encounter denotes the form through which something is expressed, experienced, or encountered. A mixed-language project represents language Encounters where they occur rather than replacing the functional type with a language-suffixed path.

The dotted namespace is a strict typology: every prefix must itself express a valid Function or Encounter type. Encoding alone does not qualify as a type; an encoding name may appear where the path is actually expressing a Function, such as an encoder. Thus `document.html` fails when HTML is used only as document encoding, while `code.html` can qualify as a language Encounter and `code.encoder.jpg` can qualify as an encoding Function.

### 5. Encounter propagation and perspectival resolution

With `code.c` joined at `code.utility.disk`, the supplied backward propagation is:

```text
code.utility.disk → code.utility → code
```

This is backward visibility through functional type ancestry: the Encounter is available when reasoning at broader ancestor types. Forward application conditions inference from the attachment point through the functional descendants of that branch. Backward visibility does not cause an Encounter to fan back down unrelated sibling branches. Composition rules for nested or overlapping Encounters remain open.

The operation is not equivalent to annotating the attachment point with language advice. Its consequences can affect realization of functions, data representations, interfaces, dependencies, memory semantics, error behavior, and operating-system interactions. Those consequences can then be examined through other perspectives represented in the graph.

Every part of the Metaform can potentially resolve knowledge from any relevant represented perspective. No fixed traversal order through the principal perspectives is implied by this statement.

The perspectival dimensions and propagation concern semantic operations with intended literal mathematical definitions. The supplied account establishes the roles, their interaction, and the propagation direction. It does not specify numerical coordinates or a vector-space algebra for these inference orientations, so no such formalization is assigned here.

### 6. Tripartite relation and semantic identity

For an Artifact Type `T`, the formal identity is the exact set:

`C(T) = {(rᵢ ∧ pᵢ ∧ e)}`

Each conjunction binds a Receiving Entity `rᵢ`, its Operative Purpose `pᵢ`, and the Type's single Encounter Function `e`.

Encounter Function supplies the how, Receiving Entity the who or what, and Operative Purpose the why. The conjunction is relational: the function is interpreted according to its receiver and the purpose of that relationship at the selected resolution.

Receiving entities can themselves participate in further receiving relationships. Each relationship can have its own Operative Purpose. This recursive structure preserves intermediate meanings rather than substituting one ultimate purpose for all local relations.

`C(T)` is exact as a semantic definition. It is not a lower bound, partial signature, similarity measure, confidence score, or candidate identity projection. An Artifact Type has one Encounter Function at the represented resolution. A materially different Encounter makes a different Type or variant, represented through a further typological distinction rather than by adding a second EF to the same Type.

The intended mutation/transformation distinction uses semantic identity. Mutation changes the realization while retaining its identity-defining relation. Transformation changes that identity. The invariant therefore need not be preserved artifact content: substantial restructuring or a different implementation Encounter need not require a frozen implementation core.

The identity definition is semantic guidance for reasoning about the Type; it does not itself prescribe an approval gate, lifecycle, or runtime check.

### 7. Knowledge graph of knowledge graphs

The semantic representation is a knowledge graph of knowledge graphs with reified knowledge hypergraph semantics. Relations are available as subjects of inference, not only as links between subjects.

A dependency's meaning can include the dependent function, the required capability, the purpose satisfied, a receiving role, conditions, evidence, procedures, and other meaningful participants. Reducing this to pairwise adjacency can omit precisely the information needed to distinguish alternative realizations.

Contextual and latent forms retain their own relationships within this representation. Other represented perspectives can be brought to bear on either view and on their agreement or divergence. The significance of the structure is its ability to make prior semantic inference available beyond the local working fragment while supporting further inference through that meaning.

Schema-backed layers can represent further inferred understanding. The proposed `refactor_planning` layer is an exploratory example of that possibility, not an established mandatory layer or a supplied schema definition.

### 8. Prompts as operations through represented semantics

A prompt specifies an inference operation through the available semantic structure. The Metaform supplies previously inferred meaning; the prompt directs the current work. Each can be reused independently.

The user-supplied refactoring example compares a plan's shape with the Metaform, examines where the refactoring becomes difficult to follow, and considers representing that planning through `refactor_planning`. The user-supplied porting example links `code.langA` and `code.langB` and examines functions node by node to derive considerations and imperatives. Both remain untested exploratory possibilities.

Their significance is structural engagement. The refactoring prompt examines a proposed realization against represented meaning. The porting prompt engages two Encounters through the ancestry-and-forward-inference mechanism. Neither defines a universal workflow or a closed operator list.

Refactoring can therefore examine alternatives to present organization without equating that organization with type identity. Porting can preserve semantic function and receiving-purpose relationships while deriving a destination realization through another Encounter. The previously performed inference supplies meaning from which to evaluate those alternatives.

### 9. Effective inferential depth and local narrowing

Without reusable preparation, a task may require reconstructing semantic prerequisites and solving the requested problem within the same attempt. With the Metaform, some prerequisites have already been inferred and represented. Subsequent inference can reason from them to further consequences rather than starting again with raw project material.

This advances the starting point of task reasoning. It also changes what comparisons are available: whether a dependency is intrinsic to a function, whether a difficulty belongs to the current realization, or whether an alternative Encounter could realize the same receiving-purpose relationship differently.

The mechanism combines two effects. Contextual and latent construction supplies differently oriented understanding, including divergences that can expose local bias. Amortization reuses the inference that developed this understanding. Graph-wide relationships keep local work examinable through the larger semantic structure. None of these effects is adequately described as merely shortening a prompt.

Related research shows that earlier subproblem solutions can support later reasoning and that reasoning structures can be prepared for subsequent task use.[1][2] Those findings support the general plausibility of prior inferential preparation, not the effectiveness of this particular system.

Later work still performs inference through the represented understanding. Effective depth refers to reduced prerequisite reconstruction and a more developed basis for higher-order work, rather than a specified number of physical neural layers.

### 10. Formal and empirical status

The semantic contract establishes exact conjunction-set Type identity, one Encounter Function per Type, structural presence in the shape-similarity layer, complete independent Contextual and Latent Metaforms, and branch-scoped Encounter propagation. Composition rules for nested or overlapping Encounters remain open. These semantic definitions do not prescribe runtime identity checking or a correspondence algorithm.

The development conversation provides an early proof of behavior: the agent engaged the prepared perspectives through different instructions and produced specific analysis and imperatives. It does not establish quantified inference savings or elimination of hallucination.

The architectural claim remains precise: **upfront semantic inference is represented for reuse; the retained contextual and latent orientations support reasoning beyond project-local framing; and subsequent operations can devote more of their effective depth to higher-order work because some necessary understanding has already been developed.**

---

## Research references

These references support the limited external comparison in Section 9. The system semantics are supplied definitions, not deductions from these papers.

[1] Denny Zhou et al. *Least-to-Most Prompting Enables Complex Reasoning in Large Language Models*. ICLR, 2023. arXiv:2205.10625.

[2] Pei Zhou et al. *Self-Discover: Large Language Models Self-Compose Reasoning Structures*. arXiv:2402.03620, 2024.

````

