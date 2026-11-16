"""roundtables: a table opened at an Address through the Roundtable 2 engine, followed live and chaired from Metaform,
ticket code.gateway.messaging#3.

The engine is the one shipped inside the module, run as a fresh install runs it, with no engine on PATH, and with
its own fakes as its offline proof runs it: its stub OpenRouter and Jev on the loopback (fakes.py) and its fake ACP
agent (fake_agent.py) as Claude Code. Nothing is paid for and nothing leaves the machine.
"""
from __future__ import annotations

import json
import os
import shutil
import signal
import sys
import threading
import time
from pathlib import Path
from typing import Any

import pytest

from metaform import events
from metaform.data import Store
from metaform.module import Context
from metaform.modules.dispatch.names import is_name
from metaform.modules.roundtables import engine, follow
from metaform.modules.roundtables.tests import fakes

pytestmark = pytest.mark.kind('simulation')

FAKE_AGENT = Path(__file__).with_name('fake_agent.py')
ADDRESS = 'code.gateway.messaging'
PURPOSE = 'Accept external agent work as project-addressed tickets.'
MEMORY = 'Peers are named by the person'
LIMIT = 240.0  # seconds a fake table has to end
REPORT_MARK = 'The roundtable has ended'
STAGE_MARKS = ('# Topic synthesis', '# Rank collected ideas', '# Explain your top three', '# Explain your bottom three',
               '# Host summary', REPORT_MARK, 'could not be read as every idea')  # the offline proof's

def stubbed(*, pace: float = 0.0) -> Any:
    """The stub with a table's worth of behaviour, as the offline proof has it: vega's second turn vetoed, and voluntary PASS replies
    after three contributions, so a complete unanimous round ends discussion.
    `pace` slows every seat's turn so the chair acts while the table runs."""
    base = fakes.Stub

    class Offline(base):  # type: ignore[misc, valid-type]
        def chat(self, body: dict[str, Any]) -> tuple[int, dict[str, Any]]:
            last = json.dumps(body['messages'][-1]['content'])
            time.sleep(pace)  # a stub's pacing, so the table is still running when the chair acts
            code, answer = super().chat(body)
            asked = sum(1 for one in self.chats if one.get('session_id') == body.get('session_id'))
            if code == 200 and body['model'] == 'stub/vega' and asked == 2 and not any(mark in last
                                                                                     for mark in STAGE_MARKS):
                answer['choices'][0]['message']['content'] = 'vega agrees, veto this, it adds nothing.'
            if code == 200 and asked >= 4 and not any(mark in last for mark in STAGE_MARKS):
                answer['choices'][0]['message']['content'] = 'PASS'
            return code, answer

    return Offline()


@pytest.fixture
def table(run, tmp_path, monkeypatch):
    """A project with the part on its map and a memory at it, the engine set up with its fakes in a home of its own,
    dispatch on for the slots, and the person's jev on."""
    folder = tmp_path / 'proj'
    folder.mkdir()
    run('add', 'project', 'proj', str(folder))
    store = Store('proj')
    with store.atomic():
        store.layer('intake-1', 'intake', 'The functional map.', kind='intake', mutable=False, hideable=False,
                    provenance={'module': 'intake'}, ready=True)
        store.add_element('intake-1', 'code.server.tool', name_length=2, role='DE')
        store.add_element('intake-1', ADDRESS, name_length=2, role='SE')
        store.add_join('intake-1', 'code.server.tool', ADDRESS, purpose=PURPOSE, ef='Hands over a peer\'s task.')
    run('memory', 'create_entities', json.dumps([{
        'name': MEMORY, 'entityType': 'behaviour', 'title': MEMORY, 'why': 'A seat must not invent peers.',
        'observations': ['Only a peer the person names in the home can be sent a message.']}]),
        f'node=element:{ADDRESS}', cwd=folder)
    run('enable', 'dispatch', cwd=folder)
    run('set', '--jev', cwd=folder)
    engine_home = tmp_path / 'engine'
    log = tmp_path / 'fake-acp.log'
    for key, value in {'ROUNDTABLE_HOME': str(engine_home), 'OPENROUTER_API_KEY': 'stub-key',
                       'ROUNDTABLE_AGENT_CLAUDE': f'{sys.executable} {FAKE_AGENT}',
                       'ROUNDTABLE_AGENT_WAIT': '30', 'FAKE_ACP_PASS_AFTER': '3',
                       'ROUNDTABLE_REPORT_MODEL': 'stub/reporter', 'FAKE_ACP_LOG': str(log)}.items():
        monkeypatch.setenv(key, value)
    yield folder, log
    run('dispatch', 'stop-all', cwd=folder, ok=False)


def serve(monkeypatch, stub: Any) -> Any:
    held = fakes.serve_stub(stub)
    monkeypatch.setenv('ROUNDTABLE_OPENROUTER_URL', f'http://127.0.0.1:{held.server_address[1]}/api')
    return held


class Heard:
    """The table's events as another process of the home hears them: each map.changed naming the kind roundtables,
    then the table's events read after the last seq held; `ended` is set once the end is told."""

    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []
        self.changes = 0
        self.ended = threading.Event()
        self.lock = threading.Condition()
        self.listener = events.listen('roundtables-test', self.heard)

    def heard(self, payload: dict[str, Any]) -> None:
        if 'roundtables' not in (payload.get('kinds') or []):
            return
        with self.lock:
            self.changes += 1
            seen = {(one['table_id'], int(one['seq'])) for one in self.events}  # each table counts its own seq
            with Store('proj', module='roundtables').tables(write=False) as tx:
                fresh = [dict(one) for one in tx.rows('events', limit=0).results
                         if (one['table_id'], int(one['seq'])) not in seen]
            self.events += fresh
            if any(one['kind'] == 'end' for one in fresh):
                self.ended.set()
            self.lock.notify_all()

    def told(self, check: Any, limit: float = LIMIT) -> bool:
        """Whether an event that passes `check` is heard within the limit, woken by each one heard."""
        with self.lock:
            return self.lock.wait_for(lambda: any(check(one) for one in self.events), limit)

    def kinds(self) -> list[str]:
        with self.lock:
            return [str(one['kind']) for one in self.events]

    def close(self) -> None:
        self.listener.close()


