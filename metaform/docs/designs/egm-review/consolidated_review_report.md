# Consolidated review: map server design

**Document reviewed:** `docs/designs/metaform-server-design.md` (847 lines). Lines 1–535 are the design. Lines 536–847 are the implementation plan.

**How it was reviewed:** five stages, run one after another. Each reviewer started fresh, with no knowledge of this conversation. Every reviewer completed. The document was not edited during the review.

| Stage | What it checked | Report |
|---|---|---|
| 5. Zoom out | Scope and simplicity, whole file | `zoom_out_report.md` |
| 6. Comprehension | Whether a new reader can follow it, using only the document | `comprehension_report.md` |
| 7. Critic | Design, structure and wording of lines 1–535 | `critic_report.md` |
| 8. Zoom out again | Whether the fixes asked for make the design too big | `intermediate_zoom_out_report.md` |
| 9. Readiness | Whether lines 536–847 can be built as written, checked against the code | `implementation_readiness_report.md` |

**Verdict:** not ready to build. The overall direction holds up: one map server, JSON files, forwarders and narrower reads. No reviewer argued against it. The gaps are in parts the design leaves undefined, and in parts the plan describes wrongly.

**Three items need an owner decision.** They are marked ⚖️ below. The others are drafting work.

---

## 🔴 Blockers

### A1 ⚖️ What a layer is in the first version
**The gap:**
- The plan builds layer files, a layer read, a walk and a search over active layers.
- No command writes or registers a layer.
- Nothing says which fields go in `map.json` and which go in `layers/`.
- Today `skills` is stored inside the element, and `Intake.md` tells agents to write layers inline.
- The spec itself says D-7 and D-13 block Step 4.
- Skills as layers, and layer files after a delete, are still listed as open questions.

**Choices put forward:**
- **Stage 5:** keep everything in `map.json` for now. Stage 8 points out that this conflicts with Decided R-4.3 and R-6.21.
- **Stage 8 (smallest change):**
  - Every array field on an element is a layer file. Intake fields and wants stay in `map.json`.
  - The existing `add`, `update` and `delete` write those files, so no new command is needed.
  - Deleting an element deletes its layer files.
  - Layer registration and the R-6.6 walk wait for D-7 and D-13.
  - R-6.1 to R-6.8 come out of Step 4, both here and in spec section 9.

**Why it needs the owner:** it changes Step 4's scope and the spec's section 9.

**Owner decision (2026-11-03), partial:** "make a command called layer to add a layer. every other command works the same way". The design and spec R-5.28 now have a `layer` command that registers a layer. Data goes into a registered layer through `add` and `update`, and is stored in that layer's files. Still open: the R-6.6 walk and D-7/D-13, skills as layers, and layer files after a delete.

### A2 Two servers can both start after a crash
**The gap:** two servers that start together after a crash can both delete the socket and bind their own. Both then write the same files. A reused process id can also block start-up entirely.

**Reviewer disagreement:**
- **Stage 7:** use `flock`.
- **Stage 8:** Node has no `flock`. It would need a native addon, which is the same reason Ladybug was rejected. Trying to connect before deleting also leaves the race open.
- **Stage 8's fix:** use a Linux abstract-namespace socket as a lock, keyed by the home path. The kernel releases it when the process dies. This removes the lock file and the process-id check. It means stating Linux as the supported platform.

### A3 The stored formats are not defined
**The gap:** none of these has a defined shape:
- `map.json`: its root key, where the registries go, where the sequence number goes, and the shape of `wants` (D-4 is still open);
- layer files;
- `registry.json`;
- the settings files;
- the log entry.

The log entry is shared by `log.ts`, the start-up replay, the announcements and the viewer. A sequence number at the top of the nested map would be read as a field.

**Fix:**
- Give a JSON example for each file.
- State that an effect stores final values: the whole element, the whole layer file, or a removal.
- That rule lets the plan drop the sequence numbers in each file, the log segments and the archive folder (Stage 8, Z-3).

### A4 The read results have no shape, and "Definitive" has no stored value
**The gap:**
- The address read and the layer read have no key names.
- Nothing says whether the root read's `addresses` includes trunk prefixes.
- The data marks Definitive in two ways: `role: "DE"` in the intake files and free text in the canonical map. Nothing says which one counts.
- Nothing says what happens when no element, or more than one, is Definitive.

