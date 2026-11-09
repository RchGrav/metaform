# Sol — core and web review

Reviewed README.md, ACP design, IMPLEMENTATION.md in that order, then all current Rust crate source/tests and the web asset. Scope: roundtable and roundtable-web; cross-read bus/acp-host. Only review/ is modified. Findings below are source-confirmed unless a verification limit is stated. Priorities: P1 security/table liveness, P2 reachable correctness, P3 smaller integrity defects. No objection to explicitly deferred ACP v2, AgentSight, or SDK adapter work.

## S1 (P1) — Participant tokens do not protect the chair API or process launcher

**Location:** crates/roundtable-web/src/app.rs:77-85, 139-146; crates/roundtable-web/src/tables.rs:68; crates/acp-host/src/harness.rs:94.

**Wrong:** All /api routes are unauthenticated, including command, settings, global event history and arbitrary command launch. Token checks protect only /mcp. No Host or Origin validation exists either.

**Failure:** Any participant with HTTP access to localhost can list tables and POST an `end`, change judging, inject chair guidance, or create a seat whose command executes an arbitrary program before any ACP permission check. With --host 0.0.0.0 the same capabilities are exposed to network peers. A DNS-rebinding origin is not rejected by Host validation. Ordinary cross-origin JSON POSTs may be prevented by browser preflight; that does not protect local processes or rebinding.

**Fix:** Separate authenticated chair credentials from seat credentials; require chair authorization for the whole /api surface, validate allowed Host/Origin values, and deliver credentials only to the chair UI. Test the actual router with an untrusted seat caller. Merely adding CORS does not fix this.

## S2 (P1) — A stalled seat setup prevents all discussion and even End

**Location:** crates/roundtable/src/engine.rs:157-158, 244-258; crates/acp-host/src/harness.rs:229-255.

**Wrong:** start() awaits join_all of every initialize/session/new/config operation before entering the command/event loop. Session creation and setting configuration have no deadline.

**Failure:** A answers initialize but never answers session/new. B is completely ready. Neither B's first turn nor queued Hold/End commands run, indefinitely. This contradicts independent progress and the explicit-chair-hold-only principle.

**Fix:** Integrate per-seat readiness as events into the running engine; process controls during setup and let ready seats progress while stalled seats remain pending. Bound/isolate setup RPC failures without cancelling productive prompt work. Test a fake that hangs on session/new while another seat contributes and End works.

## S3 (P1) — Independent typed subscriptions discard the bus's global order

**Location:** crates/roundtable/src/engine.rs:148-153, 302-307, 422-439, 442-469.

**Wrong:** Completion, text and exit arrive through distinct subscriptions selected randomly by tokio::select!. Their Delivery.seq values are ignored. Per-stream order is insufficient for state transitions that require cross-type order.

**Failure:** A queues `WORK\n`, tool activity, final text, completion while the table task is busy. Completion can win before the earlier WORK text. The seat becomes Idle; the WORK event is subsequently ignored. Since acp-host returns the final text block after a tool, the work note is broadcast as an ordinary contribution. Likewise an exit can make a queued successful completion disappear. This is an engine race even if the ACP SDK perfectly orders its callbacks.

**Fix:** Consume one ordered bus tap and downcast/filter the relevant event types, or merge deliveries by the global sequence. Test a backlog containing WORK, tool and completion before the engine resumes; assert a work note and no contribution.

## S4 (P1) — advance while a turn is active corrupts floor ownership

**Location:** crates/roundtable/src/engine.rs:324-338, 414-416, 490-493, 584-590; crates/roundtable/src/turn.rs:184-208.

**Wrong:** topic_due is checked before the active-floor guard, so advance(None) polls other seats while an old floor remains active. When polling becomes empty through failure/exit, step() clears floor_deadline although it belongs to that active floor. release_floor() tracks no owner.

