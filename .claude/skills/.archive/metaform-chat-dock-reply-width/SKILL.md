---
name: metaform-chat-dock-reply-width
description: Use when editing #helpdesk reply bubble width or 72ch caps.
category: development
---

# Chat dock reply width

Agent replies in the chat dock take the width their content needs, up to the dock's width less the log's padding on each side. Never put a character cap (`ch`) on a reply, prose included, and never add a second margin on the bubble: the margin is the log's `var(--s3)` padding. Write margins as the page's spacing tokens (`var(--s1)`..`var(--s6)`), never literal px.

- The person's own bubble stays on the right, capped at `min(85%,64ch)`. That is the only capped bubble.
- Code scrolls sideways only when it is wider than the dock less the margins.
- The global `.row` rule wraps, so a full-width reply pushes its time and Copy (hover-only) onto a line under it. Accepted: keeping them beside the reply would take width from it.

Prove a change with measured boxes, not screenshots alone. Copy `app.css` aside with the old rule restored (never `git stash`, the tree is shared), then run `python -I scripts/chat_width_probe.py <css> <dock_px> <out_dir>` on the before and after copies and compare `bubble`, the gaps and `sideways`. Probe at a wide dock (about 1960 px) and a narrow one (about 600 px).
