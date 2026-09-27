# 05. CLI and settings

This section specifies the metaform command line grammar, help, errors, and the settings system that every switch belongs to.
It covers the chassis commands and the rules every module command follows; MCP reuses the same declarations and is specified in its own section.

Current code referenced here: `src/metaform/settings.py`, `cli.py`, `docs.py`, `module.py` on branch `chassis`. The settings pattern follows mvm's `scripts/commcube_config/schema.py` and `cli.py`.

## Grammar

### CLI-001 Commands are verbs, arguments are nouns, switches are adverbs
- Requirement: every metaform command line reads as a verb, the nouns it acts on, and switches that change how it runs.
- What this means: the first word after `metaform` is a chassis verb (`help`, `add`, `list`, `set`, `unset`, `config`, `enable`, `disable`, `activate`, `install`, `uninstall`, `build`, `import`, `export`, `query`, `feedback`, `read`, `extract`, `prompts`, `prompt`, `clear`) or a module id followed by that module's verb. `mcp` is not a chassis verb; the MCP server is `metaform mcp serve`, MCP-001. Words that name what the verb acts on are arguments. Words starting with a dash change how the verb runs and never name what it acts on.
- Why: one consistent grammar makes every command predictable for people and agents, so a user who knows one command can guess the next, and an agent does not have to read source to find out how to call something.
- How it shows: `metaform add project mgm ~/mgm-main` (verb add, nouns project, mgm, path). `metaform helloworld greet world --loud` (module template, verb greet, noun world, adverb --loud).
- Build: the parser takes `argv[0]` as the verb; if it is not a chassis verb it is looked up as a module id and `argv[1]` as that module's verb. Remaining words are split into arguments and switches by CLI-004, optional nouns are read by BASE-043, and `--` ends switch parsing, CLI-003. Module verbs declare their nouns and switches in `Verb`, BASE-035; the parser rejects an unknown switch, a missing required noun, or an extra word with one Next line naming `metaform <module> <verb> --help`.
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
- How it shows: `metaform install -- all` sets up a tool literally named `all`. `metaform memory add-observations element:code.radio -- "-40 dBm is the weakest usable signal."` stores an observation that begins with a dash, BASE-040, where without `--` the parser would reject `-40` as a switch.
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
- Build: a chassis function. Its exact lines are CLI-028.
- Acceptance: in an unregistered folder, status exits 0 and names `metaform add project <id> <path>`; in a registered folder, it names that project.
- Relates to: CLI-020, CLI-021, CLI-022, MCP-009.
- Status: confirmed.

### CLI-006 `metaform help` is a brief overview ending with tips
- Requirement: `metaform help` prints a brief overview of common commands that ends with tips pointing to the intro, the commands index, the switches index, and `config --show`.
- What this means: the overview is one screen. It names what Metaform does in one line, lists a few common commands, and ends with tips. It never lists every command. All help text, here and on every help page, is brief, uses one consistent term for each thing, and is plain, competent English: no pages of text and no filler.
- Why: a brief first screen is readable, and the tips lead to the full indexes when they are needed.
- How it shows: the current `docs.overview()` output, ending with:
  ```
  Tips:
    - start here: metaform help intro
    - run 'metaform help commands' for an index of all commands
    - run 'metaform help switches' for all switches
    - run 'metaform config --show' to inspect your saved defaults.
  ```
- Build: the overview is exactly these lines, with `<version>` filled in:
  ```
  Metaform <version>: gives agents a project's purpose before they work on it.

  Common commands
    metaform                          Show status: home, folder, project.
    metaform add project <id> <path>  Register a project.
    metaform config                   Open the settings screen.
    metaform set --<setting> <value>  Save a setting.

  Tips:
    - start here: metaform help intro
    - run 'metaform help commands' for an index of all commands
    - run 'metaform help switches' for all switches
    - run 'metaform config --show' to inspect your saved defaults.
  ```
  Column alignment pads the left column to its widest entry plus two spaces. `metaform help intro` prints exactly:
  ```
  Metaform keeps a map of what each part of a project is for: which element receives
  from which, why, and how. Agents read the map before they work, so they start from
  the project's purpose instead of rebuilding it.

  All data lives in the Metaform home, <home>. Nothing is written into your projects.

  Start:
    metaform add project <id> <path>   Register a project.
    metaform install                   Set up your AI tools to use Metaform.
    metaform                           See status and the next step.
  ```
  with `<home>` filled in.
- Acceptance: the overview includes each of the four tip commands and fits in 24 lines.
- Relates to: CLI-007, CLI-008.
- Status: confirmed.

### CLI-007 `help <thing>` is the man page; `--help` and `-h` give syntax
- Requirement: `metaform help <thing>` prints the full page for a command, module, verb or switch, and `<thing> --help` or `-h` prints only its syntax.
- What this means: the page has the summary, description, usage lines, switches, details, examples and related topics. The syntax form has the usage lines and switch names only.
- Why: understanding and typing are two needs; the page serves understanding and the syntax serves typing, and merging them fails both.
- How it shows: `metaform help set` prints the page; `metaform set --help` prints `metaform set --<setting> <value> [--glue] [--quiet]` and the switch list. `metaform help helloworld greet` prints the verb page; `metaform helloworld greet -h` prints its syntax.
- Build: the page and syntax layouts are CLI-029. All pages are generated from the live declarations of the chassis and the loaded modules, never from static text.
- Acceptance: `help set` includes the examples block and `set --help` does not; a newly declared module verb appears in `help <module>` with no help text written anywhere else.
- Relates to: CLI-008, BASE-006, CLI-010.
- Status: confirmed.

