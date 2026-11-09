# Pro assignment: complete the final functional-core specification without losing source semantics

You are a **critical specification engineer**, not an autonomous replacement architect or repo-code migrator. The owner has suffered costly unauthorized implementation drift; rigor, cost control, and source fidelity matter. Your objective: produce an engineering-complete Metaform specification from this package **without** silently importing prior code or deciding unresolved design policy.

Read `00_authority/README_READ_FIRST.md`, then the corrected core candidate, original XML, latest original JSON and correction ledger. Carry every substantive semantic invariant forward. Treat the XML's flattened serialization and one-object-per-tool-call instructions as historic **implementation mechanics**, not requirements for the new tool API.

Tasks, in order:

1. Construct a fully numbered requirement set for namespace, provider joins, reference integrity, semantic intake, three-mode read, batch apply, error/idempotency semantics, context delivery, inboxes, directed messaging, orchestration, peer reputation, chassis/module lifecycle, MCP/CLI boundaries and the three embodiment paradigms.
2. Derive and separately label **physical storage/DAO design proposal** from the user-approved logical schema. Do not present a proposed LadybugDB table/index layout as if previously approved; no raw backend internals in the agent's API.
3. Specify input/output JSON Schemas for the proposed two functional agent operations, including examples and failure cases, and keep separate from logical graph serialization. Identify any fields requiring a brief owner decision; propose defaults with rationale but do not silently choose where semantics are consequential.
4. Build an acceptance matrix from each requirement to actual observable behavior/test, including no duplicate paid model context, ICE during intake, final closure, agent and node mailbox ack, cost transparency, deterministic agent identity, and absent unsolicited informational prompts.
5. Perform a gap analysis versus original XML and older draft. Report every weakened or omitted invariant, conflict, proof limitation and provenance. Prioritize by severity. Do not change original XML/JSON or mutate GitHub.
6. Construct a dependency-ordered implementation plan with clean-room read-only legacy reconnaissance and a mandatory **owner prompt review** before copying any prompt into the new implementation. No old source code transfer.

**Output:** complete candidate spec, separate machine-readable contracts/examples, acceptance matrix, decision register and implementation plan. A decision register is an owner-review artifact, **not** a reason to stop the long pass and ask a question. Keep every decision tentative, with alternatives and consequences. Report what is evidenced vs proposed vs unknown. Preserve original field names and semantic vocabulary. Do not invent tool families, expand the MCP catalog, add content-gating policy or repair unrelated legacy code.

**Hard prohibitions:** rename `op` to `purpose`; rename EF to `function` in provider record; resurrect `join type="purpose"`; make an agent edit SQL/Cypher/rows; require seven MCP tools for the functional graph; send progress/completion/log events as model messages; pull neighbor knowledge via local view; wipe legitimate ICE/final proof checks; expose reviewer attribution; make two agents mandatory; silently edit the canonical original procedure.
