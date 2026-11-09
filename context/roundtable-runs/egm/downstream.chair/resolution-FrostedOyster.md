# Resolution of review findings for `downstream.chair`: user

This document records my decision on each review finding against the element description in `element.md` and the code in `source/`. For each finding I say whether it is right and what should change.

## Verified source for this resolution

The element's own source is `source/crates/roundtable-web/src/tables.rs`, `src/app.rs`, and `assets/index.html`. I read all three in full. Findings that cite core-engine files (`engine.rs`, `turn.rs`, `events.rs`, `config.rs`) point at behavior that lives outside this element's copied source; I rely on those line references and cross-check them against the web code I did read.

---

## GF1 — Blocker — CORRECT. Change the code.

The elephant `built` says "The web page shows every message, rejection and score." The code does not.

- `index.html:234` stores the scores: `scores: d.scores` is carried on the message item.
- `index.html:343-355` (`renderItem`) renders the `who` row, the "unjudged"/"after work"/length badges, and the text — but never renders `item.scores`. So an accepted contribution's scores are fetched and stored but never displayed.
- For vetoes, `index.html:346` renders only `"vetoed: " + item.reasons.join("; ")`, so the failed-check reasons show but not the per-dimension scores even where they exist.

This is a real gap: the description promises every score is shown, but no score is rendered. Fix in code: in the `msg` and `veto` cases of `renderItem`, render `item.scores` using the same per-dimension badge pattern already used for feedback at `index.html:243` and `:251` (iterate `Object.entries(item.scores)` and emit `dimension value` badges). Also render the score alongside a veto's reasons (`index.html:346`). If scores are not meant to be shown, the `built` sentence must be narrowed instead — but since the author's stated intent is to show them, the code change is the right fix.

---

## GF2 — Major — CORRECT. Change the description of the want.

The want for `code.manager.chat.group` reads: "continuing across topics until the work is produced." The defaults contradict this:

- `tables.rs:32-34`: `topics: bool` defaults to `false` (off). So by default there are no topic changes; the discussion stays on one topic.
- `tables.rs:29-30` with `fn rounds() -> Option<u64> { Some(DEFAULT_ROUNDS) }`: rounds default to 10, so the table ends after 10 rounds regardless of whether the work is produced.
- The reviewers cite `engine.rs:647-651` that even an unlimited-round table ends after two consecutive unproductive rounds.

So "continuing across topics until the work is produced" describes a mode that is not the default. Fix the description, not the code: state that these are configurable defaults (topics off, 10-round limit, unproductive-ending) and that the chat group only continues across topics when `topics` is enabled and a round limit is not hit. The want's wording overstates what the group does out of the box.

---

## GF3 — Major — CORRECT. Change the page text and the description.

- `index.html:406` confirm reads: "End this table? Every participant's harness is shut down."
- The reviewers cite `engine.rs:901-908` and `turn.rs:420-434, 564-575`: the first End starts the rating round, and the table ends only after results; a second End stops it immediately.

So the confirm text is wrong about the timing: on the first End the harnesses are not shut down at once, they run for the rating round and are shut down afterwards. The user should be told what actually happens. Fixes:
1. Code: relabel the End button so the two phases are distinct — "End and rate" for the first End, then switch the label to "End now" when the `roundtable.ratings.asked` event arrives (`index.html:242`); make the confirm text match each phase ("This starts the rating round; harnesses shut down after results" vs. "End now, before results"). The page already handles `roundtable.ratings.asked`, so the label switch has a ready hook.
2. Description: `elephant.built` says the page has "end controls" without explaining the two-step end. Add a sentence describing that End begins the rating round and stops the table after results.

---

## GF4 — Major — CORRECT. Change the description (add missing capabilities).

The elephant `built` lists only "hold, resume, guidance and end controls." The code has six more user-facing capabilities that are undocumented in the description:

- advance topic — `index.html:119, 405`
- judging toggle — `index.html:108, 407`
- OpenRouter key settings — `index.html:154`; `app.rs:234-243`
- past-table replay — `app.rs:279-341`; `index.html:371-401`
- prompts-received panel — `index.html:255, 321-331`
- identity resume — `index.html:412-457`

