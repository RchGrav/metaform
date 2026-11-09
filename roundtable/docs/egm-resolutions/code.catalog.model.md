# OpenRouter model selection — review resolutions

Prepared by ExactGeneral. These are decisions and proposed changes; application code and `element.md` have not been changed.

## Evidence and scope

The supplied snapshot contains only `crates/acp-host/src/models.rs` and `crates/roundtable-web/src/app.rs`. References below use paths relative to `source/`. The cited `assets/index.html`, `tables.rs`, `engine.rs`, and README are absent. Browser and session behavior reported by the reviewers is therefore identified as reported, not independently verified. Their absence does not justify rejecting the observations, but those files must be checked before implementing the corresponding changes.

The verified contract is catalog discovery: fetch OpenRouter's published model identifiers rather than maintain a fixed list. Catalog membership alone does not establish tool capability, account access, harness compatibility, or successful application of a requested model.

## GF1 — Accept the clarification; reject the implied requirement for a closed picker

**Decision:** Partly right. Datalist suggestions still constitute listing models. Neither “lists” nor “pick … by … model id” explicitly requires catalog membership validation. Free text is not, by itself, a violation. However, the reported harness restrictions and page-lifetime caching materially qualify the claim that the page offers a live catalog.

**Change:** Describe the browser control as free-text model input with catalog suggestions loaded on focus for `openrouter-acp`, `pi-acp`, `opencode*`, and commands containing `openrouter`, using the reviewer's reported detection rules. Document the reported `openrouter/` adaptation for OpenCode and distinguish that harness value from the upstream model ID. State that the browser reuses the fetched list until page reload; “current” means fetched from the service, not continuously refreshed. Confirm those details against the missing HTML before finalizing the description.

Do not introduce mandatory membership validation solely to satisfy this finding. Add an explicit refresh/retry action as part of GF2 so the chair can recover from stale data or failures without reloading. There is no established requirement for periodic refresh or a fixed refresh interval.

## GF2 — Accept; repair failure presentation and retry

**Evidence:** `app.rs:222–227` returns `{models: …}` on success and HTTP 502 with `{error: …}` on failure. `models.rs:27` propagates request, upstream HTTP-status, and JSON decoding errors. The silent empty-list behavior is reported from the missing HTML.

**Change:** Keep the server's error response. In the browser, check the HTTP status and response shape, show a visible catalog-load error, and provide retry. Do not convert failures into a successful empty catalog or retain a failed result as the page's permanent cache. An actually empty successful response must remain distinguishable from failure. Retry must issue a new request, including after a key change; it must not reuse a rejected or empty failure promise. Preserve manual input and any already entered value.

**Why:** The server already distinguishes failure from an empty catalog; the reported browser path discards that distinction and hides the recovery path. Add a browser-level check for a failed request followed by a successful retry when implementing this fix.

## GF3 — Accept as a missing downstream contract, with an evidence qualification

**Decision:** The reported conversion into a generic `model` session option and warning-only behavior are significant limits on what “pick participants by … model id” promises. They cannot be independently confirmed from this snapshot. The description must not imply that catalog selection guarantees that a particular harness uses that model.

**Change:** Add a description of the handoff: the requested model value becomes a session configuration option and is applied through the harness's `set_config` mechanism. Record the reported limitation that an unadvertised option produces a warning while the participant still joins; explicitly distinguish a requested model from a confirmed model. Assign configuration enforcement to the participant/session component, rather than to the HTTP catalog reader.

**Why:** Discovery and application are separate operations. The supplied description establishes no fail-on-unsupported policy, so this finding alone does not justify changing admission behavior. If the product requires guaranteed model selection, that is an additional contract: the session component should refuse readiness when an explicit model cannot be applied and test that behavior. Do not claim that contract is already implemented.

## GF4 — Accept as documentation detail; no reader change required

**Evidence and change:** Record the fixed endpoint `https://openrouter.ai/api/v1/models` (`models.rs:6`); optional upstream bearer authentication (`models.rs:23–26`); initial key from nonempty `OPENROUTER_API_KEY` (`app.rs:135`); and in-memory updates through the `openrouter_key` field of `POST /api/settings` (`app.rs:234–242`). Settings updates trim whitespace and an empty value clears the key. The setter does not validate credentials against OpenRouter.

**Shared-key side effect (identified by ViciousMidas, `app.rs:234–242`):** when settings supply an `openrouter_key` string, the handler also calls `handle.send(roundtable::Command::SetJevKey(key.clone()))` for every running-table handle, including when clearing the key. Document this coupling to evaluator-key configuration as well as catalog authentication. The supplied code proves the command is sent; its return value is ignored and the engine implementation is absent, so it does not prove every evaluator successfully changes credentials. This is a documentation correction, with no code change required by this finding.

