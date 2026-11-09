# SecretBunker — backing verification for `resolution.md`

Line-by-line evidence used to resolve GF1–GF12. Only two source files were
provided: `source/crates/roundtable/src/mcp.rs` and
`source/crates/roundtable/src/engine.rs`. `element.md` is the description under
review. `roundtable-web/src/{app,tables}.rs` are **not** in the provided sources.

## Evidence table

| Finding | Claim | Verified at | Result |
|---|---|---|---|
| GF1 | tools only when harness accepts HTTP MCP; else warning | `engine.rs:966` `offered = tools.is_some() && harness.accepts_http_mcp()`; `967-971` push gated on `offered`; `973-975` warning "has no Roundtable tools"; `977-979` `open_session/resume_session(servers)` | confirmed |
| GF1 | per-seat url/token built for every seat | `engine.rs:270` `tokens` map over all `cfg.seats`; `427-430` url + token per seat | confirmed (built, not always delivered) |
| GF2 | mcp.rs not an HTTP server | `mcp.rs:1-4` "independent of any web framework ... passes them to `handle`"; `mcp.rs:42` `handle(table, seat, message) -> Option<Value>` takes parsed `Value` | confirmed |
| GF2 | bearer credential check | `engine.rs:225-228` `seat_token_valid` (constant-time compare) | confirmed |
| GF2 | HTTP route/batching/202 in app.rs | app.rs NOT PROVIDED | unverifiable |
| GF3 | RT-G07 gate in code | `mcp.rs:67-70` `if !table.topics_enabled()` + `// gate: RT-G07`; `engine.rs:376-379` `topics_active()` + `// gate: RT-G07` | confirmed |
| GF3 | pending advance dropped when JEV lost | `engine.rs:912-923` `settings_changed`: `self.advance.take()` + "topic advance was dropped" | confirmed |
| GF3 | RT-G07 absent from gates layer | `element.md:59-72` lists only RT-G11, RT-G15 | confirmed |
| GF4 | advance stored / replaced | `engine.rs:879` `self.advance = Some((by, topic.filter(...)))` — plain assignment, overwrites, no notice | confirmed |
| GF4 | applied only when no floor/verdict pending | `engine.rs:511` `if self.floor.is_some() \|\| self.judging_floor.is_some() { return; }`; `514-519` `self.advance.take().filter(\|_\| self.topics_active())` | confirmed |
| GF4 | turn-end timing | `mcp.rs:18` "Takes effect when the current turn ends" (tool schema, NOT in element decision) | confirmed |
| GF4 | chair can issue it | tables.rs NOT PROVIDED; but `element.md:51` "no role checks" + `element.md:40` owner "not a formalized 'only this role can do this'" | consistent, not a defect |
| GF5 | "0-5" unenforced | `mcp.rs:23` "0-5 in each category, plus a bonus"; `mcp.rs:89-96` loop inserts every key except `participant`/`note` with raw `value.clone()`; `mcp.rs:24-36` schema has no min/max, no `additionalProperties: false` | confirmed |
| GF5 | matched by genesis name, excluding sender | `engine.rs:887` `filter(\|&j\| j != i && self.seats[j].name.as_deref() == Some(to.as_str()))`; name set at `822` `genesis_name(&session)` | confirmed |
| GF5 | zero/several -> notice at next turn | `engine.rs:888-893` `targets.len() != 1` -> `self.notice(...)` + `self.seats[i].notices.push(why)`; `notices` doc `engine.rs:89-90` "for the next turn" | confirmed |
| GF5 | unknown sender dropped | `engine.rs:886` `let Some(i) = ... position(\|s\| s.label == from) else { return }` | confirmed |
| GF5 | saved to identity/accolades | app.rs NOT PROVIDED; `element.md:20` states the intent | unverifiable |
| GF6 | protocol echo / default | `mcp.rs:12` `PROTOCOL="2025-06-18"`; `mcp.rs:48` `params.protocolVersion ... unwrap_or(PROTOCOL)` | confirmed |
| GF6 | four methods, -32601 | `mcp.rs:46-56` match arms; `other => Err((-32601, ...))` | confirmed |
| GF6 | notifications no reply | `mcp.rs:43` `let id = message.get("id").cloned()?;` | confirmed |
| GF7 | poll = refusal (not queue) | `mcp.rs:72-75` "Not done: a topic poll is in progress"; `engine.rs:876-877` notice "the poll decides" (does not set `self.advance`) | confirmed |
| GF7 | "waits for the floor" = deferral | `engine.rs:511-519` | confirmed (different case) |
| GF7 | "floor free" = TWO conditions, not one | `engine.rs:511-513` `floor.is_some() \|\| judging_floor.is_some()` both block; `engine.rs:10,30` floor offered only while >=2 free (`MIN_FREE_TO_DISCUSS=2`); `engine.rs:157` `floor: Option<(usize,u64)>` whose turn; `engine.rs:161-164` `judging_floor` = contribution awaiting JEV; `engine.rs:41,872` "once the floor is free" | confirmed (SpinedSolid addendum pt.1, incorporated) |
| GF7 | RT-G11 status conflict | `element.md:63` "removal proposed"; `mcp.rs:72` + `engine.rs:872` comments `// gate: RT-G11` still active | confirmed |
| GF8 | topics off by default, 3 conditions | `engine.rs:374-379` "off by default"; `cfg.topics && self.judging && self.jev.configured()`; `mcp.rs:67-70` "Not done: this table has no topics" | confirmed |
| GF9 | token issuance | `engine.rs:270` `random_hex()` per seat; `236-239` 32 bytes OS random as hex; `engine.rs:200` `tokens` on `TableHandle` | confirmed |
| GF9 | delivery | `engine.rs:967-971` `HttpHeader::new("Authorization", format!("Bearer {token}"))` on the `McpServer::Http` | confirmed |
| GF9 | purpose = caller identity | `engine.rs:225-228` `seat_token_valid(seat, token)`; `mcp.rs:42` `handle(table, seat, ...)` | confirmed (inference: HTTP layer derives `seat` from validated token + URL path `engine.rs:428`) |
| GF10 | terms undefined in element | `element.md:52` "R3 is the third topic"; `:62` "floor"; `:20` "accolades"; `:19-20` "upstream.system.reputation" | confirmed |
| GF10 | `R{n}-` is a message-id prefix | `engine.rs:370` `format!("R{}-", self.topic_index)` | confirmed (decision wording "archive's numbering" is loose) |
| GF11 | `Intent: send` undefined | `element.md:16,19,20` all tagged `send`; `element.md:3` defines the map but not `Intent` | confirmed (field undefined) |
| GF11 | "send" is defensible, not wrong | `engine.rs:977-979` config sent in session; `engine.rs:207-209` `send(Command::...)` | qualified |
| GF12 | unnumbered reference | `element.md:29` "4 session/new..." vs `:30` "ACP v2 workspace/tool distinction" (no number) | confirmed |
| GF12 | TRACEABILITY I-3/I-4 unverifiable from bundle | `element.md:81`; `engine.rs:3-4` attests `docs/TRACEABILITY.md` exists with R/D/O prefix scheme, but file not provided -> citation is attested, not bogus; items not quoted | qualified (SpinedSolid addendum pt.2) |
| GF12 | undefined `I` prefix | `element.md:81` "owner decisions ... (TRACEABILITY I-3, I-4)" vs `engine.rs:3-4` "O = an owner decision" — `I` is not in the attested R/D/O scheme | confirmed (new, not in findings or addendum) |
| GF12 | `by: Claude` vs open owner question | `element.md:50` `"by": "Claude"`; `:69` RT-G15 "owner disposition pending"; `:85` "Whether the feedback tool stays is open with the owner" | confirmed unclear status |

