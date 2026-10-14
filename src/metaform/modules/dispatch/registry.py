"""registry: the ACP Registry, where dispatch finds agents and pins the exact version it starts, P013 and P030.

The ACP Registry is the curated list of ACP agents an ACP client can install, each entry an `agent.json` with an id, a
semantic version and how it is distributed: an npm package run with `npx`, a PyPI package run with `uvx`, or a binary
archive per platform. Read 2026-10-12: agentclientprotocol.com/get-started/registry; the registry itself,
https://cdn.agentclientprotocol.com/registry/v1/latest/registry.json; its schema, agent.schema.json, and its
CONTRIBUTING.md at github.com/agentclientprotocol/registry, whose CI checks every entry against the schema, refuses
`latest`, and requires each distribution to name the entry's version.

A pin is `<id>@<version>`, kept in the person's `dispatch_registry_agents` setting. The registry's `latest` file moves
on every hour, so pinning keeps the entry as it was when it was pinned, in the Metaform home under
`agents/<id>/<version>/agent.json`, with a binary agent's archive checked against its sha256 and unpacked beside it.
The agent then starts from that snapshot, the same version on every start, until the person pins another.

Claude Code, Codex and Gemini CLI are dispatch's own agents, their `dispatch_<agent>` commands pinned to the registry's
versions of claude-acp, codex-acp and gemini; `upgrades` names a newer registry version of each without changing what
the person set.

`publication` writes the entry that would publish `metaform dispatch serve` to the registry, for review: it is checked
against the registry's own schema and its CI rules, and never submitted; publishing is a pull request the person opens.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import platform as host
import re
import shlex
import shutil
import stat
import subprocess
import tarfile
import time
import urllib.parse
import urllib.request
import zipfile
from importlib import resources
from pathlib import Path
from typing import Any, cast

from metaform import home
from metaform.module import Stop

URL = 'https://cdn.agentclientprotocol.com/registry/v1/latest/registry.json'
BUILTIN = {'claude': 'claude-acp', 'codex': 'codex-acp', 'gemini': 'gemini'}  # dispatch's own agents, by registry id
CACHE = 'acp-registry.json'  # the registry as last read, in the Metaform home
FOLDER = 'agents'  # the pinned entries and unpacked binaries, in the Metaform home
FETCH_LIMIT = 30.0  # seconds one read of the registry or one download may take
ARCHIVES = ('.zip', '.tar.gz', '.tgz', '.tar.bz2', '.tbz2')  # what the registry allows; anything else is a raw binary
INSTALLERS = ('.dmg', '.pkg', '.deb', '.rpm', '.msi', '.appimage')  # what it refuses
ID = re.compile(r'^[a-z][a-z0-9-]*$')
SEMVER = re.compile(r'^[0-9]+\.[0-9]+\.[0-9]+$')
PIN = re.compile(r'^(?P<id>[a-z][a-z0-9-]*)@(?P<version>[0-9]+\.[0-9]+\.[0-9]+(?:-[0-9A-Za-z.-]+)?)$')
SHA256 = re.compile(r'^[a-fA-F0-9]{64}$')
COLOUR = re.compile(r'''(?:fill|stroke)\s*[=:]\s*["']?(?!currentColor|none|inherit)[#a-zA-Z(]''')


def platform() -> str:
    """This system as the registry names a binary's target: darwin-aarch64, linux-x86_64, windows-x86_64 and so on."""
    system = {'darwin': 'darwin', 'linux': 'linux', 'windows': 'windows'}.get(host.system().lower(), host.system().lower())
    machine = host.machine().lower()
    arch = {'arm64': 'aarch64', 'aarch64': 'aarch64', 'amd64': 'x86_64', 'x86_64': 'x86_64', 'x64': 'x86_64'}.get(
        machine, machine)
    return f'{system}-{arch}'


def _fetch(url: str) -> bytes:
    """The bytes at a registry or archive URL: https, or a local file by file:// URL or path, for a private mirror."""
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme in ('http', 'https'):
        request = urllib.request.Request(url, headers={'User-Agent': 'metaform-dispatch'})
        with urllib.request.urlopen(request, timeout=FETCH_LIMIT) as answer:  # http(s) only, above
            return cast(bytes, answer.read())
    path = Path(urllib.request.url2pathname(parsed.path)) if parsed.scheme == 'file' else Path(url).expanduser()
    return path.read_bytes()


