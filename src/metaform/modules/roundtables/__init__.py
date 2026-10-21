"""roundtables: the person brings a question to a table of agents, and the agents debate it, build on each other's
ideas and go on until it is answered, through the Roundtable 2 engine. The table exists for its report, which the
person's system agent writes when the table ends.

The engine is the person's standalone program, `roundtable`, an MCP and A2A server
(https://github.com/RchGrav/roundtable); this module connects Metaform to it and ports nothing of it. Its seats speak
in turn, 512 characters each; Jev, through OpenRouter, keeps only what is new and on the topic; after the discussion a
synthesizer names the ideas, every seat ranks them and explains its choices, and the host summarises.

- `open` opens a table on the person's question, which is the table's one topic and its whole frame: it is limited to
  no part and to no project. An Address given focuses it on that part: the opening then holds the part's context from
  the map, its element, the joins it receives and provides with their purposes and encounter functions, and the
  memories at it. Seats are Metaform's own agents, `claude/<model>`, `codex/<model>` and `antigravity/<model>`, which the
  engine runs through its own ACP client with dispatch's commands, and OpenRouter models by their id, which the engine
  calls itself.
- The chair's controls are the engine's: `comment`, `hold`, `continue`, `advance`, `reseat` and `end`.
- A follower for each table, `follow.py`, turns what the table does into events: on the bus as `roundtables.event`,
  and in the project's `events` table, whose writes reach every other process of the home, the web page's among them,
  as `map.changed` naming the kind `roundtables`.
- The table ends when Jev judges its topic covered and the host has summarised, or when the person ends it. Its
  answer is the host's summary. Its record is saved in the project and handed to the person's system agent, which
  writes the report from it and saves it beside the record. Adopting an idea as a ticket, `adopt`, comes after.

Guardrails. Each seat takes one of dispatch's agent slots, through dispatch's own gate, so a table is refused when
fewer are free than its seats. A table spends at most `roundtables_spend` US dollars through OpenRouter, a cap only
the person raises. Seats read the project folder and change nothing: the engine gives them only reading tools, refuses
every write they ask for, and this module never gives them an MCP server. Operational events, credits, holds and a
seat lost, are the person's and never reach a seat or Jev. Opening a table sends the question, and the part's context
when a part is given, to OpenRouter, so it waits for the person's own `jev` setting. The tables and their events are
kept at the project's level, so a base switch, a clear or a restore never takes them.
"""
from __future__ import annotations

import json
import os
import secrets
import selectors
import subprocess
import sys
from importlib import resources
from pathlib import Path
from typing import Any, cast

from metaform import outline, prompt_files, settings
from metaform.data import Column, Index, Node, Table, Tables
from metaform.module import Context, Module, Noun, Stop, Verb, context, node_items, provided

from . import engine, follow

SUPPORTED_OS = ('linux', 'macos')  # a follower and the engine's servers are detached into a session of their own
DEPENDENCIES = ()
SHIPS_DISABLED = False  # a person can open a table in any project once the engine is installed

PACKAGE = resources.files(__name__)
OPEN_LIMIT = engine.CALL_LIMIT + 30  # seconds `open` waits for its follower's first line: a deadline on one request
CHAIR = ('state', 'reason', 'stage', 'topic', 'round', 'turn_of', 'spend', 'spent', 'runner')

settings.text('roundtables_engine', 'roundtable', scope='global', person_only=True, label='Roundtable engine',
              category='integrations', heading='Roundtables',
              help='The command that runs the Roundtable 2 engine, such as <its folder>/.venv/bin/roundtable.',
              details='Metaform runs it as `<command> serve` to open and chair a table and `<command> web` to follow '
                      'one. OPENROUTER_API_KEY must be set where Metaform runs: Jev judges every turn through '
                      'OpenRouter.')
settings.number('roundtables_spend', 2, min=0, max=100, person_only=True, label='Most a table spends (US dollars)',
                category='integrations', heading='Roundtables',
                help='The most one table spends through OpenRouter, its model seats and Jev; open may only lower it.')


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


settings.items('roundtables_seats', ('claude/opus', 'codex/astra', 'codex/sol', 'claude/fable'), person_only=True,
               label='Seats a table opens with', category='integrations', heading='Roundtables', check=_check_seats,
               help='The seats, in speaking order, of a table opened without any named, as the page\'s roundtable '
                    'opens one: claude/<model>, codex/<model>, antigravity/<model> or OpenRouter model ids. A model is a '
                    'short name, such as opus or sol, which means the newest release of its family when the table '
                    'opens, or an exact value, such as gpt-6-sol, which pins one.')

