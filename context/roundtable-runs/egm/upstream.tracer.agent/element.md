# Map element `upstream.tracer.agent`: AgentSight

This document is one element of the functional map of Roundtable, a program in which several AI agents discuss a user's objective in turns while an evaluator checks each message. The map records what each part of the program must do, what it relies on, and knowledge about it. Paths are relative to the Roundtable folder.

## Properties
```json
{
  "name": "AgentSight",
  "name_length": 2,
  "uri": "https://github.com/eunomia-bpf/agentsight/tree/master/agentsight-capture"
}
```

## What other parts rely on it for (their wants)
- `code.monitor.activity`: goal: See what a participant's harness is doing when ACP reports nothing. Function: Captures process, subprocess, file, network and observable model-provider activity through agentsight-capture. Intent: receive

## Layer `references`
```json
[
  {
    "path": "README.md",
    "sections": [
      "10.2 Independent Activity Monitoring with AgentSight"
    ]
  },
  {
    "path": "Roundtable_ACP_Integration_Design.md",
    "sections": [
      "8 AgentSight"
    ]
  }
]
```

## Layer `investigations`
```json
[
  {
    "topic": "platform check 2026-11-05",
    "note": "The owner's WSL2 kernel 6.18 has CONFIG_BPF_SYSCALL, CONFIG_DEBUG_INFO_BTF (/sys/kernel/btf/vmlinux present), CONFIG_BPF_EVENTS and CONFIG_UPROBE_EVENTS, so eBPF tracing is possible. /sys/kernel/tracing is not readable as the normal user, so capture needs root or CAP_BPF/CAP_PERFMON on the capture binary. agentsight-capture is on crates.io (last updated 2026-10-23), MIT licensed; repo eunomia-bpf/agentsight last pushed 2026-10-31."
  }
]
```

## Layer `decisions`
```json
[
  {
    "by": "Claude",
    "date": "2026-11-05",
    "decision": "Monitoring fails open: without the privileges for eBPF capture, the monitor runs with what it can observe unprivileged (process exit, ACP traffic) and publishes that capture is unavailable. Granting capabilities is a one-time setup step the owner chooses, never something Roundtable does itself."
  }
]
```

## Layer `elephant` (the project author's account of this element)
```json
{
  "date": "2026-11-07",
  "design": "AgentSight observes agent processes with eBPF.",
  "sources": [
    "README.md §10.2"
  ],
  "built": "Used through agentsight-capture by the activity monitor.",
  "gaps": [
    "Needs root."
  ]
}
```

## The review findings to resolve

Two reviewers who had never seen this project read the description above and the code. Their findings follow. Severity: Blocker means the description says something the code does not do; Major means an important gap; Nit means a small one.

- **GF1** (Blocker, egm-codebase-details, decisions): 'Without the privileges ... the monitor runs with what it can observe unprivileged (process exit, ACP traffic) and publishes that capture is unavailable' is false. Without effective root, attach returns Err before anything starts, so no Monitor exists and nothing is observed (crates/agent-monitor/src/capture.rs:40-42; lib.rs:49-53). Process exit is reported by acp-host's HarnessExited, not by the monitor (crates/roundtable/src/engine.rs:465-466).
- **GF2** (Blocker, egm-codebase-details, decisions; investigations: platform check): 'Granting capabilities is a one-time setup step' and 'capture needs root or CAP_BPF/CAP_PERFMON on the capture binary' contradict the code. It requires effective uid 0 and rejects a process holding CAP_BPF and CAP_PERFMON without root (crates/agent-monitor/src/capture.rs:179-209; test at capture.rs:506-509). There is also no lasting capture binary to grant capabilities to: the probes are unpacked by BinaryExtractor while the monitor runs (capture.rs:50-52).
- **GF3** (Major, egm-codebase-details, wants: code.monitor.activity): 'Observable model-provider activity': sslsniff is limited to the harness pid, not its children, and AgentSight's LLM classifier is not used (crates/agent-monitor/src/lib.rs:33-45; capture.rs:103-114).
- **GF4** (Major, egm-codebase-details, whole document): Unstated dependency details: (1) The version is pinned exactly at agentsight-capture =1.0.35 (crates/agent-monitor/Cargo.toml:18); the investigation only mentions the crates.io update date. (2) The dependency is optional behind the default `agentsight` feature (Cargo.toml:8-12). (3) The probes ship prebuilt, so building needs no clang or headers, but at run time they need libelf, libz and libzstd (lib.rs:55-58).
- **GF5** (Nit, egm-codebase-details, whole document): The probe settings are not recorded: process probe `-p <pid> -m 2 --trace-fs --trace-net` seeded with the pid family (capture.rs:55-58); sslsniff with `--binary-path` when the executable embeds its own TLS library (capture.rs:105-114); HTTPParser with raw data disabled (capture.rs:119-123).
- **GF6** (Major, egm-comprehension, decisions vs. elephant gaps): The decision says monitoring fails open with unprivileged observation; the gap says 'Needs root' and the code's attach fails without root. The current behaviour is unclear.
- **GF7** (Major, egm-comprehension, investigations vs. elephant): The investigation says root or CAP_BPF/CAP_PERFMON is enough; the elephant layer says root, and the code shows capabilities without root still fall back to sudo -n. The documented setup would not work.
- **GF8** (Major, egm-comprehension, decisions): The 'one-time setup step the owner chooses' has no steps or link, and it conflicts with the root service under HoldOn named in code.monitor.activity.
- **GF9** (Nit, egm-comprehension, wants): 'Observable model-provider activity' is vague: the document doesn't say how provider traffic is seen (e.g. TLS capture) or when it can't be.
- **GF10** (Nit, egm-comprehension, investigations): Only the owner's WSL2 machine was checked; the platform limits in general are not stated or linked.

The code for this part is copied into the `source` folder here, under the same paths as above.
