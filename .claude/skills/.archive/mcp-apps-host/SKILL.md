---
name: mcp-apps-host
description: Use when editing MCP Apps views or ui/ methods in chat.
category: development
---

# The chat's MCP Apps host

Declare in `HOST_CAPABILITIES` (`page/app/session/apps.js`) only what the host implements. Refuse every other request with -32601 and say so in the view's `.appnote` line, so a view never waits on silence.

- Check a capability change against the stable ext-apps spec revision and the SDK. A method the SDK declares but the stable text does not list is declared only once the host implements it.
- Tool results: `ui/notifications/tool-result` carries `content`, `isError` and `structuredContent`. The runner (`metaform_called` in `dispatch/runner.py`) keeps `structuredContent` only under its size limit. A view paints from it first, so a dropped field paints blank. Test a view's painted text through the real node view, not a stub.
- `ui/update-model-context` is kept per thread and view and sent before the person's next message to that session (`withContext`). `ui/message` is sent only after the person confirms.
- Teardown waits up to 600 ms for the view's answer before pop-out, back, close or a project switch. The project switch goes through `leaveApps()`, called from `leaveAgents`.
- The frame stays an opaque-origin sandbox unless asked; it differs from the spec's separate-origin proxy, and that stays.
- Not offered: serverResources, app-provided tools, downloadFile, sampling.
