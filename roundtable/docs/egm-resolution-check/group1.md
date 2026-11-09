# Check of group 1 resolutions against the owner's sources

Sources used: the owner's session decisions of 2026-11-07 ("session decision N" below), the owner entries in the map decisions ("map, owner"), `Roundtable_ACP_Integration_Design.md` ("ACP design"), the owner's evaluation specification ("evaluation spec"), and `docs/gate-burden.md`. Map entries marked `"by": "Claude"` are builder choices, and I name them as builder choices where they matter. `README.md` is cited only to show where a proposal leans on it.

One rule I applied throughout: when a proposal disagrees with an owner answer, I put it in **Against the owner**, not in **Already answered**. That way every disagreement appears in the list at the end. **Already answered** rows all agree with the owner.

---

## collection.workspace.shared

Treats code as truth: partly. Most of its fixes rewrite the description to match the code. It also keeps the README as the element's source, which the owner rejected. But it limits code changes to cases where the code breaks a principle.
Compares options: partly. For the workspace failure it offers a notice or a startup error, but it does not explain why the chosen one is best for the project.

| # | Proposed change (short, plain words) | Group | Owner source and quote, or reason |
|---|---|---|---|
| 1 | Code: when the workspace folder cannot be created or resolved at table start, publish an error notice before building the permission policy. This addresses the finding that the creation failure is silently ignored. | No owner source | This is a real code bug fix. The resolution cites "Failures are loud (O)" from a comment in `engine.rs`. I did not find those words in any owner source I was given, so I cannot confirm that they are the owner's. |
| 2 | Code, from the final refinement: stop the table at startup on that failure, launch no seats, and send a table-ended event. | No owner source | This is a real code bug fix, but it adds a stop condition, so the owner should decide. It is a startup check, not an inference gate, so Gate Burden does not apply ("This only relates to inference"). The owner's rule "This roundtable must do everything it can not to get stuck" concerns a running table. I am unsure whether he would accept a stop at startup. |
| 3 | Description: say that the folder is created at start on a best-effort basis. | No owner source | Wording fix to the description. |
| 4 | Description: say that write access depends on the permission scope (the workspace by default, but configurable) and on the harness sending its permission requests to Roundtable. If it does not, the result is only a warning. This addresses the finding that write access is not unconditional. | Already answered | Map, owner + Claude, permission requests: "Auto inside workspace, or auto across project. This roundtable must do everything it can not to get stuck." The proposal agrees. The map decision's own residual risk already records the routing limit. Note: the decision text sets the scope to "the project root that contains the shared workspace", but the code defaults to the workspace. Both fit the owner's words, so the description should not present the code default as the decision. |
| 5 | Description: reword the "supplies cwd on session/new" want so it also covers resumed seats (session/resume, or session/load on version 1). This addresses the finding that resumed seats use a different call. | Consistent | ACP design section 4 table: `session/resume` is used to "Rejoin a session with its context rather than replacing it at topic changes". |
| 6 | Description: say that the engine does not isolate folders, that a relative path resolves against the server's working directory, and that two tables can share a folder. | No owner source | Wording fix to the description. |
| 7 | Description: add `config.rs` and `engine.rs` to the references. This addresses the finding that the uri names only a README anchor. | No owner source | Wording fix to the map. |
| 8 | Map: keep the README anchor as the uri "for the prose", and add README.md to the element's source and references (cross-cutting recommendation 2). | Against the owner | Leans on the disputed README. Session decision 19: README.md "that was never my spec." The session note says the README's standing is still open, so this is the mildest kind of disagreement. Even so, the proposal should not make the README a cited authority. |
| 9 | Description: say that tool (file) work during a turn counts as topic input and can postpone the end of a table with no round limit. | Already answered | Map, owner, 2026-11-07: "unlimited must have some kind of end though like no more good input or all agents state done.." The proposal agrees, because file work is counted as input. Session decision 9 also says a 10-round table needs no such ending: "we have a bound so that thats fine". |
| 10 | Description: note the warning raised after two topics in a row with no accepted message and no work. | Consistent | Session decision 11: "we can keep topics in the code just not by default". The description should add that this applies only when topics are switched on, and they are off by default. |
| 11 | Description: carry the concurrent-edits gap from the investigations into the gaps list, and say that the code has no locking. | No owner source | Wording fix to the description. |
| 12 | Description: say who creates the folder, how its path is chosen, and that an existing folder is reused. This addresses the finding that these facts are missing. | No owner source | Wording fix to the description. |
| 13 | Description: explain the convention that extra detail goes in agent-named files, link the prompt line, and define or link the "owner's evaluation specification". | Consistent | Evaluation spec section 9: "Tell agents they may put sample code, diagrams, and extended details in a file with their agent name in the filename." One caution: the evaluation spec is a separate owner document (Version 1.0, 7 November 2026). The description should link it, not define it as "that prompt/thresholds". |
| 14 | Description: define "chair", and say that the manager receives the produced files from the workspace, not a transcript. | Consistent | ACP design section 1: "the shared workspace contains developing work products. A coherent transcript or summary is not a substitute for the requested result." |
| 15 | Description: drop or footnote "Roundtable 7 proposals", and state that nothing coordinates concurrent edits. | No owner source | Wording fix to the description. |
| 16 | Description: add one sentence linking the file convention to the owner's acceptance that files are not judged, while the judged message must still state its point. | Already answered | Evaluation spec section 4: "Artifact contents are not implicitly available to the evaluator. Agents can cite files, but the message must communicate the argument's substantive basis." The proposal agrees. |
| 17 | Map: define ACP and JEV in a map-wide glossary, and remove the word session/new instead of defining it. | No owner source | Wording fix to the map. |