# Version 2: a table's Address may be empty, a table on the question alone; the engine's reporter seat and its report
# are gone, since the person's system agent writes the report from the saved record.
TABLES = Tables(version=2, tables=(
    Table('tables', place='project', key=('table_id',), columns=(
        Column('table_id', required=True), Column('address'), Column('topic', required=True),
        Column('opening', required=True), Column('seats', 'json', required=True), Column('host'),
        Column('synthesizer'), Column('rounds', 'int'), Column('spend', 'real', required=True),
        Column('state', required=True), Column('reason'), Column('discussion', 'int'), Column('chair'),
        Column('context_id'), Column('task_id'), Column('seated', 'json'), Column('follower', 'int'),
        Column('followed', 'json'), Column('answer'),
        Column('answered', 'bool', required=True, default=False), Column('created', required=True),
        Column('ended')),
        indexes=(Index(('created',)),)),
    Table('events', place='project', key=('table_id', 'seq'), columns=(
        Column('table_id', required=True), Column('seq', 'int', required=True), Column('kind', required=True),
        Column('audience', required=True), Column('payload', 'json', required=True), Column('at', required=True))),
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
    """Where the table's report is, from the project's folder, once the system agent has written it beside the
    table's record; None before."""
    saved = str(cast(dict[str, Any], row.get('followed') or {}).get('saved') or '')
    found = f'{saved}/{follow.REPORT}' if saved else ''
    return found if found and (Path(ctx.require_store().project().path) / found).is_file() else None


def shown(ctx: Context, row: dict[str, Any]) -> dict[str, Any]:
    followed = cast(dict[str, Any], row.get('followed') or {})  # where its record was saved and its memory kept
    report = report_of(ctx, row)
    return {'table': row['table_id'], **({'address': row['address']} if row.get('address') else {}),
            'topic': row['topic'], 'state': row['state'],
            **({'reason': row['reason']} if row.get('reason') else {}), 'seats': row['seats'],
            **({'seated': row['seated']} if row.get('seated') else {}),
            'spend': row['spend'], 'discussion': row.get('discussion'),
            'follower': 'running' if follow.alive(row.get('follower')) else 'stopped',
            'answered': bool(row.get('answered')), **({'answer': row['answer']} if row.get('answer') else {}),
            **({'report': report} if report else {}), 'created': row['created'],
            **({'ended': row['ended']} if row.get('ended') else {}),
            **{key: followed[key] for key in ('saved', 'recorded', 'handed', 'unhanded') if followed.get(key)}}


def started(ctx: Context, table_id: str) -> dict[str, Any]:
    """A follower started detached for the table, and the first line it says: opened, following or refused."""
    log = os.open(engine.folder_log() / 'followers.log', os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    env = {key: value for key, value in os.environ.items() if key not in engine.IDENTITY}
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


def open_table(ctx: Context) -> dict[str, Any]:
    if not settings.value('jev', ctx.folder):
        raise Stop('A table sends your question, and the part\'s context when it is about a part, to OpenRouter, where '
                   'Jev judges every turn, and only you allow project text to leave this machine.',
                   'metaform set --jev')
    engine.command(ctx.folder)
    address, topic = str(ctx.nouns.get('address') or '').strip(), str(ctx.nouns['topic']).strip()
    if not topic:
        raise Stop('A table opens on a question.', 'metaform roundtables open')
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
    text = opening(ctx, address, topic)
    table_id = secrets.token_hex(4)
    with ctx.require_store().tables() as tx:
        tx.concern(kind=follow.CHANGE_KIND)
        tx.insert('tables', {'table_id': table_id, 'address': address or None, 'topic': topic, 'opening': text,
                             'seats': seats, **roles, 'rounds': ctx.nouns.get('rounds'), 'spend': spend,
                             'state': 'opening', 'created': follow.now()})
    answer = started(ctx, table_id)
    if 'refused' in answer:
        raise Stop(str(answer['refused']), str(answer.get('next') or 'metaform dispatch sessions'))
    return {'table': table_id, **({'address': address} if address else {}), 'topic': topic,
            **{key: value for key, value in answer.items() if key != 'opened'},
            'next': f'metaform roundtables status {table_id}; its events: metaform roundtables events {table_id}'}


def chaired(ctx: Context, tool: str, **more: Any) -> dict[str, Any]:
    """One of the chair's controls, passed to the engine with the table's chair token."""
    row = table_row(ctx)
    if row['state'] in ('opening', 'refused') or row.get('discussion') is None:
        raise Stop(f'Roundtable {row["table_id"]} never opened: {row.get("reason") or row["state"]}.',
                   'metaform roundtables open')
    answer = engine.call(ctx.folder, tool, discussion=int(row['discussion']), chair=row['chair'], **more)
    return {'table': row['table_id'], **{key: answer[key] for key in CHAIR if key in answer}}


def comment(ctx: Context) -> dict[str, Any]:
    return chaired(ctx, 'comment', text=str(ctx.nouns['text']))


def hold(ctx: Context) -> dict[str, Any]:
    return chaired(ctx, 'hold')


def continued(ctx: Context) -> dict[str, Any]:
    return chaired(ctx, 'continue')


def advance(ctx: Context) -> dict[str, Any]:
    return chaired(ctx, 'advance')


def reseat(ctx: Context) -> dict[str, Any]:
    return chaired(ctx, 'reseat', seat=str(ctx.nouns['seat']))


def end(ctx: Context) -> dict[str, Any]:
    return chaired(ctx, 'end')


def status(ctx: Context) -> dict[str, Any]:
    row = table_row(ctx)
    found = shown(ctx, row)
    if ctx.nouns.get('report') and found.get('report'):
        found['report_text'] = (Path(ctx.require_store().project().path) / found['report']).read_text(
            encoding='utf-8')
    return found


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
    return {'table': row['table_id'], 'events': [{'seq': one['seq'], 'kind': one['kind'], 'audience': one['audience'],
                                                  'at': one['at'], **cast(dict[str, Any], one['payload'])}
                                                 for one in found],
            'latest': max((int(one['seq']) for one in found), default=after)}


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


ADOPT_CAUTION = ('Adopting an idea files a ticket that Full Auto starts like any other, so it spends agent time: the '
                 'person decides which ideas become work.')


TABLE = Noun('table', 'The table, by the id open returned; metaform roundtables tables lists them.')

MODULE = Module(
    id='roundtables',
    summary='Bring a question to a table of agents, through the Roundtable 2 engine; its report is the outcome.',
    purpose='Opens a table of agents on the person\'s question, through the person\'s Roundtable 2 engine: the seats '
            'debate it, focused on a part only when an Address is given, Jev keeps what is new, the host summarises '
            'the answer, and the person\'s system agent writes the report. Details: metaform help roundtables.',
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
                    Noun('rounds', 'The most rounds of discussion, up to the engine\'s own most.', kind='int',
                         required=False),
                    Noun('spend', 'The most US dollars, such as 0.50, up to roundtables_spend.', required=False)),
             switches=('roundtables_spend', 'roundtables_seats'), open_world=True),
        Verb('comment', comment, 'As the chair, say something to the table at its next gap between turns.',
             nouns=(TABLE, Noun('text', 'What the chair says.')), open_world=True),
        Verb('hold', hold, 'As the chair, hold the table after the turn in flight.', nouns=(TABLE,),
             open_world=True),
        Verb('continue', continued, 'As the chair, run a held table again.', nouns=(TABLE,), open_world=True),
        Verb('advance', advance, 'As the chair, end the topic\'s discussion after its fewest rounds, for its '
                                 'synthesis, rankings and summary.', nouns=(TABLE,), open_world=True),
        Verb('reseat', reseat, 'As the chair, bring a seat that left or failed back to the table.',
             nouns=(TABLE, Noun('seat', 'The seat, by its id or its name at the table.')), open_world=True),
        Verb('end', end, 'As the chair, end the table: its record is saved here and the person\'s system agent '
                         'writes its report.', nouns=(TABLE,),
             open_world=True),
        Verb('status', status, 'A table: its state, seats, spend, answer, its saved record and its report once '
                               'written.',
             nouns=(TABLE, Noun('report', 'true: the report\'s text too, once written.', kind='bool',
                                required=False)),
             effect='read'),
        Verb('tables', listed_tables, 'Every table of the project, newest first.', effect='read'),
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
                    Noun('title', 'The ticket\'s title; the idea\'s name when left out.', required=False)),
             person_decides=lambda ctx: ADOPT_CAUTION),
        Verb('run', run, 'Follow one table in this process until it ends. open and follow run it detached.',
             nouns=(TABLE,), surfaces=('cli',), open_world=True),
    ),
    tables=TABLES,
)
