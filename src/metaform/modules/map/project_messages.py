"""`map ask`, `reply`, `reopen` and `messages` for a project held in the project store (`metaform.project`): its
questions and messages for the person are the records of its `questions` overlay, at the element each is about, where
the page's Messages pane reads them.

Kickoff 2026-11-17, Phase 3, decision t-legacy-keep: every old-store feature is kept and moved onto the project store.
A record holds what the old store's message held, MAP-050: its id, kind (question or message), title and why, the
text, the answers it suggests, who wrote it, the ticket it belongs to, when it was made, and when it was closed with
its answer. The overlay is defined in a project the first time one is written there. A question at a join's purpose
(provider=, address=) has no place there, since the project store keeps a want inside the element that holds it and
an overlay record at an element only, and item numbers (`<address>#<n>`) are not kept there; each is refused by name.
Each change names the record and revision it found (F02), so it never lands on another record.
"""
from __future__ import annotations

import json
import secrets
from typing import Any, cast

from metaform import home
from metaform import project as project_store
from metaform.data import LIMIT, Notice
from metaform.module import Stop

KEY = 'questions'
DEFINITION_PATH = 'overlay.questions'
DEFINITION: dict[str, object] = {
    'description': ('What is left for the person at this element: each record is one question, which waits for an '
                    'answer, or one message, which waits to be read.'),
    'instruction': ('Add one record for each question or message. A question carries the answers it suggests, the '
                    'one recommended first. Change one by its position with update: answer and closed when the person '
                    'answers a question, closed alone when a message is read; both cleared reopen a question.'),
    'id': {'type': 'text', 'rule': "A short id that stays the same for the record's life.", 'example': 'q-3f9a2c1b'},
    'kind': {'type': 'question | message', 'rule': 'A question waits for an answer; a message waits to be read.',
             'example': 'question'},
    'title': {'type': 'text', 'rule': 'One short line saying what it is.', 'example': 'Keep the quiet tone?'},
    'why': {'type': 'text', 'rule': 'One short line saying why it is asked.', 'optional': True,
            'example': 'The alarm is missed in a loud room.'},
    'text': {'type': 'text', 'rule': 'The question or the message, in full.',
             'example': 'Is the quiet tone still wanted?'},
    'suggestions': {'type': 'text', 'rule': 'The answers suggested, the recommended one first, as a JSON list of text.',
                    'example': '["Yes, keep it", "No, make it louder"]', 'optional': True},
    'by': {'type': 'text', 'rule': 'Who wrote it.', 'example': 'builder', 'optional': True},
    'work': {'type': 'text', 'rule': 'The id of the ticket it belongs to, in the tickets overlay.', 'example': 't-3f9a',
             'optional': True},
    'created': {'type': 'text', 'rule': 'When it was written, as a date and time.', 'example': '2026-11-17T09:30:00Z'},
    'closed': {'type': 'text', 'rule': 'When it was answered or read, as a date and time; left out while it waits.',
               'example': '2026-11-17T10:00:00Z', 'optional': True},
    'answer': {'type': 'text', 'rule': "The person's answer to a question.", 'example': 'No, make it louder',
               'optional': True},
}
HELP = 'metaform help map messages'


def ask(project: str, nouns: dict[str, Any], notices: list[Notice]) -> dict[str, Any]:
    """A question the person writes at an element, with the answers it suggests and, with work=, its ticket."""
    work = nouns.get('work')
    if work is not None and not any(record.get('id') == work
                                    for record in project_store.overlay_records(project, 'tickets') or []):
        raise Stop(f"No ticket {work!r} in {project}'s tickets, so the question cannot belong to it.",
                   'metaform map work op=list')
    return _added(project, 'question', nouns, notices)


def tell(project: str, address: str, text: str, *, by: str | None = None, title: str | None = None) -> dict[str, Any]:
    """A message left for the person at an element, which waits to be read."""
    return _added(project, 'message', {'node': address, 'question': text, 'by': by, 'title': title}, [])


def reply(project: str, record_id: str, answer: object, notices: list[Notice]) -> dict[str, Any]:
    """Answer a question, or mark a message read. One already closed keeps its first answer."""
    found = _found(project, record_id)
    if found.get('closed'):
        notices.append(Notice('id', f"This was closed at {found['closed']}; its answer was kept."))
        return _shown(project, found)
    text = answer.strip() if isinstance(answer, str) and answer.strip() else None
    return _changed(project, found, {'closed': home.now(), 'answer': text})


def reopen(project: str, record_id: str, notices: list[Notice]) -> dict[str, Any]:
    """A question answered by mistake waits again, with its suggestions and no answer."""
    found = _found(project, record_id)
    if found.get('kind') != 'question':
        raise Stop('Only a question is reopened; this is a message.', 'metaform map messages kind=question')
    if not found.get('closed'):
        notices.append(Notice('id', 'This question is open; it was left as it is.'))
        return _shown(project, found)
    return _changed(project, found, {'closed': None, 'answer': None})


def listed(project: str, nouns: dict[str, Any]) -> dict[str, Any]:
    """The questions and messages, oldest first, by element, kind or whether they still wait, a page at a time:
    `after` is the id of the last one the previous page gave."""
    node = str(nouns.get('node') or '')
    if node.startswith('join:'):  # a join holds none in the project store, as the page asks of each join it shows
        return {'results': [], 'next': None}
    at = None if not node else _element(node)
    rows = [_shown(project, record) for record in _records(project)]
    # oldest first, as the old store gives them; one second's records keep the store's order, a stable sort
    rows.sort(key=lambda row: str(row.get('created') or ''))
    opened = nouns.get('open')
    kept = [row for row in rows if (at is None or row['address'] == at)
            and (not nouns.get('kind') or row['kind'] == nouns['kind'])
            and (opened is None or (row['closed'] is None) == bool(opened))]
    after = nouns.get('after')
    if after:
        place = next((index for index, row in enumerate(kept) if row['id'] == after), None)
        if place is None:
            raise Stop(f'after={after} names no question or message of this list.', HELP)
        kept = kept[place + 1:]
    limit = int(nouns.get('limit', LIMIT) or 0)
    page = kept[:limit] if limit else kept
    return {'results': page, 'next': page[-1]['id'] if limit and len(kept) > limit else None}


