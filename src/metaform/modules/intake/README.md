# intake

Serves the Canonical Intake instructions by name and stores the intake's final shape.

## Purpose

The intake is agent work. A subagent reads the instructions with `intake prompt`, performs the whole method on the artifact, and submits the final shape once with `intake_submit`. The module stores it as one intake layer in one atomic write and reports whether the project has an intake. It ships enabled.

## Template version

Started from template 0.2.0.

## Declaration

`SUPPORTED_OS = ('linux', 'macos', 'windows')`, `DEPENDENCIES = ()`, `SHIPS_DISABLED = False`. `MODULE` declares `prompt`, `submit` and `status`, and a status hook.

## Common base used

`metaform.module` for the declaration, `Context` and `Status`; `metaform.settings` for `--intake-file`; `metaform.data` for the atomic write.

## Verbs

- `prompt`: the stored intake text with the project's target filled, then the submit line. Tool `intake_prompt`.
- `submit`: checks the submission against its input schema and stores it. Over MCP `elements` is the array; on the CLI `elements=<path>` names a JSON file, or `-` for standard input. Returns the layer name, the project and the counts. Tool `intake_submit`.
- `status`: whether the project has an intake, with the latest intake layer. Tool `intake_status`.

## Settings

`--intake-file`, default empty, meaning the Canonical Intake in `resources/`.

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
