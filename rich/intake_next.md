# Digital Typology

Oct 29, 2026 · @Rich Graver

## Goal

- Make a metaform that shows the functions of the Artifact Under Examination (AUE).
- Examine the AUE one element at a time.
- Find the function of each element.
- Use your knowledge of functions to select important element types.
- Do not select types by genre, medium, encoding, or style.
- Do not examine a subtype further if its difference does not change its function.
- Give each selected element a namespace address.
- Obey the namespace rules.
- For each Receiving Element (RE), record its Operative Purpose (OP) in a provider record under "providers", keyed by the Providing Element's (PE's) namespace address.
- Record the Providing Element's Encounter Function (EF) for that relationship.
- Make sure that the OP gives the RE's intended result.

## Prompt

The prompt is `{prompt}`. It can specify a target or a task.

- If no target is specified, use the context of the project folder.
- The prompt can request changes, corrections, an analysis of omissions, or new functions.
- Other requests can also change the process.

## Core Concepts

- **AUE (Artifact Under Examination):** The entity or entities that you examine, make, or use. Examples include photographs, contracts, stories, resale assets, and software. The work can include more than one artifact or project. An AUE is an asset if its use in that context gives it this role.
- **Provider Record:** A dictionary object in the Receiving Entity's (RE's) `providers` map, keyed by the Providing Element's (PE's) namespace address. The object contains the `ifd`, `op`, and `ef` for that encounter.
- **Element:** A part of an entity that can have a type name. A name alone does not make an element important. Some elements are immediately visible. Other elements are easy to find from the available evidence.
- **Entity:** An independent whole with its own identity. An element is a part of a whole. All entities are elements, but some elements are not entities. In one analysis scope, a part is an element. In another scope, the same part is an entity. When you examine a part and its internal elements, that part becomes an entity in this scope.
- **OP (Operative Purpose):** The intended result that the RE holds in its provider record. The PE gives an EF to help get this result. The OP gives the reason for this relationship.
- **EF (Encounter Function):** The mechanism, interface, relationship, or method through which an AUE or element gives the RE its intended result. The EF can be the function of an encounter or the encounter of a function. The PE has the EF, but the RE holds the EF in the provider record for that encounter. One PE type can give different EFs for different REs and OPs. Do not make one element-level EF record outside the provider records.
- **RE (Receiving Element/Entity):** The element, person, group, system, component, or other participant that holds an OP for a PE's EF. This receiver has the OP. This receiver holds the provider record.
- **CQU (Cestui Que Use):** The external RE whose intended result causes work to make this artifact type better. The CQU is a party type. Its provider record contains the OP for which the PE gives an EF. The CQU that causes the greatest improvement gives the best basis for selection.
- **PE (Providing Element):** The element that gives the EF for the result specified by the RE's OP. The PE is the other endpoint of the provider record.
- **AT (Artifact Type):** A category of artifacts with the same characteristics. One AT can contain more than one AUE of the same type. Examples include photographs, data objects, scripts, and templates.
- **NE (Notable Element):** A component, interface, or specification that gives an important external requirement or dependency. This requirement or dependency is necessary for the system or component to operate correctly.
- **DE (Defining Element):** The notable element whose removal would change the AUE's type. Its EF gives an external CQU the result specified by that CQU's OP. The DE gives the functional type of the AUE from its functions. Its function is independent of medium, encoding, genre, and style.
- **SE (Substantial Element):** An element whose EF helps the DE give the CQU the result specified by the CQU's OP. An element is substantial because of its intended contribution. This includes a contribution that works against the purpose or is weak. It also includes a contribution that you can replace or make better.
- **Parametric:** A quality or quantity that you can adjust. It has no type name of its own in the namespace scope of this AUE. It has no namespace address in this graph or process.
- **NS (Namespace Scope):** The scope of the Artifact Type. The listed base types are `code`, `document`, `media`, `data`, `collection`, `upstream`, and `downstream`.
- **IFD (Information Flow Direction):** The direction of the information or substance flow that gives the RE the result specified by its OP. The listed direction values are `sends`, `receives`, and `both`.

## CQU Examples

- **`media.photo` / seller:** Valid. The seller causes changes to the photograph to help sell the item.
- **`media.photo` / operator:** Invalid. The operator does the analysis for any artifact type. This role gives no information about this artifact type.
- **`code.[not a programming tool]` / developer:** Invalid. Do not select the developer only because the developer works on the code. Select this role only for an IDE or another programming tool.
- **`*` / End User:** Invalid. This term is too general. It gives no useful information about the party's purpose.
- **`document.story` / Reader:** Valid. The reader spends time on the story and wants a good story. This interest does not always involve money.
- **`media.photo` / buyer:** Invalid. The buyer examines the photograph. This evaluation does not change the photograph or make it better.
- **`media.photo` / insurance company:** Invalid. The insurance company records the photograph and does not want changes to it.
- **`media.photo` / social media poster:** Valid. The social media poster causes changes to the photograph or makes it better.
- **`media.photo` / blogger:** Valid. The blogger causes changes to the photograph or makes it better.

