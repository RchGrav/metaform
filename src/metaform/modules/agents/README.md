# Agent context evidence

This module records instruction deliveries, context epochs, compaction observations and exact prompt versions.
The public provider is `agent.context`. Context accounting does not create or assign roles.

Commands: `sent`, `receipts`, `confirm`, `updates`.

Assigned work and dynamic skills belong to the `tasks` module. Its `user_agent` definition is the user-facing task.
Live role definitions, source registries and role-authoring tools are removed. Immutable definition history and
accepted-delivery records remain readable. Schema version 6 removes the live factory tables, preserving retained
rows and creating the standard store-upgrade backup before migration.