def seat_entries(home: Path) -> list[Path]:
    return sorted((home / 'run' / 'dispatch' / 'agents').glob('*-seat-*.json'))


def opened(run, folder: Path, *args: str) -> dict[str, Any]:
    return json.loads(run('roundtables', 'open', 'How should agents in two projects reach each other?',
                          f'address={ADDRESS}', *args, '--json', cwd=folder).stdout)


def gone(paths_of: Any, limit: float = 30.0) -> bool:
    deadline = time.monotonic() + limit
    while paths_of():
        if time.monotonic() > deadline:
            return False
        time.sleep(0.2)
    return True


def test_a_seats_short_name_means_the_newest_release_of_its_family_as_the_table_opens(run, tmp_path):
    """A seat's model is a short name or an exact value, resolved from the agent's current models when the table
    opens: sol is the newest sol, and a new release is picked up with no change; Claude's own alias is itself; a word
    that is none of the agent's models is refused naming its families and the nearest; an agent that has not run here
    is kept unchecked."""
    from metaform.module import Stop, context
    folder = tmp_path / 'proj'
    folder.mkdir()
    run('add', 'project', 'proj', str(folder))
    run('enable', 'dispatch', cwd=folder)
    from metaform.modules.roundtables import seat_of  # as loaded now: a run loads the modules again

    def offers(agent: str, *values: str) -> None:
        from metaform.modules.dispatch import offered as harness_offered
        harness_offered.keep(agent, {'state': 'ready', 'version': '9', 'name': agent, 'seen': '2026-10-21T00:00:00Z',
                                     'settings': [
            {'id': 'model', 'name': 'Model', 'category': 'model', 'type': 'select', 'current': values[0],
             'options': [{'value': value, 'name': value} for value in values]}]})
    ctx = context('roundtables', folder, project='proj')
    assert seat_of(ctx, 'codex/sol') == 'acp:codex/sol', 'not run here: kept as written'
    offers('codex', 'gpt-6.1-sol', 'gpt-6-astra', 'gpt-6-sol', 'gpt-5.6-sol')
    offers('claude', 'default', 'opus', 'fable', 'claude-opus-5')
    assert [seat_of(ctx, seat) for seat in ('codex/sol', 'codex/astra', 'codex/gpt-6-sol', 'claude/fable')] == \
        ['acp:codex/gpt-6.1-sol', 'acp:codex/gpt-6-astra', 'acp:codex/gpt-6-sol', 'acp:claude/fable']
    offers('codex', 'gpt-6.2-sol', 'gpt-6.1-sol', 'gpt-6-astra')
    assert seat_of(ctx, 'codex/sol') == 'acp:codex/gpt-6.2-sol', 'the new release, with no change'
    with pytest.raises(Stop, match='sol, astra each mean the newest release of their family'):
        seat_of(ctx, 'codex/nope')
    refused = run('set', '--roundtables-seats=claude/opus,codex/astr', cwd=folder, ok=False)
    assert 'nearest is astra, now gpt-6-astra' in refused.stdout + refused.stderr


@pytest.mark.timeout(LIMIT + 60)
def test_a_fresh_install_with_no_engine_on_path_runs_a_table_where_every_seat_gets_to_speak(run, home, table, monkeypatch):
    """The engine ships inside the module: with no `roundtable` anywhere on PATH, a table on the question alone opens,
    ready seats speak while others start, every participant contributes, and it runs to its answer."""
    folder, _ = table
    monkeypatch.setenv('PATH', os.pathsep.join((str(Path(sys.executable).parent), '/usr/bin', '/bin')))
    assert shutil.which('roundtable') is None, 'no engine on PATH'
    held = serve(monkeypatch, stubbed())
    heard = Heard()
    try:
        answer = json.loads(run('roundtables', 'open', 'How should a table be heard?', 'host=stub/host',
                                'seats=' + json.dumps(['stub/vega', 'claude/haiku', 'stub/orion']), '--json',
                                cwd=folder).stdout)
        assert heard.ended.wait(LIMIT), f'the table did not end: {heard.kinds()}'
    finally:
        heard.close()
        held.shutdown()
    status = json.loads(run('roundtables', 'status', answer['table'], '--json', cwd=folder).stdout)
    assert len(status['seated']) == 3 and len(set(status['seated'])) == 3, status
    assert all(is_name(name) for name in status['seated']), status
    spoke = [one['payload']['seat'] for one in heard.events if one['kind'] in ('turn', 'veto')]
    assert set(spoke) == set(status['seated']), spoke  # Startup latency must not prevent anyone else speaking.
    assert status['state'] == 'ended' and status['answered'] and 'summarises' in status['answer'], status


