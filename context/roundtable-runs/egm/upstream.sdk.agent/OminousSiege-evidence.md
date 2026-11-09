# OminousSiege — evidence boundaries

The source snapshot contains one package manifest and five TypeScript files: adapter.ts, index.ts, models.ts, sdk-patch.ts, and tools.ts. Each was read. Searches for OpenCode/opencode returned no matches; imports of @openrouter/agent were confined to this adapter in the supplied snapshot.

Three distinctions govern the resolutions:

- SDK dispatch and adapter implementation are separate responsibilities. Adapter-defined tools do not invalidate the claim that an SDK executes tools, but do invalidate an implication that it supplies these tool implementations or persistent storage.
- File-tool path validation and a shell's working directory do not establish equivalent confinement. runShell invokes /bin/sh with the command unchanged; cwd selects where execution starts, not which paths a command can access.
- The private-method override and model-filter predicates are executable local evidence. The historical SDK bug, precise upstream endpoint implementation, and package-wide absence of built-in tools are described in local comments; upstream package internals and the tests named in those comments are not supplied. These claims should retain that evidence qualification.

The snapshot does not include Roundtable_ACP_Integration_Design.md, project-wide routing or usage information, node_modules, a lockfile, test files, or TypeScript configurations. No live upstream documentation or runtime behavior was used to stand in for the pinned package versions. Consequently neither an OpenCode migration decision nor SDK-wide behavior beyond the integration's demonstrated assumptions can be certified here.
