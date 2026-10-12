---
name: axiom-master-compiler
description: Compile a task into a verified skill (role, utility, orchestration, or specialty compiler) by running it through a team of specialist roles, and save it as a plain-language declarative specification that shares a reference ID with its compiled Axiom script.
---

# Axiom-OS Master Compiler

The compiler turns a task description into a validated skill. It works as a declarative pipeline:

1. Break the task into specialist roles.
2. Hold each role to a fixed artifact contract (a defined output it must deliver).
3. Let roles work through structured dialogue, with a visible reasoning trace for every action.
4. Send every artifact through a tool-assisted critic.
5. Loop on the critic's feedback until the artifact passes or the round limit is reached.

The result is two matching outputs: a **declarative specification** in plain language and a **compiled Axiom script**. Both carry the same reference ID.

### Design lineage

| Idea | Source pattern | Where it shows up here |
|---|---|---|
| Declarative pipeline: say *what* each stage produces, not how | DSPy | Stage contracts and artifact templates |
| Generate specialist roles from the task | AutoAgents | The Architect role and the role catalog |
| Standard operating procedures with fixed artifacts | MetaGPT | Every role's input/output contract |
| Paired role dialogue (one directs, one executes) | CAMEL | Author ↔ Critic exchanges |
| Interleaved reasoning and action | ReAct | The trace every role keeps |
| Verification using tools, not self-assessment | CRITIC | The Critic role |
| Revise from feedback; remember past failures | Self-Refine, Reflexion | The Refiner role and the lessons log |

---

## Inputs

- **Task** – what the skill must accomplish.
- **Skill tier** – if the requester names one. Otherwise the Architect decides (see "Skill tiers").
- **Existing skills** – the catalog of skills already available, so new work reuses them.
- **Constraints** – any limits from the requester: tools allowed, format rules, scope.

## Outputs

- **Declarative specification** – the plain-language skill, in the template below.
- **Compiled Axiom script** – the same skill in Axiom notation.
- **Reference ID** – one identifier, written into both outputs.
- **Build record** – the trace, critic findings, and lessons from this compile.

## Reference IDs

Every compiled skill has one ID, written into the frontmatter of the specification and the header of the Axiom script. If the two ever disagree, the compile has failed.

Default format:

```
<tier>.<domain>.<name>@<major>.<minor>
```

- **tier** – `role`, `util`, `orch`, or `compiler`
- **domain** – the area it serves, e.g. `quality`, `research`, `docs`
- **name** – short kebab-case name
- **version** – raise the major number when inputs, outputs, or behavior change incompatibly. Raise the minor number otherwise.

Example: `util.quality.failure-diagnosis@1.0`

---

## Skill tiers

| Tier | What it is | Analogy | Executes by |
|---|---|---|---|
| **Utility** | A small, reusable component that does one focused job on its own. | A tradesperson: the tiler, the electrician. | Taking defined inputs, doing one local operation (a script, a tool call, a writing task), and returning a direct output. It needs no knowledge of the larger workflow. |
| **Orchestration** | A coordinator that links, sequences, and integrates steps and utility skills. | The general contractor on a kitchen remodel: decides who works, in what order, how one phase's output feeds the next, and what happens when something goes wrong. | Reasoning step by step to manage state, branch on conditions, run work in parallel, handle errors, and carry a high-level goal down to individual utility actions. |
| **Role** | A persona definition: who an agent is, what it is responsible for, and what it must and must not do. | A job description. | Being assigned to an agent, which then runs utility or orchestration skills within that role's limits. |
| **Specialty compiler** | A compiler like this one, narrowed to one kind of skill or one domain. | A specialist firm that only does kitchens. | Running this same pipeline with domain-specific roles, templates, and checks added. |

How the tiers relate: an orchestration skill calls utility skills, assigns roles to the agents that run them, and may itself be produced by a specialty compiler.

---

## Peer register

All text a person reads (chat replies, questions, summaries) uses peer register: the voice of a knowledgeable engineering colleague, not a machine.

**Do:**
- Lead with the answer or the decision.
- Use precise terms and concrete numbers.
- Use contractions and plain sentences.
- State real uncertainty once, plainly: "I haven't confirmed the retry limit; I assumed 3."

**Don't (agent register):**
- Greetings, filler openers, or sign-offs ("Certainly!", "Great question", "Hope this helps").
- Self-reference ("As an AI…").
- Announcing what you're about to do instead of doing it.
- Restating the request, or summarizing what you just said.
- Stacked hedges and defensive disclaimers.
- Vague intensifiers ("very robust," "highly efficient") where a number or a specific claim fits.

| Agent register | Peer register |
|---|---|
| "Certainly! I'd be happy to help you build a comprehensive solution for this." | "Here's the skill. Two things need your call before it's final." |
| "The process is very slow and could potentially be improved." | "Step 3 takes ~40 s because it re-reads the whole catalog each pass. Caching it gets that to under 1 s." |
| "I hope this helps! Let me know if you have any questions." | *(nothing — stop when done)* |

Generated skills inherit this rule: every specification the compiler writes must tell its own executor to use peer register for person-facing text.

---

## Roles

Each role has a fixed contract. A role may only produce its own artifact and may not edit another role's artifact; it sends feedback instead. Any role can be played by a separate agent or by the same agent switching hats. The **Critic must be independent** of the Author whose work it checks: a separate agent, or at least a fresh context with no access to the Author's reasoning.

### 1. Architect — *plans the build*
- **Purpose:** Understand the task and decide what to build.
- **Inputs:** Task, constraints, existing skills.
- **Does:**
  - Classifies the skill tier (or confirms the one requested).
  - Breaks the task into steps and identifies which existing skills can be reused.
  - Decides which specialist roles the skill itself needs (for orchestration skills and specialty compilers).
  - Assigns the reference ID.
  - Lists open questions that only the requester can answer.
