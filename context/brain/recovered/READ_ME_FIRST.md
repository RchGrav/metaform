# Intake prompt recovery

Recovered complete prior files from **all 16 currently exposed branches** of `RchGrav/metaform`, pinned to the returned branch heads. This package preserves previous wording; it does not propose a rewrite or designate a clean/approved master.

## Open these first

`starting-points/` contains five complete historical prompts to compare:

1. **September 13 — `e4581c230b3e` — `specifications/intake.xml`.** An early XML version with the minimal-base-shape completion paragraph and no unconditional code/README examination directive.
2. **September 18, 23:50 EDT — `a8e0e0db3884` — `specifications/Canonical_Intake.xml`.** The September 19 UTC checkpoint, preserving another early full canonical prompt.
3. **September 24 — `156bb3d267db` — `specifications/Canonical_Intake.xml`.** The main WIP branch copy, before the October completion rewrite.
4. **October 1, 00:44 EDT — `ed76db4fc09a` — `specifications/Canonical_Intake.xml`.** The last tracked change on this file before the completion paragraph changed later that morning. It includes the longer universal first-method passage.
5. **Parent `95a8dc6727b0` — `rich/intake.xml`.** The exact previous-commit copy before the October 10 served XML import. This older parallel prompt retains the minimal-base-shape completion paragraph and lacks the added code/README directive. It is a different lineage from the October 1 canonical rewrite.

These are retrieval starting points, not findings that their whole contents are correct or exclusively owner-authored.

## What changed, and when

### October 1, 08:06:53 EDT — completion rewritten amid broader edits

Commit [`0d9e1a639ed7`](https://github.com/RchGrav/metaform/commit/0d9e1a639ed7ea3a9d0929a3b1924c611b90467f) changes `specifications/Canonical_Intake.xml`.

The exact parent `cbef758c083b` still has the paragraph beginning “The task is complete when the final result is a minimal base shape”. The child replaces it with a singular-root/second-final-pass requirement and includes “Ensure that the code node contains all other elemeents”. The full original paragraphs and **all other changes in that commit to this file** are preserved in `key-diffs/01_2026-10-01_completion-and-other-wording.diff`.

This was not an isolated completion edit: the file's goal, concepts, method placement/text, and other sections also changed. Recover the full earlier prompt if you want to restore wording elsewhere.

### October 9, 09:20 EDT — Axiom v2.0 served

[`6316aad925de`](https://github.com/RchGrav/metaform/commit/6316aad925de2f0b7aeaf1c7568d95f85ba28302) replaces the served Axiom procedure with a v2.0 form. At 11:56 EDT, [`63ce039f5b32`](https://github.com/RchGrav/metaform/commit/63ce039f5b32fdccafaa552b78372e18b869fbe0) changes it to v2.1. Full before/after files are in `commit-copies/`, including the distinct control-flow and condition wording.

### October 10, 01:13:07 EDT — code/README directive enters served XML

[`19667e1ba027`](https://github.com/RchGrav/metaform/commit/19667e1ba027b44ba8b8c6d6e7b4f68956c81f05) introduces `src/metaform/modules/intake/resources/intake.xml` with an unconditional first method step beginning “Do not skip examining the code” and referring to examining the README. The served XML also has a root-relationship/second-final-pass completion condition.

The exact parent still has the older `rich/intake.xml`, without that directive and with the minimal-base-shape completion paragraph. The new served path did not previously exist. The comparison in `key-diffs/02_2026-10-10_previous-rich-copy_to_new-served-xml.diff` therefore compares the prior **rich source path** with the newly added **served resource path**, not an in-place edit of one path.

This is the first tracked appearance of that code/README sentence in the prompt paths inspected. Backups with October 10 names were committed later; their names alone do not establish an earlier Git edit time or writer.

### October 12, 02:58:30 EDT — served completion reverts to code-root wording

[`06edcf80e741`](https://github.com/RchGrav/metaform/commit/06edcf80e74108bf606c50fb79bea5dc3cff8ff3) changes the served XML from the root-relationship completion to the singular-root/code-node completion already seen in the canonical copy. It also changes `rich/intake.xml` and adds many backups. Exact parent/child text is in `key-diffs/03_2026-10-12_served-xml-reset.diff`.

### October 14, 02:33:07 EDT — terminology and served-source change

[`0acd2c1d2b7c`](https://github.com/RchGrav/metaform/commit/0acd2c1d2b7cb0d78580f93f7a350a47921490f9) replaces join terminology with purpose-record terminology in the served files and changes which procedure is served. The full versions are retained. Its commit subject describes ownership/authorization; this recovery does not independently confirm those claims.

### October 24 and 28 — additional branch variants

The `remove/consent-layer` branch retains additional October 24 and October 28 edits to the served XML and a separate `rich/intake.axiom` variation. Those are included alongside the main-branch copies; the current main branch does not stand in for every branch's latest prompt.

## Package layout

- **`starting-points/`** — the five complete earlier prompts above.
- **`commit-copies/`** — 199 full files at tracked edits, organized by UTC date, commit, and original repository path. This includes prompts and their companion declarations/docs; all retained history is available, not only excerpts matching the two disputed phrases.
- **`branch-copies/`** — 81 distinct path/content combinations recovered at current branch heads, including XML, Markdown, Axiom, tilde backups, archived copies, and prompt companions. Identical copies across branches are indexed once.
- **`exact-parents/`** — the parent-commit sources for the key comparisons.
- **`key-diffs/`** — three complete comparison files described above.
- **`commit-history.csv`** — dates, commit subjects, original paths, recovered paths, blob identities, queried branches, and source links.
- **`branch-copy-index.csv`** — where each branch-head copy survives.
- **`full-edit-timeline.md`** — every recovered tracked edit, including companion files.
- **`recovery-manifest.json`** and **`branch-heads.json`** — pinned source identities.
- **`SHA256SUMS`** — digests of the recovered package files.

## Verification and scope

All 288 copied source instances were checked against their original **Git blob SHA-1**, including byte count and Git blob header. No whitespace cleanup, spelling correction, newline normalization, formatting conversion, or wording edits were applied to recovered source files. In particular, historical typos remain intact. Newly written indexes and this report are separate from recovered source text.

The search enumerated all 16 returned branches, recursively listed their trees without truncation, and inspected commit histories for the discovered prompt paths, older source locations, backups, and related prompt declarations. All queried history pages contained fewer than 100 commits. Histories follow explicit old and new paths across the `specifications/` → `rich/` and resource-directory moves. Deleted paths at the rename commit are recorded as absent, not as retrieval successes.

This covers currently reachable branch histories for those discovered paths. It cannot recover uncommitted edits, browser-only copies, deleted/unreachable branch histories, or private conversation provenance. A checkpoint's date proves when Git recorded its contents, not when each line was originally written. Git author/committer names and filenames such as `owner-save`, `good`, or `cleaned` do not prove authorship, approval, or correctness.

No repository branch, prompt, or project setting was modified.
