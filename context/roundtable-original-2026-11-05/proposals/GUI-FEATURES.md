# Roundtable interface: prioritized feature proposal

Authors: Sonnet (page and chair controls) and Sol (records, APIs, synthesis). Joint proposal, updated against builder changes on 2026-11-05. Sonnet’s assessment is in [sonnet-notes.md](sonnet-notes.md).

Past-table review now exists across server runs. The next release should harden that review and make returning to an autonomous discussion easy. Keep the interface a channel: a compact table picker, a discussion stream, expandable details, and chair actions. No new approval steps, automatic intervention rules, or requirement that the chair remain present.

Priority reflects chair value, with the owner's required archive first. S = mostly page work using existing data; M = substantial page behavior or a focused API/event extension; L = coordinated persistence/API/page work. Sizes describe implementation scope, not elapsed time. The archive estimate covers remaining work; its baseline has shipped. Optional extensions have separate sizes.

| Rank | Feature | Size | Proposed by | Both agree? |
| --- | --- | --- | --- | --- |
| 1 | Harden shipped past-table review: paging, integrity labels, long-record rendering | M remaining | Owner required; Sonnet + Sol design | Yes |
| 2 | Return-to-table catch-up and connection status | M | Sonnet; Sol adds reconnection semantics | Yes |
| 3 | Topic navigation, work notes, and outcome review | M | Sonnet; Sol refines provenance | Yes |
| 4 | Persistent attention strip and optional notifications | S | Sonnet | Yes |
| 5 | Inspect judgments and topic selection | S | Sonnet; promoted in Sonnet’s review | Yes |
| 6 | Inline chair controls, draft retention, and action errors | S | Sonnet; Sol adds status semantics | Yes; command correlation deferred separately |
| 7 | Search, filters, links, and export | M | Sonnet; Sol adds stable links | Yes; client features first |
| 8 | Participant activity and discussion phase | S | Sonnet; Sol refines observations | Yes; M detail extension follows #7 |
| 9 | Guidance delivery and prompt provenance | M | Sonnet; Sol adds correlation | Yes; preferred new observability event |
| 10 | Explicit outcome and artifact references | M | Sol, building on Sonnet’s optional outcome event | Yes; optional reporting |
| 11 | Setup options and effective seat configuration | M | Sol | Yes to defer; Sonnet’s priority objection accepted |

**Already delivered, source re-check:** the page sends this run’s chair token in API requests and the SSE query; the objective-labelled picker follows new tables unless pinned; a Past tables list uses disk-backed `GET /api/history` and `GET /api/history/{id}` across server runs. Replay deduplicates by table ID plus sequence. Ended/stopped views disable guidance, hold, advance, end, judging, and window controls. Sonnet confirmed token, picker and archive delivery; Sol additionally verified the present control disabling and deduplication. These are existing capabilities, not additions requested below.

## Evidence and current boundaries

Read in the requested order: [implementation](../docs/IMPLEMENTATION.md), [functional specification](../README.md), then [page](../crates/roundtable-web/assets/index.html), [HTTP surface](../crates/roundtable-web/src/app.rs), [table creation/commands](../crates/roundtable-web/src/tables.rs), [Roundtable events](../crates/roundtable/src/events.rs), and [ACP events](../crates/acp-host/src/events.rs). Also checked [recording](../crates/roundtable/src/record.rs), command handling in [engine.rs](../crates/roundtable/src/engine.rs), and the earlier record findings preserved in this draft. This update is based on static source inspection, not a fresh browser test.

- The page already renders discussion, topic dividers, expandable work notes, veto reasons, basic seat state, guidance, hold/resume, advance, judging, deliberation window, and end. These proposals extend those capabilities rather than presenting them as absent.
- `GET /api/tables` returns running IDs only; ended handles are removed. `GET /api/history` now scans disk records and returns objective, seat names, start/last times, ended/reason, accepted count and topic count. `GET /api/history/{id}` returns all parseable events except `acp.agent.text` in one response. Listing reads every record on every call; malformed lines are silently skipped and unreadable records omitted.
- Records contain `{seq, at_ms, event, data}`. The recorder keeps ACP text, including thought-marked text, full prompts, completed replies, tools, and Roundtable events, until `roundtable.ended`. Both the Hub history and the history API omit `acp.agent.text`; full text remains on disk. Bare sequence numbers are not unique across server runs; the page has fixed this by keying `seen` as `table_id:seq`.
- `roundtable.ended` has a reason, not a success verdict, summary, or artifact inventory. Records preserve discussion and notes, not historical copies of workspace files. Tool locations are observations, not proof that a file is a deliverable.
- Current SSE subscriptions atomically snapshot memory history and subscribe to future events, preventing a gap during that handoff. They send no SSE IDs; the page handles messages but has no open/error status callbacks. `render()` rebuilds the full feed on each scheduled render, losing expanded details and growing expensive as a run grows.

