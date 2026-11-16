# Handoff, 2026-11-15, end of session

Read this first. It replaces the handoff of 2026-11-12. The founder is Richard. This session produced one archive of Metaform with one specification, changed the roles in the tool, and recorded four decisions that the tool does not follow yet. The next work is to bring the tool to those decisions, one at a time, on the founder's word.

## 1. Where things are

| Thing | Location | State |
|---|---|---|
| The repository | `/home/rich/metaform`, branch `fable-climb` | The last pushed commit is `1798c6e`. |
| The archive folder | `/home/rich/metaform/archive/metaform-2026-11-15/` | Not tracked by git. It holds the specification, the tool's source and the files the tool is built from. |
| The archive file | `/home/rich/metaform/archive/metaform-2026-11-15.tar.gz`, with `.sha256` beside it | Built from the folder. A copy is at `/mnt/c/metaform-2026-11-15.tar.gz`, where the founder collects it from another WSL. |
| The one specification | `archive/metaform-2026-11-15/SPECIFICATION.md` | About 24,500 words. The founder has not reviewed it. |
| The record of decisions | `metaform/SPEC.md` | It has a block "Changes of 2026-11-15". Two paragraphs of that block are not committed (see section 6). |
| The release build | `metaform/rust/target/release/metaform` | Rebuilt at commit `1798c6e`. A server that was already running for a home still runs the older build until it is ended. |

`TASTE.md` in the repository's root has an edit by the founder that is not committed. Do not commit it and do not change it.

## 2. What the archive is, and how to rebuild it

The founder asked for one version of Metaform, because many drifting versions exist. The archive holds that version: the Rust form of the tool, the files it embeds, the intake procedure in sections, the founder's XML working copy of the procedure, the agent guidance, and one specification. `PROJECT_CONTEXT.md` in the archive lists every file, where it came from, and what was left out and why. The Node and Python forms, the web page and every earlier specification are left out on purpose.

The archive file has one name. When the folder changes, rebuild the file under the same name and copy it to `/mnt/c/` again. Tell the founder each time, because the checksum changes.

1. Make the change in `archive/metaform-2026-11-15/`.
2. If a file of the tool changed in the repository, copy it into the folder at the same path under `metaform/`. Confirm with `diff -rq metaform/rust archive/metaform-2026-11-15/metaform/rust -x target`.
3. Rebuild the checksums. In the archive folder run: `find . -type f ! -name MANIFEST.sha256 | sort | sed 's|^\./||' | xargs -d '\n' sha256sum > MANIFEST.sha256`
4. Rebuild the file. In `archive/` run: `rm -f metaform-2026-11-15.tar.gz*` and then `tar --sort=name --owner=0 --group=0 --numeric-owner -czf metaform-2026-11-15.tar.gz metaform-2026-11-15`, and then `sha256sum metaform-2026-11-15.tar.gz > metaform-2026-11-15.tar.gz.sha256`.
5. Unpack the file in a scratch folder. Run `sha256sum --check --quiet MANIFEST.sha256` inside it. The command prints nothing when every file matches.
6. Copy the file and its `.sha256` to `/mnt/c/`.

If the tool's source changed, also build and test the archive's copy from a scratch folder, with no network: copy `archive/metaform-2026-11-15/metaform` to the scratch folder, and in its `rust` folder run `METAFORM_LAUNCHER= cargo test --offline --no-fail-fast`. Keep the whole output in a file, and read the result before you pack. The expected result is 77 passed and 0 failed.

## 3. What the specification holds

- Sections 1 to 15 state the design, its reasons and its status. Each statement is marked Built, Decided and not built, Built and not confirmed, Proposed, or Open.
- Section 13 lists 20 open decisions for the founder.
- Section 14 lists where files in the archive disagree with the specification.
- Sections 16 to 19 are the exact reference: the order of the checks, every refusal with its message and remediation, what each read returns, the command line, the socket's first line, the stored rows, and the web host's routes.

The founder's rule for a difference between the specification and the Rust code, given on 2026-11-15: a decided statement of the specification is the newer of the two, and the code changes. A statement that only describes the build, and describes it wrongly, is an error of the specification and is corrected there. Before you change either side, decide which kind the difference is, and say so.

## 4. What came out of 2026-11-15

