"""The paperclip module against a Paperclip server simulated in memory: no network, no token, no Paperclip agent. The
server answers the calls client.py makes as Paperclip's REST API answers them, and records each one; tests reach it
through the module's OPENER, the opener every Client the module makes is given."""
from __future__ import annotations

import io
import json
import subprocess
import sys
import time
import urllib.error
import urllib.parse
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any

import pytest

from metaform.data import Node, Store, StoreError
from metaform.module import Stop, context
from metaform.modules import paperclip

pytestmark = pytest.mark.kind('simulation')

COMPANY = 'co-1'
AGENT = '11111111-1111-4111-8111-111111111111'  # the Paperclip agent whose process adapter runs heartbeat
WORKER = '22222222-2222-4222-8222-222222222222'  # a Paperclip agent that works what send hands it


class Paperclip:
    """One Paperclip server in memory. `refuse` maps a method and path to the status it fails with."""

    def __init__(self) -> None:
        self.issues: dict[str, dict[str, Any]] = {}
        self.comments: dict[str, list[dict[str, Any]]] = {}
        self.documents: dict[tuple[str, str], dict[str, Any]] = {}
        self.interactions: dict[str, list[dict[str, Any]]] = {}
        self.calls: list[tuple[str, str, Any]] = []
        self.refuse: dict[tuple[str, str], int] = {}
        self.me = AGENT
        self.made = 0
        self.watchers: list[tuple[list[str], Any]] = []  # each watcher started: its argv and folder

    def __call__(self, request: urllib.request.Request, timeout: float | None = None) -> io.BytesIO:
        url = urllib.parse.urlsplit(request.full_url)
        path = url.path.removeprefix('/api')
        method = request.get_method()
        body = json.loads(request.data) if isinstance(request.data, bytes) else None
        self.calls.append((method, path, body))
        status = self.refuse.get((method, path))
        if status is None:
            status, answer = self.answer(method, [urllib.parse.unquote(part) for part in path.split('/')[1:]],
                                         dict(urllib.parse.parse_qsl(url.query)), body)
        else:
            answer = 'refused by the test'
        if status >= 400:
            raise urllib.error.HTTPError(request.full_url, status, 'refused', None,  # type: ignore[arg-type]
                                         io.BytesIO(json.dumps({'error': answer}).encode()))
        return io.BytesIO(b'' if answer is None else json.dumps(answer).encode())

    def issue(self, issue_id: str, **fields: Any) -> dict[str, Any]:
        """A new issue in the company, as a person or another agent made it."""
        self.made += 1
        made = {'id': issue_id, 'identifier': f'PAP-{self.made}', 'companyId': COMPANY, 'status': 'todo',
                'title': issue_id, 'description': None, 'assigneeAgentId': None, 'executionPolicy': None,
                'monitorNextCheckAt': None, **fields}
        self.issues[issue_id] = made
        return made

    def comment(self, issue_id: str, body: str, **author: Any) -> dict[str, Any]:
        said = self.comments.setdefault(issue_id, [])
        made = {'id': f'{issue_id}-c{len(said) + 1}', 'body': body, 'authorType': 'agent', **author}
        said.append(made)
        return made

    def find(self, key: str) -> dict[str, Any] | None:
        return self.issues.get(key) or next((one for one in self.issues.values() if one['identifier'] == key), None)

    def answer(self, method: str, parts: list[str], query: dict[str, str], body: Any) -> tuple[int, Any]:
        if parts == ['health']:
            return 200, {'status': 'ok', 'version': 'test', 'deploymentMode': 'local_trusted'}
        if parts == ['agents', 'me', 'inbox-lite']:
            return 200, [{key: one[key] for key in ('id', 'identifier', 'title', 'status')}
                         for one in self.issues.values()
                         if one['assigneeAgentId'] == self.me and one['status'] in ('todo', 'in_progress', 'blocked')]
        if parts[:1] == ['companies'] and parts[2:] == ['issues'] and method == 'POST':
            replayed = next((one for one in self.issues.values()
                             if one.get('idempotencyKey') == body.get('idempotencyKey')), None)
            return 201, replayed or self.issue(f'issue-{self.made + 1}', **body)
        if parts[:1] == ['companies'] and parts[2:] == ['agents']:
            return 200, [{'id': WORKER, 'name': 'Builder', 'urlKey': 'builder', 'status': 'idle'}]
        if parts[:1] != ['issues'] or len(parts) < 2:
            return 404, f'no route {method} {"/".join(parts)}'
        issue = self.find(parts[1])
        if issue is None:
            return 404, 'Issue not found'
        issue_id, rest = issue['id'], parts[2:]
        if not rest and method == 'GET':
            return 200, issue
        if not rest and method == 'PATCH':
            fields = dict(body)
            if 'comment' in fields:
                self.comment(issue_id, fields.pop('comment'), authorAgentId=self.me)
            if 'executionPolicy' in fields:
                monitor = (fields['executionPolicy'] or {}).get('monitor') or {}
                issue['monitorNextCheckAt'] = monitor.get('nextCheckAt')
            issue.update(fields)
            return 200, issue
        if rest == ['comments'] and method == 'GET':
            said = self.comments.get(issue_id, [])
            after = next((n + 1 for n, one in enumerate(said) if one['id'] == query.get('after')), 0)
            return 200, said[after:] if query.get('order') != 'desc' else said[after:][::-1]
        if rest == ['comments'] and method == 'POST':
            said = self.comments.get(issue_id, [])
            again = next((one for one in said if body.get('clientRequestId')
                          and one.get('clientRequestId') == body['clientRequestId']), None)
            return 201, again or self.comment(issue_id, body['body'], authorAgentId=self.me,
                                              clientRequestId=body.get('clientRequestId'))
        if rest[:1] == ['documents']:
            held = self.documents.get((issue_id, rest[1]))
            if method == 'GET':
                return (200, held) if held else (404, 'Document not found')
            revision = f'rev-{int(str((held or {}).get("latestRevisionId", "rev-0"))[4:]) + 1}'
            self.documents[(issue_id, rest[1])] = {**body, 'latestRevisionId': revision}
            return 200, self.documents[(issue_id, rest[1])]
        if rest == ['interactions'] and method == 'GET':
            return 200, self.interactions.get(issue_id, [])
        if rest == ['interactions'] and method == 'POST':
            cards = self.interactions.setdefault(issue_id, [])
            again = next((one for one in cards if one['idempotencyKey'] == body['idempotencyKey']), None)
            if again is None:
                again = {**body, 'id': f'{issue_id}-card{len(cards) + 1}', 'status': 'pending'}
                cards.append(again)
            return 201, again
        if rest[:1] == ['interactions'] and rest[2:] == ['withdraw']:
            card = next(one for one in self.interactions[issue_id] if one['id'] == rest[1])
            card['status'] = 'withdrawn'
            return 200, card
        if rest == ['checkout']:
            if issue['assigneeAgentId'] not in (None, body['agentId']):
                return 409, 'Issue is checked out by another agent'
            issue.update(status='in_progress', assigneeAgentId=body['agentId'])
            return 200, issue
        if rest == ['release']:
            issue['status'] = 'todo'
            return 200, issue
        return 404, f'no route {method} {"/".join(parts)}'

    def sent(self, method: str, path: str) -> list[Any]:
        """The bodies of each call made with this method to this path."""
        return [body for made, at, body in self.calls if made == method and at == path]

    def answered(self, card: dict[str, Any], *, picked: tuple[str, ...] = (), text: str | None = None) -> None:
        """A person answers a question card in Paperclip's board."""
        card.update(status='answered', result={'answers': [{'questionId': paperclip.ANSWER, 'optionIds': list(picked),
                                                            **({'otherText': text} if text else {})}]})


