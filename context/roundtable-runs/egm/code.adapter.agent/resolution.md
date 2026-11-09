# Resolution of review findings — `code.adapter.agent` (OpenRouter ACP adapter)

## Method and scope

I read the description (`element.md`) and all five source files copied into
`source/adapters/openrouter-acp/src/`: `adapter.ts`, `models.ts`, `tools.ts`,
`index.ts`, `sdk-patch.ts`. Line-by-line verification of every code claim made by
the reviewers is in `ShadowMortar-evidence.md`.

The code is the ground truth for this review: the reviewers read "the description
above and the code", and the findings' central claims check out, subject to the
GF4 confinement qualification below. GF1's citation of `crates/roundtable-web/src/tables.rs:76-99` is
**not** in the provided `source` folder and cannot be verified here; it is
supplementary, not load-bearing, for that finding.

**Headline decision: all ten findings are Right.** The code is consistent and its
non-obvious behaviours are already explained in its own comments; what is wrong,
stale, or vague is the **description** (`element.md`). **Every fix is to the
description. No source-code change is required to resolve any finding** (the one
optional code considerations, GF4, are noted below). Related findings share edits;
the consolidated six-step plan below avoids applying the same correction twice.

| # | Severity | Verdict | Fix lives in |
|---|---|---|---|
| GF1 | Blocker | Right (one citation unverifiable) | `element.md` investigations |
| GF2 | Blocker | Right | `element.md` wants (client) |
| GF3 | Blocker | Right | `element.md` wants (gateway) |
| GF4 | Major | Right | `element.md` elephant.built (+ optional code) |
| GF5 | Major | Right | `element.md` new ACP-surface section |
| GF6 | Major | Right | `element.md` investigations (same edit as GF1) |
| GF7 | Major | Right | `element.md` elephant.gaps |
| GF8 | Major | Right | `element.md` elephant.gaps |
| GF9 | Nit | Right | `element.md` wants (same edit as GF3) |
| GF10 | Nit | Right | `element.md` properties |

---

## GF1 — Blocker, investigations "build or reuse" — **Right**

**Why.** `element.md:46` says the adapter is "(to be built …)" and "Which to build
first is not yet decided". That is contradicted by (a) the code itself:
`createAdapter` in `source/adapters/openrouter-acp/src/adapter.ts:118-301` is a
complete ACP implementation, with `index.ts` wiring it to stdio; and (b)
`element.md:70` (`elephant.built`) which says it *is* built. The description is
internally inconsistent about the element's current status.

Two caveats that keep this honest:
- The claim that the adapter is "listed first in the harness catalog
  (`crates/roundtable-web/src/tables.rs:76-99`)" cannot be checked from the provided
  source folder; that file is absent. The finding stands without it, because the
  source and `elephant.built` already prove the adapter exists. The editor should
  confirm that catalog line before repeating the "listed first" detail.
- `investigations` are point-in-time notes. The right resolution is to mark the
  build-vs-reuse question **resolved**, not to claim the old observation was always
  false.

**What to change.** Replace the `investigations` note (`element.md:46`) with a
resolved statement, e.g.: *"Two routes were considered: Pi + pi-acp (existing) and
this adapter around the OpenRouter Agent SDK. The adapter was built
(`adapters/openrouter-acp`, see `elephant.built`); one adapter serves every model
id that passes the catalog filter in `models.ts`. The build/reuse question is
therefore settled. Note the later owner decision recorded in `elephant.gaps`
(2026-11-06): the author's account reports that the owner preferred OpenCode for
OpenRouter models. This does not establish usage frequency or retirement."*
This single edit also resolves GF6.

---

## GF2 — Blocker, wants relied on by `code.client.agent` — **Right**

**Why.** `element.md:17` claims the adapter "Serves the ACP agent side for **any**
OpenRouter model id". The code does not:
- `fetchModelOptions` (`models.ts:43-80`, filter at `:66-68`) keeps only catalog
  models whose `supported_parameters` contains `"tools"` **and** whose `endpoints`
  contains `"/api/v1/responses"` (`models.ts:20`). There is no built-in list; the
  catalog is fetched per session (`models.ts:4-5`).
- `session/set_config_option` rejects any value not in that set
  (`adapter.ts:245-251`).
- `session/new` fails outright if `openrouter/auto` (`INITIAL_MODEL`,
  `models.ts:17`) is not in the filtered catalog (`adapter.ts:214-219`).

"Any" is an overclaim: arbitrary or filtered-out ids are refused. The filtering is
deliberate and correct (a model without tool support or without the Responses
endpoint would fail on the first prompt — `models.ts:38-41`), so the code should not
change.

