# 06 MCP, installer and agent instructions

This section specifies the MCP module that serves Metaform to AI tools, the `metaform install` setup that registers it and writes the skill, and the instructions an agent receives.
It also defines the first working test, which exercises all three end to end.

## MCP module

### MCP-001 MCP is a module

- Requirement: The MCP server is provided by a module named `mcp`, built on the common base like every other module.
- What this means: The chassis runs completely without MCP. The `mcp` module adds the verb `metaform mcp`, which starts the server. It uses the same chassis resources as any module: the module registry, the settings, the command surface and the verb declarations. It gets no private access. MCP's library dependencies belong to the module, not the chassis.
- Why: The chassis must stay usable on its own, and every surface stands on the same base. Keeping MCP a module also keeps its compiled dependencies out of the chassis, so a wheel without the MCP module runs anywhere.
- How it shows: `metaform list modules` lists `mcp`. With it disabled, `metaform mcp` fails with one next step, `metaform enable module mcp`. Everything else in the chassis still works.
- Build: Move `src/metaform/mcp_server.py` into `src/metaform/modules/mcp/`, following the template's shape. Remove `mcp` from `VERBS` and `ALWAYS` in `src/metaform/cli.py` and from `RESERVED` in `src/metaform/loader.py`, and remove the `mcp` command page from the chassis docs. Move the `mcp>=1.10` dependency out of the chassis requirements and into the module's declared requirements. How a module declares its requirements for a wheel build is in the packaging section.
- Acceptance: With the `mcp` module disabled, `metaform mcp` exits nonzero with a `Next: metaform enable module mcp` line, and the chassis command tests still pass. Importing the chassis package with the `mcp` library absent succeeds.
- Relates to: BASE-003, BASE-026, CLI-001, MCP-002, MCP-003.
- Status: confirmed.

### MCP-002 The server speaks MCP over stdio through the official SDK's low-level server

- Requirement: `metaform mcp` serves the Model Context Protocol over stdin and stdout, using the low-level `Server` class of the official `mcp` Python SDK.
- What this means: One process serves one host connection. Tools and instructions are computed on each request from the live module declarations, not registered once with decorators.
- Why: Tools come from module verb declarations and change with the folder's command surface. A server that lists tools per request fits that directly. A decorator-based framework would sit between the declaration and the server and add dependencies without adding anything used.
- How it shows: A host that launches `metaform mcp` completes initialization and receives the tool list and the instructions.
- Build: Keep the current `serve()` shape in `mcp_server.py`: `Server(... on_list_tools=..., on_call_tool=...)` with `stdio_server()`. Tool calls run in a worker thread through `anyio.to_thread.run_sync`, as now.
- Acceptance: An MCP client test starts `metaform mcp` as a subprocess, initializes, lists tools and calls one. It protects MCP-003 and MCP-004 through real protocol traffic.
- Relates to: MCP-001, MCP-003.
- Status: recommended.

### MCP-003 Each module verb is one tool, built from the same declaration as its CLI command

- Requirement: Every verb of every module on the folder's command surface is served as a tool named `<module>_<verb>`, built from the same declaration that builds its CLI command.
- What this means: The tool's description is the verb's summary. Its input schema comes from the verb's nouns and switches. A module author declares a verb once and gets the CLI command, its help and its tool. Names must match `^[a-zA-Z0-9_-]{1,64}$` and contain no double underscore. A verb whose name would break that rule is refused when the module loads, with the reason. It is not silently skipped.
- Why: One declaration for both surfaces means CLI and MCP never disagree, and an agent without MCP loses nothing.
- How it shows: The template's `greet` verb appears as the tool `template_greet`, with the same summary as `metaform help template greet`.
- Build: `tools()` in `mcp_server.py` does this now. Change the silent `continue` on an invalid name into a load-time refusal in `loader.py`, with a `Next:` line naming the fix.
- Acceptance: A verb added to a test module appears as a tool with no MCP code written for it. A module declaring an invalid verb name fails to load and says why.
- Relates to: BASE-006, CLI-001, MCP-004, MCP-005.
- Status: confirmed.

