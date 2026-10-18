# Node read profile, 2026-10-16 (code.dispatcher.agent)

Symptom: opening a node on the page took 7.5 s and was answered 503 under load (15 s read limit).

Where the time went, from a profile in a fresh request scope:
- memory node_read -> whole -> entity -> stale -> citations.stale: 6.8 s of 7.9 s in the line split of the moved-lines search.
- Cause: when a cited file had changed, the search for moved lines called the split once per candidate position, so each file was split again and again (29,580 splits).
- loader.discover: 0.74 s, paid by the first call in a fresh process. The discover cache already holds until a module is enabled, disabled or the project changes, so the cost was the cold first call only.

What changed and what it measured:
- Split each cited file once per read; digest each window of a span once per file. Same answers. A 10,000-line test file: 3.82 s before, 0.02 s after.
- Node read of code.dispatcher.agent in a fresh request scope: 7.4 s before; 104 ms after the split fix; 21 ms median once the citation results were stored and looked up.

Test pattern kept: a unit test on the moved-lines search over a large file that fails on time or on call count without the fix.
