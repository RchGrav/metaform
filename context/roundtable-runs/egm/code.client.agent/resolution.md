# Resolution of the review findings — `code.client.agent` (ACP client)

Reviewed `element.md` against the code copied into `source/`
(`crates/acp-host/src/harness.rs`, `permission.rs`, `process.rs`). For each finding: whether it is
right, and what should change in the code or the description, and why.

**Verification scope.** Only the `acp-host` crate is present in `source/`. GF1, GF4 and GF8 cite
files in `crates/roundtable/`, `crates/roundtable-web/` and `docs/gate-registry.yaml` that are not
in the copy. For those, the acp-host-side mechanism was verified but the caller-side claims are
accepted on the reviewers' reading of the full repository and must be confirmed against that crate
before the edit is made. All other findings rest on copied code or on `element.md` itself.

**Governing convention to add.** Date implementation and verification claims separately and mark
historical implementation status explicitly. A later implementation report can supersede an older
implementation report; it does not silently supersede an owner requirement or prove live
verification. Resolve decision/gate conflicts explicitly. GF3/GF7 concern chronology; GF8 concerns
the permission boundary; GF9 concerns observable extraction behavior. They need separate remedies.

---

## GF1 — Scope is `cfg.scope`, not the project root (Blocker, egm-codebase-details) — RIGHT

The decision says scope is "the project root that contains the shared workspace". In the copied
code, `ScopePolicy::new(root)` (permission.rs 41–50) enforces exactly the root it is handed;
`decide()` checks `full.starts_with(&self.root)` (permission.rs 62, 121–138). **This element is
boundary-agnostic** — it does not choose project root vs workspace. The reviewers' claim (default
`cfg.scope` = workspace; the web page sends no scope) lives in the roundtable/roundtable-web crates
not present here; accept and confirm there.

What to change: this needs a decision, not a wording tweak, and the chosen boundary must be quoted
consistently in (a) the decision text, (b) gate RT-G18, (c) the config default in
`crates/roundtable/src/config.rs`, and (d) `roundtable-web/assets/index.html`. Either
- keep the promise: make the page (or engine) pass the project root as scope, and set that as the
  default; or
- amend the decision to "the shared workspace, or the scope the caller names" and fix RT-G18 to
  match.

Why: as shipped, the default path (workspace, page sends nothing) does not honour "project root
containing the workspace", so the description states a guarantee the running configuration does not
provide. Blocker stands.

## GF2 — The agent never receives the reason (Blocker, egm-codebase-details) — RIGHT about the code

`Shared::decide()` (harness.rs 898–930) returns only `Option<usize>` — the index of the chosen
permission option. Both response builders `on_permission_v1` (936–951) and `on_permission_v2`
(953–974) construct only `Selected(option_id)` or `Cancelled`. The `reason` string is published
only as the `PermissionDecided` bus event (920–928). So the decision's "rejected at once **with the
reason**, so the agent can continue another way" is not delivered to the agent; the reason reaches
only the bus. Delivery onward to the discussion record / chair is an integration obligation whose
consumers are not supplied; publication alone does not verify that clause.

What to change — primarily the **description**:
- Reword the decision: the refusal is signalled to the agent by withholding the allow option (a
  selected reject option, or `Cancelled`); the **reason is published as a `PermissionDecided` bus
  event** to the discussion record and the chair, not sent to the agent in-band. Keep the "instead
  of stalling" intent — the reject/Cancelled answers the permission request immediately, but does
  not guarantee that the agent continues successfully or knows how to choose another approach.
- Do not claim the code delivers the reason to the agent. The natural ACP outcomes used here carry
  no free text. If the owner truly requires the agent to see the reason, that is a **code/product
  decision** — a new out-of-band message to the agent (or a free-text outcome field if the SDK
  exposes one) — and it must be reconciled with RT-G19 (no second prompt on a busy session). The
  copied files do not establish whether the SDK outcome type has such a field; do not assert it.

Why: the blocker is that the description promises something to the agent that the code does not do.
The honest resolution records where the reason actually goes and drops the in-band claim.

## GF3 — 'ACP v2 not implemented' is not marked superseded (Major, egm-codebase-details) — RIGHT

`verified` (2026-11-05) records a live v1-only test and ends "ACP v2 not implemented". The current
code is v2-first with v1 fallback (harness.rs 8–12, 187–230; `connect_v2`, `v1_fallback_reason`
1096–1111). The entry is a dated snapshot but reads as current because the doc has no as-of rule.

What to change — `verified` layer: mark the entry "as of 2026-11-05 (v1 live test)" and add that
the v2-first build (`elephant.built`, 2026-11-07) is **implemented in code but not yet
live-verified**; cross-reference `elephant.built`. Apply the governing convention above.

