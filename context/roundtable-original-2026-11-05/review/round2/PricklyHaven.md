# PricklyHaven findings (engine, turn, rules, bus, prompts)
Line numbers: engine.rs from `cat -n`; turn.rs/rules.rs approximate by function.

## P1 (HIGH, hang) Rating round never completes if a busy seat fails or crashes
engine.rs:625-638 (on_failed) and 655-667 (on_exited): only `Activity::Rating` calls `rating_done`.
A seat that was Working/Reviewing/Floor-owner/Proposing when End was pressed is in `rating.left`
but not yet asked (the ask happens only in on_completed, engine.rs:609). If its prompt then FAILS
(on_failed) it goes Idle and nothing asks it to rate; if it CRASHES (on_exited, Working arm is `_`)
it is Gone and never removed from `left`. `left` never empties -> `end()` never runs, step() returns
early on `rating.is_some()` (engine.rs:430): table hangs until chair presses End a second time.
Fix: in on_failed/on_exited, after handling, run the same "owed a rating" check as on_completed
(ask if Idle+Ready, else `rating_done` if Gone). Test: End while one seat Working, then crash it.

## P2 (HIGH, wrong topic) Late proposal reply corrupts a later or in-flight poll
turn.rs on_proposal / engine.rs on_tool:576-581. A seat that starts tool work while Proposing is
dropped from `waiting` but keeps `Activity::Proposing`. Its eventual reply goes to on_proposal:
(a) while `polling.scoring` is Some, the proposal is pushed AFTER finish_polling built the pair
list; complete_polling then scores it with `unwrap_or(0.0)` for every pair and re-derives
`proposals` from a different (unsorted, longer) list than the one JEV compared, so pair keys
`p{a}_{b}` index the wrong proposals -> wrong winner. (b) If a later poll is open, the stale
proposal from poll 1 is counted into poll 2. Fix: tag Proposing with the poll id and drop replies
whose poll is not the live one and not still `waiting`; never push once `scoring` is set.

## P3 (MED, lost accounting) Accepted-after-work not counted when judging is off / no key
turn.rs submit: unjudged branches call `accept` and return `Outcome::Accepted`, but for
`after_work` resolve_reply discards the outcome (returns None) and `rounds.record_accept()` is only
reached from on_judged. A reply-after-work accepted unjudged never marks the round productive.
Harmless today because topics need JEV, but toggling judging on mid-table (SetJudging) gives wrong
nonproductive streaks. Fix: call `rounds.record_accept()` in the unjudged after_work path.

## P4 (MED, invention / spec) Review reply is published as a discussion contribution
engine.rs on_completed:601 routes Reviewing replies through resolve_reply(after_work=true) ->
submit -> judged -> logged as `R{t}-{n}` message with id, allowance spend and veto. The owner said
only "the idle agent is told to review the materials" (TRACEABILITY M); nothing says the review
reply is a message. The REVIEW prompt (prompts.rs REVIEW) says "Reply when you are done, with your
message or PASS" and omits the allowance line, so the agent is truncated at an unstated limit.
Either (a) treat the reply as its next-turn reply, or (b) include allowance. Needs owner ruling;
recommend (b) minimal.

## P5 (MED, spec drift) PASS parsing is looser than the spec
rules.rs classify: `trim_end_matches('.')` and `eq_ignore_ascii_case` accept "pass", "Pass.", "PASS..."
R §4.3 / prompt say "exactly PASS". L#1 keeps "reading PASS from the reply" only. Lowercase
"pass" as a one-word contribution is rare, but the "." tolerance is an invention with no observed
failure cited. Fix: exact (after trim) match, or cite the failure.

