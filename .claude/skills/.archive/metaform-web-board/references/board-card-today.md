# Board card as built on 2026-10-19

File: src/metaform/modules/web/page/app/board/board.js, around line 119.

- The whole card is `draggable: 'true'` so it can move between columns.
- `onclick: open` selects the card's node on the map and opens that node's history. No view of one ticket exists.
- The card's controls are move, agent, glyph and hold. No title or task edit control exists on the page, though the server edits tickets through `store.edit_work` (server.py).
- Fix direction: click opens a ticket panel with selectable title, task, note and log, and editable title and task; only the top line stays draggable.
