# Source register and coverage

> **Historical inventory.** [REQUIREMENTS.md](../REQUIREMENTS.md) is the complete
> governing contract. This September 16 source snapshot supplies evidence and
> context, not additional requirements. Its hashes and branch observations retain
> their original date. Active status belongs in the [remediation matrix](../REMEDIATION-MATRIX.md).

Snapshot date: **2026-09-16**. Working branch: `realignment-2026-09-10`.
HEAD: `ff6d53f5533d071612ceb574a94338efdffa3af9`.

This register records what the [combined specification](PRODUCT-SPECIFICATION.md)
is built from. Current uncommitted files are included: a HEAD-only inventory would
miss the new plugin/global-data/chassis documents and fresh implementation. The
[source manifest](source-manifest.json) records file hashes, archive-member hashes
and branch refs. It is an inventory, not a claim that every log or review artifact
was reread and accepted.

## Historical source classification

The source families below record what informed the September 16 consolidation.
Their descriptions, authority rankings, old IDs, and then-current claims are part
of that snapshot; they do not establish current product precedence.

[REQUIREMENTS.md](../REQUIREMENTS.md) now supplies the complete normative contract.
It preserves the authority of current Canonical Intake and explicitly maintained
authored workflows over their own behavior. Other retained sources help explain
meaning, inspect history, preserve data, and reproduce defects. They cannot add
requirements or turn old open decisions into a general stop condition.

Developer and agent operating instructions remain separate from product runtime
behavior. The original source files and recorded hashes remain available for
inspection; this navigation update does not revise their authored content.

## Source families

Paths below are relative to this directory. Section references in the combined
specification identify the relevant part of a family. S01 records conversation
content available in this thread; it has no fabricated repository transcript.

