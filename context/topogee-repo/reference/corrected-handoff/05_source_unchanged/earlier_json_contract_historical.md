# Metaform — Canonical JSON Contract

The accompanying JSON Schema is the canonical serialization contract for Metaform. It describes the logical data model, not the implementation details of SQLite, NetworkX, GrandCypher, or another storage engine.

- `metaform` is the root. Namespace segments are nested JSON object keys, e.g. `metaform.code.system.management.knowledge`.
- A value may be a nested object, an array, or a scalar. **Any array** is a collection, independently of the key's name or its position in the namespace. No predefined collection-name catalog exists.
- Knowledge collection entries preserve their originating format and nesting. Metaform-native records use their own Metaform-defined format. Do not introduce a common wrapper, generate IDs for records, or impose semantic array ordering.
- A receiving element's `providers` is an object keyed by providing-element namespace address. Each value directly contains `op`, `ef`, and `ifd`. It is **not** a list. There is no `joins`, `layers`, `ops`, `pe`, or `element` indirection for these provider relationships.
- A provider relationship is identified by the pair (receiving element namespace address, providing element namespace address). The root Metaform `id` is document metadata, not a synthesized record ID.
- `name`, `name_length` and `role` may describe an element. Such words may also occur as namespace segments, as `code.registry.role` demonstrates. Do not decide identity or traversal from the spelling of a key alone.
- The JSON Schema checks the JSON representation and provider-record fields. It does not verify graph referential integrity (whether a provider namespace points to an actual element), which requires consulting the complete graph.

## Files

- `metaform_canonical_final.schema.json` — JSON Schema (Draft 2020-12).
- `metaform_canonical_example.json` — Small, illustrative instance showing arbitrary collections and a provider dictionary.
- `metaform_canonical_final.json` — Previous converted map rewritten to remove synthetic IDs and the orphan conversion-only `ops` record. The source XML and previous exports were not modified.

## Conversion note (not part of the schema)

The earlier export introduced numeric IDs for records and a leftover `ops` entry at `code.gateway.messaging` for an empty `<join>` lacking a provider and operative purpose. This new *example conversion* omits that entry, rather than promoting it into the canonical model. The original XML remains the authority for source content.
