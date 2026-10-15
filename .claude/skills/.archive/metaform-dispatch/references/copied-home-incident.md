# Copied home resumed three paid agents (2026-10-14, ticket code.dispatcher.agent#26)

Symptom: three scratch homes (`/tmp/f1check/home`, `home-old`, `home-wc`) were copies of one store. Session d9fd1ab3 was `state=running` with the pid of a runner that had exited. Each scratch server read it as ended, then resumed it.

Cause: `session_status()` reported the dead pid as ended with `how` 'the runner is no longer running'. `stay_connected()` (system agent, VIEW-045) and `retry()` (supervisor) treated that as resumable and called `spawn(resume=...)`. No row said which home had started it, so every copy took it as its own. Afterwards each copy's row showed a different runner pid.

Fix shape:
- `dispatch/__init__.py`: `origin()` returns `<socket.gethostname()>:<home.home().resolve()>`; `foreign(row)` is `row.get('origin') != origin()`; `session_status()` reads a running foreign row as ended with `how` 'another Metaform home started it' (FOREIGN).
- `retry()`, `stay_connected()` (returns `{}` when the latest system session is foreign, so no replacement starts either), `resumed_conversation()`, and `recovery.recover()` (defers foreign rows, so it never stops another home's adapter group).
- Home path plus machine, not a random id stored in the home: copying the home would copy that id too. Moving or renaming a home makes its sessions foreign.
- Sessions table version 13 adds `origin` (private, like `pid` and `token`). `dispatch resume` still works on any row.

Tests: `test_a_home_copied_with_its_store_resumes_none_of_the_sessions_the_original_home_started` in `src/metaform/modules/dispatch/tests/test_dispatch.py`. With `foreign()` forced to False in a `/tmp` copy it spawned `resume=s1` and `resume=w1 retry=true`; with the fix it spawns nothing in the copy and both resume in the original.
