# **Metaform**

**[Governing requirements](specifications/REQUIREMENTS.md) · [Live remediation matrix](specifications/REMEDIATION-MATRIX.md) · [Conformance audit](specifications/chassis-design-conformance-2026-09-18.md) · [Rulebook](specifications/REQUIREMENTS.md#12-rulebook) · [Agent memory](specifications/REQUIREMENTS.md#11-knowledge-selection-and-agent-memory)**

**Meta** — self-referential, going beyond, describing a higher level of its own category.

**Form** — the shape, structural arrangement, or overall appearance of something; a document with blank spaces for information.

**Metaform** — the shape that describes itself. The structure that holds the structure. The form that forms the forms. The meta is the same meta in meta prompts, but the meta understands the form of what you are prompting.   Sorry thats too meta.  Lets begin again.

---

## The Problem

Every AI system you've used pays a hidden tax. The model has to figure out what it's looking at, how to behave, what constraints apply, and what the actual task is — all before it can start working. That tax is paid in every forward pass, in every prompt, in every interaction.

## The Solution

Metaform pre-pays that tax. It's a context management surface that gives the model a pre-structured, linguistically native map of your system — the wiring formboard, the skeletal frame, the coarse shape — so the model operates *inside* the structure instead of reconstructing it from scratch every time.

The system knows its own shape. The shape describes the system. The model receives the form, fills in the blanks, and the work flows.

This isn't RAG. This isn't prompt engineering. This is architectural.

---

## What It Does

First it finds your skeletons, not from the closet but from your plans, your ideas, from whatever it is you are working on. Its like an X-Ray of the skeleton of your ideas. Map the shape once, at the perfect level of abstraction.   Its the form of the thought.. a digital thoughtform if you will. 

**Lexicalized prompts that speak specifically.** Every element has a namespace address that reverses to natural language. `code.auth.jwt` isn't "the authentication system" — it's a precise pointer. The model knows exactly what you're referencing because the address is both human-readable and machine-resolvable.

**Knowledge layers that blanket the design.** "For every object, attach 3 best practices." "For every join, identify bias blind spots." One statement, comprehensive coverage. The formboard makes it possible because every node is addressable and the structure is coherent.

**Nonce-mediated handoffs.** An agent receives a nonce, the MCP server delivers exactly the context that nonce addresses, the agent does the work, submits results under the same nonce, and the system passes it forward. No orchestrator paraphrasing. No low-context instructions. No self-orientation tax.

**Provenance-tracked layers.** Knowledge lives at the node. If the node is removed or transformed, the attached knowledge is hidden or invalidated. No stale context. No drift between documentation and code.

**An immutable chassis.** The core system — provenance, module controller, settings, CLI, workflow, MCP — is versioned and stable. You extend it, you don't modify it. The system knows its own metaform, making it trivial to add modules that integrate cleanly.

---

## What This Enables

**Port legacy systems without the model choking.** Give the model the coarse map, let it expand the shape, attach knowledge layers, add the port intent, pre-reason the considerations, then execute. The formboard carries the cognitive load.

**Find blind spots before they find you.** Hand an unbiased agent your design map and ask "where might oversights exist." The structural distance makes it possible. The agent isn't enmeshed in the code — it's looking at the frame.

**Collaborate without losing context.** Agents receive exactly what they need via nonce, do the work, pass it forward. The handoff is clean because the context is structural, not paraphrased.

**Build systems that scale.** The chassis is immutable. The modules are self-describing. The namespace is reversible. The knowledge layers are provenance-tracked. The system extends itself without collapsing under its own weight.

---

## Why This Matters

Because friction blocks flow. Because models work better when they're not paying a cognitive tax on every operation. Because the difference between a system that works and a system that doesn't is often just *whether the model can see the structure*.

Metaform is that structure.

The shape that describes itself. The form that forms the forms. The map that the model can actually use.


---

## Read the product requirements

**[Metaform requirements — the complete current product contract](specifications/REQUIREMENTS.md)**

This README explains the system and why its parts belong together. The
[146 `REQ-*` requirements](specifications/REQUIREMENTS.md) are the complete,
superseding product contract. Earlier specifications, plans, inventories, and
implementation accounts supply evidence and context; they add no requirements.
The current Canonical Intake and explicitly maintained authored workflows retain
authority over their own behavior.

The authored introduction above preserves the product's original explanation.
Its older core list includes workflow and MCP. Under the governing ownership
requirements, those features are contained modules; the chassis supplies their
shared services. Statements of intended benefits are not acceptance evidence.

**Development status:** the checkout is incomplete. The
[current engineering state](docs/development-state.md) records branch disposition,
supported verification commands, and this consolidation effort. The
[conformance audit](specifications/chassis-design-conformance-2026-09-18.md)
records defects in containment, public cooperation, exact inputs, provenance,
selection, portability, and lifecycle. [Section 20](specifications/REQUIREMENTS.md#20-remediation-instructions)
authorizes repair from the externally visible product boundary inward. The
[live remediation matrix](specifications/REMEDIATION-MATRIX.md) tracks each
requirement, its evidence, and remaining work. Older review pauses and unresolved
implementation choices do not halt this remediation. Passing component tests and
agent runs establish only their tested behavior, not full product acceptance.

## Prepare understanding so later reasoning can start further ahead

Metaform is Richard Graver's approach to **inference amortization**: invest in
understanding a project, retain that understanding in a useful form, and supply
it to later work. A short instruction can then address the project's actual
functions, relationships, and constraints without requiring the agent to discover
them all again.

The investment is specific to the project and its development. A recorded account
must remain inspectable and revisable as the artifact changes. Reuse is valuable
when the selected understanding still applies; provenance and change awareness
make that judgment possible. This creates room for more reasoning about design,
consequences, alternatives, and difficult decisions. It does not establish a
measured token-saving claim by itself.

The structure matters as much as retaining information. Metaform uses **Type** to
place an artifact by what it is and what function makes it that kind of thing.
Meaningful names, descriptions, receiving purposes, and encounters give the model
stable subjects for reasoning. Those semantic relationships engage the model's
existing understanding of the concepts while keeping the project's actual detail
available at its objects and joins.

An artifact can be a program, a subsystem within a repository, an installation
procedure, photographs, a contract, or a story. A functional map makes the same
approach available across those forms. For example:

> For every object and its receiving joins, identify the concerns that matter
> when porting this project from C++ to C#.

That request becomes useful because “every object” resolves to an inspectable
project structure, each encounter has its own meaning, and the resulting guidance
can remain attached to the subjects it concerns.

## Intake records what the artifact actually does

Native intake examines the actual artifact. The current Canonical first establishes
whether the target is one entity or a collection, then identifies the **Defining
Element**: the representative function whose loss would mean the artifact could
no longer remain the same Type. It traces the **Operative Purposes** held by each
receiving Element and the encounters satisfying them. The maintained Canonical supplies the authored procedure; the product preserves
and executes it through the workflow module and common services.

A join belongs to its **Receiving Entity**. It records that receiver's purpose,
the provider it encounters, and the **Encounter Function** supplied in that
particular relationship. The same provider can satisfy different purposes for
different receivers; its encounter functions are recorded on those receiving
joins. Medium, style, and encoding must not displace the defining function.

The Native account retains actual artifact understanding: observations,
descriptions, requirements, and source detail. Types retain their universal
meaning. The namespace places each subject at its appropriate semantic
specificity; it is not merely a translation of a file tree. A Type's proper name
is read backward from the selected suffix of its namespace address. For example,
`code.engine.game` with `name_length: 2` reads “game engine.”

The current namespace uses `asset` in place of the former `media` terminology
and supports an `entity` Type trunk. An Entity is an Element that may contain
other Elements; its Type need not match its Defining Element's Type. Historical
accounts remain readable. Outside participants can receive from an artifact or
provide something it needs without requiring a new prescribed trunk name.

The Native Metaform becomes the project's **Inference Metaform**. Latent reasoning
then receives the complete Native account and reasons from outside the native
implementation frame. It must see what Native actually recorded. Its agreements,
corrections, missing understanding, and other findings must remain attributable
and available at the relevant subjects as a separate knowledge contribution.
This allows independent reasoning without erasing the account it examined.

The [Canonical Intake](specifications/Canonical_Intake.xml),
[Name rule](docs/rulebook/element/name.md), and
[Description rule](docs/rulebook/element/description.md) contain the authored
semantic instructions. A successful process launch or parsable XML response does
not establish that an agent followed them correctly.

## One object shape, with knowledge owned where it belongs

The common object contract exposes namespace identity, naming information, and
owned typed joins. The current representation expresses these as:

```json
{
  "namespace_address": "code.engine.game",
  "name_length": 2,
  "joins": []
}
```

The address identifies the subject; the name length determines its proper name;
the owned joins carry its contributions and relationships. Each join has a type
and the fields needed by that authored contribution. A workflow, a memory, an
intake encounter, a rule, and a producing relationship can contribute different
join content without requiring a new universal object class for each feature.

**Mirrors preserve this common namespace shape.** The same namespace can receive
contributions in different stores: native understanding in one place, inference
or memory in another, and producing provenance elsewhere. Those placements do not
create different semantic owners. Reading the applicable mirrors assembles the
subject's selected contributions; moving storage must not change what a join
means or whom it belongs to.

A join reference retains its project, receiving namespace, persistent join ID,
and exact revision. This gives later prompts something precise to select and
previous work something precise to retain. A new revision must not silently
change an already issued prompt. Authored fields and references remain intact
through copying, export, import, and inspection.

The [namespace and join account](specifications/namespace-join-implementation-plan.md)
documents this storage shape. The consolidated requirements distinguish the
intended contract from incomplete or conflicting implementation choices.

## Layers develop the understanding for a particular task

The base map provides subjects on which further inference can operate. A layer
can apply an authored request to **every object and every owned join**, or to a
selected part of the project. Examples include engineering practices, purpose
imperatives, blind spots, memory, and guidance for a temporary porting task.
The output belongs at the object or encounter it explains and retains the actual
inputs and producing request behind it.

A workflow selects the layers it needs. Selection and source visibility determine
which knowledge can enter an operation. The same applicable rules govern direct
object reads, provider/property context, workflow context, and MCP reads.

Selection flows from the project trunk toward the namespace leaves. Project
selection supplies the initial selection. Objects add no local selection by
default and pass inherited selection through unless masked. At each object:

```text
outgoing selection = (incoming selection AND local mask) OR local selection
```

The mask filters inherited selection before local selection is added. A more
specific descendant can therefore select a layer again after an earlier mask
blocked it. Workflow selection observes those same masks. Unsupported selection
forms remain preserved and explicitly reported; they must not silently expand
context. Unspecified implementation details can use a reversible design consistent
with the governing selection requirements.

Property placement determines applicability. A language property on an installer
can inform its descendants and be visible in an ancestor summary without making
an unrelated engine use that language. Selection must also control the knowledge
inserted through those properties; an unselected layer must not leak into an
actual prompt merely because it sits on a referenced provider.

Consider a C++ project being ported to C#. A porting object can carry the intent,
while a layer supplies memory-management concerns and other guidance for each
relevant object and join. C# knowledge can be selected alongside it. Once the
port is complete, hiding the temporary porting object hides inference derived
from it. Independent knowledge remains available and the historical producing
chain remains inspectable.

A changed source revision and a hidden source are different events. The product
must identify affected understanding and support requested re-inference without
silently treating all old work as absent. Recorded causal inputs help trace what
was used; a newly relevant property may require applicability reasoning even when
it was not among a previous run's inputs. Native interpretation variants and this
broader change-sensitive behavior remain incomplete.

## Agent memory is local, editable knowledge

An agent should be able to record what it learned against the objects and joins
it was working with. That memory then becomes reusable context for another step,
agent, or workflow, selected through the same knowledge mechanisms.

[Agent memory](specifications/REQUIREMENTS.md#11-knowledge-selection-and-agent-memory) includes creating,
finding, inspecting, updating, and individually deleting or withdrawing an active
memory. Editing one memory must update what later work receives without changing
what an earlier prompt already consumed. Removing a memory must not require
hiding the entire namespace object or unrelated knowledge. Its source, producing
context, and retained history remain attributable under the data rules.

This makes memory a working part of the project. An observation can be corrected,
a temporary assumption retired, and a useful result carried into later reasoning.
The current `remember`/view implementation demonstrates part of this path;
complete memory lifecycle and attachment-update behavior are still required.

## The rulebook governs operations

The [rulebook](docs/rulebook/README.md) remains an active part of Metaform. It
contains specific rules for tasks and system operations, and those operations
must enforce their applicable authored rules. It is editable and inspectable;
it is not merely a historical source of wording for prompts.

Rules retain their authored concise statements, explanations, examples, and
teaching distinctions. Operations supply and apply the applicable rules according
to that authored behavior. There is no universal retry, rejection, approval, or
scoring policy imposed merely because a rule exists.

Rules apply to the operations they govern. Namespace authoring must honor the
applicable naming and description rules. Intake must follow its functional and
encounter semantics. Workflow preparation and execution must honor the rules
assigned to that procedure. The rulebook's authored requirements determine the
checks and enforcement needed; the implementation must not substitute invented
universal answer restrictions for them.

An issued operation must expose the rules and revisions actually applied. Editing
a rule changes the applicable future preparation while retaining the evidence
needed to understand earlier work. This connects editable operating policy to
provenance: a reviewer should be able to inspect an outcome, its operation, its
context, and its governing rules together.

See [rulebook requirements](specifications/REQUIREMENTS.md#12-rulebook) for the current
contract. Older command examples in source documents do not prove that this full
operational surface is implemented in the fresh chassis.

## Workflows put referenced objects inside prompts

A workflow preserves the author's procedure while making its references specific
to the project. “Review the game engine” can contain an inline reference to
`code.engine.game`, with the relevant description, selected guidance, or previous
answer attached. The visible name remains readable; the stored reference retains
identity and selected revisions.

Lexicalization is an explicit agent task: orient the procedure to the actual
project and insert the appropriate namespace references. Import and format
conversion preserve source text, local aliases, structure, and bindings. Inferring
correct executable handoffs is additional reasoning, whose source and resulting
interpretation must remain available for review.

Workflows must round-trip through Markdown, XML and JSON while retaining that
meaning. Authored aliases, section names, attributes, repeated structure, and mixed text
remain intact. Semantic conversion can infer steps, handoffs, and how earlier
outputs become later inputs; it retains its source and resulting interpretation
separately. Serialization preserves the chosen representation without silently
performing that inference.

A prompt can carry an object index, selected contextual layers, and applicable
imperatives. Those contributions must remain distinguishable from authored text.
The graphical editor is intended to make this visible: editable surrounding
instructions, inspectable inline objects, and the exact content an issued step
will deliver. CLI access must offer the corresponding operations independently.

Execution must support agents, user decisions, tools, branches, repetition,
parallel work, and nested handoffs as the authored workflow requires. Long-running
agent work returns later without blocking other activity. Editing a later step
should allow earlier completed outputs to be reused while preserving the original
run; ordinary resumption of an unchanged run is a different operation.

## A nonce identifies the work; provenance explains the result

The orchestrator gives an agent a nonce. Entering that nonce supplies its actual
assignment, current step, prompt, required submission header, selected context,
and knowledge addresses. The agent-facing command surface becomes contextual:
ordinary administration gives way to the assigned work until it exits or finishes.
A hidden workfolder binding lets later CLI invocations recover that context.

The same assignment must work when Metaform launches a harness directly or when
an agent is already running inside one. CLI and MCP must reach the same operations
and state. MCP process IDs are useful diagnostics, but do not establish which
logical agent or assignment a request belongs to. Nonce and header identity must
survive shared transports, background jobs, events, and step transitions.

An inference result must lead to its **actual producing occurrence**: the issued
prompt revision, exact rendered text, object bindings, consumed contribution
revisions, governing context, and actual answer. Repeating an operation with a
similar answer must not merge distinct causes into an ambiguous history. Reading
a whole object must account for the exact delivered content, not merely record
its revisionless address.

This inspection continues through the chain:

```text
answer C → actual prompt C → inserted answer B → actual prompt B
         → inserted answer A → actual prompt A → original selected context
```

Merely available knowledge is not automatically a producing input. Conversely,
context actually delivered through a CLI read, MCP read, module call, event, or
job cannot disappear from provenance because that route bypassed a private
helper. The chassis must provide a complete common contract and enforce it for
inference. That is why universal inspection and exact causal identity are core
requirements, rather than conventions each feature reimplements.

## A complete chassis, with contained feature modules

The chassis is a project in its own right. It owns common object access,
provenance, module lifecycle, settings, contextual CLI/status/menu construction,
work identity, synchronous and asynchronous execution, jobs, and the event data
bus. Modules cooperate through those public services, for example:

```python
from metaform import settings, event, cli, data
```

In the current intended ownership model, workflow execution, knowledge/inference,
harness and MCP adapters, history, distribution, and web features belong to their
respective modules. A module is one Python file or a self-contained directory
under `modules/`, including its feature implementation, resources, settings,
help, and dependency ownership. Built-in and community modules use the same
contract. A removable command wrapper around an engine still embedded in the
chassis does not meet that requirement.

Modules register synchronous operations, asynchronous operations, or both. Agent
work is asynchronous. The event bus carries object references and the correct
work context, so one module can request work and receive an attributable response
later. Direct cooperation also needs a public contract; features must not depend
on another module's private engine or raw operational tables.

Each module's Python declarations provide its settings, defaults, help, command
availability, and configuration needs. The chassis supplies common CLI and
keyboard-driven configuration surfaces. A user can **glue** a setting as a baseline
that survives reset until explicitly unglued. Removing a module withdraws its
live contributions while retaining saved settings and records for inspection or
reactivation. Generated feature configuration belongs in writable runtime space,
including when the executable package itself is read-only.

The CLI must form a navigable menu with visible command ownership and contextual
status. Entering a module opens its menu; exiting returns to the main chassis.
An assignment further narrows that surface. Linux, macOS, and Windows are chassis
targets; a feature module can declare a narrower supported operating-system set
and be skipped before incompatible imports execute.

### Prove the product and extension boundaries

[Outside-in remediation](specifications/REQUIREMENTS.md#20-remediation-instructions)
starts with the empty chassis and executable delivery, then repairs the public
extension boundary. [Three teaching modules](specifications/REQUIREMENTS.md#18-developer-experience-and-documentation)
make that boundary concrete:

1. A standalone hello-world template demonstrating every public chassis service
   and hook, including settings that enable or disable commands, object work,
   provenance, sync/async behavior, assignments, and clean lifecycle removal.
2. A requester derived from that template, sending work through the shared event
   system and receiving the eventual response.
3. A harness responder derived from the same template, demonstrating Codex and
   Claude, plus a deterministic local fixture, asynchronously and returning the
   result through that event system.

The demonstration must show nonce entry replacing the base commands and exit
restoring them; module navigation using its hidden working-folder binding; useful
work continuing while an agent runs; and removal of one module leaving the chassis
and another module usable. The source should teach how the examples were derived,
and the packaged modules must contain what they need.

The boundary proof must be repeated as remediation proceeds. An empty module
directory and a wheel with no selected feature modules must still provide chassis administration and
shared object/provenance services, without bundling those optional feature engines.
The present examples and passing tests do not settle the boundary defects found
in the audit.

## Preserve the project when its storage or working environment changes

Configuration has one authoritative writable root outside installed packages and
wheel extraction. Data retains project ownership while supporting configured
global or project-local placement and unified or split databases. A namespace's
contributions can span arbitrary SQLite files; routing by join type is a configurable placement choice. The same objects,
join identities, revisions, and producing relationships must remain readable
when that placement changes.

Artifact history retains an origin, its full source identity and baseline, and
produced variants with their actual provenance. A selected Git origin must retain
the selected commit's bytes; folder artifacts need an equally explicit captured
baseline. Reconstruction must preserve required text, binary, and filesystem
content without relying on the original repository or a Git executable. Earlier
user data requires explicit preservation and conversion, including reference
mapping and unresolved cases.

Exports must preserve the selected work's necessary closure: project knowledge,
eligible referenced global knowledge, exact historical contributions, rules,
prompts, workflow definitions, selected modules/resources/dependencies, artifact
payloads, and pending assignment/workfolder state. Another project's unrelated
content must not expand that export. Conflicting histories need inspectable
resolution; copying or importing must not silently replace retained identities.

The intended result is continued work: take a project to a Python-capable execution
environment, run the wheel by its entrypoint, resume its assignment, inspect what
produced the answer, and export the developed work again. Full CLI functionality
is required without a web interface. An installed command, `python -m metaform`,
and direct-wheel execution must use a consistent contract. Native dependencies
and optional module support must be represented truthfully for the target platform.

The [data and portability requirements](specifications/REQUIREMENTS.md#14-artifact-history-and-portability)
govern origins, variants, preservation, and reconstruction. The older
[global data pattern](specifications/global-data.md) supplies historical context.
Existing wheel checks demonstrate specific transfers; the audit identifies missing workfolder fidelity, recovery,
configuration, and packaging boundaries that broader acceptance still requires.

## Portable work must start cold and remain compatible

A delivered wheel must perform meaningful work offline outside the checkout,
without an installation step, source tree, network, or warmed dependency cache.
Selected modules mean selected implementations and their declared dependencies;
a zero-feature wheel still contains a usable chassis. Native dependencies must
accurately identify the supported interpreter and platform.

Python-capable hosted agents, including ChatGPT and Anthropic environments, are a
primary delivery case. The agent should use its existing reasoning context while
Metaform supplies structure and operations. An external provider API is not a
prerequisite for that mode of work.

Portable and installed versions must deliberately share durable configuration
without modifying each other's packages, entrypoints, or dependencies. Within a
major version, supported minor and patch versions must read and write the same
root in both orders without losing newer compatible data. This requires behavioral
compatibility checks, not just accepting a version string. These requirements let
a project move between working environments without sacrificing retained work.

## The graphical workbench is an intended surface

The optional graphical workflow editor should let a person author and inspect
these same objects, procedures, selections, and producing chains. It should show
collected relationships without inventing edges, expose the exact selected inline
content, and let the user follow an answer back through its actual prompts and
inputs. Module-owned web contributions should use the same operations as CLI.

The intended authoring view makes surrounding prompt text editable while preserving
inspectable inline object identities, selected contributions, and exact revisions.
A graph displays collected objects and joins and exposes their details. The
presentation should make those relationships understandable without exposing
internal registries or inventing relationships absent from the data.

The web module may use one global instance for tracked projects. It owns bind,
port, and access-policy settings, including an explicitly enabled trusted-environment
bypass. Unauthenticated non-loopback access is not the default. Browser terminals
belong to a separate optional module. The implementation framework is an engineering
choice; every surface uses the same owning operations and object contracts.
A browser is not required for complete product use. Graphical design and integrated
live editing are deferred while the technical contract and mechanics are repaired;
retained screenshots are evidence of particular earlier surfaces. Optional web
remains subject to the governing product and polish requirements.

## Inspect the current incomplete checkout

These commands open the current CLI for inspection. They are not a claim that the
full product journey or the repaired module boundary has been accepted.
Python 3.11 or newer is required; run from this repository:

```sh
uv sync --frozen
.venv/bin/python -m metaform --root "$PWD/.metaform-inspection" --help
.venv/bin/python -m metaform --root "$PWD/.metaform-inspection" skill
.venv/bin/python -m metaform --root "$PWD/.metaform-inspection" status
```

The explicit `--root` selects the inspection data root even if the working folder
has a saved context binding. Stop that root's persistent host with:

```sh
.venv/bin/python -m metaform --root "$PWD/.metaform-inspection" runtime stop
```

Use the [current API account](docs/plugin-api.md) to inspect available operations,
and read it alongside the conformance audit. Current command/path choices are
implementation evidence, not permission to redefine the requirements around them.
Earlier runtime code remains available as historical implementation material.

## Where to read next

| Document | Purpose |
| --- | --- |
| [Current requirements](specifications/REQUIREMENTS.md) | Sole product contract: 146 requirements, compatibility, acceptance, and authorized remediation. |
| [Live remediation matrix](specifications/REMEDIATION-MATRIX.md) | Requirement status, affected boundaries, verification, and remaining work. |
| [Design-conformance audit](specifications/chassis-design-conformance-2026-09-18.md) | Reproduced defects, ownership violations, missing capabilities, and required proof. |
| [Rulebook](docs/rulebook/README.md) | Authored operating rules, explanations, examples, and semantic rule sources. |
| [Canonical Intake](specifications/Canonical_Intake.xml) | Current authored intake procedure and encounter semantics. |
| [Primer](docs/primer/README.md) | The conceptual account of Metaform and inference amortization. |
| [Source inventory](specifications/product/SOURCES.md) | Earlier specifications, examples, proposals, and their provenance. |
| [Verification record](docs/chassis-verification.md) | Scoped tests, artifacts, provider results, failures, and their limits. |

A useful implementation must satisfy both the mechanics and the intended meaning.
The governing requirements and live matrix guide active remediation; each
completed slice must be verified at its public boundary and within the whole product.
