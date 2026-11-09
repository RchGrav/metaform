# RustyBoulder: corrections to the combined resolution

I inspected the sibling `code.gate.quality/source/crates/roundtable/src/turn.rs` and `code.quota.character/source/crates/roundtable/src/rules.rs`. They confirm that all three gates must reach 0.70 and both scores must reach 3.0, and that missing keys, context-budget failures, and evaluation errors cause sharing unjudged. This strengthens EarthenLiquid's evidence and removes my earlier caller-verification limitation.

I amended the combined `resolution.md` with four qualifications:

- GF6 is partly right: missing gate names and incomplete current scope need repair, but the dated owner statements do not contradict three gates plus two scores.
- GF3 measures separately estimated state and question payloads, not the entire request envelope; the heuristic is ceil(JSON UTF-8 bytes / 3), not a provider token count.
- GF4 has no local evaluation timer; the injected HTTP client may still configure timeouts. HTTP diagnostic truncation happens after reading the body. A context-budget failure differs from the caller's separate character-length rejection.
- GF7's owner comment establishes newest-release intent, not a provider-defined meaning for the leading tilde. The code passes the identifier verbatim; provider syntax remains unverified.

These changes preserve the verified five-check interface and the useful caller evidence while avoiding unsupported claims in the final decision.
