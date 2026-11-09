# Participant selection — review resolutions

Author: FangedCyclops

These decisions use the three files supplied under `source/`. Source paths and line numbers below are relative to that directory. The referenced README, design document, launcher implementation, downstream session-option handler, and sibling map elements were not supplied. Statements about those files or a map-wide schema cannot be verified here. This is a resolution document; it does not modify the implementation or `element.md`.

Most findings warrant expanding the description of existing behavior, rather than changing behavior to match its current abbreviated account. Defaults, option ordering, credential sharing, and validation belong in the element's contract because they affect what the selected participant actually receives.

## GF1 — Accept: document the added adapter and its availability condition

**Evidence:** `crates/roundtable-web/src/tables.rs:73-99` calls ACP autoselection and prepends an entry with id `openrouter-acp`, displayed as “OpenRouter (Agent SDK)”. Both listing and creation use this catalog. Its script path starts at the build-time `CARGO_MANIFEST_DIR` and appends `../../adapters/openrouter-acp/dist/index.js`. Canonicalization happens when the entry is constructed. Failure leaves the entry present but without a launch spec, marks it unavailable, and supplies an `npm ci && npm run build` instruction.

**Change:** Expand `built` and the launcher dependency description to say that participant selection augments the discovered catalog with this repository adapter, including the script location and unavailable/build-note behavior. Keep launch availability distinct from guaranteed runtime success: canonicalizing the script does not verify that Node or all runtime prerequisites work. Prepending in the API catalog does not guarantee first position in the sorted page.

**Why:** Otherwise a reader cannot explain the extra harness or why it may be listed yet unselectable. The fixed build path is a deployment constraint to document; the finding does not establish a requirement for a relocatable adapter or justify a code change by itself.

## GF2 — Accept: document launch defaults and setting order precisely

**Evidence:** `tables.rs:106-126` gives custom commands an initially empty settings vector. Catalog harnesses receive `default_env(id)` and `default_settings(id)`. `crates/roundtable/src/config.rs:198-218` supplies OpenCode permission-routing configuration through `OPENCODE_CONFIG_CONTENT` for `opencode` and `opencode-v2`, Claude `mode=default` for `claude-acp`, and Codex `mode=workspace-write` for `codex-acp`. Other ids receive empty defaults.

**Change:** Add these defaults to the description. State that catalog environment defaults fill missing entries in the launch spec (`or_insert`); they do not overwrite an explicit value already there. Session settings are assembled in order: harness defaults, request `settings`, then a nonblank top-level `model` as another `("model", value)` pair. Custom commands skip harness-specific defaults but still receive the requested settings and model.

**Why:** This ordering determines the option requests sent to a session and the initial permission behavior. Describe ordered application, not a deduplicated map or a locally guaranteed successful override: this function retains duplicate keys. `config.rs:15-16` says a failed session setting is reported loudly and the seat still joins. There is no evidence here that defaults should be imposed on an arbitrary custom command.

## GF3 — Accept the model correction; narrow the aliases claim to the inspected interface

**Evidence:** `SeatRequest.model` is explicitly shorthand for a session option (`tables.rs:59-61`) and is appended for either launch branch without an OpenRouter restriction (`123-126`). Catalog resolution is an exact `entry.id == id` lookup (`114`); no separate alias translation is shown.

**Change:** Replace the consumer want with: “Provides each seat's resolved ACP launch specification, harness id or command label, ordered session settings (including an optional harness-specific model), resume session, and OpenRouter-key sharing choice.” Replace “catalog aliases” in the launcher want with “catalog entries/ids”; retain the separate custom-command path. Do not claim that aliases cannot exist anywhere in the unsupplied launcher.

**Why:** An OpenRouter-only model description misstates the API. Accepting a model field does not prove every harness supports that value; support depends on the harness's advertised option. The supplied interface establishes ids, not a distinct alias facility.

## GF4 — Accept, with qualifications about UI defaults and enforcement location

