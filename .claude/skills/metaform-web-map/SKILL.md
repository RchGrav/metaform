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

## Word bubbles: SVG over both maps, tail to the speaker
Every word bubble, agents' and the mascot's, is SVG in the one fixed `#bubbles` layer over both maps, drawn each frame by `bubbles3d` in `figures/bubble3d.js` (graphical#c7, 2026-10-18). Do not bring back per-map planes or a canvas for bubbles. `say` in `figures/cut.js` only records the line in `BUBBLE` (`figures/bubble.js`), and `placeBubble` reads the speaker's head on the page just before `bubbles3d` draws. The head is the eye point plus `LOOK.lift`, so import `LOOK` from `bubble3d.js` in any test; never copy its literals. The tail runs from the body to the speaker's head on screen, so it keeps pointing at the speaker when the body is pushed apart; when the head is off the map area the tip is where that line leaves the area. A click on an agent's bubble picks that agent through `figureAt` to `bubbleAt(x, y)`, and each bubble element carries `data-who`. Guard: `test_word_bubbles_point_at_their_speakers_stay_apart_in_view_and_the_watched_agent_speaks_at_the_bottom` in `web/tests/test_working_figures.py`. The mascot's reply field still opens in the plain `.mascot-bubble` box, which `bubbles3d` positions over the speaker's head.

## Mascot and agent figures: moving them
Read `web_embody` first: `figure: false` means every move drives the person's mascot, so stop and report instead of moving. Treat `address=` moves as approximate, confirm with one `web_look`, and send one act at a time, waiting for its `done`. Details: `references/mascot-navigation.md`.

## Chat keys follow Claude Code
The person works in Claude Code all day, and a mis-key that costs the window and a mouse hunt costs a whole turn. Escape interrupts a running turn and never puts the chat away; Up recalls the last message. Details: `references/chat-keys.md`. The open rollback question and its three routes: `references/rollback-options.md`. Spec amendments for these rules follow the metaform-development skill's spec section.

## Context the person points at: capture it when they act
When a page act refers to something the person just did ("this", the last click), fix what it refers to at the moment the person asks, never when the message is later delivered. A delivery that waits on a starting agent otherwise lets a later click change what "this" means, or drops the reference after a timeout. Every ask path (the chat dock and the mascot) must do the same: a path that builds its reference at delivery is a defect, even when its own comment says it matches the chat. When one click both opens a box and is recorded as context, the test that opens the box and the test that skips the record are one shared predicate (`mascotTakes` in `figures/ask.js`, used by `clicked3dAt` in `figures/eyes.js`): two copies of "is a node here" drifted, so a mascot click near a node opened the field and also recorded that node. A failed send must release every ask waiting on it and tell the person: a mascot question queued behind a chat send that fails stays unsent with no word to the person, so a failed send hands the waiting ask its failure too (graphical#13b).

## View context goes with one message, once
A view's `ui/update-model-context` waits per thread and goes with the person's next message. Every sender to a thread takes it when it composes that message: `takeContext(...)` in `session/apps.js` removes the context and clears the views' notes, `withContext(taken, text)` only composes the `[From the <view>: ...]` lines, and a failed post gives it back with `contextBack(taken)`, which skips any view that told something newer since the take. Dropping the context only after the post answers ok sends it twice: `/api/dispatch-message` answers after the agent has the prompt, so a follow-up sent in that gap carries it again. The queued send, the direct send in `sendMessage` and a view's `ui/message` all take and give back the same way; a new sender does too. The click line follows the same rule: the direct send sets `CLICKED.told` before `wrote()` and clears it again if the post fails, so a follow-up sent in the gap does not repeat it, and a failed send leaves the click for the resend. A click is used up only when its line reaches the system agent: a message to any other agent leaves `CLICKED.told` untold, so the next message to the system agent still carries the line once. Guard: the last-click step in `test_web.py` sends to another agent after a click and asserts the click stays untold. Guard: `test_a_queued_message_that_fails_puts_back_only_the_persons_words_and_keeps_the_views_context` in `modules/web/tests/test_web.py`.

## Reads that land out of order: the newest draw wins
A page read started before a redraw can land after it. Number each draw, and drop a read that lands after a later draw has begun instead of drawing it. `drawHelpdesk` in `dock/helpdesk.js` does this, and `renderAgents` in `agents/dispatch.js` does it for a full read of every agent (`WHOLE_READS`); a read of named tickets alone still merges in landing order. Guard: the last-click step in `test_web.py`, which sends after a click while a read is in flight.

## Which project a new page opens on
Never infer the person's project from folder file times or any other activity that background work touches: runners, the memory watcher and the a2a server open every project's stores, so the newest file times follow sweeps, not the person (FQC c67259bc, 2026-10-19). The page reports the project it shows (`shown(id)` in `loading/load.js`, POST `/api/shown`), and the server keeps it for the person's own page only (`VOUCHED.server`), answering `kept: false` for an agent-driven page. `/api/projects` serves that as `recent`. Per-tab `sessionStorage` loses the project in a new tab, so the browser-wide `localStorage` key is the one a new tab reads. Guard: `test_the_page_is_told_the_project_of_the_folder_metaform_web_last_ran_in` in `web/tests/test_web.py`, which must keep `recent` on the shown project when another project's stores were opened later.

## Roundtable stage: leaving keeps the figures in the scene
`leaveStage` in `page/app/roundtable/stage.js` must leave the seat meshes in `VIEW.scene`. The stage is not drawn while the person is away, so keeping them costs nothing, and removing them makes a returning table show names and bubbles with the tails pointing at empty space. Only `unseat` removes them, and only when the table has ended or never opened. The `roundtable_stage` browser test in `web/tests/test_working_figures.py` leaves a table that is still running, returns with `T` or the Roundtable button, and asserts every seat mesh has a parent in the scene.

## Checks
Run `node --input-type=module --check < FILE` on each changed page part: the parts are ES modules with `import`/`export`, and plain `node --check FILE` is not the check to rely on. Keep lines within 120 characters. To prove a queued path, the browser test marks the system agent's session `starting` by rewriting `/api/dispatch-sessions`, asks, then makes the session live through `renderAgents`, so the waiting step actually runs. The browser-test procedure is in the metaform-development skill (web page and browser tests). In the small area the open chat dock covers the 3D mascot, so a test that clicks the mascot swaps the 3D map back to the large area first; a click on the covered mascot misses without any error.
