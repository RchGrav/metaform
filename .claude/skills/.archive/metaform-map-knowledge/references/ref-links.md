# Refs and file links: details

- A ref_id is dotted segments of letters, digits and underscores. A title with spaces or hyphens is refused by `dispatch_link`, and nothing is linked (`STORE-029 runner hand-over draft` was answered "cannot be a ref_id"). Name a spec draft as `specs_draft.store_029.runner_hand_over` and keep the title in `why=`.
- A ref_id is unique in the base. A clash writes nothing and answers with the ref that holds the name.
- The 13 field names of CTX-087 (`metaform.data.RESERVED_REF_NAMES`) are refused as ref_ids. No other name is banned (CTX open question 19).
- The same file linked at a second place is a second ref with a derived name: `metaform.data.refs` at the first place, `metaform.data.refs_py` at a second, then `_py_2`. The link answers the name it made, so check it.
- `ref` is made from the path when left out. The link answers the ref's name and id.
- A ref is one item of the sources layer, written only as versions (src/metaform/data/refs.py, built 2026-10-15, code.graph.knowledge#c). Cite its item id or its ref_id, never a row or a position. Refs are not properties and never move (owner ruling, 2026-10-15); the moving link of CTX-009 applies to properties only.
- Defect this rule prevents: a move to the longest common prefix made the `code` and `code.store` elements hold about 90 refs with no joins. code.graph.knowledge#17 deleted the move from refs.py and restored every live store's refs to their pre-layout-22 places. A process started before that still moves refs until it is restarted: check start times with `ps -eo pid,lstart,args | grep "mcp serve"`.
- Never create an element to hold refs. A role-less element at a short prefix such as `code` is drawn by the page as the parent of everything under it, so an upgrade or link that makes one is a defect.
- Before linking, run `metaform map where` on the Address. If it is missing, link at the existing element that realizes the file, or ask in the ticket. Do not name a new one to hold a file.
- Automatic code-layer matching is gone: the `map code-*` verbs and `code_index.py` were deleted on 2026-10-15 (ticket code.analyzer.refactoring#1a). The matcher had put 44% of files in a folder fallback. Place files by an explicit link made while working on the file.
- A script that writes a file (sed, python, a bulk rewrite) is an edit too: link each file before the script touches it. Editing through Bash to get past the gate, then linking afterwards, is the same breach.
- Read the ticket before assuming any part of a ref or link change is built. A status line written in a skill goes stale.
