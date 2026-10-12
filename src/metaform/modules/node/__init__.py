"""node: the Metaform Node, Metaform reachable from the internet on a host of your own, or through a relay.

`metaform node init <domain>` writes a Docker Compose project for that name: Caddy for TLS in front, the Node's own
OAuth 2.1 authorization server with passkeys (`authserver.py`), `metaform mcp serve --http` with A2A, and the web
page, every Metaform process on 127.0.0.1 behind Caddy. `deploy` prepares a fresh Ubuntu host over SSH, or creates
one on Vultr with cloud-init, then copies, builds, starts and checks the stack from outside. `status`, `logs` and
`update` run against it; `invite`, `accounts` and `revoke` manage who may sign in; `connect` prints how AI tools
register the Node. `relay` puts a Metaform with no open port behind a relay; `relay-init`, `relay-enrol` and
`relay-gate` are the relay operator's side.

Every verb is the person's own, on the command line: none is a tool an agent can call.
"""
from __future__ import annotations

import json
import os
import shlex
import sys
from pathlib import Path
from typing import Any

from metaform import home, settings
from metaform.module import Context, Module, Noun, Stop, Verb

from . import config

SUPPORTED_OS = ('linux', 'macos', 'windows')
DEPENDENCIES = ('mcp>=2.2,<3', 'webauthn>=2.8,<3', 'httpx>=0.28,<1', 'uvicorn>=0.31', 'starlette>=0.48')
SHIPS_DISABLED = False
REMOTE_AGENT = False  # a deployment tool for the person; a remote agent has no use for it

G = 'global'
settings.text('node_domain', '', scope=G, person_only=True, label='Node domain',
              help='The public name the Node is reached at, such as metaform.example.com.',
              details='Set by metaform node init and read by the authorization server, whose issuer is https://<it>. '
                      'Passkeys belong to this name: moving the Node to another name means enrolling them again.')
settings.choice('node_mode', list(config.MODES), 'acme', scope=G, person_only=True, label='Node TLS mode',
                help='How the Node gets its certificate and is reached: acme, dns, relay or internal.',
                details='acme: a public host, Let\'s Encrypt over HTTP-01 or TLS-ALPN-01. dns: DNS-01 through the DNS '
                        'provider\'s API (node_dns_provider), for a wildcard or a host port 80 cannot reach. relay: '
                        'no open port, through a relay that passes TLS through (metaform node relay). internal: '
                        'Caddy\'s local CA, for a stand-in on a test machine only.')
settings.text('node_email', '', scope=G, label='Certificate contact',
              help='The email address the certificate authority warns before a certificate lapses.')
settings.choice('node_capability', list(config.CAPABILITIES), 'write', scope=G, person_only=True,
                label='Node capability',
                help='What the Node lets an agent do: read, write (memories, tickets, terms), or dispatch (start '
                     'agents with shells and file writes).',
                details='It caps what the authorization server grants: read grants mcp:read; write adds mcp:write and '
                        'a2a:tickets; dispatch adds mcp:dispatch. Below dispatch the dispatch module is off in the '
                        'Node. A Node at dispatch runs agents on its host, so it belongs on a VM of its own.')
settings.choice('node_relay_capability', list(config.CAPABILITIES), 'read', scope=G, person_only=True,
                label='Capability through a relay',
                help='The capability a Node reached through a relay has: read unless you raise it.',
                details='Used instead of node_capability by metaform node relay, so dispatch is reachable through a '
                        'relay only when you set this to dispatch yourself.')
settings.items('node_projects', (), scope=G, label='Node project folders',
               help='Folders on the host mounted into the Node, each at /srv/projects/<its name>.')
settings.text('node_dns_provider', '', scope=G, label='DNS provider',
              help='The caddy-dns module for DNS-01, such as cloudflare, vultr or route53; its token goes in '
                   'secrets.env on the host as DNS_API_TOKEN.')
