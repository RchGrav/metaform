# Intermediate zoom-out review: map server design (Stage 8)

**Target:** `docs/designs/metaform-server-design.md`, the full file (lines 1–847)
**Reviewer:** egm-zoom-out, using the zoom-out standard

**What the reviewer read:**

- the reports from Stages 5, 6 and 7;
- both background briefs;
- `TOPOGEE-SPEC.md` and `DECISIONS.md`;
- `mcp-server/src/{store,commands,contract,server}.ts` and `mcp-server/package.json`;
- `mcp-tools.proposed.json` and `experiments/map-viewer/server.mjs`.

**Verdict:** changes requested. The review is complete, and the context is sufficient.

## The overall picture

Taken together, the earlier reports would make the design much bigger. They ask for:

- a risk section with 13 items;
- an admin channel that agents cannot call;
- a catch-up protocol with bounds;
- subscriber tokens and origin checks;
- a log for the registry;
- macOS `F_FULLFSYNC`, Windows named pipes and hashed file names;
- measured limits;
- log retention;
- three new alternatives.

Most of that is not needed for a first version. About 60 findings come down to **five root gaps**. Each gap closes with one decision, and several of those decisions **remove** machinery the design already has.

| Root gap | Findings it covers |
|---|---|
| **G1. What a layer is in version 1** | Stage 5 B1; Comprehension 1 (the contradiction), 4; Critic 4 (deleted-file archive rule), 10, 12 (skills, layer files after a delete); D-N3; D-N7; Y-N4; Stage 5 M1 (sequence numbers in layer files) |
| **G2. Server lifecycle** | Critic 1; Stage 5 M6, M7, M8, N6; Comprehension 6; Critic 5, 6 |
| **G3. Commit protocol: too much structure, too few rules** | Stage 5 M1; Critic 3, 4, 14 (log growth), 15 (`node:sqlite`); Comprehension 20; Y-N5 |
| **G4. The browser transport sits inside the writer** | Stage 5 M3, M4; Critic 7, 8; Comprehension 8, 14; the Open Question on the announcement channel |
| **G5. The non-MCP uses of the socket are unnamed** | Stage 5 M5; Comprehension 7; Critic 9 |

Everything else is wording and consistency. It does not change what gets built.

## Smallest set of changes that clears the Blockers

1. **G1:** one paragraph stating that array fields are layer files. Layer registration and the R-6.6 walk wait for D-13 and D-7.
2. **G2:** replace the lock file and the process-id stale rule with one mutex that the kernel releases when the process dies.
3. **Critic 2:** a risk table with one line per risk. Nearly every line points at a fix from item 1, item 2 or the Majors below, or says "accepted for version 1".

## Findings

### 🔴 Z-1. Layers: keep the Blocker, but replace Stage 5's option (b)

**Lines:** 22–23, 160–167, 264–276, 313–333, 684–687, 748–750. Spec: `TOPOGEE-SPEC.md:207`, `:355`, `:495`, `:505–507`, `:520`, `:525`.

**Problem:**

- Stage 5's option (b) would keep everything in `map.json`. That conflicts with R-4.3 and R-6.21, which are Decided: "each layer is kept in its own files".
- Option (a) as written, a registration command plus the walk, cannot be built either. The spec itself says D-13 and D-7 **block Step 4**. The design mentions neither, yet its Step 4 includes R-6.1 to R-6.8.

**Smallest fix:** reuse the rule the code already has. `store.ts:28` treats "every other field" as "a native layer". The contract says "Arrays denote composed element layers" (`mcp-tools.proposed.json:105`). So:

- Intake fields and wants stay in `map.json`.
- Each array field on an element is stored as `layers/<field>/<address>.json`.
- The existing `add`, `update` and `delete` write these files. No new command is needed.
- Deleting an address deletes its layer files.
- "Attached layers" means the layer files present at that address.
- Layer registration (R-6.15) and the walk (R-6.6, R-6.9) wait for D-13 and D-7. Take R-6.1 to R-6.8 out of Step 4, both in the design and in spec section 9.
- `skills[]` is a layer like any other array. The `system` dictionary stays unbuilt.
- Rewrite CUJ 3 and the Step 2 test around an `add` that writes an element together with its `skills` array. That is a real command that changes two files, and it is what justifies the log.

