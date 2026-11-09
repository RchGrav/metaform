# ModularShift — Round 4 review

Reviewed an immutable snapshot at `/tmp/ModularShift-blueprint-review-snapshot.md`, not an implementation. The shared draft is changing concurrently, so findings describe that snapshot. Used the BMad review skill with independent adversarial, edge-case and structural lenses. Overlap is retained as evidence of independent agreement. No main-spec edits were made in this review.

The immediate synthesis issues are the missing new-module publication path, contradictory external-role rules, and source-handle pinning versus destination grants. Proposed repairs below are recommendations, not owner decisions.

## adversarial

| Location | Trigger | Concrete repair | Consequence |
|---|---|---|---|
| B-2.2a / B-3.1 | Every slot needs placement, including existing external roles. | Require placement only for owned spatial slots; prohibit moving external roles through placement. | Valid external bindings are rejected or existing entities are moved. |
| B-2.3 / B-3.1 / example | No fixture or input schedule triggers the lever-use event. | Store starting state, typed stimuli, step origin and assertions. | Tests cannot distinguish an already-open door from one opened by use. |
| B-4.2 / MS-4 | Pinning actual source handles conflicts with forbidding authority cloning. | Pin capability roles/scopes; resolve fresh destination grants and record the mapping. | Release copies source authority or rejects valid destination handles. |
| B-3.5 / B-4.1 | Source hashes are described as the executable hashes release pins. | Record sourceHash, componentHash and their build association separately. | Hash comparisons fail or inspected source is unrelated to the tested executable. |
| B-3.1 / B-2.2 | The verb set requires existing content keys but cannot publish a newly written module. | Define component publication, verified manifest extraction and slot binding to the returned hash. | Agents can assemble existing assets but cannot complete a novel programmed feature. |
| B-2.2 / B-3.1 | links[] and independently written link steps can disagree. | Reference declared link ids from steps or derive steps from the canonical links. | The validated machine differs from the instantiated machine. |
| B-3.1 / B-3.4 | Link checks name WIT equality but omit explicit direction and cardinality checks. | Enforce outbound-to-inbound fan-out or exactly two two-way endpoints under W-5.4. | Equal-type links can violate W-5.4. |
| B-2.2 / blueprint.step | Voxel-only placement lacks orientation, scale and joint frames for imported objects. | Specify initial transforms and attachment frames through the selected interfaces. | Identical records admit geometrically different machines. |
| B-1.1 / D-B1 | The owner's expressly unsettled map reconsideration is described as settled. | Label agent-owned storage a proposal; distinguish ownership from physical storage. | A recommendation is mistaken for an owner decision. |
| B-3.4 | Rejection refers to absent B-2.5. | Restore the prohibition or replace the dangling reference. | Implementers cannot determine the rejection condition. |
| B-2.3 / blueprint.assert | Assertions require step, but assert accepts no step and n+2 has no origin. | Accept an observation step and define test-relative step zero. | The writer cannot populate timing; evaluators use different steps. |
| B-2.3 / B-3.5 / B-4.1 | Behavioral tests are repeatedly made the basis of generated-code safety. | Describe tests as functional evidence; cite limits, host imports and capability isolation for confinement. | Passing selected tests is mistaken for execution confinement. |

## edge-case-hunter

| Location | Trigger | Concrete repair | Consequence |
|---|---|---|---|
| B-2.2a / blueprint.submit | An external slot already has a transform. | Place owned spatial slots only; retain external transforms. | Valid external roles are rejected or moved. |
| B-2.2a / B-3.3 / MS-3 | An external role names a live-world entity during admin-world testing. | Separate test and destination bindings; supply an admin fixture matching the contract. | Testing uses an undefined cross-world link or acts on the live target early. |
| B-2.3 / blueprint.assert | The agent must author the assertion's required step. | Use assert(selectorRef, expected, step) with a run-relative origin. | The mandatory field cannot be written reproducibly. |
| B-3.1 / B-3.3 | A door assertion needs a use event with no stimulus operation. | Record fixture, endpoint, typed payload, relative step and initial state. | Event-driven code stays idle or depends on unrecorded actions. |
| B-2.2 / B-3.1 | Link steps and declarations disagree or omit each other. | Reference canonical link ids and materialize each exactly once. | Validation and construction produce different links. |
| B-3.5 / B-4.1 | Recorded source is compiled into a distinct executable component. | Record sourceHash and componentHash plus build association. | The hash reconciliation cannot compare like artifacts. |
| B-3.1 / B-2.4 | The requested feature needs a newly written module. | Publish compiled bytes and a verified manifest to obtain the content key. | The defined authoring path cannot create new behavior. |
| B-2.2 / MS-5 | set_param succeeds before a later build step fails. | Stage parameter effects until commit or restore their prior values. | A failed build changes global simulation settings. |
| B-3.4 | Prohibited content must be checked against absent B-2.5. | Restore or replace the missing clause. | A stated rejection rule has no definition. |

## structure

| Location | Trigger | Concrete repair | Consequence |
|---|---|---|---|
| ModularShift addition after section 6 | Requirements for a single operation are scattered after examples and decisions. | MOVE/MERGE MS-1/MS-2 into integrity, MS-3 into slots, MS-4 into permissions, MS-5 into submission and MS-6 into intent. | Readers must reconstruct the contract across passages. |
| B-2.2a and B-2.6 | Duplicate explanations obscure the slot contract. | MERGE owned/external role rules and allowed operations into one subsection. | Readers must reconstruct the contract across passages. |
| Section 6 | The heading combines decided recommendations and unresolved choices. | MOVE settled proposals to a decision summary and leave unresolved questions under Open decisions. | Readers must reconstruct the contract across passages. |
| B-2.1 and B-2.2 | Long field paragraphs hinder implementation lookup. | MOVE field definitions into tables with field, meaning, writer and reference. | Readers must reconstruct the contract across passages. |
| B-3.4 | The reference has no destination. | QUESTION the absent B-2.5 reference and repair its target. | Readers must reconstruct the contract across passages. |
| Section 5 | One paragraph mixes distinct structures the agent must write. | MOVE example into slots/manifests, links, assertions and build-step blocks. | Readers must reconstruct the contract across passages. |

## Additional roundtable reasoning

AcuteNitrate's argument about D-W10 conflates scope with data access. W-1.1 forbids the world system from reading the engineering functional map. A resolver spanning the world graph's own records need not read that map. The world server can reuse the technique or implementation with isolated data. Therefore W-1.1 does not force blueprint-only resolver scope, and D-W10 remains open.

Similarly, immutable content does not make an entity's module reference immutable. Changing one existing entity to reference a new module hash would leave other entities on the old hash. In-place updates may reasonably be deferred because state migration and incident-link validation need specification, but changing every shared instance is not an inevitable consequence under W-3.5.

A concrete next authoring contract is: allow a draft slot with a planned manifest; publish a compiled component and verify its actual manifest; bind the returned immutable component hash to that slot; reject submission until planned and actual manifests agree. This makes novel feature programming possible while retaining content-hash identity.

