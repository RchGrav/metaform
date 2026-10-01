# 06 MCP, installer and agent instructions

This section specifies the MCP module that serves Metaform to AI tools, the `metaform install` setup that registers it and writes the skill, and the instructions an agent receives.
It also defines the first working test, which exercises all three end to end.

## MCP module

### MCP-001 MCP is a module

- Requirement: The MCP server is provided by a module named `mcp`, built on the common base like every other module.
- What this means: The chassis runs completely without MCP. The `mcp` module adds the verb `metaform mcp serve`, which starts the server. The verb is declared for the CLI only, so it is never itself a tool, BASE-035. It uses the same chassis resources as any module: the module registry, the settings, the command surface and the verb declarations. It gets no private access. MCP's library dependencies belong to the module, not the chassis.
- Why: The chassis must stay usable on its own, and every surface stands on the same base. Keeping MCP a module also keeps its compiled dependencies out of the chassis, so a wheel without the MCP module runs anywhere.
- How it shows: `metaform list modules` lists `mcp`. With it disabled, `metaform mcp serve` fails with one next step, `metaform enable mcp`. Everything else in the chassis still works.
- Build: Move `src/metaform/mcp_server.py` into `src/metaform/modules/mcp/`, following the template's shape. Remove `mcp` from `VERBS` and `ALWAYS` in `src/metaform/cli.py` and from `RESERVED` in `src/metaform/loader.py`, and remove the `mcp` command page from the chassis docs. Move the `mcp>=1.10` dependency out of the chassis requirements and into the module's `DEPENDENCIES`, BASE-035 and BASE-041. The module ships enabled.
- Acceptance: With the `mcp` module disabled, `metaform mcp serve` exits 2 with a `Next: metaform enable mcp` line, and the chassis command tests still pass. Importing the chassis package with the `mcp` library absent succeeds.
- Relates to: BASE-003, BASE-026, CLI-001, MCP-002, MCP-003.
- Status: confirmed.

### MCP-002 The server speaks MCP over stdio through the official SDK's low-level server

- Requirement: `metaform mcp serve` serves the Model Context Protocol over stdin and stdout, using the low-level `Server` class of the official `mcp` Python SDK.
- What this means: One process serves one host connection. Tools and instructions are computed on each request from the live module declarations, not registered once with decorators.
- Why: Tools come from module verb declarations and change with the folder's command surface. A server that lists tools per request fits that directly. A decorator-based framework would sit between the declaration and the server and add dependencies without adding anything used.
- How it shows: A host that launches `metaform mcp serve` completes initialization and receives the tool list and the instructions.
- Build: The MCP module declares `DEPENDENCIES = ('mcp>=2.2',)`. In the 2.x SDK the low-level server takes its handlers as constructor arguments: `Server('metaform', version=<chassis version>, instructions=<composed text>, on_list_tools=list_tools, on_call_tool=call_tool)`, run with `stdio_server()` under `anyio.run`. The decorator registration of the 1.x SDK is not used; the minimum version is what makes this constructor available, and the current chassis code runs on it with mcp 2.2.0. `list_tools` returns one `Tool` per surfaced verb, MCP-003. `call_tool` builds a new `Context` for the call, BASE-028: a verb whose `run` is a coroutine function is awaited in the server's loop, so the host's cancellation reaches it, BASE-031; a plain function runs in a worker thread through `anyio.to_thread.run_sync`. The result follows BASE-036. The folder is the server's working folder at start, until D37 is answered, MCP-011.
- Acceptance: An MCP client test starts `metaform mcp serve` as a subprocess, initializes, lists tools and calls one. It protects MCP-003 and MCP-004 through real protocol traffic.
- Relates to: MCP-001, MCP-003.
- Status: recommended.

### MCP-003 Each module verb is one tool, built from the same declaration as its CLI command

- Requirement: Every verb of every module on the folder's command surface is served as a command of the module's tool, built from the same declaration that builds its CLI command. Corrected 2026-09-28 by CLI-037: a module is one tool, and a verb is reached inside it; before, every verb was a tool of its own named `<module>_<verb>`.
- What this means: The tool's description is the verb's summary. Its input schema comes from the verb's nouns and switches. A module author declares a verb once and gets the CLI command, its help and its tool. Names must match `^[a-zA-Z0-9_-]{1,64}$` and contain no double underscore. A verb whose name would break that rule is refused when the module loads, with the reason. It is not silently skipped.
- Why: One declaration for both surfaces means CLI and MCP never disagree, and an agent without MCP loses nothing. Because every capability is its own tool, a host can grant a capability such as importing prompts or creating memory layers to one permitted agent, and ordinary agents never need that tool.
- How it shows: The hello module's `greet` verb appears as the tool `hello_greet`, with the same summary as `metaform help hello greet`.
- Build: For each surfaced verb whose `surfaces` include `mcp`: name `<module>_<verb>`; description the verb's summary, followed by ` Caution: <caution>` for a caution verb; input schema `{"type": "object", "properties": {...}, "required": [...], "additionalProperties": false}` with one property per noun, typed by BASE-035, which gives the schema for each noun kind including `bool` and `json`, a many noun as an array, required nouns listed in `required`; one property per switch the verb reads, keyed by the setting key, typed by CLI-027; each noun and switch property carries the noun's or the setting's help as its `description`, as does every property of the chassis's own tools, `set`, `feedback`, `list_reports` and `read_report`, so an agent reads over MCP what `metaform help` says, such as the values `map_knowledge`'s `op` takes; `confirm` of type boolean for a caution verb; and on every tool, an optional `project` property of type string, MCP-025. An invalid tool name is refused at load, BASE-037. A tool's result is the verb's result, BASE-036, so every tool result that holds a join carries the join's `layer`, the name of the layer it comes from, exactly as the CLI shows it, STORE-025, LAYER-016. The current code puts all nouns in one `nouns` array and silently skips invalid names; both change.
- Acceptance: A verb added to a test module appears as a tool with no MCP code written for it. A module declaring an invalid verb name fails to load and says why.
- Relates to: BASE-006, CLI-001, MCP-004, MCP-005.
- Status: confirmed. Corrected 2026-09-27 by CLI-037: one tool for each verb of every module is not the design; the record stands for building a command and its tool from one declaration.

### MCP-004 The tool list follows the folder's command surface

