**Metaform MCP interface review — 29 September 2026**

The module-based design is the right foundation for a concise agent interface. It has a small first surface, a predictable invocation pattern, and command declarations shared with the CLI. It does not yet meet the goal of an interface an unfamiliar agent can use instinctively. The main problem is uneven disclosure: the first menu is small, but entering a module delivers a large argument reference while withholding the operational guidance that explains how to use it.

The subtype Operative Purpose defect discovered during this review has been fixed at Rich's request. The remaining design changes below are recommendations, not implemented changes.

The review used the current working checkout, version `2026.9.29.25`, including its existing local changes. Its procedural test used [Canonical_Intake.xml](/home/rich/metaform/specifications/Canonical_Intake.xml) through a real MCP client and stdio server, with a separate `METAFORM_HOME` under this repository. The Artifact Under Examination was the current MCP interface and its module implementation, not a whole-repository intake. The requested file was selected with `intake_file`; the served text matched it after undoing only the target substitution. The Canonical Intake was not edited.

The recorded intake followed the receiver–purpose–provider encounter relationships, recorded each object in its own call, read back the map, absorbed two internal mechanisms while preserving their purposes, and finished. It produced eight element records, five outer joins and two subtype joins. Eight stored elements does not mean eight independent graph roots: the absorbed elements remain identifiable records held inside their subtype joins. The post-fix replay made 52 tool calls, including four deliberate error probes. It also exercised file-reference lookup, task add/take/done, memory readback in another connection, narrowed menus, and errors. It started and stopped the isolated web GUI. These are functional observations; completing this run is not proof of an intuitively understandable interface or a definitive semantic grading of the intake.

[Before-fix traffic](/home/rich/metaform/docs/reviews/2026-09-29-mcp-interface-evidence/before-fix.json), [after-fix traffic](/home/rich/metaform/docs/reviews/2026-09-29-mcp-interface-evidence/traffic.json), [served intake](/home/rich/metaform/docs/reviews/2026-09-29-mcp-interface-evidence/served-intake.xml), and [proof readback](/home/rich/metaform/docs/reviews/2026-09-29-mcp-interface-evidence/intake-proof.json) preserve the evidence. The replay script is [capture.py](/home/rich/metaform/.tmp/mcp-interface-review/capture.py). Its calls are scripted, and this reviewer had read the implementation; this is not a measured fresh-agent success-rate experiment.

A separate agent received only the initial pre-intake instructions, tool definitions, module menus and served Canonical Intake. It did not read implementation code or subsequent call results. Its qualitative walkthrough found the wrapper, empty-call discovery, receiver/provider fields and absorption argument direction understandable. It found task handoff and the distinction between retained records and graph roots insufficiently explicit. Those observations support the specific findings below; the walkthrough did not execute another live intake.

The observed first surface contained five tools and 68 commands beneath them. The complete tool definitions serialized to 3,794 bytes of compact JSON. The actual returned menu text measured:

| Tool entered | Commands | Menu bytes after the purpose fix |
|---|---:|---:|
| `map` | 34 | 29,979 |
| `intake` | 11 | 14,124 |
| `memory` | 9 | 5,570 |
| `web` | 2 | 928 |
| `metaform` | 12 | 8,152 |

These are bytes, not token counts. The measurements exclude protocol framing. The `map` menu alone is almost the length of the served Canonical Intake, 31,046 bytes. Opening a menu and receiving task instructions serve different purposes; making those payloads nearly the same size is a substantial orientation cost.

**What already serves the purpose well**

`intake`, `map`, `memory` and `web` communicate recognizable areas of responsibility. Opening a tool with an empty call and executing it with `command` and `arguments` is a learnable pattern. The Canonical Intake arrives on demand rather than being charged to every connection. Tool availability follows the folder's module surface. In the narrowed-memory session only `memory` and `metaform` were available. Initialization instructions were short in all observed states: 741 characters unregistered, 1,003 before intake, 817 while recording, and 1,248 after finishing. The one-read `where` result is especially useful once an address is known: it carries the part's relationships, open work and knowledge together. The intake's tolerant recording and notices allow the reasoning to continue without introducing content acceptance gates.

**1. The top menu still contains the entire command list twice.**

