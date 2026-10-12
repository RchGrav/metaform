# Metaform and the Emerging Agentic Systems Stack

## Executive assessment

Metaform is unusually well positioned for the direction the agent ecosystem is taking because the emerging standards are **not converging on a universal “agent protocol.”** They are separating into layers: editor-to-agent interaction, agent-to-tool/context access, agent-to-agent collaboration, capability discovery, user-interface synchronization, and observability. The official A2A documentation now describes this explicitly: MCP is the “vertical” layer that deepens an individual agent with tools and resources, while A2A is the “horizontal” layer that connects independent agents across organizational boundaries. citeturn19view2turn17search23

That creates a natural role for Metaform:

> **Metaform should become the persistent semantic/context plane underneath these protocols, not another protocol competing with them.**

The protocols can be treated as adapters around a stable Metaform domain model. MCP becomes the principal way agents **consume and contribute context**. ACP connects that capability to IDE-hosted coding agents. A2A lets specialist or externally operated agents participate in project work. ARD can advertise and discover those capabilities. MCP Apps and AG-UI provide two complementary ways of presenting Metaform's project model to humans. LSP and similar deterministic code-intelligence systems feed the model. OpenTelemetry supplies the cross-cutting trace plane. An optional containerized **Metaform Node** places those capabilities beside repositories, build environments, databases, or private infrastructure without making cloud deployment mandatory.

The important 2026 development is that this layering has become substantially clearer.

| Layer | Leading technology | What Metaform should use it for | Recommendation |
|---|---|---|---|
| IDE ↔ coding agent | **ACP** | Make Metaform-enhanced agents usable in JetBrains, Zed, and other ACP clients | **Implement** |
| Agent ↔ context/tools | **MCP 2026-07-28** | Primary Metaform context, memory, capability, and workflow interface | **Core priority** |
| Agent ↔ agent | **A2A 1.0.0** | Delegation to specialist and remote agents | **Implement after MCP** |
| Capability discovery | **ARD** | Publish/discover Metaform nodes, MCP servers, agents, and skills | **Prototype now** |
| Embedded agent UI | **MCP Apps** | Portable graph explorers, context inspectors, review interfaces | **High-value feature** |
| First-party agent UI | **AG-UI** | Metaform web workbench, live multi-agent state, steering, HITL | **Strong fit** |
| Code intelligence | **LSP + Metaform bridge** | Populate and refresh functional relationships without LLM rediscovery | **Core ingestion feature** |
| Composed execution | **ATP/code mode** | Run compact programs over many tools/context APIs near the data | **Experiment, not foundation** |
| Observability | **OpenTelemetry GenAI/MCP work** | Trace the entire context and execution path | **Build in from inception** |

There are several corrections to the protocol landscape in the material in the question.

First, **MCP over HTTP/SSE is no longer the forward-looking transport**. Streamable HTTP replaced the older HTTP+SSE transport, and the July 28, 2026 specification goes further: core MCP is now stateless, protocol-level sessions have been removed, GET is no longer part of Streamable HTTP, and requests carry protocol/capability information explicitly. The same release adds discovery, subscription/listening mechanisms, cache metadata, trace propagation, and moves tasks into an official extension. citeturn5view0turn5view1

Second, **A2A is now at released version 1.0.0**, with task lifecycle operations, streaming and push updates, Agent Cards, multiple protocol bindings, signed-card support, and explicit OAuth/OIDC/mTLS security models. citeturn19view0turn18view0

Third, **BeeAI's Agent Communication Protocol should no longer be treated as a separate strategic standard**. Its own documentation now says that ACP has become part of A2A under the Linux Foundation and directs users toward migration. citeturn9view0

Fourth, **JetBrains/Zed ACP v2 is now an important architectural signal even though it remains a draft**. The draft changes ACP from a simple request/response coding-agent channel toward asynchronous sessions, background work, steering, multiple observers, stable update identities, and structured file changes. Crucially, v2 removes several client-side filesystem/terminal APIs and directs agents that need client capabilities toward client-provided MCP servers. That is strong evidence that ACP and MCP are becoming complementary rather than competing layers. citeturn7view0turn7view2

Finally, two important layers were largely absent from the earlier landscape: **Agentic Resource Discovery (ARD)**, announced in June 2026 for cross-protocol discovery and publisher verification, and the emerging agent-to-UI ecosystem represented by **MCP Apps and AG-UI**. citeturn13view0turn16view1turn11view0

The resulting architecture is less “one protocol to rule them all” and much more reminiscent of LSP/DAP-era modularity:

```text
                    HUMAN / DEVELOPER EXPERIENCE
          ┌──────────────────────────────────────────┐
          │ IDEs                Metaform Web UI      │
          │ ACP clients         AG-UI / MCP Apps     │
          └─────────┬──────────────────────┬─────────┘
                    │                      │
                    ▼                      ▼
          ┌──────────────────────────────────────────┐
          │              AGENT RUNTIMES              │
          │ coding agents · specialists · pipelines │
          └─────────┬──────────────────────┬─────────┘
                    │ MCP                  │ A2A
                    ▼                      ▼
          ┌─────────────────┐    ┌───────────────────┐
          │ METAform        │    │ Other agents      │
          │ context plane   │    │ / organizations   │
          └────────┬────────┘    └───────────────────┘
                   │
         ┌─────────┼─────────────────────────────┐
         ▼         ▼                             ▼
       LSP      project artifacts          external tools
     indexes       memory                  MCP / APIs / DBs

          Discovery: ARD          Trace plane: OpenTelemetry
          Execution: containers / sandbox / optional ATP code mode
```

