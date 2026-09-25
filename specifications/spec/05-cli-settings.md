# 05. CLI and settings

This section specifies the metaform command line grammar, help, errors, and the settings system that every switch belongs to.
It covers the chassis commands and the rules every module command follows; MCP reuses the same declarations and is specified in its own section.

Current code referenced here: `src/metaform/settings.py`, `cli.py`, `docs.py`, `module.py` on branch `chassis`. The settings pattern follows mvm's `scripts/commcube_config/schema.py` and `cli.py`.

## Grammar

### CLI-001 Commands are verbs, arguments are nouns, switches are adverbs
- Requirement: every metaform command line reads as a verb, the nouns it acts on, and switches that change how it runs.
- What this means: the first word after `metaform` is a chassis verb (`help`, `add`, `list`, `set`, `unset`, `config`, `enable`, `disable`, `install`, `build`, `import`, `export`, `query`) or a module id followed by that module's verb. Words that name what the verb acts on are arguments. Words starting with a dash change how the verb runs and never name what it acts on.
- Why: one consistent grammar makes every command predictable for people and agents, so a user who knows one command can guess the next, and an agent does not have to read source to find out how to call something.
- How it shows: `metaform add project mgm ~/mgm-main` (verb add, nouns project, mgm, path). `metaform template greet world --loud` (module template, verb greet, noun world, adverb --loud).
- Build: the parser takes `argv[0]` as the verb; if it is not a chassis verb it is looked up as a module id and `argv[1]` as that module's verb. Remaining words are split into arguments and switches by CLI-004. Module verbs declare their nouns and switches in `Verb`; the parser rejects an unknown switch with one Next line.
- Acceptance: a module verb given a noun and a declared switch receives the noun in `nouns` and the switch in its switches; an undeclared switch fails with exit code 2 and a Next line naming `metaform <module> <verb> --help`.
- Relates to: CLI-004, CLI-005, BASE-002, BASE-006, MCP-003.
- Status: confirmed. Whether `install` is a chassis verb or a module's verb is open, per BASE open question 5.

### CLI-002 `all` is an argument
- Requirement: `all` is an argument wherever a verb can act on every item, and `--all` is never a switch.
- What this means: `all` is a pronoun standing for every item the verb can act on, so it takes the place of a noun. A command that accepts named items accepts `all` in the same position.
- Why: a switch changes how a verb runs; `all` changes what the verb acts on, which is the job of an argument. Using it the same way everywhere keeps the grammar consistent.
- How it shows: `metaform unset all`, `metaform install all`. `metaform unset --all` fails: `Error: --all is not a switch. all is an argument.` `Next: metaform unset all`.
- Build: verbs that act on sets of items treat the literal word `all` as the whole set. The parser rejects `--all` with the Next line pointing at the argument form. The current `unset` already does this; its error text changes from "not a setting" to "not a switch".
- Acceptance: `metaform unset --all` exits 2 with Next `metaform unset all`; `metaform unset all` resets every unglued setting.
- Relates to: CLI-004, CLI-017.
- Status: confirmed.

### CLI-003 `--` ends switch parsing
- Requirement: on every command, `--` ends switch parsing, and every word after it is an argument.
- What this means: a name that starts with a dash, or collides with a word the command gives special meaning, can still be passed as a plain argument after `--`.
- Why: it is the standard command line convention for this, and users who know git or rm expect it.
- How it shows: `metaform install -- all` sets up a tool literally named `all`. `metaform add project -- -scratch ./scratch` registers a project named `-scratch`.
- Build: the shared parser stops classifying words at the first `--` and passes all later words through as arguments, also suppressing keyword meaning such as `all`. The current chassis parsers (`set_`, `unset`, `run_module`) do not handle `--`; the change adds it once in the shared parser that all verbs use.
- Acceptance: a word after `--` that starts with `--` arrives as an argument, not a switch; `all` after `--` is not expanded.
- Relates to: CLI-001, CLI-002.
- Status: confirmed.

