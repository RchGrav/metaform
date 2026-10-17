"""Settings: one schema drives parsing, validation, defaults, help, `config --show` and the settings screen, CLI-010.

A module declares its settings in its own code with `text`, `number`,
`boolean`, `items` and `choice`; the chassis records the module as owner while
it loads. Each setting is in one of three states: default, set, or glued,
CLI-013. A folder setting belongs to the folder it was set in and every folder
below it, CLI-014; a global setting applies everywhere. Nothing is written for
a default, CLI-023.
"""
from __future__ import annotations

import inspect
import os
import re
from collections.abc import Callable, Generator, Iterable, Mapping
from contextlib import contextmanager, suppress
from contextvars import ContextVar
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, NamedTuple, cast

from . import home
from .errors import PersonsDecision

KINDS = ('str', 'int', 'bool', 'list', 'select')

# The categories the settings screens group settings into, in the order a person comes to them: each a name, a title
# and a line saying what it holds. A setting names its own `category`; one that names none takes its module's
# `settings_category`, and the chassis's own take advanced.
CATEGORIES: tuple[tuple[str, str, str], ...] = (
    ('general', 'General', 'The project these settings are kept for, and where they apply.'),
    ('agents', 'Agents', 'Which agent works, when agents start, how many at once, and what they may do unasked.'),
    ('budgets', 'Budgets', 'How many tokens and how much money agents may spend, and what happens at the limit.'),
    ('agent_options', 'Agent options', "Each agent's own mode, model and effort, used when it starts."),
    ('map', 'Map and display', 'What the map shows and how the page draws it.'),
    ('voice', 'Voice and speech', 'Talking to Metaform, and the voice its agent answers with.'),
    ('phone', 'Phone', 'Talk with your system agent by phone, and be called or texted when something needs you.'),
    ('integrations', 'Integrations', 'A2A, Paperclip, Cloud, Node and Jev: other services Metaform works with.'),
    ('advanced', 'Advanced', 'Everything rarely changed, by module.'),
)
CATEGORY_NAMES = tuple(name for name, _, _ in CATEGORIES)
# A number's unit, read from the end of its key when it declares none: dispatch_wait_seconds is in seconds.
UNITS = {'seconds': 'seconds', 'minutes': 'minutes', 'hours': 'hours', 'days': 'days', 'ms': 'ms', 'kb': 'KB',
         'bytes': 'bytes'}


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
    # A setting that decides what agents may do or how they are started and overseen. MCP and a dispatched agent's
    # CLI refuse it unless the person has allowed agents to set control, so an agent cannot widen its own control.
    person_only: bool = False
    # A person_only setting that is part of the ordinary, reversible work of orchestration, such as Autostart agents:
    # the person's own system agent changes it without a consent card in a turn the person's own message in its chat
    # started (`metaform.module.persons_word`), and in no other turn, nor any other agent.
    on_persons_word: bool = False
    # A list whose entries are `<name><exclusive><value>`, such as `claude.model=opus` with `=`, holds one value per
    # name: two are refused, and a picker that checks one unchecks the others of its name.
    exclusive: str | None = None
    # A select's choices in plain words, each with what it does and what it risks, shown beside the choice wherever
    # it is picked; a choice without one shows as its value alone. A function of a Context reads them as choices are.
    choice_help: Mapping[str, str] | Callable[..., Mapping[str, str]] = field(default_factory=dict[str, str],
                                                                             compare=False)
    # Where the setting sits among its owner's, as a path of headings, such as `Agent options/Claude Code`: the
    # settings screen and the page group the settings of one section under it, a menu in a menu. None: at the top.
    section: str | None = None
    # A switch given on the call alone, never stored: a stored value would silently change later calls of another
    # kind, such as a transport, a dry run or the type of a blind-spot run. `set`, the settings screen, `config --show`
    # and the agent's set tool leave it out, and a value stored before it was marked is never read.
    per_call: bool = False
    # The choices that let an agent act without asking, such as approve-all: every surface asks the person to confirm
    # one before it is stored, and stepping through the choices never lands on one. A function of a Context reads
    # them as choices are, for choices an agent offers.
    risky: Callable[..., Iterable[str]] | tuple[str, ...] = field(default=(), compare=False)
    # The settings screen's category, one of CATEGORY_NAMES; None takes the module's `settings_category`.
    category: str | None = None
    # The small heading it sits under on its category's page, such as Starting work; None: its section, else its
    # module's name. Unlike a section it opens no menu of its own.
    heading: str | None = None
    # A place among the essentials, lower first: the settings screen opens on them, and CLI settings lists show
    # them first. 0 keeps it off Essentials. Only what a person needs for setup and day-to-day use is marked.
    essential: int = 0
    # What a number counts, such as minutes or cents, shown beside its control; None reads it from the key's end.
    unit: str | None = None
    # A list with choices refuses a member outside them, as a select does, CLI-019; True offers its choices and passes
    # any other member to its check, which says what it does, as layers keeps a name that is no layer yet, CLI-033.
    beyond_choices: bool = False
    # The command that reads a select's choices from their source while it offers no more than its default, such as an
    # agent's models, which it says only when it is started: the settings screens offer to run it, and a refused value
    # names it as the next step.
    choices_from: str | None = None

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

    def helps(self, folder: Path | None = None) -> dict[str, str]:
        """Each choice's plain words: the declared ones, or the owning module's function of a Context."""
        if callable(self.choice_help):
            from .context import build
            return dict(self.choice_help(build(self.owner, folder or Path.cwd())))
        return dict(self.choice_help)

    def risks(self, folder: Path | None = None) -> set[str]:
        """The choices that are confirmed before they are stored: the declared ones, or the owning module's function
        of a Context."""
        if callable(self.risky):
            from .context import build
            return {str(one) for one in self.risky(build(self.owner, folder or Path.cwd()))}
        return set(self.risky)

    def needs_project(self) -> bool:
        """A module's select reads its choices from the project's store, CLI-019; the chassis's never do."""
        return callable(self.choices) and self.owner != 'chassis'

    @property
    def type(self) -> type:
        return {'int': int, 'bool': bool, 'list': list}.get(self.kind, str)