@pytest.mark.timeout(150)
def test_two_round_native_session_selects_privately_and_finishes_without_an_intertopic_discussion(
        run, table, monkeypatch):
    """Real MCP, ACP, follower and local judging transports exercise the full autonomous session."""
    from metaform.modules.roundtables.roundtable import store as native

    folder, log = table
    stub = stubbed()
    service = serve(monkeypatch, stub)
    heard = Heard()
    answer = None
    try:
        answer = opened(run, folder, 'seats=' + json.dumps(['claude/haiku', 'claude/opus']),
                        'host=stub/host', 'chain=2')
        assert heard.ended.wait(100), heard.kinds()
        status = json.loads(run('roundtables', 'status', answer['table'], '--json', cwd=folder).stdout)
        assert status['state'] == 'ended', status
        number = status['discussion']
        found = native.discussion(number)
        assert found['topic'] == 1 and found['stage'] == 'farewell'
        assert len(native.topics(number)) == 2
        assert not any(row['kind'] == 'collab' for row in native.submissions(number))
        assert not any(one.get('payload', {}).get('stage') == 'collaboration' for one in heard.events)
        with native.connect() as db:
            proposals = [dict(row) for row in db.execute('SELECT * FROM topic_proposals WHERE discussion=?', (number,))]
            decisions = [dict(row) for row in db.execute('SELECT * FROM topic_decisions WHERE discussion=?', (number,))]
        assert len(proposals) == 2 and all(row['state'] == 'ready' and row['receipt'] for row in proposals)
        assert len(decisions) == 1 and decisions[0]['state'] == 'ready'
        assert len([body for body in stub.decisions if set(body['questions']) == {'p0_1'}]) == 1
        assert len(native.scorecards(number)) == 2
        materials = Path(status['materials'])
        assert all(name in (materials / 'participants.md').read_text() for name in status['seated'])
        assert not (materials / 'next-topic.md').exists()
        shared = json.loads((folder / status['saved'] / 'export.json').read_text())
        assert 'judgments' not in shared
        assert all(row['kind'] in ('seat', 'chair') for row in shared['submissions'])
        assert all(brand not in json.dumps(shared).lower() for brand in ('acp:claude/', 'claude/haiku', 'claude/opus'))
        for topic in (1, 2):
            ids = [int(row['message_id'].split('-')[1]) for row in shared['submissions'] if row.get('topic') == topic]
            assert ids == list(range(1, len(ids) + 1))
        requests = [row['message']['params'] for row in map(json.loads, log.read_text().splitlines())
                    if row.get('message', {}).get('method') == 'session/prompt']
        text = lambda row: '\n'.join(block.get('text', '') for block in row.get('prompt', []) if block.get('type') == 'text')
        intros = [row for row in requests if 'You are participating in a roundtable discussion as' in text(row)]
        assert len(intros) == 2, 'Existing participants must retain their original sessions and context.'
        assert len([row for row in requests if '# Private next-topic proposal' in text(row)]) == 2
    finally:
        if answer and not heard.ended.is_set():
            run('roundtables', 'end', answer['table'], cwd=folder, ok=False)
        heard.close()
        service.shutdown()


@pytest.mark.timeout(LIMIT + 60)
def test_a_table_at_an_address_opens_on_the_parts_context_and_its_events_are_heard_as_it_runs_to_its_answer(
        run, home, table, monkeypatch):
    folder, log = table
    stub = stubbed()
    held = serve(monkeypatch, stub)
    heard = Heard()
    try:
        answer = opened(run, folder, 'seats=' + json.dumps(['claude/haiku', 'stub/vega']), 'host=stub/host')
        assert len(seat_entries(home)) == 2, 'each seat holds one agent slot while the table runs'
        assert heard.ended.wait(LIMIT), f'the table did not end: {heard.kinds()}'
        kinds = heard.kinds()
        # the events came while the table ran, each write of the follower heard by this process as it happened
        assert heard.changes > 3 and kinds.index('turn') < kinds.index('end')
        for kind in ('turn', 'veto', 'stage', 'ideas', 'rankings', 'summary', 'end'):
            assert kind in kinds, (kind, kinds)
        end = next(one for one in heard.events if one['kind'] == 'end')
        assert end['audience'] == 'person' and end['payload']['answered'] is True
        status = json.loads(run('roundtables', 'status', answer['table'], '--json', cwd=folder).stdout)
        assert status['state'] == 'ended' and status['answered'] and 'summarises' in status['answer']
        assert status['topics'] and any(one.get('borda') for one in status['topics'])
    finally:
        heard.close()
        held.shutdown()
    # the opening every seat read first is the part's context and the question
    first = next(body for body in stub.chats if body['model'] == 'stub/vega')
    seen = json.dumps(first['messages'])
    assert ADDRESS in seen and PURPOSE in seen and MEMORY in seen and 'two projects reach each other' in seen
    # The same ACP v2 setup is used by every agent. This fixture requests no permission.
    lines = [json.loads(line) for line in log.read_text().splitlines()]
    assert not [line for line in lines if 'permission' in line]
    initialized = [line['message']['params'] for line in lines
                   if line.get('message', {}).get('method') == 'initialize']
    assert initialized and all(one['protocolVersion'] == 2 for one in initialized)
    sessions = [line['message']['params'] for line in lines if line.get('message', {}).get('method') == 'session/new']
    assert sessions and all(not one.get('mcpServers') for one in sessions)
    assert gone(lambda: seat_entries(home)), 'the slots go back when the table ends'
    # the table's record is saved in the project: the engine's mechanical report and its export with the Borda count;
    # the engine's record supplies the result without another report-writing agent
    saved = folder / status['saved']
    assert status['saved'].startswith('docs/roundtables/') and not (saved / 'report.md').exists(), status
    assert (saved / 'mechanical-report.md').is_file()
    assert any(one.get('borda') for one in json.loads((saved / 'export.json').read_text())['topics'])
    # its outcome is one memory at the Address it was raised at, naming the question and the answer, linked to the
    # saved record
    graph = json.loads(run('memory', 'read_graph', f'node=element:{ADDRESS}', '--json', cwd=folder).stdout)
    kept = [one for one in graph['entities'] if one['entityType'] == 'roundtable']
    assert len(kept) == 1 and kept[0]['name'] == status['recorded'], graph
    said = ' '.join(kept[0]['observations'])
    assert 'two projects reach each other' in said and 'summarises' in said, said
    assert f'{status["saved"]}/export.json' in said, said
    # an idea the person adopts becomes one ticket at its part, with the table as its source, once
    idea = next(one for one in heard.events if one['kind'] == 'ideas')['payload']['ideas'][0]
    adopted = json.loads(run('roundtables', 'adopt', answer['table'], idea['id'], '--json', cwd=folder).stdout)
    again = json.loads(run('roundtables', 'adopt', answer['table'], idea['id'], '--json', cwd=folder).stdout)
    assert again['ticket'] == adopted['ticket']
    listed = json.loads(run('map', 'work', f'node={ADDRESS}', 'limit=0', '--json', cwd=folder).stdout)
    made = [one for one in listed['results'] if answer['table'] in (one.get('note') or '')]
    assert [one['id'] for one in made] == [adopted['ticket']] and made[0]['address'] == ADDRESS, made
    ticket = json.loads(run('map', 'work', f'id={adopted["ticket"]}', '--json', cwd=folder).stdout)
    assert not ticket['held'] and idea['name'] in ticket['task'], 'a ticket Full Auto starts, on the idea'


