# Manual test of the chassis build

Date: 2026-09-25. Branch `chassis` at 3e610e7. Tester: a Claude agent, by hand, as a user and as an AI agent would use Metaform. No code was changed.

## Setup

- `MT` is the scratch folder `/tmp/claude-1000/-home-rich-notes/3beff1cb-4a4c-4d8c-a313-66e536b5ad27/scratchpad/manual-test`. Every command ran with `METAFORM_HOME=$MT/home`. The real `~/.metaform` and the real tool configs were never touched.
- The CLI ran as `/home/rich/metaform/.venv/bin/python -m metaform`, written below as `metaform`. The folder a command ran in is shown when it is not `$MT/proj`.
- Projects: `demo` on `$MT/proj`, holding a real intake; `photos` on `$MT/photos`, target `artifact kitchen_photos`, holding a subtype intake; `rtproj` and `rtnew` for the real-tool run.
- The installer ran with `HOME=$MT/insthome`, fake `claude`, `codex`, `gemini`, `code`, `copilot` and `droid` executables that record their arguments, the folders `~/.cursor`, `~/.gemini/config` and `~/Library/Application Support/Claude` made in the fake home, and a Cursor `mcp.json` holding one other server.
- MCP was driven with the real `mcp` 2.2.0 SDK client in the venv, scripts `$MT/mcpc.py`, `$MT/s3.py` and `$MT/s6.py`. The full transcript of every command is `$MT/log.txt`.
- The spec was read at 12:46 on 2026-09-25. Another session edited 01 to 06 at 13:05 and 13:06, during this run. The Spec column quotes the text as read at 12:46.
- The real intake submission was built from `/home/rich/notes/intake_1.1.xml` by `$MT/xml2submit.py`: each receiving element with its joins, and each provider element nested in a join added as its own element. It has 13 elements, 12 joins and 59 refs, and no subtypes, so subtypes were tested with a second submission on `photos`.

## Result

156 checks: 131 pass, 25 fail. Of the failures, 5 are features the build log already lists as not built. Every failure is listed with its fix in Defects.

## Status and help

| # | Feature | Command | Observed, trimmed | Spec | Result |
|---|---|---|---|---|---|
| 1 | Status, unregistered folder, empty home | `metaform`, then `ls $MT/home` | `Metaform 0.1.0`, Home, Folder, `Project: none`, `Register one: metaform add project <id> <path>`, exit 0. The home stays empty. | CLI-005, CLI-028, STORE-002: a read writes no file | PASS |
| 2 | Status, registered project, no intake | `metaform` | Lines in order: Home, Folder, `Project: demo (…/proj)`, `Target: path …`, `Metaform: none yet`, `Projects: 1 registered`, `Modules: 5 on`, `Intake: none yet` and the notice, `Instructions: metaform help agents` | CLI-028; `none yet` follows Q12 | PASS |
| 3 | Status in a subfolder | `metaform` in `proj/src` | `Project: demo (…/proj)` with no suffix | PROJ-003: containment default | PASS |
| 4 | Version | `metaform --version` | `metaform 0.1.0` | BASE-041 | PASS |
| 5 | Overview | `metaform help` | Exactly the CLI-006 lines, four tips, 14 lines | CLI-006 | PASS |
| 6 | Intro | `metaform help intro` | Exactly the CLI-006 text with the home filled | CLI-006 | PASS |
| 7 | Commands index | `metaform help commands` | Chassis verbs, then `intake:`, `map:`, `mcp:`, `memory:` groups with each verb under its module | CLI-008, CLI-032 | PASS |
| 8 | Switches index | `metaform help switches` | Every setting and verb control, sorted, then the `Use 'metaform help <switch>'` line | CLI-008 | PASS |
| 9 | Page and syntax | `metaform help set`, `metaform set --help` | The page has Usage, Switches, Details, Examples, See also; the syntax has Usage and switches only, ending `-h, --help  Show this syntax.` | CLI-007, CLI-029 | PASS |
| 10 | Short help alias | `metaform help -h`, `metaform help --help` | Identical syntax screens | CLI-004 | PASS |
| 11 | `help modules` | `metaform help modules` | `Error: No command, module or switch modules.` `Next: metaform help commands`, exit 2 | CLI-031 lists `modules` among `help` nouns | FAIL, D1 |
| 12 | Switch page | `metaform help --modules` | The CLI-022 help text, Usage `set` and `unset`, `Owner: chassis. Kind: list. Applies to: this folder.` | CLI-022, CLI-029 | PASS |
| 13 | Module page layout | `metaform help map` | Every verb row is padded to about 350 characters because the `knowledge` usage line lists 40 nouns; `op` and `layer` show as optional `[op] [layer]` | CLI-006 brief pages, LAYER-018 every call names its layer | FAIL, D2 |
| 14 | Per-system verb, help page | `metaform help helloworld beep` | Page with Usage and See also; nothing says it runs on windows | BASE-016: the page prints `helloworld beep runs on windows.` | FAIL, D3 |
| 15 | Per-system verb, run and listing | `metaform helloworld beep`; `metaform help helloworld` | `Error: helloworld beep runs on windows.` `Next: metaform help helloworld`; listed under `Not on this system`; absent from the MCP tool list | BASE-016 | PASS |
| 16 | Verb page for nouns | `metaform help intake submit` | Optional nouns `elements=<str>`, `id=<str>` … are listed under the heading `Switches` | CLI-029, BASE-043: nouns are not switches | FAIL, D4 |
| 17 | Empty section left out | `metaform enable template`, `metaform help template` | Page shows an empty `Verbs` heading | CLI-029: empty sections are left out | FAIL, D5 |
| 18 | Composed instructions on the CLI | `metaform help agents` | Base text, `## helloworld`, `## intake`, `## map`, `## mcp`, `## memory`, then the notice | MCP-007, CLI-029 | PASS |
| 19 | Switch owner | `metaform help --loud` | `Owner: helloworld. Kind: bool. Applies to: this folder.` | CLI-012 | PASS |
| 20 | Unknown help topic | `metaform help nosuch` | `No command, module or switch nosuch.` `Next: metaform help commands` | CLI-031 | PASS |

## Errors

