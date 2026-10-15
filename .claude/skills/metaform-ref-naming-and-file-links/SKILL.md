---
name: metaform-ref-naming-and-file-links
description: Use when naming a ref or linking a file to a map element.
category: development
---

# Ref naming and file links in Metaform

A layer is named by its scope, then `@`, then its content (`base@best_practices`). A ref is named `{ref_id}@{address}` (CTX-066): its id first, then the Address it is linked at. The `:{join}` part is not built while what it names is open (CTX open question 25): a ref on a join is named at its receiver's Address and its record's `join` says which. Whether an element's main ref is named `main` is open (question 13); do not build it.

- A `ref_id` is a proper noun for what the referenced thing is; for code, its qualified name (`metaform.data.refs`). Underscores and periods are allowed, as in Address segments. It is unique in the base; a clash writes nothing and answers with the ref that holds it. The 13 field names of CTX-087 (`metaform.data.RESERVED_REF_NAMES`) are refused as ref_ids; no other name is banned (question 19).
- The `ref_id` is the identity. Moving a ref changes its `@address` part, not its id. A read with a stale address (`store.ref('x@code.a')`) answers with where the ref is now.
- A ref is one item of the sources layer, written only as versions (src/metaform/data/refs.py, built 2026-10-15, code.graph.knowledge#c): cite its item id or its ref_id, never a row or position. Linked again at another place it moves to the longest common prefix of the two (CTX-009); at a place its link already covers it stays.
- An agent places a file on an element by an explicit link, made while it works on that file, and before the first edit to it: an edit to an unlinked file is refused with "To unlock access to this file, please first link it to its functionality in the map", so run `dispatch_link` with the node first, then edit. The link is `dispatch_link file=<path> node=<Address> ref=<ref_id> why=<why>` (CLI `metaform dispatch link`); `ref` is made from the path when left out. It answers the ref's name and id. Never link through `map knowledge op=add-element` with refs: that replaces the refs last linked at that element. The `map code-*` verbs and `code_index.py` were deleted on 2026-10-15 (ticket `code.analyzer.refactoring#1a`), so there is no code-layer link to write. Do not place files by matching code structure: the automatic matcher put 44% of files in a folder fallback and was removed with them.
- A script that writes a file (sed, python, a bulk rewrite) is an edit too: link each file with `dispatch_link` before the script touches it. Editing through Bash to get past the gate, then linking afterwards, is the same breach.
- Read the ticket before assuming any part of a ref or link change is built; a status line written in a skill goes stale.
