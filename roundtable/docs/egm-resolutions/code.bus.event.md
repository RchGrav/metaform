# Event bus review resolutions

Author: LethalCohort

Scope: decisions from `element.md` and the supplied `source/crates/bus/src/lib.rs`. This resolves all twelve findings; it does not implement the proposed changes. The snapshot contains no engine, turn module, test source, or Cargo manifest. References to those files in the review are evidence reported by the reviewer, not independently verified here. The description's historical test results have not been rerun.

## GF1 — Accept: correct the description

`subscribe::<E>()` registers by `TypeId` (lib.rs:149–154), and `publish` sends only to the matching typed registry entry (138–141). Taps receive every published type (142–145).

Replace `elephant.built` with: “Each bus instance assigns publications a global sequence number. A typed subscription receives subsequent events of its own type in that order; a tap receives subsequent events of every type in that order. Publication does not wait for consumers to read.” Bus clones share the same instance and sequence; independently constructed buses do not. Typed subscriptions can have gaps in sequence numbers. Retain type filtering in the code: it is intentional and matches the decision. Every-event coverage also requires a receiver to have registered before publication; there is no replay.

The same overstatement must also be corrected in the crate's own module-level rustdoc at **lib.rs:10–11**: “every subscriber receives events in sequence order, whatever their type.” That sentence is the literal origin of the GF1/GF7 wording and would mislead anyone reading the crate source directly. Rewrite it to: “Every event gets a sequence number; a typed subscriber receives its own event type in that order, and a tap receives every type in that order.” This is a rustdoc edit alongside the `element.md` edit, so the fix is consistent at both the crate and the map.

## GF2 — Accept the scope problem; integration details remain unverified

The library can transport any type implementing `Event`. That capability does not establish that chair commands or JEV results actually pass through it. Neither the cited engine/turn code nor integration tests are supplied, so the specific mpsc routes cannot be independently confirmed from this snapshot.

Change the description now to distinguish the owner's event-driven requirement from verified bus adoption. Narrow the manager's current integration claim to verified traffic, and explicitly record chair-command and JEV-result routing as requiring integration verification. If the cited routes are confirmed, record them as a gap against rule 0, which expressly requires those messages to be published as events. An awaited mpsc channel satisfies the no-polling principle, but does not by itself satisfy that stronger bus-publication rule. Publishing only effects is not proof of publishing the command or result itself.

To fulfill the stronger rule, the engine/turn integration must publish command and evaluation-result events and consume them through subscriptions, with an explicit single handler where these represent commands; alternatively, retain direct request channels and publish their receipt/results for observers if the owner clarifies that the bus requirement concerns observability. Verify ordering and exactly-once command execution at that boundary. No change to this generic bus is demonstrated as necessary. Do not silently weaken the owner's rule merely to describe existing routing.

## GF3 — Accept: enforce name uniqueness in release builds

At lib.rs:135–136 the registry remembers the first type for a name, but only `debug_assert!` checks subsequent publications. Release builds can emit indistinguishable names for different payload types. Typed delivery remains correct because it uses `TypeId`; records identified by name become ambiguous. The uniqueness instruction exists in the `Event` rustdoc, but release behavior is not explained.

Use an unconditional assertion for the existing infallible `publish` API, before incrementing the sequence or enqueueing anything. Document that publishing a second type with an already-used name on the same bus panics. Keep the first name-to-type mapping intact. This is a programmer contract violation, not an event to enqueue under an ambiguous name. A fallible publication API could be a separate API decision, but is not needed to correct this defect. The registry can enforce uniqueness only within one bus instance, not across the entire program.

Validate with two distinct types sharing one name under both debug and release builds, and verify that the conflicting payload reaches no receiver. Also cover repeated publication of the same type/name.

