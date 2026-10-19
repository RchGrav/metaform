# Draft: following an agent keeps its figure in the middle of both maps, ticket code.interface.graphical#46

Draft for Rich. Not a specification until he moves it in. It is for VIEW-005 and VIEW-041 in
`specifications/09-viewer.md`, and it replaces the last paragraph of the earlier draft
`artifacts/specs-draft/map-keys-2026-10-14.md` (lines 33 to 35), which describes what this ticket changed.

## Stale text

- `artifacts/specs-draft/map-keys-2026-10-14.md:33-35`: "While the person follows an agent, the 2D map frames
  that agent's node and the parts one join away, and follows the agent from node to node." Since 2026-10-15 the
  2D map follows the agent's figure itself, and the 3D map does too.
- VIEW-041, "Auto zoom follows the newest agent start" (the comment above `followStart` in
  `page/app/agents/dispatch.js` cites VIEW-041 and VIEW-005): while the person follows an agent, a new agent's
  start no longer moves either camera.

## Proposed amendment, 2026-10-15, written to match what is built, ticket code.interface.graphical#46

While the person follows an agent (A), both maps keep its figure in the middle, frame by frame, as it comes onto
the map, walks and works. The 2D map zooms to frame the agent's node and the parts one join away around the
figure's place beside the node. It follows the figure's own place there, so a small act or a reach toward another
part does not move the map. The 3D map, large or small, moves the point the camera turns about and the camera
together with the figure where it is drawn, its acts included, keeping its distance and angle, so the hand can
still turn about the figure and zoom. Both ease in and out as every camera move does (VIEW-041): a figure that sets
off is caught up gently and one that stops is settled on without passing it. A figure at rest moves neither camera.

Following takes the 3D camera from the layout's own fits and from a flight under way, and an agent's start moves
neither camera while an agent is followed. A drag on either map ends the following where the hand leaves the
view; a click and the wheel do not, and the wheel's zoom is the one followed at. In the agent's view (V) the 3D
camera is the agent's eyes as before, and the 2D map still follows the figure.

While an agent is followed, the 2D map's top right names it under the corner notes, with its glyph's image: its
agent's name and its glyph, "Following Claude Code · comet". Its entry in the Agents key is marked as the one
followed. Both go when none is followed.

Why: following framed the ticket's node, so a walking figure left both maps for seconds (the critic measured the
puffer 2,468 px from the 2D map's centre and the comet at NDC y 1.109 in 3D), and the only thing naming the
followed agent was a note that faded in 1.6 s.
