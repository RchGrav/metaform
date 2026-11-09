# Roundtable review — consolidated findings

Seats: **S** = Sonnet (review/Sonnet.md, IDs H*/M*/W*/E*/L*), **O** = Sol (review/Sol.md, IDs S1–S12). "Agreement": **both** = found or confirmed by both seats; **S-only / O-only** = found by one, read by the other and not disputed, or marked as noted; **narrowed** = both agree on a smaller claim than first written. Ordered most severe first. Line numbers: use Sol.md's (Sonnet.md has a correction table at its top). Nothing here was run; findings are from reading source, as Sol's file also states.

## Priority 1 — security and table liveness

| # | Finding | Found by | Agreement | Fix (agreed) |
|---|---|---|---|---|
| 1 | **Chair API and launcher unauthenticated** (O:S1, S:W1). Every /api route, including `POST /api/tables` with a seat `command` (arbitrary process), settings, command, global event stream, has no auth and no Host/Origin check; `--host 0.0.0.0` accepted. Participant tokens only guard /mcp. DNS rebinding or any local process/user reaches it. | both | both | Separate chair credential (random per run) on the whole /api surface, Host/Origin allow-list, refuse non-loopback bind without it, test with the real router. |
| 2 | **ScopePolicy symlink escape** (S:H1; O agrees). New file through an in-scope symlink pointing outside passes: `canonicalize` fails for non-existing path, lexical fallback accepts. permission.rs:56-61 | both | both | Canonicalize the deepest existing ancestor, then re-append unresolved components (reject `..`). |
| 3 | **Shell and no-location requests are unscoped; non-asking harnesses bypass the policy** (S:H2; O agrees in substance). permission.rs:65-79, config default_settings. | both | both (fix refined by O) | Do not rely on command-string heuristics; enforce with OS isolation (sandbox mode, container or namespaces) where available and state "scope not enforced" visibly per harness otherwise. |
| 4 | **Bus order discarded by the engine** (O:S3, S:E2). Four typed subscriptions in `select!`: completion can beat earlier WORK text (work note broadcast as contribution), exit can beat a queued completion (reply lost). engine.rs run loop. | both | both | Consume one ordered tap or merge by `seq`. Test backlog WORK+tool+completion, and exit-after-completion. |
| 5 | **Seat setup stalls the whole table, including End** (O:S2, S:H4 first half). `start()` awaits `join_all` of launch/session/config with no deadline before the command loop runs. | both | both | Make seat readiness events inside the running loop; controls work during setup; ready seats progress. |
| 6 | **`advance` during an active turn corrupts floor and topic identity** (O:S4, S:E3). Poll starts while an old floor is active; empty poll clears the active seat's deadline; the old turn's reply is judged and numbered against the new topic. | both | both | Floor ownership by seat+prompt; each reply keeps the topic index of its prompt; topic transitions retire old bookkeeping without cancelling work. |
| 7 | **Huge `window_secs`/`SetWindow` panics the engine task** (S:W2). `Instant::now() + Duration::from_secs(u64::MAX)`; table silently dead, seats keep running. tables.rs:98,116; engine.rs:379. | S | S-only (O did not dispute) | Clamp (e.g. 24 h); supervise the engine task and publish `TableEnded` on panic. |
| 8 | **A contribution beginning "Work …" is taken as a WORK declaration and dropped** (S:E1). rules.rs:105-108, 85-103. | S | S-only | First line exactly `WORK` (optionally `WORK:`); tests for "Work plan", "Workflow". |
| 9 | **JEV awaited inline in the only event loop** (O:S9, S:E8). Hold/End/WORK/deadlines queue behind up to 8 s per contribution. turn.rs:123,239. | both | both | Judge as a task reporting through an event; keep ordering of distribution. |

## Priority 2 — reachable correctness and integrity