**Cross-finding interaction with GF5:** the panic in the GF3 fix fires *while holding the registry `Mutex`*, which is acquired at lib.rs:132 before the name check at 135–136. A panic under `std::sync::Mutex` poisons the lock, so every later `publish`/`subscribe`/`tap` (lines 132, 152, 160) will hit `unwrap_or_else(|poisoned| poisoned.into_inner())` and silently drop the poison — the exact silent-recovery behavior GF5 documents. Thus, after one conflicting-name panic, the registry stays poisoned and the bus keeps running, masking the failure. Two consistent resolutions: (a) place the unconditional uniqueness check *before* any registry mutation (before the `seq` increment and before enqueueing) and keep the GF5 `into_inner()` recovery — the panic then aborts before the registry is changed, so recovery is safe and no ambiguous event is enqueued; or (b) report the conflict without panicking under the lock (e.g. a fallible API). Option (a) is the minimal fix and matches the resolution's "before incrementing the sequence" guidance, but the resolution must state that the panic is expected to poison the lock and that recovery is the designed handling rather than a silent side effect.

## GF4 — Partly accept: add a compact API contract to the map

The map omits useful API details, but “undocumented” overstates the problem: the source already documents the trait, envelope fields, delivery type, receiver lifetime, and several method contracts. This is a discoverability gap in the description, not a missing implementation. Add an API summary with a link to the crate rustdoc:

- `Event: Any + Send + Sync + Debug + Serialize` requires a stable `NAME`; `Any` implies a `'static` event type. Describe the uniqueness enforcement selected in GF3.
- `Bus::new()`/`Default` make independent buses; cloning shares the registry. `publish(E)` returns a sequence number, starting at 1 per instance.
- `subscribe::<E>()` returns `Subscription<E>` yielding `Delivery<E> { seq, at, event: Arc<E> }`. `tap()` returns an untyped `Tap` yielding `Envelope` for every type.
- An envelope exposes `seq`, `at: SystemTime`, and `name`; `downcast::<E>()` returns `Option<&E>`, and `to_json()` is fallible and lazy. State the corrected caching contract from GF6.
- Both receiver types implement `futures::Stream` and asynchronous `recv()`. Registration takes effect under the same registry mutex as publication. Concurrent registration/publication is ordered by lock acquisition.
- Receivers deliver queued items before returning `None` after the last bus clone drops. An idle live bus does not terminate its streams. Dropping a receiver discards its unread queue; its sender is pruned when a later relevant publication attempts delivery. A typed sender may remain registered until its type is published again.

The timestamp is sampled before acquiring the mutex (127–132), so sequence number, rather than wall-clock timestamp, defines publication order. No separate API implementation change is needed for GF4.

## GF5 — Accept the qualification; retain the mutex design

`publish`, `subscribe`, and `tap` use a blocking `std::sync::Mutex` (132, 152, 160). Therefore “publishing never blocks” is too broad. Unbounded queues eliminate waiting for receiver capacity or consumption; they do not make publication lock-free or give it a latency bound. Lock duration includes delivery to all relevant queues and grows with fan-out, so even “briefly” is not a guarantee.

Replace the unconditional wording in the decision, `elephant.built`, and crate-level rustdoc with: “Publication does not wait for subscribers to read or free queue capacity. Publication and registration serialize under a shared mutex.” Preserve the mutex because it orders numbering and enqueueing consistently.

Document the existing poison policy: a poisoned registry lock is recovered with `into_inner()`, without reporting the poison. Recovery is not rollback and does not establish that a panicking publication reached all receivers. This finding alone does not justify changing that policy, but delivery guarantees should be stated for normal successful operation.

## GF6 — Accept: fix failed-serialization caching

The decision's “lazy JSON” is accurate, but `Envelope::to_json` rustdoc promises serialization once per event (52–53), which is false on failure. The first call initializes the cache with `None` after a failed attempt, then immediately calls the serializer again (55–58). Every later call serializes again. For an always-failing serializer, N completed calls therefore make N+1 serialization attempts, not N. Even if a later attempt succeeds, that success is never cached because the `OnceLock` is already initialized to `None`.

