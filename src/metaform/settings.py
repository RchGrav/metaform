"""Settings: one schema drives parsing, validation, defaults, help, `config --show` and the settings screen, CLI-010.

A module declares its settings in its own code with `text`, `number`,
`boolean`, `items` and `choice`; the chassis records the module as owner while
it loads. Each setting is in one of three states: default, set, or glued,
CLI-013. A folder setting belongs to the folder it was set in and every folder
below it, CLI-014; a global setting applies everywhere. Nothing is written for
a default, CLI-023.
"""
from __future__ import annotations

import re
import inspect
from collections.abc import Callable, Generator
from contextlib import contextmanager
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, NamedTuple, cast

from . import home

KINDS = ('str', 'int', 'bool', 'list', 'select')


class SettingError(ValueError):
    """A value a setting cannot take. It carries the one next step."""

    def __init__(self, message: str, next_step: str | None = None) -> None:
        super().__init__(message)
        self.next_step = next_step


@dataclass(frozen=True)
class Setting:
    key: str
    default: Any = None
    kind: str = 'str'
    group: str | None = None
    label: str | None = None
    help: str = ''
    details: str = ''
    switches: tuple[str, ...] = ()
    short: str | None = None
    choices: Callable[..., list[str]] | list[str] | tuple[str, ...] | None = field(default=None, compare=False)
    min: int | None = None
    max: int | None = None
    scope: str = 'folder'
    owner: str = 'chassis'
    default_from: Callable[[Path], Any] | None = field(default=None, compare=False)
    check: Callable[[Any, Path], list[str] | None] | None = field(default=None, compare=False)
    boundary: Callable[[Path], Path | None] | None = field(default=None, compare=False)

    @property
    def switch(self) -> str:
        """The long switch help shows first."""
        return self.switches[0]

    @property
    def negative(self) -> str | None:
        """A boolean's `--no-` form, CLI-015."""
        return next((item for item in self.switches if item.startswith('--no-')), None)

    def options(self, folder: Path | None = None) -> list[str]:
        """The current choices of a select: a fixed list, or the owning module's function of a Context, CLI-019."""
        if callable(self.choices):
            from .context import build
            return list(self.choices(build(self.owner, folder or Path.cwd())))
        return list(self.choices or [])

    def needs_project(self) -> bool:
        """A module's select reads its choices from the project's store, CLI-019; the chassis's never do."""
        return callable(self.choices) and self.owner != 'chassis'

    @property
    def type(self) -> type:
        return {'int': int, 'bool': bool, 'list': list}.get(self.kind, str)


SCHEMA: dict[str, Setting] = {}
_owner: str | None = None


@contextmanager
def owned_by(module: str) -> Generator[None, None, None]:
    """While a module loads, the settings it declares belong to it."""
    global _owner
    previous, _owner = _owner, module
    try:
        yield
    finally:
        _owner = previous


_MODULE_NAME = re.compile(r'^(?:metaform\.modules\.|metaform_module_(?:system|user)_)([A-Za-z0-9_-]+)')


def _declaring_module() -> str | None:
    """The module whose code made the declaration, however its package was imported, such as by a test runner.

    Only the frame that called `declare` or one of its helpers counts: a chassis setting declared while a module's
    import first loads this file stays the chassis's, BASE-029.
    """
    frame = inspect.currentframe()
    while frame is not None and frame.f_globals.get('__name__') == __name__ and frame.f_code.co_name in _DECLARING:
        frame = frame.f_back
    if frame is None:
        return None
    match = _MODULE_NAME.match(str(frame.f_globals.get('__name__', '')))
    return match.group(1) if match else None


_DECLARING = ('_declaring_module', 'declare', 'text', 'number', 'boolean', 'items', 'choice')


def declare(setting: Setting) -> Setting:
    if setting.key == 'confirm':
        raise ValueError('confirm is never a setting; it is a one-call switch of caution verbs, CLI-018.')
    if setting.kind not in KINDS:
        raise ValueError(f'Setting {setting.key}: kind must be one of {", ".join(KINDS)}.')
    owner = _owner or _declaring_module() or setting.owner
    hyphens = setting.key.replace('_', '-')
    switches = setting.switches or ((f'--{hyphens}', f'--no-{hyphens}') if setting.kind == 'bool' else (f'--{hyphens}',))
    setting = replace(setting, owner=owner, group=setting.group or owner,
                      label=setting.label or setting.key.replace('_', ' ').capitalize(), switches=tuple(switches))
    existing = SCHEMA.get(setting.key)
    if existing is not None and existing.owner != setting.owner:
        raise ValueError(f'Setting {setting.switch} already belongs to {existing.owner}.')
    SCHEMA[setting.key] = setting
    return setting


def text(key: str, default: str = '', **common: Any) -> Setting:
    return declare(Setting(key=key, default=default, kind='str', **common))