### CLI-008 `help commands` and `help switches` are the indexes
- Requirement: `metaform help commands` lists every command on the folder's surface, and `metaform help switches` lists every switch with the commands that use it.
- What this means: the commands index groups chassis verbs and each module's verbs, each with a one-line summary. The switches index lists every setting switch and every verb control switch.
- Why: an index lets a user or agent find any command or switch in one read without guessing names.
- How it shows: `metaform help commands` shows `chassis` then each module group; hidden groups do not appear.
- Build: the commands index prints `Commands` and one row per chassis verb on the surface, then for each surfaced module a heading `<id>: <summary>` and one row per verb, `<id> <verb>` and its summary, then `Use 'metaform help <command>' or 'metaform help <module> <verb>' for details.` The switches index prints `Switches` and one row per setting switch and per verb control switch, sorted, then `Use 'metaform help <switch>' for details.` Both are generated from the declarations, CLI-029.
- Acceptance: after `metaform set --modules helloworld`, `help commands` lists no chassis-only verbs except the ones always shown; a module declared setting appears in `help switches`.
- Relates to: CLI-010, CLI-022.
- Status: confirmed.

### CLI-009 Every error ends with exactly one Next line
- Requirement: every error prints what happened and exactly one `Next:` line naming the command to run next.
- What this means: errors go to stderr as `Error: <what happened>` followed by `Next: <one command>`, with exit code 2. There is never zero or more than one Next line. The other exit codes are in BASE-031: 1 for an unexpected failure, 3 for cancelled, 130 for interrupted.
- Why: an error that names the next command keeps an agent on the command line and out of the source, where it starts guessing at the design.
- How it shows:
  ```
  Error: --colour is not a setting.
  Next: metaform help switches
  ```
- Build: `Stop(message, next_step)`, BASE-035, and the handler in `cli.main` that prints the two lines and returns 2. `next_step` is a required argument, so an error without a next step cannot be raised. An exception that is not a `Stop` prints `Error: <type>: <message>` and `Next: metaform list modules` when it came from a module, or `Next: metaform help` otherwise, and exits 1.
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
  - Declaration functions, in `metaform.settings`, one per kind, each returning the declared `Setting`:
    - `text(key, default='', **common)` for `str`;
    - `number(key, default=0, *, min=None, max=None, **common)` for `int`;
    - `boolean(key, default=False, **common)` for `bool`;
    - `items(key, default=(), **common)` for `list`;
    - `choice(key, choices, default=None, **common)` for `select`.
  - `common` is the keyword arguments `help=''`, `details=''`, `group=None`, `label=None`, `short=None`, `switches=None`, `scope='folder'` and `default_from=None`. `group` defaults to the owner, `label` to the key with underscores as spaces and the first letter capitalized, and `switches` to `('--<key with hyphens>',)`, with `'--no-<key with hyphens>'` added for a boolean. A `switches` value given explicitly lists every long form, the first being the one help shows first. `scope` is `folder` or `global`, CLI-014. `short` is one letter, used with one dash, CLI-004.
  - The owner is set by the chassis while it loads a module, through `owned_by`, so a module never passes it.
- Acceptance: a setting declared in a test module appears with the same default and help in `config --show --json`, in `help switches`, and is accepted by `set`; a second declaration of the same key by another owner fails at load.
- Relates to: CLI-011, CLI-012, BASE-008, QUAL-004.
- Status: confirmed.

### CLI-011 Every long switch is a setting
- Requirement: every long switch that changes how commands run is a setting, so it can be passed on one call, stored with `set`, cleared with `unset`, and protected with `--glue`.
- What this means: passing a switch on a command affects that call only. `set` stores the value for the folder. `unset` clears the stored value. `--glue` protects the stored value from `unset all`. `unset all --unglue` returns every setting, glued ones included, to its safe default.
- Why: any behavior a user can ask for once, they can also make their standing choice, with no second mechanism for configuration.
- How it shows: `metaform helloworld greet world --loud` shouts once. `metaform set --loud` makes every later greet shout. `metaform unset --loud` returns to the default.
- Build: when a command runs, each setting's effective value resolves in this order: the switch on this call, then the stored value at the nearest folder at or above the current folder, then the declared default. Verb control switches that only steer a chassis command (`--glue`, `--unglue`, `--show`, `--json`, `--quiet`, `--help`) are listed in the open questions. The change: module switches become settings (CLI-012), and per-call values join the resolution order.
- Acceptance: with a stored value of off and `--loud` passed on one call, that call shouts and `config --show` still shows off afterward; with no stored value, the declared default applies.
- Relates to: CLI-012, CLI-013, CLI-014, CLI-016.
- Status: confirmed.

### CLI-012 Module switches are declared once and are settings
- Requirement: a module declares each of its switches once, and that declaration is both the verb's switch and a setting.
- What this means: a module switch such as `--loud` is a setting owned by the module. The verb lists which settings it reads, and the parser accepts those settings as switches on that verb.
- Why: one declaration keeps a module's switches, settings and help in step, and makes every module switch storable with `set` the same way chassis switches are.
- How it shows: the helloworld module declares `--loud` once; `metaform helloworld greet world --loud` and `metaform set --loud` both work, and `help --loud` names the template as owner.
- Build: `Adverb` in `module.py` is replaced by a reference from `Verb` to setting keys declared through `metaform.settings`. The verb's context gives effective values by key, which already exists as `Context.setting(key)`. The current demo module declares `--loud` as an `Adverb`, separate from settings; that changes.
- Acceptance: `metaform set --loud` succeeds for a module that declares `loud`, and the verb then behaves as if `--loud` were passed.
- Relates to: CLI-010, CLI-011, BASE-006, BASE-007, MCP-005.
- Status: recommended.

