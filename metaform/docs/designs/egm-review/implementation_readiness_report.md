# Implementation readiness review: map server design (Stage 9)

**Target:** `docs/designs/metaform-server-design.md`, lines 536–847 (Detailed Implementation Plan)

**Reviewers:** all three completed.

- **egm-implementation-readiness** used the implementation-readiness standard. It reviewed the document and its context only, and did not open code.
- **egm-codebase-details** used the same standard. It checked every cited file and line against the repository.
- **egm-style** reviewed the wording.

**Background read:** `docs/designs/metaform-server.md` and `docs/designs/metaform-server-round2.md`.

**Verdict:** not ready to implement.

| Reviewer | Blockers | Majors | Nits |
|---|---|---|---|
| Readiness | 6 | 9 | 8 |
| Codebase | 6 | 11 | 6 |
| Style | 0 | 11 | 9 |

Findings raised by more than one reviewer appear once, with every ID. IR is readiness, CB is codebase, and Y is style.

---

## 🔴 Blockers

### 1. The new name patterns break the contract checks unless the protected schema changes too (CB-B1)

**Lines:** 564–565, 586–592.

**Problem:** `NamespaceNode.propertyNames` and `Wants.items.propertyNames` in `mcp-tools.proposed.json:314` and `:332` are copies of definitions in `metaform.schema.json:217-219` and `:235-237`. Two checks depend on those copies matching:

- `tests/check_contract.py:165-167` requires them to be equal.
- `tools/verify_bootstrap.py:58-61` overwrites them with the schema's version and compares the result.

The plan (lines 633–635) and `AGENTS.md:9` both exclude changing `metaform.schema.json`.

**Fix:** needs an owner decision. Either authorize the schema change, or keep the shared definitions as they are and enforce the round-trip rule elsewhere.

### 2. No rule says which data goes in `map.json` and which in layer files, and no command writes a layer (IR-B2, CB-B6; also IR-M13, CB-M11)

**Lines:** 558–570, 645–655, 684–687, 744–764.

**Problem:** today every non-column field is stored inside the element, including `skills` (`store.ts:28-29`, `:176-186`; `metaform-canonical.json:6-21`). `Intake.md:71` and `:160` tell agents to write layers inline. The plan gives none of the following:

- a rule for which keys an `add` or `update` sends to `layers/<layer>/<address>.json`;
- a command for registering a layer;
- where skill frontmatter comes from;
- what happens to layer files when an element is deleted;
- what happens to the root dictionaries of R-6.15. `tree.flatten` would turn them into elements (`tree.ts:47-51`).

The spec (`TOPOGEE-SPEC.md:520` and `:525`) says decisions D-7 and D-13 block Step 4. The R-6.6 walk has no algorithm and no tests. None of the acceptance checks in spec section 9 (`:501-508`) appears among the planned tests.

**Fix:** see the consolidated report, action A1.

### 3. The stored formats are not defined (IR-B1, CB-M5)

**Lines:** 645–675; open question at line 138.

**Problem:** the plan gives no format for any of these:

- `map.json`: its root key, where the registries go, where the sequence number goes, and the shape of `wants` (D-4).
- Layer files: whether they are wrapped in an envelope, and what that means for SEP-2640 content.
- `registry.json` and both `settings.json` files.
- The effect and log entry. `log.ts`, `store.open`, `announce.ts` and the viewer all share this format.

If the sequence number sits at the top of the nested map, `flatten` reads it as a root field.

**Fix:** give a JSON example and a list of fields for each file and for the effect.

### 4. The read results have no output shape, and "Definitive" has no stored value (IR-B3, CB-M6)

**Lines:** 744–750, 760–764.

**Problem:**

- Neither the address read nor the layer read has key names.
- The plan does not say whether `addresses` in the root read includes trunk prefixes.
- Nothing says which stored value marks the Definitive element. `Intake.md:165` and `intake-example.json` use `role: "DE"`. `metaform-canonical.json:69` uses free text. R-3.13 says "Definitive".
- Nothing says what happens when no element, or more than one, is Definitive.

