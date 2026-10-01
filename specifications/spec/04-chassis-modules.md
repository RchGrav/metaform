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
- Build: The chassis package contains no import of any module package. Chassis verbs live in `cli.py` and never branch on a module id; module state reaches chassis output only through the generic status hook of BASE-035, which the chassis calls for every enabled module alike. `loader.discover()` returning an empty list is a normal state, not an error.
- Acceptance: Run the chassis verbs above in a home with all modules disabled; each succeeds. Run them with `src/metaform/modules/` removed from a built wheel; each succeeds. Import `metaform` with every module package unimportable; import succeeds.
- Relates to: BASE-002, BASE-003, STORE, CLI.
- Status: confirmed.

### BASE-002 The chassis owns the data, the settings and the CLI
- Requirement: The chassis is the only owner of Metaform data, settings and the command line, and it provides import, export, query and wheel building for them.
- What this means: All persistent Metaform state is written and read by chassis code. Settings are declared by modules but stored, validated and presented by the chassis. Every command, including module commands, is parsed, dispatched and documented by the chassis. Import, export and query operate on the whole of the data, so they are chassis verbs, not module verbs.
- Why: One owner means one format, one set of rules and one place to fix a fault. Data that a module keeps privately cannot be exported, imported or queried whole, and a command surface parsed in several places drifts apart.
- How it shows: `metaform export all file=backup.json` writes every project's data, including what modules stored, and `metaform export` writes the folder's project. `metaform import backup.json` restores it. `metaform query` reads it. `metaform build` produces a wheel. No module needs its own storage code.
- Build: New chassis verbs `import`, `export`, `query` and `build`, added to `cli.VERBS` and to `loader.RESERVED`. The grammar and document of export and import are STORE-027, query is STORE-028, and build is BASE-042. The chassis dependencies stay limited per BASE-026.
- Acceptance: A module writes layer data through the data access object; `export` then `import` into an empty home reproduces it, read back through the same object. A module that writes a file into the home outside the data access object is reported by a test over the home folder after the template's verbs run.
- Relates to: BASE-004, STORE-022, STORE-027, CLI.
- Status: confirmed.

### BASE-003 The chassis does not run workflows, and MCP is a module
- Requirement: Workflows and the MCP server are modules built on the common base; the chassis contains neither.
- What this means: The chassis never starts a model, a subagent or a workflow. A workflow is module work. The MCP server is the `mcp` module: it serves the tools and instructions that come from module declarations through the same base every other module uses.
- Why: Workflows are agent work that modules provide. Keeping MCP a module puts it on the same footing as every other module and keeps its compiled dependencies out of the chassis, so a wheel without MCP runs anywhere.
- How it shows: `metaform disable mcp` leaves every chassis verb working. A wheel built without the `mcp` module carries no `mcp` package dependency.
- Build: The chassis contains no workflow runner and no model launcher. Moving the MCP server into the `mcp` module, its verb, its dependency and its disabled behavior are specified in MCP-001.
- Acceptance: With `mcp` disabled, every chassis verb works. The rest is MCP-001's acceptance.
- Relates to: MCP-001, MCP-007, CLI.
- Status: confirmed.

---

## Common base

### BASE-004 One common base that every module builds on
- Requirement: Modules reach every Metaform resource through one public base, and a module may use everything that base offers.
- What this means: The public base is a small set of stable imports: `metaform.module` for the declaration types and the verb context, `metaform.settings` for declaring settings, `metaform.data` for the data access object, `metaform.events` for publishing and subscribing, and `metaform.nonce` for handing work to an agent by nonce, BASE-050. A module may use all of it. There is no prohibition on what a module does beyond that. If modules need a Metaform resource that the base lacks, the resource is added to the chassis base, not built inside a module.
- Why: One implementation of each resource means every module behaves the same way and no module rebuilds what another has. Shared resources in the chassis are what let modules compose.
- How it shows: The hello and template modules import only from these public names. A resource that two modules need appears in the base, and both use it.
- Build: Public names are `metaform.module` (Module, Verb, Subscription, Stop, Context, call), `metaform.settings`, `metaform.data`, `metaform.events`, `metaform.nonce` (request, read, update, close, current). Everything else in the package is private. Importing a public name creates no database, process or project state; services resolve the active context when called.
- Acceptance: A test lists the imports of hello and template and fails if any is outside the public names. Importing each public name into a fresh interpreter with a missing home creates no files.
- Relates to: BASE-006, BASE-009, BASE-010, STORE-023, CLI-010.
- Status: confirmed.

### BASE-005 The data access object is the only way modules keep data
Specified in STORE-022 and STORE-023: everything a module keeps is a layer written through the data access object, and a verb reaches it as `ctx.store`.

### BASE-006 Modules declare verbs with nouns and switches
- Requirement: A module declares each verb once, with the nouns it acts on and the switches that change how it runs, and that one declaration drives the CLI, help and MCP.
- What this means: Commands are verbs, arguments are the nouns a verb acts on, and switches are adverbs that change how it runs. A verb runs as `metaform <module> <verb> <nouns> [switches]`. Its summary, details, usage and examples come from the declaration. MCP exposes the same verb as the tool `<module>_<verb>`.
- Why: A consistent grammar makes every command predictable. One declaration means the CLI, help and MCP can never disagree.
- How it shows: `metaform help <module> <verb>` shows the page, `metaform <module> <verb> --help` shows the syntax, and the MCP tool list carries the same verb.
- Build: The full declaration is BASE-035. The current `Verb` has `nouns` as one free string and `adverbs: tuple[Adverb, ...]`, declared separately from settings. Both change: nouns become `Noun` records, and switches become setting keys per CLI-012.
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
- How it shows: The hello module's `wait` verb is async and behaves like any other verb on the CLI and over MCP.
- Build: `module.call(function, *args)` calls the function; when the result is awaitable and no event loop is running in the current thread, it runs it with `asyncio.run`. The MCP module does not use `call` for coroutine verbs: it awaits a coroutine verb in the server's own loop, so the host's cancellation reaches it, and it runs a plain function in a worker thread, MCP-002. Nothing ever calls `asyncio.run` inside a running loop: when a loop is running in the current thread, `call` refuses an awaitable with a `RuntimeError` saying to await it, so no caller blocks the loop without knowing. The settings screen runs discovery, enable and disable in a worker thread, so a module's async `start` and `stop` run there on a loop of their own. Cancellation is BASE-018 and BASE-031.
- Acceptance: An async verb called from the CLI and through the MCP module both complete and return the same result.
- Relates to: BASE-018, MCP.
- Status: confirmed.

### BASE-010 Events connect modules
- Requirement: A module publishes a topic and every enabled module subscribed to it receives the payload, and one subscriber's failure never hides the others.
- What this means: Modules cooperate through events without importing each other. Each delivery reports completed or failed for each subscriber.
- Why: Modules must compose without knowing each other's code; an event names what happened, not who handles it.
- How it shows: The hello module's `greet` publishes `hello.greeted`, and its subscriber records the name.
- Build: `ctx.publish(topic, payload)` calls `events.publish(topic, payload, ctx)`. For each loaded module in discovery order, BASE-037, and each of its subscriptions whose topic equals the topic exactly, the chassis builds a new `Context` for the subscriber's module with the publisher's folder and project, BASE-028, and calls `handler(copy of payload, context)` through `call`. It returns a list with one entry per delivery: `{"module": id, "status": "completed", "result": value}` or `{"module": id, "status": "failed", "error": message}`, and `cancelled` per BASE-032. A subscriber's exception is caught and reported, never raised to the publisher. Subscribers write through the data access object per STORE-022. From an async verb a module publishes with `await ctx.publish_async(topic, payload)`, which awaits an async subscriber in the running loop and runs a plain one in a worker thread, with the same deliveries, BASE-009; `ctx.publish` called while a loop is running raises a `RuntimeError` naming `publish_async`.
  - The chassis itself fires `map.changed` after any command that changed a project's map, VIEW-018, and the web GUI's server fires it the same way after each of the page's writes that changed the map: a topic every module can subscribe to, with no module announcing its own writes. A subscriber's `Context.surface` is `cli`, `mcp` or `web`, where the change was made.
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
- How it shows: `metaform hello forget` prints the caution and `Next: If you are sure: metaform hello forget --confirm`.
- Build: `Verb.caution`, BASE-035, checked by the dispatcher as in CLI-018 and by the MCP module as in MCP-006.
- Acceptance: Without `--confirm` the data is unchanged; with it, the data is removed.
- Relates to: CLI-018, CLI.
- Status: confirmed.

---

## Module contract and discovery

### BASE-014 Modules load from the system place, the user place, entry points and the project place
- Requirement: Metaform finds modules in the system place shipped with Metaform, the user place `~/.metaform/modules`, installed packages that declare a `metaform.modules` entry point, and the project place, whose modules load only for the active selected project.
- What this means: A module is a folder with an `__init__.py`, or a package named by an entry point. Its id is its folder or entry point name and must equal `MODULE.id`. The system place holds the modules bundled in and installed from a wheel. The user place holds modules any project can use. The project place holds modules that load only for the active selected project, PROJ-003. The places are ranked, system, then user, then project: a module whose id a module of an earlier place already holds does not enable, so an installed module always wins, and the chassis can disable any module, BASE-017. A directly run wheel is not a higher place but a separate authority of its own, BASE-023. Two modules with one id, or a module named like a chassis verb, are not loaded, and `metaform list modules` says why.
- Why: Community extensibility means a module can be dropped into the user place or installed like any Python package. A module made for one project's own work loads only where that project is selected, so it never adds its commands and tools to every other project. Ranking the places means a module installed with Metaform, or by the user for every project, is never displaced by a same-name copy of a later place. Metaform writes nothing into a project folder, because all data is global; where the project place's modules live is open, D93.
- How it shows: `metaform list modules` shows each module with its place and state, and the reason for any that is not loaded.
- Build: Discovery and loading in full are BASE-037. `RESERVED` is every chassis verb plus `chassis`: `help`, `add`, `list`, `set`, `unset`, `config`, `enable`, `disable`, `activate`, `import`, `export`, `query`, `build`, `install`, `uninstall`, `feedback`, `read`, `extract`, `prompts`, `prompt`, `clear`, `chassis`. It loses `mcp`, which is a module. The project place is found after the entry points and is not built until D93 settles where it lives.
- Acceptance: A user-place module and an entry-point module with the same id: the second is reported with the reason and not loaded. A module named `export` is refused with the reason.
- Relates to: BASE-015, BASE-017, BASE-023, BASE-037, PROJ-003, STORE-001, CLI.
- Status: confirmed for the system and user places, 2026-09-19, and for entry points. The project place, the ranking of the places, a same-name module of a later place never enabling, and the wheel as a separate authority are confirmed as design, 2026-09-19. Where the project place lives is open, D93, and it is not built until then.

### BASE-015 Compatibility is read before any module code runs
- Requirement: The chassis reads a module's compatibility and dependencies without importing it, and skips an incompatible module without affecting the chassis or other modules.
- What this means: `SUPPORTED_OS` is a literal tuple of `linux`, `macos`, `windows`. The chassis parses it from source. A module without it is not loaded.
- Why: Importing incompatible code can fail in ways that take the chassis down. Reading literals first keeps every failure contained and reportable.
- How it shows: A module declaring only `linux` is listed on Windows as not loaded, with the reason.
- Build: The module's `__init__.py`, or the entry point package's `__init__.py`, is parsed with `ast` and never executed. Each declaration is one top-level assignment of a literal: `SUPPORTED_OS` and `DEPENDENCIES` a tuple or list of strings, `SHIPS_DISABLED` a boolean, and from 1.0 `REQUIRES_CHASSIS` a string. A name assigned more than once, assigned a non-literal, or defined any other way is an error naming the declaration. A `manifest.py` beside `__init__.py` may hold the same declarations; when both hold one, they must be equal. `SUPPORTED_OS` values are `linux`, `macos` and `windows`, compared with `platform.system()` lowercased, with `darwin` read as `macos`. A missing `SUPPORTED_OS` makes the module incompatible with the reason `SUPPORTED_OS is required`. Each `DEPENDENCIES` requirement is checked against the installed distributions, by name and version, still without importing the module; a module whose requirement is not installed is not imported, and its reason names the requirement, so `list modules` says what to install instead of showing an import error.
- Acceptance: A module whose `__init__.py` raises on import but declares an unsupported OS is reported as incompatible and its code never runs.
- Relates to: BASE-016, BASE-022.
- Status: confirmed.

