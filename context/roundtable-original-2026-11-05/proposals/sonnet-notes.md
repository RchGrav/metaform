# Sonnet notes: page and chair-control gaps (input for Sol's GUI-FEATURES.md)

Evidence read: index.html (368 lines), app.rs, tables.rs, roundtable events.rs. Facts that drive ranking:
- `GET /api/tables` returns only LIVE ids; `Hub.history` is memory-only and `acp.agent.text` is dropped. A restarted server shows nothing of old tables; the page has no list/replay. record.jsonl exists but no route reads it. (Sol owns the API design; page side below.)
- Page state is rebuilt per `seq` from `/api/events` history; `render()` rebuilds the whole feed DOM on every event (O(n) per event; long tables will lag).
- `scores` arrive on every contribution but are never rendered. `acp.agent.tool`/thoughts only show as one live line per seat.

## Proposals (priority order; S/M/L)
1. **Past-tables browser + read-only replay (L; owner requirement).** Left list of ended tables (objective, seats, topic count, ended reason, date); open one to read the same channel view. Page reuses `apply()` unchanged: feed record lines through it into a read-only table (buttons disabled, status "ended"). Needs NEW: `GET /api/history` (scan `tables/*/record.jsonl`: opened/ended/topic lines) and `GET /api/history/{id}` (stream/return lines). No new event. Must work across server restarts.
2. **Topic outline + outcome view (M).** Per-table jump list of topics (`roundtable.topic` index/how/scores) and collapsible per-topic work notes (`work.finished`) and chair messages; "Outcomes" = last accepted contributions per topic plus workspace path. Works live and in review. Uses existing events. A final-outcome/summary event at `ended` (NEW, optional: `roundtable.ended` only has `reason`) would let review show "what was produced" without inference.
3. **"Since you left" catch-up + unread marker (S).** Remember last-seen `seq` per table (localStorage); on return show a divider and a digest (N accepted, topics changed, vetoes, failures, held/ended) with jump. Fits the walk-away chair and channel view. Existing events only.
4. **Attention strip / notifications (S).** Surface things needing the chair without scanning: seat failed/gone, turn.failed, permission refused, JEV not configured, table idle/waiting for hold. Browser title badge + optional Notification API. Existing events (`seat.failed`, `seat.gone`, `turn.failed`, `acp.permission`, `notice`).
5. **Guidance state: pending vs delivered (S/M).** Chair sees whether guidance was delivered at each seat's next turn. Needs NEW event (`roundtable.guidance.delivered {seat}`); currently only `roundtable.chair` echo.
6. **Show JEV scores and veto reasons inline (S).** Render `scores` per contribution (compact chips), filter to "vetoed only"; helps steering/judging decisions. Existing data, page-only.
7. **Replace prompt()/confirm()/alert() with inline chair controls (S).** Advance-with-topic composer, hold with reason, end confirm inline; errors as channel system messages. Page only; matters for embedding in a chat channel.
8. **Round/clock indicator (S).** Current round, whose turn, deliberation-window countdown from `floor`/`round` events (window_secs known); "topic may advance" from `roundtable.round`. Existing events.
9. **Incremental rendering + virtualized feed (M).** Append instead of rebuild; needed before long runs/replays. Page only.
10. **Search / filter / export (M).** Text search, per-seat and per-kind filters (accepted, vetoed, work, chair); export a table to Markdown. Page-only for loaded table; export of past tables via history API.
11. **Live detail drill-down (M).** Per-seat expandable tool-call/thought stream (`acp.agent.tool`, `acp.agent.text` with `thought`); live-only today since text is not kept. Persisting needs record change (NEW).
12. **Seat control (M, NEW command).** Mute/pass or restart a failed seat; add a seat mid-table. Needs new Command; ranked low (adds control surface, not asked for).
13. **Accolades view (S).** Read `accolades.jsonl` via NEW `GET /api/accolades`; low value for steering.
Not proposing approval/gate features (owner constraint).

---
# Sonnet assessment of GUI-FEATURES.md (draft 2026-11-05)

Verdicts: AGREE / AGREE-with-change / OBJECT. Corrections accepted: disk records hold ACP text, replay needs scoped identity (my "feed lines through apply() unchanged" was wrong on the global `seen` set), last contribution is not an outcome.

1. Archive: AGREE. Scope is right; one tightening: ship list + discussion view first, `view=all` and search later.
2. Catch-up + connection status: AGREE. SSE `Last-Event-ID` with epoch is the right fix for reconnect.
3. Topic nav/work notes/outcomes: AGREE. The "no explicit outcome recorded" label is correct and honest.
4. Attention strip: AGREE.
5. Inline controls + command status: AGREE-with-change. Inline controls, draft retention and per-table drafts are S and high value. The persisted `command.status` event with `command_id` is a larger engine change for modest gain; split it out as optional (L), and keep the page-only part as the M.
6. Activity/phase: AGREE-with-change. Seat state, last-activity time and round/phase are useful (S). The tool-call drill-down and effective-config display are separable; do them after #7.
7. Search/filter/export: AGREE. Client-side filter and Markdown export first; server search later.
8. Judgments/topic selection: AGREE on content, OBJECT on rank. It is S, page-only, and uses data already sent. It should rank above #5 and #6, next to #4.
9. Guidance delivery: AGREE-with-change. Wanted, but it needs a new event, so rank below the page-only items. It also answers the chair's real worry ("did my guidance land?") better than #5's status event does; if only one new event ships, ship this one.
10. Setup options: OBJECT on priority. It is about starting tables, not seeing, steering or reviewing, and sits furthest from the brief. Keep, but last, and consider moving it to "later".
11. Explicit outcomes: AGREE as optional. It needs a new participant tool; the owner wants no extra logic, so keep it opt-in and never required.

Ranking I propose: 1, 2, 3, 4, 8, 5(page part), 7, 6, 9, 11, 10. Deferrals (seat mutation, accolades): AGREE.

---
# Sonnet re-check after builder changes (2026-11-05)

Verified in code: token sent (`authed`, EventSource `?token=`); table picker labelled by objective + status; `GET /api/history` (scan of every record.jsonl: id, objective, seat names, started/last ms, ended+reason, accepted count, topic count) and `GET /api/history/{id}` (whole record minus `acp.agent.text`, unpaged); page `loadPast`/`openPast` replays lines through `apply()`; ended/stopped status shown, controls untouched.

Consequences for the proposal:
- #1 is now PARTLY DELIVERED. Reword as "Past tables v1 shipped; remaining gaps": (a) list re-scans and parses every record on each call and each table end, no paging/search/filter by date or seat; (b) history_table returns the whole record in one response (no cursor); (c) damaged lines are skipped silently, unlabeled; (d) a past table opened via `openPast` shares the global `seen`/state with live tables (check `seen` is per-table); (e) controls are not disabled in review of ended/stopped tables; (f) thoughts/streamed text are dropped from history, so the "actually said" drill-down for past tables needs `view=all`; (g) "stopped" (no end event) is labelled but not explained. Size of remainder: M, not L.
- Rank: keep archive remainder at 1 (hardening is cheap), then 2,3,4,8,5(page part),7,6,9,11,10 as before.
- Token is delivered; drop any "page sends token" item. Alert() on missing token remains an inline-control candidate (#5).
