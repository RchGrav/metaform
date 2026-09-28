# Metaform global data pattern

Date: 2026-09-15

## Basis and scope

This is the initial all-global storage pattern for the [chassis and plugin system](plugin-system.md). It adapts [specs/data_folder.md](../specs/data_folder.md), as requested by Rich, to the subsequent decision to begin with one user-folder data root and one database. The source document remains a historical account containing successive proposals, observations, and Rich's later corrections. This document carries forward its identity, provenance, history, and reconstruction structure with current storage placement.

All Metaform records, provenance, assignments, and edit copies initially live under the global user folder. Source repositories and source folders remain at their existing locations. Each project retains its ownership within the global store. One global web instance serves the tracked projects on one configured port. Physical repository-local storage can evolve later.

## 1. One index and one authoritative database

The global database answers which projects are known, where their sources are, and what work belongs to an operating folder. This restores the resume function described under `sessions.json` in the source account through the chassis data service.

| Responsibility | Information retained |
| --- | --- |
| Projects | Project identity, source locations, repository/folder kind, known origins, and selected origin |
| Operating folders | Operating path, selected project/origin, assignment binding, and recorded working position |
| Origins | Full source identity, commit or content baseline, content manifest, lineage identity, and project ownership |
| Variants | Origin reference, collected changes, artifact references, producing operation/run/prompt revision, and provenance |
| Assignments | Nonce, workflow/module and step, workfolder, prompt bindings, selected context/layers, submissions, and lifecycle |
| Knowledge | Namespace records with RE-owned joins, layers, memories, revisions, and provenance references |
| Modules and settings | Loaded-module management state, contributed settings, and configuration for the global instance |

These are responsibilities to map into the schema, not a requirement for one table per row. Payload files may live under the data root with references from the database. The chassis services provide data access to every module.

The workfolder's `.agentid/nonce` remains a small discovery marker referring to the globally stored assignment. CLI help and reads use the recorded context. Assignment completion retains work history while clearing the active binding according to the agreed lifecycle.

## 2. Proposed physical layout

This layout gives the existing history pattern a global home. Directory names and the database filename below are implementation proposals; the one-root/one-database ownership is settled.

```text
~/.metaform/
├── metaform.sqlite3                 authoritative records, indexes, settings
├── modules/                        external module packages and assets
├── origins/
│   └── <origin-instance>/
│       ├── origin/                 retained non-repository baseline
│       └── versions/
│           └── <variant-id>/
│               ├── text.patch      text diff representation when used
│               └── files/          retained text and changed binary payloads
├── workfolders/                    working copies tracked by assignments
└── runtime/                        active process/endpoint information
```

`<origin-instance>` represents a stored lineage instance associated with its full source identity. The identity-to-path mapping must preserve the forms below when reconciling existing stores. Export manifests are serialized views of the records and their payloads. Live project, assignment, and knowledge ownership is recorded in the single database.

## 3. Origin identity and re-anchoring

A repository baseline is identified by its selected commit; a non-repository baseline is identified by a content-manifest hash. The full source identity is retained alongside the manifest digest and the Metaform lineage identifiers.

The later identity form recorded in the source document is:

- `mform_sha_id`: the 240 most significant bits of the origin digest followed by a 16-bit suffix, 64 hexadecimal characters.
- `mform_id`: the 48 most significant bits of that digest followed by the same 16-bit suffix, 16 hexadecimal characters.

Both forms have no underscore. The full original digest remains recorded. The suffix distinguishes provenance-bearing lineage instances. The repository commit identity and the digest used for these derived names remain explicit fields; the current code already records both a `base_commit` and `origin_sha256`.

Selecting a new origin creates a new history unit. Previous origins and their variants remain accessible. A different source commit establishes a different origin; incrementing the lineage suffix is a separate operation.

For repository work, retain the selected commit as the baseline reference and extract its contents for export. For non-repository work, retain a baseline copy under the global origin unit. This follows Rich's later history-layout description. Moving Metaform state globally leaves that source distinction intact.

## 4. Variants and reconstruction

Collected workfolders become retained variants under their selected origin, with the operation, run, and prompt revision that produced them. Mutation experiments can retain many variants from one baseline.

For the common-origin mutation case, every variant describes changes against that origin. A separately selected new origin begins another history unit. Scheduling sibling operations sequentially does not change their baseline.

Text changes are represented using Python-generated diffs against the origin, and changed binaries are retained whole. The later small-artifact refinement says text under 3 MB may be kept intact. The source account interprets this as retaining changed text files whole below that threshold and using a text diff above it; finalize the threshold calculation in the storage implementation examples. Unchanged content is recovered from the origin.

Reconstruction applies the recorded changes to the selected origin and restores the represented artifact, including additions and removals. The recorded file manifest supplies reconstruction checks. An exported artifact carries the baseline contents and changes needed for reconstruction using Python in the receiving environment.

The provenance path is concrete: variant → producing operation/run → prompt revision and issued bindings → received answer and referenced inputs. An origin or variant directory alone is not the provenance model; the chassis records those relationships.

## 5. Import and workflow delivery

Retain the source account's preservation behavior: if importing into an existing lineage would lose local data or provenance, allocate another suffix and keep both instances accessible. The operation returns the resulting identity and location. This history-preservation rule belongs in the shared data/provenance services used by the importing module.

The origin history unit is the export unit: its baseline and associated variants, plus their retained records and provenance. The workflow module owns preparing the uploadable workflow and its CLI execution through the wheel entrypoint. It uses chassis data and packaging services to include the required history and reconstruct a selected variant, several variants, or the entire exported set into external folders.

The global Metaform web interface continues to use one instance and one port. The source account's separate discussion of serving reconstructed web artifacts concerns those artifacts' execution; it does not change the global Metaform endpoint.

## 6. Initial recovery checks

- Track two repositories and one non-repository source in the single global database, preserving separate project ownership and source paths.
- Resume the selected project and assignment from a working folder across separate CLI invocations.
- Record two origins for one project and retrieve both without altering the first history unit.
- Collect multiple variants against one origin and follow each to its producing prompt and answer.
- Reconstruct text changes, a binary replacement, an added file, and a removed file from the retained origin and variant representation.
- Exercise retained whole-text and text-diff representations against the same reconstruction contract.
- Import divergent history and retrieve both preserved lineage instances.
- Prepare the exported history through the workflow module and reconstruct it from the actual wheel entrypoint in a supported Python environment.

## 7. Current implementation evidence

This document specifies recovery work; it does not describe a completed migration. The inspected `src/metaform/history.py` still initializes one manifest with an extracted origin copy, writes the older `mform_sha_id` form, and uses checkpoint-parent relationships for history reads. `src/metaform/workfolders.py` contains existing creation, diff, and apply machinery to examine when implementing retained variant collection.

Task 1 of the [recovery plan](../docs/superpowers/plans/2026-09-15-chassis-plugin-recovery.md) maps those records into the proposed global structure. The data and provenance services establish the new path; migration and executable-wheel checks complete its delivery. Existing source records remain available while that mapping is developed.
