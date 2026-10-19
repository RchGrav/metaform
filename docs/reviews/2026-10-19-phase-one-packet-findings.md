# Phase-one packet findings

Examined 2026-10-19 against checkout `8d479f2`. This report separates exported state, current source, and behavior still requiring a live reproduction. The accompanying [recovery plan](../plans/phase-one-autonomy-and-knowledge-recovery.md) turns these findings into bounded implementation work.

## Import and integrity

The four uploaded parts were joined in numeric order. The gzip-compressed tar contains one project ZIP. The gzip stream and ZIP member checks completed successfully. The ZIP contains a manifest and the project exchange document; it contains no project source files.

- Archive timestamp: `2026-10-19T03:26:14Z`.
- Export version: `2026.9.30.2`; storage schema and compatibility: 22.
- Project: `metaform` only. The Flask project is absent.
- Native command: `metaform import /workspace/.onboarding/packet-review/metaform-20261019T032622Z.zip metaform`.
- Diagnostic home: `/workspace/.onboarding/packet-review/home`; registered project directory: `/workspace/.onboarding/packet-review/project`.
- Import result: three bases, 28 layer additions, 95,786 things added, none skipped. These are importer counts, not counts of current map elements or runnable tickets.
- Re-export through `metaform.data.exchange.export_document` matched all three imported base documents and all project module exports exactly. The diagnostic registration keeps its local path and initially selected `main`; all active-base findings below explicitly read the packet's original active base by ID.
- No imported agents or automation were started, and no tickets were filed or changed during this study.

The native importer initially rejected `prior_schema_version: "21"`, although the current exporter legitimately carries that history in a schema-22 document. The only application change made for this task adds 21 to the historical-version validation list in `src/metaform/data/exchange.py`. A regression test failed before that change and passed afterward; all 13 exchange tests, Ruff on both changed files, and Pyright on the changed source file passed. This is an import fix, not an autonomy fix.

The assembled tar's SHA-256 is `689bd2e05fa11a1c813fbad304f752c0055301aa895a760893cb5b413b2e4ce0`.

## What the board contains

The original active base is `feature-code-alignment-20261013`, ID `f30ba9e989c04040a832c8562a7c80f3`. Public Store reads return 441 work records. Applying the product's `is_work` predicate distinguishes 407 tickets from 34 condition/status records.

| Column | Tickets |
|---|---:|
| Backlog | 11 |
| To do | 42 |
| Doing | 14 |
| Done | 340 |

There are **67 open tickets**. Of the 340 done tickets, 323 record completion and 17 cancellation. These counts are the packet's state, not the earlier screenshot's counts or a current live measurement. Server-level board retention and line-in-the-sand settings are not in this project export.

All 14 Doing tickets still have an owner/taken marker whose session is recorded as ended:

| Recorded reason | Doing tickets |
|---|---:|
| Runner terminated | 7 |
| Stopped by the person | 5 |
| Runner no longer running | 1 |
| Orchestration suspended | 1 |

The export contains 354 project dispatch sessions, all recorded as ended. This does not establish the state of processes on the user's machine now. It does establish that the exported board's Doing column is not a reliable statement that work is executing. Recovery must distinguish an unexpected loss from an intentional user stop; automatically restarting all 14 would violate user control.

**Twelve of the 42 To do tickets have a separate `map.ticket_settings.hold = 1`**, even though their work-record `held` flag is false. Those tickets can look ready while dispatch still holds them. The export does not establish who set every hold or what the global effective policy was; those holds must be reconciled individually, not cleared indiscriminately.

Only one open ticket satisfying `is_work` has an empty task field: `f7ae5992…`, a trouble marker whose note actually contains investigation and verification instructions. Another taskless record is an unbuilt condition, not a ticket. Thus this snapshot does not support a general conclusion that all open cards lack instructions. It does support a need for consistent actionable presentation and claimability.

## Review-generated expansion is measurable