### CLI-013 Settings have three states: default, set, glued
- Requirement: every setting is in one of three states: default, set, or glued.
- What this means: default means nothing is stored for it, so its value is the declared default. Set means a value is stored and `unset all` clears it. Glued means a value is stored and `unset all` keeps it. A default is a real value, such as 4 nodes or true.
- Why: glue lets a user keep a baseline through a reset, while everything else returns to the working defaults.
- How it shows: `config --show` prints each setting with its value and a state note: nothing for default, `(set)`, or `*` and `(glued)`.
- Build: the `settings` and `glue` tables of STORE-002. A setting's state at a folder: glued when a `glue` row exists at its scope, CLI-014; set when a `settings` row exists there; otherwise default.
- Acceptance: `set --x v --glue` then `unset all` keeps v; `unset all --unglue` returns x to its declared default and state default.
- Relates to: CLI-014, CLI-016, CLI-017.
- Status: confirmed.

### CLI-014 A stored setting belongs to a folder and its subfolders
- Requirement: `set` stores a folder setting for the folder it runs in, and that value applies to every folder below it until a deeper folder sets its own.
- What this means: the effective stored value for a folder is the one stored at the nearest folder at or above it.
- Why: agents run in many folders and worktrees inside one project; a setting made at the project root reaches all of them without being repeated.
- How it shows: `cd ~/mgm-main && metaform set --modules workflow` then `cd ~/mgm-main/src && metaform config --show` shows modules workflow.
- Build: a folder setting's scope at folder F is the `folders.path_key` of the nearest folder at or above F, walking F and then each parent to the root, that holds a `settings` or `glue` row for the setting's owner and key; with none, it is F's own path key. `set` always writes at F's own path key. A global setting's scope is `global`. All values live in the home database under ~/.metaform; nothing is written into the folder.
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
- Build: `set` writes the value whether or not the setting is glued and leaves any glue row unchanged. Resetting one setting skips it, reporting `skipped (glued)`, when a glue row exists, unless `--unglue` is given, which deletes the glue row and the value.
- Acceptance: after the sequence above, state is glued and value false; `unset --tmux` reports skipped (glued).
- Relates to: CLI-013, CLI-015, CLI-017.
- Status: confirmed.