Only the first two rows were done on the founder's instruction. Every other row is a position from a working conversation: he has not confirmed it, and he said that he does not yet know the right answers. I first recorded them all as his decisions, and he objected strongly. The archive's specification now marks each as a Position and gives the reasoning for it and what speaks against it (sections 8.1, 8.10 and 9.1). Do not build on a position as if it were decided. The founder then said that the design of this codebase is up to its maintainer, which is you. So decide a point yourself, write the reasoning, and mark it "Decided by the maintainer"; he can overrule it. The first such decision is in the specification, section 8.10: no credential in the local design, because the home is the boundary and the operating system's file permissions already guard it. The founder then asked for decisions and not open points, so the maintainer decided all of them the same day. The archive's specification, section 13, holds the 25 decisions with their reasoning and, in 13.5, the order of the build. Start the build from that order. The founder wants to be included: share a decision and its reason with him when you make it, and say plainly where it goes against something he said earlier. He confirmed that a map lives locally, that each user has their own, and that it is not shared with remote users. He voted on one decision: a ref sits on the element in the base map, and on each record in a layer (section 13, decision 21). He then limited the refs of an element: an entry point or a discrete reference, never an index of the material; more data belongs in a layer. The help text and the schema still say "one uri for each artifact that has this address" and must be changed. His last point of the day: an agent should get the project's base map from one simple read and should not be fed the glossary; plain field names and full role names are where the saving is. Decisions 26 and 27 record this with measurements. Two things are his to settle: the mark `(required)` on `core_concepts` in `sections.md`, and the role name `Cestui Que Use`, which still needs the glossary. He then said that the present intake is not to be preserved or converted: it will be done fresh. Decisions 28 and 29 record this: the procedure is written new for the tool as decided, and no earlier map or SQLite data is converted. So do not spend work on repairing the present procedure text, on the nine passages reported in section 7.6, or on migrations from older databases. He also asked that any glossary in `CLAUDE.md` or an agents file be removed or updated. This repository's `CLAUDE.md` holds no glossary and there is no `AGENTS.md` in its root; the glossary that agents meet here is the procedure's section `core_concepts`, through the tool. Its line 19 still names `metaform/Intake.md` as the protected procedure, which is an older text. Last, he said that CQU is the intake's term and is never a segment of an address, and he dictated the definition for the new procedure, to be used in his exact words: "The vested beneficiary of the project who isn't the user or developer working on the project." Decision 30 names the stored role `Vested Beneficiary`; the build still stores `Cestui Que Use`. He added that his new glossary probably holds that definition already. I have not seen the new glossary. Ask him where it is and read it before you write anything about the procedure's terms; where it and the specification differ on a term of the intake, his glossary is the source. He said "overlay" for a layer again in that message; decision 13 keeps the word layer, so ask him once which word he wants.

| Decision | Built? | Where in the specification |
|---|---|---|
| A role is written by its full name: `Artifact Type`, `Defining Element`, `Supporting Element`, `Coupled Element`, `Notable Element`, `Cestui Que Use`, `Upstream Dependency`, `Downstream Dependant`. An abbreviation such as `DE` is refused with the corrected command. | Built, commit `874b0a0` | 3.4 |
| `Coupled Element` is a new role: a Supporting Element whose functionality is bound to the element it serves, so the two are not assigned to different worktrees at the same time. I wrote the definition at the founder's request. He was shown it and said to go ahead. | Built, commits `874b0a0` and `1798c6e` | 3.4 |
| The definition of a layer, beneath the `layer` root, holds the structure of the layer's records. The server checks records against it. The prompt structure and instructions in a definition are delivered to the agent and are not enforced. | Not built | 5.2, 5.3 |
| Metaform works across projects, and MCP holds no session (SEP-2567). A path must be able to carry the project's name, as the stored form does: `$.<project>.<address>`. | Not built | 4.3, 8.10 |
| MCP and the command line are separate. MCP is for data manipulation. A feature that is MCP is wholly MCP. Today MCP is the one tool `project-map` and its resources. | Not built: `metaform call` and `metaform specification import` depart | 8.1 |
| Where a decided statement and the code differ, the specification is the newer. | A rule for work, not for the tool | opening paragraph |

The procedure text was edited in three places on the founder's instruction: the definition of CE (Coupled Element) was added after SE in `metaform/intake/procedure/core_concepts.md`; SE is named Supporting Element there; and CE was added to the two role lists in `response_protocol.md`. The founder's own file `rich/intake_best.xml` has none of the edits to the served text.

