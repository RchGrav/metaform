"""The Metaform Node's deployment, as files: what `metaform node init` writes for one domain.

One image serves every mode; only this configuration changes:

- `acme`: a public host; Caddy obtains the certificate from Let's Encrypt (HTTP-01 or TLS-ALPN-01).
- `dns`: the certificate through the DNS provider's API (DNS-01), optionally a wildcard for a managed domain whose
  instances share it, through Caddy's `caddy-dns` modules; the token is in `secrets.env` on the host, never here.
- `relay`: no open port; frpc carries the TLS stream to a relay that routes by SNI without terminating it, and the
  certificate is obtained through that passthrough with TLS-ALPN-01, so its key never leaves the instance.
- `internal`: Caddy's own local CA, for a stand-in on a test machine; never for a public name.

A Node has one of two roles. `node`, the default, serves a Metaform of its own: its maps, MCP, A2A and the page. `broker`
is metaform.ing's: it serves no Metaform at all, only accounts, sign-in and the broker that carries AI hosts' MCP to the
Metaform on each person's own machine (broker.py), so it runs Caddy and one process and mounts no project.

Every Metaform process binds 127.0.0.1 inside one network namespace, Caddy's, so only Caddy is reachable. Discovery
and sign-in answer before any credential; `/mcp` and A2A check their own bearer tokens; the page passes the
authorization server's session gate first. The later one-port service mounts the same pieces in one ASGI app, so
the routes below stay as they are and only the upstreams merge.
"""
from __future__ import annotations

import ipaddress
import json
import re
import secrets
import time
from dataclasses import dataclass, field
from hashlib import sha256
from pathlib import Path, PurePosixPath
from typing import Any, cast

# Pinned by digest, so a host builds exactly what was tested; `node update` is where they move.
CADDY_IMAGE = 'caddy:2.11.7-alpine@sha256:d8542f48d34a9cf4e4c11a478865229840e87e4c96ea3f439101f31a5d35f75f'
CADDY_BUILDER = 'caddy:2.11.7-builder-alpine@sha256:aa705b1e8e4bce41a7a30de934c1e00f6821667c1d1206424465065c92cb7674'
PYTHON_IMAGE = 'python:3.13.13-slim-trixie@sha256:aa938a849bcb82dce8f49480f056ab82bf5c1c3ebc294f0430f37b6820e7f286'
FRPC_IMAGE = 'fatedier/frpc:v0.71.0@sha256:99ece6a2b62cfc68731e0df289af804ff1c699911cfc47871856434f1d6d53ee'
FRPS_IMAGE = 'fatedier/frps:v0.71.0@sha256:cd8b947ba61678b200baa4f71ccc33f3c52e4e2cc0059700ba3b8354e36af7c3'
IMAGE = 'metaform-node:local'  # built on the host from the wheel beside the Dockerfile; never pushed

WEB_PORT, MCP_PORT, AUTH_PORT, GATE_PORT = 7433, 7434, 7435, 7440
TWILIO_PORT = 7441  # the twilio module's phone bridge, `metaform twilio serve`, when the person runs it here
UID = 10001
HOME_IN_IMAGE = '/data/home'
AUTH_IN_IMAGE = '/data/auth'  # the auth volume: accounts, passkeys and keys, mounted into the auth container only
PROJECTS_IN_IMAGE = '/srv/projects'
# The per-deploy secret Caddy adds to every request it hands the page, after the gate, so the page server trusts the
# account headers only from Caddy. Written once beside compose.yaml and given to caddy and web only, as env_file.
GATE_FILE = 'gate.env'
GATE_SECRET = 'METAFORM_GATE_SECRET'
MODES = ('acme', 'dns', 'relay', 'internal')
ROLES = ('node', 'broker')
CAPABILITIES = ('read', 'write', 'dispatch')
INVITE_DAYS = 7
LABEL = re.compile(r'^(?!-)[a-z0-9-]{1,63}(?<!-)$')
# Names a relay never hands out: its own, and the ones people expect to belong to the operator.
RESERVED = frozenset({'www', 'relay', 'api', 'mail', 'admin', 'root', 'auth', 'login', 'status', 'docs', 'node'})


