# Manual test of the web GUI, step 22

Date: 2026-09-26. Branch `chassis`, after unit 7 of step 3. Tester: a Claude agent, by hand, on Linux, WSL2. The CLI ran as `/home/rich/metaform/.venv/bin/metaform`.

## Setup

- `MT` is the scratch folder `/tmp/claude-1000/-home-rich-metaform/61f77ef6-a53d-4c77-b3e1-89175e9daeed/scratchpad/mt5`. Every command ran with `METAFORM_HOME=$MT/home`, on `--web-port 7502`. Projects `proj` on `$MT/proj` and `other` on `$MT/other`.
- The page was checked against a copy of the real home, holding this repository's own intake: 8 elements, 7 joins, 9 subtypes. The copy ran on port 7501; the real `~/.metaform` was only read.
- The browser was Chromium, headless, through Playwright, with WebGL in software. The same checks run on macOS and Windows in CI with every change; a person's look at the page on those systems is still to do.

## Commands

| # | Check | Command | Observed | Spec | Result |
|---|---|---|---|---|---|
| 1 | Help page | `metaform help web` | Summary, purpose, verbs `start` and `stop`, settings `--web-port`, `--web-bind`, `--web-autostart`, details naming loopback and the token | VIEW-001, CLI-007 | PASS |
| 2 | Syntax | `metaform web --help` | `Usage: metaform web <verb> [nouns] [switches]` and both verbs | BASE-035 | PASS |
| 3 | Start from one project's folder | `metaform web` in `proj` | `state: started`, `address: http://127.0.0.1:7502/` | VIEW-002 | PASS |
| 4 | Start again from another project's folder | `metaform web --json` in `other` | `{"state": "running", "address": "http://127.0.0.1:7502/"}`; `run/web.json` names one process | VIEW-002 | PASS |
| 5 | Setting help | `metaform help --web-bind` | What loopback means, that another address needs the token, set and unset | VIEW-002, CLI-007 | PASS |
| 6 | Notice for agents | `metaform help agents` in `proj` | Ends with the intake notice, then VIEW-015's notice word for word | VIEW-015 | PASS |
| 7 | Notice off | `metaform set --no-web-autostart`, then `metaform help agents` in `proj` | `web_autostart: true → false`; the notice is gone | VIEW-015 | PASS |
| 8 | Stop, twice | `metaform web stop`, twice | `state: stopped`, then `state: not running` | VIEW-002 | PASS |
| 9 | Settings shown | `metaform config --show` | `web_port: 7502 (set)`, `web_bind: 127.0.0.1`, `web_autostart: true` in a folder where it was not turned off | VIEW-002, VIEW-015 | PASS |