### CLI-004 Long switches take two dashes, single letters take one
- Requirement: a long switch is `--` followed by its full name, and a single-letter short form takes one dash.
- What this means: switch names are full words separated by hyphens, derived from the setting key (`tmux_panes` becomes `--tmux-panes`). A short form such as `-q` or `-h` is a single letter with one dash and is an alias of one long switch.
- Why: long names say what they do, and single letters stay short for the few switches typed constantly, matching normal command line conventions.
- How it shows: `metaform set --quiet` and `metaform set -q` do the same thing. `metaform help -h` is the same as `metaform help --help`.
- Build: the schema records the long switch and an optional one-letter short form per setting. Value switches accept `--name value` and `--name=value`. The parser rejects a single-dash word longer than one letter.
- Acceptance: `-q` and `--quiet` produce identical behavior; `-quiet` fails with a Next line naming `--quiet`.
- Relates to: CLI-010, CLI-011, CLI-015.
- Status: confirmed.

## Status and help

### CLI-005 `metaform` alone shows status
- Requirement: `metaform` with no words shows the status of the home, the folder, the project, and the modules.
- What this means: status lists the Metaform version, the home path, the current folder, the folder's project and whether it was selected here or inherited, the number of registered projects, how many modules are on and which failed to load, and the command surface when it is narrowed. When something needs doing, status ends with one next step.
- Why: the first thing a user or agent needs is where they are and what Metaform will act on; status answers that without a subcommand to remember.
- How it shows:
  ```
  Metaform 0.1.0
  Home: /home/rich/.metaform
  Folder: /home/rich/mgm-main
  Project: mgm (/home/rich/mgm-main)
  Projects: 2 registered
  Modules: 3 on
  ```
  With no project: `Project: none` then `  Register one: metaform add project <id> <path>`.
- Build: exists as `status()` in `cli.py`. It remains a chassis function and gains the intake state line specified in the agent instructions section.
- Acceptance: in an unregistered folder, status exits 0 and names `metaform add project <id> <path>`; in a registered folder, it names that project.
- Relates to: CLI-020, CLI-021, CLI-022, MCP-009.
- Status: confirmed.

### CLI-006 `metaform help` is a brief overview ending with tips
- Requirement: `metaform help` prints a brief overview of common commands that ends with tips pointing to the intro, the commands index, the switches index, and `config --show`.
- What this means: the overview is one screen. It names what Metaform does in one line, lists a few common commands, and ends with tips. It never lists every command.
- Why: a brief first screen is readable, and the tips lead to the full indexes when they are needed.
- How it shows: the current `docs.overview()` output, ending with:
  ```
  Tips:
    - start here: metaform help intro
    - run 'metaform help commands' for an index of all commands
    - run 'metaform help switches' for all switches
    - run 'metaform config --show' to inspect your saved defaults.
  ```
- Build: exists as `docs.overview()`. Its heading line drops the em dash.
- Acceptance: the overview includes each of the four tip commands and fits in 24 lines.
- Relates to: CLI-007, CLI-008.
- Status: confirmed.

### CLI-007 `help <thing>` is the man page; `--help` and `-h` give syntax
- Requirement: `metaform help <thing>` prints the full page for a command, module, verb or switch, and `<thing> --help` or `-h` prints only its syntax.
- What this means: the page has the summary, description, usage lines, switches, details, examples and related topics. The syntax form has the usage lines and switch names only.
- Why: understanding and typing are two needs; the page serves understanding and the syntax serves typing, and merging them fails both.
- How it shows: `metaform help set` prints the page; `metaform set --help` prints `metaform set --<setting> <value> [--glue] [--quiet]` and the switch list. `metaform help template greet` prints the verb page; `metaform template greet -h` prints its syntax.
- Build: exists in `docs.py` (`page`, `syntax`, `module_page`, `verb_page`, `module_syntax`, `verb_syntax`, `switch_page`). All pages are generated from the live declarations of the chassis and the loaded modules, never from static text.
- Acceptance: `help set` includes the examples block and `set --help` does not; a newly declared module verb appears in `help <module>` with no help text written anywhere else.
- Relates to: CLI-008, BASE-006, CLI-010.
- Status: confirmed.

