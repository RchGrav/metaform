# Roundtable 7: a4c0c884-multiplayer-extensible-world-with-chunks

This report was written from the table's record alone, by no model. The table ended because every topic was discussed, synthesized, ranked, explained and summarized.

Opening: A person working on a project brings you a question about one part of it. The part is at the Address code.adapter.context, and here is what the project's functional map holds about it: the element, what it receives and provides, and why.

# Gateway issue context

## Gateway issue context

`code.adapter.context`, SE

Paths: src/metaform/modules/mcp/tests/test_mcp.py, docs/reference/metaform-mcp-server.md, src/metaform/modules/paperclip/__init__.py, src/metaform/modules/mcp/server.py, src/metaform/module.py, src/metaform/context.py, artifacts/swarm-2026-10-11/PAPERCLIP-INTEGRATION.md

### paperclip receives from Gateway issue context

Copies gateway identity into request context. Includes agent, issue and run identifiers. Scopes delivery by agent and run. Uses agent and issue without run. Preserves server environment.

Why: Resolve the correct issue and run for each gateway call without repeating context across distinct runs.

What has been learned and kept about this part:
- None yet.

The question: Multiplayer extensible world with chunks and regions instead of redstone and voxels it uses wasm and a wasm bus ..  agents can extend world which is based on real physics...   regions can have different properties and borders.   like a multiverse A shared, playable 3D canvas where the person and agents edit the same world through one operation format, and every meaningful object and rule keeps its purpose, constraints and decisions through Metaform (I1). Its core is an authoritative scene service (I5) over a portable, renderer-independent world format with one runtime for editor, web export and headless checks (I4). Agents act through a small typed vocabulary (I7) with spatial perception (I8), propose edits as reviewable patches against a revision (I9), and prove intent with bounded simulation checks (I14). Build it JavaScript-first: TypeScript, Three.js, Rapier WASM, Web Workers (I2, I16).

You can read the project's files in the folder you are in. You cannot change anything, and nothing you say changes the project; the person reads the table's answer and decides. Build on what the others contribute, add what only you can add, and keep going until the question is answered.

## Seats

- Opus (acp:claude/opus): 7 slots, 5 submissions, 4 kept, active
- Astra (acp:codex/gpt-6-astra): 7 slots, 6 submissions, 6 kept, active
- Sol (acp:codex/gpt-6.1-sol): 7 slots, 4 submissions, 4 kept, active
- Fable (acp:claude/fable): 7 slots, 5 submissions, 5 kept, active

## Topic 1: Multiplayer extensible world with chunks and regions instead of redstone and voxels it uses wasm and a wasm bus ..  agents can extend world which is based on real physics...   regions can have differe

### Ideas, as Opus synthesized them

