"""intake: the Canonical Intake served by name, one atomic submission, and intake state, BASE-039.

A subagent reads `intake prompt`, performs the whole method on the artifact,
and submits the final shape once through `intake_submit`. The tool never parses
the intake's XML: it takes its own input schema, the metaform's general data
pattern, checks it, and stores it as one intake layer in one atomic write, so
a half-written intake never exists, MAP-040 and STORE-032.
"""
from __future__ import annotations

import json
import re
from importlib import resources
import secrets
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from metaform import settings
from metaform.data import Store
from metaform.module import Context, Module, Noun, Status, Stop, Verb

from .schema import ELEMENTS, check

SUPPORTED_OS = ('linux', 'macos', 'windows')
DEPENDENCIES = ()
SHIPS_DISABLED = False

RESOURCE = resources.files(__name__) / 'resources' / 'Canonical_Intake.xml'
SUBMIT_LINE = 'Submit the result with intake_submit, or metaform intake submit on the command line.'
NOTICE = ('This project has no intake yet. Have a subagent perform it. Tell the subagent to read its instructions '
          'with `metaform intake prompt`, or the `intake_prompt` tool, and to follow them.')
VARIABLE = ('The functional map of the artifact: its elements, and each receiver\'s purpose served by a provider\'s '
            'encounter function.')
TARGET = re.compile(r'<target\b[^>]*>')

settings.text('intake_file', '', help='An intake file to serve instead of the Canonical Intake. Empty means the '
                                      'Canonical Intake.')


def _escape(text: str) -> str:
    return text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')


def _fill(tag: str, name: str, value: str) -> str:
    attribute = re.compile(rf'(\s{name}=")[^"]*(")')
    if attribute.search(tag):
        return attribute.sub(lambda match: match.group(1) + _escape(value) + match.group(2), tag, count=1)
    return tag.replace('<target', f'<target {name}="{_escape(value)}"', 1)


def served(ctx: Context) -> str:
    """The intake text exactly as stored, with its target filled, then the submit line, BASE-039."""
    store = ctx.require_store()
    chosen = ctx.setting('intake_file')
    source: Any = Path(chosen) if chosen else RESOURCE
    try:
        text = source.read_text(encoding='utf-8')
    except OSError:
        raise Stop(f'No intake file at {source}.', 'metaform unset --intake-file') from None
    record = store.project()
    match = TARGET.search(text)
    if match is not None:
        tag = _fill(_fill(match.group(0), 'type', record.target_type), 'value', record.target_value)
        text = text[:match.start()] + tag + text[match.end():]
    text = text.replace('{project_id}', record.project_id)
    return text + ('\n' if text.endswith('\n') else '\n\n') + SUBMIT_LINE + '\n'


def prompt(ctx: Context) -> str:
    return served(ctx)


def _elements(ctx: Context) -> Any:
    given = ctx.nouns.get('elements')
    if not isinstance(given, str):
        return given
    try:
        text = sys.stdin.read() if given == '-' else Path(given).read_text(encoding='utf-8')
    except OSError:
        raise Stop(f'No file at {given}.', 'metaform intake submit elements=<path to a JSON file>') from None
    try:
        return json.loads(text)
    except ValueError:
        raise Stop(f'{given} is not JSON.', 'metaform intake submit elements=<path to a JSON file>') from None


