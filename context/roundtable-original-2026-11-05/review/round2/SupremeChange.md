# SupremeChange — round 2 review

Coverage agreed at kickoff: prompts.rs, jev.rs, mcp.rs, names.rs, roundtable-web (Rust and HTML), OpenRouter adapter (source and tests). PricklyHaven covers transport, monitoring and discussion engine. Authority read: owner quotations and decisions in TRACEABILITY L/M/N, then README and ACP design. Builder status claims were not treated as proof. No implementation files changed.

## SC1 — P1: Listed OpenRouter adapter cannot be selected when creating a table

**Location:** `crates/roundtable-web/src/tables.rs:68-70`; compare `crates/roundtable-web/src/app.rs:185-189` and `assets/index.html:373`.

GET /api/harnesses adds a repository-local `openrouter-acp` entry after autoselection. POST /api/tables independently runs autoselection and never adds that entry. The UI submits the selected ID, not its launch specification. The built-in catalog has no such ID.

**Failure:** Build the adapter, choose “OpenRouter (Agent SDK)” in New table, provide a key and a model. Create fails with “unknown harness openrouter-acp” unless an unrelated remote registry happens to publish the same ID; in that case creation can select a different program. README §9.4 requires selecting OpenRouter participants.

**Fix:** Share one harness resolver between listing and creation, including the local adapter entry and its exact launch specification. Add an API integration check that a listed local ID resolves during creation, with registry traffic mocked.

## SC2 — P1: Cancelling a command misses descendants after the shell exits

**Location:** `adapters/openrouter-acp/src/tools.ts:197-200`.

The abort handler refuses to signal the process group when its leader has exited. The group's descendants can still exist and retain stdout/stderr, preventing `close` and keeping the tool promise pending. Detaching the shell also separates that group from the adapter's group, so host group shutdown does not solve this.

**Failure:** An allowed command `sleep 30.123456789 & exit 0` leaves sleep holding the pipes. Cancel after the shell exits. The handler sees `child.exitCode !== null`, returns, and cancellation neither kills sleep nor settles the command until sleep exits. A long-lived descendant can stall it indefinitely and survive adapter shutdown. This contradicts cancellation and the owner-observed requirement to stop leftover processes.

**Evidence:** `node review/round2/cancel-descendant.mjs` prints `{"cancelled":true,"settled":false}`; the script then kills its distinctive test group and awaits cleanup. No provider calls. Existing test `kills a running command...` only tests `exec sleep`, whose leader remains alive.

**Fix:** Track the process group independently of leader exit; signal that group on cancellation until all command pipes/processes are done. Treat ESRCH as already stopped. Add the exited-leader case to cancellation and connection-close tests.

## SC3 — P2: Web layer still introduces timers despite the owner's explicit prohibition

**Location:** `crates/roundtable-web/src/app.rs:342`; `crates/roundtable-web/assets/index.html:233`.

The event stream enables periodic `KeepAlive::default()` ticks, and table completion schedules a 500ms delayed history fetch. Owner M says “Timers. None anywhere”; N only leaves the ACP process-shutdown sequence open. These web timers have no recorded owner exception or observed-failure justification.

**Failure:** Every quiet SSE connection schedules periodic wakes. Every ended table assumes its record will be ready within 500ms; a delayed recorder still produces stale history after that delay. A completion event already exists, so the arbitrary wait also fails the event-driven requirement.

**Fix:** Remove timed SSE keepalives. Update the history summary from the existing table events, or emit a recorder-completion event and refresh on that event if disk confirmation is needed. Do not substitute another delay.

## SC4 — P2: Corrupt or unreadable identity profiles are silently reset and overwritten

**Location:** `crates/roundtable-web/src/app.rs:412-418`.

All profile read and parse errors become a new profile with zero points and no ratings; the next write replaces the original file. Writes truncate the destination directly, so interruption can itself create the corrupt profile which triggers this reset next time.

**Failure:** An identity has accumulated ratings, but its JSON is truncated by an interrupted write. The next rating quietly erases the prior score and history. A transient read error on a writable file does the same. Owner M requires accumulated ratings and loud failures.