### MCP-004 The tool list follows the folder's command surface

- Requirement: A tool exists on the MCP server exactly when its command is on the folder's command surface: it is listed only then, and it runs only then.
- What this means: The `commands` setting and the module enabled state decide the surface. A command outside the surface is neither listed nor callable. A call to it returns an error with one next step. Harness tool permissions can narrow the surface further, but never widen it.
- Why: The command surface governs what exists, so the narrowing holds even when a host grants every tool. The orchestrator that narrowed the surface holds the way back; a subagent meets only what is on the surface.
- How it shows: `metaform set --commands template` in a folder. A new MCP connection from that folder lists only `template_*` tools. A call to `map_where` returns `Error: No tool map_where on this surface.` followed by one `Next:` line.
- Build: `_surface()` and `run_tool()` in `mcp_server.py` do this now. Per-verb OS compatibility is filtered by the same check, as specified in the CLI section.
- Acceptance: With the surface narrowed, the narrowed-out tool is absent from `tools/list`, and calling it by name returns `is_error` true. With the surface restored, both work.
- Relates to: CLI-022, BASE-016, MCP-003.
- Status: confirmed.

### MCP-005 Tool arguments follow the command grammar, and booleans appear once

- Requirement: A tool takes the verb's nouns as an array argument `nouns` and each switch as a named argument. A boolean setting appears once, as a boolean named after the setting, and is left out when not given.
- What this means: `nouns` carries the words the CLI takes after the verb. A switch that takes a value is a string argument. A boolean appears as `tmux: true | false`. Leaving it out means not given, so the stored or default value applies. The no-form exists for people typing on a command line. An agent never sees it and never has to resolve a double negative. `confirm` is a per-call boolean, present only on caution verbs, and never a setting.
- Why: The CLI grammar is verbs, nouns and switches, and MCP carries the same grammar in JSON. A boolean has three parsing cases: on, off and not given. Absent is how JSON says not given. One argument per setting keeps the tool schema free of contradictions such as `tmux: true, no_tmux: true`.
- How it shows: The schema for a verb with a boolean setting `tmux` shows one property, `tmux`, of type boolean. Calling it with `tmux: false` runs that call with tmux off, even when `--tmux` is glued on. Calling it without `tmux` uses the stored value.
- Build: In `tools()`, switch properties come from the module's settings declarations, not a separate adverb list, per the settings section. Change `run_tool()` so that `false` is passed through as off. Today it drops `False`, which makes off impossible over MCP. Apply the value to that call only, as the CLI does.
- Acceptance: A glued-on boolean called with `false` runs off for that call, and the stored value remains on afterward. A call without the argument uses the stored value.
- Relates to: CLI-011, CLI-012, CLI-015, CLI-018, MCP-003.
- Status: recommended.

### MCP-006 Every tool error ends with one next step

- Requirement: A tool error returns `is_error` true with text ending in exactly one `Next:` line, the same line the CLI prints for the same failure.
- What this means: Errors from `Stop` carry the message and one next command. A caution verb called without `confirm` explains what it would do and names the call with `confirm` true as the next step.
- Why: An error that names the next command keeps an agent on the surface instead of sending it into the source code, where it starts guessing at the design.
- How it shows: `template_forget` without `confirm` returns the caution text and `Next: If you are sure: call template_forget with confirm true`.
- Build: `run_tool()` does this now.
- Acceptance: For each error path of the template's tools, the text has exactly one `Next:` line, and it matches the CLI's next step for the same failure.
- Relates to: CLI-009, CLI-018, BASE-013.
- Status: confirmed.

### MCP-007 Server instructions are composed live from the base text and each module's instructions

