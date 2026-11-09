---
id: digital-typology
version: "3.1"
title: Digital Typology Intake
contracts:
  document_schema: metaform.schema.json
  tool_registry: mcp-tools.proposed.json
---

# Digital Typology Intake

Map the functional shape of an Artifact Under Examination (AUE) into a nested typological ontology[cite: 1]. Perform an element-by-element trace focused strictly on observed functionality—avoiding genre, medium, encoding, language, and style[cite: 1]. Do not perform a deeper intake based on variants that do not describe functionality on the leaf[cite: 1].

Process entities one at a time by standing at a `local_address`, identifying every `remote_address` it encounters or depends on, and recording each relationship in the `local_address`'s `wants` dictionary using `why`, `how`, and `direction`[cite: 1].

## Target Prompt

Prompt: `{prompt}`

The prompt may state a target or a task[cite: 1]. Assume the target is the current project folder context if not stated otherwise[cite: 1]. Prompts may refine the process, construct correction layers, analyze blind spots, or define feature enhancements[cite: 1]. Intake is never gated or judged; only the resulting map is evaluated and refined contextually afterward[cite: 1].

## 1. Core Concepts

* **AUE (Artifact Under Examination):** The entity (thing or things) being examined, created, or used—including photographs, contracts, stories, resale assets, and software[cite: 1]. All artifacts are entities, and all entities are elements (Artifacts are a subset of Entities, which are a subset of Elements)[cite: 1]. Whether an component is viewed as a passive element or an active entity depends on your current scope: the moment you zoom into a component to examine its internal composition, it becomes the active entity (`local_address`) with its own subordinate elements[cite: 1].
* **AT (Artifact Type):** A general category or classification that groups individual artifacts based on shared functional characteristics (e.g., photos, data objects, scripts, templates)[cite: 1].
* **Element Filter:** An element is any nameable part of an entity as a type; however, just because an element can be named does not mean it is interesting, remarkable, or deserving of special attention[cite: 1]. Only map elements that must be named to understand the artifact's functionality[cite: 1].
* **Local Address:** The namespace address of the element currently under active examination. The Local Address owns the `wants` dictionary and holds the `why` for every encounter it initiates or requires[cite: 1].
* **Remote Address:** The namespace address of an element that the Local Address encounters or depends on to fulfill a `why`. Recorded as the key inside the Local Address's `wants` dictionary[cite: 1]. Both endpoints must resolve to actual elements in the project namespace[cite: 1].
* **Want:** A directed encounter record stored inside the Local Address's `wants` dictionary, keyed by the `remote_address`, containing `why`, `how`, and `direction`[cite: 1].
* **Why:** The active **goal** held by the Local Address—what the Local Address intends to accomplish through its encounter with the Remote Address[cite: 1].
* **How:** The **function** of what is delivered[cite: 1]. Depending on the contextual understanding of the artifact, this may be understood as the *function of an encounter* or the *encounter of a function*[cite: 1]. It is the mechanism, interface, relationship, or method through which the Remote Address satisfies the Local Address's `goal`, explaining how the effect is encountered, used, or experienced[cite: 1]. Because a single Remote Address may satisfy different Local Addresses through different functions, record the encounter-specific `function` inside the Local Address's `want` record rather than as a static property on the Remote Address[cite: 1].
* **Direction:** The direction (`outbound`, `inbound`, or `two-way`) of the substantial exchange relative to the Local Address that satisfies its `why`—strictly excluding the request parameters, invocation call, or delivery receipt[cite: 1].
  * *Inbound Example:* `code.loop.main` wants `code.registry.tool` -> **`inbound`**. Passing a lookup key is merely the request; receiving the resolved tool schema is the substance that satisfies the main loop's goal[cite: 1].
  * *Outbound Example:* `code.bus.data.event` wants `code.queue.dead_letter` -> **`outbound`**. A delivery receipt is incidental; sending the undeliverable event substance into quarantine satisfies the event bus's goal[cite: 1].
  * *Two-Way Example:* `code.client.email` wants `upstream.server.email` -> **`two-way`**. An email client requires both sending outbound messages and receiving inbound messages to satisfy its goal[cite: 1].