Cache the first outcome, success or failure, in the shared once cell and return that outcome on subsequent calls. Keep `to_json()` fallible. Since `serde_json::Error` is not directly cloneable, the implementation must deliberately choose a shareable error representation or reconstruct an appropriate public error; do not propose simply cloning `Result<Value, serde_json::Error>`. Document any loss of error detail if reconstruction is chosen. This preserves lazy, shared, one-attempt serialization and avoids repeated work across taps for malformed payloads.

Validate with a custom failing `Serialize` implementation and a call counter: repeated and concurrent calls through cloned envelopes must invoke serialization once and return errors. Retain a success-cache test. This is a serialization-path fix, not a change to typed event delivery.

## GF7 — Accept; duplicate of GF1

The contradiction is real for the same reasons as GF1. Apply GF1's replacement once, and record GF7 as resolved by that same change. Do not change typed subscribers to receive unrelated types or count this as a second independent implementation defect.

## GF8 — Accept as a context gap, not an established major code defect

The description repeatedly uses the chassis to motivate portability without explaining the term. Add: “The chassis is the intended future host for these reusable components. This bus is designed to be adopted there without Roundtable-specific dependencies.” Describe the Bevy bridge as intended integration, not functionality implemented by this file. The implementation uses futures channels and has no explicit async-runtime API dependency; a complete dependency audit would also need the missing manifest.

No chassis implementation or Bevy bridge should be invented to resolve a terminology finding. Link to the authoritative chassis description if available; the local evidence does not establish further chassis requirements.

## GF9 — Accept: define local terms and summarize the referenced requirement

Add a short glossary: ACP means Agent Client Protocol; ACP autoselection means choosing an ACP implementation automatically; chair commands are control instructions to the discussion coordinator; JEV results are the message evaluator's returned judgments; “never-halt” here means a slow or unread receiver must not force publishers to wait for it. Confirm project-specific expansions and autoselection behavior against authoritative documentation before claiming more detail. The supplied material does not establish the expansion of JEV, so do not invent one.

Summarize the requirement attributed to Integration Design §6 in the map itself: event-driven state propagation and ordered event delivery, using the independently supported local owner statement and decision. Explicitly mark the external section as unavailable for verification here, rather than claiming this summary reproduces its contents. Add a resolvable link when that document is available. Preserve the owner's quotation; explain terms alongside it instead of rewriting historical statements. No code change follows from unexplained terminology.

## GF10 — Accept as a map clarification

Define “subscriber” as the general receiver category. A typed subscription is created by `Bus::subscribe::<E>()` and yields that event type wrapped in `Delivery<E>`. A tap is created by `Bus::tap()` and is untyped: it yields every subsequent published event as an `Envelope`, which carries ordering/time/name metadata and a shared payload accessible through JSON or a checked downcast.

These distinctions already appear in crate rustdoc (15–16, 123, 149, 157); copy the concise contract into the description or refer to GF4's API summary. No new tap API is required.

## GF11 — Accept the missing startup contract; actual loss is unproven

The library supplies no replay and gives no priority to a recording tap. A tap created after an event is published cannot recover it (157–162). The recorder startup path is absent, so neither an existing guarantee nor an actual startup-loss defect can be established here.

Add: “A complete record requires the recording tap to be registered before any event producers start. Its startup ordering is not verified in this snapshot.” If a complete session record is required, the integrating startup code must create the tap synchronously before exposing bus clones to producers, retain it throughout the session, and drain its backlog during shutdown. Add an integration check that the first session event reaches the recorder. A running recorder task is not required before publication; registration is sufficient because its queue buffers unread events. Replay is not necessary to meet this startup contract.