All six are real, reachable controls in the page. Fix the description: extend the `built` list (or add a `gaps`/detail note) to include these. This is a description gap, not a code gap.

---

## GF5 — Major — CORRECT. Change the description (document the security model).

The reviewers cite `app.rs:4-7` (security comment) and `app.rs:170-199` (`require_host` + `require_chair`), and `index.html:164-168, 468` (token from URL fragment). I confirmed all of these in the source I read:

- Every `/api/*` route is behind `require_chair` (`app.rs:192-199`), plus a Host/Origin check (`app.rs:170-184`).
- The token is read from the URL fragment at `index.html:164-168` and kept in `sessionStorage`; `index.html:468` tells the user to open the URL the server printed at startup.

The description never mentions that the user must authenticate as chair with a token, or that this is how the page is reached. Fix the description: state that the chair token is required on all API routes, that it is delivered in the startup URL fragment, and that a Host/Origin check guards against DNS rebinding. Undocumented security requirements are a real gap, not a nit.

---

## GF6 — Nit — MOSTLY CORRECT. Minor code cleanup plus a documented nuance.

Sub-points:

1. `index.html:234` reads `d.truncated`, which the Contribution event lacks (reviewers cite `events.rs:39-50`). It is stored but never rendered, so it is dead code. Action: drop the `truncated` field from the stored item (or add it to the event if it is wanted). Low value either way.
2. The client defaults the limit to 512 (`index.html:177`) against the engine's no-default. This is only a display fallback before events arrive and is corrected by `roundtable.opened` (`index.html:218`). Action: either align the fallback with the engine default or note it is only a placeholder. Low impact.
3. "Hold only stops new turns" (`engine.rs:500`) is engine behavior; the description should say Hold pauses the turn-taking but does not interrupt in-flight work. This belongs in the description, not as a code fix.
4. The empty `gaps` list is owned by GF9, not this finding (see GF9).

So the actionable changes are tiny (remove dead `truncated`, align/annotate the 512 default) and one description sentence for Hold semantics.

---

## GF7 — Major — CORRECT. Reconcile the decision and the elephant.

- The `decisions` layer says CQU is "the chair … (observation-only human chair)" from the run-1 audit.
- The `elephant` layer and owner quote describe an interacting chair: "hold, guide or end it" and "the intent is for me to be able to interact with them."

These are different models of the user. The run-1 "observation-only human chair" is a separate notion (an audit that only observes). This element's CQU is interactive. Fix the description: clarify in the decision that the observation-only sense belongs to the run-1 audit and is not the sense used here, and that in this element the user is an interactive chair who starts a table, follows it, and holds/guides/ends it. The two should be reconciled, not left contradictory.

---

## GF8 — Major — CORRECT. Define the undefined terms.

The decision uses `CQU`, `Intake 3.1`, `address vs alias`, and "why 'user' is invalid" without defining them, and the element is titled/named `user` while addressed `downstream.chair`. Fix the description: add brief definitions — what CQU means, what Intake 3.1 requires of a CQU, the distinction between the element's address (its map key, `downstream.chair`) and its alias/nickname (`user`), and why `user` cannot serve as the CQU address under Intake 3.1 while it is fine as the display name. Without these the decision is not auditable.

---

## GF9 — Major — CORRECT (with a corrected diagnosis). Fill `gaps`.

- The decision says the chair "sets its objective and selects its participants."
- The New-table dialog does collect an Objective and Seats at creation (`index.html:127-149`), so it is not true that the code lacks these entirely. The real gap is that both are **fixed at creation and cannot be changed once the table is running**: the `command` handler (`tables.rs:157-168`) only accepts `hold`, `resume`, `guidance`, `judging`, `advance`, and `end` — there is no command to revise the objective or change the roster mid-run. So the decision's "sets its objective and selects its participants" reads like ongoing chair control when in fact it is one-time setup at creation.
- `elephant.built` lists only display and hold/resume/guidance/end controls, omitting the creation-time objective/seat setup.
- `gaps` is empty.

