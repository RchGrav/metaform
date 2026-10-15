---
name: metaform-module-signals
description: Use when dispatch drops a module's signal.raised payload.
category: development
---
# Signal payloads that dispatch keeps

Never put a key named `active` in a `signal.raised` payload. Dispatch's collector reads `active` as its own raised-or-cleared flag and returns early, so the signal is dropped while its delivery still reads `completed`. Name the agents-and-tickets field `working` instead, as autoticket does.

- Before naming a payload key, grep `src/metaform/modules/dispatch` for the keys its collector reads, and avoid every one of them.
- A publish returns one result per subscriber, such as `[{'module': 'dispatch', 'status': 'completed', 'result': None}]`. `completed` means dispatch ran, not that it kept the signal.
- Prove delivery in a scratch home: `metaform enable dispatch` first (it is off by default and `dispatch signals` answers "Module dispatch is off"), trigger the signal, then read `metaform dispatch signals --json` and check the keys that arrived.
- To tell the system agent that a feature the person set up is broken, publish `signal.raised` with `signal: 'setup-not-working'` and the fields `module`, `key`, `feature`, `set_up`, `look` and `report`. Dispatch keeps it under the producer's key and clears it with `{key, clear: True}`. Only the system runner takes it, as a queued turn at start, after any turn in flight, and when a map change reaches it. Never surface the same problem to the person through a banner or log line as well.
