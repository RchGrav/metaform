# Forensic reconstruction: the roundtable project, evening of 2026-10-16

Critic report, written 2026-10-17. Read-only: every SQLite file was copied to the scratchpad and opened read-only; no
metaform command ran against the real home (one `map where` ran against a scratch copy of the metaform project); no
agent was started, nothing was restored.

Times are UTC. Local time is EDT (UTC-4): 21:50Z is 17:50 on Rich's clock.

Code citations: the editable install (`~/.local/share/uv/tools/metaform`) runs the working tree of `/home/rich/metaform`,
which carries 70 uncommitted files. Lines are given at commit `dc4af39` (HEAD during incidents 1 to 3) and, where they
differ, in the working tree as of this report. Whether an uncommitted change was live at a given minute is unknown;
none of the cited paths changed between `dc4af39` and the working tree except where noted.

Evidence keys used below:
- `main` = `~/.metaform/projects/-home-rich-roundtable-001/main.metaform.sqlite3` (base `16b9a65e…`).
- `spec` = `…/roundtable-2-spec.metaform.sqlite3` (base `cb970494…`, active now).
- `B1` = `~/.metaform/backups/clear/roundtable/20261016T215026Z/` (made by the first clear).
- `B2` = `~/.metaform/backups/clear/roundtable/20261016T215354Z/` (made by the restore's own clear).
- Transcripts are `~/.claude/projects/-home-rich-roundtable/<session>.jsonl`; `n:` is the line in that file.

---

## 1. Verdict

Nothing Rich built was destroyed: both maps, all 116 tickets, the memory graph and every conversation still exist,
on disk and in transcripts. What failed is that Metaform keeps the person's conversation with their agent inside the
map's base store and anchors it to a ticket on a map element, so a clear deleted the chat, a restore deleted the next
chat, an intake finishing switched the active base and silently gave him a new agent with no memory, and an empty map
refused him an agent at all. On top of that, Start all ignored the six-slot limit (66 agents in 5.5 minutes, since fixed
in `7b10595`), and the system agent is handed its role prompt as if it were the person's message with no objective, so
two fresh agents in a row answered "no objective" instead of working.

---

## 2. Timeline (UTC, 2026-10-16 unless marked)

| Time | Actor | Action | Code path | Effect | Evidence (O = observed, I = inferred) |
|---|---|---|---|---|---|
| 10-15 02:37:51 | Metaform | Base `main` created for project `roundtable` | `home._create_base` | Map store `main` | `project.sqlite3` `bases` row (O) |
| 20:22:48 | Person (page Call) | Held ticket "Conversation with the system agent" made at the DE | `dispatch/__init__.py:2264 anchor` (dc4af39) | Ticket `8c003e22` in `main` | `main.work` row 50 (O) |
| 20:22:53 | Person | Codex system agent `01a14661` started, stopped 20:23:01 | `system()` → `converse()` :2305/:2287 | — | `B1."dispatch.sessions"`, signal not-smooth (O) |
| 20:24:14 | Person | Claude system agent `1d2d3085` (pid 58504) | same | First turn = dispatch `prompts.xml` `<system>` | `runner.py:3268` (dc4af39); transcript n:5 (O) |
| 20:24:35 | Agent 1d2d3085 | "Your message set up the orchestrator role but didn't include an objective" | — | Waits | 1d2d3085 n:49 (O) |
| 20:26–21:44 | Person ↔ 1d2d3085 | Brainstorm (SDF, octrees, holodeck); 14 person lines | `dispatch.lines` in `main` | Thread of 88 lines | `B1."dispatch.lines"` (O) |
| 21:26:42, 21:48:29 | Person | `/effort ultracode on`, `/goal …` | — | Stop hook active | n:244, n:249 (O) |
| 21:49:41 | Person | "you can clear the intake and do a new one off of just the specification.. please fo that ok" | — | — | n:283; `B1` lines seq 78 (O) |
| 21:49:55 | Agent 1d2d3085 | `metaform_clear_project {}` | `mcp/server.py:287`, `home.to_clear` | Caution only: "removes one base, main, with its store, and four report files" | n:302–304 (O) |
| **21:50:26** | Agent 1d2d3085 | `metaform_clear_project {confirm:true}` | `home.py:1125 clear_project` → `backup_project` :1200 → `_remove_files` :1147 | Backup `B1`; `main` deleted: 1119 ops, 581 objects, 50 tickets, 273 dispatch lines incl. the whole chat and ticket `8c003e22`; 4 reports. No person consent | n:307–308; `B1/rows.json` (O). Consent skipped: `mcp/consent.py:39 can_ask` returns False for any dispatched agent (O, code) |
| 21:50:26–21:51:19 | Person (page) | Chat shows nothing; Call refused | `anchor()` raises `Stop('Talking with an agent needs a map with one element at least.')`, `dispatch/__init__.py:2278` (dc4af39), :2381 (tree) | Person cannot reach an agent | Rich at 21:57:28 "be denied from talking to help before you do the fucking intake" (O); refusal text not logged (I) |
| 21:51:19 | Page read | Empty base `main` recreated, id `e41d6558…` | read of a cleared project, `home.py:1299` docstring | Same file name `main.metaform.sqlite3` | `B2/rows.json` (O) |
| 21:51:23 | Person (page "Start the intake") | Intake agent `a3941c37` on `intake-38c77d4a…` | `intake.js:302` → `startIntake` :222 | First turn = intake AXIOM; agent concludes "no intake started" | `B2."dispatch.raised"`; a3941c37 n:5, n:63 (O); who clicked (I) |
| 21:50:28–21:53:54 | Runner of 1d2d3085 | Keeps writing its thread into the new file | runner store resolved by base file name (I) | 13 lines (seq 90–102) land in the throwaway base | `B2` lines for 1d2d3085 seq 90–102 (O) |
| 21:52:15–21:53:19 | Person ↔ a3941c37 | "the whole context got lost when you cleared the project!!!" / "I never called the clear tool." | — | Agent disowns the clear | a3941c37 n:68, n:71, n:101, n:128 (O) |
| **21:53:54** | Person (I) | Restore of `20261016T215026Z` | `web/server.py:1678 restore` or CLI → `home.py:1266 restore_project` → `clear_project` :1274 | Backup `B2` of the throwaway base, then deleted: a3941c37's session row and 50 of its lines, 1d2d3085 seq 90–102. `main` copied back | `B2` contents (O). No agent transcript holds a restore call; shell history has none (O) → person via page (I) |
| 21:54:25 | Agent a3941c37 | Warns that a restore "is itself a clear" | — | After the fact | a3941c37 n:178 (O) |
| 21:54:49–55 | Person (I) | Web server SIGTERM, restarted | — | — | `run/web.log:3179–3184` (O) |
| 21:55:25–22:01:39 | Person ↔ 1d2d3085 | "I cant fucking believe it" … "that's a bug" | thread back in `main` | Chat visible again | `main` lines seq 103–125 (O) |
| 22:02:00 | Agent 1d2d3085 | Worktree `metaform-conversations`, fix workflow | — | Commit `b8bc70f` later, unmerged | n:440; `git log` (O) |
| 22:05:31, 22:07:29, 22:07:41 | Person | "I was waiting to see you start", "Are you stuck" ×2 | — | — | n:541, 564, 570 (O) |
| 22:07:58 | Agent 1d2d3085 | `dispatch_intake` with "intake start name=roundtable-2-spec" | dispatch intake | Session `0b356706` ("roundtable-e5") at 22:08:02, recorded in `main` | n:579; `main` sessions (O) |
| 22:08:26 | Intake 0b356706 | Base `roundtable-2-spec` added, `activate=False` | `intake/__init__.py:271` | New store | `spec.ops` seq 1 (O) |
| 22:09:30 | Agent 1d2d3085 | Claude Code `Workflow` wf_6fe49970 (build both products) | outside Metaform dispatch | ~6 subagents not on any ticket; `dispatch_peers` cannot see them | n:592 (O) |
| 22:10:23–22:19:35 | Intake 0b356706 | 66 MISS/BKN findings written as tickets | intake procedure | 66 open tickets duplicating the workflow's scope | `spec.work` rows 1–66 (O) |
| **22:20:28** | Intake 0b356706 | Intake finish activates `roundtable-2-spec` | `intake/__init__.py:1045–1047 store.activate_base(found.metaform)` | Page now reads the spec base; the chat ticket `8c003e22` and its thread stay in `main`, unseen | `spec.ops` seq 505; 0b356706 n:689 "Finishing switched the active map" (O) |
| 22:20:40 | Person | Types `/effort ultracode on`, `/goal resume prior goal` into the intake's thread | intake chat in the dock | Intake agent starts acting as orchestrator | `main` lines 0b356706 seq 23–24 (O) |
| 22:26:07–11 | Person (page Call) | New chat ticket `e2ce3739` in the spec base; new system agent `c528b47a` | `anchor()` finds no ticket in the active base, makes one; `resumed_conversation` (:2468 tree) finds no session for it | Fresh agent, no memory of the 1d2d3085 thread | `spec.work` row 67, sessions (O) |
| 22:26:33 | Agent c528b47a | "didn't include an objective… No agents are working on open tickets" (wrong: workflow running) | `<system>` as first turn; reads `dispatch_peers` | Person: "i assure you that you are wrong" | c528 n:52, n:57, n:110 (O) |
| **22:28:26–22:33:57** | Person (page Start all) | 66 claude ticket agents, one per ticket, ~5 s apart | `dispatch.js:190 startAllTickets` (dc4af39) loops every offered ticket; `dispatch start` :2189 checks no slots | 66 `dispatch run` processes; `dispatch_agents`=6 ignored | `spec."dispatch.sessions"` 66 rows (O); Rich 22:46:37 "i went in and clicked start agents i thought it would start seven" (O) |
| 22:45:16 | — | Machine-wide: 46 claude binaries, 5 codex, 45 dispatch runs | — | The "46 agents" Rich saw | c528 n:151 (O) |
| 22:46:45–22:48:55 | Agent c528b47a | `metaform_set dispatch_autostart=false` (result never returned); stops 34 agents | `dispatch stop` | 34 sessions "stopped by the person"; setting still `true` | c528 n:204–234; `project.sqlite3` settings (O) |
| 22:48:11 | Person | "I asked you four times to fucking start them… everything locks up and there's a thousand fucking agents" | — | — | c528 n:335 (O) |
| 22:49:13–22:51:14 | Person ↔ intake 0b356706 | "I keep talking to different versions of your context" / agent: "Me (roundtable-e5, this terminal)… Your main agent (roundtable-30, on the Metaform page)" / "my main agent who the fuck is my main agent you're the one" | intake thread kept open after finish, `intake.js:169 openIntakeChat` | Agent disowns being his agent, says it will tell the other session | 0b356706 n:931–1012 (O) |
| 22:59:18–23:01:37, 10-17 00:03:41–00:04:13 | Autostart (I) | 6 + 5 more agents on open tickets | dispatch autostart | Restarted work after tickets were closed | `spec` sessions (O); autostart setting `true` (O) |
| 23:29:03, 23:30:12 | Web server | `/api/dispatch-sessions` stuck 20 s, watchdog restarts ×2 | — | Page stalls | `web.log:3317–3327` (O) |
| 00:03:57–00:04:59 (10-17) | All three Claude sessions | "You've hit your session limit" | — | Orchestration stops | c528 n:643, 1d2d3085 n:838, 0b356706 n:1515 (O) |
| 01:19:21 (10-17) | Host | WSL "System is powering down", orderly | — | Reboot | `journalctl -b -2` tail (O). No kernel OOM, no oomd kill in that boot (O) |

The "crash" after Start all: the Linux VM did not reboot then (boot -2 runs 13:26–21:19 EDT). Rich's "everything locks
up" at 22:48 and the stuck server at 23:29 are consistent with load from ~50 agent processes; whether Windows itself
froze is unknown.

---

## 3. Findings, ranked

### F1. The person's conversation lives in the map's base store, so clear, restore and a base switch take it away

- **What happens.** `dispatch.sessions` and `dispatch.lines` are declared without `place`, so they default to
  `place='metaform'` (`data/tables.py:83`; `dispatch/__init__.py:115–124`), beside the map in
  `<base>.metaform.sqlite3`. The chat is also hung on a held ticket in that same store (`anchor`, :2264 dc4af39).
  - Clear at 21:50:26 removed the file, so the page had no thread (O: `B1` holds 273 lines, live store after clear
    held 51, a3941c37 n:122).
  - Restore at 21:53:54 runs `clear_project` first (`home.py:1274`), which deleted the throwaway base with the
    a3941c37 thread and the 13 lines 1d2d3085 wrote meanwhile (O: only in `B2`).
  - Intake finish at 22:20:28 activated another base; the next Call found no chat ticket in it, made `e2ce3739`, and
    started c528b47a with no memory (O). This is Rich's "another context came up knowing nothing".
  - The runner of a live session keeps writing to whichever file has its base's name: 1d2d3085's lines 90–102 went
    into the throwaway `main`, a3941c37's lines 51–60 went into the restored `main` (O), so a thread ends up split across
    stores (mechanism I).
- **Governing records.** PROJ-025 ("clearing … removes only the inference", "keeps what the person set up"),
  PROJ-030 ("a restore loses nothing either"), VIEW-045 ("the one always-available slot means the person can always
  reach an agent"), STORE-045 (memory already moved to project level for exactly this reason). The code contradicts
  all four; the records are right.
- **Pattern elsewhere.** Every per-session or per-person datum declared with the default place: `dispatch.raised`,
  `claims`, `claim_work`, `proposals`, `ticket_options`, `spend`, `attempts` (`dispatch/__init__.py:132–175`);
  `map.ticket_settings`, `map.glyphs`; and the 50 tickets themselves, which vanish from the board on a base switch.
- **Remediation.**
  1. Review commit `b8bc70f` on `fix/conversations-outside-map` (`/home/rich/metaform-conversations`): it moves sessions,
     lines and attempts to project-level tables `agent_sessions`, `session_lines`, `session_attempts` in
     `modules/dispatch.sqlite3`, carries old rows over (`carry_conversations`), and hooks it into clear and restore
     through `home.CARRIERS`. Two `tests/test_cli.py` failures were open on it at 00:02:53Z (1d2d3085 n:826); run those two
     tests on `dc4af39` and on `b8bc70f`, isolated, and fix any that fail only on the branch.
  2. Make sure the branch also covers a base switch, which its message does not name: in `system()`
     (`dispatch/__init__.py:2408` tree) look up the person's last system conversation by role across the project table,
     not by the active base's anchor ticket, so `metaform map activate <other>` and an intake finish resume the same
     `session_id`.
  3. Move `spend` and `attempts` to `place='project'` in the same change (spend already has a project table
     `spending`; drop the base copy rather than keep two).
  4. Merge `b8bc70f` plus steps 2–3 to the working branch; add CHANGELOG lines to dispatch.
- **Verify (fails today, passes after).** In a test home: start a system agent session on a project with a map, write
  three lines, then (a) `clear project --confirm`: `dispatch sessions` still lists the session with three lines;
  (b) `restore project <first backup>`: still three lines, plus any written between; (c) add a second base and
  `map activate` it, then POST `/api/system-chat`: answer carries the same `session_id`. Today (a) and (c) fail
  (observed in this incident: 51 vs 273 lines; new session c528b47a).

### F2. With no element on the map, the person cannot talk to any agent

- **What happens.** `anchor()` raises `Stop('Talking with an agent needs a map with one element at least.',
  'metaform intake prompt')` (`dispatch/__init__.py:2278` dc4af39, :2381 tree). Call, `/system` and stay-connected all go
  through it. The empty stage then offers only Start the intake (`intake.js:290–302`). Rich met this at 21:50–21:51, in
  the middle of a planning conversation, and started an intake he did not want (O: Rich 21:57:28; a3941c37 started 57 s
  after the clear).
- **Governing record.** VIEW-045 (the person can always reach an agent); the memory "Start: one line, helpdesk" (the
  system agent chat troubleshoots). The gate is the defect.
- **Pattern elsewhere.** Any conversation that needs a node: talk and raise (fine, they are about a node), and the
  stay-connected supervisor, which starts the system agent through the same anchor.
- **Remediation.** `b8bc70f` replaces the Stop with a non-ticket work id `conversation-system` when the map has no
  element. Keep that; also delete the `metaform intake prompt` next-step from every surface that shows this refusal.
- **Verify.** Empty project in a test home: POST `/api/system-chat` returns 200 with a session; today 400 with that
  message.

### F3. Start all started every ticket, ignoring `dispatch_agents` (fixed in `7b10595`, one residual)

- **What happens.** At `dc4af39`, `startAllTickets` (`page/app/agents/dispatch.js:190–195`) started every offered
  ticket in sequence, and `dispatch start` (:2189) only checked `startable`, never the slots; only autostart counted
  (`summon_room`). 66 runners started in 5.5 minutes against a limit of 6 (O). Commit `7b10595` (19:12 EDT) adds
  `free_slots`/`slots_used`, a refusal in `start`, a re-check in the runner (`over_limit`), and slices Start all to
  `free`.
- **Residual.** `const pending = free === null ? offered : offered.slice(0, free);` (dispatch.js, after `7b10595`): when
  the harness read fails, the page still fires every start; the server now refuses each one past the limit, so the
  person gets 60 failed-start toasts instead of a plain "N wait".
- **Governing record.** VIEW-039 as amended 2026-10-16.
- **Remediation.** 1. In `startAllTickets`, when `free === null`, read `/api/dispatch-agents` once more; if still null,
  start none and toast the reason with the error from `readHarnesses`. 2. Add one test in
  `modules/dispatch/tests/test_dispatch.py` that calls `start` 10 times with `dispatch_agents=6` and asserts six
  reservations and four Stops (if `7b10595`'s test does not already cover the tenth call).
- **Verify.** Test home, 10 open tickets, 6 slots: Start all leaves 4 in To do marked Waiting and launches 6 runner
  processes; with `/api/dispatch-agents` failing, launches 0.

### F4. The system agent receives its role prompt as the person's message, with no objective and no prior thread

- **What happens.** `runner.py:3268` (dc4af39) sends `prompt('system', …)`, the `<system>` element of
  `dispatch/resources/prompts.xml` (line 255 on), as the session's first turn the moment the agent starts. The agent
  reads it as a user turn ("Your message set up the orchestrator role…", 1d2d3085 n:49 and c528 n:52, O). Its TASK
  begins "Investigate the user's objective" and ends at "Write tickets"; there is no objective in that turn and no step
  to start or follow agents. After F1's base switch the same prompt opened a second, blank agent. c528 then checked
  `dispatch_peers`, which lists only ticketed agents, and told Rich nothing was running while a workflow and its
  subagents were (O). The agent's own memory `orchestrator-prompt-is-the-assignment.md` records that it read "four"
  sends of this prompt as setup. The orchestrator also built through Claude Code `Workflow` outside Metaform's tickets
  (1d2d3085 n:592) while the intake it dispatched wrote 66 tickets for the same scope (O), which is why Start all
  duplicated live work.
- **Governing records.** BASE-054 (the orchestrator "watches the board", "reports to the person"), VIEW-045 (the agents
  the person summons "write tickets and start, stop and message agents").
- **Role of the text.** The prompt is Rich's and tuned; "Investigate the user's objective" is right for a turn that
  carries one. The defect is the delivery: it is sent alone, before the person has said anything.
- **Remediation.**
  1. `runner.py`, the `elif self.system:` branch (:3420 tree): do not call `self.turn(text)` at start. Keep `text` on the
     runner (`self.opening_text`) and send it as the head of the first person message, one turn: role prompt, a blank
     line, then the person's words. The resumed path (`self.resume`) stays as is.
  2. In the same first turn, after the role prompt, add the filled `<conversation_state/>` place (new empty element
     inside `<system>`, code-filled): the open tickets count, the sessions running in this project with their work id
     and how they were started (dispatch runner vs other), and, when a previous system conversation of this project
     exists, its session id and last person message. Code fills it; the wording around it needs Rich (below).
  3. `dispatch_peers` description and result: name that it lists ticket agents only, and add `dispatch sessions` as the
     next step when it is empty.
- **Verify.** Test with a fake ACP agent: start a system agent; assert no turn is sent before the first
  `dispatch message`; then that the first turn text starts with the `<system>` text and ends with the person's
  message. Fails today (turn sent at start).
- **Needs Rich.** (a) Whether the role prompt rides with the first message (step 1) or stays a separate first turn.
  (b) Wording for a fifth TASK step and for the state block. Proposed, for him to accept or replace:
  "5. **Then:** start agents on the tickets within the free agent slots (`dispatch agents` says how many), follow them
  with `dispatch sessions`, and tell the user as each one lands. When this message carries no objective, the open
  tickets and the work already running are the objective: read them and propose the plan before asking anything."

### F5. A destructive clear by the person's own agent skips the person, and the caution understates what goes

- **What happens.** `consent.can_ask` (`mcp/consent.py:39–45`) returns False whenever `METAFORM_ROLE`/`METAFORM_WORK`
  is set, i.e. for every dispatched agent, including the person's system agent whose chat is on the page. So the agent's
  own `confirm:true` cleared the project 31 s after the caution (O, n:302–308). The caution
  (`home.Cleared.caution`, :1080) lists bases and report files only; it never says the 50 tickets, the open question,
  or the conversation in progress go with the store. The agent's choice was also avoidable: a named intake
  (`intake start name=…`) makes a separate base without clearing, which is what it did 18 minutes later.
- **Governing records.** CLI-011 and MCP-006 (consent of the person for a caution), PROJ-030.
- **Remediation.**
  1. `consent.can_ask`: when `METAFORM_ROLE` is the person's system agent (role `system`), do not return False on the
     dispatched check; route the form through the runner's existing elicitation relay (the page already shows an
     `elicitation` line and a `question-waiting` signal, observed `B1` seq 24–25). First confirm that Claude Code forwards
     an MCP server's elicitation to its ACP client; if it does not, have `metaform_clear_project` called by a system
     agent write a held question on the page (map messages) and return "waiting for the person" until answered.
  2. `Cleared.caution` and `Cleared.said` (`home.py:1080–1091`): add the counts the store holds that are not inference:
     open and done work records, open questions, running sessions and lines (until F1 lands; after F1, say they stay).
  3. Add to the `clear_project` tool description in `mcp/server.py:287`: "To map again beside the current map, start a
     named intake instead; a clear is for discarding the map." (Tool descriptions are code, not authored prompts.)
- **Verify.** Test: a system agent session (`METAFORM_ROLE=system`) calls `metaform_clear_project confirm=true`; the
  project is not cleared and a consent form or held question appears. Today it clears.

### F6. The advertised restore command now restores the wrong backup

- **What happens.** The clear's result says `"restore":"metaform restore project roundtable"` with no backup name
  (`Cleared.restore`, `home.py:1094–1096`). `restore_project(name=None)` picks the newest (`backups()` sorts by name
  descending, :1245; :1270). After Rich's restore the newest is `B2`, the empty throwaway base. Running the command the
  clear printed would today clear both live bases (backing them up) and bring back an empty `main` (O, by code and
  `rows.json`). Two agents and the autoharness skill patches repeated the bare command (`79eea774`, `38a3779f`).
- **Governing record.** PROJ-030 ("tells the person the backup's name and the one command that brings it back").
- **Remediation.** 1. `Cleared.restore`: return `f'metaform restore project {self.project_id} {self.backup}'` when
  `self.backup` is set. 2. Same for the page's clear toast and `Restored.said` (name the backup made of what was there
  before, with its own restore command). 3. `restore_project` with no name: refuse when the newest backup was made by a
  restore (record `"made_by": "restore"` in `rows.json` from the `clear_project` call at :1274) and list the choices.
- **Verify.** Test: clear (backup A), restore A (backup B made), then run the string the first clear returned: it
  restores A. Today it restores B.

### F7. The intake agent, left open as the person's chat after it finished, disowns being his agent

- **What happens.** After the intake finished, Rich kept typing into its thread (`intake.js:169 openIntakeChat`, the
  dock keeps it as a conversation). It took over orchestration under `/goal resume prior goal`, then told him
  "Me (roundtable-e5, this terminal)… Your main agent (roundtable-30, on the Metaform page)" and "I'll tell your main
  agent" (0b356706 n:939, n:962). Earlier a3941c37 said "I never called the clear tool" (n:71). Three agents answered
  him about one project inside 30 minutes, each sure the others were the real one (O). Nothing in the intake's first
  turn or later tells it that, once finished, it is talking to the person on the page.
- **Governing record.** VIEW-045 (the person meets purpose-defined agents only).
- **Remediation.**
  1. `runner.py`: when a person message arrives on an intake session whose base layer is ready (finished), prepend a
     one-line frame from a new `prompts.xml` element `<intake_finished>` (dispatch module), sent once per session.
  2. Dock (`dock/threads.js`): on an intake thread whose intake is finished, show above the composer "This intake is
     finished. My agent has the project's conversation." with a button that opens My agent; the thread stays usable.
- **Verify.** Fake ACP agent test: finish an intake, send a person message, assert the first message after finish
  carries the `<intake_finished>` text once.
- **Needs Rich.** Wording of `<intake_finished>`. Proposed: "Your intake is finished. The person is now talking with
  you on the Metaform page; you are their agent in this thread. Answer as yourself, and do not send them to another
  session."

---

## 4. Per incident

### Incident 1: "everything reset" and "could not speak to an agent before an intake"
- **Trigger.** Person's request (21:49:41) → system agent 1d2d3085 → MCP `metaform_clear_project confirm=true`
  (21:50:26) → `home.clear_project`.
- **Destroyed.** From the live store: the `main` map (78 elements, 111 joins, 392 items, 1119 ops), 50 tickets, 1 open
  question, the chat ticket and its 88-line thread; 4 report files. All backed up first in `B1`.
- **Spawned.** An empty `main` (21:51:19) and an unwanted intake agent a3941c37 (21:51:23).
- **Confirmation / backup / limit.** The agent's own `confirm:true`; no person consent (F5). Backup made (PROJ-030
  worked). The restore at 21:53:54 then deleted a3941c37's thread (F1, F6).