- Requirement: A tool exists on the MCP server exactly when its command is on the folder's command surface: it is listed only then, and it runs only then.
- What this means: The `modules` setting and the module enabled state decide the surface. `metaform mcp serve` itself is never cut off by narrowing: it is the transport, not a command an agent runs, so it starts whatever `--modules` says, and `--modules` narrows the tools it lists and runs. The chassis tools that always run, `set`, `feedback`, `list_reports` and `read_report`, stay listed, CLI-022. A command outside the surface is neither listed nor callable. A call to it returns an error with one next step. Harness tool permissions can narrow the surface further, but never widen it.
- Why: The command surface governs what exists, so the narrowing holds even when a host grants every tool. The orchestrator that narrowed the surface holds the way back; a subagent meets only what is on the surface.
- How it shows: `metaform set --modules hello` in a folder. `metaform mcp serve` still starts there, and a new MCP connection from that folder lists only `hello_*` tools and the always-run chassis tools. A call to `map_where` returns `Error: No tool map_where on this surface.` followed by one `Next:` line.
- Build: The surface is the loaded modules whose ids pass the `modules` check of CLI-022 for the server's folder, and within them the verbs whose `surfaces` include `mcp` and whose `supported_os` includes this system, BASE-016. `list_tools` lists exactly those. `call_tool` for any other name returns `is_error` true with `Error: No tool <name> on this surface.` and `Next: metaform help commands`.
- Acceptance: With the surface narrowed to a module other than `mcp`, `metaform mcp serve` starts and serves; the narrowed-out tool is absent from `tools/list`, and calling it by name returns `is_error` true. With the surface restored, both work.
- Relates to: CLI-022, BASE-016, MCP-003.
- Status: confirmed. Corrected 2026-09-27 by CLI-037 and CLI-038: what an agent receives is the top menu and what its folder is given.

### MCP-005 Tool arguments follow the command grammar, and booleans appear once

- Requirement: A tool takes each of the verb's nouns and each switch as a named argument. A boolean setting appears once, as a boolean named after the setting, and is left out when not given.
- What this means: Each noun is a named property, the name from its declaration. A switch that takes a value has the JSON type of its setting kind, CLI-027. A boolean appears as `tmux: true | false`. Leaving it out means not given, so the stored or default value applies. The no-form exists for people typing on a command line. An agent never sees it and never has to resolve a double negative. `confirm` is a per-call boolean, present only on caution verbs, and never a setting.
- Why: The CLI grammar is verbs, nouns and switches, and MCP carries the same grammar in JSON. A boolean has three parsing cases: on, off and not given. Absent is how JSON says not given. One argument per setting keeps the tool schema free of contradictions such as `tmux: true, no_tmux: true`.
- How it shows: The schema for a verb with a boolean setting `tmux` shows one property, `tmux`, of type boolean. Calling it with `tmux: false` runs that call with tmux off, even when `--tmux` is glued on. Calling it without `tmux` uses the stored value.
- Build: Switch properties come from the module's settings declarations, not a separate adverb list, CLI-012. A call's switch arguments become `Context.switches` for that call only; `false` is passed through as off. Today the code drops `False`, which makes off impossible over MCP; that changes. A noun's value is read by BASE-035's rule: a `str` noun sent a JSON value that is not a string reaches the verb as that value's JSON text, with a notice in the result and no error; an `int` or `bool` noun sent a value that is not its kind stops the call with the command line's next step. A switch is read by its kind the same way, CLI-027: a `str` or `select` switch, and a `list` member, sent another type is read as its JSON text with the same notice; an `int` or `bool` switch sent another type stops the call. The chassis's own tools, `feedback`, `list_reports` and `read_report`, BASE-045, and the history, prompt and clear tools of MCP-004, read their arguments by the same rule, so every tool on the MCP surface reads a call one way: a text argument sent another JSON type is read as its JSON text, with the notice `<key> is text; what was sent was kept as its JSON text.` as a `Notice: <key>: <message>` line in the block before the result, where a module verb's notices appear; an integer or boolean argument sent another type, and an array argument sent no array, stop the call with the command line's next step.
- Acceptance: A glued-on boolean called with `false` runs off for that call, and the stored value remains on afterward. A call without the argument uses the stored value.
- Relates to: CLI-011, CLI-012, CLI-015, CLI-018, MCP-003.
- Status: recommended.

### MCP-006 Every tool error ends with one next step

- Requirement: A tool error returns `is_error` true with text ending in exactly one `Next:` line, the same line the CLI prints for the same failure, and errors are kept to calls that cannot be read at all; everything else is a notice, BASE-044.
- What this means: Errors from `Stop` carry the message and one next command. A caution verb called without `confirm` explains what it would do and names the call with `confirm` true as the next step.
- Why: An error that names the next command keeps an agent on the surface instead of sending it into the source code, where it starts guessing at the design.
- How it shows: `hello_forget` without `confirm` returns the caution text and `Next: If you are sure: call hello_forget with confirm true`.
- Build: A `Stop` raised by the verb, or by the dispatch checks, becomes a result with `is_error` true whose text is `Error: <message>` and `Next: <next_step>`. A caution verb called without `confirm: true` raises `Stop(caution, 'If you are sure: call <tool name> with confirm true')` before it runs. An unexpected exception becomes `Error: <type>: <message>` and `Next: metaform list modules`.
- Acceptance: For each error path of the hello module's tools, the text has exactly one `Next:` line, and it matches the CLI's next step for the same failure.
- Relates to: CLI-009, CLI-018, BASE-013, BASE-044.
- Status: confirmed.

### MCP-007 Server instructions are composed live from the base text and each module's instructions