The strategic point is that **Metaform occupies the center rather than an edge of this picture**. None of these standards attempts to define what persistent project understanding means, how derived understanding ages, how one inference should be reused by another agent, or how accumulated project knowledge should be organized around functionality. That remains a layer Metaform can own.

## The protocol stack that is actually emerging

**MCP should be Metaform's primary external context interface.** The current MCP definition is broader than simple “tool calling”: it connects AI applications to external data sources, tools, and workflows. citeturn17search23 For Metaform, the killer application is therefore not a generic collection of utilities. It is a **Project Context Bus** through which any MCP-compatible agent can ask questions about the functional model without understanding Metaform's internal storage.

A sensible mapping is:

| Metaform concept | MCP representation |
|---|---|
| Functional entities and project views | Resources |
| Project snapshots / context packages | Resources |
| Existing decisions and memories | Resources or structured resource views |
| Query functional relationships | Tool |
| Prepare context for a work item | Tool |
| Record an observation or discovery | Tool |
| Attach knowledge to functionality | Tool |
| Request impact analysis inputs | Tool |
| Context preparation recipes | Prompts/workflows where useful |
| Context changes | Subscriptions/listening |
| Interactive project explorer | MCP App |

The July 2026 MCP changes have a direct consequence for Metaform's architecture: **do not make an MCP connection itself the owner of project state**. The protocol deliberately removed protocol-level sessions. Project, branch, revision, workspace, task, and context-snapshot identity should therefore exist in Metaform's own domain model and be explicit in its resource identities or calls. citeturn5view0turn5view1

That is actually beneficial. A project context object can survive agent restarts, model changes, IDE changes, MCP reconnects, A2A handoffs, and cloud/local migrations. It reinforces Metaform's stated purpose: persistent understanding is infrastructure rather than an accidental property of one conversation.

The new MCP discovery, subscription, deterministic listing/caching support, cache lifetime/scope metadata, and OpenTelemetry trace propagation are especially relevant to persistent context services. They provide standard mechanisms that can be used around Metaform's changing context graph rather than inventing Metaform-specific transport behaviors for every client. The same 2026 revision also deprecates older Roots, Sampling, Logging, the legacy HTTP+SSE transport, and dynamic client registration patterns, so new Metaform integration work should target the modern surface instead of carrying those older assumptions forward. citeturn5view0turn5view1

**ACP's killer application is “bring your own coding agent, keep your IDE.”** ACP explicitly models the editor/IDE-to-agent boundary and takes LSP as an architectural analogy. Stable ACP v1 uses JSON-RPC and supports agent sessions and editor integration; session setup can include MCP servers, which provides a particularly clean Metaform insertion point: an ACP-capable IDE can start an arbitrary coding agent and supply the Metaform MCP endpoint as part of that environment. citeturn2view0turn6view2

That means Metaform does **not** have to convince every coding-agent vendor to implement a Metaform SDK. The integration can look like this:

```text
JetBrains / Zed / other ACP client
             │
             │ ACP
             ▼
      Any ACP coding agent
             │
             │ MCP
             ▼
        Metaform context
```

ACP v2 makes the opportunity larger. Its draft supports background work, queueing/steering, multiple clients observing a session, durable update identities, richer streaming tool-call state, and structured add/delete/modify/move/copy file changes. At the same time it removes v1-style client filesystem and terminal APIs in favor of MCP for capabilities the agent needs from the client side. citeturn7view0turn7view2

For Metaform, the development choice should therefore be **ACP v1 compatibility with a deliberately thin adapter, while tracking v2 behind a separable compatibility layer**. Do not put core Metaform functionality into ACP-specific methods. ACP should carry agent/session/user-experience semantics; MCP should carry Metaform's project capabilities. Remote ACP transport remains an evolving area, so it would be premature to make it the network protocol for the proposed cloud node. citeturn7view0turn7view5

**A2A's killer application is delegation across an ownership boundary.** A2A 1.0.0 defines messages, tasks, artifacts, multi-turn contexts, streaming status/artifact events, push notifications, Agent Cards, skills, and multiple network bindings. It supports JSON-RPC, gRPC, and HTTP+JSON/REST bindings and exposes security metadata covering API keys, HTTP authentication, OAuth 2, OpenID Connect, and mutual TLS. citeturn18view0turn19view0

This is where Metaform can move beyond “shared context for one coding agent” into **shared context for an agent organization**.

Consider an implementation task involving an API, PostgreSQL schema, Terraform deployment, and security policy. Metaform should not need to become the agent that makes all four decisions. Instead:

```text
Primary development agent
      │
      ├── Metaform/MCP: obtain functional context
      │
      └── A2A: delegate infrastructure review
                    │
                    ▼
            Infrastructure agent
                    │
                    ├── its own MCP tools
                    └── returns artifact + observations
                              │
                              ▼
                         Metaform memory
```

