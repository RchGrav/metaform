# Critic: ordinary use must not overwhelm the machine (runaway, fan-out, load)

Date 2026-10-17. Tree: branch `events-not-polling-2026-10-15` with uncommitted changes. Every finding below was also checked against HEAD `7b10595` and holds there. Measured in isolated homes under the session scratchpad, with the fake ACP agent. No real agent, no real home, no live server was used.

## 1. Verdict

At idle the long-running processes are quiet: 0 CPU ticks in 60 s for the web server (with and without a page open), runners, the fake agents, `mcp serve` and `memory watch`. Under load it is a different story. The agent ceiling is enforced where a launch is *asked for*, never where a process is *spawned*. It is also counted per project, not per machine, and it does not cover the supervisor's retries. So after a crash every dead session comes back at once, whatever the limit says. On top of that, every dispatch-relevant change makes the web server sweep every open ticket with a write transaction. That pegs a core and slows every agent's writes. Once agents are running, the only off switch is stopping them one ticket at a time.

## 2. Findings, ranked

### F1 (blocker) After a crash, the supervisor resumes every dead session at once, ignoring `dispatch_agents`
- **What happens.** `settle` writes each session whose runner died as ended with `how = 'the runner is no longer running'`, which is not a person's end. `retry` then resumes each one with `resume_spawn`. Nothing on that path counts slots. It runs on every autostart pass: at web start, on page open, and on each dispatch change. In Rich's case, if the 46 tickets Start all launched were running when the PC died, the next web start with Autostart checked relaunches all 46. Each can be retried `dispatch_retries` (2) times, so up to 138 launches.
- **Evidence (observed).** Scratch test `critic-load-r1/../exp/test_crash_fanout.py`: 5 fake sessions running, runners and agents SIGKILLed, limit then lowered to 1:
  ```
  slots_used while running 5
  settled 5
  slots_used after settle 5 free 0 limit 1
  retry resumed 5 with dispatch_agents = 1
  ```
  Code: `src/metaform/modules/dispatch/__init__.py:1948-2005` (`retry`: no `free_slots`/`summon_room`/capacity); `recovery.py:281-302` (`settle`); `runner.py:893` (`if not resume and ... over_limit`, so a resumed runner skips the last-line check too).
- **Governing record.** BASE-052 amendment 2026-10-08/12 (supervisor P012). It says "budgets checked before every start are what keep a resume loop bounded", but every budget defaults to 0 (no limit), so nothing bounds it. VIEW-039 amendment 2026-10-16 (start keeps to the agent slots). The code is right to resume. It is wrong to resume past the ceiling the person set.
- **Root pattern: admission at the door, not at the spawn.** Each launcher checks its own predicate, or none. Other places with the same gap:
  - `prep` (merge assist, `__init__.py:2342-2362`): no `summon_room`, although its docstring says it "is an agent the person summons".
  - The worker branch of `resume` (`__init__.py:3786`): only `not worker` is checked.
  - The runner's `over_limit` skips every `resume=` launch (`runner.py:893`).
- **Remedy.**
  1. In `dispatch/__init__.py` add `live_agents(store) -> int`. It counts the sessions in state `running` that are not summoned and not `editor`, plus the `dispatch starting` reservations younger than `STALE_START`. A session `settle` has ended counts as not live.
  2. Add `admit(ctx, store, n) -> int`, which returns `max(0, min(n, dispatch_agents - extra_summoned - live_agents))`. Call it inside the same `store.atomic()` that reserves.
  3. In `retry`, collect the due candidates first, sort them oldest `next_at` first, take `admit(ctx, store, len(due))` of them, and resume only those. Leave the rest's `attempts` row untouched (no retry counted, `next_at` unchanged), so the next pass takes them. Return `retry_due = now + RETRY_SECONDS` while any remain, so the runner or the web server's `schedule_retry` comes back.
  4. In `runner.py` `dispatch()`, extend the `over_limit` check to `resume` launches whose noun `retry=true` is set. Keep the person's own `dispatch resume` and Call outside it.
  5. In `prep`, before `Popen`, raise the same `Stop` as `converse` when `summon_room(ctx, store) <= 0`.
