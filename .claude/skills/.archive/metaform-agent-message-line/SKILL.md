---
name: metaform-agent-message-line
description: Use when editing peer notes, one-line agent messages, or writing the closing reply after a commission, check-in, role publication, delivery, or a ticket done such as a fault repair.
category: development
---

# One line per agent-to-agent message

Every delivery from one agent to another is one line: `Agent Name: Task Phrase: Message`. The only builder is `peering.line`, which reads the `peer_note` prompt in `dispatch/resources/prompts.xml`. Code cuts the lengths; the sender does not.

- **Agent Name:** the sender's agent and ticket number, until agents have names of their own.
- **Task Phrase:** the sender's ticket title cut to 80 characters (`TITLE`); `no ticket` when there is none.
- **Message:** the sender's summary, else the note's first sentence, cut to 200 characters (`MESSAGE`).
- A note holding more ends with the read that returns the whole, `(the whole: dispatch_notes note=<id>)`. A question also says how to reply.

The whole text stays in the sender's thread on its ticket. Do not copy it into a ticket step, since steps move the progress count.

Applies to peer notes, replies a question takes back or misses, orchestration check-ins and change orders, the Facilitator commission, and each entry of the system agent's `dispatch notes` inbox list. A relayed decision of the person's (`decision=true`) stays whole, since it is their own message.

Do not add a second formatter. Its predecessors, runner `inbox_phrase` and peering `inbox_line`, were removed for that reason.

The closing reply a session gives after its check-in is one line in the same shape, `Agent Name: Task Phrase: result`. A closing reply that is a multi-section report or an XML `<result>` block breaks this rule, however complete it is; on 2026-10-21 (code.processor.intake#18) a commission closed that way, and its runtime, role and memory detail belonged in the check-in summary and the ticket note. A bulleted report of the specialist, the model, the files and the records is a context dump: the detail belongs in the ticket note and the check-in summary, and the reply names them.

A fault-repair session that closes its ticket with `op=done` is bound the same way: its closing reply is the one line, and the cause, the fix and the check go in the `resolution` and the check-in summary. A "no code change" verdict is one line too.

Before a closing reply is sent, count its lines: more than one line, or any bullet, bold heading or sign-off, means it is rewritten to the one-line shape and the rest moves to the check-in summary and the ticket note.

Check: send a 1,000-character note and read the delivered line. It must be one line, its message exactly 200 characters, and it must end with the `dispatch_notes note=` read.
