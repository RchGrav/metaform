"""Settings: one schema drives set, unset, validation, defaults, help and config.

Each setting is in one of three states: default, set, or glued. A glued setting
keeps its value through `unset all` until it is unglued. Folder settings belong
to the folder the command runs in; global settings apply everywhere.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from . import home


class SettingError(ValueError):
    """A value a setting cannot take. The message names the next step."""


@dataclass(frozen=True)
class Setting:
    key: str
    default: object = None
    help: str = ''
    kind: str = 'str'  # str, int, bool, list or select
    choices: Callable[[], list[str]] | list[str] | None = None
    scope: str = 'global'  # global or folder
    owner: str = 'chassis'
    details: str = ''
    default_from: Callable[[Path], object] | None = field(default=None, compare=False)

    @property
    def switch(self) -> str:
        return '--' + self.key.replace('_', '-')

    def options(self) -> list[str]:
        return list(self.choices() if callable(self.choices) else self.choices or [])


SCHEMA: dict[str, Setting] = {}


def declare(setting: Setting) -> Setting:
    existing = SCHEMA.get(setting.key)
    if existing is not None and existing.owner != setting.owner:
        raise ValueError(f'Setting {setting.switch} already belongs to {existing.owner}.')
    SCHEMA[setting.key] = setting
    return setting


def _scope(setting: Setting, folder: Path) -> str:
    return 'global' if setting.scope == 'global' else 'folder:' + str(folder.resolve())


def default(setting: Setting, folder: Path):
    return setting.default_from(folder) if setting.default_from else setting.default


def value(key: str, folder: Path):
    setting = SCHEMA[key]
    scope = _scope(setting, folder)
    return home.saved(scope, key) if home.has_saved(scope, key) else default(setting, folder)


def state(key: str, folder: Path) -> str:
    setting = SCHEMA[key]
    scope = _scope(setting, folder)
    if home.glued(scope, key):
        return 'glued'
    return 'set' if home.has_saved(scope, key) else 'default'


def parse(setting: Setting, raw: str):
    if setting.kind == 'int':
        try:
            return int(raw)
        except ValueError:
            raise SettingError(f'{setting.switch} needs a whole number, not {raw!r}.') from None
    if setting.kind == 'bool':
        lowered = raw.lower()
        if lowered in {'1', 'true', 'yes', 'on'}:
            return True
        if lowered in {'0', 'false', 'no', 'off'}:
            return False
        raise SettingError(f'{setting.switch} needs on or off, not {raw!r}.')
    if setting.kind == 'list':
        return [item.strip() for item in raw.split(',') if item.strip()]
    if setting.kind == 'select':
        options = setting.options()
        if raw not in options:
            listed = ', '.join(options) if options else 'none yet'
            raise SettingError(f'{setting.switch} has no choice {raw!r}. Choices: {listed}.')
    return raw


def assign(key: str, raw: str, folder: Path, *, glue: bool = False):
    """Set one setting. Returns (old, new)."""
    setting = SCHEMA[key]
    new = parse(setting, raw)
    old = value(key, folder)
    scope = _scope(setting, folder)
    home.save(scope, key, new)
    if glue:
        home.set_glue(scope, key, True)
    return old, new


def reset(key: str, folder: Path, *, unglue: bool = False) -> tuple[str, bool]:
    """Reset one setting.

    Returns the outcome (reset, skipped because glued, or unchanged) and whether
    it was unglued.
    """
    setting = SCHEMA[key]
    scope = _scope(setting, folder)
    unglued = False
    if home.glued(scope, key):
        if not unglue:
            return 'skipped', False
        home.set_glue(scope, key, False)
        unglued = True
    if not home.has_saved(scope, key):
        return 'unchanged', unglued
    before = value(key, folder)
    home.clear(scope, key)
    return ('reset' if before != default(setting, folder) else 'unchanged'), unglued


def describe(folder: Path) -> list[dict]:
    return [{'key': key, 'switch': setting.switch, 'owner': setting.owner, 'kind': setting.kind,
             'scope': setting.scope, 'value': value(key, folder), 'default': default(setting, folder),
             'state': state(key, folder), 'help': setting.help}
            for key, setting in sorted(SCHEMA.items())]


declare(Setting(
    key='project', kind='select', scope='folder',
    choices=lambda: list(home.projects()),
    default_from=home.folder_project,
    help='The project this folder works on.',
    details='Defaults to the registered project that contains this folder. '
            'Set it to work on another project from here. Unset it to return to the folder\'s own project.',
))
