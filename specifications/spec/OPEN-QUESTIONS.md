# Open questions

Only questions that depend on Rich's intent are open. Every question with one technically correct answer is settled by its recommendation, which the build follows as written.

## Open

**D82. Submissions that break the shape.** The Canonical Intake says intake is never gated or judged. A submitted join whose provider is its own receiver, or whose provider is a subtype, cannot exist in the acyclic mesh. Store it as given for a later correction layer or grading layer to deal with, or refuse the submission?
Recommendation: store it as given. A refusal makes the agent loop and retry, and the intake is never gated. Reads show it like any other join, and a correction layer removes it.

## Answered

**D81. intake_submit.** It has its own input schema, the metaform's general data pattern, with field names and nesting taken from the Canonical Intake. The agent submits against it once. The intake text is served unchanged with one module line after it, and can change freely as long as its structure keeps that pattern.

**D10. One element per address.** An element is its namespace address, so a project has one element per address. This replaces the earlier recommendation.

**D60. Origins.** The origin records the commit hash as its base. Diffs are intermediary checkpoints between real commits, only for worktrees and agent work, made with git diff even outside a repository. Collecting a worktree makes the diff and either removes the worktree or leaves it.

**D66. History and provenance.** Chassis functions. Provenance tracks one record per layer and the intermediary diffs, nothing else.

**D69. Stacking commands.** Dropped.

**D75. Properties from the intake.** The intake produces no properties. Properties come from knowledge layers.

**D1. Root types.** code, document, media, data and stakeholder, as in the current Canonical Intake. Exterior is gone.

**D2. Subtypes.** A subtype never has its own purpose. A part with its own purpose is not sharing the join, so it is its own element.

**D9. C(T).** The theory behind how Metaform works. It describes no mechanism and no stored field.

**D26. A directly run wheel's data.** A subfolder of ~/.metaform per wheel name and version.

**D27. Installing a wheel.** Its data can be pulled into the main folder, each metaform arriving as its own. Nothing is merged.

**D59. Mapping a worker's folder.** The orchestrator runs `metaform set --modules workflow,memory folder=<path>` before the worker starts. The setting formerly called `--commands` is `--modules`. This per-folder surface is the closest thing Metaform has to a nonce.

**D77. Correction and knowledge layers.** Correction layers always beat knowledge layers and sit underneath them. A knowledge item left with nothing to attach to is orphaned: kept, and no longer shown.

**D23 and D76. Import.** Everything exported carries its unique id, and importing something that already exists does nothing. Agent work brought in is a new layer. Backup and restore is separate. A project can have several metaforms, each with its own layers; one is active, and starting over creates a new, empty metaform while the old one is kept.

**D7 and D49. Encounters.** Every encounter is a function or a property. A join is always a function. A property is its own record, attached only to an element, transitive up to the leaves and visible down to the trunk. A property at a prefix with no element goes on an element the layer creates there. MAP-022, STORE-039.

**D70. Toggling layers.** Layers are tagged, listed and toggled. The toggled set for a folder is the `--layers` setting, which names layers or tags. LAYER-019, CLI-033, STORE-038.

**D8 and D54. How the intake result reaches the store.** The intake agent completes the whole method, including annealing, then submits once through the `intake_submit` tool. Its inputs mirror the intake schema's fields. The tool validates the submission and stores it as the intake layer in one write, so an intake is never half written. The intake text's response protocol will say to submit the final shape through `intake_submit`; the method stays word for word.


## Settled by recommendation

**D3. Can a subtype own joins after annealing?** (MAP, STORE)
Recommendation: no. Its joins lift to the parent when it is annealed. A subtype is reachable only through its join and is never a root, so it cannot be a receiver in the graph.

**D4. Can one element be a subtype in two different joins?**
Recommendation: no. A subpart is absorbed only when one parent's join already carries its purpose. A part that serves two joins has a role of its own in the map and stays a root element. This also settles whether a subtype can share an address with a root element: it cannot.

**D5. Can a subtype hold subtypes of its own?**
Recommendation: no, one level. A subtype lives inside a join, not inside an element. This can be relaxed later without breaking stored maps.

**D6. Several VEs.** When the intake names more than one VE, is one recorded as primary?
Recommendation: yes, a primary flag on the VE element, because the VE that drives the most improvement gives the best inference and agents need to know which one it is.

