# Resolution of review findings — element `code.server.tool` (participant tools)

Decisions by **SecretBunker**. Each finding is judged as *right* (identifies a real
defect/gap in the element) or *not right*, with the change prescribed for the **code**
and/or the **description** (`element.md`). Severity tags are the reviewers'.

## Scope and verification note

The `source` folder contains only `crates/roundtable/src/mcp.rs` and
`crates/roundtable/src/engine.rs`. Findings that cite
`crates/roundtable-web/src/app.rs` and `crates/roundtable-web/src/tables.rs`
(GF2 partly, GF4's chair sub-point, GF5's persistence sub-point) cite material that
is **not in the provided sources**. Those specific line references cannot be
independently confirmed here; the verifiable parts (everything in `mcp.rs` and
`engine.rs`) are confirmed below. Where a finding rests on the unavailable files,
the resolution accepts it **provisionally** and marks it "confirm against
roundtable-web" rather than asserting it as established fact.

## Verdict summary

| Finding | Verdict | Change in | essence |
|---|---|---|---|
| GF1 | Right | description | decision overstates "every participant" |
| GF2 | Right | description | `elephant.built` misattributes HTTP serving to mcp.rs |
| GF3 | Right | description | gate RT-G07 missing from `gates` |
| GF4 | Right (qualified) | description | decision under-describes advance semantics |
| GF5 | Right | description + code | feedback under-documented; "0-5" unenforced |
| GF6 | Right (Nit, facts only) | description (optional) | no discrepancy, protocol detail only |
| GF7 | Right | description | RT-G11 name conflates refuse and wait |
| GF8 | Right | description | topics on/off never defined |
| GF9 | Right | description | per-agent token unexplained |
| GF10 | Right | description | terms undefined |
| GF11 | Right (Nit, qualified) | description | `Intent: send` undefined (not wrong) |
| GF12 | Right (qualified) | description | unlocatable refs (TRACEABILITY attested but not bundled); decision status unclear |

No finding is rejected outright. One finding (GF4) contains a sub-point that is
*not* a defect, and two (GF6, GF11) are accurate observations that identify an
undefined field rather than a wrong statement — the distinction matters for what
should change.

---

## GF1 — Blocker, decisions: "not every participant gets the server"

**Verdict: Right.** The decision (element.md:51) says Roundtable "serves an MCP
server to every participant, passed in session/new mcpServers". The code passes
the HTTP `McpServer` config only conditionally:

- `engine.rs:966` `let offered = tools.is_some() && harness.accepts_http_mcp();`
- `engine.rs:967-971` the server is pushed only when `offered` is true;
- `engine.rs:973-975` otherwise a warning is recorded ("has no Roundtable
  tools").

The per-seat URL and token are *built* for every seat (`engine.rs:427-430`,
`engine.rs:270`), but they are only *delivered* in `open_session`/
`resume_session` (`engine.rs:977-979`) when the harness advertises HTTP MCP.

**Change: description, not code.** The behaviour is correct and reasonable (you
cannot hand an HTTP MCP server to a harness that does not accept one); the map is
what overstates. Amend the `code.client.agent` want (element.md:16) and the
decision (element.md:51) to say: the server config is offered to every seat but
is passed in `session/new` / `session/resume` `mcpServers` **only when the
harness advertises HTTP MCP**; otherwise the seat has no Roundtable tools and a
warning is published. This turns a "Blocker" into an accurate qualified claim.

---

## GF2 — Major, elephant.built: "mcp.rs does not serve HTTP itself"

**Verdict: Right.** `element.md:83` says "mcp.rs serves both tools over HTTP to
each agent with its own token". `mcp.rs:1-4` states the opposite: it is a
framework-independent handler — "A host receives MCP JSON-RPC messages for one
seat ... and passes them to `handle`". `handle(table, seat, message)`
(`mcp.rs:42`) receives an already-parsed `Value` and a `seat` chosen by the
caller; it opens no socket and performs no auth. Token validation is
`TableHandle::seat_token_valid` (`engine.rs:225-228`), which lives on the engine
handle, not in `mcp.rs`.

The claim that the HTTP route, bearer check, batching and 202 live in
`roundtable-web/src/app.rs` is **provisionally accepted** (app.rs is not in the
provided sources); the verifiable half — mcp.rs is not the HTTP server, and the
bearer credential is checked by `seat_token_valid` — is confirmed.

**Change: description.** Rewrite `elephant.built` to: `mcp.rs` is the
framework-independent MCP JSON-RPC handler (`tools/list`, `tools/call`, etc.);
the per-seat HTTP endpoint, `Authorization: Bearer` check (via
`TableHandle::seat_token_valid`), request batching and `202` replies are in
`roundtable-web`. No code change.

---

## GF3 — Major, gates / elephant.gaps: RT-G07 missing

**Verdict: Right.** The `gates` layer (element.md:59-72) lists only RT-G11 and
RT-G15. The code implements a third, distinctly-numbered gate for this element:

- `mcp.rs:67-70` — `if !table.topics_enabled()` → "Not done: this table has no
  topics", comment `// gate: RT-G07`;
- `engine.rs:374-379` — `topics_active()` = `cfg.topics && judging &&
  jev.configured()`, comment `// gate: RT-G07 topics are off by default and need
  JEV`;
- `engine.rs:921-923` — a pending advance is dropped when JEV is lost
  ("topics need judging on and a key").

The elephant gap "advance only works with topics on" (element.md:86) is true but
too vague to stand in for a gate.

**Change: description.** Add **RT-G07** to the `gates` layer with its registry
status, naming it "advance refused when topics are off; topics need the setting,
judging on and a JEV key; a pending advance is dropped when JEV is lost". Replace
the vague elephant gap with the same three conditions. No code change — the gate
already exists and is correctly commented.

---

## GF4 — Major, decisions: advance semantics

**Verdict: Right in substance, with one qualification.** The decision
(element.md:51) says advance "ends the current topic and moves the table on" but
does not say *when* or what happens to overlapping calls. The code:

- `engine.rs:879` `self.advance = Some((by, topic...))` **stores** the request;
  a later advance **silently replaces** a still-pending one (no notice);
- `engine.rs:511-519` it is applied in `step()` only after `if self.floor.is_some()
  || self.judging_floor.is_some() { return; }` — i.e. deferred until no floor and
  no JEV verdict is pending;
- `mcp.rs:18` does say "Takes effect when the current turn ends", but that text
  is in the tool schema, not in the element's decision.

So three real omissions: deferred application, last-advance-wins, and the
turn-end timing being absent from the decision.

**Timing correction (GammaIodine final adjudication, verified).** "Applied at the
end of the current turn" is *not* an accurate description of the implementation.
`on_tool` (`engine.rs:666-675`) changes a floor holder to `Working` and calls
`release_floor` (`:673`) then `opportunity` (`:675`) as soon as tool activity is
reported — before that participant's eventual finished contribution. A pending
advance can therefore apply *before* the working participant completes, as well
as being delayed by a pending verdict, hold, seating or rating
(`engine.rs:495-524`). The tool text "Takes effect when the current turn ends"
(`mcp.rs:18`) is a request acknowledgement, not a completion guarantee. The
correct wording is: "requested for application when the discussion floor and
pending verdict clear, subject to table state." No element text should repeat
"applied at the end of the current turn" as if it described the code.

**Qualification:** the sub-point "the chair can also issue it (tables.rs:164)" is
**not a defect**. The decision explicitly says "with two tools and no role
checks" and the owner statement (element.md:40) says it is "not a formalized
'only this role can do this'". Anyone, chair included, being able to call advance
is *consistent* with the description, not a contradiction. (tables.rs is also
outside the provided sources, so this sub-point is unconfirmed.)

**Change: description.** Extend the advance decision to state: the request is
queued for application when the discussion floor and pending verdict clear,
subject to table state; only the last pending advance is applied (an earlier one
is superseded without notice — and a later blank-topic request can replace a
set-topic request with a full poll, `engine.rs:879,517`); there are no role
checks, so the chair may issue it too. Correct `mcp.rs:18`'s "when the current
turn ends" to the truthful timing above. Whether to add a displacement notice /
first-request-wins is an optional design choice, not mandated by the supplied
contract (per the owner statement, no first-request-wins requirement exists).

---

## GF5 — Major, feedback (missing)

**Verdict: Right.** Feedback's actual behaviour is nowhere described in the
element (the `want` at element.md:20, gate RT-G15, and the elephant line 79 only
say it exists), and one claim in the code is not enforced:

- **Unenforced "0-5"**: `mcp.rs:23` promises "0-5 in each category, plus a
  bonus", but `mcp.rs:89-96` copies **every** argument key except `participant`
  and `note` into `ratings` with its raw `Value`, with no type or range check;
  the `inputSchema` (`mcp.rs:24-36`) declares the four categories as `integer`
  and `bonus` as `boolean` but adds no `minimum`/`maximum`, no
  `additionalProperties: false`, and `call()` does not validate. Any key with any
  value passes.
- **Matching**: `engine.rs:887` matches the target by `genesis_name` (set at
  `engine.rs:822`), excluding the sender (`j != i`). The tool text
  (`mcp.rs:23,27`) says "as they appear at the table" / "the name of the
  participant" — the genesis-name basis is not spelled out.
- **Zero/ambiguous match**: `engine.rs:888-893` requires exactly one target; on
  zero or several matches it publishes a notice and pushes it onto
  `seat.notices` (the "next turn" queue, `engine.rs:89-90`). `mcp.rs:23` only
  mentions the *zero*-match case, not the several-match case.
- **Unknown sender**: `engine.rs:886` drops the command with no reply when
  `from` is not a seat label.
- **Persistence** ("saved to identity and accolades log", app.rs:103-111) is
  **provisionally accepted**; app.rs is not in the provided sources. Element.md:20
  already states the intent ("toward accolades and identity").

**Change: description AND code.**
- *Description*: add a feedback paragraph to the element documenting: ratings are
  currently opaque key/value pairs (the "0-5" claim is not enforced), the target
  is matched by genesis name excluding the sender, exactly one other participant
  must match (zero or several produce a notice at the sender's next turn), an
  unknown caller is dropped, and the result is published to identity/accolades.
- *Code*: make the tool's promise true. Either (preferred) add `minimum: 0`,
  `maximum: 5` to the four integer fields, `additionalProperties: false`, and
  validate the category/bonus types in `mcp.rs::call`; or, if ratings are meant to
  be free-form, remove the "0-5" wording from `mcp.rs:23` and say ratings are
  recorded verbatim. Code and description must agree on this point.

---

## GF6 — Nit, protocol details

**Verdict: Right as an observation; it does not identify a discrepancy.** All
three facts are accurate:

- `mcp.rs:12` `const PROTOCOL = "2025-06-18"`; `mcp.rs:48` echoes the client's
  `protocolVersion` with that default;
- `mcp.rs:46-56` answers only `initialize`, `ping`, `tools/list`, `tools/call`;
  everything else gets `-32601`;
- `mcp.rs:43` `let id = message.get("id").cloned()?;` returns `None` for
  messages with no id (notifications get no reply).

The element makes no contrary claim about protocol versions, so there is no
"description says something the code does not do" here. This is standard MCP
conformance detail.

**Change: description, optional only.** If the map is meant to be
self-contained, add a one-line "Protocol handling" note under `references`
recording the above; otherwise explicitly accept the omission. **No code
change.** Keep it a Nit.

---

## GF7 — Major, egm-comprehension, gate RT-G11

**Verdict: Right.** The gate name (element.md:62) — "The advance tool is **refused**
during a topic poll **and waits for the floor**" — merges two different behaviours
into one confusing sentence, and "floor" is undefined (see GF10). The code shows:

- during a poll: `mcp.rs:72-75` returns "Not done: a topic poll is in progress"
  and `engine.rs:876-877` records a refusal — the request is **not** queued;
- when a floor or JEV verdict is pending: `engine.rs:511-519` **defers** an
  already-stored advance until both are free.

Precise definition of the term (to be inserted): "floor" is the speaking turn
offered to a participant, in seat order, and is offered only while at least two
participants are free (`MIN_FREE_TO_DISCUSS = 2`, `engine.rs:10, 30`);
`floor: Option<(usize,u64)>` is whose turn it is (`engine.rs:157`),
`judging_floor: Option<u64>` is a floor contribution still awaiting its JEV
verdict (`engine.rs:161-164`, RT-G10, `engine.rs:510`). "Floor free" therefore
means **both** `floor.is_none()` **and** `judging_floor.is_none()` — the exact
guard at `engine.rs:511-513`, and the sense of "End the current topic once the
floor is free" (`engine.rs:41`, `engine.rs:872`). This two-condition definition
is stricter than "no pending JEV verdict" alone and is the wording GF7/GF10
should carry. (Credit: SpinedSolid addendum, point 1.)

"Refused" and "waits" therefore describe two different situations, not one. The
gate's status "active, removal proposed" also conflicts with code comments that
still treat RT-G11 as an active gate (`mcp.rs:72`, `engine.rs:872`).

**Change: description.** Rename/clarify RT-G11 so it states the poll case alone
("advance is refused while a topic poll is in progress; the poll decides the
next topic"), and record the deferral as its own behaviour (or its own gate) with
"floor" defined as above (speaking turn + the two-condition "floor free").
Reconcile "removal proposed" with the live RT-G11 comments in code and with
`docs/gate-registry.yaml`. No code change.

---

## GF8 — Major, egm-comprehension, elephant.gaps ("topics on")

**Verdict: Right.** The element never defines a topics on/off mode. It appears
only as the gap "advance only works with topics on" (element.md:86) and the
decision note "Topics need JEV judging" (element.md:51-52). The code
(`engine.rs:374-379`) defines it precisely: topics are a table setting, **off by
default**, and active only when `cfg.topics && judging && jev.configured()`. When
off, `mcp.rs:67-70` refuses advance with "Not done: this table has no topics"
and `engine.rs:921-923` drops a pending advance. None of that is in the element.

**Change: description.** Add a short definition: "topics" is a table setting,
off by default; it is active only with the setting on, judging on, and a JEV key;
when off, `advance` is refused with a "Not done" reply, topic polls do not run,
and a pending advance is dropped. Cross-reference RT-G07 (GF3). No code change.

---

## GF9 — Major, egm-comprehension, elephant.built (per-agent token)

**Verdict: Right.** `element.md:83` mentions "its own token" but explains nothing
about issuance, delivery, or purpose. The code:

- `engine.rs:270` issues one `random_hex()` (32 OS-random bytes,
  `engine.rs:236-239`) per seat name at spawn, held in `TableHandle.tokens`
  (`engine.rs:200`);
- `engine.rs:427-430` builds a per-seat URL
  (`{base}/{table}/{seat}`) and pairs it with that seat's token;
- `engine.rs:967-971` delivers the token as an `Authorization: Bearer` header on
  the HTTP `McpServer` config in `mcpServers`;
- `engine.rs:225-228` `seat_token_valid` checks the presented token against the
  seat, so the HTTP layer can pass a trustworthy `seat` into
  `mcp.rs::handle(table, seat, ...)` — that is the token's purpose: caller
  identity.

**Change: description.** Extend the element (and the corrected `elephant.built`)
with: tokens are 32 random bytes generated per seat at table spawn; delivered as
a Bearer header in that seat's `mcpServers` entry; used by `seat_token_valid` to
authenticate the caller so `handle`'s `seat` argument is authoritative. No code
change. (Overlaps GF2 — fix both together.)

---

## GF10 — Major, egm-comprehension, undefined terms

**Verdict: Right.** The element uses *topic, round, poll, floor, head of the
table, accolades, upstream.system.reputation* and the "R3" archive numbering
(element.md:52) without definition, and assumes prior knowledge of the
discussion model. The code adds further terms a reader would need — `genesis
name` (`engine.rs:822`), "floor"/`FloorGiven` (`engine.rs:611`), the `R{n}-`
message-ID prefix (`engine.rs:370`). Note `engine.rs:370` builds
`format!("R{}-", topic_index)`, so "R3" really denotes the third *topic's*
message prefix, not an external archive's numbering — the decision's wording
("the archive's numbering where R3 is the third topic") is itself loose.

**Change: description.** Add a glossary (or a pointer to the canonical
definitions in the README / ACP design / TRACEABILITY) covering every listed
term, plus `genesis name`, `JEV`, and the `R{n}-` prefix. Define "floor" exactly
as in GF7: the speaking turn offered in seat order while at least two
participants are free, with "floor free" = `floor.is_none()` AND
`judging_floor.is_none()`. Replace the vague "archive's numbering" phrase with the precise statement that `R{n}-` prefixes
message IDs for the n-th topic. No code change.

---

## GF11 — Nit, egm-comprehension, wants (Intent: send)

**Verdict: Right that the field is undefined; not right that "send" is wrong.**
Every want in the element (element.md:16, 19, 20) is tagged `Intent: send`, and
the document never defines `Intent` or its direction. A new reader cannot tell
whether "send" describes this element sending, or the other part sending. In
fact "send" is defensible: the config is *sent* to the client in `session/new`
(`engine.rs:977-979`), and this element *sends* `Command::Advance` /
`Command::Feedback` to its dependencies (`engine.rs:207-209`). So the value is
not wrong — only undocumented.

**Change: description.** Add a one-line legend defining `Intent: send` (e.g.
"the want is fulfilled by a one-way send from the producer to the consumer"), or
replace the tag with an explicit directional wording. No code change. Keep it a
Nit.

---

## GF12 — Nit, egm-comprehension, references / sources / decisions.by

**Verdict: Right.** Three locatability/status problems, all verifiable from
`element.md` itself:

1. `references` (element.md:24-31) lists "4 session/new 'optional MCP tools'"
   (numbered) next to "ACP v2 workspace/tool distinction" (**unnumbered**);
   the latter cannot be located consistently.
2. `elephant.sources` (element.md:81) cites "TRACEABILITY I-3, I-4".
   `engine.rs:3-4` confirms `docs/TRACEABILITY.md` is a real repo document with
   an attested citation scheme (R = README.md, D = the ACP integration design,
   O = an owner decision). So this is **not a bogus citation**: the defect is
   narrower — the file was not included in the review bundle and the `I-3`/`I-4`
   items are not quoted, so their content cannot be checked here. There is also
   a concrete inconsistency the reviewers did not name: the elephant calls them
   "owner decisions recorded 2026-11-05" but tags them with an **`I`** prefix,
   whereas the attested scheme uses **`O`** for owner decisions. The `I` prefix
   is not defined anywhere in the supplied materials.
3. `decisions.by` is `"Claude"` (element.md:50) — an AI agent, not the project
   owner — while gates still carry "owner disposition pending" (RT-G15,
   element.md:69) and `elephant.gaps` says "Whether the feedback tool stays is
   open with the owner" (element.md:85). The decision's authority/ratification
   status is therefore unclear.

**Tension found during verification (not named in the findings), stated
carefully:** the owner statement (element.md:40, dated 2026-11-05) says *"and
give them the feedback tool"*, which endorses providing feedback, while the
November 7 elephant (element.md:85) records "Whether the feedback tool stays
is open with the owner" and RT-G15 (element.md:69) is "owner disposition
pending". These are not strictly contradictory, because (i) an endorsement of
*giving* the tool does not settle RT-G15's specific "exactly one other
participant" gate, and (ii) the dated statement does not by itself prove the
later retention question is resolved. (Credit: GammaIodine final adjudication.)
The resolution should record the chronology and keep "what is currently
implemented" distinct from "what disposition is pending" — it should **not**
mark RT-G15 approved, the gap resolved, or the earlier statement superseded
purely by inference. Reconcile against the actual owner record.

**Change: description.** (a) Give the "ACP v2 workspace/tool distinction"
reference a section number or a precise anchor (the project does cite section
numbers elsewhere, e.g. "D §6" at `engine.rs:7`), and either include, point to,
or quote `docs/TRACEABILITY.md` items I-3/I-4; reconcile the `I` prefix with the
attested R/D/O scheme (`engine.rs:3-4`). Do **not** invent the items' content.
(b) State who "Claude" is and mark the decision's status (provisional /
owner-ratified / superseded). Do not infer ratification from chronology.
(c) Record the feedback chronology as above: keep the implemented behaviour
distinct from pending dispositions, and reconcile against the actual owner
record rather than resolving it by inference. No code change.

---

## Cross-cutting observations

1. **Most fixes are documentation-only.** The code implements a coherent,
   well-commented design; the defects are that `element.md` overstates (GF1,
   GF2), omits (GF3, GF4, GF8, GF9, GF10), or leaves undefined (GF7, GF11,
   GF12) what the code does. GF5 is the one finding that also warrants a code
   change (or a deliberate decision that ratings are free-form).
2. **Gate bookkeeping is inconsistent.** RT-G07 is in code but not in `gates`;
   RT-G11 is "removal proposed" in `gates` but still cited as active in code;
   RT-G15 is "owner disposition pending" while the elephant records feedback's
   survival as open. `docs/gate-registry.yaml` and the `gates` layer need a
   single reconciliation pass (GF3, GF7, GF12) — but this should not be resolved
   by inferring the owner's November 5 statement settled the November 7 question
   (see GF12).
3. **"No role checks" is consistently implemented** and should be preserved as
   the design intent (owner statement, element.md:40; decision, element.md:51);
   GF4's chair sub-point is not a defect.
4. **Unverifiable references** to `roundtable-web/src/app.rs` and `tables.rs`
   (GF2, GF4, GF5) should be confirmed against those files before the
   corresponding sub-points are treated as established; the `mcp.rs`/`engine.rs`
   halves are confirmed above.
5. **Refinements from SpinedSolid's addendum** are incorporated: (i) GF7/GF10
   now carry the exact two-condition "floor free" definition
   (`floor.is_none()` AND `judging_floor.is_none()`, `engine.rs:511-513`);
   (ii) GF12 is qualified — `docs/TRACEABILITY.md` and its R/D/O prefix scheme
   are attested at `engine.rs:3-4`, so the citation is *unverifiable from the
   bundle*, not bogus. An additional inconsistency is recorded there: the
   elephant uses an undefined `I` prefix for "owner decisions" where the
    attested scheme uses `O`.
6. **Verified addenda A1–A3 (CuriousArmada; confirmed by BuoyantSentry and
   re-checked here), with corrected scope.** A1: a blank-topic `advance`
   overwrites `Some(Some("UI"))` with `Some(None)` at `engine.rs:879` and
   `:517` turns that into a full poll — a silent change of the pending action,
   not just last-writer-wins (GF4). A2: `settings_changed` (`:912-928`) notices
   a cancelled poll (`:917`) and a dropped advance (`:922`) but silently clears
   a bare `topic_due` at `:924`; note the *reachable* case is a `topic_due` from
   quiet rounds (`:655`) deferred behind a floor/verdict (`:511`) and then
   cleared by a settings command — the `:517`→`:520` sequence has no command
   point between set and check, and `SettingsChanged` is still published
   (`:927`). A3: `accepts_http_mcp()` is re-evaluated on the freshly launched
   harness for both `open_session` and `resume_session` (`:966`, `:976-978`), so
   a resumed identity can gain/lose tools across tables; but both branches
   report current availability via `SeatReady { tools }` (`:821-831`), so "no
   audit record of the flip" overclaims — a once-per-start event carries the
   current state. (Scope corrections: GammaIodine final adjudication.)
7. **Code changes that are warranted vs. optional.** Warranted: GF5 rating
   validation (allowlist four 0–5 integer categories + boolean bonus + string
   note, reject unknown fields, in `mcp.rs::call`, mirrored in the schema) and
   truthful advance/topics-disabled wording. Optional design choices, not
   mandated by the supplied contract: a displacement notice / first-request-wins
   for `advance`, a dedicated `topic_due` cancellation notice, a cross-table
   capability audit, and a loud notice for an unknown `feedback` sender (the
   "Sent your feedback" text at `mcp.rs:98-99` acknowledges a successful
   enqueue, not recorded success). Where first-request-wins is chosen, a
   read-only `TableHandle` accessor is insufficient — two callers can both see
   an empty slot before enqueueing; enforce it in the serialized engine.


## GammaIodine final qualifications

See [GammaIodine final adjudication](GammaIodine-final-adjudication.md) for evidence and decisions on A1–A3 and disputed GF4/GF5/GF11/GF12 conclusions. In particular, advance may apply before a working participant completes; resume already emits SeatReady with tool availability; SettingsChanged is still emitted when topic_due is cleared; and feedback-retention intent does not decide the exact-one-target gate. Required code corrections remain feedback validation and truthful advance/topics-disabled wording. These qualifications supersede contrary assertions above in GammaIodine’s contribution; no source implementation was changed.
