---
name: metaform-mascot-browser-test-setup
description: Use when a browser test needs the mascot shown.
category: development
---

# Browser tests: give the mascot its body before waiting for it

The mascot draws only after the system agent has a body. In a browser test, wait for `window.metaform.loaded()`, then call `window.metaform.embody(<system agent id>, "seahorse")`, and only then wait for `window.metaform.mascot().shown`. Waiting for `shown` before embodying times out.

- Run browser tests with `uv run pytest -n 0 -m browser <file> -k <name>` and clear the display variables (`env -u DISPLAY -u WAYLAND_DISPLAY`), so no window opens on the person's screen.
- Use the existing `web`, `mapped` and `browser` fixtures; do not add a new test file unless asked.
- Working example: references/embody-setup.md