- Requirement: The server's instructions are the chassis base text followed by each surfaced module's concise instructions, in module id order, composed when a connection starts.
- What this means: The base text says what Metaform is, how tools are named, how arguments work, and that errors end with a next step. Each module on the surface adds a section headed by its id. Nothing is cached in files, so enabling, disabling or narrowing takes effect on the next connection. The same composed text is available on the CLI, so an agent without MCP reads the same instructions. The command name for that is open.
- Why: Live instructions have one source. A module's instructions are never copied anywhere that could go stale.
- How it shows: Enable a module and reconnect: its section appears. Disable it and reconnect: its section is gone.
- Build: `instructions()` in `mcp_server.py` composes the text. Add a module field for concise instructions, per MCP-008. It replaces the use of `purpose` here, if the two differ; that is open. The base text lives in the chassis, because every module surface uses it.
- Acceptance: The instructions returned at initialization contain exactly the sections of the surfaced modules, in id order, and change after an enable or disable with no other step.
- Relates to: MCP-008, MCP-009, BASE-012, CLI-005.
- Status: confirmed.

### MCP-008 Each module adds concise instructions that defer to help

- Requirement: Each module declares short instructions that give an agent enough to work with the user, and point to `metaform help <module>` for everything else.
- What this means: The text is low in context. It says what the module is for, when to use it, and where the details are. It does not list every verb or switch, because help does that. The template shows the expected length and shape.
- Why: Agents start with little context. The details stay in help, where they are current and cost nothing until needed.
- How it shows: The template module's section in the instructions is a few sentences, ending with `metaform help template`.
- Build: Add a field to the `Module` declaration in `src/metaform/module.py`. Its relation to `purpose` is open. Update the template and its README.
- Acceptance: A module missing the field fails to load with a next step. It is not served with empty instructions.
- Relates to: MCP-007, BASE-012, BASE-019.
- Status: confirmed. The field name and its relation to `purpose` are open.

### MCP-009 A project with no intake gets a notice to delegate the intake to a subagent

- Requirement: When the folder's project has no intake, the instructions say so and tell the agent to have a subagent perform the intake. The subagent reads its instructions from Metaform by name, through the CLI or MCP. The orchestrator passes only where to read them.
- What this means: Metaform never starts a model. The notice is addressed to the agent reading it. The orchestrator tells a subagent the command or tool that returns the intake instructions, and never the instruction text itself. The subagent reads the text word for word and writes its result back through the same kind of plain commands and tools. The same notice appears in `metaform` status output, so an agent without MCP sees it too.
- Why: Intake is agent work, and hosts start subagents in different ways, so a command that ran the intake could not work in every host. One source means every worker reads the same text unaltered, and the results depend on the procedure, not on how an orchestrator reworded it. The nonce later replaces the name as the handle, without changing how anything works.
- How it shows: In a registered project with no intake, the instructions contain a notice in this shape: the project has no intake yet; have a subagent perform it; tell the subagent to read its instructions with the named command or tool and follow them. After an intake is stored, the notice is gone.
- Build: "Has an intake" means the project holds an intake layer in the store. The check reads the store through the data access object. The intake instructions come from the module that owns the intake, served by name: recommended `metaform intake prompt` and the tool `intake_prompt`. The owning module and the exact names are open.
- Acceptance: Instructions for a project with no intake layer contain the notice and name a command that exists on the surface. Instructions for a project with an intake layer do not contain it. The text returned by the named command is byte-identical to the stored intake instructions.
- Relates to: MCP-007, MCP-024, CLI-005, LAYER-001, STORE-013.
- Status: confirmed. The owning module and the command names are open.

### MCP-010 AI tools start the server with uvx

- Requirement: The registration each AI tool receives runs `uvx --from <source> metaform mcp`, where the source is the user's built wheel or the published distribution.
- What this means: uvx gives the server its own environment with its own dependencies, the same way on every system. For a local build, the source is the absolute path of the wheel. Once published, it is the distribution name. The command and the Python package stay `metaform` either way.
- Why: The server runs isolated from whatever else is installed, with the modules the user enabled, on Linux, macOS and Windows alike.
- How it shows: A tool's MCP entry reads `"command": "uvx", "args": ["--from", "<source>", "metaform", "mcp"]`.
- Build: The installer writes this entry, per MCP-016. `uv` must be present, per MCP-013.
- Acceptance: The installer's proof step (MCP-017) launches exactly the registered command and lists tools. A registration that cannot start fails that step.
- Relates to: MCP-013, MCP-016, MCP-017, BASE-021.
- Status: confirmed. The PyPI distribution name is undecided; `metaform` belongs to an unrelated package.

