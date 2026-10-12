---
name: workflow-authoring
description: Design, write, check, and register a reusable multi-step workflow from a stated goal, then optionally start a run.
---

# Workflow Authoring

Use this skill when you are asked to build a workflow: a named set of reusable steps that an executor (a person, an agent, or an automation system) can run to reach a goal.

## Inputs

- **Goal** – what the workflow must accomplish.
- **Run arguments** – values for an immediate run, if any. May be empty.
- **Target scope** – where the workflow is stored (a project, folder, namespace, configuration layer, or similar), as given by the requester.

## What you produce

- **Workflow identity** – a clear, unique name or address for the workflow.
- **Supporting scopes** – any existing configuration, knowledge, or context sets the workflow depends on.
- **Steps** – one self-contained definition per step (see "How to write each step").
- **Entry step** – the step a run starts with.
- **Triggers** (optional) – small pieces of logic attached to specific items that start the workflow from those items.
- **Entry call** (optional) – the call that starts a run with the given run arguments.

## Ground rules

### Read the shared references first
Before anything else, read every shared reference document the workflow depends on (language or format rules, system description, naming rules, general workflow rules, available tools). Use the exact version you were given. Do not substitute a newer or older version. These references bind as if written in this skill.

### Writing the workflow
- Follow the general workflow rules for every step and trigger you write.
- Choose supporting scopes only from those that already exist. Check before you choose.
- If an existing step elsewhere already does the job, call it instead of writing it again.
- If a step needs a value the goal does not settle, make it a parameter with a sensible default.
- Use the right control structure:
  - **Branch** when the path depends on a condition.
  - **Run in parallel** when steps are independent.
  - **Iterate** when working through several items.
- Give every step that can fail a **retry policy**: which errors it retries on, the maximum number of attempts, and how much to increase the wait between attempts.
- When another step can handle a particular error, **route that error** to that step.
- **Delegate to a fresh agent** (or person) wherever the work benefits from no prior context, for example an independent review.

### Writing triggers
- Write triggers only when the goal or run arguments name specific items the workflow should run from.
- Store each trigger in the scope the goal names. If no scope is named, store it in the target scope, so that turning that scope off also turns its triggers off.
- A trigger refers to the item it is attached to through a generic self-reference, never a hard-coded name or address.
- Read any value that may be missing (for example, because its scope is turned off) in a way that returns "empty" instead of raising an error. The receiving step treats "empty" as "not given" and uses its default. If the parameter has no default, the call fails back to the trigger.
- Never modify the self-reference, and never call anything through it. Every call names its target explicitly.

### The user and tools
- If you, or any step you write, needs a decision that only the user can make, ask the user. Meanwhile, carry on with the work that does not depend on the answer.
- Use only the tools listed in the shared tool reference. Follow its rule for any tool marked as not yet available.

## Decision rules

Apply these to every step and call.

**Iteration (per step)**
- If the step works through several items: process them one at a time. Repeat each item until it meets the step's acceptance criteria or reaches the maximum attempts.
- Otherwise: repeat the step until it meets its acceptance criteria or reaches the maximum attempts.

**Failure (per error a step can raise)**
- If another step handles this error: route the error to that step.
- Otherwise: fail back to the caller.

**Delegation (per call)**
- If the work needs a fresh agent: mark the call for delegation. The executor sets it up when the run happens.
- Otherwise: run it in the current agent.

**Entry (per run)**
- If triggers exist: runs start from the triggers.
- Else, if run arguments were given: the entry call is the entry step called with those arguments.
- Else: register the workflow only. Do not start a run.

## Process

### Stage 1 – Load
1. Read every shared reference at its specified version.
2. Go to Stage 2.

### Stage 2 – Orient
1. Analyze the goal. Identify what the workflow is, what kinds of items it works on, which supporting scopes it needs, and whether it should run from triggers.
2. List the existing scopes and workflows. Reuse what fits.
3. Decide the workflow's identity and its supporting scopes.
4. Go to Stage 3.

### Stage 3 – Write the steps
1. Break the goal into the steps that reach it.
2. For each step, apply the iteration, failure, and delegation rules. Then write the step in full:
   - its parameters and their defaults,
   - its acceptance criteria,
   - its control flow,
   - its retry policy and error routing,
   - the errors it can raise,
   - how it ends: a return value or a call to the next step.
3. Record the full list of steps and name the entry step.
4. If specific items to run from are named, write the triggers.
5. Run the checklist below. If everything passes, go to Stage 4.

### Stage 4 – Register
1. Register the workflow in the target scope, together with its supporting scopes.
2. Register each step's definition with the workflow.
3. Register each trigger on its item, in its scope.
4. Export the stored workflow to a portable file named after the workflow.
5. Go to Stage 5.

### Stage 5 – Start
1. Apply the entry rule.
2. If there is an entry call, hand it to the executor.
3. Report what was registered and how a run starts.

## Checklist

Run this before registering. The action column says where to go back to if a check fails.

| # | Check | If it fails |
|---|---|---|
| 1 | Was every shared reference read at its specified version? | Return to Stage 1. |
| 2 | Is there one definition per step, rather than one flattened script? | Rewrite steps. |
| 3 | Is each step complete and self-contained, in the required format? | Rewrite steps. |
| 4 | Does every call point to a step that actually exists? | Rewrite steps. |
| 5 | Does every step declare its parameters, state its acceptance criteria, and end in a return or a call? | Rewrite steps. |
| 6 | Is the entry step named? | Rewrite steps. |
| 7 | Does every loop have a maximum number of attempts, and say what it returns when they run out? | Rewrite steps. |
| 8 | Does every step list the errors it raises? Does every retry and error route match a listed error (or "any")? Does every error route point to a handler that exists? Can the original caller use what the handler returns? | Rewrite steps. |
| 9 | Does every delegated step carry complete instructions, state what data it accepts and returns, and end in a return? | Rewrite steps. |
| 10 | Is every step free of hard-coded addresses and project-specific names, taking such values as parameters instead? | Rewrite steps. |
| 11 | Do triggers use the self-reference instead of a written-out address, read possibly-missing values safely, and never modify or call through the self-reference? | Rewrite steps. |
| 12 | Does every supporting scope actually exist? | Return to Stage 2. |
| 13 | All checks pass? | Go to Stage 4. |
