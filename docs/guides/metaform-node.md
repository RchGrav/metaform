# The Metaform Node

The Node puts a Metaform where agents elsewhere can reach it: the MCP server, A2A and the web page on a host the
owner controls, reachable from the internet, with nothing served to anyone the owner has not let in. It is one image
and one compose project; self-hosting, a relay, and hosted instances on metaform.ing are configurations of it, not
separate products.

Built in the `node` module (`src/metaform/modules/node/`) and the mcp module's `oauth.py`. Commands:
`metaform help node`.

## Shape

```
internet ──443──> Caddy (TLS, Let's Encrypt) ── one network namespace, every Metaform process on 127.0.0.1 ──
                    ├─ /.well-known/oauth-authorization-server, /oauth/*, /node/*  ->  auth  :7435  (the AS, passkeys)
                    ├─ /mcp, /.well-known/oauth-protected-resource/*, /a2a*, /.well-known/agent-card.json
                    │                                                              ->  mcp   :7434  (checks its own tokens)
                    └─ everything else: forward_auth /node/gate, then              ->  web   :7433  (the page)
```

- **Caddy** (2.11.7, pinned by digest) is the only service with ports. It was chosen because automatic HTTPS is its
  default: it obtains and renews certificates with HTTP-01 and TLS-ALPN-01, DNS-01 through `caddy-dns` modules, and
  its `forward_auth` directive is how the page sits behind the Node's session without the page server changing.
- **auth**, **mcp** and **web** run the same image (`python:3.13.13-slim-trixie`, pinned; user `metaform`, uid 10001;
  read-only root filesystem; all capabilities dropped; `no-new-privileges`; the home on the `home` volume; project
  folders mounted at `/srv/projects/<name>`). Each has a health check (`python -m metaform.modules.node.health`);
  mcp and web start once auth is healthy.
- The page server is `python -m metaform.modules.web.server`, the process `metaform web start` itself spawns, run in
  the foreground. Caddy hands it the loopback Host and Origin it checks, after refusing any request whose Origin is
  another site; the page needs no change.
- **The one-port merge is a drop-in.** The authorization server is a Starlette app (`authserver.Node.app()`), the
  resource-server pieces are ASGI (`oauth.py`), and Caddy's routes are by path. When MCP, A2A and the page become one
  ASGI service, the three upstreams become one and the gate moves from `forward_auth` into middleware; the paths, the
  tokens, the metadata and the accounts stay as they are.

## Authorization