SCHEMA: dict[str, Setting] = {}


TERMINAL = 'their own terminal window (an AI tool runs commands without the consent a terminal carries)'


def asking(folder: Path | None = None) -> tuple[str, str]:
    """How a refused agent gets the person's decision, and how the next step it is given begins: an agent asks the
    person in its chat with them; one whose role the person holds back (roles_without_authority, a worker by default)
    asks no one and says it in its ticket's note, for the person's own agent to ask (UX review, person-consent F2)."""
    role = os.environ.get('METAFORM_ROLE')
    if role and role in (value('roles_without_authority', folder or Path.cwd()) or ()):
        said = f"A {role} agent asks no one: say what you need in your ticket's note, and the person's own agent asks them."
        return said, 'metaform map work op=edit id=<your work id> note="..."; to do it the person '
    return ('Ask the person in your chat with them: say what you propose and why, then wait for their answer.',
            'ask the person in chat; to do it they ')


def on_persons_word(keys: Iterable[str]) -> bool:
    """Whether every person-only setting among `keys` is one the person's own system agent may change on the person's
    word in its chat (`Setting.on_persons_word`), and at least one is named."""
    held = [SCHEMA[key] for key in keys if key in SCHEMA and SCHEMA[key].person_only]
    return bool(held) and all(setting.on_persons_word for setting in held)


def refuse_held_control(keys: Iterable[str], folder: Path | None = None, command: str | None = None) -> None:
    """Refuse person-only settings to a call without the person's consent, unless the person lets agents set control.
    The refusal tells the agent how to ask the person, `asking`, and the person how to set it: the page's settings
    screen, or `command`, pasted into their own terminal (UX review, person-consent F2)."""
    if value('agents_may_set_control', folder or Path.cwd()):
        return
    held = sorted(key for key in keys if (setting := SCHEMA.get(key)) is not None and setting.person_only)
    if held:
        switches = ' '.join(f'{SCHEMA[key].switch} <value>' for key in held)
        said, step = asking(folder)
        only = [key for key in held if not SCHEMA[key].on_persons_word]
        worded = [key for key in held if SCHEMA[key].on_persons_word]
        told = [f'{", ".join(only)} {"is" if len(only) == 1 else "are"} set only by the person, never by an agent.'
                if only else '',
                f'{", ".join(worded)} {"is" if len(worded) == 1 else "are"} set by the person, or by their own system '
                f'agent {WORD_TURN}; this call is made in no such turn.' if worded else '']
        raise PersonsDecision(
            f'{" ".join(one for one in told if one)} {said}',
            f'{step}use the settings screen on the page, or paste into {TERMINAL}: '
            f'{command or "metaform set " + switches}')


