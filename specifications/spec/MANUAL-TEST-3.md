# Manual test of the chassis build, third round

Date: 2026-09-26. Branch `chassis` at commit `0f2157b` when this run began; two commits landed on the branch during this session, `b0a36ee` and `1160159`, both spec and test files only, test review round 3's reports and a build question, no change to `src/metaform`, confirmed by `git show --stat`. Tester: a Claude agent, by hand, as a user and as an AI agent would use Metaform. No code was changed; this file is the only file added.

Scope: only what changed since round two, `specifications/spec/MANUAL-TEST-2.md`: step 19 of `specifications/spec/BUILD-LOG.md`, atomic report writes N1, an owned metaform skipped on import STORE-027, tool schemas carry each noun's and switch's help MCP-003, type-ignore reasons L8, not manually testable, and the two Windows fixes noted at the end of the log: UTF-8 on every stream regardless of the pipe's encoding, and the installer's proof starting a full path, which is not exercised here since it needs a Windows-style launcher fake.

## Setup

- `MT` is the scratch folder `/tmp/mt3`. Every command ran with `METAFORM_HOME` pointed at one of `$MT/home`, single project `demo`; `$MT/home2`, projects `proja`, `projb`, `projc`; `$MT/home3`, project `projd`; or `$MT/mcphome`, projects `rtproj` and `rtnew`, as named below. The real `~/.metaform` was never created and `~/.metaform.pre-chassis*` was never touched.
- The CLI ran as `/home/rich/metaform/.venv/bin/python -m metaform`, written below as `metaform`.
- The elements array for the kitchen-timer fixture was written to `$MT/elements.json` from `tests/fixtures/intake_timer.json`'s `elements` field, per round two's own note that `intake submit elements=` wants the array itself, not the whole fixture object.
- The full pytest suite ran first, unmodified, from the repository root with `METAFORM_HOME` pointed at a scratch home: `417 passed` in about 5 minutes, no failures. This is 3 more than round two's `414 passed`, matching step 19's three added tests.
- The real-tool run built the wheel with `metaform build` into `$MT/buildhome`, wrote `$MT/rt-mcp.json` with one stdio server, `uvx --from <wheel> metaform mcp serve`, env `METAFORM_HOME=$MT/mcphome`, and ran `claude -p ... --model sonnet --mcp-config $MT/rt-mcp.json --strict-mcp-config --setting-sources "" --allowedTools mcp__metaform --disallowedTools Bash,Edit,Write,Read,Glob,Grep,WebFetch,WebSearch,Task,Agent --output-format stream-json --verbose` from `rtproj`, flags exactly as given in the task. Transcript: `$MT/rt1.jsonl`.
- `metaform mcp add` was never run and no real tool configuration file was touched.

## Result

12 checks: 11 pass, 1 fail. The failure is a new finding, not previously tracked in `BUILD-LOG.md`, `REVIEW-CODE-3.md`, `TEST-REVIEW-3.md` or `BUILD-QUESTIONS.md`. Two further things were noticed but are not counted as failed checks, kept in "Other observations" at the end, for the same reason round two kept its MCP schema note there: not required by the letter of any record.

## Feedback and reports

| # | Feature | Command | Observed | Spec | Result |
|---|---|---|---|---|---|
| 1 | Concurrent feedback writes, text survives, N1 | 8 separate OS processes started together, each `metaform feedback "<distinct text>" layer=<the intake layer>` | All 8 processes reported the same run id, the layer's own id; the file grew to 717 bytes with all 8 dated sections present; a second batch of 6 more processes against the same file, 843 bytes, still all present | BASE-045, STORE-043 | PASS |
| 2 | `read report` after concurrent writes | `metaform read report <run>-feedback.md` | Full text returned, byte for byte; all 8 markers present, then all 14 after the second batch, decoded as UTF-8 | BASE-045, STORE-043 | PASS |
| 3 | `list reports` size after concurrent writes | `metaform list reports`, then `stat -c%s` on the actual file | Listed size 207 bytes; actual file 717 bytes. Repeated with a second batch: listed 843, actual 1095. The DB row for the file is stale under real concurrency, though the file itself and `read report` are both fully correct | STORE-043 | FAIL, new finding |

