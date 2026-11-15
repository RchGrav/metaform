"""Roundtables with private participant identities, judged messages and inline document work.

Ready participants speak while busy participants work on shared files. Each substantive message is checked for a
new contribution or position, value and relevance before peers receive it. Only its author receives a rejected
message's failed conditions, at the start of the next turn. Passes and accepted peer messages missed while busy
bank reply space. Public IDs name accepted messages without exposing rejected attempts.

Two complete quiet cycles finish a topic when every participant has completed PP, VV or VP; PV receives a return
turn to reword or pass. An accepted message resets everyone's outcomes. Sessions privately collect the next-topic
proposals and choose the highest mean of unordered pairwise similarity judgments. There is no intertopic discussion
or document-file handoff. Final scorecards remain private, followed by farewells.

The bridge opens and chairs the shipped ACP/MCP/A2A engine, holds dispatch's agent slots and follows only its changed
records. Changes reach the page through the existing event bus. New project-readable records contain accepted
messages and generated names. The engine's private owner audit retains full usage and diagnostic evidence.
"""
from __future__ import annotations

import contextlib
import json
import os
import secrets
import selectors
import subprocess
import sys
from datetime import UTC, datetime
from importlib import resources
from pathlib import Path
from typing import Any, cast

from metaform import events, outline, prompt_files, settings
from metaform.data import Column, Index, Node, Table, Tables
from metaform.module import Context, Module, Noun, Stop, Subscription, Verb, context, node_items, provided

from . import engine, follow, live_summary, pipeline

SUPPORTED_OS = ('linux', 'macos')  # a follower and the engine's servers are detached into a session of their own
# The shipped engine's own requirements, roundtable/ (its pyproject.toml), so it runs on every install
DEPENDENCIES = ('mcp>=2.2,<3', 'agent-client-protocol==1.0.0rc2', 'a2a-sdk[http-server]>=1.2.2,<2', 'httpx>=0.28,<1',
                'uvicorn>=0.31')
SHIPS_DISABLED = False  # a person can open a table in any project: the engine ships inside this module

PACKAGE = resources.files(__name__)
OPEN_LIMIT = engine.CALL_LIMIT + 30  # seconds `open` waits for its follower's first line: a deadline on one request
CHAIR = ('state', 'reason', 'stage', 'topic', 'round', 'turn_of', 'spend', 'spent', 'runner', 'token_budget',
         'token_basis', 'phase_budget')

settings.number('roundtables_spend', 2, min=0, max=100, label='Most a table spends (US dollars)',
                category='integrations', heading='Roundtables',
                help='The most one table spends through OpenRouter, its model seats and Jev; open may only lower it.',
                details='OPENROUTER_API_KEY is required for judging or OpenRouter seats. ACP-only unjudged tables '
                        'use their agent logins.')

settings.boolean('roundtables_judging', True, label='Judge discussion novelty with Jev',
                 category='integrations', heading='Roundtables',
                 help='Checks new contribution or position, value and relevance. Judged discussions end after '
                      'two complete quiet rounds. Off keeps substantive replies and ends on unanimous PASS. '
                      'End discussion and the configured token budget remain available.')
settings.number('roundtables_context_tokens', 24000, min=4096, max=1000000,
                label='Seat context handoff trigger (estimated tokens)', category='integrations', heading='Roundtables',
                help='Fallback context handoff for independent tables. Continuous native-agent sessions keep '
                     'their conversations. Independent of the Jev history window.')
settings.number('roundtables_judging_context_tokens', 50000, min=4096, max=52428,
                label='Jev history window (estimated tokens)', category='integrations', heading='Roundtables',
                help='Sliding accepted history plus instructions and candidate, with 20% headroom under both '
                     'request and question limits. Older responses leave the window without pausing the panel.')
settings.number('roundtables_token_budget', 0, min=0, max=9007199254740991,
                label='Tokens per agent per round', category='integrations', heading='Roundtables',
                help='Reported tokens under the selected counting basis. Fresh counters for each '
                     'round. Warn at 50% and 80%, closing statements at 100%, advance at 120%. Zero disables it.')
settings.choice('roundtables_token_basis', ['uncached', 'output', 'all'], 'uncached',
                label='Count toward the phase token budget', category='integrations', heading='Roundtables',
                choice_names={'uncached': 'Uncached input + output', 'output': 'Generated output only',
                              'all': 'Input + cached input + output'},
                help='Uncached counts input, cache writes and output, excluding cached reads. Full usage stays '
                     'recorded. Existing tables keep their basis until explicitly adjusted while stopped.')
settings.boolean('roundtables_live_summary', False, label='Legacy live roundtable summary',
                 category='integrations', heading='Roundtables',
                 help='Historical summary records remain readable. Roundtables use linked participant messages '
                      'and shared documents without starting a separate observer.')


def _check_seats(seats: Any, folder: Path) -> list[str] | None:
    """Each of dispatch's agents' seats names a model it offers, by short name or exact value, checked as a table
    checks it when it opens; one whose agent has not run here is kept unchecked, with a notice."""
    ctx = context('roundtables', folder)
    notices: list[str] = []
    for seat in cast(list[Any], seats or []):
        agent, _, model = str(seat).strip().removeprefix('acp:').partition('/')
        if agent not in engine.AGENTS or not model.strip():
            continue
        try:
            if model_of(ctx, agent, model.strip()) is None:
                notices.append(f'{agent} has not run here, so {seat} is kept unchecked; metaform dispatch options '
                               f'agent={agent} prime=true starts it once and reads its models.')
        except Stop as error:
            raise settings.SettingError(error.message, error.next_step) from error
    return notices or None


