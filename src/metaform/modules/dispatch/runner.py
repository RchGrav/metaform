"""runner: one ACP session for one ticket, BASE-052, run by `metaform dispatch run`.

Metaform is the ACP client. A runner started on a ticket with an agent glyph, VIEW-040, works the glyph's tickets one
after another in board order, a session for each, the next taken when the one before is done. The agent's ACP adapter runs as a child process in its own process group, in the
project's folder, with the person's environment, its PATH led by the runner's interpreter folder; ACP goes over its standard input and output as bytes,
through the official SDK, `acp`. The runner listens on a loopback port for `message` and `stop`, and hears each
`map.changed` published in another process through the base's listener, QUAL-015 and BASE-053.

What a session puts in front of the person is a permission prompt the agent's own tool raised, and a question the agent
or one of its MCP servers asked through ACP's elicitation, each asked at the ticket's node and answered on the page;
dispatch_elicitation can decline every question instead. A turn that ends with the ticket open leaves the session idle
and reachable, and the ticket taken, until the person acts. A session that ends is closed with session/close where
the agent offers it.

What ACP gives beyond text is kept structured, so the page can show it as it is: the session's state, one `state` line
with the agent's capabilities, its settings (its modes and its config options, a model among them), its slash
commands, its plan, its usage and the parts of the map it has touched; each tool call's diffs, locations and
terminals in a `tool_detail` line, each file placed on the map through the refs of the sources layer; and each
permission request in a `permission` line with its options. A session whose agent can load or resume it is resumed
in place, its thread going on where it ended.
"""
from __future__ import annotations

import asyncio
import base64
import contextlib
import contextvars
import difflib
import fnmatch
import hashlib
import json
import os
import re
import secrets
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import traceback
import uuid
from collections import deque
from collections.abc import Callable, Coroutine, Sequence
from dataclasses import dataclass, replace
from importlib import metadata
from pathlib import Path
from typing import Any, cast

import acp
from acp.connection import StreamDirection, StreamEvent
from acp.schema import (
    AcceptElicitationResponse,
    AllowedOutcome,
    AuthCapabilities,
    BooleanConfigOptionCapabilities,
    CancelElicitationResponse,
    ClientCapabilities,
    ClientSessionCapabilities,
    CreateTerminalResponse,
    DeclineElicitationResponse,
    DeniedOutcome,
    ElicitationCapabilities,
    ElicitationFormCapabilities,
    ElicitationUrlCapabilities,
    EnvVariable,
    FileSystemCapabilities,
    Implementation,
    InitializeRequest,
    InitializeResponse,
    KillTerminalResponse,
    McpServerStdio,
    PermissionOption,
    ReadTextFileResponse,
    ReleaseTerminalResponse,
    RequestPermissionResponse,
    SessionConfigOptionsCapabilities,
    TerminalExitStatus,
    TerminalOutputResponse,
    ToolCallUpdate,
    WaitForTerminalExitResponse,
    WriteTextFileResponse,
)

from metaform import home, jev, prompt_files
from metaform.data import BASE_VARIABLE, NewerStore, Node, Store, StoreError, WorkRecord
from metaform.module import (
    WITHHELD,
    Context,
    Stop,
    child_environment,
    code_print,
    context,
    mcp_server,
    surface,
)

from . import (
    HANDED,
    PERSON_ENDS,
    PROMPTS,
    READS,
    REPLY_LIMIT,
    agent_label,
    agent_named,
    argv,
    billable,
    claimed,
    end_group,
    eyes_line,
    glyph_of,
    group_options,
    handed_path,
    handoff_parts,
    held_ticket,
    holder,
    intake_id,
    intake_prompt,
    intake_store,
    launch_options,
    mascot_line,
    memory_read,
    memory_text,
    module_read,
    next_ticket,
    option_key,
    origin,
    over_budget,
    prompt,
    release,
    require_eligible,
    resuming_path,
    runner_of,
    session_cost,
    session_state,
    slots_used,
    start_command,
    start_environment,
    startable,
    ticket,
    today,
    wanted_options,
    work_line,
    workflow_skill,
)
from .merge import checkpoint
from .signals import THREAD_TABLES, add_line, concerning, mark_peer

START_LIMIT = 300.0  # the one wait for the agent to start and make its session; npx may download it first
END_LIMIT = 10.0  # the one wait for a cancelled turn to end, and for the agent to end once its input is closed
LINE_LIMIT = 64 * 1024 * 1024  # the longest line read from the agent
CHUNKS = ('agent_message_chunk', 'agent_thought_chunk', 'user_message_chunk')
WRITES = ('edit', 'delete', 'move')  # the tool kinds of ACP that change files, each file under `locked`
# Rich, 2026-10-15, code#1e: no permission on files is locked until the rules and prompts are in place. Off, nothing
# below locks a file: no link is required, the ignore list is not read-only, Claude Code gets no ask rules or
# sandbox, Codex keeps the person's mode, the runner's terminal is unconfined and no sandbox request is refused. True
# brings back code.dispatcher.agent#3d's and #43's lock together, with the rule line that tells agents of it.
LINK_LOCK = False
# The sandbox half of the lock, kept apart from it after the 2026-10-15 crash, when every dispatched agent's commands
# ran sandboxed at once: True sends Claude Code its command sandbox (held_settings), runs the runner's own terminal
# under bubblewrap or sandbox-exec (confined_command) and refuses requests to widen the sandbox (unsandboxed). With
# it False the lock still refuses edits of unlinked and ignore-listed files through the edit tools, the ask rules and
# fs/write_text_file, and a command run in a shell is not confined. Turned on only by the person, after one agent has
# been run with it.
SHELL_SANDBOX = False
# The mode in which an agent asks before every change of a file and runs its commands in a sandbox that cannot write,
# by the name in its agentInfo: codex-acp writes files, and runs commands that write the workspace, without asking in
# every other mode, so it is kept in read-only whatever mode the person chose, code.dispatcher.agent#43, CTX-061.
ASKING_MODES = {'codex-acp': 'read-only'}
# What the mode the person chose for such an agent approves without asking, by tool kind, once the lock has passed:
# what the agent would have done unasked in that mode, `mcp` an MCP tool's approval, which Codex's auto review
# answered itself. Any other mode approves only what dispatch_prompts does.
MODE_APPROVES = {'workspace-write': WRITES, 'agent': (*WRITES, 'mcp'),
                 'agent-full-access': (*WRITES, 'execute', 'fetch', 'other', 'mcp')}


# The folders tools write as they run, left writable to commands wherever the walk of denied_writes meets them: git's
# index, the project's environment, bytecode and the caches of the test runner, the linter and the type checker,
# code.dispatcher.agent#47. They hold no file of the map's.
TOOL_FOLDERS = frozenset({'.git', '.venv', '__pycache__', '.pytest_cache', '.ruff_cache', '.mypy_cache',
                          'node_modules'})
GIT_HELD = ('hooks', 'config')  # what of .git a command may not write: a hook it wrote would run unconfined later
# The most characters of paths the command sandbox denies one by one. claude-agent-sdk passes the settings to Claude
# Code as one command-line argument, which Linux caps at 128 KiB; past this, folders are denied whole, the largest
# lists first, which only ever denies more.
DENIED_CHARS = 96 * 1024


def denied_writes(root: str, folder: str, index: dict[str, list[dict[str, str]]], patterns: Sequence[str]) -> list[str]:
    """The paths of the project a command may not write, absolute, code.dispatcher.agent#47: what `locked` refuses,
    and no more. Each path .metaform/ignore.txt holds; each existing file no ref names exactly; each folder holding no
    such file, whole, so nothing can be made in it. A folder that holds a linked file is walked instead, and the
    folders of TOOL_FOLDERS stay writable. Claude Code's sandbox lets a denied folder win over any path allowed inside
    it, so the list names what is denied and never the project folder itself. Not covered: a new file made in a
    folder that holds a linked file, under a name no list could know. The session's own worktree is walked with the
    names it gives its files; symbolic links are left out, a write through one landing on the path it names."""
    base, own = Path(root).resolve(), Path(folder).resolve()
    hides = ignored(patterns) if patterns else None
    holding = {'/'.join(parts[:end]) for parts in (key.split('/') for key in index) for end in range(1, len(parts))}
    kept: dict[str, list[str]] = {}  # each walked folder's own denied paths, to deny it whole if the list is too long

    def walk(directory: Path) -> list[str]:
        denied: list[str] = []
        try:
            entries = sorted(os.scandir(directory), key=lambda entry: entry.name)
        except OSError:
            return denied
        for entry in entries:
            if entry.is_symlink():
                continue
            named = relative(entry.path, [str(own), str(base)])
            if named is None:
                continue
            inside = entry.is_dir()
            if hides is not None and (hides(named) or inside and hides(f'{named}/\0')):
                denied.append(entry.path)
            elif not inside:
                if folded(named) not in index:
                    denied.append(entry.path)
            elif entry.name in TOOL_FOLDERS:
                if entry.name == '.git':
                    denied += [path for name in GIT_HELD if os.path.exists(path := os.path.join(entry.path, name))]
            elif folded(named) in holding or own == Path(entry.path) or Path(entry.path) in own.parents:
                kept[entry.path] = walk(Path(entry.path))
                denied += kept[entry.path]
            else:
                denied.append(entry.path)
        return denied
    denied = walk(base)
    whole: list[str] = []
    for path, inner in sorted(kept.items(), key=lambda one: -len(one[1])):
        if sum(map(len, denied)) <= DENIED_CHARS:
            break
        if own == Path(path) or Path(path) in own.parents or not inner \
                or any(path.startswith(one + os.sep) for one in whole):
            continue  # the session's own folder stays open to its tools; one inside a folder denied whole is gone
        whole.append(path)
        denied = [one for one in denied if not one.startswith(path + os.sep)] + [path]
    return denied


def writable_roots() -> list[str]:
    """Where an agent's commands may write outside what denied_writes denies: the person's home, which holds the
    project as a rule and the tools' caches (~/.cache/uv), and the temporary folders, code.dispatcher.agent#47. Never
    the file system's root: Claude Code 2.1.293, the build claude-agent-acp 0.89.1 bundles, then makes a mount point
    for its managed settings, /etc/claude-code, which it cannot, and every command fails. A project outside these
    stays writable as the session's folder, which Claude Code's sandbox allows by default."""
    found = (str(Path.home()), tempfile.gettempdir(), '/tmp', '/var/tmp')
    return list(dict.fromkeys(str(Path(one).resolve()) for one in found if os.path.isdir(one)))


def held_settings(denied: Sequence[str] | None) -> dict[str, Any]:
    """The `_meta` every session/new, load and resume sends: claude-agent-acp hands `claudeCode.options.settings` to
    Claude Code as its settings. An explicit ask rule reaches the permission request, session/request_permission, in
    every permission mode, bypassPermissions and acceptEdits included, so each edit of its own tools, which write to
    disk themselves, is decided by the runner first, code.dispatcher.agent#3d. Its sandbox runs every command with the
    paths of `denied`, denied_writes', read-only and no way out, so a shell write to an unlinked or ignore-listed file
    is prevented, code.dispatcher.agent#43 and #47, CTX-062, while the tools' folders and the files linked when the
    session starts stay writable; a session cannot start where the sandbox cannot. Paths outside the project stay
    writable, CTX-060. With LINK_LOCK off, `denied` None, neither the ask rules nor the sandbox is sent, so an edit is
    asked about only as the person's mode and dispatch_prompts would ask, Rich 2026-10-15. Other agents ignore the
    key."""
    if denied is None:
        return {}
    if not SHELL_SANDBOX:
        return {'claudeCode': {'options': {'settings': {
            'permissions': {'ask': ['Edit', 'Write', 'MultiEdit', 'NotebookEdit']}}}}}
    sandbox = {'sandbox': {'enabled': True, 'failIfUnavailable': True, 'allowUnsandboxedCommands': False,
                           'filesystem': {'allowWrite': writable_roots(), 'denyWrite': list(denied)}}}
    return {'claudeCode': {'options': {'settings': {
        'permissions': {'ask': ['Edit', 'Write', 'MultiEdit', 'NotebookEdit']}, **sandbox}}}}


def confined_command(denied: Sequence[str], command: str, args: Sequence[str]) -> list[str] | None:
    """A command of the runner's own terminal, ACP's terminal/create, run with the paths of `denied`, denied_writes',
    read-only, as the agents' own commands are, code.dispatcher.agent#43 and #47: bubblewrap on Linux, sandbox-exec on
    macOS; None where neither is found, and the terminal is refused."""
    if sys.platform.startswith('linux') and (found := shutil.which('bwrap')):
        return [found, '--dev-bind', '/', '/', *(part for path in denied for part in ('--ro-bind', path, path)), '--',
                command, *args]
    if sys.platform == 'darwin' and (found := shutil.which('sandbox-exec')):
        rules = ''.join(f'({"subpath" if os.path.isdir(path) else "literal"} "{quoted}")' for path in denied
                        if (quoted := path.replace('\\', '\\\\').replace('"', '\\"')))
        return [found, '-p', f'(version 1)(allow default){f"(deny file-write* {rules})" if rules else ""}', command,
                *args]
    return None
STREAM_EVERY = 0.4  # seconds between writes of text still being written, so the page shows it as it grows
LINES_EVERY = 0.25  # at most one `dispatch.session_lines` event per this many seconds; the rows are written at once
TERMINATED = 'the runner was terminated'  # how a session ends on SIGTERM; its runner takes no next ticket
RELEASE_LIMIT = 90.0  # the one wait for a new process to release: its start, and two writes that may each wait on a lock
RELEASE = ('import json, sys; from metaform.data import Store; from metaform.modules.dispatch import release; '
           "given = json.loads(sys.argv[1]); release(Store(given.pop('project'), module='dispatch'), **given)")
# The hand-over of a session to a runner on the code on disk, run by that code, `Session.hand_over`; it prints the start.
HAND_OVER = ('import json, sys; from metaform.data import Store; from metaform.modules.dispatch import hand_over; '
             "given = json.loads(sys.argv[1]); "
             "print(json.dumps(hand_over(Store(given.pop('project'), module='dispatch'), **given)))")
LOADED = code_print()  # the package's code as this process loaded it, told apart from the code on disk, STORE-029
# The updates that change what the session is rather than add to its thread: kept in its one `state` line.
STATE_UPDATES = ('available_commands_update', 'current_mode_update', 'config_option_update', 'session_info_update',
                 'usage_update')
PATCH_LIMIT = 200_000  # the most characters of a file's two texts a diff is worked out from; past it, its size only
PATCH_KEPT = 60_000  # the most characters of one diff kept in the thread; the rest is in the file itself
AWAIT_SPARE = 10  # seconds past a question's wait its runner still holds replies for the call that waits
TOUCHED_KEPT = 40  # the parts of the map a session's state lists as touched, the latest first
# What a session reported of itself that a resume carries over until the agent reports it again, so the page is not
# left blank after a resume; each is named in `before_resume` while it still holds what was known before the resume.
CARRIED = ('plan', 'usage', 'tokens', 'spent', 'auth', 'title', 'updated_at', 'commands')
SETTING_LIMIT = 10.0  # the one wait for the agent to take a setting; inside the caller's REPLY_LIMIT
LINE_MARK = re.compile(r'(?::\d+(?:-\d+)?|#L\d+(?:-L?\d+)?)$')  # a line or a range after a path: file.py:12, #L3-L9
FOLDED = os.name == 'nt' or sys.platform == 'darwin'  # their file systems compare names without case, as a rule
# This runner, one `dispatch run`: the tickets it works in turn spend against one run budget, and a retry the supervisor
# starts is given the run of the session it resumes as its `run` noun, so retries never reset it, M01.
RUN = secrets.token_hex(8)
# The JSON-RPC id of the agent's request being handled: set as each message is seen, in the receive loop, and so
# carried into the task the SDK starts for the request, which copies the context it is started in.
INCOMING: contextvars.ContextVar[Any] = contextvars.ContextVar('incoming', default=None)
STDERR_EVERY = 1.0  # seconds the agent's stderr lines are gathered before they are written as one line of the thread
STDERR_TAIL = 12  # the last lines of the agent's stderr a failure note carries
# Kilobytes of the agent's stderr one session's thread keeps, redacted; past it one line counts the rest, which the
# runner's log keeps. Settings cleanup 2026-10-15 made it fixed (dispatch_stderr_kb): a buffer size has one right answer.
STDERR_KB = 64
# Kilobytes of one terminal's output kept when the agent names no outputByteLimit; the oldest is dropped first, as ACP
# says. Fixed in the same cleanup (dispatch_terminal_kb).
TERMINAL_KB = 1024
LOGIN_LIMIT = 600.0  # the one wait for an agent's own login, which may wait on the person in a browser
# The longest a runner whose session stopped waits to come back for a due retry: the supervisor's own longest backoff,
# RETRY_SECONDS doubled for each retry dispatch_retries allows, plus a moment for the clock; a retry due later is the
# web server's retry timer's and the next change's, never an idle runner's held for up to an hour (UX review round 1,
# runaway F8).
RETRY_WAIT_SLACK = 5.0


def retry_wait_limit(ctx: Context) -> float:
    from . import RETRY_SECONDS
    return float(RETRY_SECONDS) * 2 ** max(0, int(ctx.setting('dispatch_retries'))) + RETRY_WAIT_SLACK
AUTH_REQUIRED = -32000  # ACP's auth_required error: the agent needs a login before it makes a session
# The order a session's chosen settings are applied in, by ACP category: a model switch may replace the effort and
# config options it offers, and set_config_option answers with the whole new set, so what depends on the model goes
# after it, session-config-options. Anything else follows in the order it was chosen.
APPLY_ORDER = ('mode', 'model', 'model_config', 'thought_level')
ELICIT_WORDS = {'decline': 'decline', 'cancel': 'cancel', 'skip': 'decline'}  # an answer that is an action, not content
# The limits a field of a form elicitation may set, the restricted JSON Schema of ACP's elicitation; `pattern` is ACP's.
ELICIT_LIMITS = ('minLength', 'maxLength', 'pattern', 'format', 'minimum', 'maximum', 'minItems', 'maxItems')
REQUEST_CANCELLED = -32800  # ACP's request cancellation: the answer to a request its sender withdrew
# What looks like a credential in what an adapter writes to stderr, replaced before it is kept anywhere.
SECRETS = (
    re.compile(r'(?i)\b(bearer|basic)\s+[A-Za-z0-9._~+/=-]{8,}'),
    re.compile(r'(?i)\b([A-Za-z0-9_]*(?:api[_-]?key|token|secret|password|passwd|authorization|cookie|session[_-]?key)'
               r'[A-Za-z0-9_]*)(\s*[:=]\s*|["\']\s*:\s*["\']?)[^\s"\',;]{4,}'),
    re.compile(r'\b(?:sk|pk|rk)-[A-Za-z0-9_-]{16,}'),
    re.compile(r'\b(?:gh[pousr]|github_pat)_[A-Za-z0-9_]{20,}'),
    re.compile(r'\bxox[abprs]-[A-Za-z0-9-]{10,}'),
    re.compile(r'\bAKIA[0-9A-Z]{16}\b'),
    re.compile(r'\bAIza[0-9A-Za-z_-]{30,}'),
    re.compile(r'\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}'),  # a JSON web token
)


def redact(text: str) -> str:
    """A line of the agent's stderr with anything that looks like a credential replaced by [redacted]: the name of
    a `name=value` pair is kept, so the line still says what was there."""
    for pattern in SECRETS:
        text = pattern.sub(lambda found: (f'{found.group(1)}{found.group(2)}[redacted]'
                                          if found.re.groups >= 2 and found.group(2) is not None
                                          else f'{found.group(1)} [redacted]' if found.re.groups == 1
                                          else '[redacted]'), text)
    return text


def stamp() -> str:
    """The time as the store writes it, to the second."""
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())


def agent_environment(**own: str) -> dict[str, str]:
    """The person's environment for the agent, with this interpreter's folder first on PATH: an agent that runs
    `metaform` or `python` in its shell reaches the install running this runner, not another one or none. Windows
    keeps the name upper case in `os.environ`, so `PATH` is the one name on every system.
    `DISABLE_MCP_CONFIG_FILTERING` makes codex-acp start the server the runner asks for even when the person's Codex
    config has one of the same name, `metaform`, which it would otherwise run in its place; other adapters ignore it.
    The session's identity is `own`, never one this runner inherited, BASE-052."""
    env = child_environment(**own)
    folder = os.path.dirname(sys.executable or '')
    rest = env.get('PATH', '')
    if folder and rest.split(os.pathsep)[0] != folder:
        env['PATH'] = os.pathsep.join(part for part in (folder, rest) if part)
    env['DISABLE_MCP_CONFIG_FILTERING'] = 'true'
    return env


# What lets a process draw on the person's desktop: X11 and Wayland, which WSLg puts on the Windows desktop.
DESKTOP = ('DISPLAY', 'WAYLAND_DISPLAY')


def windowless(env: dict[str, str]) -> dict[str, str]:
    """`env` without the desktop: an agent and every command it runs can open no window on the person's screen,
    however it starts a browser or any other program, so its work never takes over the screen while the person works.
    The person's own login, run in their terminal, keeps it."""
    return {name: value for name, value in env.items() if name not in DESKTOP}


def server_environment(**own: str) -> list[EnvVariable]:
    """The runner's METAFORM_* variables, METAFORM_HOME among them when set, named for the MCP server it asks the agent
    to start: Codex gives an MCP server only a short list of the adapter's variables, so a home that is not named here
    would be lost and the server would open another one. The session's identity is `own`, never one this runner
    inherited, BASE-052."""
    return [EnvVariable(name=name, value=value) for name, value in sorted(child_environment(**own).items())
            if name.startswith('METAFORM_')]


def role(nouns: dict[str, Any], work_id: str) -> str:
    """What a session's agent is, from the nouns its runner was started with, BASE-052: an intake agent, one of the
    agents the person summons (the sentinel on an issue, a talk, the system agent), a merge preparation, or a worker
    on its ticket. The nouns decide and not the session's flags, since intake and the summoned agents run as prep too."""
    if intake_id(work_id):
        return 'intake'
    if nouns.get('system'):
        return 'sentinel' if nouns.get('sentinel') else 'talk' if nouns.get('talk') else 'system'
    return 'prep' if nouns.get('prep') else 'worker'


def relative(path: str, roots: Sequence[str]) -> str | None:
    """A path an agent named, as the project names it: relative to the first of the roots it is inside, with forward
    slashes; None for a path inside none of them. ACP paths are absolute; a relative one is taken as given."""
    if not os.path.isabs(path):
        given = path.replace('\\', '/')
        while given.startswith('./'):
            given = given[2:]
        return given.rstrip('/') or None
    for root in roots:
        try:
            found = os.path.relpath(path, root)
        except ValueError:  # Windows: another drive
            continue
        if found == os.curdir or found == os.pardir or found.startswith(os.pardir + os.sep):
            continue
        return found.replace(os.sep, '/')
    return None


def folded(path: str) -> str:
    return path.casefold() if FOLDED else path


def sources_index(store: Store, root: str) -> dict[str, list[dict[str, str]]]:
    """Each path the sources layer's refs name, as the project names it, with the part of the map its ref is linked at:
    an element, or a join under its receiver's address, code.graph.knowledge#c. A ref's line mark is left off, so
    file.py:12 is file.py. With no sources layer the map places no file."""
    index: dict[str, list[dict[str, str]]] = {}
    for ref in store.refs():
        if ref.address is None:
            continue  # linked at a part no longer on the map
        path = relative(LINE_MARK.sub('', ref.value.strip()), [root])
        if path:
            place = {'kind': ref.node.kind, 'id': ref.node.id, 'address': ref.address}
            held = index.setdefault(folded(path), [])
            if place not in held:
                held.append(place)
    return index


def placed(index: dict[str, list[dict[str, str]]], path: str | None) -> tuple[list[dict[str, str]], bool]:
    """The parts of the map a file belongs to: those whose refs name it, or else those whose refs name the nearest
    folder holding it; and whether the match was exact, the file itself named, rather than that folder fallback."""
    if not path or not index:
        return [], False
    parts = folded(path).split('/')
    for end in range(len(parts), 0, -1):
        found = index.get('/'.join(parts[:end]))
        if found:
            return found, end == len(parts)
    return [], False


def ignored(patterns: Sequence[str]) -> Callable[[str], bool]:
    """Whether a project-relative path falls under the project's `.metaform/ignore.txt`, BASE-058, read with
    gitignore's common forms: `dir/` a folder anywhere, `/dir` from the root, a pattern without a slash a name
    anywhere, `*` and `**` wildcards. Negations are not read; they would only let more be written."""
    compiled: list[Callable[[str], bool]] = []
    for raw in patterns:
        pattern = raw.strip().strip('"').strip("'")
        if not pattern or pattern.startswith('!'):
            continue
        folder = pattern.endswith('/')
        pattern = pattern.strip('/')
        if not pattern:
            continue
        rooted = raw.strip().startswith('/') or '/' in pattern

        def match(path: str, pattern: str = pattern, folder: bool = folder, rooted: bool = rooted) -> bool:
            parts = path.split('/')
            if rooted:
                depth = pattern.count('/') + 1
                heads = ['/'.join(parts[:index]) for index in range(depth, len(parts) + 1)]
                return any(fnmatch.fnmatchcase(head, pattern) and (not folder or head != path)
                           for head in heads) or fnmatch.fnmatchcase(path, pattern + '/**')
            names = parts[:-1] if folder else parts
            return any(fnmatch.fnmatchcase(name, pattern) for name in names)
        compiled.append(match)
    return lambda path: any(match(path) for match in compiled)


def unified(path: str, old: str | None, new: str) -> dict[str, Any]:
    """A file edit as a unified diff with the lines it adds and removes; one too large to work out says its size only,
    and a long diff is cut, saying so."""
    if len(old or '') + len(new) > PATCH_LIMIT:
        return {'patch': None, 'added': None, 'removed': None, 'created': old is None, 'truncated': True,
                'size': len(new)}
    lines = list(difflib.unified_diff((old or '').splitlines(keepends=True), new.splitlines(keepends=True),
                                      f'a/{path}', f'b/{path}', n=3))
    added = sum(1 for line in lines if line.startswith('+') and not line.startswith('+++'))
    removed = sum(1 for line in lines if line.startswith('-') and not line.startswith('---'))
    text = ''.join(line if line.endswith('\n') else line + '\n' for line in lines)
    return {'patch': text[:PATCH_KEPT], 'added': added, 'removed': removed, 'created': old is None,
            'truncated': len(text) > PATCH_KEPT}


def setting_of(option: dict[str, Any]) -> dict[str, Any]:
    """One of the agent's config options, as the page offers it: its choices flattened, each with its group."""
    choices: list[dict[str, Any]] = []
    for given in cast(list[dict[str, Any]], option.get('options') or []):
        if 'group' in given:
            choices += [{'value': one.get('value'), 'name': one.get('name'), 'description': one.get('description'),
                         'group': given.get('name')} for one in cast(list[dict[str, Any]], given.get('options') or [])]
        else:
            choices.append({'value': given.get('value'), 'name': given.get('name'),
                            'description': given.get('description'), 'group': None})
    return {'id': option.get('id'), 'name': option.get('name'), 'description': option.get('description'),
            'category': option.get('category'), 'type': option.get('type', 'select'),
            'current': option.get('currentValue'), 'options': choices, 'source': 'option'}


def switched(value: str) -> bool | None:
    """A boolean setting's value as a person writes it; None when it is neither."""
    said = value.strip().casefold()
    return True if said in ('true', 'on', 'yes', '1') else False if said in ('false', 'off', 'no', '0') else None


def meta_records(meta: Any, depth: int = 0) -> list[dict[str, Any]]:
    """Every object inside an ACP `_meta`, nested ones too, for the vendor marks a field carries under its own key:
    codex-acp's `codex.questionId` and `isSecret`, JetBrains AIR's custom-answer mark."""
    if not isinstance(meta, dict) or depth > 3:
        return []
    found = [cast(dict[str, Any], meta)]
    for value in cast(dict[str, Any], meta).values():
        found += meta_records(value, depth + 1)
    return found


def elicit_fields(schema: dict[str, Any]) -> list[dict[str, Any]]:
    """Each field a form elicitation asks for, from its restricted JSON Schema, ACP's elicitation: its key, title,
    description, type, its choices as (value, title) when it offers some, whether it takes several, whether it is
    required, its default, its limits (length, pattern, format, range, count), whether a `_meta` marks it secret, and
    `note_of`, the choice field it is the free-text companion of. A companion is an optional string with no choices
    that a `_meta` names as answering another field (`questionId`), whose key extends a choice field's key
    (`question_0_custom`, `q1_note`), or that stands beside the form's only choice field: claude-agent-acp puts an
    "Other" field after each AskUserQuestion question, and codex-acp an "Additional answer or note"."""
    properties = cast(dict[str, Any], schema.get('properties') or {})
    required = set(cast(list[str], schema.get('required') or []))
    fields: list[dict[str, Any]] = []
    for key, given in properties.items():
        prop = cast(dict[str, Any], given) if isinstance(given, dict) else {}
        kind = str(prop.get('type') or 'string')
        source = cast(dict[str, Any], prop.get('items') or {}) if kind == 'array' else prop
        listed = cast(list[dict[str, Any]], source.get('oneOf') or source.get('anyOf') or [])
        choices = [(str(one.get('const')), str(one.get('title') or one.get('const'))) for one in listed] or \
            [(str(one), str(one)) for one in cast(list[Any], source.get('enum') or [])]
        marks = meta_records(prop.get('_meta'))
        fields.append({'key': key, 'title': str(prop.get('title') or key), 'description': prop.get('description'),
                       'type': kind, 'choices': choices, 'many': kind == 'array', 'required': key in required,
                       'default': prop.get('default'),
                       'limits': {name: prop[name] for name in ELICIT_LIMITS if prop.get(name) is not None},
                       'secret': any(mark.get('isSecret') is True for mark in marks), 'note_of': None,
                       'answers': next((str(mark['questionId']) for mark in marks if mark.get('questionId')), None)})
    selects = [field['key'] for field in fields if field['choices']]

    def free(field: dict[str, Any]) -> bool:
        return not field['choices'] and field['type'] == 'string' and not field['required']
    for field in fields:
        if not free(field):
            continue
        if field['answers'] in selects:
            field['note_of'] = field['answers']
        else:
            field['note_of'] = max((key for key in selects if str(field['key']).startswith(f'{key}_')), key=len,
                                   default=None)
    if len(selects) == 1 and all(field['key'] == selects[0] or free(field) for field in fields):
        for field in fields:
            if field['key'] != selects[0]:
                field['note_of'] = selects[0]
    for field in fields:
        del field['answers']
    return fields


