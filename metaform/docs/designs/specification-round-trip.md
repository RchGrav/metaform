# Specification round trip

**State:** draft, 2026-11-06. Written by Claude (Opus 5.5) toward the founder's goal in `metaform/SPEC.md` R-1.2. The founder has not reviewed it. Choices marked **(agent's choice)** are the agent's.

## The goal

The founder: Topogee "not only being able to ingest a systems intent, but also being able to be a place where you construct and refine intent and then have a function to export it back into a specification, or even round tripping a specification in, first its intent and then its materials into categorical layers, it provides a structure of understanding and refinemenet which a roundtable could operate on together."

The round trip has four parts:

1. **In:** a specification's intent becomes the skeleton.
2. **Materials:** the rest of the specification goes into categorical layers.
3. **Refinement:** agents refine the map, alone or at a roundtable.
4. **Out:** the map is rendered back into a specification.

The skeleton holds functionality only. Detail lives in layers built around it (R-3.20). That separation is what lets each part change one thing at a time.

## Out: the export (built)

`node src/main.ts <folder> --specification [--layers <file>]` prints the map as Markdown. It is a CLI command, not an MCP command, because MCP is for data manipulation and reads (R-5.14 to R-5.16, the founder's rule of 2026-11-06). The code is `metaform/server/src/specify.ts`.

How it reads the map:

- **Order follows the role hierarchy** (R-3.13, R-3.20): Definitive, then Supportive, Notable and Divergent. After them come elements with an unrecognized role or none, then what the project relies on (`upstream`) and what relies on it (`downstream`). Within a group, elements are sorted by address. **(agent's choice)**
- **Each element is a heading:** its name and address, plus its technical name, status and URI where they are present.
- **Each want is one sentence** from the wants template of R-6.17: "`{this.address}` ({this.name}) requires `{other.address}` ({other.name}) in order to {why}, which {how}." Until the R-3.4 renames, `why` reads the stored `goal` and `how` reads the stored `function`.
- **Each layer record is one sentence** from its layer's `template` (R-6.16, R-6.20), with `{this.address}`, `{this.name}`, the record's `{name}` in a named layer, and each of its fields. A layer with no definition shows each record as written, so the export loses nothing. **(agent's choice)**
- **Fragments are fitted into sentences.** A trailing full stop is removed. A first capital is lowered when the next letter is lower case, so "Receive" becomes "receive" while "Jev" and "ACP" stay as written. **(agent's choice)**
- **Project-wide layers** at the root, such as the canonical map's `skills`, come first.

**Which layers make up the specification is a project detail, kept in the main database** (the founder, 2026-11-06). A user never names layers: the founder asked "how would they even know". The list is filled in, not typed:

- Taking a specification in records the layers its materials went into.
- An agent that builds a map registers the layers it writes for the specification.

The export reads the list and each layer's definition, and needs no argument. The current `--layers <file>` option is a stopgap, to be removed with the CLI redesign.

## What the first exports showed

The export was run on `metaform/intake-example.json` and on `metaform/metaform-canonical.json`, the earlier system's map of 67 elements. Rendering the data as sentences exposes problems the JSON hides:

- **Functions written as several sentences.** For example, `code.engine.workflow`: "which registers addressed prompts. Binds variables and element values. Persists call frames…". R-3.17 asks for one fragment. In a rendered sentence, the break is obvious.
- **Functions that are not verb phrases.** The intake example's function "Prepared mash data packets" renders as "which prepared mash data packets". R-6.17 asks for a verb ending in -s that agrees with "which".
- **Skills with no template render as raw JSON.** The system layers in `groups.json` need definitions with templates, such as "{this.name} offers the skill {name}: {description}.", before skills read well.
- **Supportive elements with no wants show only a heading.** That is the skeleton working as designed: what such an element is, beyond its connections, belongs in a layer.

So the export is also a quality check. A map whose export reads correctly obeys the grammar of R-3.17 and R-6.17.

## In: a specification's intent (designed, not built)

A specification is evidence of functionality, like code (section 1).

1. **Intake builds the skeleton.** The intake procedure (`metaform/Intake.md`) runs on the specification as its artifact. It records elements, roles and wants, with status `not_built` wherever the specification describes functionality that does not exist yet. No new procedure is needed.
2. **Materials go into layers.** For each registered layer, an agent reads the specification with that layer's `instruction` and writes records at the addresses each passage concerns, using the ordinary `add` command (R-5.28). The instruction is the inbound half of a layer, and the template is the outbound half.
3. **Material that fits no layer is listed, not dropped.** The list is the evidence for registering a new layer with `layer`. **(agent's choice)**

This needs no new MCP command. The CLI only starts the work; the intake agent writes through `project-map` as usual.

## Refinement (designed, not built)

The founder proposed that an agent owns its own map and brings others into a roundtable, as its head, to refine it (section 11).

- A seat orients by `goto` or by taking a ticket, never by reading the whole export.
- A change to one record changes one sentence of the next export, so the specification is never rewritten by hand.

## Round-trip check (designed, not built)

To test that the round trip holds, export a map, take the result in again, and compare:

- **The skeleton must match:** the same addresses, roles and wants.
- **Layers must match** record for record, for every layer whose template carries all of its fields.

A difference points at a template that drops a field, or at intake that misread a sentence. **(agent's choice)**

## For the founder

1. **Can seats write to the founder's map, or only propose?** This was asked earlier and is still open. It decides how refinement is built. Recommended: proposals that the founder accepts.
2. **The export format.** It is plain Markdown now, grouped by role. If exported specifications should look like `metaform/SPEC.md`, with numbered requirements and a status on each, that is a later step. Plain Markdown is recommended until a real round trip shows what the requirements form needs.