Check 3: `reports.write` computes `target.stat().st_size` right after its own append and hands that number to `store.save_report`, which does `INSERT ... ON CONFLICT(report_id) DO UPDATE SET size=excluded.size`. Under real concurrent processes, whichever process's database commit lands last decides the stored `size`, and that process's own `stat()` call can predate other processes' later appends, so the row can under-report the true size by a wide margin. This is not the same bug N1 fixed. The file's content is never lost, and every write is durably in the file and returned whole by `read report`. Only the `size` column that `list reports` shows can go stale. No acceptance test in STORE-043 or BASE-045 covers size accuracy under concurrency, and the only automated test for this area, `test_writes_to_one_file_at_the_same_time_all_survive`, passes `project=None`, the one case STORE-043 itself says has no store and so writes no row at all, per `TEST-REVIEW-3.md`'s own finding 1. This gap is real but untested by anything in the suite.

## Export and import

| # | Feature | Command | Observed | Spec | Result |
|---|---|---|---|---|---|
| 4 | Import into a different registered project | Export `proja` from `$MT/home2`; `metaform import <file> projd` into `$MT/home3`, where `projd` is registered but does not hold that metaform and nothing else in that home owns it | `metaforms added: 1`, `layers added: 1`, `things added: 9`, exit 0; `list projects` still shows `projd` at its own path `$MT/projD`; `map roots` in `projd`'s folder reads back the whole intake map | STORE-027 | PASS |
| 5 | Import meeting a metaform another project owns | Export `proja`; `metaform import <file> projb`, same home, `home2`, where `proja` already owns that metaform id | `metaforms added: 0`, `metaforms skipped: 1`, exit 0, no error; `Notice: metaforms.<id>: Metaform <id> belongs to project proja here; nothing of it was written. To add what it holds to that project: metaform import <file> proja`; no folder was even created under `home2/projects/projb` | STORE-027, BASE-044 | PASS |
| 6 | Ordinary reimport still works after the owner-conflict fix | `metaform import <file> projd` a second time, into the project that already holds it | `metaforms skipped: 1`, `layers skipped: 1`, exit 0, no notice | STORE-027 | PASS |

## MCP tool schemas and the real-tool run

| # | Feature | Command | Observed | Spec | Result |
|---|---|---|---|---|---|
| 7 | Every noun and switch carries a description | A real `tools/list` call against `metaform mcp serve` on a mapped project, 46 tools, every property of every module-verb tool checked | Every noun and switch property of every module-verb tool carries a non-empty `description`; confirmed across all 46 tools with no exceptions among module verbs | MCP-003 | PASS |
| 8 | `map_knowledge`'s `op` lists its values | Same `tools/list` call, `map_knowledge` tool's `op` property | `description`: "create, add-element, add-join, add-subtype, add-property, add-item, add-ref, add-plan, edit, remove, correct, finish, peel or discard." | MCP-003 | PASS |
| 9 | Real host builds a knowledge layer with no wrong `op` guesses | `claude -p` from `rtproj`, prompt: create a small knowledge layer, add one item and one property at the kitchen timer element, finish it, read it back, report every tool call | See below. 9 tool calls, every `map_knowledge` call's `op` correct on the first try: `create`, `add-item`, `add-property`, `finish`. Round two's run needed five wrong guesses at `op` before finding `add-item`; this run needed none | MCP-003 | PASS |

Run 1 prompt: create a small knowledge layer named `agent-notes3` on the kitchen timer element, add one item and one property there, finish it, read it back, and report every tool call in order.

What it did: `ToolSearch` to load the four tool schemas it expected to need, `map_roots`, `map_search "kitchen timer"`, then `map_knowledge {"op": "create", "layer": "agent-notes3", "kind": "layer", "variable": "..."}`, refused once for missing required nouns, `Error: knowledge op=create needs mutable, hideable.` It added `mutable: true, hideable: true` and the call succeeded at once, no further `op` confusion. It then called `add-item` correctly on the first try with `node: "element:code.timer.kitchen"`, `add-property` correctly on the first try with `element: "code.timer.kitchen"`, `finish`, and read the layer back with `map_layer`. 9 tool calls, no `op` guessed wrong at any point, one ordinary required-noun refusal on `create` that named exactly what was missing.

