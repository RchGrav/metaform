"""cloud: this machine's Metaform, reached by cloud AI tools (claude.ai, ChatGPT) through an account at metaform.ing.

`metaform cloud login` signs this machine in to the person's account at the broker with the device grant: a code here,
the person's passkey on the page (login.py). `metaform cloud connect` dials out to the broker over one WebSocket and
serves the MCP requests it carries, with the same MCP server `metaform mcp serve --http` runs, in-process, so no port
is opened (tunnel.py). The AI tool signs in to the same account with standard MCP OAuth at `https://metaform.ing/mcp`;
the broker checks its token, keeps it, and sends each request down this machine's tunnel with a signed statement of
who is calling, which is checked here. Maps, memories and every tool stay and run here; the record of who called what
is kept here too (audit.py). `status` shows the account and the connection, `logout` revokes this machine's sign-in,
`audit` reads the record.

The broker is trusted to say who is calling, within the scopes the person allows here (cloud_capability): a broker
that misbehaved could call tools as the person up to that ceiling, and every call it carried is in the audit log.
Turn the module off (`metaform disable cloud`) and nothing of this path loads.

Every verb is the person's own, on the command line: none is a tool an agent can call.
"""
from __future__ import annotations

import contextlib
import json
import os
import re
import subprocess
import sys
import time
import webbrowser
from pathlib import Path
from typing import Any, cast

from metaform import home, settings
from metaform.module import Context, Module, Noun, Stop, Subscription, Verb, child_environment

SUPPORTED_OS = ('linux', 'macos', 'windows')
DEPENDENCIES = ('mcp>=2.2,<3', 'httpx>=0.28,<1', 'websockets>=13', 'pyjwt[crypto]>=2.10')
SHIPS_DISABLED = False
REMOTE_AGENT = False  # the person's own connection; a remote agent has no use for it

G = 'global'
LABEL = re.compile(r'^(?!-)[a-z0-9-]{1,63}(?<!-)$')  # a DNS label, as the broker names instances
CAPABILITIES = ('read', 'write', 'dispatch')
settings.text('cloud_url', 'https://metaform.ing', scope=G, person_only=True, label='Cloud broker',
              help='The broker this machine signs in to and dials, https://metaform.ing unless you run your own.',
              details='Its authorization server signs this machine in (metaform cloud login) and carries AI tools\' '
                      'MCP requests to it over the tunnel (metaform cloud connect). Changing it means logging in '
                      'again.')
settings.text('cloud_instance', 'default', scope=G, person_only=True, label='Cloud instance name',
              help='The name this machine has in your account: default is reached at https://metaform.ing/mcp, any '
                   'other name at https://metaform.ing/mcp/<name>.',
              details='Lowercase letters, digits and hyphens. Give each machine its own name; a second machine '
                      'connecting under the same name takes the first one\'s place. AI tools approved for one name '
                      'cannot reach another.')
settings.choice('cloud_capability', list(CAPABILITIES), 'write', scope=G, person_only=True,
                label='What cloud AI tools may do here',
                help='The most an AI tool reaching this machine through the broker may do: read, write (memories, '
                     'tickets, terms), or dispatch (start agents with shells and file writes).',
                details='This machine\'s own ceiling, whatever the AI tool was granted at sign-in: each request is held '
                        'to the scopes both allow, and a tool needing more is refused with insufficient_scope. '
                        'dispatch starts agents on this machine, so raise it only if you want that from a cloud chat.')
settings.choice('cloud_audit', ['names', 'full'], 'names', scope=G, person_only=True, label='Cloud audit detail',
                help='What the local record of cloud calls keeps: names (the tool or resource called, never its '
                     'arguments) or full (the arguments too).',
                details='The record is <home>/cloud/audit.jsonl on this machine only, readable by you alone; '
                        'metaform cloud audit reads it. Results are never written.')
settings.boolean('cloud_autoconnect', False, scope=G, person_only=True, label='Connect with the web GUI',
                 help='Start metaform cloud connect when metaform web start starts the page, once this machine is '
                      'logged in.',
                 details='It runs detached beside the page and stops when you stop it or the account signs out.')


def _base(ctx: Context) -> str:
    from .login import check_url
    return check_url(str(ctx.setting('cloud_url')))