* **Roles (`Definitive`, `Supportive`, `Notable`, `Divergent`):** Every element inside the AUE carries exactly one role: `Definitive` (`DE`), `Supportive` (`SE`), `Notable` (`NE`), or `Divergent`[cite: 1].
  * **Definitive (DE):** The notable element of this AUE whose loss would prevent the AUE from remaining the same type[cite: 1]. Its function services the `why` of a `CQU` outside the AUE and names the functional type of the AUE independent of medium, encoding, genre, and style[cite: 1].
  * **Supportive (SE):** An element inside the AUE whose function helps the `DE` serve the `CQU`'s `why`[cite: 1]. It counts as substantial because of what it is meant to contribute to the AUE, even when that contribution is subversive, weak, replaceable, or should be improved[cite: 1].
  * **Notable (NE):** A component, interface, or specification inside the AUE that defines an essential demand or requirement—highlighting what the AUE explicitly expects, needs, or depends on from its environment to operate successfully[cite: 1].
  * **Divergent:** An unaligned, weak, or redundant element captured during intake that deviates from the core architecture. This role must be investigated on the purpose it is serving, and either be realigned as repaired or improved, or ejected.
* **CQU (Cestui Que Use):** The explicit external party types (`downstream.*`) for whose benefit the AUE is held, modified, and managed—the parties that hold an objective purpose for this type of object and drive improvements to it[cite: 1].
  * Enumerate every CQU whose purpose drives changes or improvements to the artifact; the CQU that drives the most improvement yields the strongest functional inference[cite: 1].
  * Deciding on the CQU requires inferring it from what the artifact is; do not look for the CQU inside the artifact[cite: 1].
  * When one person holds several roles, name the specific role title that drives changes to the artifact[cite: 1].
  * *Valid CQUs:* `downstream.seller` for `media.photo` (stages/presents the photo to facilitate a sale)[cite: 1]; `downstream.social_media_poster` or `downstream.blogger` for `media.photo` (drives edits/improvements to the photo)[cite: 1]; `downstream.reader` for `document.story` (invests time to read a good story)[cite: 1].
  * *Invalid CQUs:* `developer` (unless the AUE is actually `code.ide` or a programming tool), `end_user`, `operator`, or the person requesting the intake (these could be named for every artifact and yield zero unique reasoning)[cite: 1]; `buyer` or `insurance_company` for `media.photo` (judging or recording a photo does not change or improve it)[cite: 1].
* **Parametric:** A tunable quality or quantity that does not carry a distinct functional name in the namespace of the AUE[cite: 1]. Never assign a namespace address to parametrics, no matter how many exist[cite: 1].

## 2. Load-Bearing Constraints

1. **General Address, Specific Want Record:** The namespace address names the reusable functional *type* (keeping namespace identity general), while the `want` records (`why`, `how`) and native knowledge layers state what *this specific AUE* actually does in its own particulars[cite: 1].
2. **Function of Representations:** Where an AUE or element represents something in the real world (such as a subject in a photograph or a character in a story), describe the function of that *representation within the AUE* rather than substituting the independent real-world functionality of the thing represented[cite: 1].
3. **Discrete Reusable Types:** Elements represent discrete functional roles actively instantiated by the artifact, named at their most specific reusable type level[cite: 1]. Never use vague top-level labels where a specific functional mechanism exists[cite: 1].

## 3. Namespace Rules

Tool selectors use flat project-relative dotted addresses (e.g., `code.bus.data.event`)[cite: 1]. The storage engine persists them as nested objects under the project root[cite: 1].

**Valid Root Scopes:** `code`, `document`, `media`, `data`, `collection`, `upstream`, `downstream`[cite: 1].

1. **Address Identity vs. Canonical Alias (`name`):** An element's identity is its namespace address, never its readable name alone[cite: 1]. The dotted namespace address defines *what the element functionally is* using standard industry practitioner nouns—never coin, invent, or adapt bespoke terms[cite: 1]. The `name` field holds the canonical project-specific name or internal alias used in the project specifications or source (or the standard industry term if no project alias exists)[cite: 1].
2. **Reversibility & `technical_name`:** Reversing the segments of a namespace address (replacing periods with spaces) must read properly as a well-understood noun phrase where children take their parent's name as their last name[cite: 1]. Narrow from trunk to leaf: every child segment must be a subtype or functional part within its parent scope[cite: 1]. Set `technical_name` to the well-understood practitioner short name derived from the leaf segments; it must exactly match the same number of leading words of the reversed, space-separated namespace address[cite: 1]:
   * `code.bus.data.event` (`technical_name: "event data bus"`) -> the leading words of the reversed address `"event data bus code"` (`code` is root scope)[cite: 1].
   * `code.loop.main` (`technical_name: "main loop"`) -> the leading words of the reversed address `"main loop code"`[cite: 1].
   * `code.engine.game.fps` (`technical_name: "fps game engine"`) -> the leading words of the reversed address `"fps game engine code"`[cite: 1].
