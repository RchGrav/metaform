# Critic review: map server design (Stage 7)

**Target:** `docs/designs/metaform-server-design.md`, lines 1–535 (the feature design)
**Reviewers:** egm-design and egm-structural, each with the feature-spec standard, and egm-style. All three completed.
**Background read:** `docs/designs/metaform-server.md` and `docs/designs/metaform-server-round2.md`

**Verdict:** not ready.

- The design reviewer found 2 Blockers, 11 Majors and 7 Nits.
- The structure reviewer found 1 Blocker, 5 Majors and 5 Nits.
- The style reviewer found 11 Majors and 10 Nits.

Findings that two reviewers raised appear once below, with both IDs. Finding IDs are `<reviewer>-<n>`: D is design, S is structure, Y is style.

---

## 🔴 Blockers

### 1. Two servers can both start after a crash (D-B1)
**Lines 67–70, 228–235.**

The server that runs is the one that binds the socket. A stale socket is cleaned up by checking the process id in the lock file. Two servers started together after a crash can both see the stale lock:

1. A deletes the socket and binds.
2. B deletes A's socket and binds its own.

Both processes now write the same files, with clashing log sequence numbers. A reused process id can also make the lock point at an unrelated live process, so the server never starts. The design does not say whether the lock is written before or after the bind.