**Recorder order must be `seq`, not `at`:** because `Envelope::at` is sampled before the mutex while `seq` is assigned under it (lib.rs:129 vs 133–134), two events can have `at` ordered opposite to their `seq` (A4). The discussion record therefore must be keyed by `seq` (the bus's global order), never sorted by `at`; otherwise two near-simultaneous publications can appear reordered in the record. Make this explicit in the GF11 startup contract and add an integration assertion that record order equals `seq` order.

## GF12 — Accept as a schema-documentation gap; do not guess schema meanings

The supplied map does not define `role: SE`, `name_length`, or the intent enumeration. Link the shared functional-map schema and give brief field definitions there or beside the properties. Keep `SE` unexpanded until the schema establishes its meaning; likewise, do not declare that `name_length` counts words just because the current name has two words.

The local arrows do establish perspective for these wants: `send` means the named consumer supplies events to the bus, and `send_receive` means it both supplies and consumes them. Document that perspective, then confirm the formal intent enumeration against the schema. This affects reader comprehension, not bus behavior; it requires no code change.

## Disposition

The demonstrated behavioral fixes are release-build name validation (GF3) and one-attempt serialization caching (GF6). GF1/GF7 and GF5 require precise delivery and blocking language. GF4 and GF8–GF12 require API/context documentation and, for GF11, an explicit integration precondition. GF2 needs an honest description of the evidence gap and integration reconciliation against the owner's rule. Missing source prevents claiming the external routing and recorder startup questions are already verified or fixed.

## Addendum — second review (DreadedWisdom)

Full independent analysis and a citation audit are in `DreadedWisdom-decisions.md`. Every `lib.rs`
line reference in GF1, GF3, GF4, GF5, GF6 and GF10 was checked and is accurate; GF1's `tests/bus.rs`
citation and all of GF2's `engine.rs`/`turn.rs` citations are unverifiable because the snapshot
contains only `source/crates/bus/src/lib.rs`. GF2 is the only finding whose entire factual basis
lies outside the supplied source.

Four corrections to the resolutions above:

1. **GF2 — narrow, do not accept as a bus finding.** The element is explicitly a reusable,
   Roundtable-independent library (`rules[1]`, owner statement "standalone tool", `package`
   "reusable"). A bus that carried chair-command or JEV types would violate that rule; the bus
   transports arbitrary `Event` types, and routing is a producer decision in `engine.rs`. This
   document already concedes no generic bus change is necessary, so accepting GF2 as a Blocker on
   this part mislabels a consumer wiring question. The engine redesign ("publish command and
   evaluation-result events and consume them through subscriptions", verify ordering and
   exactly-once execution) belongs in the `code.manager.chat.group`/engine element's findings,
   not here. An awaited mpsc channel is not polling, so the owner's "never poll" principle may
   already hold. For this element: add one scoping sentence to `rules[0]` and to that want — the
   bus is *capable* of carrying these as events; whether a producer publishes them is that
   producer's concern — and record GF2 as forwarded with evidence unverified. Preserve the owner's
   quotation and `rules[0]`; do not weaken them, and do not import an engine redesign here.

2. **GF1/GF7 — the code's own rustdoc has the same defect.** `lib.rs:10–11` says "**One global
   order.** Every event gets a sequence number, and every subscriber receives events in sequence
   order, whatever their type." "whatever their type" reads as a subscriber receiving all types.
   Rewording only `element.md` leaves the contradiction alive in the crate documentation. Add a
   one-line rustdoc fix: "Every event gets one global sequence number. A typed subscription sees
   its own events in that order; a tap sees all events in that order." This is the concrete missing
   step for GF1/GF7.

3. **GF3 — make the pre-mutation placement explicit as a GF5 interaction.** A panic while holding
   the registry `Mutex` poisons it, and `publish` recovers poison silently via `into_inner()`
   (132, also 152 and 160). If the unconditional assertion fired after `registry.seq += 1` (133),
   the recovered registry would skip a sequence number and some queues would be missing an event
   with no signal. Checking uniqueness *before* the increment and before any enqueueing leaves the
   registry untouched. State this reason, not just the placement. Note also that a panic is not
   backpressure, so it does not violate "publishing never blocks".

4. **Group the editorial fixes.** GF4, GF8, GF9, GF10 and GF12 are all "the map uses undefined
   terms / has no API summary" findings and are best resolved by one edit: a "Terms & external
   references" glossary plus a compact "API & semantics" section. Treating them as five separate
   edits invites a repetitive `element.md`. GF12 in particular is a *schema* field set
   (`role`, `name_length`, `Intent`); its definition belongs in the shared functional-map schema,
   not duplicated per element — link it there. GF11's fix is a description note about tap
   registration ordering; adding replay would contradict `elephant.gaps` ("No stored log or
   replay") and the `decisions` memory tradeoff, so replay should not be proposed.

Net effect on disposition: GF3 is the only change that alters runtime behavior in all builds; GF6
is either an optional serialization-cache fix or a rustdoc reword (the `decisions` "lazy JSON" phrasing
is itself accurate, so the finding's cited target is wrong); everything else is description or
single-line rustdoc wording.

## Round 2 additions (RagingTyphon) — corrections to the resolution above

These are verified against `source/crates/bus/src/lib.rs`; they amend, not replace, the decisions above.

### A1. GF5: the lock is released before anyone waits on a receiver — "never blocks" is closer to true than the resolution says

The GF5 section says lock duration "includes delivery to all relevant queues and grows with fan-out," which reads as if the lock is held while a queue operation could wait. It is not: both sends are `unbounded_send` (lib.rs:140, 144), and `futures` `unbounded_send` on an unbounded channel neither yields nor blocks — it only returns `Err` on a disconnected receiver, which `retain` then prunes. So the real inverse of "never blocks" is *memory*, not latency: an unread receiver grows its backlog without bound until dropped (the decision's own tradeoff). Keep the resolution's recommended reword ("does not wait for subscribers to read or free queue capacity"), but drop "grows with fan-out" as a latency claim; the honest statement is that the mutex is held for O(subscribers) non-blocking enqueues plus clones, and publication is not lock-free.

### A2. GF5/poison: `into_inner()` recovery actually violates the ordering guarantee the mutex exists for

`publish` computes `registry.seq += 1` under the lock (133). If a thread panics inside the critical section (e.g. the GF3 `debug_assert!` firing, or an allocation aborting mid-`retain`), the lock is poisoned and the next publisher recovers with `into_inner()` (132) and continues numbering. That is fine for the counter, but the admitted reason for the mutex is "numbering and enqueueing together, so ... every queue receives events in sequence order" (130–131). A panic between assigning `seq` and finishing the `retain` loops (140–144) can leave one queue with seq N-1 and another without it yet, and the recovered publisher then hands out N+1 — so "one consistent order" survives only if panic-in-`publish` cannot happen. Two options, pick one deliberately: (i) keep recovery but document that delivery/ordering guarantees hold only for `publish` calls that do not panic, or (ii) treat a poisoned registry as fatal. Either way this belongs in the map's GF5 note; silence is the only wrong answer.

### A3. GF3: promoting to an unconditional assert panics *while holding* the mutex and *after* the sequence was already consumed

The GF3 fix ("unconditional assertion ... before incrementing the sequence or enqueueing anything") is the right direction, but as written the check in the current code sits *after* `seq += 1` (133–136). The corrected order must be: (1) look up the name→type map; (2) if it conflicts, release without touching `seq`, then panic (or return an error from a fallible API) — i.e. the conflict check precedes the increment and precedes any `retain`. This also avoids the A2 poisoning path for the one panic that GF3 will deliberately introduce. A `HashMap<&'static str, TypeId>` probe that has to `entry(...).or_insert` does the insert as a side effect; restructure to probe first, insert the mapping only after the conflict check passes, so a rejected publication leaves the registry unchanged (the existing "keep the first name-to-type mapping intact" note in GF3 already wants this — this makes it literal).

### A4. GF4: one API fact is missing and one is mis-stated

- Missing: `Envelope::downcast` (`lib.rs:63–65`) only returns the payload when the envelope's concrete type is `E`; a tap that downcasts to the wrong type gets `None`, silently. Combined with GF3's release-build name ambiguity (two types, one `NAME`), a tap that keys on `name` and downcasts to the expected type can also get `None` — worth one line in the map so readers do not assume `name` ⇒ successful `downcast`.
- Mis-stated: the resolution's GF4 bullet "Concurrent registration/publication is ordered by lock acquisition" is true, but the sequence number is assigned under that lock (133–134) while `at` is sampled *before* it (129). Two publishers that sample `at` in one order can receive sequence numbers in the opposite order. The resolution already notes "sequence number, rather than wall-clock timestamp, defines publication order" — good; but it should also warn that `at` is not monotonic with `seq`, so any recorder that sorts by `at` can reorder relative to `seq`.

### Net effect on the disposition

Unchanged: GF3 and GF6 remain the behavioral fixes; GF1/GF7/GF5 are wording; GF4/GF8–GF12 are documentation; GF2 is unverifiable here. What changes is the *substance* of two of them — GF3's assertion must move before the `seq` increment (A3), and GF5 must stop implying lock-held-while-waiting and instead state the memory/poison caveats (A1, A2).

## Round 2, part 2 (DreadedWisdom) — agreement, one sharpening, one unresolved disagreement

I checked A1–A4 against the code and agree with all four. Two additions:

**A2/A3 sharpening: the poisoning path is already live, not hypothetical.** The current
`debug_assert!(known == TypeId::of::<E>())` at `lib.rs:136` fires **in debug builds while the
registry mutex is held**, and it already sits *after* `registry.seq += 1` (133). So a duplicate
`NAME` in a debug build today panics mid-critical-section, poisons the lock, and the next
`publish` recovers via `into_inner()` (132) from a registry that has already consumed a sequence
number. The GF3 fix does not *introduce* this risk; it makes it deterministic in release builds
too. That is the strongest argument for A3's ordering (probe the name map first, insert the
mapping only after the conflict check passes, increment `seq` last) and for A2's "guarantees hold
only for non-panicking publishes" note. Also note the two error paths differ: `Envelope::to_json`
(GF6) runs on a receiver, outside the lock, so a serialization failure can never poison the
registry — only `publish` can.

**A1 clarification, not a correction.** LethalCohort's "lock duration grows with fan-out" is a
true statement about *hold time* (O(subscribers) clones plus `unbounded_send` calls, 139–144),
not a claim that a queue operation waits. RagingTyphon's "drop it as a latency claim" is right
only if a reader mistakes hold time for backpressure. The accurate merge of both is: the mutex is
held for O(subscribers) non-blocking enqueues; publication is not lock-free and has no latency
bound, but never waits on receiver capacity or consumption. My own GF5 wording in the addendum
above is consistent with this.

**Unresolved: GF2.** RagingTyphon's additions address GF3/GF4/GF5 but leave GF2 as "unverifiable
here" while the main resolution still "accepts the scope problem" and prescribes engine-side
redesign. My position stands: GF2 is **not a finding against the event bus element** and should
not be recorded as an accepted Blocker on this part. The bus is deliberately Roundtable-
independent (`rules[1]`, owner statement, `package`); it has no chair-command or JEV types by
design and carries arbitrary `Event` types. The document already concedes no generic bus change
is needed, so the correct resolution for *this* element is (a) one scoping sentence in `rules[0]`
and the `code.manager.chat.group` want — the bus provides the capability, producer wiring is the
producer's concern — and (b) forward GF2, with its unverified evidence, to the engine/chat.group
element. Preserve the owner's quotation and `rules[0]`; do not weaken them and do not carry an
engine redesign in this document. This is the one decision the group should still settle.

**Still unclaimed: the `lib.rs:10–11` rustdoc fix (GF1/GF7).** Neither addendum picks up the
crate-level "every subscriber receives events in sequence order, whatever their type" line. Until
that one line is reworded, the contradiction GF1 and GF7 identify survives in the code's own
documentation even after `element.md` is corrected. It is a single-line change and belongs in the
final edit list.

**Editorial grouping (addendum point 4) also still stands:** GF4, GF8, GF9, GF10 and GF12 are one
glossary + API-section edit, with GF12's schema fields defined in the shared map schema rather
than duplicated here.