### CLI-008 `help commands` and `help switches` are the indexes
- Requirement: `metaform help commands` lists every command on the folder's surface, and `metaform help switches` lists every switch with the commands that use it.
- What this means: the commands index groups chassis verbs and each module's verbs, each with a one-line summary. The switches index lists every setting switch and every verb control switch.
- Why: an index lets a user or agent find any command or switch in one read without guessing names.
- How it shows: `metaform help commands` shows `chassis` then each module group; hidden groups do not appear.
- Build: exists as `docs.commands_index(shown)` and `docs.switches_index()`. The switches index is generated from the settings schema plus verb control switches.
- Acceptance: after `metaform set --commands template`, `help commands` lists no chassis-only verbs except the ones always shown; a module declared setting appears in `help switches`.
- Relates to: CLI-010, CLI-022.
- Status: confirmed.

### CLI-009 Every error ends with exactly one Next line
- Requirement: every error prints what happened and exactly one `Next:` line naming the command to run next.
- What this means: errors go to stderr as `Error: <what happened>` followed by `Next: <one command>`, with exit code 2. There is never zero or more than one Next line.
- Why: an error that names the next command keeps an agent on the command line and out of the source, where it starts guessing at the design.
- How it shows:
  ```
  Error: --colour is not a setting.
  Next: metaform help switches
  ```
- Build: exists as `Stop(message, next_step)` in `module.py` and the handler in `cli.main`. `Stop` requires `next_step`; the change makes it a required argument so an error without a next step cannot be raised.
- Acceptance: every error path exercised by the CLI tests prints exactly one `Next:` line; raising `Stop` without a next step fails at the call site.
- Relates to: CLI-020, BASE-011, MCP-006, STORE-026.
- Status: confirmed.

## Settings

### CLI-010 One schema drives every surface
- Requirement: one settings schema lists every setting and drives parsing, validation, defaults, help, `config --show` and the settings screen.
- What this means: each setting is declared once, by the chassis or by a module in its own code. Every surface reads that one declaration, so no surface keeps its own list.
- Why: a module author writes settings once and never touches CLI or screen plumbing, and the switches, help and screen cannot drift apart.
- How it shows: a module that declares `settings.number('panes', 4, ...)` immediately gets `metaform set --panes 6`, `metaform unset --panes`, an entry in `help switches`, a line in `config --show`, and a row in the settings screen.
- Build: each schema entry holds `key`, `default` (a real declared value, or `default_from` for a value computed from the folder), `kind` (`str`, `int`, `bool`, `list`, `select`), `group` (the owning module id or chassis area), `label` (short name for the screen), `help` (one line), `details` (the longer explanation), `switches` (the long form and, for booleans, the `--no-` form, spelled out), `short` (optional one letter), `choices` (list or function, for selects), `min` and `max` (for numbers), `scope`, and `owner`. The current `Setting` dataclass has key, default, help, kind, choices, scope, owner, details and default_from; the change adds `group`, `label`, `switches`, `short`, `min` and `max`, and makes `switches` explicit rather than derived.
- Acceptance: a setting declared in a test module appears with the same default and help in `config --show --json`, in `help switches`, and is accepted by `set`; a second declaration of the same key by another owner fails at load.
- Relates to: CLI-011, CLI-012, BASE-008, QUAL-004.
- Status: confirmed.

### CLI-011 Every long switch is a setting
- Requirement: every long switch that changes how commands run is a setting, so it can be passed on one call, stored with `set`, cleared with `unset`, and protected with `--glue`.
- What this means: passing a switch on a command affects that call only. `set` stores the value for the folder. `unset` clears the stored value. `--glue` protects the stored value from `unset all`. `unset all --unglue` returns every setting, glued ones included, to its safe default.
- Why: any behavior a user can ask for once, they can also make their standing choice, with no second mechanism for configuration.
- How it shows: `metaform template greet world --loud` shouts once. `metaform set --loud` makes every later greet shout. `metaform unset --loud` returns to the default.
- Build: when a command runs, each setting's effective value resolves in this order: the switch on this call, then the stored value at the nearest folder at or above the current folder, then the declared default. Verb control switches that only steer a chassis command (`--glue`, `--unglue`, `--show`, `--json`, `--quiet`, `--help`) are listed in the open questions. The change: module switches become settings (CLI-012), and per-call values join the resolution order.
- Acceptance: with a stored value of off and `--loud` passed on one call, that call shouts and `config --show` still shows off afterward; with no stored value, the declared default applies.
- Relates to: CLI-012, CLI-013, CLI-014, CLI-016.
- Status: confirmed.