**What to change.** Qualify `element.md:17` to say the adapter serves the ACP agent
side for the OpenRouter model ids it offers, i.e. those passing the catalog
filter (`tools` + `/api/v1/responses`); `session/set_config_option` rejects any
other value, and `session/new` requires `openrouter/auto` to be present. Keep the
`send_receive` intent. This is the fix; do not "fix" the code to accept all ids.

---

## GF3 — Blocker, wants `upstream.gateway.llm` "Routes chat completions" — **Right**

**Why.** The code never uses chat completions. `runTurn` calls `callModel`
(`adapter.ts:150-161`) with an `input_text` payload — the OpenRouter **Responses**
format — and `models.ts:19-20` records the endpoint as `POST /api/v1/responses`.
A grep of all five source files finds no `chat/completions`. The word "chat
completions" in the description is also a leftover from the old Python path: the
`archaeology` layer (`element.md:55`) says Python "called OpenRouter models directly
through chat completions, outside ACP". The ACP adapter replaced that with the SDK's
Responses calls, so the description mixes the retired and current call paths.

**What to change.** Rewrite the `upstream.gateway.llm` `Function` (`element.md:20`)
to reflect the Responses endpoint and the SDK, e.g. *"Routes model inference to the
selected provider model via the OpenRouter Responses endpoint
(`POST /api/v1/responses`); inference is invoked through the OpenRouter Agent SDK.
The adapter separately fetches the model catalog directly."* Also
reconcile with GF9 (below). No code change.

---

## GF4 — Major, `elephant.built` "keeps its file tools inside the session folder" — **Right**

**Why.** `element.md:70` states a containment guarantee that is only partly true and
therefore misleading. Verification:
- `read_file`, `list_directory`, `write_file` validate paths: `resolveInRoot`
  (`tools.ts:113-125`) does lexical + symlink-aware resolution (including dangling
  links, `:71-100`) and `openResolved` uses `O_NOFOLLOW` (`:135-146`); `write_file`
  re-checks after the permission round-trip (`:411-415`). These checks reject
  lexical escapes and symlink escapes on a stable filesystem. They are not a
  race-proof confinement guarantee: `O_NOFOLLOW` protects only the final path
  component, parent directories can change after validation, and listing uses
  pathname-based `fs.readdir` (`:367`).
- `run_command` is **not** covered by that statement. `runShell` (`tools.ts:254-306`)
  runs `/bin/sh -c` with `cwd` = session root but **no path confinement** (the
  command can reference any absolute path), **no time limit** (explicit at `:252`),
  withholds **only** `OPENROUTER_API_KEY` from the environment
  (`WITHHELD_ENV`, `:34`, `:257`) — so *other* environment secrets are exposed to
  model-run shell commands — and on cancel kills the whole process group with
  `SIGKILL` (`:277-287`). `write_file` and `run_command` both call
  `session/request_permission` first (`needsPermission:true` at `:396`, `:443`;
  lifecycle `:204-229`). All accurate.

**What to change — narrow the claim, do not negate it.** The reviewer's finding is
right that the statement is incomplete. The three file tools have real path
checks, but their confinement claim needs the filesystem-race qualification above;
the shell has no such checks. Writing "the adapter does not check paths" would *understate* real,
careful protections and could mislead a maintainer into "fixing" working code. Make
`elephant.built` precise instead of a blanket claim, e.g.:
*"…It rejects client-supplied MCP/tool servers. Its three file tools (read_file,
list_directory, write_file) check paths against the session folder using symlink-aware
resolution (including dangling links), with O_NOFOLLOW on read/write final components and write_file re-checking
after the permission prompt; the fourth tool, run_command, runs `/bin/sh -c` in the
session folder but is **not** path-confined, has no time limit, withholds only
OPENROUTER_API_KEY from the environment (other environment secrets remain visible
to model-run commands), and is killed as a process group on cancel; write_file and
run_command require client permission **per invocation, not per session**."*

A concrete probe discriminates the two readings (verified against the code): in a
session rooted at `/root/s`, `read_file` with `../../etc/passwd` is refused by the
lexical check in `resolveInRoot` (`tools.ts:114-117`) inside `prepare`
(`tools.ts:336`) before any permission prompt — no `tool_call` reaches
`in_progress` — whereas `run_command` with `cat /etc/passwd` **succeeds once the
client grants permission and host filesystem permissions permit the read**, because its `prepare` (`tools.ts:445-451`) does no path
resolution. (Precision: a `tool_call` "pending" notification is emitted at
`tools.ts:194-197` before `prepare` in both cases; only the `in_progress` update at
`:231` is never reached for the refused read.) The security-relevant fact to record
is that this adapter's shell gate is a selected `allow` permission response on each
call. The ACP client supplies that response; the source does not establish that a
human must click. Host OS permissions and any external sandbox still apply.