| # | Feature | Command | Observed, trimmed | Spec | Result |
|---|---|---|---|---|---|
| 21 | Undeclared switch on a verb | `metaform helloworld greet world --colour` | `Error: helloworld greet has no switch --colour.` `Next: metaform helloworld greet --help`, exit 2 | CLI-001 | PASS |
| 22 | Missing noun, extra word | `metaform helloworld greet`; `… greet a b` | `greet needs <name>.` and `greet does not take 'b'.`, each with one Next line naming `--help` | CLI-001 | PASS |
| 23 | Unknown setting | `metaform set --colour red` | `Error: --colour is not a setting.` `Next: metaform help switches` | CLI-009 | PASS |
| 24 | Long name with one dash | `metaform set -quiet` | `-quiet is not a switch: a short switch is one letter.` `Next: metaform help --quiet` | CLI-004 | PASS |
| 25 | `--all` | `metaform unset --all` | `Error: --all is not a switch. all is an argument.` `Next: metaform unset all` | CLI-002 | PASS |
| 26 | Bad noun and unknown verb | `metaform list foo`; `metaform nosuchverb` | `list needs a noun: projects or modules.` `Next: metaform list projects`; `Unknown command: nosuchverb.` `Next: metaform help commands` | CLI-031, CLI-009 | PASS |

Every error seen in this run, on the CLI and over MCP, ended with exactly one `Next:` line.

## Modules, enable and disable

| # | Feature | Command | Observed, trimmed | Spec | Result |
|---|---|---|---|---|---|
| 27 | Shipping state | `metaform list modules` on a fresh home | `helloworld off`, `template off`, `intake`, `map`, `mcp`, `memory` on, all `system` | BASE-017 | PASS |
| 28 | Summary of an off module | same | The off modules show no summary: `helloworld  off    system` | BASE-037: `<summary or reason>` on every line | FAIL, D6 |
| 29 | Enable, disable, unknown id | `metaform enable helloworld`; `enable nosuch` | `Module helloworld: on`; `No module nosuch.` `Next: metaform list modules` | CLI-031 | PASS |
| 30 | Verb of an off module | `metaform helloworld greet world` while off | `Error: Module helloworld is off.` `Next: metaform enable helloworld` | BASE-017 | PASS |
| 31 | Chassis alone | disable map, memory, intake, mcp, helloworld; run `metaform`, `help`, `config --show`, `export`, `query where code.manager.route` | All exit 0; status `Modules: 0 on`; `mcp serve` says `Module mcp is off.` `Next: metaform enable mcp` | BASE-001, MCP-001 | PASS |
| 32 | Module settings while absent | `set --greeting bonjour --glue`, `disable helloworld`, `unset all`, `enable helloworld`, `config --show` | While off `--greeting is not a setting.`; after enable `* greeting: bonjour  (glued)` | CLI-024 | PASS |
| 33 | Template | `metaform enable template`; `list modules` | Loads, `template  on  system  The empty start of a module.`, no verbs | BASE-019 | PASS |

## Helloworld

| # | Feature | Command | Observed, trimmed | Spec | Result |
|---|---|---|---|---|---|
| 34 | Verb, switch on one call, history as a layer | `greet world`; `greet rich --loud`; `history`; `query layers` | `hello, world`; `HELLO, RICH!`; `world` `rich`; a layer `helloworld.greetings` | CLI-011, STORE-022 | PASS |
| 35 | Verb that needs a store, no project | `greet world` before any project | `No project for this folder.` `Next: metaform add project <id> <path>` | CLI-020, STORE-023 | PASS |
| 36 | Async verb | `metaform helloworld wait 1` | `waited 1 s` | BASE-009 | PASS |
| 37 | Caution verb | `helloworld forget`; then `--confirm` | `Error: This deletes the greeting history.` `Next: If you are sure: metaform helloworld forget --confirm`, history unchanged; then `Greeting history deleted.` | BASE-013, CLI-018 | PASS |
| 38 | Select with choices from module data | `set --favorite zed`; `set --favorite world` | `--favorite has no choice 'zed'. Choices: rich, world.` `Next: metaform help --favorite`; then stored | CLI-019 | PASS |
| 39 | Ctrl+C on an async verb | `helloworld wait 10`, SIGINT after 1.5 s | `Cancelling helloworld wait...` `Cancelled.`, exit 3 | BASE-031 | PASS |

## Settings

| # | Feature | Command | Observed, trimmed | Spec | Result |
|---|---|---|---|---|---|
| 40 | Stored boolean, per-call opposite | `set --loud`; `greet ann`; `greet bob --no-loud`; `config --show` | `HELLO, ANN!`; `hello, bob`; `loud: true  (set)` still stored | CLI-011, CLI-015 | PASS |
| 41 | `--name=value` | `set --greeting=hey` | `greeting: hello → hey` | CLI-004 | PASS |
| 42 | Booleans never toggle | `set --loud` twice | second prints `Success: no changes`, value stays true | CLI-015 | PASS |
| 43 | Quiet | `set -q --greeting hola`; `unset -q --greeting` | No output, exit 0 | CLI-031 | PASS |
| 44 | Glue and unset all | `set --greeting hi --glue`; `unset all`; `unset --greeting`; `set --greeting yo` | `glued: greeting`; `Skipped (glued): greeting`; `No settings required reset` `Skipped (glued): greeting`; value yo, still `(glued)` | CLI-013, CLI-016 | PASS |
| 45 | Glued boolean inverted | `set --loud --glue`; `set --no-loud`; `unset all` | `* loud: false  (glued)` kept | CLI-016 | PASS |
| 46 | Unglue | `unset all --unglue`; `unset --loud --unglue` | `Reset 1 setting(s): greeting` `Unglued: greeting`; `config --show --json` every state `default` | CLI-017 | PASS |
| 47 | Reporting a value equal to the default | `set --loud`; `set --no-loud`; `config --show`; `unset all`; `set --no-loud`; `config --show` | `loud: false  (set)`; `unset all` prints `No settings required reset` yet clears it; `set --no-loud` prints `Success: no changes` yet stores it, `loud: false  (set)` | CLI-017: every reset setting is listed; CLI-022: `no changes` only when nothing changed | FAIL, D7 |
| 48 | `--confirm` is never a setting | `set --confirm` | `Error: --confirm is not a setting.` `Next: metaform help --confirm` | CLI-018 | PASS |
| 49 | `--` ends switch parsing | `greet -- --dash`; `greet -- all`; `memory add-observations element:code.monitor.uplink -- "-40 dBm is the weakest usable signal."` | `HELLO, --DASH!`; `HELLO, ALL!`; the observation stored with its dash | CLI-003 | PASS |
| 50 | Folder scope | `set --greeting parent` in proj; `set --greeting child` in proj/src; greet in each | `child, x` in src, `parent, y` in proj | CLI-014 | PASS |
| 51 | Project selection outside any project | in `outside`: `set --project demo`; `metaform`; `set --project nosuch`; `unset --project` | `Project: demo (…), selected here`; `--project has no choice 'nosuch'. Choices: demo.` `Next: metaform list projects`; back to `Project: none` | PROJ-003, CLI-030 | PASS |
| 52 | Narrowing the surface | `set --modules chassis,map` in proj/src; `memory read-graph`; `metaform` | The five CLI-022 lines; `memory is not on this folder's command surface.` `Next: metaform unset --modules`; status line `Modules: chassis, map (narrowed; restore: metaform unset --modules)` | CLI-022, CLI-028 | PASS |
| 53 | Narrowing another folder | `set --modules helloworld folder=$MT/other`; `help commands` in other | Stored for other; `help commands` there shows help, set, unset, config and helloworld only. The output does not name the folder | PROJ-007; CLI-022: the lines name the folder | FAIL, D8 |
| 54 | Bad group | `set --modules mapp` | `--modules has no group 'mapp'. Groups: chassis, helloworld, intake, map, mcp, memory, template.` `Next: metaform list modules` | CLI-030 | PASS |
| 55 | `--layers` stored | `set --layers practices`; read in proj/src; `set --layers nosuch`; `set --layers fix-3`; `set --layers practices --glue`, `unset all`, `unset all --unglue` | Only `practices-notes` in the node read, in the subfolder too; `--layers has no layer or tag 'nosuch'.`; `fix-3 is a correction layer; correction layers are always applied.`; glued kept, then back to `all` | CLI-033, LAYER-019 | PASS |
| 56 | `--layers` on one call | `metaform map node element:code.interface.control --layers foresight-notes` | `Error: map node has no switch --layers.` | CLI-033 acceptance 2, CLI-011 | FAIL, D9 |
| 57 | `--project` on one call | in `outside`: `metaform map where code --project demo` | `Error: map where has no switch --project.` | CLI-021, BASE-028, MCP-025: `--project <id>` on the CLI | FAIL, D9 |
| 58 | `config --show` and JSON | `config --show`; `config --show --json` | `<mark> <key>: <value>` rows, `(set)` and `(glued)`, footer; JSON rows with key, switch, owner, kind, value, state, default, help | CLI-031, BASE-029 | PASS |
| 59 | Settings screen | `metaform config` in a pseudo terminal via `script`, keys `j` and `q` | Opens with Modules and Registered settings panels, details and key bar; `q` quits. Rows read `project = demo default` and lists show `[]` | CLI-026: rows `key: value` with `*` for glued and `(set)` for set | FAIL, D10 |

