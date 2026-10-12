"""The relay: how a Metaform with no open port is reached at `<name>.<relay domain>`, and the operator's side of it.

The tunnel is frp (https://github.com/fatedier/frp, Apache-2.0): the instance's frpc dials the relay's frps, and
frps routes each incoming TLS connection by the server name in its ClientHello to that instance's tunnel without
terminating it (frp's `https` proxy type), so the relay holds no certificate and reads nothing. The instance's Caddy
obtains its own certificate through the same passthrough with ACME TLS-ALPN-01, whose challenge is answered in the
TLS handshake on port 443 for the very name being routed; HTTP-01 would need the relay to proxy plain HTTP, and
DNS-01 would need the instance to hold a DNS credential for the operator's zone.

frps itself authenticates no one per user; its server plugin does: on each Login and NewProxy frps asks the gate
here, which admits a client only with the enrolment secret the operator issued for that name, and a proxy only for
`https` on that same name. One secret per name, kept as its hash, so a leaked file enrols nobody.
"""
from __future__ import annotations

import json
import time
from hashlib import sha256
from pathlib import Path
from typing import Any, cast

from .authstore import made
from .config import FRPS_IMAGE, GATE_PORT, IMAGE, LABEL, RESERVED, to_yaml

CONTROL_PORT = 7000


def frps_toml(domain: str) -> str:
    return f"""# frp server for the Metaform relay at *.{domain}, written by metaform node relay-init. It routes TLS by
# server name and never terminates it; the gate admits each client by its enrolment.
bindPort = {CONTROL_PORT}
vhostHTTPSPort = 443
subDomainHost = "{domain}"
transport.tls.force = true
log.to = "console"

[[httpPlugins]]
name = "metaform-relay-gate"
addr = "127.0.0.1:{GATE_PORT}"
path = "/frp"
ops = ["Login", "NewProxy"]
"""


def operator_compose(domain: str) -> dict[str, Any]:
    """frps and the gate, the gate on loopback in frps's network namespace; 443 and the control port open."""
    return {'name': 'metaform-relay', 'services': {
        'frps': {'image': FRPS_IMAGE, 'restart': 'unless-stopped', 'command': ['-c', '/etc/frp/frps.toml'],
                 'ports': ['443:443', f'{CONTROL_PORT}:{CONTROL_PORT}'],
                 'volumes': ['./frps.toml:/etc/frp/frps.toml:ro'], 'read_only': True, 'cap_drop': ['ALL'],
                 'cap_add': ['NET_BIND_SERVICE'], 'security_opt': ['no-new-privileges:true']},
        'gate': {'image': IMAGE, 'build': {'context': '.'}, 'restart': 'unless-stopped',
                 'network_mode': 'service:frps', 'command': ['node', 'relay-gate', '--node-relay-domain', domain],
                 'environment': {'METAFORM_NODE_SERVICE': 'gate'}, 'volumes': ['relay:/data/home'],
                 'read_only': True, 'tmpfs': ['/tmp'], 'cap_drop': ['ALL'],
                 'security_opt': ['no-new-privileges:true']}},
        'volumes': {'relay': {}}}


def operator_files(domain: str) -> dict[str, str]:
    from .config import dockerfile
    return {'compose.yaml': '# The Metaform relay, written by metaform node relay-init. Start it with: '
                            'docker compose up -d --build\n' + to_yaml(operator_compose(domain)),
            'frps.toml': frps_toml(domain), 'Dockerfile': dockerfile(), '.dockerignore': '*\n!wheels/\n'}


# ---------------------------------------------------------------------------------------------------- enrolments

class Enrolments:
    """The names the operator handed out, each with its secret's hash, in a JSON file in the relay's home."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def read(self) -> dict[str, dict[str, Any]]:
        try:
            return cast(dict[str, dict[str, Any]], json.loads(self.path.read_text(encoding='utf-8')))
        except (OSError, ValueError):
            return {}

    def enrol(self, name: str) -> str:
        name = name.lower()
        if not LABEL.match(name) or name in RESERVED:
            raise ValueError(f'{name!r} cannot be a relay name: lowercase letters, digits and hyphens, not reserved.')
        secret = made()
        held = self.read()
        held[name] = {'sha256': sha256(secret.encode()).hexdigest(), 'enrolled': time.time()}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(held, indent=2) + '\n', encoding='utf-8')
        self.path.chmod(0o600)
        return secret

    def withdraw(self, name: str) -> bool:
        held = self.read()
        if held.pop(name.lower(), None) is None:
            return False
        self.path.write_text(json.dumps(held, indent=2) + '\n', encoding='utf-8')
        return True


def decide(request: dict[str, Any], enrolled: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """The gate's answer to frps, in frp's server-plugin protocol: `reject` with a reason, or `unchange`."""
    op = request.get('op')
    content = cast(dict[str, Any], request.get('content') or {})
    if op == 'Login':
        user = str(content.get('user') or '').lower()
        secret = str(cast(dict[str, Any], content.get('metas') or {}).get('token') or '')
        record = enrolled.get(user)
        if record is None or not secret or sha256(secret.encode()).hexdigest() != record.get('sha256'):
            return {'reject': True, 'reject_reason': 'not enrolled'}
        return {'reject': False, 'unchange': True}
    if op == 'NewProxy':
        owner = cast(dict[str, Any], content.get('user') or {})
        user = str(owner.get('user') or '').lower()
        secret = str(cast(dict[str, Any], owner.get('metas') or {}).get('token') or '')
        record = enrolled.get(user)
        if record is None or sha256(secret.encode()).hexdigest() != record.get('sha256'):
            return {'reject': True, 'reject_reason': 'not enrolled'}
        if content.get('proxy_type') != 'https':
            return {'reject': True, 'reject_reason': 'only https passthrough is relayed'}
        if str(content.get('subdomain') or '').lower() != user or content.get('custom_domains'):
            return {'reject': True, 'reject_reason': 'a client is relayed only under its own name'}
        return {'reject': False, 'unchange': True}
    return {'reject': True, 'reject_reason': 'unsupported operation'}


def gate_app(enrolments: Enrolments) -> Any:
    from starlette.applications import Starlette
    from starlette.requests import Request
    from starlette.responses import JSONResponse
    from starlette.routing import Route

    async def frp(request: Request) -> JSONResponse:
        try:
            body = await request.json()
        except ValueError:
            return JSONResponse({'reject': True, 'reject_reason': 'bad request'})
        return JSONResponse(decide(cast(dict[str, Any], body) if isinstance(body, dict) else {}, enrolments.read()))

    async def health(_: Request) -> JSONResponse:
        return JSONResponse({'ok': True})
    return Starlette(routes=[Route('/frp', frp, methods=['POST']), Route('/health', health, methods=['GET'])])


def public_url(name: str, domain: str) -> str:
    return f'https://{name.lower()}.{domain.lower()}'