# What lets the person's own system agent act on the person's word, said in each refusal of such an action
# (`metaform.module.on_persons_word`), so the agent, and the person, know what would allow it.
WORD_TURN = 'only in a turn the person\'s own message in its chat started (sent on the page, or at their terminal)'
WORD_COVERS = (f'Their own system agent acts on it {WORD_TURN}, and, in any later turn, on a ticket of the work it '
               'started, released, ordered or added to wait on others on that message, with the tickets that wait on '
               'it and the open tickets it waits on, or added later to wait only on tickets of that work, until that '
               'work is done or the person stops it.')


# The module the current thread is loading. It is per thread, not a process global: while one thread loads a module,
# another thread's own declarations, such as a direct import of a module package, keep their own owner.
_owner: ContextVar[str | None] = ContextVar('metaform_settings_owner', default=None)


@contextmanager
def owned_by(module: str) -> Generator[None, None, None]:
    """While a module loads, the settings it declares on this thread belong to it."""
    token = _owner.set(module)
    try:
        yield
    finally:
        _owner.reset(token)


_MODULE_NAME = re.compile(r'^(?:metaform\.modules\.|metaform_module_(?:system|user|project)_)([A-Za-z0-9_-]+)')


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
    if setting.category is not None and setting.category not in CATEGORY_NAMES:
        raise ValueError(f'Setting {setting.key}: category must be one of {", ".join(CATEGORY_NAMES)}.')
    owner = _owner.get() or _declaring_module() or setting.owner
    hyphens = setting.key.replace('_', '-')
    switches = setting.switches or ((f'--{hyphens}', f'--no-{hyphens}') if setting.kind == 'bool' else (f'--{hyphens}',))
    # A label not declared is the key in words, less its module's name, which the screens show as its heading
    named = setting.key[len(owner) + 1:] if setting.key.startswith(f'{owner}_') else setting.key
    unit = setting.unit or (UNITS.get(setting.key.rsplit('_', 1)[-1]) if setting.kind == 'int' else None)
    setting = replace(setting, owner=owner, group=setting.group or owner,
                      label=setting.label or named.replace('_', ' ').capitalize(), switches=tuple(switches),
                      unit=unit)
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
    """Resolve the scope once while the process registry is unchanged."""
    return home.registry_cached(('setting_scope', setting.key, setting.owner, setting.scope, setting.boundary, home.path_key(folder)),
                                lambda: _scope_of(setting, folder))


def _scope_of(setting: Setting, folder: Path) -> str:
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
    if setting.per_call:  # only the call gives it; a value stored before it was marked is never read
        return default(setting, folder)
    scope = scope_of(setting, folder)
    return _stored_value(setting, scope) if _has(scope, setting) else default(setting, folder)


def folder_of(scope: str) -> str:
    """A folder scope's path as it was stored, for saying where a value comes from; the scope itself when unknown."""
    with home.settings_db(scope) as db:
        row = db.execute('SELECT path FROM folders WHERE path_key=?', (scope,)).fetchone()
    return str(row[0]) if row else scope


def inherited_from(key: str, folder: Path) -> str | None:
    """The folder above whose stored or glued value this folder takes, or None when the value is this folder's own
    or the default, CLI-014."""
    setting = SCHEMA[key]
    scope = scope_of(setting, folder)
    if scope == own_scope_of(setting, folder):
        return None
    return folder_of(scope) if _has(scope, setting) or home.glued(scope, setting.owner, key) else None


def _inherited(setting: Setting, folder: Path, what: str) -> SettingError:
    """A change that would reach the folder above that holds the value, refused with that folder named: a folder acts
    only on its own value, CLI-014, so a subfolder never undoes the choice made for every folder below another."""
    source = inherited_from(setting.key, folder)
    return SettingError(f'{setting.key} is inherited from {source}; nothing is stored here to {what}.',
                        f'metaform unset {setting.switch} folder={source}')


def toggled_layers(folder: Path) -> list[str]:
    """The layers chosen for a folder with `--layers`, CLI-033 and LAYER-019, or an empty list with none chosen."""
    if 'layers' not in SCHEMA:
        return []
    chosen = value('layers', folder)
    return [str(item) for item in cast(list[Any], chosen)] if isinstance(chosen, list) else []


def state(key: str, folder: Path) -> str:
    """default, set or glued here, or inherited from a folder above, CLI-013 and CLI-014."""
    setting = SCHEMA[key]
    scope = scope_of(setting, folder)
    if scope != own_scope_of(setting, folder) and inherited_from(key, folder) is not None:
        return 'inherited'
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
        return _listed(setting, _members(setting, raw.split(','), text=True), folder)
    if setting.kind == 'select':
        options = setting.options(folder)
        if not options and setting.needs_project():
            from .context import project_for
            if folder is not None and project_for(folder) is None:
                raise SettingError(f'{setting.switch} has no choices here: this folder is not in a registered '
                                   'project.', 'metaform add project <id> <path>')
        if raw not in options:
            raise _no_choice(setting, [raw], options)
    return raw


