# 05. CLI and settings

This section specifies the metaform command line grammar, help, errors, and the settings system that every switch belongs to.
It covers the chassis commands and the rules every module command follows; MCP reuses the same declarations and is specified in its own section.

Current code referenced here: `src/metaform/settings.py`, `cli.py`, `docs.py`, `module.py` on branch `chassis`. The settings pattern follows mvm's `scripts/commcube_config/schema.py` and `cli.py`.

## Grammar

### CLI-001 Commands are verbs, arguments are nouns, switches are adverbs
- Requirement: every metaform command line reads as a verb, the nouns it acts on, and switches that change how it runs.
- What this means: the first word after `metaform` is a chassis verb (`help`, `add`, `list`, `set`, `unset`, `config`, `enable`, `disable`, `activate`, `install`, `uninstall`, `build`, `import`, `export`, `query`, `feedback`, `read`, `extract`, `prompts`, `prompt`, `clear`) or a module id followed by that module's verb. `mcp` is not a chassis verb; the MCP server is `metaform mcp serve`, MCP-001. Words that name what the verb acts on are arguments. Words starting with a dash change how the verb runs and never name what it acts on.
- Why: one consistent grammar makes every command predictable for people and agents, so a user who knows one command can guess the next, and an agent does not have to read source to find out how to call something.
- How it shows: `metaform add project notes ~/notes` (verb add, nouns project, notes, path). `metaform hello greet world --loud` (module template, verb greet, noun world, adverb --loud).
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
  Folder: /home/rich/notes
  Project: notes (/home/rich/notes)
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
- Amendment, 2026-10-14, start onboarding, ticket code.installer.package#d: the overview's Common commands list `metaform start  Map the project in this folder and open it.` right after `metaform`, and `metaform help intro`'s Start list begins with `metaform start                     Map the project in this folder and open it.`, so a new person meets the one command that maps their own project first, CLI-041.

