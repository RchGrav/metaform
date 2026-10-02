# Open questions

Only questions that depend on Rich's intent are open. Every question with one technically correct answer is settled by its recommendation, which the build follows as written.

## Open

**D84. Work records and layers.** A work record is built as a record of its own, attached to one element or join and to no layer. Does it stay a record of its own, or does it live in a layer? (MAP-046, STORE-042)
Recommendation: a record of its own, as built: it follows its object through every version, survives the discard of any layer, and any agent writes it at any time.

**D85. `tbd`.** Is `tbd` one condition whose task says whether the object needs building or deciding, or two conditions? (MAP-046, STORE-042)
Recommendation: one condition, as built; the task says which.

**D86. Correction layers.** On 2026-09-27 the design was stated as: changing the metaform is updating it, each change a new version of the object with provenance, with no need for correction layers now that the map is changed object by object. Do correction layers go entirely, or do they stay as the one ordered way to change the metaform, LAYER-011? The stack and peel of STORE-017, the checks of STORE-034, the re-examination marks of STORE-036, the removal from the top of VIEW-014, and the way an approved blind-spot entry enters the metaform, D89, all follow the answer. (LAYER-011, STORE-017, STORE-034, STORE-036, VIEW-014)

**D87. Roles with several AUEs.** An element carries one role, on its own record, MAP-017. When one project holds several AUEs and an element plays a different role for each, such as DE of one and SE of another, how is its role recorded? D51's recommendation, each element recording the AUE it belongs to, settles membership and not a second role. (MAP-017, MAP-042, D51)

**D88. How a property is recorded.** MAP-022 and STORE-039 record a property as a value attached to an element, with no join. The Foundation speaks of property joins that are transitive. The design of 2026-09-26 and 2026-09-27 has an element of any kind linked to the node where it belongs, the link marking it as a property, a link that can be moved and that a function reads as transitive. Is a property a value on an element, a link between two elements, or a join of its own kind? (MAP-022, STORE-039, LAYER-020, VIEW-022)

**D89. An approved blind-spot entry.** An approved entry becomes a permanent record of the metaform, with provenance, and the user holds the final veto over every green and every yellow answer, LAYER-015. How does the entry enter the metaform, and does it arrive with an open `tbd` work record carrying its task, drawn at partial opacity until it is built, as an approved blind spot becoming a spec waiting to be built says? How is the veto recorded? (LAYER-011, LAYER-015, STORE-040, VIEW-020, D19, D86)
Recommendation: it arrives with an open `tbd` record carrying the critic's task, since that is what a spec waiting to be built is, MAP-046; the way it enters the metaform follows D86.

**D90. The voice of the fields.** The fields are written with third-person singular present-tense active verbs ending in -s or -es, so each reads as a sentence after the element's name, and the intake agent writes, for each element, a concise statement that continues from its name, MAP-020. The Canonical Intake applies the voice to the relation and the verb. Which other fields follow it? Which element's name does each field continue from, the receiver's or the provider's? And where is an element's statement kept, now that an element holds only its address, name_length and role, MAP-015? (MAP-015, MAP-020, MAP-040, BASE-039)

**D91. Listed rules and the item flags.** What an agent is handed with a task lists the rules rather than carrying their full text. Does listing replace the `read_first` and `always_show` flags, or do they stay beside it? (LAYER-021, MAP-048)

**D92. Tasks, questions and past work.** Answered in part, Rich 2026-10-01: a task is a ticket, the work record on the node it is assigned to, which links other nodes for reference, keeps its kind while it is worked, and moves across a board's columns, STORE-042 and VIEW-035; agents are told to use Metaform for all task assignment while the `tasks` setting is on, the default. The rest stands: A task is written on every node the work concerns, MAP-048; a work record carries a task, MAP-046; and a knowledge item can be flagged `task`, LAYER-021. Are these one kind of task or several? What holds the orchestrator's task list and its queue, MAP-049, the agent's progress sentence at each node, a question at a node and its answer, MAP-050, and past work with its work log, MAP-051? Can a person submit work directly in the web GUI, as the explanation offered with an intake says, MCP-027, which would be a write beyond VIEW-011's? (MAP-046, MAP-048 to MAP-051, LAYER-021, MCP-027, VIEW-011, VIEW-020, VIEW-021)

