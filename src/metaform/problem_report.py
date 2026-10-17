"""A tester's problem report: one zip that holds what Rich needs to see a problem, written in one step, BASE-045.

`metaform report` and the page's "Report a problem" item both build it here. It holds the tester's one line, the
versions, the tails of the logs and the errors found in them, the settings in force, and, from the page, the browser
and its console errors. Every text in it is scrubbed of secrets first, keeping the last two characters of each. The
project's own files go in only when the tester asks. Nothing is ever sent: the tester sends the file.
"""
from __future__ import annotations

import io
import json
import os
import platform
import re
import sys
import tempfile
import zipfile
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from . import __version__, archive, home, loader, settings
from .data import Store, StoreError

SEND_TO = 'Send this file to rchgrav on Discord.'
LOG_LINES = 400  # the last lines kept of each log
LOG_BYTES = 256 * 1024  # read from the end of a log, so a large one is never read whole
RUNNER_LOGS = 10  # the newest dispatch runner logs of this home's agents kept
ERRORS = 60  # the most recent errors kept in errors.txt
MASK = '****'

# A name that says its value is a secret: a key, a token, a password, a phone number and the like.
SECRET_NAME = re.compile(r'api[_-]?key|access[_-]?key|private[_-]?key|secret|token|passw|pwd|credential|cookie|'
                         r'authorization|auth[_-]|nonce|phone|_sid\b|^key$', re.IGNORECASE)
# The name of an environment variable, such as OPENAI_API_KEY: a setting that names where a secret is kept, not one.
VARIABLE = re.compile(r'[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+')
# A value that is a secret whatever it is called.
SECRET_VALUES = (
    re.compile(r'\b(?:sk|pk|rk)-[A-Za-z0-9_-]{12,}'),  # OpenAI, Anthropic, OpenRouter and Stripe keys
    re.compile(r'\bgh[pousr]_[A-Za-z0-9]{20,}'),  # GitHub tokens
    re.compile(r'\bgithub_pat_[A-Za-z0-9_]{20,}'),
    re.compile(r'\bglpat-[A-Za-z0-9_-]{20,}'),  # GitLab tokens
    re.compile(r'\bxox[abprs]-[A-Za-z0-9-]{10,}'),  # Slack tokens
    re.compile(r'\bAKIA[0-9A-Z]{16}\b'),  # AWS access keys
    re.compile(r'\bAIza[0-9A-Za-z_-]{30,}'),  # Google API keys
    re.compile(r'\beyJ[\w-]{8,}\.[\w-]{8,}\.[\w-]{8,}'),  # JSON web tokens
    re.compile(r'(?<=://)[^/\s:@]+:[^/\s@]+(?=@)'),  # a user and password in an address, https://user:pw@host
)
# A secret named beside its value: `token=...`, `"api_key": "..."`, `Authorization: Bearer ...`.
NAMED_SECRET = re.compile(r'(?P<name>[\w.-]*(?:api[_-]?key|access[_-]?key|private[_-]?key|secret|token|passw|pwd|'
                          r'credential|cookie|authorization|auth[_-]|nonce|_sid)[\w.-]*)'
                          r'(?P<between>["\']?\s*[:=]\s*["\']?(?:Bearer\s+|Basic\s+)?)'
                          r'(?P<value>[^\s"\'&,;<>]{4,})', re.IGNORECASE)
BEARER = re.compile(r'(?P<between>\bBearer\s+)(?P<value>[A-Za-z0-9._~+/=-]{8,})')
# A phone number: one written to the international plan, +15551234567, or as (555) 123-4567 and 555-123-4567.
PHONE = re.compile(r'\+\d[\d ().-]{6,}\d|\(\d{3}\)\s?\d{3}[ .-]\d{4}\b|\b\d{3}[.-]\d{3}[.-]\d{4}\b')
# A line that says something went wrong, in a log.
ERROR_LINE = re.compile(r'Traceback \(most recent call last\)|\b\w*(?:Error|Exception)\b|\bfailed\b|\bFATAL\b|'
                        r'\bCRITICAL\b|\bCould not\b|\bunhandled\b')


def masked(value: str) -> str:
    """A secret with all but its last two characters hidden; a phone number keeps its last two digits."""
    if PHONE.fullmatch(value.strip()):
        digits = re.sub(r'\D', '', value)
        return MASK + digits[-2:]
    return MASK + value[-2:] if len(value) > 2 else MASK


def known_secrets(rows: Iterable[dict[str, Any]]) -> set[str]:
    """The secrets this process can name: the values of the environment and the settings whose names say secret."""
    found = {value for name, value in os.environ.items() if SECRET_NAME.search(name) and len(value) >= 6}
    for row in rows:
        if secret_setting(row):
            values = row['value'] if isinstance(row.get('value'), list) else [row.get('value')]
            found |= {str(item) for item in values
                      if item is not None and len(str(item)) >= 6 and not VARIABLE.fullmatch(str(item))}
    return found


