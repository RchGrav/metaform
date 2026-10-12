"""A host for the Node on Vultr, through Vultr's API v2: the SSH key, a firewall group for 22, 80 and 443, and an
Ubuntu 24.04 instance prepared by cloud-init. The API key is read from `VULTR_API_KEY`, as vultr-cli reads it, and
is never stored. Field names follow Vultr's own Go client, govultr v3 (instance.go, firewall_rule.go, ssh_key.go).

API reference: https://www.vultr.com/api/ ; CLI: https://github.com/vultr/vultr-cli
"""
from __future__ import annotations

import json
import time
from collections.abc import Callable
from typing import Any

import httpx

from metaform.module import Stop

from .config import NodeSpec
from .plans import Step, b64, cloud_init, environment_key

BASE = 'https://api.vultr.com'
KEY = 'VULTR_API_KEY'
UBUNTU_2404 = 2284  # "Ubuntu 24.04 LTS x64" in GET /v2/os; the setting can name another
RULES = (('tcp', '22', 'ssh'), ('tcp', '80', 'acme http-01'), ('tcp', '443', 'https'), ('udp', '443', 'http/3'))


class Vultr:
    """The few calls the Node makes, each `Authorization: Bearer <key>` over HTTPS."""

    def __init__(self, key: str, transport: httpx.BaseTransport | None = None) -> None:
        self.client = httpx.Client(base_url=BASE, timeout=30, transport=transport,
                                   headers={'Authorization': f'Bearer {key}', 'User-Agent': 'metaform-node'})

    def call(self, method: str, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        answer = self.client.request(method, path, json=body)
        if answer.status_code >= 400:
            raise Stop(f'Vultr refused {method} {path}: {answer.status_code} {answer.text[:300]}',
                       'Check the plan, region and API key access (Vultr limits API keys by IP address).')
        return answer.json() if answer.content else {}


def calls(spec: NodeSpec, *, region: str, plan: str, os_id: int, public_key: str, label: str,
          relay_port: int | None = None) -> list[tuple[str, str, str, dict[str, Any] | None]]:
    """Every API call the provisioning makes, in order: (what it is, method, path, body). A path or body naming
    `{ssh_key_id}`, `{firewall_group_id}` or `{instance_id}` takes the id an earlier call answered with."""
    rules = [*RULES, *((('tcp', str(relay_port), 'frp relay control'),) if relay_port else ())]
    made: list[tuple[str, str, str, dict[str, Any] | None]] = [
        ('ssh_key', 'POST', '/v2/ssh-keys', {'name': label, 'ssh_key': public_key}),
        ('firewall_group', 'POST', '/v2/firewalls', {'description': label})]
    for ip_type, subnet, size in (('v4', '0.0.0.0', 0), ('v6', '::', 0)):
        for protocol, port, note in rules:
            made.append(('rule', 'POST', '/v2/firewalls/{firewall_group_id}/rules',
                         {'ip_type': ip_type, 'protocol': protocol, 'subnet': subnet, 'subnet_size': size,
                          'port': port, 'notes': note}))
    made.append(('instance', 'POST', '/v2/instances', {
        'region': region, 'plan': plan, 'os_id': os_id, 'label': label, 'hostname': spec.domain.split('.')[0],
        'tags': ['metaform-node'], 'sshkey_id': ['{ssh_key_id}'], 'firewall_group_id': '{firewall_group_id}',
        'enable_ipv6': True, 'backups': 'disabled', 'activation_email': False,
        'user_data': '<base64 of the cloud-init below>'}))
    return made


def _filled(value: Any, state: dict[str, Any]) -> Any:
    if isinstance(value, str):
        for key, found in state.items():
            value = value.replace('{' + key + '}', str(found))
        return value
    if isinstance(value, list):
        return [_filled(one, state) for one in value]  # pyright: ignore[reportUnknownVariableType]
    if isinstance(value, dict):
        return {key: _filled(one, state) for key, one in value.items()}  # pyright: ignore
    return value


def provision_steps(spec: NodeSpec, *, region: str, plan: str, os_id: int, public_key: str,
                    relay_port: int | None = None, client: Callable[[], Vultr] | None = None,
                    wait_seconds: float = 900) -> list[Step]:
    """The steps that make the VM; each shows its call exactly, the API key as $VULTR_API_KEY."""
    label = f'metaform-node-{spec.domain}'
    user_data = cloud_init(relay_port=relay_port)
    connect = client or (lambda: Vultr(environment_key(KEY)))
    held: dict[str, Vultr] = {}

    def api() -> Vultr:
        if 'api' not in held:
            held['api'] = connect()
        return held['api']

    steps: list[Step] = []
    for what, method, path, body in calls(spec, region=region, plan=plan, os_id=os_id, public_key=public_key,
                                          label=label, relay_port=relay_port):
        shown_body = json.dumps(body, indent=2) if body else ''
        if what == 'instance':
            shown_body += '\nuser_data (cloud-init, base64-encoded when sent):\n' + user_data

        def run(state: dict[str, Any], what: str = what, method: str = method, path: str = path,
                body: dict[str, Any] | None = body) -> dict[str, Any]:
            sent = _filled(body, state) if body else None
            if sent and what == 'instance':
                sent['user_data'] = b64(user_data)
            answer = api().call(method, _filled(path, state), sent)
            if what == 'ssh_key':
                return {'ssh_key_id': answer['ssh_key']['id']}
            if what == 'firewall_group':
                return {'firewall_group_id': answer['firewall_group']['id']}
            if what == 'instance':
                return {'instance_id': answer['instance']['id']}
            return {}
        steps.append(Step(f'Vultr: create the {what.replace("_", " ")}',
                          f'{method} {BASE}{path}\nAuthorization: Bearer ${KEY}\n{shown_body}'.rstrip(), run))

    def wait(state: dict[str, Any]) -> dict[str, Any]:
        deadline = time.monotonic() + wait_seconds
        while True:
            instance = api().call('GET', f'/v2/instances/{state["instance_id"]}')['instance']
            if instance.get('status') == 'active' and instance.get('server_status') == 'ok' \
                    and instance.get('main_ip') not in (None, '', '0.0.0.0'):
                return {'main_ip': instance['main_ip'], 'v6_main_ip': instance.get('v6_main_ip', '')}
            if time.monotonic() > deadline:
                raise Stop('The Vultr instance did not become active in time.', 'metaform node status')
            time.sleep(10)
    steps.append(Step('Vultr: wait until the instance is active and has its address',
                      f'GET {BASE}/v2/instances/{{instance_id}}  (until status=active, server_status=ok)', wait))
    return steps
