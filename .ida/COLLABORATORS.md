---
title: "Collaborators"
type: collaborators
status: active
created: 2026-11-08
updated: 2026-11-08
---

## metaform-d2 / consolidation session
- Role and responsibility: Consolidated this folder and set up the GitHub repository `RchGrav/metaform` (private, `main` pushed). The owner's old repository is now `RchGrav/metaform-archive`.
- Relevant current work: A read-only review of `metaform-archive`: what went right, what went wrong and what fits this project. Pending the owner: applying the rename of `intent` to `direction` across the protected intake, schema, contract, servers and stored maps.
- Coordination preferences or dependencies: No overlap with R-001, R-002 or R-005. Asked that an export of the topogee map account for the later `direction` migration. Leaves committing `.ida/` and `.marcus/` to the owner.
- Source and last verified date: Its message of 2026-11-08. Commit `db8c9f8` and the `origin` remote were verified by Ida on 2026-11-08.

## metaform-ba / Marcus (MCP consultant)
- Role and responsibility: Reviews the Metaform MCP server layer: `metaform-server/src/*`, `mcp-tools.proposed.json`, and `SPEC.md` §1, §2, §4.2, §5 and §8-10. Notes are in `.marcus/notes.md`.
- Relevant current work: No code changes yet. Pending the owner: a test that records the serialized `tools/list` size as an R-1.3 baseline, and possibly a rewrite of the protected contract text.
- Coordination preferences or dependencies: Leaves R-001 (path-keyed maps) to Ida. Wants to be told if a fix changes the handshake or the map URI (`announce.rs` `map_uri` embeds the project id). Logged separately: the server trusts the handshake folder, and only the forwarder canonicalizes it.
- Source and last verified date: Its message of 2026-11-08. Not otherwise verified.
