# Resolution of review findings: `code.manager.chat.group` (Roundtable)

Scope: `element.md` (description) and the copied code in `source/crates/roundtable/src/`.
Where the finding cites a line in a file that is not in `source/` (`turn.rs`, `jev.rs`, `config.rs`,
`prompts.rs`), I mark the citation **unverifiable here** and decide only on what the copies show.
Line numbers below are from the copies in `source/`.

Verdict key: **Agree** = finding is right; **Partly** = right in substance, wrong in detail;
**Disagree** = finding is wrong.

---

## GF1 (Blocker) - WORK convention vs tool-activity work detection

**Verdict: Agree (the finding is right).**

Evidence in the copies: `engine.rs:6-8` states "An agent is working when ACP reports tool
activity during its turn; it is not asked to announce work (O: 'Saying work, thats not a thing')".
`engine.rs:666-676` (`on_tool`) is the only place work is detected: a `ToolActivity` for a floor
prompt flips `Activity::Working` and records `Outcome::SkippedWorking`. `rules.rs:41-59` defines
only `Pass`, `Contribution`, `Empty`, and `classify` matches `PASS` case-insensitively after
trimming trailing dots (`rules.rs:54`).

So the description's decision *"A reply whose first line is WORK declares independent work"* is
not implemented. It also directly contradicts the code's cited owner statement. And the code is
stricter than the description on PASS, which is a third divergence the finding correctly notes.

