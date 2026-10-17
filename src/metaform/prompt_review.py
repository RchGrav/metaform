"""Review every prompt an agent reads, in a terminal: `metaform prompts review`, STORE-044.

The catalog is every element of the chassis's, skill registry's and each module's `resources/prompts.xml`,
plus the skill folders' Axiom procedures: its text, the comment
written above it in the file (its purpose), and the lines of code that load it. The list shows them; Enter shows
one whole; e opens its text in an editor. A changed text is saved as a new version in the prompt store, and then
written where the prompt lives when that can be done exactly; otherwise it becomes a packet under
artifacts/prompt-edits/ with the source file, the element, the old text and the new, so an agent told to apply the
edits knows where each came from and what to replace.
"""
from __future__ import annotations

import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import UTC, datetime
from importlib import resources
from pathlib import Path
from typing import TYPE_CHECKING

from . import home, loader, prompt_files, skills
from .data import prompts as store
from .errors import Stop

if TYPE_CHECKING:
    import curses  # the screen's window type; at run time curses is imported only where it exists

PACKETS = 'artifacts/prompt-edits'
REGISTRY = 'prompt-registry.json'  # in the Metaform home: prompts kept anywhere, registered with the review
EDITORS = ('nano', 'vi', 'vim', 'notepad')


@dataclass
class Entry:
    owner: str          # chassis or the module id
    name: str           # the element's name
    source: Path        # the prompts.xml it is in
    text: str
    purpose: str        # the comment above it, if any
    used_at: list[str] = field(default_factory=list[str])   # file:line of the code that loads it
    saved: int | None = None                           # the newest stored version number, when an edit was saved
    # an element of a prompts.xml: its text as the file holds it, `text` being the plain text the person reads and
    # edits; empty for any other prompt, whose text is its file's
    stored: str = ''

    @property
    def key(self) -> str:
        return f'{self.owner}:{self.name}'


_ELEMENT = re.compile(r'(?:<!--(?P<comment>.*?)-->\s*)?<(?P<name>[a-z_-]+)(?:\s[^>]*)?>(?P<body>.*?)</(?P=name)>', re.DOTALL)


def _entries(owner: str, source: Path, code: Path) -> list[Entry]:
    raw = source.read_text(encoding='utf-8')
    inner = raw[raw.index('<prompts>') + len('<prompts>'):raw.rindex('</prompts>')] if '<prompts>' in raw else raw
    found: list[Entry] = []
    for match in _ELEMENT.finditer(inner):
        name, text = match.group('name'), match.group('body').strip()
        purpose = ' '.join((match.group('comment') or '').split())
        # shown and edited as plain text, the characters the agent is sent, F3
        found.append(Entry(owner, name, source, prompt_files.plain(text), purpose, _uses(code, name), stored=text))
    return found


GENERIC = {  # elements every module may have, read by the chassis under the same name, MCP-029 to MCP-033
    'instructions': 'served as the module\'s instructions when it is active (MCP-029)',
    'commands': 'the module\'s slash commands (MCP-032)',
}


def _uses(code: Path, name: str) -> list[str]:
    """The code lines in the package that name the prompt, outside tests."""
    hits = [GENERIC[name]] if name in GENERIC and code.name != 'metaform' else []
    pattern = re.compile(rf"['\"]{re.escape(name)}['\"]")
    for path in sorted(code.rglob('*.py')):
        if 'tests' in path.parts or path.name == 'prompt_review.py':
            continue
        for number, line in enumerate(path.read_text(encoding='utf-8').splitlines(), 1):
            if pattern.search(line) and ('prompt' in line or 'required(' in line or 'text(' in line):
                hits.append(f'{path.relative_to(code.parent)}:{number}')
    return hits


