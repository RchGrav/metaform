---
name: metaform-orchestration-check-in
description: Use when returning a ticket with orchestration check-in.
category: development
---

# Metaform check-in: state, then summary, then key=value

Return a finished ticket with the state word, the quoted summary, then the keyword arguments: `metaform orchestration check-in returned "<summary>" assignment=<id> 'candidate=<json>' 'evidence=<json list>'`. Placing `assignment=` before the state word or the summary is refused with "assignment= comes after the required nouns".

- `candidate` names the work's `kind` (for a working tree, `working-tree`), its `branch` and the changed `files`, as one JSON object.
- `evidence` is a JSON list of the commands you ran and what they showed: the test counts, and the failure you saw without the fix.
- Put the work's own result in the summary, and name any part left to another ticket by its ticket id.
- Quote the arguments in single quotes when they hold JSON, so the shell does not split them.
