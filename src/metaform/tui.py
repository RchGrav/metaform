"""The settings screen: every setting the chassis and its modules declare.

The screen stages changes and saves them through the settings module, so the
screen, set and unset all read and write the same settings.
"""
from __future__ import annotations

import asyncio
import copy
import json

from prompt_toolkit import Application
from prompt_toolkit.data_structures import Point
from prompt_toolkit.filters import Condition
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import (
    ConditionalContainer, Float, FloatContainer, HSplit, Layout, VSplit, Window,
)
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.layout.dimension import Dimension
from prompt_toolkit.styles import Style
from prompt_toolkit.widgets import Box, Frame, TextArea

import sys
from dataclasses import dataclass
from pathlib import Path

from . import home, loader, settings


@dataclass
class _Owner:
    settings: tuple
    description: str = ''
    help: str = ''


class _Backend:
    """What the screen needs: owners of settings, their values, and saving."""

    def __init__(self, folder: Path):
        self.folder = folder
        self.root = home.home()
        self.plugins = {}
        self.load_errors = {}

    def rows(self):
        loader.reset()
        found = loader.discover()
        self.plugins = {'chassis': _Owner(tuple(item for item in settings.SCHEMA.values() if item.owner == 'chassis'),
                                          description='Settings of the chassis itself.')}
        self.load_errors = {}
        rows = [{'id': 'chassis', 'enabled': True, 'path': str(self.root)}]
        for item in found:
            if item.module is not None:
                self.plugins[item.id] = _Owner(
                    tuple(setting for setting in settings.SCHEMA.values() if setting.owner == item.id),
                    description=item.module.purpose, help=item.module.details or item.module.purpose)
            if item.problem:
                self.load_errors[item.id] = item.problem
            rows.append({'id': item.id, 'enabled': item.enabled, 'path': str(item.path)})
        return rows

    def definition(self, owner):
        return self.plugins[owner]

    def describe(self, owner):
        return [{'key': row['key'], 'value': row['value'],
                 'source': 'saved' if row['state'] != 'default' else 'default',
                 'pinned': row['state'] == 'glued'}
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


class ChassisTUI:
    """Keyboard-operated setup using the runtime's existing lifecycle and store."""

    def __init__(self, runtime, module=None, *, input=None, output=None):
        self.runtime = runtime
        self.module_scope = module
        self.rows = []
        self.definitions = {}
        self.definition_errors = {}
        self.values = {}
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
        self.filter_text = ""
        self.filtering = False
        self.pending_settings = {}
        self.pending_modules = {}
        self.pending_pins = {}
        self.pins = {}
        self.sources = {}
        self.message = 'Select a group. Edit settings, then press S to save or F10 to save and exit.'
        self.error = False
        self.exit_requested = False
        self._edit_target = None
        self.modules_control = FormattedTextControl(self._module_lines, focusable=True,
            get_cursor_position=lambda: Point(0, self.module_index))
        self.settings_control = FormattedTextControl(self._setting_lines, focusable=True,
            get_cursor_position=lambda: Point(0, self.setting_index))
        self.editor = TextArea(multiline=False, wrap_lines=False)
        modules_window = Window(self.modules_control, wrap_lines=False, always_hide_cursor=True)
        settings_window = Window(self.settings_control, wrap_lines=False, always_hide_cursor=True)
        self.modules_window = modules_window
        self.settings_window = settings_window
        details = Window(FormattedTextControl(self._details), height=lambda: 3 if self.app.output.get_size().rows < 24 else 5, wrap_lines=True,
                         style='class:details')
        content = HSplit([
            Window(FormattedTextControl('  METAFORM  |  CHASSIS SETUP'), height=1, style='class:title'),
            Window(FormattedTextControl(lambda: f'  Modules ({len(self.rows)})    /    Settings     '
                f'  {"Working…" if self.busy else str(self.change_count) + " pending changes"}'), height=1, style='class:tabs'),
            VSplit([
                Frame(modules_window, title='Modules', width=Dimension(weight=2, min=20)),
                Frame(settings_window, title='Registered settings', width=Dimension(weight=3, min=26)),
            ], padding=1),
            Frame(details, title='Selection details'),
            Window(FormattedTextControl(lambda: self.message), height=2, wrap_lines=True,
                   style=lambda: 'class:error' if self.error else 'class:status'),
            Window(FormattedTextControl('  ↑↓ Select   ←→ / Tab Panel   Enter Edit   Space Toggle'),
                   height=1, style='class:footer'),
            Window(FormattedTextControl('  F1 Keys  F2 Help  / Filter  G Glue  R Reset  P Preview  S Save  F10 Save/Exit'),
                   height=1, style='class:footer'),
        ])
        edit_dialog = Frame(Box(HSplit([
            Window(FormattedTextControl(self._edit_label), height=2, wrap_lines=True),
            self.editor,
            Window(FormattedTextControl(lambda: self.edit_error or 'Enter Stage change    Esc Cancel'),
                   height=2, wrap_lines=True),
        ]), padding=1), title='Edit setting', width=Dimension(preferred=66))
        self.help_text = TextArea(text=
            'SETUP KEYS\n\n'
            '↑ / ↓             Select a module or setting\n'
            '← / →, Tab        Switch between panels\n'
            'Shift+Tab         Switch back\n'
            'Home / End        First / last item\n'
            'Page Up / Down    Move one page\n'
            'Enter             Open settings or edit a value\n'
            'Space             Stage module or boolean toggle\n'
            'F2                Selected module help from its declaration\n'
            'F5                Refresh modules and declarations\n'
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
            'Press Esc or F1 to close.', read_only=True, scrollbar=True, wrap_lines=True)
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
        self.app = Application(layout=Layout(container, focused_element=modules_window),
            key_bindings=self._bindings(), style=STYLE, full_screen=True,
            input=input, output=output, refresh_interval=.5)
        self.app.ttimeoutlen = .1

    @property
    def selected(self):
        return self.rows[self.module_index] if self.rows else None

    @property
    def declared_settings(self):
        definition = self.definitions.get(self.selected['id']) if self.selected else None
        if not definition:
            return ()
        query = self.filter_text.casefold()
        return tuple(item for item in definition.settings
                     if query in item.key.casefold() or query in item.help.casefold())

    def _module_lines(self):
        if not self.rows:
            return [('class:disabled', '  No registered modules.\n  Copy a Python file or package folder\n  into the modules directory below.\n  F5 refreshes.')]
        result = []
        for index, row in enumerate(self.rows):
            style = 'class:enabled' if row['enabled'] else 'class:disabled'
            if index == self.module_index:
                style = 'class:selection' if self.panel == 'modules' else 'class:selected-inactive'
            state = 'On ' if self.pending_modules.get(row['id'], bool(row['enabled'])) else 'Off'
            if row['id'] in self.pending_modules:
                state += '*'
            elif row['enabled'] and row['id'] not in self.runtime.plugins:
                state = 'Err'
            result.append((style, f' {">" if index == self.module_index else " "} [{state}] {row["id"]}\n'))
        return result

    def _setting_lines(self):
        if not self.declared_settings:
            return [('class:disabled', ('  Enable and save to configure.' if self.selected['id'] not in self.runtime.plugins
                                          else '  No matching settings.') if self.selected else '  Select a module.')]
        result = []
        for index, setting in enumerate(self.declared_settings):
            style = ''
            if index == self.setting_index:
                style = 'class:selection' if self.panel == 'settings' else 'class:selected-inactive'
            value = self._value(self.selected['id'], setting)
            rendered = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
            rendered = str(rendered).replace('\n', '\\n')
            result.append((style, f' {">" if index == self.setting_index else " "} {"◆" if self._pinned(self.selected["id"], setting.key) else " "} {setting.key} = {rendered}'
                                  f'  {"*" if (self.selected["id"], setting.key) in self.pending_settings else self.sources.get((self.selected["id"], setting.key), "default")}\n'))
        return result

    def _details(self):
        if not self.selected:
            return (f'Modules: {self.runtime.root / "modules"}\n'
                    'Copy a Python file or package folder here; F5 refreshes.\n'
                    'Alternate: metaform modules load PATH')
        row = self.selected
        definition = self.definitions.get(row['id'])
        error = self.definition_errors.get(row['id']) or self.runtime.load_errors.get(row['id'])
        if not error and row.get('compatible') is False:
            error = row.get('compatibility_reason')
        if self.panel == 'settings' and self.declared_settings:
            setting = self.declared_settings[self.setting_index]
            return (f'{row["id"]}.{setting.key}  |  {setting.type.__name__}\n{setting.help}\n'
                    f'Default: {json.dumps(setting.default, ensure_ascii=False)}\n'
                    f'CLI: metaform set {setting.switch} VALUE\n'
                    f'Reset: metaform unset {setting.switch}   '
                    f'{"Glued (G unglues)" if self._pinned(row["id"], setting.key) else "G glues value"}')
        state = 'Enabled and active' if row['id'] in self.runtime.plugins else 'Disabled'
        if row['enabled'] and row['id'] not in self.runtime.plugins:
            state = 'Enabled; unavailable' if row.get('compatible') is False else 'Enabled; activation failed'
        return (f'{row["id"]}  |  {state}\n'
                f'{error or (definition.description if definition else "")}\n'
                f'{row["path"]}\nSpace changes module state. Enter opens its settings.')

    def _edit_label(self):
        if self.filtering:
            return 'Filter settings by name or help. Empty text clears the filter.'
        if not self._edit_target:
            return ''
        module, setting = self._edit_target
        return f'{module}.{setting.key} ({setting.type.__name__})\n{setting.help}'

    async def refresh(self, *, declarations=False):
        previous = self.selected['id'] if self.selected else None
        self.rows = self.runtime.rows()
        self.definitions = {}
        for row in self.rows:
            identifier = row['id']
            try:
                self.definitions[identifier] = self.runtime.definition(identifier)
                for item in self.runtime.describe(identifier):
                    self.values[identifier, item['key']] = item['value']
                    self.sources[identifier, item['key']] = item['source']
                    self.pins[identifier, item['key']] = item['pinned']
                self.definition_errors.pop(identifier, None)
            except Exception as error:
                self.definition_errors[identifier] = str(error)
        self.module_index = next((i for i, row in enumerate(self.rows) if row['id'] == previous), 0)
        self.setting_index = min(self.setting_index, max(0, len(self.declared_settings) - 1))
        self.app.invalidate()

    def _focus(self, panel):
        self.panel = panel
        self.app.layout.focus(self.modules_window if panel == 'modules' else self.settings_window)

    def _move(self, amount=None, end=False):
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

    def _perform(self, action, message, *, success=None):
        if self.busy:
            return
        self.busy = True
        self.error = False
        self.message = message
        async def run():
            try:
                await action()
                await self.refresh()
                self.message = success() if success else 'Applied. Changes are saved globally.'
            except Exception as error:
                self.message = str(error)
                self.error = True
                try:
                    await self.refresh()
                except Exception:
                    pass  # Preserve the actionable error from the requested change.
            finally:
                self.busy = False
                self.app.invalidate()
                if self.exit_requested:
                    self.exit_requested = False
                    if self.change_count:
                        self.quit_open = True
                    else:
                        self.app.exit()
        self.app.create_background_task(run())

    @property
    def change_count(self):
        return len(self.pending_modules) + len(self.pending_settings) + len(self.pending_pins)

    def _value(self, module, setting):
        pending = self.pending_settings.get((module, setting.key))
        if pending:
            return copy.deepcopy(setting.default) if pending[0] == 'reset' else pending[1]
        return self.values.get((module, setting.key), setting.default)

    def _preview(self):
        lines = []
        for module, enabled in self.pending_modules.items():
            lines.append(f'{module}: {"enable" if enabled else "disable"}')
        for (module, key), pinned in self.pending_pins.items():
            lines.append(f'{module}.{key}: {"glue" if pinned else "unglue"}')
        for (module, key), (action, value) in self.pending_settings.items():
            before = json.dumps(self.values.get((module, key)), ensure_ascii=False)
            after = 'default' if action == 'reset' else json.dumps(value, ensure_ascii=False)
            lines.append(f'{module}.{key}: {before} → {after}')
        return '\n'.join(lines) or 'No pending changes.'

    def _toggle_module(self):
        if not self.selected:
            return
        row = self.selected
        if row['id'] == 'chassis':
            self.message = 'The chassis is always on. Enter opens its settings.'
            return
        enabled = not self.pending_modules.get(row['id'], bool(row['enabled']))
        if enabled == bool(row['enabled']):
            self.pending_modules.pop(row['id'], None)
        else:
            self.pending_modules[row['id']] = enabled
        self.message = 'Module change staged. S saves; P previews pending changes.'

    def _edit(self):
        if not self.declared_settings:
            return
        setting = self.declared_settings[self.setting_index]
        module = self.selected['id']
        value = self._value(module, setting)
        if setting.type is bool:
            self._save(module, setting, not value)
            return
        self._edit_target = (module, setting)
        self.editor.text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
        self.editor.buffer.cursor_position = len(self.editor.text)
        self.edit_error = ''
        self.editing = True
        self.app.layout.focus(self.editor)

    def _save(self, module, setting, value):
        identity = (module, setting.key)
        if value == self.values.get(identity, setting.default):
            self.pending_settings.pop(identity, None)
        else:
            self.pending_settings[identity] = ('set', value)
        self.message = 'Setting staged. S saves; P previews pending changes.'

    def _reset(self, group=False):
        if self.panel != 'settings' or not self.declared_settings:
            return
        entries = self.definitions[self.selected['id']].settings if group else [self.declared_settings[self.setting_index]]
        for setting in entries:
            identity = (self.selected['id'], setting.key)
            if self._pinned(*identity):
                continue
            if self.sources.get(identity) == 'saved':
                self.pending_settings[identity] = ('reset', None)
            else:
                self.pending_settings.pop(identity, None)
        self.message = 'Defaults staged. S saves the change.'

    def _pinned(self, module, key):
        return self.pending_pins.get((module, key), self.pins.get((module, key), False))

    def _toggle_pin(self):
        if self.panel != 'settings' or not self.declared_settings:
            return
        identity = (self.selected['id'], self.declared_settings[self.setting_index].key)
        pinned = not self._pinned(*identity)
        if pinned == self.pins.get(identity, False):
            self.pending_pins.pop(identity, None)
        else:
            self.pending_pins[identity] = pinned
        if pinned and self.pending_settings.get(identity, (None,))[0] == 'reset':
            setting = self.declared_settings[self.setting_index]
            self.pending_settings[identity] = ('set', copy.deepcopy(setting.default))
        self.message = 'Glue change staged. Glued values survive reset. S saves.'

    def _save_changes(self, exit_after=False):
        self.quit_open = False
        async def save():
            folder = self.runtime.folder
            for (module, key), (action, value) in list(self.pending_settings.items()):
                identity = (module, key)
                glue = self.pending_pins.get(identity)
                if action == 'reset':
                    settings.reset(key, folder, unglue=glue is False)
                else:
                    settings.put(key, value, folder, glue=bool(glue))
                self.pending_settings.pop(identity)
                self.pending_pins.pop(identity, None)
            for (module, key), pinned in list(self.pending_pins.items()):
                settings.glue(key, folder, pinned)
                self.pending_pins.pop((module, key))
            for module, enabled in list(self.pending_modules.items()):
                loader.set_enabled(module, enabled)
                self.pending_modules.pop(module)
            if exit_after:
                self.exit_requested = True
        self._perform(save, 'Saving settings and module state…')

    def _apply_edit(self):
        if self.filtering:
            self.filter_text = self.editor.text
            self.filtering = self.editing = False
            self.setting_index = 0
            self._focus('settings')
            self.message = f'Filter: {self.filter_text or "all settings"}'
            return
        module, setting = self._edit_target
        try:
            value = self.editor.text if setting.type is str else json.loads(self.editor.text)
            if not isinstance(value, setting.type) or (setting.type is int and isinstance(value, bool)):
                raise ValueError(f'Enter a {setting.type.__name__} value.')
        except (ValueError, TypeError) as error:
            self.edit_error = str(error)
            return
        self.editing = False
        self._focus('settings')
        self._save(module, setting, value)

    def _exit(self):
        if self.busy:
            self.exit_requested = True
            self.message = 'Finishing the current change, then exiting…'
        elif self.change_count:
            self.quit_open = True
        else:
            self.app.exit()

    def _bindings(self):
        keys = KeyBindings()
        browsing = Condition(lambda: not self.editing and not self.help_open and not self.quit_open and not self.preview_open and not self.module_help_open)
        editable = browsing & Condition(lambda: not self.busy)
        def bind(key, callback, filter=editable):
            keys.add(key, filter=filter)(lambda event: callback())
        bind('up', lambda: self._move(-1))
        bind('k', lambda: self._move(-1))
        bind('j', lambda: self._move(1))
        bind('h', lambda: self._focus('modules'))
        bind('l', lambda: self._focus('settings'))
        bind('down', lambda: self._move(1))
        bind('home', lambda: self._move())
        bind('end', lambda: self._move(end=True))
        def page(direction):
            window = self.modules_window if self.panel == 'modules' else self.settings_window
            height = window.render_info.window_height if window.render_info else 10
            self._move(direction * max(1, height - 1))
        bind('pageup', lambda: page(-1))
        bind('pagedown', lambda: page(1))
        bind('left', lambda: self._focus('modules'))
        bind('right', lambda: self._focus('settings'))
        for key in ('tab', 's-tab'):
            bind(key, lambda: self._focus('settings' if self.panel == 'modules' else 'modules'))
        bind('enter', lambda: self._focus('settings') if self.panel == 'modules' else self._edit())
        bind(' ', lambda: self._toggle_module() if self.panel == 'modules' else self._edit())
        bind('f5', lambda: self._perform(lambda: self.refresh(declarations=True), 'Refreshing modules…',
             success=lambda: f'Refreshed. {self.change_count} pending changes remain unsaved.'))
        bind('f9', self._reset)
        bind('r', self._reset)
        bind('g', self._toggle_pin)
        bind('G', self._toggle_pin)
        bind('R', lambda: self._reset(group=True))
        bind('s', self._save_changes)
        bind('S', self._save_changes)
        def preview():
            self.preview_text.text = self._preview()
            self.preview_open = True
            self.app.layout.focus(self.preview_text)
        bind('p', preview)
        bind('P', preview)
        def filter_settings():
            self.filtering = self.editing = True
            self.editor.text = self.filter_text
            self.edit_error = ''
            self.app.layout.focus(self.editor)
        bind('/', filter_settings)
        def increment(amount):
            if self.panel == 'settings' and self.declared_settings:
                setting = self.declared_settings[self.setting_index]
                if setting.type in (int, float):
                    self._save(self.selected['id'], setting, self._value(self.selected['id'], setting) + amount)
        bind('+', lambda: increment(1))
        bind('-', lambda: increment(-1))
        def module_help():
            if not self.selected:
                return
            definition = self.definitions.get(self.selected['id'])
            self.module_help_text.text = (self.selected['id'] + '\n\n' +
                ((getattr(definition, 'help', '') or definition.description) if definition
                 else 'Enable and save this module to load its help and settings.'))
            self.module_help_open = True
            self.app.layout.focus(self.module_help_text)
        bind('f2', module_help)
        def help_toggle():
            self.help_open = not self.help_open
            if self.help_open:
                self.app.layout.focus(self.help_text)
            else:
                self._focus(self.panel)
        bind('f1', help_toggle, Condition(lambda: not self.editing and not self.quit_open and not self.preview_open and not self.module_help_open))
        bind('?', help_toggle, Condition(lambda: not self.editing and not self.quit_open and not self.preview_open and not self.module_help_open))
        bind('enter', self._apply_edit, Condition(lambda: self.editing))
        def back():
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
        bind('escape', back, Condition(lambda: True))
        bind('q', self._exit)
        bind('Q', self._exit)
        bind('c-c', self._exit, Condition(lambda: True))
        bind('f10', lambda: self._save_changes(exit_after=True), editable)
        for key in ('s', 'S'):
            bind(key, lambda: self._save_changes(exit_after=True), Condition(lambda: self.quit_open))
        for key in ('d', 'D'):
            bind(key, lambda: self.app.exit(), Condition(lambda: self.quit_open))
        return keys

    async def run(self):
        await self.refresh()
        return await self.app.run_async()


def available() -> bool:
    return sys.stdin.isatty() and sys.stdout.isatty()


def run(folder: Path, *, input=None, output=None):
    """Open the settings screen for this folder."""
    return asyncio.run(ChassisTUI(_Backend(folder), input=input, output=output).run())