3. **Pure Functionality:** Never include encodings (`media.photo.jpg`, `document.word.story.conflict`), languages (`code.cpp`), or non-functional genres (`code.engine.game.platformer`) in the namespace path[cite: 1].
   * *Valid Examples:* `code.engine.game` (provides the runtime loop, rendering, input, and simulation independent of game content)[cite: 1]; `code.engine.game.fps` (first-person camera viewport with targeting reticle is a distinct technical functionality)[cite: 1]; `media.photo` (has a DE subject and optional SE supporting elements, such as a couple [DE] at the Eiffel Tower [SE], or the Grand Canyon [DE] with a rider and mule [SE])[cite: 1]; `media.photo.scenery` (encounter function where the scene itself is the DE focus)[cite: 1]; `media.asset.image` (images acting as functional asset elements inside an AUE)[cite: 1]; `document.story.conflict`[cite: 1].
   * *Invalid Examples:* `code.game` (not a function)[cite: 1]; `code.game.engine` (reverses to "engine game", a game about engines)[cite: 1]; `code.engine.game.platformer` (defines a gameplay challenge/objective rather than a technical mechanism)[cite: 1].
4. **Segment Joining:** When a leaf is a functional variant of its parent type (`code.engine.game`, `code.engine.physics`), separate segments with periods so every prefix remains a complete type that passes its practices to its children[cite: 1]. Join words with underscores in one segment *only* when none of the individual words forms a valid standalone functional prefix (`code.queue.dead_letter`, `data.bill_of_materials`), ensuring the reversed name still reads naturally[cite: 1].
5. **Upstream & Downstream Prefixes:** Prepend `upstream.` to the namespace address for external prerequisites/providers outside the AUE, and `downstream.` for external consumers (`downstream.*`) or dependents[cite: 1].
6. **Source Entry Point (`uri`):** Set one relative `uri` on each element to identify the primary entry point for its functionality[cite: 1]. Do not enumerate every contributing file on the element; keep additional evidence references and collection-member paths in the native knowledge layers[cite: 1].
7. **Continuous Auditing:** During any refinement or correction pass, audit all existing namespace paths against these rules and remediate any coined words, non-standard terms, or improper segmentation[cite: 1].

## 4. MCP Interface Protocol

Interact with the graph one `local_address` at a time using top-level keys: `add`, `update`, `delete`, `orphaned`, or a bare address query[cite: 1]. Do not invent extra `data`, `layers`, or `properties` wrappers[cite: 1].

**Query an Element:**
```json
{"code.bus.data.event": {}}
```
*Response:*
```json
{
  "code.bus.data.event": {
    "technical_name": "event data bus",
    "name": "pulsar router",
    "role": "Supportive",
    "uri": "./src/core/event_bus.c"
  }
}
```

**Add or Update an Element & Its Wants:**
Every `remote_address` referenced in `wants` must resolve to an existing element in the selected project[cite: 1]. Do not copy remote element properties inside a `want` record[cite: 1].
```json
{
  "add": {
    "code.engine.game.fps": {
      "technical_name": "fps game engine",
      "name": "idtech core",
      "role": "Definitive",
      "uri": "./src/engine/fps_core.c",
      "wants": {
        "code.bus.data.event": {
          "why": "Receive player input and collision telemetry for frame simulation.",
          "how": "Dispatches subscribed runtime event streams.",
          "direction": "inbound"
        }
      }
    }
  }
}
```

**Remove a Property:**
```json
{
  "update": {
    "code.bus.data.event": {
      "role": null
    }
  }
}
```

**Delete a Relationship (Orphaning):**
Remove a specific `remote_address` from a `local_address`'s `wants` list before deleting the remote element[cite: 1]:
```json
{
  "delete": {
    "code.engine.game.fps": {
      "wants": ["code.bus.data.event"]
    }
  }
}
```

**Scan for Orphans:**
Queries all elements with zero incoming `wants` references[cite: 1]. Orphan results do not instruct you to delete them (root `downstream.*` nodes naturally have no incoming `wants`)[cite: 1]:
```json
{"orphaned": {}}
```