def _no_choice(setting: Setting, wrong: list[str], options: list[str]) -> SettingError:
    """A value outside a setting's choices, refused with the choices listed, CLI-019. While a select offers no more
    than its default, the next step is the command that reads its choices from their source."""
    listed = ', '.join(option or "''" for option in options) if options else 'none yet'
    named = ', '.join(repr(one) for one in wrong)
    return SettingError(f'{setting.switch} has no choice {named}. Choices: {listed}.',
                        setting.choices_from if setting.choices_from and len(options) <= 1 else None)


def _listed(setting: Setting, members: list[str], folder: Path | None) -> list[str]:
    """A list with choices takes only its choices, as a select does; the word that clears a list shown as all when
    empty, `all`, and a list's own word for none, such as `none`, are among its choices or cleared before it is kept."""
    if setting.choices is None or setting.beyond_choices or not members or \
            (setting.key in EMPTY_IS_ALL and members == ['all']):
        return members
    options = setting.options(folder)
    wrong = [member for member in members if member not in options]
    if wrong:
        raise _no_choice(setting, wrong, options)
    return members


def _members(setting: Setting, given: Iterable[str], *, text: bool = False) -> list[str]:
    """A list's members, trimmed, with empty ones left out. A list of `<name><exclusive><value>` holds one value per
    name, and a member without the mark is refused, so a list item split at a comma on the command line is never
    stored as a broken entry."""
    items = [item.strip() for item in given if item.strip()]
    if setting.exclusive:
        mark = setting.exclusive
        unnamed = [item for item in items if mark not in item]
        if unnamed:
            raise SettingError(f'{setting.switch} takes items of the form <name>{mark}<value>; '
                               f'{", ".join(repr(item) for item in unnamed)} {"is" if len(unnamed) == 1 else "are"} '
                               f'not.' + (' On the command line a comma separates items.' if text else ''),
                               f'metaform help {setting.switch}')
        names = [item.partition(mark)[0].strip() for item in items]
        twice = sorted({name for name in names if names.count(name) > 1})
        if twice:
            raise SettingError(f'{setting.switch} holds one value for each name; {", ".join(twice)} '
                               f'{"is" if len(twice) == 1 else "are"} given more than one.')
    return items


def _typed(setting: Setting, typed: Any, folder: Path) -> Any:
    """A typed value, as the settings screen, the agent's set tool and the page give it, read and checked as `parse`
    reads its CLI text. A list is taken member by member as given, never joined into text and split again, so a
    member may hold a comma, CLI-027."""
    if setting.kind == 'bool':
        return bool(typed)
    if setting.kind == 'list' and isinstance(typed, list):
        return _listed(setting, _members(setting, (str(member) for member in cast(list[Any], typed))), folder)
    return parse(setting, str(typed), folder)


def calls_of(setting: Setting) -> list[str]:
    """The commands that take a setting's switch on the call, such as `metaform mcp serve --http`."""
    from . import loader
    return [f'metaform {item.id} {verb.name} {setting.switch}' for item in loader.discover() if item.module
            for verb in item.module.verbs if setting.key in verb.switches]


def _per_call(setting: Setting) -> SettingError:
    """A per-call switch is refused wherever a value would be stored, with the call that takes it."""
    verbs = calls_of(setting)
    return SettingError(f'{setting.switch} is given on the call alone and never stored: stored, it would change '
                        'every later call.', verbs[0] if verbs else f'metaform help {setting.switch}')


def risk(key: str, value: Any, folder: Path) -> str | None:
    """What a risky choice risks, in its own words, when `value` is one of the setting's risky choices; else None.
    Every surface confirms such a choice with the person before it is stored."""
    setting = SCHEMA[key]
    if setting.kind != 'select' or not setting.risky:
        return None
    try:
        risky = setting.risks(folder)
    except Exception:  # noqa: BLE001  a module's failing function still confirms a choice it cannot judge
        return f'{setting.key}: {value} could not be checked for its risk.'
    if str(value) not in risky:
        return None
    with suppress(Exception):
        if said := setting.helps(folder).get(str(value)):
            return said
    return f'{setting.key} {value} lets an agent act without asking you.'

class Assigned(NamedTuple):
    """A stored setting: its value before and after, and what did not fit and was kept, BASE-044."""
    old: Any
    new: Any
    notices: tuple[str, ...] = ()


