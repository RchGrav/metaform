# 04 Chassis, common base and modules

Scope: what the chassis is and owns, the common base every module builds on, how modules are found, loaded, enabled and retired, and how Metaform is versioned, packaged and delivered as wheels.
Out of scope here: the map and layer data model (MAP, LAYER), storage internals (STORE), the command grammar and settings semantics in detail (CLI), the MCP module's tools (MCP), and quality checks (QUAL).

Current code referenced below is the `chassis` branch: `src/metaform/module.py`, `loader.py`, `module_metadata.py`, `events.py`, `settings.py`, `cli.py`, `mcp_server.py` and `modules/template/`.

---

## Chassis

### BASE-001 The chassis runs completely on its own as a CLI
- Requirement: The chassis is a complete, working Metaform with every feature module disabled or physically absent.
- What this means: With no modules, `metaform` still shows status, registers projects, reads and changes settings, gives help, and holds, imports, exports and queries the project data. Feature modules add capabilities; their absence removes only those capabilities. This holds for an installed Metaform and for a directly run wheel.
- Why: The data must stay usable without any module, and every module must stand on the same working base. A chassis that needs a module to function makes that module privileged and makes the data hostage to it.
- How it shows: With the modules folder empty and every system module disabled, `metaform`, `metaform help`, `metaform set`, `metaform unset`, `metaform config --show`, `metaform export` and `metaform import` all work and exit 0.
- Build: The chassis package contains no import of any module package. Chassis verbs live in `cli.py` and never branch on a module id. `loader.discover()` returning an empty list is a normal state, not an error.
- Acceptance: Run the chassis verbs above in a home with all modules disabled; each succeeds. Run them with `src/metaform/modules/` removed from a built wheel; each succeeds. Import `metaform` with every module package unimportable; import succeeds.
- Relates to: BASE-002, BASE-003, STORE, CLI.
- Status: confirmed.

### BASE-002 The chassis owns the data, the settings and the CLI
- Requirement: The chassis is the only owner of Metaform data, settings and the command line, and it provides import, export, query and wheel building for them.
- What this means: All persistent Metaform state is written and read by chassis code. Settings are declared by modules but stored, validated and presented by the chassis. Every command, including module commands, is parsed, dispatched and documented by the chassis. Import, export and query operate on the whole of the data, so they are chassis verbs, not module verbs.
- Why: One owner means one format, one set of rules and one place to fix a fault. Data that a module keeps privately cannot be exported, imported or queried whole, and a command surface parsed in several places drifts apart.
- How it shows: `metaform export` writes every project's data, including what modules stored. `metaform import` restores it. `metaform query` reads it. `metaform build` produces a wheel. No module needs its own storage code.
- Build: New chassis verbs `import`, `export`, `query` and `build`, added to `cli.VERBS` and to `loader.RESERVED`. Their data formats are defined in STORE. The chassis dependencies stay limited per BASE-026.
- Acceptance: A module writes layer data through the data access object; `export` then `import` into an empty home reproduces it, read back through the same object. A module that writes a file into the home outside the data access object is reported by a test over the home folder after the template's verbs run.
- Relates to: BASE-004, STORE-022, STORE-027, CLI.
- Status: confirmed.

### BASE-003 The chassis does not run workflows, and MCP is a module
- Requirement: Workflows and the MCP server are modules built on the common base; the chassis contains neither.
- What this means: The chassis never starts a model, a subagent or a workflow. A workflow is module work. The MCP server is the `mcp` module: it serves the tools and instructions that come from module declarations through the same base every other module uses.
- Why: Workflows are agent work that modules provide. Keeping MCP a module puts it on the same footing as every other module and keeps its compiled dependencies out of the chassis, so a wheel without MCP runs anywhere.
- How it shows: `metaform disable module mcp` leaves every chassis verb working. A wheel built without the `mcp` module carries no `mcp` package dependency.
- Build: The chassis contains no workflow runner and no model launcher. Moving the MCP server into the `mcp` module, its verb, its dependency and its disabled behavior are specified in MCP-001.
- Acceptance: With `mcp` disabled, every chassis verb works. The rest is MCP-001's acceptance.
- Relates to: MCP-001, MCP-007, CLI.
- Status: confirmed.

