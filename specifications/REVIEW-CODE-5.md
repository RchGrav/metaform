# Code review, fifth round

Branch `chassis`, reviewed 2026-09-26 by a critic agent on Sonnet, at `93d549a` with the working tree. Scope: `git diff d8a645f -- src`, step 22 of `BUILD-LOG.md`: the web module, `query.py`, `settings.py`'s `_declaring_module`, `data/reads.py`'s `children('')` and `peel_preview`, `data/corrections.py`'s `preview`, the preview records, the per-store write lock and busy wait, and a module's default verb. Bar: `rich/code_quality_standards.md`, VIEW-001 to VIEW-015, BASE-029, BASE-035, STORE-006, STORE-017, STORE-025, STORE-028.

## Count

| Severity | Count |
|---|---|
| Critical | 0 |
| High | 0 |
| Medium | 0 |
| Low | 1 |

## Tool results

- `.venv/bin/pyright`: 0 errors, 0 warnings, 0 informations.
- The web, correction, read and CLI tests: 98 passed, browser tests included. `METAFORM_HOME` pointed at a scratch folder; the real home and its server on port 7433 were not touched.

## Findings

1. Low. `src/metaform/modules/web/tests/test_probe_tmp.py`, untracked, imported every web test a second time and added a test with no assertion. It was a probe of the 2D layout, made and deleted during the arrow-key fix; the review ran while it existed. Resolved: deleted before any commit.

## What the reviewer checked and found holding

- The server: the Host check, loopback names and the wildcard's port-only check with the token; the token checked before any GET or POST; a write needs the request's own Origin and a JSON body; `PUT`, `PATCH` and `DELETE` answer 501; no GET reaches a store write.
- The page sets store text as text nodes only; the 3D tooltip is serialized from text nodes, so the browser escapes it.
- `corrections.preview` against `corrections.peel`, row by row: add, remove and change, the move back, the relocation removals and the items that show again or become orphaned.
- `children('')`, `_declaring_module`, the per-store write lock with the 30-second busy wait, and the default verb, each against its record.
- Every vendor file's SHA-256 matches `vendor/README.md`.
- Cross-platform: the detached start on POSIX and Windows, exclusive port binding on Windows, a fixed content-type table, and `stop` removing the run file itself.