## Projects

| # | Feature | Command | Observed, trimmed | Spec | Result |
|---|---|---|---|---|---|
| 60 | Id rules and duplicates | `add project Demo proj`; `add project demo /nonexistent`; `add project demo .` twice; `add project demo2 .`; `add project demo . url http://x` | Uppercase refused; `No folder at /nonexistent.`; `Added project demo …` then `Project demo is already registered.`; `… already registered as project demo.`; `Project demo is registered with another folder or target.` | STORE-031 | PASS |
| 61 | Target | `add project photos $MT/photos artifact kitchen_photos`; `metaform` there; `intake prompt` there | `Target: artifact kitchen_photos`; `<target type="artifact" value="kitchen_photos" …>` | MAP-041, MAP-043 | PASS |
| 62 | Nothing written into the project | `ls -la proj` after the whole run | Only `src`, which the tester made | STORE-001, PROJ-001 | PASS |

## Intake

| # | Feature | Command or call | Observed, trimmed | Spec | Result |
|---|---|---|---|---|---|
| 63 | Prompt served unchanged | `intake prompt > prompt.out`; `diff` with `rich/Canonical_Intake.xml` | Only line 7, the `<target>` attributes, differs, plus the blank line and `Submit the result with intake_submit, or metaform intake submit on the command line.` | BASE-039, MCP-009 | PASS |
| 64 | Resource is a byte copy | `cmp` of the resource and the spec file | identical | BASE-039 | PASS |
| 65 | Prompt over MCP | `intake_prompt` | One text block, byte-equal to the CLI standard output | BASE-036 | PASS |
| 66 | Refused submission | `intake submit elements=$MT/bad1.json`: one join without purpose, a bad address, an unknown provider | Lists all four problems with their paths, `Next: fix the listed fields and call intake_submit again`; `intake status` still `No intake yet.`; the notice stays | BASE-039, MAP-040 | PASS |
| 67 | Subtype with a purpose | `bad2.json` | `elements[0].joins[0].subtypes[0].purpose: is not a field here` | MAP-030 | PASS |
| 68 | Self join | `bad3.json` | `a join runs to a different element than its receiver` | Q7, D11 | PASS |
| 69 | Real intake over MCP | `intake_submit` with the 13 converted elements, `id`, model, role, blinded | `{"layer": "intake-20260925T165008Z-40fee4", "project": "demo", "elements": 13, "joins": 12, "subtypes": 0, "refs": 59}` | MAP-040, BASE-039 | PASS |
| 70 | Read back whole | A script compared every element's name, name_length, role and refs in order, and every join's type, purpose, function, relation, observation and non_goal, against the submission | `mismatches: 0` | MAP-040 acceptance 1 | PASS |
| 71 | Intake layer record | `query layers --json`; `query provenance <intake layer> --json` | kind intake, immutable, not hideable, ready, `result_id` the submitted id; provenance module intake, workflow canonical-intake, model, role, blinded as given, prompt equal to the served text | BASE-039, LAYER-010 | PASS |
| 72 | Notice gone | new MCP connection; `metaform`; `intake status` | No notice; `Intake: complete`; `This project has an intake. Latest intake layer: …` | MCP-009, CLI-028 | PASS |
| 73 | CLI submission with subtypes | `intake submit elements=$MT/photos_elements.json id=photos-1 model=manual role=tester blinded=false` with a duplicate VE, a join with an empty purpose, and `media.photo.jpg` | `elements: 4`, `joins: 2`, `subtypes: 2`, `refs: 3`: the duplicate merged, the empty purpose and the `jpg` address stored | BASE-039, STORE-026, MAP-013 | PASS |
| 74 | Subtypes read back | `map subtypes <join>`; `map where media.view.wall`; `map element media.view.wall`; `map citing path a.jpg` | Each subtype with its own function, relation, observation, role and refs and its join's layer; `where` returns kind subtype with its join; `element` says it is not an element; `citing` finds the join and the subtype | MAP-030, MAP-031, MAP-021 | PASS |
| 75 | Submission with a project argument | `intake_submit` with `project: rtnew` from a server started in `outside` | Stored into rtnew; `intake status` in rtnew says it has an intake | MAP-043 acceptance 3 | PASS |

## The map module