**D11. A join whose receiver and provider are the same element.**
Recommendation: no. A join is one receiver's purpose served by a different provider, and a self join is a cycle, which the mesh cannot express.

### Layers

**D12. Layer properties.** Are mutable, hideable and transitive fixed per kind of layer, or declared by the module for each layer it creates?
Recommendation: declared by the module when it creates the layer, fixed after that. The chassis applies them uniformly, which is what lets modules compose.

**D13. Hiding follows dependencies (REQ-124).** Does hiding a layer hide the layers built from it?
Recommendation: yes.

**D14. Where a layer's sources are recorded.** Hiding by dependency and re-examining dependents after a correction both need to know which layers a layer was built from.
Recommendation: the layer's one record lists its source layers and the revision of each it read.

**D15. Provenance for a layer written by a person or by a plain import.** It has no model, prompt or role.
Recommendation: the same record, holding who or what wrote it, with model and prompt empty.

**D16. A second run of the same workflow.** Does it add to the existing layer or create a new one?
Recommendation: a new layer. Provenance records how a layer was created, and a second run is a second creation.

**D17. Select and mask on a join.** Does a join have its own, or use its receiver's?
Recommendation: its receiver's, since the receiver owns the join.

**D18. Memory for a name that is not in the map.** The reference memory server's create operation makes new entities.
Recommendation: allowed. It creates a new element in the memory layer, which a layer may do.

**D19. Promoting a proposed element into the map.** How does a B verdict from a challenge become part of the map?
Recommendation: through a correction, as a new revision of the map layer.

**D20. Hiding one item inside a layer.**
Recommendation: no, whole layers only. Hideable is a property of the layer.

**D21. The shape of a layer's variable.** Does each layer declare the fields of its one variable, such as imperative, why and evidence for a best practice?
Recommendation: yes. Readers and exports then know what every item holds.

**D22. A module item about no map node.** The template's greeting history is the example.
Recommendation: the module's layer creates an element of its own to attach to.

### Storage

**D24. Data written by the current chassis branch.**
Recommendation: dropped. Before 1.0 the contract changes freely and nothing real is stored yet.

### Chassis, modules and wheels

**D25. A module place per project (REQ-035).**
Recommendation: none, since all data is global.

**D28. Whether install and uninstall are chassis verbs.**
Recommendation: chassis verbs. Setup is the first thing a user runs and has to work with no modules enabled. The MCP module supplies the registration entry the installer writes.

**D29. One module using another.**
Recommendation: through the other module's declared verbs, called through the chassis, and through events. Never by importing its code.

**D30. Maintaining a user's fork, CI and wheel at release.**
Recommendation: after the MVP. It does not block the first test.

### CLI and settings

**D31. Global settings.** Are some settings the same in every folder?
Recommendation: each setting's schema entry declares folder or global. Context and module settings are folder settings; settings about the Metaform home are global.

**D32. Verb controls.** Are `--glue`, `--unglue`, `--show` and `--json` exempt from being settings, like `--confirm`?
Recommendation: yes. They control the verb, not the outcome. `--quiet` is a setting, since people want it to stick.

**D33. Switch aliases.** mvm lists more than one long form for some settings, such as `--hbi`.
Recommendation: allowed when declared in the schema, and help shows them.

**D34. `--name=false`.**
Recommendation: not accepted. A boolean takes its two bare forms only. Over MCP a boolean is a true or false value.

**D35. The way back when `set --modules` narrows the commands with no workflow active.**
Recommendation: the line names `metaform unset --modules`. help, set, unset and config are always shown.

**D36. What `unset all` resets.**
Recommendation: only the settings stored at the current folder. Values inherited from parent folders show again once the folder's own values are gone.

### MCP and installer

**D37.** Answered by section 8: PROJ-003, PROJ-005 and PROJ-006 carry project selection as settled in the CLI discussion.

**D38. The intake instructions.** The intake module serves them as `metaform intake prompt` and the tool `intake_prompt`.
Recommendation: yes.

**D39. The field for a module's concise instructions.**
Recommendation: the existing `purpose` field. One field, one source.

**D40. Where an agent without MCP reads the composed instructions.**
Recommendation: `metaform`, the status command, which the skill already points to.

