# Build log

One entry per build step of `00-index.md`: the step, the records it satisfies, the tests added, the commit, and the questions it raised.

## Step 1: storage and the data access object

- Records satisfied: STORE-001 to STORE-041 at the data access object, including the settings and module-state tables of the base database, built against the storage text of commit f8dd39a (paged reads, no attachment at a bare type address, `moved` and `stack_at`, `layer_fields`, no transitive flag, list settings one row per member). With them, the storage side of LAYER-001 to LAYER-007, LAYER-010 to LAYER-012, MAP-002, MAP-003, MAP-010, MAP-013, MAP-015, MAP-016, MAP-020 to MAP-022, MAP-030, MAP-031, MAP-044 and MAP-045.
- Tests added: `tests/test_home.py`, `tests/test_store_map.py`, `tests/test_store_layers.py`, `tests/test_store_corrections.py`, `tests/test_store_reads.py`, `tests/test_store_operations.py` (every STORE-024 operation's rows, every listed error, and the query plan of every write), `tests/test_store_exchange.py`, `tests/test_store_challenges.py`, `tests/test_store_concurrency.py`; shared helpers in `tests/storekit.py`. 202 tests, each marked with its requirement and `kind('fixture')`. Whole suite: 264 passed. No existing test was removed in this step.
- Not yet covered: STORE-005's timing thresholds on a store loaded to a million items. The plan test covers every read and write; the timed load is left for a separate run with the storage-proof loader.
- Commit: bbd2fce.
- Questions raised: Q1 to Q8 in BUILD-QUESTIONS.md.

## Step 2: the common base and the module contract

- Records satisfied: BASE-001, BASE-004, BASE-006, BASE-009, BASE-010, BASE-013 to BASE-019, BASE-028 for verbs and event deliveries, BASE-032, BASE-033, BASE-034, BASE-035, BASE-036, BASE-037 and BASE-043 for module verbs; STORE-022, the helloworld history as a layer; MCP-008's load check; CLI-012 and CLI-019 through helloworld's `--loud` and `--favorite`. The template module is now `helloworld`, a new empty `template` sits beside it, and both ship disabled.
- Tests added: `tests/test_base.py` (contract, discovery refusals, lifecycle, events, per-verb systems, READMEs), `src/metaform/modules/helloworld/tests/test_helloworld.py`, `src/metaform/modules/template/tests/test_template.py`; pytest collects `tests` and `src/metaform/modules`. Shared fixtures moved to the root `conftest.py`. Whole suite: 268 passed.
- Tests removed, because the spec replaces what they protected: `tests/test_map.py` and its fixture (XML import of an intake result, which the spec forbids; the map module is rebuilt in step 4), `tests/test_mcp.py` (the single `nouns` array schema, replaced by MCP-003; rebuilt in step 6), `tests/test_modules.py` (the old template demo, replaced by the helloworld and base tests).
- Commit: 5ff5870.
- Questions raised: Q9 and Q10.

