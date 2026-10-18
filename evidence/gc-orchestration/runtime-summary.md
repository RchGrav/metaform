# Retained orchestration runtime evidence

Runtime and prompt code candidate: `8c9bf81eaa6876b5dc34766574ebb1eece2a5851`.

The initial run passed eight scenarios and exposed one test-readiness race in strict-mode PM startup. The runtime refused the extra launch while its previous capacity lease was still held. After changing only the test to wait on the public capacity ledger, the strict rerun passed. All nine distinct scenarios have passing evidence.

The exact ACP/MCP inputs, recipient prompts, cross-process events and runtime snapshots are retained losslessly in `runtime-traces.tar.gz`. `runtime-summary.json` records each archive member hash, source candidate, session/assignment relationships, prompt receipts, capacity samples, functional memory reads and actual PM recipients.

| Scenario | Recorded roles | Peak project / machine agents | Loaded sessions | Worker MCP calls | PM context turns |
|---|---|---:|---:|---:|---:|
| adaptive-change | functionality (3), gc (2), implementer (1), investigator (1) | 1 / 1 | 5 | 1 | 2 |
| communication-interruption | gc (1), implementer (1), investigator (1) | 3 / 3 | 0 | 0 | 0 |
| communication-restart | gc (1), implementer (1), investigator (1) | 3 / 3 | 1 | 0 | 0 |
| compaction-and-memory | functionality (1), gc (1) | 1 / 1 | 0 | 0 | 0 |
| gc-worker-specialist-fqc-pm | functionality (1), gc (1), implementer (1), investigator (1) | 1 / 1 | 3 | 1 | 2 |
| generated-role-creation-reuse | functionality (1), gc (1), implementer (1), role_creator (1), route_specialist (2) | 1 / 1 | 5 | 1 | 0 |
| installed-bmad-menu | bmad.bmm.dev (1), functionality (1), gc (1) | 1 / 1 | 1 | 0 | 0 |
| stop-suspended-gc | gc (1), implementer (1) | 1 / 1 | 0 | 0 | 0 |
| strict-recommendation | functionality (2), gc (1), implementer (1), investigator (1) | 1 / 1 | 4 | 1 | 2 |

The communication scenarios intentionally retain live assignments at the assertion point; cleanup stops them afterward. The user-stop scenario intentionally retains stopped assignments and unfinished root work. Delivery scenarios complete their requested root outcomes and independent assessment paths.

Machine capacity was one in delivery, role creation, reuse, assessment, PM reconnect, BMAD and compaction scenarios. Communication and owned interruption used capacity three. Every recorded capacity sample stayed within its configured limits.

These fixtures validate orchestration and context delivery through actual processes. They do not establish model decision quality or execute external BMAD scripts/tools beyond the installed fixture entry and menu.

## Retained test reports

| Report | Result | Elapsed time |
|---|---|---:|
| `integrated-runtime-initial.xml` | 8 passed; 1 strict-mode PM readiness failure | 229.69 s |
| `integrated-strict-rerun.xml` | 1 passed after the test-only readiness fix | 66.21 s |
| `memory-focused.xml` | 63 passed | 55.86 s |

The initial suite wrote `integrated-runtime.xml`; it was renamed to `integrated-runtime-initial.xml` to retain the original refusal and prevent confusion with the strict rerun. Exact commands, including candidate label, basetemp and report paths, are recorded in `runtime-summary.json`.

The focused memory gate covers canonical CRUD, notes/citations/locks and migration preservation; exact MCP body delivery versus counts or shaped-away bodies; same-identity suppression across functional indices; distinct identities; same-count revisions and deletions; concurrent revisions that remain unread; context epochs; cross-process receipt persistence; and resource notifications that filter unrelated events before reading.

All runtime, prompt and memory implementation code remained at the stated candidate. The later readiness change affects only the test's choice of when to start its PM.