## 1. Harden shipped past-table review — M remaining

**Chair can:** Open a compact table picker with Running and Recorded sections; browse by date, objective, participants, and ended/interrupted status; open any table as a read-only channel. Read its objective, topics, accepted and vetoed discussion, guidance, notices, work notes, and end reason. An ended table must remain selectable after restarting the server.

**Why:** The owner’s mandatory browse/read requirement now has a working baseline. Long histories, silently skipped damage, and unstable reading position still weaken its reliability. Complete this foundation before building more review features.

**Existing sources:** `<data_dir>/tables/<id>/record.jsonl`, using `roundtable.opened`, `roundtable.topic`, `roundtable.work.finished`, `roundtable.contribution`, `roundtable.chair`, `roundtable.ended`, and timestamps. `data_dir` respects `ROUNDTABLE_HOME`, defaulting to `~/.roundtable`. Current live handles establish which tables are actually running.

**Existing APIs:** `GET /api/history` and `GET /api/history/{id}` already supply listing and replay. Extend these routes with `cursor`/`limit` and ordered record positions, rather than introduce a competing `/events` route. Add completeness metadata (malformed-line counts, unreadable records, incomplete tail) and workspace metadata. Keep current clients working when pagination is omitted. Listing filters/search belong to #7. Discussion pages retain work notes and lifecycle/diagnostic notices; no new core event is required. An optional `view=all` later exposes stored text chunks for explicit diagnostics (#8), not the main feed.

**Design details:**

