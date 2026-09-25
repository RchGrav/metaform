# Build log

One entry per build step of `00-index.md`: the step, the records it satisfies, the tests added, the commit, and the questions it raised.

## Step 1: storage and the data access object

- Records satisfied: STORE-001 to STORE-041 at the data access object, including the settings and module-state tables of the base database, built against the storage text of commit f8dd39a (paged reads, no attachment at a bare type address, `moved` and `stack_at`, `layer_fields`, no transitive flag, list settings one row per member). With them, the storage side of LAYER-001 to LAYER-007, LAYER-010 to LAYER-012, MAP-002, MAP-003, MAP-010, MAP-013, MAP-015, MAP-016, MAP-020 to MAP-022, MAP-030, MAP-031, MAP-044 and MAP-045.
- Tests added: `tests/test_home.py`, `tests/test_store_map.py`, `tests/test_store_layers.py`, `tests/test_store_corrections.py`, `tests/test_store_reads.py`, `tests/test_store_operations.py` (every STORE-024 operation's rows, every listed error, and the query plan of every write), `tests/test_store_exchange.py`, `tests/test_store_challenges.py`, `tests/test_store_concurrency.py`; shared helpers in `tests/storekit.py`. 202 tests, each marked with its requirement and `kind('fixture')`. Whole suite: 264 passed. No existing test was removed in this step.
- Not yet covered: STORE-005's timing thresholds on a store loaded to a million items. The plan test covers every read and write; the timed load is left for a separate run with the storage-proof loader.
- Commit: bbd2fce.
- Questions raised: Q1 to Q8 in BUILD-QUESTIONS.md.

