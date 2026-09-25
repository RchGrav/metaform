# Build questions

Questions the build raised. Each names the record it concerns, what the build did meanwhile, and what it blocks. The orchestrator takes them to Rich.

## Step 1, storage

**Q1. How is a blind-spot layer recognized? (STORE-040, LAYER-015)**
`answer` must refuse an item that is not in a blind-spot layer, and reads must show `open` for an unanswered challenge, but no layer kind, tag or field marks a layer as a blind-spot layer.
Meanwhile: `answer` accepts an item of any knowledge layer (kind `layer`) and refuses items of the intake, memory and correction layers. An unanswered item shows no state, so `open` is never shown.
Blocks: showing `open` on unanswered challenges.

**Q2. An explicitly empty list setting. (STORE-002, CLI-013, CLI-014)**
A list setting is stored one row per member, so an empty list has no rows and cannot be told apart from nothing stored. A folder then cannot override a parent folder's list with an empty one, for example `set --modules ''` below a narrowed folder.
Meanwhile: storing an empty list stores nothing, so the folder inherits again.
Blocks: nothing in the first working test.

**Q3. The join of an exported subtype. (STORE-027)**
The document's subtype rows carry the columns of `subtypes`, which has no join column; the join lives in `subtype_ids`. Without it an import cannot rebuild the subtype's identity row.
Meanwhile: each exported subtype row carries one extra member, `join_id`.
Blocks: nothing.

**Q4. Putting an element back needs a lookup by address. (STORE-017, STORE-005)**
An `add` in a correction layer reuses the most recently removed element at that address. No listed index finds element rows by address, so the lookup would scan.
Meanwhile: the store adds `CREATE INDEX elements_by_address ON elements(address)`.
Blocks: nothing.

**Q5. Is an intake element a node when the intake layer is not toggled on? (STORE-014, LAYER-019)**
STORE-014 says an element made by a layer is absent from a node read whose selection excludes that layer. LAYER-019 acceptance 2 says `set --layers practices` makes a node read return the practices layer's items, which needs the node itself to be found with the intake layer off.
Meanwhile: elements of the metaform, added by the intake or a correction layer, are always nodes; an element a knowledge or memory layer created shows only where its layer reaches. The intake layer's joins and items are still filtered by selection like any layer's, STORE-025.
Blocks: nothing in the first working test, where every layer is on.

**Q6. The next step in STORE-026's example names a verb that does not exist. (STORE-026, BASE-038)**
The example says `Next: metaform map add-element code.probe.echo`, and BASE-038 has no `add-element` verb; adding an element is `knowledge op=add-element`.
Meanwhile: the error's next step is `metaform map knowledge op=add-element layer=<layer> address=<address>`.
Blocks: nothing.

**Q7. A self join from an intake submission. (D11, D82, BASE-039)**
D11, settled by recommendation, refuses a join whose receiver and provider are the same element, and `add_join` refuses it. D82 is still open on whether `intake_submit` stores such a join as given.
Meanwhile: `intake_submit` lists a self join among the problems it refuses.
Blocks: only the D82 case.

**Q8. Property ids have no identity row. (STORE-033, STORE-039)**
`identities.kind` allows element, join, subtype and item, but `correct`, `edit`, `remove` and `history` also take property ids.
Meanwhile: a bare id not in `identities` is looked up through the `properties` `UNIQUE(property_id, layer_id)` index.
Blocks: nothing.

## Step 2, common base and modules

**Q9. The template's purpose. (BASE-019, MCP-008)**
BASE-019 says the template declares every field with none filled and loads when a copy is enabled; MCP-008 says a module whose `purpose` is empty fails to load.
Meanwhile: the template's `purpose` holds one placeholder sentence telling the author what to write, ending `Details: metaform help template.`, so a copy loads. Its other fields are empty.
Blocks: nothing.

**Q10. Discarding a layer whose items keep identity rows. (STORE-032, STORE-033)**
`discard` keeps every identity row and deletes the layer row, but `item_ids.layer_id` references `layers`, so the layer row cannot go while its items' `item_ids` rows stay.
Meanwhile: `discard` deletes the discarded layer's `item_ids` rows and keeps their `identities` rows, so an item id is still never reused.
Blocks: nothing.

## Step 3, CLI and settings

**Q11. Is `--quiet` a setting or a verb control? (D32, CLI-004, CLI-031)**
D32 says `--quiet` is a setting because people want it to stick, while CLI-031 has `-q` and `--quiet` suppress output on the one `set` or `unset` call they are given on; on `set`, a setting switch is stored, so `set --quiet` cannot mean both.
Meanwhile: `-q` and `--quiet` stay verb controls of `set` and `unset`, never stored.
Blocks: nothing in the first working test.

**Q12. The status line for a project with no metaform yet. (CLI-028, STORE-041)**
Line 5a shows the active metaform's name, but a project has no metaform until its first write creates `main`.
Meanwhile: status shows `Metaform: none yet` until then.
Blocks: nothing.

