I'll start by reading the head of the log to learn its structure.

The log is large and mixes tool output with chat. I'll map its structure with a few searches before reading the rest in parts.

The log is 4,035 lines. I'll read the remainder in chunks, starting after the part already read.

# Metaform Context Recovery: Handoff for Fable

## 1. Executive summary

The only source is the uploaded log, `/mnt/user-data/uploads/6642ba87-other_fable.md`. It has 4,035 lines and covers 2026-11-15, from about 5:45 PM to 7:25 PM. Its timestamps have no time zone. The log starts mid-session, so earlier work appears only as quotes and summaries.

The log describes the Rust form of Metaform, a project-map tool. It lives in `/home/rich/metaform`, branch `fable-climb`, under the WSL user `rich`. Agents read and write a map of a project through one tool.

Main points recovered:

- The log's assistant recorded 40 numbered decisions in a specification. Most are labelled "Decided by the maintainer," not decided by the founder.
- The assistant built six small changes. It committed them as `943ac06` and pushed to `fable-climb`. The test suite then reported 77 passed and 0 failed.
- Near the end, the founder wrote that he had been talking to the wrong agent (L4020). The log does not say which messages were meant for another project.

Cautions before use:

1. Do not treat a decision as settled because the log calls it decided. The founder objected to having his words recorded as his decisions (L1969).
2. Several decisions conflict with each other or with earlier founder statements. Section 8 lists them.
3. Nothing here was checked against any repository. Fable must verify each item in its own environment.
4. The log's assistant is named "claude-fable-5-2," the same name as the recipient. This handoff calls it "the log agent."

## 2. Source and environment inventory

**Confirmed by recorded evidence:** I read the whole uploaded log. No other file was attached. I did not run commands, change files, or create memories.