---

## Common base

### BASE-004 One common base that every module builds on
- Requirement: Modules reach every Metaform resource through one public base, and a module may use everything that base offers.
- What this means: The public base is a small set of stable imports: `metaform.module` for the declaration types and the verb context, `metaform.settings` for declaring settings, `metaform.data` for the data access object, and `metaform.events` for publishing and subscribing. A module may use all of it. There is no prohibition on what a module does beyond that. If modules need a Metaform resource that the base lacks, the resource is added to the chassis base, not built inside a module.
- Why: One implementation of each resource means every module behaves the same way and no module rebuilds what another has. Shared resources in the chassis are what let modules compose.
- How it shows: The template module imports only from these public names. A resource that two modules need appears in the base, and both use it.
- Build: Public names are `metaform.module` (Module, Verb, Subscription, Stop, Context, call), `metaform.settings`, `metaform.data`, `metaform.events`. Everything else in the package is private. Importing a public name creates no database, process or project state; services resolve the active context when called.
- Acceptance: A test lists the template's imports and fails if any is outside the public names. Importing each public name into a fresh interpreter with a missing home creates no files.
- Relates to: BASE-006, BASE-009, BASE-010, STORE-023, CLI-010.
- Status: confirmed.

### BASE-005 The data access object is the only way modules keep data
Specified in STORE-022 and STORE-023: everything a module keeps is a layer written through the data access object, and a verb reaches it as `ctx.store`.

### BASE-006 Modules declare verbs with nouns and switches
- Requirement: A module declares each verb once, with the nouns it acts on and the switches that change how it runs, and that one declaration drives the CLI, help and MCP.
- What this means: Commands are verbs, arguments are the nouns a verb acts on, and switches are adverbs that change how it runs. A verb runs as `metaform <module> <verb> <nouns> [switches]`. Its summary, details, usage and examples come from the declaration. MCP exposes the same verb as the tool `<module>_<verb>`.
- Why: A consistent grammar makes every command predictable. One declaration means the CLI, help and MCP can never disagree.
- How it shows: `metaform help <module> <verb>` shows the page, `metaform <module> <verb> --help` shows the syntax, and the MCP tool list carries the same verb.
- Build: `Verb(name, run, summary, nouns, switches, details, examples, caution, supported_os)`. The current `Verb` has `adverbs: tuple[Adverb, ...]`, declared separately from settings. It changes per CLI-012.
- Acceptance: Declaring a verb in a scratch module makes it appear in `metaform help commands`, in `metaform help <module>` and in the MCP tool list with the same summary.
- Relates to: CLI-012, CLI, MCP.
- Status: confirmed.

### BASE-007 Module switches are settings
Specified in CLI-011, CLI-012, CLI-015 and CLI-018: every long switch a module declares is a setting declared once, booleans have two forms, and `--confirm` is never a setting.

### BASE-008 Modules declare their settings in code
Specified in CLI-010, CLI-019 and CLI-020: a module declares its settings in its own code through `metaform.settings`, one schema drives every surface, selects take choices from a list or the module's data, and the defaults work with zero configuration.

### BASE-009 Verbs run sync or async the same way
- Requirement: A verb or a subscriber may be a plain function or a coroutine, and the chassis runs both the same way.
- What this means: The chassis awaits a coroutine and calls a function; the author does not manage an event loop. Long work can be async without blocking other work the chassis runs in the same loop.
- Why: Module work includes waiting on processes, networks and agents. Authors should not choose between blocking the chassis and writing loop code.
- How it shows: The template's `wait` verb is async and behaves like any other verb on the CLI and over MCP.
- Build: Existing `module.call` runs a coroutine with `asyncio.run`. Inside an already running loop, such as the MCP module's server, the chassis awaits the coroutine in that loop instead. Cancellation is BASE-018.
- Acceptance: An async verb called from the CLI and from inside a running loop both complete and return the same output.
- Relates to: BASE-018, MCP.
- Status: confirmed.

