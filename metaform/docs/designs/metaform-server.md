# Metaform functional map server: JSON maps behind one live server

> **Storage superseded (2026-11-07).** This document designs JSON file storage (`map.json`, layer files, a log). The founder never decided JSON for the map. Maps live in LadybugDB: `metaform.lbug` for the chassis and one `project.lbug` per project (`metaform/SPEC.md` R-4.1; the founder's documentation set, section 1.2). Read its storage sections as history; its other positions stand only where the specification still holds them.

* **Author:** Rich
* **Date:** 2026-11-03

## Overview

This brief collects a six-lens brainstorm on a concept the founder confirmed as the hypothesis to examine. The lenses were design, codebase details, zoom-out, comprehension, implementation readiness and structural.

The concept: Topogee narrows to one purpose. Intake builds the project's map, its functional form and intent, as one plain file. Only one agent at a time holds the map-updating role. That role is carried as a skill, and the same skill writes tickets homed at functional addresses. Every other writer (memories, inbox messages, sessions) gets its own file. The map then needs neither LadybugDB nor a long-running chassis. (Revised later in the session: the MCP server has its own running back end, and the chassis hooks it when present. See positions 9 and 10.) The Node MCP server delivers only the context and skills that fit the task, seen from where the agent stands. Orchestration (ACP harness, role assignment, agent identity) is a separate part, linked through the map.

The method is not under review here. That covers the roles, the want record, the address rules, the intake vocabulary, the layer walk and the claims about how models benefit (`docs/pushback.md:201-209`). Every finding below asks whether this build plan carries the method. Each item is written as a gap in our build. The answer to any of them may be "already considered" or "handled elsewhere".

Status of the inputs. The founder is questioning whether to drop Ladybug for the map. That is not a decision. The chassis language (D-9) is undecided, and so is whether the chassis belongs inside the MCP server. "One agent at a time holds the map-updating role" and "where there would be more than one writer they each get their own file" are the founder's stated positions from this session.

## Analysis

**Round 2 (revised concept, positions 1–17).** The full findings are in [`metaform-server-round2.md`](metaform-server-round2.md): 6 blockers, 21 major, 5 minor, and 19 new open questions. All six lenses completed. The blockers:

- **B1, B2, B3 resolved by position 22.** Their original text follows.
- **B1 Start-up.** Nothing says who starts the server, where its endpoint is, what keeps it to one copy, or what a forwarder does while it is down. "Per machine" conflicts with `METAFORM_HOME`, which tests and worktrees use to keep separate homes.
- **B2 Routing.** With one server for all projects, a call has no way to name its project. R-5.3's "the server starts for one project folder" no longer applies, and `home.ts:100-109` registers a new project for any folder it is given.
- **B3 One writer under the home.** Replacing R-4.4 and R-4.5 removes the only rule that makes one process the writer. If outside parts write layer files directly, they skip validation, the log and announcements, and search goes stale.
- **B4 Where want records live.** Resolved by position 18: wants is a layer included in intake, so an address read returns this element's own `why`, `how` and `intent`.
- **B5 No command returns layer content.** Positions 12, 13 and 17 return names and locations only. R-5.21 and R-5.22, which read a named layer, are not stated to still hold. The inbox is out of this question: position 21 moves it to later work.
- **B6 The spec has no place for the server**, and more Decided lines conflict with the positions than this brief listed.

Round 1 findings follow. They are kept for the record, and several are resolved by positions.

Severity: 🔴 Blocker, 🟡 Major, 🟢 Nit. "Observed" means a reviewer saw it at the cited line. "Inferred" means the reviewer's reading.

### 🔴 B1. The concept conflicts with Decided requirements and founder files, and no Open item covers it
*Lenses: design, zoom-out, codebase-details, structural, implementation-readiness, comprehension*
- **Observed:**
  - R-4.1 is "Decided and built" and names `project.lbug` (`metaform/SPEC.md:172-179`).
  - R-4.4 and R-4.5 are Decided (`metaform/SPEC.md:197-201`): "The chassis owns every database. It is one long-running process, and it holds the only connections." and "No other process opens a database. The MCP server ... reach the data through the chassis."
  - `DECISIONS.md:12` and `AGENTS.md:7` say "LadybugDB is selected".
  - `AGENTS.md:8` says "A standalone MCP deployment uses the same authoritative database and shared services".
  - `AGENTS.md:26` says "add no second database by exception".
  - R-1.1 forbids building on a temporary foundation (`metaform/SPEC.md:34-36`).
  - No entry in the decision table (`metaform/SPEC.md:443-460`) covers storing the map as a plain file.
- **Inferred:** while the store is undecided, an implementer cannot build the file map without breaking a Decided requirement. Under R-1.1 they also cannot build further on Ladybug as if the question were settled.
- **Blocks:** every build step that touches the map's storage.

### B2. Resolved by the founder: more than one agent runs only under orchestration
*Lenses: design, codebase-details, zoom-out, implementation-readiness, structural*

The founder: "the only place multiples would be running is when multiple are orchestrated only one agent performs intake". Outside orchestration there is one agent, so there is one map writer. Under orchestration, keeping one writer on the map is orchestration's job. This is no longer a gap in the map or its store. The reviewers' original finding is kept below for the record.

- **Observed (as reviewed):**
  - Each harness spawns its own stdio server process (`metaform/server/src/main.ts:80`).
  - Every process offers add, update and delete to any caller (`metaform/server/src/server.ts:14-22`).
  - The store comment says "Ladybug allows one read-write process" (`metaform/server/src/store.ts:7-8`). The spike records "second_read_write_process: refused by file lock" (`metaform/verification/ladybug-spike-2026-10-30.json:10`).
  - Identity is Open (D-8, `metaform/SPEC.md:454`). R-6.11 "cannot be enforced until agent identity exists" (`metaform/SPEC.md:349-351`). Orchestration is deferred (`metaform/SPEC.md:469`).
  - R-5.19's exclusion list, which mentions "locks", is an agent's wording. The founder has not reviewed it (`metaform/SPEC.md:297`).
- **Inferred:**
  - Today the file lock is the only guard against a second writer. A plain file has no such guard, so two writers would overwrite each other without an error.
  - The founder's position makes orchestration responsible for "only one". Orchestration is not built, and no interim guard is specified.
- **Blocks:** any session where more than one agent can reach the map. R-4.9 asks for that (`metaform/SPEC.md:185-187`).

### 🟡 M1. "A failed command changes nothing" has no file-store mechanism
*Lenses: design, codebase-details, implementation-readiness, structural*
- **Observed:**
  - R-5.8 (`metaform/SPEC.md:237`) is built on Ladybug `BEGIN/COMMIT/ROLLBACK` (`store.ts:123-139`). Each command is wrapped in `store.transaction` (`commands.ts:159`).
  - Writes are queued in one process (`store.ts:95-96`).
  - `test/metaform.test.ts:90` and `:106` cover restart durability and concurrent commands.
- **Inferred:** a file store needs these steps:
  1. Apply the command to an in-memory copy.
  2. Validate the whole map.
  3. Write a temporary file and rename it over the map.
  4. Keep the in-process queue.
  5. Follow a stated rule for how other processes see the new version: reload on each call, or watch the file.
  6. Follow a stated rule for a map file that fails to parse or validate, including one edited by hand, which bypasses the form (R-2.1).
- **Blocks:** keeping R-5.8 after the move.

### 🟡 M2. The map has more writers in the spec than the concept names
*Lenses: design, zoom-out, comprehension, structural, implementation-readiness*

Partly resolved by the founder: "orchestration refers to the map any writing doesnt need to change the map the map should be durable info". Orchestration reads the map, and its writes do not change the map. What remains is a gap in the text: R-3.16 lists `skills` as map content, and R-6.15 puts `system.memory`, "durable, atomic facts", in the map's root. Neither says which role writes them. See open question 3.

- **Observed (as reviewed):**
  - The Composer creates `not_built` addresses and binds tickets (`TOPOGEE.md:41`).
  - The Facilitator attaches a `skills` CEL Component to the Entity (`TOPOGEE.md:42`).
  - R-6.15 (Decided, not built) puts `memory` in the root `system` dictionary. Agents keep that memory current "through create, read, update and delete" (`metaform/SPEC.md:370`, `:400`).
  - `DECISIONS.md:45` has each element own `memories[]`, `tasks[]` and `inbox[]`.
  - R-3.16 sends ephemeral knowledge to tickets, "never in the map", and the founder's source quote is "we'll have it write a ticket for it" (`metaform/SPEC.md:140-142`).
- **Inferred:**
  - The updater's work matches the Composer's.
  - The Facilitator is a second map writer unless generated skills live in their own files.
  - Memory as separate files changes R-6.15, which the founder decided.
  - If working agents also write or close tickets, the ticket files have more than one writer.
- **Blocks:** the claim that the map has exactly one writer. Also R-6.15 `system.memory`, the Composer and the Facilitator.

### M3. Resolved by the founder: the address inbox is a layer, stored in its own file
*Lenses: design, zoom-out, comprehension, structural, implementation-readiness*

The founder: "inbox is a layer a layer is indexed by the map as a separate file". The inbox lives in its own file, keyed by the map's addresses, and writing to it does not change the map (position 7). The spec agrees in part: R-6.15 requires a layer to be registered in the map's `layers` dictionary before data is written to it. A layer can be many files. The inbox layer has one file per address, named from the functional address, for example `this_address_inbox.json`: "a layer could be many files if its an address inbox it would be this_address_inbox.json or some similar naming scheme identfied by all of these functional addresses". Agents do not write the inbox file. The system picks a message up, delivers it to be read and clears it; no agent does. The one thing written per read is a record that the message was read and by whom. That record is also added to the reading agent's own read-messages list: "no body writes to that file in those agents, its picked up and read and the system clears it not an agent.. what gets written once is the message that it was read and by whom it also gets added to the agents own read messages list". An address inbox is like a knowledge layer, but a message lives only until it is delivered to whoever works at that address next: "an inbox at an address is like what a knowledge layer is but it its life span is only until its delivered to whomever works there next".

- **Observed (as reviewed):**
  - Each functional address keeps one shared inbox and one read-messages list that every reading agent adds to (`TOPOGEE.md:51-52`).
  - Each context block is delivered once per session (`TOPOGEE.md:53`).
  - `metaform/SPEC.md` has no requirement on either the inbox or the read-messages list. The structural reviewer searched for "inbox" and found no match.
  - R-8.2 (Proposed) says the server keeps no session state (`metaform/SPEC.md:420-422`).
  - `DECISIONS.md:15` excludes recurring polling.
  - `DECISIONS.md:16` describes the mailbox as a waiting-count notice plus an explicit read.
- **Inferred:**
  - One file per message and one file per read record would satisfy "each writer gets its own file". TOPOGEE.md §5 does not say this.
  - "Delivered to the next agent" needs exactly one agent to claim each message.
  - Delivery tracking needs an identity (D-8).
  - Without polling, a reader has no stated way to learn that a new message file exists.
- **Blocks:** TOPOGEE.md §5 under the concept.

### 🟡 M4. The server has no path to deliver skills, or to learn where the agent stands
*Lenses: design, codebase-details, zoom-out, comprehension, structural, implementation-readiness*
- **Observed:**
  - The server declares only `capabilities: { tools: {} }` and lists one tool (`server.ts:11-14`).
  - "how an agent receives its skill" is listed as not specified (`metaform/SPEC.md:468`).
  - The layer walk and registries are not built (R-6.6, R-6.15 to R-6.17).
  - The server starts for one project folder until identity exists (`metaform/SPEC.md:221-223`).
  - R-3.19 defines this element as where the agent stands (`metaform/SPEC.md:150-152`).
  - Every new tool needs a founder decision (`DECISIONS.md:108`).
- **Inferred:**
  - Selecting skills by task and position needs the agent's address and task. Those come from orchestration, which the concept separates out.
  - Which fields cross the "link through the map", and which side writes them, is not defined anywhere the reviewers read.
  - Delivering skills needs MCP resources (SEP-2640) or a new command. Either one needs the founder.
- **Blocks:** the concept's delivery purpose.

### 🟡 M5. The chassis has two jobs, and the concept removes only one
*Lenses: comprehension, structural, zoom-out*
- **Observed:**
  - R-2.6 (Proposed) gives the chassis "the store ... events, settings, the module contract" (`metaform/SPEC.md:63-71`).
  - R-2.3 and R-2.7 are Decided and need something that hosts modules (`metaform/SPEC.md:55-59`, `:73-81`).
  - The founder on the earlier build: "the chassis itself, the settings system, and the template based development approach" (`docs/owner-statements-2026-10-31.md:65`).
  - `DECISIONS.md:107` calls "The Python chassis" the proven base. D-9 lists the language as open (`metaform/SPEC.md:455`). This session the founder said the language is undecided.
- **Inferred:**
  - Removing the database-owning process leaves the settings, events and the module contract and template without a stated home.
  - `DECISIONS.md:107` and D-9 disagree on the language.
- **Blocks:** R-2.7, R-4.8, and the founder rule that features land as modules on the chassis.

### 🟡 M6. The main database (`metaform.lbug`) is a multi-writer point the concept leaves out
*Lenses: codebase-details, design, implementation-readiness*
- **Observed:**
  - Every process opens `metaform.lbug` read-write for lookups, with no retry (`main.ts:40-48`, `home.ts:17-18`, `:78`).
  - That database holds the project registry and global settings (`home.ts:51-54`).
  - R-4.8 puts project setting overrides in the project database (`metaform/SPEC.md:181-183`).
- **Inferred:**
  - Two servers starting together can hit the lock refusal.
  - If `metaform.lbug` stays on Ladybug, R-4.4 still needs a chassis for it, and the native dependency stays (`package.json:11`).
  - Project overrides need a new place if the project store becomes a file.
- **Blocks:** settings, the project registry, and the scope of "no chassis".

### 🟡 M7. The map file's format and location are not given, and they depend on Open and unbuilt items
*Lenses: zoom-out, codebase-details, design, implementation-readiness, comprehension, structural*
- **Observed:**
  - D-4, the shape of `wants`, is Open (`metaform/SPEC.md:450`). `tree.ts:15-27` reads both shapes.
  - The R-4.2 export puts the project name at the root (`metaform/SPEC.md:189-191`, `tree.ts:101-103`). R-4.1 keeps the name out of the project store (`metaform/SPEC.md:176-179`).
  - Nothing is written into the project's own folder (`metaform/SPEC.md:177`).
  - The store, the form and the tests still use the superseded names `id`, `name_length`, `goal`, `function` and `ice`, and `send`/`receive`/`send_receive`:
    - `store.ts:14-20`, `:29-35`
    - `commands.ts:26-29`
    - `metaform/metaform.schema.json:256-259`
    - `metaform/mcp-tools.proposed.json:352-355`
    - `metaform/tests/check_contract.py:51-54`
  - R-3.4, R-3.6, R-3.13 and R-3.14 replace those names (`metaform/SPEC.md:97-156`).
- **Inferred:** if the file uses the export shape, D-4 becomes a storage decision. The root key and the field names also have to be settled first.
- **Blocks:** defining the file.

### 🟡 M8. Separate files can point at addresses that no longer exist
*Lenses: codebase-details, structural, implementation-readiness*
- **Observed:**
  - Delete refuses only when incoming wants exist (`commands.ts:102-108`).
  - The R-5.25 delete steps do not mention tickets, inbox messages or memory (`metaform/SPEC.md:269-273`).
  - R-3.8 says a change of functionality makes a new node (`metaform/SPEC.md:162-164`).
- **Inferred:** a ticket, message or memory file homed at an address can be left behind when that address is deleted or replaced. Neither the orphan query nor delete looks at those files.
- **Blocks:** "a ticket needs a home" holding over time.

### 🟡 M9. R-4.6 calls the Node server a prototype, and the label is an agent's inference
*Lenses: design, zoom-out, structural, codebase-details, comprehension*
- **Observed:**
  - R-4.6: "`mcp-server/` is a prototype ... The foundation is not built on it" (`metaform/SPEC.md:207`).
  - Its status line reads "Decided by R-1.1 and R-4.4" (`:209`). That status is an agent's inference.
  - The concept makes this server the delivery part.
- **Inferred:** R-4.6 as written forbids the build the concept describes. If the map leaves the chassis, the reason R-4.6 gives no longer applies.
- **Blocks:** building further on `mcp-server/` under R-1.1.

### 🟡 M10. Section 9 has no status and starts with the chassis
*Lenses: structural, zoom-out, implementation-readiness*
- **Observed:**
  - §9 (`metaform/SPEC.md:424-441`) has no status line.
  - Step 1 is "decide D-9, then build the process that owns the database" (`:428`).
  - D-9 blocks "All of section 9" (`:455`).
- **Inferred:** under the concept, steps 1 to 3 have no valid order until the storage question and D-9 are answered.
- **Blocks:** any build order for this concept.

### 🟡 M11. Migration from the existing Ladybug data is unspecified
*Lenses: codebase-details, zoom-out, design, implementation-readiness*
- **Observed:**
  - `--export` exists (`main.ts:70-76`, `tree.ts:101-103`).
  - `importProject` already rejects wants that name a missing provider (`tree.ts:81-87`).
  - The old SE covered both Supportive and Divergent (`metaform/SPEC.md:130`).
- **Inferred:**
  - Some conversions are mechanical: field renames, and probably `ice` to Supportive.
  - Others are not: SE to Supportive or Divergent, `goal` text into the R-6.17 grammar, and the mapping of `send`/`receive` to `outbound`/`inbound`. That mapping is one reviewer's guess; the founder has to state it.
  - A migration needs these parts:
    - the steps: export, convert, validate, write;
    - a rule for which store wins when both exist;
    - keeping the `.lbug` files until the founder accepts the converted maps.
- **Blocks:** moving existing projects.

### 🟡 M12. The test plan has to be redone
*Lenses: implementation-readiness, codebase-details*
- **Observed:**
  - `test/metaform.test.ts:137-142` asserts that the folder holds `project.lbug`, and `:156-166` copies `.lbug` files.
  - `CLAUDE.md` limits each feature to five tests.
- **Inferred:** the features still need names, for example map file, updater guard, tickets, skill delivery and migration. Each then needs its five tests chosen. Candidate tests from the readiness lens:
  - an interrupted write leaves the previous map readable;
  - a second updater is refused;
  - a ticket at a missing address is refused;
  - an agent receives only the skills resolved for its address;
  - a migrated map validates.
- **Blocks:** verification of the new store.

### 🟡 M13. No record of who changed the map
*Lens: codebase-details*
- **Observed:**
  - `apply` returns a result and logs nothing (`commands.ts:153-165`).
  - The map lives in `~/.metaform`, outside the project's git (R-4.1).
  - `DECISIONS.md:21` requires "attributable changes and conflict-safe writes".
- **Inferred:** a rewritten file keeps no history of changes. The current Ladybug store keeps none either. The single updater could append a command log: command, result, and caller once D-8 is settled.
- **Blocks:** `DECISIONS.md:21` under the concept.

### 🟢 N1. Terms used in more than one sense
*Lens: comprehension*
- **Observed:** these words carry more than one meaning across the concept and the spec:
  - "skill" means the updater role, the Facilitator's `skills` CEL Component (`TOPOGEE.md:23`, `:42`), and SEP-2640 entries in `system.skills` (`metaform/SPEC.md:370`).
  - "ticket" means a CEL Component (`TOPOGEE.md:25`) and the place for ephemeral knowledge (R-3.16).
  - "orchestration" means the Composer, Facilitator and Execution Agent in TOPOGEE.md §4, and the ACP harness and identity in the concept (§5).
  - "chassis" means the database owner (R-4.4) and the host of settings and modules (R-2.6).
  - "map" means functional form and intent in the concept, but R-3.16 also puts `sources` and `skills` in it.
- **Inferred:** an implementer could build the wrong part unless each term is pinned down.

### 🟢 N2. Superseded terms in the opening statement and code
*Lenses: comprehension, zoom-out*
- **Observed:**
  - `TOPOGEE.md:12-16` uses `goal`/`function`, DE/SE/NE, CQU as a role, and `send`/`receive`. R-3.6, R-3.13 and R-3.15 replace these.
  - The spec names TOPOGEE.md as the opening statement (`metaform/SPEC.md:26`).

### 🟢 N3. Multiple users means multiple updaters
*Lens: design*
- **Observed:** `DECISIONS.md:21` requires multi-user access. D-10 covers scaling across machines (`metaform/SPEC.md:460`).
- **Inferred:** "one updater" holds per orchestrator. Whether two users with separate orchestration on one map is in scope is not stated.

### 🟢 N4. Code structure and reuse
*Lenses: structural, codebase-details*
- **Observed:**
  - All `src` files are under 500 lines: `store.ts` 232, `commands.ts` 166, `home.ts` 142, `tree.ts` 104, `main.ts` 97, `contract.ts` 37, `server.ts` 26.
  - No check enforces the limit, although `DECISIONS.md:110` says it is checked.
  - All Cypher is in `store.ts`, and `home.ts:23` reuses its `connect`/`query`.
  - `commands.ts` and `tree.ts` import only the `Store` type (`commands.ts:7`, `tree.ts:2`).
  - The orphan query, the delete refusal with its remediation payload, prune and reads run in TypeScript (`commands.ts:87-134`).
  - `tree.ts:43-78` already converts between the nested document and elements.
  - `metaform/validate_metaform.py` validates a whole document.
- **Inferred:** a file-backed store replaces the `Store` class body, about 230 lines. The command grammar, refusals and remediation payloads can stay as they are. `Store` is a concrete class, not an interface.

## Goals vs. Non-Goals

**Goals (from the concept and the founder's statements):**
- Intake builds the map, the project's functional form and intent, as one plain file.
- One agent at a time holds the map-updating role. The role is carried as a skill, and that skill writes tickets homed at functional addresses.
- Where there would be more than one writer, each writer gets its own file.
- The MCP server hands an agent what is relevant to its task, from the agent's perspective, and surfaces "only the skills which align to the task being done".
- Orchestration is separate and connected to the map.

**Non-goals (stated in the concept or the brief):**
- Reviewing or changing the method: the roles, the want record, the address rules, the intake vocabulary, the layer walk and the claims.
- Building orchestration (ACP harness, role assignment, agent identity) as part of this part. The spec already defers it (`metaform/SPEC.md:469`).
- Settling the chassis language (D-9) here.

**Not stated either way:** whether settings, the project registry, the module contract and template, and `system.memory` belong to the narrowed part. See M2, M5 and M6.

## Alternatives Weighed

| Alternative | Status |
|---|---|
| Keep the map in Ladybug, owned by a long-running chassis (R-4.1, R-4.4, R-4.5 as written) | Decided in the current spec. The founder is now questioning it ("I'm questioning whether we should drop ladybug ... although maybe it doesnt matter") and said of the chassis "maybe the best move is to stay the course". Neither statement changes the status. |
| Map as one plain file; Ladybug used "for other aspects of the system" | Questioned by the author. Not decided. |
| Chassis inside the MCP server, or a separate process | Undecided. The founder: "no one has convinced me ... if it needs to be part of the mcp server". |
| Chassis language (D-9; `DECISIONS.md:107` names Python) | Undecided. The founder said this session that the language is undecided. |
| `metaform.lbug` (registry, global settings) stays on Ladybug, or moves to files | Undecided. Not discussed by the founder. Raised by reviewers (M6). |
| An interim guard against a second map writer (lock file, hash check on write) | Proposed by an agent. Not needed: the founder says more than one agent runs only under orchestration, and only one agent performs intake. |
| Atomic write by in-memory apply, validate, temp file and rename | Proposed by an agent (codebase-details and implementation-readiness lenses). |
| Map file uses the R-4.2 export shape (`{name: nested}`) | Proposed by an agent (zoom-out lens). Depends on D-4 and on R-4.1's rule that the project store does not hold the name. |
| Inbox as one file per message and one file per read record under the address | Proposed by an agent (zoom-out lens). |
| Skill delivery through MCP resources (SEP-2640) or through a new command | Proposed by an agent (design lens). Either one needs the founder (`DECISIONS.md:108`). |
| Append-only command log written by the updater | Proposed by an agent (codebase-details lens). |

## Key Decisions & Staging for Next Steps

**The founder's stated positions (this session):**
1. Only one agent at a time holds the map-updating role: "yes only one".
2. Where there would be more than one writer, each writer gets its own file: "it does [remove the writer question] in the sense that where there would be more than one writer they each get their own file".
3. A ticket needs a home, which is a functionality: "for a ticket in this system to exist it needs a home, which is a functionality". The role that updates the map is the role that writes a ticket: "the role of updating that map could be a skill file, which is the role which writes a ticket".
4. Writers such as memories are an orchestration matter: "thats more of an orchestration issue than an intake one... it could also be agents creating memories".
5. More than one agent runs only under orchestration, and only one agent performs intake: "the only place multiples would be running is when multiple are orchestrated only one agent performs intake".
6. Orchestration reads the map. Its writes do not change the map, and the map holds durable information: "orchestration refers to the map any writing doesnt need to change the map the map should be durable info". This agrees with R-3.16.
7. A layer is a separate file, indexed by the map. The address inbox is a layer: "inbox is a layer a layer is indexed by the map as a separate file". A layer can be many files: the inbox layer has one file per functional address, such as `this_address_inbox.json`.
8. What a layer is: "a layer is the same type or kind of knowledge spread across the map specifically where it applies". The aim of delivery is "nothing more and nothing less than exactly what is needed". Section 6 of `metaform/SPEC.md` does not state either of these.
9. The metaform MCP server has a running back end. It applies commands and announces each change, so a viewer receives changes as they commit and does not poll. That process is not the chassis.
10. The MCP server and the chassis work together when both are present. The chassis is part of a larger vision. It can hook the metaform MCP server, and messaging can be a chassis module that originates the inbox commands. The MCP server and the map provide an index, and the server can own and control layers, but layers must also be addable from outside. The MCP server brokers for the other parts of the system: "the shape I want is so they work together when both are present.. the chassis would need to be able to hook the metaform mcp server ... the mcp server itself and the map provides an index and it can own and control layers conceivably but those layers must be able to be added externally messaging could be a module that is part of the chassis and thats where commands related to the inbox come from that means the mcp server needs to be able to broker for the other parts of the system which is my I say it has a running back end".
11. Tools are organized by module, not gated by locality. A module exposes a tool, and all tools that act on the same functionality should collapse into one tool. ACP has a clear role here: "thats why acp plays a clear role.. the tools arent gates by locality they are organized my the module, a module exposes a tool, any and all tools that interact with the same functionaliuty should collapse hopefully into a single tool". `TOPOGEE.md` §3 still lists "the specific MCP tools ... resolved for that address" in the localized node context; the founder's words here govern.
12. Reading an address returns one localized JSON object. It holds the address as it is in the map; the frontmatter of the skills for that address; the layers attached there, by existence only, not their contents; and the names of the directly connected functionalities, both those this address depends on and those that depend on it. It does not return the layer data of those other addresses. Without ACP, agents are told to orient through it: "before working on a part of the system locate its functionality in the mcp server". The founder: "you get all of the info directly linked to the address you will be working on which is the context you need". This differs from R-5.10, "A read returns the address and everything beneath it".
13. Reading the root returns only the connections tree: the addresses, with the relations between them as edges. It returns no layers, not even the wants layer's content: "if you read the root of the map you only get the connections tree, no layers not even the wants layer but you do get the relations as edges". The whole-map read is a connected index with no element detail. Detail comes only from reading an actual address: "you cant dump detail when you view the whole map... you can ONLY get detail by reading an actual address". One label is allowed in the index: the definitive functionality can be marked ("you can label the definitive functionality.. that we can give"). There is only one. The reason: "that conveys understanding which helps reason on what the project itself is". Settled during drafting: agents see full namespace addresses, never the nested form, which is for storage only ("storage is nested, agents see full namerspace addresses, nested is for storage. Agents dont see nested form.").
14. The map is stored as JSON, on one condition, which is the foundation: a live running server tracks all projects, acts as the sink for each agent's MCP server, and can speak to a bigger system. "So long as that map can have a live running server that tracks all of the projects and can be a sink for each agents mcp server then yes its going to need to be able to speak to a bigger system and I think thats the better design.. if that is possible. that must be the foundation of it".
15. The tool is renamed from the provisional `metaform_apply` to `project-map`. The reason: "something an agent can actually reason against is highly preferred over something they have no idea what it is for". Not yet applied to the files.
16. Agents use snake_case and the store uses camelCase. The layer between the agents and the stored data (`$.projectName.namespaceAddress`) lowercases and converts snake_case to camelCase on the way in, and camelCase to snake_case on the way back, so no lint warnings about underscores appear: "normalize to lower and snake to camel and when landing back with the agent camel to snake.. I dont want to see any lint warnings about the underscores when it can be mitigated in the layer between the agents and what is actually the $.{{projectName}}.{{namespaceAddress}} in the data". This applies R-2.1: agents use the form and never see how the store is structured. Settled during drafting: uppercase is refused with a reason and the lowercase address as the fix, rather than lowercased without telling the agent. A name that would not convert back exactly, such as an underscore before a digit, is refused by input validation, in the same way `technical_name` is validated against the leading words of the reversed address ("thats what input validation is for").
17. A search command on the tool is a deep search over everything in the map, layers included. It returns where a match is, not the matched content: the address where it is, and the layer or layers when the match is in a layer of that address and not in the element itself. The running process enumerates every trunk-to-leaf path through the hierarchy, not only the flat list of addresses: "I would let search match anything in the map not just addresses.. treat it like a deep search.. and the running process needs to enumerate all of the trunk to leaf paths via the hierachy not just the flat addresses... A search should return the address where it exists THIS address, and the layer or layers if its in the layer of an address and not the address itself... so a search returns heres where the thing is in the data." The search reads all content. A result reads, for example: `Found: "code.bar.foo" in "baz" layer`. The address and the layer name are quoted.
18. Wants is a layer, and it is included in intake: "wants is a layer that is included in intake!" So reading an address returns its wants (`why`, `how`, `intent`) with the other intake fields, and the root read leaves the wants content out and shows the relations as edges (position 13). This agrees with R-6.15, which lists `wants` in the `intake` dictionary.
19. The home is `~/.metaform`. The founder never authorized the `METAFORM_HOME` override, but accepts it unless it becomes a blocker: "I never authorized an override, but I dont have an issue with one UNLESS its a blocker..". R-4.1 marks the override sentence Decided; the founder did not decide it, so its status should be Proposed. The override carries over from the earlier Python system, where tests used it to keep away from real data.
20. There is a write queue: "well there needs to be a write queue". R-4.7 (Proposed) already describes one: writes run one at a time per database, reads run against the last committed state, and a write is acknowledged only after it commits.
21. The inbox is not part of the base intake system. It comes later: "inbox isnt part of the base intake system, it comes later". Round 2's inbox findings (M15, and the inbox parts of B5 and M1) move to that later work.
22. Only one server can start, on the home. Each agent's own instance is a thin forwarder to it, names its project folder when it connects, and never writes files; the server is the only writer under the home. The founder: "yeah only one can start". These follow from positions 14 and 20, and resolve round 2's B1, B2 and B3.
23. Input validation is real, and every rejection says why: "input validationb is real and it must return why it was rejected". R-5.24 (Decided, not built) already requires a fixed code, the rule broken, the tested sentence and a remediation command. Today a schema failure returns only the failing path and the validator's message, such as "must match pattern", with no code, rule or remediation (`contract.ts:27-36`, `commands.ts:154-157`). Each check, including the round-trip check, needs its own code and a reason a person can read; a regular-expression pattern alone cannot give one.

**Treated as holding, unless the founder says otherwise (agent's reading of existing decisions):**
- R-5.21 still holds. Position 12 is the default address read; a read that names a layer returns that layer's content. This answers B5.
- Live announcements follow `DECISIONS.md:15`: WebTransport, with no recurring polling. The viewer's 1.5-second loop and its server-sent events are replaced.
- The server is written in Node, building on `mcp-server/`, which is the code being worked on now ("at present we are working on the mcp server which exists in node").

**Authorized by the founder's decisions (positions 15, 16, 17):** the changes these make to the protected contract `metaform/mcp-tools.proposed.json` and its tests. These are the tool name `metaform_apply` → `project-map`; address patterns that refuse names that would not convert back exactly; and a search command. The founder: "it better not be something I already authorized".

**Proposed by an agent:** the command log is the commit point. Each entry is written and synced first, then the files are saved, and entries after the last save are replayed at start-up. This is the only form that recovers a command that changes several files. It differs from R-5.11 and the section 9 acceptance line, which have `{".": {}}` return the `intake` fields for the whole project.

**Open questions, each with what it blocks:**

1. **Answered by position 14, on its condition.** The decided lines that name Ladybug still need the founder's revision before the store is built. **Original question: is the map stored as one plain file, replacing `project.lbug`?**
   - If yes, R-4.1, R-4.3 to R-4.7 and R-4.8, `DECISIONS.md:12` and `AGENTS.md:7`, `:8` and `:26` need the founder's revision. A new Open entry belongs in the decision table.
   - Blocks: every build step on the store (B1).
2. ~~Until orchestration exists, what stops a second map writer?~~ Answered by position 5: without orchestration there is one agent. Under orchestration, one writer on the map is orchestration's requirement.
3. **R-3.16 lists `skills` in the map, and R-6.15 puts `system.memory` there. Which role writes them, now that orchestration does not change the map?**
   - Blocks: R-6.15 `system.memory`, and where skills are stored (M2).
4. Answered by position 10: the chassis is a separate part of a larger vision, with its own modules such as messaging. It hooks the MCP server when both are present.
5. **Answered by the founder:** settings and the project registry are JSON too ("settings and project registry can be in json obviously"). **Original question: does `metaform.lbug` stay on Ladybug?**
   - Blocks: the scope of "no chassis", and whether the native dependency and the start-up lock contention stay (M6).
6. **Is the existing `mcp-server/` the product, with its own back end (positions 9 and 10), and no longer a prototype?** This follows from question 1.
   - Blocks: R-4.6, and building further on the current code under R-1.1 (M9).
7. **What is the shape of `wants` (D-4)? Does the file carry the project name at its root?**
   - Blocks: the file format and migration (M7, M11).
8. **What does the hook between the chassis and the MCP server carry?** Positions 10 and 11 name its parts: modules expose their own tools, layers can be added from outside, and the chassis can use what the server exposes. How an outside layer is registered and how changes are announced are not defined.
   - Blocks: the chassis and its modules working with the MCP server.
9. **Position 12 puts skill frontmatter in the address read. How does an agent then get a skill's body?**
   - Blocks: skill delivery (M4).
13. **`metaform/SPEC.md` now disagrees with positions 8, 12 and 13.** Section 6 does not say what a layer is, and R-5.10, R-5.11 and the section 9 acceptance line describe reads that the founder has replaced.
   - Blocks: building reads and layers from the spec.
10. Answered by position 7: the address inbox is a layer in its own file, indexed by the map (M3).
11. **What happens to ticket, message and memory files when their address is deleted or replaced?**
    - Blocks: tickets keeping their home (M8).
12. **What are the migration mappings that are not mechanical: SE to Supportive or Divergent, `send`/`receive` to the new intent values, and `goal` text into the R-6.17 grammar?**
    - Blocks: moving existing projects (M11).

**Staging, if the founder answers question 1 with a file (proposed by an agent; not decided):**
1. Settle D-4 and the root key, and define the map file.
2. Replace the `Store` body with an in-memory map and an atomic write. Keep `commands.ts` and `tree.ts`.
3. Build the ticket file homed at an address, and the updater skill.
4. Build skill delivery by address.
5. Migrate the existing Ladybug data.

Section 9 would then need a status line and a rewrite (M10).