### CLI-012 Module switches are declared once and are settings
- Requirement: a module declares each of its switches once, and that declaration is both the verb's switch and a setting.
- What this means: a module switch such as `--loud` is a setting owned by the module. The verb lists which settings it reads, and the parser accepts those settings as switches on that verb.
- Why: one declaration keeps a module's switches, settings and help in step, and makes every module switch storable with `set` the same way chassis switches are.
- How it shows: the template declares `--loud` once; `metaform template greet world --loud` and `metaform set --loud` both work, and `help --loud` names the template as owner.
- Build: `Adverb` in `module.py` is replaced by a reference from `Verb` to setting keys declared through `metaform.settings`. The verb's context gives effective values by key, which already exists as `Context.setting(key)`. The current template declares `--loud` as an `Adverb`, separate from settings; that changes.
- Acceptance: `metaform set --loud` succeeds for a module that declares `loud`, and the verb then behaves as if `--loud` were passed.
- Relates to: CLI-010, CLI-011, BASE-006, BASE-007, MCP-005.
- Status: recommended.

### CLI-013 Settings have three states: default, set, glued
- Requirement: every setting is in one of three states: default, set, or glued.
- What this means: default means nothing is stored for it, so its value is the declared default. Set means a value is stored and `unset all` clears it. Glued means a value is stored and `unset all` keeps it. A default is a real value, such as 4 nodes or true.
- Why: glue lets a user keep a baseline through a reset, while everything else returns to the working defaults.
- How it shows: `config --show` prints each setting with its value and a state note: nothing for default, `(set)`, or `*` and `(glued)`.
- Build: exists in `settings.py` (`state`, `glue`, `reset`) and the home database's saved and glued tables.
- Acceptance: `set --x v --glue` then `unset all` keeps v; `unset all --unglue` returns x to its declared default and state default.
- Relates to: CLI-014, CLI-016, CLI-017.
- Status: confirmed.

### CLI-014 A stored setting belongs to a folder and its subfolders
- Requirement: `set` stores a folder setting for the folder it runs in, and that value applies to every folder below it until a deeper folder sets its own.
- What this means: the effective stored value for a folder is the one stored at the nearest folder at or above it.
- Why: agents run in many folders and worktrees inside one project; a setting made at the project root reaches all of them without being repeated.
- How it shows: `cd ~/mgm-main && metaform set --commands workflow` then `cd ~/mgm-main/src && metaform config --show` shows commands workflow.
- Build: exists as `settings._scope`, walking the folder and its parents for a saved or glued value. All values live in the home database under ~/.metaform; nothing is written into the folder.
- Acceptance: a value set in a parent is effective in a child; a value set in the child overrides it for the child only.
- Relates to: CLI-021, STORE-001, STORE-002.
- Status: confirmed.

### CLI-015 Booleans have two forms and never toggle
- Requirement: every boolean setting has exactly two switch forms, `--name` for true and `--no-name` for false, and neither form toggles.
- What this means: the schema spells out both forms. Passing a form states its value; passing `--name` when the value is already true changes nothing. Parsing gives three cases: `--name`, `--no-name`, or not given. Not given leaves the setting unchanged.
- Why: a boolean's default can be true or false, so each boolean needs one form to depart from its default and the other to return. A glued value is inverted with the opposite form. Treating not given as false would silently switch booleans off whenever any other setting is set.
- How it shows: `metaform set --no-tmux` stores false. `metaform lab --no-tmux` runs one call without tmux while a glued `--tmux` stays stored. `metaform set --tmux` twice leaves it true.
- Build: the parser registers both forms for each boolean, with not given parsed as no value (None), `--name` as true and `--no-name` as false. `unset --name` and `unset --no-name` both clear the stored value. The current chassis takes `set --name on|off` and treats a bare `--name` as on, with no `--no-name` form; that changes to the two forms.
- Acceptance: `set --a-setting` then `set --b-setting value` leaves a-setting true; `set --no-name` stores false; `--name` on one call over a stored false gives true for that call and leaves false stored.
- Relates to: CLI-011, CLI-016, MCP-005.
- Status: confirmed.