- Requirement: The server's instructions are the chassis base text followed by each surfaced module's concise instructions, in module id order, composed when a connection starts.
- What this means: The base text says what Metaform is, how tools are named, how arguments work, and that errors end with a next step. Each module on the surface adds a section headed by its id. Nothing is cached in files, so enabling, disabling or narrowing takes effect on the next connection. The same composed text is available on the CLI, so an agent without MCP reads the same instructions. The command name for that is open.
- Why: Live instructions have one source. A module's instructions are never copied anywhere that could go stale.
- How it shows: Enable a module and reconnect: its section appears. Disable it and reconnect: its section is gone.
- Reporting: the base text always tells agents that an agent that cannot continue stops and submits a trouble report with the `feedback` tool instead of retrying, BASE-044. When `--debug` is on for the folder, it also asks for feedback on the Metaform process; `--report` governs the intake report line in the intake footer, CLI-034.
- Build: The text is assembled as the base text; then, for each surfaced module in id order, a blank line, the line `## <id>`, and the module's `purpose`; then, for each surfaced module in id order whose status hook, BASE-035, returns a notice, a blank line and that notice. The notice of MCP-009 arrives this way, from the intake module's hook. Lines end with a single newline and the text ends with one newline. D39 and BASE-035. The base text lives in the chassis, because every surface uses it, and reads exactly:
  ```
  Metaform keeps this project's functional map: what each part is for, who receives what it does, and how. Read the map before you change the project, so you work from the purpose of each part. Each tool comes from a module; the sections below say what each module is for. A tool named <module>_<verb> takes the verb's nouns and switches as named arguments. A tool error ends with the one next step to take. For any module's full help, run metaform help <module>.
  ```
  `metaform help agents` prints the same composed text for the folder, CLI-029, so an agent without MCP reads the same instructions.
- Acceptance: The instructions returned at initialization contain exactly the sections of the surfaced modules, in id order, and change after an enable or disable with no other step.
- Relates to: MCP-008, MCP-009, BASE-012, CLI-005, BASE-044, CLI-034.
- Status: superseded by MCP-031 on 2026-09-30. The base text wording is recommended. Corrected 2026-09-27 by MCP-029.

### MCP-008 Each module adds concise instructions that defer to help

- Requirement: Each module declares short instructions that give an agent enough to work with the user, and point to `metaform help <module>` for everything else.
- What this means: The text is low in context. It says what the module is for, when to use it, and where the details are. It does not list every verb or switch, because help does that. The template shows the expected length and shape.
- Why: Agents start with little context. The details stay in help, where they are current and cost nothing until needed.
- How it shows: The hello module's section in the instructions is a few sentences, ending with `metaform help hello`.
- Build: The `purpose` field of `Module`, BASE-035, following D39's recommendation. A module whose `purpose` is empty fails to load with the next step `metaform help hello`. The template and its README show the expected length: two to four sentences ending with `metaform help <id>`. The shipped modules' texts are exactly:
  - `map`: `Reads and writes this project's functional map. Start with map_roots: it returns the map's entry, the CQU and the DE with their joins, and the root elements. Before changing a part, read it with map_where or map_element and follow its joins: the receiver holds the purpose, the provider delivers the function. Record what you learn at a node with the memory tools; to build or improve a knowledge layer, use map_knowledge, naming the layer on every call: create it, add, edit and remove its objects one at a time, and finish it when the task is done. Details: metaform help map.`
  - `intake`: `Serves the Canonical Intake instructions, records the intake as it is reasoned, and tracks whether this project has an intake. The intake is agent work: a subagent reads its instructions with intake_prompt and follows them. Details: metaform help intake.`
  - `memory`: `Notes that agents keep at the map's own nodes, in the reference memory server's operations. When the map is wrong or incomplete at a node, add an observation there so the next agent reads it where it looks. Details: metaform help memory.`
  - `mcp`: `Serves Metaform's tools to AI tools over MCP. Every tool is also a metaform command on the CLI. Details: metaform help mcp.`
- Acceptance: A module missing the field fails to load with a next step. It is not served with empty instructions.
- Relates to: MCP-007, BASE-012, BASE-019.
- Status: confirmed. Using `purpose` follows D39, recommended. Corrected 2026-09-27 by MCP-029.

### MCP-009 A project with no intake gets a notice to delegate the intake to a subagent

- Requirement: When the folder's project has no intake, the instructions say so and tell the agent to have a subagent perform the intake. The subagent reads its instructions from Metaform by name, through the CLI or MCP. The orchestrator passes only where to read them.
- What this means: Metaform never starts a model. The notice is addressed to the agent reading it. The intake goes to a fresh subagent with no stake in the project, carrying only the intake text and the target; the main agent performs it itself only when that is the only choice. The orchestrator tells a subagent the command or tool that returns the intake instructions, and never the instruction text itself. The subagent reads the text word for word, performs the method, recording the map one object per call through the intake tools as it reasons it, and finishes it with `intake_finish` after a proofing pass, BASE-039. The served text ends with the intake module's lines saying how to record the result; the intake text itself is never edited. The same notice appears in `metaform` status output, so an agent without MCP sees it too. Offering the intake, the agent also suggests the layers of MCP-027.
- Why: Intake is agent work, and hosts start subagents in different ways, so a command that ran the intake could not work in every host. One source means every worker reads the same text unaltered, and the results depend on the procedure, not on how an orchestrator reworded it. An agent embroiled in coding work carries the bias of that work into the map, LAYER-014; a fresh agent with no stake maps the project for the purpose of the analysis alone.
- How it shows: In a registered project with no intake, the instructions end with:
  ```
  This project has no intake yet. Have a subagent perform it. Tell the subagent to start it with `metaform intake start`, or the `intake` tool's command `start`, and to follow what it returns.
  ```
  After an intake is completed, the notice is gone.
- Build: When the folder resolves to no registered project, no intake notice appears; the text ends instead with a blank line and `This folder is not in a registered project. To register one: metaform add project <id> <path>`. Otherwise the notice comes from the intake module's status hook, BASE-035 and BASE-039, which the chassis calls like any module's hook, so the chassis never checks for the intake module by name. "Has an intake" is `has_intake()`: a finished layer of kind intake exists, STORE-032. The intake layer is building while it is recorded and counts only once it is finished, so a half-recorded intake never clears the notice; while one is being recorded, the hook says so in place of the notice, BASE-039. The notice appears only when the intake module is on the folder's surface, because only surfaced modules' hooks are called. The intake instructions are handed over by the intake module's `start`, BASE-039, exactly as stored except for the filled `<target>` attributes and any `{project_id}` placeholder, with nothing added.
- Acceptance: Instructions for a project with no intake layer and none being recorded contain the notice, and the command it names exists on the surface. Instructions for a project with a finished intake layer do not contain it. The text returned by `intake start` equals the stored intake file with only the `<target>` element's attributes filled.
- Relates to: MCP-007, MCP-024, MCP-027, CLI-028, LAYER-001, LAYER-014, STORE-032, BASE-039.
- Status: confirmed, including recording the intake one object per call through the intake tools, 2026-09-26, and the intake going to a fresh agent with no stake, the main agent performing it only when that is the only choice, 2026-09-19. The intake module, its command names and the notice wording follow D38, recommended. Open against MCP-031, 2026-09-30: the instructions are now the chassis's instructions prompt, which says a new context performs the intake directly and does not delegate it, and no notice is added to them.

