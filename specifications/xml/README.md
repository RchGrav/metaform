# Digital Archeology — three variants

All three files share the same ontology, namespace_rules, and Method — they only differ in what they ask for as output. None of them use CDATA anywhere; the response schema in each is literal embedded XML, not a string blob, since a CDATA-wrapped schema converts to an opaque text field once parsed to JSON and stops acting as a structural pattern for whatever executes it.

## `digital-archeology-shallow.xml`
The baseline. Produces exactly one document: the final, annealed, coarse `result` — DE/SE/NE elements, their joins, and what got combined away during annealing. This is the version that has actually worked reliably. Use this unless you specifically need the deep pass.

## `digital-archeology-deep.xml`
Shallow intake plus a deep pass, requested together in one run via `deep_intake return="true"`. Deep expansion runs *after* the shallow result is finished internally, and only expands outward from that already-finished canonical shape — it does not independently redecompose the artifact. Produces two linked documents: the shallow `result` (with an `id`) and a `deep_result` (with a matching `ref`).

This is the retest. The first attempt at this failed — wrapped both documents in an invented tag, produced only the deep half, and substituted a top-down "architecture summary" for the actual recursive RE→OP→EF discovery. The two most concrete causes have been fixed: the CDATA-weakened schema (see above), and missing instructions telling the model both documents are required and neither gets wrapped. Whether that's enough, or the top-down-substitution problem is a separate, harder issue, is what this run tests.

## `digital-archeology-expand.xml`
Deep expansion only, decoupled from shallow generation entirely. Takes an already-produced shallow `result` as literal input (`canonical_input` — paste the finished XML from a `shallow.xml` run in there) plus `target` for going back to the source artifact when needed. It never generates a canonical shape itself, only expands one it's handed.

This is the architecturally strictest version of the deep pass: since shallow and deep happen as two fully separate invocations, there's no way for the model to blend the two phases or invent shallow structure while trying to satisfy a deep objective — the canonical shape is a hard constraint it's given, not something it can improvise around. If `deep.xml`'s combined run still drifts into architecture-summary mode, this is the version to try instead.

## Suggested order
1. Run `shallow.xml` on its own first — confirm it still holds up alone.
2. Either run `deep.xml` for the combined test, or take the `shallow.xml` output and feed it into `expand.xml` for the decoupled test.
3. Compare: if `deep.xml` still drifts but `expand.xml` doesn't, the failure mode is about combining both objectives in one pass, not about the deep concept itself.
