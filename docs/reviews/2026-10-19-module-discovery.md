# Module-owned MCP discovery

The previous catalog assigned tools to a hardcoded set of categories. A module developer could not add a new capability to discovery without accepting that taxonomy. Unkeyed HTTP clients received every available tool schema, and keyed workers received several unrelated tool sets at startup.

The module declaration is now the discovery contract. `metaform://modules` publishes active module names, summaries and tools URLs. `metaform://<module>/tools` lists commands belonging to that module, with their exact names and arguments. Reading the resource selects that module for the caller's session; opening another replaces the exposed schemas. Directory and resource reads share context receipts with catalog calls.

`metaform_catalog module=<id>` selects a module. `search=<words>` searches names, descriptions and module summaries with exact, prefix and typo-tolerant matching. Results identify their owning modules. A module argument narrows a search; searching neither selects a module nor executes commands. Stateless clients retain discovery tools and invoke commands through the catalog's tool/arguments path.

The old category tables, verb category declarations and `metaform://tools` index are removed. Extensions must remove `category=` from Verb constructors. Settings-screen categories are unaffected. Module rules continue to accompany the first use of that module's commands. Explicit user authority settings remain independent of discovery. Existing running MCP processes must restart to load the change.

## Measured startup payload

The [reproduction script](../../evidence/module-discovery/measure.py) measures serialized name/description/inputSchema fields in isolated homes. The same module setup is used before and after, with dispatch and orchestration enabled. Catalog descriptions and transport-specific search/fetch/view tools are excluded in both runs. These are byte measurements, not tokenizer counts or billed-token savings.

| Surface | Before: tools / bytes | After: tools / bytes |
| --- | ---: | ---: |
| Worker with session | 26 / 28,759 | 1 / 737 |
| Triage with session | 22 / 21,272 | 1 / 737 |
| Worker over stateless transport | 154 / 118,341 | 1 / 737 |
| Person over stateless transport | 154 / 128,596 | 1 / 737 |

Requested module schemas still cost context. This change removes their automatic upfront distribution. It does not measure subsequent provider history retention or solve the remaining universal deduplication work.

## Verification

The discovery/protocol selection passed 28 tests; six lifecycle tests passed, including surface changes and connected HTTP clients. Tests cover a newly added module requiring no MCP registry edit, exact module ownership, fuzzy search, isolated sessions, stateless invocation, shared delivery receipts, compaction, and user-configured restrictions. A broader integration selection passed 36 tests with two signal-test failures. Both reproduce on unchanged `e00f582`: the spin counter does not clear after a progress step, and the no-background-task assertion includes an unrelated log flush. Neither failure is a discovery regression.

The before/after 60-second idle measurements both recorded 0.03 runner CPU seconds (approximately 0.05% of one core), with zero adapter CPU seconds. The unrelated-event burst test passed with zero reads or scheduled work. Type checks and lint passed. No paid model calls were used.

The browser integration test could not start because Chromium is absent. Installing it was blocked by an HTTP 403 from the browser download endpoint. Protocol checks ran independently.