### CLI-007 `help <thing>` is the man page; `--help` and `-h` give syntax
- Requirement: `metaform help <thing>` prints the full page for a command, module, verb or switch, and `<thing> --help` or `-h` prints only its syntax.
- What this means: the page has the summary, description, usage lines, switches, details, examples and related topics. The syntax form has the usage lines and switch names only.
- Why: understanding and typing are two needs; the page serves understanding and the syntax serves typing, and merging them fails both.
- How it shows: `metaform help set` prints the page; `metaform set --help` prints `metaform set --<setting> <value> [--glue] [--quiet]` and the switch list. `metaform help hello greet` prints the verb page; `metaform hello greet -h` prints its syntax.
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
- Acceptance: after `metaform set --modules hello`, `help commands` lists no chassis-only verbs except the ones always shown; a module declared setting appears in `help switches`.
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
- Amendment, 2026-10-15, settings screen redesign, ticket 31ee6b74f11342f08ff7ef35c2bc1f0e (code.interface.graphical#61), recorded to match the code: `common` also takes `category` (one of `settings.CATEGORIES`: general, agents, budgets, agent_options, map, voice, phone, integrations, advanced), `heading` (the small heading it sits under on that page; unlike `section` it opens no menu in the terminal screen), `essential` (its place on the web screen's Essentials page, 0 for none) and `unit` (what a number counts, read from the key's end, such as `_minutes`, when not declared). A setting with no category takes its module's `Module(settings_category=...)`, else advanced. A label not declared is the key in words less its module's name. `config --show --json` gives each row its `label`, `category`, `heading`, `essential` and `unit`. The web settings screen is built from them: a side list of the categories, Essentials first and the page it always opens on, then General, Agents, Budgets, Agent options, Map and display, Voice and speech, Phone, Integrations, Advanced with every module folded, and Modules last under Advanced; a search across every category that goes to the setting; each row with its plain label, its state (default, set here, inherited from a named folder, glued), whether only the person sets it, a risky choice marked and confirmed once, and the screen reading again when a setting changes elsewhere. Before, it opened on the module switches and listed one page per module with raw key names.
- Amendment, 2026-10-15, welcome and expanding text, ticket code.interface.graphical#73 (cd9fa353c1c142e5acd250e40c546409): on the web settings screen each row's control (a switch, a choice, a number, a text box) stands at the row's right edge, Reset just before it, and the label and its line of help take the width between, so less of them is cut. Text a row still cuts short with an ellipsis (a label, a line of help such as a module's description on Modules, a unit) shows a pointer and opens that row in place, wrapped, at a click or Enter, and folds it again the same way; a row opened stays open through the screen's redraws, and text that fits takes no click. Before, the controls sat in fixed columns mid-row with empty space to their right, and a cut line could be read only from its tooltip. Acceptance: `test_a_settings_line_cut_short_opens_in_place_at_a_click_or_enter_and_folds_again`.
- Amendment, 2026-10-15, enhancement implementation, ticket b74031aed37e42a78fa8c243bc71e2de (code.manager.configuration#16): `settings.ordered()` puts settings marked `essential` first by their declared position, then the other settings by category, owner and heading, with the chassis's module filter last. `describe`, `config --show` and `set --help` share that order; the web screen retains it within its categories. This makes a setting's importance visible across surfaces without separate lists. The gear clears any previous search and opens Essentials. The existing marked list and defaults are preserved. Essentials uses compact spacing to fit a desktop screen at the usual text size. Modules uses two columns of enable/disable switches, falling back to one in a narrow pane. The screen reads the existing voice status: a ready speech engine other than the selected `voice_tts` is named beside that setting, with its switch and the value that selects it. Selecting it removes the notice. Reading readiness never selects an engine or calls the provider's speech service. Why: prepared capabilities can remain unused through an undiscovered setting, and a settings landing page that scrolls hides the controls it is meant to expose. Acceptance: `test_settings_surfaces_put_essentials_first_then_categories_and_modules_last` and `test_essentials_names_a_ready_unused_speaker_fits_the_screen_and_keeps_modules_compact`.

### CLI-011 Every long switch is a setting
- Requirement: every long switch that changes how commands run is a setting, so it can be passed on one call, stored with `set`, cleared with `unset`, and protected with `--glue`.
- What this means: passing a switch on a command affects that call only. `set` stores the value for the folder. `unset` clears the stored value. `--glue` protects the stored value from `unset all`. `unset all --unglue` returns every setting, glued ones included, to its safe default.
  - A setting declared `person_only` is written only by the person, on the command line or the page. Over MCP, the `set` tool refuses a call that names one and stores nothing of that call, and a module command given one as a switch stops before it runs. Each refusal ends with one next step, the ticket's note, MCP-006. Neither schema offers it to an agent. A setting is `person_only` when it decides which agents run, how they are started, what they are permitted, how they are watched or when their work merges. These settings are: dispatch's `dispatch_prompts`, `dispatch_recovery`, `dispatch_autostart`, `dispatch_agents`, `dispatch_agent`, `dispatch_claude`, `dispatch_codex`, `dispatch_gemini`, `dispatch_worktrees`, `dispatch_test_command`, `dispatch_review_minutes`, `dispatch_spin_calls`, `dispatch_spin_minutes`, `dispatch_repeat_failures`, `dispatch_record_on_finish`, `dispatch_agent_options`, `dispatch_steering`, `dispatch_silence_seconds`, `dispatch_stderr_kb`, `dispatch_retries`, `dispatch_retry_seconds`, `dispatch_budget_ticket`, `dispatch_budget_run`, `dispatch_budget_day`, `dispatch_budget_cost_ticket`, `dispatch_budget_cost_day`, `dispatch_budget_action` and `dispatch_elicitation`; web's `agent_command` and `web_bind`; fork's `fork_agent` and `fork_secret`; and the chassis's `roles_without_authority`, the roles held back from writing tickets and steering agents, MAP-050 and BASE-052. A module that declares a setting of this kind marks it so. A verb that changes a ticket's intended outcome or its cost, dispatch's `cancel` and `tune`, is refused over MCP by the same rule. This is a permission the person holds, not a rule fixed against them: the setting `agents_may_set_control`, itself `person_only` and off by default, lets agents set these over MCP too, through the person's own permission policy. Why, 2026-10-11: control belongs in permissions the person sets and can change, never in a rule an agent enforces that the person cannot bypass.
- Why: any behavior a user can ask for once, they can also make their standing choice, with no second mechanism for configuration. That holds for the person. An agent that can store, or pass for one call, a setting that decides its own permissions or control can widen them past what the person chose: before this rule, `set` over MCP stored `dispatch_prompts=approve-all`, and `dispatch autostart` over MCP took `dispatch_autostart` and `dispatch_agents` for the call. A start or test command runs whatever it names, and it can start an agent with that agent's own permission checks turned off. The review time and worktree settings decide whether an agent's work merges without the person. The spin and failure thresholds decide when the person is told that an agent is stuck. `web_bind` decides who can reach the page where agents are permitted and started. `fork_secret` decides which secret CI gives an agent. `modules` stays an agent's to set: MCP-004 gives the orchestrator the narrowing, and the setting enables no module. `dispatch_wait_seconds` and the settings that shape what an agent reads or where its writes go are also left to agents, because they give an agent no power over other agents or itself. The rule depends on the surface: a dispatched agent that runs `metaform set` in a shell is not refused. Under `ask_all`, that shell command is itself a permission request that the person answers.
- How it shows: `metaform hello greet world --loud` shouts once. `metaform set --loud` makes every later greet shout. `metaform unset --loud` returns to the default.
- Build: when a command runs, each setting's effective value resolves in this order: the switch on this call, then the stored value at the nearest folder at or above the current folder, then the declared default. Verb control switches that only steer a chassis command (`--glue`, `--unglue`, `--show`, `--json`, `--quiet`, `--help`) are listed in the open questions. The change: module switches become settings (CLI-012), and per-call values join the resolution order.
- Acceptance: with a stored value of off and `--loud` passed on one call, that call shouts and `config --show` still shows off afterward; with no stored value, the declared default applies. Over MCP, `set` with `dispatch_prompts` is refused with one next step, stores nothing of the call and is not offered, while `metaform set --dispatch-prompts` still stores it; `dispatch autostart` given `dispatch_autostart` is refused before it runs. Both are checked in `src/metaform/modules/mcp/tests/test_mcp.py`.
- Relates to: CLI-012, CLI-013, CLI-014, CLI-016, BASE-052, MCP-003, MCP-004, MCP-006.
- Status: confirmed. `person_only` settings refused over MCP, built 2026-10-11, work 59b74b9d.
- Amendment, 2026-10-17, UX review round 1, fix group person-consent (settings-govern-behavior F2, F5; agent-identity-handoff F2): who is an agent is no longer read from METAFORM_ROLE alone, which an agent cleared with `METAFORM_ROLE= metaform set ...` or `METAFORM_ROLE=none`. `metaform.caller.agent()` (`metaform.module.agent_caller`) takes a command for an agent's when any runner identity name (METAFORM_ROLE, METAFORM_SESSION, METAFORM_WORK, METAFORM_NODE) is set, whatever its value, or, on Linux, when one of the processes that started it is a Metaform dispatch runner, a Metaform MCP server or an AI tool (Claude Code, Codex, Gemini CLI and the ACP adapters) working in the same home. `set`, `unset`, a verb's person-only switches, `persons_own` and memory's lock use it. A command the web server runs for a write it judged the person's carries the server's vouch (`METAFORM_PAGE_VOUCH`), so the person's page write runs when an agent started the server. Not covered, and said in `caller.py`: an agent writing the home's files itself, importing the library, or starting a process through a service outside its own tree; outside Linux only the identity names count. A verb may also be the person's decision (`Verb.person_says`, see BASE-013).

### CLI-012 Module switches are declared once and are settings
- Requirement: a module declares each of its switches once, and that declaration is both the verb's switch and a setting.
- What this means: a module switch such as `--loud` is a setting owned by the module. The verb lists which settings it reads, and the parser accepts those settings as switches on that verb.
- Why: one declaration keeps a module's switches, settings and help in step, and makes every module switch storable with `set` the same way chassis switches are.
- How it shows: the hello module declares `--loud` once; `metaform hello greet world --loud` and `metaform set --loud` both work, and `help --loud` names the template as owner.
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
- How it shows: `cd ~/notes && metaform set --modules workflow` then `cd ~/notes/src && metaform config --show` shows modules workflow.
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
- How it shows: `metaform unset all` prints `Reset one setting: ...` or `Reset 2 settings: ...` and `Skipped (glued): ...`. `metaform unset all --unglue` prints the reset list and `Unglued: ...`.
- Build: `unset all` resets every setting whose owner is loaded, one by one under CLI-016's rule, and prints `Reset <count> <setting or settings>: <keys>`, the count written as PROJ-025 writes counts, `one setting`, `two settings`, `12 settings`, or `No settings required reset`, then `Skipped (glued): <keys>` and `Unglued: <keys>` when those lists are not empty. Scope of `all` is listed in the open questions.
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
  Next: If you are sure: metaform hello forget --confirm
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
- Acceptance: with an empty home, every chassis verb runs with exit 0 given valid nouns, and every hello verb that needs no project store runs with exit 0. A module verb that needs a project store, such as the template's greeting and history verbs, stops in an empty home with exit 2 and `Next: metaform add project <id> <path>`, STORE-023; no configuration is involved, since registering a project is data, not a setting. After `metaform add project <id> <path>` and nothing else, every hello verb runs with exit 0.
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
- Status: confirmed. Corrected 2026-09-27: the `modules` list is what an alias grew out of, CLI-039, and `set` is for configuration settings only, CLI-040; "empty means all" does not stand, CLI-037.

### CLI-022 Narrowing the command surface hides and blocks, and states the way back
- Requirement: commands outside the folder's command surface are neither shown nor run, on the CLI or over MCP, and the `set` that narrows the surface states the exact way back.
- What this means: `--modules` lists the modules whose commands a folder shows and runs; `chassis` names the chassis's own commands. It narrows what the folder shows and runs; it does not enable or disable any module. Help indexes, help pages and MCP tool lists omit hidden groups, and a hidden command fails with a Next line. The narrowing `set` prints which commands remain and the way back. An orchestrator narrows a worker's folder before the worker starts by naming that folder with a `folder=<path>` noun, PROJ-007.
- Why: removing commands from the surface holds even for agents with full permissions, where host permissions do not. The orchestrator that narrowed the surface holds the exact way back and acts with confidence; a subagent meets only the caution. The wording steers, and nothing gates inference.
- How it shows:
  ```
  Success: updated one key
    modules: all → workflow,memory
  Commands shown here: workflow, memory.
  All other commands and help, including yours, are now hidden and will not run.
  To restore them: metaform unset --modules
  ```
  When a workflow narrowed the surface, the last line names that workflow module's abort verb instead, D50. `metaform set --modules workflow,memory folder=~/wt/job1` stores the same value for that folder and prints the same lines, naming the folder at the end of the first: `Success: updated one key for <folder>`, or `Success: no changes for <folder>`.
  `metaform help --modules` says: `Narrows which modules' commands this folder shows and runs. It does not enable or disable modules; use metaform enable and disable for that.`
- Build:
  - The exact text of `set` output is owned here. Line 1: `Success: updated one key` when one setting changed, `Success: updated <n> keys` otherwise, the count written as PROJ-025 writes counts: `two keys`, `12 keys`. Then one line per change, `  <key>: <old> → <new>`, values shown per CLI-031's value rule, except that an empty `modules` value is shown as `all`, because empty means every group. Then `  glued: <keys>` when `--glue` was given. With no change: `Success: no changes`. When the new `modules` value is narrower than the old, three lines follow: `Commands shown here: <groups, comma and space separated>.`, `All other commands and help, including yours, are now hidden and will not run.`, and the way-back line below. `-q` suppresses all of it except errors.
  - A command group is shown when `modules` is empty or contains the group, where a group is `chassis` or a module id. `help`, `set`, `unset` and `config` always run, whatever the surface, so the surface can always be restored; `feedback`, `list reports` and `read report` always run too, so an agent can always report, BASE-045. `mcp serve` is the transport, not a command an agent runs, so it always runs, whatever the surface; `--modules` narrows which tools the server lists and runs, MCP-004. The same check filters the commands index, help pages, dispatch and the MCP tool list, MCP-004. Until D35 and D50 are answered, the way back line is `To restore them: metaform unset --modules`, which is the current text.
- Acceptance: after narrowing to one module, a chassis verb outside the surface exits 2 and is absent from `help commands` and from the MCP tool list.
- Relates to: CLI-008, CLI-021, MCP-004, BASE-016, PROJ-007.
- Status: confirmed for hiding and blocking, for the name `--modules` and its help text, and for the `folder=<path>` noun that stores the value for another folder. The way-back text depends on D35 and D50. Corrected 2026-09-27: narrowing by `set --modules` moves to forcing a menu on a folder and to aliases, CLI-038 to CLI-040.

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

  A switch sent another JSON type over MCP is read by its kind as a noun is, BASE-035, on a verb's call and through the `set` tool alike. A `str` or `select` switch sent a value that is not a string is not refused: the value is read as its JSON text, `json.dumps(value, ensure_ascii=False)`, the result carries the notice `<key> is text; what was sent was kept as its JSON text.`, and that text is then checked as `set` checks the typed word, so a `select` still has to name a choice. A `list` member that is not a string is read the same way, with the same notice once. An `int` or `bool` switch sent another type, and a `list` switch sent no array, cannot be read as that kind: the call stops with the command line's next step, `metaform help <switch>`, as `loud: "no"` does. The reason is BASE-044's line: an agent's submission is never refused for its content, and a number or an object sent where text goes is content with a text reading; `"no"` sent where a boolean goes has no reading as a boolean, on the CLI either, where `--loud` takes no value, so it is a call that cannot be read, which BASE-044 allows to be an error.
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
  Folder: /home/rich/notes/src
  Project: notes (/home/rich/notes), inherited from /home/rich/notes
  Target: path /home/rich/notes
  Metaform: main
  Projects: 2 registered
  Modules: 4 on
  Intake: none yet
    This project has no intake. Nothing else in Metaform works until it is done. First make sure the web GUI is running: ...
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
  Every `<n>` and `<m>` is written as PROJ-025 writes counts: `Projects: one registered`, `Modules: two on`, `Metaform: main, two in project`.
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
- How it shows: `metaform help set` and `metaform help hello greet` have the same section order.
- Build:
  - Page: `<name>: <summary>`, blank line, description when present, `Usage` and each usage line indented two spaces, `Switches` and one row per switch with its one-line help, `Caution` for a caution verb, `Details` when present, `Examples` with each example and its meaning on the next line indented four spaces, then `See also: <names>`. Empty sections are left out.
  - Syntax: `Usage: <first usage line>`, further usage lines aligned under it, a blank line, then one row per switch including `-h, --help  Show this syntax.`
  - Module page: `<id>: <summary>`, blank line, the module's purpose, `Verbs` with one row per verb, `Settings` with one row per owned setting, `Details` when present, and `Use 'metaform help <id> <verb>' for one verb.`
  - Rows: the left column is padded to its widest entry of at most 40 characters, plus two spaces. An entry longer than that goes on its own line with its help on the next, under the others' help, so one long usage never widens every row.
  - Switch page for a setting: `<switch>: <help>`, details, `Usage` with `metaform set <switch>` and `metaform unset <switch>`, the choices for a select, and `Owner: <owner>. Kind: <kind>. Applies to: this folder` or `everywhere`.
  - `metaform help agents` prints the composed instructions of MCP-007 for the folder. `metaform instructions` prints the same text and runs whatever the folder's command surface, as the `metaform` tool's `instructions` command does over MCP, 2026-10-02.
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
- Build: Every error below is a `Stop` with its one Next line, CLI-009. `-q` and `--quiet` suppress success output on `set` and `unset`. An empty `modules` or `layers` is shown as `all`, and set to the word `all` it is cleared, so what is shown and what is typed mean the same: stored as the word, it named no module and no layer and turned every one off, with nothing on the screen to say why, found 2026-09-28. `--json` prints the result as JSON, BASE-036, on `list`, `config --show` and `query`.

  | Verb | Nouns and switches | Output and errors |
  |---|---|---|
  | `help` | none; `intro`; `commands`; `switches`; `agents`; a switch such as `--loud`; a chassis verb; a module id; a module id and verb | The overview, CLI-006; the intro, CLI-006; the indexes, CLI-008; the composed instructions, MCP-007; the pages, CLI-029. Unknown thing: `No command, module or switch <thing>.` Next `metaform help commands`. |
  | `add` | `project <id> <path> [<target type> <target value>]`; `metaform <name> [<project>]`; `origin [<project>]`; `variant <folder> [origin=<id>] [remove=true] [module=] [workflow=] [prompt=] [model=] [role=] [blinded=true|false]` | project: STORE-031. Success: `Added project <id>: <path> (target <type> <value>)`. metaform: STORE-041, with the output stated there. origin, PROJ-014: `Added origin <mform_id>, repo at commit <commit>.` or `Added origin <mform_id>, folder copied from <path>.`, then `Uncommitted work was collected as variant <id>.` when it was; the same content again: `Origin <mform_id> already holds this content; nothing was added.` variant, PROJ-017: `Collected variant <id> of origin <mform_id>: <n> files changed.` |
  | `list` | `projects`, `modules`, `metaforms [<project>]` (STORE-041), `reports [<project>]` (BASE-045), `origins [<project>]` or `variants [origin=<id>]` (PROJ-024) | projects: one line per project, `<id>  <path>  <target type> <target value>`, ids padded to the widest; none: `No projects yet. Register one: metaform add project <id> <path>`. modules: BASE-037's line per module, `<id>  <on|off|error>  <system|user|entry>  <summary or reason>`, ids padded to the widest. origins: `<mform_id>  <repo|folder>  <commit or source path>  <established>  <n> variants`. variants: `<id>  <collected>  <source path>  <workflow or ->`. Any other noun: `list needs a noun: projects, modules, metaforms, reports, origins or variants.` Next `metaform list projects`. |
  | `set` | one or more setting switches with values, CLI-011 and CLI-015; `--glue`; `-q` | Success output: exactly as CLI-022's Build states, which owns the text of `set` output with or without narrowing. A word that is not a switch: `set takes switches, not '<word>'.` Next `metaform set --help`. An unknown switch: `<switch> is not a setting.` Next `metaform help switches`. An invalid value: the error of CLI-027 with Next `metaform help <switch>`. |
  | `unset` | one or more setting switches, or `all`; `--unglue`; `-q` | `Reset one setting: <keys>`, `Reset two settings: <keys>`, `Reset 12 settings: <keys>`, the count as PROJ-025 writes counts, or `No settings required reset`, then `Skipped (glued): <keys>` and `Unglued: <keys>` when they apply. `--all`: the error and Next line of CLI-002, which owns that text. |
  | `config` | none; `--show`; `--show --json` | none: the settings screen, CLI-026, or `--show`'s output without a terminal. `--show`: one line per setting in schema order, `<mark> <key>: <value>` with `*` as the mark for glued and a space otherwise, followed by `  (set)` or `  (glued)` unless default, then a blank line and `* glued: kept by unset all until unglued.` `--json`: a list of objects with key, switch, owner, kind, value, state, default and help. |
  | `activate` | `metaform <name> [<project>]` | STORE-041, with the output stated there. Unknown name: `No metaform <name> in <project>.` Next `metaform list metaforms`. |
  | `enable`, `disable` | `<module>` | `Module <id>: on` or `off`. Unknown id: `No module <id>.` Next `metaform list modules`. Writes the `module_state` row, STORE-002. |
  | `feedback` | BASE-045 | As specified there. |
  | `read` | `report <file name> [<project>]` | BASE-045. Unknown file: `No report <name>.` Next `metaform list reports`. |
  | `install`, `uninstall` | MCP-013 to MCP-020 | As specified there. |
  | `build` | none | BASE-041. |
  | `import`, `export` | STORE-027 | As specified there. |
  | `query` | STORE-028 | As specified there. |
  | `prompts`, `prompt` | `prompts`; `prompts review`; `prompt <name> [<version>]`; `prompt save <name> <text\|-> [format=<text\|markdown\|xml>] [parent=<version>] [--json]`, STORE-044 | prompts: one line per prompt, `<name>  <format>  version <newest>`. prompt: the version's text exactly, the newest unless a number is given. save: the saved version record, with an unchanged-text notice when no version was added; `-` reads standard input. Unknown prompt: `No prompt <name>.` Next `metaform prompts`. |
  | `extract` | `<variant id>... <folder>` or `all <folder>`, `[origin=<id>]`, PROJ-018 | `Extracted into <folder>` for each folder written. A folder that is not empty: `<folder> is not empty.` Next `metaform extract <variant id> <empty folder>`. No origin: PROJ-024's error. |
  | `clear` | `project [<project>]`; `--confirm` | PROJ-025: without `--confirm`, the caution and Next `If you are sure: metaform clear project <project> --confirm`; with it, `Cleared <project>: <metaforms> and <report files>. Its registration, folder, settings, origins and variants stay.`, where `<metaforms>` is `no metaforms`, `one metaform, main,` or `two metaforms, main and fresh,` and `<report files>` is `no report files`, `one report file` or `two report files`, counted as PROJ-025 counts. |

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
- Status: confirmed for the hierarchy. Extended 2026-09-27 by CLI-037: the top menu shows names only, and a module's commands are shown when it is entered.

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
  notes-foresight layer   map   foresight        ready   off
  memory          memory  memory                 ready   on
  $ metaform unset --layers
  Reset one setting: layers
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
- How it shows: `metaform set --debug` adds the request for feedback to the instructions an agent reads when it connects, MCP-029. The intake text is served alone, BASE-039, so neither setting changes it.
- Build: `settings.boolean('debug', False, scope='folder', help='Ask agents doing Metaform work for feedback and trouble reports on the Metaform process.')` and `settings.boolean('report', True, scope='folder', help='Ask the intake agent for a report on the project it examined.')`, both owned by the chassis. The composed instructions, MCP-029, read `debug` for the folder. Nothing reads `report` since 2026-09-29, when the lines appended to the intake were removed, BASE-039: where the request for a project report is made, now that it is not side loaded into the intake, is open. Submitted feedback and reports are stored whatever the settings, BASE-044.
- Acceptance:
  - The intake text served is the same whatever `--debug` and `--report` are.
  - `metaform set --debug --glue` then `metaform unset all` leaves `debug` on.
- Relates to: CLI-011, CLI-015, BASE-039, BASE-044, BASE-045, MCP-007.
- Status: confirmed, including the defaults: `--debug` off and `--report` on. During development the orchestrator turns `--debug` on for its own runs. The names `--debug` and `--report` are recommended.

### CLI-035 The command line follows mvm's design
- Requirement: The Metaform command line works as mvm does, the command line whose settings pattern this section follows: its command index, its help pages, and `set`, `unset` and `config`, except where a record of this section decides otherwise.
- What this means: mvm's design is the pattern. Help lists the commands in grouped sections, one full-length line each, then a footer naming the help command, then tips. `help <command>` and `<command> --help` give one page each: a summary, a description, when to use the command, usage, subcommands, the switches one line each, details, examples each followed by an indented explanation, and see also. `help <switch>` explains a switch across commands. `set --<key> <value>` takes `--glue` and `--quiet` and answers in plain text, such as `Success: no changes`; `unset --<key>` and `unset all` return keys to their defaults, and glued keys stay unless `--unglue` is given. `config` opens the settings screen, and `config --show` prints `key: value` lines. Where a record of this section decides otherwise, the record governs: `metaform` alone shows status, CLI-005; `metaform help` is a brief overview ending with tips, and the full index is `help commands`, CLI-006 and CLI-008; every error ends with one Next line and exit 2, CLI-009. mvm leaks its argument parser's usage on an unknown switch to `set`; that is not copied. mvm's `config <group>`, which opens one group of the screen, and `config --wizard`, a guided setup, and the page sections for when to use a command and for its subcommands, which CLI-029's page does not have, are open, D97.
- Why: A command line copied from a working design is settled in full, so a builder has nothing left to reinterpret, and a person who already uses mvm knows Metaform's command line without learning it.
- How it shows: `metaform help set` and `mvm help set` give pages of the same shape; `metaform unset all` keeps glued settings as `mvm unset all` does.
- Build: The records of this section, CLI-001 to CLI-034, are that design; each difference from mvm is one of the decisions named above.
- Acceptance: None of its own; each record's acceptance protects its part.
- Relates to: CLI-005, CLI-006, CLI-007, CLI-008, CLI-009, CLI-016, CLI-017, CLI-026, CLI-029, CLI-036.
- Status: confirmed, 2026-09-21. The later decisions named above, 2026-09-24, govern where they differ. `config <group>`, `config --wizard` and the two page sections are open, D97.

### CLI-036 Everything a person reads is short, whole and plain
- Requirement: Every text a person reads or needs to understand, on the command line and in help, status, errors, notices, the web GUI and the documentation, is meaningful, short, never cut off, and written to one writing standard.
- What this means: Help for a feature says what needs to be done to use it, not only what it is. Text is never cut off mid-thought: an entry too long for its column goes on its own line, CLI-029. Commands are organized, CLI-032. The writing standard is a set of plain-writing rules; its text is not yet in this repository, D98.
- Why: A person must understand what the tool says on the first read. Text that is padded, cut off or vague makes them reread, guess or go to the source, and an agent reading the same text does the same.
- How it shows: No help line ends mid-word or in an ellipsis, and each help page says what to do to use its feature.
- Build: The critic review, QUAL-008, checks every string a person reads against the standard.
- Acceptance: Checked in the critic review, QUAL-008.
- Relates to: CLI-006, CLI-007, CLI-029, CLI-032, CLI-035, QUAL-008.
- Status: confirmed, 2026-09-21; help saying what needs to be done to use a feature, 2026-09-11. Where the standard's text is kept is open, D98.

### CLI-037 The top menu shows names, and a module's commands are reached inside it

- Requirement: The first thing a person or an agent meets is the top menu, which shows one name for each thing that can be entered and none of the commands beneath it. A module's commands are written `<module> <command>` and are shown when the module is entered.
- What this means: The top menu is kept as small as possible. Each module is one name, and each alias, CLI-039, is one name. Typing a module's name, or asking for its help, shows that module's commands. `map where` is the command `where` of the module `map`: the command is a subcommand of the name, so a module reads as one command with everything it does beneath it. A command's switches are shown by that command's help and are not sent ahead of need. Over MCP it is the other way: every command is a tool of its own, `<module>_<command>`, with its arguments in its schema, MCP-003, because a host lists, validates and grants tools, and a menu entered by calls hides the commands from all three.
- Why: Whatever is at the top is paid for by every session, whether the work uses it or not, so each thing placed there is a cost charged to everyone. Metaform exists to spend an agent's orientation in advance; a surface that hands an agent every command when it connects spends that saving before the work begins. A reader shown every command must also weigh each one against its task, and most have nothing to do with it. The cause of clutter is structural: a rule that adds one entry at the top for each command makes the top grow with every module anyone writes, so it returns however often it is cleaned. One name for each module means a new module adds one line.
- How it shows: The top menu lists `intake`, `map`, `mcp`, `memory` and `web`, one line each. Entering `map` lists `map roots`, `map where` and the rest of its commands. Over MCP the tool list holds `map_roots`, `map_where` and every other command, each with its own arguments.
- Build: On the command line a module's command is `metaform <module> <command>`, and `metaform help <module> <command>` shows its page; `metaform <module>` and `metaform help <module>` enter the module. No colon form is read: `metaform map:where` is an unknown command. Over MCP: built 2026-09-28 in `entries` and `enter` of `src/metaform/modules/mcp/server.py` as one tool per module taking `command` and `arguments`, with the chassis's own commands under one tool named `metaform`, which answered question 14 for MCP; a call with no command entered the module, and `help` with a command's name gave its schema. Measured then with four modules on: five tools under 6,000 bytes where 64 tools, one per verb, had been 55,139. Replaced on 2026-10-11 at the owner's request that each command be its own tool, described once where it is listed, with typed arguments, MCP-003: `listing` in the same file lists `<module>_<command>` for each surfaced verb and `metaform_<command>` for the chassis's own, sorted, and a call runs its command directly. The wrapper's two extra calls before a command's first use are gone, and a host can again grant one command and withhold another. The cost moved to the tool list: 123 tools of 114,095 bytes on this project with the shipped modules that ship enabled, where the module tools were 7,542 bytes with every schema behind `help`. Where the chassis's own commands sit on the command line is still open, question 14.
- Acceptance: Open with the build. It will hold that the top menu's size does not change when a command is added to a module.
- Relates to: CLI-032, CLI-038, CLI-039, CLI-040, MCP-003, MCP-004, MCP-029.
- Status: confirmed as design for the command line, 2026-09-27; over MCP replaced by one tool per command on 2026-10-11, MCP-003. It corrects MCP-003 and MCP-004, which serve every command of every module at once. 2026-10-01: the colon belongs only to Claude Code's user-facing `/<server>:<prompt>`, which runs an MCP prompt; Metaform writes and reads no `<module>:<command>`, and the colon form built 2026-09-30 is removed. The context flow was reorganized 2026-10-02 at the owner's request, without changing any prompt's meaning, from baseline commit 4c84d7c. Built that day: the MCP listing had sent every command's argument schema with its descriptions when a tool was opened, which this record's rule, that a command's switches are shown by its help and not sent ahead of need, already ruled out. Opening a tool now returns each command with its one-line summary only; the tool's `help` argument, given a command's name and no `command`, returns that command's summary and the schema of what it takes, from the same declaration. Measured on this project: opening map went from 30,460 characters to 3,522, intake from 26,213 to 1,753, memory from 11,631 to 1,794 and metaform from 9,107 to 2,147; reading one command costs 227 to 5,723. The tools/list descriptors grew from 4,331 to 4,829 for the `help` argument.

### CLI-038 The working folder decides what is shown, and holds the continuity of the work

- Requirement: Metaform is aware of the working folder. What an agent is shown and can run is decided for the folder it works in, and the record of the work done in a folder stays with the folder.
- What this means: A module's menu is reached in two ways: the orchestrator forces a menu on a folder before a worker starts there, or an agent enters a module by its name. No agent identity is tracked. An agent that starts work in a folder receives what was done there before and carries it on, whichever agent it is.
- Why: An agent has nothing lasting that identifies it: subagents of one session share its session id and process id, so a design that depends on knowing which agent is which fails or needs a token the agent can lose or pass on. The folder is a fact the orchestrator sets and the agent does not control, so it can be relied on to say what the agent there is meant to be doing. Continuity is the history of the work, and a history kept with the place reaches whoever continues the work without anything having to be proved. Deciding by folder is also what keeps an agent from widening what it was given by asking for more.
- How it shows: An orchestrator forces the `map` menu on a worker's folder; the worker there meets the `map` commands. A second agent that later starts in the same folder is shown the same menu and the record of the first one's work.
- Build: Open. The folder table and the `folder=<path>` noun of CLI-022 and PROJ-007 already store values for a folder. The command that forces a menu is open, question 15.
- Acceptance: Open with the build.
- Relates to: CLI-021, CLI-022, CLI-037, PROJ-007, MCP-012.
- Status: confirmed as design, 2026-09-27.

### CLI-039 An alias is one top-level name that stands for several modules

- Requirement: The orchestrator can define an alias, a name at the top menu that stands for two or more modules, and entering it gives the commands of all of them.
- What this means: An alias is a convenience for work that crosses modules. It is one more name at the top menu, beside the module names.
- Why: Without it, the only answer to an agent that needs three modules is to show it everything, which brings the clutter back. An alias gives that agent what its work needs under one name and keeps the top menu short.
- How it shows: An alias `mapping` for `map` and `memory` appears at the top menu as one line, and entering it lists the map and the memory commands.
- Build: Answered 2026-10-03, question 16: its own chassis command, `metaform alias <name> <module> <module>...`, stored per folder in the folder table and given `folder=<path>` for a worker folder, like CLI-022. Built 2026-10-03 in `src/metaform/aliases.py` and `alias` and `run_alias` of `src/metaform/cli.py`.
  - Storage: the `aliases` table of STORE-002, one row per module, keyed by the folder's `folders.path_key`, in the database that holds that folder's settings, PROJ-026. The folder row is written with it.
  - Defining: `metaform alias <name> <module> <module>... [folder=<path>]` prints `Success: <name> stands for <modules>`, or `Success: in <folder>, <name> stands for <modules>` with `folder=`. A module named twice counts once. Defining a name again replaces what it stood for at that folder. Refused, each with one Next line: fewer than two modules, `alias needs a name and two or more modules.`; a name that is not a lowercase letter followed by letters, digits, `-` or `_`; a name that is a chassis command, a reserved word, a module id or `metaform`, the tool of the chassis's own commands over MCP, `<name> is already a command.`; a module that does not exist, `No module <module>.`
  - Resolving: an alias defined at a folder holds there and in every folder below it, the nearest folder's definition of a name winning, as a folder setting does, CLI-014. A module installed later under the alias's name comes first.
  - The command line: `help commands` ends with an `Aliases` section, one line per alias naming the modules it stands for. `metaform <name>`, `metaform <name> --help` and `metaform help <name>` print what `metaform <module> --help` prints for each of its modules, in its order. Words after the name are refused with `Next: metaform <name>`: the commands it lists run by their module's name.
  - MCP: an alias adds no tool. Every command of its modules is a tool of its own, MCP-003, so a name standing for several modules has nothing left to gather; defining one changes no tool and announces nothing, MCP-004. Built so on 2026-10-11; from 2026-10-03 the alias was one more tool whose commands were written `<module> <command>`, the form the owner's open point below asked about.
  - The command surface: an alias shows and lists only its modules that are loaded and on the folder's surface, CLI-022; with none of them it is not shown, and entering it fails with `Next: metaform unset --modules`.
  - The owner's 2026-10-03 answer leaves four points open, asked at the join `code.chassis` to `code.interface.command_line`, message 0485ecfb01b948cb9313ee179f96a409: how an alias is removed, which is not built; and whether the inheritance to folders below, the MCP form above, and an `aliases` table keyed by the folder table rather than a column of it, are what he meant. Each is built as described here until he answers.
- Acceptance: In `tests/test_cli.py`: an alias is one line under `Aliases` in `help commands`, entering it in each of its forms prints its modules' listings, defining it again replaces it there and in the index, and a module named twice counts once; every refusal above gives its exact Error and Next lines and stores nothing; a module installed under an alias's name runs in its place; `folder=` defines it for a worker folder, it holds below that folder and the nearest definition wins; its rows and folder row are in the project's `project.sqlite3` for a folder inside a project; it shows only the modules that are loaded and on the folder's surface and is refused when none are. In the mcp module's tests: defining an alias adds no tool and the commands of its modules run as their own tools, equal to the command line's; in a running session defining it announces nothing and narrowing the surface removes the narrowed modules' tools with one tool list change.
- Relates to: CLI-014, CLI-021, CLI-022, CLI-037, CLI-038, STORE-002.
- Status: confirmed as design, 2026-09-27. Built 2026-10-03; the open points above wait on the owner.

### CLI-040 `set` and `unset` are for configuration settings only

- Requirement: `set` and `unset` store and clear configuration settings, the same settings the settings screen edits, and do nothing else. They are not how a module is entered.
- What this means: Entering a module, forcing a menu and defining an alias are acts of their own, CLI-037 to CLI-039.
- Why: A command with one meaning can be read without knowing its history. If `set` both configures and moves an agent between menus, a person reading a folder's settings cannot tell a preference from a place, and an agent that changes a setting may change what it can reach without meaning to.
- How it shows: Every key `set` accepts is a row of the settings screen, CLI-026.
- Build: Open. Today `set --modules` narrows a folder's command surface, CLI-022; that use moves to the acts of CLI-038 and CLI-039.
- Acceptance: Open with the build.
- Relates to: CLI-010, CLI-021, CLI-022, CLI-026, CLI-038, CLI-039.
- Status: confirmed as design, 2026-09-27.

### CLI-041 `metaform start` maps the project in this folder with one command

- Requirement: `metaform start`, run in a person's own project folder, takes them to their project's map in the browser, asking only what the project's files cannot say, at most two short questions.
- What this means: It chains what exists, each with the default that asks nothing: registration, the MCP connection, the intake agent dispatch starts, and the web GUI. Run again, it does nothing already done and opens the page again.
- Why: A person who has just installed Metaform should see their own project as a living map in a couple of minutes, without a pile of questions.
- How it shows, in order, one line each:
  - `Project: <id>, registered for <folder>.` The id is the folder's name made into a project id, `home.project_id_for`, the rule the MCP register tool uses; a name another folder holds takes the next free number. A folder already inside a project says `Project: <id>, already registered.`
  - `Modules: turned on <ids>.` when any of map, intake, mcp, web and dispatch is off; dispatch ships off.
  - With Claude Code on PATH: `Claude Code: wrote the metaform MCP server into <folder>/.mcp.json; Claude Code asks once to use it.` The entry is `mcpServers.metaform` = `{"type": "stdio", "command": ..., "args": [...], "env": {}}`, Claude Code's documented project-scope form, merged into a file that already holds other servers, the old file backed up under the home's `backups/start/`. The command is `metaform mcp serve` when `metaform` is on PATH, `uvx --from <wheel> metaform mcp serve` when Metaform runs from a wheel, else this Python with `-m metaform mcp serve`. Nothing is written when `metaform install` already registered Claude Code for every folder, or the entry is already there. Another AI tool found is named with `metaform install <tool>`; none found gives two lines saying so and how to connect one later, and it carries on.
  - `Read: <languages>, <n> code files; <file> says what it is.` from the files alone: the README's first paragraph or a manifest's description (pyproject.toml, Cargo.toml, package.json), the name a manifest gives, the languages by extension, the top folders and the manifests present. A folder with no code says `no code yet (<n> files), so the map records intent only.`
  - The questions, only at a terminal and never in an agent's run: `What is this project for, in a sentence?` when nothing says what it is (`What will this project be, in a sentence?` with no code), and `Who is it for?` only for a folder with no code. An empty answer skips.
  - `Intake: <agent> is mapping the project; the page shows each part as it is recorded.` The intake agent is started by `dispatch intake` with the chassis prompt `start_intake`, or `start_intent` for a folder with no code, filled with what was read and answered. The agent is the AI tool found among claude, codex and gemini unless the person chose `dispatch_agent`. A mapped project says `Intake: the map is recorded; opening it.`; one being recorded, or an intake agent already running, is left to finish. An agent that cannot start is said with its next step, and the page still opens.
  - `Map: <address>#p=<project>`, after the browser is opened on it once. Nothing opens without a desktop, in an agent's run, or where the only browser found is a terminal one; the line then ends `(open it in your browser)`.
- The page: the map follows the intake as each part is recorded, VIEW-018. When an intake the page followed finishes, one card at the top of the map offers the next step: `Start an agent on a ticket`, which opens the board, and `Chat with your system agent`, which opens the chat.
- Build: `src/metaform/start.py`, the chassis verb `start` in `cli.py`; the card is `offerNext` in `page/app/intake/intake.js`, called from `follow` in `page/app/live/stream.js`.
- Acceptance: In `tests/test_install.py`: a first run in a scratch home registers the folder by its name, turns dispatch on, writes the `.mcp.json` entry, starts the web GUI and the intake agent with the brief, and asks nothing without a terminal; a second run changes nothing and starts no second intake.
- Relates to: CLI-006, MCP-009, MCP-010, VIEW-002, VIEW-018, VIEW-045, BASE-039.
- Status: built 2026-10-14, start onboarding, ticket code.installer.package#d (b0ceca010322499289cd998bac0724d7).
- Amendment, 2026-10-15, start says what really happened, ticket 7f3f4583613143009984b3f38658eeb8 (code.installer.package#13), findings 1, 2, 8 and 9 of artifacts/critic/2026-10-15-round7/onboarding.md, built by a Claude agent on that ticket and recorded to match the code: start checks and turns on the modules first, then registers the folder, so a Metaform without them registers nothing; the order of its lines is `Modules:`, `Project:`, `Claude Code:`, `Read:`, `Map:`, then the intake. With no AI tool found and no `dispatch_agent` chosen it starts no agent, so nothing is fetched with npx, and says `Intake: not started; no AI tool here can run it.` with `Install Claude Code, then run metaform start here again`. Otherwise it says `Intake: starting <agent>`, starts it with `dispatch intake wait=true`, and says `<agent> is mapping the project` only once the agent has made its session; an agent that did not start is said as `Intake: <agent> did not start: <why>` with its next step, `metaform dispatch login <agent>` for a login, else its runner's log. The runner leaves an ended session row, `start-<runner>`, holding why, when its agent never made a session, so the ticket, the page and start read it, and the launch gives back its slot. The answers to start's questions are kept in `<home>/start/<project>.json` and used by the next start there, which does not ask them again. Why: start told a person an agent was mapping when none could start, fetched an agent from npm with no AI tool present, and lost the answers.

### CLI-042 `metaform demo` shows Metaform at work with one command and no questions

- Requirement: `metaform demo`, run anywhere right after installing, opens a sample project's living map in the browser with agents at work on it, within 30 seconds, asking nothing and needing no AI tool, API key or account.
- What this means: It runs in a home of its own, `demo` inside the Metaform home: `cli.main` points `METAFORM_HOME` there, and drops any agent session's identity, before the command reads a home, so the person's projects and settings are never read or written and every process it starts inherits that home. Run again, it reuses that home; `metaform demo --reset` removes it first. A second `metaform demo` while one runs is refused and names the running one's address.
- How it shows:
  - The sample is Pocket Ledger, a small expense command line (`ledger/cli.py`, `amounts.py`, `store.py`, `report.py`, README) with a planted bug: `parse_amount` truncates `int(float(text) * 100)`, so 19.99 is stored as 1998 cents. Its finished map, eight elements and eight purpose records with a `sources` layer naming each file, ships as an export document, `src/metaform/demo/map.json`, imported on the first run, so no intake runs.
  - The first run copies the sample into the demo home, registers it, imports the map, turns dispatch on and sets `dispatch_claude`, `dispatch_codex` and `dispatch_gemini` to the demo agent, `python -m metaform.demo.agent`, a standard-library ACP agent with no model, promoted from dispatch's test fake. Nothing the demo starts calls a model or a network service or costs money.
  - It starts the web GUI on a free port, never 7433, opens the browser once and prints, one line each: the demo's home, `The map of Pocket Ledger, with three demo agents at work: <address>`, and how long it took, whether the browser opened, and that Ctrl+C stops it. Each line is flushed, so a pipe shows it at once.
  - Three tickets are worked, one per lane: `Monthly totals come out a cent short` at `code.parser.amount`, `Show each category's share of the month` at `code.report.monthly`, `A crash while saving can empty the ledger` at `code.store.ledger`. Each agent plays its ticket's script from `script.json` once: sentences streamed as message chunks, which the page shows in its figure's speech bubble from the server's `said`; file reads as tool calls naming the file, which dispatch places through the `sources` layer, so the flow draws them reaching those parts; and its plan, steps, a memory and the ticket's close through the real `metaform` command line. The agent at the amount parser finds the bug, checks it with Python, records it and closes its ticket. A closed ticket's lane rests 10 seconds and a fresh ticket is worked there; one worked 240 seconds without closing is started again, so someone who arrives late still sees agents at work.
  - The person's system agent is the demo agent too: the page gives it its body as soon as its conversation runs, so the mascot walks out and says `Here I am.`, then greets the person with `web say` and waves, and says a line about the map every 40 seconds.
  - One small card in the lower right of the page, over the side panel and above its Chat button, so it covers no part of the map, says what the person is looking at in two lines and offers the next steps, each a command to copy: `Connect Claude Code: metaform install claude` and `Map your own project: cd <your project> && metaform start`, CLI-041. It can be closed. The web GUI serves it as `GET /api/demo` from the home's `demo.json`, and `{demo: null}` in any other home, where the card is never drawn.
  - Ctrl+C at any point stops the demo agents and the web GUI and says `Stopped.`
- Build: `src/metaform/demo/` (the command `__init__.py`, the agent `agent.py`, `script.json`, `map.json`, `sample/`), the chassis verb `demo` in `cli.py`, `demo_card` and `/api/demo` in `modules/web/server.py`, and the page part `page/app/demo/demo.js`.
- Acceptance: In `tests/test_cli.py`: the demo runs in `home/demo` without an agent's identity and puts both back; its project comes from the package with its map finished, the bug in place and the demo agent as every agent's command, and a second run reuses it without running anything; the person's home holds no project of the demo's; a second demo is refused naming the running one, and `--reset` is its only word. In `modules/web/tests/test_web.py`: the card is served only from the home the demo wrote it in.
- Relates to: CLI-041, MCP-009, VIEW-002, VIEW-005, VIEW-035, BASE-052.
- Status: built 2026-10-14, demo onboarding, ticket code.installer.package#c (ab78d1bfdf51458c86d67ab9c127dd46).
- Amendment, 2026-10-15, ticket 7f3f4583613143009984b3f38658eeb8 (code.installer.package#13), findings 1, 2, 8 and 9 of artifacts/critic/2026-10-15-round7/onboarding.md, built by a Claude agent on that ticket and recorded to match the code: the card's next step is one, `Map your own project and connect Claude Code to it: cd <your project> && metaform start`, and the mascot's greeting and `metaform help demo` name the same, so the README, the demo and start connect Claude Code the one same way, the project's `.mcp.json`. The demo stops with one sentence, before it copies anything, when the build carries no map, dispatch or web module. `metaform` in a folder with no project now also offers `Watch it first: metaform demo` and `Map this folder: metaform start`, and `metaform help` lists `metaform demo` among its common commands.
- Amendment, 2026-10-15, ticket 93404d2f8d7743c1b9ca89662b0d8f3e (code.installer.package#14), findings 3 to 7 and 11 of artifacts/critic/2026-10-15-round7/onboarding.md, built by a Claude agent on that ticket and recorded to match the code: only one lane rests at a time. A lane whose ticket closes while another lane rests starts a fresh ticket at once, so the three lanes, whose scripts take about as long as each other, no longer rest together and leave the map with no agent. The demo opens the page as `metaform start` does (CLI-041): only in a desktop browser, never a terminal one such as w3m or lynx, and never in an agent's run. When nothing opens it says `Open that address in your browser.` Ctrl+C now also runs `metaform dispatch reset` after stopping the agents, and every run runs it once more before it serves. A ticket a stopped agent held stays taken by design, so without the reset the next `metaform demo` stopped with `Work … is already taken`. The page shows `Loading the map…` from its first paint until it is laid out (VIEW-002). Acceptance: `test_a_demo_lane_whose_ticket_closes_while_another_rests_starts_at_once`, `test_a_demo_stopped_or_killed_leaves_no_ticket_taken_for_the_next_run`. Evidence: artifacts/perf/2026-10-15-installer-14/.

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
11. NEW mvm's `config <group>` and `config --wizard`, and its help page's sections for when to use a command and for its subcommands: are they wanted? D97. (CLI-035)
12. NEW Where is the writing standard's text kept? D98. (CLI-036)
13. ANSWERED Metaform has no `<module>:<command>` form, 2026-10-01; over MCP each command is its own tool, `<module>_<command>`, since 2026-10-11. (CLI-037, MCP-003)
14. NEW Where do the chassis's own commands, such as help, config, install and export, sit: at the top menu beside the module names, or under one name of their own? (CLI-037)
15. NEW Which command forces a menu on a folder? (CLI-038)
16. ANSWERED Its own chassis command, `metaform alias <name> <module> <module>...`, stored per folder in the folder table, with `folder=<path>` for a worker folder, 2026-10-03. How an alias is removed is still open. (CLI-039)