### BASE-016 A verb may narrow its own compatibility
- Requirement: A verb may declare the systems it runs on, narrower than its module, and on other systems it is filtered out like a command outside the folder's command setting, while help says where it runs.
- What this means: The module still loads everywhere it declares. The verb is not shown and does not run on a system outside its list. `metaform help <module> <verb>` on that system states the systems it runs on and gives one next step. A small OS-specific piece may instead be its own module.
- Why: One piece that cannot run on a system should not make a whole module unusable there. Filtering through the existing command check adds no second mechanism.
- How it shows: On Windows, a linux-only verb is missing from `metaform help <module>` and from the MCP tool list, and its help page explains why.
- Build: `Verb.supported_os`, a subset of the module's `SUPPORTED_OS`, default the module's. The dispatcher and the MCP tool list apply the same filter as the command setting. `metaform help <module>` lists such a verb after the others under the heading `Not on this system`, with the systems it runs on. `metaform help <module> <verb>` and running the verb both print `<module> <verb> runs on <systems>.` with the next step `metaform help <module>`.
- Acceptance: Simulating the current OS outside a verb's list hides it from help commands and MCP, running it gives the explanation with one next step, and the module's other verbs still work.
- Relates to: BASE-015, CLI, MCP.
- Status: per-verb compatibility is confirmed as acceptable; the mechanism is recommended.

### BASE-017 Modules are enabled and disabled by name, and hello and template ship disabled
- Requirement: Modules are the only thing Metaform enables or disables, by name, and a module's declaration states whether it ships disabled; hello and template ship disabled.
- What this means: `metaform enable <module>` and `metaform disable <module>` take the module's name directly, because nothing else in the design is enabled or disabled. A module's state is its declared shipping state until the user enables or disables it. The user's choice is stored and wins. A copy of the template starts disabled, and its author enables it.
- Why: Every module adds commands, so many modules clutter help and the menus; enabling and disabling keeps the surface to the modules in use. A fresh install runs only real work, so the two example modules ship disabled. Declaring the shipping state in the module means the chassis keeps no list of names.
- How it shows: On a fresh home, `metaform list modules` shows `hello` and `template` off. `metaform enable hello` turns it on.
- Build: A literal `SHIPS_DISABLED = True` in the module source, read per BASE-015. The base db stores explicit choices in the `module_state` table of STORE-002. The current `disabled_modules` table records only disables, so every module loads on by default, including the current demo; that changes.
- Acceptance: Fresh home: hello off, template off, map on. Enable hello, restart: on. Disable map, restart: off.
- Relates to: BASE-014, BASE-019, STORE-002.
- Status: confirmed; declaring the shipping state in the module is recommended.

### BASE-018 Module lifecycle is owned and reversible
- Requirement: Loading a module registers its contributions as one owned unit, and unloading, reloading, shutdown and async cancellation withdraw them completely while durable data stays.
- What this means: A failed load withdraws whatever it registered. Unload removes its verbs, settings from the schema, help, subscriptions and running tasks. Reload does not accumulate duplicates. Shutdown ends the module's running tasks cleanly. Cancelling an async verb stops it and leaves stored data consistent. Stored settings values, layers and history are never removed by unload.
- Why: The quality standard requires explicit lifecycle and no resource leakage or state corruption across load, unload, reload and shutdown. Without owned contributions, disabling a module leaves behind ghost commands and subscribers.
- How it shows: `metaform disable hello` removes its verbs and settings from help at once; enabling it again shows them once.
- Build: The loader records every contribution by owner. Existing: failed import restores the settings schema; `loader.reset()` removes settings by owner. Added:
  - `Module(start=None, stop=None)`. Each is a function or coroutine taking one argument, the module's `Context` with no nouns. `start` runs once per process, after the module's verbs, settings and subscriptions are registered and before its first verb, subscriber or tool call runs. `stop` runs once, at process exit or unload, after its running tasks are cancelled. A `start` that raises unloads the module and reports the error as its load problem. A `stop` that raises is reported as the module's problem in `list modules`, and its withdrawal completes all the same: settings, verbs and code are removed whatever `stop` did.
  - `ctx.spawn(coroutine)` starts a task owned by the context's module and returns it. The chassis keeps each module's tasks. Unload, reload and shutdown cancel them, wait for them to finish, then call `stop`.
  - Withdrawal of subscriptions and tasks on unload.
- Acceptance: Load, unload, load: each verb, setting and subscription appears exactly once. A module whose import fails leaves no settings behind. Cancelling a running async verb leaves no partial write.
- Relates to: BASE-009, QUAL.
- Status: confirmed; the hook names are recommended.

---

## Template

### BASE-019 Two example modules: hello shows the features, template is the empty start of every module
- Requirement: Metaform ships exactly two example modules: `hello`, a demo that shows each chassis feature working, and `template`, the same module completely empty but scaffolded; every module and every non-chassis feature starts from `template`, which is kept current with its changelog.
- What this means: `hello` is hello-world style code that exercises the current contract once each: verbs with nouns and switches, sync and async, events, settings declared in code including a select from its own data, data kept as a layer through the data access object, instructions for agents, the status hook, MCP tools, per-verb compatibility and a caution verb with `--confirm`. `template` has every file and declaration `hello` has, in the same places, with nothing in them, ready to copy. Its changelog records each contract change so forks can follow. The chassis is developed against both. Other modules are added only when a need exists.
- Why: Authors need two things: to see each feature work, and a clean start that carries nothing to delete. One demo and one empty scaffold of the same shape give both. Building many speculative modules is what repeatedly buried the chassis.
- How it shows: `src/metaform/modules/hello/` and `src/metaform/modules/template/` each hold `__init__.py`, `README.md`, `CHANGELOG.md` and `tests/`. Copying `template` and enabling the copy gives a module that loads with no verbs.
- Build: The current `template` module becomes `hello`, with its verbs greet, wait, history and forget, its settings and its event. A new `template` holds the same files and the same declaration fields, empty. Added to both: `CHANGELOG.md`, tests inside the module folder, which pytest collects because the chassis's `testpaths` lists both `tests` and `src/metaform/modules`, QUAL-006, and the demonstrations of STORE-022, MCP-008, BASE-016 and BASE-017 in `hello`. Both modules' CI runs on Linux, macOS and Windows.
- Acceptance: Each contract feature listed above is exercised by one `hello` test that fails if the chassis drops the feature. `template` loads and declares every field `hello` declares, with none filled. A contract change without a changelog entry fails review.
- Relates to: BASE-017, QUAL-001.
- Status: confirmed; the name `template` for the empty module is recommended.

### BASE-020 Versioning and compatibility
- Requirement: Before 1.0 the module contract changes freely; from 1.0 a module declares the lowest chassis version it needs and checks capabilities, breaks come only in a major release, and a frozen suite enforces this.
- What this means: The chassis publishes its version and a set of named capabilities. A module declares its minimum chassis version as a literal read before import. At runtime it asks whether a capability exists instead of comparing versions. The frozen suite is a set of modules written against earlier releases that must keep working. Compatibility runs one way: at the official release, a chassis runs the modules written for an earlier chassis of the same major version; an older chassis running a module written for a newer one is not promised. During development the version is CalVer, never SemVer; its format is open, D94. 1.0 in this spec names the first official release.
- Why: Community modules must keep working across chassis updates, or nobody builds on the chassis. Capability checks let a module use new features where they exist without breaking on an older chassis. Until the first release the design is still settling, so compatibility machinery would only slow it, and a SemVer number would promise a compatibility the contract does not yet keep; a CalVer version says only when a build was made. A module states the lowest chassis it needs, so the promise can only run toward newer chassis: an older chassis cannot know features that did not exist when it shipped.
- How it shows: A module needing a newer chassis is listed as not loaded with the version it needs.
- Build: From 1.0: `metaform.CHASSIS_VERSION`, `metaform.capabilities` with `has(name)`, a literal `REQUIRES_CHASSIS` in the module source. Before 1.0 none of this is required. During development the version is `YYYY.M.D.N`, written with no leading zeros as packaging writes a version: the date of the update and its place among the updates of that day, counted from 1. `python -m scripts.calver` stamps it into `pyproject.toml` and `src/metaform/__init__.py` before a commit, counting the commits already made that day. It says when a build was made and which of that day it is, and asks for no decision when it is set.
- Acceptance: From 1.0 only: the frozen suite loads and runs on each release.
- Relates to: BASE-015, BASE-047.
- Status: confirmed. CalVer during development, 2026-09-19. Its format, Rich 2026-09-28 at `code.builder.package`: the date and the count of updates made that day, `YYYY.M.D.N`, where N counts the commits of that day, from 1. Compatibility within a major version at the official release, running one way toward newer chassis, 2026-09-19.

---

## Wheels and packaging

### BASE-021 Packaging uses pyproject.toml and uv, and clients start the MCP server with uvx
- Requirement: Metaform is packaged with `pyproject.toml` and the uv toolchain, and AI clients launch the MCP module with uvx.
- What this means: The registration entry an installer writes is specified in MCP-010. The command and the Python package are `metaform`. The distribution name is separate.
- Why: uvx runs the server in its own environment with its own dependencies, the same way on every system, without a permanent install.
- How it shows: A client configured that way starts the server and lists its tools.
- Build: `pyproject.toml` with the hatchling build backend, the console script `metaform = "metaform.cli:main"`, and `python -m metaform` running the same entry. The PyPI distribution name is undecided; `metaform` belongs to an unrelated package.
- Acceptance: `uvx --from <built wheel> metaform mcp serve` answers an MCP initialize and tools/list on Linux, macOS and Windows.
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
- Build: A `__main__.py` at the wheel root bootstraps from the wheel, BASE-042. The wheel's data folder is `~/.metaform/wheels/<name>-<version>`, one per wheel name and version, so two builds never share data by accident. It is never the main data folder.
- Acceptance: With an installed Metaform present, run a different-version wheel directly; the installed package, entry points and base db are byte-identical afterwards.
- Relates to: BASE-024, BASE-025.
- Status: confirmed. The folder naming by wheel name and version is the technical answer.

### BASE-024 A directly run wheel works in hosted code execution environments
- Requirement: A wheel runs in the code execution environments of OpenAI and Claude, offline, carrying everything its selected modules need.
- What this means: The wheel carries its code, modules, dependencies, resources, defaults and help. No Metaform install, source checkout, internet or prepared cache is needed. The hosting agent does the reasoning in its own context and uses Metaform through its CLI.
- Why: A user can build a custom Metaform and upload it where an agent runs code.
- How it shows: Uploading the wheel and running `python metaform.whl` in such an environment shows status and help and completes chassis work.
- Build: Pure-Python dependencies are carried inside the wheel. A wheel carrying compiled content is tagged for its platform and never claims universal compatibility.
- Acceptance: In a clean container with no network and no Metaform, `python <wheel>` runs `metaform`, `help`, `set`, `export` and `import` successfully.
- Relates to: BASE-023, BASE-026.
- Status: confirmed.

### BASE-025 Data from a directly run wheel can be pulled into the main data folder
- Requirement: When a wheel that was run directly is later installed, its data can be moved into the main data folder and used there, arriving as its own metaforms, never merged into existing ones.
- What this means: A wheel run directly keeps its data in its own subfolder of `~/.metaform`, BASE-023, not in the main data folder. If the user later installs that wheel, for example because it is a newer version they have reason to install, the installed Metaform can pull the wheel's data into the main folder so the work done while running it directly is still usable. Separate data cannot really be merged, so nothing is merged into an existing metaform: each metaform from the wheel's folder arrives in the main folder as its own metaform, MAP-045. A project that already exists in the main folder gains the incoming metaform as another metaform, not active; a project that does not exist is registered with it.
- Why: Work done while using a wheel directly is not lost when the user moves to an installed Metaform.
- How it shows: After installing a wheel that was run directly, `metaform import wheel=<name>-<version>` lists and pulls in that wheel's data; `list metaforms` in each affected project shows the pulled-in metaform next to the ones already there, and nothing already there changed.
- Build:
  - The noun `wheel=<name>-<version>` on the chassis `import` verb names a folder under `~/.metaform/wheels/`. Import reads that folder's projects, metaforms and layers the same way it reads an export document, STORE-027.
  - Each incoming metaform is added under a new metaform id. Its name is its original name followed by `-from-<name>-<version>`; if that name is taken, a numeric suffix is added. It is never made active by the pull; the user selects it with `activate metaform`.
  - Identity ids that already exist are not added again, STORE-027, so pulling the same folder twice adds nothing the second time.
  - The wheel's folder is left in place. Removing it is a separate, explicit act by the user.
  - The wheel's folder is read as a home of its own: its export document, STORE-027, is imported with each metaform's id replaced by one made from the wheel's name and version and the metaform's own id, so a second pull finds each one and adds nothing. A project the pull registers gets the metaform too, not active, so it has no active metaform until the user activates one or writes, STORE-041. A folder that holds no wheel data stops with the first wheel folder there as the next step.
