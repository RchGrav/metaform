---
name: agent-refusal-rule-delivery
description: Use when a lock refuses a dispatched agent session.
category: development
---

# Deliver a refusal's rule before the refusal applies

An agent refused by a lock must already have been told the rule behind it. A lock holds for a session only once its rule has gone to that session in a real prompt.

- Set a per-session flag (`Session.ruled` in the dispatch runner) when the rule is sent inside a prompt. Until the flag is set, the lock refuses nothing.
- Never send the rule as a turn of its own (CTX-043). It rides at the end of the first prompt each runner process sends a session.
- Check every path that starts or continues a session: hand-off, resume, load and the next message after it, system agent opening, talk, sentinel, intake and prep. A path that skips the rule leaves its agents refused and never told.
- Do not carry the rule only in a ticket's work line; a resumed session never sees the ticket.
- Test it twice: the lock holds only after the rule is sent, and a resumed session is told the rule with its next prompt.
