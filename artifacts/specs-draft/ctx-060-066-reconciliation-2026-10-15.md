# Draft: CTX-060 to CTX-066 reconciled with the code, 2026-10-15

Ticket document.specification#2 (6b12df5a71424d4f828da4fa84bb0693), for the owner's approval. The ticket asked for
the records in `specifications/11-context.md` to be updated directly; under the spec-amendment rule a worker drafts
the wording here and the owner's session lands it. Nothing below is in the spec yet, and no code was changed.

It reflects, by the code in the working tree at 2026-10-15 23:10 UTC:

- code.graph.knowledge#c, commit 858e3d9: refs as records of the sources layer, `dispatch_link` with `ref=` and
  `why=`, names `{ref_id}@{address}`, layout 22.
- code.graph.knowledge#17, uncommitted: refs stay where they were linked; the live stores restored.
- code#1e, uncommitted: `LINK_LOCK = False` (src/metaform/modules/dispatch/runner.py:143). The runner's comment
  (runner.py:139-142) records the ruling as Rich's, 2026-10-15; his own words are not in this session, so the
  records below say what the switch does and cite the comment, not a quote.
- code.dispatcher.agent#43, uncommitted: the Codex and shell lock, all of it under the same switch. Its own draft,
  artifacts/specs-draft/2026-10-15-ctx-061-062-codex-and-shell-lock.md, holds the method and wording for CTX-061 and
  CTX-062; this draft does not repeat it and only says where those records stand.

In progress, not reconciled: code.dispatcher.agent#47 (the link rule reaches every session before its lock does, and
the command sandbox never locks an agent out) and code.dispatcher.agent#48 (a runner or MCP server older than its
store recovers on current code). Both change runner.py, so its line numbers below can drift; reconcile CTX-060,
CTX-061 and CTX-062 again once they close.

Tests run for this draft, 2026-10-15, `-n 0`: tests/test_store_map.py:237, :260, :292 pass (3 passed);
test_dispatch.py:3496 and :3518 pass, and :3457, :3543, :3557, :3593 skip, "the lock on unlinked files is off until
the rules and prompts for linking are in place, code#1e" (`skip_while_unlocked`, test_dispatch.py:33).

Each record's earlier sentences stay as written. Owner quotes stay word for word: CTX-060's refusal sentence is
untouched. Each block below is appended after the record's `Status:` line.

## CTX-060

Contradicted now: "Every agent dispatch starts on a ticket gets the rule as one line of its first message" (sent only
while `LINK_LOCK` is on), the Build's line numbers, and the Status "built for agents dispatch runs", which reads as in
force.

- Amendment, 2026-10-15, spec reconciliation, ticket document.specification#2, reflecting code.graph.knowledge#c and
  code#1e:
  - Build: built by code.dispatcher.agent#3d and off. With `LINK_LOCK` False (runner.py:143, code#1e) no file is
    locked: `Session.locked` returns None before it reads anything (runner.py:2219), so `write_text_file`
    (runner.py:2314, lock checked at :2320) and `edit_locked` (:2235) let every write through. `work_line` sends
    `work_link` only while the switch is on (src/metaform/modules/dispatch/__init__.py:723, :730). With it on, the
    lock is as built by #3d: `placed()` (runner.py:346) over `sources_index` (:329), which since
    code.graph.knowledge#c reads the store's ref records, `Store.refs()`, and places a ref on a join under its
    receiver's Address. Prompts: `work_link` (prompts.xml:196, with #43's sentence on commands), `write_unlinked`
    (:203), `link_call` (:207).
  - Acceptance: 1, test_dispatch.py:3457, skips while the switch is off. 2, :3518, passes. 3, :3496, passes; the
    added case (a ref naming only `src/` leaves `src/fresh.py` locked) is still to add.
  - Status: built, off since code#1e; the requirement does not hold today. Open: the wording of `work_link` and
    `link_call` (open question 9), and code.dispatcher.agent#47, in progress, which changes how the rule reaches a
    session before its lock.

## CTX-061

Contradicted now: "today the lock does not hold for Codex" and `EDITS_ASK` with its line numbers; replaced by #43's
`held_settings`, `ASKING_MODES`, `MODE_APPROVES`, `hold_mode` and `unsandboxed`.