- Acceptance:
  1. A project with an active metaform in the main folder, and a wheel folder holding a metaform for the same project: after the pull, the project has both metaforms, the original is still active, and every read of the original returns what it returned before.
  2. Pulling the same wheel folder a second time adds no metaform and no rows.
- Relates to: BASE-023, BASE-042, MAP-045, STORE-027, STORE-041.
- Status: confirmed for moving the data into the main folder as its own metaform, never merged. The noun, naming and flow are recommended.

### BASE-026 The chassis depends only on the standard library and pure-Python packages
- Requirement: The chassis has no compiled dependencies; modules bring their own.
- What this means: A wheel without compiled modules runs on any system and Python that the chassis supports. The `mcp` SDK and its compiled dependencies belong to the MCP module.
- Why: Compiled dependencies such as pydantic_core tie a wheel to one Python version and platform.
- How it shows: The chassis's own dependency list contains only pure-Python distributions.
- Build: The chassis's dependency list is `[project].dependencies` in `pyproject.toml`, carried into built wheels per BASE-041. Current chassis dependencies are `mcp` and `prompt_toolkit`; `mcp` moves to the `mcp` module's `DEPENDENCIES`; `prompt_toolkit` is pure Python and stays.
- Acceptance: Building a wheel with no modules produces a `py3-none-any` wheel whose dependencies resolve without any compiled distribution.
- Relates to: BASE-003, BASE-024.
- Status: recommended.

### BASE-027 Metaform offers to maintain a user's fork, CI and wheel
- Requirement: At release, Metaform offers to maintain a user's personal fork of the template, its CI and the build of their own wheel.
- What this means: A community author starts from the template and Metaform keeps their fork current with the template changelog, runs its CI on three systems and builds their wheel. Metaform can administer its own fork the same way. CI builds a wheel with the full set of modules that has passed muster: an agent ensures that each module meets or exceeds the standard of QUAL-001 before it goes in. A fork's CI-built wheels run directly in hosted code environments, BASE-024, or update the installed copy, BASE-047.
- Why: The community builds on the template, and that upkeep is what keeps their forks working as the chassis changes. A wheel carries every module it holds to every user of it, so a module that falls short of the standard reaches them all.
- How it shows: Open.
- Build: Open.
- Acceptance: Open.
- Relates to: BASE-019, BASE-022, BASE-024, BASE-047, QUAL-001, QUAL-003.
- Status: confirmed as intent; the full module set that has passed muster, checked by an agent against the standard, and CI-built wheels for forks, 2026-09-19. Behavior open.

---

### BASE-028 Context travels with each operation

- Requirement: Every verb, event delivery and tool call receives its full context explicitly, and no operation reads another operation's context.
- What this means: The chassis builds one context object for each operation and passes it in. It holds the module, the folder, the project, the nouns and switches of this call, and the way to reach the data access object and settings. A module never keeps the current project or folder in a module-level variable. Two operations running at once, such as two MCP tool calls, each have their own context and cannot see each other's changes to it.
- Why: Metaform serves many folders and agents at once through the CLI and MCP. Context held anywhere but the operation leaks from one call into the next, and a write lands in the wrong project with no error at all.
- How it shows: A tool call for one project and a tool call for another, running together, each read and write only their own project.
- Build: `Context` gains `project`, the project the folder resolves to or the one named by the call, and `store`, the data access object bound to that project. Events build a new context for each subscriber from the publisher's folder and project. The server builds a new context for every tool call; a call names its project with the optional `project` argument every tool takes, MCP-025, as `--project <id>` does on the CLI, CLI-021, and otherwise uses the folder's project. Module code receives context only as the argument to its verb or handler.
- Acceptance:
  1. Two concurrent tool calls for two different projects each write one element; each element lands only in its own project's store.
- Relates to: BASE-004, BASE-009, BASE-010, STORE-023, MCP-003, MCP-011, MCP-025, CLI-021.
- Status: confirmed. The per-call project argument is recommended, MCP-025, see D37.

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
- Build: A verb's outcome is one of completed, failed, cancel requested, cancelled, interrupted. The CLI exit codes: 0 completed; 1 failed with an unexpected error; 2 a user error, a `Stop` with its Next line, CLI-009; 3 cancelled; 130 interrupted by the user. On the CLI, the first Ctrl+C during an async verb requests cancellation and prints `Cancelling <module> <verb>...` to standard error; the verb then reports cancelled when it has stopped. A second Ctrl+C interrupts at once with exit 130. Over MCP, the host's `notifications/cancelled` for a running tool call cancels its task; per the protocol no result is sent for a cancelled request, and the task's stored writes follow BASE-030.
- Acceptance:
  1. Cancelling an async verb mid-wait yields cancelled, never completed or failed, and its partial writes are either committed whole or absent.
- Relates to: BASE-009, BASE-018, MCP-006.
- Status: confirmed for the distinction; recommended for the exit codes and the display. Exit 2 for user errors follows CLI-009, confirmed.

### BASE-032 Every event delivery reaches a terminal outcome

- Requirement: Every event delivery ends as completed, failed or cancelled, reported back through the same publish call.
- What this means: When a module publishes an event, each enabled subscriber's outcome comes back to the publisher. One subscriber failing never hides the others. An async subscriber that is cancelled reports cancelled. No delivery is left without an outcome.
- Why: Modules cooperate through events. A publisher that cannot tell whether its event was handled cannot act correctly on the result.
- How it shows: The hello module's greet verb publishes an event and receives each subscriber's outcome.
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
- Build: The template's README has one heading per item above and is the pattern every module copies.
- Acceptance:
  1. A check lists every shipped module folder without a README, or whose README lacks one of the headings; the list is empty.
- Relates to: BASE-019, QUAL-013.
- Status: confirmed.


## Records added by the cold build check

