---
name: metaform-prompt-store-served
description: Use when editing prompts.xml or a prompt agents are sent.
category: development
---

# Send an agent prompt through the prompt store, never around it

A prompt an agent is sent goes through `prompt_files.served(...)` (`served_text(...)` for a whole-file prompt). The store decides the text sent: an edit saved there replaces the shipped `prompts.xml` text from the next turn. Check the text the agent gets, not the file alone.

- The key is `<owner>:<element>` (owner = folder name, `chassis` for metaform, `skills` for metaform/skills), the same key `metaform prompts review` shows.
- A malformed edit is passed over: the shipped text is sent, a line goes to stderr, and `agents role` reports `broken_edit`. A bad edit does not block a send.
- `intake.axiom` and `schema_pointer` are never stored or edited. STORE-044 and `test_the_intake_serves_the_shipped_file_and_keeps_nothing_in_the_prompt_store` pin this; a change that routed them through the store was reverted on 2026-10-15. Read that test before moving any prompt into the store.
- Each turn that carries a served prompt must reach the runner's `collect()`, or `prompt.sent` loses its versions and `agents sent` returns nothing. The guard is `test_a_worker_s_first_turn_tells_the_prompt_versions_it_carried_and_agents_keeps_them` in dispatch's tests.
- A schema change to the prompt store takes a new layer: see verify-store-schema-change.
- A new served prompt is a new module capability: follow metaform-module-capability-checklist.
- The knowledge-update step (6) and the work record both carry placement wording. The current rule is record where found, not choose the depth (`metaform-memory-graph-links`); change both in one edit, then check each served text.
- A rule only an on-demand block holds never reaches an agent. Agents receive the pushed texts (the first-call guide, served prompts, the dispatch brief); an element behind `metaform_instructions`, `metaform help` or a module's instructions is read only when an agent asks, and on 2026-10-15 none did. So every rule an agent must follow goes into a pushed text. Claude Code keeps only the first 2,048 characters of the MCP connect instruction, so a rule placed later in it never arrives. Check the rule in what is sent, not in the file.
- A rule that several served texts carry is changed in every copy, in the same edit. Dispatch's prompts.xml repeats the memory placement rule in more than one step (the work record, the Knowledge Update step and the memory retrieval step), so changing one leaves agents holding the old rule in the others. After the edit, check each served text, not the file.
- Prove the served text before reporting it: with no edit saved, `prompt_files.served(folder, name, **fills)` must equal `prompt_files.module(identifier, name, **fills)` for the same fills. `agents role` shows the stored XML, so `>` appears as `&gt;` there; what the agent is sent is unescaped.
