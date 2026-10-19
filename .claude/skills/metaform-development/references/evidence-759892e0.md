E       AssertionError: assert (0 != 0)
E        +  where 0 = CompletedProcess(args=['/home/rich/metaform/.venv/bin/python3', '-m', 'metaform', 'dispatch', 'tune', '78c0eecdeafe445...o model=bogus is kept unchecked; metaform dispatch options agent=claude prime=true lists what it offers.\n', stderr='').returncode

src/metaform/modules/dispatch/tests/test_dispatch.py:3339: AssertionError

tune now resolves the ticket's agent to claude (the default since `preferred()` changed on 2026-10-17), but the test only seeds a catalog row for codex.

ancestor
in first parent
189:-def preferred(record: WorkRecord, kept: dict[str, Any] | None) -> str:
...
+def preferred(record: WorkRecord, kept: dict[str, Any] | None, default: str) -> str:
...
+    return str(agent) if agent in agent_choices() else default