## IFD Examples

- **ifd1**
  - Scenario: The RE has an OP for the EF of a PE.
  - Requirement: `{ifd}` data to get the intended result.
  - IFD: `receives`
  - Reasoning: Parameters sent to the PE do not give the RE its intended result. The received data gives that result.
- **ifd2**
  - Scenario: The previous PE is now an RE. Its OP is to send a request record to a logger PE.
  - Requirement: `{ifd}` log data to get the intended result.
  - IFD: `sends`
  - Reasoning: The RE gets its intended result when it sends the log data.
- **ifd3**
  - Scenario: An email client RE uses an email server PE through SMTP and IMAP.
  - Requirement: Direction of the flow necessary for the OP.
  - IFD: `both`
  - Reasoning: The RE must send and receive email. One direction alone does not give the RE its intended result.

## Constraints

1. Use elements for different functional roles that the AUE actually has.
   - Give each role the most detailed type name that applies to other AUEs of this type.
2. If a more detailed functional mechanism exists, use its type name.
   - Do not use a general label instead.
3. Keep the namespace identity at the type level.
   - Put AUE-specific `ifd`, `op`, and `ef` data in provider records.
4. After the process and final inspection, try to make one record from provider records that have the same purpose.
   - Try to make one element from elements that have the same purpose.
   - Make sure that the result gives the artifact type.
5. Make a full map of the parent functions.
6. Include only functional element types in the graph structure.
   - Use provider records to give the functions of this AUE as a whole.
7. Select important notable elements.
   - Do not give an element special attention only because it can have a name.
8. Make each provider record apply to this AUE.
   - Record what this AUE does in its `op` and `ef` fields.
9. If the AUE contains a representation, record the function of that representation in the AUE.
   - Do not replace this function with the independent function of the real-world thing shown.
10. For each AUE, find its SEs.
    - Use the SE definition in the core concepts.
11. Do not stop intake or give it a quality grade.
    - Give a quality grade only to the resulting map.
    - Then change the intake as necessary for its context.

## CQU Entity Rules

1. Use CQU for the party whose benefit causes work to hold, change, or manage an artifact.
   - This party receives the consideration that causes work to add value.
2. Assume that conversion to a metaform has the purpose of making the artifact better.
   - List each CQU whose purpose causes changes or improvements.
3. Give priority to the CQU that causes the greatest improvement.
4. Do not select the person who requested the intake.
   - Do not use the general term "end user."
5. Make the CQU the receiver of the root provider record.
   - Record its OP as the intended result.
   - Record the PE's EF as the method that gives this result.
   - Make sure that every other provider record connects to a root provider record through its receivers.
6. If one person has more than one role, select the role that causes changes to the artifact.
   - Use the title of that role.
7. To select the CQU, find which party causes the greatest improvement in this artifact type.
8. Find the CQU from the artifact's type and functions.
   - Do not search for the CQU as a part inside the artifact.
9. Do not select the developer, the user, or the person who does the operation.
   - These general roles give no useful information about this artifact type.

## Namespace Rules

> **Note:** This model is a typological ontology, not a taxonomy. It has no filler levels such as `domain` or `class`. It sets no minimum or maximum number of namespace segments.

### Root Types

- `code`
- `document`
- `media`
- `data`
- `upstream`
- `downstream`
- `collection`

### Rules

1. **Readable names:** Make each namespace address readable as its type name.
   - Reverse the order of its segments.
   - Replace periods with spaces.
   - Make sure that the result is a noun phrase that practitioners understand.
   - Make sure that each child phrase ends with its parent's reversed name.
2. **Entity relation:** Every artifact is an entity. Every entity is an element. Some entities are not artifacts. Some elements are not entities.
   - The relation is: Artifacts are a subset of Entities. Entities are a subset of Elements.
3. **Proper nouns:** Use each namespace entry as a proper-noun name for a functional approach.
4. **Increasing detail:** Make each address more detailed from its root to its final segment.
   - Make each entry a type or functional part of its parent.
   - Do not add a segment for a difference that does not change the function.
5. **DE variants:** Include one or more entities with different OPs and EFs for the DE.
6. **Periods and underscores:**
   - Use periods between words when each prefix is a functional type. Use `code.engine.game` for game engine. Use `code.engine.physics` for physics engine.
   - Make sure that each prefix gives a type with practices that apply to its children.
   - Use underscores within one segment only when none of its words gives a correct prefix. Examples are `code.queue.dead_letter` and `data.bill_of_materials`.
   - Make sure that the reversed name is correct.
