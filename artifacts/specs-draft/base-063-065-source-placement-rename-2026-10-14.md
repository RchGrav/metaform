# Draft for Rich: BASE-063 to BASE-065 after the rename of `refactor` to `source_placement` (ticket code.analyzer.refactoring#a)

Not a specification. This is the text I would propose for `specifications/04-chassis-modules.md` once Rich confirms
it. The code as built on 2026-10-14 is the reference; it already behaves as written below.

## What changed in the code

1. The module id is `source_placement` (folder `src/metaform/modules/source_placement`). Its description, in the
   declaration, README and help: "Uses tree-sitter plus the existing functional map, and derives function placement
   into the map at a 90% confidence level."
2. Commands and tools: `metaform source_placement <verb>` and `source_placement_<verb>` for `intake`, `extend`,
   `status`, `pending`, `resolve` and `associate`; the client prompt is `source_placement-intake`.
3. The knowledge layer is `source_placement`, owned by the module `source_placement`. A layer the module makes now has
   the variable "Where each source function is placed on the functional map, with its confidence and reason."
4. Run files are under the project's `.metaform/source_placement/`. The Jev decision point is
   `source_placement.associate`. A remainder ticket made from now on carries the note
   `source_placement remainder: <run>`.
5. The default threshold is 90 percent (it was 83): a function is placed only at 90% or above; everything below goes
   to the Place remaining code ticket.
6. As the module starts, once per home, what was stored under `refactor` is kept under the new names: the module's
   enabled state, members of the `modules`, `layers` and `jev_decisions` settings and of aliases, the `refactor`
   layer of every base (renamed in place, items and provenance kept, through a new data-layer rename of a layer), and
   each project's `.metaform/refactor/` run files. Tickets already written keep their note and task text as written.

Unchanged: the intake procedure is still Rich's refactoring-preparation Axiom (BASE-063), so where it means
refactoring the English word stays, in its text and in the intake verb's help.

## Proposed record text

### BASE-063 Refactoring intake prepares reusable knowledge before implementation

- Requirement: An optional `source_placement` module serves an Axiom intake procedure that prepares refactoring
  knowledge in a `source_placement` CEL on the existing functional map.
- What this means: `metaform source_placement intake`, exposed as `source_placement_intake`, returns the procedure.
  (Rest of the bullet unchanged.)
- How it shows: An agent reads `source_placement_intake`, prepares the requested scope, then records and reads items
  at the receiving Addresses in the `source_placement` layer. An editing agent reads `<address>@source_placement` and
  the code context for that Address. (Rest unchanged.)
- Build: "creates the mutable, hideable `refactor` knowledge layer" becomes "creates the mutable, hideable
  `source_placement` knowledge layer". (Rest unchanged.)
- Acceptance 3: MCP declares `source_placement_intake` as a read-only tool, available when the module is enabled.
- Status (added): renamed from `refactor` to `source_placement` by Rich, 2026-10-14: the module does not refactor; it
  places code at the map. Stores made before the rename are moved once as the module starts.

### BASE-064 Optional bulk provider classification during source placement

- Title: "during refactor preparation" becomes "during source placement".
- Requirement: "Refactor preparation offers" becomes "Source placement offers".
- Build: `source_placement intake association=jev confidence=90` adds the optional procedure.
  `source_placement associate` receives named code evidence (rest unchanged).

### BASE-065 Code intake places indexed functions upfront and delegates the remainder

- Requirement: "through `metaform refactor extend` and `refactor_extend`" becomes "through
  `metaform source_placement extend` and `source_placement_extend`".
- What this means, first bullet: "The refactor module ships enabled." becomes "The source_placement module ships
  enabled."
- Third bullet: "The refactor module owns the Tree-sitter runtime" and "Missing refactor dependencies" become
  "The source_placement module owns the Tree-sitter runtime" and "Missing source_placement dependencies".
- Fifth bullet, replaced: Placements at or above the configured threshold, 90 percent by default, are recorded in the
  existing `source_placement` knowledge layer directly at the selected provider element acting as RE, never at a
  purpose/join record. A function below 90 percent is not placed: it goes to the Place remaining code ticket, whose
  session reads source, resolves category selections and records the evidence for each decision. (Rest unchanged.)
- Sixth bullet: "Local artifacts under `.metaform/refactor/`" becomes "Local artifacts under
  `.metaform/source_placement/`".
- Acceptance 7 (added): A home that stored the module's enabled state, setting and alias members, layer or run files
  under `refactor` reads them under `source_placement` after the module first starts, once.
- Status: "tracked with the refactor module" becomes "tracked with the source_placement module".
- Verified by: `src/metaform/modules/source_placement/tests/test_source_placement.py::test_a_home_with_refactor_data_reads_it_under_the_new_names`,
  and the threshold in `tests/test_pipeline.py::test_places_high_confidence_and_validates_remainder_without_rebilling`.

## Also affected

- `artifacts/specs-draft/base-065-jev-consent-2026-10-14.md` (ticket #7) names `refactor_extend`,
  `refactor_associate`, `refactor.associate`, `.metaform/refactor/` and the test path under `modules/refactor/`. I
  left that draft as written; read those names as the `source_placement` ones above when the two are merged.
- `docs/reference/metaform-mcp-server.md` lists every tool but never listed this module's; the
  `source_placement_*` tools are missing from it.
