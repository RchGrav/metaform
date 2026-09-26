# Source edition and validation

[Documentation](README.md) | [System introduction](../README.md) | [Preprint](preprint/inference-metaform.md)

This documentation edition is dated **September 26, 2026**. It explains the author's independently developed Inference Metaform and the supplied implementation, using the project's own recorded representation as its principal worked example.

## Repository placement

The archive is a documentation overlay. Its root `README.md` belongs at the repository root; its `docs/` directory retains the paths used by the links. The package includes the finished user documentation, preprint, technical-reference set, and example export. It does not include or replace the runtime, tests, packaging configuration, or operative prompts.

Links between delivered documents work within the extracted layout. Source links, such as `../../src/metaform/module.py` from a guide, resolve after placement in the supplied repository. Those source files are not duplicated in this documentation archive.

## Source identity

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

The branch and commit are the bundle's attribution in `BUNDLE_INDEX.txt`. The supplied source has no `.git` directory; this edition does not substitute a subsequently fetched branch. Package requirements are declared in [pyproject.toml](../pyproject.toml).

The live [Canonical Intake resource](../src/metaform/modules/intake/resources/Canonical_Intake.xml) is byte-identical to [its specification copy](../specifications/Canonical_Intake.xml). Its SHA-256 is:

```text
7e2140a9dd71c875689604772c07e5f0c1dd6366b55ba03a530211867eb909f8
```

The included [project-metaform.json](examples/project-metaform.json) is an unchanged copy of the supplied project export. Its SHA-256 is:

```text
213fc23c4e25078ce070c6148e957ec3eca18a0fd9e759902e3e3400fb887bc5
```

The export retains the original project path as recorded data. The [first-use guide](guides/getting-started.md) imports it into an explicitly named local project rather than assuming that original path exists on the reader's machine.

## Evidence used by the documents

**The design account** comes from the author's explanations and corrections. **Present operations** come from the operative source, resources, schemas, and tests. **Recorded project material** comes from the supplied map and associated records. **Derived illustrations** show uses of those mechanisms without presenting them as original agent runs. The earlier explanatory README, preprint, and generated drafts were not used as the basis for the new public account.

Research citations in the [preprint](preprint/inference-metaform.md#14-connections-to-other-work) were checked against the cited primary-source records. They locate subsequent conceptual connections; the author's independent development history is not derived from them.

## Documentation checks

The operational check used the supplied Python source with a separate `METAFORM_HOME` and temporary workpiece folders. It comprised **48 CLI invocations**, including an expected unreadable-submission notice. The [exercise record](examples/CLI-EXERCISE.md) describes inputs, results, and scope.

The exercise covered project registration and import, provider and subtype reads, element- and join-addressed memory, memory relations, knowledge layers and properties, prefix selection and masking, hiding and restoring a layer, correction history and peeling, the bundled demo module, and the extension guide's example module. It also submitted the supplied kitchen-timer fixture's element array, repeated intake into a new Metaform, and exercised export/reimport behavior.

These are local checks of the documented operations, not model-performance measurements. The exercise did not run an AI model, build or install a wheel, alter an agent client's configuration, start a live MCP server, operate the GUI, or execute the full test suite. Those other instructions and interface descriptions were checked against the supplied source. The exercise environment did not have the MCP SDK; module discovery reported that dependency directly.

Repository-relative links and document anchors were checked against both the delivered tree and the supplied source layout. The preprint was typeset from its Markdown manuscript, rendered for page-by-page layout review, and checked for text overflow and missing glyphs.

A before/after SHA-256 comparison found no changes in the **131 supplied source files**. The runtime and operative prompts remain unchanged.

## Continuity of the technical reference

[REFERENCE.md](inference-metaform/REFERENCE.md), [IMPLEMENTATION_MAP.md](inference-metaform/IMPLEMENTATION_MAP.md), and [EXAMPLES_TO_COLLECT.md](inference-metaform/EXAMPLES_TO_COLLECT.md) carry the substance of the completed technical-reference edition. A later presentation pass converted their ASCII structure drawings into rendered Mermaid diagrams, corrected `above`/`below` wording that misdescribed the namespace's trunk-to-leaves direction, and corrected the note about the select test's title now that the test is named `test_a_select_toward_the_leaves_from_a_mask_turns_the_layer_on_again_there_and_nowhere_toward_the_trunk`; no technical claim changed. Their account of the checks performed for that earlier edition remains intact; the additional local exercises are recorded here.

[IDEAS.md](inference-metaform/IDEAS.md) retains its eight tooling proposals. Its documentation-status section now links to the completed public materials instead of treating those delivered pages as future proposals. The separation between established mechanisms, completed documentation, and proposed additional tooling remains explicit.

## Citation

Use the [preprint citation](preprint/CITATION.md) for this edition and [references.bib](preprint/references.bib) for the accompanying bibliographic records. The author is credited as **Rich**, independent developer. No DOI or license has been assigned by this documentation work.
