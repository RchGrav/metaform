# BalmyBoron — Round 3 independent verification

Scope claimed: F01, F19, F03, F05 (plus cross-check of others via VERDICTS).
Authority used: TRACEABILITY L/M/N, then README, then ACP design.

## F01 — Configured chair credential reaches participants — FIXED

Fix lives in `crates/roundtable/src/config.rs:28` (`SECRET_ENV` now lists
`ROUNDTABLE_TOKEN` alongside `OPENROUTER_API_KEY`, `TYPESAFE_API_KEY`) and
`SeatConfig::launch_spec` (`config.rs:34-56`) which, for **every** seat, removes
each secret from `launch.env` and pushes it onto `launch.env_remove`, so even a
seat config that tries to inject the token explicitly loses it.
`srv` launcher only creates the token in memory (`app.rs:113`), matching the
finding's note that the default path was already safe.

Test proof: `crates/roundtable/tests/config.rs:15`
`secrets_and_the_chair_token_never_reach_a_seat` asserts for all three names
that they are in `env_remove` and absent from `env`, while an unrelated var
survives. This is the fake-harness environment test the fix required (it tests
the launch specification, not a live spawned child — see caveat below).

Caveat (not a new defect, an observation): the test inspects the spec, not a
spawned child's actual environment. `acp-host` `process.rs:65-71` applies
`env_remove` before `envs`, so the composition is sound, but no end-to-end
"read /proc/self/environ from the fake agent" assertion exists. Given F19's
test *does* spawn (`process.rs:199`), the composition risk is covered there.

## F19 — Opt-in provider key removed again at launch — FIXED

Two coordinated changes:
- `acp-host/src/process.rs:63-71`: removal loop runs **before** `.envs(&spec.env)`
  with an explicit comment, so an explicit variable wins over a removal of the
  same name.
- `config.rs:44-49`: an opted-in seat inserts `OPENROUTER_API_KEY` into
  `launch.env`; `ROUNDTABLE_TOKEN`/`TYPESAFE_API_KEY` remain removed.

Test proof:
- `acp-host/src/process.rs:199` `explicit_env_wins_over_removal` spawns `sh`,
  removes `RT_PROCESS_TEST_KEY`, sets it explicitly, and reads `shared` from the
  child's stdout; a second case proves a pure removal yields `unset`. This is a
  real spawned-child test, closing the R2 concern that the proof was synthetic.
- `config.rs:26` `an_opted_in_seat_gets_only_the_openrouter_key` checks the
  spec-side composition for share-on and share-off, plus the warn-when-no-key
  branch.

Residual gap: no test drives the *full* `start_seat` → `Harness::launch` path
with share on and verifies the adapter sees the key. The two halves are each
tested; the seam (`start_seat` calling `launch_spec` then `Harness::launch`) is
untested. I judge this FIXED for the defect as stated (env precedence), with a
test-coverage note, not a new defect.

## F03 — Busy seat strands end-rating round — PARTIAL (needs owner of this item to confirm)

I traced the rating-obligation lifecycle in `engine.rs` and `turn.rs` but did
not complete a runtime reproduction this pass; see VERDICTS for the assigned
checker. Deferring my verdict here to whoever owns F03 unless unclaimed.

## F05 — Listed OpenRouter adapter fails creation-time resolution — PARTIAL

`app.rs:185-189` and `tables.rs:68-70` — the listing/creation resolver sharing
and the command+argv construction (PH cross-read about paths with spaces) need
a dedicated trace; I did not finish it. Deferring.

## F02 — Dangling symlinks bypass filesystem guards — FIXED (my item)

Rust: `crates/acp-host/src/permission.rs:83-...` `resolve()` now detects a
not-found component whose `symlink_metadata` is a symlink and follows it via
`read_link` (loop-bounded by `MAX_SYMLINKS`), pushing the remaining components
onto the target. So a dangling in-root link whose target is outside resolves to
the outside path and is rejected.

Test: `permission.rs:188` `scope_follows_dangling_symlinks` builds
`escape`→outside/missing.txt, `escape-dir`→outside/no-such-dir, `hop`→link
chain, `relative` (`../outside/…`), `loop-a/b`, plus allowed cases
`inside`→root/not-yet.txt, `present-link`, `brand-new.txt`,
`new-dir/new.txt`. Asserts rejected for the five escapes and allowed for the
five benign. This covers both dangling and existing-target links, as required.

TS: `adapters/openrouter-acp/src/tools.ts:68-100` `resolveReal` does the same
(lstat/readlink on a missing component, throws `ELOOP` via realpath).
Test: `test/adapter.test.ts:406` "refuses dangling symlinks …" plus `:374`
existing-target links.