- Amendment, 2026-10-15, spec reconciliation, ticket document.specification#2, reflecting code#1e and
  code.dispatcher.agent#43:
  - Build: built for Claude Code, ACP fs writes and Codex, all off under `LINK_LOCK` (runner.py:143).
    `request_permission` (runner.py:2663) reads the request with the call it began as, then `edit_locked` (:2235) and
    `unsandboxed` (:2254), before any approval. `held_settings` (runner.py:155) replaces `EDITS_ASK`: the four edit
    tools' ask rules and #43's sandbox, sent on session/new, load and resume, and nothing while the switch is off.
    Codex: `ASKING_MODES` (:147), `MODE_APPROVES` (:151), `hold_mode` (:1647). The method and its evidence are in
    artifacts/specs-draft/2026-10-15-ctx-061-062-codex-and-shell-lock.md, awaiting the owner.
  - Acceptance: 1, test_dispatch.py:3543, and 3, now test_codex_is_kept_asking_and_cannot_write_an_unlinked_or_ignored_file_or_lift_its_sandbox
    (:3557), skip while the switch is off. 2: :3557 checks session/new's `_meta`; session/load and session/resume are
    still to add.
  - Status: built, off since code#1e. Open: the live check of a real Claude Code session in bypassPermissions
    editing an unlinked file (open question 10; code.dispatcher.agent#47's acceptance includes it), and the owner's
    approval of #43's method.

## CTX-062

Contradicted now: "Build: Open.", "Acceptance: Open." and How it shows' "Today this is not so", for agents dispatch
runs, as #43's draft says.

- Amendment, 2026-10-15, spec reconciliation, ticket document.specification#2, reflecting code#1e and
  code.dispatcher.agent#43:
  - Build: built by #43 for agents dispatch runs and off under `LINK_LOCK`: Claude Code's command sandbox
    (`held_settings`, runner.py:155), Codex held in read-only (CTX-061), the runner's own terminal under bubblewrap or
    sandbox-exec (`confined_command`, :174), refused escalations with `command_unsandboxed` (prompts.xml:220) and
    `terminal_unconfined` (:225). No worktree was built. Detail in #43's draft.
  - Acceptance: 1 is test_dispatch.py:3593, the runner's terminal; 2's ignore-listed case is in :3557. Both skip
    while the switch is off.
  - Status: built, off since code#1e. Open: gemini-cli's own shell, agents connected only over MCP (open question
    11, second half), the owner's approval of the method, and code.dispatcher.agent#47, in progress, so the sandbox
    never locks an agent out of running tests, ruff and git.

## CTX-063

