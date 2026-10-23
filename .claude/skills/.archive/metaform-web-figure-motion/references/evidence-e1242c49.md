Causes found (measured, real createAgent/orientAgent driven 60 fps in Node, 10 s per path):
1. plane BUILD anim rocked root.rotation.z sin(1.1t)*0.25 + pitch wobble + y bob on own clock -> cruise roll -14.3..14.3 deg, height span 0.136 figure units.
2. orientAgent lean 0.09 rad per rad/s -> orbit bank only 2.7 deg, swamped by rock (drawn -11.6..17.0 deg, often against turn).
3. gait pitch tipped glide/dart nose down 0.1*speed -> nose 2.3..9.2 deg below level path.
- orientAgent: corner 'bank' characters (kite, comet, plane, owl) bank 0.5 rad per rad/s, max 0.6 rad; others keep 0.09/0.35. Mirrors 2D map's 1.6x lean for corner bank.