# Draft amendment to VIEW-005 (specifications/09-viewer.md), for the owner's approval

Ticket 7990845eb79c427b8c4b9b75bc102713 (code.interface.graphical#80). The bullet goes after the last amendment of VIEW-005, the one of 2026-10-15 for code.interface.graphical#63.

What it amends:
- The record's original sentences do not describe the reply's shape.
- The amendment of 2026-10-10 says "the dots run … one dot each way", which still holds for requests and records.
- The reply was built as a train of dots (`fxTrain` in the 3D map, dot paths in the 2D map); no sentence recorded that.
- The bullet records the new shape, at the owner's request in the session of 2026-10-15: "instead of a row of dots just a solid line of varying lengths".

Proposed bullet:

- Amendment, 2026-10-15, ticket code.interface.graphical#80 (7990845eb79c427b8c4b9b75bc102713), the reply's look: a request is one small ball, and its reply is one solid line along the join, the way the data goes, in the colour of the element the data comes from, one line each way on a join whose information goes both ways. Its length says how much data it carries: (random + random) × 5 times the request's size, a fresh length each cycle (`replySize` and `FLOW.data` in `flow/flow.js`), drawn new for an agent's live reply too. Its round ends add the request's size, so no reply is smaller than its request. It leaves as the request arrives and its far end arrives as the reply ends; on a join too short for it, it runs the join's length. In the 2D map it is one path, the stretch of the edge's own curve between its ends (`reply2d`, `.line` in the page's CSS, 4.2 px thick). In the 3D map it is a run of faint overlapping flow points that add up to one solid line (`fxReply`). Before, the reply was a train of up to 12 separate dots whose number carried the amount, the last three fading.