Each tool description enumerates its commands, and its schema repeats the same names in the `command` enum. Adding a command therefore increases what every connecting agent receives. The tool count remains small, but the first surface still grows with command count. This weakens the names-only top-menu intent in CLI-037. See [entry_schema](/home/rich/metaform/src/metaform/modules/mcp/server.py:383) and [entry_description](/home/rich/metaform/src/metaform/modules/mcp/server.py:389).

The ideal first surface identifies each module by name, gives its short purpose, and explains how to enter it. Command discovery belongs inside the module. This preserves the current one-tool-per-module organization and its context savings as modules gain capabilities.

**2. Module entry discloses too much detail at once.**

An agent entering `map` to find `where` receives 34 complete schemas, including layer construction, corrections, messages, history and work management. There is no command-specific help request over MCP; attempting `map` with `command: "help"` returns an error and sends the agent back to the entire menu. See [enter](/home/rich/metaform/src/metaform/modules/mcp/server.py:419).

The ideal is two levels within the existing tool: a short menu of named actions and summaries, then the exact contract of the chosen command on request. Normal execution should remain direct when the agent already knows the command. A help request should explain a command without running it. This is a disclosure improvement, not a requirement to force agents through extra calls before every action.

**3. The MCP reference omits guidance already authored for the same commands.**

Module `purpose` and `details`, command `details`, and examples are absent from the returned menu. Only summaries and argument schemas survive. Intake's declaration explains the recording lifecycle and when ordinary reads start seeing the result. Map's declaration explains how to enter the map and build a layer. The `ask` command's details explain where the user answers and how the agent retrieves the answer. An MCP agent cannot request those explanations through the tool. See [menu construction](/home/rich/metaform/src/metaform/modules/mcp/server.py:369), [intake guidance](/home/rich/metaform/src/metaform/modules/intake/__init__.py:625), and [map guidance](/home/rich/metaform/src/metaform/modules/map/__init__.py:577).

The ideal module entry includes a brief usage sequence, with command details and a working MCP example available for the selected action. Reuse the existing declaration as the source of meaning. Startup should remain short and state-aware; restoring the old module catalogue to initialization would undo MCP-029's design.

The fresh-agent walkthrough gives two concrete examples of the missing guidance. It could record work, but could not find a call that assigns it to a named worker. The current interface records and tracks work; the harness handoff must explicitly give the worker the relevant addresses and work id. Explain that route in module help rather than suggesting an assignment operation the tool does not provide. It also could not reconcile the Canonical Intake's removal of absorbed subparts from the outer graph with `absorb` saying the element record remains. Help and readback should distinguish an independent outer-graph element from the retained identity inside a subtype join. The agent should not have to guess whether deleting that retained record is required.

**4. Map's entered menu lacks organization by the job being done.**

The flat list mixes orientation, focused reading, layers, knowledge production, task coordination, and correspondence with the user. Several nearby names require interpretation: `element` returns the functional element record, while `node` returns layer items; `layer` reads one layer, while `layers` lists layers; `reply` answers a user question, while `answer` answers a blind-spot challenge. The names are usable once understood, but the menu gives the agent no visible organization that helps it choose. See [map commands](/home/rich/metaform/src/metaform/modules/map/__init__.py:588).

The ideal entered menu groups existing commands by purpose: find/read a part; record and coordinate work; communicate with the user; build knowledge; choose what layers are visible; inspect history and metaforms. Mark `roots` and `where` as reading entry points and explain overlapping names in one sentence. This does not require splitting the module, renaming the whole API, or changing what agents are allowed to do.

**5. Finding a part from a file path requires an undocumented bridge.**

The initialization message says to read the part before changing it, but an agent commonly starts with a filename rather than a namespace address. `where` accepts an address. Sending `server.py` as its address returned success with no content. `citing` could find the matching path refs, but the results were join ids with `address: null`; the next step to recover the relevant receiver/provider address was not explained. `search` searches item values and is not a substitute for path lookup. See [where](/home/rich/metaform/src/metaform/modules/map/__init__.py:590) and [citing](/home/rich/metaform/src/metaform/data/reads.py:333).