def catalog() -> list[Entry]:
    chassis = Path(str(resources.files('metaform')))
    entries = _entries('chassis', chassis / 'resources' / 'prompts.xml', chassis)
    entries.extend(_entries('skills', chassis / 'skills' / 'resources' / 'prompts.xml', chassis))
    for one in skills.catalog():
        source = Path(str(one.folder / 'references' / 'procedure.axiom'))
        entries.append(Entry('skill', one.name, source, skills.procedure(one.name), one.description,
                             ['skills.py:procedure']))
    for item in loader.discover():
        path = Path(str(item.path))
        file = path / 'resources' / 'prompts.xml'
        if file.is_file():
            entries.extend(_entries(item.id, file, path))
    saved = {p.name: p.newest for p in store.prompts()}
    for entry in entries:
        entry.saved = saved.get(entry.key)
    for item in registered():  # prompts kept anywhere else, registered with the review
        entries.append(_registered_entry(item))
    # prompts that live only in the store: written by agents or saved from the GUI, named without an owner
    for name in sorted(n for n in saved if ':' not in n):
        version = store.prompt_version(name)
        first = version.text.splitlines()[0] if version.text else ''
        purpose = first[len('Purpose:'):].strip() if first.lower().startswith('purpose:') else ''
        entries.append(Entry('store', name, Path('(prompt store)'), version.text, purpose, [], version.number))
    return entries


# ---------------------------------------------------------------- registration

def _registry_path() -> Path:
    return Path(home.home()) / REGISTRY


def registered() -> list[dict[str, str]]:
    path = _registry_path()
    if not path.is_file():
        return []
    import json
    return list(json.loads(path.read_text(encoding='utf-8')))


def register(key: str, source: str, *, element: str = '', purpose: str = '', used: str = '') -> dict[str, str]:
    """Register a prompt kept anywhere: `key` is owner:name, `source` the file that holds it, `element` the XML
    element inside it when the file holds several, `purpose` what it is for, `used` where the system reads it."""
    import json
    if ':' not in key:
        raise Stop('A registered prompt is named owner:name, as fork:handoff.', 'metaform prompt register')
    path = Path(source).expanduser().resolve()
    if not path.is_file():
        raise Stop(f'{path} is not a file.', 'metaform prompt register')
    items = [i for i in registered() if i['key'] != key]
    item = {'key': key, 'source': str(path), 'element': element, 'purpose': purpose, 'used': used}
    items.append(item)
    home.mkdir_private(_registry_path().parent)
    home.write_private(_registry_path(), json.dumps(items, indent=1))
    return item


def _registered_entry(item: dict[str, str]) -> Entry:
    owner, name = item['key'].split(':', 1)
    source = Path(item['source'])
    text = source.read_text(encoding='utf-8') if source.is_file() else '(the source file is gone)'
    if item.get('element') and source.is_file():
        found = _pattern(item['element']).search(text)
        text = found.group(2).strip() if found else f'(no <{item["element"]}> element in the file)'
    return Entry(owner, name, source, text.strip(), item.get('purpose', ''), [item['used']] if item.get('used') else [])


# ---------------------------------------------------------------- saving an edit

def packet_folder() -> Path:
    """Under the project this folder works on, else under the folder itself."""
    from .context import project_for
    project_id = project_for(Path.cwd())
    project = home.project(project_id) if project_id is not None else None
    return (Path(project.path) if project is not None else Path.cwd()) / PACKETS


def _is_packet(where: Path) -> bool:
    """Whether `save_edit` wrote a packet rather than the prompt's own file, read by path parts on every system."""
    return where.parent.parts[-len(Path(PACKETS).parts):] == Path(PACKETS).parts