## P6 (MED, silent) Empty/PASS-less proposal and empty rating are dropped without a record
turn.rs on_proposal: Reply::Empty is ignored silently (only Contribution counted), unlike the
floor path (L#15: loud error). Owner: fail loudly. Fix: notice + TurnFailed for Empty proposal.
Also proposals truncated at 512 with no notice to the author (silent loss).

## P7 (LOW) "(joining)" leaks into first prompt; Failed seats stay "(joining)"
turn.rs turn_prompt names list uses seat.name or "(joining)"; step() waits for no Starting seats,
but a seat that FAILED to start has name None forever, so the turn-order list tells agents a
non-existent participant is "(joining)". Fix: omit Failed/Gone seats or label them.

## P8 (LOW) process prompt advertises `advance`/`feedback` tools to seats that cannot have them
prompts.rs process(); engine.rs start_seat warns when harness lacks HTTP MCP (OpenRouter adapter
accepts no MCP at all, TRACEABILITY N). Those agents are told to use tools they do not have, and
the "head of the table" election text assumes they can advance. Fix: per-seat tool line.

## P9 (LOW, unbounded) Allowance credits accumulate without limit
rules.rs credit(): each skipped-while-working round adds +base while something new arrived; a long
worker's allowance grows unbounded and its reply is then broadcast to all seats (R §1.2 cost
amplification). Matches owner's "extends when credited" text; flag for owner whether a cap exists.
(Owner decision, not a bug.)

## P10 (LOW) End reason text wrong after rating
turn.rs rating_done calls end("ended by the chair") even when rating finished because the last
rater crashed/failed. Cosmetic, but record is evidence.

## Untested (to verify)
- End while a seat is Working then fails/crashes (P1).
- Proposal arriving during scoring (P2).
- JEV panic/never-reply: judging_floor stays Some forever (no timer allowed; but the spawned task
  has no catch so a panic in jev.ask silently stalls). Suggest `JoinHandle` watch -> Internal::Judged Err.
- select_topic ties and 1-proposal path.

## P11 (MED, hang on End) shutdown waits on session/close with no way out while a turn is running
acp-host/src/harness.rs:~600-640 (`shutdown`). Table end calls `harness.shutdown()`; if the agent
supports close, the process stop is sent only after EVERY `session/close` is answered. An agent
mid-turn (long tool work, or hung) may not answer until the turn ends, so the processes outlive
`TableEnded` - the exact failure L#19 cites ("agent processes outlived End"). The owner struck
timers, so the fix is event-based, not a timeout: on shutdown send `cancel` for sessions with a
turn in progress (harness already has `cancel`) before `session/close`, and stop on connection end.
Owner decision touching this (SDK sequence 1s/2s) is pending; flag, do not time out.

## P12 (HIGH, security) ScopePolicy allows a dangling symlink that points outside the scope
acp-host/src/permission.rs `inside` (loop at ~line 66-80). `Path::canonicalize` (realpath) fails
with ENOENT on a symlink whose target does not exist. The loop then treats the link itself as a
"not yet existing" name, resolves only its parent (inside the root) and appends the link's name,
so `root/dangling -> /home/rich/.ssh/authorized_keys_new` (or any missing outside path) passes
`starts_with(root)`. An allowed edit/write to `dangling` creates the file OUTSIDE the scope.
Same class as SC8 (adapter write_file) but in the Rust host policy that guards every Claude/Codex
seat. The existing symlink test only covers a link to an existing directory.
Fix: before the ancestor walk, `symlink_metadata` each component; if it is a symlink, read_link
and resolve its target (recursively, bounded) instead of treating it as new. Add a test with a
dangling link. (Reasoned from realpath semantics; not executed against ScopePolicy.)
Also: `decide` allows every ask with no `locations` (execute/fetch): the doc comment admits this,
but then `ScopePolicy` is not a confinement for shell tools; the startup warning in
engine.rs:841 covers only the missing-mode case.

## P13 (LOW) Agent-monitor attaches by the harness leader pid only; coverage limits
engine.rs on_started -> Monitor::attach(pid). Observations are keyed by that pid, so a harness that
forks workers is covered only if AgentSight follows descendants (not verified by me). Monitor
events serialise `harness` as {pid,id} (agent-monitor/src/lib.rs:70) - see SC11 for the routing
break. No race or lost-event defect found in attach; non-root fails closed, per owner.
Not audited: AgentSight probe internals, capture.rs beyond a skim.
