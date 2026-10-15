"""The phone's self-check: where Twilio sends the number's calls and texts, whether that is where the bridge serves,
and whether that address answers, each problem said plainly with the one step that fixes it.

It reads the number from Twilio's REST API with a GET, which changes nothing. Only `fix`, which the person asks for
with `metaform twilio check fix=true`, changes the number, and only to the address the bridge serves when that address
answers. A temporary quick tunnel, such as a trycloudflare.com address, is flagged wherever it is found: it stops
answering when its tunnel closes, as the one that left every call hearing Twilio's "application error" did on
2026-10-15.
"""
from __future__ import annotations

import hashlib
import ipaddress
import json
import shutil
import socket
import ssl
import subprocess
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast
from urllib.parse import urlsplit

from metaform.module import Stop

from . import api

# Hosts whose names belong to one run of a tunnel and change with the next: Cloudflare's quick tunnels, localtunnel,
# localhost.run.
TEMPORARY = ('trycloudflare.com', 'loca.lt', 'lhr.life')
PROBE_TIMEOUT = 5  # seconds an address has to answer
FIX = 'metaform twilio check fix=true'
SAID = {'voice': ('calls', "every call hears Twilio's application error"),
        'sms': ('texts', 'your texts get no answer')}
# Where the check asks this machine's public address, only on a direct route: one line of plain text, the address.
PUBLIC_IP = 'https://checkip.amazonaws.com'
PORT = 7441  # the bridge's port, the module's PORT

Probe = Callable[[str, bool], str | None]
# A direct route's problem with the public address, and its one next step; None when the address is not this machine
# or the bridge answers there.
Direct = Callable[[str, str], tuple[str, str] | None]


@dataclass(frozen=True)
class Setup:
    """What the check compares Twilio's side with: the Twilio number, shown masked; the public address the bridge
    serves, the running bridge's own when it runs here, else twilio_public_url; whether the bridge runs here and the
    phone is on; and the address it listens on, twilio_bind, which is a direct route when it is not loopback."""
    number: str
    shown: str
    public: str
    running: bool
    enabled: bool
    bind: str = '127.0.0.1'


def loopback(bind: str) -> bool:
    try:
        return ipaddress.ip_address(bind).is_loopback
    except ValueError:
        return bind == 'localhost'


def wsl_nat() -> bool:
    """Whether this is WSL2 with its default NAT networking, where a port Windows does not forward never reaches Linux.
    Mirrored networking shares Windows's addresses, so a forwarded port arrives as it would on Windows."""
    try:
        version = Path('/proc/version').read_text(encoding='utf-8').lower()
    except OSError:
        return False
    if 'microsoft' not in version or 'wsl2' not in version:
        return False
    found = shutil.which('wslinfo')
    if found:
        try:
            mode = subprocess.run([found, '--networking-mode'], capture_output=True, text=True, timeout=5, check=False)
        except (OSError, subprocess.SubprocessError):
            return True
        return mode.stdout.strip().lower() != 'mirrored'
    return True


WSL_STEP = ('; under WSL2, turn on mirrored networking (networkingMode=mirrored in .wslconfig) or, on Windows, '
            f'netsh interface portproxy add v4tov4 listenport={PORT} connectport={PORT} connectaddress=<WSL address>')


def own_addresses() -> set[str]:
    """This machine's addresses: its interfaces' and the public one the internet sees it from, which a router in front
    of it holds; the public one is asked of PUBLIC_IP, and left out when that does not answer."""
    found: set[str] = set()
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None):
            found.add(str(info[4][0]))
    except OSError:
        pass
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:  # the address the default route leaves from
        try:
            probe.connect(('192.0.2.1', 9))  # a documentation address; nothing is sent
            found.add(str(probe.getsockname()[0]))
        except OSError:
            pass
    try:
        with urllib.request.urlopen(PUBLIC_IP, timeout=PROBE_TIMEOUT) as answer:
            found.add(answer.read(64).decode('ascii', 'replace').strip())
    except (OSError, ValueError):
        pass
    return found