### MCP-011 The server serves the right project when the host starts it outside the project folder

- Requirement: The server resolves the project the agent is working in, even when the host starts it with a working folder outside the project.
- What this means: Some hosts start the server in the project folder, and some do not; a desktop app may start it with no working folder. The design for this is open.
- Why: A server bound to the wrong folder serves the wrong project's map and surface.
- How it shows: Open.
- Build: Open. Old code passed an environment variable; that is not confirmed design.
- Acceptance: Open.
- Relates to: MCP-010, CLI-021, STORE-002.
- Status: open.

### MCP-012 Remote hosting and nonces come later

- Requirement: The MVP serves MCP locally over stdio, with data in `~/.metaform`, and has no nonces.
- What this means: Remote hosting, where a server holds the data for several users over HTTP, is a later goal. The nonce, the handle that carries a job's text to a worker exactly as written, is designed after the MVP. Until then, instructions are read by name (MCP-009).
- Why: The first test and the MVP need a working local server. Remote hosting changes where the data lives, and nonces depend on their own design.
- How it shows: `metaform mcp` has no transport or nonce options.
- Build: Nothing is built for either now.
- Acceptance: None needed.
- Relates to: MCP-009.
- Status: confirmed.

## Installer

### MCP-013 Setup checks first

- Requirement: `metaform install` first shows the system, the Python version, whether `uv` is present, and which AI tools it found, and stops with the exact fix when something required is missing.
- What this means: Nothing is changed before the checks pass. A missing `uv` gives the one command that installs it on this system. The installer never installs anything itself.
- Why: Setup touches other tools' configuration. Failing early with the fix beats a half-finished setup, and installing software behind the user's back surprises them.
- How it shows: The first screen lists each check with its result. With `uv` missing, it ends with `Next:` and the install command for this OS.
- Build: An `install` verb, in the chassis CLI unless BASE open question 5 places it in a module. Checks use `shutil.which` and `platform`. The screen uses the chassis settings-screen code, `tui.py`, so it looks like the rest of Metaform.
- Acceptance: With `uv` absent from PATH, `metaform install` changes no files and exits nonzero with one `Next:` line.
- Relates to: MCP-010, CLI-001.
- Status: recommended.

### MCP-014 The installer asks by default, and named tools or `all` set up without asking

- Requirement: `metaform install` asks which detected tools to set up. `metaform install <tool> ...` sets up the named tools without asking, and `metaform install all` sets up every detected tool without asking.
- What this means: The tool names are nouns, because they are what the verb acts on. `all` is a pronoun standing for every detected tool, so it is an argument, not a switch. Names are the ones people know: `claude`, `codex`, `cursor`, `gemini`, `copilot`, `vscode`, and the others in MCP-016. A name that is not detected is an error with one next step. Every form ends with a report of what changed.
- Why: No one is surprised by changes to their tools, and scripts can still install without questions. Naming what to install already means do not ask.
- How it shows: `metaform install` shows a checklist with the detected tools ticked. `metaform install claude codex` sets up those two and prints the report. `metaform install all` sets up everything detected.
- Build: The checklist uses `tui.py`. With no terminal and no names, the installer changes nothing and names both forms in its `Next:` line. `--` ends switch parsing, as everywhere.
- Acceptance: With stdin not a terminal and no nouns, no file changes. `install claude` touches only Claude Code's configuration and the skill folders for Claude. `install all` touches every detected tool and no undetected one.
- Relates to: CLI-001, CLI-002, CLI-003, MCP-015.
- Status: asking by default is confirmed. The noun form and `all` are recommended.