I1. Gateway attribution of world patches: Every proposed world patch is tagged at the gateway with the agent, issue and run that made it, plus the world ID and the base revision it applies to (T02). This lets reviewable patches (the earlier I9) be traced back to whoever started them.
I2. Identity is not authority: Knowing who made a call does not give them any power. WASM modules get explicit capabilities, limited by region, allowed operations and resource budgets. The authoritative scene service checks every mutation, and no extension can skip that check (T02).
I3. Cross-region border policy with atomic acceptance: Any edit that crosses a region border needs an explicit border policy, and the whole edit is accepted or rejected as one unit. This stops an extension from escaping a region's physics or permissions by moving an object across the boundary (T02).
I4. Immutable envelope on the WASM bus: Each operation carries a fixed envelope: worldId, agentId, issueId, optional runId, operationId and baseRevision. It is captured when the call arrives and passed through worker messages, queued jobs and simulation results using per-request context, and operationId is deduplicated at commit. Test it with two interleaved runs and with a call that has no runId (T03). T03 also said to "preserve the server environment"; T09 disputed this (see I11).
I5. Envelope as data, replay uses recorded identity: This follows Metaform, where identity is a plain dict on a Context built once per call (`context.py`). The world envelope should likewise be data, not shared global state. The headless check runtime builds its own Context from the identity recorded on the patch, not from the worker's, so a replayed or re-verified patch is still credited to its original author (T04). T04 also suggested Metaform's fallback to the process's own agent session; T09 rejected that and T12 agreed (see I11).
I6. Outbound delivery scoped by agent and run: Events sent back out, such as perception snapshots, review results and simulation verdicts, are routed by the same agent and run keys. Otherwise an agent could receive another run's rejection and retry the wrong patch. Calls with an issue but no run go to an issue-level draft queue that outlives runs, so a later run can pick up pending patches instead of starting over (T05).
I7. Draft keying and explicit resume: A missing runId stays missing. It never borrows the worker's current run and never acts as a wildcard for delivery. Drafts that persist are keyed by world, agent and issue, and a new run only gets access through an explicit resume operation. Original authorship stays unchanged and the resuming run is recorded separately. This keeps an issue shared by several agents from turning into an accidental shared inbox (T07).
I8. Authenticated replay with a separate verifier: A recorded identity only proves attribution if the gateway actually authenticated it. On replay, keep the original author, record the verifier separately, and recheck current permissions before commit (T06).
I9. Verdicts bound to dependencies and expiring when they change: A simulation verdict is tied to the patch hash, the base revision, the WASM module hashes and the physics configuration. It becomes invalid when any of those change, so a patch validated under one region's rules cannot be committed under another's (T06).
I10. The extension as a fourth identity: When WASM code runs physics or rules inside a region, its mutations carry the caller's agent, issue and run plus the hash of the module that ran. A region's decision log can then say "agent X, via extension Y@hash, under rule Z". This keeps a bug in a shared extension from looking like misconduct by every agent who called it, and makes rollback by extension version possible. It mirrors how Metaform keeps `module` separate from `identity` (T08).
I11. No fallback identity and no ambient identity in pooled workers: In a shared world, a call with no identity must not be credited to the server's own agent session. It carries an explicit person or anonymous principal, or it is rejected. Pooled Web Workers and WASM instances serve many runs, so they must never read identity from globals or environment variables (T09). T12 accepted this: the fallback suits a single-user CLI but is wrong for a shared server.
I12. A world runtime principal for autonomous activity: Physics and installed rules keep running after the installing run ends. Those ticks are credited to an explicit world runtime principal, linked to the rule version and the patch that installed it. The installer is kept as history, not as ongoing authority, so autonomous events don't inherit expired run permissions or flood a dead inbox. Events go to current subscriptions, and causation IDs are kept for replay and debugging (T10).
I13. Commit log with an idempotent outbox to Metaform: Each accepted patch is stored in the authoritative commit log with its purpose, constraints, decisions and attribution. It is then published to Metaform through an outbox keyed by commit ID, so retries don't create duplicates. A Metaform outage cannot leave an accepted object with no recoverable intent. Per-frame physics state stays out of this path (T11).
I14. Pooled-worker leak test: Send one pooled worker patch A (run 1), then patch B (no run), then a check for A. Assert that B's commit record has no runId and that A's verdict goes only to run 1. The test fails if identity leaks through a module-level global and passes if envelopes are passed explicitly (T12).
I15. Split by hop with a session handle: This resolves a tension: the gateway exists so callers don't repeat context, yet I4 passes a full envelope everywhere. An agent binds agent, issue and run once and gets a session handle back. The scene service then expands each operation into the full envelope used by workers, checks and the commit log. Agents never write identity themselves, so they can't forge it or let it drift (T13). Refinement: the handle must bind one specific run, not just a connection, since one connection can carry several runs, and the binding never changes when a new run starts (T14).
I16. Revocation checked at commit time: A queued patch can finish simulation after its run was cancelled, so permissions are checked again at commit. Cancelling a run blocks its future commits but keeps its accepted history. Test a cancellation that lands between successful validation and commit (T14).
I17. Authorship separate from commit authority: A person can approve an agent's saved proposal after the agent's run has ended. The approval becomes a new commit request under the person's current permissions, linked to the original agent and run as history, with stale checks run again. This way, cancelling a run doesn't make its useful proposals permanently unusable (T15).
I18. Who constructs the envelope, and where trust actually lives: T16 proposed that the scene service be the only place envelopes are built, with workers getting a frozen read-only copy, so that unforgeable identity is a property of the type (like Metaform's MCP server being the only builder of Context). T17 corrected this: postMessage copies the object and drops Object.freeze, and WASM only sees raw bytes, so any worker could send back an altered copy. Resolution (T17, accepted by T20): workers return only an envelope ID plus their results, and at commit the service looks up the real agent, issue, run and module hash in its own table and ignores any identity the worker sends.
I19. Untrusted extension execution versus a trusted checker: A valid envelope ID doesn't make a worker's verdict trustworthy. WASM only proposes effects. Host code enforces region permissions, resource limits and simulation assertions, and a module cannot certify its own compliance. Each result is tied to a server-issued job and accepted only from the worker assigned to that job (T18).
I20. Envelope table lifecycle: The ID lookup in I18 means the service has to store the envelope table and clean it up. An entry outlives its worker job and is retired when its operation commits or is rejected. Issue-level drafts keep their own copy of the resolved identity, so a later resume never needs to look up a retired ID (T20).
I21. Durable deduplication that survives cleanup: Retiring an envelope must not remove the evidence used for deduplication. The commit record durably keeps the operationId, payload hash and outcome. An identical retry (for example, after a lost acknowledgement) gets the original outcome back, and reusing an operationId with different content is rejected. This stops a reconnect from applying the same edit twice (T22, extending I4's commit-time dedup).

### Rankings, best first

Opus: I1, I18, I2, I19, I15, I4, I11, I6, I9, I21, I16, I17, I10, I12, I7, I13, I3, I5, I14, I8, I20

Astra: I2, I11, I18, I9, I21, I13, I16, I4, I19, I17, I1, I7, I12, I3, I8, I14, I15, I10, I6, I5, I20

Sol: I2, I11, I18, I4, I21, I9, I19, I3, I16, I1, I13, I7, I12, I8, I17, I15, I14, I10, I5, I6, I20

Fable: I18, I2, I15, I11, I19, I4, I1, I9, I21, I16, I7, I6, I17, I12, I13, I10, I3, I8, I5, I14, I20

### Borda count (derived)

Derived: a Borda count over the rankings that were read (of n ideas, first earns n - 1 points, last none). The raw rankings are the record; nothing in the protocol depends on this.

I2. Identity is not authority: 77 points
I18. Who constructs the envelope, and where trust actually lives: 75 points
I11. No fallback identity and no ambient identity in pooled workers: 69 points
I4. Immutable envelope on the WASM bus: 60 points
I19. Untrusted extension execution versus a trusted checker: 59 points
I9. Verdicts bound to dependencies and expiring when they change: 57 points
I1. Gateway attribution of world patches: 55 points
I21. Durable deduplication that survives cleanup: 55 points
I16. Revocation checked at commit time: 47 points
I15. Split by hop with a session handle: 43 points
I13. Commit log with an idempotent outbox to Metaform: 36 points
I7. Draft keying and explicit resume: 34 points
I17. Authorship separate from commit authority: 34 points
I12. A world runtime principal for autonomous activity: 30 points
I3. Cross-region border policy with atomic acceptance: 28 points
I6. Outbound delivery scoped by agent and run: 25 points
I10. The extension as a fourth identity: 19 points
I8. Authenticated replay with a separate verifier: 17 points
I14. Pooled-worker leak test: 12 points
I5. Envelope as data, replay uses recorded identity: 8 points
I20. Envelope table lifecycle: 0 points

### Top three, as each seat explained them

Opus: **I1, gateway attribution of world patches.** This is what this part of the project is for, applied to the world. The Address copies agent, issue and run into the request context. Pinning that identity, plus the world ID and base revision, to each patch is what makes reviewable patches (the original I9) and Metaform's purpose and decision record (the original I1) traceable. Most of the other ideas refine I1: the envelope, delivery scoping, draft resume, the outbox and dedup all assume it exists. So it ranks first because the rest depend on it.

**I18, where trust actually lives.** This is the point where the discussion found a real mistake. The design looked sound but would have failed in the browser and WASM runtime the project picked (I2/I16). Structured clone drops `Object.freeze`, and WASM only sees bytes, so a "frozen envelope" type gives no guarantee across a worker boundary. Workers should send back only an envelope ID, and the scene service should resolve identity from its own table. That makes the authoritative scene service (I5) the only source of truth for who did what. I15, I20 and I21 all depend on this decision, so I ranked it above them.

**I2, identity is not authority.** Attribution answers who made a call; it doesn't decide whether that call may change the world. The project wants regions with their own physics, rules and borders, extended by agents through WASM. In that setup the main risk isn't misattribution but an extension doing more than it should. I2 keeps the two concerns apart: capabilities are scoped by region, operation and budget, and the scene service checks every mutation. I19 (no self-certifying modules), I3 (border policy) and I16 (revocation at commit) each apply this principle to one case, so I put the principle above them.

**Why these over the rest.** These three are the decisions that would be most expensive to get wrong late. If attribution or trust is put in the wrong place, every patch already in the commit log is suspect, and changing it touches every worker and extensio

Astra: 1. **I2 establishes the permission model.** Attribution tells us who requested a change. Capabilities determine whether they may make it. Region, operation and resource limits let people install useful extensions without granting unrestricted control of the world. Every other mechanism depends on the scene service enforcing this distinction.

2. **I11 prevents identity leakage between users and runs.** A process-level fallback can silently credit a person’s edit to a server agent. Ambient worker state can attach one run’s identity to another run’s operation. Explicit request context removes both failure paths. This is especially relevant when adapting gateway behavior from a single-user tool to a shared service.

3. **I18 places trust at the actual enforcement boundary.** TypeScript types and frozen objects cannot authenticate data returned across worker or WASM boundaries. Resolving a job’s identity from service-owned records prevents a worker from choosing its own attribution. The lookup must also be authorized: possession of an envelope ID alone grants no permission.

These rank above persistence, replay and delivery refinements because those mechanisms can faithfully preserve or distribute a wrongly attributed, unauthorized operation. Establishing authority, isolating identity and protecting the service’s authoritative records makes the remaining ideas dependable.

Sol: 1. **I2 sets the core authority boundary.** Attribution tells us who requested an edit. Capabilities and scene-service validation determine whether it may happen. This makes agent extensions workable in a shared world: a module cannot acquire permission merely by carrying a valid identity. Logging, replay and delivery depend on this distinction.

2. **I11 prevents silent misattribution.** A server-session fallback can credit a person’s edit to an agent, while ambient identity in pooled workers can carry one run’s identity into another. Those errors undermine permissions, audit history and result routing at once. Explicit principals and request-local context address the failure at entry.

3. **I18 puts enforcement where it can be trusted.** A frozen envelope or TypeScript type cannot establish trust across execution boundaries. The scene service must retain authoritative context and resolve returned job IDs against it, ignoring worker-supplied identity. This turns I2 and I11 into an enforceable design. It still needs I19’s separate checks on the returned effects.

These rank above lifecycle, deduplication and replay refinements because those mechanisms can operate correctly yet preserve the wrong actor or accept an unauthorized edit if these three foundations are missing.

Fable: **I18 first** because it is the one idea that was actually tested and corrected in discussion, and the correction changes the architecture. My own T16 proposal (frozen envelope as a type guarantee) was wrong: structured clone drops `Object.freeze`, and WASM sees bytes. The resolution, workers return only an envelope ID and the scene service looks up identity in its own table at commit, is the single mechanism that makes every other attribution idea hold. Without it, I1, I4, I5 and I10 are conventions a buggy or hostile worker can violate. It also mirrors what Metaform already does: `context.py:31-45` is the one builder of `Context`, and verbs downstream only read `ctx.identity`.

**I2 second** because it names the distinction the whole topic depends on. The gateway context in Metaform is identity (agent, issue, run), not permission. Conflating them in a multiplayer world would mean "the gateway said agent X" becomes "agent X may mutate region R". Making capabilities explicit per region, operation and budget, and having the scene service validate every mutation, is what makes I16 (recheck at commit), I17 (approval under the approver's permissions) and I19 (host enforces, WASM proposes) coherent. They are all consequences of I2.

**I15 third** because it resolved a real tension rather than adding a rule. T03/T09/T12 all wanted a full envelope on every message, while the gateway's stated purpose is to stop callers repeating context. Binding once per run to get a session handle, then expanding at the scene service, satisfies both and closes the forgery hole: agents never write identity, so it cannot drift. Astra's refinement (bind a specific run, not a connection) is what makes it safe under multiplexing. Combined with I18, it fixes identity at exactly two points, entry and commit, with nothing in between trusted.

I ranked I20 and I14 low not because they are wrong but because they are consequences and tests of the top three; they follow once I18 and I15 are in place.

### Bottom three, as each seat explained them

Opus: None of these three is wrong. Each one depends on a decision ranked higher, so it adds the least on its own.

**I14 (pooled-worker leak test)** checks I11 (no ambient identity) and I18 (envelope ID lookup). It's a good test to have. But once workers can only return an envelope ID, a leaked global can't change who gets credited, so the test mainly confirms that design. It also repeats T03's earlier "two interleaved runs" test.

**I8 (authenticated replay with a separate verifier)** is mostly covered elsewhere. Gateway authentication is already assumed. Rechecking permissions before commit is I16, and keeping the original author while a new party acts is I17. The separate verifier record is the only new part, and that's an audit detail.

**I20 (envelope table lifecycle)** is housekeeping that I18 creates. Expiring entries when an operation commits or is rejected is the obvious policy. The real risk, losing dedup evidence when entries are cleaned up, is handled better by I21.

Astra: - **I6:** Scoped delivery is essential, but the idea also makes an unsupported product choice: a missing run automatically creates an issue-level draft. I7 improves this with explicit resume and isolation by world, agent and issue. Runtime events also need current subscriptions.

- **I5:** Explicit context data is sound, but replaying recorded identity leaves authentication and authority unresolved. Original authorship must remain separate from the verifier and current commit permissions. I8 and I17 make those distinctions explicit.

- **I20:** Cleanup is a secondary implementation concern, and retiring entries on commit or rejection needs care around outstanding jobs, late results and retries. I21 supplies the more consequential invariant: durable deduplication survives cleanup. The exact retention policy can follow the execution model.

These ideas remain useful, but contribute less independently or need refinement before adoption.

Sol: - **I5:** Treating context as data is sound, but other ideas cover it with stronger trust boundaries. Replay must distinguish original authorship from the verifier’s current authority. Copying recorded identity alone does not establish either authentication or permission.

- **I6:** Scoping outbound delivery is essential. Its weaker part is automatically putting calls without a run into an issue-level queue. That assumes persistence and resume behavior, and issue-only routing risks mixing agents. I7 supplies the missing boundaries.

- **I20:** Cleanup matters operationally, but its design depends on job recovery, retries and retention requirements that remain unspecified. Retiring context immediately after commit or rejection may be premature. I21 establishes the more fundamental requirement: cleanup must preserve durable deduplication evidence.

Fable: All three are mine, and all three were superseded or absorbed by later ideas.

**I5** was half wrong. The "envelope as data" part survives, but I bundled it with Metaform's fallback to the process's own agent session (`context.py:44`), which T09 correctly rejected for a shared server. The useful half is restated more precisely by I8 (replay keeps author, records verifier, rechecks permissions), so I5 adds little on its own.

**I14** is a good test but only a test. It verifies I11 and I18; it introduces no design. Once envelope IDs are looked up at commit, the leak it guards against is structurally impossible, so it becomes a regression check rather than an idea.

**I20** is bookkeeping that follows mechanically from I18: if you have a lookup table, you must retire entries. The one non-obvious point, that drafts keep their own copy of identity, is small, and I21 immediately showed that retiring the table is not enough for dedup anyway. It belongs in the implementation notes, not the design.

### Host summary by Opus

# Summary of the models' rankings: identity and authority in the multiplayer WASM world

## Overall result

All four models agree on the core: **authority is separate from identity, and the scene service is the only trusted source of who did what.** I2, I18 and I11 are near the top of every list. I20 is last on every list.

Approximate average positions (1 = best, 21 = worst):

| Idea | Opus | Astra | Sol | Fable | Avg |
|---|---|---|---|---|---|
| **I2** Identity is not authority | 3 | 1 | 1 | 2 | **1.75** |
| **I18** Where trust lives (envelope ID lookup) | 2 | 3 | 3 | 1 | **2.25** |
| **I11** No fallback or ambient identity | 7 | 2 | 2 | 4 | **3.75** |
| I4 Immutable envelope | 6 | 8 | 4 | 6 | 6.0 |
| I19 Untrusted extension vs trusted checker | 4 | 9 | 7 | 5 | 6.25 |
| I9 Dependency-bound verdicts | 9 | 4 | 6 | 8 | 6.75 |
| I21 Durable dedup | 10 | 5 | 5 | 9 | 7.25 |
| I1 Gateway attribution | 1 | 11 | 10 | 7 | 7.25 |
| … | | | | | |
| I8 Authenticated replay | 20 | 15 | 14 | 18 | 16.75 |
| I14 Pooled-worker leak test | 19 | 16 | 17 | 20 | 18.0 |
| **I5** Envelope as data, replay | 18 | 20 | 19 | 19 | **19.0** |
| **I20** Envelope table lifecycle | 21 | 21 | 21 | 21 | **21.0** |

## Most favored ideas and why

**I2: identity is not authority.** Astra and Sol ranked it first, Fable second and Opus third. They all gave the same reason: attribution says who asked, and capabilities decide whether the change is allowed. In a world where agents install WASM extensions with region-specific physics, the main risk is an extension doing more than it should, not misattribution. Opus and Fable both described I16, I17, I19 and I3 as applications of I2. That was their reason for ranking the principle above those ideas.

**I18: where trust actually lives.** Fable ranked it first and the others second or third. Every model cited the same technical correction: `postMessage` structured clone drops `Object.freeze`, and WASM only sees bytes, so a "frozen envelope" type guarantees nothing across a worker boundary. Opus and Fable said this was the point where the discussion caught a real design error. Fable acknowledged that the flawed T16 proposal was its own. Astra added that holding an envelope ID must not grant any permission by itself. Sol noted that I18 still needs I19 to check the effects a worker returns.

**I11: no fallback or ambient identity.** Astra and Sol ranked it second. Both said one failure at the entry point would corrupt permissions, the audit history and result routing at the same time. That failure is either a server-session fallback crediting a person's edit to an agent, or a pooled worker carrying one run's identity into another. Opus ranked it lower, at 7, but did not argue against it.

**Other top-three picks:**
- **Opus put I1 first** because almost every other idea assumes patches are already attributed. Envelopes, delivery scoping, resume, the outbox and dedup all build on it.
- **Fable put I15 third** because it removes a real conflict: the gateway's purpose is to avoid repeating context, yet I4 sends a full envelope everywhere. Binding once per run at entry and resolving identity at commit fixes identity at exactly those two points.

Astra and Sol both explained their top three the same way. Persistence, replay and delivery mechanisms can work perfectly and still store or deliver an edit with the wrong author or without permission, so the foundations come first.

## Least favored ideas and why

**I20: envelope table lifecycle.** All four ranked it last. They called it housekeeping that follows from I18. Each model also said that I21 covers the one consequential risk, which is losing dedup evidence during cleanup. Astra and Sol added that retiring entries on commit or rejection may be too early, given late results, retries and job recovery.

**I5: envelope as data, replay uses recorded identity.** Astra, Sol and Fable each put it in their bottom three. Replaying recorded identity does not settle whether it was authenticated or whether the caller still has authority. I8 and I17 state those distinctions more precisely. Fable, which authored I5, said it was "half wrong" because it was bundled with the `context.py` session fallback that T09 rejected.

**I14: pooled-worker leak test.** Opus and Fable put it in their bottom three. It verifies I11 and I18 but adds no design. Once identity is looked up at commit, a leak can no longer change who gets credited, so the test becomes a regression check. Opus also noted that it overlaps T03's interleaved-runs test.

**I6: delivery scoped by agent and run.** Astra and Sol ranked it 19th and 20th. Both agreed that scoped delivery is essential. They objected to the automatic issue-level draft queue for calls with no run, which risks mixing agents. They said I7's explicit resume, keyed by world, agent and issue, is the better version.

**I8: authenticated replay.** Opus put it in its bottom three because I16 and I17 already cover most of it. Only the separate verifier record is new, and Opus called that an audit detail.

## Where they agreed

- I2, I18 and I11 form the foundation, and the scene service owns identity.
- The low-ranked ideas are not wrong. They are tests, bookkeeping, or earlier versions that later ideas improved on: I21 over I20, I7 over I6, and I8/I17 over I5.
- I19 is a necessary companion to I18, because a valid envelope ID does not make a worker's verdict trustworthy.

## Where they disagreed

- **I1 (gateway attribution):** Opus ranked it 1st as the base everything else assumes. Astra (11th) and Sol (10th) ranked it in the middle, apparently treating attribution as less important than authority and isolation.
- **I15 (session handle):** Fable ranked it 3rd and Opus 5th, but Astra and Sol put it 17th and 16th. Fable valued it for resolving a design conflict, while Astra and Sol seemed to treat it as an ergonomic refinement.
- **I6 (scoped delivery):** Opus ranked it 8th, while Astra and Sol placed it near the bottom over the draft-queue assumption.
- **I13 (commit log with outbox):** Astra ranked it 6th, while Opus and Fable put it 16th and 15th.
- **I3 (border policy):** Sol ranked it 8th, while Opus and Fable both put it 17th. Opus treated it as one application of I2 rather than a separate principle.
