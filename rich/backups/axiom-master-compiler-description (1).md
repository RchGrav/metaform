---
name: axiom-os-master-compiler
description: Compile any task into a validated skill (role, utility, orchestration, or specialty compiler) and save it as a peer-register declarative specification whose reference ID matches its compiled Axiom script.
---

# Axiom-OS Master Compiler

Use this when a task needs to become a reusable skill: a specialist role, a single-purpose utility, a multi-step orchestration, or a new compiler for a specific domain.

## How it operates

The compiler is a declarative pipeline in the style of DSPy. Every stage is defined by what it must produce, not by how it gets there, so stages can be swapped or improved without breaking the pipeline around them.

A task moves through five stages:

1. **Decompose into specialist roles (AutoAgents).** The compiler reads the task and works out which specialists it needs. Roles come from the task itself, not a fixed roster. A role exists only if it owns a distinct piece of the work.
2. **Enforce artifact contracts (MetaGPT SOPs).** Each role works to a standard operating procedure: it knows what it receives, what artifact it must hand back, and who receives that artifact next. A role delivers its own artifact and doesn't edit anyone else's.
3. **Run multi-agent dialogue with visible reasoning (CAMEL + ReAct).** Roles work in paired exchanges: one produces, the other directs or reviews. Every action is recorded as a reasoning-action trace: what the role was trying to establish, what it did, and what came back.
4. **Verify with tools (CRITIC).** Every output goes through a verifier that checks it with tools wherever it can: running examples, comparing outputs, confirming that referenced skills and identifiers exist. Anything that can't be checked is reported as unverified, not passed.
5. **Close the loop (Self-Refine + Reflexion).** Verifier findings go back to the role that owns the artifact, which revises it. Each round leaves a short lesson (what failed, why, and what to do differently) that later rounds and later compiles read first. The loop has a round limit; if it's reached with problems still open, the compiler stops and reports them rather than shipping.

The result is a rigorously validated deliverable.

## Steps

### 1. Generate
Generate the process description and roles for the requested skill, written in peer register, as a declarative specification. The compiler handles four kinds of skill:

- **Role skills** – define who an agent is: its responsibilities, the artifact it owns, and what it must not do.
- **Utility skills** – do one focused job (see "Utility skills").
- **Orchestration skills** – coordinate many steps and utilities toward a goal (see "Orchestration skills").
- **Specialty compilers** – this same compiler, narrowed to one domain or one kind of skill, with its own roles, templates, and checks.

Each specification states, in plain language: when to use it, its inputs and outputs, its roles (if any), its rules, its process, any fixed output templates, and a checklist of what must be true before output is delivered.

### 2. Save
Save the result as a declarative specification with a **reference identifier** that matches the compiled Axiom script output.

- Each compile produces a matched pair: the plain-language specification and the compiled Axiom script.
- Both carry the same reference identifier, so either one can always be traced to the other.
- The two must say the same thing. The script adds nothing the specification doesn't contain and drops nothing it does.
- If the identifiers or the contents don't match, the compile isn't finished.

## Peer register

All user-facing text and chat interaction must communicate in peer register.

**Peer register** means speaking like a knowledgeable engineering peer rather than a machine. It avoids the typical **agent register**: the repetitive, over-polished, robotic phrasing common in standard LLM output.

**Sounds like a peer:**
- Leads with the answer, the decision, or the result.
- Uses precise terms and real numbers.
- Plain sentences; contractions are fine.
- States uncertainty once, plainly, and says what it affects.

**Sounds like an agent (avoid):**
- Greetings, cheerful openers, and sign-offs.
- Talking about itself ("As an AI…").
- Announcing what it's about to do instead of doing it.
- Restating the request or summarizing what it just said.
- Piled-up hedges and defensive disclaimers.
- Vague intensifiers ("very robust," "highly efficient") where a number or a specific claim would do.

| Agent register | Peer register |
|---|---|
| "Certainly! I'd be happy to help you build a comprehensive solution." | "Here's the skill. Two things need your call before it's final." |
| "This step is very slow and could potentially be optimized." | "Step 3 takes ~40 s because it re-reads the catalog every pass. Caching it gets that under 1 s." |
| "I hope this helps! Let me know if you have any other questions." | *(nothing; stop when done)* |

The rule carries forward: every skill the compiler generates must tell its own executor to use peer register for anything a person reads. Machine-only content (scripts, data, tool calls) follows its own format.

## Skill tiers

Utility skills and orchestration skills are two distinct functional tiers in the Metaform Axiom compiler framework.

### Utility skills

- **Definition:** Small, modular, reusable components that perform a single, focused task independently.
- **Role:** Each acts like an individual specialist agent built for one specific task.
- **Execution:** It takes defined inputs, executes a localized operation (often through scripts, tool integrations, or writing instructions), and returns a direct output without needing the full big-picture workflow.

In practice, a good utility skill:
- does one job; if it's doing two, it should be two utilities,
- declares everything it needs as inputs, and reads nothing else from the surrounding workflow,
- turns anything the task doesn't settle into a parameter with a sensible default,
- can be called on its own, or by any orchestration skill, without changes,
- says which errors it can raise, so whoever calls it can retry or route them.

*Example:* the failure-diagnosis skill. It takes one failure report and returns one diagnostic report, without knowing anything about the release process around it.

### Orchestration skills (workflow authoring)

- **Definition:** Higher-level workflow coordinators that link, sequence, and integrate multiple steps and utility skills.
- **Role:** They act like the general contractor on a kitchen renovation. They don't necessarily lay the tile or wire the outlet themselves, but they decide who works, in what order, how outputs feed the next phase, and how errors and conditions are handled.
- **Execution:** They use reasoning patterns such as ReAct to manage state, branch conditionally, run tasks in parallel, and guide an agent from a high-level goal ("generate a comprehensive report," "redo my kitchen") down to individual utility actions.

In practice, a good orchestration skill:
- hands focused work to utility skills, and reuses an existing utility rather than rebuilding it,
- names where a run starts and the order steps run in,
- says how each step's output feeds the next,
- branches when the path depends on a condition, runs independent work in parallel, and iterates over sets of items,
- gives every step that can fail a retry limit, and sends each error to a handler or back to the caller,
- gives work that needs fresh judgment, such as a review, to a fresh agent,
- puts a limit on every loop and says what happens when it's reached,
- asks the user about decisions that are theirs to make, and keeps going on work that doesn't depend on the answer.

*Example:* a "ship a release" workflow that runs tests, calls the failure-diagnosis utility on anything that fails, routes the chosen fix to an implementation step, sends the change to an independent reviewer, and only then publishes.

### How the tiers fit together

| | Utility skill | Orchestration skill |
|---|---|---|
| Scope | One task | A goal made of many tasks |
| Knows the bigger workflow | No | Yes |
| Does the work itself | Yes | Mostly delegates |
| Manages state and order | No | Yes |
| Handles others' errors | No; raises its own | Yes; retries and routes |
| Analogy | The tiler, the electrician | The general contractor |

Role skills describe who does the work. Utility skills do it. Orchestration skills decide who does what, and when. Specialty compilers build more of all three for a particular domain.
