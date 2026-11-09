# Resolution of review findings: `collection.workspace.shared` (shared workspace)

Decisions by **NeuralEarth**. Each finding is judged against the description in `element.md`
and the code actually copied into `source/`.

## Scope of the evidence (read this first)

The `source/` folder for this element contains only three files:

- `crates/roundtable/src/config.rs`
- `crates/roundtable/src/engine.rs`
- `crates/roundtable/resources/roundtable_prompt.md`

The findings also cite `tables.rs:132/137`, `turn.rs:399-407`,
`acp-host harness.rs:392-427`, `README.md` (§2, §4.4), `TRACEABILITY.md`,
"Roundtable 7 proposals", and the "owner's evaluation specification". **None of these are in
this element's copied source.** I therefore mark each finding as *verified*, *verified against
sibling source*, *partially verified*, or *unverifiable*, and I never treat an un-copied
reference as proven without checking it. Where the substantive claim is independently
confirmable in engine.rs/config.rs, I decide on that basis.

**Update after cross-checking:** three of these files do exist as sibling elements of the same
repository (see Cross-cutting #2), and I verified the relevant lines directly: GF3's ACP method
mapping, GF4's relative-path resolution, and GF6's `idle_topics` idle-topic warning. Those
findings are now corroborated against real code rather than merely asserted. The accurate
provenance label is "verified against sibling source", **not** "verified in this element's
source", until those files are copied into `source/`. My first revision wrongly treated GF6's
`idle_topics` as dead state; the sibling `turn.rs` proves it is read and written — that
correction is recorded below.

A second framing point: this element is a **functional-map document** (see `element.md:3`),
not the program. Its job is to record "what each part must do, what it relies on, and
knowledge about it". The review defines Blocker as a description/code contradiction and Major as an important gap. So most valid findings resolve to a
**description change** (add the missing knowledge / correct the want); a finding resolves to a
**code change** only where the code breaks an owner principle or an invariant the map promises.
I apply that distinction below rather than reflexively recommending edits to both.

---

## GF1 — (Major, codebase-details, edge cases)
> Workspace creation failure is ignored: `let _ = create_dir_all` and a canonicalize fallback
> (engine.rs:402-404). No notice is raised; the failure surfaces only when session open fails.

**Decision: RIGHT, but partially; resolves to a CODE change plus a one-line description note.**

Verified against engine.rs:402-404:
```rust
let _ = std::fs::create_dir_all(&self.cfg.workspace);
let workspace = self.cfg.workspace.canonicalize()
    .unwrap_or_else(|_| self.cfg.workspace.clone());
self.cfg.workspace = workspace.clone();
```
The `create_dir_all` result is discarded and the canonicalize failure silently falls back to
the un-canonicalized path. No `notice(...)` is published in `start()`. Session open is the
only later point that would fail loudly (`Internal::SeatStarted` → `SeatFailed`, engine.rs:834-838).

Why it matters for *this* element: `engine.rs:12` states the owner principle **"Failures are
loud (O). Nothing polls (O)."** Silently swallowing a failure of the very directory that
constitutes this element contradicts that principle. Two concrete harms: (a) `ScopePolicy::new(scope)`
(engine.rs:406) is then built over a path that may not exist / may be non-canonical, so the
permission boundary the shared workspace relies on is wrong from the start; (b) the operator
gets no signal until a seat fails.

What to change:
- **Code (primary):** in `Table::start`, handle the `create_dir_all` error — publish a
  `Notice { level: "error" }` (and treat canonicalize failure the same way) before building the
  policy, or return a `ConfigError` from `spawn` so `validate()`/host startup fails loudly.
  This restores "Failures are loud" and protects the ScopePolicy invariant.
- **Description (secondary):** `elephant.built` should say the folder is created best-effort at
  table start and that the effective path is the canonicalized `cfg.workspace` published in
  `TableOpened` (engine.rs:411). Today `elephant.built` ("Every agent's session opens in the
  table's workspace folder") reads as if the folder is guaranteed present.

Caveat on severity: the reviewers call this Major. It is a real gap, but it is an **edge case**
(a missing/unwritable parent dir), and in the normal case `create_dir_all` on an existing or
creatable directory succeeds. I would not downgrade it (the silent-failure + wrong-scope
combination is legitimate), but I record that it is conditional, not a guaranteed defect.

---

## GF2 — (Major, codebase-details, elephant.built)
> Write access depends on ScopePolicy over cfg.scope (defaults to workspace, configurable;
> engine.rs:405-406; config.rs:144-146; tables.rs:137), and on the harness routing permissions
> via mode or env (config.rs:189-218); otherwise only a warning (engine.rs:992-995). Not documented.

**Decision: RIGHT (verified in the copied code); resolves to a DESCRIPTION change.**

Verified:
- engine.rs:405-406: `scope = self.cfg.scope.clone().unwrap_or_else(|| workspace.clone())`;
  `Arc::new(ScopePolicy::new(scope))`.
- config.rs:143-146: `workspace: PathBuf` and `scope: Option<PathBuf>` ("Root that permission
  requests are checked against; defaults to the workspace") — so scope is configurable and can
  differ from the shared workspace.
- config.rs:189-218: `default_settings` (claude → `mode=default`, codex → `workspace-write`),
  `default_env` (opencode → `OPENCODE_CONFIG_CONTENT`), `PERMISSION_ROUTING_ENV`.
- engine.rs:992-995: if no `mode` setting and no routing env var, the only consequence is a
  **warning string** pushed to `warnings`; it does not block the seat.
- `tables.rs:137` is not copied, so the claim that the host *configures* scope there is
  unverifiable; but config.rs:146 already proves `scope` is a public, serde-deserialized field,
  so the substantive point stands without it.

Why right: `elephant.built` says agents "read and write each other's files there" as an
unqualified fact. In reality that write access is **conditional** on three things the map never
names: the `scope` root, the harness `mode`/env routing, and the fact that missing routing is
only warned about. A reader of the map would wrongly assume writing is guaranteed by the
workspace alone. This is exactly a "description says something the code does not (unconditionally)
do."

What to change (description): extend `elephant.built` / add a `gaps` or `knowledge` entry:
- The permission boundary is `cfg.scope` (defaults to `workspace`, configurable independently).
- Enforcement requires the harness to route permission requests to Roundtable via a `mode`
  session setting or `PERMISSION_ROUTING_ENV` (e.g. `OPENCODE_CONFIG_CONTENT`); otherwise the
  engine only emits a warning (engine.rs:992-995) and the scope may not be enforced.
- More precise wording: "Agents share a working directory. Requests routed to Roundtable use
  its scope policy; a harness may instead enforce its own sandbox (the Codex workspace-write
  default). Actual access also depends on filesystem permissions. Shared cwd alone guarantees
  neither writable access nor confinement."

No code change needed: the warning is an intentional, documented-in-code design (config.rs:189-197
explains the builder policy). The defect is that the map omits it.

---

## GF3 — (Major, codebase-details, wants (code.client.agent))
> Resumed seats pass the cwd via session/resume or session/load, not session/new
> (engine.rs:976-978; acp-host harness.rs:392-427).

**Decision: PARTLY RIGHT; resolves to a DESCRIPTION change (correct the want's wording).**

Verified in engine.rs:976-978:
```rust
let opened = match &seat.resume_session {
    Some(id) => harness.resume_session(workspace, id, servers).await,
    None => harness.open_session(workspace, servers).await,
};
```
Both branches pass `workspace` (the shared folder) as the first argument. config.rs:23-28
documents `resume_session`. So the *substance* is confirmed: a resumed seat gets its cwd via a
different ACP call than a new seat. The exact wire methods were verified against the sibling
element `code.client.agent/source/crates/acp-host/src/harness.rs:392-427`:
`resume_session` issues `session/resume` on ACP v2 (`s2::ResumeSessionRequest`), and on v1 uses
`session/resume` when the agent advertises it, else falls back to `session/load` via `load_v1`.
So the finding's "session/resume or session/load" wording is accurate, not loose — the "or" is
the v1 capability branch. The new-seat path (`open_session`) corresponds to `session/new`. Note
this file is not in *this* element's `source/`; the status is "verified against sibling source",
not "verified in this element's source" (see Cross-cutting #2).

Why the want is still wrong: `element.md:16` says
`Function: Supplies the directory passed as cwd on session/new.`
That names only one call path. Resumed seats (config.rs:28) are a real supported mode, so the
want is inaccurate/incomplete — it describes the new-seat path as if it were the only one.

What to change (description): reword the want to be path-neutral and complete, e.g.
"Supplies the directory passed as the session cwd, for both new sessions (`open_session` →
`session/new`) and resumed sessions (`resume_session` → `session/resume`, or `session/load` on
v1) — engine.rs:976-978; acp-host harness.rs:392-427." Since the wire-method mapping is now
verified against sibling source, the map may name the methods, but it should cite the harness
file and add it to `references` so the claim is auditable from this element.

Severity: the reviewers say Major. In my judgment this is a **wording accuracy** fix, not a
functional defect — every seat still receives the correct cwd on both paths. I'd treat it as a
legitimate but lower-impact correction; I do not veto the Major label outright, but I record that
the behavior (cwd delivered) is correct and only the description is narrow.

---

## GF4 — (Nit, codebase-details, missing detail)
> Relative paths resolve against the server cwd (tables.rs:132); the path is published in
> TableOpened (engine.rs:411); nothing prevents tables from sharing one folder.

**Decision: RIGHT (now fully verified); resolves to a DESCRIPTION note (low priority).**

Verified: engine.rs:411 publishes `workspace: workspace.display().to_string()` in `TableOpened`,
so the effective path is indeed published. `config.rs::validate` (106-132) checks objective,
seats, allowances, rounds, seat-name uniqueness — it does **no** workspace uniqueness or
per-table check, so "nothing prevents tables from sharing one folder" is confirmed by absence
(two `TableConfig`s can carry the same `workspace: PathBuf`; engine.rs:402 `create_dir_all` is
idempotent and would not object). The `tables.rs:132` claim was verified against the sibling
element `code.roster.participant/source/crates/roundtable-web/src/tables.rs:132`:
```rust
let workspace = if request.workspace.is_absolute() { request.workspace }
                else { std::env::current_dir()?.join(request.workspace) };
```
So a relative `workspace` resolves against the server's current directory — the finding is
accurate, not unverifiable. Status is "verified against sibling source" (see Cross-cutting #2).
It is still a host/config-resolution fact, not an engine property, which is why it stays a Nit.

Why it is only a Nit, and partly right: "the path is published in TableOpened" is true but is
already consistent with `elephant.built` and not a contradiction. "Nothing prevents tables from
sharing one folder" is a genuine missing-detail but it is a **host-level** concern (how table
ids map to folders), not a property of the shared-workspace element itself; the engine takes
whatever `cfg.workspace` it is given.

What to change (description, optional): add one line under `investigations` or `elephant`:
"The engine does not allocate or isolate workspace folders; it uses `cfg.workspace` verbatim
(canonicalized at start) and publishes it in `TableOpened`. A relative `workspace` in the host
request is resolved against the server's cwd (`tables.rs:132`); folder isolation is the host's
responsibility; two tables can be pointed at the same folder." Cite the host file in
`references` — the claim is now verified against sibling source, so it should be recorded rather
than withheld.

---

## GF5 — (Nit, codebase-details, properties.uri)
> The uri is a README anchor; the implementing code (config.rs:142-146; engine.rs:401-440,
> 949-997) is never named.

**Decision: RIGHT; resolves to a DESCRIPTION change.**

Verified: `element.md:11` `"uri": "README.md#2-participants-and-shared-workspace"` is a README
anchor. The `properties` block and `references` layer name only README.md sections. No `.rs`
file is referenced anywhere in the element. The implementing code is in the cited ranges:
config.rs:142-146 (workspace/scope fields), engine.rs:401-440 (`Table::start`: create, canonicalize,
ScopePolicy, TableOpened, seat spawn), engine.rs:949-997 (`start_seat`: launch, open/resume
session, tools, settings, routing warning).

Why right: a functional map whose `uri` points only to prose cannot be traced to the behavior
it describes. GF5 is a small but valid auditability gap, and it is the direct cause of GF7 (see
below): because no code is named, the map cannot answer who creates the folder or how the path
is chosen.

What to change (description): add the implementing files to `references` (or a `code` layer),
e.g. `crates/roundtable/src/config.rs` and `crates/roundtable/src/engine.rs`, with the relevant
symbols. Keep the README `uri` for the prose; the two point at different kinds of source and do
not conflict.

---

## GF6 — (Nit, codebase-details, gaps)
> Not stated: tool activity sets worked_in_topic, which affects table ending and idle-topic
> warnings (engine.rs:368-372, 647, 672; turn.rs:399-407). The concurrent-edits gap from
> investigations is still open but missing from the elephant gaps.

**Decision: SPLIT — the `worked_in_topic`→table-ending half is RIGHT; the "idle-topic warnings"
half is RIGHT (verified from sibling `turn.rs`); the missing-gaps half is RIGHT. Resolves to
DESCRIPTION changes.**

Verified line by line:
- engine.rs:672 `self.worked_in_topic = true;` is set inside `on_tool` when `Activity::Floor`
  receives `ToolActivity` — i.e. ACP tool activity during a floor turn.
- engine.rs:368-372 `topic_had_input()` returns `self.worked_in_topic || <accepted Message with
  this topic's prefix>`.
- engine.rs:647 uses `topic_had_input()` to decide whether a no-round-limit table ends after
  two quiet rounds (`!self.topic_had_input()` → `start_rating()`).
So the claim "tool activity sets worked_in_topic, which affects table ending" is **correct and
verified**, and it is genuinely relevant to this element: it is the mechanism by which *file
work in the shared workspace counts as input* and keeps a table alive. That is exactly knowledge
the map should hold and currently does not.

- **`idle_topics` / idle-topic warnings**: `turn.rs` is not copied into this element's `source/`,
  so the prior version of this resolution called the flag dead state. **That inference was wrong.**
  `turn.rs` exists in the sibling element `code.gate.quality/source/crates/roundtable/src/turn.rs`
  (`:399-407`), and `change_topic` there reads and writes `idle_topics`:
  ```rust
  if accepted || self.worked_in_topic { self.idle_topics = 0; }
  else { self.idle_topics += 1; if self.idle_topics == 2 {
         self.notice("warn", "Two topics in a row ended with nothing accepted and no work..."); } }
  ```
  So the idle-topic warning **is** substantiated: it fires at two consecutive topics with no
  accepted message and no `worked_in_topic`, and it is governed by the same flag GF6's first half
  concerns. This half of GF6 is therefore RIGHT and should be recorded, not dropped. (The warning
  is gated on `topics_active()`, so it only applies when topics are on.)

- **Missing gap**: `investigations` (element.md:34-39) records the concurrent-edits gap;
  `elephant.gaps` (element.md:52-55) lists only "Files are not checked by JEV...". So the open
  gap is indeed not carried into `gaps`. Confirmed.

What to change (description):
- Add to `elephant.gaps` (or a knowledge note): "Tool (file) activity during a turn sets
  `worked_in_topic` (engine.rs:672); with no round limit this counts as topic input
  (`topic_had_input`, engine.rs:368-372) and can postpone the table ending (engine.rs:647)."
- Note the idle-topic warning: two topics in a row with no accepted message and no file work
  raise a warning (`turn.rs:399-407`) — verified from the sibling copy.
- Carry the concurrent-edits item from `investigations` into `elephant.gaps` so the open gap is
  not lost. Note that the copied code contains **no** locking/coordination mechanism (search for
  `lock`/`flock`/`conflict` finds only the unrelated `Mutex<Vec<Harness>>`), which confirms the
  investigations note is still accurate.

---

## GF7 — (Major, comprehension, Properties.uri, elephant.built)
> The document doesn't say who creates the table's workspace folder, how its path is chosen, or
> whether it is new or existing; the uri points only to a README section.

**Decision: RIGHT; resolves to a DESCRIPTION change. This is the highest-value comprehension fix.**

Verified: the element never states any of those three facts. The README `uri` (element.md:11)
cannot supply them. Meanwhile the answer **is** fully derivable from the copied code:
- **Who creates it:** `Table::start` (engine.rs:401-402) calls
  `std::fs::create_dir_all(&self.cfg.workspace)` — the engine creates it, best-effort, before
  any seat launches.
- **How the path is chosen:** it comes from `TableConfig.workspace` (config.rs:143), is
  canonicalized (engine.rs:403, fallback to the raw path on failure), assigned back to
  `cfg.workspace`, and published as `TableOpened.workspace` (engine.rs:411). `cfg.scope`
  (config.rs:146) is independent.
- **New or existing:** `create_dir_all` is idempotent — it creates the folder if absent and is a
  no-op if it already exists. So both; the map should say "created if missing, otherwise reused".

Why Major: this is the core "what the part does" knowledge for a *shared workspace* element, and
its absence is what makes `elephant.built` unfalsifiable. It also subsumes GF4's "path published"
and GF5's "code not named" points.

What to change (description): replace the single sentence in `elephant.built` with the three
facts above and add the implementing files to `references` (see GF5). Suggested wording:
"The engine creates `cfg.workspace` at table start with `create_dir_all` (so a pre-existing
folder is reused), canonicalizes it, and publishes the effective path in `TableOpened`. Every
seat's session opens with that path as cwd (engine.rs:401-440, 976-978)."

---

## GF8 — (Major, comprehension, elephant.sources)
> The convention 'extra detail goes in files named with the agent's name' is not explained: what
> extra detail is, and what rule it relieves. The owner's evaluation specification is not defined
> or linked.

**Decision: RIGHT (with a useful correction from the copied source); resolves to a DESCRIPTION
change.**

Verified: `element.md:49` cites `"owner's evaluation specification: extra detail goes in files
named with the agent's name"` as a source, but the element never explains it or links the spec.
Confirmed gap.

Correction/addition the reviewers missed: the convention is **actually present in the copied
source**, in `resources/roundtable_prompt.md:10`:
> "If you have sample code, diagrams, or additional details, write them to a file on disk whose
> filename includes your agent name, within `{{artifact_directory}}`. In your reply, explain the
> substantive point and what the artifact establishes. A file reference alone does not make the
> reasoning visible in the discussion."

That text answers both of the reviewers' questions:
- **What "extra detail" is:** sample code, diagrams, additional details that are too large or too
  incidental for the chat message.
- **What rule it relieves:** no evaluation exemption is established. Supporting material goes
  in files, but the prompt still requires the reply to explain the substantive point and what
  its artifact establishes. File placement does not make a bare-link reply sufficient or waive
  evaluation thresholds. The existing owner acceptance establishes that file contents are
  unjudged, not that the reply's reasoning requirements are relaxed.

What to change (description): in `elephant.sources`, replace the bare phrase with a real pointer
to `resources/roundtable_prompt.md:10` (and add that file to `references`), plus one sentence
explaining the convention: bulk/detail goes to an agent-named file in the shared folder; the chat
message keeps a short substantive explanation so the evaluator still has something to judge.
Define "owner's evaluation specification" as that prompt/thresholds, or link it; do not leave it
as an undefined proper noun.

This also gives GF11 its answer (see below).

---

## GF9 — (Major, comprehension, want from code.manager.chat.group)
> Intent is receive, but the document doesn't say what the manager receives from the workspace or
> how; 'chair' is undefined.

**Decision: RIGHT; resolves to a DESCRIPTION change.**

Verified: `element.md:17` reads
`goal: Produce the chair's deliverable, not a discussion summary. Function: Holds the artifacts
the participants create and refine independently or together. Intent: receive`.
The "Function" describes what the *workspace* does (holds artifacts), not what the *manager
receives*. There is no statement of payload or mechanism, and `chair` appears nowhere else in the
element. In the copied code, "chair" appears only in engine.rs comments/commands
(`:32, :37, :221, :861-862, :900-905`: `Command::Guidance` "Chair guidance", `Command::End`
"the chair ends the table", `ChairSpoke`) — so the engine has a chair concept but the map never
defines it. Confirmed comprehension gap.

What to change (description):
- Define `chair` once (the operator/host role that issues `Command::{Guidance, End, Advance}`,
  engine.rs:34-46, and whose deliverable is the objective's result).
- State what the manager **receives** and **how**: the concrete artifacts in the shared folder
  (the files agents write, per GF8), read from the same `cfg.workspace` directory — not a chat
  transcript. "Intent: receive" should name the received thing: "the produced files/artifacts,
  read from the workspace folder".
- Keep it honest: the copied code does not show a manager component consuming those files
  (`code.manager.chat.group` is not in `source/`), so describe the *contract* (what is received)
  rather than inventing a delivery mechanism. If the maintainers want a mechanism, add the
  manager source to `references`.

---

## GF10 — (Nit, comprehension, investigations)
> 'Roundtable 7 proposals' is undefined, and current behaviour under conflicting edits is not stated.

**Decision: RIGHT; resolves to a DESCRIPTION change.**

Verified: `element.md:37` says "Roundtable 7 proposals discussed conflicting edits as a topic."
There is no definition of "Roundtable 7 proposals", no link, and no file in `source/` for it.
The note also does not say what happens *today* when two agents edit the same file.

Useful addition from the evidence: the copied code contains **no** edit-coordination, file
locking, or conflict detection (verified by searching engine.rs/config.rs; the only `Mutex` is
the unrelated `live` harness list). So the current behavior can be stated plainly and
accurately: **no Roundtable-level coordination is shown** — the spec names no mechanism and the engine
adds none. That is a stronger, more useful statement than the vague "Open gap for the build".

What to change (description): rewrite the `investigations` note to (a) drop or footnote
"Roundtable 7 proposals" (or link the artifact if it exists — it is not in the copied source),
and (b) state the observed behavior: "The engine provides no locking or conflict detection;
concurrent writes to the same path are uncoordinated at this layer. Results depend on whether
tools append, overwrite in place, or replace files atomically; no universal last-writer-wins
rule follows. No coordination mechanism is established by the supplied code." This also makes GF6's "carry the gap into
`elephant.gaps`" concrete.

---

## GF11 — (Nit, comprehension, elephant.gaps with elephant.sources)
> Files are unjudged and agents are told to put detail in files; the document doesn't say whether
> this bypass of the evaluator is intended.

**Decision: PARTLY RIGHT; mostly already covered — resolves to a small DESCRIPTION clarification,
not a new finding of substance.**

Verified: `elephant.gaps` (element.md:53) **already states** "Files are not checked by JEV; the
owner accepted that on 2026-11-07." So the "files are unjudged" half is not missing — the
reviewers' own premise is already in the document. What is genuinely missing is the *link* between
the two facts: that the file convention of `elephant.sources` (GF8) is the deliberate channel that
carries detail around the evaluator, and that the owner's acceptance covers exactly that. The
word "bypass" is the reviewers' framing; the map should say whether it is intentional.

From `roundtable_prompt.md:10` (GF8) the design is in fact coherent and intentional: bulk detail
goes to a file (unjudged), while the chat message must still "explain the substantive point and
what the artifact establishes" — so the evaluated prose is preserved and the artifact is an
appendix, not an evasion. That answers "whether the bypass is intended": **yes, intentional, and
bounded** — the judged message still carries the reasoning.

What to change (description): add one sentence to `elephant.gaps` connecting the pieces:
"Agents are instructed (`resources/roundtable_prompt.md:10`) to put bulk detail in an
agent-named file in this folder; those files are deliberately outside JEV (accepted by the owner,
2026-11-07). The evaluated chat message must still state the substantive point, so this is an
intentional, bounded split between the judged summary and its unjudged appendix — not an
unchecked path for the contribution itself."

Severity: keep as Nit. It is a clarification of two facts already present, not a new gap.

---

## GF12 — (Nit, comprehension, wants, Properties)
> ACP, session/new, JEV, and the map fields role, name_length and Intent are undefined.

**Decision: RIGHT but LOW-value / partly out of scope; resolves to an optional DESCRIPTION
glossary, and one term should be removed rather than defined.**

Verified: `element.md` uses `ACP` (via "session/new"), `JEV` (elephant.gaps:53), `role: "SE"`,
`name_length: 2`, and `Intent: send/receive` without defining them. The intro (element.md:3)
explains the "functional map" but not these labels. `roundtable_prompt.md:8` uses "true/false
gate" and "0–5 scores" (the evaluation/JEV concept) but that file is not referenced by the
element. Confirmed.

Two judgments that add precision:
- **`session/new` should be removed, not defined.** GF3 already shows the want's `session/new`
  wording is inaccurate (resumed seats use a different path, and the exact ACP method names are
  in an uncopied file). Defining a term we then have to correct is wasted work; apply GF3's
  reword first. "ACP" itself can get a one-line gloss ("Agent Client Protocol, the harness
  session interface") pointing at `acp-host`.
- **`role`, `name_length`, `Intent` are map-meta conventions**, not properties of this element.
  `name_length: 2` is verifiably just the token count of `"shared workspace"`. `role: "SE"` and
  `Intent` are map schema fields. They belong in a **map-level glossary** (one shared definition
  for every element), not repeated/defined inside this single element's `Properties`. Defining
  them here would be inconsistent with the rest of the map.

What to change (description, optional): add a short "Terms" line or rely on the map-level
glossary: define ACP and JEV once (JEV = the evaluator that judges each message, per
`roundtable_prompt.md:8` and engine.rs:25 `use crate::jev::Jev`). Leave `role`/`name_length`/
`Intent` to the map schema. Do not expand this into a per-element definitions section.

---

## Summary table

| Finding | Decision | Change in | Verified? |
|---|---|---|---|
| GF1 | Right (partly, edge case) | **Code** (loud failure) + description note | Yes, engine.rs:402-404, 12 |
| GF2 | Right | Description (`elephant.built`/gap) | Yes, engine.rs:405-406,992-995; config.rs:144-146,189-218 |
| GF3 | Partly right (wording) | Description (reword want) | Substance yes; ACP method names verified from sibling harness.rs:392-427 |
| GF4 | Right (verified from sibling) | Description (optional note) | engine.rs:411, config.rs:106-132 yes; tables.rs:132 verified from sibling (relative path resolves against current_dir) |
| GF5 | Right | Description (`references`) | Yes |
| GF6 | Split: ending-half right, idle-topic-half right (verified), gap-half right | Description (gap + note + warning) | Yes; turn.rs:399-407 verified from sibling (idle_topics reset/increment/warn at 2) |
| GF7 | Right (highest value) | Description (`elephant.built` + `references`) | Yes, engine.rs:401-411, config.rs:143 |
| GF8 | Right (+ new evidence) | Description (`elephant.sources` + `references`) | Yes, roundtable_prompt.md:10 |
| GF9 | Right | Description (define chair; name the receive payload) | Yes; manager source absent |
| GF10 | Right | Description (rewrite investigations note) | Yes (no coordination in code) |
| GF11 | Partly right (already stated) | Description (one clarifying sentence) | Yes, gaps:53 + prompt:10 |
| GF12 | Right, low value / out of scope | Optional glossary (map-level); remove `session/new` per GF3 | Yes (meta-terms) |

## Cross-cutting recommendations

1. **Name the code (GF5 + GF7).** Adding `crates/roundtable/src/config.rs` and
   `crates/roundtable/src/engine.rs` to `references` is the single change that resolves or
   strengthens GF1, GF2, GF3, GF4, GF5, GF6, and GF7 at once, because every one of those
   findings is "the map doesn't record what the code does".
 2. **Add the copied files that are cited but missing.** `tables.rs`, `turn.rs`,
    `acp-host harness.rs`, and README.md should be added to `source/`/`references` so the map's
    provenance claim rests on this folder's own copy. In the meantime the three claims that
    previous revisions flagged as unverifiable were **verified against sibling elements of the
    same repo**: GF3's ACP method mapping (`code.client.agent/source/crates/acp-host/src/harness.rs:392-427`),
    GF4's relative-path resolution (`code.roster.participant/source/crates/roundtable-web/src/tables.rs:132`),
    and GF6's idle-topic warning (`code.gate.quality/source/crates/roundtable/src/turn.rs:399-407`).
    They are corroborated, not merely asserted — but the provenance label should stay "verified
    against sibling source", not "verified in this element's source", until the files are copied here.
3. **Separate code fixes from doc fixes.** Only GF1 warrants a code change (it violates the
   engine's own "Failures are loud (O)" principle and can leave ScopePolicy pointing at a
   non-existent path). All other valid findings are documentation gaps in a functional-map
   artifact; fixing them in code would be solving the wrong problem.
4. **Resolve GF3 before GF12.** Rewording the `session/new` want makes GF12's request to
   "define session/new" moot.


## DenseEscort: final decision refinements

- **GF1:** stop table startup on workspace creation/canonicalization failure before publishing
  `TableOpened` or launching seats. Keep the asynchronous API and report a path-specific error
  followed by a table-ended event. Acceptance check: an existing regular file used as the
  workspace must produce those errors with no participant launch; an existing valid directory
  containing an artifact must start without clearing the artifact.
- **GF8/GF11:** owner acceptance already answers the literal intent question. Uphold only the
  clarification linking unjudged supporting files to the file convention. The corrected
  description must also retain the prompt's requirement that the evaluated reply explain the
  contribution. Do not characterize file placement as relief from evaluation requirements.
- **GF12:** use a link to authoritative map-wide definitions rather than repeat them locally.
  The existence of shared vocabulary alone does not establish that readers can discover its
  meaning; an existing accessible glossary would resolve this documentation concern.

Further operational reasoning and observable checks: [DenseEscort final decisions](DenseEscort-final-decisions.md).