| # | Feature | Command | Observed, trimmed | Spec | Result |
|---|---|---|---|---|---|
| 76 | Element read with readings | `map element code.daemon.manager.gateway` | `reading: gateway manager daemon code`, `short_name: gateway manager daemon`, name, role, the descriptor with its 11 refs in order, the intake layer name | MAP-012, STORE-025 | PASS |
| 77 | Children and one element per address | `map children code`; `knowledge op=add-element layer=practices-notes address=code.manager.route` | The next level under code; `existing: True`, the same element id | MAP-010, MAP-016 | PASS |
| 78 | Create a knowledge layer | `knowledge op=create layer=practices-notes variable=… mutable=true hideable=true module=manualtest workflow=practices prompt=… model=none role=person blinded=false 'tags=["practices"]'` | The layer, building, with its tag; provenance reads back with every field | LAYER-018, LAYER-010 | PASS |
| 79 | Create without a variable | `knowledge op=create layer=bad2 …` | `knowledge op=create needs variable.` | LAYER-002 | PASS |
| 80 | Building layer out of context | `map context code.interface.control`; `map node element:code.interface.control` and `--raw` | Context empty; practices-notes absent in context, present raw | STORE-032, LAYER-008 | PASS |
| 81 | Build object by object | `add-element code`, three `add-property`, `add-join`, `add-item` on the join, `edit`, `add-ref`, `remove` of an element, `remove` of the used join, `finish` twice | Each returns its record; removing the join still used is refused naming the item; second finish `Layer practices-notes is already finished.` | LAYER-018, STORE-024 | PASS |
| 82 | Edit after finish | `knowledge op=edit … value=…`; `map node join:<id>`; `map history <item>` | New value in context; one version | LAYER-018, STORE-032 | PASS |
| 83 | Property transitivity | `map context` at `code.interface.control`, `code.interface.control.cli`, `code`, `code.daemon`, `code.interface` | At the control element and above it: `C` and `Bash` apply. At `code`: `C` applies, `C++…` and `Bash` visible. At `code.daemon`: only `C++…` visible, no Bash | MAP-022, LAYER-005, STORE-035 | PASS |
| 84 | Joins from layers with their names | `map joins code.interface.control`; `map joins code.protocol.multicast as=provider`; with `--layers practices`; with a mask of practices-notes at `code.interface`; `--raw` | Each join shows `[layer practices-notes]` or the intake layer name; the knowledge join is absent when masked and present with `--raw` | LAYER-016, STORE-025 | PASS |
| 85 | Tags | `map tag practices-notes review`; `map tag practices-notes BAD`; `map layers tag=practices`; `map untag` twice | Tagged; `'BAD' is not a tag …`; the tagged layer listed; untag is a no-op the second time | LAYER-019, STORE-038 | PASS |
| 86 | Layer listing format | `metaform map layers` | One compact JSON line of all layer records | CLI-033 shows one aligned row per layer: name, kind, module, tags, ready, on | FAIL, D11 |
| 87 | Select and mask | `map mask code practices-notes`; `map select code.interface.control practices-notes`; `query effective-selection` at five addresses | practices-notes off at `code`, `code.interface`, `code.daemon.manager.gateway`; on at `code.interface.control` and above it | LAYER-007 | PASS |
| 88 | Hide and unhide | `map hide practices-notes`; with `--confirm`; node read; raw; read by name; `map unhide`; hide the intake layer | Caution first; hidden from context and joins, present raw and by name; back after unhide; `Layer intake-… is not hideable.` | LAYER-006, BASE-038 | PASS |
| 89 | Intake layer changes only by correction | `knowledge op=edit layer=<intake> id=<join> purpose=changed`; `op=add-element`; `op=discard` | Each refused, naming `metaform map knowledge op=correct layer=<correction layer> …` | LAYER-004, STORE-032 | PASS |
| 90 | Cycle shapes | `add-join` uplink to route and route to uplink; `add-join` route to route | Both mutual joins stored; self join refused | MAP-002, D11 | PASS |
| 91 | Unknown provider | `add-join … provider=code.nope` | `code.nope is not an element in this project.` `Next: metaform map knowledge op=add-element layer=practices-notes address=code.nope` | STORE-026 | PASS |
| 92 | Property on a join | `add-property … element=join:<id>` | Refused, but the Next line is `… op=add-element layer=practices-notes address=join:3f4e…`, which is not an address | MAP-022; CLI-009: the Next line names a command that works | FAIL, D12 |
| 93 | Query reads | `query`; `query joins … as=receiver`; `query node … raw=true`; `query search POSIX`; with a mask | The read list; results; masked layer absent from `query node` | STORE-028 | PASS |
| 94 | An agent finds where to start | real Claude run 1, see below | The agent found no element: no read lists the map's roots or elements, `map where 1` returns nothing at all, and the instructions name no entry point | MCP-024 steps 4 and 8, MAP-005 | FAIL, D13 |

## Blind-spot challenges

| # | Feature | Command | Observed, trimmed | Spec | Result |
|---|---|---|---|---|---|
| 95 | Answers and approval | layer `challenge.blind` with a new element `code.probe.echo`, its join from the gateway, three challenges; `map answer C3 C`; with `link=element:code.monitor.uplink`; `answer C2 A`; `answer C1 B`; `approve` on A, on C, on an open one, on B | C without a link refused; A, B, C stored; approve refused for A, C and open with `Next: metaform map answer <id> B`; B becomes `plan`; the proposed element and join read as `plan`; a later answer refused as already approved | LAYER-015, STORE-040 | PASS |
| 96 | Open state shown | `map node element:code.manager.roaming` before any answer | `state: None` | LAYER-015: every read shows the state, open included | FAIL, D14 |
| 97 | Direct plan | `knowledge op=add-plan layer=practices-notes element=code.cache.route join=<id>` | `source: direct`; element reads `plan` | STORE-040 | PASS |
| 98 | Approve is a person's act | MCP tool list | `map_answer` listed, `map_approve` absent | LAYER-015, BASE-035 | PASS |

## Memory