### BASE-035 The module and verb declarations in full
- Requirement: A module is declared with fixed records, `Module`, `Verb`, `Noun` and `Subscription`, and a verb receives a fixed `Context`, all from `metaform.module`.
- What this means: These records are the whole contract between a module and the chassis. Everything the CLI, help, MCP and the settings screen show about a module comes from them.
- Why: A builder with only this spec must be able to write the chassis and a module against the same contract without reading earlier code.
- How it shows: The hello module's declaration uses every field below.
- Build:
  - `Stop(message: str, next_step: str)`: an exception for a user error. `next_step` is required and is one command, CLI-009. The CLI prints `Error: <message>` and `Next: <next_step>` to standard error and exits 2; MCP returns the same two lines with `is_error` true.
  - `Noun(name: str, help: str, kind: str = 'str', required: bool = True, many: bool = False, schema: dict | None = None)`. `kind` is `str`, `int`, `bool` or `json`. Only the last noun of a verb may have `many`.
    - On the CLI: a `str` noun is the word; an `int` noun is decimal digits with an optional leading minus; a `bool` noun is `true` or `false`, and nothing else; a `json` noun is JSON text, parsed with the standard `json` module. A value that does not parse for its kind is an error naming the noun and its kind.
    - Over MCP, each noun is one input schema property: `str` is `{"type": "string"}`, `int` is `{"type": "integer"}`, `bool` is `{"type": "boolean"}`, and `json` is the noun's `schema` when given, else `{}`, which accepts any JSON value. A `many` noun is `{"type": "array", "items": <the kind's schema>}`. A JSON value sent for a `str` noun that is not a string is not refused, BASE-044: the chassis grammar hands the verb that value's JSON text, `json.dumps(value, ensure_ascii=False)`, and adds a notice to the call's result, `<noun> is text; what was sent was kept as its JSON text.`, each member of a many `str` noun the same way. This is the grammar's job, not each verb's: the grammar owns the reading of a call on both surfaces, it already carries a notice for a name it does not know, BASE-043, and a verb declared with a `str` noun then always receives text, whoever wrote the module. An `int` or `bool` noun sent a value that is not its kind cannot be read as that kind, so it stops the call as the command line does, with the same next step, MCP-005. A switch is read by its setting kind under the same rule, CLI-027. Usage renders a required noun as `<name>`, an optional one as `[name]`, and a many noun as `<name>...` or `[name...]`.
  - `Verb(name, run, summary, nouns: tuple[Noun, ...] = (), switches: tuple[str, ...] = (), details='', examples: tuple[tuple[str, str], ...] = (), caution='', supported_os: tuple[str, ...] | None = None, surfaces: tuple[str, ...] = ('cli', 'mcp'))`. `name` matches `^[a-z][a-z0-9-]*$`. `switches` names setting keys the verb reads, CLI-012. `caution` makes it a `--confirm` verb, BASE-013. `surfaces` says where it is offered; a verb with only `cli` is never an MCP tool, such as `mcp serve`, MCP-001. Usage is generated: `metaform <module> <verb> <nouns> [switches]`, plus `[--confirm]` for a caution verb.
  - `Subscription(topic: str, handler)`: `handler(payload: dict, ctx: Context)`, a function or coroutine.
  - `Module(id, summary, purpose, verbs=(), subscriptions=(), details='', start=None, stop=None, status=None, default=None)`. `summary` is one line for indexes. `purpose` is the module's concise instructions for agents, MCP-008 and D39. `details` is the longer help text. `id` must equal the module's folder or entry point name. `default` names one of its verbs, which `metaform <id>` runs when no verb follows, including when only switches follow, as `metaform web --json` starts the web GUI, VIEW-002; `metaform <id> --help` still prints the module's syntax, and without a default, `metaform <id>` prints it. The default verb is also reachable by its name, and over MCP it is the tool `<id>_<verb>` like any other.
  - `status`, optional, is the module's status hook: `status(ctx: Context) -> Status`, a function or coroutine run through `call`, BASE-009, where `Status(lines: tuple[str, ...] = (), notice: str | None = None)`. `lines` are status lines the module adds; `notice` is at most one notice addressed to the agent. The chassis calls the hook of every enabled, loaded module on the folder's command surface, in module id order, when it builds `metaform` status, CLI-028, `metaform help agents`, CLI-029, and the MCP server instructions, MCP-007. The context has the folder's project and store, either of which may be None. A hook that raises is reported as one status line `<id>: status failed: <ExceptionType>: <message>` and contributes nothing else. This is how module state reaches chassis output without the chassis naming any module.
  - Module source literals, read before import, BASE-015: `SUPPORTED_OS`, required; `DEPENDENCIES`, a tuple of requirement strings; `SHIPS_DISABLED`, a boolean; and from 1.0, `REQUIRES_CHASSIS`.
  - `Context` fields: `module`, `folder`, `project` (the project id or None), `store` (the data access object or None), `nouns` (a dict of noun name to value, a list for a many noun), `switches` (a dict of setting key to the value passed on this call, only those passed), `sink` (where `say` writes), `surface` (`cli` or `mcp`). Methods: `say(text)`, `setting(key)` which returns the per-call value when passed and otherwise the resolved stored or default value, CLI-011, `require_store()`, STORE-023, `publish(topic, payload)` and `publish_async(topic, payload)`, BASE-010, and `spawn(coroutine)`, BASE-018.
  - `call(function, *args)`, BASE-009.
- Acceptance:
  - Declaring `Stop` without a next step fails at the call site.
  - A verb with a many noun receives a list; a verb whose optional noun is omitted receives no key for it.
  - A verb with `surfaces=('cli',)` appears in help and not in the MCP tool list.
- Relates to: BASE-004, BASE-006, BASE-009, BASE-013, BASE-016, BASE-018, CLI-001, CLI-009, CLI-012, MCP-003.
- Status: recommended. The records replace the current `Adverb`, the free-string `nouns` and the list-based `Context.nouns`.

### BASE-036 A verb's result is data, shown the same way on every surface
- Requirement: A verb may return a result value, and the CLI and MCP present that one value, so both surfaces carry the same data.
- What this means: `say` is for messages to a person. The result is the data an agent needs back, such as the id of the element it just wrote. Every surface shows the same result.
- Why: An intake agent needs the ids of what it writes to write the joins and refs that point at them. STORE-023 requires CLI and MCP to return equal results, which needs one representation.
- How it shows: `metaform map knowledge op=add-element layer=practices-cpp address=code.bus.event name="Event bus" --json` prints `{"element_id": "...", "address": "code.bus.event", ...}`. The tool `map_knowledge` with the same arguments returns the same JSON.
- Build:
  - A verb returns None, a string, a JSON-ready value, or an object with `to_dict()`. The chassis converts it with `to_dict()` when present.
  - A string result is text, shown exactly as returned on every surface: the CLI writes it to standard output byte for byte, with no JSON encoding, no quoting and no added newline beyond what the string holds, with or without `--json`; MCP returns it as one text content block holding the string unmodified, after the `say` block when there is one. Only results that are not strings are JSON, as below.
  - CLI: lines from `say` go to standard output. A result is then printed as readable text, one `key: value` line per top-level field, where a value that is a list or an object is written as compact JSON on that line, `json.dumps(value, separators=(',', ':'), ensure_ascii=False)`, and a result that is itself a list is printed as one compact JSON line per entry, or as JSON alone on standard output when the call has `--json`; with `--json`, `say` lines go to standard error, CLI-025. `--json` is a verb control switch accepted by every verb, not a setting, D32.
  - MCP: the tool result content is one text block with the `say` lines, when there are any, followed by one text block holding the result as JSON, when there is a result.
- Acceptance:
  - For each map module verb, the CLI `--json` output and the MCP JSON block parse to equal values.
  - `metaform intake prompt` standard output and the text of the `intake_prompt` tool's content block are both byte-identical to the string the verb returned.
- Relates to: BASE-035, STORE-023, CLI-025, MCP-003.
- Status: recommended.

### BASE-037 Discovery and loading in full
- Requirement: The chassis finds modules in three places in a fixed order, reads each one's literals before importing it, and loads the enabled, compatible ones, reporting every module it does not load with the reason.
- What this means: `metaform list modules` is a complete account: every module found, where, whether it is on, and why any is not loaded.
- Why: A module that fails quietly leaves an agent searching the source for a command that was never registered.
- How it shows: `metaform list modules` prints one line per module: id, state on, off or error, place, and the summary or the reason.
- Build:
  1. Candidates, in order: the system place, `metaform/modules/` inside the package, each folder with an `__init__.py`, sorted by name; the user place, `modules/` under the home, the same way; then each installed entry point in the group `metaform.modules`, whose value is an importable package name.
  2. For each candidate: an id in `RESERVED`, BASE-014, is refused. An id already taken by an earlier candidate is refused, naming the place that holds it. Otherwise its literals are read, BASE-015. An incompatible module is refused with the reason, and so is a module whose declared dependency is not installed, BASE-015.
  3. Enabled state: the `module_state` row when present, otherwise not `SHIPS_DISABLED`, STORE-002.
  4. An enabled, compatible module is imported under the name `metaform_module_<place>_<id>` for folder modules, where `<place>` is `system` or `user`, or its own package name for entry points, with its settings declarations owned by its id, CLI-010. `MODULE` must be a `Module` whose id equals the module's id. Verb names must be unique, match BASE-035, and give tool names matching `^[a-zA-Z0-9_-]{1,64}$` with no double underscore, MCP-003. Any failure withdraws everything the module registered and records the reason as `<ExceptionType>: <message>`.
  5. Then each loaded module's `start` runs, BASE-018.
  - Discovery runs once per process and is cached. `enable` and `disable` reset the cache.
- Acceptance: One test module per refusal reason, reserved id, duplicate id, missing `SUPPORTED_OS`, wrong `MODULE.id`, duplicate verb, invalid tool name, import error, appears in `list modules` with that reason and contributes no verb or setting.
- Relates to: BASE-014, BASE-015, BASE-017, BASE-018, STORE-002, MCP-003.
- Status: confirmed for the three places and for reporting; the order and names are recommended.

### BASE-038 The map module
- Requirement: A shipped module named `map` exposes the data access object's map and layer operations as verbs, so every read and write is available on the CLI and as MCP tools.
- What this means: MCP tools come only from module verbs, MCP-003, so the map's reads and writes need a module to reach agents over MCP. The chassis `query` verb gives the same reads on the CLI with no module, STORE-028. The map module ships enabled.
- Why: The intake agent builds the map, and every agent reads it, through these verbs. One module owning them keeps one declaration per operation.
- How it shows: The tools `map_where`, `map_element`, `map_knowledge` and the rest appear in the tool list.
- Build: Every verb calls `ctx.require_store()` and exactly one operation of STORE-024 or STORE-025, returning its result per BASE-036. The fields of a record being written are data the verb acts on, so they are nouns, never switches: required nouns are positional, and optional nouns are written as `name=value` words on the CLI, BASE-043, and as named arguments over MCP. The only switch is `--raw`, a boolean setting owned by `map` that changes how `node` and every read returning joins read, STORE-025. Every result that holds a join shows the join's `layer`, the name of the layer it comes from, a subtype join's included, so the CLI and MCP output always say whether a join is from the intake map or from which knowledge layer, LAYER-016. A layer noun is a layer reference, an id or a name, STORE-013. An element, join, subtype or id noun is an address or an identity id, read as an id exactly when it matches the id form, STORE-007. The nouns mutable, hideable and blinded are `bool` nouns, BASE-035.

  | Verb | Nouns | Operation |
  |---|---|---|
  | `roots` | none | `roots`, STORE-025: the map's entry, the CQU and the DE with their joins, and every root element, one direct read |
  | `where` | address; optional `full` as a `bool` noun; with no address it returns the same entry as `roots` | `where`: one read of an address, the read an agent orients from: the element, what relies on it, what it relies on, the subtype joins inside those joins and the one holding it, its open work records and the layers in context at it, STORE-025. Ids and empty fields are left out unless `full=true` |
  | `element` | element | `element` |
  | `joins` | element, optional `as` receiver or provider | `joins` |
  | `identity` | element | `identity` |
  | `subtypes` | join | `subtypes`: the subtype joins in the join, each with the element it holds |
  | `children` | address | `children` |
  | `layers` | optional tag, kind, module | `layers` |
  | `tag`, `untag` | layer, tag | `tag`, `untag`, STORE-038 |
  | `layer` | layer, optional node | `layer_items` |
  | `node` | node; switch `--raw` | `node` |
  | `context` | address | `context` |
  | `links` | node | `links_to` |
  | `citing` | key, value | `citing` |
  | `history` | id | `history` |
  | `stack` | | `stack` |
  | `metaforms` | optional project | `metaforms`, `active_metaform`, STORE-041 |
  | `add-metaform` | name, optional project | `add_metaform`, STORE-041 |
  | `activate` | name, optional project | `activate_metaform`, STORE-041 |
  | `search` | text | `search` |
  | `work` | `op=` one of `list`, the default, `add`, `edit`, `done`; for `list`, optional `node`, `condition`, `open` as a `bool` noun; for `add`, `node` and `condition`, optional `note`, `task`, `held` and `reviewed` as `bool` nouns; for `edit`, `id` and any of `condition`, `note`, `task`, `held`, `reviewed`; for `done`, `id`, optional `resolution` | `work`, `add_work`, `edit_work`, `finish_work`, STORE-042. Served as the one tool `map_work`, so any agent writes or reads the condition of an object at any time, MAP-046 |
  | `knowledge` | `op=` one of `create`, `add-element`, `add-join`, `add-subtype`, `add-property`, `add-item`, `add-ref`, `add-plan`, `edit`, `remove`, `correct`, `finish`, `peel`, `discard`; `layer=` naming the layer on every call; then the nouns of that operation: for `create`, name, variable, mutable, hideable, optional kind, fields (`layer` or `correction`), sources, tags and the provenance fields module, workflow, prompt, model, role, blinded; for `add-element`, address, optional name_length, role, refs, extra; for `add-join`, receiver, provider, purpose, function, relation, observation, optional name, ef, verb, non_goal, type, refs, extra; for `add-subtype`, join, the parent join, and address, the element it holds, optional function, ef, relation, verb, observation, non_goal, name, name_length, role, refs, extra, where `name` and `refs` are the subtype join's and name_length and role the element's, MAP-020 and STORE-011; for `add-property`, element, value, optional refs, extra; for `add-item`, node, value, optional link, refs, extra; for `add-ref`, owner, key, value; for `add-plan`, element, join; for `edit`, id and each changed field of STORE-034, a join's `receiver`, `provider` and `parent` included, which move it, MAP-003; for `remove`, id; for `correct`, id, reason, optional evidence, `remove=true` and each changed field of STORE-034 | the matching STORE-024 operation: `layer`, `add_element`, `add_join`, `add_subtype`, `add_property`, `add_item`, `add_ref`, `add_plan`, `edit`, `remove`, `correct`, `finish`, `peel`, `discard` |
  | `select`, `mask` | address, layer | `select`, `mask` |
  | `clear` | address, layer, kind | `clear` |
  | `hide`, `unhide` | layer | `hide`, `unhide` |
  | `reexamined` | layer | `reexamined` |
  | `answer` | challenge, A or B or C; for C `link=` an existing element or join | `answer` |
  | `approve` | challenge; CLI only, `surfaces=('cli',)`, never an MCP tool | `approve` |

  `knowledge` is the one read-write verb for layers, served as the single MCP tool `map_knowledge`, LAYER-018. It is the only verb that makes a new layer. Every call names its layer with `layer=`. There is no token and no ownership check: an agent that has the tool can write to any knowledge layer, before or after it is finished, and an agent without it cannot write to any. Granting or withholding the tool, through the command surface, CLI-022, and harness permissions, is the whole of the access rule. An agent builds a layer with `op=create`, then adds, edits and removes objects one at a time, then `op=finish` when its task is done. The intake layer is created only by `intake_start`, BASE-039, and the memory layer only by the memory module, LAYER-012.

  Neither `knowledge` nor `work` refuses what it is sent for its content, BASE-044. A field an operation writes that is missing is stored empty and named in a notice, `<field> is missing; stored empty.`, the way the intake's tools do: a join's purpose, function, relation and observation, an item's or a property's value, a ref's key and value, a correction's reason and a work record's condition. A new layer's variable is stored empty with the notice of LAYER-002, and its mutable and hideable, when missing, are stored false, each named in a notice. A ref that is not a key and a value, both text, is not written as a ref: it is kept in the record's `extra` under `refs`, with a notice, `A ref is a key and a value, both text; one was not, and kept in the extra under refs.`, or `two were not` and so on, counted as PROJ-025 counts, the way the intake's tools keep it and for every writer that takes `refs`, STORE-012; `add-ref`'s key and value are text nouns, so over MCP a value that is not text reaches it as JSON text under BASE-035's rule. `add-join` and `add-subtype` store `perspective` and `verb` in the join's and the subtype's own fields, as `intake_join` and `intake_subtype` do. Besides the store's own errors, for a reference that names nothing or an argument it cannot read, STORE-026, a call stops, exit 2 with one Next line, only when it names no operation, or when a field is missing that its record cannot be stored without because nothing else in the call can stand for it:

  | Verb and operation | Field | Why nothing can stand for it |
  |---|---|---|
  | `knowledge`, every call | `op`, missing or not one of the operations | The call names nothing to do. |
  | `knowledge` `create`, `finish`, `peel`, `discard` | `layer` | It is the layer the call makes or acts on. An add operation sent without a layer goes to a new unnamed layer instead, LAYER-001; `edit`, `remove` and `add-ref` name their thing by id, so they go ahead and a notice says no layer was named. |
  | `knowledge` `add-plan`, `correct` | `layer` | A plan's row names the layer it comes from and is never stored without one, STORE-040, and a correction is written into the building correction layer that applies it, STORE-017; nothing else in the call names either. |
  | `knowledge` `create` | `kind` other than `layer` or `correction` | The intake layer and memory are made only by their own modules, and the store holds no other kind. |
  | `knowledge` `add-element`, `add-subtype` | `address` | An address is the element's identity, the element a subtype join holds included, STORE-009 and STORE-011. |
  | `knowledge` `add-join` | `receiver`, `provider` | A join is owned by its receiver and served by its provider, STORE-010. |
  | `knowledge` `add-subtype` | `join` | A subtype join lives inside one join, STORE-011. |
  | `knowledge` `add-property`, `add-plan` | `element` | The element the property or the plan belongs to. |
  | `knowledge` `add-item` | `node` | The node the item attaches at, LAYER-003. |
  | `knowledge` `add-ref` | `owner` | The thing the ref belongs to, STORE-012. |
  | `knowledge` `edit`, `remove`, `correct` | `id` | The thing to change. |
  | `work`, every call | `op` not one of `list`, `add`, `edit`, `done` | The call names nothing to do. |
  | `work` `add` | `node` | A work record is attached to one element or join, STORE-042. |
  | `work` `edit`, `done` | `id` | The work record to change. |

  A node noun is written `element:<address or id>`, `join:<id>` or `type:<address>`; a subtype join is `join:<id>`, and the element it holds `element:<address or id>`. `refs` is a `json` noun holding an array of `[key, value]` pairs of strings, with the schema `{"type": "array", "items": {"type": "array", "items": {"type": "string"}, "minItems": 2, "maxItems": 2}}`. `extra` is a `json` noun holding an object, with the schema `{"type": "object"}`. Neither is ever a switch. `retire` and `hide` are caution verbs.
- Acceptance:
  - Each verb's result equals the result of its operation called directly, and each appears as a tool with a schema built from its declaration.
  - Each field the table above does not list, missing from its operation, is stored empty or false and named in a notice, exit 0; each field it lists, missing, stops the call with exit 2 and one Next line and writes nothing.
  - `op=add-join` and `op=add-subtype` with `perspective` and `verb` read back with them in the join's and the subtype join's own fields and nothing in `extra`.
  - `op=edit` with `receiver` moves a knowledge layer's join to that receiver with the same id, and with `parent` makes it a subtype join of that join.
- Relates to: STORE-010, STORE-011, STORE-024, STORE-025, STORE-028, STORE-032, STORE-040, STORE-042, BASE-035, BASE-036, BASE-044, LAYER-015, LAYER-018, MCP-003.
- Status: recommended. `approve` being a person's act on the CLI only is confirmed, LAYER-015.

### BASE-039 The intake module
- Requirement: A shipped module named `intake` serves the Canonical Intake instructions by name, records the intake one object per call as the agent reasons it, lets the agent read back and correct what it recorded before it finishes, and reports intake state.
- What this means: The intake module owns everything specific to the intake and nothing general. An intake run is: a subagent reads `intake prompt`, which returns the intake text unchanged except for its filled target, followed by lines from the module saying how to record; it starts the intake with `intake_start`; as it works the method it records each element with `intake_element`, each join with `intake_join` and each subtype join with `intake_subtype`, one object per call, as soon as it is reasoned; it anneals with `intake_absorb`, one call per join it places inside its parent's join; once everything is recorded it performs the proofing pass of the intake's step 12, reading the map back with `intake_show`, whole or one receiver at a time, and correcting it with `intake_edit` and `intake_remove`; and it ends with `intake_finish`, which carries its intake report on the project and any feedback on the Metaform process, BASE-045. The tools never parse the intake's XML: each takes one object's fields, named as in the intake's response schema, the metaform's general data pattern: elements; joins held by their receivers, each with a purpose and a function; subtype joins inside their parent join with their own function and no purpose; and refs. The intake text can change as long as its data still follows that pattern, and such changes need no change to the tools. Every record goes into one building intake layer. While it is building, no context read sees it, the no-intake notice stays away because an intake is being recorded, and the web GUI draws each object as it arrives, VIEW-005. At the finish every read sees it, and from then on it changes only through correction layers, STORE-017. Nothing is refused for its content, BASE-044. The tools carry no condition field: the condition of an object is a work record, apart from the map, which the intake agent writes with `map_work` as it maps, MAP-046. The module ships enabled.
- Why: The orchestrator passes only the name of the instructions, and the subagent reads them itself, MCP-009. Tools that take the general data pattern mean an intake text change that keeps the pattern never breaks recording. Rich, 2026-09-26: an intake is long, so the agent records the map as it builds it and the web GUI shows each object as it arrives; once everything is recorded, the agent proofs it. Recording as it goes improves the result and lets agents with smaller context windows perform the same intake, since no agent has to hold the whole map in its head: the system helps the agent build the metaform.
- How it shows: `metaform intake prompt` prints the intake text with the project's target filled in, and nothing beside it. During the run, `metaform` status says an intake is being recorded, and the web GUI grows the map object by object. After `intake_finish`, `metaform intake status` says the project has an intake, and `metaform` status no longer shows the notice.
- Build:

  | Verb | Nouns | Does |
  |---|---|---|
  | `prompt` | none | Returns the stored intake text with its target filled, and nothing beside it |
  | `start` | optional `model`, `role`, `blinded` as a `bool` noun, `id`, the result's generated id | Opens the building intake layer `intake-<UTC timestamp YYYYMMDDTHHMMSSZ>-<6 random lowercase hex characters>`, kind intake, immutable, not hideable, variable `The functional map of the artifact: its elements, and each receiver's purpose served by a provider's encounter function.`, provenance module `intake`, workflow `canonical-intake`, prompt empty, since no copy of the Canonical Intake is kept, STORE-016, and model, role and blinded as the calling agent gives them. When an intake is already being recorded, it resumes that one and says so. Returns the layer, the project and the metaform |
  | `element` | `namespace_address`; optional `role`, `name_length`, `refs`, `extra`; and `name`, which an element does not hold | Records one element, or describes again one already recorded in this intake: the fields given replace the ones it had, the others are kept. An element is its address, name_length and role, STORE-009; a `name` given is kept in its `extra` with a notice saying that the project's name for a functionality goes on the join. Returns `element_id` and `namespace_address` |
  | `join` | `receiver`, `provider`, both addresses; optional `name`, `purpose`, `ef`, `perspective`, `relation`, `verb`, `observation`, `non_goal`, `type`, `refs`, `extra` | Records one join held by its receiver, with the project's name for the functionality it names, MAP-020. An address that names no element gets one in the intake layer, with no role, and a notice. Returns `join_id` |
  | `subtype` | `into`, the parent join's id, and `namespace_address`, the element it holds; optional `purpose`, `ef`, `perspective`, `relation`, `verb`, `observation`, `non_goal`, `role`, `name`, `name_length`, `refs`, `purpose`, `extra` | Records the element, or describes it again as `element` does with the `role` and `name_length` given, and one subtype join inside the parent join holding it, MAP-030; `name` and `refs` are the subtype join's, MAP-020. Returns the subtype join's `join_id`, its `parent` and the `element_id` it holds |
  | `absorb` | `join`, the id of the join where the element provides, and `into`, the id of the parent's purpose join | Makes that join a subtype join inside `into`, keeping every field, its purpose among them; any other join that still names the element is listed in a notice and left as it is, MAP-030 and STORE-034. Returns its `join_id`, its `parent` and the `element_id` it holds. After the finish it writes nothing and names the correction layer, STORE-032 |
  | `show` | optional `receiver`, an element's address | The intake being recorded: with no receiver, whole, read by `layer_graph`, STORE-025, every element with its `element_id` and `namespace_address`, every join with its `join_id` and, under `subtypes`, each subtype join inside it with its `join_id`, `parent` and the `element_id` and `namespace_address` of the element it holds, and the addresses recorded only as the end of a join and never described with `element`; with a receiver, that receiver's joins and what they hold, and the elements they name, so an agent never has to read the whole map at once |
  | `edit` | `id`: an element's address or `element_id`, or a `join_id`, a subtype join's included; the fields to change | Changes one recorded object in place while the intake is building; the fields given replace the ones it had. An element cannot be moved, MAP-015: `namespace_address` on an element is not applied, and the notice says to record the element at the new address and move its joins with `receiver` or `provider`. `receiver` and `provider` move a join, MAP-003; on a subtype join `namespace_address` gives it another element to hold, and `role` and `name_length` describe the element it holds. After the finish it writes nothing and names the correction layer, STORE-032 |
  | `remove` | `id` | Removes one recorded object while the intake is building; what still used it is named, STORE-017 |
  | `finish` | optional `report`, `feedback` | Marks the layer ready. Writes the report and feedback files, BASE-045. Returns the layer name, the project id, the metaform name, the counts of the elements, the joins held by receivers, the subtype joins and the refs recorded, the count of open work records on its objects as `work`, and `notices`, BASE-044, among them the addresses never described |
  | `status` | none | Has an intake or not, with the name of the latest intake layer, and the intake being recorded when there is one |

  - Field schemas, each tool's `inputSchema`, JSON Schema draft 2020-12: `perspective` is one of `Function`, `Encounter`, MAP-020; `role` on `element` one of `AUE`, `CQU`, `DE`, `SE`, `NE`, and on `subtype` one of `DE`, `SE`, `NE`, the nested element's roles in the Canonical Intake; `name_length` an integer at least 1; `refs` an array of objects with `key` and `value`, both strings, in order; `extra` an object. Every other field is a string. Each field's description is the Canonical Intake's own wording for it, from `specifications/Canonical_Intake.xml`, the proper schema for the shape; `name` on `join` and `subtype` takes the wording of the Canonical Intake's name, a Canonical Name in the project's official terminology or an informal name. `name` on `element` is described as `purpose` on `subtype` is: what goes there, the join, and that a name given is kept in the element's `extra`. On the CLI the same fields are `name=value` nouns, with `refs` and `extra` as JSON text. A `refs` value that is not a JSON array, over MCP a value of another type and on the CLI text that parses to another type or does not parse as JSON, is read as a list holding that one ref, never refused, BASE-044: an object with `key` and `value`, both text, is then one ref, and anything else is the odd ref STORE-012 places in the record's `extra` under `refs` with its notice. The store still writes each ref as its own row, STORE-004.
  - Intake is never gated or judged; only the resulting map may be graded, Canonical Intake constraint. Nothing recorded is refused for its content, BASE-044. Each condition below is stored as given and named in a notice by the field it concerns:
    - an address not in the form of MAP-010: stored as given;
    - a join end that names no element: an element is created at that address in the intake layer, with no role;
    - a join whose provider is its own receiver: stored as given, D82; a correction layer or a reviewer deals with it;
    - a join absorbed into a join whose receiver is not its own: stored, with its receiver's address in its `extra`;
    - an element held by another subtype join: stored, with a notice naming that subtype join, D4;
    - `namespace_address` given to `edit` for an element: not applied, since an element cannot be moved, MAP-015;
    - an element given a `name`: stored, with the name in the element's `extra`, and the notice says that the project's name for a functionality goes on the join, with `intake_join`'s `name`. The Canonical Intake's schema still shows a `<name/>` on the element; that text is Rich's and changes only with his wording, MAP-040;
    - an `perspective` that is not `Function` or `Encounter`: the object is stored without it, with the value kept in `extra`, MAP-020;
    - a ref that is not a key and a value, both text, or an `extra` that is not a JSON object: kept in `extra`;
    - a missing `purpose`, `ef`, `perspective`, `relation`, `verb` or `observation` on a join, the same on a subtype join, or a missing `role` on an element: the object is stored with the field empty.
    An element recorded twice at one address is the same element, MAP-015: its joins stay under it, and the second call describes it again.
  - A record sent before `start` starts the intake, with a notice. An intake into a metaform that already has an intake is recorded, never blocked, in a new metaform of the project named `intake-<UTC timestamp YYYYMMDDTHHMMSSZ>`, STORE-041, which becomes the active metaform at the finish; the earlier metaform is kept whole. `start` says where it is recorded, and `finish` names `metaform activate metaform <earlier name>` as the way back.
  - An intake left building by an agent that stopped is resumed by the next `start`; `show` returns what it holds.
  - Status hook, BASE-035: `status(ctx)` returns no lines and no notice when `ctx.store` is None. When `has_intake()` is true, it returns the lines `Intake: complete` and `Start with: metaform map roots` and no notice, with `Intake: being recorded in layer <layer> of metaform <metaform>` between them when another intake is being recorded. Otherwise, when an intake is being recorded, it returns that line alone and no notice. Otherwise it returns the line `Intake: none yet` and the notice of MCP-009.
  - The stored intake text is the module resource `resources/Canonical_Intake.xml`, a checked-in byte copy of `specifications/Canonical_Intake.xml`. It is served as shipped and is never kept in the prompt store or edited, STORE-044. A repository test fails when the two files differ, so adopting a new intake text means copying the file in the same commit. A test file is never served unless the setting `intake_file` names one: declared `settings.text('intake_file', '', scope='folder')`, owned by `intake`, where the empty default means the resource and any other value is a file path read at serve time.
  - Serving: the text is returned exactly as stored, except that the attributes of its first `<target>` element are filled: `type` with the project's target type and `value` with its target value, each escaped for an XML attribute: `&` as `&amp;`, `<` as `&lt;`, `>` as `&gt;` and `"` as `&quot;`, in that order. If the text contains the literal `{project_id}`, each occurrence is replaced with the project id. Nothing is added before it or after it: the intake is the instruction, and an instruction served beside it competes with it, so the agent cannot tell which of the two is the procedure, and the person who reads the intake has not read what the agent was told. Corrected 2026-09-29, Rich: no instructions are side loaded into a workflow; before, recording lines were appended, which said how to record, gave the stop rule, and asked for the report and the feedback by the `--report` and `--debug` settings. Two sentences of those lines were Rich's own, 2026-09-27: `Do not read past memories or any other details other than the material targeted for intake. Record each element as you work through the process.` The intake tools record into the folder's project, or the project named by their optional project argument, MCP-025.
  - Model and role are supplied by the agent that calls `start`, since only the agent knows them.
