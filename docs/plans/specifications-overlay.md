# Specifications on the map

Status: plan, 2026-11-16. Nothing built on this branch yet. The design is the one already built and tested on the
Rust branch on 2026-11-09; this plan carries it onto the Python project store.

## The problem it solves

Agents have been changing Metaform without knowing what it is or what the part in front of them is for. Two cases
from 2026-11-16: a camera change slipped into the 3D map inside an unrelated commit broke dragging, and a feature built
only because the agent protocol offered it (client files and terminals, an editor's feature in a program that has no
editor) kept every agent on the protocol's old version. In both, nothing put the purpose of the part in front of the
agent. The specification holds that purpose, and it belongs on the map, at the parts it describes.

## Source

The design, its tests and its history are in the archive `/mnt/c/spec_roundtrip.zip` (collected 2026-11-16 from the
Rust branch `fable-climb` at `943ac06` and from topogee). Read first:

- `2-current-metaform-943ac06/metaform/docs/designs/specification-layer.md`: the overlay, its block format and rules,
  the export and the import, the owner's decisions and the tests performed.
- `2-current-metaform-943ac06/metaform/SPEC.md`, R-1.2: the round trip as a requirement, in the owner's words.
- `.../rust/crates/metaform-core/src/markdown.rs` (`render` is the export, `parse` the import) and `specification.rs`
  (the overlay's definition and the rules on a block).
- `2-current-metaform-943ac06/metaform/docs/designs/specification-round-trip.md`: the earlier draft of the whole round
  trip, not reviewed by the owner.

## How it works, as designed

1. **In.** Intake builds the base map from the project or from a written specification. After it, an agent reads the
   specification and writes its text as blocks at the elements each part describes. This first step is done by
   inference, not by a command (owner, 2026-11-09).
2. **The overlay.** Each block is `{level, title, text}` with an optional `code`, unique across the project, that
   other text can cite. The first block at an element may be text alone, its introduction. The tool refuses only what
   would break the round trip: a skipped heading level, a heading line inside the text, a title that is not one line,
   a code used twice. The writing guidance (TASTE) comes with the overlay's instruction. Blocks at the top of the map
   are the project's own description.
3. **Out.** A command prints the map and its blocks as one Markdown document: the project's heading and description,
   then each element as a heading with its role, names and wants, then its blocks.
4. **Back in.** A command reads an edited copy of that document back and writes the changed blocks, all or nothing.
   It refuses any other document, and one that no longer matches the map. Export, edit, import and export again gives
   the edited document byte for byte.
5. **At start.** An agent is given the project's description and the base map. At a part, the part's localized view
   carries its blocks, so it reads what the part is for before changing it.

## Order of work

1. **The overlay** on the Python project store, given to every project as `wants`, `tickets` and `memories` are, with
   the block rules checked on every write that changes blocks. The store already names `overlay.specifications.project`
   as its example of an overlay.
2. **Export and import** as CLI commands, ported from `markdown.rs`, with the tests the Rust branch has:
   render-parse-render gives the same document; an edited import is all or nothing; a stale document is refused.
3. **Metaform's own specification in.** An agent reads `specifications/01` to `11` (about 450 requirement records) and
   writes them as blocks at the elements of the `metaform` map. The person sees the placements before they are kept.
4. **At start:** the project description and the base map in what an agent is given, and the blocks in the localized
   view at each part.
5. **Check:** an agent started on a ticket at the 3D view is shown the 3D view's blocks before it edits.

## Open

- **The layers that make up a project's specification** are recorded with the project's details, so a person never
  names them (owner, 2026-11-06). The Rust design exports the specification overlay alone; whether the export also
  carries other overlays is open there and here.
- **Which side is edited day to day,** the map or the exported document, once both exist.
- **`specifications/` itself:** whether the files stay as the written form, or the exported document replaces them.
