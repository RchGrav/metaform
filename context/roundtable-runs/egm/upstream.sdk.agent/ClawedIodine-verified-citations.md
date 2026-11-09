# ClawedIodine — verified citation table for `upstream.sdk.agent`

Independent re-verification of every finding's code claims against `source/adapters/openrouter-acp/`.
All line citations below were confirmed by reading the files. `element.md` was not modified.

| Finding | Claim | Code evidence | Verdict |
|---|---|---|---|
| GF1 | SDK ships no file/shell tools; adapter defines 4 | `tools.ts:1-9` (explicit comment), `createTools` `tools.ts:318-456` (read_file/list_directory/write_file/run_command) | Right (wording overstates) |
| GF1 | State in adapter memory via StateAccessor; lost on close; no load | `adapter.ts:144-149` (load/save → `session.state`), `:176` `loadSession:false`, `:290-294` delete on close | Right |
| GF1 | SDK defines state *contract* | `adapter.ts:27,59` `ConversationState`, `:150-159` `callModel({state})` | Nuance: SDK defines type+contract, adapter owns storage |
| GF2 | Monkey-patches private method; hard-fails if absent | `sdk-patch.ts:30-48` (`ModelResult.prototype.startTurnBroadcasterExecution`), `:37-41` throw; `adapter.ts:33,36` import+call at load | Right, undocumented |
| GF3 | Exact pins | `package.json:25-26` `@openrouter/agent 1.0.1`, `@openrouter/sdk 0.13.67` | Facts right |
| GF3 | Custom fetcher + retries off | `adapter.ts:226-232` `new HTTPClient({fetcher})`, `retryConfig:{strategy:"none"}` | Facts right; finding states no discrepancy (weak as Major) |
| GF4 | Only `/api/v1/responses` + `tools` models | `models.ts:19-20` `AGENT_ENDPOINT`, `:64-71` filter on `supported_parameters`+`endpoints` | Right |
| GF4 | Incomplete reason → ACP stop/error | `adapter.ts:92-106`: `max_output_tokens`→`max_tokens`, `content_filter`→`refusal`, else `internalError` | Right |
| GF5 | Only adapter src imports `@openrouter/agent` | `adapter.ts:30`, `tools.ts:14`, `sdk-patch.ts:24` (grep confirms); manifest only lists it | Right (confirmation, no change); snapshot cannot prove project-wide absence |
| GF6 | "rarely used / superseded by OpenCode" | `grep -rin opencode source/` → 0 hits; only `references` is design doc §7.3 (identifiers, not in snapshot) | Reject as stated — unsourced |
| GF7 | Refuses MCP servers / extra dirs | `adapter.ts:190-198` `mcpServers` + `additionalDirectories` rejected; `:176-179` mcpCapabilities false | Right |
| GF7 | File tools confined to session root | `tools.ts:113-125` `resolveInRoot` | Right for file tools; NOT a sandbox for `run_command` (`tools.ts:254-263`) |
| GF8 | No package/language/version in properties | `element.md` properties = name/name_length/uri only; `package.json:2-3,6,14-15,25-26` | Right |
| GF9 | No investigations/decisions; `gaps: []` unexplained | `element.md` has only `references`/`elephant` layers, `gaps: []` | Right (empty list ≠ no evaluation) |

## Additional gap no finding raised
`references` cites design doc §7.3 "models are selected by their published identifiers", but
`models.ts:43-80` fetches the catalog live per `session/new` and filters it — the reference is
about the `model` config option, not the SDK element, and the doc is not in this snapshot. Re-scope
it; record in the investigations layer whether the SDK's own docs were consulted.

## Net recommendation
Change `element.md` only (never code) for GF1, GF2, GF3, GF4, GF7, GF8, GF9; no change for GF5;
reject GF6 as stated. GF1/GF7 and GF3/GF8 overlap — resolve each pair with a single coherent edit.
