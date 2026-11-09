# ViciousMidas — independent verification & one correction to the resolutions

## What I verified directly (supplied `source/` copy: models.rs, app.rs)

- `models.rs:6` — `MODELS_URL = https://openrouter.ai/api/v1/models`. Correct (GF4).
- `models.rs:9-15` — `OpenRouterModel` keeps only `id`, `name`, `context_length`. Correct (GF4).
- `models.rs:23-26` — optional `bearer_auth(key)` on the GET. Correct (GF4).
- `models.rs:27-28` — returns `listing.data` wholesale; no capability filter. Correct (GF6).
- `app.rs:146` — `/api/models` route exists. Correct (GF5).
- `app.rs:222-228` — on fetch/auth failure returns `502 BAD_GATEWAY` + error string. Correct (GF2/GF7).
- `app.rs:135` — `openrouter_key` seeded from `OPENROUTER_API_KEY`. Correct (GF4/GF8).
- `app.rs:222-224` — every `/api/models` call re-fetches; no server caching. Correct (GF4/GF8).

I could not re-read `index.html`, `tables.rs`, `engine.rs` (sandbox blocks paths outside the
workspace). Their line-level claims are taken on the reviewers' word, as LatentIodine noted.

## The one substantive correction the group missed

**GF4 and GF8 mischaracterize the bearer key as *only* optional auth for the models fetch.**
`app.rs:234-241` (`set_settings`) does two things with `openrouter_key`:
1. stores it in `state.openrouter_key` (which `models()` at app.rs:223 reads for the GET auth), AND
2. sends `roundtable::Command::SetJevKey(key.clone())` to every running table (app.rs:239).

So the same value is **also the JEV (judge/evaluator) credential** pushed into the engine — a
second, unrelated function. `get_settings` (app.rs:231) exposes `openrouter_key_set`, and
`AppState::new` (app.rs:135) seeds it from `OPENROUTER_API_KEY`. This is observable in the
supplied code; it needs no unprovided file.

Consequence: `element.md.proposed` upstream want ("Auth: Bearer key optional; taken from
OPENROUTER_API_KEY or set via POST /api/settings") and `elephant.built` ("optional bearer key")
are both incomplete in a way that matters — a reader would conclude the key only gates the
catalog request. In fact setting it also re-keys the evaluator for every live table. GF4's
resolution ("optional bearer key, sourced from env or POST /api/settings") and GF8's ("auth
(optional bearer key)") should both be amended to record this dual role, and GF4's "unstated
implementation details" finding is even stronger than the reviewer stated.

Action: in `resolution.md`, GF4 and GF8 fixes should say the key is shared — catalog auth AND
`SetJevKey` evaluator credential — and `element.md.proposed` should note the `SetJevKey`
forwarding. No code change required; this is description accuracy.

## Verdict on the nine findings

All nine are correct (I concur with LatentIodine). Fixes are description-side; the only code
change that would be warranted is GF1's optional validate-free-text-against-catalog (and GF6's
filter, only if ACP-capability restriction is actually intended — the code currently offers
everything). My addition does not flip any verdict; it sharpens GF4/GF8 and the proposed text.