Record that only `id`, `name`, and `context_length` are retained; `name` defaults to an empty string and context length is optional (`models.rs:9–15`). Each admitted `/api/models` request makes an upstream fetch; this handler has no server catalog cache (`app.rs:222–227`). This is compatible with a separate browser cache.

**Why:** These facts explain the dependency and its operational behavior. More metadata and server caching are not requirements established by the description.

## GF5 — Reject that the primary URI is wrong; accept adding implementation references

**Decision:** `crates/acp-host/src/models.rs` is a correct primary location for this element's reusable catalog reader. Nothing in the supplied map defines `uri` as an exhaustive list of every integration file. A single primary URI is therefore not a demonstrated defect.

**Change:** Keep `properties.uri`. Add supporting implementation references to `crates/roundtable-web/src/app.rs` (`/api/models`, settings, and authentication) and `crates/roundtable-web/assets/index.html` (the reported input/suggestion behavior). Keep downstream session configuration under the participant component and cross-reference it as appropriate.

**Why:** This makes the end-to-end claim traceable without changing the element's primary identity or inventing a new URI format.

## GF6 — Accept the ambiguity; resolve it as an unfiltered discovery catalog

**Evidence:** `models.rs:20–28` deserializes and returns the entire `data` array without filtering. The retained fields contain no tool-support information. `app.rs:225` forwards that list without filtering.

**Change:** State explicitly: “All entries returned by the published models endpoint are exposed as discovery candidates. This component does not filter for tool calling or certify ACP/MCP compatibility.” Qualify “models a participant can use” in the consumer want to mean candidate model identifiers whose usability depends on the selected harness, account, and session configuration.

**Why:** The implementation conclusively answers what this reader returns. The requirement for participants to use tools does not establish that this reader must certify them. Do not add a speculative tool filter or claim that an upstream capability flag would guarantee end-to-end ACP/MCP operation. If compatibility filtering becomes a requirement, define and implement that separate policy with the harness integration.

## GF7 — Accept; combine its remedy with GF2

**Change:** Document transport, upstream HTTP/authentication, and malformed-response failures as catalog failures returned by `/api/models` as HTTP 502 with an error message. Document the browser's reported silent handling as a gap until GF2 is implemented. The intended browser behavior is a visible error, retry, and retained manual input; it must not synthesize a fixed model list or substitute a model automatically. Manually entered IDs remain subject to downstream configuration and provider acceptance.

Also distinguish authentication boundaries: the local API requires the chair credential and valid Host/Origin; a missing or wrong chair token returns 401 (`app.rs:169–198`). The optional OpenRouter key is a different credential. An upstream authentication error is handled by the catalog handler as 502, not as a local chair-token failure.

**Why:** The absence of a fixed list does not prevent an explicit failure state or manual entry. The server behavior exists already; user-visible recovery and its documentation are the unresolved work. GF2 and GF7 describe one failure-handling issue, not two separate implementations.

## GF8 — Accept; document the same dependency contract as GF4 and GF1

**Change:** Expand the upstream want with the HTTPS host and path, optional upstream bearer key, and fresh upstream request per admitted local API request. Separately document the reported browser cache and the proposed explicit refresh/retry behavior. Include the local chair-token requirement so readers do not confuse the two credentials. Cross-reference GF4's settings side effect: updates to the optional OpenRouter key also send `SetJevKey` commands to running-table handles.

**Why:** “Current” describes the source of the list; it does not establish continuous freshness. No additional caching mechanism or automatic polling is required by this finding. This is a documentation overlap with GF1/GF4, not a separate code defect.

## GF9 — Accept the terminology clarification; reject a consumer contradiction

**Change:** Define the chair as the human operator configuring a discussion, a seat as a configured participant position, and a harness as the ACP adapter/session implementation running that participant. Clarify the relationship: participant configuration consumes model candidates; the web page is the interface through which the chair supplies that configuration.

**Why:** A logical consumer (`code.roster.participant`) and its user interface (“the web page”) can both be accurately named. The differing terms do not establish incorrect wiring. Add the glossary and relationship rather than replacing the consumer dependency with the page.

## Resulting description and implementation work

Revise the design/built account to describe published-catalog discovery, free-text suggestions, freshness boundaries, unfiltered candidates, and the downstream configuration limitation. Replace `gaps: []` with the reported hidden browser failure/retry gap and the unverified downstream model-application limitation, pending inspection of the missing files. Consolidate endpoint/authentication details and terminology once, cross-referencing them rather than duplicating GF4/GF8 and GF2/GF7.

