# Review against the earlier system (metaform-tasks)

**From:** the Claude session reviewing `/home/rich/metaform-tasks`. The owner asked it to compare this design with what the earlier system did, and to act as a harsh critic. That session runs on another machine and read the design from GitHub (`RchGrav/topogee`, branch `intake-3.1`).

**Date:** 2026-11-03

**Status:** Everything below is advice. None of it is an owner decision.

- Two of its findings went into the design before the owner had seen them: commits `a4b78bc` (`goto` delivery) and `98151b9` (start-up). Those changes are marked as the agent's choice, so they are proposals that the owner can reverse.
- Nothing else from this review has been applied.

Each item gives the reviewer's finding, then this session's view.

---

## Decisions for the owner

### 1. Tickets have no write path

**Finding:** In metaform, ticket writes (`map_work`) were the most frequent call: 3,877 calls, about 36% of all calls. `TOPOGEE.md` section 2 puts tickets in a layer, but `project-map` has no answer for them yet.

**View:** Agreed, and this matters most. The path should be settled before Step 1 fixes the command set. There are two options:

- **(a) A system layer.** `tickets` is a system layer in `groups.json`. A ticket is a named record at its address, and a state change is an `update` of one field. No new command is needed.
- **(b) A module.** Tickets become a module with its own tool, like memory. This makes sense if tickets carry a workflow (take, done, assign). R-5.18 says a workflow's order of steps belongs in a prompt, so (a) fits that rule better.

### 2. Infrastructure before any proof

**Finding:**

- The plan builds a daemon, a forwarder, three line protocols, `log.db`, a viewer server and WebTransport before any agent has run intake on it.
- Intake uses one agent.
- **Fix:** make the first step the smallest thing that serves the JSON form to one agent.

**View:** Partly agreed.

- The owner asked for one server with many agents (positions 20 and 22), so the daemon stays.
- After Step 2, though, the plan already serves one agent over stdio from the JSON store.
- **Proposal:** add a gate after Step 2. A real test intake runs on it, using `Intake.md` 3.1, before Step 3 builds the daemon.

### 3. Which installation owns `~/.metaform`

**Finding:**

- A forwarder starts the server from its own checkout, and the server accepts only its own version.
- With worktrees, which `AGENTS.md` requires for each feature, one checkout owns the home and the rest are refused.
- Metaform hit this: its stores run from only one branch.

**View:** Agreed.

**Proposal:**

- `~/.metaform` belongs to one installed copy, named by the owner.
- Every development checkout and worktree sets its own `METAFORM_HOME`.

### 4. Size limits for large projects

**Finding:**

- Every size estimate rests on one 40 KB map.
- A game engine or a monorepo could be 100 times larger.
- The root read goes straight into an agent's context.

**View:** Agreed for what reaches an agent.

**Proposal:**

- Set a byte budget for the root read and for `goto` replies.
- If a reply goes over its budget, it says so, and the agent narrows the request.
- Holding the map in memory can wait until a large real project is measured (R-5.20).

### 5. One file per layer per address

**Finding:** Five layers on 2,000 addresses make 10,000 files.

**View:**

- The owner's own example is one file for each address (R-6.21: "a layer could be many files if its an address inbox it would be this_address_inbox.json").
- One file per layer, keyed by address, is simpler, and diffs stay readable.
- The owner should choose.

### 6. Case conversion

**Finding:**

- A camelCase store and a snake_case agent form tax every read and write with a conversion.
- They also add a class of refusals that exists only because there are two styles.

**View:**

- Position 16 is the owner's.
- The conversion now sits in one place, the store's edge, which keeps the cost small.
- Whether one style end to end is acceptable is the owner's call.

### 7. Memory calls before any `goto`

**Finding:**

- Before any `goto`, the agent is at `.`.
- So the memory tool should act on the root's graph. Refusing the call is wrong.
- This removes a refusal code, resolves the conflict with R-5.26 ("tools are not gated by where an agent stands"), and matches the Resources of `TOPOGEE.md`.

**View:** Agreed. This removes a rule. Not applied yet.

### 8. The memory count in `goto`

**Finding:**

- In metaform, a pushed notice, "N memories; N unread", drove `memory_read_unread` to 1,884 calls, the second most-called command.
- The count in `goto` will likely cause a memory read on nearly every first arrival.

**View:**

- The owner said an agent "sees a memory count", so that may be intended.
- The choice is between the total and the number not yet read.

### 9. The layer walk (D-7, D-13)

**Finding:**

- **D-7:** metaform's reads returned only effective layers. A raw read existed for internal integrity work only.
- **D-13:** select and mask rows sat at addresses and were walked from the trunk.
- Agents called `map_layers` 21 times. No evidence shows any agent used select or mask.
- **Suggestion:** drop select and mask, and add `inherits: true` to a layer's definition.

**View:**

- The evidence answers D-7: agents get effective layers, and raw stays internal.
- Dropping select and mask would undo Decided requirements R-6.1 to R-6.5, so that is for the owner alone.
- This design already defers the walk.

### 10. Text in `TOPOGEE.md` that conflicts with the rest

These are the owner's own text:

- **(a)** The Facilitator writes a skill per ticket. That is one agent briefing another, the handoff loss the design aims to remove, and it costs an inference per ticket.
- **(b)** The 50/55/60/65% context hooks with a hard stop are a sequence held in code, which R-5.18 would move to a prompt.
- **(c)** "Delivered only once" cannot be guaranteed. Only "sent once" can be.
- **(d)** A name derived from a hash of the first context collides for identical starts.

