"""A table recorded by Metaform's roundtable module, taken into this store so the web page shows it: the combined
record Metaform exported, such as `docs/roundtables/1-embodied-ai-in-a-3d-physics.json`, with the report beside it as
`<same name>.md`.

    roundtable import /path/to/1-embodied-ai-in-a-3d-physics.json

The table takes the next number here and keeps its own in `imported`. Every text is kept exactly as recorded: each
seat's conversation (the table's messages as `user`, the seat's replies as `assistant`), every submission with its
round, seat, outcome and scores, the turn Jev never judged, the end reason and the report's error. What no column
holds is kept in `imported`: the record's legend, what it did not record, what happened, the configuration, and each
Claude Code and Codex session's log with the model and usage it reported at its end. The report is copied into the
reports folder. An imported table has ended and is only read: no one chairs it, and nothing runs it again.
"""
from __future__ import annotations

import json
import secrets
import shutil
from pathlib import Path
from typing import Any, cast

from . import config, render, store
from . import seats as seating

OUTCOME = {'included': 'kept', 'excluded by Jev': 'vetoed', 'excluded: over 512': 'over512',
           'no submission': 'none'}
COLUMNS = ('subject', 'opening', 'state', 'reason', 'round', 'position', 'round_kept', 'unjudged', 'report_error',
           'created', 'ended', 'spent')


def reported(log: list[dict[str, Any]]) -> dict[str, Any]:
    """What a session's state line says it ran on and used: its current model, its last turn's usage and tokens, and
    what the session spent."""
    for line in log:
        if line.get('kind') == 'state':
            try:
                state = cast(dict[str, Any], json.loads(str(line.get('text') or '')))
            except ValueError:
                return {}
            model = next((one.get('current') for one in cast(list[dict[str, Any]], state.get('settings') or [])
                          if one.get('id') == 'model'), None)
            return {'model': model, 'usage': state.get('usage'), 'tokens': state.get('tokens'),
                    'spent': state.get('spent')}
    return {}


def load(path: Path) -> int:
    """The record at `path` taken in as a table of this store; its number here."""
    given = cast(dict[str, Any], json.loads(path.read_text(encoding='utf-8')))
    found = cast(dict[str, Any], given['discussion'])
    logs = {str(one['session_id']): cast(list[dict[str, Any]], one.get('log') or [])
            for one in cast(list[dict[str, Any]], given.get('harness_sessions_other_lines') or [])}
    rows: list[dict[str, Any]] = []
    positions: dict[str, int] = {}
    seated: list[dict[str, Any]] = []
    sessions: dict[str, Any] = {}
    session_logs: dict[str, Any] = {}
    for seat in cast(list[dict[str, Any]], given['seats']):
        parsed = seating.parse(str(seat['seat']))
        name, position = str(seat['name']), int(seat['position'])
        positions[name] = position
        log = logs.get(str(seat.get('session_id') or ''))
        said = reported(log) if log else {}
        if said:
            sessions[str(position)] = said
        if log:
            session_logs[str(position)] = log
        messages = [{'role': 'user' if one['role'] == 'table' else 'assistant', 'content': one['content']}
                    for one in cast(list[dict[str, Any]], seat.get('conversation') or [])]
        seated.append({'position': position, 'kind': parsed['kind'], 'id': parsed['id'], 'name': name,
                       'agent': parsed.get('agent'), 'model': parsed.get('model'), 'reported': said.get('model'),
                       'session': seat.get('session_id'), 'messages': messages, 'taken': 0, 'kept': 0})
    for one in cast(list[dict[str, Any]], given['submissions']):
        outcome = OUTCOME[str(one['outcome'])]
        scores = cast(list[float], one.get('scores') or [])
        rows.append({'number': int(one['n']), 'round': int(one['round']), 'position': positions[str(one['seat'])],
                     'seat': next(seat['id'] for seat in seated if seat['name'] == one['seat']), 'name': one['seat'],
                     'kind': 'none' if outcome == 'none' else 'seat', 'text': str(one.get('text') or ''),
                     'reason': one.get('reason'), 'accepted': outcome == 'kept', 'over512': outcome == 'over512',
                     **dict(zip(store.NOULS, scores, strict=False)), 'created': ''})
    counted = cast(dict[str, Any], cast(dict[str, Any], given.get('summary') or {}).get('kept_by_seat') or {})
    for seat in seated:  # kept against taken as the record counted them, else from its submissions
        own = [row for row in rows if row['position'] == seat['position']]
        held = cast(dict[str, Any], counted.get(seat['name']) or {})
        seat['taken'] = int(held.get('taken', len(own)))
        seat['kept'] = int(held.get('kept', sum(1 for row in own if row['accepted'])))
    settings = cast(dict[str, Any], cast(dict[str, Any], given.get('configuration') or {}).get('settings') or {})
    record = {key: value for key, value in found.items() if key not in COLUMNS}
    imported = {'from': str(path), 'number': found['number'], 'record': record, 'legend': given.get('legend'),
                'not_recorded': given.get('not_recorded'), 'what_happened': given.get('what_happened'),
                'configuration': given.get('configuration'), 'summary': given.get('summary'),
                'sessions': sessions, 'session_logs': session_logs}
    number = store.imported({**{key: found.get(key) for key in COLUMNS}, 'subject': render.slug(str(found['subject'])),
                             'folder': '', 'chair_key': None, 'chair_token': secrets.token_urlsafe(18),
                             'reporter': str(settings.get('roundtable_reporter') or ''), 'rounds': 0, 'spend': 0.0,
                             'spent': float(found.get('spent') or 0), 'imported': imported}, seated, rows)
    report = path.with_suffix('.md')
    if report.is_file():
        copied = config.reports() / f'{number}-{render.slug(str(found["subject"]))}.md'
        shutil.copyfile(report, copied)
        store.change(number, report=str(copied))
    return number
