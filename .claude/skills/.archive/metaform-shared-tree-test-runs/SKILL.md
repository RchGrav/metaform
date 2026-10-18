---
name: metaform-shared-tree-test-runs
description: Use when pytest runs in the shared metaform checkout.
category: development
---

# Test runs in the shared metaform checkout can end other sessions' servers

Before a pytest run in `/home/rich/metaform`, list the running web servers (`ps -ef | grep metaform.modules.web.server`). The test setup treats a web server it does not own as a leftover of an earlier run and kills it, so a test run can end a peer session's live page.

- Run the narrowest target only: `uv run pytest -n 0 <file> -k <name>`.
- Browser-marked tests are left out of the default run (`272 deselected` on a 3-test selection without the flag). To run them by name, add `-m "browser or not browser"`, run under `env -u DISPLAY -u WAYLAND_DISPLAY`, and add `-p no:cacheprovider`. Run them after a measurement finishes, never beside it.
- If a peer's server is up and the run is not needed now, run it later.
- If the run cannot wait, tell the peer first with `dispatch_note` or `SendMessage`, then run it.
- Never run the full suite in this shared tree.