- Long text at the finish: on the command line, `report=` and `feedback=` given a value that names a file read the file, and `-` reads standard input, as `metaform feedback` reads them, BASE-045. Over MCP the value is the text itself and no path is opened. The reason: a report runs to pages with quotes and new lines in it, which a command line carries badly, so an agent without MCP writes it to a file first; a tool that opened whatever path it was handed would let a report's text reach files it was never meant to read.
- Resuming: a `start` that resumes a layer being built fills in the model, role, blinded flag and result id the layer lacks, LAYER-010; what the layer holds is kept, and a different value is named in a notice and not stored. The reason: an orchestrator starts the intake before the agent, so the page shows it, and knows only the model; the agent knows its own role and its result's id, and they were dropped without a word.
- Acceptance:
  - `intake prompt` output differs from the stored file only inside the `<target>` element's attributes, whatever the settings are, and ends where the stored file ends.
  - A subtype join recorded with `type=purpose`, as the intake writes it, is stored with no notice and nothing set aside.
  - An intake recorded one object per call reads back whole after `finish`; before `finish`, `has_intake()` is false, no context read returns its elements, and `show` returns all of them.
  - A join recorded without its purpose is stored, and the call's notice names `purpose`.
  - A subtype join carrying a `purpose` is stored with it as its own purpose, and no notice is given.
  - `absorb` makes a recorded join a subtype join inside the parent's join with the same `join_id` and every field, its purpose among them; another join naming the element it holds is listed in the notice, and once no other join names it, that element, still one element record, is in neither the roots nor the graph.
  - `show receiver=<address>` returns that receiver's joins, each with the subtype joins it holds, and no join of another receiver.
  - Every object `show` lists is under the key its recording call returned: `element_id`, `join_id`, and for a subtype join `join_id` with `parent`; `edit` and `remove` take any of them as `id`.
  - `edit` with `namespace_address` on an element leaves the element at its address and names `namespace_address` in a notice; with `receiver` on a join it moves the join, keeping its `join_id`.
  - An element recorded with a `name` has the name in its `extra` and none of its own, and the call's notice names `name` and the join; a join and a subtype join recorded with a `name` read back with it; `show` returns each join's and subtype join's name and each element's name_length and role.
  - A join whose provider is its own receiver is stored and named in a notice.
  - `edit` and `remove` change a building intake; after `finish`, `edit` and `absorb` write nothing and name the correction layer.
  - A record sent before `start` starts the intake with a notice, and a second `start` resumes the same layer.
  - A second intake into the same metaform is recorded in a new metaform, activated at the finish, and the first is kept whole.
  - A `finish` with `report` and `feedback` writes both files and lists them in `list_reports`; a `exclude` work record written with `map_work` on one of its elements is counted in the finish's `work` and returned by `map_work condition=exclude`.
  - An element recorded twice at one address is one element holding both calls' joins.
  - A real intake, such as a real project's map, recorded and finished, sets `has_intake()` true and reads back per MAP-040 acceptance 1.