The active base contains 146 orchestration assignments created between `2026-10-18T14:26:07Z` and `2026-10-19T00:59:06Z`:

- 73 use `metaform://role/gc`.
- 73 use `metaform://role/functionality`.
- All have execution role `worker` and mode `adaptive`.
- 68 GC assignments have a parent assignment.
- 73 tickets contain a structured `reviewed_work` payload; two remain open.

The correction tree rooted at ticket `5decae95491d4e928076d200000dad5a` has **46 GC assignments**. One ancestry path has eight assignments, seven parent-child steps:

| UTC on October 18 | Ticket prefix | Task subject |
|---|---|---|
| 14:26:07 | `5decae95` | Rotate the map around the selected node |
| 14:53:33 | `f27acfca` | Camera position inside large followed figures |
| 15:08:45 | `3b37031f` | Per-frame allocation in the clearance correction |
| 15:29:29 | `7ccb85ce` | Eased clearance still entering a figure |
| 16:18:33 | `68ad6580` | Clearance while flying to a watched figure |
| 16:46:40 | `8a5dd2d9` | Clearance when agent size is unlimited |
| 17:07:47 | `6c77b9be` | Correcting the report's claim about memory-tool availability |
| 17:31:51 | `dd87d814` | Naming sessions still running old code |

These are assignment creation times. The original ticket was marked done at 14:49:50, before most of this chain. The lineage proves repeated creation of follow-on coordination work and widening subject matter; it does not prove every individual finding was invalid or a duplicate. The remedy is direct workers, bounded assessment on the same candidate/ticket, and explicit handling of distinct issues. Merely hiding completed cards would leave this mechanism intact.

The conversation record also contains the advisor reporting that it could not stop the growing clearance chain (`627d03a9…`, message sequence 1045). That is recorded historical testimony, not a fresh cancellation test. Current source separately confirms the subsequent blanket stop-consent bypass.

## Roles and the fault-to-repair gap

The agents export has zero generated definitions, zero definition-history rows, and three registered role sources: `gc`, `functionality`, and `triage`. Orchestration has zero role requests. There are 5,514 component delivery receipts and 1,674 sent-prompt records, so prompt delivery machinery was in use; a specialist library was not populated in these project records. The current source already provides versioned role publication, Metaform role URIs and resource-read receipts. The plan should connect that machinery to ticket intake and worker admission.

Autoticket exports one fault group and zero registered logs, rules or state rows. The single captured group came through MCP, not a watched log file:

- First and last observation: `2026-10-19T00:21:14Z`, one occurrence.
- Error: `FileNotFoundError` while `orchestration_change` attempted to read a specification path ending in `/None`.
- Ticket: `cf26d1e5333e4911baea2db0a2944503`, still open and untaken at export.
- No per-ticket dispatch hold, dependency row, orchestration assignment or dispatch session for this ticket appears in the packet.
- Its task explicitly says to find and fix the cause, contains the failing call and stack, and asks for a check proving the repair. Its final paragraph also broadly sends design choices or data removal to the person.

This is a concrete example of **capture succeeding while repair never starts**. It remained unclaimed for about three hours before export. The exact admission blocker cannot be reconstructed from this project packet alone: effective home/folder settings, the launch ledger at that time, runtime scheduling decisions and live processes are absent. The system must record that decision and show its reason on the ticket. A blank reason should itself be a reconciliation failure.

Zero log registrations establish that this project's exported watcher configuration was empty. They do not prove no external logger or other project's watcher existed. Onboarding must register and test relevant sources, while the supervisor owns their lifecycle.

## Knowledge and intake limits

Public reads show 12 current layers across the three bases; the import's 28 additions include historical layers. The active base currently has `base`, `sources`, `feature-audit-20261013`, `memory`, and `agents`. Its sources layer has 488 items; its audit layer has 17 items and five properties. A zero item count is not sufficient evidence that a layer is useless: a base contains elements/joins, and a module can keep records in its own tables.

