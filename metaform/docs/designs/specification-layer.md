# Specification layer

**State:** built on branches, not merged. Owner review pending. Written 2026-11-09 by Marcus (MCP review), with Ida (export and import), Matthew (TASTE) and Jorge (store). Requirements: `metaform/SPEC.md` R-6.24 to R-6.28.

## Purpose

Intake records a project's functional skeleton: elements, roles and wants, with no prose (R-3.20). The specification layer holds the prose the skeleton leaves out on purpose: what each element does, how it behaves, and the reasons behind it. Agents keep the prose current through the `project-map` tool. A CLI command exports the map and its prose as one Markdown specification. The structure is built for round trips: the export can be imported again with nothing lost, because the tool enforces the Markdown heading structure when the prose is written.

## Owner decisions

Each entry restates the decision and gives its reason. "Relayed" means the decision reached Marcus through another session, not from the owner directly.

1. **A specification layer starts after intake** (owner, 2026-11-09, the goal the owner gave for this work). The layer stores data in the map. It encodes Markdown heading levels for its text, and the tool enforces them. Its text is not normative and follows TASTE. Agents use the MCP server to keep specifications up to date, and a CLI export produces a well-organized specification document. Reason: the skeleton holds functionality only, so a specification needs its prose kept elsewhere in the map, in a form agents can maintain and export.
2. **All layers work the same way** (owner, 2026-11-09, relayed by Jorge). The specification layer gets no mechanism of its own. Reason (Proposed, the agents' reading, not stated by the owner): one mechanism with no special cases keeps the forms and tools few. This applies the owner's reason for the read form (R-6.27), that a form consistent with every other command is the right design and any other form is a deviation. The owner also treats `wants`, `skills` and `memory` as layers, which fits one mechanism but is not itself a reason. See Open decisions, item 3.
3. **The layer is defined by the element `layer.document.specification` in the main map** (owner, 2026-11-09, relayed by Jorge). So `layer` becomes a root scope, and a root prefix like `upstream` and `downstream`. Reason (owner, recorded in R-3.3): a layer definition is not located in the project, and under a project root such as `data` it would mix with the project's functionality and read as part of it.
4. **The data sits on the receiving elements as a JSON field named `specification`** (owner, 2026-11-09, relayed by Jorge). The owner left the choice between a dictionary and an array to the team. Jorge chose an array, for the reasons under Decision rationale.
5. **A block can carry a code that works as a key, unique across the specification, so text can cite it** (owner, 2026-11-09, relayed by Jorge).

## Design

### Layer definitions (every layer)

- A layer is defined by an element beneath the `layer` root scope that has an `instruction` field. The layer's field name at receiving elements is the definition's last address segment. `layer.document.specification` defines `specification`. The field name is the layer's key at every receiving element, so a write that would give two definitions the same last segment is refused with `LAYER_NAME_COLLISION`, naming the existing definition.
- A layer's value at an element is a list of records.
- Records are accepted only at a skeleton element: one with `technical_name`, `name` and `role`, which are R-3.4's mandatory fields. The root `.` is the exception: it accepts records once the map has a Definitive element. Elements in the `layer` scope never hold records. Refusal: `ELEMENT_NOT_IN_SKELETON`. This is how "after intake" is enforced without a done marker, which R-5.19 rules out.
- Records the write did not change are not checked again. So a later intake correction, such as removing a role, is never refused because of records already stored.
- `goto` lists every defined layer whose records are allowed at the address, with its record count, even when the count is 0. The sheet's `instructions` part carries each listed layer's guidance. The server delivers each entry once per connection, not once per address.
- A read names each layer in the slot where it is written, with `{}` as its value: `{"<address>": {"specification": {}, "wants": {}}}`. A defined layer with no records reads as `[]` where records are allowed. The root's own blocks appear in the raw dump, `{".": {}}` (R-5.34).

### The `markdown_blocks` format

A definition may declare `format: "markdown_blocks"`. The specification layer declares it, and so can any other layer. Its records are blocks:

```json
[
  {"text": "Intro prose under the element's heading. Optional, first block only."},
  {"level": 1, "code": "PL-1", "title": "Packing", "text": "Prose."},
  {"level": 2, "title": "Limits", "text": ""}
]
```

The tool enforces these rules on every write that changes the blocks:

| Rule | Refusal |
|---|---|
| A block is `{level, title, text}` with an optional `code`, or `{text}` alone as the first block (the intro, which must have text). | `FIELD_MISMATCH`, with an example as the remediation |
| A title is one line. It does not start with `#` or a backtick, and does not end with an address in backticks inside parentheses (the export's element-heading form). | `FIELD_MISMATCH` |
| The first titled block is level 1. Each level is at most one more than the level before it. No level is above 4. | `HEADING_LEVEL_INVALID`, with the same update with levels corrected as the remediation |
| Text holds no Markdown heading line outside fenced code: no ATX line (`## Title`) and no setext underline (`---` or `===` directly under a paragraph line). | `HEADING_IN_TEXT`, with the heading moved into a block of its own as the remediation |
| A code is a letter, then up to 31 letters, digits, `.`, `_` or `-`, ending with a letter or digit. Only a titled block has one. | `FIELD_MISMATCH` |
| A code is unique in its layer across the whole map, ignoring case. | `CODE_NOT_UNIQUE`, naming the block that already holds it |

On write, the tool converts line ends to line feeds (LF) and trims each title and text. An empty list removes the field. `update` replaces every block at the address and is safe to repeat. `add` appends blocks and is not safe to repeat: if the answer is lost, a retried `add` appends the blocks twice.

The tool refuses nothing else. Sentence length, paragraph length, word choice and normative keywords are TASTE targets that depend on meaning. They are reported by `export --check`, which a person reviews (R-5.20; TASTE ranks meaning above length).

### The specification layer's definition

`metaform_core::specification::definition()` gives the definition element's fields: `technical_name` "specification document layer", `name` "Specification", `role` Supportive, `description`, `template` "{title}: {text}" (R-6.20), `format` `markdown_blocks`, and `instruction`, which holds the TASTE text below. The store writes this element into each main map on its first load in a server run, whenever the element is missing or differs (Jorge, branch `specification-store`). Standalone maps (R-4.15) are not seeded. A write to `layer.document.specification` that leaves it different from `definition()` is refused with `LAYER_DEFINITION_LOCKED`. The same rule applies to the intake group (R-6.22): agents write a layer's data, not its existence (R-6.11). The seed write is accepted, because it equals `definition()`.

### Instruction (TASTE for one block)

Prepared by Matthew from `TASTE.md` and the owner's short version (`context/brain/taste.md`). It is delivered with `goto`, after the format rules.

```text
Write each block in TASTE: Technically Accurate, Simple, Transparent English. A block adds what the map leaves out on purpose; do not repeat what the element's fields and wants already say.
- Start with what the element does or holds. Then give the detail that explains it.
- Name the element, field or command instead of starting with "it", "this" or "they". A block is often read alone.
- Use the project's terms and exact identifiers. Use one term for one thing. Put identifiers in backticks.
- Write one claim per sentence. Aim for 25 words or fewer per sentence and six sentences or fewer per paragraph. Never cut a condition, an exception or a reason to meet a length target.
- Use lowercase must, should, may, can and might with their TASTE meanings. Do not write SHALL or capitalized MUST.
- Say whether something is built, proposed or planned. Do not describe planned behavior as if it exists.
- Replace words such as simple, robust or fast with the behavior or a measurement.
- Define an abbreviation at its first use. Keep noun clusters to three nouns.
- Leave out openings such as "This section describes", repeated points, analogies and promotion.
- Prefer start, use, adjust, perform and end over kick off/launch/begin, utilize/leverage, modify/change/alter, execute/run and terminate/stop/abort, when the meaning stays the same.
- Do not put Markdown heading lines in the text. Set the block's level and title instead.
```

"Not normative" is read as: the prose explains the system, and the map and `SPEC.md` decide it. The instruction carries that reading. The tool does not refuse modal verbs, because TASTE rule 15 uses lowercase "must" in plain descriptions too.

### Export and import (Ida, branch `specification-layer`)

`metaform specification export [--project DIR | --map NAME] [--check]` prints the document. `metaform specification import [--project DIR | --map NAME] FILE | -` reads an edited document back. Both ask the server through an admin request (`export` or `import`), so the server stays the only reader and writer of the store (R-4.4). A folder with no map is refused, and the request does not register it, so neither command creates an empty map. The code is `metaform-core/src/markdown.rs` (render and parse), `check.rs` (the check) and `metaform-server/src/admin.rs` (the requests).

- Line 1 is `# <project name>`.
- Root blocks follow. Their Markdown level is the relative level plus 1. The intro is a plain paragraph.
- Each element has a heading ``## <name> (`<address>`)``. Its blocks follow at the relative level plus 2, so `###` to `######`. A block's code is a leading code span in its heading: ``### `PL-2.a` Purpose``.
- Under each element heading, a generated preamble comes before the intro: `Role: X. Technical name: Y. Status: Z.` (Status only when set), then one list item per want, using the R-6.17 template.
- The elements are every skeleton element, plus any element that still holds blocks. The `layer` scope is left out. Order: R-3.3 scope order, then each element directly before the elements beneath it (`specification::scope_order`).
- Elements that hold some of `technical_name`, `name` and `role` but not all three are left out. The CLI names them on stderr, so a map from an older intake does not export as an empty document with no explanation.
- The parser regenerates each preamble from the current map and strips it. It refuses:
  - a preamble or element heading that no longer matches the map: a stale document, or a skeleton change made in the prose;
  - an unknown address, or a `layer.*` heading;
  - a second section for one element;
  - a code used twice, with both line numbers;
  - a `##` heading that does not end with an element address in backticks;
  - a code fence that is not closed, at the line where it opens;
  - a document with no section for an element that holds text.
- Emptying a section, with its heading kept, removes that element's text. Dropping the section is refused, because the parser cannot tell a deletion from an accident. Each section's blocks pass `blocks`, `check_blocks` and `check_allowed`, so a document that parses can be written.
- Import is all or nothing. Each section whose blocks differ from the stored ones becomes one `{"update": {"<address>": {"specification": [...]}}}`, where an emptied section sends `[]`. The server first runs every update through `metaform_core::execute` on a copy of the map. At the first refusal it writes nothing and reports the address and the code. Only then does it send the updates through `Store::execute`. Exit status: 0 when the import wrote its sections or had nothing to write, 1 when refused, 2 on a usage or connection error. Limit: another agent can write between the check and the writes. Each write is still checked when it is made. If one then fails, the writes before it stay, and the CLI names them.
- `--check` prints the reports to stderr and leaves stdout as clean Markdown. It exits 0 with or without reports; reports are targets, not errors. Its 11 checks (Matthew's rules) are `CAPITAL_MODAL`, `SHALL`, `SENTENCE_LENGTH` (over 25 words), `PARAGRAPH_LENGTH` (over six sentences), `BLACKLIST` (the `TASTE.md` blacklist), `VAGUE_WORD`, `OPENING`, `START_PRONOUN`, `ABBREVIATION`, `REPEATED_SENTENCE` and `EMPTY_SECTION`. They skip code spans, fenced code, URLs, table rows and quoted text. Exact messages are in `metaform-core/src/check.rs`.

### Storage (Jorge, branch `specification-store`)

- Layer records are stored on the receiving element, as the owner requires. The store keeps every field without its own column in the element node's `extra` property, a JSON string. The `specification` array is one entry in that string. There are no layer tables and no per-block nodes.
- Block order is the order of the JSON array. Ladybug returns rows in no guaranteed order without `ORDER BY`, so separate block nodes would need a position property; the array needs none.
- Each command is one Ladybug transaction, and the store replaces the element's whole state, so a whole-array `update` is atomic and safe to repeat.
- Verified on lbug 0.22.3: one STRING property round-trips byte for byte up to 64 Mi characters, including quotes, backticks, backslashes, tabs and non-ASCII. A 200-block, 152 KB layer is unchanged after a restart. A `status` update on an element carrying that layer took about 11 ms in a debug build, against about 3.8 ms without it, because `extra` is rewritten. That is acceptable until a measurement says otherwise (R-5.20).
- On open, the store compares each table's columns with what the build expects. It renames `WANTS.intent` to `direction` in one transaction, and refuses any other difference with a schema error before it changes anything. A database made before the rename therefore opens with its wants intact.
- Code uniqueness is checked against the whole map on every write. Each check reads every block in the map. That cost is acceptable for today's maps; a code index on the map waits for a measurement that shows a need (R-5.20).

## Specification updates

Proposed additions to `metaform/SPEC.md`, made on this branch:

- R-3.3 adds `layer` to the root scopes (owner decision 2, relayed).
- R-6.24: layers are defined in the map, beneath `layer`, and all work the same way.
- R-6.25: the `markdown_blocks` format, its rules and block codes.
- R-6.26: records only on skeleton elements and at the root after a Definitive element exists.
- R-6.27: discovery through `goto` and the layer read.
- R-6.28: the specification export and import.

## Decision rationale

- **Array of blocks, not a dictionary** (Jorge's decision, which Marcus and Ida agree with). Document order carries meaning, and JSON object order is not guaranteed (RFC 8259); JavaScript clients also move integer-like keys to the front. A whole-array `update` is idempotent. A dictionary keyed by title would forbid two sections with the same title. Confidence: high.
- **Relative levels with a maximum of 4.** Element headings are `##`, so level 4 is `######`, the deepest Markdown heading. One rule holds at every address, and no heading level is skipped in the export. Confidence: high.
- **Skeleton test instead of an intake-done marker.** R-5.19 says intake has no start or stop. A mechanical test on R-3.4's mandatory fields needs no new state. Confidence: high.
- **Refuse only structural problems.** Heading levels and heading lines would break the round trip. The other TASTE targets depend on meaning, so a refusal would push agents to cut text until it passes. Confidence: high.
- **Guidance through `goto`, once per context, not in `tools/list`.** The tool definition reaches every agent in every session (R-1.3). `goto` follows R-5.30's rule that agents get context when it becomes relevant. A FIELD_MISMATCH refusal also carries a valid example, so an agent that writes without a `goto` still learns the shape. Confidence: medium. It depends on agents using `goto` before writing, which is the documented flow but has not been measured.
- **One contract change: the layer read.** Agents cannot keep a specification current without reading it back, and the input schema allowed only `{}` as a read value. The change lets a read value name layers in the slot where they are written, `{"<layer>": {}}` (`LayerRead`); `{}` alone still reads the element's own fields. The first build used a list, `{"layers": [names]}`; the owner replaced it on 2026-11-09 because every layer, `wants` included, is named the same way in reads and writes. Writes needed no contract change, because the schema already accepts any array as a layer (`ComposedElementLayer`).
- **Code form.** A code has no spaces or backticks, so it survives Markdown. It ends with a letter or digit, so a sentence's full stop is never part of it. Case-insensitive uniqueness stops `R-1` and `r-1` from being cited as two keys. Uniqueness is checked against the whole map on every write. The store sends each write to one writer thread, so two writes cannot both pass the check (Jorge, `metaform-store/src/lib.rs` `write`).

## Open decisions for the owner

1. **Closed 2026-11-09: the layer read changes the protected tool contract.** The owner approved the change in the form `{"<address>": {"<layer>": {}}}`, with the layer named where it is written, because it is consistent with every other command.
2. **The `goto` `instructions` part** adds a part to the R-5.30 summary sheet. Recommendation: keep it. The alternative is the tool description, which costs every agent tokens on every session.
3. **The reason for owner decision 2** (all layers work the same way) is recorded as Proposed: Jorge and Marcus read it from the owner's R-6.27 reason. Please confirm or correct it, so the spec can record it as decided. The reason for decision 3 is in R-3.3.
4. **R-6.15 lists `system` layers** (skills, memory, sources) as layers created only in code. Owner decision 2 suggests every layer, including those, should become a definition in the map. This design does not move them. Recommendation: decide this when memory and skills are built, not now.

## Risks and verification

- **Stale instruction text in existing maps.** Seeding rewrites the definition whenever it differs from `definition()`, so a text change reaches every main map on the next server start. Verified by Jorge's store test (branch `specification-store`).
- **An agent writes before `goto`.** It does not see the TASTE guidance, but the structure is still enforced. The `--check` report catches the rest.
- **`tools/list` size.** The layer read adds about 330 bytes to the tool definition. The size test on branch `tools-list-size-baseline` (`TOOLS_LIST_BYTES`) must be updated in the merge that brings both together.
- **Merged branch `specification-layer` (a296a70, 23971eb, 393608e and 0dc88dd merged with Ida's work), tests run 2026-11-09 in its own target folder:** core 13 unit tests (render, parse, codes, check), 4 contract tests and 5 specification tests; server 16 tests, including `the_specification_exports_as_markdown_through_the_cli` and `an_edited_specification_imports_all_or_nothing` (export, edit, import, export equals the edited document; re-import changes nothing; a refused import writes nothing); store 8 tests (9 with `execute_all`). clippy is clean. Python contract checks and `tools/verify_bootstrap.py` pass.
- **Earlier, on the separate branches:** core 4 unit tests, 4 contract tests and 5 specification tests; server 14 tests, including `specification_blocks_survive_a_restart_and_instructions_arrive_once`; store 6 tests (8 on `specification-store`, with the rename migration and seeding). Python contract checks: 30 and 13. `tools/verify_bootstrap.py` passes. These tests do not cover the export round trip, which Ida's tests cover on `specification-layer`.
- **Import atomicity (closed).** An import sends all its section updates as one write, `Store::execute_all` (Jorge). The writer applies them in order, each checked against the map the ones before it made, and stores them in one Ladybug transaction with one announcement. No other agent's write can land in between, and a refused section writes nothing. Verified by the store test `a_batch_is_stored_whole_or_not_at_all` and by `an_edited_specification_imports_all_or_nothing`. Any store failure that is not a refusal, such as a failed commit, is reported as "may or may not be stored", because the CLI cannot tell whether the transaction landed. The message asks the user to export the specification and compare it with the document before importing again.
- **Verified 2026-11-09 through the debug binary** (`e9c3c8b`, fresh home, by Marcus): seeding, `goto` listing and instructions, writes with codes, the duplicate-code refusal, export, `--check` (stdout unchanged, exit 0), then edit → import → export equal to the edited document byte for byte, a re-import that changes nothing, and two refused imports (skipped level, duplicate code) that write nothing. Ida repeated the sequence independently on `fd65d17`, with the same results, and also checked that an import is refused after an intake change makes the document stale.
- **Verified 2026-11-09 through the MCP protocol** (`99d988f`, debug binary, fresh home, by Jorge): a scripted client spoke JSON-RPC to `metaform mcp` over stdio, as an agent harness does, and passed 23 checks: `initialize`; `tools/list` offers `project-map`; skeleton writes; the root index lists `layer.document.specification` and `orphaned` leaves it out; `goto` lists the layer and delivers the TASTE instruction; block writes with a code, repeated; the layer read; refusals for a duplicate code in other case, a skipped level, and an edit or delete of the definition; CLI export, `--check`, import of an edited document, a refused import that writes nothing; and blocks that survive a server restart. The script is kept in Jorge's notes (`.jorge/probes/e2e_mcp.py`).
- **Not yet verified:** a Claude Code agent session that uses the tool through `.mcp.json`. That needs the release binary rebuilt from the merged code. `.mcp.json` runs the release binary from the main worktree for every session, so the rebuild waits for the owner's decision on merging to `main`.
