---
name: metaform-node-hosting
description: Use when editing Node gate, Caddy, gate.env, page routes, route_class, or what a Node member may run or save.
category: development
---

# Changing the Node's trust chain

A page route the gate does not know is refused. Add every new page route to `route_class` in `src/metaform/modules/web/server.py` in the same change; an unlisted POST counts as `admin`, so a member gets 403 until it is classed. Class a route by what it stores, not by how the page calls it: any route that saves a home-global setting (`workspace._put`: web_toolbar, web_layout, web_workspaces, web_workspace) is `admin`. Keep every secret the Node uses out of the shared home and away from agents. Chain, invariants and test commands: `references/node-trust-chain.md`.

- Origin checks go through `Handler.same_origin` only. A test's `_Handler` stand-in must define `same_origin` too.
- A tool run (`POST /api/workspace/run`) is classed per verb, not by URL: `route_class` passes it as `read`, then `workspace.run` calls `Handler.holds(server.verb_class(...))` before the caution prompt and before `module_verb`, so a refused account is refused without first being asked to confirm. `verb_class`: admin for a caution verb or one given a `person_only` setting; dispatch for the dispatch module or a non-read `open_world` verb (as `mcp.oauth.required_scope`); otherwise read or write by effect. Keep it in step with `page_classes` (node/config.py, mirrors `scopes_for`): `read` always; `write` only at write or dispatch capability; `dispatch` only at dispatch; `admin` only for the owner.
- `Handler.holds(needed, path)` is the single class check, and `permitted()` calls it. A test's `_Handler` stand-in needs `holds()` too: return True when the page is ungated, as the workspace tests' fake does.
- Check a gate change against a copy of the home, never the live one: `cp -a <home> $S/`, `METAFORM_HOME=$S/home`, then call the page server on 127.0.0.1 with the gate secret and `X-Metaform-Classes` headers. A member at read capability must get 403 "needs write" on `/api/note`; a member at write capability must get 403 "needs admin" on `/api/workspace/save`.
- Open: members on a gated Node cannot save their page arrangement now; whether they get their own arrangement is the person's call.
- `gate.env` (`METAFORM_GATE_SECRET`) reaches the caddy and web services only. The page server reads it once and removes it from its environment before starting anything.
- Accounts, passkeys and keys live on the `auth` volume, mounted into the auth service only. Nothing new goes under the shared home, which web and mcp both read.
- A setting that chooses what the Node exposes, which host deploy reaches or which SSH key a VM trusts is `person_only`.
- A change in Node behaviour updates `modules/node/README.md`, `modules/web/README.md` and `docs/guides/metaform-node.md` together. Running Nodes take Caddy or compose changes only through `metaform node update`.

## Files

- `references/node-trust-chain.md`: the gate, Caddy and secret flow, the route classes and the open gaps.