### BASE-010 Events connect modules
- Requirement: A module publishes a topic and every enabled module subscribed to it receives the payload, and one subscriber's failure never hides the others.
- What this means: Modules cooperate through events without importing each other. Each delivery reports completed or failed for each subscriber.
- Why: Modules must compose without knowing each other's code; an event names what happened, not who handles it.
- How it shows: The template's `greet` publishes `template.greeted`, and its subscriber records the name.
- Build: Existing `events.publish(topic, payload, source)`, `Subscription(topic, handler)`. Subscribers write through the data access object per STORE-022.
- Acceptance: Two subscribers, one raising; publish returns one completed and one failed delivery, and the completed one's effect is stored.
- Relates to: STORE-022.
- Status: confirmed.

### BASE-011 A user error states what happened and one next command
Specified in CLI-009: a module stops on a user error by raising `Stop` with the message and exactly one next command, on the CLI and in the MCP result, per MCP-006.

### BASE-012 Each module adds concise instructions for agents
Specified in MCP-007 and MCP-008: each module declares concise instructions that defer to `metaform help`, composed live with the chassis base text. The field and the CLI command that shows the composed text are open there.

### BASE-013 Destructive verbs act only with --confirm
- Requirement: A verb declared with a caution does nothing until called with `--confirm`, and without it prints the caution and the exact confirming command.
- What this means: The caution text says what will be lost. The confirming command is the same command plus `--confirm`.
- Why: The main agent that holds the confirming command acts with confidence; a subagent meeting only the caution hesitates. The wording steers, and nothing gates inference.
- How it shows: `metaform template forget` prints the caution and `Next: If you are sure: metaform template forget --confirm`.
- Build: Existing `Verb.caution`.
- Acceptance: Without `--confirm` the data is unchanged; with it, the data is removed.
- Relates to: CLI-018, CLI.
- Status: confirmed.

---

## Module contract and discovery

### BASE-014 Modules load from the system place, the user place and entry points
- Requirement: Metaform finds modules in the system place shipped with Metaform, the user place `~/.metaform/modules`, and installed packages that declare a `metaform.modules` entry point.
- What this means: A module is a folder with an `__init__.py`, or a package named by an entry point. Its id is its folder or entry point name and must equal `MODULE.id`. Two modules with one id, or a module named like a chassis verb, are not loaded, and `metaform list modules` says why.
- Why: Community extensibility means a module can be dropped into the user place or installed like any Python package. Nothing lives in project folders because all data is global.
- How it shows: `metaform list modules` shows each module with its place and state, and the reason for any that is not loaded.
- Build: Existing `loader.discover()`, `RESERVED`. `RESERVED` gains `import`, `export`, `query`, `build` and loses `mcp`.
- Acceptance: A user-place module and an entry-point module with the same id: the second is reported with the reason and not loaded. A module named `export` is refused with the reason.
- Relates to: BASE-015, CLI.
- Status: confirmed. A per-project module place is open.

### BASE-015 Compatibility is read before any module code runs
- Requirement: The chassis reads a module's compatibility and dependencies without importing it, and skips an incompatible module without affecting the chassis or other modules.
- What this means: `SUPPORTED_OS` is a literal tuple of `linux`, `macos`, `windows`. The chassis parses it from source. A module without it is not loaded.
- Why: Importing incompatible code can fail in ways that take the chassis down. Reading literals first keeps every failure contained and reportable.
- How it shows: A module declaring only `linux` is listed on Windows as not loaded, with the reason.
- Build: Existing `module_metadata.read`, which parses `SUPPORTED_OS` and `DEPENDENCIES` by AST. It adds the literal declarations of BASE-016 and BASE-022.
- Acceptance: A module whose `__init__.py` raises on import but declares an unsupported OS is reported as incompatible and its code never runs.
- Relates to: BASE-016, BASE-022.
- Status: confirmed.

