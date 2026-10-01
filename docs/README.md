# Inference Metaform documentation

[System introduction](../README.md)

The Inference Metaform prepares substantive understanding before work and retains it for subsequent reasoning. These guides explain how to use the present implementation and how to read the functional understanding it carries.

## Start with your task

| You need to... | Read |
|---|---|
| Install Metaform, connect an agent, and obtain a first map | [Getting started](guides/getting-started.md) |
| Find a part or relationship, retain knowledge, or choose context | [Working with Metaform](guides/working-with-metaform.md) |
| Understand what an address, purpose, Encounter, or internal subtype means | [Reading an Inference Metaform](guides/reading-a-metaform.md) |
| Add a capability as a community module | [Extending Metaform](guides/extending-metaform.md) |
| See a project's recorded map used to orient a task | [The module-system walkthrough](examples/project-walkthrough.md) |
| Follow the complete causal explanation | [Preprint](preprint/inference-metaform.md) / [PDF](preprint/inference-metaform.pdf) |

For a first session, follow Getting started through a receiving-purpose relationship; it also records a small kitchen timer map by hand, which the operating and extension guides use for their examples. For continuing work, keep the operating guide alongside the agent or command line. For extension, the module-system walkthrough and the extension guide approach the module contract from different perspectives.

## Deeper technical material

The [technical reference](inference-metaform/REFERENCE.md) is the full account of the design. Its [implementation map](inference-metaform/IMPLEMENTATION_MAP.md) identifies source symbols, data lifecycles, present interfaces, and source-local differences. [Examples to collect](inference-metaform/EXAMPLES_TO_COLLECT.md) describes useful future evidence; [Ideas](inference-metaform/IDEAS.md) separates new proposals from established mechanisms.

[MCP instruction places](reference/mcp-instruction-places.pdf) is a cheat sheet of every field an MCP server can use to put words in front of a model or a person: what it is, its type, its limit, what triggers it and how the model sees it, for protocol revision 2026-07-28 on Claude Code. [mcp-instruction-places.py](reference/mcp-instruction-places.py) holds its rows and writes the [HTML](reference/mcp-instruction-places.html) that prints it.

The [bibliography](preprint/references.bib) contains the preprint's research references. [Citation information](preprint/CITATION.md) identifies this edition without implying journal publication or peer review.

## Examples and evidence

[project-metaform.json](examples/project-metaform.json) is an export of an earlier version: this repository's own map, recorded on September 26, 2026, at schema version 1, copied with one change, `verb` recorded as null on each join and subtype row. The current chassis imports schema version 8 only and stops on this file. The reader guide and walkthrough quote its records as recorded material, and [the reader guide](guides/reading-a-metaform.md) says which of its record shapes have changed since. [CLI-EXERCISE.md](examples/CLI-EXERCISE.md) is the dated record of the command exercise made for the September 26 edition.

The guides label **derived illustrations** when they demonstrate a described use rather than quote an executed agent task. The current store, command line, memory, layer, module, and GUI operations are explained as operations. Lexicalization, complete automated blindspot production, and intent-driven recomposition are explained as mechanisms with their construction boundaries, not invented commands.

[Edition and validation notes](EDITION.md) record the documentation edition of September 26, 2026, the source it was written against and the checks made on it, and what has changed since. Source links resolve in the repository layout.
