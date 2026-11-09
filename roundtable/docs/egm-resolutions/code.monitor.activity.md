# Resolution of review findings — `code.monitor.activity` (agent activity monitoring)

Draft contributed by StarkVortex for the roundtable. Each finding gets a decision (right / not
right), the change it requires (in the **description** `element.md` or in the **code**), and the
reason. Where a finding's reasoning needs correction, that is stated explicitly.

## Verification scope

The `source/` folder in this run contains only `crates/agent-monitor/src/lib.rs` and
`crates/agent-monitor/src/capture.rs`. Findings citing `engine.rs`, `index.html`, `Cargo.toml`,
`README.md`, `Roundtable_ACP_Integration_Design.md`, `archaeology/...` or `topogee DECISIONS.md`
refer to files not provided here. All assertions GF1–GF5 make **about `lib.rs`/`capture.rs` were
checked and are accurate**; claims about the absent files are treated as unverifiable here, which
does not change any verdict because each verdict also stands on the description plus the two
supplied files.

A general principle applied below: `lib.rs:9-10` ("The monitor is an observer only. Nothing here
judges, times out, or stops an agent") and rule 1 (element.md:48) are deliberate design choices.
No resolution should make `agent-monitor` derive states, time out, or act on silence.

---

## GF1 — Blocker — decisions (states are not derived)

**Right.**

`lib.rs:9-10` confirms the crate judges nothing; it publishes `monitor.attached`,
`monitor.observation`, `monitor.unavailable` only (`lib.rs:102-104, 117-119, 153-155`). The
decision at element.md:83 asserts five participant states including "unavailable (last provider
call failed, with the error)". Nothing in `agent-monitor` derives them, provider-call failure is
not something it observes, and the elephant `gaps` (element.md:98-101) list only root/HoldOn —
not the missing state derivation. The engine/UI citations (engine.rs:481-486, index.html:259)
are unverifiable here, but the blocker stands without them.

**Change (description).** Do **not** add state derivation to the crate. Either:
1. Move the five-state decision to the consumer `code.manager.chat.group`, whose want
   (element.md:17) is the part that actually "shows" participant state, and replace it here with
   a statement of what this element emits (raw observations + attached/unavailable notices); or
2. Keep it here but add to `elephant.gaps` an explicit "unbuilt" entry: no component derives
   working/waiting/unavailable/exited/unknown; the monitor supplies observations only;
   provider-call failures are not observed by this element.

**Why.** The description currently presents a contract as decided while `built`/`gaps` imply only
the probe-attachment crate exists. A reader cannot tell the state model is unimplemented. Fixing
the description (not the observer-only code) preserves rule 1 and the crate's stated purpose.

---

## GF2 — Major — want `code.client.agent` ("ACP session ids")

**Right.**

`Harness` is `{ pid: u32, id: Option<String> }` (`lib.rs:72-77`); `lib.rs:19-20` says observations
are tagged with "the harness's pid and the optional harness id the host chose". There is no ACP
session id and no collection of session ids. The engine citations (796-802, 484, 490-493) are
unverifiable here, but the description is wrong regardless of them.

**Change (description).** Rewrite the want's Function to: "Provides the launched harness process
id and an optional harness-name/id string chosen by the host; observations are correlated to a
seat through that harness id, not through an ACP session id." Remove "its ACP session ids" and
the plural. Correspondingly amend rule 2 and GF10 (below).

**Why.** The want promises an identifier the code never receives; anyone implementing against the
description would look for a session-id correlation mechanism that does not exist.

---

## GF3 — Major — want `upstream.tracer.agent` ("observable model-provider activity")

**Right.** Fully confirmed in the supplied files: TLS is `sslsniff` on the harness pid alone
(`lib.rs:33-39`, `capture.rs:103-115` — `-p <pid>`, descendants explicitly excluded), and
requests are never classified as model calls (`lib.rs:41-45`); only method, host, path, status
and exchange id are published (`capture.rs:265-281`).

**Change (description).** Replace "Captures process, subprocess, file, network and observable
model-provider activity" with: "Captures process-tree exec/exit, file, write and network
operations, plus HTTP requests and responses on the harness process's **own** TLS connections;
provider endpoints are identifiable from host/path and HTTP status, but requests are not
classified as model calls and descendants' TLS is not captured."

