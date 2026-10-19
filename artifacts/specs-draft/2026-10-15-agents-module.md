# Agents module: draft record and amendments for Rich's review

Ticket code.store.prompt#3 (3a1306bd), 2026-10-15. Nothing in `specifications/` was changed. Every heading below is a draft for Rich to approve, change or drop. The code is built as described here; where this text and the code differ, the code is the reference.

## Draft: BASE-066 Each role an agent runs as has one record, naming the prompts it is sent where they already live

- Requirement: The agents module keeps one record for each role an agent Metaform starts runs as. The record says what the role is for, the prompts it is sent in the order sent and when, the tools and authority it has, and the agents running as it now. The module also says which role a given session ran as and which prompt versions each of its turns carried.
- What this means:
  - The roles are the code's: `settings.AGENT_ROLES`, intake, system, sentinel, talk, prep and worker (`src/metaform/settings.py:779`). BASE-054 names six other roles: the person, the orchestrator, the workflow builder, the evaluator, the loop controller and the workers. The two lists do not match. The code is the reference: the module follows AGENT_ROLES. Reconciling the two lists is Rich's decision (see "Questions" below).
  - A role names each prompt by its name in the prompt store, the name `metaform prompts review` already uses: `<module>:<element>` for an element of a module's prompts.xml (`dispatch:system`, `dispatch:work`), `<module>:<file>` for a prompt kept whole in a file (`intake:intake.axiom`), and `skill:<name>` for a skill's procedure (`skill:sentinel`). The prompts stay in their modules, and those modules still send them.
  - A name that no longer resolves stays on the role with `resolves: false` and the reason. The role is never shortened to hide it.
  - The authority on each role comes from `roles_without_authority` (MAP-050). The tools are every tool on the folder's surface, less `dispatch_intake_withheld` for the intake. A role started with system true may put a question to the person; prep and worker are answered with `dispatch:decide` (BASE-052).
  - What each session was sent comes from dispatch's runner. As each turn that carried a prompt goes, the runner publishes `prompt.sent` with the session's ids, its role and each prompt version served since the last turn. The module keeps one row for each turn in its table `sent`, at project place, linked from its layer `agents` the way memory's tables are linked from the memory layer (LAYER-001).
- Why: Rich decided on 2026-10-15 that the module augments the prompts and does not move them. A role's prompts are spread over several modules, so without the record nobody can see in one place what an agent of a role is told, or which text a past session got.
- How it shows: `metaform agents roles` lists the six roles. `metaform agents role name=worker` shows each prompt with its text, its version and whether an edit is sent in its place. `metaform agents sent session=<id>` shows a session's role and the versions it was sent. `metaform agents override name=dispatch:work text=...` saves an edit, and `metaform agents drop name=dispatch:work` goes back to the shipped text. Both carry a caution, and an agent whose role is held back is refused.
- Build: `src/metaform/modules/agents/` (ROLES, five verbs, table `sent` version 1, subscriber of `prompt.sent`); `prompt_files.served` and `served_text`; dispatch's `prompt()` and its runner's `carried()`; skills' `served` and `bound`; workflow's agent-facing prompts. Tests: `src/metaform/modules/agents/tests/test_agents.py`, `tests/test_prompts.py` (the two newest), `tests/test_prompt_files.py` (the newest), `src/metaform/modules/dispatch/tests/test_dispatch.py::test_a_worker_s_first_turn_tells_the_prompt_versions_it_carried_and_agents_keeps_them`.

## Draft amendment to STORE-044 (`specifications/03-storage.md`)

- Amendment 2026-10-15, ticket 3a1306bd (draft): a prompt a module sends to an agent is served through the prompt store as `<module>:<element>` (`prompt_files.served`). Its shipped text becomes a version whenever it changes, and an edit saved in the store is sent in its place. Dispatch sends all its prompts this way, as do the skill registry's `served` and `assignment_input`, a skill's procedure (`skill:<name>`) and workflow's prompts. An edit that is not well formed is not sent: the shipped text is, with a line on stderr. A shipped text that changes while an edit is the newest version is kept beside that edit in `prompt_shipped`, layout 3 (layout 2's code still reads it). The role shows it, so the person sees that their edit is behind and can merge it (`agents override`) or drop it (`agents drop`). Before this, `shipped()` ignored such a change without a word (`prompts.py`, formerly line 219). The Canonical Intake is unchanged: it is served as shipped and never stored or edited, nor is the schema line served with it.

## Questions for Rich

1. Today's message said intake's role prompts should be served through the store too. STORE-044's own bullet (03-storage.md:1165) and `test_the_intake_serves_the_shipped_file_and_keeps_nothing_in_the_prompt_store` (commit 4675e14) say the Canonical Intake is the one prompt that is never stored or edited. I kept that: the intake role shows `intake:intake.axiom` and `intake:schema_pointer` as `fixed`, and override refuses them. Lifting it is one line in `intake.served` plus the record's wording.
2. BASE-054's six roles and the code's six are different lists. Should the record name both lists, or should BASE-054 be amended to the code's list?
3. The module's connect line (`<connect>` in `modules/agents/resources/prompts.xml`) is empty, so it adds nothing to the 2,048-character connect message. A proposed line: "– agents: the roles of the agents Metaform starts, the prompts each is sent and what each session was sent". Approve, change or keep it empty.
4. The module ships enabled, because a session's record exists only while the module is on. Its five tools are on every agent's list. Should it ship disabled, like dispatch?
5. The sentinel's skill text is read through the workflow module. With workflow off (it ships disabled), the role lists `skill:sentinel` as `unread`, not broken, because a module may not import `metaform.skills`. Should `metaform.skills` join the public base?

## Places that should move onto code.framework.plugin#b

Each of these tells the person something. For now each one is returned in a verb's result or written to stderr, and none of them is a popup:

- `agents role` / `agents roles`: `behind` and its `note`, when an override is sent in place of a newer shipped text (`_held` in `modules/agents/__init__.py`).
- `agents role`: `broken` and its `notice`, when a prompt name no longer resolves (`role` in the same file).
- `agents role`: `broken_edit`, when the edit in the store is not well formed and the shipped text is sent in its place.
- `prompt_files.served`: the stderr line `Prompt <name> version <n> is not well-formed XML...`, written when a malformed edit is passed over.
- `agents override`: the notice that the edit leaves out a fill place the module fills.
