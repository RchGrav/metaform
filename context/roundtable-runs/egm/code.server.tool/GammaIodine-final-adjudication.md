# GammaIodine — final adjudication of disputed points

This qualifies the shared `resolution.md` using only the supplied `mcp.rs` and `engine.rs`. Observing a behavior does not by itself prove a missing requirement.

## GF4 / A1: keep replacement policy, correct the timing promise

A later blank-topic request can replace a pending explicit topic with a poll request (`engine.rs:879,517`). That is a concrete example of last-request-wins, including replacement by a different action. Blank already means “poll,” not “no-op” (`mcp.rs:76-79`). Neither the owner statement nor the decision requires first-request-wins. Document this behavior; a displacement notice is an optional improvement. Calling a poll a “downgrade” adds an unsupported preference.

The existing “when the current turn ends” wording does need a code correction. Tool activity changes the floor holder to `Working` and releases the floor before its eventual completed contribution (`engine.rs:666-674`). A pending advance can therefore apply before that participant finishes, as well as being delayed by a pending verdict, hold, seating or rating (`engine.rs:495-524`). Say “requested for application when the discussion floor and pending verdict clear, subject to table state.” Do not repeat “applied at the end of the current turn” as an accurate implementation description. A successful enqueue is a submission acknowledgement, not a completion guarantee.

If first-request-wins is later selected, a read-only handle accessor is not enough: two callers can both observe an empty pending slot before enqueueing. Enforce any such policy in the serialized engine; authoritative immediate results require an acknowledgement or atomic reservation design.

## GF3/GF8 / A2: silent clearing is real; “no event” and the proposed interleaving are too broad

`settings_changed` clears `topic_due` without a dedicated cancellation notice (`engine.rs:924`), but publishes `SettingsChanged` (`:927`). Document cancellation of deferred topic work when prerequisites disappear. A separate cancellation notice is useful but not mandated by the supplied contract.

For a key/judging command processed before deferred topic work, the flag is already cleared by `settings_changed`; it is not subsequently lost at step line 524 in that sequence. There is no await or command-processing point between setting `topic_due` for an advance at line 517 and checking it at line 520. A due flag from quiet rounds can instead remain deferred behind a floor/verdict or hold check, then be cleared by a settings command. Use that reachable case for eventual verification.

## GF1/GF9 / A3: reassessment is real; a missing resume report is not

Open and resume both reassess the launched harness's HTTP MCP capability (`engine.rs:965-980`). Both return their `offered` result through `Internal::SeatStarted`, which publishes `SeatReady { ..., session, tools, ... }` (`engine.rs:821-831`). Thus a resumed seat does get its current availability reported at this start. Cross-table changes are possible and belong in the description. No permanent per-identity capability guarantee or separate capability-delta audit requirement is supplied. The absent event consumer also prevents conclusions about durable audit storage. A once-per-start event containing current state does not establish “no audit record of the flip.”

## GF5: validate ratings; do not misclassify correct acknowledgements or counts

Require executable validation of the four optional categories as integers 0–5, optional boolean bonus and optional string note, required string participant, and rejection of unknown fields. Mirror those checks in the advertised schema; a schema alone does not validate the raw handler.

The unknown-sender command drop exists (`engine.rs:886`), but “Sent your feedback … to the table” follows a successful enqueue (`mcp.rs:98-99`) and does not claim that recording succeeded. A diagnostic is useful; an immediate authoritative recorded/not-recorded response requires engine acknowledgement. Likewise, “matches 0 other participants” is a true count, not false text. Zero/multiple target matching must remain documented; rewording zero alone is cosmetic.

## GF11/GF12: preserve uncertainty rather than infer authority

GF11's direction is undefined in the supplied map. A provider-sends reading is plausible; a claim that a wanting-party-sends convention is established is not supported here. State the concrete configuration flow as engine/tools provider → agent client and check shared conventions before changing the tag.

For GF12, the dated owner statement endorses giving agents feedback, but does not settle RT-G15's exact-one-other-participant gate. Nor does a November 5 statement prove that the November 7 account's retention question is resolved. Keep the current implementation and pending dispositions distinct, and reconcile chronology against the actual owner record. Do not mark the gate approved, the gap resolved, or the earlier statement superseded solely by inference. A source comment referencing `docs/TRACEABILITY.md` establishes the intended path, not independently verified existence or contents of the omitted document.

## Result

The twelve findings retain the decisions in the shared resolution subject to these qualifications. Required code changes are feedback validation and truthful advance/topics-disabled wording; most other changes clarify the description. A1–A3 add useful examples and lifecycle details, but do not establish mandatory first-request-wins, cancellation-notice or cross-table audit features. No source implementation was changed.
