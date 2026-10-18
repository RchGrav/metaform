# Final role, prompt, skill, MCP and browser verification

Runtime and prompt candidate: `8c9bf81eaa6876b5dc34766574ebb1eece2a5851`.
Candidate tree: `0491a3ce9f3d0814c835de60f6070211ccf9dd57`.

No runtime or prompt source changed during these final checks. The only test correction adds the implemented public resources to the pre-existing exact MCP inventory assertion: fixed resource `metaform://orchestration/bmad`, plus templates `metaform://role/{name}` and `metaform://orchestration/assignment/{assignment}`.

## Consolidated focused gate

Result: **124 passed, 1 failed, 1 deselected in 151.24 seconds**. The failure is the resource-inventory expectation corrected and rerun below. The original result remains in `roles-prompts.xml`; it has not been rewritten to conceal that failure.

The deselected pre-existing `no_prompt_text_is_written_in_python` check flags an unrelated existing map critic phrase. Prompt-review tests with the previously established grouped-comment and root-user chmod assumptions are outside this focused gate.

Run from the repository root:

```bash
.venv/bin/pytest -n0 \
  src/metaform/modules/agents/tests \
  tests/test_prompt_updates.py \
  tests/test_prompt_files.py \
  tests/test_prompts.py \
  tests/test_skill_deployment.py \
  tests/test_universal_skills.py \
  src/metaform/modules/workflow/tests/test_skills.py \
  src/metaform/modules/mcp/tests/test_mcp.py::test_ticket_authority_refuses_a_worker_over_mcp_and_on_the_command_line \
  src/metaform/modules/mcp/tests/test_mcp.py::test_ticket_authority_is_lifted_when_the_person_holds_no_role_back \
  src/metaform/modules/mcp/tests/test_mcp.py::test_a_worker_is_listed_its_category_alone_and_opens_another_in_its_place \
  src/metaform/modules/mcp/tests/test_mcp.py::test_a_configured_restricted_worker_keeps_its_ticket_schema_and_guides \
  src/metaform/modules/mcp/tests/test_mcp.py::test_resources_serve_the_instructions_and_what_a_module_declares \
  src/metaform/modules/mcp/tests/test_mcp.py::test_every_role_connects_to_the_directive_and_the_links_that_apply_and_each_reads_back_its_block_whole \
  src/metaform/modules/mcp/tests/test_mcp.py::test_a_compaction_inside_a_turn_is_said_with_the_agent_s_next_tool_call_once \
  src/metaform/modules/mcp/tests/test_mcp.py::test_each_guide_comes_once_until_the_agent_says_its_context_was_compacted \
  src/metaform/modules/mcp/tests/test_mcp.py::test_on_the_july_wire_over_http_a_session_handle_keys_the_guides_and_no_listing_is_claimed \
  -q -k 'not no_prompt_text_is_written_in_python' \
  --timeout=45 --timeout-method=thread \
  --junitxml=evidence/gc-orchestration/roles-prompts.xml
```

## Resource-inventory correction

Result: **1 passed in 3.81 seconds**, recorded in `resource-inventory.xml`.

```bash
.venv/bin/pytest -n0 \
  src/metaform/modules/mcp/tests/test_mcp.py::test_resources_serve_the_instructions_and_what_a_module_declares \
  -q --timeout=45 --timeout-method=thread \
  --junitxml=evidence/gc-orchestration/resource-inventory.xml
```

The correction adds two lines to the test's expected resource sets; every existing resource, description, actual body, CLI-equivalence and unknown-resource assertion remains.

## Actual Chromium browser scenarios

Result: **2 passed, 4 deselected in 41.61 seconds**, recorded in `browser.xml`.

```bash
PLAYWRIGHT_BROWSERS_PATH=/workspace/scratch/243b683ad142/browsers \
.venv/bin/pytest -n0 -m browser \
  src/metaform/modules/web/tests/test_orchestration_ui.py \
  -q --timeout=50 --timeout-method=thread \
  --junitxml=evidence/gc-orchestration/browser.xml \
  --basetemp=/workspace/scratch/243b683ad142/swarm-browser-tests
```

The notification scenario verifies actual message-body visibility in the live project banner and Chat, the notification channel's read-only controls, and a second actual transport-published message refreshing the banner without reloading or injecting an event.

The specialist scenario verifies the real native and installed-BMAD menu, displays installed source and menu text, and launches through the normal public continuation. The fake ACP recipient receives the installed authored source, requested `CR` contribution and authored role URI. The source file remains unchanged. Configured and actual project and machine capacity are all **1**. Both scenarios assert no browser console errors.

Retained adapter transcript:
`/workspace/scratch/243b683ad142/swarm-browser-tests/test_role_picker_keeps_native_0/role-picker-acp.jsonl`.

The requested initial in-repository `--basetemp=artifacts/swarm-browser-tests` failed before scenario execution because the existing project-history fixture discovered the ancestor source Git repository and attempted to archive an untracked temporary path. Moving the retained test directory outside the source repository resolved setup without a source change.

These async checks used the authorized escalated execution environment: the default sandbox independently hangs on the minimal AnyIO thread primitive, before repository behavior is involved.

## Frozen-source whitespace observation

`git diff --check 10e2984ea36231b474b197e30661712ff45e3765 HEAD` reports extra EOF blank lines in `src/metaform/modules/agents/roles.py` and `src/metaform/modules/dispatch/orchestration.py`. All newly added Python test files end with exactly one newline. The two implementation files were left unchanged to preserve the frozen candidate.