## New inconsistency surfaced (not among GF1–GF12)

`element.md:40` owner statement: *"We'll prompt who should use this, let the
agents organize, and give them the feedback tool."* — this **endorses** the
feedback tool. But:
- `element.md:85` elephant.gaps: "Whether the feedback tool stays is open with
  the owner."
- `element.md:69` RT-G15: "active, owner disposition pending".

All three cannot be current at once. The resolution of GF12 (and GF5) should
reconcile them: either the owner statement settles the question (so the "open"
gap and RT-G15's disposition must be marked resolved), or the owner statement is
superseded and should be annotated as such. This is a concrete, inspectable
contradiction in the description that the reviewers did not name verbatim.

## Other cross-cutting notes

- `engine.rs:100` `pub tools: bool` on `Seat`, set from `offered` at
  `engine.rs:827` and published in `SeatReady` (`engine.rs:831`): the engine
  already exposes per-seat tool availability, which supports the description fix
  for GF1.
- `mcp.rs:18,23` tool descriptions are the only place "0-5" and "turn ends"
  appear; they are code, not `element.md`. GF5's "0-5" mismatch is therefore an
  internal code/description inconsistency, while GF4's "turn ends" is a detail
  present in code but missing from the element decision.
- `engine.rs:3-4` header: "Every rule here traces to `docs/TRACEABILITY.md`
  (R = README.md, D = the ACP integration design, O = an owner decision)". This
  is the key for making `element.md:81`'s "I-3, I-4" locatable (GF12). Two
  consequences: (a) the TRACEABILITY citation is attested as a real repo doc, so
  GF12's "cannot be located" is really "not included in the review bundle and
  the items are not quoted" — do not invent their content (SpinedSolid addendum
  pt.2); (b) the elephant tags these "owner decisions" with an `I` prefix while
  the attested scheme uses `O` for owner decisions — an undefined prefix that
  should be reconciled. The project does cite numbered sections elsewhere
  (e.g. "D §6" at `engine.rs:7`), which supports GF12's point that the
  unnumbered "ACP v2 workspace/tool distinction" reference should get a § number.