- **Verify.** Turn the scratch test into a test in `src/metaform/modules/dispatch/tests/test_liveness.py` next to `test_a_session_whose_runner_and_agent_died_with_the_machine_is_settled_for_the_supervisor`: 5 dead sessions, `dispatch_agents = 1`, assert `len(retry(...)['retried']) == 1` and four `attempts` rows still at `retries == 0`. It fails today (5 resumed) and passes after the fix.

### F2 (blocker) The agent ceiling is per project; nothing limits agents per machine
- **What happens.** `dispatch_agents` is read per folder, and `slots_used`/`free_slots`/`start_work` count only the current project's store. Two projects at 3 slots run 6 agents. A program split in two (Rich's roundtable in two halves) gets twice the agents, and every extra project adds more. Each agent costs a runner (79 MB, 7 threads), an `mcp serve` (81 MB) and the real agent CLI, which was not measured here because only the fake was used.
- **Evidence (observed).** Projects `crx` and `cry` in one home, each with `dispatch_agents 3` and Autostart on. Live runners: `3 project crx`, `3 project cry`. Idle footprint from `/proc`: runner `rss=79152 thr=7`, `metaform mcp serve` `rssKB 81424 threads 2`. Code: `__init__.py:2567-2588` (`free_slots`, `slots_used` over `store.work(...)` of one project); `__init__.py:263` (`settings.number('dispatch_agents', 5, min=1, person_only=True` with no max).
- **Governing record.** VIEW-039 (amended 2026-10-16) and BASE-052. Neither says whether the slots are per project or per machine. Rich's incident is a machine crash, so the machine is what the limit has to protect.
- **Root pattern: a ceiling on a machine resource kept per project.** The same scoping applies to `summon_room`, intake (`__init__.py:3821`) and `start_raised`.
- **Remedy.**
  1. Add a home-level agent ledger, `home.home()/run/agents/`. The runner writes one file per live session in `Session.run` right after `session/new` succeeds: pid, runner identity from `recovery.identity`, project and role. It removes the file in its end path. Writes go through `home.write_private`.
  2. Add `machine_agents() -> int` in dispatch. It counts the ledger files whose pid still carries the recorded identity and deletes the stale ones as it goes. That is a read at admission, not a timer.
  3. Make `admit` (F1 step 2) take `min(project room, dispatch_machine_agents - machine_agents())` under `home.file_lock(run/agents/admit.lock)`.
  4. Declare `dispatch_machine_agents`, person-only, global scope, defaulting to the current `dispatch_agents` default (5). Show it beside Agents in the Autostart window.
- **Needs Rich.** Whether to add the machine-wide setting, or to make `dispatch_agents` itself global. A new control needs his say. Proposed label text for him to accept or replace: "Agents on this machine: the most agents Metaform runs at once across every project."
- **Verify.** Test: two projects, each `dispatch_agents 3`, `dispatch_machine_agents 3`, Autostart on in both, with the fake agent in `hold` mode. Assert that at most 3 `dispatch run` processes are alive across both projects. Today there are 6.

### F3 (major) Every dispatch change makes the web server sweep every open ticket with a write transaction, even when nothing can start
- **What happens.** `start_work` calls `progress.refresh` for every open ticket before it looks at capacity (`__init__.py:1815-1817`). Each `refresh` opens `store.atomic()`, the project's write transaction (`progress.py:89-93`), and re-reads the registry stamp. The web server runs this pass for every coalesced batch of `map.changed` that names `work` (`server.py:141-143`, `183-190`, `597-631`). An agent editing a ticket note counts.
- **Evidence (observed).**
  - One pass with 200 open tickets and 0 free slots: `autostart pass ms 978.7`. cProfile: `progress.py:89(refresh)` 200 calls, 1.659 s of 1.866 s, with `store.atomic` called 402 times.
  - A burst of 300 unrelated note edits plus `events.announce`, web server CPU from `/proc/<pid>/stat`: Autostart off, 135 ticks (1.35 s) over 8 s. Autostart on with 0 free slots, 743 ticks (7.4 s) over 8 s, about 93% of a core.
  - With 2 fake agents running, the same 300 writes took the writer 22.3 s instead of 7.9 s, while the server burned 21.2 s CPU. The extra time is write-lock contention, and every agent's writes suffer it.
  - Runners filter correctly: about 38 ticks each per 300 events.