def test_a_table_ended_with_no_report_records_its_outcome_citing_its_export_and_adopt_passes_on_the_maps_notice(
        run, table):
    """Memory refuses a citation of a missing file, so a table the engine wrote no report for cites its saved export;
    an idea adopted at a part the map does not hold is filed with the map's notice that says so."""
    folder, _ = table
    store = Store('proj', module='roundtables')
    with store.tables() as tx:
        tx.insert('tables', {'table_id': 'rt1', 'address': ADDRESS, 'topic': 'Who reaches whom?', 'opening': '.',
                             'seats': ['stub/vega'], 'spend': 0.0, 'state': 'ended', 'created': follow.now(),
                             'followed': {'saved': 'docs/roundtables/1-who-reaches-whom'}})
        tx.insert('events', {'table_id': 'rt1', 'seq': 1, 'kind': 'ideas', 'audience': 'table', 'at': follow.now(),
                             'payload': {'ideas': [{'id': 'I1', 'name': 'Named peers', 'summary': 'Peers by name.'}]}})
    saved = folder / 'docs' / 'roundtables' / '1-who-reaches-whom'
    saved.mkdir(parents=True)
    (saved / 'export.json').write_text('{}\n', encoding='utf-8')
    listed = [{'host_summary': {'name': 'host', 'text': 'Peers are named.'}}]
    follower = follow.Follower(Context('roundtables', folder, project='proj', store=store), 'rt1')
    recorded, unrecorded = follower.recorded(listed, 'Peers are named.', 'docs/roundtables/1-who-reaches-whom')
    assert recorded and unrecorded is None, unrecorded
    graph = json.loads(run('memory', 'read_graph', f'node=element:{ADDRESS}', '--json', cwd=folder).stdout)
    kept = [one for one in graph['entities'] if one['entityType'] == 'roundtable']
    assert [one['name'] for one in kept] == [recorded], graph
    said = ' '.join(kept[0]['observations'])
    assert 'docs/roundtables/1-who-reaches-whom/export.json' in said, said
    adopted = json.loads(run('roundtables', 'adopt', 'rt1', 'I1', 'address=no.such.part', '--json', cwd=folder).stdout)
    assert any('No current element' in one['message'] for one in adopted.get('notices', [])), adopted


def broken(monkeypatch, tmp_path: Path) -> None:
    """The shipped engine made to fail at once: its home is a file, so it cannot open its store."""
    held = tmp_path / 'engine-home-is-a-file'
    held.write_text('')
    monkeypatch.setenv('ROUNDTABLE_HOME', str(held))


def openings(run, folder: Path, tmp_path: Path, monkeypatch) -> dict[str, str]:
    """Each table's opening as `open` kept it, by its question, the engine failing at once, so the table is refused
    after its opening is written and no seat starts."""
    broken(monkeypatch, tmp_path)
    run('roundtables', 'open', 'What could a peer directory be?', 'seats=["stub/vega"]', cwd=folder, ok=False)
    run('roundtables', 'open', 'Who reaches whom?', f'address={ADDRESS}', 'seats=["stub/vega"]', cwd=folder, ok=False)
    with Store('proj', module='roundtables').tables(write=False) as tx:
        return {str(one['topic']): str(one['opening']) for one in tx.rows('tables', limit=0).results
                if one['address'] in (None, ADDRESS)}


def test_a_table_with_no_address_opens_on_the_question_alone_and_one_with_an_address_on_the_part(
        run, table, tmp_path, monkeypatch):
    folder, _ = table
    found = openings(run, folder, tmp_path, monkeypatch)
    alone = found['What could a peer directory be?']
    assert 'What could a peer directory be?' in alone, alone
    assert ADDRESS not in alone and PURPOSE not in alone and MEMORY not in alone, alone
    focused = found['Who reaches whom?']
    assert ADDRESS in focused and PURPOSE in focused and MEMORY in focused, focused


def test_a_table_with_no_part_records_its_result_and_files_ideas_where_the_map_holds_them(
        run, table):
    """A table about no part keeps its outcome at the project's top element. Adopted ideas go to existing map
    Addresses, or the top element with the proposed Address in the note."""
    folder, _ = table
    store = Store('proj', module='roundtables')
    saved = 'docs/roundtables/2-peer-directory'
    ideas = [{'id': 'I1', 'name': 'Peer list', 'summary': 'One list.'},
             {'id': 'I2', 'name': 'Named peers', 'summary': 'By name.'},
             {'id': 'I3', 'name': 'Peer directory', 'summary': 'A directory.'}]
    with store.tables() as tx:
        tx.insert('tables', {'table_id': 'rt2', 'topic': 'What could a peer directory be?', 'opening': '.',
                             'seats': ['stub/vega'], 'spend': 0.0, 'state': 'ended', 'created': follow.now(),
                             'followed': {'saved': saved}})
        tx.insert('events', {'table_id': 'rt2', 'seq': 1, 'kind': 'ideas', 'audience': 'table', 'at': follow.now(),
                             'payload': {'ideas': ideas}})
    (folder / saved).mkdir(parents=True)
    (folder / saved / 'export.json').write_text('{}\n', encoding='utf-8')
    follower = follow.Follower(Context('roundtables', folder, project='proj', store=store), 'rt2')
    recorded, unrecorded = follower.recorded([], '', saved)
    assert recorded and unrecorded is None, unrecorded
    graph = json.loads(run('memory', 'read_graph', 'node=element:code.server.tool', '--json', cwd=folder).stdout)
    assert [one['name'] for one in graph['entities'] if one['entityType'] == 'roundtable'] == [recorded], graph
    top = json.loads(run('roundtables', 'adopt', 'rt2', 'I1', '--json', cwd=folder).stdout)
    held = json.loads(run('roundtables', 'adopt', 'rt2', 'I2', f'address={ADDRESS}', '--json', cwd=folder).stdout)
    new = json.loads(run('roundtables', 'adopt', 'rt2', 'I3', 'address=code.peers.directory', '--json',
                         cwd=folder).stdout)
    assert (top['address'], held['address'], new['address']) == ('code.server.tool', ADDRESS, 'code.server.tool')
    assert new['proposed'] == 'code.peers.directory' and not new.get('notices'), new
    ticket = json.loads(run('map', 'work', f'id={new["ticket"]}', '--json', cwd=folder).stdout)
    assert 'code.peers.directory' in ticket['note'] and ticket['kind'] == 'enhancement', ticket
    assert Store('proj').element('code.peers.directory') is None, 'a ticket never changes the map'