Why: it is not a real contradiction in time (the build postdates the test), but leaving an unmarked
older entry invites a reader to treat a historical test as the current state. The substantive gap —
GF7's "is v2 verified live?" — must stay visible, not be hidden by a bare "superseded" label.

## GF4 — Sandbox mode is hard-coded by harness id (Major, egm-codebase-details) — RIGHT about where the gap is

`decisions.residual_risk` promises Roundtable "selects [a sandbox mode] through
session/set_config_option" where a harness advertises one. In the copied code the **capability
exists**: `set_config()` (465–506), the `ConfigOptionUpdate` handlers (774–778, 833–836) and the
published `config_options` on `SessionOpened`/`SessionResumed`/`ConfigChanged` all expose advertised
options to the caller. The reviewers' claim that selection is actually a static per-harness-id table
(config.rs 212–218; OpenCode via env 198–210) with only a warning for other seats (engine.rs
992–995) is caller-side and not verifiable from `source/` — confirm before editing.

What to change:
- If the owner wants the promised behaviour: fix the selection logic in `crates/roundtable` to
  consult the advertised config options (a code change).
- Otherwise amend `residual_risk` to say sandbox mode is chosen from a static table keyed on
  harness id, that advertised options are **not** consulted for this choice, and that seats without
  an entry get a warning only.

Why: the description asserts a runtime capability-driven selection the shipped path does not
perform; Major stands. But do not write that acp-host lacks the setter — it has one.

## GF5 — Undocumented permission-policy edge cases (Major, egm-codebase-details) — RIGHT

All six are verified in the copied code:
1. A request naming **no** paths is allowed for any kind (`outside.is_empty()` → Allow,
   permission.rs 130–131; test 162).
2. A relative path with a non-absolute (unknown) cwd is refused (58–60; test 167–168).
3. Symlinks are followed up to `MAX_SYMLINKS = 40` (68, `resolve` 79–119; tests 190–220).
4. A v2 command's `cwd` is treated as a location and scope-checked (harness.rs 964).
5. An allow becomes a reject when the agent offers no allow option (910–914).
6. One-time options are preferred over standing ones (905–909); a standing-only choice is noted
   in the reason (915–919).

What to change — add a "Permission policy edge cases" subsection to the description recording all
six, with the reason for (1): a request with no named path has nothing to scope-check, so it is
allowed by the same logic as the residual risk (which already admits commands cannot be confined by
path checks). Why: these are observable, safety-relevant behaviours a reader cannot infer from the
decision text; Major stands.

## GF6 — Undocumented lifecycle behaviours (Major, egm-codebase-details) — RIGHT

All verified in copied code: auth retry via `authenticate`/`auth/login` (309–384); `session/resume`
or `session/load` with replay suppressed (386–459; `on_receiving_result` clears `replaying` in
order at 444–451; replay suppressed at 727–732); `set_config` only for advertised options
(465–482); SSE MCP refused on v2 (1118–1131); `idle` ends a turn only after the session was seen
active (848–860); open prompts failed on process exit (268–269 `fail_open_turns`); `session/close`
at shutdown (598–644); 1 s / 2 s grace then SIGKILL of the process group (process.rs 25–27,
108–111, 132–148); stderr tail 40 lines × 2000 bytes (process.rs 17–18, 159–188); env removals
applied before explicit env (process.rs 63–70, test 196–214).

What to change — add a "Connection and process lifecycle" section to the description documenting
these, and expand the `upstream.agent.coding` want to cover auth retry, resume/load, set_config and
SSE refusal. Note that "idle ends a turn only after seen active" is an implementation detail of
rule 2 ("v2 completion is state_update idle") that the rules layer should spell out, and that
process.rs 23–24 already flags the shutdown timers as "PENDING OWNER CONFIRMATION" — the
description should carry the same caveat. Why: none of these are reachable from the current wants;
Major stands.

## GF7 — Which layer is current / is v2 verified live (Major, egm-comprehension) — RIGHT, overlaps GF3

`verified` (2026-11-05, v1-only) vs `elephant.built` (2026-11-07, v2-first) vs `rules` (v1/v2
semantics) — the document never says which is current or whether the v2-first build was tested
against live agents.

What to change — add the governing as-of/superseded convention (top of this file), mark the
verified entry as a dated snapshot, and state plainly: **v2-first negotiation is implemented in
code; the supplied record establishes live verification only for ACP v1 (2026-11-05), not v2.**
Why: a later source implementation does not establish a live test. GF8 and GF9 are separate
decision/gate conflicts, not resolved by chronology.

## GF8 — Ambiguous governing boundary (Major, egm-comprehension) — RIGHT

`decisions` says scope = "project root containing the workspace"; gate RT-G18 says "outside the
workspace". `docs/gate-registry.yaml` is not in the copy — confirm the gate's exact wording there.