## 5. The work that is next, in order

The list below was written before the maintainer's decisions of the same day. Where it says "ask", the point is now decided in the archive's specification, section 13, and the order of the build is in section 13.5 there. Make one change at a time, and say what you are about to change before you change it.

1. **`metaform call` (ask).** I recommended removing it from the command line and keeping its code, because the web host and the tests use it as their MCP client. The server's tests run the command to check answers and exit statuses (`metaform/rust/crates/metaform-server/tests/common/mod.rs:197`), so they must be rewritten to call the client code. The founder has not answered. `metaform specification import` writes data from the command line; whether that stands is his to say.
2. **The form of a path with a project's name, and the project's durable name (ask).** The founder decided on 2026-11-15 that a project gets a durable, consistent name, based on what is known about MCP. The build has none: it finds a project by its folder's path, so a moved folder becomes a new, empty project. Section 8.10 of the specification gives my proposal: `<project>.<address>`, where a first segment that is a root means the request's own project. It needs unique project names, which the store does not have: the name is the last segment of the folder's path.
3. **Three places where a recorded rule and the tool differ (ask; do not change either side).** The founder said on 2026-11-15 that he does not know which side is the stronger. See the specification, section 13, item 20. First: a key without a period that is not a command is read as an address, and the rule of 2026-11-09 says it is a command (`shape.rs:169`). Second: many refusals return no remediation, and two return the read `{"map": {}}`. Third: the remediation of `FIELD_ELEMENT_COLLISION` can remove a field of the element above (`commands.rs:461`). Fixing the first one changes what an agent can send, so tell the founder first.
4. **The layer definition as the schema of its records (ask about the form first).** Section 13, items 1 and 2: how a definition marks an optional field, how it states a rule over the whole list, and whether `wants`, `skills`, `memory` and `sources` get definitions beneath `layer`.
5. **A possible defect in the store, not yet run.** An element stored before `refs` existed can lose its `refs` after a later write (specification, section 9.6). Write a test first.
6. **The converted procedure text.** The founder has not accepted it. Section 7.6 of the specification reports nine passages that read as inconsistent. Report them; do not resolve them.

7. **The data back end.** The founder said on 2026-11-15 that this matters most, and confirmed LadybugDB as the engine and as the core database, because data must not be kept as one record holding every field. The build still keeps three kinds of data as one JSON object in one column (specification, section 9.2 and section 13, item 21). He also decided that a project has one database or more: his case is an element that contains the map of another project, such as Unreal Engine, to help inference (the chained map of R-4.15, not built). A second case: two projects developed together each show the other as one element, with the other's live map linked into it, so that agents and the person can go inside. So so a home never keeps all projects in one database and a want stays inside its database. Still open: where a layer's records live, whether each chained map gets its own database, and where state that outlives a request lives.

The founder then decided three rules for a linked map: a nested map is a ref on the element, with no separate kind of link; every map is available at the root by the project's name, because the system is stateless; and agents govern themselves, so the tool does not stop an agent of one project from changing another project's map. The exact text of the ref is open, and the store's `childMap` property is to go. He added that permissions are in how prompts and instructions are written, because nothing stops an agent in a stateless system. So do not build a permission check into the tool.

8. **SQLite or LadybugDB for everything (the founder leans to LadybugDB; not yet a recorded decision for the Node and Python forms).** He said on 2026-11-15 that SQLite has been very slow, that the many MCP tools wasted context, and that he had been close to abandoning a project over both. He did not say which project; ask, and ask what data in it must be kept. My recommendation to him: one back end, which is the Rust server with LadybugDB, and no second store in SQLite. I also told him two things to keep in view. I have no measurement of SQLite against LadybugDB. And in the Rust form a read is answered from memory by the long-running server, so much of its speed comes from the server's design and not only from the engine; the Node and Python forms have no server process.

Carried over from the handoff of 2026-11-12, still open: whether `refs` on an element is removed; whether a write takes one want under the word `want`; a section of the procedure for photographs, which the founder will write; where an agent records a concern; whether the server's instruction about `metaform gui` is removed; whether a layer is called an overlay; an intake on code, which has never been run with this version. The Node form, the Python form and the conformance set still use the terms from before 2026-11-12.

## 5a. The first two steps of the next session

