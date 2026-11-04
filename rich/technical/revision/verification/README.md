# Verification materials

`results.json` records sixteen local checks performed during preparation. These are schema and small reference-semantics checks, not an end-to-end runtime test.

`build_contracts.py` is the artifact-generation and recheck utility used in this session. It writes the example contracts and results under its configured output path and reads the supplied Hermes correction from `/mnt/data/hermes-agent-ice-corrections.xml`. It is retained as provenance of the checks, not offered as the Metaform runtime or a language requirement. To rerun elsewhere, adjust its source/output paths and provide Python's `jsonschema` package. The latest resource-response fixture includes the current required cache fields.

Unexecuted integration checks remain identified in the specification and results.
