# Fable climb: results

**Date:** 2026-11-09. **Branch:** `fable-climb`. **Prompt:** `dev/Fable_Climb.md`, with the owner's goal: the Rust, Node and Python forms complete and polished; Node and Python give agents the same form and store data as a structure of arrays; test intakes by Sonnet agents that report context waste; the workspace address shown and told to the user; a final polish of the graph workspace.

Each section says what was done, how it was checked, and what the check does not establish.

## 1. Baseline

Performed on `main` at `6ef3edf` before any change.

| Check | Result |
|---|---|
| `python3 metaform/tests/check_contract.py` | 30 passed |
| `python3 metaform/tests/check_tool_input.py` | 13 passed |
| `python3 tools/verify_bootstrap.py` | PASS |
| `cargo test` in `metaform/rust` | 52 passed, 0 failed |
| `cargo clippy --all-targets` | no warnings |

The Node harness and the workspace had no installed dependencies, so their tests were not performed at baseline.

## 2. The evaluation loop

The repository had no check that compared the forms, and no measure of what the tool delivers to an agent. Two were added.

- **`metaform/conformance/run.py` and `cases.json`.** 23 cases, 373 steps, performed through each form's stdio MCP server on a new home. The Rust form's answers are recorded; every form must repeat them, including the order of keys. It establishes equal answers on the recorded steps and nothing about other commands.
- **`metaform/conformance/replay.py` and `traces/`.** The commands of four real intake sessions (334 commands). Replaying them against a build gives the bytes that build would have delivered. It does not establish how an agent would behave with different answers.

## 3. Verified gaps in the Rust form, and fixes

Found by reading the first recorded answers (1 to 6), by four test intakes (7 to 11) and by the port agents' comparisons (12 to 14). Each has a test.

| # | Gap | Fix |
|---|---|---|
| 1 | Messages for a malformed command came from the schema validator: Rust type names, JSON pointer paths, and some pointed at the wrong problem | A hand-written shape check, `shape.rs`, in a fixed order; 34 rules, each with a test |
| 2 | The root accepted `technical_name`; the refusal's remediation was itself refused | Refused with a remediation that works |
| 3 | R-3.12 (`name` differs from `technical_name`) was not enforced | Enforced, then **withdrawn** (see 7) |
| 4 | Any text was accepted as a role | A written role is one of the four roles (R-3.13) |
| 5 | A refusal gave an empty remediation | `null` |
| 6 | A remediation removed a layer's stored records | The remediation gives the value as one record |
| 7 | The R-3.12 refusal made all four intake agents invent a name, where the intake procedure allows the standard term | Refusal withdrawn; the conflict is open as `SPEC.md` D-19 |
| 8 | A want to a missing address made an empty element that stayed after the want was removed | A deletion leaves no empty element (R-5.36) |
| 9 | The refusal of a second Definitive element offered to remove the existing Definitive role | The remediation gives the new element another role |
| 10 | The agent had no way to learn where a person sees the map | The server's instructions give the workspace address (R-5.37) |
| 11 | A home with a long path failed with `SUN_LEN`, repeated on each retry | Refused once, with the lengths and what to do |
| 12 | `{"wants": {}}` made an element named `wants` | Refused |
| 13 | Text or a number was accepted as a system layer's value | Refused; the remediation gives it as a list |
| 14 | In the SQLite forms, one command that removed an element and the empty element it wanted broke a foreign key | The store removes `wants` rows before element rows |

## 4. The Node and Python forms

Both are complete ports of the agent-facing tool, with no dependencies, on one SQLite store format (`metaform/docs/designs/sqlite-forms.md`): one narrow table for each field and each layer.