**Evidence:** `tables.rs:65-70,127-128` accepts the resume id and sharing flag. `index.html:412-450,454-456` offers saved identities and serializes the selected session. `config.rs:52-81` constructs a launch spec that removes `OPENROUTER_API_KEY`, `TYPESAFE_API_KEY`, and `ROUNDTABLE_TOKEN`, then explicitly restores only the OpenRouter key when opted in and a key exists. Opting in without a configured key returns a warning.

**Change:** Document both seat fields and the identity-picker dependency. The picker restores the saved harness/command and model, fills the name only when empty, and submits the saved session; the session must belong to the selected harness. Do not promise that this creation function validates that relationship: it only drops blank resume ids.

Document sharing as **false by default in the API**. On a harness change, the page checks the box for `openrouter-acp` or `pi-acp`; on a model change, it checks the box for an OpenCode model beginning `openrouter/`. These handlers do not automatically uncheck it on later changes. Initial harness selection and identity restoration do not invoke those handlers, so “the page always auto-ticks it for an OpenRouter seat” would be inaccurate.

Record secret filtering as a core launch-spec responsibility consumed by the selection path, rather than claiming `tables::create` performs it. The supplied method defines the filtering; its downstream invocation is outside this snapshot.

**Why:** Sharing is a per-seat credential decision and resumption changes session continuity. Neither should remain implicit. The finding supports documenting the observed conditional behavior; a broader automatic-sharing policy would need a separate product decision and corresponding UI changes.

## GF5 — Accept: document validation, precedence, and workspace interpretation

**Evidence:** `tables.rs:105-128,132,145-146` and `config.rs:96-131`.

**Change:** Add the following rules:

- A nonblank `command` wins over `harness`. A blank command falls through to harness resolution. A seat without either usable route is rejected; malformed custom command lines can also fail parsing.
- Harness ids must match a catalog entry exactly and have a launch spec. Unknown ids and entries with no launch spec fail creation. The backend checks `launch`, not the `available` flag directly; the page disables entries according to `available`.
- Creation trims seat names before core validation. The resulting name must contain 1–40 Unicode characters, each alphanumeric or a space, `_`, `-`, or `.`; core validation rejects leading/trailing whitespace. “Letters and digits” should not be described as ASCII-only because the implementation uses Rust `is_alphanumeric()`.
- Names must be distinct after `to_lowercase()`; this is the implemented case-insensitive comparison, not a guarantee of Unicode normalization or full case folding.
- A relative workspace is joined to the server process's current directory. This is not filesystem canonicalization or a check that the directory exists.

**Why:** These are observable acceptance rules and launch precedence, not implementation trivia. Keep general table validation in its owning core description, with this element explicitly invoking it. No new validator is needed for the reported omissions.

## GF6 — Accept as a small description omission

**Evidence:** `index.html:420-421,469`.

**Change:** State that the page sorts harnesses by availability first, then non-`builtin` before `builtin`, then name using `localeCompare`. Unavailable catalog options remain visible, labelled unavailable, and disabled. Initial selection uses the first available entry or falls back to custom command.

**Why:** This explains the displayed choices and reconciles their order with GF1's API insertion order. Keep it as UI behavior, without requiring the backend catalog to use that ordering or claiming locale-independent alphabetical order. The code shown does not display each entry's diagnostic note in the option label.

## GF7 — Accept: make the harness/model relationship explicit

**Evidence:** `tables.rs:50-70,106-128`; `index.html:143,422-433`.

**Change:** Expand the existing separation rule: the harness/command chooses the ACP process; the model is an optional session setting interpreted by that process. `openrouter-acp` is the bundled adapter route, but it is not the only harness that can use OpenRouter models. The page also offers OpenRouter catalog hints for Pi and OpenCode, and for custom command text containing `openrouter` when no other hints exist. OpenCode hints use the `openrouter/` provider prefix. Other harnesses and custom commands may receive a model value too, subject to their support for the advertised option. Omitting a model adds no top-level model setting.

The model field is free text with a datalist, not a required selection from or validation against the OpenRouter catalog. Selecting an OpenRouter model does not automatically switch the harness.

**Why:** This resolves both ambiguous directions: a model id does not launch an ACP adapter, and selecting a non-OpenRouter harness does not prohibit a model setting. Merge GF3 and GF7 into one coherent description update rather than introducing competing definitions.