### BASE-016 A verb may narrow its own compatibility
- Requirement: A verb may declare the systems it runs on, narrower than its module, and on other systems it is filtered out like a command outside the folder's command setting, while help says where it runs.
- What this means: The module still loads everywhere it declares. The verb is not shown and does not run on a system outside its list. `metaform help <module> <verb>` on that system states the systems it runs on and gives one next step. A small OS-specific piece may instead be its own module.
- Why: One piece that cannot run on a system should not make a whole module unusable there. Filtering through the existing command check adds no second mechanism.
- How it shows: On Windows, a linux-only verb is missing from `metaform help <module>` and from the MCP tool list, and its help page explains why.
- Build: `Verb.supported_os`, a subset of the module's `SUPPORTED_OS`, default the module's. The dispatcher and the MCP tool list apply the same filter as the command setting.
- Acceptance: Simulating the current OS outside a verb's list hides it from help commands and MCP, running it gives the explanation with one next step, and the module's other verbs still work.
- Relates to: BASE-015, CLI, MCP.
- Status: per-verb compatibility is confirmed as acceptable; the mechanism is recommended.

### BASE-017 Modules are enabled and disabled per module, and template and demos ship disabled
- Requirement: Each module is enabled or disabled by the chassis, a module's declaration states whether it ships disabled, and the template and demo modules ship disabled.
- What this means: A module's state is its declared shipping state until the user enables or disables it. The user's choice is stored and wins. A copy of the template starts disabled, and its author enables it.
- Why: A fresh install runs only real work. Declaring the shipping state in the module means the chassis keeps no list of names.
- How it shows: On a fresh home, `metaform list modules` shows `template` off. `metaform enable module template` turns it on.
- Build: A literal `SHIPS_DISABLED = True` in the module source, read per BASE-015. The base db stores explicit choices in the `module_state` table of STORE-002. The current `disabled_modules` table records only disables, so every module loads on by default, including the template; that changes.
- Acceptance: Fresh home: template off, map on. Enable template, restart: on. Disable map, restart: off.
- Relates to: BASE-014, STORE-002.
- Status: shipping disabled is confirmed; declaring it in the module is recommended.

### BASE-018 Module lifecycle is owned and reversible
- Requirement: Loading a module registers its contributions as one owned unit, and unloading, reloading, shutdown and async cancellation withdraw them completely while durable data stays.
- What this means: A failed load withdraws whatever it registered. Unload removes its verbs, settings from the schema, help, subscriptions and running tasks. Reload does not accumulate duplicates. Shutdown ends the module's running tasks cleanly. Cancelling an async verb stops it and leaves stored data consistent. Stored settings values, layers and history are never removed by unload.
- Why: The quality standard requires explicit lifecycle and no resource leakage or state corruption across load, unload, reload and shutdown. Without owned contributions, disabling a module leaves behind ghost commands and subscribers.
- How it shows: `metaform disable module template` removes its verbs and settings from help at once; enabling it again shows them once.
- Build: The loader records every contribution by owner. Existing: failed import restores the settings schema; `loader.reset()` removes settings by owner. Added: withdrawal of subscriptions and running tasks, optional module `start(ctx)` and `stop(ctx)` hooks, and cancellation delivered to running coroutines on shutdown.
- Acceptance: Load, unload, load: each verb, setting and subscription appears exactly once. A module whose import fails leaves no settings behind. Cancelling a running async verb leaves no partial write.
- Relates to: BASE-009, QUAL.
- Status: confirmed; the hook names are recommended.

---

## Template

