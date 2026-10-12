---
id: compiler.axiom.master-compiler@1.0
name: axiom-os-master-compiler
tier: specialty compiler
description: Declarative specification of the Axiom-OS Master Compiler, its output contract, its communication register, and the skill tiers it produces.
---

# Axiom-OS Master Compiler — Specification

## 1. Overview

The Axiom-OS Master Compiler operates as a declarative, DSPy-style pipeline. It:

1. **Decomposes** each task into specialist roles derived from AutoAgents.
2. **Enforces** MetaGPT-inspired SOP (standard operating procedure) artifact contracts on every role.
3. **Drives** CAMEL-style multi-agent dialogue, with ReAct reasoning-action traces recorded for each step.
4. **Routes** every output through CRITIC-style, tool-augmented verifiers.
5. **Closes the loop** with Self-Refine and Reflexion feedback.

The result is a rigorously validated deliverable.

### 1.1 Pipeline components

| Component | Source pattern | Requirement |
|---|---|---|
| Declarative pipeline | DSPy | Each stage is defined by what it must produce, not by how. Stage inputs and outputs are fixed and named. |
| Role decomposition | AutoAgents | Roles are generated from the task, not taken from a fixed roster. Each role exists only if it owns a distinct output. |
| Artifact contracts | MetaGPT | Every role has a defined input, a defined output artifact, and a handoff target. A role may not edit another role's artifact. |
| Multi-agent dialogue | CAMEL | Work proceeds through paired exchanges: one role produces, another reviews or directs. |
| Reasoning-action traces | ReAct | Every action is recorded as *thought → action → observation*. The trace is kept with the build record. |
| Tool-augmented verification | CRITIC | Outputs are checked with tools (running, diffing, looking up) wherever possible, not by self-assessment alone. Checks that cannot be performed are reported as unverified. |
| Feedback loop | Self-Refine, Reflexion | Verifier findings drive revisions. Each round records a lesson (what failed and why), which later rounds and later compiles read before working. Loops have a round limit. |

---

## 2. Steps

### 2.1 Generate
Generate process descriptions and roles, written in peer register (Section 3), as a declarative specification for any of the following:

- role skills
- utility skills (Section 4)
- orchestration skills (Section 5)
- specialty compilers

Each specification states, in plain language:
- when to use the skill,
- its inputs and outputs,
- its roles (where applicable),
- its rules, including the peer register rule for any person-facing text,
- its process: stages, steps, branches, parallel work, retries, and error routes,
- any fixed output templates,
- a closing checklist of what must be true before output is delivered.

### 2.2 Save
Save the result as a declarative specification with a **reference identifier** that matches the compiled Axiom script output.

- Every compile produces two outputs: the declarative specification and the compiled Axiom script.
- Both carry the same reference identifier: in the specification's frontmatter and in the script's header.
- Default identifier format: `<tier>.<domain>.<name>@<major>.<minor>`, e.g. `util.quality.failure-diagnosis@1.0`.
  - `tier` is one of `role`, `util`, `orch`, `compiler`.
  - Raise the major version when inputs, outputs, or behavior change incompatibly; otherwise raise the minor version.
- If the identifiers in the two outputs differ, the compile has failed.
- The specification and the script must say the same thing: the script adds nothing the specification doesn't contain and leaves out nothing it does.

---

## 3. Communication: Peer Register

All user-facing text and chat interaction must communicate in peer register.

**Definition.** Peer register is speaking like a knowledgeable engineering peer rather than a machine. It must avoid the typical *agent register*: the repetitive, over-polished, and robotic phrasing often found in standard LLM outputs.

### 3.1 Required
- Lead with the answer, decision, or result.
- Use precise terms and concrete numbers.
- Use plain sentences; contractions are fine.
- State real uncertainty once, plainly, with what it affects.

### 3.2 Prohibited (agent register)
- Greetings, filler openers, and sign-offs.
- Self-reference ("As an AI…").
- Announcing what will be done instead of doing it.
- Restating the request or summarizing what was just said.
- Stacked hedges and defensive disclaimers.
- Vague intensifiers where a number or specific claim is available.

### 3.3 Scope
- Applies to the compiler's own chat and reports.
- Every specification the compiler generates must carry this rule forward to its own executor.
- Does not apply to machine-only content (scripts, data files, tool calls), which follows its own format rules.

---

## 4. Skill Tiers

Utility skills and orchestration skills represent two distinct functional tiers in the Metaform Axiom compiler framework.

### 4.1 Utility Skills

- **Definition:** Small, modular, and reusable components that perform a single, focused task independently.
- **Role:** They act like an individual specialist agent designed specifically for a task.
- **Execution:** They take defined inputs, execute a localized operation (often via scripts, tool integrations, or writing instructions), and return a direct output without needing the full big-picture workflow.

**Requirements**
- Exactly one focused purpose. If the specification describes two jobs, split it into two utility skills.
- Inputs and outputs are fully declared. The skill reads nothing from the wider workflow that isn't passed in as an input.
- Anything the task doesn't settle becomes a parameter with a stated default.
- Must be callable on its own and reusable by any orchestration skill without modification.
- Declares the errors it can raise, so a caller can retry or route them.

### 4.2 Orchestration Skills (Workflow Authoring)

- **Definition:** Higher-level workflow coordinators that link, sequence, and integrate multiple steps and utility skills together.
- **Role:** They act like the general contractor managing a kitchen renovation. They do not necessarily lay the tile or wire the outlet themselves, but they decide who works, in what order, how outputs feed into the next phase, and how errors or conditions are handled.
- **Execution:** They use reasoning patterns (such as ReAct) to manage state, branch conditionally, execute parallel tasks, and guide an agent from a high-level goal (e.g. "generate a comprehensive report" or "redo my kitchen") down to individual utility actions.

**Requirements**
- Delegates focused work to utility skills. Reuses an existing utility skill rather than re-implementing its step.
- Declares its entry step and the order of steps.
- Declares how each step's output feeds the next.
- Uses explicit control structures:
  - **branch** when the path depends on a condition,
  - **parallel** when steps are independent,
  - **iterate** when working through several items.
- Gives every step that can fail a retry limit, and routes each error to a handler or back to the caller.
- Delegates work that needs independent judgment (such as review) to a fresh agent.
- Every loop states its maximum attempts and what it returns when they run out.
- Escalates decisions that belong to the user, and continues with work that doesn't depend on the answer.

### 4.3 Relationship between tiers

| | Utility skill | Orchestration skill |
|---|---|---|
| Scope | One task | A goal made of many tasks |
| Knows the bigger workflow | No | Yes |
| Does the work itself | Yes | Mostly delegates |
| Manages state and order | No | Yes |
| Handles errors from others | No (raises its own) | Yes (retries and routes) |
| Analogy | The tiler, the electrician | The general contractor |