def save_edit(entry: Entry, new_text: str, folder: Path | None = None) -> Path:
    """A changed text is written where the prompt lives when that can be done exactly: the element of its prompts
    file, the registered file, or the store. The store keeps a version either way. When the source cannot be
    changed exactly, the edit becomes a packet under artifacts/prompt-edits and the caller tells the person to hand
    it to an agent. Returns the file updated, or the packet."""
    if entry.owner == 'store':  # a stored prompt is its own source: the new version is the edit
        store.save_prompt(entry.name, new_text)
        return Path('(prompt store)')
    if entry.stored:  # an element of a prompts.xml, edited as plain text: through the gate every surface saves through
        try:
            version, _ = prompt_files.save_edit(entry.key, new_text, format='xml', shipped_text=entry.stored)
        except ValueError as error:
            raise Stop(f'{error}.', f'metaform prompt {entry.key}') from None
        written = version.text  # the file's form of it, written where the prompt lives
    else:
        store.save_prompt(entry.key, new_text, format='xml')
        written = new_text
    if update_source(entry, written):
        entry.text, entry.stored = new_text, written if entry.stored else ''
        return entry.source
    return packet(entry, written, folder)


def update_source(entry: Entry, new_text: str) -> bool:
    """Write the new text into the prompt's own file, exactly between its tags or as the whole file. False when the
    element is not found once, the file is not writable, or the written file does not read back as the new text."""
    source = entry.source
    if not source.is_file() or not os.access(source, os.W_OK):
        return False
    tag = _tag(entry)
    try:
        if tag is None:
            source.write_text(new_text + '\n', encoding='utf-8')
            return source.read_text(encoding='utf-8').strip() == new_text
        raw = source.read_text(encoding='utf-8')
        pattern = _pattern(tag)
        found = pattern.findall(raw)
        if len(found) != 1:
            return False
        written = pattern.sub(lambda m: m.group(1) + new_text + m.group(3), raw, count=1)
        if _parses(raw) and not _parses(written):
            return False  # a text that would break the file, such as a bare < or &, goes to a packet instead
        source.write_text(written, encoding='utf-8')
        back = pattern.search(source.read_text(encoding='utf-8'))
        return back is not None and back.group(2).strip() == new_text
    except OSError:
        return False


def packet(entry: Entry, new_text: str, folder: Path | None = None) -> Path:
    """The edit as a packet an agent applies, for a prompt the review could not update itself."""
    folder = folder or packet_folder()
    if home.is_home_path(folder):
        home.mkdir_private(folder)
    else:
        folder.mkdir(parents=True, exist_ok=True)
    version = store.prompt_version(entry.key)
    when = datetime.now(UTC).strftime('%Y-%m-%dT%H:%M:%SZ')
    packet = folder / f'{entry.owner}--{entry.name}.md'
    text = (
        f'# Prompt edit: {entry.key}\n\n'
        f'- Source file: `{entry.source}`\n- Element: `{_element_of(entry)}`\n'
        f'- Stored as prompt `{entry.key}` version {version.number}\n- Saved: {when}\n'
        f'- Used at: {", ".join(entry.used_at) or "no code line found"}\n'
        f'- Purpose, from the comment above it: {entry.purpose or "none written"}\n\n'
        f'## Apply\n\n{_apply_of(entry)}\n\n'
        f'## Old text\n\n```\n{entry.stored or entry.text}\n```\n\n## New text\n\n```\n{new_text}\n```\n')
    if home.is_home_path(packet):
        home.write_private(packet, text)
    else:
        packet.write_text(text, encoding='utf-8')
    _index(folder)
    return packet


def _tag(entry: Entry) -> str | None:
    """The element the prompt is the text of, or None when it is a registered file's whole text."""
    if entry.owner == 'skill':
        return None  # a skill's authored procedure is one whole Axiom file
    reg = next((i for i in registered() if i['key'] == entry.key), None)
    if reg is not None:
        return reg.get('element') or None
    return entry.name


def _pattern(tag: str) -> re.Pattern[str]:
    return re.compile(rf'(<{re.escape(tag)}(?:\s[^>]*)?>)(.*?)(</{re.escape(tag)}>)', re.DOTALL)


