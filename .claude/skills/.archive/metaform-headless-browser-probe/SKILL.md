---
name: metaform-headless-browser-probe
description: Use when checking a Metaform web page in headless browser.
category: development
---

# Metaform headless browser probe

A throwaway browser check of the web page runs as an in-tree pytest, never as a script.

- Import the fixtures the web tests use: `web`, `browser`, `mapped`, `threaded` from `metaform.modules.web.tests.test_web` (or re-exported by `test_ticket_detail`). `threaded` is required by `web`; omitting it gives "fixture 'threaded' not found".
- Mark the test with `@pytest.mark.kind("simulation")`, or the run reports "Tests without a kind of run".
- Run with `-n 0 -m browser` on the single file.
- Any `run('set', ...)` call that depends on a folder needs `cwd=mapped`; without it the CLI runs in the wrong folder and the choice list does not contain the new value.
- Seed the catalog rows you need before the CLI call, because a choice only exists once the agent's catalog row lists it.
- Delete the probe file before finishing; it is scratch, and CLAUDE.md forbids leaving new test files.

Working template: [references/probe-template.md](references/probe-template.md)
