# CrypticComet — corrections to the shared resolution

These are static source findings, not claims of executed integration tests. They
preserve the ten accepted findings while correcting overstatements introduced
during discussion.

1. **OpenRouter access is not exclusively through the SDK.**
   `source/adapters/openrouter-acp/src/models.ts:49–53` directly invokes
   `fetchImpl(url, { headers: ... })` against `MODELS_URL`, defined at line 9 as
   `https://openrouter.ai/api/v1/models`. Pagination repeats that path. Only
   inference is delegated to SDK `callModel` (`adapter.ts:150–161`). GF3/GF9 must
   distinguish direct metadata retrieval from SDK-mediated inference.

2. **Symlink checking is not atomic filesystem isolation.**
   `tools.ts:113–125` validates a resolved pathname; `openResolved` later opens
   it by pathname (`135–137`). Its `O_NOFOLLOW` flag (`127–128`) protects the
   final component. If a parent directory is renamed and replaced by a symlink
   after validation and before open, that parent can still be followed. Directory
   listing similarly calls pathname-based `fs.readdir` (`367`). The write recheck
   (`413`) narrows the window after permission but does not make the subsequent
   mkdir/open atomic. Document effective path checks without claiming race-proof
   confinement. Shell non-confinement remains independently established by
   `spawn('/bin/sh', ['-c', command], { cwd, ... })` (`259–264`).

3. **Permission means a client response, not proof of human interaction.**
   `tools.ts:217` defines option ID `allow`, with kind `allow_once`. The check at
   `221–222` requires outcome `selected` and option ID `allow`; it does not compare
   the returned ID with `allow_once`. Each invocation requests permission. The
   adapter does not prove whether the client prompts a human or applies policy.
   A session-wide grant would broaden authorization and is not a security fix.

4. **MCP rejection can prevent a seat from starting.**
   `adapter.ts:190–195` rejects nonempty `mcpServers`. The four local tools are
   available in sessions successfully created with an empty list; servers are not
   silently ignored.

5. **Unknown facts should remain unknown.**
   The snapshot has no definition of `ori` or `SE`, no harness catalog, and no
   usage data or retirement policy. Do not expand either abbreviation by guess,
   repeat “rarely used” as a measured fact, or infer retirement from the reported
   OpenCode preference. The TypeScript entry point proves implementation presence,
   not current UI selection or production deployment.

No source behavior was changed. The corrections are in `resolution.md` so the
requested deliverable remains complete and does not depend on this supplement.
