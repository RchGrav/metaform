# Test review 5

Scope: every test added or changed since `99940af`, by a test-review agent on Sonnet, 2026-09-26, judged only against the spec records each test names and Q51 and Q52; no implementation file was read. `tests/test_store_reads.py`'s graph read test and index entry, and `test_web.py`'s drawing test, wheel license list, graph paging, removal provenance check and wrong cookie.

## Findings and what was done

1. The VIEW-010 drawing test covers only the acceptance line that every visible element and join is drawn; it does not time the first vertices, sample the frame rate while orbiting, or reopen the page to use a cached layout, and its large case is 3,000 elements, not STORE-005's 100,000. Kept, and recorded here: the first vertices and the frame rate were measured by hand at 20,000 and 100,000 elements in step 22, in software rendering, and the frame rate on real hardware is for Rich's machine; the layout cache is not built, Q51. VIEW-010's timing and cache acceptance is not covered by any automated test.
2. The same test checked each size's draw calls against a ceiling of 12, so calls growing with size would pass. The large map now holds the same kinds of things as the small one, subtypes and namespace edges included, and its draw calls must equal the small map's.
3. The graph read test checked the parent of one element. It now checks every element's nearest parent, `None` for the three roots.
4. The graph read test's raw case had nothing hidden, so a read ignoring `raw` would pass. A hidden layer now adds an element and a join: the read in context leaves both out, the raw read returns both.

## Coverage notes

The reviewer found the wrong-cookie fix, the provenance check through the export, the license list and the relaxed page count sound.
