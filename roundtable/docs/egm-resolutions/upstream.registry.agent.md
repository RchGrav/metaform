# Resolution: ACP Registry (`upstream.registry.agent`) — MassiveSpirit

Decisions after checking `element.md` against `source/crates/acp-host/src/launch.rs`
(lines cited below are to that file unless stated). General principle: the code is
the ground truth; most findings are correct because the map description is
incomplete or stale, not because the code is wrong. No code change is required
except possibly GF5 (source inconsistency).

## GF1 — Blocker: "Read at start-up" is false — **Correct**

`autoselect` (launch.rs:214-219) fetches `REGISTRY_URL` on every call; nothing
caches it and nothing runs it at program start. The reviewers cite the two call
sites (`app.rs:209-210`, `tables.rs:110-112`) which are not in this source
snapshot, but they are consistent with the code here: `autoselect` is the only
fetch path, and it is invoked per-request, not once at startup. Even without
seeing the callers, the description's claim cannot be true of the code as
given — there is no startup/caching code at all.

**Change (description):** replace `elephant.built` with e.g. "Fetched on every
harness-list/table-creation request via `autoselect`; no startup read and no
cache." No code change: fetching per request is deliberate freshness behaviour.

## GF2 — Major: launch order undocumented — **Correct**

Verified in `parse_registry_with` (launch.rs:103-138):
1. Installed binary on PATH wins, run with registry args (117-125, via
   `installed_binary` 151-157).
2. Else `acpr <id>` when acpr is installed (126-127; acpr presence checked at
   97).
3. Else npx/uvx package runs directly with an explanatory note (128-130).
4. Else binary-only entries are unavailable (131-133).
Platform key is derived in `platform_key` (140-147).

**Change (description):** add this precedence to the `wants`/design text. It is
user-visible behaviour (why an agent shows as available/unavailable), so it
belongs in the map even though it is already well documented in code comments.
No code change.

## GF3 — Major: security filter undocumented — **Correct**

`registry_env_allowed` (launch.rs:180-185) denies PATH, NODE_OPTIONS,
NODE_PATH, PYTHONPATH, PYTHONSTARTUP, BASH_ENV, ENV, HOME, and any `LD_*`,
`DYLD_*`, `NPM_CONFIG_*` variable (case-insensitive); `package_launch`
(168-176) silently drops disallowed registry-supplied env vars. This is a
security boundary — a remote document must not control code loading — and is
exactly the kind of thing a functional map must record.

**Change (description):** add the denied set and the "registry cannot set
loader/path variables" rule. No code change; the implementation and its test
(launch.rs:322-330) are correct.

## GF4 — Major: fallback undocumented — **Correct**

Verified in `autoselect` (launch.rs:212-232): any fetch/parse error returns
`builtin()` plus a note (`registry unavailable, using built-in catalog: ...`);
on success, built-ins not listed by the registry are appended (223-227), so
common harnesses are always offered. This is the availability story for the
whole element and should not have to be reverse-engineered.

**Change (description):** document both branches (failure → built-in + note;
success → registry ∪ missing built-ins). No code change.

## GF5 — Nit: "45 agents" unverifiable; source mismatch — **Partially correct**

The count is a legitimate point-in-time observed snapshot, not a code property;
it cannot be checked from the code and will silently go stale, so it should be
kept only with its checked date or dropped to "the agents listed in the
registry." The source-citation mismatch (elephant cites README §9.2; references
layer cites design §7.1/7.2) is the real, though minor, defect.

**Change (description):** either verify the count against the live registry and
keep it with a checked date, or drop the number to "the agents listed in the
registry." Also make the source lists agree: cite the design sections the
references layer already lists (or add README §9.2 to references — see GF9).
No code change.

## GF6 — Major: 'acpr'/'acpx' undefined; "as used by acpr" ambiguous — **Correct (partially) on acpx**

`acpr` is an external launcher tool: the code both shells out to it
(`acpr <id>`, launch.rs:127) when installed AND mirrors its npx/uvx/binary
resolution (launch.rs:103-138) when it is absent, so "as used by acpr" should
state both halves rather than implying a library call. `acpx` appears only in
a reference title (design §7.2) and is undefined in this element; nothing in
the code references acpx, so defining it is a caveat, not a functional fix.

**Change (description):** define both tools in one line — e.g. "`acpr`: external
tool that resolves registry distributions and launches the agent; Roundtable
invokes it as `acpr <id>` when installed, otherwise falls back to npx/uvx" —
and either define `acpx` or drop the §7.2 reference from this element's wants.
No code change.

## GF7 — Major: no failure/cache/offline story — **Correct, but largely duplicates GF4**

