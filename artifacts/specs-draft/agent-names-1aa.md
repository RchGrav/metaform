# Draft amendments for agent names, ticket code.interface.graphical#1aa

Drafted 2026-10-21 by the worker on 548c4770223a, from the code as built. Not in `specifications/` until the owner
approves the wording.

## BASE-052 The dispatch module starts an agent on a ticket through ACP

- Amendment, 2026-10-21, ticket code.interface.graphical#1aa, every session is named as it starts: one adjective and
  one noun from dispatch's `resources/names` lists, chosen for the most significant words of its ticket's title and
  task, through Jev when it is on, else by matching the ticket's words to the lists. The name is the best pair no
  other running session of the project holds, taken in the write that records the session; it is kept on the
  session's state line as `name` and carried when the session is resumed. The agent is told its name once, at the head
  of its first turn, and again on its first turn after a compaction. `sessions`, `talk` and `resume` take a name where
  they take a session id, meaning the latest session of that name. No table changes.

## VIEW-039 Agents are started on tickets, followed, messaged and stopped from the page

- Amendment, 2026-10-21, ticket code.interface.graphical#1aa, the page names an agent by its session's name first and
  its ticket's number after it, in the agents key, the chat dock's head, tabs and list, and the Agents menu. A figure
  under the pointer, in 2D and 3D, is named beside the pointer with the model and the thinking level its session runs,
  read from the session's settings as the dock's line shows them; the label is one element whose words change only
  when the figure under the pointer does, it moves with the pointer, and nothing is drawn on the figure.
