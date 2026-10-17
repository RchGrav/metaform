"""Who is asking: the person, or an agent acting in their home, CLI-011 and MCP-006.

A person-only setting and an operation that is the person's decision (clearing the project, switching or removing its
map, discarding an intake, deleting memories) are refused to an agent. Who the caller is was read from METAFORM_ROLE,
which an agent can clear in its own shell (`METAFORM_ROLE= metaform set ...`), and on the page from the Origin header,
which any process can send. Here it is read from facts the agent's own process does not control:

- The identity names a runner sets on its agent (METAFORM_ROLE, METAFORM_SESSION, METAFORM_WORK, METAFORM_NODE): set,
  they make the caller an agent. They can only add restriction, never remove it.
- The process's ancestors, as the kernel keeps them (Linux, `/proc/<pid>/stat`): a caller started, however
  indirectly, by a Metaform dispatch runner, a Metaform MCP server or an AI tool (Claude Code, Codex, Gemini CLI and
  the ACP adapters) is that agent's, when that ancestor works in the same Metaform home. An agent cannot change who
  started it. The home is compared so a test run an agent starts in a scratch home still exercises the person's
  flows there; the ancestor's home is read from its own environment as the kernel holds it.
- A command the web server runs for a person it has judged (the page, `peer_agent`) is vouched for: the server passes
  a secret only it knows, and the command checks that its parent is the server whose secret it holds.

What this does not stop: an agent that writes the home's files itself, imports Metaform's library in its own Python,
or starts a process through a long-running service outside its own tree (systemd-run, a terminal multiplexer's server,
the hold tool). Those are deliberate attacks on files the agent can reach as the same user; a boundary against them is
the command sandbox's. Outside Linux the ancestors are not read, so only the identity names count there.
"""
from __future__ import annotations

import hashlib
import ipaddress
import os
import secrets
import sys
from pathlib import Path

from . import home
from .errors import PersonsDecision

IDENTITY = ('METAFORM_ROLE', 'METAFORM_SESSION', 'METAFORM_WORK', 'METAFORM_NODE')  # what a runner sets, BASE-052
VOUCH = 'METAFORM_PAGE_VOUCH'  # the web server's secret, given to a command it runs for the person it judged
# The AI tools whose processes are agents, by the name they run as: the harnesses and the ACP adapters dispatch runs.
HARNESSES = frozenset({
    'claude', 'claude-code', 'claude-agent-acp', 'claude-code-acp', 'codex', 'codex-acp', 'gemini', 'gemini-cli',
    'opencode', 'cursor-agent', 'aider', 'goose', 'qwen', 'amp', 'copilot', 'crush', 'cline', 'droid', 'auggie'})
# Programs that run another by its path or package name, whose next arguments name the program they run.
LAUNCHERS = frozenset({'node', 'nodejs', 'bun', 'deno', 'npx', 'npm', 'pnpm', 'pnpx', 'yarn', 'bunx', 'uv', 'uvx'})
DEPTH = 64  # ancestors read at most; a tree deeper than this is unusual and its top is the system's


def persons_decision(caution: str, command: str, page: str | None = None) -> PersonsDecision:
    """The refusal an agent gets for an operation that is the person's decision: the caution, that it is theirs, and
    the exact command the person runs, with the page's control when there is one. It tells the agent how to ask the
    person, never how to confirm it itself."""
    said = (f"{caution.rstrip()} This is the person's decision, not an agent's: an agent's confirm does not run it. "
            'Tell the person what you propose and why; they run it themselves.')
    where = f' or use {page} on the page' if page else ''
    return PersonsDecision(said, f'the person runs: {command}{where}')


def agent() -> str | None:
    """Why this process acts for an agent, in a few words; None when it acts for the person."""
    named = [name for name in IDENTITY if os.environ.get(name)]
    if named:
        return f'{named[0]} is set'
    if vouched():
        return None
    return _agent_above(os.getpid(), _same(home.home()))


def peer_agent(pid: int | None, served: Path) -> str | None:
    """Why the process `pid`, the other end of a connection to the web server, acts for an agent of the home
    `served`; None when it does not, or when it cannot be found, such as a browser on another system."""
    if pid is None:
        return None
    environ = _environ(pid)
    named = [name for name in IDENTITY if environ is not None and environ.get(name)]
    if named:
        return f'{named[0]} is set on process {pid}'
    return _agent_above(pid, _same(served))


def _same(path: Path) -> str:
    try:
        return str(path.expanduser().resolve())
    except OSError:
        return str(path)


def _agent_above(pid: int, own_home: str) -> str | None:
    """The first agent process at `pid` or above it working in the home `own_home`, named, else None."""
    if not sys.platform.startswith('linux'):
        return None
    seen = 0
    while pid > 1 and seen < DEPTH:
        seen += 1
        argv = _argv(pid)
        what = agent_process(argv) if argv else None
        if what is not None:
            environ = _environ(pid)
            if environ is None or _home_of(environ) == own_home:  # unreadable counts as the same home
                return f'{what} (process {pid})'
        parent = _parent(pid)
        if parent is None or parent == pid:
            return None
        pid = parent
    return None


def agent_process(argv: list[str]) -> str | None:
    """What agent a process is, from its arguments: a Metaform dispatch runner, a Metaform MCP server, or an AI tool
    named in HARNESSES; None for any other."""
    words = [_name(word) for word in argv]
    if 'metaform' in words:
        rest = words[words.index('metaform') + 1:]
        if any(rest[at:at + 2] == ['dispatch', 'run'] for at in range(len(rest))):
            return 'a Metaform dispatch runner'
        if any(rest[at:at + 2] == ['mcp', 'serve'] for at in range(len(rest))):
            return 'a Metaform MCP server'
    if not words:
        return None
    if words[0] in HARNESSES:
        return words[0]
    if words[0] in LAUNCHERS or words[0].startswith('python'):
        for word in argv[1:4]:
            for part in word.replace('\\', '/').split('/'):
                if _name(part) in HARNESSES:
                    return _name(part)
    return None