**D93. The project module place.** Modules load from ranked places, system, user and project, where the project place holds modules that load only for the active selected project, BASE-014. Metaform writes nothing into a project folder and keeps all data in the home, STORE-001. Does the project place live in the project's own folder, as `.metaform/modules/`, which the person creates, or under the project's data in the home? D25 had recommended no project place, before the place was part of the design. (BASE-014, BASE-037, STORE-001, D25)

**D94. The CalVer format.** Versions during development are CalVer, never SemVer, BASE-020. Which format? The package declares `0.2.0` today, and the spec's examples show that form. (BASE-020, BASE-041, BASE-042, CLI-028)

**D95. Which folder's settings the web GUI shows.** A browser has no folder, and one server serves every project. Which folder's settings, such as `--layers`, CLI-033, does the GUI show and change? (VIEW-002, VIEW-004, VIEW-007, section 09 question 5)
Recommendation: each project's registered folder, shown with its path at the top of the page; built so until answered.

**D96. First-run provisioning.** MCP-028 carries the design of 2026-09-11, which offered provisioning through the menus that nonces keyed, since dropped, MCP-012. The installer of MCP-013 to MCP-021, designed later, sets up the tools it knows. Does first-run provisioning for an unfamiliar harness stand beside the installer, and through which commands? (MCP-028, MCP-013, MCP-016, MCP-021)

**D97. mvm's parts the spec does not carry.** The command line follows mvm, CLI-035. mvm has `config <group>`, which opens one group of the settings screen, and `config --wizard`, a guided setup, and its help page has a section on when to use the command and one listing its subcommands, which CLI-029's page does not. Are they wanted? (CLI-035, CLI-026, CLI-029)
Recommendation: yes, all four, since the design is mvm's and no later decision removed them.

**D98. The writing standard's text.** Everything a person reads is written to one writing standard, CLI-036, given as a set of plain-writing rules that are not in this repository. Where is the text kept, so the critic review, QUAL-008, can apply it? (CLI-036, QUAL-008)
Recommendation: a file in `specifications/`, beside `code_quality_standards.md`.

**D99. The Canonical Intake's wording.** Its text changes only in Rich's words. It differs from the decided shape in these places: each element carries a `<name/>`, while the project's name for a functionality goes on the join, MAP-020; its response protocol says to remove absorbed subparts recorded as root elements, while the element stays one record, MAP-031; its nested subtype join has no type and no non_goal and carries a provider beside its inline element, MAP-030; its method's steps do not show the call the agent makes for each entry, with the JSON arguments it sends; it does not say that the intake agent writes the condition of an object as a work record, MAP-046, and the recording lines served after it, BASE-039, do not name `map_work`; and the voice of the fields and the element's statement, D90, are not in it. Which wording do you want for each? (MAP-020, MAP-030, MAP-031, MAP-040, MAP-046, BASE-039, D90)

**D100. The install front door.** Installing a wheel goes through an install stage that never downgrades without force, with a backstage check on the first run of an install that went around it, BASE-047. The design writes the front door `python metaform.whl install`, while `install` is the chassis verb that sets up AI tools, MCP-013, and a directly run wheel runs the same command line, BASE-042. What is the front door's command, and what exactly do the stage and the backstage check? (BASE-047, BASE-025, BASE-042, MCP-013)

**D101. TRAO-DAG.** Rich's description of 2026-09-26, TRAO-DAG, is the reference the build is measured against. The spec carries its binary Func and Enc state on joins as `ef`, MAP-020, its annealing as subtype joins that keep their own encounter functions under the combined one, MAP-030, and its prompt expansion as preprocessing and the `context` read, LAYER-017 and STORE-035. Two of its parts are not carried: the Func and Enc state on nodes, and bias blind spots computed as Func capabilities minus Enc manifestations, beside the two critic analyses of LAYER-014. Does either belong in the design? (MAP-020, MAP-030, LAYER-014, LAYER-017)

**D102. Metaform's own metaform.** The release carries a metaform of Metaform itself, for developing Metaform, BASE-048. Where does it live, and how does it reach a user's home, given that a project's data lives only in the home, STORE-001: as an export document in the repository, STORE-027, imported on first run, or another way? (BASE-048, STORE-001, STORE-027)