@pytest.fixture
def server(monkeypatch) -> Paperclip:
    for name in ('PAPERCLIP_API_URL', 'PAPERCLIP_API_KEY', 'PAPERCLIP_COMPANY_ID', 'PAPERCLIP_AGENT_ID',
                 'PAPERCLIP_RUN_ID', 'PAPERCLIP_TASK_ID'):
        monkeypatch.delenv(name, raising=False)
    found = Paperclip()
    monkeypatch.setattr(paperclip, 'OPENER', found)
    started = subprocess.Popen

    def spawn(argv: list[str], *args: Any, **options: Any) -> Any:
        """The watcher a send or web start starts is recorded, never run; any other process runs."""
        if list(argv[-2:]) != ['paperclip', 'watch']:
            return started(argv, *args, **options)
        found.watchers.append((list(argv), options.get('cwd')))
        return SimpleNamespace(pid=4242)
    monkeypatch.setattr(paperclip.subprocess, 'Popen', spawn)
    return found


@pytest.fixture
def folder(run, tmp_path, server):
    """A project whose map holds two Addresses, with paperclip on and its company set."""
    made = tmp_path / 'proj'
    made.mkdir()
    run('add', 'project', 'proj', str(made))
    store = Store('proj')
    with store.atomic():
        layer = store.layer('intake-1', 'intake', 'The map.', kind='intake', mutable=False, hideable=False,
                            provenance={'module': 'intake'}, ready=True)
        store.add_element(layer.name, 'code.timer.kitchen', name_length=2, role='DE')
        store.add_element(layer.name, 'code.alarm.audible', name_length=2, role='SE', name='audible alarm')
        store.add_join(layer.name, 'code.timer.kitchen', 'code.alarm.audible', purpose='Get attention.',
                       ef='Plays a tone.')
    run('enable', 'paperclip', cwd=made)
    run('set', '--paperclip-company', COMPANY, cwd=made)
    return made