The A2A specification itself describes this division: MCP supplies an agent with tools/resources, while A2A connects independent agents that discover one another, negotiate interaction, and collaborate on tasks. citeturn19view2

Metaform's functional namespace is particularly useful here. Instead of dumping a transcript into a delegated task, an A2A request can reference the relevant project snapshot and functional entities; the receiving agent can then acquire permitted context through MCP. Returned A2A artifacts can be associated with the same functional entities. **A2A handles delegation; Metaform handles continuity.**

That distinction is important. A database query is not an “agent.” A language server is not an “agent.” A stored project decision is not an “agent.” Converting every capability into A2A would throw away the useful distinction the standards are beginning to establish. Use MCP for deterministic capabilities and information; use A2A where another autonomous system actually owns part of the reasoning or work.

**ARD's killer application is effectively DNS/search for the agentic capability layer.** Google's June 17, 2026 announcement defines Agentic Resource Discovery as an open specification for publishing, discovering, and verifying tools, skills, and agents independently of their native protocol. An organization publishes an `ai-catalog.json`-style catalog under its domain; federated registries can index those catalogs; resources may point to MCP servers, A2A agents, OpenAPI services, or nested catalogs; discovery ultimately hands control to the resource's native protocol. citeturn13view0

This is an excellent match for Metaform's modular chassis.

A future Metaform capability registry could maintain one internal record such as:

```text
Capability
 ├─ stable identity
 ├─ project / organization / module association
 ├─ description and functional purpose
 ├─ native interface
 │    ├─ MCP server
 │    ├─ A2A agent
 │    ├─ OpenAPI service
 │    └─ Metaform module
 ├─ version
 ├─ deployment location
 └─ trust / provenance metadata
```

From that record Metaform could emit the appropriate MCP metadata, A2A Agent Card, and ARD catalog entry instead of maintaining three disconnected registries. That would turn Metaform's functional model into a **capability namespace as well as a project namespace**.

ARD is substantially newer than MCP and A2A, so I would treat it as a prototype target rather than make the platform depend upon it. Its architectural idea, however—federated discovery with direct handoff to native protocols—is strong and aligns almost perfectly with Metaform's goal of remaining independent of any one agent ecosystem. ARD also explicitly distinguishes discovery from execution and can represent multiple protocol families rather than replacing them. citeturn13view0

**MCP Apps' killer application for Metaform is the Context Inspector.** MCP Apps became the first official MCP extension in January 2026 and allows an MCP tool to associate an interactive HTML UI resource with its result. Hosts render that UI in a sandboxed iframe and communicate with it bidirectionally over a JSON-RPC dialect using `postMessage`. The current documentation describes interactive dashboards, data exploration, forms, real-time monitoring, document review, and multi-step workflows as first-class use cases. citeturn16view1turn16view2

A Metaform MCP App could make otherwise invisible context infrastructure tangible:

```text
┌──────────────── Metaform Context Inspector ────────────────┐
│                                                            │
│  [ Authentication ] ──depends on──> [ Session Management ] │
│          │                              │                  │
│          │ implemented by               │ affected by      │
│          ▼                              ▼                  │
│      auth/*.ts                    recent change #837       │
│                                                            │
│ Context snapshot: 9f32…        freshness: current          │
│ Existing decisions: 4          observations: 11            │
│ Derived relationships: 27      stale inferences: 2         │
│                                                            │
│ [inspect evidence] [compare snapshot] [attach observation] │
└────────────────────────────────────────────────────────────┘
```

This could run *inside* external agent products rather than requiring users to switch to a Metaform application. MCP Apps now has support across multiple major hosts, and its sandbox, permission, CSP, and host-mediated communication model makes it specifically intended for third-party UI delivered through MCP. citeturn16view1

**AG-UI solves a different problem and is complementary.** AG-UI defines an event-based protocol between an agent backend and a user-facing application, covering streaming interaction, state synchronization, frontend tools, human-in-the-loop interrupts, agent/tool events, and generative or dynamically updated UI patterns. Its reference architecture supports transports such as SSE, WebSockets, and webhooks. citeturn11view0turn11view1

For Metaform:

- **MCP Apps** are how Metaform injects portable mini-applications into somebody else's agent host.
- **AG-UI** is how Metaform could build its own rich, model-independent agent/context workbench.

That workbench could show several concurrent agents, their tasks, the context each received, project-state changes, memories produced, context invalidations, and pending human interactions without coupling the UI to one particular agent framework.

**Monday.com's ATP has an interesting killer application, but it should be treated as an execution pattern rather than an ecosystem foundation.** ATP's project describes code-first tool use: an agent generates JavaScript/TypeScript that executes in an isolated V8 environment, allowing multiple calls, data transformations, batching, and parallel operations before returning a reduced result. The project includes SDK services for approvals, caching, logging and other runtime facilities and advertises OpenAPI and MCP compatibility. citeturn9view2

The idea is highly relevant to Metaform even if ATP itself never becomes a dominant protocol. Imagine an agent asking:

> Find every functional component transitively dependent on authentication, correlate each with changed symbols since snapshot X, attach unresolved decisions, and return only components with test coverage below the project baseline.

Making the model invoke thirty separate tools would be a poor interface. Giving it a small sandboxed Metaform SDK lets it perform the joins near the data and return a compact structured result.