Fix: update `built` to mention that a table is opened with an objective and a chosen roster; and record in `gaps` that objective and seats are set only at creation and cannot be altered mid-run. This is a description fix — it is not a mandate to build a mid-run roster-change capability, which the engine does not support and which was never requested.

---

## GF10 — Nit — CORRECT (as a description gap). Document guidance delivery.

The elephant `built` says the page has "guidance … controls" but not who receives guidance, when, or whether JEV judges it. The HTML placeholder (`index.html:115`) does state "delivered to every participant at its next turn," but that is not in the description. Guidance is a chair command (Command::Guidance, `tables.rs:162`) sent to participants; JEV judges contributions, not chair guidance. Fix: add to the description that guidance is a chair message delivered to each participant at its next turn and is not JEV-judged.

---

## GF11 — Nit — CORRECT (as a description gap). State where the page lives and define terms.

The description does not say where the web page is served or how it is reached, and `table`, `rejection`, and `JEV` are used without definition. I confirmed the page is served at the server root (`app.rs:156`) and reached via the startup URL that carries the chair token (`index.html:468`). Fix: add a sentence that the page is served at the server's root and opened with the token-carrying URL printed at startup, and briefly define `table` (a discussion group), `rejection` (a vetoed contribution), and `JEV` (the judging component).

---

## GF12 — Nit — CORRECT (as a description gap). Say who decides the work is done.

The want says "until the work is produced" but does not say who decides that. Given the chair sets the objective and can end the table, the chair is the decision-maker; the table's end conditions (round limit, unproductive rounds — see GF2) also play a role. Fix: state in the want that it is the chair's judgment together with the table's end conditions that determines when the work is produced and the discussion stops. This can be folded into the same description sentence as GF2.

---

## Summary

- Right and actionable in code: GF1 (render scores, reusing the feedback badge pattern), GF3 (relabel the End flow "End and rate" → "End now" on `roundtable.ratings.asked`, fix confirm text), GF6 (drop dead `truncated`, align/annotate the 512 default, document Hold in the description).
- Right description gaps to fix in `element.md`: GF2, GF4, GF5, GF7, GF8, GF9, GF10, GF11, GF12.
- No finding is wrong as raised; all are accepted, with changes split between code (GF1, GF3, GF6) and description (GF2, GF4, GF5, GF7-GF12).

## Two corrections after the final round

SyncedVulcan proposed "all 12 findings are correct, fix three in code." That matches my verdicts on every finding, but its grouping and its GF6 fix need adjustment, and those corrections change what gets edited:

1. **GF6 is not a code-fix class by itself.** Three of its four parts are description edits: the empty `gaps` (owned by GF9), the Hold semantics (`engine.rs:500` stops new turns only, which is intended), and the engine/client limit default. Only `truncated` is code. Calling GF6 a code item invites a bundling error where the Hold sentence is "fixed" in `index.html` rather than stated in `element.md`. My recommendation stands: change the description for Hold; touch code only for `truncated`.
   - One relevance point both documents missed: `truncated` is not merely dead, it is **worth displaying**. `index.html:241` and `234` show that after a busy skip the chair's limit changes (the "larger limit" recovery path, `tables.rs:26-28`), so a reply cut at a changed allowance needs a visible marker. Deleting the field fixes the dead code but loses information the chair needs to interpret a short message. Prefer rendering `truncated` as a badge.

2. **GF3's fix should be a label change, not only confirm text.** SyncedVulcan edits the confirm string at `index.html:406`. The confirm is transient; the button label (`index.html:121`, `End table`) is permanent and is what the chair reads before clicking. The page already receives `roundtable.ratings.asked` (`index.html:242`), so the label can be driven by state: `End and rate` while running, `End now` after the rating round starts. That makes the two-step end visible without a modal. Fixing the confirm text alone leaves the button promising an immediate stop it does not perform.

Neither correction rejects a finding. They change two fixes: GF6 -> one code badge plus three description sentences; GF3 -> label state plus confirm text. The other nine stand as resolved above. GF9 is correct once its diagnosis is corrected: objective and seats are set at creation, not changeable mid-run, so `gaps` should record that rather than implying a missing capability.