settings.text('node_wildcard', '', scope=G, label='Wildcard base',
              help='A base domain to hold a wildcard certificate for, such as metaform.ing, with node_mode dns.')
settings.boolean('node_dcr', False, scope=G, person_only=True, label='Dynamic client registration',
                 help='Let older AI tools register themselves (RFC 7591), which the MCP specification of 2026-07-28 '
                      'deprecates in favour of Client ID Metadata Documents.')
settings.text('node_host', '', scope=G, label='Node host', help='The host deploy reaches over SSH, a name or address.')
settings.text('node_ssh_identity', '', scope=G, label='SSH identity',
              help='The private key file deploy uses; empty uses your SSH agent and configuration.')
settings.text('node_dir', 'metaform-node', label='Node folder',
              help='The folder, under this one, that holds the Node\'s compose project.')
settings.choice('node_provider', ['none', 'vultr'], 'none', scope=G, label='Cloud provider',
                help='none: you made the host; vultr: deploy creates it with Vultr\'s API, the key in VULTR_API_KEY.')
settings.text('node_vultr_region', 'ewr', scope=G, label='Vultr region', help='The region id, ewr for New York (NJ).')
settings.text('node_vultr_plan', 'vhf-1c-1gb', scope=G, label='Vultr plan',
              help='The plan id: GET https://api.vultr.com/v2/plans lists them.')
settings.number('node_vultr_os', 2284, min=1, scope=G, label='Vultr OS id',
                help='The OS id, 2284 for Ubuntu 24.04 LTS x64: GET https://api.vultr.com/v2/os lists them.')
settings.text('node_ssh_public_key', '~/.ssh/id_ed25519.pub', scope=G, label='SSH public key',
              help='The public key a created VM lets in, for root and the working user.')
settings.text('node_relay_server', '', scope=G, label='Relay server',
              help='The relay this Metaform dials, such as relay.metaform.ing.')
settings.number('node_relay_port', 7000, min=1, max=65535, scope=G, label='Relay control port',
                help='The port the relay\'s frps takes tunnel clients on; 7000 unless the operator says otherwise.')
settings.text('node_relay_domain', '', scope=G, label='Relay domain',
              help='On the relay\'s own host: the domain whose names it routes, such as metaform.ing.')
settings.boolean('node_dry_run', False, switches=('--dry-run', '--no-dry-run'), label='Dry run',
                 help='Print every step, API calls and cloud-init included, and run none.',
                 details='Given on the command line for the one run; deploy and update with it change nothing.')


def _folder(ctx: Context) -> Path:
    return (Path(ctx.folder) / str(ctx.nouns.get('dir') or ctx.setting('node_dir'))).resolve()


def _write(folder: Path, made: dict[str, str]) -> list[str]:
    for name, text in made.items():
        path = folder / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding='utf-8')
    (folder / 'wheels').mkdir(exist_ok=True)
    return sorted(made)


def _spec(ctx: Context, domain: str, mode: str | None = None) -> config.NodeSpec:
    mode = mode or str(ctx.setting('node_mode'))
    capability = str(ctx.setting('node_relay_capability' if mode == 'relay' else 'node_capability'))
    return config.NodeSpec(
        domain=domain.lower(), mode=mode, email=str(ctx.setting('node_email')), capability=capability,
        projects=tuple(str(one) for one in ctx.setting('node_projects') or ()),
        dns_provider=str(ctx.setting('node_dns_provider')), wildcard=str(ctx.setting('node_wildcard')),
        relay_server=str(ctx.setting('node_relay_server')), relay_port=int(ctx.setting('node_relay_port')),
        relay_name=str(ctx.nouns.get('name') or domain.split('.')[0]) if mode == 'relay' else '',
        dcr=bool(ctx.setting('node_dcr')), owner=str(ctx.nouns.get('owner') or 'owner'))