def move(project: str, record_id: str, node: str) -> dict[str, Any]:
    """Move a question or message to another element, keeping its id, suggestions, answer and closed state."""
    found = _found(project, record_id)
    address = _element(node)
    if f'{project}.{address}' == found['element']:
        return _shown(project, found)
    kept = {name: value for name, value in found.items() if name not in ('element', 'position', 'record', 'revision')}
    # two commands, the tool's add then its delete: added first, so a delete refused meanwhile leaves it at both
    # elements, said by the refusal, and never at neither
    _done(project_store.run({'add': {f'{project}.{address}': {KEY: [kept]}}}))
    _done(project_store.run({'delete': {str(found['element']): {KEY: [found['record']]}}}))
    return _shown(project, _found(project, record_id))


def _element(node: str) -> str:
    kind_of, _, address = node.partition(':')
    if not address:
        kind_of, address = 'element', kind_of
    if kind_of != 'element' or not address:
        raise Stop(f"{node} is not an element: in the project store a question or message is at one element, and a "
                   "join has none there yet; put it at the join's receiver, node=element:<address>.", HELP)
    return address


def _added(project: str, kind: str, nouns: dict[str, Any], notices: list[Notice]) -> dict[str, Any]:
    address = _element(str(nouns.get('node') or ''))
    text = str(nouns.get('question') or '').strip()
    if not text:
        raise Stop(f'A {kind} says something.', 'metaform help map ask')
    suggested: list[str] = []
    given = nouns.get('suggestions')
    if isinstance(given, (list, tuple)):
        suggested = [one if isinstance(one, str) else json.dumps(one, ensure_ascii=False)
                     for one in cast('list[Any] | tuple[Any, ...]', given)]
    elif given is not None:
        notices.append(Notice('suggestions', 'suggestions is a list of answers; what was sent was kept as the one '
                                             'suggestion.'))
        suggested = [given if isinstance(given, str) else json.dumps(given, ensure_ascii=False)]
    if kind == 'question' and not suggested:
        notices.append(Notice('suggestions', 'This question has no suggestions. Ask with the answers you suggest, the '
                                             'one you recommend first: suggestions=["...", "..."].'))
    title = str(nouns.get('title') or '').strip() or next(line.strip() for line in text.splitlines() if line.strip())
    record: dict[str, object] = {
        'id': ('q-' if kind == 'question' else 'm-') + secrets.token_hex(4), 'kind': kind, 'title': title, 'text': text,
        **({'why': str(nouns['why']).strip()} if str(nouns.get('why') or '').strip() else {}),
        **({'suggestions': json.dumps(suggested, ensure_ascii=False)} if suggested else {}),
        **({'by': str(nouns['by'])} if nouns.get('by') else {}),
        **({'work': str(nouns['work'])} if nouns.get('work') else {}),
        'created': home.now()}
    command = {'add': {f'{project}.{address}': {KEY: [record]}}}
    answer = project_store.run(command)
    if answer.get('code') == 'OVERLAY_NOT_DEFINED':  # the first written in this project: its overlay is defined
        _done(project_store.run({'add': {f'{project}.{DEFINITION_PATH}': DEFINITION}}))
        answer = project_store.run(command)
    _done(answer)
    return _shown(project, _found(project, str(record['id'])))


def _records(project: str) -> list[dict[str, Any]]:
    return cast(list[dict[str, Any]], project_store.overlay_records(project, KEY) or [])


def _found(project: str, record_id: str) -> dict[str, Any]:
    found = next((record for record in _records(project) if record.get('id') == record_id), None)
    if found is None:
        raise Stop(f'No question or message has the id {record_id}.', 'metaform map messages')
    return found


def _changed(project: str, found: dict[str, Any], fields: dict[str, object]) -> dict[str, Any]:
    """Change one record by the position, record id and revision it was found at (F02): a record moved or changed by
    another writer meanwhile is refused, never another record changed. A field given as None is removed."""
    _done(project_store.run({'update': {str(found['element']): {KEY: [
        {'position': found['position'], 'record': found['record'], 'revision': found['revision'], **fields}]}}}))
    return _shown(project, _found(project, str(found['id'])))


def _shown(project: str, record: dict[str, Any]) -> dict[str, Any]:
    """One record as the old store's message reads, so the page and the command line show it the same way: its node,
    its suggestions as a list, its ticket as work_id, and the record id and revision it is changed by."""
    address = str(record['element'])[len(project) + 1:]
    suggestions: Any = json.loads(str(record['suggestions'])) if record.get('suggestions') else []
    return {'id': record['id'], 'kind': record['kind'], 'node_kind': 'element', 'node_id': address,
            'address': address, 'receiver_address': None, 'provider_address': None, 'title': record.get('title'),
            'why': record.get('why'), 'text': record.get('text'), 'suggestions': suggestions, 'by': record.get('by'),
            'created': record.get('created'), 'closed': record.get('closed'), 'answer': record.get('answer'),
            'work_id': record.get('work'), 'record': record['record'], 'revision': record['revision']}


def _done(answer: dict[str, object]) -> None:
    if answer.get('status') == 'error':
        raise Stop(str(answer.get('message') or 'The question or message was not changed.'),
                   str(answer.get('remediation') or HELP))
