---
name: metaform-web-board
description: Use when editing the web board's ticket cards or Archive, when the board is slow or full of done tickets, when setting tickets aside or archiving a board, or when proposing saved or named boards.
category: development
---

# Metaform web board

The board shows open tickets only. A ticket that is done moves to the board's Archive at once. Nothing is deleted. Keep the board to open work, because a board with hundreds of done cards hangs the browser.

- A card click opens the ticket itself: title, task, note and log, as selectable text, with the title and task editable through the server's edit path (`store.edit_work`).
- Only the card's top line is draggable. A `draggable` card swallows mouse-drag text selection, so the card's words cannot be copied.
- Do not add a click action that only selects the map node; the person must be able to read and copy the ticket on the board.
- Archiving done tickets from the board is open to the system agent: `board_line` is not `person_only`. Do not re-add `person_only` to it, or the system agent's Archive of done tickets is refused.
- A card is rebuilt only when what it shows changes. Its comparison text holds the ticket's own fields and the names its chips draw, never its position in the column or a map-wide counter: a move renumbers the positions below it, and a counter bumped by every map op rebuilds every card on the next draw. On 2026-10-20 one move rebuilt 400 of 500 cards; after the fix it rebuilds 0. The order buttons count a card's place when clicked. Chips resolve names through one address index per draw, not a map scan per chip. Keep `test_a_board_of_500_tickets_opens_in_time_and_a_move_makes_no_other_card_again` passing (open under 5 s, no card rebuilt by a move).
- A slow board is measured on its read before and after: `curl` the board's `/api/work?project=ID&limit=0&board=shown` and record bytes and seconds. On 2026-10-20 the read was 855 KB for 157 cards; `uv run metaform set --board-line TIMESTAMP` (UTC, now) archived the done tickets and the same read gave 79 KB for 21 cards with none done.
- On open, the page first draws from the ticket list it loaded at startup. Done tickets still in that list show for a moment, then the board's own read (done tickets archived) replaces them. A flash of 104 done cards that drops to 0 is stale data, not lost tickets. Check the read before reporting tickets missing.
- Setting tickets aside is not closing them. Closing them as done with a "set aside" resolution files them as finished in the Archive. Before telling the person an action reverses (for example, that moving a ticket back to To do reopens it), run that reversal on one ticket and read it back.
- Board features the person has not specified (epics, stories, user journeys, sprints) are outside this design. The board tracks tickets, and done work is visible. Propose board organization only in the person's terms, such as named boards the person can move tickets between.

Reference: [references/board-card-today.md](references/board-card-today.md) records how the card is built now and where to change it.