EMPTY_IS_ALL = ('modules', 'layers', 'jev_decisions')  # shown as all when empty, CLI-031, and cleared when set to the word all


def _clears(setting: Setting, folder: Path) -> bool:
    """Whether the word all clears a value stored at this folder; refused when the value is held above, since an
    empty list is not stored apart from no choice, so all cannot be kept here over an inherited list."""
    if _has(own_scope_of(setting, folder), setting):
        return True
    if inherited_from(setting.key, folder) is not None:
        raise _inherited(setting, folder, 'clear')
    return False


def _store(setting: Setting, new: Any, folder: Path, glue: bool) -> Assigned:
    key = setting.key
    if setting.per_call:
        raise _per_call(setting)
    if key in EMPTY_IS_ALL and new in (['all'], []):
        # The word the setting is shown as when it is empty means the same when it is set: the setting is cleared.
        # Stored as the word, it named no module and no layer, and turned every one off.
        old = value(key, folder)
        if _clears(setting, folder):
            home.clear(own_scope_of(setting, folder), setting.owner, key)
        return Assigned(old, [], ())
    notices = (setting.check(new, folder) or []) if setting.check is not None else []
    old = value(key, folder)
    scope = own_scope_of(setting, folder)
    _save(setting, scope, new, folder)
    if glue:
        home.set_glue(scope, setting.owner, key, True, folder=folder.resolve())
    return Assigned(old, new, tuple(notices))


def assign(key: str, raw: Any, folder: Path, *, glue: bool = False) -> Assigned:
    """Store one setting from its CLI form, or a typed boolean."""
    setting = SCHEMA[key]
    return _store(setting, raw if setting.kind == 'bool' else parse(setting, raw, folder), folder, glue)


def put(key: str, typed: Any, folder: Path, *, glue: bool = False) -> Assigned:
    """Store one setting from a typed value, as the settings screen, the agent's set tool and the page do."""
    setting = SCHEMA[key]
    return _store(setting, _typed(setting, typed, folder), folder, glue)


def checked(key: str, value: Any, folder: Path, *, typed: bool = False) -> None:
    """Parse and check a value as `assign` or `put` would, storing nothing, so a `set` of several settings stores
    them only when every one fits. Raises `SettingError`."""
    setting = SCHEMA[key]
    if setting.per_call:
        raise _per_call(setting)
    if typed:
        new = _typed(setting, value, folder)
    else:
        new = value if setting.kind == 'bool' else parse(setting, value, folder)
    if key in EMPTY_IS_ALL and new in (['all'], []):  # it clears the setting, so there is no name to check
        _clears(setting, folder)
        return
    if setting.check is not None:
        setting.check(new, folder)


def glue(key: str, folder: Path, on: bool) -> None:
    """Glue or unglue a setting at this folder. Gluing a default keeps the default through unset all."""
    setting = SCHEMA[key]
    scope = own_scope_of(setting, folder)
    if not on and not home.glued(scope, setting.owner, key) and inherited_from(key, folder) is not None:
        raise _inherited(setting, folder, 'unglue')
    if on and not _has(scope, setting):
        _save(setting, scope, value(key, folder), folder)
    home.set_glue(scope, setting.owner, key, on, folder=folder.resolve())


def check_reset(key: str, folder: Path) -> None:
    """Refuse a reset whose value is held by a folder above, naming it, CLI-014: nothing is stored here to reset, and
    the folder above keeps its choice for every folder below it. Raises `SettingError`."""
    if state(key, folder) == 'inherited':
        raise _inherited(SCHEMA[key], folder, 'reset')


def reset(key: str, folder: Path, *, unglue: bool = False) -> tuple[str, bool]:
    """Reset one setting at this folder: (reset, skipped because glued, or unchanged) and whether it was unglued,
    CLI-016. A value held by a folder above is refused with that folder named, CLI-014."""
    setting = SCHEMA[key]
    check_reset(key, folder)
    scope = own_scope_of(setting, folder)
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


_carried: set[tuple[str, str]] = set()  # (home, step) carries this process saw done: a start reads the meta once


def carry_once(step: str, carry: Callable[[], list[str]]) -> list[str]:
    """Run a one-time carry of stored values out of a setting that was removed, merged or moved, once per home: the
    home's meta records `carried:<step>`, with what `carry` said it moved, once it returns. Two processes starting
    together carry once, under the home's carry lock. A carry that raises records nothing and runs at the next start.
    Settings cleanup, 2026-10-15: the marker is a meta row, never another file in the home."""
    seen = (str(home.home()), step)
    if seen in _carried:
        return []
    marker = f'carried:{step}'
    if home.meta(marker) is None:
        with home.file_lock(home.home() / 'carry.lock'):
            if home.meta(marker) is None:
                said = carry()
                home.set_meta(marker, '\n'.join(said) or 'nothing to carry')
                _carried.add(seen)
                return said
    _carried.add(seen)
    return []