def verb(folder, name: str, **nouns: Any) -> Any:
    """Run one of the module's verbs from the command line's surface."""
    return getattr(paperclip, name)(context('paperclip', folder, nouns=nouns))


def ticket(title: str, address: str = 'code.timer.kitchen') -> str:
    return Store('proj').add_work(Node('element', address), None, title=title, task=f'{title}.').id


def sent_out(folder, title: str) -> dict[str, Any]:
    """A ticket sent to Paperclip for WORKER to work: the link send shows."""
    return verb(folder, 'send', id=ticket(title), assignee=WORKER)


def taken_in(folder, server: Paperclip, monkeypatch, address: str = 'code.alarm.audible') -> dict[str, Any]:
    """An issue assigned to AGENT whose document names `address`, taken by one heartbeat: the link it shows."""
    monkeypatch.setenv('PAPERCLIP_AGENT_ID', AGENT)
    made = server.issue('issue-in', title='Make the alarm louder', assigneeAgentId=AGENT)
    server.documents[(made['id'], paperclip.DOCUMENT)] = {'body': f'address: {address}\n', 'latestRevisionId': 'rev-1'}
    beat = verb(folder, 'heartbeat')
    assert [one['issue_id'] for one in beat['taken']] == [made['id']], beat
    return beat['taken'][0]


@pytest.mark.req('CLI-011')
def test_routing_off_carries_once_into_a_jev_decisions_without_paperclip_route(folder):
    """Settings cleanup 2026-10-15: paperclip_jev_route folds into jev_decisions as paperclip.route. Where the person
    turned it off, the carry names every other decision there, so Jev still does not route issues; it runs once."""
    from metaform import home, settings
    scope = home.path_key(folder)
    home.save(scope, 'paperclip', 'paperclip_jev_route', [False], folder=folder)
    with home.chassis(write=True) as db:  # the test home's own start carried nothing and marked it; undo the mark
        db.execute("DELETE FROM meta WHERE key='carried:paperclip-jev-route'")
    settings._carried.clear()
    assert paperclip.carry_route() == [f'{scope}: jev_decisions leaves out paperclip.route']
    chosen = settings.value('jev_decisions', folder)
    assert paperclip.ROUTE_DECISION not in chosen and 'choose_agent' in chosen
    assert home.stored(scope, 'paperclip', 'paperclip_jev_route') is None
    assert paperclip.carry_route() == [], 'once per home'


def test_send_creates_the_issue_and_links_it_and_a_refused_create_gives_the_ticket_back(folder, server):
    store = Store('proj')
    work_id = ticket('Wire the beeper')
    server.refuse[('POST', f'/companies/{COMPANY}/issues')] = 500
    with pytest.raises(Stop, match='create the issue'):
        verb(folder, 'send', id=work_id, assignee=WORKER)
    given_back = store.ticket(work_id).work
    assert given_back.column == 'todo' and not given_back.done
    assert server.issues == {} and verb(folder, 'links') == []

    del server.refuse[('POST', f'/companies/{COMPANY}/issues')]
    shown = verb(folder, 'send', id=work_id, assignee=WORKER)
    issue = server.issues[shown['issue_id']]
    assert shown['ticket'] == work_id and shown['address'] == 'code.timer.kitchen' and shown['works'] == 'paperclip'
    assert issue['assigneeAgentId'] == WORKER and issue['status'] == 'todo'
    assert issue['idempotencyKey'] == f'metaform:{store.project_id}:{work_id}'
    assert server.documents[(issue['id'], paperclip.DOCUMENT)]['body'] == \
        f'address: code.timer.kitchen\nbrief: map_where code.timer.kitchen\nticket: {work_id}\n'
    assert store.ticket(work_id).work.taken_by == 'paperclip'
    assert verb(folder, 'send', id=work_id) == shown and len(server.issues) == 1  # a repeat shows the same link


