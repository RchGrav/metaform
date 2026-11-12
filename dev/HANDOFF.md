# Handoff, 2026-11-12, end of day

Read this first. It replaces the handoff written on the morning of 2026-11-12. The founder is Richard. Usage is nearly spent for the week (resets Saturday 18:00): work in few steps, run no test intake unless the founder asks, and use Sonnet for mechanical work.

## The work, in order

1. **The intake procedure.** Get it to produce the map the founder expects for photos, then test it on code.
2. **The MCP server.** It now records what the procedure produces. Keep it in step with the founder's decisions.

The web interface is a separate job. Do not start it and do not show the founder any existing page (see "Do not").

## How to work with the founder

Each rule was learned from a failure. The reason is given so that you can apply it to a case this list does not name.

- **Treat the procedures and the grammar of the prompts as formulas.** Do not reword, reorder, shorten or clarify them. A passage that reads as ambiguous is contextual; report it and do not resolve it. Agents that removed apparent ambiguity changed the meaning, and the repair took a week.
- **Never write a test, check or build step that reads the content of the procedure.** In an earlier project such tests locked the prompts until the founder could not edit them.
- **When the tool and the procedure use different words, change the tool,** or make the tool answer the procedure's word with the corrected command. Do not ask the founder to change the procedure to fit the tool.
- **Do not add an example of your own** to the procedure or to the tool's help. One example changes what a model infers in every run.
- **A rule that is true for one artifact may be false for many.** Twice today a rule built for a code project (one uri for each element; one want for each wanted element) could not record a folder of photographs.
- **Say what you are about to change before you change it,** and make one change at a time. The founder stopped work more than once because an edit was made without notice.
- **Do not copy the founder's words into the project;** write what he means and why. The exception is procedure text he dictates: use his exact words there.
- **Ask before you save a memory.** Do not edit `~/brain`.
- **Report plainly when you were wrong,** and correct the record in the next commit message. Never rewrite a commit.

## What the tool is now (Rust form only)

All of this is built, tested (`cargo test` in `metaform/rust`: 77 passed) and pushed on branch `fable-climb`. `metaform/SPEC.md` has a block at the top, "Changes of 2026-11-12", that records each decision with its reason. Read it.

