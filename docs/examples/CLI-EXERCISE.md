# Local CLI exercise record

[Documentation](../README.md) | [Edition notes](../EDITION.md) | [Project walkthrough](project-walkthrough.md)

**Date:** September 26, 2026  
**Source edition:** `chassis`, attributed commit `ce9062bdec9398ca1f23ac60684bd3cc7e37f23c`

This record describes the local command exercise used to check instructions in the guides. It is separate from the author's original model work and from the supplied September 26 project intake.

It records the source of that day. Since then the intake is recorded one object per call and `intake submit` is gone, and the store is at schema version 5, which does not import the version 1 export this exercise imported. The guides now use the kitchen timer's map recorded by hand in [Getting started](../guides/getting-started.md#record-a-small-map-by-hand).

## Environment and inputs

The exercise ran the supplied source through `python -m metaform`, with `PYTHONPATH` pointing to its `src` directory, `PYTHONDONTWRITEBYTECODE=1`, an isolated `METAFORM_HOME`, and temporary workpiece directories. No persistent user configuration or supplied source was changed.

The principal input was the recorded [project export](project-metaform.json), imported into a local project named `reference-demo`. A second project used the supplied [kitchen-timer fixture](../../tests/fixtures/intake_timer.json). The fixture's outer object contains an `elements` array; the array, not that wrapper, is the input expected by `intake submit`.

The [extension guide's `nodeview` example](../guides/extending-metaform.md) was copied verbatim from its Python code block into the isolated home's module directory. The bundled `hello` module supplied the other extension exercise.

## Invocations and observed results

There were **48 CLI invocations**. All returned process exit status zero. Result content was also inspected: the unreadable-input case below returned a notice and no map, not a successful intake merely because its process exit status was zero.

| Invocations | Operation exercised | Observed result |
|---|---|---|
| 1-4 | Module discovery, register `reference-demo`, import the project export, select the project for the folder | The import retained one Metaform and its intake layer. Discovery reported the missing MCP dependency while exposing the other available modules. |
| 5-7 | Read `code.system.plugin`, its provider-side joins, and `code.template.module` | The project name was `module contract and loader`; the provider had six joins; the template was located as an internal subtype with its containing relationship. |
| 8-11 | Open and add observations at an element and the module-author join | Initially empty memory was readable; the new join-local observation was returned at that join's address. |
| 12-16 | Create a knowledge layer, add a node item, add a property at `type:code`, finish, and read plugin context | The finished layer participated in context; the ancestor's property appeared as applying knowledge. |
| 17-22 | Mask at `code.system`, select at `code.system.plugin`, clear each override, hide and unhide the layer | Parent masking removed participation, the child selection restored it locally, clearing restored inheritance, and hiding/restoring changed visibility without deleting the layer. |
| 23-27 | Enable `hello`; greet normally and loudly; read history; wait zero seconds | The greetings were `hello, world` and `HELLO, WORLD!`; both invocations appeared in history; the zero-delay operation returned. |
| 28-30 | Export, reimport into the same project, and inspect configuration | Reimport skipped existing record identities rather than duplicating them. Configuration remained in the isolated home. |
| 31-33 | Enable the documented `nodeview` module and read an element and a join | The example loaded and returned the requested graph nodes through the supplied shared context/store. |
| 34-35 | Create a memory relation and search memory | The memory relation was retained independently of the functional purpose joins; the search returned matching memory content. |
| 36-41 | Create and finish a correction layer, examine history and stack, then peel it | The correction recorded a deliberately local exercise observation, appeared in correction history, and could be peeled. The supplied source assertion was not edited. |
| 42-44 | Register `timer-fixture`, submit the wrapper object, then submit its extracted element array | The wrapper produced an unreadable-array notice and no stored layer. The array produced three elements, two joins, one internal subtype, and five refs, with no notices. |
| 45-48 | Submit the same element array again, list Metaforms, activate `main`, and read roots | Repeated intake created and activated a new Metaform while retaining the first one. Reactivating `main` made the original timer map readable. |

The actual module-author join used in the memory and correction exercises was:

```text
join:d14bd3498b614dfbaf0754c99b28dba3
```

That identifier belongs to the supplied project export. A newly generated intake has its own stored identifiers; the guides show how to obtain them rather than treating this example ID as universal.

## What this establishes

The exercise checks the documented read/write forms, the first-use import path, the distinction between fixture wrapper and submission array, selected layer behavior, and the module example against the supplied implementation. It provides a local observation of those operations, not a complete integration certification.

No new model inference was performed. Wheel building, client installation, live MCP transport, GUI interaction, artifact-history workflows, and the full test suite were not executed in this exercise. Their coverage in the guides comes from source inspection, as described in the [edition notes](../EDITION.md).
