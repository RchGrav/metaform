---
name: metaform-map-write-provenance
description: Use when tracing which agent or ticket wrote a map change.
category: development
---

# Trace who wrote a map change from the store's ops log

Find the writer in the project store's `ops` table, opened read-only. Each map write there carries its session id and time. Do not trace through the page or any write path.

- Open `~/.metaform/projects/{project folder}/{project name}.metaform.sqlite3` with `sqlite3.connect("file:{path}?mode=ro", uri=True)`.
- Find the creating row for a layer by its name: `select seq, session_id, at, id, data from ops where kind='layer' and op='add' and data like '%{layer name}%'`.
- Count writes by hour, session and kind for a layer id: `select substr(at,1,13), session_id, kind, count(*) from ops where layer_id=? group by 1,2,3 order by 1`.
- An item's extra data may carry `"by": "work {work id} session {session}"`. That ties the writer to a ticket; read the ticket with `metaform map work`.
- Where that `by` field is absent, the change has no ticket link. Say so; do not infer the ticket from timing.

The page does not show any of this yet: a ticket card does not list its map writes, and agent-made layers were created with no provenance.