7. **Name length:** Set `name_length` to the number of final segments necessary for a short name that practitioners understand.
8. **General type:** Use the namespace address for the general type. Use the provider record for what this AUE does.
9. **Established terms:** Use established terms that practitioners use for this artifact type.
   - Obey this rule for elements, segment identifiers, compound tokens, and reversed noun phrases.
   - Do not use abstract pattern labels, invented synonyms, internal abbreviations, informal phrases, or marketing terms.
   - If no authoritative term exists, use the common noun for the function in normal practice.
   - Do not invent terms or change established terms.
10. **Corrections:** During each refinement or correction, examine every existing element and namespace path against these rules.
    - Do not exempt existing entries.
    - Record a correction for each error that you find.
    - Make each correction.
    - Include errors in terminology, invented words, and incorrect segments.
11. **Canonical name:** Put the canonical name in the `name` field.
    - Use the exact name in the project specifications.
    - If the project specifies no name, use the industry term.
12. **Writing style:** Write all metaform prose in ASD-STE100 Simplified Technical English. This requirement is mandatory.

### Reading Examples

- `code.loop.main` reads as "main loop program code."
- `code.bus.data.event` reads as "event data bus code."

### Validity Examples

- **`code.game`:** Invalid. The term *game* does not give a function.
- **`code.game.engine`:** Invalid. The address reverses to "engine game." This is a game about engines, not an established functional type. Its parent `code.game` is also incorrect.
- **`code.engine.game`:** Valid. A game engine gives a game its runtime functions. These include the main loop, rendering, input, and simulation. The type is independent of genre and content. *Game engine* is an established term.
- **`code.engine.game.fps`:** Valid. The example gives a different function.
  - Proof: first-person camera viewpoint and targeting reticle.
- **`code.engine.game.platformer`:** Invalid. This type gives the game's primary challenge and objective. It does not give a technical function.
  - Proof: spatial navigation and movement past environmental obstacles.
  - Note: This example shows that a mandatory distinction is between functions and other differences.
- **`media.image`:** Valid. Image is a permitted functional type under the media root.
- **`media.asset.image`:** Valid. An image is an asset when it has this functional role in an AUE.
- **`media.photo`:** Valid. A photograph has a DE and can have SEs.
  - A couple can be the DE, with the Eiffel Tower as an SE.
  - A car can be the DE in a street photograph.
  - A racing car can be the DE, with the racetrack as an SE.
  - The Grand Canyon can be the DE, with a distant person and mule as SEs.
- **`media.photo.scenery`:** Valid. The scene is the DE. The scene has a subject, but the photograph gives priority to the scene.
- **`media.photo.jpg`:** Invalid. The final segment gives an encoding.
- **`code.cpp`:** Invalid. The final segment gives a programming language.
- **`document.word.story.conflict`:** Invalid. The segment "word" gives an encoding. It does not give a functional approach at this namespace level.
- **`document.story.conflict`:** Valid. The address gives story conflict as a document element.

## Completion Condition

The task is complete when the final result is a minimal base shape of notable categorical elements of the artifact, joined by artifact-specific Operative Purposes, suitable for later expansion through project memory graph relations and other knowledge layers.

## Response Protocol

### Instructions

1. **ID:** Give the result an `"id"` when intake starts.
   - This process does not use the ID internally.
   - A later process can put the result in the `"canonical_input"` of `digital-typology-expand.xml`.
   - Its `"deep_result"` uses a matching `"ref"` to point to this result.
2. **Recording:** Record the result with the intake tools.
   - Record one object in each call as soon as you find its function and relationships.
   - Use the object fields specified by the schema below.
   - Do not give the schema as an output document.
3. **Cleanup:** After step 12, keep only the final combined elements and provider records.
   - Keep the root element list small, broad, and shallow.
   - Put subparts under their important parent elements.
   - Remove subparts that no longer have independent root entries.
   - Keep each subpart's individual function as an element in a provider record under its parent.
4. **Element identity:** Use `namespace_address` as the element identity.
   - Do not use the readable name as an element reference.
   - For example, use `code.registry.tool` to refer to that element. The name "tool registry" alone is not a correct reference.
   - Make sure that every element reference matches an existing namespace address.
5. **Roles:** Use an element for every namespace record.
   - Give each element inside the AUE exactly one role: `DE`, `SE`, or `NE`.
   - Give an external CQU the role `CQU`. Do not also give that CQU a DE, SE, or NE role.
   - `PE` is an endpoint in a provider record, not a role attribute.
   - Use the same element record when it is an RE in one relationship and a PE in another.
6. **Provider records:** Connect each RE and its OP to the PE that gives the applicable EF.
   - Include `"ifd"`, `"op"`, and `"ef"` in every provider record.
7. **Direction prefixes:**
   - Add `"upstream"` before the namespace address of an upstream requirement.
   - Add `"downstream"` before the namespace address of a downstream CQU or dependent.