@pytest.mark.timeout(LIMIT + 60)
def test_hold_and_end_work_from_metaform_and_the_result_is_saved(run, home, table,
                                                                                                 monkeypatch):
    folder, _ = table
    held = serve(monkeypatch, stubbed(pace=0.4))
    heard = Heard()
    try:
        answer = opened(run, folder, 'seats=' + json.dumps(['stub/vega', 'stub/orion']), 'host=stub/host')
        holding = json.loads(run('roundtables', 'hold', answer['table'], '--json', cwd=folder).stdout)
        assert holding['state'] == 'held'
        assert heard.told(lambda one: one['kind'] == 'state' and one['payload']['state'] == 'held'), heard.kinds()
        ending =json.loads(run('roundtables', 'end', answer['table'], '--json', cwd=folder).stdout)
        assert ending['state'] in ('ending', 'ended')
        assert heard.ended.wait(LIMIT), f'the table did not end: {heard.kinds()}'
        states = [one['payload']['state'] for one in heard.events if one['kind'] == 'state']
        assert 'held' in states and all(one['audience'] == 'person' for one in heard.events
                                        if one['kind'] in ('state', 'operational', 'seat_lost', 'end'))
        status = json.loads(run('roundtables', 'status', answer['table'], '--json', cwd=folder).stdout)
        assert status['state'] == 'ended' and (folder / status['saved'] / 'export.json').is_file()
        # a submission the table ended before Jev judged it is told, as unjudged, when the engine lists one
        exported = json.loads((folder / status['saved'] / 'export.json').read_text())
        if any(one.get('outcome') == 'unjudged' for one in exported['submissions']):
            assert any(one['kind'] == 'turn' and one['payload'].get('outcome') == 'unjudged' for one in heard.events)
    finally:
        heard.close()
        held.shutdown()
    assert gone(lambda: seat_entries(home))


def test_a_table_with_more_seats_than_free_agent_slots_is_refused_before_any_seat_starts(run, home, table):
    folder, log = table
    run('set', '--dispatch-agents=1', cwd=folder)
    refused = run('roundtables', 'open', 'Too many seats?', f'address={ADDRESS}',
                  'seats=' + json.dumps(['claude/haiku', 'stub/vega']), cwd=folder, ok=False)
    assert refused.returncode != 0 and 'needs 2 free agent slots and 1 is free' in refused.stderr, refused.stderr
    listed = json.loads(run('roundtables', 'tables', '--json', cwd=folder).stdout)['tables']
    assert [one['state'] for one in listed] == ['refused']
    assert not log.exists() and not seat_entries(home), 'no seat started and no slot is held'


def running(pid: int) -> bool:
    """Whether a process runs: an ended follower this test process started and never reaped is a zombie."""
    try:
        return Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()[0] != 'Z'
    except OSError:
        return False


def page_servers() -> list[int]:
    """The engine's page servers of this test's engine home that still run."""
    found = []
    for proc in Path('/proc').iterdir():
        try:
            words = (proc / 'cmdline').read_bytes().split(b'\0')
            environ = (proc / 'environ').read_bytes().split(b'\0')
        except OSError:
            continue
        if b'web' in words and f'ROUNDTABLE_HOME={os.environ["ROUNDTABLE_HOME"]}'.encode() in environ:
            found.append(int(proc.name))
    return found


@pytest.mark.timeout(100)
def test_unjudged_acp_table_runs_and_continues_without_provider_credentials(run, home, table, monkeypatch):
    """Real shipped MCP/ACP processes use fake agents only, retaining saved records across continuation."""
    folder, log = table
    run('set', '--no-jev', cwd=folder)
    monkeypatch.delenv('OPENROUTER_API_KEY', raising=False)
    heard = Heard()
    answer = None
    try:
        answer = opened(run, folder, 'seats=' + json.dumps(['claude/haiku', 'claude/opus']), 'judging=false')
        assert heard.ended.wait(35), heard.kinds()
        before = json.loads(run('roundtables', 'status', answer['table'], '--json', cwd=folder).stdout)
        original_record = folder / before['saved'] / 'export.json'
        original_bytes = original_record.read_bytes()
        assert gone(lambda: seat_entries(home))
        assert gone(lambda: json.loads(run('roundtables', 'status', answer['table'], '--json', cwd=folder).stdout)
                    ['follower'] == 'running')
        heard.ended.clear()
        resumed = json.loads(run('roundtables', 'continue', answer['table'], '--json', cwd=folder).stdout)
        assert resumed['table'] == answer['table'] and resumed['state'] == 'running'
        assert heard.ended.wait(35), heard.kinds()
        after = json.loads(run('roundtables', 'status', answer['table'], '--json', cwd=folder).stdout)
        assert after['discussion'] == before['discussion']
        assert after['seats'] == before['seats'] and after['seated'] == before['seated']
        assert len(after['topics']) == 2 and after['answered']
        assert original_record.read_bytes() == original_bytes
        assert after['saved'] != before['saved']
        exported = json.loads((folder / after['saved'] / 'export.json').read_text())
        assert 'judgments' not in exported
        assert all(one['kind'] in ('seat', 'chair') for one in exported['submissions'])
        from metaform.modules.roundtables.roundtable import store as private
        assert not private.judgments(after['discussion'])
        assert any(one['kind'] == 'handoff' for one in private.submissions(after['discussion']))
        prompts = [line['message']['params'] for line in map(json.loads, log.read_text().splitlines())
                   if line.get('message', {}).get('method') == 'session/prompt']
        assert any('Shared continuation:' in json.dumps(one) for one in prompts)
        assert gone(lambda: seat_entries(home))
    finally:
        if answer and not heard.ended.is_set():
            run('roundtables', 'end', answer['table'], cwd=folder, ok=False)
        heard.close()