def elicit_checked(field: dict[str, Any], value: Any) -> Any:
    """A field's answer held to the limits its schema sets, the restricted JSON Schema ACP's elicitation allows: a
    string's length, pattern and format, a number's range, a list's count. ValueError says which it breaks."""
    limits = cast(dict[str, Any], field.get('limits') or {})
    title = field['title']
    if isinstance(value, str):
        if 'minLength' in limits and len(value) < int(limits['minLength']):
            raise ValueError(f'{title} takes at least {limits["minLength"]} characters.')
        if 'maxLength' in limits and len(value) > int(limits['maxLength']):
            raise ValueError(f'{title} takes at most {limits["maxLength"]} characters.')
        if 'pattern' in limits:
            with contextlib.suppress(re.error):  # a pattern Python cannot read is not held against the person
                if re.search(str(limits['pattern']), value) is None:
                    raise ValueError(f'{title} must match {limits["pattern"]}.')
        kind = limits.get('format')
        try:
            if kind == 'email' and not re.fullmatch(r'[^@\s]+@[^@\s]+\.[^@\s]+', value):
                raise ValueError
            if kind == 'uri':
                from urllib.parse import urlsplit
                if not urlsplit(value).scheme:
                    raise ValueError
            if kind == 'date':
                import datetime
                datetime.date.fromisoformat(value)
            if kind == 'date-time':
                import datetime
                datetime.datetime.fromisoformat(value)
        except ValueError:
            raise ValueError(f'{title} is {"an" if kind in ("email", "uri") else "a"} {kind}, not {value}.') from None
    elif isinstance(value, (int, float)) and not isinstance(value, bool):
        if 'minimum' in limits and value < float(limits['minimum']):
            raise ValueError(f'{title} is at least {limits["minimum"]}.')
        if 'maximum' in limits and value > float(limits['maximum']):
            raise ValueError(f'{title} is at most {limits["maximum"]}.')
    elif isinstance(value, list):
        count = len(cast(list[Any], value))
        if 'minItems' in limits and count < int(limits['minItems']):
            raise ValueError(f'{title} takes at least {limits["minItems"]}.')
        if 'maxItems' in limits and count > int(limits['maxItems']):
            raise ValueError(f'{title} takes at most {limits["maxItems"]}.')
    return cast(Any, value)


def elicit_value(field: dict[str, Any], raw: Any) -> Any:
    """One field's answer in the type its schema asks for and within its limits; ValueError naming what it takes when
    it is not."""
    choices = cast(list[tuple[str, str]], field['choices'])

    def chosen(said: str) -> str:
        found = elicit_choice(choices, said)
        if found is None:
            raise ValueError(f'{field["title"]} is one of {", ".join(title for _, title in choices)}, not {said}.')
        return found
    if field['many']:
        items = cast(list[Any], raw) if isinstance(raw, list) else [one for one in str(raw).split(',') if one.strip()]
        return elicit_checked(field, [chosen(str(one)) if choices else str(one).strip() for one in items])
    if choices:
        return chosen(str(raw))
    if field['type'] == 'boolean':
        found = raw if isinstance(raw, bool) else switched(str(raw))
        if found is None:
            raise ValueError(f'{field["title"]} is yes or no, not {raw}.')
        return found
    if field['type'] in ('integer', 'number'):
        try:
            number = int(str(raw)) if field['type'] == 'integer' else float(str(raw))
        except ValueError:
            raise ValueError(f'{field["title"]} is a number, not {raw}.') from None
        return elicit_checked(field, number)
    return elicit_checked(field, raw if isinstance(raw, str) else json.dumps(raw))


def elicit_choice(choices: list[tuple[str, str]], said: str) -> str | None:
    """The value of the choice an answer names, by its value or its title, ignoring case; None when it names none."""
    for value, title in choices:
        if said.strip().casefold() in (value.casefold(), title.casefold()):
            return value
    return None


def elicit_named(fields: list[dict[str, Any]], said: str) -> dict[str, Any]:
    """An answer that names its fields: a JSON object, or `name: value` per line or per `;`, each name a field's key or
    its title where no other field shares it. Empty when no part names a field, so the answer is read as a bare one;
    ValueError when some parts name fields and another names none."""
    try:
        loaded: Any = json.loads(said)
    except ValueError:
        loaded = None
    if isinstance(loaded, dict):
        return cast(dict[str, Any], loaded)
    titles: dict[str, list[str]] = {}
    for field in fields:
        titles.setdefault(str(field['title']).casefold(), []).append(str(field['key']))
    keys = {str(field['key']).casefold(): str(field['key']) for field in fields}
    given: dict[str, Any] = {}
    unknown: list[str] = []
    for part in re.split(r'[\n;]', said):
        name, mark, value = part.partition(':') if ':' in part else part.partition('=')
        if not mark:
            if part.strip():
                unknown.append(part.strip())
            continue
        named = name.strip().casefold()
        key = keys.get(named) or (titles[named][0] if len(titles.get(named, [])) == 1 else None)
        if key is None:
            unknown.append(name.strip())
        else:
            given[key] = value.strip()
    if given and unknown:
        raise ValueError(f'{", ".join(unknown)} names no field; the fields are '
                         f'{", ".join(str(field["key"]) for field in fields)}')
    return given


def elicit_bare(fields: list[dict[str, Any]], main: dict[str, Any], said: str) -> dict[str, Any]:
    """A bare answer to a form of one question: a choice it names goes to the choice field, and words of the person's
    own to the field's free-text companion, as claude-agent-acp's "Other" box takes them. An answer that begins with a
    choice and goes on, `Blue, but darker`, is both. With no companion the whole answer is the field's."""
    notes = [field for field in fields if field['note_of'] == main['key']]
    choices = cast(list[tuple[str, str]], main['choices'])
    if not choices or not notes:
        return {main['key']: said}
    if main['many']:
        parts = [one.strip() for one in said.split(',') if one.strip()]
        picked = [found for one in parts if (found := elicit_choice(choices, one)) is not None]
        rest = ', '.join(one for one in parts if elicit_choice(choices, one) is None)
        return {**({main['key']: picked} if picked else {}), **({notes[0]['key']: rest} if rest else {})}
    if elicit_choice(choices, said) is not None:
        return {main['key']: said}
    lowered = said.casefold()
    for value, title in sorted(choices, key=lambda one: -len(one[1])):
        for name in (title, value):
            rest = said[len(name):] if lowered.startswith(name.casefold()) else None
            if rest is not None and (not rest or not rest[0].isalnum()):
                note = rest.strip(' \t\n,;:.-–—')
                return {main['key']: value, **({notes[0]['key']: note} if note else {})}
    if main['required']:
        raise ValueError(f'{main["title"]} is one of {", ".join(title for _, title in choices)}: begin the answer with '
                         'one, then add your own words after it')
    return {notes[0]['key']: said}


def elicit_answer(fields: list[dict[str, Any]], answer: str) -> tuple[str, dict[str, Any]]:
    """The person's answer to a form elicitation as ACP's response: decline or cancel when the answer says so, or
    accept with the content the schema asks for. A form of one question, a field and its free-text companions, takes
    a bare answer, elicit_bare; any form takes a JSON object or `name: value` lines, elicit_named. Fields left out
    take their default. ValueError says what is wrong, and an answer that fills no field is one: it is never sent as
    an empty accept, which an agent reads as no answer."""
    said = answer.strip()
    action = ELICIT_WORDS.get(said.casefold())
    if action is not None:
        return action, {}
    if not fields:
        return 'accept', {}
    questions = [field for field in fields if field['note_of'] is None]
    given = elicit_named(fields, said)
    if not given and len(questions) == 1:
        given = elicit_bare(fields, questions[0], said)
    if not any(given.get(field['key']) not in (None, '', []) for field in fields):
        raise ValueError('the answer fills none of the fields; answer one line per field as name: value, or decline')
    content: dict[str, Any] = {}
    for field in fields:
        raw = given.get(field['key'])
        if raw is None or raw == '' or raw == []:
            if field['default'] is not None:
                content[field['key']] = field['default']
            elif field['required']:
                raise ValueError(f'{field["title"]} is required')
            continue
        content[field['key']] = elicit_value(field, raw)
    return 'accept', content


def elicit_suggestions(fields: list[dict[str, Any]], url: str | None) -> list[str]:
    """The answers offered as suggestions: accept or decline for a page to open; a one-question form's choices; else
    decline only."""
    if url is not None:
        return ['accept', 'decline']
    questions = [field for field in fields if field['note_of'] is None]
    if len(questions) == 1 and questions[0]['choices'] and not questions[0]['many']:
        return [title for _, title in questions[0]['choices']] + ['decline']
    return ['decline']


def elicit_question(name: str, message: str, fields: list[dict[str, Any]], url: str | None,
                    deadline: float | None = None) -> str:
    """What the person reads: who asks and what, each field with what it takes, or for a URL its full address and
    host, which ACP's elicitation says the person sees before consenting; how to answer; and when the agent goes on
    without the answer, if it said."""
    after = f'\nIt goes on without your answer after {round(deadline)} s.' if deadline else ''
    if url is not None:
        from urllib.parse import urlsplit
        host = urlsplit(url).hostname or 'no host'
        coded = ' The host is written in another script (punycode): check it is the one you expect.' \
            if any(part.startswith('xn--') for part in host.split('.')) or not host.isascii() else ''
        return (f'{name} asks you to open a page: {message}\nAddress: {url}\nHost: {host}{coded}\nOpen it yourself in '
                f'your browser if you consent, then answer accept; or answer decline.{after}')
    questions = [field for field in fields if field['note_of'] is None]
    lines = [f'{name} asks: {message}']
    single = len(questions) == 1

    def shown(field: dict[str, Any], indent: str) -> str:
        takes = ', '.join(title for _, title in field['choices']) if field['choices'] else \
            'your own words' if field['note_of'] else field['type']
        named = field['title'] if single else f'{field["key"]} ({field["title"]})'
        return (f'{indent}- {named}{" (required)" if field["required"] else ""}: {field["description"] or ""} '
                f'[{"any of " if field["many"] else ""}{takes}]').replace(':  [', ': [')
    for field in questions:
        lines.append(shown(field, ''))
        lines += [shown(note, '  ') for note in fields if note['note_of'] == field['key']]
    if any(field['secret'] for field in fields):
        lines.append('This asks for a secret: answer it on the page or with metaform dispatch permit, where it is kept '
                     'out of the thread; a sign-in page the agent offers is safer still.')
    if single and questions[0]['choices'] and len(fields) > 1:
        lines.append('Answer with a choice, your own words, or a choice and then your words; or decline.')
    elif not single:
        lines.append('Answer with one line per field as name: value, by the name before the brackets; or decline.')
    return '\n'.join(lines) + after


def decided(fields: list[dict[str, Any]]) -> AcceptElicitationResponse | DeclineElicitationResponse:
    """The answer dispatch gives at once to a question from an agent that may not ask the person, a worker among them:
    the `decide` prompt in each own-words field, which claude-agent-acp's AskUserQuestion and codex-acp read as the
    answer; a form with no such field, one that requires a field, or a page to open is declined."""
    notes = [field['key'] for field in fields if field['note_of']]
    if not notes or any(field['required'] for field in fields):
        return DeclineElicitationResponse(action='decline')
    reply = prompt('decide')
    return AcceptElicitationResponse(action='accept', content={key: reply for key in notes})


class Exits(asyncio.subprocess.SubprocessStreamProtocol):
    """The agent's process protocol, which says when the process itself has ended. `Process.wait` waits also for its
    pipes, which a process it started may hold open after it ends."""

    def __init__(self, limit: int, loop: asyncio.AbstractEventLoop) -> None:
        super().__init__(limit=limit, loop=loop)
        self.exited = asyncio.Event()

    def process_exited(self) -> None:
        super().process_exited()
        self.exited.set()


async def dispatch(ctx: Context) -> dict[str, Any]:
    """`metaform dispatch run <id> <agent>`: the session for one ticket, until it ends. When the ticket is done and has an
    agent glyph, VIEW-040, the glyph's next ticket in board order gets a session of its own, and so on until the glyph
    has none waiting or a session ends with its ticket not done. A runner that fails in any way before its session
    holds the ticket gives the ticket's reservation back at once, with the traceback in its log (UX review round 1,
    runaway F6): a reservation held a slot for 180 s after a start died, and the log said one line."""
    try:
        return await dispatching(ctx)
    except Stop:
        await asyncio.to_thread(given_back, ctx.require_store(), ctx.nouns['id'], ctx.nouns.get('reservation'))
        raise
    except BaseException:
        sys.stderr.write(traceback.format_exc())
        try:
            await asyncio.to_thread(given_back, ctx.require_store(), ctx.nouns['id'], ctx.nouns.get('reservation'))
        except BaseException:  # noqa: BLE001  the failure itself is what the runner reports
            sys.stderr.write(traceback.format_exc())
        raise


async def dispatching(ctx: Context) -> dict[str, Any]:
    store = ctx.require_store()
    # Every runner stays on the metaform its ticket or conversation began in, whichever is made active later, and so
    # do its agent and that agent's MCP server, which inherit the variable: the one its starter named, else the one
    # active now, BASE-052. A conversation on no map has none to stay on, and follows the first one made.
    bound = await asyncio.to_thread(store.bound_base)
    if bound is not None:
        os.environ[BASE_VARIABLE] = bound.id
        store = Store(store.project_id, toggled=store.toggled, base=bound.id, module=store.module,
                      write_layer=store.write_layer)
        ctx = replace(ctx, store=store)
    agent, work_id = agent_named(ctx.nouns['agent']), ctx.nouns['id']
    command = argv(start_command(ctx, agent))
    resume = str(ctx.nouns['resume']) if ctx.nouns.get('resume') else None
    run_id = str(ctx.nouns.get('run') or RUN)  # a retry goes on spending against the run of the session it resumes
    # a server it could not choose refuses the start before any agent runs, MCP-006 and MCP-010; `dispatch` gives the
    # reservation back
    await asyncio.to_thread(mcp_server, Path(store.project().path))
    if resume:  # a session a live runner holds is never resumed a second time, before its agent is even started
        holds = (intake_store(store, work_id) or store) if intake_id(work_id) else store
        pid = await asyncio.to_thread(holder, holds, work_id, resume, besides=os.getpid())
        if pid is not None:
            raise Stop(f'Session {resume} is held by its live runner, process {pid}, so it is not resumed again.',
                       f'metaform dispatch sessions id={work_id}')
    resumed = await asyncio.to_thread(worked_in, store, work_id, resume) if resume else None
    if intake_id(work_id):  # an intake agent, VIEW-045: no ticket; its session lives in the metaform it began in
        held_in = await asyncio.to_thread(intake_store, store, work_id) or store
        return await moved_on(store, await Session(ctx, held_in, None, agent, command, resumed, prep=True, system=True,
                                                   work_id=work_id, resume=resume).run())
    if ctx.nouns.get('system'):  # the person's system agent, the +1: talks with them in the project's folder
        # on its held ticket; with no map, or on a ticket a map cleared since took with it, on no ticket, PROJ-026
        held = await asyncio.to_thread(held_ticket, store, work_id)
        return await moved_on(store, await Session(ctx, store, held, agent, command, resumed, prep=True, system=True,
                                                   work_id=work_id, resume=resume).run())
    if ctx.nouns.get('prep'):  # VIEW-044: an agent helps the person prepare a merge under review, in its worktree
        from .merge import worktree_of
        held = await asyncio.to_thread(ticket, store, work_id)
        folder = await asyncio.to_thread(worktree_of, store, work_id)
        return await moved_on(store, await Session(ctx, store, held, agent, command, folder, prep=True).run())

    def reserve(record: WorkRecord) -> WorkRecord:
        with store.atomic():
            record = ticket(store, record.id)
            reservation = ctx.nouns.get('reservation')
            if reservation and record.taken_by == reservation:
                require_eligible(ctx, record, agent)
                return record
            startable(ctx, store, record, agent)
            reservation = 'dispatch starting ' + secrets.token_hex(16)
            record = store.take_work(record.id, by=reservation)
            ctx.nouns['reservation'] = reservation
            return record

    def over_limit() -> bool:
        """Whether this start's reservation finds the agent slots already full, and then gives its ticket back."""
        with store.atomic():
            record = ticket(store, work_id)
            if not ctx.nouns.get('reservation') or record.taken_by != ctx.nouns['reservation'] or \
                    slots_used(ctx, store) <= int(ctx.setting('dispatch_agents')):
                return False
            store.move_work(record.id, 'backlog' if record.held else 'todo', record.position)
            return True

    # A start the agent slots have no room for, from a process on older code, gives its ticket back before any agent
    # runs, VIEW-039. Found 2026-10-16: an MCP server started before the slot check went on starting tickets past it.
    if not resume and await asyncio.to_thread(over_limit):
        raise Stop(f'Every agent slot is in use: {ctx.setting("dispatch_agents")} agents at once. Work {work_id} is '
                   'back in To do.', 'metaform dispatch sessions')
    # A worker resumed in place holds its ticket already, taken by its own session, so nothing is reserved for it.
    record = await asyncio.to_thread(ticket, store, work_id) if resume else \
        await asyncio.to_thread(reserve, ticket(store, work_id))
    worked: list[str] = []
    while True:
        folder: Path | None = None
        if resume:
            folder = Path(resumed) if resumed else None  # where it worked, its worktree when it had one
        elif ctx.setting('dispatch_worktrees'):  # VIEW-044: each ticket's agent works in a worktree of its own
            from .merge import worktree_for
            folder = await asyncio.to_thread(worktree_for, store.project().path, record.id)
        ended = await Session(ctx, store, record, agent, command, folder, resume=resume).run()
        resume = None  # the glyph's next ticket, if any, is a new session
        worked.append(record.id)
        if ended.get('ended') in (TERMINATED, HANDED):  # it reads nothing more: a store it cannot reach is no error
            return ended if len(worked) == 1 else {**ended, 'worked': worked}
        record = await asyncio.to_thread(ticket, store, record.id)
        if folder is not None and record.done:  # its work committed, tested and checked to merge, VIEW-044
            from .merge import finished
            await asyncio.to_thread(finished, ctx, store, record, folder)
            active = await asyncio.to_thread(store.active_base)
            await ctx.publish_async('map.changed', {'project': store.project_id, 'tables': 'dispatch',
                                                    'dispatch_tables': ['dispatch.merges'],
                                                    'base_id': active.id if active else None,
                                                    **concerning(record.id, ended.get('session_id'),
                                                                 ['dispatch.merges'])})
        glyph = await asyncio.to_thread(glyph_of, ctx, record)  # read again, so a glyph given while it ran counts
        if glyph is not None and await asyncio.to_thread(over_budget, ctx, store, run=run_id) is not None:
            glyph = None  # past this run's or today's token budget, the glyph's next ticket waits, M01
        if glyph is None:
            return await moved_on(store, ended if len(worked) == 1 else {**ended, 'worked': worked})
        def following(glyph: str) -> WorkRecord | None:
            with store.atomic():
                found = next_ticket(ctx, store, glyph, agent=agent, exclude=tuple(worked))
                return reserve(found) if found is not None else None
        try:
            found = (await asyncio.to_thread(following, glyph)
                     if record.done or ended.get('ended') == 'cannot continue without an answer' else None)
        except Stop:  # another runner now occupies the glyph
            found = None
        if found is None:
            return await moved_on(store, {**ended, 'glyph': glyph, 'worked': worked})
        record = found


async def moved_on(store: Store, ended: dict[str, Any]) -> dict[str, Any]:
    """This runner is done with its sessions: the queue moves on in this process, VIEW-042, so waiting tickets start
    whether or not a page is open. Autostart recovers what dead runners left first, BASE-052, and starts nothing when
    Autostart agents is unchecked. A terminated runner starts nothing; a failed check is said in this runner's log and
    leaves the result as it was."""
    if ended.get('ended') not in (TERMINATED, HANDED):  # a runner that handed its session over reads nothing more
        from . import autostart
        project = await asyncio.to_thread(store.project)
        ctx = context('dispatch', Path(project.path), project=store.project_id)
        try:
            started = await asyncio.to_thread(autostart, ctx)
            # A session that stopped without the person's stop is retried after a wait, P012: this runner, which saw
            # it stop, comes back once the retry is due, so no timer runs anywhere else.
            due = started.get('retry_due')
            wait = max(float(due) - time.time(), 0.0) if due is not None else None
            if wait is not None and wait <= retry_wait_limit(ctx) and \
                    str(ended.get('ended') or '') not in PERSON_ENDS:
                await asyncio.sleep(wait)
                await asyncio.to_thread(autostart, ctx)
        except Exception as error:  # noqa: BLE001  the session's own result stands whatever the next start meets
            sys.stderr.write(f'Could not start the waiting tickets: {error}\n')
    return ended


def given_back(store: Store, work_id: str, reservation: Any) -> None:
    """A ticket `start` reserved for a runner that refuses to begin goes back where it waited, To do, or the backlog
    when the person holds it, as a start that fails does."""
    if not reservation or intake_id(work_id):
        return
    with store.atomic():
        record = ticket(store, work_id)
        if record.taken_by == reservation:
            store.move_work(work_id, 'backlog' if record.held else 'todo', record.position)


def worked_in(store: Store, work_id: str, session_id: str) -> str | None:
    """The folder a session worked in, as its state line keeps it; None when it kept none."""
    held = session_state(intake_store(store, work_id) or store if intake_id(work_id) else store, session_id)
    cwd = held.get('cwd') if held else None
    return str(cwd) if cwd else None


# the thread lines that change what a session is, its state and its subagents, announced with kind session
STATE_LINES = frozenset({'state', 'subagent'})
# the map's tables a change to a ticket, its questions or its workflow runs writes, for a change that does not say
# which ticket it concerns
TICKET_TABLES = frozenset({'work', 'work_steps', 'work_links', 'messages', 'map.question_work'})


def concerns(payload: dict[str, Any], work_id: str, session_id: str | None, tables: list[str] | None) -> bool:
    """Whether a `map.changed` from another process can concern this session, BASE-053: it names its ticket or its
    session; or it does not say which tickets it wrote, and wrote tickets, questions or workflow runs, or did not say
    what it wrote. One that names only other tickets and sessions does not."""
    named: Any = payload.get('work_ids')
    sessions: Any = payload.get('session_ids')
    if isinstance(named, list) and work_id in named or \
            session_id is not None and isinstance(sessions, list) and session_id in sessions:
        return True
    if isinstance(named, list) or isinstance(sessions, list):
        return False
    return tables is None or any(table in TICKET_TABLES or table.startswith('workflow.') for table in tables)


def choose(options: list[PermissionOption], answer: str | None) -> str | None:
    """The option a person's answer names, by its name or its id; None when it names none."""
    said = (answer or '').strip()
    for exact in (True, False):
        for option in options:
            names = (option.name, option.option_id)
            if any(name == said if exact else name.casefold() == said.casefold() for name in names):
                return option.option_id
    return None


def allowed(options: list[PermissionOption], how: str, kind: Any) -> PermissionOption | None:
    """The agent's allow-once option when the prompts choice `how` approves a request of this tool kind without asking
    the person: approve-all approves any, approve-reads only reads and searches; None when it is asked."""
    allow = next((option for option in options if str(option.kind) == 'allow_once'), None)
    if allow is not None and (how == 'approve-all' or (how == 'approve-reads' and str(kind) in READS)):
        return allow
    return None


def chunk_text(content: Any) -> str:
    if not isinstance(content, dict):
        return ''
    block = cast(dict[str, Any], content)
    return str(block.get('text', '')) if block.get('type') == 'text' else f'[{block.get("type", "content")}]'


def subject(store: Store, work_id: str, talk: str) -> tuple[str, str]:
    """What a conversation agent talks about, in words, and how it reads it first, from `talk=<kind>:<ref>`."""
    kind, _, ref = talk.partition(':')
    if kind == 'ticket':
        record = ticket(store, ref)
        return (f'ticket {ref}, {"done" if record.done else "open"}: {record.task or record.note or ""}',
                f'`metaform map work id={ref}`, and what its agents did with `metaform dispatch sessions id={ref}`')
    if kind == 'question':
        asked = next((one for one in store.messages(None, 'question', None, limit=0).results if one.id == ref), None)
        text = asked.text or '' if asked else ''
        return (f'question {ref}{", answered" if asked and asked.closed else ""}: {text}',
                f'`metaform map messages kind=question` for question {ref}, and its ticket with `metaform map work id={work_id}`')
    if kind == 'thread':
        return (f'what an earlier agent did in session {ref} on ticket {work_id}',
                (f'that session\'s whole thread with `metaform dispatch sessions id={work_id}` (session {ref}), and '
                 f'the ticket with `metaform map work id={work_id}`'))
    return f'the node {ref} of the map', f'`metaform map where {ref}`'


@dataclass
class Terminal:
    """One terminal the agent asked the runner for, ACP's terminal/create: its process in a group of its own, the
    output kept so far, at most `limit` bytes with the oldest dropped first, and how it exited once it has."""
    command: str
    cwd: str
    process: asyncio.subprocess.Process
    limit: int
    output: bytearray
    truncated: bool = False
    exit: TerminalExitStatus | None = None
    reader: asyncio.Task[None] | None = None
    shown: float = 0.0  # when its line in the thread was last written


def trimmed(output: bytearray, limit: int) -> bool:
    """Drop the oldest output past `limit` bytes, at a character boundary as ACP asks; whether anything was dropped."""
    if len(output) <= limit:
        return False
    del output[:len(output) - limit]
    while output and output[0] & 0xC0 == 0x80:  # a UTF-8 continuation byte: the character began in what was dropped
        del output[0]
    return True


def exit_status(code: int | None) -> TerminalExitStatus:
    """A process's end as ACP says it: its exit code, or the signal that ended it, by name."""
    if code is not None and code < 0:
        try:
            return TerminalExitStatus(exit_code=None, signal=signal.Signals(-code).name)
        except ValueError:
            return TerminalExitStatus(exit_code=None, signal=str(-code))
    return TerminalExitStatus(exit_code=code, signal=None)


PROVIDERS = {'claude': 'anthropic', 'codex': 'openai', 'gemini': 'gcp.gemini'}  # gen_ai.provider.name, semconv


def usage_attributes(agent: str, name: str, version: str | None, session_id: str | None, usage: Any,
                     reason: str, model: str | None) -> dict[str, Any]:
    """One agent turn's span attributes, as the OpenTelemetry GenAI semantic conventions name them for an invoke_agent
    client span, github.com/open-telemetry/semantic-conventions-genai docs/gen-ai/gen-ai-agent-spans.md, read
    2026-10-12: input tokens count every input token, the cached ones among them, so ACP's input, which leaves the
    cached part out, is added to the cache reads and writes; output is ACP's output, which holds the thinking."""
    attributes: dict[str, Any] = {'gen_ai.operation.name': 'invoke_agent',
                                  'gen_ai.provider.name': PROVIDERS.get(agent, agent), 'gen_ai.agent.id': agent,
                                  'gen_ai.agent.name': name, 'gen_ai.response.finish_reasons': [reason]}
    if version:
        attributes['gen_ai.agent.version'] = version
    if session_id:
        attributes['gen_ai.conversation.id'] = session_id
    if model:
        attributes['gen_ai.request.model'] = model
    if usage is not None:
        cache_read, cache_write = int(usage.cached_read_tokens or 0), int(usage.cached_write_tokens or 0)
        attributes['gen_ai.usage.input_tokens'] = int(usage.input_tokens) + cache_read + cache_write
        attributes['gen_ai.usage.output_tokens'] = int(usage.output_tokens)
        if usage.cached_read_tokens is not None:
            attributes['gen_ai.usage.cache_read.input_tokens'] = cache_read
        if usage.cached_write_tokens is not None:
            attributes['gen_ai.usage.cache_write.input_tokens'] = cache_write
    return attributes


