# Browser-checking the web GUI

A throwaway probe goes in /tmp, outside the repo, and runs as `python -I probe.py` so nothing in the working folder shadows an import.

## Private server

- `export METAFORM_HOME=/tmp/<name>/home`, then `metaform add project proj /tmp/<name>/proj` and `metaform set --web-port=<free port>`.
- Start with `metaform web --json` from the project folder. Use a port other than the person's (7433 by default).
- Stop with `metaform web stop`, then delete the temp folders.

## Playwright, Python

- Launch Chromium with `--use-fake-device-for-media-stream`, `--use-fake-ui-for-media-stream` and `--autoplay-policy=no-user-gesture-required`. For WebGL in headless runs add `--use-gl=angle --use-angle=swiftshader --enable-unsafe-swiftshader`. Make the context with `permissions=['microphone']` and `bypass_csp=True`.
- The page CSP forbids string evaluation. `page.wait_for_function('<string>')` fails with an EvalError about 'unsafe-eval'. Either use `bypass_csp=True` or pass a function.
- A function given to `wait_for_function` must not be `async`: an async arrow returns a Promise, which is truthy, so the wait ends at once. Poll with a loop of `page.evaluate` and `time.sleep` under a deadline instead. A TypeError on a null field right after a wait means the wait returned early.
- Stub the voice endpoints with `page.route`: `**/api/voice/status` returns the engine state (`server.installed` and `server.downloaded` true for the server engine); `**/api/voice/transcribe*` returns `{text: ...}`.
- Stop the agent from starting: add a capture-phase `submit` listener on the compose form that records the box value, then calls `preventDefault()` and `stopImmediatePropagation()`.
- The chat trims the sent text, so compare with `.strip()`.
- Hold a key with `page.keyboard.down(key)` and `up(key)`; a tap is `press`.
- Print each check as PASS or FAIL. Cover the held path, the tap that hears nothing, a focused control that must keep its own key, a text box that must still type, and the modified-key path that must be unchanged.

## Pictures from another camera

- `web look` renders from a figure's eye, not the person's camera. The 3D signs are oriented for the person's camera and drawn double-sided, so a render from behind a sign reads mirrored. `signsFor(camera)` in `map3d/labels.js` turns the signs for that one render and restores them; `lookFrom` in `figures/eyes.js` applies it only for a camera other than the person's.
- Check the picture by reading a label with a known name. Mirrored text means the sign's back is facing the eye.
- Stand in for the mascot's body without a system-talk session: pause frames with `window.metaform.pause3d(true)` first, then set `MASCOT.mesh = MASCOT.mesh || new THREE.Object3D()` and move it. `eyeOf` falls back to the object's world position and direction.
- Confirm the person's view is untouched: record every sign's quaternion before the look and after it, and compare.
- Keep the probe in /tmp, not as a repo test file.