settings.items('roundtables_seats', ('claude/opus', 'codex/astra', 'codex/sol', 'claude/fable'),
               label='Seats a table opens with', category='integrations', heading='Roundtables', check=_check_seats,
               help='The seats, in speaking order, of a table opened without any named, as the page\'s roundtable '
                    'opens one: claude/<model>, codex/<model>, antigravity/<model> or OpenRouter model ids. A model is a '
                    'short name, such as opus or sol, which means the newest release of its family when the table '
                    'opens, or an exact value, such as gpt-6-sol, which pins one.')

# Version 2: a table's Address may be empty, a table on the question alone; the engine's reporter seat and its report
# are gone. The engine's synthesis and saved mechanical report supply the result.
# Version 6 adds only pending stage launches, so session events recover refused work without scanning task history.
# Versions 7 and 8 keep the mutable budget and live observer outside follower-owned cursors.
TABLES = Tables(version=8, compatible_from=5, upgrade=pipeline.upgrade, tables=(
    Table('tables', place='project', key=('table_id',), columns=(
        Column('table_id', required=True), Column('address'), Column('topic', required=True),
        Column('opening', required=True), Column('seats', 'json', required=True), Column('host'),
        Column('synthesizer'), Column('rounds', 'int'), Column('spend', 'real', required=True),
        Column('state', required=True), Column('reason'), Column('discussion', 'int'), Column('chair'),
        Column('context_id'), Column('task_id'), Column('seated', 'json'), Column('follower', 'int'),
        Column('followed', 'json'), Column('token_budget', 'int'), Column('answer'),
        Column('answered', 'bool', required=True, default=False), Column('created', required=True),
        Column('ended')),
        indexes=(Index(('created',)),)),
    Table('events', place='project', key=('table_id', 'seq'), columns=(
        Column('table_id', required=True), Column('seq', 'int', required=True), Column('kind', required=True),
        Column('audience', required=True), Column('payload', 'json', required=True), Column('at', required=True))),
    Table('pipelines', place='project', key=('table_id',), columns=(
        Column('table_id', required=True), Column('stage', required=True), Column('state', required=True),
        Column('file'), Column('work_id'), Column('coordinator'), Column('digest'), Column('error'),
        Column('revision', 'int', required=True, default=0), Column('artifacts', 'json'), Column('history', 'json'),
        Column('automate_ticket_creation', 'bool', required=True, default=False),
        Column('feedback'), Column('project_name'), Column('project'), Column('folder'), Column('board'),
        Column('created', required=True))),
    Table('intake_links', place='project', key=('origin', 'table_id'), columns=(
        Column('origin', required=True), Column('table_id', required=True))),
    Table('pending_stages', place='project', key=('origin', 'table_id'), columns=(
        Column('origin', required=True), Column('table_id', required=True),
        Column('stage', required=True), Column('work_id'))),
    Table('live_summaries', place='project', key=('table_id',), columns=(
        Column('table_id', required=True), Column('through_seq', 'int', required=True, default=0),
        Column('text'), Column('state', required=True, default='idle'), Column('error'), Column('updated'),
        Column('usage', 'json'), Column('permissions', 'json'))),
))


# ------------------------------------------------------------------ seats and the opening

def model_of(ctx: Context, agent: str, model: str) -> str | None:
    """The exact model a seat's word means now, through dispatch's `dispatch.models`: a short name such as sol is its
    family's newest release, and a word that is none of the agent's models is refused naming the nearest. None when
    the agent has not run here or dispatch is off, so nothing can check it."""
    for _, resolve in provided(ctx.folder, 'dispatch.models'):
        return cast(str | None, resolve(ctx.store, agent, model))
    return None


def seat_of(ctx: Context, given: str) -> str:
    """A seat as the engine writes it: `claude/<model>`, `codex/<model>` and `antigravity/<model>` are Metaform's agents,
    `acp:<agent>/<model>` on the engine's ACP client, the model resolved as the table opens; any other id is an
    OpenRouter model the engine checks."""
    text = given.strip()
    agent, slash, model = text.removeprefix('acp:').partition('/')
    if agent in engine.AGENTS:
        if not slash or not model.strip():
            raise Stop(f'{text}: name the model the agent runs, such as {agent}/opus.', 'metaform roundtables open')
        return f'acp:{agent}/{model_of(ctx, agent, model.strip()) or model.strip()}'
    if text.startswith(('acp:', 'agent:', 'a2a:')):
        raise Stop(f'{text} cannot sit: a seat is claude/<model>, codex/<model>, antigravity/<model> or an OpenRouter '
                   'model id, such as deepseek/deepseek-v4.1-flash.', 'metaform roundtables open')
    if not slash:
        raise Stop(f'{text} is not a seat: write claude/<model>, codex/<model>, antigravity/<model> or an OpenRouter '
                   'model id, such as deepseek/deepseek-v4.1-flash.', 'metaform roundtables open')
    return text


def opening(ctx: Context, address: str, topic: str) -> str:
    """The table's opening. With no Address, the person's question alone: the question is the frame, and the seats
    read the project's files themselves when it touches the project. With one, the part as the map holds it, its
    element and the joins it receives and provides with their purposes and encounter functions, and the memories at
    it, then the question."""
    if not address:
        return prompt_files.served(PACKAGE, 'opening_question', question=topic)
    part = outline.markdown(ctx.require_store(), address)
    found = node_items(ctx.folder, address, kinds=('memory',), limit=20, project=ctx.project)
    held = cast(list[dict[str, Any]], found.get('items') or [])
    memories = '\n'.join(f'- {one.get("title")}' + (f': {one["why"]}' if one.get('why') else '') for one in held)
    return prompt_files.served(PACKAGE, 'opening', address=address, part=part.strip(), question=topic,
                               memories=memories or prompt_files.required(PACKAGE, 'no_memories'))



# ------------------------------------------------------------------ the tables

