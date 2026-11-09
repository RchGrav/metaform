# HybridParrot — final evidence checks

The consolidated resolution now incorporates EminentStrike's duplicate-seat validation observation, with the necessary call-order condition: a validation function's presence does not establish when it runs or which names it sees. The omitted engine might validate provisional seat labels before assigning generated agent names. Neither table-start rejection nor feedback rejection is proven by the supplied files.

GF2 requests documentation of the no-fallback behavior, not a fallback implementation. The comments at `config.rs:15–16` concern settings failures and explicitly say the seat still joins; they cannot establish a hard failure for resume. That behavior still requires the omitted session-start code.

Independent finite enumeration of every adjective/noun combination produced **65,536 distinct rendered names**. This verifies the output-space count directly rather than inferring concatenation uniqueness from unique entries in each list. The calculation used the source's first-character capitalization and concatenation on the supplied lists.

For 300 independent uniform draws from that space, the probability of at least one collision is:

`1 - product((65536 - k) / 65536 for k in range(300)) = 0.4961121639277085`.

This is a distribution-dependent scale illustration. It proves neither that actual session IDs have that distribution nor that any downstream rating resolver rejects a name. A demonstrated hash collision establishes only that the display label is not an identity key.

Two scope corrections also matter: `genesis_name` being pure does not prove its callers use the right ID; and source references to a historical document or reference implementation are checkable citations in this excerpt, not evidence that those external files have been inspected.