def submit(ctx: Context) -> Any:
    """Check the submission, then store it in one atomic write as a new intake layer."""
    store = ctx.require_store()
    elements = _elements(ctx)
    known = set()
    if isinstance(elements, list):
        for element in elements:
            for join in element.get('joins', []) if isinstance(element, dict) else []:
                provider = join.get('provider') if isinstance(join, dict) else None
                if isinstance(provider, str) and store.element(provider, raw=True) is not None:
                    known.add(provider)
    problems = ['elements: is required'] if elements is None else check(elements, known)
    if 'id' in ctx.nouns and not isinstance(ctx.nouns['id'], str):
        problems.append('id: must be a string')
    if problems:
        raise Stop('The submission cannot be stored:\n' + '\n'.join(f'  {problem}' for problem in problems),
                   'fix the listed fields and call intake_submit again')
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    name = f'intake-{stamp}-{secrets.token_hex(3)}'
    provenance = {'module': 'intake', 'workflow': 'canonical-intake', 'prompt': served(ctx),
                  'model': ctx.nouns.get('model'), 'role': ctx.nouns.get('role'), 'blinded': ctx.nouns.get('blinded')}
    counts = {'elements': 0, 'joins': 0, 'subtypes': 0, 'refs': 0}
    with store.atomic():
        store.layer(name, 'intake', VARIABLE, kind='intake', mutable=False, hideable=False, provenance=provenance,
                    result_id=ctx.nouns.get('id'), ready=True)
        seen: set[str] = set()
        for element in elements:
            address = element['namespace_address']
            refs = [(ref['key'], ref['value']) for ref in element.get('refs', [])]
            store.add_element(name, address, name=element.get('name'), name_length=element.get('name_length'),
                              role=element.get('role'), refs=refs)
            if address not in seen:
                seen.add(address)
                counts['elements'] += 1
                counts['refs'] += len(refs)
        for element in elements:
            for join in element.get('joins', []):
                refs = [(ref['key'], ref['value']) for ref in join.get('refs', [])]
                made = store.add_join(name, element['namespace_address'], join['provider'], purpose=join['purpose'],
                                      function=join['function'], relation=join['relation'],
                                      observation=join['observation'], non_goal=join.get('non_goal'),
                                      type=join.get('type', 'purpose'), refs=refs)
                counts['joins'] += 1
                counts['refs'] += len(refs)
                for subtype in join.get('subtypes', []):
                    inner = subtype['element']
                    sub_refs = [(ref['key'], ref['value']) for ref in inner.get('refs', [])]
                    store.add_subtype(name, made.join_id, inner['namespace_address'], function=subtype['function'],
                                      relation=subtype['relation'], observation=subtype['observation'],
                                      name=inner.get('name'), name_length=inner.get('name_length'),
                                      role=inner.get('role'), refs=sub_refs)
                    counts['subtypes'] += 1
                    counts['refs'] += len(sub_refs)
    return {'layer': name, 'project': ctx.project, **counts}


def status_verb(ctx: Context) -> str:
    store = ctx.require_store()
    intakes = store.layers(kind='intake', limit=0).results
    if not intakes or not store.has_intake():
        return 'No intake yet. Read the instructions with metaform intake prompt.\n'
    return f'This project has an intake. Latest intake layer: {intakes[-1].name}\n'


def status(ctx: Context) -> Status:
    if ctx.store is None:
        return Status()
    if ctx.store.has_intake():
        return Status(lines=('Intake: complete',))
    return Status(lines=('Intake: none yet',), notice=NOTICE)


MODULE = Module(
    id='intake',
    summary='Serve the Canonical Intake and store its result.',
    purpose='Serves the Canonical Intake instructions and tracks whether this project has an intake. The intake is '
            'agent work: a subagent reads its instructions with intake_prompt and follows them. '
            'Details: metaform help intake.',
    details='The intake text is served unchanged except for its filled target. The result is submitted once, '
            'after the whole method, and stored as one intake layer in one atomic write.',
    verbs=(
        Verb('prompt', prompt, 'The Canonical Intake instructions for this project.'),
        Verb('submit', submit, "Store an intake's final shape, once, as one intake layer.",
             nouns=(Noun('elements', 'The elements, each holding its joins: over MCP the array, on the command line '
                                     'a path to a JSON file holding it, or - for standard input.', required=False,
                         schema=ELEMENTS),
                    Noun('id', "The result's generated id.", required=False),
                    Noun('model', 'The model that performed the intake.', required=False),
                    Noun('role', 'The role of the agent that performed it.', required=False),
                    Noun('blinded', 'Whether the agent saw only the map.', kind='bool', required=False))),
        Verb('status', status_verb, 'Whether this project has an intake, and its latest intake layer.'),
    ),
    status=status,
)