def number(key: str, default: int = 0, *, min: int | None = None, max: int | None = None, **common: Any) -> Setting:
    return declare(Setting(key=key, default=default, kind='int', min=min, max=max, **common))


def boolean(key: str, default: bool = False, **common: Any) -> Setting:
    return declare(Setting(key=key, default=default, kind='bool', **common))


def items(key: str, default: tuple[str, ...] | list[str] = (), **common: Any) -> Setting:
    return declare(Setting(key=key, default=list(default), kind='list', **common))


def choice(key: str, choices: Callable[..., list[str]] | list[str], default: str | None = None,
           **common: Any) -> Setting:
    return declare(Setting(key=key, default=default, kind='select', choices=choices, **common))


def by_switch(switch: str) -> tuple[Setting, bool] | None:
    """The setting a long or short switch names, and whether it is a boolean's `--no-` form."""
    for setting in SCHEMA.values():
        if switch in setting.switches:
            return setting, switch == setting.negative
        if setting.short and switch == f'-{setting.short}':
            return setting, False
    return None


# Scopes and values ------------------------------------------------------------

def own_scope_of(setting: Setting, folder: Path) -> str:
    return 'global' if setting.scope == 'global' else home.path_key(folder)


def _has(scope: str, setting: Setting) -> bool:
    return home.stored(scope, setting.owner, setting.key) is not None


def scope_of(setting: Setting, folder: Path) -> str:
    """Where this folder's value lives: the nearest folder at or above it that holds one, CLI-014."""
    if setting.scope == 'global':
        return 'global'
    folder = folder.resolve()
    stop = setting.boundary(folder) if setting.boundary else None
    for candidate in (folder, *folder.parents):
        scope = home.path_key(candidate)
        if _has(scope, setting) or home.glued(scope, setting.owner, setting.key):
            return scope
        if stop is not None and home.path_key(candidate) == home.path_key(stop):
            break
    return home.path_key(folder)


def default(setting: Setting, folder: Path) -> Any:
    return setting.default_from(folder) if setting.default_from else setting.default


def _stored_value(setting: Setting, scope: str) -> Any:
    members = home.stored(scope, setting.owner, setting.key)
    if members is None:
        return None
    return list(members) if setting.kind == 'list' else members[0]


def value(key: str, folder: Path) -> Any:
    setting = SCHEMA[key]
    scope = scope_of(setting, folder)
    return _stored_value(setting, scope) if _has(scope, setting) else default(setting, folder)


def state(key: str, folder: Path) -> str:
    setting = SCHEMA[key]
    scope = scope_of(setting, folder)
    if home.glued(scope, setting.owner, key):
        return 'glued'
    return 'set' if _has(scope, setting) else 'default'


def _save(setting: Setting, scope: str, new: Any, folder: Path) -> None:
    members = list(new) if setting.kind == 'list' else [new]
    home.save(scope, setting.owner, setting.key, members, folder=None if scope == 'global' else folder.resolve())


def parse(setting: Setting, raw: str, folder: Path | None = None) -> Any:
    """A value from its CLI form, CLI-027."""
    if setting.kind == 'int':
        try:
            number_value = int(raw)
        except ValueError:
            raise SettingError(f'{setting.switch} needs a whole number, not {raw!r}.') from None
        if setting.min is not None and number_value < setting.min:
            raise SettingError(f'{setting.switch} is at least {setting.min}.')
        if setting.max is not None and number_value > setting.max:
            raise SettingError(f'{setting.switch} is at most {setting.max}.')
        return number_value
    if setting.kind == 'bool':
        raise SettingError(f'{setting.switch} takes no value: use {setting.switch} or {setting.negative}.')
    if setting.kind == 'list':
        return [item.strip() for item in raw.split(',') if item.strip()]
    if setting.kind == 'select':
        options = setting.options(folder)
        if not options and setting.needs_project():
            from .context import project_for
            if folder is not None and project_for(folder) is None:
                raise SettingError(f'{setting.switch} has no choices here: this folder is not in a registered '
                                   'project.', 'metaform add project <id> <path>')
        if raw not in options:
            listed = ', '.join(options) if options else 'none yet'
            raise SettingError(f'{setting.switch} has no choice {raw!r}. Choices: {listed}.')
    return raw


class Assigned(NamedTuple):
    """A stored setting: its value before and after, and what did not fit and was kept, BASE-044."""
    old: Any
    new: Any
    notices: tuple[str, ...] = ()


def assign(key: str, raw: Any, folder: Path, *, glue: bool = False) -> Assigned:
    """Store one setting from its CLI form, or a typed boolean."""
    setting = SCHEMA[key]
    new = raw if setting.kind == 'bool' else parse(setting, raw, folder)
    notices = (setting.check(new, folder) or []) if setting.check is not None else []
    old = value(key, folder)
    scope = own_scope_of(setting, folder)
    _save(setting, scope, new, folder)
    if glue:
        home.set_glue(scope, setting.owner, key, True, folder=folder.resolve())
    return Assigned(old, new, tuple(notices))