def test_sync_closes_a_ticket_whose_issue_is_done_or_cancelled_cancelling_through_dispatch_when_it_is_on(
        run, folder, server):
    store = Store('proj')
    run('enable', 'dispatch', cwd=folder)
    done, cancelled = sent_out(folder, 'Wire the beeper'), sent_out(folder, 'Paint the case')
    server.issues[done['issue_id']]['status'] = 'done'
    server.issues[cancelled['issue_id']]['status'] = 'cancelled'
    result = verb(folder, 'sync')
    assert result['failed'] == []
    assert {one['ticket']: one['ticket_now'] for one in result['changed']} == {
        done['ticket']: 'completed', cancelled['ticket']: 'cancelled'}
    assert store.ticket(done['ticket']).work.outcome == 'completed'
    by_dispatch = store.ticket(cancelled['ticket']).work
    assert by_dispatch.outcome == 'cancelled' and by_dispatch.resolution == \
        f"Cancelled: {cancelled['issue']} was cancelled in Paperclip."
    assert verb(folder, 'sync')['changed'] == []  # closed once

    run('disable', 'dispatch', cwd=folder)
    alone = sent_out(folder, 'Sand the case')
    server.issues[alone['issue_id']]['status'] = 'cancelled'
    verb(folder, 'sync')
    closed = store.ticket(alone['ticket']).work
    assert closed.outcome == 'cancelled' and closed.resolution == f"{alone['issue']} is cancelled in Paperclip."


def test_a_ticket_the_person_cancels_cancels_its_issue_once(folder, server):
    shown = sent_out(folder, 'Wire the beeper')
    Store('proj').finish_work(shown['ticket'], 'Not needed.', 'the person changed plans', outcome='cancelled')
    assert verb(folder, 'sync')['changed'] == [{'issue': shown['issue'], 'ticket': shown['ticket'],
                                                'issue_now': 'cancelled'}]
    issue_path = f"/issues/{shown['issue_id']}"
    assert server.issues[shown['issue_id']]['status'] == 'cancelled'
    assert len(server.sent('PATCH', issue_path)) == 1
    assert 'Not needed.' in server.comments[shown['issue_id']][-1]['body']
    verb(folder, 'sync')
    assert len(server.sent('PATCH', issue_path)) == 1


def test_heartbeat_takes_an_issue_naming_an_address_and_leaves_one_note_on_one_naming_none(
        folder, server, monkeypatch):
    lost = server.issue('issue-lost', title='Quarterly paperwork', assigneeAgentId=AGENT)
    refused = server.issue('issue-refused', title='Refused here', assigneeAgentId=AGENT)
    server.documents[(refused['id'], paperclip.DOCUMENT)] = {'body': 'address: code.timer.kitchen\n'}

    def add_work(store, node, condition, **fields):  # the store refuses the one ticket, as it refuses a held node
        if fields.get('title') == 'Refused here':
            raise StoreError('The store refused the ticket.', 'metaform map work')
        return Store.__getattr__(store, 'add_work')(node, condition, **fields)
    monkeypatch.setattr(Store, 'add_work', add_work, raising=False)
    shown = taken_in(folder, server, monkeypatch)
    issue = server.issues[shown['issue_id']]
    record = Store('proj').ticket(shown['ticket']).work
    assert shown['address'] == 'code.alarm.audible' and shown['works'] == 'metaform'
    assert record.column == 'todo' and record.address == 'code.alarm.audible'
    assert issue['status'] == 'in_progress' and issue['assigneeAgentId'] == AGENT
    assert issue['executionPolicy']['monitor']['kind'] == 'external_service'
    assert len(server.comments[shown['issue_id']]) == 1  # the taken note

    # the issue naming no Address gets one note; the one whose ticket the store refuses is checked out and released
    assert len(server.comments[lost['id']]) == 1
    assert server.sent('POST', f"/issues/{refused['id']}/checkout") and \
        server.sent('POST', f"/issues/{refused['id']}/release")
    assert server.issues[refused['id']]['status'] == 'todo'

    again = verb(folder, 'heartbeat')
    assert again['taken'] == [] and len(server.comments[lost['id']]) == 1
    assert [one['issue_id'] for one in verb(folder, 'links')] == [shown['issue_id']]