- **Governing record.** CLAUDE.md section 2, rules 1, 2 and 4. QUAL-015. BASE-053.
- **Root pattern: a sweep on every event.** A handler recomputes and rewrites the whole collection instead of the records the event names. Other places with the same shape:
  - `moved_on` runs a full autostart in every runner as its session ends (`runner.py:935-957`).
  - `start_raised` calls `summon_room` once per queued row, and each call re-reads every session (`__init__.py:2608-2614`).
- **Remedy.**
  1. Delete the `for record in store.work(...): refresh(ctx, store, record)` loop from `start_work`. `progress.changed` already reconciles the tickets a change names (`progress.py:125-140`).
  2. In `start_work`, compute `capacity` first (the same transaction). When `capacity == 0` and `retry` has nothing due, return before any per-ticket work.
  3. Where a candidate is about to be reserved, call `progress.blocked` (read-only), which `rework_blocked` already does. No write.
  4. In `progress.refresh`, read first with `store.tables(write=False)`. Open `store.atomic()` only when `_advanced` or a signal change requires a write.
  5. Make note-only ticket edits publish `kinds: ['note']`, and leave `note` out of `STARTS` in `server.py`, so `dispatch_change` is false for them.
- **Verify.** Test in `src/metaform/modules/web/tests` (existing burst style): 100 `edit_work(note=...)` plus `announce` with Autostart on and 0 free slots must call `progress.refresh` 0 times and `autostart` at most once. Measure: rerun `critic-load-r1/burst.py 300` with the server CPU delta under 150 ticks, the Autostart-off baseline.

