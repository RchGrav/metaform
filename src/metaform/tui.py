"""The settings screen: every setting the chassis and its modules declare, CLI-026.

The screen stages changes and saves them through the settings module, so the
screen, set and unset all read and write the same settings.
"""
from __future__ import annotations

import asyncio
import copy
import json
import shlex
import subprocess
import sys
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from prompt_toolkit import Application
from prompt_toolkit.data_structures import Point
from prompt_toolkit.filters import Condition, FilterOrBool
from prompt_toolkit.formatted_text import StyleAndTextTuples
from prompt_toolkit.input import Input
from prompt_toolkit.key_binding import KeyBindings, KeyPressEvent
from prompt_toolkit.layout import ConditionalContainer, Float, FloatContainer, HSplit, Layout, VSplit, Window
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.layout.dimension import Dimension
from prompt_toolkit.output import Output
from prompt_toolkit.styles import Style
from prompt_toolkit.widgets import Box, Frame, TextArea

from . import docs, home, loader, settings

Key = tuple[str, str]  # (module or chassis, setting key)


@dataclass(frozen=True)
class _Row:
    """One group in the left panel: the chassis or a discovered module."""
    id: str
    enabled: bool
    path: str


@dataclass(frozen=True)
class _Owner:
    """What a group declares: its settings, and the text its help shows."""
    settings: tuple[settings.Setting, ...]
    description: str = ''
    help: str = ''


@dataclass(frozen=True)
class _Stored:
    """One setting as the folder holds it: its value, whether it is set or glued here, the folder above it is
    inherited from, if any, and its default here, which a function of the folder may give."""
    key: str
    value: Any
    saved: bool
    glued: bool
    inherited: str | None = None
    default: Any = None


class _Backend:
    """What the screen needs: the groups, their settings and the values stored for this folder."""

    def __init__(self, folder: Path) -> None:
        self.folder = folder
        self.root = home.home()
        self.modules: dict[str, _Owner] = {}
        self.load_errors: dict[str, str] = {}

    def rows(self) -> list[_Row]:
        found = loader.discover()  # cached; only enable and disable reset it, BASE-037
        self.modules = {'chassis': _Owner(tuple(item for item in settings.SCHEMA.values()
                                                if item.owner == 'chassis' and not item.per_call),
                                          description='Settings of the chassis itself.')}
        self.load_errors = {}
        rows = [_Row('chassis', True, str(self.root))]
        for item in sorted(found, key=lambda one: one.id.casefold()):  # the chassis first, then the modules by name
            if item.module is not None:
                self.modules[item.id] = _Owner(
                    tuple(setting for setting in settings.SCHEMA.values()
                          if setting.owner == item.id and not setting.per_call),  # per-call: given on its verb
                    description=item.module.summary, help=item.module.summary)  # the summary, for people; purpose is for agents
            if item.problem:
                self.load_errors[item.id] = item.problem
            rows.append(_Row(item.id, item.enabled, str(item.path)))
        return rows

    def definition(self, owner: str) -> _Owner:
        return self.modules[owner]

    def describe(self) -> dict[str, list[_Stored]]:
        """Every group's stored settings from one description of the folder, by owner. The choices are left out: a
        setting's are read when its picker opens, so the screen's first paint never waits on a module's data."""
        found: dict[str, list[_Stored]] = {}
        for row in settings.describe(self.folder, choices=False):
            found.setdefault(str(row['owner']), []).append(
                _Stored(str(row['key']), row['value'], row['state'] in ('set', 'glued'), row['state'] == 'glued',
                        row.get('from'), row.get('default')))
        return found

    def read_choices(self, command: str) -> str:
        """Run a setting's `choices_from` command in this folder, as the command line runs it; its error, if any."""
        words = shlex.split(command)
        done = subprocess.run([sys.executable, '-m', 'metaform', *words[1:]], cwd=self.folder, capture_output=True,
                              text=True, encoding='utf-8', stdin=subprocess.DEVNULL, timeout=300, check=False)
        if done.returncode == 0:
            return ''
        said = (done.stderr + done.stdout).strip().splitlines()
        return ' '.join(line for line in said if line.startswith(('Error:', 'Next:'))) or ' '.join(said[-2:])


STYLE = Style.from_dict({
    '': 'bg:#001a45 #d9e8ff',
    'title': 'bg:#b9d8f2 #001a45 bold',
    'tabs': 'bg:#00306d #7fe9ff bold',
    'frame.border': '#7fb9ed',
    'frame.label': '#9af5ff bold',
    'selection': 'bg:#80e7ee #001528 bold',
    'selected-inactive': 'bg:#234a72 #ffffff',
    'enabled': '#80eac7',
    'disabled': '#9cacc5',
    'details': '#b9d8f2',
    'staged': '#ffd27f',
    'risky': '#ff9fb0 bold',
    'status': 'bg:#00306d #ffffff',
    'error': 'bg:#692b43 #ffffff',
    'footer': 'bg:#b9d8f2 #001a45',
    'text-area': 'bg:#d9e8ff #001a45',
    'text-area.cursor-line': 'bg:#d9e8ff #001a45',
})

HELP = ('SETUP KEYS\n\n'
        '↑ / ↓             Select a module or setting\n'
        '← / →, Tab        Switch between panels; on a choice, on/off or\n'
        '                  number setting, ← / → change its value\n'
        'Shift+Tab         Switch back\n'
        'Home / End        First / last item\n'
        'Page Up / Down    Move one page\n'
        'Enter             Open settings or edit a value; a setting with\n'
        '                  choices opens a list to pick from; a section,\n'
        '                  marked ▸, opens its settings (→ also opens it,\n'
        '                  ← and Esc go back out)\n'
        'Y / N             Confirm or refuse a choice that lets agents\n'
        '                  act without asking; ← / → never step onto one\n'
        'Space             Stage module or boolean toggle\n'
        'F2                Selected module or setting help from its\n'
        '                  declaration\n'
        'F5                Read the stored values again\n'
        'r / F9            Reset selected setting; R resets the group, or\n'
        '                  every setting a filter lists\n'
        '+ / -             Increase/decrease numeric setting\n'
        '/                 Find settings in every group by key, label or\n'
        '                  help; an empty filter shows the groups again\n'
        'P                 Preview pending changes\n'
        'S                 Save pending changes\n'
        'Esc               Close dialog, back, then exit\n'
        'F10               Save and exit\n'
        'Q / Ctrl+C        Quit (save/discard/continue)\n\n'
        'Changes are staged until saved. Folder settings apply to this folder.\n'
        'A list is typed as the command line takes it, items between commas,\n'
        'or as a JSON list when an item holds a comma. A value that has a list\n'
        'of choices is picked from it; one typed outside it is refused.\n'
        'G glues/unglues values; glued values survive reset.\n\n'
        'ROW MARKS\n\n'
        '~ staged, not saved yet    * glued    P only the person changes it\n'
        '! a risky choice: agents act without asking\n'
        '(set) set here    (inherited from <folder>)    no mark: the default\n'
        'A value too long for the panel ends in …; the details show it whole.\n'
        '\n'
        'Press Esc or F1 to close.')