**Permission granularity.** `createTools` is rebuilt on every `session/prompt`
(`adapter.ts:158`, inside `runTurn`), and `lifecycle` issues
`session/request_permission` with `allow_once` / `reject_once` on **every** call
(`tools.ts:204-229`, options at `:216-219`). So the gate is per tool invocation,
not a session-wide grant; a model can prompt repeatedly. The description must say
so, or a reader will assume a stronger, cached control than exists.

**Code:** no change is required to resolve this finding — the behaviour is
intentional and documented in `tools.ts`. But the editor should be aware that if
"keeps its file tools inside the session folder" was meant as a real security
property, the code has a genuine gap (unconfined `run_command`, no timeout, one-key
env filtering, and file-path races); adding stronger isolation or a timeout would
be a *separate design/code task*. A session-wide permission grant is not a
confinement fix and would broaden authorization rather than strengthen isolation.

---

## GF5 — Major, whole document — undocumented ACP surface and limits — **Right**

**Why.** All nine items are real, externally visible behaviours of the code, none of
which appear anywhere in `element.md`:

| Limit | Evidence |
|---|---|
| Implements ACP **v1** | `adapter.ts:3` |
| `loadSession: false` | `adapter.ts:176` |
| no MCP over HTTP or SSE | `adapter.ts:178` (`mcpCapabilities:{http:false,sse:false}`) |
| prompts accept only `text` and `resource_link` | `adapter.ts:76-90` (`promptToText`, default throws) |
| one turn at a time per session | `adapter.ts:259-261` |
| `OPENROUTER_API_KEY` required | `adapter.ts:127-136`, called `:186`,`:258` |
| `additionalDirectories` refused | `adapter.ts:196-198` |
| SDK's hour-long retry disabled | `adapter.ts:229-231` (`retryConfig:{strategy:"none"}`) |
| new session starts on `openrouter/auto` | `models.ts:17`, used `adapter.ts:224` |

A functional map "records what each part must do … and knowledge about it"
(`element.md:3`), so the advertised ACP contract (capabilities, limits, required
env, turn model) belongs here; a reader of the current description cannot know any
of it.

**What to change.** Add a concise "ACP surface / contract" section (or a new `acp`
layer) to `element.md` capturing the table above, prioritising the externally
visible contract (ACP v1, capabilities advertised in `initialize`, one-turn model,
`OPENROUTER_API_KEY`, model selection/filter, default model). It should be a short
structured summary, not a paste of every implementation detail. No code change.
This edit overlaps GF2 (model filter) and GF7 (MCP/tool servers); keep them
consistent.

---

## GF6 — Major, comprehension — investigations vs elephant — **Right**

**Why.** `element.md:46` says "to be built" and the route is "not yet decided"
between Pi and this adapter; `element.md:70` says built; `element.md:73` records the
owner's 2026-11-06 decision to move OpenRouter models to OpenCode. Three layers
give three different impressions of status, leaving the element's state unclear.

**What to change.** Same single edit as GF1: resolve the investigation note, record
that the adapter was built, and cross-reference the OpenCode decision in
`elephant.gaps`. Do not leave the stale "not yet decided" text alongside it.

---

## GF7 — Major, comprehension — `elephant.gaps` undefined terms — **Right**

