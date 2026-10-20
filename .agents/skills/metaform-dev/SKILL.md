---
name: metaform-dev
description: You are developing Metaform itself in its own repository. This is the index of what governs the work; read the pointed-at files before changing anything.
---

# Developing Metaform

This repository builds Metaform itself. Read current project instructions before
changing code. Use this index to locate ownership, semantics and verification.

## Governing instructions and semantics

- Read `AGENTS.md`, then `CLAUDE.md` and `README.md` at the repository root.
  They establish working rules, architecture and product purpose. Keep changes
  within the assignment.
- The semantic foundation is the `IMMUTABLE SEMANTIC FORMULAS (DO NOT PARAPHRASE)`
  section under `Retain in context, do not discard or compact.` in `AGENTS.md`
  and `CLAUDE.md`. The runtime glossary is the `<glossary>` element in
  `src/metaform/modules/mcp/resources/prompts.xml`. Read these definitions
  exactly, including RE, OP, PE, Join, IFD, EF and C(T). Do not replace them
  with synonyms or require a separate foundation block.
- Read `CLAUDE.md` sections `Architecture`, `Structure` and `Instructing agents`
  before changing execution paths or prompts. Use existing events and filter
  handlers before reads. Module-owned prompts belong in that module's
  `resources/prompts.xml`. Follow current delivery contracts rather than
  copying developer instructions into runtime prompts.
- Prompts, examples and instruction files are product text. When one is wrong or
  incomplete, refine it as you refine code, or route the fix to an agent that
  can make it; never leave a fault standing because a person wrote the text.
  The one fixed text is the Canonical Intake (`prompt.intake:intake.axiom`,
  `prompt_files.FIXED`): its semantics work like a formula and are not edited.
- Use the Metaform map as the memory index. Read applicable unread knowledge at
  the assigned functionality. Link implementation entry points there. Keep
  progress in work records and maintained project knowledge in memory.

## Requirements

Start at `specifications/00-index.md`. Follow the records relevant to the
assignment and compare them with current implementation and project instructions.
`CLAUDE.md` identifies requirement records separately from build logs and reviews.
Historical design documents do not establish current file ownership. Resolve
consequential conflicts through the assignment's responsible roles.

## Current implementation ownership

Paths below are relative to the repository root.

- `src/metaform/cli.py` is the CLI entry point. `src/metaform/loader.py` loads
  modules. `src/metaform/module.py` defines `Module`, `Verb` and `Noun` records.
  A declaration drives CLI commands, help and MCP tools. `src/metaform/docs.py`
  produces help. `src/metaform/context.py` supplies command context.
  `src/metaform/results.py` presents results across surfaces.
- `src/metaform/settings.py` owns shared settings declarations.
  `src/metaform/home.py` owns the home registry.
  `src/metaform/data/` exposes shared storage.
  `src/metaform/events.py` and `src/metaform/changes.py` supply existing change
  notifications. Reuse these mechanisms rather than adding polling.
- Feature owners live under `src/metaform/modules/`. Read the owning module's
  declaration in `__init__.py`, its `README.md` and relevant implementation.
  Declarations may delegate to `manifest.py`. Inspect the actual module before
  changing its commands, settings or prompts.
- Functional map operations belong to `src/metaform/modules/map/`.
  Intake belongs to `src/metaform/modules/intake/`.
  Memory belongs to `src/metaform/modules/memory/`.
  Agent roles and context delivery belong to `src/metaform/modules/agents/`.
  Agent processes belong to `src/metaform/modules/dispatch/`.
  Assignment orchestration belongs to `src/metaform/modules/orchestration/`.
  Workflows belong to `src/metaform/modules/workflow/`.
- `src/metaform/modules/mcp/server.py` serves MCP. Its module declarations
  determine tools and resources. `src/metaform/modules/mcp/resources/prompts.xml`
  holds MCP guidance and glossary text.
- `src/metaform/modules/web/server.py` serves the web GUI.
  `src/metaform/modules/web/page/` holds the page.
- `src/metaform/modules/fork/resources/template/` is the new-module template.
  Read its `__init__.py`, `README.md`, `resources/prompts.xml` and `CHANGELOG.md`.
  New module capabilities must appear in the template and its changelog so
  modules created through fork receive the supported contract.
- `src/metaform/prompt_files.py` reads module prompts.
  `src/metaform/skill/SKILL.md` is the installed base skill.

## Verification

Follow `AGENTS.md` testing guidance. Match checks to change risk. Do not add
implementation-mirroring tests for reversible, low-impact edits. For behavior
changes, use meaningful requirement or regression checks. Run applicable checks,
then stop unless changes, failures or unresolved concerns require more evidence.

`CLAUDE.md` lists current commands. `pyproject.toml` defines test discovery and
markers. `.github/workflows/checks.yml` defines CI checks. Tests live in `tests/`
and module-local `tests/` folders. Use an existing test file for focused runs:

```bash
uv sync --extra dev
uv run pyright
uv run ruff check src tests conftest.py
uv run pytest -n 0 src/metaform/modules/mcp/tests/test_upgrade.py
uv run pytest -q
uv run pytest -q -m browser
```

The focused run above covers MCP upgrades. Select tests for the actual change.
Default pytest discovery includes chassis and module tests, excludes browser
checks. The browser command selects browser checks. Read `conftest.py` for test
home isolation and fixtures. Documentation-only changes need reference and
instruction consistency checks, not runtime correctness claims. Record checks,
results and remaining limits in the assignment.