@dataclass(frozen=True)
class NodeSpec:
    """One Node: its public name and how it is reached, its capability level, and the folders it serves."""
    domain: str
    mode: str = 'acme'
    email: str = ''
    capability: str = 'write'
    projects: tuple[str, ...] = ()
    dns_provider: str = ''
    wildcard: str = ''
    relay_server: str = ''
    relay_port: int = 7000
    relay_name: str = ''
    dcr: bool = False
    owner: str = 'owner'
    role: str = 'node'
    extra: dict[str, Any] = field(default_factory=dict[str, Any])

    @property
    def issuer(self) -> str:
        return f'https://{self.domain}'


def hostname(name: str) -> bool:
    if not name or len(name) > 253 or name.endswith('.'):
        return False
    try:
        ipaddress.ip_address(name)
        return False  # an address cannot hold a certificate from a public CA or a passkey's relying party id
    except ValueError:
        pass
    labels = name.split('.')
    return len(labels) >= 2 and all(LABEL.match(label) for label in labels)


def problems(spec: NodeSpec) -> list[str]:
    """Everything that stops this Node from being served safely, each a sentence; empty when it can be written."""
    found: list[str] = []
    domain = spec.domain.lower()
    if spec.mode not in MODES:
        found.append(f'The mode must be one of {", ".join(MODES)}, not {spec.mode!r}.')
    if spec.mode != 'internal' and not hostname(domain):
        found.append(f'{spec.domain!r} is not a public host name: the Node needs one for its certificate and for '
                     'passkeys, whose relying party is the name.')
    if spec.mode == 'internal' and not (hostname(domain) or domain == 'localhost'):
        found.append(f'{spec.domain!r} is not a host name.')
    if spec.mode in ('acme', 'dns', 'relay') and '@' not in spec.email:
        found.append('An email address is needed for the certificate authority account (Let\'s Encrypt), so it can '
                     'warn before a certificate lapses.')
    if spec.capability not in CAPABILITIES:
        found.append(f'The capability must be one of {", ".join(CAPABILITIES)}, not {spec.capability!r}.')
    if spec.mode == 'dns' and not re.fullmatch(r'[a-z0-9_]+', spec.dns_provider or ''):
        found.append('DNS mode needs the DNS provider, the caddy-dns module name such as cloudflare or vultr.')
    if spec.wildcard and (spec.mode != 'dns' or not domain.endswith('.' + spec.wildcard.lower())):
        found.append('A wildcard certificate is obtained by DNS only, for a base the domain is one name under.')
    if spec.mode == 'relay':
        if not spec.relay_server or not hostname(spec.relay_server.lower()):
            found.append('Relay mode needs the relay server\'s host name.')
        name = spec.relay_name.lower()
        if not LABEL.match(name) or name in RESERVED:
            found.append(f'{spec.relay_name!r} cannot be a name on the relay.')
        elif not domain.startswith(name + '.'):
            found.append(f'On a relay the domain is the name under the relay\'s domain, {name}.<relay domain>.')
    if spec.mode != 'relay' and spec.capability == 'dispatch':
        pass  # a VM of its own is the operator's rule for dispatch; a self-hoster's host is already theirs
    for folder in spec.projects:
        path = PurePosixPath(folder)
        if not path.is_absolute() or '..' in path.parts or len(path.parts) < 2:
            found.append(f'Project folder {folder!r} must be an absolute path on the host, below the root.')
    names = [PurePosixPath(folder).name for folder in spec.projects]
    if len(set(names)) != len(names):
        found.append('Two project folders share a name; each is mounted under /srv/projects/<name>.')
    if spec.role not in ROLES:
        found.append(f'The role must be one of {", ".join(ROLES)}, not {spec.role!r}.')
    if spec.role == 'broker' and spec.mode == 'relay':
        found.append('A broker is the public end machines dial; it cannot itself sit behind a relay.')
    if spec.role == 'broker' and spec.projects:
        found.append('A broker serves no project: the maps stay on each person\'s own machine.')
    if not LABEL.match(spec.owner.lower()):
        found.append(f'{spec.owner!r} cannot be an account name: lowercase letters, digits and hyphens.')
    return found


# Every scope the Node knows; what an instance grants of them is its capability's, scopes_for.
KNOWN_SCOPES = ('mcp:read', 'mcp:write', 'mcp:dispatch', 'a2a:tickets')


def scopes_for(capability: str) -> dict[str, tuple[str, ...]]:
    """What the authorization server can grant at a capability level, by resource. dispatch is the only level at
    which agents with shells and file writes can be started, so its scope exists only there."""
    mcp = ['mcp:read']
    a2a: list[str] = []
    if capability in ('write', 'dispatch'):
        mcp.append('mcp:write')
        a2a.append('a2a:tickets')
    if capability == 'dispatch':
        mcp.append('mcp:dispatch')
    return {'mcp': tuple(mcp), 'a2a': tuple(a2a)}


