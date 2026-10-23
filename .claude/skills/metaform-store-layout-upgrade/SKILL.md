---
name: metaform-store-layout-upgrade
description: Use when bumping a Metaform store layout or schema_version.
category: development
---

# Verify a store layout change read-only, per store, before and after

A layout bump runs inside each store's own upgrade transaction, under its lock, after its backup. Verify it from outside without writing anything.

- Count stores at each version with a read-only connection: `sqlite3.connect(f"file:{path}?mode=ro", uri=True)` and `select value from meta where key='schema_version'`. Run it with `.venv/bin/python -I <script outside the repo>`, never a writable open.
- Stores live under `~/.metaform/projects/*/*.metaform.sqlite3`. Each upgrade writes one backup under `~/.metaform/backups/upgrade-<version>/<timestamp>/`. Expect one backup per store that moved.
- Record the before and after counts, and any moved-item counts from the backup's report file. The report holds counts and ids only; do not copy note text into the ticket.
- A store that is not opened stays at its old version. Say so in the resolution rather than forcing an open.
- Before the bump is trusted, prove it on a fixture: build a map from the previous layout's code, run the new code's upgrade on it, and check the moved items against the old records.

Layout-23 specifics (base notes moved to the critic layer): `references/layout-23-verification-2026-10-21.md`.