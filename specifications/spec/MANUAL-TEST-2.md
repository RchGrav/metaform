# Manual test of the chassis build, second round

Date: 2026-09-26. Branch `chassis` at 727ae05. Tester: a Claude agent, by hand, as a user and as an AI agent would use Metaform. No code was changed; this file is the only file added.

## Setup

- `MT` is the scratch folder `/tmp/mt2`. Every command ran with `METAFORM_HOME=$MT/home`, except where a fresh home is named (`$MT/home2`, `$MT/mcphome`, `$MT/insthome`). The real `~/.metaform` and `~/.metaform.pre-chassis*` were never touched.
- The CLI ran as `/home/rich/metaform/.venv/bin/python -m metaform`, written below as `metaform`.
- Projects: `demo` on `$MT/proj`, given a small intake, `tests/fixtures/intake_timer.json`'s elements, which has one subtype (`code.loop.tick` under the alarm join); `rtproj` and `rtnew` on `$MT/mcphome`, for the real-tool run, `rtproj` with the same fixture, `rtnew` with no intake.
- The full pytest suite was run first, unmodified, from the repository root with `METAFORM_HOME` pointed at the scratch home: `414 passed` in 4 minutes, no failures. The last build log entry (step 18) recorded `411 passed, 3 failed on Q39`; the Canonical Intake reconciliation noted at the end of BUILD-LOG.md accounts for the 3 that now pass.
- The installer ran with `HOME` and `USERPROFILE` pointed at `$MT/insthome/user`, a `PATH` holding only fake `uv`, `uvx` (serving the SDK's fake tiny server), `claude`, `codex`, `gemini`, `code` and `copilot` from `tests/fakes.py`, and a pre-existing `~/.cursor/mcp.json` holding one other server. `METAFORM_WHEEL` named the wheel built by `metaform build`.
- The real-tool run built the wheel with `metaform build`, wrote `$MT/rt-mcp.json` with one stdio server, `uvx --from <wheel> metaform mcp serve`, env `METAFORM_HOME=$MT/mcphome`, and ran `claude -p ... --model sonnet --mcp-config $MT/rt-mcp.json --strict-mcp-config --setting-sources "" --allowedTools mcp__metaform --disallowedTools Bash,Edit,Write,Read,Glob,Grep,WebFetch,WebSearch,Task,Agent --output-format stream-json --verbose` from `rtproj` and `rtnew`. Transcripts: `$MT/rt1.jsonl`, `$MT/rt2.jsonl`, `$MT/rt3.jsonl`.
- The settings screen needs a terminal. This environment has no pty driver available to the tester, so it was not driven; this is noted once and not counted as a check, per the task's own instruction.

## Result

86 checks: 78 pass, 8 fail. Of the failures, 4 are features the build log already lists as not built (D18) or out of scope for this step (the viewer, section 09). The other 4 are open defects the build log itself tracks as unresolved (D1, D4, D14, D19). No new defect is raised; one behavior change from round one (self joins) is a resolved open question, not a defect, and one usability gap in MCP tool schemas is recorded as an observation, not a defect, because the spec as written does not require it.

## Status, help and errors

| # | Feature | Command | Observed | Spec | Result |
|---|---|---|---|---|---|
| 1 | Status, empty home | `metaform`, `ls $MT/home` | Home, Folder, `Project: none`, register line, exit 0; home stays empty | CLI-005, CLI-028, STORE-002 | PASS |
| 2 | Status, registered project, no intake | `metaform` | Home, Folder, `Project: demo (…)`, `Target: path …`, `Metaform: none yet`, `Projects: 1 registered`, `Modules: 4 on`, `Intake: none yet` with the notice, `Instructions: metaform help agents` | CLI-028, Q12 | PASS |
| 3 | Status in a subfolder | `metaform` in `proj/src` | `Project: demo (…)` with no suffix | PROJ-003 | PASS |
| 4 | Version | `metaform --version` | `metaform 0.1.0` | BASE-041 | PASS |
| 5 | Overview and intro | `metaform help`, `metaform help intro` | CLI-006 text, tips, home filled in | CLI-006 | PASS |
| 6 | Commands index | `metaform help commands` | Chassis verbs, then `intake:`, `map:`, `mcp:`, `memory:` groups, each verb under its module, `build` and `feedback`/`read` now listed among chassis commands | CLI-008, CLI-032 | PASS |
| 7 | Switches index | `metaform help switches` | Sorted switches including the new `--debug`, `--report`, `--intake-file` | CLI-008 | PASS |
| 8 | Page and syntax | `metaform help set`, `metaform set --help` | Page has Usage, Switches, Details, Examples, See also; syntax has Usage and switches only | CLI-007, CLI-029 | PASS |
| 9 | Short help alias | `metaform help -h`, `metaform help --help` | Identical syntax screens | CLI-004 | PASS |
| 10 | `help modules` (D1) | `metaform help modules` | `Error: No command, module or switch modules.` `Next: metaform help commands`, exit 2 | CLI-031 lists `modules`; CLI-008's indexes are `commands`, `switches` | FAIL, D1 still open (Q42) |
| 11 | Module page width (D2, part) | `metaform help map` | Rows no longer padded to 350 characters; a long row now wraps to its own line. The `knowledge` usage still shows `op=<op>` and `layer=<layer>` as `[op] [layer]`, optional | CLI-006, LAYER-018 | FAIL, D2 partly fixed, remainder is Q44 |
| 12 | Verb page, unsupported system (D3) | `metaform help helloworld beep`, `metaform helloworld beep` | Both now print `Error: helloworld beep runs on windows.` `Next: metaform help helloworld` | BASE-016 | PASS, D3 fixed |
| 13 | Optional nouns under `Switches` (D4) | `metaform help intake submit` | `elements=<str>`, `id=<str>`, `report=<str>`, `feedback=<str>`, `model=<str>`, `role=<str>`, `blinded=<bool>` still listed under `Switches` | CLI-029, BASE-043 | FAIL, D4 still open (Q43) |
| 14 | Empty section left out (D5) | `metaform enable template`, `metaform help template` | No `Verbs` heading printed; page is the summary plus purpose text only | CLI-029 | PASS, D5 fixed |
| 15 | Composed instructions | `metaform help agents` | Base text, `## map` names `map_roots` as the start, sections for `intake`, `mcp`, `memory`, notice at the end | MCP-007, CLI-029 | PASS |
| 16 | Undeclared switch | `metaform helloworld greet world --colour` (module off) | `Error: Module helloworld is off.` `Next: metaform enable helloworld`, exit 2 (the module happened to be off at the time; the message is the module gate, correctly taking priority) | CLI-020 | PASS |
| 17 | Unknown setting | `metaform set --colour red` | `Error: --colour is not a setting.` `Next: metaform help switches` | CLI-009 | PASS |
| 18 | Long name, one dash | `metaform set -quiet` | `-quiet is not a switch: a short switch is one letter.` `Next: metaform help --quiet` | CLI-004 | PASS |
| 19 | `--all` as argument | `metaform unset --all` | `Error: --all is not a switch. all is an argument.` `Next: metaform unset all` | CLI-002 | PASS |
| 20 | Bad noun, unknown verb | `metaform list foo`, `metaform nosuchverb` | `list needs a noun: projects or modules.`; `Unknown command: nosuchverb.` `Next: metaform help commands` | CLI-031, CLI-009 | PASS |

## Modules

| # | Feature | Command | Observed | Spec | Result |
|---|---|---|---|---|---|
| 21 | Shipping state, off-module summary (D6) | `metaform list modules` | `helloworld  off  system  A demonstration of every module feature.`; `template  off  system  The empty start of a module.`; `intake`, `map`, `mcp`, `memory` on | BASE-017, BASE-037 | PASS, D6 fixed |
| 22 | Enable and disable | `metaform enable helloworld`, `disable helloworld` | `Module helloworld: on` / `off` | CLI-031 | PASS |
| 23 | Select with choices from module data | `set --favorite zed` before any greet; after `greet rich`, `greet world`, `set --favorite zed` and `set --favorite world` | `Choices: none yet.` before any greeting; `Choices: rich, world.` after; `world` accepted and stored | CLI-019 | PASS |
| 24 | Caution verb | `helloworld forget`; `helloworld forget --confirm` | `Error: This deletes the greeting history.` `Next: … --confirm`; then `Greeting history deleted.` | BASE-013, CLI-018 | PASS |
| 25 | Async cancel | `helloworld wait 10`, SIGINT after 1 s | `Cancelling helloworld wait...` `Cancelled.`, exit 3 | BASE-031 | PASS |

## Settings

| # | Feature | Command | Observed | Spec | Result |
|---|---|---|---|---|---|
| 26 | `set`/`unset` report stored state, not value (D7) | `unset all`; `set --no-loud` from default | `set --no-loud` now prints `Success: updated 1 key` with `loud: false → false`, and `config --show` shows `loud: false  (set)`; a following `unset all` prints `Reset 1 setting(s): loud` | CLI-015, CLI-017 | PASS, D7 fixed |
| 27 | `set … folder=<path>` names the folder (D8) | `set --greeting child folder=/tmp/mt2/proj/src` | `Success: updated 1 key for /tmp/mt2/proj/src` then the value line | CLI-022 | PASS, D8 fixed |
| 28 | `config --show` with the new settings | `config --show` | `project`, `modules`, `layers`, `debug`, `report`, `greeting`, `loud`, `favorite`, `intake_file`, `raw`, each with its mark | BASE-029, CLI-034 | PASS |
| 29 | `--project` on one call to any module verb (D9) | from `outside`: `metaform map where '' --project demo` | Works without `set --project` first, returns the map's entry | CLI-021, BASE-028, D9 | PASS, D9 fixed |
| 30 | `--layers` on one call to any module verb (D9) | `metaform helloworld greet z --layers practices` | Runs without `map … has no switch --layers` | CLI-033 acceptance 2 | PASS, D9 fixed |
| 31 | Settings screen | `metaform config` | Not driven: no pty/terminal driver is available in this tool environment | CLI-026 | SKIPPED, noted |

## Projects and intake

| # | Feature | Command | Observed | Spec | Result |
|---|---|---|---|---|---|
| 32 | Nothing written into the project | `ls -la $MT/proj` after the whole run | Only `src`, made by the tester | STORE-001, PROJ-001 | PASS |
| 33 | Intake prompt served | `intake prompt` | The Digital Typology XML, target filled with the project path, submit line at the end | BASE-039, MCP-009 | PASS |
| 34 | Intake submit, CLI form | `intake submit elements=<file of the elements array> id=timer-1 model=manual role=tester blinded=false report="…" feedback="…"` | `elements: 3, joins: 2, subtypes: 1, refs: 5`; a real intake layer `intake-<timestamp>-<hex>` | BASE-039 | PASS |
| 35 | Intake status, before and after | `intake status` | `No intake yet. Read the instructions with metaform intake prompt.` before; `This project has an intake. Latest intake layer: …` after | MCP-009 | PASS |
| 36 | Subtype read back | `map subtypes <join>`, `map where code.loop.tick`, `map element code.loop.tick` | Subtype listed with its own function, relation, observation, refs; `where` gives `kind: subtype` with the subtype and its join; `element` refuses it, `No element code.loop.tick in context here.` `Next: metaform map where code.loop.tick` | MAP-030, MAP-031 | PASS |
| 37 | Status names the start (D13) | `metaform` after intake | `Start with: metaform map roots` | D13 | PASS, D13 fixed |
| 38 | `--debug` and `--report` footers | `set --debug`; `intake prompt` tail; `set --no-report`; `intake prompt` tail | `--debug` adds the feedback-on-the-process paragraph; `--no-report` removes the report-field paragraph; the stop-and-report sentence is always present | CLI-034, MCP-007 | PASS |

## The map module

| # | Feature | Command | Observed | Spec | Result |
|---|---|---|---|---|---|
| 39 | `map roots` finds the entry (D13) | `map roots` | `entry` with the VE and DE and their joins; `elements` lists all three roots | MAP-005, D13 | PASS, D13 fixed |
| 40 | `map where ''` equals roots | `map where ''` | Byte-identical to `map roots`'s output | Q27 | PASS |
| 41 | Instructions name the start | `metaform help agents`, the `## map` section | Names `map_roots` explicitly as where to start, and `map_where`/`map_element` before changing a part | D13, MAP-005 | PASS |
| 42 | Knowledge layer creation | `map knowledge op=create layer=practices variable=practice mutable=true hideable=true module=manualtest …` | Layer record, `kind: layer`, `mutable: True`, building | LAYER-018 | PASS |
| 43 | Property on a join, clearer notice (D12) | `map knowledge op=add-property layer=practices element=join:<id> key=note value='"test"'` | `Notice: element: join:<id> is a join; properties attach only to elements, so it was stored as given, orphaned, with its target in its extra.` No bad `Next:` line naming a non-address | MAP-022, STORE-008, STORE-039 | PASS, D12 fixed |
| 44 | Unnamed layer (LAYER-001) | `map knowledge op=add-element address=code.probe.scratch`, no `layer=` | Stored in a new building layer `unnamed-<UTC timestamp>`, with the notice `No layer was named; this was stored in a new building layer …, which has no variable and no provenance.` | LAYER-001 | PASS |
| 45 | Unknown `name=value` kept in `extra` (BASE-043) | `map knowledge op=add-element layer=practices address=code.probe.two bogus_field=surprise` | Stored with `extra: {"bogus_field":"surprise"}` and a notice naming the field not a noun here, listing the real nouns | BASE-043 | PASS |
| 46 | Findings and flags | `map knowledge op=add-element layer=practices address=code.probe.three flag=missing flag_note="No implementation found."`; `map findings`; `map findings flag=missing` | Element reads with `flag: missing`, `flag_note: …`; `map findings` and the filtered form both list it | MAP-046, STORE-042 | PASS |
| 47 | `map layers` as an aligned row (D11) | `map layers` | One row per layer: `name kind module tags state on/off/applied`, e.g. `practices  layer  manualtest  ready  on`, `fix-a  correction  map  ready  applied`, `unnamed-… layer map building off` | CLI-033, LAYER-019 | PASS, D11 fixed |
| 48 | `map stack` as an aligned row (D11) | `map stack` (with `fix-a` applied) | `fix-a  correction  map  ready  applied` | D11 | PASS, D11 fixed |
| 49 | `map metaforms` as an aligned row (D11) | `map metaforms` | `main  2026-09-26T…  active` | D11 | PASS, D11 fixed |
| 50 | Tags | `map tag practices review`; `map tag practices BAD`; `map layers tag=review`; `map untag practices review` twice | Tagged; an invalid tag is now stored as given with a notice, `'BAD' is not lowercase letters, digits, ., _ and -; it was stored as given.` (not refused, matching the notices-everywhere policy); listed by tag; untag is a no-op the second time | LAYER-019, BASE-044 | PASS |
| 51 | Hide and unhide | `map hide practices` (refused, needs `--confirm`); `--confirm`; `map node element:code.timer.kitchen` | Caution message first; hidden layer absent from the node read (only the intake layer's item shows); `map unhide practices` restores it | LAYER-006, BASE-038 | PASS |
| 52 | Select, mask, clear, effective-selection | `map mask code practices`; `map select code.timer.kitchen practices`; `query effective-selection <address>`; `map clear …` | `practices` absent from `code`'s effective selection while masked, present at `code.timer.kitchen` after select, and restored to the pre-select/mask set after `clear` | LAYER-007 | PASS |
| 53 | Self join, resolved (not round one's D11/Q7) | `map knowledge op=add-join layer=practices receiver=code.timer.kitchen provider=code.timer.kitchen …` | Stored, not refused: `Notice: provider: The provider is the receiver itself; the join was stored as given, D82.` | OPEN-QUESTIONS.md D82; 04-chassis-modules.md line 494 | PASS, spec change, not a defect (see note below) |
| 54 | Query reads | `query` (index), `query has-intake`, `query search cook`, `query node element:… raw=true` | Index printed; `True`; one hit; raw node view with layers grouped, states shown | STORE-028 | PASS |

## Blind-spot challenges

| # | Feature | Command | Observed | Spec | Result |
|---|---|---|---|---|---|
| 55 | Create challenge items | `map knowledge op=create layer=challenge.blind2 kind=layer …`; `op=add-item layer=challenge.blind2 node=element:… value=…` (twice); `op=finish` | Items stored, layer finished | LAYER-015 | PASS |
| 56 | C answer without link | `map answer <item> C` | Stored, not refused: `Notice: link: A C answer names the element or join that already handles the challenge; give it with link=element:<address>. The answer was stored without it.` | STORE-040 | PASS |
| 57 | Approve gate | `map approve <item>` while state is C | `Error: Challenge <id> is C; only a challenge answered B is approved.` `Next: metaform map answer <id> B` | LAYER-015 | PASS |
| 58 | B then approve, becomes a plan | `map answer <item> B`; `map approve <item>` | State goes `B` then `plan`, with `approved` timestamped | STORE-040 | PASS |
| 59 | Open item shows no state (D14) | `map knowledge op=add-item …` (unanswered), then `map node`/`map element` reads it | `state: null` throughout | LAYER-015, STORE-040 | FAIL, D14 still open (Q1) |

## Memory

| # | Feature | Command | Observed | Spec | Result |
|---|---|---|---|---|---|
| 60 | Unknown element, clearer notice (D15) | `memory add-observations element:code.nosuch.node x` | `Notice: target: code.nosuch.node was not an element; it was created in layer memory.` The element now exists, `layer: memory` | LAYER-012, BASE-038 | PASS, D15 fixed |
| 61 | `create-entities`, existing and new | `memory create-entities code.idea.future concept` twice | `existing: false` then `existing: true` | D18 (original) | PASS |

## Correction layers

| # | Feature | Command | Observed | Spec | Result |
|---|---|---|---|---|---|
| 62 | Correction layer, immutable/hideable notice | `map knowledge op=create layer=fix-a kind=correction …` | Stored, `mutable: False`, `hideable: False`, notice: `A correction layer is immutable and never hideable; it was stored so.` | LAYER-011 | PASS |
| 63 | `receiver=` named in a notice, not silently dropped (D16) | `map knowledge op=correct layer=fix-a id=<join> purpose="First fix." receiver=code.timer.kitchen reason=r` | `purpose` applied; `Notice: receiver: A join keeps its receiver for life; receiver was not applied. To move a join, remove it and add a new one in the same correction layer.` | STORE-034 | PASS, D16 fixed |
| 64 | Peel | `map knowledge op=peel layer=fix-a`; `map stack` | Layer back to building; the purpose reverts to the original text; stack empties | LAYER-011, STORE-017 | PASS |

## Multiple metaforms, export and import

| # | Feature | Command | Observed | Spec | Result |
|---|---|---|---|---|---|
| 65 | Add and switch back | `add metaform second`; `activate metaform main` | New metaform active, then switched back, with the way-back line | MAP-045 | PASS |
| 66 | `export layer=` with no `metaform=`, two metaforms present (D17) | `export demo layer=practices file=…` | `Exported to …`, succeeds; earlier this failed with `No layer practices-notes.` | STORE-027 | PASS, D17 fixed |
| 67 | Export all, import, re-import | `export all`; `import` into a fresh home; `import` again | `metaforms added: 2`, `layers added: 6`, `things added: 19`; a re-import reports everything skipped, nothing added | STORE-027 | PASS |

## Build, install and MCP

| # | Feature | Command | Observed | Spec | Result |
|---|---|---|---|---|---|
| 68 | Build | `metaform build` (helloworld, template off) | Wheel written; `cffi`, `cryptography`, `pydantic_core`, `rpds_py`, `wcwidth` named compiled, not carried | BASE-022, BASE-041 | PASS |
| 69 | `uvx --from <wheel>` runs | `uvx --from <wheel> metaform --version` | `metaform 0.1.0`, installs 31 packages | BASE-041 | PASS |
| 70 | Installer, checks only | `metaform install` with no names, no terminal | System, Python, uv, Source, all tools found or marked unverified, `Next: metaform install <tool>... or metaform install all`, nothing written | MCP-013, MCP-014 | PASS |
| 71 | Install three tools | `metaform install claude codex cursor` against fake tools | Preview with exact registration commands, backups, six skill copies, `Proof: server starts, 2 tools` (the fake server's own count) for each, `Next: open your AI tool …` | MCP-015 to MCP-018, MCP-021 | PASS |
| 72 | Re-run marks nothing as already set up (D19) | `metaform install claude codex cursor` again | Tool list identical to the first run; nothing marks claude, codex or cursor as already set up | MCP-019 | FAIL, D19 still open (deferred by D41) |
| 73 | `mcp serve` on a narrowed surface (D20) | `set --modules helloworld`; a real MCP client session against `metaform mcp serve` | The server starts and serves; `tools/list` returns `feedback`, `list_reports`, `read_report`, `set` (helloworld itself was off, so no `helloworld_*` tools; no refusal to start) | MCP-004 | PASS, D20 fixed |

## Real-tool run

`claude` (local install), model reported as `claude-sonnet-5`. Config `$MT/rt-mcp.json`: one stdio server, `uvx --from <built wheel> metaform mcp serve`, env `METAFORM_HOME=$MT/mcphome`. Flags exactly as specified in the task. Working folders `$MT/rtproj` (registered, three-element intake: `stakeholder.cook.home` VE, `code.timer.kitchen` DE, `code.alarm.audible` SE) and `$MT/rtnew` (registered, no intake). Transcripts: `$MT/rt1.jsonl`, `$MT/rt2.jsonl`, `$MT/rt3.jsonl`.

Run 1 prompt: read the instructions and say what they say, check the intake state, find one element, write an observation there, read it back, report every tool call.

What it did: loaded tool schemas with `ToolSearch`, then `intake_prompt`, `intake_status` (`This project has an intake. Latest intake layer: …`), `map_roots` — which, unlike round one, returned the map's entry directly, no failed searches needed. It picked `code.alarm.audible`, tried `memory_add-observations` with `node: "code.alarm.audible"` (no prefix), got the refusal `'code.alarm.audible' is not a node: write element:<address or id>, join:<id> or subtype:<address or id>.`, self-corrected to `element:code.alarm.audible`, wrote the observation, and read it back with `memory_open-nodes`. It also summarized the instructions correctly. 8 tool calls, no dead ends. This is a clean, direct pass through what round one's row 94/149 and D13 flagged as broken.

Run 2 prompt: create a small knowledge layer, add one item at the kitchen timer element, finish it, submit feedback.

What it did: `map_roots`, `map_search`, then `map_knowledge {"op": "create", ...}` succeeded at once. Adding the item was not as smooth: it tried `op: "add"`, `op: "help"`, `op: "item"`, `op: "property"`, and a call with no `op` at all, each refused by name with the correct `Next: metaform help map knowledge`, before landing on `op: "add-item"`, whose error then named its own missing nouns (`node, value`), and one more attempt with a bare id before `node: "element:code.timer.kitchen"` worked. It then finished the layer and submitted feedback describing the friction. 15 tool calls; the task completed, but with real trial and error on the `op` values.

Run 3 prompt: quote the instructions on intake state for `rtnew`, and check it.

What it did: quoted, without a tool call, the no-intake notice delivered at connection start, then called `intake_status` and got `No intake yet. Read the instructions with metaform intake prompt.` Both matched exactly.

| # | Feature | Observed | Spec | Result |
|---|---|---|---|---|
| 74 | Real host receives instructions | Run 1 summarized correctly; run 3 quoted the notice exactly | MCP-007 | PASS |
| 75 | Real host checks intake state | `intake_status` in all three runs | MCP-024 | PASS |
| 76 | Real host finds an element without help (D13) | Run 1's `map_roots` returned the roots on the first call; no failed searches, no giving up | D13, MAP-005 | PASS, D13 fixed |
| 77 | Real host writes and reads memory at an element | Run 1 wrote and read back at `element:code.alarm.audible` | MCP-024 steps 8, 9 | PASS |
| 78 | Real host builds and finishes a knowledge layer | Run 2's `agent-notes` layer created, one item added, finished | LAYER-018 | PASS |
| 79 | Real host submits feedback | Run 2's `feedback` call, `{"project": "rtproj", "run": "…", "files": ["…-feedback.md"]}` | BASE-045 | PASS |

## Not built (confirmed)

| # | Feature | Command | Observed | Spec | Result |
|---|---|---|---|---|---|
| 80 | `import wheel=<name>-<version>` | `metaform import wheel=metaform-0.1.0` | Read as a file path: `No file at …/wheel=metaform-0.1.0.` | BASE-025 | FAIL, D18, not built |
| 81 | `metaform uninstall` | `metaform uninstall claude` | `Unknown command: uninstall.` | MCP-020 | FAIL, D18, not built |
| 82 | History commands | `metaform add origin`; `metaform list origins`; `metaform add variant .`; `metaform extract all /tmp/x` | `add needs: project <id> <path>, or metaform <name>.`; `list needs a noun: projects or modules.`; same as `add origin`; `Unknown command: extract.` | PROJ-010 to PROJ-024 | FAIL, D18, not built |
| 83 | The web GUI, section 09 | `metaform web`; `metaform help history` (a viewer-adjacent guess); `list modules` | `Unknown command: web.`; no `web` module exists; `list modules` still shows only `helloworld`, `intake`, `map`, `mcp`, `memory`, `template` | VIEW-002 and section 09 generally | FAIL, not built, as expected |

## Defects: status of D1 to D20

| Defect | Round one | This round | Note |
|---|---|---|---|
| D1 | `help modules` refused | Still refused | Open, Q42: recommendation is to read it as `commands`, not yet built |
| D2 | Row padded to 350 chars, `op`/`layer` shown optional | Row width fixed; `op`/`layer` still shown optional in `knowledge` usage | Partly fixed; remainder is Q44 |
| D3 | No runs-on-system line on the verb's help page | Fixed: help page and running the verb both show it | Fixed |
| D4 | Optional nouns listed under `Switches` | Unchanged | Open, Q43 |
| D5 | Empty `Verbs` heading printed | Fixed: heading left out when the module has none | Fixed |
| D6 | Off module shows no summary | Fixed: summary shown without importing the module | Fixed |
| D7 | `set`/`unset` compare values, not stored state | Fixed: reporting follows stored state | Fixed |
| D8 | `folder=` narrowing omits the folder name | Fixed | Fixed |
| D9 | `--project`/`--layers` not usable on one CLI call to a module verb | Fixed: both work on any module verb, matching MCP | Fixed |
| D10 | Settings screen row format wrong | Not re-verified: no terminal available this round | Not retested |
| D11 | `map layers` prints one JSON line | Fixed: `map layers`, `map stack`, `map metaforms` all print one aligned row each | Fixed |
| D12 | Next line names a non-address | Fixed: the notice now says a property attaches only to an element, no bad Next line | Fixed |
| D13 | Agent cannot find where the map starts | Fixed: `map roots`, `map where ''`, the status line and the map instructions all point to it; a real agent run used it cleanly | Fixed |
| D14 | Unanswered challenge shows no state | Still shows `null` | Open, Q1: nothing yet marks a layer as blind-spot |
| D15 | Next line steers to a bad workaround | Fixed: the notice now explains the element was created in the memory layer directly | Fixed |
| D16 | Correction accepts and silently drops `receiver=` | Fixed: `receiver` is named in a notice, not applied, nothing else lost | Fixed |
| D17 | `export layer=` fails without `metaform=` when more than one metaform exists | Fixed | Fixed |
| D18 | `import wheel=`, `uninstall`, history commands not built | Still not built | Confirmed, unchanged |
| D19 | Re-run of `install` does not mark tools already set up | Still does not | Open, deferred by D41 |
| D20 | Narrowing away from `mcp` stops the server starting | Fixed: `mcp serve` now runs on any surface and filters its own tool list | Fixed |

Of the 20 defects: 13 fixed (D3, D5, D6, D7, D8, D9, D11, D12, D13, D15, D16, D17, D20), 1 partly fixed (D2), 4 still open and already tracked as such by the spec's own open questions (D1/Q42, D4/Q43, D14/Q1, D19/deferred), 1 confirmed still not built (D18), and D10 was not re-driven for lack of a terminal.

## Other observations, not counted

- Self joins (round one's check 90, "Cycle shapes") are no longer refused by `map knowledge op=add-join`; they are stored as given with a notice citing D82. This is not a defect: `specifications/spec/OPEN-QUESTIONS.md` records D82 as settled ("Stored as given") and `04-chassis-modules.md` and the code (`src/metaform/data/writes.py`) agree. `BUILD-QUESTIONS.md`'s Q7 entry, which still says `add_join` refuses a self join, is stale text left over from before step 12's "notices everywhere" pass; the current spec and the current build agree with each other, just not with that one superseded paragraph.
- Over MCP, the `map_knowledge` tool's JSON schema gives `op` as a bare string with no `enum` and no `description`; the noun's help text ("create, add-element, add-join, …") that appears on the CLI's help page is not carried into the tool schema. A real Claude agent in run 2 needed five wrong guesses (`add`, `help`, `item`, `property`, no `op` at all) before finding `add-item`, and one more before supplying the right shape of `node`. This is not a defect against the spec as written: MCP-003's Build paragraph says a noun's schema property is "typed by BASE-035," type only, with no requirement for a description or an enum of valid values. It is a real cost in a live run, worth a design decision, not a violation.
- `map layers`, `map stack` and `map metaforms`' new aligned-row format lines up well for short names; a long layer name (such as `unnamed-20260926T001427Z`) pushes the following columns out of alignment with the shorter rows above it. Cosmetic, not counted.
- The intake CLI's `elements=<path>` noun wants a file holding the elements array itself, not the whole fixture object (`{"id": ..., "elements": [...]}`) that `tests/fixtures/intake_timer.json` is shaped as. The `id` goes on the command line separately, `id=<value>`. This matches how the module's own tests build the call and is not a defect; it is worth knowing before reading `intake_timer.json` as a ready-made CLI argument.
- The full pytest suite is green: 414 passed, 0 failed, where the last recorded build-log state was 411 passed with 3 failing on Q39. The Canonical Intake reconciliation at the end of BUILD-LOG.md accounts for this.