### BASE-019 One template module is the start of every module
- Requirement: Metaform ships one template module, in its own folder with a README, tests and a changelog, and every module and every non-chassis feature starts from it.
- What this means: The template demonstrates the current contract once each: verbs with nouns and switches, sync and async, events, settings declared in code including a select from its own data, data through the data access object, instructions for agents, MCP tools, per-verb compatibility and a caution verb. Its changelog records each contract change so forks can follow. It is the module the chassis is developed against. Other modules are added only when a need exists.
- Why: Authors copy the template, so it must show exactly what the chassis offers now. Building many speculative modules is what repeatedly buried the chassis; one template that exercises every feature proves the chassis and teaches authors at once.
- How it shows: `src/metaform/modules/template/` holds `__init__.py`, `README.md`, `CHANGELOG.md` and `tests/`.
- Build: Existing README and module. Added: `CHANGELOG.md`, tests inside the template folder, and the demonstrations of STORE-022, MCP-008, BASE-016 and BASE-017. The template's CI runs on Linux, macOS and Windows.
- Acceptance: Each contract feature listed above is exercised by one template test that fails if the chassis drops the feature. A contract change without a changelog entry fails review.
- Relates to: BASE-017, QUAL.
- Status: confirmed.

---

## Versioning

### BASE-020 Versioning and compatibility
- Requirement: Before 1.0 the module contract changes freely; from 1.0 a module declares the lowest chassis version it needs and checks capabilities, breaks come only in a major release, and a frozen suite enforces this.
- What this means: The chassis publishes its version and a set of named capabilities. A module declares its minimum chassis version as a literal read before import. At runtime it asks whether a capability exists instead of comparing versions. The frozen suite is a set of modules written against earlier releases that must keep working.
- Why: Community modules must keep working across chassis updates, or nobody builds on the chassis. Capability checks let a module use new features where they exist without breaking on an older chassis. Until the first release the design is still settling, so compatibility machinery would only slow it.
- How it shows: A module needing a newer chassis is listed as not loaded with the version it needs.
- Build: From 1.0: `metaform.CHASSIS_VERSION`, `metaform.capabilities` with `has(name)`, a literal `REQUIRES_CHASSIS` in the module source. Before 1.0 none of this is required.
- Acceptance: From 1.0 only: the frozen suite loads and runs on each release.
- Relates to: BASE-015.
- Status: confirmed.

---

## Wheels and packaging

### BASE-021 Packaging uses pyproject.toml and uv, and clients start the MCP server with uvx
- Requirement: Metaform is packaged with `pyproject.toml` and the uv toolchain, and AI clients launch the MCP module with uvx.
- What this means: The registration entry an installer writes is specified in MCP-010. The command and the Python package are `metaform`. The distribution name is separate.
- Why: uvx runs the server in its own environment with its own dependencies, the same way on every system, without a permanent install.
- How it shows: A client configured that way starts the server and lists its tools.
- Build: Existing `pyproject.toml` with hatchling; the `metaform` console script stays. The PyPI distribution name is undecided; `metaform` belongs to an unrelated package.
- Acceptance: `uvx --from <built wheel> metaform mcp` answers an MCP initialize and tools/list on Linux, macOS and Windows.
- Relates to: BASE-003, MCP-010.
- Status: confirmed; the distribution name is open.

### BASE-022 The repo wheel carries every repo module, and the local build carries the enabled ones
- Requirement: The wheel built from the repository contains every repo module, and `metaform build` builds a wheel containing the chassis and only the modules enabled in the user's configuration.
- What this means: A release is complete. A user's own build holds exactly what they use, with each selected module's own resources and declared dependencies, and nothing from excluded modules.
- Why: The release carries everything; a custom build carries only what its user runs, which keeps it small and runnable where it is uploaded.
- How it shows: With only `map` enabled, the built wheel contains the chassis and `map`, and no other module code.
- Build: Module dependencies are declared by the module in a literal `DEPENDENCIES`, read per BASE-015. `metaform build` collects enabled modules from all three places. The chassis selects nothing by module name.
- Acceptance: Build with one module enabled; the wheel's file list contains that module and no other, and its metadata lists only the chassis's and that module's dependencies.
- Relates to: BASE-017, BASE-023.
- Status: confirmed.