### CLI-017 `unset all --unglue` always returns to the safe defaults
- Requirement: `unset all` returns every unglued setting in scope to its default, and `unset all --unglue` also clears and unglues glued settings, leaving every setting at its declared default.
- What this means: the declared defaults are safe working values, so `unset all --unglue` always lands on a working configuration.
- Why: a user or agent can always get back to a known good state in one command, whatever was set or glued before.
- How it shows: `metaform unset all` prints `Reset N setting(s): ...` and `Skipped (glued): ...`. `metaform unset all --unglue` prints the reset list and `Unglued: ...`.
- Build: `unset all` resets every setting whose owner is loaded, one by one under CLI-016's rule, and prints `Reset N setting(s): <keys>` or `No settings required reset`, then `Skipped (glued): <keys>` and `Unglued: <keys>` when those lists are not empty. Scope of `all` is listed in the open questions.
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
  Next: If you are sure: metaform helloworld forget --confirm
  ```
  `metaform set --confirm` fails with `Error: --confirm is not a setting.` and a Next line naming `metaform help --confirm`.
- Build: the dispatcher checks `Verb.caution`, BASE-035; without `--confirm` on the call it raises `Stop(caution, 'If you are sure: <the same command> --confirm')` before the verb runs. The settings schema rejects the key `confirm` at declaration.
- Acceptance: `set --confirm` exits 2; a caution verb without `--confirm` exits 2 and changes nothing.
- Relates to: CLI-011, BASE-013, MCP-006.
- Status: confirmed.

### CLI-019 Select settings take choices from a list or from module data
- Requirement: a select setting takes its choices either from a fixed list in code or from a function that reads the owning module's data at the time of use.
- What this means: the workflow setting, for example, offers the workflows its module has stored. An invalid choice fails with the current choices listed.
- Why: a module can offer choices it authored itself, and the choices stay current without redeclaring the setting.
- How it shows: `metaform set --favorite zed` fails with `Error: --favorite has no choice 'zed'. Choices: world, rich.` and a Next line naming `metaform help --favorite`.
- Build: `settings.choice(key, choices, default=None, help='')`, where `choices` is a list or a function `choices(ctx: Context) -> list[str]` returning the current list. The chassis builds the Context for the folder the setting is being read or set for, BASE-028, and calls the function each time the choices are needed: parsing, help and the settings screen. It reads through `ctx.store`, the data access object. When `ctx.store` is None, because the folder resolves to no project, the function returns an empty list, and a `set` of that setting then fails with `Error: --<switch> has no choices here: this folder is not in a registered project.` and `Next: metaform add project <id> <path>`.
- Acceptance:
  - After the module stores a new item, `set` accepts it as a choice with no redeclaration.
  - In a folder with no project, the choices function receives a Context whose store is None and the `set` fails with the Next line above.
- Relates to: CLI-010, STORE-022, STORE-023, BASE-028.
- Status: confirmed.

### CLI-020 Metaform works with zero configuration
- Requirement: out of the box, the declared defaults are the working settings, and Metaform and every module work with no configuration.
- What this means: no setting has to be set before any command works. Settings tune a working system.
- Why: low-friction start for users and agents; nothing blocks the first command.
- How it shows: a fresh home with no saved settings runs `metaform`, `metaform help`, and every enabled module verb.
- Build: every declared setting has a working default or a `default_from`. A module whose setting cannot have a working default is refused at load with a Next line.
- Acceptance: with an empty home, every chassis verb runs with exit 0 given valid nouns, and every helloworld verb that needs no project store runs with exit 0. A module verb that needs a project store, such as the template's greeting and history verbs, stops in an empty home with exit 2 and `Next: metaform add project <id> <path>`, STORE-023; no configuration is involved, since registering a project is data, not a setting. After `metaform add project <id> <path>` and nothing else, every helloworld verb runs with exit 0.
- Relates to: CLI-010, CLI-017, STORE-022, STORE-023.
- Status: confirmed.

## Context and the command surface

### CLI-021 Working context is made of ordinary folder settings
- Requirement: the working context is four folder settings: `--project`, `--workflow`, `--modules` and `--layers`.
- What this means: `--project` defaults to the registered project that contains the folder. `--workflow` names the active workflow, with choices from the workflow module's data. `--modules` lists the command groups on the folder's surface; empty means all. `--layers` lists the layers toggled on, by name or tag; empty means every finished layer that is not hidden, CLI-033. One workflow runs at a time, so the workflow is a single setting and never a list. A workflow may come with its own settings, declared by the module that provides it, like any module setting.
- Why: context as settings needs no extra machinery, and it is visible and reversible like any setting.
- How it shows: `metaform set --workflow intake --modules workflow,memory`. `metaform` status shows the project and the narrowed commands.
- Build: the chassis declares `project`, a folder select whose choices are the registered project ids and whose default comes from the folder, STORE-002, and `modules`, a folder list whose default is empty, and `layers`, a folder list whose default is empty, CLI-033. `workflow` is declared by the workflow module as a select, not by the chassis, since the chassis does not run workflows. The values each accepts are CLI-030.
- Acceptance: in a subfolder of a registered project with nothing set, `--project` is that project; `unset --project` returns to it.
- Relates to: CLI-014, CLI-022, STORE-002, MCP-011.
- Status: confirmed.

### CLI-022 Narrowing the command surface hides and blocks, and states the way back
- Requirement: commands outside the folder's command surface are neither shown nor run, on the CLI or over MCP, and the `set` that narrows the surface states the exact way back.
- What this means: `--modules` lists the modules whose commands a folder shows and runs; `chassis` names the chassis's own commands. It narrows what the folder shows and runs; it does not enable or disable any module. Help indexes, help pages and MCP tool lists omit hidden groups, and a hidden command fails with a Next line. The narrowing `set` prints which commands remain and the way back. An orchestrator narrows a worker's folder before the worker starts by naming that folder with a `folder=<path>` noun, PROJ-007.
- Why: removing commands from the surface holds even for agents with full permissions, where host permissions do not. The orchestrator that narrowed the surface holds the exact way back and acts with confidence; a subagent meets only the caution. The wording steers, and nothing gates inference.
- How it shows:
  ```
  Success: updated 1 key
    modules: all → workflow,memory
  Commands shown here: workflow, memory.
  All other commands and help, including yours, are now hidden and will not run.
  To restore them: metaform unset --modules
  ```
  When a workflow narrowed the surface, the last line names that workflow module's abort verb instead, D50. `metaform set --modules workflow,memory folder=~/wt/job1` stores the same value for that folder and prints the same lines, naming the folder at the end of the first: `Success: updated 1 key for <folder>`, or `Success: no changes for <folder>`.
  `metaform help --modules` says: `Narrows which modules' commands this folder shows and runs. It does not enable or disable modules; use metaform enable and disable for that.`
- Build:
  - The exact text of `set` output is owned here. Line 1: `Success: updated <n> key` when one setting changed, `Success: updated <n> keys` otherwise. Then one line per change, `  <key>: <old> → <new>`, values shown per CLI-031's value rule, except that an empty `modules` value is shown as `all`, because empty means every group. Then `  glued: <keys>` when `--glue` was given. With no change: `Success: no changes`. When the new `modules` value is narrower than the old, three lines follow: `Commands shown here: <groups, comma and space separated>.`, `All other commands and help, including yours, are now hidden and will not run.`, and the way-back line below. `-q` suppresses all of it except errors.
  - A command group is shown when `modules` is empty or contains the group, where a group is `chassis` or a module id. `help`, `set`, `unset` and `config` always run, whatever the surface, so the surface can always be restored; `feedback`, `list reports` and `read report` always run too, so an agent can always report, BASE-045. `mcp serve` is the transport, not a command an agent runs, so it always runs, whatever the surface; `--modules` narrows which tools the server lists and runs, MCP-004. The same check filters the commands index, help pages, dispatch and the MCP tool list, MCP-004. Until D35 and D50 are answered, the way back line is `To restore them: metaform unset --modules`, which is the current text.