---

## downstream.chair

Treats code as truth: partly. It describes the web page as built. But it defers to the owner's later account of an interactive chair (its decision 7), and it refuses to switch topics on or remove limits just to match the old prose (its decision 2).
Compares options: partly. A few decisions weigh alternatives (End behavior, the 512 placeholder), but most do not explain why the choice is best.

| # | Proposed change (short, plain words) | Group | Owner source and quote, or reason |
|---|---|---|---|
| 1 | Code: show each judged contribution's evaluation scores in the chair's page, and record the gap until this is done. | No owner source | User interface feature. It supports the owner's aim that he can read the table ("the intent is for me to be able to interact with them"), but no owner text asks for scores on the page. |
| 2 | Description: replace "until the work is produced" with a run that has optional judging and topics within configured limits, and document the 10-round and topics-off defaults. | Already answered | Session decision 8, "make it by default 10 rounds", and session decision 11, "default is no topics its just the sent in prompt". The proposal agrees. |
| 3 | Description: document the reported rule that a table stops after two unproductive rounds, once it is checked against the engine. | Already answered | Session decision 9: "we have a bound so that thats fine". Session decision 10: "unlimited must have some kind of end though like no more good input or all agents state done." The proposal agrees only if the description limits this rule to unlimited mode. It does not say so yet. |
| 4 | Description and page: explain that the first End starts the closing rating round, and that a second End stops at once. Label the button "Stop now" during closing. | Already answered | Map, owner, 2026-11-06: "what about agent ratings at the end and saving the agents rating". The proposal agrees. A stop at the chair's request fits ACP design section 4: `session/cancel` is "Explicit cooperative cancellation **when requested**". |
| 5 | Description: add the chair features that are already built: explicit or proposed next topic, judging switch, OpenRouter settings, replay of stored tables, received prompts, and identity resume. | Consistent | Map, owner, JEV is optional: "You can surface a setting to the user in the GUI, but JEV is an optional thing." |
| 6 | Description: document the startup link, the chair token, and the address checks. | No owner source | Wording fix to the description. |
| 7 | Code: remove the unused `d.truncated` property from the page. | Already answered | Session decision 7: "we arent going to be truncating if we add limits in we will block messages for being too long". The proposal agrees. |
| 8 | Keep the page's temporary 512 value and reject the claim that new tables are limited to 512, because the opened event replaces it. | Already answered | Session decision 7: no length limit by default. The proposal agrees. |
| 9 | Description: say that Hold pauses new turns while running work continues. | Already answered | Map, owner, 2026-11-05: "We will be developing an interface where the user can hold the roundtable, to give them time to walk away and return". Session decision 14: "if you start an agent on a task it typically runs until completion." The proposal agrees. |
| 10 | Map: put confirmed mismatches in the gaps list, but do not list every review comment as a gap. | No owner source | Rule for maintaining the map. |
| 11 | Map: date the old "observation-only chair" decision and say that the current chair can interact. | Already answered | Map, owner: "or to say their part and give guidance." Session decision 18: "the intent is for me to be able to interact with them". The proposal agrees. |
| 12 | Description: explain that the address is `downstream.chair` and the alias is `user`. Link the meaning of CQU and the Intake 3.1 rule, or remove the claim that `user` is invalid. | No owner source | Wording fix to the description. Caution: CQU is a term from the owner's authored intake method. Removing the Intake 3.1 claim should therefore go to the owner, not be done on the grounds that no copy was supplied. |
| 13 | Description: add that the chair enters the objective and workspace and selects the seats, harnesses, and models. | Consistent | ACP design section 6 diagram: "U->>R: Objective and selected participants". |
| 14 | Description: say that guidance goes to every participant at its next turn, and check in the engine whether it skips JEV. | Consistent | Map, owner: "or to say their part and give guidance." Not judging the guidance is a builder choice (map, Claude, "chair guidance"), and the proposal correctly asks for it to be checked rather than asserted. |
| 15 | Description: add access instructions and a short glossary (table, rejection, JEV). | No owner source | Wording fix to the description. |
| 16 | Description: say that ending a run is not the same as accepting the deliverable, and add no automatic completion check. | Consistent | ACP design section 1: "A coherent transcript or summary is not a substitute for the requested result." |