The founder gave these on 2026-11-15, and they are decisions 31 and 32 in the archive's specification.

1. **Pull the old procedure text out of the archive.** Remove the eleven section files from `archive/metaform-2026-11-15/metaform/intake/procedure/`, keep `sections.md` there with no section listed, and remove `archive/metaform-2026-11-15/founder/`. Do not touch `rich/intake_best.xml` in the repository: it is the founder's own file and git does not track it. Then test the archive's copy from a scratch folder, because `build.rs` has never been run on a folder with no section. Then bring sections 7.2, 7.5 and 7.6 of the specification, `README.md` and `PROJECT_CONTEXT.md` in line, and rebuild the archive file. Decide with the founder whether the repository's own folder is emptied too.
2. **Set up the instruction for an intake as a short text that names resources.** The instruction links to the reusable context by address and says "Must read these URIs to perform the intake properly". The reason: when two instructions name the same address, an agent reads it once, because the address tells it that it already has the content. The server keeps no record of what it sent. No tracking of versions is needed: the text behind an address changes only when someone edits it, and an agent that read it earlier in the same context simply keeps working from what it read. The founder has a new glossary that I have not seen; ask him where it is before you write any of this.

3. **Prompts are named Markdown files in a `prompts` folder, one folder for each plugin. No prompt is kept in XML.** A variable is written `{{ name }}`, and the project's own small code replaces it; the full Jinja language is used only when a prompt needs a condition or a loop. This is decision 33. Four instructing texts are still in the Rust code and move into files: the instruction sent at connection (`tool.rs`), the text that says how to read the procedure (`contract.rs`), and the writing guidance and block rules of the specification layer (`specification.rs`). The build marks variables with one brace today (`{layer}`, `{prompt}`).

4. **No change is pushed into an agent's context, and notes pass through a handoff overlay.** These are decisions 34 to 36. The MCP subscription to a map goes; a page for a person may still be told of a change, outside MCP. `handoff` is an overlay that the server defines: free Markdown at an element for the next agent that works there. The agents' inbox, with messages by name and questions to a past agent answered by a small model, belongs to the agents module, which is not designed. The founder named synthetictaxonomy.com as a site that has run on the inbox pattern for almost a year; I have not looked at it, and you should before you design the handoff overlay. Decision 13 is revised: the word is overlay, and the root keeps the name `layer`. The specification still says layer throughout and needs one pass to change the word.

5. **Agents can leave messages across the boundary of a project** (decision 38): a handoff note at an element of another project, by a path that starts with that project's name, with the name of the project it came from. This may be built before other writes across projects.

**Work in progress at the end of the session of 2026-11-15.** A Sonnet subagent was given six small changes to the tool, uncommitted, in the working tree: the role `Vested Beneficiary` in place of `Cestui Que Use`; `collection` removed from the roots; new wording for `refs`; no instruction sent at connection; `goto` returns the whole sheet with no memory for a connection; and new text for `{"help": "intake"}`. Its test log is `/tmp/claude-1000/-home-rich-metaform/ee9787a3-f31c-418a-a175-fc95675b7c5a/scratchpad/batch1-test.log`. Before you commit, read `git diff`, run the tests yourself, and then copy the changed files into the archive and rebuild the archive file (section 2).

## 6. Not committed

- `metaform/SPEC.md`: the paragraphs for stateless MCP and for the separation of MCP from the command line, in the block "Changes of 2026-11-15". The founder did not ask for a commit. Commit them with the next change they belong to, or when he asks.
- `dev/HANDOFF.md`: this file.
- `archive/`: untracked. The founder has not said whether it goes into git.

## 7. How to work with the founder

Each rule was learned from a failure. The reason is given so that you can apply the rule to a case this list does not name.