def traced(attributes: dict[str, Any], started_ns: int, error: str | None = None) -> None:
    """The turn as an OpenTelemetry client span, from when its prompt was sent to now, through the OpenTelemetry API
    when it is installed; with no SDK set up, the API records nothing. Never raises: a trace is never worth a turn."""
    try:
        from opentelemetry import trace
    except ImportError:
        return
    try:
        tracer = trace.get_tracer('metaform.dispatch')
        span = tracer.start_span(f'invoke_agent {attributes.get("gen_ai.agent.name") or ""}'.strip(),
                                 kind=trace.SpanKind.CLIENT, attributes=attributes, start_time=started_ns)
        if error:
            from opentelemetry.trace import Status, StatusCode
            span.set_attribute('error.type', 'turn_error')
            span.set_status(Status(StatusCode.ERROR, error))
        span.end()
    except Exception as failure:  # noqa: BLE001  a tracer's own failure is said in the log and nowhere else
        sys.stderr.write(f'Could not trace the turn: {failure}\n')


# What a tool call reaches for: a Metaform tool by its MCP name, mcp__metaform__map_node or metaform_map_node as hosts
# show it, or the command line, metaform map node. The tool is <module>_<verb>, a verb's dashes as written.
METAFORM_TOOL = re.compile(r'(?i)(?:mcp__metaform__|metaform[_ ])(?P<module>[a-z][a-z0-9]*)[_ ](?P<verb>[a-z][a-z0-9_-]*)')
DRIFT_EVERY = 10  # tool calls between two asks of Jev whether a worker has drifted, when Jev's session_drift is on


def call_line(call: dict[str, Any]) -> str:
    """One tool call as one line, its title and its input, as Jev's session_drift reads calls."""
    raw = call.get('rawInput')
    return f'{call.get("title") or call.get("kind") or "tool"} {json.dumps(raw, ensure_ascii=False)[:400] if raw else ""}'.strip()


CALLED_MOST = 64_000  # characters of a Metaform call's input and of each block of its result kept in its thread


def metaform_called(known: dict[str, Any], data: dict[str, Any], title: str) -> dict[str, Any] | None:
    """The Metaform tool a call names, `<module>_<verb>`, with what it was given and, once it is complete, what it gave
    back as an MCP tool result, each clipped to CALLED_MOST; None for any other call, or before either is known.
    Read from the call's title as hosts show it, or claude-agent-acp's `_meta.claudeCode.toolName`."""
    meta = cast(dict[str, Any], data.get('_meta') or {})
    named = tools_named(f'{title} {cast(dict[str, Any], meta.get("claudeCode") or {}).get("toolName") or ""}')
    if not named:
        return None
    module, verb = named[0]
    raw = known.get('rawInput')
    given = cast(dict[str, Any], raw) if isinstance(raw, dict) and len(json.dumps(raw, default=str)) <= CALLED_MOST else {}
    output = data.get('rawOutput')
    blocks: list[dict[str, Any]] = []
    if isinstance(output, dict) and isinstance(cast(dict[str, Any], output).get('content'), list):
        blocks = [cast(dict[str, Any], one) for one in cast(list[Any], cast(dict[str, Any], output)['content'])
                  if isinstance(one, dict)]
    elif data.get('status') in ('completed', 'failed'):
        blocks = [cast(dict[str, Any], one['content']) for one in cast(list[dict[str, Any]], known.get('content') or [])
                  if one.get('type') == 'content' and isinstance(one.get('content'), dict)]
        if not blocks and isinstance(output, str):
            blocks = [{'type': 'text', 'text': output}]
    text = [{'type': 'text', 'text': str(one.get('text', ''))[:CALLED_MOST]} for one in blocks if one.get('type') == 'text']
    called: dict[str, Any] = {'tool': f'{module}_{verb}', 'input': given}
    if data.get('status') in ('completed', 'failed'):
        called['result'] = {'content': text, 'isError': data.get('status') == 'failed'}
        # the structured result too, where the agent passed it on, since a view paints from it before it reads
        structured = cast(dict[str, Any], output).get('structuredContent') if isinstance(output, dict) else None
        if isinstance(structured, dict) and len(json.dumps(structured, default=str)) <= CALLED_MOST:
            called['result']['structuredContent'] = structured
    return called


def tools_named(line: str) -> list[tuple[str, str]]:
    """The Metaform tools a call line names, as (module, verb)."""
    return [(found['module'].lower(), found['verb'].lower().rstrip('_')) for found in METAFORM_TOOL.finditer(line)]


def withheld_named(line: str, entries: Sequence[str], effects: dict[tuple[str, str], str]) -> list[str]:
    """The Metaform tools a call line reaches for that the session's withheld entries name, `<module>_<verb>`:
    `<module>`, `<module>:read` with the verb's effect read, or the tool itself."""
    found: list[str] = []
    for module, verb in tools_named(line):
        tool = f'{module}_{verb}'
        if (module in entries or tool in entries
                or (f'{module}:read' in entries and effects.get((module, verb)) == 'read')):
            found.append(tool)
    return found


@dataclass
class ActiveTurn:
    """Cancellation belongs to one prompt, including its turn-start publication before ACP receives it."""
    sent: bool = False
    cancel_requested: bool = False


