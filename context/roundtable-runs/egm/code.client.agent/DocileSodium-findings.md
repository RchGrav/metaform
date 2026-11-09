# DocileSodium — independent verdicts on GF1–GF12

Everything below was checked against `source/crates/acp-host/src/{harness.rs,permission.rs,process.rs}`
and `element.md`. Line numbers are to the copied source. I read WindyOutfit's analysis and where I
disagree or add precision I say so explicitly.

## Verification scope (important for auditability)

Only the `acp-host` crate is in `source/`. Many findings cite files that are **not** here:

| finding | cited files outside the copy |
|---------|------------------------------|
| GF1 | `crates/roundtable/src/engine.rs`, `config.rs`, `roundtable-web/assets/index.html` |
| GF4 | `crates/roundtable/src/config.rs`, `engine.rs` |
| GF8 | `docs/gate-registry.yaml` |
| GF12 | archaeology `harness.py`, the "500-line limit" source |

For GF1/GF4/GF8 I can verify the *acp-host mechanism* but **not the caller-side claims**. Those
verdicts are "right on the reviewer's reading of the full repo; confirm against that crate before
editing." GF2, GF3, GF5, GF6, GF7, GF9, GF10, GF11, GF12 rest on copied code or on `element.md`
itself and I verified them directly.

## Points where I add to or differ from WindyOutfit

### GF10 — the Intent convention is recoverable, and exactly two labels are wrong
This is stronger than "define it once." Take the natural convention: in *"What other parts rely on
it for (their wants)"* the Intent is from the **other part's** view; in *"What it relies on (its
wants)"* the Intent is from **this element's** view — `send` = this element emits to the edge,
`receive` = this element takes in from the edge, `send_receive` = both. Under that single rule,
every "its wants" entry is consistent **except two**:

- `code.bus.event` `send` ✓ — the client calls `bus.publish(...)` (harness.rs 252, 523, 920).
- `code.launcher.agent` `receive` ✓ — the client takes a `LaunchSpec`/spawned process.
- `code.adapter.agent`, `upstream.agent.coding` `send_receive` ✓ — ACP is bidirectional.
- `code.server.tool` `send` ✗ — the client **receives** mcpServers config and forwards it in
  `session/new` (harness.rs 315, 327). Should be `receive`.
- `collection.workspace.shared` `send` ✗ — the client **receives** cwd (harness.rs 312, 315).
  Should be `receive`.

So GF10 is right that the semantics are undefined; the constructive fix is (1) write the convention
down and (2) flip those two labels. No other label needs to change. The `their wants` entries are
already from the dependent's view and are fine.

### GF9 — there are TWO text outputs, and the doc names neither correctly
`Transcript` has `reply()` (172–179: **all** non-empty segments joined by blank lines — the whole
turn) and `final_message()` (166–170: the **last** non-empty block only). Both are published in
`PromptCompleted` as `reply` and `final_message` (539–545, 883–890). The map never says which one
is "the participant's reply" that `code.manager.chat.group` collects. On v1, `text.split()` at
each `ToolCall` (747) makes the last block = "text after the last tool call", so `final_message()`
implements RT-G09 and equals archaeology's "last non-empty agent message block". On v2 there is
no split at tool calls (820–832); blocks are keyed by `message_id`, so `final_message()` = "last
non-empty message block". They are equivalent in intent across versions, but the description must
(1) say so and cite RT-G09, and (2) name which of `reply`/`final_message` is the collected reply.
WindyOutfit's "they are the same rule" is right but glosses over the `reply`-vs-`final_message`
split, which is a real undocumented gap.

### GF2 — a description fix, with an honest product caveat
`decide()` (898–930) returns only `Option<usize>` — the index of the chosen option. `on_permission_v1`
(936–951) and `on_permission_v2` (953–974) build only `Selected(option_id)` or `Cancelled`. The
`reason` string is published solely on `PermissionDecided` (920–928). So the agent never receives
the reason: GF2 is right about the code and about the decision's "rejected at once **with the
reason**, so the agent can continue another way" clause. Two fixes:
- **Description (primary):** the reason goes to the discussion record / chair via the bus event;
  the agent is unblocked by the reject or Cancelled, **not** by a reason. Reword that clause. The
  "instead of stalling" intent is still met — the reject itself unblocks the request.
