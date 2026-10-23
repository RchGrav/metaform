# agents

One record for each role an agent Metaform starts runs as, ticket 3a1306bd (2026-10-15).

## Purpose

The agents module says, for each role in the code (`settings.AGENT_ROLES`: intake, system, sentinel, talk, prep, worker), what the role is for, the prompts it is sent in the order they are sent and when, each prompt's text and its version in the prompt store, the tools and authority it has, and the agents running as it now. It also says which role a given session ran as and which prompt versions each of its turns carried, and lets the person save an edit of a role's prompt that is sent in place of the shipped text.

The prompts stay where they are. A role names each by its name in the prompt store, the name `metaform prompts review` gives it: `<module>:<element>` for an element of a module's `resources/prompts.xml` (`dispatch:system`, `dispatch:work`, `skills:served`), `<module>:<file>` for a prompt kept whole in a file (`intake:intake.axiom`) and `skill:<name>` for a skill's procedure (`skill:sentinel`). The module that ships a prompt still sends it, through `prompt_files.served`, which serves the store's version, STORE-044.

## Template version

The template changelog version this module started from: 0.2.0.

## Declaration

- `SUPPORTED_OS`: linux, macos and windows; it reads files and the stores only.
- `DEPENDENCIES`: none.
- `SHIPS_DISABLED = False`: what each session was sent is kept only while the module is on, so it is on from the start.
- `REMOTE_AGENT = False`: the roles and the record of what each session was sent belong to the home whose dispatch started the sessions.
- `MODULE`: five verbs, one subscription (`prompt.sent`), one table (`sent`). No settings, toolbar items or panes.

## Common base used

- `metaform.prompt_files`: `shipped(id, name)` for the text a module ships now, `rendered(text)` to check that an edit is well formed, as `served` sends it.
- `metaform.data.prompts`: `prompt_versions`, `prompt_version`, `behind`, `shipped`, `save_prompt` and `add_prompt_version`, the home's prompt store, STORE-044.
- `metaform.data`: `Tables`, `Table`, `Column` and `Index` for its table; `Store.layer` for its layer.
- `metaform.module`: `surface` and `context` to call dispatch's `sessions` and workflow's `skill` verbs without importing them; `held_role` to refuse an override from an agent the person holds back.
- `metaform.settings`: `AGENT_ROLES`, and `dispatch_intake_withheld` when dispatch is on.

## Prompts

`resources/prompts.xml` holds the module's own `connect`, `instructions`, `counts` and `rules`. `connect` is empty until the owner approves its wording, so the module adds no line to the connect message. The prompts a role is sent are not here.

## Verbs

| Verb | Tool | Effect | Returns |
| --- | --- | --- | --- |
| `metaform agents roles` | `agents_roles` | read | Each role with what it is for, its prompt names, the names that no longer resolve (`broken`), those whose shipped text cannot be read here (`unread`), those whose edit is behind the shipped text (`behind`), whether `roles_without_authority` holds it back, and how many agents run as it now. |
| `metaform agents role name=<role>` | `agents_role` | read | One role: each prompt with `when`, `resolves`, its `revision` and `origin` in the prompt store, the `text` sent next with its fill places, a `note`, `behind` when an edit is sent in place of a newer shipped text, `broken_edit` when the edit is not well formed; then `tools`, `withheld`, `held_back`, `authority`, `asks_person` and `running`. A name that no longer resolves stays in the list with `resolves: false` and its `problem`, and the result carries `broken` and a `notice`. |
| `metaform agents sent session=<id>` | `agents_sent` | read | The role, agent and ticket of a session, by its session id or its runner's (`METAFORM_SESSION`), each prompt it was sent with the version numbers, and each turn with its time and the versions it carried. |
| `metaform agents override name=<prompt> text=<text>` | `agents_override` | write, caution | Saves an edit in the prompt store, sent in place of the shipped text from the next turn of every role that names it. The shipped text becomes version 1 first, so the edit has a parent. An edit that is not well formed is refused; one that leaves out a fill place is saved with a notice naming it. |
| `metaform agents drop name=<prompt>` | `agents_drop` | write, caution | Goes back to the shipped text: it becomes the newest version, so later shipped changes flow in again. |

`override` and `drop` carry a caution, so over MCP the person confirms them in their AI tool and on the command line they need `--confirm`. An agent whose role `roles_without_authority` names is refused both. The Canonical Intake (`intake:intake.axiom`) and the schema line served with it (`intake:schema_pointer`) are never stored or edited, STORE-044: the role shows them as shipped, `fixed`, and `override` refuses them.