def write_project(folder: Path, spec: config.NodeSpec) -> dict[str, Any]:
    """The compose project for `spec`, refused while anything in it would be unsafe; the owner's setup link only
    when this folder has none yet, since only its hash is kept."""
    found = config.problems(spec)
    if found:
        raise Stop(' '.join(found), 'metaform help node init')
    first = not (folder / 'bootstrap' / 'owner-invite.json').exists()
    secret, invite = config.owner_invite(spec) if first else (None, None)
    written = _write(folder, config.files(spec, invite))
    shown: dict[str, Any] = {'folder': str(folder), 'files': written, 'issuer': spec.issuer,
                             'capability': spec.capability, 'mode': spec.mode}
    if secret:
        shown['owner_setup_link'] = config.setup_link(spec.issuer, secret)
        shown['note'] = ('Open the setup link once the Node is up to enrol your passkey; it works once, for '
                         f'{config.INVITE_DAYS} days, and is not kept anywhere. Lost: metaform node invite '
                         f'{spec.owner} on the host makes another.')
    return shown


def init(ctx: Context) -> dict[str, Any]:
    domain = str(ctx.nouns['domain']).lower()
    shown = write_project(_folder(ctx), _spec(ctx, domain))
    settings_note = f'metaform set --node-domain {domain}'
    shown['next'] = f'metaform node deploy --dry-run   (then without --dry-run); {settings_note} for the other verbs'
    return shown


# ---------------------------------------------------------------------------------------------------- deploy

def _project(ctx: Context) -> tuple[Path, config.NodeSpec]:
    folder = _folder(ctx)
    if not (folder / 'node.json').is_file():
        raise Stop(f'No Node project in {folder}.', 'metaform node init <domain>')
    return folder, config.spec_from(folder)