def page_classes(capability: str, role: str) -> tuple[str, ...]:
    """The classes of page route an account may use, which the gate hands the page server, as scopes_for grants MCP's:
    every signed-in account reads; write, which changes the map, its tickets and memories, only at the write or
    dispatch capability, as mcp:write; dispatch, which starts and steers agents, only at the dispatch capability, as
    mcp:dispatch; admin (settings, the page's arrangement and workspaces, modules, prompts, bases, removing or clearing
    a project, builds) only for the owner."""
    allowed = ['read']
    if capability in ('write', 'dispatch'):
        allowed.append('write')
    if capability == 'dispatch':
        allowed.append('dispatch')
    if role == 'owner':
        allowed.append('admin')
    return tuple(allowed)


# ---------------------------------------------------------------------------------------------------- the files

BROKER_ROUTES = """
	# Everything the broker answers is one process on 127.0.0.1: the authorization server and its pages, the key set,
	# the AI hosts' MCP endpoint with each instance's resource metadata, and the machines' tunnel. Streams are flushed
	# as they come. Caddy writes no access log here: what passes is nobody's to keep.
	@broker path /.well-known/oauth-authorization-server /.well-known/oauth-authorization-server/* /.well-known/oauth-protected-resource/* /.well-known/jwks.json /oauth/* /node/* /device /account /account/* /mcp /mcp/* /cloud/*
	handle @broker {{
		reverse_proxy 127.0.0.1:{port} {{
			flush_interval -1
		}}
	}}
	handle {{
		respond "Metaform. Sign in to your account at /account; AI tools connect at /mcp." 200
	}}
"""


def caddyfile(spec: NodeSpec) -> str:
    domain = spec.domain.lower()
    protocols = 'h1 h2' if spec.mode == 'relay' else 'h1 h2 h3'  # a relay carries TCP only
    globals_ = ['\temail {$ACME_EMAIL}' if spec.mode != 'internal' else '\tlocal_certs',
                '\tadmin off', f'\tservers {{\n\t\tprotocols {protocols}\n\t}}']
    tls = {'acme': '',
           'dns': '\ttls {\n\t\tdns ' + spec.dns_provider + ' {env.DNS_API_TOKEN}\n\t}\n',
           'relay': '\ttls {\n\t\tissuer acme {\n\t\t\tdisable_http_challenge\n\t\t}\n\t}\n',
           'internal': '\ttls internal\n'}[spec.mode]
    site = f'{domain} {{\n{tls}\timport metaform_node\n}}\n'
    if spec.role == 'broker':
        body = BROKER_ROUTES.format(port=AUTH_PORT)
        return f"""# The Metaform broker's front door, written by metaform node init for {domain}. Caddy terminates TLS and
# routes to the one broker process on 127.0.0.1.
{{
{chr(10).join(globals_)}
}}

(metaform_node) {{
	header {{
		Strict-Transport-Security "max-age=63072000"
		X-Content-Type-Options nosniff
		Referrer-Policy no-referrer
		-Server
	}}{body}}}

{site}"""
    if spec.wildcard:  # one certificate for every name under the base, this instance answering for its own
        site = (f'*.{spec.wildcard.lower()} {{\n{tls}\t@this host {domain}\n\thandle @this {{\n'
                f'\t\timport metaform_node\n\t}}\n\thandle {{\n\t\tabort\n\t}}\n}}\n')
    return f"""# The Metaform Node's front door, written by metaform node init for {domain}. Caddy terminates TLS and
# routes; every Metaform process listens on 127.0.0.1 in this container's network namespace.
{{
{chr(10).join(globals_)}
}}

(metaform_node) {{
	header {{
		Strict-Transport-Security "max-age=63072000"
		X-Content-Type-Options nosniff
		Referrer-Policy no-referrer
		-Server
	}}
	# Discovery and sign-in answer before any credential: the authorization server's metadata and endpoints and its
	# passkey pages.
	@authorization path /.well-known/oauth-authorization-server /.well-known/oauth-authorization-server/* /oauth/* /node/*
	handle @authorization {{
		reverse_proxy 127.0.0.1:{AUTH_PORT}
	}}
	# MCP and A2A check their own bearer tokens and answer their metadata and the public Agent Card unauthenticated.
	@protocols path /mcp /mcp/* /.well-known/oauth-protected-resource /.well-known/oauth-protected-resource/* /a2a /a2a/* /.well-known/agent-card.json
	handle @protocols {{
		reverse_proxy 127.0.0.1:{MCP_PORT} {{
			flush_interval -1
		}}
	}}
	# The twilio module's phone bridge, while it runs: Twilio's webhooks and the call's audio stream. Twilio has no
	# sign-in, so no session gate: the bridge checks Twilio's signature on every request, and accepts only the owner's
	# numbers.
	@twilio path /phone/*
	handle @twilio {{
		reverse_proxy 127.0.0.1:{TWILIO_PORT} {{
			flush_interval -1
		}}
	}}
	# The page, only behind the authorization server's session: a request from another site's page is refused. Who
	# is calling is said only by the gate: what a client sent under its header names is dropped first, the gate's
	# account, role and route classes are copied in, and the per-deploy secret tells the page server the request came
	# through here. Host and Origin reach the page server as the browser sent them; it checks them against its public
	# origin.
	handle {{
		route {{
			@foreign {{
				header Origin *
				not header Origin https://{domain}
			}}
			respond @foreign 403
			request_header -X-Metaform-Account
			request_header -X-Metaform-Role
			request_header -X-Metaform-Classes
			request_header -X-Metaform-Gate
			forward_auth 127.0.0.1:{AUTH_PORT} {{
				uri /node/gate
				copy_headers X-Metaform-Account X-Metaform-Role X-Metaform-Classes
			}}
			reverse_proxy 127.0.0.1:{WEB_PORT} {{
				header_up X-Metaform-Gate {{env.{GATE_SECRET}}}
				flush_interval -1
			}}
		}}
	}}
}}

{site}"""


