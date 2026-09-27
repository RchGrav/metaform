# Source edition and validation

[Documentation](README.md) | [System introduction](../README.md) | [Preprint](preprint/inference-metaform.md)

This file records the documentation edition of **September 26, 2026**: the source it was written against and the checks made on it. That edition explained the author's independently developed Inference Metaform and the implementation of that day, using the project's own recorded map as its principal worked example. The documentation has since been revised to follow the code; [Since this edition](#since-this-edition) says what changed and what was checked for the revision. The identity table and the checks below belong to the September 26 edition and describe the source of that day, not the current branch.

## Repository placement

The edition was delivered as a documentation overlay. Its root `README.md` belonged at the repository root, and its `docs/` directory kept the paths used by the links. The package held the user documentation, preprint, technical-reference set, and example export. It did not include or replace the runtime, tests, packaging configuration, or operative prompts.

Links between delivered documents worked within the extracted layout. Source links, such as `../../src/metaform/module.py` from a guide, resolve after placement in the repository.

## Source identity of the September 26 edition

| Field | Supplied value |
|---|---|
| Branch | `chassis` |
| Commit attribution | `ce9062bdec9398ca1f23ac60684bd3cc7e37f23c` |
| Package version | `0.1.0` |
| Python requirement | `>=3.11` |
| Project Metaform | `main` |
| Metaform ID | `6a339171fe6f44c49a40f4a270d98913` |
| Intake layer ID | `2f6b86ffc49c4575bfdbf0ad2ac712f7` |
| Intake layer name | `intake-20260926T192840Z-f04016` |
| Recorded intake time | `2026-09-26T19:28:40Z` |
| Recorded result ID | `metaform-intake-20260926-a823b992` |

The branch and commit were the bundle's attribution in `BUNDLE_INDEX.txt`. The supplied source had no `.git` directory, and the edition did not substitute a later fetched branch. Package requirements are declared in [pyproject.toml](../pyproject.toml).

On that day the live [Canonical Intake resource](../src/metaform/modules/intake/resources/Canonical_Intake.xml) was byte-identical to [its specification copy](../specifications/Canonical_Intake.xml), with SHA-256:

```text
7e2140a9dd71c875689604772c07e5f0c1dd6366b55ba03a530211867eb909f8
```

The [project-metaform.json](examples/project-metaform.json) delivered with the edition was an unchanged copy of the supplied project export, with SHA-256:

```text
213fc23c4e25078ce070c6148e957ec3eca18a0fd9e759902e3e3400fb887bc5
```

The export retains the original project path as recorded data.

## Evidence used by the documents

**The design account** comes from the author's explanations and corrections. **Present operations** come from the operative source, resources, schemas, and tests. **Recorded project material** comes from the supplied map and associated records. **Derived illustrations** show uses of those mechanisms without presenting them as original agent runs. The earlier explanatory README, preprint, and generated drafts were not used as the basis for the public account.

Research citations in the [preprint](preprint/inference-metaform.md#14-connections-to-other-work) were checked against the cited primary-source records. They locate subsequent conceptual connections; the author's independent development history is not derived from them.

## Documentation checks of the September 26 edition

The operational check used the supplied Python source with a separate `METAFORM_HOME` and temporary workpiece folders. It comprised **48 CLI invocations**, including an expected unreadable-submission notice. The [exercise record](examples/CLI-EXERCISE.md) describes inputs, results, and scope.

The exercise covered project registration and import, provider and subtype reads, element- and join-addressed memory, memory relations, knowledge layers and properties, prefix selection and masking, hiding and restoring a layer, correction history and peeling, the bundled demo module, and the extension guide's example module. It also submitted the supplied kitchen-timer fixture's element array, repeated intake into a new Metaform, and exercised export/reimport behavior.

These were local checks of the documented operations, not model-performance measurements. The exercise did not run an AI model, build or install a wheel, alter an agent client's configuration, start a live MCP server, operate the GUI, or execute the full test suite. Those other instructions and interface descriptions were checked against the supplied source. The exercise environment did not have the MCP SDK; module discovery reported that dependency directly.

Repository-relative links and document anchors were checked against both the delivered tree and the supplied source layout. The preprint was typeset from its Markdown manuscript, rendered for page-by-page layout review, and checked for text overflow and missing glyphs.

A before/after SHA-256 comparison found no changes in the **131 supplied source files**. The runtime and operative prompts were unchanged by the documentation work.

## Continuity of the technical reference

[REFERENCE.md](inference-metaform/REFERENCE.md), [IMPLEMENTATION_MAP.md](inference-metaform/IMPLEMENTATION_MAP.md), and [EXAMPLES_TO_COLLECT.md](inference-metaform/EXAMPLES_TO_COLLECT.md) carry the substance of the completed technical-reference edition. A later presentation pass on September 26 converted their ASCII structure drawings into rendered Mermaid diagrams, corrected `above`/`below` wording that misdescribed the namespace's trunk-to-leaves direction, and corrected the note about the select test's title now that the test is named `test_a_select_toward_the_leaves_from_a_mask_turns_the_layer_on_again_there_and_nowhere_toward_the_trunk`; no technical claim changed in that pass.

[IDEAS.md](inference-metaform/IDEAS.md) retains its eight tooling proposals. Its documentation-status section links to the completed public materials instead of treating those delivered pages as future proposals. The separation between established mechanisms, completed documentation, and proposed additional tooling remains explicit.

<a id="since-this-edition"></a>
## Since this edition

The same evening the presentation pass recorded `verb` as null on each join and subtype row of the example export, since that intake was made before `verb` existed, and replaced ASCII drawings with Mermaid. The example export's SHA-256 is now:

```text
f46c9f4865f2dace87eff692efdc2b91729efd82a002373dd13774e83dcc2c1f
```

Build steps 41 to 56 of the [build log](../specifications/spec/BUILD-LOG.md) then changed what Metaform stores and does. An element is its address, `name_length` and role, and the project's name for a functionality is on the join. The condition of an element or a join is a work record, `tbd`, `broken` or `cruft`, kept apart from the map. A subtype is a join of type `subtype` inside its parent join. Joins move and elements never do. The intake gained `intake_absorb` and `intake_show receiver=`; `map where` reads what relies on an address and what it relies on; `clear project` clears a project on the command line, over MCP and on the page; the tools never refuse content; and the web module no longer polls. The store's schema version went from 1 to 5, so the example export, at version 1, no longer imports. Steps 57, 59, 60, 61 and 62 followed: the page's own writes announce `map.changed` as a command's do, the MCP server's chassis tools read a call as module verbs do, each kind of database keeps its own schema version, the metaform store's 5 and the base, history and prompt databases' 1, ruff's safe fixes were applied, and going inside a node zooms in as the map fades.

Step 58 brought the documentation to the code on the `chassis` branch after step 62, commit `2e6f581`. The root README, the guides, the technical reference set, the module READMEs and changelogs, and the specifications index were revised; the guides' examples moved from importing the example export to a kitchen timer's map recorded by hand, and the screenshot was retaken from the current web GUI. The preprint and [CLI-EXERCISE.md](examples/CLI-EXERCISE.md) still describe September 26, and say so.

On that branch the served Canonical Intake is still byte-identical to its specification copy, and its SHA-256 is:

```text
9554f5b82674fb0ce2fb61381022d49cd9c45071401c5f8c433770e27f3feab6
```

The package version is still `0.1.0`, and the Python requirement `>=3.11`. The checks for step 58 are recorded in its build log entry.

## Citation

Use the [preprint citation](preprint/CITATION.md) for this edition and [references.bib](preprint/references.bib) for the accompanying bibliographic records. The author is credited as **Rich**, independent developer. No DOI or license has been assigned by this documentation work.
