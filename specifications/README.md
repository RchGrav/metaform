# Specifications

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
- `Canonical_Intake.xml`: the intake procedure, the tested version. The intake module serves a byte copy of it, `src/metaform/modules/intake/resources/Canonical_Intake.xml`, and a test fails when the two differ.
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