def _parses(text: str) -> bool:
    try:
        ET.fromstring(text)
    except ET.ParseError:
        return False
    return True


def _element_of(entry: Entry) -> str:
    if entry.owner == 'skill':
        return 'the whole file'
    reg = next((i for i in registered() if i['key'] == entry.key), None)
    if reg is not None:
        return f'<{reg["element"]}>' if reg.get('element') else 'the whole file'
    return f'<{entry.name}> inside <prompts>'


def _apply_of(entry: Entry) -> str:
    tag = _tag(entry)
    if tag is None:
        return 'Replace the whole source file with the new text below, exactly as written.'
    return (f'Replace the text between `<{tag}>` and `</{tag}>` in the source file with the new text below, exactly as '
            'written. Keep any empty fill elements such as `<modules/>` the code fills in.')


def _index(folder: Path) -> None:
    packets = sorted(p for p in folder.glob('*--*.md'))
    lines = ['# Prompt edits waiting to be applied\n',
             ('Each file holds one prompt: where it lives, its old text and the new text. To apply them, tell an agent: '
              'apply every packet in artifacts/prompt-edits, then delete the packet it applied.\n')]
    lines += [f'- `{p.name}`' for p in packets]
    path = folder / 'README.md'
    if home.is_home_path(path):
        home.write_private(path, '\n'.join(lines) + '\n')
    else:
        path.write_text('\n'.join(lines) + '\n', encoding='utf-8')


# ---------------------------------------------------------------- the editor

def editors() -> list[str]:
    chosen = [os.environ.get('VISUAL'), os.environ.get('EDITOR')]
    found = [e for e in chosen if e] + [e for e in EDITORS if shutil.which(e)]
    return list(dict.fromkeys(found))


def edit_text(text: str, editor: str) -> str:
    with tempfile.NamedTemporaryFile('w', suffix='.prompt.txt', delete=False, encoding='utf-8') as f:
        f.write(text)
        path = f.name
    try:
        if os.name == 'nt':  # Windows splits its own command lines, and an editor's path often holds spaces
            subprocess.call(f'{editor} "{path}"')
        else:
            subprocess.call([*shlex.split(editor), path])
        return Path(path).read_text(encoding='utf-8').strip()
    finally:
        os.unlink(path)


# ---------------------------------------------------------------- the screens

def _wrap(text: str, width: int) -> list[str]:
    import textwrap
    out: list[str] = []
    for line in text.splitlines() or ['']:
        out.extend(textwrap.wrap(line, max(10, width)) or [''])
    return out


def run() -> None:
    entries = catalog()
    if not entries:
        raise Stop('No prompt files were found.', 'metaform status')
    try:
        import curses
    except ImportError:  # Windows without windows-curses: a plain menu
        return _plain(entries)
    curses.wrapper(_screen, entries)


def _plain(entries: list[Entry]) -> None:
    choices = editors()
    for i, e in enumerate(entries, 1):
        sys.stdout.write(f'{i:3} {e.key:40} {e.purpose[:70]}\n')
    pick = input('Number to edit, blank to quit: ').strip()
    if not pick.isdigit() or not 1 <= int(pick) <= len(entries):
        return
    entry = entries[int(pick) - 1]
    new = edit_text(entry.text, choices[0] if choices else 'notepad')
    if new != entry.text:
        where = save_edit(entry, new)
        sys.stdout.write(f'Could not update the source. Tell an agent: apply {PACKETS}/{where.name}\n'
                          if _is_packet(where) else f'Updated {where}\n')


