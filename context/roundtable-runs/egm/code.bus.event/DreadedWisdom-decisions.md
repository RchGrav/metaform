# DreadedWisdom — independent decisions on the `code.bus.event` review findings

Scope of evidence: `element.md` plus `source/crates/bus/src/lib.rs` (212 lines). The `source/`
folder contains **only** this one file. `crates/roundtable/src/engine.rs`, `turn.rs`,
`crates/bus/tests/bus.rs` and any Cargo manifest are **not** in the snapshot. Findings that cite
those paths are reports of reviewer evidence, not verifiable here.

## Citation audit (establishes how much of the review is checkable)

Every line reference into `lib.rs` is accurate:

| Finding | Cited | Verified |
|---|---|---|
| GF1 | 138–141 typed send, 142–145 tap send, 149–155 `subscribe` | yes |
| GF3 | 135–136 `names.entry` + `debug_assert!` | yes |
| GF4 | 34–36 `Event`, 39–66 `Envelope`, 94–99 `Delivery`, 132 lock, 140/144 `retain`, 166/194 stream-end doc | yes |
| GF5 | 132 `lock()` | yes |
| GF6 | 55–59 `to_json` | yes |
| GF10 | 15–16, 149, 157 rustdoc | yes |

GF1 also cites `tests/bus.rs:22–36` and GF2 cites `engine.rs`/`turn.rs` **exclusively**; none of
those files are present. **GF2 is the only finding whose entire factual basis is unverifiable in
this snapshot.** This matters for how it is resolved (below).

## Decisions