This closes around ten findings with one rule, adds no command, and keeps Decided requirements intact. Option (b) stays available only if the owner explicitly defers R-4.3.

### 🔴 Z-2. Running only one server: neither proposed fix is enough on its own

**Lines:** 228–235, 694–696.

**Problem:**

- The critic's fix is `flock`. Node core has no `flock`, so it needs a native addon. That is the same objection the design uses to reject Ladybug (lines 59–61, 388–389).
- Stage 5's fix, trying to connect before deleting, does not close the race. Two starters can both get a refused connection, then both delete the socket and bind.
- After a reboot, process ids get reused, so the process-id check fails exactly when it is most needed.

**Smallest fix:** a mutex that the kernel releases when the process dies, using only what Node has built in.

- On Linux, a listening socket in the abstract namespace, keyed by `homePath()`, serves as the mutex. Only the process that holds it may delete and bind `server.sock`.
- The lock file and the process-id check go away, so the design gets smaller.
- State the supported platform in the same sentence. That also settles D-N4 and the macOS fsync item.

### 🟡 Z-3. Commit path: store final values in each effect

**Lines:** 262–267, 279, 283–306, 645–665.

Stage 5 M1 (too much structure) and Critic 4 (too few rules) pull in opposite directions. One rule reconciles them: **an effect stores final values**, meaning the whole element record, the whole contents of a layer file, or a removal. Replaying such an effect twice is harmless. With that rule:

- Per-file sequence numbers, log segments and the archive folder go away. That removes Comprehension 20, Y-N5, the archive rule for deleted files, and the need to wrap SEP-2640 files in an envelope.
- One log per project and one checkpoint are enough.

Keep only these of the critic's rules:

- fsync the temporary file before renaming it;
- drop a half-written last log line at start-up;
- reload the project from its files and log after any error past the commit point.

### 🟡 Z-4. Checks that read the map: keep today's split

**Lines:** 287–293.

The design introduces Critic 3's bug. Today `apply` checks only the schema outside the transaction. Every check that reads the map already runs inside `store.transaction` (`commands.ts:153–165`).

**Fix:** keep that split. Step 2 checks shape and grammar only. Every check that reads the map runs at step 5, inside the queue.

### 🟡 Z-5. Announcements: subscribe on the existing socket, receive a snapshot, and take WebTransport out of the writer

**Lines:** 129–131, 171–174, 335–341, 495–498, 772–797.

**Problem:** the design puts the browser's transport inside the only writer. That means HTTP/3, TLS, a certificate renewed at least every 14 days, and a library that `DECISIONS.md:25` still lists as unchosen, all to serve one local, experimental viewer.

**Smallest fix:**

- A subscriber connects to `server.sock`. It receives a snapshot tagged with its sequence number, then each later entry. A reconnect simply subscribes again. The viewer already works this way toward the browser: `server.mjs:14` sends `latest` on connect.
- This removes gap detection, the catch-up protocol and its bounds, and the full-view read. It closes Stage 5 M4 and Comprehension 8.
- If the owner keeps WebTransport for the viewer, it lives in `server.mjs`, with its own certificate.
- "Accepts no network connection" then becomes true for the map server.
- The Step 5 test becomes: "a new subscriber receives a snapshot at the current sequence, then each later entry."

### 🟡 Z-6. Lifecycle: the forwarder understands nothing, and refusals arrive as tool results

**Lines:** 160–167, 230–231, 242–253, 703–710, 738–739.