Line references in this document (L###) point to line numbers in the uploaded file. Speaker labels used here:

- **Founder:** lines that begin with the prompt marker `❯`.
- **Log agent:** assistant text blocks that end with a timestamp and "claude-fable-5-2."
- **Subagent report:** blocks headed "Message from general-purpose" or "Agent(...) finished."

| Source | Status | What the log shows |
|---|---|---|
| Uploaded log (4,035 lines) | Reviewed in full | The only evidence. It mixes chat, commands, tool output, and subagent reports. |
| Repository `/home/rich/metaform` | Not accessible | Named throughout. The log shows commits and pushes there. |
| Branch `fable-climb` | Not accessible | Named in push output (L3812). |
| Archive `/home/rich/metaform/archive/metaform-2026-11-15/` and its `.tar.gz` | Not accessible | Named. The log says the folder is untracked by git (L1075). |
| Copy at `/mnt/c/metaform-2026-11-15.tar.gz` | Not accessible | Named as the copy target (L557, L566). |
| `SPECIFICATION.md` (archive) | Not accessible | Only edits and search output appear in the log. |
| `dev/HANDOFF.md` (repository) | Not accessible | Shown only in fragments and interleaved diffs (L1057–L1065). |
| `metaform/SPEC.md` (repository) | Not accessible | Short records added (L2189–L2198, L2484). |
| Memory folder `~/.claude/projects/-home-rich-metaform/memory/` | Not accessible | Listed at L792–L802. |
| SEP-2567 web page | Not accessible | Extract only (L268–L430). |
| Founder's new glossary | Not seen | The log agent never opened it (L3058). |
| `~/brain` | Not accessed | Named (L1104, L1169). |
| Repository `CLAUDE.md`, `EXPECTATIONS.md`, `START_HERE.md` | Not accessible | `CLAUDE.md` appears only in search output, truncated (L2857–L2865). |
| synthetictaxonomy.com | Not visited | Named by the founder (L3305). |
| "The other WSL" | Not visible | The log agent could not see it (L2943). |

**Environment facts from the log:**

- The WSL user is `rich`. Paths start with `/home/rich`. The log does not name the WSL distribution.
- The repository is `/home/rich/metaform`. The Rust workspace is `metaform/rust`.
- The branch is `fable-climb`. The commit before the session is `1798c6e` (L1074). The session commit is `943ac06` (L3811).
- Session scratch paths use the session identifier `ee9787a3-f31c-418a-a175-fc95675b7c5a` (L555).

**Variant identification (Inferred):** The log calls this the "Rust form." The same repository also holds a Node form, a Python form, and a conformance set. Those still use SQLite and older terms (L1207, L1230). Whether this repository is the one Fable works on is **Unknown**.

**Completeness limits:**

- The log starts at L1. The first visible founder message is at L220.
- Some quoted text is cut off, notably `CLAUDE.md` (L2857–L2865).
- Some diffs show old and new lines interleaved (L1057–L1065). The final text of `dev/HANDOFF.md` cannot be rebuilt from the log.
- The log gives no time zone. The request arrived at 19:35 New York time. The log's last timestamp is 07:25 PM. Whether they match is **Unknown**.

## 3. Instructions and working agreements

Status labels: **Explicitly stated** means the founder or a repository file said it. Rules marked "log agent" were written by the log agent.

| # | Instruction | Given by and scope | Status | Source | Caution for Fable |
|---|---|---|---|---|---|
| 1 | Use subagents to save your context. If something must be right, do it yourself. | Founder, to the log agent | Explicitly stated | L1009 | Guidance for that agent. Check it before adopting. |
| 2 | Choose a subagent model by the inference the task needs. Use Haiku for direct instructions, Sonnet for familiar coding, Opus for complex work, and Fable only for the deepest reasoning. | Founder described the models (L774). The rubric is the log agent's (L805–L829). | Explicitly stated (founder). Rubric: log agent. | L774, L805 | The founder's model descriptions are his. Verify them. |
| 3 | Write for a low-context reader. Lead with key points, use plain words, and use short sentences. | Block at L1010–L1014 | Explicitly stated. Origin **Uncertain**: the block is indented like the founder's message but not marked. | L1010–L1014 | Confirm the origin before applying it as a founder rule. |
| 4 | Do not record what the founder says in a working conversation as his decision. | Founder, to the log agent | Explicitly stated at L1969. Later overtaken by L2308 and L2475. | L1969, L2308, L2475 | Two founder messages pull in different directions. See section 8, item 2. |
| 5 | Give reasoning with every decision, in the writer's own words. Do not write "the founder said" as the reason. | Founder, to the log agent | Explicitly stated | L1969–L1970, L2205 | This applies to Fable's records too. |
| 6 | Agents may message the founder to report. They may not message him to ask for a decision or a question. | Founder, L3387 | Explicitly stated for agents | L3387 | The log agent added an exception for "a fact only he holds" (L3415). The founder did not say that. |
| 7 | Spec and code differ: the spec is "more up to date." | Founder (L902) | Explicitly stated at L902. Later changed by the log agent (L2006). | L902, L956–L957, L2006 | The log agent later wrote "the code is what changes." The founder did not confirm that. See section 8, item 6. |
| 8 | Permissions are in how prompts and instructions are written. Nothing stops an agent in a stateless system. | Founder, L1911 | Explicitly stated | L1911 | Conflicts with the token in decision 39. See section 8, item 4. |
| 9 | The map lives locally. Each user has their own. It is not shared with remote users. | Founder, L2475 | Explicitly stated (the founder's own statement) | L2475, L2508 | Scope of the credential decision. |
| 10 | MCP is stateless: no session. | Founder, L220 | Explicitly stated as the founder's claim. The log agent confirmed a summary of SEP-2567 (L281–L300). | L220, L1832 | The SEP page says it is a historical record. Check the current MCP specification. |
| 11 | MCP is for data. A feature that is MCP is wholly MCP. Command-line commands are separate. | Founder, L630 | Explicitly stated | L630 | The build does not yet follow it (L668–L674). |
| 12 | Metaform works across projects. Every map is available at the root by project name. | Founder, L1832 | Explicitly stated | L1832 | Form of the path is open. |
| 13 | Agents may message each other across project boundaries. | Founder, L3497 | Explicitly stated | L3497 | Only the rough direction is stated. |
| 14 | Move the MCP server to local HTTP first. Follow the evolving remote-host protocol ("ACP") and build your own only where it does not fit. | Founder, L3907 | Explicitly stated | L3907, L3950 | "ACP" is never defined in the log. |
| 15 | No change is pushed into an agent's context. Call the inbox a handoff overlay. | Founder, L3305 | Explicitly stated | L3305 | The log agent first removed the page subscription, then restored it (L3352, L3398). |
| 16 | Procedure text and prompt grammar are formulas. Do not reword them. | Repository `CLAUDE.md` (L2861) and handoff (L1094) | Explicitly stated | L1094, L2861 | Carried from earlier sessions. |
| 17 | Intake is done fresh. Do not preserve or convert the present procedure or old maps. | Founder, L2809 | Explicitly stated | L2809, L2886–L2887 | Decisions 28 and 29 follow it. |
| 18 | Remove or update the glossary in `CLAUDE.md` and agent files if present. | Founder, L2809 | Explicitly stated. The log agent found none (L2937). | L2809, L2937 | None exists in the files it checked. |
| 19 | Reusable context is named by address. Instructions say "Must read these URI to perform intake properly." | Founder, L3067 | Explicitly stated. The log agent changed the words (L3079, L3098). | L3067 | Use the founder's words. |
| 20 | Prompts are named Markdown files in a `prompts` folder per plugin. No XML. Variables use a Jinja-like pattern. | Founder, L3194 | Explicitly stated. The `{{ name }}` syntax is the log agent's choice. | L3194, L3210 | "Plugin" or "module" is unresolved (section 8, item 16). |
| 21 | Refs are an entry point or a discrete reference, not an index. Use an overlay for more data. | Founder, L2562 (vote) and L2626 | Explicitly stated | L2562, L2626 | Founder's 2026-11-12 view that refs "will not work" (L1194) is also cited. |
| 22 | Use well-named fields and full role names, such as Defining Element, not DE. | Founder, L2695 | Explicitly stated | L2695 | The procedure keeps its own terms. |
| 23 | CQU is the intake's term. It is never a segment of an address. Use the founder's definition wording. | Founder, L2954 | Explicitly stated for the wording. The address rule and the name "Vested Beneficiary" are the log agent's. | L2954, L3025 | Text differs in one apostrophe (section 8, item 13). |
| 24 | LadybugDB is the engine. Do not store one record per element with every field in it. | Founder, L1462 | Explicitly stated | L1462 | Founder's reason for the engine. |
| 25 | One database per project, or more. | Founder, L1514 and L1598 | Explicitly stated | L1514, L1598 | Chained maps may get their own database. |
| 26 | Never leave a subagent's model unset. An unset model runs on Fable. | Log agent's memory | Log agent's rule | L805–L829 | Cost reason. |
| 27 | Make a feature commit and push it before the owner tests. Bugs get a note in `metaform/docs/trouble-log.md`. | Repository `CLAUDE.md` (owner instruction of 2026-11-09) | Explicitly stated. The text is cut off in the log. | L2862–L2865 | The log agent did not cite this rule when it committed (section 8, item 2). |
| 28 | The intake procedure, its semantics, the schema, and the tool contract are protected. Do not change them without the owner's direct instruction. | Repository `CLAUDE.md` | Explicitly stated. Cut off. | L2860 | The six changes edited the schema and tool contract (section 8, item 3). |
| 29 | Do engineering work and make supported decisions. Bring back only owner-dependent decisions. | `CLAUDE.md` refers to `EXPECTATIONS.md` | Explicitly stated. File not seen. | L2858 | Interacts with the founder's "make a decision" request (L2308). |
| 30 | Do not write a test that reads the content of the procedure. | Earlier handoff | Explicitly stated | L1096, L1255 | Carried forward. |
| 31 | Do not show the founder the page that `metaform gui` serves, or any page in `metaform/workspace`. | Earlier handoff | Explicitly stated | L1232, L1278 | He rejected them. |
| 32 | Ask before saving a memory. Do not edit `~/brain`. | Earlier handoff and existing memory | Explicitly stated | L787–L791, L1104 | The subagent rubric was an exception the log agent inferred (section 5). |
| 33 | Do not commit `TASTE.md`. It holds the founder's uncommitted edit. | Earlier handoff | Explicitly stated | L1084 | |
| 34 | Do not use `pkill`, `killall`, or `pgrep -f`. End a process by its ID. | Earlier handoff | Explicitly stated | L1281 | |
| 35 | Keep the full output of every test run. Read the result before packing the archive. | Earlier handoff | Explicitly stated | L1122–L1123, L1270, L1284 | |
| 36 | Say what you will change before you change it. Make one change at a time. | Earlier handoff | Explicitly stated | L1102, L1260 | |
| 37 | Report plainly when wrong. Correct the record in the next commit message. Never rewrite a commit. | Earlier handoff | Explicitly stated | L1105, L1265 | |
| 38 | A socket path holds at most 107 bytes. Use a short test home such as `/tmp/mf1`. Remove it afterwards. | Earlier handoff | Explicitly stated (technical) | L1282–L1283 | |
| 39 | Do not open `~/.metaform`, `~/.metaform-rust`, or `~/.metaform-sqlite` in a test. | Earlier handoff | Explicitly stated | L1234, L1278 | |

## 4. Decisions and rationale

The log numbers decisions 1 to 40 in section 13 of the archive specification. Decisions 1 to 37 were recorded by 2026-11-15 19:18. Decisions 38 to 40 were added later (L3498–L3517, L3914–L3921). Each row cites the decision number where the log gives one.

**Status labels:** "Built" means the log shows code, test output, or a command result. "Decided, not built" means the log records it and no code change appears.

| Decision or question | Recorded outcome | Rationale and evidence | Status | Source | Caution for Fable |
|---|---|---|---|---|---|
| 1. Stateless server (no memory per connection) | `goto` returns the whole sheet every time. The server keeps no record per connection. | MCP has no session. Clients keep connections for different lengths of time, so a saving that depends on a connection fails silently for some (L3787–L3789). | **Built** in `943ac06`. Test output shows two `goto` calls returned equal output (362 bytes). | L3755, L3787 | Verify against the current MCP specification. |
| 2. Project name in paths | A path that starts with a project's name reaches that project. A root such as `code` means the agent's own project. | Founder: "all maps will be available at root if you name the project" (L1832). Whether a path with no name still means the agent's own project is open (L1904). | Decided, not built | L1832, L2365 | Founder has not confirmed the path form. |
| 3. Durable project name | Given once, unique per home. Registry keyed by name. Folder is a changeable property. | The build finds a project by folder path, so a moved folder becomes an empty new project (L1355). | Decided, not built | L1355, L2342 | The form is open: `mashtrac`, `carverj/mashtrac`, or an ID (L1905). |
| 4. No permission and no credential in the tool. The home is the boundary. | Every agent runs as the same user and can open the data directly. A check in the tool cannot stop it. | Founder's basis: "the map lives locally" (L2475). Log agent's reasoning at L2236–L2246. | Decided by the log agent. Founder's basis confirmed. | L2236–L2246, L2475 | Conflicts with decision 39. Founder earlier said "lets use credentials" (L2156), then questioned it (L2219). |
| 5. One back end: Rust server with LadybugDB. SQLite goes. | Stop the second store. Node and Python become thin processes, or are dropped. | Founder: "fine with moving to ladybugdb" (L1462). Log agent: two engines drift apart (L2529). It has no measurement that compares the two engines (L1805). | Decided, not built | L1462, L1779–L1800 | The speed figures come from project notes and are not checked. |
| 6. One database per project, or more | Decided. A want stays inside one database. | Founder (L1514). Each project keeps its own writer (L2531). | Decided. Built, per the log agent (L1561). | L1514, L1561 | "Or more" allows a chained map its own database. |
| 7. Link to another project's map | A ref `metaform://map/<project>` on an element. The `childMap` property goes. | Founder's cases: an engine used by a game (L1598) and two projects that rely on each other (L1681). | Decided, not built | L1598, L1681, L2354 | Open: which version a product map describes, and whether projects share one copy. |
| 8. Layer records stay in the project database | Keep records as rows in the database. | One transaction covers an element and its records. A file for each address would make tens of thousands of files (L2371–L2372). | Decided by the log agent. Built. | L2371, L2432 | **Conflicts with an earlier founder decision** that each layer has its own files (R-4.3, R-6.21, cited at L2432 and L2544). No founder reply appears. |
| 9–10. Definitions state record structure in `fields`. Only `markdown_blocks` is a rule. | Required by default. `"optional": true` marks optional fields. | Most fields are required. A rule over a whole list cannot be stated as a field type (L2375–L2376). | Decided, not built | L2375–L2376 | Depends on the new procedure. |
| 11. Role names written in full | Stored values are full names. Abbreviations are refused with the corrected command. | An agent that has read no glossary cannot read "DE" (L2010). | Built (commit `874b0a0`, per L1178) | L1177–L1178, L2010, L2695 | Abbreviations still appear in the procedure. |
| 12. Coupled Element role | A role for a supporting element bound to the element it serves. | Founder was shown the wording and said to go ahead (L1180). | Built (commits `874b0a0`, `1798c6e`) | L1179–L1180, L2012–L2020 | Founder did not restate the wording. The log agent lists the arguments against it. |
| 13. Word for knowledge laid over the map | "Overlay." The root that defines overlays stays `layer`. | Founder says "overlay" every time (L3305). A name the founder never uses will not hold (L3379). | Decided. The specification still says "layer" throughout. | L3316, L3379 | Founder never confirmed the root word. See section 8, item 11. |
| 14. Specification layer path | Stays at `layer.document.specification`. | Matches every other definition beneath a root type. | Decided | L2380 | |
| 15. `metaform call` and `specification import` | `call` goes. `specification import` stays. The web host's `/call` and `/write` routes stay. | `call` is a second surface for the same tool. The test harness uses it (L762). | Decided by the log agent. **Not built.** Founder's answer not in log. | L762, L764, L2328–L2330, L2384 | Log agent asked "say 'remove call'" (L764). No yes appears. |
| 16. Fixed command names | Only `add`, `update`, `delete`, `orphaned`, `goto`, `map`, `help` are commands. Other keys are paths to read. | A one-segment path such as `code` must be reachable. A rule that every key without a period is a command would block it. | Decided by the log agent. Built. | L2385 | **Replaces founder's rule R-5.1** (L911). Founder said he did not know which side was stronger (L1327). |
| 17. Corrected command in refusals | Return a corrected command only when one follows. Return none when the tool would have to guess. | A guess offered as the fix is followed, and a wrong guess does damage. | Decided by the log agent. Built, per the log agent. | L2386 | Replaces R-5.24 (L911). |
| 18. Remediation never changes unrelated fields | Stated as a rule. The build breaks it in one case (`FIELD_ELEMENT_COLLISION` removes a field). | Agents follow remediations without checking the rest of the map. | Decided. **Build fault, not fixed.** | L1218, L2387 | Not in the six changes. |
| 19–20. Wants as a list. Delete one want by record. | `wants` is always a list (19, built). One want is removed with `{"element", "ref"}` (20, not built). | A want's key is its element plus its ref. | 19 built. 20 not built. | L2388–L2389, L1208 | `delete` currently removes every want on an element. |
| 21. Refs | An element holds `refs` as an entry point or discrete reference. A layer record holds one `ref`. | Founder voted for element refs in the base map (L2562) and limited them to entry points (L2626). | Wording built in `943ac06`. Per-record `ref` not built except for wants. | L2562, L2616, L2626, L3744 | Founder's 2026-11-12 view that refs "will not work" (L1194). |
| 22. `collection` removed as a root | Roots are `code`, `document`, `media`, `data`, `upstream`, `downstream`, `layer`. | `collection` names no kind of functionality (L2391). | **Built** in `943ac06` (L3733). | L2391, L3733 | A stored map with `collection` still loads. |
| 23. A name may equal `technical_name` | Allowed. | Refusing it made test agents invent names (L2392). | Built | L2392 | |
| 24. No instruction sent at connection | The server's connection answer holds no instruction. | Every agent paid for the text on each connection (L2547). | **Built** in `943ac06`. | L2547, L3631 | Founder's acceptance not shown. |
| 26. Agents need no glossary; the procedure is read to perform an intake | Help text changed. | Plain names make the glossary unnecessary for ordinary work (L2735). | Help text **built**. Procedure rewrite not done. | L2735, L3647 | Founder's new glossary not seen. |
| 27. First read is the shape: `{"map": {}}` | Shape read is built. The version with all wants is not built. | Shape of the test map is 6,085 bytes. With why and how it is 28,559 bytes (L2722–L2725). | Shape built. Wants variant not built. | L2722–L2725, L2790–L2796 | Measured on one test map of 113 addresses and 68 wants. |
| 28–29. Procedure written fresh. Maps made fresh by intake. | No conversion of the old procedure or maps. Old procedure text to be removed from the archive. | A text repaired piece by piece toward a moving tool is never right (L2922). | Decided, not done. | L2886–L2887, L2922 | Founder writes the new procedure. |
| 31. Reusable context named by address | An instruction names its resources with "Must read these URIs..." | One text serves many tasks. The agent decides whether to re-read (L3120–L3122). | Decided. Not built. The server already serves `metaform://intake/<section>`. | L3079, L3131 | Wording changed from the founder's (section 8, item 14). |
| 33. Prompts as named Markdown files | Each plugin has a `prompts` folder. Variables use `{{ name }}`. | One XML file puts every edit in one place (L3246). | Decided. Not built. | L3206–L3212 | Founder asked for the pattern. Braces are the log agent's choice. |
| 34. No change pushed into an agent's context | No broadcast. The page keeps its live feed. | Pushed changes are paid for whether or not they matter (L3350). | Decided. The page feed is kept. | L3350, L3398, L3427–L3431 | Reversal after first decision. |
| 35. Handoff overlay | Free Markdown notes left at an element, read by the next agent that works there. | Knowledge passes at the place of the work (L3365). | Decided. Not built. | L3320, L3365 | Founder named it (L3305). |
| 36. Agents' inbox | Belongs to the agents module, not to this tool. | An inbox needs an agent name on each request, and the tool knows none (L3371). | Decided. Not designed. | L3321, L3371 | |
| 37. Agents report; they do not ask | Messages to the founder may report. They may not ask for a decision or a question. | A way to ask becomes a way to stop (L3437). | Decided. | L3387, L3435–L3439 | The "fact only he holds" exception is the log agent's (L3415). |
| 38. Notes across project boundaries | A handoff note left at another project's element by a path with that project's name. | Founder asked for it (L3497). The log agent moved it ahead of other cross-project writes because it adds one record and changes nothing else (L3545). | Decided. Not built. | L3497, L3545 | The log agent's reasoning, not the founder's. |
| 39. Local HTTP with checks | MCP served on the loopback address. The server checks `Host` and `Origin`. A token file in the home is required on each request. | Founder: "move to local http for the mcp server initially" (L3907). The log agent proposed the token (L4000–L4002). | Decided by the log agent. Not built. The MCP library's HTTP support is not checked. | L3907, L3915, L4000–L4004 | **Conflicts with decision 4** (no credential in the tool). |
| 40. Agents across hosts | Follow the remote-host protocol as it settles. Write your own only where it does not fit. | Founder's instruction (L3907). The protocol's remote form is unfinished (L3950). | Decided. Not designed. | L3907, L3916, L3950 | "ACP" is not defined in the log. |

**Changes of direction the log records:**

- Founder's words were first recorded as his decisions (L1971–L2002). They were then relabelled "Position" (L2002). They were then relabelled "Decided by the maintainer" (L2232). The founder asked for decisions (L2308).
- Credentials: the founder said "lets use credentials" (L2156), then questioned the proposal (L2219). The log agent decided no credential (L2236).
- Subscription feed: removed in the record (L3352), then kept (L3398).
- Inbox: named "inbox" by the log agent (L3321), renamed "handoff" by the founder (L3305).
- Role CQU: named "Cestui Que Use" (L2958), then "Vested Beneficiary" by the log agent (L3025).

**Rejected alternatives the log records:**

- A per-connection memory of what `goto` already sent (rejected, decision 1).
- A credential on every request for local use (rejected, decision 4).
- A second store in SQLite beside LadybugDB (rejected, decision 5).
- A special `childMap` property for linked maps (to be removed, decision 7).
- One database for a whole home (closed, L1561).
- Converting old maps or old SQLite data (rejected, decision 29).

## 5. Memory records and memory requests

**Confirmed as saved or edited**

| Memory | Substance | Evidence |
|---|---|---|
| `subagent-model-rubric.md` in `/home/rich/.claude/projects/-home-rich-metaform/memory/` | Rules for choosing a subagent's model. Always set the model. Delegation rules. Evidence from the day. | Written with the Write tool. Output: "Wrote 39 lines" (L805–L806). Later extended with a script (L1016–L1029). The script printed no error, but the file was not read back. |
| `MEMORY.md` index line for the rubric | Points to the rubric file. | Appended (L857). Printed tail confirms (L858–L860). |
| `communicating-clearly.md` | The guidance on messages to the founder, kept as given. | Written by a script (L1030–L1047). The index line was appended and printed (L1048–L1054). The file body was not read back. Likely saved. |

**Existing memories the log lists but does not show (not created here):**

- `ask-before-memory`: full text shown at L778–L791. It says to propose before writing a memory and to wait for approval.
- `write-our-own-code` and `procedure-text-is-a-formula`: index lines shown (L858–L859).
- Others listed by name only (L792–L802): `answer-own-questions-no-quotes`, `carry-owners-intent`, `one-pattern-no-deviations`, `owner-files-reference`, `saving-is-reasoning-cost`, `spec-is-kept-current`, `verify-boat-sandbox-ownership`.

**Requested, intended, or unconfirmed (no approval shown)**

- Two memories proposed at L2301–L2303. One says not to record the founder's words as his decisions without reasoning. The other says the maintainer decides the codebase design. The founder's reply at L2308 is not an approval. Status: **requested, unconfirmed**.
- A Haiku note proposed at L626 ("Run subagents on Haiku to save Fable usage..."). The rubric replaced it. Status: **superseded**.
- The subagent rubric was written at L805 without a prior proposal. The ask-before-memory rule (L787–L791) required one. The log agent says it took the founder's message at L774 as approval (L864). The founder's L1009 ("you can also create this memory") has an unclear referent. Status: **Uncertain**.

Note: `dev/HANDOFF.md` is a repository file, not a memory. It was committed in `943ac06` (L3769). It was edited again after the commit (L3931–L3942), and that edit is not committed.

## 6. Project context and conventions

**Goal.** Metaform keeps a map of a project, so agents need less reasoning and less context. The log agent calls this "the reasoning cost, which is the purpose of Metaform" (L1652). **Explicitly stated** by the founder: "a shared understanding of the other system" leads to better communication (L1681, L1738). **Inferred:** the map must stay small enough to read first.

**Architecture (Rust form).** Items marked "confirmed" appear in test output or command results.

- Cargo workspace `metaform/rust` with four crates: `metaform-core`, `metaform-store`, `metaform-server`, `metaform-web` (L41). **Confirmed.**
- One server process per home folder. It is the only writer. Agent processes send commands to it over a socket (L1408). **Confirmed by the log agent's reading of code.** Decision 39 would replace the socket.
- Engine: LadybugDB 0.22.3 (L1473). The registry is `metaform.lbug`. Each project has `projects/<id>/project.lbug`. Maps that belong to no project are in `maps/maps.lbug` (L1415–L1419). **Explicitly stated** (handoff text).
- One writer thread per database. One command is one transaction. The answer comes after the commit (L1428). A read is served from memory (L1428, L1807).
- The store limits open databases to 16 (L1812). Each open database holds about 32 MB (L1805). **Explicitly stated** in project notes. Not checked.
- The MCP surface is one tool, `project-map`, plus resources (L1820, L664). **Explicitly stated.** Published definition is 656 bytes (L1820).
- Commands: `add`, `update`, `delete`, `orphaned`, `goto`, `map`, `help`. A key that starts with a period is a raw dump. Other keys are addressed reads (L2455, L911).
- Roots after `943ac06`: `code`, `document`, `media`, `data`, `upstream`, `downstream`, `layer` (L3733).
- Roles (full names): Artifact Type (AT), Defining Element (DE), Supporting Element (SE), Coupled Element (CE), Notable Element (NE), Vested Beneficiary (CQU, formerly Cestui Que Use), Upstream Dependency (UD), Downstream Dependant (DD) (L3664–L3666, L3466).
- A want has `element`, `why`, `how`, `direction` (`send`, `receive`, or `both`), and `ref`. Its key is its element plus its `ref` (L1126–L1128).
- `refs` are paths relative to the project folder (L1129).
- The intake procedure lives in `metaform/intake/procedure/`, one file per section, plus `sections.md`. The tool serves it through help and resources. `build.rs` compiles it in (L1137–L1139).

**Documents.**

- `archive/metaform-2026-11-15/SPECIFICATION.md`: about 24,500 words (L527, L1078). Sections 1–15 state design. Sections 16–19 are the exact reference. Section 13 holds the decisions. Section 14 lists disagreements.
- `metaform/SPEC.md`: repository record, with a block "Changes of 2026-11-15" (L2189–L2198).
- `dev/HANDOFF.md`: the repository handoff.
- `PROJECT_CONTEXT.md` in the archive: lists files and their origins (L1091).
- `TASTE.md`: the repository's prose standard. The founder has an uncommitted edit in it.

**Terminology.** Use the founder's words where he has given them.

| Term | Meaning in the log | Open question |
|---|---|---|
| map, element, address | Base map of elements at dotted addresses. | None. |
| layer / overlay | Knowledge laid over the map. Wants overlay is the default. | Root word `layer` versus the word `overlay` (section 8, item 11). |
| handoff overlay | Notes for the next agent at an element. | Founder chose the name (L3305). |
| goto sheet | What `goto` returns for an element. | None. |
| shape | `map` read: addresses and wanting pairs. | None. |
| stateless | The server keeps no memory for a connection or session. | Meaning depends on current MCP specification. |
| CQU, Cestui Que Use, Vested Beneficiary | The same role. | Final name (section 8, item 12). |
| plugin, module | Same thing, per the log. | Which word (section 8, item 16). |

**Commands and checks.**

- Tests: `cd metaform/rust && METAFORM_LAUNCHER= cargo test --offline --no-fail-fast`. Expected: 77 passed, 0 failed (L1122–L1123, L3720).
- Release build: `cargo build --release --offline -p metaform-server -p metaform-web` (L3768).
- Archive rebuild. The log agent's steps (L1109–L1117, L3863–L3864):
  1. Edit in the archive folder.
  2. Copy changed tool files into the archive, at the same paths.
  3. Rebuild `MANIFEST.sha256`.
  4. Rebuild the `.tar.gz` with fixed owner and sort options.
  5. Unpack in a scratch folder and check the manifest.
  6. Copy the archive and its checksum to `/mnt/c/`.
- Short test homes only. A socket path holds at most 107 bytes (L1282–L1283).

**Quality expectations (from the log).**

- Read the code yourself before stating what it does. Reports are not enough (L1247–L1248).
- Check a cheaper agent's findings against source before acting on them (L1250–L1251).
- Do not rewrite a decided rule to match the code (L1252, L956–L957).
- Treat procedure text as a formula (L1253–L1254).
- Keep plain English in code comments (L3458).

## 7. Work completed, current state, and known issues

**Verified completed (evidence in log)**

| Item | Evidence |
|---|---|
| Commit `943ac06` on `fable-climb`, pushed | Push output `1798c6e..943ac06 fable-climb -> fable-climb` (L3811–L3812). |
| Six changes: role renamed, `collection` removed, refs wording, no connection instruction, `goto` returns whole sheet, intake help text | Subagent report (L3551–L3653). Log agent's reviewed diff (L3654–L3706). |
| Test suite after the changes: 77 passed, 0 failed, exit 0 | Output at L3719–L3720. |
| Role refusal shows the new name | Output at L3721. |
| `collection` root refused | Output at L3733. |
| Non-list `refs` gets the new wording | Output at L3744. |
| Two `goto` calls return equal output | Output at L3755–L3756. |
| Intake help returns the new text | Output at L3757. |
| Release build rebuilt | "Finished release profile" (L3810). |
| Archive rebuilt, unpacked, and checked; copied to `/mnt/c/` | Each rebuild shows "OK" and "manifest-ok" (L3945–L3971). Last shown checksum `1fd423fd…` (L3968). |
| Specification sections 16–19 read against code by reviewers; differences corrected | Reviewer reports (L38–L80, L134–L165). The log agent says each difference was checked (L960–L1000). |
| SEP-2567 fetched | Fetch exit 0, 47,985 bytes (L227–L231). |

**Claimed, not shown in the log**

- A baseline run of 77 passed before any change (L3552).
- No test asserted the old connection instruction text (L3631).
- 223 quoted message fragments matched in code (L14).
- The subagent costs: about 420,000 tokens and about $0.50 per intake (L895, L1161).
- The 28–50 ms scan of 1,000,000 elements (L1805).
- A website run on the inbox pattern for about a year (L3305, founder's statement).

**Failures and known problems**

- One earlier run of the store's tests reported only 66 tests. Its log was not kept. The cause is **Unknown**. Twelve later runs passed (L7–L11, L1269–L1271).
- Before the role change, a test read `metaform/metaform-canonical.json` and failed (L5).
- Two check scripts fail: `metaform/tests/check_contract.py` and `metaform/tests/check_tool_input.py`. They failed before the session too (L1272).
- Build fault: decision 18. `FIELD_ELEMENT_COLLISION` removes a field of the element above (L1218, L2387).
- `delete` removes every want on an element (L1208).
- A home whose path is too long for a socket gives only "Connection closed" to the agent (L1210).
- A possible defect: an element stored before `refs` existed can lose its `refs` after a later write. Not run (L1222). Decision 29 says this path goes.
- The server announces every commit, including layer-only writes (L3299).
- The store keeps a `childMap` property that no command sets (L1656).
- `extra` on an element, `extra` on a want, and `data` on a layer record are each one JSON text column (L1567–L1577).
- The build finds a project by folder path (L1355).
- The build records no author of a write and keeps no earlier state of an element (L2112).
- The web interface is not started (L1211). The founder rejected earlier pages (L1232).
- The intake procedure has never been run on code (L1209).
- Node and Python forms still use SQLite and older terms. The conformance set is stale (L1207, L1230).

**Planned, not started** (log's build order, section 13.5 and handoff, with the HTTP step moved to the front, L4012):

1. Remove the old procedure text from the archive. Test a build with no sections (decision 32).
2. Add the `prompts` folder and the short instruction that names resources (decisions 31 and 33).
3. Durable project name, and the registry keyed by it (decision 3).
4. HTTP server on loopback with the token (decision 39). Check the MCP library first.
5. Paths with a project name, for reading. The ref to another map (decisions 2 and 7).
6. Layer structure in its definition, and a table for each layer (decisions 9–12).
7. Small changes: decisions 18, 20, 22, 24, 26, 27, 30, 34; the handoff overlay (decision 35).
8. Origin of a write, and earlier state of an element. Writing into another project comes after this.
9. Remove SQLite (decision 5). Remove `metaform call` (decision 15).
10. The new intake procedure, written by the founder, then a fresh intake of each project.

**Blockers.** No hard blocker appears in the log. The following wait on the founder: section 8 items 1–10, the glossary location, and the form of the project name.

**Uncommitted state at the end of the log**

- `dev/HANDOFF.md` changed after the commit (L3931–L3942).
- `TASTE.md`: the founder's edit, uncommitted (L3813).
- Untracked: `TASTE.md~`, `TASTE_Backup.md`, `archive/`, `dev/Fable_Climb.md~`, `dev/user_agent_interfaces.md~`, `metaform/intake/stripped/intake.v9.xml`, `rich/` (L3813–L3820). The log does not say what `intake.v9.xml` is.
- The archive is untracked. The founder has not said whether it goes into git (L1241).

## 8. Open questions, conflicts, and unresolved items

| # | Item | What conflicts or is missing | Evidence | What would resolve it |
|---|---|---|---|---|
| 1 | Which messages belonged to another agent or project | The founder says he was talking to the wrong agent (L4020). The log does not say which messages. The log agent asks the founder to say (L4031). | L4020–L4031 | The founder lists the items. Fable checks each decision against its own project. |
| 2 | Commit and push of `943ac06` | The subagent brief said the founder would commit (L3452). The log agent noted that the founder did not ask for a commit (L1238–L1239). The commit and push then happened. `CLAUDE.md` says to commit and push each feature commit (L2862–L2864, cut off). | L1238, L3452, L3812, L2862 | The founder confirms. Read the full `CLAUDE.md` sentence. |
| 3 | Protected schema and tool contract | `CLAUDE.md` protects the schema and tool contract unless the owner instructs directly (L2860, cut off). The six changes edited the schema and the contract text. The log shows no direct founder instruction for those edits. | L2860, L3463–L3474, L3606–L3650 | The founder confirms the rule and whether the edits fall under it. |
| 4 | Credential versus token | Founder: "lets use credentials" (L2156), then doubt (L2219). Decision 4: no credential in the tool. Decision 39: a token on every HTTP request. The log agent says a token is not a permission (L4002). | L2156, L2219, L2246, L3915, L4002 | The founder decides whether a token is in scope for local HTTP. |
| 5 | Layer records: database or own files | Founder's earlier decision: each layer in its own files (cited at L2432, L2544). Decision 8 keeps them in the database. No founder reply appears. | L2432, L2544, L2886 | The founder decides. |
| 6 | Which side wins when spec and code differ | Founder: spec "more up to date" (L902). Handoff cites the same rule (L1154). Founder: does not know which of three rules is stronger (L1327). Log agent later wrote "the code is what changes" (L2006). | L902, L1154, L1327, L2006 | The founder states the rule once. |
| 7 | Three rule-versus-build differences (decisions 16–18) | Earlier founder rules (R-5.1, R-5.24, and the remediation rule) differ from the build. The log agent first said neither side changes until decided (L1346). It later decided all three itself (L2385–L2388). | L911, L1327, L1346, L2385–L2388 | The founder decides. Until then, change neither side. |
| 8 | Whether `metaform call` leaves the command line | Log agent recommends removal (L750–L764). No founder reply. Tests depend on it (L762). Decision 15 records removal (L2384). | L762, L764, L2384 | The founder answers. |
| 9 | Whether `metaform specification import` stays | Decision 15 keeps it (L2329). The founder did not state a view. | L2329, L2384 | The founder answers. |
| 10 | Form of the durable project name | Options: `mashtrac`, `carverj/mashtrac`, or the `id` field (L1365). Current direction: default to the last segment of the folder path (L2342). | L1365, L1905, L2342 | The founder chooses. |
| 11 | Root word: `layer` or `overlay` | Founder says "overlay" often (L3305, L2620). He said the root is `layer` on 2026-11-12 (L1199). Decision 13 keeps `layer` as root and uses "overlay" for the knowledge. The specification still says "layer" (L3323). | L1199, L2620, L3316, L3379 | The founder states one word. |
| 12 | Role name "Vested Beneficiary" | The log agent chose it from the founder's sentence (L3025). The founder did not confirm it. His new glossary may name the role (L3043). | L3025, L3043, L3061 | Read the glossary. Use the founder's name. |
| 13 | Exact wording of the CQU definition | Founder's text: "...who isnt the user..." (L2954). Log agent's text: "isn't" (L2967, L3021). The log agent says it kept the wording exactly. | L2954, L2967, L3021 | Use the founder's text as given. |
| 14 | Required-reading phrase | Founder: "Must read these URI to perform intake properly" (L3067). Log agent: "Must read these URIs to perform the intake properly" (L3079, L3098, L3131). | L3067, L3079 | Use the founder's phrase. |
| 15 | New glossary | Founder says it "probably has that anyway" (L3043). The log agent has not seen it (L3058). Location is not given. | L3043–L3063 | The founder gives its location. Read it before writing any term. |
| 16 | "Plugin" or "module" | Founder says plugin (L3194). The specification says module (L3263). | L3194, L3263 | The founder picks. |
| 17 | "ACP" and the remote-support quote | "ACP" is never defined. The log agent calls it the protocol that connects an agent to its client (L3916), with no source. The quote at L3950 has no source in the log. | L3907, L3916, L3950 | The founder names the specification and its link. |
| 18 | HTTP library support | Decision 39 needs the MCP library to serve HTTP in the protocol's form. Not checked (L3915, L4004). | L3915, L4004 | Check the library in use. |
| 19 | Path with no project name | Open (L1904). Decision 2 says it means the agent's own project. The founder did not answer explicitly. | L1904, L2365 | The founder confirms. |
| 20 | `refs` on an element | Founder said refs "will not work" (2026-11-12, cited at L1194). He then voted for element refs (L2562) and limited them (L2626). Partly resolved. | L1194, L2562, L2626 | Confirm the limit with the founder. |
| 21 | Many wants on one element (photographs) | 37 photographs would give 37 wants on one element (L2689). Not decided. | L2689 | Founder and Fable decide. |
| 22 | Writing into another project's map | Decision 4 allows it. Writes into another project wait until origin and earlier state are kept (L2345). The founder has not confirmed the write rule. | L1911, L2345 | The founder confirms. |
| 23 | synthetictaxonomy.com | Named as evidence (L3305). Not visited. The log agent asks Fable to study it before designing the handoff overlay (L3375). Scope unknown. | L3305, L3375 | The founder says what it is and whether to read it. |
| 24 | Project nearly abandoned | Asked at L1828. No answer in the log. The founder said "this project" (L1779). | L1779, L1828 | The founder answers. |
| 25 | Memory approvals | Two memories proposed (L2301–L2303). No approval in the log. The rubric was written without a prior proposal (L805). | L805, L864, L2301 | The founder says yes or no. |
| 26 | Test failure cause | Unknown. The log was not kept. | L7–L11, L1269–L1271 | Re-run the suite and keep the log. |
| 27 | Subscription feed | Founder says the page's map already updates (L3387). Decision 34 keeps the feed and forbids telling agents to subscribe (L3398). | L3387, L3398 | The founder confirms. |
| 28 | "Usage nearly spent" line in the handoff | Appears in a diff (L1062–L1063). Unclear whether it remains. | L1057–L1065 | Read `dev/HANDOFF.md`. |
| 29 | Log time zone | Not stated. | — | Only matters if timing matters. |

## 9. Safe transfer guidance for Fable

Each step is a check to make before adopting anything from this handoff.

1. Confirm the repository exists at the path given. Check the branch `fable-climb` and the commits `1798c6e` and `943ac06` with `git log`. If they are absent, stop. The log may describe a different project.
2. Confirm the repository is the Metaform project you work on. Check for the Rust workspace at `metaform/rust` and four crates. Check `CLAUDE.md` in full.
3. Ask the founder which messages in the log apply to your project (L4020–L4031). Do not adopt a decision until he answers.
4. For each decision, read its reasoning in section 13 of the specification. Decide whether the reasoning holds in your context. Do not adopt it because the log calls it decided.
5. Treat each "Decided by the maintainer" item as the log agent's proposal until the founder confirms it.
6. Fetch the current MCP specification. Check the claim that MCP is stateless. The SEP-2567 page says it is historical and that the current specification governs (L283).
7. Check the LadybugDB version and the performance figures against your build. The log has no measurement comparing it with SQLite.
8. Run the test suite yourself. Expect 77 passed, and keep the full output. Check whether the two check scripts still fail.
9. Check the role name and the CQU wording against the founder's glossary, once you have it.
10. Read `CLAUDE.md` and `EXPECTATIONS.md` in full. Check the rules on commits and on protected files.
11. Resolve the conflicts in section 8, items 4, 5, 6, 7, and 11, before you change code that depends on them.
12. Before any commit or push, confirm with the founder that the action is allowed (section 8, item 2).
13. Check each memory file exists and says what section 5 describes. Do not assume a memory is approved.
14. Ask whether synthetictaxonomy.com is in scope before reading it (section 8, item 23).
15. Check any command, path, or refusal text against the tool's current output. Do not copy it from the log.
16. Write your own reasoning into each decision you record. Do not write "the founder said" as the reason.
17. Check `dev/HANDOFF.md` on disk. It changed after the commit, and some of its text is only visible in diffs.

## 10. Source index

Speaker key: Founder, Log agent, and Subagent report are defined in section 2. Timestamps appear where the log shows them.

| Claim or section | Location in the log |
|---|---|
| Log covers 2026-11-15, about 5:45–7:25 PM | L13 (05:45 PM), L4022 (07:25 PM) |
| Earlier failed run of store tests (66 tests) | L7–L11; L1269–L1271 |
| Founder: MCP is 100% stateless | L220 |
| SEP-2567 fetched and status "Final" | L227–L231; L281; L283 |
| MCP is for data; command line separate | L630; L668–L674 |
| Subagent model rubric | L774; L805–L829; L857–L860 |
| Founder's rule: write for a low-context reader | L1010–L1014 (origin uncertain) |
| Founder: do not record his words as decisions | L1969; L1971–L2002 |
| Founder: reasoning with every decision | L1969–L1970; L2205 |
| Founder: "make a decision" | L2308 |
| Founder: include me in decisions | L2475 |
| Founder: map lives locally | L2475; L2508 |
| Founder: LadybugDB as engine | L1462 |
| Founder: one database per project, or more | L1514; L1598 |
| Founder: two projects that depend on each other | L1681 |
| Founder: nested map is a ref; all maps at root; agents self-govern | L1832; L1911 |
| Founder: vote on refs | L2562; limit at L2626 |
| Founder: well-named fields, full role names | L2695 |
| Founder: CQU definition | L2954 |
| Founder: fresh intake; remove glossary | L2809 |
| Founder: new glossary | L3043 |
| Founder: reusable context and "Must read these URI" | L3067 |
| Founder: prompts as Markdown; no XML | L3194 |
| Founder: map is a command; handoff overlay; no broadcast | L3269; L3305 |
| Founder: agents report, not ask | L3387 |
| Founder: build the work now | L3447 |
| Founder: agents across projects | L3497 |
| Founder: local HTTP; remote-host ACP | L3907 |
| Founder's quote on remote support | L3950 |
| Founder: wrong agent | L4020 |
| Repository `CLAUDE.md` excerpts | L2857–L2866 |
| Archive folder and checksum routine | L531–L557; L1113–L1116 |
| Archive is untracked | L1075; L1241 |
| Commit and push `943ac06` | L3769–L3812 |
| Subagent brief (six changes; no commit) | L3449–L3496 |
| Subagent report and test log | L3551–L3653 |
| Test results after changes (77 passed) | L3709–L3720 |
| Tool checks after changes | L3721–L3757 |
| Repository state after commit | L3813–L3820 |
| Handoff edit after commit | L3931–L3942 |
| Decisions 1–40 in specification | L2310–L2415; L2422–L2555; L2566–L2593; L2632–L2652; L2657–L2670; L2686–L2733; L2795–L2840; L2885–L2937; L3316–L3340; L3352–L3420; L3500–L3517; L3914–L3924 |
| Decision 4 text (no permission, no credential) | L2236–L2246 |
| Decision 39 text (token) | L3915 |
| Decision 40 text | L3916 |
| Decision 15 text and the call question | L764; L2328–L2330; L2384 |
| Decision 16–18 text and conflict with R-5.1 | L911; L1327; L1346; L2385–L2388 |
| Memory listing | L792–L802 |
| `ask-before-memory` text | L778–L791 |
| Two memories proposed | L2301–L2303 |
| Test-count discrepancy in subagent report | L3552 (baseline claim); L3551 (subagent report) |
| Subagent log path differs from brief | L3552 versus L3455 |
