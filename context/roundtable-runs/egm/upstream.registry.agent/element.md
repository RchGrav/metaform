# Map element `upstream.registry.agent`: ACP Registry

This document is one element of the functional map of Roundtable, a program in which several AI agents discuss a user's objective in turns while an evaluator checks each message. The map records what each part of the program must do, what it relies on, and knowledge about it. Paths are relative to the Roundtable folder.

## Properties
```json
{
  "name": "ACP Registry",
  "name_length": 2,
  "uri": "https://cdn.agentclientprotocol.com/registry/v1/latest/registry.json"
}
```

## What other parts rely on it for (their wants)
- `code.launcher.agent`: goal: Resolve a selected harness name to a launch command without a bespoke integration per harness. Function: Lists published ACP agents and their distributions (binary, npx, uvx), as used by acpr. Intent: receive

## Layer `references`
```json
[
  {
    "path": "Roundtable_ACP_Integration_Design.md",
    "sections": [
      "7.1 Published ACP agents: official Registry and acpr",
      "7.2 acpx agent catalog"
    ]
  }
]
```

## Layer `elephant` (the project author's account of this element)
```json
{
  "date": "2026-11-07",
  "design": "The ACP Registry lists published ACP agents and how to start them.",
  "sources": [
    "README.md §9.2"
  ],
  "built": "Read at start-up for the harness catalog; 45 agents on 2026-11-07.",
  "gaps": [
    "The registry does not say which ACP version an agent speaks."
  ]
}
```

## The review findings to resolve

Two reviewers who had never seen this project read the description above and the code. Their findings follow. Severity: Blocker means the description says something the code does not do; Major means an important gap; Nit means a small one.

- **GF1** (Blocker, egm-codebase-details, elephant.built): 'Read at start-up for the harness catalog' is false. autoselect fetches REGISTRY_URL every time it is called (crates/acp-host/src/launch.rs:214-219). It is called on every harness-list request (crates/roundtable-web/src/app.rs:209-210) and at table creation (crates/roundtable-web/src/tables.rs:110-112). Nothing reads it at start-up or caches it.
- **GF2** (Major, egm-codebase-details, wants: code.launcher.agent): The launch order is undocumented. A binary already on PATH runs directly with the registry's arguments (launch.rs:117-125). Otherwise `acpr <id>` is used when acpr is installed (launch.rs:96-98, 126-127). Without acpr, npx or uvx entries run directly with a note (launch.rs:128-130), and binary-only entries are unavailable (launch.rs:131-133). The binary is chosen by platform key (launch.rs:140-147).
- **GF3** (Major, egm-codebase-details, whole document): The security filter is undocumented: entries may not set PATH, NODE_OPTIONS, NODE_PATH, PYTHONPATH, PYTHONSTARTUP, BASH_ENV, ENV, HOME, or any LD_*, DYLD_* or NPM_CONFIG_* variable (crates/acp-host/src/launch.rs:168-185).
- **GF4** (Major, egm-codebase-details, whole document): Fallback is undocumented: on any fetch or parse failure the built-in list is used with a note, and on success built-ins the registry does not list are added (crates/acp-host/src/launch.rs:212-231).
- **GF5** (Nit, egm-codebase-details, elephant): '45 agents on 2026-11-07' cannot be checked from code. elephant.sources cites README §9.2, while the references cite design §7.1/7.2.
- **GF6** (Major, egm-comprehension, wants / references): 'acpr' and 'acpx' are undefined, and 'as used by acpr' doesn't say whether Roundtable calls acpr or copies its resolution.
- **GF7** (Major, egm-comprehension, elephant built): 'Read at start-up' doesn't say what happens if the CDN fetch fails or whether there is a cache or offline fallback.
- **GF8** (Major, egm-comprehension, elephant gaps): The missing ACP version is listed as a gap without its consequence for launching v1 vs v2 agents.
- **GF9** (Nit, egm-comprehension, elephant sources): README §9.2 is cited as a source but missing from the references layer.

The code for this part is copied into the `source` folder here, under the same paths as above.