- **The forwarder exits when its socket closes.** It does not reconnect. Alternative H already rejected a forwarder that understands MCP. CUJ 3 becomes "the next forwarder started restarts the server".
- **The server accepts every connection.** It returns `PROJECT_NOT_REGISTERED` or `VERSION_MISMATCH` on each `tools/call`. For a version mismatch, the remediation is `server restart`.
- **The contract loads once, at start-up.** Today it reloads for every connection (`server.ts:8`).
- **Three one-sentence additions:**
  - every path, including the socket, comes from `homePath()`;
  - the server writes its output to a log file under the home folder;
  - the server runs from the checkout of the forwarder that starts it.
- **Duplicate `add`s on retry are a known risk** and are accepted. Request ids stay deferred.

### 🟡 Z-7. CLI and admin: one handshake field, and reuse the MCP path

**Lines:** 236–238, 370–371, 700–701, 719–727.

- **The handshake carries one of two fields.** A `folder` field opens MCP for one project. An `"admin": true` field opens one-line JSON requests: register, projects, settings, set, status, stop and subscribe.
- **`--import`, `--export` and project commands** connect with a folder and send one `tools/call`. That meets R-5.14 at no extra cost, and imports run full validation through the normal commit path.
- **`restart` is `stop`.** The next forwarder starts the server again.

**Rejected:** the critic's "admin channel agents cannot call". Agents run as the same user and have a shell, so nothing can enforce it before D-8.

### 🟡 Z-8. Downgrade Critic 2 (no Risks section) from Blocker to Major

**Lines:** the whole document; 491–510.

The content of the risk section comes from the fixes above, and its absence does not stop the build. Write it as a table with one line per risk. Most lines point to Z-1 to Z-7 or say "accepted for version 1". The accepted risks are: a full disk, the dashed tool name, a duplicate `add`, log growth, size ceilings and platforms.

### 🟡 Z-9. Stage 5 M9 is confirmed: Step 6 is already done, so cut it

**Lines:** 547, 799–820.

`TOPOGEE-SPEC.md:211–241` already holds R-4.4 to R-4.13, and `DECISIONS.md:12` already holds the new wording. Spec section 9 (`TOPOGEE-SPEC.md:497`) still lists Step 6. Remove Step 6 from both, and keep section 9 in step with Z-1.

### 🟢 Z-10. Downgrade Critic 14 and 15 to Nits

**Lines:** 499–502, 378–489.

- **Speed claim.** Replace the unmeasured "about a millisecond" with one line stating the scale the design is built for.
- **No premature limits.** Do not require limits, retention, measurements or a search that avoids blocking writes before a bottleneck is seen (R-5.20).
- **`node:sqlite`.** Add it only as a one-line rejected alternative. R-4.1 and position 14 require readable JSON.
- **Single-instance alternative.** This one folds into Z-2.

### 🟢 Z-11. Critic 13 is partly wrong

**Lines:** 391–393, 414–416, 448–451, 459–461.

Three of the five quotes trace to Source lines in the spec:

- "dash if its allowed" is at `TOPOGEE-SPEC.md:249`;
- "please make recommendation" is at `:237`;
- the design paraphrases the chassis line at `:217`.

Only "kinda sucks" and "no data needs to move" have no source. Link the spec instead of finding a new source for every quote.

## Recommendations to reject as unneeded complexity

- **`flock`:** it needs a native addon.
- **A subscriber token and origin check on the map server:** these are moot once announcements use the 0600 Unix socket.
- **A catch-up protocol, bounds and gap detection:** replaced by the snapshot on subscribe.
- **A log for the registry and settings:** each is one file, and a single rename is already atomic.
- **macOS `F_FULLFSYNC`, Windows named pipes and hashed file names:** a one-line platform statement settles these.
- **Limits, measurements, log retention, and replay time against the 5-second retry:** premature at this scale.
- **An admin channel that agents cannot call:** it cannot be enforced before D-8.
- **An MCP-aware forwarder that reconnects:** the forwarder exits instead.
- **Stage 5 B1 option (b):** it conflicts with Decided R-4.3.
- **A full domain model inside the design (Comprehension 1):** link to the spec sections instead.