**Failure:** A holds the floor and invokes advance without a topic; B gets a proposal prompt which fails. step clears A's deadline, closes the empty poll, then can give B the discussion floor while A is still Floor. A's later completion or WORK clears B's deadline. If B then hangs, the table cannot apply its deliberation window. Even successful polls mix an old-topic reply into the new topic.

**Fix:** Model floor ownership explicitly by seat/prompt and make topic transitions close/retire old floor bookkeeping without cancelling the ACP work. Preserve outstanding replies' topic identity and ensure only the current owner can release its deadline. Test advance during a live turn with successful, failed and timed-out proposals.

## S5 (P2) — SSE history/live handoff loses events

**Location:** crates/roundtable-web/src/app.rs:50-57, 153-158.

**Wrong:** History is filled asynchronously by a separate tap. Subscribing live before copying history does not capture events already published but not yet processed by the history task.

**Failure:** Publish opened or contribution E; pause the history consumer; connect /api/events. E precedes the new live subscription and is absent from the history snapshot. It appears in neither stream, leaving a page without its objective, seat list or an accepted message. Reconnect can encounter the same race. Deduplication cannot restore omissions.

**Fix:** Have one replay owner atomically create a snapshot and register its live subscriber, or wait for history to reach an explicit bus watermark before constructing the replay/live boundary. Test with history ingestion deliberately blocked at connection time.

## S6 (P2) — Millisecond IDs alias independent tables

**Location:** crates/roundtable-web/src/tables.rs:89, 100-105, 123-125.

**Wrong:** new_id uses only wall-clock milliseconds, without uniqueness checking.

**Failure:** Two custom-command create requests complete in the same millisecond. The second handle replaces the first; both engines use identical harness IDs, listen to each other's events, and append to the same record. One table loses its chair control and MCP tokens. Clock rollback can repeat an older ID too.

**Fix:** Use random UUIDs or an atomic monotonic counter plus a process nonce and insert with collision rejection. Test concurrent creation with a fixed clock or injectable ID source.

## S7 (P2) — Valid seat names break tools URLs and the browser's seat map

**Location:** crates/roundtable-web/src/tables.rs:64-65; crates/roundtable/src/engine.rs:236; crates/roundtable-web/assets/index.html:168, 175, 198-199.

**Wrong:** Only `/` is excluded from seat names, but names are interpolated into a URL without path encoding. The UI also stores seats in `{}` and uses inherited properties as existing seats.

**Failure:** `Sol#1` or `Sol?1` passes validation but makes the token a URL fragment/query rather than a path segment, so tools fail. A seat named `__proto__` or `constructor` resolves an inherited property; initialization/order insertion is skipped, hiding that participant and mutating a prototype/function object.

**Fix:** Encode URL path segments using a URL builder; use Map or Object.create(null) for user-keyed dictionaries. Apply equivalent validation/construction at the public library boundary. Test these names end to end.

## S8 (P2) — Headless operation ignores HTTP bind failure

**Location:** crates/roundtable-web/src/main.rs:33-36.

**Wrong:** run mode spawns the server and never observes its Result before launching agents.

**Failure:** Port 4180 is occupied. The server task exits with an error; the table still starts and tells participants to use the unrelated listener as their MCP endpoint. Tools fail and the CLI can continue indefinitely without reporting the cause.

**Fix:** Bind first, fail immediately if unavailable, then launch tables with the actual listener address and monitor server termination. Test an occupied port.

## S9 (P2) — Optional JEV requests suspend the entire engine

**Location:** crates/roundtable/src/turn.rs:123, 239; crates/roundtable/src/engine.rs:302-307; crates/roundtable/src/jev.rs:130-169.

**Wrong:** Both judgment calls are awaited inline inside the sole table event loop. The eight-second fail-open timeout limits but does not remove the pause.

**Failure:** An optional provider stalls for eight seconds; Hold/End, another participant's WORK declaration, completion and floor deadlines all sit queued. Repeated stalls repeat this every judged contribution, against 'Nothing waits ... on an optional service'.