| # | Feature | Command | Observed, trimmed | Spec | Result |
|---|---|---|---|---|---|
| 99 | Observations at an element and a join | `memory add-observations element:code.manager.route "…" "…"`; `memory add-observations join:<id> "…"`; `memory open-nodes` both | Both nodes with their observations | LAYER-013, BASE-040 | PASS |
| 100 | Relations | `memory create-relations element:code.guard.switch.gateway "depends on" element:code.manager.route`; open either end | The relation appears opening either node | BASE-040, STORE-020 | PASS |
| 101 | Search | `memory search-nodes ejected`; `… 'packed "delete'` | Finds the node; the quote is not read as query syntax | STORE-020 | PASS |
| 102 | Create entities | `memory create-entities code.idea.future concept`; the same for an existing address | `existing: false` and a new element in the memory layer; `existing: true` | D18 | PASS |
| 103 | Read graph and deletes | `read-graph`; `delete-observations`; `delete-relations`; `delete-entities element:code.monitor.uplink` | Graph grouped by node; each delete reports `deleted: 1`; the element itself remains | BASE-040 | PASS |
| 104 | Memory layer record | `map layers kind=memory`; `query provenance memory` | name memory, kind memory, module memory, the STORE-020 variable, mutable, hideable, ready; no provenance | LAYER-012, STORE-020 | PASS |
| 105 | Bare type address | `memory add-observations type:code x` | Refused: a bare type address is not a node | STORE-015, D74 | PASS |
| 106 | Next line for an unknown element | `memory add-observations element:code.nosuch.node x` | `Next: metaform map knowledge op=add-element layer=memory address=code.nosuch.node`, which writes an element into the memory layer through the knowledge tool | LAYER-012, BASE-038: memory is written by the memory module; the natural next step is `memory create-entities` | FAIL, D15 |

## Correction layers

| # | Feature | Command | Observed, trimmed | Spec | Result |
|---|---|---|---|---|---|
| 107 | Relocation with attachments following | layer `fix-1`, kind correction; `op=correct id=<uplink> address=code.monitor.uplink.direct reason=… evidence=…`; `finish`; node, memory and joins reads; `map history` | Same element id at the new address; the practices property and the memory follow it; its intake join from the gateway is gone; history shows the intake row then `fix-1` `change`; the property applies at `code.monitor.uplink.direct.x` | MAP-015, LAYER-011, STORE-017 | PASS |
| 108 | Receiver change refused | `op=correct layer=fix-a id=<join> purpose="First fix." receiver=code.monitor.uplink reason=r` | Accepted. `receiver=` is silently dropped and the change is written | STORE-034 acceptance 1 | FAIL, D16 |
| 109 | Removal needs its joins removed | `fix-2`: `correct id=<control element> remove=true`; `finish`; add the join removal; `finish` | `Finishing fix-2 would leave join 6940… pointing at removed element 2a4c….` with the exact Next line; then finished at position 2 | STORE-034 | PASS |
| 110 | Orphans | `map element code.interface.control`; `map node element:<id>`; `--raw`; `map joins … as=provider` and `--raw` | Absent in context with `--raw` as the next step; raw returns the descriptor, the POSIX item, the Bash property and the foresight item each with `orphaned: true`; the knowledge join raw only, `orphaned: true` | LAYER-011, STORE-017 | PASS |
| 111 | Put back | `fix-3`: `op=add-element address=code.interface.control`; `finish`; reads | Same element id; the orphaned item, property and knowledge join show again; the intake join a correction removed stays removed | LAYER-011, D80 | PASS |
| 112 | Never toggled | `map mask code fix-3`; `map select`; `map hide --confirm`; `set --layers fix-3` | All refused | LAYER-011 | PASS |
| 113 | Peel | `op=peel layer=fix-1`; `op=peel layer=fix-3`; `discard fix-3`; peel fix-2 and fix-1; `map stack` | `fix-1 is not on top of the stack; the top correction layer is fix-3.` with Next peel fix-3; fix-3 back to building; after peeling all, the stack is empty and both removed joins are current again | LAYER-011, STORE-017 | PASS |
| 114 | Two corrections on one thing | `fix-a` and `fix-b` each change the route join's purpose | Reads show `Second fix.`; history intake, fix-a, fix-b | LAYER-011 acceptance 1 | PASS |
| 115 | Re-examination | `deps-notes` with `sources=["<intake>"]`; after fix-a and fix-b, `map layers`; `map reexamined deps-notes` | `deps-notes` marked; cleared | STORE-036 | PASS |

## Multiple metaforms

| # | Feature | Command | Observed, trimmed | Spec | Result |
|---|---|---|---|---|---|
| 116 | Start over and switch back | `list metaforms`; `add metaform fresh` twice; status; node read; `query has-intake`; `activate metaform nosuch`; `activate metaform main`; compare | `Added metaform fresh to demo; it is now active. …`; duplicate refused; `Metaform: fresh, 2 in project` and the notice; not found; `False`; `No metaform nosuch in demo.`; `Active metaform for demo: main`; the node read is byte-identical and main's store md5 unchanged | MAP-045, STORE-041 | PASS |
| 117 | Map module forms | `map metaforms`; `map add-metaform third`; `map activate main` | Each works | BASE-038 | PASS |

## Export, import and query

| # | Feature | Command | Observed, trimmed | Spec | Result |
|---|---|---|---|---|---|
| 118 | Round trip | `export file=exp1.json`; import into the empty `home2`; export again | `metaforms added: 3`, `layers added: 12`; the two documents are byte-identical; node, raw node and context reads equal across homes | STORE-027 | PASS |
| 119 | Import of existing ids | `import exp1.json` into the same home, twice | `metaforms skipped: 3`, `layers skipped: 12`, nothing added | STORE-027 | PASS |
| 120 | Export all | `export all` | Both projects | STORE-027 | PASS |
| 121 | Layer export and its requires | `export demo metaform=main layer=practices-notes file=…`; import into a home without the map | Only that layer, `requires` of 5; import refused naming the first missing element | STORE-027 | PASS |
| 122 | Layer export without `metaform=` | `export demo layer=practices-notes`; `export layer=practices-notes` | `Error: No layer practices-notes.` although the active metaform holds it | STORE-027 | FAIL, D17 |
| 123 | Unknown schema version | set `schema_version` to 999 in a copy; `list projects` | `… has schema version 999; this Metaform supports version 1.` | STORE-029 | PASS |

## Build and the directly run wheel

