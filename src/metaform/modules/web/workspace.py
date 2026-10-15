"""The web GUI's workspace: the toolbar, the panes and the named workspaces, served to the page under /api/workspace.

Modules declare toolbar items and panes in their `Module` and the chassis declares its own, `module.contributions`;
this file lays the person's saved arrangement over those defaults, and saves it back through the settings path, as
`metaform set` does, never to the settings table directly.

Three shapes, each kept as the JSON text of a global setting of the web module:

- the toolbar, `web_toolbar`: `{"toolbar": [[id, ...], ...], "extra": [id, ...]}`, each inner list one slot whose
  first tool shows and whose others are behind it, and `extra` the tools behind the toolbar's last slot;
- the layout, `web_layout`: `{"areas": {area: {"size": px|null, "groups": [{"id": name, "tabs": [id, ...],
  "active": id|null, "size": share|null}, ...]}}, "floating": [{"pane": id, "x", "y", "w", "h"}], "off": [id, ...]}`,
  the areas left, main, right and bottom; a pane in `off` keeps its place and is not drawn;
- the workspaces, `web_workspaces`: `{name: {"toolbar": ..., "layout": ...}}`, the person's own; `Default` is never
  stored, since it is the declarations' defaults, so it cannot be deleted and always holds every contribution.

An id is `<owner>.<id>`, the owner a module's id or `chassis`. The merge: what the saved arrangement names and is
contributed now stays where the person put it; what it names and is not contributed now, a disabled module's, is left
out of what the page reads but kept in the setting, so it comes back where it was; a contribution it does not name
lands in its declared place, beside its group wherever the person moved that group.
"""
from __future__ import annotations

import json
import re
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from metaform import events, home, settings
from metaform import module as chassis
from metaform.module import Pane, Stop, ToolbarItem

if TYPE_CHECKING:
    from .server import Handler

PREFIX = '/api/workspace'
DEFAULT = 'Default'
AREAS = ('left', 'main', 'right', 'bottom')  # where panes dock; `float` panes are in `floating`
# CSS px; main fills, and the right area is the side column's width as the page draws it, unless the person sizes it
AREA_SIZES: dict[str, int | None] = {'left': 360, 'main': None, 'right': None, 'bottom': 280}
NAME = re.compile(r'^[^\x00-\x1f]{1,40}$')
FILE_TYPES = {'.svg': 'image/svg+xml', '.md': 'text/markdown; charset=utf-8', '.txt': 'text/plain; charset=utf-8',
              '.html': 'text/html; charset=utf-8'}
KEYS = {'toolbar': 'web_toolbar', 'layout': 'web_layout'}

# The developer panes, offered only while the page's developer level is on, `metaform web start --web-debug <level>`
# or the web_debug setting: none of them exists otherwise, so a person who never asks for them never sees them.
DEVELOPER: tuple[Pane, ...] = (
    Pane('dev-prompts', 'Prompts sent', 'Read every prompt Metaform and each enabled module would send, exactly, with '
         'when it is sent and its size; read-only.', icon='file', page='dev-prompts', area='bottom', group='developer',
         visible=True, order=900, min_width=360, min_height=160),
    Pane('dev-trace', 'Traces', "Follow the page's reads, writes and the events it hears, with their times and, at "
         'trace, the raw responses.', icon='gauge', page='dev-trace', area='bottom', group='developer', visible=True,
         order=910, min_width=360, min_height=160),
)


def _debugging() -> bool:
    from . import debug_level
    try:
        return debug_level() != 'off'
    except (settings.SettingError, KeyError):
        return False


Items = dict[str, tuple[str, ToolbarItem]]  # qualified id: (owner, declaration)
Panes = dict[str, tuple[str, Pane]]


# The shapes, checked ---------------------------------------------------------------------------------------------

def _ids(value: Any, where: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(one, str) for one in cast(list[Any], value)):
        raise settings.SettingError(f'{where} is a list of ids, each <owner>.<id>.')
    return list(cast(list[str], value))