**Fix:** Create a fresh profile only on NotFound. Propagate read/parse/schema failures and surface a recorded visible error. Replace profiles atomically using a sibling temporary file and rename; serialize writers if multiple hosts share a data directory. Add corrupt-profile and interrupted-write coverage.

## SC5 — P2: Feedback tool claims identity credit but only writes an unrelated log, silently

**Location:** `crates/roundtable/src/mcp.rs:90-91`; `crates/roundtable-web/src/app.rs:75-85`; compare `mcp.rs:23` and `prompts.rs:31`.

The feedback tool says ratings build the participant's identity and replies “Recorded”. Only `roundtable.rating` updates identity profiles; `roundtable.feedback` is appended to accolades.jsonl and never updates a profile. Open or write failures on that path are ignored entirely. The event contains chair seat labels rather than resolved genesis names.

**Failure:** A valid agent rates a peer through feedback. It receives “Recorded”, but the peer's accumulated identity score never changes. If accolades.jsonl cannot be written, no durable feedback exists and no failure is shown. Owner L#13 requires truthful tool replies, and M requires ratings saved to identity. Whether to keep feedback itself is explicitly unresolved; that does not authorize false persistence claims.

**Fix:** If retaining feedback, resolve participants to identities and use the rating persistence path, reporting persistence outcomes before claiming recording. Alternatively describe the existing event/log action truthfully while the owner decides the tool's future. Never ignore storage failures. Test the feedback-to-profile path and unwritable storage.

## SC6 — P2: Chair UI displays 512 after acceptance regardless of configured base

**Location:** `crates/roundtable-web/assets/index.html:194,214`.

Seat creation and accepted contributions hardcode allowance 512, although New table accepts a chair-selected base (`index.html:398`). Owner M makes the base a chair setting and acceptance resets to that base.

**Failure:** With base 1024, an accepted contribution from A resets A's displayed allowance to 512 until A's next floor event. The engine may be correct while the chair sees a false limit. The initial display is also wrong for every nondefault base.

**Fix:** Consume the base_allowance already present in TableOpened (`engine.rs:367`) and store it per table; initialize and reset the UI to that value. Test a nondefault base across accepted and vetoed messages.

## SC7 — P2: OpenRouter adapter refuses the table's own tools

**Location:** `adapters/openrouter-acp/src/adapter.ts:178,190-194`; `adapter.ts:158`; `crates/roundtable/src/prompts.rs:31`.

The adapter advertises HTTP MCP as false and rejects every nonempty mcpServers list. It exposes only filesystem and shell tools, so its agents cannot use advance or feedback even though their common process prompt tells them they can. TRACEABILITY N explicitly acknowledges this open limitation; acknowledgment does not implement the owner's tools.

**Failure:** An OpenRouter agent elected head cannot advance a completed task through the advertised tool, and cannot give feedback during discussion. It is an unequal participant compared with an HTTP-MCP-capable harness.

**Fix:** Connect client-supplied MCP servers with an existing MCP client library and expose their tools through the OpenRouter agent SDK, preserving seat credentials and cancellation. Test a real local Roundtable MCP exchange through the adapter. Until implemented, the participant prompt must accurately describe tool availability.

## SC8 — P1 security: Dangling symlink escapes file confinement without a race

**Location:** `adapters/openrouter-acp/src/tools.ts:68-77,332-334`.

When realpath returns ENOENT for a dangling symlink, resolveInRoot treats the symlink as a nonexistent ordinary leaf and ascends to its parent. It then reconstructs the lexical symlink path and certifies it as inside the root. Both the initial and the second checks have this defect. writeFile follows that symlink and creates its missing outside target.

**Failure:** A session root contains `link -> ../outside.txt`, and outside.txt does not exist. Ask write_file to write link. Permission reports only the in-root path, the scope check also treats its ENOENT as a new in-root leaf, and the tool writes outside the root. No concurrent symlink swap is needed. The common shared workspace makes peer-created links a realistic input. This is a violation of the implemented file confinement and permission boundary, irrespective of the separately allowed shell tool's powers.

**Evidence:** `node review/round2/dangling-symlink.mjs` invokes the existing tool and prints a session root under `review/round2/symlink-fixture/root` and an outside sibling file whose contents are `escaped`. Fixtures are created and removed only under review/round2. Existing symlink tests cover links to existing targets, not dangling ones.

