# node

Serves Metaform from a host of your own, reachable from the internet behind your own sign-in.

## Purpose

The node module writes, deploys and runs the Metaform Node: the MCP server with A2A, and the web page, in Docker on
a Linux host, behind Caddy for TLS and the Node's own OAuth 2.1 authorization server, where people sign in with
passkeys. Every verb is the person's own, on the command line; none is a tool an agent can call. The design, the
modes and what a host needs are in [docs/guides/metaform-node.md](../../../../docs/guides/metaform-node.md).

With `node_role` at `broker` the same Node is metaform.ing's broker instead: it serves no Metaform of its own, keeps
nothing on disk but accounts and their passkeys' public keys, signs every token with its own key (`tokens.py`), signs
people's machines in with the device grant (`device.py`, for `metaform cloud login`), and carries AI hosts' MCP down
each person's own tunnel to the Metaform on their machine (`broker.py`). The person's side is the cloud module.

## Template version

The template changelog version this module started from: 0.2.0.

## Declaration

`SUPPORTED_OS = ('linux', 'macos', 'windows')`; `DEPENDENCIES` adds `webauthn` (Duo's py_webauthn) to what the mcp
module already needs, and `pyjwt[crypto]` and `websockets` for the broker's signed tokens and tunnel; `SHIPS_DISABLED =
False`.

## Common base used

`metaform.module` for the declaration, `Context` and `Stop`; `metaform.settings` for its settings; `metaform.home`
for the home's folders; `metaform.data.private_database` for the authorization server's own SQLite file.

## Prompts

`resources/prompts.xml` holds the four standard elements, all empty: no node verb is offered to agents. The sign-in,
setup and consent pages under `resources/` are the person's, not prompts.

## Verbs

- `init <domain> [owner=] [dir=]`: the compose project in `metaform-node/` (`node_dir`): `compose.yaml`, `Caddyfile`,
  `Dockerfile`, `node.json`, and `bootstrap/owner-invite.json`, the hash of the owner's one-time setup secret. It
  prints the setup link once; the secret is kept nowhere. It refuses a name that is not a public host name, a
  missing certificate contact, and a relay name that is reserved or not the instance's own. On a Node (not a broker)
  it also writes `gate.env` once, mode 0600, the per-deploy secret Caddy adds to every page request so the page
  server trusts the gate's account headers only from Caddy; `init` and `update` keep it.
- `deploy [--dry-run]`: on Vultr (`--node-provider vultr`, key in `VULTR_API_KEY`) creates the SSH key, a firewall
  group (22, 80, 443 and, on a relay host, 7000) and an Ubuntu 24.04 instance prepared by cloud-init; on any other
  fresh Ubuntu host (`--node-host`) runs the same preparation over SSH. Then it waits for DNS, builds the wheel, copies
  the project, builds and starts it, waits for health, and checks TLS, the metadata and `/mcp`'s 401 from outside.
  `--dry-run` prints every step, the API calls and the cloud-init included, and runs none.
- `status`, `logs [service=] [lines=]`, `update [--dry-run]`: the services' health and the outside checks; the
  recent logs; rebuild with this Metaform and restart what changed.
- `auth`: the authorization server itself, run by the `auth` container.
- `invite <name>`, `accounts`, `revoke <name>`: the allowlist. An invitation is an account and a one-time link to
  enrol a passkey; run where the Node's folder and host are known, these run on the host through
  `docker compose exec`. `revoke` ends the account's sessions, links and tokens.
- `signout <name>`: signs an account out everywhere by moving its generation: every signed token, session and
  tunnel it holds stops working (a running broker ends its sessions at once and its tokens and tunnels within half a
  minute). Run beside a broker it opens the broker's store, by the role `auth` last ran as (`role` in the authorization server's folder).
- `rotate-key [revoke_old=true]`: a new signing key for a broker's tokens, which the running broker uses within five
  seconds. The old one stays published until its tokens expire; with `revoke_old=true`, for a key that may have been
  copied, every older key is deleted at once and every token it signed, genuine or forged, is refused.
- `connect`: how Claude Code, VS Code, Cursor and claude.ai add the Node, and its Agent Card URL.
- `relay <name>`: this Metaform through a relay with no open port, the enrolment secret read from
  `METAFORM_RELAY_TOKEN`; at `node_relay_capability`, `read` unless raised.
- `relay-init <domain>`, `relay-enrol <name>`, `relay-gate`: the relay operator's compose project (frps and the
  gate), a name's one-time enrolment secret, and the gate frps asks on every login and proxy.

## Settings

`node_domain`, `node_mode` (acme, dns, relay, internal), `node_email`, `node_capability` (read, write, dispatch;
write by default), `node_relay_capability` (read by default), `node_projects`, `node_dns_provider`, `node_wildcard`,
`node_dcr` (off), `node_host`, `node_ssh_identity`, `node_dir`, `node_provider`, `node_vultr_region` (ewr),
`node_vultr_plan`, `node_vultr_os` (2284, Ubuntu 24.04), `node_ssh_public_key`, `node_relay_server`,
`node_relay_port`, `node_relay_domain`, `node_dry_run`, and for a broker `node_role` (node, broker),
`node_refresh_replay` (memory, durable; memory) and `node_member_dispatch` (off). The ones that decide who reaches
what are person-only, and so are `node_projects`, `node_host`, `node_ssh_identity` and `node_ssh_public_key`, which
say what the Node exposes, which host deploy reaches and which key a created VM trusts for root.
No secret is a setting: API keys come from the environment, DNS and relay tokens from `secrets.env` on the host.

## Events

None published or subscribed.

## Sync and async

Every verb is synchronous; `auth` and `relay-gate` run their own uvicorn servers until stopped. The broker's tunnel
endpoint and host requests are asyncio, in that server's loop.

## Layers

None. The authorization server keeps `auth.sqlite` in its own folder (accounts with their generation and pending
invitation, passkeys' public keys, and on a self-hosted Node sessions, clients, codes and tokens, every secret as its
SHA-256); a broker keeps only the accounts and passkeys there, with its signing keys in `keys/` (mode 0600), and
everything else in memory. That folder is `METAFORM_NODE_AUTH`, the `auth` volume at `/data/auth`, in the Node's auth
container, which is the only container that mounts it, so the page, MCP and every agent they start cannot reach the
accounts; anywhere else it is `<home>/node`. On its first start after an update, `auth` moves what an older Node kept
in `<home>/node` to the volume and removes the old folder. The relay keeps `relay/enrolments.json`.

## The page behind the gate

Caddy asks `/node/gate` before every page request. The gate answers the account, its role and the classes of page
route it may use: `read` and `write` for every account, `dispatch` only on a Node at `dispatch` capability, `admin`
(settings, modules, prompts, bases, backups, removing or clearing a project, builds, MCP Apps tool calls) only for the
owner. Caddy drops whatever a client sent under those header names, copies the gate's, and adds the `gate.env`
secret; Host and Origin reach the page server as the browser sent them. The page server runs with
`--origin https://<domain>` and the secret, refuses any request without it or for another host, and refuses a route
whose class the gate did not grant (`web/server.py`, `route_class`).

## Lifecycle and cleanup

No `start` or `stop`. The `auth` verb writes `run/node-introspection`, the resource servers' introspection
credential, and `issuer` and `role` in its own folder.

## Modules relied on

mcp, through its settings `mcp_public_url`, `mcp_bind` and `mcp_introspection`, written into the compose file, and
through RFC 7662 introspection over loopback; web, whose server process the compose file runs. Neither is imported.
The broker and the cloud module read one definition of the tunnel's wire format, `metaform.frames` in the public base.

## Systems supported

`linux`, `macos` and `windows` for writing projects, dry runs and the CLI; the Node itself runs in Linux containers
on an Ubuntu host.

## Resources owned

The compose project folder it writes, the auth store, and, while `auth` or `relay-gate` runs, port 7435 or 7440 on
loopback.

## Installed and direct wheel

The same in both; `deploy` builds the wheel the image installs with `metaform build kind=full`.

## Demonstration

```
metaform node init metaform.example.com --node-email me@example.com
metaform node deploy --dry-run --node-host 203.0.113.9
metaform node connect
```

## Files

`config.py` the files; `authserver.py` and `authstore.py` the authorization server; `tokens.py` the signed tokens,
generations, refresh families and DPoP; `device.py` the device sign-in and the account page; `broker.py` the broker;
`plans.py` the deploy plans and
the host script; `vultr.py` the Vultr calls; `tunnel.py` the relay; `health.py` the image's health check;
`resources/` the sign-in, setup, consent, device and account pages and `passkey.js`.
