# CLI settings draft amendments: per-call switches, risky choices, inherited values, typed lists

Draft for Rich, from ticket code.manager.configuration#5 (system review 2026-10-14, H1, H3, H4, H5). Not applied to `specifications/05-cli-settings.md`, `09-viewer.md` or `OPEN-QUESTIONS.md`.

## CLI-011 and D32: per-call switches (H1)

### What the record says now

CLI-011: "every long switch that changes how commands run is a setting, so it can be passed on one call, stored with `set`, cleared with `unset`, and protected with `--glue`." Its Build leaves the verb controls (`--glue`, `--unglue`, `--show`, `--json`, `--quiet`, `--help`) to D32, which is unanswered.

### What the code does now

- `Setting.per_call` (`src/metaform/settings.py`). A per-call setting is read only from the call's own switch: `settings.value` never reads a stored row of one, so a value stored before it was marked has no effect.
- `metaform set`, the agent's `metaform_set` tool and the page's save refuse it. The refusal names the verb that takes it, for example `Next: metaform mcp serve --http`.
- `metaform unset` still clears an old stored row.
- `config --show`, the settings screen (TUI and page), set's Tab completion and the `metaform_set` schema leave it out.
- `metaform help --http` shows the verbs that take it.
- Marked per-call: `mcp_http` (`--http`), `node_dry_run` (`--dry-run`), map's `raw` and `critic`.

### Proposed amendment text

- Amendment, 2026-10-14, per-call switches: a switch whose stored value would silently change later calls of another kind is declared per-call. Examples are a transport, a dry run, an unmasked read and the type of a blind-spot run. It is accepted on the call and never stored. `set`, over MCP or the command line, refuses it and names the verb that takes it. The settings screens, `config --show` and the set tool's schema leave it out. A value stored before it was declared per-call is never read, and `unset` clears it.
  - Why: a stored `--http` made every `metaform mcp serve` in its folder serve HTTP, including the stdio servers that AI tools and dispatch start, so none of them answered. An agent could store it over MCP and cut its own connection. A stored `--dry-run` silently turned every deploy into a no-op, a stored `--raw` unmasked every read below the folder, and a stored `--critic` silently made every blind-spot run the sighted one (LAYER-014). CLI-018 already exempts `--confirm` from being a setting for the same reason.
  - Acceptance: `metaform set --http` exits 2 with `Next: metaform mcp serve --http`. A row for `mcp_http` stored before it was marked does not change `settings.value`, and `unset --http` clears it. Test: `tests/test_cli.py::test_a_per_call_switch_is_given_on_its_verb_and_never_stored`.
- D32, proposed answer: yes. The verb controls `--glue`, `--unglue`, `--show`, `--json`, `--help` and `--confirm` steer the command and are never settings. `--quiet` stays a setting. A switch that is a setting but must never be stored is declared `per_call`, as above.

## CLI-018: `--confirm` on `set` for a risky choice (H5)

### What the record says now

"`--confirm` is accepted only as a one-call switch on caution verbs."

### What the code does now

`metaform set` takes `--confirm` as a one-call switch beside `--glue`. A select can declare `risky` choices (`Setting.risky`): dispatch's `dispatch_prompts` declares `approve-all`, and each `dispatch_<agent>_<option>` declares the values the agent offered that skip its own permission prompts.

| Surface | How a risky choice is stored |
|---|---|
| CLI | refused without `--confirm`; the Next line is the same command with `--confirm` |
| MCP `metaform_set` | refused without `confirm: true`; the person's own answer to the consent form counts as confirmed |
| TUI | asks Y/N before staging one |
| Web settings screen, the Agents menu and the session panel's agent defaults | ask with the confirm dialog |

Stepping through choices with the arrow keys never lands on a risky one, in the TUI or on the page. `metaform set --confirm` with no setting still fails with `Error: --confirm is not a setting.`

### Proposed amendment text

