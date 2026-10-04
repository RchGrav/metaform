"""The settings screen: every setting the chassis and its modules declare, CLI-026.

The screen stages changes and saves them through the settings module, so the
screen, set and unset all read and write the same settings.
"""
from __future__ import annotations

import asyncio
import copy
import json
import sys
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

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

from . import home, loader, settings

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
    """One setting as the folder holds it: its value, and whether it is set or glued."""
    key: str
    value: Any
    saved: bool
    glued: bool


class _Backend:
    """What the screen needs: the groups, their settings and the values stored for this folder."""

    def __init__(self, folder: Path) -> None:
        self.folder = folder
        self.root = home.home()
        self.modules: dict[str, _Owner] = {}
        self.load_errors: dict[str, str] = {}

    def rows(self) -> list[_Row]:
        found = loader.discover()  # cached; only enable and disable reset it, BASE-037
        self.modules = {'chassis': _Owner(tuple(item for item in settings.SCHEMA.values() if item.owner == 'chassis'),
                                          description='Settings of the chassis itself.')}
        self.load_errors = {}
        rows = [_Row('chassis', True, str(self.root))]
        for item in found:
            if item.module is not None:
                self.modules[item.id] = _Owner(
                    tuple(setting for setting in settings.SCHEMA.values() if setting.owner == item.id),
                    description=item.module.summary, help=item.module.summary)  # the summary, for people; purpose is for agents
            if item.problem:
                self.load_errors[item.id] = item.problem
            rows.append(_Row(item.id, item.enabled, str(item.path)))
        return rows

    def definition(self, owner: str) -> _Owner:
        return self.modules[owner]

    def describe(self, owner: str) -> list[_Stored]:
        return [_Stored(str(row['key']), row['value'], row['state'] != 'default', row['state'] == 'glued')
                for row in settings.describe(self.folder) if row['owner'] == owner]


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
    'status': 'bg:#00306d #ffffff',
    'error': 'bg:#692b43 #ffffff',
    'footer': 'bg:#b9d8f2 #001a45',
    'text-area': 'bg:#d9e8ff #001a45',
    'text-area.cursor-line': 'bg:#d9e8ff #001a45',
})

