"""The map module: import a project's functional map and read it.

Each element's joins are stored on that element, the receiver. An internal
subtype stays inside the join it serves; it is never a root element. The
original XML is kept whole as its own join, so nothing in the answer is lost.
"""
import json
import xml.etree.ElementTree as ET
from hashlib import sha256
from pathlib import Path

from metaform import settings
from metaform.module import Adverb, Module, Stop, Verb
from metaform.store import Store

SUPPORTED_OS = ('linux', 'macos', 'windows')

JOIN_FIELDS = ('type', 'provider', 'purpose', 'non_goal', 'function', 'relation', 'observation', 'role')
SUBTYPE_FIELDS = ('namespace_address', 'name_length', 'element_name', 'relation', 'function', 'observation', 'graph')


def reading(address):
    return ' '.join(reversed(address.split('.')))


def _project(ctx):
    project = settings.value('project', ctx.folder)
    if project is None:
        raise Stop('This folder has no project.', 'metaform add project <id> <path>')
    return Store(project)


def _refs(node):
    return [dict(ref.attrib) for ref in node.findall('refs/ref')]


def _subtypes(join):
    result = []
    for element in join.findall('elements/element'):
        if element.get('graph') != 'internal':
            continue
        item = {key: element.get(key) for key in SUBTYPE_FIELDS if element.get(key) is not None}
        item['name'] = (element.findtext('name') or element.get('element_name') or '').strip()
        item['refs'] = _refs(element)
        result.append(item)
    return result


def import_(ctx):
    if len(ctx.nouns) != 1:
        raise Stop('import needs one map file.', 'metaform map import <file.xml>')
    path = Path(ctx.nouns[0])
    path = path if path.is_absolute() else ctx.folder / path
    if not path.is_file():
        raise Stop(f'No file at {path}.', 'metaform map import <file.xml>')
    store = _project(ctx)
    text = path.read_text(encoding='utf-8')
    try:
        root = ET.fromstring(text)
    except ET.ParseError as error:
        raise Stop(f'{path.name} is not well-formed XML: {error}.', f'metaform map import <file.xml>') from None
    counts = {'elements': 0, 'joins': 0, 'subtypes': 0, 'changed': 0}
    top = root.find('elements')
    for element in (top if top is not None else root).findall('element'):
        address = element.get('namespace_address')
        if not address:
            continue
        length = int(element.get('name_length') or 1)
        record = {'id': 'element', 'type': 'element', 'role': element.get('role'), 'vested': element.get('vested'),
                  'name': (element.findtext('name') or '').strip(), 'notes': (element.findtext('notes') or '').strip()}
        counts['changed'] += store.put(address, record, name_length=length)['changed']
        counts['elements'] += 1
        for index, join in enumerate(element.findall('joins/join')):
            body = {key: join.get(key) for key in JOIN_FIELDS if join.get(key) is not None}
            body['id'] = f"{body.get('type', 'join')}:{body.get('provider', index)}"
            body['refs'] = _refs(join)
            body['subtypes'] = _subtypes(join)
            counts['subtypes'] += len(body['subtypes'])
            counts['changed'] += store.put(address, body, name_length=length)['changed']
            counts['joins'] += 1
    source = {'id': 'source', 'type': 'source', 'file': str(path), 'sha256': sha256(text.encode()).hexdigest(),
              'xml': text}
    counts['changed'] += store.put('project', source)['changed']
    ctx.say(f"Imported into {store.project}: {counts['elements']} elements, {counts['joins']} joins, "
            f"{counts['subtypes']} internal subtypes" + ('' if counts['changed'] else ' (unchanged)'))


def _map(store):
    records = store.latest()
    elements = {ref['address']: body for ref, body in records if body.get('type') == 'element'}
    joins = [(ref, body) for ref, body in records if body.get('provider')]
    return elements, joins


def _token(value):
    return str(value or '').split(' ', 1)[0].rstrip(',')


def _cites(value, path):
    """The ref names this file."""
    token = _token(value)
    return bool(token) and (token == path or token.endswith('/' + path) or path.endswith('/' + token))


def _contains(value, path):
    """The ref names a folder that holds this file."""
    token = _token(value).rstrip('/')
    return bool(token) and (path.startswith(token + '/') or ('/' + token + '/') in ('/' + path))


def _join_view(ref, body):
    return {'receiver': ref['address'], 'provider': body['provider'], 'revision': ref['revision'], 'ref': ref,
            **{key: body[key] for key in ('purpose', 'function', 'relation', 'observation', 'non_goal') if key in body},
            'refs': body.get('refs', [])}


def _emit(ctx, value, lines):
    if ctx.adverbs.get('--json'):
        ctx.say(json.dumps(value, indent=1, ensure_ascii=False))
    else:
        ctx.say('\n'.join(lines))