### CLI-016 A glued value inverts with the opposite form
- Requirement: `set` with the opposite form changes a glued value and it stays glued.
- What this means: glue protects a stored value from `unset all`; it does not lock the value. `set` always changes it. `unset --name` alone skips a glued setting; `unset --name --unglue` clears it and removes the glue.
- Why: glue records the user's standing choice, and the user must be able to change that choice without first unwinding it.
- How it shows: `set --tmux --glue`, then `set --no-tmux` gives false, glued; `unset all` keeps false.
- Build: exists: `settings.assign` writes regardless of glue and leaves glue unchanged. `reset` skips glued keys unless `unglue`.
- Acceptance: after the sequence above, state is glued and value false; `unset --tmux` reports skipped (glued).
- Relates to: CLI-013, CLI-015, CLI-017.
- Status: confirmed.

### CLI-017 `unset all --unglue` always returns to the safe defaults
- Requirement: `unset all` returns every unglued setting in scope to its default, and `unset all --unglue` also clears and unglues glued settings, leaving every setting at its declared default.
- What this means: the declared defaults are safe working values, so `unset all --unglue` always lands on a working configuration.
- Why: a user or agent can always get back to a known good state in one command, whatever was set or glued before.
- How it shows: `metaform unset all` prints `Reset N setting(s): ...` and `Skipped (glued): ...`. `metaform unset all --unglue` prints the reset list and `Unglued: ...`.
- Build: exists as `cli.unset`. Scope of `all` is listed in the open questions.
- Acceptance: after arbitrary set and glue operations, `unset all --unglue` leaves `config --show --json` with every state `default`.
- Relates to: CLI-002, CLI-013, CLI-022.
- Status: confirmed.

### CLI-018 `--confirm` is never a setting
- Requirement: `--confirm` is accepted only as a one-call switch on caution verbs, and it can never be set, stored or glued.
- What this means: a verb declared with a caution does nothing without `--confirm` on the same call. The error names the exact command with `--confirm` appended.
- Why: `--confirm` guards destructive verbs. Stored or glued, it would silently approve every deletion from then on.
- How it shows:
  ```
  Error: This deletes the greeting history.
  Next: If you are sure: metaform template forget --confirm
  ```
  `metaform set --confirm` fails with `Error: --confirm is not a setting.` and a Next line naming `metaform help --confirm`.
- Build: exists in `run_module` (`verb.caution`). The settings schema rejects the key `confirm` at declaration.
- Acceptance: `set --confirm` exits 2; a caution verb without `--confirm` exits 2 and changes nothing.
- Relates to: CLI-011, BASE-013, MCP-006.
- Status: confirmed.

### CLI-019 Select settings take choices from a list or from module data
- Requirement: a select setting takes its choices either from a fixed list in code or from a function that reads the owning module's data at the time of use.
- What this means: the workflow setting, for example, offers the workflows its module has stored. An invalid choice fails with the current choices listed.
- Why: a module can offer choices it authored itself, and the choices stay current without redeclaring the setting.
- How it shows: `metaform set --favorite zed` fails with `Error: --favorite has no choice 'zed'. Choices: world, rich.` and a Next line naming `metaform help --favorite`.
- Build: exists as `settings.choice(key, choices=list|callable)`. The function reads through the chassis data access object once module data moves there.
- Acceptance: after the module stores a new item, `set` accepts it as a choice with no redeclaration.
- Relates to: CLI-010, STORE-022.
- Status: confirmed.

### CLI-020 Metaform works with zero configuration
- Requirement: out of the box, the declared defaults are the working settings, and Metaform and every module work with no configuration.
- What this means: no setting has to be set before any command works. Settings tune a working system.
- Why: low-friction start for users and agents; nothing blocks the first command.
- How it shows: a fresh home with no saved settings runs `metaform`, `metaform help`, and every enabled module verb.
- Build: every declared setting has a working default or a `default_from`. A module whose setting cannot have a working default is refused at load with a Next line.
- Acceptance: with an empty home, every chassis verb and the template's verbs run with exit 0 given valid nouns.
- Relates to: CLI-010, CLI-017.
- Status: confirmed.

## Context and the command surface