def secret_setting(row: dict[str, Any]) -> bool:
    """A setting that may hold a secret: free text or a list, named as a secret. A choice, a number or a switch is
    one of the values its declaration lists, never a secret."""
    return row.get('kind') in ('text', 'list') and bool(SECRET_NAME.search(str(row.get('key', ''))))


def scrub(text: str, secrets: Iterable[str] = ()) -> str:
    """The text with every secret it holds masked: those named, those of a known shape, and phone numbers."""
    for secret in sorted(set(secrets), key=len, reverse=True):
        text = text.replace(secret, masked(secret))
    for pattern in SECRET_VALUES:
        text = pattern.sub(lambda found: masked(found.group(0)), text)
    text = NAMED_SECRET.sub(lambda found: found['name'] + found['between'] + masked(found['value']), text)
    text = BEARER.sub(lambda found: found['between'] + masked(found['value']), text)
    return PHONE.sub(lambda found: masked(found.group(0)), text)


def _setting_value(secret: bool, value: Any, secrets: set[str]) -> Any:
    """A setting's value as the report shows it: masked whole when it may hold a secret, unless it is the name of
    the environment variable that holds one, and scrubbed otherwise."""
    if isinstance(value, list):
        return [_setting_value(secret, item, secrets) for item in cast(list[Any], value)]
    if value is None or isinstance(value, bool | int | float):
        return value
    text = str(value)
    return masked(text) if secret and text and not VARIABLE.fullmatch(text) else scrub(text, secrets)


def _tail(path: Path) -> str:
    """The last `LOG_LINES` lines of a log, read from its end."""
    with path.open('rb') as log:
        log.seek(0, os.SEEK_END)
        size = log.tell()
        log.seek(max(0, size - LOG_BYTES))
        data = log.read()
    lines = data.decode('utf-8', errors='replace').splitlines()
    if size > LOG_BYTES:
        lines = lines[1:]  # the first line read from the middle of a file is cut
    return '\n'.join(lines[-LOG_LINES:]) + '\n'


def agent_work() -> set[str]:
    """The work ids of every agent session this home's projects recorded: the tickets, intakes and conversations its
    dispatch runners worked, kept in each project's own store, and those its metaforms still hold from before."""
    found: set[str] = set()
    for project in home.projects():
        try:
            with Store(project.project_id, module='dispatch').tables(write=False) as tx:
                found |= {str(row['work_id']) for row in tx.rows('agent_sessions', limit=0).results}
        except StoreError:  # dispatch is off there, or never ran
            pass
        for base in home.bases(project.project_id):
            try:
                with Store(project.project_id, base=base.id, module='dispatch').tables(write=False) as tx:
                    found |= {str(row['work_id']) for row in tx.rows('sessions', limit=0).results}
            except StoreError:
                continue
    return found


def logs() -> dict[str, Path]:
    """The logs worth reading, by their name in the report: every log the home's run folder and its other folders
    keep, such as the web server's `run/web.log`, and the newest dispatch runner logs in the system's temporary
    folder of this home's own agents. That folder is shared by every Metaform home on the machine, and a runner's
    log is named for its work id alone, `metaform-dispatch-[<kind>-]<work id>.log`, so only the ids this home's
    sessions recorded are taken. The projects folder is a project's own and is left out."""
    root = home.home()
    found: dict[str, Path] = {}
    if (root / 'run').is_dir():
        for path in sorted((root / 'run').rglob('*.log')):
            found['logs/' + path.relative_to(root).as_posix()] = path
    if root.is_dir():
        for folder in sorted(entry for entry in root.iterdir() if entry.is_dir() and entry.name not in ('run',
                                                                                                    'projects')):
            for path in sorted(folder.glob('*.log')):
                found['logs/' + path.relative_to(root).as_posix()] = path
    own = agent_work()
    runners = sorted((path for path in Path(tempfile.gettempdir()).glob('metaform-dispatch-*.log')
                      if _work_of(path) & own), key=_modified, reverse=True)
    for path in runners[:RUNNER_LOGS]:
        found[f'logs/dispatch/{path.name}'] = path
    return found


def _work_of(path: Path) -> set[str]:
    """The work ids a runner log's name can hold: all after `metaform-dispatch-`, or that without its kind."""
    named = path.name[len('metaform-dispatch-'):-len('.log')]
    return {named, named.split('-', 1)[-1]}


def _modified(path: Path) -> float:
    try:
        return path.stat().st_mtime
    except OSError:
        return 0.0


def errors(tails: dict[str, str]) -> list[str]:
    """The errors the logs hold, each with the lines that follow it, such as a traceback, under the log's name."""
    found: list[tuple[str, list[str]]] = []
    for name, text in tails.items():
        lines = text.splitlines()
        index = 0
        while index < len(lines):
            if not ERROR_LINE.search(lines[index]):
                index += 1
                continue
            block = [lines[index]]
            traceback = 'Traceback' in lines[index]
            index += 1
            while index < len(lines) and len(block) < 40:
                line = lines[index]
                if line[:1].isspace() or line.startswith('Traceback'):  # the web log stamps only an entry's first line
                    traceback = traceback or line.startswith('Traceback')
                    block.append(line)
                    index += 1
                    continue
                if traceback:
                    block.append(line)  # the exception's own line ends a traceback
                    index += 1
                break
            found.append((name, block))
    return [f'{name}:\n' + '\n'.join(block) for name, block in found[-ERRORS:]]


