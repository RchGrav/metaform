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
                    ├─ /phone/*  (Twilio's webhooks and call audio)                ->  twilio :7441 (checks Twilio's signature)
                    └─ everything else: forward_auth /node/gate, then              ->  web   :7433  (the page)
```

- **Caddy** (2.11.7, pinned by digest) is the only service with ports. It was chosen because automatic HTTPS is its
  default: it obtains and renews certificates with HTTP-01 and TLS-ALPN-01, DNS-01 through `caddy-dns` modules, and
  its `forward_auth` directive is how the page sits behind the Node's session.
- **auth**, **mcp** and **web** run the same image (`python:3.13.13-slim-trixie`, pinned; user `metaform`, uid 10001;
  read-only root filesystem; all capabilities dropped; `no-new-privileges`; the home on the `home` volume; project
  folders mounted at `/srv/projects/<name>`). The accounts, passkeys and keys are on the `auth` volume, mounted at
  `/data/auth` into auth only, so nothing running in mcp or web, agents included, can read or change them. Each has a health check (`python -m metaform.modules.node.health`);
  mcp and web start once auth is healthy.
- The page server is `python -m metaform.modules.web.server`, the process `metaform web start` itself spawns, run in
  the foreground with `--origin https://<domain>` and the gate secret from `gate.env`. Caddy refuses any request whose
  Origin is another site, then passes Host and Origin through unchanged; the page server checks them against its
  public origin, and takes the account only from requests that carry the gate secret.
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
`__Host-`, Secure, HttpOnly, SameSite=Lax, seven days. The gate says who is calling and which classes of page route
the account may use: every account reads; writes (the map, tickets, notes, memories) need a Node at `write`
capability; `dispatch` (starting and steering agents) needs a Node at `dispatch` capability; `admin` (settings, the
page's toolbar, layout and saved workspaces, modules, prompts, bases, backups, removing or clearing a project, builds,
MCP Apps tool calls) is the owner's only. A toolbar tool that runs a verb is classed by that verb, as an MCP tool call
is scoped: a read is `read`, a write `write`, a dispatch verb or one that reaches past the map `dispatch`, and a verb
with a caution or a person-only setting `admin`. Caddy drops any client-sent copies of those
headers and adds the per-deploy secret in `gate.env`; the page server refuses a request without it, and a route
whose class the account was not given.

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

Secrets are `secrets.token_urlsafe(32)` and are stored only as SHA-256. The store is `auth.sqlite` on the `auth`
volume, which only the auth container mounts, apart from every project's map and from the home the other containers
share.

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

## metaform.ing: the cloud broker

The broker lets AI tools that run in the cloud (ChatGPT, Claude on the web, any remote MCP host) reach the Metaform on
a person's own machine, with no port opened there. It is the same image with `node_role` at `broker`; the person's
side is the cloud module (`src/metaform/modules/cloud/`).

```
 claude.ai / ChatGPT ──HTTPS, Bearer (aud = https://metaform.ing/mcp[/<instance>])──┐
                                                                                      ▼
                       metaform.ing: Caddy :443 ── one process on 127.0.0.1:7435
                                                    authorization server, passkeys, device sign-in, key set
                                                    broker: /mcp*, /cloud/tunnel
 person's machine: metaform cloud connect ──WSS, DPoP (aud = https://metaform.ing/cloud/tunnel)──┘
                   └─ the MCP server's app run in-process (no listening socket), audit log, person-only rules
```

### For the person

1. Install Metaform on the machine that holds the projects.
2. `metaform cloud login`: the terminal shows a code and opens `https://metaform.ing/device`; sign in with the passkey,
   check the code matches, approve.
3. `metaform cloud connect`, left running (or `cloud_autoconnect`, so `metaform web start` starts it).
4. In ChatGPT or Claude, add a custom connector at `https://metaform.ing/mcp`, sign in with the passkey, Allow.

A second machine takes its own name first (`metaform set --cloud-instance laptop`) and is reached at
`https://metaform.ing/mcp/laptop`. `metaform cloud status` shows the state and the URL.

### One account, two kinds of client

The local service and the AI host sign in to the same authorization server, as the same account, with the same
passkey. The local service uses the device authorization grant (RFC 8628) as the built-in public client
`metaform-cli`, its tokens bound to a key it made (DPoP, RFC 9449); the host uses the authorization code grant with
PKCE S256, identified by its Client ID Metadata Document, exactly as on a self-hosted Node. Dynamic Client
Registration stays off unless `node_dcr` is on. On a broker it then keeps nothing: the client id it hands back is a JWT
of the registered metadata signed with the Node's key, and a secret, for a client that asks for one, is derived from
that key, so a registration outlives any restart and lives as long as the key that signed it.

Before `metaform cloud login` keeps anything it names the account that approved the code and, at a terminal, asks the
person to confirm it is theirs; declined, the sign-in is revoked at once. Wrong codes typed on `/device` count against
the source (an IPv4 address, an IPv6 /64) and the signed-in account: ten in ten minutes lock either out for fifteen.

### What the server stores

On disk, on the `auth` volume, `auth.sqlite`: `accounts` (id, name, role, created, disabled, `generation`, and one pending invitation
as its hash and expiry) and `passkeys` (credential id, public key, sign count, transports). The Node's signing keys
are in `keys/` beside it, mode 0600: they are the server's identity, not anyone's data. Nothing else: no maps, memories,
tool arguments or results, no token or grant table, no audit log.

In memory, lost on a restart by design: WebAuthn challenges, page sessions (one hour, each naming the generation it
was opened under, so signing out everywhere ends it too), consent requests, used authorization codes, pending device
sign-ins, the client metadata cache (at most 1,024 documents, least recently used dropped first), the tunnel routing
table, the rate-limit buckets, each account's cached generation and the refresh families' marks. A restart costs every
machine an automatic reconnect, one to five seconds after the broker's `goaway`, and anyone mid-sign-in a retry.

The store is opened as the role the server last ran as (`node/role`, written by `metaform node auth`), so `metaform
node invite`, `signout` and the other account commands run beside a broker open its store the same way; a broker's
store opened over a self-hosted Node's file drops the self-hosted tables, so it never holds more than the accounts and
passkeys (and, with `node_refresh_replay` at `durable`, the `families` marks).

### Tokens

Every token is a JWT signed with the Node's Ed25519 key (EdDSA), named by `kid`, published at
`/.well-known/jwks.json` and named `jwks_uri` in the metadata, and says what it is in `typ`, so one kind is never
taken for another:

| Token | `typ` | Life | Bound to |
|---|---|---|---|
| Host access token | `at+jwt` | 10 minutes | `aud` = the instance's resource URL |
| Machine access token | `at+jwt` | 10 minutes | `aud` = `/cloud/tunnel`, `cnf.jkt` = the machine's key |
| Refresh token | `rt+jwt` | 30 days sliding, 90 days from the approval | the grant (`fam`) and its sequence (`seq`) |
| Authorization code | `code+jwt` | 5 minutes, used once | the PKCE challenge and the redirect URI |
| Per-request assertion | `mf-assert+jwt` | 60 seconds | the account, the instance's resource, the body's hash |

Every token names the account's `generation`. A check is the signature, the type, the issuer, the audience, the
expiry and the generation, with no read of any store per request: each account's generation is read once and kept
for 30 seconds. `metaform node rotate-key` makes a new key; the old one stays published until its tokens expire. A key
that may have been copied is revoked instead with `metaform node rotate-key revoke_old=true`: every older key file is
deleted and leaves the published key set, the running broker reads the change within five seconds with no restart,
and every token signed with an old key, genuine or forged, is refused. The generation is no defence here, since a
forger writes whatever generation it likes; removing the key is what ends a key compromise. Each machine's tunnel
closes on its next check and its refresh is refused, so it stops and asks for `metaform cloud login`; each machine
also replaces its saved key set whole with the one the broker sends in `ready`.

**Revoking.** "Sign out everywhere" on `/account` (the person, with their passkey) or `metaform node signout <name>`
(the operator) moves the generation: every token, session and tunnel of the account fails its next check, and the
broker closes the account's tunnels at once (4003). One grant is revoked with RFC 7009 (`metaform cloud logout` does
it for its machine); that is held in memory while the process runs.

**What is lost without token tables, and why it is acceptable.** OAuth 2.1 asks an authorization server to detect a
refresh token used twice. Each refresh token carries its grant and a sequence number, and the broker keeps, in memory,
the highest number issued per grant: one presented below it is a replay, so the grant is revoked and both holders sign
in again. While the process runs this is exactly OAuth 2.1's rotation detection. Across a restart the marks are gone,
so a refresh token retired before the restart can be redeemed once more, by whoever presents it first; a revocation of
one grant is forgotten the same way. That needs a stolen refresh token and a restart before the thief uses it; the
90-day cap and the passkey bound it, the machine's own refresh token is useless without its DPoP key, and "sign out
everywhere" is durable. A grant forked after a restart (the thief and the holder each refreshing from the same token)
is still caught at the following rotation, by whichever of them refreshes second. An operator who wants detection
across restarts sets `node_refresh_replay` to `durable`, which keeps the same marks (grant ids and counters, no secret)
in a `families` table; set it in the broker's home, as compose does not pass it.

### The tunnel and the broker

The machine opens one WebSocket to `/cloud/tunnel` (subprotocol `metaform-tunnel.1`) with its access token and a DPoP
proof; a request with an `Origin` is refused, so no web page opens one. Each message is one frame: a 4-byte length, a
JSON header, then raw body bytes; the frame types, the header allowlists, credit and the close codes are in the cloud
module's README. Requests are multiplexed by a stream number the broker assigns, never by JSON-RPC id. Pings every 20
seconds; an idle host stream gets an SSE comment every 25 seconds; the machine renews its token in-band before it
expires and reconnects with jittered backoff (1 to 60 seconds).

The broker never forwards the host's token (the MCP security guidance forbids token passthrough). It checks it, then
signs an assertion for that one request: the account, the client, the scopes (the host's, capped by what the machine
allows), the instance's resource URL, the body's SHA-256, valid 60 seconds. The machine checks it against the key set
it saved at login, its own resource URL, the account it signed in as and the body, spends it once, and only then
hands the request to the MCP app, whose bearer check, scope gate and person-only refusals are the ones every exposed
Metaform uses. A misrouted request is refused by the receiver, not run. The machine writes one line per request to
`<home>/cloud/audit.jsonl`: account, client, method, tool or resource, project, outcome, duration, the assertion's id.

**One resource per machine.** `https://metaform.ing/mcp` is the instance named `default`, `/mcp/<instance>` any other,
each with its own Protected Resource Metadata (RFC 9728), so a token approved for one machine is useless at another.
Routing is by (account, instance): two accounts may both have `default`. A newer connection for the same instance
replaces the old one (4009 to it).

**Offline.** A tool call gets a result with `isError: true` saying which machine to run `metaform cloud connect` on, so
the model tells the person; any other request a JSON-RPC error, code -32050, with `data.next`; a notification or a
stream 503 with `Retry-After`. Only then does the broker read a request body.

**Limits** (`broker.Limits`, in memory): 10 requests a second per account with a burst of 30 (429); a 1 MiB request
body (413); an 8 MiB answer that is not a stream; 1 MiB frames; 32 requests open per tunnel (a request waits 10
seconds for one, then 503). Held-open streams, a GET or a POST to `subscriptions/listen` (known by its `Mcp-Method`
header, which the machine refuses if it does not match the body), never take one of those 32: they are counted apart,
8 per account and client and 16 per tunnel (429 beyond), each an hour at most. Credit is enforced at the broker: a
machine may send a stream only the bytes granted it, and is disconnected (4008) for a byte more, so a machine that
ignores credit fills nothing but its own windows; the answers a tunnel holds at once are capped at 16 MiB (502 for
the request that passes it). 5 machines per account; a tunnel connection every 2 seconds per account after a burst of
5.

Before anyone is signed in, each source (an IPv4 address, an IPv6 /64) has its own allowance, spent before the global
ceiling of 200 a second: 20 a minute to the sign-in, consent and device pages and the device endpoint, 600 a minute
to anything else. The token and revocation endpoints are charged differently, since AI hosts call them from a few
addresses for many people: a request naming a refresh token, code or device code this server signed or issued is
charged to that grant (1 a second after a burst of 10), and one naming nothing valid to its source (120 a minute). One
source flooding junk therefore spends only its own allowance, never the refreshes of every account.

**Scopes** are capped twice: at the broker by the Node's capability and the account's role (only the owner may be
granted `mcp:dispatch`, unless `node_member_dispatch`), and on the machine by `cloud_capability` (person-only, `write`
by default). A tool beyond the machine's ceiling is answered 403 `insufficient_scope` saying the owner caps it there.

**ChatGPT.** ChatGPT's connectors and deep research call two tools by exactly these names, so the mcp module serves
`search` and `fetch` itself, read-only, over HTTP and the tunnel (`mcp_search_fetch`, `remote` by default; not over
stdio, where a local agent has the real tools). `search` looks through the map's layer items, the memories (each hit
as the node it is attached to) and the glossaries, and returns `{"results": [{"id", "title", "url"}]}` with
`metaform://` ids; `fetch` reads one as `resources/read` does.

**What runs where.** metaform.ing: `metaform node init metaform.ing --node-role broker` writes Caddy and one service,
`metaform node auth --node-role broker`: the authorization server, the pages, the key set, `/mcp*` and
`/cloud/tunnel` in one process on 127.0.0.1:7435, because the generations, the device codes and the routing table are
shared in memory. No mcp or web service, no project mount, no access log in Caddy or uvicorn. Known limit: one
process; scaling out needs routing by account at the front.

### Threats

| Threat | Handling |
|---|---|
| Stolen host access token | 10 minutes, one instance's resource |
| Stolen host refresh token | rotation with replay detection; 90-day cap; sign out everywhere; the restart gap above |
| Stolen machine credentials file | the DPoP key is in it, so the whole file works, as for an SSH key: mode 0600; `logout` or sign out everywhere ends it; the token without the key does not work |
| Token passthrough, confused deputy | the host's token stops at the broker; the machine accepts only assertions for its own resource, account and body |
| Broker misroutes a request | refused on the machine by `sub` or `aud`, never run |
| Compromised broker | it can call tools as the person within the scopes the machine allows (`cloud_capability`, `write` by default, dispatch never unless raised); every call is in the machine's audit log, signed by the broker; `cloud logout` cuts it |
| Device-code phishing | the page shows the device and instance and warns per RFC 8628 section 5.4; codes live 10 minutes. The result is a tunnel token, so the attacker's machine never reads the person's maps. But approved under the name of an instance the person uses, it takes that instance's place (4009 to the person's machine), and from then on every request the person's AI tools send there, with whatever the person's prompts put in its arguments, goes to the attacker's machine, which can answer with content of its choosing. So when that name is connected the page says so and approval needs a box ticked to replace it, and `/account` and the person's machine (stopped with 4009) both show the change |
| Someone approves a person's code on their own account (a guessed or sent code) | the person's machine would connect to the attacker's account and serve the person's maps to the attacker's AI tools; `metaform cloud login` names the approving account and asks the person to confirm it before keeping anything, and declined revokes the sign-in |
| Someone connects as the person's instance | needs the person's passkey approval; a replacement shows as 4009 on the person's machine and on `/account` |
| User-code guessing | 20^8 codes, 10 minutes; ten wrong in ten minutes lock out the source (an IPv4 address, an IPv6 /64) and the signed-in account that typed them for fifteen minutes |
| Server breach | account names, passkey public keys, generations: nothing that signs anyone in or reads a map. The signing key is what to protect. A rotation alone does not end a copied key, nor does signing everyone out, since a forger chooses the generation: `metaform node rotate-key revoke_old=true` deletes every older key, which leaves the key set at once in the running broker and on each machine at its next connection, and every token it signed, genuine or forged, is refused |
| Clock drift on a person's machine | DPoP proofs and assertion checks use the broker's time, measured from each answer's `Date` header and from `ready`, with 30 seconds of leeway; a request refused for the time alone is answered with a message saying to set the clock, and the tunnel reconnects to measure again |
| A machine that ignores credit or holds streams open | disconnected at the first byte past its credit; held-open streams counted apart from requests; slots given back however a stream ends |
| Token endpoint flooding | junk spends its own source's allowance; requests naming a valid grant are charged to that grant |
| Client metadata fetch (SSRF) | the name is resolved once and the connection made to the address checked public, never resolved again (no DNS rebinding); no redirects, 5 KB, 5 seconds |
| Logs | no bodies, tokens, query strings, tool or instance names in the server's logs |

## Hosted instances on metaform.ing

An alternative to the broker for someone who wants their Metaform itself in the cloud: the same image, one instance
per user (`<name>.metaform.ing`), each with its own authorization server, passkeys,
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
- The broker runs as one process; serving more people than one process holds needs routing by account at the front.
- A self-hosted Node still issues opaque tokens kept as hashes; signed tokens are the broker's alone until agreed for
  every Node.
- A2A through the broker (`/a2a[/<instance>]` over the same tunnel) is not built.