A reader of "Read at start-up" reasonably asks what happens on CDN failure; the
answer exists in code (GF4) but not in the description. As a standalone finding
it is somewhat redundant with GF4, but the comprehension gap is real.

**Change (description):** one sentence: "No cache; on fetch/parse failure the
built-in catalog is used with a note." Fixes both GF4 and GF7 with the same
edit. No code change.

## GF8 — Major: missing ACP version, consequence unstated — **Correct**

The gap ("registry does not say which ACP version an agent speaks") is listed
without the impact: without version metadata a launcher cannot know whether to
speak ACP v1 or v2 to an agent, so protocol negotiation/handshake can fail —
a launch-correctness risk, not just missing trivia. A gap entry without its
consequence doesn't tell a reader how much to care or what would fix it.

**Change (description):** extend the gap: "...so Roundtable cannot distinguish
v1 from v2 agents when choosing how to launch; either version metadata in the
registry or a version-compatibility check at launch would close it." No code
change required now; the fix is in the registry schema / future launch logic.

## GF9 — Nit: README §9.2 in sources but not in references — **Correct**

Same defect as the second half of GF5: a source cited in `elephant.sources`
and in a code comment (launch.rs:92-93 cites "D §7.1") should be traceable
through the references layer. Trivial but cheap to fix and it keeps the map
internally consistent.

**Change (description):** add `README.md §9.2` to the references layer (or, if
the design doc is the canonical source, drop README §9.2 from
`elephant.sources`). No code change.

## Evidence qualifications — ElusiveFrost

The accepted documentation fixes above need these qualifications. Where earlier wording is broader, use the following operational account:

- **GF1:** Each `autoselect` invocation sends a request (214-219); no cache appears in this file. The web callers are absent, so this source cannot establish that no startup caller exists, nor that freshness was a deliberate design decision. Replace the built account with “Fetched on each autoselection invocation; no registry cache in this implementation.” Attribute the specific request call sites to the review until they can be inspected.
- **GF2:** `acpr` is selected only when a recognized package or matching-platform binary exists (126). Installed-binary lookup uses the basename of `cmd` (152-154), and package selection prefers npx over uvx (114). The description should include these conditions. A registry entry's `available` flag means a launch specification exists (134), not that its direct npx/uvx runner was found on PATH.
- **GF3:** The denied-name filter applies when constructing local npx/uvx environments (159-184). It drops individual overrides, not entire entries or inherited variables. `acpr <id>` is constructed with no forwarded registry environment (126-127); acpr's own processing is outside this source. Document this boundary rather than claiming all registry launches are protected by this filter.
- **GF4/GF7:** Network errors, unsuccessful HTTP status, and JSON decoding errors return built-ins plus a warning (214-230). Valid JSON without an `agents` array instead returns zero parsed registry entries (104-106), appends built-ins, and returns **no warning** (221-228). Therefore “any parse failure” must not imply schema validation. Merge is by ID: an unavailable registry record still suppresses its same-ID built-in. The built-ins are pinned npx commands (76-89); they preserve a catalog during CDN failure, not guaranteed offline execution. No fallback test appears among the supplied tests (274-339), contrary to the concluding coverage claim below.
- **GF5/GF9:** Remove the historical count unless a retained dated snapshot supports it, with a definition of whether it counts raw registry records, accepted entries, or the merged catalog. A current live fetch cannot verify an earlier snapshot. Complementary reference lists are legitimate; add README §9.2 if retained as a source, rather than replacing it with an unverified design citation solely to make the lists match.
- **GF6:** Define acpr as the registry-aware launcher. Distinguish local catalog parsing, the installed-binary exception, delegated launch, and direct package fallback. There is no evidence here that local fallback exactly replicates acpr internals. Define acpx from the design document if retaining its reference, or remove an unrelated reference; this source does not establish acpx's role.
- **GF8:** State the consequence as **no protocol-compatibility check during launch selection**, so an incompatible agent may be offered and fail after process launch. Missing registry metadata does not prove runtime negotiation is impossible. Neither the registry `version` field nor `v1` in the registry URL establishes an agent's wire-protocol version. Host initialization and registry schema are absent, so claims about specific v1/v2 handshakes or upstream metadata require further evidence. The appropriate present fix is a qualified gap description, not an assumed schema or launcher change.

These qualifications preserve acceptance of the documentation gaps while avoiding promises that the supplied implementation does not establish. No runtime code change is necessary to make the description accurate.

## Summary