### MCP-010 AI tools start the server with uvx

- Requirement: The registration each AI tool receives runs `uvx --from <source> metaform mcp serve`, where the source is the user's built wheel or the published distribution.
- What this means: uvx gives the server its own environment with its own dependencies, the same way on every system. For a local build, the source is the absolute path of the wheel. Once published, it is the distribution name. The command and the Python package stay `metaform` either way.
- Why: The server runs isolated from whatever else is installed, with the modules the user enabled, on Linux, macOS and Windows alike.
- How it shows: A tool's MCP entry reads `"command": "uvx", "args": ["--from", "<source>", "metaform", "mcp", "serve"]`.
- Build: The installer writes this entry, per MCP-016. `uv` must be present, per MCP-013. The source is found in this order: when Metaform is running directly from a wheel file, the path the bootstrap records in `METAFORM_WHEEL`, BASE-042; otherwise the last wheel `metaform build` wrote, recorded as `last_build`, BASE-041. An installed or uvx-run Metaform uses `last_build`. With neither, install stops before changing anything, with the next step `metaform build`. The published distribution name replaces the path once publishing is decided.
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

### MCP-012 Remote hosting comes later

- Requirement: The MVP serves MCP locally over stdio, with data in `~/.metaform`.
- What this means: Remote hosting, where a server holds the data for several users over HTTP, is a later goal. Work is handed to an agent by nonce, BASE-050, over the command line and over MCP alike, MCP-030.
- Why: The first test and the MVP need a working local server, and remote hosting changes where the data lives.
- How it shows: `metaform mcp serve` has no transport options.
- Build: Nothing is built for remote hosting now.
- Acceptance: None needed.
- Relates to: MCP-009, BASE-050, MCP-030.
- Status: confirmed. The statement that nonces are dropped, recorded here on 2026-09-25, was wrong and was removed on 2026-09-29.

## Installer

### MCP-013 Setup checks first

- Requirement: `metaform install` first shows the system, the Python version, whether `uv` is present, and which AI tools it found, and stops with the exact fix when something required is missing.
- What this means: Nothing is changed before the checks pass. A missing `uv` gives the one command that installs it on this system. The installer never installs anything itself.
- Why: Setup touches other tools' configuration. Failing early with the fix beats a half-finished setup, and installing software behind the user's back surprises them.
- How it shows: The first screen lists each check with its result. With `uv` missing, it ends with `Next:` and the install command for this OS.
- Build: An `install` verb in the chassis CLI, per D28's recommendation. Checks, in order:
  - System: `platform.system()` mapped to linux, macos or windows.
  - Python: the running version against the `Requires-Python` of the Metaform distribution, read with `importlib.metadata`; today `>=3.11`.
  - uv: `shutil.which('uv')` and `shutil.which('uvx')`. When missing, the next step is uv's own install command for the system: on Linux and macOS `curl -LsSf https://astral.sh/uv/install.sh | sh`; on Windows `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"`.
  - Source: MCP-010.
  - Tools: detection per MCP-016.
  With a terminal, the checks show on a screen built with the same `prompt_toolkit` code as the settings screen, CLI-026; without one, they print as lines.
- Acceptance: With `uv` absent from PATH, `metaform install` changes no files and exits nonzero with one `Next:` line.
- Relates to: MCP-010, CLI-001.
- Status: recommended. The uv install commands are uv's documented ones and are checked against uv's docs during the build, E2.

### MCP-014 The installer asks by default, and named tools or `all` set up without asking

- Requirement: `metaform install` asks which detected tools to set up. `metaform install <tool> ...` sets up the named tools without asking, and `metaform install all` sets up every detected tool without asking.
- What this means: The tool names are nouns, because they are what the verb acts on. `all` is a pronoun standing for every detected tool, so it is an argument, not a switch. Names are the ones people know: `claude`, `codex`, `cursor`, `gemini`, `copilot`, `vscode`, and the others in MCP-016. A name that is not detected is an error with one next step. Every form ends with a report of what changed.
- Why: No one is surprised by changes to their tools, and scripts can still install without questions. Naming what to install already means do not ask.
- How it shows: `metaform install` shows a checklist with the detected tools ticked. `metaform install claude codex` sets up those two and prints the report. `metaform install all` sets up everything detected.
- Build: The checklist uses `tui.py`. With no terminal and no names, the installer changes nothing and names both forms in its `Next:` line. `--` ends switch parsing, as everywhere.
- Acceptance: With stdin not a terminal and no nouns, no file changes. `install claude` touches only Claude Code's configuration, `~/.claude/skills/metaform/`, and the shared skill copies `~/.metaform/skills/metaform/` and `~/.agents/skills/metaform/`, MCP-021. `install all` touches every detected tool and no undetected one.
- Relates to: CLI-001, CLI-002, CLI-003, MCP-015.
- Status: asking by default is confirmed. The noun form and `all` are recommended.

### MCP-015 A preview comes before any write, and every changed file is backed up

- Requirement: Before writing, the installer lists every file it will create or change and where each backup will go, and writes only after one confirmation.
- What this means: The preview names, for each tool, the registration command it will run or the config file it will merge into, and in both cases the file that ends up changed, and each skill file. For a tool registered through its own command, the file backed up is the file that command manages, as listed in MCP-016. Each existing file is copied to a backup before it changes. Other entries in a tool's config are preserved. With named tools or `all`, the preview is printed as part of the report and no confirmation is asked.
- Why: Setup changes other programs' configuration. A user sees exactly what will happen and can undo it.
- How it shows: A table of files and backups, then the single question `Apply these changes? [y/N]`. Only `y` or `yes`, any case, applies them.
- Build: Backups go to `~/.metaform/backups/install/<UTC timestamp YYYYMMDDTHHMMSSZ>/`, mirroring each file's path under the user's home, E1. JSON configs are merged by key, never rewritten from scratch, and the merged file is written beside the old one and moved into its place, so a crash never leaves half a file. A JSON config that is not an object holding an `mcpServers` object, such as one with comments, is left unchanged and the install stops, naming the file and its backup, with the entry to add by hand as the next step. TOML configs are written only through the tool's own command. Each tool's own command, such as `claude mcp add`, has two minutes to finish; one that does not stops the install, naming the tool. Each tool is recorded as installed as soon as its registration succeeds, so a failure at a later tool never hides it from the next run, MCP-019.
- Acceptance: After install, each changed config still holds every entry it had before, and a backup byte-identical to the original exists.
- Relates to: MCP-016, MCP-020.
- Status: recommended.