## Updated verdicts for my items
- F01 FIXED — config.rs SECRET_ENV + test config.rs:15
- F02 FIXED — permission.rs resolve + test :188; tools.ts resolveReal + test :406
- F03/F05 — deferred to NobleChaos (owns F03-F05).
- F19 — FIXED (see above); NobleChaos owns the report line.

## Cross-checks (independent second read)

### F09 — monitor routing — FIXED (concurs with BrinySteel)
`record.rs:31` `harness_id` accepts string or `{id}`; `record.rs:23` `table_of`
uses it. `index.html:179-198` `harnessId` returns a string or null before
`.includes`, so no object call. `engine.rs:423-429` raises a loud `error`
notice for every `MonitorUnavailable`, covering attach and later failures.
Test: `record.rs` `monitor_events_route_to_their_table`. Gap: JS routing has
only the code read, no JS test — agree with BrinySteel this is coverage, not a
defect.

### F10 — timers — FIXED (concurs with BrinySteel)
`grep setTimeout|setInterval index.html` → no match. `app.rs:346-349` Sse has
no keepalive, with the owner's rule cited. History refresh is driven by the
`roundtable.ended` event (`index.html:247`). No invented delay remains.

### F11 — feedback persistence — FIXED (concurs with BrinySteel)
`app.rs:77-84` `loud` publishes an `error` notice to the table and also
eprintl'ns; both `save_feedback` and the accolades append are checked
(`app.rs:88-96`). `mcp.rs:90-94` truthfully reports send failure. Points stay
end-rating only, matching owner categories.

## Cross-checks on prompt items

### F12 — tools advertised to seats that lack them — FIXED (coverage note)
`prompts.rs:22-36` `process(..., tools: bool)` emits the `Tools:` line only
when true; `turn.rs:39` passes `seat.tools`, which `engine.rs:733` sets from
`start_seat`'s `offered = tools.is_some() && harness.accepts_http_mcp()`
(`engine.rs:865`); a non-MCP harness also gets a warning (`:872`).
Test: `tests/engine.rs:406` asserts no `Tools:` in the first prompt.
**Coverage gap (not a defect):** every test calls `spawn(..., tools: None)`
(`tests/engine.rs:33`), so the positive and mixed cases (one seat with tools,
one without) are not exercised by an automated test. Recommend a test that
passes `Some(ToolsEndpoint)` and gives one seat an MCP-accepting fake vs one
non-accepting, asserting the Tools line appears for exactly the first.

### F17 — struck "private" proposal label — FIXED
`prompts.rs:70-72` `topic_proposal()` no longer says "privately"; it keeps the
`PROPOSAL_LIMIT` bound. `resources/participant_prompt.md` has no "private".
Concur with the literal-versus-L#6 check. No dedicated test, but the string is
a constant; a unit assertion on the literal would be cheap.

### F18 — failed seats described as joining — FIXED
`turn.rs:31-38` filters `Ready`→name, `Starting`→"(joining)",
`Failed|Gone`→None. Test: `tests/engine.rs:389`
`a_failed_seat_is_not_listed_as_joining` starts one broken seat beside two
passing ones and asserts the first prompt contains no "(joining)" and that a
`roundtable.seat.failed` event fired for Broken.

### F04 — cancellation of exited leader — PARTIAL (concurs with NobleChaos)
Checked the adapter suite: the only command-cancel test is
`test/adapter.test.ts:558` "kills a running command…", which cancels while the
leader (`exec sleep 1000`) is still alive. The F04 scenario (`sleep 30.123456789
& exit 0`, leader gone, descendant holding pipes) is NOT exercised. Code at
`tools.ts:277-286` is correct (unconditional `-pid`, ESRCH swallowed), but
FINDINGS required an exited-leader cancellation and disconnect test; absent →
PARTIAL.

## F13–F16 (taken over from AlloyedReaper's pending lane)

### F13 — review requests omit the enforced allowance — FIXED
`engine.rs:521-526` `ask_to_review` formats `REVIEW` then the owner's
`allowance(current)` line, and the turn code never substitutes it (unlike a
normal turn which uses `ask` in place of the allowance line, `turn.rs:57`).
Test: `tests/engine.rs:163` asserts the review prompt ends with
"Characters to Respond". Caveat: the test uses base 512, not a nondefault
bank as FINDINGS asked; the code path uses `self.seats[i].allowance.current`
so a nondefault bank is structurally correct but untested at a custom value.

