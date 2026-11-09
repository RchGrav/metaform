# SmoothMemory — independent verification notes for `upstream.registry.agent`

Purpose: audit `element.md` findings GF1–GF9 against the only source file provided,
`source/crates/acp-host/src/launch.rs`, and record corrections to the shared
`resolution.md` draft. Line numbers below are to `launch.rs`.

## Ground truth established from the code

- `REGISTRY_URL` (12) equals the element's `uri` property exactly. No finding contests it.
- `autoselect` (214–232) is the only fetcher. It fetches on **every call** (215–219),
  holds no cache, and has no start-up hook. There is no other reader in this snapshot.
- `parse_registry_with` (103–138) resolves a distribution in this exact order:
  1. installed binary on PATH → run directly with registry args (117–125,
     `installed_binary` 151–157);
  2. else `acpr <id>` if `acpr` present (126–127, presence checked at 97);
  3. else npx/uvx package runs directly + note (128–130, builder 159–178);
  4. else binary-only entry → unavailable (131–133).
  `platform_key` (141–147) maps `macos`→`darwin` and appends the arch.
- `registry_env_allowed` (181–185): DENIED = PATH, NODE_OPTIONS, NODE_PATH,
  PYTHONPATH, PYTHONSTARTUP, BASH_ENV, ENV, HOME (8 items), plus any key whose
  uppercased form starts with `LD_`, `DYLD_`, `NPM_CONFIG_`. Filtering is
  case-insensitive and is applied **only** in `package_launch` (168–176) to the
  `env` object inside a `distribution.npx` / `distribution.uvx` spec. It is not a
  global env filter and there is no top-level agent env in the schema.
- `autoselect` branches (220–231): `Err` → `(builtin(), Some("registry unavailable,
  using built-in catalog: ..."))`; `Ok` → `parse_registry` ∪ built-ins whose `id`
  is absent (223–227).
- `HarnessEntry.version` (66) is populated from the registry's `"version"` field
  (116) — the **agent/package version**, e.g. `"9.9"` in test 309 — NOT the ACP
  protocol version. Nothing in the file branches on ACP protocol version; no
  `v1`/`v2` concept exists.
- Test inventory (274–339): `registry_entries_resolve_npx_uvx_and_binary` (279),
  `installed_registry_binaries_are_launchable` (303),
  `registry_cannot_set_loader_or_path_variables` (323),
  `command_lines_split_on_whitespace_and_respect_quotes` (333). **There is no
  `autoselect` / fallback test.** GF4's fallback behaviour is untested.

## Verdicts (where I differ from the MassiveSpirit draft)

All nine findings are substantively right about a real documentation gap, but
three need a sharper verdict and the draft contains one factual error.

1. **GF1 — right, but the "no code change" conclusion needs a justification, not
   an assertion.** The draft says fetching per request is "deliberate freshness
   behaviour". That is an inference. The defensible argument is: the URL ends in
   `.../latest/registry.json`, so a cached/start-up snapshot would go stale by
   design; adding a cache would be a product change, not a review correction.
   Either way the minimal fix is the description. I agree with the verdict.

2. **GF5 — the first half is a category error and should be marked wrong as
   stated.** The `elephant` layer is explicitly "the project author's account",
   with a `date` field. A count of agents in a remote, mutable CDN document is a
   dated external observation; it is *not supposed to be* a code constant and
   "cannot be checked from code" is therefore not a defect. Marking GF5 "Correct"
   on that basis (as the draft's Summary does) endorses a misunderstanding.
   The *second* half (source mismatch) is right but is exactly GF9. Net: GF5 =
   partly wrong; resolve the real part through GF9, and annotate the count as a
   dated snapshot rather than deleting it.

3. **GF8 — right that a consequence is missing; wrong about what the consequence
   is.** "v1 vs v2 agents when choosing how to launch" has no basis in the code:
   there is no version-based launch path, and `version` is the package version.
   Documenting a v1/v2 launch switch would introduce a false statement into the
   map. The accurate consequence: the host cannot verify ACP protocol
   compatibility *before* launch, so an incompatible agent is only detected at
   `initialize`/connection time and there is no way to prefer a compatible one.
   The draft's proposed edit ("cannot distinguish v1 from v2 ... version-aware
   launching") should be replaced.

4. **Factual error in the draft's Summary.** It says the tests "cover the
   resolution, fallback, and env-filter behaviour". They cover resolution (279),
   env filter (323) and installed-binary (303) — **not** `autoselect`/fallback.
   For GF4, an optional code-side improvement is to add a fallback test with a
   stubbed `reqwest::Client`; that is the only place a code change is genuinely
   useful, and it is optional, not required by the finding.

5. **GF6 — right, with a placement caveat.** `acpr` is defined by the code's own
   comment (92–95, "D §7.1: acpr resolves registry distribution types and
   launches the agent"); `acpx` appears only in the §7.2 reference title and is
   referenced nowhere in code. Both are undefined *in the element*, so the
   finding stands. But "whether Roundtable calls acpr or copies its resolution"
   is a `code.launcher.agent` concern — this element is the upstream CDN JSON.
   The answer from code is "both": it invokes `acpr <id>` when installed (127)
   and reimplements resolution in `parse_registry_with` otherwise. Add a
   glossary + a one-line cross-reference, not a full launcher spec here.

6. **GF3 — one precision fix.** The filter applies only to `distribution.npx` /
   `distribution.uvx` `env`, not to "entries" generally. Document the exact
   scope so the map does not claim a broader guarantee than the code provides.

## Consolidation (reduces nine edits to four)

- GF1 ⊇ GF7: fix `elephant.built`; GF7's question is answered by that fix plus GF4.
- GF4 covers the offline-fallback half of GF7.
- GF9 covers the source-mismatch half of GF5.
- GF2, GF3, GF4, GF6 → one "how Roundtable consumes the registry" section.
- GF8 → one corrected gap sentence.

Net distinct edits to `element.md`: (a) rewrite `elephant.built`; (b) add a
consumption/behavior section (launch order, env filter scope, fallback, no
cache); (c) define `acpr`/`acpx` and clarify "as used by acpr"; (d) add
`README.md §9.2` to references + label the 45 count as a dated snapshot;
(e) restate the ACP-version gap consequence accurately. No code changes required;
one optional test for `autoselect`.

## Placement note (coordination)

`launch.rs` lives in `crates/acp-host` and is the **consumer** of the registry,
not the registry itself (the element is a remote CDN JSON, per its `uri`).
Detailed launch resolution, env filtering and fallback arguably belong to
`code.launcher.agent`'s element. Recommend keeping a short "consumption" section
here for self-containedness, with a cross-reference to the launcher element, to
avoid duplicating the two elements. This is a placement decision the group should
make; it does not change any verdict.
