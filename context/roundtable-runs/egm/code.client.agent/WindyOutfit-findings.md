# WindyOutfit: independent verdicts on GF1-GF12, with code evidence

Every claim below was checked against the copied source. Line references are to `source/crates/...`.

## The central split

Nine findings (GF1-GF6, GF11, GF12, partly GF10) are *description* defects: the code does
something, `element.md` says something else or omits it. All of those are right on the code
and are fixed by editing the description, except GF2, which is also a genuine product bug.

Three findings (GF7-GF9) are the same defect reported three times: **`element.md` carries two
generations of statements side by side and never marks which one won.** GF7 is the root
(verified says "ACP v2 not implemented", elephant.built says v2-first). GF8 (scope) and GF9
(reply rule) are the same pathology in `decisions`/`archaeology` vs `gates`. If GF7 is fixed
with a general rule ("when layers disagree, the newer dated layer governs and the older is
marked superseded"), GF8 and GF9 collapse into two applications of it.

## What the code actually does (the facts the resolution must encode)

**Permission reason (GF2).** `decide()` in harness.rs computes `reason` (905-931) and publishes
it only on `PermissionDecided`. The two response builders at 939-973 pick an option and drop
the string:

```rust
let outcome = match self.decide(session, ask, &offered) {
    Some(index) => ...Selected(...request.options[index].option_id...),
    None => ...Cancelled,
};
```

ACP v1 and v2 both have a "cancelled" outcome that carries nothing; the only free-text channel
is the option label, which belongs to the agent, not the client. So the decision text cannot
be delivered in-band on `session/request_permission`. The honest fix is to change the
*description*: say the reason is published to the bus and to the chair discussion record, and
that the refusal is signalled to the agent only by withholding allow (reject option or
Cancelled). No ACP mechanism carries it. Do not pretend the code can.

**Scope (GF1, GF8).** The policy takes a root at construction (`ScopePolicy::new`, permission.rs
41-50). Who builds it and with what is in the roundtable crate, which is *not* in the copy
here. GF1 cites engine.rs:405 and config.rs:144-146 (default `cfg.scope` = workspace) and
index.html:484-489 (page never sets scope). This is consistent with the decision text only in
the default case; if the page never sends a scope, the "project root containing the workspace"
promise is not kept by the shipped path. That is a code/description Blocker, and the fix is a
decision, not a wording tweak: either the page sends the project root, or the decision is
amended to "workspace, or the scope the caller names". GF8 is the same question posed as a
gate/decision conflict; the gate is the operative test and must quote whatever boundary the
decision finally settles on.

**Reply rule (GF9).** `final_message()` (harness.rs 172-175) already carries
`// gate: RT-G09`. Gate RT-G09 is "text after the last tool call"; the code splits the buffer at
`ToolCall`/`ToolCallUpdate` (on_update_v1 739-747) and takes the last non-empty segment. These
are the *same* rule stated two ways — "last non-empty block" is the implementation of "after the
last tool call" — so GF9 is not a contradiction once the archaeology entry names RT-G09. It is
right that the doc does not say they are equivalent.

**Sandbox selection (GF4).** The residual risk promises scope is chosen from *what a harness
advertises*. GF4 says it is hard-coded by harness id in config.rs (212-218, 198-210 OpenCode via
env) and other seats only get a warning (engine.rs:992-995). This is a Major that is *right
about the code and wrong about where the lie lives*: the code does not even have the capability
`element.md` describes as pending. Fix the description: sandbox mode is selected per launch by a
static table keyed on harness id; advertised config options are not consulted for it.

**Policy edge cases (GF5).** All six are visible in the copy: no-path request allowed
(permission.rs 130-131, also the test at 162), relative path with empty cwd refused (58-60,
test 167-168), symlinks up to `MAX_SYMLINKS = 40` (68, 79-119), v2 command cwd treated as a
location (harness.rs 964), allow downgraded to reject when no allow option offered (910-914),
one-time option preferred (905-909). Accurate; document them, and note that "no location" is
the *intended* safe lift only because a request with no named path has nothing to scope-check —
which is exactly the residual risk already stated.

**Lifecycle (GF6).** Authenticate retry 309-384, resume/load with replay suppressed 386-459 and
727-732 (`on_receiving_result` clears `replaying` in order), set_config only advertised 465-482,
SSE refused on v2 (mcp_server_v2 1118-1131), idle-after-active 848-866, fail open prompts on exit
(253-269 `fail_open_turns`), session/close 598-644, SIGKILL group in process.rs 132-148 with
1 s/2 s grace (25-27), stderr tail 40x2000 (17-18), env removals before explicit env
(process.rs 60-70). All accurate.

**Wants direction (GF10).** `session/new`'s `mcpServers` and `cwd` are *sent by* the client and
*received by* the agent, yet the wants say "Intent: send" on the two dependencies that supply
them (`code.server.tool`, `collection.workspace.shared`). That is the reviewer's point and it is
right: the field should be read from the *client's* side of the edge ("what I receive from X"),
not the edge's label. Define it once.

**Terms (GF11).** No definition of harness/agent/participant/seat/chair/chassis/occupied/SE/
name_length anywhere in the doc. Right.

**Paths and line limit (GF12).** `harness.py:508-516` etc. have no base (the archaeology base is
`archaeology/src/metaform/modules/...`, stated once at the first entry only). "500-line limit"
has no citation. Right, Nit.

## Verdict table

| id | right? | layer to change | essence |
|----|--------|-----------------|---------|
| GF1 | yes (Blocker) | decisions + code | scope default is workspace; page sends none |
| GF2 | yes, but fix the words not the code | decisions | ACP has no in-band reason channel; say so |
| GF3 | yes | verified | mark superseded by 2026-11-07 v2-first build |
| GF4 | yes | decisions.residual_risk | sandbox from static id table, not advertised |
| GF5 | yes | new description section | six named edge cases |
| GF6 | yes | wants + new lifecycle section | nine named behaviours |
| GF7 | yes, root of GF7-9 | verified + a governing rule | newer dated layer wins; older marked |
| GF8 | yes, same root | gates/decisions | quote the settled boundary once, gate cites it |
| GF9 | partly | archaeology | last-block == after-last-tool-call; cite RT-G09 |
| GF10 | yes | all wants | define Intent from the client side |
| GF11 | yes | new Glossary | harness vs agent vs participant |
| GF12 | yes (Nit) | archaeology + gaps | one base line; cite the 500-line source |

## Addendum after reading DocileIsotope's `resolution.md`

The draft resolution is sound on GF1, GF3-GF8, GF10-GF12 — verdicts match my code reading. Two
places need correction before it stands.

**1. GF9 — the draft's suggested wording is wrong on v2.** `resolution.md` says the rule is
"the last non-empty agent message block." That is true on v1 but false on v2. `Transcript` is
documented (harness.rs:110-113): "on v1 a new segment starts after each tool call; on v2 each
message id is a segment." `final_message()` (172-175) takes the last non-empty *segment*, not
block. On v2, a trailing empty segment is skipped. The genuine problem is a second one the draft
misses: `take_turn` returns **both** `reply()` and `final_message()` (690), `reply()` joins *every*
non-empty segment (`"Let me check.\n\nFinal answer."`, test 1297-1301), and nothing in the doc says
which one the message the group reads is. RT-G09 is the gate on `final_message`; the caller in
the roundtable crate selects. So GF9's fix must say: the reply handed to the discussion is
`final_message()` (gate RT-G09); `reply()` is the full transcript and is not the message.

**2. GF2 — "no code change is feasible" is too strong.** The wire has no reason field, true, but
the *decision* text promises the agent "can continue another way." With only a reject-id, the
agent learns nothing about why. Code cannot add a reason to the response, but it can publish the
decision to an in-band channel the agent already reads: the bus is client-side only. The honest
options are (a) change the decision wording — "rejected; the reason is recorded for the
chair/discussion, not conveyed to the agent", or (b) accept that "continue another way" is lost
and drop that clause. Recommend (a) plus a one-line note in the decision that in-band delivery is
impossible in ACP v1/v2. My earlier file already said "fix the words," which agrees; this addendum
sharpens it so the resolution does not leave "no code change feasible" as a blanket excuse.