**Fix:** give literal JSON for each read and a rule for selecting the Definitive element.

### A5 The forwarder's lifecycle and the version rule
**The gap:**
- Refusals at the handshake (`PROJECT_NOT_REGISTERED`, `VERSION_MISMATCH`) happen before MCP starts, so the agent never sees them.
- A forwarder that exits on a mismatch is restarted as the same binary, and the loop repeats.
- A byte pipe that reconnects after a crash reaches a server that never received `initialize`.
- No version source or rule is given. Both versions are `0.0.0`.
- The handshake line must be read off the socket before MCP takes it over.

**Fix (Stage 8, Z-6):**
- The forwarder exits when its socket closes, and the next one started restarts the server.
- The server accepts every connection and returns these refusals on each `tools/call`. The remediation for a version mismatch is `server restart`.
- The contract is loaded once, at start-up.
- Duplicate `add`s on retry are accepted as a known risk.

### A6 The CLI has no protocol for talking to the server
**The gap:** these commands become "calls to the server", but the socket only carries a handshake followed by MCP for one tool:
- `register`;
- `--import` and `--export`;
- `--projects`, `--settings` and `--set`;
- `server status|stop|restart`.

**Fix (Stage 8, Z-7):**
- The handshake carries either `folder`, for MCP on one project, or `"admin": true`, for one-line JSON requests.
- Imports and exports send one `tools/call`, so they get full checks and meet R-5.14.
- `restart` is `stop`; the next forwarder starts the server again.
- Stage 7 also asked for an admin channel that agents cannot call. Stage 8 rejects that: it cannot be enforced before agent identity (D-8) exists.

### A7 ⚖️ Announcements and the viewer
**The gap:**
- WebTransport sits inside the only writer. It brings HTTP/3, TLS, a certificate renewed at least every 14 days, and probably a native QUIC library. A native binary is one of the objections used against Ladybug.
- No library, port, message format or catch-up rule is chosen.
- A newly opened viewer has no way to load the full map.
- The 127.0.0.1 listener can be opened by any local user.

**Fix (Stage 8, Z-5):**
- Subscribers connect to the existing Unix socket. They receive a snapshot tagged with a sequence number, then each change.
- If WebTransport stays, it lives in `server.mjs`, the viewer's own server.
- This removes the catch-up protocol, the subscriber tokens and the full-view read.

**Why it needs the owner:** it moves where `DECISIONS.md:15` (WebTransport) applies.

### A8 ⚖️ The new name patterns break the contract checks
**The gap:**
- Two of the patterns to change are shared with the protected `metaform.schema.json`.
- `tests/check_contract.py:165-167` and `tools/verify_bootstrap.py:58-61` fail unless both copies match.
- The plan and `AGENTS.md:9` both exclude changing the schema.
- The schema check also runs first, so a bad name fails as a plain schema error and never reaches `NAME_ROUND_TRIP_FAILURE`. The Step 1 test would fail.

**Why it needs the owner:** it means either authorizing the schema change, or enforcing the round-trip rule outside the schema.

### A9 The build steps do not each leave a working build
**The gap:**
- **Step 1** uses Step 2's effect interface.
- **Step 2** removes Ladybug while `main.ts` still imports it. It also stops `project()` from registering folders, which every test relies on.
- **Step 2** says `tree.ts` reads and writes "through the server", which only exists in Step 3.
- **The viewer** is broken from Step 2 to Step 5.
- **All test edits** sit in Step 6, even though tests break in Steps 2 and 3.
- **Two exact-match examples** in `tool-examples.json` break in Steps 1 and 4. One of them is also described wrongly as a whole-map read.

**Fix:** move each change and each test edit into the step that needs it.

### A10 Step 6 is already done
**The gap:** commit `1f9c262` already made the spec, `DECISIONS.md` and `AGENTS.md` edits that Step 6 describes. Three stages found this independently.