**Fix:** give a literal JSON example for each read, and a rule for selecting the Definitive element.

### 5. The handshake response, the forwarder's lifecycle and the version rule are not specified (IR-B4, CB-M9)

**Lines:** 691–710, 735–740.

**Problem:**

- `PROJECT_NOT_REGISTERED` and `VERSION_MISMATCH` happen before any MCP session exists. The plan does not say how the refusal reaches the agent.
- The plan does not say where the version comes from (`package.json:3` and `server.ts:10` both say `0.0.0`), or what makes a version supported.
- A newer forwarder that meets an older server is refused, exits and restarts, and the cycle repeats.
- A pure byte pipe that reconnects to a new server sends `tools/call` without `initialize`, so the new server rejects it.
- The handshake line has to be read off the socket before the socket is handed to the MCP transport. The plan does not say so.

**Fix:** see the consolidated report, action A5.

### 6. The CLI has no protocol for talking to the server (IR-B5, CB-B5)

**Lines:** 680–681, 691–701, 719–727.

**Problem:** these commands are not tool commands:

- `register`
- `--import` and `--export`
- `--projects`, `--settings` and `--set`
- `server status`, `server stop` and `server restart`

The plan does not say how the CLI identifies itself on the socket, what its messages look like, or how `restart` works. The daemon handles only `status` and `stop`.

**Fix:** define a handshake for the CLI, with one request and response shape per command.

### 7. Step 5 leaves the transport and the viewer's starting state undecided (IR-B6, CB-M10, Y-M9)

**Lines:** 729–733, 772–797.

**Problem:** the plan leaves all of these open:

- **The library.** No WebTransport library is chosen; `DECISIONS.md:25` still lists it as open.
- **The connection.** No port, subscribe message, message format or catch-up request is given.
- **The certificate.** The plan does not say where the certificate is stored, how `server.mjs` gets its hash, or how renewal works.
- **A failed proof.** Nothing says what happens if the browser proof fails, and `DECISIONS.md:15` forbids a WebSocket fallback.
- **The viewer's starting state.** The viewer builds its picture from the full nested map (`index.html:33`, `:179`, `:256-258`). With the export removed, it has no starting state.
- **The file list.** `daemon.ts` and `package.json` are missing from Step 5.

**Fix:** see the consolidated report, action A7.

### 8. Steps 1 and 2 do not leave the code buildable, and test edits sit in the wrong step (CB-B3, IR-M7, Y-M4)

**Lines:** 538, 631–632, 645–687, 719–727, 822–829.

**Problem:**

- **Step 1 depends on Step 2.** It uses "the effect interface of Step 2".
- **Step 2 breaks `main.ts`.** Step 2 removes Ladybug, but `main.ts` still imports `DEFAULT_SIZE`, `DatabaseSize`, `Store.open(path, size)`, `home.size()` and `Home.open/close`, and only changes in Step 3.
- **Step 2 breaks every test.** It stops `project()` from registering folders, and every test registers through `--import` (`metaform.test.ts:35`).
- **Step 2 depends on Step 3.** `tree.ts` uses "through the server" in Step 2, but the server arrives in Step 3.
- **The viewer is broken from Step 2 to Step 5.** It depends on `--database --export` (`server.mjs:11`).
- **Test edits come too late.** All test edits sit in Step 6, but the Ladybug tests break in Step 2 and the stdio test harness breaks in Step 3.

**Fix:** move each change and each test edit into the step that needs it.

### 9. Two exact-match tests break, and an example is described wrongly (CB-B2)

**Lines:** 599–604.

**Problem:**

- `tool-examples.json:84-90` is `read_after_role_removal`, which is an address read. The plan calls it a whole-map read.
- `referenced_delete_error` (`:52-67`) keeps the old refusal shape. `metaform.test.ts:71` compares that exactly, so Step 1 breaks the test.
- The address read changes in Step 4, so `metaform.test.ts:76` breaks too.

**Fix:** update both examples in the step that changes their shape.