def dockerfile() -> str:
    return f"""# syntax=docker/dockerfile:1
# The Metaform Node image: Metaform from the wheel beside this file, as an unprivileged user, the home on a volume.
FROM {PYTHON_IMAGE}
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1 \\
    METAFORM_HOME={HOME_IN_IMAGE}
RUN groupadd --system --gid {UID} metaform \\
 && useradd --system --uid {UID} --gid metaform --home-dir /data --shell /usr/sbin/nologin metaform \\
 && apt-get update && apt-get install --yes --no-install-recommends git \\
 && rm -rf /var/lib/apt/lists/*
COPY wheels/ /tmp/wheels/
# constraints.txt holds the versions node deploy built and tested with, so the host resolves the same ones.
RUN if [ -f /tmp/wheels/constraints.txt ]; then set -- --constraint /tmp/wheels/constraints.txt; fi \\
 && pip install --root-user-action=ignore "$@" /tmp/wheels/*.whl && rm -rf /tmp/wheels \\
 && mkdir -p {HOME_IN_IMAGE} {AUTH_IN_IMAGE} {PROJECTS_IN_IMAGE} && chown -R metaform:metaform /data {PROJECTS_IN_IMAGE}
USER metaform
WORKDIR {PROJECTS_IN_IMAGE}
VOLUME ["{HOME_IN_IMAGE}"]
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \\
    CMD ["python", "-m", "metaform.modules.node.health"]
ENTRYPOINT ["metaform"]
"""


def caddy_dockerfile(spec: NodeSpec) -> str:
    """Caddy with the DNS provider's module, for DNS-01; xcaddy is Caddy's own way to add a module."""
    return f"""# Caddy with github.com/caddy-dns/{spec.dns_provider}, for certificates through the DNS provider's API.
FROM {CADDY_BUILDER} AS builder
RUN xcaddy build --with github.com/caddy-dns/{spec.dns_provider}
FROM {CADDY_IMAGE}
COPY --from=builder /usr/bin/caddy /usr/bin/caddy
"""


def _service(command: list[str], service: str, *, mounts: list[str], entrypoint: list[str] | None = None,
             depends: bool = True) -> dict[str, Any]:
    made: dict[str, Any] = {
        'image': IMAGE, 'restart': 'unless-stopped', 'network_mode': 'service:caddy', 'command': command,
        'environment': {'METAFORM_NODE_SERVICE': service}, 'volumes': ['home:' + HOME_IN_IMAGE, *mounts],
        'read_only': True, 'tmpfs': ['/tmp'], 'cap_drop': ['ALL'], 'security_opt': ['no-new-privileges:true']}
    if entrypoint:
        made['entrypoint'] = entrypoint
    if depends:
        made['depends_on'] = {'auth': {'condition': 'service_healthy'}}
    return made


