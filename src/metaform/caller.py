"""Whose consent a call carries: the person's, or none, CLI-011 and MCP-006.

A person-only setting and an operation that is the person's decision (clearing the project, restoring it, switching
or removing its map, discarding an intake, deleting memories, changing what agents are sent, answering an agent's
permission request) run only on the person's consent. Round 1 (2026-10-17) judged the caller instead: an agent was
known by the identity its runner sets and by the processes above it, and every other process counted as the person.
One shell line, `( metaform ... & )`, re-parents a command to init, so nothing above it is an agent, and it passed
every guard, the page's included (UX review, person-consent F1). Who is above a process is a fact an agent can
change; that no process carries consent until the person gives it is not.

So no process has the person's authority by default. Consent comes only through a channel the person controls and an
agent does not drive in the ordinary course of its work:

- The person's own interactive terminal (`terminal`): the command has a controlling terminal, runs in that
  terminal's foreground, descends unbroken from the terminal's session leader (a command re-parented to init has lost
  who started it), and neither it nor the session leader was started by an agent of this home. An AI
  tool runs an agent's commands without a terminal (Claude Code's Bash tool starts each in a session of its own,
  with none); a tool that gives them a pseudo-terminal (Codex) started that terminal's session leader, and
  re-parenting a command changes neither its terminal nor its session.
- The page: a write the page sends with the key the web server put in that page's cookie when it served it, from a
  process not known as an agent's; the commands the server runs for it carry the server's vouch (`vouched`).
- The person's answer to a form their AI tool shows them, MCP elicitation (`modules/mcp/consent.py`), and, for a
  dispatched agent, to the consent card its runner shows in its chat on the page (dispatch's `consent`), which is
  answered only from the page, never at the map's node, where agents write.

The identity names a runner sets (METAFORM_ROLE, METAFORM_SESSION, METAFORM_WORK, METAFORM_NODE) and the processes
above a command or its session leader (`agent`) only take authority away; they never give it.

What this does not stop, since every agent runs as the person's own Unix user: an agent that deliberately builds one
of those channels itself. It can open a pseudo-terminal of its own in a new session and answer there (`setsid script
...`), or type into a terminal multiplexer the person uses (`tmux send-keys`); fetch the page to take its cookie and
send the write as the page would; run its own MCP client against `metaform mcp serve` and answer the form itself;
read a runner's control token from the store and answer its own card; or write the home's files, or import
Metaform's library, and so skip the checks. Each is a deliberate attack on files and processes the agent can reach as
the same user, never an ordinary command; a boundary against them is the command sandbox's (another user, or a
container without the home). On macOS the processes above a command are not read, so there the terminal and the
identity names decide. On Windows neither is read: only the identity names count there, as before this design, so a
command an agent runs with them cleared carries the person's consent; the page and the forms still ask the person.
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
VOUCH = 'METAFORM_PAGE_VOUCH'  # the web server's secret, given to a command it runs for a write from its own page
# The AI tools whose processes are agents, by the name they run as: the harnesses and the ACP adapters dispatch runs.
HARNESSES = frozenset({
    'claude', 'claude-code', 'claude-agent-acp', 'claude-code-acp', 'codex', 'codex-acp', 'gemini', 'gemini-cli',
    'opencode', 'cursor-agent', 'aider', 'goose', 'qwen', 'amp', 'copilot', 'crush', 'cline', 'droid', 'auggie'})
# Programs that run another by its path or package name, whose next arguments name the program they run.
LAUNCHERS = frozenset({'node', 'nodejs', 'bun', 'deno', 'npx', 'npm', 'pnpm', 'pnpx', 'yarn', 'bunx', 'uv', 'uvx'})
DEPTH = 64  # ancestors read at most; a tree deeper than this is unusual and its top is the system's


def persons_decision(caution: str, command: str, page: str | None = None) -> PersonsDecision:
    """The refusal an agent gets for an operation that is the person's decision: the caution, that it is theirs, how
    the agent asks them (`settings.asking`), and how the person gives it: the page's control when there is one, and
    the exact command they paste into their own terminal. It never says how an agent could confirm it itself."""
    from . import settings
    said, step = settings.asking()
    where = f'use {page} on the page, or ' if page else ''
    return PersonsDecision(f"{caution.rstrip()} This is the person's decision, not an agent's: no confirm of an "
                           f"agent's runs it. {said}", f'{step}{where}paste into {settings.TERMINAL}: {command}')


def unconsented() -> str | None:
    """Why this process does not carry the person's consent, in a few words; None when it does: the web server ran
    it for a write from its own page, or it runs at the person's own terminal and no agent started it."""
    if vouched():
        return None
    named = [name for name in IDENTITY if os.environ.get(name)]
    if named:
        return f'{named[0]} is set'
    return terminal()