### BASE-023 A wheel runs directly, isolated from any installed Metaform
- Requirement: A wheel runs directly with `python <wheel>`, keeps its data in its own subfolder under `~/.metaform`, and never changes an installed Metaform.
- What this means: Running a wheel needs no permanent install. Its prepared runtime is separate from its durable data. It never replaces, downgrades or modifies an installed Metaform, its dependencies or its data.
- Why: A custom build never has to worry about version compatibility with the installed Metaform.
- How it shows: Running a wheel creates its own subfolder under `~/.metaform` and leaves the installed Metaform's files unchanged.
- Build: A `__main__.py` at the wheel root bootstraps from the wheel. The subfolder naming is open.
- Acceptance: With an installed Metaform present, run a different-version wheel directly; the installed package, entry points and base db are byte-identical afterwards.
- Relates to: BASE-024, BASE-025.
- Status: confirmed; the subfolder naming is open.

### BASE-024 A directly run wheel works in hosted code execution environments
- Requirement: A wheel runs in the code execution environments of OpenAI and Claude, offline, carrying everything its selected modules need.
- What this means: The wheel carries its code, modules, dependencies, resources, defaults and help. No Metaform install, source checkout, internet or prepared cache is needed. The hosting agent does the reasoning in its own context and uses Metaform through its CLI.
- Why: A user can build a custom Metaform and upload it where an agent runs code.
- How it shows: Uploading the wheel and running `python metaform.whl` in such an environment shows status and help and completes chassis work.
- Build: Pure-Python dependencies are carried inside the wheel. A wheel carrying compiled content is tagged for its platform and never claims universal compatibility.
- Acceptance: In a clean container with no network and no Metaform, `python <wheel>` runs `metaform`, `help`, `set`, `export` and `import` successfully.
- Relates to: BASE-023, BASE-026.
- Status: confirmed.

### BASE-025 Installing a wheel updates and merges the installed data
- Requirement: Installing a wheel can update the installed data and merge the wheel's data into it.
- What this means: Open. See the open questions.
- Why: A wheel that was run on its own accumulates data the user wants to keep when the wheel becomes the installed Metaform.
- How it shows: Open.
- Build: Open.
- Acceptance: Open.
- Relates to: BASE-023, STORE-027, STORE-030.
- Status: confirmed as intent; behavior open.

### BASE-026 The chassis depends only on the standard library and pure-Python packages
- Requirement: The chassis has no compiled dependencies; modules bring their own.
- What this means: A wheel without compiled modules runs on any system and Python that the chassis supports. The `mcp` SDK and its compiled dependencies belong to the MCP module.
- Why: Compiled dependencies such as pydantic_core tie a wheel to one Python version and platform.
- How it shows: The chassis's own dependency list contains only pure-Python distributions.
- Build: Current chassis dependencies are `mcp` and `prompt_toolkit`; `mcp` moves to the MCP module; `prompt_toolkit` is pure Python.
- Acceptance: Building a wheel with no modules produces a `py3-none-any` wheel whose dependencies resolve without any compiled distribution.
- Relates to: BASE-003, BASE-024.
- Status: recommended.

### BASE-027 Metaform offers to maintain a user's fork, CI and wheel
- Requirement: At release, Metaform offers to maintain a user's personal fork of the template, its CI and the build of their own wheel.
- What this means: A community author starts from the template and Metaform keeps their fork current with the template changelog, runs its CI on three systems and builds their wheel.
- Why: The community builds on the template, and that upkeep is what keeps their forks working as the chassis changes.
- How it shows: Open.
- Build: Open.
- Acceptance: Open.
- Relates to: BASE-019, BASE-022.
- Status: confirmed as intent; behavior open.

---

### BASE-028 Context travels with each operation