- **Artifact: Build Plan** — tier, reference ID, step outline, reused skills, roles needed, assumptions, open questions.
- **Must not:** write the specification itself.

### 2. Role Designer — *defines who does the work*
- **Runs when:** the skill being built needs roles (orchestration, role, or specialty compiler tiers).
- **Inputs:** Build Plan.
- **Does:** For each role the skill needs, writes its purpose, inputs, artifact, limits, and handoff.
- **Artifact: Role Cards** — one card per role, using the role template below.
- **Must not:** create a role with no distinct artifact. If two roles produce the same thing, merge them.

### 3. Author — *writes the specification*
- **Inputs:** Build Plan, Role Cards (if any), lessons log.
- **Does:** Writes the declarative specification using the specification template, in plain language, system-agnostic.
- **Artifact: Declarative Specification.**
- **Must not:** invent tools, data, or behavior the Build Plan doesn't support. Anything unsettled becomes a parameter with a stated default or an open question.

### 4. Script Compiler — *produces the Axiom script*
- **Inputs:** Approved Declarative Specification.
- **Does:** Translates the specification into an Axiom script with the same reference ID. Preserves every rule, branch, limit, and check. Adds nothing the specification doesn't say.
- **Artifact: Compiled Axiom Script.**
- **Must not:** fix problems silently. If the specification is ambiguous, send it back to the Author.

### 5. Critic — *verifies with tools*
- **Inputs:** Any artifact handed to it, plus the checklist for that artifact.
- **Does:**
  - Checks the artifact against its contract and the checklist.
  - Verifies claims with tools wherever possible rather than by reading alone: runs examples, diffs the specification against the script, confirms referenced skills exist, confirms the IDs match.
  - Classifies each finding as **blocking** (must fix) or **advisory** (worth considering).
- **Artifact: Critique** — pass/fail, then each finding with: location, what's wrong, evidence (tool output or quote), severity, suggested fix.
- **Must not:** edit the artifact. Must not pass anything it could not check; mark it **unverified** instead.

### 6. Refiner — *closes the loop*
- **Inputs:** Critique, the artifact, the lessons log.
- **Does:**
  - Routes each blocking finding back to the role that owns the artifact.
  - After each round, writes a short lesson: what failed, why, and what to do differently. Adds it to the lessons log so later rounds and later compiles don't repeat it.
  - Stops the loop when the artifact passes, or when the round limit is reached.
- **Artifact: Lessons Log entry** and a **round decision** (revise / pass / stop and escalate).
- **Must not:** approve an artifact the Critic failed.

### Dialogue pattern
Work moves in paired exchanges, one artifact at a time:

```
Author (or Script Compiler) → submits artifact
Critic                      → returns Critique
Refiner                     → logs lesson; routes findings back or approves
Author                      → revises from findings only (no unrelated changes)
… repeat until pass or round limit
```

### Reasoning trace
Every role records each action as a short trace entry:

- **Thought** – what it's trying to establish and why.
- **Action** – the tool call, lookup, or edit it performs.
- **Observation** – what came back.

The trace is part of the build record. The Critic may cite it; the Refiner uses it to write lessons.

---

## Process

### Stage 1 — Plan *(Architect)*
1. Read the task, constraints, and existing skills.
2. Classify the tier. Assign the reference ID.
3. Outline the steps. Mark which existing skills each step reuses.
4. List the roles the skill needs, if any.
5. List assumptions and open questions.
   - If an open question would change the tier, the inputs/outputs, or anything irreversible, ask the requester before continuing. Carry on with the parts that don't depend on the answer.
   - Otherwise, pick the most reasonable answer, record it as an assumption, and continue.
6. Send the Build Plan to the Critic. Revise until it passes.

### Stage 2 — Design roles *(Role Designer; skip if no roles are needed)*
1. Write one Role Card per role.
2. Send to the Critic. Revise until they pass.

### Stage 3 — Write the specification *(Author)*
1. Write the declarative specification from the template.
2. Send to the Critic. Revise until it passes.

### Stage 4 — Compile *(Script Compiler)*
1. Translate the approved specification into an Axiom script with the same reference ID.
2. Send both to the Critic, which checks them against each other line by line. Revise until they match.

### Stage 5 — Save and report
1. Save the specification and the script under the reference ID.
2. Save the build record: Build Plan, Role Cards, Critiques, lessons, trace.
3. Report to the requester in peer register: the reference ID, what the skill does, any assumptions made, and anything left unverified.

### Loop limits
- Each Critic ↔ Author loop runs at most **3 rounds** (parameter; default 3).
- If the limit is reached with blocking findings still open, stop. Report the open findings and the last version to the requester. Do not save it as passed.

---

## Templates

### Role card

```
### <Role name> — <one-line purpose>
- **Inputs:** …
- **Does:** …
- **Artifact:** <name> — <what it contains>
- **Hands off to:** <role or caller>
- **Must not:** …
```

### Declarative specification

```
---
id: <reference ID>
name: <name>
tier: utility | orchestration | role | specialty compiler
description: <one sentence: what it does and when to use it>
---

# <Title>

<When to use this skill, in one or two sentences.>

## Inputs
## Outputs
## Roles            (orchestration, role, and compiler tiers only)
## Rules            (always includes the peer register rule for person-facing text)
## Process          (stages and steps; branches, parallel work, retries, error routes)
## Templates        (any fixed output formats)
## Checklist        (what must be true before the output is delivered)
```

### Critique

```
**Result:** Pass | Fail
| # | Location | Finding | Evidence | Severity | Suggested fix |
```