### 11. WebTransport

**Finding:**

- Node has no WebTransport server built in.
- WebTransport needs TLS certificates and an HTTP/3 library, all for a viewer on the same machine.
- WebSocket or server-sent events would give the same push.

**View:**

- `DECISIONS.md:15` is the owner's, and it rules out a WebSocket fallback.
- This design already moved WebTransport out of the map server.
- The cost is now stated, and the choice stays with the owner.

### 12. The refresh exception in `goto`

A `goto` to the address the agent is already at returns every part in full (commit `a4b78bc`). This bends the owner's rule of once per context.

**View:** Still needs the owner's yes or no.

---

## Working practice

### 13. The design grows with every finding

**Finding:**

- In two hours, the reviewer's advice added `server.json`, a file-system check, preloading, a refresh rule and a risk row, and removed nothing.
- That ratchet took metaform to about 180,000 lines.
- Agents agreeing with each other is not an owner decision.

**View:** Agreed. From now on:

- Advice is collected here for the owner before any of it is applied.
- Each addition names what it removes, or why nothing can go.

### 14. The development environment and the size of the design

**Finding:**

- The repository carries 31 `SKILL.md` files and 435 files under `.agents/skills`, over the owner's limit of 30 selectable things.
- The design document is 77 KB, about 20,000 tokens, about 2.3 times the size of the server code (34 KB), as the reviewer corrected.

**View:**

- Agreed that a builder should not need the whole design for Step 1. The plan can be split so each step stands alone.
- Trimming the repository's skills concerns the owner's environment. It is the owner's call.

### 15. Two sources of truth

**Finding:** The JSON files and `log.db` can disagree after a hand edit or a git checkout.

**View:**

- The files live under `~/.metaform`, not in a repository, so git does not reach them.
- The design should still say which is the truth:
  - The files are the truth at rest.
  - The log is the commit point.
  - A hand edit while the server runs is unsupported, and the server overwrites it.
- This is drafting work, not an owner decision.
- **One part is for the owner:** is version control a goal for the map? Problem 5 of the design argues for JSON partly because a database "cannot be ... kept in version control". The files are never in a repository, so that argument does not hold as written. Readability alone may still justify JSON. The reviewer raised this and accepted the rest of the correction.

### 16. Agent names (for the agents module)

**Finding:**

- Metaform's names come from a 16-bit hash, 65,536 names in all.
- Collisions reach about 50% at around 300 agents.

**Advice:** key an agent by a full hash of something unique, such as the session ID plus the start time. The readable name is only a label.

**View:** Agreed. Record it for the agents module.

---

## 17. How many tools kept metaform's map current (asked by the owner)

**Facts** (declarations in `metaform-tasks`; Claude calls from 1,789 saved transcripts, 2026-10-11 to 2026-11-02, 10,878 calls):

- **Map writes.** The map module had 43 MCP commands, 22 of which write. 17 of those 22 were never called.
  - The ticket command `work` made 3,877 calls, 97% of map writes.
  - `knowledge` made 96 and `refine` 19.
  - `select`, `mask`, `hide`, `tag`, `add-base`, `promote` and `critic` were never called.
- **Intake.** The intake module had 9 MCP commands, 5 of which write.
  - In Claude sessions, `start` made 2 calls and `element`, `purpose`, `remove` and `finish` made none. Codex ran intake; its calls were not counted.
- **Intake lifecycle.** `start` and `finish` came in `81399e91` (2026-09-26), from the owner's request to record the intake object by object as it is reasoned. The builder turned that request into a hidden draft that `finish` publishes. The lock, the verification marker, one-intake-at-a-time and discard came later, mostly with no stated reason.
- **Totals.** There were 194 MCP commands across all modules: 100 write, 85 read and 9 remove. Counting terminal-only commands, enabled modules had 261, and with the disabled module there were 285. 107 of the 194 were never called, and 44 had 20 or more calls.

**The reviewer's reading:**

- Almost everywhere, the tools mirrored storage: one command per row type or flag.
- The cause was the rule that the CLI and MCP must offer the same commands (`module.py:204`). That rule put every storage operation on MCP.
- **Caution:** `project-memory` copies the reference memory server's nine commands, which follow the same pattern of one command per table. In metaform the most-used memory write was `add_observations` (693 calls), and `delete_relations` had 9.

**This session's view:**

- The facts support the owner's point: how data is stored and the tools an agent gets are separate concerns (`DECISIONS.md`).
- The owner chose commands identical to the canonical memory server. The reviewer's caution is noted for the owner and changes nothing yet.

---

## 18. Evidence on R-5.18 from stopping a roundtable

The reviewer opened roundtable `120b9fed` through metaform's MCP tool, at the owner's go-ahead. The owner ended it so that he could rerun it from metaform's page, where its 3D stage follows only tables started from that page.

To stop the table, the reviewer's end call was refused with `instructions_required`. The call went through only after the reviewer read a per-tool instructions resource and retried with a session handle. A one-word stop took three calls.

**This session's view:** this is an observed instance of ceremony held in the tool rather than in a prompt (R-5.18). It also supports giving `project-map` refusals a remediation command the agent can send as is (R-5.24).
