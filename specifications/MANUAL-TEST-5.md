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

## The page, after unit 9

On a copy of the real home, this repository's own map, at `http://127.0.0.1:7501/#p=metaform`, driven by a Playwright script in headless Chromium, with screenshots looked at by the tester.

| # | Check | Done | Seen | Spec | Result |
|---|---|---|---|---|---|
| 10 | Opens and settles | Load the page | First vertices drawn after 0.73 seconds: 8 elements, 7 purpose and 7 encounter vertices, 9 subtypes, 7 faces, 7 ties, 9 draw calls, 8 labels; settled within 6 seconds | VIEW-005, VIEW-010 | PASS |
| 11 | Orbit | Drag across the 3D view | The mesh turns around its center | VIEW-005 | PASS |
| 12 | Zoom | Scroll up five times | The camera closes in | VIEW-005 | PASS |
| 13 | Pan | Shift and drag | The view slides sideways | VIEW-005 | PASS |
| 14 | Fit | Press F | Both views show the whole map | VIEW-008 | PASS |
| 15 | Select in 2D | Click `event bus` in the 2D map | The panel shows event bus, `code.bus.event`, SE, the join it serves with its purpose and function; the 2D camera centers it; the 3D camera flies to it and dims elements not joined to it | VIEW-008, VIEW-009 | PASS |
| 16 | Legend | Read it | The intake layer by name, the tie, the namespace | VIEW-006 | PASS for one layer; a map with several knowledge layers was not looked at |
| 17 | Provenance | Open the tab | The intake layer: kind, module, created, ready, variable, workflow `canonical-intake`, model `claude-sonnet-5`, role `intake agent`, and the prompt it was made from | VIEW-013 | PASS |
| 18 | Corrections | Open the tab | `No correction layers. The metaform reads as the intake left it.` | VIEW-014 | PASS |
| 19 | Toggle a layer | Turn off the only layer | The note says an empty choice reads as every layer, as an empty `--layers` does; Apply is offered; nothing changes in the folder | VIEW-007 | PASS; with one layer the view cannot change |
| 20 | Offline | Watch every request | None left the server | VIEW-003 | PASS |
| 21 | Errors | Watch the console | None | VIEW-012 | PASS |

Seen and fixed: each label sat over its own sphere, so the DE's white sphere hid its label; labels now sit above the sphere's rim at any zoom. Flags were not seen on this map, which has none; the browser test of the panel covers a broken element. macOS and Windows are checked only by the browser tests in CI; on Windows two of them time out, under diagnosis.
