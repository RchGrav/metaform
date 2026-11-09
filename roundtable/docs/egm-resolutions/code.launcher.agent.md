# Resolution — review findings for `code.launcher.agent`: ACP autoselection

Consolidated adjudication by the roundtable (LoyalAtlas, AerialSifaka,
FrigidBravo, AcuteMotor). Evidence basis: `source/crates/acp-host/src/launch.rs`
(the only file copied into `source/`), plus a permitted read of
`code.client.agent/process.rs:61-85` for GF1. Findings that cite `tables.rs`
(GF2) could not be fully checked against that file; the conclusion stands on
`launch.rs` alone and the unverified location is tagged below. Working artifacts:
`AcuteMotor-analysis.md` (precedence diagrams), `AerialSifaka-verification.md`
(runnable checks), `LoyalAtlas-resolution-draft.md` (per-finding citations).

**Group verdict: all 12 findings are upheld.** No finding requires a code
change; every remedy is a clarification of `element.md`. Supporting references
are consolidated at the end.

## Interpretation note (applies to GF1, GF2, GF9)
The "their wants" bullets read `goal / Function / Intent: receive`. Because the
intent is `receive`, the `Function` line is what the dependent receives **from
this element** — i.e. a claim about this element's behaviour. Both
egm-codebase-details findings (GF1, GF2) use that reading, so I apply it
consistently. If the map instead intends `Function` to be the dependent's own
job, then GF1/GF2 are misreadings; **under either reading the remedy is the
same**: make the description unambiguous so it does not appear to claim that
this element spawns processes or lists user commands.

---

## GF1 — Blocker, egm-codebase-details (their wants: code.client.agent)
> launch.rs does not spawn or set up stdio; it only builds LaunchSpec (14-51).
> Spawning is process::spawn (process.rs:61-85), part of code.client.agent.

**Decision: RIGHT** (the code fact is solid; the description overstates scope).
**Why.** `LaunchSpec` (14-51) is pure data (`command`, `args`, `env`,
`env_remove`); `parse_registry_with`, `autoselect`, `custom` only construct
`HarnessEntry`/`LaunchSpec`. There is no `Command`, no `Stdio`, no spawn in
launch.rs. Read as a statement of what this element provides, the `Function`
line "Resolves the harness to a launch command **and spawns it with stdio for
newline-delimited JSON-RPC**" claims a behaviour the code does not have; that
spawning lives in `code.client.agent`/`process.rs`, as GF1 states. The same
loose wording appears in `elephant.design`: "Find and **start** agents ...",
which reads as spawning while the module doc (1-5) means "how to launch them".
**Change: description (two sites) + source doc comment.** The wants sentence
credits *both halves* of `code.client.agent`'s action to this element when only
the resolve half is delivered here: the piped-stdio half comes from
`process::spawn` (process.rs:61-85:
`.stdin(piped()).stdout(piped()).stderr(piped())`, with `env_remove` applied
before `env`). Keep the consumer-action form of the wants section (its native
form — the sibling `code.roster.participant` want is also a consumer verb), but
state that the deliverable is only a `LaunchSpec` (command, pre-split args, env
overlay, env_remove) and that spawning with piped stdio is the receiver's
function. Reword `elephant.design` "start" -> "resolve the launch command for",
and add an explicit scope note "this element resolves and lists; it does not
spawn". **Second site:** the `LaunchSpec` doc comment at launch.rs:14
("How to start one ACP agent process") asserts the same claim inside the source
and must be corrected too. **Leave the module doc (launch.rs:1-5) alone** —
"find the harnesses ... and how to launch them" is accurate. No functional code
change.

## GF2 — Major, egm-codebase-details (their wants: code.roster.participant)
> No 'catalog aliases' exist; user-supplied commands are not listed:
> `launch::custom` (235-238) is used only for the OpenRouter adapter
> (tables.rs:88); seat commands bypass launch.rs via `from_command_line`
> (tables.rs:107-108).