def _name(word: str) -> str:
    """A program's name from one argument: its last path part, without a version or an extension."""
    last = word.replace('\\', '/').rstrip('/').rsplit('/', 1)[-1]
    if '@' in last[1:]:
        last = last[0] + last[1:].split('@', 1)[0]
    for suffix in ('.js', '.mjs', '.cjs', '.exe', '.cmd', '.py'):
        last = last.removesuffix(suffix)
    return last.lstrip('@').lower()


def _argv(pid: int) -> list[str]:
    try:
        raw = Path(f'/proc/{pid}/cmdline').read_bytes()
    except OSError:
        return []
    return [part.decode('utf-8', 'replace') for part in raw.split(b'\0') if part]


def _environ(pid: int) -> dict[str, str] | None:
    try:
        raw = Path(f'/proc/{pid}/environ').read_bytes()
    except OSError:
        return None
    found: dict[str, str] = {}
    for part in raw.split(b'\0'):
        name, equals, value = part.decode('utf-8', 'replace').partition('=')
        if equals:
            found[name] = value
    return found


def _home_of(environ: dict[str, str]) -> str:
    """The Metaform home a process works in, from its environment, as `home.home()` reads it."""
    given = environ.get('METAFORM_HOME')
    if given:
        return _same(Path(given))
    user = environ.get('HOME')
    return _same(Path(user) / '.metaform') if user else _same(Path.home() / '.metaform')


def _parent(pid: int) -> int | None:
    try:
        stat = Path(f'/proc/{pid}/stat').read_text(encoding='utf-8', errors='replace')
    except OSError:
        return None
    fields = stat[stat.rfind(')') + 2:].split()  # the name in parentheses may hold spaces
    try:
        return int(fields[1])
    except (IndexError, ValueError):
        return None


# ------------------------------------------------------------------------------------- the web server's vouch

def _vouch_file(secret: str) -> Path:
    return home.home() / 'run' / 'vouch' / hashlib.sha256(secret.encode('utf-8')).hexdigest()


class Vouch:
    """The web server's secret: made when it starts, held in its memory, and kept on disk only as its hash beside the
    server's process id, so a command the server runs for the person can show it was the server that ran it."""

    def __init__(self) -> None:
        self.secret = secrets.token_hex(32)
        self.path = _vouch_file(self.secret)
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            descriptor = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(descriptor, 'w', encoding='utf-8') as file:
                file.write(str(os.getpid()))
        except OSError:
            pass  # without it the server's commands are judged by their ancestors, as any other command is

    def environment(self) -> dict[str, str]:
        return {VOUCH: self.secret}

    def close(self) -> None:
        try:
            self.path.unlink()
        except OSError:
            pass


def vouched() -> bool:
    """Whether this process was run by the web server for the person: it holds the server's secret, and the server
    that wrote that secret's hash is its parent."""
    secret = os.environ.get(VOUCH)
    if not secret:
        return False
    try:
        written = _vouch_file(secret).read_text(encoding='utf-8').strip()
    except OSError:
        return False
    return written.isdigit() and int(written) == os.getppid()


# --------------------------------------------------------------------------------- the page's connection's process

def peer_pid(client: tuple[str, int], local: tuple[str, int]) -> int | None:
    """The process at the other end of a TCP connection this process accepted: `client` is its address and port as
    the server saw them, `local` the server's own end. Linux only, from /proc/net/tcp and each process's open files;
    None elsewhere, or when the process is not this user's or cannot be found."""
    if not sys.platform.startswith('linux'):
        return None
    inode = _inode(client, local)
    if inode is None:
        return None
    wanted = f'socket:[{inode}]'
    for entry in os.scandir('/proc'):
        if not entry.name.isdigit():
            continue
        try:
            for opened in os.scandir(f'/proc/{entry.name}/fd'):
                if os.readlink(opened.path) == wanted:
                    return int(entry.name)
        except OSError:
            continue
    return None


def _hex(host: str, port: int, six: bool) -> str | None:
    """An address as /proc/net/tcp writes it: the address's 32-bit words each in the machine's own byte order."""
    try:
        address = ipaddress.ip_address(host.split('%', 1)[0])
    except ValueError:
        return None
    if six:
        if address.version == 4:
            address = ipaddress.IPv6Address(f'::ffff:{address}')
        packed = address.packed
    else:
        if address.version == 6:
            mapped = getattr(address, 'ipv4_mapped', None)
            if mapped is None:
                return None
            address = mapped
        packed = address.packed
    words = [packed[at:at + 4] for at in range(0, len(packed), 4)]
    order = 'little' if sys.byteorder == 'little' else 'big'
    return ''.join(f'{int.from_bytes(word, order):08X}' for word in words) + f':{port:04X}'


def _inode(client: tuple[str, int], local: tuple[str, int]) -> str | None:
    for name, six in (('tcp', False), ('tcp6', True)):
        near, far = _hex(client[0], int(client[1]), six), _hex(local[0], int(local[1]), six)
        if near is None or far is None:
            continue
        try:
            lines = Path(f'/proc/net/{name}').read_text(encoding='ascii', errors='replace').splitlines()[1:]
        except OSError:
            continue
        for line in lines:
            fields = line.split()
            if len(fields) > 9 and fields[1] == near and fields[2] == far:
                return fields[9]
    return None