| Key | Sources and authority | Main coverage |
| --- | --- | --- |
| **S01** | Supplied conversation; short exact anchors in [decision ledger](DECISIONS-AND-CONFLICTS.md). Explicit user corrections outrank prior assistant suggestions. | Product direction; fresh chassis; global placement; layers; nonce/header; Python modules; three demos; TUI/glue; disabled file; complete CLI. |
| **S02** | [docs/SPEC.md](../../docs/SPEC.md), capabilities, semantic contract §§1–15 and acceptance scenarios. Detailed contract with internal historical conflicts. | P, SEM, OBJ, INT, KG, WF, UX, DATA, WEB, DIST. |
| **S03** | [Primer index](../../docs/primer/README.md), [full explanation](../../docs/primer/01_full_explanation.md), [introduction](../../docs/primer/02_specification_introduction.md), [technical account](../../docs/primer/03_technical_account.md), [inference Metaform documentation](../../docs/primer/inference_metaform_documentation.md). Rationale and history; old dual-graph/empirical claims remain attributed. | Purpose, Type identity, inference amortization, historical source comparisons. |
| **S04** | [Semantic index](../../docs/semantics/README.md), [functional typology](../../docs/semantics/functional_typology.md), [inference rules](../../docs/semantics/inference_metaform_rules.md), [names/receivers/variants](../../docs/semantics/names-receivers-and-variants.md), [artifacts and intake](../../docs/semantics/artifacts-and-functional-intake.md), [equation reuse](../../docs/semantics/semantic_equation_reuse_rule.md), [understanding/work](../../docs/semantics/understanding-and-work.md); [Name rule](../../docs/rulebook/element/name.md), [Description rule](../../docs/rulebook/element/description.md). Older conflicting statements remain identifiable. | SEM, OBJ, INT, KG, DATA; exact operative wording. |
| **S05** | [Current intake XML](../intake.xml), [RE schema](../re.schema.json), [related digital typology XML](../digital-typolo.xml). User-authored source shape; no automatic harmonization of differing copies. | Intake procedure, fields, combining/subtypes, response instructions; C01–C06. |
| **S06** | [Plugin system](../plugin-system.md). Records the later product direction and separates proposals. | CH, UX, AG, KG, WF, DATA, WEB, DIST. |
| **S07** | [Chassis product](../chassis-product.md), [September 16 plan](../../docs/superpowers/plans/2026-09-16-chassis-product.md). Current scope plus implementation plan; not whole-product completion. | CH, UX, AG, DEMO. |
| **S08** | [Public module API](../../docs/plugin-api.md), [chassis verification](../../docs/chassis-verification.md), [showcase](../../examples/modules/showcase/README.md), [event requester](../../examples/modules/event_requester/README.md), [harness runner](../../modules/harness_runner/README.md). Current implementation/evidence. | Exact service/hook signatures, job semantics, CLI/TUI commands, demo proof. |
| **S09** | [Generated specs Metaform](../metaform-specs-20260915-7c8f4d21.xml), [best-practices layer](../metaform-chassis-best-practices.xml); [Codex sample Metaform](../sample/metaform.dt-codex-20260915-8d3f2c1a.xml), [Codex knowledge sample](../sample/metaform.kl-codex-developer-best-practices-20260915.xml). Guidance/examples; basis explicitly limits original coverage. | Functional map, attached layer examples, combined entities, attributed source-hiding clarification. |
| **S10** | [Global data pattern](../global-data.md), [original data-folder account](../data_folder.md). Global adaptation plus successive historical proposals/corrections. | DATA-01–10; origin IDs, variants, preserving import, Python reconstruction. |
| **S11** | [Next version](../../docs/next-version.md), [workflows](../../docs/workflows.md), [knowledge/revisions](../../docs/knowledge-and-revisions.md), [CLI/harnesses](../../docs/cli-and-harnesses.md), [discussion handoff](../../docs/discussion-handoff.md), [repair specification](../../docs/repair-spec.md), [backlog](../../docs/repair-backlog.md), [repair list](../../docs/metaform-repair-list.md). Mixed requirements and implementation history. | Workflow interaction/continuity, memories, onboarding, artifact fidelity, image capability, community library; superseded mechanisms flagged. |
| **S12** | [Native variants specification](../../feature-briefs/native-metaform-variants-specification.md), [its plan](../../feature-briefs/native-metaform-variants-implementation-plan.md); [shared knowledge/portable specification](../../feature-briefs/shared-knowledge-service-and-portable-projects-specification.md), [brief](../../feature-briefs/shared-knowledge-service-and-portable-projects.md), [plan](../../feature-briefs/shared-knowledge-service-and-portable-projects-implementation-plan.md). Specifications distinct from proposed storage mechanics. | DATA-09; selected-project closure, source preservation, offline continuation/re-export. |
| **S13** | [Workbench brief](../../docs/workbench-brief.md), [navigation](../../docs/workbench-navigation.md), [cleanup](../../docs/workbench-cleanup.md), [calls](../../docs/workbench-calls.md). User experience requirements versus historical presentation/performance details. | WEB, prompt authoring/replay, actual agent-visible context, real intake acceptance. |
| **S14** | [XML experiments index](../xml/README.md) and XML files in that folder: shallow, deep, expansion, nested/alternate intake, artifact and prompt-generator orchestration. Sample alternatives, not one implicitly selected schema. | WF-02; INT-03; C09. |
| **S15** | [September 15 design handoff](../../docs/handoff/2026-09-15-design-recovery.md), [chassis recovery plan](../../docs/superpowers/plans/2026-09-15-chassis-plugin-recovery.md), [semantic recovery plan](../../docs/superpowers/plans/2026-09-10-semantic-delivery-recovery.md), [native/latent plan](../../docs/superpowers/plans/2026-09-10-native-latent-intake.md), [navigation plan](../../docs/superpowers/plans/2026-09-10-actual-elements-navigation.md), [release repair plan](../../docs/superpowers/plans/2026-09-11-release-quality-repairs.md), [older plan](../../docs/plan.md). Explicit quotations distinct from tentative architecture/task lists. | Fresh architecture correction, XML/context objects, semantic delivery, earlier recovery commitments. |
| **S16** | [Prompt corpus](../../prompts/README.md), [workflow conversion evidence](../../docs/reviews/workflow-conversion/README.md), [release status](../../docs/release-quality-status.md), [current work](../../docs/current-work.md), related reviews and the old handoff set under `docs/handoff/`. Historical evidence with scenario limitations. | Seven-source library; verification versus outstanding migration; previous semantic failures and corrected status. |
| **S17** | Repository-root [realignment archive](../../metaform-realignment-2026-09-10.zip), [metaform.zip](../../metaform.zip), [metaform_2.zip](../../metaform_2.zip), [out.md](../../out.md), and compared Git refs below. Archive members retained in the manifest. | Branch recovery, historical proposed schemas/GUI/access model, source completeness check. |
| **S18** | User-supplied external references listed below. Technical examples and usability inspiration; not blanket product requirements. | Click/plugin guidance, CLI ergonomics, pattern vocabulary, MCP historical discussion. |

## Branch comparison

Remote heads were refreshed and compared read-only. `git ls-remote --heads origin`
advertised main, realignment and review; the codex refs below remain local tracking
refs but are no longer advertised upstream. Counts are commits unique to current
HEAD / commits unique to the listed ref, from `git rev-list --left-right --count`.

| Ref | Commit | Current / ref | Finding |
| --- | --- | --- | --- |
| `main`, `origin/main` | `b7aea90` | 90 / 0 | Entire committed branch is in current ancestry. |
| `repair/release-quality` | `d264f51` | 89 / 0 | Entire committed branch is in current ancestry; dirty worktree checked separately. |
| `origin/codex/metaform-chassis` | `8efbd25` | 134 / 0 | Retained tracking ref; already in current ancestry. |
| `origin/codex/workbench-cleanup` | `aabe629` | 132 / 0 | Retained tracking ref; already in current ancestry. |
| `origin/codex/element-rulebook` | `5e9acea` | 130 / 0 | Retained tracking ref; separate Name/Description sources preserved. |
| `origin/realignment-2026-09-10` | `59c00e0` | 32 / 0 | Remote is behind current local HEAD. |
| `origin/review/metaform-realignment-2026-09-10` | `69eed8b` | 91 / 5 | Divergent review/evidence package; substantive files already in current archive. |

