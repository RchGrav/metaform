"""Help text: one record per command and switch, rendered two ways.

`metaform help <thing>` renders the man page. `<command> --help` renders the
syntax only. The indexes list every command and switch.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from . import __version__, settings


@dataclass(frozen=True)
class Command:
    name: str
    summary: str
    usage: tuple[str, ...]
    switches: tuple[tuple[str, str], ...] = ()
    description: str = ''
    details: str = ''
    examples: tuple[tuple[str, str], ...] = ()
    see_also: tuple[str, ...] = ()
    owner: str = 'chassis'


@dataclass(frozen=True)
class Switch:
    name: str
    summary: str
    details: str = ''
    used_by: tuple[str, ...] = field(default=())


COMMANDS: dict[str, Command] = {}
SWITCHES: dict[str, Switch] = {}


def command(record: Command) -> Command:
    COMMANDS[record.name] = record
    return record


def switch(record: Switch) -> Switch:
    SWITCHES[record.name] = record
    return record


def setting_switches() -> tuple[tuple[str, str], ...]:
    return tuple((item.switch + ('' if item.kind == 'bool' else ' <value>'), item.help)
                 for item in sorted(settings.SCHEMA.values(), key=lambda item: item.switch))


def _rows(pairs, indent=2):
    pairs = list(pairs)
    if not pairs:
        return []
    width = max(len(left) for left, _ in pairs)
    return [' ' * indent + f'{left:<{width}}  {right}'.rstrip() for left, right in pairs]


def _switches_of(record: Command):
    rows = list(record.switches)
    if record.name == 'set':
        rows = list(setting_switches()) + rows
    if record.name == 'unset':
        rows = [(item.switch, item.help) for item in sorted(settings.SCHEMA.values(), key=lambda item: item.switch)] + rows
    return rows


def syntax(name: str) -> str:
    record = COMMANDS[name]
    lines = ['Usage: ' + record.usage[0]] + ['       ' + usage for usage in record.usage[1:]]
    rows = _switches_of(record) + [('-h, --help', 'Show this syntax.')]
    return '\n'.join(lines + [''] + _rows(rows)) + '\n'


def page(name: str) -> str:
    record = COMMANDS[name]
    lines = [f'{record.name} — {record.summary}', '']
    if record.description:
        lines += [record.description, '']
    lines += ['Usage'] + ['  ' + usage for usage in record.usage] + ['']
    rows = _switches_of(record)
    if rows:
        lines += ['Switches'] + _rows(rows) + ['']
    if record.details:
        lines += ['Details', '  ' + record.details, '']
    if record.examples:
        lines += ['Examples']
        for example, meaning in record.examples:
            lines += ['  ' + example, '    ' + meaning]
        lines += ['']
    if record.see_also:
        lines += ['See also: ' + ', '.join(record.see_also)]
    return '\n'.join(lines).rstrip() + '\n'


def switch_page(name: str) -> str:
    setting = next((item for item in settings.SCHEMA.values() if item.switch == name), None)
    if setting is not None:
        lines = [f'{name} — {setting.help}', '']
        if setting.details:
            lines += [setting.details, '']
        lines += ['Usage', f'  metaform set {name}' + ('' if setting.kind == 'bool' else ' <value>'),
                  f'  metaform unset {name}', '']
        options = setting.options() if setting.kind == 'select' else []
        if setting.kind == 'select':
            lines += ['Choices: ' + (', '.join(options) if options else 'none yet'), '']
        lines += [f'Owner: {setting.owner}. Kind: {setting.kind}. Applies to: '
                  + ('this folder' if setting.scope == 'folder' else 'everywhere') + '.']
        return '\n'.join(lines) + '\n'
    record = SWITCHES[name]
    lines = [f'{name} — {record.summary}', '']
    if record.details:
        lines += [record.details, '']
    if record.used_by:
        lines += ['Used by: ' + ', '.join(record.used_by)]
    return '\n'.join(lines).rstrip() + '\n'


def known_switch(name: str) -> bool:
    return name in SWITCHES or any(item.switch == name for item in settings.SCHEMA.values())


def overview() -> str:
    return '\n'.join([
        f'Metaform {__version__} — gives agents a project\'s purpose before they work on it.',
        '',
        'Common commands',
        *_rows([('metaform', 'Show status: home, folder, project.'),
                ('metaform add project <id> <path>', 'Register a project.'),
                ('metaform config', 'Open the settings screen.'),
                ('metaform set --<setting> <value>', 'Save a setting.')]),
        '',
        'Tips:',
        '  - start here: metaform help intro',
        "  - run 'metaform help commands' for an index of all commands",
        "  - run 'metaform help switches' for all switches",
        "  - run 'metaform config --show' to inspect your saved defaults.",
    ]) + '\n'


INTRO = '''intro — What Metaform is and how to start.

Metaform keeps a functional map of a project: what each part is for, who
receives what it does, and how it does it. Agents read the map before they
work, so they start from the project's purpose instead of rebuilding it.

All data lives in the Metaform home. A project is a folder you register. Run
metaform inside that folder and Metaform works on that project.

Start
  metaform add project <id> <path>   Register a project.
  metaform                           Check the status.
  metaform config                    Review the settings.

Commands are verbs, switches change how a command runs, and the words after a
command name what it acts on.
'''


def commands_index() -> str:
    rows = [(record.name, record.summary) for record in sorted(COMMANDS.values(), key=lambda item: item.name)]
    return '\n'.join(['Commands', *_rows(rows), '', "Use 'metaform help <command>' for details."]) + '\n'


def switches_index() -> str:
    rows = [(item.switch, item.help) for item in settings.SCHEMA.values()]
    rows += [(record.name, record.summary) for record in SWITCHES.values()]
    rows.sort()
    return '\n'.join(['Switches', *_rows(rows), '', "Use 'metaform help <switch>' for details."]) + '\n'
