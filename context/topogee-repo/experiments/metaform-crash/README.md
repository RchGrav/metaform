# Metaform crash experiment

Storage note risk 3 (`docs/designs/storage.md`): kill the functional map server with SIGKILL in the middle of writes, under load, many times. Not product code.

`crash.py` drives the real `metaform` binary through `metaform call`, the way an agent's harness would. Six writer threads add receivers whose want creates a provider. The server is killed at a random moment in every round, and the next call starts a new one. After each round the script checks:

1. Every write acknowledged with exit 0 is present.
2. No write is half visible: a receiver, its provider and the want edge all exist, or the receiver does not.

Run: `python3 crash.py metaform/rust/target/release/metaform <scratch dir> [rounds] [writers]`. Results are in `metaform/verification/metaform-crash-2026-11-07.json`.
