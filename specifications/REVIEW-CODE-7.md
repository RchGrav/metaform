# Code review, seventh round

Branch `chassis`, reviewed 2026-09-26 by a critic agent on Sonnet, at `bd23785`. Scope: `git diff d21920f -- src`, history, its MCP tools and the 3D label release, and also `metaform uninstall`, `7eb1b6e`, and `metaform import wheel=`, `e9676ab`, which no earlier round covered. Bar: `rich/code_quality_standards.md`, MCP-020, BASE-025, PROJ-010 to PROJ-024, CLI-031, MCP-004, Q53.

## Count

| Severity | Count |
|---|---|
| Critical | 0 |
| High | 2 |
| Medium | 2 |
| Low | 0 |

## Tool results

- `.venv/bin/pyright`: 0 errors, 0 warnings, 0 informations.
- History, install, exchange and MCP tests: 57 passed. Every experiment used scratch homes, scratch user folders and scratch repositories.

## Findings, each fixed with a test seen failing first

1. High. With `core.autocrlf=input` and a file committed with CRLF, a clean repository made a first variant on `add origin`, since dirtiness came from comparing `git archive`'s bytes with the working tree's. The build log's claim that the two always match was wrong. Dirtiness is now `git status --porcelain`, PROJ-012.
2. High. A variant's folder was moved into place before its rows committed, so a crash between the two left a folder no row named, and every later variant of that origin failed with a bare `OSError`. The payload is now renamed to `.pending-<id>` inside the transaction and into place after the commit; a read finishes a move a crash left undone, and a leftover for the next id is cleared, PROJ-023.
3. Medium. Two `add origin` calls at once for new content crashed with a unique-key `IntegrityError`, since the same-content check and the insert were in separate transactions. They now share one write, and the suffix is taken again if another project's origin of the same content took it, PROJ-014.
4. Medium. `remove=true` on a folder that is not a git worktree collected and kept the variant, then refused the removal, and the next step it named made a second copy. The check now comes first and a refusal collects nothing, PROJ-017.

## What the reviewer checked and found holding

- `apply_diff` against real `git diff --no-index` output, with and without final newlines, empty and non-empty files, and a 10 MB file edited at the start, the middle and the end.
- Byte and mode identical reconstruction of a modified binary, an added, a removed and a renamed file, a folder only the variant has, an empty file, and the executable bit set and cleared.
- BASE-025's two acceptance cases, live.
- The uninstall tests' coverage of MCP-020, and the worktree check against the main checkout and a plain folder.
- The 3D label release, read through.