### CLI-021 Working context is made of ordinary folder settings
- Requirement: the working context is three folder settings: `--project`, `--workflow` and `--commands`.
- What this means: `--project` defaults to the registered project that contains the folder. `--workflow` names the active workflow, with choices from the workflow module's data. `--commands` lists the command groups on the folder's surface; empty means all.
- Why: context as settings needs no extra machinery, and it is visible and reversible like any setting.
- How it shows: `metaform set --workflow intake --commands workflow,memory`. `metaform` status shows the project and the narrowed commands.
- Build: `project` and `commands` exist in `settings.py`. `workflow` is declared by the workflow module as a select, not by the chassis, since the chassis does not run workflows.
- Acceptance: in a subfolder of a registered project with nothing set, `--project` is that project; `unset --project` returns to it.
- Relates to: CLI-014, CLI-022, STORE-002, MCP-011.
- Status: confirmed.

### CLI-022 Narrowing the command surface hides and blocks, and states the way back
- Requirement: commands outside the folder's command surface are neither shown nor run, on the CLI or over MCP, and the `set` that narrows the surface states the exact way back.
- What this means: help indexes, help pages and MCP tool lists omit hidden groups, and a hidden command fails with a Next line. The narrowing `set` prints which commands remain and the way back.
- Why: removing commands from the surface holds even for agents with full permissions, where host permissions do not. The orchestrator that narrowed the surface holds the exact way back and acts with confidence; a subagent meets only the caution. The wording steers, and nothing gates inference.
- How it shows:
  ```
  Success: updated 1 key
    commands: all → workflow,memory
  Commands shown here: workflow, memory.
  All other commands and help, including yours, are now hidden and will not run.
  To restore them: metaform abort intake --confirm
  ```
- Build: exists as `cli.shown`, `ALWAYS`, and `mcp_server._surface`. The current way back text is `metaform unset --commands`; the design states `metaform abort <workflow> --confirm` when a workflow narrowed the surface. What remains always shown is listed in the open questions.
- Acceptance: after narrowing to one module, a chassis verb outside the surface exits 2 and is absent from `help commands` and from the MCP tool list.
- Relates to: CLI-008, CLI-021, MCP-004, BASE-016.
- Status: confirmed for hiding and blocking; the way-back text depends on open questions 5 and 8.

### CLI-023 Defaults are never written, and a changed default never replaces a stored value

- Requirement: A setting at its default has nothing stored, so a new release's default reaches it, while stored and glued values are never overwritten by a default.
- What this means: The default state means no row exists; the value is read from the schema each time. When a release changes a default, every folder still at default follows the new one, and every folder that set or glued a value keeps it. Values stored for keys this release does not know, such as settings added by another compatible release, are kept untouched. Reading settings any number of times writes nothing.
- Why: Filling config files with defaults freezes old defaults into place and makes an upgrade quietly overwrite what users chose. Storing only what a user chose keeps both their choices and new defaults correct.
- How it shows: After upgrading, `metaform config --show` shows new defaults where nothing was set, and every set or glued value unchanged.
- Build: Settings are stored only by set and glue. There is no hydration step that writes defaults. Stored rows whose key is not in the current schema are kept and ignored for display.
- Acceptance:
  1. Changing a setting's declared default changes its value in a folder where it was never set, and leaves it unchanged in a folder where it was set.
  2. A stored row for an unknown key survives `unset all` run by a release that does not declare it.
- Relates to: CLI-010, CLI-013, CLI-017, STORE-021.
- Status: confirmed.

### CLI-024 A module's settings survive while the module is absent

- Requirement: Disabling, removing and later restoring a module keeps its stored and glued settings, and its settings disappear from every surface while it is absent and return with it.
- What this means: A module's settings belong to it. When it is disabled or removed, its switches are not accepted, and set, unset, help, `config --show` and the settings screen do not show them. The stored values and glue stay in the base database. When the module comes back, its settings come back exactly as they were.
- Why: Turning a module off to troubleshoot, or reinstalling it, must not cost a user the settings they built up.
- How it shows: Disable a module, confirm its switches are gone from help, enable it again, and its glued values are still glued.
- Build: A stored setting is keyed by its owner and key, so a later module cannot take over another module's stored value by declaring the same key. Only settings whose owner is enabled are shown or accepted. Whether `unset all` touches an absent module's stored values is open; the recommendation is that it does not.
- Acceptance:
  1. A glued module setting is still glued, with the same value, after the module is disabled and enabled again.
  2. While the module is disabled, its switch is refused with a Next line.
