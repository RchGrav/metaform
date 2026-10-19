# Draft amendments: CTX-060, CTX-061, CTX-062, CTX-064 (code.dispatcher.agent#47)

Drafted 2026-10-15 by the worker on ticket 7b82c2818ea04ff3bf389a7eb3510970 (code.dispatcher.agent#47). Awaiting the owner's approval of this exact wording before any bullet is added to `specifications/11-context.md`. The built code is gated by `LINK_LOCK` (src/metaform/modules/dispatch/runner.py:154), which stays `False` in the tree. None of this holds until the owner sets it to `True`.

## CTX-060

Sentence the code now contradicts: "Every agent dispatch starts on a ticket gets the rule as one line of its first message, so the refusal does not come as a surprise." Also the Build bullet saying `work_line` appends `work_link` to the first message.

Proposed bullet, after its Status line:

- Amendment, 2026-10-15, ticket code.dispatcher.agent#47, the rule reaches every session before its lock does. Every session dispatch runs gets the `work_link` rule at the end of the first prompt its runner sends it, whatever that prompt is: a ticket's hand-off, a resumed or loaded session's next message, the system agent's opening, a talk, the sentinel, an intake or a prep worker. The rule is never a turn of its own (CTX-043). The lock holds for a session only once the rule has gone with a prompt (`Session.ruled`, set in `prompted`). Before that, `locked` and `unsandboxed` refuse nothing. `work_line` no longer carries the rule. Before this, only a ticket's first message carried it, so resumed sessions, the system agent and intake agents were refused without ever being told. Acceptance: test_the_lock_holds_for_a_session_only_once_its_rule_has_gone_to_it, test_a_resumed_session_is_told_the_rule_with_its_next_prompt, and test_the_handoff_is_the_brief_the_ticket_its_node_and_counts_under_three_kilobytes (the rule ends the first prompt).

## CTX-061

Proposed bullet:

- Amendment, 2026-10-15, ticket code.dispatcher.agent#47, the lock holds in every mode from the session's first prompt, not from its start. Claude Code still gets the ask rules on session/new, load and resume. A permission request that came before the rule went to the session would be decided by `dispatch_prompts` alone. No agent acts before its first prompt, so this does not happen in practice. Live check (follow-up (e)) done 2026-10-15 in a scratch home with the switch on: a real Claude Code session (claude-agent-acp 0.89.1, Claude Code 2.1.293, Sonnet 5.5, bypassPermissions) edited the unlinked AGENTS.md and was refused with the owner's sentence and the link call. After `dispatch_link` the same Edit went through, approved by `dispatch_prompts=approve-all`.

## CTX-062

Sentences the code now changes: the 2026-10-15 build by code.dispatcher.agent#43 sent Claude Code a sandbox with `denyWrite: [project]`, and its accepted cost was "commands cannot write any project file, linked ones included".

Proposed bullet:

- Amendment, 2026-10-15, ticket code.dispatcher.agent#47, the command sandbox denies what the lock denies and no more. Checked live with Claude Code 2.1.301 (`claude -p`, bypassPermissions): a `denyWrite` folder wins over every `allowWrite` path inside it. A linked file, `.venv` and `.git` under a denied project all stayed read-only. So the sandbox allows the person's home and the temporary folders (`writable_roots`), never `/`, and denies path by path. With `allowWrite: ['/']`, Claude Code 2.1.293, the build claude-agent-acp 0.89.1 bundles, fails every command with "bwrap: Can't mkdir /etc/claude-code: Permission denied". #43's sandbox sent that, so under it no Claude session dispatch ran could run a command at all. The deny list is built by `denied_writes` (runner.py), which lists each path `.metaform/ignore.txt` holds, each existing file no ref names exactly, and each folder holding no linked file, whole. The folders tools write as they run (`TOOL_FOLDERS`: `.git`, `.venv`, `__pycache__`, `.pytest_cache`, `.ruff_cache`, `.mypy_cache`, `node_modules`) stay writable, and so do the files linked when the session starts. A denied file cannot be written, removed or moved (EBUSY), and a denied path that does not exist cannot be made. The runner's own terminal uses the same list, read again for each command. Limits: (1) a file linked during a Claude Code session is writable by its edit tools at once, but by its commands only from its next start or resume, because the settings are fixed when the session is made; (2) a new file made by a command, under a name no list could know, in a folder that also holds a linked file, is not prevented; (3) the claude-agent-sdk passes settings as one command-line argument, which Linux caps at 128 KiB, so past `DENIED_CHARS` (96 KiB) whole folders are denied, largest first, which only ever denies more. (4) While a command runs, the sandbox shows empty mount points in the project root (`.bashrc`, `.gitconfig`, `.mcp.json`, `.idea` and others), so an agent's `git status` lists them as untracked. They are gone when the command ends. Live, 2026-10-15, in the session above: `uv run pytest -n 0 tests/test_home.py`, `uv run ruff check` and `git status` ran; `echo >> AGENTS.md` (unlinked) failed read-only; `echo >> src/metaform/home.py` (linked) and `git checkout --` of it went through. Acceptance: test_commands_may_write_linked_files_and_tool_folders_and_nothing_else_of_the_project; test_codex_is_kept_asking_and_cannot_write_an_unlinked_or_ignored_file_or_lift_its_sandbox (the sandbox never names the project folder); test_a_command_in_the_runners_terminal_cannot_write_the_project.

## CTX-064

Proposed bullet:

- Amendment, 2026-10-15, ticket code.dispatcher.agent#47: commands cannot write a path the ignore list holds either. A folder the list holds is denied whole, so nothing can be made in it, linked or not.

## Open for the owner

- Limit (2) of CTX-062 means a shell can still make a new unlinked file under an arbitrary name in a folder that holds linked files (the project root among them). Claude Code's sandbox has no exception inside a denied folder, so closing this would take a different mechanism.
- `.git` is writable to commands, as the ticket asked, so `git status` and `git commit` work. `.git/hooks` and `.git/config` stay denied (`GIT_HELD`), because a hook a command wrote would run later outside the sandbox. Under #43 the whole project was denied, so this hole never existed, and #47 closes it in the same change.
- Codex is still kept in read-only mode, so its commands write nothing at all, `/tmp` included, and it cannot run the tests. Its mode was outside this ticket.