def agent() -> str | None:
    """Why this process is known to act for an agent, in a few words; None when nothing says so. It only takes
    authority away: a process it does not name is not, for that, the person's (`unconsented`)."""
    named = [name for name in IDENTITY if os.environ.get(name)]
    if named:
        return f'{named[0]} is set'
    own = _same(home.home())
    return _agent_above(os.getpid(), own) or _leader_agent(os.getpid(), own)


def dispatched() -> str | None:
    """Why this process works for an agent Metaform dispatched, in a few words; None when nothing says so: an identity
    name its runner set, or, with those cleared, a dispatch runner of this home above it (Linux). A session the person
    runs outside dispatch is not dispatched, though it is no more the person's consent (`unconsented`)."""
    named = [name for name in IDENTITY if os.environ.get(name)]
    if named:
        return f'{named[0]} is set'
    if not sys.platform.startswith('linux'):
        return None
    own, pid, seen = _same(home.home()), os.getppid(), 0
    while pid > 1 and seen < DEPTH:
        seen += 1
        argv = _argv(pid)
        if argv and agent_process(argv) == 'a Metaform dispatch runner':
            environ = _environ(pid)
            if environ is None or _home_of(environ) == own:
                return f'a Metaform dispatch runner (process {pid}) is above it'
        parent = _parent(pid)
        if parent is None or parent == pid:
            return None
        pid = parent
    return None


def terminal() -> str | None:
    """Why this process is not at the person's own interactive terminal; None when it is: it has a controlling
    terminal, runs in that terminal's foreground, and neither it nor the terminal's session leader was started by an
    agent of this home (`agent`). On Windows neither is read, so there only the identity names count, as before."""
    if os.name != 'posix':
        return None
    return _at_tty() or agent()


def _at_tty() -> str | None:
    """Why this process is not in the foreground of a controlling terminal; None when it is."""
    try:
        descriptor = os.open('/dev/tty', os.O_RDWR | os.O_NOCTTY)
    except OSError:
        return 'it runs with no terminal, as an AI tool runs its commands'
    try:
        if os.tcgetpgrp(descriptor) != os.getpgrp():
            return 'it runs in the background of its terminal'
    except OSError:
        return 'its terminal cannot be read'
    finally:
        os.close(descriptor)
    if not _reaches_leader(os.getpid()):
        return 'it was detached from the terminal session that started it'
    return None


def _reaches_leader(pid: int) -> bool:
    """Whether the processes above `pid` lead, unbroken, to the leader of its session, as a command typed at a shell
    does: one re-parented to init or a subreaper (`( cmd & )`, nohup, disown) has lost who started it, and a shell
    without job control leaves it in the terminal's foreground. True where the processes are not read."""
    if not sys.platform.startswith('linux'):
        return True
    try:
        leader = os.getsid(pid)
    except OSError:
        return False
    seen = 0
    while seen < DEPTH:
        seen += 1
        if pid == leader:
            return True
        parent = _parent(pid)
        if parent is None or parent <= 1 or parent == pid:
            return False
        pid = parent
    return False


def claim() -> None:
    """Take the web server's vouch out of this command's environment as it starts, so no process it starts inherits
    it, and keep it for this command's own checks."""
    global _claimed
    secret = os.environ.pop(VOUCH, None)
    _claimed = (secret, os.getpid()) if secret else None


_claimed: tuple[str, int] | None = None  # the vouch this command started with, out of its environment, and its pid


def _leader_agent(pid: int, own_home: str) -> str | None:
    """The agent above the leader of `pid`'s session, when the leader is another process: re-parenting a command
    leaves it in the session its agent's shell made. A leader that has ended names no agent."""
    if not sys.platform.startswith('linux'):
        return None
    try:
        leader = os.getsid(pid)
    except OSError:
        return None
    if leader in (pid, 0, 1):
        return None
    return _agent_above(leader, own_home)


def peer_agent(pid: int | None, served: Path) -> str | None:
    """Why the process `pid`, the other end of a connection to the web server, is known to act for an agent of the
    home `served`; None when nothing says so, or when it cannot be found, such as a browser on another system."""
    if pid is None:
        return None
    environ = _environ(pid)
    named = [name for name in IDENTITY if environ is not None and environ.get(name)]
    if named:
        return f'{named[0]} is set on process {pid}'
    own = _same(served)
    return _agent_above(pid, own) or _leader_agent(pid, own)


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
    """Whether this process was run by the web server for a write from its own page: it holds the server's secret,
    from its environment or as the command claimed it at start, and the server that wrote that secret's hash is its
    parent."""
    secret = os.environ.get(VOUCH) or (_claimed[0] if _claimed is not None and _claimed[1] == os.getpid() else None)
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
