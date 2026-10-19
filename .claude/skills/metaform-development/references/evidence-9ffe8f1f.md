$ git worktree add -q /tmp/helper-head HEAD && cp src/metaform/modules/dispatch/tests/test_dispatch.py /tmp/helper-head/src/metaform/modules/dispatch/tests/test_dispatch.py && cd /tmp/helper-head && ... PYTHONPATH=/tmp/helper-head/src timeout 600 /home/rich/metaform/.venv/bin/python -m pytest -n 0 -p no:cacheprovider src/metaform/modules/dispatch/tests/test_dispatch.py -k "a_helper" -q --tb=short
src/metaform/modules/dispatch/tests/test_dispatch.py:2054: in test_a_helper_runs_its_brief_on_no_ticket_outside_the_worker_slots_seen_live_and_ended_by_stop_all
src/metaform/modules/dispatch/tests/test_dispatch.py:44: in eventually
E   AssertionError: not within 60 s
src/metaform/modules/dispatch/tests/test_dispatch.py:2085: in test_a_helper_that_finishes_its_brief_puts_one_line_in_the_system_agents_inbox_and_ends
E   AssertionError: not within 60 s
2 failed, 193 deselected in 126.07s (0:02:06)