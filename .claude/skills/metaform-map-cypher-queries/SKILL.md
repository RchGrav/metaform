---
name: metaform-map-cypher-queries
description: Use when running map_cypher queries on the Metaform map.
category: development
---
# Query the map with map_cypher in the dialect the parser accepts

Write bare node bindings (`MATCH (e)`), filter on properties with WHERE, and put every string in double quotes. Anything outside that subset is rejected before it runs.

- `MATCH (e:Element)` fails: "No terminal matches '('". Use `MATCH (e)` and filter with `WHERE e.kind = "element"`.
- `labels(e)` is not supported; read the kind from a property instead.
- Sorting with `ORDER BY` over an unfiltered match raised "'<' not supported between instances of 'float' and 'str'" (rows with a null property). Filter first, then sort; the filtered query returned all 66 element addresses.
- Edges are matched by kind: `[x] WHERE x.kind = "join"`.
- On an error, read the `Next:` line; it says which input schema to call with.
- Read a whole address list in one query, then compute per-address results in a local script instead of issuing one query per address.
