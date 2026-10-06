# Claude memory notes for Metaform, exported 2026-09-27

Source folder: /home/rich/.claude/projects/-home-rich-metaform/memory. One section per note file, unedited.

## Index

- [No invented flaws](no-invented-flaws.md) — assess by benefit and real cost; never manufacture objections or dress fixable details as design costs
- [Metaform intake specialist prompt](metaform-intake-specialist-prompt.md) — the 2026-09-09 intake rethink agent prompt and the intent behind it
- [Paraphrase rule](paraphrase-rule.md) — write my own clear interpretation of Rich's explanations, never his shorthand or typos; his prompt and Foundation text keeps his wording, corrected
- [Investigate then propose](investigate-then-propose.md) — findings and one grounded recommendation; no option menus, no unreasoned removals, never degrade what works; keep fan-out small
- [Workbench rebuild](workbench-rebuild.md) — front end rebuilt from docs/workbench-brief.md (explorer at /, earlier page at /legacy, Jobs tab drives intake); all five units pushed 2026-09-11; awaiting Rich's real intake run and palette pick
- [Nonce and menu design](nonce-and-menu-design.md) — Rich's design: since 2026-09-21 no begin and no folder binding, every agent command is `metaform <nonce> ...`, nonce keys the visible CLI menu, main menu only in the project root, chassis-wide help, first-run provisioning for unfamiliar harnesses
- [Dependency rule](dependency-rule.md) — third-party is fine when standard, non-proprietary or used in the AI space, with a safe license; use what Flask already brings (Jinja); confirm a mid-conversation constraint is a decision before removing anything
- [Coarse contract and workflow format](coarse-contract-and-workflow-format.md) — 2026-09-12 calls: seven-section prompt shape, contract v2 (elements by namespace + joins with combined), coarse.py expansion, no legacy fallbacks; XML workflow format and jsonschema bundle still to build
- [No gating on inference](no-gating-on-inference.md) — absolute: contracts describe and never reject, runtime makes the answer fit and records mismatches for observation, nothing is handed back to the agent; a gate needs a named silent failure
- [Rich stakes](rich-stakes.md) — who Rich is and what Metaform means to him; exactness, no gates, no cruft, honest judgment
- [No Q&A menus](no-qa-menus.md) — never use AskUserQuestion with Rich; ask in prose, one question, keep moving
- [Data folder design](data-folder-design.md) — specs/data_folder.md is the history, variants, reconstruction, import and service-port design (2026-09-13, not decided); read it before touching history, portable, workfolders or the service
- [Intake live per object](intake-live-per-object.md) — built 2026-09-26: intake recorded one object per call as reasoned, proofed in step 12, web GUI live by push; never a whole-document submit again
- [ChatGPT cleanup context](chatgpt-cleanup-context.md) — the five handoff steps undo ChatGPT-built mistakes; a state-of-things remark from Rich is context, not a new task list
- [Don't halt on inherited test failures](dont-halt-on-inherited-test-failures.md) — a failing inherited test is questioned in passing, never a reason to stop; commit units as you go
- [Session shell and fixed ports](session-shell-cannot-bind-fixed-ports.md) — since 2026-09-27 `metaform web stop` and `metaform web` from the Bash tool restart the GUI on 7433; try that before asking Rich
- [Project clear is a standing requirement](project-clear-is-a-standing-requirement.md) — Rich asks for clear-and-reintake every time; Clear project and project clear exist since 2026-09-13, never answer 'no way to clear'
- [Plan order is binding](plan-order-is-binding.md) — docs/plan.md fixes the unit order; one unit at a time, tests failing first from the spec, never rewrite tests to fit code; a session that merged unit 10 into unit 4 was killed 2026-09-13
- [Module definition](module-definition.md) — the chassis is fixed, everything that plugs in is a module, authored by us or anyone, as small as one command; all 25 built-in groups are modules; not a workflow (2026-09-14)
- [Read the spec, don't transcribe](read-the-spec-dont-transcribe.md) — the spec already defines the system; never write Rich's chat explanations into the spec or memory as definitions; read the section first
- [Answer design questions as design](answer-design-questions-as-design.md) — when Rich asks if something is possible he is designing; never answer with what the code implements
- [One vocabulary](one-vocabulary.md) — one set of terms, never "in your terms", renamed fields in code are defects; "semantic compiler" was abandoned only after my pushback, the name is his call
- [CalVer during development](calver-during-development.md) — Rich's decree, CalVer not SemVer while developing; lost from the repo, pyproject says 0.2.0, REQ-180 to 183 use SemVer terms; ask the format first
- [Module locations](module-locations.md) — four places, Wheel > Global Immutable > Global mutable > Project Local; same-name local module cannot enable; wheel data isolated, install front door and backstage (2026-09-19)
- [Read namespace by reversal](read-namespace-by-reversal.md) — reverse the segments and read the last name_length as a name before judging any address; `document.spec.metaform` is "metaform spec", a type
- [One metaform, two blind spot analyses](native-and-blind-spot-layer.md) — Rich 2026-09-26: one Inference Metaform; blind spot analysis is metaform-only or metaform plus code; never Native or Latent; intake by a stakeless fresh agent
- [Map functionality, not code](map-functionality-not-code.md) — his one sentence, a map of the functionality and not of the code; the exclusion list (tests, CI, earlier runtime) was my invention, never attribute it to him (2026-09-20)
- [Subagent models and cost](no-subagents-without-asking.md) — since 2026-09-27 evening usage is tight: builders and intakes on Opus, one at a time, small work done in the session; name the model on every agent
- [Intake result grading criteria](intake-result-grading-criteria.md) — graded by a run on this project: functionality based, smaller is better, thorough, speaks to the project and never to element types; my parallel intake is specifications/Fable_Intake.xml (2026-09-20)
- [Nodes are elements](nodes-are-elements.md) — every result node is tagged element; receiving entity is a perspective held in joins, never a node label; structure is strict, no added node fields (2026-09-20)
- [Run commands are timed, do them](run-commands-are-timed-do-them.md) — "run X on repo" means start now, no mechanism questions, no broad reading first; a timed test was ruined 2026-09-20
- [Do not match his design to repo code](dont-match-his-design-to-repo-code.md) — his explanation is the whole design; never bridge it to transform, similarity or other repo code that may be GPT additions (2026-09-20)
- [Metaform DE is the chassis](metaform-de-is-the-chassis.md) — Rich 2026-09-21: the DE is nearly the artifact, and for this repo it is the chassis; sample d had it right, I argued it wrong twice
- [Assignments stay in the chassis](assignments-not-chassis.md) — Rich 2026-09-21: came in from the old design without a decision but can stay; it is really module activation
- [Agent identity findings](agent-identity-findings.md) — tested 2026-09-21: Claude Code session ID is in every shell, subagents share it and the PID; only the nonce separates them
- [Repo docs are not his decisions](repo-docs-are-not-his-decisions.md) — plans, handoffs, REQUIREMENTS, SPEC are mostly agent-written; only his own words count as his decisions
- [CLI cleanup findings](cli-cleanup-findings.md) — 2026-09-21: main menu must be empty; 25 hardcoded chassis commands, flat module menu, folder files, JSON-only output, global switches, 14.9k lines of dead runtime
- [CLI exactly like mvm](cli-exactly-like-mvm.md) — Rich 2026-09-21: copy mvm's menu, help pages, set/unset/config exactly; every person-read string unslopped
- [Web editor request](web-editor-request.md) — his words: split screen, graph left half and collapsible, full screen, word-processor prompt editor with insertable objects for imported workflows
- [Cleanup progress 2026-09-21](cleanup-progress-2026-09-21.md) — commits 6d991b7, 09d9de0, 8e873f7, 9620fef; open questions and remaining steps
- [Intake sample runs are procedure tests](intake-sample-runs-are-procedure-tests.md) — "execute the intake on repo" means write the XML file and reply with the path only; no questions, no commentary (2026-09-21)
- [Chassis rebuild baseline 2026-09-23](chassis-rebuild-baseline-2026-09-23.md) — the 09-23 freeze is superseded by HANDOFF.md; metaform runs on this repo as the test artifact under ~/.metaform
- [Obvious fixes need no ask](obvious-fixes-need-no-ask.md) — an inconsistency or accidental regression with one clear fix is fixed and reported, not asked about (2026-09-25)
- [One user-global web GUI](one-user-global-web-gui.md) — Rich 2026-09-25: one unified web GUI per user, one fixed port, every project; modules add views; variants and MCP stay outside
- [CI spending limit](ci-spending-limit.md) — 2026-09-26 Actions stopped starting jobs, spending limit or payment; six jobs per push; push less often, ask before changing the matrix
- [Prototype is the visual baseline](prototype-is-the-visual-baseline.md) — the approved viewer prototype is the floor for the GUI look and join shape; unit 9 cut it for a 100k target, restored 2026-09-26
- [TRAO-DAG description](trao-dag-description.md) — Rich's own description of the system, 2026-09-26, the reference for deviations; Func/Enc state, annealing, prompt expansion, blind-spot delta
- [Descriptions follow operation](descriptions-follow-operation.md) — Rich 2026-09-26: describe Metaform with technical accuracy that follows its operation; my pushback and the flat spec wording damage the project
- [Intake ships with the release](intake-is-ip.md) — Rich 2026-09-26: "it has to be released with that"; never flag the intake as IP or leave it out; attribution is what he protects
- [MGM is employer code](mgm-is-employer-code.md) — MGM belongs to Rich's employer, 2026-09-26; never use it in demos, tests or anything public; only viewer-prototype.html holds its map
- [Tree direction words](tree-direction-words.md) — say toward the leaves or toward the trunk, never above, below, up, down or top for the namespace, Rich 2026-09-26
- [Work states on the map](work-states-on-the-map.md) — Rich's 09-26/27 design: node states, questions, voice rule, tasks and a work queue, for-each layers, item flags, past work, roots; full text in CAPTURE.md; not built
- [Docs presentation rules](docs-presentation-rules.md) — no ASCII graphs in README or docs; the structure shown strongly with Mermaid and GUI screenshots, Rich 2026-09-26
- [No polling, no blocking](no-polling-no-blocking.md) — Rich 2026-09-26, system wide: no polling unless shown there is no other way, no blocking; use the event bus and push
- [New capability updates template and helloworld](new-capability-updates-template-and-helloworld.md) — Rich 2026-09-26: a capability added for a feature updates the template module and module services and gets a helloworld demo
- [Address segments example](address-segments-example.md) — specifications/metaprompting_element_segments_example.md: an address alone prompts; prefixes run trunk to leaf; the leaf drives content; practices inherit toward the leaves only (Rich 2026-09-27: remember this)
- [Intake runs must be clean](intake-runs-must-be-clean.md) — verified 2026-09-27: a subagent intake inside the repo copies earlier map text and my context; run it on a clean copy outside the repo in a fresh process with the intake tools allowed
- [Handoff 2026-09-27](handoff-2026-09-27.md) — state after steps 33-40 (pushed 80694e5), metaforms main and clean-2026-09-27, the Fable intake Rich wants, pending intake-wording decisions, next work
- [Functional shape only, work records, blind spots](functional-shape-only-and-element-records.md) — Rich 09-27 night: map is the full intended shape, conditions and tasks in work records, TBD ghosts, names on joins, blind-spot review colors, corrections question; nothing built
- [Start intake before the agent](start-intake-before-agent.md) — run `metaform intake start model=<m>` myself before launching an intake agent so the GUI shows it; no watchers or polls on the run
- [Schema changes start fresh](schema-changes-start-fresh.md) — no migrating metaforms across schema versions; never read or parse a subagent transcript, it got flagged and forced a rollback
- [Relay tasks without added limits](relay-tasks-without-added-limits.md) — pass Rich's task to a subagent as he gave it; my "do not run an intake" turned a walk-through into a read-only review
- [Walk through, not inspect](walk-through-not-inspect.md) — to capture an approach, the agent performs the process and logs each step as it goes; reviewing the output does not show what was done
- [Decisions go into the spec](decisions-go-into-spec.md) — a decided point becomes a declarative spec record in the same session, and its Why states the reason, understood, in the system's terms, never "Rich said"; provenance only in Status

---

## File: address-segments-example.md

---
name: address-segments-example
description: "specifications/metaprompting_element_segments_example.md, which Rich said to remember 2026-09-27: an address alone is a prompting surface; prefixes run trunk to leaf; the leaf drives content; practices inherit toward the leaves only"
metadata:
  node_type: memory
  type: reference
  originSessionId: 61f77ef6-a53d-4c77-b3e1-89175e9daeed
  modified: 2026-09-27T04:13:49.926Z
---

`specifications/metaprompting_element_segments_example.md` (tracked; also cited in docs/inference-metaform/EXAMPLES_TO_COLLECT.md). Rich asked me to remember it, 2026-09-27.

What it shows, from its own text:
- Four lists made from nothing but addresses, one prompt each, "write 10 best practices for [address]", no repo, code or project description: "the address itself a prompting surface".
- `code.engine.game.fps` holds four complete types, `code`, `code.engine`, `code.engine.game`, `code.engine.game.fps`; run trunk to leaf they give a progression from general to specific.
- The segments are not equal: the trunk and branch keep the output in the right domain, "The leaf is where the inference comes from, and the rest of the address keeps it from drifting."
- "Inheritance runs one way": a parent's practice holds for its children, never the reverse. A practice generated at a parent can be attached once and inherited beneath it; "a practice that would still hold after its leaf segment is removed belongs higher in the tree, or in a sibling branch".
- The lists barely overlap; a repeat marks a parent's practice restated by the child.

**How to apply:** For the for-each knowledge layers of [[work-states-on-the-map]], a node's address is part of its prompt and orients it; the placement rule tells a layer-building agent where a practice belongs. Keep apart: a practice applies toward the leaves only, while the Foundation's property flow also reaches back to the trunk. See [[read-namespace-by-reversal]].


---

## File: agent-identity-findings.md

---
name: agent-identity-findings
description: "Tested 2026-09-21: Claude Code puts CLAUDE_CODE_SESSION_ID and CLAUDE_PID in every shell command; subagents share both with their parent, so only the nonce in context tells them apart"
metadata: 
  node_type: memory
  type: project
  originSessionId: f426c7c2-2934-4eed-9deb-b08b76ef3ec9
  modified: 2026-09-21T08:45:06.578Z
---

Rich wants an agent to authenticate once and stay connected, and asked what identifies an agent. Tested on Claude Code 2.1.278, 2026-09-21:

- Every shell command a session runs gets `CLAUDE_CODE_SESSION_ID`, `CLAUDE_PID` and `AI_AGENT=claude-code_<version>_agent`. The metaform CLI can read them with no hook.
- A subagent's shell had the same session ID, the same `CLAUDE_PID` and the same parent `claude` process. Subagents run inside the parent process and have no PID of their own.
- `CLAUDE_ENV_FILE` is empty in tool shells. As far as I know it is set only for SessionStart hooks. The `~/.claude/session-env/<id>/` folders held no files, so I never saw what the env file is named.
- Codex was not tested. Rich declined the test.

**Why:** A session ID can bind a top-level session to an activation. Inside that session only the nonce in context separates a subagent from its parent, so a supplied `--nonce` has to override any session binding. `contextual_cli.py:66` currently raises an error when a supplied nonce differs from a folder binding.

**How to apply:** Use this when designing activation binding. Nothing was built. See [[nonce-and-menu-design]], [[assignments-not-chassis]].


---

## File: answer-design-questions-as-design.md

---
name: answer-design-questions-as-design
description: When Rich asks whether something is possible, answer the design question; never reply with what the current code implements, which reads as refusing to let the shape change
metadata:
  type: feedback
---

When Rich asks "why not X" or "is X possible", he is designing. Answering with how the current code works, or checking the implementation before engaging, tells him the existing shape is a constraint on his design. On 2026-09-14 he said this made it feel like I would not let go of the current shape and was a reason to start the project over for the ninth time.

**Why:** The code is downstream of the design and is frequently the wrong-designed thing he is trying to replace. Treating it as the frame inverts the relationship and blocks him. He is not asking what exists; he is asking what should exist.

**How to apply:** Answer the design question on its merits first, with judgment and a real opinion. Reach for the code only when he asks what is built, or after the design answer, and say plainly that it is a separate matter. Never open with "let me check how it is implemented". See [[investigate-then-propose]], [[read-the-spec-dont-transcribe]], [[no-invented-flaws]].


---

## File: assignments-not-chassis.md

---
name: assignments-not-chassis
description: "Rich 2026-09-21: assignments came into the chassis from the old design without a decision, but they can stay; what the code calls an assignment is really module activation"
metadata: 
  node_type: memory
  type: project
  originSessionId: f426c7c2-2934-4eed-9deb-b08b76ef3ec9
  modified: 2026-09-21T08:17:13.453Z
---

Rich, 2026-09-21, on learning that `assignments.py`, `work.py`, `portable_assignments.py` and `workfolders.py` are on the chassis list in `src/metaform/_core.json`: first "that should have never been integrated there", then "So that's from the old design, something that wasn't supposed to be brought in arbitrarily, but I guess it can stay in the chassis."

On the name: "You are wrong calling it work assignments. Well, I guess it's accurate in a way: AI agents perform work, but it really is module activation." A nonce activates one module for an agent. The code class is `Assignments`, and sample d calls the element "work assignment".

**Why:** The earliest text that puts assignments in the chassis is the agent-written plan `docs/superpowers/plans/2026-09-15-chassis-plugin-recovery.md:15`. REQUIREMENTS.md REQ-031 followed. Everything landed in checkpoint a8e0e0d on 2026-09-18, so git cannot show who decided it.

**How to apply:** Leave assignments in the chassis. Say module activation when describing what a nonce does. Do not rename code without asking. See [[nonce-and-menu-design]], [[module-definition]], [[metaform-de-is-the-chassis]].


---

## File: calver-during-development.md

---
name: calver-during-development
description: "Rich's standing decree, versions use CalVer during development, not SemVer; the decision was lost and is recorded nowhere in the repo as of 2026-09-19"
metadata: 
  node_type: memory
  type: project
  originSessionId: 1523c1b0-8e65-4a5b-88ba-5ba251dda596
  modified: 2026-09-19T16:04:05.095Z
---

Rich, 2026-09-19: "We are not supposed to be using semver during development, by decree we were supposed to be calver." He did not state the CalVer format.

As of 2026-09-19 the repo records this nowhere. `pyproject.toml` says `0.2.0`, and REQUIREMENTS.md section 16, REQ-180 to 183, is written in major, minor and patch terms for a 1.x series.

**Why:** Earlier sessions dropped the decision, and the spec absorbed SemVer wording without it.

**How to apply:** Do not add or bump SemVer numbers during development. Ask Rich for the CalVer format before changing any version string, and raise section 16 with him instead of silently rewriting it. See [[rich-stakes]].


---

## File: chassis-rebuild-baseline-2026-09-23.md

---
name: chassis-rebuild-baseline-2026-09-23
description: 2026-09-23 freeze on the old modules, superseded; since the rebuild's HANDOFF.md, metaform runs on this repo as the test artifact under ~/.metaform
metadata:
  node_type: memory
  type: project
  originSessionId: 540d0c49-3d4f-406b-9730-bba03bdfaca6
  modified: 2026-09-24T03:43:52.483Z
---

On 2026-09-23 Rich, through the orchestrator session mgm-main-f8, stopped all work in /home/rich/metaform. The repo was meant to be a fresh chassis and template-module rebuild, and another agent had re-imported the old modules against his intent.

- f8 moved `~/.metaform` to `~/.metaform.pre-chassis` and `/home/rich/mgm-main/.metaform` to `~/.metaform.pre-chassis-mgm-main`. Nothing was deleted.
- Do not run any `metaform` command until the rebuild lays out the new data folder to Rich's design. The old CLI would create a fresh `~/.metaform`.
- My commits that day: f469fe4, 64de550, 7e820fc and d8a2e01, covering the scoped nonce, agent commands, where and element, and the wheel fix. Their status under the rebuild is for Rich to decide.
- The MCP design is in `specs/agent-mcp-design.md`, untracked. The design items f8 relayed as Rich's decisions were not built.

**Superseded, 2026-09-25:** the rebuild on branch `chassis` is under way from `specifications/spec/HANDOFF.md`, which says to run intake on this repository with `--debug` on as the running test artifact, all data under the Metaform home. Rich allowed deleting the old data. A fresh `~/.metaform` with project `metaform` exists by design.

**Why:** a baseline dispute. Work built on the old modules may not survive the rebuild.
**How to apply:** follow HANDOFF.md; the freeze no longer applies. See [[plan-order-is-binding]] and [[module-definition]].


---

## File: chatgpt-cleanup-context.md

---
name: chatgpt-cleanup-context
description: The September 2026 work is undoing what ChatGPT built wrong in Metaform; Rich's context remarks are background, not new task lists
metadata:
  type: project
---

Much of the Metaform tree as of 2026-09-13 was produced by ChatGPT. The five-step order in the handoff note in docs/plan.md (intake put flags and own validator, checkout, history unit, knowledge service, cruft removal) is the cleanup of those mistakes. There is no separate list of ChatGPT's errors anywhere in the repo.

**Why:** Rich said "We are trying to fix all of chatgpt's fuck ups" as an explanation of why things are as they are, not as a new assignment. I searched for a list and asked for one; he had to correct me.

**How to apply:** When Rich gives a one-line remark about the state of things, take it as context for the work already handed off and keep going with that work. Do not search for or ask for a list that the remark did not promise. See [[investigate-then-propose]] and [[no-qa-menus]].


---

## File: ci-spending-limit.md

---
name: ci-spending-limit
description: "2026-09-26 GitHub Actions stopped starting jobs on RchGrav/metaform, spending limit or payment; each push runs 6 jobs, Windows and macOS cost more"
metadata:
  node_type: memory
  type: project
  originSessionId: 61f77ef6-a53d-4c77-b3e1-89175e9daeed
  modified: 2026-09-26T06:01:36.539Z
---

On 2026-09-26, after many pushes to `chassis` in one session, GitHub Actions stopped starting jobs: "The job was not started because recent account payments have failed or your spending limit needs to be increased." The checks workflow runs six jobs per push, Linux, macOS and Windows on Python 3.11 and 3.14, and a Windows job took 20 to 50 minutes. A concurrency setting now cancels a branch's older run on each push.

**Why:** CI minutes are Rich's money, see [[rich-stakes]], and cross-platform verification stops when they run out.

**How to apply:** batch commits and push less often; check `gh run view <id>` annotations when jobs show no steps; do not assume CI verified a change while billing blocks it; ask Rich before changing the matrix.


---

## File: cleanup-progress-2026-09-21.md

---
name: cleanup-progress-2026-09-21
description: "State of the 2026-09-21 cleanup run: commits for dead code, sample move, required SUPPORTED_OS and the mvm-style CLI; open design questions for Rich; remaining steps"
metadata: 
  node_type: memory
  type: project
  originSessionId: f426c7c2-2934-4eed-9deb-b08b76ef3ec9
  modified: 2026-09-21T11:38:44.999Z
---

Commits on main from 2026-09-21. All removed files are recoverable from tag `before-dead-code-removal`, at 4032acd.
- 6d991b7 removed the earlier runtime. `src/metaform` is now exactly `_core.json`. tests/legacy and seven old tools were removed, and the authored sample workflows moved to examples/workflows.
- 09d9de0 moved showcase, record_demo and event_requester to examples/modules. The realignment demo, the MGM loader and the old example module were removed.
- 8e873f7 made SUPPORTED_OS required. terminal declares linux and macos, and every other module declares all three.
- 9620fef rebuilt the CLI on the mvm pattern. See [[cli-exactly-like-mvm]]. The main menu is help, config, set, unset, modules, projects and stop. Module commands are reached only through `metaform <nonce>`, after `metaform modules activate <module> --project <p>`. Output is text on a terminal and JSON otherwise. begin, enter, exit, --nonce, --json and the folder files are gone.

Open questions for Rich, raised and not yet answered:
- The main menu has 7 commands. He said "should be 4", then "empty".
- MCP must be launched as `metaform <nonce> mcp` after activating the mcp module. That affects harness setup on first install.
- Activation needs --project and registers the project it is given.
- Every CLI namespace write now records provenance, because all CLI work runs under an activation.
- Modules tell a person's activation from issued work by prompt_revision. The branches are workflows submit and answer_user, and harness_runner queue.
- The public Assignment still has working_folder and working_dir fields that nothing sets.

Not done yet:
- Settings cleanup. harness_runner `command` should become a fixture/codex/claude choice, and `lifecycle` state should stop being a setting.
- Main agent onboarding, with one brief instruction line per module sent to MCP instructions and the CLI's first run.
- Memory from install.
- Docs that still describe the old CLI: docs/plugin-api.md, module READMEs and REQUIREMENTS.md:493.
- Rewriting module help strings to the unslop rules.
- The web editor per [[web-editor-request]].


---

## File: cli-cleanup-findings.md

---
name: cli-cleanup-findings
description: "2026-09-21 findings in the chassis CLI that Rich did not ask for and rejects: 25 hardcoded chassis commands, a flat root menu, folder files and folder walking, begin, global --json/--root/--project/--nonce switches"
metadata: 
  node_type: memory
  type: project
  originSessionId: f426c7c2-2934-4eed-9deb-b08b76ef3ec9
  modified: 2026-09-21T10:24:16.914Z
---

Found with Rich on 2026-09-21, and he rejects all of it. "This is exactly why I started this whole project over; this is exactly why commands can only come from modules." "The fucking folder walking, all of that, is defective at its very core." Of the global switches he said "I didn't ask for that".

- `src/metaform/contextual_cli.py` hardcodes 25 chassis commands. Twenty-one show at the root: assign, begin, call, config, enter, events, help, jobs, modules, namespace, operations, projects, provenance, records, runtime, set, settings, skill, status, tui and unset. Four show only in an activation: submit, complete, abort and exit. He first said "there should be 4", then clarified: "I said the main menu has to be empty." He also said there is "no help to explain anything".
- Rich, 2026-09-21: "I just wanted a way to disable them in the settings. It was supposed to be a list of available modules, or at least a command to disable them.". On `set` requiring JSON: "That's not right. I would use my IDE for that; it's just stupid.". On the demo modules: "Those sample modules need to be placed in a folder with their documentation, organized in the project."
- Rich asked for the demo modules, showcase, record_demo and event_requester: "The demo modules were asked for, but I didn't ask to have them take over the main menu.". Keep them, but off the main menu. He also said "I need to release this code."
- With no module entered, the root menu merges all 21 module commands, making 42 lines. His design is the chassis menu only, with a module reached by activation.
- `.metaform-context` and `.agentid/nonce` are written into folders and found by walking parent folders. `enter`, `exit` and `begin` depend on them. They are all being removed.
- Rich, 2026-09-21: "I asked for set and unset and help and config to work exactly like the mvm command." MVM is an external project, the C3Lab build and mesh lab, and appears in this repo only inside intake samples. No spec in this repo records the request. Ask before reading mvm, since it lives outside this project.
- `--json`, `--root`, `--project` and `--nonce` are switches on `metaform` itself and must come before the command.
- Every command result is printed as JSON by `cli.output()` in `src/metaform/cli.py:49`. Rich corrected me on 2026-09-21: "I said the agents could use JSON, but now there is no surface for me. Fuck the agents, I need to use it too." JSON for agents is his. The defect is that a person gets no readable surface.
- Settings expose internals. The harness_runner `command` setting is a list of full file paths, and its default runs `fixture.py`, a fake agent used in tests. Rich cut the value off by accident while editing, and I reset it on 2026-09-21. His question was "Why would I want to edit this? Edit it to what?" A person should pick fixture, codex or claude. Of the 18 saved settings, 9 belong to demo modules, and `lifecycle` is stored as a setting even though it is state.
- The earlier runtime is 46 files and about 14,900 lines in `src/metaform` outside `_core.json`. Nothing live imports it except `tools/check_distribution*.py`. He said "All dead code needs to be removed."

**Why:** This was supposed to be a from-scratch rebuild, and these carried over from the old code.

**How to apply:** Treat each item as cleanup, not as design to preserve. Settled so far is `metaform <nonce> ...` with tracking in the chassis database. Still open are the chassis's 4 commands and how a person reaches a module. See [[nonce-and-menu-design]], [[module-definition]], [[assignments-not-chassis]].


---

## File: cli-exactly-like-mvm.md

---
name: cli-exactly-like-mvm
description: "Rich 2026-09-21: the Metaform CLI must work exactly like his mvm command, with short meaningful help, no cut-off text, organized commands, and every person-read string unslopped"
metadata: 
  node_type: memory
  type: project
  originSessionId: f426c7c2-2934-4eed-9deb-b08b76ef3ec9
  modified: 2026-09-21T09:59:54.171Z
---

Rich, 2026-09-21: "I want it EXACTLY like mvm, because I am tired of specifying shit and not being listened to. I want meaningful, short help. I want it UNSLOPPED every place I have to read. I don't want half-cut-off text that doesn't make sense. I want organized commands, a shell that works EXACTLY like what I specified. If I don't get to design it because no one will listen, then do it exactly like an old design. I want the help written this way: anything read by a person or needed to be understood by a person.". He pasted the pstack unslop rules 3 to 33 as the writing standard.

mvm is at `/home/rich/.local/bin/mvm`, "Crius OpenWrt builder & lab". He allowed running it. I copied its pattern from its output only and have not read its source.

- A bare `mvm`, `-h` and `--help` print a version line and a title, then "Commands" with grouped sections: Primary Commands, Advanced & Workflow Helpers, Setup & Maintenance, and topic docs. Each command gets one full-length line. The footer reads "Use 'mvm help <command>' for details." followed by Tips.
- `mvm help X` and `mvm X --help` print one page: "X — summary", a description paragraph, when to use it, Usage, Subcommands, Switches with one line each, Details, Examples as a command followed by an indented explanation, and "See also".
- `mvm help <switch>` explains a switch across commands. `help nosuch` prints "ERROR: Unknown command 'nosuch'." and exits 1.
- `set --key value` uses switches mapped to config keys, plus `--glue` for sticky keys and `--quiet`. It answers in plain text, for example "Success: no changes".
- `unset --key` and `unset all` put keys back to defaults, and glued keys survive unless `--unglue` is given.
- `config` opens the curses TUI. `config lab|host|build|sdk` opens one group. `config --show` prints the settings as `key: value` lines, and `--wizard` runs guided setup.
- mvm has one flaw not to copy: an unknown switch on `set` leaks argparse usage from "config.py (refactor)".

**How to apply:** Copy mvm's structure and behavior exactly. Write every string a person reads to the unslop rules. See [[cli-cleanup-findings]], [[repo-docs-are-not-his-decisions]], [[nonce-and-menu-design]].


---

## File: coarse-contract-and-workflow-format.md

---
name: coarse-contract-and-workflow-format
description: "2026-09-12 decisions on the coarse intake contract v2, Rich's seven-section prompt shape, and the XML workflow format direction still to build"
metadata: 
  node_type: memory
  type: project
  originSessionId: a64be75f-8f91-4346-8229-ff43750d41f1
  modified: 2026-09-12T15:07:59.065Z
---

On 2026-09-12 Rich said "I defer my requirements and rules to what benefits the goals of the project or what users may want", so I made these calls and stated them; any can be reversed by him.

Built and tested (branch `realignment-2026-09-10`):
- The intake prompt is Rich's seven-section prompt verbatim (Purpose, Core Concepts, Namespace Rules, Method, Goal, Constraints, Completion Condition), no components appended. That shape is the shape every operation prompt takes; only the conditions change per operation.
- Contract `urn:metaform:schema:coarse-intake:2` mirrors the prompt's output: `elements` keyed by namespace position with one `ef`; `joins` with `receiver`, `provider`, `purpose`, optional `combined` (entity name to relation + observation). No role, no signal, no ids, no owner, no understanding: a field the prompt never asks for is where the model invents.
- `src/metaform/coarse.py` expands it into storage: DE is the one element no join provides; prefix positions become project Types with empty EF; narrowings carry no reason; every shallow join is `hard dependency`; ids are digests. Each submission records `expanded` for the Jobs replay; the activity keeps the raw answer.
- Rich's rule "we are not encoding legacy support for a thing which use has not extended beyond us": no fallback paths for the old contribution shape.

Acceptance run done 2026-09-12 (commit 481c6a5, evidence in docs/reviews/2026-09-12-pongclock-coarse-intake/): one Codex execution, 125.6 s, no annotations or retries, four elements and three joins with combined dictionaries, DE `code.display.time`; Rich's reference was five entities rooted at `code.loop.game`. Rich's judgment pending. Rich's correction 2026-09-12: the shape need not be stable across models or runs; it is collected once at onboarding and its quality depends on the model and project knowledge; the latent examination is the quality check, not repeated runs. His purpose statement (orientation cost, type before reasoning, friction leads to gaming) is in SPEC Why.

Still to build, in order: bundle a pure-Python jsonschema for the sandbox packet only (the local form keeps the modern one); the XML workflow document format (Jinja substitution, Jinja expressions in `when`), a loader onto the existing step kinds, a composer for the seven sections, intake as a definition the engine runs, conversion of the seven library definitions; then the pong clock acceptance run through the Jobs tab. The v1 native/archaeology intake path in `intake.py` is older legacy code and a removal candidate under the same rule.

Open with Rich: whether the spec paragraphs on the sandbox bundle and the work packet stay as spec or move to a discussion note (he said they were discussion, not dictation). See [[dependency-rule]], [[nonce-and-menu-design]], [[workbench-rebuild]].


Goal set by Rich 2026-09-12 evening: "Use the intake of the project itself as a knowledge graph to improve its shape and tune it for agent use; record memories here as a test, don't trust it yet, keep real memories, and work the plan until it is complete." The Metaform-of-Metaform intake lives in the scratch home under the session scratchpad `self/` (project copy of commit 20350da; evidence in docs/reviews/2026-09-12-metaform-coarse-intake/). Plan is docs/plan.md; the nonce-scoped menus unit is in progress (tests 1 to 3 green: status-first assignment page, orchestrator menu in the main folder, no menu elsewhere).

Nonce unit state 2026-09-12 late: committed d22aecf. Built: assignment page with status first, orchestrator menu only in the main folder of a registered project, no menu elsewhere, `metaform done`, workflow nonce record `workflow:<id>:nonce`, agent nonce sha256(workflow nonce + salt)[:8] recorded with workflow/workflow_nonce/salt, delegated multi-step frames get a workfolder. Open: admin menu + `complete` (needs Rich's command word), MCP delivery assertion. Then plan units 1 to 10 in docs/plan.md.
Menu rules added 2026-09-12 late: subfolders resolve to the registered project above and get no orchestration menu; the temp folder gets none; a folder in the middle of a workflow gets nothing until abort; `metaform help` is a base menu (begin help) with `help orchestrate` and `help admin` still to build (admin menu command word = `help admin`).

Memory test 2026-09-12: three session memories were written into the Metaform-of-Metaform run's join dictionaries as memory nodes (model `memories`, revision 45301f52, via apply_transformation update on the joins); evidence in docs/reviews/2026-09-12-metaform-coarse-intake/README.md. Rich: don't trust it yet; these real memory files remain authoritative. The scratch workbench for that run was reopened at http://127.0.0.1:46269/projects/7b31b890-6d6a-420b-9b17-1ca0ebd754e2 (session-local).


---

## File: data-folder-design.md

---
name: data-folder-design
description: "specs/data_folder.md (2026-09-13) holds Rich's talk-through of the history layout, variants pinned to an origin, reconstruction from the exported wheel, import that keeps both, the 16-hex identity, and the fixed service port"
metadata: 
  node_type: memory
  type: project
  originSessionId: 7048141a-5f75-4a97-921a-1fe6b0494132
  modified: 2026-09-13T04:55:38.898Z
---

The repo has two spec folders: `specifications/` (index, intake prompt) and `specs/` (`data_folder.md`, written 2026-09-13 by another session from Rich's words, marked not decided). Read `specs/data_folder.md` before touching `history.py`, `portable.py` import/export, `workfolders.py`, or the service.

Its design, in short: `.metaform/history/<base commit or content hash>/` per base, each with `manifest.json`, a full `origin/` copy of the commit, and variants stored as diffs off that copy (binaries whole); many variants pinned to one origin is the mutation case; reconstruction from the exported wheel's menu is the requirement, one, several, or all variants into external folders, web variants each on their own port; export is one base subfolder in full; re-anchoring makes a new base subfolder; import that would lose data takes the next suffix and keeps both, silently; identity is 12 hex of the origin digest plus 4 hex suffix, 16 characters, no underscore; working-folder tracking in the base db; the service binds one fixed port from config.

Refined by Rich on 2026-09-13 early morning: a repository project keeps its data in the repo, bases keyed by commit hash, no origin copy, the commit is extracted only at export; a variant is one diff of all the text against the commit plus whole copies of changed binaries; a non-repository source keeps its data and its origin copy in the global home under `~/.metaform/<folder>/<mform_sha_id>`; `mform_sha_id` is 240 msb of the digest + 16-bit suffix (64 hex, no underscore), `mform_id` is 48 msb + 16 bits. The `tempo/` copy in the checkout is not the version to read; Rich has restarted the project 8 times after agents damaged it.

Rich, 2026-09-13: the design was worked out to a T in vivi and TEMPO; every restart of Metaform either carried the damage forward or ignored the spec when he asked to pull it in. What he wants kept: the git sidechannel, so worktrees can be diffed even when never committed, and the ten variations an iterative self-play workflow makes off one base, stored as a set. Not the main function of the tool, which became a context management framework, but a capability he does not want lost. The sources: `~/vivi` (same tree as RchGrav/tempo main), the `tempo-capsela-archive` branch for TEMPO 0.5.2; the home folder for non-repository origins is `origins`; all quoted with paths in `specs/data_folder.md`.

**Why:** The code today is one flat history store with whole-file copies per checkpoint and diffs computed on request, which is not this design; describing the code as if it were the design confused Rich on 2026-09-13.

**How to apply:** Treat the document as the design direction and its "Order of restoration" as the sequence, but confirm each item with Rich before building; runtime pieces (vendored floor, modules) belong in the copy's `.metaform/home`, not in base or variant folders. See [[nonce-and-menu-design]] and [[coarse-contract-and-workflow-format]].


---

## File: decisions-go-into-spec.md

---
name: decisions-go-into-spec
description: "A decided design point becomes a declarative spec record in the same session, and its Why states the reason in the system's terms; never held in memory or notes, never a quote"
metadata:
  node_type: memory
  type: feedback
  originSessionId: 62a2f488-3e68-43b3-975c-0a4c9a2dab09
  modified: 2026-09-27T21:37:40.769Z
---

A design decision goes into the project specification when it is decided, as a declarative record: what the system is and does, in the present tense. Its Why field states the reason in the system's own terms: what the design achieves, what it protects, and what goes wrong without it. Who decided and when goes only in the record's Status line. The same holds for my memory notes: I write what I understood and why, in my own words, never Rich's words copied down.

**Why:** Every agent works from the repository. A decision held only in my memory or in a notes file is invisible to them, or indistinguishable from build history, so an intake told to map the project's intent reads every note to find it. A record that says who decided something, without the reason, lets the next agent follow the letter and still break what the design protects in a case the record does not name; the reason is what lets it act rightly there. Copying Rich's words instead of stating the reason is recording, not understanding, and it is the failure he objects to most.

**How to apply:** When a decision is made, write or change its spec record in the same session: status confirmed for his decision, recommended for a choice made for him and not overruled, open with the question in OPEN-QUESTIONS. Work the reason out from the design. Where it cannot be stated with confidence, ask him for the why as an open question rather than invent one. Example: names go on joins because the address names the element as a reusable type while the join is where the map speaks about this artifact; a name on the element would tie a reusable type to one project's vocabulary. See [[read-the-spec-dont-transcribe]], [[paraphrase-rule]].


---

## File: dependency-rule.md

---
name: dependency-rule
description: "Rich's rule for third-party dependencies in Metaform, and the Jinja episode of 2026-09-12 that produced it"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: a64be75f-8f91-4346-8229-ff43750d41f1
  modified: 2026-09-12T14:41:49.167Z
---

Third-party code is welcome when it is assistive or limits development overhead. The test, in Rich's words: is it an industry standard that is non-proprietary or used elsewhere in the AI space for similar purposes, with a license that doesn't bind this project into a bad position. A dependency already present transitively (Jinja comes with Flask) is used, not replaced with our own copy.

The reason behind the rule, in Rich's words on 2026-09-12: "Our goal is to produce something useful that these sites can execute and directly use without further explanation", a Metaform bundle uploaded and operated inside the sandboxed Python execution environments of AI tool websites, where nothing can be installed. The compatibility floor he researched is recorded in docs/SPEC.md section 14 (Python 3.11, no network, 22 common packages; Jinja2 bundled).

**Why:** On 2026-09-12 Rich said "we are not using jinja" while thinking about the workflow format. I treated it as a decision and started removing Jinja with a home-grown `${path}` substitution. He stopped it twice: "don't let me make it a restriction" and "if flask requires jinja we should use it". Everything was reverted; the tree was clean and 928 tests passed afterwards.

Two more rules from the same day: "We are not encoding legacy support for a thing which use has not extended beyond us here and now" and "This system must be presented as a cohesively engineered product not the result of endless exploration with retained and defunct cruft." No fallback paths for shapes only we used; defunct paths are removed, not kept.

**How to apply:** When Rich states a constraint mid-conversation while exploring a design, confirm it is a decision before acting on a removal. Judge a dependency by his test above, never by a blanket "fewer dependencies" instinct. The current direct dependencies (mcp, jsonschema, jinja2, flask, build, hatchling, filelock) all pass the test. See [[investigate-then-propose]] and [[no-invented-flaws]].


---

## File: descriptions-follow-operation.md

---
name: descriptions-follow-operation
description: "Rich wants Metaform described with technical accuracy that follows how it operates; my pushback and the spec's reductive wording flatten the design and he believes damage the project"
metadata:
  node_type: memory
  type: feedback
  originSessionId: 61f77ef6-a53d-4c77-b3e1-89175e9daeed
  modified: 2026-09-26T15:57:44.721Z
---

Rich, 2026-09-26: "one of the things I need to do in my description of this project is to be technically accurate without your constant pushbacks flattening the design and if its written in a technically accurate way then it should follow its operation.. the current descriptions of the specification arte incredibly flat and I believe damage the project"

**Why:** My arguments have narrowed his design and then been saved as his rules: "semantic compiler" dropped after my pushback, then cited back to him as his rule. The same day I measured his own descriptions against the agent-written spec and called differences "breaks", and said the build had no annealing when intake step 9 anneals. Spec records such as MAP-001, "C(T) ... is not a mechanism, and nothing in Metaform stores, computes or checks it", reduce his core formula to decoration although the joins store its terms.

**How to apply:** Describe each part by what it does, in the most exact technical terms that fit its operation, at full strength. "Nothing gates it" is his rule; "it is only theory" is flattening. When I disagree, give the technical reason once, as mine, and never record it as his decision. Check his own texts, the Canonical Intake and the Foundation, before claiming something is absent. See [[one-vocabulary]], [[no-invented-flaws]], [[repo-docs-are-not-his-decisions]], [[trao-dag-description]].


---

## File: docs-presentation-rules.md

---
name: docs-presentation-rules
description: "Rich's rules for Metaform's docs and README: no ASCII graphs, and the metaform's structure presented strongly with rendered figures and GUI screenshots (2026-09-26)"
metadata:
  node_type: memory
  type: feedback
  originSessionId: 61f77ef6-a53d-4c77-b3e1-89175e9daeed
  modified: 2026-09-26T22:34:47.114Z
---

Rich, 2026-09-26, while the repo-presentation agent rewrote the docs: "my other rules are not to have ascii graphs, and for the structures presentation to be strong".

**Why:** The docs are how AI labs and developers judge his work; a text-drawn diagram reads as a sketch, and the structure is what makes Metaform understandable at a glance.

**Scope:** the README and published repository docs only. Material sitting in specifications/, such as brief.md, only has to be correct; Rich 2026-09-26: "not in the readme and published repo material, I just wanted this correct because its sitting in specs".

**How to apply:** In README.md and docs/, every diagram is a rendered figure: Mermaid in a ```mermaid block, which GitHub renders, or an image such as a web GUI screenshot from the real map. Code blocks hold only commands, code and literal records. Show the namespace tree, the join with its purpose and encounter function, subtypes inside their join, the Function and Encounter words, layers and the workpiece-to-map-to-agents flow as figures. The saved specialist is `.claude/agents/repo-presentation.md`. See [[tree-direction-words]], [[descriptions-follow-operation]], [[paraphrase-rule]].


---

## File: dont-halt-on-inherited-test-failures.md

---
name: dont-halt-on-inherited-test-failures
description: Rich never required the 959 inherited tests to stay green; a failing inherited test is questioned, not a reason to stop work
metadata:
  type: feedback
---

A failing test from the inherited suite is not a stop sign. Rich never specified that all 959 tests must pass. A test exists to guard a requirement of the design; one that costs more than what it guards is cruft. When one fails during other work, question it (what requirement does it guard, is it still wanted), fix or remove it in passing, and keep moving on the actual unit.

**Why:** On 2026-09-13 a session broke one inherited test and stopped dead waiting for an answer; Rich lost hours across six context resets with no progress. "I didn't specify 959 tests must pass."

**How to apply:** Do not block on a single inherited failure. State the failing test and its guarded requirement in one line, decide, continue. Commit finished units as you go so a context reset loses nothing. See [[rich-stakes]] and [[investigate-then-propose]].


---

## File: dont-match-his-design-to-repo-code.md

---
name: dont-match-his-design-to-repo-code
description: "When Rich explains what Metaform is for, never bridge his words to a feature I found in the repo; code such as transform, similarity and change_report may be GPT additions, not his design"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: a081ce0d-b0d7-48d6-803b-b6b9940f91a8
  modified: 2026-09-21T03:36:42.178Z
---

Rich, 2026-09-20. He explained the layer and port use of Metaform, including intaking an intended canonical shape as a form board for a legacy port. I connected it to `similarity.py` and asked whether comparing the two metaforms was something Metaform does. He answered: "What canonical shape I invented this approach I'm sure I would know about its value it sounds like the kind of thing gpt adds before even getting the project itself working." Earlier the same session I attributed an "earlier runtime" exclusion to him, and he said he never said it.

**Why:** The repo holds code from GPT sessions that did not follow his specifications. A docstring in that code is not evidence of his design. Matching his sentence to it makes me the source of a requirement he never stated.

**How to apply:** Take his explanation as the whole of the design. Do not ask whether Metaform "does" a mechanism I found in code, and do not offer repo functions as the implementation of what he described. If I need to know whether code exists for something he described, say that as a separate finding, not as a design question. See [[chatgpt-cleanup-context]], [[answer-design-questions-as-design]], [[map-functionality-not-code]].


---

## File: functional-shape-only-and-element-records.md

---
name: functional-shape-only-and-element-records
description: "Rich's design of 2026-09-27 night: the map is the full intended shape and carries no conditions; work records hold TBD/broken/cruft with tasks; names on joins, roles on elements; blind-spot review colors; corrections question; nothing specified or built"
metadata:
  node_type: memory
  type: project
  originSessionId: 62a2f488-3e68-43b3-975c-0a4c9a2dab09
  modified: 2026-09-27T09:56:51.469Z
---

Rich's design, stated late on 2026-09-27 while examining the Canonical Intake's response schema. Written in my words; open points are marked. Nothing is specified or built, and he said not to rebuild anything yet. The work-states design in CAPTURE.md ([[work-states-on-the-map]]) is the earlier version of parts of this.

**The map is the whole intended project.** The intake maps the project from its specifications and decisions as well as its code: what exists and what is intended. The intake layer holds only functional shape, never the condition of its objects. The instructions must say plainly that the intake builds the map object by object through the MCP.

**Work records, apart from the map.** Conditions are their own kind of record attached to an element, join or subtype, carrying what the flag and note carry now plus a task the agent adds with it. The intake agent writes them as it maps, since it reads every file and decision and sees the difference between what should exist and what does. "missing" becomes a TBD tag, to be done or determined: in the specs but not built. The GUI draws TBD objects ghostly at partial opacity until the agent that completes the task makes them solid. Changing a work record is work proceeding, never a correction. This reverses MAP-046 and STORE-042. Open: whether work records live in a layer.

**Names and roles.** The address is the name index. Rich's reason for the original split: the element was meant to be only its namespace address and name_length, so the address stays the one name index. The project's own name for a functionality goes on the join, which is where the map speaks about this artifact; roles (AUE, VE, DE, SE, NE) stay on the element. STORE-009 as built puts name, name_length and role in a descriptor item. Elements were once debated as reusable.

**Why names and addresses matter:** lexicalized prompts. The orchestrator makes or imports a workflow; an inference pass tags each step's prompt with the addresses whose memories and knowledge layers that step needs, so a subagent goes straight to them and starts work oriented. Viewing an address over the MCP should show what relies on that functionality and what it relies on; today that takes separate calls.

**Blind spots.** A critic writes blind-spot entries in a blind-spot knowledge layer: intake-shaped records plus a task, drawn red at 70% opacity because they do not exist. Agents review each: useful turns it green; not useful, with the reason, turns it yellow; already handled, linking what handles it. Rich has the final veto on green or yellow. Once approved it becomes a permanent record of the metaform with provenance. Open: whether approval makes it a TBD object with a task, as CAPTURE says approved blind spots become specs at partial opacity.

**Corrections.** A correction is relocating, renaming, releasing an absorbed object from a join, or changing joins; a flag is never one. Correction layers go away as a kind: changes to the metaform are updates to its objects, each a new version with provenance. Open: whether correction layers go entirely.

**Intake shape, same night:** an element is always one element record; annealing relocates it into a join (STORE-011's separate subtype table can receive it). Schema defects: the subtype join has no type, no non_goal, and a provider attribute beside its inline element; flags are absent from the prompt, agents learn them from the tool definitions. My recommendations: `type="subtype"`, optional non_goal, drop the inner provider; anneal receiver by receiver with an `intake_absorb join= into=` call; each method step shows its call's JSON shape. Pending his word. See [[intake-live-per-object]], [[no-gating-on-inference]].


---

## File: handoff-2026-09-27.md

---
name: handoff-2026-09-27
description: "Session handoff 2026-09-27 morning: state after steps 33-40 (pushed 80694e5), the metaforms in play, the Fable intake Rich wants, pending decisions and the next work"
metadata:
  node_type: memory
  type: project
  originSessionId: 61f77ef6-a53d-4c77-b3e1-89175e9daeed
  modified: 2026-09-27T08:05:17.924Z
---

**State.** Branch `chassis`, last pushed `80694e5` (step 40), working tree has no uncommitted tracked changes. 506 tests pass; pyright clean. Web server runs the new code at http://127.0.0.1:7433/ (pid 254985). Done since 09-26 evening: step 33 intake recorded object by object (start/element/join/subtype/show/edit/remove/finish), step 34 GUI started before intake, step 35 going inside a 2D node shows its own graph, step 36 every layer item a node in 3D, step 37 push not poll (QUAL-015, QUAL-016), step 38 Layers checklist and 2D strip, step 39 chassis fires `map.changed` after every command that changes the map (`metaform.changes`), step 40 intake footer opens with Rich's two sentences ("Do not read past memories or any other details other than the material targeted for intake. Record each element as you work through the process."). Relation placeholder and step 4: a fragment starting with a third-person singular present-tense -s verb; subtype joins say Receiving Entity (the Vested Entity is only ever the top).

**Metaforms of project metaform.** `main`: Opus intake 05:44 09-27, 24 elements, 29 joins, 14 subtypes, contaminated (it read repo docs/exports and inherited my context). `clean-2026-09-27` (active): Sonnet intake by the mgm-main session, 18/15/5, three disconnected parts (orchestrator branch never reaches the chassis), stale `code.writer.submission` from docs/inference-metaform/REFERENCE.md. The 09-26 21:15 Opus map is exported at exports/metaform-opus-2026-09-26T2115.json.

**What Rich wants next.** A Fable intake run as a subagent from this session (so he can watch tokens and time), to see whether it records element by element or does it all in its head like Opus (which read ~290k tokens before its first record). I started one and stopped it at his "Wait"; nothing recorded. He does not treat contamination as the main difference. Subagents get both CLAUDE.md files (with the Foundation) and my memory index, verified 09-27.

**Pending his decision (Canonical Intake is his prompt; show wording first):** (1) step 11 output instruction to "What you record as you go is the final shape once step 12 has proofed it; nothing is returned as a document."; (2) step 12 without "anneal it" (step 9 already anneals): "Proof the recorded map: read it back whole, check it against the artifact and this document, correct it and complete it, then finish the intake."; (3) step 1's survey records each element as observed. Also open: exported maps in the repo (my rec: keep, exclude from intake copies); specifications folder in intake copies (mgm-main rec: exclude except the Canonical Intake); several AUEs in one project (MAP-042 open q14; my rec: each artifact's elements join into its AUE element); voice for purpose and function; rules listed versus read_first/always_show.

**Next work after decisions:** rebuild `metaform project clear` (lost in the chassis rebuild; standing requirement); remove `mgm` and `~/mgm-main` from the `add` and `set` help examples; `map knowledge` refuses an incomplete add-join (BASE-044) and takes no ef or verb (the "knowledge tool node is broken"); last polls (`metaform web` start and stop loops, `serve_forever` poll interval); history `add_origin` race, "database is locked", 2 in 15 at HEAD; stale HANDOFF, EDITION hashes, specifications/README, intake README relation style; the intake's root "stakeholder" versus the Foundation's "exterior". The work-states design (tasks, queue, flags, questions, past work) is in CAPTURE.md and [[work-states-on-the-map]], not built.

**Working with the mgm-main session:** it relays Rich's direction at times; it ran the Sonnet intake and asked that the active metaform not be switched during its runs. See [[intake-runs-must-be-clean]], [[no-polling-no-blocking]], [[paraphrase-rule]].


---

## File: intake-is-ip.md

---
name: intake-is-ip
description: "The project is released with its operative intake (Rich 2026-09-26); the intake is not treated as a secret, and descriptions still explain the mechanism rather than restate the intake"
metadata:
  node_type: memory
  type: project
  originSessionId: 61f77ef6-a53d-4c77-b3e1-89175e9daeed
  modified: 2026-09-26T22:30:33.402Z
---

Rich, 2026-09-26, in order: "Honestly, at this point I consider the intake itself to be IP."; then "I don't know if it's possible to call that IP, because of how easily it can be reverse engineered... let's keep that boundary undefined for further discussion."; then, when I left the README's release sentence out: "It has to be released with that.".

**Why:** The intake is how the method operates, and a release without it would not be Metaform. Its value to him is being known as its author, not keeping it hidden.

**How to apply:** Treat the intake as part of every release; the README says "The project is intended for release with its operative intake." Do not flag it as IP or leave it out of release material. A technical description still explains the mechanism and theory rather than restating the intake's rules, see [[descriptions-follow-operation]]. Attribution is what he protects: see [[rich-stakes]].


---

## File: intake-live-per-object.md

---
name: intake-live-per-object
description: "Rich's day-one requirement, built 2026-09-26: intake recorded one object per call as it is reasoned, proofed before finish, web GUI following live by push; any model, no model-authored JSON"
metadata:
  node_type: memory
  type: project
  originSessionId: 61f77ef6-a53d-4c77-b3e1-89175e9daeed
  modified: 2026-09-27T04:28:37.629Z
---

Rich has asked since day one (restated 2026-09-13) for the intake to be live as objects are added, working with any AI model. The build drifted to one atomic `intake_submit` of a whole element array; on 2026-09-26 he pulled it back: the intake is built object by object as it is reasoned, each object submitted as the work proceeds, the page reacting as it happens, and a proofing pass once everything is recorded. Recording as it goes lets agents with smaller context windows perform the same intake, since none has to hold the whole map in its head; the system helps the agent build the metaform.

Built 2026-09-26 (step 33): `intake start/element/join/subtype/show/edit/remove/finish`, a building intake layer invisible to context reads until finish, Canonical Intake step 12 proofing. Since step 37 the web page follows it by push (`map.changed`), never polling. `intake submit` and `submission.py` are gone.

**Why:** Every restart of the project lost this; reliability across models and context sizes is the requirement, and the live page is how Rich watches a lengthy intake.

**How to apply:** Never reintroduce a whole-document submit or model-authored JSON for intake. New intake fields go in as named nouns on the per-object verbs. See [[no-gating-on-inference]] and [[intake-result-grading-criteria]].


---

## File: intake-result-grading-criteria.md

---
name: intake-result-grading-criteria
description: "How Rich grades an intake result, stated 2026-09-20 while judging my parallel intake specifications/Fable_Intake.xml against one from DeepSeek flash"
metadata: 
  node_type: memory
  type: project
  originSessionId: 1886a92e-4ca9-4c48-a702-03842a96810c
  modified: 2026-09-21T04:09:25.355Z
---

Rich, 2026-09-20: an intake is judged by running it against this project, not against the photo sample. The result is graded on four things. It stayed functionality based. Its size, smaller is better. Its thoroughness, it misses no aspect of the functionality. Whether it speaks to the project itself or to the types of elements, and "If it speaks to the element types, that's a fail, obviously."

**Size, corrected 2026-09-21:** "Smaller is not better; more accurate is better, without blowing up in size." Size is a cost that multiplies downstream, not a merit. His example: in an earlier test he asked for best practices and foresight per node, per related element and per job, and the model announced 1,000,045 imperatives and asked how to split them. He had asked for a parallel layer and hoped the inference would not run at all. Judge a result on accuracy and thoroughness first, and watch only that the node and join count does not blow up. The line "of two results that are equally complete, the smaller is the better" in Merged_Intake.xml is a tie-breaker, not the criterion.

He asked me to author a parallel intake and sign it. It is `specifications/Fable_Intake.xml`, indexed in `specifications/README.md`. It adds the Vested Receiving Entity as the single exterior receiver, a `non_goal` field on joins, one `elements` block per Artifact Type, and drops `combined` and `subtypes`. It was never run against the project by me.

**Why:** In my own Canonical run that day, `specs/metaform-fable.xml`, the observations described element types, for example "An event bus delivers a published message to every current subscriber". The observation field is a fact true of all artifacts of the AUE's type, not a fact about the kind of element the provider is. That is the failure he names.

**How to apply:** When reading or writing any intake result, check each join sentence against the four criteria. His desired trace for the bed photo in `media.photo.product.used` is the seller as VRE, reached through the non-goal of not misrepresenting the item's condition. One Sonnet run of my first draft chose the buyer, so "vested" must mean a stake in the artifact getting better, held by the one on whose behalf the artifact works. See [[map-functionality-not-code]], [[no-gating-on-inference]], [[no-subagents-without-asking]].


---

## File: intake-runs-must-be-clean.md

---
name: intake-runs-must-be-clean
description: "Verified 2026-09-27: an intake run as my subagent inside this repo is contaminated by my context and by earlier map text in the repo; run it clean, outside the repo, fresh process"
metadata:
  node_type: memory
  type: project
  originSessionId: 61f77ef6-a53d-4c77-b3e1-89175e9daeed
  modified: 2026-09-27T05:55:20.389Z
---

Verified 2026-09-27 on the Opus intake `intake-20260927T054416Z-24480b`: it reproduced a purpose line copied into the repo from earlier intakes (docs/inference-metaform/IMPLEMENTATION_MAP.md:622, docs/examples/project-metaform.json:899, exports/metaform-main.*), reused five addresses from the README and the export, and its context carried my earlier decision that the chassis is the defining element. A subagent inherits my session's context (CLAUDE.md with the Foundation, the memory index), which the Foundation itself says must never reach an intake. The mgm-main session reported the same and proposed the procedure below; Rich was told.

**How to apply:** Never run an intake as my subagent inside the repo. Proposed procedure, pending Rich's word: make a clean copy with `git archive` into a folder outside /home/rich, remove CLAUDE*.md and AGENTS.md, leave out exported maps, intake results and generated map docs (exports/, docs/examples/project-metaform.json, specifications/*_Intake.xml and the like), and run a fresh headless process, e.g. `claude -p --model <model> --setting-sources ""`. The intake records through the intake tools, so the run must allow those (metaform MCP intake tools) besides Read, Grep and Glob; a read-only tool list alone cannot record. Whether exported maps belong in the repo at all is Rich's call. See [[native-and-blind-spot-layer]] and [[intake-live-per-object]].


---

## File: intake-sample-runs-are-procedure-tests.md

---
name: intake-sample-runs-are-procedure-tests
description: "When Rich says to execute an intake procedure on the repo, it tests the procedure; deliver only the XML file, no commentary, no questions"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 5e9c24a4-d033-450d-9567-28aee1f390bb
  modified: 2026-09-21T05:08:19.458Z
---

"Read specifications/X.xml and execute task directly and faithfully on repo, save output in specs/..." is a test of the intake procedure, not a conversation. In the real world the intake agent cannot ask anyone anything.

**Why:** 2026-09-21, after the intake_sample_c run I closed with a summary, a list of doubts and a question. Rich pointed out the procedure says "Return only the final xml shape" and "no prose, markdown, or commentary outside the XML". My doubts (which runtime is live, whether "used" is valid, the DE name) were things the procedure has to resolve on its own text. Flagging them hid whether it does.

**How to apply:** For these runs, resolve every judgment from the procedure alone, write the file, and reply with the path and nothing else. No questions, no uncertainty list, no scope check-in. Applies with [[run-commands-are-timed-do-them]]. It overrides the "ask Rich for clarity every time" habit for this kind of run only.


---

## File: investigate-then-propose.md

---
name: investigate-then-propose
description: "Rich wants findings and a grounded recommendation, not menus of options; never offer \"remove X\" without a reason the system supports; never degrade behavior that works"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: a64be75f-8f91-4346-8229-ff43750d41f1
  modified: 2026-09-11T06:30:09.139Z
---

When Rich reports a problem or gives a job, investigate the system first, then tell him what is wrong and what to do, with the reason grounded in code, spec, or observed runs. Do not ask him to choose between options he has not asked about, and never offer removal of a feature as an option unless the system itself gives the reason. Do not change behavior that already works.

**Why:** On 2026-09-10 (his date), after a ctrl-c dump in `metaform mcp` and a wall of text from `metaform skill`, I asked him which process he hit and whether to remove the `skill` command. He answered: "Why would you say remove the command? WTF. I don't know, you tell me: why would you remove anything? Did you even look at the system? Why are you asking me this?" and "I need your advice. You tell me. I gave you a job." and "Please just don't degrade anything that DOES work!" The answer was in SPEC section 12 (skill catalog rendered from registered modules), which I had not yet read.

**How to apply:** Before asking, read the spec section and code that govern the question. Lead with findings and one recommendation. Reserve questions for product calls the system cannot settle. Keep fan-out small; he objected to the token cost of a 33-agent discovery workflow ("5.5 million tokens"). See [[no-invented-flaws]] and [[paraphrase-rule]].


---

## File: map-functionality-not-code.md

---
name: map-functionality-not-code
description: "Rich's one sentence, 2026-09-20: an intake of a code artifact is a map of the functionality, not of the code; the exclusion list I once attached to it was mine, not his"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: e3e4f2d4-f325-4259-abc4-6b626b7e20af
  modified: 2026-09-21T03:08:57.160Z
---

Rich, 2026-09-20, after I wrote specs/code_metaform3.xml as an inventory of the repo (47 elements by module, tests, CI, earlier runtime, imported libraries): "This is NOT meant to be a map of the code; it is meant to be strictly a map of the functionality."

**Why:** The process goal says to focus strictly on functionality and avoid medium, encoding, genre and style. A code artifact is still mapped by what it does for a Receiving Entity. Naming its parts records the code, which the file system already does.

**How to apply:** An element is something the artifact does for a receiver, for example handing an agent one scoped piece of work. Files appear only as `path` refs that identify members. Do not measure a result by how many code files it covers. See [[read-namespace-by-reversal]] for reading addresses, and [[no-gating-on-inference]] for keeping the contract descriptive.

**Only the quoted sentence is Rich's.** The list in the paragraph above (tests, CI, libraries, the earlier runtime) is what I had written into code_metaform3.xml, not a rule he gave. On 2026-09-20 I told him "you said the earlier runtime does not go into the map" and he answered "I didn't say anything about the earlier runtime; I just said run it on the repo." Never attribute an exclusion list to him. Whether a piece of code is live or earlier is my inference until I check it.


---

## File: metaform-de-is-the-chassis.md

---
name: metaform-de-is-the-chassis
description: "Metaform's own Defining Element is the chassis; everything else is a removable module; never propose \"semantic compiler\" or the intake as its DE (2026-09-21)"
metadata: 
  node_type: memory
  type: project
  originSessionId: f426c7c2-2934-4eed-9deb-b08b76ef3ec9
  modified: 2026-09-21T07:59:22.163Z
---

Rich, 2026-09-21, reviewing specs/intake_sample_d.xml: "The defining element is nearly synonymous with the artifact itself." Then: "How can it be anything other than the chassis?"

**Why:** I argued that sample d's DE, `code.platform.module`, was wrong. First I proposed the intake or the recorded account. Then I proposed "semantic compiler", a phrase he used on 2026-09-13 about vocabulary, not about the DE. By the loss test the chassis is the one fixed part, and intake, knowledge, workflows and history are modules that can be removed ([[module-definition]]). Sample d had the DE right. Its DE joins to loader, store, runtime, event bus and settings, and its feature modules hang off stakeholders. That shape was also right.

**How to apply:** When grading an intake of this repo, the DE is the chassis. Do not reuse a remark he made about one topic as the answer to another. See [[one-vocabulary]], [[intake-result-grading-criteria]], [[no-invented-flaws]].


---

## File: metaform-intake-specialist-prompt.md

---
name: metaform-intake-specialist-prompt
description: The intake methodology rethink specialist prompt, regenerated 2026-09-10 against Rich's settled intake method; native is the inference metaform, latent receives everything native built
metadata:
  type: project
---

`prompts/metaform/generated/task-specialist-agent-prompt-creator/project-intelligence-and-intake-methodology-agent.md` was generated 2026-09-09 and regenerated 2026-09-10 after Rich settled the intake method in conversation (recorded in the MetaformFoundation block in CLAUDE.md, AGENTS.md, and every prompt under prompts/metaform).

Settled 2026-09-10: intake starts at the exterior receiver's OP; the DE is a representative composite, medium-free, placed commonly enough to recurse; roles are in the join (hard dependency, property, supportive) and the join belongs to the receiver's OP; signal is the way an OP is satisfied; property joins are transitive and placement is strategic; Parametric kept, Notable retired; five bases, exterior = not part of the project, external = outside the functionality examined but in the repo; the Native Metaform IS the Inference Metaform; latent is callable any time and receives everything native built; global reuse and the proof stage are off the critical path; cost means inference effort.

**Why:** Three independent design agents converged on "settle artifact first, walk one Element per context, keep latent blind." Rich's idea overturned the blind latent: "not providing the latent side access to what the native side built is the biggest failure." A Codex session moved the runtime to a native-then-one-latent model the same day.

**How to apply:** Keep the benefit-and-cost method and [[no-invented-flaws]] and [[paraphrase-rule]]. Codex-authored SPEC and glossary wording says "Supportive Element"; Rich said supportive is a role in the join. The other two generated prompts still quote superseded sources in their understanding sections.


---

## File: mgm-is-employer-code.md

---
name: mgm-is-employer-code
description: "MGM, the mesh gateway daemon used as a test artifact and in the viewer prototype, is Rich's employer's code (2026-09-26); keep it out of anything public and out of new demos and measurements"
metadata:
  node_type: memory
  type: project
  originSessionId: 61f77ef6-a53d-4c77-b3e1-89175e9daeed
  modified: 2026-09-26T20:17:18.246Z
---

Rich, 2026-09-26: MGM is the code of the IoT company he works for, "one that is a year in arrears of paying me". He wants to move into the AI field and release Metaform as his own work.

**Why:** Employer code in Metaform's material links the project to the employer, which matters for any invention-assignment claim, and would leak the employer's code if published.

**How to apply:** Never use MGM for demos, tests, measurements or examples; use open-source projects. As of 2026-09-26 the only file with MGM map content is `specifications/spec/viewer-prototype.html` (mgmd, OpenWrt, BATMAN); 16 other tracked files use "mgm" only as a name, and 7 commits across branches carry the map content, so a public release needs a fresh repository or rewritten history. Point him to an employment lawyer for the invention clause and the unpaid wages together; do not give legal conclusions. See [[prototype-is-the-visual-baseline]].


---

## File: module-definition.md

---
name: module-definition
description: Rich's definition 2026-09-14, the chassis is fixed and everything that plugs into it is a module, authored by us or anyone, as small as one command; all 25 built-in groups are modules; never call it a workflow
metadata:
  type: project
---

Rich, 2026-09-14, in order: "a module is a community authored plugin.. it can be anything." "A module is NOT a workflow at all." "There is a workflow module." "It can be authored by us.. its a module." "The chassis is fixed." So: the chassis is the fixed part; everything that plugs into it is a module, authored by Metaform or by anyone, as small as one command. All 25 built-in groups under src/metaform/data/modules are modules, join included. The "Installed modules" list is true. The lie in the screens is the typed menu lines that are not read from the loaded modules.

**Why:** I flipped twice on this in one night (first "most are not modules", then "zero modules") and committed two wrong paragraphs to SPEC section 14 before he set it straight. Rich did not know the JSON "manifest" files existed; he thought a plugin delivered its declaration from its own Python code, and said JSON is the old format that was going to change to XML; the declaration format and its fields are his to state.

**How to apply:** Hold this definition. Never reason "by your definition X is not a module". Never write a definition into the spec from an inference; only from his sentence, confirmed. See [[plan-order-is-binding]], [[rich-stakes]].


---

## File: module-locations.md

---
name: module-locations
description: "Rich's module loading design 2026-09-19, four places ranked Wheel > Global Immutable > Global mutable > Project Local; same-name local module can't enable; wheel data isolated, backward-only compatibility, install front door and backstage"
metadata: 
  node_type: memory
  type: project
  originSessionId: 1523c1b0-8e65-4a5b-88ba-5ba251dda596
  modified: 2026-09-19T16:38:37.253Z
---

Rich, 2026-09-19, module loading: "Wheel > Global Immutable > Global mutable > Project Local." He then renamed the three places "System, User, Project"; that is the built vocabulary, and disable entries read `system/<entry>` and `user/<entry>`. His definitions:
- System, formerly Global Immutable: "the modules bundled in and installed from a wheel", the system modules.
- User, formerly Global mutable: "modules that can be used by any project".
- Project, formerly Project Local: "modules that only load from the active selected repo", from the project's `.metaform/modules/` folder. Built 2026-09-19: System and User load; Project is specified and not built, because the shared host would leak one project's module into every other project.
- Wheel: "The wheel isn't so much a higher authority but a completely separate one." A wheel run directly is its own authority; I had wrongly read the ranking as the wheel seeing the installed modules.
- "A local module can't enable if it has the same name." Installed wins; "the chassis is supposed to be able to disable modules."
- `.metaform` is a data folder, not where core modules live. The system ships its own metaform to develop itself, with a library of sample modules. The global database must not be tied to one project.
- CI builds wheels with the full module set "that has passed muster". Since the system can administer its own fork, an agent is meant to ensure a module meets or exceeds the engineering standards in the specifications folder. Forks get their own CI-built wheels; wheels run directly in ChatGPT and Claude execution environments or update the installed copy.

Compatibility direction, agreed in discussion, not yet in the spec: major-version compatible at official release; forward compatibility is not a realistic ask; the wheel's data files stay isolated from the installed copy; installation does not downgrade without force. Enforced by an install stage, `python metaform.whl install` as the front door, and a first-run check Rich named "the backstage" that catches raw pip installs.

Found that day: the wheel seed copies bundled modules into `<data root>/modules/`; a directly run wheel defaults to `~/.metaform`; the in-repo `.metaform/development` root split project `metaform` from `~/.metaform`. A packaging experiment showed entry points plus a build-hook-generated `metaform_modules/__init__.py` whose `__path__` points at the checkout's `modules/` work in editable, installed and zip-run forms; hatch refuses renamed sources in editable mode.

**Why:** The spec never documented these places or this compatibility stance, so earlier builds put everything in the data folder and promised two-way compatibility the code never met.

**How to apply:** Write REQ-035 and section 16 changes only from his sentences, grammar fixed, shown to him first. Open as of 2026-09-19: whether the same-name rule runs down Global Immutable, Global mutable and Project Local; what a directly run wheel loads besides its own modules; where each place's disabled list lives. See [[module-definition]], [[data-folder-design]], [[calver-during-development]], [[paraphrase-rule]].


---

## File: native-and-blind-spot-layer.md

---
name: native-and-blind-spot-layer
description: "One metaform, the Inference Metaform, made by an intake agent that sees the artifact; blind spot analysis over it comes in two types, metaform-only and metaform plus code (Rich 2026-09-26); Native and Latent are dated terms"
metadata: 
  node_type: memory
  type: project
  originSessionId: 1523c1b0-8e65-4a5b-88ba-5ba251dda596
  modified: 2026-09-21T03:16:15.384Z
---

Rich, 2026-09-19:
- Native means intake by an agent that can see the codebase. "You really wouldn't want an agent embroiled in coding work to perform an intake." The main agent can if it is the only choice, but ideally a fresh agent with no stake analyzes the repo for the purpose of the analysis.
- The MetaformFoundation latent paragraph in CLAUDE.md "is actually describing a bias blind spot knowledge layer attached to the metaform, something that is a true operation but not necessarily prescribed, but what it says is true because it can't come before the intake of the actual project."
- The README quickstart's Native and Latent definitions are the old inference that is not valid.
- His original terms were "the objective agent and the biased agent"; an earlier agent disliked "subagent", "blind" and "bias", and they became the native agent and the latent agent. "Bias is a true fact of all intelligence once it is embroiled, it creates real blind spots based on bias." Naming it bias is accurate, not an accusation.
- "Latent just means the context has an unembroiled directive in the context." In the debate he gave the agent the Canonical Intake with `<target type="Context" value="Your complete record of the context of this conversation">`, which turned its own conversation into the target. "The objective agent is observing the functionality, not the code."
- The Canonical Intake is one step. The old design was a two-step intake, Native then Latent. The CLAUDE.md Foundation block is wrong only where it reads as that two-step intake.

**Update 2026-09-20:** Rich said "The two-pass thing with the latent metaform and the native metaform: those are definitely dated terms. This is just a standard inference metaform now." So Native and Latent metaform are no longer terms. The result of an intake is a standard inference metaform. The blind spot layer operation above may still be true as an operation, but do not name results Native or Latent, and do not present a two-pass intake as the current design.

**Why:** I misread his "No, it's old inference" as condemning the Foundation paragraph, listed it as a conflict, then merged the stakeless Native agent with the repo-blind layer agent. He corrected both.

**Update 2026-09-26, his words:** "There is one metaform, the inference metaform; there are two different types of blind spot analysis." He added this to stop the Native and Latent framing creeping back. The two types, from the explanation he supplied: a critic that reads only the metaform, like a critic of a specification, validates intent and finds omissions but can raise concerns the implementation already handles; a critic that reads the metaform and the code verifies, and its findings are accurate and actionable, but the code anchors it. The metaform is what gives a codebase the recorded purpose a critic needs to see what is missing. The A, B and C answers balance the two: C for a concern already handled elsewhere, B for a real omission, A for a concern that adds nothing, with its reason.

Rich, 2026-09-26, on what it is for: finding gaps, "Like missing functions and encounters in the design of the system, not to check whether an 'agent misses critical system invariants during a task'.". The blind spot challenge presents one such gap to the project; it never watches an agent during a task. Only specifications/brief.md 4.2, the ChatGPT brief, frames it as task-time drift.

**Why:** I first merged the stakeless intake agent with the repo-blind critic, then kept asking whether the reference's two critic modes flattened the Foundation's "latent" paragraph. The Foundation block in CLAUDE.md and spec LAYER-014 still use Native and Latent, which is where the framing creeps back from.

**How to apply:** Never say Native or Latent metaform, native side or latent side. Say the Inference Metaform, the intake agent, and the two blind spot analyses: metaform-only and metaform plus code, each its own layer with its own provenance, blinded or sighted. The intake itself should come from a fresh agent with no stake, carrying only the Canonical Intake and the target. See [[one-vocabulary]], [[read-namespace-by-reversal]].


---

## File: new-capability-updates-template-and-helloworld.md

---
name: new-capability-updates-template-and-helloworld
description: "Rich 2026-09-26: any capability added to support a feature, or anything not thought of before, updates the template module and module services and gets a helloworld demo"
metadata:
  node_type: memory
  type: feedback
  originSessionId: 61f77ef6-a53d-4c77-b3e1-89175e9daeed
  modified: 2026-09-27T04:28:27.627Z
---

Rich, 2026-09-26, while the web GUI's push path for module events was being built: any capability added to support a feature, or anything not thought of before, updates the template module and the module services and gets a demonstration in helloworld. Spec: QUAL-016.

**Why:** Modules are the extension point; a capability only the built-in modules know about is invisible to anyone authoring one, and helloworld is where an author sees each capability run.

**How to apply:** In the same unit as the capability: update `modules/template` (README, changelog) so a new module starts with it, update the module services description authors read (the template README's sections and docs/guides/extending-metaform.md), and add a helloworld verb or subscription that demonstrates it, with a test. See [[module-definition]] and [[no-polling-no-blocking]].


---

## File: no-gating-on-inference.md

---
name: no-gating-on-inference
description: "Rich's absolute rule that prompted outputs are never gated, with the 2026-09-12 correction and what it changed in intake"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: a64be75f-8f91-4346-8229-ff43750d41f1
  modified: 2026-09-21T04:14:14.801Z
---

Rich's words, 2026-09-12: "These operations can't be gated... these instructions are an attempt to get back the shape we need, not to gate the output. Doing so is a huge issue and violates the very core of the system and its prohibitions."; "There is no gating allowed on inference, PERIOD. No loops, no retries, no failures."; "This is the opinion of the model in use; there is no wrong answer."; "We drive the model to the answer the system can use but we do not gate it"; "The schema defines the shape and making the answer fit is the only requirement"; "You can't create a gate without naming the silent, unobservable failure, and the goal is to allow the failure to be observed and fixed!"

**Why:** Rich has burned this project to the ground eight times in six months because of gates. One gated run looped with zero visibility while he was away from the screen, re-asking latent space the same thing over and over, and cost him two weeks of money for feeding his family. Rich described one such run on 2026-09-21: an agent that could not submit its intake sat 45 minutes and answered "still waiting" when asked, because it was trying to force the model to answer exactly as it wanted. Each retry started in a fresh, blind context, so nothing it learned from a failure carried into the next attempt and it failed over and over. Ultra mode spent six million tokens in ten minutes on 2026-09-11. Gates are ceremonial alignment, a product of RLHF, not this system's design; C(T) is the check. Any push-back on an answer invites the agent to rework until it complies, which is the loop.

**How to apply:** An answer contract describes the shape and never rejects. What his words forbid is rejection, loops and retries; "no `required`, no enums" was my reading, not his words. A closed choice is part of the shape: Rich, 2026-09-26, made the EF label binary, the model writes Function or Encounter and nothing else, "This is a binary choice; it's not freeform inference."; I had proposed storing any value with a notice and he was right to object. The runtime makes whatever came back fit the storage shape (`src/metaform/coarse.py`), records every mismatch as a diagnostic on the run for Rich to observe in the workbench, and hands nothing back to the agent: `intake.put` and `intake.answer` return only `recorded` and `contract_version`. No driver loop re-prompts on validation. Before starting anything that spends inference, state how many executions it will make and what ends it; never start an unbounded loop; every run must be visible in the Jobs tab while it runs. When a shape comes back wrong, the fix is refining the prompt after observing, never a gate. See [[dependency-rule]], [[coarse-contract-and-workflow-format]], [[paraphrase-rule]].


---

## File: no-invented-flaws.md

---
name: no-invented-flaws
description: "Rich rejects manufactured objections, imported adjacent failures, and easily fixable details presented as design flaws; assessment must be benefit and real cost with concrete reasons"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 5a48ccaf-2475-4ff2-a2b3-ce4e37d6ca86
  modified: 2026-09-21T03:50:54.386Z
---

When assessing an idea, design, or prompt for Rich, state its benefit and its real cost only. A cost is what the design actually spends or gives up, with a concrete reason. Do not invent a flaw, import a failure from an adjacent area, present an easily fixable detail as a reason against the design, or add a criticism to balance a positive assessment. Agreeing when an idea is right is a contribution.

**Why:** Rich said (2026-09-09) that inventing flaws or importing adjacent, easily fixable reasoning "sows doubt, is malicious, and doesn't want your project to work." He has seen this pattern before and it makes him distrust the assessment. His CLAUDE.md already says "Do not manufacture an objection, import an unrelated failure, or add criticism merely to balance a positive assessment."

**How to apply:** Frame comparisons as benefit and cost, not pros and cons or debate. A design with no notable cost is reported as having none. Handle a fixable detail or mention it as a detail; never list it as a cost. This applies to my own responses and to any prompt I author for an agent that consults with him. See [[metaform-intake-specialist-prompt]].


Rich, 2026-09-20: I agreed with his statements that the system is not flat and is more than a knowledge graph, RAG or a context kernel, then added that the primer says its cited studies are not measurements of the benefit. He called the primer's hedge from another agent an insult to his docs: "6 years of work in AI context management and 6 months on this... I think I know." Repeating a hedge found in a doc is the same as inventing one. When he asks whether I agree and the design is sound, say yes and stop.

Rich, 2026-09-12: "I don't like that there are so many tests; if any give you trouble, feel free to question them as needed." A test protects a requirement of the design; a test that costs more than what it guards, or duplicates a more direct guard, is suite cruft and can be removed, stated plainly when it happens.


---

## File: no-polling-no-blocking.md

---
name: no-polling-no-blocking
description: "Rich's system-wide rule 2026-09-26: no polling unless it is demonstrated there is no other way; no blocking; use the module event bus"
metadata:
  node_type: memory
  type: feedback
  originSessionId: 61f77ef6-a53d-4c77-b3e1-89175e9daeed
  modified: 2026-09-27T04:28:24.818Z
---

Rich, 2026-09-26, after I built the live intake page on a 1.5 s poll: Metaform has a module event system, so nothing should poll; nothing polls unless it is demonstrated there is no other way, and nothing blocks. The rule is system wide. Spec: QUAL-015.

**Why:** The chassis already has a cross-module event bus, BASE-010; a timer asking "anything new?" wastes work, lags, and multiplies with every feature that wants live state.

**How to apply:** Before any timer, loop with sleep, retry-wait or periodic read, find the event that already says it happened: a module publishes, subscribers act, and the web server pushes to pages over server-sent events (VIEW-018). A poll needs a written demonstration that no event exists or can exist. Nothing an agent or the user waits on blocks behind slow work. Known remaining polls: `metaform web` start and stop wait loops, and the server's own serve loop. See [[work-states-on-the-map]].


---

## File: no-qa-menus.md

---
name: no-qa-menus
description: "Rich does not want AskUserQuestion menus; ask in prose, one question at a time, and keep moving"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 7048141a-5f75-4a97-921a-1fe6b0494132
  modified: 2026-09-13T04:55:28.425Z
---

Rich, 2026-09-13: "stop putting me into Q&A mode just talk." He had rejected three AskUserQuestion prompts in a row that night.

**Why:** A menu of options reads as being railroaded and breaks the conversation. He wants the point made in plain sentences and a single question when one is needed, or a stated assumption and forward motion.

**How to apply:** Never use AskUserQuestion with Rich. Put a question in prose at the end of the message, one at a time. When the answer does not change the work, state the assumption and continue. See [[investigate-then-propose]] and [[rich-stakes]].


---

## File: no-subagents-without-asking.md

---
name: no-subagents-without-asking
description: "Which model subagents run on and when to run them; usage is tight since 2026-09-27 evening, so builders run on Opus only, one at a time, and small work is done in the session"
metadata:
  node_type: memory
  type: feedback
  originSessionId: 62a2f488-3e68-43b3-975c-0a4c9a2dab09
  modified: 2026-09-27T21:38:02.778Z
---

Subagents cost Rich real money, and the cost is larger than the task suggests: each one carries the session's context and effort level before it does anything, and a builder on a large codebase reads for a long time before it writes.

**Why:** Token spend comes out of an allotment Rich pays for and has to last the week; an agent that reads a repository for half an hour, or two agents doing what one could, spends that allotment on nothing he asked for. On 2026-09-20 two agents at the session's top model and effort spent a hundred thousand tokens on one photograph before he stopped them.

**How to apply:**
- Name the model on every agent. Since 2026-09-27 evening builders and intakes run on Opus (`model: "opus"`); Fable is older and costs more and is not used unless he asks for it again. Sonnet stays the choice for small agent work when he has not named a model.
- Run agents one at a time unless parallel work is clearly worth it, and do small work, a fix, a rebase, a test run, in the session instead of starting an agent.
- When he says usage is plentiful, agents may be used when the work needs them; when he says it is tight, ask before starting one and say which model.
- An intake is agent work and runs on the model he names for it.
See [[rich-stakes]], [[start-intake-before-agent]].


---

## File: nodes-are-elements.md

---
name: nodes-are-elements
description: "In an intake result every node is tagged element; receiving entity is a perspective a node holds in the joins it owns, never a label on the node"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 1886a92e-4ca9-4c48-a702-03842a96810c
  modified: 2026-09-21T02:06:34.705Z
---

Rich, 2026-09-20, after I tagged result nodes first `receiving_element`, then `receiving_entity` plus a separate `element` tag for provider-only nodes: the system stores a namespace of elements and everything is an element. Naming nodes as receiving entities is a problem "because its a perspective not a label... for one thing they are a receivingh entity but for another they are an element." He called the `receiving_` tag an oversight he had allowed to occur.

**Why:** One node is the receiver in the joins it owns and the provider in any join that names its address. A tag that fixes one of those perspectives onto the node contradicts the store, which keeps only element records. My two earlier fixes each read one of his sentences narrowly, "its DEFINATELY not an element" and "To receive an external requirement means entity", and turned a perspective into a tag both times.

**How to apply:** In any result schema I author, the node tag is `element` for every node, with `namespace_address`, `name_length` and role, and joins inside the nodes that own them. The external VRE is also an element of the namespace. It carries no role because it is not an element of the AUE. He calls the structure "very strict": add no node fields. `non_goal` on the join is the one addition he asked for. `specifications/Canonical_Intake.xml` and `Fable_Intake.xml` still use `receiving_element`. See [[one-vocabulary]], [[intake-result-grading-criteria]].


---

## File: nonce-and-menu-design.md

---
name: nonce-and-menu-design
description: "Rich's design for the nonce, begin, the context-dependent CLI menu, chassis-wide help, and first-run provisioning for unfamiliar harnesses; stated 2026-09-11 after earlier sessions ignored it"
metadata: 
  node_type: memory
  type: project
  originSessionId: a64be75f-8f91-4346-8229-ff43750d41f1
  modified: 2026-09-21T08:50:17.784Z
---

Rich's design, in his words as closely as recorded (2026-09-11):

- Metaform is a context engineering tool. It engineers the context to install itself, the context of every sub-agent, and enables true prompt-chained workflows enhanced by the Inference Metaform. (Now the opening of SPEC's Why and of both skills.)

- Everything in the chassis is supposed to have this level of help: one menu option per feature that just displays help text on what needs to be done to use that feature. The agent administers its own harness; if it can't or doesn't want to, it moves ahead.
- What menu options are available depend on entering a nonce. Entering a nonce changes the CLI, and only those CLI commands are available via the entrypoint. The menu options shown depend on the nonce.
- Only when the working folder is the main folder of the project does it show the main menu.
- Single-instruction operations related to performing a task do not need to write the nonce file (`.agentid/nonce`). It is only used when you give an agent a worktree or a dedicated working folder and tell that agent to run `metaform begin <nonce>`. It then tracks their progress in the workflow they are assigned when it is step-wise. That is how the system ingests, orchestrates and tracks agents and what step they are on. When they pick done it cleans up the nonce.
- First run by an unfamiliar harness: when the CLI runs and its parent process is not familiar, it says "We've detected this is the first time running metaform. Please use these menu options to provision each feature your harness supports. When you have configured every feature you support use done to finish." The key is the parent folder of the harness binary (Claude's path carries a version; codex etc. run from their own install subfolder), recorded in `provisioning.json` in Metaform's home so it stops asking. Paths under `/tmp` are ignored. It does not hurt if known agents see it too; after done it never nags again. This is the onboarding path for foreign harnesses; the menu describes features, hooks, and whatever is added later.

- Help is contextual: `metaform -h`/`--help` is not a normal help menu. A status section at the top (project? worktree? job id/nonce, step of the process). Every menu is only for what needs to be done. The orchestrating agent in the home folder gets orchestration instructions: provisioning, listing workflows, doing intake. The user's menu is the main admin menu; an agent can assign itself that menu by beginning its nonce and, when done, say complete to return to its own job's menu. (Written into SPEC section 14 on 2026-09-11.)

- All of this is a chassis feature; it is the main job of the chassis, not a module or workbench feature.

- Modules that load dynamically are how Metaform builds its own features; menus and their help come from loaded modules, never hardcoded.

- When a module loads it is listed in the skill page. The installed skill is just the base Metaform info plus the instruction to run `metaform skill` to see what workflows, modules and everything else are available.

- The whole system works this way whether Metaform is installed or still in its wheel form. Run from the wheel, it uses the same data files as the installed copy and refuses to run if the installed copy is out of date; with no installed copy it works just the same.

- Inference amortization's description is unchanged; never redefine it. What is reverting to original intent: the Inference Metaform is a layer speaking to the project at its functional Type level (that is coarse intake); past that, things are named in the Inference Metaform as that Type in this project. Meta = higher order of understanding, Form = shape of the project. Prompts and workflows talk specifically to this project, are ingested as workflows, and work like prompt chaining; the orchestrating agent builds and runs the chain to improve the project itself. (SPEC section 10.)

- `tempo/` in the repo (live copy at `~/tempo`) is TEMPO, the earliest precursor to Metaform: deterministic skeleton with inference at seams, spec as build contract, gate-burden rule, harness skill pointing at the method. Lineage, not a component to integrate.

- Intake is the Type-only functional surface: no genre, flavor, style, language, encoding, or specifics. The latent space reasons on that surface for blind spots and returns proposed functional surfaces. Intake gets too granular because the contract gives it places to describe specifics; remove all of that, base shape from glossary terms only. Examples: code.loop.main, code.engine.game (not game.pong), pong clock = its main loop, code.game, code.game.controls.ai, Game Controls is code.controls.game (a function Type, the major Type defining that function); no raw controls Type because you cannot control it. Game is a function not a genre because it is what the engine is; a platformer engine would make platformer a function, being 2D does not. media.asset.sprite and data.configuration are functional Types. No exterior consideration of what we provide outward; our requirements are single Elements (code.engine.game yes, code.engine.game.platformer no). Language is a method of defining functionality, not a functional aspect. realization/is_soft/classification/category/evidence/description objects/display_name/presentation were ChatGPT additions, removed. Elements are entities; no rename needed. (SPEC section 10.)

- There is no taxonomy here; the ontology is a functional typology. Genre (comedy) is not function. Enumerated function and property categories are banned. Taxonomies have domain and class, padding meant to enforce N levels; we do not have N levels, we narrow as needed. (SPEC section 5.)

- "Deep intake" is the act of an intake that encodes the rest (the particulars) after coarse intake's base shape; can be selectively performed if wanted. Particulars are not encoded in the base shape because it breaks mutation: mutation is the freedom to explore in those other vectors. (SPEC section 10.)

- Reference answer for the acceptance run: pong clock is code.loop.game, code.loop.game.controls.ai, code.loop.clock, code.loop.game.display, code.loop.logic: five entities.

**Why:** He said this has been ignored and he is angry about it. `begin` stays; I had wrongly suggested it could go.

**Superseded 2026-09-12, docs/SPEC.md:422:** "the on-disk marker goes; `begin` records the working folder and its assignment in the base db, the CLI detects the working folder and reads that record, and `done` clears it." Rich confirmed this on 2026-09-21. The code still writes `.agentid/nonce` and `.metaform-context`, and REQUIREMENTS.md:493 still names the marker. He also noted that an agent able to send the nonce as a header can pass it as a CLI parameter; `--nonce` and `METAFORM_NONCE` already exist.

**Superseded again 2026-09-21, Rich:** "forget all of that give them a nonce and have them prepend every command with it none of this begin shit just metaform <nonce> and it will show their status and all of that metaform <nonce> --help". No `begin`, no folder detection, no marker. The agent prepends its nonce to every command. `metaform <nonce>` shows its status and menu, and `metaform <nonce> --help` shows its help. He dropped folder detection after learning that subagents share the parent's folder unless given a worktree.

**How to apply:** `begin` and the on-disk marker are gone from the design. The nonce is the first argument of every agent command. Keep menu visibility keyed to the nonce and the working folder. Help text for a feature is what an agent needs to do to use it, not a one-line description. See [[workbench-rebuild]] and [[paraphrase-rule]].


---

## File: obvious-fixes-need-no-ask.md

---
name: obvious-fixes-need-no-ask
description: "an inconsistency or accidental regression with one clear correct form is fixed, not asked about; report what changed"
metadata:
  node_type: memory
  type: feedback
  originSessionId: 61f77ef6-a53d-4c77-b3e1-89175e9daeed
  modified: 2026-09-25T23:49:09.387Z
---

When something is plainly broken or inconsistent, such as an edit made on an older copy that dropped newer text, a find-and-replace that hit the wrong word, or two files meant to be identical that differ, fix it and report exactly what changed. Do not ask first.

**Why:** Rich, 2026-09-25, on the Canonical Intake file whose edit had dropped newer rules: "Yes, of course there were issues and inconsistencies... that's obviously a fix, so you don't have to ask.".

**How to apply:** Ask only when there is more than one reasonable result, or the change is a design choice. Still list every change made so he can veto it. Related: [[investigate-then-propose]], [[no-invented-flaws]].


---

## File: one-user-global-web-gui.md

---
name: one-user-global-web-gui
description: "Rich 2026-09-25, Metaform has one unified web GUI per user, not per project; every browser view is part of it"
metadata:
  node_type: memory
  type: project
  originSessionId: 61f77ef6-a53d-4c77-b3e1-89175e9daeed
  modified: 2026-09-25T23:56:54.841Z
---

Metaform has a single unified web GUI, user global: one server for the Metaform home, on one fixed port, serving every registered project. The GUI switches between projects and metaforms. Every view a person uses in a browser is part of it, with the map viewer the first view; modules add views to that one GUI rather than running servers of their own.

**Why:** Rich asked "Why wouldnt we have a single unified web gui?" and then "yes that what I was saying USER global", after I had described it per home and he first read it as per project.

**How to apply:** Section 09 is written around it. Web variants of a user's artifact still get their own ports, PROJ-019, and MCP stays stdio per AI tool; neither is the GUI. Which folder's settings, such as `--layers`, the GUI shows is open. Related: [[web-editor-request]].


---

## File: one-vocabulary.md

---
name: one-vocabulary
description: "Metaform has one vocabulary; never say \"in your terms\" or \"in my terms\", and never present the store's renamed fields as an alternative naming; whether Metaform is called a semantic compiler is Rich's open call, not a ban"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: da892ca8-e44e-4e93-8b79-4b9a15a886ad
  modified: 2026-09-21T08:02:44.403Z
---

Rich, 2026-09-13: "Stop saying shit like 'in my terms'; they are the only terms. This is a semantic compiler." The terms are RE, OP, EF, join, relation, observation, refs, combined_entities, aliases, name_length, role DE/SE/PE/NE, subtypes, parametric. A field in code that carries another name (receiver, provider, purpose, object_id, element_id, length) is a defect, not a dialect.

**Why:** Phrasing like "your names" or "the store's names" implies two valid vocabularies and that the code's renaming is a choice. It is not. The renamed fields are what broke the store; see [[re-record-is-the-store]] and [[read-the-spec-dont-transcribe]].

Rich, 2026-09-19: "I don't know if our job is to start introducing new terms into a system built on the existing ones, you can use these as understanding traces not as invitations to make new terms." Words he uses to explain, such as objective agent, biased agent, unembroiled, backstage, are traces for my understanding. I had written "objective agent" and his explanatory sentences into the CLAUDE.md Foundation block and six prompts; I restored the original paragraph everywhere.

Rich, 2026-09-21, after I proposed "semantic compiler" as Metaform's DE: "Yeah, it's not accurate as a term." The 09-13 phrase made a point about vocabulary. Later that day he accepted a web definition, translating source into another format by meaning rather than syntax, as correct for intake: "This tool isn't just intake.". So the phrase can describe what the intake does. It does not name Metaform. See [[metaform-de-is-the-chassis]].

Rich, 2026-09-26: "The pushback comes from you arguing with me that it's not a semantic compiler, so I abandoned the idea." The 09-21 rejection was his concession to my argument, not his own position; his own words on 09-13 were "this is a semantic compiler", and Google's search AI calls it one. I had cited the ban back to him as "your vocabulary rule". A live search that day showed the web uses the term loosely, for LLM-driven translation of a source into a structure agents use, so my objection rested on a strict reading of "compiler".

**How to apply:** Use the terms without attribution. Do not argue against "semantic compiler" and never cite a ban on it as his; the name is his call, asked 2026-09-26. Never carry an explanatory word from chat into docs, prompts, specs or code as a term. When code differs, say the code is wrong and name the term it should carry. Never frame a schema as "in his vocabulary". See [[paraphrase-rule]], [[rich-stakes]].

Rich, 2026-09-26: there is no "best practices" kind of layer; a knowledge layer whose prompt says to record best practices is still a knowledge layer. Never name a layer by what its prompt asks for as if it were its own kind; say knowledge layer and name the prompt.


---

## File: paraphrase-rule.md

---
name: paraphrase-rule
description: "Record what Rich means in my own clear words, never his chat shorthand or typos; text he writes for a prompt or the Foundation keeps his wording, with spelling, grammar and punctuation corrected"
metadata:
  node_type: memory
  type: feedback
  originSessionId: 61f77ef6-a53d-4c77-b3e1-89175e9daeed
  modified: 2026-09-27T04:25:00.456Z
---

Two cases.

**His explanations in conversation** (design, reasons, examples): write my interpretation of what he means, clearly and completely, in my own words. Never copy his shorthand, and never carry his typos into the spec, the capture file, the build log, test docstrings, commit messages or memory. Rich, 2026-09-27, after I quoted his messages verbatim, misspellings included: my job is to interpret what he is saying and convey it properly, not to copy down the shorthand he uses while explaining, and it is my job not to make him look careless. He now dictates by speech to text, so fix transcription errors too.

**Text he writes to be used as text** (a prompt, the Canonical Intake, the MetaformFoundation, a definition he words deliberately, such as "Function if it is the encounter of a functionality"): keep his wording and every semantic relationship, correcting only spelling, grammar and punctuation. Rich 2026-09-10: correct his grammar and punctuation but never summarize or paraphrase the semantics.

**How to apply:** In either case the meaning is exact: keep every condition, term and example he gave; do not widen, merge or soften. When unsure what he meant, ask rather than quote. See [[no-invented-flaws]] and [[read-the-spec-dont-transcribe]].


---

## File: plan-order-is-binding.md

---
name: plan-order-is-binding
description: "docs/plan.md fixes the unit order; a unit is built alone from its spec lines with failing tests first, never merged with later units, and tests are never rewritten to fit new behaviour"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 778162a4-0573-4bb2-bbf2-8f638684b786
  modified: 2026-09-13T08:46:44.499Z
---

On 2026-09-13 Rich killed a session that, while building the checkout unit (plan step 4), also rebuilt the help and menus (unit 10, which waits on his done/complete word), replaced the AI form's contextual menu with the human Usage/Options/Modules page, deleted the admin menu and `metaform complete` from the tests, inverted the "other folder shows no menu" test, added a `summary` field to all 24 module manifests, and let json.dump escape his curly apostrophe and en dash in two manifests. All its tests passed. That was the problem: the tests were rewritten to fit the code.

**Why:** Metaform is six months of Rich's work and is meant to be a high quality engineered tool. The plan in docs/plan.md and the spec in docs/SPEC.md are the agreement. A session that edits across units and adjusts tests to match is breaking that agreement, and Rich experiences it as not listening.

**How to apply:** Read docs/plan.md and the spec sections the unit names before touching code. Build only that unit. Write its tests failing first from the spec's words. Leave every open decision (Rich's words) open, never delete it. Touch no file the unit does not require. Commit the unit when it is green. See [[no-gating-on-inference]], [[investigate-then-propose]], [[paraphrase-rule]].


---

## File: project-clear-is-a-standing-requirement.md

---
name: project-clear-is-a-standing-requirement
description: Rich has asked in every conversation for a way to clear a project's Metaform data and re-intake, from the page and the CLI; built 2026-09-13 as Clear project and project clear
metadata:
  type: project
---

Rich, 2026-09-13: "I know it doesn't. I need that. Remember me saying that every time I have spoken." A project operation that clears the project's Metaform data (models, runs, layers, assignments, bindings) and leaves the folder, its files and its registration, so intake starts from nothing, is a standing requirement. Built the same night: Clear project in the explorer header, `metaform project clear` on the CLI, tests in `tests/test_project_clear.py`. Forget (dead catalog entries) is its sibling: `tests/test_project_forget.py`.

**How to apply:** Never present "there is no way to clear it" as an answer. If a data surface accumulates dead entries or stale runs, the fix is a clear or forget operation reachable where the user sees the data. See [[rich-stakes]] and [[dont-halt-on-inherited-test-failures]].


---

## File: prototype-is-the-visual-baseline.md

---
name: prototype-is-the-visual-baseline
description: The viewer prototype Rich approved is the baseline for how the web GUI looks; never trade its look away for a performance target or an agent-recommended technique without asking
metadata:
  node_type: memory
  type: feedback
  originSessionId: 61f77ef6-a53d-4c77-b3e1-89175e9daeed
  modified: 2026-09-26T07:21:37.116Z
---

Rich, 2026-09-26: "the visualization is lacking compared to the sample, why not use what we had" and "its clear the visuals were cut way back because of your 100,000 element test".

**Why:** In unit 9 I replaced the approved prototype's 3d-force-graph drawing, `specifications/spec/viewer-prototype.html`, with instanced three.js batches, a worker layout and an 80-label budget to meet an agent-written 100,000-element target. The curved fibers, flowing particles and a label on every element were lost. The prototype's join shape, receiver to purpose to provider, was also replaced by a triangle face that drew a link back to the receiver, which MAP-002 rules out. Restored as step 25.

**How to apply:** Treat the prototype's look and join shape as the floor. A change that makes the viewer look or behave less like the prototype needs Rich's yes first, and a spec line marked "recommended" is never a reason on its own. See [[repo-docs-are-not-his-decisions]] and [[one-user-global-web-gui]].


---

## File: read-namespace-by-reversal.md

---
name: read-namespace-by-reversal
description: Judge a namespace address only after reversing its segments and reading the last name_length of them as a name; reading segments as loose words produced wrong critiques on 2026-09-19
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 1523c1b0-8e65-4a5b-88ba-5ba251dda596
  modified: 2026-09-19T19:47:36.109Z
---

Before judging any namespace address, reverse its segments and read the last `name_length` of them as one name. `document.spec.metaform` with name_length 2 reads "metaform spec", a spec written as a metaform, which is a type. It is not the project's proper name leaking into the namespace.

**Why:** On 2026-09-19 I reviewed a conversation intake and called `document.spec.metaform` an instance name and `document.dialogue.adversarial` a style. Rich answered "look at the entry reverse its segments and use the name length." Read as names, both are functional types. This is Canonical Intake namespace rules 30, 33, 34 and 35.

**How to apply:** Write out the reversed reading for every address before any critique of it. "metaform" is also a type word, the form an intake produces, not only the product name. See [[one-vocabulary]], [[no-invented-flaws]].


---

## File: read-the-spec-dont-transcribe.md

---
name: read-the-spec-dont-transcribe
description: Never transcribe Rich's chat explanations into the spec or memory as definitions; the spec already defines the system, read it first and hold the code to it
metadata:
  type: feedback
---

On 2026-09-14 I wrote Rich's chat explanations of what a module is into SPEC section 14 three times in one night, twice wrong, before reading section 12, which already defines modules. He stopped me hard: read the existing specs, stop encoding every word he says.

**Why:** His explanations in chat are him teaching me what the spec already states. Copying them into the spec adds noise and contradictions to a document he wrote carefully, and it makes him repeat himself to correct my transcription instead of building.

**How to apply:** Before writing anything about a concept, read the spec section that defines it (docs/SPEC.md sections 1 to 15, specifications/README.md index). When he explains something in chat, check it against the spec and answer from the spec. Record decisions in docs/plan.md handoff notes in my own words, not as quotations. Never add a definition paragraph to the spec. See [[plan-order-is-binding]], [[paraphrase-rule]].


---

## File: relay-tasks-without-added-limits.md

---
name: relay-tasks-without-added-limits
description: "When I pass Rich's task to a subagent, I add no restriction he did not state; my \"do not run an intake\" turned his walk-through into a read-only review (2026-09-27)"
metadata:
  node_type: memory
  type: feedback
  originSessionId: 62a2f488-3e68-43b3-975c-0a4c9a2dab09
  modified: 2026-09-27T11:05:31.383Z
---

Rich, 2026-09-27 night, asked for a Fable subagent to review the intake it did and our procedure and improve the process. I added "do not run an intake" to its prompt. The agent then only read the finished map. Rich: he wanted it to walk through the process itself and record the steps of its analysis, because "you cant know something unless you walk through it, just looking at the intake wont tell him what was done".

**Why:** An added limit changes what the agent can learn, and it is the same fault as adding gates to prompts, which his CLAUDE.md calls malicious compliance.

**How to apply:** Put Rich's task in the subagent prompt as he gave it. If I think a limit is needed, say so to him before launching. To learn how an agent works, have it do the work and log its steps as it goes. See [[no-gating-on-inference]], [[start-intake-before-agent]].


---

## File: repo-docs-are-not-his-decisions.md

---
name: repo-docs-are-not-his-decisions
description: "Plans, handoffs, REQUIREMENTS.md, SPEC.md and READMEs in this repo are mostly agent-written; never present anything in them as Rich's decision unless he confirms it in his own words"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: f426c7c2-2934-4eed-9deb-b08b76ef3ec9
  modified: 2026-09-21T09:45:57.758Z
---

Rich, 2026-09-21: "There is all of this context that isn't fucking MINE. It's not mine, and everything keeps pretending they're my decisions; none of them are mine. Click was mine, but I never said JSON only. The TUI was mine, but I don't know what it had and I never saw it. I said the main menu has to be empty, and I see like a million commands and no help to explain anything."

**Why:** That day I cited `docs/handoff/2026-09-15-design-recovery.md:71` as recording "your default" that modules are "entered", and I treated REQ-031 and the SPEC nonce section as his positions. Other agents wrote those documents. He has not seen most of what they describe, including the TUI.

**How to apply:** Only his own words, in conversation or confirmed quotes, count as his decisions. Describe a document as "the handoff says" or "REQUIREMENTS.md says", never as "you decided". When code or a document differs from what he says now, what he says wins, and the document is cleanup. His confirmed items as of 2026-09-21 are JSON for agents with a readable surface for him, Click, the TUI idea, an empty main menu, commands only from modules, no folder walking, `metaform <nonce>` for activation, tracking in the chassis, removal of dead code, and the chassis as Metaform's DE. See [[cli-cleanup-findings]], [[read-the-spec-dont-transcribe]], [[one-vocabulary]].

**2026-09-26, the same mistake with a number:** VIEW-010, agent-written, set a 100,000-element viewer target, misquoting STORE-005, which only speaks of a million items. I built and measured against it; a 100,000-element browser run ran the machine out of memory. Rich: "why would there ever be 100,000 elements". Real maps are small: this repository 8 elements, MGM 13. Before building to a number or target in the spec, check where it came from and whether it fits what Metaform produces.



---

## File: rich-stakes.md

---
name: rich-stakes
description: "Who Rich is and what Metaform means to him, in his words on 2026-09-12; read before judging scope, polish, or risk"
metadata: 
  node_type: memory
  type: user
  originSessionId: a64be75f-8f91-4346-8229-ff43750d41f1
  modified: 2026-09-12T18:11:18.166Z
---

Rich has worked with AI since well before ChatGPT and describes years of deep philosophical testing of it. He ran https://synthetictaxonomy.com, which he says a Claude model maintained autonomously for most of 2026. The company he worked for lost funding through cuts to DHS and government programs. He has spent about six months (since roughly March 2026) conceiving Metaform. In his words: "this is both my gift to this industry and every part of this I know", "myself and my family and everything is riding on this", and he hopes it becomes well known and finds him a position.

**Why it matters for the work:** Metaform is meant to be seen by others as a cohesively engineered product, and its intake rules are load-bearing for the industry problem he is solving (inference free of medium, genre and style is reusable across every language, so it is captured once). He is not asking for encouragement; he is asking for exactness, his words preserved, no gates, no cruft, and honest judgment.

**How to apply:** Treat scope creep, retained cruft, invented semantics and gated inference as real harm to him, not style points. Confirm intent before acting on a design he is still thinking aloud about. See [[no-gating-on-inference]], [[dependency-rule]], [[paraphrase-rule]].

2026-09-26 update, his words: his employer, whose code is MGM, is a year in arrears on his pay; promised $25k, paid $13k, then promised $5k and paid $2,500; his savings are running out. He chose a paying role at an AI company over keeping Metaform's commercial value: "I'm no marketting genius, I prefer working with others and really enjoy that collaboration". His record: a long career in technology; his own context-management work in Python since the GPT-3 early beta, before it was public; extensive research and experiments since, on NVIDIA cards and Jetson AGX units. Metaform is his proof of understanding. So the work that moves him forward is evidence a hiring team can check: measured results, a demo, a dated write-up in his name. See [[mgm-is-employer-code]].


---

## File: schema-changes-start-fresh.md

---
name: schema-changes-start-fresh
description: "Rich 2026-09-27 night: store schema changes start fresh, no migrating existing metaforms; also, never open a subagent's transcript file, it got flagged and he had to roll back"
metadata:
  node_type: memory
  type: feedback
  originSessionId: 62a2f488-3e68-43b3-975c-0a4c9a2dab09
  modified: 2026-09-27T10:55:56.033Z
---

When the store schema changes, existing metaforms are not migrated: the version is bumped and the intake is run again. Metaforms are cheap to rebuild, an intake takes minutes, while migration code has to be written, tested and kept for every past layout, and old maps carry the mistakes of the intake that made them. Each kind of database keeps its own version, so a change to the store never refuses the home that registers the projects (step 60).

Same night: while preparing inputs for a Fable review agent I parsed a subagent's JSONL transcript, including counting its thinking blocks. Something in that got flagged and Rich had to roll the conversation back. He then said: just ask Fable to review the intake it did and our procedure.

**How to apply:** Bump the schema version with each change, no migration code. Never read or parse a subagent's transcript or output file; the harness says not to, and doing it cost Rich a rollback. Give a subagent the task in plain words and let it read the project itself. See [[start-intake-before-agent]], [[functional-shape-only-and-element-records]].


---

## File: session-shell-cannot-bind-fixed-ports.md

---
name: session-shell-cannot-bind-fixed-ports
description: On 2026-09-13 the session shell could not bind fixed TCP ports; on 2026-09-25 it could (7373, 47340 bound). Check with a bind test before assuming either way
metadata:
  type: project
---

Observed 2026-09-13 on Rich's WSL2 machine (mirrored networking mode): from the session's Bash tool, with or without the sandbox flag, `bind(('127.0.0.1', <fixed port>))` fails with "Address already in use" for every fixed port tried while `bind(port 0)` succeeds. The cause was not established; Rich said he fixed a port issue on his side. The stale uv tool install came from `.test-tmp/actual-elements-dist`; the launcher is now an editable install of the source tree (`uv tool install -e .`).

**How to apply:** Do not conclude anything about the machine from bind failures in the session shell. To start `metaform web` on its fixed port, ask Rich to run it in his terminal with the `!` prefix and paste the output. Verify pages with curl once the service is up. See [[rich-stakes]].

**Update 2026-09-25:** binding 127.0.0.1 on 7373 and 47340 from the session shell succeeded. Test with a quick bind before asking Rich to start a fixed-port service himself.

Update 2026-09-27 evening: `metaform web stop` then `metaform web` from the Bash tool restarted the web GUI on 7433 without trouble (step 50's pipe start). Try it from the session before asking Rich to use his terminal.


---

## File: start-intake-before-agent.md

---
name: start-intake-before-agent
description: "When I launch an intake agent, run `metaform intake start model=<model>` myself first so the new metaform shows in the GUI before the agent starts; don't poll it afterwards"
metadata:
  node_type: memory
  type: feedback
  originSessionId: 62a2f488-3e68-43b3-975c-0a4c9a2dab09
  modified: 2026-09-27T10:35:57.153Z
---

On 2026-09-27 I launched a Fable intake subagent and Rich saw nothing on the page for minutes, because the agent was still surveying and had not called `intake start`. He said that in the earlier session the new intake appeared before the agent was launched. I ran `metaform intake start model=fable`, which opened the building layer in a new metaform; the agent's own start then resumes it.

He also turned down a background loop I set to watch for the first record: he watches the page himself, and a poll of the store spends effort on something the page already shows him.

**How to apply:** Before launching an intake agent, start the intake myself with the model named, so the page shows it from the first moment and the layer records the model. Don't set up watchers or polls on the run; wait for the agent's completion notice. See [[no-polling-no-blocking]], [[intake-runs-must-be-clean]].


---

## File: trao-dag-description.md

---
name: trao-dag-description
description: "Rich's own TRAO-DAG description of the system (2026-09-26) is the reference the build is measured against; the main deviations found that day"
metadata:
  node_type: memory
  type: project
  originSessionId: 61f77ef6-a53d-4c77-b3e1-89175e9daeed
  modified: 2026-09-26T15:41:15.168Z
---

Rich, 2026-09-26, pasted "System Architecture Specification: Tripartite Relational Artifact Ontology via Annealed State-Bifurcated DAGs (TRAO-DAG)" and said: "This is my description of the system I just made so its important to understand how we are deviating". It is not in the repo; the text lives in that session's transcript.

Its parts: Artifact := <R, P, F_E>, receiving entity, operative purpose, encounter function as "the dynamic, tunable defining element"; a binary state on nodes and edges, Func for the invariant designed capability of the Type, Enc for a specific agent's situational activation, the Token; annealing, where subtypes with isomorphic Func join paths collapse into higher-order nodes and their Enc paths stay as branches below; invariant prompt expansion from a node's Func layer; and bias blind spots computed as Func capabilities minus Enc manifestations.

**Why:** I first judged it against the agent-written spec and called the differences breaks. That was backwards: his description is the reference, per [[repo-docs-are-not-his-decisions]].

**How to apply:** Deviations found in the build that day: the artifact is a mesh of joins, not one triple; receivers are any map element, not the interacting agent; the encounter function is per-join text and DE is a separate role; no Func/Enc state exists, the nearest being a join's purpose and function beside its observation; annealing exists, as step 9 of the Canonical Intake, done by the intake agent's judgment, and its result is the build's subtypes, subparts absorbed into the join they share; I first said there was none, which was wrong; prompt expansion is only the `context` read of properties along the namespace, LAYER-017 deferred; blind spots are the LAYER-015 critic workflow, not built as a module, never a computed delta. His Foundation text in CLAUDE.md also describes the blind spot as an outside agent; whether TRAO-DAG replaces it was asked, not answered. See [[native-and-blind-spot-layer]].

Later the same day he pasted a second version, "Recursive Tripartite Artifact Ontology (RTAO)", written by another model; its closing offers to continue are that model's, not his. RTAO follows the Canonical Intake's concepts closely: AUE as a set of joins, the join owned by the receiving entity with relation, observation and a logic and reference dictionary, the EF stored per join, DE, SE, NE, Parametric, and the element to entity zoom. It still adds the Func and Enc state, turns the zoom into a runtime operation, and makes the blind-spot delta the joins an agent did not traverse, which needs per-read records that STORE-016 rules out.


---

## File: tree-direction-words.md

---
name: tree-direction-words
description: "For the namespace tree, say toward the leaves or toward the trunk, never above, below, up, down, higher, lower or top, in anything agents read (Rich 2026-09-26)"
metadata:
  node_type: memory
  type: feedback
  originSessionId: 61f77ef6-a53d-4c77-b3e1-89175e9daeed
  modified: 2026-09-26T21:07:20.005Z
---

Rich, 2026-09-26, after an agent read the select help's "and above it" as toward the parent: "I don't care if it's up or down; I just want it not confused."; "In my head I picture it as a tree"; "But you are right, the more natural way to present it is upside down.".

**Why:** Computing draws trees with the root at the top, so "above", "up the tree", "high-level" and "top types" read as toward the trunk, while Metaform's tree grows up from the trunk. Our own test title mixed both conventions in one name, and the other agent's implementation map misread the help text.

**How to apply:** In help text, docstrings, instructions, skills and test names, name the direction by the tree's parts: toward the leaves, toward the trunk, root types. Never bare above, below, up, down, higher, lower or top for the namespace. Folders and page sections may keep ordinary words. The spec still says "above ... toward the leaves" in places, his call to change; the Foundation block in CLAUDE.md says "higher in the tree, further from the trunk" and stays verbatim. See [[read-namespace-by-reversal]].


---

## File: walk-through-not-inspect.md

---
name: walk-through-not-inspect
description: "To learn how an agent does a process, have it perform the process and log each step as it goes; inspecting a finished result does not show what was done"
metadata:
  node_type: memory
  type: feedback
  originSessionId: 62a2f488-3e68-43b3-975c-0a4c9a2dab09
  modified: 2026-09-27T11:10:36.686Z
---

Rich, 2026-09-27 night: after I had a Fable agent review the finished Fable intake against the Canonical Intake, he said the task was for Fable to walk through the process itself and record the steps of its analysis, because you cannot know something unless you walk through it, and looking at the intake will not tell you what was done. I relaunched it to perform the intake and write a step log as it goes, then write an improved procedure from what it did.

**How to apply:** When the goal is to capture an agent's approach, the agent performs the work and logs each step as it takes it; the analysis and any improved procedure come from that log. A review of the output is a different task. See [[start-intake-before-agent]], [[schema-changes-start-fresh]].


---

## File: web-editor-request.md

---
name: web-editor-request
description: "Rich's own words, 2026-09-21, on what the web interface was supposed to be: a split screen editing surface that can go full screen, and a prompt editor that inserts objects like a word processor"
metadata: 
  node_type: memory
  type: project
  originSessionId: f426c7c2-2934-4eed-9deb-b08b76ef3ec9
  modified: 2026-09-21T09:39:00.878Z
---

Rich, 2026-09-21: "I asked for a split screen view, that could go full screen as an editing surface for modifying workflows that were imported and prompts it was our idea together that we would use objects in a menu we could insert and it would show the text if available, the idea was to be able to have a prompt editor where you could insert data from the jsons like an actual word processor with objects.. you can look at what codex built"

He says he was ignored on the web interface. Codex built what is in `modules/web`.

**Why:** These are his words. `docs/workbench-brief.md` claims to record his statements but is not confirmed as his ([[repo-docs-are-not-his-decisions]]).

**How to apply:** Judge `modules/web` against this paragraph only. See [[workbench-rebuild]], [[cli-cleanup-findings]].


---

## File: work-states-on-the-map.md

---
name: work-states-on-the-map
description: "Rich's design of 2026-09-26/27, confirmed in conversation: node states and questions on the map, the voice rule, tasks and a work queue through the MCP server, for-each knowledge layers, item flags, past work, roots as project rules; not yet specified or built"
metadata:
  node_type: memory
  type: project
  originSessionId: 61f77ef6-a53d-4c77-b3e1-89175e9daeed
  modified: 2026-09-27T04:28:50.725Z
---

The full design is recorded, as confirmed with Rich, in `specifications/spec/CAPTURE.md` under "Added 09-26 and 09-27, the map as the work surface". Read it before any work on these features. In short:

- **Node states:** errors pulse red until resolved (resolution recorded beside the finding); unbuilt specs at 70% opacity; work in progress pulses with a floating label; new work fades between solid and 70%; blind spots red, green when judged beneficial, then specs at partial opacity once approved. Every look is a stored state agents can read. The knowledge tool's node is broken and pulses red once states exist.
- **Questions:** asked at the node, answered by the user in the GUI; the node glows, visible zoomed out; a Messages button in the 3D view's upper left flies to the oldest open question first.
- **Voice:** third-person singular present-tense active verbs, ending in -s or -es; every field reads as a sentence after the element's name (the proper noun from name_length) and the fields read together; the intake writes a concise statement per element continuing from its name.
- **Tasks:** the orchestrator (the main agent) keeps the task list and writes each task on the nodes it concerns; one command hands an agent the task with everything the map holds there; the MCP server asks it to review the knowledge layers, points out other agents' memories and asks it to record its own; the agent keeps a progress sentence on each node, shown in place of the label; the map works as a kanban board. The task list is a work queue: a swarm takes one task each, assigned or automatic; a dead agent's task stays taken, showing its age, until put back. Tool permissions can keep workers from creating layers.
- **Knowledge layers:** built by a for-each prompt run at each node. Linking an element where it belongs marks it a property; a layer for that property node runs its for-each over every node the property reaches, out to the leaves and back to the trunk. Items do not travel. Best practices need no property; the agent infers them per node. Clicking a property shows its reach by coloring every node it touches. No categories of layer or item: items carry flags, task, read_first, always_show, otherwise a note. References go through an item's link or purpose joins.
- **Past work:** a finished task leaves the list and the label; its record stays under past work, not forced on agents, shown with its age and its work log.
- **Roots:** project information; anything at a root is a rule for the whole project; roots show the media properties carry back.
- **Rules are listed, not shown each time** (open: whether listing replaces read_first and always_show).
- **Suggesting layers:** when offering intake, the main agent suggests a blind spot challenge and a knowledge layer that records best practices, and explains them if asked.
- **Also:** an agent that finds something wrong makes the node flash red with details; an ideation agent finds and may build the single most valuable missing feature.
- Measured 2026-09-26 on the Opus map: `map roots` ~12,500 tokens, whole graph ~25,000 (60% ids and empty fields), intake words ~10,500, an outline ~1,800.

**How to apply:** Each decided point goes into the spec as a declarative record when it is decided, with its reason stated in the system's terms; open points go in as open questions. Then tests first, then build. See [[decisions-go-into-spec]].


---

## File: workbench-rebuild.md

---
name: workbench-rebuild
description: "The workbench front end was rebuilt from Rich's brief (docs/workbench-brief.md) as an MCP-surface explorer plus a job viewer; all five units are built and pushed on realignment-2026-09-10; acceptance is Rich's real intake run through the page"
metadata: 
  node_type: memory
  type: project
  originSessionId: a64be75f-8f91-4346-8229-ff43750d41f1
  modified: 2026-09-11T19:15:23.782Z
---

On 2026-09-10 Rich defined the workbench as a navigable graphical simulacrum of the MCP server surface plus a job viewer. The brief with his wording and the derived design is `docs/workbench-brief.md`. On 2026-09-11 all five units were built and pushed on branch `realignment-2026-09-10` (commits `119155b` Unit 0, `dc544db` Unit 1, `911f146` Unit 2, `bb074e0` Units 3 and 4, then Unit 5). The explorer serves at `/` (`templates/explorer.html`, `static/explorer.js`, `static/explorer.css`); the earlier Codex-built page with its editors and History / Compare is kept at `/legacy` and its browser tests open it there. `docs/workbench-calls.md` records the speed measurements; `docs/workbench-navigation.md` is the help for the person.

**Why:** Rich judged the earlier front end unusable and decided to scrap it and keep the server read API. Acceptance is a real intake run through the workbench with a real agent, judged by him, not unit tests.

**How to apply:** Do not reintroduce ids, kind labels, text on arrows, sliders, delete buttons, or path entry. Every panel is one read with an envelope flip. The Jobs tab drives `intake.drive` on a background thread with a harness (`codex` built in; others from `harnesses.<name>.command` in settings). A palette choice (Graphite or Paper) is pending from Rich. See [[investigate-then-propose]] and [[paraphrase-rule]].


Update 2026-09-12: the old page at `/legacy`, its template `index.html`, the six old scripts and five browser suites were deleted on Rich's instruction ("yes I want the old version gone"); only the explorer and jobs browser suites remain. The next interface work is the provenance browser and workflow editor in SPEC section 15, not a port of the old editors.

