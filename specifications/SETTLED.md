# Settled design

The spec in spec/ now carries every entry below; TRACE.md maps each entry to its records, and the spec is the authority. This file stays as the record of what was settled in conversation and is not edited further.

## Chassis and modules

**The chassis runs completely on its own as a CLI.** It owns the data, the settings and the CLI. It imports, exports and queries its data, and builds wheels. Confirmed.
*Why:* the data must stay usable with no modules at all, and every module stands on the same working base.

**The chassis does not run workflows. MCP is a module.** Confirmed.
*Why:* workflows are agent work that modules provide. Keeping MCP a module puts it on the same base as every other module and keeps its dependencies out of the chassis.

**A module may use everything the chassis offers. Any Metaform resource that modules use belongs in the chassis.** This includes the data access object, settings, verbs, events and help. Confirmed.
*Why:* one implementation of each resource means every module behaves the same way, and no module rebuilds what another already has.

**Every module and every non-chassis feature starts from the one common template, which is kept current with a changelog.** Confirmed.
*Why:* authors copy the template, and the changelog lets every fork follow the contract as it changes.

**Template and demo modules ship disabled.** A module's own declaration states that it ships disabled. Shipping disabled is confirmed; declaring it in the module is recommended.
*Why:* a fresh install runs only real work. Declaring it in the module means the chassis keeps no list of names.

**Everything a module keeps goes through the chassis data access object, as a layer.** Recommended.
*Why:* data held outside the chassis cannot be exported, imported or queried whole. The template currently writes its own history.json, which breaks this.

## Wheels and packaging

**The repo's wheel carries every repo module. The local build command carries only the enabled modules.** Confirmed.
*Why:* the release is complete, and a user's own build holds exactly what they use.

**A wheel runs directly, from its own subfolder under ~/.metaform.** Confirmed. Whether it gets one subfolder per build or one per wheel name is open.
*Why:* a custom build never depends on version compatibility with the installed Metaform.

**A directly run wheel works in the code execution environments of OpenAI and Claude.** It carries its requirements and is compatible there. Confirmed.
*Why:* a user can build a custom Metaform and upload it where an agent runs code.

**Installing a wheel can update the installed data and merge the wheel's data in.** Confirmed. What merging does exactly is open.

**At release, Metaform offers to maintain a user's personal fork, its CI and the build of their own wheel.** Confirmed.
*Why:* the community builds on the template, and that upkeep is what keeps their forks working as the chassis changes.

**Packaging uses pyproject.toml and the uv toolchain. AI clients start the MCP server with uvx.** Confirmed. The registration is `uvx --from <wheel or distribution> metaform mcp serve`.
*Why:* uvx runs the server in its own environment with its own dependencies, the same way on every system.

**The PyPI distribution name is undecided.** `metaform` belongs to an unrelated package, last released 2020-06-09. The command and the Python package stay `metaform`. Open; the name only matters when publishing.

**The chassis depends only on the standard library and pure-Python packages.** Recommended.
*Why:* compiled dependencies such as pydantic_core tie a wheel to one Python version and platform. MCP, as a module, brings its own.

**MCP uses the official mcp SDK's server.** Recommended.
*Why:* tools come from module verb declarations and change with the folder's command setting. The SDK's low-level server lists tools per request, which fits that directly.

**Remote hosting of the MCP server is a later goal.** Confirmed. It is outside the first test and the MVP.

## Cross-platform

**Everything works on Linux, macOS and Windows by default.** Confirmed, and written into CLAUDE.md.
*Why:* Metaform runs wherever its users and their agents work.

**Modules state their compatibility. A verb may narrow its own.** Module compatibility in SUPPORTED_OS is confirmed; per-verb compatibility is confirmed as acceptable. Recommended mechanism: a verb that does not match the system is filtered by the same check as the command setting, and `help <verb>` says where it runs and gives one next step. A small OS-specific piece can also be its own module.
*Why:* one piece that cannot run on a system should not make a whole module unusable there.

**CI runs the checks on Linux, macOS and Windows. The template's CI does the same.** Recommended.
*Why:* cross-platform needs proof on every change, and forks inherit it.

## Installer