@pytest.mark.skipif(not sys.platform.startswith('linux'), reason='reads /proc for the page servers left')
@pytest.mark.timeout(2 * LIMIT + 60)
def test_a_stopped_follower_ends_its_table_before_its_slots_go_back(run, home, table, monkeypatch):
    """The follower's SIGTERM, and the person's Stop all, which asks it with one: the table is ended through the
    engine, its seats close, the person is told why, and only then do the slots go back."""
    folder, _ = table
    held = serve(monkeypatch, stubbed(pace=2.0))  # slow enough that each stop lands while the table discusses
    try:
        for stop in ('sigterm', 'stop-all'):
            heard = Heard()
            try:
                answer = opened(run, folder, 'seats=' + json.dumps(['claude/haiku', 'stub/vega']), 'host=stub/host')
                with Store('proj', module='roundtables').tables(write=False) as tx:
                    row = dict(tx.get('tables', {'table_id': answer['table']}) or {})
                assert len(seat_entries(home)) == 2 and follow.alive(row['follower'])
                said = ''
                if stop == 'sigterm':
                    os.kill(int(row['follower']), signal.SIGTERM)
                else:
                    said = run('dispatch', 'stop-all', '--json', cwd=folder).stdout
                table_id = answer['table']
                assert heard.told(lambda one: one['table_id'] == table_id and one['kind'] == 'end'), (  # noqa: B023
                    f'{stop}: the table did not end: {heard.kinds()} {said}')
                own = [one for one in heard.events if one['table_id'] == table_id]
                told = [one for one in own if one['payload'].get('what') == 'follower_stopped']
                assert told and told[0]['audience'] == 'person', (stop, [one['kind'] for one in own])
                end = next(one for one in own if one['kind'] == 'end')
                assert end['audience'] == 'person'
                engine_said = engine.call(folder, 'status', discussion=int(row['discussion']))
                assert engine_said['state'] == 'ended' and engine_said.get('runner') == 'stopped', (stop, engine_said)
                assert 'ended by its chair' in str(engine_said.get('reason')), 'the follower ended it, the table did not'
                pid = int(row['follower'])
                assert gone(lambda: running(pid)), f'{stop}: the follower ended'  # noqa: B023
                assert gone(lambda: seat_entries(home)), f'{stop}: the slots went back'
                assert not page_servers(), f'{stop}: no page server is left'
            finally:
                heard.close()
    finally:
        held.shutdown()


def test_an_engine_that_fails_on_open_refuses_the_table_at_once_and_holds_no_slot(run, home, table, tmp_path,
                                                                                    monkeypatch):
    folder, _ = table
    broken(monkeypatch, tmp_path)
    began = time.monotonic()
    refused = run('roundtables', 'open', 'Does it open?', f'address={ADDRESS}', 'seats=' + json.dumps(['stub/vega']),
                  cwd=folder, ok=False)
    assert refused.returncode != 0 and 'The table did not open' in refused.stderr, refused.stderr
    assert time.monotonic() - began < engine.CALL_LIMIT, 'refused at once, not at the follower\'s deadline'
    listed = json.loads(run('roundtables', 'tables', '--json', cwd=folder).stdout)['tables']
    assert [one['state'] for one in listed] == ['refused'] and 'The table did not open' in listed[0]['reason']
    assert gone(lambda: seat_entries(home)), 'no slot is held'


def test_finished_result_keeps_each_topics_rankings_without_requesting_a_system_report(run, table, tmp_path):
    from metaform.modules.dispatch.orchestration import user_updates

    folder, _ = table
    store = Store('proj', module='roundtables')
    topics = [
        {'number': 1, 'title': 'Storage', 'synthesis': {'ideas': [
            {'id': 'I1', 'name': 'Append events', 'summary': 'Persist each change.'}]},
         'borda': {'order': ['I1'], 'points': {'I1': 3}},
         'host_summary': {'name': 'host', 'text': 'Keep events.'}},
        {'number': 2, 'title': 'Delivery', 'synthesis': {'ideas': [
            {'id': 'I2', 'name': 'Direct result', 'summary': 'Show the result on the page.'}]},
         'borda': {'order': ['I2'], 'points': {'I2': 4}},
         'host_summary': {'name': 'host', 'text': 'Show results directly.'}},
    ]
    mechanical = tmp_path / 'mechanical.md'
    mechanical.write_text('Full transcript.\n', encoding='utf-8')
    with store.tables() as tx:
        tx.insert('tables', {'table_id': 'finished', 'topic': 'How should results arrive?', 'opening': '.',
                             'seats': ['stub/vega'], 'spend': 0.0, 'state': 'running', 'created': follow.now(),
                             'followed': {'topics': {'1': {'ideas': True, 'rankings': 1, 'summary': True}}}})

    class Page:
        def get(self, path, **_kwargs):
            if path.endswith('/turns'):
                return {'turns': [], 'latest': 0}
            if path.endswith('/topics'):
                return {'topics': topics}
            if path.endswith('/download/export.json'):
                return {'topics': topics, 'mechanical_report': str(mechanical)}
            assert path == '/tables/7'
            return {'reason': 'covered'}

    dispatch = Context('dispatch', folder, project='proj', store=Store('proj'))
    before = user_updates(dispatch)
    follower = follow.Follower(Context('roundtables', folder, project='proj', store=store), 'finished')
    follower.ended(Page(), 7)
    status = json.loads(run('roundtables', 'status', 'finished', 'report=true', '--json', cwd=folder).stdout)
    assert status['topics'] == topics and status['answer'] == 'Show results directly.'
    assert all(text in status['report_text'] for text in ('Storage', 'Delivery', 'Keep events.', 'Show results directly.'))
    assert status['report'].endswith('/mechanical-report.md')
    assert (folder / status['saved'] / 'export.json').is_file()
    assert user_updates(dispatch) == before
    assert follower.followed['topics']['1']['summary'] is True, 'result data must preserve follower cursors'
    result = json.loads(run('roundtables', 'events', 'finished', '--json', cwd=folder).stdout)['events'][-1]
    assert result['kind'] == 'end' and result['topics'] == topics
    assert result['answer'] == status['answer'] and result['saved'] == status['saved']