- Acceptance: after narrowing to one module, a chassis verb outside the surface exits 2 and is absent from `help commands` and from the MCP tool list.
- Relates to: CLI-008, CLI-021, MCP-004, BASE-016, PROJ-007.
- Status: confirmed for hiding and blocking, for the name `--modules` and its help text, and for the `folder=<path>` noun that stores the value for another folder. The way-back text depends on D35 and D50.

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
- Build: A stored setting is keyed by scope, owner and key, STORE-002, so a later module cannot take over another module's stored value by declaring the same key. Only settings whose owner is enabled are shown or accepted. Whether `unset all` touches an absent module's stored values is open; the recommendation is that it does not.
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
- Build: The screen reads and writes only through the settings module and `enable` and `disable`, never the database directly. It uses `prompt_toolkit`, which is pure Python, BASE-026, and opens only when standard input and output are terminals; otherwise `metaform config` prints what `config --show` prints.
  - Layout: a left panel lists the chassis and every discovered module, each with on, off or error; a right panel lists the selected group's settings, each row `key: value` with `*` for glued and `(set)` for set; a bottom line shows the selected setting's help and the count of unsaved changes.
  - Keys: Up, Down, `k`, `j` move; Home, End, PageUp, PageDown jump; Left, `h`, Right, `l`, Tab and Shift+Tab switch panels; Enter on a module moves to its settings; Enter or Space on a setting edits it; Space on a module stages enable or disable; `+` and `-` step a number; `r` or F9 stages a reset of one setting; `R` stages a reset of the whole group; `g` stages glue or unglue; `/` filters settings by text; `p` previews staged changes; `s` saves; F1 or `?` shows key help; F2 shows the module's help page; Esc goes back one level; `q` quits; F10 saves and quits; Ctrl+C quits.
  - Editing: a boolean edit offers its two values; a select offers its current choices; text and numbers are typed and validated by the same parser as `set`, with the error shown on the bottom line.
  - Quitting with unsaved changes asks: `s` save and quit, `d` discard and quit, Esc continue.
  - Saving applies the staged changes in order through `set`, `unset`, glue and `enable` or `disable`, then reloads.
- Acceptance:
  1. A value staged in the screen and then discarded leaves the stored settings unchanged.
  2. A value saved in the screen reads back the same through `metaform config --show`.
- Relates to: CLI-010, CLI-013, CLI-015, BASE-017.
- Status: confirmed.


### CLI-027 Values of each setting kind on each surface
- Requirement: Each setting kind has one written form on the CLI and one JSON type over MCP.
- What this means: An agent over MCP and a person on the CLI give the same value in the form natural to each.
- Why: One representation per kind keeps the two surfaces equal and keeps a stored value from depending on which surface wrote it.
- How it shows: `metaform set --panes 6` and a tool argument `panes: 6` store the same integer.
- Build:

  | Kind | CLI form | MCP type | Stored as |
  |---|---|---|---|
  | `str` | the word | string | JSON string |
  | `int` | decimal digits, optional leading minus | integer | JSON number |
  | `bool` | the two forms `--name` and `--no-name`, CLI-015 | boolean, absent when not given | JSON boolean |
  | `list` | comma-separated items, `--name a,b`; `--name ''` for empty | array of strings | JSON array of strings |
  | `select` | one of the current choices | string with an `enum` of the current choices | JSON string |

  A value switch takes `--name value` or `--name=value`, CLI-004. Numbers are checked against `min` and `max` when declared. Nouns of kind `json` are parsed as JSON on the CLI and passed as JSON values over MCP, BASE-043.
- Acceptance: For each kind, a value set on the CLI and the same value set through a tool read back equal in `config --show --json`.
- Relates to: CLI-010, CLI-015, MCP-005, BASE-043.
- Status: recommended.

### CLI-028 The status lines
- Requirement: `metaform` status prints fixed lines in a fixed order, and ends with the one next step when something needs doing.
- What this means: Agents and people read the same status, and the skill points agents to it, MCP-021, so it carries the no-intake notice and the composed instructions' location.
- Why: A fixed format lets an agent read status reliably, and the next step keeps it on the surface.
- How it shows, in a registered project with no intake:
  ```
  Metaform 0.2.0
  Home: /home/rich/.metaform
  Folder: /home/rich/mgm-main/src
  Project: mgm (/home/rich/mgm-main), inherited from /home/rich/mgm-main
  Target: path /home/rich/mgm-main
  Metaform: main
  Projects: 2 registered
  Modules: 4 on
  Intake: none yet
    This project has no intake yet. Have a subagent perform it. Tell the subagent to read its instructions with `metaform intake prompt`, or the `intake_prompt` tool, and to follow them.
  Instructions: metaform help agents
  ```
- Build: lines in order:
  1. `Metaform <version>`
  2. `Home: <home>`
  3. `Folder: <folder>`
  4. `Project: <id> (<path>)`, followed by `, selected here` when the `project` setting is stored at this folder, `, inherited from <folder>` when it is stored at a parent, and nothing when it comes from the default. With no project: `Project: none` and the line `  Register one: metaform add project <id> <path>`, and status ends there.
  5. `Target: <type> <value>`, STORE-031.
  5a. `Metaform: <name>`, the project's active metaform, STORE-041, followed by `, <n> in project` when the project has more than one. Omitted when there is no project.
  6. `Projects: <n> registered`
  7. `Modules: <n> on`, followed by `, <m> not loaded (metaform list modules)` when any enabled module failed.
  8. When `modules` is not empty: `Modules: <groups> (narrowed; restore: metaform unset --modules)`.
  9. For each enabled module on the folder's surface that declares a status hook, BASE-035, in module id order: each of its lines, then its notice, when it returns one, indented two spaces. The chassis prints what the hooks return and names no module. With the intake module on, its hook gives the `Intake:` lines and the no-intake notice shown above, BASE-039.
  10. `Instructions: metaform help agents`, the command that prints the composed agent instructions, MCP-007.
