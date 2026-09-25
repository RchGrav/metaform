# Build brief

For the agent that builds Metaform from this spec.

## Where

- Repository `/home/rich/metaform`, branch `chassis`. The spec is `specifications/spec/`; start at `00-index.md`.
- The current chassis code is in `src/metaform`. The spec says, record by record, where it changes.
- Old branches such as `main-wip-2026-09-24` and `release-quality-wip-2026-09-24` are reference only. Nothing comes from them unless it matches a record.

## Goal

The first working test in section 6. Follow the build order in `00-index.md`. Build a step only after its tests exist and fail.

## How to work

- The shape of the metaform comes from `specifications/Canonical_Intake.xml`: its concepts, rules and response schema. It is the proper schema. Read it in full before building anything that stores or reads the map, and where any record, older file or earlier code disagrees with its shape, it wins.

- Build from the records. Each record's why says what the requirement protects. When a Build part and a why seem to disagree, stop and ask; do not pick.
- A record marked open is built only as far as it is settled. Do not fill the gap. Take the question to the orchestrator, who brings it to Rich.
- A record marked recommended is built as written.
- Every test names its requirement with `@pytest.mark.req("ID")`, protects that requirement, and fails on a build that gets it wrong. No tests that mirror the implementation. No tests for reversible, low-impact changes. Passing tests are not proof of quality.
- Quality is judged against `code_quality_standards.md` by a critic review before merge, with a separate review of the tests for gaming.
- Everything runs on Linux, macOS and Windows.
- Nothing writes into project folders. All data lives under the Metaform home.
- No XML import of intake results. The intake agent writes the map through the intake module's tools.
- The chassis runs no workflows and launches no models.

## Reporting

After each build step, report to the orchestrator: what was built, which records it satisfies, which tests protect them, and any question it raised. Commit each step on `chassis` with a message that names the records.