So the feature worth adopting is **code mode over Metaform context**, not necessarily ATP as a hard dependency.

The older **Agent Protocol** remains useful context but should be lower priority. The original AI Engineer Foundation repository now redirects to AGI, Inc., describes itself as a common agent API, and defines a relatively minimal REST/OpenAPI task/step model such as task creation and step execution. citeturn16view0 A2A now covers a considerably richer standardized peer-agent/task boundary, so I would support Agent Protocol only where compatibility demand exists rather than make it part of Metaform's architectural core.

## Metaform-specific capabilities that can become the real differentiator

Protocols will commoditize connectivity. **Metaform's defensible value is what happens before and between protocol calls.**

The most important product opportunity is what I would call a **Context Compiler**.

A conventional RAG system asks approximately:

> Which stored chunks are semantically similar to this query?

Metaform can ask a much richer question:

> Given this project snapshot, this portion of the functional model, this work item, the known relationships, accumulated observations, established decisions, and current implementation state, what existing understanding is relevant to the agent that is about to work here?

That aligns directly with the platform's inference-first premise. It does not tell the agent what decision to make. It compiles the **already-known environment in which the decision should be made**.

A context package might conceptually contain:

```text
ContextPackage
    project snapshot
    functional entities in scope
    relationships among those entities
    implementation artifacts
    known current state
    relevant prior decisions
    relevant observations / discoveries
    active work and recent changes
    provenance for each assertion
    freshness / invalidation state
```

The same package can be consumed by an MCP client, attached to an A2A task, visualized by an MCP App, presented in an AG-UI application, or inspected from an IDE. The internal object remains Metaform's; protocol representations are projections of it.

This leads to several high-value features.

**Stable functional identity independent of files is foundational.** A function may move files. A subsystem can be rewritten. A repository can be reorganized. If Metaform's primary identities are files, paths, or chat messages, the accumulated understanding fractures whenever implementation structure changes. Functional entities should instead have durable identities, with source artifacts treated as evidence or implementations of those entities.

That also makes inter-agent communication much cleaner:

```text
"auth.login.session-validation"
```

is a more durable reference than:

```text
src/services/security/login/sessionValidator.ts lines 42–138
```

The latter can still be evidence behind the former.

**Provenance should be first-class rather than decorative.** Every reusable inference should be capable of answering, at minimum, “what was this derived from?” and “against which project state?” This is especially important because the central Metaform proposition is reuse. Reusing an inference ten times magnifies its value when correct—and magnifies its damage when stale.

A practical provenance chain could look like:

```text
Functional assertion
       │
       ├── derived from source snapshot 4c18…
       ├── derived from architecture.md revision …
       ├── observed by ingestion pipeline version …
       └── subsequently confirmed by agent run …
```

This is not something MCP, ACP, or A2A attempts to model semantically. Those protocols can transport the resulting information, but Metaform can own its lifecycle.

**Incremental invalidation is potentially one of Metaform's killer features.** When source state changes, the goal should not be “re-understand the repository.” Metaform should be able to identify which derived understanding depended upon what changed, mark that portion of context stale, and recompute only what has become questionable.

That produces a useful amortization loop:

```text
source change
     ↓
deterministic analysis
     ↓
affected functional entities
     ↓
invalidate dependent inference
     ↓
targeted re-analysis
     ↓
new project snapshot
```

This is where **LSP should become an ingestion substrate, not merely another agent tool**. Microsoft's LSP separates editors from language-specific semantic services and exposes language/workspace features through a standardized protocol. citeturn15view1 Rather than having every agent read source text to reconstruct basic program semantics, a Metaform pipeline can consume language-server results while building or refreshing the functional graph.

There are two distinct opportunities:

```text
Persistent path:
Source → LSP/static analysis → Metaform functional model
                            → reusable inference

Live path:
Agent → Metaform MCP → live language server query
                    → current deterministic answer
```

This is more powerful than simply wrapping an LSP server with MCP. A thin “LSP-over-MCP” adapter can certainly give an agent efficient live semantic navigation, but **Metaform can amortize those same deterministic facts across every future agent** by incorporating them into project understanding.

That suggests a useful rule:

> Deterministic semantic analysis should be performed before probabilistic inference whenever it can establish the same fact.

The model then spends reasoning capacity on things the compiler, language server, dependency graph, Git history, or project metadata cannot determine.

**Context diffs are another high-value feature.** Agents frequently do not need the entire current project model; they need to know what changed since the context they already saw.

Metaform should be able to express:

```text
context(snapshot B) - context(snapshot A)
```

in semantic rather than merely textual terms:

```text
+ capability: refresh-token rotation
~ authentication/session now depends on key-management
~ database migration changed persisted token representation
- legacy session invalidation path
! prior inference "tokens are stateless" became stale
```

That could drastically reduce the need for repeated project-wide analysis and is almost a literal implementation of amortized inference.

**Agent write-back should be a core protocol-independent operation.** Metaform's own description already has the right conceptual categories: agents consume context, make discoveries, record observations, contribute decisions and progress, and improve the environment for later work.