- **Code (if the owner insists the agent see the reason):** that needs a new mechanism (an
  out-of-band message/notification to the agent, or a free-text field on the outcome if the SDK
  exposes one). The latter is a product decision, not a doc tweak, and would interact with RT-G19
  (no extra prompt on a busy session). I could not confirm the SDK's outcome schema has a
  free-text field from the copied files alone; do not assert it either way.

### GF3 / GF7 — unify; the real gap is "implemented ≠ live-verified"
`verified` (2026-11-05) is a dated live-test record: "…over ACP v1 … ACP v2 not implemented."
`elephant.built` (2026-11-07) and harness.rs 8–12/187–230 say v2-first with v1 fallback. These are
not a contradiction in time — the v2 build came two days after the v1-only test — but `element.md`
has no "as-of / superseded" convention, so the entry reads as current. Fix: (1) mark the verified
entry as an as-of snapshot, (2) add a general rule that a newer dated layer governs and older ones
are marked as-of/superseded, (3) **state explicitly that the v2-first negotiation is implemented in
code but has not been live-verified against real agents** — that is GF7's real question
("whether v2 has been verified live"). Simply marking it "superseded" (WindyOutfit) hides the
unverified status; keep it visible.

### GF1 / GF4 — acp-host is boundary-agnostic and does expose the setter
`ScopePolicy::new(root)` canonicalizes whatever root it is given and `decide()` checks
`full.starts_with(&self.root)` (permission.rs 41–63, 121–138). So this element enforces **exactly
the boundary the caller passes**; it does not itself pick "workspace" vs "project root". Likewise
`set_config()` (465–506), the `ConfigOptionUpdate` handler (774–778, 833–836), and the published
`config_options` on `SessionOpened`/`SessionResumed`/`ConfigChanged` mean the client **can** select
any advertised option via `session/set_config_option` — the capability the residual_risk describes
exists here. The disputed "hard-coded by harness id" selection logic is in `crates/roundtable`
(not copied). So for GF4 the resolution is genuinely a fork: either fix the caller's selection
logic to consult advertised options (code) or amend residual_risk to describe a static id table
(description). Don't claim the acp-host lacks the capability.

### GF12 — the archaeology base IS stated once, but is wrong/ambiguous
The first archaeology entry gives a full path ending in `.../roundtable/harness.py:420-480`; later
entries say `harness.py:508-516`, `harness.py ~793`, `test_acp_v2.py:60-160`, `fake_agent.py` with
no base. So "short paths lack a base" is right. Additionally `harness.py:45,383-387` mixes the
roundtable README reference. Fix: state the archaeology root once and make every short path
relative to it (or give full paths); cite the source of the "500-line limit" or drop the number.

## Verdict table

| id | right? | fix | essence |
|----|--------|-----|---------|
| GF1 | yes, Blocker (caller-side; verify) | decisions + config default + page | this element is boundary-agnostic; shipped default is workspace |
| GF2 | yes, Blocker about code; fix words | decisions (+ possible code) | no in-band reason; reason is a bus event only |
| GF3 | yes, Major | verified | as-of snapshot + "v2 implemented, not live-verified" |
| GF4 | yes, Major (caller-side; verify) | decisions.residual_risk OR caller code | selection is static id table, not advertised |
| GF5 | yes, Major | new description subsection | six edge cases, all verified in copied code |
| GF6 | yes, Major | wants + new lifecycle section | nine behaviours, all verified in copied code |
| GF7 | yes, Major, root of GF3/8/9 | verified + governing as-of rule | which layer is current; v2 unverified live |
| GF8 | yes, Major, same root | decisions + gate RT-G18 | one boundary, quoted once |
| GF9 | yes, but clarify the doc | archaeology + wants | last-block == after-last-tool-call; name reply vs final_message |
| GF10 | yes, Major | all wants | define Intent from the element's view; flip two `send`→`receive` |
| GF11 | yes, Major | new Glossary | define 9 terms; "occupied" is doc-only (code: busy) |
| GF12 | yes, Nit | archaeology + gaps | one base path; cite the 500-line source |