def category_of(setting: Setting) -> str:
    """A setting's category on the settings screens: its own, else its module's `settings_category`, else advanced."""
    if setting.category is not None:
        return setting.category
    from . import loader
    found = next((item for item in loader.discover() if item.id == setting.owner and item.module is not None), None)
    declared = found.module.settings_category if found is not None and found.module is not None else None
    return declared or 'advanced'


def ordered() -> list[Setting]:
    """Stored settings in their shared display order: Essentials, categories, then the module filter.

    Within a category, owners and headings sort by name, the chassis follows modules, and settings under one
    heading keep their declaration order. A per-call switch has no stored setting to show.
    """
    categories = {name: index for index, name in enumerate(CATEGORY_NAMES)}

    def place(setting: Setting) -> tuple[int, int, bool, str, str]:
        if setting.owner == 'chassis' and setting.key == 'modules':
            return (2, 0, False, '', '')
        if setting.essential > 0:
            return (0, setting.essential, False, '', '')
        return (1, categories[category_of(setting)], setting.owner == 'chassis', setting.owner.casefold(),
                (setting.heading or setting.section or '').casefold())

    return sorted((setting for setting in SCHEMA.values() if not setting.per_call), key=place)


def describe(folder: Path, *, choices: bool = True) -> list[dict[str, Any]]:
    """Every stored setting as the screens show it; a per-call switch is no setting to store, so it is left out. An
    inherited value names the folder it comes from, and a select names its risky choices. `choices` False leaves out
    the choices, their words and the risky ones, which a module reads from its data, for a screen that reads them only
    when a setting's choices are opened: the settings TUI. One read of the registry serves the whole description."""
    described: list[dict[str, Any]] = []
    with home.registry_scope():
        resolved = folder.resolve()  # every scope a value here can come from, read once each
        home.preload_settings(['global', *(home.path_key(one) for one in (resolved, *resolved.parents))],
                              [(setting.owner, setting.key) for setting in SCHEMA.values()])
        for setting in ordered():
            key = setting.key
            entry = {'key': key, 'switch': setting.switch, 'owner': setting.owner, 'kind': setting.kind,
                     'scope': setting.scope, 'value': value(key, folder), 'default': default(setting, folder),
                     'state': state(key, folder), 'help': setting.help, 'label': setting.label,
                     'category': category_of(setting), 'heading': setting.heading, 'essential': setting.essential,
                     'unit': setting.unit, 'person_only': setting.person_only}
            if entry['state'] == 'inherited':
                entry['from'] = inherited_from(key, folder)
            if choices and setting.kind in ('select', 'list') and setting.choices is not None:
                with suppress(Exception):  # a module's failing choices function leaves the entry without them
                    entry['choices'] = setting.options(folder)
                    if setting.choices_from and len(entry['choices']) <= 1:
                        entry['choices_from'] = setting.choices_from
                with suppress(Exception):
                    if helps := setting.helps(folder):
                        entry['choice_help'] = helps
            if choices and setting.kind == 'select' and setting.risky:
                with suppress(Exception):
                    entry['risky'] = sorted(setting.risks(folder))
            described.append(entry)
    return described


def _project_root(folder: Path) -> Path | None:
    """A registered project's folder stops a project selection made above it from reaching inside, D57."""
    found = home.folder_project(folder)
    record = home.project(found) if found else None
    return Path(record.path) if record else None


def _module_choices(ctx: Any = None) -> list[str]:
    """The groups `modules` can name: the chassis and every discovered module, enabled or not."""
    from . import loader
    return ['chassis', *sorted({item.id for item in loader.discover()})]


def _check_modules(groups: Any, folder: Path) -> list[str] | None:
    known = _module_choices()
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
    store = Store(project_id)
    layers = {layer.name for layer in store.layers(limit=0).results}
    notices: list[str] = []
    for name in names:
        if name not in layers and not store.layers(tag=name, limit=0).results:
            notices.append(f'{name} is not a layer or a tag here; it was kept and turns nothing on. See metaform map '
                           'layers')
    return notices


def _project_choices(ctx: Any) -> list[str]:
    return [record.project_id for record in home.projects()]