- Relates to: MCP-009, MAP-040, MAP-043, STORE-009, STORE-024, STORE-032, LAYER-001, LAYER-010, VIEW-005.
- Status: confirmed 2026-09-26: recorded one object per call as it is reasoned, read back and proofed before the finish, the web GUI following it live; the tools' fields are the metaform's general data pattern with its names taken from the Canonical Intake; the intake text served unchanged plus the module's recording lines. Records are never blocked; the report and the feedback are confirmed, BASE-044, BASE-045. Rich, 2026-09-27: the condition of an object is a work record apart from the map, never a field of the intake's objects, MAP-046. Rich, 2026-09-27: the element is its address, name_length and role, and the project's name for a functionality goes on the join; keeping a name sent with `intake_element` in the element's `extra` until the Canonical Intake's text changes is recommended. Rich, 2026-09-27: an element always appears as one element record and annealing places it in its parent's join as a subtype join; an element cannot be moved and a join can; the intake must not depend on the size of the agent's context. `absorb`, `show receiver=`, `namespace_address` and `into` as the tools' field names, and the ids under the keys their recording calls return, are recommended. Storing a second intake as a new active metaform, the notice list and the CLI form are recommended. Self joins and joins to a subtype are stored as given, D82. Rich, 2026-10-01: `intake start` again returns the layer, project and metaform it opened, and `intake prompt` again serves the Canonical Intake; handing the intake over from `start`, built 2026-09-30, is undone. Corrected 2026-10-01 by LAYER-025: the layer is named `intake`. Corrected 2026-10-01, Rich: the missing and broken findings an intake reports show on the map, so `intake element`, `intake join` and `intake subtype` take `condition` and `note`, which write a work record at what they record, MAP-046; their definitions in the intake's prompts.xml are the Canonical Intake's step 2 words.

### BASE-040 The memory module
- Requirement: A shipped module named `memory` offers the reference memory server's operations as verbs over the map's nodes.
- What this means: The operations of LAYER-013, on the memory layer of STORE-020. The module ships enabled.
- Why: Agents already know these operations, and one declaration gives them on the CLI and as tools.
- How it shows: `metaform memory add-observations element:code.manager.route "Routes are ejected, never packed on delete."`.
- Build:

  | Verb | Nouns | Maps to |
  |---|---|---|
  | `create-entities` | name, entity type | D18: pending; recommended to create an element in the memory layer |
  | `create-relations` | from node, relation type, to node | `add_item` in memory at from, linking to, value the relation type |
  | `add-observations` | node, text... | one `add_item` per text |
  | `delete-entities` | node... | deletes every memory item at each node; never the node |
  | `delete-observations` | node, text... | deletes memory items at the node whose value equals each text |
  | `delete-relations` | from node, relation type, to node | deletes the matching relation item |
  | `read-graph` | none | every memory item, grouped by node |
  | `search-nodes` | query | `search` on the memory layer, grouped by node |
  | `open-nodes` | node... | for each node: its identity read, its memory items, and memory relations to it |

  Node nouns follow BASE-038. Each writing verb creates the memory layer on first use, STORE-020.
- Acceptance: `add-observations` then `open-nodes` on the same node returns the observations; a relation from A to B appears when opening B.
- Relates to: LAYER-012, LAYER-013, STORE-020, BASE-038.
- Status: recommended.

### BASE-041 The build command
- Requirement: `metaform build` writes one wheel of the chassis and the enabled modules to a known place, with module dependencies as wheel metadata and pure-Python dependencies carried inside for direct runs.
- What this means: A user's build holds exactly what they use, BASE-022, and runs offline when run directly, BASE-024.
- Why: The installer and the user need to find the built wheel, and an uploaded wheel has no network to fetch its dependencies.
- How it shows: `metaform build` prints the path of the wheel it wrote.
- Build:
  - Output: `~/.metaform/builds/<UTC timestamp YYYYMMDDTHHMMSSZ>/metaform-<version>-py3-none-any.whl`. The wheel is always tagged `py3-none-any`. The newest build is recorded in the base database `meta` table as `last_build`, the wheel's absolute path.
  - The chassis writes the wheel itself with the standard `zipfile` module, from the installed package, so no source tree is needed: the files of the installed `metaform` package, found from `metaform.__file__`, excluding `__pycache__` folders; each enabled module, from any place, copied to `metaform/modules/<id>/` so that it is a system module inside the wheel, without its `tests/` folder, which a running wheel never uses; the root `__main__.py`, BASE-042; and the `metaform-<version>.dist-info/` folder with `METADATA`, `WHEEL`, `entry_points.txt` and `RECORD` written as the wheel format, PEP 427, the core metadata format and the entry points format define them. `entry_points.txt` holds a `[console_scripts]` section with `metaform = metaform.cli:main`, so installing the wheel, or running it with `uvx --from <wheel>`, creates the `metaform` command; and a `[metaform.modules]` section with one line `<id> = metaform.modules.<id>` for every module the wheel carries. `WHEEL` holds `Wheel-Version: 1.0`, `Generator: metaform <version>`, `Root-Is-Purelib: true` and `Tag: py3-none-any`. `RECORD` lists every file with its `sha256=` urlsafe base64 digest without padding and its size, and itself with empty fields. `METADATA` holds `Metadata-Version: 2.1`, `Name`, `Version`, `Requires-Python` as the chassis declares it, and `Requires-Dist` lines.
  - `Requires-Dist` lists the chassis's own dependencies followed by the `DEPENDENCIES` of every module the wheel carries, duplicates removed. The chassis's own list is the `[project].dependencies` array of the chassis `pyproject.toml`, copied at package build time into the literal `CHASSIS_DEPENDENCIES` in `metaform/_build_info.py`, which the build reads, because an installed package has no `pyproject.toml` and its installed metadata also names the dependencies of every module it carries. A module's requirements are only ever its own `DEPENDENCIES` literal. `mcp` is the `mcp` module's requirement, so a build that does not carry the `mcp` module does not list it.
  - Carried dependencies: the build writes those requirements to a temporary file, pins them with `uv pip compile <file> -o <pinned> --no-header`, and installs the pinned set with `uv pip install --target <temporary folder> --no-deps -r <pinned>`. Each installed distribution whose `RECORD` lists no `.so`, `.pyd` or `.dylib` file is pure Python and is copied into the wheel under `metaform/_vendor/`. A compiled distribution is not carried: it stays in `Requires-Dist` only, the build still succeeds, and it prints one line per compiled distribution naming it and the enabled module that needs it, with the note that a direct run of this wheel needs it installed. An installed or uvx run gets it through `Requires-Dist`.
  - The build needs `uv` and network or a warm uv cache. Running the wheel directly does not, when every carried dependency is pure Python.
- Acceptance:
  - With `map` enabled and `hello` and `template` disabled, the wheel holds `metaform/modules/map/` and neither `metaform/modules/hello/` nor `metaform/modules/template/`, lists only `CHASSIS_DEPENDENCIES` and map's `DEPENDENCIES`, with no `mcp`, and runs `python <wheel> query layers` in a container with no network.
  - `uvx --from <wheel> metaform --version` runs, which checks `entry_points.txt`.
  - With `mcp` enabled, the build succeeds, the wheel is tagged `py3-none-any`, `pydantic_core` is absent from `metaform/_vendor/` and present in `Requires-Dist` through `mcp`, and the build output names it with the `mcp` module.
  - `pip install <wheel>` into a fresh environment succeeds, which checks the `RECORD` and `METADATA` format.
- Relates to: BASE-022, BASE-024, BASE-026, BASE-042, MCP-010.
- Status: recommended.