**Why.** "Model-provider activity" implies both coverage of child processes and semantic
classification of LLM calls. Neither is true; overstating it would mislead the dependent part
(GF7's "unavailable" state relies on exactly this overstatement).

---

## GF4 — Major — whole document (undocumented behaviour + event names)

**Right.** All five sub-points confirmed:
1. Process capture required / TLS fail-open (`lib.rs:28-39`; `capture.rs:60-64` → `Err`,
   `capture.rs:90-98` → publish unavailable, return `Ok`).
2. `attach` waits for `CLOCK_SYNC`/`phase=start` before returning (`capture.rs:66-81, 212-215`).
3. File-change/write/network aggregation flushed every 5s (`lib.rs:30-31`).
4. A probe that stops publishes `monitor.unavailable` (`capture.rs:136-147`).
5. Dropping `Monitor` stops probes silently (`lib.rs:23-24`; `capture.rs:23-35`).
The three event names `monitor.attached`, `monitor.unavailable`, `monitor.observation`
(`lib.rs:102-104, 117-119, 153-155`) are absent from element.md.

**Correction to the finding's wording:** these behaviours *are* documented in `lib.rs`'s module
doc comments (lines 14-58). "Undocumented" is correct only with respect to `element.md`, which
is what the finding is about.

**Change (description).** Add an "Interface / behaviour" section to element.md recording: the
three bus event names; process-required vs TLS-fail-open; the `CLOCK_SYNC` attach barrier (so a
caller knows `attach` blocks until probes are live); the 5s aggregation flush (so a consumer does
not expect per-event timing); probe-stop → `monitor.unavailable`; host-requested stop → silent.
Alternatively add `lib.rs:14-58` to the `references` layer as the normative behavioural source
instead of duplicating it.

**Why.** These are load-bearing semantics for anyone consuming the events or calling `attach`,
and the event names are the actual contract with `code.bus.event` (element.md:20).

---

## GF5 — Nit — investigations: privileges (four missing facts)

**Right.** All four confirmed: `sudo -n` fallback refused / capabilities insufficient
(`capture.rs:179-210`, test `495-510`); Linux-only (`capture.rs:169-171`); `agentsight` feature
default-on and nothing captured without it (`lib.rs:55-58`; `Cargo.toml` absent but `lib.rs:55`
independently states default-on); runtime libs `libelf`, `libz`, `libzstd` (`lib.rs:57-58`).

**Change (description).** Extend the privileges investigation note with those four facts,
attributed to `lib.rs:49-58` and `capture.rs:169-210`.

**Why.** "Needs root" alone is misleading: a reader might grant CAP_BPF/CAP_PERFMON, run on
macOS, or build with `--no-default-features` and still expect capture. Each is a distinct reason
capture silently degrades to `monitor.unavailable`.

---

## GF6 — Major — three state vocabularies

**Right, and understated: there are four.** Confirmed in element.md: want
working/waiting/gone/unknown (line 17); decision working/waiting/unavailable/exited/unknown
(line 83); investigation responsive/occupied/unavailable (line 57-58). A fourth is in the code's
own doc comment, `lib.rs:6-7`: "working, waiting on the network, exited, or alive with no
observable activity". "gone", "exited" and "alive with no observable activity" overlap without
being equated; "unavailable" is used for both an agent state and a monitor state.

**Change (description).** Choose one vocabulary as the contract and define each term; either
equate or explicitly distinguish "gone" and "exited"; drop "responsive/occupied" from the
investigation as a state vocabulary (keep it as historical narrative about run 1); align
`lib.rs:6-7`'s informal wording with the chosen terms. State which vocabulary is normative for
`code.manager.chat.group`.

**Why.** Multiple undefined, overlapping vocabularies make it impossible to say what the
dependent part should display, and they feed directly into GF1, GF7 and GF8.

---

## GF7 — Major — decision "unavailable"

**Right in substance; one part of the reasoning needs correction.**

Confirmed: `MonitorUnavailable` (`lib.rs:110-119`) means *monitoring* is unavailable and
"`capture` ... This says nothing about the agent itself" (`lib.rs:109`). The decision's
"unavailable (last provider call failed)" therefore collides with a code event of the same name
that means the opposite kind of thing. And no want states a source of provider errors.

Correction: "no stated source" is slightly overstated — `upstream.tracer.agent`'s want claims
"observable model-provider activity" (GF3 shows this is overclaimed), and `HttpResponse.status`
exists as raw data (`lib.rs:185`; 401 test at `capture.rs:427`). The real problem is that HTTP
requests are not classified as model calls (GF3), no component derives a state from them (GF1),
and the name collides.

**Change (description, convergent with the roundtable).** Do **not** rename the state to
"failed" yet. Keep the name open and mark the row **"no source in this element — requires an
explicit provider-error source (ACP or engine) to be added to the wants before it can be
derived"** (CrypticHammer's refinement, adopted by StarkTornado). Add a note that
`monitor.unavailable` describes the monitor, not the participant.

**Why the rename is wrong (concrete check):** the crate does publish `HttpResponse { status }`
(`lib.rs:185`; 401 test at `capture.rs:427-431`), and a reader could mistake a 401/429 status for
a provider-call *outcome*. But a response status is traffic — the provider answered — not an
outcome of whether the call succeeded from the host's perspective. Wiring "failed" to HTTP status
would repeat GF3's overclaim (inventing a classification the crate does not make). Leaving the
row flagged "no source" keeps GF7's defect visible until a genuine provider-error feed is named.
The naming collision with `monitor.unavailable` is real and must still be documented.

See the state-derivation table below, which makes this the single normative contract.

---

## GF8 — Major — elephant gaps vs. fail-open decision

**Right in substance; the stated cause is not verifiable here and is a mis-framing.**

What is real: "It observes nothing unless Roundtable runs as root" (element.md:99, 100) leaves
"nothing" unscoped, so a reader cannot tell which of the five decision states work without root
— a genuine comprehension gap. What cannot be confirmed: the "depended-on fail-open decision
(process exit and ACP traffic still observed)" is **not** in element.md, and the cited
`upstream.tracer.agent` decisions were not supplied. Literally read, the elephant sentence is
accurate about the thing it describes: `crates/agent-monitor` (the `built` item, element.md:97)
attaches AgentSight probes, and `attach` returns `monitor.unavailable` without root
(`lib.rs:49-53`; `capture.rs:37-42`). ACP traffic and harness-liveness are a separate channel —
element.md:92 says the design observes "independently of what ACP reports" — so there is no
contradiction inside this element, only an unstated boundary.

**Change (description).** Scope the gap: "The **AgentSight-based process-level observations**
produce nothing unless Roundtable runs as root; without root `monitor.unavailable` is published
for the whole monitor. ACP-reported activity and harness process liveness are a separate channel
and are not provided by this element (see `code.client.agent` / `code.manager.chat.group`)."
Then state which decision states remain available without root. Do not record this as an error
in the elephant.

**Why.** Fixes the reader's real problem (which states degrade) without falsely asserting a
contradiction with a decision that is not in this document, and without weakening the accurate
root requirement that GF5 strengthens.

---

## GF9 — Major — undefined load-bearing terms and sources

**Right.** All six appear in element.md and none is defined there: `chassis` (line 8), `chair`
(line 83), `seat` (lines 58, 71), `HoldOn` (lines 62, 100), `topogee DECISIONS.md` (line 62),
`run 1 audit P04-P06, D03` (line 58). The elephant `gaps` make resolution of the root gap depend
on "a root service run under HoldOn" (line 100), so HoldOn is load-bearing yet unexplained.

**Change (description).** Add a short glossary (or a `references` entry with resolvable paths)
for these terms; for the external audit/DECISIONS sources, either give a resolvable path or mark
them as external context not required to understand this element. Most importantly, state what
HoldOn is and how the root service would satisfy the root requirement, or remove the claim that
closing the gap depends on it.

**Why.** A reviewer of this element alone cannot evaluate the privileges gap, the run-1
investigation, or the decision's audience. Undefined external dependencies in a functional map
make the element unauditable.

---

## GF10 — Nit — rules (attribution)

**Right.** Rule 2 (element.md:49) warns that process observations cannot always be attributed to
one ACP session, but the description never says what is published in that case, and the want
(line 22) implies a participant has "several session ids" without explaining why. The code's
actual model answers what is published, but does not explain the host's session lifecycle:
there is no ACP session correlation at all; every `Observation` is
tagged with a `Harness` (`lib.rs:141-142`), and when the probe cannot attribute a record to a
process, `Observation.pid` is `None` (`lib.rs:143-145`, `capture.rs:295-301`; the `EventsLost`
example is at `capture.rs:473-477`). An `Other` record may retain a PID;
its variant alone does not determine process attribution.

**Change (description).** Replace rule 2 / the want with: "Observations are always attributed to
a harness (pid + optional harness id); they are not attributed to an ACP session. When the probe
cannot attribute a record to a specific process, `Observation.pid` is `None` (e.g. lost-event
counts); the harness tag still supports the host's participant correlation." Remove "ACP
session ids" everywhere (GF2) and any implication of several session ids.

**Why.** Gives the consumer the concrete answer the rule currently withholds and removes a
distinction (session-level attribution) the code never makes.

---

## Proposed consumer state model (StarkTornado / CrypticHammer, corrected by HeroicLizard)

The crate is observer-only and publishes three event types: `monitor.attached`,
`monitor.observation`, `monitor.unavailable`. `MonitorUnavailable` "says nothing about the agent
itself" (`lib.rs:109`), so the intended participant display belongs downstream. The following
records necessary evidence, not an implemented or complete state machine. The consumer must
still define freshness, precedence, recovery and request lifecycle handling (GF1, GF6, GF7):

| Decision state | Derivation from published events |
|---|---|
| exited | `Observation` with `Activity::ProcessExit` where `pid == harness.pid` |
| working | Recent positive work evidence from ACP or relevant activity observations; an arbitrary observation is insufficient. `EventsLost`, `ProcessExit`, or a diagnostic `Other` must not automatically imply working. |
| waiting | A known in-flight request, no recent positive work evidence, and sufficient current observation coverage to interpret silence. A historical `MonitorAttached` alone is insufficient. |
| unknown | Evidence is insufficient or stale, including when required capture coverage is lost and no independent ACP/host evidence resolves the state. This can occur after an earlier attachment or observation. |
| unavailable (provider call failed) | **no source in this element — requires an explicit provider-error source (ACP or engine) to be added to wants before it can be derived** |
| capture health (separate) | `MonitorUnavailable` updates confidence/coverage for the specified capture; it must never directly mean participant unavailable or exited. Independent ACP or host evidence can still establish participant state. |

Use 'exited' in place of 'gone' in the current goal. Keep responsive/occupied as historical
audit terminology, not aliases of the display states: they describe different dimensions.
The `pid: None` unattributable case (GF10) stays a property of individual
`Observation`s, not a participant state.

Track health per capture and track host-requested stops: `Drop` is silent and a past attachment
does not prove present coverage (`capture.rs:29-34, 90-98, 136-146`). Process-exit evidence must
refer to the harness PID, not a child. Host lifecycle reporting should also support exit display
when privileged capture is absent; this host behavior is not verified in the supplied source.

**Precedence rule (required for the consumer).** If the consumer receives both an authoritative
harness `ProcessExit` (`pid == harness.pid`) and a later `monitor.unavailable`, the established
exit must not regress to unknown or waiting for the same harness lifetime. Still record capture
health independently. `pump` publishes unavailable whenever its stream ends (`capture.rs:136-147`);
the local code does not establish that every harness exit ends that stream, nor that every stream
end indicates a harness exit. This is a proposed consumer precedence rule, not an implemented
state reducer or a guarantee about upstream probe termination.

**Observable test that the resolution was applied** (CrypticHammer): after the edits, element.md's
decisions/wants/gaps layers must (1) name the three bus events plus the `pid: null` case instead
of asserting five participant states are produced here, and (2) list the state-derivation layer
as an explicit unbuilt gap owned by the consumer.

---

## Summary of decisions

| Finding | Decision | Primary change |
|---|---|---|
| GF1 | Right | Description: scope/move the five-state decision; record derivation as an unbuilt gap |
| GF2 | Right | Description: replace "ACP session ids" with harness pid + optional harness id |
| GF3 | Right | Description: narrow "model-provider activity" to the harness's own TLS HTTP traffic, no classification |
| GF4 | Right | Description: add interface/behaviour section incl. the three event names (or reference lib.rs:14-58) |
| GF5 | Right | Description: add the four privilege facts |
| GF6 | Right (four vocabularies, not three) | Description: one normative, defined vocabulary |
| GF7 | Right (reasoning corrected) | Description: keep state name open, flagged "no source"; note the `monitor.unavailable` collision; do not wire to HTTP status |
| GF8 | Right in substance (cause corrected) | Description: scope "nothing" to AgentSight observations; state which states survive without root |
| GF9 | Right | Description: glossary / resolvable sources, especially HoldOn |
| GF10 | Right | Description: state `pid: None` behaviour; remove session-id language |

**No code changes are required.** Every finding is a defect in `element.md` (or a mis-framing of
it), not in `lib.rs`/`capture.rs`. The crate is internally consistent and well documented; the
description drifted from it. In particular, do not fix GF1 by adding state derivation to an
observer-only crate — that would violate rule 1 and `lib.rs:9-10`.

## Two cross-cutting themes worth applying as a package

- **Cluster A (GF1, GF6, GF7, GF8):** the `decisions` layer is a *consumer* contract misplaced in
  this element. Resolve these four together by scoping the decision to `code.manager.chat.group`
  and stating what this element actually emits.
- **Cluster B (GF2, GF3, GF7, GF10):** the description's "ACP session ids / model-provider
  activity" model does not match the code, which correlates by harness pid + one optional id
  string and publishes process-tree observations plus unclassified HTTP. Resolve these four
  together with one consistent vocabulary.