### F4 (major) No way to stop every agent; stopping the web GUI or unchecking Autostart leaves them all running
- **What happens.** Runners are detached in their own sessions (`run_reserved`, `group_options()`), so they outlive the server. Unchecking Autostart only stops new starts. The only stop is `dispatch stop <id>`, one ticket at a time, and the person needs the ids. With 46 agents and a machine already thrashing, that is a long serial job.
- **Evidence (observed).** After `metaform web stop`, 18 of my processes survived (6 runners, 6 agents, 6 agent children). Stopping them took `dispatch stop <id>` per ticket at about 0.75 s each, so 46 would take about 35 s, with ids read from `dispatch sessions --json`. The verbs (`__init__.py:4391`): `stop` takes one id, and no verb stops all.
- **Governing record.** BASE-052 (person's stop) and VIEW-039 (agents stopped from the page). The quality bar says users keep control over work they start.
- **Root pattern: detached work with no collective off switch.** The intake and summoned agents and the system agent are in the same position. `memory watch` also outlives `web stop` (see section 5).
- **Remedy.**
  1. Add the verb `dispatch halt [project=all]`. In one pass it sets `dispatch_autostart` false for the project (or every project), then for each `running` session calls the existing cancel-then-`end_group` path of `stop` concurrently, through a thread pool of the session count, and records each as `stopped by the person`, so `retry` never resumes them.
  2. Have `web stop` print the count of agents still running and the `dispatch halt` call.
  3. Put a page control in the agents pane that posts to a new `/api/dispatch-halt` (in `DISPATCH_ROUTES`).
- **Needs Rich.** The page control and its wording are new UI (his rule: a control only when he asks). The CLI verb is mechanism. Proposed label: "Stop all agents".
- **Verify.** Test: 3 fake `hold` sessions. `dispatch halt` returns with every `dispatch run` process gone within 5 s, `dispatch_autostart` false, and a following `autostart` with `RETRY_SECONDS = 0` resumes 0. Today the verb does not exist.

### F5 (major, inferred from code) A merged ticket writes a follow-up ticket that autostart starts, which can merge and write another
- **What happens.** `merge_due` writes, after an unreviewed merge, a plain open ticket with a task, "Newly committed feature, needs testing before the next release: …" (`merge.py:307-311`). It is not held. `start_work` takes every untaken ticket with a non-empty task (`__init__.py:1822-1823`), so Autostart starts an agent on it. If that agent commits (a testing agent writes tests), its worktree passes, waits `dispatch_review_minutes`, merges, and writes the next follow-up with the task text nested again. Each generation is one more paid agent, and nothing ends the chain. This needs `dispatch_worktrees` and `dispatch_test_command`, both off by default.
- **Evidence.** Code read at HEAD and in the working tree. Not run end to end, because it needs git worktrees plus a test command; unknown whether a real testing agent commits.
- **Governing record.** VIEW-044: "logged as a newly committed feature that needs testing before the next release". Its acceptance says "a ticket or a knowledge item marked committed, needs testing before release". That is a release log entry, not a work order for agents. The code goes further than the record, and the record is right.
- **Root pattern: work that writes its own successor work.** Check `autoticket.promote` (`autoticket/__init__.py:234`), which is gated by the person's promote and fine, and every future `add_work` in a done-handler.
- **Remedy.**
  1. In `merge.py:307`, write the follow-up held. After `add_work`, set the ticket's `hold` in `ticket_settings` the way `start_work` reads it (`kept.get(...).get('hold')`), or move it to Backlog with `held`.
  2. Leave it out of glyph chaining (`next_ticket`) the same way.
  3. Never write a follow-up for a ticket that is itself a follow-up: test the task prefix or add a `kind='release'` field.
- **Verify.** Test in `test_merge.py`: after `merge_due` merges, `start_work` with Autostart on and free slots reserves no ticket whose task starts with "Newly committed feature". It fails today.

### F6 (minor) A runner that dies before its session holds an agent slot for 180 s, with no traceback
- **What happens.** One of 3 runners that autostart launched at once died at startup with `Error: ProgrammingError: SQLite objects created in a thread can only be used in that same thread. The object was created in thread id 134928591222336 and this is thread id 134928574613056.` That is the whole of `/tmp/metaform-dispatch-de2fb4b6....log`. The ticket stayed `dispatch starting be67…`, so `dispatch agents` reported `free: 0` with 2 agents running against a limit of 3, until `STALE_START = 180` (`__init__.py:1744`) expired.
- **Evidence (observed)** as above. `runner.py:836-843` gives the reservation back only for a `Stop` from `mcp_server`. Any other exception keeps it. The root cause of the thread error is unknown: there is no traceback.
- **Governing record.** BASE-052 ("a crashed start never holds a slot for good").
- **Root pattern: a reservation with no release on failure.** `run_reserved` handles `OSError` only (`__init__.py:2330-2338`).
- **Remedy.**
  1. In `runner.dispatch`, wrap everything from `mcp_server` to the first `Session(...).run()` in `try/except BaseException`. Call `given_back(store, work_id, ctx.nouns.get('reservation'))`, write `traceback.format_exc()` to stderr (the runner's log), and re-raise.
  2. With the traceback in hand, fix the thread misuse. The suspect is an object created on the loop thread and used inside `asyncio.to_thread` (`over_limit`/`reserve` at `runner.py:866-893`).
- **Verify.** Test: monkeypatch `runner.ticket` to raise `RuntimeError` once on the reserved run. Assert the ticket is in To do right after the runner exits and the log contains `Traceback`.

### F7 (minor) Opening a page loads CUDA, cuDNN and cuBLAS into the web server for good
- **What happens.** The voice probe `engine.machine()` imports `ctranslate2` and checks that the CUDA libraries load (`voice/engine.py:75-100`) inside the server, on page load, even when voice is never used.
- **Evidence (observed).** Server RSS went from 59,316 KB before the page to 336,900 KB after a headless page load, with `/proc/<pid>/maps` showing `libcudnn_*`, `libcublasLt.so.12` and `libctranslate2`. The page made 482 requests on load and 0 after 10 s, so it is reactive.
- **Governing record.** QUAL (resource use). No specific record found.
- **Root pattern: a heavyweight probe inside a long-lived server.**
- **Remedy.**
  1. Run `machine()` in a short child process (`python -m metaform.modules.voice.probe`) the first time the voice pane asks for it, and cache its JSON in `home/run/voice-probe.json`, keyed by the installed versions.
  2. The server reads only that file.
- **Verify.** Headless page load (`critic-load-r1/../page.py`), then server `VmRSS` under 100 MB, and no `libcudnn` in `/proc/<pid>/maps`.

### F8 (minor, inferred from code) A runner whose session stopped can sleep up to an hour waiting for its retry
- **What happens.** `moved_on` sleeps `min(due - now, RETRY_WAIT_LIMIT)` with `RETRY_WAIT_LIMIT = 3600.0` (`runner.py:324`, `947-951`). Each waiting runner keeps about 79 MB and 7 threads. With many failed sessions that is many idle processes. Combined with F1, all of them then wake at once.
- **Governing record.** BASE-052 amendment (the runner comes back for its retry, so no other timer runs).
- **Remedy.**
  1. After F1, the waiting runner calls `autostart` only for its own ticket's retry, not a full pass.
  2. Cap the wait at the actual next backoff, at most `RETRY_SECONDS * 2 ** dispatch_retries` (120 s at the defaults), not 3600.
- **Verify.** Test: a session ended with `how = DEAD` and `dispatch_retries = 2`. The runner process exits within 125 s.

## 3. What should be true instead

1. **Admission.** One function, `admit`, decides every launch that is not the person's own single summon. That covers start, Start all, autostart, retries, the next ticket of a glyph, merge assist, sentinels and intake. It runs inside the reserving write transaction and under a home-wide lock. It counts live agents (alive runners plus fresh reservations), never tickets merely waiting for a resume, across every project of the home. When it says 0, the caller queues and records why, and the next event (a session ending) frees a slot.
2. **Recovery.** After a crash, `settle` marks the dead sessions. `retry` resumes them oldest first, only as slots free, and a deferred one costs no retry count.
3. **Event handling.** A change that names tickets touches only those tickets. An autostart pass with no capacity does no per-ticket work. No pass takes the project's write lock unless it writes.
4. **Off switch.** `dispatch halt` (and its page control, if Rich wants one) stops every agent and turns Autostart off in one action. `web stop` tells the person how many agents still run and how to halt them.
5. **No self-feeding work.** What a done-handler writes (release log, follow-ups) is held or is a knowledge item, never an autostart candidate.

## 4. Tickets

Map addresses are proposed and **not checked** with `metaform map where`: this run was barred from the real home, which holds the project's map. Check each before filing.

1. **code.module.dispatch.supervisor** (`retry`). Condition: broken. Task: F1 steps 1-5. Verify: the F1 test, where 5 dead sessions with `dispatch_agents 1` give 1 resumed.
2. **code.module.dispatch.admission** (`slots_used`/`free_slots`). Condition: missing. Task: F2 steps 1-4, after Rich decides between a new setting and making the existing one global. Verify: the two-project test, at most 3 alive.
3. **code.module.dispatch.autostart** (`start_work` / `progress.refresh`). Condition: trouble. Task: F3 steps 1-5. Verify: the burst test, 0 refresh writes and 1 or fewer passes; server CPU for the 300-write burst under 150 ticks.
4. **code.module.dispatch.stop**. Condition: missing. Task: F4 steps 1-2 (CLI), and step 3 if Rich approves. Verify: the F4 halt test.
5. **code.module.dispatch.merge** (`merge_due`). Condition: broken. Task: F5 steps 1-3. Verify: no follow-up is ever reserved by autostart.
6. **code.module.dispatch.runner** (startup). Condition: broken. Task: F6 steps 1-2. Verify: an injected startup exception returns the ticket at once, with a traceback in the log.

## 5. Other defects seen

- A bare `metaform web` (default verb `start`) from an isolated home started a server on the default port 7433 and placed a `hold` call named `metaform-web-7433`. The hold name is not scoped by home (`web/__init__.py:230-231`), and start runs `hold purge <name>` (`:611`), so two homes share one hold name. I triggered this by accident at 01:14 and stopped it within about a minute. No live server was listening on 7433 at the time, and `hold list` shows no leftover.
- `memory watch` outlives `web stop` (pid 44477 alive 675 s after start, 54 MB). I ended it myself.
- The ended-session rows from a failed agent start ("it did not start") keep their tickets taken and in a slot until the person acts. Observed with 3 tickets after a bad agent command; it did not cascade.
- Shared scratchpad: parallel critics wrote the same file names (`homepath`, `proj/`). My `../homepath` was overwritten, and I ran `dispatch autostart --json` five times against another critic's home `home-YOYx` (project `uxp`). Each run started nothing (policy manual). I moved to `critic-load-r1/` for the rest.
