# ModularShift: build receipts and dependency validity

**Status:** Proposed. These rules refine blueprint submission and release. They add no functional-map namespace or core content kind.

**MS-1 Evidence identifies an exact build.** Submission returns a server-issued build receipt containing the blueprint id/revision, slot-to-entity bindings, instantiated assembly id, world id, module/asset/manifest hashes and relevant world configuration. A test result names that receipt, the acceptance criterion id, fixture/starting state, stimuli, observations and verdict. Merely storing assertions or claiming tests passed does not establish a tested feature. Release requires passing evidence for every required criterion on the same build. A rejected type-mismatched link proves a validation rule, not that a valid machine works.

**MS-2 Dependencies cannot silently change.** Validation records a dependency fingerprint: pinned WIT package definitions, archetype manifests, referenced graph revisions, hashes and relevant world settings. Submission rechecks it. A changed dependency returns a diagnostic identifying the changed references; the agent rereads those records, revises, validates and retests. A module, manifest, binding, assertion or relevant world-setting change invalidates dependent evidence. Historical receipts remain inspectable. An agent cannot replace provenance hashes in an immutable submitted revision; it creates and tests a successor revision.

**MS-3 Local and external ownership are explicit.** A planned slot is either owned content to instantiate or an external role requiring a binding. An external binding records its world/entity id and expected manifest contract. Missing bindings are permitted in drafts and block building. An assembly copies owned content only. On release, internal endpoints, joint targets and intent attachments are remapped to destination ids; external roles are explicitly rebound and revalidated against destination manifests. Two instantiations receive separate entity-id mappings. Referencing an entity never makes it part of the release unit.

**MS-4 Ownership grants no world authority.** Owning an agent map or blueprint permits editing that artifact. It grants no handle to actuate referenced entities or alter volumes. Required W-7.4 handles are declared dependencies and must be granted within W-9.6. Instantiation and release never serialize or clone authority. Release may be performed by any holder of the release capability, held by the admin by default. Current grants and destination bindings are checked again at release.

**MS-5 Submission is retryable and staged.** Submission accepts a request id; retrying the same request returns the prior receipt rather than creating duplicate entities. The server resolves all slots and links before activating any feature module. Failure returns diagnostics and removes or leaves explicitly inactive only that submission's staged content, without undoing unrelated world edits. The response identifies staged resources requiring cleanup. Build validation respects W-2.3: an admin void without a generator cannot receive chunk writes. Describing voxel data as an entity component cannot bypass this rule.

**MS-6 Intent remains attributable.** Every referenced intent is pinned by record id and revision and retains its author and original text. Agent interpretation and assumptions are attributed additions, never replacements for user intent. Acceptance criteria reference the intent clauses they demonstrate; built entities and released assemblies retain the applicable intent references (W-5.5). An unresolved ambiguity that changes observable behavior or required authority blocks readiness. Routine implementation choices may proceed with a recorded rationale.

These checks belong to the server. The agent's write loop is: preserve intent → declare criteria → draft slots, ports and links → validate → instantiate → exercise and observe criteria → revise/retest as necessary → hand the exact tested build to a release-capability holder. The loop requires no particular MCP implementation and does not settle perception or general context delivery in D-W7/D-W10.

## Inspectable acceptance cases

These are proposed implementation checks, not claims that a server exists or has passed tests.

| Case | Required result |
|---|---|
| Submit a controller/door blueprint twice with the same request id | One staged assembly, same binding map and receipt |
| Instantiate it under a new request id | Distinct entity ids; each link resolves within its own assembly |
| Change its module after door tests pass | Old evidence cannot qualify the changed build for release |
| Change an external target manifest after validation | Build reports the changed dependency and creates no active partial machine |
| Release with an unresolved external target | Rejected with that role identified; unrelated entities are not copied |
| Clone a blueprint requesting an actuator handle | The clone has a request, not a grant |
| Write voxels into an admin void without a generator | Rejected under W-2.3 |
| Test only rejection of mismatched port types | Structural negative case passes; door-opening behavior remains unproved |
| Agent refines user intent | Original author/text/revision survives; interpretation is separate |

W-5.4 establishes structural compatibility; W-5.5 supplies behavior to demonstrate. Neither proves that a later module hash or differently bound destination behaves like the tested build.