def test_the_monitor_is_set_again_once_its_check_has_passed_and_not_before(folder, server, monkeypatch):
    shown = taken_in(folder, server, monkeypatch)
    issue_path = f"/issues/{shown['issue_id']}"
    policies = len(server.sent('PATCH', issue_path))
    assert verb(folder, 'sync')['changed'] == [] and len(server.sent('PATCH', issue_path)) == policies

    past = (datetime.now(UTC) - timedelta(minutes=1)).isoformat()
    server.issues[shown['issue_id']]['monitorNextCheckAt'] = past
    assert verb(folder, 'sync')['changed'] == [{'issue': shown['issue'], 'ticket': shown['ticket'],
                                                'next_check': 'set'}]
    assert server.issues[shown['issue_id']]['monitorNextCheckAt'] > datetime.now(UTC).isoformat()


def test_a_question_at_the_address_goes_out_once_as_a_card_and_its_answer_comes_back_as_a_reply(
        folder, server, monkeypatch):
    store = Store('proj')
    shown = taken_in(folder, server, monkeypatch)
    at = Node('element', 'code.alarm.audible')
    asked = store.ask(at, 'Which tone should it play?', suggestions=['Chime'], work=shown['ticket'])
    dropped = store.ask(at, 'Louder than the oven?', work=shown['ticket'])
    store.ask(at, 'Another ticket\'s question.')
    assert verb(folder, 'sync')['changed'] == [{'issue': shown['issue'], 'ticket': shown['ticket'],
                                                'questions_out': 2}]
    cards = server.interactions[shown['issue_id']]
    question = cards[0]['payload']['questionSet']['questions'][0]
    assert cards[0]['kind'] == 'ask_user_questions' and cards[0]['resolverPolicy'] == 'human_only'
    assert question['prompt'] == 'Which tone should it play?' and question['answerMode'] == 'text'
    assert question['initialText'] == 'Chime'
    assert verb(folder, 'sync')['changed'] == [] and len(cards) == 2  # once

    server.answered(cards[0], text='Chime, twice')
    store.reply(dropped.id, 'Yes.')  # answered here first: its card is withdrawn
    assert verb(folder, 'sync')['changed'] == [{'issue': shown['issue'], 'ticket': shown['ticket'],
                                                'answers_in': 1}]
    replied = next(one for one in store.messages(at, limit=0).results if one.id == asked.id)
    assert replied.closed and replied.answer == 'Chime, twice'
    assert cards[1]['status'] == 'withdrawn'
    verb(folder, 'sync')
    assert next(one for one in store.messages(at, limit=0).results if one.id == asked.id).answer == 'Chime, twice'


@pytest.mark.parametrize('choice, issue_now', [('retry', 'todo'), ('close', 'cancelled')])
def test_a_failed_ticket_puts_its_issue_in_review_with_a_card_whose_retry_forgets_the_link(
        folder, server, monkeypatch, choice, issue_now):
    shown = taken_in(folder, server, monkeypatch)
    Store('proj').finish_work(shown['ticket'], 'The beeper is not wired.', 'no hardware here', outcome='failed')
    assert verb(folder, 'sync')['changed'] == [{'issue': shown['issue'], 'ticket': shown['ticket'],
                                                'issue_now': 'in_review'}]
    issue = server.issues[shown['issue_id']]
    [card] = server.interactions[shown['issue_id']]
    assert issue['status'] == 'in_review' and issue['executionPolicy'] is None
    assert [one['id'] for one in card['payload']['questionSet']['questions'][0]['options']] == ['retry', 'close']
    assert verb(folder, 'sync')['changed'] == [] and issue['status'] == 'in_review'  # reported once

    server.answered(card, picked=(choice,))
    verb(folder, 'sync')
    assert issue['status'] == issue_now
    links = [one['issue_id'] for one in verb(folder, 'links')]
    assert links == ([] if choice == 'retry' else [shown['issue_id']])


def test_what_the_paperclip_agent_said_reaches_the_address_and_its_last_word_resolves_the_ticket(folder, server):
    """W2I-F3: until send's issues read their comments in and close with the assignee's last word, this fails."""
    store = Store('proj')
    shown = sent_out(folder, 'Wire the beeper')
    server.comment(shown['issue_id'], 'Picked up.', authorType='system')
    server.comment(shown['issue_id'], 'Looking at the cadence timer.', authorAgentId=WORKER)
    finding = 'Root cause: the cadence timer used 500ms ticks; changed to 250ms in src/beep.c.'
    server.comment(shown['issue_id'], finding, authorAgentId=WORKER)
    server.issues[shown['issue_id']]['status'] = 'done'
    verb(folder, 'sync')
    said = [one.text for one in store.messages(Node('element', 'code.timer.kitchen'), limit=0).results]
    assert 'Looking at the cadence timer.' in said and finding in said and 'Picked up.' not in said
    closed = store.ticket(shown['ticket']).work
    assert closed.outcome == 'completed' and closed.resolution == finding