def _screen(win: curses.window, entries: list[Entry]) -> None:
    import curses
    curses.curs_set(0)
    choices = editors() or ['nano']
    editor = 0
    at, top = 0, 0
    message = ''
    while True:
        h, w = win.getmaxyx()
        win.erase()
        win.addnstr(0, 0, f' Prompts agents read: {len(entries)}   edits saved: {sum(1 for e in entries if e.saved)}', w - 1, curses.A_REVERSE)
        rows = h - 3
        top = min(top, at)
        if at >= top + rows:
            top = at - rows + 1
        for i, e in enumerate(entries[top:top + rows]):
            line = f'{"*" if e.saved else " "} {e.owner:9} {e.name:32} {e.purpose or "(no comment above it)"}'
            win.addnstr(1 + i, 0, line, w - 1, curses.A_REVERSE if top + i == at else 0)
        bar = f' Enter view  e edit in {choices[editor]}  v/n/Tab change editor  * has a saved edit  q quit   {message}'
        win.addnstr(h - 1, 0, bar.ljust(w - 1), w - 1, curses.A_REVERSE)
        key = win.getch()
        if key in (ord('q'), 27):
            return
        if key in (curses.KEY_DOWN, ord('j')):
            at = min(len(entries) - 1, at + 1)
        elif key in (curses.KEY_UP, ord('k')):
            at = max(0, at - 1)
        elif key == curses.KEY_NPAGE:
            at = min(len(entries) - 1, at + rows)
        elif key == curses.KEY_PPAGE:
            at = max(0, at - rows)
        elif key in (ord('v'), ord('n'), 9):
            editor = _pick_editor(choices, editor, key)
        elif key in (10, 13, curses.KEY_ENTER):
            message = _detail(win, entries[at], choices, editor)
        elif key == ord('e'):
            message = _edit(win, entries[at], choices[editor])


def _pick_editor(choices: list[str], current: int, key: int) -> int:
    want = {ord('v'): ('vi', 'vim'), ord('n'): ('nano',)}.get(key)
    if want:
        for i, c in enumerate(choices):
            if c.split()[0] in want:
                return i
    return (current + 1) % len(choices)


def _edit(win: curses.window, entry: Entry, editor: str) -> str:
    import curses
    curses.endwin()
    new = edit_text(entry.text, editor)
    win.refresh()
    if new == entry.text:
        return 'unchanged'
    where = save_edit(entry, new)
    entry.saved = store.prompt_version(entry.key if entry.owner != 'store' else entry.name).number
    if _is_packet(where):
        return f'could not update the source; tell an agent: apply {PACKETS}/{where.name}'
    return f'updated {where}'


def _detail(win: curses.window, entry: Entry, choices: list[str], editor: int) -> str:
    import curses
    scroll, message = 0, ''
    while True:
        h, w = win.getmaxyx()
        win.erase()
        head = [f'{entry.key}   source {entry.source}',
                f'purpose: {entry.purpose or "(no comment above it in the file)"}',
                f'used at: {", ".join(entry.used_at) or "no code line found"}',
                f'saved edit: {"version " + str(entry.saved) if entry.saved else "none"}', '']
        body = _wrap(entry.text, w - 2)
        lines = head + body
        win.addnstr(0, 0, f' {entry.owner} / {entry.name} ', w - 1, curses.A_REVERSE)
        for i, line in enumerate(lines[scroll:scroll + h - 2]):
            win.addnstr(1 + i, 0, line, w - 1, curses.A_BOLD if i + scroll < len(head) else 0)
        bar = f' e edit in {choices[editor]}  v/n/Tab change editor  up/down scroll  Esc back   {message}'
        win.addnstr(h - 1, 0, bar.ljust(w - 1), w - 1, curses.A_REVERSE)
        key = win.getch()
        if key in (27, ord('q')):
            return message
        if key in (curses.KEY_DOWN, ord('j')):
            scroll = min(max(0, len(lines) - (h - 2)), scroll + 1)
        elif key in (curses.KEY_UP, ord('k')):
            scroll = max(0, scroll - 1)
        elif key in (ord('v'), ord('n'), 9):
            editor = _pick_editor(choices, editor, key)
        elif key == ord('e'):
            message = _edit(win, entry, choices[editor])
