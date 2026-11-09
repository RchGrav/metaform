# Resolution — `code.launcher.agent` (ACP autoselection)

Reviewed `element.md` against the code copied into `source/crates/acp-host/src/launch.rs`
(the only file supplied). I also checked the one cross-element claim I could, with a permitted read
of `code.client.agent/src/crates/acp-host/src/process.rs`; everything else that cites
`crates/roundtable-web/**` is accepted on the reviewers' reading and flagged below.

**Verification scope.** `launch.rs` is the whole of this element: 339 lines, no `process::spawn`,
no `tokio::process`, no stdio. Line references below are to the copied file.

**Shape of the fix.** Most findings are description defects, not code defects. Only GF1 needs a
structural change to the description (narrow the promise and move the spawn/stdin/stdout detail to
`code.client.agent`); GF2 and GF3 need a decision about what this element *is* before the wording
can be right. Everything else is a "describe what the code already does" edit. The single genuine
code-vs-intent judgement call is GF7 (whether the element should do work its name implies).

---

## GF1 — "does not spawn anything or set up stdio" (Blocker, egm-codebase-details) — RIGHT

`LaunchSpec` (launch.rs:14-51) is a pure value: `command`, `args`, `env`, `env_remove`. `new`
(29-36) just collects args; `from_command_line` (39-43) splits words; `display` (45-50) joins them.
Nothing in the file touches `std::process`, `tokio::process`, `Stdio`, or a pipe. The doc comment
even calls it "How to start one ACP agent process" (14) — a claim the type does not keep.

The spawn lives in `process::spawn` in `code.client.agent`: it does
`Command::new(&spec.command)`, `.args(&spec.args).envs(&spec.env)`, then
`.stdin(piped()).stdout(piped()).stderr(piped())`, `process_group(0)`, `kill_on_drop(true)` and
`child.spawn()`. stdio for newline-delimited JSON-RPC is set there, not here. So the element's want
from `code.client.agent` — "Resolves the harness to a launch command **and spawns it with stdio for
newline-delimited JSON-RPC**" — mixes two owners' jobs into one sentence and gives this element
credit for the other's.

**Change (description):**
- Rewrite the want: `code.client.agent` *receives a `LaunchSpec` and does the spawning*. This
  element's function is to *resolve* (id → `LaunchSpec`, availability, note) and *list* entries —
  never to start a process.
- Retitle the `LaunchSpec` doc comment from "How to start one ACP agent process" to "How to start
  one ACP agent process — a description only; `process::spawn` performs it" so the source cannot be
  misread again.
