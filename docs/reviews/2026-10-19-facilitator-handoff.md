# Facilitator handoff

Tickets now progress from a confident JEV “none fits” result directly to the Facilitator. When JEV has no key, is unavailable, lacks observed OpenRouter credit, or cannot decide confidently, the ticket writer checks the specialist registry and assigns existing expertise or hands the ticket to the Facilitator. The fallback raises one brief board notice and requests the orchestrator's existing reconnect path. It does not require a user to relay the ticket.

## Workflow

1. Read `metaform://specialists`, which contains reusable expertise names, purposes and role URLs, without duty bodies. Framework responsibilities are excluded. Unchanged registry resources use context receipts; a changed registry or compaction makes the relevant read eligible again.
2. Reuse a suitable specialist. If several fit, record a brief reason for the closest match. If none fits, the Facilitator chooses a reusable domain name and authors the five-section XML system prompt supplied by the metaprompt.
3. Call `orchestration_publish_role` with the commission, selected role and match reason. For new expertise, also supply a reusable purpose and the XML duty. For existing expertise, omit the duty. The operation reuses an existing registered role without editing it, including when another Facilitator published it concurrently.
4. Publication binds the registered role version to the original ticket, places that ticket in To do and records its worker continuation. An explicit `column=backlog` holds it without queuing a worker launch. The actual assignment and board column are returned as receipts.
5. Report the specialist identity and actual outcome. The full prompt is stored at `metaform://role/<name>`; it is not echoed to the ticket writer or user. A failed registry read, publication, assignment or placement must be reported as a failure, not completed work.

The prompt is an executable workflow with named tools. Returning a specialist name in chat alone does not register it, assign it, or advance the ticket. Code owns continuation, replay protection and user-stop handling.

## Commands

- `orchestration_claim work=<id> role=<name>` assigns existing expertise or commissions that named expertise if missing.
- `orchestration_claim work=<id> create=true` asks the Facilitator to find or create expertise and choose its reusable name.
- `orchestration_publish_role request=<id> role=<name> purpose=<purpose> duty=<XML> match_reason=<reason>` publishes new expertise and continues the recorded assignment.
- The same publication command with no duty reuses registered expertise. `column=backlog` explicitly holds the continuation; To do is the default.

These command names are MCP names. CLI equivalents use `metaform orchestration <verb>`. Discover their declared arguments at `metaform://orchestration/tools`.

## Prompt and cost controls

The Facilitator checks existing specialists before authoring. A new prompt covers identity, objective, rules and constraints, methods and behaviors, and output formatting. It uses actionable second-person instructions. Ticket IDs, one-off objectives, paths, revisions and return destinations remain in assignments so the expertise can be reused.

The supplied metaprompt's assignment and placement steps are bound to real operations. Its full generated system prompt is the publication artifact; outward XML receipts carry the role URL and status instead of another copy of that artifact. Publication replies and continuation messages omit the prompt body. The helper receives the ticket text once, its relevant note and structured local functional context; repeated copies of the request, requested result and rendered graph are omitted.

Routing keeps the existing answer cache and one-decision-per-pass scheduling. An empty specialist inventory with available JEV configuration commissions the Facilitator without an empty-choice inference. A confident no-match result is recorded as creating, so further routing calls do not repeat classification or create another helper. Named missing-specialist requests share an active helper; unnamed requests remain independent until their expertise is identified. Concurrent publications of the same role name reuse the existing version.

A ticket held in Backlog does not spend on automatic routing or commission a helper. Releasing it makes it eligible again. The Facilitator is an automation helper outside worker slots, subject to the existing helper limits and automation controls. User-stopped assignments remain stopped. Repeated publication cannot revise the duty or launch duplicate workers. While expertise is pending, the sessionless delivery owner cannot bind a generic worker.

## Compatibility and validation

New helper assignments use `metaform://role/facilitator`. The old `role_creator` identity remains resolvable for already recorded assignments and retains helper admission and stop handling. No database schema changes are required. Generated role resolution now includes its stored version identity, including when expertise is reused.

Validation covers confident and uncertain no-match results, missing keys, credit fallback, no empty-choice inference, registry resource reads, immutable role reuse, publication replay, pending-role binding, original-ticket continuation, explicit Backlog placement, held-ticket release, compact receipts and one-time orchestrator wakeup. Existing orchestration, role registry and module discovery scenarios were also exercised.

Actual ACP/MCP fixture runs exercise named and unnamed specialist creation, role-URL reading, delivery of the original ticket and independent assessment. Additional fixture runs exercise worker-requested and GC-requested missing expertise. The lifecycle assertions allow the coordinator to read a completed result before its queued notice arrives, without demanding a repeated startup body, and keep the user-facing advisor available after workers finish. Provider decisions and ACP agents are deterministic fixtures; no paid model inference or live credit-account validation was used. The public role-resolver check verifies that all six workflow steps, five required sections and XML templates survive prompt rendering. The metaprompt is stored as literal text because ordinary nested prompt elements are substitution slots. Runtime fixtures also assert that the Facilitator receives the full metaprompt over MCP. Ruff, strict type checks and whitespace checks cover the changed code.

Restart the running web/MCP processes to load the new role, resource and prompt. Existing sessions may retain their pinned role version; a new session is needed to receive the updated Facilitator instructions.