## Settings

None.

## Events

The module subscribes to `prompt.sent`, which dispatch's runner publishes as each turn goes that carried a prompt, from `turn` and from `steer` when the agent took the text into the turn in flight: `project`, `work_id`, `session_id`, `runner`, `role`, `agent`, `at`, and `prompts`, each `name`, `number`, `origin` and `version_id`, the versions served since the previous turn. The handler writes one row and reads nothing else. It publishes nothing.

## Sync and async

Every verb and the subscriber are synchronous; the runner delivers `prompt.sent` to the subscriber in a worker thread.

## Layers

The layer `agents`, made on the first record while the project has a metaform, with the variable "Which role and which prompt versions each agent session in this project was sent.", mutable and hideable. Its rows are kept in the module's table and linked from the layer, as memory's tables are from the memory layer, LAYER-001.

The table `sent`, version 1, at place `project`, so a clear keeps it: `session_id`, `seq` (the time in nanoseconds the row was written), `work_id`, `runner`, `role`, `agent`, `at` and `prompts` (JSON), keyed by `(session_id, seq)`, indexed by `runner`. `record` writes it; `sent`, `role` and `roles` read it.

## Lifecycle and cleanup

No start or stop hook, no tasks. Disabling the module stops the record; what was kept stays in the project.

## Modules relied on

dispatch, for the running sessions (its `sessions` verb) and for `prompt.sent`; workflow, for a skill's shipped text (its `skill` verb). Both are reached through their verbs and events, never by import. With dispatch off, no agent runs and none is listed; with workflow off, a skill's prompt is listed as `unread`.

## Systems supported

Linux, macOS and Windows.

## Resources owned

None beyond its table and layer.

## Installed and direct wheel

The same in both: it reads the packaged prompts.xml files through the loaded modules.

## Demonstration

```bash
metaform agents roles
metaform agents role name=worker
metaform agents override name=dispatch:work 'text=Work ticket <work_id/> with the map_work tool. <record/>' --confirm
metaform agents role name=worker        # dispatch:work: revision 2, origin edited
metaform agents drop name=dispatch:work --confirm
metaform agents sent session=<session id>
```

## Delivery observations and effective instructions

`agents sent session=<id>` includes `effective_instructions`, the latest observed delivery of each named component. It reports actual and selected version identities separately, rendered digest, shipped source identity, source kind/path, delivery path, fallback problems and assignment snapshot information when supplied by transport. Trial text, selected edits and malformed-source fallback remain distinguishable. Unknown historical metadata is reported as unknown. This report does not alter prompt selections or overwrite edits.

Native project instruction files are discoverable candidates, marked `discovered_not_confirmed_loaded` with a digest at inspection. The current ACP adapter does not expose which native/internal instructions its model received, their priority or its retained context. The manifest therefore records Metaform delivery history, not a complete model context inventory.

A startup marker is an explicit diagnostic observation only. Ordinary work does not request a marker check or its tool exchange. Matching it does not prove that a useful fact or responsibility survived. Omitting it does not invalidate delivery receipts or advance the context epoch. An actual completed compaction observation or explicit context replacement advances the epoch, making requested current grounding eligible on demand. It does not schedule a reconstruction turn. Explicit source and memory reads remain available.

Generic shown records describe content delivery hints, host discovery configuration (`catalog:`) or guide discovery history (`guide:`). Process sessions end with their process. Named sessions survive process replacement without age-based invalidation. Compaction resets content hints while preserving discovery history; it cannot establish which semantic facts survived.

Current generated responsibilities resolve through the same selected prompt store as other duties. Definition provenance (`source.definition_version_id`) and immutable definition history remain separate from the effective selected component. Existing assignment snapshots retain their historical bytes. If the home prompt store cannot resolve a generated duty, the project definition supplies its exact portable snapshot as `definition_fallback`, with an explicit problem and unknown selected version. An available selected edit always wins.

The existing `agent.role` provider offers `changes(ctx, session, role, bindings=None)` and `delivered_changes(ctx, session, notices)`. Changes returns compact source references only for instructions previously consumed by that session/epoch whose current rendered text differs. Equal text at a new version produces no notice. A reference carries an `agents_resolve` lookup for the current source and current/previous fingerprints, without delivering or acknowledging its body. The authored assignment resource continues to return its exact pinned snapshot. Dispatch can attach these references to the next natural turn, then acknowledge accepted notices. A later change remains eligible. The separate `change_notices` table deduplicates accepted references without claiming semantic retention or changing body receipts. This never starts a model or makes an initial role read mandatory.
