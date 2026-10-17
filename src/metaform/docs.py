"""Help text, generated from the live declarations, CLI-006 to CLI-008 and CLI-029.

`metaform help <thing>` renders the page. `<thing> --help` renders the syntax
only. The indexes list every command and switch on the folder's surface.
"""
from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from . import __version__, settings

if TYPE_CHECKING:
    from .module import Module, Verb


@dataclass(frozen=True)
class Command:
    """One chassis verb's help record."""
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
    """A verb control switch: it steers a chassis command and is never a setting, D32."""
    name: str
    summary: str
    details: str = ''
    used_by: tuple[str, ...] = field(default=())


COMMANDS: dict[str, Command] = {}
SWITCHES: dict[str, Switch] = {}
ALWAYS = ('help', 'set', 'unset', 'config', 'feedback', 'report', 'read', 'instructions', 'provision')


def command(record: Command) -> Command:
    COMMANDS[record.name] = record
    return record


def switch(record: Switch) -> Switch:
    SWITCHES[record.name] = record
    return record


WIDE = 40  # a left cell longer than this goes on its own line, so one long usage never pads every row


def rows(pairs: Iterable[tuple[str, str]], indent: int = 2) -> list[str]:
    pairs = list(pairs)
    if not pairs:
        return []
    width = max((len(left) for left, _ in pairs if len(left) <= WIDE), default=WIDE)
    lines: list[str] = []
    for left, right in pairs:
        if len(left) > width:
            lines += [' ' * indent + left, *([' ' * (indent + width + 2) + right] if right else [])]
        else:
            lines.append(' ' * indent + f'{left:<{width}}  {right}'.rstrip())
    return lines


def _setting_rows(record: Command) -> list[tuple[str, str]]:
    found = list(record.switches)
    if record.name in ('set', 'unset'):
        found = [(', '.join(setting.switches) + ('' if setting.kind == 'bool' or record.name == 'unset'
                                                  else ' <value>'), setting.help)
                 for setting in settings.ordered()] + found
    return found


def syntax(name: str) -> str:
    record = COMMANDS[name]
    lines = ['Usage: ' + record.usage[0]] + ['       ' + usage for usage in record.usage[1:]]
    return '\n'.join(lines + [''] + rows(_setting_rows(record) + [('-h, --help', 'Show this syntax.')])) + '\n'


def page(name: str, *, extra_details: str = '') -> str:
    record = COMMANDS[name]
    lines = [f'{record.name}: {record.summary}', '']
    if record.description:
        lines += [record.description, '']
    lines += ['Usage'] + ['  ' + usage for usage in record.usage] + ['']
    found = _setting_rows(record)
    if found:
        lines += ['Switches'] + rows(found) + ['']
    if record.details or extra_details:
        lines += ['Details', '  ' + extra_details + record.details, '']
    if record.examples:
        lines += ['Examples']
        for example, meaning in record.examples:
            lines += ['  ' + example, '    ' + meaning]
        lines += ['']
    if record.see_also:
        lines += ['See also: ' + ', '.join(record.see_also)]
    return '\n'.join(lines).rstrip() + '\n'


def switch_page(name: str, folder: Any = None) -> str:
    found = settings.by_switch(name)
    if found is not None:
        setting = found[0]
        lines = [f'{setting.switch}: {setting.help}', '']
        if setting.details:
            lines += [setting.details, '']
        if setting.per_call:  # given on its verbs alone, never stored
            lines += ['Usage', *(f'  {call}' for call in settings.calls_of(setting)), '',
                      'Given on the call alone; it is never stored.', '']
        else:
            lines += ['Usage', f'  metaform set {setting.switch}' + ('' if setting.kind == 'bool' else ' <value>'),
                      f'  metaform unset {setting.switch}', '']
        if setting.kind == 'select' or setting.kind == 'list' and setting.choices is not None:
            try:
                options = setting.options(folder)
            except Exception:  # noqa: BLE001  a module's failing choices function leaves its help without choices
                options = []
            lines += ['Choices: ' + (', '.join(options) if options else 'none yet'), '']
        lines += [f'Owner: {setting.owner}. Kind: {setting.kind}. Applies to: '
                  + ('this folder' if setting.scope == 'folder' else 'everywhere') + '.']
        return '\n'.join(lines) + '\n'
    record = SWITCHES[name]
    lines = [f'{name}: {record.summary}', '']
    if record.details:
        lines += [record.details, '']
    if record.used_by:
        lines += ['Used by: ' + ', '.join(record.used_by)]
    return '\n'.join(lines).rstrip() + '\n'


def known_switch(name: str) -> bool:
    return name in SWITCHES or settings.by_switch(name) is not None