**Fix:** let an operating-system lock (`flock` on `server.lock`, held for the server's whole life) decide which server runs. Only the holder may delete and bind the socket. Try to connect to a socket before deleting it. *(Stage 5 raised the same issue as M6.)*

### 2. No Risks & Mitigations section (D-B2, S-B1)
**Whole document; partial coverage at 129–131, 450–451, 491–510.**

The feature-spec standard requires failure modes, security implications, scale limits and their mitigations. Those that appear are scattered. These are missing:

- the server dying while agents are connected;
- a half-written log line;
- a full disk;
- a corrupt file;
- a stale lock;
- certificate expiry;
- harnesses that reject a dashed tool name;
- a duplicate `add` on retry;
- a log that grows without limit;
- which platforms are supported (Unix socket, 0600/0700 modes, rename into place);
- isolation of tests and worktrees under `METAFORM_HOME`;
- contract skew in a long-running server;
- any ceiling on projects, connections or layer files.

**Fix:** add an H2 "Risks & Mitigations" after Non-Functional Requirements. Give each risk a mitigation, or mark it as an accepted risk.

---

## 🟡 Majors

### 3. Checks that read the map run before the queue (D-M1)
**Lines 287–293.**

These checks depend on the current map:

- refusing a delete while other elements still want the address;
- requiring that the element a want names exists;
- `LAYER_NOT_REGISTERED`;
- the single Definitive element.

They run at step 2, before the command enters the queue. Suppose agent A deletes X while agent B adds a want naming X. Both pass step 2 and both commit, which leaves a want that points at nothing.

**Fix:** keep shape and grammar checks before the queue. Run the checks that read the map at step 5, inside the queue.

### 4. Gaps in the commit and recovery path (D-M2)
**Lines 74–76, 283–306, 507–509.**

- **Missing syncs.** The temporary file is not synced before the rename, and the folder is not synced after it. After a power cut, `map.json` can be empty or torn, the project is then marked failed, and "no acknowledged change is lost" does not hold.
- **Torn log line.** Nothing says that start-up drops a half-written last log line.
- **Errors after the commit point.** An error after step 6 fails only that request, which leaves memory and the files out of step with the log.
- **Failed file writes.** A file write that fails after the commit has no defined behaviour.
- **Registry and settings.** These have a queue but no log.
- **What an effect stores.** Nothing says whether an effect stores final values. If an effect stores an append, replaying it doubles arrays.
- **Deleted files.** The archive rule is undefined for a file that has been deleted.
- **macOS.** Node's `fsync` does not use `F_FULLFSYNC`.

**Fix:** write the commit protocol out as numbered rules. Reload the project on any error after step 6. State that effects store final values. Give the registry and settings a log, or explain why they do not need one.

### 5. The forwarder's life cycle does not fit a pure byte pipe (D-M3; Comprehension 6)
**Lines 160–167, 216–221, 230–231, 246–253.**

- **Reconnecting.** After the server restarts, a reconnecting forwarder reaches a new MCP session that never received `initialize`.
- **Calls in flight.** Calls that were running when the server died never get an answer.
- **Retries.** A committed `add` whose reply was lost gets retried, which doubles arrays.
- **Version mismatch.** On `VERSION_MISMATCH` the forwarder exits so the harness can restart it. The harness restarts the same binary, which fails the same way.
- **Refusals at the handshake.** `PROJECT_NOT_REGISTERED` and `VERSION_MISMATCH` happen before MCP starts, so the agent never sees the refusal code or its remediation.

**Fix:** accept every connection and return these refusals on each `tools/call`. Decide what the forwarder must understand about MCP. Either add request ids or accept duplicate `add`s as a known risk.

### 6. `METAFORM_HOME`, worktrees and upgrades (D-M4; Stage 5 M7, M8)
**Lines 12, 119, 203, 228–231, 250–251.**

- **Fixed endpoint.** The socket is fixed at `~/.metaform`, so tests and worktree agents can reach the owner's live server.
- **Which checkout runs.** The first forwarder starts the detached server from its own checkout. That checkout can be a feature-branch worktree.
- **Upgrades.** There is no upgrade rule.
- **Logs.** Nothing says where the detached server's output goes.

**Fix:**

- Make every path follow the home folder, including the override.
- State which checkout the server runs from.
- Give an upgrade rule.
- Name a log file for the server's output.

### 7. WebTransport costs not counted, and the viewer has no first load (D-M5; Stage 5 M3, M4; Comprehension 8)
**Lines 129–131, 172–174, 335–341, 387–390.**

- **Certificates.** WebTransport needs a self-signed certificate that is renewed at least every 14 days.
- **Native dependency.** It likely needs a native QUIC library. That is the same objection used to reject Ladybug.
- **First load.** The viewer has no defined way to load the full map when it opens.
- **Catching up.** Catch-up has no protocol, no limit, and no rule for archived segments.

**Fix:** list these costs as risks. Define a full-view read and the catch-up protocol. Record a fallback for the owner in case WebTransport fails its test.

### 8. The announcement listener is wider open than the security section says (D-M6, Y-N9; Comprehension 14)
**Lines 222–224, 495–498.**

- **Any local user.** Any local user can connect to the 127.0.0.1 listener, skip the certificate check, and receive every change to every project, including the log history.
- **"No network connection" is inaccurate** for a UDP listener on the loopback address.
- **The socket is open to the same user.** Any process running as the same user can claim any folder through the socket.
- **Two meanings of "owner."** At line 495, "owner" means the operating-system file owner, which is not the person the document calls "the owner."

**Fix:** require a subscriber token kept under the home folder, and check the browser's origin. Limit catch-up to a bounded range. State that the user account is the trust boundary until D-8 exists.

### 9. The architecture leaves out the CLI and outside parts (D-M7, S-M5; Stage 5 M5; Comprehension 7)
**Lines 22–23, 68–70, 192–224, 236–238, 370–371.**

The socket speaks a handshake and then MCP for one tool. Yet `server status`, `server stop`, `server restart`, `register`, `--set`, `--import` and `--export` all "become calls to the server". The diagram shows only the forwarders and the viewer. Nothing says that an import runs full validation.

**Fix:** define an admin channel that agents cannot call. Add the CLI and the outside parts to the diagram. Route imports through the normal commit path.

### 10. The goals depend on layer machinery that is unbuilt or still open (D-M8; Stage 5 B1; Comprehension 4)
**Lines 82–86, 134–135, 162–163, 313–319, 329.**

- **Unbuilt.** The R-6.6 walk and layer registration are not built, and no command writes layer data.
- **Skills.** The design assumes skills are a layer while open question 4 still asks whether they are.
- **`wants`.** The shape of `wants` (D-4) is still open.

**Fix:** either add the layer walk and layer registration to the Goals, or narrow the reads to what exists. Settle the skills question and D-4, or state an explicit assumption for each.

### 11. The "(agent's choice)" label is applied unevenly (D-M9, S-M2, Y-M9)
**Lines 188–190; Technical Plan 214–509.**

Line 189 says that everything without the label comes from the owner. Many items without the label are agent proposals from round 2:

- Node;
- deciding the running server by socket binding;
- the 5-second retry;
- the handshake format;
- log segments and archiving;
- sequence numbers in files;
- the shape of announcements;
- the JSON shape of the root read;
- the file modes and the 127.0.0.1 bind;
- the rollout behaviour;
- per-request isolation.

Round 2 M20 raised the same problem.

**Fix:** mark every agent proposal.

### 12. Open Questions disagree with the body (S-M3, Y-M8; Comprehension 5; Stage 5 N1)
**Lines 124–138 against 92–93, 214, 317–333, 292–293.**

- **Search scope** is listed as open but answered at 327–333. The goal at 92 also says search reads "all content".
- **Server language** is listed as open but stated as Node at 214.
- **Skills as layers** is listed as open but assumed at 317–318.
- **Layer files after a delete** is not marked as pending in the write path.
- **No question says what it blocks.**

**Fix:** turn each answered question into "confirm the agent's choice: …". Say what each open question blocks.

### 13. Owner quotes and rejections that cannot be traced (S-M4, D-N6, Y-N7)
**Lines 373–374, 391–393, 404–407, 414–416, 448–451, 459–461.**

These quotes do not appear in the linked brief:

- "you know this kinda sucks…";
- "is a process, not the chassis";
- "dash if its allowed";
- "please make recommendation";
- "no data needs to move…".

The "(position N)" references are not linked. Alternative F lists no downside for `project_map`. The quote at 406–407 does not support "the viewer must not poll"; `DECISIONS.md:15` does.

**Fix:** cite a source for each quote or drop the attribution. Give each rejection a concrete trade-off.

### 14. No size limits, and the speed figure has no measurement (D-M10, Y-M1)
**Lines 117–118, 231, 305–306, 499–502.**

- **Speed figure.** "About a millisecond" is not measured, and the 40 KB "current map" does not exist.
- **Search blocks writes.** A search scans layer files on the shared event loop, so one large search delays writes to every project.
- **Log growth.** Archived segments are never deleted.
- **Start-up time.** Replay at start-up can take longer than the 5-second retry.
- **Unstated limits.** Nothing states a limit on projects, map size or subscribers.

**Fix:** state the limits the design is built for. Say whether projects load at start-up or on first use. Set a log retention rule. Measure the write cost before quoting it.

### 15. The riskiest agent choices have no alternatives weighed (D-M11)
**Lines 378–489.**

Three choices have no alternatives:

- **Choosing the running server:** socket binding versus an operating-system lock.
- **The write-ahead log:** a hand-built log versus a built-in transactional store such as `node:sqlite`, with JSON written out for reading.
- **The announcement channel:** WebTransport versus server-sent events on the loopback address.

**Fix:** add each as an alternative with its trade-offs.

### 16. Field names: CUJ 5 uses `technical_name` (Y-M4; Comprehension 10)
**Lines 80–81, 120–121, 178–180.**

The Goals defer the rename from `name_length` to `technical_name`. CUJ 5 uses the new name anyway, so a test for CUJ 5 would not know which field to check.

**Fix:** use `name_length` in CUJ 5, or state that CUJ 5 assumes the rename.

### 17. One relation goes by five names (Y-M5)
**Lines 85–86, 149–150, 315–316, 322–323.**

The two ends of a want are called "depends on / depend on it", "providers", "the elements whose wants name it", "holder" and "other". The latest commit settled on "this element" and "the other element".

**Fix:** use the settled pair everywhere.

### 18. "Author" and "owner" are never said to be the same person (Y-M6; Comprehension 12)
**Lines 3, 25, 188–190, 391.**

"Agent" is also used for both the writer of the design and the clients of the map.

**Fix:** state once who the author and the owner are, and give "agent" one meaning.

### 19. "Option A" is never defined, and it clashes with Alternative A (Y-M7, S-N7; Comprehension 15)
**Lines 296, 459–461.**

**Fix:** describe the option in words, for example "the log is the commit point".

### 20. Claims that outrun the evidence (Y-M2, Y-M3, Y-M10)

- **Lines 58–60, 389.** "Kept in version control": the JSON files live under `~/.metaform`, outside any repository. Say "read or compared as text" instead.
- **Lines 60–62.** "Many concurrent writers" is listed as a Ladybug strength, but lines 40–42 say Ladybug refuses a second writer.
- **Lines 223–224, 479–480.** "Forwarders cover every harness" holds only for harnesses that start local stdio servers.

### 21. The sentence on conversion scope contradicts itself (Y-M11; Stage 5 M2)
**Lines 349–352.**

The sentence says the conversion touches "addresses that appear as values" and also that it "does not touch values". Stage 5 M2 also argues that the conversion belongs in the store, not at the MCP boundary.

### 22. Additional Resources and Future Improvements sit under the wrong heading (S-M6)
**Lines 511–527.**

Both are H3s, so they fall under Non-Functional Requirements.

**Fix:** make both H2s.

---

## 🟢 Nits

- **D-N1 (88–89, 321–322).** One Definitive element is assumed but never checked. Nothing says what happens with zero or two.
- **D-N2 (327–333).** Search does not say whether it matches the snake_case or the camelCase form. It can also see a command that is half applied.
- **D-N3 (279, 349–352).** Nothing says how outside-format content is recognised. A sequence number inside SEP-2640 files changes those files.
- **D-N4 (228, 495–496).** Supported platforms are not stated: Windows named pipes, the file modes, and the length limit on socket paths.
- **D-N5 (372–374, 503–506).** Rollback works only while maps are throwaway. Nothing says what happens to old `.lbug` folders.
- **D-N7 (270–273).** Long layer file names can exceed 255 bytes. Give a rule, such as truncating and adding a hash.
- **S-N8 (345–360).** The list has a stray blank line, and `NAME_ROUND_TRIP_FAILURE` appears before the rule behind it.
- **S-N9 (196–207).** The diagram's viewer line and announcement arrow do not join.
- **S-N10 (7, 184, 491, 511, 515–521).** Horizontal rules are used unevenly, line 184 runs past the wrap width, and links are formatted unevenly.
- **S-N11 (80).** "Reads shaped by position" can mean an owner position or a place in the map.
- **Y-N1 (11).** "The foundation of Topogee's functional map" is a metaphor. Say what the server does.
- **Y-N2 (33–35).** "Nothing more and nothing less" repeats what comes before it. The sentence also mixes the context problem with the lock problem.
- **Y-N3 (17, 78, 173).** "As it commits" should say "after it commits", because the announcement comes at step 9.
- **Y-N4 (270–273).** The case-collision sentence names the wrong form. CamelCase names collide, snake_case names do not.
- **Y-N5 (305–306).** The archive rule is hard to parse. Say "highest sequence number at or below every file's".
- **Y-N6 (333, 345–348, 184).** One sentence is a fragment. "Same pattern" is vague; name UPPER_SNAKE_CASE.
- **Y-N8 (444–450).** "No character any client could reject" and "a dash is allowed by MCP, Claude and OpenAI" cite no source.
- **Y-N10 (117–118, 501–502, 525–527).** The search-index rule is stated three times.
- **Y, lower priority.** "So R-8.2 still holds" (253) states the agent's reading as settled. "Outside parts" (22, 69, 110) is never defined. "A much larger scope" (412) is vague.