The ideal entry guidance explicitly shows the path-to-address route: find refs using `citing` with `key: "path"`, identify the functional element or the endpoints of the returned join, then read the relevant address with `where`. Returned citations should make the corresponding functional location directly usable. A read that finds nothing should say that it found nothing and give the existing discovery step; an empty successful response is insufficiently self-documenting. Any file-lookup behavior must be described accurately rather than implying that `where` already accepts paths.

**6. The interface hides the context its defaults will use.**

Initialization describes the project state but does not name the current registered project, server folder, active metaform or effective layer selection. The `metaform` tool can store settings but has no command to read the effective settings/context. A worker cannot easily verify which defaults a call will use, especially when a server starts outside the expected folder or a call overrides `project`. See [compose](/home/rich/metaform/src/metaform/instructions.py:53) and [chassis menu](/home/rich/metaform/src/metaform/modules/mcp/server.py:374).

On the narrowed-memory surface, `metaform` still described itself as holding history and prompts, although its menu contained only settings, feedback and reports. Descriptions should reflect the commands actually available on that surface.

The ideal offers a small context read: current project, server folder, active metaform, layer selection, relevant state and next action. State-changing operations should report the resulting relevant state. This makes implicit defaults understandable; it need not add a mandatory verification step to the workflow.

**7. In-progress intake and changed project state are not fully reflected in guidance.**

A new connection during recording received neither the no-map intake message nor a resume message. Calling `intake status` separately did identify the recording layer and metaform. The module supplies that information in `Status.lines`, while the instruction composer reads only `Status.notice`. Additionally, server instructions are built when the server is constructed; finishing intake does not refresh the same connection's initialization text. A fresh connection received the finished-map guidance. See [intake status](/home/rich/metaform/src/metaform/modules/intake/__init__.py:560), [notice collection](/home/rich/metaform/src/metaform/instructions.py:39), and [Server construction](/home/rich/metaform/src/metaform/modules/mcp/server.py:482).

The ideal identifies the intake already being recorded and points to `show` and `start` for inspection/resumption. A state read or module entry should give current guidance throughout a long connection. Completion should name what is active and where to continue. The existing connection's original instructions should not be treated as the permanent account of current state.

**8. Operation-specific argument requirements are buried in a union of fields.**

`knowledge` has 44 argument properties and `required: []`. Execution nevertheless needs `op`, then different identifying fields for each operation. `work` similarly contains several different operations. Field descriptions partly explain their applicability, but the agent must reconstruct a contract by cross-reading them. The `work` summary mentions add/edit/done but omits take/plan/step despite those being central to task progress. See [knowledge fields](/home/rich/metaform/src/metaform/modules/map/__init__.py:403), [existing structural needs](/home/rich/metaform/src/metaform/modules/map/__init__.py:274), and [work command](/home/rich/metaform/src/metaform/modules/map/__init__.py:638).

The ideal lets the agent inspect one operation and see only the fields it reads, existing structural requirements, defaults and notices. For instance, `work/add` identifies the node and task; `work/take` uses the returned work id; `work/done` uses that id and resolution. This documents the current behavior. It should not make currently optional semantic fields mandatory or reject an answer that the current tolerant recorder preserves.

**9. Error recovery leaves MCP at the point the agent most needs guidance.**

Missing `where` arguments produced `Next: metaform map where --help`; missing knowledge operation produced `Next: metaform help map knowledge`; an unregistered folder required a CLI registration command. The MCP chassis has no help, project-list or registration command. An agent with shell access can bridge that gap, but a connected MCP interface is not self-contained when its own recovery instructions require another interface. The unconditional trouble-report instruction also leaves unclear whether a corrected argument call counts as the prohibited retry. See [errors and dispatch](/home/rich/metaform/src/metaform/modules/mcp/server.py:431) and [base instructions](/home/rich/metaform/src/metaform/instructions.py:17).

The ideal error gives the exact available MCP recovery invocation when one exists. If setup truly requires the shell, say so explicitly. Clarify the difference between correcting a described invocation and being unable to continue; preserve the intended trouble-report behavior. Error recovery should communicate the action, rather than requiring the agent to translate a CLI help path into a missing MCP command.

**10. Equivalent concepts change their public representation between recording paths.**

