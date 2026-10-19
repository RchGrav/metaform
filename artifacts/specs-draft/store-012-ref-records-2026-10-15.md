# Drafted amendments: refs as records of the sources layer, 2026-10-15, ticket code.graph.knowledge#c

Drafted by the worker on code.graph.knowledge#c for the owner's approval. The ticket asked for STORE-012 and LAYER-028
to be amended directly; by the spec-amendment rule a worker drafts here and the owner's session lands the bullets.
Each bullet is appended after the record's `Status:` line, the record's earlier sentences left as written. The code
is the reference: each bullet says what is built.

## STORE-012 Refs (specifications/03-storage.md)

- Amendment, 2026-10-15, ticket code.graph.knowledge#c, CTX-065: a ref of the sources layer is no longer a key and
  value on one version of an item. Each ref is an item of its own in the sources layer, at the element or join it is
  linked at, written only as versions of that item (src/metaform/data/refs.py): its value is its ref_id, its refs are
  its key and value then its details (the pairs that followed a `path` in the same list, such as `lines` and
  `object`), and its extra holds who linked it, when, the place the link named, and why, which is also its version's
  reason. The item's id lasts across an edit, a move and a removal, each a version, so a removed ref reads in its
  history; adding a ref to an element leaves the others' ids alone. Writes reach it by `Store.link_ref`,
  `place_refs`, `unlink_ref`, and through `add_item`, `add_ref`, `edit` and `remove` on the sources layer, which
  route to the records (src/metaform/data/writes.py:183, :204, :421, :470); reads by `Store.ref` and `Store.refs`
  (src/metaform/data/store.py:259-290). A ref given to the sources layer that is not a key and a value, both text, is
  never refused: a key or value that is not text is linked as its JSON text, an object of one entry as that key and
  value, anything else under the key `ref`, with one notice counting them (`link_all`). Refs on items and properties
  of every other layer, such as a provenance record's files, are still that item's own key and value list, as this
  record first said. Layout 22 (src/metaform/sqlite.py:25, compatible_from 22) makes every current item of the
  sources layer into records and removes the item as a version (`refs_to_records`, src/metaform/data/upgrade.py:241),
  writing its counts, names and moves beside the backup. The `refs` table SQL above is layout 20's and is no longer
  created.

## MAP-021 Refs are an ordered key and value list in the sources layer (specifications/01-map.md)

- Amendment, 2026-10-15, ticket code.graph.knowledge#c, CTX-065 and CTX-066: an element's or a join's refs are
  records of the sources layer, one item per ref, each with a ref_id unique in the base, no longer one item holding
  an ordered list. The refs at a node read in the order each was first linked (`Store.refs(node)`); `citing` still
  finds each by its key and value, at the address it sits at. The intake and `map knowledge op=add-element refs=`
  link each ref given at the node and remove the refs at that node that were not given again (`place_refs`). A ref
  never moves: the same key and value linked at another place is a second ref there (code.graph.knowledge#17; refs
  are not properties, and CTX-009 is for properties only). Acceptance 1 holds as written.

## LAYER-028 (specifications/02-layers.md), settling its 2026-10-08 amendment

- Amendment, 2026-10-15, ticket code.graph.knowledge#c: the owner's form of 2026-10-08 is settled for refs, as
  CTX-066 records: a ref is named `{ref_id}@{address}`, the referenced thing's name, `@`, the Address it serves.
  What a `:{join}` part names is open (CTX open question 25), so no `:` part is built: a ref on a join is named at
  its receiver's Address, and its record's `join` gives the join (src/metaform/data/refs.py:103). A read by a name
  whose Address is not where the ref is now answers with where it is, with a notice (refs.py:137).

## CTX-063 One call links a file (specifications/11-context.md)

- Build, open item 2 is built, 2026-10-15, code.graph.knowledge#c: `dispatch link` writes a ref record
  (src/metaform/modules/dispatch/__init__.py:2728) with `ref=`, the ref_id, made from the path when left out
  (`derived`, refs.py:170: `src/metaform/data/refs.py` is `metaform.data.refs`, a package's `__init__.py` is the
  package, a taken name gets the extension, then `_2`), and `why=`; who linked it is the work and session of the
  agent's runner, or the surface. It answers `ref` and `id` besides `file`, `node`, `linked`, `made` and `said`. A
  name taken or reserved writes nothing and is answered as a result, exit 0 (BASE-044). Open items 1 (the element
  made in the base) and 3 (`join=`) are unchanged.

