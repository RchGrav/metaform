# Spec drafts: one setting per agent option (ticket code.interface.command_line#2, 2026-10-14)

Drafts for Rich. Nothing here is in `specifications/` yet.

## specifications/04-chassis-modules.md:814 (settings the agent offers, P199 and P015)

Replace "offered as the choices of the person-only setting `dispatch_agent_options`, entries `<agent>.<key>=<value>` with the key the ACP category when it is a reserved one (`mode`, `model`, `model_config`, `thought_level`) and the option id otherwise, so a choice holds across versions that rename an option." with:

> offered as the choices of one person-only setting per agent option: for claude, codex and gemini `dispatch_<agent>_mode`, `dispatch_<agent>_model`, `dispatch_<agent>_effort` (ACP `thought_level`) and `dispatch_<agent>_fast` (`model_config`), with `dispatch_claude_agent` and `dispatch_codex_collaboration_mode` for the two options offered today that have no ACP category. Each is `default`, which sends nothing and leaves the agent's own, or a value the agent offered at its last session here; setting one never touches another. Why, Rich 2026-10-14: one list for every agent's options lost the other entries whenever one was saved, and a choice must be picked from what is offered, never typed. The stored entries of the old `dispatch_agent_options` moved once to the new settings as dispatch started, and the old setting is gone.

## specifications/05-cli-settings.md:174 (person-only settings)

In the list of dispatch's person-only settings, replace `dispatch_agent_options` with: `dispatch_claude_mode`, `dispatch_claude_model`, `dispatch_claude_effort`, `dispatch_claude_fast`, `dispatch_claude_agent`, `dispatch_codex_mode`, `dispatch_codex_model`, `dispatch_codex_effort`, `dispatch_codex_fast`, `dispatch_codex_collaboration_mode`, `dispatch_gemini_mode`, `dispatch_gemini_model`, `dispatch_gemini_effort`, `dispatch_gemini_fast`.

## CLI-026 (the settings screen), added lines

> The screen lists the modules after the chassis, and each one's settings, alphabetically by the name shown. A setting may declare a `section`, a path of headings such as `Agent options/Claude Code`: the screen lists a section as one row that opens a menu of what is inside it (→ or Enter opens it, ← or Esc goes back), and the web settings screen puts its settings under the heading. A choice setting may declare each choice in plain words, `choice_help`, shown beside the choice where it is picked. Why, Rich 2026-10-14: the agent permission settings were hard to find and to set.

> `metaform set` completes its switches and each setting's choices on Tab once the shell asks metaform for them: `complete -C metaform metaform` in bash, after `autoload bashcompinit; bashcompinit` in zsh.

Acceptance: tests/test_tui.py `test_a_section_opens_as_a_menu_of_its_settings_and_lists_are_alphabetical`; tests/test_cli.py `test_tab_completes_a_settings_switch_and_its_choices`; dispatch's `test_an_agents_options_are_kept_offered_as_settings_and_applied_with_the_tickets_own`, `test_cancel_and_tune_are_the_persons_and_tune_takes_only_what_the_agent_offers`, `test_the_old_agent_options_move_once_into_each_options_own_setting`; web's `test_the_settings_screen_opens_from_the_agents_menu_and_saves_each_change_as_it_is_made`.