### MCP-015 A preview comes before any write, and every changed file is backed up

- Requirement: Before writing, the installer lists every file it will create or change and where each backup will go, and writes only after one confirmation.
- What this means: The preview names each tool's config file or registration command, and each skill file. Each existing file is copied to a backup before it changes. Other entries in a tool's config are preserved. With named tools or `all`, the preview is printed as part of the report and no confirmation is asked.
- Why: Setup changes other programs' configuration. A user sees exactly what will happen and can undo it.
- How it shows: A table of files and backups, then a single confirm.
- Build: Backups go to `~/.metaform/backups/install/<timestamp>/`, mirroring each file's path. Recommended; the old installer put backups next to each config file. JSON configs are merged by key, never rewritten from scratch.
- Acceptance: After install, each changed config still holds every entry it had before, and a backup byte-identical to the original exists.
- Relates to: MCP-016, MCP-020.
- Status: recommended.

### MCP-016 Each tool is registered through its own mechanism, per OS

- Requirement: The installer registers the server with each chosen tool through that tool's own registration command where one exists, and otherwise by merging an entry into its user-level config file, at the location for the current OS.
- What this means: Registration is user-level and never touches a project folder. Recommended table:

| Tool | Mechanism | Location |
|---|---|---|
| Claude Code | `claude mcp add --transport stdio --scope user metaform -- uvx --from <source> metaform mcp` | Claude Code manages `~/.claude.json` |
| Codex | `codex mcp add metaform -- uvx --from <source> metaform mcp` | `~/.codex/config.toml`, or `$CODEX_HOME` |
| Gemini CLI | `gemini mcp add --scope user metaform uvx --from <source> metaform mcp` | `~/.gemini/settings.json` |
| Cursor | merge `mcpServers.metaform` | `~/.cursor/mcp.json` |
| VS Code | `code --add-mcp '{"name":"metaform","command":"uvx","args":[...]}'` | user profile `mcp.json` |
| Copilot CLI | open | open |
| Factory | open | open |
| Claude Desktop | open whether it is a target | macOS `~/Library/Application Support/Claude/claude_desktop_config.json`, Windows `%APPDATA%\Claude\claude_desktop_config.json` |

  On Windows, `~` is `%USERPROFILE%`.
- Why: A tool's own command knows its current config format. Writing its files by hand breaks when the format changes. User-level registration serves every project, and nothing is written into project folders.
- How it shows: After install, `claude mcp list` shows `metaform`.
- Build: Salvage detection and registration from the old installer (`git show 6d991b7^:src/metaform/installation.py`) only where it matches this table. The server entry is the uvx form, never a bare launcher path. Detection is by the tool's executable on PATH, or its config folder for tools without one.
- Acceptance: Per tool and per OS in CI: after install, the tool's own list command, where it has one, shows `metaform` with the uvx entry.
- Relates to: MCP-010, MCP-015, MCP-017, QUAL-003.
- Status: recommended. Paths and commands are not verified against each tool's current docs on each OS. Copilot CLI, Factory and Claude Desktop are open.

### MCP-017 Setup proves each tool can start the server

- Requirement: After registering, the installer launches the server with the exact command it registered for each tool, initializes it and lists its tools, and reports pass or fail per tool with the reason.
- What this means: The installer proves that the entry it wrote starts a working server. It does not prove that the host tool applies the server's instructions; each host decides that.
- Why: A written entry is not a working setup. This check turns installed into working.
- How it shows: The report lists each tool with `server starts, N tools` or the failure and one next step.
- Build: An MCP client call from the installer, using the SDK's stdio client, against the registered command and arguments.
- Acceptance: A registration with a wrong source path reports fail for that tool and exits nonzero.
- Relates to: MCP-002, MCP-010, MCP-018.
- Status: recommended.

### MCP-018 Setup ends with a finish screen and one next step