- Acceptance:
  - In a registered project with no intake and the intake module on, status contains the notice; while an intake is being recorded it shows that and no notice; after `intake_finish`, it shows `Intake: complete` and no notice.
  - A test module with a status hook returning one line and one notice gets both printed in its id order; `cli.py` contains no module id.
- Relates to: CLI-005, MCP-007, MCP-009, STORE-031, BASE-035, BASE-039.
- Status: recommended. `metaform help agents` follows D40's intent that status leads an agent without MCP to the instructions.

### CLI-029 Help page and syntax layouts
- Requirement: Every help page and syntax screen follows one layout generated from the declarations.
- What this means: A reader finds the same sections in the same order for every command, module, verb and switch.
- Why: A predictable layout is what lets agents read help instead of source.
- How it shows: `metaform help set` and `metaform help helloworld greet` have the same section order.
- Build:
  - Page: `<name>: <summary>`, blank line, description when present, `Usage` and each usage line indented two spaces, `Switches` and one row per switch with its one-line help, `Caution` for a caution verb, `Details` when present, `Examples` with each example and its meaning on the next line indented four spaces, then `See also: <names>`. Empty sections are left out.
  - Syntax: `Usage: <first usage line>`, further usage lines aligned under it, a blank line, then one row per switch including `-h, --help  Show this syntax.`
  - Module page: `<id>: <summary>`, blank line, the module's purpose, `Verbs` with one row per verb, `Settings` with one row per owned setting, `Details` when present, and `Use 'metaform help <id> <verb>' for one verb.`
  - Rows: the left column is padded to its widest entry of at most 40 characters, plus two spaces. An entry longer than that goes on its own line with its help on the next, under the others' help, so one long usage never widens every row.
  - Switch page for a setting: `<switch>: <help>`, details, `Usage` with `metaform set <switch>` and `metaform unset <switch>`, the choices for a select, and `Owner: <owner>. Kind: <kind>. Applies to: this folder` or `everywhere`.
  - `metaform help agents` prints the composed instructions of MCP-007 for the folder.
- Acceptance: A newly declared verb's page has exactly the sections its declaration fills, in this order.
- Relates to: CLI-006, CLI-007, CLI-008, MCP-007.
- Status: recommended.

### CLI-030 Values the context settings accept
- Requirement: `--project` accepts only a registered project id, and `--modules` accepts only `chassis` and ids of discovered modules.
- What this means: A context setting that named nothing real would narrow a folder to an empty surface or point it at a missing project.
- Why: Context decides what an agent can reach. A typo in it must fail at once with the next step, not later as a missing command.
- How it shows: `metaform set --modules mapp` fails: `Error: --modules has no group 'mapp'. Groups: chassis, intake, map, mcp, memory.` `Next: metaform list modules`.
- Build: `project` is a select over registered ids, CLI-019. `modules` validates each item against `chassis` plus the ids `loader.discover()` found, whether enabled or not; naming a disabled module is accepted, and its commands appear when it is enabled.
- Acceptance: The example fails and stores nothing; `set --modules chassis,map` succeeds.
- Relates to: CLI-021, CLI-022, BASE-037.
- Status: recommended.