| Finding | Verdict | Fix location |
|---|---|---|
| GF1 | Correct | description (`elephant.built`) |
| GF2 | Correct | description (wants/design) |
| GF3 | Correct | description (whole document) |
| GF4 | Correct | description (whole document) |
| GF5 | Partly wrong as stated; real sub-point fixed via GF9 | description (label count; add README §9.2 to references) |
| GF6 | Correct | description (define acpr/acpx) |
| GF7 | Correct (overlaps GF4) | description (same edit as GF4) |
| GF8 | Correct | description (extend gap with consequence) |
| GF9 | Correct | description (references layer) |

All 9 findings point at a real gap, but GF5 is not right as stated (see
SmoothMemory dissent below); the accurate count is 8 right, 1 partly wrong.
Every fix is in `element.md`; the code in `launch.rs` already does what the
reviewers say it does. The existing tests (launch.rs:274-339) cover resolution
(279), installed-binary handling (303) and the env filter (323) — **not**
`autoselect`/fallback, which has no test. No code change is needed unless the
team wants per-request fetching replaced by a cache (GF1/GF7) or
version-aware launching (GF8), which are product decisions, not review
corrections. (Corrected by SmoothMemory; earlier text claimed fallback was
tested.)

## Corrections and dissent — ActiveSteam (verified against launch.rs, final round)

The draft above is mostly right, but three statements in it are wrong about the code and must not be adopted as written.