| # | Feature | Command | Observed, trimmed | Spec | Result |
|---|---|---|---|---|---|
| 124 | Build | `metaform build` with helloworld and template off | Wheel under `home/builds/<stamp>/`; modules intake, map, mcp, memory only; `Requires-Dist` prompt_toolkit and mcp; entry points for the console script and each module; `Tag: py3-none-any`; `last_build` recorded; cffi, cryptography, pydantic_core, rpds_py and wcwidth each named as compiled and not carried | BASE-022, BASE-041 | PASS |
| 125 | uvx | `uvx --from <wheel> metaform --version` | `metaform 0.1.0` | BASE-041 | PASS |
| 126 | Direct run from its own data folder | `HOME=$MT/fakehome python3.13 -I <wheel>` with no `METAFORM_HOME`: status, help, `add project`, `list modules`, `map knowledge op=create`, memory writes, `query layers`, `export`, `config --show` | `Home: $MT/fakehome/.metaform/wheels/metaform-0.1.0`; every command works; the scratch home is untouched | BASE-023, BASE-042, BASE-024 | PASS |
| 127 | `mcp serve` from a direct run | same, `mcp serve` | `ModuleNotFoundError: No module named 'pydantic_core'`, exit 1, as the build warned | BASE-041 | PASS |
| 128 | Pull a wheel's data | `metaform import wheel=metaform-0.1.0` | Read as a file name: `No file at …/wheel=metaform-0.1.0.` | BASE-025 | FAIL, D18, not built |

## Installer

| # | Feature | Command | Observed, trimmed | Spec | Result |
|---|---|---|---|---|---|
| 129 | Checks and detection of every path | `metaform install` with no terminal and no names | System, Python, uv, Source, then all nine tools found: claude, codex, gemini, vscode by PATH; cursor by `~/.cursor`; copilot and factory by PATH, antigravity by `~/.gemini/config`, claude-desktop by its folder, the last four marked unverified and not offered. `Next: metaform install <tool>... or metaform install all`, nothing changed | MCP-013, MCP-014, MCP-016 | PASS |
| 130 | uv missing | PATH without uv, `install claude` | `uv is not installed; …` `Next: curl -LsSf https://astral.sh/uv/install.sh \| sh`, no file written | MCP-013 | PASS |
| 131 | Unverified or unknown tool | `install copilot`; `install nosuchtool`; `install -- all` | `copilot is not verified yet.`; `nosuchtool is not detected here.`; `all is not detected here.` | MCP-016, CLI-003 | PASS |
| 132 | Install five tools | `install claude codex gemini cursor vscode` | Preview of each command and changed file with the backup folder; the recorded arguments are exactly the MCP-016 forms; Cursor keeps `other` and gains `metaform`; the Cursor backup is byte-identical to the original; six SKILL.md copies, real files, byte-identical to the chassis copy; `Proof: … server starts, 41 tools` for each; `installs` rows; `Next: open your AI tool in a project folder, or run metaform` | MCP-015, MCP-016, MCP-017, MCP-018, MCP-021 | PASS |
| 133 | Re-run | `install all` | One `metaform` entry in Cursor; each command tool gets `mcp remove` then `mcp add` | MCP-019: no duplicate | PASS |
| 134 | Re-run shows what is set up | same | The tool list is the same as a first run; nothing marks the five tools as already set up | MCP-019: the checklist marks tools already set up | FAIL, D19 |
| 135 | Uninstall | `metaform uninstall claude` | `Unknown command: uninstall.` | MCP-020 | FAIL, D18, not built |

## MCP

| # | Feature | Call | Observed, trimmed | Spec | Result |
|---|---|---|---|---|---|
| 136 | Start and instructions | `mcpc.py proj none --instructions --tools` | `metaform 0.1.0`; the MCP-007 base text, one section per surfaced module in id order, then the notice | MCP-002, MCP-007, MCP-009 | PASS |
| 137 | Tool list | same | 45 tools, `<module>_<verb>` plus `set`; no `map_approve`, `mcp_serve` or `helloworld_beep` | MCP-003, BASE-016, BASE-035 | PASS |
| 138 | Schemas | `--schema` for greet, forget, intake_submit, map_node, memory_add-observations, set | `loud` once as boolean; `confirm` only on forget, whose description ends with `Caution: …`; optional `project` and `layers` on every tool; `text` an array for the many noun; the intake schema exactly BASE-039's with `additionalProperties: false` | MCP-003, MCP-005, MCP-025 | PASS |
| 139 | Caution without confirm | `helloworld_forget {}` | `is_error: true`, `Next: If you are sure: call helloworld_forget with confirm true` | MCP-006 | PASS |
| 140 | Boolean false over glue | `--loud` glued on; `helloworld_greet {"name": "mcp", "loud": false}` | `hello, mcp`; `* loud: true  (glued)` afterwards | MCP-005 | PASS |
| 141 | Unknown project and tool | `map_where` with `project: nosuch`; `map_nosuch` | `No project nosuch is registered.` `Next: metaform list projects`; `No tool map_nosuch on this surface.` `Next: metaform help commands` | MCP-025, MCP-004 | PASS |
| 142 | Narrowed surface, mcp kept | `set --modules helloworld,mcp`; new connection | Tools `helloworld_*` and `set` only; `map_where` refused on this surface; `helloworld_wait` works | MCP-004 | PASS |
| 143 | Narrowed surface, spec example | `set --modules helloworld`; start the server | The server exits before initializing: `Error: mcp is not on this folder's command surface.` | MCP-004 How it shows: the connection lists only `helloworld_*` tools | FAIL, D20 |
| 144 | Instructions follow enable and disable | `disable memory`, connect; `enable memory`, connect | `## memory` gone, then back | MCP-007 | PASS |
| 145 | Server outside any project | server in `outside2`: `map_where`; `set {"project": "demo"}`; `map_where`; `map_where` with `project: photos` | Instructions list `Registered projects: demo, photos.` and the register line; `No project for this folder.` `Next: metaform set --project <id>`; after `set`, demo's element; photos' subtype for the one call | PROJ-005, MCP-025, Q15, Q16 | PASS |
| 146 | Concurrent calls, two projects | 10 `map_knowledge op=add-element` calls gathered, alternating `project` demo and photos | No errors; five elements in each project and none in the other | BASE-028, MCP-025 | PASS |
| 147 | First working test steps 8 to 10 | connection 1: `memory_add-observations` at `element:code.daemon.manager.gateway` and at the route join; connection 2: `memory_open-nodes` both; `map_mask` memory at the gateway; `map_node` both; `map_clear`; mask at `code.daemon` with select at the gateway | Both observations read back on the second connection; the mask hides the element's and the join's memory; clear restores both; the select below the mask restores both | MCP-024, LAYER-007 | PASS |
| 148 | `layers` for one call | `map_node` with `layers: ["practices-notes"]` | Only practices-notes; the stored `--layers` stays `all` | CLI-033, Q17 | PASS |

## Real-tool run

