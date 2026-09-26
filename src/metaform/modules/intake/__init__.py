"""intake: the Canonical Intake served by name, one atomic submission never blocked, and intake state, BASE-039.

A subagent reads `intake prompt`, performs the whole method on the artifact,
and submits the final shape once through `intake_submit`. The tool never parses
the intake's XML: it takes its own input schema, the metaform's general data
pattern, and stores it as one intake layer in one atomic write, so a
half-written intake never exists, MAP-040 and STORE-032. Nothing is refused for
its content: what does not fit is stored as given and named in a notice,
BASE-044. The intake report and process feedback are saved beside it, BASE-045.
"""
from __future__ import annotations

import json
import re
import secrets
import sys
from datetime import datetime, timezone
from importlib import resources
from pathlib import Path
from typing import Any, cast

from metaform import settings
from metaform.data import Store, prompts
from metaform.module import Context, Module, Noun, Status, Stop, Verb, save_report

from .schema import ELEMENTS
from .submission import Writer, unreadable

SUPPORTED_OS = ('linux', 'macos', 'windows')
DEPENDENCIES = ()
SHIPS_DISABLED = False

RESOURCE = resources.files(__name__) / 'resources' / 'Canonical_Intake.xml'
PROMPT = 'canonical-intake'  # the stored prompt the shipped file becomes, STORE-044
ALWAYS = ('Submit the result with intake_submit, or metaform intake submit on the command line. If you cannot '
          'continue, stop and submit a trouble report with the feedback tool, attaching what you have in its shape '
          'field; do not retry.')
REPORT_LINE = ('Include your report on the project you examined in the report field: broken code, things that need '
               'fixing, anything not working or partially working.')
DEBUG_LINE = ('Include feedback on this process in the feedback field: bad semantics, a tool that did not match its '
              'schema, where you got stuck.')
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


def footer(ctx: Context) -> str:
    """The submit lines: always the submit and stop rule, then the report and feedback requests, CLI-034."""
    lines = [ALWAYS]
    if ctx.setting('report'):
        lines.append(REPORT_LINE)
    if ctx.setting('debug'):
        lines.append(DEBUG_LINE)
    return '\n'.join(lines) + '\n'


def _source(ctx: Context) -> tuple[str, prompts.PromptVersion | None]:
    """The intake text: the `--intake-file` as it is, or the newest stored version of the Canonical Intake, which
    is the shipped file until someone saves an edit, STORE-044."""
    chosen = ctx.setting('intake_file')
    if chosen:
        try:
            return Path(chosen).read_text(encoding='utf-8'), None
        except OSError:
            raise Stop(f'No intake file at {chosen}.', 'metaform unset --intake-file') from None
    version = prompts.shipped(PROMPT, 'xml', RESOURCE.read_text(encoding='utf-8'))
    return version.text, version


def served(ctx: Context, text: str | None = None) -> str:
    """The intake text exactly as stored, with its target filled, then the submit lines, BASE-039."""
    store = ctx.require_store()
    if text is None:
        text = _source(ctx)[0]
    record = store.project()
    match = TARGET.search(text)
    if match is not None:
        tag = _fill(_fill(match.group(0), 'type', record.target_type), 'value', record.target_value)
        text = text[:match.start()] + tag + text[match.end():]
    text = text.replace('{project_id}', record.project_id)
    return text + ('\n' if text.endswith('\n') else '\n\n') + footer(ctx)


def prompt(ctx: Context) -> str:
    return served(ctx)


def _elements(ctx: Context) -> tuple[list[Any] | None, str]:
    """The submitted elements, or None and why they cannot be read. A file or standard input only on the CLI."""
    given = ctx.nouns.get('elements')
    if given is None:
        return None, 'elements is missing, so there is no map to store.'
    if isinstance(given, str):
        if ctx.surface != 'cli':
            return None, 'elements is text; over MCP it is the array of elements itself.'
        try:
            text = sys.stdin.read() if given == '-' else Path(given).read_text(encoding='utf-8')
        except OSError:
            return None, f'No file at {given}.'
        try:
            given = json.loads(text)
        except ValueError:
            return None, f'{"Standard input" if given == "-" else given} is not JSON.'
    if not isinstance(given, list):
        return None, 'elements is not an array of elements.'
    return cast(list[Any], given), ''


def _text_noun(ctx: Context, name: str, notices: list[dict[str, str]]) -> str | None:
    value = ctx.nouns.get(name)
    if value is None or isinstance(value, str):
        return value
    notices.append({'where': name, 'message': f'{name} is not text; it was stored as its JSON text.'})
    return json.dumps(value, ensure_ascii=False)


