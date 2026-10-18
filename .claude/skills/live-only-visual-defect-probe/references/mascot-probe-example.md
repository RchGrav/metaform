# Example: mascot shake probe (2026-10-16)

- Headless runs showed only the text-to-speech size pulse (about 4 percent, 2.9 Hz). The live shake was not reproduced headless.
- The probe returned per-channel summaries for the last ~4 s: screen_x/y, yaw, pitch, scale, gait_y, gait_pitch, body_y, body_lean, want_x/y/z, camera_x/y/z. Each channel reports least, most, median step and turns-back-per-second.
- Read rule: the channel whose turns-back-per-second is high names the unstable layer. Screen/yaw/pitch means the body transform; scale means the size pulse; gait/body means the animation; want means target switching; camera means the camera.
- The probe was committed with only its own hunks, and a single browser test covered it.