## CTX-065 A ref is a stable record (specifications/11-context.md)

- Build: built 2026-10-15, code.graph.knowledge#c, as the STORE-012 amendment above says. `sources_index` reads
  `Store.refs()` (src/metaform/modules/dispatch/runner.py:287), placing each ref's value at its address.
- Acceptance 1 to 3: test_a_refs_id_lasts_through_an_edit_a_rebuild_and_another_ref_and_a_removed_ref_reads_in_history
  (tests/test_store_map.py). Acceptance 4: test_dispatch_link_adds_the_ref_beside_the_elements_own_and_makes_an_address_that_has_no_element
  (src/metaform/modules/dispatch/tests/test_dispatch.py). Acceptance 5:
  test_layout_22_makes_every_ref_of_the_sources_layer_a_record_and_keeps_the_old_items_in_history (tests/test_store_map.py),
  and the run on copies of the five project stores, then on the stores themselves:

  | store | sources items | pairs | ref records | versions | moves | pairs lost | places lost |
  |---|---|---|---|---|---|---|---|
  | metaform main | 39 | 171 | 121 | 171 | 21 | 0 | 0 |
  | metaform feature-code-alignment-20261013 | 139 | 436 | 215 | 436 | 105 | 0 | 0 |
  | metaform app-internal-refactor | 397 | 6162 | 3 | 397 | 2 | 0 | 0 |
  | mgm main | 53 | 264 | 176 | 264 | 29 | 0 | 0 |
  | roundtable main | 149 | 243 | 116 | 243 | 6 | 0 | 0 |

  app-internal-refactor's items each start with `path=src/metaform/modules/web/page/app.js`, so its bundles become
  three refs; every item, with each place's own pairs, stays in history as the item's removal version.
- Status: built 2026-10-15. The live stores were upgraded at 22:05 UTC by a web server restarted from the working
  tree (backups under ~/.metaform/backups/upgrade-22, with refs-layout-22.json beside each). That run moved refs
  toward the trunk and made 6 elements to hold them, which was wrong: refs are not properties. code.graph.knowledge#17
  removed the move, restored every ref to each place it held before layout 22, and removed those elements as
  versions (artifacts/refs-restore-2026-10-15/README.md). The table above is the bad run's; its "moves" column counts
  moves that were undone.

## CTX-066 A ref is named {ref_id}@{address}:{join} (specifications/11-context.md)

- Build: built 2026-10-15, code.graph.knowledge#c, without the `:` part (open question 25); corrected by
  code.graph.knowledge#17 the same day. A ref stays at the one element or join it was linked at; no ref moves and no
  element is made for one. The same key and value linked at another place is a second ref there, its derived ref_id
  unique in the base (`metaform.data.views`, `metaform.data.views_py`). Uniqueness refuses a ref_id held by another
  ref, naming `{ref_id}@{address}`, and a ref_id given for a key and value another ref at the same node already
  holds. A removed ref's ref_id stays its own: linking its key and value again at its node brings it back under its
  id. Acceptance 1 and 2 as written describe the move; the amendment drafted in
  artifacts/specs-draft/ctx-066-refs-stay-where-linked-2026-10-15.md replaces them.
- Acceptance: test_a_ref_stays_where_it_was_linked_and_a_file_linked_at_two_places_is_two_refs
  (tests/test_store_map.py). Acceptance 3 waits on open question 25.

## CTX-087 Reserved field names (specifications/11-context.md)

- Build: built 2026-10-15 for the ref writer, code.graph.knowledge#c: the thirteen names are
  `metaform.data.RESERVED_REF_NAMES` (src/metaform/data/refs.py:42). A ref_id given as one of them writes nothing
  and is answered with the reserved list and the next step; a name made from a path skips them. The other names
  `this` reads are not reserved (open question 19). The `this` reader imports the list when flat reads are built
  (CTX-085, open question 17); the guard test of acceptance 2 goes with that.

## Not built, by the open questions

- `main` (CTX-085, CTX-086; open questions 13 and 18), flat reads on `this` (open question 17), the `:` part of a
  ref's name (open question 25), and further reserved names (open question 19).