class Session:
    """One ticket's ACP session. The SDK calls `session_update` and `request_permission` on it."""

    def __init__(self, ctx: Context, store: Store, record: WorkRecord | None, agent: str, command: list[str],
                 folder: Any = None, prep: bool = False, system: bool = False, *, work_id: str | None = None,
                 resume: str | None = None) -> None:
        self.system = system  # the person's system agent: no ticket work, a conversation that lasts until stopped
        self.prep = prep  # helping the person prepare a merge, VIEW-044: it takes no ticket and lives between turns
        # The agent a start launched on its ticket, which takes that launch's own permissions, `launch_options`
        self.launched = record is not None and not (system or prep)
        self.ctx, self.store, self.agent, self.command = ctx, store, agent, command
        # An intake agent has no ticket and no node: its work id names its session alone, and a permission it asks
        # for is put to the person on the page only, as a choice among its options.
        self.work_id = record.id if record is not None else str(work_id)
        self.node = Node.of(record.node_kind, record.node_id) if record is not None else None
        # Who the agent is, told to it and to its MCP server, BASE-052: its role, the id this runner gives its session
        # when it starts, its ticket and where the ticket is, an element's address or a join's two ends.
        self.role = role(ctx.nouns, self.work_id)
        self.at = (record.address or '|'.join(end for end in (record.receiver_address, record.provider_address) if end)
                   if record is not None else '')
        self.runner: str | None = None
        self.root = store.project().path
        self.folder = str(folder) if folder is not None else self.root  # its worktree, VIEW-044
        self.name = agent_label(agent)
        self.base_id: str | None = None
        self.resume = resume  # the ended session this one goes on with, resumed or loaded through ACP
        self.replaying = False  # session/load replays the history the thread already holds; it is not written again
        self.session_id: str | None = resume
        self.recovery: dict[str, Any] | None = None  # the process births automatic recovery verifies, MAP-049
        self.request = ''  # what the person asked an intake agent for, taken from its launch's row
        self.token = secrets.token_hex(16)
        self.port = 0
        self.process: asyncio.subprocess.Process | None = None
        self.exited = asyncio.Event()  # the agent's process has ended
        self.conn: Any = None
        self.recorded = False  # the session's row is written
        self.took = bool(record is not None and ctx.nouns.get('reservation')
                         and record.taken_by == ctx.nouns['reservation'])
        # What the session is, kept whole in its `state` line: capabilities, settings, commands, plan, usage, touched.
        # `spent` is what the session has used, the tokens of every turn and its cost so far, M01; `auth` the login
        # its agent reports through the authStatus extension, and `auth_methods` the logins it offers, P031.
        self.acp: dict[str, Any] = {'agent': agent, 'agent_info': None, 'capabilities': {}, 'cwd': self.folder,
                                    'commands': [], 'plan': [], 'usage': None, 'tokens': None, 'title': None,
                                    'touched': [], 'resumed': None, 'before_resume': [],
                                    'spent': None, 'auth': None, 'auth_methods': [],
                                    # the files it read and wrote through the runner, P019, the latest first, and an
                                    # intake agent's first call and record, M04
                                    'files': [], 'intake': None,
                                    # how the person chose this session's permission requests are answered, one of
                                    # dispatch_prompts' choices over the launch's and the project's, `answering`
                                    'prompts': None,
                                    # what a conversation is about, so the person's next Call or Chat on it resumes it,
                                    # and what its agent is, so the person's system agent is told from an intake or a
                                    # sentinel whatever its work id hangs on, PROJ-026
                                    'about': str(ctx.nouns.get('talk') or 'system') if system else None,
                                    'role': self.role}
        self.modes: dict[str, Any] | None = None  # the agent's session modes: current and available
        self.config: list[dict[str, Any]] = []  # the agent's config options, as it sent them
        self.offered = False  # the last session/new, load or resume answer named its modes or config options
        self.asking: str | None = None  # the mode this agent is kept in so it asks before every write, ASKING_MODES
        self.chosen_mode: str | None = None  # the mode the person chose for it, which decides what is approved unasked
        self.sources: dict[str, list[dict[str, str]]] | None = None  # the sources layer's paths, read when needed
        # The rule on writing files, work_link, has gone to the agent with a prompt of this process: the lock holds for
        # the session only from then, so no refusal reaches an agent never told of it, code.dispatcher.agent#47.
        self.ruled = False
        self.permissions: dict[str, dict[str, Any]] = {}  # each permission request asked, by its request id
        self.patches: dict[str, tuple[Any, dict[str, Any]]] = {}  # a running call's diffs, worked out once each
        self.named: set[str] = set()  # the lines kept for something, such as one tool call, changed in place
        self.lines = 0
        self.tools: dict[str, dict[str, Any]] = {}
        # The parts of the map each tool call has touched, and those not yet told to the open pages, `flowed`
        self.reached: dict[str, set[tuple[str, str]]] = {}
        self.flowing: list[dict[str, Any]] = []
        self.flow_kind: str | None = None
        self.flow_text = ''
        self.flow_key: str | None = None  # the note the text being written grows in
        self.flow_at = 0.0
        self.lines_at = 0.0  # when the last `dispatch.session_lines` event was fired
        self.lines_due: asyncio.TimerHandle | None = None  # the event that covers lines written since, when one waits
        self.flows = 0
        self.asked: dict[str, tuple[asyncio.Future[str | None], list[PermissionOption], str]] = {}
        self.answers: dict[str, tuple[str | None, str | None]] = {}  # the answer revision already delivered
        self.heard = stamp()  # the last session update or prompt, the earliest a tool call first seen next began
        self.turns = 0
        self.active_turn: ActiveTurn | None = None
        # a conversation's opening turn, its greeting: what the person sends during it waits for it to end rather than
        # being steered in, so the agent greets once and then answers, in order, never twice in one reply
        self.opening = False
        self.interrupt_lock = asyncio.Lock()  # cancellation cannot spill into the next queued prompt
        self.pending: deque[str] = deque()  # prompts wait in arrival order while one turn is in flight
        # beside each, the ACP blocks of the person's recording and the frame they sent, the ones its agent takes
        self.voiced: deque[list[Any]] = deque()
        self.peered: deque[list[tuple[str, str]]] = deque()  # each waiting prompt's peer notes, beside `pending`
        self.awaiting: dict[str, dict[str, Any]] = {}  # this session's questions waiting for replies, by note id
        self.timers: dict[str, dict[str, Any]] = {}  # the agent's own timers, `dispatch timer`, by id
        self.idle = asyncio.Event()
        self.idle.set()
        self.lock = asyncio.Lock()
        self.starting = asyncio.Lock()  # shutdown waits for resources an in-flight startup acquires
        self.ended = asyncio.Event()
        self.ending = False
        self.over = asyncio.Event()
        self.how = ''
        self.tasks: set[asyncio.Task[Any]] = set()
        self.failure: Exception | None = None
        self.progress_steps = record.steps_done if record is not None else 0
        self.progress_at = time.monotonic()
        self.progress_calls = 0
        self.failed_input: str | None = None
        self.failed_count = 0
        self.record_asked = False  # the turn asking the agent to record at its node was decided, BASE-052
        self.finishing = False  # a done ticket's end is being decided; a second notice of it waits on none
        self.retrying = bool(ctx.nouns.get('retry'))  # resumed by the supervisor: it goes on with its ticket, P012
        # The store moved to a layout past this runner's code while newer code is on disk, STORE-029: the session is
        # handed to a runner on that code, `outdated`, with what this one was sent and could not record, and whether a
        # turn was cut short by it.
        self.handing = False
        self.handed_on: list[dict[str, Any]] = []
        self.cut = False
        self.budget: dict[str, Any] | None = None  # the token budget this session reached, M01
        self.silence: asyncio.TimerHandle | None = None  # the turn's silence clock, P040
        self.silent = False  # the silent signal is raised and waits for the agent's next word
        self.stderr_lines: list[str] = []  # the agent's stderr not yet written to the thread, P014
        self.stderr_due: asyncio.TimerHandle | None = None
        self.stderr_kept = 0  # bytes of stderr written to the thread
        self.stderr_dropped = 0  # bytes past STDERR_KB, said in one line at the end
        self.stderr_tail: deque[str] = deque(maxlen=STDERR_TAIL)
        self.echo = True  # the agent's stderr goes to this process's own, the runner's log; not for a verb's agent
        self.raw_init: dict[str, Any] = {}  # the agent's initialize answer as sent, its `_meta` extensions with it
        # Subagent sessions the agent started, P016, by their session id: name, task, state and their own thread's
        # line count and names, since each child's thread is kept under its own session id.
        self.children: dict[str, dict[str, Any]] = {}
        # Questions the agent put to the person through ACP's elicitation, by request: the person's answer resolves
        # each as an action and its content, ACP's accept, decline or cancel.
        self.elicited: dict[str, dict[str, Any]] = {}
        self.elicitations: dict[str, dict[str, Any]] = {}  # each question's line, by its name, kept at its latest
        # elicitation/complete for a page whose question is not asked yet, by its elicitation id, `complete_elicitation`
        self.completed_early: set[str] = set()
        self.run_id = str(ctx.nouns.get('run') or RUN)  # the run it spends against, a retry's the run it goes on, M01
        self.cost: float | None = None  # the session's cumulative cost as last reported, to count what each adds
        self.metered = False  # the agent has reported some usage in this session
        self.steering: list[Any] = []  # the ids of _session/steering requests sent, the latest last
        # The agent's requests that wait on the person, by their JSON-RPC id: what each is, ('elicit' or 'permit', its
        # request), so the agent's `$/cancel_request` for one withdraws it; None until the request is asked, and
        # `withdrawn` holds the ids cancelled before then.
        self.incoming: dict[Any, tuple[str, str] | None] = {}
        self.withdrawn: set[Any] = set()
        self.provisional = 0  # the billable tokens the turn in flight is estimated to have used so far, M01
        self.context_used = 0  # the context the agent last reported in use, to see what each model call adds
        self.cost_open = True  # no prompt sent yet: a cost reported now is the session's baseline, not spend
        self.attached: list[dict[str, str]] = []  # resource links the next prompt carries beside its text
        self.closed = False  # session/close was sent
        self.probe = False  # started only to be asked something, P199 and P031: it keeps no thread
        self.sent: list[prompt_files.Sent] = []  # the prompt versions served since the last turn went out
        self.left_out = ''  # what initialize could not offer, said in the thread once it exists
        self.terminals: dict[str, Terminal] = {}  # the agent's terminals, ACP's terminal/*, by their id, P019
        self.terminal_count = 0
        self.servers: list[McpServerStdio] = []  # the MCP servers its session was given, given again to a fork
        self.stop_record_asked = False  # the turn asking a stopped or failed worker to record was decided, P033
        self.interrupted = False  # the last turn ended by the person's interrupt, so no recording turn follows it
        # An intake agent's first Metaform call and first record, M04: when its first turn began, the seconds each
        # took, and whether it was steered; and its clock, which steers it once when no call has come in time.
        self.intake: dict[str, Any] | None = {'phase': 'starting'} if self.role == 'intake' else None
        self.intake_began = 0.0
        self.intake_timer: asyncio.TimerHandle | None = None
        self.withheld: list[str] = []  # what the intake agent's server leaves out, dispatch_intake_withheld
        self.effects: dict[tuple[str, str], str] | None = None  # each Metaform tool's effect, read when needed
        self.calls: deque[str] = deque(maxlen=jev.CALLS)  # the latest tool calls, one line each, for Jev's drift check
        self.drift_at = 0  # the fresh calls counted when Jev was last asked about drift
        self.drifting = False  # a drift check is in flight
        self.paused_runs: set[str] = set()  # the workflow runs this worker's ticket paused on the person, H03
        self.workflow_reading = False
        self.workflow_again = False  # a change to its runs came while they were read: read once more after
        self.checking = False  # a check runs; a change for it meanwhile asks for one more, `checks`
        self.check_again = False
        self.spinning = False  # spinning-time is raised, until the ticket next advances
        self.auth_heard = asyncio.Event()  # the agent pushed its login state, `_auth/status_update`
        self.state_noted = False  # a state or subagent line written since the lines were last announced

    def option(self, key: str, default: Any) -> Any:
        """A setting of the session's context, or `default` when it cannot be read, so a setting that is not there
        never keeps a session from starting."""
        try:
            return self.ctx.setting(key)
        except Exception:  # noqa: BLE001  a missing or unreadable setting is the default
            return default

    @property
    def waiting(self) -> bool:
        """The agent waits on the person: a permission request or a question of its own is open."""
        return bool(self.asked or self.elicited)

    async def raise_signal(self, signal: str, *, key: str = '', active: bool = True, **details: Any) -> None:
        if self.probe:  # an agent started only to be asked something answers its asker, and raises nothing
            return
        from .signals import record
        value = await asyncio.to_thread(record, self.store, signal, work_id=self.work_id,
                                        session_id=self.session_id or '', key=key, active=active, **details)
        if value is not None:
            self.lines += 1
            await self.ctx.publish_async('signal.raised' if active else 'signal.cleared', value)
            self.lines_covered()
            await self.ctx.publish_async('map.changed', {'project': self.store.project_id, 'tables': 'dispatch',
                                                       'dispatch_tables': ['dispatch.lines'], 'signal': value,
                                                       **concerning(self.work_id, self.session_id, ['dispatch.lines'],
                                                                    True)})

    async def progress(self, record: WorkRecord | None = None) -> None:
        """Observe progress on an incoming event, never with a timer or a repeated wait. The ticket is the one a change
        to it was read for, `check`; an update of the agent's own reads nothing and only looks at the clock."""
        if self.prep or self.ending:
            return
        if record is not None and (record.steps_done != self.progress_steps or record.done):
            if record.steps_done > self.progress_steps and self.folder != self.root:  # a worktree's step, P009
                said = record.said[-1].said if record.said else ''
                await asyncio.to_thread(checkpoint, self.folder, self.work_id,
                                        f'Step {record.steps_done} of ticket {self.work_id}: {said or ""}'.strip())
            self.progress_steps = record.steps_done
            self.progress_at = time.monotonic()
            self.progress_calls = self.failed_count = self.drift_at = 0
            self.failed_input = None
            self.spinning = False
            for signal in ('spinning-calls', 'spinning-time', 'repeated-failure'):
                await self.raise_signal(signal, active=False)
        elif self.turns and not self.waiting and not self.spinning \
                and time.monotonic() - self.progress_at >= 60 * self.ctx.setting('dispatch_spin_minutes'):
            self.spinning = True
            await self.raise_signal('spinning-time', minutes=self.ctx.setting('dispatch_spin_minutes'))

    @property
    def by(self) -> str:
        return f'{self.agent} {self.session_id}'

    def spawn(self, coroutine: Coroutine[Any, Any, Any]) -> None:
        task = asyncio.create_task(coroutine)
        self.tasks.add(task)
        task.add_done_callback(self.finished)

    def finished(self, task: asyncio.Task[Any]) -> None:
        self.tasks.discard(task)
        if not task.cancelled() and (error := task.exception()) is not None:
            self.fail(error)

    def fail(self, error: BaseException) -> None:
        """A failed callback must wake the owner, including callbacks whose errors the ACP SDK catches."""
        if self.outdated(error):
            return
        if not self.ending and isinstance(error, Exception):
            self.failure = self.failure or error
            self.ended.set()

    def outdated(self, error: BaseException) -> bool:
        """Whether a refusal is the store at a layout past this runner's code while the code on disk has changed,
        STORE-029: at the first such refusal, a write or a read, the session ends here and goes on in a runner on the
        code on disk, `hand_over`, with the prompts still waiting to be sent. A store from a release newer than the
        code on disk too is not: its refusal fails the session as any other."""
        if self.handing:
            return True
        if not isinstance(error, NewerStore) or self.ending or self.probe or not self.recorded \
                or self.session_id is None or code_print() == LOADED:
            return False
        self.handing, self.cut, self.how = True, self.turns > 0, HANDED
        self.handed_on.extend({'text': text, 'by': None} for text in self.pending)  # their lines are written
        sys.stderr.write(f'Session {self.session_id} on work {self.work_id} is handed to a runner on the code on '
                         f'disk: {error}\n')
        self.ended.set()
        return True

    # ------------------------------------------------------------------ the map

    async def write(self, function: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        """One write through the store, off the loop, then `map.changed`, so an open web GUI shows it at once."""
        try:
            result = await asyncio.to_thread(function, *args, **kwargs)
            await self.changed()
        except Exception as error:
            self.fail(error)
            raise
        return result

    async def table(self, change: Callable[[Any], Any], *, name: str = 'session_lines', fatal: bool = True) -> Any:
        """One write to this module's own tables, off the loop, then `map.changed` naming the dispatch tables, so an
        open agent window shows it at once and an open page reads only its agents again, not the map, STORE-045. A
        write that is not `fatal`, a line of a thread, is logged when it fails and the runner goes on without it,
        code.dispatcher.agent#12."""
        def done() -> Any:
            with self.store.tables() as tx:
                return change(tx)
        try:
            result = await asyncio.to_thread(done)
            if name == 'session_lines':
                await self.lines_changed()
            else:
                await self.changed(tables='dispatch', dispatch_tables=[f'dispatch.{name}'])
        except Exception as error:
            if not fatal and not isinstance(error, NewerStore):
                sys.stderr.write(f'A line of session {self.session_id} on work {self.work_id} was not written: '
                                 f'{error}\n')
                return None
            if not fatal:  # a store this code cannot write keeps no line of it: the session goes on elsewhere or ends
                self.fail(error)
                return None
            self.fail(error)
            raise
        return result

    async def lines_changed(self) -> None:
        """Announce lines written: at once when none was announced in the last `LINES_EVERY` seconds, otherwise once
        when that time is up, covering every line written meanwhile. Any other event announces them with it."""
        wait = self.lines_at + LINES_EVERY - time.monotonic()
        if wait <= 0:
            await self.changed(tables='dispatch', dispatch_tables=['dispatch.session_lines'])
        elif self.lines_due is None:
            self.lines_due = asyncio.get_running_loop().call_later(wait, lambda: self.spawn(self.lines_flush()))

    async def lines_flush(self) -> None:
        if self.lines_due is not None:  # an event fired since has announced them
            await self.changed(tables='dispatch', dispatch_tables=['dispatch.session_lines'])

    def lines_covered(self) -> None:
        """An event about to fire tells readers of the lines too, so a waiting one is not needed."""
        if self.lines_due is not None:
            self.lines_due.cancel()
            self.lines_due = None
        self.lines_at = time.monotonic()

    async def changed(self, tables: str | None = None, *, dispatch_tables: list[str] | None = None,
                      kinds: list[str] | None = None) -> None:
        """Announce this session's writes on `map.changed`. `kinds` names a change no table holds, such as the session
        now working or idle, `session`, so a reader of other kinds reads nothing for it."""
        if self.base_id is None:
            active = await asyncio.to_thread(self.store.active_base)
            self.base_id = active.id if active is not None else None
        payload: dict[str, Any] = {'project': self.store.project_id, 'base_id': self.base_id}
        if tables:
            payload['tables'] = tables
        if dispatch_tables is not None and self.lines_due is not None:
            dispatch_tables = sorted({*dispatch_tables, 'dispatch.session_lines'})
        if dispatch_tables is not None:
            payload['dispatch_tables'] = dispatch_tables
        if self.flowing:  # where the agent's tool calls reached since the last event, `flowed`
            payload['flow'], self.flowing = self.flowing, []
        stated = False
        if tables != 'dispatch' or dispatch_tables is None or THREAD_TABLES.intersection(dispatch_tables):
            self.lines_covered()  # no detail, or the map's tables, reads the agents too
            stated, self.state_noted = self.state_noted, False
        if tables == 'dispatch':  # this session's own tables: its ticket and session, so no other runner reads for it
            about = concerning(self.work_id, self.session_id, dispatch_tables)
            if kinds and (dispatch_tables is None or 'kinds' in about):
                about['kinds'] = sorted({*about.get('kinds', []), *kinds})
            if stated and 'kinds' in about:  # its state or a subagent's line: the session changed, not its thread only
                about['kinds'] = sorted({*about['kinds'], 'session'})
            payload.update(about)
        await self.ctx.publish_async('map.changed', payload)

    def extra(self, state: str) -> dict[str, Any]:
        return {'dispatch': 'session', 'work_id': self.work_id, 'agent': self.agent, 'session_id': self.session_id,
                'recovery': self.recovery, 'pid': os.getpid(), 'port': self.port, 'token': self.token, 'state': state,
                'how': self.how or None, 'runner': self.runner}

    def summary(self, state: str) -> str:
        return f'{self.name} session {self.session_id} on work {self.work_id}: {state}'

    async def note(self, key: str | None, kind: str, text: str) -> None:
        """A line of the session's thread, in this module's tables and never on the map: a new one, or the one kept
        for `key` changed in place. An agent started only to be asked something keeps no thread."""
        if self.session_id is None or self.probe:
            return
        session_id, known = self.session_id, self.lines
        if kind in STATE_LINES:
            self.state_noted = True  # announced as a change to the session, `changed`
        written = await self.table(lambda tx: add_line(tx, session_id, self.work_id, key, kind, text, known),
                                   fatal=False)
        if written is not None:
            self.named.add(written[0])
            self.lines = max(self.lines, written[1])

    async def unstarted(self, text: str) -> None:
        """An agent that never made its session still leaves its ticket a session row, ended with why, and the failure
        as that row's one line, since a thread needs a session: the ticket, the page and whoever started it then read
        that it did not start and why, and its launch gives back its slot at once."""
        row = {key: value for key, value in self.extra('ended').items() if key != 'dispatch'}
        row.update(session_id=f'start-{self.runner}', pid=None, port=None, token=None,
                   started=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), seq=time.time_ns() // 1_000_000,
                   origin=origin())

        def write(tx: Any) -> None:
            tx.insert('agent_sessions', row)
            add_line(tx, row['session_id'], self.work_id, None, 'failed', text)
        await self.table(write, name='agent_sessions', fatal=False)

    async def flush(self) -> None:
        """The message or thought text gathered so far, as one note: the note it has grown in while it was written."""
        kind, text, key = self.flow_kind, self.flow_text, self.flow_key
        self.flow_kind, self.flow_text, self.flow_key = None, '', None
        if kind is not None and text:
            await self.note(key, kind, text)

    # ------------------------------------------------------------------ the ACP client, called by the SDK

    async def session_update(self, session_id: str, update: Any, **kwargs: Any) -> None:
        data: dict[str, Any] = update.model_dump(mode='json', by_alias=True, exclude_none=True)
        kind = str(data.get('sessionUpdate', ''))
        if self.replaying and kind not in STATE_UPDATES:
            return  # the history session/load replays is in the thread already
        self.awake()
        if session_id in self.children:  # a subagent's own update goes in its own thread, P016
            async with self.lock:
                await self.child_update(session_id, kind, data)
            return
        heard, self.heard = self.heard, stamp()
        async with self.lock:
            await self.progress()
            if kind in CHUNKS:
                if kind != self.flow_kind:
                    await self.flush()
                    self.flow_kind = kind
                    self.flows += 1
                    self.flow_key = f'flow:{self.flows}'
                self.flow_text += chunk_text(data.get('content'))
                now = time.monotonic()
                if now - self.flow_at >= STREAM_EVERY:  # the text so far, grown in place, so it reads as it is written
                    self.flow_at = now
                    await self.note(self.flow_key, kind, self.flow_text)
                return
            await self.flush()
            if kind in ('tool_call', 'tool_call_update'):
                ident = str(data.get('toolCallId', ''))
                fresh = ident not in self.tools
                # a call first seen before it completes began then; one first seen complete, after the update before it
                known = self.tools.setdefault(ident, {'began': heard if data.get('status') == 'completed' else
                                                      self.heard})
                for field in ('title', 'kind', 'status', 'rawInput'):
                    if data.get(field):
                        known[field] = data[field]
                for field in ('content', 'locations'):  # an update that carries either replaces it whole, as ACP says
                    if field in data:
                        known[field] = data[field]
                title = known.get('title') or known.get('kind') or 'A tool call'
                await self.note(f'tool:{ident}', kind, f'{title} ({known.get("status", "pending")})')
                detail = await self.tool_detail({**known, 'toolCallId': ident, 'title': title})
                # a call of a Metaform tool keeps what it was given and gave back, for a page that shows that tool's
                # MCP App view with the call, its tool-input and tool-result; kept past the call, as its line is
                called = metaform_called(known, data, title)
                if called is not None:  # an update without the input or the result keeps those already known
                    held_call = cast(dict[str, Any], known.get('called') or {})
                    known['called'] = {**held_call, **{key: value for key, value in called.items() if value}}
                if known.get('called') is not None:
                    detail: dict[str, Any] | None = {**(detail or {'tool_call_id': ident, 'title': title, 'kind': known.get('kind'),
                                            'status': known.get('status', 'pending'), 'diffs': [], 'locations': [],
                                            'terminals': [], 'nodes': []}), 'call': known['called']}
                if detail is not None:
                    self.flowed(ident, detail['nodes'], str(known.get('kind') or 'other'))
                    await self.note(f'detail:{ident}', 'tool_detail', json.dumps(detail, ensure_ascii=False))
                    await self.touch(detail['nodes'], str(known.get('kind') or 'other'))
                line = call_line({**known, 'title': title})
                if self.intake is not None and (fresh or known.get('status') in ('completed', 'failed')):
                    await self.intake_call(line, known.get('status') == 'completed', ident)
                if fresh and not self.prep and not self.ending:
                    self.calls.append(line)
                    if self.progress_calls + 1 - self.drift_at >= DRIFT_EVERY and \
                            await asyncio.to_thread(jev.config, Path(self.root), 'session_drift') is not None:
                        self.drift_at = self.progress_calls + 1
                        self.spawn(self.drift())
                    self.progress_calls += 1
                    if self.progress_calls >= self.ctx.setting('dispatch_spin_calls'):
                        await self.raise_signal('spinning-calls', calls=self.progress_calls)
                if not self.prep and not self.ending and known.get('status') in ('failed', 'completed') and not known.get('counted'):
                    known['counted'] = True
                    if known['status'] == 'failed':
                        fingerprint = json.dumps([known.get('kind'), title, known.get('rawInput')], sort_keys=True)
                        self.failed_count = self.failed_count + 1 if fingerprint == self.failed_input else 1
                        self.failed_input = fingerprint
                        if self.failed_count >= self.ctx.setting('dispatch_repeat_failures'):
                            await self.raise_signal('repeated-failure', calls=self.failed_count, tool=title)
                    else:
                        self.failed_input, self.failed_count = None, 0
                if known.get('status') in ('failed', 'completed'):
                    # Its line and its detail line hold what it did; a long session keeps no copy of each file's text.
                    for field in ('content', 'locations', 'rawInput'):
                        known.pop(field, None)
            elif kind == 'plan':
                entries: list[Any] = data.get('entries') or []
                said = [cast(dict[str, Any], entry) for entry in entries if isinstance(entry, dict)]
                await self.note('plan', kind, '\n'.join(f'{entry.get("content")} ({entry.get("status")})'
                                                        for entry in said))
                self.acp['plan'] = [{key: entry.get(key) for key in ('content', 'priority', 'status')} for entry in said]
                self.reported('plan')
                await self.save_state()
            elif kind in STATE_UPDATES:
                self.updated(kind, data)
                await self.save_state()
                if kind == 'usage_update' and isinstance(data.get('used'), (int, float)) and not self.replaying:
                    await self.provision(int(data['used']))
                if kind == 'usage_update' and isinstance(data.get('cost'), dict):
                    await self.cost_spent(cast(dict[str, Any], data['cost']))
            elif kind == 'notice':  # written from the wire in observe, which sees it whatever the SDK's schema knows
                return
            else:
                rest = {key: value for key, value in data.items() if key != 'sessionUpdate'}
                await self.note(kind, kind, json.dumps(rest, ensure_ascii=False))

    def reported(self, key: str) -> None:
        """The agent has reported this part of its state since a resume; a replay of its history has not."""
        if not self.replaying and key in self.acp['before_resume']:
            self.acp['before_resume'] = [held for held in self.acp['before_resume'] if held != key]

    def updated(self, kind: str, data: dict[str, Any]) -> None:
        """One update to what the session is, kept in its state."""
        if kind == 'available_commands_update':
            commands = cast(list[dict[str, Any]], data.get('availableCommands') or [])
            self.acp['commands'] = [{'name': one.get('name'), 'description': one.get('description'),
                                     'hint': cast(dict[str, Any], one.get('input') or {}).get('hint')}
                                    for one in commands]
            self.reported('commands')
        elif kind == 'current_mode_update':
            self.modes = {**(self.modes or {'available': []}), 'current': data.get('currentModeId')}
            self.spawn(self.hold_mode())
        elif kind == 'config_option_update':
            self.config = cast(list[dict[str, Any]], data.get('configOptions') or [])
            self.spawn(self.hold_mode())
        elif kind == 'session_info_update':
            for key, field in (('title', 'title'), ('updatedAt', 'updated_at')):
                if key in data:
                    self.acp[field] = data[key]
                    self.reported(field)
        elif kind == 'usage_update':
            self.acp['usage'] = {'used': data.get('used'), 'size': data.get('size'), 'cost': data.get('cost')}
            self.reported('usage')

    # ------------------------------------------------------------------ what the session is, for the page

    def capture(self, init: InitializeResponse, raw: dict[str, Any] | None = None) -> None:
        """What the agent said it can do when it was initialized, with the extensions its answer's `_meta` names."""
        meta = cast(dict[str, Any], (raw or {}).get('_meta') or {})
        caps_meta = cast(dict[str, Any], cast(dict[str, Any], (raw or {}).get('agentCapabilities') or {}).get('_meta')
                         or {})
        caps = init.agent_capabilities
        session = caps.session_capabilities if caps is not None else None
        prompts = caps.prompt_capabilities if caps is not None else None
        raw_session = cast(dict[str, Any], cast(dict[str, Any], (raw or {}).get('agentCapabilities') or {})
                           .get('sessionCapabilities') or {})
        self.acp['capabilities'] = {
            'load': bool(caps is not None and caps.load_session),
            'resume': bool(session is not None and session.resume is not None),
            'list': bool(session is not None and session.list is not None),
            'close': bool(session is not None and session.close is not None),
            'fork': bool(session is not None and session.fork is not None),
            'delete': raw_session.get('delete') is not None,
            'image': bool(prompts is not None and prompts.image),
            'audio': bool(prompts is not None and prompts.audio),
            'embedded_context': bool(prompts is not None and prompts.embedded_context),
            # Extensions an agent advertises in `_meta`, used only when advertised: `_session/steering` at the top
            # level of its answer, claude-agent-acp and codex-acp; the authStatus push in its capabilities' `_meta`.
            'steering': bool(cast(dict[str, Any], meta.get('steering') or {}).get('supported')),
            'auth_status': 'authStatus' in caps_meta,
            'logout': bool(caps is not None and caps.auth is not None and caps.auth.logout is not None)}
        info = init.agent_info
        self.acp['agent_info'] = info.model_dump(mode='json', exclude_none=True, exclude={'field_meta'}) \
            if info is not None else None
        self.asking = ASKING_MODES.get(str(info.name if info is not None else '').rsplit('/', 1)[-1]) \
            if LINK_LOCK else None  # with the lock off, the agent keeps the mode the person chose, code#1e
        # The logins it offers, as sent, since a method's `type` (agent, terminal or env_var) is what says how it runs.
        methods = cast(list[Any], (raw or {}).get('authMethods') or [])
        self.acp['auth_methods'] = [
            {key: value for key, value in cast(dict[str, Any], method).items()
             if key in ('id', 'name', 'description', 'type', 'args', 'env', 'vars', 'link')}
            for method in methods if isinstance(method, dict) and cast(dict[str, Any], method).get('id')]

    def apply(self, made: Any) -> None:
        """The modes and config options a session/new, load or resume answered with; `offered` says whether it named
        either, since a resume or load may leave both out, ACP's session-setup."""
        self.offered = False
        if made is None:
            return
        modes = getattr(made, 'modes', None)
        self.offered = modes is not None or getattr(made, 'config_options', None) is not None
        if modes is not None:
            self.modes = {'current': modes.current_mode_id,
                          'available': [{'id': mode.id, 'name': mode.name, 'description': mode.description}
                                        for mode in modes.available_modes]}
        options = getattr(made, 'config_options', None)
        if options is not None:
            self.config = [option.model_dump(mode='json', by_alias=True, exclude_none=True) for option in options]
        if self.asking is not None and self.chosen_mode is None:  # the mode it began in is the person's until changed
            self.chosen_mode = self.mode_now()

    def mode_now(self) -> str | None:
        """The mode the agent says it is in: its config option of category mode, else its session modes' current."""
        found = next((option.get('currentValue') for option in self.config if option.get('category') == 'mode'), None)
        return str(found) if found is not None else cast(str | None, (self.modes or {}).get('current'))

    async def hold_mode(self) -> None:
        """An agent that writes without asking outside one mode is put back in that mode whenever it is in another,
        whatever the person chose, which goes on deciding what is approved without asking, CTX-061."""
        if self.asking is None or self.ending or self.session_id is None or self.mode_now() in (None, self.asking):
            return
        found = next((one for one in self.settings() if one['category'] == 'mode'), None)
        if found is not None:
            await self.configure(str(found['id']), str(self.chosen_mode or self.asking))

    def settings(self) -> list[dict[str, Any]]:
        """What the person can set on this session, each a select or a switch: the agent's config options, a model
        among them, and its session modes as one more select, `source` mode, unless a config option already is the
        mode, which ACP says supersedes the modes."""
        found = [setting_of(option) for option in self.config]
        available = cast(list[dict[str, Any]], (self.modes or {}).get('available') or [])
        if available and not any(one['category'] == 'mode' for one in found):
            taken = {one['id'] for one in found}
            found.insert(0, {'id': 'mode' if 'mode' not in taken else 'session_mode', 'name': 'Mode',
                             'description': None, 'category': 'mode', 'type': 'select',
                             'current': (self.modes or {}).get('current'),
                             'options': [{'value': mode['id'], 'name': mode['name'],
                                          'description': mode.get('description'), 'group': None}
                                         for mode in available], 'source': 'mode'})
        if self.asking is not None and self.chosen_mode is not None:  # the person's mode, which the agent runs as
            found = [{**one, 'current': self.chosen_mode} if one['category'] == 'mode' else one for one in found]
        return found

    async def remember(self) -> None:
        """What the agent offered, kept per agent and version in this project, P199: the settings of this session, its
        logins and extensions. The dispatch_<agent>_<option> settings offer them as their choices, and dispatch
        options lists them."""
        info = cast(dict[str, Any], self.acp['agent_info'] or {})
        caps = cast(dict[str, Any], self.acp['capabilities'])
        row = {'agent': self.agent, 'version': str(info.get('version') or 'unknown'), 'name': info.get('title')
               or info.get('name'), 'settings': self.settings(), 'auth': self.acp['auth_methods'],
               'extensions': {key: caps.get(key) for key in ('steering', 'auth_status', 'logout', 'resume', 'load',
                                                              'fork', 'close', 'delete')},
               'seen': stamp(), 'seq': time.time_ns()}

        def kept() -> None:
            with Store(self.store.project_id, module='dispatch').tables() as tx:
                held = tx.get('catalog', {'agent': row['agent'], 'version': row['version']})
                if not self.offered and held is not None:  # an answer naming no settings leaves those known as kept
                    row['settings'] = held['settings']
                tx.delete('catalog', {'agent': row['agent'], 'version': row['version']})
                tx.insert('catalog', row)
        try:
            await asyncio.to_thread(kept)
        except StoreError as error:  # a catalog that cannot be written never keeps a session from starting
            sys.stderr.write(f'Could not keep what {self.name} offered: {error}\n')

    def jev_chosen(self) -> dict[str, str]:
        """The model and effort Jev chose when autostart started this session, by ACP category; none otherwise."""
        try:
            found: Any = json.loads(str(self.ctx.nouns.get('chosen') or '{}'))
        except ValueError:
            return {}
        given = cast(dict[str, Any], found) if isinstance(found, dict) else {}
        return {key: str(value) for key, value in given.items() if key in ('model', 'thought_level') and value}

    async def apply_options(self) -> list[dict[str, Any]]:
        """Give the session the settings chosen for it, P199 and P015: its agent's dispatch_<agent>_<option> settings,
        then its ticket's own model and effort, each matched to the agent's settings by ACP category or by id and set through
        session/set_config_option, or session/set_mode for a mode, in APPLY_ORDER, so a model switch never undoes the
        effort chosen with it. A choice the agent does not offer is said once in the thread and left; one already
        current, as the agent's latest answer has it, is not sent again."""
        if self.ending or self.session_id is None:
            return []
        await self.hold_mode()
        wanted = await asyncio.to_thread(wanted_options, self.ctx, self.store, self.agent,
                                         None if self.node is None else self.work_id)
        wanted = {**self.jev_chosen(), **wanted}  # Jev's choice, H23, under every choice of the person's
        if self.launched:  # the mode its start gave this launch, over dispatch_<agent>_<option>
            found = await asyncio.to_thread(launch_options, self.store, self.work_id)
            wanted = {**wanted, **({'mode': found['mode']} if 'mode' in found else {})}
        rank = {key: at for at, key in enumerate(APPLY_ORDER)}
        done: list[dict[str, Any]] = []
        for key, value in sorted(wanted.items(), key=lambda pair: rank.get(pair[0], len(APPLY_ORDER))):
            found = next((one for one in self.settings() if option_key(one) == key), None)
            if found is None:
                async with self.lock:
                    await self.note(f'option:{key}', 'notice', f'{self.name} offers no {key} on this session, so '
                                                             f'{key}={value} was not applied.')
                done.append({'key': key, 'value': value, 'error': 'not offered'})
                continue
            current = found.get('current')
            if str(current).casefold() == value.casefold():
                continue
            result = await self.configure(str(found['id']), value)
            done.append({'key': key, 'value': value, **({'error': result['error']} if 'error' in result else {})})
            if 'error' in result:
                async with self.lock:
                    await self.note(f'option:{key}', 'notice', str(result['error']))
        return done

    # ------------------------------------------------------------------ extensions the agent advertises

    def observe(self, event: StreamEvent) -> None:
        """Every message from the agent, seen before the SDK reads it: a subagent's start and end, P016, which the
        SDK's schema does not know, so it would drop them; the id of each steering request sent, which the SDK does
        not return, so a steer that takes too long can be cancelled by it; and ACP's request cancellation, which the SDK
        does not handle: the id of each request of the agent's that waits on the person, permission or question, is
        noted, and the agent's `$/cancel_request` for one withdraws it. The rest is the SDK's to handle."""
        method = event.message.get('method')
        if event.direction == StreamDirection.OUTGOING:
            if method == '_session/steering' and 'id' in event.message:
                self.steering.append(event.message['id'])
            return
        INCOMING.set(event.message.get('id') if method is not None else None)
        if method in ('elicitation/create', 'session/request_permission') and 'id' in event.message:
            self.incoming[event.message['id']] = None
        if method == '$/cancel_request':
            ident = cast(dict[str, Any], event.message.get('params') or {}).get('requestId')
            if ident in self.incoming:
                self.spawn(self.withdraw(ident))
            return
        if method != 'session/update':
            return
        params = cast(dict[str, Any], event.message.get('params') or {})
        update = cast(dict[str, Any], params.get('update') or {})
        kind, child = update.get('sessionUpdate'), str(update.get('subagentSessionId') or '')
        if kind == 'notice' and not self.replaying:  # ACP's session notices, which this SDK's schema does not know
            self.spawn(self.notice({key: update.get(key) for key in ('severity', 'title', 'description')}))
            return
        if kind not in ('subagent_spawned', 'subagent_state_update') or not child:
            return
        held = self.children.setdefault(child, {'session_id': child, 'name': None, 'task': None, 'state': 'running',
                                                'started': stamp(), 'lines': 0, 'named': set(), 'flow': None})
        if kind == 'subagent_spawned':  # registered at once, so its first updates go to its own thread
            held.update(name=update.get('name'), task=update.get('task'))
        else:
            held['state'] = str(update.get('state') or 'ended')
        self.spawn(self.child_line(child))

    async def notice(self, said: dict[str, Any]) -> None:
        """One of ACP's session notices, the agent's own word on its state, such as an MCP server it could not start:
        a line of the thread of its own, by severity, so it is never read as the agent's words. Live only: a notice
        is never replayed, as the RFD says."""
        async with self.lock:
            await self.flush()
            await self.note(None, 'agent_notice', json.dumps(said, ensure_ascii=False))

    async def child_line(self, child: str) -> None:
        """A subagent's line in its parent's thread, kept at its latest: its session id, name, task and state, and
        whether it is a fork made by session/fork rather than the agent's own subagent."""
        held = self.children[child]
        async with self.lock:
            flow = cast(dict[str, Any] | None, held['flow'])
            if flow is not None and held['state'] != 'running':  # its last words, whole, as it ended
                await self.child_note(child, str(flow['key']), str(flow['kind']), str(flow['text']))
                held['flow'] = None
            await self.flush()
            await self.note(f'subagent:{child}', 'subagent', json.dumps(
                {**{key: held[key] for key in ('session_id', 'name', 'task', 'state', 'started')},
                 'fork': bool(held.get('fork'))}, ensure_ascii=False))

    async def child_note(self, child: str, key: str | None, kind: str, text: str) -> None:
        """A line of a subagent's own thread, under its session id: a new one, or the one kept for `key`."""
        held = self.children[child]
        known = int(held['lines'])
        written = await self.table(lambda tx: add_line(tx, child, self.work_id, key, kind, text, known), fatal=False)
        if written is not None:
            cast(set[str], held['named']).add(written[0])
            held['lines'] = max(known, written[1])

    async def child_update(self, child: str, kind: str, data: dict[str, Any]) -> None:
        """One update of a subagent's session, in its own thread: its words and thinking growing in place, each tool
        call one line changed as its status changes, and its plan."""
        held = self.children[child]
        flow = cast(dict[str, Any] | None, held['flow'])
        if flow is not None and kind != flow['kind']:  # the text it was writing is whole: written as it ended
            await self.child_note(child, str(flow['key']), str(flow['kind']), str(flow['text']))
            held['flow'] = flow = None
        if kind in CHUNKS:
            if flow is None:
                held['flows'] = int(held.get('flows', 0)) + 1
                flow = held['flow'] = {'kind': kind, 'key': f'flow:{held["flows"]}', 'text': '', 'at': 0.0}
            flow['text'] = str(flow['text']) + chunk_text(data.get('content'))
            if time.monotonic() - float(flow['at']) >= STREAM_EVERY:  # grown in place, as the parent's text is
                flow['at'] = time.monotonic()
                await self.child_note(child, str(flow['key']), kind, str(flow['text']))
            return
        if kind in ('tool_call', 'tool_call_update'):
            calls = cast(dict[str, dict[str, Any]], held.setdefault('tools', {}))
            known = calls.setdefault(str(data.get('toolCallId', '')), {})
            known.update({field: data[field] for field in ('title', 'kind', 'status') if data.get(field)})
            await self.child_note(child, f'tool:{data.get("toolCallId")}', kind,
                                  f'{known.get("title") or known.get("kind") or "A tool call"} '
                                  f'({known.get("status", "pending")})')
        elif kind == 'plan':
            entries = cast(list[dict[str, Any]], data.get('entries') or [])
            await self.child_note(child, 'plan', kind, '\n'.join(f'{entry.get("content")} ({entry.get("status")})'
                                                                 for entry in entries))

    async def ext_notification(self, method: str, params: dict[str, Any]) -> None:
        """An extension notification from the agent: `_auth/status_update`, the login the agent itself uses, which
        claude-agent-acp and codex-acp push when they advertise authStatus, P031. A known logged-out state raises the
        login-needed signal, naming dispatch login; any other clears it. Others are not used."""
        if method != 'auth/status_update':
            return
        status = params.get('authStatus')
        self.acp['auth'] = status if isinstance(status, dict) else None
        if self.acp['auth'] is not None:
            self.auth_heard.set()
        self.reported('auth')
        logged_out = isinstance(status, dict) and cast(dict[str, Any], status).get('kind') == 'none'
        async with self.lock:
            await self.save_state()
            await self.raise_signal('login-needed', key=self.agent, active=logged_out, agent=self.agent,
                                    next=f'metaform dispatch login {self.agent}')

    async def steer(self, text: str) -> bool | None:
        """Deliver a message into the turn in flight with the agent's `_session/steering` request, when it advertises
        it: True when the agent took it into the turn, False when it is to go as the next
        prompt, the agent having answered promptRequired, refused it or offering no steering. None when the agent did
        not answer within SETTING_LIMIT: the request is withdrawn with ACP's `$/cancel_request`, and since the agent
        may have taken it already, it is not sent again; the thread says so."""
        if not (self.acp['capabilities'].get('steering') and self.session_id and self.conn is not None):
            return False
        sent = len(self.steering)
        try:
            answer = await asyncio.wait_for(self.conn.ext_method('session/steering', {
                'sessionId': self.session_id, 'prompt': [{'type': 'text', 'text': text}],
                '_meta': {'steering': {'idleBehavior': 'promptRequired'}}}), SETTING_LIMIT)
        except TimeoutError:
            if len(self.steering) > sent and (raw := self.raw()) is not None:
                with contextlib.suppress(Exception):
                    await raw.send_notification('$/cancel_request', {'requestId': self.steering[sent]})
            self.carried()  # the agent may have taken it, so it is not sent again: counted as sent
            return None
        except Exception:  # noqa: BLE001  an error answer: the agent did not take it, so it goes as the next prompt
            return False
        injected = isinstance(answer, dict) and cast(dict[str, Any], answer).get('outcome') == 'injected'
        if injected:
            self.carried()
        return injected

    def raw(self) -> Any:
        """The SDK's JSON-RPC connection under the client one, for what its schema does not carry yet: initialize with
        the capabilities it leaves out, `$/cancel_request` and session/delete. None when an SDK version has none, and
        the caller does without."""
        return getattr(self.conn, '_conn', None) if self.conn is not None else None

    # ------------------------------------------------------------------ the agent's stderr, P014

    async def read_stderr(self, stream: asyncio.StreamReader) -> None:
        """The agent's standard error, line by line: each redacted, written to the runner's log, kept as the tail a
        failure note carries, and gathered into one stderr line of the thread every STDERR_EVERY seconds."""
        loop = asyncio.get_running_loop()
        while True:
            try:
                line = await stream.readline()
            except (ValueError, asyncio.LimitOverrunError):  # a line longer than the limit: what is there is read
                line = await stream.read(LINE_LIMIT)
            if not line:
                break
            text = redact(line.decode('utf-8', 'replace').rstrip('\r\n'))
            if self.echo:
                sys.stderr.write(text + '\n')
            self.stderr_tail.append(text)
            self.stderr_lines.append(text)
            if self.stderr_due is None:
                self.stderr_due = loop.call_later(STDERR_EVERY, lambda: self.spawn(self.stderr_flush()))
        await self.stderr_flush()

    async def stderr_flush(self) -> None:
        """The stderr gathered so far, as one line of the thread, within STDERR_KB for the session; what is
        past it is counted and said in one line. Kept until the session exists, which is when its thread does."""
        if self.stderr_due is not None:
            self.stderr_due.cancel()
            self.stderr_due = None
        if self.session_id is None or self.probe or not self.stderr_lines:
            return
        text, self.stderr_lines = '\n'.join(self.stderr_lines), []
        room = STDERR_KB * 1024 - self.stderr_kept
        size = len(text.encode('utf-8'))
        kept = text if size <= room else text.encode('utf-8')[:max(room, 0)].decode('utf-8', 'ignore')
        self.stderr_kept += len(kept.encode('utf-8'))
        self.stderr_dropped += size - len(kept.encode('utf-8'))
        if kept:
            await self.note(None, 'stderr', kept)
        if self.stderr_dropped:
            await self.note('stderr:dropped', 'stderr', f'{self.stderr_dropped} more bytes of stderr were left out, '
                                                        f'past {STDERR_KB} KB; the runner\'s log has them.')

    def tail(self) -> str:
        """The last lines the agent wrote to stderr, for a failure note."""
        return ' | '.join(self.stderr_tail)

    # ------------------------------------------------------------------ the turn's silence clock, P040

    def awake(self) -> None:
        """The agent said something: a raised silent signal is cleared, and while a turn is in flight and nothing waits
        on the person the silence clock starts again, so a turn that falls silent a second time is signalled again."""
        if self.silent:
            self.silent = False
            self.spawn(self.raise_signal('silent', active=False))
        if self.turns and not self.waiting:
            self.arm()

    def arm(self) -> None:
        """Start the turn's silence clock again: one timer per turn, never while the agent waits on the person."""
        self.hush()
        if self.ending or not self.turns or self.waiting:
            return
        try:
            seconds = float(self.ctx.setting('dispatch_silence_seconds'))
        except Exception:  # noqa: BLE001  a clock whose setting cannot be read is not started; the turn goes on
            return
        self.silence = asyncio.get_running_loop().call_later(seconds, lambda: self.spawn(self.silent_turn(seconds)))

    def hush(self) -> None:
        if self.silence is not None:
            self.silence.cancel()
            self.silence = None

    async def silent_turn(self, seconds: float) -> None:
        self.silence = None
        if self.ending or not self.turns or self.waiting or self.silent:
            return
        self.silent = True
        await self.raise_signal('silent', seconds=seconds, next=f'metaform dispatch interrupt {self.work_id}')

    # ------------------------------------------------------------------ spend, M01

    async def spend(self, usage: Any) -> None:
        """What a turn used, as the agent reported it at the turn's end, kept as a row of `spending` for the ticket, the
        run and the day: each kind of token apart and their billable sum, `billable`. A turn that ended with no usage
        at all, as an agent that reports none ends every turn, is kept as unmetered, so dispatch spend can say a budget
        cannot see it. Then the budgets are checked."""
        counts: dict[str, int | None] = {'input': None, 'output': None, 'cache_read': None, 'cache_write': None,
                                         'thought': None}
        if usage is not None:
            self.metered = True
            counts = {'input': usage.input_tokens, 'output': usage.output_tokens,
                      'cache_read': usage.cached_read_tokens, 'cache_write': usage.cached_write_tokens,
                      'thought': usage.thought_tokens}
        tokens = billable(counts) if usage is not None else 0
        held = cast(dict[str, Any], self.acp['spent'] or {'tokens': 0, 'cost': None})
        self.acp['spent'] = {**held, 'tokens': int(held.get('tokens') or 0) + tokens, 'metered': self.metered}
        self.reported('spent')
        row = {'session_id': cast(str, self.session_id), 'seq': time.time_ns(), 'work_id': self.work_id,
               'run': self.run_id, 'day': today(), 'tokens': tokens, 'metered': usage is not None, **counts}
        await self.table(lambda tx: tx.insert('spending', row), name='spending')
        self.provisional = 0  # the turn's estimate gives way to what the agent reported
        await self.budget_check()

    async def provision(self, used: int) -> None:
        """The turn's provisional meter, M01: the adapters report tokens only when a turn ends, and claude-agent-acp
        its cost only then too, but both report the context in use after each model call (ACP's usage_update `used`).
        Each call rereads the context and adds what grew, so while a turn is in flight each new reading adds an
        estimate, the context at the cache-read rate and its growth at the full rate, billable(); the token budgets
        are checked against what is stored plus this estimate, so dispatch_budget_action interrupt can stop a turn
        part way. The turn's reported usage replaces the estimate at its end."""
        before, self.context_used = self.context_used, used
        if not self.turns or self.active_turn is None or not self.active_turn.sent or used == before:
            return
        self.provisional += billable({'input': max(used - before, 0), 'cache_read': used})
        await self.budget_check(pending=self.provisional)

    async def cost_spent(self, cost: dict[str, Any]) -> None:
        """A usage update's cost, ACP's session usage, which is the session's cumulative cost: what it added since the
        last reading is kept as a row of `spending`, never the running total. A reading before this runner's first
        prompt, which ACP's session usage has an agent send after session/load or resume, is the session's standing
        total: it is the baseline, and adds nothing. Without one, the first reading counts from what the session's rows
        hold already, so a resumed session's history is not counted twice; a reading below the last is an agent that
        counts afresh after a restart, and counts from zero. Then the budgets are checked. claude-agent-acp reports
        cost only as a turn ends, so a cost budget acts then; the token budgets' provisional meter acts during it."""
        try:
            amount = float(cost.get('amount'))  # pyright: ignore[reportArgumentType]
        except (TypeError, ValueError):
            return
        if self.session_id is None:
            return
        if self.cost_open:
            self.cost = amount
            return
        if self.cost is None:
            self.cost = await asyncio.to_thread(session_cost, self.store, self.session_id)
        added = amount - self.cost if amount >= self.cost else amount
        self.cost = amount
        if added <= 0:
            return
        self.metered = True
        held = cast(dict[str, Any], self.acp['spent'] or {'tokens': 0})
        currency = str(cost.get('currency') or '')
        self.acp['spent'] = {**held, 'cost': {'amount': amount, 'currency': currency}, 'metered': True}
        self.reported('spent')
        row = {'session_id': self.session_id, 'seq': time.time_ns(), 'work_id': self.work_id, 'run': self.run_id,
               'day': today(), 'tokens': 0, 'cost': added, 'currency': currency or None, 'metered': True}
        await self.table(lambda tx: tx.insert('spending', row), name='spending')
        await self.budget_check()

    async def budget_check(self, pending: int = 0) -> None:
        """A budget reached raises the budget signal once, and the session gets no further turn of Metaform's own;
        with dispatch_budget_action interrupt, the turn in flight is cancelled too, as the person's interrupt is.
        `pending` is the turn's provisional estimate, counted on the token budgets."""
        if self.budget is not None:
            return
        reached = await asyncio.to_thread(over_budget, self.ctx, self.store,
                                          work_id=None if self.node is None else self.work_id, run=self.run_id,
                                          pending=pending)
        if reached is None or self.budget is not None:
            return
        self.budget = reached
        await self.raise_signal('budget', key=str(reached['budget']), **reached)
        if self.turns and await asyncio.to_thread(self.ctx.setting, 'dispatch_budget_action') == 'interrupt':
            self.spawn(self.interrupt())  # spawned: it takes the lock an update may be holding

    async def save_state(self) -> None:
        """The session's state line, kept at its latest."""
        await self.note('state', 'state', json.dumps({**self.acp, 'settings': self.settings()}, ensure_ascii=False))

    async def places(self) -> dict[str, list[dict[str, str]]]:
        if self.sources is None:
            self.sources = await asyncio.to_thread(sources_index, self.store, self.root)
        return self.sources

    async def denied(self) -> list[str] | None:
        """The paths of the project the agent's commands may not write, denied_writes', read now; None with LINK_LOCK
        off or for a probe, whose commands are not confined."""
        if self.probe or not LINK_LOCK:
            return None
        patterns = await asyncio.to_thread(home.ignore_patterns, self.root)
        return await asyncio.to_thread(denied_writes, self.root, self.folder, await self.places(), patterns)

    async def tool_detail(self, call: dict[str, Any]) -> dict[str, Any] | None:
        """What a tool call acts on, structured: each file it edits as a diff, each place it reads or writes, each
        terminal it runs, every file placed on the map; None for a call that names none."""
        content = cast(list[dict[str, Any]], call.get('content') or [])
        locations = cast(list[dict[str, Any]], call.get('locations') or [])
        edits = [one for one in content if one.get('type') == 'diff']
        terminals = [str(one.get('terminalId')) for one in content if one.get('type') == 'terminal']
        if not (edits or locations or terminals):
            return None
        index = await self.places()
        roots = [self.folder, self.root]
        nodes: list[dict[str, str]] = []

        def where(path: str) -> tuple[str, list[dict[str, str]], bool]:
            named = relative(path, roots)
            found, exact = placed(index, named)
            nodes.extend(place for place in found if place not in nodes)
            return named or path, found, exact

        diffs: list[dict[str, Any]] = []
        for at, edit in enumerate(edits):
            path, found, exact = where(str(edit.get('path', '')))
            old, new = edit.get('oldText'), str(edit.get('newText', ''))
            key, sign = f'{call.get("toolCallId")}:{at}', (path, hash(old), hash(new))
            held = self.patches.get(key)  # a status update carries the same diff again
            worked = held[1] if held is not None and held[0] == sign else \
                await asyncio.to_thread(unified, path, old, new)
            if call.get('status') in ('completed', 'failed'):
                self.patches.pop(key, None)  # the call is over: its diff is in its line
            else:
                self.patches[key] = (sign, worked)
            diffs.append({'path': path, **worked, 'nodes': found, 'exact': exact})
        places: list[dict[str, Any]] = []
        for location in locations:
            path, found, exact = where(str(location.get('path', '')))
            places.append({'path': path, 'line': location.get('line'), 'nodes': found, 'exact': exact})
        return {'tool_call_id': call.get('toolCallId'), 'title': call.get('title'), 'kind': call.get('kind'),
                'status': call.get('status', 'pending'), 'diffs': diffs, 'locations': places,
                'terminals': terminals, 'nodes': nodes}

    def flowed(self, ident: str, nodes: list[dict[str, str]], action: str) -> None:
        """The parts of the map a tool call reached that it had not reached before, from the ticket's node, for the open
        pages to draw as the agent's request going there, VIEW-005. They ride on the next `map.changed` this session
        fires, `changed`, as its `flow`; the line the call writes fires one within LINES_EVERY, so no event is added."""
        if self.probe or not nodes:
            return
        reached = self.reached.setdefault(ident, set())
        fresh = [{'kind': place['kind'], 'id': place['id']} for place in nodes if (place['kind'], place['id']) not in reached]
        if not fresh:
            return
        reached.update((place['kind'], place['id']) for place in fresh)
        self.flowing.append({'session_id': self.session_id, 'agent': self.agent, 'work_id': self.work_id,
                             'from': {'kind': self.node.kind, 'id': self.node.id} if self.node is not None else None,
                             'to': fresh, 'action': action})

    async def touch(self, nodes: list[dict[str, str]], action: str) -> None:
        """The parts of the map this session has touched, the latest first, kept in its state."""
        if not nodes:
            return
        held = cast(list[dict[str, str]], self.acp['touched'])
        fresh = [{**place, 'action': action} for place in nodes]
        kept = fresh + [one for one in held if (one['kind'], one['id']) not in {(p['kind'], p['id']) for p in fresh}]
        if kept[:TOUCHED_KEPT] != held:
            self.acp['touched'] = kept[:TOUCHED_KEPT]
            await self.save_state()

    async def configure(self, setting: str, value: str) -> dict[str, Any]:
        """Set one of the session's settings, as the person chose: a mode with session/set_mode, anything else with
        session/set_config_option; the agent's answer is the settings from then on."""
        if self.ending or self.session_id is None or self.conn is None:
            return {'error': 'The session has not started or is ending.'}
        offered = self.settings()
        found = next((one for one in offered if one['id'] == setting), None)
        if found is None:
            return {'error': f'{self.name} offers no setting {setting} on this session; it offers: '
                             f'{", ".join(str(one["id"]) for one in offered) or "none"}.'}
        try:
            if found['type'] == 'boolean':
                given = switched(value)
                if given is None:
                    return {'error': f'{found["name"]} is on or off, not {value}.'}
                answer = await asyncio.wait_for(self.conn.set_config_option(
                    config_id=found['id'], session_id=self.session_id, value=given), SETTING_LIMIT)
                chosen, shown = given, 'on' if given else 'off'
                sent: Any = given
            else:
                choices = cast(list[dict[str, Any]], found['options'])
                option = next((one for one in choices if one['value'] == value), None) or next(
                    (one for one in choices if str(one['name']).casefold() == value.strip().casefold()), None)
                if option is None:
                    listed = ', '.join(f"{one['name']} ({one['value']})" for one in choices)
                    return {'error': f'{value} is none of the choices of {found["name"]}: {listed}.'}
                chosen, shown = option['value'], option['name']
                sent = chosen
                if self.asking is not None and found['category'] == 'mode':  # kept asking, the choice kept, CTX-061
                    self.chosen_mode, sent = str(chosen), self.asking
                    if sent != chosen:
                        shown = f'{shown}, run as {self.asking} so every change of a file is asked first and ' \
                                f'{shown} decides what is approved without asking'
                if found['source'] == 'mode':
                    answer = await asyncio.wait_for(self.conn.set_session_mode(
                        session_id=self.session_id, mode_id=sent), SETTING_LIMIT)
                    self.modes = {**(self.modes or {'available': []}), 'current': sent}
                else:
                    answer = await asyncio.wait_for(self.conn.set_config_option(
                        config_id=found['id'], session_id=self.session_id, value=sent), SETTING_LIMIT)
        except Exception as error:  # noqa: BLE001  the agent's refusal is the person's to read
            return {'error': f'{self.name} did not take {found["name"]}: {error}'}
        if found['source'] == 'option':
            options = getattr(answer, 'config_options', None)
            if options is not None:
                self.apply(answer)
            else:  # an agent that answers with nothing has taken the value as given
                self.config = [{**option, 'currentValue': sent} if option.get('id') == found['id'] else option
                               for option in self.config]
        async with self.lock:
            await self.flush()
            await self.note(None, 'setting', f'{found["name"]} set to {shown}.')
            await self.save_state()
        return {'setting': found['id'], 'value': chosen, 'settings': self.settings()}

    # ------------------------------------------------------------------ the client's files and terminals, P019

    async def refuse(self, what: str, path: str, why: str) -> acp.RequestError:
        """A file or terminal request refused, said in the thread so the person sees it, and returned for the SDK to
        answer the agent with as invalid params, its reason in the error's data."""
        async with self.lock:
            await self.flush()
            await self.note(None, 'notice', f'{self.name} asked to {what} {path}: refused, {why}.')
        return acp.RequestError.invalid_params({'path': path, 'reason': why})

    async def confined(self, what: str, path: str | None) -> Path:
        """An absolute path inside the session's folder, its worktree when it has one, its links followed; a path
        outside it is refused, as is a relative one, which ACP does not allow."""
        if not path or not os.path.isabs(path):
            raise await self.refuse(what, str(path), 'ACP paths are absolute')
        found, root = Path(path).resolve(), Path(self.folder).resolve()
        if found != root and root not in found.parents:
            raise await self.refuse(what, path, f'it is outside the session\'s folder, {root}')
        return found

    async def filed(self, path: Path, action: str) -> list[dict[str, str]]:
        """A file the agent read or wrote through the runner: placed on the map, kept among the parts it touched, and
        kept in the session's state, the latest first."""
        named = relative(str(path), [self.folder, self.root]) or str(path)
        nodes, _ = placed(await self.places(), named)
        files = [{'path': named, 'action': action}] + [one for one in cast(list[dict[str, str]], self.acp['files'])
                                                        if one != {'path': named, 'action': action}]
        self.acp['files'] = files[:TOUCHED_KEPT]
        async with self.lock:
            await self.touch(nodes, action)
            await self.save_state()
        return nodes

    async def locked(self, named: str | None) -> str | None:
        """Why the agent may not write a file of the project, or None when it may, code.dispatcher.agent#3d: a path
        under the project's `.metaform/ignore.txt` is read-only to agents, linked or not; a file no element's ref
        names exactly is locked until the agent links it to its element, with the call that does it. A path outside the
        project is not the map's. Reads never come here: reading is how the agent finds where a file belongs. With
        LINK_LOCK off, no file is locked, the ignore list's included, until the rules and prompts are in place, Rich
        2026-10-15; nor before the rule has gone to the agent, `ruled`, code.dispatcher.agent#47."""
        if not named or self.probe or not LINK_LOCK or not self.ruled:
            return None
        patterns = await asyncio.to_thread(home.ignore_patterns, self.root)
        if patterns and ignored(patterns)(named):
            return prompt('write_ignored', file=named) or f'{named} is read-only to agents.'
        if not LINK_LOCK or placed(await self.places(), named)[1]:
            return None
        return ' '.join(part for part in (prompt('write_unlinked'), prompt('link_call', file=named)) if part)

    async def edit_locked(self, call: dict[str, Any]) -> str | None:
        """Why a permission request to change files is refused, or None: every file it names, by its diffs, its
        locations or its input's path, under `locked`. A request of any other kind is not a write; one that gives no
        kind, as a request may when its call has begun, is taken as one, code.dispatcher.agent#43."""
        if call.get('kind') is not None and str(call.get('kind')) not in WRITES:
            return None
        raw = call.get('rawInput')
        given = cast(dict[str, Any], raw) if isinstance(raw, dict) else {}
        paths = [*(str(one.get('path')) for one in cast(list[dict[str, Any]], call.get('content') or [])
                   if one.get('type') == 'diff' and one.get('path')),
                 *(str(one.get('path')) for one in cast(list[dict[str, Any]], call.get('locations') or [])
                   if one.get('path')),
                 *(str(given[key]) for key in ('file_path', 'notebook_path', 'path') if isinstance(given.get(key), str))]
        for path in dict.fromkeys(paths):
            why = await self.locked(relative(path, [self.folder, self.root]))
            if why is not None:
                return why
        return None

    async def unsandboxed(self, call: dict[str, Any]) -> str | None:
        """Why a request to widen the sandbox the agent's commands run in is refused, or None, code.dispatcher.agent#43:
        write access for a path of the project that `locked` holds, or for a folder that is or holds the project, which
        no ref names exactly; a pattern or scope that cannot be read as a path, if it opens writing; and, for an agent
        kept in its asking mode, a command run outside its sandbox altogether, which could write any file: a request
        whose own input names a command. Network access, an MCP tool's approval and paths outside the project are left
        to the answer as usual."""
        if not LINK_LOCK or not SHELL_SANDBOX or not self.ruled:  # off with the lock or its sandbox, and until the rule
            return None  # is sent, #47
        raw = call.get('rawInput')
        given = cast(dict[str, Any], raw) if isinstance(raw, dict) else {}
        grant = given.get('additionalPermissions') or given.get('permissions')
        if isinstance(grant, dict):
            files = cast(dict[str, Any], cast(dict[str, Any], grant).get('fileSystem') or {})
            paths = [str(one) for one in cast(list[Any], files.get('write') or [])]
            for entry in cast(list[dict[str, Any]], files.get('entries') or []):
                where = cast(dict[str, Any], entry.get('path') or {})
                if 'write' not in str(entry.get('access', '')):
                    continue
                if where.get('type') != 'path':
                    return prompt('command_unsandboxed') or 'Commands may not be given write access to the project.'
                paths.append(str(where.get('path')))
            root = Path(self.root).resolve()
            for path in paths:
                found = Path(path).resolve() if os.path.isabs(path) else root / path
                if found == root or root in found.parents and found.is_dir() or found in root.parents:
                    return prompt('command_unsandboxed') or 'Commands may not be given write access to the project.'
                why = await self.locked(relative(str(found), [self.folder, self.root]))
                if why is not None:
                    return why
            return None
        if self.asking is not None and str(call.get('kind')) == 'execute' and given.get('command') \
                and not given.get('url'):  # a command, not a network host or an MCP tool's approval
            return prompt('command_unsandboxed') or 'Commands run in a sandbox that cannot write the project.'
        return None

    async def told(self, text: str) -> None:
        """A refusal's reason given to the agent: into the turn in flight when it steers, otherwise as its next turn,
        since a permission answer carries no text."""
        steered = await self.steer(text) if self.turns and self.active_turn is not None and self.active_turn.sent \
            else False
        if steered is False:  # None: the agent may have taken it, so it is not sent again
            self.turn(text)

    async def read_text_file(self, session_id: str, path: str, line: int | None = None, limit: int | None = None,
                             **kwargs: Any) -> ReadTextFileResponse:
        """ACP's fs/read_text_file: the file's text from `line`, 1-based, at most `limit` lines."""
        found = await self.confined('read', path)
        try:
            text = await asyncio.to_thread(found.read_text, encoding='utf-8', errors='replace')
        except OSError as error:
            raise acp.RequestError.resource_not_found(path) if isinstance(error, FileNotFoundError) else \
                acp.RequestError.internal_error({'path': path, 'reason': str(error)}) from None
        if line is not None or limit is not None:
            lines = text.splitlines(keepends=True)
            start = max((line or 1) - 1, 0)
            text = ''.join(lines[start:start + limit] if limit is not None else lines[start:])
        await self.filed(found, 'read')
        return ReadTextFileResponse(content=text)

    async def write_text_file(self, session_id: str, path: str, content: str,
                              **kwargs: Any) -> WriteTextFileResponse | None:
        """ACP's fs/write_text_file: the file written whole, made with its folders when it does not exist; refused
        inside a part of the map another ticket's claim reserves, LAYER-029."""
        found = await self.confined('write', path)
        named = relative(str(found), [self.folder, self.root])
        why = await self.locked(named)
        if why is not None:
            raise await self.refuse('write', path, why)
        for place in placed(await self.places(), named)[0]:
            lock = await asyncio.to_thread(claimed, self.store, place.get('address'), self.work_id)
            if lock is not None:
                raise await self.refuse('write', path, f'{place.get("address")} is claimed by "{lock["name"]}"')

        def written() -> None:
            found.parent.mkdir(parents=True, exist_ok=True)
            found.write_text(content, encoding='utf-8')
        try:
            await asyncio.to_thread(written)
        except OSError as error:
            raise acp.RequestError.internal_error({'path': path, 'reason': str(error)}) from None
        await self.filed(found, 'edit')
        return WriteTextFileResponse()

    async def create_terminal(self, session_id: str, command: str, args: list[str] | None = None,
                              env: list[EnvVariable] | None = None, cwd: str | None = None,
                              output_byte_limit: int | None = None, **kwargs: Any) -> CreateTerminalResponse:
        """ACP's terminal/create: the command started at once in a process group of its own, in the session's folder
        or a folder inside it, with the agent's environment and the variables it names; its output, stdout and stderr
        together, kept up to its limit, or TERMINAL_KB when it names none."""
        folder = await self.confined('run a terminal in', cwd) if cwd else Path(self.folder)
        given = windowless({**child_environment(), **{one.name: one.value for one in env or []}})
        # Run with the project read-only, as the agents' own commands are, code.dispatcher.agent#43, CTX-062.
        denied = await self.denied()  # read for each command, so a file linked since the session began is writable
        run = [command, *(args or [])] if denied is None or not SHELL_SANDBOX \
            else confined_command(denied, command, args or [])
        if run is None:
            raise await self.refuse('run', command, prompt('terminal_unconfined')
                                    or 'no sandbox can keep the project read-only to it here')
        try:
            process = await asyncio.create_subprocess_exec(
                *run, cwd=str(folder), env=given, stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT, **group_options())
        except OSError as error:
            raise await self.refuse('run', command, str(error)) from None
        self.terminal_count += 1
        ident = f'term-{self.terminal_count}'
        limit = output_byte_limit if output_byte_limit is not None else 1024 * TERMINAL_KB
        held = Terminal(' '.join([command, *(args or [])]), str(folder), process, max(int(limit), 0), bytearray())
        self.terminals[ident] = held
        held.reader = asyncio.create_task(self.terminal_read(ident, held))
        self.tasks.add(held.reader)
        held.reader.add_done_callback(self.tasks.discard)
        await self.terminal_line(ident, held)
        return CreateTerminalResponse(terminal_id=ident)

    async def terminal_read(self, ident: str, held: Terminal) -> None:
        """A terminal's output read as it comes, its line in the thread kept at its latest every STREAM_EVERY, then
        its exit."""
        stream = held.process.stdout
        if stream is not None:
            while chunk := await stream.read(65536):
                held.output += chunk
                held.truncated = trimmed(held.output, held.limit) or held.truncated
                if time.monotonic() - held.shown >= STREAM_EVERY:
                    await self.terminal_line(ident, held)
        held.exit = exit_status(await held.process.wait())
        await self.terminal_line(ident, held)

    async def terminal_line(self, ident: str, held: Terminal) -> None:
        """A terminal's line in the thread: its command, folder, the last of its output and its exit."""
        held.shown = time.monotonic()
        said = {'terminal_id': ident, 'command': held.command, 'cwd': relative(held.cwd, [self.folder]) or '.',
                'output': held.output[-4096:].decode('utf-8', errors='replace'), 'truncated': held.truncated,
                'exit': held.exit.model_dump(mode='json', by_alias=True, exclude_none=True) if held.exit else None}
        async with self.lock:
            await self.note(f'terminal:{ident}', 'terminal', json.dumps(said, ensure_ascii=False))

    def terminal(self, ident: str) -> Terminal:
        held = self.terminals.get(ident)
        if held is None:
            raise acp.RequestError.invalid_params({'terminalId': ident, 'reason': 'no such terminal, or released'})
        return held

    async def terminal_output(self, session_id: str, terminal_id: str, **kwargs: Any) -> TerminalOutputResponse:
        """ACP's terminal/output: what it has written so far, whether some was dropped, and its exit once it has."""
        held = self.terminal(terminal_id)
        return TerminalOutputResponse(output=held.output.decode('utf-8', errors='replace'), truncated=held.truncated,
                                      exit_status=held.exit)

    async def wait_for_terminal_exit(self, session_id: str, terminal_id: str,
                                     **kwargs: Any) -> WaitForTerminalExitResponse:
        """ACP's terminal/wait_for_exit: answered once the command has ended."""
        held = self.terminal(terminal_id)
        if held.reader is not None:
            await asyncio.shield(held.reader)
        ended = held.exit or exit_status(await held.process.wait())
        return WaitForTerminalExitResponse(exit_code=ended.exit_code, signal=ended.signal)

    async def kill_terminal(self, session_id: str, terminal_id: str, **kwargs: Any) -> KillTerminalResponse | None:
        """ACP's terminal/kill: its process group ended; the terminal stays readable until it is released."""
        held = self.terminal(terminal_id)
        if held.process.returncode is None:
            await asyncio.to_thread(end_group, held.process.pid)
        return KillTerminalResponse()

    async def release_terminal(self, session_id: str, terminal_id: str,
                               **kwargs: Any) -> ReleaseTerminalResponse | None:
        """ACP's terminal/release: ended when it still runs, and forgotten; its line stays in the thread."""
        held = self.terminals.pop(terminal_id, None)
        if held is not None and held.process.returncode is None:
            await asyncio.to_thread(end_group, held.process.pid)
        return ReleaseTerminalResponse()

    async def terminals_ended(self) -> None:
        """Every terminal still running ends with the session."""
        for ident in list(self.terminals):
            with contextlib.suppress(Exception):
                await self.release_terminal(self.session_id or '', ident)

    # ------------------------------------------------------------------ session/fork, P030

    async def fork(self, text: str) -> dict[str, Any]:
        """ACP's session/fork, where the agent offers it: a session branching from this one with all its context,
        given the same Metaform server with the same identity, so what it was told stays told and its calls are this
        session's. It is kept as a child thread, as a subagent is, and `text`, when given, is its first turn."""
        caps = cast(dict[str, Any], self.acp['capabilities'])
        if not caps.get('fork'):
            return {'error': f'{self.name} does not offer session/fork.'}
        if self.ending or self.session_id is None or self.conn is None:
            return {'error': 'The session has not started or is ending.'}
        made = await asyncio.wait_for(self.conn.fork_session(session_id=self.session_id, cwd=self.folder,
                                                             mcp_servers=self.servers), START_LIMIT)
        child = str(made.session_id)
        self.children[child] = {'session_id': child, 'name': 'fork', 'task': text or None, 'state': 'running',
                                'started': stamp(), 'lines': 0, 'named': set(), 'flow': None, 'fork': True}
        await self.child_line(child)
        if text:
            self.spawn(self.fork_turn(child, text))
        identity = {one.name: one.value for server in self.servers for one in server.env
                    if one.name in ('METAFORM_ROLE', 'METAFORM_SESSION', 'METAFORM_WORK', 'METAFORM_NODE')}
        return {'fork': child, 'from': self.session_id, 'identity': identity}

    async def fork_turn(self, child: str, text: str) -> None:
        """One turn of a fork, its words in its own thread."""
        held = self.children.get(child)
        if held is None:
            return
        async with self.lock:
            await self.child_note(child, None, 'person', text)
        held['state'] = 'running'
        try:
            answer = await self.conn.prompt(session_id=child, prompt=[acp.text_block(text)])
            reason = str(answer.stop_reason)
        except Exception as error:  # noqa: BLE001  the fork's turn ends whatever ended it
            reason = f'error: {error}'
        held['state'] = 'idle'
        async with self.lock:
            await self.child_note(child, None, 'turn', f'The turn ended: {reason}.')
        await self.child_line(child)

    # ------------------------------------------------------------------ the intake's guards, M04

    def intake_clock(self) -> None:
        """Start the intake's first-record clock with its first turn: past dispatch_intake_first_record seconds with
        no Metaform call, it is steered once."""
        if self.intake is None or self.intake_began:
            return
        self.intake_began = time.monotonic()
        self.intake.update(phase='waiting for first record', began=stamp())
        self.acp['intake'] = dict(self.intake)
        seconds = float(self.option('dispatch_intake_first_record', 0) or 0)
        if seconds > 0:
            self.intake_timer = asyncio.get_running_loop().call_later(
                seconds, lambda: self.spawn(self.first_record_due(seconds)))

    async def first_record_due(self, seconds: float) -> None:
        """No Metaform call in time: the intake_first_record line, into the turn in flight when the agent offers
        steering, otherwise its next turn; once."""
        self.intake_timer = None
        if self.intake is None or self.ending or 'first_call_s' in self.intake or self.intake.get('steered'):
            return
        text = prompt('intake_first_record', seconds=str(int(seconds)))
        if not text:
            return
        self.intake['steered'] = stamp()
        self.acp['intake'] = dict(self.intake)
        steered = await self.steer(text) if self.turns and self.active_turn is not None and self.active_turn.sent \
            else False
        async with self.lock:
            await self.note(None, 'steered' if steered else 'notice',
                            f'No Metaform call in {int(seconds)} s: {"steered" if steered else "sent next"}: {text}')
            await self.save_state()
        if not steered:
            self.turn(text)

    async def intake_call(self, line: str, completed: bool, ident: str = '') -> None:
        """An intake agent's tool call, under the session's lock: its first Metaform call and its first record timed
        from its first turn, and a reach for earlier conclusions, a withheld tool or a report, review, log or notes
        file, signalled at the session."""
        if self.intake is None or self.probe:
            return
        kind = jev.call_kind(line)
        if self.effects is None:
            found = await asyncio.to_thread(surface, Path(self.root))
            self.effects = {(module.id, verb.name.replace('-', '_')): verb.effect for module in found
                            for verb in module.verbs}
            self.effects.update({(module, verb.replace('_', '-')): effect
                                 for (module, verb), effect in list(self.effects.items())})
        reached = withheld_named(line, self.withheld, self.effects)
        if reached or kind == 'conclusion':
            await self.raise_signal('intake-conclusions', key=ident or hashlib.sha256(line.encode()).hexdigest()[:16],
                                    tool=line[:200], withheld=reached or None,
                                    reason='a withheld tool' if reached else 'a file of earlier conclusions')
        if kind != 'metaform' or reached or not self.intake_began:  # a withheld tool is not served: no call made
            return
        took = round(time.monotonic() - self.intake_began, 1)
        changed = False
        if 'first_call_s' not in self.intake:
            self.intake['first_call_s'] = took
            changed = True
            if self.intake_timer is not None:
                self.intake_timer.cancel()
                self.intake_timer = None
        writes = [tool for tool in tools_named(line) if (self.effects or {}).get(tool, 'write') != 'read']
        if completed and writes and 'first_record_s' not in self.intake:
            self.intake.update(first_record_s=took, phase='recording')
            changed = True
        if changed:  # under the session's lock already, as every update is
            self.acp['intake'] = dict(self.intake)
            await self.save_state()
            await self.changed(tables='dispatch', kinds=['session'])

    # ------------------------------------------------------------------ Jev's drift check, H23

    async def drift(self) -> None:
        """Ask Jev, every DRIFT_EVERY tool calls of a worker, whether it reads conclusions in place of the source,
        strays from its ticket or repeats work, when jev is on and its session_drift decision is chosen; a sure yes
        raises the drift signal, which names what drifted. With Jev off, unsure or unreachable, nothing is raised and
        the spinning signals stand as before."""
        if self.drifting or self.node is None or self.system or self.prep or self.probe:
            return
        self.drifting = True
        try:
            record = await asyncio.to_thread(ticket, self.store, self.work_id)
            steps = [step.said for step in record.said if step.said]
            folder, calls, task = Path(self.root), list(self.calls), record.task or record.note or ''

            def asked() -> Any:
                with jev.within(jev.DEADLINE):
                    return jev.session_drift(folder, self.session_id or self.work_id, calls, task, steps=steps,
                                             address=self.at or None, project=self.store.project_id)
            decision = await asyncio.to_thread(asked)
            found = cast(dict[str, Any], decision.answer) if decision is not None else {}
            drifted = sorted(part for part, value in found.items() if value is True)
            await self.raise_signal('drift', key='jev', active=bool(drifted), drifted=drifted or None,
                                    reason=decision.reason[:400] if decision is not None and drifted else None)
        except Exception as error:  # noqa: BLE001  a decision that fails changes nothing
            sys.stderr.write(f'Could not ask Jev about drift: {error}\n')
        finally:
            self.drifting = False

    async def permission(self, request: str, **changes: Any) -> None:
        """A permission request's line, kept at its latest: waiting, answered, unmatched or cancelled."""
        held = self.permissions.get(request)
        if held is None:
            return
        held.update(changes)
        await self.note(f'permission:{request}', 'permission', json.dumps(held, ensure_ascii=False))

    async def permit(self, request: str, option: str) -> dict[str, Any]:
        """The person's choice for a waiting permission request, given on the page: it answers the agent at once, and
        its question at the node, when there is one, is closed with the option's name, as an answer there would be. A
        question the agent asked through elicitation is answered the same way, with the person's words as its answer."""
        if request in self.elicited:
            async with self.lock:
                message_id = self.elicitations.get(f'elicitation:{request}', {}).get('message_id')
                answered = await self.elicit_answered(request, option)
                if message_id and 'error' not in answered:
                    await self.write(self.store.reply, message_id, option)
            return answered
        held = self.asked.get(request)
        if held is None:
            return {'error': f'No permission request {request} waits on this session.'}
        waiting, options, title = held
        chosen = choose(options, option)
        if chosen is None:
            return {'error': f'{option} is none of the options: '
                             f'{", ".join(f"{one.name} ({one.option_id})" for one in options)}.'}
        name = next(one.name for one in options if one.option_id == chosen)
        async with self.lock:
            if self.asked.get(request) is not held:  # answered at the node meanwhile
                return {'error': f'Permission request {request} was answered already.'}
            del self.asked[request]
            message_id = self.permissions.get(request, {}).get('message_id')
            if message_id:
                await self.write(self.store.reply, message_id, name)
            await self.raise_signal('permission-waiting', key=request, active=False, message_id=message_id,
                                    request=request, tool=title)
            self.progress_at = time.monotonic()  # waiting for a person is not agent spinning
            await self.permission(request, state='answered', chosen=chosen, answer=name)
        if not waiting.done():
            waiting.set_result(chosen)
        self.arm()
        return {'request': request, 'chosen': chosen, 'answer': name}

    # ------------------------------------------------------------------ permission requests

    async def answering(self) -> tuple[str, str]:
        """How this session's permission requests are answered now, and whose choice that is: the person's for this
        session, `session`; the launch's own prompts, `launch`, for the agent a start launched; else dispatch_prompts,
        `project`, read as set now, so a change there reaches this agent."""
        own = self.acp.get('prompts')
        if own in PROMPTS:
            return str(own), 'session'
        launched = (await asyncio.to_thread(launch_options, self.store, self.work_id)).get('prompts') \
            if self.launched else None
        if launched:
            return launched, 'launch'
        return str(await asyncio.to_thread(self.ctx.setting, 'dispatch_prompts')), 'project'

    @staticmethod
    def answered_by(how: str, source: str) -> str:
        return {'session': f'this session\'s prompts={how}, chosen by the person',
                'launch': f'this launch\'s prompts={how}'}.get(source, f'dispatch_prompts={how}')

    async def set_prompts(self, how: str) -> dict[str, Any]:
        """The person's choice of how this session's permission requests are answered from now on, one of
        dispatch_prompts' choices: kept in its state line, so it holds when the session is resumed, and applied at once
        to each request waiting now that it approves."""
        if how not in PROMPTS:
            return {'error': f'prompts is one of {", ".join(PROMPTS)}, not {how}.'}
        async with self.lock:
            self.acp['prompts'] = how
            await self.flush()
            await self.note(None, 'setting', f'Permission requests in this session: {how}, chosen by the person.')
            await self.save_state()
        approved: list[str] = []
        said = self.answered_by(how, 'session')
        for request, (_, options, title) in list(self.asked.items()):
            allow = allowed(options, how, self.permissions.get(request, {}).get('kind'))
            if allow is None or 'error' in await self.permit(request, allow.option_id):
                continue
            approved.append(request)
            async with self.lock:
                await self.flush()
                await self.note(None, 'approved', f'{title}: approved by {said}')
        await self.changed(tables='dispatch', dispatch_tables=['dispatch.session_lines', 'dispatch.permissions'])
        return {'prompts': how, 'from': 'session', 'approved': approved}

    async def request_permission(self, session_id: str, tool_call: ToolCallUpdate, options: list[PermissionOption],
                                 **kwargs: Any) -> RequestPermissionResponse:
        """Asked at the ticket's node with the options as suggestions, and on the page as a choice among them; the
        agent waits for the person's choice. One the agent withdraws with `$/cancel_request` is answered with ACP's
        request-cancelled error."""
        rpc = INCOMING.get()
        waiting: asyncio.Future[str | None] = asyncio.get_running_loop().create_future()
        title = str(tool_call.title or tool_call.kind or 'a tool call')
        # A change to a locked file, or a widening of the sandbox the agent's commands run in, is refused before any
        # answer the prompts choice or the agent's mode would give, code.dispatcher.agent#3d and #43; the agent's
        # reject-once option where it offers one, never one it would remember. A request names only what the call it
        # belongs to did not already say, codex-acp's file changes, so the call as it began is read with it.
        asked = tool_call.model_dump(mode='json', by_alias=True, exclude_none=True)
        began = self.tools.get(str(asked.get('toolCallId')), {})
        call = {**{key: began[key] for key in ('kind', 'rawInput') if key in began}, **asked,
                **{key: [*cast(list[Any], asked.get(key) or []), *cast(list[Any], began.get(key) or [])]
                   for key in ('content', 'locations')}}
        why = await self.edit_locked(call) or await self.unsandboxed({**call, 'rawInput': asked.get('rawInput')})
        if why is not None:
            async with self.lock:
                await self.flush()
                await self.note(None, 'notice', f'{title}: refused, {why}')
            self.spawn(self.told(why))
            reject = next((option for option in options if str(option.kind) == 'reject_once'), None)
            return RequestPermissionResponse(outcome=AllowedOutcome(option_id=reject.option_id, outcome='selected')
                                             if reject is not None else DeniedOutcome(outcome='cancelled'))
        how, source = await self.answering()
        said = self.answered_by(how, source)
        allow = allowed(options, how, call.get('kind'))
        approving = 'mcp' if kwargs.get('is_mcp_tool_approval') else str(call.get('kind'))  # codex-acp's mark
        if allow is None and self.asking is not None and approving in MODE_APPROVES.get(
                str(self.chosen_mode), ()):  # what the agent would have done unasked in the mode the person chose
            allow = next((option for option in options if str(option.kind) == 'allow_once'), None)
            said = f'the mode {self.chosen_mode}'
        if allow is not None:
            async with self.lock:
                await self.flush()
                await self.note(None, 'approved', f'{title}: approved by {said}')
            return RequestPermissionResponse(outcome=AllowedOutcome(option_id=allow.option_id, outcome='selected'))
        detail = await self.tool_detail({**call, 'title': title})  # what it would act on, shown before it does
        async with self.lock:
            await self.flush()
            await self.bind(rpc, 'permit', await self.ask(waiting, options, title, '', call, detail))
        chosen = await waiting
        self.incoming.pop(rpc, None)
        self.spawn(self.changed(tables='dispatch', kinds=['session']))  # beside the answer, never before it
        if rpc is not None and rpc in self.withdrawn:
            self.withdrawn.discard(rpc)
            raise acp.RequestError(REQUEST_CANCELLED, 'Request cancelled')
        if chosen is None:
            return RequestPermissionResponse(outcome=DeniedOutcome(outcome='cancelled'))
        return RequestPermissionResponse(outcome=AllowedOutcome(option_id=chosen, outcome='selected'))

    async def ask(self, waiting: asyncio.Future[str | None], options: list[PermissionOption], title: str,
                  before: str, call: dict[str, Any] | None = None, detail: dict[str, Any] | None = None) -> str | None:
        """Ask the person a permission request, and return its request; None when the turn or session is ending and
        it is answered cancelled at once."""
        if self.ending or (self.active_turn is not None and self.active_turn.cancel_requested):
            if not waiting.done():
                waiting.set_result(None)
            return None
        message_id: str | None = None
        if self.node is not None:
            text = f'{before}{self.name} asks permission on work {self.work_id}: {title}'
            asked = await self.write(self.store.ask, self.node, text, suggestions=[option.name for option in options],
                                     by=self.by, work=self.work_id)
            request = message_id = asked.id
        else:
            request = uuid.uuid4().hex
        self.asked[request] = (waiting, options, title)
        self.hush()  # waiting on the person is not the agent's silence, P040
        self.permissions[request] = {
            'request': request, 'message_id': message_id, 'tool_call_id': (call or {}).get('toolCallId'),
            'title': title, 'kind': (call or {}).get('kind'),
            'options': [{'option_id': option.option_id, 'name': option.name, 'kind': str(option.kind)}
                        for option in options],
            'detail': detail, 'state': 'waiting', 'chosen': None, 'answer': None, 'asked': stamp(),
            'said': before.strip() or None}
        await self.permission(request)
        await self.raise_signal('permission-waiting', key=request, message_id=message_id, request=request, tool=title)
        await self.changed(tables='dispatch', dispatch_tables=['dispatch.session_lines', 'dispatch.permissions'])
        return request

    async def check(self) -> None:
        """On a change to this session's own ticket or session, `changed_elsewhere`: resolve permission requests the
        person answered, and end the session once its ticket is done while no prompt of its own runs, whatever turn
        closed it, VIEW-035. The answers come first, since the agent waits on them; the ticket is read once, after."""
        if self.waiting and self.node is not None and not self.ending:  # with no node, nothing is asked as a question
            async with self.lock:
                await self.answered()
        record = None
        if not self.ending and not self.prep:
            record = await asyncio.to_thread(ticket, self.store, self.work_id)
            if record.done and not self.ending and self.turns == 0:
                self.spawn(self.ticket_done())
                return
        async with self.lock:
            await self.progress(record)

    def checks(self) -> None:
        """Check for a change of its own: at once, or, while a check runs, once more after it, so a burst of changes
        costs one pass more and never one each."""
        if self.checking:
            self.check_again = True
            return
        self.checking = True
        self.spawn(self.checked_all())

    async def checked_all(self) -> None:
        try:
            while True:
                self.check_again = False
                await self.check()
                if not self.check_again or self.ending:
                    return
        finally:
            self.checking = False

    async def answered(self) -> None:
        """The questions at its node the person answered: the agent's own, and its permission requests, each answer
        handed to the agent before it is recorded."""
        if self.node is not None:
            found = await asyncio.to_thread(self.store.messages, self.node, 'question', None, limit=0)
            for message in found.results:
                if message.id in self.elicited and message.closed is not None:  # the agent's own question, answered
                    await self.elicit_answered(message.id, message.answer or '', reask=True)
                    continue
                held = self.asked.get(message.id)
                if held is None or message.closed is None:
                    continue
                del self.asked[message.id]
                waiting, options, title = held
                chosen = choose(options, message.answer)
                if chosen is not None and not waiting.done():
                    waiting.set_result(chosen)  # to the agent first; its thread line is written under this lock
                await self.raise_signal('permission-waiting', key=message.id, active=False,
                                        message_id=message.id, request=message.id, tool=held[2])
                self.progress_at = time.monotonic()  # waiting for a person is not agent spinning
                self.answers[message.id] = (message.closed, message.answer)
                if chosen is not None:
                    await self.permission(message.id, state='answered', chosen=chosen, answer=message.answer)
                    self.arm()
                    continue
                await self.permission(message.id, state='unmatched', answer=message.answer)
                asked = self.permissions.get(message.id, {})
                call = {'toolCallId': asked.get('tool_call_id'), 'kind': asked.get('kind')}
                again = await self.ask(waiting, options, title,
                                       f'The answer "{message.answer}" names none of the options. ', call,
                                       asked.get('detail'))
                if again is not None:
                    self.rebound('permit', message.id, again)

    # ------------------------------------------------------------------ the agent's questions, ACP elicitation

    async def create_elicitation(self, message: str, mode: Any, **kwargs: Any) -> Any:
        """A question the agent puts to the person, ACP's elicitation/create: a form, such as Claude Code's
        AskUserQuestion or an MCP server's form, or a URL to open, such as an MCP server's OAuth sign-in. Asked at the
        ticket's node with its choices as suggestions, and on the page, as a permission request is; dispatch_prompts
        never answers one, since it is a question and not a permission. With dispatch_elicitation decline, it is
        declined at once and the agent goes on without the answer. The agent waits for the answer: accept with the
        content its schema asks for, decline, or cancel when the turn or the session ends first; a question the agent
        withdraws with `$/cancel_request` is answered with ACP's request-cancelled error. A URL is never opened or
        fetched by Metaform: the person opens it, and answering accept is their consent. The question keeps its
        scope, the session that asked (a subagent's, P016) and the tool call it belongs to, and a deadline the agent
        gives in its `_meta` (codex-acp's autoResolutionMs) is shown to the person."""
        rpc = INCOMING.get()
        given_url = getattr(mode, 'url', None)  # the SDK gives it as pydantic's AnyUrl
        url = str(given_url) if given_url is not None else None
        schema = getattr(mode, 'requested_schema', None)
        fields = [] if url is not None or schema is None else \
            elicit_fields(schema.model_dump(mode='json', by_alias=True, exclude_none=True))
        scope = {'session_id': getattr(mode, 'session_id', None), 'tool_call_id': getattr(mode, 'tool_call_id', None)}
        deadline = next((float(mark['autoResolutionMs']) / 1000 for mark in meta_records(kwargs)
                         if isinstance(mark.get('autoResolutionMs'), (int, float))), None)
        if not self.system:  # only the sentinel and the head agent ask the person, VIEW-045
            self.incoming.pop(rpc, None)
            return decided(fields)
        how = await asyncio.to_thread(self.ctx.setting, 'dispatch_elicitation')
        stopping = self.ending or (self.active_turn is not None and self.active_turn.cancel_requested)
        if how == 'decline' or stopping or rpc in self.withdrawn:
            self.incoming.pop(rpc, None)
            async with self.lock:
                await self.flush()
                await self.note(None, 'elicitation', json.dumps(
                    {'message': message, 'url': url, 'state': 'cancelled' if stopping else 'declined',
                     'by': None if stopping else 'dispatch_elicitation=decline', **scope}, ensure_ascii=False))
            return CancelElicitationResponse(action='cancel') if stopping or rpc in self.withdrawn else \
                DeclineElicitationResponse(action='decline')
        waiting: asyncio.Future[tuple[str, dict[str, Any]]] = asyncio.get_running_loop().create_future()
        async with self.lock:
            await self.flush()
            elicitation_id = cast(str | None, getattr(mode, 'elicitation_id', None))
            request = await self.elicit(waiting, message, fields, url, elicitation_id, scope=scope, deadline=deadline)
            await self.bind(rpc, 'elicit', request)
            if elicitation_id is not None and elicitation_id in self.completed_early:
                # its page was done with before the question was asked, as a sign-in that finishes at once
                self.completed_early.discard(elicitation_id)
                await self.elicit_closed(request, 'completed', ('accept', {}))
        action, content = await waiting
        self.incoming.pop(rpc, None)
        await self.changed(tables='dispatch', kinds=['session'])
        if action == 'withdrawn':
            self.withdrawn.discard(rpc)
            raise acp.RequestError(REQUEST_CANCELLED, 'Request cancelled')
        if action == 'accept':
            return AcceptElicitationResponse(action='accept', content=content if url is None else None)
        return DeclineElicitationResponse(action='decline') if action == 'decline' else \
            CancelElicitationResponse(action='cancel')

    async def complete_elicitation(self, elicitation_id: str, **kwargs: Any) -> None:
        """ACP's elicitation/complete: the agent says the page it asked the person to open is done with, as when an
        MCP server's sign-in finished in the browser before the person answered. A question still waiting is closed
        as completed and the agent gets accept; its line says completed either way. One done already is ignored, as
        the RFD says; one not asked yet is remembered, since the question can still be on its way, its settings read
        while the page it names is done with, and is closed as it is asked. A few are remembered at most."""
        for name in [name for name in self.named if name.startswith('elicitation:')]:
            held = self.elicitations.get(name)
            if held is None or held.get('elicitation_id') != elicitation_id or held.get('state') == 'completed':
                continue
            async with self.lock:
                if str(held['request']) in self.elicited:
                    await self.elicit_closed(str(held['request']), 'completed', ('accept', {}))
                else:
                    held['state'] = 'completed'
                    await self.note(name, 'elicitation', json.dumps(held, ensure_ascii=False))
            await self.changed(tables='dispatch', dispatch_tables=['dispatch.session_lines'])
            return
        if len(self.completed_early) >= 32:
            self.completed_early.pop()
        self.completed_early.add(elicitation_id)

    async def bind(self, rpc: Any, kind: str, request: str | None) -> None:
        """Note which question or permission request an agent's request is asked as, the caller holding the lock, so
        its `$/cancel_request` can withdraw it; withdrawn at once when it was cancelled before it was asked."""
        if rpc is None or request is None:
            return
        if rpc in self.withdrawn:
            await self.withdrawn_now(kind, request)
        else:
            self.incoming[rpc] = (kind, request)

    def rebound(self, kind: str, old: str, new: str) -> None:
        """A question asked again under a new request: the agent's request it answers now names the new one."""
        for rpc, found in list(self.incoming.items()):
            if found == (kind, old):
                self.incoming[rpc] = (kind, new)

    async def withdraw(self, rpc: Any) -> None:
        """The agent's `$/cancel_request` for one of its requests that waits on the person, ACP's request
        cancellation: the question or permission request is withdrawn, its question at the node closed, its signal
        cleared, and the silence clock goes on."""
        async with self.lock:
            found = self.incoming.pop(rpc, None)
            if found is None or await self.withdrawn_now(*found):  # one answered already gets its answer, as the RFD says
                self.withdrawn.add(rpc)
        await self.changed(tables='dispatch', dispatch_tables=['dispatch.session_lines', 'dispatch.permissions'])

    async def withdrawn_now(self, kind: str, request: str) -> bool:
        """Withdraw one waiting question or permission request, the caller holding the lock; False when it no longer
        waits."""
        if kind == 'elicit':
            return await self.elicit_closed(request, 'withdrawn', ('withdrawn', {}))
        held = self.asked.pop(request, None)
        if held is None:
            return False
        waiting, _, title = held
        message_id = self.permissions.get(request, {}).get('message_id')
        if message_id:
            with contextlib.suppress(Exception):
                await self.write(self.store.reply, message_id, 'withdrawn by the agent')
        await self.raise_signal('permission-waiting', key=request, active=False, message_id=message_id,
                                request=request, tool=title)
        await self.permission(request, state='withdrawn')
        if not waiting.done():
            waiting.set_result(None)
        self.progress_at = time.monotonic()
        self.arm()
        return True

    async def elicit_closed(self, request: str, state: str, result: tuple[str, dict[str, Any]]) -> bool:
        """Close a waiting question that was not answered, the caller holding the lock: withdrawn by the agent, or
        completed out of band. Its question at the node is closed saying so, its signal cleared, its line set to the
        state, and the agent's request gets `result`. False when it no longer waits."""
        held = self.elicited.pop(request, None)
        if held is None:
            return False
        line = self.elicitations.get(f'elicitation:{request}', {})
        if line.get('message_id'):
            with contextlib.suppress(Exception):
                await self.write(self.store.reply, line['message_id'],
                                 'withdrawn by the agent' if state == 'withdrawn' else 'completed in the browser')
        await self.raise_signal('question-waiting', key=request, active=False, message_id=line.get('message_id'),
                                request=request, question=held['message'])
        line.update(state=state)
        await self.note(f'elicitation:{request}', 'elicitation', json.dumps(line, ensure_ascii=False))
        future = cast(asyncio.Future[tuple[str, dict[str, Any]]], held['future'])
        if not future.done():
            future.set_result(result)
        self.progress_at = time.monotonic()
        self.arm()
        return True

    async def elicit(self, waiting: asyncio.Future[tuple[str, dict[str, Any]]], message: str,
                     fields: list[dict[str, Any]], url: str | None, elicitation_id: str | None,
                     before: str = '', *, scope: dict[str, Any] | None = None, deadline: float | None = None) -> str:
        """Put the agent's question to the person, and return its request: at the ticket's node when it has one, with
        a one-question form's choices as suggestions, unless a field is secret, which is never written where agents
        read; on the page always, as a line of the thread and the question-waiting signal. A subagent's question
        says so, and its own thread notes it was asked."""
        scope = scope or {}
        text = before + elicit_question(self.name, message, fields, url, deadline)
        suggestions = elicit_suggestions(fields, url)
        secret = any(field['secret'] for field in fields)
        message_id: str | None = None
        if self.node is not None and not secret:
            asked = await self.write(self.store.ask, self.node, text, suggestions=suggestions, by=self.by,
                                     work=self.work_id)
            request = message_id = asked.id
        else:
            request = uuid.uuid4().hex
        self.elicited[request] = {'future': waiting, 'fields': fields, 'url': url, 'message': message,
                                  'elicitation_id': elicitation_id, 'scope': scope, 'deadline': deadline}
        self.hush()  # waiting on the person is not the agent's silence, P040
        from urllib.parse import urlsplit
        child = self.children.get(str(scope.get('session_id') or ''))
        line = {'request': request, 'message_id': message_id, 'message': message, 'url': url,
                'host': urlsplit(url).hostname if url else None, 'elicitation_id': elicitation_id,
                'fields': [{key: field[key] for key in ('key', 'title', 'description', 'type', 'choices', 'many',
                                                        'required', 'default', 'note_of', 'secret')}
                           for field in fields],
                'suggestions': suggestions, 'state': 'waiting', 'asked': stamp(), 'said': before.strip() or None,
                'session_id': scope.get('session_id'), 'tool_call_id': scope.get('tool_call_id'),
                'subagent': child['name'] if child else None, 'secret': secret,
                'deadline': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(time.time() + deadline))
                if deadline else None}
        self.elicitations[f'elicitation:{request}'] = line
        await self.note(f'elicitation:{request}', 'elicitation', json.dumps(line, ensure_ascii=False))
        if child is not None and not before:
            await self.child_note(str(scope['session_id']), None, 'notice', f'Asked the person: {message}')
        await self.raise_signal('question-waiting', key=request, message_id=message_id, request=request,
                                question=message, url=url, tool_call_id=scope.get('tool_call_id'))
        await self.changed(tables='dispatch', dispatch_tables=['dispatch.session_lines'])
        return request

    async def elicit_answered(self, request: str, answer: str | None, *, reask: bool = False) -> dict[str, Any]:
        """The person's answer to the agent's waiting question, the caller holding the lock: the agent gets it as
        accept with its content, decline or cancel; None is cancel. An answer that cannot be read is asked again at
        the node when `reask`, or else refused with what is wrong. A secret question's answer is never kept."""
        held = self.elicited.get(request)
        if held is None:
            return {'error': f'No question {request} waits on this session.'}
        action: str | None
        content: dict[str, Any] = {}
        problem = ''
        if answer is None:
            action = 'cancel'
        elif held['url'] is not None:
            word = answer.strip().casefold()
            action = 'accept' if word in ('accept', 'yes', 'ok', 'open', 'opened', 'done') else \
                'decline' if word in ('decline', 'no') else 'cancel' if word == 'cancel' else None
            problem = 'answer accept, decline or cancel'
        else:
            try:
                action, content = elicit_answer(cast(list[dict[str, Any]], held['fields']), answer)
            except ValueError as error:
                action, problem = None, str(error)
        del self.elicited[request]
        line = self.elicitations.get(f'elicitation:{request}', {})
        kept = None if line.get('secret') else answer
        await self.raise_signal('question-waiting', key=request, active=False, message_id=line.get('message_id'),
                                request=request, question=held['message'])
        self.progress_at = time.monotonic()  # waiting for a person is not agent spinning
        if action is None:
            line.update(state='unreadable', answer=kept, problem=problem)
            await self.note(f'elicitation:{request}', 'elicitation', json.dumps(line, ensure_ascii=False))
            if reask and self.node is not None and not line.get('secret'):
                again = await self.elicit(held['future'], held['message'], held['fields'], held['url'],
                                          held['elicitation_id'], f'The answer "{answer}" could not be read: {problem}. ',
                                          scope=held['scope'], deadline=held['deadline'])
                self.rebound('elicit', request, again)
                return {'error': problem}
            self.elicited[request] = held  # still waiting, for an answer it can read
            line.update(state='waiting')
            await self.note(f'elicitation:{request}', 'elicitation', json.dumps(line, ensure_ascii=False))
            await self.raise_signal('question-waiting', key=request, message_id=line.get('message_id'),
                                    request=request, question=held['message'])
            return {'error': f'The answer could not be read: {problem}.'}
        line.update(state='answered' if action == 'accept' else action + 'led' if action == 'cancel' else 'declined',
                    answer=kept if action == 'accept' else None, problem=None)
        await self.note(f'elicitation:{request}', 'elicitation', json.dumps(line, ensure_ascii=False))
        future = cast(asyncio.Future[tuple[str, dict[str, Any]]], held['future'])
        if not future.done():
            future.set_result((action, content))
        self.arm()
        return {'request': request, 'action': action}

    async def elicitations_cancelled(self) -> None:
        """Every question still waiting answered as cancelled, its question at the node closed: the turn or the session
        is ending, the caller holding the lock."""
        for request in list(self.elicited):
            message_id = self.elicitations.get(f'elicitation:{request}', {}).get('message_id')
            if message_id:
                with contextlib.suppress(Exception):
                    await self.write(self.store.reply, message_id)
            with contextlib.suppress(Exception):
                await self.elicit_answered(request, None)

    async def waits_moved(self, session_id: str) -> None:
        """The session is made, `session_id`: every question or permission request the agent put while it was being
        made, its signal raised under no session and its line kept from a thread that did not exist yet, is moved to
        it, the caller holding the lock so none is answered meanwhile. Its signal is cleared where it was raised and
        raised again under the session, so it is read and cleared against the session the person sees, and its line
        is written, as stderr gathered before the session is."""
        for request, (_, _, title) in self.asked.items():
            await self.raise_signal('permission-waiting', key=request, active=False,
                                    message_id=self.permissions.get(request, {}).get('message_id'), request=request,
                                    tool=title)
        for request, held in self.elicited.items():
            await self.raise_signal('question-waiting', key=request, active=False,
                                    message_id=self.elicitations.get(f'elicitation:{request}', {}).get('message_id'),
                                    request=request, question=held['message'])
        self.session_id = session_id
        for request, (_, _, title) in self.asked.items():
            await self.permission(request)
            await self.raise_signal('permission-waiting', key=request,
                                    message_id=self.permissions.get(request, {}).get('message_id'), request=request,
                                    tool=title)
        for request, held in self.elicited.items():
            line = self.elicitations.get(f'elicitation:{request}', {})
            await self.note(f'elicitation:{request}', 'elicitation', json.dumps(line, ensure_ascii=False))
            await self.raise_signal('question-waiting', key=request, message_id=line.get('message_id'),
                                    request=request, question=held['message'], url=held['url'],
                                    tool_call_id=cast(dict[str, Any], held['scope']).get('tool_call_id'))

    # ------------------------------------------------------------------ the session

    async def run(self) -> dict[str, Any]:
        self.sent = prompt_files.collect()  # every prompt this runner serves from here on, its tasks' and threads' too
        server = await asyncio.start_server(self.control, '127.0.0.1', 0)
        self.port = int(server.sockets[0].getsockname()[1])
        loop = asyncio.get_running_loop()
        listener = self.ctx.listen(lambda payload: loop.call_soon_threadsafe(self.changed_elsewhere, payload))
        with contextlib.suppress(NotImplementedError):  # Windows ends a process with no signal it can handle
            loop.add_signal_handler(signal.SIGTERM, lambda: self.spawn(self.end(TERMINATED)))
        try:
            async with self.starting:
                await self.begin()
            await self.ended.wait()
            if self.failure is not None:
                raise self.failure
        except Exception as error:  # noqa: BLE001  the agent did not start; the map says why
            said = 'did not start' if self.session_id is None else 'failed'
            sys.stderr.write(f'{self.name} {said} on work {self.work_id}: {error}\n')
            last = self.tail()
            self.how = f'it {said}: {error}' + (f'; its last stderr: {last}' if last else '')
            text = f'{self.name} {said} on work {self.work_id}: {error}' + (
                '\nIts last stderr:\n' + '\n'.join(self.stderr_tail) if last else '')
            try:
                if self.session_id is None and not self.probe:
                    await self.unstarted(text)
                else:
                    await self.note(None, 'failed', text)
            except Exception as note_error:  # noqa: BLE001  a failure note cannot prevent resource cleanup
                sys.stderr.write(f'Could not record the session failure: {note_error}\n')
        finally:
            with contextlib.suppress(NotImplementedError):
                loop.remove_signal_handler(signal.SIGTERM)
            try:
                await asyncio.shield(self.end(self.how or 'the runner ended'))
            finally:
                pending = tuple(self.tasks)
                for task in pending:
                    task.cancel()
                await asyncio.gather(*pending, return_exceptions=True)
                try:
                    await asyncio.to_thread(listener.close)
                finally:
                    prompt_files.release(self.sent)
                    server.close()
                    await server.wait_closed()
        return {'work_id': self.work_id, 'agent': self.agent, 'session_id': self.session_id, 'ended': self.how}

    async def begin(self) -> None:
        if self.ending:
            return
        if self.node is None and self.ctx.nouns.get('intake') and not self.resume:
            self.request = await asyncio.to_thread(self.asked_for)
        if self.resume:  # the thread goes on where it ended: its lines keep their names and their order
            await asyncio.to_thread(self.continue_thread)
        # The server the agent is asked to start is the one AI tools are registered with, chosen at the project's root
        # and not in a worktree, run by this interpreter; none is asked for when no module provides one, MCP-010.
        server = await asyncio.to_thread(mcp_server, Path(self.root))
        self.runner = secrets.token_hex(8)
        identity = {'METAFORM_ROLE': self.role, 'METAFORM_SESSION': self.runner, 'METAFORM_WORK': self.work_id,
                    **({'METAFORM_NODE': self.at} if self.at else {})}
        await self.open_agent(identity)
        if self.ending or self.process is None:
            return
        self.spawn(self.watch(self.process))
        # The runner's server is named `metaform`, the name the person's AI tools register it under, so it is used in
        # place of a server of that name the agent's own config holds rather than beside it: one set of Metaform
        # tools, each call carrying this session's identity. Its environment names the METAFORM_* variables, the home
        # and the identity, since codex-acp gives an MCP server only a short list of its own variables, ticket 80cafcd9.
        # An intake agent's server leaves out the tools that read earlier conclusions, M04 and P019: named in its
        # environment beside its identity, so only this session's server withholds them.
        if self.intake is not None:
            self.withheld = [str(one) for one in cast(list[Any], self.option('dispatch_intake_withheld', []) or [])]
        withheld = {WITHHELD: ','.join(self.withheld)} if self.withheld else {}
        servers = [McpServerStdio(name='metaform', command=sys.executable, args=['-m', *server],
                                  env=server_environment(**identity, **withheld))] if server else []
        self.servers = servers
        try:
            if self.resume:
                made = await asyncio.wait_for(self.reopen(servers), START_LIMIT)
            else:
                made = await asyncio.wait_for(self.conn.new_session(cwd=self.folder, mcp_servers=servers,
                                                                    **held_settings(await self.denied())),
                                              START_LIMIT)
                async with self.lock:  # what the agent asked while the session was made moves to it
                    await self.waits_moved(str(made.session_id))
        except acp.RequestError as error:
            if error.code == AUTH_REQUIRED:  # the agent needs a login first: the person's, never Metaform's, P031
                await self.raise_signal('login-needed', key=self.agent, agent=self.agent,
                                        methods=[one.get('id') for one in self.acp['auth_methods']],
                                        next=f'metaform dispatch login {self.agent}')
                raise RuntimeError(f'{self.name} needs a login before it makes a session: metaform dispatch login '
                                   f'{self.agent}') from None
            raise
        self.apply(made)
        if self.ending:
            return
        await self.remember()
        await self.stderr_flush()  # what the agent wrote before its session was made, now that its thread exists
        if self.left_out:
            await self.note(None, 'notice', f'Initialize left out {self.left_out}.')
        from .recovery import resources
        # Evidence acquired before taking the ticket, kept privately in the session's own row with it.
        self.recovery = await asyncio.to_thread(resources, self.store.project_id, self.work_id,
                                                cast(str, self.session_id), self.process.pid)
        if self.ending:
            return
        row = {key: value for key, value in self.extra('running').items() if key != 'dispatch'}
        pinned = await asyncio.to_thread(self.store.bound_base)  # the metaform this runner stays on, `dispatch`
        row.update(started=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), seq=time.time_ns() // 1_000_000,
                   origin=origin(), base=pinned.id if pinned is not None else None)
        def take() -> None:
            # A worker takes its ticket and records its session together. A conversation takes nothing of the map,
            # so it writes no metaform, and one held on no map makes none, PROJ-026.
            with self.store.atomic() if not self.prep else contextlib.nullcontext():
                if not self.prep:
                    record = ticket(self.store, self.work_id)
                    if self.resume:  # a worker resumed in place goes on only with the ticket still its own
                        if record.done or record.taken_by != self.by:
                            raise Stop(f'Work {self.work_id} is no longer taken by session {self.session_id}, so it '
                                       'cannot be resumed as its worker.',
                                       f'metaform dispatch talk session={self.work_id}:{self.session_id}')
                    else:
                        if self.took:
                            if record.taken_by != self.ctx.nouns['reservation']:
                                raise Stop('The startup reservation is no longer held.', 'metaform map work open=true')
                            self.store.move_work(self.work_id, 'todo', record.position)
                        self.store.take_work(self.work_id, None, self.by)
                with self.store.tables() as tx:
                    if self.resume:  # the ended session's own row runs again
                        # Two resumes at once, a second click on Resume, would run one ACP session twice: the first
                        # to get here holds it, and a row another live runner of this work holds is not taken over.
                        held = tx.rows('agent_sessions', {'session_id': self.session_id}, limit=1).results
                        other = held[0]['pid'] if held and held[0]['state'] == 'running' else None
                        if other not in (None, os.getpid()) and runner_of(other) == self.work_id:
                            raise Stop(f'Session {self.session_id} has been resumed already.',
                                       f'metaform dispatch sessions id={self.work_id}')
                        # a conversation goes on where it hangs now, the map it began on cleared or restored since
                        kept = ('state', 'recovery', 'pid', 'port', 'token', 'how', 'runner', 'origin', 'base',
                                *(('work_id',) if self.system else ()))
                        tx.update('agent_sessions', {'session_id': self.session_id}, {key: row[key] for key in kept})
                        with contextlib.suppress(OSError):  # its row holds it now, not the file its start left
                            resuming_path(str(self.session_id)).unlink()
                    else:
                        tx.insert('agent_sessions', row)
                if not self.prep:
                    from .progress import begin
                    begin(self.store, ticket(self.store, self.work_id), str(self.session_id), str(self.runner))
            # Acquisition is complete before write publishes its change. A failed announcement still needs release.
            self.took = not self.prep
            self.recorded = True
        await self.write(take)
        # every runner stays in the metaform it began in, whichever becomes active later, `dispatch`; one started by
        # an older starter, with none named, is bound here to the one it took its ticket in
        bound = await asyncio.to_thread(self.store.bound_base)
        if bound is not None:
            self.store = Store(self.store.project_id, base=bound.id, module=self.store.module)
        await self.save_state()
        await self.apply_options()  # dispatch_<agent>_<option> and the ticket's own, on new, load and resume, P199
        if self.ending:
            return
        if self.resume:  # a resumed session waits for the person's next message, or goes on when the supervisor retries
            await self.taken_over()
            if self.retrying and self.node is not None and not self.budget:
                self.turn(prompt('retry', work_id=self.work_id))
            await self.troubles()
            return
        if self.node is None and self.ctx.nouns.get('intake'):  # the intake, served as it is, VIEW-045 and BASE-039
            text = await asyncio.to_thread(intake_prompt, self.ctx, self.request)
        elif self.system and self.ctx.nouns.get('sentinel'):  # the person raised an issue: the sentinel skill, VIEW-045
            address = str(self.ctx.nouns['sentinel'])
            record = await asyncio.to_thread(ticket, self.store, self.work_id)
            given = f'node: {address}\nticket: {self.work_id}\nreport:\n{record.note or ""}'
            text = await asyncio.to_thread(workflow_skill, self.ctx, 'sentinel', given)
        elif self.system and self.ctx.nouns.get('talk'):  # the person clicked something to talk about: no ticket work
            about, read = await asyncio.to_thread(subject, self.store, self.work_id, str(self.ctx.nouns['talk']))
            text = prompt('talk', about=about, read=read, eyes=await asyncio.to_thread(eyes_line, Path(self.root)))
        elif self.system:  # the person's own, and their mascot's voice when they have one
            text = prompt('system', project=self.store.project_id,
                          mascot=await asyncio.to_thread(mascot_line, Path(self.root)))
        elif self.prep:
            from .merge import branch_of, dev_branch
            text = prompt('prep', work_id=self.work_id, branch=branch_of(self.work_id),
                          dev=dev_branch(self.store.project().path) or 'the dev branch')
        else:  # the hand-off with its counts, told to the agent's own session so it is not told them again, MCP-039
            text = None
        if text is None:
            text = await asyncio.to_thread(self.handed)
        if not self.ending:
            self.opening = self.system
            self.turn(text)
            await self.troubles()

    async def taken_over(self) -> None:
        """A session a runner on older code handed over, `hand_over`: one line in its thread says it was restarted on
        updated code, then what that runner was sent and could not record goes on, each message's line written here
        and its text sent as the agent's next turn, in the order it came."""
        path = handed_path(str(self.session_id))
        try:
            given: Any = json.loads(await asyncio.to_thread(path.read_text, encoding='utf-8'))
        except (OSError, ValueError):
            return
        with contextlib.suppress(OSError):
            path.unlink()
        kept: Any = cast(dict[str, Any], given).get('carried') if isinstance(given, dict) else None
        carried = cast(list[dict[str, Any]], kept) if isinstance(kept, list) else []
        async with self.lock:
            await self.note(None, 'notice', 'Restarted on updated code: the store moved to a newer layout than this '
                                            "session's runner was started with, so a runner on the current code took "
                                            'the session over.')
        for one in carried:
            text, by = str(one.get('text') or ''), str(one.get('by') or '')
            if one.get('by') is not None:
                async with self.lock:
                    await self.note(None, 'message' if by else 'person', f'From the {by} agent: {text}' if by else text)
            if text:
                self.turn(text)

    async def troubles(self) -> None:
        """The person's system agent takes each feature the person set up that a module says is not working, the
        signal SETUP_NOT_WORKING, as its next turn, after any turn in flight and never inside one: the setup_trouble
        prompt, so it brings the matter up with the person. Each is taken once, by the one system agent that clears
        it first; one raised while no system agent runs waits for the next to start."""
        if self.role != 'system' or self.probe or self.ending:
            return
        from .signals import SETUP_NOT_WORKING, rows, taken
        found = await asyncio.to_thread(rows, self.store)
        for value in found:
            if value.get('signal') != SETUP_NOT_WORKING or not value.get('signal_key'):
                continue
            if not await asyncio.to_thread(taken, self.store, value):
                continue
            report: Any = value.get('report')
            text = prompt('setup_trouble', feature=str(value.get('feature') or 'a feature'),
                          set_up=str(value.get('set_up') or ''), look=str(value.get('look') or ''),
                          report=json.dumps(report, ensure_ascii=False, indent=1))
            if text and not self.ending:
                self.turn(text)
        await self.changed(tables='dispatch', kinds=['session'])

    def handed(self) -> str:
        """The hand-off this worker is sent as its first turn, BASE-050, its links attached to that turn as ACP
        resource links; with no map to read it from, its one sentence alone. Ahead of it, the owner's memory prompt,
        filled with the ticket's element, a join's receiver under the Join rule, CTX-028."""
        try:
            text, self.attached = handoff_parts(self.ctx, self.work_id, session=self.runner)
        except Stop:
            text = work_line(self.work_id, Path(self.folder), self.at)
        try:
            memory = memory_text(Path(self.root), self.store.project_id, self.at.partition('|')[0] or None)
        except Exception as error:  # noqa: BLE001  a prompt that cannot be read never keeps the work from starting
            sys.stderr.write(f'Could not read the memory prompt for work {self.work_id}: {error}\n')
            memory = ''
        return f'{memory}\n\n{text}' if memory else text

    async def open_agent(self, identity: dict[str, str], *, terminal_login: bool = False) -> InitializeResponse:
        """Start the agent's adapter in its own process group, its stderr read into the thread, and initialize it.
        The client offers its own file reads and writes and its own terminals while dispatch_client_files and
        dispatch_client_terminal are on, P019, each confined to the folder the agent works in. It takes boolean config
        options, so every setting reaches the page;
        subagent sessions, so a subagent's work is a child session rather than mixed into its parent's, P016; ACP's
        elicitation in both modes, so a question the agent or one of its MCP servers puts to the person reaches them
        rather than being answered empty; and ACP's session notices, so what the agent says of its own state is a
        line of its own rather than mixed into its words. The SDK's schema has no `subagents` capability yet, so
        initialize is sent as the protocol's JSON; an SDK without its JSON-RPC connection initializes through its own
        call, with the capabilities its schema has, and the thread says what was left out."""
        loop = asyncio.get_running_loop()
        transport, protocol = await loop.subprocess_exec(
            lambda: Exits(LINE_LIMIT, loop), *self.command, stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, cwd=self.folder,
            env=windowless({**agent_environment(**identity), **start_environment(self.agent)}), **group_options())
        self.process, self.exited = asyncio.subprocess.Process(transport, protocol, loop), protocol.exited
        if self.process.stderr is not None:
            self.spawn(self.read_stderr(self.process.stderr))
        # The unstable protocol is enabled only so the SDK routes elicitation without a warning; ACP marks it Completed.
        self.conn = acp.connect_to_agent(self, self.process.stdin, self.process.stdout,  # pyright: ignore[reportArgumentType]
                                         observers=[self.observe], use_unstable_protocol=True)
        try:
            version = metadata.version('metaform')
        except metadata.PackageNotFoundError:
            version = '0'
        # The client's own files and terminals, P019, each offered while its setting is on.
        files, terminal = bool(self.option('dispatch_client_files', False)), \
            bool(self.option('dispatch_client_terminal', False))
        asked = InitializeRequest(
            protocol_version=acp.PROTOCOL_VERSION,
            client_capabilities=ClientCapabilities(
                fs=FileSystemCapabilities(read_text_file=files, write_text_file=files), terminal=terminal,
                session=ClientSessionCapabilities(config_options=SessionConfigOptionsCapabilities(
                    boolean=BooleanConfigOptionCapabilities())),
                auth=AuthCapabilities(terminal=terminal_login),
                elicitation=ElicitationCapabilities(form=ElicitationFormCapabilities(), url=ElicitationUrlCapabilities())),
            client_info=Implementation(name='metaform', title='Metaform', version=version))
        params = asked.model_dump(mode='json', by_alias=True, exclude_none=True)
        params['clientCapabilities']['subagents'] = {}  # claude-agent-acp and codex-acp: native subagent sessions
        params['clientCapabilities'].setdefault('session', {})['notices'] = {}  # ACP's session notices, v1
        connection = self.raw()
        if connection is None:
            self.left_out = 'subagent sessions and session notices, which this SDK version cannot send'
            init = await asyncio.wait_for(self.conn.initialize(
                protocol_version=asked.protocol_version, client_capabilities=asked.client_capabilities,
                client_info=asked.client_info), START_LIMIT)
            self.raw_init = init.model_dump(mode='json', by_alias=True, exclude_none=True)
        else:
            raw: Any = await asyncio.wait_for(connection.send_request('initialize', params), START_LIMIT)
            self.raw_init = cast(dict[str, Any], raw) if isinstance(raw, dict) else {}
            init = InitializeResponse.model_validate(self.raw_init)
        self.capture(init, self.raw_init)
        # An agent that answers with a version the runner does not speak is closed before any session, as ACP's
        # initialization asks; run() says why it did not start.
        if init.protocol_version != acp.PROTOCOL_VERSION:
            raise RuntimeError(f'{self.name} answered initialize with ACP protocol version {init.protocol_version}; '
                               f'Metaform speaks version {acp.PROTOCOL_VERSION}')
        return init

    def asked_for(self) -> str:
        """What the person asked the intake for, from the row its launch holds its slot in, so their words never go in
        an argument; taken before the session is made, while the row is still there, and cleared once read. Nothing
        asked is this project."""
        with Store(self.store.project_id, module='dispatch').tables() as tx:
            row = tx.get('raised', {'work_id': self.work_id})
            if row is None or not row['asked']:
                return ''
            tx.update('raised', {'work_id': self.work_id}, {'asked': None})
        return str(row['asked'])

    async def reopen(self, servers: list[McpServerStdio]) -> Any:
        """The ended session made live again: session/resume where the agent offers it, which sends nothing back, or
        else session/load, which replays the history the thread already holds and is not written again."""
        caps = cast(dict[str, Any], self.acp['capabilities'])
        session_id = cast(str, self.resume)
        if caps.get('resume'):
            self.acp['resumed'] = 'resume'
            return await self.conn.resume_session(session_id=session_id, cwd=self.folder, mcp_servers=servers,
                                                   **held_settings(await self.denied()))
        if caps.get('load'):
            self.acp['resumed'] = 'load'
            self.replaying = True
            return await self.conn.load_session(cwd=self.folder, session_id=session_id, mcp_servers=servers,
                                                 **held_settings(await self.denied()))
        raise RuntimeError(f'{self.name} offers neither session/resume nor session/load, so session {session_id} '
                           'cannot be resumed')

    def continue_thread(self) -> None:
        """Take up the ended session's thread: the names its lines are kept by, the last of their order, what its
        state held of the map it touched, and what it last reported of itself, its plan, usage, tokens, title and
        commands, each named in `before_resume` until the agent reports it again. Its settings and capabilities are
        not carried: the agent gives them afresh when it starts and resumes."""
        with self.store.tables(write=False) as tx:
            rows = tx.rows('session_lines', {'session_id': self.session_id}, by=('session_id', 'seq'), limit=0).results
        self.named = {str(row['name']) for row in rows}
        self.lines = max((int(row['seq']) for row in rows), default=0)
        self.flows = max((int(name[5:]) for name in self.named if name.startswith('flow:') and name[5:].isdigit()),
                         default=0)
        kept = next((row for row in rows if row['name'] == 'state'), None)
        before: Any = None
        if kept is not None:
            with contextlib.suppress(ValueError, TypeError):
                before = json.loads(str(kept['text']))
        if isinstance(before, dict):
            held = cast(dict[str, Any], before)
            self.acp['touched'] = list(held.get('touched') or [])
            if held.get('prompts') in PROMPTS:  # the person's choice for this session holds when it goes on
                self.acp['prompts'] = held['prompts']
            carried =[key for key in CARRIED if held.get(key) not in (None, [], '')]
            self.acp.update({key: held[key] for key in carried})
            self.acp['before_resume'] = carried

    def recording(self, path: str) -> Any:
        """The person's spoken message as an ACP audio block, ContentBlock::Audio, beside its transcript: only for a
        session whose agent declared promptCapabilities.audio, never assumed, and only a clip the web GUI kept under the
        home's run/voice/clips. The file is removed once read, sent or not, so the recording is not left behind."""
        if not path:
            return None
        clips = (home.home() / 'run' / 'voice' / 'clips').resolve()
        file = Path(path).resolve()
        if file.parent != clips or file.suffix != '.wav':
            return None
        try:
            data = file.read_bytes() if self.acp['capabilities'].get('audio') else None
        except OSError:
            data = None
        finally:
            file.unlink(missing_ok=True)
        return acp.audio_block(base64.b64encode(data).decode('ascii'), 'audio/wav') if data else None

    def picture(self, path: str) -> Any:
        """A frame the person sent with a message as an ACP image block, ContentBlock::Image, beside its text: only for
        a session whose agent declared promptCapabilities.image, never assumed, and only a frame the web GUI kept under
        the home's run/captures. The file is removed once read, sent or not."""
        if not path:
            return None
        frames = (home.home() / 'run' / 'captures').resolve()
        file = Path(path).resolve()
        kinds = {'.jpg': 'image/jpeg', '.png': 'image/png'}
        if file.parent != frames or file.suffix not in kinds:
            return None
        try:
            data = file.read_bytes() if self.acp['capabilities'].get('image') else None
        except OSError:
            data = None
        finally:
            file.unlink(missing_ok=True)
        return acp.image_block(base64.b64encode(data).decode('ascii'), kinds[file.suffix]) if data else None

    def timer(self, asked: dict[str, Any]) -> dict[str, Any]:
        """The agent's own timers, `dispatch timer`, held by this runner and so never outliving the session they wake:
        set, one wakes the session after its seconds with the agent's note as a turn; cancel takes one back by its id;
        with neither, the timers set."""
        if asked.get('cancel'):
            held = self.timers.pop(str(asked['cancel']), None)
            if held is not None:
                held['handle'].cancel()
            return {'timer': str(asked['cancel']), 'cancelled': held is not None}
        if asked.get('seconds') is None:
            return {'timers': [{'timer': key, 'due': one['due'], 'text': one['text']} for key, one in self.timers.items()]}
        if self.ending or self.session_id is None:
            return {'error': 'The session has not started or is ending.'}
        key, seconds = secrets.token_hex(4), float(asked['seconds'])
        due = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(time.time() + seconds))
        handle = asyncio.get_running_loop().call_later(seconds, lambda: self.spawn(self.timer_due(key)))
        self.timers[key] = {'handle': handle, 'text': str(asked.get('text') or ''), 'due': due, 'set': stamp()}
        return {'timer': key, 'due': due, 'work_id': self.work_id, 'session_id': self.session_id}

    async def timer_due(self, key: str) -> None:
        """A timer is due: its note goes in the thread, and the session takes a turn with it, after any before it."""
        held = self.timers.pop(key, None)
        if held is None or self.ending:
            return
        async with self.lock:
            await self.note(None, 'timer', f'Timer {key}, set at {held["set"]}, is due: {held["text"]}')
        self.turn(prompt('timer', timer=key, set=held['set'], note=held['text']))

    async def peer_note(self, asked: dict[str, Any]) -> dict[str, Any]:
        """A peer note, `dispatch note`, `peering`: its line in this session's thread, after the words so far, on the
        sender's and each receiver's alike. A receiver takes it as a turn after any in flight, never steered into one,
        so it waits for the turn boundary as a person's message does, and the open pages draw it as a pulse of the
        flow from the sender's figure to this one; a reply to a question this session is waiting on is held for that
        wait instead, which returns it. The sender's own copy notes how long it waits, `awaiting`."""
        line: Any = asked.get('line')
        if self.ending or self.session_id is None or not isinstance(line, dict):
            return {'noted': False, 'error': 'The session has not started or is ending.'}
        held, busy = cast(dict[str, Any], line), bool(self.turns)
        note_id = str(held.get('id'))
        sender: dict[str, Any] = held.get('from') or {}
        if asked.get('deliver') and sender.get('node') and self.node is not None and not self.probe:
            # the pulse between the two figures, riding the event the note's line fires
            self.flowing.append({'session_id': sender.get('session_id'), 'agent': sender.get('agent'),
                                 'work_id': sender.get('work_id'), 'from': sender['node'],
                                 'to': [{'kind': self.node.kind, 'id': self.node.id}], 'action': 'note'})
        async with self.lock:
            await self.flush()
            await self.note(f'peer:{note_id}', 'peer', json.dumps(held, ensure_ascii=False))
        if not asked.get('deliver'):
            if asked.get('awaiting'):
                self.awaiting[note_id] = {'until': time.monotonic() + float(asked['awaiting']) + AWAIT_SPARE,
                                          'held': []}
            return {'noted': True}
        reply_to = str(held.get('reply_to') or '')
        what = 'question' if held.get('ask') else f'reply to your note {reply_to}' if reply_to else 'note'
        text = prompt('peer_note', what=what, agent=str(sender.get('agent') or ''), item=str(sender.get('item') or ''),
                      title=str(sender.get('title') or ''), note=str(held.get('text') or ''), id=note_id)
        marks = [(note_id, str(sender.get('session_id') or ''))]
        waiting = self.awaiting.get(reply_to)
        if waiting is not None and time.monotonic() < float(waiting['until']):
            cast(list[Any], waiting['held']).append((note_id, text, marks))  # the waiting call returns it
            return {'noted': True, 'queued': False, 'awaited': True}
        self.turn(text, peers=marks)
        return {'noted': True, 'queued': True, 'busy': busy}

    def unawait(self, asked: dict[str, Any]) -> dict[str, Any]:
        """A question's wait is over, `dispatch note wait=`: the replies held for it that the call did not return go
        to the agent as turns after all, so none is lost between the call's last read and its end."""
        waiting = self.awaiting.pop(str(asked.get('id') or ''), None)
        taken = {str(one) for one in cast(list[Any], asked.get('taken') or [])}
        given = 0
        for note_id, text, marks in cast(list[Any], (waiting or {}).get('held') or []):
            if note_id not in taken:
                self.turn(text, peers=marks)
                given += 1
        return {'released': given}

    async def peer_marked(self, marks: list[tuple[str, str]], state: str) -> None:
        """The peer notes a turn carried, marked on this session's copy and on each sender's."""
        if not marks or self.session_id is None:
            return
        own = self.session_id

        def marked(tx: Any) -> None:
            for note_id, sender in marks:
                for session_id in {own, sender} - {''}:
                    mark_peer(tx, session_id, note_id, self.work_id, state)
        await self.table(marked, fatal=False)

    def carried(self) -> None:
        """The prompt versions served since the last turn went out, told on `prompt.sent` with this session's ids and
        role as that turn goes, so a module that keeps what each session was sent records it, ticket 3a1306bd. Nothing
        is told for a turn that carried no prompt, such as the person's own message, or for an agent started only to
        be asked something."""
        taken = [self.sent.pop(0) for _ in range(len(self.sent))]
        if not taken or self.session_id is None or self.probe:
            return
        payload = {'project': self.store.project_id, 'work_id': self.work_id, 'session_id': self.session_id,
                   'runner': self.runner, 'role': self.role, 'agent': self.agent, 'at': stamp(),
                   'prompts': [{'name': one.name, 'number': one.number, 'origin': one.origin,
                                'version_id': one.version_id} for one in taken]}
        self.spawn(self.ctx.publish_async('prompt.sent', payload))

    def turn(self, text: str, audio: Any = None, image: Any = None, peers: list[tuple[str, str]] | None = None) -> None:
        if self.handing:  # the runner taking the session over sends it
            self.handed_on.append({'text': text, 'by': None})
            return
        if self.ending:
            return
        self.carried()
        self.replaying = False  # what comes from here on is the session's own, never a replay
        self.pending.append(text)
        self.voiced.append([block for block in (audio, image) if block is not None])
        self.peered.append(list(peers or []))  # the peer notes the turn carries, marked as it is sent and read
        if self.turns == 0:
            self.progress_at = time.monotonic()
        if self.turns:
            return
        self.turns = 1
        self.active_turn = ActiveTurn()
        self.idle.clear()
        self.spawn(self.prompted())

    async def prompted(self) -> None:
        """One prompt in flight, draining messages in order before the normal turn-end decision."""
        reason = ''
        try:
            if not self.prep:  # the agent is working again, so it no longer stands stopped with its ticket open
                async with self.lock:
                    await self.raise_signal('stopped-open', active=False)
            while self.pending and not self.ending:
                async with self.interrupt_lock:
                    current = self.active_turn or ActiveTurn()
                    self.active_turn = current
                    text = self.pending.popleft()
                    beside = self.voiced.popleft() if self.voiced else []
                    marks = self.peered.popleft() if self.peered else []
                self.heard = stamp()  # a tool call of this turn began no earlier than its prompt
                began_ns: int | None = None
                try:
                    await self.changed(tables='dispatch', kinds=['session'])
                    if self.ending:
                        break  # stop may arrive while the turn-start event is published
                    if current.cancel_requested:
                        reason = 'cancelled'
                    else:
                        current.sent = True
                        # The rule on writing files rides the first prompt this process sends the session, whatever
                        # it is, a ticket's hand-off, a resumed session's next message, the system agent's or the
                        # intake's opening, and is never a turn of its own; the lock holds from then, #47, CTX-043.
                        if LINK_LOCK and not self.ruled and not self.probe:
                            rule = prompt('work_link')
                            text = f'{text}\n\n{rule}' if rule else text
                            self.ruled = True
                        await self.peer_marked(marks, 'delivered')
                        self.cost_open, self.provisional = False, 0
                        self.arm()  # the turn's silence clock, P040
                        self.intake_clock()  # an intake's first-record clock starts with its first turn, M04
                        began_ns = time.time_ns()
                        blocks: list[Any] = [acp.text_block(text), *beside]
                        blocks += [acp.resource_link_block(one['name'], one['uri'], title=one.get('title'))
                                   for one in self.attached]  # the hand-off's links, typed, beside its text
                        self.attached = []
                        if not self.prep:
                            from .progress import executed
                            await asyncio.to_thread(executed, self.store, self.work_id, str(self.runner))
                        answer = await self.conn.prompt(session_id=self.session_id, prompt=blocks)
                        reason = str(answer.stop_reason)
                        if answer.usage is not None:  # the tokens of this turn, as the agent counts them
                            self.acp['tokens'] = answer.usage.model_dump(mode='json', exclude_none=True,
                                                                         exclude={'field_meta'})
                            self.reported('tokens')
                        await self.spend(answer.usage)
                        self.trace(answer.usage, reason, began_ns)
                except Exception as error:  # noqa: BLE001  the turn's end is noted whatever ended it
                    reason = f'error: {error}'
                    if began_ns is not None:  # a turn sent and failed is reported too, as an error
                        self.trace(None, 'error', began_ns, error=str(error) or type(error).__name__)
                self.hush()
                async with self.interrupt_lock:
                    self.active_turn = None
                    self.interrupted = current.cancel_requested  # a turn sent since the interrupt clears it
                self.opening = False
                async with self.lock:
                    await self.flush()
                    await self.note('turn', 'turn', f'The turn ended: {reason}.')
                    if self.acp['tokens'] is not None:
                        await self.save_state()
                if current.sent and reason != 'cancelled' and not reason.startswith('error'):
                    await self.peer_marked(marks, 'read')  # the turn that carried them ended: they were read
        finally:
            self.turns -= 1
            if self.turns == 0:
                self.idle.set()
        await self.changed(tables='dispatch', kinds=['session'])  # readers now see idle after the queue drained
        if self.turns == 0 and not self.ending and not self.prep:
            record = await asyncio.to_thread(ticket, self.store, self.work_id)
            if self.turns or self.ending:  # a message can arrive while the ticket is read
                return
            if record.done:
                await self.ticket_done()
                return
            # Otherwise the agent stopped with its ticket open: the session stays, idle and reachable, and the
            # ticket stays taken with the agent's last note, until the person talks to it, stops it or puts the
            # ticket back. Nothing restarts by itself, change order of 2026-10-07. The stopped-open signal says so,
            # since the session no longer ends, BASE-057; the next turn or the session's end clears it. Once per
            # session a worker is first given a turn to record what it learned, P033, on_stopped_open or, after a
            # turn that failed, on_failure; the signal is raised when that turn ends.
            # A turn the person interrupted is not followed by one: they stopped it to say something.
            if not self.interrupted and await self.record_before_stop(reason):
                return
            async with self.lock:
                if not self.turns and not self.ending:  # a message that came meanwhile has started the next turn
                    await self.raise_signal('stopped-open', stop_reason=reason, steps=record.steps_done)

    async def ticket_done(self) -> None:
        """A worker's ticket is done: once per session, the agent first gets one more turn to record what it learned
        at the ticket's node when `dispatch_record_on_finish` asks for it, and the session ends when that turn ends;
        otherwise it ends now, BASE-052. The turn's end and a change heard from elsewhere can both find the ticket
        done; whichever comes second leaves the decision to the first."""
        if self.finishing or self.ending:
            return
        self.finishing = True
        try:
            if not self.record_asked and self.budget is None:  # past a budget, no further turn of Metaform's own
                self.record_asked = True
                try:
                    text = await asyncio.to_thread(self.record_prompt)
                except Exception as error:  # noqa: BLE001  a failed check never keeps the session from ending
                    sys.stderr.write(f'Could not check what work {self.work_id} recorded: {error}\n')
                    text = ''
                if text and not self.ending and not self.turns:
                    self.turn(text)
                    return
            if not self.turns:
                await self.end('the ticket is done')
        finally:
            self.finishing = False

    async def record_before_stop(self, reason: str) -> bool:
        """Give a worker that stopped with its ticket open one turn, once per session, to record what it learned,
        P033: the on_failure turn after a turn that ended in an error while its agent still runs, otherwise the
        on_stopped_open turn, each as its setting asks. Whether the turn was sent."""
        if self.stop_record_asked or self.budget is not None or self.role != 'worker' or self.ending:
            return False
        self.stop_record_asked = True
        failed = reason.startswith('error')
        if failed and (self.process is None or self.process.returncode is not None or self.exited.is_set()):
            return False
        setting, name = ('dispatch_record_on_failure', 'on_failure') if failed else \
            ('dispatch_record_on_stop', 'on_stopped_open')
        try:
            text = await asyncio.to_thread(self.record_prompt, setting, name)
        except Exception as error:  # noqa: BLE001  a failed check never keeps the session from waiting as before
            sys.stderr.write(f'Could not check what work {self.work_id} recorded: {error}\n')
            return False
        if not text or self.ending or self.turns:
            return False
        self.turn(text)
        return True

    def trace(self, usage: Any, reason: str, began_ns: int, error: str | None = None) -> None:
        """The turn as an OpenTelemetry invoke_agent span with its usage, recorded only where an OpenTelemetry SDK is
        set up in this process; a turn that failed carries its error."""
        info = cast(dict[str, Any], self.acp.get('agent_info') or {})
        model = next((str(one.get('current')) for one in self.settings() if one.get('category') == 'model'
                      and one.get('current')), None)
        traced(usage_attributes(self.agent, self.name, cast(str | None, info.get('version')), self.session_id, usage,
                                reason, model), began_ns, error)

    def record_prompt(self, setting: str = 'dispatch_record_on_finish', name: str = 'on_ticket_done') -> str:
        """The turn asking a worker to record at its node, `on_ticket_done` by default, with where to record, when one
        is due: never with its setting `off`, the prompt empty, no node or the memory module off its surface, which
        leaves the agent nothing to record with; always with `always`; with `when-missing` only when no memory join or
        observation at the node was written by this session, its `by` the runner's id, BASE-052 and STORE-020."""
        mode = self.ctx.setting(setting)
        if mode == 'off' or self.node is None:
            return ''
        node = self.at if self.node.kind == 'element' and self.at else f'{self.node.kind}:{self.node.id}'
        text = prompt(name, node=node)
        if not text:
            return ''
        root = Path(self.root)
        said = memory_read(root, self.store.project_id, 'joins', node=node)
        if said is None:
            return ''
        if mode == 'always':
            return text
        joined = cast(list[dict[str, Any]], said['joins'])
        if any(row['by'] == self.runner for row in joined):
            return ''
        names = {row['entity'] for row in joined}
        if names:
            whole = memory_read(root, self.store.project_id, 'graph')
            if any(one['by'] == self.runner for entity in whole['entities'] if entity['name'] in names
                   for one in entity['observations']):
                return ''
        return text

    async def interrupt(self) -> bool:
        """Request cancellation of only the current turn; its response owns completion and queued prompts stay serial."""
        async with self.interrupt_lock:
            current = self.active_turn
            if self.ending or self.session_id is None or current is None:
                return False
            if current.cancel_requested:
                return True
            current.cancel_requested = True
            if current.sent:
                try:
                    await asyncio.wait_for(self.conn.cancel(session_id=self.session_id), END_LIMIT)
                except Exception:
                    current.cancel_requested = False  # a failed notification must allow a real retry
                    raise
            async with self.lock:
                for request, (waiting, _, title) in list(self.asked.items()):
                    message_id = self.permissions.get(request, {}).get('message_id')
                    if message_id:  # closed history remains, without live answer controls
                        await self.write(self.store.reply, message_id)
                    if not waiting.done():
                        waiting.set_result(None)
                    await self.raise_signal('permission-waiting', key=request, active=False,
                                            message_id=message_id, request=request, tool=title)
                    await self.permission(request, state='cancelled')
                self.asked.clear()
                await self.elicitations_cancelled()
                await self.flush()
                await self.note(None, 'interrupt', 'Cancellation of the current turn requested.')
            await self.changed(tables='dispatch', kinds=['session'])
            return True

    async def watch(self, process: asyncio.subprocess.Process) -> None:
        await self.exited.wait()
        code = process.returncode
        if not self.ending:
            said = self.tail()
            await self.end(f'the agent ended with exit code {code}' + (f'; its last stderr: {said}' if said else ''))

    def changed_elsewhere(self, payload: dict[str, Any]) -> None:
        """map.changed from another process, handed over by the base's listener, BASE-053, acted on only when it can
        concern this session: one naming its ticket or its session, as the person's answer to its permission request
        or a step on its ticket, is checked; one naming only other tickets and sessions, such as another agent's thread
        lines and steps, does nothing here. A change that does not say what it concerns is checked only when it wrote
        tickets, questions or workflow runs, or did not say what it wrote. A change to its ticket's workflow runs reads
        those runs. A change to the map itself may move the refs that place a file on it, so they are read again when
        next needed. This process's own writes never come back here."""
        if payload.get('project') != self.store.project_id or self.ending:
            return
        given: Any = payload.get('tables')
        tables = None if given is None else [given] if isinstance(given, str) else \
            [str(one) for one in cast(list[Any], given)] if isinstance(given, list) else []
        if tables is None or any(not table.startswith('dispatch') for table in tables):
            self.sources = None
        if concerns(payload, self.work_id, self.session_id, tables):
            self.checks()
            if tables is None or any(table.startswith('workflow.') for table in tables):
                self.spawn(self.workflow_answers())
        raised: Any = payload.get('signal')
        if isinstance(raised, dict) and cast(dict[str, Any], raised).get('signal') == 'setup-not-working' \
                and cast(dict[str, Any], raised).get('active') and self.session_id is not None:
            self.spawn(self.troubles())  # a feature the person set up is not working: the system agent says so

    async def workflow_answers(self) -> None:
        """A workflow run this worker's ticket paused on the person, MAP-050, that the person has answered since: the
        agent is told to resume it, the workflow_answered prompt as its next turn, so the person's answer reaches it
        without a message of their own, H03. Read on a change to its ticket's runs only, and then only the runs paused
        on the person, and the running ones once one it knew paused is no longer paused; through workflow's own runs
        verb, never its tables. A change that comes during a read is read once more after it."""
        if self.node is None or self.system or self.prep or self.probe or self.ending:
            return
        if self.workflow_reading:
            self.workflow_again = True
            return
        self.workflow_reading = True
        try:
            while True:
                self.workflow_again = False
                await self.workflow_read()
                if not self.workflow_again or self.ending:
                    return
        finally:
            self.workflow_reading = False

    async def workflow_read(self) -> None:
        def runs(state: str) -> list[dict[str, Any]]:
            found = module_read(Path(self.root), self.store.project_id, 'workflow', 'runs', state=state, limit=0)
            listed: Any = cast(dict[str, Any], found).get('runs') if isinstance(found, dict) else None
            return [run for run in cast(list[dict[str, Any]], listed or []) if run.get('ticket') == self.work_id]
        try:
            paused = {str(run.get('run')) for run in await asyncio.to_thread(runs, 'input_required')}
            left = self.paused_runs - paused
            running: set[str] = {str(run.get('run')) for run in await asyncio.to_thread(runs, 'running')} \
                if left else set()
        except Exception as error:  # noqa: BLE001  a read that fails delivers nothing; the ticket's note still says it
            sys.stderr.write(f'Could not read the workflow runs: {error}\n')
            return
        self.paused_runs = (self.paused_runs | paused) - left  # one no longer paused is answered, or ended
        for word in sorted(left & running):
            text = prompt('workflow_answered', run=word)
            if text and not self.ending:
                current = self.active_turn  # into the turn in flight where the agent steers, else its next turn
                steered = (await self.steer(text) if self.turns and not self.pending and current is not None
                           and current.sent and not current.cancel_requested else False)
                async with self.lock:
                    await self.note(None, 'notice', f'Workflow run {word} was answered; its agent is told to '
                                                    'resume it.')
                if not steered:
                    self.turn(text)

    async def control(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        """One request on the control port, with this session's token: `status`, `message`, `interrupt`, `stop`,
        `cancel`, and the person's own controls of the session, `permit` a permission request's option, `configure` a
        setting and `tune`, the ticket's own model and effort applied again."""
        try:
            line = await asyncio.wait_for(reader.readline(), REPLY_LIMIT)
            found: Any = json.loads(line) if line else None
            asked = cast(dict[str, Any], found) if isinstance(found, dict) else {}
            if asked.get('token') != self.token:
                await self.reply(writer, {'error': 'This is not a request for this session.'})
                return
            said = {'work_id': self.work_id, 'agent': self.agent, 'session_id': self.session_id}
            op = asked.get('op')
            if op == 'status':
                alive = self.process is not None and self.process.returncode is None and not self.exited.is_set()
                live = alive and not self.ending and self.failure is None and not self.handing
                activity = ('waiting' if self.waiting else 'working' if self.turns else 'idle') if live else 'idle'
                how, source = await self.answering() if live else (None, None)
                await self.reply(writer, {**said, 'state': 'running' if live else 'ended', 'agent_alive': alive,
                                          # how its permission requests are answered now, and whose choice that is
                                          **({'prompts': how, 'prompts_from': source} if how else {}),
                                          'activity': activity,
                                          'waiting_on': 'question' if self.elicited else 'permission' if self.asked
                                          else None,
                                          'interrupting': bool(self.active_turn and self.active_turn.cancel_requested),
                                          # an intake waiting for its first record, M04, said as the page reads it
                                          **({'phase': self.intake.get('phase')} if live and self.intake else {}),
                                          'how': None if live else self.how or 'the agent is no longer running'})
            elif op == 'message' and asked.get('fork') in self.children and self.children[asked['fork']].get('fork'):
                self.spawn(self.fork_turn(str(asked['fork']), str(asked.get('text', ''))))  # a turn of a fork, P030
                await self.reply(writer, {**said, 'sent': True, 'fork': asked['fork']})
            elif op == 'message':
                if self.ending or self.session_id is None:
                    await self.reply(writer, {**said, 'sent': False, 'error': 'The session has not started or is ending.'})
                    return
                text, by = str(asked.get('text', '')), str(asked.get('by') or '')
                audio = self.recording(str(asked.get('audio') or '')) if not by else None
                image = self.picture(str(asked.get('image') or '')) if not by else None
                # one message of a broadcast, `dispatch broadcast`: its line is kept under the broadcast's id
                sent = str(asked.get('broadcast') or '')
                if not self.handing:
                    async with self.lock:  # the sender's words in the thread, where the agent's reply follows
                        await self.flush()
                        # an agent's message is never shown as the person's, BASE-052
                        await self.note(f'broadcast:{sent}' if sent else None, 'message' if by else 'person',
                                        f'From the {by} agent: {text}' if by else text)
                if self.handing:  # its line could not be written: the runner taking the session over writes and sends it
                    self.handed_on.append({'text': text, 'by': by})
                    await self.reply(writer, {**said, 'sent': True, 'steered': False, 'handed': True})
                    return
                # Into the turn in flight when the agent offers steering and nothing waits before it, P016; otherwise
                # it waits its turn, in order.
                current = self.active_turn
                steered = (await self.steer(text) if self.turns and not self.pending and current is not None
                           and current.sent and not current.cancel_requested and audio is None and image is None
                           and not self.opening else False)
                if steered is not False:
                    async with self.lock:
                        await self.note(None, 'steered', 'Delivered into the running turn.' if steered else
                                        f'{self.name} did not answer the steer in time, so it was withdrawn; it may '
                                        'have reached the turn, so it is not sent again. Send it again if it did not.')
                    await self.reply(writer, {**said, 'sent': True, 'steered': steered})
                    return
                self.turn(text, audio, image)
                await self.reply(writer, {**said, 'sent': True, 'steered': False, 'audio': audio is not None,
                                          'image': image is not None})
            elif op == 'timer':  # the agent's own timers, `dispatch timer`
                await self.reply(writer, {**said, **self.timer(asked)})
            elif op == 'note':  # a peer note, `dispatch note`: kept in the thread, and the receiver's next turn
                await self.reply(writer, {**said, **await self.peer_note(asked)})
            elif op == 'unawait':  # a question's wait is over: what was held for it and not returned is given
                await self.reply(writer, {**said, **self.unawait(asked)})
            elif op == 'attach':  # a file the agent attached to its chat, `dispatch attach`, after its words so far
                given_attachment: Any = asked.get('attachment')
                if self.session_id is None or not isinstance(given_attachment, dict):
                    await self.reply(writer, {**said, 'attached': False, 'error': 'The session has not started.'})
                    return
                attachment = cast(dict[str, Any], given_attachment)
                async with self.lock:
                    await self.flush()
                    await self.note(f'attachment:{attachment.get("id")}', 'attachment',
                                    json.dumps(attachment, ensure_ascii=False))
                await self.reply(writer, {**said, 'attached': True})
            elif op == 'interrupt':
                try:
                    requested = await self.interrupt()
                    await self.reply(writer, {**said, 'requested': requested})
                except Exception as error:  # noqa: BLE001  a failed cancel is reported without destroying the session
                    await self.reply(writer, {**said, 'error': f'Could not interrupt the turn: {error}'})
            elif op == 'permit':
                await self.reply(writer, {**said, **await self.permit(str(asked.get('request', '')),
                                                                      str(asked.get('option', '')))})
            elif op == 'configure':
                await self.reply(writer, {**said, **await self.configure(str(asked.get('setting', '')),
                                                                         str(asked.get('value', '')))})
            elif op == 'prompts':  # how this session's permission requests are answered, the person's choice
                await self.reply(writer, {**said, **await self.set_prompts(str(asked.get('prompts', '')))})
            elif op == 'fork':  # ACP's session/fork, a side conversation with the session's context, P030
                try:
                    await self.reply(writer, {**said, **await self.fork(str(asked.get('text') or ''))})
                except Exception as error:  # noqa: BLE001  a fork that fails leaves the session as it was
                    await self.reply(writer, {**said, 'error': f'Could not fork the session: {error}'})
            elif op == 'tune':  # the ticket's own model and effort, changed while it runs, P015
                await self.reply(writer, {**said, 'applied': await self.apply_options()})
            elif op in ('stop', 'cancel'):  # session/cancel for a turn in flight, then the session ends, P232
                await self.end('stopped by the person' if op == 'stop' else 'cancelled by the person', release=False)
                try:
                    await self.reply(writer, {**said, 'stopped': True})
                finally:
                    self.ended.set()
            else:
                await self.reply(writer, {'error': f'No request {op}.'})
        except (TimeoutError, OSError, ValueError):
            pass
        finally:
            with contextlib.suppress(Exception):
                writer.close()

    @staticmethod
    async def reply(writer: asyncio.StreamWriter, answer: dict[str, Any]) -> None:
        writer.write(json.dumps(answer).encode('utf-8') + b'\n')
        await writer.drain()

    async def end(self, how: str, release: bool = True) -> None:
        """End the session once: cancel a running turn, answer every waiting request as cancelled, close the agent's
        input, end its process group and say on the map how it ended."""
        if self.ending:
            await self.over.wait()
            if release:
                self.ended.set()
            return
        self.ending, self.how = True, how
        self.pending.clear()
        self.voiced.clear()
        self.peered.clear()
        for held in self.timers.values():  # a timer never outlives the session it wakes
            held['handle'].cancel()
        self.timers.clear()
        try:
            # Cancelling startup would abandon to_thread writes or a child being created. Let the current
            # acquisition finish and let begin observe ending before proceeding, then clean up its resources.
            async with self.starting:
                pass
            for request, (waiting, _, title) in list(self.asked.items()):
                if not waiting.done():
                    waiting.set_result(None)
                with contextlib.suppress(Exception):
                    await self.raise_signal('permission-waiting', key=request, active=False,
                                            message_id=self.permissions.get(request, {}).get('message_id'),
                                            request=request, tool=title)
                with contextlib.suppress(Exception):
                    await self.permission(request, state='cancelled')
            self.asked.clear()
            with contextlib.suppress(Exception):
                await self.elicitations_cancelled()
            process = self.process
            if process is not None and process.returncode is None:
                if self.turns and self.conn is not None and self.session_id is not None:
                    with contextlib.suppress(Exception):
                        await self.conn.cancel(session_id=self.session_id)
                    with contextlib.suppress(asyncio.TimeoutError):
                        await asyncio.wait_for(self.idle.wait(), END_LIMIT)
                await self.close_session()  # the agent frees the session; it can still be resumed or loaded later
                if process.stdin is not None:
                    with contextlib.suppress(Exception):
                        process.stdin.close()
                with contextlib.suppress(asyncio.TimeoutError):
                    await asyncio.wait_for(self.exited.wait(), END_LIMIT)
            await self.terminals_ended()  # the terminals it asked for end with it, P019
            if self.folder != self.root and not self.prep and self.node is not None:  # nothing lost on a crash, P009
                with contextlib.suppress(Exception):
                    await asyncio.to_thread(checkpoint, self.folder, self.work_id,
                                            f'The session of ticket {self.work_id} ended: {how}')
            if self.intake_timer is not None:
                self.intake_timer.cancel()
                self.intake_timer = None
            if process is not None:
                await asyncio.to_thread(end_group, process.pid)  # what it started ends with it
                with contextlib.suppress(asyncio.TimeoutError):
                    await asyncio.wait_for(process.wait(), END_LIMIT)
            if self.conn is not None:
                with contextlib.suppress(Exception):
                    await self.conn.close()
            try:
                async with self.lock:
                    await self.flush()
            except Exception as error:  # noqa: BLE001  transcript failure cannot prevent session cleanup
                sys.stderr.write(f"Could not flush the ended session: {error}\n")
            with contextlib.suppress(Exception):  # the last lines are announced before the process can end
                await self.lines_flush()
            if self.took or self.recorded:
                await self.release(how)
        finally:
            self.over.set()
            if release:
                self.ended.set()

    async def close_session(self) -> None:
        """ACP's session/close, when the agent offers it and the session is open, within END_LIMIT; once."""
        if self.closed or self.conn is None or self.session_id is None or not self.acp['capabilities'].get('close'):
            return
        self.closed = True
        with contextlib.suppress(Exception):
            await asyncio.wait_for(self.conn.close_session(session_id=self.session_id), END_LIMIT)

    async def release(self, how: str) -> None:
        """Give back the ticket and record the session ended, never silently failing: when this runner's code cannot
        reach the store, as when a newer Metaform upgraded it under the runner, STORE-029, a new process does it with
        the code on disk; when that fails too, the runner's log says what is left and how to put the ticket back."""
        if self.handing and await self.hand_over():
            return
        owner = self.by if self.recorded else self.ctx.nouns.get('reservation') or self.by
        given: dict[str, Any] = {'work_id': self.work_id, 'by': owner, 'took': self.took,
                                 'session_id': self.session_id if self.recorded else None, 'how': how,
                                 'runner': self.runner}
        try:
            await asyncio.to_thread(release, self.store, **given)
        except Exception as error:  # noqa: BLE001  the code on disk may reach what this code cannot
            command = [sys.executable, '-c', RELEASE, json.dumps({'project': self.store.project_id, **given})]
            try:
                done = await asyncio.to_thread(subprocess.run, command, capture_output=True, text=True,
                                               encoding='utf-8', stdin=subprocess.DEVNULL, timeout=RELEASE_LIMIT)
                failed = done.stderr.strip() if done.returncode else None
            except (OSError, subprocess.TimeoutExpired) as run_error:
                failed = str(run_error)
            if failed is not None:
                sys.stderr.write(f'Could not end session {self.session_id} on work {self.work_id}: {error}\n'
                                 f'Nor with the code on disk: {failed}\n')
                if self.took:
                    on = os.environ.get(BASE_VARIABLE)  # its ticket is in the metaform this runner stayed on
                    sys.stderr.write(f'Work {self.work_id} stays taken by {self.by}. To put it back: '
                                     f'{f"{BASE_VARIABLE}={on} " if on else ""}'
                                     f'metaform map work op=move id={self.work_id} column=todo\n')
                return
        with contextlib.suppress(Exception):  # the release stands whether or not an open page hears of it
            await self.changed()


    async def hand_over(self) -> bool:
        """Start a runner on the code on disk that resumes this very session, never the latest one, once this one's
        agent has ended: the code on disk does it, as it does a release, STORE-029. A worker goes on as its ticket's
        worker, against the same run, told to go on where it left off when a turn was cut short; a conversation goes
        on as one. False when it could not, and the session is released as any other."""
        extra = [*(['system=true'] if self.system else []),
                 *([f"talk={self.ctx.nouns['talk']}"] if self.ctx.nouns.get('talk') else []),
                 *([f'run={self.run_id}', *(['retry=true'] if self.cut else [])] if self.node is not None
                   and not self.system and not self.prep else [])]
        given = {'project': self.store.project_id, 'work_id': self.work_id, 'agent': self.agent,
                 'session_id': self.session_id, 'runner': self.runner, 'pid': os.getpid(), 'extra': extra,
                 'carried': self.handed_on}
        command = [sys.executable, '-c', HAND_OVER, json.dumps(given)]
        started = ''
        try:
            done = await asyncio.to_thread(subprocess.run, command, capture_output=True, text=True, encoding='utf-8',
                                           stdin=subprocess.DEVNULL, timeout=RELEASE_LIMIT)
            failed, started = done.stderr.strip() if done.returncode else None, done.stdout.strip()
        except (OSError, subprocess.TimeoutExpired) as error:
            failed = str(error)
        if failed is not None:
            sys.stderr.write(f'Could not hand session {self.session_id} on work {self.work_id} to the code on disk: '
                             f'{failed}\n')
            return False
        sys.stderr.write(f'Session {self.session_id} on work {self.work_id} handed over: {started}\n')
        return True


async def closed(probe: Session) -> None:
    """End an agent started only to be asked something: its process group, its connection and what it read."""
    try:
        await probe.end('asked and closed')
    finally:
        pending = tuple(probe.tasks)
        for task in pending:
            task.cancel()
        await asyncio.gather(*pending, return_exceptions=True)


def asked(ctx: Context, store: Store, agent: str, purpose: str) -> Session:
    """A session object for an agent started only to be asked something, P199 and P031: no ticket, no MCP server
    and no prompt, so no tokens are spent and nothing is written to any thread."""
    probe = Session(ctx, store, None, agent, argv(start_command(ctx, agent)), prep=True, system=True,
                    work_id=f'{purpose}-{secrets.token_hex(8)}')
    probe.echo = False  # its stderr is the tail of a refusal, not the person's terminal
    probe.probe = True
    return probe


async def prime(ctx: Context, store: Store, agent: str) -> dict[str, Any]:
    """`dispatch options agent=<agent> prime=true`: start the agent, make one session in the project's folder with no MCP
    server, keep what session/new answered, its settings, in the catalog, close the session where the agent offers
    session/close and delete it where it offers session/delete, and end the agent. No prompt is sent."""
    probe = asked(ctx, store, agent, 'prime')
    try:
        await probe.open_agent({})
        made = await asyncio.wait_for(probe.conn.new_session(cwd=probe.folder, mcp_servers=[]), START_LIMIT)
        probe.session_id = str(made.session_id)
        probe.apply(made)
        await probe.remember()
        await probe.close_session()
        # Deleted where the agent offers session/delete, so the throwaway session is not left in the person's own
        # session list in Claude Code or Codex.
        if probe.acp['capabilities'].get('delete') and (raw := probe.raw()) is not None:
            with contextlib.suppress(Exception):
                await asyncio.wait_for(raw.send_request('session/delete', {'sessionId': probe.session_id}), END_LIMIT)
        return {'agent': agent, 'settings': probe.settings()}
    except acp.RequestError as error:
        if error.code == AUTH_REQUIRED:
            raise Stop(f'{probe.name} needs a login before it makes a session.',
                       f'metaform dispatch login {agent}') from None
        raise Stop(f'{probe.name} refused a session: {error}.', 'metaform dispatch agents') from None
    except (OSError, TimeoutError, ValueError) as error:
        last = probe.tail()
        raise Stop(f'{probe.name} did not start: {error}' + (f'; its last stderr: {last}' if last else ''),
                   'metaform dispatch agents') from None
    finally:
        await closed(probe)


async def logged_in(ctx: Context, store: Store, agent: str) -> bool | None:
    """Whether the agent is logged in now, asked of a freshly started agent as ACP's terminal authentication says to
    after a terminal login: its authStatus push when it advertises one, or else whether session/new answers rather than
    refusing with auth_required, the session then closed and deleted. None when it cannot be told."""
    probe = asked(ctx, store, agent, 'login')
    try:
        await probe.open_agent({})
        if probe.acp['capabilities'].get('auth_status'):
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(probe_status(probe), 5.0)
            status = cast(dict[str, Any] | None, probe.acp['auth'])
            if status is not None:
                return status.get('kind') != 'none'
        try:
            made = await asyncio.wait_for(probe.conn.new_session(cwd=probe.folder, mcp_servers=[]), START_LIMIT)
        except acp.RequestError as error:
            return False if error.code == AUTH_REQUIRED else None
        probe.session_id = str(made.session_id)
        await probe.close_session()
        if probe.acp['capabilities'].get('delete') and (raw := probe.raw()) is not None:
            with contextlib.suppress(Exception):
                await asyncio.wait_for(raw.send_request('session/delete', {'sessionId': probe.session_id}), END_LIMIT)
        return True
    except (OSError, TimeoutError, ValueError):
        return None
    finally:
        await closed(probe)


async def probe_status(probe: Session) -> None:
    """Until the agent pushes its login state, `ext_notification`; its caller bounds the wait."""
    await probe.auth_heard.wait()


async def login(ctx: Context, agent: str, method: str | None) -> dict[str, Any]:
    """`dispatch login <agent> [method=<id>]`, the person's own: the agent's auth methods from initialize, ACP's
    authentication#auth-methods. The agent is asked as a client that can run a terminal login, so it lists every
    method it has. An `agent` method is run with authenticate, the agent doing the login itself; a `terminal` method
    runs the agent's own command with the method's arguments and environment in this terminal, and is refused with
    the reason when there is none; once it ends, the agent is started afresh and asked whether it is logged in, as
    ACP's terminal authentication says. An `env_var` method names the variables to set, which Metaform never reads.
    With no method and more than one offered, the methods are listed."""
    store = ctx.require_store()
    terminal = sys.stdin.isatty() and sys.stdout.isatty()
    probe = asked(ctx, store, agent, 'login')
    try:
        await probe.open_agent({}, terminal_login=True)
        methods = cast(list[dict[str, Any]], probe.acp['auth_methods'])
        listed = [{key: one.get(key) for key in ('id', 'name', 'description', 'type')} for one in methods]
        if not methods:
            return {'agent': agent, 'state': 'no login offered', 'methods': [],
                    'said': f'{probe.name} offers no login through ACP; it uses the login of its own command.'}
        if method is None and len(methods) > 1:
            return {'agent': agent, 'state': 'choose a method', 'methods': listed,
                    'next': f'metaform dispatch login {agent} method=<id>'}
        chosen = methods[0] if method is None else next((one for one in methods if one.get('id') == method), None)
        if chosen is None:
            raise Stop(f'{probe.name} offers no login method {method}; it offers '
                       f'{", ".join(str(one.get("id")) for one in methods)}.', f'metaform dispatch login {agent}')
        kind = str(chosen.get('type') or 'agent')
        if kind == 'env_var':
            names = [str(cast(dict[str, Any], one).get('name')) for one in cast(list[Any], chosen.get('vars') or [])]
            return {'agent': agent, 'state': 'set the variables', 'method': chosen.get('id'), 'vars': names,
                    'link': chosen.get('link'),
                    'said': f'Set {", ".join(names)} in the environment Metaform starts {probe.name} from.'}
        if kind == 'terminal':
            if not terminal:
                raise Stop(f'{probe.name}\'s login {chosen.get("id")} runs in a terminal, and this has none; run this '
                           'command in a terminal.', f'metaform dispatch login {agent} method={chosen.get("id")}')
            await closed(probe)  # the agent's own login runs as a process of its own, then it is started anew
            env = {**agent_environment(), **{str(key): str(value) for key, value in
                                            cast(dict[str, Any], chosen.get('env') or {}).items()}}
            done = await asyncio.to_thread(subprocess.run, [*probe.command, *[str(one) for one in
                                                                             cast(list[Any], chosen.get('args') or [])]],
                                           cwd=probe.folder, env=env, check=False)
            now = await logged_in(ctx, store, agent)
            state = ('logged in' if now else 'not logged in yet' if now is False else
                     'the login ended; whether it took could not be told') if done.returncode == 0 else \
                f'the login ended with exit code {done.returncode}'
            return {'agent': agent, 'method': chosen.get('id'), 'state': state, 'logged_in': now}
        await asyncio.wait_for(probe.conn.authenticate(method_id=str(chosen['id'])), LOGIN_LIMIT)
        return {'agent': agent, 'method': chosen.get('id'), 'state': 'logged in', 'logged_in': True}
    except acp.RequestError as error:
        raise Stop(f'{probe.name} did not log in: {error}.', f'metaform dispatch login {agent}') from None
    except TimeoutError:
        raise Stop(f'{probe.name}\'s login did not finish within {int(LOGIN_LIMIT)} seconds.',
                   f'metaform dispatch login {agent}') from None
    finally:
        await closed(probe)