---

## upstream.gateway.llm

Treats code as truth: partly. It documents the JEV route from the code and does not check it against the evaluation spec's endpoint. But it refuses to change the adapter code to match the old wording.
Compares options: partly. For the two model-list readers it names the requirement that would justify aligning them, but it does not choose between the options.

| # | Proposed change (short, plain words) | Group | Owner source and quote, or reason |
|---|---|---|---|
| 1 | Description (merge addendum): record that a missing key turns off JEV's veto and the table continues (fail open). | Already answered | Map, owner, 2026-11-05: "If JEV is down this doesn't halt, it continues." The proposal agrees. |
| 2 | Description: the adapter's inference uses the OpenRouter Responses API, not "chat completions". Do not change the code. | Consistent | ACP design section 7.3, path 2: "use OpenRouter's existing `@openrouter/agent` agent loop ... but expose it through an ACP-compatible agent adapter." |
| 3 | Description: add the openrouter-acp integration to what is built. | Consistent | ACP design section 7.3, path 2 (same quote). |
| 4 | Description: describe the two model-list readers and their different behavior, with no code change. | Consistent | ACP design section 7.3: "Use the model identifiers returned by this API to present and select OpenRouter participants." |
| 5 | Description: document JEV's route (`openrouter.ai/api/alpha/decisions`), the model `~typesafe/jev-latest`, the request body, and the answer ranges. | Already answered | Session decision 3: the JEV model is "~typesafe/jev-latest". The proposal agrees on the model. I am unsure about the route. The evaluation spec section 11 says "POST the assembled request to `https://api.typesafe.ai/v1/systemone`", while the ACP design says "JEV through OpenRouter". The owner should say which route is current before the description fixes one. |
| 6 | Description: document the key requirements for each operation separately (catalog, adapter, JEV, and sharing a key with seats). | Consistent | ACP design section 7.3: "The OpenRouter key used for participant models and the key used to access JEV may use the same OpenRouter provider, but these are separate functional uses". |
| 7 | Map: add a want for JEV, and make OpenCode participant inference explicit. | Consistent | ACP design section 3 table: "Contribution and topic judgment, JEV through OpenRouter". |
| 8 | Description: add the prerequisites of account funding and service limits. Do not add retry or billing code on the evidence of run 1's errors. | No owner source | Wording fix to the description. |
| 9 | Description: add references for the Models, Responses and Decisions routes. | No owner source | Wording fix to the description. |
| 10 | Keep the adapter want, and reject the claim that the adapter is "rarely used". | No owner source | Wording decision with no owner text behind it. |

---

## upstream.tracer.agent

Treats code as truth: partly. Every layer is corrected to match the current wrapper. This includes narrowing what the ACP design says AgentSight should observe. It does name the work that keeping the larger requirement would need.
Compares options: partly. It says what supporting capability-based setup or child-process TLS would require, but it does not weigh which is best for the project.