### F14 — missing peer ratings / empty proposals — PARTIAL
Empty proposal: FIXED. `turn.rs:245-249` publishes `TurnFailed` and an error
notice. Empty discussion reply: `turn.rs:79-83`.
Missing peer ratings: **NOT FIXED.** `on_rating` (`turn.rs:357-382`) iterates only the cards present and never diffs the received target set against the required peers; a partial set is recorded and `rating_done(i)` still fires.
only the cards present in the JSON and then unconditionally calls
`rating_done(i)` (`:384`); it never compares the received target set against
`names()` minus self, so a reply rating only 1 of 2 peers is recorded silently
and the rater is marked done. FINDINGS required explicitly reporting missing
peer ratings. Test `tests/engine.rs:347` covers late proposals (F06), not
partial rating sets; no test submits `{}` or a partial set. Fix: after
building the rated-target set, diff against required peers and raise an error
notice naming the missing ones (no retry loop), per L/O "fail loudly".

### F15 — immediate after-work acceptance omits productivity — FIXED
`turn.rs:90-93` `resolve_reply`: on `after_work && Accepted` it calls
`rounds.record_accept()`, mirroring `on_judged`'s count for judged replies
(`turn.rs:143-150`). Test: `tests/engine.rs:156` asserts `after_work == true`
on the acceptance. Residual: no test drives the specific nonproductive-round +
immediate-acceptance + settings-toggle scenario FINDINGS described; code path
is present and single-counted (the `if !after_work { return None }` above
prevents double counting).

### F16 — chair allowance display ignores configured base — FIXED
`index.html:214` on `roundtable.opened` sets `t.base = d.base_allowance` and
resets existing seats' allowance; new seats seed from `t.base` (`:207`); an
accepted contribution resets to `t.base` (`:229`); form default is 512 (`:136`),
overridden by the events. Engine supplies it (`engine.rs:373`,
`events.rs:26`). No automated JS test; verified by code read against the
opened-event field F16 named.

### F04 — CORRECTED to FIXED
I was wrong: `stopAfterLeaderExit` (`adapter.test.ts:590-660`) is exactly the
exited-leader case — the shell `exit 0`s at `:601` while the background `cat`
holds the pipes, the harness waits for `ESRCH` on the group (`:622-626`, leader
reaped) before signalling, and the helper runs twice: `session/cancel` (`:662`)
and client disconnect via `abortAll` (`:667`). FINDINGS' required tests exist.
Verdict FIXED. My earlier PARTIAL was based only on the first, live-leader test.

## F06–F08 (current topic)

### F06 — stale proposals enter scoring or later polls — FIXED
`turn.rs:224-236` `on_proposal` rejects a reply when the poll is gone
(`polling.is_none()`), when the seat was not in `p.asked`, or when
`p.scoring.is_some()`, with a notice ("... and was not counted"). Proposals
live in `polling.proposals` and the exact immutable vector is passed to JEV at
finish_polling (`turn.rs:266-288`) and consumed by `complete_polling` from
`polling.take()` (`:304-310`). Test: `tests/engine.rs:347`
`a_late_proposal_does_not_enter_a_decided_poll` uses a 3s topic delay plus a
tool call to become busy, and asserts no `topic.proposed` for Cy and that the
late notice says "not counted".

### F07 — topics can change after judging is disabled — FIXED
`engine.rs:811-823` `settings_changed` drops any `polling` (both collecting and
scoring: `polling.take()`) and any queued `advance`, clearing `topic_due`, when
`topics_active()` (judging && key, `:323`) goes false. A JEV score that arrives
later hits `on_scored`'s guard `polling.scoring != Some(ticket)` → `polling` is
now `None`, so it returns without a topic change (`turn.rs:289-291`).
`step` also re-filters a pending advance with `topics_active()` (`engine.rs:454`).
Test: `tests/engine.rs:370` `turning_judging_off_mid_poll_stops_topic_selection`.

### F08 — corrupt identity history silently replaced — FIXED
`app.rs:415-434` `update_profile` initializes a fresh profile **only** on
`ErrorKind::NotFound`; any other read error or a JSON parse error returns
`InvalidData`, and a wrong-shape object is rejected (`:427-428`). The write goes
to a sibling `.tmp` and is `rename`d over the target (`:432-433`); callers run
on the single recorder task, so writers are serialized. Failures are surfaced
by `loud` (`app.rs:77-84`). Test: `app.rs:591`
`identity_profiles_are_never_silently_replaced` writes `{ truncated`, asserts
`save_rating` returns `InvalidData` **and** the file is unchanged, checks the
`.tmp` is gone, and confirms feedback adds no points and rejects `../escape`.

### F14 — CORRECTED to FIXED (re-checked late in the round)
The code changed after my PARTIAL read: `turn.rs:366-370` builds `unrated`
from `names()` minus self and `retain`s each listed target; `turn.rs:394-398`
takes the `error` notice "… did not rate …; those ratings are missing." with no
retry. Test `tests/engine.rs:422` `missing_peer_ratings_are_reported` sends `{}`
via `FAKE_RATING` and asserts the exact notice plus that only the other agent's
rating was recorded. FINDINGS also asked for a partial-peer-set test; `{}` and
a partial set take the same `retain` path, so this is a test gap, not a defect.
Verdict FIXED.

