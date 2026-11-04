# cloud

Reach this Metaform from cloud AI tools, ChatGPT and Claude, through your account at metaform.ing.

## Purpose

The cloud module makes the Metaform on your own machine reachable by AI tools that run in the cloud, such as ChatGPT
and Claude on the web, which cannot start a local MCP server. Your machine signs in to your account at metaform.ing
and dials out to it over one WebSocket, so you open no port. The AI tool signs in to the same account with standard
MCP OAuth and talks MCP to `https://metaform.ing/mcp`. The broker there checks the AI tool's token, keeps it, and
carries each request down your machine's tunnel with a signed statement of who is calling. Your maps, memories and
every tool stay and run on your machine, and the record of who called what is kept on your machine too.

### Using it

1. Install Metaform on the machine that holds your projects.
2. Sign the machine in to your account:

   ```
   metaform cloud login
   ```

   It prints a code and opens `https://metaform.ing/device`. Sign in there with your passkey, check that the code
   matches the one in your terminal, and approve. Approve only a code you started yourself, just now.
3. Open the tunnel, and leave it running:

   ```
   metaform cloud connect
   ```

   Or turn on `cloud_autoconnect` (`metaform set --cloud-autoconnect`), and `metaform web start` starts it beside the
   page.
4. In ChatGPT or Claude, add a custom connector (an MCP server) at `https://metaform.ing/mcp`. The AI tool opens the
   metaform.ing sign-in: your passkey, then Allow.

`metaform cloud status` shows the account, the instance, whether the tunnel is up, and the URL to give an AI tool.
If the machine is off or the tunnel is down, the AI tool is told so in a message its model reads: "Your Metaform
named default is not connected. On that machine run: metaform cloud connect".

**More than one machine.** Give each machine its own instance name before it signs in
(`metaform set --cloud-instance laptop`, then `metaform cloud login`). The machine named `default` is at
`https://metaform.ing/mcp`; any other is at `https://metaform.ing/mcp/<name>`. An AI tool approved for one machine
cannot reach another. A second machine that signs in under a name already connected takes its place, and the first
stops and says so.

### What to trust, said plainly

- metaform.ing keeps your account and your passkeys' public keys, nothing else: no maps, memories, tool arguments or
  results, tokens or log of calls.
- The broker is trusted to say who is calling. A broker that misbehaved could call tools as you, up to the ceiling
  you set here with `cloud_capability` (`write` by default, so it could never start agents unless you raise it to
  `dispatch`). Every call it carried is in this machine's audit log, signed by the broker.
- `metaform cloud logout` ends this machine's sign-in. "Sign out everywhere" on `https://metaform.ing/account` ends
  every AI tool's access, every machine's tunnel and every page session of the account at once.
- The credentials file holds the key that this machine's tokens are bound to: a copy of the whole file works, as for
  an SSH key. It is readable by you alone; `logout` or "Sign out everywhere" ends it.

## Template version

The template changelog version this module started from: 0.2.0.

## Declaration

`SUPPORTED_OS = ('linux', 'macos', 'windows')`; `DEPENDENCIES = ('mcp>=2.2,<3', 'httpx>=0.28,<1', 'websockets>=13',
'pyjwt[crypto]>=2.10')`; `SHIPS_DISABLED = False`. Every verb is on the command line only (`surfaces=('cli',)`): none
is a tool an agent can call.

## Common base used

`metaform.module` for the declaration, `Context`, `Stop` and `child_environment`; `metaform.settings` for its
settings; `metaform.home` for the home's `cloud/` folder.

## Prompts

`resources/prompts.xml` holds the four standard elements, all empty: no cloud verb is offered to agents.

## Verbs

- `login`: the OAuth 2.0 device authorization grant (RFC 8628) as the built-in client `metaform-cli`, with a key pair
  made here and DPoP proofs (RFC 9449) on every request, so the tokens are bound to the key. Saves
  `<home>/cloud/credentials.json`, mode 0600: the issuer, the account, the instance, the refresh token, the DPoP
  private key, and the broker's key set fetched over TLS. Access tokens are kept in memory only.
- `connect`: the tunnel (`transport=True`, runs until stopped). Builds the same MCP app `metaform mcp serve --http`
  serves (`mcp.server.http_app`) and runs it in-process; nothing listens on any address. Renews its token in-band
  before it expires; reconnects with jittered backoff from one second to a minute; stops, saying why, when the account
  signed out everywhere or this sign-in was revoked, and when a newer connection for the same instance took its place.
- `status`: the account, the instance, the tunnel's state and the URL to give an AI tool.
- `logout`: revokes the refresh token at the broker (RFC 7009) and deletes the credentials file.
- `audit [lines=]`: the latest lines of the local audit log.

## Settings

All global:

- `cloud_url` (`https://metaform.ing`): the broker; plain `http` is accepted only for a broker on this machine.
- `cloud_instance` (`default`): this machine's name in the account.
- `cloud_capability` (`read`, `write`, `dispatch`; `write`): the most a cloud AI tool may do here, whatever it was
  granted at sign-in. A tool needing more is answered 403 `insufficient_scope`, saying the owner caps it here.
- `cloud_audit` (`names`, `full`; `names`): whether the audit log keeps tool arguments too. Results are never kept.
- `cloud_autoconnect` (off): `metaform web start` starts `metaform cloud connect` beside the page.

## Events

Subscribes to `web.started`: with `cloud_autoconnect` on and this machine signed in, starts `metaform cloud connect`
detached, unless one is already running. Publishes nothing.

## Sync and async

`login`, `logout`, `status` and `audit` are synchronous. `connect` runs an asyncio loop of its own: the tunnel, one
task per request the broker opens, and the MCP app's lifespan.

## Layers

None. What it keeps is in the home, not in any project: `cloud/credentials.json`, `cloud/audit.jsonl` (rotated at 10
MiB, five older files kept) and `cloud/connect.json`, the tunnel's state for `status`, beside `cloud/connect.lock`, which a running `connect` holds locked, so `status` reads a connection whose process ended as not running.

## Lifecycle and cleanup

No `start` or `stop`. `logout` deletes the credentials. `metaform disable cloud` turns the whole path off: nothing of
it loads.

## Modules relied on

mcp: the tunnel serves `mcp.server.http_app` and checks the broker's assertions with `mcp.oauth.Asserted`, so the
mcp module's scope gate and tools apply as they do over HTTP. The broker's side is the node
module's broker role (`node/broker.py`), which reads this module's wire format, `frames.py`.

## Systems supported

`linux`, `macos` and `windows`. On Windows the credentials file is protected by the profile's permissions rather than
its mode.

## Resources owned

`<home>/cloud/`. No port.

## Installed and direct wheel

The same in both.

## Demonstration

```
metaform cloud login
metaform cloud connect
metaform cloud status
```

## Files

`login.py` the device grant, DPoP and the credentials file; `tunnel.py` the connection, the bridge from frames to the
MCP app, and reconnecting; `frames.py` the wire format, shared with the broker; `audit.py` the local record.

## The tunnel's wire format

One WebSocket to `wss://metaform.ing/cloud/tunnel`, subprotocol `metaform-tunnel.1`, opened with
`Authorization: DPoP <access token>` and a `DPoP` proof. Each message is one binary frame: a 4-byte big-endian length,
a JSON header, then the body's raw bytes. The broker numbers a stream per HTTP request from a host; JSON-RPC ids are
the hosts' own and collide across hosts, so they never key anything.

| type | from | header | body |
|---|---|---|---|
| `hello` | machine | `version`, `instance`, `allows` (scopes this machine grants) | none |
| `ready` | broker | `account`, `instance`, `resource`, `limits`, `now` (the broker's time), `keys` (its key set) | none |
| `auth` | machine | `token`, `proof`: a fresh access token before expiry | none |
| `open` | broker | `stream`, `method`, `path`, `query`, `headers` (allowlisted), `assertion` | the request body |
| `head` | machine | `stream`, `status`, `headers` (allowlisted) | none |
| `data` | machine | `stream` | response bytes, SSE events included |
| `end` | machine | `stream`, `error` | none |
| `cancel` | both | `stream`, `reason` | none |
| `credit` | broker | `stream`, `bytes` | none |
| `goaway` | broker | `reason`, `reconnect_after_ms` | none |

Headers carried: to the machine `content-type`, `accept`, `mcp-method`, `mcp-name`, `mcp-protocol-version`,
`mcp-session-id`, `last-event-id`; back `content-type`, `cache-control`, `www-authenticate` and `mcp-*`. Never
`authorization`, cookies, `host`, `origin` or forwarding headers. Credit: 256 KiB per stream to start, given back as the
host reads; the broker enforces it, and a machine that sends a byte past it is disconnected (4008). Close codes: 4001
token no longer valid, or its signing key revoked (refresh and reconnect), 4003 signed out everywhere or revoked
(stop; log in again), 4008 frame too large or data past the credit granted, 4009 replaced by a newer connection for the
instance (stop), 4029 too many connections (back off), 1012 broker restarting (reconnect after `goaway`'s delay, or a
random one to five seconds without one). Pings every 20 seconds.

`ready` carries the broker's key set, which replaces the one saved at login whole, so a key the broker revoked stops
being trusted here at once, and the broker's time: this machine judges assertions, and dates its DPoP proofs, on the
broker's clock (also measured from each answer's `Date` header), with 30 seconds of leeway, so a laptop or WSL clock
that is off still connects. A request refused for its time alone is answered with a message, through the AI tool, to
set the clock, and the tunnel reconnects to measure again.

`metaform cloud login` names the account that approved the code and, at a terminal, asks whether it is the person's
own before keeping anything: a code approved from another account would connect this machine, and its maps, to that
account. Declined, the sign-in is revoked and nothing is kept.