def direct(public: str, bind: str, *, mine: Callable[[], set[str]] = own_addresses,
           nat: Callable[[], bool] = wsl_nat) -> tuple[str, str] | None:
    """On a direct route, the bridge on a non-loopback twilio_bind with the person's router or firewall forwarding a
    port to it: when twilio_public_url names this machine, what keeps the bridge from answering there, as a closed
    port, a failed TLS handshake or a certificate Twilio would refuse, with its one next step. None when it is not a
    direct route, the address is not this machine, or the bridge answers there."""
    if loopback(bind):
        return None
    parts = urlsplit(public)
    host, port = parts.hostname or '', parts.port or 443
    try:
        resolved = {str(info[4][0]) for info in socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)}
    except OSError:
        return None
    here = resolved & mine()
    if not here:
        return None
    address = min(here)
    try:
        raw = socket.create_connection((address, port), timeout=PROBE_TIMEOUT)
    except OSError as error:
        return (f'The port {port} of {host} ({address}) is closed: {error.strerror or error}.',
                (f'forward TCP port {port} on your router or firewall to port {PORT} of this machine'
                 + (WSL_STEP if nat() else '')))
    with raw:
        try:
            with ssl.create_default_context().wrap_socket(raw, server_hostname=host):
                return None
        except ssl.SSLCertVerificationError as error:
            return (f'The bridge at {host}:{port} shows a certificate Twilio would refuse: {error.verify_message}.',
                    (f'set twilio_certificate to a PEM for {host} from a public CA, its chain and key in one file, '
                     'such as Let\'s Encrypt\'s fullchain.pem and privkey.pem joined'))
        except (ssl.SSLError, OSError) as error:
            return (f'The bridge at {host}:{port} does not speak TLS: {error}.',
                    ('metaform set --twilio-certificate <PEM with the chain and key>, or put your TLS terminator in '
                     'front of it'))


def findings(report: dict[str, Any]) -> str:
    """What the report found, as a short fingerprint that changes only when its problems do; its time is left out."""
    said = [(one['problem'], one['next']) for one in cast(list[dict[str, str]], report.get('problems') or [])]
    return hashlib.sha256(json.dumps(said).encode()).hexdigest()[:16]


def temporary(url: str) -> bool:
    host = (urlsplit(url).hostname or '').lower()
    return any(host == name or host.endswith('.' + name) for name in TEMPORARY)


def answers(url: str, health: bool) -> str | None:
    """None when `url` answers, else why not, in words. With `health` it must answer 200, as the bridge's
    /phone/health does; otherwise any answer below 500 says something serves there. A GET, which no webhook acts on."""
    request = urllib.request.Request(url, headers={'User-Agent': 'metaform-twilio-check'})
    try:
        with urllib.request.urlopen(request, timeout=PROBE_TIMEOUT) as answer:
            return None if not health or answer.status == 200 else f'it answered {answer.status}'
    except urllib.error.HTTPError as error:
        return None if not health and error.code < 500 else f'it answered {error.code}'
    except urllib.error.URLError as error:
        return f'it could not be reached: {error.reason}'
    except (OSError, ValueError) as error:
        return f'it could not be reached: {error}'


def expected(public: str) -> dict[str, str] | None:
    return {'voice': f'{public}/phone/voice', 'sms': f'{public}/phone/sms'} if public else None


def bridge_side(setup: Setup, probe: Probe,
                route: Direct = direct) -> tuple[bool, str | None, list[tuple[str, str]]]:
    """Whether the public address answers, why not, and what keeps the bridge from being reached there; on a direct
    route to this machine, the closed port, TLS failure or wrong certificate itself."""
    found: list[tuple[str, str]] = []
    why = probe(f'{setup.public}/phone/health', True) if setup.public else 'no address is set'
    if not setup.public:
        found.append(('twilio_public_url is not set, so the bridge has no address Twilio can reach.',
                      'metaform set --twilio-public-url https://<your node or tunnel>'))
    if why is None:
        return True, None, found
    named = route(setup.public, setup.bind) if setup.running and setup.public else None
    if named is not None:
        found.append(named)
    elif setup.running:
        host = urlsplit(setup.public).netloc
        found.append((f'The bridge runs here, but {setup.public}/phone/health does not answer: {why}.',
                       f'route https://{host}/phone/* to 127.0.0.1:7441, on your Node or your tunnel'))
    elif not setup.enabled:
        found.append(('The phone bridge is not running: the phone is off.',
                      'metaform set --twilio-enabled, then metaform web start'))
    else:
        found.append(('The phone bridge is not running' + (f', and {setup.public}/phone/health does not answer: {why}.'
                                                            if setup.public else '.'), 'metaform twilio serve'))
    return False, why, found


def _wrong(kind: str, url: str, app: str, wanted: dict[str, str] | None, why: str | None) -> str | None:
    """What is wrong with where the number sends one kind, its calls or its texts, in words; None when it is the
    bridge's address and that answers. `why` is why `url` does not answer, None when it does."""
    what, so = SAID[kind]
    if app:
        return f'Your Twilio number sends its {what} to the TwiML App {app}, not to the bridge.'
    if not url:
        return f'Your Twilio number sends its {what} nowhere: its {kind} address is empty.'
    if why is not None:
        return f'Your Twilio number sends its {what} to {url}, which does not answer ({why}), so {so}.'
    if wanted is None:
        return (f'Your Twilio number sends its {what} to {url}, and twilio_public_url is not set to say whether that is '
                'the bridge.')
    if url == wanted[kind]:
        return None
    return f'Your Twilio number sends its {what} to {url}, not to the bridge at {wanted[kind]}.'


