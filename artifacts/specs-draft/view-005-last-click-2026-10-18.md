# VIEW-005 amendment draft: the person's last click, told to their system agent

Draft for the owner, from ticket code.interface.graphical#124 (2026-10-18). Not in `specifications/` until approved.

Proposed bullet after VIEW-005's `Status:` line in `specifications/09-viewer.md`:

- Amendment, 2026-10-18, ticket code.interface.graphical#124, the page keeps the last thing the person clicked, so their system agent knows what "this" is: its kind (element, join, agent figure, mascot, board card, banner, notice, chat card, control, panel section), what names it (address and name for a map part, ticket item and agent for a figure or card, the visible label for a control or notice), the state it showed with the open ticket behind it, and when. `web_viewing` returns it as `clicked`. The person's first message to their system agent within two minutes of the click starts with one line naming it, and their bubble shows that line as a chip; a later message, or one sent after two minutes, carries none. The chat's own head, tabs, buttons and message box, a Chat button and the mascot's ask field are not recorded, since a click that opens the chat must not replace what the person asks about; nothing typed is recorded. A join is recorded as a join, clicked on its edge, since it has no node of its own.

Open for the owner:
- The mascot's own ask field (`figures/ask.js` `flushAsk`) sends to the system agent without the line; the ticket named the chat's send only.