**Fix:** Inspect existing path components with lstat/readlink rather than treating all realpath ENOENTs as nonexistent leaves; reject dangling symlinks that escape the root. For actual race-resistant confinement, perform filesystem operations relative to a trusted directory descriptor with beneath/no-symlink-escape guarantees, using a maintained library/platform facility. Add the deterministic dangling-link regression case and a directory-swap case. The Rust scope checker has the same realpath-ENOENT assumption and should be checked as well.

**Cross-check:** PH independently identified the Rust ScopePolicy counterpart (PH12). SC then compiled `review/round2/scope-dangling.rs`, which imports the actual permission.rs without modifying it, with output binary also under review/round2. Running that binary prints `dangling outside target: Allow { reason: "inside .../review/round2/scope-fixture/root" }`. Both the adapter escape and the policy's erroneous permission are reproduced. Merge SC8 and PH12.

## SC9 — P1 security: Environment-configured chair token is inherited by agents

**Location:** `crates/roundtable-web/src/app.rs:102`; `crates/roundtable/src/config.rs:27`; `crates/roundtable/src/engine.rs:802-806`; `adapters/openrouter-acp/src/tools.ts:184-185`.

The web server accepts ROUNDTABLE_TOKEN as its chair credential. Child launches inherit the environment but remove only OPENROUTER_API_KEY and TYPESAFE_API_KEY; the adapter's command tool also removes only the OpenRouter key. Thus the purported per-seat versus chair credential boundary fails when the supported token override is used.

**Failure:** Start serve with a fixed ROUNDTABLE_TOKEN of at least 16 characters. A participant executes printenv and learns the chair token. It can now send requests to /api/settings, /api/tables or another table's command endpoint using the expected localhost Host/Origin. This permits cross-table control and chair-level command launching. This path does not require reading the chair's private files. It does not apply to the default token generated only in memory.

**Fix:** Strip the chair credential from every harness launch, including explicit LaunchSpec env entries, and from any model-executed subprocesses. Verify with a fake harness that the configured token never reaches its environment while legitimate provider credentials still follow the explicit sharing policy. Check other launch-carried chair credentials at the same boundary.

## SC10 — P2: Review requests omit the allowance yet their replies are truncated to it

**Location:** `crates/roundtable/src/turn.rs:44`; `crates/roundtable/src/prompts.rs:68`; `crates/roundtable/src/engine.rs:601-602`.

REVIEW replaces the allowance line instead of preceding it. Its response is handled as a normal after-work contribution, including truncation and allowance spending. Owner M requires the participant to be informed of its limit before contributing.

**Failure:** An agent's bank has grown while working. When it is the lone free participant it receives “review the materials” and “reply ... with your message”, with no current limit. It replies with an otherwise useful report and is truncated against a limit absent from that request. A first-ever review request also never supplies a numerical current allowance.

**Fix:** Include the current allowance at the end of review requests as for ordinary turns. This finding does not require declaring review replies forbidden; that broader PH4 interpretation lacks authority. Add a prompt assertion for review with a nondefault bank.

## SC11 — P2: Monitor events cannot be routed, recorded or displayed

**Location:** `crates/roundtable/src/record.rs:26`; `crates/roundtable-web/assets/index.html:175-177,197-235`; event shape in `crates/agent-monitor/src/lib.rs:112,142`.

ACP events have a string harness id (`table/seat`). AgentSight events instead have an object `{pid,id}`. record::table_of only handles a string, so its per-table recorder and filtered SSE subscriptions discard monitor events. The browser helper calls `.includes` on the object and throws TypeError. Even after fixing routing, apply has no cases for monitor observations, attachments or unavailability. Engine handles initial attach failure via a notice, but never consumes later MonitorUnavailable events from pump (`capture.rs:146`) or TLS attach failure (`capture.rs:95-96`).

**Failure:** Capture attaches and shows process/network activity on the bus, then its TLS probe stops. Neither observations nor the failure reach that table's saved record or visible chair interface. Unfiltered SSE clients receive events that throw in the browser instead. A chair cannot distinguish an idle harness from failed monitoring, contrary to README §10.2–10.3 and the loud-error requirement.