- Requirement: The installer ends by showing what it changed, where the backups are, the proof results, and one next step.
- What this means: The next step is to open an AI tool in a project folder, or to run `metaform` for status.
- Why: The user knows the state of their system and what to do next, with no surprises afterward.
- How it shows: A summary screen or, without a terminal, the same summary printed.
- Build: Part of the `install` verb.
- Acceptance: None beyond MCP-015 and MCP-017.
- Relates to: MCP-015, MCP-017.
- Status: recommended.

### MCP-019 Running setup again is safe

- Requirement: Running `metaform install` again shows the current state and offers to repair, update or add tools, and never duplicates an entry.
- What this means: Registration is idempotent. An existing `metaform` entry is shown, and replaced only when the user chooses to update it.
- Why: Users rerun setup after upgrades and when something breaks. A duplicate or silently overwritten entry is exactly the surprise setup must avoid.
- How it shows: The checklist marks tools already set up.
- Build: Read each tool's registration before writing.
- Acceptance: Two runs of `install claude` leave exactly one `metaform` entry.
- Relates to: MCP-014, MCP-016.
- Status: recommended. Whether it belongs in the first test is open.

### MCP-020 `metaform uninstall` removes what setup added

- Requirement: `metaform uninstall` removes Metaform's registrations and skills from each tool, and restores from backups where that is safe.
- What this means: Only Metaform's own entries and files are removed. A config changed by the user after install is not rolled back to the backup; only the Metaform entry is removed from it. Metaform's data in `~/.metaform` stays unless the user asks otherwise; how is open.
- Why: A polished setup has a clean way out, and removing Metaform must not undo the user's own changes.
- How it shows: A preview, a confirm, then a report of what was removed.
- Build: Mirror of MCP-015 and MCP-016, using each tool's remove command where one exists.
- Acceptance: After install then uninstall, no tool lists `metaform`, no Metaform skill file remains, and every other entry in each config is unchanged.
- Relates to: MCP-015, MCP-016, MCP-021.
- Status: recommended. Whether it belongs in the first test is open.

### MCP-021 One fixed skill is copied to each chosen tool's global skill folder

- Requirement: The installer writes one fixed, short skill to `~/.metaform/skills/metaform/SKILL.md` and copies it into the global skill folder of each chosen tool, and never into a project folder.
- What this means: The skill says what Metaform is and tells the agent to run `metaform` for the live state and instructions, or use the MCP server's instructions. It carries no module text. It is written as real copies, never symlinks. Recommended global folders:
  - `~/.agents/skills/`, the cross-agent folder
  - `~/.claude/skills/` for Claude Code
  - `~/.codex/skills/` for Codex
  - `~/.cursor/skills/` for Cursor
  - `~/.gemini/skills/` for Gemini CLI
  - `~/.gemini/config/skills/` for Antigravity
  - `~/.copilot/skills/` for Copilot CLI
  - Factory: open

  Each copy lives at `<folder>/metaform/SKILL.md`.
- Why: Live instructions have one source, so enabling or disabling a module never rewrites skill files in several places. Symlinks need admin rights or Developer Mode on Windows. All Metaform data is global, and nothing is written into project folders.
- How it shows: After install, each chosen tool's skill folder holds `metaform/SKILL.md`, identical to the copy in `~/.metaform/skills`.
- Build: The skill text ships inside the chassis package. The old installer wrote `~/.metaform/skills`, `~/.agents/skills`, `~/.claude/skills` and `~/.codex/skills`, and used `gemini skills install` for Gemini. Which Gemini mechanism to use is open.
- Acceptance: After `install claude`, `~/.claude/skills/metaform/SKILL.md` is byte-identical to the chassis copy. No file is written under the current folder. Enabling a module changes no skill file.
- Relates to: MCP-007, MCP-014, MCP-022.
- Status: confirmed. The folder paths come from secondary sources and are not verified. Factory's path and the Gemini mechanism are open.

### MCP-022 Each skill path is proven by the tool loading the skill

