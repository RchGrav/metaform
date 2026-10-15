---
name: metaform-web-ui
description: Use when editing the Metaform web page chat dock or header.
category: development
---

# Metaform web page: one path per action, measured layout, file serving kept intact

Add new behaviour to the existing path, measure any header or dock change in a headless page, and drive browser tests through the real write.

## Chat dock
- Every chat file goes through `attachFiles(files)` in `src/metaform/modules/web/page/app/dock/send.js`, which posts to `/api/attach`. Never add a second upload route; the server judges what is refused. Dispatch's `attach` is the other direction; do not merge them.
- A paste attaches only when the clipboard holds files and no `text/plain`. A refusal (413, 25 MB) or an unreadable dropped folder becomes a `dockNote` naming the file and reason.
- Put every dock child inside `.chatpane`. Give new dock classes a dock-specific name, since `.pane` and `.item` in `app.css` style any element carrying them.
- The agent list shows only when `#dock` has `open big` and the page is wider than 820 px. Step counts reach it only through `ticketsChanged`.
- Agent replies take the width their content needs. Never put a `ch` cap on a reply. The person's own bubble, capped at `min(85%,64ch)`, is the only capped bubble. Use the spacing tokens, never literal px.

## Header and menus
- The header folds in steps before it hides controls, and the full row needs about 1,907 px. A new header button can fold every control at 1280 px and break tests that click Agents or Board there.
- Put a new project-wide action as the first item of an existing menu: Agents (`#agentbox`) for agent actions, Window or Help for the rest.
- Measure each child's right edge against the header's right edge less its padding in a headless page. `scrollWidth` rounds and under-reads by about 3 px.
- A new page write is a `/api/...` route in `web/server.py`. Add it to the VIEW-011 list and its count, and to `test_the_dispatch_writes_are_taken_only_from_the_page`. Record the route in the module README and CHANGELOG.

## Static serving
- Every page file is rewritten: each `/vendor/` address becomes `/vendor/v-` plus a 16-hex digest. Never serve a page file unrewritten, and never import a vendor file by a path the import map covers, or the browser loads two Three.js instances.
- Current-version vendor addresses are `immutable`; unversioned or stale ones stay `no-cache` with an ETag. Page parts revalidate on every load.
- Gzip text, JSON and SVG of 1 KB or more when `Accept-Encoding` allows it; the gzip copy is cached by file stamp and sent with `Vary: Accept-Encoding`.
- `index.html` lists `modulepreload` links after the import map. Keep `disable_nagle_algorithm = True` on the handler.
- A new root-level file (an AudioWorklet) takes the same route: check `text/javascript` and that it loads under `script-src 'self'`.
- In `test_web.py`, match versioned vendor addresses by regex and keep the exactly-one-fetch count.
- VIEW-003 still says vendor files are revalidated on every load, which no longer matches the code. Amend the record through `metaform-spec-amendments` rather than editing the code to match it.

## Browser tests on live updates
- Make the change with the same CLI write a person would make, then `page.wait_for_function` on the text it should produce, with a 15000 ms timeout. Never sleep.
- Prove the wait depends on the code: remove the call that carries the update, and the test must fail. Restore from a copy, never `git stash`.
- Run each browser file in its own pytest command, with `DISPLAY` and `WAYLAND_DISPLAY` unset so no window opens on the person's screen.
- The paste-and-drop test command is `env -u METAFORM_ROLE -u METAFORM_SESSION -u METAFORM_WORK -u METAFORM_NODE -u DISPLAY -u WAYLAND_DISPLAY METAFORM_BUILD_VIEWS=1 uv run pytest -n 0 -m browser src/metaform/modules/web/tests/test_web.py -k pasted_picture_and_dropped`.
