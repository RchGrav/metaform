---
name: wslg-voice-recovery
description: "If /voice says no working recorder in WSL but SoX is installed, WSLg's mic channel is wedged; restart weston and pulseaudio in this distro's system shell"
metadata:
  type: reference
---

Claude Code's "could not find a working audio recorder" message can be misleading here. On 2026-10-30 SoX and libsox-fmt-pulse were installed and the cause was WSLg. `pactl` gave "Connection refused" or hung, `wlog.log` showed audin error 1359, and opening the mic froze pulseaudio on a futex. Restarting pulseaudio alone did not hold, because the next mic open froze it again.

Recovery, run from this distro:

`/mnt/c/Windows/System32/wsl.exe -d Ubuntu --system -u root sh -c 'pkill -HUP weston; sleep 6; pkill -KILL pulseaudio'`

WSLGd restarts both, and msrdc.exe reconnects. It closes any GUI windows in this distro. Terminal sessions survive.

Always pass `-d Ubuntu`. The machine's default distro is Ubuntu-22.04, and a bare `wsl --system` reaches that instance. Use `timeout -s KILL` on any audio test, because a stuck sox ignores TERM.
