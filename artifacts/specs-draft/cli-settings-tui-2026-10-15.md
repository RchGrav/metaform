# Draft amendments: settings TUI, ticket e3a3a2e4deea459cbb123ca48aa8be0d (code.manager.configuration#15)

Drafted by the worker on this ticket for the owner to approve. Each bullet records what the code now does; none asks
for a code change. Each goes after its record's `Status:` line in `specifications/05-cli-settings.md`.

## CLI-019 Select settings take choices from a list or from module data

The code now goes beyond "an invalid choice fails": a list with choices refuses a member outside them too, and a select can name the command that reads its choices. Proposed bullet:

- Amendment, 2026-10-15, settings TUI, ticket e3a3a2e4deea459cbb123ca48aa8be0d (code.manager.configuration#15): a list setting with `choices` refuses a member outside them on every surface, with the choices listed, as a select does (`settings._listed`, `_no_choice`). A list whose check says what another member does keeps it and is marked `beyond_choices`: `layers` (CLI-033's notice), `jev_decisions` (a module's own `<module>.<point>`), and `modules` and `roles_without_authority`, whose checks refuse in their own words. Choices are now declared for `install_server`, `write_layer`, `layers`, `roles_without_authority`, `twilio_call_when`, `twilio_text_when`, `twilio_project`, `web_agent_glyphs`, `voice_language` (Whisper's language codes), `code_kinds` and `dispatch_intake_withheld`. A select may declare `choices_from`, the command that reads its choices from their source while it offers no more than its default. Each `dispatch_<agent>_<option>` names `metaform dispatch options agent=<agent> prime=true`. That command is the Next line of a refused value, and the settings TUI and the web settings window offer to run it. Why: a value that has a list was typed by hand, a typo was stored with exit 0 (`set --twilio-call-when stuk`), and the agent model pickers offered only `default` with no way to fill them from the screen (critic finding F5, artifacts/critic/2026-10-14-system-review/settings-ux.md).

## CLI-026 The settings screen

Proposed bullet:

- Amendment, 2026-10-15, settings TUI, ticket e3a3a2e4deea459cbb123ca48aa8be0d (code.manager.configuration#15):
  - Speed. One `settings.describe(folder, choices=False)` serves every group (`_Backend.describe`). A setting's choices are read when its picker opens. `describe` runs in one registry scope, and `home.preload_settings` reads each scope's stored values and glue with one query. The read and every save run off the screen's event loop, so moving, finding and help keep working while a save runs. First paint fell from 2.4–3.4 s to 0.63–0.97 s on a scratch home with every module on.
  - Title and rows. The title reads `SETTINGS FOR <folder>`. Each row starts with marks: `P` person-only, `!` a risky value, `~` staged and not saved, `*` glued. Then `key: value` and `(set)`, `(glued)`, `(staged)` or `(inherited from <folder name>)`; a default has no note. From the glue mark on, the row reads as `config --show` prints it. A value too long for the panel ends in `…`.
  - Details. The details pane shows the value whole, where it comes from (with the full folder), the default as computed for the folder, the scope, person-only, what a risky value risks, the help, and the command-line forms (`--x or --no-x` for a boolean).
  - Finding. `/` finds settings in every group by key, label or help, listed as `group  key: value`; reopening it puts the cursor at the end.
  - Editing. A value with choices is picked from them. A typed value is read as `set` reads it, a list's items between commas or a JSON list when an item holds a comma, and checked with `settings.checked` when it is staged, so a refusal is said at once with its next step. A save checks every staged value before it stores any.
  - Reading choices. A select with `choices_from` and no choice but its default shows a last picker line, `Read its choices`, that runs the command in the folder and opens the picker again with what it read. `R` resets the group, or every setting a filter lists.
  - Why: findings F9, F10, F12 and F14 of artifacts/critic/2026-10-14-system-review/settings-ux.md.

## CLI-010 One schema drives every surface (the web settings window)

Proposed bullet:

- Amendment, 2026-10-15, settings TUI, ticket e3a3a2e4deea459cbb123ca48aa8be0d (code.manager.configuration#15):
  - Each row of the web settings window shows its default in its More box, and the folder an inherited value comes from.
  - A select with `choices_from` shows a Read choices button while it offers only its default. The button posts `/api/settings/choices`, an admin route that runs only the setting's declared command in the project's folder and answers with the settings as they are now.
  - `describe` gives `person_only`, and `choices_from` while it applies.
  - A glue change now announces the settings change as a stored value does (`home.set_glue`), so an open window re-reads after a glue made elsewhere, as it already did after a set or reset (finding F13).