The review branch's `.realignment-package/` has 60 files. All 60 exist inside the
tracked ZIP; 57 match byte-for-byte. The remaining differences are phrasing about
prompt-output/authorization separation, schema extensibility, and one corrected
Name-rule source-link hash. No missing product requirement was found in those
differences. The review package describes a baseline review and proposed rewrite,
not a completed implementation. Its proposed standalone joins, manifest model,
Flask retention and event-bus prohibition cannot override later decisions.

The dirty `.worktrees/release-quality/docs/` comparison found 307 identical files,
15 differing and none missing from current `docs/`. Historical repair work was
checkpointed at `3d3543b`; current docs subsequently revise enumeration, retire
Ladybug/Cypher and withdraw earlier semantic acceptance claims. No ahead product
source was found only in that worktree. File timestamps or uncommitted status alone
do not make those older copies current requirements.

Reproduce the comparison without changing branches:

```sh
git rev-list --left-right --count HEAD...repair/release-quality
git log --oneline HEAD..origin/review/metaform-realignment-2026-09-10
git ls-tree -r --name-only REF -- docs specifications specs feature-briefs
git show REF:path/to/document.md
git -C .worktrees/release-quality status --short
```

## Archive and generated-source findings

`metaform_2.zip` has 140 documentation Markdown members in the audited scope:
136 match current files exactly, two indexes differ, and two intake Markdown
drafts are absent because they were deliberately removed. Their coarse/annealing/
subtype content is represented by current XML and SPEC. `metaform.zip` retains 46
documentation paths, all present now; 21 differing files are older versions.
`out.md` bundles 33 historical documents, including the superseded rule withholding
Native joins/OPs from Latent. Do not promote that old wording into the new PRD.
`pongclock.zip` is an artifact fixture, not an additional product specification.

The supplied specs Metaform contains **9 Elements and 16 joins**. Its engineering
layer contains **94 directives** and says some linked sources were absent from the
original material. It is not a comprehensive substitute for those sources. The
separate Codex sample contains **9 Elements, 14 joins and 16 combined entities**;
that is a different example. `digital-typolo.xml` lacks portions present in the
current `intake.xml`; it must not silently replace it.

Archive clarifications on readable graph text and focused role-specific prompt
context are retained in the combined document with source attribution. Proposed
semantic search/neighborhood/grounding APIs, graph layouts and schema envelopes
remain review candidates, rather than silently adopted requirements.

## External references supplied in the conversation

These are retained for provenance of the design discussion. This consolidation
does not convert their sample code, standards claims or every recommendation into
Metaform requirements, and does not claim a fresh standards/version audit.

- [Click complex example](https://github.com/pallets/click/blob/main/examples/complex/README)
  and [complex application guidance](https://click.palletsprojects.com/en/stable/complex/).
- [Python plugin-system article](https://oneuptime.com/blog/post/2026-01-30-python-plugin-systems/view).
- [Agent CLI Guide](https://github.com/Johnixr/agent-cli-guide/blob/main/README.md).
- [Python patterns catalog](https://github.com/faif/python-patterns).
- Historical MCP identity discussion: [Kotlin InitializeRequest](https://kotlin.sdk.modelcontextprotocol.io/kotlin-sdk-core/io.modelcontextprotocol.kotlin.sdk.types/-initialize-request/index.html),
  [server-session SDK page](https://py.sdk.modelcontextprotocol.io/api/mcp/server/session/),
  and [user-supplied explanatory article](https://babulal.com.np/blogs/mcp-server-in-depth.html).

A specific memory MCP example was discussed without a uniquely identified source
URL. Preserve the requested memory behavior; do not invent which server/version
was meant. The user-authorized terminal reference was `~/ccl-min/c3lab`'s
`mvm config`/set/unset/glue behavior; no unrelated repository context was imported
in this consolidation.

## Coverage and limits

The semantic, feature/workflow, branch and archive audits were read-only. Detailed
requirements were extracted from the source families above and independently
checked against the combined draft. Logs, screenshots, generated answers, shipped
runtime prompts and code are inventoried where relevant, but their presence does
not make their contents requirements. Implementation status relies on the cited
verification reports; runtime tests were not rerun for this documentation task.

This is a comprehensive recovered review draft, not a guarantee that an unstated
idea or unavailable conversation has been recovered. Every known substantive
source conflict is carried into the decision ledger. The source manifest makes the
snapshot checkable without pretending the current dirty workspace is a commit.
