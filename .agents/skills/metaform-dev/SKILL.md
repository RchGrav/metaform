---
name: metaform-dev
description: You are developing Metaform itself in its own repository. This is the index of what governs the work; read the pointed-at files before changing anything.
---

# Developing Metaform

This repository is Metaform, a context engineering tool: it engineers the
context to install itself, the context of every sub-agent, and true
prompt-chained workflows enhanced by the Inference Metaform. You are not using
it on a project; you are building it. Everything below is the map of what already decides how this repo works.
Do not freestyle over it.

## Where it came from

`tempo/` is TEMPO, the earliest precursor to what Metaform is now: a recursive
artifact-improvement engine with a normative spec, a deterministic skeleton
that owns routing, gates, ledger and loop, inference only at the seams, a
harness skill that points at the method instead of restating it, and the rule
that every gate must name its silent failure or die. Read it to understand the
intent behind the chassis rules, not as a component to integrate. Its live copy
is the sibling folder `~/tempo`; the copy here is untracked.

## The rules of working here

- `CLAUDE.md` and `AGENTS.md` at the repository root. They are the highest
  instruction: no added conditions or gates in prompts or prompted code, no
  inverted intent when told to remove something, the blacklist is dynamic,
  Rich's wording is preserved verbatim, tests are written failing first to
  enforce the design, and passing tests prove only that a test passed.
- The `<MetaformFoundation>` block in `CLAUDE.md` is the semantic core every
  expert on this platform must hold. Keep it verbatim in prompts for agents
  building the platform; never place it in the runtime's own prompts.

## The specification is the source

`docs/SPEC.md`, indexed from `specifications/00-index.md`. Sections that decide
the shape of the chassis:

- 1 to 8: Type identity, OP join roles (hard dependency, property, supportive),
  strict typology, the namespace, encounter propagation, one foundation with
  outside-in knowledge.
- 9: inference amortization and the nonce. The chassis owns nonce registration,
  `.agentid/nonce`, assignment-scoped commands and cleanup. Entering a nonce
  changes the CLI; only that context's commands exist; the main menu shows only
  in the project's main folder; `begin <nonce>` is for delegated step-wise
  work in a dedicated folder; done cleans the nonce up.
- 12: chassis customization and built-in guidance. Every feature carries help
  at the level of "what has to be done to use it". The skill page lists every
  loaded module and every available workflow; the installed skill is the base
  information pointing at `metaform skill`.
- 13: startup and onboarding, and first-run provisioning: an unfamiliar harness
  gets the provisioning notice and menu, keyed on the harness binary's parent
  folder in `provisioning.json`, `/tmp` ignored, until it says done.
- 14: contextual help and menus. This is the chassis's main job. `--help` is
  contextual with a status section on top. Every menu is only what needs to be
  done. The user's menu is the main admin menu; an agent can assign itself that
  nonce and say complete to return. Metaform's own features are dynamically
  loaded modules. Installed or in wheel form, it all works the same.
- 15: provenance, prompt objects, porting through medium change. Every
  produced record has one producer holding the prompt revision, the binding
  map and the answer; prompts store variables as references; a medium is a
  transitive property join whose applicability set decides which knowledge
  is re-inferenced in a port; the base shape is never medium-conditioned.
  Written in a declarative register, not Rich's verbatim words, on his
  instruction.

Companion specifications: `feature-briefs/*-specification.md` and
`docs/next-version.md` (handoff and continuity, nonce issuance and cleanup).

## Where the chassis lives in the code

- `src/metaform/cli.py`: the entrypoint, launcher commands, help and starting
  page. `src/metaform/registry.py`: module discovery from the package,
  `~/.metaform/modules` and `<project>/.metaform/modules`; `visible()` scopes
  commands to the bound assignment or mode.
- `src/metaform/continuation.py`: nonce publish, `begin`, marker, retire.
  `src/metaform/onboarding.py`: skill text, guide state, MCP instructions.
  `src/metaform/installation.py`: launcher, harness registration, skills.
- `src/metaform/mcp_server.py` and `portable_mcp.py`: the MCP surface.
  `src/metaform/harness.py`: how drive runs an external agent.
- `src/metaform/data/modules/*.json`: every module manifest; the catalog, help
  and menus derive from these. `src/metaform/data/roles/` and
  `data/semantics/`: the authored prompts. `data/chassis.json`: the chassis's
  own built-in account. `data/skills/metaform/SKILL.md`: the base skill.
- `src/metaform/intake.py`, `workflow.py`, `models.py`, `read_model.py`,
  `properties.py`, `knowledge.py`: intake, the workflow engine, revisions,
  reads, applicability, storage.
- `src/metaform/coarse.py`: expands a coarse intake contribution
  (`urn:metaform:schema:coarse-intake:2`: notable elements by namespace
  position with one EF, joins with the receiver's OP and optional `combined`)
  into storage. The intake prompt `data/roles/runtime/intake.md` is Rich's
  seven-section prompt with no components; its shape is the shape every
  operation prompt takes. Nothing gates an answer: the contract describes and
  never rejects, the expansion makes the answer fit and records mismatches,
  receipts carry nothing back to the agent. Tests:
  `tests/test_coarse_intake_contract.py`.
- `src/metaform/viewer.py` with `templates/explorer.html` and
  `static/explorer.js`: the workbench, built to `docs/workbench-brief.md`.

## What is open

- `docs/repair-backlog.md` and `docs/repair-spec.md`: the reconciled repair
  inventory and the decisions still with Rich. R01 and R02 are the help gap
  that sections 12 and 14 now specify.
- `docs/current-work.md`: the state of the checkout.
- The workbench acceptance: a real intake run through the page with a real
  agent, judged by Rich.

## How work is verified

`.venv/bin/python -m pytest -q tests` for the suite and `npm run test:browser`
for the page. A test exists to protect a requirement of the design; write it
failing first. Screenshots and traces are evidence; Rich's judgment is the
acceptance.
