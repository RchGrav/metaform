# Editable intake task

Intake is a named task. Its instructions remain editable text, and its records continue through the existing MCP data tools. The MCP server implementation and protocol were not rewritten.

The instruction source is `src/metaform/modules/intake/resources/intake.xml`, under prompt-store name `prompt.intake:intake.xml`. `tasks read name=intake`, assignment and `intake prompt` resolve the same selected version. A configured UTF-8 file can replace the source. Tags, headings, method phases, `{prompt}` and `{project_id}` have no special runtime meaning. Only declared task bindings apply. Request and recording-mode data follow the instructions separately.

Removed the fixed-intake editing restriction, target-tag rewriting, prompt-slot substitution and construction-guide section extraction. Map guidance remains independently editable. Active Axiom intake resources were removed. The User Agent, Worker, Facilitator and Architect instruction files were not rewritten.

The normal intake launcher and GUI now assign the named task. Existing map selection, unfinished-recording handling, status, stop and explicit native resume use the task's identity. The task follows the ordinary task runner without the retired intake role's tool withholding or first-record steering. Recording locks prevent concurrent writers from interleaving map records.

Removed intake's automatic critic notes, assessment writes and repair-ticket creation. The retired `note`, `condition` and `same_as` recording arguments are absent. Existing stored assessment records remain readable. Native `block` and `within` element metadata survive recording, refinement, rename, export and import without a new storage table or knowledge layer. The authored ICE definitions and analysis steps are preserved.

## Validation

- Intake, map guidance, element metadata and store exchange: 117 tests passed.
- Task documents: 25 tests passed. Prompt store: 13 focused tests passed. Three broader prompt-suite checks remain unresolved: inline prose detection, a full-instruction fixture expecting a tasks `prompts.xml`, and startup instruction length with every optional module enabled.
- GUI task identity and controls: 7 Node tests passed.
- A separate MCP stdio process returned identical unfinished-markup instruction text through the task and intake reads. Evidence: `/tmp/metaform-opaque-task-mcp-sa2zba9h/proof.json`.
- Intake launch, native transport, project registration and onboarding: 42 tests passed. Native session identity is preserved by the explicit resume route. A production ACP resume was not exercised.

Tests use isolated homes and local test adapters. No production model session was started or live Metaform server restarted. Actual model execution and a complete browser run were not validated.

Hermes remains at 69 elements and 69 purpose records. The accidental critic layer was removed through MCP. The supplied block-correction XML has not been applied, and no synthetic relationships were added.

Checkpoint before these repairs: branch `recovery/pre-intake-note-removal-20261024`, commit `94e809b754c74ef8dcd1e13967af292e2cabd714`. Unrelated working-tree changes and user files under `rich/` remain untouched.
