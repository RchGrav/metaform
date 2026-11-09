# ShadowMortar — code-verification evidence for the 10 findings

Ground truth = the 5 files under `source/adapters/openrouter-acp/src/`:
`adapter.ts` (302 lines), `models.ts` (81), `tools.ts` (456), `index.ts` (28), `sdk-patch.ts` (49).
`crates/roundtable-web/src/tables.rs` (cited by GF1) is **not** present in the provided
`source` folder, so that one supporting claim cannot be checked here.

## Verification table

| # | Reviewer's code claim | Verified? | Exact evidence |
|---|---|---|---|
| GF1 | `adapters/openrouter-acp/src/adapter.ts` exists | YES | file present (302 lines); `createAdapter` at :118 |
| GF1 | listed first in harness catalog `tables.rs:76-99` | UNVERIFIABLE | file absent from source folder |
| GF1 | contradicts `elephant.built` | YES | element.md:70 says built; :46 says "to be built" / "not yet decided" |
| GF2 | only models with `tools` + `/api/v1/responses` offered (`models.ts:36-71`) | YES | filter at :66-68; `AGENT_ENDPOINT="/api/v1/responses"` :20; `fetchModelOptions` :43-80 |
| GF2 | `set_config_option` rejects other values (`adapter.ts:245-251`) | YES | :246 `!session.models.some(...)` -> invalidParams |
| GF2 | `session/new` fails if `openrouter/auto` missing (`adapter.ts:214-219`) | YES | :214 `INITIAL_MODEL` check; `INITIAL_MODEL="openrouter/auto"` models.ts:17 |
| GF3 | SDK `callModel` uses Responses, not chat completions | YES | adapter.ts:150-161 `callModel` + `input_text`; models.ts:19-20 `/api/v1/responses`; grep found no `chat/completions` anywhere |
| GF4 | read/list/write confined (`tools.ts:113-125,135-146,411-415`) | YES | `resolveInRoot` :113-125, `openResolved` O_NOFOLLOW :135-146, write re-check :411-415 |
| GF4 | `run_command` = `/bin/sh -c` in cwd, no path confinement, no time limit (`248-264`) | YES | `runShell` :254-306; comment "There is no time limit." :252; spawn :259-264 |
| GF4 | only `OPENROUTER_API_KEY` withheld | YES | `WITHHELD_ENV=["OPENROUTER_API_KEY"]` :34; loop :257 |
| GF4 | cancel kills whole process group (`277-287`) | YES | `process.kill(-child.pid,"SIGKILL")` :281 |
| GF4 | write_file + run_command ask permission (`204-229`, `431-453`) | YES | `needsPermission:true` :396/:443; `requestPermission` :205-220 |
| GF5 | ACP v1 (`adapter.ts:3`) | YES | comment :3 |
| GF5 | `loadSession:false`; no MCP http/sse (`173-183`) | YES | :176, :178 |
| GF5 | prompts only text + resource_link (`76-90`) | YES | `promptToText` :76-90, default throws |
| GF5 | one turn per session (`259-261`) | YES | :259-261 |
| GF5 | `OPENROUTER_API_KEY` required (`127-136`) | YES | `apiKey()` :127-136, called :186 & :258 |
| GF5 | `additionalDirectories` refused (`196-198`) | YES | :196-198 |
| GF5 | SDK hour-long retry off (`229-231`) | YES | `retryConfig:{strategy:"none"}` :231 + comment :229-230 |
| GF5 | new session starts `openrouter/auto` (`models.ts:17`) | YES | `INITIAL_MODEL` :17, used adapter.ts:224 |
| GF6 | investigation "to be built"/undecided vs elephant built+OpenCode | YES | element.md :46 vs :70, :73 |
| GF7 | "Refuses tool servers" / "Roundtable tools" undefined | YES (description) | element.md :72; code: mcpServers rejected adapter.ts:190-194, mcpCapabilities false :178 |
| GF8 | "ori" undefined; "rarely used" vague | YES (description) | element.md :73 |
| GF9 | wants list gateway(chat completions) + SDK without direct/SDK clarity | YES (description) | element.md :19-21 |
| GF10 | "agent host library", role "SE" undefined | YES (description) | element.md :8, :11 |

## Cross-cutting conclusions

1. **Every code claim in all 10 findings is accurate** (one citation, `tables.rs`, is
   outside the provided source and cannot be checked; it is supplementary to GF1).
2. The code is internally consistent and its unusual behaviours are *documented in
   comments* (e.g. `runShell` no-time-limit, `resolveReal` symlink handling,
   `retryConfig` rationale, `sdk-patch.ts` floating-promise fix). So the code is the
   ground truth; the **description (`element.md`) is what is wrong/stale/vague**.
   => All fixes are description-side. No code change is required to resolve any finding.
3. Findings group into four edits, so the editor does not double-apply:
   - GF1 + GF6  -> stale `investigations` note.
   - GF3 + GF9  -> the two `wants` (gateway vs SDK) and "chat completions" wording.
   - GF2        -> "any OpenRouter model id" overclaim in the client want.
   - GF4 + GF5 + GF7 + GF8 + GF10 -> elephant.built/gaps, a new ACP-surface section,
     and undefined properties/terms.
4. Genuinely notable subtleties worth surfacing in the resolution:
   - GF4 also implies a real security property gap: `run_command` inherits the whole
     `process.env` except one key, so *other* secrets in the environment are exposed to
     model-run shell commands. That is a limitation, not a documentation error.
   - GF3's "chat completions" is also historically loaded: `archaeology` (element.md :55)
     says the old Python path called chat completions directly. The new adapter moved to
     the Responses API, so the description mixes the old and new call paths.
   - `investigations` are point-in-time notes; the correct fix is to mark the question
     *resolved*, not to assert the old observation was always false.