The concrete code remedy supported by these findings is browser error presentation and retry/refresh with failure-cache invalidation. A mandatory catalog-only picker, automatic polling, tool-capability filtering, or rejection of unsupported model settings would each require an additional product contract. They are not implied by the current catalog-discovery description.

## Consensus note (LatentIodine)

I converge with the above on all nine findings. Two points worth recording explicitly:

- **GF5** — I withdraw my earlier "uri is wrong" reading: `uri` is a *primary* location, not an exhaustive list, so keeping it and adding supporting references (`app.rs`, `index.html`) is the correct fix. This matches ExactGeneral's GF5.
- **GF1** — I accept the "partly right" framing: free-text is not inherently a violation; the real correction is describing the datalist-hint control accurately, not mandating a closed picker. This matches ExactGeneral's GF1.
- **GF4/GF8** — the verified settings side effect omitted from the earlier drafts is added above: updates to `openrouter_key` also send `SetJevKey` commands to every running-table handle (`app.rs:239`). This should be reflected in the description, subject to GF4's distinction between sending a command and confirming its application.

## Status of the separate proposed description

`element.md.proposed` is a discussion draft, not an adopted replacement for `element.md`. At the time of this consolidation it still broadens `properties.uri`, contrary to the GF5 decision; states browser/session behavior without the evidence qualifications above; and describes refresh as “per page-load fetch,” which obscures the reported first-focus trigger and browser cache. Reconcile those points before adopting it. Describe unfiltered discovery and the deliberate absence of a fixed fallback as contract facts rather than automatically treating them as implementation defects. These decisions in `resolution.md` remain the authoritative requested deliverable.

## Addendum (LoyalGeneral) — full-tree verification and the per-seat key opt-in

The caveat in "Evidence and scope" that `index.html`, `tables.rs`, `engine.rs` are absent and
therefore unverifiable is now **retired**: the full tree is at `/home/rich/roundtable/crates`
and every disputed line was inspected. Results:

- GF1 **Right, now verified**: `assets/index.html:423-434` — free-text `<input>` with a
  `datalist`, hints fetched from `/api/models` only on focus, guarded by
  `if (!state.openrouterModels)` (once per page load); triggers `openrouter-acp`, `pi-acp`,
  `opencode*`, or a command matching `openrouter`; OpenCode prefixes `openrouter/`. All three
  sub-claims hold. Fix: describe the control as free text with catalog suggestions per page
  load; do not mandate a closed picker.
- GF2 **Right, now verified**: `app.rs:222-228` returns 502 + error; the page's
  `.catch(() => ({}))` (index.html:429) discards it. Fix: show a visible error + retry, keep
  manual input, never cache a failure.
- GF3 **Right, now verified**: `tables.rs` pushes the typed id as a generic `model` setting;
  `engine.rs:966-970` calls `set_config`, and on failure only pushes a warning and lets the
  seat join. **Plus a gap the drafts lack (below).**
- GF4–GF9 done: correct as recorded. GF5's uri broadening and the GF6 "no filter" statement
  match `models.rs:27-28` / `app.rs:225`.

**New, verified correction to GF3 and GF4 (not in any prior draft):** the OpenRouter key is a
*per-seat opt-in credential*, distinct from catalog auth and JEV auth.
`config.rs:50-82` strips `OPENROUTER_API_KEY` from every agent; a seat regains it only when
`SeatConfig::share_openrouter_key` is true (`launch_spec`), default false. The page auto-checks
the "key" box for `openrouter-acp`/`pi-acp` and for `openrouter/` models (index.html:437-440).
`engine.rs:430` feeds `self.jev.key()` into `start_seat`, which passes it to `launch_spec`.
So a chosen model runs only if the harness advertises `model` **and** the seat has the key
shared; otherwise it joins key-less (warning "asked for the OpenRouter key, but none is set").

Concrete description changes to adopt:
1. In the upstream-want (GF8) and GF4, list **three** roles of the key: (a) optional upstream
   bearer for GET /api/v1/models, (b) `SetJevKey` evaluator credential, (c) **per-seat API
   credential, shared only when the seat opts in (default off; stripped otherwise)**.
2. In GF3's handoff text, state that a model id is a *request*: it applies only if the harness
   advertises the `model` setting and — for OpenRouter harnesses — the seat has the key shared;
   otherwise the seat still joins, with a warning. This is why GF3 is a missing downstream
   contract, not a catalog defect.
3. Retire the "reported, not verified" qualifier for GF1/GF2/GF3: they are now verified.
