P2 needs separate discovery and delivery checks. `TOPOGEE-SPEC.md:291` specifies “record counts, not records” for `goto`. R-5.31 says a ticket “selects an agent's context.”

Proposed checks:

- Parent/child visibility through `goto`.
- Device CEL delivery through ticket context and the resolver.

A passing `goto` check cannot establish resolver behavior. These checks remain proposed.