### CLI-031 The chassis verbs in full
- Requirement: Each chassis verb takes exactly the nouns and switches below and prints exactly the lines below, so a builder needs no earlier code to reproduce them.
- What this means: The chassis runs completely on its own as a CLI. These verbs are that CLI. Module verbs follow BASE-035; these are the chassis's own.
- Why: The spec is the contract. Behavior that exists only in earlier code cannot be rebuilt from the spec, and a rebuild would drift.
- How it shows: The examples in each row.
- Build: Every error below is a `Stop` with its one Next line, CLI-009. `-q` and `--quiet` suppress success output on `set` and `unset`. `--json` prints the result as JSON, BASE-036, on `list`, `config --show` and `query`.

  | Verb | Nouns and switches | Output and errors |
  |---|---|---|
  | `help` | none; `intro`; `commands`; `switches`; `agents`; a switch such as `--loud`; a chassis verb; a module id; a module id and verb | The overview, CLI-006; the intro, CLI-006; the indexes, CLI-008; the composed instructions, MCP-007; the pages, CLI-029. Unknown thing: `No command, module or switch <thing>.` Next `metaform help commands`. |
  | `add` | `project <id> <path> [<target type> <target value>]`; `metaform <name> [<project>]`; `origin [<project>]`; `variant <folder> [origin=<id>] [remove=true] [module=] [workflow=] [prompt=] [model=] [role=] [blinded=true|false]` | project: STORE-031. Success: `Added project <id>: <path> (target <type> <value>)`. metaform: STORE-041, with the output stated there. origin, PROJ-014: `Added origin <mform_id>, repo at commit <commit>.` or `Added origin <mform_id>, folder copied from <path>.`, then `Uncommitted work was collected as variant <id>.` when it was; the same content again: `Origin <mform_id> already holds this content; nothing was added.` variant, PROJ-017: `Collected variant <id> of origin <mform_id>: <n> files changed.` |
  | `list` | `projects`, `modules`, `metaforms [<project>]` (STORE-041), `reports [<project>]` (BASE-045), `origins [<project>]` or `variants [origin=<id>]` (PROJ-024) | projects: one line per project, `<id>  <path>  <target type> <target value>`, ids padded to the widest; none: `No projects yet. Register one: metaform add project <id> <path>`. modules: BASE-037's line per module, `<id>  <on|off|error>  <system|user|entry>  <summary or reason>`, ids padded to the widest. origins: `<mform_id>  <repo|folder>  <commit or source path>  <established>  <n> variants`. variants: `<id>  <collected>  <source path>  <workflow or ->`. Any other noun: `list needs a noun: projects, modules, metaforms, reports, origins or variants.` Next `metaform list projects`. |
  | `set` | one or more setting switches with values, CLI-011 and CLI-015; `--glue`; `-q` | Success output: exactly as CLI-022's Build states, which owns the text of `set` output with or without narrowing. A word that is not a switch: `set takes switches, not '<word>'.` Next `metaform set --help`. An unknown switch: `<switch> is not a setting.` Next `metaform help switches`. An invalid value: the error of CLI-027 with Next `metaform help <switch>`. |
  | `unset` | one or more setting switches, or `all`; `--unglue`; `-q` | `Reset <n> setting(s): <keys>` or `No settings required reset`, then `Skipped (glued): <keys>` and `Unglued: <keys>` when they apply. `--all`: the error and Next line of CLI-002, which owns that text. |
  | `config` | none; `--show`; `--show --json` | none: the settings screen, CLI-026, or `--show`'s output without a terminal. `--show`: one line per setting in schema order, `<mark> <key>: <value>` with `*` as the mark for glued and a space otherwise, followed by `  (set)` or `  (glued)` unless default, then a blank line and `* glued: kept by unset all until unglued.` `--json`: a list of objects with key, switch, owner, kind, value, state, default and help. |
  | `activate` | `metaform <name> [<project>]` | STORE-041, with the output stated there. Unknown name: `No metaform <name> in <project>.` Next `metaform list metaforms`. |
  | `enable`, `disable` | `<module>` | `Module <id>: on` or `off`. Unknown id: `No module <id>.` Next `metaform list modules`. Writes the `module_state` row, STORE-002. |
  | `feedback` | BASE-045 | As specified there. |
  | `read` | `report <file name> [<project>]` | BASE-045. Unknown file: `No report <name>.` Next `metaform list reports`. |
  | `install`, `uninstall` | MCP-013 to MCP-020 | As specified there. |
  | `build` | none | BASE-041. |
  | `import`, `export` | STORE-027 | As specified there. |
  | `query` | STORE-028 | As specified there. |
  | `prompts`, `prompt` | `prompts`; `prompt <name> [<version>]`, STORE-044 | prompts: one line per prompt, `<name>  <format>  version <newest>`. prompt: the version's text exactly, the newest unless a number is given. Unknown prompt: `No prompt <name>.` Next `metaform prompts`. |
  | `extract` | `<variant id>... <folder>` or `all <folder>`, `[origin=<id>]`, PROJ-018 | `Extracted into <folder>` for each folder written. A folder that is not empty: `<folder> is not empty.` Next `metaform extract <variant id> <empty folder>`. No origin: PROJ-024's error. |
  | `clear` | `project [<project>]`; `--confirm` | PROJ-025: without `--confirm`, the caution and Next `If you are sure: metaform clear project <project> --confirm`; with it, `Cleared <project>: <n> metaform(s), <names>, and <m> report file(s). Its registration, folder, settings, origins and variants stay.` |

  A value is shown as written for text, digits for numbers, `true` or `false` for booleans, comma-separated for lists, and `(none)` for an empty value, except the `modules` setting, whose empty value is shown as `all`, CLI-022.
- Acceptance:
  - `metaform list foo` exits 2 with the stated error and Next line.
  - `metaform set --favorite world` then `metaform config --show` shows `  favorite: world  (set)`.
- Relates to: CLI-001, CLI-006, CLI-008, CLI-009, CLI-011, CLI-022, CLI-026, CLI-029, BASE-037, STORE-002, STORE-027, STORE-028, STORE-031.
- Status: recommended.

### CLI-032 The command tree has a few top-level objects

- Requirement: Commands form a hierarchy with a few top-level objects, under which commands are grouped.
- What this means: The top level holds the chassis verbs and one object per module, CLI-001 and CLI-031. Each module's verbs sit under its id, so `metaform help` stays short and a user finds a command by going one level down. The same hierarchy is what the command surface narrows, CLI-022.
- Why: A few top-level objects keep the first screen readable and make every command reachable by a predictable path.
- How it shows: `metaform help commands` lists the chassis verbs and each module with its verbs beneath it.
- Build: The commands index and the settings screen group commands by chassis and by module id, in the order of CLI-031 and module id order.
- Acceptance: `help commands` lists every enabled module's verbs under that module's id, and no module verb at the top level.
- Relates to: CLI-001, CLI-008, CLI-022, CLI-031.
- Status: confirmed for the hierarchy.