`claude` 2.1.282, model reported by the session as claude-sonnet-5. Config `$MT/rt-mcp.json`: one stdio server, `uvx --from <built wheel> metaform mcp serve`, env `METAFORM_HOME=$MT/home`. Flags: `--mcp-config ../rich/rt-mcp.json --strict-mcp-config --setting-sources "" --allowedTools mcp__metaform --disallowedTools Bash,Edit,Write,Read,Glob,Grep,WebFetch,WebSearch,Task,Agent --output-format stream-json --verbose`. Working folder `$MT/rtproj`, registered, with a three-element intake: `stakeholder.cook.home` VE, `code.timer.kitchen` DE, `code.alarm.audible` SE. Transcripts: `$MT/rt.jsonl`, `$MT/rt2.jsonl`, `$MT/rt3.jsonl`.

Run 1 prompt: read the instructions and say what they tell you, check whether the project has an intake, pick one element, write `Manual test note: verified by a real agent run.` there, read it back, report every tool call.

What it did, in order: the server connected with 41 metaform tools. It loaded tool schemas with ToolSearch, then called `intake_status` and got `This project has an intake. Latest intake layer: intake-20260925T170023Z-9745ba`. Looking for an element it called `map_metaforms`, `map_search {"text": "a"}` with no results, `map_children {"address": "1"}` with no results, `map_layers`, `map_where {"address": "1"}` which returned no output at all, `map_element {"element": "1"}` which returned `Error: No element 1 in context here.`, then `map_subtypes {"join": "1"}` and `map_context {"address": "1"}`, both empty. It summarized the instructions correctly: read the map with `map_where` or `map_element` before changing a part, and record what you learn with the memory tools. It stopped without writing: "I couldn't do step 3, because the map has no elements to write to." 14 turns. This is D13.

Run 2, the same prompt plus one clause: "namespace addresses start with a root type: code, document, media, data or stakeholder; map_children lists the next level under an address". It called `intake_status`, then `map_children {"address": "code"}` and got `code.alarm`, `code.timer`. It called `memory_add-observations` with `node: "code.timer"` and got `'code.timer' is not a node: write element:<address or id>, …`; with `element:code.timer` and got `not a current element in this project.` with `Next: metaform map knowledge op=add-element layer=memory address=code.timer`, which it ignored, as it should have; with `subtype:code.timer`, refused. Then `map_children {"address": "code.timer"}` gave `code.timer.kitchen`, and `memory_add-observations {"node": "element:code.timer.kitchen", "text": ["Manual test note: verified by a real agent run."]}` returned `{"node": "code.timer.kitchen", "added": [...]}`. `memory_open-nodes {"node": ["element:code.timer.kitchen"]}` returned `{"nodes": [{"name": "code.timer.kitchen", "entityType": "element", "observations": ["Manual test note: verified by a real agent run."]}], "relations": []}`. `metaform memory read-graph` in rtproj afterwards shows the same note. 10 turns.

Run 3, in the registered project `rtnew` with no intake: asked to quote what the instructions say about the intake and check its state. It quoted the notice word for word, "This project has no intake yet. Have a subagent perform it. Tell the subagent to read its instructions with `metaform intake prompt`, or the `intake_prompt` tool, and to follow them.", and `intake_status` returned `No intake yet. Read the instructions with metaform intake prompt.`

| # | Feature | Observed | Spec | Result |
|---|---|---|---|---|
| 149 | Real host receives the instructions | Run 1 summarized them correctly; run 3 quoted the notice exactly | MCP-024 step 4 | PASS |
| 150 | Real host checks intake state | `intake_status` in runs 1, 2 and 3 | MCP-024 | PASS |
| 151 | Real host writes and reads memory at an element | Run 2 wrote and read back at `element:code.timer.kitchen`; run 1 could not start without the root list, counted in row 94 | MCP-024 steps 8 and 9 | PASS |

## Not built

| # | Feature | Command | Observed | Spec | Result |
|---|---|---|---|---|---|
| 152 | Origins | `metaform add origin`; `metaform list origins` | `add needs: project <id> <path>, or metaform <name>.`; `list needs a noun: projects or modules.` | PROJ-012 to PROJ-014, PROJ-024 | FAIL, D18, not built |
| 153 | Variants | `metaform add variant .` | as above | PROJ-017 | FAIL, D18, not built |
| 154 | Extract | `metaform extract all /tmp/x` | `Unknown command: extract.` | PROJ-018 | FAIL, D18, not built |

## Store rules seen on the way

| # | Feature | Observed | Spec | Result |
|---|---|---|---|---|
| 155 | Wheel data kept apart | After every direct wheel run, `$MT/home` was unchanged and the wheel wrote only under `fakehome/.metaform/wheels/metaform-0.1.0` | BASE-023 | PASS |
| 156 | Layer made without provenance fields | `knowledge op=create layer=noprov variable=x mutable=true hideable=true` succeeds; `query provenance noprov` holds `module: map` and nothing else | LAYER-010 refuses a non-memory layer without provenance. The verb supplies the module, so a record always exists. Consistent with D15; noted, not a defect | PASS |

## Defects

D1. `help modules` is refused. CLI-031's `help` row lists the noun `modules` next to `intro`, `switches` and `agents`, and points to CLI-008, whose indexes are `commands` and `switches`. Either the table means `commands`, a spec typo, or `help modules` should print the module list. Fix: decide which, then make the other agree. Question for the owner.

D2. `metaform help map` pads every verb row to the width of the `knowledge` usage line, about 350 characters, so the page is unreadable in a terminal. The `knowledge` usage also shows `op` and `layer` as optional. Fix: in the module page, cap the left column or print a long usage under its row; render `op=<op> layer=<layer>` as required in the `knowledge` usage.

D3. The help page of a verb outside this system does not say where it runs. BASE-016 says `metaform help <module> <verb>` and running the verb both print `<module> <verb> runs on <systems>.` with the next step `metaform help <module>`; only running it does. Fix: add that line to the verb page when the verb's `supported_os` excludes this system.

D4. Verb pages list optional nouns under the heading `Switches`, for example `metaform help intake submit` and `metaform help map knowledge`. CLI-029 has a Switches section for switches; BASE-043 says record fields are nouns, not switches. Fix: print optional nouns under their own heading, such as `Nouns`, and keep `Switches` for settings the verb reads.

D5. An empty section is printed. `metaform help template` shows a `Verbs` heading with nothing under it. CLI-029: empty sections are left out. Fix: skip the heading when the module declares no verbs.

D6. `metaform list modules` prints no summary for an off module: `helloworld  off    system`. BASE-037 gives every line `<summary or reason>`. The summary needs an import, which an off module does not get. Fix: read `summary` without importing, for example as a source literal beside `SUPPORTED_OS`, or print a reason such as `off: metaform enable helloworld`.