The important design point is to preserve distinctions between these kinds of knowledge. An agent saying “I observed X” is different from “the project has decided X,” and both are different from “pipeline Y inferred X from these source artifacts.” Metaform should retain those semantics internally even where an external protocol reduces everything to generic JSON or textual content.

**Context budgeting should become explicit.** A Metaform context compiler can have 50,000 useful facts while an agent only has room or reason for 100 of them. The service should therefore be able to produce context at varying resolutions:

```text
functional overview
      ↓
relevant components
      ↓
important relationships
      ↓
specific implementation evidence
      ↓
raw artifacts only when needed
```

This is where Metaform can outperform generic retrieval: the system knows not only *which* facts may be relevant, but their place in a functional hierarchy and their evidentiary relationship to the work.

**Capability discovery should use the same functional namespace.** ARD's cross-protocol catalogs and A2A's Agent Cards both create a world in which agents can discover capabilities dynamically. citeturn13view0turn18view0 Metaform can improve on simple keyword capability registries because it already knows what a capability contributes to.

For example:

```text
functional entity:
    deployment.database.schema-migration

available capabilities:
    MCP: postgres-schema-reader
    MCP: migration-history
    A2A: DBA specialist agent
    module: migration-impact-analyzer
```

That is substantially more useful than presenting an agent with an undifferentiated list of 250 tools.

## The optional Metaform Node for local, edge, and cloud operation

I would add a deployable component named something deliberately generic such as **Metaform Node**.

Its purpose should be very narrow:

> **Place the Metaform context and protocol surface near the project or systems whose context it represents.**

It should not be required for Metaform itself.

The same container image could operate in several locations:

| Location | Why it is useful |
|---|---|
| Developer machine | Local repositories, LSPs, CLI tools, low latency |
| Devcontainer | Reproducible project-specific environment |
| CI runner | Analyze changes and update project understanding during builds |
| Cloud workspace | Support remote coding agents and ephemeral development environments |
| Customer VPC | Reach internal repositories, databases, observability systems, APIs |
| Remote site / edge | Keep expensive or sensitive raw data close to its source |

The core topology would be:

```text
                      ┌─────────────────────────┐
                      │     Metaform Core       │
                      │ project model / memory  │
                      │ orchestration / modules │
                      └────────────┬────────────┘
                                   │
                              sync / API
                                   │
                 ┌─────────────────▼──────────────────┐
                 │          Metaform Node             │
                 │                                    │
                 │  Protocol adapters                 │
                 │   • MCP stdio                      │
                 │   • MCP Streamable HTTP            │
                 │   • A2A                            │
                 │   • ARD catalog                    │
                 │   • optional AG-UI backend         │
                 │                                    │
                 │  Context services                  │
                 │   • local cache / snapshots        │
                 │   • functional graph projection    │
                 │   • memory / write-back adapter    │
                 │                                    │
                 │  Project intelligence              │
                 │   • Git                            │
                 │   • LSP servers                    │
                 │   • local Metaform modules         │
                 │                                    │
                 │  Optional execution                │
                 │   • sandbox/code mode              │
                 │   • external MCP servers           │
                 │                                    │
                 │  OpenTelemetry                     │
                 └───────────┬───────────┬────────────┘
                             │           │
                             ▼           ▼
                         repository   private systems
```

For MCP, the node should support **stdio when colocated with the agent and modern Streamable HTTP when networked**. The current specification specifically defines Streamable HTTP around a single HTTP endpoint and no longer relies on the older HTTP+SSE model or persistent protocol sessions. citeturn5view1

This gives Metaform one deployment artifact without turning “cloud” into an architectural prerequisite:

```text
metaform-node on laptop
        =
metaform-node in Docker
        =
metaform-node in cloud workspace
        =
metaform-node inside private VPC
```

Only configuration and available adapters change.

The killer application for a remote Node is **moving inference to the data instead of moving all data to the inference**.

A node inside a private engineering environment might see a million-line repository, internal architecture documentation, a PostgreSQL catalog, deployment metadata, and language servers. It can use those sources to maintain Metaform's structured understanding and expose the compact resulting context externally. An agent does not necessarily need every raw artifact transferred into its environment.

This architecture becomes particularly valuable with cloud-hosted coding agents. A remote agent can call the Metaform Node over MCP, while the Node performs LSP queries, project analysis, local searches, or context graph operations close to the repository.

A2A can be exposed from the same Node where there are actual autonomous Metaform-hosted services worth delegating to. For example:

```text
Metaform Context Curator Agent
Metaform Impact Analysis Agent
Metaform Project Historian Agent
Metaform Architecture Analysis Agent
```

Those would be genuine agents because they own a reasoning process. Ordinary context queries should remain MCP operations.

ARD can make the node discoverable. ARD specifically allows catalogs to advertise MCP servers, A2A agents, OpenAPI tools and other catalogs, with the eventual client connecting using the advertised native protocol. citeturn13view0 That makes an ARD publisher almost trivial once Metaform has a first-class internal capability registry.

ACP should **not** initially be the Node's remote network interface. Stable ACP is fundamentally optimized around editor/agent integration and local subprocess communication, while remote transport remains an area of active protocol evolution. citeturn2view0turn7view5 A cleaner initial topology is:

```text
IDE ──ACP── local/remote coding agent ──MCP── Metaform Node
```

rather than:

```text
IDE ──remote ACP── Metaform infrastructure
```

That maintains the layer boundaries instead of asking ACP to solve a problem already handled by MCP's remote transport.

For execution, the Node should have an optional **code-mode service** rather than force every context operation through one-call-at-a-time tools. ATP's V8 model illustrates the benefit: execute a small program against several available capabilities, perform filtering/transformation within the sandbox, and return the condensed result to the model. Those latency/token advantages are claims of the ATP project rather than a broadly established standard, but the architectural pattern is sound enough to prototype. citeturn9view2

A useful Metaform-specific version might expose an SDK conceptually like:

```javascript
const auth = await metaform.functions.get("authentication");

const affected = await metaform.graph.transitiveDependents(auth.id);

const changes = await metaform.changes.since(context.snapshot);

return affected
  .filter(component => changes.affects(component))
  .map(component => ({
    id: component.id,
    purpose: component.purpose,
    change: changes.for(component),
    decisions: metaform.memory.decisions(component.id)
  }));
```

The architectural point is not JavaScript itself. The point is **data reduction before model context**.

## Security, identity, trust, and observability

The standards are making real progress here, but the ecosystem has **not** converged on a universal cryptographic “agent intent” standard. That distinction matters.

A2A 1.0 defines explicit authentication schemes, authenticated/extended Agent Cards, card signatures, encrypted production transports, OAuth/OIDC/mTLS support, authorization behavior, and in-task authorization. citeturn18view0turn19view0 ARD adds publisher and capability verification using domain-hosted catalogs and cryptographic trust metadata. citeturn13view0 MCP's recent revisions have hardened authorization and moved away from older dynamic-client-registration assumptions. citeturn5view0

Those mechanisms answer questions such as:

> Who published this capability?

> Which endpoint belongs to it?

> Who authenticated?

> Which credentials or security scheme are required?

They do **not**, by themselves, prove:

> The human intended this exact semantic action.

> The agent's reasoning was correct.

> The capability is safe.

> The information it returned is true.

> A signed Agent Card makes the agent trustworthy.

That gap remains an active area. NIST's NCCoE is itself exploring software and AI agent identity and authorization, which is evidence that this broader problem is still developing rather than settled into one universal standard. citeturn17search17

Metaform should therefore distinguish **identity, authorization, provenance, and semantic trust** rather than combine them into one “trusted” flag.

A useful internal event could preserve the information the underlying systems actually supplied:

```text
Activity
    actor identity
    delegating identity, when supplied
    protocol
    protocol task/request IDs
    project snapshot
    functional entities concerned
    request as received
    authorization evidence/reference
    capabilities invoked
    artifacts read
    artifacts produced
    Metaform context read
    Metaform knowledge written
    trace/span IDs
    timestamp
```

The important part is preserving the request and evidence rather than inventing additional semantic restrictions that were not present in the originating intent.

**Provenance is particularly important for agent-generated memory.** Metaform should know whether an item originated from source inspection, a deterministic analyzer, a human, an external A2A agent, an MCP tool result, or model inference. That gives future agents a rational basis for deciding how much reliance to place upon it without Metaform dictating the agent's conclusion.

For cross-organizational discovery, A2A documentation warns against embedding static secrets in public Agent Cards and provides authenticated extended cards for information requiring controlled access. citeturn8view3turn18view0 ARD similarly separates discovery/trust metadata from the native connection that follows discovery. citeturn13view0 Metaform's capability registry should preserve that division: **descriptions and endpoints are metadata; credentials remain credentials.**

MCP Apps provide another valuable security boundary. The official extension uses sandboxed iframes, controlled permissions and CSP metadata, and host-mediated JSON-RPC communication; hosts can control tool access and user consent around UI-initiated operations. citeturn16view1turn16view2 That is considerably preferable to letting an arbitrary visualization returned by a context server execute as privileged IDE or host code.

Observability should be treated as a first-class Metaform interface rather than something bolted on later. The 2026 MCP specification explicitly adds OpenTelemetry trace-context propagation, while OpenTelemetry's semantic-convention work now contains dedicated Generative AI, agent, and MCP areas and has moved ongoing GenAI convention work into its dedicated repository. citeturn5view0turn15view0

A single trace should ideally be able to follow:

```text
developer
   │
   ▼
ACP prompt/session
   │
   ▼
coding agent
   │
   ├── MCP context request
   │       │
   │       ▼
   │   Metaform context compilation
   │       │
   │       ├── LSP query
   │       ├── memory lookup
   │       └── graph traversal
   │
   ├── A2A delegation
   │       │
   │       ▼
   │   specialist agent
   │       │
   │       └── MCP tools
   │
   ▼
agent result
   │
   ▼
Metaform knowledge write-back
```

That trace is more than operational debugging. It can reveal whether Metaform is actually delivering on **amortized inference**.

Metaform-specific metrics could include:

| Metric | What it tells you |
|---|---|
| Context reuse count | How often previously inferred knowledge is reused |
| Context rebuild avoidance | How much analysis was not repeated |
| Context compilation latency | Cost of preparing reusable context |
| Context package size | How much information agents actually receive |
| Source-to-context freshness lag | Time before project understanding catches up with changes |
| Invalidation rate | How much existing inference becomes stale after changes |
| Targeted recomputation ratio | Whether updates avoid project-wide reanalysis |
| Context cache hit rate | Reuse at the infrastructure layer |
| Agent write-back volume | How much useful knowledge agents contribute |
| Cross-agent reuse | Whether one agent's learning helps subsequent agents |
| Evidence depth | Whether conclusions remain traceable to underlying artifacts |