Intake subtype creation uses `into` and `namespace_address`; knowledge subtype creation uses `join` and `address`. Intake refs are `{key, value}` objects, while knowledge refs are `[key, value]` pairs. An agent moving from the canonical recording procedure to knowledge work has to translate the same concepts. Some differences are intentional, such as a generated result id versus a work record id, but these equivalent field shapes add avoidable effort. See [intake subtype fields](/home/rich/metaform/src/metaform/modules/intake/__init__.py:598) and [knowledge fields](/home/rich/metaform/src/metaform/modules/map/__init__.py:403).

The ideal uses consistent field names and shapes for the same concept across surfaces. Where compatibility preserves current names, command help should show the correspondence and accept equivalent representations without discarding authored meaning. Distinct kinds of ids should remain clearly identified.

**11. The advertised outer schema contradicts the intended accepted call forms.**

The dispatcher accepts arguments beside `command`, and the replay verified that behavior. The advertised outer schema permits only `command` and `arguments` with `additionalProperties: false`. A host that enforces that schema could reject a sibling argument before the server's accommodation runs. That host rejection is an inference, not something reproduced in this client. See [schema](/home/rich/metaform/src/metaform/modules/mcp/server.py:383) and [argument accommodation](/home/rich/metaform/src/metaform/modules/mcp/server.py:410).

The ideal advertised contract matches the accepted layouts. Retain the accommodation requested in CLI-037. The interface should not claim a call is invalid when its implementation intentionally knows how to use it.

**The concrete design the interface should aim for**

Keep one tool per module. At connection, show the short current-state message and the module names with their purposes. Upon module entry, show its usage sequence and a grouped menu of commands with one-line meanings. Upon asking about a command or one of its operations, show its relevant argument schema, defaults, effect and a working MCP invocation. Execution returns the meaningful result and any change of state; errors return the next available action in the same surface where possible.

For example, the entered `map` menu would make these routes apparent without loading every schema:

| Agent starts with | Route the menu should explain |
|---|---|
| No address | `roots`, then `where` on the relevant part |
| A namespace address | `where`; `full: true` when record ids are needed |
| A file path | `citing` for path refs, then the corresponding functional address |
| Something learned | `memory` / `add-observations` at the relevant node |
| Work to delegate | `work` / add; hand off the address and returned work id; worker takes and finishes that record |
| A user question | `ask` at its node; read the answer with `messages` |
| A knowledge layer to produce | `knowledge` / create, record objects, inspect, finish |
| A visibility change | Explain folder layer selection versus address select/mask versus hide |

The interface should make these routes understandable on demand. The Canonical Intake remains the authority for the intake operation's authored behavior; navigation help belongs around that operation, not appended as extra conditions inside its prompt.

The highest-value remaining design work is selective command help plus module usage guidance, then grouped menus and visible current context. These changes directly reduce the need to guess while retaining the architecture's existing context advantage.

**Subtype-purpose repair and verification**

Before the fix, `map` → `knowledge` → `add-subtype` returned success with `purpose: null` and `extra.purpose` containing the submitted Operative Purpose. A notice reported the relocation. This preserved the characters while losing their semantic placement. The Canonical Intake explicitly requires an internal subtype's own refined purpose; it is not interchangeable with arbitrary extra data.

The defect was in the module adapter: `purpose` was absent both from the operation's read-field set and from the arguments forwarded to `Store.add_subtype`. The store and intake path already supported the field. The repair adds it to those two places and updates the shared argument help and relevant README wording. It introduces no acceptance conditions, migrations or prompt changes. Previously stored records with a misplaced purpose are not automatically rewritten by this repair.

The existing CLI field-preservation regression now covers purpose as well as EF and verb. A new real-protocol MCP regression builds and finishes a knowledge layer, then reads the receiver with `where` and checks that the nested subtype's own purpose and encounter function survive in their semantic fields. Both regressions failed before the implementation change. The post-fix Canonical Intake replay also checks that knowledge subtype purpose is preserved and absent from `extra`.

Verification completed: 65 tests passed across the map and MCP module suites plus the existing intake tests for subtype purpose, the shipped Canonical Intake copy, and target-only substitution. Type checking of the modified map module passed with zero errors or warnings. `git diff --check` passed. Lint reported two existing issues outside the changed lines: implicit string concatenation in the map `ask` example and a list-index pattern in an existing work-progress test. Both are present in `HEAD`; neither was changed as part of this repair.