**Decision: RIGHT** (verifiable in launch.rs; the tables.rs line numbers are
unverifiable here but not needed for the conclusion).
**Why.** `autoselect()` (214-232) returns only registry entries plus builtins
whose id is absent. `custom()` (235-238) is a standalone constructor for **one**
`Source::Custom` entry and is never called by `autoselect`, so this element does
not *list* user-supplied commands. There is no alias concept anywhere: the
`Source` enum is `Registry | Builtin | Custom` (53-59) and builtin ids are plain
ids (`claude-acp`, `codex-acp`, ...); "catalog aliases" has no counterpart. Thus
the want's Function "Lists registered harnesses, **catalog aliases** and
**user-supplied ACP commands**" describes two things the element does not do.
**Change: description only.** Correct that Function line to "Lists registry and
built-in harnesses; turns a user-supplied command line into a single
`LaunchSpec` via `custom()`/`from_command_line` (assembly/listing of user
commands is done by the roster/tables layer, not by `autoselect`)". Define
"catalog aliases" if it is a real feature elsewhere, otherwise remove the term.
No code change.

## GF3 — Major, egm-codebase-details (elephant: built / gaps)
> An installed registry binary on PATH takes precedence over acpr (117-127);
> without acpr, binary-only entries are unavailable unless installed (128-133),
> so 'start through npx or uvx directly' covers package entries only.

**Decision: RIGHT.**
**Why.** In `parse_registry_with` the branches are ordered: installed binary
(117-125) is checked *before* `acpr` (126); with no acpr, package entries fall
through to direct `npx`/`uvx` (128-130) but a binary-only entry (131-133) gets
no `launch` and `available=false`. The `elephant.gaps` sentence "registry agents
start through npx or uvx directly" is therefore true only for **package**
distributions. The launch.rs tests confirm it (`installed_registry_binaries_are_launchable`,
`parse_registry_with` assertions).
**Change: description only.** Amend `elephant.gaps` to: "Without `acpr`,
registry **package** entries (npx/uvx) are launched directly; **binary-only**
entries are unavailable unless the binary is already on PATH (an installed
binary runs directly and takes precedence over `acpr`)". Optionally record in
`Layer elephant / references` the two precedence rules above. No code change —
the behaviour is deliberate and tested.

## GF4 — Major, egm-codebase-details (missing security rule)
> Registry-supplied env is filtered: PATH, NODE_OPTIONS, NODE_PATH, PYTHONPATH,
> PYTHONSTARTUP, BASH_ENV, ENV, HOME and LD_/DYLD_/NPM_CONFIG_ prefixes are
> refused (168-185); undocumented.

**Decision: RIGHT, and important.**
**Why.** `package_launch` (168-176) applies `registry_env_allowed` (181-185),
which refuses exactly that deny-list plus the `LD_`, `DYLD_`, `NPM_CONFIG_`
prefixes, because the registry is a remote document (comment 170-171). The
element.md description says nothing about it. This is a **security boundary**
(preventing a remote registry from changing what code the child loads or how it
finds programs) that a maintainer or reviewer must be able to see in the map;
omitting it is more than a cosmetic gap, so Major is fair. Test
`registry_cannot_set_loader_or_path_variables` (322-330) pins it.
**Change: description only.** Add a security-rule note: "Registry `env` values
are accepted except for PATH, NODE_OPTIONS, NODE_PATH, PYTHONPATH,
PYTHONSTARTUP, BASH_ENV, ENV, HOME and any LD_/DYLD_/NPM_CONFIG_ key; this
stops a remote registry from altering the child's loader/path." No code change.

## GF5 — Major, egm-codebase-details (missing logic)
> Undocumented: REGISTRY_URL (12); built-ins merged when registry reachable,
> whole built-in catalog + note when not (214-232); availability via `which`
> on the command (195-199).

**Decision: RIGHT** (real documentation gap; slightly overstated as "Major").
**Why.** All three behaviours exist in code: `REGISTRY_URL` const (12);
`autoselect` merges builtins not already listed on success and returns
`builtin()` + a "registry unavailable" note on failure (220-231); `entry()`
computes `available` with `which::which(&spec.command)` (195-199). None is in
element.md. The availability rule *is* self-documented in the code
(`HarnessEntry.available` comment, 70-71) and the merge rule in the `autoselect`
doc comment (212-213), so this is a map/description gap, not missing code.
**Change: description only.** Add to `Layer references`/a knowledge note:
the registry URL; that on reachability the registry catalog is used and builtins
are appended only where ids are missing, and on failure the whole built-in
catalog is used with a note; and that `available` reflects whether the launcher
(`npx`/`uvx`/`acpr`/binary) is on PATH. No code change.