def _found(found: tuple[settings.Setting, ...]) -> str:
    """How many settings a filter found, in how many groups."""
    groups = len({item.owner for item in found})
    return (f'{len(found)} setting{"" if len(found) == 1 else "s"} in {groups} group{"" if groups == 1 else "s"}')


class ChassisTUI:
    """The keyboard-driven settings screen, staging changes until they are saved, CLI-026."""

    def __init__(self, backend: _Backend, *, input: Input | None = None, output: Output | None = None) -> None:
        self.backend = backend
        self.rows: list[_Row] = []
        self.definitions: dict[str, _Owner] = {}
        self.definition_errors: dict[str, str] = {}
        self.values: dict[Key, Any] = {}
        self.saved: dict[Key, bool] = {}
        self.glued: dict[Key, bool] = {}
        self.inherited: dict[Key, str | None] = {}  # the folder above a value comes from, CLI-014
        self.defaults: dict[Key, Any] = {}  # each setting's default here, a function of the folder for some
        self.risked: dict[tuple[str, str], str | None] = {}  # (key, value): what a risky value risks, read once
        self.module_index = 0
        self.setting_index = 0
        self.panel = 'modules'
        self.busy = False
        self.editing = False
        self.edit_error = ''
        self.help_open = False
        self.module_help_open = False
        self.quit_open = False
        self.preview_open = False
        # A risky choice waits here for the person's yes before it is staged
        self.confirm_open = False
        self.confirm_target: tuple[str, settings.Setting, Any] | None = None
        self.confirm_text = ''
        self.filter_text = ''
        self.filtering = False
        self.pending_settings: dict[Key, tuple[str, Any]] = {}
        self.pending_modules: dict[str, bool] = {}
        self.pending_glue: dict[Key, bool] = {}
        self.message = 'Select a group. Edit settings, then press S to save or F10 to save and exit.'
        self.error = False
        self.exit_requested = False
        self.last_task: asyncio.Task[None] | None = None
        self._edit_target: tuple[str, settings.Setting] | None = None
        # The picker: a setting's choices to pick one of (a choice setting) or check several of (a list)
        self.picking = False
        self.pick_target: tuple[str, settings.Setting] | None = None
        self.pick_choices: list[str] = []
        self.pick_checked: set[str] = set()
        self.pick_index = 0
        self.pick_reader: str | None = None  # the command that reads the choices, while there are none but the default
        self.section: tuple[str, ...] = ()  # the section of the selected group open in the settings panel
        self.words: dict[Key, dict[str, str]] = {}  # each setting's choices in plain words, read once per refresh
        self.modules_control = FormattedTextControl(self._module_lines, focusable=True,
                                                    get_cursor_position=lambda: Point(0, self.module_index))
        self.settings_control = FormattedTextControl(
            self._setting_lines, focusable=True,
            get_cursor_position=lambda: Point(0, self.setting_index + (1 if self.section else 0)))
        self.editor = TextArea(multiline=False, wrap_lines=False)
        self.modules_window = Window(self.modules_control, wrap_lines=False, always_hide_cursor=True)
        self.settings_window = Window(self.settings_control, wrap_lines=False, always_hide_cursor=True)
        details = Window(FormattedTextControl(self._details), height=self._details_height, wrap_lines=True,
                         style='class:details')
        content = HSplit([
            Window(FormattedTextControl(lambda: f'  METAFORM  |  SETTINGS FOR {self.backend.folder}'), height=1,
                   style='class:title'),
            Window(FormattedTextControl(self._tabs), height=1, style='class:tabs'),
            VSplit([
                Frame(self.modules_window, title='Modules', width=Dimension(weight=2, min=20)),
                Frame(self.settings_window, title='Settings', width=Dimension(weight=3, min=26)),
            ], padding=1),
            Frame(details, title='Selection details'),
            Window(FormattedTextControl(lambda: self.message), height=2, wrap_lines=True,
                   style=lambda: 'class:error' if self.error else 'class:status'),
            Window(FormattedTextControl('  ↑↓ Select   ←→ Panel or value   Tab Panel   Enter Edit   Space Toggle'),
                   height=1, style='class:footer'),
            Window(FormattedTextControl('  F1 Keys  F2 Help  / Find  G Glue  r Reset  R Reset all  P Preview  '
                                        'S Save  F10 Save/Exit'), height=1, style='class:footer'),
        ])
        edit_dialog = Frame(Box(HSplit([
            Window(FormattedTextControl(self._edit_label), height=2, wrap_lines=True),
            self.editor,
            Window(FormattedTextControl(lambda: self.edit_error or 'Enter Stage change    Esc Cancel'),
                   height=2, wrap_lines=True),
        ]), padding=1), title='Edit setting', width=Dimension(preferred=66))
        self.pick_window = Window(FormattedTextControl(self._pick_lines, focusable=True,
                                                       get_cursor_position=lambda: Point(0, self.pick_index)),
                                  wrap_lines=False, always_hide_cursor=True, height=Dimension(max=16))
        pick_dialog = Frame(Box(HSplit([
            Window(FormattedTextControl(self._pick_label), height=Dimension(min=2, max=5), wrap_lines=True),
            self.pick_window,
            Window(FormattedTextControl(self._pick_keys), height=2, wrap_lines=True),
            ConditionalContainer(Window(FormattedTextControl(self._pick_about), height=Dimension(max=4),
                                        wrap_lines=True, style='class:details'),
                                 Condition(lambda: bool(self._pick_about()))),
        ]), padding=1), title='Choose', width=Dimension(preferred=72))
        self.help_text = TextArea(text=HELP, read_only=True, scrollbar=True, wrap_lines=True)
        help_dialog = Frame(self.help_text, title='Keyboard help · ↑↓ scroll',
                            width=Dimension(preferred=64), height=Dimension(preferred=26))
        quit_dialog = Frame(Box(Window(FormattedTextControl(
            'There are unsaved changes.\n\n'
            'S  Save and exit\nD  Discard and exit\nEsc  Continue editing'),
            height=7), padding=1), title='Save changes?', width=52)
        confirm_dialog = Frame(Box(Window(FormattedTextControl(
            lambda: f'{self.confirm_text}\n\nY  Yes, stage it\nN  No, keep what it is'),
            wrap_lines=True, height=Dimension(max=10)), padding=1), title='Let agents act without asking?',
            width=Dimension(preferred=64), style='class:error')
        self.preview_text = TextArea(read_only=True, scrollbar=True, wrap_lines=True)
        preview_dialog = Frame(self.preview_text, title='Pending changes · Esc closes',
                               width=Dimension(preferred=76), height=Dimension(preferred=22))
        self.module_help_text = TextArea(read_only=True, scrollbar=True, wrap_lines=True)
        module_help_dialog = Frame(self.module_help_text, title='Help · Esc closes',
                                   width=Dimension(preferred=80), height=Dimension(preferred=24))
        container = FloatContainer(content, floats=[
            Float(content=ConditionalContainer(edit_dialog, Condition(lambda: self.editing))),
            Float(content=ConditionalContainer(pick_dialog, Condition(lambda: self.picking))),
            Float(content=ConditionalContainer(help_dialog, Condition(lambda: self.help_open))),
            Float(content=ConditionalContainer(quit_dialog, Condition(lambda: self.quit_open))),
            Float(content=ConditionalContainer(confirm_dialog, Condition(lambda: self.confirm_open))),
            Float(content=ConditionalContainer(preview_dialog, Condition(lambda: self.preview_open))),
            Float(content=ConditionalContainer(module_help_dialog, Condition(lambda: self.module_help_open))),
        ])
        self.app: Application[None] = Application(layout=Layout(container, focused_element=self.modules_window),
                                                  key_bindings=self._bindings(), style=STYLE, full_screen=True,
                                                  input=input, output=output)  # redrawn on change, QUAL-015
        self.app.ttimeoutlen = .1

    def _details_height(self) -> int:
        rows = self.app.output.get_size().rows
        return 4 if rows < 26 else 6 if rows < 36 else 8

    def _tabs(self) -> str:
        return (f'  Modules ({len(self.rows)})    /    Settings       '
                f'{"Working…" if self.busy else str(self.change_count) + " pending changes"}')

    @property
    def selected(self) -> _Row | None:
        return self.rows[self.module_index] if self.rows else None

    @property
    def declared_settings(self) -> tuple[settings.Setting, ...]:
        """Every setting of the selected group, whatever its section, by name; with a filter, every setting of every
        group whose key, label or help holds its text, by group and then by name."""
        query = self.filter_text.casefold()
        if query:
            return tuple(sorted((item for definition in self.definitions.values() for item in definition.settings
                                 if query in item.key.casefold() or query in (item.label or '').casefold()
                                 or query in item.help.casefold()),
                                key=lambda item: (item.owner != 'chassis', item.owner, item.key.casefold())))
        definition = self.definitions.get(self.selected.id) if self.selected else None
        if not definition:
            return ()
        return tuple(sorted(definition.settings, key=lambda item: item.key.casefold()))

    def _name(self, setting: settings.Setting) -> str:
        """The name a setting is listed by: its label inside a section, where its section says whose it is, such as
        Mode under Claude Code; with a filter its group and key, since it may be any group's; its key elsewhere."""
        if self.filter_text:
            return f'{setting.owner}  {setting.key}'
        return (setting.label or setting.key) if self.section else setting.key

    @property
    def entries(self) -> list[settings.Setting | str]:
        """What the settings panel lists, alphabetically by the name shown: with a filter, every setting it leaves;
        else the settings in the open section and the sections inside it, each a name that opens it."""
        found = self.declared_settings
        if self.filter_text:
            return list(found)
        depth, listed = len(self.section), list[str]()
        named: list[tuple[str, settings.Setting | str]] = []
        for item in found:
            path = tuple(item.section.split('/')) if item.section else ()
            if path[:depth] != self.section:
                continue
            if len(path) == depth:
                named.append((self._name(item), item))
            elif path[depth] not in listed:
                listed.append(path[depth])
                named.append((path[depth], path[depth]))
        return [entry for _, entry in sorted(named, key=lambda pair: pair[0].casefold())]

    @property
    def current(self) -> settings.Setting | None:
        """The setting selected in the settings panel; None on a section or with none listed."""
        entries = self.entries
        entry = entries[self.setting_index] if 0 <= self.setting_index < len(entries) else None
        return entry if isinstance(entry, settings.Setting) else None

    def _open_section(self) -> bool:
        """Open the section selected in the settings panel; False when a setting is selected."""
        entries = self.entries
        entry = entries[self.setting_index] if 0 <= self.setting_index < len(entries) else None
        if not isinstance(entry, str):
            return False
        self.section, self.setting_index = (*self.section, entry), 0
        return True

    def _close_section(self) -> bool:
        """Go back out of the open section, to the row that opened it; False at the top."""
        if not self.section or self.filter_text:
            return False
        left, self.section = self.section[-1], self.section[:-1]
        self.setting_index = next((index for index, entry in enumerate(self.entries) if entry == left), 0)
        return True

    def _words(self, module: str, setting: settings.Setting) -> dict[str, str]:
        """A setting's choices in plain words, read once until the values are read again."""
        if (module, setting.key) not in self.words:
            try:
                self.words[module, setting.key] = setting.helps(self.backend.folder)
            except Exception:  # noqa: BLE001  a module's failing function leaves the choices as their values
                self.words[module, setting.key] = {}
        return self.words[module, setting.key]

    def _module_lines(self) -> StyleAndTextTuples:
        result: StyleAndTextTuples = []
        for index, row in enumerate(self.rows):
            style = 'class:enabled' if row.enabled else 'class:disabled'
            if index == self.module_index:
                style = 'class:selection' if self.panel == 'modules' else 'class:selected-inactive'
            state = 'On ' if self.pending_modules.get(row.id, row.enabled) else 'Off'
            if row.id in self.pending_modules:
                state += '*'
            elif row.enabled and row.id not in self.backend.modules:
                state = 'Err'
            result.append((style, f' {">" if index == self.module_index else " "} [{state}] {row.id}\n'))
        return result

    def _state(self, setting: settings.Setting) -> tuple[str, str | None]:
        """A setting's state as the screen holds it, staged changes counted: staged, glued, set, inherited (with the
        folder it comes from) or default."""
        identity = (setting.owner, setting.key)
        if identity in self.pending_settings or identity in self.pending_glue:
            return 'staged', None
        if self._glued(identity):
            return 'glued', None
        if self.saved.get(identity, False):
            return 'set', None
        source = self.inherited.get(identity)
        return ('inherited', source) if source else ('default', None)

    def _risk(self, setting: settings.Setting, value: Any) -> str | None:
        """What a value risks, when it is one of its setting's risky choices; read once per value until the next read.
        A default is never risky, so most rows ask nothing of their module."""
        if not setting.risky or setting.kind != 'select' or value == setting.default:
            return None
        if (setting.key, str(value)) not in self.risked:
            self.risked[setting.key, str(value)] = settings.risk(setting.key, value, self.backend.folder)
        return self.risked[setting.key, str(value)]

    def _row(self, setting: settings.Setting, width: int) -> str:
        """One setting's row, cut to the panel's width: person-only P and risky !, then staged ~ or glued *, its name
        and value, the value ending in … when cut, and where the value comes from. From the glue mark on, a row reads
        as `config --show` prints it, CLI-026 and CLI-014; an inherited value names its folder by its last part."""
        from .cli import show
        value = self._value(setting.owner, setting)
        state, source = self._state(setting)
        marks = ('P' if setting.person_only else ' ') + ('!' if self._risk(setting, value) else ' ') + \
            ('~' if state == 'staged' else '*' if self._glued((setting.owner, setting.key)) else ' ')
        note = {'set': '  (set)', 'glued': '  (glued)', 'staged': '  (staged)',
                'inherited': f'  (inherited from {Path(source or "").name or source})'}.get(state, '')
        shown = show(setting.key, value).replace('\n', '\\n')
        head = f'{marks} {self._name(setting)}: '
        room = width - len(head) - len(note)
        if len(shown) > room:
            shown = shown[:max(0, room - 1)] + '…'
        return f'{head}{shown}{note}'

    def _setting_lines(self) -> StyleAndTextTuples:
        selected = self.selected
        if selected is None:
            return [('class:disabled', '  Select a module.')]
        if not self.declared_settings:
            return [('class:disabled', '  No matching settings in any group.' if self.filter_text
                     else '  Enable and save to configure.' if selected.id not in self.backend.modules
                     else '  No matching settings.')]
        info = self.settings_window.render_info
        width = (info.window_width if info else self.app.output.get_size().columns * 3 // 5 - 4) - 2
        result: StyleAndTextTuples = []
        if self.filter_text:  # what was found, and in how many groups
            found = self.declared_settings
            result.append(('class:details', f' Found {_found(found)}: {self.filter_text}\n'))
        elif self.section:  # where the panel is, and the way back
            result.append(('class:details', f' ‹ {" / ".join(self.section)}\n'))
        for index, setting in enumerate(self.entries):
            style = ''
            if isinstance(setting, settings.Setting):
                state = self._state(setting)[0]
                style = 'class:staged' if state == 'staged' else \
                    'class:risky' if self._risk(setting, self._value(setting.owner, setting)) else ''
            if index == self.setting_index:
                style = 'class:selection' if self.panel == 'settings' else 'class:selected-inactive'
            if isinstance(setting, str):
                result.append((style, f' {">" if index == self.setting_index else " "}  {setting} ▸\n'))
                continue
            result.append((style, f'{">" if index == self.setting_index else " "}{self._row(setting, width)}\n'))
        return result

    def _details(self) -> str:
        row = self.selected
        if row is None:
            return ''
        definition = self.definitions.get(row.id)
        error = self.definition_errors.get(row.id) or self.backend.load_errors.get(row.id)
        if self.panel == 'settings' and self.entries and self.current is None:
            entry = str(self.entries[self.setting_index])
            inside = [item for item in self.declared_settings
                      if (item.section or '').split('/')[:len(self.section) + 1] == [*self.section, entry]]
            return (f'{entry}  |  {len(inside)} settings\n'
                    + ', '.join(self._name(item) if item.section == '/'.join((*self.section, entry)) else item.key
                                for item in inside[:8]) + '\nEnter or → opens it; Esc or ← goes back.')
        if self.panel == 'settings' and (setting := self.current):
            return self._setting_details(setting)
        state = 'Enabled and active' if row.id in self.backend.modules else 'Disabled'
        if row.enabled and row.id not in self.backend.modules:
            state = 'Enabled; activation failed'
        return (f'{row.id}  |  {state}\n'
                f'{error or (definition.description if definition else "")}\n'
                f'{row.path}\nSpace changes module state. Enter opens its settings.')

    def _setting_details(self, setting: settings.Setting) -> str:
        """The selected setting whole: its value, where it comes from, its default, who may change it, what a risky
        value risks, and its help, then how the command line sets and resets it."""
        from .cli import show
        identity = (setting.owner, setting.key)
        value = self._value(setting.owner, setting)
        state, source = self._state(setting)
        where = {'staged': 'staged, not saved yet', 'glued': 'set here, glued', 'set': 'set here',
                 'inherited': f'inherited from {source}', 'default': 'the default'}[state]
        about = self._words(setting.owner, setting).get(str(value))
        risked = self._risk(setting, value)
        default = self.defaults.get(identity, setting.default)
        cli = (f'{setting.switch} or {setting.negative}' if setting.type is bool
               else f'{setting.switch} VALUE')
        return '\n'.join(line for line in (
            f'{setting.owner}.{setting.key}  |  {setting.kind}  |  '
            f'{"global" if setting.scope == "global" else "this folder and below"}'
            + ('  |  only the person changes it' if setting.person_only else ''),
            f'Value: {show(setting.key, value)}  ({where})' + (f': {about}' if about else ''),
            f'Risky: {risked}' if risked else '',
            f'Default: {show(setting.key, default)}',
            setting.help,
            (f'CLI: metaform set {cli}   Reset: metaform unset {setting.switch}   '
             f'{"Glued (G unglues)" if self._glued(identity) else "G glues value"}')) if line)

    def _edit_label(self) -> str:
        if self.filtering:
            return 'Find settings in every group by key, label or help. Empty text shows the groups again.'
        if not self._edit_target:
            return ''
        module, setting = self._edit_target
        return f'{module}.{setting.key} ({setting.type.__name__})\n{setting.help}'

    async def refresh(self) -> None:
        previous = self.selected.id if self.selected else None
        # Discovery runs module start hooks; off this loop, an async one runs on a loop of its own, BASE-009. The
        # folder is described once for every group, off the loop too, so the keys keep working while it is read.
        self.rows = await asyncio.to_thread(self.backend.rows)
        try:
            described = await asyncio.to_thread(self.backend.describe)
            failed = ''
        except Exception as error:  # noqa: BLE001  the groups show why their values could not be read
            described, failed = {}, str(error)
        self.definitions = {}
        for row in self.rows:
            if row.id not in self.backend.modules:
                continue
            self.definitions[row.id] = self.backend.definition(row.id)
            if failed:
                self.definition_errors[row.id] = failed
                continue
            for item in described.get(row.id, []):
                self.values[row.id, item.key] = item.value
                self.saved[row.id, item.key] = item.saved
                self.glued[row.id, item.key] = item.glued
                self.inherited[row.id, item.key] = item.inherited
                self.defaults[row.id, item.key] = item.default
            self.definition_errors.pop(row.id, None)
        self.module_index = next((index for index, row in enumerate(self.rows) if row.id == previous), 0)
        self.words, self.risked = {}, {}
        self.setting_index = min(self.setting_index, max(0, len(self.entries) - 1))
        self.app.invalidate()

    def _focus(self, panel: str) -> None:
        self.panel = panel
        self.app.layout.focus(self.modules_window if panel == 'modules' else self.settings_window)

    def _move(self, amount: int | None = None, end: bool = False) -> None:
        if self.panel == 'modules':
            size, index = len(self.rows), self.module_index
        else:
            size, index = len(self.entries), self.setting_index
        index = max(0, min(size - 1, index + amount if amount is not None else (size - 1 if end else 0)))
        if self.panel == 'modules':
            self.module_index = index
            self.setting_index = 0
            self.section = ()
        else:
            self.setting_index = index

    def _perform(self, action: Callable[[], Awaitable[None]], message: str, *,
                 success: Callable[[], str] | None = None) -> None:
        """Run a change in the background and read the settings again after it; the screen keeps moving meanwhile,
        and only the keys that change something wait for it."""
        if self.busy:
            return
        self.busy = True
        self.error = False
        self.message = message

        async def run() -> None:
            try:
                await action()
                await self.refresh()
                self.message = success() if success else 'Applied. Changes are saved.'
            except Exception as error:  # noqa: BLE001  the failure is the screen's status line, CLI-026
                self.message = str(error)
                self.error = True
                try:
                    await self.refresh()
                except Exception as again:  # noqa: BLE001  shown after the change's own error, which comes first
                    self.message += f' The screen could not read the settings again: {again}'
            finally:
                self.busy = False
                self.app.invalidate()
                if self.exit_requested:
                    self.exit_requested = False
                    if self.change_count:
                        self.quit_open = True
                    else:
                        self.app.exit()
        self.last_task = self.app.create_background_task(run())

    @property
    def change_count(self) -> int:
        return len(self.pending_modules) + len(self.pending_settings) + len(self.pending_glue)

    def _value(self, module: str, setting: settings.Setting) -> Any:
        pending = self.pending_settings.get((module, setting.key))
        if pending:
            return copy.deepcopy(setting.default) if pending[0] == 'reset' else pending[1]
        return self.values.get((module, setting.key), setting.default)

    def _preview(self) -> str:
        lines: list[str] = []
        for module, enabled in self.pending_modules.items():
            lines.append(f'{module}: {"enable" if enabled else "disable"}')
        for (module, key), glue in self.pending_glue.items():
            lines.append(f'{module}.{key}: {"glue" if glue else "unglue"}')
        for (module, key), (action, value) in self.pending_settings.items():
            before = json.dumps(self.values.get((module, key)), ensure_ascii=False)
            after = 'default' if action == 'reset' else json.dumps(value, ensure_ascii=False)
            lines.append(f'{module}.{key}: {before} → {after}')
        return '\n'.join(lines) or 'No pending changes.'

    def _toggle_module(self) -> None:
        row = self.selected
        if row is None:
            return
        if row.id == 'chassis':
            self.message = 'The chassis is always on. Enter opens its settings.'
            return
        enabled = not self.pending_modules.get(row.id, row.enabled)
        if enabled == row.enabled:
            self.pending_modules.pop(row.id, None)
        else:
            self.pending_modules[row.id] = enabled
        self.message = 'Module change staged. S saves; P previews pending changes.'

    def _edit(self) -> None:
        row = self.selected
        if row is None or self._open_section():
            return
        setting = self.current
        if setting is None:
            return
        value = self._value(setting.owner, setting)
        if setting.type is bool:
            self._stage(setting.owner, setting, not value)
            return
        if self._open_pick(setting.owner, setting, value):
            return
        self._edit_target = (setting.owner, setting)
        self.editor.text = self._typed_form(value)
        self.editor.buffer.cursor_position = len(self.editor.text)
        self.edit_error = ''
        self.editing = True
        self.app.layout.focus(self.editor)

    @staticmethod
    def _typed_form(value: Any) -> str:
        """A value as it is typed, as the command line takes it: a list's items between commas, or JSON when an item
        holds a comma, CLI-027."""
        if isinstance(value, list):
            items = [str(item) for item in cast(list[Any], value)]
            return json.dumps(items, ensure_ascii=False) if any(',' in item for item in items) else ','.join(items)
        return str(value)

    def _refusal(self, setting: settings.Setting, value: Any) -> str:
        """Why a value cannot be stored, with its next step, as `set` would say it, the choices listed for a value
        outside them; empty when it fits, CLI-019 and CLI-026."""
        try:
            settings.checked(setting.key, value, self.backend.folder, typed=True)
        except settings.SettingError as error:
            return f'{error}' + (f' Next: {error.next_step}' if error.next_step else '')
        except Exception as error:  # noqa: BLE001  a module's failing check is said, and nothing is staged
            return str(error)
        return ''

    def _stage(self, module: str, setting: settings.Setting, value: Any) -> None:
        identity = (module, setting.key)
        if (refused := self._refusal(setting, value)) and value != self.values.get(identity, setting.default):
            self.error, self.message = True, refused
            return
        if value != self._value(module, setting) and (risked := settings.risk(setting.key, value, self.backend.folder)):
            # a choice that lets agents act without asking is staged only on the person's yes
            self.confirm_target, self.confirm_text, self.confirm_open = (module, setting, value), \
                f'{setting.key}: {value}\n{risked}', True
            return
        self._put_stage(identity, setting, value)

    def _confirm(self, yes: bool) -> None:
        target, self.confirm_open, self.confirm_target = self.confirm_target, False, None
        if yes and target is not None:
            self._put_stage((target[0], target[1].key), target[1], target[2])
        else:
            self.message = 'Not staged; the value stays as it is.'

    def _put_stage(self, identity: Key, setting: settings.Setting, value: Any) -> None:
        if value == self.values.get(identity, setting.default):
            self.pending_settings.pop(identity, None)
        else:
            self.pending_settings[identity] = ('set', value)
        self.error = False
        self.message = 'Setting staged. S saves; P previews pending changes.'

    def _reset(self, group: bool = False) -> None:
        row = self.selected
        if row is None or self.panel != 'settings' or not self.entries:
            return
        if not group and self.current is None:
            return
        if group:  # the group's settings, or with a filter every setting it found, in whichever group
            entries = self.declared_settings if self.filter_text else self.definitions[row.id].settings
        else:
            entries = (cast(settings.Setting, self.current),)
        held: list[tuple[settings.Setting, str]] = []
        for setting in entries:
            identity = (setting.owner, setting.key)
            if self._glued(identity):
                continue
            if not self.saved.get(identity, False) and (source := self.inherited.get(identity)):
                held.append((setting, source))  # held by a folder above: not this folder's to reset, CLI-014
                self.pending_settings.pop(identity, None)
                continue
            if self.saved.get(identity, False):
                self.pending_settings[identity] = ('reset', None)
            else:
                self.pending_settings.pop(identity, None)
        self.message = 'Defaults staged. S saves the change.'
        if held:
            setting, source = held[0]
            more = f' {len(held) - 1} more inherited were left too.' if len(held) > 1 else ''
            self.error = True
            self.message = (f'{setting.key} is inherited from {source}; nothing is stored here to reset.{more} '
                            f'Next: metaform unset {setting.switch} folder={source}')

    def _glued(self, identity: Key) -> bool:
        return self.pending_glue.get(identity, self.glued.get(identity, False))

    def _toggle_glue(self) -> None:
        row, setting = self.selected, self.current
        if row is None or self.panel != 'settings' or setting is None:
            return
        identity = (setting.owner, setting.key)
        glue = not self._glued(identity)
        if glue == self.glued.get(identity, False):
            self.pending_glue.pop(identity, None)
        else:
            self.pending_glue[identity] = glue
        if glue and self.pending_settings.get(identity, ('', None))[0] == 'reset':
            self.pending_settings[identity] = ('set', copy.deepcopy(setting.default))
        self.message = 'Glue change staged. Glued values survive reset. S saves.'

    def _save_changes(self, exit_after: bool = False) -> None:
        self.quit_open = False
        noted: list[str] = []

        def check() -> None:
            """Every staged value is checked before any is stored, so a save stores all of them or none, as a
            `set` of several settings does."""
            folder = self.backend.folder
            for (_, key), (action, value) in self.pending_settings.items():
                if action == 'reset':
                    settings.check_reset(key, folder)
                else:
                    settings.checked(key, value, folder, typed=True)

        def store() -> None:
            folder = self.backend.folder
            for identity, (action, value) in list(self.pending_settings.items()):
                key = identity[1]
                glue = self.pending_glue.get(identity)
                if action == 'reset':
                    settings.reset(key, folder, unglue=glue is False)
                else:
                    noted.extend(f'{key}: {message}' for message in settings.put(key, value, folder,
                                                                              glue=bool(glue)).notices)
                self.pending_settings.pop(identity)
                self.pending_glue.pop(identity, None)
            for identity, glue in list(self.pending_glue.items()):
                settings.glue(identity[1], folder, glue)
                self.pending_glue.pop(identity)
            for module, enabled in list(self.pending_modules.items()):
                loader.set_enabled(module, enabled)
                from . import install
                install.node_skill_follows(module, folder, noted.append)  # Claude Code's metaform-node follows map
                self.pending_modules.pop(module)

        async def save() -> None:
            try:
                await asyncio.to_thread(check)
            except settings.SettingError as error:
                raise settings.SettingError(f'Nothing was saved: {error}'
                                            + (f' Next: {error.next_step}' if error.next_step else '')) from None
            await asyncio.to_thread(store)  # off the loop: the screen keeps moving while the values are stored
            if exit_after:
                self.exit_requested = True
        self._perform(save, 'Saving settings and module state…',
                      success=lambda: ' '.join(['Applied. Changes are saved.', *noted]))

    def _apply_edit(self) -> None:
        if self.filtering:
            self.filter_text = self.editor.text.strip()
            self.filtering = self.editing = False
            self.setting_index = 0
            self.section = ()
            self._focus('settings')
            found = self.declared_settings if self.filter_text else ()
            self.message = (f'Found {_found(found)} for {self.filter_text}. / changes it; an empty one shows the '
                            'groups again.'
                            if self.filter_text else 'Showing the groups again.')
            return
        if self._edit_target is None:
            return
        module, setting = self._edit_target
        text = self.editor.text
        try:  # read as `set` reads it, CLI-027; a list may also be given as JSON, for an item holding a comma
            if setting.kind == 'list' and text.strip().startswith('['):
                value: Any = json.loads(text)
                if not isinstance(value, list):
                    raise ValueError('A list in JSON is written as ["one", "two"].')
            else:
                value = text if setting.type is str else settings.parse(setting, text.strip(), self.backend.folder)
        except settings.SettingError as error:
            self.edit_error = f'{error}' + (f' Next: {error.next_step}' if error.next_step else '')
            return
        except ValueError as error:
            self.edit_error = str(error)
            return
        if refused := self._refusal(setting, value):
            self.edit_error = refused
            return
        self.editing = False
        self._focus('settings')
        self._stage(module, setting, value)

    def _exit(self) -> None:
        if self.busy:
            self.exit_requested = True
            self.message = 'Finishing the current change, then exiting…'
        elif self.change_count:
            self.quit_open = True
        else:
            self.app.exit()

    def _page(self, direction: int) -> None:
        window = self.modules_window if self.panel == 'modules' else self.settings_window
        height = window.render_info.window_height if window.render_info else 10
        self._move(direction * max(1, height - 1))

    def _open_preview(self) -> None:
        self.preview_text.text = self._preview()
        self.preview_open = True
        self.app.layout.focus(self.preview_text)

    def _filter_settings(self) -> None:
        self.filtering = self.editing = True
        self.editor.text = self.filter_text
        self.editor.buffer.cursor_position = len(self.editor.text)  # typing adds to the filter, Backspace takes away
        self.edit_error = ''
        self.app.layout.focus(self.editor)

    def _step(self, amount: int) -> bool:
        """Change the selected setting's value by one step: a number up or down, on/off switched, a choice to the
        next or previous of its choices. False when the setting has no steps, such as text."""
        row, setting = self.selected, self.current
        if row is None or self.panel != 'settings' or setting is None:
            return False
        value = self._value(setting.owner, setting)
        if setting.type is int:
            self._stage(setting.owner, setting, value + amount)
        elif setting.type is bool:
            self._stage(setting.owner, setting, not value)
        elif setting.kind == 'select':
            choices = self._choices(setting)
            if not choices:
                return False
            index = choices.index(value) + amount if value in choices else (0 if amount > 0 else -1)
            chosen = choices[index % len(choices)]
            if settings.risk(setting.key, chosen, self.backend.folder):
                # a choice that lets agents act without asking is never reached by stepping, nor by wrapping round
                self.message = f'{chosen} is not stepped onto: Enter opens the choices to pick and confirm it.'
                return True
            self._stage(setting.owner, setting, chosen)
        else:
            return False
        return True

    def _side(self, amount: int) -> None:
        """← and →: on a setting with steps they change its value; → opens a section and ← goes back out of one;
        elsewhere they switch panels."""
        if self.panel == 'settings' and ((not self.busy and self._step(amount)) or (
                self._open_section() if amount > 0 else self._close_section())):
            return
        self._focus('modules' if amount < 0 else 'settings')

    def _choices(self, setting: settings.Setting) -> list[str]:
        if setting.choices is None:
            return []
        try:
            return setting.options(self.backend.folder)
        except Exception:  # noqa: BLE001  a module's failing choices function leaves the setting to be typed
            return []

    def _open_pick(self, module: str, setting: settings.Setting, value: Any) -> bool:
        """Open the picker for a choice setting or a list with choices; False when the setting has no choices."""
        if setting.kind not in ('select', 'list'):
            return False
        choices = self._choices(setting)
        if not choices:
            return False
        self.pick_target, self.pick_choices = (module, setting), choices
        # while a select offers no more than its default, the picker offers to read its choices from their source
        self.pick_reader = setting.choices_from if setting.choices_from and len(choices) <= 1 else None
        if setting.kind == 'list':
            chosen = [str(item) for item in cast(list[Any], value)] if isinstance(value, list) else []
            # An empty list means every group for the settings that read empty as all, CLI-031
            self.pick_checked = set(choices) if not chosen and setting.key in settings.EMPTY_IS_ALL else set(chosen)
            self.pick_index = 0
        else:
            self.pick_checked = {value} if value in choices else set()
            self.pick_index = choices.index(value) if value in choices else 0
        self.picking = True
        self.app.layout.focus(self.pick_window)
        return True

    def _pick_label(self) -> str:
        if not self.pick_target:
            return ''
        module, setting = self.pick_target
        return f'{module}.{setting.key}\n{setting.help}'

    def _pick_keys(self) -> str:
        if self.pick_target and self.pick_target[1].kind == 'list':
            return '↑↓ Select   Space / ←→ Check   A All   Enter Stage   Esc Cancel'
        return '↑↓ Select   Enter Stage' + ('   Enter on the last line reads the choices' if self.pick_reader
                                            else '') + '   Esc Cancel'

    def _pick_about(self) -> str:
        """Beneath the list: what the highlighted choice does, and what it risks, in plain words; on the line that
        reads the choices, the command it runs."""
        if self.pick_reader and self.pick_index == len(self.pick_choices):
            return f'Runs {self.pick_reader} in this folder: it starts the agent once, with no prompt, reads the ' \
                   'choices it offers and closes it.'
        if not self.pick_target or not self.pick_choices or self.pick_target[1].kind != 'select':
            return ''
        return self._words(*self.pick_target).get(self.pick_choices[self.pick_index], '')

    def _pick_lines(self) -> StyleAndTextTuples:
        many = bool(self.pick_target and self.pick_target[1].kind == 'list')
        result: StyleAndTextTuples = []
        for index, choice in enumerate(self.pick_choices):
            mark = ('[x]' if choice in self.pick_checked else '[ ]') if many else \
                ('(•)' if choice in self.pick_checked else '( )')
            style = 'class:selection' if index == self.pick_index else ''
            result.append((style, f' {mark} {choice or "(none)"}\n'))
        if self.pick_reader:
            style = 'class:selection' if self.pick_index == len(self.pick_choices) else 'class:details'
            result.append((style, '  ▸ Read its choices: starts it once, with no prompt\n'))
        return result

    def _pick_move(self, amount: int) -> None:
        if self.pick_choices:
            last = len(self.pick_choices) - (0 if self.pick_reader else 1)
            self.pick_index = max(0, min(last, self.pick_index + amount))

    def _read_choices(self) -> None:
        """Run the setting's command that reads its choices, then open its picker again with what it found."""
        target, command = self.pick_target, self.pick_reader
        if target is None or command is None:
            return
        self._pick_close()
        said: list[str] = []

        async def read() -> None:
            said.append(await asyncio.to_thread(self.backend.read_choices, command))

        def opened() -> str:
            module, setting = target
            if said and said[0]:
                self.error = True
                return f'The choices could not be read: {said[0]}'
            self._open_pick(module, setting, self._value(module, setting))
            found = len(self.pick_choices)
            return f'Read {found} choices for {setting.key}.' if found > 1 else \
                f'{setting.key} still offers no choice but {self.pick_choices[0] if self.pick_choices else "none"}.'
        self._perform(read, f'Reading the choices: {command}…', success=opened)

    def _pick_check(self, everything: bool = False) -> None:
        if not self.pick_target or self.pick_target[1].kind != 'list' or not self.pick_choices:
            return
        if everything:
            whole = set(self.pick_choices)
            self.pick_checked = set() if self.pick_checked == whole else whole
            return
        choice = self.pick_choices[self.pick_index]
        mark = self.pick_target[1].exclusive
        if mark and choice not in self.pick_checked:  # one value per name: the others of its name are unchecked
            self.pick_checked = {one for one in self.pick_checked
                                 if one.partition(mark)[0] != choice.partition(mark)[0]}
        self.pick_checked ^= {choice}

    def _pick_apply(self) -> None:
        if not self.pick_target:
            return
        if self.pick_reader and self.pick_index == len(self.pick_choices):
            self._read_choices()
            return
        module, setting = self.pick_target
        if setting.kind == 'list':
            chosen = [choice for choice in self.pick_choices if choice in self.pick_checked]
            if setting.key in settings.EMPTY_IS_ALL and len(chosen) == len(self.pick_choices):
                chosen = []  # every group checked is stored as all, CLI-031
            self._stage(module, setting, chosen)
        elif self.pick_choices:
            self._stage(module, setting, self.pick_choices[self.pick_index])
        self._pick_close()

    def _pick_close(self) -> None:
        self.picking = False
        self.pick_target = None
        self.pick_reader = None
        self._focus('settings')

    def _module_help(self) -> None:
        row = self.selected
        if row is None:
            return
        definition = self.definitions.get(row.id)
        self.module_help_text.text = row.id + '\n\n' + ((definition.help or definition.description) if definition
                                                        else 'Enable and save this module to load its help and '
                                                             'settings.')
        if self.panel == 'settings' and (setting := self.current):
            # A setting's own help page, its details and the folder's choices with it, as `metaform help <switch>`
            found = settings.by_switch(setting.switch) if setting.switches else None
            if found is not None and (found[0].owner, found[0].key) == (setting.owner, setting.key):
                self.module_help_text.text = docs.switch_page(setting.switch, self.backend.folder)
        self.module_help_open = True
        self.app.layout.focus(self.module_help_text)

    def _help_toggle(self) -> None:
        self.help_open = not self.help_open
        if self.help_open:
            self.app.layout.focus(self.help_text)
        else:
            self._focus(self.panel)

    def _back(self) -> None:
        if self.confirm_open:
            self._confirm(False)
        elif self.picking:
            self._pick_close()
        elif self.module_help_open:
            self.module_help_open = False
            self._focus(self.panel)
        elif self.quit_open:
            self.quit_open = False
        elif self.preview_open:
            self.preview_open = False
            self._focus(self.panel)
        elif self.help_open:
            self.help_open = False
            self._focus(self.panel)
        elif self.editing:
            self.editing = self.filtering = False
            self._focus('settings')
        elif self.panel == 'settings':
            if not self._close_section():
                self._focus('modules')
        else:
            self._exit()

    def _refresh_values(self) -> None:
        async def again() -> None:
            await self.refresh()
        self._perform(again, 'Reading the stored values again…',
                      success=lambda: f'Read again. {self.change_count} pending changes remain unsaved.')

    def _bindings(self) -> KeyBindings:
        keys = KeyBindings()
        browsing = Condition(lambda: not self.editing and not self.help_open and not self.quit_open
                             and not self.preview_open and not self.module_help_open and not self.picking
                             and not self.confirm_open)
        editable = browsing & Condition(lambda: not self.busy)
        dialogs_closed = Condition(lambda: not self.editing and not self.quit_open and not self.preview_open
                                   and not self.module_help_open and not self.picking and not self.confirm_open)
        picking = Condition(lambda: self.picking and not self.confirm_open)
        confirming = Condition(lambda: self.confirm_open)
        quitting = Condition(lambda: self.quit_open)

        def bind(key: str, callback: Callable[[], object], filter: FilterOrBool = editable) -> None:
            def handler(event: KeyPressEvent) -> None:
                callback()
            keys.add(key, filter=filter)(handler)
        # Moving, finding and reading help never wait for a save or a read in progress; a change does.
        bind('up', lambda: self._move(-1), browsing)
        bind('k', lambda: self._move(-1), browsing)
        bind('j', lambda: self._move(1), browsing)
        bind('h', lambda: self._focus('modules'), browsing)
        bind('l', lambda: self._focus('settings'), browsing)
        bind('down', lambda: self._move(1), browsing)
        bind('home', lambda: self._move(), browsing)
        bind('end', lambda: self._move(end=True), browsing)
        bind('pageup', lambda: self._page(-1), browsing)
        bind('pagedown', lambda: self._page(1), browsing)
        bind('left', lambda: self._side(-1), browsing)
        bind('right', lambda: self._side(1), browsing)
        for key in ('tab', 's-tab'):
            bind(key, lambda: self._focus('settings' if self.panel == 'modules' else 'modules'), browsing)
        bind('enter', lambda: self._focus('settings') if self.panel == 'modules' else self._edit())
        bind(' ', lambda: self._toggle_module() if self.panel == 'modules' else self._edit())
        bind('f5', self._refresh_values)
        bind('f9', self._reset)
        bind('r', self._reset)
        bind('g', self._toggle_glue)
        bind('G', self._toggle_glue)
        bind('R', lambda: self._reset(group=True))
        bind('s', self._save_changes)
        bind('S', self._save_changes)
        bind('p', self._open_preview)
        bind('P', self._open_preview)
        bind('/', self._filter_settings, browsing)
        bind('+', lambda: self._step(1))
        bind('-', lambda: self._step(-1))
        bind('f2', self._module_help, browsing)
        bind('f1', self._help_toggle, dialogs_closed)
        bind('?', self._help_toggle, dialogs_closed)
        bind('enter', self._apply_edit, Condition(lambda: self.editing))
        for key, step in (('up', -1), ('k', -1), ('down', 1), ('j', 1)):
            bind(key, lambda step=step: self._pick_move(step), picking)
        bind('home', lambda: self._pick_move(-len(self.pick_choices) - 1), picking)
        bind('end', lambda: self._pick_move(len(self.pick_choices) + 1), picking)
        for key in (' ', 'left', 'right'):
            bind(key, self._pick_check, picking)
        for key in ('a', 'A'):
            bind(key, lambda: self._pick_check(everything=True), picking)
        bind('enter', self._pick_apply, picking)
        for key in ('y', 'Y'):
            bind(key, lambda: self._confirm(True), confirming)
        for key in ('n', 'N'):
            bind(key, lambda: self._confirm(False), confirming)
        bind('escape', self._back, True)
        bind('q', self._exit)
        bind('Q', self._exit)
        bind('c-c', self._exit, True)
        bind('f10', lambda: self._save_changes(exit_after=True), editable)
        for key in ('s', 'S'):
            bind(key, lambda: self._save_changes(exit_after=True), quitting)
        for key in ('d', 'D'):
            bind(key, lambda: self.app.exit(), quitting)
        return keys

    async def run(self) -> None:
        await self.refresh()
        await self.app.run_async()


def available() -> bool:
    return sys.stdin.isatty() and sys.stdout.isatty()


def run(folder: Path, *, input: Input | None = None, output: Output | None = None) -> None:
    """Open the settings screen for this folder."""
    asyncio.run(ChassisTUI(_Backend(folder), input=input, output=output).run())