| # | Proposed change (short, plain words) | Group | Owner source and quote, or reason |
|---|---|---|---|
| 1 | Description: replace "the monitor runs with what it can observe unprivileged" with "attachment fails, reports that capture is unavailable, and starts no capture session". This addresses the finding that the decision overstates what is observed without root. | Consistent | ACP design section 8: "Full eBPF/TLS activity tracing is Linux-dependent and requires the relevant kernel support and privileges." The sentence being replaced is a builder choice (map, Claude). |
| 2 | Description: remove the capability-only setup claim, and say that capture needs effective root and that the wrapper does not escalate. | No owner source | The owner has not said whether root-only capture is acceptable or whether capability-based setup is wanted. The capability statement being removed is a builder choice (map, Claude). The owner should decide. |
| 3 | Description: narrow the want to process-family activity plus HTTP metadata from the harness process only. Say that requests from child processes are outside coverage and that nothing classifies provider traffic. The same narrowing goes into the "consistent replacement account". | Against the owner | ACP design section 8: AgentSight "supplies evidence when a harness sends no ACP messages: process existence/activity, spawned tools, filesystem access, network operations, and observed model/provider traffic." This rewrites the design's requirement down to what the code covers. The shortfall should be recorded as a gap. The resolution does offer to add child-process TLS "if descendant provider visibility is mandatory". |
| 4 | Description: record the pinned `agentsight-capture` 1.0.35 dependency and its default-on feature, and verify the runtime prerequisites. | Consistent | ACP design section 8 names "its reusable Rust `agentsight-capture` components". |
| 5 | Description: add a configuration note (probe arguments, TLS binary path, HTTP parser without raw data). | No owner source | Wording fix to the description. |
| 6 | Description: make the decision and the gap say the same thing ("effective root required; capability-only and unprivileged modes unsupported"), and build no dummy monitor. | No owner source | Wording fix. It depends on row 2, which the owner should decide. |
| 7 | Description: align the investigation, keep the WSL2 kernel checks as dated evidence, and say that the wrapper does not fall back to `sudo -n`. | No owner source | Wording fix to the description. |
| 8 | Description: replace "one-time setup" with real deployment instructions, and say that the owner provisions privileges. | No owner source | Wording fix. "The owner provisions" repeats a builder choice (map, Claude: "Granting capabilities is a one-time setup step the owner chooses"). |
| 9 | Description: explain how provider activity is observed and the limits of that observation. | Consistent | ACP design section 8: "TLS tracing depends on the executable and its SSL implementation". |
| 10 | Description: document that capture works on Linux only, with its kernel and root needs, and keep the WSL2 check as dated local evidence. | Consistent | ACP design section 8 platform limits. Note that the design also says "On Windows and macOS, AgentSight can still use native session data and lighter process information". The description should present Linux-only capture as the current state, not as the design. |

---

## code.quota.character

Treats code as truth: partly. Most proposals change the code to match the description. But it chooses a fixed 1,024 recovery partly because "replacement of a larger base already behaves this way". It also reasons from the map description, not from the owner's newest decisions.
Compares options: yes. It compares a fixed recovery limit against the larger of the base and recovery, and it gives a reason. But the comparison ignores the owner's word "larger".

| # | Proposed change (short, plain words) | Group | Owner source and quote, or reason |
|---|---|---|---|
| 1 | Policy: after a busy skip, the next reply is limited to exactly 1,024 characters, even when the normal limit is none or above 1,024. Replace "one larger reply" with "one reply with the recovery limit". | Against the owner | Map, owner, 2026-11-07: "The credit system is gone; a busy skip earns one larger reply instead." The owner's statement there is "it doesnt matter 1024 is plenty". Session decision 7: no length limit by default. Evaluation spec section 3: "the larger allowance applies to one next reply". Under the default of no limit, this policy turns the reward for a skip into a new 1,024 limit. |
| 2 | Code: check recovery first, so that the 1,024 limit applies even when no normal limit is set. | Against the owner | Same sources as row 1. Session decision 7: "No length limit by default." |
| 3 | Code: tell the participant its effective limit in every turn and review prompt, including the counting unit, what happens if it goes over, and when it returns to unlimited. Compute the limit once and use it for the prompt, enforcement and the event. This covers two review findings: that the participant is never told its allowance, and that the delivered prompt has no limit line. | Against the owner | Session decision 6: no "You have N Characters to Respond" line. Map, owner: "I prefer not to have the message that reads \"You have 512 characters to reply.. I dont like that popping up". It also adds text to the owner's prompts, which session decision 22 reserves to the owner. |
| 4 | Map: mark the old allowance-bank decisions (veto, accepted contribution, topics, characters) as superseded, and keep the Unicode counting unit as a current statement. | Already answered | Map, owner, 2026-11-07: "it doesnt matter 1024 is plenty and yes remove the credits messsage" and "we arent going to be truncating if we add limits in we will block messages for being too long". The proposal agrees. |
| 5 | Description and comments: limit the no-cutting guarantee to discussion messages, record that the length block happens before JEV, and fix the stale "truncate, then judge" comments. | Already answered | Session decision 7 (same quote). The proposal agrees. |
| 6 | Keep cutting topic proposals to 512 characters, as a separate rule. | Against the owner | Session decision 7: "we arent going to be truncating if we add limits in we will block messages for being too long". I am unsure, because the owner said this about discussion messages. Topics are off by default, and the owner said "we need to refine that a bit". The owner should decide whether proposals are exempt. |
| 7 | Starting tool work inside an issued prompt does not earn recovery. Only a skipped scheduled turn does. | Consistent | Evaluation spec section 8: "When a participant is busy at its scheduled turn, mark that slot skipped ... Assign 1,024 characters to the next reply requested after that catch-up." |
| 8 | A pending recovery is used by the next discussion prompt, including a review prompt. | Consistent | Evaluation spec section 3: "the larger allowance applies to one next reply issued after catch-up, then returns to normal. Multiple skips accumulate missed messages but do not multiply the allowance." |
| 9 | Code and description: remove the unused `DEFAULT_BASE = 512` constant, keep unlimited as the default, and require any set limit to be at least 1. | Already answered | Session decision 7: no length limit by default. The proposal agrees. |
| 10 | Description: length is the count of Unicode characters after outer whitespace is trimmed. Discussion messages are never shortened at a grapheme boundary. | Consistent | Evaluation spec section 3: "count Unicode code points in the message body, including spaces and line breaks." One small difference: the code trims outer whitespace before counting. The owner may want to know this. |
| 11 | Description: record how a length block works: it fails before JEV and also applies when judging is off, its notice is queued for the next prompt, and it does not restore recovery. | Consistent | Session decision 7 (block, never truncate). Evaluation spec section 8 order: "Deliver its pending rejection notice ... then other agents' accepted messages". The resolution correctly leaves the notice wording to the owner. |
| 12 | Description: the chair sets both limits when creating the table, and there is no live control to change them. | No owner source | Wording fix to the description. |
| 13 | Description: date the run-1 observation. Check the README sections, and label the stale ones as historical. | No owner source | Wording fix. Editing the README should go to the owner, because session decision 19 leaves its standing open ("that was never my spec"). |