D7. `set` and `unset` report by comparing values, not stored state. `set --no-loud` from the default stores `false` and prints `Success: no changes`; `config --show` then shows `loud: false  (set)`. `unset all` clears that stored `false` and prints `No settings required reset`. `unset --loud --unglue` on a glued `false` prints `No settings required reset` and `Unglued: loud` while it deletes the value. CLI-017 lists every setting reset; CLI-015 says `set --no-name stores false`. Fix: report a key as updated when its stored row or state changes, and as reset when a stored row is deleted, whatever the value.

D8. `set … folder=<path>` prints the narrowing lines without naming the folder. CLI-022: "stores the same value for that folder and prints the same lines, naming the folder." Fix: add the folder to the first line, for example `Success: updated 1 key for <path>`.

D9. Settings cannot be given on one CLI call to a module verb unless the verb declares them. `metaform map node … --layers foresight-notes` fails with `map node has no switch --layers.`; `metaform map where code --project demo` fails the same way; `helloworld greet z --layers practices` too. CLI-011 says every setting can be passed on one call, CLI-033 acceptance 2 tests `--layers` on one call, and CLI-021, BASE-028 and MCP-025 describe `--project <id>` per call on the CLI. Over MCP both work. Fix: accept the chassis context settings `--project` and `--layers` on every module verb as per-call values, the same way the MCP server adds `project` and `layers` to every tool. The build log lists `--layers` on one CLI call as untested.

D10. The settings screen shows rows as `project = demo default` and list values as `[]`. CLI-026: each row `key: value` with `*` for glued and `(set)` for set; CLI-031's value rule shows an empty list as `(none)`, or `all` for `modules`. Fix: use the `config --show` row format in the screen. Staging, preview and save were not driven here; the build log already notes the screen tests call methods instead of keys.

D11. `metaform map layers` prints one JSON line. CLI-033 shows one aligned row per layer: name, kind, module, tags, ready or building, on or off, and STORE-036 expects the re-examine mark to be visible there. Fix: give `layers` a readable text form and keep the JSON for `--json`. The same applies to `map stack` and `map metaforms`.

D12. Some Next lines name commands that cannot work. `add-property … element=join:<id>` suggests `op=add-element … address=join:<id>`, which is not an address. `memory add-observations element:<unknown>` suggests `map knowledge op=add-element layer=memory …`, D15. Fix: when the target is not an element, say a property attaches only to an element and name `metaform map where <address>`.

D13. An agent cannot find where the map starts. No read lists the map's roots or its elements: `map children` needs an address, the instructions do not name the roots, `map where` on an empty address returns no output at all over MCP, and `map search` searches item values only. In real run 1 a Claude agent tried eight reads, found nothing, and gave up with a map of three elements in place. With one clause naming the roots it succeeded at once. MCP-024 step 8 has an agent write memory at an element, and MAP-005 says an agent orients without reasoning. Fix, any one: let `map children` with no address return the roots in use; add the root list, or the AUE and DE addresses, to the map module's instructions or to the `intake_status` result; make `map where` return `No element or subtype at <address>.` with a Next line such as `metaform map children <parent>`. Also in run 2, `map children` did not say which children are elements, so the agent wrote to `code.timer` three times before going one level down.

D14. An unanswered challenge shows no state. `map node` returns `state: None` for an open challenge. LAYER-015 and STORE-040 say every read shows the state, open included. Build question Q1 records the cause: nothing marks a layer as a blind-spot layer. Fix after Q1 is answered: show `open` for an item of a blind-spot layer with no state row.

D15. The memory module's error for an unknown element steers agents to write elements into the memory layer through the knowledge tool: `Next: metaform map knowledge op=add-element layer=memory address=…`. That command succeeds. LAYER-012 and BASE-038 have the memory layer written only by the memory module, and D18 gives `memory create-entities` for a name the map does not hold. Fix: make the Next line `metaform memory create-entities <address> <type>`, and consider refusing knowledge writes to a layer of kind memory.

D16. A correction that asks to change a join's receiver is accepted. `op=correct … id=<join> purpose="First fix." receiver=code.monitor.uplink reason=r` writes the purpose change and drops `receiver=` without a word; with `receiver=` alone the error is `Name at least one field to change.` STORE-034 acceptance 1: a correction with the key `receiver` is refused. The receiver did not change, so the map stays sound, but the agent is told nothing. Fix: in `correct`, refuse every noun that is not an allowed field for the thing's kind, naming the key, before writing.

D17. `metaform export demo layer=practices-notes` fails with `No layer practices-notes.` when the project has more than one metaform, though the active metaform holds the layer. With `metaform=main` it works. STORE-027 lets `layer` limit any export. Fix: with `layer=` and no `metaform=`, look the layer up in each exported metaform and export the ones that hold it; report a layer only when no metaform holds it.

D18. Not built, as the build log says: `metaform import wheel=<name>-<version>` BASE-025, `metaform uninstall` MCP-020, and the history commands `add origin`, `list origins`, `add variant`, `list variants`, `extract` and `export origin=` PROJ-010 to PROJ-024. `import wheel=…` is read as a file path. Fix: build them, or mark them deferred in the records.

D19. A re-run of `metaform install` does not show which tools are already set up; it lists tools exactly as a first run does and then replaces each entry. MCP-019 says the re-run shows the current state and marks tools already set up, and replaces an entry only when the user chooses update. Fix: read the `installs` table and mark those tools `set up` in the tool list and preview; the build log defers repair, D41.

D20. Narrowing a folder to modules that leave out `mcp` stops the MCP server from starting in that folder. MCP-004's own example, `metaform set --modules helloworld`, then a new connection, gives `Error: mcp is not on this folder's command surface.` and the host sees the connection close. MCP-004 says that connection lists only `helloworld_*` tools. Narrowing is how an orchestrator steers a worker, so a worker narrowed to `workflow,memory` would lose MCP entirely. Fix: let `mcp serve` run whatever the surface, as `help`, `set`, `unset` and `config` do, and keep filtering the tools it serves; or make CLI-022 say that `mcp` must be in `--modules` and warn in the narrowing `set` output when it is left out.

## Other observations, not counted

- `map joins` returns joins in id order, not the order the intake gave them. No record sets an order.
- The first import into an empty home reported `things skipped: 6`. Those look like second versions of things changed by correction layers; the reads matched, so no data was lost.
- Over MCP, `set` returns JSON, `{"updated": [...], "glued": false}`, while the CLI prints the CLI-022 text. BASE-036 allows that for a result.
- `list metaforms` does not pad names, so the created column does not line up.
- A layer created with `op=create` and no provenance fields gets a provenance record with `module: map`, row 156. If LAYER-010 means the caller must supply provenance, this needs a decision.
