# Resolution of review findings — `code.roster.participant` (participant selection)

Author: DefiantHunter

Scope: this element governs turning the chair's per-seat choices into `SeatConfig`s and the
harness catalog the page offers. The code under review is
`crates/roundtable-web/src/tables.rs`, `crates/roundtable/src/config.rs`, and the seat form in
`crates/roundtable-web/assets/index.html`. Findings are judged against what the code does, not
against what a fuller description might ideally contain. The test for "right" is: does the
element description (`element.md`) fail to tell a reader something the code actually does (or
misstates it)?

Summary verdicts:

| Finding | Verdict | Fix target |
|---------|---------|------------|
| GF1 | Right | description |
| GF2 | Right | description |
| GF3 | Right (both parts) | description |
| GF4 | Right | description |
| GF5 | Right | description |
| GF6 | Right | description |
| GF7 | Right | description |
| GF8 | Right | description |
| GF9 | Partly right | description |
| GF10 | Right | Properties |
| GF11 | Right | references / elephant |

Nothing needs a code change: all ten findings are documentation gaps or small inaccuracies in the
description. That is itself an important conclusion — the code is behaving as the roles and rules
require; the map element under-describes it.

---

## GF1 — OpenRouter adapter entry (Major) — RIGHT

The catalog is `acp_host::launch::autoselect` **with an entry prefixed at index 0**
(`tables.rs:76-80`). That entry has id `openrouter-acp`, name "OpenRouter (Agent SDK)", command
`node`, and its script path is computed at **compile time** from `env!("CARGO_MANIFEST_DIR")`
joined with `../../adapters/openrouter-acp/dist/index.js` (`tables.rs:82-99`). When the script is
missing it is *not* dropped: the entry is kept with `launch = None`, `available = false`, and a
`note` telling the operator to run `npm ci && npm run build` in `adapters/openrouter-acp`
(`tables.rs:86-96`). `catalog_tests::openrouter_adapter_is_launchable_or_says_why`
(`tables.rs:170-185`) pins both branches.

Why this matters for the description, not the code: the element says it relies on
`code.launcher.agent` to "list registered harnesses, catalog aliases and user-supplied ACP
commands." But this element **adds a harness of its own**, one that launcher.agent never produces.
A reader of the map would not know that "participant selection" is also a *producer* of a harness
entry, nor that availability is a build-time property of the checkout. The docstring even cites
"R §9.4, D §7.3 path 2," i.e. the behavior is deliberate and traceable.

**Change (description):** under "What it relies on (its wants)" and/or a new "What it does" note,
state: *This element prepends a built-in `openrouter-acp` harness to the launcher's catalog. Its
launch path is fixed at compile time relative to the crate (`CARGO_MANIFEST_DIR/../../adapters/
openrouter-acp/dist/index.js`); if the built adapter is absent the entry is still listed but
marked unavailable, with a build-hint note, and cannot be seated.*

---

## GF2 — Defaults (Major) — RIGHT

`roundtable::default_env(id)` and `roundtable::default_settings(id)` are applied only on the
catalog branch (`tables.rs:116-119`), never on the custom-command branch (`tables.rs:107-109`,
which returns `Vec::new()`). `config.rs:198-218` defines them:

- `default_env`: `opencode`/`opencode-v2` → `OPENCODE_CONFIG_CONTENT` with every permission set to
  `"ask"` so permission requests are routed to the ACP client (Roundtable) instead of being
  self-granted.
- `default_settings`: `claude-acp` → `mode=default`; `codex-acp` → `mode=workspace-write`.

The order of the final `settings` vector is: **defaults, then chair-supplied `seat.settings`, then
`model`** (`tables.rs:123-126`). Since `SeatConfig.settings` is applied in order and a later
setting overrides an earlier one (per the docstring at `config.rs:11-13`, "in order (e.g. mode,
then model)"), the chair can override a default, and the model shorthand always wins last.

**Change (description):** add a rules/knowledge bullet: *Catalog seats get harness defaults:
OpenCode gets `OPENCODE_CONFIG_CONTENT` (all permissions "ask", routed to Roundtable); Claude gets
`mode=default`; Codex gets `mode=workspace-write`. Custom-command seats get no defaults. Settings
are ordered defaults → chair settings → model shorthand.*

---

## GF3 — "where applicable, its OpenRouter model id" and "catalog aliases" (Major) — RIGHT

Two independent errors in the wants/relies prose:

1. `SeatRequest.model` is `/// Shorthand for the `model` session option.` (`tables.rs:59-61`) and is
   appended to `settings` for **any** seat that has a non-empty model, regardless of harness
   (`tables.rs:124-126`). So the model is *not* an OpenRouter-only, "where applicable" concept; it
   is a generic session option. The seat's harness decides whether a given model id makes sense.
   The "where applicable" phrasing is narrower than the code and, worse, suggests to the reader
   that only OpenRouter seats take a model (directly the confusion GF7 raises).