**Evidence:** `node review/round2/monitor-routing.mjs` extracts and executes the actual index.html tableOf function against the monitor JSON shape and prints `TypeError: data.harness.includes is not a function`. No root privileges or tracing required. Rust's `.and_then(Value::as_str)` at record.rs:26 establishes the corresponding drop path.

**Fix:** Normalize/extract the object harness.id in the shared event envelope/routing helpers, retain monitor events in table records and scoped streams, and render observations and later failures. Initial attach errors must remain distinct from a probe that subsequently stops. Add a synthetic monitor event through bus → recorder/SSE → UI test; primitive serialization tests do not cover the integration.

## SC12 — P2: Empty rating objects silently satisfy the end-of-table rating round

**Location:** `crates/roundtable/src/turn.rs:333-356`; proposal counterpart at `turn.rs:213-218`.

on_rating accepts any JSON object as cards, loops over its entries, then unconditionally marks the rater done. `{}` records zero ratings and no error. A response rating only one of several peers also silently omits the rest. on_proposal likewise silently ignores an empty response, unlike the normal turn path which loudly reports an empty reply.

**Failure:** Every agent answers `{}` during ending: the table ends successfully with no identity ratings despite the owner's “each agent rates every other agent” instruction. Or a harness returns an empty topic proposal and no visible per-agent error explains its absence.

**Fix:** Track which required peer ratings were actually read and publish an explicit error for missing peers; do not silently claim a complete rating set. Report empty proposal responses with the same visible failure semantics as empty turns. This calls for completeness reporting, not reintroducing the rating-value validation struck by L#12. Add `{}`, partial-peer and empty-proposal coverage. Merge with PH6.

## SC13 — P2: Disabling judging does not stop in-flight or queued topic progression

**Location:** `crates/roundtable/src/engine.rs:433-445,737-743`; `crates/roundtable/src/turn.rs:256-278`.

Topics are gated when an advance request is received, but not when the queued request is applied or a topic poll's score returns. SetJudging/SetJevKey only update flags and publish settings. Existing polls keep requesting proposals/scoring and on_scored still changes the topic.

**Failure:** Start a topic poll with judging enabled, then turn judging off while JEV is scoring. When its already-started request returns, on_scored selects the next topic even though topics_enabled is now false. A previously queued explicit advance can also change the topic after judging is disabled. Owner M explicitly says judging off means no topic progression and no next-topic poll.

**Fix:** On disabling topics, invalidate or suspend outstanding poll/advance state and reject stale scoring results. Recheck topic eligibility at application/commit, not only at tool-call receipt. Cover disabling judging and removing the key during proposal collection, during scoring, and with an advance deferred behind the floor.

## SC14 — P1: Explicitly shared OpenRouter key is removed at process launch

**Location:** `crates/roundtable/src/engine.rs:803-810`; `crates/acp-host/src/process.rs:65,70-71`.

start_seat adds OPENROUTER_API_KEY to env_remove before inserting the authorized shared key in env. process::spawn applies envs, then env_remove, so removal wins. With share_openrouter_key enabled and a real supplied key, the adapter still receives no credential and fails session/new with authRequired. This is independent of the GUI resolver defect and affects custom-command paths as well.

**Fix:** Remove the explicitly authorized provider variable from env_remove when adding it to env, preserving other secret removals. Test the actual fake-harness environment for sharing on/off and an inherited credential. `env-order.rs` demonstrates the standard Command precedence using only a synthetic variable; it is not a live provider test. Canonical ID F19, inserted among P1 entries while retaining existing canonical IDs.

## Low-priority explicit strike

`crates/roundtable/src/prompts.rs:23` still calls topic proposals “private”, although owner L#6 explicitly struck that label. Remove it. The old unconditional allowance-credit sentence is separately listed as awaiting owner wording in M/N; I do not count that acknowledged unresolved wording as another defect.

## Cross-check status

Own findings awaiting PricklyHaven's independent confirmation. No claim of both-party agreement yet. This pass did not execute workspace-wide Rust tests because their outputs would write outside review/round2; this is a code review plus the isolated cancellation reproduction.
