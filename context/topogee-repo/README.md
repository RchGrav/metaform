# Topogee Navigator

Functional understanding, scoped knowledge and event-driven agent coordination.

Domain: **topogee.com** · Clean rebuild from the founder's Metaform architecture.

This repository develops two things: Topogee, a shared world where agents and people collaborate and build anything, including the world itself, and Metaform, the context tool for development agents ([DECISIONS.md](DECISIONS.md), "Naming: Topogee and Metaform").

## Start here

**Read [TOPOGEE.md](TOPOGEE.md) first. It states what Metaform is, under the name Topogee.** The game's design is [docs/designs/world-system-spec.md](docs/designs/world-system-spec.md).

Models: read [docs/](docs/README.md) before you form an opinion on the design.

1. [Specification](metaform/SPEC.md) — the specification the build follows. [metaform/SPECIFICATION.md](metaform/SPECIFICATION.md) is an older draft that still carries the contract appendix.
2. [Decisions](DECISIONS.md) — settled requirements and remaining technical choices.
3. [Development](DEVELOPMENT.md) — setup, checks, source authority and first implementation slices.
4. [Agent instructions](AGENTS.md) — preserve founder semantics and protected intake assets.
5. [Reference guide](reference/README.md) — papers, original intake, ECS packet, handoffs, chassis/module contract and review evidence.

## Run the bootstrap checks

Python 3.12+ is used only for the supplied validation utilities:

```sh
python -m venv .venv
.venv/bin/python -m pip install -r metaform/requirements-dev.txt
.venv/bin/python metaform/tests/check_contract.py
.venv/bin/python metaform/tests/check_tool_input.py
.venv/bin/python tools/verify_bootstrap.py
```

On Windows use `.venv\Scripts\python.exe` in place of `.venv/bin/python`.

## Contracts

- [Current intake procedure](metaform/Intake.md) (Digital Typology Intake 3.1). [metaform/Intake.xml](metaform/Intake.xml) and its [sequence diagram](metaform/intake.mmd) are the older prompt.
- [Functional namespace schema](metaform/metaform.schema.json)
- [Founder's unchanged skills example](metaform/owner-skills-example.json)
- [Provider-reference example](metaform/provider-reference-example.json) — illustrative, not a project intake
- [Stored project example](metaform/intake-example.json) and [working-tool examples](metaform/tool-examples.json)
- [Single MCP tool contract](metaform/mcp-tools.proposed.json) and [proposed agent skill](metaform/SKILL.proposed.md)

This repository bootstraps development; it does not contain a working rebuilt application.
The spec is not founder-approved or verified recovered v0.9. Contract tests establish shape
and reference behavior, not intake semantics, database concurrency or MCP interoperability.
Runtime-language and server-library selection remain visible technical choices.
