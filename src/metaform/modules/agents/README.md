# Agent context evidence

## Purpose

This module records instruction deliveries, context epochs, compaction observations and exact prompt versions.
The public provider is `agent.context`. Context accounting does not create or assign roles.

Assigned work and dynamic skills belong to the `tasks` module. Its `user_agent` definition is the user-facing task.
Live role definitions, source registries and role-authoring tools are removed. Immutable definition history and
accepted-delivery records remain readable. Schema version 6 removes the live factory tables, preserving retained
rows and creating the standard store-upgrade backup before migration.

## Template version

The recorded starting template version is 0.2.0. The context-only rewrite retains this module's delivery records.

## Declaration

`SUPPORTED_OS` names Linux, macOS and Windows. `DEPENDENCIES` is empty. `SHIPS_DISABLED` and `REMOTE_AGENT` are false.
`MODULE` declares four verbs, two subscriptions, the `agent.context` provider and its project tables.

## Common base used

`metaform.data` supplies the project store, prompt versions and table declarations.
`metaform.home` identifies the current home. `metaform.prompt_files` resolves exact selected instruction text.
`metaform.module` supplies contexts, verbs, subscriptions and the provider declaration.

## Prompts

The module records and compares instruction bodies selected by their owning modules.
It does not author task definitions or replace the recorded prompt version with current source text.
Native instruction-file discovery records hashes, without claiming the harness loaded those files.

## Verbs

Each CLI verb is also an MCP tool named `agents_<verb>`.

- `sent <session>` returns accepted prompt versions by turn, effective instruction metadata and current native-file evidence.
- `receipts <session>` returns delivery fingerprints and versions for the context epoch, without instruction bodies.
- `confirm checkpoint=<id> [key=<marker>]` records the calling session's response to its startup context check.
- `updates [name=<component>]` returns selected prompt merge history and retained conflicts.

## Settings

This module declares no settings.

## Events

`prompt.sent` records one turn's accepted prompt deliveries. `session.compacted` advances the session's context epoch.
The chassis announces table writes through its existing `map.changed` path.

## Sync and async

All declared verbs and subscription handlers are synchronous.

## Layers

The `agents` layer is mutable and hideable. It records which prompt versions each session received in the project.
The module creates it after the first recorded delivery when an active map exists.

Tables use version 6, compatible from 6, and live at project scope:

- `sent`, keyed by session and sequence, stores accepted prompt metadata for each turn.
- `definition_history`, keyed by name and sequence, preserves immutable historical definitions.
- `contexts`, keyed by session, stores the epoch and its reason.
- `receipts`, keyed by session, epoch and component name, stores accepted delivery evidence.
- `delivered_text`, keyed by session, epoch and fingerprint, tracks delivered text identities.
- `change_notices`, keyed by session, epoch and component name, records changed instruction notices.
- `context_checks`, keyed by session, stores startup checkpoint and confirmation observations.

## Lifecycle and cleanup

There are no module start or stop hooks and no agent processes owned here.
Delivery history remains in the project store when a session ends.

## Modules relied on

Dispatch publishes prompt-delivery and compaction events. Other modules use the `agent.context` provider through the common base.
Task definitions and assignments are owned by `tasks`.

## Systems supported

Linux, macOS and Windows.

## Resources owned

The module owns its context and delivery records. Store connections and prompt files use the common base's lifecycle.

## Installed and direct wheel

Both forms use the same declarations, project tables and instruction-version store. No external program is needed.

## Demonstration

From a registered project folder:

```bash
metaform help agents
metaform agents updates
```