def compose(spec: NodeSpec) -> dict[str, Any]:
    """The compose project: Caddy owns the network namespace and is the only service with ports; auth, mcp and web
    share it and bind 127.0.0.1. The accounts are on the `auth` volume, which only auth mounts; the gate secret is
    given to caddy and web only."""
    domain = spec.domain.lower()
    projects = [f'{folder}:{PROJECTS_IN_IMAGE}/{PurePosixPath(folder).name}' for folder in spec.projects]
    caddy: dict[str, Any] = {
        'image': CADDY_IMAGE, 'restart': 'unless-stopped',
        'environment': {'ACME_EMAIL': spec.email},
        'volumes': ['./Caddyfile:/etc/caddy/Caddyfile:ro', 'caddy-data:/data', 'caddy-config:/config'],
        'cap_drop': ['ALL'], 'cap_add': ['NET_BIND_SERVICE'], 'security_opt': ['no-new-privileges:true']}
    if spec.mode == 'dns':
        caddy.pop('image')
        caddy['build'] = {'context': './caddy'}
        caddy['image'] = f'metaform-node-caddy-{spec.dns_provider}:local'
        caddy['env_file'] = [{'path': './secrets.env', 'required': True}]
    if spec.mode != 'relay':
        caddy['ports'] = ['80:80', '443:443', '443:443/udp']
    public = f'https://{domain}'
    auth = _service(['node', 'auth', '--node-domain', domain, '--node-capability', spec.capability,
                     *(['--node-dcr'] if spec.dcr else []), *(['--node-role', 'broker'] if spec.role == 'broker' else [])],
                    'auth', mounts=['auth:' + AUTH_IN_IMAGE, './bootstrap:/run/metaform-bootstrap:ro'], depends=False)
    auth['environment']['METAFORM_NODE_AUTH'] = AUTH_IN_IMAGE
    auth['build'] = {'context': '.'}
    volumes: dict[str, Any] = {'home': {}, 'auth': {}, 'caddy-data': {}, 'caddy-config': {}}
    if spec.role == 'broker':  # no Metaform is served here: no mcp, no page, no project
        return {'name': 'metaform-node', 'services': {'caddy': caddy, 'auth': auth}, 'volumes': volumes}
    gate = {'path': './' + GATE_FILE, 'required': True}
    caddy['env_file'] = [*caddy.get('env_file', []), gate]
    mcp = _service(['mcp', 'serve', '--http', '--mcp-port', str(MCP_PORT), '--mcp-bind', '127.0.0.1',
                    '--mcp-public-url', public], 'mcp', mounts=projects)
    if spec.capability != 'dispatch':
        # Below dispatch no agent is started here: the dispatch module is off before the server starts, and the
        # authorization server never grants mcp:dispatch.
        mcp['entrypoint'] = ['sh', '-c', 'metaform disable dispatch >/dev/null 2>&1; exec metaform "$@"', 'metaform']
    web = _service(['--bind', '127.0.0.1', '--port', str(WEB_PORT), '--nonce', 'node', '--origin', public], 'web',
                   mounts=projects, entrypoint=['python', '-m', 'metaform.modules.web.server'])
    web['env_file'] = [gate]
    services: dict[str, Any] = {'caddy': caddy, 'auth': auth, 'mcp': mcp, 'web': web}
    if spec.mode == 'relay':
        services['frpc'] = {
            'image': FRPC_IMAGE, 'restart': 'unless-stopped', 'network_mode': 'service:caddy',
            'command': ['-c', '/etc/frp/frpc.toml'], 'volumes': ['./frpc.toml:/etc/frp/frpc.toml:ro'],
            'env_file': [{'path': './secrets.env', 'required': True}],
            'read_only': True, 'cap_drop': ['ALL'], 'security_opt': ['no-new-privileges:true']}
    return {'name': 'metaform-node', 'services': services, 'volumes': volumes}


def frpc_toml(spec: NodeSpec) -> str:
    """The tunnel client: it dials the relay, so nothing on the user's side listens on the internet. The relay routes
    `https` proxies by SNI and passes the stream through; the enrolment secret comes from secrets.env."""
    name = spec.relay_name.lower()
    return f"""# frp client for the Metaform relay, written by metaform node relay. It carries TLS for {spec.domain}
# to Caddy here; the relay reads only the server name to route it.
serverAddr = "{spec.relay_server.lower()}"
serverPort = {spec.relay_port}
loginFailExit = false
user = "{name}"
metadatas.token = "{{{{ .Envs.METAFORM_RELAY_TOKEN }}}}"
transport.tls.enable = true

[[proxies]]
name = "node"
type = "https"
localIP = "127.0.0.1"
localPort = 443
subdomain = "{name}"
"""