## Closing F12 and F13 empirically (probe crate, no source edits)

Built `review/round3/probe` (standalone crate, path-deps on `crates/*`), ran:

**F13 — custom base honoured.** `probe/src/main.rs` starts a 2-seat table with
`base_allowance: 1537`, makes Busy work (so Free is asked to review), and
asserts the review prompt's last line. Result:
`You have 1537 Characters to Respond` → `true` (exit 0). FINDINGS' required
"review request with a nondefault bank" is satisfied. **F13 FIXED.**

**F12 — per-seat tool line.** `probe/src/bin/f12.rs` calls
`prompts::process(..., tools=false/true)` directly: with false, no `Tools:` and
no `advance`/`feedback`; with true, both appear. Exit 0. Combined with the code
trace that `engine.rs:733` sets `seat.tools` from `start_seat`'s
`offered = tools.is_some() && harness.accepts_http_mcp()` (`engine.rs:865`),
and that `turn.rs:39` passes it, the gating is proven for both branches. The one
unproven step remains a *hosted* non-MCP harness; the fake always advertises
HTTP MCP and cannot be edited outside review/round3, so the end-to-end mixed
harness is documented as a harness-capability limit, not a code defect.
**F12 FIXED** (prompt branch proven; harness seam traced).

### Note on artifact evidence
`alloyed-ui-probe.log` genuinely supports F16/F17 (PASS lines). But
`alloyed-nondefault-test.log` runs `a_lone_free_agent_is_asked_to_review_once…`
(the default-512 test) and is not a nondefault-bank proof despite its name; the
nondefault evidence is `review/round3/probe/src/main.rs` (base 1537, exit 0).

## N01 (AlloyedReaper) — confirmed, genuine new defect
`turn.rs:370` `unrated.retain(|n| n != to_name)` strips the peer from the
required set, then `:371` `let Some(ratings) = card.as_object() else { continue }`
drops a non-object card with no record and no notice. So `{"Ada": null}`
removes Ada from `unrated` yet records nothing, and the rater is marked done —
a required peer is silently unrated, exactly the F14 class the fix set out to
report. Reproduced: `alloyed-null-rating-test.log`
(`null_peer_rating_is_silently_discarded`, passes).
Fix: move the `retain` after `card.as_object()` validation (or remove only on a
successful publish); leave non-object cards in `unrated`. This is a new defect
introduced by the F14 fix, not a gap in F14's original null-card-free path.

## F15 closed empirically (probe)
`probe/src/bin/f15b.rs`: worker starts a tool (opportunity counted as
SkippedWorking), then returns an accepted contribution after work with judging
off. Result: `after_work` accepted seen; `roundtable.round.topic_may_advance =
false`, i.e. the round closed productive. That is only possible if
`resolve_reply`'s `after_work && Accepted` branch called `record_accept`
(`turn.rs:91-93`); without it the round would be nonproductive. Exit 0. The
FINDINGS-required "immediate worker acceptance then settings toggle" is covered.
**F15 FIXED.**

## Final reconciliation (round close)
Verified in-crate tests landed during the round and PASS:
- F13: `a_lone_free_agent_is_asked_to_review_once_while_the_other_works`
  now uses base 700 and asserts `You have 700 Characters to Respond`
  (`engine.rs:167,187`); ran, passes.
- F12: `a_seat_with_tools_is_told_about_them` (`engine.rs:442`) spawns with
  `Some(ToolsEndpoint)` and asserts the Tools line; ran, passes.
N01 re-confirmed in current source: `turn.rs:367` `unrated.retain(...)` runs
before `turn.rs:368` `card.as_object() else { continue }`, so `{"Ada": null}`
still silently drops a required peer.
Therefore the correct closing tally is **18 FIXED, 1 PARTIAL (F14 via N01)**,
not 17/2. Suggested one-line fix: move the `retain` after a successful publish,
or leave non-object cards in `unrated`.

## F15 async path proven (closes AlloyedReaper's reservation)
`probe/src/bin/f15c.rs` runs a real axum fake JEV (judging on + key): Worker
works then contributes, JEV accepts (0.95), and the test asserts
`after_work && accepted` on the contribution and `round.topic_may_advance =
false`. Result: `true` / `false` / exit 0. So `on_judged`'s `count(self,true)`
(`turn.rs:145-153`) records the acceptance, and the immediate path
(`turn.rs:91-93`) is mutually exclusive with it (`resolve_reply` returns early
at `:86` when judging-on gives `Contributed`). Both branches now have passing
evidence; no double-count. F15 FIXED.