### MCP-016 Each tool is registered through its own mechanism, per OS

- Requirement: The installer registers the server with each chosen tool through that tool's own registration command where one exists, and otherwise by merging an entry into its user-level config file, at the location for the current OS.
- What this means: Registration is user-level and never touches a project folder. Recommended table:

| Noun | Tool | Detected by | Mechanism | File changed |
|---|---|---|---|---|
| `claude` | Claude Code | `claude` on PATH | `claude mcp add --transport stdio --scope user metaform -- uvx --from <source> metaform mcp serve` | `~/.claude.json` |
| `codex` | Codex | `codex` on PATH | `codex mcp add metaform -- uvx --from <source> metaform mcp serve` | `~/.codex/config.toml`, or under `$CODEX_HOME` |
| `gemini` | Gemini CLI | `gemini` on PATH | `gemini mcp add --scope user metaform uvx --from <source> metaform mcp serve` | `~/.gemini/settings.json` |
| `cursor` | Cursor | the folder `~/.cursor` | merge `mcpServers.metaform` | `~/.cursor/mcp.json` |
| `vscode` | VS Code | `code` on PATH | `code --add-mcp '{"name":"metaform","command":"uvx","args":[...]}'` | the user profile's `mcp.json` |
| `copilot` | Copilot CLI | `copilot` on PATH | unverified, E2 | unverified |
| `factory` | Factory | `droid` on PATH | unverified, E2 | unverified |
| `antigravity` | Antigravity | the folder `~/.gemini/config` | skill only, MCP-021; MCP registration unverified | unverified |
| `claude-desktop` | Claude Desktop | its config folder | merge `mcpServers.metaform`, after D42 | macOS `~/Library/Application Support/Claude/claude_desktop_config.json`, Windows `%APPDATA%\Claude\claude_desktop_config.json` |

  On Windows, `~` is `%USERPROFILE%`.
- Why: A tool's own command knows its current config format. Writing its files by hand breaks when the format changes. User-level registration serves every project, and nothing is written into project folders.
- How it shows: After install, `claude mcp list` shows `metaform`.
- Build: Salvage detection and registration from the old installer (`git show 6d991b7^:src/metaform/installation.py`) only where it matches this table. The server entry is the uvx form, never a bare launcher path. Detection is exactly the column above. A tool whose mechanism is unverified is detected and listed, marked `unverified`, and is not offered for setup until its mechanism is confirmed from its own documentation, E2.
- Acceptance: Per tool and per OS in CI: after install, the tool's own list command, where it has one, shows `metaform` with the uvx entry.
- Relates to: MCP-010, MCP-015, MCP-017, QUAL-003.
- Status: recommended. Paths and commands are not verified against each tool's current docs on each OS, E2. Claude Desktop waits on D42.

### MCP-017 Setup proves each tool can start the server

- Requirement: After registering, the installer launches the server with the exact command it registered for each tool, initializes it and lists its tools, and reports pass or fail per tool with the reason.
- What this means: The installer proves that the entry it wrote starts a working server. It does not prove that the host tool applies the server's instructions; each host decides that.
- Why: A written entry is not a working setup. This check turns installed into working.
- How it shows: The report lists each tool with `server starts, N tools` or the failure and one next step.
- Build: The chassis carries a small standard-library client for this, `metaform.probe`, because the chassis must not depend on the `mcp` SDK, BASE-026. It starts the registered command and arguments with `subprocess.Popen`, working folder the user's home, so the surface is every enabled module's; writes newline-delimited JSON-RPC 2.0 to its standard input: `initialize` with protocol version `2025-06-18`, client info `metaform-install`, and empty capabilities; then the `notifications/initialized` notification; then `tools/list`; reads standard output line by line, where every line must be one JSON object: a line with an `id` matching a request is that request's response; a line with a `method` and no `id` is a notification and is ignored; a line with a `method` and an `id` is a server request and is answered with a JSON-RPC error `-32601`; a line that is not JSON fails the proof, because standard output carries only protocol messages. Standard error is read and kept only to show in a failure. Then it closes standard input and stops the process. The whole exchange has a 30 second limit per tool, which covers uvx preparing its environment on first run. Pass means an `initialize` result and a `tools/list` result with at least one tool; the report shows `server starts, N tools`.
- Acceptance: A registration with a wrong source path reports fail for that tool and exits 1. A fake server script that answers correctly reports pass with its tool count.
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
- Build: The installer keeps a record in the base database of what it set up, `installs(tool TEXT PRIMARY KEY, source TEXT NOT NULL, skill_path TEXT, installed TEXT NOT NULL)`. A re-run reads that record to mark tools already set up. For a tool configured by merging a JSON file, it also reads that file and treats an existing `metaform` entry as set up. Updating replaces the one entry; adding writes a new one only when none exists. For a tool registered by its own command, an add refused because an entry the record does not know of is already there, left by an earlier home, runs the tool's remove command and adds again, so the install goes on with the one entry replaced.
- Acceptance: Two runs of `install claude` leave exactly one `metaform` entry.
- Relates to: MCP-014, MCP-016.
- Status: recommended. Whether it belongs in the first test is open.

### MCP-020 `metaform uninstall` removes what setup added

- Requirement: `metaform uninstall` removes Metaform's registrations and skills from each tool, and restores from backups where that is safe.
- What this means: Only Metaform's own entries and files are removed. A config changed by the user after install is not rolled back to the backup; only the Metaform entry is removed from it. Metaform's data in `~/.metaform` stays unless the user asks otherwise; how is open.
- Why: A polished setup has a clean way out, and removing Metaform must not undo the user's own changes.
- How it shows: A preview, a confirm, then a report of what was removed.
- Build: Mirror of MCP-015 and MCP-016, using each tool's remove command where one exists.
  - The tools are those recorded in the home's `installs` table. As for install, MCP-014, `metaform uninstall` asks per tool and then once more before any change, and naming tools or `all` removes without asking; with no names and no terminal nothing changes.
  - Claude Code, Codex and Gemini CLI run their own remove command. Cursor and Claude Desktop lose `mcpServers.metaform`, and VS Code `servers.metaform`, from their JSON config, written whole beside the old file and moved into place.
  - Only Metaform's entry is removed, never the file rolled back to its backup: removing the entry leaves every other entry as it is, and rolling back would undo whatever the user changed after install. Each file is backed up before it changes, under `~/.metaform/backups/uninstall/<UTC timestamp>/`.
  - Each tool's skill copy is removed, and its `metaform` folder when that is left empty. The source copy under the home and the cross-agent copy are removed once no set-up tool is left.
  - The data in the home stays; offering to remove it is question 9.