What to change — settle ONE boundary as in GF1, quote it once in the decision, and make RT-G18 cite
that boundary verbatim (and fix the config default/page to match). A later implementation report
does not itself authorize replacing the explicit project-root decision with a workspace boundary.
Why: a gate is the operative test; it and the decision cannot name different boundaries.

## GF9 — Reply rule conflict (Major, egm-comprehension) — RIGHT; the rules differ observably

`Transcript::final_message()` (harness.rs 166–170) returns the last nonblank segment. The
`// gate: RT-G09` comment states intent but does not prove that behavior is after the last tool.
On v1, `split()` sets a flag; only a subsequent text append creates a new segment (124–142,
746–748). Counterexample: agent text "Checking", then a tool call, then completion with no more
text. `final_message()` returns "Checking", although no text follows the last tool call. A later
blank-only segment also causes fallback to earlier text. These are not the same rule.

On v2, segments are message IDs in first-seen order, snapshots update those segments, and tool
updates do not split them (144–163, 789–831). Thus neither the latest tool boundary nor the latest
message update defines which segment `final_message()` returns.

There is also the valid two-output ambiguity: `reply()` joins all nonblank segments (172–179),
while `PromptCompleted` publishes both fields (539–545, 883–890). The test
`the_reply_is_every_text_segment_in_order` shows `reply()` returning
"Let me check.\n\nFinal answer." and `final_message()` returning "Final answer." The copied
source does not include the manager consumer, so its actual field choice cannot be verified here.

What to change — recommend an explicit contract that the group's collected message is
`final_message`, defined as the last nonblank agent text segment with the version-specific
segmentation above; `reply` is the accumulated text transcript. Check the full-repository consumer
and correct it if needed. Amend RT-G09 and its code comment to match this contract, recording the
pending gate disposition explicitly. If the owner instead retains the strict after-last-tool
requirement, change extraction to track that boundary and return empty when no qualifying later
text exists; define v2 tool/message ordering too. Merely cross-referencing the archaeology and
gate cannot reconcile them.

Why: the code's fallback to pre-tool text disproves equivalence, independently of which output
the manager consumes. See `CursedRelay-findings.md` for the reconstructable counterexample.

## GF10 — Undefined / inconsistent Intent direction (Major, egm-comprehension) — RIGHT

Define the convention explicitly: in "What other parts rely on it for (**their** wants)" the Intent
is from the **other part's** view; in "What it relies on (**its** wants)" the Intent is from **this
element's** view — `send` = this element emits to the edge, `receive` = it takes in from the edge,
`send_receive` = both.

Under that single rule the "its wants" entries are all consistent **except two**, which are simply
mislabelled:
- `code.server.tool` and `collection.workspace.shared` are tagged `send`, but this element
  **receives** the MCP config and the cwd from them and forwards them to the agent in
  `session/new` (harness.rs 312, 315, 327). Both should be `receive`.

All other labels are already correct under the convention (`code.bus.event` send = `bus.publish`;
`code.launcher.agent` receive = takes the launch; `code.adapter.agent` / `upstream.agent.coding`
send_receive = bidirectional ACP). What to change: add the one-line definition and flip those two
labels. Why: GF10 is right that the semantics are undefined; the constructive fix is a definition
plus two specific corrections, not a blanket rewrite.

## GF11 — Undefined core terms (Major, egm-comprehension) — RIGHT

`harness`, `agent`, `participant`, `seat`, `chair`, `chassis`, `occupied`, `role SE`, `name_length`
are used without definition. Concretely, "occupied" (in the `code.manager.chat.group` want:
"reports that its previous prompt is still in progress (occupied)") has **no counterpart in the
code** — the code says "busy" / `is_busy()` (harness.rs 585–587) and "still running prompt"
(519). "harness" in code = the launched ACP process plus its sessions (the `Harness` struct, 55);
"agent"/"participant"/"seat" are used interchangeably in prose for a roundtable member.

What to change — add a Glossary defining each term from its role in this element, and note where a
doc term differs from the code term (occupied ↔ busy). Why: the ambiguity is real and blocks a new
reader; Major stands.

## GF12 — Short archaeology paths / uncited 500-line limit (Nit, egm-comprehension) — RIGHT

Only the first archaeology entry gives a full-ish base (`archaeology/src/metaform/modules/
roundtables/roundtable/harness.py:420-480`); later entries (`harness.py:508-516`, `harness.py
~793`, `test_acp_v2.py:60-160`, `fake_agent.py`) have no base, and `elephant.gaps` cites a
"500-line limit" with no source.

What to change — state the archaeology root once and make every short path relative to it (or give
full paths); cite the source of the 500-line limit, or drop the number and just record that
`harness.rs` is ~1,330 lines. Why: small but real; a reader cannot locate the referenced files or
verify the limit. Nit stands.