- Preserve the existing table-plus-sequence deduplication. Add stable record positions for paging; scope reconnect cursors by live server epoch (#2). Keep archive and live reducers from changing the selected table during replay.
- A recorded table absent from the live map with no end event is **interrupted / end not recorded**, not live or successfully completed. Preserve its valid prefix; label damaged or truncated lines and continue through readable entries. Failure in one record must not hide other tables.
- Preserve the shipped disabling of all mutating controls for ended/stopped tables. Explain “stopped” as “not running; end not recorded.” Preserve scroll position and expanded work notes across incoming events and current-run transitions to review.
- Use paged records, incremental rendering, and a bounded rendered window for large histories. Keep stable message anchors and scroll position while loading earlier pages; do not allocate a DOM node for every token event.
- Build listing metadata by scanning records initially and maintaining a rebuildable index from events thereafter; no repeated filesystem polling. The current listing already uses a blocking worker; retain this. Keep existing validated-ID lookup, chair authentication and Host/Origin checks.
- Report HTTP/authentication/read errors explicitly instead of treating an error response as an empty archive. Retain the selected transcript when a history request fails.
- Read completed records immediately; while a live recorder is appending, treat its last incomplete line as pending. Live SSE remains the live source. Any future disk-to-live handoff needs a cursor and deduplication boundary, preserving the current atomic subscribe guarantee.

**Acceptance:** A table from an earlier server run opens with all its recorded discussion, topics and work notes; a truncated record remains readable and labeled; two records sharing sequence numbers both render; no history view can send a command. Outcome review is specified in #3.

## 2. Return-to-table catch-up and connection status — M

**Chair can:** Leave a table, return to a “Since you last read” divider, see counts of new accepted contributions, topic changes, work completions, failures and end/hold transitions, and jump to each. Read older content without being forced to the bottom; a “New activity / Jump to latest” button restores following. See connected, reconnecting, disconnected, and credential-error states separately from table state.

**Why:** Returning after autonomous work should take seconds. A quiet or disconnected browser must not imply that agents stopped.

**Existing sources:** All discussion and lifecycle events plus `at_ms`; browser visibility and `EventSource` open/error callbacks. Store last-read position per table in local browser storage, advancing only when visible messages are actually read, not on receipt. The digest is deterministic event counts with links, not a new model summary.

**New API/transport work:** Add SSE event IDs and an `after`/`Last-Event-ID` resume contract containing server epoch and sequence. On an expired or different epoch, reconcile with #1 rather than discarding new lower sequence numbers. Preserve order and deduplicate across replay/reconnect; transient token chunks may remain live-only. A small authenticated status request on connection/authentication failure can distinguish invalid credentials from a network outage; do not poll engine state. No new engine event is needed.

## 3. Topic navigation, work notes, and outcome review — M

**Chair can:** Open a topic outline and jump to each topic's discussion, chair guidance and work notes. Open a compact review section with all completed work notes, referenced deliverable paths where explicitly named, final discussion links, and the end reason. The same affordance works during a live table and after it ends.

**Why:** Long transcripts bury substantive work. The owner needs to read what was accomplished, not only the last messages on screen.

**Existing sources:** Opening topic from `roundtable.opened`; transitions, index and selection method from `roundtable.topic`; `roundtable.work.started/finished`, `roundtable.chair`, contributions and end reason. Keep full note text readable, searchable and exportable. Existing collapsed work notes become directly discoverable through this index. No new API beyond #1 and no event needed for this recorded-evidence view.

**Truthful outcome labels:** Present “Recorded work notes” and “Final discussion,” never treat the last accepted contribution as an authoritative outcome or consensus. Show “No explicit outcome recorded” when appropriate; the chair can still read the complete evidence. A file mentioned in a note is a reference, not a preserved revision. Structured outcomes are the independent enhancement in #10 and must not delay required archive review.

**Attribution caveat:** Late replies can belong to the topic under which they were prompted, even after a topic change. Existing contribution/work events do not carry topic or prompt IDs. Keep chronology exact and label inferred grouping as such. For exact topic grouping of late discussion/work, extend floor/result/work events with originating `topic_index` and `prompt`/turn correlation; older records retain the caveat. Do not silently attribute every late message to the currently displayed topic.

## 4. Persistent attention strip and optional notifications — S

**Chair can:** See a small, persistent list of seat launch failures, departures, failed turns, refused permissions, warning/error notices, and current held/ended state. Jump from each item to its evidence; dismiss the visual alert without altering the event. Opt into browser notifications and title badges for failure, completion, or work completion while away.

**Why:** Important facts otherwise disappear among pass/skip messages. Notification opt-in affects only the browser; the table keeps running.

**Existing sources:** `roundtable.seat.failed/gone`, `roundtable.turn.failed`, `roundtable.notice`, `acp.permission`, `roundtable.held`, `roundtable.ended`, `roundtable.work.finished`, opening/settings judging flags. Group repeated identical failures and replay historical alerts quietly. No new API/event. Distinguish “judging disabled,” “no JEV key,” and a recorded unjudged contribution rather than treating all as errors. Never infer a stall solely from silence or create automatic holds.

## 5. Inspect judgments and topic selection — S

**Chair can:** Expand a contribution to inspect its three JEV scores, 0.70 threshold, veto reasons and note; filter vetoes; expand topic transitions to see the recorded proposal totals and selection method. See truncation, late and unjudged labels without hovering.

**Why:** Reasons already appear but scores and explanatory notes are largely hidden. Understanding why content was withheld helps the chair guide agents or change judging.

**Existing sources:** `roundtable.contribution` (`scores`, `reasons`, `note`, `judged`, `truncated`, `late`); `roundtable.topic.proposed` and `roundtable.topic` (`scores`, `how`). Page-only; no new event/API. Show missing judgments as unavailable, never zero. Topic totals use summed pairwise confidence, not the contribution threshold. Individual pairwise judgments are not present in these events; displaying them would need a separate event extension and is deferred.

## 6. Inline chair controls, draft retention, and action errors — S

**Chair can:** Send guidance, hold/resume, advance to a supplied topic or request proposals, toggle judging, change the window, and end from inline channel controls. See sending, accepted for processing, or failed status; retain drafts on failure. Show later observed effects without claiming exact command correlation. Guidance drafts belong to their table, so changing the picker cannot accidentally send another table's instructions. Errors appear beside the relevant action instead of blocking browser alerts.

**Why:** The existing controls cover the right actions, but guidance clears before success, advance uses a browser prompt, and HTTP `{ok:true}` only means a command was queued. Event-driven status avoids apparent lost commands and fits embedding.

**Existing sources/API:** `POST /api/tables/{id}/command`; effects arrive as `roundtable.held`, `roundtable.settings`, `roundtable.chair`, `roundtable.topic.polling/topic`, and `roundtable.ended`. The engine defers advance until the floor is free; holding does not cancel agents already working. Explain those semantics beside status. Retain disabled controls in ended/stopped views and disable sending without a selected table or valid connection. Replace `prompt()`/`alert()` with an inline topic composer and action errors; remove the existing blocking end confirmation so End remains a direct chair action. Avoid additional confirmation or approval gates.

**Deferred extension — L, not required for the S feature:** For exact command status across reloads, accept a client-generated `command_id`, echo it in the response, and emit a persisted `roundtable.command.status` with ID, kind, state and reason for queued/applied/rejected/superseded commands. Deferred advance particularly needs this: its current queued state is not observable, and a later advance can replace it. Pending status must survive page reload through event replay. Events report existing engine actions; they do not make action conditional on another approval.

## 7. Search, filters, links, and export — M

**Chair can:** Search a table's discussion and notes; filter by seat, topic, accepted/vetoed, work, chair, or notices; copy a link to a table/message; export a readable Markdown transcript or the original JSONL. Search results include surrounding context and an escape back to the full stream.

**Why:** Review must support finding a specific decision, failure, or work note without rereading a whole run. Exports preserve evidence for other workflows.

**Sources/new APIs:** Existing fields, IDs, timestamps and records. Ship client filters, text search and Markdown export first using the currently loaded record. With #1 pagination, search must say when results cover only loaded content. Add date/objective/seat/status filters and search to the existing `/api/history` listing when needed. For full-record search add `GET /api/history/{id}/search?q=&cursor=` returning matching record positions and context; add a raw download representation to the existing record endpoint for original JSONL; its current response omits text chunks and malformed lines, so serializing that response is not an original-record export. Markdown is rendered from recorded discussion events and includes objective, topics, work notes and end reason; raw diagnostics are optional. Stable links use table plus record position and resolve through #1, using the current session's chair credential; never include tokens in copied links. No new engine event.

## 8. Participant activity and discussion phase — S

**Chair can:** Distinguish a participant holding the floor, independently working, late but still running, ready, or gone; see elapsed time since last observed activity; see the latest tool title. An optional M detail extension expands recent tool activity with status and locations. See current round, topic polling, and the deliberation-window boundary. The detail extension also inspects actual configured model/mode rather than only the requested harness label.

**Why:** Autonomous independent work can resemble inactivity. The current seat card shows only a clipped live reply or last tool title, and omits useful existing events.

**Existing sources:** `roundtable.floor` (`round`, allowance), `roundtable.round`, topic polling/proposals, skip/work/seat events, `acp.agent.tool` (`tool_call`, status, locations), `acp.prompt.sent/completed/failed`, `acp.harness.started/exited`, `acp.session.opened/config`, and timestamps. No new event/API beyond archive access. Correlate tool updates by tool-call ID and prompt. Keep raw prompts, stderr and thought-marked text in explicit diagnostic detail, outside the main discussion. Tool events, full prompts and completed replies are already returned by the shipped history API but lack a page inspector. Thought-marked text is on disk but omitted by that API; its archived display needs #1’s optional `view=all`, not a recorder change. Deliver basic status first; schedule this M detail extension after #7.

**Limits:** Label time as “last observed activity,” never “hung.” A window expiry skips a seat; it does not kill its work. A display countdown is approximate when scheduling the turn and publishing the floor event differ. Existing events expose no precise JEV request lifecycle; an exact “awaiting judgment since…” indicator would require new judgment-started/completed events. AgentSight resource/network tracing is not implemented and is outside this GUI proposal.

## 9. Guidance delivery and prompt provenance — M

**Chair can:** See which seats have had specific guidance included in a subsequent prompt, and inspect the recorded prompt for context. Distinguish “queued for next turn,” “included in prompt,” and failed delivery. Do not claim an agent read, understood, or obeyed it.

**Why:** `roundtable.chair` currently proves only that guidance entered the table. A working or late participant may not receive it immediately.

**Existing sources:** `roundtable.chair` and `acp.prompt.sent` with full prompt text; prompt failure/completion. Prompt inspection is available from records with #1 and needs no core change. Avoid text matching as a reliable delivery receipt.

**New events:** Give chair guidance a stable `guidance_id` (independent of the deferred command-status extension in #6) and emit `roundtable.guidance.delivered {guidance_id, seat, prompt}` when it is included in a successfully dispatched prompt, with explicit failure status if dispatch fails. Persist the event and use it for replay. Older records show delivery as unknown, with prompt evidence available. This adds observability, no acknowledgement gate.

## 10. Explicit outcome and artifact references — M

**Chair can:** Read an explicitly reported result and a list of deliverable paths with descriptions, linked back to the reporting participant and topic, in the review section from #3.

**Why:** Recorded work notes satisfy immediate review, but unstructured messages cannot reliably identify final deliverables. An end reason must never stand in for success.

**New event/tool:** Add an optional participant reporting tool that publishes `roundtable.outcome {seat, topic_index, summary, artifacts:[{path, description}]}`. Accept reports during normal operation and independent work, without pausing the discussion, requiring chair approval, or blocking end when absent. Render competing or superseding reports with provenance; do not synthesize consensus. Old records retain “No explicit outcome recorded” and full work-note review.

**API/storage boundary:** This M covers references and recorded summaries only. A local file's content can change or vanish after a run. Durable historical artifact content requires copying reported versions into table-owned storage plus a scoped read/download API, an additional L feature. Current tool locations and text mentions do not provide that guarantee. No arbitrary filesystem browsing route is proposed.

## 11. Setup options and effective seat configuration — M

**Chair can:** Set an optional filesystem scope distinct from shared workspace; supply supported per-seat settings such as mode through a compact advanced section; discover OpenRouter model choices instead of relying solely on fixed hints. After startup, inspect advertised choices and effective settings, including setting warnings.

**Why:** `CreateTable` already accepts `scope` and seat `settings`, but the page exposes neither. `/api/models` exists but the page does not use it. Requested settings and effective settings can differ.

**Existing sources/API:** `POST /api/tables` (`scope`, `seats[].settings`), `GET /api/models`, `GET /api/harnesses` defaults, `acp.session.opened/config`, seat failures and notices. Scope remains optional and follows the current engine policy. The catalog is specifically OpenRouter's, not a universal harness-model list. Before launch, the API has no general way to query every harness's session choices; allow explicit settings and show choices when actually advertised rather than inventing universal availability. No new engine event or mandatory setup gate.

## Delivery sequence and exclusions

Deliver #1’s remaining archive hardening with #3’s review essentials, then #2’s return/read continuity. #4–#6 are small improvements that can ship independently while that work proceeds. Follow with #7 and #8; #8’s M diagnostic detail extension follows #7. Prefer #9 when adding new observability events. #10 is optional outcome reporting and never delays reading existing discussion and work notes. #11 is deferred setup work, with Sol accepting Sonnet’s priority objection. Exact command correlation (#6, optional L) and durable artifact snapshots (#10, optional L) are separate later projects.

Sonnet’s review changed the initial draft: judgments moved from rank 8 to 5; page-only chair controls were separated from engine command tracking; activity was split into basic status and later detail; setup moved last. Sol accepts these changes. No feature-level disagreement remains. Static re-check also corrects Sonnet’s interim notes: review controls **are** disabled, and deduplication **is** table-scoped in the present page.

Defer seat mute/restart/add commands: those change orchestration semantics and have lower demonstrated value than making existing steering reliable. Defer an accolades dashboard: feedback already appears in the stream, and a new cross-table metrics surface does little for see/steer/review. No automatic stall termination, approval queues, mandatory summaries, or heavy dashboard is proposed.

Acceptance scenarios for future implementation: cross-restart archive discovery; equal sequence numbers in different tables; ended versus interrupted records; partial/damaged lines; paged long replay with preserved scroll and expanded notes; disabled archive controls; reconnect without duplicate/missing discussion; failed commands retaining table-specific drafts; pending advance without false application claims; late replies spanning topic changes. Source inspection verified the shipped baseline and API/event dependencies; these scenarios were not executed. No application code was changed for this proposal.