### GF1 — RIGHT (description defect, not a code defect). Fix `elephant.built`.
`subscribe::<E>()` registers a sender under `TypeId::of::<E>()` (149–154) and `publish` enqueues
only into `registry.typed[TypeId::of::<E>()]` (138–141); the receiver then does a checked downcast
with `expect("subscription received a foreign event type")` (188), so foreign types are impossible
by construction. `tap()` registers in `registry.taps` and receives `Envelope` for every type
(142–145). `elephant.built`'s "every subscriber sees every event" is therefore false for typed
subscriptions. The `decisions` and `tests` layers are already correct ("typed delivery only of own
type" vs "tap sees all types"), so the code needs no change. Rewrite `elephant.built` to: typed
subscriptions get their own type in global order, taps get every type in global order, and both
only from the moment they register (no replay).

**Additional fix the current resolution.md misses:** the same looseness is in the code's own
crate-level rustdoc, `lib.rs:10–11`: "**One global order.** Every event gets a sequence number, and
every subscriber receives events in sequence order, whatever their type." "whatever their type"
reads as "a subscriber receives events of all types". Correcting only `element.md` leaves the
contradiction alive in `lib.rs`. Reword to: "Every event gets one global sequence number. A typed
subscription sees its own events in that order; a tap sees all events in that order." This is a
one-line code-doc change and is the concrete missing step for GF1/GF7.

### GF2 — NOT RIGHT as a finding against the event bus element. Do not accept it as a bus Blocker.
This is my substantive disagreement with the existing resolution (which "accepts the scope
problem" and then prescribes engine-side redesign).

- The element is explicitly a **reusable, Roundtable-independent library**: `package` says
  "reusable; basis for the chassis", the owner says "this is a standalone tool", `rules[1]` says
  "The bus has no dependency on Roundtable", and `decisions` says no async-runtime dependency.
  A bus that had chair-command or JEV types would *violate* that rule. The bus carries arbitrary
  `Event` types; whether a producer routes a command through it is that producer's decision, in
  `crates/roundtable/src/engine.rs`.
- The bus code therefore **cannot** be wrong here, and the existing resolution concedes this
  ("No change to this generic bus is demonstrated as necessary"). Given that, accepting GF2 as a
  *Blocker on this part* mislabels a consumer-side wiring question as a defect in this part.
- The engine/turn files are absent, so the mpsc claim is unverifiable; prescribing "publish command
  and evaluation-result events and consume them through subscriptions, verify ordering and
  exactly-once command execution" is a design change to `code.manager.chat.group`/engine, and it
  belongs in **that element's** findings, not in the bus element's resolution document.
- An awaited mpsc channel is **not polling**, so the owner's "never poll what can surface as an
  event" principle may already be satisfied even if commands bypass this bus. The stronger reading
  of `rules[0]` (all named messages *are published as events*) is an architectural aspiration about
  the whole program, not a contract the bus library can enforce or guarantee.

Resolution for **this** element, kept minimal: add one scoping sentence to `rules[0]` and to the
`code.manager.chat.group` want — "the bus is capable of carrying these as events; whether a given
producer publishes them is that producer's concern" — and record GF2 as **forwarded to the
engine/chat.group element** with its evidence unverified. Do not weaken the owner's quotation, do
not delete `rules[0]`, and do not import an engine redesign into this document. If the engine
routes are later confirmed, the gap is logged there against `rules[0]`, not here.

### GF3 — RIGHT (Major). One real code change, plus a documentation change.
In release builds `debug_assert!` (136) is compiled out, and `names.entry(...).or_insert_with(...)`
keeps the **first** type for a name, so a second type under the same `NAME` is silently accepted.
`names` is otherwise never read — it is a debug-only guard. Records keyed by `name` become
ambiguous; typed delivery is unaffected because it uses `TypeId`. The *requirement* is documented
(`Event` rustdoc 32–33 "Keep it unique across the program"; Registry comment 106 "a name must
identify one type in records") but the **debug-only enforcement and release consequence are not** —
so "Undocumented" is half right.

Fix: replace `debug_assert!` with an unconditional check that fires in all builds, and **move it
before `registry.seq += 1` (133) and before any enqueueing**. The pre-mutation placement is
important and interacts with GF5: a panic while holding the `Mutex` poisons it, and `publish`
recovers poison silently via `into_inner()` (132). If the assertion fired after the sequence was
incremented, the recovered registry would skip a sequence number and some queues would be missing
an event with no signal. Panicking before mutation leaves the registry untouched. This is a
programmer-contract violation (like the downcast `expect`), not a runtime condition, so failing
loud is consistent with the design and does not violate "publishing never blocks" (a panic is not
backpressure). Document in `element.md` and rustdoc that a duplicate name on one bus panics, and
note the enforcement is **per bus instance**, not global. Add a test with two types sharing one
`NAME` under debug and release, asserting no conflicting payload reaches any receiver.

### GF4 — PARTLY RIGHT. Description gap; "undocumented" is wrong.
`element.md` has no API section, so a newcomer to the map cannot learn the public surface. But
`lib.rs` has rustdoc on essentially every item listed: `Event` bounds (30–36), `Envelope`
fields and `to_json`/`downcast` (38–65), `Delivery` (93–99), `publish`/`subscribe`/`tap`
(123–163), `recv` and `Stream` (172–211), "starting at 1" (41), dropped-receiver pruning (126),
and "Ends only when every `Bus` clone is dropped" (166, 194). So the code is documented; the
*map* is not. Accept as a discoverability gap (Major is defensible for a library that is the
"basis for the chassis"), resolved by adding a compact "API & semantics" section to `element.md`
plus a pointer to the crate rustdoc. No code change. This is the same class of fix as GF10 — merge
them into one section rather than two.

### GF5 — RIGHT as a Nit precision issue, but it does NOT contradict the decision.
`publish` (132), `subscribe` (152) and `tap` (160) all take `std::sync::Mutex`, so publication can
wait on other publishers and on registration. The `decisions` layer already says the sequence is
"assigned under the same lock as enqueueing", and the crate rustdoc scopes "Publishing never
blocks" to "A slow or stalled subscriber cannot stop a publisher" (7–9) — i.e. subscriber
backpressure, not lock-freedom. So there is no contradiction; there is an absolute-sounding
phrase worth qualifying. Fix is description-only: "Publication does not wait for subscribers to
read or free queue capacity; publication and registration serialize under a shared mutex." Note
that lock hold time grows with fan-out (delivery to all queues happens under the lock), so even
"briefly" is not a bound — worth saying. Also document the silent poison recovery at 132/152/160
and its real consequence (a panic mid-publish is not rolled back; the recovered registry may have
an inconsistent view of which queues received the event). No code change needed for GF5 alone.

### GF6 — RIGHT as a Nit, but the finding targets the wrong layer.
Behavior: `get_or_init(|| self.payload.to_json().ok())` (55) stores `None` on failure and the
`None` arm calls the serializer again (58), so every subsequent `to_json()` re-serializes. The
`decisions` layer's "lazy JSON" is **accurate** (serialization is deferred to first use), so GF6's
cited target is not wrong. The false claim is the rustdoc at `lib.rs:52–53`: "Serialized once per
event, on first request, and shared by every tap that asks." That is false for failures and, on
success, `value.clone()` (57) clones the `Value` per call — "serialized once" is true,
"shared" is a shared cache with per-call clones.

Since the payload is an immutable `Arc<dyn Payload>`, a failing `Serialize` can never later
succeed, so caching the failure is strictly better than retrying. Two valid resolutions:
(a) **code** — cache the first outcome, success or failure, in the `OnceLock` (e.g. store
`Result<Value, String>` with the error stringified, or a small cloneable error type; `serde_json::Error`
is not `Clone`, so do not propose `OnceLock<Result<Value, serde_json::Error>>` without addressing
that), document any loss of error detail; or (b) **doc-only** — reword the rustdoc to "attempted
once on first request; a failed attempt is retried on each call". Prefer (a) for consistency,
but note (b) is sufficient to make the description honest. Test with a `Serialize` impl that
fails and a call counter. `element.md`'s decisions layer needs no change.

### GF7 — RIGHT; exact duplicate of GF1, same fix.
Record as resolved by GF1's single rewrite of `elephant.built` (plus the `lib.rs:10–11` rustdoc
fix). Do not count as a second defect, and do not change typed subscribers to receive unrelated
types — the `decisions` and `tests` layers already describe the intended behavior correctly.

### GF8 — RIGHT as a context gap; Major is heavy but the fix is cheap.
"chassis" appears five times (`package`, owner statement, `rules[1]`, `decisions`, `elephant.design`)
and is never defined; "Bevy" appears once. It is load-bearing for the entire portability rationale
(no Roundtable dependency, no runtime, Bevy bridge), so an undefined term genuinely weakens the
element. Fix: one sentence in `element.md` — the chassis is the intended future host for these
reusable components, and this bus is designed to be adopted there unchanged, with the Bevy bridge
described as *intended integration*, not implemented functionality. Link to the chassis element if
one exists in the map. No code change, no invented chassis implementation, no manifest-based
dependency claim (the manifest is missing).

### GF9 — RIGHT (Major). Fix together with GF8, GF10 and GF12 in one glossary.
All six terms/references are used without definition or summary in this element: ACP, ACP
autoselection, JEV, chair commands, never-halt, and `Roundtable_ACP_Integration_Design.md §6`.
Add a short "Terms & external references" section with one-line working definitions (ACP ≈ Agent
Client Protocol, the agent/host protocol producing session, tool, permission and exit events;
autoselection = choosing an ACP implementation automatically; chair commands = control
instructions to the discussion coordinator; JEV results = the evaluator's judgments on messages —
from the roundtable's own operation, messages are evaluated before reaching the group;
never-halt = a slow/unread receiver must not force publishers to wait). Do not invent an acronym
expansion for JEV. For §6, state that the document is not in this snapshot and summarize only
what is independently supported here (the owner's "never poll" quote and the ordered-delivery
decision), marking it explicitly as unverified; add a resolvable link when available. Preserve
historical quotations verbatim. No code change.

**Coordination insight:** GF8, GF9, GF10 and GF12 are all "the map uses undefined terms" findings
and GF4 is "the map has no API summary". They are one editorial edit (a glossary + API section),
not five independent fixes. Grouping them avoids a bloated, repetitive resolution and is the
fastest path to a complete `element.md`.

### GF10 — RIGHT (Nit). Root cause of GF1/GF7.
`Tap`, `Envelope` and "subscriber" are undefined in `element.md`; it never says a tap is created
by `Bus::tap()` (157), that it is **untyped** (type-erased `Arc<dyn Payload>`, 47), or that it
differs from `subscribe::<E>()`. Because the description never distinguishes the two receiver
kinds, `elephant.built`'s "every subscriber sees every event" became misleading — so fixing GF10
is what makes the GF1/GF7 fix obvious. Define: subscriber = general receiver category;
`subscribe::<E>() -> Subscription<E>` yields `Delivery<E>` of that type only; `tap() -> Tap`
yields `Envelope` for every type with `seq`/`at`/`name`, lazy JSON and checked `downcast::<E>()`.
All of this already exists in rustdoc (15–16, 149, 157). No new API.

### GF11 — RIGHT (Nit); state the consequence, do not add replay.
`elephant.gaps` says a late subscriber misses earlier events, and `decisions` says a tap serves the
discussion record. The code has no replay: `tap()` (157–162) registers a new unbounded channel at
call time, so events published before registration are gone. There is **no guarantee** in the code
that the record tap attaches first, and the description is silent. The right fix is a description
note: "A complete discussion record requires the recording tap to be registered before any
producer publishes; the bus provides no replay, so this is a startup-ordering responsibility of
the host." Registration is sufficient (the queue buffers unread events, so a drained-but-not-yet-
running recorder task is fine). Do **not** add a replay buffer/log: that contradicts the explicit
"No stored log or replay" gap and the `decisions` tradeoff (unbounded per-subscriber backlog is
already the accepted memory cost). Optionally add an integration check that the first session
event reaches the recorder. The recorder startup path is not in the snapshot, so actual loss is
unproven — say so.

### GF12 — RIGHT (Nit), lowest value; the fix is global, not per-element.
`role: SE`, `name_length: 2` and `Intent: send` / `send_receive` are undefined in `element.md`. But
these are **fields of the functional map's schema**, not properties of the event bus. Defining them
belongs in the shared map schema/legend; duplicating a schema legend into every element would be
noise. Fix: link the shared schema document and give brief field definitions there (or one line
here noting where they are defined). Keep `SE` unexpanded until the schema establishes it;
`name_length: 2` is consistent with the two words in "event bus" but should not be asserted as the
rule without the schema. The local arrows do establish perspective: `send` = the named part
supplies events to the bus, `send_receive` = it both supplies and consumes. No code change.

## Disposition (net changes proposed)

**Code — `crates/bus/src/lib.rs`:**
1. GF3: unconditional name-uniqueness check, moved before `seq += 1` and before enqueueing;
   document + test under debug and release.
2. GF6 (optional but recommended): cache the first `to_json` outcome, success or failure; else
   reword the rustdoc at 52–53.
3. GF1/GF7: reword crate rustdoc 10–11 (one line).
4. GF5: reword crate rustdoc 7–9 to scope "never blocks" (description-only wording).

**Description — `element.md`:**
- Rewrite `elephant.built` (GF1/GF7).
- Add an "API & semantics" section (GF4 + GF10, merged).
- Add a "Terms & external references" glossary (GF8 + GF9 + GF12, merged; GF12 points to the
  shared schema rather than redefining it).
- Scope `rules[0]` and the `code.manager.chat.group` want; forward GF2 to the engine element
  (GF2 — **not** an accepted bus Blocker).
- Document name-uniqueness enforcement (GF3), qualify "never blocks" and note poison recovery
  (GF5), note the lazy-JSON failure caveat (GF6), and add the tap-startup precondition to
  `elephant.gaps` (GF11).

**Severity calibration:** under `element.md`'s own scale (Blocker = description says something the
code does not do; Major = important gap; Nit = small one), GF1/GF7 qualify as Blocker/Major but
are single-sentence *wording* fixes with correct code. GF2, if its evidence were verified, would be
a Blocker against `rules[0]` — but against the **engine** element, not this one. GF3 is the only
finding that changes runtime behavior in all builds. GF4/GF8/GF9 are documentation/context gaps;
GF5/GF6/GF10/GF11/GF12 are Nits.

## Review of the existing `resolution.md` (LethalCohort)

Strong and largely convergent; I endorse its GF3 pre-mutation assertion placement, its GF4
"partly accept" nuance, its GF5 qualification, its GF6 `serde_json::Error`-is-not-`Clone` caveat,
and its GF9 refusal to invent a JEV expansion. Four corrections:

1. **GF2 is over-accepted.** It is forwarded/misattributed, not a bus finding; the engine redesign
   prescription belongs in another element's document. See my GF2 above.
2. **GF1/GF7 fix is incomplete.** `lib.rs:10–11` carries the same "every subscriber ... whatever
   their type" imprecision and must be reworded too; otherwise the contradiction survives in the
   code's own documentation.
3. **GF3 × GF5 interaction should be stated explicitly.** The pre-mutation assertion is what keeps
   a poison-recovered registry consistent; this is the reason for the placement, not just style.
4. **Group the editorial fixes.** GF4/GF8/GF9/GF10/GF12 are one glossary + API section; treating
   them as five separate edits invites a repetitive `element.md`. GF12's fix is global (shared
   schema), not per-element.
