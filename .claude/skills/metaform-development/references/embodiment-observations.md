# Embodiment observations, 2026-10-13

Session: ticket code.system.management.knowledge#15 (wishlist). Owl body taken with web_embody.

Seen in use:
- web_embody owl returned {"character":"owl","mascot":false,"figure":true}.
- web_go code.interface.graphical distance=60 returned {"act":"go","address":"code.interface.graphical","distance":60,"height":null,"pages":1}; a following web_see still put the eye about 146 units from Metaform, facing code.graph.knowledge, Web GUI not in view.
- web_move to an element: the next web_look faced another node, and the target was not in frame.
- Eye position moved about 180 units between two calls with no act between them.
- web_look with address set to a node 350 units away: label text about 8 px high.

Code behind it (read, not all exercised):
- src/metaform/modules/web/page/app/figures/attention.js:127 computes `own`, the caller's own figure.
- attention.js:131-135 refuses bodily acts only when there is no body and no own figure; with own set, the refusal is skipped.
- attention.js:139 dispatches to MASCOT_ACTS (185-231); only `say` reads `own`. go, move, turn, point, emote, push, drag, drop write MASCOT.
- attention.js:157-180: web_come routes to the caller's own figure first. This is the pattern to copy.
- src/metaform/modules/web/page/app/figures/eyes.js:31-45: seer() picks the caller's own figure, so see and look use it correctly.
- src/metaform/modules/web/__init__.py:813, 822, 827: go, point, move descriptions say "the person's mascot".

Wishes raised (not implemented, not ticketed): acts answer who acted and where it ended up; tool descriptions name the acting body; look frames its target; an agent can hold its own figure still; see lists figures beyond the frame.

Fixed 2026-10-14, ticket code.interface.graphical#28 (the routing above is history):
- attention.js mascotEvent routes go, move, turn, point (MOVES) and emote, take, release (OWN_ACTS) to the caller's own figure; roam3d.js stage `driven` holds it where its agent put it. Goals: walk.js driveGoal (node + offset fixed at the act) and driveFace.
- attention.js settle answers when the body is at rest at its goal and within 3 degrees of its face, or after 6 s with stopped_by=time. Measured: forward=12 asked 12 moved 12; move to an address asked 8.6 moved 8.7, off 0.1.
- The wrong facing after a look came from the owl's idle head turn (up to 43 degrees at rest, agents3d.js owl). A driven body at rest passes move state `attend`, and the owl and gearling hold their gaze. Any new character whose eyes move at idle needs the same check.
- see/look on a 243-node map: 22,969 chars before, 1,839 after.