- Acceptance: After install then uninstall, no tool lists `metaform`, no Metaform skill file remains, and every other entry in each config is unchanged.
- Relates to: MCP-015, MCP-016, MCP-021.
- Status: recommended. Whether it belongs in the first test is open.

### MCP-021 One fixed skill is copied to each chosen tool's global skill folder

- Requirement: The installer writes one fixed, short skill to `~/.metaform/skills/metaform/SKILL.md` and copies it into the global skill folder of each chosen tool, and never into a project folder.
- What this means: The skill says what Metaform is and tells the agent to run `metaform` for the live state and instructions, or use the MCP server's instructions. It carries no module text. It is written as real copies, never symlinks. The source copy `~/.metaform/skills/metaform/SKILL.md` and the cross-agent copy `~/.agents/skills/metaform/SKILL.md` are written whenever any tool is set up; each chosen tool's own folder gets a copy too. Recommended global folders:
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
- Build: The skill text ships inside the chassis package as `metaform/skill/SKILL.md` and reads exactly:
  ```
  ---
  name: metaform
  description: Use when working in a project registered with Metaform, or when the user mentions Metaform or a functional map. Metaform holds the project's functional map and agent instructions.
  ---

  Metaform keeps a project's functional map: what each part is for, who receives what it does, and how.

  Before you work in a project, run `metaform` in its folder. It shows the project, whether it has an intake, and the next step. Run `metaform help agents` for the current instructions from every enabled module, or read the Metaform MCP server's instructions when it is connected. Follow the next step Metaform gives you.
  ```
  The old installer wrote `~/.metaform/skills`, `~/.agents/skills`, `~/.claude/skills` and `~/.codex/skills`, and used `gemini skills install` for Gemini. Gemini gets a copy in `~/.gemini/skills`, like the others, until its own mechanism is confirmed, E2.
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

- Requirement: A fresh machine goes from installing Metaform to an agent that sees each module's concise instructions and the no-intake notice, delegates the intake by name, and then shares memory at map nodes whose visibility follows layer select and mask.
- What this means: The scenario, in order:
  1. A user builds or obtains the wheel, and has `uv` and at least one AI tool installed.
  2. `metaform install` passes its checks, shows the detected tools, previews the changes, registers the uvx entry and writes the skill, proves the server starts, and ends with one next step.
  3. The user registers a project with `metaform add project <id> <path>`. It has no intake.
  4. The user opens the AI tool in that project folder. The agent receives the server instructions: the base text, each enabled module's concise instructions, and the no-intake notice.
  5. The agent has a subagent perform the intake, telling it only the command or tool that returns the intake instructions.
  6. The subagent reads the instructions by name, unaltered.
  7. The subagent records the intake one object per call through the intake tools and finishes it with `intake_finish`. A new connection no longer shows the notice.
  8. An agent writes a memory at an element and at a join through the memory tools, `memory_add-observations`.
  9. A second agent, on its own connection, reads both back with `memory_open-nodes`.
  10. A mask of the memory layer at the element's address makes that memory disappear from the in-context read there, `map_node`, and clearing the mask, or selecting the layer, makes it appear again. The join's memory follows its receiver's selection in the same way, LAYER-007.

  The modules on in this test are `map`, `intake`, `memory` and `mcp`, all of which ship enabled. `hello` and `template` are the only modules that ship disabled, and they do not appear.
- Why: This is the smallest run that proves setup works, that agents are oriented by live instructions, and that intake is delegated without rewording. Memory and layer selection are in it because memory is how a small wrong inference gets fixed right at the node, and select and mask are how a job controls which layers an agent sees; the first test is not a working Metaform without them.
- How it shows: The steps above, observed in at least one real AI tool.
- Build: Depends on MCP-001 to MCP-021, BASE-038 to BASE-041, LAYER-007, LAYER-012, LAYER-013, STORE-019, STORE-020, STORE-032, and the `purpose` field. The first test's tool list must include `intake_start`, `intake_element`, `intake_join`, `intake_subtype`, `intake_show`, `intake_finish`, `memory_add-observations`, `memory_open-nodes`, `map_select`, `map_mask`, `map_clear`, `map_node`, `map_layers`, `map_tag`, `map_untag`, `map_knowledge`, `map_work`, `feedback`, `list_reports`, `read_report` and `set` with `layers`.
- Acceptance: An automated run of steps 2 to 10, plus one recorded manual run in a real tool. The automated run:
  - Uses a temporary `METAFORM_HOME` and a temporary user home, and puts fake `claude` and `codex` executables first on PATH. Each fake records its arguments to a file and exits 0, so registration is checked without the real tools. The temporary home also holds `.cursor/mcp.json` containing one other server entry, so the Cursor merge and its backup are checked against a real existing file.
  - Every process the test starts inherits its environment, including the temporary `METAFORM_HOME`; the registered command carries no environment of its own, so inheritance is how the probe's server finds the test home. The test needs network access or a warm uv cache for uvx to prepare the server's environment; CI keeps the uv cache between runs.
  - Builds the wheel with `metaform build`, runs `metaform install claude codex cursor`, and checks the recorded registration arguments, the skill copies, the Cursor file holding both its old entry and `metaform`, the backup of the Cursor file byte-identical to the fixture, and a passing proof step against the built wheel.
  - Registers a temporary project folder, then starts the registered command, `uvx --from <wheel> metaform mcp serve`, with that folder as its working folder, using the probe client of MCP-017 as the scripted host. It checks that the instructions hold the base text, the four modules' sections and the notice.
  - Calls `intake` with command `start` and checks the intake text it returns against the stored file with only the target filled.
  - Records a three-element fixture intake one object per call through the intake tools: a CQU, a DE and one SE, with two joins. A join recorded without its purpose is stored with a notice naming `purpose`, and nothing is refused. The intake tools carry no condition, MAP-046; the finish carries a `report` and a `feedback` text.
  - Starts a new connection and checks the no-intake notice is gone.
  - Calls `list_reports` and sees the intake layer's report and feedback; calls `read_report` on each and gets the submitted text back byte for byte; calls `map_work` with `op=add`, `node=element:code.alarm.audible` and `condition=broken`, then `map_work` with `condition=broken`, and gets that element back with its record; calls `feedback` with a freeform text and sees a new feedback file listed.
  - Checks the tool list holds every tool named in Build.
  - On one connection, calls `memory_add-observations` at the DE element and at one join. On a second connection, calls `memory_open-nodes` on both and gets both observations back.
  - Calls `map_node` in context at the DE element and sees the memory; calls `map_mask` for the memory layer at the DE's address and no longer sees it; calls `map_clear` for that mask and sees it again; the join's memory is checked the same way through its receiver's address.