def _target(store: Store, project: str) -> tuple[Store, str | None, str, str | None]:
    """Where this intake goes: the active metaform, or a new one when that one has an intake, BASE-039.

    Returns the store to write, the earlier metaform's name when a new one is made, the name of the metaform
    written, and the new metaform's id.
    """
    active = store.active_metaform()
    if active is None or not store.has_intake():
        return store, None, active.name if active is not None else 'main', None
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    fresh = store.add_metaform(f'intake-{stamp}', activate=False)
    return Store(project, metaform=fresh.metaform_id), active.name, fresh.name, fresh.metaform_id


def submit(ctx: Context) -> Any:
    """Store the submission in one atomic write as a new intake layer; nothing is refused for its content."""
    store = ctx.require_store()
    project = store.project_id
    elements, why = _elements(ctx)
    empty: dict[str, Any] = {'layer': None, 'project': project, 'metaform': None, 'elements': 0, 'joins': 0,
                             'subtypes': 0, 'refs': 0, 'findings': 0}
    if elements is None:
        return {**empty, 'notices': [unreadable(why)]}
    notices: list[dict[str, str]] = []
    result_id = _text_noun(ctx, 'id', notices)
    report = _text_noun(ctx, 'report', notices)
    feedback = _text_noun(ctx, 'feedback', notices)
    target, previous, metaform, fresh = _target(store, project)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    name = f'intake-{stamp}-{secrets.token_hex(3)}'
    text, version = _source(ctx)
    provenance = {'module': 'intake', 'workflow': 'canonical-intake', 'prompt': served(ctx, text),
                  'model': ctx.nouns.get('model'), 'role': ctx.nouns.get('role'), 'blinded': ctx.nouns.get('blinded')}
    writer = Writer(target, name)
    try:
        with target.atomic():
            layer = target.layer(name, 'intake', VARIABLE, kind='intake', mutable=False, hideable=False,
                                 provenance=provenance, result_id=result_id, ready=True)
            receivers = [writer.element(index, raw) for index, raw in enumerate(elements)]
            for index, (raw, receiver) in enumerate(zip(elements, receivers)):
                if receiver is not None and isinstance(raw, dict):
                    writer.joins(index, cast(dict[str, Any], raw), receiver)
    except BaseException:
        if fresh is not None:
            store.withdraw_metaform(fresh)
        raise
    if fresh is not None:
        store.activate_metaform(metaform)
        notices.append({'where': 'metaform', 'message': f'This project already had an intake in metaform {previous}. '
                                                        f'This one was stored as the new active metaform {metaform}; '
                                                        f'the earlier one is kept whole. To switch back: metaform '
                                                        f'activate metaform {previous}'})
    if version is not None:
        prompts.record_use(version.version_id, project, layer.metaform_id, layer.layer_id)
    for kind, said in (('report', report), ('feedback', feedback)):
        if said is not None:
            save_report(project, layer.layer_id, kind, said, store=target, layer=layer.layer_id)
    findings = len(target.findings(layer=name, raw=True, limit=0).results)
    counts = writer.counts
    return {'layer': name, 'project': project, 'metaform': metaform, 'elements': counts.elements,
            'joins': counts.joins, 'subtypes': counts.subtypes, 'refs': counts.refs, 'findings': findings,
            'notices': notices + writer.notices}


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
        return Status(lines=('Intake: complete', 'Start with: metaform map roots'))
    return Status(lines=('Intake: none yet',), notice=NOTICE)


MODULE = Module(
    id='intake',
    summary='Serve the Canonical Intake and store its result.',
    purpose='Serves the Canonical Intake instructions and tracks whether this project has an intake. The intake is '
            'agent work: a subagent reads its instructions with intake_prompt and follows them. '
            'Details: metaform help intake.',
    details='The intake text is served unchanged except for its filled target. The result is submitted once, '
            'after the whole method, and stored as one intake layer in one atomic write. Nothing is refused for its '
            'content: what does not fit is stored as given and named in a notice.',
    verbs=(
        Verb('prompt', prompt, 'The Canonical Intake instructions for this project.', switches=('report', 'debug')),
        Verb('submit', submit, "Store an intake's final shape, once, as one intake layer.",
             nouns=(Noun('elements', 'The elements, each holding its joins: over MCP the array, on the command line '
                                     'a path to a JSON file holding it, or - for standard input.', required=False,
                         schema=ELEMENTS),
                    Noun('id', "The result's generated id.", required=False),
                    Noun('report', 'Your report on the project you examined: broken code, things that need fixing, '
                                   'anything not working or partially working.', required=False),
                    Noun('feedback', 'Feedback on the Metaform process: bad semantics, a tool that did not match its '
                                     'schema, where you got stuck.', required=False),
                    Noun('model', 'The model that performed the intake.', required=False),
                    Noun('role', 'The role of the agent that performed it.', required=False),
                    Noun('blinded', 'Whether the agent saw only the map.', kind='bool', required=False))),
        Verb('status', status_verb, 'Whether this project has an intake, and its latest intake layer.'),
    ),
    status=status,
)
