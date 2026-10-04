# Manual test of the chassis build, fourth round

Date: 2026-09-25. Branch `chassis` at commit `7b232f1` for this whole run, no commits made or needed during the session. Tester: a Claude agent, by hand, as a user and as an AI agent would use Metaform. No code was changed; this file is the only file added.

Scope: only the three fixes named in step 20 of `specifications/BUILD-LOG.md`, drawn from round three's one failure and two gaps: `list reports` now keeps the largest recorded size under concurrent writes, STORE-043; a noun a knowledge operation does not read is kept in the new record's `extra` with a notice, or named as ignored when the operation adds no record, BASE-043 and BASE-044; and `feedback`, `list_reports` and `read_report` now carry a description on every property, MCP-003, checked here together with `set`'s own schema.

## Setup

- `MT` is the scratch folder `/tmp/mt4`. Every command ran with `METAFORM_HOME` set to `/tmp/mt4/home`, one registered project `demo` at `/tmp/mt4/proj1`. The real `~/.metaform` was never created and `~/.metaform.pre-chassis*` was never touched.
- The CLI ran as `/home/rich/metaform/.venv/bin/python -m metaform`, written below as `metaform`.
- The elements array for the kitchen-timer fixture was written to `/tmp/mt4/elements.json` from `tests/fixtures/intake_timer.json`'s `elements` field, then submitted with `metaform intake submit elements=/tmp/mt4/elements.json`, giving the intake layer used for the feedback checks.
- The full pytest suite ran once, unmodified, from the repository root with `METAFORM_HOME` pointed at a separate scratch home, `/tmp/mt4/testhome`: `420 passed` in about 9 minutes, no failures.
- The MCP checks used the `mcp` package's own client, `ClientSession` over `stdio_client`, from a script run with `/home/rich/metaform/.venv/bin/python`, launching `metaform mcp serve` as a subprocess with `METAFORM_HOME=/tmp/mt4/home` and the project folder as its cwd. No server ran on a fixed port; the transport is stdio. `metaform mcp add` was never run and no real tool configuration file was touched.

## Result

6 checks: 6 pass, 0 fail. 0 defects found.

## Feedback and reports

| # | Feature | Command | Observed | Spec | Result |
|---|---|---|---|---|---|
| 1 | Concurrent feedback writes for one run and kind, text survives, `list reports` size matches the file on disk | 8 separate OS processes started together, each `metaform feedback "<distinct text>" layer=<the intake layer>`, then a second batch of 6 more against the same run; `metaform list reports` and `stat -c%s` on the actual file after each batch | All 14 processes across both batches reported the same run id. After the first batch the file held all 8 markers at 589 bytes and `list reports` showed 589; the actual file was 589 bytes, exact match. After the second batch the file held all 14 markers at 1056 bytes, `list reports` showed 1056, and the actual file was 1056 bytes, exact match. `read report` returned the full text, all 14 markers present, byte for byte. | STORE-043, BASE-045 | PASS |

## Unread nouns on the knowledge verb

| # | Feature | Command | Observed | Spec | Result |
|---|---|---|---|---|---|
| 2 | `op=add-property` given a noun the operation does not read, on the CLI | `metaform map knowledge op=add-property layer=agent-notes4 element=code.timer.kitchen value='"C"' key=mytestkey` | Exit 0. Result's `extra` field: `{"key":"mytestkey"}`. Printed notice: `Notice: key: op=add-property does not read key; it was kept in the record's extra.` | BASE-043, BASE-044 | PASS |
| 3 | `op=finish` given a noun the operation does not read, on the CLI | `metaform map knowledge op=finish layer=agent-notes4 reason=done` | Exit 0. The layer's `ready` field was set, so `finish` ran; no `extra` field exists on a layer result to hold it. Printed notice: `Notice: reason: op=finish does not read reason; it was ignored.` | BASE-043, BASE-044 | PASS |
| 4 | `op=add-property` given the same unread noun, as a raw MCP tool call | `map_knowledge` called with `{"op": "add-property", "layer": "agent-notes4-mcp", "element": "code.timer.kitchen", "value": "D", "key": "mytestkey-mcp"}` through the `mcp` package's `ClientSession` against `metaform mcp serve` | `is_error` false. Result JSON: `"extra": {"key": "mytestkey-mcp"}`, `"notices": [{"where": "key", "message": "op=add-property does not read key; it was kept in the record's extra."}]` | BASE-043, BASE-044, MCP-003 | PASS |
| 5 | `op=finish` given the same unread noun, as a raw MCP tool call | `map_knowledge` called with `{"op": "finish", "layer": "agent-notes4-mcp", "reason": "done"}` through the same client | `is_error` false. Result JSON: `"ready": "2026-09-26T01:16:43Z"`, `"notices": [{"where": "reason", "message": "op=finish does not read reason; it was ignored."}]` | BASE-043, BASE-044, MCP-003 | PASS |

## MCP tool schema descriptions

| # | Feature | Command | Observed | Spec | Result |
|---|---|---|---|---|---|
| 6 | `feedback`, `list_reports`, `read_report` and `set` carry a description on every property | A real `tools/list` call against `metaform mcp serve`, checked for each of the four tools' `inputSchema.properties` | `feedback`: `text`, `layer`, `report`, `shape`, `project`, all with a description. `list_reports`: `kind`, `layer`, `limit`, `after`, `project`, all with a description. `read_report`: `name`, `project`, both with a description. `set`: `project`, `modules`, `layers`, `debug`, `report`, `intake_file`, `raw`, `glue`, all with a description. No property of any of the four tools was missing one. | MCP-003 | PASS |

## Defects: this round

None. All three fixes from step 20 held under the checks run here.
