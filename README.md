> "Empty your mind. Be formless, shapeless, like water. You put water into a cup,
> it becomes the cup. You put water into a bottle, it becomes the bottle.
> You put it in a teapot, it becomes the teapot. Water can flow, or it can crash.
> Be water, my friend."
> — Bruce Lee

---

# Inference Metaform

**Develop understanding before the work. Make that understanding available for the work that follows.**

[Documentation](docs/README.md) · [Getting started](docs/guides/getting-started.md) · [Worked project example](docs/examples/project-walkthrough.md) · [Technical](#technical)

## What is Metaform?

Metaform uses the concept of *meta* to abstract your ideas into their purest
functional form — then stores that form as a living, queryable structure your
agents navigate, recompose, and build from.

A codebase is a forest. An agent can have perfect memory of every file, every
doc, every past session — and still be lost, because memory doesn't say where
you are, what anything is for, or which direction serves the purpose. Metaform
is the view from above: the functional shape visible at once, purposes laid out
as terrain, every agent's position marked within it. And because ideas are
stored as functional forms rather than implementation descriptions, the forest
itself can be recomposed. The form is built once, before the work starts, and
amortized across every agent, every session, and every operation that follows.

The organizing question is not simply what an agent should remember. It is **what reasoning can be performed in advance to offset reasoning that would otherwise have to happen while doing the work?** Identifying a project's functional parts, understanding a dependency, interpreting a request against project terminology, and deriving the consequences of a particular realization are all reasoning tasks. Metaform retains their useful results so that subsequent work can begin from them, examine them, and extend them.

This is **advance inference amortization**. Its principal subject is reasoning effort, not a promise that every request will contain fewer tokens. A prepared input can be longer while carrying more semantic work that the executing agent no longer needs to originate.

## The name

**Meta** — showing or suggesting an explicit awareness of itself or oneself as
a member of its category : cleverly self-referential

**Form** — a type or kind of something
           to cause (something) to have a particular shape or form.
           to get, create, or develop (something) over a period of time
           to make or create (something)
           to be arranged in (a shape)

## What it does

**Orients.** Every element has an address, a purpose, and a record of what
depends on it. Agents receive their position, their purpose, and exactly the
knowledge in scope — the stored functional record, not a paraphrase of last
session's chat.

**Abstracts.** The shape of your AI agent's workpiece is derived from its functionality, not
its medium, genre, style, encoding, file layout, class hierarchy, or framework.

**Recomposes.** Functional forms can be rearranged. Attach knowledge layers,
hide old ones, swap realizations under stable purposes, graft a capability from
one project into another. The addresses don't move; the purposes don't change.

**Traces.** Every layer keeps the record of how it was made — the module,
workflow, model and role behind it, and the prompt version it came from.
Corrections keep every earlier version, and variants keep each worker's files
against one origin. *Why is it like this?* is a query, not an excavation.

## How the mechanism works

### Type understanding supplies an orientation

Models already bring understanding of kinds of things to a task. Metaform engages this **primordial type understanding** through meaningful functional addresses. For example:

```text
code
  code.engine
    code.engine.game
      code.engine.game.fps
```

Each prefix is a usable type and a prompting surface. In the author's supplied address-only examples, requests for best practices at these four addresses produced distinct guidance about general code, engines, game engines, and first-person game engines. The final segment supplies specificity; the ancestry keeps the inference in the intended domain. General knowledge belongs at the parent where it applies, rather than being copied beneath every specialization.

### Relationships connect the type to this particular workpiece

A type address is not a substitute for knowing the project. The address `code.system.plugin` engages understanding of plugin systems. Its recorded relationships establish what **this** plugin system provides, to whom, and for what purpose.

A Receiving Entity owns an **Operative Purpose**: the reason it needs something. A Providing Element supplies an **Encounter Function**: how the required effect is delivered, used, or experienced. The join retains that relationship, its active-voice description, observations, and relevant references. The relationship has an identity of its own, so an agent can reason about it and attach knowledge to it.

**Function** concerns operative capability. **Encounter** concerns its expression or realization. The term Encounter Function deliberately accommodates both the encounter of a functionality and the functionality of an encounter. It is not restricted to a callable function in source code.

### Understanding is selected, used, and extended

```text
Workpiece + its context
          |
          v
Functional understanding developed in advance
  types + receiving purposes + Encounters + references
          |
          +------> further examination and knowledge layers
          |
Request -> project-grounded interpretation -> subsequent work
                                                |
                                                v
                                 findings, memory, corrections
                                 retained at meaningful addresses
```

The prompt directs an operation; the Metaform supplies the semantic orientation through which it is interpreted. Selected knowledge can provide information or, when that is the layer's purpose, additional imperatives. Memory is attached to elements, joins, and internal subtypes, rather than detached from the functionality it concerns.

This also supports criticism. A critic can inspect the code together with its Metaform, or examine the Metaform on its own. A blindspot challenge asks the project for substantive reasoning: why a concern was already considered and adds no benefit, why an unexplored concern matters, or where another part of the system already fulfills the apparent omission.

## What it looks like

An agent assigned to work on your event bus receives the stored record:

    code.chassis  ←  code.system.plugin
      purpose: "Carry every capability beyond its own commands as modules it
                finds, checks and loads on its own, and withdraw everything a
                module registered when it goes."
      subtype code.bus.event
        function: "Delivers a published topic to every loaded subscriber with
                   its own Context and a copy of the payload, and returns each
                   delivery's outcome, completed, failed or cancelled, to the
                   publisher; one subscriber's failure never hides another's."
        ef: Function
        relation: "The event bus connects modules without either naming the other."
        observation: "events.py; from inside a running loop async subscribers are
                      awaited and sync ones run in a worker thread. The bus runs
                      no workflow. Only helloworld subscribes today."

Every agent that touches this element — this session, next month, a different
model from a different vendor — sees the same stored purpose.

### Extending Metaform itself

The supplied project Metaform calls `code.system.plugin` **the module contract and loader**. One of its receivers is `stakeholder.author.module`, the **module author**. That receiver's recorded purpose is:

> Add a capability to Metaform as a module, declared once in its own folder, that runs as a metaform command and an MCP tool with its own settings, events, status line and lifecycle, without changing the chassis.

The join explains how a `MODULE = Module(...)` declaration supplies those surfaces. Inside that relationship, `code.template.module` identifies **template**, and `code.module.example` identifies **helloworld**. They are internal subtypes of the relationship, not extra top-level subsystems inferred from their filenames.

An agent asked to add a module can receive the provider's project name, this receiving purpose, the template and example, and the source references for the declaration and loader. It can then implement against the existing shared facilities rather than invent separate command registration, settings storage, or an event mechanism. The same provider also has relationships to the command line, MCP server, package builder, chassis, and agent instructions. Those relationships make the consequences of a change available from the receivers' perspectives.

For an imported copy of the supplied project map, the reads are executable:

```sh
metaform map element code.system.plugin
metaform map joins code.system.plugin as=provider
metaform map where code.template.module
metaform map where code.bus.event
metaform memory open-nodes element:code.system.plugin
```

A **derived illustration of project-grounded lexicalization** uses the request:

```text
Review error handling in the plugin system.
```

The project-grounded request becomes:

```text
Review error handling in the module contract and loader.
```

A separate mapping connects `module contract and loader` to `code.system.plugin`, with directions to the relevant joins and selected knowledge. The operation remains a review of error handling. The preprocessing does not perform the review or add a new assignment.

The graph reads and addressed memory are implemented. The lexicalization producer described here is intended functionality, not a shipped command. [Follow the complete example](docs/examples/project-walkthrough.md) for the actual records, executable inspection, and the distinction between recorded material and derived use.

### Refactoring legacy code

A capability smeared across twelve files gets one coherent functional shape,
bound back to the exact locations where it lives. Ask "what is the
authentication flow" and get an answer that spans files, references exact
lines, and describes purposes and encounters — not which class calls which
method. The map is generated from what the code *does*, not from its AST, so it
stays stable while the implementation moves under it.

### Porting across languages

**Before:** elements carry layers of C++ best practices and memory-management
concerns, injected into prompts when agents work on those elements.
**During:** a "porting to Rust" layer attaches — ownership semantics, lifetime
annotations, error handling — while the C++ layers mask out.
**After:** the C++ layers hide (kept and still readable, never deleted); the
Rust layers activate. Addresses unchanged. Purposes unchanged. The knowledge
swapped. Past prompts remain exactly as issued; future prompts receive the new
layers.

## What it makes possible

Metaform connects several parts of the work process rather than treating them as unrelated utilities:

| During the work | What the prepared understanding contributes |
|---|---|
| Understand a whole system | Functional parts, receiving purposes, and relationships that cross file or medium boundaries. |
| Prepare a task | Project names and functional addresses through which a reusable operation can be interpreted. |
| Retain findings | Meaningful locations for observations about a part, a relationship, or an internal subtype. |
| Change perspective | Reason from a receiver's need, a provider's effects, a broader type, or a particular Encounter. |
| Examine blindspots | Compare a concern with the project's actual reasoning and other places where it may already be handled. |
| Shape the workpiece | Preserve relevant identity while changing a realization, or deliberately transform the purposes and effects that define it. |

A workpiece can be software, a document, a narrative, an image, a collection, or an idea under construction. The same method asks what the artifact is doing in its context. A photograph used as an asset has a different relationship to the surrounding work from the same photograph examined on its own; a functional type does not erase its particular subject or occasion.

## Community-extensible by construction

The implementation is a Python chassis with discoverable modules. A module declares its verbs, input nouns, settings, event subscriptions, lifecycle hooks, and purpose. The chassis uses those declarations to expose commands, MCP tools, help, settings, and agent instructions.

Modules receive a per-call context with the selected project, store, folder, settings, and output facilities. Shared facilities include graph and knowledge storage, addressed memory operations, event delivery, owned asynchronous work, reports, and packaging. Modules are discovered from the bundled module directory, the user's Metaform home, and installed entry points.

The current modules provide intake, map operations, memory, MCP service, and a web interface. The disabled-by-default **helloworld** module exercises the contract; **template** supplies its empty starting shape. The existence of a shared facility is distinct from how many modules currently use it. A new inference producer can use the existing chassis without rebuilding those facilities.

[Extend Metaform](docs/guides/extending-metaform.md) explains the actual contract, scheduling, lifecycle, and packaging behavior.

## Begin using it

From a source checkout, use Python 3.11 or newer. These commands install the local project and the dependencies needed for the MCP/build path in this source edition:

```sh
python -m venv .venv
. .venv/bin/activate
python -m pip install -e . "mcp>=2.2" uv
metaform list modules
```

On Windows PowerShell, activate with `.\.venv\Scripts\Activate.ps1` instead. Register an existing workpiece folder:

```sh
cd /path/to/workpiece
metaform add project example .
metaform intake prompt
```

The last command serves the Canonical Intake instructions; **the agent performs the intake**. It examines the workpiece, follows the served method, and submits the final element array through `intake_submit` or `metaform intake submit`. You choose the workpiece and direct the work; Metaform retains the resulting functional representation. Start reading it with `metaform map roots`, or open `metaform web`.

For an agent connection, build the selected modules with `metaform build`, then run `metaform install` to choose a detected supported client. The installer registers a wheel-backed stdio MCP server and probes it. [Getting started](docs/guides/getting-started.md) covers the source and wheel paths, supported installer adapters, submission shape, retained data, and first useful inspection. It also includes a way to inspect the supplied map without running a new model intake.

## Documentation

The [documentation index](docs/README.md) connects the complete set:

- [Getting started](docs/guides/getting-started.md): install, connect, register, perform intake, and inspect the first result.
- [Working with Metaform](docs/guides/working-with-metaform.md): relationships, memory, layers, corrections, project context, GUI, and exchange.
- [Reading an Inference Metaform](docs/guides/reading-a-metaform.md): types, names, receiving purposes, joins, and the project's own functional map.
- [Extending Metaform](docs/guides/extending-metaform.md): build a module using the template, example, and shared facilities.

## Technical

The [preprint](docs/preprint/inference-metaform.md) develops the complete causal account, including exact relational identity, Encounter propagation, lexicalization, provenance, and formation through intent. A [typeset PDF](docs/preprint/inference-metaform.pdf) and [citation information](docs/preprint/CITATION.md) accompany it.

The technical-reference set supplies the deeper engineering account:

| Document | Use it for |
|---|---|
| [REFERENCE.md](docs/inference-metaform/REFERENCE.md) | Full mechanisms, terminology, connected walkthroughs, and functional commitments. |
| [IMPLEMENTATION_MAP.md](docs/inference-metaform/IMPLEMENTATION_MAP.md) | Source correspondence, present behavior, tests, and localized implementation boundaries. |
| [EXAMPLES_TO_COLLECT.md](docs/inference-metaform/EXAMPLES_TO_COLLECT.md) | Original traces and measurements that would make preparation and reuse inspectable. |
| [IDEAS.md](docs/inference-metaform/IDEAS.md) | Separate proposals for additional tools and views. |

This documentation describes the supplied `chassis` source edition at commit `ce9062bdec9398ca1f23ac60684bd3cc7e37f23c`. [Edition and validation notes](docs/EDITION.md) distinguish checked source behavior, local documentation exercises, recorded project material, and intended producers.

## Authorship and independent development

Inference Metaform is the independently developed work of **Rich**. The method grew through six years of hands-on work with AI models, including self-authored context management and semantic rules for inference predating GPT-3's completions API. Rich manually exercised and measured the method and spent six months refining and encoding the present design.

The research connections in the preprint are subsequent comparisons, not the origin of the design. The project is intended for release with its operative intake. Intake integrity concerns preserving how the method operates; it does not depend on a claim that the procedure is unpublished.