---

## upstream.agent.coding

Treats code as truth: no. It keeps the requirements apart from what the launcher proves. It refuses to delete wants or to change code just to make lists match.
Compares options: partly. It weighs relabeling against replacing the version 1 URI, but most decisions do not compare options.

| # | Proposed change (short, plain words) | Group | Owner source and quote, or reason |
|---|---|---|---|
| 1 | Description: add an investigation entry for the openrouter-acp harness, to be verified. Do not add it to the launcher's built-in list. | Consistent | ACP design section 7.3, path 2 (OpenRouter Agent SDK behind an ACP adapter). |
| 2 | Description: record the pinned built-in commands and the exact rule for when they are used after the registry. Do not change the launcher. | Consistent | ACP design section 7.2: "These are **references to available mechanisms**, not a fixed hardcoded list for Roundtable." |
| 3 | Description: label the URI as the ACP version 1 reference, and present the version 2 runs as the author's report until there is evidence. | Consistent | ACP design section 4: "The current stable specification is **ACP v1**. **ACP v2 is a draft**". |
| 4 | Description: keep the RPC want as a requirement, separate from verified behavior, and attach traces when they are available. | Consistent | ACP design section 10, proof point 1: "the working trace shows a resolved ACP executable, `initialize`, `session/new`, `session/prompt`". |
| 5 | Description: replace the unexplained version 2 gap with a compatibility status for each harness by negotiated version. | Consistent | ACP design section 4: "The SDK and integration must follow the version negotiated by `initialize`". |
| 6 | Description: document the RPC names, versions and required capabilities. Fix the client only if it calls unsupported operations without checking. | Consistent | ACP design section 4 table: `session/set_config_option` is used "Where advertised", "Only when a harness actually offers a model config option". |
| 7 | Description: state Pi's status (a launch recipe exists, no recorded runs, compatibility unverified). | No owner source | Wording fix to the description. |
| 8 | Description: replace "checked by their source" with a dated audit reference. | No owner source | Wording fix to the description. |

---

## upstream.sdk.agent

Treats code as truth: partly. It rewrites the want to match the adapter and accepts the adapter's refusal of MCP servers as a limit that needs no change. Its addendum would demote the owner's design reference without having read it.
Compares options: partly. It explains why it keeps the patch and the version pins, but it rarely weighs alternatives.