**D103. Why the ideation agent adds one feature.** An ideation agent examines the whole project, adds the single most valuable missing feature, and may build its own module to do it, LAYER-023. What is it for, beside the blind spot analyses of LAYER-014, and why one feature? (LAYER-023)

**D104. The inferred slash commands.** Rich named `status`, `config`, `web`, `messages` and `tasks` as slash commands, MCP-033. Each is inferred to run one verb and serve its result: `status` what `metaform` alone prints, `config` what `config --show` prints, `web` what `web start` prints after starting the web GUI when it is not running, `messages` what `map messages` prints, and `tasks` what `map work open=true` prints. Is each the verb meant, and does any carry words of Rich's that tell the agent what to do with the result, such as walking the person through the open questions, or taking a task? (MCP-032, MCP-033, D92)
Recommendation: each runs the verb in MCP-033's table and serves its result alone until Rich writes its words.

**D105. `/metaform:prompt`.** Does it show a stored prompt by name, the way `metaform prompt <name>` does, STORE-044, or run a stored prompt on the metaform, preprocessed against the map, LAYER-017? (MCP-033, STORE-044, LAYER-017)
Recommendation: none. The two are different commands, and which one is meant is Rich's intent.

**D106. `/metaform:correct`.** A correction layer is the only way to change the metaform, LAYER-011. Running the command could create a correction layer at once, or serve Rich's words telling the agent to record the correction the person describes in a new correction layer and finish it. Which, and what are the words? (MCP-033, LAYER-011)
Recommendation: no verb, and Rich's words, so no empty correction layer is left behind when the person stops before saying what is wrong.

**D107. `/metaform:refine`.** No command or record of this name exists. What does it do, and which module owns it: annealing, MAP-030, building a knowledge layer node by node, LAYER-020, or something else? (MCP-033)
Recommendation: none. Nothing in the spec says what is meant. Since 2026-10-01 changing the metaform is called refining, LAYER-025; whether `/metaform:refine` starts a refinement, and whether `/metaform:correct` is still a command of its own, D106, are still Rich's.

**D108. Undoing a refinement.** Refinements are versions in the `intake` layer, LAYER-025, and every version is kept. Correction layers were undone by peeling the top one, VIEW-014. Is a refinement undone, and how: the page steps a thing back one version, or a refinement is undone only by refining again? (LAYER-025, VIEW-014)
Recommendation: refining again, which keeps one way to change the metaform; history shows each earlier version to refine back to.

**D109. Who made a refinement.** A correction layer carried its own provenance: the module, workflow, prompt, model and role of the agent that made it, and its tags. A refinement is a version in the `intake` layer, LAYER-025, and keeps only its reason and evidence; the intake layer's provenance is the intake agent's. Is the model, role and prompt of each refinement recorded, and where: on each version, or as one record per refinement run that its versions name? (LAYER-025, LAYER-010, STORE-044)
Recommendation: one record per refinement run, with its provenance and tags, that each version it wrote names, so a run's versions are read together and nothing about who made them is lost.

**D110. The tickets and the agent figures on the map.** VIEW-035. Which node is the most primary: the DE? Does a figure stand for a ticket or for an agent, given that subagents of one session share its session id and process id, 05-cli-settings? What are the stored names of the four kinds, a work record holding only missing, broken and exclude today, and who took a ticket under which harness, which a work record does not hold, D92?
Recommendation: the DE; one figure per ticket from take to done; the shortest way along the drawn edges. Built on this recommendation 2026-10-01, Rich may overrule it; the stored names are `flawed` and `enhancement`, Rich 2026-10-01, and who took a ticket is `taken_by`, STORE-042.

**D111. Collapsing the metaform into a single layer.** LAYER-026. Do the knowledge and memory layers fold into the single layer, carry over as their own layers, or stay with the old metaform? Do open tickets carry over? Does collapse write a new metaform, keeping the old one whole, or the same metaform in place?
Recommendation: a new metaform of one layer, made active, the old one kept whole; element and join ids carry over; knowledge and memory layers carried over as their own layers; open tickets carried over, done ones left with the old metaform.