def where(ctx):
    if len(ctx.nouns) != 1:
        raise Stop('where needs one file path.', 'metaform map where <path>')
    path = ctx.nouns[0]
    _, joins = _map(_project(ctx))
    hits, within = [], []
    for ref, body in joins:
        folders = [item for item in body.get('refs', []) if item.get('key') in ('path', 'source')
                   and _contains(item.get('value'), path)]
        if folders:
            within.append({'address': body['provider'], 'receiver': ref['address'], 'refs': folders})
        cited = [item for item in body.get('refs', []) if item.get('key') in ('path', 'source') and _cites(item.get('value'), path)]
        if cited:
            hits.append({'kind': 'join', 'address': body['provider'], 'reading': reading(body['provider']),
                         'receiver': ref['address'], 'provider': body['provider'], 'purpose': body.get('purpose'),
                         'refs': cited})
        for sub in body.get('subtypes', []):
            cited = [item for item in sub.get('refs', []) if item.get('key') in ('path', 'source') and _cites(item.get('value'), path)]
            if cited:
                hits.append({'kind': 'subtype', 'address': sub['namespace_address'],
                             'reading': reading(sub['namespace_address']), 'receiver': ref['address'],
                             'provider': body['provider'], 'relation': sub.get('relation'), 'refs': cited})
    lines = [f"{hit['kind']:7}  {hit['address']}  ({hit['reading']})  in {hit['receiver']} -> {hit['provider']}"
             for hit in hits] or [f'No element or join cites {path}.']
    lines += [f"within   {item['address']}  (its folder ref covers this file)" for item in within]
    _emit(ctx, {'path': path, 'hits': hits, 'within': within}, lines)


def element(ctx):
    if len(ctx.nouns) != 1:
        raise Stop('element needs one address.', 'metaform map element <address>')
    address = ctx.nouns[0]
    elements, joins = _map(_project(ctx))
    if address in elements:
        record = elements[address]
        value = {'kind': 'element', 'namespace_address': address, 'reading': reading(address),
                 'role': record.get('role'), 'vested': record.get('vested'), 'name': record.get('name'),
                 'notes': record.get('notes'),
                 'owns': [_join_view(ref, body) for ref, body in joins if ref['address'] == address],
                 'provides': [_join_view(ref, body) for ref, body in joins if body['provider'] == address],
                 'subtypes': [dict(sub, receiver=ref['address']) for ref, body in joins
                              if body['provider'] == address for sub in body.get('subtypes', [])]}
        lines = [f"{address}  ({value['reading']})  role {value['role']}", value['name'] or '']
        lines += [f"  owns     -> {join['provider']}: {join.get('purpose', '')}" for join in value['owns']]
        lines += [f"  provides <- {join['receiver']}: {join.get('function', '')}" for join in value['provides']]
        lines += [f"  subtype  {sub['namespace_address']}: {sub.get('relation', '')}" for sub in value['subtypes']]
    else:
        found = next(((ref, body, sub) for ref, body in joins for sub in body.get('subtypes', [])
                      if sub.get('namespace_address') == address), None)
        if found is None:
            raise Stop(f'No element or internal subtype at {address}.', 'metaform map list')
        ref, body, sub = found
        value = {'kind': 'subtype', 'reading': reading(address), **sub,
                 'parent': {'receiver': ref['address'], 'provider': body['provider']}}
        lines = [f"{address}  ({value['reading']})  internal subtype in {ref['address']} -> {body['provider']}",
                 sub.get('relation', ''), sub.get('function', '')]
    _emit(ctx, value, [line for line in lines if line])


def list_(ctx):
    elements, _ = _map(_project(ctx))
    ctx.say('\n'.join(f"{address}  {record.get('role') or ''}" for address, record in sorted(elements.items()))
            or 'No map yet. Import one: metaform map import <file.xml>')


JSON = Adverb('--json', 'Print JSON.')

MODULE = Module(
    id='map',
    summary="Import a project's functional map and read it.",
    purpose="Holds the project's functional map: what each element is for, who receives it, and how. "
            'Use where to find the elements a file implements, and element to read one element before changing it.',
    details='Joins are stored on the element that receives them. Internal subtypes stay inside the join they '
            'serve. Importing a changed map adds new revisions; earlier revisions stay readable.',
    verbs=(
        Verb('import', import_, "Import a functional map into this folder's project.", nouns='<file.xml>'),
        Verb('where', where, 'Find the elements and joins that cite a file.', nouns='<path>', adverbs=(JSON,),
             examples=(('metaform map where src/mgm_safetynet.c', 'Shows the SafeNet join and its subtypes.'),)),
        Verb('element', element, 'Show an element: role, joins both ways, internal subtypes.', nouns='<address>',
             adverbs=(JSON,)),
        Verb('list', list_, 'List the root elements.'),
    ),
)