**`metaform install` is a proper polished setup.** Confirmed. Recommended contents: checks first; a checklist of detected tools; a preview of every file it will change and every backup; a proof that each tool can start the server and list its tools; a finish screen with one next step; safe to run again; `metaform uninstall`. Which of these belong in the first test is open.
*Why:* setup is the first thing a user meets, and it touches other tools' configuration.

**The installer asks before it writes to any tool. It writes without asking only when told which tools to set up.** Asking by default is confirmed. Recommended form: `metaform install` asks; `metaform install claude codex` sets up those tools; `metaform install all` sets up every detected tool. `all` is an argument because it stands for the things acted on.
*Why:* no one is surprised by changes to their tools, and scripts can still install without questions.

**The installer writes one fixed, short skill to each chosen tool's global skill folder.** The skill points to the live instructions from `metaform` and the MCP server and carries no module text. It writes copies from ~/.metaform/skills, not symlinks, and never writes into project folders. Confirmed.
*Why:* live instructions have one source, so enabling a module never rewrites skill files. Symlinks need admin rights or Developer Mode on Windows.

**Each tool's skill path is checked by a test that the tool loads the skill from there.** Recommended.
*Why:* the known paths come from secondary sources.

**Picking the project in hosts that start the server outside the project folder.** The problem is real. How to solve it is open; old code used an environment variable, which is not confirmed design.

## Agent instructions

**Each module adds concise instructions: low context, enough to work with the user, deferring to `metaform help`.** Confirmed.
*Why:* agents start with little context. The details stay in help, where they are current.

**When a project has no intake, the instructions say so and tell the agent to have a subagent perform it. The subagent reads its instructions from Metaform by name, through the CLI or MCP. The orchestrator passes only where to read them, never the text.** Confirmed.
*Why:* intake is agent work, and hosts start subagents in different ways, so Metaform never launches a model. One source means every worker reads the same text, unaltered. The nonce later replaces the name as the handle.

## CLI and settings

**`--` ends switch parsing, everywhere.** Confirmed.
*Why:* it is the standard way to pass a name that looks like a switch or collides with a keyword.

**Every long switch is a setting.** Passing it affects one call. `set` stores it for the folder, `unset` clears it, `--glue` protects it from `unset all`, and `unset all --unglue` always returns everything to the safe defaults. Confirmed.
*Why:* one schema drives the switches, the settings, help and the settings screen, so they cannot drift apart.

**`--confirm` is the one switch that is never a setting.** Confirmed.
*Why:* it guards destructive verbs. Stored or glued, it would silently approve every deletion from then on.

**The settings schema lists every setting with its system default, type, group, label, description, and its switches spelled out.** A default is a real declared value, for example 4 nodes or true. Confirmed, following mvm's commcube_config/schema.py.
*Why:* the default differs per setting, and one table is the single source for every surface.

**A boolean has two switch forms, `--name` and `--no-name`. Neither toggles.** Parsing gives three cases: `--name`, `--no-name`, or not given; not given leaves the setting unchanged. On one call, a form overrides a stored or glued value for that call only. Confirmed.
*Why:* a boolean's default can be true or false, so each needs a form to depart from it and a form to return. A glued value needs its opposite form to be inverted. The chassis booleans currently take an on or off value instead.

**Module switches are declared once and are settings too.** Recommended. The chassis currently declares module switches separately, where `set` cannot reach them.

## Quality

**specifications/code_quality_standards.md is the bar.** Confirmed.
*Why:* the code will face outside scrutiny and must pass it.

**Tests exist only to protect the design.** Each test comes from one requirement and fails on a build that gets that requirement wrong. No test mirrors the implementation or covers a reversible, low-impact change. Passing tests are not evidence of quality. Confirmed.
*Why:* tests that mirror the code pass on wrong builds, cost tokens, and make corrections harder.

**Quality checks: strict type checking of the base and chassis, one lint config, the three-OS runs, and a critic review of the code against the standard before merge.** Confirmed as the quality section.

## First working test

**The first working test is the installer, the instructions for a project whose intake has not been performed yet, and each module's concise instructions.** Confirmed.

## Open questions carried from the corrections file

- REQ-018: media or asset; stakeholder or an entity trunk. Recommended: Canonical Intake 1.1's roots.
- REQ-035: a module place per project. Recommended: none, since all data is global.
- REQ-124: whether hiding a layer hides the layers built from it. Recommended: yes.
- Section 20: remove the remediation instructions. Recommended: remove.