There is no current checked layer in these Metaform bases. This packet therefore cannot reproduce the reported Flask clutter. Current source nevertheless creates `checked`/`ok` assessment items in intake and sends non-base layer items to the viewer. That is a source-grounded mechanism to exercise in a controlled Flask intake.

The attached screenplay document was read as a semantic example: 29 elements, 28 purpose records and three BKN observations in its local proof. Its director/screenwriter, screenplay, scenes, headings and dialogue demonstrate why intake must be based on functional relations rather than software-specific directory categories. The document itself says its proof was local, not MCP persistence. No embedded correction instructions were executed.

The user's platformer/C++/Bash examples supply the required CEL tests: purposeful layer identity; attachment scope; applicable instruction content flowing toward leaves; adjacent branches excluded; removable selection and masks; local evidence remaining local. Existing property propagation alone does not prove useful instruction delivery.

## Source findings that constrain implementation

| Source | Finding and implication |
|---|---|
| `dispatch/__init__.py`, `STOP_CONSENT`, `may_stop` | The bypass treats stop calls as the person's. Restore authenticated/delegated actor handling while preserving the user's ability to stop their agents. |
| `dispatch/__init__.py`, `slots` | Project capacity counts workers plus summoned agents; global capacity counts all entries. Existing project/global settings should become worker limits. |
| `dispatch/runner.py`, `turn`, `message`, `interrupt` | Human messages can move ahead of queued work; that alone does not interrupt a long active turn. Test ordering and active-turn behavior per adapter. |
| `orchestration/state.py`, `ensure`, `_correction` | Root and correction assignments still use GC ownership. Retire the execution path and migrate its state, not just its role label. |
| `autoticket/faults.py`, `tell`, `held_why` | A recurring fault can lose its link to a completed ticket; error-word heuristics and feedback type impose holds. Reopen canonical issues and decide authority from the proposed action and effective policy. |
| `web/page/app/loading/load.js`, `progressOf` | Every map load still reads all work to compute progress. Existing board archive/retention does not remove this load. |
| `web/page/app/live/stream.js`, `heardProjects`; `workspace/workspace.js` | Global opened-project events can navigate existing tabs, and server selection can override restoration. Give each tab explicit project/base context. |
| `home.py`, `staying_agents`; dispatch base pinning | Current mechanisms intend workers to remain on their original base. The actual project-switch process-termination cause still requires reproduction; clearing displayed sessions is not proof of termination. |
| `dispatch/peering.py` | Session discovery is project-local. Cross-project communication needs explicit destination routing and stable identity. |
| `intake/__init__.py`, `_checked`; `data/reads.py`, `context` | Assessment markers and knowledge applicability are different concerns. Correct both storage/presentation and worker-context semantics. |

## Validation and remaining evidence

- Import/exchange suite: 13 passed; importer regression observed failing before the fix. Changed-file lint/type checks passed.
- Layer and authored-role suites: 34 passed, two failed. All eight authored-role tests passed. Both layer failures stop at a fixture using the now-reserved layer name `media`; their later inheritance assertions were not exercised.
- Three focused autoticket tests passed: immediate filing of a new fault, grouping repeated occurrences, and zero reads for irrelevant event bursts.
- Baseline cloud setup and its separate failures are recorded in `/workspace/.onboarding/validation/REPORT.md`. A broad earlier run was interrupted after 150 passes and 37 failures; it is not a suite pass. Global Pyright reported 21 errors.
- No live browser/ACP cancellation, cross-project switch, Flask intake or end-to-end autonomous repair was validated in this study.

The packet provides enough evidence to prioritize implementation. Later reproductions need the original effective settings and runtime identities, and either a Flask packet or a fresh controlled intake. Missing evidence should narrow claims, not hold up the confirmed control, scheduling and orchestration repairs.

Diagnostic artifacts are under `/workspace/.onboarding/packet-review`: `inventory.json`, `import-readback.json`, `import.log`, and sanitized work/module extracts. Raw transcripts and database copies remain there rather than being copied into repository documentation.
