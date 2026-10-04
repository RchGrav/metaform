# Code review, sixth round

Branch `chassis`, reviewed 2026-09-26 by a critic agent on Sonnet, at `d21920f` with the working tree. Scope: `git diff 99940af -- src`: the store read `graph` and the server serving it, the server's bind without a host name lookup, the 3D drawing in `page/scene.js` and `page/layout.js`, the Mermaid limit, `vendor/README.md`, and `reports.py`'s file lock. Bar: `rich/code_quality_standards.md`, VIEW-003, VIEW-004, VIEW-005, VIEW-008, VIEW-010, VIEW-012, STORE-025, BASE-045, Q51, Q52.

## Count

| Severity | Count |
|---|---|
| Critical | 0 |
| High | 0 |
| Medium | 1 |
| Low | 0 |

## Tool results

- `.venv/bin/pyright`: 0 errors, 0 warnings, 0 informations.
- The web, read and report tests: 32 passed. The real home and its server were not touched; the reviewer's one browser probe ran capped at 6 GB on a static fixture.

## Findings

1. Medium. `page/scene.js` hid a label whose element left the chosen set but never removed it, and a view change kept the old view's labels, so the label map and its spans grew for the life of the page and each choice walked all of them, defeating VIEW-010's budget of 80. Resolved: a label leaves the page when its element leaves the chosen set, and a view reset clears them all. `drawn().labels` now counts every label span, and the drawing test zooms around a 3,000-element map and checks at most 80 exist; before the fix it found 384.

The reviewer also noted that the report test's slow `exists` patch had become inert, since the lock replaced the check it slowed; it is removed.

## What the reviewer checked and found holding

- `graph` builds each element, join and subtype with the same view functions the separate reads use, threads `raw` the same way, and cannot skip or repeat an element across pages, since the cursor is a strict `>` on a unique address.
- The server's old walk is gone; every read goes through `query.call`; no trace of 3d-force-graph is left.
- The report lock: `flock` on POSIX, a lock on byte 0 on Windows used by every writer, and a first write told from a later one by the file's size under the lock.
- No store text reaches the page as markup; a probe of a malformed address through the bundled Mermaid threw a parse error the page already catches.
- Every SHA-256 in `vendor/README.md` matches; the wheel test confirms the new folders ship.
- The draw objects are a fixed nine whatever the size, disposed before rebuilding, rebuilt only on doubling and at the end.