- Requirement: Every verb, event delivery and tool call receives its full context explicitly, and no operation reads another operation's context.
- What this means: The chassis builds one context object for each operation and passes it in. It holds the module, the folder, the project, the nouns and switches of this call, and the way to reach the data access object and settings. A module never keeps the current project or folder in a module-level variable. Two operations running at once, such as two MCP tool calls, each have their own context and cannot see each other's changes to it. Nonce and assignment context join the same object when nonces are designed.
- Why: Metaform serves many folders and agents at once through the CLI and MCP. Context held anywhere but the operation leaks from one call into the next, and a write lands in the wrong project with no error at all.
- How it shows: A tool call for one project and a tool call for another, running together, each read and write only their own project.
- Build: `Context` gains `project`, the project the folder resolves to or the one named by the call, and `store`, the data access object bound to that project. Events build a new context for each subscriber from the publisher's folder and project. The server builds a new context for every tool call. Module code receives context only as the argument to its verb or handler.
- Acceptance:
  1. Two concurrent tool calls for two different projects each write one element; each element lands only in its own project's store.
- Relates to: BASE-004, BASE-009, BASE-010, STORE-023, MCP-003, MCP-011.
- Status: confirmed; nonce and assignment context deferred with nonces.

### BASE-029 Every capability shows which module owns it

- Requirement: Users and agents can always tell which module owns a command, setting, tool, event, layer or screen entry.
- What this means: Module verbs are named with their module, `metaform <module> <verb>` and the tool `<module>_<verb>`. Every setting records its owner, and `metaform config --show` and the settings screen group settings by owner. Help pages say which module a command belongs to. Every layer's provenance names the module that created it. The chassis's own commands are listed as chassis. Module commands are not flattened into the chassis's root.
- Why: When something misbehaves, the first question is who owns it. An agent that can see ownership goes to the right help page and the right module instead of searching the source.
- How it shows: `metaform help commands` lists each command under its owner. `metaform config --show` shows an owner column.
- Build: The owner comes from the declaration: the module id for everything a module declares, chassis for the rest. Help, config, the settings screen, the tool list and layer provenance read it from there. No capability is registered without an owner.
- Acceptance:
  1. Every row of `metaform config --show --json` has an owner, and every tool name begins with its module id.
- Relates to: BASE-006, BASE-008, CLI-008, CLI-010, LAYER-010, MCP-003.
- Status: confirmed.

### BASE-030 Work state never depends on the client that started it

- Requirement: Anything an operation needs later is written through the data access object before the operation returns, so no state depends on the lifetime of the process that started it.
- What this means: A CLI call or MCP session can end at any moment. Whatever a later call must continue from is already stored when the call returns: layers, items, provenance, settings. Long-running agent work runs in the host, as subagents the host starts, not inside Metaform, so the chassis itself holds no running jobs. The workflow module, when specified, owns receipts for work it tracks and keeps them as layers through the same store.
- Why: Agents come and go, sessions end and hosts restart. A workflow that only lives in one process is lost the moment that process ends.
- How it shows: Killing the MCP server or the CLI right after a write returns loses nothing that the write reported as done.
- Build: Every write operation commits before it returns success, per STORE-006. The chassis keeps no in-memory job table. Whether any chassis verb runs long enough to return a receipt is open.
- Acceptance:
  1. A write reported as successful is readable by a new process started after the first is killed.
- Relates to: BASE-003, STORE-006, STORE-024.
- Status: confirmed for durability; open for receipts.

### BASE-031 Cancellation is reported truthfully

- Requirement: Success, failure, cancellation requested, cancellation completed and interruption are always told apart.
- What this means: Asking an operation to stop is not the same as it having stopped. An async verb that is asked to cancel reports that the request was received, and reports cancelled only once it has actually stopped and cleaned up. A CLI call stopped by the user reports interruption, not failure. Over MCP, a cancelled tool call reports cancellation, not an error.
- Why: An agent that believes work stopped when it did not will start a second copy, and one that believes work failed when it was cancelled will retry work nobody wants.
- How it shows: Pressing Ctrl+C during an async verb prints that the verb was interrupted, and the exit code differs from a failure's.
- Build: A verb's outcome is one of completed, failed, cancel requested, cancelled, interrupted. The CLI maps them to exit codes: 0 completed, 1 failed, 130 interrupted by the user; cancelled is reported in the message with its own code, recommended 2. The MCP module maps a host's cancellation notice to cancelling the task and reports cancelled when the task has ended.
- Acceptance:
  1. Cancelling an async verb mid-wait yields cancelled, never completed or failed, and its partial writes are either committed whole or absent.
