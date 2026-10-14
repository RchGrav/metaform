---
name: agent-chat-attachments
description: Use when attaching files to agent chat with dispatch attach.
category: development
---

# Agent files in chat

`dispatch attach path=...` publishes a file into the calling agent's own chat. The verb copies the bytes into the project's folder in the Metaform home, under the session and a fresh 16-hex id, so a reused name or a later edit never replaces an earlier attachment.

- The source must resolve inside the project folder. The caller is found through METAFORM_WORK and METAFORM_SESSION, as `dispatch timer` finds it, and only that chat gets the attachment.
- Downloads are served by session and id only (`GET /api/attachment`), never by a path from the request. A traversal attempt answers 400; a missing file answers 404.
- The page asks `check=1` before a download, so a removed file shows "no longer kept" on its card instead of a failed download.
- A runner started before the change refuses the op. The verb then removes its copy and empty folder before it reports the refusal; confirm with `ls` that nothing is left.
- Restart the web GUI after changing `modules/web` (`metaform web start`) before testing a download in a browser.
