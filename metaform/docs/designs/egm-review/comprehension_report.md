### What this proposes

There will be one long-running Node "map server" per home folder (`~/.metaform`). It is the only process that writes each registered project's map and layers, which are stored as plain JSON files. Each agent's MCP process becomes a simple forwarder. It connects to the server over a Unix socket, sends a one-line handshake naming its folder, and then passes bytes both ways. The server checks each write, converts names from snake_case to camelCase, and queues the write for its project. It records the write's effect in a log that is synced to disk; that sync is the commit point. It then updates memory and the files, answers the agent, and announces the change over WebTransport. Reads change shape: an address read returns only that address and what it is directly linked to, the root read returns a bare index of addresses and edges, a layer read returns layer content, and search answers with `Found:` lines saying where a match is. The tool is renamed `project-map`. Every refusal gets a code, the rule broken, a plain reason and a fix. Ladybug is removed.

### How the existing system works, per this document

Each agent's harness starts its own MCP server process over stdio. Each of those processes opens the project's Ladybug database directly. Ladybug allows only one read-write process per file, so a second agent on the same project is locked out. Nothing announces changes. The map viewer polls every 1.5 seconds: it copies the database files, starts a new Node process to export the whole map, and compares the result. A read returns the address and everything beneath it, and a root read returns every intake field in the project. Schema refusals return the validator's raw pattern message. The tool is called `metaform_apply`. Looking up an unknown folder registers it as a project without being asked.

---

# Comprehension review: map server design (Stage 6)

**Target:** `docs/designs/metaform-server-design.md`. The feature range is lines 1–535, and the detailed range is lines 536–847.
**Reviewer:** egm-comprehension. The reviewer read the target alone, with no standard and no background reading.

The review is complete. No section was impossible to paraphrase, so there are no Blockers. There are 10 Major findings and 10 Nits.

## Findings

**1. 🟡 Major: the domain model is never defined**
- **Where:** lines 22–23, 82–86, 115–116, 148–150, 178–180, 264, 274, 315–316, 323–324, 569, 649
- **The gap:** The design depends on a set of nouns it never defines: element, address, intake, intake fields, intake layer, wants, providers, root registries, the want record and its grammar, intent, and the `orphaned` command. The reviewer had to guess these from examples. For instance, they worked out that a "want" names another element only from the description of edges at line 323.
- **Why it matters:** The fields an address read returns are never listed. The only clues are scattered: `name`, `technical_name`, `name_length`, `goal`, `function`, `why`, `how` and `intent`.
- **A contradiction:** Layers are "kept in their own files" (line 22), yet the intake layer lives inside `map.json` (line 274).
- **Why it matters for testing:** A new reader cannot check that an address read is "exactly what is needed", because they do not know what an element contains.

**2. 🟡 Major: requirement, decision and position references carry the argument but are not explained or linked**
- **Where:** for example lines 51–57, 75, 91, 135, 138, 253, 275, 315, 382, 806
- **The gap:** References like R-5.8, R-5.24, R-6.6, R-6.15, R-8.2, R-4.2, D-4, D-8, D-9 and D-10 are cited bare. The document never says which file holds them. `TOPOGEE-SPEC.md` is listed at line 519, but it is not linked and not tied to the IDs.
- **Examples a reader cannot follow:**
  - "so R-8.2 still holds" (line 253) is meaningless without the text of R-8.2.
  - "the walk of R-6.6" decides which layers are active, and that drives both the address read and search.
  - R-5.24's list of codes is what the three new codes are meant to fit.
  - R-6.15's `system` dictionary is the alternative in an open question.
- **Owner positions:** The positions are linked to the brief, but several decisions rest only on "position N" with no summary next to them.

**3. 🟡 Major: "the one Definitive functionality" is not defined**
- **Where:** lines 89, 322, 436–437, 763
- **The gap:** This is a field (`definitive`) in the root read's output, and a test asserts it. Nothing says what makes one functionality Definitive, who sets it, or where it is stored.