project = choice('project', choices=_project_choices,
                 default_from=home.folder_project, boundary=_project_root, help='The project this folder works on.',
                 details="Defaults to the registered project that contains this folder. Set it to work on another "
                         "project from here. Unset it to return to the folder's own project.",
                 label='Project', category='general')

modules = items('modules', choices=_module_choices, beyond_choices=True, check=_check_modules,  # its check refuses
                help='Narrows which modules\' commands this folder shows and runs. It does not enable or disable '
                     'modules; use metaform enable and disable for that.')

def _server_choices(ctx: Any = None) -> list[str]:
    """Empty, which takes the sole provider, then each enabled module that declares an MCP server."""
    from . import loader
    return ['', *sorted(module.id for module in loader.enabled() if module.mcp_server is not None)]


install_server = choice('install_server', _server_choices, '', scope='global',
                      help='The enabled module whose MCP server install and provision use.',
                      details='Empty selects the sole enabled provider automatically. When several modules declare '
                              'a server, name one explicitly. With no provider, install sets up skills and '
                              'supported instructions and reminders without changing MCP registrations.')

def _layer_names(ctx: Any) -> list[str]:
    """The project's layers by name, then the tags they carry, read when the choices are needed."""
    if ctx.store is None:
        return []
    found = ctx.store.layers(limit=0).results
    names = [layer.name for layer in found]
    return [*names, *sorted({tag for layer in found for tag in layer.tags} - set(names))]


def _write_layers(ctx: Any) -> list[str]:
    """Empty, a new building layer for each write, then the project's layers by name."""
    return ['', *(layer.name for layer in ctx.store.layers(limit=0).results)] if ctx.store is not None else ['']


layers = items('layers', choices=_layer_names, beyond_choices=True, check=_check_layers,
               help='The layers toggled on in this folder, by name or tag. Empty means every finished layer that '
                    'is not hidden.',
               label='Layers shown', category='map', heading='Layers')

write_layer = choice('write_layer', _write_layers, '',
                   help='The layer a write that names no layer goes to. Empty means a new building layer '
                        'unnamed-<time> for each such write.',
                   details='A project wheel\'s first run sets it to the working layer it opens, so what a remote '
                           'agent writes travels back in one layer, BASE-060. A write that names its layer still goes '
                           'to the layer it names.',
                   label='Layer for unnamed writes', category='map', heading='Layers')

debug = boolean('debug', False, help='Ask agents doing Metaform work for feedback and trouble reports on the Metaform '
                                     'process.',
                label='Ask agents for feedback on Metaform')

connect_instructions = choice('connect_instructions', ['compact', 'full'], 'compact',
                              help='What agents get as instructions: compact lists each module in one line, full '
                                   'gives every module\'s whole instructions.',
                              details='Claude Code shows the first 2,048 characters of a server\'s instructions and '
                                      'drops the rest, so compact keeps them whole there, and each module\'s full '
                                      'instructions come from metaform_instructions with module set, at '
                                      'metaform://instructions/<module>, or with metaform help agents <module>. full serves them all at once, for hosts that show more.',
                              label='Instructions at connect')

agents_may_set_control = boolean(
    'agents_may_set_control', False, person_only=True,
    help='Let agents change the settings that control agents, such as the permission policy, over MCP.',
    details='Off, the default: over MCP an agent is refused the settings marked as the person\'s, and says what it '
            'needs in its ticket. On: an agent may set them, through the person\'s own permission policy like any '
            'other call. Only the person turns this on or off, on the command line or the page; it is a permission '
            'the person holds and can change, never a rule the person cannot get past, CLI-011.',
                                 label='Agents may change agent control', category='agents', heading='Permissions')

# The roles a dispatch runner gives the agent it starts, BASE-052: the intake, the agents the person summons, a merge
# preparation and a worker on its ticket. A session with no role is one the person runs outside dispatch.
AGENT_ROLES = ('intake', 'system', 'sentinel', 'talk', 'prep', 'worker')


def _check_roles(names: Any, folder: Path) -> list[str] | None:
    """A misspelt role would hold no agent back while seeming to, so it is refused, MAP-050. `none` alone holds back
    no role: an empty list is not stored apart from no choice, so the default would come back."""
    if list(names) == ['none']:
        return None
    for name in names:
        if name not in AGENT_ROLES:
            raise SettingError(f"--roles-without-authority has no role {name!r}. Roles: {', '.join(AGENT_ROLES)}.",
                               'metaform help --roles-without-authority')
    return None