**What should change:** in `element.md`, decisions -> "signalling contribute / pass / work":
replace the `WORK` first-line rule with the implemented rule - *the agent does not announce work;
it is working while ACP reports tool activity in its turn (`on_tool`), at which point the floor is
released and its opportunity is recorded as `SkippedWorking`; its final message when the turn ends
is its contribution.* Record the exact pass grammar ("trimmed reply equals `pass` ignoring ASCII
case and trailing `.`") because that is what the code does and it matters for agents.
No code change: the code matches the newer owner statement, and the description is the stale side.

---

## GF2 (Blocker) - configurable deliberation window and +512 credits

**Verdict: Agree (the finding is right).**

`engine.rs:12` is explicit: "No timers anywhere (O)." There is no per-turn deadline anywhere in
the copy; a table advances only on bus/internal events or commands (`engine.rs:442-456`). There is
also no credit mechanism: the only grant of extra length is `limit_for` (`engine.rs:396-399`),
which gives `cfg.recovery_allowance` (default 1,024, `rules.rs:9-10`) to a seat whose next
discussion prompt follows a *skip*, and no points are added per skip. `session_points` and
`rating_points` (`rules.rs:150-162`) are the rating round, not skip credit.

**What should change:** delete the "deliberation window" decision body, or restate it as a
*rejected/superseded* decision recording the timers ban, because as written the description claims
a live mechanism. Rewrite the owner_statements consequence line 113 ("a silent participant is
treated as occupied after the deliberation window") so it no longer promises a timer. Also fix the
"+512 per skipped opportunity" phrase wherever it survives (see GF7). No code change.

---

## GF3 (Blocker) - "nothing waits on an optional service" / "the only pause is a chair hold"

**Verdict: Agree (the finding is right).**

Three blocking waits are visible in the copy, and each is labelled as a gate:

1. JEV verdict: `engine.rs:510-513` - `step` returns while `floor` or `judging_floor` is set;
   `judging_floor` is only cleared by `Internal::Judged`, and there is no timer (line 12).
2. Two-free-agents wait: `engine.rs:540-552` sets `waiting_for_free = true` and returns; nothing
   bounds it; if every seat is working (`free.len() == 0`) the message is a single table-wide
   wait with no per-seat notice at all (`engine.rs:542` only acts on a *lone* free seat).
3. Topic poll: `engine.rs:503-507` will not finish while any asked or pending seat has not
   answered or failed, so poll progress waits on every agent.

The consequences in the description therefore overstate the code in the opposite direction from
GF1: here the description is *too strong a safety claim*, and it hides a real stall risk.

**What should change:** rewrite the consequence in **both** owner_statements entries that make this
claim (line 113 and line 118) to state the actual invariant: *the loop waits on JEV's verdict for a
contribution (RT-G10), on every agent for a topic poll (RT-G21), and on two free seats (RT-G03);
none of these has a timeout, so a hung provider can stall a turn, but no ACP turn is ever
cancelled.* If the owner's non-halting statement is to be honoured, the code should get a
deliberation-window equivalent for the floor only (a *wait that does not cancel*), which is a
code change and an owner decision - not a wording change. Flag it in the elephant `gaps`.

---

## GF4 (Blocker) - automatic end and ranking exist

**Verdict: Agree (finding right in code; must reconcile with owner statements rather than revert).**

`engine.rs:634-641`: when `cfg.rounds == Some(self.round_no)` the engine calls `start_rating`.
`rules.rs:11-12` fixes `DEFAULT_ROUNDS = 10`, and `element.md` rule[0] says the same, so the
default table does end automatically. `engine.rs:643-651` ends a no-limit table after two quiet
rounds. The ranking is built and sent during the rating round (`ranking`, `results_sent`,
`settle_results`/`start_rating`; those functions live in `turn.rs`, which is **not in `source/`** -
unverifiable here, but `engine.rs:44` and 900-907 confirm the rating round runs and ends the
table). The decisions entry "A Roundtable has no automatic end... no convergence vote or summary
phase" and owner_statements line 136-142 supersede it: the owner since said "make it by default 10
rounds" and "unlimited must have some kind of end".

**What should change:** do not revert the code. Rewrite the **ending** decision to the current
state: *default 10 rounds (`DEFAULT_ROUNDS`), then a rating round that collects peer ratings and
publishes a session ranking, then shutdown; unlimited tables end when two rounds bring no accepted
message (RT-G06).* Keep the old text as a `superseded` record (GF7 requires the superseded layer).

---

## GF5 (Major) - no-limit end only without topics; quiet rounds include skips

**Verdict: Agree (the finding is right), with one correction to its premise.**

`engine.rs:647` guards the end with `(!self.topics_active() || !self.topic_had_input())`, so with
topics **active and a topic that produced input** two quiet rounds do *not* end the table - they
set `topic_due` (`engine.rs:654-656`, gate RT-G08) and the topic poll picks a new topic. Also
`RoundTracker` (`rules.rs:102-111`) counts a round as "nonproductive" when `accepted == 0`
regardless of whether seats passed or were skipped while working, so the "two quiet rounds" test
originally described as "every seat passed" (decision on rounds) no longer means passes only.
Correction: the finding's "rounds of all passes or busy skips also count" is true, but the code
actually broadens it further - *any* round with zero accepted messages counts, including all-failed
rounds.

**What should change:** rewrite rule[0] as: *"A table with no round limit ends when two consecutive
rounds brought no accepted message, **and** the current topic has produced no input; otherwise the
two quiet rounds start a topic poll. 'The end' is the rating round starting."* That is exactly the
`topics_active()`/`topic_had_input()` split in `engine.rs:647`.

---

## GF6 (Major) - wants are stale or incomplete

**Verdict: Agree on every sub-point, but they split cleanly into "description is wrong" and
"description omits behaviour".**

Right and verifiable in the copies:
- Gate want says "three 70% conditions"; `rules.rs:13-16` has `GATE_PASS = 0.70` and
  `SCORE_PASS = 3.0` (a 0-5 score, not a 70% condition), so "three 70% conditions" is wrong; the
  actual checks (five, per `turn.rs:205-210`, unverifiable here) are not described. Restate as
  *"accepts or vetoes against a set of yes/no checks at 0.70 and 0-5 scores at 3.0, with veto
  reasons"* and point at the registry for the exact list.
- Quota want ("1,024 once after a busy skip... by default"): `limit_for` (`engine.rs:396-399`)
  returns `None` when `cfg.base_allowance` is `None`, so with no base limit there is no recovery
  limit either. Restate: *"each turn has the table's reply limit (`base_allowance`, none by
  default); a skipped-busy seat's next discussion turn gets `recovery_allowance` once instead
  (1,024), but only when a base limit is set."*
- Two-step End (`engine.rs:900-907`): first End starts the rating round, End again shuts down.
- Turns start only once every seat has left `Starting` (`engine.rs:499-500`).
- Table ends when no `Starting`/`Ready` seat remains (`engine.rs:789-792`, also 838-841).
- Rating needs at least two named seats - `turn.rs:422-425`, **unverifiable here**, cite as such.
- Review notice sent once per waiting episode (`alone_noticed`, `engine.rs:98`, 545-548,
  reset at `engine.rs:830`).

**What should change:** the wants block and rules must describe these; none requires a code change.

---

## GF7 (Major) - active decisions contradict current rules; no superseded layer

**Verdict: Agree (the finding is right).** This is the most damaging description defect: a reader
cannot tell which text governs. The code implements the *later* owner statements (2026-11-07:
10 rounds default; unlimited must end), not the 2026-11-05 ending decision.

**What should change:** (a) add a `superseded` marker (a `status` field) to the "ending", "rounds"
and "deliberation window" decision entries and to owner_statements lines 110-114/136-142 where
older consequences are out of date; (b) re-write those decisions to the implemented rules; (c) add
one sentence at the top of `decisions`: *"newest dated entry wins; superseded ones are kept for
history only."* The description is the artifact to change here; no code change.

---

## GF8 (Major) - two-free wait vs "do everything it can not to get stuck"

**Verdict: Agree that there is an unresolved conflict; I would not "fix" it in favour of removing
the gate, because the owner's 2026-11-06 statement ("we need at least two agents to have a debate")
is the authority being implemented by RT-G03.**

The code waits with no bound (`engine.rs:540-552`) and, if all seats are busy, gives no notice
(`free.len() == 0` is silent). But it is not a deadlock: every busy turn ends with
`PromptCompleted`, `PromptFailed`, or `HarnessExited`, and each of those clears
`waiting_for_free` (`engine.rs:690`, 737, 768), so a provider that eventually fails or finishes
frees the table. The real stall is a harness that hangs with no provider timeout; that is outside
engine.rs (the ACP host), which is why it is not fixed here.

**What should change:** restate rule[1] honestly - *"the table offers no turn while fewer than two
seats are free; a lone free seat is told once to review the workspace; readiness is restored by
any turn ending, failing, or a harness exit; there is no timer, so a harness that never reports
completion stalls the debate by design (two agents are required to have a debate)."* Add a
`gaps` entry: a floor-level non-cancelling deadline is the only safe resolution and needs an owner
decision (squarely the GF2/RT-G03 question). Do not silently choose "no wait" over "two agents".

---

## GF9 (Major) - "two quiet rounds" both ends and starts a poll; precedence unstated

**Verdict: Agree (finding right).** The precedence *is* in the code and simply not in the
description: `engine.rs:647` tests end first and `return`s on the no-limit end; only if it does not
fire does `engine.rs:653-656` set `topic_due`. With topics active and input present in the current
topic, the poll wins over ending. With topics off, two quiet rounds end the table.

**What should change:** put that ordering in rule[0] (same rewrite as GF5): *"the end is tested
first; only when it does not fire do two quiet rounds start a poll."* Cross-reference
`code.selector.topic`'s trigger, since that want says "once a topic is exhausted" without saying
the exhaustion signal is `RoundTracker::close_round` returning true (RT-G08).

---

## GF10 (Major) - undefined terms

**Verdict: Agree (finding right).** The document uses JEV, ACP stopReason/state_update/
session cancel, chair, seat, harness, head of the table, rating round, AgentSight, Python/
archaeology, PV correction turn, run 1 T755, and M2/M3/M4 with no glossary. Nothing in the code
copies contradicts these uses - they are simply undocumented.

**What should change:** add a short glossary section at the top of `element.md` (JEV = the
quality gate's evaluator; ACP = Agent Client Protocol, v1 stopReason and v2 state_update idle/
session cancel; seat = one participant slot/agent; harness = the ACP host process running a model;
chair = the user; rating round = the peer-rating phase before shutdown; AgentSight = the activity
monitor). Replace the archaeology-only references (Python runner, PV correction turn, run 1 T755)
with a pointer to the archaeology note so they are traceable, and either expand M2/M3/M4 or drop
the codes.

---

## GF11 (Major) - Advance "through the normal poll" when topics are off

**Verdict: Agree (finding right).** `Command::Advance` (`engine.rs:872-881`) refuses when
`!self.topics_active()` with an error notice ("topics need JEV (judging on and a key)"), and does
not start a poll in that case; the poll is only reached from `step` when `topics_active()`
(`engine.rs:514-522`). So with topics off, Advance does nothing but publish an error.

**What should change:** in the `code.server.tool` want for Advance, state: *"Ends the current topic
and starts the next one from a caller-supplied topic or from a poll. Topics are a table setting,
off by default and needing judging on and a JEV key; when they are off, Advance is refused with an
error notice and the table continues."* That matches the code and tells the tool author the
disabled case.

---

## GF12 (Nit) - unexplained form fields, stale investigation, unsourced 500-line limit

**Verdict: Agree, except the 500-line limit, which I will not endorse without the source.**
The `elephant.gaps` claim "engine.rs is about 990 lines, over the 500-line limit" is measurable
(the copy is 997 lines) but the *limit* is asserted with no citation anywhere in the material; the
finding is right that it needs one. The OPEN idle-loop investigation still describes the indefinite
cycling that the 10-round default and RT-G06 now prevent in the common case, so it reads as a live
risk when it is now an unlimited-mode-only risk. `role: DE`, `name_length: 3` and the `Intent`
values are map-format fields that are never explained in the description.

**What should change:** (1) add a one-line explanation of `role`/`name_length`/`Intent`(or a
pointer to the map's schema); (2) rewrite the investigation note: *"still open only with no round
limit; default 10 rounds bounds it"*; (3) cite the line-limit policy or drop it from `gaps` - if
it is only a house rule, move it out of `gaps` into `rules` so it is not read as a functional gap.

---

## Summary of what to change

| # | Verdict | Change lives in |
|---|---------|-----------------|
| GF1 | Agree | description: signalling decision -> tool-activity rule; record PASS grammar |
| GF2 | Agree | description: delete/rewrite deliberation window and +512 skip credit |
| GF3 | Agree | description: consequence lines 113, 118; or code: floor-only non-cancelling deadline (owner call) |
| GF4 | Agree | description: ending decision -> 10 rounds + rating round + ranking (supersede, do not revert code) |
| GF5 | Agree | description: rule[0] - no-limit end also requires no topic input |
| GF6 | Agree | description: gate/quota wants, two-step End, seating start, no-seats end, rating >=2 seats, review-once |
| GF7 | Agree | description: add superseded status + "newest wins" rule |
| GF8 | Agree | description: honest statement of bounded-is-not-implemented; gaps: owner decision |
| GF9 | Agree | description: state end-before-poll precedence |
| GF10 | Agree | description: add glossary, replace archaeology shorthand with pointer |
| GF11 | Agree | description: Advance is refused when topics are off |
| GF12 | Agree (partial) | description: explain map fields, refresh investigation; cite or drop the 500-line limit |

No finding requires a code change on its own; all twelve are description defects, except that GF3
and GF8 identify a genuine stall risk whose only real fix (a non-cancelling floor deadline) would
be a code change and needs the owner's decision.
