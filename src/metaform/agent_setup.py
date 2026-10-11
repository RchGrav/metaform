"""Global instruction pointers and passive harness reminders, MCP-036.

Prepare every edit before setup changes anything. The installer owns previews
and backups, and this module preserves all text and settings outside its additions.
"""
from __future__ import annotations

import hashlib
import json
import os
import shlex
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from . import prompt_files, settings
from .errors import Stop

BEGIN = b'<!-- metaform:global:begin -->'
END = b'<!-- metaform:global:end -->'
DIGEST = b'<!-- metaform:global:sha256:'
HOOK_MARK = ' # metaform-work-reminder'
TOOLS = ('claude', 'codex', 'gemini')


@dataclass(frozen=True)
class Change:
    path: Path
    before: bytes | None
    after: bytes
    description: str

    def write(self) -> None:
        current = self.path.read_bytes() if self.path.exists() else None
        if current != self.before:
            raise Stop(f'{self.path} changed after the preview; Metaform left it as it is.',
                       'metaform help provision')
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_name(f'.{self.path.name}.metaform-{os.getpid()}')
        try:
            temporary.write_bytes(self.after)
            if self.path.exists():
                shutil.copymode(self.path, temporary)
            os.replace(temporary, self.path)
        finally:
            temporary.unlink(missing_ok=True)


def pointer_block() -> bytes:
    payload = prompt_files.chassis('global_instructions').encode('utf-8') + b'\n'
    checksum = hashlib.sha256(payload).hexdigest().encode('ascii')
    return BEGIN + b'\n' + DIGEST + checksum + b' -->\n' + payload + END + b'\n'


def _installed_pointer(content: bytes, path: Path) -> bytes | None:
    """Verify ownership against installed bytes, so a prompt revision never looks like a user edit."""
    if BEGIN not in content and END not in content:
        return None
    if content.count(BEGIN) == content.count(END) == 1:
        start, end = content.index(BEGIN), content.index(END)
        # An editor that turned the file's line endings to CRLF, as Windows editors do, has not edited the block.
        middle = content[start + len(BEGIN):end].replace(b'\r\n', b'\n')
        if middle.startswith(b'\n' + DIGEST):
            marker, _, payload = middle[1:].partition(b'\n')
            intact = marker == DIGEST + hashlib.sha256(payload).hexdigest().encode('ascii') + b' -->'
        else:
            # Earlier installations carry no checksum. Only their exact current authored text is recognized.
            intact = middle == b'\n' + prompt_files.chassis('global_instructions').encode('utf-8') + b'\n'
        if start < end and intact:
            finish = end + len(END)
            finish += next((len(ending) for ending in (b'\r\n', b'\n')
                            if content[finish:finish + len(ending)] == ending), 0)
            return content[start:finish]
    raise Stop(f'{path} has an edited Metaform instruction block or malformed ownership markers; '
               'Metaform left it unchanged.', 'metaform help provision')


def _hook(tool: str) -> dict[str, Any]:
    event = 'PreToolUse' if tool == 'claude' else 'AfterTool'
    payload = json.dumps({'hookSpecificOutput': {
        'hookEventName': event, 'additionalContext': prompt_files.chassis('work_reminder')}})
    code = f'import sys; sys.stdout.write({(payload + chr(10))!r})' + HOOK_MARK
    if tool == 'claude':
        return {'matcher': '^(Agent|Task|Workflow|AskUserQuestion)$',
                'hooks': [{'type': 'command', 'command': sys.executable, 'args': ['-c', code], 'timeout': 5}]}
    # Gemini runs hooks in Bash on POSIX and PowerShell on Windows, not a direct argument vector.
    # Hex keeps JSON quotes out of native argument passing in Windows PowerShell 5.1.
    encoded = (payload + '\n').encode('utf-8').hex()
    code = f'import sys;sys.stdout.write(bytes.fromhex({encoded!r}).decode())' + HOOK_MARK
    words = [sys.executable, '-c', code]
    command = ('& ' + ' '.join("'" + word.replace("'", "''") + "'" for word in words) if os.name == 'nt'
               else shlex.join(words))
    return {'matcher': '^(invoke_agent|delegate_to_agent|ask_user)$',
            'hooks': [{'type': 'command', 'command': command, 'timeout': 5000}]}


def _ours(hook: Any) -> bool:
    if not isinstance(hook, dict):
        return False
    handler = cast(dict[str, Any], hook)
    command = handler.get('command')
    arguments: Any = handler.get('args', [])
    return (handler.get('type') == 'command' and
            ((isinstance(command, str) and HOOK_MARK in command) or
             (isinstance(arguments, list) and any(isinstance(arg, str) and HOOK_MARK in arg
                                                 for arg in cast(list[Any], arguments)))))


