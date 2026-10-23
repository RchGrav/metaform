ERROR at teardown of test_a_page_open_through_a_restart_starts_a_ticket_without_a_reload
        for started, folder, log in runners:
>           pid = started['pid']
E           KeyError: 'pid'
conftest.py:208: KeyError

Without fix: `403`, exact reported error. Fix restored.

Pre-existing: fails identically on HEAD's `server.py` ... Not my change.