- Relates to: BASE-009, BASE-018, MCP-006.
- Status: confirmed for the distinction; recommended for the exit codes.

### BASE-032 Every event delivery reaches a terminal outcome

- Requirement: Every event delivery ends as completed, failed or cancelled, reported back through the same publish call.
- What this means: When a module publishes an event, each enabled subscriber's outcome comes back to the publisher. One subscriber failing never hides the others. An async subscriber that is cancelled reports cancelled. No delivery is left without an outcome.
- Why: Modules cooperate through events. A publisher that cannot tell whether its event was handled cannot act correctly on the result.
- How it shows: The template's greet verb publishes an event and receives each subscriber's outcome.
- Build: `events.publish` returns one entry per subscriber with its module and status: completed with its result, failed with its error, or cancelled. This is the current behavior for completed and failed; cancelled is added for async subscribers.
- Acceptance:
  1. With one subscriber that raises and one that succeeds, publish returns one failed and one completed entry.
- Relates to: BASE-010, BASE-031, BASE-033.
- Status: confirmed.

### BASE-033 Events announce and deliver; they do not run workflows

- Requirement: The event bus announces and delivers cooperative activity and holds no workflow logic.
- What this means: Events carry a topic and a payload to subscribers and return outcomes. They do not order steps, wait for conditions, retry, branch or track progress. Authored workflow progression belongs to the workflow module.
- Why: The chassis does not run workflows. A bus that grew sequencing would become a second, hidden workflow engine, and authored workflows would then run under rules nobody wrote.
- How it shows: The chassis's event module has publish and subscribe, and nothing else.
- Build: `events` offers publish and subscription by declaration. No retry, delay, ordering guarantee between subscribers beyond declaration order, or persistent queue is added to it.
- Acceptance: none; this is a boundary on scope, checked in review against QUAL-008.
- Relates to: BASE-003, BASE-010, BASE-032.
- Status: confirmed.

### BASE-034 Every shipped module has a developer README

- Requirement: Every module shipped in the repo has a README that lets a developer understand and change it without reading the chassis source.
- What this means: The README covers the module's purpose; which template version it started from; its declaration; the parts of the common base it uses; its verbs, what each returns and its CLI and tool forms; its settings and defaults; the events it publishes and subscribes to; which verbs are sync or async; the layers it writes, their properties and provenance; its lifecycle and cleanup; the modules it relies on; the systems it supports; the resources it owns; how it behaves installed and in a directly run wheel; and a runnable demonstration.
- Why: Authors learn modules by reading one. A README that answers these questions lets a community author build on a module without guessing at its contract.
- How it shows: Every folder under the shipped modules has a README with these headings.
- Build: The template's README has one heading per item above and is the pattern every module copies. Work and nonce context is added when nonces are designed.
- Acceptance:
  1. A check lists every shipped module folder without a README, or whose README lacks one of the headings; the list is empty.
- Relates to: BASE-019, QUAL-013.
- Status: confirmed; the nonce heading deferred.

## Open questions

1. A per-project module place: is it wanted, and if so where, given all data is global?
2. A directly run wheel's data subfolder: one per build, or one per wheel name reused across its versions?
3. Installing a wheel: does the installed Metaform take on the wheel's data, does the wheel's code convert the installed data to its format, or both, and what happens on conflicting records?
4. The PyPI distribution name.
5. Whether `metaform install` and `metaform uninstall` are chassis verbs or belong to a module, given MCP registration is part of installing.
6. How Metaform maintains a user's fork, CI and wheel at release: which service, which commands.
7. Whether a module can call another module's public operation directly, beyond events, and through what interface.
8. Does any chassis verb run long enough to return a receipt, or do receipts belong only to the workflow module? Recommended: only the workflow module. (BASE-030)