def read(url: str = URL, *, max_age: float = 86_400.0, refresh: bool = False) -> dict[str, Any]:
    """The registry: the copy kept in the home while it is younger than `max_age` seconds and from the same URL,
    otherwise read again and kept. A registry that cannot be read falls back to the kept copy, said as stale, and with
    none kept, stops with the setting that names where it is read from."""
    kept_at = home.home() / CACHE
    kept: dict[str, Any] | None = None
    try:
        found: Any = json.loads(kept_at.read_text(encoding='utf-8'))
        kept = cast(dict[str, Any], found) if isinstance(found, dict) else None
    except (OSError, ValueError):
        kept = None
    fresh = kept is not None and kept.get('url') == url and time.time() - float(kept.get('fetched') or 0) < max_age
    if kept is not None and fresh and not refresh:
        return {**cast(dict[str, Any], kept['registry']), 'fetched': kept['fetched'], 'url': url, 'stale': False}
    try:
        registry: Any = json.loads(_fetch(url))
        if not isinstance(registry, dict) or not isinstance(cast(dict[str, Any], registry).get('agents'), list):
            raise ValueError('it holds no agents list')  # noqa: TRY004  a bad registry is read as bad JSON is
    except (OSError, ValueError) as error:
        if kept is not None and kept.get('url') == url:
            return {**cast(dict[str, Any], kept['registry']), 'fetched': kept['fetched'], 'url': url, 'stale': True,
                    'error': str(error)}
        raise Stop(f'The ACP Registry could not be read from {url}: {error}.',
                   'metaform set --dispatch-registry-url "<url or file>"') from None
    now = time.time()
    home.mkdir_private(kept_at.parent)
    home.write_private(kept_at, json.dumps({'url': url, 'fetched': now, 'registry': registry}))
    return {**cast(dict[str, Any], registry), 'fetched': now, 'url': url, 'stale': False}


