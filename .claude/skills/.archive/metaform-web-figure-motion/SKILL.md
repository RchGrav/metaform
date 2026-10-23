---
name: metaform-web-figure-motion
description: Use when a 3D figure moves wrong: glide, bank, heading.
category: development
---

# Figure motion stays true to each character

A figure's character is read from how it moves. Fix motion at its character record or its locomotion kind, never by special-casing one figure in draw code.

- Character records: `MOTION` in `src/metaform/modules/web/page/agents3d.js` (go, speed, accel, corner, stride, lift, orbit, lap, dir, temper, idle, act, arrive, flourish). `plane` is `go: 'glide'`, `corner: 'bank'`, `arrive: 'swoop'`, `flourish: 'loop'`.
- Locomotion kinds and stiffness: `STIFF` in `src/metaform/modules/web/page/app/figures/walk.js`. Glide covers `plane` and `kite` alike, so a glide fix is checked against both.
- Before code changes, write the real counterpart's motion as checkable properties (nose along velocity, roll with turn rate, no vertical bounce at cruise) and name each place the drawn motion departs from them.
- Measure the actual motion headless (per-channel steps, turn-backs per second, or per-frame position and yaw in typed arrays). Never open a visible browser, and warn before GPU-heavy probes.
- A figure body is rigid. The BUILD animation's returned function must not rock, tilt or bob on its own clock; roll and pitch come only from `orientAgent` and the locomotion. A clock-driven wing rock made the plane roll 14 degrees while flying straight.
- Banking is set by `corner: 'bank'` (kite, comet, plane, owl): `orientAgent` leans them 0.5 rad per rad/s of turn rate, at most 0.6 rad. Other characters keep `LEAN` 0.09 and `MOST_LEAN` 0.35. Keep the bank values in step with the 2D map's lean for the same corner.
- Only `go: 'hover'` tips its nose with speed. Glide and dart noses stay on their path.
- Prove a motion fix with a probe: in a headless browser test, drive `createAgent` and `orientAgent` at 60 fps, read roll and pitch from the body's world quaternion (YXZ Euler), skip about 2 s to settle, then assert on min and max over about 8 s. Confirm the test fails on the old `agents3d.js` by copying that file aside (never `git stash` in the shared tree).
- Per-frame code allocates nothing: scratch vectors and quaternions live at module level. Never cap or throttle the frame rate to hide a jitter.
