# Metaform examples

## Sample modules

The [hello module](../src/metaform/modules/hello/README.md) demonstrates the current
module contract and public services. Enable it in a registered project:

```sh
metaform enable hello
metaform hello greet world
```

Start a new module from the [template](../src/metaform/modules/template/__init__.py).
The [extension guide](../docs/guides/extending-metaform.md) explains the contract.

## Workflows

| Path | What it is |
| --- | --- |
| [workflows/sources](workflows/sources) | Seven authored workflows in Markdown. |
| [workflows/definitions](workflows/definitions) | The same seven workflows converted to the workflow module's JSON. The workflow tests compare the two. |
| [workflows/manifest.json](workflows/manifest.json) | The intent and inputs of each of the seven workflows. |
| [workflows/conditional_review.json](workflows/conditional_review.json), [workflows/element_prompts.json](workflows/element_prompts.json), [review.json](review.json) | Older workflow files. They have not been checked against the current workflow module. |

## Intake

[intake/mgm-main](intake/mgm-main/README.md) is a 2026-09-10 intake of the MGM project in the first intake format. It is kept for comparison. The current chassis cannot load it.