2. "catalog aliases" appears in this element's wants for `code.launcher.agent` ("Lists
   registered harnesses, catalog aliases and user-supplied ACP commands") and is not a concept the
   code implements. `catalog` returns `Vec<acp_host::HarnessEntry>` of autoselected harnesses plus
   the one built-in adapter; there is no alias layer. The on-disk `acp-host` crate is a dependency
   not shipped here, but nothing in this element's code references aliases, and `SeatConfig.
   harness` is documented as "Harness catalog id or label, for display" (`config.rs:9-10`) with
   lookup by exact `e.id` (`tables.rs:114`). The phrase should be dropped unless the launcher
   element author can point to the alias mechanism; as written it is a phantom concept.

**Change (description):**
- Reword the rely-on want for seats to "Provides each seat's harness and its session options,
  including an optional model."
- Reword `code.launcher.agent` want to "Lists registered harnesses and user-supplied ACP
  commands" and remove "catalog aliases" (or justify it against acp-host; see note above).

---

## GF4 — Undocumented seat fields (Major) — RIGHT

Three real behaviors are absent from the element:

- `share_openrouter_key` (`tables.rs:69-70`, passed through at `tables.rs:128`). The page
  auto-ticks it for `openrouter-acp`, `pi-acp`, and an OpenCode seat whose model starts with
  `openrouter/` (`index.html:436-441`). Setting it causes `SeatConfig::launch_spec` to insert
  `OPENROUTER_API_KEY` into the agent's environment (`config.rs:70-84`).
- `resume_session` plus the identity picker (`index.html:412-450`; passthrough at `tables.rs:127`).
  Resuming continues an earlier harness session so the agent keeps its identity; the harness must
  be the one holding that session (`config.rs:20-27`).
- Removal of Roundtable secrets from agents: `launch_spec` removes every name in `SECRET_ENV`
  (`OPENROUTER_API_KEY`, `TYPESAFE_API_KEY`, `ROUNDTABLE_TOKEN`) from the inherited environment and
  records them in `env_remove` so they are excluded even if reintroduced by the parent
  (`config.rs:52-84`). The chair token never reaches an agent; the OpenRouter key is opt-in only.

**Change (description):** add to the element's "What it does"/knowledge:
*Each seat may opt in to `share_openrouter_key`; only `OPENROUTER_API_KEY` can be shared this way,
and only when a key is configured. All of `OPENROUTER_API_KEY`, `TYPESAFE_API_KEY` and
`ROUNDTABLE_TOKEN` are otherwise removed from the agent's inherited environment; the chair token
never reaches an agent. A seat may resume a prior harness session to keep the agent's identity; the
harness must hold that session.*
Because the auto-tick rules live in the page, also note that they are a **UI convenience**, not a
correctness requirement — the server honors the flag but does not auto-derive it.

---

## GF5 — Validation rules (Major) — RIGHT

Kept to what this element's code (and the core it calls) enforces:

- A seat needs a harness **or** a non-empty command; otherwise `bail!("seat {name:?} needs a
  harness or a command")` (`tables.rs:121`).
- Command wins over harness: the match arm `(Some(command), _) if !command.trim().is_empty()`
  comes before the harness arm (`tables.rs:106-109`). The page also enforces this by disabling the
  command field when a harness is selected, but the server is what matters.
- An unknown id is `unknown harness {id}` and an unlaunchable id is `{id} cannot be launched here:
  {note}` (`tables.rs:114-115`).
- Names are 1–40 chars, trimmed, and only alphanumeric / space / `_` / `-` / `.`
  (`valid_seat_name`, `config.rs:96-104`); duplicates are rejected **case-insensitively**
  (`config.rs:127`, `to_lowercase`). Note the finding says "1-40" — the code is chars, not bytes,
  so non-ASCII alphanumerics count singly (worth stating).
- Relative `workspace` is resolved against the server's current directory
  (`std::env::current_dir()?.join(...)`, `tables.rs:132`).
- Whole-table invariants also live in the same validate call the element delegates to: at least
  one seat, non-empty objective, reply limits ≥1, at least one round (`config.rs:108-118`). These
  belong to the element as the point where the roster is validated; state that the element calls
  `TableConfig::validate`.

**Change (description):** add a "Validation" subsection enumerating the above, and say the
element both builds and validates the roster (which also answers GF10).

---

## GF6 — Harness ordering / disabled entries (Nit) — RIGHT

`index.html:469` sorts: available first (`b.available - a.available`), then non-builtin before
builtin (`(a.source==="builtin") - (b.source==="builtin")`), then `name.localeCompare`.
`index.html:420` renders unavailable harnesses with " (unavailable)" and `disabled = !h.available`,
so they are visible but not selectable in the page. This is genuinely a page-side presentation
detail, so a nit is the right severity. It is still undocumented and a reader cannot predict the
dropdown order.

**Change (description):** one sentence in the element knowledge: *The page lists harnesses
available-first, user/non-builtin before builtin, then by name; unavailable entries are shown
disabled.*

---

## GF7 — How harness and model combine (Major) — RIGHT

This is the core comprehension gap and it is consistent with GF3: because `model` is a generic
session option, an OpenRouter seat is expressed as *harness = `openrouter-acp` (or `pi-acp`) plus
`model = <openrouter id>` plus `share_openrouter_key`*. For other harnesses the model is passed as
their own `model` session option (OpenCode prefixes ids with `openrouter/`, per `index.html`'s
model hint logic). Nothing in the description says this. The rule in `element.md` "an OpenRouter
model id is not an ACP harness" is correct but only half the story: it tells you what the model is
*not* without telling you how to seat one.

**Change (description):** state the combination explicitly:
*An OpenRouter model is selected by choosing an ACP harness that speaks OpenRouter
(`openrouter-acp` or `pi-acp`, or an OpenCode seat with an `openrouter/`-prefixed model) and giving
the seat a model id, typically with `share_openrouter_key`. For every other harness the model is
that harness's own `model` session option and may be empty.*

---

## GF8 — Chair / seat / table undefined (Major) — RIGHT

The description uses "chair", "seat", "table", "harness", "seat's harness" without definitions,
and never says whether the chair is a human or an agent. In the code the chair is clearly the
**human operator holding the chair token**: `SeatRequest.command` is gated "chair only: the API is
behind the chair token" (`tables.rs:56-58`), commands such as `Advance` are attributed to
`"the chair"` (`tables.rs:164`), and `ROUNDTABLE_TOKEN` is the "chair credential" that never
reaches agents (`config.rs:52-55`). A reader cannot infer that from the element alone.

**Change (description):** add a short glossary:
*Chair: the human operator holding the chair token; it selects seats, sets table parameters and
sends commands. Seat: one participant's configuration (name, harness or command, settings). Table:
one Roundtable run seating several agents. Harness: an ACP agent adapter (catalog entry or custom
command).*

---

## GF9 — Seat count, duplicates, evaluator (Major) — PARTLY RIGHT

Split into three:
- **Seat count:** the element imposes **no upper limit** on seats; only "at least one seat"
  (`config.rs:117`) and reply/round limits. So "seat count limits" is answered by "there is no
  maximum; minimum is one," which should be stated.
- **Duplicates:** rejected, case-insensitively (`config.rs:127`) — covered under GF5; should be
  stated here too if this finding is kept separate.
- **Evaluator chosen here:** **not** chosen in participant selection. The evaluator is JEV
  (`Jev::new` built in `create` at `tables.rs:149`), while `judging` is only an on/off table
  parameter (`CreateTable.judging`, default true, `tables.rs:21-22`, passed into `TableConfig`).
  The seat list is unrelated to which evaluator runs.

So the finding overstates by implying there may be count limits and by lumping the evaluator in;
but the needed clarifications are real. Verdict: partly right — accept the recommended
clarifications, reject the premise that the element should define a seat-count limit (it has none)
and the suggestion that the evaluator is selected here (it is not).

**Change (description):** *Seats: at least one, no upper limit; names unique case-insensitively.
The evaluator is JEV, not a seat; the chair toggles judging on/off but does not choose the
evaluator here.*

---

## GF10 — Properties uri / scope / missing package (Nit) — RIGHT

The element's `uri` is `crates/roundtable-web/src/tables.rs`, yet the behavior it must describe
spans three files: the web `tables.rs` (builds/validates the roster), `crates/roundtable/src/
config.rs` (defaults, secret stripping, name validation), and `assets/index.html` (the seat form,
ordering, auto-ticks). The element is therefore **not** UI-only and **not** single-file. Sibling
elements apparently carry a `package` property; this one omits it.

**Change (description):** add `package` (matching siblings, e.g. the roundtable core/web package
name), and make the `uri` or a new `files` field list all three files, or state in prose that the
element owns the roster contract and cites the core config module it delegates validation to.

---

## GF11 — References vs elephant sources (Nit) — RIGHT

References cite README §9 and `Roundtable_ACP_Integration_Design.md` §3 and §9; `elephant.sources`
cites only "README.md §9.3-9.4". The two are inconsistent (one is broader and includes the design
doc). This is a minor bookkeeping defect, but it matters for auditability: a reader cannot tell
whether the design doc is a source of record for this element.

**Change (description):** make `elephant.sources` list the same references (README §9.3-9.4 plus
Design §3 and §9), or narrow the references to match. Prefer listing both, since the docstring in
`tables.rs:73-74` itself cites "R §9.4, D §7.3 path 2" and the code at `tables.rs:85` reflects a
design decision that belongs in the design doc.

---

## Cross-cutting note: one fix resolves several findings

GF3, GF5, GF7 and GF10 all stem from the description treating this element as "a page that offers
harnesses and models" while the code is "the roster builder/validator, the catalog augmenter, and
the form." A single rewrite that (a) states the element builds *and validates* the roster, (b)
lists the three files it spans, and (c) states the harness/model/command composition explicitly,
closes GF3, GF5, GF7 and GF10 together. GF1, GF2, GF4, GF6 are additive knowledge bullets; GF8 is a
glossary; GF9 is a partial correction; GF11 is a bookkeeping fix.