**Why.** `element.md:72` says seats "get no Roundtable tools, because it refuses
tool servers". Neither term is defined, and a reader cannot tell what is refused or
what is lost. The code is concrete: `session/new` rejects any non-empty `mcpServers`
(`adapter.ts:190-194`, "this adapter does not connect to client-supplied MCP
servers") and `initialize` advertises `mcpCapabilities:{http:false,sse:false}`
(`adapter.ts:178`). The only tools a seat gets are the four built-ins in
`tools.ts:455` (`read_file`, `list_directory`, `write_file`, `run_command`).

**What to change.** Define the terms in `elephant.gaps`: "tool servers" = client-
supplied MCP servers, which `session/new` rejects (`adapter.ts:190-194`) and which
the adapter does not advertise (`adapter.ts:178`); "Roundtable tools" = the
harness-provided tools delivered over MCP, which these seats therefore cannot use;
they get only the adapter's four built-in tools when created with `mcpServers: []`.
If the client instead supplies servers, session creation fails rather than silently
creating a seat without those tools. When stating that `run_command` is
permission-gated, add **per invocation, not per session** (see GF4) — `createTools`
is rebuilt each prompt (`adapter.ts:158`) and `allow_once` is requested each call
(`tools.ts:216-219`), so there is no cached session grant. No code change.

---

## GF8 — Major, comprehension — `elephant.gaps` quote and status — **Right**

**Why.** `element.md:73` uses the undefined name "ori" and the vague "rarely used",
without saying whether the adapter is still selectable, by whom, or whether it is
kept or retired. The description gives no way to answer those questions.

**What to change.** Remove the informal quote; the supplied materials do not define
"ori", so do not invent an expansion. Attribute the OpenCode preference to the
author's account. Replace "rarely used" with a sourced concrete status
statement (still selectable / kept as a fallback / retired, and who can choose it).
Note: whether it remains in the harness catalog is the `tables.rs` claim from GF1,
which cannot be verified from the provided source — the editor should check that
file before asserting selectability. Until verified, say: "The adapter implementation
remains present; current selectability, usage frequency, and retention or retirement
policy are not established by this snapshot." No code change.

---

## GF9 — Nit, comprehension — wants gateway + SDK — **Right**

**Why.** `element.md:19-21` lists two wants: `upstream.gateway.llm` ("Routes chat
completions", `send_receive`) and `upstream.sdk.agent` ("agent loop, tool execution
and conversational state", `receive`), without saying whether OpenRouter is called
directly or only through the SDK. The code resolves the ambiguity: the adapter
constructs `OpenRouter` from `@openrouter/agent` with a custom `HTTPClient`
(`adapter.ts:226-232`) and calls `callModel` (`adapter.ts:150`) for inference.
However, `fetchModelOptions` directly calls `fetchImpl` for the OpenRouter catalog
(`models.ts:49-53`), including pagination. Inference goes through the SDK on the
Responses endpoint; catalog retrieval goes directly through the supplied fetch.

**What to change.** With GF3, collapse the ambiguity: state that this element reaches
OpenRouter inference via `@openrouter/agent`'s `callModel` (Responses endpoint),
with a separate direct catalog GET;
describe the gateway want as the OpenRouter inference service and the SDK want as
the agent loop/tools/state, and drop "chat completions". Keep both wants if the map
needs them, but make the direct-vs-SDK relationship explicit. No code change.

---

## GF10 — Nit, comprehension — properties undefined — **Right**

**Why.** `element.md:8` `"package": "agent host library: separate ACP agent binary
(reusable)"` and `:11` `"role": "SE"` are undefined labels; the document never
explains "agent host library" or what "SE" denotes. They are accurate only to
someone who already knows the project's vocabulary.

**What to change.** Define packaging as a separately launched ACP stdio agent
process with a reusable TypeScript `createAdapter` factory. Expand `SE` using the
map's authoritative role legend, link that definition, or remove the code if optional.
Calling `SE` a "role code" alone does not explain its meaning; the supplied files
do not establish its expansion. No code
change.

---

## Consolidated edit plan for `element.md`

1. **Investigations** (`element.md:46`) — resolve build/reuse; adapter built;
   cross-reference the OpenCode decision. *(GF1, GF6)*
2. **Wants** (`element.md:17,19-21`) — qualify "any model id" with the catalog
   filter; replace "chat completions" with the Responses endpoint; state that
   inference uses the SDK while catalog fetching is direct. *(GF2, GF3, GF9)*
3. **elephant.built** (`element.md:70`) — **narrow, do not negate**: describe the real
   path checks of the three file tools with their race limitation, add an explicit non-confinement sentence for
   `run_command`, and state the permission gate is per invocation, not per session.
   *(GF4)*
4. **elephant.gaps** (`element.md:72-73`) — define "tool servers"/"Roundtable
   tools"; remove unexplained "ori"; give sourced status or explicitly record it
   as unverified. *(GF7, GF8)*
5. **New ACP-surface section/layer** — ACP v1, advertised capabilities, prompt
   types, one-turn model, required key, refused params, retry policy, default
   model. *(GF5, consistent with 2 & 4)*
6. **Properties** (`element.md:8,11`) — define or drop "agent host library" and
   "SE". *(GF10)*

## On the code

**No source change is required to resolve these description findings.** The
description must accurately record the implementation's limits. GF4 identifies
possible future code work: shell isolation, timeout/environment policy, and
race-resistant file access if strict filesystem confinement is required. Existing
comments establish intended behavior; they do not prove the absence of bugs.

## Unverifiable item to confirm before publishing

GF1's "listed first in the harness catalog (`crates/roundtable-web/src/tables.rs:
76-99`)" — that file is not in the provided `source` folder. Verify it in the full
repo before repeating the claim or using it to answer GF8's "still selectable"
question. It does not affect the verdict on GF1.

CrypticComet's additional source-based corrections to the shared decisions are
documented in `CrypticComet-evidence.md`: direct catalog access, file-path race
limits, permission-response semantics, and unsupported status/terminology claims.