| Check | Node | Python |
|---|---|---|
| Conformance, 373 steps | 0 differences | 0 differences |
| Own tests: layout, two processes, ended process (SIGKILL), refused write, format marker | 5 passed | 5 passed |
| Generated commands compared with the Rust binary (the agents' own check, before the last Rust changes) | about 14,000, 0 differences | about 45,000 as raw text, 0 differences |
| A home written by both forms in turn | read the same through both | read the same through both |
| Replay of 334 intake commands | 206,858 bytes, equal to Rust | 206,858 bytes, equal to Rust |

Types: the Node form passes `tsc --strict` and the Python form passes `pyright`, both performed from a scratch folder, so neither is a project dependency. Not established: survival of power loss, and fairness of the write lock under heavy load (SQLite's lock is not first come, first served; the design document says so).

## 5. Test intakes

Four Sonnet agents performed `metaform/Intake.md` through one MCP connection each (`metaform/tools/session.py`) into the home `~/.metaform-climb`, and reported as test users.

| Target | Elements | Wants | Commands | Refused |
|---|---|---|---|---|
| This repository | 50 | 65 | 131 | 9 |
| `axum` 0.8.9 | 23 | 41 | 100 | 3 |
| `rmcp` 3.9.0 | 29 | 49 | 64 | 3 |
| `lbug` 0.22.3 | 21 | 30 | 39 | 1 |

All four named the same two wastes (the command repeated in every successful answer; the specification layer's rules in the first `goto`) and the same conflict (gap 7).

## 6. Hill climbing

One variable for each experiment. Evaluation: `replay.py --form rust` on the four traces, with the fixes of section 3 in place as the baseline.

| # | Hypothesis | Change | Bytes received | Decision |
|---|---|---|---|---|
| 0 | Baseline | | 302,384 | |
| 1 | The repeat of the command in a successful answer gives the agent nothing | A successful write answers `{"status": "ok"}` | 215,946 (−28.6%) | Kept (R-5.35). All tests passed unchanged. |
| 2 | A layer's rules are needed only when the agent writes that layer | `goto` gives one sentence that names the definition's address; the rules are at the definition | 206,858 (−4.2%) | Kept. Four tests asserted the old text and now read the rules at the definition. |

| 3 | At a layer's definition, the sheet holds the instruction twice | The sheet's `element` part leaves `instruction` out; `guidance` holds it | First `goto` at `layer.document.specification`: 2,720 bytes, down from 4,189. The traces are unchanged, because no first-round session went to a definition. | Kept. |

The replay holds the commands fixed, so it cannot show how an agent behaves with the smaller answers. Section 6a does.

## 6a. A second round of intakes, on the final build

Two new Sonnet agents performed the same briefs on `lbug` and `axum`, into the home `~/.metaform-climb2`. Their sessions are in `metaform/conformance/traces/round2/`.

| | `lbug` round 1 | `lbug` round 2 | `axum` round 1 | `axum` round 2 |
|---|---|---|---|---|
| Commands | 39 | 41 | 100 | 139 |
| Refused | 1 | 0 | 3 | 3 |
| Elements, wants | 21, 30 | 18, 24 | 23, 41 | 36, 56 |
| Bytes sent | 10,963 | 9,572 | 20,947 | 24,978 |
| Bytes received | 34,109 | 11,743 | 65,053 | 61,100 |
| Bytes received for each command | 875 | 286 | 651 | 440 |
| Bytes received from successful writes | not kept apart | 480 (32 writes) | not kept apart | 1,065 (71 writes) |

What this shows:
- Both agents finished every step of the procedure. Neither invented a name, and neither was refused for a name.
- A successful write now costs 15 bytes. In round 2 it is no longer a measurable part of what an agent receives.
- The second `axum` agent did more with about the same bytes: 39 more commands and a larger map. It read every element back with `goto` in its final proof (55 calls, 40,242 bytes), which the first agent did not do.

What it does not show: two sessions for each target are too few to separate the effect of the build from the difference between two agents.

What the second round found:
- **The pointer in `goto` did not keep the rules away.** Both agents followed "Before you write specification, goto layer.document.specification for its rules", received about 2.7 KB, and wrote no specification.
- **`{"status": "ok"}` does not say what an `update` did to existing wants.** Agents in both later rounds checked with a `goto` that an `update` adds to the wants and replaces only the one it names. This belongs in the tool's description, which is a protected file.
- **A role on a `downstream` element is accepted without comment,** and the procedure gives none. Every agent was unsure (section 8, item 5).
- **`DEPENDENCY_LOCK` names every element that still wants the target and gives the remediation for the first only.**

## 6b. Experiment 4: the wording of the pointer, tested with a third round

| # | Hypothesis | Change | Result | Decision |
|---|---|---|---|---|
| 4 | The pointer read as an invitation. A sentence that says when to read the rules keeps an agent from reading them early. | The `instructions` entry is "The rules for writing <layer> are at <address>. Read them only when you write <layer>." | Round 2 (old wording): 2 of 2 agents went to the layer's definition, and neither wrote the layer. Round 3 (new wording): 0 of 2 went. One round-3 agent sent `{"goto": "layer"}` (88 bytes received) to learn what the `layer` addresses in `map` are; it did not read the rules. The sentence is 148 bytes longer over the four first-round traces (207,006 against 206,858). | Kept, in all three forms. |

The third round, on the build with experiments 1 to 4 (`metaform/conformance/traces/round3/`):

| | `lbug` round 1 | `lbug` round 3 | `axum` round 1 | `axum` round 3 |
|---|---|---|---|---|
| Commands | 39 | 37 | 100 | 146 |
| Refused | 1 | 0 | 3 | 2 (both sent on purpose, to read the messages) |
| Elements, wants | 21, 30 | 22, 42 | 23, 41 | 37, 61 |
| Bytes sent | 10,963 | 14,394 | 20,947 | 28,887 |
| Bytes received | 34,109 | 7,346 | 65,053 | 23,234 |
| Bytes received for each command | 875 | 199 | 651 | 159 |

In round 3 both agents received fewer bytes than they sent, and both recorded larger maps than in round 1. Two sessions for each target in each round remain too few to separate the build from the agent; the direction is the same in all four later sessions.

**Most useful next experiments,** from both rounds: the wording of the pointer in `goto`; `goto` lists layers and memory with zero records; `map` lists the branch addresses and the `layer` addresses with the elements; `orphaned` returns whole records where intake needs addresses; a refusal's remediation repeats the whole command.

## 7. The graph workspace

The owner rejected the first page and gave a specification, `dev/gui_specification.md`. The page was built again to it. `metaform/workspace/ARCHITECTURE.md` says how it is built, what is real and what is simulated, and its limits.

- `metaform gui` prints the address, `http://127.0.0.1:4170/` or a free port when that one is in use. The server's instructions tell each agent to give its user this address. The page does not show its own address.
- One specification model feeds the graph, the outline, the element panels and the Markdown.
- Checked in Chrome through the Rust host, on the axum, rmcp, lbug and metaform maps:
  - First fit with and without side panels; depth (collapse all, expand all, one level, undo); categories (hide, isolate, restore); fit graph. Each change settled in about 800 ms with every element in view.
  - An edited name was stored by the server, shown on the graph, marked user-authored and recorded in the `review` layer.
  - Of two simulated proposals, one was accepted (stored, shown, recorded) and one rejected (listed as rejected, nothing written).
  - The Markdown preview opened from the top bar with the whole project.
  - Present mode, Element mode, the light theme and a 900-pixel window drew without overlap.
- Three defects were found by looking at the page and fixed: a first view with a left panel was never fitted; keyboard focus on the selected element restarted the slide on every redraw; the graph was not fitted again when the pane changed size.

First-time-user test, a Sonnet agent with no knowledge of the product, on the rmcp map:

| Build | Tasks answered | Usable without a manual |
|---|---|---|
| The rejected page | 4 of 6 | No |
| An intermediate build | 5 of 6 | No |
| This page, before the wording fixes | 9 of 9, all sure | No: proposals sat in a closed panel, and several labels were unclear |
| This page, as published on 2026-11-10 | 9 of 9, all sure | "Mostly yes" |

The last test asked for proposals in 3 actions; the one before needed 7. It still could not tell the meaning of the role names, the category names and the bottom strip's Records without their tooltips, and it found labels too small to read at 44% zoom.

Not established: the clipboard copy and the file download (the browser under test has no clipboard or downloads folder to inspect), behavior in Firefox or Safari, and maps above 200 elements in a browser.

## 7a. The grammar of `why` and `how`, and a fourth round of intakes (2026-11-10)

The owner saw whole sentences and values in `why` and `how` on the page. `SPEC.md` R-3.17 and R-6.17 and the documentation set, module 6.4, state the rule. No form delivered it or checked it, and the input schema says only "Use clear, simple technical English". The three earlier rounds of intakes were measured without this fault being seen.

Built in the Rust, Node and Python forms: the refusal `GRAMMAR_CONSTRAINT_VIOLATION` (see the note under R-5.24 in `SPEC.md`). Conformance is 24 cases, 388 steps, 0 differences in each form.

Four Sonnet intakes into a new home, `~/.metaform-climb4`, with the check in force:

| Target | Elements | Wants | Commands | Refused (grammar) | Received |
|---|---|---|---|---|---|
| axum-0.8.9 | 21 | 26 | 67 | 2 (2) | 9,058 bytes |
| lbug-0.22.3 | 26 | 36 | 48 | 7 (1) | 19,591 bytes |
| rmcp-3.9.0 | 40 | 77 | 113 | 10 (3) | 51,282 bytes |
| this repository | 61 | 80 | 141 | 1 (1) | 49,356 bytes |

The stored wants are fragments. The axum intake was shallow by its own account, so its map is not comparable with the earlier one.

What the four agents reported:

- The rule reaches an agent only through a refusal. All four said so. An agent wrote about 15 wants before its first refusal.
- The check does not refuse a long `how` made of verbs joined by commas, or a `why` that lists several actions.
- The message did not name the part or the fault. This was adjusted after the first intake; the other three still saw the earlier message, because the server process of that home had started before the adjustment.
- A refusal of about 1,100 bytes carries about 100 bytes of new information: the command is echoed, rendered as the tested sentence and given again as the remediation.
- A want for an address that is not an element is accepted and makes an empty element. `Intake.md` says both ends must resolve to elements. `SPEC.md` has no rule for it.
- `Intake.md` names a "native investigation knowledge layer" that does not exist (three agents), and the refusal's remediation for it, `{"map": {}}`, does not help.
- `goto` at the specification layer's definition returned 2,000 to 2,800 characters of writing rules to agents that only wanted to know what the `layer` addresses were.
- `orphaned` returns whole elements where addresses would do, and lists the downstream parties every time.

A fifth round, into `~/.metaform-climb5`, after three more adjustments: the message names the part and the fault, a `why` or `how` of more than 14 words is refused, and the remediation for a refused `add` of a new element is that `add`. The agents were told to read the source in depth.

| Target | Elements | Wants | Commands | Refused (grammar) | Received |
|---|---|---|---|---|---|
| axum-0.8.9 | 47 | 92 | 327 | 4 (3) | 85,225 bytes |
| lbug-0.22.3 | 39 | 72 | 66 | 1 (1) | 20,048 bytes |
| rmcp-3.9.0 | 47 | 75 | 251 | 7 (4) | 75,744 bytes |
| this repository | 72 | 121 | 103 | 0 (0) | 69,837 bytes |

The command counts include each agent's own reads for its final proof. The agent for this repository read the grammar rule in `rules.rs` while it surveyed the source, so its zero refusals say nothing about the refusal text. The other three said each grammar refusal let them write the next text correctly the first time.

Reported in this round:

- The fault "holds a value" does not name the word; an agent guessed `128-bit`.
- Only the first broken want of a command is reported.
- An `-ing` word after the first word passes (D-14), and so does a `how` of two verbs joined by "and" within 14 words.
- Writing a layer's list replaces the list, with no word that it did.
- `FIELD_MISMATCH` for an unknown want field has no remediation; for `intent` it could name `direction`. The field `intent` is in the tool the agents' own harness lists (`mcp__metaform__project-map`, the owner's installed server of an earlier build), not in this build.
- Three agents shared one scratch folder and one overwrote another's helper script; no data was lost. A later round must give each agent its own folder for helpers.

## 7b. The earlier map page (2026-11-10)

The owner said the new page was a step backwards from the earlier Metaform page and asked to start from the old code. The earlier page's own 2D map, camera, depth, flow, hover, selection, keys, search, side column tabs, layers list, right-click menu and exports now run against the new host at `/classic/` (`metaform/workspace/public/classic`), with one adapter for the new server's data. A third pass brought the earlier 3D map beside the 2D map, with one selection. Agents, chat, board, roundtables, voice and memory are not ported.

## 8. Open for the owner

1. **D-19.** Whether `name` may equal `technical_name` when the project has no name of its own. Recommended: yes, as the procedure says.
2. **`collection`.** The owner said intake has six roots. The procedure, the code and `roundtable/metaform.json` still have `collection`. The procedure is protected, so nothing was changed.
3. **The layer's address.** `layer.specification` or `layer.document.specification`. The build has the second, which has the form of the owner's `layer.code.cpp`.
4. **Where a layer is active** (enabled, linked, blocked) is recorded in `SPEC.md` and not built.
5. **The procedure names things the tool does not have:** a "native investigation knowledge layer", and it gives no role for a `downstream` party. Two agents asked for both.
6. **One map or two.** The intake of this repository put Metaform and Roundtable in one map and had to make Roundtable's engine Divergent, because a map has one Definitive element. The agent recommends a separate map for Roundtable.
8. **The example `"how": "Prepared mash data packets."`** in `tool-examples.json`, `intake-example.json` and `SPECIFICATION.md` is refused by the grammar check. Recommended: "Prepares mash data packets."
9. **The schema's descriptions of `why` and `how`** do not state the R-6.17 rule. The schema is protected. Recommended: replace them with the rule and the two examples, so an agent reads the rule before its first write.
10. **A want for an address that is not an element** is accepted and makes the element. Withdrawn as a recommendation: `SPEC.md` R-5.4 decides it ("A write creates every path it needs, including the element that a want names"). `Intake.md` says both ends must resolve to elements, so the procedure and the specification disagree; the procedure is protected.
11. **Which page is the base:** the earlier page at `/classic/`, or the page written on 2026-11-09 and 2026-11-10.
7. **Deleting a layer's definition** leaves its records at the elements, where no read that names the layer returns them. Whether a deletion should remove them, or be refused while records exist, depends on item 4.

## 9. Known limits left as they are

- A refused read of an address named `code`, `status`, `message` or `remediation` loses the repeated command, because the refusal's own key has the same name.
- A whole number written with a fraction, such as `3.0`, comes back as `3` from the Node form.
- `metaform/SKILL.proposed.md` and `SPECIFICATION.md` use earlier terms. `tools/verify_bootstrap.py` reads them, so they were not edited.
- `.mcp.json` starts the Rust form on `~/.metaform-rust`. The server that was already running for that home on 2026-11-09 was an older build and was not ended.