### CLI-033 `--layers` toggles the layers on for a folder
- Requirement: the layers toggled on for a folder are the context setting `--layers`, which follows every settings rule.
- What this means: `--layers` holds a list of layer names and tags. A tag turns on every layer carrying it. Correction layers are never named or toggled here: they are always applied, in order, LAYER-011; naming one is refused. The listed layers are the starting selection for every in-context read from this folder and its subfolders, on the CLI and over MCP; per-address select and mask apply on top, LAYER-007. Like any setting, it is given on one call to apply to that call only, stored with `set`, cleared with `unset`, protected with `--glue`, and `unset all` returns it to its default. The default, empty, means every finished layer that is not hidden. The orchestrator sets it for the work it hands out, choosing the layers by how it is prompted, LAYER-019.
- Why: Toggling layers is part of the working context, like the workflow and the command surface, so it is an ordinary setting: visible, reversible, stored per folder and needing no machinery of its own.
- How it shows:
  ```
  $ metaform set --layers practices,memory
  Success: updated 1 key
    layers: all → practices,memory
  $ metaform map layers
  practices-cpp   layer   map   practices        ready   on
  mgm-foresight   layer   map   foresight        ready   off
  memory          memory  memory                 ready   on
  $ metaform unset --layers
  Reset 1 setting(s): layers
  ```
  Over MCP, the same value is passed to the `set` tool as `layers`, or as `layers` on a single tool call to apply to that call only.
- Build: the chassis declares `layers` as a folder list setting with default empty, value syntax per CLI-030 for lists. Validation resolves each entry through STORE-038; an entry that is neither a layer nor a tag is kept, turns nothing on, and the output carries a notice naming `metaform map layers`, BASE-044. A building layer named in the list is not turned on until it is finished; a hidden layer named in the list stays out, LAYER-006. The set's output follows CLI-022's format, showing an empty value as `all`.
- Acceptance:
  1. `set --layers practices` in a folder, then an in-context read in a subfolder, returns only layers tagged `practices`.
  2. `--layers memory` given on one call changes that call's read and leaves the stored setting unchanged.
  3. `set --layers practices --glue` then `unset all` keeps `layers` at `practices`; `unset all --unglue` returns it to empty.
- Relates to: CLI-011, CLI-013, CLI-014, CLI-021, CLI-022, CLI-030, LAYER-007, LAYER-019, STORE-035, STORE-038, MCP-003.
- Status: confirmed that layers are toggled on and off and that toggling is a context setting following every settings rule. The name `--layers`, the default and the listing format are recommended.

### CLI-034 `--debug` and `--report` decide what agents are asked to report
- Requirement: Two chassis boolean settings, `--debug` for the Metaform process and `--report` for the project, each follow every settings rule and decide whether agents are asked for process feedback and for a project report.
- What this means: `--debug` is about Metaform itself. When it is on, agents doing Metaform work are told to submit feedback and trouble reports on the process: bad semantics, a tool that did not match its schema, where they got stuck. `--report` is about the project. When it is on, the intake agent returns a report on the project it performed intake on. Each is a boolean with `--name` and `--no-name`, stored with `set`, cleared with `unset`, protected with `--glue`, per folder like other context settings. They produce two separate files in the project's reports folder, BASE-045. The intake prompt's footer and the module instructions carry the matching request only when its setting is on.
- Why: Process feedback is what the people improving Metaform need while testing, and noise otherwise. A project report is what the project owner wants from an intake. Keeping them separate lets each be turned on for its own reason. As settings they follow the one schema, so they can be set per folder, glued, and passed on a single call.
- How it shows: `metaform set --debug` then `metaform intake prompt` shows the feedback line in the footer; `metaform set --no-report` removes the report line.
- Build: `settings.boolean('debug', False, scope='folder', help='Ask agents doing Metaform work for feedback and trouble reports on the Metaform process.')` and `settings.boolean('report', True, scope='folder', help='Ask the intake agent for a report on the project it examined.')`, both owned by the chassis. The intake module's footer, BASE-039, and the composed instructions, MCP-007, read them for the folder. Submitted feedback and reports are stored whatever the settings, BASE-044.
- Acceptance:
  - With `--debug` off and `--report` on, the intake prompt footer holds the report line and not the feedback line; with both flipped, the reverse.
  - `metaform set --debug --glue` then `metaform unset all` leaves `debug` on.
- Relates to: CLI-011, CLI-015, BASE-039, BASE-044, BASE-045, MCP-007.
- Status: confirmed, including the defaults: `--debug` off and `--report` on. During development the orchestrator turns `--debug` on for its own runs. The names `--debug` and `--report` are recommended.

## Open questions

1. Scope of settings: every context setting is per folder. Do some settings stay global (applying in every folder), as the chassis `Setting.scope` allows today, and which?
2. Verb control switches: `--glue`, `--unglue`, `--show`, `--json` and `--quiet` steer chassis commands rather than change what a command does. Are they exempt from being settings, alongside `--confirm`, or is `--quiet` a setting?
3. Switch aliases: mvm's schema lists more than one long form for some settings (`--target-profile` and `--profile`, `--host-bridge-isolation` and `--hbi`). Does a setting get exactly one long form, or may it list aliases?
4. Boolean with a value: should `--name=false` be accepted, or does a boolean only take its two bare forms?
5. Way back from narrowing: when the surface is narrowed by `set --modules` with no workflow active, what is the way back line, and which commands remain always shown (today help, set, unset, config and mcp)?
6. Scope of `unset all`: does it reset only the settings stored at the current folder, or also the values it inherits from parent folders and any global settings?
7. Module switches as settings: what scope does a module switch get when stored with `set`: folder, like context settings, or global?
8. `metaform abort <workflow> --confirm` is written as a chassis verb, but the chassis does not run workflows (BASE-003) and module verbs take the module id first (CLI-001). Is `abort` a chassis verb, or the workflow module's verb, written `metaform workflow abort <workflow> --confirm`?
9. When a module is absent, does `unset all` leave its stored settings untouched? Recommended: yes. (CLI-024)
10. Dropped: stacking commands is not part of the design. CLI-032 keeps only the hierarchy.