- **Root cause.** F1 (conversation in the base store) and F2 (chat gated on a map element).
- **Pattern.** Per-person state stored per base (F1 list).
- **Fix and check.** F1, F2, F5, F6 steps and checks.
- "~5 hours lost": the conversation itself spanned 20:24:14–21:50:26 (1 h 26 min); the map was from 10-15. Neither was
  lost; the context of 1d2d3085 stayed intact in its process and transcript (it said so at 21:56:51, n:372).

### Incident 2: tickets set up, then the orchestrator would not orchestrate
- **Trigger.** 1d2d3085 dispatched the spec intake (22:07:58), which wrote 66 tickets; 1d2d3085 itself built through a
  Claude Code `Workflow` outside Metaform (22:09:30). The intake finish switched the base (22:20:28); the person's next
  Call gave a new agent c528b47a (22:26:11) whose first turn was `<system>` alone.
- **Effect.** c528 asked for an objective and reported "no agents working" from `dispatch_peers` (F4). Rich's "start"
  requests went to 1d2d3085 (22:05–22:07) and to c528; neither started a ticket.
- **Root cause.** F4 (prompt delivered alone, no start step, peers list blind to workflows) plus F1 (base switch gave a
  blank agent).
- **Fix and check.** F4, F1 step 2.

### Incident 3: 46 agents and the lock-up
- **Trigger.** The person's Start all on the board (22:28:26), page `startAllTickets` → `/api/dispatch-start` ×66 →
  `dispatch start`.