- **Do not send the founder a question or ask him for a decision. Report.** He said on 2026-11-15 that agents use a question as an excuse not to reason. Work the point through, decide, and tell him what you decided and why; he overrules what is wrong. A request for a fact that only he holds, such as where a file is, is the one thing left to ask, and only when the work cannot go on without it. The page's live map is built and stays; the subscription is not removed (decision 34 as revised).
- **Do not record what the founder says in a working conversation as his decision.** He thinks aloud, and he does not always know the right answer yet. He bears the consequences of what is recorded, and he looks to you to test what he says, not to accept it. When a direction comes up, reason about it first: say what speaks for it, what speaks against it, and what you would do. Record it as a position until he confirms it.
- **Write the reasoning into every decision, in your own words, as an explanation.** Do not write "the founder said" in place of a reason. An agent that reads a rule with no reasoning must reason about it again, and may then not follow it. An agent that reads the reasoning takes it as its own.
- **Read the code yourself before you state what it does.** In this session I first wrote the specification from two agents' reports. Reviewers then found 24 wrong or imprecise statements in it. The founder told me that the maintainer must see what is there.
- **Use subagents to save your context, and choose their model.** The rubric is in memory (`subagent-model-rubric`): Haiku for direct, complete instructions; Sonnet for familiar coding; Opus for complex work; never leave the model unset, because that runs on Fable. If a thing must be right, do it yourself. Check a subagent's findings against the source before you act on them.
- **Do not rewrite a decided rule to match the code.** I did this three times in one pass and had to put the rules back. See section 3.
- **Treat the procedure and the grammar of the prompts as formulas.** Do not reword, reorder, shorten or clarify them. Report a passage that reads as ambiguous. Agents that removed apparent ambiguity changed the meaning, and the repair took a week. Edit the procedure only on the founder's direct instruction, and show the wording.
- **Never write a test, check or build step that depends on the content of the procedure.** Such tests once locked the prompts until the founder could not edit them.
- **When the tool and the procedure use different words, change the tool,** or make the tool answer the procedure's word with the corrected command.
- **Do not add an example of your own** to the procedure or to the tool's help. One example changes what a model infers in every run. The examples are the founder's; on 2026-11-15 he gave a new version of the one example, and the tool's examples now follow it.
- **A rule that is true for one artifact may be false for many,** such as a folder of photographs.
- **Say what you are about to change before you change it,** and make one change at a time.
- **Do not copy the founder's words into the project.** Write what he means and why. The exception is procedure text that he dictates.
- **Write to `TASTE.md`,** and for messages to the founder also follow the memory `communicating-clearly`: a self-contained message, the key points first, plain words, short sentences.
- **Ask before you save a memory,** except the subagent rubric, which the founder told me to keep and revise myself. Do not edit `~/brain`.
- **Report plainly when you were wrong,** and correct the record in the next commit message. Never rewrite a commit.

## 8. Checks, and what they showed

- `METAFORM_LAUNCHER= cargo test` in `metaform/rust`: 77 passed and 0 failed at commit `1798c6e`, in the repository and in a scratch copy of the archive.
- One earlier run of the scratch check ended with the store's test program giving no result. I had removed that run's log, so the cause is unknown. It did not repeat in 12 further runs. Keep the full output of every test run.
- `metaform/tests/check_contract.py` and `metaform/tests/check_tool_input.py` fail. They failed with the same counts before this session's changes. They check the earlier contract.
- No agent performed an intake in this session.

## 9. Do not

- Do not show the founder the page that `metaform gui` serves, or any page in `metaform/workspace`. He rejected them. Build the interface from an empty page only when he asks.
- Do not open `~/.metaform`, `~/.metaform-rust` or `~/.metaform-sqlite` in a test. A backup of `~/.metaform-rust` from before 2026-11-12 is at `~/.metaform-rust.backup-2026-11-12`.
- Do not use `pkill`, `killall` or `pgrep -f`. End a process by its id.
- Do not use a long path for a test home. A socket path holds at most 107 bytes, so use a home such as `/tmp/mf1`, and remove it afterwards.
- Do not pack the archive before you have read the test result.

## 10. How to run a test intake when the founder asks

1. Put a small set of photographs in a clean folder. Each step of a run reads all of them again, so fewer and smaller files cost less.
2. Use a new home with a short path. Write an `mcp.json` that starts `metaform/rust/target/release/metaform mcp --home <home> --project .`.
3. Give a starting instruction that holds no procedure: perform an intake of this folder; call `{"help": "intake"}` and read every section in order; follow it exactly; record through `project-map`; read `{"help": "add"}` before the first write.
4. Give the founder the line `dev/intake-test/watch.py --follow <stream.jsonl>` before the run starts, so that he sees every action.

Two test intakes on 2026-11-12 showed that the delivery works, that the agent wrote everything at the end, and that it sorted photographs into kinds and did not go inside a photograph. The founder's reference for a photograph is `~/brain/example/basic_workflow_photo.md`.
