---
name: metaform-chat-dock-layout
description: Use when editing the chat dock layout, agent list or tabs.
category: development
---

# Chat dock layout: wrap, redraw, and name the classes

Put every dock child inside `.chatpane`, never beside it, and give new dock classes a dock-specific name. Global `app.css` rules for `.pane` (~466) and `.item` (~653) style any element carrying those classes.

- `#helpdesk`'s body under the head is `.chatbody`, holding `nav.agentlist` and `.chatpane`. `.chatpane` is `position:relative`, so `.latest` centres on it. Elements appended to `#helpdesk` itself (resize grip, SESSIONPOP, workspace edge) stay its direct children.
- The list shows only when `#dock` has class `open big` and the page is wider than 820 px (`narrowPage()`). `drawAgentList` in `dock/threads.js` returns at once otherwise. Its callers are `drawTabs`, `renderAgents` (`agents/dispatch.js`) and `ticketsChanged` (`live/ops.js`).
- Step counts reach the list only through `ticketsChanged`, which refreshes `S.tickets`. `renderAgents` alone does not see them.
- A MutationObserver on `#dock`'s class and the 820 px media query call `drawTabs` only when shown-ness flips. `drawTabs` hides the tab strip while the list shows.
- Rows are keyed and rebuilt by `keyedFill`, whose text holds every shown field plus `on`, so one step rebuilds one row. A row click resolves the open chat at click time, because a kept row's closure can be stale.
- Alt+Up and Alt+Down in `send.js` walk `.agentrow` rows while the list shows.
- A ticket's `item` and `title` come from `with_glyphs` in `web/server.py`, read from map's `numbered` table. Tickets made by `store.add_work` in tests have no number.
