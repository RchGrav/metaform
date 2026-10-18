# Orbit pivot and follow clearance: mechanics and test recipe

While a node is selected, the orbit target (the pivot) is that node's centre, so a drag turns the map about the node the person is looking at, not its name or empty space.

## Mechanics
- After the meeting flight to the node's sign, the target eases from the sign to the node over 0.35 s with the camera held. No jump.
- While selected, `pivot3d` in `camera/fly3d.js` moves the target and the camera by the node's layout step each frame. It allocates nothing (module-level scratch vectors) and costs about 7 us a frame.
- `zoomToCursor` is off while a node is selected and on when the selection clears. `steer3d` in `map3d/graph3d.js` sets it on at start; while selected the wheel zooms along the line to the node, and with nothing selected it zooms toward the pointer.
- A drag does not end the pivot. While `FOLLOW.work` is set, `followIn3d` is the only mover.
- A selection flight takes the pivot up on arrival (`pivotOn` as its `done`), and every flyTo ends the pivot first, so a hand that cuts a selection flight short would leave no pivot. Keep the node in `PIVOT.pending` from the flight's start, clear it in `pivotOn` and `pivotEnds`, and have `steer3d`'s 'start' handler call `pivotOn(PIVOT.pending)` while `FLIGHT.on`.
- A click on a 3D figure is a selection, not a follow. It runs openFigure, agentAt, focusThread, then `select(key, true)` and its `fly3d` flight, and never sets `FOLLOW.work`, so `followIn3d`'s clearance does not run. `ROAM.focus` also draws the clicked figure 1.4 times larger. With agent size not limited, the pivot's wheel dolly can carry the camera inside the figure. On the selection flight and while the pivot holds, keep the camera at least `CLEAR` (3.3) times `FIGURE_RADIUS` (0.8) times `mesh.scale.x` from the focused figure, reusing `followIn3d`'s spring and scratch vectors with no per-frame allocation. The limited default hides this.
- The follow clearance in `followIn3d` (eyes.js) keeps the camera out of a followed figure: when the camera is nearer than `CLEAR` drawn radii, it eases back along the camera-to-figure line, never along target-to-camera. Measure the distance after the follow step has moved the camera that frame, not before, or a fast-circling figure reads clear while the drawn camera sits inside. Inside the zone the camera is never drawn nearer than on the frame before. The floor is `go.least` in followIn3d, a ratchet in drawn radii that resets only once the camera is past CLEAR; a hand or wheel move resets it, so a zoom-in still eases out.
- The camera's distance to a figure is at least STAGE.height / (ROAM.most * tan(fov/2)) radii under limited agent size, about 17 at fov 50 on a 900-pixel stage.
- In Work mode with agents on the node, and in Free mode, a selection does not move the camera to the node; leave the pivot alone there.
- Label size, flight easing and auto zoom are outside this rule; do not change them to fit it.

## Known open cause of clearance dips (graphical#cf, 2026-10-18)
Leftover damping in the orbit controls keeps drifting the camera toward the figure before `followIn3d` first runs. The floor has no value yet on that first frame, so a figure stepping toward the camera can take the camera to about 0.22 radii. Close it either with a hard floor at CLEAR from the first frame (measured after the follow step), or by making the test take its starting distance after the controls settle. Check the code before assuming it is closed.

## Test recipe
- Browser test `test_the_3d_map_turns_and_zooms_about_the_selected_node` in `web/tests/test_web.py`, run with `-n 0 -m browser` on that file. It must fail on HEAD: copy the files aside and run the copy (see `verify-change-proof`).
- Drag on an empty part of the stage, never on a node. A node drag moves the node, the pivot follows it, and a screen-position check proves nothing.
- Read the target after the ease, not right after the pin: the layout still moves then, and an immediate read failed 3 of 5 runs. Hold the layout with P, as the selection test does, before reading.
- For timings, follow the probe setup section of the 3D map skill.
- A clearance test has a thin margin (least 3.00 to 3.04 radii against a 3-radius bar). Rerun it several times before calling a fix done: the follow clearance test failed about 1 run in 6 before the no-nearer floor, and passed 8 of 8 after it.
- Probe the test without the fix by copying the file aside, never by `git stash` in the shared tree.