- Relates to: MCP-001 to MCP-023, BASE-017, BASE-039, BASE-040, LAYER-001, LAYER-007, LAYER-012, LAYER-013, MAP-046, STORE-013, STORE-019.
- Status: confirmed. The condition of an object written as a work record with `map_work`, never by the intake tools, follows MAP-046, 2026-09-27.


### MCP-025 Every tool takes an optional project
- Requirement: Every tool accepts an optional `project` argument that names the project for that one call and overrides the folder's project.
- What this means: `project` is the chassis context setting of CLI-021, carried as a per-call value the same way `--project <id>` is on the CLI. A call without it uses the project the server's folder resolves to. A call with it builds its Context for the named project, so two calls running at once can each work in a different project, BASE-028.
- Why: One server serves one connection, and an agent may need to read or write more than one registered project through it. Context carried per call is what keeps concurrent calls from landing in each other's projects.
- How it shows: `map_where` called with `{"address": "code", "project": "notes"}` reads the notes project's store whatever folder the server started in.
- Build: The server adds `"project": {"type": "string", "description": "A registered project id; overrides the folder's project for this call."}` to every tool's input schema, never in `required`. On a call, a given `project` is validated as a registered id, CLI-030; an unknown id is a tool error with `Next: metaform list projects`. The Context for that call gets that project and `Store(project)`; nothing is stored, and the folder's `project` setting is unchanged. This does not settle how the server chooses a project when the call names none and the folder is outside every project; that remains D37 and MCP-011.
- Acceptance:
  - Two concurrent `map_knowledge` calls with `op=add-element` naming two different projects each write one element, each only in its own project's store, BASE-028.
  - A call naming an unregistered project fails with the Next line and writes nothing.
- Relates to: BASE-028, CLI-021, CLI-030, MCP-003, MCP-005, MCP-011.
- Status: recommended. The fallback when no project is named and the folder is outside every project is open, D37.

### MCP-027 Offering an intake, the agent suggests a blind spot challenge and a best-practices layer
- Requirement: When the main agent offers to start an intake, it suggests also creating a blind spot challenge and a knowledge layer that records best practices, and asks the person whether that is all right.
- What this means: Asked what those are, the agent explains: an agent examines the code, the project spec and the code quality enforcement, and puts enforcement in place where there is none; work can be submitted directly in the Metaform web GUI, and the graph shows what work is done and what is not; best practices and code quality are enforced from the start; and any instructions can become knowledge layers that agents see when they are assigned work on that part of the code. The challenge is LAYER-014 and LAYER-015's; the best-practices layer is a knowledge layer built at each node, LAYER-016 and LAYER-020.
- Why: The offer of an intake is when the person decides how Metaform will serve the project. The challenge and the best-practices layer are what put enforcement and practice in place from the start, and asking leaves the choice with the person.
- How it shows: An agent in a project with no intake says it will have a subagent perform the intake, and asks whether to also create a blind spot challenge and a knowledge layer of best practices.
- Build: The suggestion reaches the agent in the intake module's no-intake notice, MCP-009 and BASE-039, after its sentence on delegating the intake; its wording is recommended with the notice's, D38. Submitting work directly in the web GUI waits on D92.
- Acceptance: The composed instructions for a project with no intake hold the suggestion of both layers and the question to the person.
- Relates to: MCP-009, BASE-039, LAYER-014, LAYER-015, LAYER-016, LAYER-020, MAP-048, VIEW-011.
- Status: confirmed as design, 2026-09-26 and 2026-09-27. The notice's wording is recommended; submitting work in the web GUI is open, D92.

### MCP-028 An unfamiliar harness is asked on its first run to provision what it supports
- Requirement: When Metaform runs for the first time under a harness it does not know, it says so and offers help for provisioning each feature the harness supports, and once the agent says it is done, it never asks again.
- What this means: The agent administers its own harness: it sets up what its harness supports, such as the MCP registration, the skill, hooks and whatever is added later, and when it cannot or does not want to, it moves ahead. A harness is known by the parent folder of its binary, since a harness's path may carry its version and some harnesses run from an install folder of their own; paths under the system's temporary folder are ignored. A known harness seeing the offer takes no harm. The help for each feature says what needs to be done to use it, CLI-036. This is the onboarding path for harnesses the installer, MCP-016, does not know.
- Why: The installer sets up only the tools it knows, MCP-016. An agent in any other harness can still give it Metaform's features, because only that agent knows what its harness supports.
- How it shows: The first `metaform` run under an unfamiliar harness says that this is Metaform's first run there, points to the help for provisioning each feature, and says how to finish; after the agent finishes, runs under that harness say nothing of it.
- Build: Open, D96. The record of known harnesses lives in the home, STORE-001.
- Acceptance: Open with D96.
- Relates to: MCP-013, MCP-016, MCP-021, CLI-028, CLI-036, STORE-001.
- Status: confirmed as design, 2026-09-11. Whether it stands beside the installer of MCP-013 to MCP-021, and the commands it offers, are open, D96.

### MCP-029 The instructions tell the agent what to do, and the host shows them whole