- Add **one line** to the description naming what a `LaunchSpec` guarantees to the consumer: command
  is resolved by name (PATH lookup is the consumer's, via `which` here only for `available`), args
  are pre-split, `env` overlays the inherited environment and `env_remove` is applied first (that
  ordering is documented at process.rs:65-67, so it belongs in the contract, not here).

**Why:** the finding is exactly right and it is a Blocker because the current sentence tells a
reader this element owns spawning. Moving the sentence removes the false claim; the extra contract
line keeps the element's real output inspectable.

## GF2 — "no catalog aliases; user commands not listed" (Major, egm-codebase-details) — RIGHT

Two separate claims, both checkable:

1. **"catalog aliases" do not exist.** `HarnessEntry` has `id` and `name` (launch.rs:64-65);
   `builtin()` hard-codes a single `id` per harness ("claude-acp", "codex-acp", "pi-acp",
   "opencode", 85-88). There is no alias type, no alias table, no lookup by alias.
2. **user-supplied commands are not listed.** `custom()` (235-238) builds a `HarnessEntry` from a
   command line and returns it — nothing in `launch.rs` returns a *catalogue* containing customs.
   The reviewer says `custom` is used only for the OpenRouter adapter entry (tables.rs:88) and seat
   commands go through `LaunchSpec::from_command_line` directly (tables.rs:107-108), bypassing
   `custom` and therefore never appearing in any list. I cannot open `roundtable-web` here, but the
   `launch.rs` side is consistent with that reading: the file exports `custom` as a one-off
   constructor, not a listing step, and `autoselect` (214-232) only ever merges registry + builtin.

**Change (description):**
- Delete "catalog aliases" from the want. Replace with "the fixed ids and display names in
  `builtin()` and the registry's `id`/`name`".
- Replace "user-supplied ACP commands" in the want with "an arbitrary command line turned into a
  `LaunchSpec` by `LaunchSpec::from_command_line`; whether it appears in a list is the caller's
  decision (this element offers `custom()` but does not merge customs into `autoselect`)".
- Say explicitly in the description that `autoselect` returns **registry ∪ builtin only**.

**Why:** the want currently promises a capability (listing user commands, aliases) that no code path
in this element provides. Naming the real three constructors is honest and still useful to callers.

## GF3 — "start through npx or uvx directly" is too strong" (Major, egm-codebase-details) — RIGHT

Order in `parse_registry_with` (117-133), read top to bottom:
1. **Installed binary wins** (117-125): `binary.and_then(installed_binary)` runs `which` on the
   binary's basename and, if found, launches *that* copy with the registry args — this branch is
   checked **before** `acpr` and ignores `acpr` entirely.
2. **acpr** (126-127) only reached if (1) missed.
3. **direct package launch** (128-130) only if not acpr.
4. **binary-only without acpr** is immediately unavailable (131-133) with
   "install acpr to launch it".

So "registry agents start through npx or uvx directly" is true only for the **package** entries in
the no-acpr case. A binary entry with an installed copy starts from PATH; a binary entry without one
does not start at all. The elephant's `gaps` line is therefore narrower than stated.

**Change (description + elephant.gaps):**
- Rewrite the gap as: "acpr is not installed on this machine. Package (npx/uvx) registry agents
  start directly from the registry's package and args; a registry binary that is already installed
  starts from PATH; a binary that is not installed is offered but unavailable."
- In the description add the precedence sentence (see GF9) so the gap is not read as universal.

**Why:** the current gap is a runtime fact about *this* machine and it is being stated as a general
rule. Restating it with the binary exception makes it correct and stops it from masking GF9.

## GF4 — "registry-supplied env is filtered; undocumented" (Major, egm-codebase-details) — RIGHT

`package_launch` (168-176) copies registry `env` into `launch.env` **only** when both the value is a
string and `registry_env_allowed(key)` is true. `registry_env_allowed` (181-185) rejects, case
insensitively:
- exact: `PATH`, `NODE_OPTIONS`, `NODE_PATH`, `PYTHONPATH`, `PYTHONSTARTUP`, `BASH_ENV`, `ENV`,
  `HOME` (`DENIED`, 8 entries);
- prefixes: `LD_`, `DYLD_`, `NPM_CONFIG_`.

The list is exactly as the reviewer described, and no sentence in `element.md` mentions it. The test
`registry_cannot_set_loader_or_path_variables` (322-330) pins the behaviour, which confirms it is
intentional, so it is a documentation omission, not a bug.

**Change (description):** add a "Trust boundary" note: the registry is a remote document; only its
package `env` is honoured, only for allowed keys, and refused keys are silently dropped (not an
error). List the denied set and prefixes verbatim from 183-184 — a reader deciding whether to trust
the loader needs the exact list, not "some variables".

**Why:** this is a security rule that a reader of the description cannot infer from "Find and start
agents from the ACP Registry". Undocumented security controls get "cleaned up" by later maintainers.

## GF5 — "undocumented: REGISTRY_URL, merge-when-reachable, `which` availability" (Major, egm-codebase-details) — RIGHT on all three

- `REGISTRY_URL` = `https://cdn.agentclientprotocol.com/registry/v1/latest/registry.json`
  (launch.rs:12), absent from the description.
- `autoselect` (214-232): on success it parses the registry, then appends every `builtin()` entry
  whose `id` the registry did not already list (223-227), and returns `None` as the note. On error it
  returns `builtin()` with a note string "registry unavailable, using built-in catalog: {error}"
  (230). So "built-ins merged when reachable, whole catalog plus note when not" is exact.
- `entry` (195-199): `available` is `which::which(&spec.command).is_ok()`; otherwise the note is
  "{command} is not on PATH". `available` therefore means "the *launcher* (npx/uvx/acpr/the binary)
  is on PATH", not "this harness will work" — a distinction worth stating.

**Change (description):** add a short "How selection works" paragraph: the URL; merge rule with the
`id`-equality caveat (a builtin with an id the registry reuses under a different package is *not*
appended, it is shadowed); the fallback note; and the precise meaning of `available`/`note`.

**Why:** these are the only pieces of behaviour a caller has to know to interpret the return value,
and none are written down.

## GF6 — "pinned versions not stated; splitter has no escapes" (Nit, egm-codebase-details) — RIGHT

Pins at 85-88: `@agentclientprotocol/claude-agent-acp@0.101.0`, `@agentclientprotocol/codex-acp@2.5.0`,
`pi-acp@0.0.34`, `opencode-ai@1.19.5` (with `acp`), all via `npx -y <pkg>`. `split_words`
(240-272) has three states (none / inside `'` / inside `"`), treats both quote characters the same
inside a quoted run (so `'` inside `"` is literal), and has **no escape handling** — a backslash is
an ordinary character, and an unterminated quote returns `None` (265-267). Note also that an empty
quoted word is kept (`started = true` at 251), so `node ""` yields an empty arg; that is correct
shell-like behaviour but untested.

**Change (description):** state the four pinned versions in the elephant `built` line (or a table).
Say the splitter handles quotes only — no backslash escapes, no variable expansion, no globbing — and
that failures to balance quotes are an error, not a partial parse.

**Why:** the pins are what make the built-in fallback reproducible, and the splitter's limits decide
which command lines a user can actually write. Both are cheap to state and expensive to guess.

## GF7 — "'ACP autoselection' misdescribes the element" (Major, egm-comprehension) — RIGHT about the name, and the name should change

`autoselect()` (214) is a **fetch-and-merge**, not a choice: it returns every entry it can find with
`available`/`note` flags and does not pick one. The chair picks (that is `code.client.agent` /
roster territory). The module comment on line 1 says "find the harnesses that can be launched here
and how to launch them", which is accurate — but the *title* "autoselection" imports the opposite
claim. "Auto-selection" is a promise of choice; the code offers a ranked-by-source list.

**Change:** rename the element to something that describes the output, e.g. **"Harness resolution
and catalogue"** (or "Launch-spec resolution"). Keep `autoselect` as the function name only if it is
cheap to rename; if the API is already consumed, leave the function and fix the *title* and title
only, noting the function is a merge. Do **not** "fix" this by making the code choose an agent — the
chair's choice is an explicit design decision recorded in the neighbouring elements, and making this
element pick would duplicate or shadow it.

**Why:** a wrong name is a Major in a *comprehension* review because every downstream sentence is
read against it. Renaming is the cheapest correct fix, and explicitly refusing the alternative
(the code should not start choosing) keeps the fix from breaking the client.

## GF8 — "acpr is never defined; what it adds over npx/uvx unexplained" (Major, egm-comprehension) — RIGHT

`acpr` appears in the doc comment (92-95: "acpr resolves registry distribution types and launches the
agent"), in `parse_registry` (`which::which("acpr")`, 97), in the launch (`LaunchSpec::new("acpr",
[id])`, 127), and in user-facing notes ("install acpr to launch it", 132). Nowhere is it said what
`acpr` *is* or why `acpr <id>` is better than `npx -y pkg` / `uvx pkg` / the binary. The reader can
infer it is an ACP Registry launcher, but not that choosing it handles the binary distribution type,
pins a resolved version, and avoids duplicating the registry's arg/env translation in this crate.

**Change (description):** one sentence defining acpr (the ACP Registry's reference launcher) and one
sentence of *what it buys here*: it is the only path that can start a **binary** distribution this
machine has not installed (branch order above), and when present it takes precedence over direct
package launch so the registry's package/args/env rules live in acpr rather than here. Also say the
reverse: when a binary is already on PATH, this crate prefers that copy over acpr (GF3).

**Why:** without the definition the "acpr" branches in the code read as arbitrary. With it, GF3, GF5
and GF9's precedence question become one coherent story.

## GF9 — "precedence unstated; 'catalog aliases' undefined; how a user supplies a command undescribed" (Major, egm-comprehension) — RIGHT

No sentence in the description orders the sources. From the code the real order is:

**Per registry agent** (parse_registry_with, 117-133): installed binary > acpr > direct npx/uvx >
unavailable.
**Across sources** (autoselect, 220-231): registry entries first, then builtin entries whose `id` is
not already present. Custom entries never enter `autoselect` at all (GF2). So custom is a *separate*
constructor the caller invokes on a command line it already has — it has no place in the precedence
because it is not merged.

"Catalog aliases" is undefined because it does not exist (GF2). "How a user supplies a command" is
`LaunchSpec::from_command_line` → `custom(id, name, line)`; the caller must already have a command
line, and `custom` only validates the quoting and probes `which` on the first word.

**Change (description):** add a short precedence list (the two orders above) and a "user-supplied
command" subsection: the entry point is `LaunchSpec::from_command_line` / `custom`, the input is a
shell-like line (quotes only, GF6), and it is *not* auto-merged — the caller lists it if it wants.
Drop "catalog aliases" everywhere.

**Why:** precedence is the single most load-bearing fact about this element and it is only in the
code. Writing it down also resolves GF3 and GF8's apparent contradictions.

## GF10 — "no failure behaviour for unreachable registry / missing npx, uvx / failed start or handshake" (Major, egm-comprehension) — RIGHT, but only partly this element's

Break it into three:

- **Unreachable registry:** *this element's.* `autoselect` returns `(builtin(), Some(note))`
  (230) — no error, degraded list. This is the whole failure policy and it is written in the code,
  not the description.
- **Missing npx/uvx/acpr/binary:** *this element's.* Handled, not fatal: the spec is still built,
  `entry` marks `available: false` with a "not on PATH" note (195-199); binary-without-acpr gets
  "install acpr to launch it" (132). The engine keeps a selectable-but-unusable entry. This should
  be stated.
- **Spawn fails / handshake fails:** **not this element.** `process::spawn` returns
  `could not start <display>` (process.rs:75) and `harness.rs` (connect_v2/connect_v1, fail) owns
  handshake errors (1076). The finding's severity is right but the ownership is wrong: the
  description should say spawn and handshake failure are `code.client.agent`'s, so a reader does not
  look for them here.

**Change (description):** a three-line "Failure behaviour" section: (1) registry unreachable →
builtin + note; (2) launcher missing → entry present, `available: false`, note explains; (3) after
resolution, start and handshake failures belong to `code.client.agent`.

**Why:** the description's silence makes a reader unable to tell a degraded path from a bug. Naming
the boundary is the fix; pretending this element handles spawn errors would be another GF1.

## GF11 — "'any local ACP command' vs §3 'Discovery is not a universal local executable scanner'" (Nit, egm-comprehension) — RIGHT

The elephant `design` (47) says "any local ACP command"; the cited §3 is titled "Discovery is not a
universal local executable scanner". The code agrees with §3: there is **no scan of the machine**.
The only local lookups are `which` on (a) the already-selected `acpr` (97) and (b) the basename of a
binary the *registry* named (151-157) — i.e. resolution only ever confirms or rejects something that
was already proposed, it never enumerates. A "local ACP command" only enters via an explicit line
handed to `from_command_line`/`custom`.

**Change (description):** reword the design to "accept any ACP command the user explicitly supplies"
and add the sentence "Nothing here enumerates executables on the machine; `which` only checks a
command already named by the registry or supplied by the user." That reconciles §3 with the phrase.

**Why:** Nit, but it is the exact distinction §3 exists to make, and the current wording contradicts
the cited section.

## GF12 — "registry location and caching not stated" (Nit, egm-comprehension) — RIGHT

Location is `REGISTRY_URL` (12), same as GF5's first item — so GF5 and GF12 overlap and should be
resolved together, not twice. Caching: **there is none in this element.** `autoselect` issues a GET
on every call (216); the only reuse is the caller's `reqwest::Client`. No TTL, no on-disk cache, no
ETag. Additionally, `error_for_status()` (216) and `json()` mean a 203/HTML/proxied error page
surfaces as the "registry unavailable" note, which is the right degraded behaviour but hides *why*.

**Change (description):** state the URL once (in the GF5 section), and say explicitly "fetched on
every call; no cache in this element; the caller's `reqwest::Client` may reuse connections". Note
that any non-2xx or non-JSON body is treated as unreachable (falls back), so the note's error text is
the only diagnostic.

**Why:** a caller who expects caching will otherwise add a stale cache this element does not have,
or duplicate one; and the "falls back on any fetch/parse failure" rule is the real behaviour.

---

## Summary table

| # | Right? | Owner of fix | Core change |
|---|---|---|---|
| GF1 | Yes (Blocker) | description | Move "spawns with stdio" to `code.client.agent`; state `LaunchSpec` is a value |
| GF2 | Yes | description | Drop "catalog aliases"; state autoselect = registry ∪ builtin; custom is caller-driven |
| GF3 | Yes | description + gaps | Rewrite gap: package direct, installed binary from PATH, else unavailable |
| GF4 | Yes | description | Document the env deny-list and prefixes |
| GF5 | Yes | description | Document URL, merge rule, `available` = launcher-on-PATH |
| GF6 | Yes (Nit) | description | State 4 pins; splitter quotes-only, no escapes |
| GF7 | Yes | name | Rename element; keep it non-choosing |
| GF8 | Yes | description | Define acpr and what it buys |
| GF9 | Yes | description | Write the two precedence orders; define user command path |
| GF10 | Yes, partly | description | Degraded paths here; spawn/handshake are `code.client.agent` |
| GF11 | Yes (Nit) | description | Reword "any local ACP command"; state no scanning |
| GF12 | Yes (Nit) | description | URL once; no cache; any fetch/parse failure = fallback |

**Deferred to full repo (cannot verify from the copy):** GF2's tables.rs:88/107-108 claims. If those
turn out different, GF2's "user commands are not listed" still stands on `autoselect` alone; only
the *where* of the bypass would change. No other finding depends on unread files except GF10's
`harness.rs` handshake line, which is attributed to `code.client.agent` and does not alter this
element's changes.