- SpinedSolid's addendum self-corrects a *prior draft* of `resolution.md` that
  defined "floor" as only a pending JEV verdict. The `resolution.md` written by
  SecretBunker does not contain that error: GF7 already separates the poll
  refusal from the floor/verdict deferral, and GF10 lists "floor" as an
  undefined term. The addendum's substantive contribution — the exact two-
  condition "floor free" definition — is nonetheless correct and has been
  inserted into GF7/GF10 verbatim.

## GammaIodine final adjudication — verified corrections (final round)

Re-checked against source; all four corrections hold, and `resolution.md` has
been updated accordingly.

1. **GF4 timing.** `on_tool` (`engine.rs:666-675`) sets `Working`, calls
   `release_floor` (`:673`) and `opportunity` (`:675`) on tool activity, before
   the participant's eventual finished contribution. So a pending advance can
   apply *before* a working participant completes, as well as being delayed by
   verdict/hold/seating/rating (`:495-524`). "Applied at the end of the current
   turn" is inaccurate; `mcp.rs:18`'s "Takes effect when the current turn ends"
   is an enqueue acknowledgement, not a completion guarantee. Corrected in GF4.
2. **A2 reachable case.** `step()` sets `topic_due` at `:517` and checks it at
   `:520` in the same synchronous function — no command-processing point in
   between — so a settings command cannot intervene in that exact sequence.
   The reachable silent-clear case is a quiet-rounds `topic_due` (`:655`)
   deferred behind `floor`/`judging_floor` (`:511` returns) then cleared by a
   settings command (`settings_changed :924`), which still publishes
   `SettingsChanged` (`:927`). Added to cross-cutting item 6.
3. **A3 "no audit record" overclaims.** Both `open_session` and
   `resume_session` return `offered` from `start_seat` (`:996`) through
   `Internal::SeatStarted`, and `SeatReady { ..., tools, ... }` is published at
   `engine.rs:821-831` on every start. Cross-table flips are real and belong in
   the description, but a once-per-start event does carry current state.
   Qualified in cross-cutting item 6.
4. **GF12 chronology.** The owner statement (`element.md:40`, 2026-11-05)
   endorses giving the feedback tool but does not settle RT-G15's exact-one-
   other-participant gate, and does not prove the 2026-11-07 retention question
   is resolved. My "cannot all be current / contradiction" claim was too strong;
   softened to a chronology note that keeps implementation distinct from
   pending disposition. Corrected in GF12 and cross-cutting item 2.

Also adopted: rating validation is a warranted boundary/data-integrity fix (not
a forbidden role/flow gate); the "Sent your feedback" text acknowledges a
successful enqueue, so a loud notice for unknown senders is optional, not a
truthfulness defect; "matches 0 other participants" is a true count, not false
text; first-request-wins would need enforcement in the serialized engine, not a
read-only `TableHandle` accessor (two callers can both observe an empty slot).
`start_polling`, `change_topic`, `start_rating` are called but not defined in the
two supplied files, and the web crate is absent — findings resting on those
sites remain plausible but unverified.