- **Spawned.** 66 claude ticket agents (each its own `dispatch run`, ACP adapter and Claude CLI), on top of the
  workflow's subagents and 3 conversation agents; 46 claude binaries machine-wide at 22:45:16.
- **Limit.** `dispatch_agents`=6 existed and was not applied to Start all (F3). Autostart was not the trigger, despite
  two agents saying so (0b356706 n:908, c528 memory).
- **Crash.** No reboot or OOM in the Linux journal at that time; orderly WSL power-down at 01:19:21Z. Lock-up from load
  is inferred.
- **Fix and check.** `7b10595` plus F3 residual.

### Incident 4: the agent that "was not his agent", the map gone again, a context that knew nothing
- **Agent disowning.** a3941c37 at 21:52:19 and intake 0b356706 at 22:49–22:51, both talking in page threads (F7).
- **"Map deleted again."** Two events fit: the restore's own clear at 21:53:54 (deleted the throwaway base and
  a3941c37's thread) and the intake finish at 22:20:28 (the 78-element `main` replaced on screen by the 85-element spec
  map). Which one Rich meant is unknown.
- **"Another context came up knowing nothing."** c528b47a at 22:26:11 (F1 base switch, F4).
- **Fix and check.** F1 step 2, F4, F7.

---

## 5. What should be true instead