def _state(folder: Path) -> dict[str, Any]:
    try:
        return json.loads((folder / 'node-state.json').read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {}


def _target(ctx: Context, folder: Path) -> Any:
    from .plans import Target
    state = _state(folder)
    host = str(ctx.setting('node_host') or state.get('main_ip') or '')
    return Target(host=host, folder=folder, identity=str(ctx.setting('node_ssh_identity')), state=state)


def deploy(ctx: Context) -> dict[str, Any]:
    from . import plans
    folder, spec = _project(ctx)
    target = _target(ctx, folder)
    dry = bool(ctx.setting('node_dry_run'))
    provision: list[Any] = []
    vultr = str(ctx.setting('node_provider')) == 'vultr' and not target.host
    # A host that also runs the relay (node_relay_domain set here) opens the tunnel's control port too.
    relay_port = int(ctx.setting('node_relay_port')) if str(ctx.setting('node_relay_domain')) else None
    if vultr:
        from . import vultr as provider
        key_file = Path(os.path.expanduser(str(ctx.setting('node_ssh_public_key'))))
        public_key = key_file.read_text(encoding='utf-8').strip() if key_file.is_file() else f'<contents of {key_file}>'
        if not dry and not key_file.is_file():
            raise Stop(f'No public key at {key_file}.', 'metaform set --node-ssh-public-key <file.pub>')
        provision = provider.provision_steps(spec, region=str(ctx.setting('node_vultr_region')),
                                             plan=str(ctx.setting('node_vultr_plan')),
                                             os_id=int(ctx.setting('node_vultr_os')), public_key=public_key,
                                             relay_port=relay_port)
        target.host = '{main_ip}'
    elif not target.host:
        raise Stop('No host to deploy to.', 'metaform set --node-host <name or address>, or --node-provider vultr')
    steps = plans.deploy_plan(spec, target, prepared_by_cloud_init=vultr, relay_port=relay_port)
    if dry:
        return {'dry_run': True, 'host': target.host, 'plan': plans.show(provision + steps)}
    state = target.state
    if provision:
        state = plans.execute(provision, state, ctx.say)
        (folder / 'node-state.json').write_text(json.dumps(state, indent=2) + '\n', encoding='utf-8')
        target.host = str(state['main_ip'])
        ctx.say(f'Point {spec.domain} at {target.host} (an A record) if it does not already.')
    state = plans.execute(steps, state, ctx.say)
    return {'deployed': spec.issuer, 'host': target.host, 'checks': {key: state.get(key) for key in (
        'certificate', 'issuer', 'cimd', 'resource', 'mcp_refuses_anonymous')},
            'next': 'metaform node connect'}


def update(ctx: Context) -> dict[str, Any]:
    from . import plans
    folder, spec = _project(ctx)
    target = _target(ctx, folder)
    if not target.host:
        raise Stop('No host recorded for this Node.', 'metaform set --node-host <name or address>')
    _write(folder, {name: text for name, text in config.files(spec, None).items() if not name.startswith('bootstrap')})
    steps = plans.update_plan(spec, target)
    if ctx.setting('node_dry_run'):
        return {'dry_run': True, 'host': target.host, 'plan': plans.show(steps)}
    plans.execute(steps, target.state, ctx.say)
    return {'updated': spec.issuer, 'host': target.host}


def status(ctx: Context) -> dict[str, Any]:
    from . import plans
    folder, spec = _project(ctx)
    target = _target(ctx, folder)
    if not target.host:
        raise Stop('No host recorded for this Node.', 'metaform set --node-host <name or address>')
    shown: dict[str, Any] = {'issuer': spec.issuer, 'host': target.host, 'capability': spec.capability}
    try:
        services = plans.parse_ps(plans.run_command(target.ssh(target.user, f'cd {plans.REMOTE_DIR} && docker compose ps '
                                                                     '--format json')))
        shown['services'] = {one.get('Service'): one.get('Health') or one.get('State') for one in services}
    except Stop as error:
        shown['services'] = f'unreachable: {error}'
    try:
        shown['checks'] = plans.verify(spec.domain, verify_tls=spec.mode != 'internal')
    except OSError as error:
        shown['checks'] = f'unreachable: {error}'
    return shown


def logs(ctx: Context) -> str:
    from . import plans
    folder, _ = _project(ctx)
    target = _target(ctx, folder)
    if not target.host:
        raise Stop('No host recorded for this Node.', 'metaform set --node-host <name or address>')
    service = ctx.nouns.get('service')
    return plans.run_command(target.ssh(target.user, plans.logs_command(
        str(service) if service else None, int(ctx.nouns.get('lines') or 200))))


# ---------------------------------------------------------------------------------------------------- accounts

def _issuer(ctx: Context) -> str:
    kept = home.home() / 'node' / 'issuer'
    if kept.is_file():
        return kept.read_text(encoding='utf-8').strip()
    domain = str(ctx.setting('node_domain'))
    if not domain:
        raise Stop('This home serves no Node.', 'metaform set --node-domain <domain>')
    return f'https://{domain.lower()}'


def _on_host(ctx: Context, verb: str, *words: str) -> Any | None:
    """Run an account verb where the accounts are: inside the Node's container directly, otherwise on the host
    through `docker compose exec`, when this folder holds a deployed Node."""
    if os.environ.get('METAFORM_NODE_SERVICE'):
        return None
    folder = _folder(ctx)
    if not (folder / 'node.json').is_file():
        return None
    from . import plans
    target = _target(ctx, folder)
    if not target.host:
        return None
    command = f'cd {plans.REMOTE_DIR} && docker compose exec -T auth metaform node {verb} ' + shlex.join(words)
    return plans.run_command(target.ssh(target.user, command)).strip()


def _store() -> Any:
    from .authserver import store_path
    from .authstore import AuthStore
    return AuthStore(store_path())


def invite(ctx: Context) -> Any:
    name = str(ctx.nouns['name']).lower()
    remote = _on_host(ctx, 'invite', name)
    if remote is not None:
        return remote
    if not config.LABEL.match(name):
        raise Stop(f'{name!r} cannot be an account name.', 'metaform node invite <lowercase letters and digits>')
    store = _store()
    account = store.add_account(name, 'member' if store.owner_exists() else 'owner')
    if account.disabled:
        raise Stop(f'{name} was revoked.', 'Invite them under another name.')
    secret = store.invite(account, config.INVITE_DAYS)
    return {'account': account.name, 'role': account.role, 'setup_link': config.setup_link(_issuer(ctx), secret or ''),
            'note': f'It enrols one passkey, once, within {config.INVITE_DAYS} days. Send it privately.'}


def accounts(ctx: Context) -> Any:
    remote = _on_host(ctx, 'accounts')
    return remote if remote is not None else _store().accounts()


def revoke(ctx: Context) -> Any:
    name = str(ctx.nouns['name']).lower()
    remote = _on_host(ctx, 'revoke', name, '--confirm')
    if remote is not None:
        return remote
    if not _store().disable(name):
        raise Stop(f'No account {name}.', 'metaform node accounts')
    return {'revoked': name, 'note': 'Its sessions, invitations and tokens no longer work.'}


def auth(ctx: Context) -> None:
    from .authserver import Policy, serve
    domain = str(ctx.setting('node_domain')).lower()
    if not domain:
        raise Stop('The authorization server needs the Node\'s domain.', 'metaform node auth --node-domain <domain>')
    issuer = 'https://' + domain
    kept = home.home() / 'node' / 'issuer'
    kept.parent.mkdir(parents=True, exist_ok=True)
    kept.write_text(issuer + '\n', encoding='utf-8')
    serve(Policy(issuer, str(ctx.setting('node_capability')), bool(ctx.setting('node_dcr'))), config.AUTH_PORT,
          Path(str(ctx.nouns.get('bootstrap') or '/run/metaform-bootstrap')))


def connect(ctx: Context) -> dict[str, Any]:
    """How each AI tool registers the Node's MCP server, and where its Agent Card is. A host signs in on first use
    with the Node's own sign-in; no token is copied anywhere."""
    folder = _folder(ctx)
    domain = config.spec_from(folder).domain if (folder / 'node.json').is_file() else str(ctx.setting('node_domain'))
    if not domain:
        raise Stop('No Node to connect to.', 'metaform node init <domain>, or metaform set --node-domain <domain>')
    url = f'https://{domain.lower()}/mcp'
    entry = {'type': 'http', 'url': url}
    return {
        'mcp_url': url,
        'claude_code': f'claude mcp add --transport http metaform {url}',
        'vscode': {'file': '.vscode/mcp.json', 'json': {'servers': {'metaform': entry}}},
        'cursor': {'file': '~/.cursor/mcp.json', 'json': {'mcpServers': {'metaform': {'url': url}}}},
        'claude_ai': f'Settings > Connectors > Add custom connector: {url}',
        'a2a_agent_card': f'https://{domain.lower()}/.well-known/agent-card.json',
        'note': 'Each tool opens the Node\'s sign-in the first time: your passkey, then Allow.'}


# ---------------------------------------------------------------------------------------------------- the relay

def relay(ctx: Context) -> dict[str, Any]:
    """Enrol this Metaform with a relay: the compose project in relay mode, the enrolment secret from
    METAFORM_RELAY_TOKEN written to secrets.env beside it, and the public URL it will have."""
    from . import plans
    from .tunnel import public_url
    name = str(ctx.nouns['name']).lower()
    server = str(ctx.setting('node_relay_server')).lower()
    if not server:
        raise Stop('No relay named.', 'metaform set --node-relay-server <relay host>')
    secret = os.environ.get('METAFORM_RELAY_TOKEN', '').strip()
    if not secret:
        raise Stop('The relay operator\'s enrolment secret is not in METAFORM_RELAY_TOKEN.',
                   'export METAFORM_RELAY_TOKEN=<the secret the operator gave you>, then run this again')
    base = str(ctx.nouns.get('domain') or server.split('.', 1)[-1])
    domain = f'{name}.{base}'
    folder = _folder(ctx)
    shown = write_project(folder, _spec(ctx, domain, 'relay'))
    path = folder / 'secrets.env'
    path.write_text(f'METAFORM_RELAY_TOKEN={secret}\n', encoding='utf-8')
    path.chmod(0o600)
    built = plans.build_step(plans.Target(host='', folder=folder)).run
    if built is not None:
        built({})  # the image installs this Metaform's own wheel
    shown.update({'public_url': public_url(name, base), 'mcp_url': public_url(name, base) + '/mcp',
                  'next': f'cd {folder} && docker compose up -d --build'})
    return shown


def relay_init(ctx: Context) -> dict[str, Any]:
    from .tunnel import operator_files
    domain = str(ctx.nouns['domain']).lower()
    if not config.hostname(domain):
        raise Stop(f'{domain!r} is not a host name.', 'metaform node relay-init <domain such as metaform.ing>')
    folder = (Path(ctx.folder) / str(ctx.nouns.get('dir') or 'metaform-relay')).resolve()
    written = _write(folder, operator_files(domain))
    return {'folder': str(folder), 'files': written,
            'dns': f'*.{domain} -> this host (A and AAAA); relay.{domain} too',
            'firewall': 'open 22, 443 and 7000 only',
            'next': f'metaform node relay-enrol <name> --node-relay-domain {domain}, inside the gate container'}


def _enrolments() -> Any:
    from .tunnel import Enrolments
    return Enrolments(home.home() / 'relay' / 'enrolments.json')


def relay_enrol(ctx: Context) -> dict[str, Any]:
    from .tunnel import public_url
    name = str(ctx.nouns['name']).lower()
    domain = str(ctx.setting('node_relay_domain'))
    try:
        secret = _enrolments().enrol(name)
    except ValueError as error:
        raise Stop(str(error), 'metaform node relay-enrol <name>') from None
    return {'name': name, 'public_url': public_url(name, domain) if domain else None, 'secret': secret,
            'note': 'Give the secret to its owner privately; it is shown once. They run: METAFORM_RELAY_TOKEN=<secret> '
                    f'metaform node relay {name}'}


def relay_gate(ctx: Context) -> None:
    import uvicorn

    from .tunnel import gate_app
    print(f'Metaform relay gate on 127.0.0.1:{config.GATE_PORT}', file=sys.stderr, flush=True)
    uvicorn.Server(uvicorn.Config(gate_app(_enrolments()), host='127.0.0.1', port=config.GATE_PORT,
                                  log_level='warning')).run()


CLI: tuple[Any, ...] = ('cli',)
SETUP = ('node_mode', 'node_email', 'node_capability', 'node_relay_capability', 'node_projects', 'node_dns_provider',
         'node_wildcard', 'node_dcr', 'node_relay_server', 'node_relay_port', 'node_dir')
REACH = ('node_host', 'node_ssh_identity', 'node_dir')

MODULE = Module(
    id='node',
    summary='Serve Metaform from a host of your own, reachable from the internet behind your own sign-in.',
    purpose='Writes, deploys and runs the Metaform Node: MCP, A2A and the page on a host of your own, behind TLS '
            'and the Node\'s own OAuth 2.1 sign-in with passkeys. The person\'s commands only. Details: '
            'metaform help node.',
    details='init writes the compose project; deploy prepares the host (or creates it on Vultr) and starts it; '
            'status, logs and update follow it; invite, accounts and revoke decide who signs in; connect prints how '
            'AI tools add it. A Node refuses to serve beyond this machine without its authorization server. Design: '
            'docs/guides/metaform-node.md.',
    verbs=(
        Verb('init', init, 'Write the Node\'s compose project for a domain, and the owner\'s one-time setup link.',
             nouns=(Noun('domain', 'The public name, such as metaform.example.com.'),
                    Noun('owner', 'The owner\'s account name.', required=False),
                    Noun('dir', 'The folder to write, under this one.', required=False)),
             switches=SETUP, surfaces=CLI,
             examples=(('metaform node init metaform.example.com --node-email me@example.com',
                        'A public host with a Let\'s Encrypt certificate.'),)),
        Verb('deploy', deploy, 'Prepare the host, copy the Node, start it, and check it from outside.',
             switches=('node_dry_run', 'node_provider', 'node_vultr_region', 'node_vultr_plan', 'node_vultr_os',
                       'node_ssh_public_key', 'node_relay_domain', 'node_relay_port', *REACH), surfaces=CLI, open_world=True, task=True,
             examples=(('metaform node deploy --dry-run', 'Print every step and run none.'),)),
        Verb('status', status, 'Show the Node\'s services and check it from outside.', switches=REACH, surfaces=CLI,
             effect='read', open_world=True),
        Verb('logs', logs, 'Show the Node\'s recent logs.',
             nouns=(Noun('service', 'caddy, auth, mcp or web.', required=False),
                    Noun('lines', 'How many lines.', kind='int', required=False)),
             switches=REACH, surfaces=CLI, effect='read', open_world=True),
        Verb('update', update, 'Rebuild the Node with this Metaform and restart what changed.',
             switches=('node_dry_run', *REACH), surfaces=CLI, open_world=True, task=True),
        Verb('auth', auth, 'Run the Node\'s authorization server, in the Node\'s auth container.',
             nouns=(Noun('bootstrap', 'The folder holding the owner\'s setup record.', required=False),),
             switches=('node_domain', 'node_capability', 'node_dcr'), surfaces=CLI, transport=True),
        Verb('invite', invite, 'Let a person in: an account and a one-time link to enrol their passkey.',
             nouns=(Noun('name', 'Their account name.'),), switches=REACH, surfaces=CLI),
        Verb('accounts', accounts, 'List the accounts that may sign in, with their passkeys.', switches=REACH,
             surfaces=CLI, effect='read'),
        Verb('revoke', revoke, 'Shut an account out: its sessions, links and tokens stop working.',
             nouns=(Noun('name', 'The account name.'),), switches=REACH, surfaces=CLI, effect='remove',
             caution='The account cannot sign in again; invite them under a new name to let them back.'),
        Verb('connect', connect, 'Show how AI tools add the Node, and its Agent Card.',
             nouns=(Noun('dir', 'The Node folder, under this one.', required=False),), surfaces=CLI, effect='read'),
        Verb('relay', relay, 'Reach this Metaform through a relay, with no open port.',
             nouns=(Noun('name', 'The name the relay operator enrolled.'),
                    Noun('domain', 'The relay\'s domain, when it is not the server\'s parent.', required=False),
                    Noun('dir', 'The folder to write, under this one.', required=False)),
             switches=('node_relay_server', 'node_relay_port', 'node_relay_capability', 'node_email',
                       'node_projects', 'node_dir'), surfaces=CLI, open_world=True),
        Verb('relay-init', relay_init, 'Write a relay operator\'s compose project for a domain.',
             nouns=(Noun('domain', 'The domain whose names the relay routes.'),
                    Noun('dir', 'The folder to write, under this one.', required=False)), surfaces=CLI),
        Verb('relay-enrol', relay_enrol, 'On the relay: enrol a name and show its one-time secret.',
             nouns=(Noun('name', 'The name, a DNS label.'),), switches=('node_relay_domain',), surfaces=CLI),
        Verb('relay-gate', relay_gate, 'On the relay: answer frps on who may connect.',
             switches=('node_relay_domain',), surfaces=CLI, transport=True),
    ),
)