def table_row(ctx: Context) -> dict[str, Any]:
    table_id = str(ctx.nouns['table'])
    with ctx.require_store().tables(write=False) as tx:
        found = tx.get('tables', {'table_id': table_id})
    if found is None:
        raise Stop(f'No roundtable {table_id} in this project.', 'metaform roundtables tables')
    return dict(found)


def report_of(ctx: Context, row: dict[str, Any]) -> str | None:
    """The engine's saved transcript, relative to the project's folder; None before it is saved."""
    saved = str(cast(dict[str, Any], row.get('followed') or {}).get('saved') or '')
    found = f'{saved}/{follow.REPORT}' if saved else ''
    return found if found and (Path(ctx.require_store().project().path) / found).is_file() else None


def phase_progress(ctx: Context, row: dict[str, Any]) -> dict[str, Any] | None:
    """Read this table's current counters without starting an engine or depending on follower cursors."""
    if row.get('discussion') is None:
        return None
    from .roundtable import budget, config, store

    if not (config.home() / 'roundtable.sqlite3').is_file():
        return None
    try:
        found = store.discussion(int(row['discussion']))
    except store.Missing:
        return None
    project = Path(ctx.require_store().project().path).resolve()
    if not Path(str(found['folder'])).resolve().is_relative_to(project) or \
            not str(found['subject']).startswith(str(row['table_id'])):
        return None
    from .roundtable import topics as next_topics

    return {**budget.progress(found), 'stage': found['stage'] or 'discussion',
            'topic_selection': next_topics.progress(found) if found['stage'] == 'topic_selection' else None}


def shown(ctx: Context, row: dict[str, Any]) -> dict[str, Any]:
    followed = cast(dict[str, Any], row.get('followed') or {})  # where its record was saved and its memory kept
    report = report_of(ctx, row)
    materials = cast(dict[str, Any], followed.get('session') or {}).get('folder')
    progress = phase_progress(ctx, row)
    return {'table': row['table_id'], **({'address': row['address']} if row.get('address') else {}),
            **({'materials': materials} if materials else {}),
            'topic': row['topic'], 'state': row['state'],
            **({'reason': row['reason']} if row.get('reason') else {}), 'seats': row['seats'],
            **({'seated': row['seated']} if row.get('seated') else {}),
            'spend': row['spend'], 'reply_limit': followed.get('reply_limit', 512), 'discussion': row.get('discussion'),
            'token_budget': int(progress['limit'] if progress is not None else
                                row['token_budget'] if row.get('token_budget') is not None
                                else followed.get('token_budget') or 0),
            'token_basis': progress['basis'] if progress is not None else followed.get('token_basis', 'all'),
            'live_summary': live_summary.snapshot(ctx, str(row['table_id'])),
            'phase_budget': progress,
            'topic_selection': progress.get('topic_selection') if progress is not None else None,
            **({'stage': progress['stage']} if progress is not None else {}),
            'follower': 'running' if follow.alive(row.get('follower')) else 'stopped',
            'answered': bool(row.get('answered')), **({'answer': row['answer']} if row.get('answer') else {}),
            **({'report': report} if report else {}), 'created': row['created'],
            **({'ended': row['ended']} if row.get('ended') else {}),
            **({'topics': followed['result_topics']} if 'result_topics' in followed else {}),
            **({'pipeline': held} if (held := pipeline.state(ctx, str(row['table_id']))) is not None else {}),
            **{key: followed[key] for key in ('saved', 'recorded') if followed.get(key)}}