def _object(value: Any, where: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise settings.SettingError(f'{where} is a JSON object.')
    return cast(dict[str, Any], value)


def _number(value: Any) -> bool:
    return value is None or (isinstance(value, (int, float)) and not isinstance(value, bool) and value >= 0)


def toolbar_shape(value: Any) -> dict[str, Any]:
    """A toolbar arrangement as stored: its slots and its extra tools, raising SettingError when it is not one."""
    found = _object(value, 'The toolbar')
    slots = found.get('toolbar', [])
    if not isinstance(slots, list):
        raise settings.SettingError('toolbar is a list of slots, each a list of ids.')
    return {'toolbar': [_ids(slot, 'Each slot') for slot in cast(list[Any], slots)],
            'extra': _ids(found.get('extra', []), 'extra')}


def layout_shape(value: Any) -> dict[str, Any]:
    """A layout as stored: its areas with their groups of tabs, its floating panes and the panes turned off."""
    found = _object(value, 'The layout')
    areas = _object(found.get('areas', {}), 'areas')
    unknown = sorted(set(areas) - set(AREAS))
    if unknown:
        raise settings.SettingError(f'The layout has no area {unknown[0]}; areas are {", ".join(AREAS)}.')
    shaped: dict[str, Any] = {}
    for name, area in areas.items():
        area = _object(area, f'Area {name}')
        groups: list[dict[str, Any]] = []
        for group in cast(list[Any], area.get('groups', [])) if isinstance(area.get('groups', []), list) else []:
            group = _object(group, f'A group of {name}')
            if not isinstance(group.get('id'), str) or not _number(group.get('size')) or \
                    not (group.get('active') is None or isinstance(group.get('active'), str)):
                raise settings.SettingError(f'A group of {name} has an id, its tabs, and may have active and size.')
            groups.append({'id': group['id'], 'tabs': _ids(group.get('tabs', []), 'tabs'),
                           'active': group.get('active'), 'size': group.get('size')})
        if not _number(area.get('size')):
            raise settings.SettingError(f'The size of {name} is a number of pixels, or null.')
        shaped[name] = {'size': area.get('size'), 'groups': groups}
    floating: list[dict[str, Any]] = []
    for one in cast(list[Any], found.get('floating', [])) if isinstance(found.get('floating', []), list) else []:
        one = _object(one, 'A floating pane')
        if not isinstance(one.get('pane'), str) or not all(_number(one.get(key)) for key in ('x', 'y', 'w', 'h')):
            raise settings.SettingError('A floating pane names its pane, and may give x, y, w and h in pixels.')
        floating.append({key: one.get(key) for key in ('pane', 'x', 'y', 'w', 'h')})
    return {'areas': shaped, 'floating': floating, 'off': _ids(found.get('off', []), 'off')}


def workspaces_shape(value: Any) -> dict[str, dict[str, Any]]:
    found = _object(value, 'The workspaces')
    shaped: dict[str, dict[str, Any]] = {}
    for name, saved in found.items():
        if not NAME.fullmatch(name) or name.strip().casefold() == DEFAULT.casefold():
            raise settings.SettingError(f'{name!r} cannot name a workspace: one line of 1 to 40 characters, and '
                                        f'never {DEFAULT}, which is the defaults.')
        saved = _object(saved, f'Workspace {name}')
        shaped[name] = {'toolbar': toolbar_shape(saved.get('toolbar', {})),
                        'layout': layout_shape(saved.get('layout', {}))}
    return shaped


def _parsed(text: Any, shape: Any) -> Any:
    """A setting's JSON text in its shape; empty text is the defaults, None."""
    if not isinstance(text, str) or not text.strip():
        return None
    try:
        found = json.loads(text)
    except ValueError:
        raise settings.SettingError('The value is not JSON.', 'metaform unset it to return to the defaults') \
            from None
    return shape(found)


def check_toolbar(value: Any, folder: Path) -> list[str] | None:
    _parsed(value, toolbar_shape)
    return None


def check_layout(value: Any, folder: Path) -> list[str] | None:
    _parsed(value, layout_shape)
    return None


def check_workspaces(value: Any, folder: Path) -> list[str] | None:
    _parsed(value, workspaces_shape)
    return None


def workspace_choices(ctx: Any = None) -> list[str]:
    """Default first, then the person's own workspaces, for `web_workspace`."""
    try:
        saved: dict[str, Any] = _parsed(settings.value('web_workspaces', home.home()), workspaces_shape) or {}
    except (settings.SettingError, KeyError):
        saved = {}
    return [DEFAULT, *sorted(saved)]


# What is contributed, and the defaults -----------------------------------------------------------------------------

def contributed(folder: Path) -> tuple[Items, Panes]:
    """Every toolbar item and pane the folder's surface offers, by qualified id; a tool whose pane is not offered is
    left out, since it would open nothing."""
    items: Items = {}
    panes: Panes = {}
    for owner, toolbar, declared in chassis.contributions(folder):
        items.update({f'{owner}.{item.id}': (owner, item) for item in toolbar})
        panes.update({f'{owner}.{pane.id}': (owner, pane) for pane in declared})
    if _debugging():
        panes.update({f'web.{pane.id}': ('web', pane) for pane in DEVELOPER})
    return {key: (owner, item) for key, (owner, item) in items.items()
            if item.pane is None or _pane_id(owner, item.pane) in panes}, panes


def _pane_id(owner: str, named: str) -> str:
    return named if '.' in named else f'{owner}.{named}'


def merge_toolbar(saved: dict[str, Any] | None, items: Items) -> dict[str, Any]:
    """The toolbar the page draws: the saved slots and extra tools that are offered now, then each tool the
    arrangement does not name, in its declared place, joining the slot of its group where that group is."""
    saved = saved or {'toolbar': [], 'extra': []}
    slots = [[one for one in slot if one in items] for slot in cast(list[list[str]], saved['toolbar'])]
    slots = [slot for slot in slots if slot]
    extra = [one for one in cast(list[str], saved['extra']) if one in items]
    placed = {one for slot in slots for one in slot} | set(extra)

    def order(ident: str) -> tuple[int, str]:
        return items[ident][1].order, ident

    for ident in sorted((one for one in items if one not in placed), key=order):
        declared = items[ident][1]
        group = declared.group
        home_slot = next((slot for slot in slots if group and any(items[one][1].group == group for one in slot)),
                         None)
        if home_slot is not None:
            home_slot.append(ident)
        elif (group and any(items[one][1].group == group for one in extra)) or declared.placement == 'extra':
            at = next((index for index, one in enumerate(extra) if order(one) > order(ident)), len(extra))
            extra.insert(at, ident)
        else:
            at = next((index for index, slot in enumerate(slots) if order(slot[0]) > order(ident)), len(slots))
            slots.insert(at, [ident])
    return {'toolbar': slots, 'extra': extra}


def merge_layout(saved: dict[str, Any] | None, panes: Panes) -> dict[str, Any]:
    """The layout the page draws: the saved areas, groups, floating panes and panes turned off, holding only what is
    offered now, then each pane the layout does not name, in its declared group wherever that group now is, or in a
    group of its own in its declared area; one declared not visible starts turned off."""
    saved = saved or {'areas': {}, 'floating': [], 'off': []}
    stored = cast(dict[str, dict[str, Any]], saved['areas'])
    areas: dict[str, dict[str, Any]] = {}
    for name in AREAS:
        area = stored.get(name, {})
        groups = [{**group, 'tabs': [one for one in group['tabs'] if one in panes]}
                  for group in cast(list[dict[str, Any]], area.get('groups', []))]
        areas[name] = {'size': area.get('size', AREA_SIZES[name]), 'groups': [group for group in groups
                                                                                 if group['tabs']]}
    floating = [one for one in cast(list[dict[str, Any]], saved['floating']) if one['pane'] in panes]
    off = [one for one in cast(list[str], saved['off']) if one in panes]
    placed = {one for area in areas.values() for group in area['groups'] for one in group['tabs']}
    placed |= {one['pane'] for one in floating}

    def order(ident: str) -> tuple[int, str]:
        return panes[ident][1].order, ident

    for ident in sorted((one for one in panes if one not in placed), key=order):
        declared = panes[ident][1]
        if not declared.visible and ident not in off:
            off.append(ident)
        if declared.area == 'float':
            floating.append({'pane': ident, 'x': None, 'y': None, 'w': None, 'h': None})
            continue
        name = declared.group or declared.id
        found = next((group for area in areas.values() for group in area['groups'] if group['id'] == name), None)
        if found is None:
            groups = areas[declared.area]['groups']
            at = next((index for index, group in enumerate(groups) if order(group['tabs'][0]) > order(ident)),
                      len(groups))
            groups.insert(at, {'id': name, 'tabs': [ident], 'active': None, 'size': None})
            continue
        tabs = found['tabs']
        tabs.insert(next((index for index, one in enumerate(tabs) if order(one) > order(ident)), len(tabs)), ident)
    for area in areas.values():
        for group in area['groups']:
            shown = [one for one in group['tabs'] if one not in off]
            if group.get('active') not in shown:
                group['active'] = shown[0] if shown else None
    return {'areas': areas, 'floating': floating, 'off': off}


def kept_toolbar(new: dict[str, Any], old: dict[str, Any] | None, items: Items) -> dict[str, Any]:
    """What is saved: the page's toolbar, and from the setting before it each tool not offered now, so a module turned
    off and on again finds its tools where the person put them."""
    if not old:
        return new
    named = {one for slot in new['toolbar'] for one in slot} | set(new['extra'])
    away = [[one for one in slot if one not in items and one not in named] for slot in old['toolbar']]
    return {'toolbar': [*new['toolbar'], *(slot for slot in away if slot)],
            'extra': [*new['extra'], *(one for one in old['extra'] if one not in items and one not in named)]}


def kept_layout(new: dict[str, Any], old: dict[str, Any] | None, panes: Panes) -> dict[str, Any]:
    """What is saved: the page's layout, and from the setting before it each pane not offered now, in its group when
    the group is still there, otherwise in its own group in the area it was in."""
    if not old:
        return new
    areas: dict[str, dict[str, Any]] = {
        name: {'size': area.get('size'), 'groups': [dict(group) for group in cast(list[Any], area.get('groups', []))]}
        for name, area in cast(dict[str, dict[str, Any]], new['areas']).items()}
    named = {one for area in areas.values() for group in area['groups'] for one in group['tabs']}
    named |= {one['pane'] for one in new['floating']}
    for name, area in cast(dict[str, dict[str, Any]], old['areas']).items():
        for group in cast(list[dict[str, Any]], area.get('groups', [])):
            away = [one for one in group['tabs'] if one not in panes and one not in named]
            if not away:
                continue
            found = next((one for each in areas.values() for one in each['groups'] if one['id'] == group['id']), None)
            if found is not None:
                found['tabs'] = [*found['tabs'], *away]
            else:
                areas.setdefault(name, {'size': area.get('size'), 'groups': []})['groups'].append(
                    {**group, 'tabs': away})
    floating = [*new['floating'], *(one for one in old['floating'] if one['pane'] not in panes
                                    and one['pane'] not in named)]
    off = [*new['off'], *(one for one in old['off'] if one not in panes and one not in new['off'])]
    return {'areas': areas, 'floating': floating, 'off': off}


# What the page reads ------------------------------------------------------------------------------------------------

def _icon(owner: str, icon: str) -> dict[str, Any]:
    if icon.startswith('resources/'):
        return {'icon': None, 'icon_url': f'{PREFIX}/file/{owner}/{icon}'}
    return {'icon': icon, 'icon_url': None}


def item_record(ident: str, owner: str, item: ToolbarItem, folder: Path) -> dict[str, Any]:
    action: dict[str, Any] = {'kind': item.action}
    if item.verb is not None:
        verb = next(verb for verb in _module(owner, folder).verbs if verb.name == item.verb)
        action.update(verb=item.verb, arguments=dict(item.arguments), effect=verb.effect, caution=verb.caution)
        form = form_of(item, verb)
        if form:  # a tool that runs at once has none
            action['form'] = form
    elif item.pane is not None:
        action['pane'] = _pane_id(owner, item.pane)
    elif item.page is not None:
        action['page'] = item.page
    else:
        link = cast(str, item.link)
        action['url'] = f'{PREFIX}/file/{owner}/{link}' if link.startswith('resources/') else link
    return {'id': ident, 'owner': owner, 'title': item.title, 'description': item.description,
            **_icon(owner, item.icon), 'action': action, 'selection': item.selection, 'group': item.group,
            'placement': item.placement, 'order': item.order, 'shortcut': item.shortcut}


def form_of(item: ToolbarItem, verb: chassis.Verb) -> list[dict[str, Any]]:
    """What the person fills in before a verb tool runs, a small form: each of the verb's nouns that the tool's fixed
    arguments and the selection leave open, typed as the tool's schema types it, with its help as the field's hint.
    Empty when the tool runs at once."""
    fixed = {*item.arguments, *([item.selection] if item.selection else [])}
    fields: list[dict[str, Any]] = []
    for noun in verb.nouns:
        if noun.name in fixed:
            continue
        schema: dict[str, Any] = noun.schema or {}
        choices = cast(list[Any] | None, schema.get('enum'))
        fields.append({'name': noun.name, 'help': noun.help, 'kind': noun.kind, 'many': noun.many,
                       'required': noun.required or noun.help.startswith('Required'),
                       **({'choices': [str(one) for one in choices]} if choices else {})})
    return fields


def pane_record(ident: str, owner: str, pane: Pane) -> dict[str, Any]:
    content: dict[str, Any] = {'kind': pane.content}
    if pane.page is not None:
        content['page'] = pane.page
    elif pane.verb is not None:
        content.update(verb=pane.verb, arguments=dict(pane.arguments), url=f'{PREFIX}/pane?pane={ident}')
    else:
        resource = cast(str, pane.resource)
        content.update(url=f'{PREFIX}/file/{owner}/{resource}', type=FILE_TYPES[Path(resource).suffix])
    return {'id': ident, 'owner': owner, 'title': pane.title, 'description': pane.description,
            **_icon(owner, pane.icon), 'content': content, 'selection': pane.selection, 'area': pane.area,
            'group': pane.group or pane.id, 'visible': pane.visible, 'order': pane.order,
            'min_width': pane.min_width, 'min_height': pane.min_height}


def _module(owner: str, folder: Path) -> chassis.Module:
    found = next((one for one in chassis.surface(folder) if one.id == owner), None)
    if found is None:
        raise Stop(f'{owner} is not on this folder\'s surface.', f'metaform enable {owner}')
    return found


def _stored(key: str, shape: Any) -> Any:
    """A setting's value in its shape; a value that no longer fits, stored by an older Metaform, reads as the
    defaults rather than breaking the page."""
    try:
        return _parsed(settings.value(key, home.home()), shape)
    except settings.SettingError:
        return None


def state(folder: Path) -> dict[str, Any]:
    """Everything the page needs to draw and edit the workspace."""
    items, panes = contributed(folder)
    saved: dict[str, Any] = _stored('web_workspaces', workspaces_shape) or {}
    active = settings.value('web_workspace', home.home()) or DEFAULT
    return {
        'items': [item_record(ident, owner, item, folder) for ident, (owner, item) in items.items()],
        'panes': [pane_record(ident, owner, pane) for ident, (owner, pane) in panes.items()],
        'icons': list(chassis.ICONS), 'areas': [*AREAS, 'float'],
        'toolbar': merge_toolbar(_stored('web_toolbar', toolbar_shape), items),
        'layout': merge_layout(_stored('web_layout', layout_shape), panes),
        'defaults': {'toolbar': merge_toolbar(None, items), 'layout': merge_layout(None, panes)},
        'workspace': active if active == DEFAULT or active in saved else DEFAULT,
        'workspaces': [DEFAULT, *sorted(saved)],
        'view': view(),
    }


def view() -> dict[str, Any]:
    """How the page draws, from the web module's global settings: node shapes, how long the 3D map's flow lasts once
    nothing moves, whether it keeps flowing slowly, whether agents' real activity is drawn in the flow, and the
    developer level, off unless asked for."""
    from . import debug_level
    where = home.home()
    return {'panes': bool(settings.value('web_panes', where)), 'shapes': bool(settings.value('web_node_shapes', where)),
            'flow_seconds': int(settings.value('web_flow_seconds', where) or 0),
            'pulse_ms': int(settings.value('web_pulse_ms', where) or 1500),
            'flow_mode': settings.value('web_flow_mode', where),
            'idle_flow': bool(settings.value('web_idle_flow', where)),
            'bubble_seconds': int(settings.value('web_bubble_seconds', where) or 5),
            'live_flow': bool(settings.value('web_live_flow', where)),
            'mascot': settings.value('web_mascot', where),
            'mascot_mischief': settings.value('web_mascot_mischief', where),
            'agent_glyphs': list(settings.value('web_agent_glyphs', where) or []),
            'map_direction': str(settings.value('web_map_direction', where) or 'auto'), 'debug': debug_level()}


# The endpoints --------------------------------------------------------------------------------------------------

def answer(handler: Handler, method: str, path: str, query: dict[str, list[str]]) -> None:
    """Route one request under /api/workspace. The server has checked its Host and token already."""
    given = {key: values[-1] for key, values in query.items() if key != 't'}
    if method == 'POST':
        return write(handler, path)
    if path == PREFIX:
        return _read(handler, given, lambda folder: handler.send(200, state(folder)))
    if path == f'{PREFIX}/pane':
        return _read(handler, given, lambda folder: pane_content(handler, folder, given))
    if path.startswith(f'{PREFIX}/file/'):
        return _read(handler, given, lambda folder: serve_file(handler, folder, path[len(PREFIX) + len('/file/'):]))
    handler.send(404, {'error': f'Nothing at {path}.'})


def _folder(given: dict[str, Any]) -> Path:
    """The project's folder, whose surface says what is offered; with no project named, the home's."""
    named = str(given.get('project') or '')
    if not named:
        return home.home()
    project = home.project(named)
    if project is None:
        raise Stop(f'No project {named} is registered.', 'metaform list projects')
    return Path(project.path)


def _read(handler: Handler, given: dict[str, Any], then: Callable[[Path], None]) -> None:
    try:
        then(_folder(given))
    except Stop as error:
        handler.refuse(error, 404 if str(error).startswith('No project') else 400)


def pane_content(handler: Handler, folder: Path, given: dict[str, str]) -> None:
    """A verb pane's content: its verb run with its arguments and the selection, as a tool call runs it, with the
    result, its JSON text and the length of that text, which is what an agent is handed."""
    from .server import module_verb
    _, panes = contributed(folder)
    found = panes.get(given.get('pane', ''))
    if found is None or found[1].verb is None:
        return handler.send(404, {'error': f'No pane {given.get("pane", "")} with a verb here.',
                                  'next': f'GET {PREFIX} lists the panes'})
    owner, pane = found
    arguments = dict(pane.arguments)
    if pane.selection is not None:
        if not given.get('selection'):
            return handler.send(400, {'error': f'{pane.title} follows the selection; select a node.',
                                      'next': 'send selection=<address>'})
        arguments[pane.selection] = given['selection']
    result = module_verb(given, owner, cast(str, pane.verb), arguments)
    text = chassis.result_json(result)
    handler.reply(200, json.dumps({'pane': given['pane'], 'result': json.loads(text), 'chars': len(text)})
                  .encode('utf-8'), 'application/json', {'Cache-Control': 'no-store'})


def serve_file(handler: Handler, folder: Path, rest: str) -> None:
    """A file a contribution names under its module's resources folder: an icon, a pane's file or a link. An HTML file
    is sent with the sandbox policy, so in its frame it runs with no reach into the page or the server."""
    owner, _, path = rest.partition('/')
    named = [one for who, toolbar, panes in chassis.contributions(folder) if who == owner
             for one in (*(item.icon for item in toolbar), *(item.link or '' for item in toolbar),
                         *(pane.icon for pane in panes), *(pane.resource or '' for pane in panes))]
    root = chassis.module_files(owner) if path in named else None
    target = root.joinpath(*path.split('/')) if root is not None else None
    if target is None or not target.is_file() or Path(path).suffix not in FILE_TYPES:
        return handler.send(404, {'error': f'No file {path} of {owner}.'})
    kind = FILE_TYPES[Path(path).suffix]
    policy = 'sandbox; default-src \'none\'; img-src data:; style-src \'unsafe-inline\''
    handler.reply(200, target.read_bytes(), kind, {'Cache-Control': 'no-cache', 'Content-Security-Policy': policy})


def write(handler: Handler, path: str) -> None:
    """One write of the workspace, from the GUI's own page only, with the checks every write of the server makes."""
    if not handler.same_origin():
        return handler.send(403, {'error': "A write is taken only from the web GUI's own page."})
    if (handler.headers.get('Content-Type') or '').split(';')[0].strip().lower() != 'application/json':
        return handler.send(415, {'error': 'A write takes a JSON body.'})
    writes = {f'{PREFIX}/arrangement': arrange, f'{PREFIX}/reset': reset, f'{PREFIX}/save': save,
              f'{PREFIX}/select': select, f'{PREFIX}/delete': delete}
    if path not in writes and path != f'{PREFIX}/run':
        return handler.send(404, {'error': f'No such write: {path}.'})
    try:
        body: Any = handler.json_body()
    except ValueError:
        return handler.send(400, {'error': 'The body is not JSON.'})
    given = cast(dict[str, Any], body) if isinstance(body, dict) else {}
    try:
        folder = _folder(given)
        if path == f'{PREFIX}/run':
            return run(handler, folder, given)
        writes[path](folder, given)
    except settings.SettingError as error:
        return handler.send(400, {'error': str(error), 'next': error.next_step})
    except Stop as error:
        return handler.refuse(error, 400)
    handler.gui.push({'topic': 'workspace', 'payload': {'workspace': settings.value('web_workspace', home.home())}})
    handler.send(200, state(folder))


def _put(key: str, value: Any) -> None:
    """Save one setting as `metaform set` saves it: checked, then stored for its scope; None returns it to its
    default as `metaform unset` does."""
    where = home.home()
    if value is None:
        settings.reset(key, where)
        return
    text = value if isinstance(value, str) else json.dumps(value, separators=(',', ':'))
    settings.checked(key, text, where)
    settings.assign(key, text, where)


def arrange(folder: Path, given: dict[str, Any]) -> None:
    """Save the page's toolbar, layout or both, as the person left them."""
    if 'toolbar' not in given and 'layout' not in given:
        raise Stop('An arrangement sends toolbar, layout or both.', 'send toolbar or layout')
    items, panes = contributed(folder)
    if 'toolbar' in given:
        _put('web_toolbar', kept_toolbar(toolbar_shape(given['toolbar']), _stored('web_toolbar', toolbar_shape),
                                         items))
    if 'layout' in given:
        _put('web_layout', kept_layout(layout_shape(given['layout']), _stored('web_layout', layout_shape), panes))


def _saved() -> dict[str, dict[str, Any]]:
    return _stored('web_workspaces', workspaces_shape) or {}


def _name(given: dict[str, Any]) -> str:
    name = given.get('name')
    if not isinstance(name, str) or not NAME.fullmatch(name.strip()):
        raise Stop('A workspace has a name of 1 to 40 characters on one line.', 'send name')
    return name.strip()


def reset(folder: Path, given: dict[str, Any]) -> None:
    """Return the toolbar, the layout or both to the active workspace as it was saved; for Default, to the defaults."""
    part = given.get('part')
    if part not in (None, 'toolbar', 'layout'):
        raise Stop('part is toolbar or layout, or left out for both.', 'send part')
    active = settings.value('web_workspace', home.home()) or DEFAULT
    snapshot = _saved().get(active)
    for which in ('toolbar', 'layout') if part is None else (part,):
        _put(KEYS[which], None if snapshot is None else snapshot[which])


def save(folder: Path, given: dict[str, Any]) -> None:
    """Save the current toolbar and layout as a workspace of the person's, replacing one of that name, and make it the
    active one. Default is the defaults and is never saved over."""
    name = _name(given)
    if name.casefold() == DEFAULT.casefold():
        raise Stop(f'{DEFAULT} is the defaults and cannot be saved over.', 'save under another name')
    items, panes = contributed(folder)
    saved = _saved()
    saved[name] = {'toolbar': kept_toolbar(merge_toolbar(_stored('web_toolbar', toolbar_shape), items),
                                           _stored('web_toolbar', toolbar_shape), items),
                   'layout': kept_layout(merge_layout(_stored('web_layout', layout_shape), panes),
                                         _stored('web_layout', layout_shape), panes)}
    _put('web_workspaces', saved)
    _put('web_workspace', name)


def select(folder: Path, given: dict[str, Any]) -> None:
    """Make a workspace the active one, its toolbar and layout the current ones."""
    name = _name(given)
    saved = _saved()
    if name != DEFAULT and name not in saved:
        raise Stop(f'No workspace {name}.', f'GET {PREFIX} lists them')
    snapshot = saved.get(name)
    _put('web_toolbar', None if snapshot is None else snapshot['toolbar'])
    _put('web_layout', None if snapshot is None else snapshot['layout'])
    _put('web_workspace', None if name == DEFAULT else name)


def delete(folder: Path, given: dict[str, Any]) -> None:
    """Delete a workspace of the person's. Default cannot be deleted; deleting the active one leaves the current
    arrangement as it is, now under Default."""
    name = _name(given)
    if name.casefold() == DEFAULT.casefold():
        raise Stop(f'{DEFAULT} is the defaults and cannot be deleted.', 'reset it instead')
    saved = _saved()
    if name not in saved:
        raise Stop(f'No workspace {name}.', f'GET {PREFIX} lists them')
    del saved[name]
    _put('web_workspaces', saved or None)
    if settings.value('web_workspace', home.home()) == name:
        _put('web_workspace', None)


def run(handler: Handler, folder: Path, given: dict[str, Any]) -> None:
    """Run a tool's verb, as a tool call runs it, with its fixed arguments and the selection: only a declared tool, so
    the page can run nothing else through here; behind a Node's gate, only for an account with the class its verb
    needs, server.verb_class. A caution verb runs only with confirm true, after the page has shown
    its caution. A write is announced as the server's other writes are, so every open page redraws."""
    from .server import module_verb, verb_class
    items, _ = contributed(folder)
    found = items.get(str(given.get('item', '')))
    if found is None or found[1].verb is None:
        return handler.send(404, {'error': f'No tool {given.get("item", "")} that runs a verb here.',
                                  'next': f'GET {PREFIX} lists the tools'})
    owner, item = found
    verb = next(verb for verb in _module(owner, folder).verbs if verb.name == item.verb)
    # Behind a Node's gate, the account needs the class the verb's effect calls for; the form adds only nouns, so the
    # tool's fixed arguments say whether it is given a setting only the person sets.
    if not handler.holds(verb_class(owner, verb, dict(item.arguments)), f'{PREFIX}/run {item.title}'):
        return
    if verb.caution and given.get('confirm') is not True:
        return handler.send(409, {'error': verb.caution, 'next': 'send confirm true if you are sure', 'confirm': True})
    arguments = dict(item.arguments)
    if item.selection is not None:
        if not isinstance(given.get('selection'), str) or not given['selection']:
            return handler.send(400, {'error': f'{item.title} acts on the selected node; select one.',
                                      'next': 'send selection'})
        arguments[item.selection] = given['selection']
    # What the person filled in, only the fields the tool's form offers: the fixed arguments and the selection stay
    # the tool's, so a form never runs the verb with more than its declaration lets it.
    values: Any = given.get('values') or {}
    if not isinstance(values, dict):
        return handler.send(400, {'error': 'values is an object of the form\'s fields.', 'next': 'send values'})
    offered = {field['name'] for field in form_of(item, verb)}
    unknown = sorted(set(cast(dict[str, Any], values)) - offered)
    if unknown:
        return handler.send(400, {'error': f'{item.title} has no field {unknown[0]}.',
                                  'next': f'GET {PREFIX} lists its form'})
    arguments.update({name: value for name, value in cast(dict[str, Any], values).items()
                      if value not in (None, '', [])})
    result = module_verb(given, owner, verb.name, arguments)
    if verb.effect != 'read':
        chassis.refresh_modules()
        for payload in events.announce(folder, 'web'):
            handler.gui.changed(dict(payload))
    handler.reply(200, json.dumps({'item': given['item'], 'result': json.loads(chassis.result_json(result))})
                  .encode('utf-8'), 'application/json', {'Cache-Control': 'no-store'})