**D112. Promoting a join to an element.** MAP-054. When a join is promoted, is it rerouted through the new element, so the receiver reaches the former provider only through it, keeping the join's id and what is attached to it, or does the original join stay as it was with the new element beside it?
Recommendation: reroute, so the map says once how the receiver is served and the join keeps its memories and work.

## Answered

**D78. What an element record holds.** Rich, 2026-09-27: the namespace address is the name index, and the element was meant to be only its address and name_length; roles stay on the element. The project's own name for a functionality goes on the join, the purpose join and the subtype join alike. The element record is its identity, address, name_length and role; its refs are rows linked to it. MAP-015, STORE-009, MAP-020.

**D83. Moving elements and joins, and the subtype join.** Rich, 2026-09-27: an element cannot be moved; it is an address in the namespace, and moving it changes its address. A function's join can be moved, mostly while annealing, otherwise to fix a serious misinterpretation or to follow a change in the design's structure, and a moved join is the same join. An element always appears as one element record; annealing places it in its parent's join as a subtype join, and the element itself does not move. The subtype join is a join of type `subtype` held in its parent's purpose join, a row of `joins` whose current row is kept apart from the element graph's, and an element whose only joins are subtype joins is not a root. D3, D4 and D5 carry over to it. MAP-003, MAP-015, MAP-030, MAP-031, MAP-032, STORE-007, STORE-010, STORE-011, STORE-017, STORE-034.

**D82. Submissions that break the shape.** Stored as given; a correction layer or a reviewer deals with them. No agent submission is refused for its content: what does not fit is stored and noted in a notice, and an agent that cannot continue stops and submits a trouble report. BASE-044, STORE-026.

**D81. intake_submit.** It has its own input schema, the metaform's general data pattern, with field names and nesting taken from the Canonical Intake. The agent submits against it once. The intake text is served unchanged with one module line after it, and can change freely as long as its structure keeps that pattern. Replaced 2026-09-26: the intake is recorded one object per call through the intake tools, whose fields keep that pattern, and the text is served with the module's recording lines, MAP-040, BASE-039.

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

**D8 and D54. How the intake result reaches the store.** The intake agent completes the whole method, including annealing, then submits once through the `intake_submit` tool. Its inputs mirror the intake schema's fields. The tool validates the submission and stores it as the intake layer in one write, so an intake is never half written. The intake text's response protocol will say to submit the final shape through `intake_submit`; the method stays word for word. Replaced 2026-09-26: the intake agent records each object through the intake tools as it is reasoned, proofs the recorded map, and finishes it; nothing is submitted whole, MAP-040, BASE-039, STORE-032.


## Settled by recommendation

**D3. Can a subtype own joins after annealing?** (MAP, STORE)
Recommendation: no. Its joins lift to the parent when it is annealed. A subtype is reachable only through its join and is never a root, so it cannot be a receiver in the graph. Since D83 the absorbed element is an ordinary element: the agent lifts its joins by moving them, and until it does the element is a node of the outer map, MAP-032.

**D4. Can one element be a subtype in two different joins?**
Recommendation: no. A subpart is absorbed only when one parent's join already carries its purpose. A part that serves two joins has a role of its own in the map and stays a root element. This also settles whether a subtype can share an address with a root element: it cannot. Since D83 an element held by a second subtype join is stored as given with a notice naming the first, BASE-044, MAP-032.

**D5. Can a subtype hold subtypes of its own?**
Recommendation: no, one level. A subtype lives inside a join, not inside an element. This can be relaxed later without breaking stored maps. Since D83 a subtype join's parent is a join held by a receiver; one that names a subtype join cannot be read, and a join absorbed while it holds subtype joins passes them to its new parent, MAP-032.

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
Recommendation: through a correction, as a new revision of the map layer. Since 2026-09-27 an approved entry becomes a permanent record of the metaform; how is D89.

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
Recommendation: none, since all data is global. Reopened as D93: the project place is part of the design, BASE-014, and where it lives is open.

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
Recommendation: each element records the AUE it belongs to, so a project can hold several artifacts and each map stays separable. The role an element plays for each AUE is D87.

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
Recommendation: the element row holds only its identity and its address. The name, name length, role and refs the intake gives for an element are stored as intake-layer items attached to that element, so they are linked to it, not held in it. Replaced by Rich's answer of 2026-09-27, under Answered.

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