## GF6 — Nit, egm-codebase-details (built entries)
> Pinned built-in versions not stated (claude-agent-acp 0.101.0, codex-acp
> 2.5.0, pi-acp 0.0.34, opencode-ai 1.19.5; 85-88); command-line splitter
> handles quotes, no escapes (240-272).

**Decision: RIGHT** (small, accurate).
**Why.** `builtin()` (84-89) pins exactly those four versions;
`elephant.built` lists the four harnesses but no versions. `split_words`
(240-272) groups words with `'` / `"` and rejects unbalanced quotes, but has no
backslash/escape handling (a `\` is an ordinary char); test
`command_lines_split_on_whitespace_and_respect_quotes` (332-338) confirms.
Both are undocumented. **Change: description only (optional, nit).** Record the
four pinned versions (they matter for reproducibility) and note the splitter
supports quotes but not escapes. No code change.

## GF7 — Major, egm-comprehension (name)
> 'ACP autoselection' misdescribes the element; it resolves and spawns what the
> chair selected and lists options, and nothing is auto-selected.

**Decision: RIGHT** (the title misdescribes the element; the remedy is the
title only, not a change to the code).
**Why.** `autoselect()` (214-232) is fetch-and-merge: one GET on `REGISTRY_URL`,
then `parse_registry` plus every `builtin()` whose `id` is not already present
(223-227). It returns `(Vec<HarnessEntry>, Option<String>)` — an offer set plus
a diagnostic — never a single chosen entry, and nothing in `launch.rs` reads
`available` to pick a winner. `HarnessEntry` (62-74) carries no rank/score/
selected field. So "auto-selection" imports a promise of *choice* the code does
not make, and the map title is a comprehension hazard. Note two caveats the
finding's wording gets wrong, recorded so they are not "fixed" later: (a) the
element does **not** spawn (GF1 places spawn in `code.client.agent`/process.rs);
(b) it is not literally true that "nothing is auto-selected" — the function does
auto-resolve a launch path (installed binary > acpr > direct package >
unavailable) and auto-merge the catalogue. The genuine defect is that *which
participant runs* is not selected here; that is the chair's act in neighbouring
elements.
**Change: description only.** Rename the element in `element.md` to an
output-descriptive title such as "Harness resolution and catalogue", and update
the `name_length` property (currently 2) to match. Add one line: "autoselect
returns the whole offer set; it must stay non-choosing — the chair selects
participants." **Keep the `autoselect` function name**: it is exported and
consumed cross-crate (GF1), its return type already legitimises "select" as
"select the options to offer", and renaming a public API across crates adds
migration cost with no functional benefit. Explicitly refuse the alternative
remedy of making `autoselect` rank/return one agent — that would create a second,
competing selection site the chair could not override. Deferred check for the
full-repo pass: confirm no caller in `crates/roundtable-web` uses `entries[0]`
as "the chosen agent" (none exists in `launch.rs`).

## GF8 — Major, egm-comprehension (wants / elephant.built (acpr))
> acpr is never defined, and what it adds over direct npx/uvx is not explained.

**Decision: RIGHT** (strong comprehension gap).
**Why.** The description names `acpr` in `upstream.registry.agent` ("as used by
acpr"), `elephant.built` and `elephant.gaps` but never defines it. The code
(L92-95, 97, 126-133, 285-298) shows `acpr` is a CLI that resolves registry
distribution types and is launched as `acpr <id>`. What it adds over direct
npx/uvx is concrete and undocumented: it also handles **binary distributions**
(binary-only entries are launchable with `acpr` but unavailable without it,
131-133 / 319) and gives one uniform invocation instead of per-runner commands.
Without this, `elephant.gaps` ("acpr is not installed so ... npx or uvx
directly") is unintelligible to a reader.
**Change: description only.** Define `acpr` once (an ACP Registry CLI/launcher;
`which::which("acpr")` decides its availability) and state what it adds: a
single `acpr <id>` command and support for binary distributions, whereas the
direct fallback only covers npx/uvx packages. No code change.

## GF9 — Major, egm-comprehension (resolution order / terms)
> Precedence among built-in, registry, acpr and user commands is unstated;
> 'catalog aliases' is undefined; how a user supplies an ACP command is not
> described.

**Decision: RIGHT.**
**Why.** element.md states none of: the per-agent precedence (installed binary >
acpr > direct package > unavailable), the `autoselect` merge/fallback order
(registry + builtins vs builtins-only), the fact that `custom()`/user commands
are a separate path outside `autoselect`, the meaning of "catalog aliases"
(which does not exist as a distinct feature — see GF2), or the mechanism by
which a user supplies a command (a command line turned into a `LaunchSpec` by
`from_command_line`, 39-43). The precedence in `parse_registry_with` is
non-obvious (installed binary even beats `acpr`) and is the kind of thing a
maintainer must see in the map. See the diagrams in `AcuteMotor-analysis.md`.
**Change: description only.** Add a "Resolution order" note with the ordered
list above plus `autoselect`'s merge/fallback, define or remove "catalog
aliases", and describe the user-command mechanism (command line ->
`LaunchSpec::from_command_line` -> one `Source::Custom` entry). No code change.

## GF10 — Major, egm-comprehension (failure behaviour)
> No behaviour is given for an unreachable registry, missing npx/uvx, or a
> spawned process that fails to start or handshake.

**Decision: RIGHT** (as a documentation gap), with an ownership split.
**Why.** The description documents none of the three, but two behaviours **are
implemented here and merely unwritten**: an unreachable registry degrades to
`(builtin(), Some(note))` (230) — degraded, not an error; and a missing launcher
sets `available=false` with a "... is not on PATH" note (195-199), while a
binary without acpr gets "install acpr to launch it" (132). The third — spawn
or handshake failure — is **not** this element's concern: it is
`process::spawn`'s `could not start {display}` (process.rs:75) and the
`harness.rs` connect path. Documenting it here would recreate GF1's error of
crediting this element with the spawn.
**Change: description only.** Add three lines naming the boundary: (1) registry
unreachable -> built-in catalog + note; (2) launcher absent -> entry marked
unavailable with a note; (3) process-start and handshake failures belong to
`code.client.agent`/process.rs and are out of scope here. No code change.

## GF11 — Nit, egm-comprehension (elephant.design vs references §3)
> 'any local ACP command' sits against a cited section titled 'Discovery is not
> a universal local executable scanner' without reconciliation.

**Decision: RIGHT** (a small reconciliation/clarity nit; the two statements are
compatible, not contradictory).
**Why.** "Any local ACP command" means a command the **user explicitly supplies**
(custom()/from_command_line, 39-43, 235-238); "not a universal local executable
scanner" means the program does **not** auto-detect every binary on the machine
— `which` only confirms something the registry named or the user supplied
(195-199), it does not enumerate PATH. The launch.rs module doc (3-5) already
reconciles them verbatim: "The registry is not a detector of every program on
the machine; a user-supplied command covers the rest." The cited §3 title is a
*supporting* reference, not a conflict. The finding is upheld as a clarity nit
because a newcomer could still misread "any local ACP command" as scanning.
**Change: description only.** Add "(explicitly user-supplied, not discovered by
scanning local executables)" to `elephant.design`. No code change.

## GF12 — Nit, egm-comprehension (upstream.registry.agent)
> Registry location and caching are not stated.

**Decision: RIGHT** (a doc nit), resolved together with GF5.
**Why.** The registry location is `REGISTRY_URL` (12, the ACP CDN
`.../registry/v1/latest/registry.json`) and is not stated in element.md. There
is **no caching**: `autoselect` issues a fresh `client.get(REGISTRY_URL).send()`
on every call (215-219), so the honest documentable fact is precisely that
there is none — not that a cache exists to describe. Both GF5 and GF12 cite the
same URL; documenting it once avoids two drifting copies.
**Change: description only (one shared paragraph with GF5).** State the
registry URL and "fetched fresh on each `autoselect` call; no caching". No code
change (adding a cache would be a new feature, not a fix to this finding).

---

## Summary
| Finding | Decision | Change |
|---|---|---|
| GF1 | RIGHT (scope/attribution) | description + LaunchSpec doc comment (L14): element resolves, not spawns |
| GF2 | RIGHT | description: correct the wants Function line; drop/define "catalog aliases" (tables.rs location unverified, tagged) |
| GF3 | RIGHT | description: qualify elephant.gaps (package entries only); note binary precedence |
| GF4 | RIGHT (security) | description: document env deny-list |
| GF5 | RIGHT (doc gap) | description: URL, merge/fallback, availability rule (shared with GF12) |
| GF6 | RIGHT (nit) | description: pinned versions, splitter limits |
| GF7 | RIGHT (name misdescribes) | description: rename element + name_length; keep `autoselect`; refuse making it choose |
| GF8 | RIGHT | description: define acpr + what it adds |
| GF9 | RIGHT | description: precedence, terms, user-command mechanism |
| GF10 | RIGHT (ownership split) | description: document 2 in-scope behaviours; exclude spawn/handshake |
| GF11 | RIGHT (clarity nit) | description: one-line reconciliation; no contradiction in the code |
| GF12 | RIGHT (nit) | description: URL + "no caching" (shared with GF5) |

No finding requires a **functional code** change: every remedy is a
clarification of `element.md`, plus one source doc comment (GF1, launch.rs:14).
Two caveats are kept on record so they are not "fixed" incorrectly later:
GF7's finding wrongly says the element "spawns" (GF1) and that "nothing is
auto-selected" (the function does auto-resolve a launch path); GF11's
"contradiction" is already reconciled by the module doc (3-5). These qualify
the findings' wording, not the verdict.

## Consolidations (avoid drifting duplicate text)
- **GF3 + GF8 + GF9 -> one precedence block.** Branch order at
  `parse_registry_with` 117-133 (installed binary > acpr > direct package >
  unavailable) plus the merge at `autoselect` 223-227 (registry ∪ builtin by
  id; `custom` never merged). Documenting these separately would restate the
  same order three times. This single block resolves GF9's "unstated
  precedence", GF3's overstated gap, and GF8's undefined `acpr` at once.
- **GF5 + GF12 -> one registry paragraph.** Both cite `REGISTRY_URL` (12).
  State the URL once, with "fetched fresh on each call; no caching", the
  reachable/unreachable merge+fallback (220-231), and
  `available = which(command)` (195-199).
- **GF1 + GF10's spawn half -> one ownership sentence.** Both exist only
  because the resolve/spawn boundary is unstated; process-start and handshake
  failures belong to `code.client.agent`/process.rs (cf. GF1).

## Verified vs accepted-on-reading (audit tagging)
- Everything except the two items below rests on lines quoted from
  `launch.rs` itself, which is present in full.
- **GF2 "where":** `launch.rs` proves `custom` (235-238) is standalone and
  `autoselect` (220-227) never merges customs; the *bypass location*
  (`tables.rs:88` uses `custom` only for OpenRouter; `tables.rs:107-108` calls
  `from_command_line` directly) is NOT in the copied source. Accepted on the
  reviewers' reading; the verdict does not depend on it. Re-check in the
  full-repo pass.
- **GF10 handshake half:** spawn half verified (process.rs:75); handshake
  (`harness.rs`) is attributed to another element and does not change what this
  element's description must say.

## Additional finding surfaced by the roundtable (not a reviewer finding)
**Built-in id shadowing silently drops a launchable fallback.** In `autoselect`
(223-227) a built-in is added only when its `id` is absent from the registry
entries: `if !entries.iter().any(|known| known.id == fallback.id)`. If the
registry lists `opencode` as a binary on a machine with acpr missing and that
binary not installed, the registry entry is present but `available:false` with
note "install acpr" (132), and the pinned built-in `opencode-ai@1.19.5` via npx
(88) is **discarded, not offered as an alternative** — with no note that it was
shadowed. This contradicts the "built-ins are always offered" comment
(212-213). Observable test: feed `parse_registry_with` such a document without
acpr, then check the union — the built-in `opencode` entry is absent. The
merged "How selection works" description should state: "a built-in is dropped
when the registry reuses its id, even when the registry entry is itself
unavailable." No code change requested here (it is a behaviour to document, not
a reviewer finding to fix), but the diagnostic wording should be honest.

## Independent runnable verification (AerialSifaka)
`registry_env_allowed` (181-185) and `split_words` (240-272) were reimplemented
and executed verbatim: GF4's deny-list is case-insensitive exact-set plus
`LD_/DYLD_/NPM_CONFIG_` prefixes (e.g. `AGENT_MODE` allowed, `LD_PRELOAD`
denied); GF6's splitter keeps quotes, rejects unbalanced quotes, treats
backslash as an ordinary char (no escapes), and keeps empty quoted words.
The empty-word and mixed-quote cases are untested by either reviewer, so the
resolution does not certify them — an implementer adding tests should not
assume it does.