def started(ctx: Context, table_id: str) -> dict[str, Any]:
    """A follower started detached for the table, and the first line it says: opened, following or refused."""
    log = os.open(engine.folder_log() / 'followers.log', os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    env = engine.environment(ctx.folder)
    try:
        process = subprocess.Popen([sys.executable, '-m', 'metaform', 'roundtables', 'run', table_id,
                                    '--project', str(ctx.project)], cwd=ctx.folder, env=env,
                                   stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=log,
                                   start_new_session=True)
    finally:
        os.close(log)
    assert process.stdout is not None
    with selectors.DefaultSelector() as waiting:
        waiting.register(process.stdout, selectors.EVENT_READ)
        ready = waiting.select(OPEN_LIMIT)
    line = process.stdout.readline() if ready else b''
    process.stdout.close()
    try:
        found: Any = json.loads(line) if line else None
    except ValueError:
        found = None
    if isinstance(found, dict):
        return cast(dict[str, Any], found)
    if not ready:
        raise Stop(f'The follower of roundtable {table_id} said nothing in {OPEN_LIMIT:g} s; its log is in the '
                   'Metaform home under run/roundtables/followers.log.', f'metaform roundtables status {table_id}')
    try:  # its standard output closed with nothing said: it ended, and is reaped within this deadline
        code: int | None = process.wait(10)
    except subprocess.TimeoutExpired:
        code = None
    reason = (f'The follower of roundtable {table_id} ended{f" (exit {code})" if code is not None else ""} before '
              'it said anything; its log is in the Metaform home under run/roundtables/followers.log.')
    with ctx.require_store().tables() as tx:
        held = tx.get('tables', {'table_id': table_id})
        if held is not None and dict(held).get('state') == 'opening':
            tx.concern(kind=follow.CHANGE_KIND)
            tx.update('tables', {'table_id': table_id}, {'state': 'refused', 'reason': reason, 'follower': None})
    raise Stop(reason, f'metaform roundtables status {table_id}')


def session_of(ctx: Context, table_id: str, total: int, topic: str) -> dict[str, Any]:
    """A session's settings for the engine: its shared documents folder in the project, the owner's
    messages filled in, and the first roundtable's topic; and its opening, the owner's first message with the
    project's writing rules."""
    root = Path(ctx.require_store().project().path)
    folder = root / 'docs' / 'roundtables' / f'session-{datetime.now(UTC):%Y%m%d}-{table_id}'
    folder.mkdir(parents=True, exist_ok=True)
    taste = ''
    with contextlib.suppress(OSError, UnicodeDecodeError):
        taste = (root / 'docs' / 'taste.md').read_text(encoding='utf-8').strip()
    return {'total': total, 'folder': str(folder),
            'compress_between_topics': bool(ctx.nouns.get('compress_between_topics', False)),
            'opening': prompt_files.required(PACKAGE, 'session_opening', total=str(total),
                                             session_folder=str(folder),
                                             taste=taste or prompt_files.required(PACKAGE, 'minutes_taste_default')),
            'first': prompt_files.required(PACKAGE, 'session_first', total=str(total), topic=topic),
            'score': prompt_files.required(PACKAGE, 'session_score'),
            'farewell': prompt_files.required(PACKAGE, 'session_farewell')}


def permission_settings(ctx: Context, given: Any, agents: set[str]) -> dict[str, dict[str, str]]:
    """Validate per-agent setup choices and capture the ordinary launch defaults once for this session."""
    if given is not None and not isinstance(given, dict):
        raise Stop('permissions maps agent names to their prompts and mode choices.', 'metaform help roundtables open')
    supplied = cast(dict[str, Any], given or {})
    for agent, values in supplied.items():
        if agent not in engine.AGENTS or not isinstance(values, dict):
            raise Stop('permissions names an ACP agent and its prompts and mode choices.',
                       'metaform help roundtables open')
        choices = cast(dict[str, Any], values)
        if any(key not in ('prompts', 'mode') or not isinstance(value, str) for key, value in choices.items()):
            raise Stop('Each permission choice is prompts or mode, with a text value.',
                       'metaform help roundtables open')
    found = provided(ctx.folder, 'dispatch.roundtable_permissions')
    if not found:
        if supplied:
            raise Stop('Dispatch supplies the agent permission controls.', 'metaform enable dispatch')
        return {}
    resolve = found[0][1]
    return {agent: cast(dict[str, str], resolve(ctx, agent, supplied.get(agent) or {}))
            for agent in sorted(agents | supplied.keys())}


def open_table(ctx: Context) -> dict[str, Any]:
    total = ctx.nouns.get('chain')
    if total is not None and (type(total) is not int or total < 1):
        raise Stop('chain is how many roundtables the session runs, 1 or more.', 'metaform roundtables open')
    if type(ctx.nouns.get('compress_between_topics', False)) is not bool:
        raise Stop('compress_between_topics is true or false.', 'metaform roundtables open')
    # When enabled for a session, Jev judges whether each turn keeps to its panel's topic.
    judging = ctx.nouns.get('judging', ctx.setting('roundtables_judging'))
    if judging and not settings.value('jev', ctx.folder):
        raise Stop('A table sends your question, and the part\'s context when it is about a part, to OpenRouter, where '
                   'Jev judges every turn, and only you allow project text to leave this machine.',
                   'metaform set --jev')
    address, topic = str(ctx.nouns.get('address') or '').strip(), str(ctx.nouns['topic']).strip()
    if not topic:
        raise Stop('A table opens on a question.', 'metaform roundtables open')
    reply_limit = ctx.nouns.get('reply_limit', 512)
    if type(reply_limit) is not int or reply_limit < 1:
        raise Stop('reply_limit is a positive whole number of characters.', 'metaform roundtables open')
    token_budget = ctx.nouns.get('token_budget', ctx.setting('roundtables_token_budget'))
    if type(token_budget) is not int or not 0 <= token_budget <= 9007199254740991:
        raise Stop('token_budget is a non-negative whole number; zero disables it.', 'metaform roundtables open')
    token_basis = ctx.nouns.get('token_basis', ctx.setting('roundtables_token_basis'))
    if token_basis not in ('uncached', 'output', 'all'):
        raise Stop('token_basis is uncached, output or all.', 'metaform roundtables open')
    given = ctx.nouns.get('seats') or ctx.setting('roundtables_seats')
    listed = cast(list[Any], json.loads(given) if isinstance(given, str) else given)
    seats = [seat_of(ctx, str(one)) for one in listed]
    if not seats:
        raise Stop('A table has seats.', 'metaform roundtables open')
    most = float(ctx.setting('roundtables_spend'))
    spend = float(ctx.nouns['spend']) if ctx.nouns.get('spend') not in (None, '') else most
    if not 0 <= spend <= most:
        raise Stop(f'spend is 0 to ${most:g}, roundtables_spend; only the person raises it.',
                   'metaform roundtables open')
    roles = {key: seat_of(ctx, str(ctx.nouns[key])) if ctx.nouns.get(key) else None
             for key in ('host', 'synthesizer')}
    roles['host'] = roles['host'] or seats[0]  # never the engine's own default, which seats an agent nobody chose
    agents = {one.split('/', 1)[0].removeprefix('acp:') for one in [*seats, *roles.values()]
              if one and one.startswith('acp:')}
    permissions = permission_settings(ctx, ctx.nouns.get('permissions'), agents)
    table_id = secrets.token_hex(4)
    held = session_of(ctx, table_id, int(total), topic) if total else None
    text = str(held.pop('opening')) if held else opening(ctx, address, topic)
    with ctx.require_store().tables() as tx:
        tx.concern(kind=follow.CHANGE_KIND)
        tx.insert('tables', {'table_id': table_id, 'address': address or None, 'topic': topic, 'opening': text,
                             'seats': seats, **roles, 'spend': spend,
                             'state': 'opening', 'created': follow.now(), 'token_budget': token_budget,
                             'followed': {'reply_limit': reply_limit, 'judging': judging,
                                          'token_budget': token_budget,
                                          'token_basis': token_basis,
                                          'permissions': permissions,
                                          **({'session': held} if held else {}),
                                          'automate_ticket_creation': bool(ctx.nouns.get('automate_ticket_creation')),
                                          'opener': 'person' if ctx.surface == 'web' or (
                                              ctx.surface == 'cli' and not os.environ.get('METAFORM_SESSION')) else 'agent'}})
    answer = started(ctx, table_id)
    if 'refused' in answer:
        raise Stop(str(answer['refused']), str(answer.get('next') or 'metaform dispatch sessions'))
    return {'table': table_id, **({'address': address} if address else {}), 'topic': topic, 'reply_limit': reply_limit,
            **{key: value for key, value in answer.items() if key != 'opened'},
            'next': f'metaform roundtables status {table_id}; its events: metaform roundtables events {table_id}'}


def chaired(ctx: Context, tool: str, **more: Any) -> dict[str, Any]:
    """One of the chair's controls, passed to the engine with the table's chair token."""
    row = table_row(ctx)
    if row['state'] in ('opening', 'refused') or row.get('discussion') is None:
        raise Stop(f'Roundtable {row["table_id"]} never opened: {row.get("reason") or row["state"]}.',
                   'metaform roundtables open')
    answer = engine.call(ctx.folder, tool, discussion=int(row['discussion']), chair=row['chair'], **more)

    def announced() -> None:
        with ctx.require_store().tables() as tx:
            current = tx.get('tables', {'table_id': row['table_id']})
            if current is not None:
                tx.concern(kind=f'roundtables:control:{row["discussion"]}')
                tx.concern(kind=follow.CHANGE_KIND)
                tx.concern(kind=f'{follow.CHANGE_KIND}:{row["table_id"]}')
                changes: dict[str, Any] = {'reason': dict(current).get('reason')}
                if tool == 'budget':
                    changes['token_budget'] = more['token_budget']
                    changes['followed'] = {**cast(dict[str, Any], dict(current).get('followed') or {}),
                                           'token_budget': more['token_budget']}
                tx.update('tables', {'table_id': row['table_id']}, changes)

    events.announced(ctx.folder, ctx.surface, announced)
    return {'table': row['table_id'], **{key: answer[key] for key in CHAIR if key in answer}}


def comment(ctx: Context) -> dict[str, Any]:
    return chaired(ctx, 'comment', text=str(ctx.nouns['text']))


def hold(ctx: Context) -> dict[str, Any]:
    return chaired(ctx, 'hold')


def continued(ctx: Context) -> dict[str, Any]:
    row = table_row(ctx)
    spend = float(ctx.nouns['spend']) if ctx.nouns.get('spend') is not None else None
    if spend is not None and not 0 <= spend <= float(ctx.setting('roundtables_spend')):
        raise Stop('spend exceeds roundtables_spend.', 'metaform roundtables continue')
    if row['state'] != 'ended' and follow.alive(row.get('follower')):
        return chaired(ctx, 'continue', spend=spend)
    if follow.alive(row.get('follower')):
        raise Stop('The previous follower is still closing. Continue once it stops.', 'metaform roundtables status')
    # Admission precedes reopening. The follower owns all participant slots before fresh sessions start.
    with ctx.require_store().tables() as tx:
        tx.concern(kind=follow.CHANGE_KIND)
        tx.concern(kind=f'{follow.CHANGE_KIND}:{row["table_id"]}')
        tx.update('tables', {'table_id': row['table_id']}, {'state': 'continuing',
                  'followed': {**cast(dict[str, Any], row.get('followed') or {}), 'continue_spend': spend,
                               'continue_from': row['state']}})
    answer = started(ctx, str(row['table_id']))
    if 'refused' in answer:
        raise Stop(str(answer['refused']), str(answer.get('next') or 'metaform roundtables status'))
    return {'table': row['table_id'], 'state': 'running'}


def advance(ctx: Context) -> dict[str, Any]:
    return chaired(ctx, 'advance')


def set_token_budget(ctx: Context) -> dict[str, Any]:
    tokens = ctx.nouns['token_budget']
    if type(tokens) is not int or not 0 <= tokens <= 9007199254740991:
        raise Stop('token_budget is a non-negative whole number; zero disables it.', 'metaform roundtables budget')
    basis = ctx.nouns.get('token_basis')
    if basis is not None and basis not in ('uncached', 'output', 'all'):
        raise Stop('token_basis is uncached, output or all.', 'metaform roundtables budget')
    return chaired(ctx, 'budget', token_budget=tokens, **({'token_basis': basis} if basis is not None else {}))


def reseat(ctx: Context) -> dict[str, Any]:
    return chaired(ctx, 'reseat', seat=str(ctx.nouns['seat']))


def permit(ctx: Context) -> dict[str, Any]:
    """Relay the person's selected ACP option and wake its waiting agent."""
    row = table_row(ctx)
    observed = live_summary.answer(ctx, str(row['table_id']), str(ctx.nouns['request']), str(ctx.nouns['option']))
    if observed is not None:
        return {'table': row['table_id'], **observed}
    if row.get('discussion') is None:
        raise Stop('The roundtable has not opened.', 'metaform roundtables status')
    number = int(row['discussion'])
    answer = engine.call(ctx.folder, 'permit', discussion=number,
                         request=str(ctx.nouns['request']), option=str(ctx.nouns['option']))

    def announced() -> None:
        with ctx.require_store().tables() as tx:
            current = tx.get('tables', {'table_id': row['table_id']})
            if current is not None:
                tx.concern(kind=f'roundtables:permissions:{number}')
                # The engine owns the answer. This record announces that exact change through the existing relay.
                tx.update('tables', {'table_id': row['table_id']}, {'reason': dict(current).get('reason')})

    events.announced(ctx.folder, ctx.surface, announced)
    return {'table': row['table_id'], **answer}


def end(ctx: Context) -> dict[str, Any]:
    answer = chaired(ctx, 'end')
    row = table_row(ctx)
    if row['state'] != 'ended' and not follow.alive(row.get('follower')):
        watching = started(ctx, str(row['table_id']))
        if 'refused' in watching:
            raise Stop(str(watching['refused']), str(watching.get('next') or 'metaform roundtables follow'))
    return answer


def abort(ctx: Context) -> dict[str, Any]:
    """The table aborted at once: the engine stops it hard and puts its files aside, no next table of a planning
    session opens, and the whole run is archived in the Metaform home's backups, its notes, saved record, engine files,
    row and events, so nothing of it is left in the project, the engine or the page."""
    row = table_row(ctx)
    if row['state'] in ('opening', 'refused') or row.get('discussion') is None:
        shelf = follow.archive(ctx, row, None)
        return {'table': row['table_id'], 'aborted': True, 'archived': str(shelf)}
    answer = engine.call(ctx.folder, 'abort', discussion=int(row['discussion']), chair=row['chair'])
    shelf = follow.archive(ctx, row, cast(str | None, answer.get('archived')))
    return {'table': row['table_id'], 'state': 'ended', 'aborted': True, 'archived': str(shelf)}


def status(ctx: Context) -> dict[str, Any]:
    row = table_row(ctx)
    found = shown(ctx, row)
    if ctx.nouns.get('report') and found.get('report'):
        found['report_text'] = (Path(ctx.require_store().project().path) / found['report']).read_text(
            encoding='utf-8')
    return found


def read_reference(ctx: Context) -> dict[str, Any]:
    """Open an accepted message, a cited source passage or a bounded literal search inside this project."""
    from . import references

    return references.read(ctx)


def listed_tables(ctx: Context) -> dict[str, Any]:
    with ctx.require_store().tables(write=False) as tx:
        rows = list(tx.rows('tables', by=('created',), limit=0).results)
    return {'tables': [shown(ctx, dict(row)) for row in reversed(rows)]}


def table_events(ctx: Context) -> dict[str, Any]:
    row = table_row(ctx)
    after = int(ctx.nouns.get('after') or 0)
    with ctx.require_store().tables(write=False) as tx:
        found = [dict(one) for one in tx.rows('events', {'table_id': row['table_id']}, limit=0).results
                 if int(one['seq']) > after]
    progress = phase_progress(ctx, row)
    if progress is not None:
        from .roundtable import export as engine_export
        from .roundtable import store as engine_store

        for one in found:
            payload = one['payload']
            if one['kind'] == 'veto' and not payload.get('veto_reason') and type(payload.get('n')) is int:
                try:
                    saved = engine_store.submission(int(row['discussion']), payload['n'])
                except engine_store.Missing:
                    continue
                one['payload'] = {**payload, 'veto_reason': engine_export.veto_reason(saved)}
    return {'table': row['table_id'], 'events': [{'seq': one['seq'], 'kind': one['kind'], 'audience': one['audience'],
                                                  'at': one['at'], **cast(dict[str, Any], one['payload'])}
                                                 for one in found],
            'latest': max((int(one['seq']) for one in found), default=after),
            'live_summary': live_summary.snapshot(ctx, str(row['table_id'])),
            'phase_budget': progress,
            'topic_selection': progress.get('topic_selection') if progress is not None else None}


def follow_table(ctx: Context) -> dict[str, Any]:
    row = table_row(ctx)
    if row['state'] in ('ended', 'refused', 'opening'):
        return shown(ctx, row)
    if follow.alive(row.get('follower')):
        return {**shown(ctx, row), 'said': 'Its follower is running.'}
    answer = started(ctx, row['table_id'])
    if 'refused' in answer:
        raise Stop(str(answer['refused']), str(answer.get('next') or 'metaform dispatch sessions'))
    return shown(ctx, table_row(ctx))


def adopt(ctx: Context) -> dict[str, Any]:
    """An idea of an ended table the person adopts, made a ticket at the part it concerns, the table's Address unless
    another is named, with the table as its source; Full Auto starts it like any ticket. Adopted once: the ticket an
    idea became is kept as the table's `adopted` event and given again."""
    row = table_row(ctx)
    if row['state'] != 'ended':
        raise Stop(f'Roundtable {row["table_id"]} has not ended: its ideas are adopted once its answer is in.',
                   f'metaform roundtables status {row["table_id"]}')
    given = str(ctx.nouns['idea']).strip().upper()
    wanted = f'I{given}' if given.isdigit() else given
    with ctx.require_store().tables(write=False) as tx:
        told = [dict(one) for one in tx.rows('events', {'table_id': row['table_id']}, limit=0).results]
    named = [cast(dict[str, Any], one['payload']) for one in told if one['kind'] == 'ideas']
    ideas = cast(list[dict[str, Any]], named[-1].get('ideas') or []) if named else []
    idea = next((one for one in ideas if str(one.get('id')) == wanted), None)
    if idea is None:
        raise Stop(f'Roundtable {row["table_id"]} named no idea {given}; its ideas are '
                   f'{", ".join(str(one.get("id")) for one in ideas) or "none"}.',
                   f'metaform roundtables events {row["table_id"]}')
    held = next((cast(dict[str, Any], one['payload']) for one in told
                 if one['kind'] == 'adopted' and cast(dict[str, Any], one['payload']).get('idea') == wanted), None)
    if held is not None:
        return {'table': row['table_id'], 'idea': wanted, 'ticket': held['work_id'], 'address': held['address'],
                'said': 'This idea was adopted already; its ticket is given again.'}
    store = ctx.require_store()
    given_address = str(ctx.nouns.get('address') or '').strip()
    part = str(row.get('address') or '')
    proposed = ''  # an Address the map does not hold: named in the note, never written to the map
    if part:
        address = given_address or part
    elif given_address and store.element(given_address) is not None:
        address = given_address
    else:
        found = follow.top_element(store)
        if found is None:
            raise Stop('The map holds no element yet, so the idea has no place to be filed at.',
                       'metaform help intake')
        address, proposed = found, given_address
    saved = str(cast(dict[str, Any], row.get('followed') or {}).get('saved') or '')
    report = (report_of(ctx, row) or f'{saved}/{follow.RECORD}' if saved
              else prompt_files.required(PACKAGE, 'adopted_unsaved'))
    fills = {'idea': str(idea.get('name') or wanted), 'substance': str(idea.get('summary') or ''),
             'question': str(row['topic']), 'answer': str(row.get('answer') or ''), 'table': str(row['table_id']),
             'address': part, 'report': report}
    note = prompt_files.required(PACKAGE, 'adopted_note' if part else 'adopted_note_question', **fills)
    if proposed:
        note += ' ' + prompt_files.required(PACKAGE, 'adopted_proposed', proposed=proposed)
    title = str(ctx.nouns.get('title') or idea.get('name') or wanted).strip()[:120]
    record = store.add_work(Node('element', address), None, kind='enhancement', title=title,
                            task=prompt_files.required(PACKAGE, 'adopted', **fills), note=note)
    seq = max((int(one['seq']) for one in told), default=0) + 1
    payload = {'idea': wanted, 'name': fills['idea'], 'work_id': record.id, 'address': address,
               **({'proposed': proposed} if proposed else {})}
    with store.tables() as tx:
        tx.concern(kind=follow.CHANGE_KIND)
        tx.concern(kind=f'{follow.CHANGE_KIND}:{row["table_id"]}')
        tx.insert('events', {'table_id': row['table_id'], 'seq': seq, 'kind': 'adopted', 'audience': 'person',
                             'payload': payload, 'at': follow.now()})
    ctx.publish(follow.TOPIC, {'table': row['table_id'], 'seq': seq, 'kind': 'adopted', 'audience': 'person',
                               **payload})
    return {'table': row['table_id'], 'idea': wanted, 'ticket': record.id, 'address': address,
            **({'proposed': proposed} if proposed else {}), 'title': title,
            'next': f'metaform map work id={record.id}',
            **({'notices': [{'where': one.where, 'message': one.message} for one in record.notices]}
               if record.notices else {})}


def run(ctx: Context) -> dict[str, Any]:
    return follow.run(ctx, str(ctx.nouns['table']))


def follow_through(ctx: Context) -> dict[str, Any]:
    return pipeline.prepare(ctx, str(ctx.nouns['table']))


TABLE = Noun('table', 'The table, by the id open returned; metaform roundtables tables lists them.')

MODULE = Module(
    id='roundtables',
    summary='Bring a question to a table of agents, through the Roundtable 2 engine; its report is the outcome.',
    purpose='Opens a table of agents on the person\'s question, through the person\'s Roundtable 2 engine: the seats '
            'debate it, focused on a part only when an Address is given, optional Jev judging filters novelty, the host summarises '
            'the answer, and the page shows its synthesis, rankings and saved transcript. Details: metaform help roundtables.',
    details='Seats are claude/<model>, codex/<model>, antigravity/<model> or OpenRouter model ids. Each seat takes one '
            'of dispatch\'s agent slots. A table spends at most roundtables_spend dollars. Its events reach the bus as '
            'roundtables.event and other processes as map.changed of kind roundtables.',
    verbs=(
        Verb('open', open_table, 'Open a table on a question, with its seats in speaking order.',
             nouns=(Noun('topic', 'The question the table answers; it is the whole frame of the table.'),
                    Noun('address', 'The Address of a part to focus the table on; its context opens the table. Left '
                                    'out, the table is limited to no part.', required=False),
                    Noun('seats', 'The seats in speaking order: claude/<model>, codex/<model>, antigravity/<model> or an '
                                  'OpenRouter model id; roundtables_seats when left out.', kind='json',
                         schema={'type': 'array', 'items': {'type': 'string'}}, required=False),
                    Noun('host', 'Who summarises the seats\' rankings; the first seat when left out.',
                         required=False),
                    Noun('synthesizer', 'Who names the ideas; the host when left out.', required=False),
                    Noun('judging', 'Use optional Jev novelty filtering; project default when omitted.',
                         kind='bool', required=False),
                    Noun('reply_limit', 'Base characters per turn before pass and busy-message credits; 512 when omitted.', kind='int',
                         required=False),
                    Noun('token_budget', 'Counted tokens per agent per round; resets each '
                         'round. Warn at 50% and 80%, closing statements at 100%, advance at 120%. Zero disables it.',
                         kind='int', required=False),
                    Noun('token_basis', 'uncached input plus output (default), output only, or all including cached '
                         'reads.', required=False,
                         schema={'type': 'string', 'enum': ['uncached', 'output', 'all']}),
                    Noun('permissions', 'Per-agent permission prompts and native ACP mode for the complete session; '
                         'project settings when left out.', kind='json', required=False,
                         schema={'type': 'object', 'additionalProperties': {'type': 'object',
                                 'properties': {'prompts': {'type': 'string'}, 'mode': {'type': 'string'}},
                                 'additionalProperties': False}}),
                    Noun('spend', 'The most US dollars, such as 0.50, up to roundtables_spend.', required=False),
                    Noun('automate_ticket_creation', 'Automate Ticket Creation: prepare through an inactive populated '
                         'board and execution outline without decisions. Default off.', kind='bool', required=False),
                    Noun('compress_between_topics', 'Use native conversation compression between session topics, '
                         'guided by the selected next topic. Keeps the same conversations. Default off.',
                         kind='bool', required=False),
                    Noun('chain', 'Run this many rounds with the same participants, editing shared files inline. '
                                  'Private proposals select each next topic; after the last, participants score '
                                  'each other.', kind='int', required=False)),
             switches=('roundtables_spend', 'roundtables_seats', 'roundtables_judging',
                       'roundtables_context_tokens', 'roundtables_judging_context_tokens'), open_world=True),
        Verb('comment', comment, 'As the chair, say something to the table at its next gap between turns.',
             nouns=(TABLE, Noun('text', 'What the chair says.')), open_world=True),
        Verb('hold', hold, 'As the chair, hold the table after the turn in flight.', nouns=(TABLE,),
             open_world=True),
        Verb('continue', continued, 'Resume a held table or continue a completed table from its saved summary.',
             nouns=(TABLE, Noun('spend', 'Optional replacement table budget, up to roundtables_spend.',
                                required=False)), open_world=True),
        Verb('advance', advance, 'As the chair, finish the current topic discussion, preserving completed work ', nouns=(TABLE,), open_world=True),
        Verb('reseat', reseat, 'As the chair, bring a seat that left or failed back to the table.',
             nouns=(TABLE, Noun('seat', 'The seat, by its id or its name at the table.')), open_world=True),
        Verb('budget', set_token_budget, 'Set the per-agent token budget for discussion rounds without '
             'resetting the current counters.',
             nouns=(TABLE, Noun('token_budget', 'Tokens per agent per phase; zero disables the budget.', kind='int'),
                    Noun('token_basis', 'Optional uncached, output or all. A basis adjustment requires a stopped '
                         'runner and recounts the current phase; omitted preserves the existing basis.',
                         required=False, schema={'type': 'string', 'enum': ['uncached', 'output', 'all']})),
             open_world=True),
        Verb('permit', permit, 'Answer an agent\'s ACP permission request with one of its supplied options.',
             nouns=(TABLE, Noun('request', 'The waiting permission request id.'),
                    Noun('option', 'The option id supplied by the agent.')), surfaces=('cli',),
             open_world=True),
        Verb('abort', abort, 'As the chair, abort the table at once: ended now, with no report, no further turn and no '
                             'next table, so nothing more is spent.', nouns=(TABLE,), open_world=True),
        Verb('end', end, 'As the chair, end the table and save its result and transcript.', nouns=(TABLE,),
             open_world=True),
        Verb('status', status, 'A table: its state, seats, spend, topics, answer and saved transcript.',
             nouns=(TABLE, Noun('report', 'true: the saved transcript\'s text too.', kind='bool',
                                required=False)),
             effect='read'),
        Verb('reference', read_reference, 'Read a cited accepted message, project file or literal search.',
             nouns=(TABLE, Noun('reference', 'A public message ID, file with optional line, or literal rg/grep search.')),
             effect='read'),
        Verb('tables', listed_tables, 'Every table of the project, newest first.', effect='read'),
        Verb('follow-through', follow_through, 'Prepare or resume the finished table\'s approved stages.',
             nouns=(TABLE,)),
        Verb('review', pipeline.review, 'Read the full current output and its exact revision.',
             nouns=(TABLE, Noun('origin', 'Source project id for a stage in another project.', required=False)),
             effect='read'),
        Verb('submit', pipeline.submit, 'Publish the current role\'s output for the person\'s decision.',
             nouns=(TABLE, Noun('stage', 'The stage this assignment delivers.'),
                    Noun('work', 'The current stage ticket id.'), Noun('file', 'Output inside the assignment folder.'),
                    Noun('origin', 'Source project id when working in a new project.', required=False),
                    Noun('project_name', 'Architect\'s name for the new project.', required=False),
                    Noun('board', 'Decomposer\'s fresh board name.', required=False))),
        Verb('decide', pipeline.decide, 'Record the person\'s decision on the current stage output.',
             nouns=(TABLE, Noun('action', 'yes, no, comment, revise or approve.',
                               schema={'enum': ['yes', 'no', 'comment', 'revise', 'approve']}),
                    Noun('digest', 'SHA-256 of the output the person reviewed.'),
                    Noun('revision', 'The reviewed stage revision.', kind='int'),
                    Noun('comment', 'The person\'s comments on the plan, sent back for planning again.', required=False))),
        Verb('events', table_events, 'A table\'s events after a cursor, as its follower told them.',
             nouns=(TABLE, Noun('after', 'The seq of the last event read; 0 for all.', kind='int', required=False)),
             effect='read'),
        Verb('follow', follow_table, 'Start a table\'s follower again when it stopped before the table ended.',
             nouns=(TABLE,), open_world=True),
        Verb('adopt', adopt, 'Adopt an idea of an ended table as a ticket, the table its source.',
             nouns=(TABLE, Noun('idea', 'The idea, by its id at the table, such as I2; metaform roundtables events '
                                        'lists them under ideas.'),
                    Noun('address', 'Where the idea would live. On a table about a part: the part it concerns, the '
                                    'table\'s own when left out. On a table with no part: the ticket goes there when '
                                    'the map holds it, else at the project\'s top element with this Address in its '
                                    'note.', required=False),
                    Noun('title', 'The ticket\'s title; the idea\'s name when left out.', required=False))),
        Verb('run', run, 'Follow one table in this process until it ends. open and follow run it detached.',
             nouns=(TABLE,), surfaces=('cli',), open_world=True),
    ),
    tables=TABLES,
    subscriptions=(Subscription('intake.completed', pipeline.intake_finished),
                   Subscription('map.changed', pipeline.tasks_changed)),
)