**4. 🟡 Major: which layers are active, and how layers get written, is not explained**
- **Active layers** (lines 132–133, 314–315, 329, 333, 750, 756): The address read and search both use the layers "active at that address after the walk of R-6.6". Line 133 also speaks of a layer "switched off at an address". Neither the walk nor switching a layer off is explained.
- **Writing layers** (lines 22–23, 110, 162–163, 325–326, 685): The document says outside parts "add [layers] through the server". CUJ 3 relies on "a command that registered a layer and wrote its first data". However, no command for registering a layer or writing layer data is shown. The contract changes in Step 1 add only reads and search.
- **Why it matters:** A reader cannot tell how a layer comes to exist, so they cannot follow CUJ 3 or the crash test in Step 2.

**5. 🟡 Major: the Open Questions list items that the body has already decided, so it is unclear what is settled**
- **Server language:** "not stated" (lines 126–128), but the design says "one long-running Node process" (line 214) and the whole plan is TypeScript.
- **Search scope and cap:** open (lines 132–133), but decided as the agent's choice at lines 327–333 and tested at line 768.
- **Skills:** "are they layers?" is open (lines 134–135). Yet line 317 reads skills as a layer named `skills` ("This is also how an agent gets a skill's body"), and the address read returns skill frontmatter (lines 83–84).
- **Shape of `wants` (D-4):** open (line 138), but `map.json`, the edges and the neighbour lists all depend on it.

**6. 🟡 Major: it is unclear how "the next forwarder call starts it again" works after a crash**
- **Where:** lines 164–165, 230–231, 707–710, 738–739
- **The gap:** A forwarder connects once, sends its handshake, and then only passes bytes. The MCP session is negotiated directly between the agent and the server, through that one connection. The document never says what a forwarder does when its socket drops in the middle of a session. Does it reconnect and send the handshake again? Does it restart the server? How does a session continue without the agent sending a new MCP initialize?
- **Why it matters:** CUJ 3 and the Step 3 test both depend on this behaviour, but it is not described anywhere.
- **Related:** "exits, so the harness starts the current one" (line 251) assumes harnesses restart MCP servers that exit. That assumption is not stated.

**7. 🟡 Major: the CLI's interface to the server is not specified**
- **Where:** lines 236–238, 370–371, 701, 722–726
- **The gap:** Every CLI command, including `register`, `--import`, `--set`, and `server status|stop|restart`, becomes "a call to the server". The only connection protocol described is the forwarder's folder handshake followed by MCP. Several questions are left open:
  - Does the CLI use the socket with a different handshake, MCP tool calls, or a separate admin protocol?
  - `register` and settings are not `project-map` commands, so what carries them?
  - `daemon.ts` handles `status` and `stop`, but not `restart`.
- **Also undefined:** `--projects` and `--settings` (line 724).

**8. 🟡 Major: how the viewer gets its starting picture, and its certificate hash, is not explained**
- **Where:** lines 171–174, 337–341, 785–786, 791–793
- **The gap:** Announcements carry only changes, and a subscriber can fetch missed log entries. Nothing says how a newly opened viewer loads the current map. The export path it used before (`--database --export`) is removed at line 726.
- **A second gap:** `server.mjs` is to "pass the certificate hash" to the page. But the certificate belongs to the map server, which is a separate process that renews it, and the document does not say how `server.mjs` obtains it.
- **Also unexplained:** what happens when a subscriber needs entries from log segments that have been archived (lines 305–306, 664–665).

**9. 🟡 Major: the build order has forward dependencies, so "each step ends with its tests passing" is hard to believe**
- **Where:** lines 538, 566–569, 631, 680–681, 687
- **The forward references:**
  - Step 1 moves `commands.ts` onto "the effect interface of Step 2".
  - Step 1 also changes the contract to accept `search` and `layers`, but those are not implemented until Step 4.
  - Step 2 has `tree.ts` read and write "through the server", which is built in Step 3.
  - Step 2's test "Concurrent writes are all applied in order" depends on the per-project queue, which lives in `daemon.ts` (Step 3).
