---
name: metaform-web-map
description: Use when editing the Metaform web map or its chat page.
category: development
---

# Metaform web map and chat page

Change the page surgically, and reproduce the person's view before you say what broke: a "the map is broken" report is a reproduction task, not an explanation.

## Triage: looks broken, blank or wrong
1. Settle the open tab first. A page loaded before a fix keeps what it drew; ask for a reload and say so in your reply.
2. List what changed: sibling tickets' logs (`map_work`), `git diff` on `src/metaform/modules/web/page`, and any page file newer than the running server. A running server keeps its old code until restarted.
3. Reproduce on a scratch copy at the person's settings (depth, layers, lens), once on the working tree and once on HEAD, headless, on the real GPU. `scripts/depth-probe.py OUT_DIR URL TAG KEY...` prints node and edge counts and page errors after each key.
4. A difference between tree and HEAD is the regression. Identical counts mean the code is not the cause; say so with the numbers.
5. Report counts, not impressions, and list what you did not check. Page-error floods such as `scale(Infinity)` are code defects: fix them at the source, never hide the symptom.

## 2D flow dots: the flow stays SVG
Never draw flow on a canvas over the map. Build each edge's shapes once, write `d` and display only when they change, and keep each composited flow layer one size. Details and measurements: `references/flow-2d.md`.

## Mascot and agent figures: moving them
Read `web_embody` first: `figure: false` means every move drives the person's mascot, so stop and report instead of moving. Treat `address=` moves as approximate, confirm with one `web_look`, and send one act at a time, waiting for its `done`. Details: `references/mascot-navigation.md`.

## Chat keys follow Claude Code
The person works in Claude Code all day, and a mis-key that costs the window and a mouse hunt costs a whole turn. Escape interrupts a running turn and never puts the chat away; Up recalls the last message. Details: `references/chat-keys.md`. The open rollback question and its three routes: `references/rollback-options.md`. Spec amendments for these rules follow the metaform-development skill's spec section.

## Checks
Run `node --check` on each changed page part and keep lines within 120 characters. The browser-test procedure is in the metaform-development skill (web page and browser tests).
