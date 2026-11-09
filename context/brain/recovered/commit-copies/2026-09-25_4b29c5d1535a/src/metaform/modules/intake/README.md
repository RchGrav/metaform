# intake

Serves the Canonical Intake instructions by name and stores the intake's final shape.

## Purpose

The intake is agent work. A subagent reads the instructions with `intake prompt`, performs the whole method on the artifact, and submits the final shape once with `intake_submit`. The module stores it as one intake layer in one atomic write and reports whether the project has an intake. It ships enabled.

## Template version

Started from template 0.2.0.

## Declaration

`SUPPORTED_OS = ('linux', 'macos', 'windows')`, `DEPENDENCIES = ()`, `SHIPS_DISABLED = False`. `MODULE` declares `prompt`, `submit` and `status`, and a status hook.

## Common base used

`metaform.module` for the declaration, `Context`, `Status` and `save_report`; `metaform.settings` for `--intake-file`; `metaform.data` for the atomic write.

## Verbs

- `prompt`: the stored intake text with the project's target filled, then the submit lines: always the submit line and the rule to stop and submit a trouble report with `feedback` instead of retrying; the report request when `--report` is on; the feedback request when `--debug` is on. Takes `--report` and `--debug` for one call. Tool `intake_prompt`.
- `submit`: stores the submission in one atomic write and never refuses it for its content. What does not fit is stored as given and named in a notice with its path: a missing field is stored empty, an unknown field is kept in the row's `extra`, a subtype's purpose and a subtype provider that differs from its element go to the subtype's `extra`, a provider that names no element gets one in the intake layer, and an address out of form is stored as given. `elements` that cannot be read at all store nothing and return one notice to save the result with `feedback`'s `shape` field. Over MCP `elements` is the array and a string is never read as a path; on the CLI `elements=<path>` names a JSON file, or `-` for standard input. `report=` and `feedback=` are saved as the intake layer's report and feedback files, and each element, join and subtype may carry `flag` and `flag_note`. A second submission into a metaform that has an intake is stored as a new active metaform named `intake-<UTC timestamp>`; the earlier one is kept. Returns the layer, the project, the metaform, the counts of elements, joins, subtypes, refs and findings, and the notices. Tool `intake_submit`.
- `status`: whether the project has an intake, with the latest intake layer. Tool `intake_status`. The status hook adds `Intake: complete` and `Start with: metaform map roots`, or `Intake: none yet` and the notice to delegate the intake.

## Settings

`--intake-file`, default empty, meaning the Canonical Intake in `resources/`. The prompt also reads the chassis settings `--report`, default on, and `--debug`, default off, CLI-034.

## Events

None.

## Sync and async

Every verb is a plain function.

## Layers

Each submission makes one layer `intake-<UTC timestamp>-<6 hex>`, kind intake, immutable, not hideable, created ready, with provenance module `intake`, workflow `canonical-intake`, the exact prompt served, and the model, role and blinded flag the agent gives.

## Lifecycle and cleanup

No `start` or `stop`, and no tasks.

## Modules relied on

None.

## Systems supported

Linux, macOS and Windows.

## Resources owned

`resources/Canonical_Intake.xml`, a byte copy of `specifications/Canonical_Intake.xml`; a repository test fails when they differ.

## Installed and direct wheel

The same in both; the intake text travels inside the module.

## Demonstration

```
metaform intake prompt
metaform intake submit elements=result.json id=my-result
metaform intake status
```