def _raw(setting: Setting, typed: Any) -> Any:
    """A typed value in the form `assign` reads: the CLI text, or a boolean."""
    if setting.kind == 'list' and isinstance(typed, list):
        return ','.join(str(member) for member in cast(list[Any], typed))
    if setting.kind == 'bool':
        return bool(typed)
    return str(typed)


def put(key: str, typed: Any, folder: Path, *, glue: bool = False) -> Assigned:
    """Store one setting from a typed value, as the settings screen does."""
    return assign(key, _raw(SCHEMA[key], typed), folder, glue=glue)


def checked(key: str, value: Any, folder: Path, *, typed: bool = False) -> None:
    """Parse and check a value as `assign` or `put` would, storing nothing, so a `set` of several settings stores
    them only when every one fits. Raises `SettingError`."""
    setting = SCHEMA[key]
    raw = _raw(setting, value) if typed else value
    new = raw if setting.kind == 'bool' else parse(setting, raw, folder)
    if setting.check is not None:
        setting.check(new, folder)


def glue(key: str, folder: Path, on: bool) -> None:
    """Glue or unglue a setting. Gluing a default keeps the default through unset all."""
    setting = SCHEMA[key]
    scope = scope_of(setting, folder) if not on else own_scope_of(setting, folder)
    if on and not _has(scope, setting):
        _save(setting, scope, value(key, folder), folder)
    home.set_glue(scope, setting.owner, key, on, folder=folder.resolve())


def reset(key: str, folder: Path, *, unglue: bool = False) -> tuple[str, bool]:
    """Reset one setting: (reset, skipped because glued, or unchanged) and whether it was unglued, CLI-016."""
    setting = SCHEMA[key]
    scope = scope_of(setting, folder)
    unglued = False
    if home.glued(scope, setting.owner, key):
        if not unglue:
            return 'skipped', False
        home.set_glue(scope, setting.owner, key, False)
        unglued = True
    if not _has(scope, setting):
        return 'unchanged', unglued
    home.clear(scope, setting.owner, key)
    return 'reset', unglued


def describe(folder: Path) -> list[dict[str, Any]]:
    return [{'key': key, 'switch': setting.switch, 'owner': setting.owner, 'kind': setting.kind,
             'scope': setting.scope, 'value': value(key, folder), 'default': default(setting, folder),
             'state': state(key, folder), 'help': setting.help}
            for key, setting in SCHEMA.items()]


def _project_root(folder: Path) -> Path | None:
    """A registered project's folder stops a project selection made above it from reaching inside, D57."""
    found = home.folder_project(folder)
    record = home.project(found) if found else None
    return Path(record.path) if record else None


def _check_modules(groups: Any, folder: Path) -> list[str] | None:
    from . import loader
    known = ['chassis', *sorted({item.id for item in loader.discover()})]
    for group in groups:
        if group not in known:
            raise SettingError(f"--modules has no group {group!r}. Groups: {', '.join(known)}.",
                               'metaform list modules')
    return None


def _check_layers(names: Any, folder: Path) -> list[str] | None:
    """A name that is neither a layer nor a tag is kept and turns nothing on, with a notice, CLI-033 and BASE-044."""
    if not names:
        return None
    from .context import project_for
    from .data import Store
    project_id = project_for(folder)
    if project_id is None:
        raise SettingError('--layers names layers of a project, and this folder is not in one.',
                           'metaform add project <id> <path>')
    layers = {layer.name: layer for layer in Store(project_id).layers(limit=0).results}
    notices: list[str] = []
    for name in names:
        if name in layers and layers[name].kind == 'correction':
            raise SettingError(f'{name} is a correction layer; correction layers are always applied.',
                               'metaform map layers')
        if name not in layers and not Store(project_id).layers(tag=name, limit=0).results:
            notices.append(f'{name} is not a layer or a tag here; it was kept and turns nothing on. See metaform map '
                           'layers')
    return notices


def _project_choices(ctx: Any) -> list[str]:
    return [record.project_id for record in home.projects()]


project = choice('project', choices=_project_choices,
                 default_from=home.folder_project, boundary=_project_root, help='The project this folder works on.',
                 details="Defaults to the registered project that contains this folder. Set it to work on another "
                         "project from here. Unset it to return to the folder's own project.")

modules = items('modules', check=_check_modules,
                help='Narrows which modules\' commands this folder shows and runs. It does not enable or disable '
                     'modules; use metaform enable and disable for that.')

layers = items('layers', check=_check_layers,
               help='The layers toggled on in this folder, by name or tag. Empty means every finished layer that '
                    'is not hidden.')

debug = boolean('debug', False, help='Ask agents doing Metaform work for feedback and trouble reports on the Metaform '
                                     'process.')

report = boolean('report', True, help='Ask the intake agent for a report on the project it examined.')
