Report on the project: metaform at commit 2e6f581, step 62.

Checked: 564 tests outside the web module pass on Linux in 303 s (.venv pytest, web tests not run). The Canonical Intake resource copy is byte-identical to specifications/Canonical_Intake.xml.

Broken
- Prompt store, code.store.prompt: not connected. Outside tests nothing calls prompts.shipped, prompts.add_prompt or prompts.record_use. No module ships a prompt, and map_knowledge op=create prompt= keeps the text in provenance but links no version. The store stays empty, every provenance read's prompt_version is empty, and the web GUI's Prompt tab and save have nothing to open. STORE-044 and VIEW-013 are built but never fed.
- Documentation, document.guide.user: statements the source now contradicts. docs/guides/working-with-metaform.md line 234 says map knowledge does not expose ef; it does, BASE-038. The preprint (lines 77, 316, 368) and IMPLEMENTATION_MAP.md (lines 62, 77, 762) describe descriptor items and a missing flag, both gone since steps 49 and 42. The set documents commit ce9062b.

Cruft
- A .metaform/ folder from the pre-chassis runtime, dated 09-10 to 09-18, sits untracked in the repository root; STORE-001 writes nothing there now.
- The root also holds untracked leftovers: AGENTS.bak, CLAUDE.md~, README.md~, metaform.zip, metaform_2.zip (35 MB), metaform-reference-inputs.zip, metaform_code-only_20260924.xml, archive/, archives/, artifacts/, dist/, exports/, node_modules/, prompts/, specs/, .test-tmp/, .tmp/, media.photo.product.used/. uv.lock is untracked while CI runs uv sync, so CI resolves dependencies fresh each run.
- specifications/spec/HANDOFF.md still describes the build near step 11 and four Canonical Intake questions the current text no longer has.
- OPEN-QUESTIONS.md's answered D8, D54 and D81 and CAPTURE's 09-25 entries describe the single intake_submit submission that MAP-040 replaced. MAP-030, MAP-040 and BASE-039 say the Canonical Intake's schema still shows a name on each element, tells agents to remove absorbed subparts and puts a provider beside the nested element; the current text does none of these.

Specified or decided and not built
- Export and import of an origin unit as a wheel, PROJ-020 and PROJ-021; metaform export refuses origin=. Questions 5 and 13 of section 08 are open.
- Serving web variants side by side, PROJ-019.
- The workflow module with --workflow, abort and receipts, and prompt and workflow lexicalization, LAYER-017, D44.
- The blind-spot critic side: no critic prompt, no answer prompt, no module running a blinded or sighted critic; only challenge states, answer, approve and plans exist.
- CAPTURE 09-26 and 09-27, under discussion: tasks on nodes and a work queue agents take from, progress labels, past work, item flags; questions at nodes with a Messages button; suggesting a blind-spot challenge and a best-practices layer when an intake is offered.
- BASE-027 fork, CI and wheel upkeep for module authors.
- QUAL-009 lists only tests without a requirement, not requirements without a test. QUAL-005: E3's rule set (import sorting, bugbear, pyupgrade, reasoned suppressions) is not applied; pyproject runs Ruff's defaults.

Open decisions blocking work
- MCP-011, the server's project when a host starts it outside every project; the set tool is the fallback.
- The PyPI distribution name; metaform is taken.
- Claude Desktop, D42; unverified registration of Copilot CLI, Factory and Antigravity; MCP-022 skill-load proof per tool.
- SE is Substantial Element in the Canonical Intake and Supportive Element in the spec, preprint, reference and agent definition.
- CAPTURE 09-27 says no correction layers, changing the metaform as versioned updates; not placed, so the stack stands.
- VIEW questions 3 and 5, how a module adds a view and which folder's settings the GUI shows.