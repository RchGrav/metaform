---
name: dispatch-session-resume
description: Use when editing dispatch resume, retry or stay-connected.
category: development
---

# Automatic resume runs only for sessions this home started

Every automatic resume (the supervisor's retry, Stay connected, Call's resumed conversation, automatic recovery) must pass over a session row whose `origin` is not this home's `origin()`. Explicit `dispatch resume <id> session=<sid>` stays unchanged and is the only path for other homes' rows.

- Check ownership with `foreign(row)`; never decide from the row's `state` or `how` alone. A dead runner reads as ended ("the runner is no longer running"), which is not the person's stop, so a resume path that trusts that read starts agents in a copied store.
- Any code that writes a session row sets `origin`: `runner.py` take() on insert and on resume, and `serve.py` open(). A new writer that omits it creates rows every home treats as foreign.
- Legacy rows (no `origin`, before sessions table version 13) are never resumed automatically. Before landing a change of this kind, count the live candidates in the real home, read-only, and say in the report what will stop being resumed.
- A test that seeds a session row by hand and expects a resume must include `'origin': module.origin()`, or the row is foreign and the test proves nothing.
- Prove a guard with a copied home: `shutil.copytree` the home, `monkeypatch.setenv('METAFORM_HOME', copy)`, a fresh context and `Store` per home, then mutate the guard in a `/tmp` copy as `verify-guard-test-by-mutation` describes. The copied home must start nothing.
- Each such change gets a dispatch `CHANGELOG.md` Unreleased entry and a sentence in the README's "Supervisor and budgets" section. Running servers and runners keep the old code until restarted.

Incident and file map: `references/copied-home-incident.md`.