8. **References:** Add provider-record `"refs"` that help later agents find important project resources.

### Method

Record the deliverable with the intake tools.

1. **Examine the code.**
   - Write OP and EF fields in ASD-STE100 Simplified Technical English.
   - Do not examine only the README.
   - Find which functions exist.
   - Find which intended functions do not yet exist.
   - These instructions are mandatory.
2. **Find errors.**
   - During the function analysis, look for errors and differences between the documentation, specifications, and code.
   - Do not assume that one source is always correct.
   - Record clear concerns that you find. Attach each finding to its element type. Include references to the evidence.
   - If intended functionality is absent or not yet built, mark its intent by labeling it `"not_built"`.
   - If an item appears unrelated, give it the status `"exclude"` for examination.
3. **Examine each AUE.**
   - Find its AT, DE, SEs, and NEs.
   - Find the OP and EF relationships that make its functions different.
   - Find the CQU's OP and the EF of the DE that gives the CQU its intended result.
   - Use `"downstream.cqu.*"` for the CQU namespace.
   - Put AUEs of the same AT in one group.
   - Use these relationships to give an agent a useful command.
   - If the input is a folder or collection, examine every member before you complete the groups.
   - Put members in one group only when their shared functions give the same command at the AT level.
   - Keep references to individual members where necessary.
4. **Make CQU entries.**
   - For each AT, make a CQU namespace entry.
   - Add a provider record under `"providers"` keyed by the PE's namespace address. Set `"op"` to the CQU's OP from step 3. Set `"ef"` to the EF from step 3. Set `"ifd"` to the information flow direction.
   - Add references to the members. For each member reference, set `"key"` to `"path"`. Set `"value"` to the member's relative path.
   - Look for functionality not yet built and set `"status"` to `"not_built"`.
5. **Examine the DE as an RE.**
   - For each AUE and each AT, examine the DE as an RE.
   - Find the requirements and dependencies necessary for the DE's EF.
   - Find the other elements whose EFs supply them.
   - Keep the DE as the PE for the external CQU where that relationship exists.
   - If another element holds an OP, examine that element as an RE. Do not make a second namespace record for it.
6. **Make provider records.** For each EF that gives an RE its intended result, make a provider record in the RE's `"providers"` map, using the PE's namespace address as the key.
   - Set `"op"` to the OP statement. Give the intended result directly.
   - Set `"ef"` to the PE's EF for this relationship.
     - Start `"ef"` in the active voice with a third-person singular verb in the present tense that ends in "-s" or "-es".
   - Set `"ifd"` to the primary information flow that gives the RE its intended result.
     - Use `"sends"` for flow from the RE to the PE.
     - Use `"receives"` for flow from the PE to the RE.
     - Use `"both"` when both directions are equally necessary.
   - Record each element and provider record as soon as you find its function and relationships.
   - Record one object in each call.
   - Do not wait until the full map is ready.
   - Look for functionality not yet built and set `"status"` to `"not_built"`.
7. **Follow the chain.** Start with the element in the first OP. Do this process again for that element and its dependencies. Then go to the next element. If an element has requirements or an OP of its own, examine that element as an RE.
8. **Find supporting OPs.** For each element, find the OPs necessary for its own EF. Include requirements from other parts of the AUE and from outside the AUE. Make sure that each OP connects through its receivers to the external CQU's OP.
9. **Continue the analysis.** Continue until you find no more of the following:
   - OPs without a result
   - NEs necessary to understand the AUE

   Do not include parametric elements as NEs. Do not give a namespace address to an adjustable quality or quantity without its own type name. Obey this restriction regardless of how many parameters exist.
10. **Check for gaps.** After the analysis, do the initial examination in step 1 again.
    - Find each function that the analysis did not reach.
    - For each function, find the RE whose OP gets its intended result from that function.
    - Record the provider record.
    - If the function is only a part of an existing function, include it in the parent's provider record.
    - Make sure that no function of the AUE is absent from the map.
11. **Combine subparts.** Where possible, put PE subfunctions in the RE's parent function through their shared integration provider records.
    - Make one larger functional element from subparts that share the same provider record. Do this only when the parent's operative purpose (OP) shares each subpart's active goal.
    - Otherwise, keep the subpart as an independent functional element.
    - Keep each included subpart's purpose as more detail of the parent's purpose.
    - Record that purpose in a provider record under the parent.
    - Let the provider record give the combined encounter.
    - Do not remove functions during this operation.
12. **Final review.** Read the full recorded map. Compare it with the artifact. Compare it with these instructions.
    - Correct the errors.
    - Make one record from records that have the same purpose where possible.
    - Make one element from elements that have the same purpose where possible.
    - Add necessary functions and relationships that are absent.
    - Then complete the intake.