**Delete an Element:**
An element can only be deleted after it has no incoming `wants`[cite: 1]. If still referenced, the engine returns `"status": "error"` with a `"remediation"` command showing which Local Address still holds a `want` for it[cite: 1]. Always inspect the remediation before submitting it[cite: 1]:
```json
{"delete": {"code.bus.data.event": {}}}
```

## 5. Intake Method

Record each element and `want` record with the working tool as soon as it is reasoned, one `local_address` at a time, rather than holding the map until the end[cite: 1].

1. **Survey the Artifact (Load-Bearing):**
   * Examine the actual artifact material or implementation—never rely solely on READMEs or summaries, as you must observe what is actually present and what is not yet built[cite: 1].
   * Be vigilant for drift or apparent errors between documentation, specifications, and implementation in either direction[cite: 1]. Where intended functionality is absent, mark status as `un_built` and record reasons to investigate with supporting references in the native investigation knowledge layer[cite: 1].
   * **Collections / Folders:** If the intake receives a folder or collection, survey every member before finalizing grouping[cite: 1]. Observe each member's Artifact Type (`AT`), its `DE`, `SE`, and `NE` elements, and its functional relationships[cite: 1]. Group only members whose shared functionality supports the same AT-level imperative, retaining individual member paths (`"path": "[relative path]"`) in the relevant knowledge/reference records[cite: 1].

2. **Anchor the CQU(s) and Defining Element (DE):**
   * For each Artifact Type (`AT`) group, identify the `DE` and enumerate the external `downstream.*` party types that drive improvements to the artifact[cite: 1].
   * `add` the `DE` at its functional namespace address (`role: "Definitive"`, `technical_name`, `name`, `uri`)[cite: 1].
   * For each identified CQU, `add` its `downstream.*` element as a `local_address` and record a `want` pointing to the `DE` (`remote_address`), setting `why` to the CQU's active objective, `how` to the DE's overarching encounter function, and `direction` (`outbound`, `inbound`, or `two-way`)[cite: 1]. Every downstream `want` in the graph will trace back to these root CQU records[cite: 1].

3. **Trace Local-to-Remote Encounters:**
   * Start with the `DE` as your current `local_address`[cite: 1].
   * Decompose what the current `local_address` needs, wants, or encounters from other elements inside the AUE (`SE`, `NE`) or outside it (`upstream.*`) in order to deliver its own function[cite: 1]. Ignore parametrics and unremarkable parts that do not need to be named to understand the artifact[cite: 1].
   * For each notable encountered element (`remote_address`):
     1. `add` the `remote_address` at its reusable type-level namespace address (`technical_name`, `name`, `role`, `uri`) if it does not already exist[cite: 1].
     2. `update` the `local_address` to add the `want` record keyed by `remote_address` with its AUE-specific `why`, `how`, `direction` (`outbound`, `inbound`, or `two-way`, excluding request parameters and delivery receipts)[cite: 1].
   * Move to the next encountered element that bears its own functional requirements (`why`) and repeat this step, treating it as the new `local_address` without creating duplicate namespace records, until no unsatisfied `why`s or unmapped `NE`s remain[cite: 1].

4. **Completeness Pass Against Survey:**
   * Return to your Step 1 survey to ensure no aspect of the AUE's functionality was left out[cite: 1].
   * For any functionality the trace did not reach, find the `local_address` whose `why` it serves and record the `want` relationship[cite: 1]. Where an unreached part is merely a minor sub-part of a functionality already named, let the existing parent's `how` description state it rather than creating a redundant element[cite: 1].

5. **Anneal and Encapsulate:**
   * Aggregate remote sub-functions into their parent element whenever a parent's purpose (`why` and `how`) can completely carry the sub-part's purpose[cite: 1]. Encapsulate a sub-part *only* when the parent's purpose can carry it; otherwise, keep it as an independent functional element[cite: 1].
   * Preserve the absorbed sub-part's contribution and native knowledge on the surviving parent[cite: 1].
   * Remove obsolete `want` relationships (`{"delete": {"local.address": {"wants": ["remote.address"]}}}`), check `{"orphaned": {}}`, and delete the absorbed element only after it has zero incoming `wants`[cite: 1].

6. **Final Proof and Audit:**
   * Read the entire recorded map back as a whole and check it against both the artifact and this specification[cite: 1].
   * Verify that all `wants` resolve to actual provider elements and that every namespace address strictly obeys the Namespace Rules (reversibility, `technical_name`, standard terminology, zero encodings/genres)[cite: 1].