- **Why it matters:** A reader cannot tell how each step builds and passes on its own.

**10. 🟡 Major: CUJ 5 uses a field this design says it does not introduce**
- **Where:** lines 178–180, set against lines 80–81, 120–121 and 632–635
- **The gap:** CUJ 5 describes an element "whose `technical_name` is 'packet ring buffer'". The Goals, Non-Goals and Step 1 all say field names stay as the store has them. They also say the `name_length` to `technical_name` rename is separate work.
- **Why it matters:** A reader cannot tell which fields exist under this design.

**11. 🟢 Nit: "Metaform" and "Topogee" are never related**
- **Where:** lines 12, 63, 101, 441
- **The gap:** The project is Topogee, but the home is `~/.metaform`. The old tool is `metaform_apply`, there is a `metaform.schema.json`, and line 63 cites "the earlier system's" map in `metaform-canonical.json`. Nothing says whether Metaform is the earlier system, the method, or the current product.

**12. 🟢 Nit: "agent", "owner" and "author" are used ambiguously**
- **Where:** lines 188–190, 270–273, 296, 459, 471
- **The gap:** "Agent" means both the AI that wrote this design ("agent's choice") and the clients of the map ("the agent's snake_case address"). Line 270 uses both senses in one bullet. The document also never says whether "the owner" and "the author" (Rich) are the same person.

**13. 🟢 Nit: the refusal codes are both decided and waiting for the owner**
- **Where:** lines 345–347 and 810–811
- **The gap:** Line 345 says the design adds three named codes. Step 6 says they are added to R-5.24 "once the owner names them".

**14. 🟢 Nit: the security section contradicts itself**
- **Where:** lines 496–498
- **The gap:** "Accepts no network connection" is immediately followed by a WebTransport listener on `127.0.0.1`, which is a network listener even though it is local only. The text also does not say that any local process can subscribe to every project's changes.

**15. 🟢 Nit: "option A" refers to options that are never shown**
- **Where:** lines 296 and 461
- **The gap:** Option A is never listed alongside the other options. Alternative G only hints at what they were.

**16. 🟢 Nit: several terms are used without explanation**
- **SEP-2640** (lines 352, 613) is not explained or linked.
- **ACP harness** (line 112) is not explained.
- **"The method"** (line 115) is not defined.
- **The chassis, its modules and "the hook"** (lines 108–111, 487–489) are described only as "a separate part of a larger vision".

**17. 🟢 Nit: the file layout leaves details unexplained**
- **Where:** lines 260–263
- **The gap:**
  - `<encoded path><n>`: neither the encoding nor `<n>` is explained.
  - The registry stores both "path" and "folder" without saying how they differ.
  - `source.txt` is marked "(unchanged)" without saying what it is unchanged from.

**18. 🟢 Nit: the forwarder takes its folder in two different ways**
- **Where:** lines 145–146 and 706
- **The gap:** CUJ 1 starts the forwarder *in* `/work/game`, which suggests its working directory. Step 3 says it "takes the project folder as its argument".

**19. 🟢 Nit: the read shapes are partly unspecified and inconsistently named**
- **Where:** lines 313–326, 755
- **The gap:**
  - The address read's response is not shown as JSON, unlike the root read's.
  - Line 325 does not say what `{".": {"layers": ["x"]}}`, a root read with named layers, returns.
  - Line 322 does not say whether `addresses` includes intermediate namespace segments.
  - "Trunk-to-leaf path" (line 755) and "address path" (line 328) seem to mean the same thing, but the document does not say so.

**20. 🟢 Nit: the log archiving rule is hard to parse**
- **Where:** lines 305–306 and 664–665
- **The gap:** "Segments whose entries are in every saved file" presumably means every file's saved sequence number has passed the segment's last entry. The document should say so directly.
