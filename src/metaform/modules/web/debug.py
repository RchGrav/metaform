"""The web GUI's developer reads, served only while the page's developer level is on (`metaform web start
--web-debug <level>` or the web_debug setting): nothing here answers otherwise.

`/api/debug/prompts?project=<id>` lists every prompt Metaform and each module enabled on the project's folder would
send, read from the prompt files exactly as the chassis reads them: the element's text with each place the code fills
shown as the empty element that marks it, the comment above it, which says who receives it and when, its size, and
the budget it is held to where one applies. It only reads: the shipped prompts are not edited at runtime.
"""
from __future__ import annotations

import os
import xml.etree.ElementTree as ET
from importlib import resources
from pathlib import Path
from typing import TYPE_CHECKING, Any

from metaform import home, settings
from metaform import module as chassis
from metaform.module import Stop

if TYPE_CHECKING:
    from .server import Handler

HOST_LIMIT = 2048  # the characters of a server's instructions Claude Code keeps, as server.HOST_LIMIT


def budget(owner: str, name: str, folder: Path) -> dict[str, Any] | None:
    """The budget a prompt is held to, by where it is sent: a module's connect line and mcp's instructions are the
    connect message, kept to the host's limit in characters; the glossary to glossary_bytes; what a node's brief is
    made of to node_summary_bytes. None where no budget is declared."""
    if name == 'connect' or (owner == 'mcp' and name == 'instructions'):
        return {'limit': HOST_LIMIT, 'unit': 'characters', 'of': 'the connect message, all of it together'}
    for key, prefixes in (('glossary_bytes', ('glossary', 'register')), ('node_summary_bytes', ('around', 'brief'))):
        if name.startswith(prefixes) and key in settings.SCHEMA:
            try:
                return {'limit': int(settings.value(key, folder)), 'unit': 'bytes', 'of': key}
            except (settings.SettingError, KeyError, TypeError, ValueError):
                return None
    return None


def prompts_of(owner: str, source: Any, folder: Path) -> list[dict[str, Any]]:
    """The prompts of one prompt file, in the file's order, each with the comment above it."""
    path = source / 'resources' / 'prompts.xml'
    if not path.is_file():
        return []
    text = path.read_text(encoding='utf-8')
    root = ET.fromstring(text, parser=ET.XMLParser(target=ET.TreeBuilder(insert_comments=True)))
    trial = os.environ.get('METAFORM_PROMPTS')
    found: list[dict[str, Any]] = []
    note = ''
    for element in root:
        if element.tag is ET.Comment:
            note = ' '.join(str(element.text or '').split())
            continue
        name = str(element.tag)
        said = ((element.text or '') + ''.join(f'<{child.tag}/>' + (child.tail or '') for child in element)).strip()
        size = len(said.encode('utf-8'))
        found.append({'owner': owner, 'name': name, 'source': f'{owner}/resources/prompts.xml <{name}>',
                      'when': note, 'text': said, 'bytes': size, 'characters': len(said),
                      'fills': [str(child.tag) for child in element], 'budget': budget(owner, name, folder),
                      'trial': bool(trial)})
        note = ''
    return found


def prompts(folder: Path) -> dict[str, Any]:
    """Every prompt the chassis and each module on the folder's surface would send."""
    found = prompts_of('chassis', resources.files('metaform'), folder)
    modules = [one.id for one in chassis.surface(folder)]
    for owner in modules:
        source = chassis.module_files(owner)
        if source is not None:
            found += prompts_of(owner, source, folder)
    connect = sum(int(one['characters']) for one in found if one['name'] == 'connect'
                  or (one['owner'] == 'mcp' and one['name'] == 'instructions'))
    return {'prompts': found, 'modules': modules, 'connect': {'characters': connect, 'limit': HOST_LIMIT},
            'editable': False}


def answer(handler: Handler, path: str, given: dict[str, str]) -> None:
    """Route one developer read; a 404 while the developer level is off, as if there were none."""
    from . import debug_level
    if debug_level() == 'off':
        return handler.send(404, {'error': f'Nothing at {path}.',
                                  'next': 'metaform web start --web-debug info, or metaform set --web-debug info'})
    if path != '/api/debug/prompts':
        return handler.send(404, {'error': f'Nothing at {path}.'})
    named = given.get('project', '')
    project = home.project(named) if named else None
    if named and project is None:
        return handler.send(404, {'error': f'No project {named} is registered.', 'next': 'metaform list projects'})
    try:
        handler.send(200, prompts(Path(project.path) if project is not None else home.home()))
    except Stop as error:
        handler.refuse(error, 400)
