# Code and test review, fourth round

Branch `chassis`, reviewed 2026-09-25, at commit `7b232f1`. Scope: `git -C /home/rich/metaform diff b0a36ee..7b232f1 -- src`, Step 20 of `specifications/spec/BUILD-LOG.md`: the map module's knowledge verb keeping an unread noun in `extra` or naming it as ignored, a report row's size kept at the largest recorded, and the MCP server's schemas for its own chassis tools. The bar is `specifications/code_quality_standards.md` and the spec records the step cites: BASE-043, BASE-044, STORE-043, MCP-003. Round three, `REVIEW-CODE-3.md`, found nothing.

Acting also as test reviewer, QUAL-007, for `git -C /home/rich/metaform diff b0a36ee..7b232f1 -- tests src/metaform/modules/*/tests`: `tests/test_reports.py`, `src/metaform/modules/map/tests/test_map.py`, `src/metaform/modules/mcp/tests/test_mcp.py`. Each test is judged only against the spec records it names, asking whether it would fail on a build that gets the requirement wrong.

## Count

| Severity | Count |
|---|---|
| Critical | 0 |
| High | 0 |
| Medium | 1 |
| Low | 1 |

One code finding, Medium. One test finding, Low.

## Tool results

- `.venv/bin/pyright` from the repo root: 0 errors, 0 warnings, 0 informations.
- `.venv/bin/python -m pytest -q -p no:cacheprovider tests/test_reports.py src/metaform/modules/map/tests/test_map.py src/metaform/modules/mcp/tests/test_mcp.py`: 40 passed, 0 failed, in 126.89s.

`METAFORM_HOME` was set to a scratch folder under `/tmp` for every command; `~/.metaform` was not touched.

## Code findings

### 1. `op=correct` drops a noun it does not read instead of keeping it in the new record's extra

- Severity: Medium.
- Where: `src/metaform/modules/map/__init__.py:255-269`, `_unread`.
- What is wrong: the function decides whether an unread noun is kept in the new record's `extra` or named as ignored by testing `'extra' in READS.get(op, frozenset()) and op.startswith('add-')`. `correct` has `extra` in its read set, `READS['correct'] = frozenset({'id', 'reason', 'evidence', 'remove', *FIELDS})` and `FIELDS` includes `'extra'`, and `correct` writes a new row: `src/metaform/data/layering.py:275`, `cursor = tx.db.execute(f'INSERT INTO {spec.table}({names}) VALUES ({marks})', ...)`, the same insert-a-new-version shape as an `add-*` op. But `op.startswith('add-')` is false for `'correct'`, so the function falls to the ignored branch regardless. I ran `_unread` directly against a `correct` call carrying `flag='broken'`, a noun the verb declares but `correct` does not read:
  ```python
  ctx = FakeCtx({'op': 'correct', 'layer': 'corr', 'id': 'x1', 'reason': 'bad', 'flag': 'broken'})
  notices = _unread(ctx, 'correct')
  # ctx.nouns after: {'op': 'correct', 'layer': 'corr', 'id': 'x1', 'reason': 'bad'}
  # notices: [Notice(where='flag', message='op=correct does not read flag; it was ignored.')]
  ```
  `flag` is popped and gone; it is never offered to the new correction row's `extra`.
- Breaks: BASE-043's build text, "kept in the new record's extra with a notice when the operation adds a record, and otherwise named in a notice as ignored, BASE-044." The condition the spec states is whether the operation adds a record, not whether the operation's name starts with `add-`. `correct` adds a record and is wrongly on the ignored side of that line.
- Why it matters: BASE-044 is confirmed and its stated purpose is that nothing an agent submits is silently lost when there is a place to keep it. A correction call that also carries a noun the verb declares but `correct` does not use, such as `flag=` meant for an element or join, loses that value outright; the notice says it happened, but the value itself never reaches the record it was written into, where the other three implemented ops, `add-element`, `add-join`, `add-subtype`, `add-property`, `add-item`, would have kept it. No test exercises this: the new test in `test_map.py` covers only `add-property`'s kept-in-extra path and `finish`'s ignored path.
- Fix: base the branch on whether `op` writes a new row with an `extra` column, not on the op's name. Since every op whose `READS` includes `'extra'` and that adds a record is exactly `{'add-element', 'add-join', 'add-subtype', 'add-property', 'add-item', 'correct'}`, either name that set directly or drive the check from whether the op both has `'extra'` in `READS[op]` and is not `'edit'`. `edit` also reads `extra` but updates in place rather than adding a row, so it stays on the ignored side.

## Test findings

### 1. `tests/test_reports.py`, `test_a_reports_recorded_size_never_falls_below_one_already_recorded`

Marked `STORE-043` and `BASE-045`.

```python
store.save_report('run-1-feedback.md', 'run-1', 'feedback', 717)
store.save_report('run-1-feedback.md', 'run-1', 'feedback', 207)
assert store.report('run-1-feedback.md').size == 717
```

What it protects, correctly: STORE-043's own build line, "the row's `size` never falls below a size already recorded: when several writers append at once, the row keeps the largest size any of them saw." It calls `Store.save_report` twice with a larger size then a smaller one and checks the row keeps the larger. It would fail on a build that reverted `reads.py`'s `ON CONFLICT(report_id) DO UPDATE SET size=MAX(size, excluded.size)` back to a plain `size=excluded.size` overwrite. That part is a real, well-aimed test.

What it does not protect, as marked: BASE-045 is that feedback and intake reports are saved as separate files, listed, readable, and referenced from a layer's provenance, with `--debug` and `--report` deciding what agents are asked for. This test never touches a report file, `list_reports`, `read_report`, or provenance refs; it calls `Store.save_report` directly with two hard-coded sizes and reads the row back. A build that broke BASE-045 in any of its own ways, files not separated by kind, not listed, not referenced from provenance, `--debug`/`--report` not gating what agents are asked for, would still pass this test. The `BASE-045` marker names a requirement this test does not exercise.

Fix: drop the `BASE-045` marker and keep `STORE-043` alone, which is what the test actually protects.

## What holds up

The `reads.py` `MAX(size, excluded.size)` change is correct and matches STORE-043's stated rule; SQLite computes it inside the same statement as the insert, so it is safe under the one-transaction-per-write model STORE-006 already requires. The MCP server's added descriptions on `feedback`, `list_reports` and `read_report` match MCP-003's requirement that every property of the chassis's own tools carry its help as `description`; `set`'s properties already carried theirs through `setting_schema`. `_unread`'s handling of every other knowledge operation, `add-element`, `add-join`, `add-subtype`, `add-property`, `add-item`, `add-ref`, `add-plan`, `edit`, `remove`, `finish`, `peel`, `discard`, matches what `_knowledge` actually reads for each, checked noun by noun against `READS`. The new MCP schema test and the new map knowledge test are each well-built for what they claim, apart from the one marker above.
