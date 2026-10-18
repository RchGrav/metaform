# Draft: VIEW-035 and VIEW-041 amendments, agent size on key 6, held by default, camera clearance removed

Tickets 3d97c7b3ab2c42fcad4080965d19792e (code.interface.graphical#100) and 76231a3f0e2c4d609a39af989584cff9
(code.interface.graphical#fe). Drafted by the Claude agent on #100 for the owner's approval. #fe asks for the
amendment in `specifications/09-viewer.md`; the worker rule is to draft it here, and the bullets land only once the
owner approves this wording. Ticket b8b842f7ac2b4c559493aa0311c35b12 (code.interface.graphical#10b) asks for the same
VIEW-041 amendment; its GC rechecked every citation below against the tree at about 17:40Z on 2026-10-18 (keys.js:59,
agents.js:54, roam3d.js:427-432, mascot.js:32 and 278, no clearance code in page/app) and found them true, so the
bullets, once approved, also close #10b.

Why it is needed: no record says that figures are capped on the screen, that the cap is on by default, or that key 6
switches it. VIEW-041 still says key 6 is the 2D map's Large text mode. A later agent reading the specs would learn
nothing of the cap that keeps the camera out of a large figure, and could reassign key 6 or put the camera clearance
back.

Checked against the working tree on 2026-10-18 at about 17:10Z (page/app is untracked or uncommitted, so the line
numbers are the tree's, not a commit's):

- `figures/agents.js:44-54`: `ROAM.most` is 110; `ROAM.held` is true unless localStorage `metaform.agentSizeFree` is
  `'1'`. The old key `metaform.agentSizeHeld` is no longer read.
- `keys/keys.js:59-60, 82-89`: key 6, `holdAgentSize`, help text "Agent size: limited or let grow"; it flips
  `ROAM.held`, stores `'0'` or `'1'` under `metaform.agentSizeFree`, and says "Agent size: limited" or "Agent size:
  not limited" at the 2D map's corner.
- `figures/roam3d.js:421-433`, `drawFigure`: while held, a figure's scale is cut so it stands at most `ROAM.most`
  pixels tall at its own distance from the camera, from the camera's field of view and the stage's height.
- `figures/mascot.js:274-278`: the person's mascot is capped the same way, at `MASCOT.most`, 64 pixels
  (`mascot.js:32`), not at `ROAM.most`. #fe's remediation names `ROAM.most` for both; the code caps the mascot lower.
- No `clearWatched`, `clearOfWatched`, `CLEAR` or `FIGURE_RADIUS` anywhere in `page/app`.

## Proposed bullet for VIEW-035, after its Status line

- Amendment, 2026-10-18, tickets 3d97c7b3ab2c42fcad4080965d19792e (code.interface.graphical#100) and
  76231a3f0e2c4d609a39af989584cff9 (#fe), from the code: a figure's size is limited on the screen by default. While
  agent size is limited, `ROAM.held` in `figures/agents.js`, `drawFigure` in `figures/roam3d.js` draws each figure at
  most `ROAM.most`, 110, screen pixels tall at its own distance from the camera, however near the camera comes, and the
  person's mascot at most `MASCOT.most`, 64 (`figures/mascot.js`). The size this record gives, 0.11 of half the drawn
  map's widest side and never less than 2.6, still holds whenever it draws the figure smaller than the cap, as it does
  with the whole map in view. Key 6, `holdAgentSize` in `keys/keys.js`, switches between limited and not limited, says
  the new value at the 2D map's corner, and keeps it in this browser under localStorage `metaform.agentSizeFree`,
  `'1'` for not limited; anything else, or no storage, is limited. The earlier key `metaform.agentSizeHeld`, kept when
  figures grew by default, is no longer read, so a choice saved under it cannot override the default. Why: with figures
  let grow, a camera watching or following a large figure stood inside it; the cap keeps a figure's half-height at
  about 0.06 of its camera distance (fov 50, a 900-pixel stage), so the camera stays outside it on every path, a click,
  a follow and the wheel. On the same day a camera clearance that eased the camera out of a large figure (`clearWatched`
  and `clearOfWatched`, and the clearance in `followIn3d`, tickets #b5, #be and #db) was built and then removed on the
  owner's decision, relayed by the system agent at about 16:33Z, because the limited default already keeps the camera
  out; no record ever described it, and it is not to be put back on its own. Avoiding a large figure with agent size not
  limited was returned to the PM as ticket #f9 (8a5dd2d9, closed 2026-10-18 16:55Z); a new ticket is needed if the
  person wants that avoidance. No test yet pins the limited default or the storage key.

## Proposed bullet for VIEW-041, after its Status line

- Amendment, 2026-10-18, tickets 3d97c7b3ab2c42fcad4080965d19792e (code.interface.graphical#100) and
  76231a3f0e2c4d609a39af989584cff9 (#fe), from the code: the digit mapping in this record's Requirement, Small, Medium
  and Large on keys 4, 5 and 6, Height, Width and All on 7, 8 and 9, and Free on 0, is superseded. The 2D map is fit-all
  and zooms by the wheel at any time, and each digit cycles one setting of its own, listed in `KEYS` in `keys/keys.js`:
  1 the 3D camera's levels, 2 the flow, 3 the layout, 4 the depth, 5 the speech bubble size, 6 agent size, VIEW-035,
  7 the lens, and 0 and Home full fit of both maps. Keys 8 and 9 have nothing. The 2026-10-14 change that freed the
  digits is drafted in `artifacts/specs-draft/map-keys-2026-10-14.md` (ticket code.interface.graphical#23), not yet
  landed; it also covers the same stale digit lines in VIEW-005 and VIEW-008.

## Lines this leaves stale, for the owner's choice of where to amend

- `09-viewer.md:93`, VIEW-005: "The 2D map's zoom is its mode, VIEW-041, on the keys 4 to 9 and 0".
- `09-viewer.md:142`, VIEW-008: "The keys 4 to 9 and 0 choose the 2D map's mode, VIEW-041".

Both are covered by the 2026-10-14 draft named above (which cites them by older line numbers, 86 and 117).

## Check once landed

`grep -n "agentSizeFree\|Key 6\|key 6" specifications/09-viewer.md` finds both bullets, each dated 2026-10-18 and
naming ticket 3d97c7b3 (#100) and 76231a3f (#fe).