- **Roles:** `AT`, `DE`, `SE`, `NE`, `CQU`, `UD`, `DD`. A map may hold several `DE` elements. `AUE` is not a role.
- **`wants`** is an array on the receiving element. A want has `element` (the wanted element's address), `why`, `how`, `direction` (`send`, `receive`, `both`) and `ref` (the uri of the one artifact the want is about).
- **A want's key** within a receiving element is its `element` with its `ref`. An element may hold several wants on the same element, one for each artifact.
- **Refs are relative to the project folder,** which the chassis registry holds. An absolute path or `file://` uri inside the project is refused with the relative form.
- **The tool speaks plain words; the procedure keeps its terms.** A command that uses `dependencies`, `pe`, `provider`, `op`, `purpose`, `ef` or `ifd` is refused with the same command in the tool's words.
- **Every refusal returns a corrected command** where one exists.
- **Reads:** a plain read returns an element's own fields; `goto` returns the element, its `wants` and `wanted_by`; a key that starts with a period is a raw dump; `map` returns every address (the layers are under `layer`), each wanting pair once, and `defining`.
- **`{"help": "<command>"}`** answers in one piece from `metaform/tool-help.json`: what the command does, its fields, the founder's examples, and for `add` the want sentence with the grammar of `why` and `how` (from SPEC R-6.17).
- **The intake procedure is served in sections.** `metaform/intake/procedure/` holds one Markdown file for each section and `sections.md` (order, `(required)`, and `(when ...)` for a section that applies to one kind of artifact). `{"help": "intake"}` lists them; `{"help": "intake/<name>"}` returns one; each is also a resource. The server reads no file while it runs; the folder is compiled in by `build.rs`.

## The procedure text

- The served text is the founder's file of 2026-11-12 07:54 with its markup converted to Markdown by script. The conversion turned tag and attribute names into visible label words ("Rules:", "Examples of a CQU:", "valid", "invalid"). The founder has been told and has not reviewed the result.
- Two wording edits were made on the founder's direct instruction: the first sentence of the CQU definition in `core_concepts.md` ("The vested beneficiary who holds the interest in the artifact that isn't involved in the process of creating or improving it."), and "an AUE role" to "a role" in `response_protocol.md`.
- The founder's own working copy is `rich/intake_best.xml` (untracked). It has neither edit.

## What two test intakes through the real server showed

One fresh Sonnet agent each, 37 photos, about 110 seconds and $0.50 each. Transcripts and maps are in the scratch folder of the session; replay one with `dev/intake-test/watch.py <stream.jsonl>`.

- **The delivery works.** The agent read all eleven sections in order, read `{"help": "add"}`, used the tool's words, and wrote `why` and `how` that read correctly in the want sentence.
- **It writes at the end.** It opened all 37 photos in one batch and then made every write. Steps 3 and 6 of the procedure say to record as it goes.
- **It sorts photos into kinds** (portrait, scenery, close-up) and does not go inside a photograph. The founder's reference is `~/brain/example/basic_workflow_photo.md`: the artifact is the photograph, and its elements are its subject, setting, frame, vantage, light and so on, with the subject as the invariant.
- **One photo in `refs` for each element.** The agent followed two sentences in `response_protocol.md` ("Every element carries one uri..." and "State in the description how many members were observed") over the tool's help. Those runs were before `ref` moved into the want.
- **The CQU.** With the earlier CQU definition, Sonnet named a photo editor in 7 of 7 runs. The founder's ruling: the CQU is who the artifact is improved for, never who improves it; the editor is the same lazy answer as the developer. After the new first sentence, two runs named an influencer, a blogger and a portrait sitter.
- **Concerns had nowhere to go.** The agent found duplicates and a missing-captions concern and could only report them in its reply.

## Open, for the founder

- Whether `refs` on an element is removed, now that each want carries `ref`. The founder said refs there will not work.
- Whether a write takes one want at a time under the singular `want`.
- A photo-handling section for the procedure (the founder will write it; `sections.md` can mark it `(when the artifact is a photograph)`).
- Where an agent records a concern (missing, broken, exclude), and an artifact it has observed before its type is settled.
- Whether the server's connection instruction, which tells every agent about `metaform gui`, is removed.
- Whether R-6.28 (a layer is called an overlay) still stands; the founder said on 2026-11-12 that the root is `layer`.
- The want sentence says "requires" and its rule for `how` says "provider"; the tool says `wants` and `element`. The founder's example `how`, "Prepared mash data packets.", is a noun phrase and does not fit the rule.

## Not done

- The Node form, the Python form and the conformance set still use the old terms; the shared contract files no longer match them.
- `delete` removes every want on an element; it cannot remove one of several.
- No intake has been run on code.
- A home whose path is too long for a socket makes the server fail with only "Connection closed" on the agent's side.
- The web interface is not started. Its requirements are in `metaform/PROJECT_SPECIFICATION.md`, section 7.

## Do not

- Do not show the founder the page that `metaform gui` serves, or any page in `metaform/workspace`. He rejected them, and being shown one again angered him. Build the interface from an empty page only when he asks.
- Do not open `~/.metaform`, `~/.metaform-rust` or `~/.metaform-sqlite` in a test. A backup of `~/.metaform-rust` from before today's builds is at `~/.metaform-rust.backup-2026-11-12`.
- Do not use `pkill`, `killall` or `pgrep -f`. End a process by its id.
- Do not use a long path for a test home; a socket path holds at most 107 bytes.

## How to run a test intake when the founder asks

1. Put a small set of photos in a clean folder. Smaller and fewer photos cost less: every step of a run re-reads all of them.
2. Use a new home with a short path. Write an `mcp.json` that starts `metaform/rust/target/release/metaform mcp --home <home> --project .`.
3. The starting instruction holds no procedure: perform an intake of this folder; call `{"help": "intake"}` and read every section in order; follow it exactly; record through `project-map`; read `{"help": "add"}` before the first write.
4. Give the founder the `watch.py --follow` line before the run starts, or give him the two lines to run it himself in Claude Code so that he sees every action.