The Node is its own OAuth 2.1 authorization server, as the MCP authorization specification of 2026-07-28 describes,
for two protected resources: `https://<domain>/mcp` and `https://<domain>/a2a`. Checked against the specification's
text ([authorization](https://modelcontextprotocol.io/specification/2026-07-28/basic/authorization),
[discovery](https://modelcontextprotocol.io/specification/2026-07-28/basic/authorization/authorization-server-discovery),
[client registration](https://modelcontextprotocol.io/specification/2026-07-28/basic/authorization/client-registration),
[security considerations](https://modelcontextprotocol.io/specification/2026-07-28/basic/authorization/security-considerations)):

| Requirement | How the Node meets it |
|---|---|
| MCP server implements Protected Resource Metadata (RFC 9728) | `/.well-known/oauth-protected-resource/mcp`: resource `https://<domain>/mcp`, `authorization_servers: ["https://<domain>"]`, scopes `mcp:read mcp:write` |
| 401 carries `WWW-Authenticate` with `resource_metadata` | the MCP SDK's bearer middleware |
| AS metadata (RFC 8414), issuer compared exactly | `/.well-known/oauth-authorization-server`; issuer `https://<domain>` with no trailing slash (a test holds this) |
| OAuth 2.1, authorization code, PKCE S256 only | the SDK's authorize and token handlers; `code_challenge_methods_supported: ["S256"]` |
| Client ID Metadata Documents (SHOULD) | `client_id_metadata_document_supported: true`; the document is fetched over HTTPS, no redirects, 5 KB at most, 5 s, from public addresses only (SSRF); `client_id` must equal its URL; redirect URIs https or loopback http; cached by Cache-Control (1 min to 1 day) |
| Dynamic Client Registration is deprecated, MAY | off; `node_dcr` turns it on for an older client |
| Exact redirect URI match; loopback on any port | exact, except loopback, which matches on any port (RFC 8252 section 7.3), as native clients pick a free port |
| Consent shows the client and the redirect host; warns on localhost | the consent page names both and warns on a loopback redirect |
| `iss` in the authorization response (RFC 9207) | on every redirect, errors included; `authorization_response_iss_parameter_supported: true` |
| Audience-bound tokens (RFC 8707); servers accept only their own | each token names one resource; MCP accepts only `.../mcp`, A2A only `.../a2a`, and both check the issuer |
| Short-lived access tokens; refresh rotation for public clients | access 1 hour; refresh 30 days, rotated on each use, a reused one revokes its family; a reused code revokes what it gave |
| Step-up on insufficient scope | 403 `insufficient_scope` with `scope` and `resource_metadata` before the call reaches the server |
| No token passthrough | the Node calls nothing upstream with a client's token |
| HTTPS for every AS endpoint | Caddy; the issuer is `https://` always |

Scopes follow the instance's capability level, `node_capability`:

| Level | Grants | What it allows |
|---|---|---|
| read | `mcp:read` | the map, briefs, glossaries, MCP Apps views, memories read |
| write (default) | + `mcp:write`, `a2a:tickets` | writes of memories, tickets and terms; A2A tickets |
| dispatch | + `mcp:dispatch` | tools that start or steer agents with shells and file writes |

A client asking for more than the level grants receives what it grants (RFC 6749 section 3.3), shown in the token
response. Below dispatch the `dispatch` module is also switched off in the container.

**People** sign in with passkeys (WebAuthn): there are no passwords. `metaform node init` prints the owner's one-time
setup link; only its SHA-256 goes to the host, and the secret travels in the link's fragment, which no server logs.
`metaform node invite <name>` makes an account and a link for anyone else, so the accounts are the allowlist; `revoke`
shuts one out. Lost every passkey? `invite <your name>` on the host makes a new link: shell access to the host is the
recovery, as it is for any self-hosted service. Passkeys require user verification and are discoverable (no user
name to type). TOTP is not built: with passkeys only and recovery through the host, it would add a second secret to
keep without closing a gap.

**The page** is behind the same sign-in: Caddy asks `/node/gate` before every request; the session cookie is
`__Host-`, Secure, HttpOnly, SameSite=Lax, seven days.

**A2A** gets its own credential: a token for audience `https://<domain>/a2a` with scope `a2a:tickets`, from the same
authorization server. Its Agent Card declares an OAuth 2.0 authorization-code scheme (PKCE required) with the
server's metadata URL. No static A2A token is made on a Node.

**Who is calling** reaches the MCP server as the token's subject: the MCP Apps views' `focus` is kept per signed-in
account, so two people using one AI tool never turn each other's views.

**Refusal.** An MCP server bound to anything but loopback, or given a public URL, does not start without the Node's
authorization server: it stops with the next step (`oauth.exposure`). The page server already refuses a non-loopback
bind without its token.

External OIDC sign-in (an identity provider the owner already has) is a possible later option, off by default; it is
not built. No outside company is in the sign-in path.

### Libraries

| Piece | Library | Version | Why |
|---|---|---|---|
| OAuth endpoints, PRM, bearer middleware, audience check | MCP Python SDK (`mcp.server.auth`) | 2.2 (pinned via `mcp>=2.2,<3`) | already Metaform's MCP server; maintained with the specification, so the handlers move with it |
| Passkeys | py_webauthn (`webauthn`), Duo Labs | 2.8.0 | maintained WebAuthn Level 3 relying-party library; options, attestation and assertion verification, no crypto of ours |
| HTTP server | Starlette and uvicorn | as the SDK requires | what the SDK and A2A already run on |
| Client metadata fetch, introspection | httpx | 0.28 | already a dependency |
| A2A | a2a-sdk | 1.2.2 | the OAuth2 security scheme types |

Secrets are `secrets.token_urlsafe(32)` and are stored only as SHA-256. The store is `node/auth.sqlite` in the home,
apart from every project's map.

## Deploying

`metaform node init <domain> --node-email <you>` writes the project; `metaform node deploy --dry-run` prints the plan;
without `--dry-run` it runs it. On Vultr (`--node-provider vultr`, `VULTR_API_KEY` in the environment, never stored)
the plan is: POST `/v2/ssh-keys`, POST `/v2/firewalls`, the rules (22, 80, 443/tcp, 443/udp, and 7000 on a relay
host, IPv4 and IPv6), POST `/v2/instances` (region `ewr`, New York (NJ); plan `vhf-1c-1gb`, 1 vCPU, 1 GB, 32 GB NVMe;
`os_id` 2284, Ubuntu 24.04 LTS; the cloud-init as `user_data`), then GET `/v2/instances/{id}` until active. Field names
follow Vultr's own client, govultr v3. Check the plan id against `GET /v2/plans` for the size you want.

The host preparation is one idempotent script, run by cloud-init on first boot or over SSH on any fresh Ubuntu host:
Ubuntu only; a 3 GB swap file, added once; `/dev/shm` noexec,nosuid,nodev; Docker from Docker's apt repository; the
`metaform` user with a home and shell, in the docker group, sudo only for `systemctl restart docker` and `ufw status`
in its own sudoers file; ufw allowing 22, 80, 443 (and 7000 on a relay host) only; SSH keys only and root by key only,
once a key is in place; unattended security upgrades; fail2ban for SSH; bash completion. No certbot (Caddy does ACME),
no system pip (24.04's Python is externally managed), no repeated fstab lines.

Then: wait until the domain resolves to the host (asking Let's Encrypt early only spends its rate limit), build the
wheel (`metaform build kind=full`) with a constraints file of the versions tested here, copy the project over SSH,
`docker compose up -d --build`, wait for every service to be healthy, and check from outside: the certificate, the
AS metadata naming its issuer with CIMD on, the PRM naming the resource and the server, and `/mcp` answering 401 with
`resource_metadata`. `status`, `logs` and `update` reuse the same steps.

Then `metaform node connect` prints `claude mcp add --transport http metaform https://<domain>/mcp`, the VS Code and
Cursor entries, the claude.ai connector URL and the Agent Card URL. Each tool opens the Node's sign-in the first time.

### What a real host needs from the owner

- A domain or subdomain, and an A (and AAAA) record pointing at the host; for the relay, `*.metaform.ing` and
  `relay.metaform.ing` pointing at the relay host.
- For Vultr: an account, an API key in `VULTR_API_KEY` (Vultr limits API keys by source address; allow yours), and an
  SSH public key (`node_ssh_public_key`). For any other provider: create the VM (Ubuntu 24.04), then `node deploy`.
- An email address for Let's Encrypt.
- For DNS-01 (wildcards): the DNS provider's API token in `secrets.env` on the host as `DNS_API_TOKEN`.
- The word go: no real server, DNS record or certificate has been created.

## The relay

For a Metaform with no open port. The instance runs frpc, which dials the relay; the relay's frps routes each TLS
connection by its server name to that instance's tunnel without terminating it (frp's `https` proxy type), so the
relay holds no certificate and reads nothing. The instance obtains its own certificate through the same passthrough
with ACME TLS-ALPN-01, whose challenge is answered in the TLS handshake on port 443 for the very name being routed
(HTTP-01 would need the relay to proxy plain HTTP; DNS-01 would put a credential for the operator's zone on every
instance). Capability through a relay is `read` unless the owner raises `node_relay_capability`; dispatch is never
reachable through it otherwise.

**Why frp.** frp (fatedier/frp, Apache-2.0, v0.71.0, actively released) routes many names on one port by SNI with
passthrough, reconnects by itself (`loginFailExit = false`), carries its control channel over TLS, and has a
server-plugin protocol in which frps asks an HTTP service on every login and every new proxy. rathole maps one port
per service and has no SNI routing, so it cannot put many instances on 443; inlets is a commercial product now. The plugin is how each client is authenticated: `metaform node relay-enrol <name>` issues a
secret per name, kept as its hash, and the gate admits a login only with it and a proxy only for `https` under that
same name.

A local stand-in run during development showed it working: frps, the gate and an enrolled frpc, curl through the
relay received the instance's own certificate (Caddy's local CA), proving the stream was not terminated; a client with
a wrong secret was refused "not enrolled".

Operator: `metaform node relay-init metaform.ing` writes the relay's compose project (frps on 443 and 7000, the gate
in its network namespace), then `relay-enrol <name>` inside the gate container. User: `METAFORM_RELAY_TOKEN=<secret>
metaform node relay <name> --node-relay-server relay.metaform.ing` writes the relay-mode project and builds the wheel;
`docker compose up -d --build` starts it.

**Alternatives the owner can choose instead.** Tailscale Funnel: TLS ends on the owner's device with a certificate
Tailscale obtains for a `ts.net` name, and Tailscale's relays carry the encrypted stream; point Funnel at the Node's Caddy, or, after the one-port merge, at
Metaform directly, and use the `ts.net` name as the Node's domain. Cloudflare Tunnel: simple
and free, but Cloudflare terminates TLS, so Cloudflare can read the traffic, sign-in included; acceptable only if the
owner accepts that.

**Gap.** On a laptop the relay serves the containerized Node with its own home, not a Metaform running natively;
pointing frpc at a native Metaform waits on the one-port service.

## Hosted instances on metaform.ing

The same image, one instance per user (`<name>.metaform.ing`), each with its own authorization server, passkeys,
store and settings; nothing shared between instances.

- **Isolation follows capability.** Instances at read or write (map, briefs, glossaries, MCP Apps, memories, tickets,
  terms) may run as separate compose projects on a shared host: separate volumes, separate network namespaces, no
  published ports but a front door, per-instance secrets. Any instance at dispatch runs agents with shells and file
  writes, so it gets a VM of its own. The same rule is the advice to self-hosters.
- **TLS.** Either each instance keeps its own certificate behind an SNI-passthrough front (the relay's frps, so the
  operator never holds a key), or the operator's Caddy terminates with one wildcard certificate by DNS-01
  (`node_mode dns`, `node_dns_provider`, `node_wildcard metaform.ing`; the generated Caddyfile serves `*.metaform.ing`
  and answers only for the instance's own name). Passthrough keeps the operator out of the traffic; termination is
  simpler and lets the operator see it. Either way no third party is in the sign-in path: passkeys are checked by the
  instance's own authorization server.
- **Operating without reading data.** The operator provisions with `node init` and `deploy`, updates with `update`
  (the image is rebuilt; the volumes are untouched), and backs up the `home` volume as an encrypted snapshot
  (`docker run --rm -v <instance>_home:/v alpine tar -C /v -cz . | age -r <user's key>`), so a backup is readable
  only by the user. The operator has the host's root, which can read volumes; the honest statement is that hosting
  means trusting the operator, and self-hosting or the relay is the answer for anyone who does not.

## Moving an instance

What moves today: each project with `metaform build kind=archive project=<id>` (the project's data and, with
`files=true`, its files), imported on the other Node with `metaform import <archive>`; or `metaform export all
file=...` and `metaform import`, the JSON document. Both directions, self-hosted to managed and back.

Gaps, written down: no single command exports the whole home (every project, the settings, which modules are on,
aliases); settings travel only by hand from `metaform config --show`. The accounts do not move and should not: a
passkey belongs to its domain (WebAuthn's relying party), so people enrol again on the new name; tokens are re-issued
by the new authorization server. A `node export` that bundles every project archive with a settings document is the
natural next step.

## Known gaps

- No test drives a real authenticator through the passkey ceremony; the options, the invitation rules and the
  origin checks are tested, and verification is py_webauthn's.
- The relay operator's own deploy is by hand (`relay-init`, copy, `docker compose up -d --build`); `node deploy`
  opens the relay's port on a host that also runs it (`--node-relay-domain`).
- Dispatch inside the image has no agent CLIs installed; a dispatch-level Node needs them added to its image.