def _instance(ctx: Context) -> str:
    name = str(ctx.setting('cloud_instance') or 'default').lower()
    if not LABEL.match(name):
        raise Stop(f'{name!r} cannot be an instance name.', 'metaform set --cloud-instance <lowercase letters, '
                                                             'digits and hyphens>')
    return name


def _credentials() -> Any:
    from .login import load
    made = load()
    if made is None:
        raise Stop('This machine is not signed in to a cloud broker.', 'metaform cloud login')
    return made


def _allows(ctx: Context) -> tuple[str, ...]:
    from . import tunnel
    return tunnel.mcp(Path(ctx.folder)).scopes_up_to(str(ctx.setting('cloud_capability')))


def sign_in(ctx: Context) -> dict[str, Any]:
    import httpx

    from . import login as signing
    base, instance = _base(ctx), _instance(ctx)
    with httpx.Client(timeout=signing.TIMEOUT) as client:
        started = signing.start(base, instance, client)
        ctx.say(f'Open {started.verification_uri} and enter the code {started.user_code}')
        ctx.say('(only if you started this yourself, just now: it connects this machine to your account)')
        with contextlib.suppress(Exception):
            webbrowser.open(started.verification_uri_complete)
        made = signing.finish(started, client, confirm=_confirm(ctx))
    return {'account': made.username, 'instance': made.instance, 'mcp_url': made.resource,
            'next': 'metaform cloud connect, then add the MCP URL as a connector in ChatGPT or Claude'}


def _confirm(ctx: Context) -> Any:
    """At a terminal, the person confirms the account that approved before this machine is connected to it: a code
    approved from someone else's account would otherwise connect this machine, and its maps, to theirs. Without a
    terminal there is no one to ask, and the account is named in the answer."""
    if not sys.stdin.isatty():
        return None

    def ask(account: str) -> bool:
        ctx.say(f'Approved by the account {account}.')
        try:
            said = input(f'Is {account} your own account? Connect this machine to it [y/N]: ')
        except EOFError:
            return False
        return said.strip().lower() in ('y', 'yes')
    return ask


def sign_out(ctx: Context) -> dict[str, Any]:
    import httpx

    from . import login as signing
    made = signing.load()
    if made is None:
        return {'signed_in': False}
    with httpx.Client(timeout=signing.TIMEOUT) as client:
        revoked = signing.revoke(made, client)
    signing.forget()
    return {'signed_out': made.username, 'revoked_at_broker': revoked,
            'note': 'This machine\'s sign-in is gone here; to end every AI tool\'s access too, sign out everywhere on '
                    f'{made.issuer}/account.'}


def connect(ctx: Context) -> dict[str, Any]:
    import anyio

    from . import tunnel
    made = _credentials()
    if made.instance != _instance(ctx) or made.issuer != _base(ctx):
        raise Stop(f'This machine signed in as {made.instance} at {made.issuer}; the settings now name another.',
                   'metaform cloud login')
    held: dict[str, Any] = {'state': 'connecting', 'pid': os.getpid(), 'instance': made.instance,
                            'resource': made.resource}

    def state(record: dict[str, Any]) -> None:
        held.update(record)
        tunnel.write_state(held)

    async def run() -> None:
        async def beat() -> None:
            while True:
                tunnel.write_state(held)
                await anyio.sleep(20)
        async with anyio.create_task_group() as group:
            group.start_soon(beat)
            try:
                await tunnel.serve(Path(ctx.folder), made, _allows(ctx),
                                   full_audit=str(ctx.setting('cloud_audit')) == 'full', say=ctx.say, state=state)
            except tunnel.Stopped as stopped:  # kept, so it leaves the task group as itself
                ended.append(stopped)
            finally:
                group.cancel_scope.cancel()
    ended: list[tunnel.Stopped] = []
    state({'state': 'connecting'})
    with contextlib.suppress(KeyboardInterrupt):
        anyio.run(run)
    if ended:
        state({'state': 'stopped', 'reason': str(ended[0]), 'next': ended[0].next_step})
        raise Stop(str(ended[0]), ended[0].next_step)
    state({'state': 'stopped', 'reason': 'stopped here', 'next': 'metaform cloud connect'})
    return {'state': 'stopped'}