**D41. Installer steps in the first test.**
Recommendation: the checks, the tool checklist, the preview with backups, and the proof that each tool starts the server. Repair on re-run and uninstall come after.

**D42. Claude Desktop as a target.**
Recommendation: after the first test, once D37 is built.

**D43. Uninstall and the data in ~/.metaform.**
Recommendation: it asks separately and keeps the data by default.

**D47. Type records: shared or per project.** MAP-010 treats Types as one shared tree; STORE-008 keeps them in each project's store.
Recommendation: one shared Type tree, with elements per project. A Type keeps its universal description, and practices attached at a Type apply to every artifact of that Type.

**D48. Roles on elements a non-intake layer creates.** MAP-017 requires a role; STORE-009 allows none.
Recommendation: no role. DE, SE, NE and VE are the intake's classification of the artifact. An element a memory or challenge layer creates is not part of that classification.

**D50. `metaform abort <workflow> --confirm`.** The chassis does not run workflows.
Recommendation: abort is the workflow module's verb, and the narrowing message names it as that module's command.

**D51. Several AUEs in one project.** How is the set of elements belonging to each AUE recorded? (MAP-042)
Recommendation: each element records the AUE it belongs to, so a project can hold several artifacts and each map stays separable.

**D52. Receipts for long-running work.** Does any chassis verb run long enough to return a receipt? (BASE-030)
Recommendation: no. Receipts belong to the workflow module, since the chassis does not run workflows.

**D53. Settings of an absent module.** Does `unset all` leave a missing module's stored settings untouched? (CLI-024)
Recommendation: yes. Configuration survives the module's absence and applies again when it returns.

**D55. Record fields on the command line.** Arguments are nouns and switches are settings, so a join's purpose or observation is neither. BASE-043 writes optional fields as `name=value` nouns.
Recommendation: `name=value` nouns on the CLI. Agents mostly write through MCP, where each field is a named argument, so the CLI form only has to be clear and unambiguous.

**D56. How a root reads.** The Canonical Intake's reading examples disagree on `code`: `code.loop.main` reads as main loop program code, and `code.bus.data.event` reads as event data bus code. Does a root carry a reading phrase, such as program code for `code`, or does every root read as its own name? (MAP-012)
Recommendation: every root reads as its own name, and the example that says program code is corrected in the test intake. One rule is easier to apply than a phrase per root.

**D57.** A `project` value stored at a folder above a registered project's source location is inherited into it by CLI-014, and that overrides the project's own containment default. A selection made in the user's home would then change the project inside every registered project below it. Should a registered project's source location stop that inheritance, so a folder inside a project defaults to its own project unless a value is set at or below the project's path? Recommended: yes. (PROJ-003, PROJ-005, CLI-014)

**D58.** Should a worktree created outside the project's source location default to the repository's project with nothing selected, found through the worktree's shared git folder, `git rev-parse --git-common-dir`? Recommended: yes, because it needs no setup and writes nothing. (PROJ-006)

**D61.** Is there one export or two? One option is a single wheel carrying the origin unit and the project's store. The other keeps them separate: STORE-027's JSON document for the map and layers, and the unit wheel for history. Recommended: one command, where exporting a project includes its selected origin unit, and the unit wheel carries the project document inside it. (PROJ-020, STORE-027)

**D62.** Knowledge rows on import follow D23: a new revision, or an in-place change. History units follow PROJ-021: a new suffix, keeping both. Should knowledge import also keep both on any loss, to match? (PROJ-021, STORE-027, D23)

**D63.** Does the first instance of an origin take suffix `0000` or `0001`? Recommended: `0000`. (PROJ-013)

**D64.** Which module serves web variants, and is the serving port OS-assigned? Recommended: the web module, with OS-assigned ports. (PROJ-019, D44)

**D65.** Is the 3 MB line measured on the total size of a variant's changed text, or per file? Recommended: the total. (PROJ-016)

**D67.** Are ignored files always outside the boundary of a repository, including generated outputs a workflow was asked to produce? Recommended: yes, and a workflow that wants its outputs kept writes them outside ignored paths. (PROJ-011)

**D68.** When a repository's working tree is dirty as an origin is established, is the commit the origin and the uncommitted work its first variant? Recommended: yes. (PROJ-012)

