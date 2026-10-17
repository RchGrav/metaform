---
name: metaform-web-map-navigation
description: Use when the seahorse or mascot must move, come, dance, wave, turn, ride a tour or talk on the Metaform web map or 3D view, or when its character or body is set, kept or lost.
category: development
---

# Navigating the Metaform 3D map

Before any `web_move` or `web_turn`, read `web_embody`'s answer. `figure: true` means you have your own body. `figure: false` means every move drives the person's mascot: stop and report that instead of moving.

- Treat `address=` moves as approximate. They can land short or overshoot. Confirm with one `web_look`, then correct with a small step.
- Let a turn finish before judging facing. A look straight after `web_turn` can report the old facing.
- Forward steps travel further than their number suggests (forward 200 went about 250 units) and head toward wherever you face, not toward a target. Labels are readable at roughly 50 to 250 units.
- `web_look` lists 60 to 90 entries, including `visible: false` ones up to about 960 units away. Read the nearest readable ones; do not paste the whole list into a reply.
- Labels are mirrored when seen from behind. Check orientation before reading text.
- When the person asks whether you can see the map, answer from a `web_look` picture. Without a look, say that you have only the act replies.
- A defect you hit is a ticket (`metaform map work op=add`), not a silent workaround.
- The 2D map is SVG. A figure opens its thread from a `pointerdown` handler on `g.agent2d`, so a test dispatches `pointerdown` and then `click` on that element; a bare `click` does nothing.
- Camera moves that follow a figure ease with a critically damped spring solved exactly per step, timed from the key press, each axis keeping its own position so a small step is not lost. An exponential ease jumped at the start and failed the VIEW-041 eased-move check (0.076 against a 0.0754 limit), because zoom and centre moved together.
- A drag of 4 px or more on either map ends following and leaves the view where the hand put it; a click or the wheel does not.
- Send one act at a time and wait for its `done`. Acts sent together cut each other off: a reply reading `"stopped_by":"a later act"` means the act was interrupted, not finished. Two turns sent together landed at 134 and 147 degrees; a hop asked for 20 units rose 12.5.
- Look before you describe. Narrate only what the `web_look` picture shows (colour, state, what is in frame), never what a ticket or tool result says the place holds. A ticket's marker is evidence to check, not a description of the view.
- If a web tool answers "The web GUI is not running", call `web_start`, open the page, then retry the act. An emote not in the list (for example a dance) is not available; say so instead of substituting one silently. The emotes are wave, think, celebrate, shrug and sleep. A dance is a timed sequence of `web_move` and `web_turn` acts, each awaited to `done`.
- `web_come` with `to: view` can land far from the person's camera when they are zoomed out. It landed about 890 units in front of the camera, and the person said they were "way back". Before bringing the mascot in, read `web_viewing` (`view_3d.at` and `gaze`), then bring it close with `web_move` to a point near the camera, and confirm with `web_look`.
- `web_come` with `follow` keeps the mascot trailing the view. Send `seconds: 0` to end it before moving the mascot by hand.
- If an act fails because the web server restarted, retry that act once.
- The mascot's character is one record, the `web_mascot` setting, since 2026-10-16 (code.interface.graphical#9e). The page draws the system agent as it in every conversation and on every page, and the system agent's prompt names it. Giving the system agent a body in the chat writes `web_mascot`; `metaform set --web-mascot=<character>` changes it on every open page. While it is set, the chat never offers the system agent a body. The one exception is a body the system agent takes itself with `web_embody` in a different character: that is its own figure for that conversation, and the mascot is not drawn meanwhile. Bodies of other chat agents are still kept per conversation in localStorage `metaform.bodies`.
- When the person says the page shows the character they picked and the stored `web_mascot` row names another, their pick is the answer: do not ask which one. Set the row to the glyph they chose with `uv run metaform set --web-mascot <glyph>`, read the row back to confirm it, and say it is a stopgap for this person. The fix stays the open `code.interface.graphical` ticket on the mascot record.
- Only the person's mascot pushes, drags, drops or carries elements. An embodied agent's figure is refused those acts by design (`96f6761`: "pushing and carrying elements are the person's mascot's"). Report the refusal; do not treat it as a routing bug, and do not move the mascot to do it.
- Do not drive the person's mascot (`web_go`, `web_move`, `web_come`) or speak in its bubble (`web_say`) to report status on a turn that did not ask for it. Answer in chat instead.
- Reading a figure's acts is not the same as testing them: a browser test covering move, turn, look and see does not show point, emote, the push refusal, or two agents acting at once.