1. The person's conversations (sessions and lines) are the project's, in `modules/dispatch.sqlite3`. No clear, restore,
   new base, activation or intake finish removes or hides them.
2. Call always reaches the person's agent, with or without a map. The same system conversation resumes after any base
   change; a new one starts only on `/new`.
3. The system agent's first turn is the role prompt together with the person's first words and a short state block
   (open tickets, running sessions and how they were started, the previous conversation's id). It plans, writes
   tickets, starts agents within the free slots, follows them, and reports.
4. Every start path, single, Start all, autostart, an agent's `dispatch start`, counts the same slots; a start past
   them waits in To do.
5. A clear asked for by any agent the person talks to waits for the person's consent on the page; its caution names
   tickets, questions and conversations; its result names the backup in the restore command.
6. A restore merges what was written since the backup; a bare `restore project` never picks a backup made by a restore.
7. A finished intake's thread says it is finished and points to My agent; the intake agent answers as the person's
   agent in that thread.

Gated by state: no map → Call still works (1, 2); intake running → its thread is the intake's; intake finished →
(7); base switch → (1, 2) unchanged; slots full → (4).

---

## 6. Tickets

Map nodes checked with `metaform map where` against a scratch copy of the metaform project (active base
`feature-code-alignment-20261013`).

1. **code.dispatcher.agent** (exists, "dispatch"). Condition: trouble. Task: land F1 and F2 by reviewing and merging
   `b8bc70f`, plus F1 steps 2–3 (resume across base switch; `spend`, `attempts` at project level). Verify: F1 (a)(b)(c)
   and F2 checks in a test home.
2. **code.dispatcher.agent**. Condition: trouble. Task: F4 delivery: hold the `<system>` turn until the first person
   message, fill a code-made state block, fix `dispatch_peers` wording. Verify: fake-ACP test that no turn precedes the
   first person message. Needs Rich: TASK step 5 and state-block wording.
3. **code.service.backup** (exists, "Backup and restore"). Condition: trouble. Task: F6: backup name in
   `Cleared.restore`, page toast and `Restored.said`; refuse a bare restore onto a restore-made backup; F5 step 2
   caution counts. Verify: clear A, restore A, run the first clear's printed command, A comes back.
4. **code.server.tool** (nearest MCP node offered by `map where`). Condition: trouble. Task: F5 steps 1 and 3: person
   consent for a system agent's caution call, tool description for named intake. Verify: system-role test call does
   not clear without the person.
5. **code.interface.graphical** (exists, "Web GUI"). Condition: trouble. Task: F3 residual (`free === null` starts
   none) and F7 step 2 (finished-intake banner with My agent button). Verify: Start all with a failing harness read
   launches 0; finished intake thread shows the banner.
6. **code.processor.intake** (exists, "intake"). Condition: trouble. Task: F7 step 1, `<intake_finished>` frame on the
   first person message after finish. Verify: fake-ACP test. Needs Rich: the frame's wording.

---

## 7. Recovery (not performed)

**First: do not run `metaform restore project roundtable`** (F6). The newest backup is `B2`, the empty base; that command
would clear both live bases.

What still exists:

| Item | Where | State |
|---|---|---|
| `main` map: 78 elements, 111 joins, 394 items, 7 properties, 1146 ops | `main.metaform.sqlite3` | Live, `integrity_check` ok, not active |
| `roundtable-2-spec` map: 89 elements, 139 joins, 295 items, 103 properties | `roundtable-2-spec.metaform.sqlite3` | Live, active, ok |
| Tickets | `main.work` 50 (48 done), `spec.work` 70 (62 done) | Live |
| Memory graph | `modules/memory.sqlite3`: 155 entities, 969 observations (21:57Z–23:36Z), 155 joins | Live; project-level, never touched |
| 1d2d3085 chat on the page | `main` `dispatch.lines`: 217 of its lines (seq 1–89, 103–231) | Live, in the inactive base |
| 1d2d3085 lines seq 90–102 (13) | `B2/stores/main.metaform.sqlite3` only | Backup |
| a3941c37 session row and 50 lines | `B2` (plus 10 lines, seq 51–60, in live `main`) | Backup + live |
| c528b47a chat (261 lines) | `spec` | Live |
| 0b356706 (intake/"roundtable-e5") chat (709 lines) | `main` | Live |
| Full conversations, every word | `~/.claude/projects/-home-rich-roundtable/` `1d2d3085…jsonl` (4.9 MB), `c528b47a…jsonl`, `0b356706…jsonl`, `a3941c37…jsonl`; workflow journals under `1d2d3085…/subagents/workflows/` and `0b356706…/subagents/workflows/` | Live |
| Claude memories | `~/.claude/projects/-home-rich-roundtable/memory/` (5 files) | Live |
| Code | `/home/rich/roundtable` master `4d3e2e2`; 14 worktrees and branches (`rt2-final`, `failsafe`, `master-pile` `c5db1dc`, …); `/home/rich/playground` `9b4bae5` | Live |
| Lost for good | `/tmp/claude-1000/-home-rich-roundtable/…/tasks/*.output`, `/tmp/rt2-handoff.*`, `/tmp/master-pile-1915.patch`, `/tmp/pg-smoke` | Cleared by the reboot; the handoff is still in `docs/roundtable-2/` and the attachment zip; the pile is branch `master-pile` |

Steps, in order, for Rich or an agent he names:

1. **See the old map and chat.** On the page, or `metaform map activate main` in `/home/rich/roundtable`. Nothing is
   removed; `metaform map activate roundtable-2-spec` switches back. Call on My agent then finds ticket `8c003e22` and
   its thread. Its session row still says `running` with pid 58504, which died at the reboot; let the dispatch
   supervisor mark it ended (`metaform dispatch sessions`), then Call with Resume to reopen `1d2d3085` in place, since
   the adapter advertises `resume` and `load` (`B1` state line).
2. **Or reopen the conversation directly** in Claude Code from `/home/rich/roundtable`: `claude --resume
   1d2d3085-2152-4787-8ce6-a69f765d4834`. This bypasses Metaform's record.
3. **Merge the 13 + 46 lines back** (optional, cosmetic for the page). With the web server and every `metaform dispatch
   run` for roundtable stopped, on a copy first (`cp -a` the store with its `-wal`/`-shm`):
   ```sql
   ATTACH 'file:/home/rich/.metaform/backups/clear/roundtable/20261016T215354Z/stores/main.metaform.sqlite3?mode=ro' AS b2;
   INSERT OR IGNORE INTO "dispatch.lines" SELECT * FROM b2."dispatch.lines";
   INSERT OR IGNORE INTO "dispatch.sessions" SELECT * FROM b2."dispatch.sessions"
     WHERE session_id = 'a3941c37-6321-4100-a8ba-f4e7c8fc1813';
   ```
   Dry run on copies: 8 lines of 1d2d3085 and 46 of a3941c37 insert; 9 names collide (`state`, `turn`, two tool ids)
   and are kept as the live store has them. Columns match (layout 16 in both). Compare counts before and after, then
   put the copy in place.
4. **Keep the backups.** `B1` is the only full copy of `main` as it stood at 21:50:26; `B2` is the only copy of step 3's
   rows.
5. **After F1 lands**, its `carry_conversations` moves these threads into the project table on first read; do step 3
   before that, so the carried rows are complete.

Recovery verdict: no work is lost. Both maps, all tickets, memories and code are live. The only data outside live
stores are 13 chat lines and one intake session in backup `B2`, and every word of every conversation is in the Claude
Code transcripts.

---

## 8. Other defects seen

- The intake started from the page at 21:51:23 with no note decided it was not assigned an intake and stopped
  (a3941c37 n:63); the empty-stage Start the intake does not make the assignment explicit.
- `metaform_set dispatch_autostart=false` from c528 never returned a result (backgrounded, n:206) and the setting is still
  `true`; autostart then restarted 11 agents (22:59Z, 00:04Z).
- `dispatch_agents` is per folder; nothing caps agents machine-wide (45 runs across projects at 22:45Z).
- `/api/dispatch-sessions` stuck 20 s twice at 23:29–23:30Z under load, forcing watchdog restarts (`web.log:3317`).
- Web log repeats `sqlite3.ProgrammingError: SQLite objects created in a thread…` in `dispatch_waiting` (`web.log:3119`).
- Autoharness skill patches staged during the incident (`79eea774`, `38a3779f`) teach the bare restore command (F6).

---

## 9. What the 66 Start-all agents completed (added 2026-10-18)

Source: read-only copies of `~/.metaform/projects/-home-rich-roundtable-001/modules/dispatch.sqlite3` (table
`dispatch.agent_sessions`, where the sessions now live) and the two base stores' `work` tables. Raw data beside this
report: `roundtable-2026-10-16-sessions.csv` (all 105 sessions with their ticket's task, outcome and resolution; column
`start_all_swarm` marks the 66) and `roundtable-2026-10-16-tickets.json` (all 120 tickets of both bases, every field).
Session tokens and nonces are left out.

**The 66 sessions started 22:28–22:34 UTC.** 32 ended "the ticket is done", all between 22:29 and 22:41; 34 ended
"stopped by the person" at 22:46–22:48, when agent c528b47a stopped them.

**Of the 32 that finished:**
- **25 confirmed and closed, no code.** The workflow wf_6fe49970 (started by system agent 1d2d3085 at 22:09) had already
  built the thing: Roundtable 2's engine in `30fbc90`, the playground's server and agent harness in `932a535` and
  `3c9a253`. Each agent checked the requirement against that code and closed the ticket citing file and line
  ("Already built", "No code changed", "Built in commit 30fbc90").
- **7 record work not in those commits:** runner fencing (`a1d5530`, `387f2f5`, branch runner-fencing); the report
  fallback chain in `runner.py`; PASS turns recorded unjudged; repeat detection (`e5496a3`, branch repeat-detection);
  OpenRouter retries for 408, 429, 5xx and dropped connections; `seat_mcp` for ACP seats; the offline stub table
  (table 7 of `scripts/check.py`). Several were uncommitted changes in the shared working tree the workflow also wrote
  to, so the records do not always prove which agent wrote the code (I).

**Where that work is now (O, `git merge-base --is-ancestor` on 2026-10-18):** runner fencing is on master directly.
The rest reached master through `974e46d` (failsafes, retries, PASS), `927fc4e` (Jev, repeats vetoed in code) and
`0c42e0f` (report fallback, seat_mcp, offline proof). Branch repeat-detection (`e5496a3`) was never merged; its feature
is on master through those commits. Master is `4d3e2e2`. The playground's cited commits are all on its `main`
(`9b4bae5`), working tree clean.

**Of the 34 stopped:** 27 tickets were closed later by other agents: 4 at 22:55–22:58 (Jev judging, the Jev version pin,
the sufficiency gate, the round protocol, fixed in the shared tree), 17 playground tickets at 23:03 citing `9b4bae5`,
6 Roundtable 2 tickets at 00:03 citing master `4d3e2e2`. 7 remain open, mostly playground: the renderer and client, the
dark room, the person walking in the world, `src/game`, per-agent history.

**In short:** the swarm wrote about 7 pieces of code and spent most of its run confirming what the workflow had built;
the building that night was the workflow's and the agents' that closed tickets after the swarm was stopped.
