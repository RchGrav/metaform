# Namespace objects, mirrors, and workflow provenance implementation plan

> **Superseded plan/specification — retained evidence.**
> [REQUIREMENTS.md](REQUIREMENTS.md) is the complete governing contract.
> Its [section 20](REQUIREMENTS.md#20-remediation-instructions) authorizes
> active outside-in remediation, tracked in the [live matrix](REMEDIATION-MATRIX.md).
> The earlier tasks, authority statements, technology choices, open questions and
> completion claims below add no requirements and impose no continuing pause.
> They remain useful as historical implementation and verification evidence.

This plan implements Rich's September 18 explanation. It is an execution plan,
not a replacement for the intake glossary or a new definition of Metaform.

## Goal and why

Store one universal namespace shape: `namespace_address`, `name_length`, and
owned, typed joins. Preserve the ability to distribute the joins across SQLite
databases, assemble them, and export a chosen subset. Use those same objects for
workflow definitions, inserted context, issued prompts, answers, and their
provenance. A final answer must lead back to the prompt and the actual inserted
objects which produced it, including previous step answers.

The namespace gives functional meaning to the subjects of reasoning. Typed joins
allow contributions to extend that understanding. Mirrored storage organizes
those contributions without replacing their common shape with separate fixed
domain record models. Placement, copying, and export retain those relationships.

## Scope of this delivery

- Universal object and SQLite join storage, including arbitrary database routing.
- Stable join references and retained revisions for issued work.
- Selective export and merge preserving supplied identities and open content.
- A workflow module that stores text plus inline object references and per-reference
  layer selection, records issued context and answers, and traverses provenance.
- CLI access through the existing plugin contract and a web editor/browser for
  the same workflow objects.
- Focused behavioral verification of a three-step chain and split/unified export.

Existing file-history handling, wheel building, settings, module lifecycle, and
execution scheduling retain their responsibilities. No live data is migrated by
this implementation task.

## Implementation choices

Namespace rows use their address as their unique key. Project ownership belongs
to contributed joins and their references when projects share a database.
Database selection is configured outside the join's semantic type; a type route
is an optional placement preference and an explicit destination is supported.

Rich confirmed persistent join IDs on September 18. Supplied IDs are retained;
generated IDs default to UUIDs. A reference identifies the project,
receiving namespace, join ID, and selected revision. References to actual project
folders remain authored content; they are not converted into namespace identities.

Join kinds and their domain fields remain open. The storage engine does not
require intake fields on provenance or workflow joins. Storage conflict handling
reports divergent copies with the same identity and revision instead of silently
replacing one; it does not validate or reject prompted semantic content.

The updated [Canonical Intake](Canonical_Intake.xml) records a provider's EF for
its specific encounter inside the receiving element's join. The universal object
has no element-level EF field; intake can therefore record different encounters
with a shared provider without changing that provider's namespace identity.

## Task 1 — universal storage

Own `src/metaform/namespace_objects.py`, `src/metaform/namespace_store.py`, and
`tests/test_namespace_store.py`.

- [x] Write and run failing split/unified, selective export, and revision tests.
- [x] Implement NamespaceObject and JoinRef with lossless reference encoding.
- [x] Implement namespace-row/owned-join persistence, configured routing, assembly,
  revision reads, selective export, and merge.
- [x] Verify identical subject meaning and contribution identities after moving
  selected joins between two files and one file, with unrelated joins retained.

Public entrypoint:

```python
NamespaceStore(project, databases, routes=None, default_database=None)
store.ensure(namespace_address, name_length)
store.get(namespace_address, join_types=None)
store.list(scope='')
store.put_join(namespace_address, join, name_length=1, database=None)
store.resolve(join_ref)
store.export(scope='', join_types=None)
store.import_export(document, database=None)
```

## Task 2 — workflow object composition and provenance

Use the storage contract directly through chassis data access. The workflow
module owns its join kinds and domain content. A definition contains authored
text and inline object bindings; an issued step retains the rendered text,
the references and selected contributions inserted, and its resulting answer.
Provenance is an owned join contribution in the mirrored namespace structure.

- [x] Verify that editing an input after issuance does not rewrite the issued
  context recorded for an existing output.
- [x] Verify output 3 → prompt 3 → output 2 → prompt 2 → original input traversal.
- [x] Verify that a record merely available in a layer is not falsely recorded as
  an input to a step that did not receive it.
- [x] Expose creation, issuance, answer recording, browsing, and export as module
  operations and ordinary Click contributions.

## Task 3 — editor and browser

The web feature presents the workflow module's objects. Inline references render
as their namespace nouns and retain editable layer selection. Selecting an output
opens its issued prompt and clickable inserted object references.

- [x] Implement editing of authored text and insertion of namespace/knowledge
  references without reducing them to substituted strings in the definition.
- [x] Implement inspection of issued prompts, bindings, and preceding outputs.
- [x] Exercise an actual three-step chain through the UI and CLI services.

## Task 4 — integration and evidence

- [x] Review object, provenance, and transport boundaries against Rich's described
  shape; a passing test is not evidence that an invented schema is acceptable.
- [x] Run relevant new tests and the existing chassis behavioral suite after
  integration. Preserve unrelated dirty source and protected instructions.
- [x] Record the actual demonstrated behavior and remaining work, with no claim
  that unspecified workflow or provenance behavior is complete.