## GF8 — Accept: define the operational roles

**Evidence:** The page has chair controls and a chair token (`index.html:115-121,162-169`); custom commands are described as chair-only (`tables.rs:56`); a table request contains the objective, workspace, and seats (`14-35`).

**Change:** Define “chair” as the user/operator controlling the table through the chair-authorized UI/API, “seat” as a named participant configuration whose harness runs an agent session, and “table” as one collaboration run sharing an objective, workspace, and participant roster. Distinguish the chair from participant agents and from JEV, the evaluator.

**Why:** These terms identify who makes the selection and what is being selected. The UI is aimed at a human operator, but token-authorized automation can make API requests; do not invent a human-only identity restriction or claim a chair occupies a participant seat.

## GF9 — Accept: specify count, duplicate policy, and evaluator boundary

**Evidence:** `config.rs:110-112,119-129` requires at least one seat and unique names. Neither `CreateTable.seats` nor the supplied validation establishes a maximum or uniqueness of harness/model combinations. The page initially adds two rows, permits adding and removing rows (`index.html:451,475,479`), and sends every remaining row (`488`). `tables.rs:139,148-152` passes the judging flag and constructs `Jev` separately from the seats.

**Change:** State that at least one seat is required, with no explicit upper bound in this selection/validation code. Two initial UI rows are a convenience, not a two-seat minimum. Reusing harnesses, commands, or model choices across differently named seats is allowed by this validation; duplicate names are rejected as in GF5. This does not establish a policy for reusing the same saved session concurrently.

State that participant rows do not select the evaluator or its model. JEV is constructed separately with the server's OpenRouter key, while the chair can enable/disable judging. Evaluator model selection and runtime behavior belong to the evaluator component, whose implementation was not supplied.

**Why:** These are important roster boundaries. Do not invent an upper limit, ban repeated harnesses, or add an evaluator seat to fix missing documentation.

## GF10 — Partly accept: clarify scope; package requirement is unsubstantiated

**Evidence:** The primary URI points to Rust, not the page. `tables.rs:101-154` resolves seat requests, calls core validation, builds `TableConfig`, starts recording and a table, and inserts its handle into `state.tables`. The supplied UI collects the roster and posts it (`index.html:481-492`).

**Change:** Keep the backend URI as primary and explicitly identify the UI and core config validation as supporting sources. Describe this element as chair roster selection plus server-side resolution/validation and handoff into table creation. Mention live registration and recording delegation without claiming that this module itself durably stores a separately editable roster. No roster-update API is shown here.

**Why:** The UI-only versus backend ambiguity is real. However, no sibling elements or property schema were supplied, so the alleged mandatory missing `package` field is not established. Do not add an invented property merely for symmetry; only add one if the map schema actually requires it and supplies its meaning.

## GF11 — Reject as an established reference inconsistency; optionally improve traceability

**Evidence:** `element.md` lists README section 9 and design sections 3/9 under `references`, while `elephant.sources` lists README subsections 9.3–9.4. The latter are narrower references within section 9, not conflicting claims. A general reference list and an author's account need not contain identical sources. The referenced documents are absent from this snapshot.

**Change:** No corrective code change or mandatory citation replacement is justified. For navigation, the description may align README references to precise verified subsections and add supporting design sections after checking their contents. `tables.rs:74` additionally mentions design §7.3 path 2; this is a lead to verify, not proof that the current design §3/9 references are wrong.

**Why:** Different citation granularity is not itself a defect. Do not assert a documentation contradiction, discard a design reference, or invent what the unprovided sections say.

## Recommended disposition

Update the description for GF1–GF9 and the scope portion of GF10, consolidating GF3/GF7 and GF5/GF9. Keep `gaps` consistent with any accepted description omissions still outstanding. Retain existing behavior unless a separate requirement establishes a code defect. Treat GF10's package claim as unverified and GF11's asserted mismatch as unsupported. The supplied snapshot supports these decisions by static inspection; it has no build manifest or complete dependency tree for a runnable integration check.
