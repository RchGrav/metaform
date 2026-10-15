---
name: metaform-code-change-banner-test
description: Use when a browser test needs the code-changed banner.
---

# Show the code-change banner by bumping a Python file's mtime, then restoring it

The page's "Metaform was updated" banner comes from code stamps (file mtimes), so a test shows it by moving a Python file's mtime forward, restarting the web GUI, and putting the stamp back. Contents are not changed.

- Save the stamp with `stat()`, bump it with `os.utime(path, ns=(atime, mtime + 1_000_000_000))`, and restore in a `finally` with the saved `st_atime_ns` and `st_mtime_ns`.
- Restore after the restart has returned: the new process takes its stamp when it starts, so the bumped value is already in it.
- Load the module with `importlib.import_module`, not `from pkg import mod`; see python-package-function-shadows-submodule.
- Give the wait a timeout of about 20 s; the banner appears after the reconnect.