**Fix:** Represent pending judgment as an asynchronous result/event while continuing controls and activity processing. Preserve required before-distribution ordering of contributions. A test with a stalled local JEV endpoint should show prompt End handling before JEV's deadline.

## S10 (P2) — Core library accepts configurations that web validation rejects

**Location:** crates/roundtable/src/engine.rs:141-145, 314-316, 320-322; crates/roundtable/src/config.rs:11-39.

**Wrong:** Public spawn accepts duplicate/empty seat identities and an empty roster without validation or an error result. The engine and token map require unique identities.

**Failure:** A chat-channel host supplies two seats named Sol. Token creation overwrites one token and seat_of always routes both harnesses' replies to the first matching seat; the second seat can remain busy indefinitely. With no seats the engine silently sits alive without any way to progress. Web-only validation does not protect another library host.

**Fix:** Validate required invariants in the core constructor, return a structured error or terminal startup event, and reuse that validation from web. Test duplicate names and no seats via public spawn.

## S11 (P3) — Feedback writes unvalidated identities and rating values

**Location:** crates/roundtable/src/mcp.rs:99-113; crates/roundtable/src/engine.rs:594-595.

**Wrong:** The advertised input schema is not enforced. Any nonempty different target and arbitrary JSON rating values are persisted as accolades.

**Failure:** A seat rates a nonexistent participant with efficient=999 or coordination={...}. The endpoint claims success and the permanent identity log contains invalid scores/identities, defeating its documented use for future participant selection.

**Fix:** Validate membership, value types and 0..5 ranges at the authoritative command boundary; reject invalid requests and do not acknowledge recording when send() failed. Test invalid target, out-of-range/wrong-type ratings and ended tables.

## S12 (P2) — Important verification gaps

**Location:** crates/roundtable/tests/engine.rs:27, 78-81, 130; crates/roundtable-web/src/app.rs:163.

**Wrong/scenario:** Every engine test sets judging=false, so the claimed fail-open coverage never enters Jev::ask; wrong three-gate thresholds, veto accounting and deferred feedback can ship undetected. The WORK-skip assertion runs only if the event exists, so removing WORK skip credit passes it. No web HTTP test exercises authentication or stream handoff; the MCP helper test bypasses routing and tests only an empty invalid token. Searched current Rust crate tests/source references, not archaeology tests.

**Fix:** Add local fake-JEV boundary tests (0.70/0.69, timeout, malformed/missing answers), inspect actual next prompts after veto/truncation, require the WORK skipped event, and test HTTP authorization/replay and advance races described above.

## Cross-review notes for Sonnet

- Agree H1 symlink escape and H2 unenforced shell scope in substance. Use OS isolation rather than command-string heuristics to enforce shell boundaries. Source line numbers in the current permission.rs are 60 and 75, rather than 258 and 268.
- Agree child-process-tree cleanup and unbounded discovery need concrete fixes. Do not make session mode failures silently best-effort: running Claude without its required manual mode can remove scope checks.
- H3 treats registry compromise as established and forbids OPENROUTER_API_KEY inheritance, conflicting with the documented Pi/OpenRouter route. Keep this as a trust-boundary discussion, not a confirmed exploit from an honest registry.
- M2/M3 depend on unspecified SDK behavior. Do not promote without verifying SDK dispatch/disconnect semantics. S3 is independently proven from the engine's separate subscriptions.
- Last-block reply extraction may intentionally distinguish progress from a final contribution; WORK must be durable independently (S3). Do not recommend broadcasting all pre-tool progress by default.
- Token-in-URL disclosure depends on actual logging. PromptSent does not intentionally include MCP URL; avoid claiming it does. The unauthenticated chair surface (S1) already bypasses tokens outright.

Validation: source/path tracing; no full suite run because existing engine/permission tests create files outside review/, forbidden by this review's write constraint. Supplemental lens checks independently confirmed S2/S4/S5/S6/S7/S8 and S12. Group agreement remains pending.