**Fix:** remove Step 6 (and spec section 9's mention of it), or turn it into a check.

---

## 🟡 Majors

### A11 Add a short Risks & Mitigations section
Stage 7 rated this a Blocker. Stage 8 lowered it to Major, because the content comes from A1–A7.

Make it one line per risk. Each line either points to a fix or says "accepted for version 1". The accepted risks are a full disk, the dashed tool name, a duplicate `add`, log growth, size limits and platforms.

### A12 Checks that read the map must run inside the queue
Step 2 runs every check before the queue. So agent A can delete X while agent B adds a want naming X, and both commit.

The current code already does this correctly (`commands.ts:153-165`). Keep that split.

### A13 Commit and recovery rules
Keep these three rules:
- sync the temporary file before renaming it;
- drop a half-written last log line at start-up;
- reload the project after any error past the commit point.

Stage 8 rejects the others as more than a first version needs: a log for the registry, macOS `F_FULLFSYNC`, and archive retention.

### A14 `METAFORM_HOME`, test isolation and the server's output
The socket, the lock and the files must follow `homePath()`. Otherwise tests and worktrees reach the owner's live server. State also:
- where the server's output goes;
- which checkout it runs from;
- how tests stop it;
- that verification stops the server before clearing the home folder.

### A15 Where the case conversion sits
- **Placement:** Stage 5 recommends converting where the store reads and writes files, not at the MCP boundary. At the boundary, addresses inside values and inside `Found:` sentences have to be found.
- **Checks break:** `check()` reads `name_length` from the stored element, so converted elements would pass unchecked.
- **Unstated rules:** the plan does not say how content in an outside format is recognised, or which form search matches.
- **Wording:** the sentence on what the conversion covers contradicts itself.

### A16 A table of refusal codes
Most existing checks have no R-5.24 code. These are undecided:
- whether `status: "error"` and the echoed command stay;
- how schema errors map to codes;
- where R-5.24's tested sentence goes.

Mark the three new codes as provisional.

### A17 The store and the commands
- **Ownership:** it is unclear whether the store or the commands own the write logic.
- **Missing replacements:** `ensure`, `save`, `setWant`, `removeWant`, `remove` and `transaction` have none.
- **Reads:** reads in the middle of a command must see the working copy.
- **Queues:** there are now two queues (`store.ts` and `daemon.ts`).

### A18 Search output rules
The plan does not say:
- what a match on a branch reports;
- how duplicates are removed;
- what order results come in;
- the exact count line and when it appears;
- whether a match is a substring match.

### A19 The test plan
- **Removed tests:** the tests marked for removal also cover rules that still apply: two folders with the same name, `source.txt`, and the project name not being stored.
- **Settings:** removing both settings makes `--set` untestable.
- **Helpers:** the test helpers break at Step 3.
- **New files:** new test files would not run, and `CLAUDE.md` says to append to existing files.
- **Crash test:** it has no way to inject the crash.
- **Existing tests:** some "new" tests already exist.
- **Acceptance checks:** the spec's section 9 checks are missing.
- **Untestable assertions:** "plain reason", "applied in order" and "with no polling" cannot be measured.

### A20 Labels and Open Questions
- **"Agent's choice" labels:** about 13 agent proposals carry no label. Line 189 says that anything unlabelled comes from the owner.
- **Open Questions answered in the body:** search scope, the Node language and skills as layers are still listed as open. Say what each remaining question blocks.

### A21 Claims that go beyond the evidence
- **Speed:** "about a millisecond" was not measured, and the 40 KB map it assumes does not exist.
- **Version control:** the files live under `~/.metaform`, so they are not in any repository.
- **Ladybug:** "many concurrent writers" contradicts lines 40–42.
- **Harnesses:** "every harness" is true only of stdio harnesses.
- **Quotes:**
  - Two have no source: "kinda sucks" and "no data needs to move".
  - Three can be traced to spec lines 217, 237 and 249. Stage 8 corrected Stage 7 on these.

### A22 Terms
- **Domain nouns:** the design never defines its domain nouns, and the R-, D- and position IDs are not linked to `TOPOGEE-SPEC.md`. Link them; do not copy the definitions.
- **Naming the two ends of a want:** the design uses five names. Use the settled pair, "this element" and "the other element".
- **"Server":** the word refers to three files.
- **One read, three names:** the root read has three names.
- **"Option A":** it is never defined.
- **Author, owner and agent:** "author" and "owner" are never said to be the same person, and "agent" has two meanings.
- **CUJ 5:** it uses `technical_name`, a rename the design defers.

---

## 🟢 Nits

The stage reports list about 40 Nits in all. The ones worth doing while drafting:

- **Reuse existing code:**
  - `serveStdio` with `StdioServerTransport(socket, socket)` works over a Unix socket.
  - `prefixes()`, `flatten`/`nest` and `receivers()` are already written.
  - Port the duplicate-provider check from `validate_metaform.py`.
- **Platform:** state the supported platform in one line. It settles Windows pipes, file modes and socket path length.
- **Long names:** give a rule for layer file names over 255 bytes, and a file name for the root address `.`.
- **Layout:** fix the heading levels of Additional Resources and Future Improvements, the diagram arrows that do not join, the horizontal rules and the line wrapping.
- **Stale references:** `SPECIFICATION.md` and `SKILL.proposed.md` still say `metaform_apply`, or call the name provisional.
- **Test file:** the new tool-input cases belong in `tests/check_tool_input.py`.

---

## Rejected as unneeded complexity (Stage 8)

These were proposed in Stages 5–7. Stage 8 recommends against them:

- `flock`, which needs a native addon;
- a subscriber token and origin check on the map server;
- a catch-up protocol;
- a log for the registry and settings;
- macOS `F_FULLFSYNC`, Windows named pipes and hashed file names;
- measured limits and log retention before a problem is seen;
- an admin channel that agents cannot call;
- a forwarder that understands MCP and reconnects;
- keeping everything in `map.json` (it conflicts with R-4.3);
- copying a full domain model into the design.

---

## Traceability

| Action | Source findings |
|---|---|
| A1 | S5-B1; Comp-1, Comp-4; Crit-10, Crit-12; Z-1; IR-B2, IR-M13; CB-B6, CB-M11 |
| A2 | Crit-1 (D-B1); S5-M6; Z-2; IR-M10 |
| A3 | IR-B1; CB-M5; Crit-4; S5-M1; Z-3; Comp-20; Y-N5 |
| A4 | IR-B3; CB-M6; Comp-3; D-N1 |
| A5 | IR-B4; CB-M9; Crit-5; Comp-6; S5-M7; Z-6 |
| A6 | IR-B5; CB-B5; Crit-9; S5-M5; Comp-7; Z-7 |
| A7 | IR-B6; CB-M10; Y9-M9; Crit-7, Crit-8; S5-M3, S5-M4; Comp-8, Comp-14; Z-5 |
| A8 | CB-B1; IR-M8; CB-M2 |
| A9 | CB-B3, CB-B2; IR-M7; Y9-M4; Comp-9; S5-N2 |
| A10 | S5-M9; Z-9; CB-B4 |
| A11 | Crit-2 (D-B2, S-B1); Z-8 |
| A12 | Crit-3 (D-M1); Z-4 |
| A13 | Crit-4 (D-M2); Z-3; IR-M11 |
| A14 | S5-M8, S5-N6; Crit-6; IR-M14; CB-M8; Y9-M11 |
| A15 | S5-M2; Crit-21 (Y-M11); CB-M3; IR-M9; D-N2, D-N3 |
| A16 | CB-M1; Y9-M8; Comp-13 |
| A17 | CB-M4 |
| A18 | IR-M12; Y9-M7 |
| A19 | CB-M7, CB-M8, CB-N4; IR-M15; Y9-M3, Y9-M5 |
| A20 | Crit-11, Crit-12; Comp-5; S5-N1; IR-N16 |
| A21 | Crit-13, Crit-14, Crit-20; Z-10, Z-11 |
| A22 | Comp-1, Comp-2, Comp-11, Comp-12, Comp-15; Crit-16 to Crit-19; Y9-M1, Y9-M2, Y9-M10; CB-N6 |

**Key to the IDs:**

- S5 is Stage 5.
- Comp is Stage 6.
- Crit is the numbered items in the Stage 7 report.
- D, S and Y are the Stage 7 design, structure and style reviewers.
- Z is Stage 8.
- IR, CB and Y9 are the Stage 9 readiness, codebase and style reviewers.
