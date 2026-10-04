# Specifications

## Start here to rebuild the specification

- `UNBUILT-DESIGN-2026-09-27.md`: every design point that is not built or is built differently, each with what it is, why, its state and the record that mentions it.

## The specification

- `spec/00-index.md`: the Metaform specification, the contract a builder builds from. Start here. It lists the sections below and the record format.
- `spec/01-map.md` to `spec/09-viewer.md`: the nine sections, MAP, LAYER, STORE, BASE, CLI, MCP, QUAL, PROJ and VIEW.
- `spec/OPEN-QUESTIONS.md`: every open question, with recommendations, and the engineering choices made.
- `spec/TRACE.md`: every source requirement mapped to the records that carry it.
- `spec/CAPTURE.md`: every design point from the design discussion, with the record that carries it.
- `spec/viewer-prototype.html`: the approved viewer prototype, the visual baseline of the web GUI.

## Sources the specification absorbed

- `REQUIREMENTS.md` and `REQUIREMENTS-corrections.md`: the source requirements, mapped into the spec by `spec/TRACE.md`.
- `SETTLED.md`: design settled in conversation, carried into the spec.
- `Intake_2.0.md`: the intake procedure, Intake 2.0, the served intake. The intake module serves a byte copy of it, `src/metaform/modules/intake/resources/Intake_2.0.md`, and a test fails when the two differ. Rich, 2026-10-02, asked whether Intake 2.0 should become the served intake: "I think that".
- `Canonical_Intake.xml`: the previous intake procedure, kept as the previous version and no longer served, BASE-039.
- `Canonical_Intake_test.xml`: identical to the Canonical Intake until `ef` was added to the Canonical Intake on 2026-09-26, and left as it was then.
- `Canonical_Intake_old.xml`: the version before, reference only.
- `Sonnet_Intake.xml`: an intake result used as a reference.
- `metaprompting_element_segments_example.md`: how an address and its prefixes carry inference.
- `code_quality_standards.md`: the quality bar, carried by section 7.

## The build and its checks

- `spec/BUILD-BRIEF.md`: how the building agent works from the spec.
- `spec/BUILD-LOG.md`: one entry per build step, with the records it satisfies, the tests added and what it found.
- `spec/BUILD-QUESTIONS.md`: the questions the build raised, for Rich.
- `spec/HANDOFF.md`: where the build stands and what comes next.
- `spec/COLD-BUILD.md`, `spec/COLD-BUILD-2.md` and `spec/COLD-BUILD-3.md`: the cold build checks of QUAL-011, where a builder reading only this folder would have to guess.
- `spec/MANUAL-TEST.md` and `spec/MANUAL-TEST-2.md` to `spec/MANUAL-TEST-5.md`: manual tests of the build, each dated with its commit.
- `spec/REVIEW-CODE.md` and `spec/REVIEW-CODE-2.md` to `spec/REVIEW-CODE-7.md`: code reviews against the quality standard and the spec.
- `spec/TEST-REVIEW-2.md` to `spec/TEST-REVIEW-8.md`: reviews of the tests against the records they protect.

## Earlier specifications, restored to this folder on 2026-09-27

These files were left off the `chassis` branch when it was started on 2026-09-24 and were restored unchanged from the `main` branch. They hold design from before the rebuild. They are listed by name only; none has been checked against the nine sections yet.

- `Canonical_Intake_draft.xml`
- `IMPLEMENTATION-PLAN.md`
- `Inference_Metaform_Reference.zip`
- `REMEDIATION-MATRIX.md`
- `brief.md`
- `chassis-design-conformance-2026-09-18.md`
- `chassis-full-code-review.md`
- `chassis-product.md`
- `data_folder.md`
- `digital-typolo.xml`
- `global-data.md`
- `intake-graph-viewer-plan.md`
- `intake.xml`
- `join_record_proposal-rough.md`
- `metaform functional walkthrough.md`
- `metaform-chassis-best-practices.xml`
- `metaform-metaform.xml`
- `metaform-specs-20260915-7c8f4d21.xml`
- `module-structure-refined.md`
- `namespace-join-implementation-plan.md`
- `plugin-system.md`
- `re.schema.json`
- `product/`: `DECISIONS-AND-CONFLICTS.md`, `PRODUCT-SPECIFICATION.md`, `SOURCES.md`, `UNDERSTANDING.md`, `source-manifest.json`
- `sample/`: `metaform.dt-codex-20260915-8d3f2c1a.xml`, `metaform.kl-codex-developer-best-practices-20260915.xml`
- `xml/`: `Canonical_Intake.xml`, `Intake.xml`, `README.md`, `artifact.xml`, `digital-archeology-deep.xml`, `digital-archeology-expand.xml`, `digital-archeology-shallow.xml`, `intake2.xml`, `intake_nested.xml`, `metaform-specs-20260915-7c8f4d21.xml`, `prompt_generator_orchestration.xml`

## Outside this folder

- `specs/` at the repository root: intake samples, `agent-mcp-design.md`, `jev-analysis.md` and the `code_metaform` files, restored from `main-wip-2026-09-24`.
- `feature-briefs/` at the repository root: the native metaform variants and shared knowledge service specifications, restored from `main`.
