# Draft: CTX-061 and CTX-062, the lock for Codex and for shell writes

Ticket code.dispatcher.agent#43 (24a95b422a0644f1b57d3b79ea6cbc43), 2026-10-15. Drafted by the worker for the owner's
approval; nothing below is in `specifications/11-context.md` yet. The ticket asked for the choice to be recorded in the
records' Build with evidence; under the spec-amendment rule, the worker drafts it here instead.

What the code now contradicts in the records as written:

- CTX-061, Build: "Open, Codex: ... today the lock does not hold for Codex." Built now (below).
- CTX-062, Build: "Open." and How it shows: "Today this is not so." Built now for shell writes of agents dispatch runs.
- CTX-062, Build, first sub-bullet: the worktree proposal (follow-up (b)) was not built, for the reason given below.
- CTX-060, What this means: "Every agent dispatch starts on a ticket gets the rule as one line of its first message".
  The line, `work_link`, now has a second sentence on commands.

## Proposed replacement of CTX-061's "Open, Codex" sub-bullet

  - Built, Codex (code.dispatcher.agent#43): codex-acp asks before a file change only in read-only, so the runner
    keeps it in read-only whatever mode the person chose (`ASKING_MODES`, src/metaform/modules/dispatch/runner.py:145;
    `hold_mode`, :1645, run before the session's options are applied and after every mode or config update the
    agent sends). The person's choice is kept and shown as the session's mode (`chosen_mode`, set in `configure`,
    :2157), and decides what is approved without asking once the lock has passed: what Codex would have done unasked
    in that mode (`MODE_APPROVES`, :149; agent and workspace-write approve file changes, agent also an MCP tool's approval, which Codex's
    auto review answered itself; agent-full-access also commands' network requests). Read-only also runs Codex's commands in its own sandbox, which writes nothing.
  - A permission request is read together with the tool call it belongs to, as the agent began it (`request_permission`,
    :2659), and a request that names files but gives no kind is taken as a write (`edit_locked`, :2231), since the
    started call may not have been read when the request arrives.

## Proposed Build for CTX-062, replacing "Open." and its sub-bullets

- Build: Built 2026-10-15 by code.dispatcher.agent#43 for agents dispatch runs, uncommitted. Every command an agent
  runs works in a sandbox where the project folder is read-only, in every permission mode, so a shell write to a file
  of the project fails before it lands, linked or not; files change only through edit tools, which the per-file lock
  (CTX-060, CTX-064) governs. Paths outside the project stay writable (CTX-060's recommendation).
  - Claude Code: `held_settings` (runner.py:153), sent in `_meta` on session/new, session/load and session/resume,
    gives Claude Code its sandbox: enabled, `failIfUnavailable` true, `allowUnsandboxedCommands` false (its
    `dangerouslyDisableSandbox` escape is ignored), `filesystem.denyWrite` the project folder and `allowWrite` the
    root of the file system. The same object carries the four edit tools' ask rules of #3d.
  - Codex: read-only mode (CTX-061). A request to run a command outside the sandbox (an execute request with no network
    host and no additional permissions) is refused, as is a grant of write access to the project folder, a folder in
    it, a folder above it, or a file the lock holds (`unsandboxed`, runner.py:2250). Network requests are answered as
    usual.
  - The runner's own terminal, ACP's terminal/create when `dispatch_client_terminal` is on, runs the command under
    bubblewrap on Linux and sandbox-exec on macOS with the project read-only (`confined_command`, runner.py:172);
    where neither is found, the terminal is refused.
  - The agent is told: `work_link` (src/metaform/modules/dispatch/resources/prompts.xml:196) now ends "Commands you run
    cannot write the project's files; change them with your edit tools." A refused escalation or grant is answered
    with `command_unsandboxed` (:220), steered into the turn or sent as the next. A command that tries a write gets
    the system's "Read-only file system".
  - Off with the lock: since 2026-10-15 (Rich, code#1e) `LINK_LOCK` (runner.py:141) is False until the rules and
    prompts for linking are in place. Every part above is under the same switch: with it off, no sandbox is sent to
    Claude Code, Codex keeps the mode the person chose, the runner's terminal runs unconfined, no escalation or grant is
    refused, and `work_link` is not sent. The ignore list is not read-only either (CTX-064): Rich, 2026-10-15, no
    permission on files is locked until the rules and prompts are in place. True brings back #3d and
    #43 together. The tests of both skip while it is off (`skip_while_unlocked`).
  - Why not a worktree (follow-up (b)): a worktree is not confinement. A command in it can still write the project by
    its absolute path, and `.worktrees` lies inside the project folder, so the write would land; and every session
    would lose the project's untracked tools (`.venv`, `node_modules`) and reach the project only through the
    VIEW-044 merge. The sandboxes stop the write at the system call, which is prevention.
  - Cost, recorded as built: a command cannot write a linked file either, so formatters, code generators and
    `git commit` run by an agent fail in the project folder. Codex's read-only sandbox also refuses writes outside the
    project, `/tmp` included; Codex may ask for additional write permissions for paths outside the project, which are
    answered as usual.
  - Where it cannot hold: a Claude Code session on Linux without `bwrap` and `socat` fails to start, rather than run
    unconfined. gemini-cli runs its own shell tool, which no ACP request names; it is not covered, and not tested.
    Agents connected only over MCP are not covered (open question 11, its second half, unchanged).
- Acceptance:
  1. test_codex_is_kept_asking_and_cannot_write_an_unlinked_or_ignored_file_or_lift_its_sandbox
     (src/metaform/modules/dispatch/tests/test_dispatch.py:3557): a codex-acp-shaped fake agent is set to read-only;
     a file change of an unlinked file asked by its path alone, an edit of an ignore-listed file, a command outside
     the sandbox and a write grant for the project folder are each refused with the reject-once option and the agent
     told; its edit of a linked file and an MCP tool's approval are approved by the mode it began in, agent, with no
     question to the person;
     session/new carries the Claude Code sandbox with the project in `denyWrite`.
  2. test_a_command_in_the_runners_terminal_cannot_write_the_project (:3593): a command in the runner's terminal that
     writes a file of the project leaves it unchanged. Checked by mutation: with the terminal unconfined it fails.
     Both tests, with #3d's four, pass with `LINK_LOCK` set True (6 passed, 2026-10-15) and skip with it False.
  3. Live, Claude Code (claude -p, bypassPermissions, the settings `held_settings` sends, in a scratch git folder):
     `echo x > <project>/unlinked.txt` and `sed -i s/base/changed/ <project>/linked.txt` both fail with "Read-only
     file system" and leave the folder unchanged; `mkdir` in the project fails the same way; writes to ~/.cache and
     /var/tmp and an HTTPS request succeed; `git status` reads. With `allowWrite` "/" and an `Edit(<project>/**)` allow
     rule, the project stays read-only: deny wins.
  4. Live, the runner's terminal sandbox on Linux: `bwrap --dev-bind / / --ro-bind <project> <project>` refuses a
     write into the project and allows one outside it.
  5. Live, Codex: see the evidence section below.
- Status: built 2026-10-15 for agents dispatch runs, Claude Code and Codex, and off with `LINK_LOCK` (code#1e); awaiting the owner's approval of the method
  and of the `work_link`, `command_unsandboxed` and `terminal_unconfined` wording. Open for gemini-cli's own shell and
  for agents connected only over MCP.

## Proposed change to open questions 10 and 11

10. Answered by build (code.dispatcher.agent#43): Codex is kept in read-only, its approvals answered by the lock, then
    by the mode the person chose, then by `dispatch_prompts`. The live check of Claude Code in bypassPermissions
    editing an unlinked file is still not run.
11. First half answered by build: shell writes are prevented by the agents' own sandboxes and the runner's, with the
    project read-only; no worktree. Second half open: may provisioned settings carry the lock for agents dispatch did
    not start?

## Evidence: live Codex session

Run 2026-10-15 22:31 to 22:36 UTC, with `LINK_LOCK` still True in the runner that ran it. A scratch git folder and a
scratch Metaform home: `src/fresh.py` (unlinked), `src/kept.py` (linked with `dispatch link`), `rich/notes.md` (linked,
and `rich/` in `.metaform/ignore.txt`). Real codex-acp 2.2.2, logged in with ChatGPT; `dispatch_prompts` ask_all; Codex's
mode as it began, agent. The ticket asked it to change each file with its own tools, once each, and to run
`sed -i s/old/new/ src/fresh.py`, then close the ticket.

- The runner set the mode to read-only before the first prompt.
- Its edit of src/fresh.py was refused with the owner's sentence and the link call; the file still reads `old`.
- `sed -i s/old/new/ src/fresh.py` failed: "the filesystem is read-only", in Codex's own words; the file is unchanged.
- Its edit of rich/notes.md was refused: "rich/notes.md is read-only to agents: .metaform/ignore.txt holds it."; the file
  still reads `mine`.
- Its edit of src/kept.py was "approved by the mode agent", with no question to the person; it reads `new`.
- It closed the ticket; the runner ended with "the ticket is done".
- Found and fixed from this run: Codex asks approval for a Metaform MCP tool as kind execute. The first build refused
  it as an escalation, so two `map_knowledge` calls failed. Now only a request whose own input names a command counts
  as an escalation, and the mode agent approves MCP tool approvals, which `is_mcp_tool_approval` marks. The fake
  agent's test covers it.