def test_session_materials_archive_without_changing_the_checkout(tmp_path, monkeypatch):
    from types import SimpleNamespace

    from metaform.modules.roundtables import chain
    session = tmp_path / 'docs' / 'roundtables' / 'session-test'
    session.mkdir(parents=True)
    (session / 'minutes.md').write_text('Decisions and disagreements.', encoding='utf-8')
    calls = []

    def git(arguments, **kwargs):
        calls.append((arguments, kwargs))
        value = {'write-tree': 'saved-tree', 'commit-tree': 'saved-commit'}.get(arguments[1], '')
        return SimpleNamespace(returncode=0, stdout=value, stderr='')

    monkeypatch.setattr(chain.subprocess, 'run', git)
    assert chain.pushed(tmp_path, session) == 'roundtables/session-test'
    assert session.with_suffix('.zip').is_file()
    assert calls[-1][0] == ['git', 'push', 'origin', 'saved-commit:refs/heads/roundtables/session-test']
    assert all(one[1]['env']['GIT_INDEX_FILE'] for one in calls)
    assert (session / 'minutes.md').read_text(encoding='utf-8') == 'Decisions and disagreements.'


@pytest.fixture
def table_follower(table):
    folder, _ = table
    store = Store('proj', module='roundtables')
    with store.tables() as tx:
        tx.insert('tables', {'table_id': 'minutes', 'topic': 'Keep decisions understandable', 'opening': '.',
                             'seats': ['claude/haiku'], 'spend': 0.0, 'state': 'running', 'created': follow.now()})
    return follow.Follower(Context('roundtables', folder, project='proj', store=store), 'minutes'), folder


@pytest.mark.parametrize('state', ['held', 'ended'])
def test_follower_page_failure_delivers_recovered_state_before_releasing_seats(table_follower, monkeypatch, state):
    follower, _ = table_follower
    calls = []

    class Recovery:
        def changes(self, number):
            assert number == 7
            yield {'state': state, 'reason': 'held by its chair.' if state == 'held' else 'ended by its chair.',
                   'runner': 'running'}
            yield {'state': state, 'reason': 'held by its chair.' if state == 'held' else 'ended by its chair.',
                   'runner': 'stopped'}

        def get(self, path, **kwargs):
            if path.endswith('/turns'):
                return {'turns': [], 'latest': 0}
            if path.endswith('/topics'):
                return {'topics': []}
            if path.endswith('/download/export.json'):
                return {'topics': [], 'submissions': []}
            assert path == '/tables/7'
            return {'reason': 'ended by its chair.'}

        def close(self):
            calls.append('closed')

    def page(*_args):
        calls.append('page')
        if calls == ['page']:
            raise RuntimeError('The initial page did not start.')
        return Recovery()

    monkeypatch.setattr(engine, 'Page', page)
    monkeypatch.setattr(engine, 'call', lambda _folder, verb, **kwargs: calls.append((verb, kwargs)))
    follower.followed_to_end(7)
    with follower.store.tables(write=False) as tx:
        recorded = [dict(one) for one in tx.rows('events', {'table_id': 'minutes'}, limit=0).results]
    assert [one['kind'] for one in recorded] == ['operational', 'state', *(['end'] if state == 'ended' else [])]
    assert recorded[1]['audience'] == 'person'
    reason = 'held by its chair.' if state == 'held' else 'ended by its chair.'
    assert recorded[1]['payload'] == {'state': state, 'reason': reason}
    assert follower.followed['state'] == state
    assert follower.row()['state'] == state and follower.row()['reason'] == reason
    assert calls == ['page', ('hold', {'discussion': 7, 'chair': None}), 'page', 'closed']


def test_follower_delivers_turns_and_result_without_a_writer_or_generated_documents(table_follower, monkeypatch):
    from metaform.modules.roundtables.roundtable import harness, openrouter
    from metaform.modules.web import server
    from metaform.modules.web.tests.test_web import _Handler

    follower, root = table_follower
    session = root / 'docs' / 'roundtables' / 'session-authored'
    session.mkdir(parents=True)
    (session / 'decisions.md').write_text('Participants agreed to preserve the decision.', encoding='utf-8')
    follower.followed['session'] = {'folder': str(session), 'total': 1}
    follower.change(discussion=7)
    model_requests = []

    def unexpected(*args, **kwargs):
        model_requests.append((args, kwargs))
        raise AssertionError('A follower must not request generated minutes or another model response.')

    monkeypatch.delenv('PYTEST_CURRENT_TEST', raising=False)
    monkeypatch.setattr(harness, 'Session', unexpected)
    monkeypatch.setattr(openrouter, 'post', unexpected)
    turns = [
        {'n': 1, 'topic': 1, 'round': 1, 'seat': 'Alpha', 'outcome': 'kept', 'text': 'Preserve the decision.'},
        {'n': 2, 'topic': 1, 'round': 1, 'seat': 'Beta', 'outcome': 'vetoed', 'text': 'Keep the disagreement.',
         'veto_reason': 'Topic relevance scored 0.42, below the required 0.6.'},
    ]
    topics = [{'number': 1, 'title': 'Decisions', 'host_summary': {'name': 'Alpha', 'text': 'Decision preserved.'}}]
    permission = {'position': 0, 'request': 'participant-write', 'state': 'waiting', 'name': 'Alpha'}

    class Page:
        def __init__(self):
            self.reads = []

        def changes(self, _number):
            yield {'latest': 2, 'topic': 0, 'stage': 'discussion', 'staged': 1, 'events': 1, 'state': 'running'}
            yield {'latest': 2, 'topic': 0, 'stage': 'discussion', 'staged': 1, 'events': 1,
                   'state': 'ended', 'runner': 'stopped'}

        def get(self, path, **kwargs):
            self.reads.append(path)
            if path.endswith('/turns'):
                return {'turns': [one for one in turns if one['n'] > kwargs.get('since', 0)], 'latest': 2}
            if path.endswith('/topics'):
                return {'topics': topics}
            if path.endswith('/download/export.json'):
                return {'topics': topics, 'turns': turns}
            assert path == '/tables/7'
            return {'reason': 'complete', 'events': [
                {'number': 1, 'kind': 'permission', 'text': json.dumps(permission)}]}

    page = Page()
    follower.follow(page, 7)
    pending = getattr(follower, 'summary_thread', None)
    if pending is not None:
        pending.join(timeout=5)
        assert not pending.is_alive()
    assert model_requests == []
    with follower.store.tables(write=False) as tx:
        recorded = [dict(one) for one in tx.rows('events', {'table_id': 'minutes'}, limit=0).results]
    assert [one['kind'] for one in recorded] == ['turn', 'veto', 'stage', 'summary', 'permission', 'state', 'state', 'end']
    assert recorded[1]['payload']['veto_reason'] == turns[1]['veto_reason']
    assert recorded[4]['audience'] == 'person' and recorded[4]['payload'] == permission
    assert follower.followed['turns'] == 2 and follower.row()['answered'] is True
    assert not (root / 'docs' / 'roundtables' / '7-notes').exists()
    assert list(session.iterdir()) == [session / 'decisions.md']
    saved = root / follower.followed['saved']
    shared = json.loads((saved / 'export.json').read_text())
    assert [one['text'] for one in shared['submissions']] == ['Preserve the decision.']
    assert 'Keep the disagreement.' not in json.dumps(shared)
    assert 'veto_reason' not in json.dumps(shared)

    before = list(page.reads)
    unchanged = {'latest': 2, 'topic': 0, 'stage': 'discussion', 'staged': 1, 'events': 1, 'state': 'ended'}
    for _ in range(20):
        follower.moved(page, 7, unchanged, unchanged)
    assert page.reads == before, 'Unrelated changes must not reread the table.'

    monkeypatch.setattr(server, 'module_verb', lambda *_args: {'discussion': 7, 'materials': str(session)})
    monkeypatch.setattr(server, 'project_folder', lambda _given: ('proj', root))
    handler = _Handler()
    server.Handler.roundtable_notes(handler, {'project': 'proj', 'note': 'decisions.md'}, {'table': 'minutes'})
    assert handler.answers == [(200, {'path': 'decisions.md',
                                      'text': 'Participants agreed to preserve the decision.', 'cut': False})]