### 10. Step 6 describes edits that are already made (CB-B4; Stage 5 M9 and Stage 8 Z-9 found the same)

**Lines:** 801–820.

**Problem:** these edits are already in place:

- `TOPOGEE-SPEC.md` holds section 4.2, R-4.1, R-4.6, R-4.7, R-5.1, R-5.10, R-5.11, `METAFORM_HOME`, section 6.0, the new section 9, and the three Proposed codes.
- `DECISIONS.md:12` and `AGENTS.md:7-8` already hold the new wording.

An implementer would rewrite text the owner has already approved.

**Fix:** remove Step 6, or turn it into a check.

---

## 🟡 Majors

### 11. The schema check runs first, so the round-trip check never fires (IR-M8, CB-M2)

**Lines:** 564–566, 616–641.

**Problem:**

- `apply()` validates the schema before anything else (`commands.ts:154-157`). A name such as `version_2` therefore fails as a plain schema error, but the Step 1 test expects `NAME_ROUND_TRIP_FAILURE`.
- The plan does not give the exact regexes, which of the nine pattern sites change, or that `.` stays allowed.
- It does not say how the corrected address is built.

### 12. Most existing checks have no refusal code (CB-M1, Y-M8)

**Lines:** 616–631, 810.

**Problem:** R-5.24 has no code for these existing checks:

- the address does not exist;
- `name_length` is longer than the number of segments;
- the schema fails;
- a want is missing a field;
- there are elements beneath the address;
- the tool is unknown.

The plan also leaves these open:

- whether `status: "error"` and the echoed command stay in the response;
- how schema error keywords map to codes;
- where R-5.24's tested sentence goes.

The three new codes are used in Step 1, yet Step 6 waits for "the owner names them". Mark them as provisional.

### 13. Converting to camelCase switches off element checks during Step 1 (CB-M3, IR-M9)

**Lines:** 606–614.

**Problem:**

- `check()` validates the stored element against the snake_case schema and reads `fields.name_length` (`commands.ts:25-33`).
- Once the element is converted, `nameLength` passes as an unknown scalar.
- The merged element has to go back through `toAgent` before `check()` runs.
- Other native array members must pass through untouched: memories, tasks and inbox (`DECISIONS.md:45`).
- The plan does not say how outside formats are recognised.
- The plan does not say which form search matches.

### 14. It is unclear whether the store or the commands own the write logic (CB-M4)

**Lines:** 631–632, 648–655.

**Problem:**

- `Store.effect(command)` would make the store parse commands, which goes against design line 368.
- Reads in the middle of a command must see the working copy.
- `ensure`, `save`, `setWant`, `removeWant`, `remove` and `transaction` have no replacements.
- Reads still go through `store.transaction`, so they still wait in the queue.
- There are now two queues: one in `store.ts:95-96` and one in `daemon.ts`.

### 15. The log and recovery behaviour is underspecified (IR-M11; see Stage 7, item 4, and Stage 8, Z-3)

**Lines:** 645–665, 684–687.

**Problem:** the plan does not define:

- a rotation rule;
- an archive rule that works, since read literally nothing is ever archived (Y-M6);
- how a half-written last line is handled;
- what happens when a file write fails after the commit;
- whether the registry and settings are made durable;
- codes for a project that fails to load, or for an unexpected error.

### 16. Single-instance start, the home path and test isolation (IR-M10, IR-M14, CB-M8, Y-M11)

**Lines:** 691–710, 735–740, 843.

**Problem:**

- Two starting servers can race to delete and bind the socket.
- The socket, lock and files are fixed at `~/.metaform` and do not follow `METAFORM_HOME`.
- The plan does not say where the detached server's output goes, what exact spawn command starts it, or whether projects load when the server starts or on first use.
- Tests have no way to stop a detached daemon in `after()`.
- Verification clears `~/.metaform` without stopping the server first.

### 17. The test plan has gaps (CB-M7, CB-M8, IR-M15, Y-M3, Y-M5, CB-N4)

**Lines:** 589–592, 684–687, 735–740, 822–829, 847.

**Problem:**