### BASE-042 A directly run wheel bootstraps from itself
- Requirement: A wheel's root `__main__.py` makes `python <wheel>` run Metaform from the wheel, with its carried dependencies and its own home.
- What this means: Python runs a zip file's root `__main__.py`. The bootstrap puts the wheel and its carried dependencies first on the import path, chooses the wheel's own home, and runs the CLI.
- Why: A direct run must never use or change an installed Metaform, BASE-023, and must work offline, BASE-024.
- How it shows: `python metaform-0.2.0-py3-none-any.whl` prints status with `Home: ~/.metaform/wheels/...`.
- Build: `__main__.py` inserts the wheel path and the wheel path joined with `metaform/_vendor` at the front of `sys.path`, removes any other path entry that provides a `metaform` package, sets `METAFORM_HOME` to `~/.metaform/wheels/<name>-<version>` when it is not already set, sets `METAFORM_WHEEL` to the wheel's absolute path, then calls `metaform.cli.main()` and exits with its code. Nothing is unpacked to disk.
- Acceptance: With a different Metaform installed, `python <wheel>` reports the wheel's version and home, and the installed package's files and base database are unchanged afterwards.
- Relates to: BASE-023, BASE-024, BASE-041, STORE-001.
- Status: recommended.

### BASE-043 Optional nouns are written as name=value
- Requirement: A verb's optional nouns are passed on the CLI as `name=value` words, in any order after its required nouns, and over MCP as named arguments.
- What this means: Required nouns stay positional, so common calls read naturally. A record with many optional fields, such as a join with a non-goal and refs, is written without a fixed order and without turning data into switches. A word containing `=` whose part before `=` is an optional noun of the verb is that noun. After `--`, no word is read this way, CLI-003.
- Why: The grammar keeps data as nouns and behavior as switches, and switches are settings, CLI-011. Record fields are data, and storing a join's purpose as a setting would be meaningless. Named optional nouns keep the grammar and stay readable.
- How it shows: `metaform map add-join intake-20260924T220000Z code.daemon code.failsafe "catch a dead gateway" "probes the gateway" "The failsafe probes the gateway." "One probe every 5 s." non_goal="balance load"`.
- Build: The shared parser, CLI-001, reads required nouns in order, and `name=value` words for optional nouns wherever they appear before `--`, then the rest per CLI-003 and CLI-004. A `json` noun's value is parsed as JSON. An unknown name before `=` is kept in the record's `extra`, with a notice naming the verb's optional nouns, BASE-044. Over MCP, each noun is a property of the tool's input schema, required ones listed as required, MCP-005. A noun the verb declares but the operation it runs does not read, such as `key=` on `map knowledge op=add-property`, is treated the same way: kept in the added object's `extra` with a notice when the operation is one of the add operations, and otherwise named in a notice as ignored, BASE-044. `edit` and `correct` change a thing that already exists, so a noun they do not read is never written into it.
- Acceptance: The example above stores the join with its non-goal; the same call with `non_goal=` moved before the positional fields stores the same join.
- Relates to: BASE-035, BASE-038, CLI-001, CLI-003, MCP-005.
- Status: recommended. See question 10 of this section.
### BASE-044 Agent submissions are never blocked
- Requirement: No agent submission is refused for its content; what does not fit is stored as given and noted in the result as a notice, never an error; and an agent that cannot continue stops, submits a trouble report and ends, never looping.
- What this means: This covers every write an agent makes: the intake tools, the knowledge-layer tool, memory, challenge answers, feedback, and settings an agent sets. When part of a submission does not fit the pattern, it is stored as given, and the result names each part and what happened to it, once. An operation that cannot apply, such as an in-place edit of an intake layer's item, writes nothing and says which operation does it; the call still succeeds. Only a call that cannot be read at all, or a failure that would damage the store itself, is an error, and its message tells the agent once what to do, never to try again. When an agent cannot submit its shape at all, it saves what it has with its report, BASE-045, so a person can review and fix it. An agent that cannot continue for any reason stops: it submits a trouble report through `feedback` and ends. It never keeps looping.
- Why: An agent must never loop and spend inference retrying, especially during testing. A rejecting check once turned a five-minute intake into 456 minutes and $750. The shape enforces itself; what does not fit is kept, seen and fixed later by a correction layer or a reviewer, not bounced back to the agent.
- How it shows: `intake_join` without a purpose returns the join id and `notices: [{"where": "purpose", "message": "purpose is missing; stored empty."}]`, with no error.
- Build:
  - A result that has notices carries them under `notices`: a list of objects with `where`, the path or id of the part, and `message`, one sentence. The CLI prints each as `Notice: <where>: <message>` after the result; MCP returns them in the JSON block with `is_error` false. BASE-036.
  - The data access object's rules for what is stored and what is noted are STORE-026. Module verbs follow the same rule: a verb raises `Stop` only when its call cannot be read or the store would be damaged.
  - A field that is missing is stored empty, and the result names it in a notice, `<field> is missing; stored empty.`. A call stops only when a field is missing that its record cannot be stored without at all, because nothing else in the call can stand for it: the field that says what the record is, where it attaches, or which layer holds it. For the map's write tools, `map_knowledge` and `map_work`, BASE-038 lists those fields and why.
  - The exit code of a CLI call that stored with notices is 0.
  - The stop rule is delivered in the words agents read: the base instructions, MCP-007 and MCP-029, say to stop and submit a trouble report instead of retrying. It applies whatever the settings are. Whether the trouble report is written when `--debug` is off is open, question 12 of this section; until it is answered, it is written.
  - `approve`, which only a person runs on the CLI, LAYER-015, and module loading, BASE-037, are not agent submissions and keep their stated checks.
- Acceptance:
  - For every refusal condition that STORE-026 and BASE-039 turn into a notice, the call returns `is_error` false over MCP and exit 0 on the CLI, the notice names the part, and the part is readable raw afterwards.
  - An MCP client that sends a malformed `elements` receives exactly one notice and no request to retry; no row is written and the server keeps serving.
  - `map knowledge op=add-join` with a receiver and a provider and none of purpose, function, relation and observation stores the join with those four empty, exit 0, and one notice for each; `map work op=add` without a condition stores the record with an empty condition, exit 0, and one notice naming `condition`. `op=add-join` without a receiver, and `op=add` of `work` without a node, stop with exit 2 and one Next line, and write nothing.
- Relates to: STORE-026, BASE-038, BASE-039, BASE-045, LAYER-015, LAYER-018, MCP-006.
- Status: confirmed. The notice format is recommended. Whether a trouble report is written with `--debug` off is open, question 12.

### BASE-045 Process feedback and intake reports are saved, reviewable and part of provenance
- Requirement: Every agent doing Metaform work can submit freeform feedback on the Metaform process, the intake agent submits a report on the project it examined, and both are saved as separate files in the project's reports folder, listed and readable, and referenced from the layer's provenance; the settings `--debug` and `--report` decide whether agents are asked for each, CLI-034.
- What this means: Feedback is about Metaform itself: problems with the process, bad semantics, a tool that did not match its schema, anything. The intake report is about the project that was examined: broken code, things that need fixing, anything not working or partially working. An agent that could not submit its shape at all attaches the raw result it has, so it can be reviewed and fixed. The files are kept in the Metaform home, never in the project folder, and a person or an agent can list and read them. When they belong to a layer, that layer's provenance record carries them as refs. Provenance still tracks only one record per layer and the intermediary diffs; the reports are refs on the layer's record, not new provenance.
- Why: The people improving Metaform need to hear from the agents running it, in their own words, and the project owner needs what the intake agent found wrong with the project. Keeping both with the layer's provenance ties each report to the run that produced it. Saving an unsubmittable result means no work is lost and nothing is retried.
- How it shows: `metaform feedback "The subtype field names did not match the intake text." layer=intake-20260925T041500Z` writes `~/.metaform/projects/notes/reports/intake-20260925T041500Z-feedback.md`. `metaform list reports` lists it with the intake report. `metaform read report intake-20260925T041500Z-report.md` prints the report.
- Build:
  - Files live in `projects/<project id>/reports/` under the home, STORE-001, or `reports/` under the home when no project is known. Names: `<run id>-report.md`, `<run id>-feedback.md`, `<run id>-shape.txt`, where the run id is the layer id when the file belongs to a layer, and otherwise `<UTC timestamp YYYYMMDDTHHMMSSZ>-<6 random lowercase hex characters>`. A second write for the same run id and kind appends a new section, headed by its UTC time, so nothing is overwritten.
  - Each file has one row in the `reports` table of the metaform's store, STORE-043. A row with a layer id is that layer's provenance ref: reading the layer's provenance, STORE-016, returns its refs as `report`, `feedback` and `shape` with the file names.
  - Chassis verbs, CLI-031, served over MCP by the mcp module under the same names as `set`, and always on the surface, CLI-022, so narrowing never hides them:

    | Verb | Nouns | Tool | Does |
    |---|---|---|---|
    | `feedback` | text; optional `layer=`, `report=`, `shape=`, where report and shape are text, or a file path or `-` on the CLI | `feedback`: fields `text`, `layer`, `report`, `shape`, `project` | Writes the feedback, and the report and shape when given, and their rows. Returns the file names. Never refused, BASE-044. |
    | `list reports` | optional project, `kind=`, `layer=` | `list_reports` | One line per file: name, kind, layer or `-`, size, UTC time; paged, STORE-025. |
    | `read report` | file name; optional project | `read_report` | The file's text exactly, BASE-036. |
  - `intake_finish`'s `report` and `feedback` fields write the same files and rows, with the intake layer's id as run id, BASE-039.
  - The feedback file holds process feedback and trouble reports, asked for when `--debug` is on; the report file holds the project report, asked for when `--report` is on, CLI-034. The two are always separate files. What an agent submits is stored whatever the settings, BASE-044; the settings decide only what agents are asked for.
- Acceptance:
  - `intake_finish` with `report` and `feedback` writes both files under the project's reports folder, nothing in the project folder, and the intake layer's provenance read returns both as refs.
  - `feedback` with `shape` and no layer writes a feedback file and a shape file with the same run id, and `list_reports` shows both.
  - With `--modules` narrowed to one module, `feedback`, `list_reports` and `read_report` are still listed and run.
- Relates to: BASE-039, BASE-044, STORE-001, STORE-016, STORE-043, LAYER-010, CLI-022, CLI-031, MCP-004.
- Status: confirmed. File names, verb names and the table are recommended.

## Records added from the design points

### BASE-046 The chassis is fixed, and everything that plugs into it is a module
- Requirement: The chassis is the fixed part of Metaform, and everything that plugs into it is a module: authored by Metaform or by anyone, as small as one command, and never a workflow.
- What this means: A module can be anything that plugs into the chassis. The modules Metaform ships, `map`, `intake`, `memory`, `mcp`, `web`, `hello` and `template`, are modules exactly as a community author's are. A module is not a workflow; running workflows is the job of a workflow module, BASE-003. A module declares itself in its own code, BASE-035.
- Why: With one fixed part, every module relies on the same base, and any feature, shipped or not, is added, removed or replaced the same way, BASE-001. A shipped module given a special place would make the chassis depend on it and every other module second to it.
- How it shows: `metaform list modules` lists the shipped modules beside a user's own, each with its place and state, and disabling any of them leaves the chassis working.
- Build: Nothing beyond BASE-035 and BASE-037: the loader treats every module alike, shipped or not, and the chassis names no module, BASE-001.
- Acceptance: None of its own; BASE-001's and BASE-037's protect it.
- Relates to: BASE-001, BASE-003, BASE-014, BASE-019, BASE-035, BASE-037.
- Status: confirmed, 2026-09-14.