**D71. A stored starting selection per project.** Should a project also keep a starting selection used wherever `--layers` is unset?
Recommendation: no. The setting already falls back to every locked, unhidden layer, and one mechanism is simpler.

**D72. Hard dependency.** With join roles gone, does hard dependency survive in any form, for example a mark on a function join saying the receiver cannot work without the provider?
Recommendation: gone. How hard a need is already shows in the purpose the join serves.

**D73. The transitive flag on layers.** Transitivity belongs to properties. Does a layer still declare a transitive flag?
Recommendation: no. An item is transitive exactly when it is a property, so the flag would only repeat that.

**D74. Items at a type address with no element.** Properties attach only to elements. Can a memory or a verdict attach at a bare type address?
Recommendation: no. Every item attaches to an element or a join, or to an element its layer creates, which the namespace tree links to the metaform. One rule for every item.

**D78. What an element record holds.** The spec gives element records a name, name length, role, refs and extras, while an element is just a namespace address that things link to. The intake schema also puts a name and refs on the element. Which fields, if any, does an element keep, and where do the rest belong? (MAP-015, STORE-009)
Recommendation: the element row holds only its identity and its address. The name, name length, role and refs the intake gives for an element are stored as intake-layer items attached to that element, so they are linked to it, not held in it.

**D79. Importing history units.** Importing something that already exists does nothing. Section 8 instead keeps both copies of a history unit when they diverge, with the next suffix. Does the does-nothing rule govern history units too? (PROJ-021, STORE-027)
Recommendation: yes for a unit whose id already exists. A diverged unit has a different id, so it is simply new, and keeping both follows without a special rule.

**D80. A removed join when both ends come back.** If an element is removed and put back at the same address, its attached items show again. Does a join whose receiver and provider both exist again at the same places show again too?
Recommendation: yes, by the same logic: the join has both ends to attach to again.

## Engineering choices made

These are decided so the build can proceed. Veto any of them.

- **E1.** Install backups go under `~/.metaform/backups/install/`, one folder per run, so uninstall and repair find them in one place.
- **E2.** Each tool's MCP and skill registration is taken from that tool's own documentation during the build. A tool whose path cannot be confirmed is left out of the first test and marked unverified.
- **E3.** Ruff with its default rules plus import sorting, bugbear and pyupgrade. A suppression needs a comment on the same line saying why.
- **E4.** A test names its requirement with a pytest marker, `@pytest.mark.req("MAP-001")`, so the trace can be generated.
- **E5.** The test-gaming review is an agent run before merge. Its report and the critic review are stored in the repo under `reviews/`, and each is linked from the pull request.
- **E6.** CI runs the chassis's declared minimum Python version and the newest release, on Linux, macOS and Windows. The minimum stays as it is until you take up the version question.
- **E7.** JSON is the exchange format for import and export.
- **E8.** A C answer's link to the element or join that already handles the challenge is kept with the challenge state, STORE-040.
- **E9.** A verb reaches the data access object as `ctx.store`. `Context.data`, the module's own folder, is removed with STORE-022.

## Scope questions from the trace

The trace in TRACE.md found requirements in REQUIREMENTS.md that no section carries yet. Chassis-level ones are being added to their sections. These three need a decision first.

**D44. Module specs outside this spec.** The rulebook (REQ-130 to 134), the workflow module (REQ-140 to 150), artifact history and variants (REQ-160 to 164), and the web and browser terminal modules (REQ-190 to 196) are modules, not chassis.
Recommendation: each gets its own module spec after the first test, built on the template and the common base. This spec covers the chassis, the map and layers, storage, CLI and settings, MCP, the installer and the intake module. Until then those requirements stay in REQUIREMENTS.md as the source for their module specs.

**D45. REQ-066, shared configuration between installed and direct-wheel use.** It says the same state root gives the same configuration, while the confirmed wheel design runs a direct wheel from its own subfolder under ~/.metaform.
Recommendation: the subfolder design stands. A direct wheel reads and writes only its own subfolder, and the only shared step is the merge when a wheel is installed (D27). REQ-066 is corrected to say that.

**D46. REQ-087, launching a harness.** It says Metaform supports launching a configured harness as well as running inside one. The confirmed design says Metaform never launches a model, because hosts start agents in different ways.
Recommendation: Metaform runs only inside the agent's harness. Launching a harness is removed.
