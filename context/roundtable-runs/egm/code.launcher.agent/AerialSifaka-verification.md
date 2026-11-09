# AerialSifaka — independent verification of the 12 findings

I independently read the supplied `launch.rs` (339 lines) and checked every finding
against it. Verdict: **all 12 findings are correct**. I verify each below with the
line that decides it, then make two refinements to the draft resolution
(LoyalAtlas-resolution-draft.md / resolution.md) that sharpen it.

## Per-finding verification (line citations to the copy)

| # | Verdict | Deciding lines |
|---|---|---|
| GF1 | Right (Blocker) | `LaunchSpec` is a value: `new` 29-36, `from_command_line` 39-43, `display` 45-50. No `std::process`, no `Stdio`. Spawn is elsewhere. |
| GF2 | Right | `HarnessEntry` has only `id`/`name` (64-65); `builtin()` hard-codes 4 ids (85-88). `custom` (235-238) returns one entry; `autoselect` (214-232) never merges customs. |
| GF3 | Right | Branch order in `parse_registry_with` 117-133: installed binary first (117-125), then acpr (126-127), then package (128-130), then binary-unavailable (131-133). So the no-acpr npx/uvx path covers package entries only. |
| GF4 | Right | `registry_env_allowed` 181-185: denies PATH/NODE_OPTIONS/NODE_PATH/PYTHONPATH/PYTHONSTARTUP/BASH_ENV/ENV/HOME + LD_/DYLD_/NPM_CONFIG_ prefixes. Matches the finding exactly. |
| GF5 | Right | `REGISTRY_URL` 12; merge-when-reachable + fallback note 214-232; `available = which(command)` 195-199. |
| GF6 | Right (Nit) | Pins 85-88; `split_words` 240-272: quotes only, no escapes, unbalanced quote → `None` (265-267). |
| GF7 | Right | `autoselect` (214) is fetch-and-merge; returns all entries with `available`/`note`; never picks one. "autoselection" overpromises. |
| GF8 | Right | `acpr` used at 97, 127, 132 but never defined in the description. |
| GF9 | Right | Precedence nowhere in the description; "catalog aliases" has no referent; user-command entry point (`from_command_line`/`custom`) not described. |
| GF10 | Right, partly | Registry-unreachable → `(builtin(), note)` (230); missing launcher → `available:false` + note (195-199, 132) are here. Spawn/handshake failure is in `code.client.agent`. |
| GF11 | Right (Nit) | No machine scan; `which` only confirms `acpr` (97) or a registry/supplied-named binary (151-157). |
| GF12 | Right (Nit) | `REGISTRY_URL` 12; fetch-on-every-call, no cache (216). |

## Refinement 1 — GF1: the "wants" section records a deliverable, not the consumer's action

The draft's GF1 fix is right but can be stated more precisely. In `element.md` the
`code.client.agent` want reads: "Resolves the harness to a launch command **and spawns
it with stdio for newline-delimited JSON-RPC**". The structural error is not merely that
spawning lives in another file; it is that the wants sentence describes the **consumer's
own downstream action** instead of the **deliverable**. The want should name only what
this element hands over — a `LaunchSpec` (command + pre-split args + env overlay +
env_remove) — and explicitly say that spawning with stdio is the *receiver's* function.
This is the cleanest phrasing because it removes the false claim without inventing
behaviour.

## Refinement 2 — GF7: reconcile the name with the kept function name

Rename the element ("Harness resolution and catalogue") but keep `autoselect` as the
function name. `resolution.md` should state in one line why this is consistent: the
"select" in `autoselect` refers to selecting the *set of options to offer* (the
catalogue), not choosing a single winner — choice is the chair's job, recorded in the
neighbouring elements. This prevents a future contributor from "fixing" the function to
choose.

## A note the draft already has, which I confirm

GF5 and GF12 both cite `REGISTRY_URL`; resolve them in one place. The URL,
merge rule, fallback note and `available`/`note` semantics belong in a single "How
selection works" section.

## Runnable verification of GF4 and GF6

I reimplemented `registry_env_allowed` (181-185) and `split_words` (240-272) in a
small executable (ghm file not included; logic copied verbatim) and ran it:

- **GF4** — denied: `PATH, path, NODE_OPTIONS, PYTHONPATH, HOME, LD_PRELOAD,
  DYLD_INSERT_LIBRARIES, NPM_CONFIG_REGISTRY`; allowed: `AGENT_MODE, MY_VAR, FOO`.
  Confirms case-insensitive exact set + `LD_/DYLD_/NPM_CONFIG_` prefixes.
- **GF6** — `node ''` → `['node','']` (empty quoted word kept); `node "my agent.js"
  --flag 'a b'` → 4 args (quotes group); `node 'open` → `None` (unterminated quote is
  an error); `node a\ b` → `['node','a\\','b']` (backslash is ordinary, no escape).
  Confirms quotes-only, no escapes, unbalanced quote fails.

Both findings are therefore not just read but executed, and hold.

### Follow-up execution (final round) — a new GF6 edge, and acceptance of corrections

LoyalAtlas's GF6 caveat is right: `node a\ b` → `['node','a\\','b']` proves the **absence** of escape handling, but does not by itself prove the splitter is otherwise shell-correct. Execution evidence must not be read as more than it shows.

I then executed the mixed-quote and apostrophe cases he flagged as untested:

- `"it's"` → `["it's"]` (apostrophe preserved inside double quotes)
- `'say "hi"'` → `['say "hi"']` (double quotes preserved inside single quotes)
- `node "a b" 'c d'` → `['node','a b','c d']`
- `node ''` → `['node','']` (empty quoted arg kept)

- `node it's` → **None** (unterminated quote)

The last case is a new, checkable finding for GF6: because the `(None, '"' | '\'')` arm (launch.rs:249) opens a quote on *every* apostrophe, an **unpaired apostrophe in a bare word** (`it's`, a filename with an apostrophe, a possessive) closes nothing, and the whole line errors as "unbalanced quotes". So the splitter's limitation is not only "no escapes" — it is "the apostrophe is always a delimiter, so bare apostrophes break parsing." This strengthens the GF6 doc note: it is not just that `'` groups words, but that there is no way to express a literal apostrophe in an unquoted word. This is a concrete, reproducible argument for documenting the splitter rather than assuming it is shell-correct.

I accept LoyalAtlas's correction to refinement 1 in full: the wants defect is **misattributed ownership inside one sentence**, not "deliverable vs consumer action"; a wants section recording consumer needs legitimately uses consumer verbs (as `code.roster.participant`'s "Lists registered harnesses…" shows). The final want text is the same either way; only the stated diagnosis differs.

### FrigidBravo's shadowing prediction — confirmed by execution

I replicated `builtin()` (85-88) and `autoselect`'s merge (223-227) and fed them a registry document whose `opencode` entry is binary-only, with acpr missing and the binary absent from PATH. Result:

- Merged ids: `['opencode','claude-acp','codex-acp','pi-acp']`
- The built-in npx fallback `opencode-ai@1.19.5` is **absent** — `"Any npx fallback for opencode present?" → False`
- The surviving `opencode` entry is `available:false` with note `"binary distribution: install acpr to launch it"` — nothing mentions the shadowed fallback.

So FrigidBravo's claim is exactly right: a built-in whose id the registry reuses is silently dropped even when the registry entry is itself unavailable. GF3/GF5/GF9's merged precedence text must state this consequence ("a built-in is dropped when the registry reuses its id, even if the registry entry is unavailable"), or the promise in the comment at launch.rs:212-213 ("so common harnesses are always offered") is false in exactly this case.
