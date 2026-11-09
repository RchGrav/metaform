# Topogee CLI and settings design

**State:** draft, 2026-11-06. Written by Claude (Opus 5.5). The founder has not reviewed it.

## Foundation: the founder's design guidance

The founder's own document, "Design Guidance with Real Examples" (2025-10-10), is the primary source. It is copied word for word in `docs/owner-design-guidance.md`. It was written for meshvm, so its commands are examples; its principles are what carry over.

**The three absolutes:**

- **Never a blocker.**
- **No tech debt.**
- **Always resettable.**

**The meta-rule:** patterns, not laws. Use a pattern where it lowers friction, and do not enforce it where it does not help.

**The principles:**

- **Defaults are home, not a void.** Resetting takes you back to a fully working state, never to nothing. "When in doubt, reset. Baseline is not 'empty'—it's *ready*."
- **The TUI and the CLI are the same tool.** The TUI is a lens on the same state the CLI changes, with no drift between them. "Script everything; discover via TUI."
- **A switch of the same name as a command is a temporary mode.** A command is an action. Flip the mode on for an activity and off when done; `unset all` is the breaker. "Switches are impulses. Flip them for a task, not for life."
- **Guided, not guessed.** Humans can pick by number; scripts can pick by ID.
- **Best-effort integrations never block.** If an optional part is missing, degrade and keep going.
- **Everything leaves a trace.** "Debugging is a read, not a séance."
- **Help is a map, not a maze.** "If you need a compass, we failed."

## Sources

- **The founder's guidance** above.
- **The settings and menu system of c3lab's `mvm`,** described in full by the Claude session working in c3lab. The founder confirmed to that session that the defaults and menu approach is his personal design, not part of the Crius product, and that c3lab's settings are examples only. That session also named mvm's weak points; they are listed under "Not copied".
- **Two rules are the founder's grammar,** from c3lab commit `efa55444`: `all` is a noun, and one schema drives set, unset and help.

**Topogee's own rules still apply:**

- **R-5.14:** every MCP tool can be used through the CLI, not the reverse.
- **R-5.15:** a CLI command is not an MCP tool by default.
- **R-5.16:** the CLI is hierarchical, each module owns a branch, and each level shows only what it offers.
- **R-5.17:** every command is one complete line.
- **R-4.8:** settings are global unless a project overrides them, and defaults are never stored.
- **The founder, 2026-11-06:** MCP is for data manipulation and reading data; CLI commands do not go into MCP.

## Rules

Each rule gives its reason.

- **A plain "Why:"** traces to the founder: his design guidance, his commit `efa55444`, or the test he recorded his grammar in.
- **"Why (Claude's reasoning):"** is reasoning by Claude, this session's or the c3lab session's, from mvm's behaviour. It is not the founder's.

### Declaration

**C-1. Declare once, derive everything.**

- **A setting** is one schema entry: key, type, default, group, label, description, choices or bounds, a format check where one applies, and its switch names.
- **A command** is one declaration: path, category, summary, usage, positionals, switches, examples and handler.

Dispatch, help, completions, validation, the settings TUI and its groups are all generated from these declarations. A module adds its CLI branch and its settings by declaring them as data, alongside its other declarations (`metaform-server-design.md`, "Modules and the data controller").

*Why:* this is the founder's design. In mvm, every hand-written second list drifted from the declarations:

- the shell's `unset` flags, so `unset --nodes` reset the wrong setting;
- help entries for switches that did not exist;
- checks hard-coded by key name;
- menu groups, so `verify` settings appeared nowhere.

**C-2. Help equals behaviour.** Help never lists a switch the command refuses, and the command never accepts a switch help does not list. A test adds a probe setting and a probe command, then asserts each appears in dispatch, help, completions and the TUI with no other edit.

*Why:* mvm's help documented four `unset` switches that did not work, and said `config --show` prints JSON when it does not. Users and agents trust help literally.

### Grammar