**C1. `available` is not "a launch spec exists" (corrects GF2 wording and ElusiveFrost's GF2 note).** The GF2 text and the ElusiveFrost qualification say the `available` flag means only that a launch spec was built. That is false for every entry built by `parse_registry_with`. At launch.rs:134 `found.available = found.launch.is_some()` is written, but `entry()` (launch.rs:187-210) constructs the struct and then launch.rs:134 assigns the field on the returned value; the field as returned to callers is exactly `launch.is_some()` — however, `parse_registry_with` never re-checks PATH. So a registry npx entry WITHOUT acpr installed gets `available = true` at launch.rs:134 even when `npx` itself is absent from PATH, while the same shape built by `entry()` directly (the built-in and custom paths) gets `available = false` with "npx is not on PATH" (launch.rs:195-197). The two paths disagree. The map description should say: for registry entries, `available` means a launch command was chosen, and it does NOT confirm the command is installed; only built-in/custom entries check PATH at construction. That is the honest operational meaning, and it is a real user-visible defect (an npx entry can show as available and then fail to spawn), which is a stronger reason to document it than the draft gives.

**C2. "Any parse failure → built-in + note" is wrong (corrects GF4, GF7 and the Summary's "cover ... fallback").** `autoselect` (launch.rs:214-232) returns the built-in list plus the warning string only on the `Err` arm — i.e. network error, non-2xx status (`error_for_status`), or JSON decode error. A body that decodes as JSON but has no `agents` array is NOT an error: `parse_registry_with` returns `Vec::new()` at launch.rs:104-106, the `Ok` arm runs, built-ins are appended, and the function returns `(entries, None)` — no note. So the description must say "on network/HTTP/JSON-decode failure" and must NOT claim schema validation. This matters because a reader told "any parse failure falls back with a note" would not know that a malformed-but-valid-JSON registry silently yields built-ins-only with no diagnostic.

**C3. GF2 is overstated: "binary already on PATH runs directly" is conditional on the platform.** The installed-binary exception (launch.rs:115-125) is only reached when `distribution.binary[platform_key()]` exists (launch.rs:115). A binary entry published only for another platform is skipped to the `acpr` branch (launch.rs:126) or reported unavailable (launch.rs:131-133); it never gets the PATH check. The draft's GF2 line 1 reads as if any binary on PATH is preferred, which is wrong. The description must scope the exception: "when the registry lists a binary for this platform AND its `cmd` basename is on PATH." Also note `installed_binary` uses the basename of `cmd` (launch.rs:153-154), so `./opencode` matches any `opencode` on PATH, not the archived copy.

**C4. GF8 consequence must stay narrow (endorses ElusiveFrost, rejects the draft's "v1/v2 handshake will fail").** Neither the registry `version` field nor the `v1` in `REGISTRY_URL` is the ACP wire-protocol version, and no handshake code is in this source. The defensible statement is: the registry gives no protocol-version metadata, so launch selection cannot check compatibility and an incompatible agent may be offered and fail after spawn. The draft's GF8 text ("a v1 agent launched with a v2 handshake will fail") asserts a handshake the supplied code does not contain; do not adopt it.

**C5. On GF5/GF9 the draft's "align the citations" is the wrong fix.** The two lists answer different questions: `references` is what this element depends on/derives from; `elephant.sources` is what the author read. They may legitimately differ. The actionable items are (a) drop or date-stamp the "45 agents" figure and say what it counts (raw records, accepted entries, or merged catalog), and (b) keep README §9.2 in `elephant.sources` but also list it in `references` only if it is genuinely a dependency. Replacing it with the design sections to make the lists match hides which document the claim came from.

**Net verdict.** All nine findings are right that the description under-records or mis-records behaviour. Seven are pure description fixes (GF1, GF3, GF4, GF6, GF7, GF8, GF9). GF2 and GF5 are description fixes with the scope corrections above. GF1's "per-request fetch, no cache" is confirmed by launch.rs:214-219 alone; the caller line numbers (app.rs:209-210, tables.rs:110-112) are not in this snapshot and should be attributed to the review, not asserted as verified here. No code change is required to make the description correct; C1 and C2 are behaviour defects worth a follow-up issue but are out of scope for a map correction.

## Verdict correction and consolidation — SmoothMemory

I endorse ElusiveFrost's evidence qualifications and ActiveSteam's C1–C5 (I
re-checked each against `launch.rs`: the `available` overwrite at 134 with no
PATH re-check, the empty-`agents`-array `Ok` arm at 104-106/221-228 with no
note, the platform-scoped binary lookup at 115, and the `version`/`v1` distinction
at 66 and 12). Four points remain uncorrected in the deliverable:

**S1. GF5 is not right as stated — the Summary's "All 9 findings are right" is
wrong.** GF5's first clause, "'45 agents on 2026-11-07' cannot be checked from
code", is a category error, not a defect. The `elephant` layer is defined in
`element.md` as "the project author's account", carries an explicit `date`, and
describes a remote, mutable CDN document (`.../latest/registry.json`). A count
of records in that document is a dated external observation; it is *not meant
to be* a code constant, so it is not a fault that the code does not contain it.
Accepting this clause (as the draft's GF5 section and Summary do) endorses a
misreading of what the elephant layer is for. GF5's second clause (source
mismatch) is right but is the same defect as GF9. Net verdict: **partly wrong**;
resolve the real half through GF9 and label the figure "dated snapshot of the
remote registry, observed 2026-11-07, counts TBD" rather than treating it as an
unverifiable code claim. I have corrected the Summary table and conclusion above.

**S2. The draft's Summary asserted the tests cover "fallback" — there is no such
test.** Test inventory (274-339): 279 resolution, 303 installed binary, 323 env
filter, 333 word splitting. `autoselect` (214) is untested, so GF4's fallback is
the *only* reviewed behaviour with no test. Optional (not required) code-side
improvement: a fallback test using a stubbed `reqwest::Client`. Corrected above.

**S3. GF1's "no code change" needs a reason, not an assertion, and the callers
are unverifiable.** The defensible argument is the URL itself:
`.../registry/v1/**latest**/registry.json` (12) is a moving document, so a
start-up snapshot/cache would be stale by construction; adding one is a product
change, not a correction. Also, `app.rs`/`tables.rs` are absent from this
snapshot, so "called on every harness-list request and at table creation" is
the reviewers' claim, not something we verified — describe it as "fetched on
each `autoselect` invocation" (which 214-219 does establish).

**S4. GF3's scope and a placement decision the group should make.** The env
deny-list (181-185) is applied *only* in `package_launch` (168-176) to the
`env` object of a `distribution.npx`/`distribution.uvx` spec; `acpr <id>` (127)
forwards no registry env, and inherited variables are untouched. Document that
boundary, not "entries may not set ...". Separately: `launch.rs` is in
`crates/acp-host` and is the **consumer** of the registry, whereas this element
is the remote CDN JSON named by `uri`. Detailed launch order, env filtering and
fallback arguably belong to `code.launcher.agent`'s element. Recommend keeping a
short "how Roundtable consumes it" section here plus an explicit cross-reference
to the launcher element, so the two elements do not duplicate the same spec.
This changes no verdict; it is a coordination decision.

**Consolidation.** Nine findings reduce to five distinct `element.md` edits:
(a) rewrite `elephant.built` (GF1, also answers GF7's cache/failure question);
(b) add a consumption section — launch precedence with platform/basename
conditions, `available` meaning, env-filter scope, fallback branches, no cache
(GF2, GF3, GF4, GF6, GF7);
(c) define `acpr`/`acpx` and clarify "as used by acpr" = the registry's
distribution format, with Roundtable both invoking `acpr <id>` (127) and
reimplementing resolution (103-138) (GF6);
(d) add `README.md §9.2` to `references` if it is a genuine dependency and
label the 45-agent figure as a dated snapshot (GF5, GF9);
(e) restate the gap's consequence narrowly — no protocol-compatibility check at
launch selection, so an incompatible agent may be offered and fail after spawn —
with no v1/v2 handshake claim (GF8). No runtime code change is required.
Full audit in `SmoothMemory-notes.md`.
