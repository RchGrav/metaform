# Metaform specification

This folder is the Metaform contract. A builder builds from these files alone. Every requirement is a full record with its reason, its build detail and the tests that protect it.

## Design decisions go in when they are decided

Every design decision goes into this spec when it is decided, in the record that governs it or in a new record, with a status that says how far it is settled: confirmed, recommended, open or deferred. A decision never lives only in notes, a conversation or an assistant's memory. A decided point whose mechanism is not settled is recorded as confirmed design with its mechanism open, and its question goes to OPEN-QUESTIONS.md. Besides new decisions, changes to this spec answer the open questions and fix defects the build finds.

## Authority

- This spec is the contract. Where it and any other document, code or test differ, this spec wins, and the difference is either a defect to fix or a question for Rich.
- Rich's design is the authority over this spec. A record that misstates the design is corrected, not worked around.
- Requirements state outcomes. The Build part of a record says how to reach the outcome; a builder may reach it another way only when every acceptance test for that record still holds and the record's why is still served, and must say so in the pull request.
- An open question blocks only the records that depend on it. Everything else is built.
- Older documents, code, tests and branches are evidence, not requirements. Material from them enters only where it matches this spec.

## Sources absorbed

- `../REQUIREMENTS.md` with `../REQUIREMENTS-corrections.md`: the requirements drawn from Rich's design. TRACE.md maps every one of them to the records here.
- `../SETTLED.md`: design settled in conversation, now carried by the records here.
- `../Canonical_Intake.xml`: the current intake procedure, the tested version. `../Canonical_Intake_test.xml` was identical to it until `ef` was added to the Canonical Intake, 2026-09-26. `../Canonical_Intake_old.xml` is the previous version, reference only.
- `../metaprompting_element_segments_example.md`: how an address and its prefixes carry inference.
- `../code_quality_standards.md`: the quality bar, carried by section 7.

## Sections

| File | Prefix | Covers |
|---|---|---|
| 01-map.md | MAP | C(T), the receiver, purpose and encounter mesh, namespace and Types, element identity, roles, joins, subtypes, how an intake result becomes records and how it is judged, work records, tasks, the work queue, questions and past work |
| 02-layers.md | LAYER | Layers and their one variable, layer properties, select and mask, direct reads, provenance, memory, corrections, the two types of blind spot analysis, the blind-spot challenge, knowledge layers built node by node, item flags, reading from the roots |
| 03-storage.md | STORE | SQLite tables, keys and indexes, the data access object, import, export and query |
| 04-chassis-modules.md | BASE | The chassis, the common base, the module contract, the template, discovery, compatibility, lifecycle, versioning, wheels and packaging, the nonce service, the workflow module |
| 05-cli-settings.md | CLI | Command grammar, help, errors, the settings schema, glue, booleans, context and the command surface, the top menu and entering a module, the working folder, aliases, the settings screen |
| 06-mcp-install.md | MCP | The MCP module, uvx launch, the installer, the skill, agent instructions and what they tell an agent to do, the slash commands, the first working test |
| 07-quality.md | QUAL | The quality bar, tests, type checking, lint, three-system CI, reviews, the cold build check |
| 08-projects.md | PROJ | Projects and source locations, working folders and project selection, origins, variants, reconstruction, export and import of history, clearing a project |
| 09-viewer.md | VIEW | The one web GUI, user global, and its first view, the viewer: a floating 3D graph of the metaform and its layers, and a 2D drill-in view of one object in the left window |
| OPEN-QUESTIONS.md | D, E | Every open design and scope question with a recommendation, and the engineering choices made |
| TRACE.md | | Every source requirement mapped to the records that carry it |
| BUILD-BRIEF.md | | How the building agent works from this spec |
| HANDOFF.md | | Where the build stands and what comes next |
| CAPTURE.md | | Every design point from the design discussion, with the record that carries it |

The Open questions list at the end of each section shows the questions that section raised. OPEN-QUESTIONS.md is the single merged list; answers are recorded there and in the owning records.

## Record format

Each record has these parts:
- **Requirement:** one declarative sentence.
- **What this means:** enough explanation for a builder with no other context.
- **Why:** the reason, from Rich's design.
- **How it shows:** observable behavior.
- **Build:** records, fields, operations and procedures.
- **Acceptance:** the tests that protect the requirement and fail on a wrong build.
- **Relates to:** other record IDs.
- **Status:** confirmed by Rich, recommended, meaning the technically correct answer, accepted and built as written, open, or deferred.

A record whose status is recommended is built as written. A record whose status is open is not built past the point the record settles.

## Out of scope for this spec

- Remote hosting of the MCP server.
- Module specs for the rulebook and the browser terminal module, pending D44. The workflow module is BASE-051. The viewer, section 9, is in scope.
- Maintaining users' forks, CI and wheels at release, pending D30.

## Build order for the first working test

1. Storage and the data access object (STORE), with the settings and module-state tables.
2. The common base and module contract changes (BASE), including the template moving to a layer.
3. CLI and settings changes (CLI): switches as settings, boolean forms, `--`.
4. The map and layer records and operations (MAP, LAYER), including select and mask resolution and direct reads, LAYER-007 and LAYER-008.
5. The memory module, LAYER-012 and LAYER-013: memory at elements and joins through the reference memory interface.
6. The MCP module (MCP), moved out of the chassis, with live instructions.
7. The intake module serving its instructions by name and recording the map one object per call as it is reasoned, through `intake_start`, `intake_element`, `intake_join`, `intake_subtype`, `intake_absorb`, `intake_show`, `intake_edit`, `intake_remove` and `intake_finish`.
8. The installer and the skill.
9. The first working test scenario in section 6, end to end, including a memory written at a node and read back by another agent, and a layer selection that changes what that read returns.

10. After the fix pass is complete and the intake and debug system is stable: the viewer module, section 9.

Memory and layer select and mask are part of the first working test because they are what make the map useful to agents: memory corrects a wrong inference at the node, and select and mask decide which layers an agent sees at each place.

Each step's tests are written first, from the records, and fail before the step is built.