def test_follower_open_forwards_the_captured_permissions(table_follower, monkeypatch):
    follower, root = table_follower
    permissions = {'claude': {'prompts': False, 'mode': 'bypassPermissions'},
                   'codex': {'prompts': True, 'mode': 'auto-edit'}}
    follower.followed['permissions'] = permissions
    follower.change(followed=follower.followed)
    calls = []
    monkeypatch.setattr(engine, 'call', lambda project_folder, verb, **kwargs:
                        calls.append((project_folder, verb, kwargs)) or {'discussion': 7, 'chair': 'chair'})
    follower.opened(follower.row())
    assert calls[0][0:2] == (root, 'open')
    assert calls[0][2]['permissions'] == permissions
    assert follower.row()['followed']['permissions'] == permissions


def test_abort_archives_bridge_records_and_session_materials(table_follower, tmp_path):
    follower, root = table_follower
    session = root / 'docs' / 'roundtables' / 'session-current'
    session.mkdir(parents=True)
    (session / 'notes.md').write_text('Existing participant work.', encoding='utf-8')
    legacy = root / 'docs' / 'roundtables' / '7-notes' / 'minutes'
    legacy.mkdir(parents=True)
    (legacy / '01.md').write_text('Prior generated minutes.', encoding='utf-8')
    follower.followed['session'] = {'folder': str(session)}
    follower.change(discussion=7)
    follower.emit('minutes', 'person', text='Saved explanation.', topic=1, seat='Alpha')
    engine_files = tmp_path / 'engine-aborted'
    engine_files.mkdir()
    (engine_files / 'turn.json').write_text('{"text": "Original contribution."}', encoding='utf-8')
    row = follower.row()
    shelf = follow.archive(follower.ctx, row, str(engine_files))
    assert shelf.parent.name == 'roundtables' and shelf.parent.parent.name == 'backups'
    assert (shelf / session.name / 'notes.md').read_text() == 'Existing participant work.'
    assert (shelf / '7-notes' / 'minutes' / '01.md').read_text() == 'Prior generated minutes.'
    assert (shelf / 'engine' / 'turn.json').is_file()
    assert json.loads((shelf / 'table.json').read_text())['table_id'] == 'minutes'
    assert json.loads((shelf / 'events.json').read_text())[0]['payload']['text'] == 'Saved explanation.'
    assert follower.row() is None and not session.exists() and not engine_files.exists()
    with follower.store.tables(write=False) as tx:
        assert not tx.rows('events', {'table_id': 'minutes'}).results


def test_concurrent_follower_events_keep_sequences_cursors_and_publication_together(table_follower, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor

    follower, _ = table_follower
    published = []
    start = threading.Barrier(2)

    def observe(ctx, topic, payload):
        if topic != follow.TOPIC:
            return []
        with follower.store.tables(write=False) as tx:
            stored = dict(tx.get('events', {'table_id': 'minutes', 'seq': payload['seq']}))
            cursor = dict(tx.get('tables', {'table_id': 'minutes'}))['followed']
        assert stored['payload']['value'] == payload['value']
        assert cursor[f'writer_{payload["writer"]}'] >= payload['value']
        published.append(payload['seq'])
        return []

    monkeypatch.setattr(Context, 'publish', observe)

    def write(writer):
        start.wait(timeout=5)
        for value in range(10):
            follower.followed[f'writer_{writer}'] = value
            follower.emit('operational' if writer else 'turn', 'person', writer=writer, value=value)

    with ThreadPoolExecutor(max_workers=2) as workers:
        list(workers.map(write, (0, 1)))
    with follower.store.tables(write=False) as tx:
        stored = [dict(one) for one in tx.rows('events', {'table_id': 'minutes'}, limit=0).results]
        cursor = dict(tx.get('tables', {'table_id': 'minutes'}))['followed']
    assert [one['seq'] for one in stored] == list(range(1, 21))
    assert published == list(range(1, 21))
    assert cursor['writer_0'] == cursor['writer_1'] == 9