def overview() -> str:
    return '\n'.join([
        f"Metaform {__version__}: gives agents a project's purpose before they work on it.",
        '',
        'Common commands',
        *rows([('metaform', 'Show status: home, folder, project.'),
               ('metaform demo', 'Watch Metaform at work on a sample project.'),
               ('metaform start', 'Map the project in this folder and open it.'),
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


def intro(home: str) -> str:
    return (
        'Metaform keeps a map of what each part of a project is for: which element receives\n'
        'from which, why, and how. Agents read the map before they work, so they start from\n'
        "the project's purpose instead of rebuilding it.\n"
        '\n'
        f'All data lives in the Metaform home, {home}. Nothing is written into your projects.\n'
        '\n'
        'Start:\n'
        '  metaform start                     Map the project in this folder and open it.\n'
        '  metaform add project <id> <path>   Register a project.\n'
        '  metaform install                   Set up your AI tools to use Metaform.\n'
        '  metaform                           See status and the next step.\n')


def _here(verb: Verb) -> bool:
    from .module import on_this_system
    return 'cli' in verb.surfaces and on_this_system(verb)


def commands_index(visible: Callable[[str], bool], aliases: dict[str, list[str]] | None = None) -> str:
    """Every command shown here by owner, then each alias as one line naming its modules, CLI-039."""
    from . import loader
    found = [(record.name, record.summary) for record in COMMANDS.values()
             if visible('chassis') or record.name in ALWAYS]
    lines = ['Commands', *rows(found), '']
    for module in sorted(loader.enabled(), key=lambda item: item.id):
        if not visible(module.id):
            continue
        verbs = [(f'{module.id} {verb.name}', verb.summary) for verb in module.verbs if _here(verb)]
        lines += [f'{module.id}: {module.summary}', *rows(verbs), '']
    if aliases:
        lines += ['Aliases', *rows((name, ', '.join(modules)) for name, modules in aliases.items()), '']
    lines.append("Use 'metaform help <command>' or 'metaform help <module> <verb>' for details.")
    return '\n'.join(lines) + '\n'


def switches_index() -> str:
    found = [(setting.switch, setting.help) for setting in settings.SCHEMA.values()]
    found += [(record.name, record.summary) for record in SWITCHES.values()]
    found.sort()
    return '\n'.join(['Switches', *rows(found), '', "Use 'metaform help <switch>' for details."]) + '\n'


def module_syntax(module: Module) -> str:
    lines = [f'Usage: metaform {module.id} <verb> [nouns] [switches]', '']
    lines += rows([(verb.usage(module.id), verb.summary) for verb in module.verbs if _here(verb)])
    return '\n'.join(lines) + '\n'


def module_page(module: Module) -> str:
    lines = [f'{module.id}: {module.summary}', '', module.purpose]
    here = [verb for verb in module.verbs if _here(verb)]
    elsewhere = [verb for verb in module.verbs if 'cli' in verb.surfaces and not _here(verb)]
    if here:
        lines += ['', 'Verbs']
        lines += rows([(' '.join([verb.name, *(noun.usage() for noun in verb.nouns)]), verb.summary)
                       for verb in here])
    if elsewhere:
        lines += ['', 'Not on this system']
        lines += rows([(verb.name, f'{verb.summary} Runs on {", ".join(verb.supported_os or ())}.')
                       for verb in elsewhere])
    owned = [setting for setting in settings.SCHEMA.values() if setting.owner == module.id]
    if owned:
        lines += ['', 'Settings'] + rows([(setting.switch, setting.help) for setting in owned])
    if module.details:
        lines += ['', 'Details', '  ' + module.details]
    lines += ['', f"Use 'metaform help {module.id} <verb>' for one verb."]
    return '\n'.join(lines) + '\n'


def _verb_rows(verb: Verb) -> list[tuple[str, str]]:
    found = [(f'{noun.name}=<{noun.kind}>', noun.help) for noun in verb.nouns if not noun.required]
    for key in verb.switches:
        setting = settings.SCHEMA.get(key)
        if setting is not None:
            found.append((', '.join(setting.switches) + ('' if setting.kind == 'bool' else ' <value>'), setting.help))
    if verb.caution:
        found.append(('--confirm', 'Run it. Without this the verb only explains what it would do.'))
    return found


def _required_rows(verb: Verb) -> list[tuple[str, str]]:
    """Each noun a verb requires, as its usage line names it, with what it means, so the help that names it says
    it too."""
    return [(f'<{noun.name}>' + ('...' if noun.many else ''), noun.help) for noun in verb.nouns if noun.required]


def verb_syntax(module: Module, verb: Verb) -> str:
    lines = ['Usage: ' + verb.usage(module.id), '']
    return '\n'.join(lines + rows(_required_rows(verb) + _verb_rows(verb) + [('-h, --help', 'Show this syntax.')])) + '\n'


def verb_page(module: Module, verb: Verb) -> str:
    lines = [f'{module.id} {verb.name}: {verb.summary}', '', 'Usage', '  ' + verb.usage(module.id), '']
    required = _required_rows(verb)
    if required:
        lines += ['Nouns'] + rows(required) + ['']
    found = _verb_rows(verb)
    if found:
        lines += ['Switches'] + rows(found) + ['']
    if verb.caution:
        lines += ['Caution', '  ' + verb.caution, '']
    said = ' '.join(part for part in (verb.details, verb.person_details) if part)
    if said:
        lines += ['Details', '  ' + said, '']
    if verb.examples:
        lines += ['Examples']
        for example, meaning in verb.examples:
            lines += ['  ' + example, '    ' + meaning]
        lines += ['']
    lines.append(f'See also: metaform help {module.id}')
    return '\n'.join(lines).rstrip() + '\n'