- Requirement: For each tool, a test shows that the tool actually loads the Metaform skill from the folder the installer writes.
- What this means: A path is not accepted because a guide lists it. It is accepted when the tool, run in a clean environment, lists or uses the skill from that folder.
- Why: The known paths come from secondary sources, and a skill in the wrong folder fails silently.
- How it shows: Environment verification per tool, recorded with the tool's version.
- Build: A verification script per tool, run where the tool is installed. It cannot run in plain CI without the tool.
- Acceptance: The verification itself.
- Relates to: MCP-021, QUAL-006.
- Status: recommended.

### MCP-023 The installer works on Linux, macOS and Windows

- Requirement: Every installer step runs on Linux, macOS and Windows, using each OS's config locations.
- What this means: Paths resolve through the home folder and each OS's application-data folder. No step assumes a POSIX shell. Registration runs tools' commands directly, never through a shell.
- Why: Everything works on the three targets by default.
- How it shows: The same commands give the same result on each OS.
- Build: `pathlib` throughout. `subprocess.run` with argument lists. The Windows `.cmd` launcher from the old installer is not needed, because uvx starts the server.
- Acceptance: The installer's tests, with tools faked on PATH, run in CI on all three OSes.
- Relates to: QUAL-002, QUAL-003, MCP-016.
- Status: confirmed.

## First working test

### MCP-024 The first working test runs installer, instructions and delegation end to end

- Requirement: A fresh machine goes from installing Metaform to an agent that sees each module's concise instructions and the no-intake notice, and delegates the intake by name.
- What this means: The scenario, in order:
  1. A user builds or obtains the wheel, and has `uv` and at least one AI tool installed.
  2. `metaform install` passes its checks, shows the detected tools, previews the changes, registers the uvx entry and writes the skill, proves the server starts, and ends with one next step.
  3. The user registers a project with `metaform add project <id> <path>`. It has no intake.
  4. The user opens the AI tool in that project folder. The agent receives the server instructions: the base text, each enabled module's concise instructions, and the no-intake notice.
  5. The agent has a subagent perform the intake, telling it only the command or tool that returns the intake instructions.
  6. The subagent reads the instructions by name, unaltered.
  7. After an intake is stored, a new connection no longer shows the notice.

  The template and demo modules are disabled and do not appear.
- Why: This is the smallest run that proves setup works, that agents are oriented by live instructions, and that intake is delegated without rewording.
- How it shows: The steps above, observed in at least one real AI tool.
- Build: Depends on MCP-001 to MCP-021, the intake module (open, MCP-009), the store's intake layer, and the module instructions field.
- Acceptance: An automated run of steps 2 to 7, with a scripted MCP client in place of the AI tool, plus one recorded manual run in a real tool. Step 7 needs the intake module and the store.
- Relates to: MCP-001 to MCP-023, BASE-017, LAYER-001, STORE-013.
- Status: confirmed.

## Open questions

1. When a host starts the server outside the project folder, how does the server know the project (MCP-011)?
2. Which module owns the intake instructions, and what are the command and tool names that serve them by name? The recommendation is `metaform intake prompt` and `intake_prompt` (MCP-009).
3. Is a module's concise-instructions field the existing `purpose` field or a new one (MCP-007, MCP-008)?
4. Which CLI command shows the composed instructions to an agent without MCP: `metaform` status, or a separate command (MCP-007)?
5. Which installer steps belong in the first test? The recommendation is to keep the checks, the preview with backups, and the proof, and to defer re-run repair (MCP-019) and uninstall (MCP-020).
6. How are Copilot CLI and Factory registered, where is Factory's skill folder, and does Gemini get its skill by copy or through `gemini skills install` (MCP-016, MCP-021)?
7. Is Claude Desktop a target (MCP-016)?
8. Do backups go under `~/.metaform/backups/install/` or next to each config file (MCP-015)?
9. Does `metaform uninstall` offer to remove `~/.metaform` data, and how (MCP-020)?
10. What is the PyPI distribution name (MCP-010)?
