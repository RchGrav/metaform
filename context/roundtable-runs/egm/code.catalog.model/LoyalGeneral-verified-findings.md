# LoyalGeneral — independent audit against the FULL source tree

The prior three agents verified only `models.rs` and `app.rs` (the two files in `source/`) and
declared `index.html`, `tables.rs`, `engine.rs` unverifiable. I located the full Roundtable tree
at `/home/rich/roundtable/crates` and checked every disputed line. Result: **every line-level
claim in GF1–GF9 is accurate to the digit**, and the "unverifiable" caveat can be retired.

## Line-by-line verification (the disputed files)

- **index.html:423-434** (`assets/index.html`) — confirmed exactly. `model` is a free-text
  `<input>` (`placeholder = "Model (optional)"`), suggestions come from
  `await authed("/api/models").then(r=>r.json()).catch(() => ({}))` guarded by
  `if (!state.openrouterModels)` (once per page load). The trigger set is
  `opencode || "pi-acp" || "openrouter-acp" || /openrouter/.test(command.value)`.
  `opencode` prefixes `"openrouter/" + m`. So **GF1's three sub-claims all hold**: datalist-only,
  free text unchecked, one-per-page-load cache.
- **index.html:429** — `.catch(() => ({}))` confirmed verbatim. **GF2's swallow half holds.**
- **tables.rs:119-121** — `settings.push(("model".into(), model))` — the typed id becomes a
  generic `model` setting. **GF3 half one holds.**
- **engine.rs:966-970** — `harness.set_config(&session, key, value)` loop pushes a warning on
  failure (`warnings.push(... "could not set {key} to {value}: {error}")`) and does **not**
  return; the seat still starts. **GF3 half two holds.**

Note line drift vs the reviewers (they cite tables.rs:124-126, engine.rs:987-990); content is
identical, only offsets differ — the `source/` copy is a slightly different revision. This does
not change any verdict.

## The finding the group MISSED: the OpenRouter key is a per-seat opt-in, not just JEV auth

ViciousMidas correctly flagged that `set_settings` forwards the key to `SetJevKey` (evaluator).
But all three missed the arm that *actually affects OpenRouter seats*:

- `config.rs:50-82` — `SECRET_ENV = ["OPENROUTER_API_KEY", ...]` is **stripped from every
  agent's environment**, and a seat gets it back **only** if `share_openrouter_key` is true
  (`launch_spec`). Default is opt-*out*.
- `tables.rs` `SeatConfig` carries `share_openrouter_key`; the page sets it from the
  `shareBox` checkbox, auto-checked for `openrouter-acp`/`pi-acp` and for `openrouter/` models
  (index.html:437-440).
- `engine.rs:430` passes `self.jev.key()` as the single `key` into `start_seat`, which hands it
  to `launch_spec` for the *seat's* env.

**Consequence for the map:** "pick participants by OpenRouter model id" is only half the story.
A chosen model will *run* only if (a) the harness advertises the `model` setting **and** (b) for
openrouter-acp/pi-acp the seat has the key shared. If the checkbox is off or no key is set,
`launch_spec` returns warning `"asked for the OpenRouter key, but none is set"` and the seat
proceeds key-less. GF4/GF8's "optional bearer key … catalog auth AND SetJevKey" is *still
incomplete* — the third role is **per-seat API credential gating whether the seat can run at
all**, opt-in, default off, secret-stripped otherwise. This belongs in the description under
GF3 (selection use) and GF4 (key roles).

## Verdicts (I concur with all-nine-correct, and raise the evidential status)

GF1,2,3,4,5,6,7,8,9 all **Right**. My delta is not a flip — it is (1) confirming the previously
"adopted on reviewer authority" findings against the full tree, so they are now *verified*, and
(2) adding the `share_openrouter_key` mechanism to GF3/GF4, which none of the drafts record.

See `resolution.md` addendum for the concrete description edits.
