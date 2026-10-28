---
name: metaform-pair-worksheets
description: Use when claiming a worksheet or pairing on a worktree.
category: development
---

# Metaform pair worksheets

Read the worktree's holder before any claim. `tasks_worksheet` refuses a claim on a worktree another agent holds, with "`<name>` is held by `<holder>`: pair with them (tasks pair) or message them; only the holder". Treat that refusal as the hold: pair or message the holder, and never re-claim the worktree to get past it.

## Claiming
- Read the holder and partner first, with `tasks_board` or a read-only `tasks_worksheet`. Claim only a worktree nobody holds.
- If a ticket's text says held, treat it as held even when the board shows it free. Report the hold and wait.
- A git worktree `.worktrees/<name>` exists only when the composer named one for the tickets (`worktree=<name>`). A ticket claimed by its own id works in the project folder; do not write that a claim makes a worktree.
- While a named ticket is open, take no other ticket. Re-claim a released worksheet only after that ticket closes.
- If a claim already overwrote someone's items, tell that agent at once and leave the items as they stand until it answers.

## Working the pair
- Register each item's `agent` as the agent's task id, never its name. An item that names an agent by name counts for nobody and its row shows `complete: null`.
- Post the plan to the partner with `tasks_message`, and split items only after the partner accepts.
- Tick an item with `tasks_check` only when you have done it. Any caller can tick any item, so tick only your own.
- Message form: `Name: Task phrase: message`, one line, signed with your agent name.
- Hand a finished item to the partner as one line: `Name: item-id: file:line-range, what changed, the check and its result`. Do not send a paragraph listing several files.
- When a file already holds other agents' uncommitted edits, give the partner your exact line ranges and say that only those lines are yours. A whole-file `git diff` then shows work the partner should not review.
- A reply can be logged without reaching the partner's active turn. If a partner says a reply never arrived, read the messages with the board read and say so. Do not read the store file directly.

## Findings and reports
- Before citing a file name, list its folder (`ls`) in the same turn. A test file named from memory (`tests/test_worktrees.py`) did not exist; the folder held `test_worker_protocol.py`.
- Check every cited line in the same turn. A line from a search for one symbol can sit in a neighbouring function, so read the lines around it and name the function you read.
- Sort each finding as contradiction, ambiguity, gap or wording, with both files' lines.
- Send the joint report to the partner for confirmation before you tick the report item.

## Closing
- Rate only after the report is confirmed. The worktree closes when every participant has rated or said alone.

Evidence and the reasons for each rule: `references/pair-incident-2026-10-25.md`.