The most interesting Metaform KPI may ultimately be an **inference amortization ratio**: how much reusable understanding is consumed relative to the cost of producing and maintaining it. That would measure the platform by its central thesis rather than generic token counts.

## What developers should build into Metaform tooling

The following features have the highest leverage because they remain useful regardless of which model, agent framework, or IDE wins.

| Feature | Why it matters | Standards leveraged | Priority |
|---|---|---|---|
| Protocol-neutral functional object model | Prevents Metaform's semantics from being defined by any transport | All | **Foundational** |
| Stable functional IDs | Lets context survive file moves, rewrites, agents, and sessions | MCP, A2A | **Foundational** |
| Project/context snapshots | Makes accumulated inference reproducible and comparable | MCP, A2A | **Foundational** |
| Provenance graph | Makes reused inference inspectable and invalidatable | MCP + OTel | **Foundational** |
| Context Compiler | Converts persistent understanding into task-relevant packages | MCP | **Killer feature** |
| Semantic context diff | Gives agents “what changed” rather than project rediscovery | MCP | **Killer feature** |
| Dependency-driven invalidation | Recomputes only context affected by project change | LSP + Metaform | **Killer feature** |
| Typed agent write-back | Accumulates discoveries, decisions, observations and progress without conflating them | MCP/A2A | **High** |
| MCP server, current spec | Makes Metaform universally consumable by agents | MCP 2026-07-28 | **Immediate** |
| MCP stdio + Streamable HTTP | Same capability locally and remotely | MCP | **Immediate** |
| MCP Apps Context Inspector | Makes context/provenance understandable to humans in agent hosts | MCP Apps | **High** |
| Thin ACP adapter | Gives IDE independence without duplicating context APIs | ACP + MCP | **High** |
| ACP v2 compatibility layer | Prepares for persistent/background/multi-client coding sessions | ACP v2 draft | **Track now** |
| LSP ingestion bridge | Converts deterministic code semantics into reusable understanding | LSP | **High** |
| A2A client/server | Enables specialist agent delegation and federation | A2A 1.0 | **Next** |
| Capability registry | One internal model for tools, modules, agents, endpoints and skills | MCP/A2A/ARD | **High** |
| ARD catalog publisher | Makes Metaform resources discoverable outside one platform | ARD | **Prototype** |
| AG-UI event adapter | Enables a rich first-party Metaform operations/context UI | AG-UI | **Next** |
| Optional code mode | Reduces multi-tool chatter for complex context queries | ATP-inspired | **Experimental** |
| OpenTelemetry propagation | Makes distributed agent/context work debuggable | OTel/MCP | **Immediate** |
| Metaform Node container | Moves context services near projects and private systems | MCP/A2A/ARD | **High** |

There is also a useful architectural rule hiding inside this table:

> **Build protocol support around Metaform's semantics; do not encode Metaform's semantics inside the protocols.**

For example, the same internal `FunctionalEntity` might appear as an MCP resource, be referenced by an A2A artifact, appear as a node in an MCP App, be rendered in an AG-UI frontend, or contribute metadata to an ARD capability. None of those should become its authoritative representation.

That insulation is valuable because the standards are still moving. ACP v2 is already substantially different from v1. MCP's July 2026 release changed core lifecycle and transport assumptions. A2A reached 1.0 with breaking representation changes relative to its pre-1.0 versions. citeturn7view0turn5view0turn19view0 Metaform should expect protocol evolution and make adapters replaceable.

## Recommended build sequence and product direction

The strongest near-term design is to make **Metaform itself the persistent context engine and Metaform Node the universal deployment surface**.

**Build first: the context plane.** Establish stable functional identities, project snapshots, provenance/derivation relationships, memory types, contextual write-back, semantic diffs, and targeted invalidation. These are the pieces no external protocol will provide for Metaform.

On top of that, build a **current-spec MCP surface** supporting local stdio and remote Streamable HTTP. Avoid legacy HTTP+SSE assumptions and avoid making protocol session identity part of Metaform state. Design the resource namespace so that a context artifact identifies its project and snapshot independently of the connection carrying it. The July 2026 MCP direction strongly supports this stateless, explicitly identified design. citeturn5view0turn5view1

The first genuinely compelling external feature should be a **Metaform Context Compiler over MCP**:

```text
agent task
   │
   ▼
functional scope resolution
   │
   ├── project structure
   ├── implementation state
   ├── relationships
   ├── prior decisions
   ├── observations
   ├── recent changes
   └── provenance
   │
   ▼
compact ContextPackage
   │
   ▼
agent reasons about the actual task
```

That directly demonstrates Metaform's value proposition: *reason once about what can be understood independently of the task; reuse that understanding when the task arrives.*

The next visible feature should be the **MCP Apps Context Inspector**, because the abstract notion of “persistent inferred context” will otherwise be difficult for developers to inspect and trust. MCP Apps now provides a standardized portable mechanism for dashboards, explorers, forms, live state and multi-step interactions inside several agent hosts. citeturn16view1turn16view2

