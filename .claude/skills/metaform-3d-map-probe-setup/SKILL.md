---
name: metaform-3d-map-probe-setup
description: Use when a probe opens the 3D map, agent view V or E.
category: development
---

# Set up the 3D map before a probe presses V or E

Before the page loads, a probe sets `localStorage` key `metaform.swapped` to the empty string. Without it the 3D map can start in the small area, where `agentView()` refuses V and `EYE.saved` stays null, so the probe measures a view that never opened.

- After pressing V or E, read `EYE.saved` first. If it is null, the setup is wrong, not the eye code; fix the setup before measuring timings.
- Run each headless browser under `env -u DISPLAY -u WAYLAND_DISPLAY` with `--headless=new`, in a scratch home, following scripted-check-spawned-servers.
- Set CPU throttling through CDP only for timing parts; frame rates on a shared machine are noisy, so report them with the throttle level.
