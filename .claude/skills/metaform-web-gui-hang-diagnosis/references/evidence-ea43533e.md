it always says this now

Error: The web GUI said it was ready but does not answer: 2026-10-19T08:57:18+00:00 Watchdog 1950612: keeps the server, process 1950615, on port 7433
Next: metaform web stop

…the server (pid 1950615) answers /api/server in 4 ms a minute later. Likely cause: the open page reconnects the moment the new server is up and fires its ~926 /api/lookup requests plus whole reads, so the readiness probe (web/__init__.py answering(), GET /api/server, timeout=2) waits behind them and gives up. Confirm that from the code and log, then fix the cause, not the probe's timeout

…2. **Cause, page.** Every agent event redrew the whole board. `drawBoard` … rebuilt all 483 cards … 4. **Fix, server.** … 8. **Found, not fixed:** `live/ops.js:273` compares tickets including `age_seconds`, so every ticket read counts as changed.