roles_without_authority = items(
    'roles_without_authority', ('worker', 'prep'), person_only=True, check=_check_roles,
    choices=['none', *AGENT_ROLES], beyond_choices=True,  # _check_roles refuses another, in its own words
    help='The roles of the agents Metaform starts that may not write tickets or start, stop or message agents.',
    details='The default holds back a worker on its ticket and a merge preparation, so an agent at work does not '
            'assign itself or others work; the person, the agents that serve them (intake, system, sentinel, talk) '
            'and a session the person runs outside dispatch keep it. The page is the person\'s and is never held. '
            'Set to none, no role is held back. Only the person changes this, on the command line or the page; it is a '
            'permission the person holds, never a rule they cannot get past, MAP-050 and CLI-011.',
                                label='Roles without authority', category='agents', heading='Permissions')

gemini_reminder = choice('gemini_reminder', ['after-tool', 'off'], 'after-tool', scope='global',
                         help='Gemini setup installs a passive reminder after delegation and questioning, or none.',
                         details='BeforeTool cannot deliver passive context. after-tool reinforces later decisions. '
                                 'off keeps global instructions alone. Apply changes with metaform provision gemini '
                                 'or metaform install gemini.')

# Jev, the optional decision service, CHANGE-ORDER-2026-10-07 item 6 (P185): off until the person turns it on, since
# it sends project text over the network. The decision points `metaform.jev` offers other modules, each named in
# jev_decisions; a module's own decision point is named `<module>.<point>`.
JEV_DECISIONS = ('choose_agent', 'start_order', 'rank_items', 'triage', 'intake_coverage', 'session_drift')
MODULE_DECISION = re.compile(r'[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*')


def _check_jev_decisions(names: Any, folder: Path) -> list[str] | None:
    for name in names:
        if name not in JEV_DECISIONS and not MODULE_DECISION.fullmatch(str(name)):
            raise SettingError(f"--jev-decisions has no decision {name!r}. Decisions: {', '.join(JEV_DECISIONS)}, "
                               "or a module's own as <module>.<point>.", 'metaform help --jev-decisions')
    return None


jev = boolean(
    'jev', False, person_only=True,
    help='Let Metaform ask Jev, a decision model reached over the network, for typed decisions.',
    details='Off, the default: no decision is asked and every caller keeps its plain fallback. On: the decision '
            'points named in jev_decisions send the text they decide about to the endpoint jev_endpoint names, '
            'OpenRouter or TypeSafe, and act on the answer only when it is sure enough, jev_confidence. The key is read '
            'from the environment, OPENROUTER_API_KEY or TYPESAFE_API_KEY, and never stored; with no key nothing is '
            'sent. A decision that is acted on is kept at the Address it concerns, with its question, choices, answer, '
            'reason, model and cost. No decision hides anything from the person. Only the person turns this on, since '
            'it sends project text to a third party.',
              label='Ask Jev for decisions', category='integrations', heading='Jev')

jev_endpoint = choice('jev_endpoint', ['openrouter', 'typesafe'], 'openrouter', person_only=True,
                      help='Where Jev is asked: OpenRouter with OPENROUTER_API_KEY, or TypeSafe with TYPESAFE_API_KEY.',
                      label='Jev endpoint', category='integrations', heading='Jev')

# The model, the decision points and the confidence decide which agent runs a ticket, how agents are watched and what
# reaches the person first, and what project text is sent, so only the person sets them, CLI-011.
jev_model = text('jev_model', '', person_only=True,
                 help="The Jev model asked. Empty means the endpoint's default: typesafe/jev-1.13-20260917 on OpenRouter, "
                      'jev-1.13.0 on TypeSafe.',
                 details='An answer is cached under the model asked and the model that answered; when a name such as '
                         'typesafe/jev-1.13 starts answering as a newer snapshot, the answers of the older one are '
                         'asked again.',
                 label='Jev model', category='integrations', heading='Jev')

jev_decisions = items('jev_decisions', choices=list(JEV_DECISIONS), beyond_choices=True, check=_check_jev_decisions,
                      person_only=True,
                      help='Narrows which decision points ask Jev. Empty means every one.',
                      details="A module's own decision point is named <module>.<point>, as the module's README says.",
                      label='Decisions asked of Jev', category='integrations', heading='Jev')

jev_confidence = number('jev_confidence', 50, min=0, max=100, person_only=True,
                        help='The confidence, in percent, below which a Jev answer is not acted on.',
                        details="A choice's confidence is Jev's own; a yes or no is as confident as its probability "
                                'is far from even, so 50 leaves out answers between 0.25 and 0.75. Below it the '
                                'caller keeps its fallback; a kept decision is marked unsure.',
                        label='Jev confidence needed', category='integrations', heading='Jev', unit='%')