def _connection() -> dict[str, Any]:
    from .tunnel import state_file
    try:
        found: Any = json.loads(state_file().read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {'state': 'not running'}
    record: dict[str, Any] = cast(dict[str, Any], found) if isinstance(found, dict) else {}
    if record.get('state') != 'stopped' and time.time() - float(record.get('beat') or 0) > 60:
        record['state'] = 'not running'
    return record


def status(ctx: Context) -> dict[str, Any]:
    from .login import load
    made = load()
    if made is None:
        return {'signed_in': False, 'next': 'metaform cloud login'}
    running = _connection()
    shown: dict[str, Any] = {'signed_in': True, 'broker': made.issuer, 'account': made.username,
                             'instance': made.instance, 'mcp_url': made.resource,
                             'connection': running.get('state'), 'capability': str(ctx.setting('cloud_capability'))}
    if running.get('reason'):
        shown['reason'] = running['reason']
    if running.get('state') in ('not running', 'stopped'):
        shown['next'] = running.get('next') or 'metaform cloud connect'
    return shown


def audit_read(ctx: Context) -> list[dict[str, Any]]:
    from . import audit
    return audit.read(int(ctx.nouns.get('lines') or 50))


def web_started(payload: dict[str, Any], ctx: Context) -> dict[str, Any] | None:
    """With cloud_autoconnect on and this machine signed in, the tunnel starts beside the web GUI, detached, unless one
    already runs."""
    from .login import credentials_file
    from .tunnel import state_file
    if not ctx.setting('cloud_autoconnect') or not credentials_file().exists() or \
            _connection().get('state') not in ('not running', 'stopped'):
        return None
    folder = Path(str(payload.get('folder') or ctx.folder))
    log = state_file().with_name('connect.log')
    home.mkdir_private(log.parent)
    options: dict[str, Any] = {'start_new_session': True} if os.name != 'nt' else \
        {'creationflags': getattr(subprocess, 'CREATE_NEW_PROCESS_GROUP', 0) | getattr(subprocess, 'DETACHED_PROCESS', 0)}
    descriptor = os.open(log, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    with os.fdopen(descriptor, 'ab') as written:
        process = subprocess.Popen([sys.executable, '-m', 'metaform', 'cloud', 'connect'], cwd=folder,
                                   stdin=subprocess.DEVNULL, stdout=written, stderr=written, env=child_environment(),
                                   **options)
    return {'cloud': 'connecting', 'pid': process.pid}


CLI: tuple[Any, ...] = ('cli',)
WHERE = ('cloud_url', 'cloud_instance')

MODULE = Module(
    id='cloud',
    summary='Reach this Metaform from cloud AI tools, ChatGPT and Claude, through your account at metaform.ing.',
    purpose='Signs this machine in to your account at metaform.ing and carries MCP from cloud AI tools to it over an '
            'outbound tunnel, with no port opened. The person\'s commands only. Details: metaform help cloud.',
    details='login signs this machine in with a code and your passkey; connect opens the tunnel; status shows the '
            'account and connection; logout revokes this machine\'s sign-in; audit reads the local record of what '
            'cloud AI tools called. Then add https://metaform.ing/mcp as a connector in ChatGPT or Claude. Design: '
            'docs/guides/metaform-node.md.',
    verbs=(
        Verb('login', sign_in, 'Sign this machine in to your account at the cloud broker: a code here, your passkey there.',
             switches=WHERE, surfaces=CLI, open_world=True,
             examples=(('metaform cloud login', 'Sign in as the instance named default.'),
                       ('metaform cloud login --cloud-instance laptop', 'Sign in as a second machine.'))),
        Verb('connect', connect, 'Open the tunnel, so cloud AI tools reach this Metaform until stopped.',
             switches=(*WHERE, 'cloud_capability', 'cloud_audit'), surfaces=CLI, open_world=True, transport=True),
        Verb('status', status, 'Show the account, the instance, the connection and the URL to give an AI tool.',
             surfaces=CLI, effect='read'),
        Verb('logout', sign_out, 'Revoke this machine\'s sign-in at the broker and forget it here.', surfaces=CLI,
             effect='remove', open_world=True),
        Verb('audit', audit_read, 'Read the local record of what cloud AI tools called here.',
             nouns=(Noun('lines', 'How many of the latest calls.', kind='int', required=False),), surfaces=CLI,
             effect='read'),
    ),
    subscriptions=(Subscription('web.started', web_started),),
)
