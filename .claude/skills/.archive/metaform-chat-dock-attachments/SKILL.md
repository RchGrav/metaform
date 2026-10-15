---
name: metaform-chat-dock-attachments
description: Use when editing chat attachments: paste, drop, paperclip.
category: development
---

# Chat box attachments: one path for paperclip, paste and drop

Every file a person adds to a chat goes through `attachFiles(files)` in `src/metaform/modules/web/page/app/dock/send.js`, which posts each file to `/api/attach`. A new entry point calls `attachFiles`; never add a second upload route. The server stays the only judge of what is refused.

- A paste attaches only when the clipboard holds files and no `text/plain`. A copy from a sheet carries a picture of itself and must still paste as text.
- A refusal (413, 25 MB limit) or an unreadable file (a dropped folder) becomes a `dockNote` naming the file and the reason, never a toast.
- Saves chain through `DOCK.attaching` (set in `embody.js`); `sendMessage` awaits it so a message carries every file.
- `#helpdesk.dropping` is set only by drags whose `dataTransfer.types` include `Files`; it clears on drop and on a dragleave that leaves `#helpdesk`.
- Dispatch's `attach` is the other direction (an agent attaching to its own chat). Do not merge the two.
- Test: `env -u METAFORM_ROLE -u METAFORM_SESSION -u METAFORM_WORK -u METAFORM_NODE -u DISPLAY -u WAYLAND_DISPLAY METAFORM_BUILD_VIEWS=1 uv run pytest -n 0 -m browser src/metaform/modules/web/tests/test_web.py -k pasted_picture_and_dropped`. Technique: `browser-synthetic-paste-and-drop`.
