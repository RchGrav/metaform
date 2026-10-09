# Handoff

This is the starting point for the Metaform session that continues the build in this repository. The rules in this repository's `CLAUDE.md` govern the work. The spec in this folder is the contract, starting at `00-index.md`. `BUILD-BRIEF.md` says how to build from it.

## Where things stand

- **Branch:** `chassis`, pushed to `github.com/RchGrav/metaform`.
- **Spec:** sections 01 to 09, about 230 records. The merged questions are in `OPEN-QUESTIONS.md`, the trace of the old requirements in `TRACE.md`, and every design point from the design conversation in `CAPTURE.md`.
- **First build:** steps 1 to 9 are done, as `BUILD-LOG.md` records.
- **Review and manual test:** the critic review found 30 findings (`REVIEW-CODE.md`). The manual test found 25 failures in 156 checks (`MANUAL-TEST.md`).
- **Fix pass:** it was stopped partway.
  - Step 10 is committed (`4b29c5d`): intake and reporting first. That covers never-blocked submissions, feedback, reports and the saved shape, the missing, broken and cruft flags, `--debug` and `--report`, and `map roots`.
  - Step 11 is committed (`1a10261`): most of the high findings.
  - A third step was started and is **uncommitted** in the working tree. It touches `src/metaform/data/corrections.py`, `records.py`, `schema.py` and several tests. Review it, then finish it or discard it. Don't commit it unreviewed.
- **The owner's `CLAUDE.md` edit** is also uncommitted: a new instruction on how turns end. Keep it and commit it.

## The Canonical Intake

- `rich/Canonical_Intake.xml` is the schema for the map's shape. The owner changed VRE to VE throughout.
- Four typos are fixed: "of of", "traverse", "variants", and "Supportive Element".
- Four questions are open. Ask the owner, and don't decide them:
  1. Step 1 says "DET elements." Should that be NE?
  2. Should the file state again that a VE outside the AUE is an element with role VE? The schema allows role VE, and an instruction line contradicts it.
  3. "Subtype" was replaced by "Vested Entity" in step 11, in the response instruction ("nested join Vested Entitys") and in the platformer example. Should those go back to "subtype"?
  4. The nested subtype join is gone from the schema. Was that intended? Annealed parts now have nowhere to go in the output.
- **Settled:** AUE stays in the nested element's role list. The VE is at the top, and the AUE can sit beneath it in the VE's join.
- **Settled:** `map roots` starts where the intake starts, at step 1. It returns the AUE with its type groups, and the join where the DE serves the VE's purpose. Update BASE-038 and STORE-025 to match.
- Once the four questions are answered, bring the intake tools' fields (BASE-039) and the mapping in MAP-040 in line with the file.

## What to do next, in order

1. Finish the fix pass, keeping intake and the debug and report system stable first:
   - the remaining review findings;
   - the manual-test defects;
   - the quality tooling, which is strict pyright, ruff, and CI on Linux, macOS and Windows, including in the template.
2. Run the critic review against `code_quality_standards.md` again. Run the manual test of every feature again, including a real Claude run connected over MCP. Repeat until both are clean. Neither is ever skipped.
3. Build the viewer, section 9. The prototype the owner approved in direction is at https://claude.ai/artifact/99q1v9vinYyC8FzPzTXPnv. Its source is `specifications/viewer-prototype.html`.
   - **3D:** a synaptic map, joins shown uncollapsed as receiver, purpose and encounter, layers as colors, short names on the nodes.
   - **2D in the left window:** the whole map, with short names on the nodes and no text on the edges. The camera moves from node to node, which is how the selected node is shown. The long text goes in the panel below.
   - **In sync:** 2D and 3D are both ways to navigate and stay in sync. Arrow keys follow joins, and F fits the whole map.
   - **Not Codex's look:** keep only the motion and ideas from Codex's viewer on `main-wip-2026-09-24`.
4. Uninstall, pulling a wheel's data in, and origins and variants come after the viewer.

## The test artifact is Metaform itself

Run intake on this repository and use the result as the running test. The owner follows the work in the viewer.

An intake of this repository never runs inside it, and never as a subagent of the build session. A subagent inherits the build session's context: CLAUDE.md with the MetaformFoundation, which must never reach an intake, and the session's memory. Inside the repository it also reads the build's own records, the spec, the handoff, the build log, the tests and the git history, and the earlier map exports and generated map docs. On 2026-09-27 an Opus intake run that way copied an earlier intake's purpose line from the docs, reused addresses from an export, carried the build session's choice of Defining Element, and read about 290,000 tokens before it recorded its first object. Run it instead on a clean copy made with `git archive` into a folder outside /home/rich, with CLAUDE*.md and AGENTS.md removed and the exported maps, intake results and generated map docs left out, in a fresh headless process, `claude -p --model <model> --setting-sources ""`, allowed Read, Grep and Glob and the intake write path, the Metaform intake MCP tools or `Bash(metaform intake:*)`, recording into the metaform project though the copy lives elsewhere. Whether the specifications folder, apart from the Canonical Intake, belongs in the copy is the owner's call, asked on 2026-09-27. As the build proceeds, the map of Metaform, its knowledge layers, the reports and flags, and the correction stack should all show there. Run with `--debug` on during development, so process feedback and trouble reports are written. Nothing is written into the repository. All data lives under the Metaform home.

## How the owner works

- The owner decides design and vetoes.
- Every question to him carries your recommendation and the reason, and any plan you already have.
- His words carry intent. Names and switches are designed from that intent and confirmed with him, never lifted from his phrasing.
- Later decisions outrank earlier ones.
- Don't invent over gaps. Search the spec, `CAPTURE.md`, the saved branches and his own messages before calling anything new or open.
- Show him behavior, not code.
