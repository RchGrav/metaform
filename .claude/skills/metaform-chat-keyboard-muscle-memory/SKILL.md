---
name: metaform-chat-keyboard-muscle-memory
description: Use when changing chat Escape, Up arrow, close keys, or the /new and /clear chat commands.
category: development
---

# Metaform chat keys follow Claude Code

Rich works in Claude Code all day. The web chat keys copy its reflexes, because a mis-key that costs him the window and a mouse hunt costs a whole turn.

- Escape while a turn runs interrupts it. Ctrl+. keeps working as an alias.
- Escape with an empty compose box and no turn running does nothing. Escape never puts the chat away. The × and the C key do that.
- Escape with text in the box clears it. Ctrl+Z gets the text back.
- Up in an empty compose box fills it with the last message sent in this thread. Further Up presses walk back through older ones, Down walks forward. With text in the box, or once a recalled message is edited, Up and Down move the cursor as usual. Down past the newest message empties the box. The history is per thread and kept on this page only.
- Escape on another agent's thread still goes back to My agent first.
- `/new` and `/clear` are the chat's own commands on every agent. On My agent, `/new` calls `dispatch system` with `fresh=true`, so it always starts a new conversation. `fresh` ends a running or held system agent the way the person's stop does, then starts one that resumes nothing. Without `fresh`, dispatch reuses the running system agent and hands back its old context. On another agent's thread, `/new` ends that thread and opens a new one beside it. Code: `app/dock/commands.js:newConversation`, `dispatch/__init__.py:system`.

Code lives in `app/dock/send.js` (`chatKeys`, `sayKeys`, `escapeChat`, the × tooltip). The helpdesk design comment in `app/dock/helpdesk.js` says Escape closes the chat, and that line is superseded by this rule. Amend the VIEW record in the same change (see metaform-spec-amendments).

ACP cannot take back a turn already sent. An interrupted turn has reached the agent, so the corrected message arrives as the next turn.

Rolling back the agent's context to an earlier message is undecided. Options and findings are in `references/rollback-options.md`.