Contradicted now: How it shows' answer fields (it also answers `ref` and `id`), Build open item 2 (built), and "`map
code-link` writes the code layer" (the verb and the layer are gone).

- Amendment, 2026-10-15, spec reconciliation, ticket document.specification#2, reflecting code.graph.knowledge#c and
  #17:
  - Build: the `link` verb (src/metaform/modules/dispatch/__init__.py:2738, declared at :3999) writes a ref record
    by `Store.link_ref` (src/metaform/data/store.py:259; `link`, src/metaform/data/refs.py:276), named by `ref=` or
    derived from the path (`derived`, refs.py:177), with `why=` and who linked it, the runner's work and session or
    the surface (__init__.py:2776-2779). It answers `file`, `node`, `ref`, `id`, `linked`, `made` and `said`
    (:2787). A name taken or reserved writes nothing and is answered with `linked` false, exit 0 (:2780-2782).
    Linking again where it is answers `linked` false (:2783). A file linked at another element is a second ref there,
    with a name of its own; no ref moves (refs.py:279-280, code.graph.knowledge#17). Open item 2 is built. Open items
    1 (the element is still made in the active map's base, __init__.py:2765-2775) and 3 (no `join=`) are unchanged.
    `map code-link` and its code layer no longer exist.
  - Acceptance: 1, test_dispatch.py:3496, passes. 2, :3457, skips while `LINK_LOCK` is off, so that the link lifts
    the lock at once is not shown today. 3 and 4 are still to add; 3 fails today.
  - Status: built, with the ref record. Open: the element made in the base, linking to a join.

## CTX-064

Contradicted now: "always" holds only while `LINK_LOCK` is on, and the Build's line numbers.

- Amendment, 2026-10-15, spec reconciliation, ticket document.specification#2, reflecting code#1e:
  - Build: `ignored` (runner.py:359) over `home.ignore_patterns` (src/metaform/home.py:210), and `write_ignored`
    (prompts.xml:212), as built by #3d. `locked` returns None before it reads the list while `LINK_LOCK` is False
    (runner.py:2219), so ignore-listed paths are writable to agents today (code#1e; runner.py:139-142).
  - Acceptance: 1, the ignore half of test_dispatch.py:3457, skips while the switch is off. 2 and 3 are still to add.
  - Status: built, off since code#1e; the requirement does not hold today. Open questions 12 and 24 unchanged; the
    `write_ignored` wording awaits the owner.

## CTX-065

Contradicted now: the Build ("Open: code.graph.knowledge#c" and "Today a ref is a row of `refs`") and the Status
"open in build".

- Amendment, 2026-10-15, spec reconciliation, ticket document.specification#2, reflecting code.graph.knowledge#c
  (commit 858e3d9) and #17:
  - Build: built. Each ref is an item of its own in the sources layer at one element or join, written only as
    versions of that item: its value is its ref_id, its refs its key and value then its details, its extra who linked
    it, when, the place named and why (`_write`, refs.py:258). Writes: `Store.link_ref`, `place_refs`, `unlink_ref`
    (store.py:259, :268, :274; refs.py:276, :384, :397, `edit` :412). Reads: `Store.ref`, `Store.refs` (store.py:282,
    :287). `sources_index` reads `Store.refs()` (runner.py:329). Layout 22 (src/metaform/sqlite.py:25-26) runs
    `refs_to_records` (src/metaform/data/upgrade.py:241; `migrate`, refs.py:446), each ref kept at the place its item
    was (#17). The `refs` table is layout 20's and is no longer created. The STORE-012, MAP-021 and LAYER-028
    amendments for this are drafted in artifacts/specs-draft/store-012-ref-records-2026-10-15.md.
  - Not built: memory citations and work records naming a ref by its id; they still cite by key and value. How it
    shows' `map where` listing each ref with its id and who linked it was not checked for this draft.
  - Acceptance: 1 to 3, tests/test_store_map.py:237, pass. 4, test_dispatch.py:3496, passes. 5, test_store_map.py:292,
    passes. The live upgrade at 22:05 UTC moved refs toward the trunk and made 6 elements for them; #17 restored every
    ref to each place it held and removed those elements as versions (artifacts/refs-restore-2026-10-15/README.md).
  - Status: built 2026-10-15. Open: citations and work records by ref id.

## CTX-066

Contradicted now: How it shows' "Recording the same ref at `code.dispatcher.runner` leaves one ref, linked at
`code.dispatcher`.", Acceptance 1, 2 and 5 (the moving link), and the Build "Open: code.graph.knowledge#c. Today refs
have no name." What this means already carries the owner's correction in the working tree.

- Amendment, 2026-10-15, spec reconciliation, ticket document.specification#2, reflecting code.graph.knowledge#c and
  #17:
  - Build: built without the `:` part. `named` (refs.py:110) writes `{ref_id}@{address}`; a ref on a join is named at
    its receiver's Address, and its record's `join` gives the join. `read` (refs.py:144) takes an id, a ref_id or a
    name, reads past any `:` part, and answers a name whose Address is not where the ref is with where it is and a
    notice (:162-164). A ref never moves: the same key and value at another node is a second ref (refs.py:279-280).
    Uniqueness: a ref_id held by another ref, or given for a key and value another ref at this node holds, writes
    nothing and returns a notice naming `{ref_id}@{address}` (refs.py:300-310), not an error. A derived ref_id skips
    taken and reserved names (`derived`, :177; `RESERVED`, :41). Points to settle: 1 is met by a read of its own,
    `read`, not `map/scoped.py`'s `resolve` (src/metaform/modules/map/scoped.py:59, unchanged); 2, the repo skill no
    longer bans `re`, `pe`, `ifd` and `de`; 3 is open.
  - Acceptance: 1, 2 and 5 are replaced as drafted in
    artifacts/specs-draft/ctx-066-refs-stay-where-linked-2026-10-15.md (two refs, `x@code.a` and another at
    `code.b`; the notice names `x@code.a`); tests/test_store_map.py:260 passes. 3 waits on open question 25. 4 holds:
    no name has a `:` part.
  - Status: built 2026-10-15 without the `:` part. Open: what `:` names (open question 25) and whether `main` is a
    ref_id (open question 13).

## Open questions

- 9, 10, 11, 12, 24: unchanged as questions; each record above now says its answer is built and off while
  `LINK_LOCK` is False. #43's draft proposes answers to 10 and 11.
- New, for the owner: when does `LINK_LOCK` go back on, and is it one switch for the link lock, the ignore list's
  read-only rule and the command sandbox together, as built, or does CTX-064's "always" keep the ignore list
  read-only while the link lock is off? (CTX-060 to CTX-064; code#1e)

## Change note, for the section's head or "Amendments to other records"

- 2026-10-15, spec reconciliation, ticket document.specification#2: CTX-060 to CTX-066 brought to what is built,
  reflecting code.graph.knowledge#c (858e3d9), code.graph.knowledge#17, code#1e and code.dispatcher.agent#43.
  code.dispatcher.agent#47 and #48 are in progress and change runner.py; CTX-060 to CTX-062 are reconciled again when
  they close.
