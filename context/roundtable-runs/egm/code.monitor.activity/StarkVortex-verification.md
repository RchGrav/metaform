# StarkVortex — verification of GF1–GF10 against the supplied code

Scope note (important for the group): the `source/` folder in this run contains exactly two
files: `crates/agent-monitor/src/lib.rs` and `crates/agent-monitor/src/capture.rs`. Findings
that cite `crates/roundtable/src/engine.rs`, `crates/roundtable-web/assets/index.html`,
`crates/agent-monitor/Cargo.toml`, `README.md`, `Roundtable_ACP_Integration_Design.md`,
`archaeology/...` or `topogee DECISIONS.md` are citing files that are **not** in this folder.
Everything below that is asserted about `lib.rs` / `capture.rs` I checked line by line; every
such assertion in GF1–GF5 turned out to be accurate. Claims about the absent files are
reported as "unverifiable here" rather than confirmed.

## Verified facts used in the decisions

- `lib.rs:9-10` — "The monitor is an observer only. Nothing here judges, times out, or stops an
  agent; silence is published as nothing, never as failure." (GF1)
- `lib.rs:72-77` — `Harness { pid: u32, id: Option<String> }`. No ACP session id, no list of
  session ids. (GF2)
- `lib.rs:19-20, 141-142` — every `Observation` is tagged with `harness` (pid + optional id),
  i.e. correlation is by harness id, not by an ACP session. (GF2, GF10)
- `lib.rs:33-39; capture.rs:103-115` — TLS probe is `-p <harness pid>` only, optionally pinned to
  one executable; descendants' TLS is explicitly not captured. (GF3)
- `lib.rs:41-45; capture.rs:265-281` — published HTTP fields are method, host, path, status,
  exchange id; AgentSight's "LLM" classifier is private, so requests are **not** labelled model
  calls. (GF3)
- `lib.rs:28-39; capture.rs:60-64, 90-98` — process capture is required (failure → `Err`), TLS
  failure only publishes `MonitorUnavailable` and `attach` still returns `Ok`. (GF4.1)
- `capture.rs:66-81, 212-215` — `attach` loops until a `CLOCK_SYNC`/`phase=start` record before
  publishing `MonitorAttached` and returning. (GF4.2)
- `lib.rs:30-31` — file-change/write/network records are aggregated and flushed every five
  seconds and at process exit (documented in the crate's module doc, absent from element.md). (GF4.3)
- `capture.rs:136-147` — when a probe's stream ends, `pump` publishes `MonitorUnavailable` with
  `capture: Some(..)`. (GF4.4)
- `lib.rs:23-24; capture.rs:23-35` — dropping `Monitor`/`Running` aborts the pump tasks; nothing
  is published for a host-requested stop. (GF4.5)
- `lib.rs:102-104, 117-119, 153-155` — the three bus event names are `monitor.attached`,
  `monitor.unavailable`, `monitor.observation`; none appear in element.md. (GF4)
- `capture.rs:179-210` — without euid 0, AgentSight would re-launch probes through `sudo -n`,
  which the crate refuses; CAP_BPF/CAP_PERFMON/CAP_SYS_ADMIN without root are explicitly not
  enough (test at `capture.rs:495-510`). (GF5)
- `capture.rs:169-171` — non-Linux is refused outright. (GF5)
- `lib.rs:55-58` — `agentsight` feature is on by default; without it `attach` reports
  `MonitorUnavailable`; probes need `libelf`, `libz`, `libzstd` at run time. (GF5; Cargo.toml
  itself is absent, but `lib.rs:55` independently states default-on.)
- `lib.rs:110-119, 421-429 of capture.rs` — `MonitorUnavailable` means *monitoring* is
  unavailable and "says nothing about the agent itself" (`lib.rs:109`); `HttpResponse.status`
  (e.g. 401 in the test) is a raw HTTP status, not a derived "provider call failed" state. (GF7)
- `lib.rs:143-145, 165; capture.rs:295-301, 473-477` — when the probe cannot attribute a record
  to a process, `Observation.pid` is `None`; `EventsLost`/`Other` carry `pid: None`. The record
  is still always tagged with the `Harness`. (GF10)

## Two findings that strengthen the reviewers' case

1. **GF6 undercounts the vocabularies.** There are at least **four**, not three. The crate's own
   module doc at `lib.rs:3-7` says a silent harness "can be told apart as **working, waiting on
   the network, exited, or alive with no observable activity**". So the full set is:
   - want `code.manager.chat.group` (element.md:17): working / waiting / gone / unknown
   - decision (element.md:83): working / waiting / unavailable / exited / unknown
   - investigation "run 1 availability" (element.md:57-58): responsive / occupied / unavailable
   - `lib.rs:6-7`: working / waiting on the network / exited / alive with no observable activity
   "gone" vs "exited" vs "alive with no observable activity" are three different labels for
   overlapping ideas; "unavailable" is used for both an agent state and a monitor state.

2. **The description's "ACP session id" mental model is simply wrong**, and it is the common
   root of GF2, GF7 and GF10. The code never sees an ACP session id, never holds several of
   them, and never correlates an observation to a session. It correlates to a harness process
   tree via `pid` + one optional name string. Rule 2 (element.md:49) therefore warns about a
   distinction ("cannot always be attributed to one ACP session") that the code does not make:
   observations are *always* attributed to a harness, and *never* to an ACP session.

## Cross-cutting diagnosis (useful when deciding the fixes)

- **Cluster A (GF1, GF6, GF7, GF8):** the `decisions` layer's five-state model is a *consumer*
  contract. The want from `code.manager.chat.group` (element.md:17) says that part is the one
  that "shows whether a silent participant is working, waiting, gone or unknown", while this
  element only "provides independent activity observations correlated to each participant".
  Nothing in `agent-monitor` derives states, and the elephant `gaps` (element.md:98-101) do not
  record state derivation as unbuilt. The cleanest fix is to scope/move the decision rather than
  to add state-derivation code to an observer-only crate (which would break rule 1, `lib.rs:9-10`).
- **Cluster B (GF2, GF3, GF7, GF10):** replace the "ACP session ids / model-provider activity"
  vocabulary with the code's actual model: harness pid, optional harness id, process-tree
  observations, and HTTP requests/responses on the harness process's own TLS connections.

## Per-finding verdict summary

| Finding | Verdict | Note |
|---|---|---|
| GF1 | Right | Blocker; lib.rs:9-10 confirmed; engine.rs/index.html citations unverifiable here |
| GF2 | Right | lib.rs:72-77 confirmed; engine.rs citations unverifiable here |
| GF3 | Right | Fully verifiable in the two supplied files; both claims confirmed |
| GF4 | Right | All five sub-points confirmed; "undocumented" means absent from element.md, not from lib.rs doc comments |
| GF5 | Right | All four facts confirmed in lib.rs/capture.rs; Cargo.toml absent but lib.rs:55 covers default-on |
| GF6 | Right | Actually four vocabularies, not three (see above) |
| GF7 | Right in substance | Collision confirmed; "no source" slightly overstated — raw HTTP status exists, but is neither classified nor derived |
| GF8 | Right in substance, reasoning corrected | Comprehension gap is real; the cited "fail-open decision" is not in element.md, and the elephant sentence is literally accurate about the AgentSight crate; fix is scoping, not contradiction-recording |
| GF9 | Right | All six terms present and undefined in element.md; HoldOn is load-bearing for the root gap |
| GF10 | Right | Code's actual answer is `Observation.pid = None` plus a `Harness` tag; "several session ids" is unsupported |
