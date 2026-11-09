# Map element `code.monitor.activity`: agent activity monitoring

This document is one element of the functional map of Roundtable, a program in which several AI agents discuss a user's objective in turns while an evaluator checks each message. The map records what each part of the program must do, what it relies on, and knowledge about it. Paths are relative to the Roundtable folder.

## Properties
```json
{
  "package": "agent host library (reusable; basis for the chassis)",
  "name": "agent activity monitoring",
  "name_length": 2,
  "role": "SE",
  "uri": "README.md#10-asynchronous-agent-operation-and-activity-monitoring"
}
```

## What other parts rely on it for (their wants)
- `code.manager.chat.group`: goal: Show whether a silent participant is working, waiting, gone or unknown. Function: Provides independent activity observations correlated to each participant. Intent: receive

## What it relies on (its wants)
- `code.bus.event`: goal: Make activity observations available to subscribers as they happen. Function: Carries observation events to subscribers. Intent: send
- `code.client.agent`: goal: Relate observations to the right participant. Function: Provides the launched harness process id and its ACP session ids. Intent: receive
- `upstream.tracer.agent`: goal: See what a participant's harness is doing when ACP reports nothing. Function: Captures process, subprocess, file, network and observable model-provider activity through agentsight-capture. Intent: receive

## Layer `references`
```json
[
  {
    "path": "README.md",
    "sections": [
      "10.2",
      "10.3",
      "10.4"
    ]
  },
  {
    "path": "Roundtable_ACP_Integration_Design.md",
    "sections": [
      "8 AgentSight",
      "Correlation with ACP sessions"
    ]
  }
]
```

## Layer `rules`
```json
[
  "Observer only. Silence or long work is never a reason to abort a participant.",
  "Process-level observations cannot always be attributed to one ACP session; do not pretend otherwise."
]
```

## Layer `investigations`
```json
[
  {
    "topic": "run 1 availability",
    "note": "Run 1 kept scheduling seats after 68 HTTP 402 credit failures, 44 empty replies and 3 rate limits; seat 'gone' stayed null. Responsive, occupied and unavailable are different states. Source: run 1 audit P04-P06, D03."
  },
  {
    "topic": "privileges",
    "note": "Built on agentsight-capture; observes nothing unless Roundtable runs as root. The owner's design is a root service under HoldOn (topogee DECISIONS.md)."
  }
]
```

## Layer `archaeology`
```json
[
  {
    "finding": "Python marked seats degraded after 2 consecutive failures and unavailable after 4, then probed with doubling waits up to an hour. Not in the spec; not carried over as an automatic action.",
    "path": "archaeology/src/metaform/modules/roundtables/roundtable/health.py:1-14; config.py:41-43"
  }
]
```

## Layer `decisions`
```json
[
  {
    "by": "Claude",
    "date": "2026-11-05",
    "decision": "Each participant shows one of: working (ACP activity or observed activity), waiting (in flight, no observed activity), unavailable (last provider call failed, with the error), exited (process gone), unknown. These are information for the chair and the record, never triggers to cancel or unseat."
  }
]
```

## Layer `elephant` (the project author's account of this element)
```json
{
  "date": "2026-11-07",
  "design": "Observe what each agent's process actually does, independently of what ACP reports, so silence can be told apart from work.",
  "sources": [
    "README.md §10.2-10.3",
    "Roundtable_ACP_Integration_Design.md §8"
  ],
  "built": "crates/agent-monitor attaches AgentSight's probes to each agent's process.",
  "gaps": [
    "It observes nothing unless Roundtable runs as root.",
    "The owner's design, a root service run under HoldOn, is not built."
  ]
}
```

## The review findings to resolve

Two reviewers who had never seen this project read the description above and the code. Their findings follow. Severity: Blocker means the description says something the code does not do; Major means an important gap; Nit means a small one.

- **GF1** (Blocker, egm-codebase-details, decisions): The decision says each participant shows one of working / waiting / unavailable (with the provider error) / exited / unknown. Nothing derives these states. agent-monitor deliberately judges nothing (crates/agent-monitor/src/lib.rs:9-10). The engine only turns MonitorUnavailable into an 'error' notice (crates/roundtable/src/engine.rs:481-486), and the web UI shows the last raw observation (crates/roundtable-web/assets/index.html:259). Provider-call failure is not something the monitor observes, and the elephant gaps do not record any of this as unbuilt.
- **GF2** (Major, egm-codebase-details, wants: code.client.agent): The document says the monitor receives 'its ACP session ids'. Harness holds only pid and an optional harness id string (crates/agent-monitor/src/lib.rs:72-77). The engine passes the HarnessStarted pid and harness id, never a session id (crates/roundtable/src/engine.rs:796-802). Observations are tied to a seat through the harness id (engine.rs:484, 490-493).
- **GF3** (Major, egm-codebase-details, wants: upstream.tracer.agent): 'Observable model-provider activity' overstates what is captured. TLS capture covers only the harness pid, not its children, and requests are never classified as model calls; only method, host, path, status and exchange id are published (crates/agent-monitor/src/lib.rs:33-45; crates/agent-monitor/src/capture.rs:103-125).
- **GF4** (Major, egm-codebase-details, whole document): Undocumented behaviour: (1) attach fails if process capture cannot start, but TLS capture may fail on its own (lib.rs:28-39). (2) attach waits for the probe's CLOCK_SYNC start record before returning (capture.rs:66-81). (3) File-change, write and network records are aggregated and flushed every 5 seconds (lib.rs:30-31). (4) A probe that stops publishes monitor.unavailable (capture.rs:136-147). (5) Dropping the Monitor stops the probes without publishing anything (lib.rs:23-24). The bus event names are not listed (lib.rs:102-104, 117-119, 153-155).
- **GF5** (Nit, egm-codebase-details, investigations: privileges): This is correct, but it should add four facts. Capabilities without root are not enough, because AgentSight would fall back to `sudo -n`, which the crate refuses (capture.rs:179-209). It runs on Linux only (capture.rs:170-171). The `agentsight` cargo feature is on by default, and without it nothing is captured (crates/agent-monitor/Cargo.toml:8-12). At run time the probes need libelf, libz and libzstd (lib.rs:55-58).
- **GF6** (Major, egm-comprehension, wants (code.manager.chat.group) / decisions / investigations): Three different state vocabularies: working/waiting/gone/unknown, working/waiting/unavailable/exited/unknown, and responsive/occupied/unavailable. A reader cannot tell which is the contract or whether 'gone' equals 'exited'.
- **GF7** (Major, egm-comprehension, decisions ('unavailable')): 'Unavailable (last provider call failed)' has no stated source of provider errors in the wants (bus, ACP or tracer). The word also collides with the code's 'monitor.unavailable', which means monitoring itself is unavailable.
- **GF8** (Major, egm-comprehension, elephant gaps vs. upstream.tracer.agent decisions): 'Observes nothing unless root' contradicts the depended-on fail-open decision (process exit and ACP traffic still observed), so a reader cannot tell which states work without root.
- **GF9** (Major, egm-comprehension, investigations / elephant): Load-bearing terms and sources are undefined or outside the folder: HoldOn, 'topogee DECISIONS.md', 'run 1 audit P04-P06, D03', seat, chair, chassis. Closing the root gap depends on HoldOn, which is never explained.
- **GF10** (Nit, egm-comprehension, rules): The document says process observations cannot always be attributed to one ACP session, but not what is published when they can't, or why a participant has several session ids.

The code for this part is copied into the `source` folder here, under the same paths as above.