def owner_invite(spec: NodeSpec, now: float | None = None) -> tuple[str, dict[str, Any]]:
    """The owner's one-time setup secret and the record the authorization server imports on its first start: only
    its hash travels to the host, and the link carries the secret in its fragment, which no server logs."""
    secret = secrets.token_urlsafe(32)
    record = {'account': spec.owner.lower(), 'role': 'owner', 'sha256': sha256(secret.encode()).hexdigest(),
              'expires': (now or time.time()) + INVITE_DAYS * 86400}
    return secret, record


def setup_link(issuer: str, secret: str) -> str:
    return f'{issuer}/node/setup#invite={secret}'


def node_env(spec: NodeSpec) -> str:
    """What the compose project was made for, kept beside it so status, logs and update need nothing else."""
    return json.dumps({'domain': spec.domain.lower(), 'mode': spec.mode, 'capability': spec.capability,
                       'projects': list(spec.projects), 'relay_server': spec.relay_server,
                       'relay_name': spec.relay_name, 'dns_provider': spec.dns_provider, 'wildcard': spec.wildcard,
                       'email': spec.email, 'dcr': spec.dcr, 'owner': spec.owner, 'role': spec.role},
                      indent=2) + '\n'


def spec_from(folder: Path) -> NodeSpec:
    data = json.loads((folder / 'node.json').read_text(encoding='utf-8'))
    return NodeSpec(domain=data['domain'], mode=data['mode'], email=data.get('email', ''),
                    capability=data['capability'], projects=tuple(data.get('projects', ())),
                    dns_provider=data.get('dns_provider', ''), wildcard=data.get('wildcard', ''),
                    relay_server=data.get('relay_server', ''), relay_name=data.get('relay_name', ''),
                    dcr=bool(data.get('dcr')), owner=data.get('owner', 'owner'), role=data.get('role', 'node'))


COMPOSE_HEAD = ('# The Metaform Node, written by metaform node init. Caddy is the only service with ports; the others share\n'
                '# its network namespace and listen on 127.0.0.1. Start it with: docker compose up -d --build\n')


def to_yaml(value: Any, indent: int = 0) -> str:
    """Block YAML for plain data, every string double-quoted as JSON writes it, which YAML reads the same way, so no
    value is ever taken for a number, a boolean or a null by accident."""
    pad = '  ' * indent
    if isinstance(value, dict):
        if not value:
            return '{}\n'
        lines: list[str] = []
        for key, item in cast(dict[str, Any], value).items():
            if isinstance(item, (dict, list)) and item:
                lines.append(f'{pad}{key}:\n' + to_yaml(item, indent + 1))
            else:
                lines.append(f'{pad}{key}: ' + to_yaml(item, indent + 1).strip() + '\n')
        return ''.join(lines)
    if isinstance(value, list):
        if not value:
            return '[]\n'
        lines = []
        for item in cast(list[Any], value):
            if isinstance(item, dict) and item:
                body = to_yaml(item, indent + 1)
                lines.append(f'{pad}- ' + body[len(pad) + 2:])
            else:
                lines.append(f'{pad}- ' + to_yaml(item, indent + 1).strip() + '\n')
        return ''.join(lines)
    if isinstance(value, bool):
        return 'true' if value else 'false'
    if isinstance(value, int):
        return str(value)
    return json.dumps(str(value))


def files(spec: NodeSpec, invite: dict[str, Any] | None) -> dict[str, str]:
    """Every file of the compose project, by path relative to its folder."""
    made = {'compose.yaml': COMPOSE_HEAD + to_yaml(compose(spec)), 'Caddyfile': caddyfile(spec), 'Dockerfile': dockerfile(),
            'node.json': node_env(spec), '.dockerignore': '*\n!wheels/\n'}
    if spec.mode == 'dns':
        made['caddy/Dockerfile'] = caddy_dockerfile(spec)
    if spec.mode == 'relay':
        made['frpc.toml'] = frpc_toml(spec)
    if invite is not None:
        made['bootstrap/owner-invite.json'] = json.dumps(invite, indent=2) + '\n'
    else:
        made['bootstrap/.keep'] = ''
    return made