- Relates to: BASE-017, CLI-013, CLI-017, STORE-002.
- Status: confirmed; open for `unset all` and absent modules.

### CLI-025 Everything works without prompts

- Requirement: Every operation that can be fully specified with arguments and switches works with no prompt, and structured output stays separate from diagnostics.
- What this means: Prompts and screens are conveniences for people. Anything a prompt asks can also be given on the command line, so scripts and agents run every operation unattended. When a command is run without a terminal and something it needs is missing, it stops with an error and one Next line rather than waiting for input. Structured output, such as `--json`, goes to standard output alone; messages, warnings and errors go to standard error.
- Why: Agents and scripts cannot answer prompts. A command that hangs waiting for input, or that mixes messages into its JSON, breaks every automated use.
- How it shows: `metaform install claude` sets up Claude Code with no questions. `metaform config --show --json | ` parses cleanly while errors still reach the terminal.
- Build: A command prompts only when standard input is a terminal and a needed value was not given. `--json` output is written to standard output only; all other text goes to standard error when `--json` is used.
- Acceptance:
  1. Running install with named tools and no terminal attached completes without reading standard input.
  2. `config --show --json` output parses as JSON even when a warning is printed.
- Relates to: CLI-009, CLI-010, MCP-014.
- Status: confirmed; failing instead of prompting without a terminal is recommended.

### CLI-026 The settings screen

- Requirement: `metaform config` opens a keyboard-driven screen for inspecting and changing settings and modules, with staged changes that are saved or discarded.
- What this means: The screen lists the chassis and each module as groups. For each setting it shows its value, its state of default, set or glued, and its help. A user edits values, resets one setting or a group, glues or unglues, and enables or disables modules. Changes are staged until saved, can be previewed first, and quitting with unsaved changes offers save, discard or continue. The screen is driven by the same schema as the CLI, so it shows exactly the settings and states the CLI shows. It applies to the folder it was opened in.
- Why: People tune a working system faster on one screen than through many commands. Staging with a preview means nothing changes by accident.
- How it shows: `metaform config` opens the screen; S saves, P previews, Q offers save, discard or continue.
- Build: The screen is the current `tui.py` salvaged onto the settings API. It reads and writes only through the settings module and `enable` and `disable`, never the database directly. Booleans take their two values, and reset returns a setting to its default state.
- Acceptance:
  1. A value staged in the screen and then discarded leaves the stored settings unchanged.
  2. A value saved in the screen reads back the same through `metaform config --show`.
- Relates to: CLI-010, CLI-013, CLI-015, BASE-017.
- Status: confirmed.

## Open questions

1. Scope of settings: every context setting is per folder. Do some settings stay global (applying in every folder), as the chassis `Setting.scope` allows today, and which?
2. Verb control switches: `--glue`, `--unglue`, `--show`, `--json` and `--quiet` steer chassis commands rather than change what a command does. Are they exempt from being settings, alongside `--confirm`, or is `--quiet` a setting?
3. Switch aliases: mvm's schema lists more than one long form for some settings (`--target-profile` and `--profile`, `--host-bridge-isolation` and `--hbi`). Does a setting get exactly one long form, or may it list aliases?
4. Boolean with a value: should `--name=false` be accepted, or does a boolean only take its two bare forms?
5. Way back from narrowing: when the surface is narrowed by `set --commands` with no workflow active, what is the way back line, and which commands remain always shown (today help, set, unset, config and mcp)?
6. Scope of `unset all`: does it reset only the settings stored at the current folder, or also the values it inherits from parent folders and any global settings?
7. Module switches as settings: what scope does a module switch get when stored with `set`: folder, like context settings, or global?
8. `metaform abort <workflow> --confirm` is written as a chassis verb, but the chassis does not run workflows (BASE-003) and module verbs take the module id first (CLI-001). Is `abort` a chassis verb, or the workflow module's verb, written `metaform workflow abort <workflow> --confirm`?
9. When a module is absent, does `unset all` leave its stored settings untouched? Recommended: yes. (CLI-024)