def _settings(path: Path, tool: str, remove: bool) -> Change | None:
    event = 'PreToolUse' if tool == 'claude' else 'AfterTool'
    before = path.read_bytes() if path.exists() else None
    try:
        parsed: Any = json.loads(before) if before is not None else {}
    except (ValueError, UnicodeError):
        parsed = None
    data = cast(dict[str, Any], parsed) if isinstance(parsed, dict) else None
    if data is None or not isinstance(data.get('hooks', {}), dict):
        raise Stop(f'{path} is not a JSON object with a hooks object; Metaform left it unchanged.',
                   'metaform help provision')
    hooks = cast(dict[str, Any], data.get('hooks', {}))
    entries: Any = hooks.get(event, [])
    if (not isinstance(entries, list) or any(not isinstance(item, dict) or
            not isinstance(cast(dict[str, Any], item).get('hooks'), list) for item in cast(list[Any], entries))):
        raise Stop(f'{path} does not hold a valid {event} hook list; Metaform left it unchanged.',
                   'metaform help provision')
    kept: list[dict[str, Any]] = []
    for entry in cast(list[dict[str, Any]], entries):
        handlers = [handler for handler in entry['hooks'] if not _ours(handler)]
        if handlers:
            kept.append({**entry, 'hooks': handlers})
        elif not entry['hooks']:
            kept.append(entry)
    if not remove:
        kept.append(_hook(tool))
    if entries == kept:
        return None
    if kept:
        hooks[event] = kept
    else:
        hooks.pop(event, None)
    if hooks:
        data['hooks'] = hooks
    else:
        data.pop('hooks', None)
    after = (json.dumps(data, indent=2) + '\n').encode('utf-8')
    return Change(path, before, after, 'remove Metaform reminder' if remove else
                  ('add passive PreToolUse reminder for Agent, Task, Workflow and AskUserQuestion' if tool == 'claude' else
                   'add passive AfterTool reminder after delegation or questioning; cannot redirect the first call'))


def prepare(tool: str, user: Path, codex: Path, *, remove: bool = False) -> list[Change]:
    """Only the three approved harnesses receive additions; Gemini supports passive context after tools."""
    if tool not in TOOLS:
        return []
    folder = codex if tool == 'codex' else user / f'.{tool}'
    filename = {'claude': 'CLAUDE.md', 'codex': 'AGENTS.md', 'gemini': 'GEMINI.md'}[tool]
    path = folder / filename
    before = path.read_bytes() if path.exists() else None
    content = before or b''
    newline = b'\r\n' if b'\r\n' in content else b'\n'  # the block takes the file's own line endings
    block = pointer_block().replace(b'\n', newline)
    installed = _installed_pointer(content, path)
    if remove:
        after = content
        if installed is not None:
            separated = newline * 2 + installed
            after = content.replace(separated if separated in content else installed, b'', 1)
    elif installed is not None:
        after = content.replace(installed, block, 1)
    elif prompt_files.chassis('global_instructions').encode('utf-8') in content:
        after = content
    else:
        after = content + (newline * 2 if content else b'') + block
    changes = [] if after == content else [Change(path, before, after, 'remove Metaform pointer' if remove else
                                                 prompt_files.chassis('global_instructions'))]
    if tool in ('claude', 'gemini'):
        remove_hook = remove or (tool == 'gemini' and settings.value('gemini_reminder', Path.cwd()) == 'off')
        if change := _settings(folder / 'settings.json', tool, remove_hook):
            changes.append(change)
    return changes


def owned(tool: str, user: Path, codex: Path) -> bool:
    """Find only Metaform's additions, so provisioning alone can be undone without unregistering MCP."""
    folder = codex if tool == 'codex' else user / f'.{tool}'
    filename = {'claude': 'CLAUDE.md', 'codex': 'AGENTS.md', 'gemini': 'GEMINI.md'}[tool]
    path = folder / filename
    if path.is_file() and BEGIN in path.read_bytes():
        return True
    hooks = folder / 'settings.json'
    if tool not in ('claude', 'gemini') or not hooks.is_file():
        return False
    try:
        data: Any = json.loads(hooks.read_bytes())
        event = 'PreToolUse' if tool == 'claude' else 'AfterTool'
        return any(_ours(handler) for entry in data.get('hooks', {}).get(event, [])
                   for handler in entry.get('hooks', []))
    except (ValueError, UnicodeError, AttributeError, TypeError):
        return False