| # | Proposed change (short, plain words) | Group | Owner source and quote, or reason |
|---|---|---|---|
| 1 | Description: the SDK supplies the agent loop and dispatches tools that the adapter defines. The adapter supplies conversation state in memory through the SDK's state interface, and there is no restore after close. | Consistent | ACP design section 7.3, path 2: "use OpenRouter's existing `@openrouter/agent` agent loop, tooling and conversational state, but expose it through an ACP-compatible agent adapter." Not restoring a session fits the design's `session/load` "Where `loadSession` advertised". |
| 2 | Description: record the private SDK patch and the startup failure it causes if the method is missing. Keep the patch. | No owner source | Records a real code dependency. |
| 3 | Description: record the exact SDK version pins, the injected fetch, and the disabled client retries. Do not restore retries. The addendum adds that the pins keep the patch valid. | Consistent | Map, owner: "This roundtable must do everything it can not to get stuck." Session decision 14 (no timeouts). Disabled retries make errors surface instead of hiding them behind a long backoff. |
| 4 | Description and `package.json`: say "eligible OpenRouter models that support tools on the Responses endpoint" instead of "any OpenRouter model". Record the stop-reason mapping. | Consistent | ACP design section 7.3: "One adapter can work with multiple OpenRouter model identifiers". |
| 5 | No change: keep "used only inside the OpenRouter adapter". | No owner source | Wording decision. |
| 6 | Reject adding "rarely used and superseded by OpenCode" (also the third addendum point). | No owner source | Nothing the owner wrote covers this. The owner should decide the adapter's status if it matters. |
| 7 | Description: name the four adapter tools and the path checks, and say that `run_command` runs a shell that the path checks do not confine. | Consistent | Map, owner + Claude, permission requests. The residual risk there: "it cannot confine what an allowed shell command does". |
| 8 | Treat the adapter's refusal of client-supplied MCP servers as an adapter limit that needs no change, and list it as "unsupported" in the suitability account. | Against the owner | Map, owner (participant tools): "We'll prompt who should use this, let the agents organize, and give them the feedback tool." ACP design section 4: `session/new` creates a participant session "with the **shared working directory** and optional MCP tools". If the adapter refuses MCP servers, OpenRouter seats cannot get the owner's advance and feedback tools. I am fairly but not fully sure: the owner has not spoken about this adapter specifically, so this should be recorded as a gap. |
| 9 | Map: add dependency metadata (packages, versions, TypeScript on Node.js). | No owner source | Wording fix to the map. |
| 10 | Description: add a suitability account and real integration limits to the gaps list. | No owner source | Wording fix (except the MCP framing in row 8). |
| 11 | Addendum: re-scope the reference to ACP design section 7.3 "so it is not read as a claim about SDK behavior", on the grounds that section 7.3 covers only the model option. | Against the owner | ACP design section 7.3 directly covers this element: "**OpenRouter Agent SDK + ACP adapter:** use OpenRouter's existing `@openrouter/agent` agent loop, tooling and conversational state". It also says "Use the model identifiers returned by this API to present and select", which is what the live catalog fetch does. The addendum had not read the design. |

---

## code.roster.participant

Treats code as truth: partly. It records the code's acceptance rules as the element's contract. The clearest case is the one-seat minimum, which it records without the owner's rule. Otherwise it avoids inventing requirements.
Compares options: partly. A few decisions explain what they reject and why, but there is no weighing of options for the project.

| # | Proposed change (short, plain words) | Group | Owner source and quote, or reason |
|---|---|---|---|
| 1 | Description: document the repository's OpenRouter adapter that is added to the harness list, its script path, and when it shows as unavailable. | Consistent | ACP design section 7.3, path 2, and section 9: "Select heterogeneous agents". |
| 2 | Description: document each harness's default environment and session settings, including permission routing and their order. | Consistent | Map, owner + Claude, permission requests: "Auto inside workspace, or auto across project." |
| 3 | Description: the model is a session option for any harness, and the catalog uses ids, not aliases. | Consistent | ACP design section 3: "Supported model selection and supported harness selection are **different dimensions**." |
| 4 | Description: document the resume session field and the OpenRouter key sharing field (off by default in the API, and how the page ticks it), and the filtering of secrets. | No owner source | Wording fix to the description. |
| 5 | Description: document the validation rules: command before harness, exact harness ids, name rules, case-insensitive duplicate names, and relative workspace paths. | No owner source | Wording fix to the description. |
| 6 | Description: document how the page sorts harnesses and which one it selects first. | No owner source | Wording fix to the description. |
| 7 | Description: the harness chooses the process, and the model is an optional setting for that process. Selecting a model does not switch the harness. | Consistent | ACP design section 7.3: "A model ID is **not** an ACP harness name; the selected runtime must execute it." |
| 8 | Description: define chair, seat and table. | No owner source | Wording fix to the description. |
| 9 | Description: at least one seat is required, with no upper limit. The two starting rows on the page are "a convenience, not a two-seat minimum". | Against the owner | Session decision 15: "If fewer than two agents are available, the loop halts or waits until at least two are available to debate. Agents must not sit passing back and forth." The proposal records the code's one-seat minimum as the rule. |
| 10 | Description: the seat rows do not choose the evaluator, and the chair switches judging on or off. | Consistent | Map, owner: "You can surface a setting to the user in the GUI, but JEV is an optional thing." |
| 11 | Description: the element covers roster selection plus server-side checks and handoff, and no package field is added. | No owner source | Wording fix to the description. |
| 12 | Reject the claim that the references are inconsistent, and optionally align the README references to its exact subsections. | Against the owner | Mild. It keeps the disputed README as a cited reference. Session decision 19: README.md "that was never my spec." Its refusal to discard the design reference is fine. |

---

## upstream.judge.llm