def entries(registry: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """The registry's agents by id, each entry as it is written."""
    found: dict[str, dict[str, Any]] = {}
    for one in cast(list[Any], registry.get('agents') or []):
        if isinstance(one, dict) and isinstance(cast(dict[str, Any], one).get('id'), str):
            found[str(cast(dict[str, Any], one)['id'])] = cast(dict[str, Any], one)
    return found


def _package_pinned(kind: str, package: str, version: str) -> bool:
    """Whether a package distribution names exactly the entry's version, as the registry's CI checks it: npm
    `name@1.2.3`, PyPI `name==1.2.3` or `name@1.2.3`."""
    if kind == 'npx':
        return package.rpartition('@')[2] == version and package.rpartition('@')[0] not in ('', '@')
    return package.endswith((f'=={version}', f'@{version}'))


def way(entry: dict[str, Any], *, system: str | None = None) -> tuple[str, dict[str, Any]] | None:
    """How this system starts an entry: npx, then uvx, while its launcher is found on PATH, then the binary built for
    this platform; None when none of them can run here."""
    given = cast(dict[str, Any], entry.get('distribution') or {})
    for kind, launcher in (('npx', 'npx'), ('uvx', 'uvx')):
        spec = given.get(kind)
        if isinstance(spec, dict) and shutil.which(launcher) is not None:
            return kind, cast(dict[str, Any], spec)
    binary = cast(dict[str, Any], given.get('binary') or {})
    target = binary.get(system or platform())
    if isinstance(target, dict):
        return 'binary', cast(dict[str, Any], target)
    return None


def folder_of(agent: str, version: str) -> Path:
    return home.home() / FOLDER / agent / version


def snapshot(agent: str, version: str) -> dict[str, Any] | None:
    """The entry as it was pinned, with how it starts here; None when this version was never pinned on this system."""
    try:
        found: Any = json.loads((folder_of(agent, version) / 'pin.json').read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None
    return cast(dict[str, Any], found) if isinstance(found, dict) else None


def _unpacked(data: bytes, archive: str, into: Path) -> None:
    """An archive unpacked into its folder, nothing written outside it: tar through the standard library's data
    filter, which refuses absolute paths, links out of the folder and device files; zip by checking every name."""
    name = urllib.parse.urlparse(archive).path.lower()
    if name.endswith(('.tar.gz', '.tgz', '.tar.bz2', '.tbz2')):
        def private_member(member: tarfile.TarInfo, destination: str) -> tarfile.TarInfo:
            filtered = tarfile.data_filter(member, destination)
            target = into / filtered.name
            home.mkdir_private(target.parent)
            if filtered.isfile():
                home.write_private(target, b'')
            elif filtered.isdir():
                home.mkdir_private(target)
            if os.name != 'nt' and not filtered.issym() and not filtered.islnk():
                filtered.mode = 0o700 if filtered.isdir() else 0o600 | ((filtered.mode or 0) & stat.S_IXUSR)
            return filtered

        with tarfile.open(fileobj=io.BytesIO(data), mode='r:*') as packed:
            packed.extractall(into, filter=private_member)
        return
    if name.endswith('.zip'):
        root = into.resolve()
        with zipfile.ZipFile(io.BytesIO(data)) as packed:
            for member in packed.namelist():
                target = (into / member).resolve()
                if root != target and root not in target.parents:
                    raise Stop(f'The archive {archive} names {member}, outside its folder; it is not unpacked.',
                               'metaform dispatch registry')
            for member in packed.infolist():
                target = into / member.filename
                if member.is_dir():
                    home.mkdir_private(target)
                else:
                    home.mkdir_private(target.parent)
                    descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
                    with os.fdopen(descriptor, 'wb') as output, packed.open(member) as source:
                        shutil.copyfileobj(source, output)
        return
    raw = into / Path(name).name  # a raw binary, kept under its own name
    home.write_private(raw, data)


def pin(entry: dict[str, Any], *, system: str | None = None) -> dict[str, Any]:
    """Pin an entry at its version: how it starts here, kept with the entry in the home; a binary is downloaded,
    checked against the sha256 the entry gives and unpacked. Refuses an entry whose distribution does not name its
    version exactly, an installer archive, and a checksum that does not match."""
    agent, version = str(entry.get('id') or ''), str(entry.get('version') or '')
    if not ID.fullmatch(agent) or not version:
        raise Stop(f'The registry entry {agent or "?"} has no usable id and version.', 'metaform dispatch registry')
    chosen = way(entry, system=system)
    if chosen is None:
        raise Stop(f'{agent} {version} offers nothing this system can run: no npx or uvx on PATH for its package, and '
                   f'no binary for {system or platform()}.', 'metaform dispatch registry')
    kind, spec = chosen
    into = folder_of(agent, version)
    home.mkdir_private(into)
    held: dict[str, Any] = {'agent': agent, 'version': version, 'kind': kind, 'entry': entry,
                            'args': [str(one) for one in cast(list[Any], spec.get('args') or [])],
                            'env': {str(key): str(value) for key, value in cast(dict[str, Any], spec.get('env') or {}).items()},
                            'pinned': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}
    if kind in ('npx', 'uvx'):
        package = str(spec.get('package') or '')
        if not _package_pinned(kind, package, version):
            raise Stop(f'{agent} {version} names {package}, not that exact version, so it cannot be pinned.',
                       'metaform dispatch registry')
        held['package'] = package
    else:
        archive = str(spec.get('archive') or '')
        if '/latest/' in archive or urllib.parse.urlparse(archive).path.lower().endswith(INSTALLERS):
            raise Stop(f'{agent} {version} offers {archive}, which the registry does not allow.',
                       'metaform dispatch registry')
        data = _fetch(archive)
        digest = hashlib.sha256(data).hexdigest()
        wanted = str(spec.get('sha256') or '')
        if wanted and digest.lower() != wanted.lower():
            raise Stop(f'{agent} {version}: the archive\'s sha256 is {digest}, not the {wanted} its entry gives; '
                       'nothing was installed.', 'metaform dispatch registry refresh=true')
        _unpacked(data, archive, into)
        cmd = (into / str(spec.get('cmd') or '')).resolve()
        if into.resolve() not in cmd.parents or not cmd.is_file():
            raise Stop(f'{agent} {version}: its command {spec.get("cmd")} is not in its archive.',
                       'metaform dispatch registry')
        cmd.chmod((cmd.stat().st_mode & 0o700) | stat.S_IXUSR if os.name != 'nt' else
                  cmd.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        held.update(path=str(cmd), sha256=digest, verified=bool(wanted))
    home.write_private(into / 'pin.json', json.dumps(held, indent=1))
    return held


def argv_of(held: dict[str, Any]) -> list[str]:
    """The words that start a pinned agent."""
    if held['kind'] == 'npx':
        return ['npx', '-y', str(held['package']), *held['args']]
    if held['kind'] == 'uvx':
        return ['uvx', str(held['package']), *held['args']]
    return [str(held['path']), *held['args']]


def command(agent: str, version: str) -> str:
    """The start command of a pinned agent, as a setting holds one; stops when this version was never pinned here."""
    held = snapshot(agent, version)
    if held is None:
        raise Stop(f'{agent} {version} is not installed on this system.', f'metaform dispatch registry add={agent}')
    words = argv_of(held)
    return subprocess.list2cmdline(words) if os.name == 'nt' else shlex.join(words)


def environment(agent: str, version: str) -> dict[str, str]:
    """The environment a pinned agent's entry asks for, such as a default model; empty for none. Never a METAFORM_
    variable: the session's identity is the runner's to give, BASE-052."""
    held = snapshot(agent, version)
    given = cast(dict[str, str], held.get('env') or {}) if held else {}
    return {key: value for key, value in given.items() if not key.upper().startswith('METAFORM_')}


def parse_pins(values: Any) -> dict[str, str]:
    """`id@version` pins as {id: version}; an entry that is not a pin is left out, the setting's check names it."""
    found: dict[str, str] = {}
    for value in cast(list[Any], values or []):
        matched = PIN.fullmatch(str(value).strip())
        if matched:
            found[matched['id']] = matched['version']
    return found


def check_pins(values: Any, folder: Path) -> list[str] | None:
    """The setting's check: each entry is `<id>@<version>`, never one of dispatch's own agents."""
    del folder
    for value in cast(list[Any], values or []):
        matched = PIN.fullmatch(str(value).strip())
        if not matched:
            from metaform.settings import SettingError
            raise SettingError(f'{value!r} is not a pin; each is <registry id>@<version>, such as goose@1.54.0.')
        if matched['id'] in BUILTIN or matched['id'] in BUILTIN.values():
            from metaform.settings import SettingError
            raise SettingError(f'{matched["id"]} is one of dispatch\'s own agents; set its command with '
                               f'--dispatch-<agent> instead.')
    return None


def builtin_command(agent: str, entry: dict[str, Any]) -> str | None:
    """The pinned start command of one of dispatch's own agents at an entry's version, its npx package; None when the
    entry offers none."""
    spec = cast(dict[str, Any], cast(dict[str, Any], entry.get('distribution') or {}).get('npx') or {})
    package = str(spec.get('package') or '')
    if not package:
        return None
    return shlex.join(['npx', '-y', package, *[str(one) for one in cast(list[Any], spec.get('args') or [])]])


# ------------------------------------------------------------------------------------------------ publication

ICON = ('<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 16 16">'
        '<path fill="currentColor" d="M2 2h3l3 5 3-5h3v12h-3V7l-3 5-3-5v7H2z"/></svg>\n')


def schema() -> dict[str, Any]:
    """The registry's agent.schema.json, as published at its $id and kept with this module."""
    text = (resources.files(__package__ or 'metaform.modules.dispatch') / 'resources' / 'registry' /
            'agent.schema.json').read_text(encoding='utf-8')
    return cast(dict[str, Any], json.loads(text))


def checked(entry: dict[str, Any], icon: str) -> list[str]:
    """What keeps an entry from passing the registry's CI: its schema, then the rules CONTRIBUTING.md lists that a
    schema cannot say (versions match, no `latest`, a monochrome 16x16 icon). Empty when nothing does. The URL checks,
    that each package or archive exists, need the network and the registry's own run."""
    problems: list[str] = []
    try:
        import jsonschema
    except ImportError:
        problems.append('jsonschema is not installed, so the entry was not checked against the registry schema')
    else:
        validator: Any = jsonschema.Draft7Validator(schema())
        problems += [f'{"/".join(str(part) for part in error.absolute_path) or "entry"}: {error.message}'
                     for error in validator.iter_errors(entry)]
    version = str(entry.get('version') or '')
    for kind, spec in cast(dict[str, Any], entry.get('distribution') or {}).items():
        if kind in ('npx', 'uvx'):
            package = str(cast(dict[str, Any], spec).get('package') or '')
            if package.endswith('@latest') or not _package_pinned(kind, package, version):
                problems.append(f'distribution/{kind}: {package} does not name version {version}')
        elif kind == 'binary':
            for target, given in cast(dict[str, Any], spec).items():
                archive = str(cast(dict[str, Any], given).get('archive') or '')
                if '/latest/' in archive:
                    problems.append(f'distribution/binary/{target}: {archive} names latest')
                if not SHA256.fullmatch(str(cast(dict[str, Any], given).get('sha256') or '')):
                    problems.append(f'distribution/binary/{target}: no sha256 pins the archive')
    if 'width="16"' not in icon or 'height="16"' not in icon or COLOUR.search(icon):
        problems.append('icon.svg: it must be 16x16 and monochrome, every fill and stroke currentColor or none')
    return problems


def publication(*, agent_id: str, name: str, version: str, description: str, package: str,
                repository: str | None, license_name: str | None, license_url: str | None,
                args: tuple[str, ...] = ('dispatch', 'serve')) -> dict[str, Any]:
    """The registry entry that publishes `metaform dispatch serve` as an ACP agent, run with uvx from its PyPI package,
    with its icon and what keeps it from passing the registry's checks. Nothing is sent anywhere."""
    entry: dict[str, Any] = {'id': agent_id, 'name': name, 'version': version, 'description': description}
    if repository:
        entry['repository'] = repository
    if license_name:
        entry['license'] = license_name
    if license_url:
        entry['license_url'] = license_url
    entry['distribution'] = {'uvx': {'package': f'{package}=={version}', 'args': list(args)}}
    return {'entry': entry, 'icon': ICON, 'problems': checked(entry, ICON)}