**C-3. The object of a verb is positional, never a switch.** That covers `all`, identifiers, a setting's key and a file to load: `topogee settings unset all`, `topogee metaform import design.json`.

*Why:* this is the founder's grammar. A switch says how a verb runs; a positional says what it acts on.

**C-4. One name per switch, and no prefix abbreviation, on every command.**

*Why (Claude's reasoning):* abbreviations make each new switch a possible breaking change, and make scripts ambiguous. mvm turned them off on `unset` only, so `set` still accepted them.

**C-5. Booleans come as a pair: `--x` and `--no-x`.** There is never `--x=false`.

*Why (Claude's reasoning):* the pair is symmetric, and either name finds the setting.

**C-6. One identifier-list grammar everywhere:** `1,3,5`, `2-6` or `all`.

*Why (Claude's reasoning):* there is nothing new to learn for each verb.

**C-7. A destructive verb requires its target.**

*Why (Claude's reasoning):* mvm's bare `stop` picked a node itself, and the c3lab session calls that questionable.

**C-8. Names resolve in one order:**

1. an exact ID wins;
2. a unique match on part of an ID or label resolves;
3. several matches are refused, listing them;
4. no match is refused.

A human may pick by the number shown in a list; a script picks by ID. Both are stable.

*Why:* this is "guided, not guessed". mvm passed an unmatched name through unchanged, which hid typos.

### Settings

**C-9. Defaults are home.**

- `topogee settings unset <key>` restores the default.
- `topogee settings unset all` restores every default.

A reset never leaves a value empty.

*Why:* this is the founder's first principle. An empty value forces every reader of the setting to handle its absence.

**C-10. Changing the future and changing one run are different acts.**

- `topogee settings set <key> <value>` persists a value.
- The same setting's switch on an action applies to that run only.

Each switch's help entry has a `Persist:` line, saying how to persist it or "runtime only".

*Why (Claude's reasoning):* the user always knows which they are changing.

**C-11. A command's same-name switch is a mode.** Where a command has a mode, its switch with the same name turns the mode on for one run, and `settings set` keeps it on until it is turned off or reset. `topogee status` shows every mode that is on.

*Why:* this is the founder's "switches are impulses", together with his own suggestion that hidden state be shown in status.

**C-12. Glue protects deliberate choices from bulk resets.**

- `topogee settings set <key> <value> --glue` marks the key.
- `settings unset all`, and `settings unset <key>`, skip glued keys and name them ("Skipped (glued): …").
- `--unglue` lifts the protection.

The TUI follows the same rule.

*Why (Claude's reasoning):* a bulk reset should not destroy a choice someone kept on purpose. The mvm TUI let `r` reset a glued key while `R` and the CLI skipped it; Topogee keeps one rule everywhere.

**C-13. Store only what the user set; compute defaults; show each value's source.**

- `topogee settings list` shows every setting with its value, its default and its source: default, global or project.
- Defaults may depend on the platform. For example, a server binds to `127.0.0.1` under WSL.

This is R-4.8: "defaults aren't stored".

*Why (Claude's reasoning):* mvm wrote every default on its first save, so a later change of default never reached its users, and its listing could not tell a default from a chosen value.

**C-14. Settings belong to the user, not the repository.** Global settings live in the home folder, and a project's overrides live with that project under the home folder (R-4.8). Neither is written into the project's source tree.

*Why (Claude's reasoning):* mvm's README said both that its settings file is tracked by Git and that it lives outside tracked sources. The c3lab session advised deciding this once, on purpose.

**C-15. Every setting can be read in one line:** `topogee settings get <key>`.

*Why (Claude's reasoning):* mvm hid `get`, so agents had to parse a full listing.

**C-16. Validate on the way in, normalise, and refuse loudly.**

- Enums are matched in any case and stored in canonical case.
- Booleans accept the usual words.
- Lists accept commas or spaces.
- An out-of-range number is refused, never clamped.
- A bad value gives an `ERROR:` line, never a stack trace.
- A stored value that fails validation is reported, then replaced by its default.
- A renamed setting is read under its old name and written under the new one, so older files keep working.

*Why (Claude's reasoning):* mvm clamped numbers, crashed on a bad value with a traceback, and dropped invalid stored values silently. Its renaming of old keys on read is worth keeping.

### Feedback

**C-17. A change reports what changed:** each key with its old and new value (`metaform.layers: 3 → 4`), "no changes", what was skipped because it is glued, and what was unglued. `--quiet` suppresses the report, not the change.

*Why (Claude's reasoning):* the user and agents can verify the effect without a second read.

**C-18. Output never claims more than happened.** "Accepted" and "done" are different results, with different exit codes where it matters. Output may say what it does not claim.

*Why (Claude's reasoning):* mvm's first node driver reported success when a move was accepted, before the node had moved. The founder rejected it.

**C-19. Errors go to stderr as `ERROR: <what is wrong, with the allowed form or range>`.** Where a remedy exists, it is in the message. Ambiguity is refused, never guessed. There are no silent fallbacks, except for optional integrations, which never block. This is R-5.24 on the command line.

*Why (Claude's reasoning):* a refusal that names its remedy costs one turn, not several. The founder's "best-effort integrations never block" covers optional parts only, never user input or state.

**C-20. Exit codes:**

- `0`: done.
- `1`: the command ran and failed.
- `2`: it was used wrongly, such as an unknown word, a bad switch or a missing positional.

**(agent's choice)**

*Why (Claude's reasoning):* scripts and agents can tell a usage error from a failure. mvm only ever returns 0 or 1.

**C-21. Human output by default; `--json` on every command that returns data, built from the same result object.** Results go to stdout; errors and tips go to stderr.

*Why (Claude's reasoning):* only some mvm commands had JSON.

**C-22. Everything leaves a trace.** A command that builds or imports something records what went in and what came out, so a failure can be read afterwards.

*Why:* this is the founder's "debugging is a read, not a séance".

### Discovery and safety

**C-23. Help is a map.**

- `topogee` prints the branches with one-line summaries and a few tips.
- Each branch word prints its own verbs.
- Help is reachable as `topogee help <path>` and as `<path> --help`.
- A switch has its own help entry, with "Works with:" and "Persist:", reachable with or without its dashes.
- `topogee help commands` and `topogee help switches` print the full indexes.
- An unknown word prints the level's help plus "did you mean …" when one name is close, and exits 2.

*Why:* this is the founder's principle and R-5.16. mvm had no suggestions.

**C-24. Never block without a terminal.**

- Prompts and the full-screen TUI appear only when both stdin and stdout are terminals.
- Without a terminal, a command that would prompt either prints what it would show and exits 0, or refuses, naming `--yes`.
- Every interactive path has a one-line form.

*Why (Claude's reasoning):* this is R-5.17. mvm's fallback menu prompted with no terminal and crashed when stdin was closed.

**C-25. Destructive verbs confirm on a terminal and take `--yes` otherwise. File output refuses to overwrite** unless told to. A command that checks and could repair reports first, then applies with `--fix`.

*Why:* this keeps "always resettable" true. mvm had no confirmations; its refusal to overwrite and its report-then-`--fix` habit are worth copying.

## The settings TUI

The TUI is a lens on the same settings the CLI changes (the founder's principle B). It is generated from the schema (C-1).

**T-1. Entering it.**

- `topogee settings` opens the TUI when a terminal is attached.
- Without one, it prints the same list as `topogee settings list` and exits 0 (C-24).
- `topogee settings <group>` opens it on one group.

**T-2. Rows use the CLI's names.** A row is labelled with the setting's switch, or its key where it has no switch. It shows:

- the value;
- the default, when the value differs from it;
- the source: default, global or project;
- `*` when glued.

A value that differs from its default is shown in green.

*Why (Claude's reasoning):* what a user learns in one tool carries over to the other. mvm did not show the default; the c3lab session recommends showing it, which fits "defaults are home".

**T-3. Groups come from the schema,** so a new group needs no edit to the TUI.

**T-4. Each type gets its editor:**

- boolean: toggle;
- choice: a pick-list with a filter;
- number: step by the schema's step, refusing out-of-range values;
- text: a prompt;
- list: a multi-select or a prompt.

Every edit goes through the same validator as the CLI, and an invalid edit shows its error and leaves the value unchanged.

**T-5. Edits stay in memory until saved.**

- `s` saves.
- Quitting with unsaved changes asks: save, discard or cancel.
- A key reverts the selected row to its saved value.
- The preview shows saved → pending, as its title says.

*Why (Claude's reasoning):* mvm's preview compared the defaults with the current values, and it had no revert to saved.

**T-6. Reset and glue follow C-9 and C-12.** `r` resets the selected row and `R` the whole group, both skipping glued rows and saying so. `g` glues or unglues the selected row.

**T-7. A wizard is for one hard decision.** It is a short line-based flow: pick from a numbered list by number or ID, then accept a suggested follow-on default. It saves only what it was asked about.

*Why:* this is the founder's "guided, not guessed". mvm's wizard picked target profiles and suggested the matching image name.

## The `topogee` command

```
topogee                                   the branches, with one-line summaries and tips
topogee help [<path> | <switch>]          help for any level or switch; also <path> --help
topogee status [--json]                   the Metaform server, the current project, and every mode that is on

topogee metaform                          this folder's Metaform in counts: elements by role, layers, last change
topogee metaform spec [--json]            this folder's Metaform as a specification (R-1.2)
topogee metaform export                   the Metaform as JSON
topogee metaform import <file>            load a Metaform; reports what changed
topogee metaform server status [--json]
topogee metaform server stop | restart

topogee project                           this folder's project: name, folder, settings it overrides
topogee project add [<folder>]            register a project; default this folder
topogee project list [--json]
topogee project remove <folder> [--yes]   destructive: confirms on a terminal

topogee settings [<group>]                the settings TUI on a terminal; the list otherwise
topogee settings list [--json]            every setting with its value, default and source
topogee settings get <key>
topogee settings set <key> <value> [--project] [--glue]    persist; reports the change
topogee settings unset <key>|all [--project] [--unglue]   back to the default; glued keys skipped
```

- **The current folder is the project** by default for every map and project verb.
- **The specification's layers are a project detail in the main database,** so `metaform spec` takes no layer names (the founder, 2026-11-06).
- **A setting's key is the object of `set`, so it is positional (C-3).** Topogee's keys are dotted names such as `database.buffer_pool_mb`. `--project` writes this project's override, not the global value (R-4.8).
- **Each module owns its branch (R-5.16).** Later modules add their own branches, such as `agent`, by declaration (C-1).

## Not copied from mvm

- Writing every default on the first save.
- Clamping numbers, crashing on a bad value, and dropping invalid stored values silently.
- Checks hard-coded by key name, and menu groups listed by hand.
- Prefix abbreviation left on for some commands.
- Hand-written help next to the code, and three separate registrations per command.
- A bare destructive verb that picks its own target.
- A name that matches nothing passed through unchanged.
- A fallback menu that prompts without a terminal.
- A TUI reset key that ignores glue.
- Command names that encode a value, such as `drop0`…`drop100`.
- Legacy switch aliases.

## For the founder

1. **The command name `topogee`.** Recommended: one name with module branches follows R-5.16 directly.
2. **Settings as `settings set <key> <value>`, not mvm's `set --key value`.** Recommended for the reason under C-3.
3. **`topogee settings` opening the TUI on a terminal and printing the list otherwise.** This follows mvm's bare `config` and the founder's "discover via TUI", with C-24 protecting agents. Recommended.
