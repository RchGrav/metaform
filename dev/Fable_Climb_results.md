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

Not established: types (no TypeScript compiler or Python type checker is installed), survival of power loss, and fairness of the write lock under heavy load (SQLite's lock is not first come, first served; the design document says so).

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

**Not established:** that agents do as well or better with the smaller answers. The replay holds the commands fixed. The next experiment should be a second set of Sonnet intakes on the current build, compared with the first on refusals, commands and the quality of the map.

**Most useful next experiments,** from the same reports: `goto` lists layers and memory with zero records (omit them); `orphaned` returns whole records where intake needs addresses; a refusal's remediation repeats the whole command; at a layer's definition the sheet holds the instruction twice (in `element` and in `guidance`).

## 7. The graph workspace

- The page uses the host's real data when `metaform-web` serves it, and the mock under `npm run dev` or with `?mock`. Nothing simulated appears on real data.
- `metaform gui` listens on `http://127.0.0.1:4170/`, or a free port when that one is in use. The page shows its own address with a control that copies it.
- Polish, checked in Chrome on the four real maps: header text no longer overlaps in an expanded element; a want count has a halo so lines do not strike through it; Details for an address that only groups elements lists them and says the arrows belong to them; an empty home and an empty map each say what they are.

Not established: the clipboard copy, and behavior in Firefox or Safari.

## 8. Open for the owner

1. **D-19.** Whether `name` may equal `technical_name` when the project has no name of its own. Recommended: yes, as the procedure says.
2. **`collection`.** The owner said intake has six roots. The procedure, the code and `roundtable/metaform.json` still have `collection`. The procedure is protected, so nothing was changed.
3. **The layer's address.** `layer.specification` or `layer.document.specification`. The build has the second, which has the form of the owner's `layer.code.cpp`.
4. **Where a layer is active** (enabled, linked, blocked) is recorded in `SPEC.md` and not built.
5. **The procedure names things the tool does not have:** a "native investigation knowledge layer", and it gives no role for a `downstream` party. Two agents asked for both.
6. **One map or two.** The intake of this repository put Metaform and Roundtable in one map and had to make Roundtable's engine Divergent, because a map has one Definitive element. The agent recommends a separate map for Roundtable.
7. **Deleting a layer's definition** leaves its records at the elements, where no read that names the layer returns them. Whether a deletion should remove them, or be refused while records exist, depends on item 4.

## 9. Known limits left as they are

- A refused read of an address named `code`, `status`, `message` or `remediation` loses the repeated command, because the refusal's own key has the same name.
- A whole number written with a fraction, such as `3.0`, comes back as `3` from the Node form.
- `metaform/SKILL.proposed.md` and `SPECIFICATION.md` use earlier terms. `tools/verify_bootstrap.py` reads them, so they were not edited.
- `.mcp.json` starts the Rust form on `~/.metaform-rust`. The server that was already running for that home on 2026-11-09 was an older build and was not ended.