One thing the agent itself flagged in its own summary, not asked for and not part of this check: it passed `key: "language"` to `add-property`, and the property came back with no key, just the bare value `"C"`. It correctly diagnosed that `add-property`'s schema does not declare `key`, only `add-ref` does, and that Metaform accepted the argument without error and silently dropped it. Reproduced directly on the CLI: `map knowledge op=add-property layer=agent-notes3 element=code.timer.kitchen key=mytestkey value='"D"'` stores the property with `extra: ` empty and no notice, `key` gone. This differs from round two's check 45, where a name that is not a noun of any operation goes into `extra` with a notice; `key` is a real noun of the `knowledge` verb, just not one `add-property` reads, so nothing catches it. This is not part of step 19's four changes and is not a new regression; it is a genuine, reproducible gap, kept here as an observation rather than a numbered failure because it was not one of the round three task's named checks, and because BASE-043's own wording, "an unknown name before `=` is kept in the record's extra, with a notice," is written for a name unknown to the verb, not one that is a real noun elsewhere in the same verb's other operations.

## Output encoding

| # | Feature | Command | Observed | Spec | Result |
|---|---|---|---|---|---|
| 10 | `set` under a cp1252 pipe | `PYTHONIOENCODING=cp1252 metaform set --debug` | Exit 0; stdout `Success: updated 1 key\n  debug: false → true\n`, the arrow's UTF-8 bytes `e2 86 92`, decodes clean as UTF-8 | QUAL-002 | PASS |
| 11 | `intake prompt` under a cp1252 pipe | `PYTHONIOENCODING=cp1252 metaform intake prompt` | Exit 0; 28707 bytes, decodes clean as UTF-8; contains an em dash and the subset symbol `⊂`, neither in cp1252 | QUAL-002 | PASS |
| 12 | `help map` under a cp1252 pipe | `PYTHONIOENCODING=cp1252 metaform help map` | Exit 0; 4256 bytes, decodes clean as UTF-8; this particular page's text happened to hold no non-ASCII characters in this build, so it exercises the exit-0 path but not the encoding path the same way the other two do | QUAL-002 | PASS |

Note on check 10: the task named `metaform set` plainly. Run with no switch at all, `metaform set` always exits 2, `Error: set needs at least one setting switch.`, regardless of encoding; that is CLI-009's ordinary usage error, not an encoding failure, and it is not what QUAL-002's fix is about. `set --debug` is the same call round two used to exercise a real settings write, and it is what actually prints the arrow character the Windows fix was written for, so that is what is reported above. `--debug` was turned back off afterward with `metaform set --no-debug`.

## Other observations, not counted

- `feedback`, `list_reports` and `read_report`'s own tool schemas, the chassis tools built by hand in `modules/mcp/server.py`'s `CHASSIS` dict rather than from a module's verb declaration, carry no `description` on any of their properties: `text`, `layer`, `report`, `shape`, `kind`, `limit`, `after`, `name`. MCP-003's requirement is written for "every verb of every module," and these three are chassis verbs, not module verbs, so this is not a violation of MCP-003 as written; the `set` tool's own settings properties, built the same way from `settings.SCHEMA`, do all carry descriptions, since `setting_schema` runs every one through the same `_described` helper the module verbs use. This is the same kind of gap round two's own note about `map_knowledge`'s `op` described before the fix: real, live, and not required by the letter of any record.
- The `key=mytestkey` finding above.

## Defects: this round

No entry in `specifications/spec/OPEN-QUESTIONS.md` or `BUILD-QUESTIONS.md` currently names either new finding. Check 3, the `list reports` size going stale under real concurrent writes to the same file, is the one counted failure of this round. The `key=` noun silently dropped on `add-property` and the chassis tools' undescribed schema properties are kept as observations, not failures, for the reasons given where each is discussed above.