- Amendment to CLI-018, 2026-10-14: `--confirm` is also a one-call switch of `set`. It confirms a choice that the setting declares risky, a choice that lets an agent act without asking. It is still never a setting.
- Amendment to VIEW-039 (or a new CLI record), 2026-10-14, risky choices:
  - A select declares the choices that let an agent act without asking. Every surface asks the person before it stores one: `set --confirm`, `confirm` on the set tool, a yes on the settings screens and the page.
  - Stepping through choices never lands on one; it is picked from the list and confirmed.
  - Why: VIEW-039 already confirms a session mode that skips the agent's permission prompts, for one session. `dispatch_prompts` makes the same decision for every agent, and it was one Right-arrow press in the TUI or one select change on the page, with no confirmation.
  - Acceptance: `tests/test_tui.py::test_a_risky_choice_is_never_stepped_onto_and_is_stored_only_when_confirmed`. The browser test `test_the_admin_sets_how_agent_prompts_are_answered_and_the_choice_is_kept_in_the_settings` checks that Cancel keeps the value and confirming stores it.

## CLI-013, CLI-014 and CLI-016: a folder resets only its own value (H4)

### What the record says now

- CLI-013: three states, default, set and glued.
- CLI-014: `set` writes at the folder's own key. It does not say where reset writes.
- CLI-017's D36: `unset all` touches only what is stored at this folder.

### What the code does now

`reset`, unglue, and clearing a list with the word `all` (or an empty list) act only at the folder's own scope. When the value comes from a folder above, they are refused with that folder named:

```
Error: panes is inherited from /p; nothing is stored here to reset.
Next: metaform unset --panes folder=/p
```

`unset` checks every key it names before it resets any of them.

`config --show` prints `(inherited from <folder>)`, and `--json` gives the state `inherited` and `from`. The TUI and the page show the same. The page turns Reset off for an inherited row.

### Proposed amendment text

- CLI-013 amendment: a fourth state is shown, not stored. Inherited means the value is stored or glued at a folder above, and the state names that folder.
- CLI-014 amendment, Build: `reset`, `unglue`, and `set` with the word `all` act at F's own path key only. When F holds nothing and a folder above holds the value, they stop with an error naming that folder and a Next line that runs the same reset there.
  - Why: from a subfolder, `unset --x` or `set --modules all` removed the project root's choice for every folder below it, and the output gave no sign. An agent working in a subfolder could undo the person's project-wide choice for any setting that is not person-only.
  - Acceptance: `tests/test_cli.py::test_a_reset_in_a_subfolder_never_reaches_the_folder_above_and_names_it`.

## CLI-027: a list item that holds a comma (H3)

### What the code does now

- The TUI, the MCP set tool and the page store a list as the list given, member by member, so an item may hold a comma.
- A list declared `exclusive` refuses an item without its mark on every surface. On the command line, `--dispatch-agent-strengths "claude=front-end, GUI"` is now refused with "On the command line a comma separates items." Before, it stored two broken entries without complaint.
- The CLI form and the page's free-text list box still split on commas.
- Test: `tests/test_tui.py::test_a_list_whose_items_hold_commas_is_saved_from_the_screen_as_it_reads`.

### Needs Rich: the CLI form for an item that holds a comma

The review proposes this addition to CLI-027's list row: "A list value that starts with `[` is read as a JSON array of strings, so an item may hold a comma." Not built. Until it is decided, the shipped default of `dispatch_agent_strengths` can be stored from the TUI, the set tool and the page, but not typed on the command line.

## Differences between code and records, for Rich to decide

- CLI-018 says `--confirm` is accepted only on caution verbs, but `set` now takes it (above).
- CLI-013 names three states, but `config --show --json` now also reports `inherited`.
- CLI-011's list of person-only settings is stale: it still names `dispatch_agent_options` and `agent_command`, as the review's H2 says. That belongs to H2 and was left for its own ticket.
