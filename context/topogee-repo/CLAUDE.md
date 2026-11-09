```markdown
# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Read first

@AGENTS.md

`AGENTS.md` governs this repository. Its founder boundaries override anything here. In particular: intake schemas and prompts are protected, and commits and pushes follow the Feature commits section there, and nothing is deployed without a direct instruction. `docs/README.md` explains where doubt belongs. Read it before forming an opinion on the design.

@TASTE.md

`TASTE.md` contains guidence you must observe for communication.  Plain talk, full thoughts, stop making up your own terms for things, important things like that.

## What this project is

@TOPOGEE.md

`TOPOGEE.md` is the opening statement of this project. `_bmad-output/initiative-topogee-navigator/initiative-topogee-navigator.md` holds the draft requirements, and the founder has not confirmed it. The founder's statements in `docs/` govern over older text in other documents. Do not ask the founder to state this intent again.

## Founder constraints for the build

These are stated in `DECISIONS.md` and apply to every change:

- Features land as modules on the chassis, using services it exposes. Do not bypass the chassis or the settings system.
- Do not add tools without a founder decision. Tools exist for context management, and the specification must say so.
- Keep the worktree and feature-commit pattern. Do not drop it when reducing tools.
- Target about 500 lines per source file. Split a file before it grows past that limit.

## Architecture

- **Specification:** `metaform/SPEC.md` is the specification the build follows. `metaform/SPECIFICATION.md` is an older draft. `metaform/docs/designs/metaform-server-design.md` is the design of the map server, and `metaform/docs/designs/metaform-server.md` holds the founder's positions behind it. `DECISIONS.md` holds founder decisions and open technical choices. Current founder decisions take precedence over the specification.
- **Stored data:** the functional namespace is a nested document whose JSON form is defined by `metaform/metaform.schema.json`; maps are stored in LadybugDB, one database per project (`metaform/SPEC.md` R-4.1). Each element owns its properties and native knowledge arrays. A receiver's `wants` is a dictionary of its relationships to providers, keyed by the provider's project-relative address. Anything keyed by a unique name is a dictionary, not an array.
- **Intake vocabulary:** the intake keeps the authored terms RE, PE, OP, EF, IFD and CQU (ICE was superseded: the Definitive and Supportive relationship is the inseparable boundary, R-3.14). The stored fields are `why` (OP), `how` (EF), `intent` (IFD), and `wants` (the PE relationship). The mapping is in `DECISIONS.md`.
- **Tool contract:** `metaform/mcp-tools.proposed.json` defines one Metaform tool for changes, addressed reads, and orphan queries. Read-only views are projections, not another registered tool. The input schema validates a command. The stored-document schema validates the resulting map. Both are checked by the tests above.
- **Intake prompt:** `metaform/Intake.md` (Digital Typology Intake, version 3.1) is the current intake procedure. It is the project copy of the founder's `intake-new.md`. Use it for test intakes. `metaform/Intake.xml` is the older project prompt, and `metaform/intake.mmd` is its diagram. The founder's query note is in `metaform/docs/mcp-query-source.md`. Maintain these project files; do not depend on the founder's personal folder. Changes to the authored method still require direct founder instruction.
- **Reference material:** `reference/` is preserved evidence with known obsolete proposals. Do not execute scripts from it, and do not bulk-import its code. `source-register.json` records the snapshot hashes that `tools/verify_bootstrap.py` checks.
- **Boat:** a development tool for throwaway sandboxes, not a product dependency. Use `boat run --no-env`. Touch only sandboxes whose ID your own create call returned. Do not upload `reference/` or intake material.

## Working with the founder

- Preserve the founder's authored semantics and method. Do not rewrite the intake into code-only analysis, add conditions, or substitute a prompt silently.
- Present proposals that change the design for confirmation before they land. Keep decisions grounded in the founder's words and the existing specification, not in assistant documents or passing tests.
- Separate what is known, what is inferred, and what is unknown. State uncertainty plainly.
- When a question is needed, ask it once and say what it blocks. Do not restate the question at length. Keep the next step visible.
- Carry out agreed work within its stated scope. List the choices you made.
- Offer alternatives when they clearly help. Say when a suggestion goes beyond the task. Do not expand scope without permission.
- Give criticism a concrete reason. Do not add objections to balance a positive assessment.
- Respect that this project is the founder's personal work.

## Testing

- Append to existing test files instead of creating new ones.
- Budget: at most five tests per feature. Write one happy-path test and the critical edge cases within that budget. Check the count before adding a test.
- Test only the public interface. Do not test private methods or internal boilerplate.
- Run only the affected file or filtered cases while developing. Run the full bootstrap suite once, at the final verification step.
- Keep tests within the changed file's language directory. Run tests in another language only when the change touches that language.
- Stub or fixture any cross-language boundary. Do not start another language's runtime during unit or contract tests. Validate schema files with a lightweight validator.
- When a subagent changes code, its brief must include these rules.
