# Test review 4

Scope: every test added or changed since `d8a645f`, by a test-review agent on Sonnet, 2026-09-26, judged only against the spec records each test names; no implementation file was read. Mainly `src/metaform/modules/web/tests/test_web.py`, with additions in `tests/test_cli.py`, `tests/test_store_corrections.py`, `tests/test_store_reads.py`, `tests/test_store_map.py`, `tests/test_build.py` and `tests/test_first_working_test.py`.

## Findings and what was done

1. `test_one_server_per_home_serves_every_project_and_stops` is marked VIEW-015 as well as VIEW-002; the reviewer read it as covering only VIEW-002. Kept: VIEW-015's second acceptance line is `web_start` returning `started`, then `running` with the same address, which the test checks through `metaform web --json`, the same verb.
2. The Host test accepts `localhost:<port>`, which VIEW-002 did not state. VIEW-002 now says that on a loopback bind address, `127.0.0.1`, `localhost` and `[::1]` with the port are all the server's own address.
3. An unregistered project answers 404, where VIEW-004's rule sent a read that cannot be read to 400. VIEW-004 now names an unregistered project as not found, 404, with the error and its next step.
4. The arrow-key check passed with the keys' directions wrong, since the element tried had one neighbor. It now selects the kitchen timer, which has joined elements on both sides, and checks ArrowRight reaches the element it receives from and ArrowLeft one that receives from it. Swapping the directions in the page fails it.

## Coverage notes

- VIEW-010's scale acceptance is not tested; nothing of it beyond paging is built. A measurement in step 22 found `/api/graph` takes 6.3 seconds for its first page of 500 on a 10,000-element store, against 2 seconds on 100,000.
- The removal test now also checks that the removed layer's provenance row is gone, VIEW-014.

The reviewer found the rest sound, naming the peel preview test as the strongest in the change.
