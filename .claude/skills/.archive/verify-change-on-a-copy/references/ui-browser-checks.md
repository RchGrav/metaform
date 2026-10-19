# UI and browser checks

Use this file for a change that must not alter what a page shows, and for browser waits and timed windows. Scripts: `scripts/pixel_diff.py`.

## Pixel comparison of a must-look-the-same change
- Shoot the untouched code, shoot the changed code, and diff every picture. Prove it with pixels, not by eye.
- Freeze what moves: seed `Math.random`, drive `requestAnimationFrame` from a virtual clock, and keep viewport, device scale factor and fixture data identical on both sides. Hold each CSS animation at its start (`document.getAnimations()`, then `pause()` and `currentTime = 0`).
- A roaming figure (an agent avatar, a wanderer) draws on `Math.random` too and shifts every seeded cycle after it. Stub its data endpoint to an empty list in the probe (`page.route` on the API path) before shooting, and say so in the report.
- Shoot both sides with the same script and the same output names, headless only. Never off-screen: under WSLg an off-screen window still shows on the screen.
- Serve the before side from a `git worktree` of the base commit, on its own port and scratch home, so the working tree stays untouched.
- Run `scripts/pixel_diff.py BEFORE AFTER --mask x0,y0,x1,y1` once per picture set. Mask real-time CSS animations you cannot freeze, and say so in the report.
- Pass means: nothing above 60 outside the masks, and the count above 24 at anti-aliasing scale. Report the counts, not "looks the same". A cluster above 120 is a finding: crop before | after | amplified diff side by side and explain it before accepting.
- For redrawn dots or paths, report displacement beside the count above 24: the largest distance from each element to its intended point, in px. Sub-0.01 px displacement with about one pixel per element over 24/255 is anti-aliasing, not a moved element.
- A seed applied after `load` does not freeze state the page drew from `Math.random` while it loaded. Seed in an init script (`add_init_script`) before the page's scripts run. When the two sides cannot share a page, compare inside one page with the clock held: shoot, redraw the changed element its old way in place, shoot again, and diff the pair.
- The image diff runs without touching the project: `uv run --no-project --with pillow --with numpy python` from a scratch folder outside the repo.
- When the project venv lacks PIL, stitch before | after crops inside a headless page: put both PNGs as `data:` images in a `set_content` body, take one `screenshot`, and run it with `python -I` from the venv that has Playwright. Do not install an imaging library into the project to do it.
- A fixed-height panel (a menu, a dock list) shows only its first rows. Scroll its container (`scrollTop = scrollHeight`) and shoot again, or the changed rows never reach the picture.
- For a UI fix, shoot the same seeded state before and after, keep the pictures and the probe script together in one evidence folder, and write a short EVIDENCE.md beside them: the scenario seeded, what the before picture shows, what the after picture shows, the check command, and what a mutant of the fix fails with. Delete any temporary probe copy left in the source or test tree.
- A `page.screenshot` on a page with a transition in flight can time out at the default 10 s. Read the state first, then screenshot with `timeout=90000, animations='disabled'`.
- An in-page harness that reads an internal field a refactor moved fails at once (`Cannot read properties of null`). Derive geometry from the DOM or from the page's own function, not from the field.
- A timed intro sampled at fixed moments: do not use Playwright `page.clock`, which freezes `requestAnimationFrame` so `page.screenshot` times out. Pin `performance.now()` per frame through `add_init_script`, step it, and wait for one rendered frame before each shot.
- When the before side is a browser test rather than a pixel probe, extract `git archive HEAD src conftest.py pyproject.toml` to a scratch folder, run the same test with `PYTHONPATH=<scratch>/src`, and print `metaform.__file__` in the test output. Without that line a before run can silently import the working tree.

## Stacking order: prove what is on top at a point
- Pick a point inside the element that must be on top. If it has `pointer-events:none`, enable pointer events for the probe only.
- Assert `document.elementFromPoint(x, y)` lands on that element before the competing layer opens.
- Open the competing layer (a window, menu or panel) over the same point, then assert the probe lands inside that layer.
- Revert the value under test on a copy of the tree and confirm the probe fails there. Never toggle the value in the shared tree.
- A probe that reads only computed style passes whether or not the layer is drawn over its neighbours.

## Playwright waits use a synchronous predicate
- A Python `page.route` handler runs only while the test is inside a Playwright call. A wait that polls a list the handler fills never lets the handler run, so the request is never answered. Make each check call Playwright, for example `eventually(lambda: page.evaluate('() => 0') or held)`.
- A wait predicate returns a plain value, never a Promise. An `async () => ...` predicate is truthy on the first poll, so the test never waits.
- Load the module once at setup into a `window` global, then wait on a synchronous read, for example `page.wait_for_function('() => window.__roam2d.ROAM2D.figures.size === 2')`.
- Before trusting a wait, make its condition false on a sed-edited copy of the test (never the original) and confirm it times out. If the copy fails at an earlier, unrelated assertion, the wait was never reached: skip that step and rerun. Run the copy unfiltered or through `tail`; a `grep | head` pipe once hid the failure entirely. Delete the copies afterwards.
- Click the value the wait returned (`wait_for_function(...).json_value()`), not a position read earlier.

## A UI test that drifts by a small margin: fix the side that is wrong
- State what the measured quantity is for, and compute the expected value from the same inputs the product uses, not from a shortcut that drops one.
- Check whether the drift predates your change: put the files you touched back to HEAD in a copy and rerun. If it still fails, the cause is elsewhere.
- Never widen the tolerance, skip the test or mark it xfail to get green. A test everyone learns to ignore hides the next real regression.
- Show the failure before the fix and the pass after it, over several runs, with a single-test filter.
- If other agents are editing the same file, tell the user before editing it.

## A slow page load: time the request, the payload, then the render
- Time the read alone with `curl -s -o FILE -w "%{http_code} %{time_total}s %{size_download}B"`, and count the rows in FILE.
- A response under about a second with a page that takes tens of seconds means the cost is in the page: each row built, drawn or measured. Read only what the view shows, filtered on the server; never hide rows in the page.
- Archive or paginate what the view does not need; never delete it.
- Count what the default window keeps on the real data before calling it a fix, and name the cutoff that shrinks it.
- Check the load path too: a full read at page load, or on every change, used only to count figures costs as much as a slow board. Have the server return the counts and read only the items a change names.
- Report the page's open time before and after, measured the same way.

## Browser tests of time windows: move the stored timestamp, not the clock
- To test a window that has passed, set the timestamp the page stored back by the needed amount, then exercise the normal action. Do not advance or fake the browser clock: a clock jump fires every page timer at once, so the test measures a burst the real page never sees.
- Assert both sides: inside the window the effect appears; past it, it is absent.
- Keep a second action inside the same window to confirm the record is consumed once.
- A window test that fails only on a busy host: say so, and count the failure as unreproduced if three reruns pass.