Alongside that, implement **LSP-backed continuous understanding**. Let deterministic code intelligence update the functional graph and trigger targeted re-inference when implementation relationships change. The agent should benefit from a language server without having to know that a language server was involved.

Then add the **ACP adapter**, but keep it intentionally thin. Its killer feature is not another agent runtime; it is that an ACP editor can run its preferred coding agent while Metaform arrives as standard MCP context. The direction of ACP v2—shifting client-side capabilities toward MCP—makes that separation increasingly natural. citeturn7view2

The **Metaform Node** should arrive at roughly the same stage. The minimum valuable container is not an enormous orchestration stack. It is:

```text
Metaform Node
    context API
    MCP stdio / Streamable HTTP
    project adapter
    Git adapter
    LSP integration
    local context cache
    protocol-neutral capability registry
    OpenTelemetry
    sync to Metaform core when configured
```

That gives developers an immediately useful deployment unit on a laptop, in a devcontainer, CI, a cloud coding workspace, or an internal network.

After this base is stable, **A2A becomes much more valuable**, because Metaform then has something durable to preserve across agent handoffs. Implement A2A v1 as a genuine agent boundary: tasks and artifacts should reference Metaform project/context identities, while participating agents retrieve detailed context as needed via MCP. A2A's task, artifact, streaming, Agent Card, security, and protocol-binding model is now mature enough to make this a reasonable production integration target. citeturn18view0turn19view0

Then publish the Node and its modules through **ARD**. Because ARD can advertise MCP, A2A and OpenAPI resources without replacing their native protocols, Metaform can become both a source and an index of capabilities. citeturn13view0 An organization could eventually ask Metaform something conceptually like:

> “What systems or agents do we already have that understand database migration impact?”

and receive capabilities tied to the same functional model that describes the project.

For Metaform's own richer interface, add **AG-UI** as the backend/frontend event layer. That workbench can become the human observability surface for persistent context, concurrent work, agent handoffs, changes, provenance and memory rather than merely another chat window. AG-UI's emphasis on bidirectional state, frontend tool calls, event streaming and human interaction makes it much better suited to that role than inventing another proprietary streaming protocol. citeturn11view0turn11view1

Finally, prototype **code mode** using the useful architectural idea behind ATP: allow agents to execute compact programs against a bounded Metaform SDK so that graph traversal, joining, filtering and reduction occur beside the data. ATP itself is still much less established than MCP or A2A, so Metaform should not require it for interoperability. citeturn9view2

The protocols that should **not** drive new core architecture are the older BeeAI Agent Communication Protocol and the original Agent Protocol. BeeAI's own project has converged into A2A, while Agent Protocol remains a simpler REST task/step abstraction that now overlaps considerably with the richer A2A boundary. citeturn9view0turn16view0 Compatibility can be added when there is a concrete consumer.

The resulting product direction is coherent:

```text
                         METAform

        ┌──────────────── Persistent Understanding ───────────────┐
        │                                                        │
        │ Functional model                                       │
        │ Context graph                                          │
        │ Persistent memory                                      │
        │ Provenance                                             │
        │ Project snapshots                                      │
        │ Semantic change / invalidation                         │
        │ Context compilation                                    │
        │ Capability registry                                    │
        │ Continuous inference pipelines                         │
        │                                                        │
        └───────────────────────┬────────────────────────────────┘
                                │
                       protocol adapters
                                │
          ┌───────────┬─────────┼────────┬───────────┐
          ▼           ▼         ▼        ▼           ▼
         MCP         ACP       A2A      ARD       AG-UI
          │           │         │        │           │
       agents       IDEs    agents/orgs discovery   UI
          │
       MCP Apps
          │
       rich UI

     Inputs: Git · LSP · docs · APIs · DBs · modules · agents
     Trace: OpenTelemetry
     Deployment: embedded · local Metaform Node · cloud · private edge
```

This architecture preserves the philosophical distinction at the center of Metaform.

**MCP does not decide what the agent should do; it makes accumulated understanding available. ACP does not dictate which agent the developer uses; it decouples the editor from the agent. A2A does not require Metaform to control another agent's reasoning; it creates a delegation boundary. ARD does not determine which capability is correct; it makes capabilities discoverable. LSP does not reason about the project; it establishes deterministic facts that need not be inferred repeatedly.**

Metaform can sit beneath all of them and do the thing the emerging standards deliberately leave undefined:

> **accumulate project understanding, keep it attached to a durable functional model, know where that understanding came from and when it became stale, prepare the relevant portion for whoever is working next, and preserve what that work teaches the system.**

That is a substantially more durable strategic position than building another agent framework. As of October 12, 2026, the standards landscape is increasingly moving toward interchangeable agents, editors, tools, discovery systems and user interfaces. MCP's evolving stateless context/tool boundary, ACP's movement toward cleaner MCP separation, A2A's released peer-agent layer, ARD's new cross-protocol discovery model, and the emergence of MCP Apps and AG-UI all point in the same direction. citeturn5view0turn7view2turn19view0turn13view0turn16view1turn11view0

**Metaform's opportunity is to make the understanding underneath those interchangeable components persistent.**