HELP = ('SETUP KEYS\n\n'
        '↑ / ↓             Select a module or setting\n'
        '← / →, Tab        Switch between panels\n'
        'Shift+Tab         Switch back\n'
        'Home / End        First / last item\n'
        'Page Up / Down    Move one page\n'
        'Enter             Open settings or edit a value\n'
        'Space             Stage module or boolean toggle\n'
        'F2                Selected module help from its declaration\n'
        'F5                Read the stored values again\n'
        'r / F9            Reset selected setting; R resets group\n'
        '+ / -             Increase/decrease numeric setting\n'
        '/                 Filter settings by name or help\n'
        'P                 Preview pending changes\n'
        'S                 Save pending changes\n'
        'Esc               Close dialog, back, then exit\n'
        'F10               Save and exit\n'
        'Q / Ctrl+C        Quit (save/discard/continue)\n\n'
        'Changes are staged until saved. Folder settings apply to this folder.\n'
        'Strings use plain text; other values use JSON.\n'
        'G glues/unglues values; glued values survive reset.\n'
        '\n'
        'Press Esc or F1 to close.')


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
        self.modules_control = FormattedTextControl(self._module_lines, focusable=True,
                                                    get_cursor_position=lambda: Point(0, self.module_index))
        self.settings_control = FormattedTextControl(self._setting_lines, focusable=True,
                                                     get_cursor_position=lambda: Point(0, self.setting_index))
        self.editor = TextArea(multiline=False, wrap_lines=False)
        self.modules_window = Window(self.modules_control, wrap_lines=False, always_hide_cursor=True)
        self.settings_window = Window(self.settings_control, wrap_lines=False, always_hide_cursor=True)
        details = Window(FormattedTextControl(self._details), height=self._details_height, wrap_lines=True,
                         style='class:details')
        content = HSplit([
            Window(FormattedTextControl('  METAFORM  |  CHASSIS SETUP'), height=1, style='class:title'),
            Window(FormattedTextControl(self._tabs), height=1, style='class:tabs'),
            VSplit([
                Frame(self.modules_window, title='Modules', width=Dimension(weight=2, min=20)),
                Frame(self.settings_window, title='Settings', width=Dimension(weight=3, min=26)),
            ], padding=1),
            Frame(details, title='Selection details'),
            Window(FormattedTextControl(lambda: self.message), height=2, wrap_lines=True,
                   style=lambda: 'class:error' if self.error else 'class:status'),
            Window(FormattedTextControl('  ↑↓ Select   ←→ / Tab Panel   Enter Edit   Space Toggle'),
                   height=1, style='class:footer'),
            Window(FormattedTextControl('  F1 Keys  F2 Help  / Filter  G Glue  R Reset  P Preview  S Save  '
                                        'F10 Save/Exit'), height=1, style='class:footer'),
        ])
        edit_dialog = Frame(Box(HSplit([
            Window(FormattedTextControl(self._edit_label), height=2, wrap_lines=True),
            self.editor,
            Window(FormattedTextControl(lambda: self.edit_error or 'Enter Stage change    Esc Cancel'),
                   height=2, wrap_lines=True),
        ]), padding=1), title='Edit setting', width=Dimension(preferred=66))
        self.help_text = TextArea(text=HELP, read_only=True, scrollbar=True, wrap_lines=True)
        help_dialog = Frame(self.help_text, title='Keyboard help · ↑↓ scroll',
                            width=Dimension(preferred=64), height=Dimension(preferred=26))
        quit_dialog = Frame(Box(Window(FormattedTextControl(
            'There are unsaved changes.\n\n'
            'S  Save and exit\nD  Discard and exit\nEsc  Continue editing'),
            height=7), padding=1), title='Save changes?', width=52)
        self.preview_text = TextArea(read_only=True, scrollbar=True, wrap_lines=True)
        preview_dialog = Frame(self.preview_text, title='Pending changes · Esc closes',
                               width=Dimension(preferred=76), height=Dimension(preferred=22))
        self.module_help_text = TextArea(read_only=True, scrollbar=True, wrap_lines=True)
        module_help_dialog = Frame(self.module_help_text, title='Module help · Esc closes',
                                   width=Dimension(preferred=80), height=Dimension(preferred=24))
        container = FloatContainer(content, floats=[
            Float(content=ConditionalContainer(edit_dialog, Condition(lambda: self.editing))),
            Float(content=ConditionalContainer(help_dialog, Condition(lambda: self.help_open))),
            Float(content=ConditionalContainer(quit_dialog, Condition(lambda: self.quit_open))),
            Float(content=ConditionalContainer(preview_dialog, Condition(lambda: self.preview_open))),
            Float(content=ConditionalContainer(module_help_dialog, Condition(lambda: self.module_help_open))),
        ])
        self.app: Application[None] = Application(layout=Layout(container, focused_element=self.modules_window),
                                                  key_bindings=self._bindings(), style=STYLE, full_screen=True,
                                                  input=input, output=output, refresh_interval=.5)
        self.app.ttimeoutlen = .1

    def _details_height(self) -> int:
        return 3 if self.app.output.get_size().rows < 24 else 5

    def _tabs(self) -> str:
        return (f'  Modules ({len(self.rows)})    /    Settings       '
                f'{"Working…" if self.busy else str(self.change_count) + " pending changes"}')

    @property
    def selected(self) -> _Row | None:
        return self.rows[self.module_index] if self.rows else None

    @property
    def declared_settings(self) -> tuple[settings.Setting, ...]:
        definition = self.definitions.get(self.selected.id) if self.selected else None
        if not definition:
            return ()
        query = self.filter_text.casefold()
        return tuple(item for item in definition.settings
                     if query in item.key.casefold() or query in item.help.casefold())

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

    def _setting_lines(self) -> StyleAndTextTuples:
        from .cli import setting_row
        selected = self.selected
        if selected is None:
            return [('class:disabled', '  Select a module.')]
        if not self.declared_settings:
            return [('class:disabled', '  Enable and save to configure.' if selected.id not in self.backend.modules
                     else '  No matching settings.')]
        result: StyleAndTextTuples = []
        for index, setting in enumerate(self.declared_settings):
            style = ''
            if index == self.setting_index:
                style = 'class:selection' if self.panel == 'settings' else 'class:selected-inactive'
            identity = (selected.id, setting.key)
            value = self._value(selected.id, setting)
            pending = self.pending_settings.get(identity)
            saved = pending[0] != 'reset' if pending else self.saved.get(identity, False)
            state = 'glued' if self._glued(identity) else ('set' if saved else 'default')
            row = setting_row(setting.key, value, state).replace('\n', '\\n')
            result.append((style, f' {">" if index == self.setting_index else " "}{row}\n'))
        return result

    def _details(self) -> str:
        row = self.selected
        if row is None:
            return ''
        definition = self.definitions.get(row.id)
        error = self.definition_errors.get(row.id) or self.backend.load_errors.get(row.id)
        if self.panel == 'settings' and self.declared_settings:
            setting = self.declared_settings[self.setting_index]
            return (f'{row.id}.{setting.key}  |  {setting.type.__name__}\n{setting.help}\n'
                    f'Default: {json.dumps(setting.default, ensure_ascii=False)}\n'
                    f'CLI: metaform set {setting.switch} VALUE\n'
                    f'Reset: metaform unset {setting.switch}   '
                    f'{"Glued (G unglues)" if self._glued((row.id, setting.key)) else "G glues value"}')
        state = 'Enabled and active' if row.id in self.backend.modules else 'Disabled'
        if row.enabled and row.id not in self.backend.modules:
            state = 'Enabled; activation failed'
        return (f'{row.id}  |  {state}\n'
                f'{error or (definition.description if definition else "")}\n'
                f'{row.path}\nSpace changes module state. Enter opens its settings.')

    def _edit_label(self) -> str:
        if self.filtering:
            return 'Filter settings by name or help. Empty text clears the filter.'
        if not self._edit_target:
            return ''
        module, setting = self._edit_target
        return f'{module}.{setting.key} ({setting.type.__name__})\n{setting.help}'

    async def refresh(self) -> None:
        previous = self.selected.id if self.selected else None
        # Discovery runs module start hooks; off this loop, an async one runs on a loop of its own, BASE-009.
        self.rows = await asyncio.to_thread(self.backend.rows)
        self.definitions = {}
        for row in self.rows:
            try:
                self.definitions[row.id] = self.backend.definition(row.id)
                for item in self.backend.describe(row.id):
                    self.values[row.id, item.key] = item.value
                    self.saved[row.id, item.key] = item.saved
                    self.glued[row.id, item.key] = item.glued
                self.definition_errors.pop(row.id, None)
            except Exception as error:  # noqa: BLE001  a group that cannot be described shows its error
                self.definition_errors[row.id] = str(error)
        self.module_index = next((index for index, row in enumerate(self.rows) if row.id == previous), 0)
        self.setting_index = min(self.setting_index, max(0, len(self.declared_settings) - 1))
        self.app.invalidate()

    def _focus(self, panel: str) -> None:
        self.panel = panel
        self.app.layout.focus(self.modules_window if panel == 'modules' else self.settings_window)

    def _move(self, amount: int | None = None, end: bool = False) -> None:
        if self.panel == 'modules':
            size, index = len(self.rows), self.module_index
        else:
            size, index = len(self.declared_settings), self.setting_index
        index = max(0, min(size - 1, index + amount if amount is not None else (size - 1 if end else 0)))
        if self.panel == 'modules':
            self.module_index = index
            self.setting_index = 0
        else:
            self.setting_index = index

    def _perform(self, action: Callable[[], Awaitable[None]], message: str, *,
                 success: Callable[[], str] | None = None) -> None:
        if self.busy:
            return
        self.busy = True
        self.error = False
        self.message = message

        async def run() -> None:
            try:
                await action()
                await self.refresh()
                self.message = success() if success else 'Applied. Changes are saved globally.'
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
        if row is None or not self.declared_settings:
            return
        setting = self.declared_settings[self.setting_index]
        value = self._value(row.id, setting)
        if setting.type is bool:
            self._stage(row.id, setting, not value)
            return
        self._edit_target = (row.id, setting)
        self.editor.text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
        self.editor.buffer.cursor_position = len(self.editor.text)
        self.edit_error = ''
        self.editing = True
        self.app.layout.focus(self.editor)

    def _stage(self, module: str, setting: settings.Setting, value: Any) -> None:
        identity = (module, setting.key)
        if value == self.values.get(identity, setting.default):
            self.pending_settings.pop(identity, None)
        else:
            self.pending_settings[identity] = ('set', value)
        self.message = 'Setting staged. S saves; P previews pending changes.'

    def _reset(self, group: bool = False) -> None:
        row = self.selected
        if row is None or self.panel != 'settings' or not self.declared_settings:
            return
        entries = self.definitions[row.id].settings if group else (self.declared_settings[self.setting_index],)
        for setting in entries:
            identity = (row.id, setting.key)
            if self._glued(identity):
                continue
            if self.saved.get(identity, False):
                self.pending_settings[identity] = ('reset', None)
            else:
                self.pending_settings.pop(identity, None)
        self.message = 'Defaults staged. S saves the change.'

    def _glued(self, identity: Key) -> bool:
        return self.pending_glue.get(identity, self.glued.get(identity, False))

    def _toggle_glue(self) -> None:
        row = self.selected
        if row is None or self.panel != 'settings' or not self.declared_settings:
            return
        setting = self.declared_settings[self.setting_index]
        identity = (row.id, setting.key)
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

        async def save() -> None:
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
                await asyncio.to_thread(loader.set_enabled, module, enabled)
                self.pending_modules.pop(module)
            if exit_after:
                self.exit_requested = True
        self._perform(save, 'Saving settings and module state…',
                      success=lambda: ' '.join(['Applied. Changes are saved globally.', *noted]))

    def _apply_edit(self) -> None:
        if self.filtering:
            self.filter_text = self.editor.text
            self.filtering = self.editing = False
            self.setting_index = 0
            self._focus('settings')
            self.message = f'Filter: {self.filter_text or "all settings"}'
            return
        if self._edit_target is None:
            return
        module, setting = self._edit_target
        try:
            value: Any = self.editor.text if setting.type is str else json.loads(self.editor.text)
            if not isinstance(value, setting.type) or (setting.type is int and isinstance(value, bool)):
                raise ValueError(f'Enter a {setting.type.__name__} value.')
        except (ValueError, TypeError) as error:
            self.edit_error = str(error)
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
        self.edit_error = ''
        self.app.layout.focus(self.editor)

    def _step(self, amount: int) -> None:
        row = self.selected
        if row is not None and self.panel == 'settings' and self.declared_settings:
            setting = self.declared_settings[self.setting_index]
            if setting.type is int:
                self._stage(row.id, setting, self._value(row.id, setting) + amount)

    def _module_help(self) -> None:
        row = self.selected
        if row is None:
            return
        definition = self.definitions.get(row.id)
        self.module_help_text.text = row.id + '\n\n' + ((definition.help or definition.description) if definition
                                                        else 'Enable and save this module to load its help and '
                                                             'settings.')
        self.module_help_open = True
        self.app.layout.focus(self.module_help_text)

    def _help_toggle(self) -> None:
        self.help_open = not self.help_open
        if self.help_open:
            self.app.layout.focus(self.help_text)
        else:
            self._focus(self.panel)

    def _back(self) -> None:
        if self.module_help_open:
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
                             and not self.preview_open and not self.module_help_open)
        editable = browsing & Condition(lambda: not self.busy)
        dialogs_closed = Condition(lambda: not self.editing and not self.quit_open and not self.preview_open
                                   and not self.module_help_open)
        quitting = Condition(lambda: self.quit_open)

        def bind(key: str, callback: Callable[[], object], filter: FilterOrBool = editable) -> None:
            def handler(event: KeyPressEvent) -> None:
                callback()
            keys.add(key, filter=filter)(handler)
        bind('up', lambda: self._move(-1))
        bind('k', lambda: self._move(-1))
        bind('j', lambda: self._move(1))
        bind('h', lambda: self._focus('modules'))
        bind('l', lambda: self._focus('settings'))
        bind('down', lambda: self._move(1))
        bind('home', lambda: self._move())
        bind('end', lambda: self._move(end=True))
        bind('pageup', lambda: self._page(-1))
        bind('pagedown', lambda: self._page(1))
        bind('left', lambda: self._focus('modules'))
        bind('right', lambda: self._focus('settings'))
        for key in ('tab', 's-tab'):
            bind(key, lambda: self._focus('settings' if self.panel == 'modules' else 'modules'))
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
        bind('/', self._filter_settings)
        bind('+', lambda: self._step(1))
        bind('-', lambda: self._step(-1))
        bind('f2', self._module_help)
        bind('f1', self._help_toggle, dialogs_closed)
        bind('?', self._help_toggle, dialogs_closed)
        bind('enter', self._apply_edit, Condition(lambda: self.editing))
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