def system(browser: str | None = None) -> dict[str, Any]:
    """The versions: Metaform's and its modules', the system's, Python's and the browser's when the page asks."""
    modules = [{'id': item.id, 'state': 'error' if item.problem else ('on' if item.enabled else 'off'),
                'place': item.place, **({'problem': item.problem} if item.problem else {})}
               for item in loader.discover()]
    return {'metaform': __version__, 'os': platform.platform(), 'machine': platform.machine(),
            'python': sys.version.replace('\n', ' '), 'python_executable': sys.executable,
            'browser': browser or '', 'modules': modules}


def _name(now: datetime) -> str:
    return f'metaform-report-{now.strftime("%Y%m%dT%H%M%SZ")}.zip'


def build(folder: Path, description: str, *, files: bool = False, browser: str | None = None,
          console: Iterable[str] = ()) -> tuple[str, bytes, list[str]]:
    """The report's file name, its bytes, and what it holds, one line each. `folder` is where the tester works:
    its settings are the ones in force, and its project's files go in when `files` is true."""
    now = datetime.now(UTC)
    rows = settings.describe(folder)
    secrets = known_secrets(rows)
    project = home.folder_project(folder)
    record = home.project(project) if project else None
    about = system(browser)
    tails: dict[str, str] = {}
    for name, path in logs().items():
        try:
            tails[name] = scrub(_tail(path), secrets)
        except OSError as error:
            tails[name] = f'{path} could not be read: {error.strerror or error}\n'
    found = errors(tails)
    console_lines = [scrub(str(line), secrets) for line in console]
    held: list[str] = ['report.txt: what went wrong, the versions and what this file holds',
                       'system.json: the versions, the system and the modules',
                       'settings.txt: the settings in force here, every secret masked',
                       f'errors.txt: {len(found)} recent errors found in the logs']
    held += [f'{name}: its last {LOG_LINES} lines' for name in tails]
    if console_lines:
        held.append(f'page/console.txt: {len(console_lines)} console errors from the page')
    project_files: dict[str, tuple[bytes, str]] = {}
    files_said = "The project's own files are not included."
    if files and record is not None:
        project_files = archive.project_files(Path(record.path))
        files_said = f"The project's own files are included under project/: {len(project_files)} files."
        held.append(f'project/: the {len(project_files)} files of the project {project}, asked for by the tester')
    elif files:
        files_said = "The project's own files were asked for, but this folder is no registered project's."
    settings_text = ''.join(
        f'{row["switch"]} = '
        f'{json.dumps(_setting_value(secret_setting(row), row["value"], secrets), ensure_ascii=False)}'
        f'  ({row["state"]}{", from " + str(row["from"]) if row.get("from") else ""})\n' for row in rows)
    modules = ', '.join(f'{module["id"]} ({module["state"]})' for module in about['modules'])
    report = '\n'.join([
        'Metaform problem report',
        f'Made: {now.isoformat(timespec="seconds")}',
        '',
        'What went wrong:',
        scrub(description.strip(), secrets),
        '',
        f'Metaform: {about["metaform"]}',
        f'System: {about["os"]} ({about["machine"]})',
        f'Python: {about["python"]}',
        f'Browser: {about["browser"] or "not used; made with metaform report"}',
        f'Project: {project or "none here"}',
        f'Modules: {modules}',
        '',
        files_said,
        'Nothing in this file was sent anywhere. ' + SEND_TO,
        '',
        'This file holds:',
        *(f'  {line}' for line in held),
        '']) + '\n'
    data = io.BytesIO()
    with zipfile.ZipFile(data, 'w', zipfile.ZIP_DEFLATED) as zipped:
        zipped.writestr('report.txt', report)
        zipped.writestr('system.json', scrub(json.dumps(about, indent=2, ensure_ascii=False), secrets) + '\n')
        zipped.writestr('settings.txt', scrub(settings_text, secrets))
        zipped.writestr('errors.txt', '\n\n'.join(found) + '\n' if found else 'No errors found in the logs.\n')
        for name, text in tails.items():
            zipped.writestr(name, text)
        if console_lines:
            zipped.writestr('page/console.txt', '\n'.join(console_lines) + '\n')
        for path, (contents, _mode) in sorted(project_files.items()):
            zipped.writestr(f'project/{path}', contents)
    return _name(now), data.getvalue(), held


def write(folder: Path, description: str, *, files: bool = False, into: Path | None = None) -> tuple[Path, list[str]]:
    """The report written into `into`, the folder by default, under a name no file there has yet."""
    name, data, held = build(folder, description, files=files)
    target_folder = into or folder
    target = target_folder / name
    number = 1
    while target.exists():
        number += 1
        target = target_folder / name.replace('.zip', f'-{number}.zip')
    with os.fdopen(os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'wb') as written:
        written.write(data)
    return target, held