Treats code as truth: partly. It says several times that "the code is correct; the description is the stale artifact". This leads it to keep wording the owner replaced (topic sameness) and to call the token check correct, although it admits the check leaves out the request envelope.
Compares options: partly. Only the path-header decision compares two options with a reason.

| # | Proposed change (short, plain words) | Group | Owner source and quote, or reason |
|---|---|---|---|
| 1 | Description: rewrite the want. One request carries five questions (three gates and two scores). JEV returns one number each and no reasons. Roundtable builds the rejection text. Gates pass at 0.70 and scores at 3.0. | Already answered | Evaluation spec section 1: "Jev performs classification. The application performs thresholds, admission, feedback formatting ... No generated explanation from Jev is needed." Session decision 5: "three gates plus value and auditability scores at 3.0 or more, a feedback prefix with bands". The proposal agrees. It should describe the rejection text as the owner's prefix and bands, not as "{name} {value}" strings. |
| 2 | Description: the current specification has three yes/no gates at 0.70 and two 0–5 scores at 3.0. Note that the owner's 0.70 statement applies to the gates. | Already answered | Session decision 2: "A gate passes at 70%." Session decision 5 (scores at 3.0). The proposal agrees. |
| 3 | Description: add a contract layer that records the code's state fields (`topic`, `conversation`, `new_message`), the four-round history, the 32,000 and 64,000 limits, and the estimate of one token per 3 bytes, which leaves out the request envelope. It says "No code change — the code is correct". | Against the owner | Evaluation spec section 2: "Request budget: Full request must fit within 64k tokens". Evaluation spec section 4 names the state fields `roundtable_subject`, `discussion_transcript` and `new_message`, and the message record "Three fields with exact spelling: `ID`, `AgentName`, `Message`". The proposal records the code's differing names and a partial budget check as the contract, and calls the code correct. Recording the estimator and its uncertainty does fit section 10: "document the estimator and its uncertainty". |
| 4 | Description: document the failure paths (no key, oversized state, or a JEV error means the message is shared unjudged with a loud notice), that there is no timer, and that the gate is best-effort. | Already answered | Map, owner: "If JEV is down this doesn't halt, it continues." Session decision 14 (no timeouts). The proposal agrees. |
| 5 | No change to the topic-sameness want, which says JEV "judges whether two proposed topics express the same underlying intent". The resolution calls this "verified accurate". | Against the owner | Session decision 4: the question is "{{foo}} is the same as {{bar}}". "Same underlying intent" gave too much leeway and let agents smuggle decisions into topics. Map, owner: topics are off by default ("default is no topics its just the sent in prompt"). The want should be corrected, not kept. |
| 6 | Description: name the three gates (contribution, usefulness, relevance) and the two scores (value, auditability), and say five checks everywhere. | Already answered | Session decision 1 (the owner's three gate questions). Session decision 5 (the value and auditability scores). The proposal agrees. |
| 7 | Description: explain `~typesafe/jev-latest` against the older pinned snapshot, and name the decision route. | Already answered | Session decision 3: the JEV model is "~typesafe/jev-latest". The proposal agrees on the model. The route has the same uncertainty as upstream.gateway.llm row 5: the evaluation spec names `https://api.typesafe.ai/v1/systemone`. |
| 8 | Description: mark the price conflict ($0.042 against $0.42 per million tokens) as unresolved and verify it. | Consistent | ACP design section 1: "approximately $0.42 per million input tokens through OpenRouter. ... These are the specified operating characteristics, not separately verified current provider guarantees." |
| 9 | Description: explain that `noul` means a yes/no answer given as a probability, and note that the old `criteria:{true,false}` shape is no longer used. | Already answered | Evaluation spec section 5: "Noul is a probability, not a literal true/false JSON field." Session decision 1: "no TRUE/FALSE criteria". The proposal agrees. |
| 10 | Description: fix the header rule about relative paths, or mark the run-1 audit path as external. It recommends the latter. | No owner source | Wording fix to the description. |

---

## data.log.discussion

Treats code as truth: no. It keeps the goal of a complete audit and asks for code fixes, instead of making silent loss the accepted contract. It rewrites the description only where the record does not do what the description claims.
Compares options: partly. It compares documenting the stop at `roundtable.ended` against extending the record through shutdown, and a new turn counter against reusing the round counter. It gives a reason in each case.

| # | Proposed change (short, plain words) | Group | Owner source and quote, or reason |
|---|---|---|---|
| 1 | Description: the record is an append-only audit of bus events. It is not the source of live prompt context, and it is not the "source for all three" (distribution, deferred notices, continuity). Prompt capture is intended but not yet verified. | No owner source | Wording fix. "Source for all three" was a builder choice (map, Claude), not the owner's. |
| 2 | Code: add a table-wide turn number to every opportunity and its outcome events (contribution, pass, skip, failure). Topic changes do not reset it. The addendum proposes reusing the round counter instead. | Changes the foundation | It changes the event model by adding a new identity to all outcome events beside the message ID. The owner's message ID must stay as it is. Session decision 16: messages "keep the ID (\"[R1-2]\") so agents can reference messages." The owner should decide how the turn number relates to that ID. |
| 3 | Code: for any shortened text, emit the original length, retained length, unit and limit, and keep the original. (The proposal to document an over-limit block separately from shortening agrees with the owner.) | Against the owner | Session decision 7: "we arent going to be truncating if we add limits in we will block messages for being too long". This keeps the "truncation counts" builder decision (map, Claude) that the owner has since overruled. |
| 4 | Code: keep the recorder running through table shutdown, drain the remaining events, then signal the end. Make publishers carry a table identity, and do not assign unknown events to a table. | No owner source | Real code bug fix (events after `roundtable.ended` are lost). |
| 5 | Code: report append and serialization failures instead of dropping them, and mark the audit as incomplete. | No owner source | Real code bug fix. |
| 6 | Description: document the line format (seq, at_ms, event, data), the routing rules, and the file location once verified. This covers two review findings: the missing schema and the missing file location. | No owner source | Wording fix to the description. |
| 7 | Description: add a local glossary (table, seat, seat availability, topic, disposition, veto, JEV, truncation, canonical turn number). | No owner source | Wording fix. The "truncation" entry should follow session decision 7, which says messages are blocked and never cut. |
| 8 | Addendum: link veto and deferred feedback to README section 4.6 instead of defining them locally. | Against the owner | Leans on the disputed README. Session decision 19: README.md "that was never my spec." The evaluation spec section 8 is the owner's source for deferred feedback. |
| 9 | Description: replace the bare audit codes (E05, E06, D01–D05) with a link and a short statement, or mark them as unverified. | No owner source | Wording fix to the description. |
| 10 | Code: have the evaluator publish the actual JEV request and response, linked to the table, seat, turn and attempt. | Consistent | Evaluation spec section 10: "Record which history IDs were supplied and which were omitted for budget reasons in host evaluation metadata." Section 5: "Retain returned score distributions, legends, and confidence in the existing evaluation record when available." |
| 11 | Map: define or link `role`, `name_length` and `Intent` in the shared map schema. | No owner source | Wording fix to the map. |

---

## Summary list

### Against the owner

- collection.workspace.shared, row 8: keeps the README as the uri and adds it to the references (leans on the README; mild).
- upstream.tracer.agent, row 3: narrows the AgentSight want to harness-process TLS metadata, against the ACP design's "observed model/provider traffic" from spawned tools.
- code.quota.character, row 1: fixed 1,024 recovery even with no normal limit, which replaces the owner's "one larger reply".
- code.quota.character, row 2: code change that applies the 1,024 limit when no limit is set.
- code.quota.character, row 3: tells the participant its character limit in every prompt, against "No 'You have N Characters to Respond' line".
- code.quota.character, row 6: keeps 512-character cutting of topic proposals (unsure; the owner may exempt proposals).
- upstream.sdk.agent, row 8: accepts the adapter's refusal of MCP servers, so OpenRouter seats lack the owner's tools (fairly sure, not fully).
- upstream.sdk.agent, row 11: re-scopes the owner's ACP design section 7.3 reference, although that section describes this element.
- code.roster.participant, row 9: records a one-seat minimum, against "at least two are available to debate".
- code.roster.participant, row 12: keeps the README as a cited reference (mild).
- upstream.judge.llm, row 3: records the code's state field names and a partial 64k check as the correct contract, against the evaluation spec.
- upstream.judge.llm, row 5: keeps "same underlying intent" in the topic-sameness want, against "{{foo}} is the same as {{bar}}".
- data.log.discussion, row 3: keeps truncation counts, against "we arent going to be truncating".
- data.log.discussion, row 8: points to README section 4.6 for veto and deferred feedback (leans on the README).

### Changes the foundation

- data.log.discussion, row 2: adds a table-wide turn number to all outcome events, which changes the event model next to the owner's "[R1-2]" message ID.

### Open points for the owner raised during the check

- The JEV route: the evaluation spec names `https://api.typesafe.ai/v1/systemone`, the ACP design and the code use OpenRouter (upstream.gateway.llm row 5, upstream.judge.llm row 7).
- Whether a table may stop at startup when its workspace folder cannot be created (collection.workspace.shared row 2).
- Whether root-only AgentSight capture is acceptable (upstream.tracer.agent row 2).