def test_web_started_starts_one_watcher_while_issues_are_followed(folder, server):
    def web_started() -> dict[str, Any] | None:
        return paperclip.web_started({'folder': str(folder)}, context('paperclip', folder))
    assert web_started() is None and server.watchers == []  # no link, nothing to follow

    sent_out(folder, 'Wire the beeper')
    server.watchers.clear()  # what web.started itself starts is checked here
    started = web_started()
    assert started is not None and started['paperclip'] == 'watching'
    assert [(argv[-2:], cwd) for argv, cwd in server.watchers] == [(['paperclip', 'watch'], folder)]

    server.watchers.clear()
    paperclip.run_file('proj').write_text(json.dumps({'pid': 4242, 'beat': time.time()}), encoding='utf-8')
    assert web_started() is None and server.watchers == []  # one watcher beats already


def test_watch_syncs_closes_and_removes_its_record(folder, server, monkeypatch):
    store = Store('proj')
    shown = sent_out(folder, 'Wire the beeper')
    sent_out(folder, 'Paint the case')  # still open, so the watcher has work left and runs until stopped
    finding = 'Root cause fixed in src/beep.c.'
    server.comment(shown['issue_id'], finding, authorAgentId=WORKER)
    server.issues[shown['issue_id']]['status'] = 'done'
    record = paperclip.run_file('proj')
    running: list[tuple[bool, bool]] = []

    def sleep(seconds: float) -> None:  # the first wait after the first sync stops it, as Ctrl-C or SIGTERM does
        running.append((record.exists(), sys.stdout.line_buffering))  # each line reaches its log as said
        raise KeyboardInterrupt
    monkeypatch.setattr(paperclip.time, 'sleep', sleep)
    said: list[str] = []
    assert paperclip.watch(context('paperclip', folder, sink=said.append)) == {'state': 'stopped', 'syncs': 1}
    closed = store.ticket(shown['ticket']).work
    assert closed.outcome == 'completed' and closed.resolution == finding
    assert running == [(True, True)] and not record.exists()
    assert [line for line in said if 'ticket_now completed' in line] == \
        [line for line in said if f"{shown['issue']}, ticket {shown['ticket']}:" in line] and len(said) == 1


def test_send_starts_one_watcher_and_web_start_anywhere_starts_one_for_each_project_left_unwatched(
        folder, server, tmp_path):
    """Round 5, ce3791fd: until send starts the watcher, and web start starts it for every project, this fails."""
    shown = sent_out(folder, 'Wire the beeper')
    assert server.watchers == [(server.watchers[0][0], folder)] and server.watchers[0][0][-2:] == ['paperclip', 'watch']
    assert 'process 4242' in shown['next']  # the watcher just started, before it has written its record
    paperclip.run_file('proj').write_text(json.dumps({'pid': 4242, 'beat': time.time()}), encoding='utf-8')
    verb(folder, 'send', id=shown['ticket'])
    sent_out(folder, 'Wire the bell')
    assert len(server.watchers) == 1  # one runs, so neither a repeat nor another send starts a second

    paperclip.run_file('proj').unlink()
    assert paperclip.web_started({}, context('paperclip', tmp_path)) == {'paperclip': 'watching',
                                                                          'started': {'proj': 4242}}
    assert [cwd for _, cwd in server.watchers] == [folder, folder]


def test_the_watcher_ends_once_nothing_is_left_to_follow_with_its_lines_written_as_said(folder, server, monkeypatch):
    shown = sent_out(folder, 'Wire the beeper')
    server.comment(shown['issue_id'], 'Fixed in src/beep.c.', authorAgentId=WORKER)
    server.issues[shown['issue_id']]['status'] = 'done'

    def sleep(seconds: float) -> None:
        raise AssertionError('the watcher waited with nothing left to follow')
    monkeypatch.setattr(paperclip.time, 'sleep', sleep)
    assert verb(folder, 'watch') == {'state': 'idle', 'syncs': 1}
    assert Store('proj').ticket(shown['ticket']).work.resolution == 'Fixed in src/beep.c.'
    assert not paperclip.run_file('proj').exists() and getattr(sys.stdout, 'line_buffering', True)
