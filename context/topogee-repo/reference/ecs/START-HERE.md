# Start here — review guide

This archive is a **proposal for review**, not an instruction to replace your existing Metaform or a claim that the system has been implemented.

## What is in it?

1. **`01-triage-report.md` — Short.** What was kept, corrected, or deferred. Start here for the summary of editorial choices.
2. **`02-inference-metaform-revised.md` — Academic paper.** The conceptual argument: infer functional understanding once and make it reusable for later reasoning. This is about Metaform, not Bevy.
3. **`03-technical-specification.md` — Working system design.** Proposed graph schema, context selection, agent context/handoffs, MCP contract, virtual and physical sensor adapters, events, and document recomposition. It contains architectural decisions that are *recommendations*, not all existing implementation facts.
4. **`Inference-Metaform-Revised-Paper-and-Specification.md` — All three in one file.** It is generated from the numbered files, rather than a different manuscript.
5. **`contracts/` — Proposed machine-readable artifacts.** Only needed when examining the proposed build interfaces. **`verification/`** records limited checks, not end-to-end certification.

## One key correction

The earlier notes invented an **ECR / Entity-Component-Resource** framework label. **ECS (Entity-Component-System)** is the established name for an engine design such as Bevy. In Bevy, **Resources** are shared data accessible to systems. Metaform's functional map is **not** an ECS engine, and LadybugDB stores functional elements, receiving-purpose Joins and attached knowledge, not Bevy entities/components. Virtual 3D runtimes *may* be implemented with ECS, but neither physical sensors nor Metaform's functional graph need ECS.

## Three different things that must not be conflated

- **Functional organization** — Metaform Addresses and RE-owned Joins say what parts contribute to an artifact, to whom, why, and through what Encounter Function. LadybugDB/Cypher is the selected graph store/query arrangement.
- **Context presentation** — When an agent is at a functional or spatial place, the system selects relevant previously prepared knowledge, tickets, specifications, documentation and skills. This is an efficiency and relevance mechanism, *not* a permission or isolation system; all agents can navigate to other Addresses.
- **Environment execution** — A simulated engine may use Bevy ECS and Resources. A real 8×8 ToF sensor uses a hardware adapter. Both can normalize observations to a shared MCP data contract. Local reflexes operate at the device/engine rate; events can cause the host to initiate a later agent turn.

## How to review

Read the paper first for the *theory* and the technical specification afterwards for the *proposed implementation*. Any claim about actual performance, sensor equivalence, database query correctness or MCP/ACP integration should be considered **unverified** unless an explicit test record supports it. The decisions near the end of the specification are choices to consider, not requirements that you have already endorsed.

The supplied source documents are listed in `sources.md`. This revised archive **does not modify the Metaform codebase**. It is delivered for inspection only.
