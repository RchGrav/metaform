# Metaform — historical consolidated product specification

> **Superseded September 16 account.** [REQUIREMENTS.md](../REQUIREMENTS.md)
> is the complete governing product contract. All requirement IDs, decisions,
> authority claims and acceptance language below belong to this historical
> consolidation; they impose no additional requirements. Current work follows
> [section 20](../REQUIREMENTS.md#20-remediation-instructions) and the
> [live remediation matrix](../REMEDIATION-MATRIX.md).

The body preserves the earlier product explanation and source references for
inspection. Its old conflicts and engineering choices do not block remediation.
Source keys refer to the dated [source register](SOURCES.md); its accompanying
[decision ledger](DECISIONS-AND-CONFLICTS.md) is likewise historical.

## 1. Purpose, people and outcome

**P-01 — Context engineering and inference amortization.** Metaform records the
functional understanding of a particular project so that later agents and
workflows can reason from it without reconstructing the same understanding on
every action. That investment belongs to the project; it is not a claim that one
inference applies to every future project forever. The intended benefit is less
orientation effort and more reasoning available for the actual task. No numerical
performance or intelligence improvement is asserted by this specification.

**P-02 — Artifact independence.** The artifact can be a codebase, a project within a
multi-project repository, a collection of photographs, a contract, a story, a plan
for a project, or another artifact. A plan can describe the artifact to onboard;
that does not automatically make the plan document itself the intake subject.
Metaform must retain each selected project's identity and source boundaries.

**P-03 — Intended users.** People inspect and refine project understanding, author
workflows and select knowledge; orchestrators assign work and assemble context;
working agents retrieve assignments and contribute results; module authors extend
capabilities through the same public contract as shipped modules. This is a role
map, not a proposed account/permission system.

**P-04 — Success.** A compact authored operation can address project-specific
functions, relationships and knowledge through recorded context; its result can be
traced to the actual prompt, inputs and answer. People can inspect and revise that
understanding without rebuilding the system. Running commands and passing tests
alone do not prove semantic correctness.

Sources: S01; S02 capabilities 1–16 and Why; S03; S04.

## 2. Functional semantics and vocabulary

**SEM-01 — Type identity.** Preserve the conjunction-set definition:

```text
C(T) = { (r_i AND p_i AND e) }
```

`C(T)` is an exact set, not a lower bound, partial signature or similarity measure.
Each Receiving Entity `r_i` is bound to its own Operative Purpose `p_i` and the
Type's single Encounter Function `e`. RE is the who/what that receives; OP is that
receiver's why; EF describes how the Type satisfies it. A join's OP cannot be
replaced by the project's ultimate purpose. This is a semantic definition, not a
requirement to build a numerical identity test or an inference rejection gate.
**Signal** is the way an OP is satisfied; it does not add another role taxonomy.

**SEM-02 — Type and realization.** A Type has one EF at its represented resolution.
A materially different Encounter calls for a different typological distinction or
variant. Preserve the universal Type Description separately from what was learned
about the actual artifact. Semantic identity permits different implementations;
it does not freeze the current code or implementation architecture.

**SEM-03 — Defining Element.** The DE is the representative composite function
whose loss would leave the artifact unable to remain the same Type. It is not
merely a code entrypoint. Its defining function excludes medium, encoding, genre
and style. Recursion examines the requirements and properties that satisfy the
receiving Element's OPs.

**SEM-04 — Exterior and external.** Exterior means outside the project; it can
receive from the artifact or provide an EF satisfying it. External means outside
the functionality being examined while still inside the repository. Ownership by
an organization is not the test. Whether the DE's exterior receiving purpose is
included in *shallow* intake is a review conflict, C02.

**SEM-05 — Roles and terms.** Preserve established semantic terms and authored
meaning. The sources use both hard dependency/property/supportive and
property/requirement with classification and softness, while intake uses DE/SE/NE
and TARGET. These are not interchangeable labels: Element roles, join roles and
executable dictionary-entry types are different dimensions. Their canonical mapping
is unresolved (C01); the draft does not silently rename them.

**SEM-06 — Parametric.** Tunables do not independently establish acceptance of a
transformation. Semantic sources reserve their names against namespace Elements;
current shallow intake says not to enumerate them. The storage/scope relationship
between those statements needs reconciliation (C06).

Sources: S02 §§1–5, 10; S03; S04; S05. Exact authored definitions remain in those
sources; this document is not a replacement runtime intake prompt.

## 3. Namespace objects and receiving-entity records

**OBJ-01 — Functional typology.** The namespace is organized by meaningful
functional Types and semantic specificity. It is not a fixed domain/class taxonomy.
Each prefix must carry meaning. Current bases are `code`, `document`, `asset`,
`data`, and `exterior`; `asset` supersedes `media`. Historical evidence retains its
original addresses and traceable mappings rather than being silently rewritten.

**OBJ-02 — Proper names.** Use the common universal singular proper noun, reuse the
most general suitable existing namespace position, and append the necessary
modifiers. Reverse the final declared number of namespace components to recover
the proper name. `code.engine.game` with name length 2 displays as Game Engine.
Reused components count toward that length. Names and Descriptions remain separate
semantic sources. Exterior retains its documented reverse-reading exception.
The [exact Name construction rule](../../docs/rulebook/element/name.md#concise-form)
remains authoritative over this summary. The separate Description rule is:

> Define the Type with the most basic universal statement that uses ancestral proper nouns in reverse namespace order in a semantically proper statement, without naming or defining its child Encounters or Functions. The Type's description remains universal; the actual Element's description carries its particular account.

Source: [Description construction](../../docs/rulebook/element/description.md#concise-form).

**OBJ-03 — Components and aliases.** Namespace components are alphanumeric and
period-separated; meaningful Type levels are not concatenated merely to avoid
underscores. Aliases preserve alternate names at the corresponding position for
lookup and duplicate avoidance. They do not globally reserve an isolated word.
Interpret a path by its meaning; language/encoding words are not a fixed blacklist.

**OBJ-04 — Object identity.** Every namespace object has its own record with
`namespace_address` at the top. This does not require one filesystem file per
object. System objects, imported workflows, prompts, context objects and artifact
intake data must be addressable. Concrete envelopes for each kind remain to be
completed without conflating Type definitions with artifact instances (C03/C04).

**OBJ-05 — Joins belong to the Receiving Entity.** A join resides in its Receiving
Entity's namespace record. It is not an independent namespace-object record.
Knowledge, provenance and automation can refer to that owned join through its
owner and local identity. The encoding of that owned-join reference remains open.

**OBJ-06 — Typed entries.** Join dictionaries can contain executable/logic entries,
including `type:layer_select` and `type:layer_select_mask`, and automation entries
for resolving context. Reading a memory or inspecting a record must not itself
execute an automation entry. These entries do not change RE/OP/EF semantics.

**OBJ-07 — Supplied RE structure.** The supplied JSON schema describes `ef`,
`name_length`, `aliases`, `joins`, and joins containing `op`, `relation`,
`observation`; `refs` is optional. Preserve these source fields. The outer namespace record,
XML mapping, `length` versus `name_length`, combined-entity references and executable
entry representation require an explicit mapping (C03/C04), not fabricated data.

Sources: S01; S02 §§5–6, 15; S04; S05; S06 §§8–10. D01/D02 settle the base rename
and ownership correction.

## 4. Intake and outside reasoning

**INT-01 — Intake is a workflow.** Intake must be an actual authored workflow
consumed and executed by the common workflow engine. A separate intake state
machine bearing a `workflow` label does not meet this requirement. Its module
supplies its prompts, structure and result mapping through the shared services.

**INT-02 — Authored procedure.** Preserve the current supplied intake procedure,
its semantic terms and response instructions. It recursively follows RE → OP → EF,
constructs a coarse functional account, and anneals discovered Elements after
understanding their relationships. Do not replace this with a top-down software
architecture summary or a census of files.

**INT-03 — Coarse and deeper accounts.** The initial shape is intentionally coarse,
minimal and extensible. Deeper understanding can be requested for an Element,
branch, join or bounded region. The supplied XML experiments include shallow,
combined deep, and expansion-from-an-existing-shallow-result variants; their mere
presence does not select one deep-intake execution design. Shallow exclusions,
exterior context and artifact-specific detail conflict across sources (C02).

**INT-04 — Combining and inactive addresses.** Discover the OPs and joins before
combining Elements. Combine them only when they can logically share a common join.
Preserve combined entities with exact namespace addresses/name lengths, active-voice
relations and atomic observations under the appropriate owned join. Absorbed `subtypes` retain full addresses as inactive
memory/reference positions; they do not inflate the active base shape. Their
requirements remain represented by the containing Type. Current DE/SE/NE output is
preserved as authored pending C01.

**INT-05 — Actual artifact support.** Preserve source and artifact context for
software and non-code intake, including binary/image content when it is the
artifact. Universal Type meaning and actual project understanding must remain
distinguishable. The precise place for project details in shallow records is C02.

**INT-06 — Native and Latent.** Native understanding is the project's Inference
Metaform. Latent reasoning receives the complete Native functional account,
including recorded descriptions, joins, REs and OPs, while remaining blind to the
repository implementation. It can agree, disagree or identify omissions; no forced
contradiction is required. It can be invoked after intake and during later work.

**INT-07 — Reports and corrections.** Outside findings attach as separately
attributed knowledge. A proposed missing Element does not become current structure
merely by appearing in a report. Applying a structural correction records the
prior and new meaning, reason, source evidence and a new foundation revision.
Keep the original account and report observable. Refinement retains established
identities and records how finer detail relates to them.

**INT-08 — Answer preservation.** The schema describes the requested structure.
Keep the actual answer and annotate interpretation or mapping issues; do not
invent semantic information or add answer-rejection/retry loops to make it pass.
The explicitly required assignment header is a separate routing requirement.
Authored workflow conditions remain as authored. Final XML submission versus
incremental object puts remains a delivery-design question (C05).

**INT-09 — History.** Older independent Native/Latent graphs and `01`/`10`/`11`
comparisons remain readable as historical evidence. Those bits express structural
presence by source, not confidence, truth or reconciliation. They do not mandate
two competing structural foundations for new intake.

Sources: S01; S02 §§2, 8, 10–11, 15; S03–S06; S10; S11.

## 5. Knowledge graph, layers and memory

**KG-01 — Layered knowledge.** The base Metaform maps the artifact by Element Types;
owned joins supply relationship detail. Further inference attaches as separately
identified knowledge layers at objects and owned joins. Each layer retains its
request, schema/recipe, generations, applicability, source dependencies and
provenance. Removing or regenerating one layer preserves other layers and the
foundation.

**KG-02 — Property propagation.** A property's effect has backward visibility
toward ancestors/the trunk and forward application from its attachment through its
functional descendants. Backward visibility does not spread it down unrelated
siblings. Bash attached to an installer and C++ attached to an engine can both be
visible at `code` without making the installer inherit C++. This is distinct from
layer-selection propagation.

**KG-03 — Selection defaults and order.** Each layer has a general-graph default
visibility flag. The project graph's initial `layer_select` is all ones. Every
object starts with `layer_select` all zeros and `layer_select_mask` all ones. The
project selector is not a field on the base Type. Traverse from trunk toward
leaves, applying the incoming mask before the object's own selection:

```text
effective_selection = (incoming_selection & layer_select_mask) | layer_select
```

The mask blocks incoming authority; the object's own selector, or a selector
farther toward the leaf, can select that layer again. For one layer:

| Position | Incoming | Mask | Local select | Effective |
| --- | --- | --- | --- | --- |
| Object A | 1 | 1 | 0 | 1 |
| Object B | 1 | 0 | 0 | 0 |
| Object C | 0 | 1 | 1 | 1 |

**KG-04 — Work context.** Workflows have their own layer selection and observe the
same object masks. The selected workflow or agent-facing module and its layer
context belong to the assigned nonce. Steps can carry layer-selection footers and
object indexes. Layer-to-bit encoding, interaction with default browsing flags,
step-versus-workflow selection and saved-view scope remain open (C07).
Generation itself also selects its input layers, including an intake-only context.
S09 recommends recording both requested and effective selection with exact input
revisions; retain that guidance's attribution when specifying generation recipes.

**KG-05 — Sources and visibility.** Hiding an object hides inference derived from
it and downstream dependent inference. Store the source dependency separately from
the location receiving generated knowledge: an attachment target is not necessarily
a prompt input. Retain hidden knowledge and provenance. The supplied guidance
explicitly records a further clarification that *any* directly used prompt-source
node becoming hidden hides its generated knowledge; this is attributed secondary
source evidence, not a newly invented rule. Granularity/view scope remains C07.

**KG-06 — Open-ended inference.** An authored instruction can operate over relevant
objects and joins using their Type context, linked properties, REs and OPs. For
example, attach `code.cpp.cxx23` and infer per-object/per-join best practices. The
old Knowledge Tool's rule that joins only supply context is not a restriction on
this newer general capability (D08/C08).

**KG-07 — Knowledge Tool recipe.** Preserve the documented recipe as a specific
feature to reconcile with the newer capability: preview exact questions without
inference; keep the user's instruction unchanged and append recorded context;
ask a reusable Type-base question and, where relevant, one whole property-qualified
composite question; avoid duplicate Element/Type questions and property powersets.
Record question-to-subject mappings and retain the requested answer lengths rather
than imposing a generic count. The exact migration of this recipe is C08.

**KG-08 — Memory.** Basic agent memory provides create, read, search, update and
delete operations in layers indexed by namespace objects and owned joins. Include
inactive and combined memory positions. Each delivered step identifies its memory
addresses. Memory follows project/assignment context, layer selection and
provenance, through CLI as well as any MCP/web adapter.

**KG-09 — Porting and temporary context.** Attaching `code.csharp.cpp.port` supplies
porting context; inference can add guidance, memory-management concerns, best
practices or other requested imperatives to relevant objects/joins. Independently
attach `code.csharp` when wanted. At completion, hide the porting object to detach
its dependent inference. Independently sourced C# knowledge follows its own
sources and selectors.

**KG-10 — Default guidance.** Earlier product sources call for Best Practices as a
default Knowledge Tool use after onboarding and periodic blind-spot analysis by
incoming agents. Preserve that onboarding requirement while reconciling its exact
recipe, cadence and relationship to coarse intake; no unstated automatic repeated
inference is introduced by this draft.

Sources: S01; S02 §§7–9, 11, 13, 15; S06 §§8–12; S09 (attributed guidance);
S10. D05–D08 and C07/C08 distinguish settled rules from open mapping.

## 6. Workflows, prompts and context authoring

**WF-01 — Preserve authored operations.** Import and specialize workflows without
changing their operative purpose, sequence, branches, loops, handoffs or interaction
points. Imported text stays substantially as authored. Lexicalization and adding
selected context are explicit operations, not permission to rewrite the procedure
or add generic output gates.

**WF-02 — Native format and serialization.** XML is the editable workflow/prompt
format; use ElementTree to convert XML to dictionaries, with XML/JSON round-trip
support. Preserve attributes, ordered and repeated children, mixed text/content,
embedded response schemas and object references. A semantic conversion from an
external workflow into the native grammar is different from deterministic
serialization of a native document. Literal import of one prompt is also distinct
from inference-based conversion into an executable multi-step workflow. Exact whitespace/comment fidelity and the
canonical grammar remain C09.

**WF-03 — Context as objects.** Prompts store variable/object references rather
than only pasted text. Namespace-backed proper nouns render by their real names.
An explicit lexicalization operation orients each step to the project by linking
its terms to appropriate namespace objects. It may add the requested layer's
imperatives. The GUI inserts resolved context objects and lets the user follow
them into graph knowledge and producing inference.

**WF-04 — Layer additions.** A workflow selects layers; a step may carry a selector
footer or index of objects referenced in its prompt. Selected imperative layers
append instructions to that step. Resolve these through the same masks and
provenance rules used by graph reads. C07 covers selection precedence still open.

**WF-05 — Deterministic assignment delivery.** The runtime combines the authored
prompt with resolved context and records exactly what it issued. The orchestrator
passes the nonce and instructs the agent to use Metaform; it does not paraphrase or
substitute the stored prompt during handoff. Shared execution handles actual step
progression and synchronization; an event bus alone is not a workflow engine.

**WF-06 — Prompt revisions and replay.** Preserve source prompt revision, variables,
resolved object revisions and rendered text. Single prompts and chains use the
same editor model. Editing a step creates a revision; replay can reuse recorded
prior answers and issue new assignments from the edited point. Never overwrite
what an earlier agent actually received. S02 §15 specifies seven prompt sections:
**Purpose, Core Concepts, Namespace Rules, Method, Goal, Constraints, Completion
Condition**. Preserve that structure when reconciling XML schemas.

The realignment archive attributes a further prompt-composition clarification to
Rich: supply focused role instructions and selected semantic context, with the
glossary available separately; do not automatically concatenate the entire glossary
into every prompt. Preserve this alongside complete Native delivery to the Latent
role: role-appropriate semantic guidance and the artifact account are distinct.
Source: S17, `00-review-clarifications.md` and `19-prompt-quality.md`.

**WF-07 — Interaction and continuity.** Authored user-question/user-response steps
must survive import and execution. Where the source asks for user approval or
feedback, wait for the actual user's response; a model must not supply it on the
user's behalf. Preserve explicit continuations, checkpoints,
step state, branch decisions, prior answers and artifacts so work can resume.
Multi-step delegated work uses its own workfolder/worktree; single-prompt operations
can work against the selected project without inventing a multi-step ceremony.

**WF-08 — Library and conversion evidence.** Preserve the authored workflow library
and source workflows as product assets. The delivered CLI/wheel catalog exposes
purpose, original source/revisions, required inputs, unresolved dependencies and a
usable start action. The converter receives the same packaged execution grammar
that authors can inspect. Historical repairs require demonstrable
conversion of the seven supplied workflow sources, source provenance and semantic
review, with actual representative execution. The library and that evidence are
not proof the fresh chassis has migrated workflow execution (see §13).

| Supplied source | Behavior to preserve |
| --- | --- |
| `metaprompt` | Initial topic question, clarification, optional specialist help, prompt production |
| `dual_agent` | Separate Dev/Eval assignments, user prerequisites, plan review and iterative slices |
| `multi_agent_orchestrator` | Analyst/Planner/Developer/Evaluator roles, authored approval and repetition |
| `orchestrator` | Bootstrap, architecture, document sharding, per-module review and persistent artifacts |
| `extractor` | Documentation task, target language, fresh artifact-only evaluator and feedback-driven reruns |
| `python_to_c` | Mixed examples/configuration, phased parallelism, shared context and authored deadline/failure behavior |
| `taskeengineplus` | Dynamic tasks/dependencies, ten roles, optional documentation and authored critique/requeue/retry behavior |

**WF-09 — Uploadable execution.** The workflow module prepares workflows for upload
and exposes complete execution through the executable wheel entrypoint. It uses
chassis data, packaging, assignments and execution. Workflow-specific preparation
and commands remain module-owned. Advanced remote command-and-control work packets
are a later module, not a prerequisite for this first migration.

**WF-10 — Source-derived execution behavior.** Keep specialist roles as separate
assignments with their required context and response routes. Preserve nested calls,
parallel dependencies, tool operations, shared files/evidence and continuations.
Literal examples, placeholders, output destinations and completion conditions stay
at their intended stage. Producing a prompt does not automatically execute the
task described by that generated prompt. Undefined external roles or schemas remain
visible dependencies; the converter does not invent their definitions. These are
source-specific workflow semantics, not blanket approval/retry rules.

Sources: S01; S02 §§9, 14–15; S06 §§11, 13; S10; S11; S12; S15; S16; S17.

## 7. Chassis and extension contract

**CH-01 — Independent chassis.** Build a complete, polished chassis as a product in
its own right. Use a microkernel/plugin architecture: the chassis owns concrete
shared services; features are executable external modules. Community and shipped
modules use the same contract. Removing one withdraws its contributions while the
chassis and unrelated modules remain usable.

**CH-02 — Public services.** Provide:

```python
from metaform import settings, event, cli, data
```

These resolve active chassis services and operation context. Imports do not create
a separate database/runtime for each module. The implemented `work`, `modules` and
`objects` surfaces extend these with assignments/jobs, catalog access and typed
objects. Their signatures are documented in S08; they are engineering contracts,
not a replacement for the product semantics in this document.

**CH-03 — Core ownership.** The chassis owns module lifecycle/registration,
settings, the event bus, contextual CLI/menu templates, work identities and
assignment lookup, shared execution boundaries, project-owned storage and
object-oriented provenance. Feature implementations contribute operations,
commands, parameters, help, settings, subscriptions, lifecycle hooks, native
workflow definitions and typed-entry handlers through that contract.

**CH-04 — Python modules.** A module can be a single `.py` file or a package folder
copied into the plugins folder. It embeds its declarations and help in Python.
A metadata manifest alone is not an executable plugin. No separate manifest is
required for the current drop-in model.

**CH-05 — Enabled state.** Use the exact plain-text file `plugins/disabled` listing
plugins that do not load. Absent entries are enabled. CLI/TUI controls operate on
that policy. Current engineering choice: entries name immediate `.py` filenames or
package-folder names, with resolved paths for explicitly loaded external modules;
comments/blank lines are preserved. Disabled modules are skipped before activation.

**CH-06 — Lifecycle and ownership.** Register commands/settings/subscriptions on
load and withdraw them on unload. Saved data, settings, glue and provenance remain
for inspection and later module return. Associate failures with the responsible
operation/module; one broken feature must not remove chassis administration.
Current modules are trusted executable Python; process sandboxing of community
code is not an implemented guarantee or an agreed new product feature.

**CH-07 — Sync and async.** Module operations and hooks can be synchronous,
asynchronous or both. Agent operations are asynchronous. Independent CLI/status
operations remain usable while an agent is running. Concurrent assignments retain
their own project, module, nonce, step and producing-operation context across sync
workers, async callbacks and events.

**CH-08 — Shared event bus.** Modules publish and subscribe through the same
chassis event service. Events identify publisher, project, assignment context,
provenance and affected record references. The current event examples keep result
payloads in managed records and pass their references; that is their engineering
contract, not a universal prohibition on event metadata.
Unloading removes subscriptions. Request publication can return before work ends;
a later response event delivers the result to the requester, with inspectable
identity and delivery/failure outcomes.

**CH-09 — Persistent work.** Jobs must survive the initiating CLI process ending
and expose status, results, errors, cancellation and process tracking. The current
engineering implementation uses one background host per global root with local RPC;
it is separate from the optional web service. Restart/interruption semantics and
specific state names are recorded in the API, not evidence of durable distributed
event replay or arbitrary resumable agent execution.

Sources: S01; S06 §§1–5; S07; S08. D03/D09/D10/D11.

## 8. Settings, help and contextual CLI/TUI

**UX-01 — Complete CLI.** Every functional operation has a CLI route independently
of web and MCP. Use Click. Modules own complete command definitions, arguments,
options, nested groups and help. The chassis dynamically builds the available
surface from active context and loaded contributions. Availability must agree
between help/listing and direct invocation.

**UX-02 — Embedded guidance.** Module Python contains its help and settings
sections, including purpose, defaults and usage. Present help at the point where a
user or agent needs to act. `-h`/`--help` and bare invocation show contextual status
and the commands available now. A module guide, setting description and command
help derive from their declarations rather than separate hardcoded catalogs.

**UX-03 — Settings declarations.** Every present, loaded module contributes its
settings to the chassis settings menu. Removing/unloading it hides that section
while preserving saved values. It returns with those values when reloaded.
Declared sensible defaults make the feature usable out of the box. The same
set/unset mechanism lets the chassis configure orchestrator-module settings.

**UX-04 — Glue.** Users can glue a chosen value as their baseline. Ordinary reset
returns unglued settings to their declared defaults while preserving glued values.
Explicit ungluing makes them resettable. Pinning an untouched default captures its
current effective value so a later changed module default does not change the
user's baseline. Removal and return preserve both value and pin state.

**UX-05 — BIOS-style setup.** Provide a polished keyboard-driven settings and
module-enable/disable menu, plus complete scriptable CLI controls. Present grouped
module settings, current/default values, help, intuitive navigation, toggles and
editing, individual/group reset, glue and save/exit behavior. The implemented menu
stages changes with preview and save/discard; key bindings and exact commands live
in S08. Reference shape: the user-selected `mvm config`, set/unset/glue behavior.

**UX-06 — Module navigation.** Entering a module replaces the base command surface.
A hidden working-folder binding persists that navigation across separate CLI
calls. Exiting removes that binding and restores the main surface. The current
implementation calls the marker `.metaform-context`; that filename is an
engineering choice, unlike the explicitly named `plugins/disabled` policy file.

**UX-07 — Assigned work.** Entering a nonce shows its module/workflow surface plus
appropriate assignment lifecycle commands, not ordinary administration. Status
includes current step, actual prompt, instructions, knowledge/memory addresses,
selected context and required submission header. Hidden discovery uses the working
path and `.agentid/nonce`. If entering assignment work without a nonce on a terminal,
request it; unbound administration must remain usable.

**UX-08 — Context transitions.** Submission records the answer; completion/abort
settles assigned work and clears active discovery state while retaining history.
Current chassis `exit` detaches navigation and does not complete/abort the durable
assignment. Older `done`/`complete` wording, multi-step cleanup and original
project-main-folder/admin restrictions need one canonical interaction contract
before feature migration (C10). Do not infer that hidden menus are a security
boundary.

**UX-09 — Guided onboarding.** Retain a dynamic module/workflow skill catalog and
built-in functional account of the chassis teaching module creation, workflow
import and public interfaces. S02 specifies this built-in account stays outside
the selected artifact's viewer and is not removable through ordinary user
operations. Product sources call for an unfamiliar harness to
receive provisioning guidance, remembering completion by harness install-folder
identity and ignoring `/tmp` identities. Reconcile `provisioning.json`, global
settings/database ownership and modern context rules (C11). Do not copy developer
collaboration instructions or the expert Foundation block into runtime prompts.

**UX-10 — Project startup.** Track selected project and operating-folder context.
Show current models/layers/capabilities; onboard missing project understanding.
Where an intake source baseline exists, report source additions/modifications/
deletions and change counts; the user decides whether to update. Explicit layer
choices persist, including show-all. Earlier rules for forgetting a registration
versus clearing project data preserve their distinct effects; they do not authorize
those destructive actions during this consolidation.

Sources: S01; S02 §§9, 12–14; S06 §§4–5, 13; S07; S08; S11. C10–C13 record
requirements that current implementation evidence does not settle.

## 9. Agents, assignments and MCP

**AG-01 — Universal harness boundary.** Support launching a harness directly and
operating inside an existing harness. Codex and Claude are both required examples;
the contract should not require either vendor to use the rest of Metaform. Include
a deterministic local fixture to demonstrate the flow without credentials.

**AG-02 — Work identity.** A nonce looks up a durable assignment. Supply the agent
with its nonce, Metaform invocation and instructions for its required submission
header. Reject missing or mismatched assignment headers. Preserve the submitted
answer without adding semantic quality gates.

**AG-03 — Process versus agent identity.** Record the MCP server's PID and its
assignment nonce association for process/work tracking; record launched harness
PIDs too. A PID or stdio connection is not sufficient logical-agent identity.
Different assignments can share a transport; route every operation through explicit
assignment context. No assumption that a harness creates one stdio server per agent
is part of the product contract.

**AG-04 — Shared deliveries.** CLI and MCP retrieve the same assignment, step,
prompt, references, layer context and header. MCP provides structured operations;
it does not replace CLI completeness. Protocol metadata/handshake details are
adapter-version concerns, not a universal agent-identity guarantee. Historical
claims about a future stateless MCP protocol are not adopted here.

**AG-05 — Nonblocking response.** Starting harness work returns promptly with a
trackable job. Capture actual prompt, stdout/stderr, exit outcome, response,
project/nonce and producing operation. When finished, publish the response through
the same event bus used by the request. Expose interruption and cancellation
honestly; never report a pending result as complete.

**AG-06 — Nonce lifecycle detail.** Older SPEC defines workflow-revision nonces,
eight-character agent nonces, inactivity expiry and different `done`/`complete`
meanings. Keep these as identifiable outstanding compatibility decisions (C10),
not silently replaced by the current generic assignment token implementation.

Sources: S01; S02 §9; S06 §§5–6; S07; S08; S11.

## 10. Global storage, provenance, origins and variants

**DATA-01 — Initial placement.** Initially keep all Metaform state in one user-folder
data root and one authoritative database across projects. Source folders and
repositories stay where they are. Preserve project ownership of records,
provenance, assignments and edit copies. Repository-local storage is a possible
later evolution; it is not required simultaneously. Small discovery/policy files
refer to this state and do not become alternate project databases.

**DATA-02 — Shared records.** The data service covers projects, operating-folder
selection, origins, variants, assignments, namespace records/owned joins, knowledge,
memories, module state and settings. These are responsibilities, not a mandated
one-table-per-kind schema. Payload files can live under the same root with durable
references. Old directory sketches are proposals; the current plugins folder
supersedes earlier module-folder sketches.

**DATA-03 — Producing objects.** Every produced record links to its producer.
Retain the actual operation/run, issued prompt revision and rendered text, variable
binding map, input objects and revisions, answer and produced outputs. Authored
records and imports retain their actual source/authoring provenance rather than an
invented inference event. This must be in the object model from the outset.

**DATA-04 — Traceability.** From any output or owned-join knowledge, follow the
producer, bindings and referenced inputs back to source evidence and prompts.
Follow dependencies forward to affected generated knowledge as well. Use those
relationships for inspection, visibility and regeneration. S02 §15 requires one
reference read to return producer, constructed prompt, binding map and bound
references together; inspecting a variable exposes its binding and producer.
A directory name or an unrelated activity log is not the requested provenance model.

**DATA-05 — Origins.** A repository baseline retains its selected commit; a
non-repository baseline retains its content-manifest hash and baseline contents.
Keep full source identity, content digest and lineage identity separately.
The retained identity forms are:

| Field | Representation |
| --- | --- |
| `mform_sha_id` | 240 most significant digest bits plus a 16-bit lineage suffix; 64 hexadecimal characters |
| `mform_id` | 48 most significant digest bits plus the same suffix; 16 hexadecimal characters |

Neither contains an underscore. The suffix distinguishes provenance-bearing
lineage instances; changing source origin is not merely incrementing this suffix.
A new origin starts a new retained history unit without erasing old units.

**DATA-06 — Artifact variants.** Retain workfolder outputs as variants linked to
their origin and producing operation/run/prompt. Sibling mutation experiments are
changes against the same selected origin, even if scheduled sequentially. This is
distinct from a Native-understanding variant in DATA-09; both need provenance.

**DATA-07 — Reconstruction.** Reconstruct origin plus changes using Python in the
receiving environment, including added/deleted files, changed text and whole
changed binaries. Retain manifests for checks. Source discussion permits whole
changed text below 3 MB and diffs above it; exact threshold units/calculation is
open (C14). Repository export must include required baseline contents rather than
assuming the recipient can fetch the originating repository.

**DATA-08 — Import preservation.** When importing into an existing lineage would
lose data or provenance, allocate a separate suffix and retain both. Return the
resulting identity/location. Export the origin history unit, baseline, variants and
associated provenance. Reconstruct one, several or all selected variants into
external folders. Do not erase local history to simplify import.

**DATA-09 — Native variants and re-inference.** Clone a foundation into a distinct
Native variant without changing the base. Replace the relevant property/binding
locally, e.g. C++ → JavaScript for an engine; never create a global language alias.
Identify affected knowledge through object, selector, membership and transitive
knowledge dependencies. Preserve unaffected knowledge and independently authored
content. Reissue affected original producing prompts with the new context and
retain new answers as variant-owned generations. Keep superseded generations
inspectable. A new relevant property can affect a recipe even if its previous
input records were unchanged.

**DATA-10 — Revisions and migration.** Foundation revisions and layer generations
are independently retained, and foundation revisions are immutable. Schema/reference
issues remain observable without inventing missing semantics. Map old records, namespaces, prompts, answers,
assignments and source histories explicitly into the new store. Preserve originals
and provenance; building the fresh chassis does not certify that migration.

**DATA-11 — Workfolder fidelity.** Capture the intended artifact boundary consistently
across baseline, diff, apply and export, for Git and plain folders. Preserve relevant
tracked, untracked and ignored files, binary content, additions, edits, deletions,
renames and applicable file metadata. Exclude ephemeral assignment/navigation
markers from source changes. Record the actual edit location and baseline. Knowledge
serialization does not dictate which development files are retained.

Sources: S01; S02 §§11, 15; S06 §§7–9; S10; S11; S12.

## 11. Web workbench and common interfaces

**WEB-01 — External global feature.** Web is a removable plugin with one global
instance on one configured listening port for tracked folders/repositories. Loading
another project uses that instance. Contribute `metaform web` and `metaform web
stop`, plus bind address and port settings through the chassis settings menu.
Accept hostname, localhost, `0.0.0.0` or a specific IP. Exact defaults/reconfiguration
semantics are engineering contract details; older extra status command/UI launch
rules need reconciliation with the two-command request (C12).

**WEB-02 — Stack.** A modern asynchronous web surface is intended. ASGI/Uvicorn
with Starlette is the current implementation choice, originally a recommendation;
it is not the semantic core of Metaform or a reason to couple web to the chassis.

**WEB-03 — Explorer.** The workbench shows the actual agent-visible graph/context,
namespace objects and joins, source relationships, selected layers, memories and
provenance. Distinguish foundation, attached knowledge, source and variant views.
Reveal actual semantic data without filler visualization or inferred confidence.
Source content, full text and selected graph information must remain inspectable.
Graph text must be readable and unobstructed; S17's review clarifications identify
covered/unreadable text as a user-reported failure, not cosmetic polish.

**WEB-04 — Jobs and authoring.** Show live work activity, steps, prompts, outputs,
recorded runs and replay. Author workflows and individual prompts using referenced
context objects; drill from those objects to their inference sources. Keep terminal,
MCP and web operations backed by the same public services. Each relevant panel can
show the exact agent-facing request/result envelope. Job inspection includes the
prompt as sent, what the agent read, evidence, answers, attachments and events.
Replay can scrub through steps as the graph grows. Edit/rerun supports side-by-side
comparison. Launch Codex or Claude through the same execution operation as CLI.

**WEB-05 — Project behavior.** Earlier requirements include opening the selected or
most recently opened project, a project chooser, visible missing-folder status,
forget-registration and clear-data operations with different effects. Retain this
feature scope, while separating those future workbench capabilities from the
already implemented small web plugin. No blank page or running HTTP process alone
is full workbench acceptance.

**WEB-06 — Recorded interaction requirements.** S13 calls for namespace-derived
names, OPs in the inspector rather than edge labels, genuine exterior entities,
full record data one action away, human-facing help, and stable layout/position
through selection, panel changes and resize. Keep the primary view free of kind
labels, IDs/long internal strings, redundant gesture hints and code-oriented legends,
while preserving record inspection. Colors describe where a joined effect applies.
Clicks respond immediately and wheel zoom behaves normally. The recorded desktop
visual direction rejects rounded-pill styling and the muted-green default palette;
palette options are to be judged on the actual screen. It explicitly excludes path-entry/file
browser and delete-join controls from this explorer. Preserve those recorded UX
requirements for review when migrating the workbench; they do not remove CLI/data
operations. The archive's keyboard/list equivalents, narrow-screen layouts, semantic
search, bounded neighborhood/grounding and coverage/continuation APIs are additional
historical proposals, not adopted exact designs (S17).

Sources: S01; S02 §§12–15; S06 §13; S11; S13; S15; S17.

## 12. Portable delivery and community demonstrations

**DIST-01 — Entrypoint parity.** Installed `metaform`, `python -m metaform`, and
`python /path/to/metaform.whl` use the same contextual CLI and public services.
The wheel has an archive-level entrypoint and carries the dependencies/assets
needed in its supported execution environment. Demonstrate actual uploaded-wheel
use without assuming an installed checkout or available web/MCP connection.

**DIST-02 — Portable projects.** Preserve the selected project's knowledge and its
related global knowledge/workflow dependencies in a self-contained executable
export. Follow the selected project's relationship closure, not unrelated projects'
local edges. Keep source contents and provenance. The portable-project spec calls
for JSON knowledge and local SQLite execution state, offline continuation, edits
and re-export. Reconcile that export representation with the initial single global
database and supported package versions explicitly (C13). Include required workflow
and prompt/rule revisions, schemas, module assets, future file-based-step inputs,
pending assignments, retained answers/continuations and workfolder outputs. Capture
a coherent selected-project snapshot whose identity is unaffected by unrelated
shared-project mutations. Verify continuation with the original home/service and
Git unavailable. A protocol for merging later portable edits back into a shared
owner is not settled merely by supporting import/re-export.

**DIST-03 — Interface usability.** Nonterminal CLI operations must accept supplied
arguments and structured input and return inspectable results without waiting for
an unavailable terminal. Help explains required inputs. Machine-readable output
and separate diagnostics are current engineering conventions serving this
requirement; external CLI style guides are references, not additional product law.

**DEMO-01 — Three main modules.** Deliver exactly the requested three-example
teaching set: a standalone hello-world-style all-services template (`showcase`),
and two derived modules (`event_requester`, `harness_runner`) demonstrating request
and eventual response over the same event system. Keep the derivation visible so
users can see how to extend the template. The optional web plugin is separate.

**DEMO-02 — Complete template.** Exercise every declared chassis service/hook
family: settings/defaults/glue, conditional commands, embedded help, sync/async
operations, event subscriptions/publication, lifecycle, records/revisions/provenance,
assignment/header handling, jobs and module inspection. It must run independently
of the event pair. Settings must demonstrably enable/disable command availability.

**DEMO-03 — Concrete journey.** Enter a module through a working-folder binding;
exit and restore main commands. Enter a nonce and inspect its prompt/header;
submit and finalize with retained records and marker cleanup. Launch a nonblocking
harness request, continue inspecting status, then receive its event response.
Support both Codex and Claude plus the local fixture. Unload one module while the
chassis and another remain usable. Repeat relevant behavior through the wheel.

Sources: S01; S02 §14; S06 §13; S07; S08; S12.

## 13. Quality, acceptance and current implementation boundary

**Q-01 — Semantic fidelity.** Judge results against authored meaning as well as
functional execution. Keep original prompts, source definitions and actual answers
available for review. A generated Metaform of the specs is useful guidance but is
not evidence that all specs were supplied or that the implementation conforms.

**Q-02 — Engineering reliability.** Verify context isolation under concurrent
assignments, attributable lifecycle/events/results, module removal, persistence,
header routing, reset/glue behavior, actual command availability and installed/
portable operation. Test observable failures and product behavior rather than tests
that only restate code. Do not equate a deterministic fixture with a real harness. S13's full-workbench acceptance includes a real intake
through the page observed and judged by Rich.

**Q-03 — Shared understanding.** Implement against the requirement IDs in this
review draft as refined by Rich, using the decision ledger for unresolved meaning.
Implementation plans must retain links to those requirements; code and test counts
do not decide specification conflicts. This is documentation traceability for the
engineering team, not an extra rule inserted into runtime prompts.

### Product acceptance journeys

| Journey | Required evidence | Requirements |
| --- | --- | --- |
| Project understanding | Intake through an actual workflow; inspect coarse records and owned joins; independent latent reasoning receives complete Native account and returns attributed knowledge | SEM, OBJ, INT |
| Layered context | Project defaults; mask a selected layer; reselect farther toward leaf; workflow obeys masks; hide a prompt source and observe dependent inference disappear without deleting history | KG-01–06 |
| Memory | Agent writes/reads/searches/updates/deletes memory at recorded object/owned-join addresses through CLI and shared adapter context | KG-08, AG-04 |
| Authored workflow | Import preserves behavior and interaction steps; XML/dict/JSON round trip; lexicalize explicitly; issue exact prompts; edit/replay with source revisions | WF-01–08 |
| Port/variant | Clone foundation; change scoped medium; preserve base/unaffected knowledge; reissue affected recipes; inspect both generations and temporary port-layer removal | KG-09, DATA-09 |
| Chassis and demos | Three modules, dynamic help/settings, glue/reset, module/nonce menu transitions, async request/result events, Codex/Claude and fixture, clean unload | CH, UX, AG, DEMO |
| Global ownership | Two repositories plus a non-repository project in one store; independent contexts; provenance traverses output to actual inputs/prompt/answer | DATA-01–04 |
| History delivery | Multiple origins/variants; text/binary/add/delete reconstruction; divergent import preserves both; actual wheel reconstructs selected outputs | DATA-05–08, DIST |
| Web workbench | Real agent work visible; graph and prompt objects inspectable; author/edit/replay; one listener across projects; CLI works with web removed | WEB, UX-01 |

These journeys define evidence to obtain, not a claim it already exists for the
fresh architecture. Resolve the listed semantic conflicts before interpreting a
passing test as acceptance of that disputed meaning.

### What is currently evidenced

| Area | Evidence/status in this checkout |
| --- | --- |
| Fresh chassis, typed services, settings/glue, drop-ins, contextual CLI, background jobs/events, three demos | Implemented locally; exact scope and previous verification in S07/S08. Prior report: 86 focused tests, 20 isolated executable-wheel commands, a real terminal-menu check, and small real Codex/Claude round trips. This document does not rerun or broaden those claims. |
| Optional global web plugin | Implemented small service/lifecycle/settings slice; it does not constitute the full workbench above. |
| Intake/workflow/layer/MCP feature migration | Still required through the fresh chassis; legacy implementations and old verification are reference evidence only. |
| Full origin/variant history, reconstruction, portable-project migration | Target specification preserved; completion is not established by the chassis data service. |
| Semantic conflicts and canonical native schemas | Review items in the companion ledger; not resolved by implementation existence. |
| Whole-product conformance | Not yet demonstrated. Historical verification has specific branch, source and scenario scope. |

### Retained optional and future scope

Earlier product sources retain image generation as an optional capability;
particular photographic workflows and expanded presets remain proposals. Using
accumulated provenance to improve Metaform’s own workflows is an expressed
opportunity, with no settled automatic adoption mechanism. Advanced remote work
packets, untrusted-plugin sandboxing, a distributed event broker and connected
portable-history merging are not implied first-delivery requirements. These
boundaries preserve the source distinctions rather than deleting the future ideas.

### Remaining product decisions

The companion ledger gives sources and effects for each issue. The most consequential
are the exact shallow-intake boundary; Element/join role vocabulary; Type versus
instance/envelope mapping; XML/reference grammar; selection/visibility scope; and
nonce/workflow-finalization behavior. These are recovered contradictions, not a
request to repeat decisions already given. The purpose of the review is to settle
them in this shared record once, then carry that meaning through implementation.