### BASE-047 Installing a wheel goes through an install stage that never downgrades
- Requirement: A wheel becomes the installed Metaform through an install stage, the front door, which never downgrades an installed Metaform without force and keeps the wheel's data apart from the installed copy's; a first-run check, the backstage, applies the same checks to a Metaform installed around the front door, such as by a raw `pip install`.
- What this means: Running a wheel directly never changes an installed Metaform, BASE-023. Installing one does, so it goes through its own stage: it refuses to put an older Metaform over a newer one unless forced, and the wheel's own data folder stays apart, pulled into the main folder only as BASE-025 says. A person or an agent can install the wheel with pip directly and skip the stage; the first run of such an install finds that the stage never ran and makes its checks then. The front door is written `python metaform.whl install` in the design; `install` is also the chassis verb that sets up AI tools, MCP-013, and a directly run wheel runs the same command line, BASE-042, so the front door's command is open, D100.
- Why: An installed Metaform's data is written at its own schema versions, and an older chassis refuses a store written by a newer one, STORE-029, so a downgrade would leave the user's data unreadable; forcing it is a deliberate act. A check made only at the front door misses every install that goes around it, so the backstage makes the same checks on the first run.
- How it shows: Open with D100.
- Build: Open, D100.
- Acceptance: Open with D100.
- Relates to: BASE-020, BASE-023, BASE-025, BASE-027, BASE-041, BASE-042, MCP-013, STORE-029.
- Status: confirmed as design, 2026-09-19. The front door's command and what the stage and the backstage check are open, D100.

### BASE-048 Metaform ships a metaform of itself, to develop itself
- Requirement: The Metaform release carries a metaform of Metaform itself, which agents developing Metaform read.
- What this means: The system ships its own metaform to develop itself. Where that metaform lives, given that a project's data lives only in the home, STORE-001, and how it reaches a user's home are open, D102.
- Why: An agent developing Metaform, or administering a fork of it, BASE-027, starts from Metaform's own recorded functional understanding instead of reconstructing it, as every project's agents do, MAP-005.
- How it shows: Open with D102.
- Build: Open, D102.
- Acceptance: Open with D102.
- Relates to: BASE-027, MAP-005, STORE-001, STORE-027.
- Status: confirmed as design, 2026-09-19. Where it lives and how it arrives are open, D102.

### BASE-049 Modules are planned whose details wait for a stable core

- Requirement: The core is built so that modules planned for later can be carried on it, and their details are not recorded here until the core is stable.
- What this means: Further modules are designed. At Rich's request their details are held back for now. What they need of the core is what CLI-037 and CLI-038 already require: a small top menu, contents reached by entering, and the working folder deciding what is shown and holding the continuity of the work.
- Why: This specification describes what is being built now. Details of later work would be read as work to do, and would send builders after features the core cannot carry yet. Stating that the modules are planned tells a builder why the core's menu and folder rules are firm, without describing what is not ready to be built.
- How it shows: No record describes these modules.
- Build: Nothing is built for them now.
- Acceptance: None needed.
- Relates to: BASE-046, CLI-037, CLI-038.
- Status: confirmed, 2026-09-27.

## Open questions

1. Answered in part: the project place is part of the design, BASE-014. Where it lives, given all data is global, is open, D93.
2. Answered: one data folder per wheel name and version, BASE-023.
3. Answered: an installed Metaform can pull a wheel's data into the main folder as its own metaforms, never merged, BASE-025.
4. The PyPI distribution name.
5. Whether `metaform install` and `metaform uninstall` are chassis verbs or belong to a module, given MCP registration is part of installing.
6. How Metaform maintains a user's fork, CI and wheel at release: which service, which commands.
7. Whether a module can call another module's public operation directly, beyond events, and through what interface.
8. Does any chassis verb run long enough to return a receipt, or do receipts belong only to the workflow module? Recommended: only the workflow module. (BASE-030)
9. Answered 2026-09-26: the intake text's response protocol says to record each object with the intake tools as it is reasoned, and a proofing step reads the whole map back before the finish; BASE-039. NEW The Canonical Intake text says to return only the final XML shape, and its method has `deliverable_format="xml"`, while the design has the intake agent build the map through Metaform's commands and tools and not by importing an XML answer. Does the intake text get a response protocol for writing through the tools, in Rich's words, with the method unchanged? Or does the agent return its XML answer through one intake tool that stores it by the MAP-040 mapping? (BASE-039, MAP-040, MCP-009)
10. NEW The grammar makes arguments nouns and switches settings. Record fields a verb writes, such as a join's purpose, are data, not settings. Is writing optional fields as `name=value` nouns, BASE-043, the form you intend, or should they be written another way?

11. Answered, D82: stored as given, BASE-039, BASE-044.
12. NEW An agent that cannot continue always stops and submits a trouble report. Is the trouble report written when `--debug` is off, or does the agent only stop? Recommended: written, since it costs nothing to keep and it records why the run ended. (BASE-044, CLI-034)
13. NEW Which CalVer format do versions take during development? D94. (BASE-020)
14. NEW What is the command of the install stage's front door, and what do the stage and the backstage check? D100. (BASE-047)
15. NEW Where does Metaform's own metaform live, and how does it reach a user's home? D102. (BASE-048)

### BASE-050 The chassis issues nonces, and a nonce is how an agent reaches its work

- Requirement: The chassis provides a nonce service that modules import. A module requests a nonce, and the nonce's record holds the identity of the module and the function in that module to call. An agent that runs `metaform <nonce>` is given its prompt and its menu. The module updates the nonce as the work moves and closes it when the task is complete.
- What this means:
  - A nonce is requested by a module, never by the chassis for itself. The record is kept in the nonce table of the base store: the nonce, the module's id, the function to call, the value the chassis passes to that function, and whether the nonce is open or closed.
  - A nonce is seven digits, and its first digit is never zero.
  - `metaform <nonce>` prints what the module's function returns for the nonce: the agent's prompt and the commands it has. `metaform <nonce> help` lists the commands the module exposes for that nonce. `metaform <nonce> <command>` runs that command: `next`, `back`, `complete`, or whatever the module's developer made.
  - The words after the nonce that name none of the module's commands are the words of the nonce's function. `metaform 6753293 next` runs the function with `next`, as `metaform <module> <function> next` would, and the nonce is reached. The function takes them through its nouns. A function that declares no nouns takes no words, and a word that names no command is refused with `metaform <nonce> help` as the next step.
  - When a command is run, the module updates the nonce through the nonce service, and the chassis holds the next command or value to send to the function.
  - Inside a command, `nonce.reached()` is the nonce the command came through, or none when the command did not come through a nonce. One verb can in this way be the module's entry, run as `metaform <module> <verb>`, and also the function its nonce calls.
  - A module closes a nonce when its task is complete. A closed nonce gives no menu and runs no command. A closed nonce and a nonce that was never issued print exactly `Error: Invalid or Unknown Nonce` and nothing else.
  - A closed nonce's record stays in the table, so its number is never issued again.
  - A nonce is a handoff. A module that hands the work on gives the agent that finished one nonce to pass to the orchestrator. The orchestrator runs it and is given a single instruction: give this new nonce to a new agent, in a worktree, an empty temporary folder, or whatever context that agent needs. The new agent runs its nonce and is given its prompt.
- Why: An agent handed one word reaches exactly its own work: its prompt, its commands and its place in them, with no menu of anything else to read or choose wrongly from. The orchestrator carries a word and follows one instruction; it never reads the workflow, chooses the next step or words the next agent's task, so the handoff holds nothing it can get wrong. The chassis keeps the record, so a module's developer writes the work and none of the tracking, and the work survives the end of a session because where it stands is in the store and not in a process. Seven digits are short for an agent to carry and repeat exactly, and with no leading zero a nonce keeps all seven digits when anything reads it as a number. A closed nonce and one never issued reach no work, and the agent holding either can do nothing with it, so both print the same line. A number is never issued twice, so a nonce left in a transcript or an old handoff can never reach work handed later to another agent. `nonce.reached()` lets a verb start the work when run directly and do the work when run through its nonce, so the module needs no second verb for it. The words after a nonce reaching its function let that one verb take each step of the work, named after the nonce, so the module needs no verb for each step.
- How it shows: A module requests a nonce and prints `metaform 6753293`. The agent runs it and reads its prompt. `metaform 6753293 help` lists `next` and `complete`. After `complete` the module closes the nonce, and `metaform 6753293` prints `Error: Invalid or Unknown Nonce`. A verb run as `metaform <module> <verb>` finds `nonce.reached()` empty and requests a nonce whose function is that same verb; run as `metaform <nonce>`, the verb finds the nonce in `nonce.reached()` and does its step. hello's `noncedemo` is such a verb: `metaform 6753293 next` reaches it with the word `next`, it keeps the step in the nonce's value so `metaform 6753293` alone gives the same message again, and `metaform 6753293 complete` closes the nonce and prints a new one to hand on.
- Build: Built. The service is `metaform.nonce`, imported by modules: `request(module, function, value=None)` issues a nonce and returns it, `read(nonce)` returns its record or none, `update(nonce, *, value=None, ef=None)` changes what its next run is sent, `close(nonce)` closes it and keeps its record, `reached()` returns the nonce the running command came through or none, and `current()` returns that nonce and stops the command when there is none. The table is in the base store, BASE-004. The command line reads a first word of seven digits whose first is not zero as a nonce unless a module has that id; no chassis command has that form. `run_nonce` in `cli.py` runs a following word that names one of the module's commands as that command, and otherwise, when the nonce's function declares nouns, runs the function with the words after the nonce.
- Acceptance: a module requests a nonce and the record names the module and its function; a nonce is seven digits and its first digit is never zero; `metaform <nonce>` prints what that function returns; `metaform <nonce> help` lists only that module's commands for the nonce; a command run through the nonce reaches the module's function with the value the chassis holds; the words after a nonce that name none of its module's commands reach its function; an update changes what the next run is sent; `nonce.reached()` is the nonce a command came through, and none for a command that did not come through one; a closed nonce and a nonce that was never issued run nothing and print exactly `Error: Invalid or Unknown Nonce`; a closed nonce's number is never issued again.
- Relates to: BASE-003, BASE-004, BASE-046, BASE-051, CLI-037, MCP-030.
- Status: confirmed by Rich, 2026-09-29. The form of a nonce, the line printed for a closed or unknown nonce, the kept records and `nonce.reached()` confirmed by Rich, 2026-09-29. The words after a nonce reaching its function added 2026-09-29, for the flow of hello's `noncedemo` Rich gave. Records of 2026-09-25 that said nonces were dropped were wrong.

### BASE-051 The workflow module orchestrates agents deterministically

- Requirement: The workflow module ingests a workflow, which can be any prompt, and runs it as a chain of prompts handed from agent to agent. An ingested prompt is saved as `<prompt name>.metaform`, tagged to show each handoff and what data is passed back and accepted by the module, so the next step can be handed to the next agent.
- What this means:
  - An agent analyzes the prompt and splits it up. `metaform workflow import` gives that agent the instructions for tagging and importing a workflow.
  - The tags mark the prompt where it stands. The words of the prompt are its author's and are not reworded.
  - Work is handed on by nonce, BASE-050. When the work of a step comes back, the module closes that agent's nonce and gives it one nonce to pass to the orchestrator. The orchestrator runs it and is given a single instruction: the nonce of the next agent, and the context to start that agent in, a worktree, an empty temporary folder, or whatever the step needs. The tags of a step say which context that is.
  - The chassis starts no agent and runs no workflow, BASE-003. The host's agents do the work, and the module keeps the order.
- Why: A prompt that names several roles and an order of work is followed loosely when one agent holds all of it, and differently on each run. Handing each step to its own agent, in the order the tags fix, makes the run the same each time, and each agent reads only its own step. Keeping the author's words keeps the prompt the thing that was written, and the tags say only where it divides.
- How it shows: An agent runs `metaform workflow import` and reads how to tag. It tags `metaprompt.md`, and the module saves `metaprompt.metaform`. The orchestrator chooses the workflow and is given a nonce. It runs it and reads: start a new agent in an empty folder and have it run `metaform 6753293`. That agent finishes and passes a nonce back, and the orchestrator runs that one for its next instruction.
- Build: Open. The module is made from a copy of the template module, BASE-019. The tags, the form of the `.metaform` file, where it is kept, the commands of a step, and how a prompt that returns to an earlier step is tagged are not decided. What an agent sends back is stored as sent and never refused for its content, BASE-044.
- Acceptance: Open. With the tags removed, a `.metaform` file is its prompt byte for byte.
- Relates to: BASE-003, BASE-019, BASE-044, BASE-046, BASE-050, LAYER-017, MCP-030.
- Status: confirmed by Rich, 2026-09-29, in its requirement; the build is open. The workflow module of the earlier runtime was removed on 2026-09-21 in error and is kept at the tag `before-dead-code-removal`; this module is made again and does not restore it.

