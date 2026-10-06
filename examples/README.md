# Metaform examples

Nothing in this folder loads on its own. Load a sample module by path when you want it.

## Sample modules

| Module | What it shows |
| --- | --- |
| [showcase](modules/showcase/README.md) | Each chassis service in use: settings, records and their revisions, events, background jobs and assignments. |
| [event_requester](modules/event_requester/README.md) | Sending work to `harness_runner` over the event bus and keeping the reply. |
| [record_demo](modules/record_demo/README.md) | The smallest module. It stores one record and shows what produced it. |

Load one with its path:

```sh
metaform modules load examples/modules/showcase
```

## Workflows

| Path | What it is |
| --- | --- |
| [workflows/sources](workflows/sources) | Seven authored workflows in Markdown. |
| [workflows/definitions](workflows/definitions) | The same seven workflows converted to the workflow module's JSON. The workflow tests compare the two. |
| [workflows/manifest.json](workflows/manifest.json) | The intent and inputs of each of the seven workflows. |
| [workflows/conditional_review.json](workflows/conditional_review.json), [workflows/element_prompts.json](workflows/element_prompts.json), [review.json](review.json) | Older workflow files. They have not been checked against the current workflow module. |

## Intake

[intake/mgm-main](intake/mgm-main/README.md) is a 2026-09-10 intake of the MGM project in the first intake format. It is kept for comparison. The current chassis cannot load it.