- Requirement: The instructions an agent receives when it connects tell it what to do next, and are short enough that the host shows all of them. When the project is not onboarded, they tell the agent to onboard it.
- What this means: The instructions are not a description of each module. They say where the agent is, what state the project is in and the next step to take. What a module is for is read in that module's help, when the agent enters it. The user's request selects the operation; the current project identifies its target. The agent executes the matching module's supplied procedure or prompt through completion and records results as directed. Platform-development guidance applies when the requested task changes Metaform's implementation. This guidance is shared by MCP connections and `metaform help agents`.
- Why: An agent that connects needs its next action. A catalogue of modules gives it things to read and nothing to do, and it is charged for the reading in every session. A host shows only so much: on 2026-09-27 Claude Code cut the instructions off at about 2,000 characters, so the sections after that point never reached the agent, and a notice placed last, where MCP-007 places the no-intake notice, is the first thing lost. The most important line has to be inside what every host shows.
- How it shows: An agent connecting in a project with no intake reads, within the first lines, that the project is not onboarded and what to do about it.
- Build: Open. Today `compose` in `src/metaform/instructions.py` joins the base text and each surfaced module's `purpose`, MCP-007 and MCP-008. Answered by Rich 2026-09-28 at `code.composer.instruction`. The instructions are a few messages, each an imperative that says what to do and how, and no longer than it needs. They say what Metaform is and how it works; they tell the agent to perform an intake when the project has none; to assign work to agents through Metaform, selecting the elements the work concerns; and to start the web GUI before an intake and tell the user its address. A message is shown only when the state it speaks to holds, as the intake message is shown only when there is no intake. A message belongs to the chassis or to the module it concerns, and the module supplies its own. A setting can turn a message off: with `web_autostart` off the message about starting the web GUI is not shown. The wording is the builder's, in this manner, and not Rich's own words. Built 2026-09-28: `compose` in `src/metaform/instructions.py` joins the chassis's own messages and each surfaced module's message for the state the project is in, which the module gives through its status hook, MCP-009. No module is described in them. A project with no map gets the intake's message and, with `web_autostart` on, the web GUI's; a project with a map gets the map's, which says to read a part before changing it, to give work to agents through Metaform at the elements it concerns, and to ask the user at the part a question concerns. On this project they are 1,421 characters.
- Acceptance: Open with the build. It will hold that the whole text is within what the supported hosts show, and that the not-onboarded instruction is in it.
- Relates to: MCP-007, MCP-008, MCP-009, CLI-037.
- Status: confirmed as design, 2026-09-27. It corrects MCP-007 and MCP-008, which compose the instructions from module descriptions. Superseded 2026-09-30 by MCP-031: the wording is not the builder's, and the instructions are the chassis's instructions prompt.

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
11. NEW Does first-run provisioning for an unfamiliar harness stand beside the installer, and through which commands? D96. (MCP-028)
12. NEW Can a person submit work directly in the web GUI, as the explanation offered with an intake says? D92. (MCP-027)
13. NEW What do the instructions say, word for word? (MCP-029)

### MCP-030 A nonce routes an MCP call to the module that serves it

- Requirement: A nonce is taken over MCP as it is on the command line, and the MCP server routes a call that carries one to the module that registered it. A module can in this way be an MCP server of its own services.
- What this means: The agent holding a nonce gets, over MCP, the interface of the module and the step the nonce stands for, and nothing else. The module provides the JSON-RPC interface for its services, and the `mcp` module passes the call to it by the nonce's record, BASE-050.
- Why: An agent works over whichever of the two it has, and the work it was handed is the same work. Routing by the nonce means the `mcp` module needs to know nothing of a module's services to serve them, so a module written by anyone is served like one of Metaform's own.
- How it shows: An agent calls the `metaform` tool with its nonce and is returned what `metaform <nonce>` prints. With the nonce and a command, the command runs in the module that registered the nonce.
- Build: Open. How a module provides its interface, by importing the chassis's data access or by another way, is not decided.
- Acceptance: Open.
- Relates to: BASE-050, BASE-051, CLI-037, MCP-012.
- Status: open. The requirement is confirmed by Rich, 2026-09-29; the build is not designed.

### MCP-031 Prompts are authored in XML files, addressed by name, and never written in Python

- Requirement: Every prompt an agent reads is kept in an XML file, as an element named for the prompt, and the code reads it by that name. What is served is what is between the element's tags. The chassis's prompts are in `src/metaform/resources/prompts.xml`; each module's are in its own `resources/prompts.xml`. The instructions are the chassis's `instructions` prompt. Under its line "modules available." each surfaced module is listed, in module id order, by what is between the tags of its own `instructions` prompt. A module's default `instructions` prompt is `<instructions>Module name is active.</instructions>`, with the module's name in place of "Module name".
- What this means: Prompt wording is edited in one kind of file, found in one place for the chassis and in the same place in every module, without searching the source. The code assembles prompts and fills the places a prompt marks with an empty element, such as `<modules/>`, and does not write their words. Module notices are not added to the instructions. Nothing but the instructions prompt and the Canonical Intake gives an intake agent directions: the intake module's no-map notice and complete line and the map module's notice are removed from status, 2026-09-30.
- Why: Prompt semantics are algorithms tuned by testing across models. Wording written into the code by whoever built it drifts from the system's semantics without anyone seeing it, and instructions sent to every session carry that drift into every model's work. In a file of its own the wording has one author and one place, and a change to it is visible.
- How it shows: `metaform help agents` and the MCP server's instructions print the `instructions` prompt with the module list in place of `<modules/>`. Editing the XML changes what is printed with no change to the code.
- Build: `metaform.prompt_files` reads a prompt by name from a `resources/prompts.xml` folder; `compose` in `src/metaform/instructions.py` fills the instructions prompt. A module's line is its instructions prompt followed by the `instruction` its status hook returns for the folder's state, when it returns one; the web module's autostart message arrives this way, VIEW-015. With no project for the folder the registered projects and the way to register one follow it, from the chassis's `registered` and `no_project` prompts.
- Acceptance: No line of a prompt file's prompts appears in any Python source outside tests. With `debug` off neither `stop` nor `debug` is in the instructions; with it on they end them. The instructions equal the chassis's `instructions` prompt with the surfaced modules' `instructions` prompts listed. Neither the intake notice nor the web notice is in the instructions.
- Relates to: MCP-007, MCP-008, MCP-009, MCP-029, BASE-044.
- Status: confirmed by Rich 2026-09-30, with the instructions prompt in his words. Supersedes MCP-029's "the wording is the builder's." The trouble report and debug feedback prompts, `stop` and `debug`, end the instructions only while the `debug` setting is on, 2026-09-30: sent to every session they were a universal instruction, and the setting's own meaning is to ask agents for feedback and trouble reports.
