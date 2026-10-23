---
name: metaform-web-gui-hang-diagnosis
description: Use when a Metaform web page freezes or hangs on a click.
category: development
---

# Diagnosing a frozen Metaform page or a growing web server

Start from the live server's own record and the page's real calls, never from guessed paths or code alone.

- Read the slow-request log first: `~/.metaform/run/web.log` holds lines like `Slow: GET /api/... has run 3 s, waiting on ...`, which name the endpoint and what it waited on.
- Find the real route names in `src/metaform/modules/web/server.py` and the fetch calls in `src/metaform/modules/web/page/app/` before probing. A guessed path answers `404` in milliseconds, which says nothing about speed.
- Probe the endpoints the clicked control calls, with the nonce from `~/.metaform/run/web.json`. Record each response's size and time; a multi-megabyte payload or a 3 s+ wait is the lead.
- Sample the server's memory from `/proc/PID/status` (`VmRSS`, `VmHWM`, `Threads`, open fds) at two moments. Threads and fds small with RSS large points at Python heap held between requests: find what the server keeps in module or instance state.
- The live process runs the code it started with. A fix in the working tree shows on the live page only after a restart the person agrees to.
- Never attach to, signal or restart the person's live server to measure it. Measure a test server or the code path instead.
- Store-level cost (a click that waits on the base, not the server): copy the live home with SQLite's backup API over read-only connections (`file:...?mode=ro`) into a scratch folder, point `METAFORM_HOME` at the copy, and run timing scripts with `.venv/bin/python -I` against it. Never open the live files for writing and never time against the live server. Time a write and a read in separate threads: a read stalled behind another process's write lock shows the freeze directly.
- A restart that reports "The web GUI said it was ready but does not answer" while `/api/server` answers in milliseconds a minute later is a starved server, not a dead one. The page reconnects the moment the new server is up and fires its burst of reads; the readiness probe (`answering()` in `modules/web/__init__.py`, a 2 s timeout) queues behind them. Find the burst in `web.log`, then fix its cause: batch per-item reads into one call (`/api/lookup` takes several refs at once), and make the page request only what it draws. Do not lengthen the probe's timeout to hide the burst. The server now starts answering requests before it starts each project's background services and agent starter (`web/server.py`, the start path), so a readiness failure after a restart is checked against that order first.
- Change detection on a read must compare only the fields the view shows. A field that changes on every read (`age_seconds`) makes every row look changed, so every card redraws on every event. Exclude such fields from the compare and keep the row object when only they differ; a check should prove a row that differs only in age is kept.
- Board load on a page drawn from many items: one batched read per drawn set, not one request per card. Count the requests a page opening sends (about 926 per board open was the fault) before and after the fix.