- **Removed tests still cover live rules.** Lines 137–175 are not all Ladybug tests: they cover two folders with the same name, `source.txt`, and that the name is not stored. "Line 114" is a test of 20 lines.
- **Settings become untestable.** Removing both settings empties `SETTINGS`, so `--set` always fails.
- **The test helpers stop working at Step 3.** `connect()` and `database()` both break.
- **New test files would not run.** `package.json:22` runs only `metaform.test.ts`, and `CLAUDE.md` says to append to existing test files.
- **The crash test has no way to inject the crash.**
- **Some "new" tests already exist:** `metaform.test.ts:56-63`, `:90-104` and `:106-112`.
- **The case count is unclear.** The plan says "Append up to five cases" but lists three, and it does not say whether they count toward the test budget.
- **Some assertions cannot be measured:** "plain reason", "is whole after restart", "applied in order" and "with no polling".

### 18. Search output rules are incomplete (IR-M12, Y-M7)

**Lines:** 752–768.

**Problem:** the plan does not say:

- whether a match on a branch reports the branch or its leaves;
- how to remove duplicates when one element matches in several fields;
- what order results come in, so which 50 are kept is undefined;
- the exact text of the count line and when it appears;
- whether a match is a substring match.

### 19. One term names several things (Y-M1, Y-M2, Y-M10, CB-N6)

**Lines:** 602–603, 680, 693, 714, 722, 748, 784, 792–793, 826.

**Problem:**

- "Server" means `daemon.ts`, `server.ts` and `server.mjs`. Call `daemon.ts` "the map server".
- One read has three names: "root read", "root index" and "whole-map read".
- "Field names stay as the store has them" contradicts the snake_case announcements. Say that the viewer keeps today's field names.

---

## 🟢 Nits

- **IR-N16:** the Open Questions contradict the plan on search scope and on Node.
- **IR-N17:** no step sets the 0600 and 0700 file modes.
- **IR-N18:** the file list leaves out deleting `snap/`, the forwarder script's name, and how harnesses are configured.
- **IR-N19:** the root address `.` has no layer file name.
- **IR-N20:** no command checks the 500-line rule.
- **IR-N22:** the content of the new `tool-examples.json` entries is not given.
- **IR-N23:** "nearest parent" routing does not cover registering a folder that is nested in, or above, a registered one.
- **CB-N1, code to reuse:**
  - `serveStdio(factory, { transport: new StdioServerTransport(socket, socket) })` works over a Unix socket (SDK `stdio.d.mts:22-30`), and R-8.1 names it.
  - `prefixes()` already exists (`store.ts:44-48`).
  - `flatten` and `nest` already exist (`tree.ts:43-69`).
  - `receivers()` already exists (`store.ts:211-218`).
  - Port the duplicate-provider check from `validate_metaform.py:91-96`.
- **CB-N2:** `SPECIFICATION.md:337` and `:908` still say `metaform_apply`, and `SKILL.proposed.md:10` calls the name provisional.
- **CB-N3:** the new tool-input cases belong in `tests/check_tool_input.py`.
- **CB-N5:** `register` and `server` as positional words collide with the `<folder>` positional (`main.ts:23-33`).
- **Y-N1:** lines 609–614 contradict each other on values.
- **Y-N2:** the name pattern is given only in words. Give the regex, including whether digits are allowed and how `.` is handled.
- **Y-N3:** no wording is given for the protected contract text at line 570.
- **Y-N4:** "Each existing check" is never listed.
- **Y-N5 and Y-N6:** "and the others" and "keep their meaning" are vague.
- **Y-N7:** at lines 685–686 the modifier attaches to the command, but it is the server that is killed.
- **Y-N8:** "both kinds of neighbour", where error messages go, `server restart` when no server is running, and which tests go in which file.
- **Y-N9:**
  - "with the owner's sign-off" is repeated.
  - "as the 500-line limit requires" is repeated.
  - "the newest procedure" will go stale.
  - "byte-identical to `~/brain/intake-new.md`" should be dated, or replaced with a `cmp` check.