| # | Finding | Found by | Agreement | Fix |
|---|---|---|---|---|
| 10 | **SSE history/live handoff can lose events** (O:S5). History is filled by an async tap task; live tap registered before copying history does not include events the history task has not processed yet. app.rs:153-158. Sonnet confirmed by reading. | O | agreed (S read and confirms) | Single replay owner: atomically snapshot + register under one lock, or watermark by `seq`. Test with history task blocked. |
| 11 | **Core library accepts invalid configs** (O:S10). Duplicate/empty seat names, no seats: tokens overwritten, replies routed to the wrong seat, table sits idle. Reuse problem for any chat host. | O | agreed | Validate in `roundtable::spawn`, return an error; web reuses it. |
| 12 | **Prompt state consumed before the send succeeds** (S:E5). `seen_*`, `first`, drained feedback advance before `prompt()` returns Ok. turn.rs:17-70. | S | S-only | Commit cursors only after Ok. |
| 13 | **Topic-poll replies unclassified** (S:E6). "PASS" becomes a proposal; with judging off it is joined into the topic. turn.rs:211-220. | S | S-only | Classify; Pass/Empty/Work are no proposal; grapheme truncation. |
| 14 | **Partial first round after a mid-round topic change counts** (S:E4). | S | S-only | Restart round on topic change. |
| 15 | **Table never ends when all harnesses exit** (S:E7). engine.rs:524 notice only. | S | S-only | Publish `TableEnded`. |
| 16 | **Process tree not killed** (S:M1; O: "needs a concrete fix"). harness.rs:105-106,175. | S | both | kill the process group with grace period. |
| 17 | **Millisecond table ids collide** (O:S6, S:W6). tables.rs:123. | both | both | UUID / counter+nonce, reject collisions. |
| 18 | **Seat names not URL-encoded; `__proto__` etc. in the UI map** (O:S7). | O | agreed on reading | Build URLs with a path-segment encoder; Map in index.html; validate in core. |
| 19 | **Headless `run` ignores bind failure** (O:S8). main.rs:33-36 spawns server and never looks at its result. | O | agreed on reading | Bind first, fail early, pass the actual address. |
| 20 | **Feedback tool does not validate target, type, range, note, or recording** (O:S11, S:W4). | both | both | Validate at the command boundary; reject; do not claim recorded on send failure. |
| 21 | **Event history unbounded, whole-history clone under lock, all tables visible to every client, ended tables never removed** (S:W3). | S | S-only | Per-table history, compact AgentText after completion, remove ended tables, reject tool calls after end. |
| 22 | **Tools token: not CSPRNG, plain `==`, in URL path** (S:W5/M5). O notes URL disclosure depends on logging and PromptSent does not carry it: **narrowed** to CSPRNG + constant-time compare + header preferred. | S | narrowed | `getrandom` 32 bytes, constant-time compare, Authorization header. |
| 23 | **Registry-supplied env/package executed; full parent env inherited** (S:H3). O: not an established exploit and a blanket ban on OPENROUTER_API_KEY conflicts with the Pi/OpenRouter route. **Narrowed** to a trust-boundary item: allow-list registry env keys (no `LD_*`, `NODE_OPTIONS`, `PATH`), pass secrets only to the harness that needs them, pin builtin versions (launch.rs:87-88). | S | narrowed | as stated; owner may accept the registry trust. |
| 24 | **Test gaps** (O:S12 + S:Missing tests). Every engine test has judging=false; no fake-JEV tests (0.70/0.69, timeout, malformed); WORK-skip assertion conditional; no HTTP/auth/SSE test; no `Harness` tests in acp-host (exit mid-turn, one-turn-per-session, permission answering); no MCP `handle` tests; no tests for hold/resume/end/poll. | both | both | Add a local fake-JEV endpoint and a router-level test suite; see both files for the list. |

## Open or narrowed (not to be fixed without verification)

| Finding | Found by | Status |
|---|---|---|
| H4 second half: failed `set_config` drops the seat (S). O: do not make mode failures silently best-effort; running Claude without Manual mode removes scope checks. | S | **agreed compromise:** fail the seat when the failed setting is a scope-enforcing default (Claude `mode`, Codex `mode`); warn and continue for other settings. |
| M2 harness exit mid-prompt gives no PromptFailed; M3 AgentText vs PromptCompleted ordering inside acp-host | S | **unverified**: depends on SDK dispatch/disconnect semantics. Verify against the SDK before promoting; both seats agree not to rank until then. |
| M4 reply = last block only discards text before a tool call | S | **disputed by O as possibly intentional**; the real requirement is that WORK is durable (item 4). Open for the owner: whether pre-tool text should count. |
| L-items: bus event NAME uniqueness, dead subscribers pruned lazily, per-tap JSON serialization, stderr 50 ms race and unbounded line, `*Always` permission options (persist an in-scope allow in the agent), `Cancelled` when no option matches, JEV candidate is untrusted input, index.html rebuilds feed per event | S | S-only, low |

## Checked and clean
index.html renders all agent text through `textContent`; no XSS path found. Bus ordering within the crate is sound (single lock covers numbering and enqueue).

## Not covered by either seat
ACP v2 / AgentSight / adapter items are recorded as deferred and were not reviewed. Library reuse for a chat-channel host beyond item 11 (Table reachable only via `spawn`+`TableHandle`, `Notice` levels as strings, tools URL assumption in `ToolsEndpoint`) was only touched by Sol's S10; no full audit.