def check(setup: Setup, client: api.Client, probe: Probe = answers, route: Direct = direct) -> dict[str, Any]:
    """What is wrong between the number and the bridge, the symptom first, each with its one fix, and what is only
    temporary. Reads only."""
    reached, why, bridge = bridge_side(setup, probe, route)
    wanted = expected(setup.public)
    # the one step that fixes the number: fix=true once the bridge answers, else the bridge's own first fix
    next_step = FIX if reached and wanted else bridge[0][1] if bridge else 'metaform twilio status'
    problems: list[tuple[str, str]] = []
    warnings: list[str] = []
    found: dict[str, str | None] | None = None
    record: dict[str, Any] | None = None
    if not setup.number:
        problems.append(('No Twilio number is set, so there is nothing to check.',
                         'metaform set --twilio-number +15551234567'))
    else:
        try:
            record = client.number(setup.number)
        except OSError as error:
            problems.append((f"The number's addresses could not be read from Twilio: {error}", 'metaform twilio status'))
        else:
            if record is None:
                problems.append((f'Twilio has no number {setup.shown} on this account.',
                                 'metaform set --twilio-number <a number on your account>'))
    if record is not None:
        found = {}
        heard: dict[str, str | None] = {}  # each address asked once, though calls and texts share it
        for kind in ('voice', 'sms'):
            url = str(record.get(f'{kind}_url') or '')
            found[kind] = url or None
            ours = wanted is not None and url == wanted[kind]
            if url and not ours and url not in heard:
                heard[url] = probe(url, False)
            said = _wrong(kind, url, str(record.get(f'{kind}_application_sid') or ''), wanted,
                          why if ours else heard.get(url))
            if said is not None:
                problems.append((said, next_step))
            if url and not ours and temporary(url):  # the bridge's own address is flagged once, below
                warnings.append(f'{url} is a temporary quick tunnel: it stops answering when its tunnel closes, '
                                'and the next tunnel has another address.')
    if setup.public and temporary(setup.public):
        warnings.append(f'twilio_public_url, {setup.public}, is a temporary quick tunnel: a number pointed there stops '
                        'working when the tunnel closes. A lasting address, such as your Node, keeps working.')
    if not loopback(setup.bind) and wsl_nat():
        warnings.append(f'This is WSL2 with NAT networking, so a port forwarded to this machine reaches Windows, not '
                        f'the bridge on {setup.bind}:{PORT}' + WSL_STEP + '.')
    problems += bridge
    return {
        'ok': not problems, 'checked': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'number': setup.shown or None,
        'number_urls': found, 'bridge': {'public_url': setup.public or None, 'answers': reached if setup.public else None,
                                         'why_not': why if setup.public else None, 'running_here': setup.running},
        'expected': wanted,
        'problems': [{'problem': problem, 'next': step} for problem, step in problems],
        'warnings': list(dict.fromkeys(warnings)),
    }


def fix(setup: Setup, client: api.Client, probe: Probe = answers, route: Direct = direct) -> dict[str, Any]:
    """Point the number's voice and SMS addresses at the bridge's, as the person asked, and only when the bridge answers
    there; then read them back and check again. Refuses, changing nothing, when there is no address or it does not
    answer, since a number pointed there would answer every call with Twilio's application error."""
    reached, why, bridge = bridge_side(setup, probe, route)
    wanted = expected(setup.public)
    if wanted is None or not reached:
        said = 'twilio_public_url is not set' if wanted is None else f'{setup.public}/phone/health does not answer: {why}'
        raise Stop(f'The number was not changed: {said}, and a number pointed there would answer every call with '
                   "Twilio's application error.", bridge[0][1] if bridge else 'metaform twilio check')
    record = client.number(setup.number) if setup.number else None
    if record is None:
        raise Stop(f'Twilio has no number {setup.shown or "set"} on this account, so nothing was changed.',
                   'metaform twilio check')
    was = {kind: str(record.get(f'{kind}_url') or '') or None for kind in ('voice', 'sms')}
    apps = any(record.get(f'{kind}_application_sid') for kind in ('voice', 'sms'))
    changed = apps or was != wanted
    if changed:
        client.point(str(record['sid']), voice=wanted['voice'], sms=wanted['sms'], apps=apps)
    after = check(setup, client, probe, route)
    return {**after, 'fixed': {'changed': changed, 'was': was, 'now': cast(dict[str, Any], after['number_urls'])}}


def headline(report: dict[str, Any]) -> str | None:
    """The report's first problem and its fix in one line, as a notice says it; None when nothing is wrong."""
    problems = cast(list[dict[str, str]], report.get('problems') or [])
    if not problems:
        return None
    more = f' ({len(problems) - 1} more: metaform twilio check)' if len(problems) > 1 else ''
    return f'{problems[0]["problem"]} Next: {problems[0]["next"]}{more}'
